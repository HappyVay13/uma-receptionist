
# =========================
# Structured Logging + Sentry (Phase 2.6)
# =========================
import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

logger = logging.getLogger("repliq")

SENTRY_DSN = os.getenv("SENTRY_DSN")
_SENTRY_MIDDLEWARE_CLASS = None

if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=0.1,
            environment=os.getenv("ENVIRONMENT", "production")
        )
        _SENTRY_MIDDLEWARE_CLASS = SentryAsgiMiddleware
        logger.info("Sentry initialized")

    except Exception as e:
        logger.error(f"Sentry init failed: {e}")


import os
import json
import re
import ast
import base64
import uuid
import logging
import random
from datetime import datetime, timedelta, timezone, date
from typing import Dict, Any, Optional, Tuple, List

import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.responses import Response, StreamingResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client as TwilioClient
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from sqlalchemy import text

from google.oauth2 import service_account
from googleapiclient.discovery import build

from db.database import engine  # expects engine in db/database.py


# -------------------------
# LOGGING
# -------------------------
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("repliq")

app = FastAPI()
if _SENTRY_MIDDLEWARE_CLASS is not None:
    app.add_middleware(_SENTRY_MIDDLEWARE_CLASS)

# -------------------------
# CORS (for Voice SDK / web demo)
# -------------------------
VOICE_SDK_ORIGINS = os.getenv("VOICE_SDK_ORIGINS", "*").strip()
origins = (
    [o.strip() for o in VOICE_SDK_ORIGINS.split(",") if o.strip()]
    if VOICE_SDK_ORIGINS != "*"
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# CONFIG
# -------------------------
TZ = timezone(timedelta(hours=2))  # Europe/Riga

TENANT_ID_DEFAULT = (os.getenv("DEFAULT_CLIENT_ID", "default") or "default").strip()
TEST_TENANT_ID = (os.getenv("TEST_TENANT_ID", "") or "").strip()
ALLOW_DEFAULT_TENANT_FALLBACK = (
    (os.getenv("ALLOW_DEFAULT_TENANT_FALLBACK", "false") or "false").strip().lower()
    in ("1", "true", "yes", "on")
)
RECOVERY_BOOKING_LINK = os.getenv(
    "RECOVERY_BOOKING_LINK", "https://repliq.app/book"
).strip()

APPT_MINUTES = int(os.getenv("APPT_MINUTES", "30"))
WORK_START_HHMM_DEFAULT = os.getenv("WORK_START_HHMM", "09:00").strip()
WORK_END_HHMM_DEFAULT = os.getenv("WORK_END_HHMM", "18:00").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
LLM_INTELLIGENCE_ENABLED = ((os.getenv("LLM_INTELLIGENCE_ENABLED", "true") or "true").strip().lower() in ("1", "true", "yes", "on"))
LLM_INTENT_MIN_CONFIDENCE = float((os.getenv("LLM_INTENT_MIN_CONFIDENCE", "0.60") or "0.60").strip())

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_VALIDATE_SIGNATURE = (
    (os.getenv("TWILIO_VALIDATE_SIGNATURE", "true") or "true").strip().lower()
    in ("1", "true", "yes", "on")
)
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()
BOOKING_CONFIRMATION_ENABLED = ((os.getenv("BOOKING_CONFIRMATION_ENABLED", "true") or "true").strip().lower() in ("1", "true", "yes", "on"))
AUTO_SEND_CONFIRMATION_FOR_TEXT_CHANNELS = ((os.getenv("AUTO_SEND_CONFIRMATION_FOR_TEXT_CHANNELS", "false") or "false").strip().lower() in ("1", "true", "yes", "on"))

# Twilio Voice SDK (WebRTC) token minting
TWILIO_API_KEY_SID = os.getenv("TWILIO_API_KEY_SID", "").strip()
TWILIO_API_KEY_SECRET = os.getenv("TWILIO_API_KEY_SECRET", "").strip()
TWILIO_TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID", "").strip()

VOICE_DEMO_TENANT_ID = (os.getenv("VOICE_DEMO_TENANT_ID", "") or "").strip()
VOICE_CLIENT_TENANT_MAP = (os.getenv("VOICE_CLIENT_TENANT_MAP", "") or "").strip()


SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "").strip().rstrip("/")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
GOOGLE_OAUTH_REDIRECT_URI = (
    os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    or (f"{SERVER_BASE_URL}/google/callback" if SERVER_BASE_URL else "")
)
GOOGLE_OAUTH_SCOPE = "https://www.googleapis.com/auth/calendar"

GOOGLE_TTS_VOICE_NAME = (
    os.getenv("GOOGLE_TTS_VOICE_NAME", "").strip()
    or os.getenv("GOOGLE_TTS_VOICE", "").strip()
    or "lv-LV-Standard-A"
)
GOOGLE_TTS_LANGUAGE_CODE = os.getenv("GOOGLE_TTS_LANGUAGE_CODE", "lv-LV").strip()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip()

GOOGLE_CALENDAR_ID_FALLBACK = os.getenv("GOOGLE_CALENDAR_ID", "").strip()
CLIENT_STATUS_FALLBACK = (
    (os.getenv("CLIENT_STATUS", "trial") or "trial").strip().lower()
)
TRIAL_END_ISO_FALLBACK = (os.getenv("TRIAL_END_ISO", "") or "").strip()

BUSINESS_FALLBACK = {
    "business_name": os.getenv("BIZ_NAME", "Repliq").strip(),
    "address": os.getenv("BIZ_ADDRESS", "Rēzekne").strip(),
    "services_lv": os.getenv("BIZ_SERVICES_LV", "").strip()
    or os.getenv("BIZ_SERVICES", "vīriešu frizūra").strip(),
    "services_ru": os.getenv("BIZ_SERVICES_RU", "").strip()
    or os.getenv("BIZ_SERVICES", "мужская стрижка").strip(),
    "services_en": os.getenv("BIZ_SERVICES_EN", "").strip()
    or os.getenv("BIZ_SERVICES", "men's haircut").strip(),
    "work_start": WORK_START_HHMM_DEFAULT,
    "work_end": WORK_END_HHMM_DEFAULT,
}

BUSINESS_WEEKLY_HOURS_JSON = os.getenv("BIZ_WEEKLY_HOURS_JSON", "").strip()
BUSINESS_BREAKS_JSON = os.getenv("BIZ_BREAKS_JSON", "").strip()
BUSINESS_DAYS_OFF = os.getenv("BIZ_DAYS_OFF", "").strip()
BUSINESS_MIN_NOTICE_MINUTES = int((os.getenv("BIZ_MIN_NOTICE_MINUTES", "0") or "0").strip())
BUSINESS_BUFFER_MINUTES = int((os.getenv("BIZ_BUFFER_MINUTES", "0") or "0").strip())



# -------------------------
# I18N
# -------------------------
I18N: Dict[str, Dict[str, str]] = {
    "lv": {
        "service_unavailable_voice": "Atvainojiet, serviss nav pieejams.",
        "service_unavailable_text": "Serviss nav pieejams.",
        "no_active_booking": "Jums nav aktīvu pierakstu.",
        "cancel_failed": "Neizdevās atcelt pierakstu. Mēģiniet vēlreiz.",
        "cancelled": "Pieraksts atcelts.",
        "reschedule_ask": "Pieraksts {when}. Uz kuru laiku pārcelt?",
        "booking_confirmed": "Paldies! Pieraksts apstiprināts.",
        "booking_confirmed_text": "Apstiprināts: {service} {when}",
        "booking_confirmation_sms": "Pieraksts apstiprināts: {service} {when}. {biz}",
        "booking_failed": "Neizdevās apstiprināt pierakstu. Mēģiniet vēlreiz.",
        "need_service": "Kādu pakalpojumu vēlaties?",
        "need_time": "Kad un cikos jums būtu ērti?",
        "need_name": "Kā jūs sauc?",
        "closed_voice": "Šajā laikā nestrādājam. Nosūtu brīvos laikus ziņā.",
        "closed_text": "Šajā laikā mēs nestrādājam. Varu piedāvāt: 1) {opt1}, 2) {opt2}. Varat arī uzrakstīt citu sev ērtu laiku darba laikā.",
        "busy_voice": "Šis laiks ir aizņemts. Nosūtu variantus ziņā.",
        "busy_text": "Šis laiks diemžēl nav pieejams. Varu piedāvāt: 1) {opt1}, 2) {opt2}. Varat arī uzrakstīt citu sev ērtu laiku.",
        "all_busy_voice": "Atvainojiet, visi laiki ir aizņemti.",
        "all_busy_text": "Visi laiki ir aizņemti. Mēģiniet vēlāk.",
        "greeting": "Labdien! Jūs sazvanījāt {biz}. Izvēlieties valodu: latviešu spiediet vai sakiet viens, русский — divi, English — three.",
        "how_help": "Kā varu palīdzēt?",
        "lang_not_understood": "Nesapratu valodu. Lūdzu, sakiet vai nospiediet viens latviešu, divi krievu, trīs angļu.",
        "voice_fallback": "Atvainojiet, nesadzirdēju. Lūdzu, mēģiniet vēlreiz.",
        "identity_yes": "Jā, jūs sazvanījāt {biz}. Kā varu palīdzēt?",
        "hours_info": "{biz} darba laiks ir no {start} līdz {end}. Kā varu palīdzēt?",
        "greeting_only_reply": "Labdien! Kā varu palīdzēt?",
        "unclear_reply": "Labdien! Precizējiet, lūdzu, kā varu palīdzēt — pieraksts, pārcelšana vai atcelšana?",
        "ask_booking_service": "Protams. Uz kādu pakalpojumu vēlaties pierakstīties?",
        "ask_booking_time": "Labi. Kurš datums un laiks jums būtu ērts?",
        "ask_booking_date": "Uz kuru dienu vēlaties pierakstīties?",
        "ask_booking_time_only": "Labi. Cikos jums būtu ērti?",
        "repeat_yes_no": "Lūdzu, pasakiet jā vai nē.",
        "invalid_time_choice": "Šis laiks nav pieejams. Lūdzu, izvēlieties no piedāvātajiem variantiem.",
        "voice_options_prompt": "Pieejami varianti: 1) {opt1}, 2) {opt2}. Varat izvēlēties vienu no tiem vai uzrakstīt citu sev ērtu laiku.",
        "ask_booking_confirm": "Apstiprināt pierakstu uz {when}? Atbildiet ar jā vai nē.",
        "voice_options_repeat": "Varu piedāvāt šādus laikus: 1) {opt1}, 2) {opt2}. Varat izvēlēties vienu no tiem vai uzrakstīt citu sev ērtu laiku.",
        "smart_slots_prompt": "Pieejamie laiki: 1) {opt1}, 2) {opt2}, 3) {opt3}. Varat izvēlēties numuru vai uzrakstīt citu sev ērtu laiku.",
        "smart_slots_repeat": "Varu piedāvāt šādus laikus: 1) {opt1}, 2) {opt2}, 3) {opt3}. Varat izvēlēties numuru vai uzrakstīt citu sev ērtu laiku.",
        "holiday_closed_text": "Diemžēl šajā dienā mēs nestrādājam. Vai vēlaties citu dienu?",
        "holiday_closed_voice": "Diemžēl šajā dienā mēs nestrādājam. Vai vēlaties citu dienu?",
        "min_notice_text": "Diemžēl tik drīz pierakstu vairs nevaram pieņemt. Varu piedāvāt tuvākos pieejamos laikus.",
        "min_notice_voice": "Diemžēl tik drīz pierakstu vairs nevaram pieņemt. Varu piedāvāt tuvākos pieejamos laikus.",
        "rescheduled_text": "Pieraksts pārcelts: {service} {when}",
        "rescheduled_voice": "Labi, pārcēlu jūsu pierakstu uz {when}.",
        "reschedule_same_time": "Tas ir jūsu pašreizējais pieraksta laiks. Lūdzu, izvēlieties citu laiku.",
        "reschedule_keep_current": "Labi, atstājam pašreizējo pierakstu bez izmaiņām.",
        "reschedule_failed_keep": "Neizdevās pārcelt pierakstu. Esošais pieraksts palika spēkā.",
        "soft_clarify_service": "Lai pierakstītu, man vēl vajag saprast, kuru pakalpojumu vēlaties.",
        "soft_clarify_date": "Saprotu. Vēl pasakiet, uz kuru dienu vēlaties pierakstīties.",
        "soft_clarify_time": "Saprotu. Vēl vajag precīzāku laiku vai izvēli no piedāvātajiem variantiem.",
        "soft_clarify_confirm": "Vai pareizi sapratu, ka vēlaties apstiprināt piedāvāto laiku? Lūdzu, atbildiet ar jā vai nē.",
    },
    "ru": {
        "service_unavailable_voice": "Извините, сервис недоступен.",
        "service_unavailable_text": "Сервис недоступен.",
        "no_active_booking": "У вас нет активных записей.",
        "cancel_failed": "Не удалось отменить запись. Попробуйте ещё раз.",
        "cancelled": "Запись отменена.",
        "reschedule_ask": "Запись на {when}. На какое время перенести?",
        "booking_confirmed": "Спасибо! Запись подтверждена.",
        "booking_confirmed_text": "Подтверждено: {service} {when}",
        "booking_confirmation_sms": "Запись подтверждена: {service} {when}. {biz}",
        "booking_failed": "Не удалось подтвердить запись. Попробуйте ещё раз.",
        "need_service": "Какую услугу вы хотите?",
        "need_time": "На какую дату и время вам удобно?",
        "need_name": "Как вас зовут?",
        "closed_voice": "В это время мы не работаем. Отправляю свободные варианты сообщением.",
        "closed_text": "В это время мы не работаем. Могу предложить: 1) {opt1}, 2) {opt2}. Вы также можете написать другое удобное вам время в рабочие часы.",
        "busy_voice": "Это время занято. Отправляю варианты сообщением.",
        "busy_text": "Это время занято. Могу предложить: 1) {opt1}, 2) {opt2}. Вы также можете написать другое удобное вам время.",
        "all_busy_voice": "Извините, все слоты заняты.",
        "all_busy_text": "Свободных слотов нет. Попробуйте позже.",
        "greeting": "Здравствуйте! Вы позвонили в {biz}. Выберите язык: латышский — один, русский — два, английский — три.",
        "how_help": "Чем могу помочь?",
        "lang_not_understood": "Не удалось определить язык. Пожалуйста, скажите или нажмите: один — латышский, два — русский, три — английский.",
        "voice_fallback": "Извините, я не расслышал. Пожалуйста, повторите.",
        "identity_yes": "Да, вы позвонили в {biz}. Чем могу помочь?",
        "hours_info": "Часы работы {biz}: с {start} до {end}. Чем могу помочь?",
        "greeting_only_reply": "Здравствуйте! Чем могу помочь?",
        "unclear_reply": "Здравствуйте! Уточните, пожалуйста, чем помочь — запись, перенос или отмена?",
        "ask_booking_service": "Конечно. На какую услугу вас записать?",
        "ask_booking_time": "Хорошо. Какая дата и время вам подходят?",
        "ask_booking_date": "На какой день вы хотите записаться?",
        "ask_booking_time_only": "Хорошо. На какое время вам удобно?",
        "repeat_yes_no": "Пожалуйста, скажите да или нет.",
        "invalid_time_choice": "Это время недоступно. Пожалуйста, выберите один из предложенных вариантов.",
        "voice_options_prompt": "Доступны варианты: один — {opt1}, два — {opt2}. Вы можете выбрать один из них или назвать другое удобное время.",
        "ask_booking_confirm": "Подтвердить запись на {when}? Ответьте да или нет.",
        "voice_options_repeat": "Могу предложить такие варианты: 1) {opt1}, 2) {opt2}. Вы можете выбрать один из них или написать другое удобное время.",
        "smart_slots_prompt": "Доступные варианты: 1) {opt1}, 2) {opt2}, 3) {opt3}. Вы можете выбрать номер или написать другое удобное время.",
        "smart_slots_repeat": "Могу предложить такие варианты: 1) {opt1}, 2) {opt2}, 3) {opt3}. Вы можете выбрать номер или написать другое удобное время.",
        "holiday_closed_text": "К сожалению, в этот день мы не работаем. Хотите выбрать другую дату?",
        "holiday_closed_voice": "К сожалению, в этот день мы не работаем. Хотите выбрать другую дату?",
        "min_notice_text": "К сожалению, так скоро записать уже нельзя. Могу предложить ближайшие доступные варианты.",
        "min_notice_voice": "К сожалению, так скоро записать уже нельзя. Могу предложить ближайшие доступные варианты.",
        "rescheduled_text": "Запись перенесена: {service} {when}",
        "rescheduled_voice": "Хорошо, я перенёс вашу запись на {when}.",
        "reschedule_same_time": "Это уже текущее время вашей записи. Пожалуйста, выберите другое время.",
        "reschedule_keep_current": "Хорошо, оставляем текущую запись без изменений.",
        "reschedule_failed_keep": "Не удалось перенести запись. Текущая запись сохранена.",
        "soft_clarify_service": "Чтобы записать вас, мне нужно понять, на какую услугу вы хотите записаться.",
        "soft_clarify_date": "Понял. Подскажите, на какой день вам нужна запись.",
        "soft_clarify_time": "Понял. Нужен более точный вариант времени или выбор из предложенных слотов.",
        "soft_clarify_confirm": "Правильно ли я понял, что вы хотите подтвердить предложенное время? Пожалуйста, ответьте да или нет.",
    },
    "en": {
        "service_unavailable_voice": "Sorry, the service is unavailable.",
        "service_unavailable_text": "Service is unavailable.",
        "no_active_booking": "You do not have any active appointments.",
        "cancel_failed": "Could not cancel the appointment. Please try again.",
        "cancelled": "Your appointment has been cancelled.",
        "reschedule_ask": "Your appointment is on {when}. What time would you like to move it to?",
        "booking_confirmed": "Thank you! Your appointment is confirmed.",
        "booking_confirmed_text": "Confirmed: {service} {when}",
        "booking_confirmation_sms": "Appointment confirmed: {service} {when}. {biz}",
        "booking_failed": "I could not confirm the booking. Please try again.",
        "need_service": "Which service would you like?",
        "need_time": "What date and time would work for you?",
        "need_name": "What is your name?",
        "closed_voice": "We are closed at that time. I am sending available options by message.",
        "closed_text": "We are closed at that time. I can offer: 1) {opt1}, 2) {opt2}. You can also type another time within working hours.",
        "busy_voice": "That time is already booked. I am sending available options by message.",
        "busy_text": "That time is already taken. I can offer: 1) {opt1}, 2) {opt2}. You can also type another convenient time.",
        "all_busy_voice": "Sorry, all slots are busy.",
        "all_busy_text": "No available slots right now. Please try later.",
        "greeting": "Hello! You have reached {biz}. Choose a language: Latvian press or say one, Russian two, English three.",
        "how_help": "How can I help you?",
        "lang_not_understood": "I could not determine the language. Please say or press one for Latvian, two for Russian, three for English.",
        "voice_fallback": "Sorry, I did not catch that. Please try again.",
        "identity_yes": "Yes, you have reached {biz}. How can I help?",
        "hours_info": "{biz} is open from {start} to {end}. How can I help?",
        "greeting_only_reply": "Hello! How can I help?",
        "unclear_reply": "Hello! Please clarify how I can help — booking, rescheduling, or cancellation?",
        "ask_booking_service": "Of course. Which service would you like to book?",
        "ask_booking_time": "Sure. What date and time would work for you?",
        "ask_booking_date": "Which day would you like to book for?",
        "ask_booking_time_only": "Sure. What time works for you?",
        "repeat_yes_no": "Please say yes or no.",
        "invalid_time_choice": "That time is not available. Please choose one of the offered options.",
        "voice_options_prompt": "Available options: one — {opt1}, two — {opt2}. You can choose one of them or say another convenient time.",
        "ask_booking_confirm": "Confirm the booking for {when}? Please answer yes or no.",
        "voice_options_repeat": "I can offer these times: 1) {opt1}, 2) {opt2}. You can choose one of them or type another convenient time.",
        "smart_slots_prompt": "Available times: 1) {opt1}, 2) {opt2}, 3) {opt3}. You can choose a number or type another convenient time.",
        "smart_slots_repeat": "I can offer these times: 1) {opt1}, 2) {opt2}, 3) {opt3}. You can choose a number or type another convenient time.",
        "holiday_closed_text": "Unfortunately, we are closed on that day. Would you like another date?",
        "holiday_closed_voice": "Unfortunately, we are closed on that day. Would you like another date?",
        "min_notice_text": "Unfortunately, it is too soon to book that time now. I can offer the nearest available options.",
        "min_notice_voice": "Unfortunately, it is too soon to book that time now. I can offer the nearest available options.",
        "rescheduled_text": "Appointment moved: {service} {when}",
        "rescheduled_voice": "Okay, I moved your appointment to {when}.",
        "reschedule_same_time": "That is already your current appointment time. Please choose another time.",
        "reschedule_keep_current": "Okay, we will keep your current appointment unchanged.",
        "reschedule_failed_keep": "I could not move the appointment. Your current appointment was kept unchanged.",
        "soft_clarify_service": "To book this for you, I still need to know which service you want.",
        "soft_clarify_date": "Got it. Please tell me which day you would like to book for.",
        "soft_clarify_time": "Understood. I still need a more specific time or one of the offered options.",
        "soft_clarify_confirm": "Just to confirm, would you like to confirm the offered time? Please answer yes or no.",
    },
}


def t(lang: str, key: str, **kwargs: Any) -> str:
    lang = get_lang(lang)
    template = I18N.get(lang, I18N["lv"]).get(key, I18N["lv"].get(key, key))
    try:
        return template.format(**kwargs)
    except Exception:
        return template


# -------------------------
# HUMAN RESPONSE LAYER (2.6)
# -------------------------
def _pick_variant(options: List[str], fallback: str) -> str:
    cleaned = [str(x).strip() for x in options if str(x).strip()]
    return random.choice(cleaned) if cleaned else fallback

def _slot_labels_from_pending(pending: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    for iso in get_offered_slots(pending or {}):
        dtv = parse_dt_any_tz(iso)
        if dtv:
            labels.append(format_dt_short(dtv))
    return labels

def humanize_result(result: Dict[str, Any], conv: Optional[Dict[str, Any]], tenant: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(result or {})
    conv = conv or {}
    tenant = tenant or {}
    lang = get_lang(result.get("lang") or conv.get("lang") or tenant.get("language") or "lv")
    state = conversation_state(conv)
    pending = conv.get("pending") or {}
    settings = tenant_settings(tenant, lang)
    service_text = str(result.get("service") or pending.get("service_display") or "").strip()
    when_text = str(result.get("when") or result.get("datetime_text") or "").strip()
    slots = _slot_labels_from_pending(pending)

    def apply(text_value: str):
        result["msg_out"] = text_value
        result["reply_voice"] = text_value

    if result.get("preserve_text") or result.get("flow_preserved"):
        return result

    if result.get("status") == "greeting":
        if lang == "ru":
            apply(_pick_variant([
                "Здравствуйте! Чем могу помочь?",
                "Добрый день! Чем могу помочь?",
            ], result.get("msg_out") or "Здравствуйте! Чем могу помочь?"))
        elif lang == "en":
            apply(_pick_variant([
                "Hello! How can I help you today?",
                "Hi! How can I help?",
            ], result.get("msg_out") or "Hello! How can I help?"))
        else:
            apply(_pick_variant([
                "Labdien! Kā varu palīdzēt?",
                "Sveiki! Kā varu palīdzēt?",
            ], result.get("msg_out") or "Labdien! Kā varu palīdzēt?"))
        return result

    if result.get("status") == "booked" and when_text:
        if lang == "ru":
            apply(_pick_variant([
                f"Отлично, записал вас на {when_text}.",
                f"Готово, запись подтверждена на {when_text}.",
                f"Хорошо, подтверждаю запись на {when_text}.",
            ], result.get("msg_out") or f"Запись подтверждена на {when_text}."))
        elif lang == "en":
            apply(_pick_variant([
                f"Great, you are booked for {when_text}.",
                f"Done, your appointment is confirmed for {when_text}.",
            ], result.get("msg_out") or f"Your appointment is confirmed for {when_text}."))
        else:
            apply(_pick_variant([
                f"Lieliski, pierakstīju jūs uz {when_text}.",
                f"Gatavs, jūsu pieraksts ir apstiprināts uz {when_text}.",
                f"Labi, apstiprinu pierakstu uz {when_text}.",
            ], result.get("msg_out") or f"Pieraksts apstiprināts uz {when_text}."))
        return result

    if result.get("status") == "reschedule_wait" and when_text:
        if lang == "ru":
            apply(_pick_variant([
                f"Понял. Сейчас у вас запись на {when_text}. На какое время хотите перенести?",
                f"Хорошо, текущая запись стоит на {when_text}. Какое новое время вам удобно?",
            ], result.get("msg_out") or f"Текущая запись на {when_text}. На какое время перенести?"))
        elif lang == "en":
            apply(_pick_variant([
                f"Understood. Your current appointment is at {when_text}. What time would you like instead?",
                f"Okay, you are currently booked for {when_text}. What new time works for you?",
            ], result.get("msg_out") or f"Your appointment is at {when_text}. What time would you like instead?"))
        else:
            apply(_pick_variant([
                f"Sapratu. Pašlaik jums pieraksts ir {when_text}. Uz kuru laiku vēlaties pārcelt?",
                f"Labi, šobrīd jūsu pieraksts ir {when_text}. Kāds jaunais laiks jums derētu?",
            ], result.get("msg_out") or f"Pieraksts ir {when_text}. Uz kuru laiku pārcelt?"))
        return result

    if result.get("status") in {"holiday_closed", "min_notice"}:
        # keep clearer existing text but make it a little warmer
        if lang == "ru":
            apply(result.get("msg_out") or "К сожалению, на это время записать нельзя. Давайте подберём другой вариант.")
        elif lang == "en":
            apply(result.get("msg_out") or "Unfortunately, that time is not available. Let me suggest another option.")
        else:
            apply(result.get("msg_out") or "Diemžēl šis laiks nav pieejams. Atradīsim citu variantu.")
        return result

    if result.get("status") in {"busy", "need_more"} and state == STATE_AWAITING_SERVICE:
        if lang == "ru":
            apply(_pick_variant([
                "Конечно. На какую услугу вас записать?",
                "Хорошо. Что именно хотите сделать?",
                "Подскажите, на какую услугу хотите записаться?",
            ], result.get("msg_out") or "На какую услугу вас записать?"))
        elif lang == "en":
            apply(_pick_variant([
                "Of course. Which service would you like to book?",
                "Sure — what would you like to book?",
            ], result.get("msg_out") or "Which service would you like to book?"))
        else:
            apply(_pick_variant([
                "Protams. Uz kādu pakalpojumu vēlaties pierakstīties?",
                "Labi. Pasakiet, lūdzu, kuru pakalpojumu vēlaties.",
                "Uz kuru pakalpojumu jūs pierakstīt?",
            ], result.get("msg_out") or "Uz kādu pakalpojumu vēlaties pierakstīties?"))
        return result

    if result.get("status") in {"busy", "need_more"} and state == STATE_AWAITING_DATE:
        if lang == "ru":
            apply(_pick_variant([
                "Хорошо. На какой день вас записать?",
                "Отлично. Какая дата вам удобна?",
                "Подскажите, на какой день хотите запись?",
            ], result.get("msg_out") or "На какой день вас записать?"))
        elif lang == "en":
            apply(_pick_variant([
                "Sure. Which day would work for you?",
                "Okay. What date would you prefer?",
            ], result.get("msg_out") or "Which day would work for you?"))
        else:
            apply(_pick_variant([
                "Labi. Uz kuru dienu vēlaties pierakstīties?",
                "Skaidrs. Kurš datums jums būtu ērts?",
                "Pasakiet, lūdzu, kuru dienu vēlaties.",
            ], result.get("msg_out") or "Uz kuru dienu vēlaties pierakstīties?"))
        return result

    if result.get("status") in {"busy", "need_more"} and state == STATE_AWAITING_TIME and slots:
        if len(slots) >= 3:
            joined = ", ".join(slots[:3])
        else:
            joined = ", ".join(slots[:2])
        if lang == "ru":
            apply(_pick_variant([
                f"Могу предложить такие варианты: {joined}. Что вам удобнее?",
                f"Есть несколько свободных вариантов: {joined}. Какое время подойдёт?",
                f"Свободно вот так: {joined}. Что выбираем?",
            ], result.get("msg_out") or f"Доступны варианты: {joined}."))
        elif lang == "en":
            apply(_pick_variant([
                f"I can offer these times: {joined}. What works best for you?",
                f"There are a few available options: {joined}. Which one suits you?",
            ], result.get("msg_out") or f"Available times: {joined}."))
        else:
            apply(_pick_variant([
                f"Varu piedāvāt šādus laikus: {joined}. Kurš jums der?",
                f"Ir pieejami vairāki varianti: {joined}. Ko izvēlamies?",
                f"Brīvie laiki ir šādi: {joined}. Kurš jums būtu ērtāks?",
            ], result.get("msg_out") or f"Pieejamie laiki: {joined}."))
        return result

    if result.get("status") == "need_more" and state == STATE_AWAITING_CONFIRM and (when_text or str(conv.get("datetime_iso") or "").strip()):
        if not when_text:
            _dtc = parse_dt_any_tz(str(conv.get("datetime_iso") or "").strip())
            when_text = format_dt_short(_dtc) if _dtc else when_text
        if lang == "ru":
            apply(_pick_variant([
                f"Тогда подтверждаем запись на {when_text}?",
                f"Подтверждаем время {when_text}?",
            ], result.get("msg_out") or f"Подтвердить запись на {when_text}?"))
        elif lang == "en":
            apply(_pick_variant([
                f"Shall I confirm the booking for {when_text}?",
                f"Would you like me to confirm {when_text}?",
            ], result.get("msg_out") or f"Confirm the booking for {when_text}?"))
        else:
            apply(_pick_variant([
                f"Tad apstiprinām pierakstu uz {when_text}?",
                f"Vai apstiprināt laiku {when_text}?",
            ], result.get("msg_out") or f"Apstiprināt pierakstu uz {when_text}?"))
        return result

    return result


# -------------------------
# NEW: MULTI-TENANT DB HELPERS
# -------------------------
def tenants_columns() -> List[Dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
            SELECT column_name, is_nullable, column_default, data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='tenants'
            ORDER BY ordinal_position
        """
            )
        ).fetchall()
    return [
        {"name": r[0], "nullable": (r[1] == "YES"), "default": r[2], "type": r[3]}
        for r in rows
    ]


def tenants_pk(cols: List[Dict[str, Any]]) -> str:
    names = {c["name"] for c in cols}
    if "id" in names:
        return "id"
    if "tenant_id" in names:
        return "tenant_id"
    return "id"



def normalize_incoming_to_number(raw_value: str) -> str:
    v = (raw_value or "").strip()
    if v.startswith("whatsapp:"):
        v = v[len("whatsapp:"):]
    if v.startswith("sip:"):
        v = v[len("sip:"):]
    if v.startswith("client:"):
        v = v[len("client:"):]
    v = re.sub(r"[^\d+]", "", v)
    if v and not v.startswith("+") and v.isdigit():
        v = "+" + v
    return v

def looks_like_phone_number(raw_value: str) -> bool:
    v = normalize_incoming_to_number(raw_value)
    digits = re.sub(r"\D", "", v)
    return len(digits) >= 7

def parse_voice_client_tenant_map() -> Dict[str, str]:
    txt = (VOICE_CLIENT_TENANT_MAP or "").strip()
    out: Dict[str, str] = {}
    if not txt:
        return out
    try:
        parsed = json.loads(txt)
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                ks = str(k).strip()
                vs = str(v).strip()
                if ks and vs:
                    out[ks] = vs
            return out
    except Exception:
        pass
    for part in txt.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        left, right = part.split(":", 1)
        left = left.strip()
        right = right.strip()
        if left and right:
            out[left] = right
    return out

def tenant_id_from_client_identity(client_identity: str) -> Optional[str]:
    ident = (client_identity or "").strip()
    if ident.startswith("client:"):
        ident = ident[len("client:"):]

    m = re.match(r"^tenant__([^_]+(?:_[^_]+)*)__.+$", ident)
    if m:
        return m.group(1)

    m2 = re.match(r"^tenant:([^:]+):.+$", ident)
    if m2:
        return m2.group(1)

    mapped = parse_voice_client_tenant_map().get(ident)
    if mapped:
        return mapped

    if VOICE_DEMO_TENANT_ID:
        return VOICE_DEMO_TENANT_ID

    return None

def resolve_voice_tenant_for_incoming(to_number: str, raw_from: str = "") -> Dict[str, Any]:
    test_tenant_id = (TEST_TENANT_ID or "").strip()
    if test_tenant_id:
        tenant = get_tenant(test_tenant_id)
        tenant["_resolved_via"] = "test_tenant_id"
        return normalize_tenant_saas_fields(tenant)

    if looks_like_phone_number(to_number):
        tenant = get_tenant_by_phone(to_number)
        if tenant.get("_id"):
            tenant["_resolved_via"] = "phone_number"
            return normalize_tenant_saas_fields(tenant)

    client_tenant_id = tenant_id_from_client_identity(raw_from)
    if client_tenant_id:
        tenant = get_tenant(client_tenant_id)
        if tenant.get("_id"):
            tenant["_resolved_via"] = "voice_client_identity"
            return normalize_tenant_saas_fields(tenant)

    if ALLOW_DEFAULT_TENANT_FALLBACK:
        tenant = get_tenant(TENANT_ID_DEFAULT)
        tenant["_resolved_via"] = "default_fallback"
        return normalize_tenant_saas_fields(tenant)

    return {
        "_id": None,
        "_resolved_via": "unconfigured",
        "_unconfigured": True,
        "phone_number": normalize_incoming_to_number(to_number),
    }

def upsert_phone_route(phone_number: str, tenant_id: str) -> None:
    phone_number = normalize_incoming_to_number(phone_number)
    tenant_id = (tenant_id or "").strip()
    if not phone_number or not tenant_id:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO phone_routes (phone_number, tenant_id)
                VALUES (:phone_number, :tenant_id)
                ON CONFLICT (phone_number)
                DO UPDATE SET tenant_id = EXCLUDED.tenant_id
                """
            ),
            {"phone_number": phone_number, "tenant_id": tenant_id},
        )

def get_tenant_by_phone(to_number: str) -> Dict[str, Any]:
    to_number = normalize_incoming_to_number(to_number)
    if not to_number or to_number.lower() == "unknown":
        return {}

    cols = tenants_columns()
    col_names = [c["name"] for c in cols]
    pk = tenants_pk(cols)

    with engine.connect() as conn:
        route = conn.execute(
            text("SELECT tenant_id FROM phone_routes WHERE phone_number=:num LIMIT 1"),
            {"num": to_number},
        ).fetchone()

        if not route:
            return {}

        tenant_id = route[0]

        row = conn.execute(
            text(f"SELECT {', '.join(col_names)} FROM tenants WHERE {pk}=:tid LIMIT 1"),
            {"tid": tenant_id},
        ).fetchone()

    if not row:
        return {}

    out: Dict[str, Any] = {}
    for i, name in enumerate(col_names):
        out[name] = row[i]
    out["_id"] = out.get(pk)
    return out

def tenant_is_resolved(tenant: Dict[str, Any]) -> bool:
    return bool(tenant and tenant.get("_id") and not tenant.get("_unconfigured"))


def log_tenant_resolution(channel: str, to_number: str, tenant: Dict[str, Any]) -> None:
    log.info(
        "tenant_resolution channel=%s to=%s normalized_to=%s via=%s tenant_id=%s",
        channel,
        to_number or "",
        normalize_incoming_to_number(to_number),
        tenant.get("_resolved_via"),
        tenant.get("_id"),
    )


def resolve_tenant_for_incoming(to_number: str) -> Dict[str, Any]:
    cleaned_to = normalize_incoming_to_number(to_number)
    test_tenant_id = (TEST_TENANT_ID or "").strip()
    if test_tenant_id:
        tenant = get_tenant(test_tenant_id)
        tenant["_resolved_via"] = "test_tenant_id"
        return normalize_tenant_saas_fields(tenant)

    tenant = get_tenant_by_phone(cleaned_to)
    if tenant.get("_id"):
        tenant["_resolved_via"] = "phone_number"
        return normalize_tenant_saas_fields(tenant)

    if ALLOW_DEFAULT_TENANT_FALLBACK:
        tenant = get_tenant(TENANT_ID_DEFAULT)
        tenant["_resolved_via"] = "default_fallback"
        return normalize_tenant_saas_fields(tenant)

    return {
        "_id": None,
        "_resolved_via": "unconfigured",
        "_unconfigured": True,
        "phone_number": cleaned_to,
    }


def default_value_for_tenant_column(col_name: str, data_type: str) -> Any:
    n = col_name.lower()
    if n in ("business_name", "name"):
        return BUSINESS_FALLBACK["business_name"]
    if n in ("address", "business_address"):
        return BUSINESS_FALLBACK["address"]
    if n in ("services_lv",):
        return BUSINESS_FALLBACK["services_lv"]
    if n in ("services_ru",):
        return BUSINESS_FALLBACK["services_ru"]
    if n in ("services_en",):
        return BUSINESS_FALLBACK["services_en"]
    if n in ("services", "business_services"):
        return BUSINESS_FALLBACK["services_lv"]
    if n in ("work_start", "work_start_hhmm"):
        return BUSINESS_FALLBACK["work_start"]
    if n in ("work_end", "work_end_hhmm"):
        return BUSINESS_FALLBACK["work_end"]
    if n in ("status", "client_status"):
        return CLIENT_STATUS_FALLBACK
    if n in ("trial_end", "trial_end_at"):
        dt = parse_dt_any_tz(TRIAL_END_ISO_FALLBACK)
        return dt or (now_ts() + timedelta(days=14))
    if n in ("calendar_id", "google_calendar_id"):
        return GOOGLE_CALENDAR_ID_FALLBACK or ""
    if n in ("created_at", "updated_at"):
        return now_ts()
    dt = (data_type or "").lower()
    if "timestamp" in dt:
        return now_ts()
    if dt == "date":
        return today_local()
    if dt in ("integer", "bigint", "smallint"):
        return 0
    if dt in ("numeric", "double precision", "real"):
        return 0
    if dt == "boolean":
        return False
    if dt in ("json", "jsonb"):
        return {}
    return ""


def ensure_tenant_row(tenant_id: str) -> None:
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    cols = tenants_columns()
    pk = tenants_pk(cols)
    insert_cols = [pk]
    params: Dict[str, Any] = {"tid": tenant_id}
    for c in cols:
        name = c["name"]
        if name == pk:
            continue
        if (not c["nullable"]) and (c["default"] is None):
            insert_cols.append(name)
            params[name] = default_value_for_tenant_column(name, c["type"])
    col_sql = ", ".join(insert_cols)
    val_sql = ", ".join([":tid" if x == pk else f":{x}" for x in insert_cols])
    sql = f"INSERT INTO tenants ({col_sql}) VALUES ({val_sql}) ON CONFLICT ({pk}) DO NOTHING"
    with engine.begin() as conn:
        conn.execute(text(sql), params)


def get_tenant(tenant_id: str) -> Dict[str, Any]:
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    ensure_tenant_row(tenant_id)
    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = [c["name"] for c in cols]
    select_cols = ", ".join(col_names)
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {select_cols} FROM tenants WHERE {pk}=:tid LIMIT 1"),
            {"tid": tenant_id},
        ).fetchone()
    out: Dict[str, Any] = {"_id": tenant_id}
    if not row:
        return out
    for i, name in enumerate(col_names):
        out[name] = row[i]
    return normalize_tenant_saas_fields(out)


