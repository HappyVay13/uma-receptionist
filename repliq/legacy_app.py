import os
import json
import re
import ast
import base64
import uuid
import logging
import random
import unicodedata
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, Tuple, List
from contextvars import ContextVar

import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.responses import Response, StreamingResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from sqlalchemy import text

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config.settings import (
    ALLOW_DEFAULT_TENANT_FALLBACK,
    APPT_MINUTES,
    AUTO_SEND_CONFIRMATION_FOR_TEXT_CHANNELS,
    BOOKING_CONFIRMATION_ENABLED,
    BUSINESS_BREAKS_JSON,
    BUSINESS_BUFFER_MINUTES,
    BUSINESS_DAYS_OFF,
    BUSINESS_FALLBACK,
    BUSINESS_MIN_NOTICE_MINUTES,
    BUSINESS_WEEKLY_HOURS_JSON,
    CLIENT_STATUS_FALLBACK,
    ELEVENLABS_API_KEY,
    ELEVENLABS_MODEL_ID,
    ELEVENLABS_VOICE_ID,
    GOOGLE_CALENDAR_ID_FALLBACK,
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET,
    GOOGLE_OAUTH_REDIRECT_URI,
    GOOGLE_OAUTH_SCOPE,
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_TTS_LANGUAGE_CODE,
    GOOGLE_TTS_VOICE_NAME,
    LLM_INTELLIGENCE_ENABLED,
    LLM_INTENT_MIN_CONFIDENCE,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    RECOVERY_BOOKING_LINK,
    SERVER_BASE_URL,
    TENANT_ID_DEFAULT,
    TEST_TENANT_ID,
    TRIAL_END_ISO_FALLBACK,
    TWILIO_ACCOUNT_SID,
    TWILIO_API_KEY_SECRET,
    TWILIO_API_KEY_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_FROM_NUMBER,
    TWILIO_TWIML_APP_SID,
    TWILIO_VALIDATE_SIGNATURE,
    TWILIO_WHATSAPP_FROM,
    TZ,
    VOICE_CLIENT_TENANT_MAP,
    VOICE_DEMO_TENANT_ID,
    VOICE_SDK_ORIGINS,
    WORK_END_HHMM_DEFAULT,
    WORK_START_HHMM_DEFAULT,
    get_sentry_middleware_class,
)
from core.i18n import I18N, t
from core.language import (
    BOOKING_OPENERS,
    GREETING_PATTERNS,
    HOURS_PATTERNS,
    IDENTITY_CHECK_PATTERNS,
    LANG_HINTS,
    detect_language,
    detect_language_choice,
    detect_language_scores,
    get_lang,
    is_booking_opener,
    is_greeting_only,
    is_hours_question,
    is_identity_check,
    resolve_reply_language,
    stt_locale_for_lang,
    tokenize_lang_text,
    tts_language_code_for_lang,
)
from core.parsing_time import (
    NATURAL_TIME_DEFAULTS,
    WEEKDAY_HINTS,
    _contains_any_phrase,
    _parse_hhmm,
    _phrase_in_text,
    combine_date_with_explicit_time,
    detect_time_bucket,
    format_dt_short,
    has_date_reference,
    has_explicit_time,
    has_natural_time_hint,
    next_weekday_date,
    now_ts,
    parse_date_only_text,
    parse_dt_any_tz,
    parse_dt_from_iso_or_fallback,
    parse_explicit_time_parts,
    parse_natural_datetime,
    parse_time_text_to_dt,
    parse_time_window,
    pending_time_window_tuple,
    sanitize_conversation_time_text,
    today_local,
)
from db.database import engine  # expects engine in db/database.py
from db.conversations import db_get_or_create_conversation, db_save_conversation
from db.runtime_tables import ensure_call_logs_table, ensure_phone_routes_table, ensure_usage_events_table
from integrations.twilio_client import send_message
from integrations.twilio_validation import install_twilio_signature_middleware
from channels.telegram import (
    handle_telegram_incoming,
    telegram_config_status,
    telegram_set_webhook_request,
)

log = logging.getLogger("repliq")

app = FastAPI()
_sentry_middleware_class = get_sentry_middleware_class()
if _sentry_middleware_class is not None:
    app.add_middleware(_sentry_middleware_class)

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
    service_text = text_mvp_localized_service_name(result.get("service") or pending.get("service_display") or "", lang)
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
# STAGE 25 — AI RESPONSE COMPOSER
# -------------------------
def ai_response_composer_enabled(channel: str = "", source: str = "runtime") -> bool:
    flag = os.getenv("AI_RESPONSE_COMPOSER_ENABLED", "").strip().lower()
    if flag in {"0", "false", "no", "off", "disabled"}:
        return False
    if flag in {"1", "true", "yes", "on", "enabled"}:
        return bool(OPENAI_API_KEY)
    # Default: follow the existing LLM intelligence switch.
    return bool(LLM_INTELLIGENCE_ENABLED and OPENAI_API_KEY)


def _safe_compose_text(value: Any, max_len: int = 900) -> str:
    txt = str(value or "").strip()
    if not txt:
        return ""
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:max_len]


def _composer_allowed_for_result(result: Dict[str, Any]) -> bool:
    status = str((result or {}).get("status") or "").strip().lower()
    if not status:
        return False
    # Do not rewrite account/system blocking or deliberately preserved technical recovery text.
    if status in {"blocked"}:
        return False
    if (result or {}).get("preserve_text") or (result or {}).get("flow_preserved"):
        return False
    base_text = str((result or {}).get("msg_out") or (result or {}).get("reply_voice") or "").strip()
    if not base_text:
        return False
    return status in {
        "greeting",
        "identity",
        "info",
        "need_more",
        "busy",
        "holiday_closed",
        "min_notice",
        "reschedule_wait",
        "booked",
        "booking_failed",
        "recovery",
    }


def _composer_style_for_lang(lang: str) -> str:
    lang = get_lang(lang)
    if lang == "ru":
        return "Пиши на русском. Тон: живой, спокойный, как администратор салона. Без канцелярита."
    if lang == "en":
        return "Write in English. Tone: warm, concise, and receptionist-like. No corporate wording."
    return "Raksti latviski. Tonis: dzīvs, mierīgs un pieklājīgs kā salona administratoram. Bez formālas, robotiskas valodas."


def ai_response_composer(
    result: Dict[str, Any],
    conv: Optional[Dict[str, Any]],
    tenant: Dict[str, Any],
    channel: str = "",
    source: str = "runtime",
) -> Dict[str, Any]:
    """Rewrite only the final customer-facing text.

    Safety contract:
    - never changes status, state, service, datetime, offered slots, or booking actions;
    - falls back to the current rule-based text on any error;
    - usage warnings are added after this layer, so AI cannot rewrite billing/limit notices.
    """
    result = dict(result or {})
    if not ai_response_composer_enabled(channel, source):
        return result
    if not _composer_allowed_for_result(result):
        return result

    conv = conv or {}
    tenant = tenant or {}
    lang = get_lang(result.get("lang") or conv.get("lang") or tenant.get("language") or "lv")
    state = conversation_state(conv)
    pending = conv.get("pending") or {}
    base_text = str(result.get("msg_out") or result.get("reply_voice") or "").strip()
    if not base_text:
        return result

    offered_slots = _slot_labels_from_pending(pending)
    settings = tenant_settings(tenant, lang)
    memory = tenant_business_memory(tenant, lang)

    composer_payload = {
        "language": lang,
        "channel": str(channel or "").strip().lower() or "unknown",
        "status": str(result.get("status") or "").strip(),
        "state": state,
        "business_name": _safe_compose_text(settings.get("biz_name"), 120),
        "business_type": _safe_compose_text(settings.get("business_type"), 80),
        "current_reply": _safe_compose_text(base_text, 900),
        "service": _safe_compose_text(result.get("service") or result.get("service_display") or pending.get("service_display") or conv.get("service"), 160),
        "when": _safe_compose_text(result.get("when") or result.get("datetime_text") or conv.get("datetime_iso"), 160),
        "offered_slots": offered_slots[:3],
        "pending_keys": sorted([str(k) for k in pending.keys()])[:30] if isinstance(pending, dict) else [],
        "business_memory": _safe_compose_text(memory, 700),
    }

    system_prompt = (
        "You are the Stage 25 AI Response Composer for Repliq, an AI receptionist SaaS. "
        "Your only job is to rewrite the already-decided customer-facing reply so it sounds natural and human. "
        "Never change facts, dates, times, services, prices, offered slots, booking status, or the question being asked. "
        "Do not add new times, do not invent availability, do not promise actions that are not in current_reply. "
        "Keep the reply concise: usually 1 sentence, maximum 2 short sentences. "
        "Return strict JSON only with this key: msg_out. "
        + _composer_style_for_lang(lang)
    )
    user_prompt = json.dumps(composer_payload, ensure_ascii=False, default=str)

    try:
        raw = openai_chat_json(system_prompt, user_prompt)
        composed = str((raw or {}).get("msg_out") or "").strip()
        composed = re.sub(r"\s+\n", "\n", composed).strip()
        if not composed:
            return result
        if len(composed) > 500:
            return result
        # Guardrail: if the original answer contained concrete offered slots, the composed answer must preserve them.
        for slot_label in offered_slots[:3]:
            if slot_label and slot_label not in composed and slot_label in base_text:
                return result
        result["msg_out"] = composed
        result["reply_voice"] = composed
        result["ai_composed"] = True
        result["ai_composer_stage"] = "stage_25"
        return result
    except Exception as e:
        log.error("ai_response_composer_failed err=%s", e)
        return result


# -------------------------
# STAGE 25.5 — CONVERSATIONAL CLOSURE LAYER
# -------------------------
def _closure_normalized_text(text_: Optional[str]) -> str:
    low = _normalize_phrase_text(text_)
    low = low.replace("🙏", "").replace("🙂", "").replace("😊", "").strip()
    return re.sub(r"\s+", " ", low).strip()


def is_thank_you_text(text_: Optional[str], lang: str) -> bool:
    low = _closure_normalized_text(text_)
    if not low:
        return False
    phrases = {
        "lv": {"paldies", "liels paldies", "paldies jums", "paldies tev", "super paldies", "ok paldies", "labi paldies"},
        "ru": {"спасибо", "спасибо вам", "большое спасибо", "спс", "благодарю", "ок спасибо", "хорошо спасибо"},
        "en": {"thanks", "thank you", "thank you very much", "many thanks", "ok thanks", "great thanks"},
    }
    allowed = set().union(*phrases.values())
    allowed.update(phrases.get(get_lang(lang), set()))
    if low in allowed:
        return True
    return any(low.startswith(p + " ") or low.endswith(" " + p) for p in allowed if p)


def is_goodbye_text(text_: Optional[str], lang: str) -> bool:
    low = _closure_normalized_text(text_)
    if not low:
        return False
    phrases = {
        "lv": {"atā", "ata", "uz redzēšanos", "uz redzesanos", "visu labu", "līdz vēlākam", "lidz velakam"},
        "ru": {"пока", "до свидания", "до встречи", "всего доброго", "хорошего дня"},
        "en": {"bye", "goodbye", "see you", "see you soon", "have a nice day"},
    }
    allowed = set().union(*phrases.values())
    allowed.update(phrases.get(get_lang(lang), set()))
    return low in allowed or any(low.startswith(p + " ") for p in allowed if p)


def is_positive_closure_ack_text(text_: Optional[str], lang: str) -> bool:
    low = _closure_normalized_text(text_)
    if not low:
        return False
    phrases = {
        "lv": {"labi", "super", "skaidrs", "forši", "forsi", "ok", "okej", "ideāli", "ideali"},
        "ru": {"ок", "хорошо", "супер", "понял", "поняла", "отлично", "ладно"},
        "en": {"ok", "okay", "great", "perfect", "sounds good", "got it", "alright"},
    }
    allowed = set().union(*phrases.values())
    allowed.update(phrases.get(get_lang(lang), set()))
    return low in allowed


def closure_reply_text(lang: str, closure_type: str, conv: Optional[Dict[str, Any]] = None, tenant: Optional[Dict[str, Any]] = None) -> str:
    lang = get_lang(lang)
    conv = conv or {}
    tenant = tenant or {}
    dtv = parse_dt_any_tz(str(conv.get("datetime_iso") or "").strip())
    when_text = format_dt_short(dtv) if dtv else ""
    state = conversation_state(conv)

    if state == STATE_BOOKED and when_text:
        if lang == "ru":
            if closure_type == "goodbye":
                return f"До встречи! Ждём вас {when_text}."
            return f"Пожалуйста! Ждём вас {when_text}."
        if lang == "en":
            if closure_type == "goodbye":
                return f"See you then! We’ll be expecting you on {when_text}."
            return f"You’re welcome! We’ll be expecting you on {when_text}."
        if closure_type == "goodbye":
            return f"Uz tikšanos! Gaidīsim jūs {when_text}."
        return f"Lūdzu! Gaidīsim jūs {when_text}."

    if state == STATE_CANCELLED:
        if lang == "ru":
            return "Пожалуйста! Если понадобится новая запись, напишите — помогу подобрать время."
        if lang == "en":
            return "You’re welcome! If you need a new appointment, just message me and I’ll help."
        return "Lūdzu! Ja vajadzēs jaunu pierakstu, uzrakstiet — palīdzēšu atrast laiku."

    if closure_type == "goodbye":
        if lang == "ru":
            return "До свидания! Хорошего дня."
        if lang == "en":
            return "Goodbye! Have a nice day."
        return "Uz redzēšanos! Lai jauka diena."

    if lang == "ru":
        return "Пожалуйста! Рад помочь."
    if lang == "en":
        return "You’re welcome! Happy to help."
    return "Lūdzu! Prieks palīdzēt."


def maybe_conversational_closure_result(
    tenant_id: str,
    user_key: str,
    msg: str,
    lang: str,
    conv: Dict[str, Any],
    tenant: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not (msg or "").strip():
        return None

    state = conversation_state(conv or {})
    pending = (conv or {}).get("pending") or {}

    # Never steal confirmations or active slot/service selection. In active booking
    # states, words like "ok" and "labi" may be real confirmation signals.
    if state in ACTIVE_BOOKING_STATES or state == STATE_POST_BOOKING_UPSELL:
        return None

    closure_type = None
    if is_thank_you_text(msg, lang):
        closure_type = "thanks"
    elif is_goodbye_text(msg, lang):
        closure_type = "goodbye"
    elif state in {STATE_BOOKED, STATE_CANCELLED} and is_positive_closure_ack_text(msg, lang):
        closure_type = "ack"

    if not closure_type:
        return None

    # After booking/cancellation, clear stale pending flags so the next polite
    # message does not accidentally re-open the booking state machine.
    if state in {STATE_BOOKED, STATE_CANCELLED} and pending:
        conv["pending"] = None
        db_save_conversation(tenant_id, user_key, conv)

    reply = closure_reply_text(lang, closure_type, conv, tenant)
    return {
        "status": "info",
        "reply_voice": reply,
        "msg_out": reply,
        "lang": lang,
        "preserve_text": True,
        "closure_type": closure_type,
    }


# -------------------------
# STAGE 33 — SOFT CONVERSATIONAL UX LAYER
# -------------------------
def stage33_soft_ux_enabled(channel: str = "", source: str = "runtime") -> bool:
    flag = os.getenv("STAGE33_SOFT_UX_ENABLED", "").strip().lower()
    if flag in {"0", "false", "no", "off", "disabled"}:
        return False
    return True


def _stage33_join_options(lang: str, items: List[str]) -> str:
    cleaned = [str(x).strip() for x in items if str(x).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    sep = " или " if get_lang(lang) == "ru" else " or " if get_lang(lang) == "en" else " vai "
    return ", ".join(cleaned[:-1]) + sep + cleaned[-1]


def _stage33_when_text(result: Dict[str, Any], conv: Dict[str, Any], pending: Dict[str, Any]) -> str:
    explicit = str((result or {}).get("when") or (result or {}).get("datetime_text") or "").strip()
    if explicit:
        return explicit
    for value in [
        (pending or {}).get("confirm_slot_iso"),
        (pending or {}).get("candidate_datetime_iso"),
        (conv or {}).get("datetime_iso"),
    ]:
        dtv = parse_dt_any_tz(str(value or "").strip())
        if dtv:
            return format_dt_short(dtv)
    return ""


def _stage33_requested_busy_hint(text_: str, lang: str) -> bool:
    low = _normalize_phrase_text(text_)
    folded = _fold_match_text(text_)
    markers = [
        "занято", "занят", "уже занято", "aiznemts", "aizņemts", "nav pieejams",
        "taken", "already taken", "not available", "busy",
    ]
    return any(m in low or m in folded for m in markers)


def stage33_soft_conversational_ux(
    result: Dict[str, Any],
    conv: Optional[Dict[str, Any]],
    tenant: Dict[str, Any],
    channel: str = "",
    source: str = "runtime",
) -> Dict[str, Any]:
    """Final deterministic wording layer for Stage 33.

    Safety contract:
    - only rewrites msg_out/reply_voice;
    - never changes status, state, calendar actions, service, datetime or offered slots;
    - keeps all concrete offered slot labels in the customer-facing reply.
    """
    result = dict(result or {})
    if not stage33_soft_ux_enabled(channel, source):
        return result

    # Stage 46: some upstream actions carry exact, action-specific wording
    # (notably completed reschedules). Preserve those replies so the soft
    # UX layer cannot turn "record moved" into a generic new-booking message.
    if result.get("preserve_text") or result.get("reschedule_finalized"):
        return result

    # Stage 38.3: side-question FAQ answers inside an active booking flow
    # already include both the business-memory answer and the preserved flow
    # follow-up. Do not let the final soft UX layer collapse that combined
    # answer back into a generic slot prompt.
    if result.get("flow_preserved") or result.get("stage38_business_faq"):
        return result

    status = str(result.get("status") or "").strip().lower()
    if status in {"blocked", "booking_failed", "recovery"}:
        return result

    conv = conv or {}
    tenant = tenant or {}
    pending = conv.get("pending") or {}
    lang = get_lang(result.get("lang") or conv.get("lang") or tenant.get("language") or "lv")
    state = conversation_state(conv)
    base_text = str(result.get("msg_out") or result.get("reply_voice") or "").strip()
    slots = _slot_labels_from_pending(pending)
    when_text = _stage33_when_text(result, conv, pending)
    service_text = text_mvp_localized_service_name(result.get("service") or result.get("service_display") or pending.get("service_display") or "", lang)

    def apply(text_value: str) -> Dict[str, Any]:
        text_value = str(text_value or "").strip()
        if not text_value:
            return result
        for slot_label in slots[:4]:
            if slot_label and slot_label not in text_value:
                return result
        result["msg_out"] = text_value
        result["reply_voice"] = text_value
        result["stage33_soft_ux"] = True
        return result

    if status == "booked" and when_text:
        if lang == "ru":
            return apply(_pick_variant([
                f"Готово, записал вас на {when_text}. Будем ждать вас!",
                f"Отлично, запись подтверждена на {when_text}. До встречи!",
                f"Супер, закрепил за вами время {when_text}.",
            ], base_text or f"Запись подтверждена на {when_text}."))
        if lang == "en":
            return apply(_pick_variant([
                f"Done — you’re booked for {when_text}. See you then!",
                f"Great, your appointment is confirmed for {when_text}.",
                f"Perfect, I’ve reserved {when_text} for you.",
            ], base_text or f"Your appointment is confirmed for {when_text}."))
        return apply(_pick_variant([
            f"Gatavs, pierakstīju jūs uz {when_text}. Gaidīsim jūs!",
            f"Lieliski, pieraksts apstiprināts uz {when_text}. Uz tikšanos!",
            f"Super, rezervēju jums laiku {when_text}.",
        ], base_text or f"Pieraksts apstiprināts uz {when_text}."))

    if status in {"need_more", "busy", "min_notice", "holiday_closed"} and state == STATE_AWAITING_TIME and slots:
        joined = _stage33_join_options(lang, slots[:4])
        busy_hint = _stage33_requested_busy_hint(base_text, lang) or status in {"busy", "min_notice", "holiday_closed"}
        if lang == "ru":
            text_value = (
                f"На запрошенное время не получается, но могу предложить: {joined}. Какой вариант вам удобнее?"
                if busy_hint else
                f"Нашёл такие варианты: {joined}. Какой вам больше подходит?"
            )
        elif lang == "en":
            text_value = (
                f"That requested time doesn’t work, but I can offer: {joined}. Which one suits you best?"
                if busy_hint else
                f"I found these options: {joined}. Which one works best for you?"
            )
        else:
            text_value = (
                f"Uz prasīto laiku nesanāk, bet varu piedāvāt: {joined}. Kurš variants jums der?"
                if busy_hint else
                f"Atradu šādus variantus: {joined}. Kurš jums būtu ērtāks?"
            )
        return apply(text_value)

    if status == "need_more" and state == STATE_AWAITING_CONFIRM and when_text:
        if lang == "ru":
            service_part = f" на услугу «{service_text}»" if service_text else ""
            return apply(_pick_variant([
                f"Это время свободно — записываем вас{service_part} на {when_text}?",
                f"Можем поставить запись на {when_text}. Подтверждаем?",
                f"{when_text} подходит — закрепить это время за вами?",
            ], base_text or f"Подтвердить запись на {when_text}?"))
        if lang == "en":
            service_part = f" for {service_text}" if service_text else ""
            return apply(_pick_variant([
                f"That time is available — shall I book you{service_part} for {when_text}?",
                f"We can do {when_text}. Should I confirm it?",
                f"{when_text} works — would you like me to reserve it?",
            ], base_text or f"Confirm the booking for {when_text}?"))
        service_part = f" uz {service_text}" if service_text else ""
        return apply(_pick_variant([
            f"Šis laiks ir pieejams — pierakstām jūs{service_part} uz {when_text}?",
            f"Varam jūs pierakstīt uz {when_text}. Apstiprinām?",
            f"{when_text} der — rezervēt šo laiku jums?",
        ], base_text or f"Apstiprināt pierakstu uz {when_text}?"))

    if status in {"need_more", "busy"} and state == STATE_AWAITING_SERVICE:
        if lang == "ru":
            return apply(_pick_variant([
                "Конечно. Подскажите, какую услугу хотите выбрать?",
                "Хорошо, помогу с записью. Какая услуга нужна?",
                "Давайте подберём время. Сначала уточню услугу — что хотите сделать?",
            ], base_text or "На какую услугу вас записать?"))
        if lang == "en":
            return apply(_pick_variant([
                "Of course. Which service would you like to book?",
                "Sure, I can help with that. What service do you need?",
                "Let’s find a time for you. Which service should I book?",
            ], base_text or "Which service would you like to book?"))
        return apply(_pick_variant([
            "Protams. Kuru pakalpojumu vēlaties izvēlēties?",
            "Labi, palīdzēšu ar pierakstu. Kāds pakalpojums nepieciešams?",
            "Atradīsim jums piemērotu laiku. Vispirms — kuru pakalpojumu vēlaties?",
        ], base_text or "Uz kādu pakalpojumu vēlaties pierakstīties?"))

    if status in {"need_more", "busy"} and state == STATE_AWAITING_DATE:
        if lang == "ru":
            return apply(_pick_variant([
                "Хорошо. На какой день посмотрим запись?",
                "Понял. Какая дата вам была бы удобна?",
                "Давайте подберём день. Когда вам удобнее?",
            ], base_text or "На какой день вас записать?"))
        if lang == "en":
            return apply(_pick_variant([
                "Sure. Which day should I check?",
                "Got it. What date would work for you?",
                "Let’s pick a day first. When would be convenient?",
            ], base_text or "Which day would work for you?"))
        return apply(_pick_variant([
            "Labi. Uz kuru dienu skatāmies pierakstu?",
            "Sapratu. Kurš datums jums būtu ērts?",
            "Vispirms izvēlēsimies dienu. Kad jums būtu ērtāk?",
        ], base_text or "Uz kuru dienu vēlaties pierakstīties?"))

    if status == "reschedule_wait" and when_text:
        if lang == "ru":
            return apply(f"Понял. Сейчас запись стоит на {when_text}. На какое новое время хотите перенести?")
        if lang == "en":
            return apply(f"Understood. Your current appointment is at {when_text}. What new time would work better?")
        return apply(f"Sapratu. Pašlaik pieraksts ir {when_text}. Uz kuru jauno laiku vēlaties pārcelt?")

    return result


# -------------------------
# NEW: MULTI-TENANT DB HELPERS
# -------------------------


def ensure_tenants_lifecycle_columns() -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS subscription_status TEXT"))
            conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS plan TEXT"))
            conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS dialogs_per_month INTEGER"))
            conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS trial_end TIMESTAMPTZ"))
    except Exception as e:
        log.error("ensure_tenants_lifecycle_columns_failed err=%s", e)
def tenants_columns() -> List[Dict[str, Any]]:
    ensure_tenants_lifecycle_columns()
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


def load_runtime_tenant(tenant_id: str) -> Dict[str, Any]:
    """Load an existing tenant for runtime use without auto-creating rows.

    Runtime paths must fail closed for unknown tenant_ids instead of silently
    creating placeholder tenants. This keeps dev_chat/dashboard checks aligned
    with the strict multi-tenant behavior we want in SaaS mode.
    """
    tenant = get_existing_tenant(tenant_id)
    if not tenant:
        return {"_id": None}
    return normalize_tenant_saas_fields(tenant)



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


def tenant_business_memory_all_languages(tenant: Dict[str, Any]) -> List[str]:
    # Stage 41.1: price data can be present in another business-memory language.
    # Example from clinic_demo QA: active RU booking uses service `konsultācija`,
    # while the grounded price line is stored in LV memory as `Konsultācija - 10 eiro`.
    # Keep this as a read-only lookup fallback for grounded FAQ answers only.
    keys = (
        "business_memory_lv", "business_memory_ru", "business_memory_en",
        "faq_lv", "faq_ru", "faq_en",
        "booking_rules_lv", "booking_rules_ru", "booking_rules_en",
        "business_memory", "faq", "booking_rules", "policies",
    )
    seen = set()
    values: List[str] = []
    for key in keys:
        val = tenant.get(key) if tenant else None
        txt = str(val or "").strip()
        if txt and txt not in seen:
            values.append(f"{key}: {txt}")
            seen.add(txt)
    return values


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
        r"(\d+(?:[\.,]\d{1,2})?\s*eiro)",
        r"(\d+(?:[\.,]\d{1,2})?\s*евро)",
    ]
    for pat in patterns:
        m = re.search(pat, src, flags=re.IGNORECASE)
        if m:
            return m.group(1).replace("eur", "EUR").replace("eiro", "eiro")
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
    current_service_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    # Stage 38: Business Memory Intelligence / FAQ Rules Hardening
    # This FAQ helper is intentionally generic now. Earlier versions only
    # answered barbershop FAQ, which made clinic/salon tenants lose side-questions
    # inside booking flows and sometimes reset the booking state. Keep the old
    # function name for compatibility, but use tenant settings, service catalog
    # and business memory for every business type.
    business_type = str(tenant.get("business_type") or settings.get("business_type") or "barbershop").strip().lower()

    low = (msg or "").strip().lower()
    if not low:
        return None

    price_markers = [
        "цена", "сколько стоит", "сколько это стоит", "стоимость",
        "price", "how much", "how much does it cost", "cost",
        "cena", "cik maksā", "cik maksa", "cik tas maksā", "cik tas maksa", "cik tas maksas",
    ]
    location_markers = ["where", "address", "адрес", "где вы", "где находитесь", "kur jūs", "adrese", "kur atrodaties"]
    services_markers = ["какие услуги", "что делаете", "services", "what services", "pakalpojumi", "ko jūs darāt", "ko jus darat"]
    duration_markers = ["сколько по времени", "сколько длится", "how long", "duration", "cik ilgi", "ilgums"]
    hours_markers = [
        "часы", "режим", "до скольки", "когда откры", "когда работает", "работаете",
        "opening hours", "hours", "when are you open", "work hours",
        "darba laiks", "cikos strād", "cikos jūs strād", "cikos jus strad",
        "līdz cikiem", "lidz cikiem", "kad strād", "kad jus strad", "kad jūs strād", "vai strādā"
    ]

    # Stage 38: prefer exact business-memory lines when tenant added them.
    # This keeps answers grounded and avoids hallucinating business rules.
    memory_lines = _line_candidates_from_memory(business_memory)

    if any(x in low for x in hours_markers):
        matched_line = next((ln for ln in memory_lines if any(k in ln.lower() for k in ["darba laiks", "hours", "часы", "режим", "working time"])), None)
        if matched_line:
            text = matched_line
        else:
            start = str(settings.get("work_start") or "09:00").strip()
            end = str(settings.get("work_end") or "18:00").strip()
            if lang == "ru":
                text = f"Обычно мы работаем с {start} до {end}."
            elif lang == "en":
                text = f"We are usually open from {start} to {end}."
            else:
                text = f"Parasti strādājam no {start} līdz {end}."
        return {"status": "info", "reply_voice": text, "msg_out": text, "lang": lang, "stage38_business_faq": True}

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
        # Stage 38.1: side-questions like "cik tas maksā?" often do not repeat
        # the service name. In an active booking flow, use the already selected
        # service so FAQ can answer the price without resetting scheduling context.
        if not service_item and current_service_key:
            current_service_text = str(current_service_key).strip()
            service_item = get_service_item_by_key(service_catalog, current_service_text)
            if not service_item:
                service_item = extract_service_from_text(current_service_text, service_catalog, lang)
        if service_item:
            line = _memory_line_for_service(business_memory, service_item)
            price = _extract_price_from_line(line or "")
            # Stage 41.1: if the current language memory mentions the service
            # but does not contain a price, search the tenant's other language
            # business-memory fields before falling back to an unknown-price answer.
            if not price:
                for memory_blob in tenant_business_memory_all_languages(tenant):
                    candidate_line = _memory_line_for_service(memory_blob, service_item)
                    candidate_price = _extract_price_from_line(candidate_line or "")
                    if candidate_price:
                        line = candidate_line
                        price = candidate_price
                        break
            display = service_display_name(service_item, lang)
            if price:
                price_display = text_mvp_localized_price(price, lang)
                if lang == "ru":
                    text = f"{display} стоит {price_display}."
                elif lang == "en":
                    text = f"{display} costs {price_display}."
                else:
                    text = f"{display} maksā {price_display}."
            else:
                duration = service_duration_min(service_item)
                if lang == "ru":
                    text = f"По услуге {display} лучше уточнить цену у специалиста. По времени это обычно около {duration} минут."
                elif lang == "en":
                    text = f"For {display}, it is best to confirm the price with the business. It usually takes about {duration} minutes."
                else:
                    text = f"Par pakalpojumu {display} cenu vislabāk precizēt uzņēmumā. Parasti tas aizņem apmēram {duration} minūtes."
            return {"status": "info", "reply_voice": text, "msg_out": text, "lang": lang, "stage38_business_faq": True}

        price_line = next((_extract_price_from_line(ln) for ln in memory_lines if _extract_price_from_line(ln)), None)
        if price_line:
            price_display = text_mvp_localized_price(price_line, lang)
            if lang == "ru":
                text = f"Цена начинается от {price_display}. Если скажете услугу, уточню точнее."
            elif lang == "en":
                text = f"Prices start from {price_display}. If you tell me the service, I can be more specific."
            else:
                text = f"Cena sākas no {price_display}. Ja pateiksiet pakalpojumu, precizēšu konkrētāk."
        else:
            options = barber_service_options_text(lang, service_catalog, max_items=3)
            if lang == "ru":
                text = f"По цене лучше уточнить конкретную услугу. Например: {options}." if options else "По цене лучше уточнить конкретную услугу."
            elif lang == "en":
                text = f"For pricing, please specify the service. For example: {options}." if options else "For pricing, please specify the service."
            else:
                text = f"Par cenu vislabāk precizēt konkrētu pakalpojumu. Piemēram: {options}." if options else "Par cenu vislabāk precizēt konkrētu pakalpojumu."
        return {"status": "info", "reply_voice": text, "msg_out": text, "lang": lang, "stage38_business_faq": True}

    # Stage 38: direct memory lookup for simple tenant FAQ lines.
    if memory_lines:
        keywords = [w for w in re.split(r"\W+", low) if len(w) >= 4][:8]
        for line in memory_lines:
            ll = line.lower()
            if keywords and any(k in ll for k in keywords):
                return {"status": "info", "reply_voice": line, "msg_out": line, "lang": lang, "stage38_business_faq": True}

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
    result["stage38_business_faq"] = bool(result.get("stage38_business_faq") or faq_result.get("stage38_business_faq"))
    return result






def ensure_lang_update(tenant_id: str, user_key: str, c: Dict[str, Any], lang: str) -> Dict[str, Any]:
    lang = get_lang(lang)
    if get_lang(c.get("lang")) != lang:
        c["lang"] = lang
        db_save_conversation(tenant_id, user_key, c)
    return c


# -------------------------
# DB helpers moved to db/conversations.py
# -------------------------


# -------------------------
# Runtime table ensure helpers moved to db/runtime_tables.py
# -------------------------


def usage_type_from_event(raw_text: str, result: Dict[str, Any], conv: Optional[Dict[str, Any]] = None) -> str:
    intent = infer_intent_label(raw_text, str((result or {}).get("status") or "").strip(), conv)
    status = str((result or {}).get("status") or "").strip().lower()
    if (result or {}).get("reschedule_finalized") or str((result or {}).get("calendar_action") or "").strip() == "update_event":
        return "reschedule"
    if status == "booked":
        return "booking"
    if intent == "reschedule":
        return "reschedule"
    if intent == "cancel":
        return "cancel"
    if intent == "info" or status == "info":
        return "faq"
    return "message"


def usage_context_is_non_billable(channel: str, source: str = "runtime") -> bool:
    ch = str(channel or "").strip().lower()
    src = str(source or "runtime").strip().lower()
    if ch in {"dev", "test", "debug"}:
        return True
    if src in {"dev", "dev_ui", "test", "debug"}:
        return True
    return False


def usage_event_is_billable(channel: str, source: str = "runtime") -> bool:
    return not usage_context_is_non_billable(channel, source)


def record_usage_event(
    tenant_id: str,
    user_id: str,
    channel: str,
    raw_text: str,
    result: Dict[str, Any],
    conv: Optional[Dict[str, Any]] = None,
    source: str = "runtime",
) -> None:
    try:
        ensure_usage_events_table()
        usage_type = usage_type_from_event(raw_text, result, conv)
        billable = usage_event_is_billable(channel, source)
        status = str((result or {}).get("status") or "").strip() or None
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO usage_events
                    (tenant_id, user_id, channel, usage_type, usage_units, billable, source, status)
                    VALUES
                    (:tenant_id, :user_id, :channel, :usage_type, :usage_units, :billable, :source, :status)
                    """
                ),
                {
                    "tenant_id": (tenant_id or "").strip() or TENANT_ID_DEFAULT,
                    "user_id": norm_user_key(user_id),
                    "channel": (channel or "").strip().lower() or "unknown",
                    "usage_type": usage_type,
                    "usage_units": 1,
                    "billable": billable,
                    "source": (source or "runtime").strip().lower() or "runtime",
                    "status": status,
                },
            )
        log.info("usage_event_written tenant_id=%s user_id=%s channel=%s usage_type=%s billable=%s status=%s", (tenant_id or "").strip() or TENANT_ID_DEFAULT, norm_user_key(user_id), (channel or "").strip().lower() or "unknown", usage_type, billable, status or "")
    except Exception as e:
        log.error("usage_event_write_failed tenant_id=%s user_id=%s err=%s", tenant_id, user_id, e)


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
        if (result or {}).get("reschedule_finalized") or str((result or {}).get("calendar_action") or "").strip() == "update_event":
            intent = "reschedule"
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


# -------------------------
# STAGE 21 — CONVERSATIONAL AUDIT FOUNDATION
# -------------------------
DIALOGUE_TEST_MATRIX: List[Dict[str, Any]] = [
    {"id": "lv_single_booking_full", "category": "single_message_booking", "lang": "lv", "message": "labdien! Es gribu pierakstīties uz konsultāciju uz 16 maiju 16:00", "expected": ["booking", "service", "date", "time"]},
    {"id": "lv_services_faq", "category": "faq_services", "lang": "lv", "message": "kādi pakalpojumi jums ir?", "expected": ["info", "services"]},
    {"id": "lv_price_generic", "category": "faq_price", "lang": "lv", "message": "cik maksā?", "expected": ["info", "price_clarify"]},
    {"id": "lv_price_specific", "category": "faq_price", "lang": "lv", "message": "cik maksā konsultācija?", "expected": ["info", "price"]},
    {"id": "lv_today_free", "category": "natural_availability", "lang": "lv", "message": "hej, jums šodien ir kas brīvs?", "expected": ["availability", "natural"]},
    {"id": "lv_after_work", "category": "time_window", "lang": "lv", "message": "var pēc darba?", "expected": ["time_window", "evening"]},
    {"id": "ru_single_booking", "category": "single_message_booking", "lang": "ru", "message": "Здравствуйте, можно записаться на консультацию завтра в 15:00?", "expected": ["booking", "service", "date", "time"]},
    {"id": "ru_price", "category": "faq_price", "lang": "ru", "message": "сколько стоит консультация?", "expected": ["info", "price"]},
    {"id": "en_single_booking", "category": "single_message_booking", "lang": "en", "message": "Hi, I want to book a consultation tomorrow at 3 pm", "expected": ["booking", "service", "date", "time"]},
    {"id": "mixed_lang", "category": "language_switch", "lang": "lv", "message": "Labdien, можно консультацию завтра?", "expected": ["booking", "mixed_language"]},
    {"id": "typo_booking", "category": "typo", "lang": "lv", "message": "gribetuu konsulatciju rit 15", "expected": ["booking", "typo_tolerant"]},
    {"id": "interrupt_price", "category": "faq_during_booking", "lang": "lv", "message": "a cik tas maksā?", "expected": ["info", "preserve_flow"]},
]




# -------------------------
# STAGE 34 — PRODUCTION REGRESSION TEST MATRIX
# -------------------------
STAGE34_REGRESSION_TEST_MATRIX: List[Dict[str, Any]] = [
    {
        "id": "stage30_ru_after_1400_window",
        "stage": 30,
        "lang": "ru",
        "category": "after_time_window",
        "message_sequence": ["хочу записаться на консультацию на послезавтра после 14:00"],
        "expected": ["booking_flow", "time_window_after_14", "multiple_slot_options", "no_exact_14_confirmation"],
        "forbidden": ["confirm_exact_14_00", "ask_service_again", "language_switch_to_lv"],
    },
    {
        "id": "stage30_lv_after_1400_window",
        "stage": 30,
        "lang": "lv",
        "category": "after_time_window",
        "message_sequence": ["gribu pierakstīties uz konsultāciju parīt pēc 14:00"],
        "expected": ["booking_flow", "time_window_after_14", "multiple_slot_options"],
        "forbidden": ["confirm_exact_14_00", "ask_service_again", "language_switch_to_ru"],
    },
    {
        "id": "stage31_ru_evening_fuzzy",
        "stage": 31,
        "lang": "ru",
        "category": "fuzzy_time_window",
        "message_sequence": ["хочу записаться на консультацию завтра вечером"],
        "expected": ["evening_window", "multiple_slot_options", "no_exact_default_time"],
        "forbidden": ["ask_date_again", "ask_service_again", "morning_slots_only"],
    },
    {
        "id": "stage31_lv_evening_fuzzy",
        "stage": 31,
        "lang": "lv",
        "category": "fuzzy_time_window",
        "message_sequence": ["gribu pierakstīties uz konsultāciju rīt vakarā"],
        "expected": ["evening_window", "multiple_slot_options", "lv_reply"],
        "forbidden": ["ask_date_again", "ask_service_again", "ru_reply"],
    },
    {
        "id": "stage32_ru_not_so_late_refinement",
        "stage": 32,
        "lang": "ru",
        "category": "contextual_refinement",
        "message_sequence": ["хочу записаться на консультацию послезавтра после 14:00", "не так поздно"],
        "expected": ["same_booking_flow", "earlier_refinement", "avoid_repeating_same_slots"],
        "forbidden": ["reset_to_new", "ask_service_again", "repeat_same_three_slots"],
    },
    {
        "id": "stage32_lv_slightly_earlier_refinement",
        "stage": 32,
        "lang": "lv",
        "category": "contextual_refinement",
        "message_sequence": ["gribu pierakstīties uz konsultāciju rīt vakarā", "var mazliet agrāk?"],
        "expected": ["same_booking_flow", "earlier_refinement", "lv_reply"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_ru"],
    },
    {
        "id": "stage33_ru_soft_confirm",
        "stage": 33,
        "lang": "ru",
        "category": "soft_ux_confirmation",
        "message_sequence": ["хочу записаться на консультацию завтра вечером", "да, подходит"],
        "expected": ["confirm_yes_detected", "booking_finalized", "soft_human_reply"],
        "forbidden": ["confirm_loop", "ask_same_confirmation_again", "duplicate_booking"],
    },
    {
        "id": "stage33_lv_soft_confirm",
        "stage": 33,
        "lang": "lv",
        "category": "soft_ux_confirmation",
        "message_sequence": ["gribu pierakstīties uz konsultāciju rīt vakarā", "jā, der"],
        "expected": ["confirm_yes_detected", "booking_finalized", "soft_human_reply", "lv_reply"],
        "forbidden": ["confirm_loop", "ask_same_confirmation_again", "duplicate_booking"],
    },
    {
        "id": "parser_date_time_protection",
        "stage": 24,
        "lang": "lv",
        "category": "parser_regression",
        "message_sequence": ["gribu pierakstīties uz konsultāciju 15.05 10:00"],
        "expected": ["date_15_05", "time_10_00"],
        "forbidden": ["time_15_05", "accidental_date_as_time"],
    },
    {
        "id": "offered_slot_choice_protection",
        "stage": 24,
        "lang": "lv",
        "category": "slot_choice_regression",
        "message_sequence": ["gribu pierakstīties rīt 14:00", "konsultācija", "10:00"],
        "expected": ["select_offered_slot", "move_to_confirmation_or_booking"],
        "forbidden": ["repeat_14_busy", "ignore_offered_choice"],
    },    {
        "id": "stage37_lv_parit_recovery",
        "stage": 37,
        "lang": "lv",
        "category": "temporal_semantic_recovery",
        "message_sequence": [
            "gribu pierakstīties uz konsultāciju",
            "rīt vakarā",
            "ne rīt",
            "parīt",
        ],
        "expected": ["booking_flow", "evening_window", "multiple_slot_options", "lv_reply", "final_slot_regeneration"],
        "forbidden": ["morning_slots_only", "ask_service_again", "ask_date_again", "awaiting_date_after_replacement", "language_switch_to_ru"],
    },
    {
        "id": "stage37_lv_aizparit_recovery",
        "stage": 37,
        "lang": "lv",
        "category": "temporal_semantic_recovery",
        "message_sequence": [
            "gribu pierakstīties uz konsultāciju",
            "rīt vakarā",
            "ne rīt",
            "aizparīt",
        ],
        "expected": ["booking_flow", "evening_window", "multiple_slot_options", "lv_reply", "final_slot_regeneration"],
        "forbidden": ["morning_slots_only", "ask_service_again", "ask_date_again", "awaiting_date_after_replacement", "language_switch_to_ru"],
    },
    {
        "id": "stage38_lv_price_side_question",
        "stage": 38,
        "lang": "lv",
        "category": "business_memory_side_question",
        "message_sequence": [
            "gribu pierakstīties uz konsultāciju rīt vakarā",
            "cik tas maksā?",
            "jā, der",
        ],
        "expected": ["business_faq_answered", "preserve_booking_flow", "lv_reply"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_ru"],
    },
    {
        "id": "stage38_ru_hours_question",
        "stage": 38,
        "lang": "ru",
        "category": "business_memory_hours",
        "message_sequence": ["до скольки вы работаете?"],
        "expected": ["business_faq_answered", "ru_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_lv"],
    },
    {
        "id": "stage38_lv_location_question",
        "stage": 38,
        "lang": "lv",
        "category": "business_memory_location",
        "message_sequence": ["kur jūs atrodaties?"],
        "expected": ["business_faq_answered", "lv_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_ru"],
    },
    {
        "id": "stage40_ru_location_side_question",
        "stage": 40,
        "lang": "ru",
        "category": "business_memory_side_question",
        "message_sequence": [
            "хочу записаться на консультацию завтра вечером",
            "где вы находитесь?",
            "да, подходит",
        ],
        "expected": ["business_faq_answered", "preserve_booking_flow", "ru_reply"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_lv"],
    },
    {
        "id": "stage40_lv_location_side_question",
        "stage": 40,
        "lang": "lv",
        "category": "business_memory_side_question",
        "message_sequence": [
            "gribu pierakstīties uz konsultāciju rīt vakarā",
            "kur jūs atrodaties?",
            "jā, der",
        ],
        "expected": ["business_faq_answered", "preserve_booking_flow", "lv_reply"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_ru"],
    },
    {
        "id": "stage40_lv_price_then_slot_number",
        "stage": 40,
        "lang": "lv",
        "category": "business_memory_side_question",
        "message_sequence": [
            "gribu pierakstīties uz konsultāciju rīt vakarā",
            "cik tas maksā?",
            "2",
        ],
        "expected": ["business_faq_answered", "preserve_booking_flow", "lv_reply", "move_to_confirmation_or_booking"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_ru"],
    },
    {
        "id": "stage40_lv_later_refinement",
        "stage": 40,
        "lang": "lv",
        "category": "contextual_refinement",
        "message_sequence": [
            "gribu pierakstīties uz konsultāciju rīt vakarā",
            "var vēlāk?",
        ],
        "expected": ["same_booking_flow", "lv_reply"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_ru"],
    },
    {
        "id": "stage40_ru_later_refinement",
        "stage": 40,
        "lang": "ru",
        "category": "contextual_refinement",
        "message_sequence": [
            "хочу записаться на консультацию завтра вечером",
            "можно позже?",
        ],
        "expected": ["same_booking_flow", "ru_reply"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_lv"],
    },
    {
        "id": "stage40_lv_other_day_after_slots",
        "stage": 40,
        "lang": "lv",
        "category": "temporal_semantic_recovery",
        "message_sequence": [
            "gribu pierakstīties uz konsultāciju rīt vakarā",
            "citu dienu",
            "parīt",
        ],
        "expected": ["booking_flow", "lv_reply", "final_slot_regeneration"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_ru", "awaiting_date_after_replacement"],
    },
    {
        "id": "stage40_ru_other_day_after_slots",
        "stage": 40,
        "lang": "ru",
        "category": "temporal_semantic_recovery",
        "message_sequence": [
            "хочу записаться на консультацию завтра вечером",
            "другой день",
            "послезавтра",
        ],
        "expected": ["booking_flow", "ru_reply", "final_slot_regeneration"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_lv", "awaiting_date_after_replacement"],
    },
    {
        "id": "stage40_ru_standalone_location",
        "stage": 40,
        "lang": "ru",
        "category": "business_memory_location",
        "message_sequence": ["где вы находитесь?"],
        "expected": ["business_faq_answered", "ru_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_lv"],
    },
    {
        "id": "stage40_lv_standalone_hours",
        "stage": 40,
        "lang": "lv",
        "category": "business_memory_hours",
        "message_sequence": ["līdz cikiem jūs strādājat?"],
        "expected": ["business_faq_answered", "lv_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_ru"],
    },
    {
        "id": "stage40_lv_location_then_slot_number",
        "stage": 40,
        "lang": "lv",
        "category": "business_memory_side_question",
        "message_sequence": [
            "gribu pierakstīties uz konsultāciju rīt vakarā",
            "kur jūs atrodaties?",
            "3",
        ],
        "expected": ["business_faq_answered", "preserve_booking_flow", "lv_reply", "move_to_confirmation_or_booking"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_ru"],
    },
    {
        "id": "stage40_ru_location_then_slot_number",
        "stage": 40,
        "lang": "ru",
        "category": "business_memory_side_question",
        "message_sequence": [
            "хочу записаться на консультацию завтра вечером",
            "где вы находитесь?",
            "3",
        ],
        "expected": ["business_faq_answered", "preserve_booking_flow", "ru_reply", "move_to_confirmation_or_booking"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_lv"],
    },
    {
        "id": "stage40_lv_services_standalone",
        "stage": 40,
        "lang": "lv",
        "category": "business_memory_services",
        "message_sequence": ["kādi pakalpojumi jums ir?"],
        "expected": ["business_faq_answered", "lv_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_ru"],
    },
    {
        "id": "stage40_ru_services_standalone",
        "stage": 40,
        "lang": "ru",
        "category": "business_memory_services",
        "message_sequence": ["какие услуги у вас есть?"],
        "expected": ["business_faq_answered", "ru_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_lv"],
    },
    {
        "id": "stage41_ru_price_side_question",
        "stage": 41,
        "lang": "ru",
        "category": "business_memory_side_question",
        "message_sequence": [
            "хочу записаться на консультацию завтра вечером",
            "сколько это стоит?",
            "да, подходит",
        ],
        "expected": ["business_faq_answered", "preserve_booking_flow", "ru_reply"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_lv"],
    },
    {
        "id": "stage41_lv_hours_side_question",
        "stage": 41,
        "lang": "lv",
        "category": "business_memory_side_question",
        "message_sequence": [
            "gribu pierakstīties uz konsultāciju rīt vakarā",
            "cikos jūs strādājat?",
            "jā, der",
        ],
        "expected": ["business_faq_answered", "preserve_booking_flow", "lv_reply"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_ru"],
    },
    {
        "id": "stage44_ru_cancel_no_active_booking",
        "stage": 44,
        "lang": "ru",
        "category": "cancellation_no_active",
        "message_sequence": ["отменить запись"],
        "expected": ["cancel_reschedule_flow", "no_active_booking", "ru_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_lv"],
    },
    {
        "id": "stage44_lv_cancel_no_active_booking",
        "stage": 44,
        "lang": "lv",
        "category": "cancellation_no_active",
        "message_sequence": ["atcelt pierakstu"],
        "expected": ["cancel_reschedule_flow", "no_active_booking", "lv_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_ru"],
    },
    {
        "id": "stage44_ru_cancel_existing_booking",
        "stage": 44,
        "lang": "ru",
        "category": "cancellation_existing_booking",
        "message_sequence": ["отменить запись"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "cancel_request_detected", "booking_cancelled", "ru_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_lv"],
    },
    {
        "id": "stage44_lv_cancel_existing_booking",
        "stage": 44,
        "lang": "lv",
        "category": "cancellation_existing_booking",
        "message_sequence": ["atcelt pierakstu"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "cancel_request_detected", "booking_cancelled", "lv_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_ru"],
    },
    {
        "id": "stage44_ru_reschedule_no_active_booking",
        "stage": 44,
        "lang": "ru",
        "category": "reschedule_no_active",
        "message_sequence": ["перенести запись"],
        "expected": ["cancel_reschedule_flow", "no_active_booking", "ru_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_lv"],
    },
    {
        "id": "stage44_lv_reschedule_no_active_booking",
        "stage": 44,
        "lang": "lv",
        "category": "reschedule_no_active",
        "message_sequence": ["pārcelt pierakstu"],
        "expected": ["cancel_reschedule_flow", "no_active_booking", "lv_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_ru"],
    },
    {
        "id": "stage44_ru_reschedule_existing_booking_start",
        "stage": 44,
        "lang": "ru",
        "category": "reschedule_existing_start",
        "message_sequence": ["перенести запись"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "reschedule_started", "reschedule_pending", "ru_reply"],
        "forbidden": ["language_switch_to_lv"],
    },
    {
        "id": "stage44_lv_reschedule_existing_booking_start",
        "stage": 44,
        "lang": "lv",
        "category": "reschedule_existing_start",
        "message_sequence": ["pārcelt pierakstu"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "reschedule_started", "reschedule_pending", "lv_reply"],
        "forbidden": ["language_switch_to_ru"],
    },
    {
        "id": "stage44_ru_reschedule_abort",
        "stage": 44,
        "lang": "ru",
        "category": "reschedule_abort",
        "message_sequence": ["перенести запись", "нет"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "reschedule_started", "reschedule_aborted", "ru_reply"],
        "forbidden": ["language_switch_to_lv"],
    },
    {
        "id": "stage44_lv_reschedule_abort",
        "stage": 44,
        "lang": "lv",
        "category": "reschedule_abort",
        "message_sequence": ["pārcelt pierakstu", "nē"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "reschedule_started", "reschedule_aborted", "lv_reply"],
        "forbidden": ["language_switch_to_ru"],
    },

    {
        "id": "stage45_ru_reschedule_full_slot_ack_confirm",
        "stage": 45,
        "lang": "ru",
        "category": "reschedule_full_flow",
        "message_sequence": ["перенести запись", "послезавтра вечером", "да, подходит", "да"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "reschedule_started", "reschedule_pending", "multiple_slot_options", "reschedule_finalized", "ru_reply"],
        "forbidden": ["ask_service_again", "reset_to_new", "language_switch_to_lv"],
    },
    {
        "id": "stage45_lv_reschedule_full_slot_ack_confirm",
        "stage": 45,
        "lang": "lv",
        "category": "reschedule_full_flow",
        "message_sequence": ["pārcelt pierakstu", "parīt vakarā", "jā, der", "jā"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "reschedule_started", "reschedule_pending", "multiple_slot_options", "reschedule_finalized", "lv_reply"],
        "forbidden": ["ask_service_again", "reset_to_new", "language_switch_to_ru"],
    },
    {
        "id": "stage45_ru_reschedule_slot_number_confirm",
        "stage": 45,
        "lang": "ru",
        "category": "reschedule_full_flow",
        "message_sequence": ["перенести запись", "послезавтра вечером", "2", "да"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "reschedule_started", "reschedule_pending", "multiple_slot_options", "reschedule_finalized", "ru_reply"],
        "forbidden": ["ask_service_again", "reset_to_new", "language_switch_to_lv"],
    },
    {
        "id": "stage45_lv_reschedule_slot_number_confirm",
        "stage": 45,
        "lang": "lv",
        "category": "reschedule_full_flow",
        "message_sequence": ["pārcelt pierakstu", "parīt vakarā", "2", "jā"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "reschedule_started", "reschedule_pending", "multiple_slot_options", "reschedule_finalized", "lv_reply"],
        "forbidden": ["ask_service_again", "reset_to_new", "language_switch_to_ru"],
    },

    {
        "id": "stage46_ru_cancel_existing_booking_delete_path",
        "stage": 46,
        "lang": "ru",
        "category": "cancellation_existing_booking",
        "message_sequence": ["отменить запись"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "cancel_request_detected", "booking_cancelled", "calendar_delete_path", "ru_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_lv"],
    },
    {
        "id": "stage46_lv_cancel_existing_booking_delete_path",
        "stage": 46,
        "lang": "lv",
        "category": "cancellation_existing_booking",
        "message_sequence": ["atcelt pierakstu"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "cancel_request_detected", "booking_cancelled", "calendar_delete_path", "lv_reply"],
        "forbidden": ["booking_started_unnecessarily", "language_switch_to_ru"],
    },
    {
        "id": "stage46_ru_reschedule_update_path_final_text",
        "stage": 46,
        "lang": "ru",
        "category": "reschedule_full_flow",
        "message_sequence": ["перенести запись", "послезавтра вечером", "2", "да"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "reschedule_started", "reschedule_pending", "multiple_slot_options", "calendar_update_path", "reschedule_finalized", "reschedule_final_text", "ru_reply"],
        "forbidden": ["ask_service_again", "reset_to_new", "language_switch_to_lv", "generic_booking_final_text"],
    },
    {
        "id": "stage46_lv_reschedule_update_path_final_text",
        "stage": 46,
        "lang": "lv",
        "category": "reschedule_full_flow",
        "message_sequence": ["pārcelt pierakstu", "parīt vakarā", "2", "jā"],
        "calendar_event_fixture": {"days_from_today": 1, "hour": 16, "minute": 0, "duration_min": 30, "service": "konsultācija"},
        "expected": ["cancel_reschedule_flow", "reschedule_started", "reschedule_pending", "multiple_slot_options", "calendar_update_path", "reschedule_finalized", "reschedule_final_text", "lv_reply"],
        "forbidden": ["ask_service_again", "reset_to_new", "language_switch_to_ru", "generic_booking_final_text"],
    },
    {
        "id": "stage48_ru_price_side_question_localized_text",
        "stage": 48,
        "lang": "ru",
        "category": "business_memory_side_question",
        "message_sequence": [
            "хочу записаться на консультацию завтра вечером",
            "сколько это стоит?",
            "да, подходит",
        ],
        "expected": ["business_faq_answered", "preserve_booking_flow", "localized_ru_price_text", "ru_text_localized", "ru_reply"],
        "forbidden": ["reset_to_new", "ask_service_again", "language_switch_to_lv", "raw_lv_service_text_in_ru_reply"],
    },
    {
        "id": "stage48_ru_slot_number_confirmation_localized_service_text",
        "stage": 48,
        "lang": "ru",
        "category": "text_mvp_confirmation_ux",
        "message_sequence": ["хочу записаться на консультацию завтра вечером", "2"],
        "expected": ["booking_flow", "move_to_confirmation_or_booking", "ru_text_localized", "ru_reply"],
        "forbidden": ["ask_service_again", "language_switch_to_lv", "raw_lv_service_text_in_ru_reply"],
    },

]


def stage34_regression_test_matrix() -> Dict[str, Any]:
    return {
        "stage": 34,
        "name": "Production Regression Test Matrix",
        "purpose": "Protect Stage 24 and Stage 30-33 conversational booking behavior from regressions.",
        "total": len(STAGE34_REGRESSION_TEST_MATRIX),
        "items": STAGE34_REGRESSION_TEST_MATRIX,
    }


@app.get("/dialogue/regression_matrix")
def dialogue_regression_matrix_endpoint():
    return stage34_regression_test_matrix()


# -------------------------
# STAGE 35 — REGRESSION RUNNER / QA DASHBOARD
# -------------------------
def _stage35_norm_text(value: Any) -> str:
    txt = str(value or "").strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt


def _stage35_time_labels(text_value: str) -> List[str]:
    return re.findall(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b", str(text_value or ""))


def stage35_detect_regression_observations(scenario: Dict[str, Any], turns: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate regression runner output.

    Stage 35.4 calibration notes:
    - This evaluator checks conversational behavior, not real calendar booking side effects.
    - "evening" / "after" tests should pass when the bot offers a valid slot window.
    - "earlier/later" refinements are detected by comparing slot windows between turns.
    - A positive reply after offered slots may mean "choose this slot" and move to AWAITING_CONFIRM;
      it is not necessarily final booking confirmation yet.
    """
    scenario = scenario or {}
    expected = [str(x) for x in scenario.get("expected") or []]
    forbidden = [str(x) for x in scenario.get("forbidden") or []]
    lang = get_lang(scenario.get("lang") or "lv")
    category = str(scenario.get("category") or "").strip().lower()
    all_reply = "\n".join(str(t.get("assistant") or "") for t in turns)
    last_reply = str((turns[-1] if turns else {}).get("assistant") or "")
    all_low = _stage35_norm_text(all_reply)
    last_low = _stage35_norm_text(last_reply)
    times = _stage35_time_labels(all_reply)
    last_times = _stage35_time_labels(last_reply)
    statuses = [str(t.get("status") or "").strip().lower() for t in turns]
    states = [str(t.get("state") or "").strip().upper() for t in turns]
    result_langs = [get_lang(t.get("lang") or lang) for t in turns if t.get("lang")]
    calendar_actions = [str((t or {}).get("calendar_action") or "").strip() for t in turns]

    observed = set()
    forbidden_hits = []

    def _time_to_minutes(label: str) -> int:
        try:
            hh, mm = label.split(":", 1)
            return int(hh) * 60 + int(mm)
        except Exception:
            return 0

    def _turn_times(turn: Dict[str, Any]) -> List[str]:
        labels = _stage35_time_labels(str((turn or {}).get("assistant") or ""))
        pending = (turn or {}).get("pending") or {}
        if isinstance(pending, dict):
            for iso in pending.get("offered_slots") or []:
                dtv = parse_dt_any_tz(str(iso or ""))
                if dtv:
                    label = f"{dtv.hour:02d}:{dtv.minute:02d}"
                    if label not in labels:
                        labels.append(label)
        return labels

    first_turn_times = _turn_times(turns[0]) if turns else []
    last_turn_times = _turn_times(turns[-1]) if turns else []
    first_avg = sum(_time_to_minutes(x) for x in first_turn_times) / len(first_turn_times) if first_turn_times else None
    last_avg = sum(_time_to_minutes(x) for x in last_turn_times) / len(last_turn_times) if last_turn_times else None
    message_sequence_text = " ".join(str(x) for x in scenario.get("message_sequence") or [])
    message_sequence_low = _stage35_norm_text(message_sequence_text)
    positive_slot_ack = any(x in message_sequence_low for x in ["да", "jā", "ja", "der", "подходит", "fits", "works", "ok"])
    selected_slot_for_confirmation = (
        len(turns) >= 2
        and "AWAITING_TIME" in states[:1]
        and (states[-1:] == ["AWAITING_CONFIRM"])
        and bool(((turns[-1].get("pending") or {}) if isinstance(turns[-1].get("pending"), dict) else {}).get("confirm_slot_iso"))
    )

    if any(st in {"need_more", "busy", "booked", "min_notice", "holiday_closed"} for st in statuses) or any(st.startswith("AWAITING_") for st in states):
        observed.add("booking_flow")
        observed.add("same_booking_flow")
    if any(st == "info" for st in statuses) or any(x in all_low for x in [
        "cena", "maksā", "darba laiks", "adrese",
        "адрес", "находимся", "стоит", "евро",
        "atrodamies", "strādājam", "работаем", "open from", "usually open", "price", "costs"
    ]):
        observed.add("business_faq_answered")
    if category.startswith("business_memory") and len(turns) >= 2 and ("AWAITING_" in " ".join(states) or any(st == "need_more" for st in statuses[1:])):
        observed.add("preserve_booking_flow")
    if category.startswith("cancellation") or category.startswith("reschedule"):
        if any(st in {"cancelled", "no_booking", "cancel_failed", "reschedule_wait", "booked", "info"} for st in statuses):
            observed.add("cancel_reschedule_flow")
    if "no_booking" in statuses:
        observed.add("no_active_booking")
    if "cancelled" in statuses:
        observed.add("cancel_request_detected")
        observed.add("booking_cancelled")
    if "cancel_failed" in statuses:
        observed.add("cancel_failed")
    if "reschedule_wait" in statuses:
        observed.add("reschedule_started")
    if any(isinstance((t or {}).get("pending"), dict) and (t.get("pending") or {}).get("reschedule_event_id") for t in turns):
        observed.add("reschedule_pending")
    if category.startswith("reschedule") and "reschedule_wait" in statuses and statuses[-1:] == ["info"] and states[-1:] == ["BOOKED"]:
        observed.add("reschedule_aborted")
    if category.startswith("reschedule") and "booked" in statuses and "reschedule_wait" in statuses:
        observed.add("reschedule_finalized")
    if category.startswith("reschedule") and ("update_event" in calendar_actions or any((t or {}).get("reschedule_finalized") for t in turns)):
        observed.add("calendar_update_path")
    if category.startswith("cancellation") and "delete_event" in calendar_actions:
        observed.add("calendar_delete_path")
    if category.startswith("reschedule") and any(x in last_low for x in ["перенесена", "перенёс", "перенес", "pārcelts", "pārcēlu", "appointment moved"]):
        observed.add("reschedule_final_text")
    # Stage 45.1: a full reschedule flow may end on a final confirmation turn
    # with only one time in the last reply, while the actual slot options were
    # correctly offered on an earlier turn. Detect multiple options per turn
    # instead of relying only on the final turn.
    if any(len(_turn_times(t)) >= 2 for t in turns):
        observed.add("multiple_slot_options")
    if len(set(times)) >= 2:
        observed.add("avoid_repeating_same_slots")
    if any(int(t.split(":", 1)[0]) >= 14 for t in times):
        observed.add("time_window_after_14")
    if any(int(t.split(":", 1)[0]) >= 16 for t in times):
        observed.add("evening_window")
    if "booked" in statuses:
        observed.add("booking_finalized")
        observed.add("confirm_yes_detected")
    if category == "temporal_semantic_recovery" and states[-1:] == ["AWAITING_TIME"] and len(last_turn_times) >= 2:
        observed.add("final_slot_regeneration")
    if selected_slot_for_confirmation:
        observed.add("confirm_yes_detected")
        observed.add("slot_selected_for_confirmation")
        observed.add("move_to_confirmation_or_booking")
        observed.add("select_offered_slot")
    if first_avg is not None and last_avg is not None and len(turns) >= 2 and last_avg < first_avg:
        observed.add("earlier_refinement")
    if any(x in all_low for x in ["agr", "раньше", "earlier", "ne tik vēlu", "не так поздно"]):
        observed.add("earlier_refinement")
    if lang == "lv" and result_langs and all(x == "lv" for x in result_langs):
        observed.add("lv_reply")
    if lang == "ru" and result_langs and all(x == "ru" for x in result_langs):
        observed.add("ru_reply")
    # Stage 48: text-MVP UX guard. Russian customer-facing replies should not
    # expose raw Latvian service/price labels when a safe localized display is
    # available for common MVP services such as consultation.
    raw_lv_service_markers = ["konsultācija", "konsultacija", " eiro"]
    if lang == "ru" and not any(x in all_low for x in raw_lv_service_markers):
        observed.add("ru_text_localized")
    if lang == "ru" and "консультац" in all_low and "евро" in all_low and not any(x in all_low for x in raw_lv_service_markers):
        observed.add("localized_ru_price_text")
    if "14:00" not in last_reply or len(last_times) >= 2:
        observed.add("no_exact_14_confirmation")
    if "no_exact_default_time" in expected:
        # For fuzzy windows, the critical check is that the bot offers a real window of options
        # instead of forcing a single default exact time.
        if len(last_turn_times or last_times or times) >= 2 and ("AWAITING_TIME" in states or "need_more" in statuses):
            observed.add("no_exact_default_time")
    if "15.05" in message_sequence_text and ("10:00" in all_reply or any(t == "10:00" for t in times)):
        observed.add("date_15_05")
        observed.add("time_10_00")
    if any(st in {"need_more", "booked"} for st in statuses):
        observed.add("move_to_confirmation_or_booking")
        observed.add("select_offered_slot")
    if any(x in all_low for x in ["lieliski", "отлично", "great", "der", "подходит", "jā", "да", "atradu", "нашёл", "нашел", "varam", "можем"]):
        observed.add("soft_human_reply")

    def hit_forbidden(token: str) -> bool:
        if token == "confirm_exact_14_00":
            return "14:00" in last_reply and any(w in last_low for w in ["подтверд", "apstip", "confirm", "pierakstīt", "записать"])
        if token == "ask_service_again":
            return any(x in last_low for x in ["какую услугу", "kādu pakalpojumu", "which service"])
        if token == "ask_date_again":
            return any(x in last_low for x in ["какой день", "kuru dienu", "which day", "what date"])
        if token == "language_switch_to_lv":
            return lang != "lv" and any(x == "lv" for x in result_langs)
        if token == "language_switch_to_ru":
            return lang != "ru" and any(x == "ru" for x in result_langs)
        if token == "ru_reply":
            return any(x == "ru" for x in result_langs)
        if token == "confirm_loop" or token == "ask_same_confirmation_again":
            # In soft-confirm scenarios, moving from offered slots to a concrete confirmation prompt is expected.
            if category == "soft_ux_confirmation" and selected_slot_for_confirmation and positive_slot_ack:
                return False
            return (statuses[-1] == "need_more" if statuses else False) and any(x in last_low for x in ["подтверд", "apstip", "confirm"])
        if token == "repeat_14_busy":
            return "14:00" in all_reply and any(x in all_low for x in ["занят", "aizņem", "busy", "taken"])
        if token == "ignore_offered_choice":
            return "10:00" in message_sequence_text and "10:00" not in all_reply and statuses[-1:] == ["busy"]
        if token == "time_15_05" or token == "accidental_date_as_time":
            return "15:05" in all_reply
        if token == "morning_slots_only":
            return bool(times) and all(int(t.split(":",1)[0]) < 12 for t in times)
        if token == "awaiting_date_after_replacement":
            return category == "temporal_semantic_recovery" and states[-1:] == ["AWAITING_DATE"]
        if token == "booking_started_unnecessarily":
            guarded_category = category.startswith("business_memory") or category.startswith("cancellation") or category in {"reschedule_no_active"}
            return guarded_category and any(st.startswith("AWAITING_") for st in states)
        if token == "reset_to_new":
            return "NEW" in states[1:]
        if token == "repeat_same_three_slots":
            return len(times) >= 6 and times[:3] == times[-3:]
        if token == "generic_booking_final_text":
            if not category.startswith("reschedule") or statuses[-1:] != ["booked"]:
                return False
            final_markers = ["перенесена", "перенёс", "перенес", "pārcelts", "pārcēlu", "appointment moved"]
            return not any(x in last_low for x in final_markers)
        if token == "raw_lv_service_text_in_ru_reply":
            return lang == "ru" and any(x in all_low for x in ["konsultācija", "konsultacija", " eiro"])
        return token in all_low

    for token in forbidden:
        if hit_forbidden(token):
            forbidden_hits.append(token)

    expected_missing = [token for token in expected if token not in observed]

    # Stage 35.4: legacy Stage 33 two-turn scenarios used to expect final booking,
    # but the real UX correctly moves from broad slot options to a concrete confirmation prompt.
    if category == "soft_ux_confirmation" and selected_slot_for_confirmation:
        expected_missing = [x for x in expected_missing if x not in {"booking_finalized"}]

    passed = not forbidden_hits and len(expected_missing) == 0
    severity = "pass" if passed else "warning" if (not forbidden_hits and expected_missing == ["soft_human_reply"]) else "fail"
    return {
        "passed": passed,
        "severity": severity,
        "observed": sorted(observed),
        "expected_missing": expected_missing,
        "forbidden_hits": forbidden_hits,
        "times_detected": times,
        "statuses": statuses,
        "states": states,
        "langs": result_langs,
    }


STAGE35_QA_TENANT_ID = os.getenv("STAGE35_QA_TENANT_ID", "clinic_demo").strip() or "clinic_demo"
STAGE35_CALENDAR_SAFE_MODE_ENABLED = os.getenv("STAGE35_CALENDAR_SAFE_MODE", "1").strip().lower() not in {"0", "false", "no", "off", "disabled"}
_STAGE35_CALENDAR_SAFE_MODE: ContextVar[bool] = ContextVar("stage35_calendar_safe_mode", default=False)
_STAGE35_CALENDAR_EVENT_FIXTURE: ContextVar[Optional[Dict[str, Any]]] = ContextVar("stage35_calendar_event_fixture", default=None)


def stage35_calendar_safe_mode_active() -> bool:
    return bool(STAGE35_CALENDAR_SAFE_MODE_ENABLED and _STAGE35_CALENDAR_SAFE_MODE.get(False))


def stage35_calendar_event_fixture() -> Optional[Dict[str, Any]]:
    if not stage35_calendar_safe_mode_active():
        return None
    fixture = _STAGE35_CALENDAR_EVENT_FIXTURE.get(None)
    return fixture if isinstance(fixture, dict) else None


def stage35_build_calendar_event_fixture(scenario: Dict[str, Any], tenant_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    cfg = (scenario or {}).get("calendar_event_fixture")
    if not isinstance(cfg, dict):
        return None
    try:
        days = int(cfg.get("days_from_today", 1))
    except Exception:
        days = 1
    try:
        hour = int(cfg.get("hour", 16))
        minute = int(cfg.get("minute", 0))
    except Exception:
        hour, minute = 16, 0
    try:
        duration_min = int(cfg.get("duration_min", 30))
    except Exception:
        duration_min = 30
    start_dt = (now_ts() + timedelta(days=max(0, days))).replace(hour=max(0, min(23, hour)), minute=max(0, min(59, minute)), second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=max(1, duration_min))
    service_name = str(cfg.get("service") or "konsultācija").strip() or "konsultācija"
    summary = str(cfg.get("summary") or f"Clinic Demo - {service_name}").strip()
    client_name = str(cfg.get("name") or "Client").strip() or "Client"
    description = build_event_description(tenant_id, client_name, user_id)
    return {
        "id": str(cfg.get("id") or f"stage44-safe-fixture-{uuid.uuid4().hex[:8]}"),
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": end_dt.isoformat()},
    }


def stage35_resolve_qa_tenant_id(tenant_id: Optional[str] = None) -> str:
    requested = str(tenant_id or "").strip()
    if requested and requested != "default" and requested != str(TENANT_ID_DEFAULT or "").strip():
        return requested
    return STAGE35_QA_TENANT_ID


def stage35_run_regression_scenario(scenario_id: str, tenant_id: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    scenario = next((x for x in STAGE34_REGRESSION_TEST_MATRIX if str(x.get("id")) == str(scenario_id)), None)
    if not scenario:
        raise HTTPException(status_code=404, detail="Regression scenario not found")
    tenant_id = stage35_resolve_qa_tenant_id(tenant_id)
    user_id = (user_id or f"qa_{scenario_id}_{uuid.uuid4().hex[:8]}").strip()
    lang = get_lang(scenario.get("lang") or "lv")
    messages = scenario.get("message_sequence") or []
    turns: List[Dict[str, Any]] = []
    token = _STAGE35_CALENDAR_SAFE_MODE.set(True)
    fixture_token = _STAGE35_CALENDAR_EVENT_FIXTURE.set(stage35_build_calendar_event_fixture(scenario, tenant_id, user_id))
    try:
        for msg in messages[:10]:
            result = handle_user_text_with_logging(tenant_id, user_id, str(msg), "dev", lang, source="regression_runner")
            try:
                conv = db_get_or_create_conversation(tenant_id, user_id, lang)
            except Exception:
                conv = {}
            turns.append({
                "user": str(msg),
                "assistant": result.get("msg_out") or result.get("reply_voice"),
                "status": result.get("status"),
                "lang": result.get("lang"),
                "state": (conv or {}).get("state"),
                "pending": (conv or {}).get("pending"),
                "calendar_action": result.get("calendar_action"),
                "reschedule_finalized": result.get("reschedule_finalized"),
            })
    finally:
        _STAGE35_CALENDAR_EVENT_FIXTURE.reset(fixture_token)
        _STAGE35_CALENDAR_SAFE_MODE.reset(token)
    evaluation = stage35_detect_regression_observations(scenario, turns)
    return {
        "stage": 35,
        "runner": "Regression Runner / QA Dashboard",
        "tenant_id": tenant_id,
        "calendar_safe_mode": STAGE35_CALENDAR_SAFE_MODE_ENABLED,
        "user_id": user_id,
        "scenario": scenario,
        "turns": turns,
        "evaluation": evaluation,
    }


def stage35_run_regression_suite(tenant_id: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    tenant_id = stage35_resolve_qa_tenant_id(tenant_id)
    requested_limit = len(STAGE34_REGRESSION_TEST_MATRIX) if limit in (None, "", 0) else int(limit)
    limit = max(1, min(requested_limit, len(STAGE34_REGRESSION_TEST_MATRIX)))
    results = []
    for scenario in STAGE34_REGRESSION_TEST_MATRIX[:limit]:
        try:
            results.append(stage35_run_regression_scenario(str(scenario.get("id")), tenant_id=tenant_id))
        except Exception as e:
            results.append({"scenario_id": scenario.get("id"), "error": str(e), "evaluation": {"severity": "fail", "passed": False}})
    passed = sum(1 for r in results if ((r.get("evaluation") or {}).get("severity") == "pass"))
    warnings = sum(1 for r in results if ((r.get("evaluation") or {}).get("severity") == "warning"))
    failed = sum(1 for r in results if ((r.get("evaluation") or {}).get("severity") == "fail"))
    return {
        "stage": 35,
        "name": "Regression Runner / QA Dashboard",
        "tenant_id": tenant_id,
        "calendar_safe_mode": STAGE35_CALENDAR_SAFE_MODE_ENABLED,
        "total": len(results),
        "passed": passed,
        "warnings": warnings,
        "failed": failed,
        "results": results,
    }


@app.get("/dialogue/qa", response_class=HTMLResponse)
def dialogue_qa_dashboard():
    qa_tenant_id = STAGE35_QA_TENANT_ID
    matrix = stage34_regression_test_matrix()
    rows = "".join([
        f"""
        <tr>
          <td><code>{item.get('id')}</code></td>
          <td>{item.get('stage')}</td>
          <td>{item.get('lang')}</td>
          <td>{item.get('category')}</td>
          <td>{' → '.join(item.get('message_sequence') or [])}</td>
          <td><button onclick=\"runScenario('{item.get('id')}')\">Run</button></td>
        </tr>
        """ for item in matrix.get("items", [])
    ])
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Repliq Stage 35 QA Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; background:#f6f7fb; color:#111827; margin:0; }}
    .wrap {{ max-width:1200px; margin:0 auto; padding:24px; }}
    .card {{ background:white; border-radius:16px; box-shadow:0 8px 24px rgba(15,23,42,.08); padding:20px; margin-bottom:18px; }}
    h1 {{ margin:0 0 8px; }}
    .muted {{ color:#6b7280; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th, td {{ border-bottom:1px solid #e5e7eb; padding:10px; vertical-align:top; text-align:left; }}
    th {{ background:#f9fafb; }}
    button {{ border:0; border-radius:10px; padding:8px 12px; cursor:pointer; background:#111827; color:white; }}
    button.secondary {{ background:#4b5563; }}
    pre {{ background:#0b1020; color:#d1e7ff; border-radius:14px; padding:14px; overflow:auto; max-height:520px; }}
    .pass {{ color:#047857; font-weight:700; }} .fail {{ color:#b91c1c; font-weight:700; }} .warning {{ color:#b45309; font-weight:700; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Repliq Stage 35 — Regression Runner / QA Dashboard</h1>
      <div class="muted">Internal QA tool for protecting Stage 24 and Stage 30–33 conversational booking behavior. Default QA tenant: <b>{qa_tenant_id}</b>.</div>
      <p><button onclick="runAll()">Run full regression suite</button> <button class="secondary" onclick="loadMatrix()">Reload matrix</button></p>
    </div>
    <div class="card">
      <h2>Regression Matrix ({matrix.get('total')})</h2>
      <table>
        <thead><tr><th>ID</th><th>Stage</th><th>Lang</th><th>Category</th><th>Messages</th><th>Action</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <div class="card">
      <h2>Result</h2>
      <pre id="out">Ready.</pre>
    </div>
  </div>
<script>
async function runScenario(id) {{
  const out = document.getElementById('out');
  out.textContent = 'Running ' + id + '...';
  const r = await fetch('/dialogue/regression_run/' + encodeURIComponent(id) + '?tenant_id=' + encodeURIComponent('{qa_tenant_id}'));
  const data = await r.json();
  out.textContent = JSON.stringify(data, null, 2);
}}
async function runAll() {{
  const out = document.getElementById('out');
  out.textContent = 'Running full suite...';
  const r = await fetch('/dialogue/regression_run_all?tenant_id=' + encodeURIComponent('{qa_tenant_id}'));
  const data = await r.json();
  out.textContent = JSON.stringify(data, null, 2);
}}
async function loadMatrix() {{
  const out = document.getElementById('out');
  const r = await fetch('/dialogue/regression_matrix');
  const data = await r.json();
  out.textContent = JSON.stringify(data, null, 2);
}}
</script>
</body>
</html>
    """
    return HTMLResponse(html)


@app.get("/dialogue/regression_run/{scenario_id}")
def dialogue_regression_run_endpoint(scenario_id: str, tenant_id: Optional[str] = None):
    return stage35_run_regression_scenario(scenario_id, tenant_id=tenant_id)


@app.get("/dialogue/regression_run_all")
def dialogue_regression_run_all_endpoint(tenant_id: Optional[str] = None, limit: Optional[int] = None):
    return stage35_run_regression_suite(tenant_id=tenant_id, limit=limit)


def ensure_dialogue_audit_table() -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dialogue_audit_events (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    tenant_id TEXT,
                    user_id TEXT,
                    channel TEXT,
                    source TEXT,
                    lang TEXT,
                    state_before TEXT,
                    state_after TEXT,
                    intent TEXT,
                    status TEXT,
                    raw_text TEXT,
                    ai_reply TEXT,
                    score INTEGER,
                    flags_json JSONB,
                    meta_json JSONB
                )
            """))
    except Exception as e:
        log.error("ensure_dialogue_audit_table_failed err=%s", e)


def dialogue_flags_for_turn(raw_text: str, result: Dict[str, Any], conv_before: Optional[Dict[str, Any]], conv_after: Optional[Dict[str, Any]]) -> List[str]:
    raw = str(raw_text or "").strip()
    low = _normalize_phrase_text(raw)
    reply = str((result or {}).get("msg_out") or (result or {}).get("reply_voice") or "").strip()
    reply_low = _normalize_phrase_text(reply)
    status = str((result or {}).get("status") or "").strip().lower()
    before_state = conversation_state(conv_before or {})
    after_state = conversation_state(conv_after or {})
    flags: List[str] = []

    if not reply:
        flags.append("empty_reply")
    if status in {"booking_failed", "recovery", "blocked"}:
        flags.append(f"status_{status}")
    if len(reply) > 420:
        flags.append("reply_too_long")
    if reply_low and any(reply_low.count(p) >= 2 for p in ["uz kuru", "kurš datums", "kuru dienu", "на какую", "which service"]):
        flags.append("possible_repetition")
    if any(x in low for x in ["cik maksa", "cik maksā", "сколько стоит", "price", "how much"]) and after_state == STATE_AWAITING_DATE:
        flags.append("faq_price_to_date_collision")
    if any(x in low for x in ["pakalpojumi", "услуги", "services"]) and after_state in {STATE_AWAITING_DATE, STATE_AWAITING_TIME, STATE_AWAITING_CONFIRM}:
        flags.append("faq_services_started_booking")
    if before_state != STATE_NEW and after_state == STATE_NEW and status not in {"booked", "cancelled", "info", "greeting"}:
        flags.append("unexpected_state_reset")
    if raw and len(raw.split()) >= 7 and after_state == STATE_AWAITING_SERVICE:
        flags.append("long_message_missing_service")
    if has_date_reference(raw) and has_explicit_time(raw) and after_state in {STATE_AWAITING_SERVICE, STATE_AWAITING_DATE}:
        flags.append("single_message_missing_date_or_time")
    if str((result or {}).get("lang") or "").strip() and str((conv_after or {}).get("lang") or "").strip():
        if get_lang((result or {}).get("lang")) != get_lang((conv_after or {}).get("lang")):
            flags.append("language_mismatch")
    if reply.lower().startswith(("sure", "great", "okay")) and get_lang((result or {}).get("lang")) == "lv":
        flags.append("english_leak_in_lv")
    return sorted(set(flags))


def dialogue_quality_score(flags: List[str], result: Dict[str, Any]) -> int:
    score = 100
    penalties = {
        "empty_reply": 40,
        "status_booking_failed": 30,
        "status_recovery": 20,
        "status_blocked": 15,
        "reply_too_long": 10,
        "possible_repetition": 15,
        "faq_price_to_date_collision": 35,
        "faq_services_started_booking": 35,
        "unexpected_state_reset": 25,
        "long_message_missing_service": 25,
        "single_message_missing_date_or_time": 30,
        "language_mismatch": 20,
        "english_leak_in_lv": 30,
    }
    for flag in flags:
        score -= penalties.get(flag, 8)
    return max(0, min(100, score))


def record_dialogue_audit_event(
    tenant_id: str,
    user_id: str,
    channel: str,
    source: str,
    raw_text: str,
    result: Dict[str, Any],
    conv_before: Optional[Dict[str, Any]],
    conv_after: Optional[Dict[str, Any]],
) -> None:
    try:
        ensure_dialogue_audit_table()
        flags = dialogue_flags_for_turn(raw_text, result, conv_before, conv_after)
        score = dialogue_quality_score(flags, result)
        status = str((result or {}).get("status") or "").strip() or "unknown"
        intent = infer_intent_label(raw_text, status, conv_after or conv_before or {})
        payload_meta = {
            "service": (conv_after or {}).get("service"),
            "datetime_iso": (conv_after or {}).get("datetime_iso"),
            "pending": (conv_after or {}).get("pending"),
        }
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO dialogue_audit_events
                (tenant_id, user_id, channel, source, lang, state_before, state_after, intent, status, raw_text, ai_reply, score, flags_json, meta_json)
                VALUES
                (:tenant_id, :user_id, :channel, :source, :lang, :state_before, :state_after, :intent, :status, :raw_text, :ai_reply, :score, CAST(:flags_json AS JSONB), CAST(:meta_json AS JSONB))
            """), {
                "tenant_id": (tenant_id or "").strip() or TENANT_ID_DEFAULT,
                "user_id": norm_user_key(user_id),
                "channel": (channel or "").strip().lower() or "unknown",
                "source": (source or "runtime").strip().lower() or "runtime",
                "lang": get_lang((result or {}).get("lang") or (conv_after or {}).get("lang") or "lv"),
                "state_before": conversation_state(conv_before or {}),
                "state_after": conversation_state(conv_after or {}),
                "intent": intent,
                "status": status,
                "raw_text": (raw_text or "").strip(),
                "ai_reply": str((result or {}).get("msg_out") or (result or {}).get("reply_voice") or "").strip(),
                "score": score,
                "flags_json": json.dumps(flags, ensure_ascii=False),
                "meta_json": json.dumps(payload_meta, ensure_ascii=False, default=str),
            })
    except Exception as e:
        log.error("dialogue_audit_write_failed tenant_id=%s user_id=%s err=%s", tenant_id, user_id, e)


def dialogue_audit_summary(tenant_id: str, limit: int = 50) -> Dict[str, Any]:
    ensure_dialogue_audit_table()
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    limit = max(1, min(int(limit or 50), 200))
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM dialogue_audit_events WHERE tenant_id=:tid"), {"tid": tenant_id}).scalar() or 0
        avg_score = conn.execute(text("SELECT COALESCE(AVG(score), 0) FROM dialogue_audit_events WHERE tenant_id=:tid"), {"tid": tenant_id}).scalar() or 0
        bad = conn.execute(text("SELECT COUNT(*) FROM dialogue_audit_events WHERE tenant_id=:tid AND score < 70"), {"tid": tenant_id}).scalar() or 0
        rows = conn.execute(text("""
            SELECT created_at, channel, lang, state_before, state_after, intent, status, raw_text, ai_reply, score, flags_json
            FROM dialogue_audit_events
            WHERE tenant_id=:tid
            ORDER BY created_at DESC
            LIMIT :lim
        """), {"tid": tenant_id, "lim": limit}).fetchall()
    items = []
    flag_counts: Dict[str, int] = {}
    for r in rows:
        flags = r[10] if isinstance(r[10], list) else []
        if isinstance(r[10], str):
            try: flags = json.loads(r[10])
            except Exception: flags = []
        for f in flags or []:
            flag_counts[str(f)] = flag_counts.get(str(f), 0) + 1
        items.append({
            "created_at": r[0], "channel": r[1], "lang": r[2], "state_before": r[3], "state_after": r[4],
            "intent": r[5], "status": r[6], "raw_text": r[7], "ai_reply": r[8], "score": r[9], "flags": flags or [],
        })
    return {
        "tenant_id": tenant_id,
        "total_events": int(total or 0),
        "average_score": round(float(avg_score or 0), 1),
        "low_score_events": int(bad or 0),
        "top_flags": sorted([{"flag": k, "count": v} for k, v in flag_counts.items()], key=lambda x: x["count"], reverse=True)[:20],
        "recent": items,
    }


def handle_user_text_with_logging(
    tenant_id: str, raw_phone: str, text_in: str, channel: str, lang_hint: str, source: str = "runtime"
) -> Dict[str, Any]:
    try:
        conv_before = dict(db_get_or_create_conversation(tenant_id, raw_phone, lang_hint or "lv") or {})
    except Exception:
        conv_before = {}

    result = handle_user_text(tenant_id, raw_phone, text_in, channel, lang_hint, source=source)

    try:
        conv = db_get_or_create_conversation(tenant_id, raw_phone, lang_hint or "lv")
    except Exception:
        conv = {}
    try:
        tenant = get_tenant(tenant_id)
        result = humanize_result(result, conv, tenant)
        result = ai_response_composer(result, conv, tenant, channel=channel, source=source)
        result = stage33_soft_conversational_ux(result, conv, tenant, channel=channel, source=source)
        result = apply_usage_soft_limit_warning(result, result.get("lang") or get_lang((conv or {}).get("lang") or lang_hint or "lv"), tenant, channel, source=source)
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
    record_dialogue_audit_event(
        tenant_id=tenant_id,
        user_id=raw_phone,
        channel=channel,
        source=source,
        raw_text=text_in,
        result=result,
        conv_before=conv_before,
        conv_after=conv,
    )
    record_usage_event(
        tenant_id=tenant_id,
        user_id=raw_phone,
        channel=channel,
        raw_text=text_in,
        result=result,
        conv=conv,
        source=source,
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
def tenant_status_value(tenant: Dict[str, Any]) -> str:
    tenant = normalize_tenant_saas_fields(tenant or {})
    explicit = str(
        tenant.get("status")
        or tenant.get("client_status")
        or CLIENT_STATUS_FALLBACK
        or "trial"
    ).strip().lower() or "trial"
    if explicit in {"inactive", "suspended"}:
        return "inactive"
    lifecycle = effective_subscription_status(tenant)
    if lifecycle == "active":
        return "active"
    if lifecycle == "past_due":
        return "past_due"
    if lifecycle == "inactive":
        return "inactive"
    if lifecycle == "expired":
        return "expired"
    return "trial"


def tenant_trial_end_value(tenant: Dict[str, Any]) -> Optional[datetime]:
    te = tenant.get("trial_end") or tenant.get("trial_end_at")
    dt = parse_dt_any_tz(te) if isinstance(te, str) else te
    if not dt:
        dt = parse_dt_any_tz(TRIAL_END_ISO_FALLBACK)
    return dt


def tenant_allowed(tenant: Dict[str, Any]) -> Tuple[bool, str]:
    decision = tenant_access_decision(tenant)
    return bool(decision.get("allowed")), str(decision.get("reason") or "ok")


def month_start_local(dt_value: Optional[datetime] = None) -> datetime:
    dt_value = dt_value or now_ts()
    return dt_value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def tenant_dialog_usage_current_month(tenant_id: str) -> int:
    tenant_id = (tenant_id or "").strip()
    if not tenant_id:
        return 0
    ensure_usage_events_table()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT COALESCE(SUM(usage_units), 0)
                FROM usage_events
                WHERE tenant_id=:tenant_id
                  AND billable=true
                  AND created_at >= :since_ts
                """
            ),
            {"tenant_id": tenant_id, "since_ts": month_start_local()},
        ).fetchone()
    return int((row[0] if row else 0) or 0)


def tenant_dialog_limit(tenant: Dict[str, Any]) -> int:
    tenant = normalize_tenant_saas_fields(tenant or {})
    plan_meta = tenant_plan_meta(tenant)
    limits = plan_meta.get("limits") or {}
    raw_limit = tenant.get("dialogs_per_month")
    try:
        if raw_limit in (None, ""):
            return max(0, int(limits.get("dialogs_per_month") or 0))
        return max(0, int(raw_limit or 0))
    except Exception:
        return max(0, int(limits.get("dialogs_per_month") or 0))


def tenant_usage_snapshot(
    tenant: Dict[str, Any],
    channel: str = "",
    source: str = "runtime",
    projected_units: int = 0,
) -> Dict[str, Any]:
    tenant_id = str((tenant or {}).get("_id") or (tenant or {}).get("id") or "").strip()
    dialog_limit = tenant_dialog_limit(tenant)
    exempt = usage_context_is_non_billable(channel, source)
    if not tenant_id:
        return {
            "allowed": False,
            "reason": "unavailable",
            "usage_current": 0,
            "usage_projected": 0,
            "usage_limit": dialog_limit,
            "limit_reached": False,
            "soft_limit_exceeded": False,
            "near_limit": False,
            "billable": False,
            "percent_used": 0.0,
            "remaining": 0,
        }
    if exempt or dialog_limit <= 0:
        return {
            "allowed": True,
            "reason": "ok",
            "usage_current": 0 if dialog_limit <= 0 else tenant_dialog_usage_current_month(tenant_id),
            "usage_projected": 0 if dialog_limit <= 0 else tenant_dialog_usage_current_month(tenant_id),
            "usage_limit": dialog_limit,
            "limit_reached": False,
            "soft_limit_exceeded": False,
            "near_limit": False,
            "billable": False,
            "percent_used": 0.0 if dialog_limit <= 0 else min(1.0, tenant_dialog_usage_current_month(tenant_id) / dialog_limit),
            "remaining": 0 if dialog_limit <= 0 else max(0, dialog_limit - tenant_dialog_usage_current_month(tenant_id)),
        }

    usage_current = tenant_dialog_usage_current_month(tenant_id)
    projected = usage_current + max(0, int(projected_units or 0))
    percent_used = (projected / dialog_limit) if dialog_limit > 0 else 0.0
    limit_reached = projected >= dialog_limit
    soft_limit_exceeded = projected > dialog_limit or usage_current >= dialog_limit
    near_limit = not limit_reached and percent_used >= 0.8
    remaining = max(0, dialog_limit - usage_current)
    reason = "soft_limit" if soft_limit_exceeded else "near_limit" if near_limit else "ok"
    return {
        "allowed": True,
        "reason": reason,
        "usage_current": usage_current,
        "usage_projected": projected,
        "usage_limit": dialog_limit,
        "limit_reached": limit_reached,
        "soft_limit_exceeded": soft_limit_exceeded,
        "near_limit": near_limit,
        "billable": True,
        "percent_used": percent_used,
        "remaining": remaining,
    }


def tenant_usage_allowed(tenant: Dict[str, Any], channel: str = "", source: str = "runtime") -> Tuple[bool, str, int, int]:
    snapshot = tenant_usage_snapshot(tenant, channel=channel, source=source, projected_units=0)
    return bool(snapshot.get("allowed")), str(snapshot.get("reason") or "ok"), int(snapshot.get("usage_current") or 0), int(snapshot.get("usage_limit") or 0)


def tenant_access_decision(tenant: Dict[str, Any], channel: str = "", source: str = "runtime") -> Dict[str, Any]:
    tenant = normalize_tenant_saas_fields(tenant or {})
    tenant_id = str(tenant.get("_id") or tenant.get("id") or "").strip()
    usage_snapshot = tenant_usage_snapshot(tenant, channel=channel, source=source, projected_units=0)
    lifecycle = tenant_lifecycle_payload(tenant)
    decision = {
        "allowed": True,
        "reason": "ok",
        "meta": {
            "tenant_id": tenant_id,
            "status": tenant_status_value(tenant),
            "subscription_status": lifecycle.get("subscription_status"),
            "effective_status": lifecycle.get("effective_status"),
            "trial_end": tenant_trial_end_value(tenant),
            "usage_current": int(usage_snapshot.get("usage_current") or 0),
            "usage_limit": int(usage_snapshot.get("usage_limit") or 0),
            "usage_projected": int(usage_snapshot.get("usage_projected") or 0),
            "usage_near_limit": bool(usage_snapshot.get("near_limit")),
            "usage_limit_reached": bool(usage_snapshot.get("limit_reached")),
            "usage_soft_limit_exceeded": bool(usage_snapshot.get("soft_limit_exceeded")),
            "usage_billable": bool(usage_snapshot.get("billable")),
            "plan": tenant_plan_meta(tenant).get("plan"),
        },
    }
    if not tenant_id:
        decision["allowed"] = False
        decision["reason"] = "unavailable"
        return decision

    effective_status = str(lifecycle.get("effective_status") or "trial")
    if lifecycle.get("blocked"):
        decision["allowed"] = False
        decision["reason"] = str(lifecycle.get("block_reason") or effective_status or "inactive")
        return decision

    if effective_status == "past_due":
        decision["reason"] = "past_due"

    if usage_snapshot.get("reason") in {"near_limit", "soft_limit"}:
        decision["reason"] = str(usage_snapshot.get("reason") or decision.get("reason") or "ok")

    return decision


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


def _text_mvp_fold_service_name(value: Any) -> str:
    txt = str(value or "").strip().lower()
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", txt).strip()


def text_mvp_localized_service_name(value: Any, lang: str) -> str:
    """Return a customer-facing service name for the active reply language.

    Some tenants may have a minimal service catalog where only the Latvian name
    is configured (for example `konsultācija`). Routing should keep using the
    canonical service key, but text replies in Russian/English should not expose
    raw Latvian labels when a safe common translation is obvious.
    """
    txt = str(value or "").strip()
    if not txt:
        return ""
    lang = get_lang(lang)
    folded = _text_mvp_fold_service_name(txt)
    if lang == "ru":
        known = {
            "konsultacija": "консультация",
            "konsultacijas": "консультация",
            "consultation": "консультация",
            "service": "сервис",
            "serviss": "сервис",
            "atbalsts": "поддержка",
            "support": "поддержка",
        }
        return known.get(folded, txt)
    if lang == "en":
        known = {
            "konsultacija": "consultation",
            "konsultacijas": "consultation",
            "консультация": "consultation",
            "serviss": "service",
            "сервис": "service",
            "atbalsts": "support",
            "поддержка": "support",
        }
        return known.get(folded, txt)
    return txt


def text_mvp_localized_price(price: Any, lang: str) -> str:
    txt = str(price or "").strip()
    if not txt:
        return ""
    lang = get_lang(lang)
    if lang == "ru":
        txt = re.sub(r"\beiro\b", "евро", txt, flags=re.IGNORECASE)
        txt = re.sub(r"\beur\b", "евро", txt, flags=re.IGNORECASE)
    elif lang == "en":
        txt = re.sub(r"\beiro\b", "EUR", txt, flags=re.IGNORECASE)
        txt = re.sub(r"\bевро\b", "EUR", txt, flags=re.IGNORECASE)
    return txt


def service_display_name(service_item: Optional[Dict[str, Any]], lang: str) -> str:
    if not service_item:
        return ""
    lang = get_lang(lang)
    raw = str(service_item.get(f"name_{lang}") or service_item.get("name_lv") or service_item.get("key") or "").strip()
    return text_mvp_localized_service_name(raw, lang)


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
    beard_name = service_display_name(beard_item, lang) or ("bārdas kopšanu" if lang == "lv" else "подравнивание бороды" if lang == "ru" else "a beard trim")
    if added:
        if lang == "ru":
            return f"Отлично 👍 Добавил {beard_name}. Ваша запись подтверждена на {when_text}."
        if lang == "en":
            return f"Great 👍 I added {beard_name}. Your booking is confirmed for {when_text}."
        return f"Lieliski 👍 Pievienoju arī {beard_name}. Jūsu pieraksts ir apstiprināts uz {when_text}."
    if lang == "ru":
        return f"Хорошо 👍 Оставляем {haircut_name}. Ваша запись подтверждена на {when_text}."
    if lang == "en":
        return f"No problem 👍 We’ll keep {haircut_name}. Your booking is confirmed for {when_text}."
    return f"Labi 👍 Paliekam pie {haircut_name}. Jūsu pieraksts ir apstiprināts uz {when_text}."


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
    norm_low = re.sub(r"\s+", " ", re.sub(r"[^\wĀ-žА-Яа-яЁё]+", " ", low, flags=re.UNICODE)).strip()
    folded_low = _fold_match_text(low)
    if low in alias_map:
        return alias_map[low]
    if norm_low in alias_map:
        return alias_map[norm_low]

    # Stage 25.6 hotfix: tolerate missing diacritics and inflected endings.
    # Example: "konsultaciju" should match "konsultācija" / "konsultāciju".
    folded_aliases: List[Tuple[int, str, str]] = []
    for alias, key in alias_map.items():
        folded_alias = _fold_match_text(alias)
        if folded_alias:
            folded_aliases.append((len(folded_alias), folded_alias, key))
    for _, folded_alias, key in sorted(folded_aliases, key=lambda x: x[0], reverse=True):
        if folded_alias == folded_low or folded_alias in folded_low or folded_low in folded_alias:
            return key

    # Prefer longest alias first so generic words don't beat specific phrases
    for alias in sorted(alias_map.keys(), key=len, reverse=True):
        if not alias:
            continue
        norm_alias = re.sub(r"\s+", " ", re.sub(r"[^\wĀ-žА-Яа-яЁё]+", " ", alias, flags=re.UNICODE)).strip()
        if alias in low or (norm_alias and norm_alias in norm_low):
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
        "matu griezums", "matu griezumu", "griezums", "griezumu",
        "apgriezt matus", "apgriezt", "frizūra", "frizura", "frizūru", "frizuru",
        "vīriešu frizūra", "viriesu frizura", "vīriešu frizūru", "viriesu frizuru",
        "vīriešu matu griezums", "viriesu matu griezums", "vīriešu matu griezumu", "viriesu matu griezumu",
        "подстричься", "стрижка", "стрижку", "мужская стрижка", "мужскую стрижку",
        "haircut", "mens haircut", "men's haircut", "cut hair", "trim hair"
    ])
    add_many(beard_key, [
        "bārda", "barda", "bārdu", "bardu", "bārdas korekcija", "bārdas korekciju",
        "bārdas trim", "bārdas trimu", "beard trim", "beard", "борода", "бороду", "подровнять бороду"
    ])
    add_many(combo_key, [
        "combo", "kombo", "комбо",
        "matu griezums un bārda", "matu griezumu un bārdu",
        "frizūra un bārda", "frizūru un bārdu",
        "haircut and beard", "стрижка и борода", "стрижку и бороду"
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

def infer_service_item_from_calendar_event(
    event: Optional[Dict[str, Any]],
    service_catalog: List[Dict[str, Any]],
    lang: str,
) -> Optional[Dict[str, Any]]:
    """Infer the original service from an existing calendar event.

    Stage 45: reschedule flows start from a calendar event, not from a fresh
    booking message. The event summary often contains the original service
    (for example, "Clinic Demo - konsultācija"). Persisting that service in
    the booking context lets the next user turn ("послезавтра вечером" /
    "parīt vakarā") regenerate slots without asking for the service again.
    """
    if not isinstance(event, dict):
        return None
    texts: List[str] = []
    summary = str(event.get("summary") or "").strip()
    description = str(event.get("description") or "").strip()
    if summary:
        texts.append(summary)
        if " - " in summary:
            texts.append(summary.split(" - ", 1)[1].strip())
    if description:
        texts.append(description)

    seen = set()
    for candidate in texts:
        candidate = str(candidate or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        service_item = extract_service_from_text(candidate, service_catalog, lang)
        if service_item:
            return service_item
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


def usage_soft_limit_warning_text(lang: str, usage_snapshot: Dict[str, Any]) -> str:
    lang = get_lang(lang)
    current = int(usage_snapshot.get("usage_projected") or usage_snapshot.get("usage_current") or 0)
    limit_value = int(usage_snapshot.get("usage_limit") or 0)
    if limit_value <= 0:
        return ""
    if usage_snapshot.get("soft_limit_exceeded") or usage_snapshot.get("limit_reached"):
        if lang == "ru":
            return f"Внимание: месячный лимит диалогов достигнут ({current}/{limit_value}). Диалог продолжается, но аккаунту нужен апдейт тарифа."
        if lang == "en":
            return f"Notice: the monthly dialog limit has been reached ({current}/{limit_value}). The conversation continues, but this account needs a plan update."
        return f"Uzmanību: mēneša dialogu limits ir sasniegts ({current}/{limit_value}). Saruna turpinās, bet kontam nepieciešams plāna atjauninājums."
    if usage_snapshot.get("near_limit"):
        if lang == "ru":
            return f"Внимание: использовано уже {current} из {limit_value} диалогов за месяц."
        if lang == "en":
            return f"Notice: {current} of {limit_value} dialogs have already been used this month."
        return f"Uzmanību: šomēnes jau izmantoti {current} no {limit_value} dialogiem."
    return ""


def apply_usage_soft_limit_warning(result: Dict[str, Any], lang: str, tenant: Dict[str, Any], channel: str, source: str = "runtime") -> Dict[str, Any]:
    result = dict(result or {})
    if str(result.get("status") or "").strip().lower() == "blocked":
        return result
    usage_snapshot = tenant_usage_snapshot(tenant, channel=channel, source=source, projected_units=1)
    warning_text = usage_soft_limit_warning_text(lang, usage_snapshot)
    if not warning_text:
        return result
    for key in ("msg_out", "reply_voice"):
        base = str(result.get(key) or "").strip()
        if not base:
            result[key] = warning_text
            continue
        if warning_text in base:
            continue
        result[key] = f"{base}\n\n{warning_text}"
    result["usage_current"] = int(usage_snapshot.get("usage_current") or 0)
    result["usage_projected"] = int(usage_snapshot.get("usage_projected") or 0)
    result["usage_limit"] = int(usage_snapshot.get("usage_limit") or 0)
    result["usage_near_limit"] = bool(usage_snapshot.get("near_limit"))
    result["usage_soft_limit_exceeded"] = bool(usage_snapshot.get("soft_limit_exceeded") or usage_snapshot.get("limit_reached"))
    return result


def blocked_result_for_lang(lang: str) -> Dict[str, Any]:
    return {
        "status": "blocked",
        "reply_voice": t(lang, "service_unavailable_voice"),
        "msg_out": t(lang, "service_unavailable_text"),
        "lang": lang,
    }


def blocked_result_for_reason(lang: str, reason: Optional[str]) -> Dict[str, Any]:
    low = str(reason or "").strip().lower()
    if low == "trial_expired":
        return {
            "status": "blocked",
            "reply_voice": t(lang, "trial_expired_voice"),
            "msg_out": t(lang, "trial_expired_text"),
            "lang": lang,
            "blocked_reason": low,
            "preserve_text": True,
        }
    if low == "inactive":
        return {
            "status": "blocked",
            "reply_voice": t(lang, "inactive_voice"),
            "msg_out": t(lang, "inactive_text"),
            "lang": lang,
            "blocked_reason": low,
            "preserve_text": True,
        }
    if low == "past_due":
        return {
            "status": "blocked",
            "reply_voice": t(lang, "past_due_voice"),
            "msg_out": t(lang, "past_due_text"),
            "lang": lang,
            "blocked_reason": low,
            "preserve_text": True,
        }
    base = blocked_result_for_lang(lang)
    base["blocked_reason"] = low or "unavailable"
    base["preserve_text"] = True
    return base


# -------------------------
# TWILIO REQUEST VALIDATION
# -------------------------
from urllib.parse import urlencode

install_twilio_signature_middleware(app)

# -------------------------
# TWILIO / OPENAI / GOOGLE
# -------------------------
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


# -------------------------
# STAGE 26 — CONVERSATIONAL SEMANTIC ROUTER
# -------------------------
def stage26_semantic_router_enabled(channel: str = "", source: str = "runtime") -> bool:
    flag = os.getenv("STAGE26_SEMANTIC_ROUTER_ENABLED", "").strip().lower()
    if flag in {"0", "false", "no", "off", "disabled"}:
        return False
    if flag in {"1", "true", "yes", "on", "enabled"}:
        return bool(OPENAI_API_KEY and LLM_INTELLIGENCE_ENABLED)
    # Default: enabled together with the existing LLM intelligence switch.
    return bool(OPENAI_API_KEY and LLM_INTELLIGENCE_ENABLED)


def _stage26_safe_list(value: Any, limit: int = 8) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(x).strip() for x in list(value)[:limit] if str(x).strip()]
    txt = str(value).strip()
    return [txt] if txt else []


def _stage26_action_hint(value: Any) -> Optional[str]:
    low = str(value or "").strip().lower()
    allowed = {
        "start_booking",
        "continue_booking",
        "answer_faq",
        "ask_service",
        "ask_date",
        "ask_time",
        "ask_confirm",
        "choose_slot",
        "confirm_yes",
        "confirm_no",
        "cancel",
        "reschedule",
        "greeting",
        "closure",
        "other",
    }
    return low if low in allowed else None


def stage26_semantic_route_message(
    msg: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    tenant: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    service_aliases: Dict[str, str],
    business_memory: str,
    llm_hint: Optional[Dict[str, Any]] = None,
    channel: str = "",
    source: str = "runtime",
) -> Dict[str, Any]:
    """Semantic interpretation layer for free conversational input.

    Safety contract:
    - this layer never performs calendar actions;
    - it only enriches understanding hints used by deterministic orchestration;
    - backend state machine and calendar guards remain authoritative.
    """
    if not stage26_semantic_router_enabled(channel, source):
        return {}
    raw_msg = str(msg or "").strip()
    if not raw_msg:
        return {}

    state = conversation_state(c or {})
    pending = pending or {}
    llm_hint = llm_hint or {}
    offered_slots = _slot_labels_from_pending(pending)
    alias_hint = ", ".join([f"{k} => {v}" for k, v in list(service_aliases.items())[:80]])
    current_context = {
        "language": get_lang(lang),
        "state": state,
        "active_booking_flow": is_active_booking_flow(c or {}),
        "known_service_key": (c or {}).get("service") or pending.get("service"),
        "known_service_display": pending.get("service_display"),
        "known_datetime_iso": (c or {}).get("datetime_iso") or pending.get("candidate_datetime_iso") or pending.get("awaiting_time_date_iso"),
        "offered_slots": offered_slots[:3],
        "existing_llm_hint": llm_hint,
    }

    system_prompt = (
        "You are Stage 26 Conversational Semantic Router for Repliq, an AI receptionist SaaS. "
        "Your job is to understand the user's conversational meaning and return structured JSON. "
        "Do not make bookings, do not invent availability, do not invent services. "
        "The backend orchestrator will decide all actions. "
        "Return strict JSON only with keys: intent, confidence, service, time_text, datetime_iso, confirmation, "
        "action_hint, missing_fields, user_goal, notes. "
        "intent must be one of booking, reschedule, cancel, info, greeting, closure, other. "
        "confirmation must be yes, no, or null. "
        "action_hint must be one of start_booking, continue_booking, answer_faq, ask_service, ask_date, ask_time, "
        "ask_confirm, choose_slot, confirm_yes, confirm_no, cancel, reschedule, greeting, closure, other. "
        "service must be a canonical service key from the alias map when clearly recognized, otherwise null. "
        "datetime_iso should only be present if the user clearly gave a date/time; otherwise null. "
        "time_text may contain natural time phrases like tomorrow afternoon / rīt pēcpusdienā / после работы. "
        "missing_fields must be a list using only service, date, time, confirmation. "
    )
    user_payload = {
        "today": str(now_ts().date()),
        "user_language": get_lang(lang),
        "business_name": settings.get("biz_name"),
        "business_hours": f"{settings.get('work_start')}-{settings.get('work_end')}",
        "known_services": service_catalog_summary(service_catalog, lang),
        "service_alias_map": alias_hint or "none",
        "business_memory": business_memory or "none",
        "context": current_context,
        "user_message": raw_msg,
    }

    try:
        raw = openai_chat_json(system_prompt, json.dumps(user_payload, ensure_ascii=False, default=str))
        if not isinstance(raw, dict):
            return {}
        intent = _normalize_llm_intent(raw.get("intent"))
        if str(raw.get("intent") or "").strip().lower() == "greeting":
            intent = "other"
        if str(raw.get("intent") or "").strip().lower() == "closure":
            intent = "other"
        try:
            confidence = max(0.0, min(1.0, float(raw.get("confidence") or 0.0)))
        except Exception:
            confidence = 0.0
        service_value = apply_service_aliases(raw.get("service"), service_aliases) or canonical_service_key_from_text(raw.get("service"), service_aliases)
        if service_value and not get_service_item_by_key(service_catalog, service_value):
            service_item = extract_service_from_text(service_value, service_catalog, lang)
            service_value = str((service_item or {}).get("key") or "").strip() or None
        out = {
            "intent": intent,
            "confidence": confidence,
            "service": service_value,
            "time_text": sanitize_conversation_time_text(raw.get("time_text")) or normalize_service(raw.get("time_text")),
            "datetime_iso": str(raw.get("datetime_iso") or "").strip() or None,
            "name": normalize_name(raw.get("name")),
            "confirmation": _normalize_llm_confirmation(raw.get("confirmation")),
            "action_hint": _stage26_action_hint(raw.get("action_hint")),
            "missing_fields": [x for x in _stage26_safe_list(raw.get("missing_fields"), 4) if x in {"service", "date", "time", "confirmation"}],
            "user_goal": _safe_compose_text(raw.get("user_goal"), 180),
            "notes": _safe_compose_text(raw.get("notes"), 220),
            "stage26": True,
        }
        return out
    except Exception as e:
        log.error("stage26_semantic_router_failed err=%s", e)
        return {}


def merge_stage26_into_llm_hint(base_hint: Optional[Dict[str, Any]], semantic: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(base_hint or {})
    semantic = semantic or {}
    if not semantic:
        return merged
    sem_conf = float(semantic.get("confidence") or 0.0)
    base_conf = float(merged.get("confidence") or 0.0)

    if semantic.get("intent") and sem_conf >= max(0.45, base_conf - 0.1):
        merged["intent"] = semantic.get("intent")
        merged["confidence"] = max(base_conf, sem_conf)
    for key in ("service", "time_text", "datetime_iso", "name", "confirmation"):
        if semantic.get(key) and not merged.get(key):
            merged[key] = semantic.get(key)
    # confirmation/action hints are often the most valuable for short replies.
    if semantic.get("confirmation"):
        merged["confirmation"] = semantic.get("confirmation")
    if semantic.get("action_hint"):
        merged["stage26_action_hint"] = semantic.get("action_hint")
    if semantic.get("missing_fields"):
        merged["stage26_missing_fields"] = semantic.get("missing_fields")
    if semantic.get("user_goal"):
        merged["stage26_user_goal"] = semantic.get("user_goal")
    merged["stage26_semantic"] = semantic
    return merged


def remember_stage26_datetime_hint(c: Dict[str, Any], pending: Dict[str, Any], semantic_hint: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    pending = pending or {}
    if not semantic_hint:
        return c, pending
    dt_iso = str(semantic_hint.get("datetime_iso") or "").strip()
    dtv = parse_dt_any_tz(dt_iso)
    if dtv:
        if dtv.hour != 9 or dtv.minute != 0:
            pending["candidate_datetime_iso"] = dtv.isoformat()
            pending["awaiting_time_date_iso"] = dtv.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
            pending["time_text"] = f"{dtv.hour:02d}:{dtv.minute:02d}"
            c["time_text"] = pending["time_text"]
        else:
            pending["awaiting_time_date_iso"] = dtv.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
    time_text = sanitize_conversation_time_text(semantic_hint.get("time_text"))
    if time_text and not pending.get("time_text"):
        pending["time_text"] = time_text
        c["time_text"] = time_text
    if semantic_hint.get("intent") == "booking" or semantic_hint.get("action_hint") in {"start_booking", "continue_booking"}:
        pending["booking_intent"] = True
    c["pending"] = pending or None
    return c, pending


# -------------------------
# STAGE 27 — ENTITY PERSISTENCE LAYER
# -------------------------
def _stage27_service_candidates_for_item(item: Dict[str, Any], lang: str) -> List[str]:
    values: List[str] = []
    if not item:
        return values
    for key in ("key", "name_lv", "name_ru", "name_en"):
        if item.get(key):
            values.append(str(item.get(key)))
    for key in (f"aliases_{get_lang(lang)}", "aliases_lv", "aliases_ru", "aliases_en"):
        for alias in item.get(key) or []:
            if alias:
                values.append(str(alias))
    return [v.strip() for v in values if v and v.strip()]


def stage27_extract_service_item_from_turn(
    msg: str,
    llm_hint: Optional[Dict[str, Any]],
    service_catalog: List[Dict[str, Any]],
    service_aliases: Dict[str, str],
    lang: str,
) -> Optional[Dict[str, Any]]:
    """Find a service from the current turn with tolerant matching.

    This layer is intentionally deterministic. It fixes cases where the LLM/router
    understands booking intent but a Latvian inflected service form such as
    "konsultāciju" is not persisted as "konsultācija".
    """
    raw = str(msg or "").strip()
    if raw:
        direct_key = canonical_service_key_from_text(raw, service_aliases)
        item = get_service_item_by_key(service_catalog, direct_key) if direct_key else None
        if item:
            return item
        item = extract_service_from_text(raw, service_catalog, lang)
        if item:
            return item

    llm_hint = llm_hint or {}
    for value in (llm_hint.get("service"), (llm_hint.get("stage26_semantic") or {}).get("service")):
        if not value:
            continue
        key = apply_service_aliases(value, service_aliases) or canonical_service_key_from_text(value, service_aliases)
        item = get_service_item_by_key(service_catalog, key) if key else None
        if item:
            return item
        item = extract_service_from_text(value, service_catalog, lang)
        if item:
            return item

    folded_raw = _fold_match_text(raw)
    if not folded_raw:
        return None

    # Stage 27.1 hotfix: common consultation stems across Latvian inflections
    # and missing diacritics: konsultācija / konsultāciju / konsultaciju.
    if any(stem in folded_raw for stem in ("konsultac", "konsultacij", "consultation", "консультац")):
        for item in service_catalog:
            hay = _fold_match_text(" ".join(_stage27_service_candidates_for_item(item, lang)))
            if any(stem in hay for stem in ("konsultac", "konsultacij", "consultation", "консультац")):
                return item

    raw_words = set(folded_raw.split())
    for item in service_catalog:
        for candidate in _stage27_service_candidates_for_item(item, lang):
            folded_candidate = _fold_match_text(candidate)
            if not folded_candidate:
                continue
            if folded_candidate in folded_raw or folded_raw in folded_candidate:
                return item
            # Latvian/Russian inflections: compare a stable prefix stem.
            compact = folded_candidate.replace(" ", "")
            if len(compact) >= 7:
                stem = compact[:8]
                if stem and stem in folded_raw.replace(" ", ""):
                    return item
            for word in raw_words:
                if len(word) >= 7 and len(compact) >= 7 and word[:7] == compact[:7]:
                    return item
    return None


def stage27_persist_entities_from_turn(
    c: Dict[str, Any],
    pending: Dict[str, Any],
    msg: str,
    lang: str,
    llm_hint: Optional[Dict[str, Any]],
    service_catalog: List[Dict[str, Any]],
    service_aliases: Dict[str, str],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Persist service/date/time entities before state routing.

    Safety contract:
    - does not create bookings;
    - does not check calendar;
    - only stores clearly extracted entities and advances missing-field state.
    """
    pending = pending or {}
    llm_hint = llm_hint or {}
    semantic = llm_hint.get("stage26_semantic") or {}
    booking_like = (
        _normalize_llm_intent(llm_hint.get("intent")) == "booking"
        or semantic.get("intent") == "booking"
        or llm_hint.get("stage26_action_hint") in {"start_booking", "continue_booking"}
        or is_booking_opener(msg)
        or is_active_booking_flow(c)
    )

    service_item = stage27_extract_service_item_from_turn(msg, llm_hint, service_catalog, service_aliases, lang)
    if service_item and not str(c.get("service") or pending.get("service") or "").strip():
        c, pending = remember_booking_service(c, pending, service_item, lang)
        pending["booking_intent"] = True

    if booking_like or service_item or str(c.get("service") or pending.get("service") or "").strip():
        c, pending = remember_partial_booking_datetime_from_message(c, pending, msg)
        if semantic:
            c, pending = remember_stage26_datetime_hint(c, pending, semantic)
        pending["booking_intent"] = True

    if (llm_hint.get("name") or semantic.get("name")) and not c.get("name"):
        c["name"] = normalize_name(llm_hint.get("name") or semantic.get("name"))

    has_service = bool(str(c.get("service") or pending.get("service") or "").strip())
    has_date = bool(parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip()))
    has_candidate_time = bool(booking_candidate_datetime_from_context(c, pending))

    if booking_like or has_service or has_date or has_candidate_time:
        if has_service and has_candidate_time:
            # Existing booking flow will check availability / ask confirmation.
            c["state"] = STATE_AWAITING_TIME
        elif has_service and has_date:
            c["state"] = STATE_AWAITING_TIME
        elif has_service:
            c["state"] = STATE_AWAITING_DATE
        else:
            c["state"] = STATE_AWAITING_SERVICE

    c["pending"] = pending or None
    return c, pending



ORCH_ACTION_CONTINUE = "continue_legacy"
ORCH_ACTION_FAQ = "faq"
ORCH_ACTION_GREET = "greet"
ORCH_ACTION_IDENTITY = "identity"
ORCH_ACTION_HOURS = "hours"
ORCH_ACTION_START_BOOKING = "start_booking"
ORCH_ACTION_CANCEL = "cancel"
ORCH_ACTION_RESCHEDULE = "reschedule"
ORCH_ACTION_ASK_DATE = "ask_date"
ORCH_ACTION_CLARIFY_TIME = "clarify_time"
ORCH_ACTION_CLARIFY_CONFIRM = "clarify_confirm"
ORCH_ACTION_CHOOSE_SLOT = "choose_slot"
ORCH_ACTION_CONFIRM_YES = "confirm_yes"
ORCH_ACTION_CONFIRM_NO = "confirm_no"

ORCHESTRATION_TOOLS: Dict[str, Dict[str, Any]] = {
    "check_availability": {"kind": "calendar", "description": "Find available slots in the tenant calendar."},
    "create_booking": {"kind": "calendar", "description": "Create a booking event in the tenant calendar."},
    "cancel_booking": {"kind": "calendar", "description": "Cancel an existing booking."},
    "reschedule_booking": {"kind": "calendar", "description": "Move an existing booking to a new time."},
    "get_business_info": {"kind": "faq", "description": "Return structured business information such as address, price, duration, or services."},
}


def orchestration_tool_registry() -> Dict[str, Dict[str, Any]]:
    return dict(ORCHESTRATION_TOOLS)


def build_understanding_result(
    msg: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    llm_hint: Optional[Dict[str, Any]],
    tenant: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    service_aliases: Dict[str, str],
    business_memory: str,
) -> Dict[str, Any]:
    raw = (msg or "").strip()
    low = raw.lower()
    llm_hint = llm_hint or {}
    llm_intent = _normalize_llm_intent(llm_hint.get("intent"))
    try:
        confidence = float(llm_hint.get("confidence") or 0.0)
    except Exception:
        confidence = 0.0

    direct_service_key = canonical_service_key_from_text(raw, service_aliases)
    service_item = get_service_item_by_key(service_catalog, direct_service_key) if direct_service_key else None
    if not service_item:
        service_item = extract_service_from_text(raw, service_catalog, lang)
    if not service_item and llm_hint.get("service"):
        service_item = get_service_item_by_key(service_catalog, llm_hint.get("service"))

    faq_result = try_barbershop_faq(
        msg=raw,
        lang=lang,
        tenant=tenant,
        settings=settings,
        service_catalog=service_catalog,
        service_aliases=service_aliases,
        business_memory=business_memory,
        current_service_key=(c or {}).get("service") or (pending or {}).get("service"),
    ) if raw else None

    explicit_cancel = any(w in low for w in ["atcelt", "отменить", "cancel"])
    explicit_reschedule = any(w in low for w in ["pārcelt", "перенести", "reschedule", "move my appointment", "change my appointment", "перенеси запись", "перенести запись", "pārcelt pierakstu"])

    signals: List[str] = []
    if is_greeting_only(raw):
        signals.append("greeting_only")
    if is_identity_check(raw):
        signals.append("identity_check")
    if is_hours_question(raw):
        signals.append("hours_question")
    if is_booking_opener(raw):
        signals.append("booking_opener")
    if is_yes_text(raw, lang):
        signals.append("yes")
    if is_no_text(raw, lang):
        signals.append("no")
    if is_hesitation_text(raw, lang):
        signals.append("hesitation")
    if is_other_day_text(raw, lang):
        signals.append("other_day")
    if has_explicit_time(raw):
        signals.append("explicit_time")
    if has_date_reference(raw):
        signals.append("date_ref")
    if parse_time_window(raw):
        signals.append("time_window")
    if extract_slot_choice(raw, pending):
        signals.append("slot_choice")
    if free_router_is_variants_request(raw, lang):
        signals.append("variants_request")
    if explicit_cancel:
        signals.append("cancel_request")
    if explicit_reschedule:
        signals.append("reschedule_request")

    return {
        "raw_text": raw,
        "lang": lang,
        "state": conversation_state(c),
        "active_flow": is_active_booking_flow(c),
        "intent": llm_intent,
        "confidence": max(0.0, min(1.0, confidence)),
        "confirmation": _normalize_llm_confirmation(llm_hint.get("confirmation")),
        "stage26_action_hint": llm_hint.get("stage26_action_hint"),
        "stage26_missing_fields": llm_hint.get("stage26_missing_fields") or [],
        "stage26_user_goal": llm_hint.get("stage26_user_goal"),
        "signals": signals,
        "entities": {
            "service_key": str((service_item or {}).get("key") or "").strip() or None,
            "service_name": service_display_name(service_item, lang) if service_item else None,
            "time_text": sanitize_conversation_time_text(llm_hint.get("time_text")),
            "datetime_iso": str(llm_hint.get("datetime_iso") or "").strip() or None,
            "name": normalize_name(llm_hint.get("name")),
            "selected_slot_iso": extract_slot_choice(raw, pending),
        },
        "faq_result": faq_result,
        "tools": list(orchestration_tool_registry().keys()),
    }


def default_orchestration_decision(understanding: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "action": ORCH_ACTION_CONTINUE,
        "next_state": understanding.get("state"),
        "reply_mode": "legacy",
        "needs_tool": False,
        "tool_name": None,
        "tool_args": {},
        "reason": "fallback_to_legacy_flow",
    }


def orchestrate_turn(
    c: Dict[str, Any],
    msg: str,
    lang: str,
    understanding: Dict[str, Any],
) -> Dict[str, Any]:
    decision = default_orchestration_decision(understanding)
    state = conversation_state(c)
    active_flow = bool(understanding.get("active_flow"))
    signals = set(understanding.get("signals") or [])
    intent = understanding.get("intent")
    confidence = float(understanding.get("confidence") or 0.0)
    selected_slot_iso = ((understanding.get("entities") or {}).get("selected_slot_iso"))
    stage26_action_hint = str(understanding.get("stage26_action_hint") or "").strip().lower()

    if stage26_action_hint == "answer_faq" and understanding.get("faq_result"):
        decision.update({
            "action": ORCH_ACTION_FAQ,
            "needs_tool": True,
            "tool_name": "get_business_info",
            "reason": "stage26_faq_detected",
            "reply_mode": "direct",
        })
        return decision

    if not active_flow and stage26_action_hint == "greeting":
        decision.update({"action": ORCH_ACTION_GREET, "reason": "stage26_greeting", "reply_mode": "direct"})
        return decision

    if understanding.get("faq_result"):
        decision.update({
            "action": ORCH_ACTION_FAQ,
            "needs_tool": True,
            "tool_name": "get_business_info",
            "reason": "faq_detected",
            "reply_mode": "direct",
        })
        return decision

    if not active_flow and "greeting_only" in signals:
        decision.update({"action": ORCH_ACTION_GREET, "reason": "greeting_only_detected", "reply_mode": "direct"})
        return decision
    if not active_flow and "identity_check" in signals:
        decision.update({"action": ORCH_ACTION_IDENTITY, "reason": "identity_check_detected", "reply_mode": "direct"})
        return decision
    if not active_flow and "hours_question" in signals:
        decision.update({"action": ORCH_ACTION_HOURS, "reason": "hours_question_detected", "reply_mode": "direct"})
        return decision

    if stage26_action_hint == "cancel" or "cancel_request" in signals or (not active_flow and intent == "cancel" and confidence >= LLM_INTENT_MIN_CONFIDENCE):
        decision.update({
            "action": ORCH_ACTION_CANCEL,
            "needs_tool": True,
            "tool_name": "cancel_booking",
            "reason": "cancel_intent_detected",
        })
        return decision

    if stage26_action_hint == "reschedule" or "reschedule_request" in signals or (not active_flow and intent == "reschedule" and confidence >= LLM_INTENT_MIN_CONFIDENCE):
        decision.update({
            "action": ORCH_ACTION_RESCHEDULE,
            "needs_tool": True,
            "tool_name": "reschedule_booking",
            "reason": "reschedule_intent_detected",
        })
        return decision

    if stage26_action_hint in {"start_booking", "continue_booking"} or "booking_opener" in signals or (not active_flow and intent == "booking" and confidence >= LLM_INTENT_MIN_CONFIDENCE):
        decision.update({
            "action": ORCH_ACTION_START_BOOKING,
            "next_state": STATE_AWAITING_SERVICE,
            "reason": "booking_intent_detected",
            "reply_mode": "mixed",
        })
        if (understanding.get("entities") or {}).get("service_key"):
            decision["next_state"] = STATE_AWAITING_DATE
        return decision

    if state == STATE_AWAITING_TIME:
        if "other_day" in signals:
            decision.update({"action": ORCH_ACTION_ASK_DATE, "next_state": STATE_AWAITING_DATE, "reason": "other_day_in_time_selection", "reply_mode": "direct"})
            return decision
        if "hesitation" in signals:
            decision.update({"action": ORCH_ACTION_CLARIFY_TIME, "next_state": STATE_AWAITING_TIME, "reason": "hesitation_in_time_selection", "reply_mode": "direct"})
            return decision
        if selected_slot_iso:
            decision.update({"action": ORCH_ACTION_CHOOSE_SLOT, "next_state": STATE_AWAITING_CONFIRM, "needs_tool": True, "tool_name": "check_availability", "tool_args": {"slot_iso": selected_slot_iso}, "reason": "slot_selected"})
            return decision

    if state == STATE_AWAITING_CONFIRM:
        if "other_day" in signals:
            decision.update({"action": ORCH_ACTION_ASK_DATE, "next_state": STATE_AWAITING_DATE, "reason": "other_day_in_confirm", "reply_mode": "direct"})
            return decision
        if "hesitation" in signals:
            decision.update({"action": ORCH_ACTION_CLARIFY_CONFIRM, "next_state": STATE_AWAITING_CONFIRM, "reason": "hesitation_in_confirm", "reply_mode": "direct"})
            return decision
        if stage26_action_hint == "confirm_yes" or "yes" in signals or understanding.get("confirmation") == "yes":
            decision.update({"action": ORCH_ACTION_CONFIRM_YES, "needs_tool": True, "tool_name": "create_booking", "reason": "confirm_yes_detected"})
            return decision
        if stage26_action_hint == "confirm_no" or "no" in signals or understanding.get("confirmation") == "no":
            decision.update({"action": ORCH_ACTION_CONFIRM_NO, "reason": "confirm_no_detected"})
            return decision

    return decision



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
    if stage35_calendar_safe_mode_active():
        log.info("stage35_calendar_safe_mode freebusy_skipped calendar_id=%s start=%s end=%s", calendar_id, dt_start, dt_end)
        return False
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
    if stage35_calendar_safe_mode_active():
        log.info("stage35_calendar_safe_mode create_event_skipped calendar_id=%s start=%s summary=%s", calendar_id, dt_start, summary)
        return "stage35://calendar-safe-mode/dummy-event"
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
    if stage35_calendar_safe_mode_active():
        log.info("stage35_calendar_safe_mode update_event_skipped calendar_id=%s event_id=%s start=%s", calendar_id, event_id, dt_start)
        return "stage35://calendar-safe-mode/dummy-updated-event"
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
    if stage35_calendar_safe_mode_active():
        fixture = stage35_calendar_event_fixture()
        if fixture:
            if tenant_id:
                if event_belongs_to_tenant(fixture, tenant_id, phone):
                    log.info("stage35_calendar_safe_mode find_next_event_fixture_hit calendar_id=%s phone=%s tenant_id=%s", calendar_id, phone, tenant_id)
                    return fixture
            else:
                desc = fixture.get("description") or ""
                phone_norm = norm_user_key(phone)
                if (phone_norm and phone_norm in norm_user_key(desc)) or (phone and phone in desc):
                    log.info("stage35_calendar_safe_mode find_next_event_fixture_hit calendar_id=%s phone=%s", calendar_id, phone)
                    return fixture
        log.info("stage35_calendar_safe_mode find_next_event_skipped calendar_id=%s phone=%s", calendar_id, phone)
        return None
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
    if stage35_calendar_safe_mode_active():
        log.info("stage35_calendar_safe_mode delete_event_skipped calendar_id=%s event_id=%s", calendar_id, event_id)
        return True
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

HESITATION_WORDS = {
    "lv": {"nezinu", "grūti pateikt", "gruti pateikt", "varbūt vēlāk", "varbut velak", "neesmu drošs", "neesmu droš a", "neesmu droša", "nav svarīgi", "nav svarigi"},
    "ru": {"не знаю", "не уверен", "не уверена", "может позже", "пока не знаю", "затрудняюсь"},
    "en": {"not sure", "i am not sure", "i'm not sure", "maybe later", "dont know", "don't know", "not certain"},
}

# Stage 24 Hotfix: protect explicit time parsing from date tokens like "15.05".
# The original parser is kept, but date-looking DD.MM / DD/MM / DD-MM tokens
# are stripped before time extraction so "15.05 10:00" resolves to 10:00,
# while a bare date does not become accidental 15:05.
_core_parse_explicit_time_parts = parse_explicit_time_parts

def parse_explicit_time_parts(text_: Optional[str]) -> Optional[Tuple[int, int]]:
    src = str(text_ or "").strip()
    if not src:
        return None

    date_token_pattern = r"(?<!\d)(?:[0-2]?\d|3[01])[./-](?:0?[1-9]|1[0-2])(?:[./-]\d{2,4})?(?!\d)"
    without_dates = re.sub(date_token_pattern, " ", src)
    if without_dates.strip() != src.strip():
        parsed_after_date_strip = _core_parse_explicit_time_parts(without_dates)
        if parsed_after_date_strip:
            return parsed_after_date_strip
        return None

    return _core_parse_explicit_time_parts(src)


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


def booking_candidate_datetime_from_context(c: Dict[str, Any], pending: Dict[str, Any]) -> Optional[datetime]:
    """Return the best partially remembered date/time from current booking context."""
    pending = pending or {}
    candidates = [
        pending.get("candidate_datetime_iso"),
        pending.get("requested_datetime_iso"),
        pending.get("partial_datetime_iso"),
        pending.get("datetime_iso"),
        c.get("datetime_iso"),
    ]
    for value in candidates:
        dtv = parse_dt_any_tz(str(value or "").strip())
        if dtv:
            # candidate must include an actual time, not just the default 09:00 date holder
            if dtv.hour != 9 or dtv.minute != 0:
                return dtv

    # If date and explicit time were stored separately, combine them.
    base_day = parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip())
    time_value = pending.get("requested_time") or pending.get("partial_time") or pending.get("time_text") or c.get("time_text")
    parts = parse_explicit_time_parts(str(time_value or ""))
    if base_day and parts:
        hh, mm = parts
        return base_day.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return None


def remember_partial_booking_datetime_from_message(c: Dict[str, Any], pending: Dict[str, Any], msg: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Persist date/time details even if service is missing."""
    pending = pending or {}
    raw = msg or ""
    natural_dt = parse_natural_datetime(raw)
    date_only_dt = parse_date_only_text(raw)
    time_parts = parse_explicit_time_parts(raw)
    time_window = parse_time_window(raw)

    if time_window:
        pending["preferred_time_window"] = [time_window[0], time_window[1]]

    if natural_dt and time_parts:
        pending["candidate_datetime_iso"] = natural_dt.isoformat()
        pending["awaiting_time_date_iso"] = natural_dt.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
        pending["time_text"] = f"{time_parts[0]:02d}:{time_parts[1]:02d}"
        c["time_text"] = pending["time_text"]
    elif time_parts and parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip()):
        # Stage 24 Hotfix: user can answer with time-only after date was already remembered.
        # This also prevents stale pending["time_text"] from the rejected slot being reused.
        base_day = parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip())
        hh, mm = time_parts
        candidate = base_day.replace(hour=hh, minute=mm, second=0, microsecond=0)
        pending["candidate_datetime_iso"] = candidate.isoformat()
        pending["time_text"] = f"{hh:02d}:{mm:02d}"
        c["time_text"] = pending["time_text"]
    elif natural_dt:
        pending["awaiting_time_date_iso"] = natural_dt.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
    elif date_only_dt:
        pending["awaiting_time_date_iso"] = date_only_dt.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()

    # Critical fallback: date reference + explicit time in one message.
    if date_only_dt and time_parts and not pending.get("candidate_datetime_iso"):
        hh, mm = time_parts
        candidate = date_only_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
        pending["candidate_datetime_iso"] = candidate.isoformat()
        pending["awaiting_time_date_iso"] = candidate.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
        pending["time_text"] = f"{hh:02d}:{mm:02d}"
        c["time_text"] = pending["time_text"]

    pending["booking_intent"] = True
    c["pending"] = pending
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


def _normalize_phrase_text(text_: Optional[str]) -> str:
    low = (text_ or "").strip().lower()
    low = re.sub(r"[\,\.\!\?\;\:\-_/]+", " ", low)
    low = re.sub(r"\s+", " ", low).strip()
    return low

def _fold_match_text(text_: Optional[str]) -> str:
    """Lowercase + remove accents/diacritics for tolerant LV/RU/EN matching."""
    src = str(text_ or "").strip().lower()
    if not src:
        return ""
    try:
        src = "".join(ch for ch in unicodedata.normalize("NFKD", src) if not unicodedata.combining(ch))
    except Exception:
        pass
    src = src.replace("ё", "е")
    src = re.sub(r"[^\wА-Яа-я]+", " ", src, flags=re.UNICODE)
    return re.sub(r"\s+", " ", src).strip()


def is_hesitation_text(text_: Optional[str], lang: str) -> bool:
    low = _normalize_phrase_text(text_)
    if not low:
        return False
    allowed = set().union(*HESITATION_WORDS.values())
    allowed.update(HESITATION_WORDS.get(get_lang(lang), set()))
    if low in allowed:
        return True
    return any(phrase in low for phrase in allowed if phrase)


def is_other_day_text(text_: Optional[str], lang: str) -> bool:
    low = _normalize_phrase_text(text_)
    if not low:
        return False
    phrases = {
        "lv": {"citu dienu", "labak citu dienu", "labāk citu dienu", "cita diena", "ne citu dienu", "vēlos citu dienu"},
        "ru": {"другой день", "на другой день", "давайте другой день", "лучше другой день", "другая дата"},
        "en": {"other day", "another day", "different day", "better another day", "lets do another day", "let's do another day"},
    }
    allowed = set().union(*phrases.values())
    allowed.update(phrases.get(get_lang(lang), set()))
    return any(phrase in low for phrase in allowed if phrase)


def detect_time_shift_direction(text_: Optional[str], lang: str) -> Optional[str]:
    low = _normalize_phrase_text(text_)
    if not low:
        return None
    earlier = {
        "lv": {"agrāk", "agrak", "nedaudz agrāk", "drusku agrāk", "mazliet agrāk", "ātrāk", "atrak"},
        "ru": {"раньше", "пораньше", "чуть раньше", "немного раньше"},
        "en": {"earlier", "a bit earlier", "slightly earlier"},
    }
    later = {
        "lv": {"vēlāk", "velak", "nedaudz vēlāk", "drusku vēlāk", "mazliet vēlāk"},
        "ru": {"позже", "попозже", "чуть позже", "немного позже"},
        "en": {"later", "a bit later", "slightly later"},
    }
    all_earlier = set().union(*earlier.values())
    all_later = set().union(*later.values())
    all_earlier.update(earlier.get(get_lang(lang), set()))
    all_later.update(later.get(get_lang(lang), set()))
    if any(p in low for p in all_earlier if p):
        return "earlier"
    if any(p in low for p in all_later if p):
        return "later"
    return None


def smart_service_clarify_prompt(lang: str, service_catalog: List[Dict[str, Any]]) -> str:
    options = barber_service_options_text(lang, service_catalog, max_items=2)
    if lang == "ru":
        return f"Могу предложить, например, {options}. Что вам ближе?" if options else "Что хотите сделать — стрижку или бороду?"
    if lang == "en":
        return f"I can offer, for example, {options}. What would you like?" if options else "Would you like a haircut or a beard trim?"
    return f"Varu piedāvāt, piemēram, {options}. Kas jums būtu tuvāk?" if options else "Vai vēlaties frizūru vai bārdu?"


def smart_date_clarify_prompt(lang: str) -> str:
    if lang == "ru":
        return "Вам удобнее сегодня, завтра или другой день?"
    if lang == "en":
        return "Would today, tomorrow, or another day work better for you?"
    return "Vai jums ērtāk būtu šodien, rīt vai cita diena?"


def clear_booking_loop_meta(pending: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(pending, dict):
        pending.pop("loop_count", None)
        pending.pop("last_prompt_type", None)
    return pending


def bump_time_loop_meta(pending: Dict[str, Any], prompt_type: str) -> int:
    if not isinstance(pending, dict):
        return 0
    prev_type = str(pending.get("last_prompt_type") or "").strip()
    prev_count = int(pending.get("loop_count") or 0)
    pending["loop_count"] = prev_count + 1 if prev_type == prompt_type else 1
    pending["last_prompt_type"] = prompt_type
    return int(pending["loop_count"])


def find_negotiation_slots_for_direction(
    calendar_id: str,
    base_day: datetime,
    anchor_dt: datetime,
    direction: str,
    duration_min: int,
    work_start: str,
    work_end: str,
    limit: int = 3,
    business_rules: Optional[Dict[str, Any]] = None,
    service_account_json: Optional[str] = None,
) -> List[datetime]:
    slots = find_first_n_slots_for_day(
        calendar_id=calendar_id,
        day_dt=base_day,
        duration_min=duration_min,
        work_start=work_start,
        work_end=work_end,
        limit=max(limit * 12, 24),
        business_rules=business_rules,
        service_account_json=service_account_json,
    )
    if not slots:
        return []
    if direction == "earlier":
        filtered = [s for s in slots if s < anchor_dt]
        return filtered[-limit:] if filtered else []
    filtered = [s for s in slots if s > anchor_dt]
    return filtered[:limit] if filtered else []


def negotiation_slots_response(
    tenant_id: str,
    user_key: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    slots: List[datetime],
) -> Dict[str, Any]:
    clear_booking_loop_meta(pending)
    if len(slots) >= 3:
        pending = set_offered_slots(pending, slots[:3])
        c["pending"] = pending
        c["state"] = STATE_AWAITING_TIME
        c["datetime_iso"] = None
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
        c["state"] = STATE_AWAITING_TIME
        c["datetime_iso"] = None
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
        "reply_voice": t(lang, "time_selection_uncertain"),
        "msg_out": t(lang, "time_selection_uncertain"),
        "lang": lang,
        "preserve_text": True,
    }


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

    month_names = {
        "jan": 1, "january": 1, "janvaris": 1, "janvāris": 1, "janvari": 1, "janvārī": 1, "января": 1,
        "feb": 2, "february": 2, "februaris": 2, "februāris": 2, "februari": 2, "februārī": 2, "февраля": 2,
        "mar": 3, "march": 3, "marts": 3, "marta": 3, "martā": 3, "марта": 3,
        "apr": 4, "april": 4, "aprīlis": 4, "aprilis": 4, "aprili": 4, "aprīlī": 4, "апреля": 4,
        "may": 5, "maijs": 5, "maija": 5, "maijā": 5, "мая": 5,
        "jun": 6, "june": 6, "jūnijs": 6, "junijs": 6, "junija": 6, "jūnijā": 6, "июня": 6,
        "jul": 7, "july": 7, "jūlijs": 7, "julijs": 7, "julija": 7, "jūlijā": 7, "июля": 7,
        "aug": 8, "august": 8, "augusts": 8, "augusta": 8, "augustā": 8, "августа": 8,
        "sep": 9, "september": 9, "septembris": 9, "septembri": 9, "septembrī": 9, "сентября": 9,
        "oct": 10, "october": 10, "oktobris": 10, "oktobri": 10, "oktobrī": 10, "октября": 10,
        "nov": 11, "november": 11, "novembris": 11, "novembri": 11, "novembrī": 11, "ноября": 11,
        "dec": 12, "december": 12, "decembris": 12, "decembri": 12, "decembrī": 12, "декабря": 12,
    }
    folded_src = _fold_match_text(src)
    md = re.search(r"\b(\d{1,2})\s+([a-zа-я]+)\b", folded_src, flags=re.IGNORECASE)
    if md:
        dd = int(md.group(1))
        month_word = md.group(2).strip().lower()
        mo = month_names.get(month_word)
        if mo:
            try:
                return datetime(today_local().year, mo, dd, 9, 0, tzinfo=TZ)
            except Exception:
                pass

    base = today_local()

    # Weekdays must win over relative substrings like "rīt" inside "rīta".
    for wd, hints in WEEKDAY_HINTS.items():
        if _contains_any_phrase(src, hints):
            d = next_weekday_date(wd, base)
            return datetime.combine(d, datetime.min.time(), tzinfo=TZ).replace(hour=9)

    # Stage 37: Latvian relative dates must be ordered from longest to shortest.
    # "aizparīt" contains "parīt", so it must be checked first.
    if _contains_any_phrase(src, ["aizparīt", "aizparit"]):
        return datetime.combine(base + timedelta(days=3), datetime.min.time(), tzinfo=TZ).replace(hour=9)
    if _contains_any_phrase(src, ["parīt", "parit", "послезавтра", "day after tomorrow"]):
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
    pending = pending or {}
    # Stage 36.1: keep fuzzy time preferences across recovery turns.
    # Example: "tomorrow evening" -> "not tomorrow" -> "day after tomorrow"
    # must still offer evening slots, not morning generic availability.
    for key in ("preferred_time_window", "stage36_recovery_time_window", "last_preferred_time_window"):
        raw = pending.get(key)
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            try:
                start_h = max(0, min(23, int(raw[0])))
                end_h = max(start_h + 1, min(24, int(raw[1])))
                return start_h, end_h
            except Exception:
                continue
    return None


def stage36_remember_time_window_context(pending: Dict[str, Any]) -> Dict[str, Any]:
    pending = pending or {}
    win = pending_time_window_tuple(pending)
    if win:
        pending["preferred_time_window"] = [win[0], win[1]]
        pending["last_preferred_time_window"] = [win[0], win[1]]
        pending["stage36_recovery_time_window"] = [win[0], win[1]]
    return pending


def stage36_recover_time_window_context(pending: Dict[str, Any]) -> Dict[str, Any]:
    pending = pending or {}
    win = pending_time_window_tuple(pending)
    if win:
        pending["preferred_time_window"] = [win[0], win[1]]
        pending["last_preferred_time_window"] = [win[0], win[1]]
        pending["stage36_recovery_time_window"] = [win[0], win[1]]
    return pending


# Stage 36.2: direct date refinement continuation inside recovery flows.
# If the client says "not tomorrow" and then gives a new date, we should not
# re-enter the date-question loop. Keep the fuzzy time window and immediately
# regenerate slots for the new day.
def stage37_temporal_norm(text_: Optional[str]) -> str:
    return _fold_match_text(_normalize_phrase_text(str(text_ or ""))).strip()


def stage37_relative_date_from_text(text_: Optional[str]) -> Optional[datetime]:
    """Centralized relative-date parser for conversational recovery.

    Stage 37 rule: longest Latvian relative words must win first.
    - rīt / rit = +1
    - parīt / parit = +2
    - aizparīt / aizparit = +3
    Also supports Russian/English equivalents used in current Repliq tests.
    """
    raw = str(text_ or "").strip()
    if not raw:
        return None
    low = stage37_temporal_norm(raw)
    base = today_local()

    def at(days: int) -> datetime:
        return datetime.combine(base + timedelta(days=days), datetime.min.time(), tzinfo=TZ).replace(hour=9)

    # Explicit Latvian order: aizparit before parit before rit.
    if re.search(r"\baizparit\b", low):
        return at(3)
    if re.search(r"\bparit\b", low):
        return at(2)

    # Negative-only phrases like "ne rīt" must not resolve back to tomorrow.
    # Combined corrections such as "ne rīt, bet parīt" are handled above by
    # the parit/aizparit checks.
    if any(x in low for x in ["ne rit", "not tomorrow", "ne zavtra", "не завтра"]):
        return None

    # Avoid matching "rita" / "no rita" as plain tomorrow when user means morning.
    if re.search(r"\brit\b", low) or "rīt" in raw.lower():
        return at(1)

    if any(x in low for x in ["poslezavtra", "послезавтра", "day after tomorrow"]):
        return at(2)
    if any(x in low for x in ["zavtra", "завтра", "tomorrow"]):
        return at(1)
    if any(x in low for x in ["sodien", "šodien", "segodnya", "сегодня", "today"]):
        return at(0)

    parsed = parse_date_only_text(raw)
    if parsed:
        return parsed.replace(hour=9, minute=0, second=0, microsecond=0)
    return None


def stage36_recovery_date_from_text(text_: Optional[str]) -> Optional[datetime]:
    # Stage 37 keeps the old function name for compatibility with Stage 36 call sites.
    return stage37_relative_date_from_text(text_)


def stage37_is_negative_date_rejection(text_: Optional[str]) -> bool:
    low = stage37_temporal_norm(text_)
    return any(x in low for x in [
        "ne rit", "ne rīt", "nav rit", "ne sodien", "ne parit", "ne aizparit",
        "не завтра", "не сегодня", "not tomorrow", "not today",
    ])


def stage37_is_short_relative_date_answer(text_: Optional[str]) -> bool:
    low = stage37_temporal_norm(text_)
    if not low:
        return False
    low = re.sub(r"[^a-zа-яё0-9 ]+", " ", low, flags=re.IGNORECASE).strip()
    low = re.sub(r"\s+", " ", low)
    allowed = {
        "rit", "parit", "aizparit", "sodien",
        "rīt", "parīt", "aizparīt", "šodien",
        "zavtra", "poslezavtra", "segodnya",
        "завтра", "послезавтра", "сегодня",
        "tomorrow", "today", "day after tomorrow",
    }
    return low in allowed or low in {"ne rit bet parit", "ne rit bet aizparit"}


def stage37_is_positive_slot_ack(text_: Optional[str], lang: str) -> bool:
    """Stage 37.3: robust positive ack detector for offered slot selection.

    `is_yes_text()` is intentionally strict and only matches exact tokens, so
    natural Latvian answers like `jā, der` or `labi, der` were slipping into
    generic temporal routing and reopening AWAITING_DATE. This helper is used
    only inside the offered-slot guard, so it is safe to be more conversational.
    """
    low = _normalize_phrase_text(text_)
    if not low:
        return False
    if is_yes_text(low, lang):
        return True

    positive_phrases = {
        "lv": {
            "ja", "jaa", "jā", "ja der", "jā der", "jaa der",
            "der", "labi", "labi der", "ok", "okej",
            "apstiprinu", "var", "varam", "šis der", "sis der",
            "jā labi", "ja labi", "jā apstiprinu", "ja apstiprinu",
        },
        "ru": {
            "да", "да подходит", "подходит", "хорошо", "ок",
            "да хорошо", "подтверждаю", "да подтверждаю",
        },
        "en": {
            "yes", "yes works", "works", "fits", "that works",
            "ok", "okay", "sure", "confirm", "yes confirm",
        },
    }
    allowed = set().union(*positive_phrases.values())
    allowed.update(positive_phrases.get(get_lang(lang), set()))
    if low in allowed:
        return True

    # Conservative compound detection: require a clear yes/ok + suitability word.
    lv_yes = {"ja", "jaa", "jā", "labi", "ok", "okej"}
    lv_fit = {"der", "apstiprinu", "var", "varam"}
    parts = set(low.split())
    if get_lang(lang) == "lv" and parts.intersection(lv_yes) and parts.intersection(lv_fit):
        return True
    return False


def stage37_choose_first_offered_slot_from_ack(
    tenant_id: str,
    user_key: str,
    raw_phone: str,
    channel: str,
    msg: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Stage 37.3 guard: in slot-offer state, positive ack selects opt1.

    Without this, short LV confirmations like "jā, der" can be routed as a
    vague continuation and move back to AWAITING_DATE. This guard is safe
    because it only runs when there are offered slots and no confirm slot yet.
    """
    if conversation_state(c) != STATE_AWAITING_TIME:
        return None
    if not stage37_is_positive_slot_ack(msg, lang):
        return None
    offered = get_offered_slots(pending or {})
    if not offered:
        return None
    selected_iso = offered[0]
    dt_selected = parse_dt_any_tz(selected_iso)
    if not dt_selected:
        return None
    pending = pending or {}
    pending["confirm_slot_iso"] = dt_selected.isoformat()
    pending["candidate_datetime_iso"] = dt_selected.isoformat()
    pending["time_text"] = dt_selected.strftime("%H:%M")
    pending["booking_intent"] = True
    c["pending"] = pending
    c["datetime_iso"] = dt_selected.isoformat()
    c["state"] = STATE_AWAITING_CONFIRM
    db_save_conversation(tenant_id, user_key, c)
    reply = t(lang, "ask_booking_confirm", when=format_dt_short(dt_selected), service=pending.get("service_display") or "")
    return {
        "status": "need_more",
        "reply_voice": reply,
        "msg_out": reply,
        "lang": lang,
        "preserve_text": True,
        "stage37_2_slot_ack_guard": True,
    }


def stage37_temporal_recovery_if_needed(
    tenant_id: str,
    user_key: str,
    msg: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Early temporal recovery layer.

    Runs before LLM/entity persistence so short Latvian replies like "parīt" or
    "aizparīt" cannot be swallowed by the generic AWAITING_DATE prompt path.
    """
    raw = str(msg or "").strip()
    if not raw:
        return None
    state = conversation_state(c)
    pending = stage36_recover_time_window_context(stage36_remember_time_window_context(pending or {}))
    active = is_active_booking_flow(c) or state in ACTIVE_BOOKING_STATES or bool(pending.get("booking_intent"))
    if not active:
        return None

    # Stage 37.1: preserve fuzzy window from short temporal answers like
    # "rīt vakarā" before any date-only routing. Without this, the date is
    # understood but slot generation falls back to 09:00/09:30.
    direct_window = parse_time_window(raw)
    if direct_window:
        pending["preferred_time_window"] = [direct_window[0], direct_window[1]]
        pending["last_preferred_time_window"] = [direct_window[0], direct_window[1]]
        pending["stage36_recovery_time_window"] = [direct_window[0], direct_window[1]]
        pending["stage37_temporal_window"] = [direct_window[0], direct_window[1]]
        c["pending"] = pending

    rel_day = stage37_relative_date_from_text(raw)

    # Stage 37.2: any short relative date answer inside an active booking flow
    # with a known service should directly regenerate slots. This covers
    # "rīt vakarā", "parīt" and "aizparīt" after "ne rīt" even if
    # the FSM is still in AWAITING_DATE or carries stage37_waiting_replacement_date.
    if rel_day and (
        state in {STATE_AWAITING_DATE, STATE_AWAITING_TIME, STATE_AWAITING_CONFIRM}
        or pending.get("stage37_waiting_replacement_date")
    ) and str(c.get("service") or pending.get("service") or "").strip():
        if direct_window:
            pending["preferred_time_window"] = [direct_window[0], direct_window[1]]
            pending["last_preferred_time_window"] = [direct_window[0], direct_window[1]]
            pending["stage36_recovery_time_window"] = [direct_window[0], direct_window[1]]
            pending["stage37_temporal_window"] = [direct_window[0], direct_window[1]]
        else:
            pending = stage36_recover_time_window_context(stage36_remember_time_window_context(pending))
        pending["stage37_temporal_engine"] = True
        pending.pop("stage37_waiting_replacement_date", None)
        return stage36_continue_with_new_date_slots(
            tenant_id=tenant_id,
            user_key=user_key,
            lang=lang,
            c=c,
            pending=pending,
            settings=settings,
            service_catalog=service_catalog,
            base_day=rel_day,
        )

    # Phrases like "ne rīt" should not clear fuzzy time context; they should
    # simply ask for the new day while keeping evening/after-work preferences.
    if state in {STATE_AWAITING_TIME, STATE_AWAITING_CONFIRM} and stage37_is_negative_date_rejection(raw) and not rel_day:
        pending = stage36_remember_time_window_context(pending)
        pending.pop("confirm_slot_iso", None)
        pending.pop("candidate_datetime_iso", None)
        pending.pop("requested_datetime_iso", None)
        pending.pop("partial_datetime_iso", None)
        clear_offered_slots(pending)
        pending["booking_intent"] = True
        pending["stage37_waiting_replacement_date"] = True
        c["pending"] = pending
        c["datetime_iso"] = None
        c["time_text"] = None
        c["state"] = STATE_AWAITING_DATE
        db_save_conversation(tenant_id, user_key, c)
        if lang == "ru":
            reply = "Понял. Тогда посмотрим другой день. Какая дата вам удобна?"
        elif lang == "en":
            reply = "Understood. Let’s check another day. Which date works for you?"
        else:
            reply = "Sapratu. Tad paskatāmies citu dienu. Kurš datums jums derētu?"
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    # Combined correction in one message: "ne rīt, bet parīt".
    if state in {STATE_AWAITING_TIME, STATE_AWAITING_CONFIRM, STATE_AWAITING_DATE} and stage37_is_negative_date_rejection(raw) and rel_day:
        pending["stage37_temporal_engine"] = True
        return stage36_continue_with_new_date_slots(
            tenant_id=tenant_id,
            user_key=user_key,
            lang=lang,
            c=c,
            pending=pending,
            settings=settings,
            service_catalog=service_catalog,
            base_day=rel_day,
        )

    return None

def stage36_continue_with_new_date_slots(
    tenant_id: str,
    user_key: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    base_day: datetime,
) -> Dict[str, Any]:
    pending = stage36_recover_time_window_context(stage36_remember_time_window_context(pending or {}))
    pending["awaiting_time_date_iso"] = base_day.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
    pending.pop("confirm_slot_iso", None)
    pending.pop("candidate_datetime_iso", None)
    pending.pop("requested_datetime_iso", None)
    pending.pop("partial_datetime_iso", None)
    clear_offered_slots(pending)
    pending = stage36_recover_time_window_context(pending)
    pending["booking_intent"] = True
    c["datetime_iso"] = None
    c["time_text"] = None
    c["state"] = STATE_AWAITING_TIME
    c["pending"] = pending
    db_save_conversation(tenant_id, user_key, c)
    return offer_slots_for_date(tenant_id, user_key, lang, c, pending, settings, service_catalog, base_day)

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

    folded_low = _fold_match_text(low)
    candidates_index: List[Tuple[int, str, Dict[str, Any]]] = []
    folded_candidates_index: List[Tuple[int, str, Dict[str, Any]]] = []
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
                folded = _fold_match_text(cand)
                if folded:
                    folded_candidates_index.append((len(folded), folded, item))

    for _, cand, item in sorted(candidates_index, key=lambda x: x[0], reverse=True):
        if cand == low or cand in low or low in cand:
            return item

    # Stage 25.6 hotfix: diacritic-insensitive service matching for natural Latvian input.
    for _, cand, item in sorted(folded_candidates_index, key=lambda x: x[0], reverse=True):
        if cand == folded_low or cand in folded_low or folded_low in cand:
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
    original_state = state
    service_key = str(c.get("service") or pending.get("service") or "").strip()
    confirm_iso = str(pending.get("confirm_slot_iso") or "").strip()
    awaiting_time_date_iso = str(pending.get("awaiting_time_date_iso") or "").strip()
    offered_slots = get_offered_slots(pending)
    has_booking_intent = bool(pending.get("booking_intent"))
    booked_dt = str(c.get("datetime_iso") or "").strip()
    upsell_active = bool(pending.get("upsell_offer_active"))

    # Preserve the dedicated post-booking upsell state. The confirm slot stays in
    # pending during this step, so without this guard the normalizer incorrectly
    # downgrades POST_BOOKING_UPSELL back to AWAITING_CONFIRM and the upsell loops.
    if original_state == STATE_POST_BOOKING_UPSELL and (upsell_active or confirm_iso):
        state = STATE_POST_BOOKING_UPSELL
    elif confirm_iso:
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


def should_offer_post_confirm_upsell(service_catalog: List[Dict[str, Any]], primary_service_item: Optional[Dict[str, Any]], pending: Dict[str, Any]) -> bool:
    if not primary_service_item:
        return False
    if service_group_key(primary_service_item) != "haircut":
        return False
    if str((pending or {}).get("addon_service") or "").strip():
        return False
    return bool(find_service_item_by_group(service_catalog, "beard"))


def move_to_post_confirm_upsell(
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    dt_confirm: datetime,
) -> Dict[str, Any]:
    haircut_item = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
    beard_item = find_service_item_by_group(service_catalog, "beard")
    pending["upsell_offer_active"] = True
    c["pending"] = pending
    c["state"] = STATE_POST_BOOKING_UPSELL
    reply_text = build_confirm_upsell_prompt(lang, format_dt_short(dt_confirm), haircut_item, beard_item)
    return {
        "status": "need_more",
        "reply_voice": reply_text,
        "msg_out": reply_text,
        "lang": lang,
        "preserve_text": True,
    }


def finalize_post_confirm_upsell_response(
    lang: str,
    pending: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    dt_confirm: datetime,
    added: bool,
) -> Dict[str, Any]:
    haircut_item = get_service_item_by_key(service_catalog, pending.get("service"))
    beard_item = find_service_item_by_group(service_catalog, "beard")
    reply_text = build_confirm_upsell_resolution(lang, format_dt_short(dt_confirm), added, haircut_item, beard_item)
    return {
        "status": "booked",
        "reply_voice": reply_text,
        "msg_out": reply_text,
        "lang": lang,
        "service": combined_service_display(lang, haircut_item, beard_item if added else None) or service_display_name(haircut_item, lang),
        "when": format_dt_short(dt_confirm),
        "datetime_text": format_dt_short(dt_confirm),
        "preserve_text": True,
    }


def offer_slots_for_date(
    tenant_id: str,
    user_key: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    base_date: datetime,
) -> Dict[str, Any]:
    service_item_for_slots = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
    stored_window = pending_time_window_tuple(pending)
    if not service_item_for_slots:
        c["pending"] = pending or None
        c["state"] = STATE_AWAITING_SERVICE
        db_save_conversation(tenant_id, user_key, c)
        prompt = barber_service_prompt(lang, service_catalog)
        return {"status": "need_more", "reply_voice": prompt, "msg_out": prompt, "lang": lang}

    pending["booking_intent"] = True
    pending["awaiting_time_date_iso"] = base_date.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
    pending.pop("confirm_slot_iso", None)
    pending.pop("candidate_datetime_iso", None)
    pending = stage36_remember_time_window_context(pending)
    clear_offered_slots(pending)
    pending = stage36_recover_time_window_context(pending)
    # Stage 37.1: recompute after recovery/persistence so callers that set
    # preferred_time_window just before this function get windowed slots.
    stored_window = pending_time_window_tuple(pending)
    c["pending"] = pending
    c["datetime_iso"] = None
    c["state"] = STATE_AWAITING_TIME

    if is_closed_day_for_rules(base_date, settings.get("business_rules")):
        c["state"] = STATE_AWAITING_DATE
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "need_more",
            "reply_voice": t(lang, "holiday_closed_voice"),
            "msg_out": t(lang, "holiday_closed_text"),
            "lang": lang,
        }

    calendar_ready = calendar_is_configured(settings["calendar_id"])
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
    if len(day_slots) == 1:
        pending = set_offered_slots(pending, day_slots[:1])
        pending["confirm_slot_iso"] = day_slots[0].isoformat()
        c["pending"] = pending
        c["state"] = STATE_AWAITING_CONFIRM
        c["datetime_iso"] = day_slots[0].isoformat()
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "need_more",
            "reply_voice": t(lang, "ask_booking_confirm", when=format_dt_short(day_slots[0]), service=pending.get("service_display") or ""),
            "msg_out": t(lang, "ask_booking_confirm", when=format_dt_short(day_slots[0]), service=pending.get("service_display") or ""),
            "lang": lang,
        }

    db_save_conversation(tenant_id, user_key, c)
    return {
        "status": "need_more",
        "reply_voice": t(lang, "ask_booking_time_only"),
        "msg_out": t(lang, "ask_booking_time_only"),
        "lang": lang,
    }


def apply_inflow_service_override(
    tenant_id: str,
    user_key: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    new_service_item: Dict[str, Any],
) -> Dict[str, Any]:
    c, pending = remember_booking_service(c, pending, new_service_item, lang)
    pending["booking_intent"] = True
    pending.pop("confirm_slot_iso", None)
    pending.pop("candidate_datetime_iso", None)
    clear_offered_slots(pending)
    base_day = parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or c.get("datetime_iso") or "").strip())
    if base_day:
        return offer_slots_for_date(tenant_id, user_key, lang, c, pending, settings, service_catalog, base_day)
    c["pending"] = pending or None
    c["datetime_iso"] = None
    c["state"] = STATE_AWAITING_DATE
    db_save_conversation(tenant_id, user_key, c)
    return {
        "status": "need_more",
        "reply_voice": t(lang, "ask_booking_date"),
        "msg_out": t(lang, "ask_booking_date"),
        "lang": lang,
    }


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

    # Stage 28: finalization must fully exit the active booking state machine.
    # Leaving pending["booking_intent"] after a successful calendar write makes
    # normalize_booking_state reopen AWAITING_DATE/AWAITING_CONFIRM on the next
    # turn, which causes repeated confirmation loops after the user says "yes".
    was_rescheduled = bool(pending.get("reschedule_event_id"))
    c["pending"] = None
    c["state"] = STATE_BOOKED
    c["name"] = final_name
    c["service"] = final_service_key or str((final_service_item or {}).get("key") or "").strip()
    c["datetime_iso"] = dt_start.isoformat()
    c["time_text"] = None
    return {
        "status": "booked",
        "reply_voice": t(lang, "rescheduled_voice", when=format_dt_short(dt_start)) if was_rescheduled else t(lang, "booking_confirmed"),
        "msg_out": t(lang, "rescheduled_text", service=final_service, when=format_dt_short(dt_start)) if was_rescheduled else t(lang, "booking_confirmed_text", service=final_service, when=format_dt_short(dt_start)),
        "lang": lang,
        "service": final_service,
        "when": format_dt_short(dt_start),
        "datetime_text": format_dt_short(dt_start),
        "calendar_action": "update_event" if was_rescheduled else "create_event",
        "reschedule_finalized": bool(was_rescheduled),
        "preserve_text": bool(was_rescheduled),
    }



# -------------------------
# STAGE 24 — FREE CONVERSATIONAL SLOT ROUTER
# -------------------------
def free_router_is_variants_request(text_: Optional[str], lang: str) -> bool:
    low = _normalize_phrase_text(text_)
    if not low:
        return False
    phrases = [
        "kadi ir varianti", "kādi ir varianti", "kadi varianti", "kādi varianti", "varianti",
        "kadi laiki", "kādi laiki", "kas pieejams", "kas ir pieejams", "brivie laiki", "brīvie laiki",
        "ir kas brivs", "ir kas brīvs", "citi varianti", "kaut kas cits",
        "какие варианты", "какие есть варианты", "что есть", "что свободно", "какое время есть", "есть варианты",
        "what options", "what times", "what is available", "available times", "any options", "anything available", "other options",
    ]
    return any(p in low for p in phrases if p)


def free_router_is_services_request(text_: Optional[str], lang: str) -> bool:
    low = _normalize_phrase_text(text_)
    if not low:
        return False
    phrases = [
        "kadi pakalpojumi", "kādi pakalpojumi", "pakalpojumi", "ko piedavajat", "ko piedāvājat",
        "какие услуги", "услуги", "что делаете", "what services", "services", "service list",
    ]
    return any(p in low for p in phrases if p)


def free_router_is_price_request(text_: Optional[str], lang: str) -> bool:
    low = _normalize_phrase_text(text_)
    if not low:
        return False
    phrases = [
        "cik maksa", "cik maksā", "cik tas maksā", "cik tas maksa", "cik tas maksas", "cena", "cenradis", "cenrādis",
        "сколько стоит", "сколько это стоит", "цена", "стоимость", "прайс", "how much", "how much does it cost", "price", "cost",
    ]
    return any(p in low for p in phrases if p)


def free_router_service_list_text(lang: str, service_catalog: List[Dict[str, Any]], max_items: int = 8) -> str:
    names: List[str] = []
    for item in service_catalog[:max_items]:
        name = service_display_name(item, lang)
        if name and name not in names:
            names.append(name)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if lang == "ru":
        return ", ".join(names[:-1]) + " или " + names[-1]
    if lang == "en":
        return ", ".join(names[:-1]) + " or " + names[-1]
    return ", ".join(names[:-1]) + " vai " + names[-1]


def free_router_context_datetime(c: Dict[str, Any], pending: Dict[str, Any]) -> Optional[datetime]:
    pending = pending or {}
    c = c or {}
    for value in [
        pending.get("candidate_datetime_iso"),
        pending.get("requested_datetime_iso"),
        pending.get("partial_datetime_iso"),
        pending.get("confirm_slot_iso"),
        pending.get("datetime_iso"),
        c.get("datetime_iso"),
    ]:
        dtv = parse_dt_any_tz(str(value or "").strip())
        if dtv and (dtv.hour != 9 or dtv.minute != 0):
            return dtv
    base_day = parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip())
    time_value = pending.get("requested_time") or pending.get("partial_time") or pending.get("time_text") or c.get("time_text")
    parts = parse_explicit_time_parts(str(time_value or ""))
    if base_day and parts:
        hh, mm = parts
        return base_day.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return None


def free_router_merge_message_slots(msg: str, c: Dict[str, Any], pending: Dict[str, Any], service_catalog: List[Dict[str, Any]], service_aliases: Dict[str, str], lang: str) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]], Optional[datetime]]:
    pending = pending or {}
    service_key = canonical_service_key_from_text(msg, service_aliases)
    service_item = get_service_item_by_key(service_catalog, service_key) if service_key else extract_service_from_text(msg, service_catalog, lang)
    if service_item:
        c, pending = remember_booking_service(c, pending, service_item, lang)
    if msg and (parse_natural_datetime(msg) or parse_date_only_text(msg) or parse_time_window(msg) or has_explicit_time(msg)):
        c, pending = remember_partial_booking_datetime_from_message(c, pending, msg)
    candidate_dt = free_router_context_datetime(c, pending)
    c["pending"] = pending or None
    return c, pending, service_item, candidate_dt


def free_router_missing_fields(c: Dict[str, Any], pending: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    if not str((c or {}).get("service") or (pending or {}).get("service") or "").strip():
        missing.append("service")
    if not free_router_context_datetime(c or {}, pending or {}):
        missing.append("datetime")
    return missing


def free_router_variants_reply_without_service(lang: str, service_catalog: List[Dict[str, Any]], pending: Dict[str, Any]) -> str:
    options = free_router_service_list_text(lang, service_catalog)
    dtv = free_router_context_datetime({}, pending or {})
    when = format_dt_short(dtv) if dtv else ""
    if lang == "ru":
        return f"Сначала выберем услугу, и тогда проверю варианты на {when}. Доступные услуги: {options}." if when else f"Сначала выберем услугу, и тогда проверю свободные варианты. Доступные услуги: {options}."
    if lang == "en":
        return f"Let’s choose the service first, then I’ll check the available options for {when}. Available services: {options}." if when else f"Let’s choose the service first, then I’ll check available options. Available services: {options}."
    return f"Vispirms izvēlamies pakalpojumu, un tad pārbaudīšu variantus uz {when}. Pieejamie pakalpojumi: {options}." if when else f"Vispirms izvēlamies pakalpojumu, un tad pārbaudīšu brīvos laikus. Pieejamie pakalpojumi: {options}."


def free_router_services_reply(lang: str, service_catalog: List[Dict[str, Any]], pending: Dict[str, Any]) -> str:
    options = free_router_service_list_text(lang, service_catalog)
    dtv = free_router_context_datetime({}, pending or {})
    when = format_dt_short(dtv) if dtv else ""
    if lang == "ru":
        return f"Доступные услуги: {options}. После выбора услуги проверю время {when}." if when else f"Доступные услуги: {options}. Какую услугу хотите выбрать?"
    if lang == "en":
        return f"Available services: {options}. Once you choose the service, I’ll check {when}." if when else f"Available services: {options}. Which one would you like?"
    return f"Pieejamie pakalpojumi: {options}. Kad izvēlēsieties pakalpojumu, pārbaudīšu {when}." if when else f"Pieejamie pakalpojumi: {options}. Kuru pakalpojumu vēlaties?"


def free_router_ask_missing_service(lang: str, pending: Dict[str, Any], service_catalog: List[Dict[str, Any]]) -> str:
    dtv = free_router_context_datetime({}, pending or {})
    when = format_dt_short(dtv) if dtv else ""
    if lang == "ru":
        return f"Хорошо, на {when}. Какую услугу записываем?" if when else "Хорошо. Какую услугу записываем?"
    if lang == "en":
        return f"Sure, for {when}. Which service should I book?" if when else "Sure. Which service should I book?"
    return f"Labi, uz {when}. Kuru pakalpojumu pierakstām?" if when else "Labi. Kuru pakalpojumu pierakstām?"


def free_router_ask_missing_datetime(lang: str, c: Dict[str, Any], pending: Dict[str, Any]) -> str:
    service_name = str((pending or {}).get("service_display") or (c or {}).get("service") or "").strip()
    if lang == "ru":
        return f"Хорошо, {service_name}. На какой день и время вас записать?" if service_name else "На какой день и время вас записать?"
    if lang == "en":
        return f"Okay, {service_name}. What day and time would work for you?" if service_name else "What day and time would work for you?"
    return f"Labi, {service_name}. Uz kuru dienu un laiku vēlaties pierakstīties?" if service_name else "Uz kuru dienu un laiku vēlaties pierakstīties?"

# -------------------------
# STAGE 29 — AFTER-TIME WINDOW ROUTER HOTFIX
# -------------------------
def detect_after_time_anchor(text_: Optional[str], lang: str = "") -> Optional[Tuple[int, int]]:
    """Detect phrases meaning strictly after a time, not exactly at that time.

    Examples:
    - "после 14:00" / "после 14"
    - "pēc 14:00" / "pec 14"
    - "after 14:00" / "after 2 pm"
    """
    src = str(text_ or "").strip().lower()
    if not src:
        return None
    folded = _fold_match_text(src)
    patterns = [
        r"\bпосле\s+([01]?\d|2[0-3])(?:[:\.](\d{2}))?\b",
        r"\bпозже\s+([01]?\d|2[0-3])(?:[:\.](\d{2}))?\b",
        r"\bpec\s+([01]?\d|2[0-3])(?:[:\.](\d{2}))?\b",
        r"\bpeec\s+([01]?\d|2[0-3])(?:[:\.](\d{2}))?\b",
        r"\bafter\s+([01]?\d|2[0-3])(?:[:\.](\d{2}))?\b",
        r"\blater\s+than\s+([01]?\d|2[0-3])(?:[:\.](\d{2}))?\b",
    ]
    for pat in patterns:
        m = re.search(pat, folded, flags=re.IGNORECASE)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2) or 0)
            return hh, mm
    return None


def after_time_window_reply(lang: str, anchor_dt: datetime, slots: List[datetime]) -> str:
    offered = [format_dt_short(x) for x in slots[:3]]
    joined_ru = " или ".join(offered)
    joined_en = " or ".join(offered)
    joined_lv = " vai ".join(offered)
    after_text = anchor_dt.strftime("%H:%M")
    if lang == "ru":
        return f"После {after_text} могу предложить: {joined_ru}. Какое время вам удобнее?"
    if lang == "en":
        return f"After {after_text}, I can offer: {joined_en}. Which time works best?"
    return f"Pēc {after_text} varu piedāvāt: {joined_lv}. Kurš laiks jums der?"


def no_after_time_slots_reply(lang: str, anchor_dt: datetime) -> str:
    after_text = anchor_dt.strftime("%H:%M")
    if lang == "ru":
        return f"После {after_text} на этот день свободных вариантов не вижу. Могу посмотреть другой день или более раннее время."
    if lang == "en":
        return f"I don’t see available times after {after_text} on that day. I can check another day or an earlier time."
    return f"Pēc {after_text} šajā dienā brīvus laikus neredzu. Varu paskatīties citu dienu vai agrāku laiku."


def offer_slots_after_time_anchor(
    tenant_id: str,
    user_key: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    base_date: datetime,
    anchor_parts: Tuple[int, int],
) -> Dict[str, Any]:
    pending = pending or {}
    service_item_for_slots = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
    if not service_item_for_slots:
        c["pending"] = pending or None
        c["state"] = STATE_AWAITING_SERVICE
        db_save_conversation(tenant_id, user_key, c)
        prompt = barber_service_prompt(lang, service_catalog)
        return {"status": "need_more", "reply_voice": prompt, "msg_out": prompt, "lang": lang, "preserve_text": True}

    if not calendar_is_configured(settings["calendar_id"]):
        return blocked_result_for_lang(lang)

    hh, mm = anchor_parts
    anchor_dt = base_date.replace(hour=hh, minute=mm, second=0, microsecond=0)
    pending["booking_intent"] = True
    pending["awaiting_time_date_iso"] = base_date.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
    pending["preferred_time_window"] = [hh, 21]
    pending.pop("candidate_datetime_iso", None)
    pending.pop("confirm_slot_iso", None)
    clear_offered_slots(pending)

    all_slots = find_first_n_slots_for_day(
        calendar_id=settings["calendar_id"],
        day_dt=base_date,
        duration_min=service_duration_min(service_item_for_slots),
        work_start=settings["work_start"],
        work_end=settings["work_end"],
        limit=32,
        business_rules=settings.get("business_rules"),
        service_account_json=settings.get("service_account_json"),
    )
    filtered = [s for s in all_slots if s > anchor_dt]

    if filtered:
        pending = set_offered_slots(pending, filtered[:3])
        c["pending"] = pending
        c["state"] = STATE_AWAITING_TIME
        c["datetime_iso"] = None
        c["time_text"] = None
        db_save_conversation(tenant_id, user_key, c)
        reply = after_time_window_reply(lang, anchor_dt, filtered[:3])
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    c["pending"] = pending
    c["state"] = STATE_AWAITING_TIME
    c["datetime_iso"] = None
    c["time_text"] = None
    db_save_conversation(tenant_id, user_key, c)
    reply = no_after_time_slots_reply(lang, anchor_dt)
    return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}




# -------------------------
# STAGE 30 — CONVERSATIONAL NEGOTIATION ENGINE HOTFIX
# -------------------------
def stage30_offer_after_time_window_if_needed(
    tenant_id: str,
    user_key: str,
    msg: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    service_aliases: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    """Route phrases like "после 14:00" / "pēc 14:00" as a window.

    Safety contract:
    - never creates a booking directly;
    - never treats the anchor as an exact confirmation candidate;
    - only offers available slots strictly after the anchor.
    """
    anchor = detect_after_time_anchor(msg, lang)
    if not anchor:
        return None

    pending = pending or {}
    service_key = str(c.get("service") or pending.get("service") or "").strip()
    if not service_key:
        service_item = stage27_extract_service_item_from_turn(msg, {}, service_catalog, service_aliases, lang)
        if service_item:
            c, pending = remember_booking_service(c, pending, service_item, lang)
            service_key = str(c.get("service") or pending.get("service") or "").strip()

    # Persist the date part, but deliberately remove exact 14:00 candidate data.
    date_dt = parse_date_only_text(msg)
    if date_dt:
        pending["awaiting_time_date_iso"] = date_dt.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()

    base_day = parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip()) or date_dt
    if not service_key:
        pending["booking_intent"] = True
        pending.pop("candidate_datetime_iso", None)
        pending.pop("confirm_slot_iso", None)
        pending.pop("time_text", None)
        clear_offered_slots(pending)
        c["pending"] = pending
        c["datetime_iso"] = None
        c["time_text"] = None
        c["state"] = STATE_AWAITING_SERVICE
        db_save_conversation(tenant_id, user_key, c)
        prompt = barber_service_prompt(lang, service_catalog)
        return {"status": "need_more", "reply_voice": prompt, "msg_out": prompt, "lang": lang, "preserve_text": True}

    if not base_day:
        pending["booking_intent"] = True
        pending.pop("candidate_datetime_iso", None)
        pending.pop("confirm_slot_iso", None)
        pending.pop("time_text", None)
        clear_offered_slots(pending)
        c["pending"] = pending
        c["datetime_iso"] = None
        c["time_text"] = None
        c["state"] = STATE_AWAITING_DATE
        db_save_conversation(tenant_id, user_key, c)
        return {"status": "need_more", "reply_voice": t(lang, "ask_booking_date"), "msg_out": t(lang, "ask_booking_date"), "lang": lang}

    pending.pop("candidate_datetime_iso", None)
    pending.pop("requested_datetime_iso", None)
    pending.pop("partial_datetime_iso", None)
    pending.pop("confirm_slot_iso", None)
    pending.pop("time_text", None)
    clear_offered_slots(pending)
    c["datetime_iso"] = None
    c["time_text"] = None
    c["pending"] = pending
    c["state"] = STATE_AWAITING_TIME
    return offer_slots_after_time_anchor(
        tenant_id=tenant_id,
        user_key=user_key,
        lang=lang,
        c=c,
        pending=pending,
        settings=settings,
        service_catalog=service_catalog,
        base_date=base_day,
        anchor_parts=anchor,
    )


def stage30_negotiate_from_confirm_if_needed(
    tenant_id: str,
    user_key: str,
    msg: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Handle "можно позже?" / "var vēlāk?" directly in confirm state."""
    if conversation_state(c) != STATE_AWAITING_CONFIRM:
        return None
    direction = detect_time_shift_direction(msg, lang)
    if not direction:
        return None

    pending = pending or {}
    anchor_iso = str(pending.get("confirm_slot_iso") or c.get("datetime_iso") or "").strip()
    anchor_dt = parse_dt_any_tz(anchor_iso)
    service_item = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
    if not anchor_dt or not service_item or not calendar_is_configured(settings["calendar_id"]):
        return None

    slots = find_negotiation_slots_for_direction(
        calendar_id=settings["calendar_id"],
        base_day=anchor_dt,
        anchor_dt=anchor_dt,
        direction=direction,
        duration_min=service_duration_min(service_item),
        work_start=settings["work_start"],
        work_end=settings["work_end"],
        limit=3,
        business_rules=settings.get("business_rules"),
        service_account_json=settings.get("service_account_json"),
    )
    pending.pop("confirm_slot_iso", None)
    pending.pop("candidate_datetime_iso", None)
    pending.pop("time_text", None)
    clear_offered_slots(pending)
    pending["booking_intent"] = True
    pending["awaiting_time_date_iso"] = anchor_dt.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
    c["datetime_iso"] = None
    c["time_text"] = None
    c["state"] = STATE_AWAITING_TIME
    c["pending"] = pending
    return negotiation_slots_response(tenant_id, user_key, lang, c, pending, slots)


# -------------------------
# STAGE 31 — HUMAN SCHEDULING INTELLIGENCE HOTFIX
# -------------------------
def stage31_detect_time_window_preference(text_: Optional[str], lang: str = "") -> Optional[Tuple[int, int, str]]:
    """Detect fuzzy scheduling windows that must not become exact timestamps.

    Examples:
    - "завтра вечером" / "rīt vakarā" / "tomorrow evening" -> evening window
    - "после обеда" / "pēcpusdienā" / "after lunch" -> afternoon window
    - "утром" / "no rīta" / "morning" -> morning window
    Exact phrases like "в 14:00" are intentionally left to the exact-time flow.
    "после 14:00" is handled by Stage 30 before this layer.
    """
    src = str(text_ or "").strip().lower()
    if not src:
        return None
    if detect_after_time_anchor(src, lang):
        return None

    folded = _fold_match_text(src)
    patterns: List[Tuple[str, Tuple[int, int], str]] = [
        (r"\b(no rita|rita|sorit|morning|in the morning|this morning|утром|с утра|на утро)\b", (9, 12), "morning"),
        (r"\b(pusdienlaika|ap pusdienlaiku|no pusdienam|pecpusdiena|after lunch|afternoon|in the afternoon|после обеда|днем|днем|днём|на день)\b", (12, 17), "afternoon"),
        (r"\b(vakara|vakar|sovakar|vakarpuse|uz vakaru|evening|tonight|in the evening|this evening|вечером|на вечер|к вечеру|ближе к вечеру)\b", (16, 21), "evening"),
        (r"\b(pec darba|after work|после работы)\b", (17, 21), "after_work"),
    ]
    for pat, window, label in patterns:
        if re.search(pat, folded, flags=re.IGNORECASE):
            return window[0], window[1], label

    parsed = parse_time_window(src)
    if parsed:
        start_h, end_h = parsed
        bucket = detect_time_bucket(src) or "window"
        return start_h, end_h, bucket
    return None


def stage31_window_label(lang: str, label: str, start_h: int, end_h: int) -> str:
    lang = get_lang(lang)
    if label == "morning":
        return "утром" if lang == "ru" else "in the morning" if lang == "en" else "no rīta"
    if label == "afternoon":
        return "после обеда" if lang == "ru" else "in the afternoon" if lang == "en" else "pēcpusdienā"
    if label == "evening":
        return "вечером" if lang == "ru" else "in the evening" if lang == "en" else "vakarā"
    if label == "after_work":
        return "после работы" if lang == "ru" else "after work" if lang == "en" else "pēc darba"
    if lang == "ru":
        return f"с {start_h:02d}:00 до {end_h:02d}:00"
    if lang == "en":
        return f"between {start_h:02d}:00 and {end_h:02d}:00"
    return f"no {start_h:02d}:00 līdz {end_h:02d}:00"


def stage31_window_slots_reply(lang: str, label_text: str, slots: List[datetime]) -> str:
    offered = [format_dt_short(x) for x in slots[:4]]
    if lang == "ru":
        return f"На {label_text} могу предложить: " + " или ".join(offered) + ". Какое время вам удобнее?"
    if lang == "en":
        return f"For {label_text}, I can offer: " + " or ".join(offered) + ". Which time works best?"
    return f"Uz {label_text} varu piedāvāt: " + " vai ".join(offered) + ". Kurš laiks jums der?"


def stage31_no_window_slots_reply(lang: str, label_text: str, fallback_slots: List[datetime]) -> str:
    if fallback_slots:
        offered = [format_dt_short(x) for x in fallback_slots[:3]]
        if lang == "ru":
            return f"На {label_text} свободных вариантов не вижу. Ближайшие свободные времена: " + " или ".join(offered) + ". Подойдёт что-то из этого?"
        if lang == "en":
            return f"I don’t see free times for {label_text}. The nearest available options are: " + " or ".join(offered) + ". Would any of these work?"
        return f"Uz {label_text} brīvus laikus neredzu. Tuvākie pieejamie laiki: " + " vai ".join(offered) + ". Vai kāds no tiem der?"
    if lang == "ru":
        return f"На {label_text} свободных вариантов не вижу. Могу посмотреть другой день или другое время."
    if lang == "en":
        return f"I don’t see free times for {label_text}. I can check another day or a different time."
    return f"Uz {label_text} brīvus laikus neredzu. Varu paskatīties citu dienu vai citu laiku."


def offer_slots_for_time_window(
    tenant_id: str,
    user_key: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    base_date: datetime,
    window_start_hour: int,
    window_end_hour: int,
    window_label: str,
) -> Dict[str, Any]:
    pending = pending or {}
    service_item_for_slots = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
    if not service_item_for_slots:
        c["pending"] = pending or None
        c["state"] = STATE_AWAITING_SERVICE
        db_save_conversation(tenant_id, user_key, c)
        prompt = barber_service_prompt(lang, service_catalog)
        return {"status": "need_more", "reply_voice": prompt, "msg_out": prompt, "lang": lang, "preserve_text": True}

    if not calendar_is_configured(settings["calendar_id"]):
        return blocked_result_for_lang(lang)

    pending["booking_intent"] = True
    pending["awaiting_time_date_iso"] = base_date.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
    pending["preferred_time_window"] = [int(window_start_hour), int(window_end_hour)]
    pending.pop("candidate_datetime_iso", None)
    pending.pop("requested_datetime_iso", None)
    pending.pop("partial_datetime_iso", None)
    pending.pop("confirm_slot_iso", None)
    pending.pop("time_text", None)
    clear_offered_slots(pending)

    all_slots = find_first_n_slots_for_day(
        calendar_id=settings["calendar_id"],
        day_dt=base_date,
        duration_min=service_duration_min(service_item_for_slots),
        work_start=settings["work_start"],
        work_end=settings["work_end"],
        limit=40,
        business_rules=settings.get("business_rules"),
        service_account_json=settings.get("service_account_json"),
    )
    filtered = [s for s in all_slots if int(window_start_hour) <= s.hour < int(window_end_hour)]
    label_text = stage31_window_label(lang, window_label, int(window_start_hour), int(window_end_hour))

    c["datetime_iso"] = None
    c["time_text"] = None
    c["state"] = STATE_AWAITING_TIME
    c["pending"] = pending

    if filtered:
        pending = set_offered_slots(pending, filtered[:4])
        c["pending"] = pending
        db_save_conversation(tenant_id, user_key, c)
        reply = stage31_window_slots_reply(lang, label_text, filtered[:4])
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    fallback = all_slots[:3]
    if fallback:
        pending = set_offered_slots(pending, fallback[:3])
    c["pending"] = pending
    db_save_conversation(tenant_id, user_key, c)
    reply = stage31_no_window_slots_reply(lang, label_text, fallback[:3])
    return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}


def stage31_offer_time_window_if_needed(
    tenant_id: str,
    user_key: str,
    msg: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    service_aliases: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    window = stage31_detect_time_window_preference(msg, lang)
    if not window:
        return None
    start_h, end_h, label = window
    pending = pending or {}

    service_key = str(c.get("service") or pending.get("service") or "").strip()
    if not service_key:
        service_item = stage27_extract_service_item_from_turn(msg, {}, service_catalog, service_aliases, lang)
        if service_item:
            c, pending = remember_booking_service(c, pending, service_item, lang)
            service_key = str(c.get("service") or pending.get("service") or "").strip()

    date_dt = parse_date_only_text(msg)
    if date_dt:
        pending["awaiting_time_date_iso"] = date_dt.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()

    # In confirmation, "можно утром/вечером?" means negotiate another window
    # on the same day as the currently proposed slot.
    if conversation_state(c) == STATE_AWAITING_CONFIRM and not date_dt:
        confirm_dt = parse_dt_any_tz(str(pending.get("confirm_slot_iso") or c.get("datetime_iso") or "").strip())
        if confirm_dt:
            date_dt = confirm_dt.replace(hour=9, minute=0, second=0, microsecond=0)
            pending["awaiting_time_date_iso"] = date_dt.isoformat()

    base_day = parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip()) or date_dt

    pending["booking_intent"] = True
    pending.pop("candidate_datetime_iso", None)
    pending.pop("confirm_slot_iso", None)
    pending.pop("time_text", None)
    clear_offered_slots(pending)
    c["datetime_iso"] = None
    c["time_text"] = None
    c["pending"] = pending

    if not service_key:
        c["state"] = STATE_AWAITING_SERVICE
        db_save_conversation(tenant_id, user_key, c)
        prompt = barber_service_prompt(lang, service_catalog)
        return {"status": "need_more", "reply_voice": prompt, "msg_out": prompt, "lang": lang, "preserve_text": True}

    if not base_day:
        c["state"] = STATE_AWAITING_DATE
        db_save_conversation(tenant_id, user_key, c)
        return {"status": "need_more", "reply_voice": t(lang, "ask_booking_date"), "msg_out": t(lang, "ask_booking_date"), "lang": lang, "preserve_text": True}

    return offer_slots_for_time_window(
        tenant_id=tenant_id,
        user_key=user_key,
        lang=lang,
        c=c,
        pending=pending,
        settings=settings,
        service_catalog=service_catalog,
        base_date=base_day,
        window_start_hour=start_h,
        window_end_hour=end_h,
        window_label=label,
    )



# -------------------------
# STAGE 32 — CONVERSATIONAL CONTEXT PERSISTENCE HOTFIX
# -------------------------
def stage32_detect_slot_refinement(text_: Optional[str], lang: str = "") -> Optional[str]:
    """Detect contextual slot refinement, not a new booking request.

    Returns:
    - "earlier" for: not so late / слишком поздно / ne tik vēlu
    - "later" for: not so early / слишком рано / ne tik agri
    This is intentionally deterministic and only influences offered-slot negotiation.
    """
    low = _normalize_phrase_text(text_)
    folded = _fold_match_text(text_)
    if not low and not folded:
        return None

    earlier_phrases = [
        "не так поздно", "слишком поздно", "очень поздно", "не позднее", "раньше", "пораньше", "чуть раньше", "немного раньше",
        "ne tik velu", "par velu", "mazliet agrak", "nedaudz agrak", "agrak", "atrak",
        "not so late", "too late", "a bit earlier", "slightly earlier", "earlier",
    ]
    later_phrases = [
        "не так рано", "слишком рано", "очень рано", "не раньше", "позже", "попозже", "чуть позже", "немного позже",
        "ne tik agri", "par agru", "mazliet velak", "nedaudz velak", "velak",
        "not so early", "too early", "a bit later", "slightly later", "later",
    ]

    for phrase in earlier_phrases:
        if phrase in low or phrase in folded:
            return "earlier"
    for phrase in later_phrases:
        if phrase in low or phrase in folded:
            return "later"
    return None


def stage32_remember_rejected_slots(pending: Dict[str, Any], slots: List[str]) -> Dict[str, Any]:
    pending = pending or {}
    existing = pending.get("rejected_slot_isos")
    rejected: List[str] = []
    if isinstance(existing, list):
        rejected = [str(x).strip() for x in existing if str(x).strip()]
    for iso in slots or []:
        iso_s = str(iso or "").strip()
        if iso_s and iso_s not in rejected:
            rejected.append(iso_s)
    pending["rejected_slot_isos"] = rejected[-20:]
    return pending


def stage32_refinement_reply(lang: str, direction: str, slots: List[datetime]) -> str:
    offered = [format_dt_short(x) for x in slots[:4]]
    if lang == "ru":
        prefix = "Понял, посмотрим пораньше" if direction == "earlier" else "Понял, посмотрим попозже"
        return prefix + ": " + " или ".join(offered) + ". Что вам удобнее?"
    if lang == "en":
        prefix = "Got it — here are earlier options" if direction == "earlier" else "Got it — here are later options"
        return prefix + ": " + " or ".join(offered) + ". Which one works best?"
    prefix = "Sapratu, paskatīsimies agrāk" if direction == "earlier" else "Sapratu, paskatīsimies vēlāk"
    return prefix + ": " + " vai ".join(offered) + ". Kurš laiks jums der?"


def stage32_no_refinement_slots_reply(lang: str, direction: str) -> str:
    if lang == "ru":
        return "Подходящих вариантов в эту сторону не вижу. Могу посмотреть другой день или другое время."
    if lang == "en":
        return "I don’t see suitable options in that direction. I can check another day or another time."
    return "Šajā virzienā piemērotus laikus neredzu. Varu paskatīties citu dienu vai citu laiku."


def stage32_refine_offered_slots_if_needed(
    tenant_id: str,
    user_key: str,
    msg: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Refine currently offered/confirmed slots using short-term memory.

    Examples:
    - Bot offers 16:30 / 17:00 / 17:30, user says "не так поздно" -> offer earlier slots.
    - Bot offers 09:00 / 09:30, user says "не так рано" -> offer later slots.
    - Avoid repeating the same rejected slots.
    """
    state = conversation_state(c or {})
    if state not in {STATE_AWAITING_TIME, STATE_AWAITING_CONFIRM}:
        return None

    direction = stage32_detect_slot_refinement(msg, lang)
    if not direction:
        return None

    pending = pending or {}
    service_item = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
    if not service_item or not calendar_is_configured(settings["calendar_id"]):
        return None

    offered_isos = get_offered_slots(pending)
    confirm_iso = str(pending.get("confirm_slot_iso") or c.get("datetime_iso") or "").strip()
    context_isos = offered_isos[:]
    if confirm_iso:
        context_isos.append(confirm_iso)

    context_dts = [dt for dt in (parse_dt_any_tz(x) for x in context_isos) if dt]
    if not context_dts:
        return None

    context_dts = sorted(context_dts)
    base_day = parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip())
    if not base_day:
        base_day = context_dts[0].replace(hour=9, minute=0, second=0, microsecond=0)

    anchor_dt = context_dts[0] if direction == "earlier" else context_dts[-1]
    pending = stage32_remember_rejected_slots(pending, [dt.isoformat() for dt in context_dts])
    rejected = set(str(x).strip() for x in (pending.get("rejected_slot_isos") or []) if str(x).strip())

    all_slots = find_first_n_slots_for_day(
        calendar_id=settings["calendar_id"],
        day_dt=base_day,
        duration_min=service_duration_min(service_item),
        work_start=settings["work_start"],
        work_end=settings["work_end"],
        limit=48,
        business_rules=settings.get("business_rules"),
        service_account_json=settings.get("service_account_json"),
    )

    win = pending_time_window_tuple(pending)
    candidates: List[datetime] = []
    if direction == "earlier":
        candidates = [s for s in all_slots if s < anchor_dt]
        if win:
            start_h, _end_h = win
            in_window = [s for s in candidates if int(start_h) <= s.hour]
            candidates = in_window or candidates
        candidates = candidates[-4:]
    else:
        candidates = [s for s in all_slots if s > anchor_dt]
        if win:
            _start_h, end_h = win
            in_window = [s for s in candidates if s.hour < int(end_h)]
            candidates = in_window or candidates
        candidates = candidates[:4]

    candidates = [s for s in candidates if s.isoformat() not in rejected]

    pending.pop("confirm_slot_iso", None)
    pending.pop("candidate_datetime_iso", None)
    pending.pop("requested_datetime_iso", None)
    pending.pop("partial_datetime_iso", None)
    pending.pop("time_text", None)
    pending["booking_intent"] = True
    pending["awaiting_time_date_iso"] = base_day.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
    c["datetime_iso"] = None
    c["time_text"] = None
    c["state"] = STATE_AWAITING_TIME

    if candidates:
        pending = set_offered_slots(pending, candidates[:4])
        c["pending"] = pending
        db_save_conversation(tenant_id, user_key, c)
        reply = stage32_refinement_reply(lang, direction, candidates[:4])
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    clear_offered_slots(pending)
    c["pending"] = pending
    db_save_conversation(tenant_id, user_key, c)
    reply = stage32_no_refinement_slots_reply(lang, direction)
    return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}


def free_router_handle_candidate_datetime(
    tenant_id: str,
    user_key: str,
    raw_phone: str,
    channel: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    candidate_dt: datetime,
) -> Dict[str, Any]:
    pending = pending or {}
    service_item = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
    duration_min = service_duration_min(service_item)
    if not calendar_is_configured(settings["calendar_id"]):
        return blocked_result_for_lang(lang)

    pending["booking_intent"] = True
    pending["awaiting_time_date_iso"] = candidate_dt.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
    pending["time_text"] = candidate_dt.strftime("%H:%M")
    c["time_text"] = pending["time_text"]
    c["pending"] = pending

    slot_ok = (
        in_business_hours(candidate_dt, duration_min, settings["work_start"], settings["work_end"], settings.get("business_rules"))
        and not is_slot_busy(
            settings["calendar_id"],
            candidate_dt,
            candidate_dt + timedelta(minutes=duration_min),
            _safe_int((settings.get("business_rules") or {}).get("buffer_minutes"), 0),
            service_account_json=settings.get("service_account_json"),
        )
    )
    if slot_ok:
        result = book_appointment_for_datetime(tenant_id, raw_phone, channel, lang, c, settings, service_catalog, candidate_dt)
        db_save_conversation(tenant_id, user_key, c)
        return result

    alternatives: List[datetime] = []
    if in_business_hours(candidate_dt, duration_min, settings["work_start"], settings["work_end"], settings.get("business_rules")):
        alternatives = find_first_n_slots_for_day(
            calendar_id=settings["calendar_id"],
            day_dt=candidate_dt,
            duration_min=duration_min,
            work_start=settings["work_start"],
            work_end=settings["work_end"],
            limit=4,
            business_rules=settings.get("business_rules"),
            service_account_json=settings.get("service_account_json"),
        )
        alternatives = [s for s in alternatives if abs((s - candidate_dt).total_seconds()) >= 60]
    if not alternatives:
        opts = find_next_two_slots(settings["calendar_id"], candidate_dt, duration_min, settings["work_start"], settings["work_end"], settings.get("business_rules"), settings.get("service_account_json"))
        if opts:
            alternatives = [opts[0], opts[1]]

    if alternatives:
        pending.pop("candidate_datetime_iso", None)
        pending.pop("confirm_slot_iso", None)
        pending = set_offered_slots(pending, alternatives[:3])
        c["pending"] = pending
        c["state"] = STATE_AWAITING_TIME
        c["datetime_iso"] = None
        db_save_conversation(tenant_id, user_key, c)
        offered = [format_dt_short(x) for x in alternatives[:3]]
        if lang == "ru":
            reply = f"На {format_dt_short(candidate_dt)} уже занято. Могу предложить: " + " или ".join(offered) + ". Что вам удобнее?"
        elif lang == "en":
            reply = f"{format_dt_short(candidate_dt)} is already taken. I can offer: " + " or ".join(offered) + ". Which works best?"
        else:
            reply = f"Diemžēl {format_dt_short(candidate_dt)} jau ir aizņemts. Varu piedāvāt: " + " vai ".join(offered) + ". Kurš laiks jums der?"
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    c["state"] = STATE_AWAITING_TIME
    c["pending"] = pending
    c["datetime_iso"] = None
    db_save_conversation(tenant_id, user_key, c)
    if lang == "ru":
        reply = f"На {format_dt_short(candidate_dt)} уже занято. Какое другое время вам было бы удобно?"
    elif lang == "en":
        reply = f"{format_dt_short(candidate_dt)} is already taken. What other time would work for you?"
    else:
        reply = f"Diemžēl {format_dt_short(candidate_dt)} jau ir aizņemts. Kāds cits laiks jums būtu ērts?"
    return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}



# -------------------------
# STAGE 36 — ADVANCED CONVERSATION RECOVERY
# -------------------------
def stage36_recovery_enabled(channel: str = "", source: str = "runtime") -> bool:
    flag = os.getenv("STAGE36_RECOVERY_ENABLED", "").strip().lower()
    if flag in {"0", "false", "no", "off", "disabled"}:
        return False
    return True


def _stage36_low(text_: Optional[str]) -> str:
    return _fold_match_text(_normalize_phrase_text(text_ or ""))


def stage36_is_hold_text(text_: Optional[str], lang: str) -> bool:
    low = _stage36_low(text_)
    if not low:
        return False
    phrases = {
        "podожди", "podozhdi", "подожди", "секунду", "минуту", "пауза", "погоди",
        "wait", "one moment", "hold on", "just a moment",
        "pagaidi", "uzgaidi", "vienu bridi", "vienu brīdi", "mazliet pagaidi",
    }
    return any(p in low for p in phrases)


def stage36_is_uncertain_text(text_: Optional[str], lang: str) -> bool:
    low = _stage36_low(text_)
    if not low:
        return False
    exact = {
        "nezinu", "ne zinu", "nav ne jausmas", "gruti pateikt", "grūti pateikt",
        "не знаю", "не уверен", "не уверена", "сложно сказать", "пока не знаю",
        "i dont know", "i don't know", "not sure", "hard to say",
    }
    return low in exact or any(p in low for p in exact)


def stage36_is_available_request(text_: Optional[str], lang: str) -> bool:
    low = _stage36_low(text_)
    if not low:
        return False
    phrases = {
        "kas ir pieejams", "kas pieejams", "kas brivs", "kas brīvs", "ko var piedavat", "ko var piedāvāt",
        "что есть", "какие есть", "что свободно", "что доступно", "предложи", "варианты", "какие варианты",
        "what is available", "what's available", "what options", "show options", "any options",
    }
    return any(p in low for p in phrases)


def stage36_is_different_time_text(text_: Optional[str], lang: str) -> bool:
    low = _stage36_low(text_)
    if not low:
        return False
    phrases = {
        "другое время", "другой вариант", "не это время", "не подходит", "не удобно", "неудобно",
        "citu laiku", "cits laiks", "ne sis laiks", "ne šis laiks", "neder", "nav erti", "nav ērti",
        "another time", "different time", "not this time", "doesnt work", "doesn't work",
    }
    return any(p in low for p in phrases)


def stage36_is_different_day_text(text_: Optional[str], lang: str) -> bool:
    low = _stage36_low(text_)
    if not low:
        return False
    phrases = {
        "не завтра", "не сегодня", "другой день", "другая дата", "не этот день",
        "ne rit", "ne rīt", "ne sodien", "ne šodien", "citu dienu", "cits datums", "ne so dienu", "ne šo dienu",
        "not tomorrow", "not today", "another day", "different day", "different date",
    }
    return any(p in low for p in phrases)


def stage36_recovery_reply(lang: str, kind: str) -> str:
    lang = get_lang(lang)
    if kind == "hold":
        if lang == "ru":
            return "Конечно, я подожду. Когда будете готовы — напишите, и продолжим с этого места."
        if lang == "en":
            return "Of course, take your time. Message me when you’re ready and we’ll continue from here."
        return "Protams, pagaidīšu. Kad būsiet gatavs, uzrakstiet — turpināsim no šīs vietas."
    if kind == "ask_day":
        if lang == "ru":
            return "Понял. Тогда посмотрим другой день и сохраним ваши пожелания по времени. Какая дата удобнее?"
        if lang == "en":
            return "Got it. Let’s check another day and keep your time preference. What date works better?"
        return "Sapratu. Tad paskatīsimies citu dienu un paturēsim jūsu vēlmi pēc laika. Kurš datums būtu ērtāks?"
    if kind == "ask_time":
        if lang == "ru":
            return "Понял. Какое другое время вам было бы удобно?"
        if lang == "en":
            return "Understood. What other time would work for you?"
        return "Skaidrs. Kāds cits laiks jums būtu ērts?"
    if kind == "need_date":
        if lang == "ru":
            return "Могу предложить варианты, только уточните день — на какую дату смотреть?"
        if lang == "en":
            return "I can suggest options — just tell me which day I should check."
        return "Varu piedāvāt variantus — tikai pasakiet, uz kuru dienu skatīties."
    if kind == "need_service":
        if lang == "ru":
            return "Конечно, помогу подобрать вариант. Сначала уточню услугу — на что вас записать?"
        if lang == "en":
            return "Of course, I can help. First, which service should I book for you?"
        return "Protams, palīdzēšu atrast variantu. Vispirms precizēšu pakalpojumu — uz ko jūs pierakstīt?"
    if lang == "ru":
        return "Понял. Давайте продолжим запись — какое время вам было бы удобно?"
    if lang == "en":
        return "Got it. Let’s continue the booking — what time would work for you?"
    return "Sapratu. Turpinām pierakstu — kāds laiks jums būtu ērts?"


def stage36_uncertain_slots_reply(lang: str, slots: List[str]) -> str:
    lang = get_lang(lang)
    joined = _stage33_join_options(lang, slots[:4]) if slots else ""
    if lang == "ru":
        return (
            f"Понимаю. Можно выбрать один из этих вариантов: {joined}. Или напишите, если посмотреть раньше, позже или другой день."
            if joined
            else "Понимаю. Могу посмотреть раньше, позже или другой день — как вам удобнее?"
        )
    if lang == "en":
        return (
            f"No problem. You can choose one of these options: {joined}. Or tell me if I should check earlier, later, or another day."
            if joined
            else "No problem. I can check earlier, later, or another day — what would help?"
        )
    return (
        f"Sapratu. Varat izvēlēties kādu no šiem variantiem: {joined}. Vai arī uzrakstiet, ja paskatīties agrāk, vēlāk vai citu dienu."
        if joined
        else "Sapratu. Varu paskatīties agrāk, vēlāk vai citu dienu — kā jums būtu ērtāk?"
    )


def stage36_offer_context_slots(
    tenant_id: str,
    user_key: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    pending = pending or {}
    service_item = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
    if not service_item:
        c["state"] = STATE_AWAITING_SERVICE
        c["pending"] = pending or {"booking_intent": True}
        db_save_conversation(tenant_id, user_key, c)
        reply = stage36_recovery_reply(lang, "need_service")
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    base_day = parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip())
    if not base_day:
        dt_context = parse_dt_any_tz(str(c.get("datetime_iso") or pending.get("candidate_datetime_iso") or pending.get("confirm_slot_iso") or "").strip())
        if dt_context:
            base_day = dt_context.replace(hour=9, minute=0, second=0, microsecond=0)
    if not base_day:
        c["state"] = STATE_AWAITING_DATE
        c["pending"] = pending or {"booking_intent": True}
        db_save_conversation(tenant_id, user_key, c)
        reply = stage36_recovery_reply(lang, "need_date")
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    return offer_slots_for_date(tenant_id, user_key, lang, c, pending, settings, service_catalog, base_day)


def stage36_advanced_recovery_if_needed(
    tenant_id: str,
    user_key: str,
    msg: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    channel: str = "",
    source: str = "runtime",
) -> Optional[Dict[str, Any]]:
    if not stage36_recovery_enabled(channel, source):
        return None
    raw = str(msg or "").strip()
    if not raw:
        return None
    state = conversation_state(c)
    pending = pending or {}

    # Stage 36.2: if we are waiting for a date and the user provides one
    # (e.g. "parīt" after "ne rīt"), continue directly to slot offering.
    if state == STATE_AWAITING_DATE:
        recovery_day = stage36_recovery_date_from_text(raw)
        if recovery_day:
            pending = stage36_remember_time_window_context(pending)
            return stage36_continue_with_new_date_slots(
                tenant_id, user_key, lang, c, pending, settings, service_catalog, recovery_day
            )

    if stage36_is_hold_text(raw, lang):
        pending["booking_intent"] = True
        pending["stage36_hold"] = True
        c["pending"] = pending
        db_save_conversation(tenant_id, user_key, c)
        reply = stage36_recovery_reply(lang, "hold")
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    if stage36_is_different_day_text(raw, lang):
        # Preserve semantic time preference before clearing concrete slots.
        pending = stage36_remember_time_window_context(pending)
        # Stage 36.2: if the same message already contains the replacement date
        # ("ne rīt, bet parīt" / "не завтра, а послезавтра"), do not ask the
        # date again; continue directly to contextual slot offering.
        recovery_day = stage36_recovery_date_from_text(raw)
        if recovery_day:
            return stage36_continue_with_new_date_slots(
                tenant_id, user_key, lang, c, pending, settings, service_catalog, recovery_day
            )
        pending.pop("confirm_slot_iso", None)
        pending.pop("candidate_datetime_iso", None)
        pending.pop("requested_datetime_iso", None)
        pending.pop("partial_datetime_iso", None)
        clear_offered_slots(pending)
        pending = stage36_recover_time_window_context(pending)
        pending["booking_intent"] = True
        c["datetime_iso"] = None
        c["time_text"] = None
        c["state"] = STATE_AWAITING_DATE
        c["pending"] = pending
        db_save_conversation(tenant_id, user_key, c)
        reply = stage36_recovery_reply(lang, "ask_day")
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    if stage36_is_different_time_text(raw, lang) and state in {STATE_AWAITING_CONFIRM, STATE_AWAITING_TIME}:
        pending.pop("confirm_slot_iso", None)
        pending.pop("candidate_datetime_iso", None)
        pending.pop("requested_datetime_iso", None)
        pending.pop("partial_datetime_iso", None)
        clear_offered_slots(pending)
        pending["booking_intent"] = True
        c["datetime_iso"] = None
        c["time_text"] = None
        c["state"] = STATE_AWAITING_TIME
        c["pending"] = pending
        db_save_conversation(tenant_id, user_key, c)
        reply = stage36_recovery_reply(lang, "ask_time")
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    if stage36_is_uncertain_text(raw, lang) or stage36_is_available_request(raw, lang):
        if state in {STATE_AWAITING_TIME, STATE_AWAITING_CONFIRM}:
            slots = _slot_labels_from_pending(pending)
            if slots:
                pending = stage36_recover_time_window_context(pending)
                pending["booking_intent"] = True
                c["pending"] = pending
                c["state"] = STATE_AWAITING_TIME
                db_save_conversation(tenant_id, user_key, c)
                reply = stage36_uncertain_slots_reply(lang, slots)
                return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}
            return stage36_offer_context_slots(tenant_id, user_key, lang, c, pending, settings, service_catalog)
        if state == STATE_AWAITING_DATE:
            return stage36_offer_context_slots(tenant_id, user_key, lang, c, pending, settings, service_catalog)
        if state == STATE_AWAITING_SERVICE:
            reply = stage36_recovery_reply(lang, "need_service")
            c["pending"] = pending or {"booking_intent": True}
            db_save_conversation(tenant_id, user_key, c)
            return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    return None

def free_router_handle_turn(
    tenant_id: str,
    user_key: str,
    raw_phone: str,
    channel: str,
    msg: str,
    lang: str,
    c: Dict[str, Any],
    pending: Dict[str, Any],
    tenant: Dict[str, Any],
    settings: Dict[str, Any],
    service_catalog: List[Dict[str, Any]],
    service_aliases: Dict[str, str],
    business_memory: str,
) -> Optional[Dict[str, Any]]:
    if not msg:
        return None
    state = conversation_state(c)
    if not (is_active_booking_flow(c) or state in ACTIVE_BOOKING_STATES):
        return None

    pending = pending or {}

    # Stage 36: recovery for chaotic / incomplete answers inside active booking flow.
    # This layer preserves booking context and avoids resetting service/date/time.
    stage36_recovery = stage36_advanced_recovery_if_needed(
        tenant_id=tenant_id,
        user_key=user_key,
        msg=msg,
        lang=lang,
        c=c,
        pending=pending,
        settings=settings,
        service_catalog=service_catalog,
        channel=channel,
        source="runtime",
    )
    if stage36_recovery:
        return stage36_recovery

    # Stage 32 Hotfix: contextual refinement of already offered/confirmed slots.
    # Examples: "не так поздно" -> earlier options; "не так рано" -> later options.
    stage32_refinement = stage32_refine_offered_slots_if_needed(
        tenant_id=tenant_id,
        user_key=user_key,
        msg=msg,
        lang=lang,
        c=c,
        pending=pending,
        settings=settings,
        service_catalog=service_catalog,
    )
    if stage32_refinement:
        return stage32_refinement

    # Stage 24 Hotfix: offered slot choice must win before generic date/time merge.
    # Example: after offering 09:00 / 09:30 / 10:00, user says "10:00".
    # Do not reuse the old rejected requested time from pending["time_text"].
    selected_offered_iso = extract_slot_choice(msg, pending)
    if selected_offered_iso:
        dt_selected = parse_dt_any_tz(selected_offered_iso)
        if dt_selected:
            pending.pop("candidate_datetime_iso", None)
            pending.pop("requested_datetime_iso", None)
            pending.pop("partial_datetime_iso", None)
            pending.pop("confirm_slot_iso", None)
            pending["awaiting_time_date_iso"] = dt_selected.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
            pending["time_text"] = dt_selected.strftime("%H:%M")
            clear_offered_slots(pending)
            c["pending"] = pending or {"booking_intent": True}
            c["datetime_iso"] = None
            c["state"] = STATE_AWAITING_TIME
            result = book_appointment_for_datetime(tenant_id, raw_phone, channel, lang, c, settings, service_catalog, dt_selected)
            db_save_conversation(tenant_id, user_key, c)
            return result

    # Stage 29 Hotfix: in confirm-state, phrases like "можно позже?" /
    # "var vēlāk?" / "later?" mean negotiate a later slot, not repeat
    # the same confirmation.
    if state == STATE_AWAITING_CONFIRM and detect_time_shift_direction(msg, lang):
        shift_direction = detect_time_shift_direction(msg, lang)
        anchor_iso = str(pending.get("confirm_slot_iso") or c.get("datetime_iso") or "").strip()
        anchor_dt = parse_dt_any_tz(anchor_iso)
        service_item_shift = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
        if anchor_dt and service_item_shift and calendar_is_configured(settings["calendar_id"]):
            slots = find_negotiation_slots_for_direction(
                calendar_id=settings["calendar_id"],
                base_day=anchor_dt,
                anchor_dt=anchor_dt,
                direction=shift_direction,
                duration_min=service_duration_min(service_item_shift),
                work_start=settings["work_start"],
                work_end=settings["work_end"],
                limit=3,
                business_rules=settings.get("business_rules"),
                service_account_json=settings.get("service_account_json"),
            )
            pending.pop("confirm_slot_iso", None)
            pending.pop("candidate_datetime_iso", None)
            pending["booking_intent"] = True
            c["datetime_iso"] = None
            return negotiation_slots_response(tenant_id, user_key, lang, c, pending, slots)

    # Stage 31 Hotfix: fuzzy windows such as "вечером" / "vakarā" /
    # "after lunch" should offer a set of slots, not become one exact confirmation.
    stage31_time_window = stage31_offer_time_window_if_needed(
        tenant_id=tenant_id,
        user_key=user_key,
        msg=msg,
        lang=lang,
        c=c,
        pending=pending,
        settings=settings,
        service_catalog=service_catalog,
        service_aliases=service_aliases,
    )
    if stage31_time_window:
        return stage31_time_window

    # Stage 24 Hotfix: a clear "no" in confirmation state means exit the
    # confirmation loop and ask for another time instead of re-confirming.
    if state == STATE_AWAITING_CONFIRM and is_no_text(msg, lang):
        pending.pop("confirm_slot_iso", None)
        pending.pop("pending_confirm_upsell", None)
        pending.pop("confirm_upsell_done", None)
        pending.pop("upsell_offer_active", None)
        pending.pop("addon_service", None)
        pending.pop("candidate_datetime_iso", None)
        pending.pop("requested_datetime_iso", None)
        pending.pop("partial_datetime_iso", None)
        clear_offered_slots(pending)
        pending["booking_intent"] = True
        c["pending"] = pending or {"booking_intent": True}
        c["datetime_iso"] = None
        c["time_text"] = None
        c["state"] = STATE_AWAITING_TIME
        db_save_conversation(tenant_id, user_key, c)
        if lang == "ru":
            reply = "Понял. Какое другое время вам было бы удобно?"
        elif lang == "en":
            reply = "Understood. What other time would work for you?"
        else:
            reply = "Skaidrs. Kādu citu laiku vēlaties?"
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    c, pending, service_item, candidate_dt = free_router_merge_message_slots(msg, c, pending, service_catalog, service_aliases, lang)

    # Stage 25.6 hotfix: when we are waiting for a date and the user gives only a date
    # ("16 maijs", "16.05"), do not treat it as missing datetime and repeat the same
    # question. Move to time selection by offering available slots for that day.
    date_only_for_router = parse_date_only_text(msg)
    if conversation_state(c) == STATE_AWAITING_DATE and date_only_for_router and (c.get("service") or pending.get("service")):
        return offer_slots_for_date(tenant_id, user_key, lang, c, pending, settings, service_catalog, date_only_for_router)

    if free_router_is_services_request(msg, lang):
        pending["booking_intent"] = True
        c["pending"] = pending
        if not (c.get("service") or pending.get("service")):
            c["state"] = STATE_AWAITING_SERVICE
        db_save_conversation(tenant_id, user_key, c)
        reply = free_router_services_reply(lang, service_catalog, pending)
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    if free_router_is_variants_request(msg, lang):
        if not (c.get("service") or pending.get("service")):
            pending["booking_intent"] = True
            c["pending"] = pending
            c["state"] = STATE_AWAITING_SERVICE
            db_save_conversation(tenant_id, user_key, c)
            reply = free_router_variants_reply_without_service(lang, service_catalog, pending)
            return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}
        base_day = candidate_dt or parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or c.get("datetime_iso") or "").strip())
        if base_day:
            return offer_slots_for_date(tenant_id, user_key, lang, c, pending, settings, service_catalog, base_day)
        c["state"] = STATE_AWAITING_DATE
        c["pending"] = pending
        db_save_conversation(tenant_id, user_key, c)
        reply = free_router_ask_missing_datetime(lang, c, pending)
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    if free_router_is_price_request(msg, lang):
        faq_result = try_barbershop_faq(
            msg,
            lang,
            tenant,
            settings,
            service_catalog,
            service_aliases,
            business_memory,
            current_service_key=(c or {}).get("service") or (pending or {}).get("service"),
        )
        if faq_result:
            pending["booking_intent"] = True
            c["pending"] = pending
            db_save_conversation(tenant_id, user_key, c)
            return faq_with_flow_followup(faq_result, lang, c, pending, service_catalog, True)

    missing = free_router_missing_fields(c, pending)
    if "service" in missing:
        pending["booking_intent"] = True
        c["pending"] = pending
        c["state"] = STATE_AWAITING_SERVICE
        db_save_conversation(tenant_id, user_key, c)
        reply = free_router_ask_missing_service(lang, pending, service_catalog)
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    if "datetime" in missing:
        pending["booking_intent"] = True
        c["pending"] = pending
        c["state"] = STATE_AWAITING_DATE
        db_save_conversation(tenant_id, user_key, c)
        reply = free_router_ask_missing_datetime(lang, c, pending)
        return {"status": "need_more", "reply_voice": reply, "msg_out": reply, "lang": lang, "preserve_text": True}

    candidate_dt = free_router_context_datetime(c, pending)
    if candidate_dt:
        return free_router_handle_candidate_datetime(tenant_id, user_key, raw_phone, channel, lang, c, pending, settings, service_catalog, candidate_dt)

    return None