def get_existing_tenant(tenant_id: str) -> Dict[str, Any]:
    tenant_id = (tenant_id or "").strip()
    if not tenant_id:
        return {}
    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = [c["name"] for c in cols]
    select_cols = ", ".join(col_names)
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {select_cols} FROM tenants WHERE {pk}=:tid LIMIT 1"),
            {"tid": tenant_id},
        ).fetchone()
    if not row:
        return {}
    out: Dict[str, Any] = {"_id": tenant_id}
    for i, name in enumerate(col_names):
        out[name] = row[i]
    return normalize_tenant_saas_fields(out)


def get_tenant_or_404(tenant_id: str) -> Dict[str, Any]:
    tenant = get_existing_tenant(tenant_id)
    if not tenant.get("_id"):
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant



# -------------------------
# GOOGLE OAUTH HELPERS (Phase 3 Foundation)
# -------------------------
def oauth_ready() -> bool:
    return bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET and GOOGLE_OAUTH_REDIRECT_URI)

def upsert_tenant_google_account(
    tenant_id: str,
    google_email: Optional[str],
    access_token: str,
    refresh_token: Optional[str],
    token_expiry: Optional[datetime],
    scope: Optional[str],
) -> None:
    tenant_id = (tenant_id or "").strip()
    if not tenant_id:
        return
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM tenant_google_accounts WHERE tenant_id=:tid"), {"tid": tenant_id})
        conn.execute(
            text(
                """
                INSERT INTO tenant_google_accounts
                (tenant_id, google_email, access_token, refresh_token, token_expiry, scope, created_at, updated_at)
                VALUES
                (:tid, :google_email, :access_token, :refresh_token, :token_expiry, :scope, NOW(), NOW())
                """
            ),
            {
                "tid": tenant_id,
                "google_email": google_email,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expiry": token_expiry,
                "scope": scope,
            },
        )

def get_tenant_google_account(tenant_id: str) -> Dict[str, Any]:
    tenant_id = (tenant_id or "").strip()
    if not tenant_id:
        return {}
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT tenant_id, google_email, access_token, refresh_token, token_expiry, scope, created_at, updated_at
                    FROM tenant_google_accounts
                    WHERE tenant_id=:tid
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"tid": tenant_id},
            ).fetchone()
        if not row:
            return {}
        keys = ["tenant_id", "google_email", "access_token", "refresh_token", "token_expiry", "scope", "created_at", "updated_at"]
        return {k: row[i] for i, k in enumerate(keys)}
    except Exception as e:
        log.error("get_tenant_google_account failed tenant_id=%s err=%s", tenant_id, e)
        return {}

def mark_tenant_google_connected(tenant_id: str, is_connected: bool, owner_email: Optional[str] = None) -> None:
    tenant_id = (tenant_id or "").strip()
    if not tenant_id:
        return
    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = {c["name"] for c in cols}
    sets = []
    params: Dict[str, Any] = {"tid": tenant_id, "gc": is_connected}
    if "google_connected" in col_names:
        sets.append("google_connected=:gc")
    if owner_email and "owner_email" in col_names:
        sets.append("owner_email=:owner_email")
        params["owner_email"] = owner_email
    if tenant_has_google_account(tenant_id) and "google_connected" in col_names:
        sets.append("google_connected=true")
    if "updated_at" in col_names:
        sets.append("updated_at=NOW()")
    if not sets:
        return
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE tenants SET {', '.join(sets)} WHERE {pk}=:tid"), params)



def tenant_has_google_account(tenant_id: str) -> bool:
    acct = get_tenant_google_account(tenant_id)
    return bool(str(acct.get("access_token") or "").strip())

def tenant_google_connected_effective(tenant: Dict[str, Any]) -> bool:
    tenant = normalize_tenant_saas_fields(tenant or {})
    if bool(tenant.get("google_connected")):
        return True
    tenant_id = str(tenant.get("_id") or tenant.get("id") or "").strip()
    if not tenant_id:
        return False
    return tenant_has_google_account(tenant_id)

def build_google_oauth_state(tenant_id: str) -> str:
    payload = {"tenant_id": tenant_id, "ts": now_ts().isoformat()}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

def parse_google_oauth_state(state: str) -> Dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode((state or "").encode("utf-8")).decode("utf-8")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}

def build_google_oauth_url(tenant_id: str) -> str:
    params = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_OAUTH_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": build_google_oauth_state(tenant_id),
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)

def exchange_google_code_for_tokens(code_value: str) -> Dict[str, Any]:
    data = {
        "code": code_value,
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    try:
        r = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=30)
        if r.status_code == 200:
            return r.json()
        log.error("google_token_exchange_failed status=%s body=%s", r.status_code, r.text[:500])
    except Exception as e:
        log.error("google_token_exchange_exception err=%s", e)
    return {}

def fetch_google_userinfo(access_token: str) -> Dict[str, Any]:
    if not access_token:
        return {}
    try:
        r = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()
        log.error("google_userinfo_failed status=%s body=%s", r.status_code, r.text[:300])
    except Exception as e:
        log.error("google_userinfo_exception err=%s", e)
    return {}

def fetch_google_calendar_list(access_token: str) -> List[Dict[str, Any]]:
    if not access_token:
        return []
    try:
        r = requests.get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("items", []) if isinstance(data, dict) else []
        log.error("google_calendar_list_failed status=%s body=%s", r.status_code, r.text[:300])
    except Exception as e:
        log.error("google_calendar_list_exception err=%s", e)
    return []

def select_tenant_calendar_id(tenant_id: str, calendar_id: str) -> None:
    tenant_id = (tenant_id or "").strip()
    calendar_id = (calendar_id or "").strip()
    if not tenant_id or not calendar_id:
        return
    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = {c["name"] for c in cols}
    if "calendar_id" not in col_names:
        return
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE tenants SET calendar_id=:cid WHERE {pk}=:tid"), {"cid": calendar_id, "tid": tenant_id})


def token_expiry_from_google(expires_in: Any) -> Optional[datetime]:
    try:
        seconds = int(expires_in)
    except Exception:
        return None
    if seconds <= 0:
        return None
    return now_ts() + timedelta(seconds=seconds)


def google_calendar_choice(calendars: List[Dict[str, Any]]) -> Optional[str]:
    if not calendars:
        return None
    for cal in calendars:
        if cal.get("primary") and str(cal.get("id") or "").strip():
            return str(cal.get("id")).strip()
    if len(calendars) == 1 and str(calendars[0].get("id") or "").strip():
        return str(calendars[0].get("id")).strip()
    return None


def sync_tenant_onboarding_state(tenant_id: str) -> Dict[str, Any]:
    tenant = get_tenant_or_404(tenant_id)
    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = {c["name"] for c in cols}
    google_connected = tenant_google_connected_effective(tenant)
    calendar_selected = bool(str(tenant.get("calendar_id") or "").strip())
    onboarding_completed = bool(google_connected and calendar_selected)

    sets = []
    params: Dict[str, Any] = {"tid": tenant_id}
    if "google_connected" in col_names:
        sets.append("google_connected=:google_connected")
        params["google_connected"] = google_connected
    if "onboarding_completed" in col_names:
        sets.append("onboarding_completed=:onboarding_completed")
        params["onboarding_completed"] = onboarding_completed
    if "updated_at" in col_names:
        sets.append("updated_at=NOW()")

    if sets:
        with engine.begin() as conn:
            conn.execute(text(f"UPDATE tenants SET {', '.join(sets)} WHERE {pk}=:tid"), params)

    return get_tenant_or_404(tenant_id)


# -------------------------
# TIME HELPERS
# -------------------------
def now_ts() -> datetime:
    return datetime.now(TZ)


def today_local() -> date:
    return now_ts().date()


def parse_dt_any_tz(iso: str) -> Optional[datetime]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    except Exception:
        return None


# -------------------------
# TEXT / LANG HELPERS
# -------------------------
def get_lang(value: Optional[str]) -> str:
    return value if value in ("en", "ru", "lv") else "lv"


def stt_locale_for_lang(lang: str) -> str:
    lang = get_lang(lang)
    if lang == "ru":
        return "ru-RU"
    if lang == "lv":
        return "lv-LV"
    return "en-US"


def tts_language_code_for_lang(lang: str) -> str:
    lang = get_lang(lang)
    if lang == "ru":
        return "ru-RU"
    if lang == "en":
        return "en-US"
    return "lv-LV"


def norm_user_key(phone: str) -> str:
    raw = (phone or "").strip().replace("whatsapp:", "")
    if not raw:
        return "unknown"
    phone_like = re.sub(r"[^\d+]", "", raw)
    digits = re.sub(r"\D", "", phone_like)
    if len(digits) >= 7:
        return phone_like or "unknown"
    safe = re.sub(r"[^a-zA-Z0-9_:\-]", "_", raw).strip("_")
    return safe or "unknown"


def normalize_voice_caller(raw_from: str) -> str:
    v = (raw_from or "").strip()
    if v.startswith("client:"):
        v = v[len("client:") :]
    return v


def _join_service_parts(values: Any) -> Optional[str]:
    if isinstance(values, dict):
        parts = [str(v).strip().strip("'\"") for v in values.values() if str(v).strip()]
        return ", ".join(parts) if parts else None
    if isinstance(values, (list, tuple, set)):
        parts = [str(v).strip().strip("'\"") for v in values if str(v).strip()]
        return ", ".join(parts) if parts else None
    return None


def normalize_service(value: Any) -> Optional[str]:
    if value is None:
        return None

    joined = _join_service_parts(value)
    if joined:
        return joined

    txt = str(value).strip()
    if not txt:
        return None

    if txt[0] in '[{(' and txt[-1] in ']})':
        try:
            parsed = ast.literal_eval(txt)
            joined = _join_service_parts(parsed)
            if joined:
                return joined
        except Exception:
            pass
        inner = txt[1:-1].strip()
        if inner:
            parts = [p.strip().strip("'\"") for p in inner.split(',') if p.strip()]
            if parts:
                return ", ".join(parts)

    return txt.strip("'\"") or None


def normalize_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        return str(value[0]).strip() if value else None
    if isinstance(value, dict):
        for k in ("name", "first_name", "full_name"):
            if value.get(k):
                return str(value[k]).strip()
        vals = [str(v).strip() for v in value.values() if str(v).strip()]
        return vals[0] if vals else None
    txt = str(value).strip()
    return txt or None


def parse_alias_mapping(value: Any) -> Dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {
            str(k).strip().lower(): str(v).strip()
            for k, v in value.items()
            if str(k).strip() and str(v).strip()
        }
    txt = str(value).strip()
    if not txt:
        return {}
    try:
        parsed = json.loads(txt)
        if isinstance(parsed, dict):
            return {
                str(k).strip().lower(): str(v).strip()
                for k, v in parsed.items()
                if str(k).strip() and str(v).strip()
            }
    except Exception:
        pass
    mapping: Dict[str, str] = {}
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        if "=>" in line:
            left, right = line.split("=>", 1)
        elif ":" in line:
            left, right = line.split(":", 1)
        else:
            continue
        left = left.strip().lower()
        right = right.strip()
        if left and right:
            mapping[left] = right
    return mapping


def tenant_service_aliases(tenant: Dict[str, Any], lang: str) -> Dict[str, str]:
    lang = get_lang(lang)
    candidates: List[Any] = []
    if lang == "lv":
        candidates.extend([tenant.get("service_aliases_lv"), tenant.get("aliases_lv")])
    elif lang == "ru":
        candidates.extend([tenant.get("service_aliases_ru"), tenant.get("aliases_ru")])
    elif lang == "en":
        candidates.extend([tenant.get("service_aliases_en"), tenant.get("aliases_en")])

    candidates.extend([
        tenant.get("service_aliases"),
        tenant.get("aliases"),
        os.getenv(f"BIZ_SERVICE_ALIASES_{lang.upper()}", "").strip(),
        os.getenv("BIZ_SERVICE_ALIASES", "").strip(),
    ])

    merged: Dict[str, str] = {}
    for candidate in candidates:
        merged.update(parse_alias_mapping(candidate))
    return merged


def apply_service_aliases(value: Optional[str], aliases: Dict[str, str]) -> Optional[str]:
    service = normalize_service(value)
    if not service:
        return None
    norm = service.strip().lower()
    if norm in aliases:
        return aliases[norm]
    for alias, canonical in aliases.items():
        if alias and alias in norm:
            return canonical
    return service


def tenant_business_memory(tenant: Dict[str, Any], lang: str) -> str:
    lang = get_lang(lang)
    parts: List[str] = []

    lang_keys = {
        "lv": ("business_memory_lv", "faq_lv", "booking_rules_lv"),
        "ru": ("business_memory_ru", "faq_ru", "booking_rules_ru"),
        "en": ("business_memory_en", "faq_en", "booking_rules_en"),
    }.get(lang, ())

    generic_keys = ("business_memory", "faq", "booking_rules", "policies")

    for key in list(lang_keys) + list(generic_keys):
        val = tenant.get(key)
        if val:
            txt = str(val).strip()
            if txt:
                parts.append(f"{key}: {txt}")

    env_memory = os.getenv(f"BIZ_BUSINESS_MEMORY_{lang.upper()}", "").strip() or os.getenv("BIZ_BUSINESS_MEMORY", "").strip()
    if env_memory:
        parts.append(f"env_memory: {env_memory}")

    return "\n".join(parts)


def default_business_memory_payload(business_type: str = "barbershop") -> Dict[str, str]:
    business_type = (business_type or "barbershop").strip().lower()
    if business_type == "clinic":
        return {
            "lv": "Biežākie jautājumi: konsultācija, atrašanās vieta, darba laiks. Atbildi mierīgi un profesionāli.",
            "ru": "Частые вопросы: консультация, адрес, часы работы. Отвечай спокойно и профессионально.",
            "en": "Common questions: consultation, location, opening hours. Answer calmly and professionally.",
        }
    if business_type == "salon":
        return {
            "lv": "Biežākie jautājumi: matu griezums, krāsošana, atrašanās vieta, darba laiks. Tonis — draudzīgs un pieklājīgs.",
            "ru": "Частые вопросы: стрижка, окрашивание, адрес, часы работы. Тон — дружелюбный и вежливый.",
            "en": "Common questions: haircut, coloring, location, opening hours. Tone should be friendly and polite.",
        }
    return {
        "lv": "Barberšopa piezīmes: galvenie pakalpojumi ir vīriešu frizūra un bārda. Ja klients jautā par pakalpojumiem, vari minēt populārākos variantus un piedāvāt pierakstu.",
        "ru": "Заметки барбершопа: основные услуги — мужская стрижка и борода. Если клиент спрашивает об услугах, можно назвать самые популярные варианты и предложить запись.",
        "en": "Barbershop notes: core services are men's haircut and beard trim. If the client asks about services, mention the most popular options and offer a booking.",
    }


def _line_candidates_from_memory(memory: str) -> List[str]:
    return [line.strip(" -•\t") for line in str(memory or "").splitlines() if line.strip()]


def _extract_price_from_line(line: str) -> Optional[str]:
    src = str(line or "")
    patterns = [
        r"(€\s*\d+(?:[\.,]\d{1,2})?)",
        r"(\d+(?:[\.,]\d{1,2})?\s*€)",
        r"(\d+(?:[\.,]\d{1,2})?\s*eur)",
    ]
    for pat in patterns:
        m = re.search(pat, src, flags=re.IGNORECASE)
        if m:
            return m.group(1).replace("eur", "EUR")
    return None


def _memory_line_for_service(memory: str, service_item: Optional[Dict[str, Any]]) -> Optional[str]:
    if not memory or not service_item:
        return None
    hay = " ".join([
        str(service_item.get("key") or ""),
        str(service_item.get("name_lv") or ""),
        str(service_item.get("name_ru") or ""),
        str(service_item.get("name_en") or ""),
        " ".join(service_item.get("aliases_lv") or []),
        " ".join(service_item.get("aliases_ru") or []),
        " ".join(service_item.get("aliases_en") or []),
    ]).lower()
    for line in _line_candidates_from_memory(memory):
        low = line.lower()
        if any(part and part in low for part in hay.split()):
            return line
    return None


def barber_service_options_text(lang: str, catalog: List[Dict[str, Any]], max_items: int = 3) -> str:
    lang = get_lang(lang)
    names = []
    for item in catalog[:max_items]:
        display = service_display_name(item, lang)
        if display:
            names.append(display)
    if not names:
        return ""
    if lang == "ru":
        return ", ".join(names[:-1]) + (" или " + names[-1] if len(names) > 1 else names[0])
    if lang == "en":
        return ", ".join(names[:-1]) + (" or " + names[-1] if len(names) > 1 else names[0])
    return ", ".join(names[:-1]) + (" vai " + names[-1] if len(names) > 1 else names[0])


def barber_service_prompt(lang: str, catalog: List[Dict[str, Any]]) -> str:
    options = barber_service_options_text(lang, catalog)
    if lang == "ru":
        return f"На какую услугу вас записать? Например: {options}." if options else "На какую услугу вас записать?"
    if lang == "en":
        return f"Which service would you like to book? For example: {options}." if options else "Which service would you like to book?"
    return f"Uz kādu pakalpojumu vēlaties pierakstīties? Piemēram: {options}." if options else "Uz kādu pakalpojumu vēlaties pierakstīties?"


def try_barbershop_faq(
    msg: str,
    lang: str,
    tenant: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    service_aliases: Dict[str, str],
    business_memory: str,
) -> Optional[Dict[str, Any]]:
    business_type = str(tenant.get("business_type") or "barbershop").strip().lower()
    if business_type != "barbershop":
        return None

    low = (msg or "").strip().lower()
    if not low:
        return None

    price_markers = ["цена", "сколько стоит", "price", "how much", "cena", "cik maksā", "cik maksa"]
    location_markers = ["where", "address", "адрес", "где вы", "где находитесь", "kur jūs", "adrese", "kur atrodaties"]
    services_markers = ["какие услуги", "что делаете", "services", "what services", "pakalpojumi", "ko jūs darāt", "ko jus darat"]
    duration_markers = ["сколько по времени", "сколько длится", "how long", "duration", "cik ilgi", "ilgums"]

    if any(x in low for x in location_markers):
        addr = str(settings.get("addr") or tenant.get("address") or "").strip()
        if not addr:
            return None
        if lang == "ru":
            text = f"Мы находимся по адресу: {addr}."
        elif lang == "en":
            text = f"We are located at: {addr}."
        else:
            text = f"Mēs atrodamies: {addr}."
        return {"status": "info", "reply_voice": text, "msg_out": text, "lang": lang}

    if any(x in low for x in services_markers):
        options = barber_service_options_text(lang, service_catalog, max_items=4)
        if lang == "ru":
            text = f"Обычно у нас доступны такие услуги: {options}. Если хотите, могу сразу помочь с записью."
        elif lang == "en":
            text = f"We usually offer services such as {options}. If you want, I can help you book right away."
        else:
            text = f"Parasti pie mums ir pieejami šādi pakalpojumi: {options}. Ja vēlaties, varu uzreiz palīdzēt ar pierakstu."
        return {"status": "info", "reply_voice": text, "msg_out": text, "lang": lang}

    if any(x in low for x in duration_markers):
        service_key = canonical_service_key_from_text(low, service_aliases)
        service_item = get_service_item_by_key(service_catalog, service_key) if service_key else extract_service_from_text(low, service_catalog, lang)
        if service_item:
            duration = service_duration_min(service_item)
            display = service_display_name(service_item, lang)
            if lang == "ru":
                text = f"{display} обычно занимает около {duration} минут."
            elif lang == "en":
                text = f"{display} usually takes about {duration} minutes."
            else:
                text = f"{display} parasti aizņem apmēram {duration} minūtes."
            return {"status": "info", "reply_voice": text, "msg_out": text, "lang": lang}

    if any(x in low for x in price_markers):
        service_key = canonical_service_key_from_text(low, service_aliases)
        service_item = get_service_item_by_key(service_catalog, service_key) if service_key else extract_service_from_text(low, service_catalog, lang)
        if service_item:
            line = _memory_line_for_service(business_memory, service_item)
            price = _extract_price_from_line(line or "")
            display = service_display_name(service_item, lang)
            if price:
                if lang == "ru":
                    text = f"{display} стоит {price}."
                elif lang == "en":
                    text = f"{display} costs {price}."
                else:
                    text = f"{display} maksā {price}."
            else:
                duration = service_duration_min(service_item)
                if lang == "ru":
                    text = f"По услуге {display} лучше уточнить цену у мастера. По времени это обычно около {duration} минут."
                elif lang == "en":
                    text = f"For {display}, it is best to confirm the price with the barber. It usually takes about {duration} minutes."
                else:
                    text = f"Par pakalpojumu {display} cenu vislabāk precizēt pie meistara. Parasti tas aizņem apmēram {duration} minūtes."
            return {"status": "info", "reply_voice": text, "msg_out": text, "lang": lang}

    return None


def faq_with_flow_followup(
    faq_result: Dict[str, Any],
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    active_flow: bool,
) -> Dict[str, Any]:
    result = dict(faq_result or {})
    if not active_flow:
        return result

    followup = prompt_for_state(lang, c, pending or {}, service_catalog)
    answer_text = str(result.get("msg_out") or result.get("reply_voice") or "").strip()
    if followup:
        combined = f"{answer_text}\n\n{followup}".strip() if answer_text else followup
    else:
        combined = answer_text

    result["status"] = "need_more"
    result["msg_out"] = combined
    result["reply_voice"] = combined
    result["lang"] = lang
    result["flow_preserved"] = True
    return result


LANG_HINTS = {
    "lv": {
        "strong": [
            "labdien", "sveiki", "lūdzu", "ludzu", "paldies", "pieraksts", "pierakstīties",
            "pierakstities", "frizētava", "frizetava", "barberšops", "bārda", "barda",
            "rīt", "rit", "parīt", "šodien", "sodien", "cikos", "pārcelt", "atcelt",
            "vai", "tas", "ir", "strādājat", "darba", "laiks"
        ],
        "weak": ["uz", "kad", "laiks", "diena", "meistars", "pakalpojums", "šodien", "rīt"],
    },
    "ru": {
        "strong": [
            "здравствуйте", "привет", "добрый", "запись", "записаться", "парикмахерская",
            "барбершоп", "стрижка", "борода", "завтра", "послезавтра", "сегодня",
            "перенести", "отменить", "время", "работаете", "это", "у вас", "можно"
        ],
        "weak": ["дата", "когда", "время", "мастер", "услуга", "запись", "сегодня", "завтра"],
    },
    "en": {
        "strong": [
            "hello", "hi", "appointment", "book", "booking", "cancel", "reschedule",
            "tomorrow", "today", "barbershop", "salon", "clinic", "open", "working",
            "hours", "service", "time", "name", "is this", "can i"
        ],
        "weak": ["when", "time", "date", "service", "today", "tomorrow"],
    },
}

GREETING_PATTERNS = {
    "lv": ["labdien", "sveiki", "čau", "cau", "halo", "alo"],
    "ru": ["здравствуйте", "добрый день", "добрый вечер", "привет", "алло", "але"],
    "en": ["hello", "hi", "good morning", "good afternoon", "hey"],
}

IDENTITY_CHECK_PATTERNS = [
    "vai tas ir", "vai jūs esat", "это ", "is this", "did i reach",
    "я туда попал", "это барбершоп", "это парикмахерская", "это клиника",
]

HOURS_PATTERNS = [
    "работаете", "во сколько", "часы работы", "открыты", "открыто",
    "strādājat", "darba laiks", "atvērts", "cikos strādājat",
    "open", "working hours", "what time are you open", "are you open",
]

BOOKING_OPENERS = [
    "можно записаться", "хочу записаться", "хотел записаться", "нужна запись",
    "gribu pierakstīties", "vēlos pierakstīties", "vai var pierakstīties",
    "i want to book", "i'd like to book", "can i book", "need an appointment",
]

def tokenize_lang_text(text_: str) -> List[str]:
    return re.findall(r"[A-Za-zĀ-žа-яА-ЯёЁ]+", (text_ or "").lower(), flags=re.UNICODE)

def detect_language_scores(text_: str) -> Dict[str, float]:
    raw = (text_ or "").strip()
    low = raw.lower()
    scores: Dict[str, float] = {"lv": 0.0, "ru": 0.0, "en": 0.0}
    if not low:
        scores["lv"] = 1.0
        return scores

    if re.search(r"[а-яё]", low, flags=re.IGNORECASE):
        scores["ru"] += 2.5
    if re.search(r"[āēīūčšžģķļņ]", low):
        scores["lv"] += 2.5
    latin_words = len(re.findall(r"[A-Za-z]+", low))
    if latin_words:
        scores["en"] += 0.2 * latin_words

    tokens = tokenize_lang_text(low)
    joined = " ".join(tokens)

    for lang_code, groups in LANG_HINTS.items():
        for tok in groups["strong"]:
            if tok in joined:
                scores[lang_code] += 2.0
        for tok in groups["weak"]:
            if tok in joined:
                scores[lang_code] += 0.7

    if any(ch in low for ch in ["ā", "ē", "ī", "ū", "č", "š", "ž", "ģ", "ķ", "ļ", "ņ"]):
        scores["lv"] += 1.2
    if re.search(r"[ёыэъ]", low):
        scores["ru"] += 1.0

    if any(x in low for x in ["hello", "appointment", "reschedule", "cancel", "book"]):
        scores["en"] += 2.5

    return scores

def detect_language(text_: str) -> str:
    scores = detect_language_scores(text_)
    lang, score = max(scores.items(), key=lambda x: x[1])
    return lang if score > 0 else "lv"

def resolve_reply_language(text_: str, current_lang: Optional[str]) -> str:
    current = get_lang(current_lang)
    scores = detect_language_scores(text_)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_lang, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    if top_score <= 0:
        return current
    if top_lang == current:
        return current

    margin = top_score - second_score
    if len(tokenize_lang_text(text_)) <= 2 and margin < 2.0:
        return current
    if margin >= 1.6:
        return top_lang
    if scores.get(current, 0.0) + 0.9 >= top_score:
        return current
    return top_lang

def is_greeting_only(text_: str) -> bool:
    low = (text_ or "").strip().lower()
    if not low:
        return False
    if len(tokenize_lang_text(low)) > 6:
        return False
    if any(p in low for p in IDENTITY_CHECK_PATTERNS + HOURS_PATTERNS + BOOKING_OPENERS):
        return False
    return any(any(g in low for g in patterns) for patterns in GREETING_PATTERNS.values())

def is_identity_check(text_: str) -> bool:
    low = (text_ or "").strip().lower()
    return any(p in low for p in IDENTITY_CHECK_PATTERNS)

def is_hours_question(text_: str) -> bool:
    low = (text_ or "").strip().lower()
    return any(p in low for p in HOURS_PATTERNS)

def is_booking_opener(text_: str) -> bool:
    low = (text_ or "").strip().lower()
    if not low:
        return False

    strong_phrases = [
        "gribu pierakstīties",
        "gribu pierakstities",
        "vēlos pierakstīties",
        "vēlos pierakstities",
        "velos pierakstities",
        "pierakstīties",
        "pierakstities",
        "pieraksts",
        "gribu rezervēt",
        "gribu rezervet",
        "vēlos rezervēt",
        "velos rezervet",
        "можно записаться",
        "хочу записаться",
        "нужна запись",
        "i want to book",
        "i'd like to book",
        "need an appointment",
    ]
    if any(p in low for p in strong_phrases):
        return True

    return any(p in low for p in BOOKING_OPENERS)

def detect_language_choice(text_: str, digits: str = "") -> Optional[str]:
    d = (digits or "").strip()
    if d == "1":
        return "lv"
    if d == "2":
        return "ru"
    if d == "3":
        return "en"
    t = (text_ or "").strip().lower()
    if not t:
        return None
    if any(x in t for x in ["latv", "latvie", "latvian", "vien", "one"]):
        return "lv"
    if any(x in t for x in ["рус", "kriev", "russian", "два", "two"]):
        return "ru"
    if any(x in t for x in ["english", "англ", "trīs", "tris", "three", "три"]):
        return "en"
    return detect_language(t)


def _short(s: Optional[str], n: int) -> str:
    return (s or "").strip()[:n]


def _parse_hhmm(hhmm: str) -> Tuple[int, int]:
    hh, mm = hhmm.split(":")
    return int(hh), int(mm)


def twiml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")


def format_dt_short(dt: Optional[datetime]) -> str:
    return dt.strftime("%d.%m %H:%M") if dt else ""


def ensure_lang_update(tenant_id: str, user_key: str, c: Dict[str, Any], lang: str) -> Dict[str, Any]:
    lang = get_lang(lang)
    if get_lang(c.get("lang")) != lang:
        c["lang"] = lang
        db_save_conversation(tenant_id, user_key, c)
    return c


# -------------------------
# DB: CONVERSATIONS
# -------------------------
def db_get_or_create_conversation(
    tenant_id: str, user_key: str, default_lang: str
) -> Dict[str, Any]:
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    user_key = norm_user_key(user_key)
    default_lang = get_lang(default_lang)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
            SELECT lang_lock, state, service, name, datetime_iso, time_text, pending_json
            FROM conversations
            WHERE tenant_id=:tid AND user_key=:uk
            LIMIT 1
        """
            ),
            {"tid": tenant_id, "uk": user_key},
        ).fetchone()
        if row:
            pending = None
            if row[6]:
                try:
                    pending = json.loads(row[6])
                except Exception:
                    pending = None
            return {
                "lang": get_lang(row[0]),
                "state": row[1] or "NEW",
                "service": row[2],
                "name": row[3],
                "datetime_iso": row[4],
                "time_text": row[5],
                "pending": pending,
            }
        conn.execute(
            text(
                """
            INSERT INTO conversations
              (tenant_id, user_key, lang_lock, state, updated_at)
            VALUES
              (:tid, :uk, :lang, 'NEW', NOW())
        """
            ),
            {"tid": tenant_id, "uk": user_key, "lang": default_lang},
        )
    return {
        "lang": default_lang,
        "state": "NEW",
        "service": None,
        "name": None,
        "datetime_iso": None,
        "time_text": None,
        "pending": None,
    }


def db_save_conversation(tenant_id: str, user_key: str, c: Dict[str, Any]) -> None:
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    user_key = norm_user_key(user_key)
    pending_json = (
        json.dumps(c["pending"], ensure_ascii=False) if c.get("pending") else None
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            UPDATE conversations
            SET lang_lock=:lang, state=:state, service=:service, name=:name,
                datetime_iso=:dtiso, time_text=:tt, pending_json=:pj, updated_at=NOW()
            WHERE tenant_id=:tid AND user_key=:uk
        """
            ),
            {
                "tid": tenant_id,
                "uk": user_key,
                "lang": get_lang(c.get("lang")),
                "state": c.get("state") or "NEW",
                "service": c.get("service"),
                "name": c.get("name"),
                "dtiso": c.get("datetime_iso"),
                "tt": sanitize_conversation_time_text(c.get("time_text")),
                "pj": pending_json,
            },
        )