# -------------------------
# CORE LOGIC: handle_user_text
# -------------------------
def handle_user_text(
    tenant_id: str, raw_phone: str, text_in: str, channel: str, lang_hint: str, source: str = "runtime"
) -> Dict[str, Any]:
    msg = (text_in or "").strip()
    tenant = load_runtime_tenant(tenant_id)

    explicit_lang_hint = (lang_hint or "").strip().lower()
    lang_locked = explicit_lang_hint if explicit_lang_hint in ("lv", "ru", "en") else None
    detected_lang = get_lang(lang_locked or detect_language(msg))
    lang = detected_lang

    if not tenant.get("_id"):
        return blocked_result_for_reason(lang, "unavailable")

    access = tenant_access_decision(tenant, channel=channel, source=source)
    if not access.get("allowed"):
        blocked = blocked_result_for_reason(lang, str(access.get("reason") or "unavailable"))
        meta = access.get("meta") or {}
        if meta.get("usage_limit"):
            blocked["usage_current"] = meta.get("usage_current", 0)
            blocked["usage_limit"] = meta.get("usage_limit", 0)
        return blocked

    user_key = norm_user_key(raw_phone)
    c = db_get_or_create_conversation(tenant_id, user_key, detected_lang)

    if lang_locked:
        c["lang"] = lang_locked
    elif msg:
        c["lang"] = resolve_reply_language(msg, c.get("lang") or detected_lang)

    lang = get_lang(c.get("lang") or detected_lang)
    if not tenant_runtime_ready(tenant):
        log_tenant_runtime_validation(tenant)
        return blocked_result_for_reason(lang, "unavailable")
    settings = tenant_settings(tenant, lang)
    service_catalog = tenant_service_catalog(tenant)
    service_aliases = ensure_default_barbershop_aliases(
        service_catalog,
        merged_service_alias_map(service_catalog, tenant, lang),
        lang,
    )
    business_memory = tenant_business_memory(tenant, lang)
    calendar_ready = calendar_is_configured(settings["calendar_id"])

    # Stage 25.5: handle post-booking thanks/goodbye before normalizing state,
    # so stale pending booking flags cannot reopen a completed flow.
    closure_result = maybe_conversational_closure_result(tenant_id, user_key, msg, lang, c, tenant)
    if closure_result:
        return closure_result

    c["state"] = conversation_state(c)
    c = normalize_booking_state(c)
    pending = c.get("pending") or {}
    t_low = msg.lower()

    # -------------------------
    # STAGE 37.2 — SLOT ACK GUARD BEFORE TEMPORAL ROUTING
    # -------------------------
    stage37_ack_guard = stage37_choose_first_offered_slot_from_ack(
        tenant_id=tenant_id,
        user_key=user_key,
        raw_phone=raw_phone,
        channel=channel,
        msg=msg,
        lang=lang,
        c=c,
        pending=pending,
        settings=settings,
        service_catalog=service_catalog,
    ) if msg else None
    if stage37_ack_guard:
        return stage37_ack_guard

    # -------------------------
    # STAGE 37 — TEMPORAL SEMANTIC ENGINE
    # -------------------------
    # Must run before LLM routing and generic entity persistence so short
    # recovery replies such as "parīt" / "aizparīt" are treated as dates,
    # not as vague text that re-enters the AWAITING_DATE loop.
    stage37_temporal = stage37_temporal_recovery_if_needed(
        tenant_id=tenant_id,
        user_key=user_key,
        msg=msg,
        lang=lang,
        c=c,
        pending=pending,
        settings=settings,
        service_catalog=service_catalog,
    ) if msg else None
    if stage37_temporal:
        return stage37_temporal

    # -------------------------
    # STAGE 28 — CONFIRMATION FINALIZATION GUARD
    # -------------------------
    # Run deterministic yes/no confirmation before LLM semantic routing and
    # entity persistence. Otherwise a short answer like "да" can be treated as
    # a generic booking continuation, moving the state back to AWAITING_TIME and
    # causing the bot to repeat the same confirmation prompt.
    if msg and conversation_state(c) == STATE_AWAITING_CONFIRM and (is_yes_text(msg, lang) or is_no_text(msg, lang)):
        confirm_iso = str(pending.get("confirm_slot_iso") or c.get("datetime_iso") or "").strip()
        dt_confirm = parse_dt_any_tz(confirm_iso)

        if is_yes_text(msg, lang):
            if not dt_confirm:
                c["state"] = STATE_AWAITING_TIME
                c["datetime_iso"] = None
                db_save_conversation(tenant_id, user_key, c)
                reply_text = prompt_for_state(lang, c, pending, service_catalog)
                return {"status": "need_more", "reply_voice": reply_text, "msg_out": reply_text, "lang": lang, "preserve_text": True}

            primary_service_item = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
            if should_offer_post_confirm_upsell(service_catalog, primary_service_item, pending):
                result = move_to_post_confirm_upsell(lang, c, pending, service_catalog, dt_confirm)
                db_save_conversation(tenant_id, user_key, c)
                return result

            result = book_appointment_for_datetime(
                tenant_id, raw_phone, channel, lang, c, settings, service_catalog, dt_confirm, require_confirmation=False
            )
            # book_appointment_for_datetime now fully exits the booking state on success.
            db_save_conversation(tenant_id, user_key, c)
            return result

        if is_no_text(msg, lang):
            pending.pop("confirm_slot_iso", None)
            pending.pop("pending_confirm_upsell", None)
            pending.pop("confirm_upsell_done", None)
            pending.pop("upsell_offer_active", None)
            pending.pop("addon_service", None)
            pending.pop("candidate_datetime_iso", None)
            pending.pop("requested_datetime_iso", None)
            pending.pop("partial_datetime_iso", None)
            clear_offered_slots(pending)
            pending["booking_intent"] = True
            c["pending"] = pending or {"booking_intent": True}
            c["datetime_iso"] = None
            c["time_text"] = None
            c["state"] = STATE_AWAITING_TIME
            db_save_conversation(tenant_id, user_key, c)
            if lang == "ru":
                reply_text = "Понял. Какое другое время вам было бы удобно?"
            elif lang == "en":
                reply_text = "Understood. What other time would work for you?"
            else:
                reply_text = "Skaidrs. Kādu citu laiku vēlaties?"
            return {"status": "need_more", "reply_voice": reply_text, "msg_out": reply_text, "lang": lang, "preserve_text": True}

    stage30_confirm_negotiation = stage30_negotiate_from_confirm_if_needed(
        tenant_id=tenant_id,
        user_key=user_key,
        msg=msg,
        lang=lang,
        c=c,
        pending=pending,
        settings=settings,
        service_catalog=service_catalog,
    ) if msg else None
    if stage30_confirm_negotiation:
        return stage30_confirm_negotiation

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
    stage26_hint = stage26_semantic_route_message(
        msg=msg,
        lang=lang,
        c=c,
        pending=pending,
        tenant=tenant,
        settings=settings,
        service_catalog=service_catalog,
        service_aliases=service_aliases,
        business_memory=business_memory,
        llm_hint=llm_hint,
        channel=channel,
        source=source,
    ) if msg else {}
    if stage26_hint:
        llm_hint = merge_stage26_into_llm_hint(llm_hint, stage26_hint)
        c, pending = remember_stage26_datetime_hint(c, pending, stage26_hint)

    # Stage 27: persist extracted service/date/time before orchestration decides
    # which missing field to ask next. This prevents asking for service/date again
    # when the user already provided them in one natural sentence.
    if msg:
        c, pending = stage27_persist_entities_from_turn(
            c=c,
            pending=pending,
            msg=msg,
            lang=lang,
            llm_hint=llm_hint,
            service_catalog=service_catalog,
            service_aliases=service_aliases,
        )

    stage30_after_window = stage30_offer_after_time_window_if_needed(
        tenant_id=tenant_id,
        user_key=user_key,
        msg=msg,
        lang=lang,
        c=c,
        pending=pending,
        settings=settings,
        service_catalog=service_catalog,
        service_aliases=service_aliases,
    ) if msg else None
    if stage30_after_window:
        return stage30_after_window

    stage31_time_window = stage31_offer_time_window_if_needed(
        tenant_id=tenant_id,
        user_key=user_key,
        msg=msg,
        lang=lang,
        c=c,
        pending=pending,
        settings=settings,
        service_catalog=service_catalog,
        service_aliases=service_aliases,
    ) if msg else None
    if stage31_time_window:
        return stage31_time_window

    understanding = build_understanding_result(
        msg=msg,
        lang=lang,
        c=c,
        pending=pending,
        llm_hint=llm_hint,
        tenant=tenant,
        settings=settings,
        service_catalog=service_catalog,
        service_aliases=service_aliases,
        business_memory=business_memory,
    )
    orchestration = orchestrate_turn(c, msg, lang, understanding)
    active_flow = is_active_booking_flow(c)

    explicit_cancel_request = orchestration.get("action") == ORCH_ACTION_CANCEL
    explicit_reschedule_request = orchestration.get("action") == ORCH_ACTION_RESCHEDULE

    # Stage 25 Hotfix: hard-confirm handler must run before generic booking flow.
    # In AWAITING_CONFIRM, clear yes/no answers must execute or exit confirmation,
    # not be reinterpreted by later generic state handlers as another confirmation prompt.
    if msg and conversation_state(c) == STATE_AWAITING_CONFIRM:
        pending = c.get("pending") or {}
        confirm_iso = str(pending.get("confirm_slot_iso") or c.get("datetime_iso") or "").strip()
        dt_confirm = parse_dt_any_tz(confirm_iso)
        llm_confirmation = (llm_hint or {}).get("confirmation")

        if is_yes_text(msg, lang) or llm_confirmation == "yes" or orchestration.get("action") == ORCH_ACTION_CONFIRM_YES:
            if not dt_confirm:
                c["state"] = STATE_AWAITING_TIME
                db_save_conversation(tenant_id, user_key, c)
                reply_text = prompt_for_state(lang, c, pending, service_catalog)
                return {"status": "need_more", "reply_voice": reply_text, "msg_out": reply_text, "lang": lang}

            primary_service_item = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
            if should_offer_post_confirm_upsell(service_catalog, primary_service_item, pending):
                result = move_to_post_confirm_upsell(lang, c, pending, service_catalog, dt_confirm)
                db_save_conversation(tenant_id, user_key, c)
                return result

            result = book_appointment_for_datetime(
                tenant_id, raw_phone, channel, lang, c, settings, service_catalog, dt_confirm, require_confirmation=False
            )
            db_save_conversation(tenant_id, user_key, c)
            return result

        if is_no_text(msg, lang) or llm_confirmation == "no" or orchestration.get("action") == ORCH_ACTION_CONFIRM_NO:
            pending.pop("confirm_slot_iso", None)
            pending.pop("pending_confirm_upsell", None)
            pending.pop("confirm_upsell_done", None)
            pending.pop("upsell_offer_active", None)
            pending.pop("addon_service", None)
            pending.pop("candidate_datetime_iso", None)
            pending.pop("requested_datetime_iso", None)
            pending.pop("partial_datetime_iso", None)
            clear_offered_slots(pending)
            pending["booking_intent"] = True
            c["pending"] = pending or {"booking_intent": True}
            c["datetime_iso"] = None
            c["time_text"] = None
            c["state"] = STATE_AWAITING_TIME
            db_save_conversation(tenant_id, user_key, c)
            if lang == "ru":
                reply_text = "Понял. Какое другое время вам было бы удобно?"
            elif lang == "en":
                reply_text = "Understood. What other time would work for you?"
            else:
                reply_text = "Skaidrs. Kādu citu laiku vēlaties?"
            return {"status": "need_more", "reply_voice": reply_text, "msg_out": reply_text, "lang": lang, "preserve_text": True}

    if explicit_cancel_request:
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
            "calendar_action": "delete_event",
        }

    if explicit_reschedule_request or ((not active_flow) and ((llm_hint or {}).get("intent") == "reschedule" and float((llm_hint or {}).get("confidence") or 0.0) >= LLM_INTENT_MIN_CONFIDENCE)):
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
        reschedule_pending = {
            "booking_intent": True,
            "reschedule_event_id": ev["id"],
            "reschedule_old_iso": ev["start"].get("dateTime"),
            "reschedule_summary": ev.get("summary") or "",
            "reschedule_description": ev.get("description") or "",
        }
        existing_name = extract_name_from_event_description(ev.get("description") or "")
        if existing_name and not c.get("name"):
            c["name"] = existing_name
        reschedule_service_item = infer_service_item_from_calendar_event(ev, service_catalog, lang)
        if reschedule_service_item:
            c, reschedule_pending = remember_booking_service(c, reschedule_pending, reschedule_service_item, lang)
        else:
            c["pending"] = reschedule_pending
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

    if orchestration.get("action") == ORCH_ACTION_FAQ and understanding.get("faq_result"):
        faq_result = faq_with_flow_followup(understanding.get("faq_result"), lang, c, pending, service_catalog, active_flow)
        if active_flow:
            db_save_conversation(tenant_id, user_key, c)
        return faq_result

    if orchestration.get("action") == ORCH_ACTION_GREET and not active_flow and c["state"] not in ACTIVE_BOOKING_STATES:
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
    if orchestration.get("action") == ORCH_ACTION_IDENTITY and not active_flow:
        return {
            "status": "identity",
            "reply_voice": t(lang, "identity_yes", biz=settings["biz_name"]),
            "msg_out": t(lang, "identity_yes", biz=settings["biz_name"]),
            "lang": lang,
        }
    if orchestration.get("action") == ORCH_ACTION_HOURS and not active_flow:
        return {
            "status": "info",
            "reply_voice": t(lang, "hours_info", biz=settings["biz_name"], start=settings["work_start"], end=settings["work_end"]),
            "msg_out": t(lang, "hours_info", biz=settings["biz_name"], start=settings["work_start"], end=settings["work_end"]),
            "lang": lang,
        }

    # Keep the Stage 26 enriched understanding for the rest of this turn.
    # get_llm_data() returns the raw classifier output, so do not overwrite
    # the merged semantic hint that was used by the orchestrator above.
    llm_hint = llm_hint if msg else {}

    fresh_booking_start = orchestration.get("action") == ORCH_ACTION_START_BOOKING
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
        # Stage 27: reset_booking_context intentionally clears old flow data,
        # but for a fresh one-message booking we must immediately re-persist
        # entities from the current user message.
        if msg:
            c, pending = stage27_persist_entities_from_turn(
                c=c,
                pending=pending,
                msg=msg,
                lang=lang,
                llm_hint=llm_hint,
                service_catalog=service_catalog,
                service_aliases=service_aliases,
            )
        active_flow = True

    pending = c.get("pending") or {}

    # Stage 36.3: semantic date-shift continuity.
    # When the user rejects the current day and then provides a replacement date
    # (e.g. "ne rīt" -> "parīt"), continue directly to contextual slot
    # offering. This must run before generic partial datetime persistence,
    # otherwise the flow can fall back into AWAITING_DATE and lose the
    # evening/after-work preference.
    if (
        msg
        and conversation_state(c) == STATE_AWAITING_DATE
        and (is_active_booking_flow(c) or active_flow)
    ):
        stage36_shift_day = stage36_recovery_date_from_text(msg)
        if stage36_shift_day:
            pending = stage36_recover_time_window_context(
                stage36_remember_time_window_context(pending or {})
            )
            pending["booking_intent"] = True
            return stage36_continue_with_new_date_slots(
                tenant_id=tenant_id,
                user_key=user_key,
                lang=lang,
                c=c,
                pending=pending,
                settings=settings,
                service_catalog=service_catalog,
                base_day=stage36_shift_day,
            )

    # Stage 27.1 hotfix: do not re-run the old fresh-booking service prompt
    # branch if Stage 27 has already persisted a service from this same turn.
    # Otherwise phrases like "uz konsultāciju" can be recognized by Stage 27,
    # then overwritten by the older exact matcher and incorrectly ask service again.
    if fresh_booking_start and msg and not str(c.get("service") or (pending or {}).get("service") or "").strip():
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
            # Do NOT clear candidate date/time here: user may have already provided it.
            clear_offered_slots(pending)
            c, pending = remember_partial_booking_datetime_from_message(c, pending, msg)
            c["pending"] = pending or None
            c["datetime_iso"] = None
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
        c, pending = remember_partial_booking_datetime_from_message(c, pending, msg)

    # Stage 29 Hotfix: "после 14:00" / "pēc 14:00" / "after 14:00" is a
    # strict time window request, not an exact 14:00 booking. Offer several
    # available slots after the anchor instead of asking to confirm 14:00.
    after_anchor_stage29 = detect_after_time_anchor(msg, lang)
    if after_anchor_stage29 and str(c.get("service") or (pending or {}).get("service") or "").strip():
        base_day_stage29 = parse_dt_any_tz(str((pending or {}).get("awaiting_time_date_iso") or "").strip()) or date_only_dt_for_msg
        if base_day_stage29:
            return offer_slots_after_time_anchor(
                tenant_id=tenant_id,
                user_key=user_key,
                lang=lang,
                c=c,
                pending=pending,
                settings=settings,
                service_catalog=service_catalog,
                base_date=base_day_stage29,
                anchor_parts=after_anchor_stage29,
            )

    # Stage 27: if one message already contains service + date but no exact time,
    # do not ask service again. Move directly to slot offering / time choice.
    if (fresh_booking_start or orchestration.get("action") == ORCH_ACTION_START_BOOKING) and c.get("service"):
        base_day_stage27 = parse_dt_any_tz(str((pending or {}).get("awaiting_time_date_iso") or "").strip())
        candidate_stage27 = booking_candidate_datetime_from_context(c, pending or {})
        if base_day_stage27 and not candidate_stage27:
            return offer_slots_for_date(tenant_id, user_key, lang, c, pending, settings, service_catalog, base_day_stage27)

    # Stage 24: free-form router gets first chance inside active booking flow.
    free_router_result = free_router_handle_turn(
        tenant_id=tenant_id,
        user_key=user_key,
        raw_phone=raw_phone,
        channel=channel,
        msg=msg,
        lang=lang,
        c=c,
        pending=pending,
        tenant=tenant,
        settings=settings,
        service_catalog=service_catalog,
        service_aliases=service_aliases,
        business_memory=business_memory,
    )
    if free_router_result:
        return free_router_result

    override_service_item = None
    if msg and c.get("service"):
        detected_override_key = canonical_service_key_from_text(msg, service_aliases)
        if detected_override_key and detected_override_key != str(c.get("service") or pending.get("service") or "").strip():
            override_service_item = get_service_item_by_key(service_catalog, detected_override_key)
        elif not detected_override_key:
            detected_service_item = extract_service_from_text(msg, service_catalog, lang)
            current_service_item = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
            if detected_service_item and current_service_item and str(detected_service_item.get("key") or "") != str(current_service_item.get("key") or ""):
                override_service_item = detected_service_item
    if override_service_item and conversation_state(c) in ACTIVE_BOOKING_STATES:
        return apply_inflow_service_override(tenant_id, user_key, lang, c, pending, settings, service_catalog, override_service_item)

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

            # Stage 22 hotfix: if date/time was provided before service,
            # use it immediately after service selection.
            candidate_dt = booking_candidate_datetime_from_context(c, pending)
            if candidate_dt:
                pending.pop("candidate_datetime_iso", None)
                pending.pop("requested_datetime_iso", None)
                pending.pop("partial_datetime_iso", None)
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
            stored_window = parse_time_window(msg) or pending_time_window_tuple(pending)
            if stored_window:
                pending["preferred_time_window"] = [stored_window[0], stored_window[1]]
            return offer_slots_for_date(tenant_id, user_key, lang, c, pending, settings, service_catalog, base_date)
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "need_more",
            "reply_voice": t(lang, "ask_booking_date"),
            "msg_out": t(lang, "ask_booking_date"),
            "lang": lang,
        }

    if c["state"] == STATE_AWAITING_TIME:
        service_item_current = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
        if msg and date_only_dt_for_msg:
            return offer_slots_for_date(tenant_id, user_key, lang, c, pending, settings, service_catalog, date_only_dt_for_msg)
        if is_other_day_text(msg, lang):
            pending.pop("confirm_slot_iso", None)
            pending.pop("candidate_datetime_iso", None)
            pending.pop("awaiting_time_date_iso", None)
            pending = stage36_remember_time_window_context(pending)
            clear_offered_slots(pending)
            pending = stage36_recover_time_window_context(pending)
            c["pending"] = pending
            c["datetime_iso"] = None
            c["state"] = STATE_AWAITING_DATE
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "need_more",
                "reply_voice": t(lang, "other_day_prompt"),
                "msg_out": t(lang, "other_day_prompt"),
                "lang": lang,
                "preserve_text": True,
            }
        shift_direction = detect_time_shift_direction(msg, lang)
        if shift_direction and pending.get("awaiting_time_date_iso"):
            base_day = parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip())
            anchor_dt = None
            offered = get_offered_slots(pending)
            if shift_direction == "earlier" and offered:
                anchor_dt = parse_dt_any_tz(offered[0])
            elif shift_direction == "later" and offered:
                anchor_dt = parse_dt_any_tz(offered[-1])
            if not anchor_dt and base_day:
                win = pending_time_window_tuple(pending)
                if win:
                    anchor_dt = base_day.replace(hour=win[0] if shift_direction == "earlier" else max(win[1]-1, win[0]), minute=0, second=0, microsecond=0)
            if base_day and anchor_dt and service_item_current:
                slots = find_negotiation_slots_for_direction(
                    calendar_id=settings["calendar_id"],
                    base_day=base_day,
                    anchor_dt=anchor_dt,
                    direction=shift_direction,
                    duration_min=service_duration_min(service_item_current),
                    work_start=settings["work_start"],
                    work_end=settings["work_end"],
                    limit=3,
                    business_rules=settings.get("business_rules"),
                    service_account_json=settings.get("service_account_json"),
                ) if calendar_ready else []
                return negotiation_slots_response(tenant_id, user_key, lang, c, pending, slots)
        if is_short_ack_text(msg, lang):
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "need_more",
                "reply_voice": prompt_for_state(lang, c, pending, service_catalog),
                "msg_out": prompt_for_state(lang, c, pending, service_catalog),
                "lang": lang,
            }
        if is_hesitation_text(msg, lang):
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "need_more",
                "reply_voice": t(lang, "time_selection_uncertain"),
                "msg_out": t(lang, "time_selection_uncertain"),
                "lang": lang,
                "preserve_text": True,
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

    if msg and conversation_state(c) == STATE_POST_BOOKING_UPSELL:
        confirm_iso = str(pending.get("confirm_slot_iso") or c.get("datetime_iso") or "").strip()
        dt_confirm = parse_dt_any_tz(confirm_iso)
        llm_confirmation = (llm_hint or {}).get("confirmation")
        if not dt_confirm:
            pending.pop("upsell_offer_active", None)
            pending.pop("addon_service", None)
            c["pending"] = pending or None
            c["state"] = STATE_AWAITING_TIME
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "need_more",
                "reply_voice": prompt_for_state(lang, c, c.get("pending") or {}, service_catalog),
                "msg_out": prompt_for_state(lang, c, c.get("pending") or {}, service_catalog),
                "lang": lang,
            }

        if is_yes_text(msg, lang) or llm_confirmation == "yes":
            beard_item = find_service_item_by_group(service_catalog, "beard")
            pending.pop("upsell_offer_active", None)
            if beard_item:
                pending["addon_service"] = str(beard_item.get("key") or "").strip()
            c["pending"] = pending
            result = book_appointment_for_datetime(tenant_id, raw_phone, channel, lang, c, settings, service_catalog, dt_confirm, require_confirmation=False)
            if result.get("status") == "booked":
                result = finalize_post_confirm_upsell_response(lang, pending, service_catalog, dt_confirm, True) | {
                    "status": "booked",
                    "service": result.get("service"),
                    "when": result.get("when"),
                    "datetime_text": result.get("datetime_text"),
                }
            db_save_conversation(tenant_id, user_key, c)
            return result

        if is_no_text(msg, lang) or llm_confirmation == "no":
            pending.pop("upsell_offer_active", None)
            pending.pop("addon_service", None)
            c["pending"] = pending
            result = book_appointment_for_datetime(tenant_id, raw_phone, channel, lang, c, settings, service_catalog, dt_confirm, require_confirmation=False)
            if result.get("status") == "booked":
                result = finalize_post_confirm_upsell_response(lang, pending, service_catalog, dt_confirm, False) | {
                    "status": "booked",
                    "service": result.get("service"),
                    "when": result.get("when"),
                    "datetime_text": result.get("datetime_text"),
                }
            db_save_conversation(tenant_id, user_key, c)
            return result

        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "need_more",
            "reply_voice": t(lang, "repeat_yes_no"),
            "msg_out": t(lang, "repeat_yes_no"),
            "lang": lang,
        }

    if msg and conversation_state(c) == STATE_AWAITING_CONFIRM:
        override_dt = None
        if date_only_dt_for_msg and not explicit_time_present:
            pending.pop("pending_confirm_upsell", None)
            pending.pop("confirm_upsell_done", None)
            pending.pop("upsell_offer_active", None)
            pending.pop("addon_service", None)
            return offer_slots_for_date(tenant_id, user_key, lang, c, pending, settings, service_catalog, date_only_dt_for_msg)
        if explicit_time_present:
            base_for_override = date_only_dt_for_msg or parse_dt_any_tz(str(pending.get("confirm_slot_iso") or c.get("datetime_iso") or pending.get("awaiting_time_date_iso") or "").strip())
            if base_for_override:
                if date_only_dt_for_msg:
                    base_for_override = date_only_dt_for_msg
                override_dt = combine_date_with_explicit_time(base_for_override.isoformat(), msg)
        if override_dt:
            pending.pop("confirm_slot_iso", None)
            pending.pop("pending_confirm_upsell", None)
            pending.pop("confirm_upsell_done", None)
            pending.pop("upsell_offer_active", None)
            pending.pop("addon_service", None)
            clear_offered_slots(pending)
            c["pending"] = pending or {"booking_intent": True}
            c["datetime_iso"] = None
            c["state"] = STATE_AWAITING_TIME
            result = book_appointment_for_datetime(tenant_id, raw_phone, channel, lang, c, settings, service_catalog, override_dt)
            db_save_conversation(tenant_id, user_key, c)
            return result
        shift_direction = detect_time_shift_direction(msg, lang)
        if shift_direction:
            confirm_anchor = parse_dt_any_tz(str(pending.get("confirm_slot_iso") or c.get("datetime_iso") or "").strip())
            base_day = confirm_anchor or parse_dt_any_tz(str(pending.get("awaiting_time_date_iso") or "").strip())
            service_item_confirm = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
            if confirm_anchor and base_day and service_item_confirm:
                slots = find_negotiation_slots_for_direction(
                    calendar_id=settings["calendar_id"],
                    base_day=base_day,
                    anchor_dt=confirm_anchor,
                    direction=shift_direction,
                    duration_min=service_duration_min(service_item_confirm),
                    work_start=settings["work_start"],
                    work_end=settings["work_end"],
                    limit=3,
                    business_rules=settings.get("business_rules"),
                    service_account_json=settings.get("service_account_json"),
                ) if calendar_ready else []
                pending.pop("confirm_slot_iso", None)
                pending.pop("pending_confirm_upsell", None)
                pending.pop("confirm_upsell_done", None)
                pending.pop("upsell_offer_active", None)
                pending.pop("addon_service", None)
                pending["booking_intent"] = True
                pending["awaiting_time_date_iso"] = base_day.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
                c["pending"] = pending or {"booking_intent": True}
                c["datetime_iso"] = None
                c["state"] = STATE_AWAITING_TIME
                return negotiation_slots_response(tenant_id, user_key, lang, c, pending, slots)
        if is_other_day_text(msg, lang):
            pending.pop("confirm_slot_iso", None)
            pending.pop("pending_confirm_upsell", None)
            pending.pop("confirm_upsell_done", None)
            pending.pop("upsell_offer_active", None)
            pending.pop("addon_service", None)
            pending.pop("candidate_datetime_iso", None)
            pending.pop("awaiting_time_date_iso", None)
            pending["booking_intent"] = True
            clear_offered_slots(pending)
            c["pending"] = pending or {"booking_intent": True}
            c["datetime_iso"] = None
            c["time_text"] = None
            c["state"] = STATE_AWAITING_DATE
            db_save_conversation(tenant_id, user_key, c)
            reply_text = t(lang, "other_day_prompt")
            return {
                "status": "need_more",
                "reply_voice": reply_text,
                "msg_out": reply_text,
                "lang": lang,
            }
        if is_hesitation_text(msg, lang):
            pending.pop("confirm_slot_iso", None)
            pending.pop("pending_confirm_upsell", None)
            pending.pop("confirm_upsell_done", None)
            pending.pop("upsell_offer_active", None)
            pending.pop("addon_service", None)
            pending.pop("candidate_datetime_iso", None)
            pending.pop("awaiting_time_date_iso", None)
            pending["booking_intent"] = True
            clear_offered_slots(pending)
            c["pending"] = pending or {"booking_intent": True}
            c["datetime_iso"] = None
            c["time_text"] = None
            c["state"] = STATE_AWAITING_DATE
            db_save_conversation(tenant_id, user_key, c)
            reply_text = t(lang, "time_selection_uncertain")
            return {
                "status": "need_more",
                "reply_voice": reply_text,
                "msg_out": reply_text,
                "lang": lang,
            }
        confirm_iso = str(pending.get("confirm_slot_iso") or c.get("datetime_iso") or "").strip()
        dt_confirm = parse_dt_any_tz(confirm_iso)
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
            primary_service_item = get_service_item_by_key(service_catalog, c.get("service") or pending.get("service"))
            if should_offer_post_confirm_upsell(service_catalog, primary_service_item, pending):
                result = move_to_post_confirm_upsell(lang, c, pending, service_catalog, dt_confirm)
                db_save_conversation(tenant_id, user_key, c)
                return result
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
    ensure_dialogue_audit_table()


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


def _stage43a_env_flag(value: Any) -> bool:
    return bool(str(value or "").strip())


def _stage43a_database_check() -> Dict[str, Any]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as e:
        log.error("stage43a_database_readiness_failed err=%s", e)
        return {"ok": False, "error": e.__class__.__name__}


def _stage43a_table_check(table_name: str) -> Dict[str, Any]:
    try:
        with engine.connect() as conn:
            exists = conn.execute(text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema='public' AND table_name=:table_name
                )
                """
            ), {"table_name": table_name}).scalar()
        return {"ok": bool(exists)}
    except Exception as e:
        log.error("stage43a_table_readiness_failed table=%s err=%s", table_name, e)
        return {"ok": False, "error": e.__class__.__name__}


def stage43a_production_readiness_payload(tenant_id: str = TENANT_ID_DEFAULT) -> Dict[str, Any]:
    requested_tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    db_check = _stage43a_database_check()
    tables = {
        name: _stage43a_table_check(name)
        for name in ("tenants", "conversations", "phone_routes", "call_logs", "dialogue_audit_events", "usage_events")
    }

    env = {
        "database_url_set": _stage43a_env_flag(os.getenv("DATABASE_URL")),
        "server_base_url_set": _stage43a_env_flag(SERVER_BASE_URL),
        "openai_api_key_set": _stage43a_env_flag(OPENAI_API_KEY),
        "llm_intelligence_enabled": bool(LLM_INTELLIGENCE_ENABLED),
        "openai_model": OPENAI_MODEL,
        "sentry_enabled": _sentry_middleware_class is not None,
        "default_tenant_id": TENANT_ID_DEFAULT,
        "test_tenant_id": TEST_TENANT_ID or None,
        "allow_default_tenant_fallback": bool(ALLOW_DEFAULT_TENANT_FALLBACK),
    }

    integrations = {
        "twilio": {
            "validate_signature": bool(TWILIO_VALIDATE_SIGNATURE),
            "account_sid_set": _stage43a_env_flag(TWILIO_ACCOUNT_SID),
            "auth_token_set": _stage43a_env_flag(TWILIO_AUTH_TOKEN),
            "from_number_set": _stage43a_env_flag(TWILIO_FROM_NUMBER),
            "whatsapp_from_set": _stage43a_env_flag(TWILIO_WHATSAPP_FROM),
            "voice_sdk_ready": bool(TWILIO_ACCOUNT_SID and TWILIO_API_KEY_SID and TWILIO_API_KEY_SECRET and TWILIO_TWIML_APP_SID),
        },
        "google": {
            "service_account_json_set": _stage43a_env_flag(GOOGLE_SERVICE_ACCOUNT_JSON),
            "oauth_ready": bool(oauth_ready()),
            "calendar_id_fallback_set": _stage43a_env_flag(GOOGLE_CALENDAR_ID_FALLBACK),
            "oauth_redirect_uri_set": _stage43a_env_flag(GOOGLE_OAUTH_REDIRECT_URI),
        },
        "tts": {
            "google_voice_name": GOOGLE_TTS_VOICE_NAME,
            "google_language_code": GOOGLE_TTS_LANGUAGE_CODE,
            "elevenlabs_api_key_set": _stage43a_env_flag(ELEVENLABS_API_KEY),
        },
    }

    tenant_status: Dict[str, Any]
    tenant: Dict[str, Any] = {}
    try:
        tenant = get_existing_tenant(requested_tenant_id)
        if tenant.get("_id"):
            tenant_status = tenant_ready_status_payload(tenant)
        else:
            tenant_status = {"tenant_id": requested_tenant_id, "ready": False, "missing": ["tenant_not_found"]}
    except Exception as e:
        log.error("stage43a_tenant_readiness_failed tenant_id=%s err=%s", requested_tenant_id, e)
        tenant_status = {"tenant_id": requested_tenant_id, "ready": False, "error": e.__class__.__name__}

    qa = {
        "protected_baseline": "50/50",
        "scenario_count": len(STAGE34_REGRESSION_TEST_MATRIX),
        "calendar_safe_mode_enabled": bool(STAGE35_CALENDAR_SAFE_MODE_ENABLED),
        "runner_endpoint": "/dialogue/qa",
        "note": "This readiness report does not run regression scenarios.",
    }

    issues: List[str] = []
    if not db_check.get("ok"):
        issues.append("database_connection_failed")
    for table_name, table_status in tables.items():
        if not table_status.get("ok"):
            issues.append(f"table_missing_or_unreadable:{table_name}")
    if not env["database_url_set"]:
        issues.append("env_missing:DATABASE_URL")
    if LLM_INTELLIGENCE_ENABLED and not env["openai_api_key_set"]:
        issues.append("env_missing:OPENAI_API_KEY")
    if TWILIO_VALIDATE_SIGNATURE and not integrations["twilio"]["auth_token_set"]:
        issues.append("env_missing:TWILIO_AUTH_TOKEN")
    if not (integrations["google"]["service_account_json_set"] or integrations["google"]["oauth_ready"]):
        issues.append("google_calendar_credentials_missing")
    if not tenant_status.get("ready"):
        issues.append("tenant_not_ready")

    status = "ok" if not issues else "degraded"
    if not db_check.get("ok"):
        status = "error"

    return {
        "status": status,
        "stage": "43A",
        "name": "Production Hardening & Readiness Checks",
        "tenant_id": requested_tenant_id,
        "timezone": str(TZ),
        "env": env,
        "database": {"connection": db_check, "tables": tables},
        "integrations": integrations,
        "tenant_readiness": tenant_status,
        "product_scope": {
            "current_mvp_channel": "text",
            "active_receptionist_mode": "text_first",
            "voice_calls_scope": "future_phase",
            "note": "Voice/TTS/Twilio readiness may exist as infrastructure, but current MVP scope is text receptionist behavior.",
        },
        "text_channel_smoke": {
            "stage": "49",
            "purpose": "manual production smoke for text-first receptionist behavior",
            "recommended_first_channel": "/dev_chat_ui",
            "covered_paths": ["booking", "price_side_question", "slot_confirmation", "reschedule", "cancel"],
            "live_calendar_required": True,
            "mutates_calendar": False,
            "note": "Readiness exposes this as checklist metadata only. This endpoint does not run smoke tests or create/update/delete calendar events.",
        },
        "client_demo_readiness": {
            "stage": "50",
            "purpose": "text-first MVP launch/demo readiness checklist",
            "status": "candidate" if status == "ok" and tenant_status.get("ready") else "blocked",
            "recommended_demo_channel": "/dev_chat_ui",
            "demo_paths": [
                "RU booking with price side-question",
                "RU reschedule same calendar event",
                "RU cancel updated booking",
                "LV booking/reschedule/cancel smoke",
            ],
            "must_show": [
                "text receptionist creates a real calendar booking",
                "side questions preserve the active booking flow",
                "reschedule updates the same event without duplicates",
                "cancel removes the active event",
            ],
            "do_not_position_as_current_scope": ["voice calls", "voice agent", "TTS demo"],
            "mutates_calendar": False,
            "note": "Readiness exposes demo checklist metadata only. The live demo itself must be run manually through a text channel.",
        },
        "tenant_admin_config": tenant_admin_config_readiness_payload(tenant) if tenant_status.get("tenant_id") else {
            "stage": "51",
            "status": "blocked",
            "tenant_id": requested_tenant_id,
            "blocking": ["tenant_not_found"],
        },
        "tenant_config_ui": tenant_config_ui_readiness_payload(tenant) if tenant_status.get("tenant_id") else {
            "stage": "52",
            "status": "blocked",
            "tenant_id": requested_tenant_id,
            "blocking": ["tenant_not_found"],
        },
        "qa": qa,
        "issues": issues,
    }


@app.get("/internal/readiness")
def internal_readiness(tenant_id: str = TENANT_ID_DEFAULT):
    return stage43a_production_readiness_payload(tenant_id=tenant_id)


# -------------------------
# TELEGRAM CHANNEL (chat-first)
# -------------------------
@app.get("/telegram/status")
def telegram_status():
    return telegram_config_status(
        default_tenant_id=os.getenv("TELEGRAM_DEFAULT_TENANT_ID", "").strip() or TENANT_ID_DEFAULT,
        server_base_url=SERVER_BASE_URL,
    )


@app.post("/telegram/set-webhook")
def telegram_set_webhook(url: str = "", tenant_id: str = ""):
    default_tenant_id = (tenant_id or os.getenv("TELEGRAM_DEFAULT_TENANT_ID", "").strip() or TENANT_ID_DEFAULT).strip()
    webhook_url = (url or "").strip()
    if not webhook_url:
        if not SERVER_BASE_URL:
            raise HTTPException(status_code=500, detail="SERVER_BASE_URL is required when url is not provided")
        webhook_url = SERVER_BASE_URL.rstrip("/") + "/telegram/webhook?tenant_id=" + default_tenant_id
    result = telegram_set_webhook_request(webhook_url)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result)
    return result


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request, tenant_id: str = ""):
    default_tenant_id = (tenant_id or os.getenv("TELEGRAM_DEFAULT_TENANT_ID", "").strip() or TENANT_ID_DEFAULT).strip()
    return await handle_telegram_incoming(
        request=request,
        default_tenant_id=default_tenant_id,
        get_tenant=get_tenant,
        tenant_is_resolved=tenant_is_resolved,
        tenant_settings_func=tenant_settings,
        handle_user_text_with_logging=handle_user_text_with_logging,
        detect_language_func=detect_language,
        unavailable_text_func=lambda lang: t(lang, "service_unavailable_text"),
    )



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

LIFECYCLE_STATUS_ALIASES = {
    "enabled": "active",
    "paid": "active",
    "live": "active",
    "due": "past_due",
    "payment_failed": "past_due",
    "paused": "inactive",
    "disabled": "inactive",
    "cancelled": "inactive",
    "canceled": "inactive",
    "expired": "expired",
}

ALLOWED_SUBSCRIPTION_STATUSES = {"trial", "active", "past_due", "inactive", "expired"}

def normalize_subscription_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    raw = LIFECYCLE_STATUS_ALIASES.get(raw, raw)
    if raw in ALLOWED_SUBSCRIPTION_STATUSES:
        return raw
    return "trial"

def normalize_tenant_saas_fields(tenant: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure SaaS lifecycle fields exist so older tenants don't break."""
    if not tenant:
        return tenant
    for k, v in SAAS_TENANT_FIELDS.items():
        if k not in tenant or tenant.get(k) is None:
            tenant[k] = v
    tenant["subscription_status"] = normalize_subscription_status(tenant.get("subscription_status"))
    tenant["plan"] = normalized_plan_name(tenant.get("plan")) if "plan" in tenant else "starter"
    return tenant