# -------------------------
# DB: CALL LOGGING
# -------------------------
def ensure_call_logs_table() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS call_logs (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT,
                    channel TEXT,
                    intent TEXT,
                    service TEXT,
                    datetime_iso TEXT,
                    status TEXT,
                    raw_text TEXT,
                    ai_reply TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(text("ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS ai_reply TEXT"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_call_logs_tenant_created_at ON call_logs (tenant_id, created_at DESC)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_call_logs_user_id ON call_logs (user_id)"))


def ensure_phone_routes_table() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS phone_routes (
                    id BIGSERIAL PRIMARY KEY,
                    phone_number TEXT NOT NULL UNIQUE,
                    tenant_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_phone_routes_tenant_id ON phone_routes (tenant_id)"))

def infer_intent_label(raw_text: str, result_status: str, conv: Optional[Dict[str, Any]] = None) -> str:
    low = (raw_text or "").strip().lower()
    if any(w in low for w in ["atcelt", "отменить", "cancel"]):
        return "cancel"
    if any(w in low for w in ["pārcelt", "перенести", "reschedule"]):
        return "reschedule"
    if conv and is_active_booking_flow(conv):
        return "booking"
    if any(w in low for w in ["pierakst", "запис", "appointment", "book"]):
        return "booking"
    if result_status in ("booked", "busy", "booking_failed", "reschedule_wait", "no_booking"):
        return "booking"
    if result_status == "greeting":
        return "greeting"
    if result_status == "identity":
        return "identity"
    if result_status == "info":
        return "info"
    return "unknown"

def log_call_event(
    tenant_id: str,
    user_id: str,
    channel: str,
    raw_text: str,
    result: Dict[str, Any],
    conv: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        conv = conv or {}
        intent = infer_intent_label(raw_text, str(result.get("status") or "").strip(), conv)
        service = str(conv.get("service") or "").strip() or None
        datetime_iso = str(conv.get("datetime_iso") or "").strip() or None
        status = str(result.get("status") or "").strip() or "unknown"
        ai_reply = str(result.get("msg_out") or result.get("reply_voice") or "").strip() or None
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO call_logs
                    (tenant_id, user_id, channel, intent, service, datetime_iso, status, raw_text, ai_reply)
                    VALUES
                    (:tenant_id, :user_id, :channel, :intent, :service, :datetime_iso, :status, :raw_text, :ai_reply)
                    """
                ),
                {
                    "tenant_id": (tenant_id or "").strip() or TENANT_ID_DEFAULT,
                    "user_id": norm_user_key(user_id),
                    "channel": (channel or "").strip().lower() or "unknown",
                    "intent": intent,
                    "service": service,
                    "datetime_iso": datetime_iso,
                    "status": status,
                    "raw_text": (raw_text or "").strip(),
                    "ai_reply": ai_reply,
                },
            )
    except Exception as e:
        log.error("call_log_write_failed tenant_id=%s user_id=%s err=%s", tenant_id, user_id, e)

def handle_user_text_with_logging(
    tenant_id: str, raw_phone: str, text_in: str, channel: str, lang_hint: str
) -> Dict[str, Any]:
    result = handle_user_text(tenant_id, raw_phone, text_in, channel, lang_hint)
    try:
        conv = db_get_or_create_conversation(tenant_id, raw_phone, lang_hint or "lv")
    except Exception:
        conv = {}
    try:
        tenant = get_tenant(tenant_id)
        result = humanize_result(result, conv, tenant)
    except Exception as e:
        log.error("humanize_result_failed tenant_id=%s err=%s", tenant_id, e)
        tenant = {}
    log_call_event(
        tenant_id=tenant_id,
        user_id=raw_phone,
        channel=channel,
        raw_text=text_in,
        result=result,
        conv=conv,
    )
    try:
        tenant = tenant or get_tenant(tenant_id)
        send_booking_confirmation_if_needed(tenant, raw_phone, channel, result)
    except Exception as e:
        log.error("booking_confirmation_failed tenant_id=%s channel=%s err=%s", tenant_id, channel, e)
    return result




# -------------------------
# Phase 3 – Tenant Calendar Abstraction
# -------------------------
def resolve_tenant_calendar_id(tenant: Dict[str, Any]) -> Optional[str]:
    if tenant.get("google_connected"):
        return str(tenant.get("calendar_id") or "").strip() or None
    return str(tenant.get("calendar_id") or "").strip() or None

def get_tenant_calendar_context(tenant: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "calendar_id": resolve_tenant_calendar_id(tenant),
        "timezone": tenant.get("timezone", "Europe/Riga"),
    }


# -------------------------
# SaaS ACCESS CONTROL
# -------------------------
def tenant_allowed(tenant: Dict[str, Any]) -> Tuple[bool, str]:
    st = (
        tenant.get("status")
        or tenant.get("client_status")
        or CLIENT_STATUS_FALLBACK
        or "trial"
    ).lower()
    if st == "inactive":
        return False, "inactive"
    if st == "trial":
        te = tenant.get("trial_end") or tenant.get("trial_end_at")
        dt = parse_dt_any_tz(te) if isinstance(te, str) else te
        if not dt:
            dt = parse_dt_any_tz(TRIAL_END_ISO_FALLBACK)
        if dt and now_ts() > dt:
            return False, "trial_expired"
    return True, "ok"


def tenant_calendar_id(tenant: Dict[str, Any]) -> str:
    for key in ("calendar_id", "google_calendar_id", "calendarId"):
        if tenant.get(key):
            return str(tenant.get(key))
    return GOOGLE_CALENDAR_ID_FALLBACK or ""


def tenant_services_for_lang(tenant: Dict[str, Any], lang: str) -> str:
    lang = get_lang(lang)
    if lang == "lv" and tenant.get("services_lv"):
        return str(tenant.get("services_lv"))
    if lang == "ru" and tenant.get("services_ru"):
        return str(tenant.get("services_ru"))
    if lang == "en" and tenant.get("services_en"):
        return str(tenant.get("services_en"))
    if tenant.get("services"):
        return str(tenant.get("services"))
    return BUSINESS_FALLBACK[f"services_{lang}"]


def _safe_json_obj(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    txt = str(value).strip()
    if not txt:
        return None
    try:
        return json.loads(txt)
    except Exception:
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(value)
    except Exception:
        return default


def _normalize_weekday_key(value: str) -> Optional[str]:
    low = (value or "").strip().lower()
    mapping = {
        "mon": "mon", "monday": "mon", "1": "mon",
        "tue": "tue", "tues": "tue", "tuesday": "tue", "2": "tue",
        "wed": "wed", "wednesday": "wed", "3": "wed",
        "thu": "thu", "thur": "thu", "thurs": "thu", "thursday": "thu", "4": "thu",
        "fri": "fri", "friday": "fri", "5": "fri",
        "sat": "sat", "saturday": "sat", "6": "sat",
        "sun": "sun", "sunday": "sun", "0": "sun", "7": "sun",
    }
    return mapping.get(low)


def _weekday_key_for_date(dt_value: datetime) -> str:
    keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    return keys[dt_value.weekday()]


def default_weekly_hours(work_start: str, work_end: str) -> Dict[str, Optional[List[str]]]:
    return {k: [work_start, work_end] for k in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]}


def tenant_business_rules(tenant: Dict[str, Any], work_start: str, work_end: str) -> Dict[str, Any]:
    weekly_hours = default_weekly_hours(work_start, work_end)
    src_weekly = (
        tenant.get("weekly_hours_json")
        or tenant.get("business_hours_json")
        or tenant.get("working_hours_json")
        or BUSINESS_WEEKLY_HOURS_JSON
    )
    parsed_weekly = _safe_json_obj(src_weekly)
    if isinstance(parsed_weekly, dict):
        for raw_key, value in parsed_weekly.items():
            wk = _normalize_weekday_key(str(raw_key))
            if not wk:
                continue
            if value in (None, False, "closed", "off"):
                weekly_hours[wk] = None
            elif isinstance(value, (list, tuple)) and len(value) >= 2:
                weekly_hours[wk] = [str(value[0]).strip(), str(value[1]).strip()]
            elif isinstance(value, dict):
                start = str(value.get("start") or value.get("from") or "").strip()
                end = str(value.get("end") or value.get("to") or "").strip()
                if start and end:
                    weekly_hours[wk] = [start, end]

    days_off: set[str] = set()
    src_days_off = tenant.get("days_off") or tenant.get("days_off_json") or BUSINESS_DAYS_OFF
    parsed_days_off = _safe_json_obj(src_days_off)
    if isinstance(parsed_days_off, list):
        for item in parsed_days_off:
            wk = _normalize_weekday_key(str(item))
            if wk:
                days_off.add(wk)
    else:
        for part in str(src_days_off or "").split(","):
            wk = _normalize_weekday_key(part)
            if wk:
                days_off.add(wk)
    for wk in list(days_off):
        weekly_hours[wk] = None

    breaks_by_day = {k: [] for k in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]}
    src_breaks = tenant.get("breaks_json") or tenant.get("breaks") or BUSINESS_BREAKS_JSON
    parsed_breaks = _safe_json_obj(src_breaks)
    if isinstance(parsed_breaks, dict):
        for raw_key, value in parsed_breaks.items():
            wk = _normalize_weekday_key(str(raw_key))
            if not wk:
                continue
            vals = value if isinstance(value, list) else [value]
            for interval in vals:
                if isinstance(interval, (list, tuple)) and len(interval) >= 2:
                    breaks_by_day[wk].append([str(interval[0]).strip(), str(interval[1]).strip()])
                elif isinstance(interval, dict):
                    start = str(interval.get("start") or interval.get("from") or "").strip()
                    end = str(interval.get("end") or interval.get("to") or "").strip()
                    if start and end:
                        breaks_by_day[wk].append([start, end])
    elif isinstance(parsed_breaks, list):
        # global breaks applied to every day
        for wk in breaks_by_day:
            for interval in parsed_breaks:
                if isinstance(interval, (list, tuple)) and len(interval) >= 2:
                    breaks_by_day[wk].append([str(interval[0]).strip(), str(interval[1]).strip()])

    holidays: List[str] = []
    src_holidays = tenant.get("holidays_json") or tenant.get("holidays")
    parsed_holidays = _safe_json_obj(src_holidays)
    if isinstance(parsed_holidays, list):
        holidays = [str(x).strip() for x in parsed_holidays if str(x).strip()]
    elif isinstance(parsed_holidays, str) and parsed_holidays.strip():
        holidays = [parsed_holidays.strip()]

    min_notice_minutes = _safe_int(
        tenant.get("min_notice_minutes")
        or tenant.get("lead_time_min")
        or tenant.get("minimum_notice_minutes")
        or BUSINESS_MIN_NOTICE_MINUTES,
        0,
    )
    buffer_minutes = _safe_int(
        tenant.get("buffer_minutes")
        or tenant.get("booking_buffer_min")
        or tenant.get("service_buffer_minutes")
        or BUSINESS_BUFFER_MINUTES,
        0,
    )

    return {
        "weekly_hours": weekly_hours,
        "days_off": sorted(days_off),
        "breaks": breaks_by_day,
        "holidays": holidays,
        "min_notice_minutes": max(0, min_notice_minutes),
        "buffer_minutes": max(0, buffer_minutes),
    }


def tenant_settings(tenant: Dict[str, Any], lang: str) -> Dict[str, Any]:
    biz_name = str(
        tenant.get("business_name")
        or tenant.get("name")
        or BUSINESS_FALLBACK["business_name"]
    )
    addr = str(tenant.get("address") or BUSINESS_FALLBACK["address"])
    work_start = str(tenant.get("work_start") or WORK_START_HHMM_DEFAULT)
    work_end = str(tenant.get("work_end") or WORK_END_HHMM_DEFAULT)
    return {
        "biz_name": biz_name,
        "addr": addr,
        "services_hint": tenant_services_for_lang(tenant, lang),
        "work_start": work_start,
        "work_end": work_end,
        "calendar_id": resolve_tenant_calendar_id(tenant) or tenant_calendar_id(tenant),
        "service_account_json": tenant_service_account_json_value(tenant),
        "business_rules": tenant_business_rules(tenant, work_start, work_end),
        "business_type": str(tenant.get("business_type") or "barbershop").strip().lower(),
    }


def _slugify_service_key(value: str) -> str:
    low = (value or "").strip().lower()
    low = re.sub(r"[^a-z0-9а-яёāēīūčšžģķļņ]+", "_", low, flags=re.IGNORECASE)
    return low.strip("_") or f"service_{uuid.uuid4().hex[:6]}"


def _ensure_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(x).strip() for x in value if str(x).strip()]
    txt = str(value).strip()
    if not txt:
        return []
    try:
        parsed = json.loads(txt)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in txt.split(",") if x.strip()]


def parse_service_catalog(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    parsed = value
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return []
        try:
            parsed = json.loads(txt)
        except Exception:
            return []
    if not isinstance(parsed, list):
        return []

    out: List[Dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        base_name = str(item.get("name") or item.get("name_lv") or item.get("display_name") or item.get("key") or "").strip()
        if not base_name:
            continue
        key = str(item.get("key") or _slugify_service_key(base_name)).strip()
        try:
            duration_min = int(item.get("duration_min") or APPT_MINUTES)
        except Exception:
            duration_min = APPT_MINUTES
        aliases = _ensure_list(item.get("aliases"))
        aliases_lv = _ensure_list(item.get("aliases_lv"))
        aliases_ru = _ensure_list(item.get("aliases_ru"))
        aliases_en = _ensure_list(item.get("aliases_en"))
        if not aliases_lv and aliases:
            aliases_lv = aliases[:]
        if not aliases_ru and aliases:
            aliases_ru = aliases[:]
        if not aliases_en and aliases:
            aliases_en = aliases[:]
        out.append({
            "key": key,
            "name_lv": str(item.get("name_lv") or base_name).strip(),
            "name_ru": str(item.get("name_ru") or item.get("name") or base_name).strip(),
            "name_en": str(item.get("name_en") or item.get("name") or base_name).strip(),
            "duration_min": max(5, duration_min),
            "aliases_lv": aliases_lv,
            "aliases_ru": aliases_ru,
            "aliases_en": aliases_en,
        })
    return out


def fallback_service_catalog(tenant: Dict[str, Any]) -> List[Dict[str, Any]]:
    names: Dict[str, List[str]] = {
        "lv": [x.strip() for x in str(tenant.get("services_lv") or BUSINESS_FALLBACK["services_lv"]).split(",") if x.strip()],
        "ru": [x.strip() for x in str(tenant.get("services_ru") or BUSINESS_FALLBACK["services_ru"]).split(",") if x.strip()],
        "en": [x.strip() for x in str(tenant.get("services_en") or BUSINESS_FALLBACK["services_en"]).split(",") if x.strip()],
    }
    max_len = max(len(names["lv"]), len(names["ru"]), len(names["en"]), 1)
    catalog: List[Dict[str, Any]] = []
    for i in range(max_len):
        lv_name = names["lv"][i] if i < len(names["lv"]) else names["lv"][0]
        ru_name = names["ru"][i] if i < len(names["ru"]) else (names["ru"][0] if names["ru"] else lv_name)
        en_name = names["en"][i] if i < len(names["en"]) else (names["en"][0] if names["en"] else lv_name)
        catalog.append({
            "key": _slugify_service_key(lv_name),
            "name_lv": lv_name,
            "name_ru": ru_name,
            "name_en": en_name,
            "duration_min": APPT_MINUTES,
            "aliases_lv": [lv_name],
            "aliases_ru": [ru_name],
            "aliases_en": [en_name],
        })
    return catalog


def tenant_service_catalog(tenant: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("service_catalog", "services_catalog", "service_catalog_json", "services_json"):
        catalog = parse_service_catalog(tenant.get(key))
        if catalog:
            return catalog
    env_catalog = parse_service_catalog(os.getenv("BIZ_SERVICE_CATALOG", "").strip())
    if env_catalog:
        return env_catalog
    return fallback_service_catalog(tenant)


def get_service_item_by_key(catalog: List[Dict[str, Any]], service_key: Optional[str]) -> Optional[Dict[str, Any]]:
    sk = str(service_key or "").strip()
    if not sk:
        return None
    for item in catalog:
        if str(item.get("key") or "").strip() == sk:
            return item
    return None


def service_display_name(service_item: Optional[Dict[str, Any]], lang: str) -> str:
    if not service_item:
        return ""
    lang = get_lang(lang)
    return str(service_item.get(f"name_{lang}") or service_item.get("name_lv") or service_item.get("key") or "").strip()


def service_duration_min(service_item: Optional[Dict[str, Any]]) -> int:
    if not service_item:
        return APPT_MINUTES
    try:
        return max(5, int(service_item.get("duration_min") or APPT_MINUTES))
    except Exception:
        return APPT_MINUTES


def service_group_key(service_item: Optional[Dict[str, Any]]) -> str:
    if not service_item:
        return ""
    hay = " ".join([
        str(service_item.get("key") or ""),
        str(service_item.get("name_lv") or ""),
        str(service_item.get("name_ru") or ""),
        str(service_item.get("name_en") or ""),
        " ".join(service_item.get("aliases_lv") or []),
        " ".join(service_item.get("aliases_ru") or []),
        " ".join(service_item.get("aliases_en") or []),
    ]).lower()
    if any(x in hay for x in ["combo", "комбо", "kombo", "haircut and beard", "стрижка и борода", "frizūra un bārda", "matu griezums un bārda"]):
        return "combo"
    has_hair = any(x in hay for x in ["friz", "haircut", "стриж", "matu griez", "griezum"])
    has_beard = any(x in hay for x in ["bārd", "barda", "beard", "бород"])
    if has_hair and has_beard:
        return "combo"
    if has_beard:
        return "beard"
    if has_hair:
        return "haircut"
    return ""


def find_service_item_by_group(catalog: List[Dict[str, Any]], group: str) -> Optional[Dict[str, Any]]:
    for item in catalog:
        if service_group_key(item) == group:
            return item
    return None


def combined_service_display(lang: str, primary_item: Optional[Dict[str, Any]], addon_item: Optional[Dict[str, Any]]) -> str:
    primary = service_display_name(primary_item, lang)
    addon = service_display_name(addon_item, lang)
    if primary and addon:
        return f"{primary} + {addon}"
    return primary or addon or ""


def build_confirm_upsell_prompt(lang: str, when_text: str, haircut_item: Optional[Dict[str, Any]], beard_item: Optional[Dict[str, Any]]) -> str:
    haircut_name = service_display_name(haircut_item, lang)
    beard_name = service_display_name(beard_item, lang) or ("bārdu" if lang == "lv" else "бороду" if lang == "ru" else "a beard trim")
    if lang == "ru":
        return f"Отлично — можем записать вас на {haircut_name} {when_text}. Если хотите, можем добавить и {beard_name}. Добавляем?"
    if lang == "en":
        return f"Great — we can book your {haircut_name} for {when_text}. If you want, we can add {beard_name} too. Shall I add it?"
    return f"Lieliski — varam pierakstīt jūs uz {haircut_name} {when_text}. Ja vēlaties, varam pievienot arī {beard_name}. Vai pievienojam?"


def build_confirm_upsell_resolution(lang: str, when_text: str, added: bool, haircut_item: Optional[Dict[str, Any]], beard_item: Optional[Dict[str, Any]]) -> str:
    haircut_name = service_display_name(haircut_item, lang)
    beard_name = service_display_name(beard_item, lang) or ("bārdu" if lang == "lv" else "бороду" if lang == "ru" else "a beard trim")
    if added:
        if lang == "ru":
            return f"Отлично 👍 Добавляю {beard_name}. Тогда подтверждаем запись на {when_text}?"
        if lang == "en":
            return f"Great 👍 I’ll add {beard_name}. Shall I confirm the booking for {when_text}?"
        return f"Lieliski 👍 Pievienoju arī {beard_name}. Vai apstiprinām pierakstu uz {when_text}?"
    if lang == "ru":
        return f"Хорошо 👍 Оставляем {haircut_name}. Подтверждаем запись на {when_text}?"
    if lang == "en":
        return f"No problem 👍 We’ll keep {haircut_name}. Shall I confirm the booking for {when_text}?"
    return f"Labi 👍 Paliekam pie {haircut_name}. Vai apstiprinām pierakstu uz {when_text}?"


def service_catalog_summary(catalog: List[Dict[str, Any]], lang: str) -> str:
    parts = []
    for item in catalog:
        display = service_display_name(item, lang)
        dur = service_duration_min(item)
        if display:
            parts.append(f"{display} ({dur} min)")
    return ", ".join(parts)


def service_alias_map_from_catalog(catalog: List[Dict[str, Any]], lang: str) -> Dict[str, str]:
    lang = get_lang(lang)
    out: Dict[str, str] = {}
    for item in catalog:
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        display = service_display_name(item, lang)
        for alias in [display] + list(item.get(f"aliases_{lang}") or []):
            a = str(alias or "").strip().lower()
            if a:
                out[a] = key
    return out


def canonical_service_key_from_text(text_: Optional[str], alias_map: Dict[str, str]) -> Optional[str]:
    low = (text_ or "").strip().lower()
    if not low:
        return None
    if low in alias_map:
        return alias_map[low]
    # Prefer longest alias first so generic words don't beat specific phrases
    for alias in sorted(alias_map.keys(), key=len, reverse=True):
        if alias and alias in low:
            return alias_map[alias]
    return None


def merged_service_alias_map(catalog: List[Dict[str, Any]], tenant: Dict[str, Any], lang: str) -> Dict[str, str]:
    merged = service_alias_map_from_catalog(catalog, lang)
    merged.update(tenant_service_aliases(tenant, lang))
    return merged


def ensure_default_barbershop_aliases(catalog: List[Dict[str, Any]], alias_map: Dict[str, str], lang: str) -> Dict[str, str]:
    out = dict(alias_map)
    haircut_keys = []
    beard_keys = []
    combo_keys = []
    for item in catalog:
        key = str(item.get("key") or "").strip()
        hay = " ".join([
            key,
            str(item.get("name_lv") or ""),
            str(item.get("name_ru") or ""),
            str(item.get("name_en") or ""),
            " ".join(item.get("aliases_lv") or []),
            " ".join(item.get("aliases_ru") or []),
            " ".join(item.get("aliases_en") or []),
        ]).lower()
        if any(x in hay for x in ["friz", "haircut", "стриж", "matu griez", "griezum"]):
            haircut_keys.append(key)
        if any(x in hay for x in ["bārd", "barda", "beard", "бород"]):
            beard_keys.append(key)
        if any(x in hay for x in ["combo", "комбо", "kombo"]):
            combo_keys.append(key)

    def add_many(key: Optional[str], aliases: List[str]):
        if not key:
            return
        for a in aliases:
            aa = a.strip().lower()
            if aa and aa not in out:
                out[aa] = key

    haircut_key = haircut_keys[0] if haircut_keys else None
    beard_key = beard_keys[0] if beard_keys else None
    combo_key = combo_keys[0] if combo_keys else None

    add_many(haircut_key, [
        "matu griezums", "griezums", "apgriezt matus", "apgriezt", "frizūra", "frizura",
        "vīriešu frizūra", "viriesu frizura", "vīriešu matu griezums", "viriesu matu griezums",
        "подстричься", "стрижка", "мужская стрижка", "haircut", "mens haircut", "cut hair", "trim hair"
    ])
    add_many(beard_key, [
        "bārda", "barda", "bārdas korekcija", "bārdas trim", "beard trim", "beard", "борода", "подровнять бороду"
    ])
    add_many(combo_key, [
        "combo", "kombo", "комбо", "matu griezums un bārda", "frizūra un bārda", "haircut and beard", "стрижка и борода"
    ])
    return out


def calendar_is_configured(calendar_id: str) -> bool:
    return bool((calendar_id or "").strip())


def tenant_event_marker(tenant_id: str) -> str:
    return f"Tenant ID: {tenant_id}"


def build_event_description(tenant_id: str, client_name: str, raw_phone: str) -> str:
    return f"Name: {client_name}\nPhone: {raw_phone}\n{tenant_event_marker(tenant_id)}"


def event_belongs_to_tenant(ev: Dict[str, Any], tenant_id: str, phone: str) -> bool:
    desc = ev.get("description") or ""
    marker = tenant_event_marker(tenant_id)
    phone_norm = norm_user_key(phone)
    desc_norm = norm_user_key(desc)
    if marker in desc:
        return bool(phone_norm and phone_norm in desc_norm)
    return bool((phone_norm and phone_norm in desc_norm) or (phone and phone in desc))


def extract_name_from_event_description(description: str) -> Optional[str]:
    text_ = str(description or "")
    m = re.search(r"^Name:\s*(.+)$", text_, flags=re.IGNORECASE | re.MULTILINE)
    if m:
        return normalize_name(m.group(1))
    m = re.search(r"^Имя:\s*(.+)$", text_, flags=re.IGNORECASE | re.MULTILINE)
    if m:
        return normalize_name(m.group(1))
    return None

def abort_reschedule_text(text_: Optional[str], lang: str) -> bool:
    low = (text_ or "").strip().lower()
    if not low:
        return False
    abort_words = {
        "lv": {"nē", "ne", "nevajag", "atstāt", "atstat", "lai paliek", "nevajag pārcelt", "nevajag parcelt"},
        "ru": {"нет", "не надо", "оставить", "оставь", "пусть остается", "не переносить"},
        "en": {"no", "keep it", "leave it", "do not move", "dont move", "don't move"},
    }
    allowed = set().union(*abort_words.values())
    allowed.update(abort_words.get(get_lang(lang), set()))
    return low in allowed


def blocked_result_for_lang(lang: str) -> Dict[str, Any]:
    return {
        "status": "blocked",
        "reply_voice": t(lang, "service_unavailable_voice"),
        "msg_out": t(lang, "service_unavailable_text"),
        "lang": lang,
    }


# -------------------------
# TWILIO REQUEST VALIDATION
# -------------------------
from urllib.parse import parse_qs, urlencode

def twilio_request_validator() -> Optional[RequestValidator]:
    if not (TWILIO_VALIDATE_SIGNATURE and TWILIO_AUTH_TOKEN):
        return None
    try:
        return RequestValidator(TWILIO_AUTH_TOKEN)
    except Exception as e:
        log.error("Twilio validator init failed: %s", e)
        return None


def should_validate_twilio_request(path: str) -> bool:
    p = (path or "").lower()

    # browser / SDK endpoints must not require Twilio signature
    if p.startswith("/voice/token"):
        return False

    # real Twilio webhook endpoints
    if (
        p.startswith("/voice/incoming")
        or p.startswith("/voice/language")
        or p.startswith("/voice/intent")
        or p.startswith("/sms")
        or p.startswith("/whatsapp")
    ):
        return True

    return False


@app.middleware("http")
async def validate_twilio_signature_middleware(request: Request, call_next):
    if not should_validate_twilio_request(request.url.path):
        return await call_next(request)

    validator = twilio_request_validator()
    if validator is None:
        return await call_next(request)

    signature = request.headers.get("X-Twilio-Signature", "").strip()
    if not signature:
        log.warning("twilio_signature_missing path=%s", request.url.path)
        return Response(content="Invalid Twilio signature", status_code=403)

    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8", errors="ignore")
    parsed = parse_qs(body_text, keep_blank_values=True)
    form_data = {k: v[-1] if isinstance(v, list) and v else "" for k, v in parsed.items()}
    url = str(request.url)

    try:
        is_valid = validator.validate(url, form_data, signature)
    except Exception as e:
        log.error("twilio_signature_validation_error path=%s err=%s", request.url.path, e)
        return Response(content="Invalid Twilio signature", status_code=403)

    if not is_valid:
        log.warning("twilio_signature_invalid path=%s", request.url.path)
        return Response(content="Invalid Twilio signature", status_code=403)

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    request._receive = receive
    return await call_next(request)

# -------------------------
# TWILIO / OPENAI / GOOGLE
# -------------------------
def twilio_client():
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        return None
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_message(to_number: str, body: str):
    client = twilio_client()
    if not client:
        log.warning("Twilio client not configured; message skipped")
        return
    to_number = (to_number or "").strip()
    is_wa = to_number.startswith("whatsapp:")
    from_number = TWILIO_WHATSAPP_FROM if is_wa else TWILIO_FROM_NUMBER
    if not from_number:
        log.warning("Twilio from number missing; message skipped")
        return
    try:
        client.messages.create(from_=from_number, to=to_number, body=body)
    except Exception as e:
        log.error(f"Twilio send error: {e}")


def send_booking_confirmation_if_needed(tenant: Dict[str, Any], raw_user: str, channel: str, result: Dict[str, Any]) -> bool:
    if not BOOKING_CONFIRMATION_ENABLED:
        return False
    if str(result.get("status") or "").strip() != "booked":
        return False

    ch = (channel or "").strip().lower()
    if ch in ("dev", ""):
        return False
    if ch in ("sms", "whatsapp") and not AUTO_SEND_CONFIRMATION_FOR_TEXT_CHANNELS:
        return False

    to_number = (raw_user or "").strip()
    if ch == "voice":
        to_number = normalize_incoming_to_number(raw_user)
    if not channel_supports_messaging("sms", to_number):
        return False

    lang = get_lang(result.get("lang"))
    biz_name = tenant_settings(tenant, lang)["biz_name"]
    body = t(
        lang,
        "booking_confirmation_sms",
        service=(result.get("service") or result.get("service_display") or ""),
        when=(result.get("when") or result.get("datetime_text") or ""),
        biz=biz_name,
    )
    if not body.strip():
        body = f"{biz_name}: {result.get('msg_out') or result.get('reply_voice') or ''}".strip()
    try:
        send_message(to_number, body)
        log.info("booking_confirmation_sent channel=%s to=%s tenant_id=%s", ch, to_number, tenant.get("_id"))
        return True
    except Exception:
        return False


def channel_supports_messaging(channel: str, raw_phone: str) -> bool:
    channel = (channel or "").strip().lower()
    if channel in ("sms", "whatsapp"):
        return True
    phone = normalize_incoming_to_number(raw_phone)
    return bool(phone and looks_like_phone_number(phone))



def llm_understanding_enabled() -> bool:
    return bool(LLM_INTELLIGENCE_ENABLED and OPENAI_API_KEY)


def _normalize_llm_intent(value: Any) -> Optional[str]:
    low = str(value or "").strip().lower()
    if not low:
        return None
    mapping = {
        "book": "booking",
        "booking": "booking",
        "appointment": "booking",
        "new_booking": "booking",
        "reschedule": "reschedule",
        "move": "reschedule",
        "change_time": "reschedule",
        "cancel": "cancel",
        "cancellation": "cancel",
        "info": "info",
        "question": "info",
        "faq": "info",
        "other": "other",
        "unknown": "other",
    }
    return mapping.get(low, low if low in {"booking", "reschedule", "cancel", "info", "other"} else None)


def _normalize_llm_confirmation(value: Any) -> Optional[str]:
    low = str(value or "").strip().lower()
    if low in {"yes", "confirm", "confirmed", "true", "1"}:
        return "yes"
    if low in {"no", "decline", "false", "0"}:
        return "no"
    return None


def openai_understand_message(system: str, user: str) -> Dict[str, Any]:
    if not llm_understanding_enabled():
        return {}
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        if r.status_code == 200:
            return json.loads(r.json()["choices"][0]["message"]["content"])
        log.error("OpenAI understand error status=%s body=%s", r.status_code, r.text[:500])
    except Exception as e:
        log.error("OpenAI understand request failed: %s", e)
    return {}


def llm_message_understanding(
    msg: str,
    lang: str,
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    service_aliases: Dict[str, str],
    business_memory: str = "",
) -> Dict[str, Any]:
    if not llm_understanding_enabled() or not (msg or "").strip():
        return {
            "intent": None,
            "confidence": 0.0,
            "service": None,
            "time_text": None,
            "datetime_iso": None,
            "name": None,
            "confirmation": None,
        }

    alias_hint = ", ".join([f"{k} => {v}" for k, v in list(service_aliases.items())[:80]])
    sys_pt = (
        f"You classify messages for an appointment receptionist of {settings['biz_name']}. "
        f"Business hours: {settings['work_start']}-{settings['work_end']}. "
        f"Known services: {service_catalog_summary(service_catalog, lang)}. "
        f"Alias map to canonical service keys: {alias_hint or 'none'}. "
        f"Business memory: {business_memory or 'none'}. "
        "Return strict JSON only with keys: intent, confidence, service, time_text, datetime_iso, name, confirmation. "
        "intent must be one of: booking, reschedule, cancel, info, other. "
        "confidence must be a number between 0 and 1. "
        "service must be the canonical service key if recognized, otherwise null. "
        "confirmation must be yes, no, or null. "
        "datetime_iso should only be set if the user clearly provided a date/time. "
        "Do not invent missing values."
    )
    usr_pt = f"Today: {now_ts().date()}. User language: {lang}. User message: {msg}"
    raw = openai_understand_message(sys_pt, usr_pt)
    confidence = 0.0
    try:
        confidence = float(raw.get("confidence") or 0.0)
    except Exception:
        confidence = 0.0

    understood = {
        "intent": _normalize_llm_intent(raw.get("intent")),
        "confidence": max(0.0, min(1.0, confidence)),
        "service": apply_service_aliases(raw.get("service"), service_aliases) or canonical_service_key_from_text(raw.get("service"), service_aliases),
        "time_text": normalize_service(raw.get("time_text")),
        "datetime_iso": str(raw.get("datetime_iso") or "").strip() or None,
        "name": normalize_name(raw.get("name")),
        "confirmation": _normalize_llm_confirmation(raw.get("confirmation")),
    }
    return understood


def openai_chat_json(system: str, user: str) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        return {"service": None, "time_text": None, "datetime_iso": None, "name": None}
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        if r.status_code == 200:
            return json.loads(r.json()["choices"][0]["message"]["content"])
        log.error("OpenAI error status=%s body=%s", r.status_code, r.text[:500])
    except Exception as e:
        log.error("OpenAI request failed: %s", e)
    return {}


_GCAL = None
_GCAL_BY_KEY: Dict[str, Any] = {}


def get_gcal(service_account_json: Optional[str] = None):
    global _GCAL, _GCAL_BY_KEY
    effective_json = (service_account_json or GOOGLE_SERVICE_ACCOUNT_JSON or "").strip()
    if not effective_json:
        return None
    if effective_json == (GOOGLE_SERVICE_ACCOUNT_JSON or "").strip() and _GCAL is not None:
        return _GCAL
    if effective_json in _GCAL_BY_KEY:
        return _GCAL_BY_KEY[effective_json]
    try:
        info = json.loads(effective_json)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/calendar"]
        )
        svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        _GCAL_BY_KEY[effective_json] = svc
        if effective_json == (GOOGLE_SERVICE_ACCOUNT_JSON or "").strip():
            _GCAL = svc
        return svc
    except Exception as e:
        log.error("Google Calendar init failed: %s", e)
        return None


def is_slot_busy(calendar_id: str, dt_start: datetime, dt_end: datetime, buffer_minutes: int = 0, service_account_json: Optional[str] = None) -> bool:
    svc = get_gcal(service_account_json)
    if not svc or not calendar_id:
        return False
    window_start = dt_start - timedelta(minutes=max(0, int(buffer_minutes or 0)))
    window_end = dt_end + timedelta(minutes=max(0, int(buffer_minutes or 0)))
    body = {
        "timeMin": window_start.isoformat(),
        "timeMax": window_end.isoformat(),
        "items": [{"id": calendar_id}],
    }
    try:
        fb = svc.freebusy().query(body=body).execute()
        return len(fb["calendars"][calendar_id].get("busy", [])) > 0
    except Exception as e:
        log.error("Calendar freebusy failed: %s", e)
        return False
    body = {
        "timeMin": dt_start.isoformat(),
        "timeMax": dt_end.isoformat(),
        "items": [{"id": calendar_id}],
    }
    try:
        fb = svc.freebusy().query(body=body).execute()
        return len(fb["calendars"][calendar_id].get("busy", [])) > 0
    except Exception as e:
        log.error("Calendar freebusy failed: %s", e)
        return False


def create_calendar_event(
    calendar_id: str,
    dt_start: datetime,
    duration_min: int,
    summary: str,
    description: str,
    service_account_json: Optional[str] = None,
):
    svc = get_gcal(service_account_json)
    if not svc or not calendar_id:
        return None
    dt_end = dt_start + timedelta(minutes=duration_min)
    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": dt_start.isoformat(), "timeZone": "Europe/Riga"},
        "end": {"dateTime": dt_end.isoformat(), "timeZone": "Europe/Riga"},
    }
    try:
        return (
            svc.events()
            .insert(calendarId=calendar_id, body=event)
            .execute()
            .get("htmlLink")
        )
    except Exception as e:
        log.error("Create calendar event failed: %s", e)
        return None

def update_calendar_event(
    calendar_id: str,
    event_id: str,
    dt_start: datetime,
    duration_min: int,
    summary: str,
    description: str,
    service_account_json: Optional[str] = None,
):
    svc = get_gcal(service_account_json)
    if not svc or not calendar_id or not event_id:
        return None
    dt_end = dt_start + timedelta(minutes=duration_min)
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": dt_start.isoformat(), "timeZone": "Europe/Riga"},
        "end": {"dateTime": dt_end.isoformat(), "timeZone": "Europe/Riga"},
    }
    try:
        return (
            svc.events()
            .patch(calendarId=calendar_id, eventId=event_id, body=body)
            .execute()
            .get("htmlLink")
        )
    except Exception as e:
        log.error("Update calendar event failed: %s", e)
        return None


# -------------------------
# TTS / VOICE OUTPUT
# -------------------------
_TTS = None


def get_google_tts():
    global _TTS
    if _TTS:
        return _TTS
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        return None
    try:
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        _TTS = build("texttospeech", "v1", credentials=creds, cache_discovery=False)
        return _TTS
    except Exception as e:
        log.error("Google TTS init failed: %s", e)
        return None


def google_tts_mp3(text_: str, lang_code: str, voice_name: str) -> bytes:
    svc = get_google_tts()
    if not svc or not text_:
        return b""
    body = {
        "input": {"text": text_[:350]},
        "voice": {"languageCode": lang_code, "name": voice_name},
        "audioConfig": {"audioEncoding": "MP3"},
    }
    last_err = None
    for attempt in range(2):
        try:
            resp = svc.text().synthesize(body=body).execute()
            return base64.b64decode(resp["audioContent"])
        except Exception as e:
            last_err = e
            log.error("Google TTS failed attempt=%s err=%s", attempt + 1, e)
    if last_err is not None:
        log.error("Google TTS failed окончательно: %s", last_err)
    return b""


def elevenlabs_tts_mp3(text_: str, voice_id: str) -> bytes:
    if not (ELEVENLABS_API_KEY and voice_id and text_):
        return b""
    try:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text_[:500],
                "model_id": ELEVENLABS_MODEL_ID,
                "voice_settings": {
                    "stability": 0.45,
                    "similarity_boost": 0.75,
                },
            },
            timeout=30,
        )
        if r.status_code == 200:
            return r.content
        log.error("ElevenLabs TTS failed status=%s body=%s", r.status_code, r.text[:500])
    except Exception as e:
        log.error("ElevenLabs TTS request failed: %s", e)
    return b""


def tts_bytes_for_lang(text_: str, lang: str) -> bytes:
    lang = get_lang(lang)
    if lang == "lv":
        return google_tts_mp3(
            text_,
            tts_language_code_for_lang(lang),
            GOOGLE_TTS_VOICE_NAME,
        )
    return elevenlabs_tts_mp3(text_, ELEVENLABS_VOICE_ID)

def say_or_play(vr: VoiceResponse, text_: str, lang: str) -> None:
    text_ = (text_ or "").strip()
    if not text_:
        return
    lang = get_lang(lang)
    if SERVER_BASE_URL:
        try:
            encoded = requests.utils.quote(text_)
            vr.play(f"{SERVER_BASE_URL}/tts?lang={lang}&text={encoded}")
            return
        except Exception:
            pass
    vr.say(text_, language=stt_locale_for_lang(lang), voice="alice")


@app.get("/tts")
def tts_endpoint(text: str, lang: str = "lv"):
    audio = tts_bytes_for_lang(text, lang)
    if not audio:
        raise HTTPException(status_code=500, detail="TTS unavailable")
    return StreamingResponse(iter([audio]), media_type="audio/mpeg")


def gather_followup_prompt(result: Dict[str, Any]) -> str:
    status = str(result.get("status") or "").strip()
    reply = str(result.get("reply_voice") or "").strip()
    if status in ("need_more", "reschedule_wait", "greeting", "identity", "info") and reply:
        return reply
    return t(get_lang(result.get("lang")), "how_help")


# -------------------------
# CALENDAR LOGIC (Business Hours & Slots)
# -------------------------
def _interval_overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and end_a > start_b


def in_business_hours(
    dt_start: datetime, duration_min: int, work_start: str, work_end: str, business_rules: Optional[Dict[str, Any]] = None
) -> bool:
    try:
        rule_hours = None
        rule_breaks: List[List[str]] = []
        if business_rules:
            weekday_key = _weekday_key_for_date(dt_start)
            rule_hours = (business_rules.get("weekly_hours") or {}).get(weekday_key)
            rule_breaks = (business_rules.get("breaks") or {}).get(weekday_key) or []
        if is_holiday_for_rules(dt_start, business_rules):
            return False
        if violates_min_notice(dt_start, business_rules):
            return False
        if rule_hours is None and business_rules:
            return False

        start_hhmm, end_hhmm = (rule_hours or [work_start, work_end])[:2]
        ws_h, ws_m = _parse_hhmm(start_hhmm)
        we_h, we_m = _parse_hhmm(end_hhmm)
        day_start = dt_start.replace(hour=ws_h, minute=ws_m, second=0, microsecond=0)
        day_end = dt_start.replace(hour=we_h, minute=we_m, second=0, microsecond=0)
        dt_end = dt_start + timedelta(minutes=duration_min)
        if not (dt_start >= day_start and dt_end <= day_end):
            return False

        for br_start, br_end in rule_breaks:
            bs_h, bs_m = _parse_hhmm(br_start)
            be_h, be_m = _parse_hhmm(br_end)
            break_start = dt_start.replace(hour=bs_h, minute=bs_m, second=0, microsecond=0)
            break_end = dt_start.replace(hour=be_h, minute=be_m, second=0, microsecond=0)
            if _interval_overlaps(dt_start, dt_end, break_start, break_end):
                return False
        return True
    except Exception:
        return False


def find_next_two_slots(
    calendar_id: str,
    dt_start: datetime,
    duration_min: int,
    work_start: str,
    work_end: str,
    business_rules: Optional[Dict[str, Any]] = None,
    service_account_json: Optional[str] = None,
):
    step, found = 30, []
    candidate = dt_start + timedelta(minutes=step)
    for _ in range(96):
        if in_business_hours(candidate, duration_min, work_start, work_end, business_rules):
            if not is_slot_busy(
                calendar_id, candidate, candidate + timedelta(minutes=duration_min),
                _safe_int((business_rules or {}).get("buffer_minutes"), 0),
                service_account_json=service_account_json
            ):
                found.append(candidate)
                if len(found) == 2:
                    return found[0], found[1]
        candidate += timedelta(minutes=step)
    return None


def find_first_two_slots_for_day(
    calendar_id: str,
    day_dt: datetime,
    duration_min: int,
    work_start: str,
    work_end: str,
    business_rules: Optional[Dict[str, Any]] = None,
    service_account_json: Optional[str] = None,
):
    try:
        weekday_key = _weekday_key_for_date(day_dt)
        if business_rules and is_holiday_for_rules(day_dt, business_rules):
            return None
        if business_rules:
            rule_hours = (business_rules.get("weekly_hours") or {}).get(weekday_key)
            if not rule_hours:
                return None
            start_hhmm, end_hhmm = rule_hours[:2]
        else:
            start_hhmm, end_hhmm = work_start, work_end
        ws_h, ws_m = _parse_hhmm(start_hhmm)
        we_h, we_m = _parse_hhmm(end_hhmm)
    except Exception:
        return None

    candidate = day_dt.replace(hour=ws_h, minute=ws_m, second=0, microsecond=0)
    day_end = day_dt.replace(hour=we_h, minute=we_m, second=0, microsecond=0)
    found = []
    step = timedelta(minutes=30)

    while candidate + timedelta(minutes=duration_min) <= day_end:
        if in_business_hours(candidate, duration_min, work_start, work_end, business_rules) and not is_slot_busy(calendar_id, candidate, candidate + timedelta(minutes=duration_min), _safe_int((business_rules or {}).get("buffer_minutes"), 0), service_account_json=service_account_json):
            found.append(candidate)
            if len(found) == 2:
                return found[0], found[1]
        candidate += step
    return None


def find_first_n_slots_for_day(
    calendar_id: str,
    day_dt: datetime,
    duration_min: int,
    work_start: str,
    work_end: str,
    limit: int = 3,
    business_rules: Optional[Dict[str, Any]] = None,
    service_account_json: Optional[str] = None,
):
    try:
        weekday_key = _weekday_key_for_date(day_dt)
        if business_rules and is_holiday_for_rules(day_dt, business_rules):
            return []
        if business_rules:
            rule_hours = (business_rules.get("weekly_hours") or {}).get(weekday_key)
            if not rule_hours:
                return []
            start_hhmm, end_hhmm = rule_hours[:2]
        else:
            start_hhmm, end_hhmm = work_start, work_end
        ws_h, ws_m = _parse_hhmm(start_hhmm)
        we_h, we_m = _parse_hhmm(end_hhmm)
    except Exception:
        return []

    candidate = day_dt.replace(hour=ws_h, minute=ws_m, second=0, microsecond=0)
    day_end = day_dt.replace(hour=we_h, minute=we_m, second=0, microsecond=0)
    found: List[datetime] = []
    step = timedelta(minutes=30)

    while candidate + timedelta(minutes=duration_min) <= day_end:
        if in_business_hours(candidate, duration_min, work_start, work_end, business_rules) and not is_slot_busy(calendar_id, candidate, candidate + timedelta(minutes=duration_min), _safe_int((business_rules or {}).get("buffer_minutes"), 0), service_account_json=service_account_json):
            found.append(candidate)
            if len(found) >= max(1, limit):
                return found
        candidate += step
    return found




def find_first_n_slots_for_day_window(
    calendar_id: str,
    day_dt: datetime,
    duration_min: int,
    work_start: str,
    work_end: str,
    window_start_hour: int,
    window_end_hour: int,
    limit: int = 3,
    business_rules: Optional[Dict[str, Any]] = None,
    service_account_json: Optional[str] = None,
):
    slots = find_first_n_slots_for_day(
        calendar_id=calendar_id,
        day_dt=day_dt,
        duration_min=duration_min,
        work_start=work_start,
        work_end=work_end,
        limit=max(limit * 6, limit),
        business_rules=business_rules,
        service_account_json=service_account_json,
    )
    filtered: List[datetime] = []
    for slot in slots:
        if window_start_hour <= slot.hour < window_end_hour:
            filtered.append(slot)
            if len(filtered) >= max(1, limit):
                return filtered
    return filtered

def find_next_event_by_phone(calendar_id: str, phone: str, tenant_id: Optional[str] = None, service_account_json: Optional[str] = None):
    svc = get_gcal(service_account_json)
    if not svc or not calendar_id:
        return None
    now = now_ts().isoformat()
    try:
        events = (
            svc.events()
            .list(
                calendarId=calendar_id,
                timeMin=now,
                singleEvents=True,
                orderBy="startTime",
                maxResults=20,
            )
            .execute()
        )
        for ev in events.get("items", []):
            if tenant_id:
                if event_belongs_to_tenant(ev, tenant_id, phone):
                    return ev
            else:
                desc = ev.get("description") or ""
                phone_norm = norm_user_key(phone)
                if phone_norm and phone_norm in norm_user_key(desc):
                    return ev
                if phone in desc:
                    return ev
    except Exception as e:
        log.error("Find next event failed: %s", e)
    return None


def delete_calendar_event(calendar_id: str, event_id: str, service_account_json: Optional[str] = None):
    svc = get_gcal(service_account_json)
    if svc and calendar_id:
        try:
            svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            log.info(
                "Deleted calendar event: calendar_id=%s, event_id=%s",
                calendar_id,
                event_id,
            )
            return True
        except Exception as e:
            log.error(
                "Delete calendar event failed: calendar_id=%s, event_id=%s, err=%s",
                calendar_id,
                event_id,
                e,
            )
            return False
    return False


# -------------------------
# DATE PARSING Fallbacks
# -------------------------
def _phrase_in_text(src: str, phrase: str) -> bool:
    src = (src or "").lower().strip()
    phrase = (phrase or "").lower().strip()
    if not src or not phrase:
        return False
    pattern = r"(?<![\wĀ-žА-Яа-яЁё])" + re.escape(phrase) + r"(?![\wĀ-žА-Яа-яЁё])"
    return re.search(pattern, src, flags=re.IGNORECASE | re.UNICODE) is not None


def _contains_any_phrase(src: str, phrases: List[str]) -> bool:
    return any(_phrase_in_text(src, p) for p in (phrases or []))


def parse_time_text_to_dt(text_: str) -> Optional[datetime]:
    src = (text_ or "")
    m = re.search(r"\b([01]?\d|2[0-3])[:. ]([0-5]\d)\b", src.lower())
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    base = today_local()
    t_low = src.lower()

    if _contains_any_phrase(t_low, ["parīt", "послезавтра", "day after tomorrow"]):
        base += timedelta(days=2)
    elif _contains_any_phrase(t_low, ["rīt", "rit", "завтра", "tomorrow"]):
        base += timedelta(days=1)

    dm = re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", src)
    if dm:
        dd, mo = int(dm.group(1)), int(dm.group(2))
        yy = dm.group(3)
        year = int(yy) + 2000 if yy and len(yy) == 2 else int(yy) if yy else base.year
        try:
            return datetime(year, mo, dd, hh, mm, tzinfo=TZ)
        except Exception:
            pass

    return datetime(base.year, base.month, base.day, hh, mm, tzinfo=TZ)


def parse_dt_from_iso_or_fallback(
    datetime_iso: Optional[str], time_text: Optional[str], raw_text: Optional[str]
) -> Optional[datetime]:
    dt = parse_dt_any_tz((datetime_iso or "").strip())
    return dt if dt else parse_time_text_to_dt(f"{time_text or ''} {raw_text or ''}")


def parse_explicit_time_parts(text_: Optional[str]) -> Optional[Tuple[int, int]]:
    src = (text_ or "").lower().strip()
    if not src:
        return None

    # 14:30 / 14.30 / 14 30
    m = re.search(r"\b([01]?\d|2[0-3])[:. ]([0-5]\d)\b", src)
    if m:
        return int(m.group(1)), int(m.group(2))

    # 2pm / 2 pm / 2:30pm / 2.30 pm
    m = re.search(r"\b(1[0-2]|0?[1-9])(?:[:. ]([0-5]\d))?\s*(am|pm)\b", src)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm == "pm" and hh != 12:
            hh += 12
        if ampm == "am" and hh == 12:
            hh = 0
        return hh, mm

    # plain hour like 14
    if re.fullmatch(r"([01]?\d|2[0-3])", src):
        return int(src), 0
    return None


def has_explicit_time(text_: Optional[str]) -> bool:
    return parse_explicit_time_parts(text_) is not None


def has_date_reference(text_: Optional[str]) -> bool:
    src = (text_ or "").lower().strip()
    if not src:
        return False
    if re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", src):
        return True
    keywords = [
        "rīt", "rit", "parīt", "šodien", "sodien", "šorīt", "sorit", "šovakar", "sovakar",
        "завтра", "послезавтра", "сегодня", "сегодня утром", "сегодня днем", "сегодня днём", "сегодня вечером",
        "tomorrow", "day after tomorrow", "today", "this morning", "this afternoon", "this evening", "tonight",
        "next monday", "next tuesday", "next wednesday", "next thursday", "next friday", "next saturday", "next sunday",
    ]
    if _contains_any_phrase(src, keywords):
        return True
    for hints in WEEKDAY_HINTS.values():
        if _contains_any_phrase(src, hints):
            return True
    return False


def combine_date_with_explicit_time(base_iso: Optional[str], time_source: Optional[str]) -> Optional[datetime]:
    base_dt = parse_dt_any_tz((base_iso or "").strip())
    parts = parse_explicit_time_parts(time_source)
    if not base_dt or not parts:
        return None
    hh, mm = parts
    return base_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)


# -------------------------
# CONVERSATION STATE HELPERS
# -------------------------
STATE_NEW = "NEW"
STATE_AWAITING_SERVICE = "AWAITING_SERVICE"
STATE_AWAITING_DATE = "AWAITING_DATE"
STATE_AWAITING_TIME = "AWAITING_TIME"
STATE_AWAITING_CONFIRM = "AWAITING_CONFIRM"
STATE_POST_BOOKING_UPSELL = "POST_BOOKING_UPSELL"
STATE_BOOKED = "BOOKED"
STATE_CANCELLED = "CANCELLED"

ACTIVE_BOOKING_STATES = {
    STATE_AWAITING_SERVICE,
    STATE_AWAITING_DATE,
    STATE_AWAITING_TIME,
    STATE_AWAITING_CONFIRM,
}

WEEKDAY_HINTS = {
    0: ["monday", "mondays", "monday's", "next monday", "понедельник", "понедельника", "в понедельник", "на понедельник", "pirmdien", "pirmdiena", "pirmdienas", "uz pirmdienu", "pirmdien vakarā", "pirmdienas vakarā", "pirmdien vakara", "pirmdienas vakara", "pirmdienu"],
    1: ["tuesday", "tuesdays", "tuesday's", "next tuesday", "вторник", "вторника", "во вторник", "на вторник", "otrdien", "otrdiena", "otrdienas", "uz otrdienu", "otrdien vakarā", "otrdienas vakarā", "otrdien vakara", "otrdienas vakara", "otrdienu"],
    2: ["wednesday", "wednesdays", "wednesday's", "next wednesday", "среда", "среду", "среды", "в среду", "на среду", "trešdien", "tresdien", "trešdiena", "tresdiena", "trešdienas", "tresdienas", "uz trešdienu", "uz tresdienu", "trešdien vakarā", "tresdien vakarā", "trešdienas vakarā", "tresdienas vakarā", "trešdien vakara", "tresdien vakara", "trešdienu", "tresdienu"],
    3: ["thursday", "thursdays", "thursday's", "next thursday", "четверг", "четверга", "в четверг", "на четверг", "ceturtdien", "ceturtdiena", "ceturtdienas", "uz ceturtdienu", "ceturtdien vakarā", "ceturtdienas vakarā", "ceturtdien vakara", "ceturtdienu"],
    4: ["friday", "fridays", "friday's", "next friday", "пятница", "пятницу", "пятницы", "в пятницу", "на пятницу", "piektdien", "piektdiena", "piektdienas", "uz piektdienu", "piektdien vakarā", "piektdienas vakarā", "piektdien vakara", "piektdienu"],
    5: ["saturday", "saturdays", "saturday's", "next saturday", "суббота", "субботу", "субботы", "в субботу", "на субботу", "sestdien", "sestdiena", "sestdienas", "uz sestdienu", "sestdien vakarā", "sestdienas vakarā", "sestdien vakara", "sestdienu"],
    6: ["sunday", "sundays", "sunday's", "next sunday", "воскресенье", "воскресенья", "в воскресенье", "на воскресенье", "svētdien", "svetdien", "svētdiena", "svetdiena", "svētdienas", "svetdienas", "uz svētdienu", "uz svetdienu", "svētdien vakarā", "svetdien vakarā", "svētdienas vakarā", "svetdienas vakarā", "svētdien vakara", "svetdien vakara", "svētdienu", "svetdienu"],
}

YES_WORDS = {
    "lv": {"jā", "ja", "jaa", "labi", "der", "ok", "okej", "apstiprinu"},
    "ru": {"да", "ага", "ок", "хорошо", "подтверждаю"},
    "en": {"yes", "yeah", "yep", "ok", "okay", "confirm"},
}

NO_WORDS = {
    "lv": {"nē", "ne", "nee"},
    "ru": {"нет", "неа"},
    "en": {"no", "nope"},
}

def conversation_state(c: Dict[str, Any]) -> str:
    state = str(c.get("state") or STATE_NEW).strip().upper()
    if state not in {STATE_NEW, STATE_AWAITING_SERVICE, STATE_AWAITING_DATE, STATE_AWAITING_TIME, STATE_AWAITING_CONFIRM, STATE_POST_BOOKING_UPSELL, STATE_BOOKED, STATE_CANCELLED}:
        return STATE_NEW
    return state


def is_active_booking_flow(c: Dict[str, Any]) -> bool:
    pending = c.get("pending") or {}
    return conversation_state(c) in ACTIVE_BOOKING_STATES or bool(pending.get("booking_intent"))


def get_offered_slots(pending: Dict[str, Any]) -> List[str]:
    slots = pending.get("offered_slots")
    if isinstance(slots, list):
        return [str(x).strip() for x in slots if str(x).strip()]
    out: List[str] = []
    for key in ("opt1_iso", "opt2_iso"):
        val = str(pending.get(key) or "").strip()
        if val:
            out.append(val)
    return out


def set_offered_slots(pending: Dict[str, Any], slots: List[datetime]) -> Dict[str, Any]:
    offered = [dt.isoformat() for dt in slots if dt]
    pending["offered_slots"] = offered
    pending["opt1_iso"] = offered[0] if len(offered) > 0 else None
    pending["opt2_iso"] = offered[1] if len(offered) > 1 else None
    return pending


def clear_offered_slots(pending: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("offered_slots", "opt1_iso", "opt2_iso"):
        pending.pop(key, None)
    return pending


def remember_booking_service(c: Dict[str, Any], pending: Dict[str, Any], service_item: Optional[Dict[str, Any]], lang: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    service_key = str((service_item or {}).get("key") or c.get("service") or pending.get("service") or "").strip()
    if service_key:
        c["service"] = service_key
        pending["service"] = service_key
    display = service_display_name(service_item, lang) if service_item else str(pending.get("service_display") or "").strip()
    if display:
        pending["service_display"] = display
    c["pending"] = pending or None
    return c, pending


def is_yes_text(text_: Optional[str], lang: str) -> bool:
    low = (text_ or "").strip().lower()
    if not low:
        return False
    allowed = set().union(*YES_WORDS.values())
    allowed.update(YES_WORDS.get(get_lang(lang), set()))
    return low in allowed


def is_no_text(text_: Optional[str], lang: str) -> bool:
    low = (text_ or "").strip().lower()
    if not low:
        return False
    allowed = set().union(*NO_WORDS.values())
    allowed.update(NO_WORDS.get(get_lang(lang), set()))
    return low in allowed

def is_short_ack_text(text_: Optional[str], lang: str) -> bool:
    low = (text_ or "").strip().lower()
    if not low:
        return False
    short_acks = {
        "lv": {"labi", "skaidrs", "ok", "okej", "der", "nu labi"},
        "ru": {"ок", "хорошо", "ладно", "давай", "понятно", "угу"},
        "en": {"ok", "okay", "sure", "alright", "got it"},
    }
    allowed = set().union(*short_acks.values())
    allowed.update(short_acks.get(get_lang(lang), set()))
    return low in allowed


def soft_clarify_for_state(lang: str, c: Dict[str, Any], pending: Dict[str, Any]) -> str:
    state = conversation_state(c)
    if state == STATE_AWAITING_SERVICE:
        return t(lang, "soft_clarify_service")
    if state == STATE_AWAITING_DATE:
        return t(lang, "soft_clarify_date")
    if state == STATE_AWAITING_TIME:
        return t(lang, "soft_clarify_time")
    if state == STATE_AWAITING_CONFIRM:
        return t(lang, "soft_clarify_confirm")
    return t(lang, "unclear_reply")


def next_weekday_date(target_weekday: int, base: Optional[date] = None) -> date:
    base = base or today_local()
    days_ahead = (target_weekday - base.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base + timedelta(days=days_ahead)


def parse_date_only_text(text_: Optional[str]) -> Optional[datetime]:
    src = (text_ or "").lower().strip()
    if not src:
        return None

    dm = re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", src)
    if dm:
        dd, mo = int(dm.group(1)), int(dm.group(2))
        yy = dm.group(3)
        year = int(yy) + 2000 if yy and len(yy) == 2 else int(yy) if yy else today_local().year
        try:
            return datetime(year, mo, dd, 9, 0, tzinfo=TZ)
        except Exception:
            pass

    base = today_local()

    # Weekdays must win over relative substrings like "rīt" inside "rīta".
    for wd, hints in WEEKDAY_HINTS.items():
        if _contains_any_phrase(src, hints):
            d = next_weekday_date(wd, base)
            return datetime.combine(d, datetime.min.time(), tzinfo=TZ).replace(hour=9)

    if _contains_any_phrase(src, ["parīt", "послезавтра", "day after tomorrow"]):
        return datetime.combine(base + timedelta(days=2), datetime.min.time(), tzinfo=TZ).replace(hour=9)
    if _contains_any_phrase(src, ["rīt", "rit", "завтра", "tomorrow"]):
        return datetime.combine(base + timedelta(days=1), datetime.min.time(), tzinfo=TZ).replace(hour=9)
    if _contains_any_phrase(src, ["šodien", "sodien", "šorīt", "sorit", "šovakar", "sovakar", "сегодня", "сегодня утром", "сегодня днем", "сегодня днём", "сегодня вечером", "today", "this morning", "this afternoon", "this evening", "tonight"]):
        return datetime.combine(base, datetime.min.time(), tzinfo=TZ).replace(hour=9)

    return None


NATURAL_TIME_DEFAULTS = {
    "morning": 10,
    "midday": 12,
    "afternoon": 14,
    "evening": 17,
}

def detect_time_bucket(text_: Optional[str]) -> Optional[str]:
    src = (text_ or "").lower().strip()
    if not src:
        return None
    patterns = {
        "morning": [
            "no rīta", "no rita", "rīt no rīta", "rit no rita", "šorīt", "sorit", "rīta", "rita",
            "утром", "сегодня утром", "утра",
            "in the morning", "this morning", "morning"
        ],
        "midday": [
            "pusdienlaikā", "pusdienlaika", "ap pusdienlaiku", "днём", "днем", "сегодня днем", "сегодня днём", "at noon", "noon", "midday"
        ],
        "afternoon": [
            "pēcpusdienā", "pecpusdiena", "pecpusdienā", "šopēcpusdien", "sopecpusdien", "after lunch", "in the afternoon", "this afternoon", "afternoon", "днём", "днем", "после обеда"
        ],
        "evening": [
            "vakarā", "vakara", "vakaru", "uz vakaru", "vakarpusē", "vakarpuse", "šovakar", "sovakar",
            "вечером", "вечеру", "сегодня вечером", "к вечеру", "ближе к вечеру", "на вечер", "на вечернее время",
            "in the evening", "this evening", "later in the evening", "towards evening", "evening", "tonight",
            "pēc darba", "pec darba", "после работы", "after work"
        ],
    }
    for bucket, hints in patterns.items():
        if _contains_any_phrase(src, hints):
            return bucket
    return None

def parse_time_window(text_: Optional[str]) -> Optional[Tuple[int, int]]:
    src = (text_ or "").lower().strip()
    if not src:
        return None

    if _contains_any_phrase(src, ["pēc darba", "pec darba", "после работы", "after work"]):
        return (17, 21)
    if _contains_any_phrase(src, [
        "ближе к вечеру", "к вечеру", "на вечер", "на вечернее время",
        "uz vakaru", "vakarpusē", "vakarpuse", "vakaru",
        "towards evening", "later in the evening", "in the evening", "tonight"
    ]):
        return (16, 21)

    bucket = detect_time_bucket(src)
    if bucket == "morning":
        return (9, 12)
    if bucket == "midday":
        return (11, 14)
    if bucket == "afternoon":
        return (12, 17)
    if bucket == "evening":
        return (16, 21)
    return None

def has_natural_time_hint(text_: Optional[str]) -> bool:
    src = (text_ or "").lower().strip()
    if not src:
        return False
    if parse_explicit_time_parts(src):
        return True
    if detect_time_bucket(src):
        return True
    approx_markers = ["ap ", "apmēram", "apmeram", "kaut kur", "around", "about", "около", "примерно"]
    if any(m in src for m in approx_markers):
        return True
    return False


def sanitize_conversation_time_text(value: Any) -> Optional[str]:
    txt = str(value or "").strip()
    if not txt:
        return None
    # Store only short user-provided temporal hints to avoid DB truncation and polluted state.
    if len(txt) > 64:
        return None
    if has_explicit_time(txt) or has_date_reference(txt) or has_natural_time_hint(txt):
        return txt
    return None


def pending_time_window_tuple(pending: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    raw = (pending or {}).get("preferred_time_window")
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        try:
            return int(raw[0]), int(raw[1])
        except Exception:
            return None
    return None

def parse_natural_datetime(text_: Optional[str], base_iso: Optional[str] = None) -> Optional[datetime]:
    src = (text_ or "").lower().strip()
    if not src:
        return None

    base_dt = parse_dt_any_tz((base_iso or "").strip())
    date_dt = parse_date_only_text(src)
    if not date_dt and base_dt:
        date_dt = base_dt

    time_parts = parse_explicit_time_parts(src)

    if not time_parts:
        approx_patterns = [
            r"\bap\s+([01]?\d|2[0-3])\b",
            r"\bapmēram\s+([01]?\d|2[0-3])\b",
            r"\bapmeram\s+([01]?\d|2[0-3])\b",
            r"\bkaut\s+kur\s+([01]?\d|2[0-3])\b",
            r"\baround\s+([01]?\d|2[0-3])\b",
            r"\babout\s+([01]?\d|2[0-3])\b",
            r"\bоколо\s+([01]?\d|2[0-3])\b",
            r"\bпримерно\s+([01]?\d|2[0-3])\b",
        ]
        for pat in approx_patterns:
            m = re.search(pat, src)
            if m:
                time_parts = (int(m.group(1)), 0)
                break

    if not time_parts:
        bucket = detect_time_bucket(src)
        if bucket:
            time_parts = (NATURAL_TIME_DEFAULTS[bucket], 0)

    if date_dt and time_parts:
        hh, mm = time_parts
        return date_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)

    if date_dt and not time_parts and detect_time_bucket(src):
        hh = NATURAL_TIME_DEFAULTS[detect_time_bucket(src)]
        return date_dt.replace(hour=hh, minute=0, second=0, microsecond=0)

    if not date_dt and base_dt and time_parts:
        hh, mm = time_parts
        return base_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)

    return None


def extract_service_from_text(text_: Optional[str], catalog: List[Dict[str, Any]], lang: str) -> Optional[Dict[str, Any]]:
    low = (text_ or "").strip().lower()
    if not low:
        return None

    candidates_index: List[Tuple[int, str, Dict[str, Any]]] = []
    for item in catalog:
        display = service_display_name(item, lang).lower()
        candidates = {display, str(item.get("key") or "").strip().lower()}
        candidates.update(str(x).strip().lower() for x in (item.get(f"aliases_{get_lang(lang)}") or []) if str(x).strip())
        candidates.update(str(x).strip().lower() for x in (item.get("aliases_lv") or []) if str(x).strip())
        candidates.update(str(x).strip().lower() for x in (item.get("aliases_ru") or []) if str(x).strip())
        candidates.update(str(x).strip().lower() for x in (item.get("aliases_en") or []) if str(x).strip())
        for cand in candidates:
            if cand:
                candidates_index.append((len(cand), cand, item))

    for _, cand, item in sorted(candidates_index, key=lambda x: x[0], reverse=True):
        if cand == low or cand in low or low in cand:
            return item
    return None


def extract_slot_choice(msg: Optional[str], pending: Dict[str, Any]) -> Optional[str]:
    low = (msg or "").strip().lower()
    offered = get_offered_slots(pending)
    if not offered:
        return None
    if low == "1" and len(offered) >= 1:
        return offered[0]
    if low == "2" and len(offered) >= 2:
        return offered[1]
    if low == "3" and len(offered) >= 3:
        return offered[2]

    parsed_parts = parse_explicit_time_parts(low)
    if parsed_parts:
        hh, mm = parsed_parts
        for iso in offered:
            dt = parse_dt_any_tz(iso)
            if dt and dt.hour == hh and dt.minute == mm:
                return iso

    for iso in offered:
        dt = parse_dt_any_tz(iso)
        if not dt:
            continue
        short_dt = format_dt_short(dt).lower()
        hhmm = dt.strftime("%H:%M").lower()
        if low == short_dt or low == hhmm or low in short_dt:
            return iso
    return None


def prompt_for_state(lang: str, c: Dict[str, Any], pending: Dict[str, Any], service_catalog: Optional[List[Dict[str, Any]]] = None) -> str:
    state = conversation_state(c)
    if state == STATE_AWAITING_SERVICE:
        return barber_service_prompt(lang, service_catalog or default_onboarding_service_catalog("barbershop"))
    if state == STATE_AWAITING_DATE:
        return t(lang, "ask_booking_date")
    if state == STATE_AWAITING_TIME:
        offered = get_offered_slots(pending)
        if len(offered) >= 3:
            dt1 = parse_dt_any_tz(offered[0])
            dt2 = parse_dt_any_tz(offered[1])
            dt3 = parse_dt_any_tz(offered[2])
            if dt1 and dt2 and dt3:
                return t(lang, "smart_slots_repeat", opt1=format_dt_short(dt1), opt2=format_dt_short(dt2), opt3=format_dt_short(dt3))
        if len(offered) >= 2:
            dt1 = parse_dt_any_tz(offered[0])
            dt2 = parse_dt_any_tz(offered[1])
            if dt1 and dt2:
                return t(lang, "voice_options_repeat", opt1=format_dt_short(dt1), opt2=format_dt_short(dt2))
        return t(lang, "ask_booking_time_only")
    if state == STATE_AWAITING_CONFIRM:
        confirm_iso = str(pending.get("confirm_slot_iso") or c.get("datetime_iso") or "").strip()
        dt_confirm = parse_dt_any_tz(confirm_iso)
        service_name = pending.get("service_display") or c.get("service") or ""
        if dt_confirm:
            return t(lang, "ask_booking_confirm", when=format_dt_short(dt_confirm), service=service_name or t(lang, "need_service"))
        return t(lang, "repeat_yes_no")
    return t(lang, "how_help")


def reset_booking_context(c: Dict[str, Any], keep_name: bool = True) -> Dict[str, Any]:
    preserved_name = c.get("name") if keep_name else None
    c["service"] = None
    c["datetime_iso"] = None
    c["time_text"] = None
    c["pending"] = {"booking_intent": True}
    c["state"] = STATE_AWAITING_SERVICE
    if keep_name:
        c["name"] = preserved_name
    else:
        c["name"] = None
    return c


def normalize_booking_state(c: Dict[str, Any]) -> Dict[str, Any]:
    pending = c.get("pending") or {}
    state = conversation_state(c)
    service_key = str(c.get("service") or pending.get("service") or "").strip()
    confirm_iso = str(pending.get("confirm_slot_iso") or "").strip()
    awaiting_time_date_iso = str(pending.get("awaiting_time_date_iso") or "").strip()
    offered_slots = get_offered_slots(pending)
    has_booking_intent = bool(pending.get("booking_intent"))
    booked_dt = str(c.get("datetime_iso") or "").strip()

    if confirm_iso:
        state = STATE_AWAITING_CONFIRM
    elif offered_slots or awaiting_time_date_iso:
        state = STATE_AWAITING_TIME
    elif service_key and state not in (STATE_POST_BOOKING_UPSELL, STATE_BOOKED, STATE_CANCELLED):
        state = STATE_AWAITING_DATE if not booked_dt else state
    elif has_booking_intent and not service_key:
        state = STATE_AWAITING_SERVICE
    elif state in ACTIVE_BOOKING_STATES and not service_key:
        state = STATE_AWAITING_SERVICE

    if state in (STATE_BOOKED, STATE_CANCELLED) and has_booking_intent:
        state = STATE_AWAITING_SERVICE if not service_key else STATE_AWAITING_DATE

    c["state"] = state
    c["pending"] = pending or None
    return c


def book_appointment_for_datetime(
    tenant_id: str,
    raw_phone: str,
    channel: str,
    lang: str,
    c: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    dt_start: datetime,
    require_confirmation: bool = True,
) -> Dict[str, Any]:
    voice_like_channel = (channel or "").strip().lower() == "voice"
    pending = c.get("pending") or {}
    calendar_ready = calendar_is_configured(settings["calendar_id"])
    service_item = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
    duration_min = service_duration_min(service_item)

    if not calendar_ready:
        return blocked_result_for_lang(lang)

    if is_closed_day_for_rules(dt_start, settings.get("business_rules")):
        pending = c.get("pending") or {}
        pending["booking_intent"] = True
        pending["awaiting_time_date_iso"] = None
        clear_offered_slots(pending)
        c["pending"] = pending
        c["state"] = STATE_AWAITING_DATE
        c["datetime_iso"] = None
        return {
            "status": "need_more" if voice_like_channel else "holiday_closed",
            "reply_voice": t(lang, "holiday_closed_voice"),
            "msg_out": t(lang, "holiday_closed_text"),
            "lang": lang,
        }

    if violates_min_notice(dt_start, settings.get("business_rules")):
        duration_for_notice = duration_min
        cutoff = min_notice_cutoff(settings.get("business_rules")) or now_ts()
        opts = find_next_two_slots(
            settings["calendar_id"],
            cutoff,
            duration_for_notice,
            settings["work_start"],
            settings["work_end"],
            settings.get("business_rules"),
            settings.get("service_account_json"),
        )
        if opts:
            pending = set_offered_slots(pending, [opts[0], opts[1]])
            pending["service"] = c.get("service")
            pending["name"] = c.get("name")
            pending.pop("confirm_slot_iso", None)
            c["pending"] = pending
            c["state"] = STATE_AWAITING_TIME
            c["datetime_iso"] = None
            voice_prompt = t(lang, "voice_options_prompt", opt1=format_dt_short(opts[0]), opt2=format_dt_short(opts[1])) if voice_like_channel else t(lang, "min_notice_voice")
            return {
                "status": "need_more" if voice_like_channel else "min_notice",
                "reply_voice": voice_prompt,
                "msg_out": t(lang, "min_notice_text"),
                "lang": lang,
            }
        return {
            "status": "need_more" if voice_like_channel else "min_notice",
            "reply_voice": t(lang, "min_notice_voice"),
            "msg_out": t(lang, "min_notice_text"),
            "lang": lang,
        }

    if not in_business_hours(dt_start, duration_min, settings["work_start"], settings["work_end"], settings.get("business_rules")):
        opts = find_next_two_slots(settings["calendar_id"], dt_start, duration_min, settings["work_start"], settings["work_end"], settings.get("business_rules"), settings.get("service_account_json"))
        if opts:
            pending = set_offered_slots(pending, [opts[0], opts[1]])
            pending["service"] = c.get("service")
            pending["name"] = c.get("name")
            pending.pop("confirm_slot_iso", None)
            c["pending"] = pending
            c["state"] = STATE_AWAITING_TIME
            c["datetime_iso"] = None
            voice_prompt = t(lang, "voice_options_prompt", opt1=format_dt_short(opts[0]), opt2=format_dt_short(opts[1])) if voice_like_channel else t(lang, "closed_voice")
            return {
                "status": "need_more" if voice_like_channel else "busy",
                "reply_voice": voice_prompt,
                "msg_out": t(lang, "closed_text", opt1=format_dt_short(opts[0]), opt2=format_dt_short(opts[1])),
                "lang": lang,
            }
        return {
            "status": "recovery",
            "reply_voice": t(lang, "all_busy_voice"),
            "msg_out": t(lang, "all_busy_text"),
            "lang": lang,
        }

    if is_slot_busy(settings["calendar_id"], dt_start, dt_start + timedelta(minutes=duration_min), _safe_int((settings.get("business_rules") or {}).get("buffer_minutes"), 0), service_account_json=settings.get("service_account_json")):
        opts = find_next_two_slots(settings["calendar_id"], dt_start, duration_min, settings["work_start"], settings["work_end"], settings.get("business_rules"), settings.get("service_account_json"))
        if opts:
            pending = set_offered_slots(pending, [opts[0], opts[1]])
            pending["service"] = c.get("service")
            pending["name"] = c.get("name")
            pending.pop("confirm_slot_iso", None)
            c["pending"] = pending
            c["state"] = STATE_AWAITING_TIME
            c["datetime_iso"] = None
            voice_prompt = t(lang, "voice_options_prompt", opt1=format_dt_short(opts[0]), opt2=format_dt_short(opts[1])) if voice_like_channel else t(lang, "busy_voice")
            return {
                "status": "need_more" if voice_like_channel else "busy",
                "reply_voice": voice_prompt,
                "msg_out": t(lang, "busy_text", opt1=format_dt_short(opts[0]), opt2=format_dt_short(opts[1])),
                "lang": lang,
            }
        return {
            "status": "recovery",
            "reply_voice": t(lang, "all_busy_voice"),
            "msg_out": t(lang, "all_busy_text"),
            "lang": lang,
        }

    final_name = normalize_name(c.get("name")) or normalize_name(pending.get("name")) or extract_name_from_event_description(pending.get("reschedule_description") or "") or "Client"
    final_service_key = str(c.get("service") or pending.get("service") or "").strip()
    final_service_item = get_service_item_by_key(service_catalog, final_service_key) or service_item
    addon_service_key = str(pending.get("addon_service") or "").strip()
    addon_service_item = get_service_item_by_key(service_catalog, addon_service_key) if addon_service_key else None
    if not final_service_item and pending.get("reschedule_summary"):
        old_summary = str(pending.get("reschedule_summary") or "").strip()
        if " - " in old_summary:
            old_service_name = old_summary.split(" - ", 1)[1].strip()
        else:
            old_service_name = old_summary
        final_service = old_service_name or settings["services_hint"]
    else:
        final_service = combined_service_display(lang, final_service_item, addon_service_item) or service_display_name(final_service_item, lang) or settings["services_hint"]
    duration_min = service_duration_min(final_service_item) + (service_duration_min(addon_service_item) if addon_service_item else 0)
    old_dt = parse_dt_any_tz(str(pending.get("reschedule_old_iso") or "").strip()) if pending.get("reschedule_old_iso") else None
    is_reschedule_flow = bool(pending.get("reschedule_event_id"))

    if is_reschedule_flow and old_dt and abs((dt_start - old_dt).total_seconds()) < 60:
        c["pending"] = pending
        c["state"] = STATE_AWAITING_TIME if get_offered_slots(pending) else STATE_AWAITING_DATE
        c["datetime_iso"] = old_dt.isoformat()
        return {
            "status": "need_more",
            "reply_voice": t(lang, "reschedule_same_time"),
            "msg_out": t(lang, "reschedule_same_time"),
            "lang": lang,
        }

    if require_confirmation:
        pending["booking_intent"] = True
        pending["confirm_slot_iso"] = dt_start.isoformat()
        pending["service"] = final_service_key or str(final_service_item.get("key") if final_service_item else "")
        pending["service_display"] = final_service
        pending["name"] = final_name
        c["pending"] = pending
        c["state"] = STATE_AWAITING_CONFIRM
        c["name"] = final_name
        c["service"] = pending["service"]
        c["datetime_iso"] = dt_start.isoformat()

        beard_item = find_service_item_by_group(service_catalog, "beard")
        if (
            service_group_key(final_service_item) == "haircut"
            and beard_item
            and not addon_service_item
            and not pending.get("confirm_upsell_done")
        ):
            pending["pending_confirm_upsell"] = True
            pending["confirm_upsell_done"] = True
            c["pending"] = pending
            when_txt = format_dt_short(dt_start)
            reply_text = build_confirm_upsell_prompt(lang, when_txt, final_service_item, beard_item)
            return {
                "status": "need_more",
                "reply_voice": reply_text,
                "msg_out": reply_text,
                "lang": lang,
                "preserve_text": True,
            }

        return {
            "status": "need_more",
            "reply_voice": t(lang, "ask_booking_confirm", when=format_dt_short(dt_start), service=final_service),
            "msg_out": t(lang, "ask_booking_confirm", when=format_dt_short(dt_start), service=final_service),
            "lang": lang,
        }

    event_summary = str(pending.get("reschedule_summary") or f"{settings['biz_name']} - {final_service}").strip()
    event_description = str(pending.get("reschedule_description") or build_event_description(tenant_id, final_name, raw_phone)).strip()

    if is_reschedule_flow:
        event_result = update_calendar_event(
            settings["calendar_id"],
            pending["reschedule_event_id"],
            dt_start,
            duration_min,
            event_summary,
            event_description,
            settings.get("service_account_json"),
        )
        if not event_result:
            pending["confirm_slot_iso"] = dt_start.isoformat()
            c["pending"] = pending
            c["state"] = STATE_AWAITING_CONFIRM
            c["name"] = final_name
            c["service"] = pending.get("service") or final_service_key
            c["datetime_iso"] = dt_start.isoformat()
            return {
                "status": "booking_failed",
                "reply_voice": t(lang, "reschedule_failed_keep"),
                "msg_out": t(lang, "reschedule_failed_keep"),
                "lang": lang,
            }
    else:
        event_result = create_calendar_event(
            settings["calendar_id"],
            dt_start,
            duration_min,
            event_summary,
            event_description,
            settings.get("service_account_json"),
        )

        if not event_result:
            pending["confirm_slot_iso"] = dt_start.isoformat()
            c["pending"] = pending
            c["state"] = STATE_AWAITING_CONFIRM
            c["name"] = final_name
            c["service"] = pending.get("service") or final_service_key
            c["datetime_iso"] = dt_start.isoformat()
            return {
                "status": "booking_failed",
                "reply_voice": t(lang, "booking_failed"),
                "msg_out": t(lang, "booking_failed"),
                "lang": lang,
            }

    pending.pop("confirm_slot_iso", None)
    pending.pop("awaiting_time_date_iso", None)
    pending.pop("candidate_datetime_iso", None)
    pending.pop("preferred_time_window", None)
    pending.pop("pending_confirm_upsell", None)
    pending.pop("confirm_upsell_done", None)
    pending.pop("addon_service", None)
    clear_offered_slots(pending)
    was_rescheduled = bool(pending.get("reschedule_event_id"))
    if pending.get("reschedule_event_id"):
        pending.pop("reschedule_event_id", None)
        pending.pop("reschedule_old_iso", None)
        pending.pop("reschedule_summary", None)
        pending.pop("reschedule_description", None)
    c["pending"] = pending or None
    c["state"] = STATE_BOOKED
    c["name"] = final_name
    c["service"] = pending.get("service") or final_service_key
    c["datetime_iso"] = dt_start.isoformat()
    return {
        "status": "booked",
        "reply_voice": t(lang, "rescheduled_voice", when=format_dt_short(dt_start)) if was_rescheduled else t(lang, "booking_confirmed"),
        "msg_out": t(lang, "rescheduled_text", service=final_service, when=format_dt_short(dt_start)) if was_rescheduled else t(lang, "booking_confirmed_text", service=final_service, when=format_dt_short(dt_start)),
        "lang": lang,
        "service": final_service,
        "when": format_dt_short(dt_start),
        "datetime_text": format_dt_short(dt_start),
    }


# -------------------------
# CORE LOGIC: handle_user_text
# -------------------------
def handle_user_text(
    tenant_id: str, raw_phone: str, text_in: str, channel: str, lang_hint: str
) -> Dict[str, Any]:
    msg = (text_in or "").strip()
    tenant = get_tenant(tenant_id)
    allowed, _ = tenant_allowed(tenant)

    detected_lang = get_lang(lang_hint or detect_language(msg))
    user_key = norm_user_key(raw_phone)
    c = db_get_or_create_conversation(tenant_id, user_key, detected_lang)

    if msg:
        c["lang"] = resolve_reply_language(msg, c.get("lang") or detected_lang)

    lang = get_lang(c.get("lang"))
    if not tenant_runtime_ready(tenant):
        log_tenant_runtime_validation(tenant)
        return blocked_result_for_lang(lang)
    settings = tenant_settings(tenant, lang)
    service_catalog = tenant_service_catalog(tenant)
    service_aliases = ensure_default_barbershop_aliases(
        service_catalog,
        merged_service_alias_map(service_catalog, tenant, lang),
        lang,
    )
    business_memory = tenant_business_memory(tenant, lang)
    calendar_ready = calendar_is_configured(settings["calendar_id"])

    if not allowed:
        return blocked_result_for_lang(lang)

    c["state"] = conversation_state(c)
    c = normalize_booking_state(c)
    pending = c.get("pending") or {}
    t_low = msg.lower()

    ai_data: Optional[Dict[str, Any]] = None
    llm_data: Optional[Dict[str, Any]] = None

    def get_llm_data() -> Dict[str, Any]:
        nonlocal llm_data
        if llm_data is not None:
            return llm_data
        llm_data = llm_message_understanding(
            msg=msg,
            lang=lang,
            settings=settings,
            service_catalog=service_catalog,
            service_aliases=service_aliases,
            business_memory=business_memory,
        )
        return llm_data

    def get_ai_data() -> Dict[str, Any]:
        nonlocal ai_data
        if ai_data is not None:
            return ai_data
        alias_hint = ", ".join([f"{k} => {v}" for k, v in list(service_aliases.items())[:50]])
        sys_pt = (
            f"You are an appointment receptionist for {settings['biz_name']}. "
            f"Business hours: {settings['work_start']}-{settings['work_end']}. "
            f"Known services: {service_catalog_summary(service_catalog, lang)}. "
            f"Service aliases map to service keys: {alias_hint or 'none'}. "
            f"Business memory: {business_memory or 'none'}. "
            "Extract and return strict JSON only with keys: service, time_text, datetime_iso, name. "
            "service and name must be plain strings, not arrays. "
            "If a user names a service using an alias, map it to the canonical service name. "
            "If value is unknown use null."
        )
        usr_pt = f"Today: {now_ts().date()}. User language: {lang}. User message: {msg}"
        ai_data = openai_chat_json(sys_pt, usr_pt)
        return ai_data

    llm_hint = get_llm_data() if msg else {}

    if any(w in t_low for w in ["atcelt", "отменить", "cancel"]) or ((llm_hint or {}).get("intent") == "cancel" and float((llm_hint or {}).get("confidence") or 0.0) >= LLM_INTENT_MIN_CONFIDENCE):
        if not calendar_ready:
            return blocked_result_for_lang(lang)
        ev = find_next_event_by_phone(settings["calendar_id"], raw_phone, tenant_id, settings.get("service_account_json"))
        if not ev:
            return {
                "status": "no_booking",
                "reply_voice": t(lang, "no_active_booking"),
                "msg_out": t(lang, "no_active_booking"),
                "lang": lang,
            }
        deleted = delete_calendar_event(settings["calendar_id"], ev["id"], settings.get("service_account_json"))
        if not deleted:
            return {
                "status": "cancel_failed",
                "reply_voice": t(lang, "cancel_failed"),
                "msg_out": t(lang, "cancel_failed"),
                "lang": lang,
            }
        c["pending"] = None
        c["state"] = STATE_CANCELLED
        c["datetime_iso"] = None
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "cancelled",
            "reply_voice": t(lang, "cancelled"),
            "msg_out": t(lang, "cancelled"),
            "lang": lang,
        }

    if any(w in t_low for w in ["pārcelt", "перенести", "reschedule"]) or ((llm_hint or {}).get("intent") == "reschedule" and float((llm_hint or {}).get("confidence") or 0.0) >= LLM_INTENT_MIN_CONFIDENCE):
        if not calendar_ready:
            return blocked_result_for_lang(lang)
        ev = find_next_event_by_phone(settings["calendar_id"], raw_phone, tenant_id, settings.get("service_account_json"))
        if not ev:
            return {
                "status": "no_booking",
                "reply_voice": t(lang, "no_active_booking"),
                "msg_out": t(lang, "no_active_booking"),
                "lang": lang,
            }
        dt_old = parse_dt_any_tz(ev["start"].get("dateTime", ""))
        c["pending"] = {
            "booking_intent": True,
            "reschedule_event_id": ev["id"],
            "reschedule_old_iso": ev["start"].get("dateTime"),
            "reschedule_summary": ev.get("summary") or "",
            "reschedule_description": ev.get("description") or "",
        }
        existing_name = extract_name_from_event_description(ev.get("description") or "")
        if existing_name and not c.get("name"):
            c["name"] = existing_name
        c["state"] = STATE_AWAITING_DATE
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "reschedule_wait",
            "reply_voice": t(lang, "reschedule_ask", when=format_dt_short(dt_old)),
            "msg_out": t(lang, "reschedule_ask", when=format_dt_short(dt_old)),
            "lang": lang,
        }

    active_flow = is_active_booking_flow(c)

    if pending.get("reschedule_event_id") and msg and abort_reschedule_text(msg, lang):
        pending.pop("reschedule_event_id", None)
        pending.pop("reschedule_old_iso", None)
        pending.pop("reschedule_summary", None)
        pending.pop("reschedule_description", None)
        pending.pop("confirm_slot_iso", None)
        pending.pop("awaiting_time_date_iso", None)
        clear_offered_slots(pending)
        c["pending"] = None
        c["state"] = STATE_BOOKED
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "info",
            "reply_voice": t(lang, "reschedule_keep_current"),
            "msg_out": t(lang, "reschedule_keep_current"),
            "lang": lang,
        }

    if msg:
        faq_result = try_barbershop_faq(
            msg=msg,
            lang=lang,
            tenant=tenant,
            settings=settings,
            service_catalog=service_catalog,
            service_aliases=service_aliases,
            business_memory=business_memory,
        )
        if faq_result:
            faq_result = faq_with_flow_followup(faq_result, lang, c, pending, service_catalog, active_flow)
            if active_flow:
                db_save_conversation(tenant_id, user_key, c)
            return faq_result

    if msg and is_greeting_only(msg) and not active_flow and c["state"] not in ACTIVE_BOOKING_STATES:
        c["state"] = STATE_NEW
        c["service"] = None
        c["datetime_iso"] = None
        c["time_text"] = None
        c["pending"] = None
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "greeting",
            "reply_voice": t(lang, "greeting_only_reply"),
            "msg_out": t(lang, "greeting_only_reply"),
            "lang": lang,
        }
    if not active_flow and msg and is_identity_check(msg):
        return {
            "status": "identity",
            "reply_voice": t(lang, "identity_yes", biz=settings["biz_name"]),
            "msg_out": t(lang, "identity_yes", biz=settings["biz_name"]),
            "lang": lang,
        }
    if not active_flow and msg and is_hours_question(msg):
        return {
            "status": "info",
            "reply_voice": t(lang, "hours_info", biz=settings["biz_name"], start=settings["work_start"], end=settings["work_end"]),
            "msg_out": t(lang, "hours_info", biz=settings["biz_name"], start=settings["work_start"], end=settings["work_end"]),
            "lang": lang,
        }

    llm_hint = get_llm_data() if msg else {}

    fresh_booking_start = bool(msg and is_booking_opener(msg))
    llm_intent = _normalize_llm_intent((llm_hint or {}).get("intent"))
    llm_conf = float((llm_hint or {}).get("confidence") or 0.0)
    explicit_time_present = has_explicit_time(msg)
    date_only_dt_for_msg = parse_date_only_text(msg)
    natural_dt_for_msg = parse_natural_datetime(msg)
    time_window_for_msg = parse_time_window(msg)

    # IMPORTANT:
    # Do not restart an already active booking flow just because the LLM
    # broadly classified a short follow-up like "pēc darba" / "after work"
    # as a booking message. Inside an active flow these should be treated
    # as contextual booking details, not a brand new booking opener.
    if (
        not fresh_booking_start
        and not active_flow
        and c["state"] not in ACTIVE_BOOKING_STATES
        and llm_intent == "booking"
        and llm_conf >= LLM_INTENT_MIN_CONFIDENCE
    ):
        fresh_booking_start = True

    if not c.get("name") and (llm_hint or {}).get("name"):
        c["name"] = llm_hint.get("name")
    llm_time_text = sanitize_conversation_time_text((llm_hint or {}).get("time_text"))
    if not c.get("time_text") and llm_time_text:
        c["time_text"] = llm_time_text

    if fresh_booking_start:
        c = reset_booking_context(c, keep_name=True)
        pending = c.get("pending") or {}
        active_flow = True

    pending = c.get("pending") or {}

    if fresh_booking_start and msg:
        direct_service_key_open = canonical_service_key_from_text(msg, service_aliases)
        service_item_open = get_service_item_by_key(service_catalog, direct_service_key_open) if direct_service_key_open else None
        if not service_item_open:
            service_item_open = extract_service_from_text(msg, service_catalog, lang)
        if service_item_open:
            c, pending = remember_booking_service(c, pending, service_item_open, lang)
        else:
            c["service"] = None
            pending.pop("service", None)
            pending.pop("service_display", None)
            pending.pop("candidate_datetime_iso", None)
            pending.pop("awaiting_time_date_iso", None)
            pending.pop("preferred_time_window", None)
            clear_offered_slots(pending)
            c["pending"] = pending or None
            c["datetime_iso"] = None
            c["time_text"] = None
            c["state"] = STATE_AWAITING_SERVICE
            db_save_conversation(tenant_id, user_key, c)
            service_prompt = barber_service_prompt(lang, service_catalog)
            return {
                "status": "need_more",
                "reply_voice": service_prompt,
                "msg_out": service_prompt,
                "lang": lang,
                "preserve_text": True,
            }

    if msg and (natural_dt_for_msg or date_only_dt_for_msg or time_window_for_msg or explicit_time_present):
        pending["booking_intent"] = True
        if time_window_for_msg:
            pending["preferred_time_window"] = [time_window_for_msg[0], time_window_for_msg[1]]
        if natural_dt_for_msg and explicit_time_present:
            pending["candidate_datetime_iso"] = natural_dt_for_msg.isoformat()
            pending["awaiting_time_date_iso"] = natural_dt_for_msg.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
        elif natural_dt_for_msg:
            pending["awaiting_time_date_iso"] = natural_dt_for_msg.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
        elif date_only_dt_for_msg:
            pending["awaiting_time_date_iso"] = date_only_dt_for_msg.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
        c["pending"] = pending

    selected_iso = extract_slot_choice(msg, pending)
    if selected_iso:
        dt_sel = parse_dt_any_tz(selected_iso)
        if dt_sel:
            result = book_appointment_for_datetime(tenant_id, raw_phone, channel, lang, c, settings, service_catalog, dt_sel)
            db_save_conversation(tenant_id, user_key, c)
            return result

    if active_flow or c["state"] in ACTIVE_BOOKING_STATES or c["state"] == STATE_NEW:
        direct_service_key = canonical_service_key_from_text(msg, service_aliases)
        service_item = get_service_item_by_key(service_catalog, direct_service_key) if direct_service_key else None
        if not service_item:
            service_item = extract_service_from_text(msg, service_catalog, lang)
        if not service_item and msg:
            llm_service_key = (llm_hint or {}).get("service")
            if llm_service_key:
                service_item = get_service_item_by_key(service_catalog, llm_service_key)
        if not service_item and msg:
            data = get_ai_data()
            extracted_service_key = apply_service_aliases(data.get("service"), service_aliases) or canonical_service_key_from_text(data.get("service"), service_aliases)
            service_item = get_service_item_by_key(service_catalog, extracted_service_key) or extract_service_from_text(data.get("service"), service_catalog, lang)
            extracted_name = normalize_name(data.get("name"))
            if extracted_name and not c.get("name"):
                c["name"] = extracted_name
            ai_time_text = sanitize_conversation_time_text(data.get("time_text"))
            if ai_time_text and not c.get("time_text"):
                c["time_text"] = ai_time_text

        if service_item and not c.get("service"):
            c, pending = remember_booking_service(c, pending, service_item, lang)
            clear_offered_slots(pending)
            candidate_dt = parse_dt_any_tz(str(pending.get("candidate_datetime_iso") or "").strip())
            if candidate_dt:
                pending.pop("candidate_datetime_iso", None)
                c["pending"] = pending or None
                result = book_appointment_for_datetime(tenant_id, raw_phone, channel, lang, c, settings, service_catalog, candidate_dt)
                db_save_conversation(tenant_id, user_key, c)
                return result

            base_day = parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip())
            stored_window = pending_time_window_tuple(pending)
            if base_day:
                slots = []
                if stored_window and calendar_ready:
                    slots = find_first_n_slots_for_day_window(
                        calendar_id=settings["calendar_id"],
                        day_dt=base_day,
                        duration_min=service_duration_min(service_item),
                        work_start=settings["work_start"],
                        work_end=settings["work_end"],
                        window_start_hour=stored_window[0],
                        window_end_hour=stored_window[1],
                        limit=3,
                        business_rules=settings.get("business_rules"),
                        service_account_json=settings.get("service_account_json"),
                    )
                elif calendar_ready:
                    slots = find_first_n_slots_for_day(
                        settings["calendar_id"],
                        base_day,
                        service_duration_min(service_item),
                        settings["work_start"],
                        settings["work_end"],
                        limit=3,
                        business_rules=settings.get("business_rules"),
                        service_account_json=settings.get("service_account_json"),
                    )
                c["state"] = STATE_AWAITING_TIME
                c["datetime_iso"] = None
                c["pending"] = pending or None
                if len(slots) >= 3:
                    pending = set_offered_slots(pending, slots[:3])
                    c["pending"] = pending
                    db_save_conversation(tenant_id, user_key, c)
                    return {
                        "status": "need_more",
                        "reply_voice": t(lang, "smart_slots_prompt", opt1=format_dt_short(slots[0]), opt2=format_dt_short(slots[1]), opt3=format_dt_short(slots[2])),
                        "msg_out": t(lang, "smart_slots_prompt", opt1=format_dt_short(slots[0]), opt2=format_dt_short(slots[1]), opt3=format_dt_short(slots[2])),
                        "lang": lang,
                    }
                if len(slots) >= 2:
                    pending = set_offered_slots(pending, slots[:2])
                    c["pending"] = pending
                    db_save_conversation(tenant_id, user_key, c)
                    return {
                        "status": "need_more",
                        "reply_voice": t(lang, "voice_options_prompt", opt1=format_dt_short(slots[0]), opt2=format_dt_short(slots[1])),
                        "msg_out": t(lang, "voice_options_prompt", opt1=format_dt_short(slots[0]), opt2=format_dt_short(slots[1])),
                        "lang": lang,
                    }
                db_save_conversation(tenant_id, user_key, c)
                return {
                    "status": "need_more",
                    "reply_voice": t(lang, "ask_booking_time_only"),
                    "msg_out": t(lang, "ask_booking_time_only"),
                    "lang": lang,
                }

            c["pending"] = pending or None
            c = normalize_booking_state(c)
            if c["state"] in (STATE_NEW, STATE_AWAITING_SERVICE, STATE_AWAITING_DATE):
                c["state"] = STATE_AWAITING_DATE
                db_save_conversation(tenant_id, user_key, c)
                return {
                    "status": "need_more",
                    "reply_voice": t(lang, "ask_booking_date"),
                    "msg_out": t(lang, "ask_booking_date"),
                    "lang": lang,
                }

    pending = c.get("pending") or {}

    if c["state"] == STATE_AWAITING_SERVICE and not c.get("service"):
        db_save_conversation(tenant_id, user_key, c)
        reply_text = barber_service_prompt(lang, service_catalog)
        return {
            "status": "need_more",
            "reply_voice": reply_text,
            "msg_out": reply_text,
            "lang": lang,
        }

    if c.get("service") and c["state"] == STATE_NEW and not c.get("datetime_iso"):
        c["state"] = STATE_AWAITING_DATE
        c = normalize_booking_state(c)

    date_only_dt = date_only_dt_for_msg

    if c["state"] == STATE_AWAITING_DATE:
        if is_short_ack_text(msg, lang):
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "need_more",
                "reply_voice": t(lang, "ask_booking_date"),
                "msg_out": t(lang, "ask_booking_date"),
                "lang": lang,
            }
        dt_start = None
        natural_dt = parse_natural_datetime(msg)
        if natural_dt:
            dt_start = natural_dt
        elif msg:
            data = get_ai_data()
            dt_start = parse_dt_from_iso_or_fallback(data.get("datetime_iso"), data.get("time_text"), msg)
        if dt_start and (explicit_time_present or has_natural_time_hint(msg)):
            result = book_appointment_for_datetime(tenant_id, raw_phone, channel, lang, c, settings, service_catalog, dt_start)
            db_save_conversation(tenant_id, user_key, c)
            return result
        if date_only_dt or (dt_start and not (explicit_time_present or has_natural_time_hint(msg))):
            base_date = date_only_dt or dt_start
            pending["booking_intent"] = True
            service_item_current = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
            c, pending = remember_booking_service(c, pending, service_item_current, lang)
            pending["awaiting_time_date_iso"] = base_date.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
            clear_offered_slots(pending)
            stored_window = parse_time_window(msg) or pending_time_window_tuple(pending)
            if stored_window:
                pending["preferred_time_window"] = [stored_window[0], stored_window[1]]
            service_item_for_slots = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
            day_slots = (
                find_first_n_slots_for_day_window(
                    calendar_id=settings["calendar_id"],
                    day_dt=base_date,
                    duration_min=service_duration_min(service_item_for_slots),
                    work_start=settings["work_start"],
                    work_end=settings["work_end"],
                    window_start_hour=stored_window[0],
                    window_end_hour=stored_window[1],
                    limit=3,
                    business_rules=settings.get("business_rules"),
                    service_account_json=settings.get("service_account_json"),
                )
                if calendar_ready and stored_window
                else find_first_n_slots_for_day(
                    settings["calendar_id"],
                    base_date,
                    service_duration_min(service_item_for_slots),
                    settings["work_start"],
                    settings["work_end"],
                    limit=3,
                    business_rules=settings.get("business_rules"),
                    service_account_json=settings.get("service_account_json"),
                )
            ) if calendar_ready else []
            c["state"] = STATE_AWAITING_TIME
            c["datetime_iso"] = None
            if is_closed_day_for_rules(base_date, settings.get("business_rules")):
                c["pending"] = pending
                c["state"] = STATE_AWAITING_DATE
                db_save_conversation(tenant_id, user_key, c)
                return {
                    "status": "need_more",
                    "reply_voice": t(lang, "holiday_closed_voice"),
                    "msg_out": t(lang, "holiday_closed_text"),
                    "lang": lang,
                }
            if len(day_slots) >= 3:
                pending = set_offered_slots(pending, day_slots[:3])
                c["pending"] = pending
                db_save_conversation(tenant_id, user_key, c)
                return {
                    "status": "need_more",
                    "reply_voice": t(lang, "smart_slots_prompt", opt1=format_dt_short(day_slots[0]), opt2=format_dt_short(day_slots[1]), opt3=format_dt_short(day_slots[2])),
                    "msg_out": t(lang, "smart_slots_prompt", opt1=format_dt_short(day_slots[0]), opt2=format_dt_short(day_slots[1]), opt3=format_dt_short(day_slots[2])),
                    "lang": lang,
                }
            if len(day_slots) >= 2:
                pending = set_offered_slots(pending, day_slots[:2])
                c["pending"] = pending
                db_save_conversation(tenant_id, user_key, c)
                return {
                    "status": "need_more",
                    "reply_voice": t(lang, "voice_options_prompt", opt1=format_dt_short(day_slots[0]), opt2=format_dt_short(day_slots[1])),
                    "msg_out": t(lang, "voice_options_prompt", opt1=format_dt_short(day_slots[0]), opt2=format_dt_short(day_slots[1])),
                    "lang": lang,
                }
            c["pending"] = pending
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "need_more",
                "reply_voice": t(lang, "ask_booking_time_only"),
                "msg_out": t(lang, "ask_booking_time_only"),
                "lang": lang,
            }
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "need_more",
            "reply_voice": t(lang, "ask_booking_date"),
            "msg_out": t(lang, "ask_booking_date"),
            "lang": lang,
        }

    if c["state"] == STATE_AWAITING_TIME:
        service_item_current = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
        if is_short_ack_text(msg, lang):
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "need_more",
                "reply_voice": prompt_for_state(lang, c, pending, service_catalog),
                "msg_out": prompt_for_state(lang, c, pending, service_catalog),
                "lang": lang,
            }
        c, pending = remember_booking_service(c, pending, service_item_current, lang)

        if pending.get("awaiting_time_date_iso"):
            if date_only_dt_for_msg:
                pending["awaiting_time_date_iso"] = date_only_dt_for_msg.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
            base_day = parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip())
            time_window = parse_time_window(msg) or pending_time_window_tuple(pending)
            if time_window and base_day:
                pending["preferred_time_window"] = [time_window[0], time_window[1]]
                slots = find_first_n_slots_for_day_window(
                    calendar_id=settings["calendar_id"],
                    day_dt=base_day,
                    duration_min=service_duration_min(service_item_current),
                    work_start=settings["work_start"],
                    work_end=settings["work_end"],
                    window_start_hour=time_window[0],
                    window_end_hour=time_window[1],
                    limit=3,
                    business_rules=settings.get("business_rules"),
                    service_account_json=settings.get("service_account_json"),
                ) if calendar_ready else []
                if len(slots) >= 3:
                    pending = set_offered_slots(pending, slots[:3])
                    c["pending"] = pending
                    db_save_conversation(tenant_id, user_key, c)
                    return {
                        "status": "need_more",
                        "reply_voice": t(lang, "smart_slots_prompt", opt1=format_dt_short(slots[0]), opt2=format_dt_short(slots[1]), opt3=format_dt_short(slots[2])),
                        "msg_out": t(lang, "smart_slots_prompt", opt1=format_dt_short(slots[0]), opt2=format_dt_short(slots[1]), opt3=format_dt_short(slots[2])),
                        "lang": lang,
                    }
                if len(slots) >= 2:
                    pending = set_offered_slots(pending, slots[:2])
                    c["pending"] = pending
                    db_save_conversation(tenant_id, user_key, c)
                    return {
                        "status": "need_more",
                        "reply_voice": t(lang, "voice_options_prompt", opt1=format_dt_short(slots[0]), opt2=format_dt_short(slots[1])),
                        "msg_out": t(lang, "voice_options_prompt", opt1=format_dt_short(slots[0]), opt2=format_dt_short(slots[1])),
                        "lang": lang,
                    }
                if len(slots) == 1:
                    pending = set_offered_slots(pending, slots[:1])
                    pending["confirm_slot_iso"] = slots[0].isoformat()
                    c["pending"] = pending
                    c["state"] = STATE_AWAITING_CONFIRM
                    c["datetime_iso"] = slots[0].isoformat()
                    db_save_conversation(tenant_id, user_key, c)
                    return {
                        "status": "need_more",
                        "reply_voice": t(lang, "ask_booking_confirm", when=format_dt_short(slots[0]), service=pending.get("service_display") or ""),
                        "msg_out": t(lang, "ask_booking_confirm", when=format_dt_short(slots[0]), service=pending.get("service_display") or ""),
                        "lang": lang,
                    }
                db_save_conversation(tenant_id, user_key, c)
                return {
                    "status": "need_more",
                    "reply_voice": t(lang, "ask_booking_time_only"),
                    "msg_out": t(lang, "ask_booking_time_only"),
                    "lang": lang,
                }

        selected_iso = extract_slot_choice(msg, pending)
        if selected_iso:
            dt_sel = parse_dt_any_tz(selected_iso)
            if dt_sel:
                result = book_appointment_for_datetime(tenant_id, raw_phone, channel, lang, c, settings, service_catalog, dt_sel)
                db_save_conversation(tenant_id, user_key, c)
                return result

        dt_start = None
        natural_dt = parse_natural_datetime(msg, pending.get("awaiting_time_date_iso"))
        if natural_dt:
            dt_start = natural_dt
        elif explicit_time_present and pending.get("awaiting_time_date_iso"):
            dt_start = combine_date_with_explicit_time(pending.get("awaiting_time_date_iso"), msg)
        if not dt_start and msg:
            data = get_ai_data()
            dt_start = parse_dt_from_iso_or_fallback(data.get("datetime_iso"), data.get("time_text"), msg)
            extracted_name = normalize_name(data.get("name"))
            if extracted_name and not c.get("name"):
                c["name"] = extracted_name

        if not dt_start and pending.get("awaiting_time_date_iso"):
            time_window = parse_time_window(msg)
            base_day = parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip())
            if time_window and base_day:
                service_item = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
                slots = find_first_n_slots_for_day_window(
                    calendar_id=settings["calendar_id"],
                    day_dt=base_day,
                    duration_min=service_duration_min(service_item),
                    work_start=settings["work_start"],
                    work_end=settings["work_end"],
                    window_start_hour=time_window[0],
                    window_end_hour=time_window[1],
                    limit=3,
                    business_rules=settings.get("business_rules"),
                    service_account_json=settings.get("service_account_json"),
                ) if calendar_ready else []
                if len(slots) >= 3:
                    pending = set_offered_slots(pending, slots[:3])
                    c["pending"] = pending
                    db_save_conversation(tenant_id, user_key, c)
                    return {
                        "status": "need_more",
                        "reply_voice": t(lang, "smart_slots_prompt", opt1=format_dt_short(slots[0]), opt2=format_dt_short(slots[1]), opt3=format_dt_short(slots[2])),
                        "msg_out": t(lang, "smart_slots_prompt", opt1=format_dt_short(slots[0]), opt2=format_dt_short(slots[1]), opt3=format_dt_short(slots[2])),
                        "lang": lang,
                    }
                if len(slots) >= 2:
                    pending = set_offered_slots(pending, slots[:2])
                    c["pending"] = pending
                    db_save_conversation(tenant_id, user_key, c)
                    return {
                        "status": "need_more",
                        "reply_voice": t(lang, "voice_options_prompt", opt1=format_dt_short(slots[0]), opt2=format_dt_short(slots[1])),
                        "msg_out": t(lang, "voice_options_prompt", opt1=format_dt_short(slots[0]), opt2=format_dt_short(slots[1])),
                        "lang": lang,
                    }
                if len(slots) == 1:
                    pending = set_offered_slots(pending, slots[:1])
                    pending["confirm_slot_iso"] = slots[0].isoformat()
                    c["pending"] = pending
                    c["state"] = STATE_AWAITING_CONFIRM
                    c["datetime_iso"] = slots[0].isoformat()
                    db_save_conversation(tenant_id, user_key, c)
                    return {
                        "status": "need_more",
                        "reply_voice": t(lang, "ask_booking_confirm", when=format_dt_short(slots[0]), service=pending.get("service_display") or ""),
                        "msg_out": t(lang, "ask_booking_confirm", when=format_dt_short(slots[0]), service=pending.get("service_display") or ""),
                        "lang": lang,
                    }

        if dt_start:
            clear_offered_slots(pending)
            pending.pop("awaiting_time_date_iso", None)
            c["pending"] = pending or None
            result = book_appointment_for_datetime(tenant_id, raw_phone, channel, lang, c, settings, service_catalog, dt_start)
            db_save_conversation(tenant_id, user_key, c)
            return result

        if get_offered_slots(pending):
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "need_more",
                "reply_voice": t(lang, "invalid_time_choice") + " " + prompt_for_state(lang, c, pending, service_catalog),
                "msg_out": t(lang, "invalid_time_choice"),
                "lang": lang,
            }

        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "need_more",
            "reply_voice": t(lang, "ask_booking_time_only"),
            "msg_out": t(lang, "ask_booking_time_only"),
            "lang": lang,
        }

    if not active_flow and not c.get("service") and msg:
        direct_service_key = canonical_service_key_from_text(msg, service_aliases)
        service_item = get_service_item_by_key(service_catalog, direct_service_key) if direct_service_key else None
        data = None
        if not service_item and (llm_hint or {}).get("service"):
            service_item = get_service_item_by_key(service_catalog, llm_hint.get("service"))
        if not service_item:
            data = get_ai_data()
            extracted_service_key = apply_service_aliases(data.get("service"), service_aliases) or canonical_service_key_from_text(data.get("service"), service_aliases)
            service_item = get_service_item_by_key(service_catalog, extracted_service_key) or extract_service_from_text(data.get("service"), service_catalog, lang)
        name = normalize_name(data.get("name")) if data else None
        if service_item:
            c["service"] = str(service_item.get("key") or "").strip()
            pending = c.get("pending") or {}
            pending["service_display"] = service_display_name(service_item, lang)
            c["pending"] = pending
            c["state"] = STATE_AWAITING_DATE
            if name and not c.get("name"):
                c["name"] = name
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "need_more",
                "reply_voice": t(lang, "ask_booking_date"),
                "msg_out": t(lang, "ask_booking_date"),
                "lang": lang,
            }

    if msg and conversation_state(c) == STATE_AWAITING_CONFIRM:
        confirm_iso = str(pending.get("confirm_slot_iso") or c.get("datetime_iso") or "").strip()
        dt_confirm = parse_dt_any_tz(confirm_iso)
        if pending.get("pending_confirm_upsell") and dt_confirm:
            haircut_item = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
            beard_item = find_service_item_by_group(service_catalog, "beard")
            when_txt = format_dt_short(dt_confirm)
            llm_confirmation = (llm_hint or {}).get("confirmation")
            if is_yes_text(msg, lang) or llm_confirmation == "yes":
                pending["pending_confirm_upsell"] = False
                if beard_item:
                    pending["addon_service"] = str(beard_item.get("key") or "").strip()
                c["pending"] = pending
                db_save_conversation(tenant_id, user_key, c)
                reply_text = build_confirm_upsell_resolution(lang, when_txt, True, haircut_item, beard_item)
                return {"status": "need_more", "reply_voice": reply_text, "msg_out": reply_text, "lang": lang, "preserve_text": True}
            if is_no_text(msg, lang) or llm_confirmation == "no":
                pending["pending_confirm_upsell"] = False
                pending.pop("addon_service", None)
                c["pending"] = pending
                db_save_conversation(tenant_id, user_key, c)
                reply_text = build_confirm_upsell_resolution(lang, when_txt, False, haircut_item, beard_item)
                return {"status": "need_more", "reply_voice": reply_text, "msg_out": reply_text, "lang": lang, "preserve_text": True}
            if is_short_ack_text(msg, lang):
                pending["pending_confirm_upsell"] = False
                pending.pop("addon_service", None)
                c["pending"] = pending
                db_save_conversation(tenant_id, user_key, c)
                # treat generic ack as plain confirm path without addon
            else:
                db_save_conversation(tenant_id, user_key, c)
                return {"status": "need_more", "reply_voice": t(lang, "repeat_yes_no"), "msg_out": t(lang, "repeat_yes_no"), "lang": lang}

        if is_short_ack_text(msg, lang) and not is_yes_text(msg, lang):
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "need_more",
                "reply_voice": t(lang, "soft_clarify_confirm"),
                "msg_out": t(lang, "soft_clarify_confirm"),
                "lang": lang,
            }
        llm_confirmation = (llm_hint or {}).get("confirmation")
        if is_yes_text(msg, lang) or llm_confirmation == "yes":
            if not dt_confirm:
                c["state"] = STATE_AWAITING_TIME
                db_save_conversation(tenant_id, user_key, c)
                return {
                    "status": "need_more",
                    "reply_voice": prompt_for_state(lang, c, pending, service_catalog),
                    "msg_out": prompt_for_state(lang, c, pending, service_catalog),
                    "lang": lang,
                }
            result = book_appointment_for_datetime(tenant_id, raw_phone, channel, lang, c, settings, service_catalog, dt_confirm, require_confirmation=False)
            db_save_conversation(tenant_id, user_key, c)
            return result
        if is_no_text(msg, lang) or llm_confirmation == "no":
            pending.pop("confirm_slot_iso", None)
            pending.pop("pending_confirm_upsell", None)
            pending.pop("confirm_upsell_done", None)
            pending.pop("addon_service", None)
            c["pending"] = pending or {"booking_intent": True}
            c["datetime_iso"] = None
            c["state"] = STATE_AWAITING_TIME
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "need_more",
                "reply_voice": prompt_for_state(lang, c, c.get("pending") or {}, service_catalog),
                "msg_out": prompt_for_state(lang, c, c.get("pending") or {}, service_catalog),
                "lang": lang,
            }
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "need_more",
            "reply_voice": t(lang, "repeat_yes_no"),
            "msg_out": t(lang, "repeat_yes_no"),
            "lang": lang,
        }

    c = normalize_booking_state(c)
    db_save_conversation(tenant_id, user_key, c)
    fallback_status = "need_more" if is_active_booking_flow(c) else "info"
    fallback_reply = soft_clarify_for_state(lang, c, c.get("pending") or {}) if is_active_booking_flow(c) else t(lang, "unclear_reply")
    if not is_active_booking_flow(c) and llm_intent == "info" and llm_conf >= LLM_INTENT_MIN_CONFIDENCE and is_hours_question(msg):
        fallback_reply = t(lang, "hours_info", biz=settings["biz_name"], start=settings["work_start"], end=settings["work_end"])
    return {
        "status": fallback_status,
        "reply_voice": fallback_reply,
        "msg_out": fallback_reply,
        "lang": lang,
    }


# -------------------------
# TWILIO ENDPOINTS
# -------------------------
@app.post("/voice/incoming")
async def voice_incoming(request: Request):
    form = await request.form()
    to_num = str(form.get("To", ""))
    caller = normalize_voice_caller(str(form.get("From", "")))
    tenant = resolve_voice_tenant_for_incoming(to_num, caller)
    log_tenant_resolution("voice", to_num, tenant)
    if not tenant_is_resolved(tenant):
        vr = VoiceResponse()
        say_or_play(vr, t("lv", "service_unavailable_voice"), "lv")
        vr.hangup()
        return twiml(vr)
    biz = tenant_settings(tenant, "lv")["biz_name"]

    c = db_get_or_create_conversation(tenant["_id"], caller, "lv")
    lang = get_lang(c.get("lang")) if caller != "unknown" else "lv"

    vr = VoiceResponse()
    g = Gather(
        input="speech dtmf",
        action="/voice/language",
        method="POST",
        timeout=7,
        speech_timeout="auto",
        num_digits=1,
        language=stt_locale_for_lang(lang),
    )
    say_or_play(g, t(lang, "greeting", biz=biz), lang)
    vr.append(g)
    say_or_play(vr, t(lang, "voice_fallback"), lang)
    return twiml(vr)


@app.post("/voice/language")
async def voice_language(request: Request):
    form = await request.form()
    to_num = str(form.get("To", ""))
    caller = normalize_voice_caller(str(form.get("From", "")))
    speech = str(form.get("SpeechResult", "")).strip()
    digits = str(form.get("Digits", "")).strip()

    tenant = resolve_voice_tenant_for_incoming(to_num, caller)
    log_tenant_resolution("voice_language", to_num, tenant)
    if not tenant_is_resolved(tenant):
        vr = VoiceResponse()
        say_or_play(vr, t("lv", "service_unavailable_voice"), "lv")
        vr.hangup()
        return twiml(vr)
    c = db_get_or_create_conversation(tenant["_id"], caller, "lv")
    selected_lang = detect_language_choice(speech, digits) or get_lang(c.get("lang"))
    c["lang"] = selected_lang
    db_save_conversation(tenant["_id"], caller, c)

    vr = VoiceResponse()
    g = Gather(
        input="speech",
        action="/voice/intent",
        method="POST",
        timeout=7,
        speech_timeout="auto",
        language=stt_locale_for_lang(selected_lang),
    )
    say_or_play(g, t(selected_lang, "how_help"), selected_lang)
    vr.append(g)
    say_or_play(vr, t(selected_lang, "voice_fallback"), selected_lang)
    return twiml(vr)


@app.post("/voice/intent")
async def voice_intent(request: Request):
    form = await request.form()
    to_num = str(form.get("To", ""))
    caller = normalize_voice_caller(str(form.get("From", "")))
    speech = str(form.get("SpeechResult", "")).strip()

    tenant = resolve_voice_tenant_for_incoming(to_num, caller)
    log_tenant_resolution("voice_intent", to_num, tenant)
    if not tenant_is_resolved(tenant):
        vr = VoiceResponse()
        say_or_play(vr, t("lv", "service_unavailable_voice"), "lv")
        vr.hangup()
        return twiml(vr)
    c = db_get_or_create_conversation(tenant["_id"], caller, detect_language(speech))
    lang = resolve_reply_language(speech, c.get("lang") or detect_language(speech))
    result = handle_user_text_with_logging(tenant["_id"], caller, speech, "voice", lang)

    vr = VoiceResponse()
    say_or_play(vr, result["reply_voice"], result["lang"])
    if result["status"] in ("need_more", "reschedule_wait", "greeting", "identity", "info"):
        g = Gather(
            input="speech",
            action="/voice/intent",
            method="POST",
            timeout=7,
            speech_timeout="auto",
            language=stt_locale_for_lang(result["lang"]),
        )
        say_or_play(g, gather_followup_prompt(result), result["lang"])
        vr.append(g)
        say_or_play(vr, t(result["lang"], "voice_fallback"), result["lang"])
    else:
        vr.hangup()

    if result["status"] in ("booked", "busy", "cancelled") and caller != "unknown" and channel_supports_messaging("voice", caller):
        biz_name = tenant_settings(tenant, result["lang"])["biz_name"]
        send_message(caller, f"{biz_name}: {result['msg_out']}")

    return twiml(vr)


@app.post("/sms/incoming")
async def sms_incoming(request: Request):
    form = await request.form()
    to_num = str(form.get("To", ""))
    from_num = str(form.get("From", ""))
    body = str(form.get("Body", "")).strip()

    tenant = resolve_tenant_for_incoming(to_num)
    log_tenant_resolution("sms", to_num, tenant)
    if not tenant_is_resolved(tenant):
        send_message(from_num, t(detect_language(body), "service_unavailable_text"))
        return Response(status_code=204)
    result = handle_user_text_with_logging(
        tenant["_id"], from_num, body, "sms", detect_language(body)
    )
    biz = tenant_settings(tenant, result["lang"])["biz_name"]
    send_message(from_num, f"{biz}: {result['msg_out']}")
    return Response(status_code=204)


@app.post("/whatsapp/incoming")
async def whatsapp_incoming(request: Request):
    form = await request.form()
    to_num = str(form.get("To", "")).replace("whatsapp:", "")
    from_num = str(form.get("From", ""))
    body = str(form.get("Body", "")).strip()

    tenant = resolve_tenant_for_incoming(to_num)
    log_tenant_resolution("whatsapp", to_num, tenant)
    if not tenant_is_resolved(tenant):
        send_message(from_num, t(detect_language(body), "service_unavailable_text"))
        return Response(status_code=204)
    result = handle_user_text_with_logging(
        tenant["_id"], from_num, body, "whatsapp", detect_language(body)
    )
    biz = tenant_settings(tenant, result["lang"])["biz_name"]
    send_message(from_num, f"{biz}: {result['msg_out']}")
    return Response(status_code=204)



# -------------------------
# GOOGLE OAUTH ENDPOINTS (Phase 3 Foundation)
# -------------------------
@app.get("/google/connect")
def google_connect(tenant_id: str):
    if not oauth_ready():
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")
    tenant = get_tenant_or_404(tenant_id)
    tenant = sync_tenant_onboarding_state(tenant["_id"])
    if bool(tenant.get("onboarding_completed")):
        return RedirectResponse(url=f"/dashboard?tenant_id={tenant['_id']}")
    if tenant_google_connected_effective(tenant):
        if str(tenant.get("calendar_id") or "").strip():
            return RedirectResponse(url=f"/dashboard?tenant_id={tenant['_id']}")
        return RedirectResponse(url=f"/google/calendars/ui?tenant_id={tenant['_id']}")
    auth_url = build_google_oauth_url(tenant["_id"])
    return RedirectResponse(url=auth_url)

@app.get("/google/callback")
def google_callback(code: str = "", state: str = "", error: str = ""):
    if not oauth_ready():
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")
    state_data = parse_google_oauth_state(state)
    tenant_id = str(state_data.get("tenant_id") or "").strip()
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Invalid state")
    get_tenant_or_404(tenant_id)

    if error:
        return RedirectResponse(url=f"/google/calendars/ui?tenant_id={tenant_id}&oauth_error={requests.utils.quote(error)}")
    if not code:
        return RedirectResponse(url=f"/google/calendars/ui?tenant_id={tenant_id}&oauth_error=missing_code")

    token_data = exchange_google_code_for_tokens(code)
    access_token = str(token_data.get("access_token") or "").strip()
    refresh_token = str(token_data.get("refresh_token") or "").strip() or None
    if not access_token:
        return RedirectResponse(url=f"/google/calendars/ui?tenant_id={tenant_id}&oauth_error=token_exchange_failed")

    userinfo = fetch_google_userinfo(access_token)
    google_email = str(userinfo.get("email") or "").strip() or None

    upsert_tenant_google_account(
        tenant_id=tenant_id,
        google_email=google_email,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expiry=token_expiry_from_google(token_data.get("expires_in")),
        scope=str(token_data.get("scope") or GOOGLE_OAUTH_SCOPE).strip() or GOOGLE_OAUTH_SCOPE,
    )

    mark_tenant_google_connected(tenant_id, True, owner_email=google_email)

    calendars = fetch_google_calendar_list(access_token)
    chosen_calendar_id = google_calendar_choice(calendars)
    if chosen_calendar_id:
        select_tenant_calendar_id(tenant_id, chosen_calendar_id)
        tenant = sync_tenant_onboarding_state(tenant_id)
        if bool(tenant.get("onboarding_completed")):
            return RedirectResponse(url=f"/dashboard?tenant_id={tenant_id}&google=connected&calendar=selected")

    sync_tenant_onboarding_state(tenant_id)
    return RedirectResponse(url=f"/google/calendars/ui?tenant_id={tenant_id}&google=connected")

@app.get("/google/calendars")
def google_calendars(tenant_id: str):
    tenant = get_tenant_or_404(tenant_id)
    acct = get_tenant_google_account(tenant["_id"])
    access_token = str(acct.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=404, detail="Google account is not connected")
    calendars = fetch_google_calendar_list(access_token)
    simplified = [
        {
            "id": c.get("id"),
            "summary": c.get("summary"),
            "primary": c.get("primary", False),
            "timeZone": c.get("timeZone"),
        }
        for c in calendars
        if str(c.get("id") or "").strip()
    ]
    tenant = sync_tenant_onboarding_state(tenant["_id"])
    return {"tenant_id": tenant["_id"], "items": simplified, "onboarding": onboarding_status_payload(tenant)}

@app.get("/google/calendars/ui", response_class=HTMLResponse)
def google_calendars_ui(tenant_id: str, google: str = "", oauth_error: str = ""):
    tenant = get_tenant_or_404(tenant_id)
    status = onboarding_status_payload(sync_tenant_onboarding_state(tenant["_id"]))
    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Select Google Calendar</title>
<style>
body {{ font-family: Arial, sans-serif; background:#f6f7fb; color:#111827; margin:0; padding:24px; }}
.wrap {{ max-width: 880px; margin:0 auto; }}
.card {{ background:#fff; border:1px solid #e5e7eb; border-radius:18px; padding:22px; box-shadow: 0 10px 28px rgba(15,23,42,.06); margin-bottom:16px; }}
button {{ border:0; background:#111827; color:#fff; padding:10px 14px; border-radius:12px; cursor:pointer; font-size:14px; }}
button.secondary {{ background:#fff; color:#111827; border:1px solid #d1d5db; }}
.row {{ display:flex; justify-content:space-between; gap:12px; padding:12px 0; border-bottom:1px solid #e5e7eb; align-items:center; }}
.small {{ font-size:12px; color:#6b7280; }}
.ok {{ color:#065f46; }}
.err {{ color:#991b1b; }}
.hidden {{ display:none; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h2>Google Calendar connection</h2>
    <p>Business: <strong>{tenant.get('business_name') or tenant['_id']}</strong></p>
    <p class="small">Tenant ID: {tenant['_id']}</p>
    <p id="status_line" class="small {'err' if oauth_error else 'ok' if google else ''}">{'OAuth error: ' + oauth_error if oauth_error else ('Google account connected. Select the calendar for Repliq.' if google or status.get('google_connected') else 'Connect Google to continue.')}</p>
    <div style="margin-top:14px; display:flex; gap:10px; flex-wrap:wrap;">
      <a href="/google/connect?tenant_id={tenant['_id']}"><button>Connect Google</button></a>
      <a href="/dashboard?tenant_id={tenant['_id']}"><button class="secondary">Open dashboard</button></a>
      <a href="/onboarding/ui?tenant_id={tenant['_id']}"><button class="secondary">Open onboarding</button></a>
    </div>
  </div>

  <div class="card">
    <h3>Calendars</h3>
    <div id="loading" class="small">Loading calendars...</div>
    <div id="calendar_list"></div>
    <div id="done" class="small ok hidden">Calendar saved. Redirecting to dashboard...</div>
  </div>
</div>
<script>
const tenantId = {json.dumps(tenant['_id'])};
async function loadCalendars() {{
  const loading = document.getElementById('loading');
  const list = document.getElementById('calendar_list');
  try {{
    const r = await fetch('/google/calendars?tenant_id=' + encodeURIComponent(tenantId));
    const data = await r.json();
    if (!r.ok) {{
      loading.className = 'small err';
      loading.textContent = data.detail || 'Could not load calendars';
      return;
    }}
    loading.className = 'small';
    loading.textContent = data.items && data.items.length ? 'Select the calendar Repliq should use:' : 'No calendars available for this account.';
    list.innerHTML = '';
    (data.items || []).forEach(item => {{
      const row = document.createElement('div');
      row.className = 'row';
      const left = document.createElement('div');
      left.innerHTML = '<div><strong>' + (item.summary || item.id) + '</strong>' + (item.primary ? ' <span class="small ok">(primary)</span>' : '') + '</div><div class="small">' + (item.id || '') + (item.timeZone ? ' · ' + item.timeZone : '') + '</div>';
      const btn = document.createElement('button');
      btn.textContent = 'Use this calendar';
      btn.onclick = async () => {{
        btn.disabled = true;
        const res = await fetch('/google/select_calendar', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ tenant_id: tenantId, calendar_id: item.id }})
        }});
        const payload = await res.json();
        if (!res.ok) {{
          btn.disabled = false;
          alert(payload.detail || 'Could not save calendar');
          return;
        }}
        document.getElementById('done').classList.remove('hidden');
        window.location = '/dashboard?tenant_id=' + encodeURIComponent(tenantId);
      }};
      row.appendChild(left);
      row.appendChild(btn);
      list.appendChild(row);
    }});
  }} catch (e) {{
    loading.className = 'small err';
    loading.textContent = 'Could not load calendars';
  }}
}}
loadCalendars();
</script>
</body>
</html>
    """
    return HTMLResponse(content=html)

@app.post("/google/select_calendar")
async def google_select_calendar(request: Request):
    data = await request.json()
    tenant_id = str(data.get("tenant_id") or "").strip()
    calendar_id = str(data.get("calendar_id") or "").strip()
    if not tenant_id or not calendar_id:
        raise HTTPException(status_code=400, detail="tenant_id and calendar_id are required")
    get_tenant_or_404(tenant_id)
    select_tenant_calendar_id(tenant_id, calendar_id)
    tenant = sync_tenant_onboarding_state(tenant_id)
    return {
        "status": "ok",
        "tenant_id": tenant_id,
        "calendar_id": calendar_id,
        "onboarding": onboarding_status_payload(tenant),
        "links": onboarding_links_payload(tenant_id),
    }


# -------------------------
# BROWSER SDK TOKEN
# -------------------------
@app.get("/voice/token")
def get_voice_token(client_id: str = "default", tenant_id: str = ""):
    if not (
        TWILIO_ACCOUNT_SID
        and TWILIO_API_KEY_SID
        and TWILIO_API_KEY_SECRET
        and TWILIO_TWIML_APP_SID
    ):
        raise HTTPException(status_code=500, detail="Twilio Voice SDK config missing")

    clean_client_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", (client_id or "default")).strip("_") or "default"
    clean_tenant_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", (tenant_id or "")).strip("_")
    identity = f"tenant__{clean_tenant_id}__{clean_client_id}" if clean_tenant_id else clean_client_id

    token = AccessToken(
        TWILIO_ACCOUNT_SID,
        TWILIO_API_KEY_SID,
        TWILIO_API_KEY_SECRET,
        identity=identity,
    )
    grant = VoiceGrant(
        outgoing_application_sid=TWILIO_TWIML_APP_SID, incoming_allow=True
    )
    token.add_grant(grant)
    return {"token": token.to_jwt(), "identity": identity, "tenant_id": clean_tenant_id or None}


@app.on_event("startup")
def _startup():
    ensure_tenant_row(TENANT_ID_DEFAULT)
    ensure_call_logs_table()
    ensure_phone_routes_table()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "tz": str(TZ),
        "test_tenant_id": TEST_TENANT_ID or None,
        "allow_default_tenant_fallback": ALLOW_DEFAULT_TENANT_FALLBACK,
        "twilio_validate_signature": TWILIO_VALIDATE_SIGNATURE,
        "google_oauth_ready": oauth_ready(),
    }



# =========================
# Tenant Configuration Hardening (Phase 2.7)
# =========================

REQUIRED_TENANT_FIELDS = [
    "calendar_id",
    "timezone",
    "work_start",
    "work_end"
]


# =========================
# Phase 3 – SaaS Tenant Lifecycle Fields
# =========================

SAAS_TENANT_FIELDS = {
    "onboarding_completed": False,
    "google_connected": False,
    "subscription_status": "trial",
    "plan": "starter",
    "owner_email": ""
}

def normalize_tenant_saas_fields(tenant: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure SaaS lifecycle fields exist so older tenants don't break."""
    if not tenant:
        return tenant
    for k, v in SAAS_TENANT_FIELDS.items():
        if k not in tenant or tenant.get(k) is None:
            tenant[k] = v
    return tenant


def tenant_service_account_json_value(tenant: Optional[Dict[str, Any]]) -> str:
    tenant = tenant or {}
    for key in ("service_account_json", "google_service_account_json"):
        val = str(tenant.get(key) or "").strip()
        if val:
            return val
    return GOOGLE_SERVICE_ACCOUNT_JSON or ""


def tenant_has_service_account_json(tenant: Optional[Dict[str, Any]]) -> bool:
    return bool(tenant_service_account_json_value(tenant))


def tenant_runtime_missing_items(tenant: Dict[str, Any]) -> List[str]:
    tenant = normalize_tenant_saas_fields(tenant or {})
    missing: List[str] = []
    if not str(tenant.get("business_name") or "").strip():
        missing.append("business_name")
    if not str(tenant.get("timezone") or "").strip():
        missing.append("timezone")
    if not str(tenant.get("work_start") or "").strip():
        missing.append("work_start")
    if not str(tenant.get("work_end") or "").strip():
        missing.append("work_end")
    if not str(tenant.get("calendar_id") or "").strip():
        missing.append("calendar_id")
    if not tenant_has_service_account_json(tenant):
        missing.append("service_account_json")
    catalog = tenant_service_catalog(tenant)
    if not catalog:
        missing.append("service_catalog")
    return missing


def tenant_runtime_ready(tenant: Dict[str, Any]) -> bool:
    return len(tenant_runtime_missing_items(tenant)) == 0


def log_tenant_runtime_validation(tenant: Dict[str, Any]) -> None:
    missing = tenant_runtime_missing_items(tenant)
    if missing:
        logger.error(
            "tenant_runtime_invalid tenant_id=%s missing=%s",
            tenant.get("_id") or tenant.get("id"),
            ",".join(missing),
        )


def validate_tenant_config(tenant: dict):
    missing = []
    for f in REQUIRED_TENANT_FIELDS:
        if not tenant.get(f):
            missing.append(f)
    for f in tenant_runtime_missing_items(tenant):
        if f not in missing:
            missing.append(f)

    if missing:
        logger.error(f"tenant_config_invalid tenant_id={tenant.get('id') or tenant.get('_id')} missing={missing}")
        raise Exception(f"Tenant configuration invalid: missing {missing}")

    return True


def safe_calendar_check(tenant: dict):
    try:
        if not tenant.get("calendar_id"):
            raise Exception("calendar_id missing")

        return True

    except Exception as e:
        logger.error(f"calendar_config_error tenant_id={tenant.get('id')} error={e}")
        raise



# =========================
# SAAS ONBOARDING (Phase 3 Step 1)
# =========================

from fastapi import Body


def default_onboarding_services(language_value: str, business_type: str = "barbershop") -> Dict[str, str]:
    business_type = (business_type or "barbershop").strip().lower()
    if business_type == "clinic":
        return {
            "lv": "konsultācija",
            "ru": "консультация",
            "en": "consultation",
        }
    if business_type == "salon":
        return {
            "lv": "matu griezums",
            "ru": "стрижка",
            "en": "haircut",
        }
    return {
        "lv": "vīriešu frizūra, bārda",
        "ru": "мужская стрижка, борода",
        "en": "men's haircut, beard trim",
    }


def default_onboarding_service_catalog(business_type: str = "barbershop") -> List[Dict[str, Any]]:
    business_type = (business_type or "barbershop").strip().lower()
    if business_type == "clinic":
        return [{
            "key": "consultation",
            "name_lv": "konsultācija",
            "name_ru": "консультация",
            "name_en": "consultation",
            "duration_min": 30,
            "aliases_lv": ["konsultācija"],
            "aliases_ru": ["консультация"],
            "aliases_en": ["consultation"],
        }]
    return [
        {
            "key": "mens_haircut",
            "name_lv": "vīriešu frizūra",
            "name_ru": "мужская стрижка",
            "name_en": "men's haircut",
            "duration_min": 30,
            "aliases_lv": ["vīriešu frizūra", "matu griezums", "frizūra"],
            "aliases_ru": ["мужская стрижка", "стрижка", "подстричься"],
            "aliases_en": ["men's haircut", "haircut"],
        },
        {
            "key": "beard_trim",
            "name_lv": "bārda",
            "name_ru": "борода",
            "name_en": "beard trim",
            "duration_min": 20,
            "aliases_lv": ["bārda", "bārdas korekcija"],
            "aliases_ru": ["борода", "подровнять бороду"],
            "aliases_en": ["beard trim", "beard"],
        },
    ]


def onboarding_links_payload(tenant_id: str) -> Dict[str, str]:
    base = SERVER_BASE_URL or ""
    return {
        "dashboard_url": f"{base}/dashboard?tenant_id={tenant_id}",
        "config_ui_url": f"{base}/tenant/config/ui?tenant_id={tenant_id}",
        "config_json_url": f"{base}/tenant/config?tenant_id={tenant_id}",
        "routes_url": f"{base}/tenant/routes?tenant_id={tenant_id}",
        "onboarding_status_url": f"{base}/onboarding/status?tenant_id={tenant_id}",
        "google_connect_url": f"{base}/google/connect?tenant_id={tenant_id}",
        "google_calendars_ui_url": f"{base}/google/calendars/ui?tenant_id={tenant_id}",
    }


def onboarding_status_payload(tenant: Dict[str, Any]) -> Dict[str, Any]:
    tenant = normalize_tenant_saas_fields(tenant or {})
    tenant_id = str(tenant.get("_id") or tenant.get("id") or "").strip()
    calendar_id = str(tenant.get("calendar_id") or "").strip()
    google_connected = tenant_google_connected_effective(tenant)
    onboarding_completed = bool(tenant.get("onboarding_completed"))
    calendar_selected = bool(calendar_id)
    phone_number = normalize_incoming_to_number(tenant.get("phone_number") or "")

    next_step = "create_tenant"
    if tenant_id:
        next_step = "connect_google"
    if google_connected:
        next_step = "select_calendar"
    if google_connected and calendar_selected:
        next_step = "finish"
    if onboarding_completed:
        next_step = "done"

    return {
        "tenant_id": tenant_id or None,
        "business_name": tenant.get("business_name"),
        "owner_email": tenant.get("owner_email"),
        "phone_number": phone_number or None,
        "google_connected": google_connected,
        "calendar_selected": calendar_selected,
        "calendar_id": calendar_id or None,
        "onboarding_completed": onboarding_completed,
        "subscription_status": tenant.get("subscription_status"),
        "plan": tenant.get("plan"),
        "next_step": next_step,
    }


PLAN_CATALOG = {
    "starter": {
        "dialogs_per_month": 300,
        "llm_calls_per_month": 0,
        "llm_mode": "off",
        "includes_advanced_ai": False,
    },
    "pro": {
        "dialogs_per_month": 1000,
        "llm_calls_per_month": 800,
        "llm_mode": "smart",
        "includes_advanced_ai": True,
    },
    "ai": {
        "dialogs_per_month": 2000,
        "llm_calls_per_month": 2500,
        "llm_mode": "full",
        "includes_advanced_ai": True,
    },
    "business": {
        "dialogs_per_month": 3000,
        "llm_calls_per_month": 5000,
        "llm_mode": "full",
        "includes_advanced_ai": True,
    },
}

def tenant_plan_meta(tenant: Dict[str, Any]) -> Dict[str, Any]:
    tenant = normalize_tenant_saas_fields(tenant or {})
    plan = str(tenant.get("plan") or "starter").strip().lower()
    defaults = PLAN_CATALOG.get(plan, PLAN_CATALOG["starter"])
    return {
        "plan": plan,
        "subscription_status": str(tenant.get("subscription_status") or "trial").strip().lower() or "trial",
        "limits": dict(defaults),
    }


def tenant_missing_setup_items(tenant: Dict[str, Any]) -> List[str]:
    tenant = normalize_tenant_saas_fields(tenant or {})
    missing: List[str] = []
    if not str(tenant.get("business_name") or "").strip():
        missing.append("business_name")
    if not str(tenant.get("timezone") or "").strip():
        missing.append("timezone")
    if not str(tenant.get("work_start") or "").strip():
        missing.append("work_start")
    if not str(tenant.get("work_end") or "").strip():
        missing.append("work_end")
    if not tenant_google_connected_effective(tenant):
        missing.append("google_connected")
    if not str(tenant.get("calendar_id") or "").strip():
        missing.append("calendar_id")
    if not tenant_has_service_account_json(tenant):
        missing.append("service_account_json")
    if not tenant_service_catalog(tenant):
        missing.append("service_catalog")
    return missing


def tenant_ready_status_payload(tenant: Dict[str, Any]) -> Dict[str, Any]:
    tenant = normalize_tenant_saas_fields(tenant or {})
    missing = tenant_missing_setup_items(tenant)
    onboarding = onboarding_status_payload(tenant)
    return {
        "tenant_id": onboarding.get("tenant_id"),
        "ready": len(missing) == 0,
        "missing": missing,
        "next_step": onboarding.get("next_step"),
        "google_connected": onboarding.get("google_connected"),
        "calendar_selected": onboarding.get("calendar_selected"),
        "onboarding_completed": onboarding.get("onboarding_completed"),
        "has_service_account_json": tenant_has_service_account_json(tenant),
        "has_service_catalog": bool(tenant_service_catalog(tenant)),
    }


def tenant_phone_routes_count(tenant_id: str) -> int:
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) FROM phone_routes WHERE tenant_id=:tenant_id"),
                {"tenant_id": tenant_id},
            ).fetchone()
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def tenant_overview_payload(tenant: Dict[str, Any]) -> Dict[str, Any]:
    tenant = normalize_tenant_saas_fields(tenant or {})
    tenant_id = str(tenant.get("_id") or tenant.get("id") or "").strip()
    return {
        "tenant": _jsonable_tenant_view(tenant),
        "onboarding": onboarding_status_payload(tenant),
        "readiness": tenant_ready_status_payload(tenant),
        "plan_meta": tenant_plan_meta(tenant),
        "links": onboarding_links_payload(tenant_id),
        "phone_routes_count": tenant_phone_routes_count(tenant_id) if tenant_id else 0,
    }


@app.get("/onboarding/status")
def onboarding_status(tenant_id: str):
    tenant = sync_tenant_onboarding_state((tenant_id or "").strip())
    return onboarding_status_payload(tenant)


@app.post("/onboarding/finish")
def onboarding_finish(payload: dict = Body(...)):
    tenant_id = str(payload.get("tenant_id") or "").strip()
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id required")

    tenant = get_tenant_or_404(tenant_id)
    tenant = sync_tenant_onboarding_state(tenant_id)

    missing = []
    if not tenant_google_connected_effective(tenant):
        missing.append("google_connected")
    if not str(tenant.get("calendar_id") or "").strip():
        missing.append("calendar_id")

    if missing:
        return {
            "status": "incomplete",
            "tenant_id": tenant_id,
            "missing": missing,
            "onboarding": onboarding_status_payload(tenant),
        }

    tenant = sync_tenant_onboarding_state(tenant_id)
    return {
        "status": "ok",
        "tenant_id": tenant_id,
        "onboarding": onboarding_status_payload(tenant),
    }


@app.get("/tenant/status")
def tenant_status(tenant_id: str = TENANT_ID_DEFAULT):
    tenant = get_tenant_or_404((tenant_id or "").strip() or TENANT_ID_DEFAULT)
    tenant = sync_tenant_onboarding_state(tenant["_id"])
    return tenant_ready_status_payload(tenant)


@app.get("/tenant/overview")
def tenant_overview(tenant_id: str = TENANT_ID_DEFAULT):
    tenant = get_tenant_or_404((tenant_id or "").strip() or TENANT_ID_DEFAULT)
    tenant = sync_tenant_onboarding_state(tenant["_id"])
    return tenant_overview_payload(tenant)

@app.get("/onboarding/ui", response_class=HTMLResponse)
def onboarding_ui(tenant_id: str = ""):
    tenant_id = (tenant_id or "").strip()
    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Repliq Onboarding</title>
<style>
body {{ font-family: Arial, sans-serif; background:#f6f7fb; color:#111827; margin:0; padding:24px; }}
.wrap {{ max-width: 980px; margin:0 auto; }}
.hero {{ margin-bottom:18px; }}
.card {{ background:#fff; border:1px solid #e5e7eb; border-radius:18px; padding:22px; box-shadow: 0 10px 28px rgba(15,23,42,.06); margin-bottom:16px; }}
h1,h2,h3 {{ margin:0 0 12px 0; }}
p {{ margin:0; color:#4b5563; line-height:1.5; }}
.grid {{ display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:14px; }}
label {{ display:block; font-size:14px; color:#374151; margin-bottom:6px; }}
input, select {{ width:100%; box-sizing:border-box; border:1px solid #d1d5db; border-radius:12px; padding:12px 14px; font-size:14px; background:#fff; }}
button {{ border:0; background:#111827; color:#fff; padding:12px 18px; border-radius:12px; cursor:pointer; font-size:14px; }}
button.secondary {{ background:#fff; color:#111827; border:1px solid #d1d5db; }}
.actions {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:16px; }}
.small {{ font-size:12px; color:#6b7280; }}
.ok {{ color:#065f46; }}
.err {{ color:#991b1b; white-space:pre-wrap; }}
.kpis {{ display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:12px; margin-top:14px; }}
.kpi {{ background:#fafafa; border:1px solid #e5e7eb; border-radius:14px; padding:14px; }}
.kpi .num {{ font-size:22px; font-weight:700; margin-top:6px; }}
.hidden {{ display:none; }}
ul.links {{ margin:8px 0 0 0; padding-left:18px; }}
ul.links li {{ margin:6px 0; }}
.code {{ background:#f9fafb; border:1px solid #e5e7eb; border-radius:12px; padding:12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12px; overflow:auto; }}
@media (max-width: 768px) {{ .grid, .kpis {{ grid-template-columns: 1fr; }} body {{ padding:16px; }} }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <h1>Create new business</h1>
    <p>Quick SaaS onboarding for Repliq. Fill in the business details, create the tenant, then continue with Google Calendar connection.</p>
  </div>

  <div class="card">
    <h2>Business setup</h2>
    <div class="grid">
      <div><label>Business name</label><input id="business_name" placeholder="Barbershop Riga"/></div>
      <div><label>Owner email (optional)</label><input id="owner_email" placeholder="owner@business.com"/></div>
      <div><label>Phone number (optional)</label><input id="phone_number" placeholder="+37120000000"/></div>
      <div><label>Business type</label>
        <select id="business_type">
          <option value="barbershop">barbershop</option>
          <option value="salon">salon</option>
          <option value="clinic">clinic</option>
        </select>
      </div>
      <div><label>Language</label>
        <select id="language">
          <option value="lv">lv</option>
          <option value="ru">ru</option>
          <option value="en">en</option>
        </select>
      </div>
      <div><label>Timezone</label><input id="timezone" value="Europe/Riga"/></div>
      <div><label>Work start</label><input id="work_start" value="09:00"/></div>
      <div><label>Work end</label><input id="work_end" value="18:00"/></div>
    </div>
    <div class="actions">
      <button onclick="createTenant()">Create business</button>
      <button class="secondary" onclick="openTenantConfig()">Open tenant config</button>
      <span id="create_status" class="small"></span>
    </div>
    <div class="small">This page calls <code>POST /tenant/create</code> and returns ready-to-use links for the new tenant.</div>
  </div>

  <div class="card hidden" id="result_card">
    <h2>Business created</h2>
    <p id="result_sub">Your new tenant is ready.</p>
    <div class="kpis">
      <div class="kpi"><div>Tenant ID</div><div class="num" id="k_tenant">-</div></div>
      <div class="kpi"><div>Google status</div><div class="num" id="k_google">-</div></div>
      <div class="kpi"><div>Next step</div><div class="num" id="k_next">-</div></div>
    </div>
    <h3 style="margin-top:18px">Quick links</h3>
    <ul class="links">
      <li><a id="r_dashboard" href="#">Dashboard</a></li>
      <li><a id="r_config_ui" href="#">Tenant config UI</a></li>
      <li><a id="r_config_json" href="#">Tenant config JSON</a></li>
      <li><a id="r_routes" href="#">Phone routes</a></li>
      <li><a id="r_status" href="#">Onboarding status</a></li>
      <li><a id="r_google" href="#">Connect Google Calendar</a></li>
      <li><a id="r_calendars_ui" href="#">Select Google Calendar</a></li>
    </ul>
    <div class="actions">
      <button onclick="openNewDashboard()">Open dashboard</button>
      <button class="secondary" onclick="copyTenantId()">Copy tenant_id</button>
    </div>
    <div class="small" style="margin-top:10px">Raw response</div>
    <div class="code" id="raw_response"></div>
  </div>
</div>

<script>
let latestResponse = null;
function currentTenantId() {{
  return document.getElementById('tenant_id_prefill') ? document.getElementById('tenant_id_prefill').value.trim() : '';
}}
function fillResult(data) {{
  latestResponse = data;
  document.getElementById('result_card').classList.remove('hidden');
  document.getElementById('k_tenant').textContent = data.tenant_id || '-';
  document.getElementById('k_google').textContent = (data.onboarding && data.onboarding.google_connected) ? 'connected' : 'pending';
  document.getElementById('k_next').textContent = (data.onboarding && data.onboarding.next_step) || '-';
  document.getElementById('result_sub').textContent = `Business “${{data.business_name || ''}}” is ready. Next step: connect Google Calendar and confirm the working calendar.`;
  const links = data.links || {{}};
  document.getElementById('r_dashboard').href = links.dashboard_url || '#';
  document.getElementById('r_config_ui').href = links.config_ui_url || '#';
  document.getElementById('r_config_json').href = links.config_json_url || '#';
  document.getElementById('r_routes').href = links.routes_url || '#';
  document.getElementById('r_status').href = links.onboarding_status_url || '#';
  document.getElementById('r_google').href = links.google_connect_url || '#';
  document.getElementById('r_calendars_ui').href = links.google_calendars_ui_url || '#';
  document.getElementById('raw_response').textContent = JSON.stringify(data, null, 2);
}}
async function createTenant() {{
  const payload = {{
    business_name: document.getElementById('business_name').value.trim(),
    owner_email: document.getElementById('owner_email').value.trim() || null,
    phone_number: document.getElementById('phone_number').value.trim() || null,
    business_type: document.getElementById('business_type').value,
    language: document.getElementById('language').value,
    timezone: document.getElementById('timezone').value.trim() || 'Europe/Riga',
    work_start: document.getElementById('work_start').value.trim() || '09:00',
    work_end: document.getElementById('work_end').value.trim() || '18:00'
  }};
  const st = document.getElementById('create_status');
  if (!payload.business_name) {{
    st.className = 'small err';
    st.textContent = 'business_name is required';
    return;
  }}
  st.className = 'small';
  st.textContent = 'Creating...';
  const r = await fetch('/tenant/create', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(payload)
  }});
  const data = await r.json();
  if (r.ok) {{
    st.className = 'small ok';
    st.textContent = 'Created';
    fillResult(data);
  }} else {{
    st.className = 'small err';
    st.textContent = data.detail || JSON.stringify(data, null, 2);
  }}
}}
function openNewDashboard() {{
  if (latestResponse && latestResponse.links && latestResponse.links.dashboard_url) {{
    window.location = latestResponse.links.dashboard_url;
  }}
}}
function openTenantConfig() {{
  const tid = (latestResponse && latestResponse.tenant_id) || '{tenant_id}';
  if (!tid) return;
  window.location = '/tenant/config/ui?tenant_id=' + encodeURIComponent(tid);
}}
async function copyTenantId() {{
  if (!latestResponse || !latestResponse.tenant_id) return;
  try {{
    await navigator.clipboard.writeText(latestResponse.tenant_id);
  }} catch (e) {{}}
}}
</script>
</body>
</html>
    """
    return HTMLResponse(content=html)


@app.post("/onboarding/create_tenant")
@app.post("/tenant/create")
def onboarding_create_tenant(payload: dict = Body(...)):
    business_name = (payload.get("business_name") or "").strip()
    owner_email = (payload.get("owner_email") or "").strip()
    phone_number = normalize_incoming_to_number(payload.get("phone_number") or "")
    business_type = (payload.get("business_type") or "barbershop").strip()
    timezone_value = (payload.get("timezone") or "Europe/Riga").strip()
    language_value = get_lang((payload.get("language") or "lv").strip())
    work_start_value = str(payload.get("work_start") or WORK_START_HHMM_DEFAULT).strip()
    work_end_value = str(payload.get("work_end") or WORK_END_HHMM_DEFAULT).strip()
    min_notice_minutes = _safe_int(payload.get("min_notice_minutes"), 0)
    buffer_minutes = _safe_int(payload.get("buffer_minutes"), 0)

    if not business_name:
        raise HTTPException(status_code=400, detail="business_name required")

    tenant_id = re.sub(r"[^a-zA-Z0-9_]+", "_", business_name.lower()).strip("_")
    if not tenant_id:
        tenant_id = "tenant_" + uuid.uuid4().hex[:8]
    tenant_id = tenant_id + "_" + uuid.uuid4().hex[:4]

    cols = tenants_columns()
    col_names = {c["name"] for c in cols}
    services_defaults = default_onboarding_services(language_value, business_type)
    weekly_hours = default_weekly_hours(work_start_value, work_end_value)
    service_catalog = default_onboarding_service_catalog(business_type)
    business_memory_defaults = default_business_memory_payload(business_type)

    fields = {
        "id": tenant_id,
        "tenant_id": tenant_id,
        "business_name": business_name,
        "owner_email": owner_email,
        "status": "active",
        "subscription_status": "trial",
        "client_status": "trial",
        "google_connected": False,
        "onboarding_completed": False,
        "business_type": business_type,
        "language": language_value,
        "timezone": timezone_value,
        "phone_number": phone_number or None,
        "plan": "starter",
        "work_start": work_start_value,
        "work_end": work_end_value,
        "services_lv": str(payload.get("services_lv") or services_defaults["lv"]),
        "services_ru": str(payload.get("services_ru") or services_defaults["ru"]),
        "services_en": str(payload.get("services_en") or services_defaults["en"]),
        "weekly_hours_json": json.dumps(payload.get("weekly_hours_json") or weekly_hours, ensure_ascii=False),
        "breaks_json": json.dumps(payload.get("breaks_json") or {}, ensure_ascii=False),
        "days_off_json": json.dumps(payload.get("days_off_json") or [], ensure_ascii=False),
        "holidays_json": json.dumps(payload.get("holidays_json") or [], ensure_ascii=False),
        "min_notice_minutes": min_notice_minutes,
        "buffer_minutes": buffer_minutes,
        "service_catalog_json": json.dumps(payload.get("service_catalog_json") or service_catalog, ensure_ascii=False),
        "service_catalog": json.dumps(payload.get("service_catalog_json") or service_catalog, ensure_ascii=False),
        "service_account_json": str(payload.get("service_account_json") or "").strip() or None,
        "business_memory_lv": str(payload.get("business_memory_lv") or business_memory_defaults["lv"]),
        "business_memory_ru": str(payload.get("business_memory_ru") or business_memory_defaults["ru"]),
        "business_memory_en": str(payload.get("business_memory_en") or business_memory_defaults["en"]),
    }

    insert_cols = []
    insert_vals: Dict[str, Any] = {}
    for k, v in fields.items():
        if k in col_names:
            insert_cols.append(k)
            insert_vals[k] = v

    if not insert_cols:
        raise HTTPException(status_code=500, detail="tenants schema mismatch")

    sql_cols = ", ".join(insert_cols)
    sql_params = ", ".join([f":{c}" for c in insert_cols])

    with engine.begin() as conn:
        conn.execute(text(f"INSERT INTO tenants ({sql_cols}) VALUES ({sql_params})"), insert_vals)

    if phone_number:
        upsert_phone_route(phone_number, tenant_id)

    tenant = get_tenant(tenant_id)
    return {
        "status": "ok",
        "tenant_id": tenant_id,
        "business_name": business_name,
        "phone_number": phone_number or None,
        "language": language_value,
        "timezone": timezone_value,
        "onboarding": onboarding_status_payload(tenant),
        "readiness": tenant_ready_status_payload(tenant),
        "plan_meta": tenant_plan_meta(tenant),
        "links": onboarding_links_payload(tenant_id),
    }


# =========================
# DASHBOARD MVP (Phase 3.1)
# =========================
def dashboard_recent_bookings(tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 200))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                WITH ranked AS (
                    SELECT
                        user_id,
                        service,
                        datetime_iso,
                        status,
                        raw_text,
                        ai_reply,
                        created_at,
                        ROW_NUMBER() OVER (PARTITION BY user_id, COALESCE(datetime_iso, ''), COALESCE(service, '') ORDER BY created_at DESC) AS rn
                    FROM call_logs
                    WHERE tenant_id=:tenant_id
                      AND intent IN ('booking', 'cancel', 'reschedule')
                      AND (service IS NOT NULL OR datetime_iso IS NOT NULL OR status IN ('cancelled','booked','reschedule_wait'))
                )
                SELECT user_id, service, datetime_iso, status, raw_text, ai_reply, created_at
                FROM ranked
                WHERE rn=1
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"tenant_id": tenant_id, "limit": limit},
        ).fetchall()
    items = []
    for r in rows:
        user_id, service, datetime_iso, status, raw_text, ai_reply, created_at = r
        name = None
        text_in = str(raw_text or '').strip()
        m = re.search(r"(?:my name is|i am|меня зовут|я\s+)([A-Za-zĀ-žА-Яа-яЁё\-]{2,40})", text_in, flags=re.IGNORECASE)
        if m:
            name = m.group(1).strip()
        items.append({
            "user_id": user_id,
            "client_name": name,
            "service": service,
            "datetime_iso": datetime_iso,
            "status": status,
            "last_user_message": raw_text,
            "last_ai_reply": ai_reply,
            "created_at": created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
        })
    return items

def dashboard_recent_conversations(tenant_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 100), 300))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, user_id, channel, intent, service, datetime_iso, status, raw_text, ai_reply, created_at
                FROM call_logs
                WHERE tenant_id=:tenant_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"tenant_id": tenant_id, "limit": limit},
        ).fetchall()
    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "user_id": r[1],
            "channel": r[2],
            "intent": r[3],
            "service": r[4],
            "datetime_iso": r[5],
            "status": r[6],
            "user_message": r[7],
            "ai_reply": r[8],
            "created_at": r[9].isoformat() if hasattr(r[9], 'isoformat') else str(r[9]),
        })
    return items


def dashboard_channel_breakdown(tenant_id: str, days: int = 14) -> List[Dict[str, Any]]:
    days = max(1, min(int(days or 14), 60))
    since_ts = now_ts() - timedelta(days=days)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COALESCE(channel, 'unknown') AS channel, COUNT(*) AS total
                FROM call_logs
                WHERE tenant_id=:tenant_id
                  AND created_at >= :since_ts
                GROUP BY COALESCE(channel, 'unknown')
                ORDER BY total DESC, channel ASC
                """
            ),
            {"tenant_id": tenant_id, "since_ts": since_ts},
        ).fetchall()
    return [{"channel": str(r[0] or 'unknown'), "count": int(r[1] or 0)} for r in rows]


def dashboard_top_services(tenant_id: str, limit: int = 5, days: int = 14) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 5), 20))
    days = max(1, min(int(days or 14), 60))
    since_ts = now_ts() - timedelta(days=days)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COALESCE(NULLIF(TRIM(service), ''), 'unknown') AS service, COUNT(*) AS total
                FROM call_logs
                WHERE tenant_id=:tenant_id
                  AND status='booked'
                  AND created_at >= :since_ts
                GROUP BY COALESCE(NULLIF(TRIM(service), ''), 'unknown')
                ORDER BY total DESC, service ASC
                LIMIT :limit
                """
            ),
            {"tenant_id": tenant_id, "limit": limit, "since_ts": since_ts},
        ).fetchall()
    return [{"service": str(r[0] or 'unknown'), "count": int(r[1] or 0)} for r in rows]


def dashboard_daily_usage(tenant_id: str, days: int = 14) -> List[Dict[str, Any]]:
    days = max(1, min(int(days or 14), 60))
    start_date = today_local() - timedelta(days=days - 1)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Riga') AS d,
                       COUNT(*) AS total_requests,
                       COUNT(*) FILTER (WHERE status='booked') AS total_bookings,
                       COUNT(*) FILTER (WHERE status='cancelled') AS total_cancelled
                FROM call_logs
                WHERE tenant_id=:tenant_id
                  AND created_at >= :start_ts
                GROUP BY DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Riga')
                ORDER BY d ASC
                """
            ),
            {"tenant_id": tenant_id, "start_ts": datetime.combine(start_date, datetime.min.time(), tzinfo=TZ)},
        ).fetchall()
    by_day = {}
    for r in rows:
        key = r[0].isoformat() if hasattr(r[0], 'isoformat') else str(r[0])
        by_day[key] = {
            "date": key,
            "requests": int(r[1] or 0),
            "bookings": int(r[2] or 0),
            "cancelled": int(r[3] or 0),
        }
    out = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        key = d.isoformat()
        out.append(by_day.get(key, {"date": key, "requests": 0, "bookings": 0, "cancelled": 0}))
    return out


def dashboard_usage_summary(tenant_id: str, days: int = 14) -> Dict[str, Any]:
    days = max(1, min(int(days or 14), 60))
    since_ts = now_ts() - timedelta(days=days)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_requests,
                    COUNT(*) FILTER (WHERE status='booked') AS total_bookings,
                    COUNT(*) FILTER (WHERE status='cancelled') AS total_cancelled,
                    COUNT(*) FILTER (WHERE intent='reschedule') AS total_reschedules,
                    COUNT(DISTINCT COALESCE(user_id, 'unknown')) AS unique_users
                FROM call_logs
                WHERE tenant_id=:tenant_id
                  AND created_at >= :since_ts
                """
            ),
            {"tenant_id": tenant_id, "since_ts": since_ts},
        ).fetchone()
    total_requests = int((row[0] if row else 0) or 0)
    total_bookings = int((row[1] if row else 0) or 0)
    total_cancelled = int((row[2] if row else 0) or 0)
    total_reschedules = int((row[3] if row else 0) or 0)
    unique_users = int((row[4] if row else 0) or 0)
    booking_rate = round((float(total_bookings) / float(total_requests) * 100.0), 1) if total_requests else 0.0
    return {
        "tenant_id": tenant_id,
        "window_days": days,
        "total_requests": total_requests,
        "total_bookings": total_bookings,
        "total_cancelled": total_cancelled,
        "total_reschedules": total_reschedules,
        "unique_users": unique_users,
        "booking_rate": booking_rate,
        "channels": dashboard_channel_breakdown(tenant_id, days=days),
        "top_services": dashboard_top_services(tenant_id, limit=5, days=days),
        "daily": dashboard_daily_usage(tenant_id, days=days),
    }


def dashboard_tenant_activity(tenant_id: str, limit: int = 25) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 25), 100))
    items = dashboard_recent_conversations(tenant_id, limit=limit)
    out = []
    for item in items:
        out.append({
            "id": item.get("id"),
            "type": item.get("intent") or item.get("status") or "activity",
            "channel": item.get("channel") or "unknown",
            "status": item.get("status") or "unknown",
            "service": item.get("service"),
            "user_id": item.get("user_id"),
            "message": item.get("user_message"),
            "reply": item.get("ai_reply"),
            "created_at": item.get("created_at"),
        })
    return out


def dashboard_analytics(tenant_id: str) -> Dict[str, Any]:
    today_start = datetime.combine(today_local(), datetime.min.time(), tzinfo=TZ)
    with engine.connect() as conn:
        total_requests = conn.execute(text("SELECT COUNT(*) FROM call_logs WHERE tenant_id=:tenant_id"), {"tenant_id": tenant_id}).scalar() or 0
        total_bookings = conn.execute(text("SELECT COUNT(*) FROM call_logs WHERE tenant_id=:tenant_id AND status='booked'"), {"tenant_id": tenant_id}).scalar() or 0
        total_cancelled = conn.execute(text("SELECT COUNT(*) FROM call_logs WHERE tenant_id=:tenant_id AND status='cancelled'"), {"tenant_id": tenant_id}).scalar() or 0
        total_reschedule = conn.execute(text("SELECT COUNT(*) FROM call_logs WHERE tenant_id=:tenant_id AND status IN ('reschedule_wait','booked') AND intent='reschedule'"), {"tenant_id": tenant_id}).scalar() or 0
        today_requests = conn.execute(text("SELECT COUNT(*) FROM call_logs WHERE tenant_id=:tenant_id AND created_at >= :today_start"), {"tenant_id": tenant_id, "today_start": today_start}).scalar() or 0
        today_bookings = conn.execute(text("SELECT COUNT(*) FROM call_logs WHERE tenant_id=:tenant_id AND status='booked' AND created_at >= :today_start"), {"tenant_id": tenant_id, "today_start": today_start}).scalar() or 0
    conversion_rate = round((float(total_bookings) / float(total_requests) * 100.0), 1) if total_requests else 0.0
    return {
        "tenant_id": tenant_id,
        "total_requests": int(total_requests),
        "total_bookings": int(total_bookings),
        "total_cancelled": int(total_cancelled),
        "total_reschedules": int(total_reschedule),
        "conversion_rate": conversion_rate,
        "today_requests": int(today_requests),
        "today_bookings": int(today_bookings),
    }

@app.get("/dashboard/bookings")
@app.get("/bookings")
def dashboard_bookings(tenant_id: str = TENANT_ID_DEFAULT, limit: int = 50):
    tenant = get_tenant((tenant_id or '').strip() or TENANT_ID_DEFAULT)
    if not tenant.get('_id'):
        raise HTTPException(status_code=404, detail='Tenant not found')
    return {
        "tenant_id": tenant.get('_id'),
        "items": dashboard_recent_bookings(tenant.get('_id'), limit),
    }

@app.get("/dashboard/conversations")
@app.get("/conversations")
def dashboard_conversations(tenant_id: str = TENANT_ID_DEFAULT, limit: int = 100):
    tenant = get_tenant((tenant_id or '').strip() or TENANT_ID_DEFAULT)
    if not tenant.get('_id'):
        raise HTTPException(status_code=404, detail='Tenant not found')
    return {
        "tenant_id": tenant.get('_id'),
        "items": dashboard_recent_conversations(tenant.get('_id'), limit),
    }

@app.get("/dashboard/analytics")
@app.get("/analytics")
def dashboard_analytics_endpoint(tenant_id: str = TENANT_ID_DEFAULT):
    tenant = get_tenant((tenant_id or '').strip() or TENANT_ID_DEFAULT)
    if not tenant.get('_id'):
        raise HTTPException(status_code=404, detail='Tenant not found')
    return dashboard_analytics(tenant.get('_id'))

@app.get("/dashboard/usage")
@app.get("/usage")
def dashboard_usage_endpoint(tenant_id: str = TENANT_ID_DEFAULT, days: int = 14):
    tenant = get_tenant((tenant_id or '').strip() or TENANT_ID_DEFAULT)
    if not tenant.get('_id'):
        raise HTTPException(status_code=404, detail='Tenant not found')
    return dashboard_usage_summary(tenant.get('_id'), days=days)

@app.get("/dashboard/activity")
@app.get("/activity")
def dashboard_activity_endpoint(tenant_id: str = TENANT_ID_DEFAULT, limit: int = 25):
    tenant = get_tenant((tenant_id or '').strip() or TENANT_ID_DEFAULT)
    if not tenant.get('_id'):
        raise HTTPException(status_code=404, detail='Tenant not found')
    return {
        "tenant_id": tenant.get('_id'),
        "items": dashboard_tenant_activity(tenant.get('_id'), limit=limit),
    }

@app.get("/dashboard/chart-data")
@app.get("/chart-data")
def dashboard_chart_data_endpoint(tenant_id: str = TENANT_ID_DEFAULT, days: int = 14):
    tenant = get_tenant((tenant_id or '').strip() or TENANT_ID_DEFAULT)
    if not tenant.get('_id'):
        raise HTTPException(status_code=404, detail='Tenant not found')
    usage = dashboard_usage_summary(tenant.get('_id'), days=days)
    return {
        "tenant_id": tenant.get('_id'),
        "window_days": usage.get("window_days", days),
        "daily": usage.get("daily", []),
        "channels": usage.get("channels", []),
        "top_services": usage.get("top_services", []),
    }

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_ui(tenant_id: str = TENANT_ID_DEFAULT):
    tenant_id = (tenant_id or TENANT_ID_DEFAULT).strip() or TENANT_ID_DEFAULT
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Repliq Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background: #f6f7fb; color: #111827; }}
    .wrap {{ max-width: 1320px; margin: 0 auto; padding: 20px; }}
    .panel {{ background: white; border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); padding: 16px; margin-bottom: 16px; }}
    .top {{ display:flex; gap:12px; align-items:center; margin-bottom:16px; flex-wrap:wrap; }}
    input, button, select {{ font: inherit; }}
    input, select {{ padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 10px; background:#fff; }}
    button {{ border:none; border-radius: 10px; padding:10px 14px; background:#111827; color:white; cursor:pointer; }}
    button.secondary {{ background:#fff; color:#111827; border:1px solid #d1d5db; }}
    .metrics {{ display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:12px; }}
    .card {{ background:#fafafa; border:1px solid #e5e7eb; border-radius: 12px; padding: 14px; }}
    .card .num {{ font-size: 28px; font-weight: bold; margin-top: 6px; }}
    .card .sub {{ font-size:12px; color:#6b7280; margin-top:6px; }}
    table {{ width:100%; border-collapse: collapse; font-size:14px; }}
    th, td {{ text-align:left; padding:10px 8px; border-bottom:1px solid #e5e7eb; vertical-align:top; }}
    th {{ background:#fafafa; }}
    .muted {{ color:#6b7280; font-size:12px; }}
    .section-title {{ margin:0 0 12px 0; }}
    .grid-2 {{ display:grid; grid-template-columns: 1.15fr .85fr; gap:16px; }}
    .grid-3 {{ display:grid; grid-template-columns: 1.3fr .85fr .85fr; gap:16px; }}
    .toolbar-label {{ font-size:12px; color:#6b7280; margin-bottom:4px; display:block; }}
    .empty {{ color:#9ca3af; font-style:italic; padding: 8px 0; }}
    .chart-wrap {{ height: 280px; }}
    .mini-chart-wrap {{ height: 240px; }}
    .badge {{ display:inline-block; font-size:12px; color:#374151; background:#f3f4f6; border:1px solid #e5e7eb; padding:6px 10px; border-radius:999px; margin-right:6px; margin-bottom:6px; }}
    .ok {{ color:#065f46; background:#ecfdf5; border-color:#a7f3d0; }}
    .warn {{ color:#92400e; background:#fffbeb; border-color:#fde68a; }}
    .err {{ color:#991b1b; background:#fef2f2; border-color:#fecaca; }}
    .status-grid {{ display:grid; grid-template-columns: 1.2fr .8fr; gap:16px; }}
    .status-list {{ margin:8px 0 0 18px; color:#6b7280; }}
    .nav-links a {{ margin-right:10px; }}
    @media (max-width: 1120px) {{
      .grid-3 {{ grid-template-columns: 1fr; }}
      .grid-2 {{ grid-template-columns: 1fr; }}
      .status-grid {{ grid-template-columns: 1fr; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0,1fr)); }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <div class="top">
        <div>
          <label class="toolbar-label">Tenant</label>
          <input id="tenant" value="{tenant_id}" placeholder="tenant_id" />
        </div>
        <div>
          <label class="toolbar-label">Window</label>
          <select id="days">
            <option value="7">7 days</option>
            <option value="14" selected>14 days</option>
            <option value="30">30 days</option>
          </select>
        </div>
        <div>
          <label class="toolbar-label">Table limit</label>
          <select id="limit">
            <option value="10">10</option>
            <option value="20" selected>20</option>
            <option value="50">50</option>
          </select>
        </div>
        <div style="display:flex; gap:12px; align-items:end; margin-left:auto; flex-wrap:wrap;">
          <button onclick="loadAll()">Refresh</button>
          <button class="secondary" onclick="openPath('/tenants/ui')">Tenants</button>
          <button class="secondary" onclick="openPath('/onboarding/ui?tenant_id='+encodeURIComponent(currentTenant()))">Onboarding</button>
          <button class="secondary" onclick="openPath('/tenant/config/ui?tenant_id='+encodeURIComponent(currentTenant()))">Tenant config</button>
        </div>
      </div>
      <div class="muted nav-links">JSON endpoints:
        <a id="lnk_analytics" href="#">analytics</a> ·
        <a id="lnk_usage" href="#">usage</a> ·
        <a id="lnk_activity" href="#">activity</a> ·
        <a id="lnk_chart_data" href="#">chart data</a> ·
        <a id="lnk_bookings" href="#">bookings</a> ·
        <a id="lnk_conversations" href="#">conversations</a> ·
        <a id="lnk_tenant" href="#">tenant config</a> ·
        <a id="lnk_tenant_ui" href="#">tenant config ui</a> ·
        <a id="lnk_status" href="#">tenant status</a> ·
        <a id="lnk_overview" href="#">tenant overview</a> ·
        <a id="lnk_tenants_ui" href="/tenants/ui">tenants ui</a>
      </div>
    </div>

    <div class="status-grid">
      <div class="panel">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:12px;">
          <div>
            <h3 class="section-title" id="biz_title">Business status</h3>
            <div class="muted" id="biz_sub">Loading tenant status…</div>
          </div>
          <div id="ready_badges"></div>
        </div>
        <div class="metrics" style="margin-top:14px;">
          <div class="card"><div>Plan</div><div id="m_plan" class="num" style="font-size:22px">-</div><div id="m_plan_sub" class="sub"></div></div>
          <div class="card"><div>Dialogs limit</div><div id="m_limit_dialogs" class="num">-</div><div class="sub">Monthly cap by plan</div></div>
          <div class="card"><div>LLM mode</div><div id="m_llm_mode" class="num" style="font-size:22px">-</div><div id="m_llm_calls" class="sub"></div></div>
          <div class="card"><div>Phone routes</div><div id="m_routes" class="num">-</div><div class="sub">Connected incoming numbers</div></div>
        </div>
        <div style="margin-top:14px;">
          <div class="muted">Missing setup items</div>
          <ul id="missing_list" class="status-list"></ul>
        </div>
      </div>
      <div class="panel">
        <h3 class="section-title">Setup checkpoints</h3>
        <div id="checkpoint_block"></div>
        <div style="margin-top:14px;" class="muted">Quick actions</div>
        <div style="margin-top:8px; display:flex; flex-wrap:wrap; gap:8px;">
          <button class="secondary" onclick="openPath(document.getElementById('lnk_status').href)">Open status JSON</button>
          <button class="secondary" onclick="openPath(document.getElementById('lnk_overview').href)">Open overview JSON</button>
          <button class="secondary" onclick="openPath('/google/connect?tenant_id='+encodeURIComponent(currentTenant()))">Connect Google</button>
          <button class="secondary" onclick="openPath('/google/calendars/ui?tenant_id='+encodeURIComponent(currentTenant()))">Select calendar</button>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="metrics">
        <div class="card"><div>Total requests</div><div id="m_requests" class="num">-</div><div class="sub">All-time requests</div></div>
        <div class="card"><div>Total bookings</div><div id="m_bookings" class="num">-</div><div class="sub">All-time successful bookings</div></div>
        <div class="card"><div>Conversion</div><div id="m_conv" class="num">-</div><div class="sub">All-time booking rate</div></div>
        <div class="card"><div>Today bookings</div><div id="m_today" class="num">-</div><div class="sub">Booked today</div></div>
      </div>
      <div class="metrics" style="margin-top:12px;">
        <div class="card"><div>Window unique users</div><div id="m_users" class="num">-</div><div class="sub">Distinct users in selected window</div></div>
        <div class="card"><div>Window reschedules</div><div id="m_reschedules" class="num">-</div><div class="sub">Intent=reschedule in selected window</div></div>
        <div class="card"><div>Window cancelled</div><div id="m_cancelled" class="num">-</div><div class="sub">Cancelled in selected window</div></div>
        <div class="card"><div>Main channel</div><div id="m_channel" class="num" style="font-size:20px">-</div><div id="m_channel_sub" class="sub"></div></div>
      </div>
    </div>

    <div class="grid-3">
      <div class="panel">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <h3 class="section-title">Usage trend</h3>
          <span class="badge" id="usage_badge">Selected window</span>
        </div>
        <div class="chart-wrap"><canvas id="trend_chart"></canvas></div>
      </div>
      <div class="panel">
        <h3 class="section-title">Channel mix</h3>
        <div class="mini-chart-wrap"><canvas id="channel_chart"></canvas></div>
      </div>
      <div class="panel">
        <h3 class="section-title">Top services</h3>
        <div class="mini-chart-wrap"><canvas id="services_chart"></canvas></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="panel">
        <h3 class="section-title">Recent bookings</h3>
        <table id="bookings_tbl"><thead><tr><th>User</th><th>Service</th><th>Date/Time</th><th>Status</th><th>Created</th></tr></thead><tbody></tbody></table>
      </div>
      <div class="panel">
        <h3 class="section-title">Top services (table)</h3>
        <table id="services_tbl"><thead><tr><th>Service</th><th>Bookings</th></tr></thead><tbody></tbody></table>
      </div>
    </div>

    <div class="grid-2">
      <div class="panel">
        <h3 class="section-title">Recent activity</h3>
        <table id="activity_tbl"><thead><tr><th>Time</th><th>Type</th><th>Channel</th><th>User</th><th>Message</th><th>Status</th></tr></thead><tbody></tbody></table>
      </div>
      <div class="panel">
        <h3 class="section-title">Daily usage (table)</h3>
        <table id="daily_tbl"><thead><tr><th>Date</th><th>Requests</th><th>Bookings</th><th>Cancelled</th></tr></thead><tbody></tbody></table>
      </div>
    </div>

    <div class="panel">
      <h3 class="section-title">Recent conversations</h3>
      <table id="conv_tbl"><thead><tr><th>Time</th><th>User</th><th>Channel</th><th>User message</th><th>AI reply</th><th>Status</th></tr></thead><tbody></tbody></table>
    </div>
  </div>
<script>
let trendChart = null;
let channelChart = null;
let servicesChart = null;
function currentTenant() {{ return document.getElementById('tenant').value.trim() || 'default'; }}
function openPath(url) {{ if (url) window.location = url; }}
function esc(v) {{ if (v === null || v === undefined) return ''; return String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'", '&#39;'); }}
function setEmpty(tbody, colSpan, label='No data yet') {{ tbody.innerHTML = `<tr><td colspan="${{colSpan}}" class="empty">${{esc(label)}}</td></tr>`; }}
async function fetchJson(url) {{ const r = await fetch(url); if (!r.ok) {{ const text = await r.text(); throw new Error(text || `HTTP ${{r.status}}`); }} return r.json(); }}
function destroyIf(chartObj) {{ if (chartObj) chartObj.destroy(); }}
function statusBadge(label, cls) {{ return `<span class="badge ${{cls||''}}">${{esc(label)}}</span>`; }}
function el(id) {{ return document.getElementById(id); }}
function setText(id, value, fallback='-') {{ const node = el(id); if (!node) return; node.textContent = (value === null || value === undefined || value === '') ? fallback : String(value); }}
function safeArray(value) {{ return Array.isArray(value) ? value : []; }}
function normalizeDailyPayload(value) {{
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.daily)) return value.daily;
  if (Array.isArray(value?.items)) return value.items;
  return [];
}}
function normalizeChannelPayload(value) {{
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.channels)) return value.channels;
  return [];
}}
function normalizeServicePayload(value) {{
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.top_services)) return value.top_services;
  if (Array.isArray(value?.items)) return value.items;
  return [];
}}
function normalizeOverview(value) {{
  return (value && typeof value === 'object') ? value : {{}};
}}
function renderTrendChart(rawDaily) {{
  const canvas = el('trend_chart');
  if (!canvas || typeof Chart === 'undefined') return;
  const daily = normalizeDailyPayload(rawDaily);
  const ctx = canvas.getContext('2d');
  destroyIf(trendChart);
  trendChart = new Chart(ctx, {{
    type:'line',
    data:{{
      labels: daily.map(x=>x?.date||''),
      datasets:[
        {{label:'Requests', data: daily.map(x=>x?.requests||0), borderWidth:2, tension:0.3}},
        {{label:'Bookings', data: daily.map(x=>x?.bookings||0), borderWidth:2, tension:0.3}},
        {{label:'Cancelled', data: daily.map(x=>x?.cancelled||0), borderWidth:2, tension:0.3}}
      ]
    }},
    options:{{responsive:true, maintainAspectRatio:false, interaction:{{mode:'index', intersect:false}}, plugins:{{legend:{{position:'bottom'}}}}, scales:{{y:{{beginAtZero:true, ticks:{{precision:0}}}}}}}}
  }});
}}
function renderChannelChart(rawChannels) {{
  const canvas = el('channel_chart');
  if (!canvas || typeof Chart === 'undefined') return;
  const channels = normalizeChannelPayload(rawChannels);
  const ctx = canvas.getContext('2d');
  destroyIf(channelChart);
  channelChart = new Chart(ctx, {{
    type:'doughnut',
    data:{{labels: channels.map(x=>x?.channel||'unknown'), datasets:[{{data: channels.map(x=>x?.count||0), borderWidth:1}}]}},
    options:{{responsive:true, maintainAspectRatio:false, plugins:{{legend:{{position:'bottom'}}}}}}
  }});
}}
function renderServicesChart(rawItems) {{
  const canvas = el('services_chart');
  if (!canvas || typeof Chart === 'undefined') return;
  const items = normalizeServicePayload(rawItems);
  const ctx = canvas.getContext('2d');
  destroyIf(servicesChart);
  servicesChart = new Chart(ctx, {{
    type:'bar',
    data:{{labels: items.map(x=>x?.service||'unknown'), datasets:[{{label:'Bookings', data: items.map(x=>x?.count||0), borderWidth:1}}]}},
    options:{{responsive:true, maintainAspectRatio:false, indexAxis:'y', plugins:{{legend:{{display:false}}}}, scales:{{x:{{beginAtZero:true, ticks:{{precision:0}}}}}}}}
  }});
}}
function renderOverview(rawOverview) {{
  const ov = normalizeOverview(rawOverview);
  const tenant = ov?.tenant || {{}};
  const readiness = ov?.readiness || {{}};
  const onboarding = ov?.onboarding || {{}};
  const planMeta = ov?.plan_meta || {{}};
  const limits = planMeta?.limits || {{}};
  setText('biz_title', tenant.business_name || tenant._id || currentTenant());
  setText('biz_sub', `Tenant ${{tenant._id || currentTenant()}} · timezone ${{tenant.timezone || '—'}} · language ${{tenant.language || '—'}}`, '');
  setText('m_plan', planMeta.plan || 'starter');
  setText('m_plan_sub', planMeta.subscription_status || 'trial', 'trial');
  setText('m_limit_dialogs', limits.dialogs_per_month ?? '-');
  setText('m_llm_mode', limits.llm_mode || '-');
  setText('m_llm_calls', `LLM calls/month: ${{limits.llm_calls_per_month ?? 0}}`, 'LLM calls/month: 0');
  setText('m_routes', ov?.phone_routes_count ?? tenant?.phone_routes_count ?? 0, '0');
  const badges = [];
  badges.push(readiness.ready ? statusBadge('Ready','ok') : statusBadge('Setup incomplete','warn'));
  badges.push(onboarding.google_connected ? statusBadge('Google connected','ok') : statusBadge('Google pending','warn'));
  badges.push(onboarding.calendar_selected ? statusBadge('Calendar selected','ok') : statusBadge('Calendar missing','warn'));
  const readyBadges = el('ready_badges');
  if (readyBadges) readyBadges.innerHTML = badges.join(' ');
  const ml = el('missing_list');
  if (ml) {{
    ml.innerHTML = '';
    const missing = Array.isArray(readiness.missing) ? readiness.missing : [];
    if (!missing.length) {{
      ml.innerHTML = '<li>No blocking setup issues</li>';
    }} else {{
      missing.forEach(x => {{
        const li = document.createElement('li');
        li.textContent = x;
        ml.appendChild(li);
      }});
    }}
  }}
  const checkpoints = [];
  checkpoints.push(`<div>${{statusBadge(onboarding.google_connected ? 'Google connected' : 'Google not connected', onboarding.google_connected ? 'ok' : 'warn')}}</div>`);
  checkpoints.push(`<div>${{statusBadge(onboarding.calendar_selected ? 'Calendar selected' : 'Calendar not selected', onboarding.calendar_selected ? 'ok' : 'warn')}}</div>`);
  checkpoints.push(`<div>${{statusBadge(onboarding.onboarding_completed ? 'Onboarding completed' : 'Onboarding in progress', onboarding.onboarding_completed ? 'ok' : 'warn')}}</div>`);
  checkpoints.push(`<div class="muted" style="margin-top:8px;">Next step: ${{esc(onboarding.next_step || readiness.next_step || 'done')}}</div>`);
  checkpoints.push(`<div class="muted">Owner: ${{esc(tenant.owner_email || onboarding.owner_email || '—')}} · Phone: ${{esc(tenant.phone_number || onboarding.phone_number || '—')}}</div>`);
  const checkpointBlock = el('checkpoint_block');
  if (checkpointBlock) checkpointBlock.innerHTML = checkpoints.join('');
}}
function renderTableRows(selector, rows, colSpan, emptyLabel, rowRenderer) {{
  const tbody = document.querySelector(selector);
  if (!tbody) return;
  tbody.innerHTML = '';
  const safeRows = safeArray(rows);
  if (!safeRows.length) {{
    setEmpty(tbody, colSpan, emptyLabel);
    return;
  }}
  safeRows.forEach(item => {{
    const tr = document.createElement('tr');
    tr.innerHTML = rowRenderer(item || {{}});
    tbody.appendChild(tr);
  }});
}}
function clearDashboardBanner() {{
  const existingBanner = el('dash_error_banner');
  if (existingBanner) existingBanner.remove();
}}
function showDashboardBanner(message, kind='warn') {{
  clearDashboardBanner();
  const banner = document.createElement('div');
  banner.id = 'dash_error_banner';
  const styleMap = {{
    warn: 'background:#fef3c7;color:#92400e;',
    err: 'background:#fee2e2;color:#991b1b;',
    ok: 'background:#dcfce7;color:#166534;'
  }};
  banner.style = `${{styleMap[kind] || styleMap.warn}}padding:12px 16px;font-size:14px;margin-bottom:12px;border-radius:12px;`;
  banner.textContent = message;
  const wrap = document.querySelector('.wrap');
  if (wrap) wrap.prepend(banner);
}}
async function loadAll() {{
  const tenant = currentTenant();
  const days = el('days')?.value || '14';
  const limit = el('limit')?.value || '20';
  setText('usage_badge', `${{days}} day window`, 'Selected window');
  el('lnk_analytics').href = `/dashboard/analytics?tenant_id=${{encodeURIComponent(tenant)}}`;
  el('lnk_usage').href = `/dashboard/usage?tenant_id=${{encodeURIComponent(tenant)}}&days=${{encodeURIComponent(days)}}`;
  el('lnk_activity').href = `/dashboard/activity?tenant_id=${{encodeURIComponent(tenant)}}&limit=${{encodeURIComponent(limit)}}`;
  el('lnk_chart_data').href = `/dashboard/chart-data?tenant_id=${{encodeURIComponent(tenant)}}&days=${{encodeURIComponent(days)}}`;
  el('lnk_bookings').href = `/dashboard/bookings?tenant_id=${{encodeURIComponent(tenant)}}&limit=${{encodeURIComponent(limit)}}`;
  el('lnk_conversations').href = `/dashboard/conversations?tenant_id=${{encodeURIComponent(tenant)}}&limit=${{encodeURIComponent(limit)}}`;
  el('lnk_tenant').href = `/tenant/config?tenant_id=${{encodeURIComponent(tenant)}}`;
  el('lnk_tenant_ui').href = `/tenant/config/ui?tenant_id=${{encodeURIComponent(tenant)}}`;
  el('lnk_status').href = `/tenant/status?tenant_id=${{encodeURIComponent(tenant)}}`;
  el('lnk_overview').href = `/tenant/overview?tenant_id=${{encodeURIComponent(tenant)}}`;
  clearDashboardBanner();

  const requests = [
    ['analytics', `/dashboard/analytics?tenant_id=${{encodeURIComponent(tenant)}}`],
    ['usage', `/dashboard/usage?tenant_id=${{encodeURIComponent(tenant)}}&days=${{encodeURIComponent(days)}}`],
    ['activity', `/dashboard/activity?tenant_id=${{encodeURIComponent(tenant)}}&limit=${{encodeURIComponent(limit)}}`],
    ['bookings', `/dashboard/bookings?tenant_id=${{encodeURIComponent(tenant)}}&limit=${{encodeURIComponent(limit)}}`],
    ['conversations', `/dashboard/conversations?tenant_id=${{encodeURIComponent(tenant)}}&limit=${{encodeURIComponent(limit)}}`],
    ['chartData', `/dashboard/chart-data?tenant_id=${{encodeURIComponent(tenant)}}&days=${{encodeURIComponent(days)}}`],
    ['overview', `/tenant/overview?tenant_id=${{encodeURIComponent(tenant)}}`]
  ];

  const settled = await Promise.allSettled(requests.map(([_, url]) => fetchJson(url)));
  const data = {{}};
  const errors = [];
  settled.forEach((result, idx) => {{
    const key = requests[idx][0];
    if (result.status === 'fulfilled') {{
      data[key] = result.value;
    }} else {{
      data[key] = null;
      errors.push(`${{key}}: ${{result.reason?.message || result.reason || 'load failed'}}`);
      console.error('dashboard_block_failed', key, result.reason);
    }}
  }});

  const a = data.analytics || {{}};
  const u = data.usage || {{}};
  const act = data.activity || {{}};
  const b = data.bookings || {{}};
  const c = data.conversations || {{}};
  const chartData = data.chartData || {{}};
  const ov = data.overview || {{}};

  try {{ renderOverview(ov); }} catch (err) {{ errors.push(`overview render: ${{err?.message || err}}`); console.error(err); }}
  setText('m_requests', a?.total_requests ?? '-');
  setText('m_bookings', a?.total_bookings ?? '-');
  setText('m_conv', `${{a?.conversion_rate ?? 0}}%`);
  setText('m_today', a?.today_bookings ?? '-');
  setText('m_users', u?.unique_users ?? '-');
  setText('m_reschedules', u?.total_reschedules ?? '-');
  setText('m_cancelled', u?.total_cancelled ?? '-');
  const topChannelObj = Array.isArray(u?.channels) && u.channels.length ? u.channels[0] : null;
  setText('m_channel', topChannelObj?.channel || '-');
  setText('m_channel_sub', topChannelObj ? `${{topChannelObj.count || 0}} events in selected window` : '', '');

  try {{ renderTrendChart(chartData?.daily || u?.daily || []); }} catch (err) {{ errors.push(`trend chart: ${{err?.message || err}}`); console.error(err); }}
  try {{ renderChannelChart(chartData?.channels || u?.channels || []); }} catch (err) {{ errors.push(`channel chart: ${{err?.message || err}}`); console.error(err); }}
  try {{ renderServicesChart(chartData?.top_services || u?.top_services || []); }} catch (err) {{ errors.push(`services chart: ${{err?.message || err}}`); console.error(err); }}

  renderTableRows('#bookings_tbl tbody', b?.items, 5, 'No bookings yet', item => `<td>${{esc(item?.client_name || item?.user_id || '')}}</td><td>${{esc(item?.service || 'unknown')}}</td><td>${{esc(item?.datetime_iso || '')}}</td><td>${{esc(item?.status || '')}}</td><td><span class="muted">${{esc(item?.created_at || '')}}</span></td>`);
  renderTableRows('#services_tbl tbody', u?.top_services, 2, 'No booked services in selected window', item => `<td>${{esc(item?.service || 'unknown')}}</td><td>${{esc(item?.count ?? 0)}}</td>`);
  renderTableRows('#activity_tbl tbody', act?.items, 6, 'No activity yet', item => `<td><span class="muted">${{esc(item?.created_at || '')}}</span></td><td>${{esc(item?.type || '')}}</td><td>${{esc(item?.channel || '')}}</td><td>${{esc(item?.user_id || '')}}</td><td>${{esc(item?.message || '')}}</td><td>${{esc(item?.status || '')}}</td>`);
  renderTableRows('#daily_tbl tbody', u?.daily, 4, 'No daily usage yet', item => `<td>${{esc(item?.date || '')}}</td><td>${{esc(item?.requests ?? 0)}}</td><td>${{esc(item?.bookings ?? 0)}}</td><td>${{esc(item?.cancelled ?? 0)}}</td>`);
  renderTableRows('#conv_tbl tbody', c?.items, 6, 'No conversations yet', item => `<td><span class="muted">${{esc(item?.created_at || '')}}</span></td><td>${{esc(item?.user_id || '')}}</td><td>${{esc(item?.channel || '')}}</td><td>${{esc(item?.user_message || '')}}</td><td>${{esc(item?.ai_reply || '')}}</td><td>${{esc(item?.status || '')}}</td>`);

  if (errors.length) {{
    showDashboardBanner(`Dashboard loaded with partial issues: ${{errors.join(' | ')}}`, 'warn');
  }}
}}
document.addEventListener('DOMContentLoaded', loadAll);
</script>
</body>
</html>
    """
    return HTMLResponse(content=html)


@app.get("/tenant/config/ui")
def tenant_config_ui(tenant_id: str = TENANT_ID_DEFAULT):
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Tenant Config</title>
<style>
body {{ font-family: Arial, sans-serif; background:#f7f7f8; color:#111; margin:0; padding:24px; }}
.wrap {{ max-width: 1100px; margin:0 auto; }}
.card {{ background:#fff; border:1px solid #e5e7eb; border-radius:16px; padding:20px; margin-bottom:18px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }}
h1,h2 {{ margin:0 0 14px 0; }}
.grid {{ display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:14px; }}
label {{ display:block; font-size:14px; margin-bottom:6px; color:#374151; }}
input, select, textarea {{ width:100%; box-sizing:border-box; border:1px solid #d1d5db; border-radius:10px; padding:10px 12px; font-size:14px; }}
textarea {{ min-height:110px; resize:vertical; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
.actions {{ display:flex; gap:10px; align-items:center; margin-top:14px; }}
button {{ border:0; background:#111827; color:#fff; padding:10px 16px; border-radius:10px; cursor:pointer; }}
button.secondary {{ background:#fff; color:#111827; border:1px solid #d1d5db; }}
.small {{ font-size:12px; color:#6b7280; }}
.ok {{ color:#065f46; }}
.err {{ color:#991b1b; white-space:pre-wrap; }}
.links a {{ margin-right:14px; }}
.full {{ grid-column: 1 / -1; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>Tenant Config Editor</h1>
    <div class="actions">
      <input id="tenant_id" value="{tenant_id}" />
      <button onclick="loadConfig()">Load</button>
      <button class="secondary" onclick="window.location='/dashboard?tenant_id='+encodeURIComponent(document.getElementById('tenant_id').value)">Open dashboard</button>
    </div>
    <div class="small">Edits are saved via <code>POST /tenant/config/update</code>.</div>
  </div>

  <div class="card">
    <h2>Basic settings</h2>
    <div class="grid">
      <div><label>Business name</label><input id="business_name"/></div>
      <div><label>Phone number</label><input id="phone_number"/></div>
      <div><label>Timezone</label><input id="timezone"/></div>
      <div><label>Language</label>
        <select id="language">
          <option value="lv">lv</option>
          <option value="ru">ru</option>
          <option value="en">en</option>
        </select>
      </div>
      <div><label>Work start</label><input id="work_start" placeholder="09:00"/></div>
      <div><label>Work end</label><input id="work_end" placeholder="18:00"/></div>
      <div><label>Min notice minutes</label><input id="min_notice_minutes" type="number"/></div>
      <div><label>Buffer minutes</label><input id="buffer_minutes" type="number"/></div>
    </div>
  </div>

  <div class="card">
    <h2>Services and rules</h2>
    <div class="grid">
      <div><label>Services LV</label><textarea id="services_lv"></textarea></div>
      <div><label>Services RU</label><textarea id="services_ru"></textarea></div>
      <div class="full"><label>Services EN</label><textarea id="services_en"></textarea></div>
      <div class="full"><label>Service catalog JSON</label><textarea id="service_catalog_json" placeholder='[{{"key":"mens_haircut","name_lv":"vīriešu frizūra","name_ru":"мужская стрижка","name_en":"men&#39;s haircut","duration_min":30,"aliases_lv":["matu griezums"],"aliases_ru":["стрижка"],"aliases_en":["haircut"]}}]'></textarea></div>
      <div class="full"><label>Service account JSON</label><textarea id="service_account_json" placeholder='{{"type":"service_account",...}}'></textarea></div>
      <div><label>Weekly hours JSON</label><textarea id="weekly_hours_json"></textarea></div>
      <div><label>Days off JSON</label><textarea id="days_off_json"></textarea></div>
      <div><label>Breaks JSON</label><textarea id="breaks_json"></textarea></div>
      <div><label>Holidays JSON</label><textarea id="holidays_json"></textarea></div>
      <div><label>Business memory LV</label><textarea id="business_memory_lv" placeholder="Piemēram: Vīriešu frizūra 20€, bārda 12€, atrodamies Brīvības ielā 10"></textarea></div>
      <div><label>Business memory RU</label><textarea id="business_memory_ru" placeholder="Например: Мужская стрижка 20€, борода 12€, адрес: Brīvības iela 10"></textarea></div>
      <div class="full"><label>Business memory EN</label><textarea id="business_memory_en" placeholder="For example: Men's haircut 20€, beard trim 12€, address: Brīvības iela 10"></textarea></div>
    </div>
    <div class="actions">
      <button onclick="saveConfig()">Save config</button>
      <span id="save_status" class="small"></span>
    </div>
  </div>

  <div class="card">
    <h2>Quick links</h2>
    <div class="links">
      <a id="lnk_json" href="#">JSON config</a>
      <a id="lnk_routes" href="#">Phone routes</a>
      <a id="lnk_bookings" href="#">Bookings</a>
      <a id="lnk_conv" href="#">Conversations</a>
      <a id="lnk_analytics" href="#">Analytics</a>
    </div>
  </div>
</div>

<script>
function j(v) {{
  if (v === null || v === undefined || v === "") return "";
  if (typeof v === "string") return v;
  return JSON.stringify(v, null, 2);
}}
function setLinks(tid) {{
  document.getElementById('lnk_json').href = '/tenant/config?tenant_id=' + encodeURIComponent(tid);
  document.getElementById('lnk_routes').href = '/tenant/routes?tenant_id=' + encodeURIComponent(tid);
  document.getElementById('lnk_bookings').href = '/bookings?tenant_id=' + encodeURIComponent(tid);
  document.getElementById('lnk_conv').href = '/conversations?tenant_id=' + encodeURIComponent(tid);
  document.getElementById('lnk_analytics').href = '/analytics?tenant_id=' + encodeURIComponent(tid);
}}
async function loadConfig() {{
  const tid = document.getElementById('tenant_id').value.trim() || 'default';
  setLinks(tid);
  const r = await fetch('/tenant/config?tenant_id=' + encodeURIComponent(tid));
  const data = await r.json();
  const t = data.tenant || {{}};
  document.getElementById('business_name').value = t.business_name || '';
  document.getElementById('phone_number').value = t.phone_number || '';
  document.getElementById('timezone').value = t.timezone || '';
  document.getElementById('language').value = t.language || 'lv';
  document.getElementById('work_start').value = t.work_start || '';
  document.getElementById('work_end').value = t.work_end || '';
  document.getElementById('services_lv').value = t.services_lv || '';
  document.getElementById('services_ru').value = t.services_ru || '';
  document.getElementById('services_en').value = t.services_en || '';
  document.getElementById('weekly_hours_json').value = j(t.weekly_hours_json);
  document.getElementById('days_off_json').value = j(t.days_off_json);
  document.getElementById('breaks_json').value = j(t.breaks_json);
  document.getElementById('holidays_json').value = j(t.holidays_json);
  document.getElementById('min_notice_minutes').value = t.min_notice_minutes ?? '';
  document.getElementById('buffer_minutes').value = t.buffer_minutes ?? '';
  document.getElementById('service_catalog_json').value = j(t.service_catalog_json || t.service_catalog);
  document.getElementById('service_account_json').value = t.service_account_json || t.google_service_account_json || '';
  document.getElementById('business_memory_lv').value = t.business_memory_lv || '';
  document.getElementById('business_memory_ru').value = t.business_memory_ru || '';
  document.getElementById('business_memory_en').value = t.business_memory_en || '';
}}
async function saveConfig() {{
  const tid = document.getElementById('tenant_id').value.trim() || 'default';
  const payload = {{
    tenant_id: tid,
    business_name: document.getElementById('business_name').value || null,
    phone_number: document.getElementById('phone_number').value || null,
    timezone: document.getElementById('timezone').value || null,
    language: document.getElementById('language').value || null,
    work_start: document.getElementById('work_start').value || null,
    work_end: document.getElementById('work_end').value || null,
    services_lv: document.getElementById('services_lv').value || null,
    services_ru: document.getElementById('services_ru').value || null,
    services_en: document.getElementById('services_en').value || null,
    weekly_hours_json: document.getElementById('weekly_hours_json').value || null,
    days_off_json: document.getElementById('days_off_json').value || null,
    breaks_json: document.getElementById('breaks_json').value || null,
    holidays_json: document.getElementById('holidays_json').value || null,
    min_notice_minutes: document.getElementById('min_notice_minutes').value ? Number(document.getElementById('min_notice_minutes').value) : null,
    buffer_minutes: document.getElementById('buffer_minutes').value ? Number(document.getElementById('buffer_minutes').value) : null,
    service_catalog_json: document.getElementById('service_catalog_json').value || null,
    service_account_json: document.getElementById('service_account_json').value || null,
    business_memory_lv: document.getElementById('business_memory_lv').value || null,
    business_memory_ru: document.getElementById('business_memory_ru').value || null,
    business_memory_en: document.getElementById('business_memory_en').value || null
  }};
  const st = document.getElementById('save_status');
  st.className = 'small';
  st.textContent = 'Saving...';
  const r = await fetch('/tenant/config/update', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(payload)
  }});
  const data = await r.json();
  if (r.ok) {{
    st.className = 'small ok';
    st.textContent = 'Saved';
    await loadConfig();
  }} else {{
    st.className = 'small err';
    st.textContent = (data.detail || JSON.stringify(data, null, 2));
  }}
}}
document.addEventListener('DOMContentLoaded', loadConfig);
</script>
</body>
</html>
    """
    return HTMLResponse(content=html)


def _safe_parse_json_text(value: Any):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    txt = str(value).strip()
    if not txt:
        return None
    try:
        return json.loads(txt)
    except Exception:
        return None

def _sync_weekly_hours_with_fallback_bounds(
    weekly_hours_value: Any,
    work_start: Optional[str],
    work_end: Optional[str],
) -> Optional[str]:
    parsed = _safe_parse_json_text(weekly_hours_value)
    if not isinstance(parsed, dict):
        if isinstance(weekly_hours_value, str):
            return weekly_hours_value
        return None
    for day_key, val in list(parsed.items()):
        if val is None:
            continue
        if isinstance(val, (list, tuple)) and len(val) >= 2:
            start_val = str(val[0]).strip() if val[0] is not None else ""
            end_val = str(val[1]).strip() if val[1] is not None else ""
            parsed[day_key] = [
                work_start.strip() if isinstance(work_start, str) and work_start.strip() else start_val,
                work_end.strip() if isinstance(work_end, str) and work_end.strip() else end_val,
            ]
    return json.dumps(parsed, ensure_ascii=False, indent=2)

class TenantConfigUpdateRequest(BaseModel):
    tenant_id: str
    business_name: Optional[str] = None
    phone_number: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    work_start: Optional[str] = None
    work_end: Optional[str] = None
    services_lv: Optional[str] = None
    services_ru: Optional[str] = None
    services_en: Optional[str] = None
    weekly_hours_json: Optional[str] = None
    days_off_json: Optional[str] = None
    breaks_json: Optional[str] = None
    holidays_json: Optional[str] = None
    min_notice_minutes: Optional[int] = None
    buffer_minutes: Optional[int] = None
    service_catalog_json: Optional[str] = None
    service_account_json: Optional[str] = None
    business_memory_lv: Optional[str] = None
    business_memory_ru: Optional[str] = None
    business_memory_en: Optional[str] = None

def _jsonable_tenant_view(tenant: Dict[str, Any]) -> Dict[str, Any]:
    tenant = dict(tenant or {})
    for k, v in list(tenant.items()):
        if hasattr(v, "isoformat"):
            tenant[k] = v.isoformat()
    return tenant

@app.get("/tenants")
def list_tenants(limit: int = 100):
    limit = max(1, min(int(limit or 100), 500))
    cols = tenants_columns()
    pk = tenants_pk(cols)
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT {pk},
                       COALESCE(business_name, name, {pk}) AS business_name,
                       phone_number,
                       timezone,
                       language,
                       calendar_id,
                       onboarding_completed,
                       google_connected,
                       subscription_status,
                       plan,
                       updated_at
                FROM tenants
                ORDER BY updated_at DESC NULLS LAST, {pk} ASC
                LIMIT :limit
            """),
            {"limit": limit},
        ).fetchall()
    items = []
    for r in rows:
        tenant_item = normalize_tenant_saas_fields({
            "_id": r[0],
            "business_name": r[1],
            "phone_number": r[2],
            "timezone": r[3],
            "language": r[4],
            "calendar_id": r[5],
            "onboarding_completed": r[6],
            "google_connected": r[7],
            "subscription_status": r[8],
            "plan": r[9],
        })
        items.append({
            "tenant_id": tenant_item["_id"],
            "business_name": tenant_item.get("business_name"),
            "phone_number": tenant_item.get("phone_number"),
            "timezone": tenant_item.get("timezone"),
            "language": tenant_item.get("language"),
            "calendar_id": tenant_item.get("calendar_id"),
            "onboarding_completed": tenant_item.get("onboarding_completed"),
            "google_connected": tenant_google_connected_effective(tenant_item),
            "subscription_status": tenant_item.get("subscription_status"),
            "plan": tenant_item.get("plan"),
            "ready": tenant_ready_status_payload(tenant_item).get("ready"),
            "missing": tenant_ready_status_payload(tenant_item).get("missing"),
            "updated_at": r[10].isoformat() if hasattr(r[10], "isoformat") else str(r[10]),
        })
    return {"items": items}

@app.get("/tenants/ui", response_class=HTMLResponse)
def tenants_ui(limit: int = 200):
    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Repliq Tenants</title>
<style>
body {{ font-family: Arial, sans-serif; background:#f6f7fb; color:#111827; margin:0; padding:24px; }}
.wrap {{ max-width: 1200px; margin:0 auto; }}
.card {{ background:#fff; border:1px solid #e5e7eb; border-radius:18px; padding:18px; box-shadow: 0 10px 28px rgba(15,23,42,.06); margin-bottom:16px; }}
.top {{ display:flex; gap:12px; align-items:end; flex-wrap:wrap; }}
input, select, button {{ font:inherit; }}
input, select {{ padding:10px 12px; border:1px solid #d1d5db; border-radius:10px; background:#fff; }}
button {{ border:none; border-radius:10px; padding:10px 14px; background:#111827; color:white; cursor:pointer; }}
button.secondary {{ background:#fff; color:#111827; border:1px solid #d1d5db; }}
.table-wrap {{ overflow:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }}
th,td {{ text-align:left; padding:10px 8px; border-bottom:1px solid #e5e7eb; vertical-align:top; }}
th {{ background:#fafafa; }}
.badge {{ display:inline-block; padding:4px 8px; border-radius:999px; font-size:12px; border:1px solid #e5e7eb; background:#f9fafb; }}
.ok {{ color:#065f46; background:#ecfdf5; border-color:#a7f3d0; }}
.warn {{ color:#92400e; background:#fffbeb; border-color:#fde68a; }}
.err {{ color:#991b1b; background:#fef2f2; border-color:#fecaca; }}
.small {{ color:#6b7280; font-size:12px; }}
.actions a {{ margin-right:8px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="top">
      <div>
        <div class="small">Search</div>
        <input id="q" placeholder="tenant or business name" />
      </div>
      <div>
        <div class="small">Limit</div>
        <select id="limit"><option value="50">50</option><option value="100" selected>100</option><option value="200">200</option></select>
      </div>
      <div style="display:flex; gap:10px; margin-left:auto;">
        <button onclick="loadTenants()">Refresh</button>
        <button class="secondary" onclick="window.location='/onboarding/ui'">Create business</button>
      </div>
    </div>
  </div>
  <div class="card">
    <div class="table-wrap">
      <table id="tenants_tbl">
        <thead><tr><th>Business</th><th>Tenant</th><th>Ready</th><th>Google</th><th>Calendar</th><th>Plan</th><th>Updated</th><th>Actions</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </div>
</div>
<script>
function esc(v) {{ return v === null || v === undefined ? '' : String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'", '&#39;'); }}
function badge(label, cls) {{ return `<span class="badge ${{cls||''}}">${{esc(label)}}</span>`; }}
async function loadTenants() {{
  const limit = document.getElementById('limit').value || '100';
  const q = (document.getElementById('q').value || '').trim().toLowerCase();
  const r = await fetch(`/tenants?limit=${{encodeURIComponent(limit)}}`);
  const data = await r.json();
  const items = Array.isArray(data.items) ? data.items : [];
  const filtered = q ? items.filter(x => String(x.tenant_id || '').toLowerCase().includes(q) || String(x.business_name || '').toLowerCase().includes(q)) : items;
  const tb = document.querySelector('#tenants_tbl tbody');
  tb.innerHTML = '';
  if (!filtered.length) {{ tb.innerHTML = '<tr><td colspan="8" class="small">No tenants found</td></tr>'; return; }}
  filtered.forEach(item => {{
    const tr = document.createElement('tr');
    const ready = item.ready ? badge('Ready','ok') : badge('Setup incomplete','warn');
    const google = item.google_connected ? badge('Connected','ok') : badge('Pending','warn');
    const cal = item.calendar_id ? badge('Selected','ok') : badge('Missing','warn');
    const missing = Array.isArray(item.missing) && item.missing.length ? `<div class="small">Missing: ${{esc(item.missing.join(', '))}}</div>` : '';
    tr.innerHTML = `<td><strong>${{esc(item.business_name || item.tenant_id)}}</strong>${{missing}}</td><td><code>${{esc(item.tenant_id)}}</code></td><td>${{ready}}</td><td>${{google}}</td><td>${{cal}}</td><td>${{esc(item.plan || 'starter')}}<div class="small">${{esc(item.subscription_status || 'trial')}}</div></td><td><span class="small">${{esc(item.updated_at || '')}}</span></td><td class="actions"><a href="/dashboard?tenant_id=${{encodeURIComponent(item.tenant_id)}}">dashboard</a><a href="/tenant/config/ui?tenant_id=${{encodeURIComponent(item.tenant_id)}}">config</a><a href="/tenant/overview?tenant_id=${{encodeURIComponent(item.tenant_id)}}">overview</a></td>`;
    tb.appendChild(tr);
  }});
}}
document.addEventListener('DOMContentLoaded', loadTenants);
</script>
</body>
</html>
    """
    return HTMLResponse(content=html)


@app.get("/tenant/config")
def tenant_config(tenant_id: str = TENANT_ID_DEFAULT):
    tenant = get_tenant((tenant_id or "").strip() or TENANT_ID_DEFAULT)
    if not tenant.get("_id"):
        raise HTTPException(status_code=404, detail="Tenant not found")
    settings = tenant_settings(tenant, get_lang(tenant.get("language") or "lv"))
    routes = []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT phone_number, tenant_id, updated_at FROM phone_routes WHERE tenant_id=:tenant_id ORDER BY updated_at DESC NULLS LAST, phone_number ASC"),
                {"tenant_id": tenant.get("_id")},
            ).fetchall()
        for r in rows:
            routes.append({
                "phone_number": r[0],
                "tenant_id": r[1],
                "updated_at": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
            })
    except Exception:
        routes = []
    return {
        "tenant": _jsonable_tenant_view(tenant),
        "resolved_settings": settings,
        "phone_routes": routes,
        "onboarding": onboarding_status_payload(tenant),
        "readiness": tenant_ready_status_payload(tenant),
        "plan_meta": tenant_plan_meta(tenant),
        "links": onboarding_links_payload(str(tenant.get("_id") or tenant_id)),
    }

@app.post("/tenant/config/update")
def tenant_config_update(payload: TenantConfigUpdateRequest):
    tenant_id = (payload.tenant_id or "").strip()
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id required")
    tenant = get_tenant(tenant_id)
    if not tenant.get("_id"):
        raise HTTPException(status_code=404, detail="Tenant not found")

    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = {c["name"] for c in cols}

    updates = []
    params: Dict[str, Any] = {"tid": tenant_id}

    def add_field(field_name: str, value):
        if field_name in col_names and value is not None:
            updates.append(f"{field_name}=:{field_name}")
            params[field_name] = value

    add_field("business_name", payload.business_name.strip() if isinstance(payload.business_name, str) and payload.business_name.strip() else payload.business_name)
    add_field("phone_number", normalize_incoming_to_number(payload.phone_number or "") or None)
    add_field("timezone", payload.timezone.strip() if isinstance(payload.timezone, str) and payload.timezone.strip() else payload.timezone)
    add_field("language", get_lang(payload.language) if payload.language is not None else None)
    clean_work_start = payload.work_start.strip() if isinstance(payload.work_start, str) and payload.work_start.strip() else payload.work_start
    clean_work_end = payload.work_end.strip() if isinstance(payload.work_end, str) and payload.work_end.strip() else payload.work_end

    add_field("work_start", clean_work_start)
    add_field("work_end", clean_work_end)
    add_field("services_lv", payload.services_lv)
    add_field("services_ru", payload.services_ru)
    add_field("services_en", payload.services_en)

    weekly_hours_value = payload.weekly_hours_json
    if weekly_hours_value is None and (((isinstance(clean_work_start, str) and clean_work_start.strip()) or (isinstance(clean_work_end, str) and clean_work_end.strip()))):
        weekly_hours_value = tenant.get("weekly_hours_json")
    if weekly_hours_value is not None:
        weekly_hours_value = _sync_weekly_hours_with_fallback_bounds(
            weekly_hours_value,
            clean_work_start,
            clean_work_end,
        )
    add_field("weekly_hours_json", weekly_hours_value)
    add_field("days_off_json", payload.days_off_json)
    add_field("breaks_json", payload.breaks_json)
    add_field("holidays_json", payload.holidays_json)
    add_field("min_notice_minutes", payload.min_notice_minutes)
    add_field("buffer_minutes", payload.buffer_minutes)
    add_field("business_memory_lv", payload.business_memory_lv)
    add_field("business_memory_ru", payload.business_memory_ru)
    add_field("business_memory_en", payload.business_memory_en)
    # support either service_catalog_json or service_catalog depending on schema
    if payload.service_catalog_json is not None:
        if "service_catalog_json" in col_names:
            add_field("service_catalog_json", payload.service_catalog_json)
        elif "service_catalog" in col_names:
            add_field("service_catalog", payload.service_catalog_json)
    if payload.service_account_json is not None:
        clean_service_account_json = payload.service_account_json.strip() if isinstance(payload.service_account_json, str) else payload.service_account_json
        if "service_account_json" in col_names:
            add_field("service_account_json", clean_service_account_json or None)
        elif "google_service_account_json" in col_names:
            add_field("google_service_account_json", clean_service_account_json or None)

    if "updated_at" in col_names:
        updates.append("updated_at=NOW()")

    if updates:
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE tenants SET {', '.join(updates)} WHERE {pk}=:tid"),
                params,
            )

    new_phone = normalize_incoming_to_number(payload.phone_number or "")
    if new_phone:
        upsert_phone_route(new_phone, tenant_id)

    updated = get_tenant(tenant_id)
    return {
        "status": "ok",
        "tenant": _jsonable_tenant_view(updated),
        "resolved_settings": tenant_settings(updated, get_lang(updated.get("language") or "lv")),
        "onboarding": onboarding_status_payload(updated),
        "readiness": tenant_ready_status_payload(updated),
        "plan_meta": tenant_plan_meta(updated),
        "links": onboarding_links_payload(tenant_id),
    }

@app.get("/tenant/routes")
def tenant_routes(tenant_id: str = TENANT_ID_DEFAULT):
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT phone_number, tenant_id, updated_at FROM phone_routes WHERE tenant_id=:tenant_id ORDER BY updated_at DESC NULLS LAST, phone_number ASC"),
            {"tenant_id": tenant_id},
        ).fetchall()
    items = []
    for r in rows:
        items.append({
            "phone_number": r[0],
            "tenant_id": r[1],
            "updated_at": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
        })
    return {"tenant_id": tenant_id, "items": items}

@app.get("/dev_rules")
def dev_rules(tenant_id: str):
    tenant = get_tenant((tenant_id or "").strip() or TENANT_ID_DEFAULT)
    settings = tenant_settings(tenant, get_lang(tenant.get("language") or "lv"))
    return {
        "tenant_id": tenant.get("_id"),
        "work_start": settings.get("work_start"),
        "work_end": settings.get("work_end"),
        "business_rules": settings.get("business_rules"),
        "min_notice_minutes": (settings.get("business_rules") or {}).get("min_notice_minutes"),
        "buffer_minutes": (settings.get("business_rules") or {}).get("buffer_minutes"),
    }


@app.get("/dev_logs")
def dev_logs(tenant_id: str, limit: int = 50):
    limit = max(1, min(int(limit or 50), 200))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, tenant_id, user_id, channel, intent, service, datetime_iso, status, raw_text, created_at
                FROM call_logs
                WHERE tenant_id=:tenant_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"tenant_id": tenant_id, "limit": limit},
        ).fetchall()
    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "tenant_id": r[1],
            "user_id": r[2],
            "channel": r[3],
            "intent": r[4],
            "service": r[5],
            "datetime_iso": r[6],
            "status": r[7],
            "raw_text": r[8],
            "created_at": r[9].isoformat() if hasattr(r[9], "isoformat") else str(r[9]),
        })
    return {"items": items}


# =========================
# DEV LOCAL CHAT (no Twilio cost)
# =========================
from pydantic import BaseModel

class DevChatRequest(BaseModel):
    tenant_id: str
    user_id: str
    message: str
    channel: str = "dev"
    lang: str = "lv"

class DevResetRequest(BaseModel):
    tenant_id: str
    user_id: str

def _dev_raw_user(user_id: str) -> str:
    uid = (user_id or "dev_user").strip()
    return f"dev:{uid}"

@app.post("/dev_chat")
async def dev_chat(req: DevChatRequest):
    try:
        raw_user = _dev_raw_user(req.user_id)
        result = handle_user_text_with_logging(
            tenant_id=req.tenant_id,
            raw_phone=raw_user,
            text_in=req.message,
            channel=req.channel,
            lang_hint=req.lang,
        )
        conv = db_get_or_create_conversation(req.tenant_id, raw_user, req.lang)
        return {
            "status": result.get("status"),
            "reply": result.get("msg_out") or result.get("reply_voice") or "",
            "lang": result.get("lang"),
            "state": conv.get("state"),
            "pending": conv.get("pending"),
            "service": conv.get("service"),
            "datetime_iso": conv.get("datetime_iso"),
            "name": conv.get("name"),
        }
    except Exception as e:
        log.exception("DEV CHAT ERROR")
        return {
            "status": "error",
            "reply": f"DEV_CHAT_ERROR: {str(e)}",
            "lang": get_lang(req.lang),
            "state": None,
            "pending": None,
            "service": None,
            "datetime_iso": None,
            "name": None,
        }


@app.post("/dev_reset")
async def dev_reset(req: DevResetRequest):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                delete from conversations
                where tenant_id = :tenant_id
                and user_key = :user_key
                """),
                {
                    "tenant_id": req.tenant_id,
                    "user_key": norm_user_key(_dev_raw_user(req.user_id))
                }
            )
        return {"status": "reset_ok"}
    except Exception as e:
        log.exception("DEV RESET ERROR")
        raise HTTPException(status_code=500, detail=str(e))



class DevFocusTestRequest(BaseModel):
    tenant_id: str
    user_id: str = "focus_runner"
    lang: str = "lv"
    cases: Optional[List[str]] = None


@app.post("/dev_understand")
async def dev_understand(req: DevChatRequest):
    tenant = get_tenant(req.tenant_id)
    lang = get_lang(req.lang)
    settings = tenant_settings(tenant, lang)
    service_catalog = tenant_service_catalog(tenant)
    service_aliases = ensure_default_barbershop_aliases(
        service_catalog,
        merged_service_alias_map(service_catalog, tenant, lang),
        lang,
    )
    business_memory = tenant_business_memory(tenant, lang)
    understood = llm_message_understanding(
        msg=req.message,
        lang=lang,
        settings=settings,
        service_catalog=service_catalog,
        service_aliases=service_aliases,
        business_memory=business_memory,
    )
    return {"tenant_id": req.tenant_id, "message": req.message, "understanding": understood}


@app.post("/dev_focus_test")
async def dev_focus_test(req: DevFocusTestRequest):
    tenant = get_tenant(req.tenant_id)
    lang = get_lang(req.lang)
    cases = req.cases or [
        "Labdien, gribu pierakstīties",
        "Vai ir kaut kas vakarā?",
        "Man vajag rīt pēc 18",
        "Varu tikai brīvdienās",
        "Nevajag, atstājam esošo pierakstu",
        "Atcelt manu pierakstu",
    ]
    settings = tenant_settings(tenant, lang)
    service_catalog = tenant_service_catalog(tenant)
    service_aliases = ensure_default_barbershop_aliases(
        service_catalog,
        merged_service_alias_map(service_catalog, tenant, lang),
        lang,
    )
    business_memory = tenant_business_memory(tenant, lang)
    raw_user = _dev_raw_user(req.user_id)
    items = []
    for case in cases:
        understood = llm_message_understanding(
            msg=case,
            lang=lang,
            settings=settings,
            service_catalog=service_catalog,
            service_aliases=service_aliases,
            business_memory=business_memory,
        )
        result = handle_user_text_with_logging(
            tenant_id=req.tenant_id,
            raw_phone=raw_user,
            text_in=case,
            channel="dev",
            lang_hint=lang,
        )
        conv = db_get_or_create_conversation(req.tenant_id, raw_user, lang)
        items.append({
            "input": case,
            "intent": understood.get("intent"),
            "confidence": understood.get("confidence"),
            "entities": {
                "service": understood.get("service"),
                "datetime_iso": understood.get("datetime_iso"),
                "time_text": understood.get("time_text"),
                "name": understood.get("name"),
                "confirmation": understood.get("confirmation"),
            },
            "response": result.get("msg_out") or result.get("reply_voice"),
            "status": result.get("status"),
            "state": conv.get("state"),
            "success": bool(result.get("status") not in {"blocked", "booking_failed"}),
        })
    return {"tenant_id": req.tenant_id, "lang": lang, "items": items}

@app.get("/dev_chat_ui", response_class=HTMLResponse)
def dev_chat_ui():
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Repliq Dev Chat</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 0; background: #f6f7fb; color: #1f2937; }
    .wrap { max-width: 900px; margin: 0 auto; padding: 20px; }
    .panel { background: white; border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); padding: 16px; }
    .top { display: grid; grid-template-columns: 1fr 1fr 120px 120px; gap: 12px; margin-bottom: 16px; }
    input, select, textarea, button { font: inherit; }
    input, select { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 10px; box-sizing: border-box; }
    .chat { height: 480px; overflow-y: auto; background: #fafafa; border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px; }
    .msg { margin: 10px 0; display: flex; }
    .msg.user { justify-content: flex-end; }
    .bubble { max-width: 72%; padding: 10px 12px; border-radius: 14px; line-height: 1.4; white-space: pre-wrap; }
    .user .bubble { background: #2563eb; color: white; border-bottom-right-radius: 4px; }
    .bot .bubble { background: #e5e7eb; color: #111827; border-bottom-left-radius: 4px; }
    .meta { font-size: 12px; color: #6b7280; margin-top: 4px; }
    .composer { display: grid; grid-template-columns: 1fr 120px 120px; gap: 12px; margin-top: 16px; }
    textarea { width: 100%; height: 64px; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 10px; resize: vertical; box-sizing: border-box; }
    button { border: none; border-radius: 10px; padding: 10px 14px; cursor: pointer; }
    .send { background: #111827; color: white; }
    .reset { background: #fee2e2; color: #991b1b; }
    .hint { margin-top: 10px; font-size: 13px; color: #6b7280; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <div class="top">
        <input id="tenant" placeholder="tenant_id" value="default" />
        <input id="user" placeholder="user_id" value="local_test_1" />
        <select id="lang">
          <option value="lv">lv</option>
          <option value="ru">ru</option>
          <option value="en">en</option>
        </select>
        <select id="channel">
          <option value="dev">dev</option>
          <option value="whatsapp">whatsapp</option>
          <option value="sms">sms</option>
          <option value="voice">voice</option>
        </select>
      </div>

      <div id="chat" class="chat"></div>

      <div class="composer">
        <textarea id="message" placeholder="Type a test message..."></textarea>
        <button class="send" onclick="sendMessage()">Send</button>
        <button class="reset" onclick="resetChat()">Reset</button>
      </div>

      <div class="hint">Use the same tenant_id + user_id to preserve conversation state between messages.</div>
    </div>
  </div>

  <script>
    const chat = document.getElementById('chat');
    const messageInput = document.getElementById('message');

    function addBubble(role, text, meta = '') {
      const row = document.createElement('div');
      row.className = `msg ${role}`;
      const wrap = document.createElement('div');
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = text;
      wrap.appendChild(bubble);
      if (meta) {
        const metaDiv = document.createElement('div');
        metaDiv.className = 'meta';
        metaDiv.textContent = meta;
        wrap.appendChild(metaDiv);
      }
      row.appendChild(wrap);
      chat.appendChild(row);
      chat.scrollTop = chat.scrollHeight;
    }

    async function sendMessage() {
      const tenant_id = document.getElementById('tenant').value.trim();
      const user_id = document.getElementById('user').value.trim();
      const lang = document.getElementById('lang').value;
      const channel = document.getElementById('channel').value;
      const message = messageInput.value.trim();
      if (!tenant_id || !user_id || !message) return;

      addBubble('user', message);
      messageInput.value = '';

      const resp = await fetch('/dev_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tenant_id, user_id, message, lang, channel })
      });
      const data = await resp.json();
      const meta = `status=${data.status || ''} | state=${data.state || ''}`;
      addBubble('bot', data.reply || '(no reply)', meta);
    }

    async function resetChat() {
      const tenant_id = document.getElementById('tenant').value.trim();
      const user_id = document.getElementById('user').value.trim();
      if (!tenant_id || !user_id) return;
      await fetch('/dev_reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tenant_id, user_id })
      });
      chat.innerHTML = '';
      addBubble('bot', 'Conversation reset.', 'dev');
    }

    messageInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  </script>
</body>
</html>
    """
    return HTMLResponse(content=html)


# -------------------------
# HOLIDAYS SUPPORT (2.2)
# -------------------------
def parse_holidays(tenant: dict):
    try:
        raw = tenant.get("holidays_json") or tenant.get("holidays")
        if not raw:
            return set()
        if isinstance(raw, str):
            raw = json.loads(raw)
        return set(str(x).strip() for x in raw if str(x).strip())
    except Exception:
        return set()

def is_holiday(check_date: date, tenant: dict):
    holidays = parse_holidays(tenant)
    return check_date.strftime("%Y-%m-%d") in holidays

def is_holiday_for_rules(dt_value: datetime, business_rules: Optional[Dict[str, Any]] = None) -> bool:
    if not business_rules:
        return False
    holidays = business_rules.get("holidays") or []
    return dt_value.strftime("%Y-%m-%d") in holidays


def is_closed_day_for_rules(dt_value: datetime, business_rules: Optional[Dict[str, Any]] = None) -> bool:
    if not business_rules:
        return False
    if is_holiday_for_rules(dt_value, business_rules):
        return True
    weekly_hours = (business_rules.get("weekly_hours") or {})
    weekday_key = _weekday_key_for_date(dt_value)
    rule_hours = weekly_hours.get(weekday_key)
    if not rule_hours:
        return True
    if isinstance(rule_hours, (list, tuple)) and len(rule_hours) >= 2:
        start_hhmm = str(rule_hours[0] or "").strip()
        end_hhmm = str(rule_hours[1] or "").strip()
        if not start_hhmm or not end_hhmm:
            return True
    return False


def min_notice_cutoff(business_rules: Optional[Dict[str, Any]] = None) -> Optional[datetime]:
    mins = _safe_int((business_rules or {}).get("min_notice_minutes"), 0)
    if mins <= 0:
        return None
    return now_ts() + timedelta(minutes=mins)

def violates_min_notice(dt_value: datetime, business_rules: Optional[Dict[str, Any]] = None) -> bool:
    cutoff = min_notice_cutoff(business_rules)
    if cutoff is None:
        return False
    return dt_value < cutoff


def exchange_code_for_tokens(*args, **kwargs):
    pass


def get_current_tenant(*args, **kwargs):
    pass


def save_tokens(*args, **kwargs):
    pass


def mark_onboarding_completed(*args, **kwargs):
    pass