def effective_subscription_status(tenant: Dict[str, Any]) -> str:
    tenant = normalize_tenant_saas_fields(tenant or {})
    status = normalize_subscription_status(tenant.get("subscription_status"))
    if status == "trial":
        trial_end = tenant_trial_end_value(tenant)
        if trial_end and now_ts() > trial_end:
            return "expired"
    return status

def tenant_lifecycle_payload(tenant: Dict[str, Any]) -> Dict[str, Any]:
    tenant = normalize_tenant_saas_fields(tenant or {})
    trial_end = tenant_trial_end_value(tenant)
    subscription_status = normalize_subscription_status(tenant.get("subscription_status"))
    effective_status = effective_subscription_status(tenant)
    blocked = effective_status in {"inactive", "expired"}
    if effective_status == "past_due":
        blocked = False
    return {
        "subscription_status": subscription_status,
        "effective_status": effective_status,
        "trial_end": trial_end.isoformat() if hasattr(trial_end, "isoformat") else None,
        "blocked": blocked,
        "block_reason": "trial_expired" if effective_status == "expired" and subscription_status == "trial" else effective_status if blocked else None,
    }


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
        log.error(
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
        log.error(f"tenant_config_invalid tenant_id={tenant.get('id') or tenant.get('_id')} missing={missing}")
        raise Exception(f"Tenant configuration invalid: missing {missing}")

    return True


def safe_calendar_check(tenant: dict):
    try:
        if not tenant.get("calendar_id"):
            raise Exception("calendar_id missing")

        return True

    except Exception as e:
        log.error(f"calendar_config_error tenant_id={tenant.get('id')} error={e}")
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
    calendar_selected = bool(calendar_id)
    persisted_onboarding_completed = bool(tenant.get("onboarding_completed"))
    onboarding_completed = bool(persisted_onboarding_completed or (google_connected and calendar_selected))
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
        "persisted_onboarding_completed": persisted_onboarding_completed,
        "subscription_status": tenant.get("subscription_status"),
        "plan": tenant.get("plan"),
        "next_step": next_step,
    }


PLAN_ALIASES = {
    "growth": "pro",
    "enterprise": "business",
}

PLAN_CATALOG = {
    "starter": {
        "display_name": "Starter",
        "dialogs_per_month": 300,
        "llm_calls_per_month": 0,
        "llm_mode": "off",
        "includes_advanced_ai": False,
        "monthly_price": 0,
        "features": ["Basic booking flow", "Calendar integration", "SMS / WhatsApp support"],
    },
    "pro": {
        "display_name": "Pro",
        "dialogs_per_month": 1000,
        "llm_calls_per_month": 800,
        "llm_mode": "smart",
        "includes_advanced_ai": True,
        "monthly_price": 0,
        "features": ["Smarter routing", "FAQ support", "Priority SaaS limits"],
    },
    "ai": {
        "display_name": "AI",
        "dialogs_per_month": 2000,
        "llm_calls_per_month": 2500,
        "llm_mode": "full",
        "includes_advanced_ai": True,
        "monthly_price": 0,
        "features": ["Advanced LLM flows", "Higher monthly capacity", "Deeper AI coverage"],
    },
    "business": {
        "display_name": "Business",
        "dialogs_per_month": 3000,
        "llm_calls_per_month": 5000,
        "llm_mode": "full",
        "includes_advanced_ai": True,
        "monthly_price": 0,
        "features": ["High volume usage", "Multi-channel scale", "Business-grade limits"],
    },
}


def normalized_plan_name(value: Any) -> str:
    plan = str(value or "starter").strip().lower() or "starter"
    plan = PLAN_ALIASES.get(plan, plan)
    if plan not in PLAN_CATALOG:
        return "starter"
    return plan


def available_plan_catalog() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for plan_key, meta in PLAN_CATALOG.items():
        item = dict(meta)
        item["plan"] = plan_key
        out[plan_key] = item
    return out


def tenant_plan_defaults(tenant: Dict[str, Any]) -> Dict[str, Any]:
    plan = normalized_plan_name((tenant or {}).get("plan"))
    defaults = dict(PLAN_CATALOG.get(plan, PLAN_CATALOG["starter"]))
    defaults["plan"] = plan
    return defaults


def tenant_effective_dialog_limit(tenant: Dict[str, Any], defaults: Optional[Dict[str, Any]] = None) -> Tuple[int, bool]:
    defaults = dict(defaults or tenant_plan_defaults(tenant))
    raw_dialog_limit = (tenant or {}).get("dialogs_per_month")
    try:
        if raw_dialog_limit in (None, ""):
            return max(0, int(defaults.get("dialogs_per_month") or 0)), False
        return max(0, int(raw_dialog_limit or 0)), True
    except Exception:
        return max(0, int(defaults.get("dialogs_per_month") or 0)), False


def tenant_plan_meta(tenant: Dict[str, Any]) -> Dict[str, Any]:
    tenant = normalize_tenant_saas_fields(tenant or {})
    plan = normalized_plan_name(tenant.get("plan"))
    defaults = tenant_plan_defaults(tenant)
    dialog_limit, has_override = tenant_effective_dialog_limit(tenant, defaults)
    defaults["dialogs_per_month"] = dialog_limit
    tenant_id = str(tenant.get("_id") or tenant.get("id") or "").strip()
    current_month_usage = tenant_dialog_usage_current_month(tenant_id) if tenant_id else 0
    return {
        "plan": plan,
        "display_name": defaults.get("display_name") or plan.title(),
        "subscription_status": normalize_subscription_status(tenant.get("subscription_status")),
        "effective_status": effective_subscription_status(tenant),
        "status": tenant_status_value(tenant),
        "monthly_price": defaults.get("monthly_price", 0),
        "features": list(defaults.get("features") or []),
        "limits": defaults,
        "limits_source": "tenant_override" if has_override else "plan_default",
        "override_dialogs_per_month": dialog_limit if has_override else None,
        "usage": {
            "dialogs_current_month": current_month_usage,
            "dialogs_per_month": dialog_limit,
            "dialogs_remaining": max(0, dialog_limit - current_month_usage) if dialog_limit > 0 else 0,
        },
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


def _stage51_has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _stage51_json_field_status(value: Any, expected_type: Optional[str] = None) -> Dict[str, Any]:
    """Read-only admin validation for JSON-like tenant config fields.

    Stage 51 intentionally does not reject existing config values. This helper only
    reports whether editable admin fields are syntactically safe for a non-technical
    tenant/admin surface.
    """
    if value is None:
        return {"present": False, "valid": True, "status": "missing"}
    if isinstance(value, str) and not value.strip():
        return {"present": False, "valid": True, "status": "missing"}

    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {"present": True, "valid": False, "status": "invalid_json"}

    actual_type = "list" if isinstance(parsed, list) else "dict" if isinstance(parsed, dict) else type(parsed).__name__
    if expected_type == "list" and not isinstance(parsed, list):
        return {"present": True, "valid": False, "status": "wrong_type", "expected_type": "list", "actual_type": actual_type}
    if expected_type == "dict" and not isinstance(parsed, dict):
        return {"present": True, "valid": False, "status": "wrong_type", "expected_type": "dict", "actual_type": actual_type}
    return {"present": True, "valid": True, "status": "ok", "type": actual_type}


def _stage51_service_catalog_source(tenant: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    for key in ("service_catalog", "services_catalog", "service_catalog_json", "services_json"):
        catalog = parse_service_catalog((tenant or {}).get(key))
        if catalog:
            return key, catalog
    env_catalog = parse_service_catalog(os.getenv("BIZ_SERVICE_CATALOG", "").strip())
    if env_catalog:
        return "env:BIZ_SERVICE_CATALOG", env_catalog
    return "fallback:services_by_language", fallback_service_catalog(tenant or {})


def tenant_admin_config_readiness_payload(tenant: Dict[str, Any]) -> Dict[str, Any]:
    """Read-only SaaS/admin readiness for tenant config and business memory.

    This is not used by runtime booking logic and must not mutate tenant data.
    It exists to make Stage 51 admin gaps explicit before building a fuller client
    dashboard/editor.
    """
    tenant = normalize_tenant_saas_fields(tenant or {})
    tenant_id = str(tenant.get("_id") or tenant.get("id") or "").strip()
    service_catalog_source, catalog = _stage51_service_catalog_source(tenant)
    runtime_missing = tenant_runtime_missing_items(tenant)

    json_checks = {
        "service_catalog_json": _stage51_json_field_status(tenant.get("service_catalog_json") or tenant.get("service_catalog"), "list"),
        "weekly_hours_json": _stage51_json_field_status(tenant.get("weekly_hours_json"), "dict"),
        "days_off_json": _stage51_json_field_status(tenant.get("days_off_json")),
        "breaks_json": _stage51_json_field_status(tenant.get("breaks_json")),
        "holidays_json": _stage51_json_field_status(tenant.get("holidays_json")),
    }

    business_memory = {
        "lv": {"configured": _stage51_has_text(tenant.get("business_memory_lv")), "chars": len(str(tenant.get("business_memory_lv") or ""))},
        "ru": {"configured": _stage51_has_text(tenant.get("business_memory_ru")), "chars": len(str(tenant.get("business_memory_ru") or ""))},
        "en": {"configured": _stage51_has_text(tenant.get("business_memory_en")), "chars": len(str(tenant.get("business_memory_en") or ""))},
    }

    warnings: List[str] = []
    for field, check in json_checks.items():
        if not check.get("valid", True):
            warnings.append(f"invalid_json:{field}")
    if service_catalog_source.startswith("fallback:"):
        warnings.append("service_catalog_uses_language_fallback")
    for lang_key, item in business_memory.items():
        if not item.get("configured"):
            warnings.append(f"business_memory_{lang_key}_missing")

    blocking = list(runtime_missing)
    for field, check in json_checks.items():
        if check.get("present") and not check.get("valid"):
            blocking.append(f"invalid_json:{field}")

    status = "ready" if not blocking and not warnings else "attention" if not blocking else "blocked"

    return {
        "stage": "51",
        "purpose": "tenant config and business memory admin readiness",
        "tenant_id": tenant_id or None,
        "status": status,
        "safe_to_demo": not blocking,
        "runtime_missing": runtime_missing,
        "blocking": blocking,
        "warnings": warnings,
        "editable_surfaces": {
            "config_ui": f"/tenant/config/ui?tenant_id={tenant_id}" if tenant_id else None,
            "config_json": f"/tenant/config?tenant_id={tenant_id}" if tenant_id else None,
            "config_update": "/tenant/config/update",
            "admin_readiness": f"/tenant/admin/readiness?tenant_id={tenant_id}" if tenant_id else None,
        },
        "business_identity": {
            "business_name_configured": _stage51_has_text(tenant.get("business_name")),
            "timezone_configured": _stage51_has_text(tenant.get("timezone")),
            "language": get_lang(tenant.get("language") or "lv"),
        },
        "calendar": {
            "google_connected": tenant_google_connected_effective(tenant),
            "calendar_selected": _stage51_has_text(tenant.get("calendar_id")),
            "has_service_account_json": tenant_has_service_account_json(tenant),
        },
        "business_hours": {
            "work_start": tenant.get("work_start"),
            "work_end": tenant.get("work_end"),
            "weekly_hours_json": json_checks["weekly_hours_json"],
            "days_off_json": json_checks["days_off_json"],
            "breaks_json": json_checks["breaks_json"],
            "holidays_json": json_checks["holidays_json"],
        },
        "service_catalog": {
            "source": service_catalog_source,
            "count": len(catalog),
            "json_check": json_checks["service_catalog_json"],
            "sample_keys": [str(item.get("key") or "").strip() for item in catalog[:5] if str(item.get("key") or "").strip()],
        },
        "business_memory": business_memory,
        "note": "Readiness metadata only. This endpoint does not call LLMs, change tenant config, mutate conversations, or create/update/delete calendar events.",
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
        "lifecycle": tenant_lifecycle_payload(tenant),
        "access": tenant_access_decision(tenant),
        "available_plans": list(available_plan_catalog().values()),
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
    tenant = get_tenant(tenant_id)
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
        "plan_meta": tenant_plan_meta(tenant),
        "effective_dialogs_limit": tenant_dialog_limit(tenant),
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
          <div class="card"><div>Dialogs limit</div><div id="m_limit_dialogs" class="num">-</div><div id="m_limit_source" class="sub">Monthly cap by plan</div></div>
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
  const limitSource = planMeta?.limits_source || 'plan_default';
  const limitSourceText = limitSource === 'tenant_override' ? 'Custom limit override' : 'Monthly cap by plan';
  setText('m_limit_source', limitSourceText, 'Monthly cap by plan');
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
    tenant_id_json = json.dumps(tenant_id, ensure_ascii=False)
    html = """
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Repliq Tenant Config</title>
<style>
:root { --bg:#f6f7fb; --card:#fff; --text:#111827; --muted:#6b7280; --line:#e5e7eb; --soft:#f9fafb; --brand:#111827; --ok:#065f46; --okbg:#ecfdf5; --warn:#92400e; --warnbg:#fffbeb; --err:#991b1b; --errbg:#fef2f2; }
* { box-sizing:border-box; }
body { font-family: Inter, Arial, sans-serif; background:var(--bg); color:var(--text); margin:0; padding:24px; }
.wrap { max-width: 1180px; margin:0 auto; }
.card { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:20px; margin-bottom:18px; box-shadow:0 10px 28px rgba(15,23,42,.055); }
.hero { display:flex; gap:16px; align-items:flex-start; justify-content:space-between; flex-wrap:wrap; }
h1,h2,h3 { margin:0; }
h1 { font-size:32px; letter-spacing:-.03em; }
h2 { font-size:22px; margin-bottom:14px; }
h3 { font-size:16px; margin-bottom:10px; }
.sub { color:var(--muted); font-size:14px; margin-top:6px; line-height:1.45; }
.grid { display:grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap:14px 16px; }
.grid3 { display:grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap:12px; }
.full { grid-column:1/-1; }
label { display:flex; justify-content:space-between; gap:8px; font-size:13px; margin-bottom:6px; color:#374151; font-weight:650; }
.hint { color:var(--muted); font-size:12px; font-weight:400; }
input,select,textarea { width:100%; border:1px solid #d1d5db; border-radius:12px; padding:11px 12px; background:#fff; color:#111827; font:14px/1.4 Arial, sans-serif; }
textarea { min-height:92px; resize:vertical; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
textarea.big { min-height:170px; }
button { border:0; background:var(--brand); color:#fff; padding:11px 16px; border-radius:12px; cursor:pointer; font-weight:700; }
button.secondary { background:#fff; color:#111827; border:1px solid #d1d5db; }
button.ghost { background:#f3f4f6; color:#111827; }
button:disabled { opacity:.55; cursor:not-allowed; }
.actions { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
.badge { display:inline-flex; align-items:center; gap:6px; padding:5px 9px; border-radius:999px; border:1px solid var(--line); background:var(--soft); font-size:12px; font-weight:700; }
.badge.ok { color:var(--ok); background:var(--okbg); border-color:#a7f3d0; }
.badge.warn { color:var(--warn); background:var(--warnbg); border-color:#fde68a; }
.badge.err { color:var(--err); background:var(--errbg); border-color:#fecaca; }
.status-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:16px; }
.status-card { background:var(--soft); border:1px solid var(--line); border-radius:14px; padding:12px; min-height:74px; }
.status-card .label { color:var(--muted); font-size:12px; margin-bottom:6px; }
.status-card .value { font-weight:800; }
.small { font-size:12px; color:var(--muted); }
.notice { border-radius:14px; padding:12px 14px; margin-top:12px; font-size:13px; line-height:1.45; }
.notice.ok { background:var(--okbg); color:#064e3b; border:1px solid #a7f3d0; }
.notice.warn { background:var(--warnbg); color:#78350f; border:1px solid #fde68a; }
.notice.err { background:var(--errbg); color:#7f1d1d; border:1px solid #fecaca; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th,td { text-align:left; border-bottom:1px solid var(--line); padding:9px 8px; vertical-align:top; }
th { color:#374151; background:#fafafa; }
.preview-empty { color:var(--muted); border:1px dashed #d1d5db; border-radius:12px; padding:12px; }
details { border:1px solid var(--line); border-radius:14px; padding:12px 14px; background:#fff; }
details + details { margin-top:12px; }
summary { cursor:pointer; font-weight:800; }
.links a { display:inline-block; margin:6px 10px 0 0; color:#1d4ed8; text-decoration:none; }
.links a:hover { text-decoration:underline; }
.secret-box { background:#f8fafc; border:1px solid #cbd5e1; border-radius:12px; padding:12px; }
.sticky-save { position:sticky; bottom:0; z-index:5; background:rgba(246,247,251,.9); backdrop-filter:blur(8px); padding:12px 0; }
@media (max-width: 850px) { .grid,.grid3,.status-grid { grid-template-columns:1fr; } body { padding:12px; } }
</style>
</head>
<body>
<div class="wrap">
  <div class="card hero">
    <div>
      <h1>Repliq Tenant Config</h1>
      <div class="sub">Demo-safe editor for the current text-first receptionist MVP. Voice/calls are future scope.</div>
      <div class="actions" style="margin-top:14px;">
        <input id="tenant_id" style="min-width:280px; max-width:420px;" />
        <button onclick="loadConfig()">Load</button>
        <button class="secondary" onclick="openPath('/dashboard?tenant_id='+encodeURIComponent(currentTenant()))">Dashboard</button>
        <button class="secondary" onclick="openPath('/dev_chat_ui?tenant_id='+encodeURIComponent(currentTenant()))">Dev chat</button>
      </div>
    </div>
    <div style="min-width:260px;">
      <div id="ready_badge" class="badge warn">Loading readiness…</div>
      <div id="scope_badge" class="badge ok" style="margin-left:6px;">Text MVP</div>
      <div class="sub">Settings are saved via <code>POST /tenant/config/update</code>. Secrets are not displayed by this UI.</div>
    </div>
  </div>

  <div class="card">
    <h2>Demo readiness</h2>
    <div class="status-grid">
      <div class="status-card"><div class="label">Admin status</div><div id="st_admin" class="value">—</div></div>
      <div class="status-card"><div class="label">Google Calendar</div><div id="st_calendar" class="value">—</div></div>
      <div class="status-card"><div class="label">Service catalog</div><div id="st_catalog" class="value">—</div></div>
      <div class="status-card"><div class="label">Business memory</div><div id="st_memory" class="value">—</div></div>
    </div>
    <div id="readiness_notice" class="notice warn">Loading tenant readiness…</div>
  </div>

  <div class="card">
    <h2>Basic business settings</h2>
    <div class="grid">
      <div><label>Business name <span class="hint">shown in dashboard/demo</span></label><input id="business_name"/></div>
      <div><label>Phone number <span class="hint">optional route</span></label><input id="phone_number"/></div>
      <div><label>Timezone</label><input id="timezone" placeholder="Europe/Riga"/></div>
      <div><label>Primary language</label><select id="language"><option value="lv">Latvian (lv)</option><option value="ru">Russian (ru)</option><option value="en">English (en)</option></select></div>
      <div><label>Work start</label><input id="work_start" placeholder="09:00"/></div>
      <div><label>Work end</label><input id="work_end" placeholder="18:00"/></div>
      <div><label>Min notice minutes <span class="hint">optional</span></label><input id="min_notice_minutes" type="number" min="0"/></div>
      <div><label>Buffer minutes <span class="hint">optional</span></label><input id="buffer_minutes" type="number" min="0"/></div>
    </div>
  </div>

  <div class="card">
    <h2>Client-facing services</h2>
    <div class="grid">
      <div><label>Services LV <span class="hint">comma-separated</span></label><textarea id="services_lv"></textarea></div>
      <div><label>Services RU <span class="hint">comma-separated</span></label><textarea id="services_ru"></textarea></div>
      <div class="full"><label>Services EN <span class="hint">comma-separated</span></label><textarea id="services_en"></textarea></div>
    </div>
    <h3 style="margin-top:16px;">Service catalog preview</h3>
    <div id="service_preview" class="preview-empty">Load config to preview services.</div>
  </div>

  <div class="card">
    <h2>Business memory / FAQ text</h2>
    <div class="sub" style="margin-bottom:12px;">Simple lines like “Consultation - 10 euro”, address, working rules, or FAQ facts. This is what side-questions use during booking.</div>
    <div class="grid">
      <div><label>Business memory LV</label><textarea id="business_memory_lv" placeholder="Konsultācija - 10 eiro\nServiss - 20 eiro\nAdrese: Rēzekne"></textarea></div>
      <div><label>Business memory RU</label><textarea id="business_memory_ru" placeholder="Консультация - 10 евро\nСервис - 20 евро\nАдрес: Резекне"></textarea></div>
      <div class="full"><label>Business memory EN</label><textarea id="business_memory_en" placeholder="Consultation - 10 euro\nService - 20 euro\nAddress: Rezekne"></textarea></div>
    </div>
  </div>

  <div class="card">
    <h2>Advanced settings</h2>
    <details>
      <summary>Service catalog JSON</summary>
      <div class="sub">Advanced structured service list. Used for matching services and durations. Keep valid JSON.</div>
      <textarea class="big" id="service_catalog_json" placeholder='[{"key":"consultation","name_lv":"konsultācija","name_ru":"консультация","name_en":"consultation","duration_min":30}]'></textarea>
    </details>
    <details>
      <summary>Optional schedule JSON</summary>
      <div class="grid" style="margin-top:12px;">
        <div><label>Weekly hours JSON <span class="hint">optional</span></label><textarea id="weekly_hours_json" placeholder='{"mon":["09:00","18:00"]}'></textarea></div>
        <div><label>Days off JSON <span class="hint">optional</span></label><textarea id="days_off_json" placeholder='[]'></textarea></div>
        <div><label>Breaks JSON <span class="hint">optional</span></label><textarea id="breaks_json" placeholder='{"mon":[]}'></textarea></div>
        <div><label>Holidays JSON <span class="hint">optional</span></label><textarea id="holidays_json" placeholder='[]'></textarea></div>
      </div>
    </details>
    <details>
      <summary>Google service account</summary>
      <div class="secret-box" style="margin-top:12px;">
        <div id="service_account_status" class="badge warn">Checking…</div>
        <div class="sub">For safety, existing service account JSON is not displayed. Paste a new JSON here only if you intentionally want to replace it. Leave empty to keep current credentials.</div>
        <textarea id="service_account_json" placeholder='Paste new service account JSON only to replace existing credentials'></textarea>
      </div>
    </details>
  </div>

  <div class="sticky-save">
    <div class="card" style="margin-bottom:0;">
      <div class="actions">
        <button onclick="saveConfig()">Save config</button>
        <button class="secondary" onclick="loadConfig()">Reload</button>
        <span id="save_status" class="small"></span>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Quick links</h2>
    <div class="links">
      <a id="lnk_json" href="#">Safe JSON config</a>
      <a id="lnk_admin" href="#">Admin readiness</a>
      <a id="lnk_dashboard" href="#">Dashboard</a>
      <a id="lnk_devchat" href="#">Dev chat</a>
      <a id="lnk_routes" href="#">Phone routes</a>
      <a id="lnk_bookings" href="#">Bookings</a>
      <a id="lnk_conv" href="#">Conversations</a>
      <a id="lnk_analytics" href="#">Analytics</a>
    </div>
  </div>
</div>
<script>
const DEFAULT_TENANT_ID = __TENANT_ID_JSON__;
let lastConfig = null;
function currentTenant(){ return (document.getElementById('tenant_id').value || '').trim() || DEFAULT_TENANT_ID || 'default'; }
function openPath(path){ window.location = path; }
function esc(v){ return v === null || v === undefined ? '' : String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'", '&#39;'); }
function j(v){ if(v===null || v===undefined || v==='') return ''; if(typeof v==='string') return v; return JSON.stringify(v,null,2); }
function badgeText(ok, labelOk, labelBad){ return `<span class="badge ${ok ? 'ok':'warn'}">${esc(ok ? labelOk : labelBad)}</span>`; }
function setLinks(tid){
  document.getElementById('lnk_json').href = '/tenant/config?tenant_id=' + encodeURIComponent(tid);
  document.getElementById('lnk_admin').href = '/tenant/admin/readiness?tenant_id=' + encodeURIComponent(tid);
  document.getElementById('lnk_dashboard').href = '/dashboard?tenant_id=' + encodeURIComponent(tid);
  document.getElementById('lnk_devchat').href = '/dev_chat_ui?tenant_id=' + encodeURIComponent(tid);
  document.getElementById('lnk_routes').href = '/tenant/routes?tenant_id=' + encodeURIComponent(tid);
  document.getElementById('lnk_bookings').href = '/bookings?tenant_id=' + encodeURIComponent(tid);
  document.getElementById('lnk_conv').href = '/conversations?tenant_id=' + encodeURIComponent(tid);
  document.getElementById('lnk_analytics').href = '/analytics?tenant_id=' + encodeURIComponent(tid);
}
function parseJsonField(id, label){
  const raw = document.getElementById(id).value.trim();
  if(!raw) return null;
  try { JSON.parse(raw); return raw; }
  catch(e){ throw new Error(`${label}: invalid JSON (${e.message})`); }
}
function renderReadiness(admin){
  admin = admin || {};
  const ready = admin.safe_to_demo === true || admin.status === 'ready';
  document.getElementById('ready_badge').className = 'badge ' + (ready ? 'ok' : 'warn');
  document.getElementById('ready_badge').textContent = ready ? 'Ready for demo' : 'Needs attention';
  document.getElementById('st_admin').innerHTML = badgeText(ready, 'Ready', 'Attention');
  const cal = admin.calendar || {};
  document.getElementById('st_calendar').innerHTML = badgeText(!!(cal.google_connected && cal.calendar_selected), 'Connected', 'Check setup');
  const cat = admin.service_catalog || {};
  document.getElementById('st_catalog').innerHTML = `${badgeText((cat.count || 0) > 0, `${cat.count || 0} services`, 'Missing')}<div class="small">${esc(cat.source || '')}</div>`;
  const bm = admin.business_memory || {};
  const memOk = !!(bm.lv?.configured && bm.ru?.configured && bm.en?.configured);
  document.getElementById('st_memory').innerHTML = badgeText(memOk, 'LV/RU/EN ready', 'Check languages');
  const blocking = Array.isArray(admin.blocking) ? admin.blocking : [];
  const warnings = Array.isArray(admin.warnings) ? admin.warnings : [];
  const notice = document.getElementById('readiness_notice');
  if(blocking.length){ notice.className='notice err'; notice.textContent='Blocking: '+blocking.join(', '); }
  else if(warnings.length){ notice.className='notice warn'; notice.textContent='Warnings: '+warnings.join(', '); }
  else { notice.className='notice ok'; notice.textContent='Tenant config is safe to demo. Optional weekly hours/days off/breaks/holidays may remain empty for the MVP.'; }
  document.getElementById('service_account_status').className = 'badge ' + (cal.has_service_account_json ? 'ok' : 'warn');
  document.getElementById('service_account_status').textContent = cal.has_service_account_json ? 'Service account configured' : 'Service account missing';
}
function renderServicePreview(value){
  const box = document.getElementById('service_preview');
  let parsed = value;
  if(typeof value === 'string' && value.trim()){
    try { parsed = JSON.parse(value); } catch(e){ box.className='notice warn'; box.textContent='Service catalog JSON is invalid; preview unavailable.'; return; }
  }
  if(!Array.isArray(parsed) || !parsed.length){ box.className='preview-empty'; box.textContent='No structured services found.'; return; }
  box.className='';
  const rows = parsed.map(item => `<tr><td><code>${esc(item.key || '')}</code></td><td>${esc(item.name_lv || item.name || '')}</td><td>${esc(item.name_ru || item.name || '')}</td><td>${esc(item.name_en || item.name || '')}</td><td>${esc(item.duration_min || '')} min</td></tr>`).join('');
  box.innerHTML = `<table><thead><tr><th>Key</th><th>LV</th><th>RU</th><th>EN</th><th>Duration</th></tr></thead><tbody>${rows}</tbody></table>`;
}
async function loadConfig(){
  const tid = currentTenant();
  document.getElementById('tenant_id').value = tid;
  setLinks(tid);
  const st = document.getElementById('save_status');
  st.className='small'; st.textContent='Loading…';
  const r = await fetch('/tenant/config?tenant_id=' + encodeURIComponent(tid));
  const data = await r.json();
  if(!r.ok){ st.className='small err'; st.textContent = data.detail || JSON.stringify(data); return; }
  lastConfig = data;
  const t = data.tenant || {};
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
  const catalogValue = t.service_catalog_json || t.service_catalog;
  document.getElementById('service_catalog_json').value = j(catalogValue);
  document.getElementById('service_account_json').value = '';
  document.getElementById('business_memory_lv').value = t.business_memory_lv || '';
  document.getElementById('business_memory_ru').value = t.business_memory_ru || '';
  document.getElementById('business_memory_en').value = t.business_memory_en || '';
  renderReadiness(data.admin_readiness || {});
  renderServicePreview(catalogValue);
  st.className='small ok'; st.textContent='Loaded safe config. Existing secrets are hidden.';
}
async function saveConfig(){
  const st = document.getElementById('save_status');
  try{
    const tid = currentTenant();
    const serviceAccountReplacement = document.getElementById('service_account_json').value.trim();
    const payload = {
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
      weekly_hours_json: parseJsonField('weekly_hours_json','Weekly hours JSON'),
      days_off_json: parseJsonField('days_off_json','Days off JSON'),
      breaks_json: parseJsonField('breaks_json','Breaks JSON'),
      holidays_json: parseJsonField('holidays_json','Holidays JSON'),
      min_notice_minutes: document.getElementById('min_notice_minutes').value ? Number(document.getElementById('min_notice_minutes').value) : null,
      buffer_minutes: document.getElementById('buffer_minutes').value ? Number(document.getElementById('buffer_minutes').value) : null,
      service_catalog_json: parseJsonField('service_catalog_json','Service catalog JSON'),
      service_account_json: serviceAccountReplacement || null,
      business_memory_lv: document.getElementById('business_memory_lv').value || null,
      business_memory_ru: document.getElementById('business_memory_ru').value || null,
      business_memory_en: document.getElementById('business_memory_en').value || null
    };
    if(serviceAccountReplacement){ JSON.parse(serviceAccountReplacement); }
    st.className='small'; st.textContent='Saving…';
    const r = await fetch('/tenant/config/update', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
    const data = await r.json();
    if(!r.ok){ throw new Error(data.detail || JSON.stringify(data)); }
    st.className='small ok'; st.textContent='Saved. Reloading safe config…';
    await loadConfig();
  } catch(e){
    st.className='small err'; st.textContent = e.message || String(e);
  }
}
document.addEventListener('DOMContentLoaded', () => { document.getElementById('tenant_id').value = DEFAULT_TENANT_ID || 'clinic_demo'; loadConfig(); });
</script>
</body>
</html>
    """.replace("__TENANT_ID_JSON__", tenant_id_json)
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
    plan: Optional[str] = None
    subscription_status: Optional[str] = None
    dialogs_per_month: Optional[int] = None
    reset_override: bool = False


class TenantPlanChangeRequest(BaseModel):
    tenant_id: str
    plan: str
    subscription_status: Optional[str] = None
    dialogs_per_month: Optional[int] = None
    reset_override: bool = False

TENANT_CONFIG_SECRET_FIELDS = {
    "service_account_json",
    "google_service_account_json",
    "google_oauth_tokens_json",
    "google_refresh_token",
    "private_key",
    "client_secret",
}


def _jsonable_tenant_view(tenant: Dict[str, Any], include_secrets: bool = False) -> Dict[str, Any]:
    tenant = dict(tenant or {})
    for k, v in list(tenant.items()):
        if hasattr(v, "isoformat"):
            tenant[k] = v.isoformat()
    if not include_secrets:
        for key in TENANT_CONFIG_SECRET_FIELDS:
            if key in tenant:
                tenant[f"{key}_configured"] = bool(str(tenant.get(key) or "").strip())
                tenant[key] = None
    return tenant


def _safe_resolved_settings_view(settings: Dict[str, Any]) -> Dict[str, Any]:
    settings = dict(settings or {})
    if "service_account_json" in settings:
        settings["service_account_json_configured"] = bool(str(settings.get("service_account_json") or "").strip())
        settings["service_account_json"] = None
    return settings


def tenant_config_ui_readiness_payload(tenant: Dict[str, Any]) -> Dict[str, Any]:
    tenant = normalize_tenant_saas_fields(tenant or {})
    tenant_id = str(tenant.get("_id") or tenant.get("id") or "").strip()
    admin = tenant_admin_config_readiness_payload(tenant)
    return {
        "stage": "52",
        "purpose": "demo-safe tenant config UI and admin UX hardening",
        "tenant_id": tenant_id or None,
        "status": "ready" if admin.get("safe_to_demo") else "attention",
        "safe_to_demo": bool(admin.get("safe_to_demo")),
        "recommended_ui": f"/tenant/config/ui?tenant_id={tenant_id}" if tenant_id else None,
        "admin_readiness": f"/tenant/admin/readiness?tenant_id={tenant_id}" if tenant_id else None,
        "secrets_exposed_by_config_api": False,
        "service_account_editing": "paste_to_replace_only",
        "advanced_json_collapsed_by_default": True,
        "client_friendly_sections": [
            "demo_status",
            "basic_business_settings",
            "service_preview",
            "business_memory",
            "advanced_json_settings",
        ],
        "note": "Readiness metadata only. The UI is demo-safe by default and does not expose tenant secrets in /tenant/config responses.",
    }

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
            "effective_status": effective_subscription_status(tenant_item),
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
    tr.innerHTML = `<td><strong>${{esc(item.business_name || item.tenant_id)}}</strong>${{missing}}</td><td><code>${{esc(item.tenant_id)}}</code></td><td>${{ready}}</td><td>${{google}}</td><td>${{cal}}</td><td>${{esc(item.plan || 'starter')}}<div class="small">${{esc(item.effective_status || item.subscription_status || 'trial')}}</div></td><td><span class="small">${{esc(item.updated_at || '')}}</span></td><td class="actions"><a href="/dashboard?tenant_id=${{encodeURIComponent(item.tenant_id)}}">dashboard</a><a href="/tenant/config/ui?tenant_id=${{encodeURIComponent(item.tenant_id)}}">config</a><a href="/tenant/overview?tenant_id=${{encodeURIComponent(item.tenant_id)}}">overview</a></td>`;
    tb.appendChild(tr);
  }});
}}
document.addEventListener('DOMContentLoaded', loadTenants);
</script>
</body>
</html>
    """
    return HTMLResponse(content=html)


@app.get("/plans")
def list_plans():
    return {"items": list(available_plan_catalog().values())}


@app.post("/tenant/change_plan")
def tenant_change_plan(payload: TenantPlanChangeRequest):
    tenant_id = (payload.tenant_id or "").strip()
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id required")
    get_tenant_or_404(tenant_id)
    plan = normalized_plan_name(payload.plan)
    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = {c["name"] for c in cols}
    updates = []
    params: Dict[str, Any] = {"tid": tenant_id}
    if "plan" in col_names:
        updates.append("plan=:plan")
        params["plan"] = plan
    if payload.subscription_status is not None and "subscription_status" in col_names:
        sub_status = normalize_subscription_status(payload.subscription_status)
        if sub_status:
            updates.append("subscription_status=:subscription_status")
            params["subscription_status"] = sub_status
    if payload.reset_override and "dialogs_per_month" in col_names:
        updates.append("dialogs_per_month=NULL")
    elif payload.dialogs_per_month is not None and "dialogs_per_month" in col_names:
        updates.append("dialogs_per_month=:dialogs_per_month")
        params["dialogs_per_month"] = max(0, int(payload.dialogs_per_month))
    if "updated_at" in col_names:
        updates.append("updated_at=NOW()")
    if not updates:
        raise HTTPException(status_code=500, detail="No writable tenant fields available")
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE tenants SET {', '.join(updates)} WHERE {pk}=:tid"), params)
    updated = get_tenant_or_404(tenant_id)
    return {
        "status": "ok",
        "tenant_id": tenant_id,
        "plan": updated.get("plan"),
        "plan_meta": tenant_plan_meta(updated),
        "billing": tenant_billing_status(updated),
    }


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
        "resolved_settings": _safe_resolved_settings_view(settings),
        "phone_routes": routes,
        "onboarding": onboarding_status_payload(tenant),
        "readiness": tenant_ready_status_payload(tenant),
        "admin_readiness": tenant_admin_config_readiness_payload(tenant),
        "config_ui_hardening": tenant_config_ui_readiness_payload(tenant),
        "plan_meta": tenant_plan_meta(tenant),
        "links": onboarding_links_payload(str(tenant.get("_id") or tenant_id)),
    }


@app.get("/tenant/admin/readiness")
def tenant_admin_readiness(tenant_id: str = TENANT_ID_DEFAULT):
    tenant = get_tenant_or_404((tenant_id or "").strip() or TENANT_ID_DEFAULT)
    return tenant_admin_config_readiness_payload(tenant)


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
    if payload.plan is not None and "plan" in col_names:
        add_field("plan", normalized_plan_name(payload.plan))
    if payload.subscription_status is not None and "subscription_status" in col_names:
        sub_status = normalize_subscription_status(payload.subscription_status)
        add_field("subscription_status", sub_status)
    if payload.reset_override and "dialogs_per_month" in col_names:
        updates.append("dialogs_per_month=NULL")
    elif payload.dialogs_per_month is not None and "dialogs_per_month" in col_names:
        add_field("dialogs_per_month", max(0, int(payload.dialogs_per_month)))
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
        "resolved_settings": _safe_resolved_settings_view(tenant_settings(updated, get_lang(updated.get("language") or "lv"))),
        "onboarding": onboarding_status_payload(updated),
        "readiness": tenant_ready_status_payload(updated),
        "admin_readiness": tenant_admin_config_readiness_payload(updated),
        "config_ui_hardening": tenant_config_ui_readiness_payload(updated),
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
            source="dev_ui",
        )
        conv = db_get_or_create_conversation(req.tenant_id, raw_user, req.lang)
        orch_debug = None
        try:
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
            llm_hint = llm_message_understanding(req.message, lang, settings, service_catalog, service_aliases, business_memory) if (req.message or '').strip() else {}
            understanding = build_understanding_result(req.message, lang, conv, conv.get("pending") or {}, llm_hint, tenant, settings, service_catalog, service_aliases, business_memory)
            orch_debug = orchestrate_turn(conv, req.message, lang, understanding)
        except Exception:
            orch_debug = None
        return {
            "status": result.get("status"),
            "reply": result.get("msg_out") or result.get("reply_voice") or "",
            "lang": result.get("lang"),
            "state": conv.get("state"),
            "pending": conv.get("pending"),
            "service": conv.get("service"),
            "datetime_iso": conv.get("datetime_iso"),
            "name": conv.get("name"),
            "orchestration": orch_debug,
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
            source="dev_ui",
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



@app.get("/dialogue/audit")
def dialogue_audit(tenant_id: str = TENANT_ID_DEFAULT, limit: int = 50):
    return dialogue_audit_summary(tenant_id, limit)


@app.get("/dev/dialogue-test-matrix")
def dev_dialogue_test_matrix():
    return {
        "count": len(DIALOGUE_TEST_MATRIX),
        "categories": sorted(set(str(x.get("category")) for x in DIALOGUE_TEST_MATRIX)),
        "scenarios": DIALOGUE_TEST_MATRIX,
    }


@app.get("/dev/dialogue-trace")
def dev_dialogue_trace(tenant_id: str = TENANT_ID_DEFAULT, limit: int = 30):
    return dialogue_audit_summary(tenant_id, limit)


@app.post("/dev/dialogue-simulate")
def dev_dialogue_simulate(payload: dict = Body(...)):
    tenant_id = str(payload.get("tenant_id") or TENANT_ID_DEFAULT).strip()
    user_id = str(payload.get("user_id") or f"sim_{uuid.uuid4().hex[:8]}").strip()
    lang = get_lang(payload.get("lang") or "lv")
    messages = payload.get("messages") or []
    if isinstance(messages, str):
        messages = [messages]
    out = []
    for msg in messages[:20]:
        result = handle_user_text_with_logging(tenant_id, user_id, str(msg), "dev", lang, source="dialogue_simulate")
        out.append({"user": str(msg), "assistant": result.get("msg_out") or result.get("reply_voice"), "status": result.get("status"), "lang": result.get("lang")})
    return {"tenant_id": tenant_id, "user_id": user_id, "turns": out, "audit": dialogue_audit_summary(tenant_id, 20)}

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