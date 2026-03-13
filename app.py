
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

if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=0.1,
            environment=os.getenv("ENVIRONMENT", "production")
        )

        app.add_middleware(SentryAsgiMiddleware)
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
from datetime import datetime, timedelta, timezone, date
from typing import Dict, Any, Optional, Tuple, List

import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, StreamingResponse
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

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_VALIDATE_SIGNATURE = (
    (os.getenv("TWILIO_VALIDATE_SIGNATURE", "true") or "true").strip().lower()
    in ("1", "true", "yes", "on")
)
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()

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
        "need_service": "Kādu pakalpojumu vēlaties?",
        "need_time": "Kad un cikos jums būtu ērti?",
        "need_name": "Kā jūs sauc?",
        "closed_voice": "Šajā laikā nestrādājam. Nosūtu brīvos laikus ziņā.",
        "closed_text": "Šajā laikā nestrādājam. Varianti: 1) {opt1} 2) {opt2}",
        "busy_voice": "Šis laiks ir aizņemts. Nosūtu variantus ziņā.",
        "busy_text": "Šis laiks ir aizņemts. Varianti: 1) {opt1} 2) {opt2}",
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
        "voice_options_prompt": "Pieejami varianti: viens — {opt1}, divi — {opt2}. Kuru izvēlaties?",
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
        "need_service": "Какую услугу вы хотите?",
        "need_time": "На какую дату и время вам удобно?",
        "need_name": "Как вас зовут?",
        "closed_voice": "В это время мы не работаем. Отправляю свободные варианты сообщением.",
        "closed_text": "В это время мы не работаем. Варианты: 1) {opt1} 2) {opt2}",
        "busy_voice": "Это время занято. Отправляю варианты сообщением.",
        "busy_text": "Это время занято. Варианты: 1) {opt1} 2) {opt2}",
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
        "voice_options_prompt": "Доступны варианты: один — {opt1}, два — {opt2}. Какой выбираете?",
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
        "need_service": "Which service would you like?",
        "need_time": "What date and time would work for you?",
        "need_name": "What is your name?",
        "closed_voice": "We are closed at that time. I am sending available options by message.",
        "closed_text": "We are closed at that time. Options: 1) {opt1} 2) {opt2}",
        "busy_voice": "That time is already booked. I am sending available options by message.",
        "busy_text": "That time is busy. Options: 1) {opt1} 2) {opt2}",
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
        "voice_options_prompt": "Available options: one — {opt1}, two — {opt2}. Which do you choose?",
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
    if "updated_at" in col_names:
        sets.append("updated_at=NOW()")
    if not sets:
        return
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE tenants SET {', '.join(sets)} WHERE {pk}=:tid"), params)

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
    p = (phone or "").strip().replace("whatsapp:", "")
    p = re.sub(r"[^\d+]", "", p)
    return p or "unknown"


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
                "tt": c.get("time_text"),
                "pj": pending_json,
            },
        )



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


def tenant_settings(tenant: Dict[str, Any], lang: str) -> Dict[str, Any]:
    biz_name = str(
        tenant.get("business_name")
        or tenant.get("name")
        or BUSINESS_FALLBACK["business_name"]
    )
    addr = str(tenant.get("address") or BUSINESS_FALLBACK["address"])
    return {
        "biz_name": biz_name,
        "addr": addr,
        "services_hint": tenant_services_for_lang(tenant, lang),
        "work_start": str(tenant.get("work_start") or WORK_START_HHMM_DEFAULT),
        "work_end": str(tenant.get("work_end") or WORK_END_HHMM_DEFAULT),
        "calendar_id": resolve_tenant_calendar_id(tenant) or tenant_calendar_id(tenant),
    }


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


def channel_supports_messaging(channel: str, raw_phone: str) -> bool:
    channel = (channel or "").strip().lower()
    if channel in ("sms", "whatsapp"):
        return True
    phone = normalize_incoming_to_number(raw_phone)
    return bool(phone and looks_like_phone_number(phone))


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


def get_gcal():
    global _GCAL
    if _GCAL:
        return _GCAL
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        return None
    try:
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/calendar"]
        )
        _GCAL = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return _GCAL
    except Exception as e:
        log.error("Google Calendar init failed: %s", e)
        return None


def is_slot_busy(calendar_id: str, dt_start: datetime, dt_end: datetime) -> bool:
    svc = get_gcal()
    if not svc or not calendar_id:
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
):
    svc = get_gcal()
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
def in_business_hours(
    dt_start: datetime, duration_min: int, work_start: str, work_end: str
) -> bool:
    try:
        ws_h, ws_m = _parse_hhmm(work_start)
        we_h, we_m = _parse_hhmm(work_end)
        day_start = dt_start.replace(hour=ws_h, minute=ws_m, second=0, microsecond=0)
        day_end = dt_start.replace(hour=we_h, minute=we_m, second=0, microsecond=0)
        return (
            dt_start >= day_start
            and (dt_start + timedelta(minutes=duration_min)) <= day_end
        )
    except Exception:
        return False


def find_next_two_slots(
    calendar_id: str,
    dt_start: datetime,
    duration_min: int,
    work_start: str,
    work_end: str,
):
    step, found = 30, []
    candidate = dt_start + timedelta(minutes=step)
    for _ in range(96):
        if in_business_hours(candidate, duration_min, work_start, work_end):
            if not is_slot_busy(
                calendar_id, candidate, candidate + timedelta(minutes=duration_min)
            ):
                found.append(candidate)
                if len(found) == 2:
                    return found[0], found[1]
        candidate += timedelta(minutes=step)
    return None


def find_next_event_by_phone(calendar_id: str, phone: str, tenant_id: Optional[str] = None):
    svc = get_gcal()
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


def delete_calendar_event(calendar_id: str, event_id: str):
    svc = get_gcal()
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
def parse_time_text_to_dt(text_: str) -> Optional[datetime]:
    src = (text_ or "")
    m = re.search(r"\b([01]?\d|2[0-3])[:. ]([0-5]\d)\b", src.lower())
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    base = today_local()
    t_low = src.lower()

    if any(k in t_low for k in ["parīt", "послезавтра", "day after tomorrow"]):
        base += timedelta(days=2)
    elif any(k in t_low for k in ["rīt", "rit", "завтра", "tomorrow"]):
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
    m = re.search(r"\b([01]?\d|2[0-3])[:. ]([0-5]\d)\b", src)
    if m:
        return int(m.group(1)), int(m.group(2))
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
        "rīt", "rit", "parīt", "šodien", "sodien",
        "завтра", "послезавтра", "сегодня",
        "tomorrow", "day after tomorrow", "today",
    ]
    return any(k in src for k in keywords)


def combine_date_with_explicit_time(base_iso: Optional[str], time_source: Optional[str]) -> Optional[datetime]:
    base_dt = parse_dt_any_tz((base_iso or "").strip())
    parts = parse_explicit_time_parts(time_source)
    if not base_dt or not parts:
        return None
    hh, mm = parts
    return base_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)


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
        db_save_conversation(tenant_id, user_key, c)

    lang = get_lang(c.get("lang"))
    settings = tenant_settings(tenant, lang)
    voice_like_channel = (channel or "").strip().lower() == "voice"
    service_aliases = tenant_service_aliases(tenant, lang)
    business_memory = tenant_business_memory(tenant, lang)
    calendar_ready = calendar_is_configured(settings["calendar_id"])

    if not allowed:
        return {
            "status": "blocked",
            "reply_voice": t(lang, "service_unavailable_voice"),
            "msg_out": t(lang, "service_unavailable_text"),
            "lang": lang,
        }

    t_low = msg.lower()

    if msg and is_greeting_only(msg):
        return {
            "status": "greeting",
            "reply_voice": t(lang, "greeting_only_reply"),
            "msg_out": t(lang, "greeting_only_reply"),
            "lang": lang,
        }

    if msg and is_identity_check(msg):
        return {
            "status": "identity",
            "reply_voice": t(lang, "identity_yes", biz=settings["biz_name"]),
            "msg_out": t(lang, "identity_yes", biz=settings["biz_name"]),
            "lang": lang,
        }

    if msg and is_hours_question(msg):
        return {
            "status": "info",
            "reply_voice": t(lang, "hours_info", biz=settings["biz_name"], start=settings["work_start"], end=settings["work_end"]),
            "msg_out": t(lang, "hours_info", biz=settings["biz_name"], start=settings["work_start"], end=settings["work_end"]),
            "lang": lang,
        }

    if msg and is_booking_opener(msg) and not any(w in t_low for w in ["atcelt", "отменить", "cancel", "pārcelt", "перенести", "reschedule"]):
        pending = c.get("pending") or {}
        pending["booking_intent"] = True
        c["pending"] = pending
        db_save_conversation(tenant_id, user_key, c)
        if not c.get("service"):
            return {
                "status": "need_more",
                "reply_voice": t(lang, "ask_booking_service"),
                "msg_out": t(lang, "ask_booking_service"),
                "lang": lang,
            }
        if not c.get("datetime_iso"):
            return {
                "status": "need_more",
                "reply_voice": t(lang, "ask_booking_time"),
                "msg_out": t(lang, "ask_booking_time"),
                "lang": lang,
            }

    # Intent: cancel
    if any(w in t_low for w in ["atcelt", "отменить", "cancel"]):
        if not calendar_ready:
            return blocked_result_for_lang(lang)
        ev = find_next_event_by_phone(settings["calendar_id"], raw_phone, tenant_id)
        if not ev:
            return {
                "status": "no_booking",
                "reply_voice": t(lang, "no_active_booking"),
                "msg_out": t(lang, "no_active_booking"),
                "lang": lang,
            }

        deleted = delete_calendar_event(settings["calendar_id"], ev["id"])
        if not deleted:
            return {
                "status": "cancel_failed",
                "reply_voice": t(lang, "cancel_failed"),
                "msg_out": t(lang, "cancel_failed"),
                "lang": lang,
            }

        c["pending"] = None
        c["state"] = "CANCELLED"
        c["datetime_iso"] = None
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "cancelled",
            "reply_voice": t(lang, "cancelled"),
            "msg_out": t(lang, "cancelled"),
            "lang": lang,
        }

    # Intent: reschedule
    if any(w in t_low for w in ["pārcelt", "перенести", "reschedule"]):
        if not calendar_ready:
            return blocked_result_for_lang(lang)
        ev = find_next_event_by_phone(settings["calendar_id"], raw_phone, tenant_id)
        if not ev:
            return {
                "status": "no_booking",
                "reply_voice": t(lang, "no_active_booking"),
                "msg_out": t(lang, "no_active_booking"),
                "lang": lang,
            }
        dt_old = parse_dt_any_tz(ev["start"].get("dateTime", ""))
        c["pending"] = {
            "reschedule_event_id": ev["id"],
            "reschedule_old_iso": ev["start"].get("dateTime"),
        }
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "reschedule_wait",
            "reply_voice": t(lang, "reschedule_ask", when=format_dt_short(dt_old)),
            "msg_out": t(lang, "reschedule_ask", when=format_dt_short(dt_old)),
            "lang": lang,
        }

    # If user selected one of offered options by number.
    if msg in ("1", "2") and c.get("pending") and "opt1_iso" in c["pending"]:
        p = c["pending"]
        selected_iso = p.get("opt1_iso") if msg == "1" else p.get("opt2_iso")
        dt_sel = parse_dt_any_tz(selected_iso or "")
        if not dt_sel:
            return {
                "status": "need_more",
                "reply_voice": t(lang, "need_time"),
                "msg_out": t(lang, "need_time"),
                "lang": lang,
            }

        svc_name = apply_service_aliases(p.get("service") or c.get("service") or settings["services_hint"], service_aliases) or settings["services_hint"]
        client_name = normalize_name(p.get("name") or c.get("name")) or "Client"

        if p.get("reschedule_event_id"):
            deleted = delete_calendar_event(settings["calendar_id"], p["reschedule_event_id"])
            if not deleted:
                return {
                    "status": "cancel_failed",
                    "reply_voice": t(lang, "cancel_failed"),
                    "msg_out": t(lang, "cancel_failed"),
                    "lang": lang,
                }

        create_calendar_event(
            settings["calendar_id"],
            dt_sel,
            APPT_MINUTES,
            f"{settings['biz_name']} - {svc_name}",
            build_event_description(tenant_id, client_name, raw_phone),
        )
        c["pending"] = None
        c["state"] = "BOOKED"
        c["datetime_iso"] = dt_sel.isoformat()
        c["service"] = svc_name
        c["name"] = client_name
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "booked",
            "reply_voice": t(lang, "booking_confirmed"),
            "msg_out": t(lang, "booking_confirmed_text", service=svc_name, when=format_dt_short(dt_sel)),
            "lang": lang,
        }


    pending = c.get("pending") or {}
    explicit_time_parts = parse_explicit_time_parts(msg)
    explicit_time_present = explicit_time_parts is not None
    date_reference_present = has_date_reference(msg)

    if explicit_time_present and not date_reference_present:
        base_dt = None
        if c.get("datetime_iso"):
            base_dt = parse_dt_any_tz(c.get("datetime_iso") or "")
        if not base_dt and pending.get("awaiting_time_date_iso"):
            base_dt = parse_dt_any_tz(pending.get("awaiting_time_date_iso") or "")
        if not base_dt and pending.get("opt1_iso"):
            base_dt = parse_dt_any_tz(pending.get("opt1_iso") or "")
        if base_dt:
            hh, mm = explicit_time_parts
            dt_guess = base_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
            c["datetime_iso"] = dt_guess.isoformat()
            if pending.get("awaiting_time_date_iso"):
                pending.pop("awaiting_time_date_iso", None)
            c["pending"] = pending or None
            db_save_conversation(tenant_id, user_key, c)

    # AI extraction
    alias_hint = ", ".join([f"{k} => {v}" for k, v in service_aliases.items()][:50])
    sys_pt = (
        f"You are an appointment receptionist for {settings['biz_name']}. "
        f"Business hours: {settings['work_start']}-{settings['work_end']}. "
        f"Known services: {settings['services_hint']}. "
        f"Service aliases: {alias_hint or 'none'}. "
        f"Business memory: {business_memory or 'none'}. "
        "Extract and return strict JSON only with keys: "
        "service, time_text, datetime_iso, name. "
        "service and name must be plain strings, not arrays. "
        "If a user names a service using an alias, map it to the canonical service name. "
        "If value is unknown use null."
    )
    usr_pt = f"Today: {now_ts().date()}. User language: {lang}. User message: {msg}"
    data = openai_chat_json(sys_pt, usr_pt)

    service = apply_service_aliases(data.get("service"), service_aliases)
    name = normalize_name(data.get("name"))
    if service:
        c["service"] = apply_service_aliases(service, service_aliases) or service
    if name:
        c["name"] = name
    if data.get("time_text"):
        c["time_text"] = str(data.get("time_text"))

    pending = c.get("pending") or {}
    pending_date_dt = None
    if pending.get("awaiting_time_date_iso") and has_explicit_time(msg):
        pending_date_dt = combine_date_with_explicit_time(pending.get("awaiting_time_date_iso"), msg)

    dt_start = pending_date_dt or parse_dt_from_iso_or_fallback(
        data.get("datetime_iso"), data.get("time_text"), msg
    )
    explicit_time_present = has_explicit_time(msg) or has_explicit_time(str(data.get("time_text") or ""))
    date_reference_present = has_date_reference(msg) or has_date_reference(str(data.get("time_text") or ""))

    if not dt_start and pending.get("awaiting_time_date_iso"):
        base_pending = parse_dt_any_tz(pending.get("awaiting_time_date_iso") or "")
        if base_pending and explicit_time_present:
            dt_start = combine_date_with_explicit_time(base_pending.isoformat(), msg)

    if dt_start and not explicit_time_present and date_reference_present:
        pending.update({
            "awaiting_time_date_iso": dt_start.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
        })
        c["pending"] = pending
        c["datetime_iso"] = None
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "need_more",
            "reply_voice": t(lang, "need_time"),
            "msg_out": t(lang, "need_time"),
            "lang": lang,
        }

    if not dt_start:
        dt_start = parse_dt_any_tz(c.get("datetime_iso") or "")
    if dt_start:
        c["datetime_iso"] = dt_start.isoformat()
        if pending.get("awaiting_time_date_iso"):
            pending.pop("awaiting_time_date_iso", None)
            c["pending"] = pending or None

    db_save_conversation(tenant_id, user_key, c)

    if not c.get("service"):
        return {
            "status": "need_more",
            "reply_voice": t(lang, "need_service"),
            "msg_out": t(lang, "need_service"),
            "lang": lang,
        }
    if not dt_start:
        return {
            "status": "need_more",
            "reply_voice": t(lang, "need_time"),
            "msg_out": t(lang, "need_time"),
            "lang": lang,
        }
    if not c.get("name") and channel == "voice":
        return {
            "status": "need_more",
            "reply_voice": t(lang, "need_name"),
            "msg_out": t(lang, "need_name"),
            "lang": lang,
        }
    if not calendar_ready:
        return blocked_result_for_lang(lang)

    # Business hours check
    if not in_business_hours(
        dt_start, APPT_MINUTES, settings["work_start"], settings["work_end"]
    ):
        opts = find_next_two_slots(
            settings["calendar_id"],
            dt_start,
            APPT_MINUTES,
            settings["work_start"],
            settings["work_end"],
        )
        if opts:
            c["pending"] = {
                "opt1_iso": opts[0].isoformat(),
                "opt2_iso": opts[1].isoformat(),
                "service": c["service"],
                "name": c.get("name"),
                **(c.get("pending") or {}),
            }
            db_save_conversation(tenant_id, user_key, c)
            voice_prompt = t(
                lang,
                "voice_options_prompt",
                opt1=format_dt_short(opts[0]),
                opt2=format_dt_short(opts[1]),
            ) if voice_like_channel else t(lang, "closed_voice")
            return {
                "status": "need_more" if voice_like_channel else "busy",
                "reply_voice": voice_prompt,
                "msg_out": t(
                    lang,
                    "closed_text",
                    opt1=format_dt_short(opts[0]),
                    opt2=format_dt_short(opts[1]),
                ),
                "lang": lang,
            }
        return {
            "status": "recovery",
            "reply_voice": t(lang, "all_busy_voice"),
            "msg_out": t(lang, "all_busy_text"),
            "lang": lang,
        }

    # Busy check
    if is_slot_busy(
        settings["calendar_id"], dt_start, dt_start + timedelta(minutes=APPT_MINUTES)
    ):
        opts = find_next_two_slots(
            settings["calendar_id"],
            dt_start,
            APPT_MINUTES,
            settings["work_start"],
            settings["work_end"],
        )
        if opts:
            c["pending"] = {
                "opt1_iso": opts[0].isoformat(),
                "opt2_iso": opts[1].isoformat(),
                "service": c["service"],
                "name": c.get("name"),
                **(c.get("pending") or {}),
            }
            db_save_conversation(tenant_id, user_key, c)
            voice_prompt = t(
                lang,
                "voice_options_prompt",
                opt1=format_dt_short(opts[0]),
                opt2=format_dt_short(opts[1]),
            ) if voice_like_channel else t(lang, "busy_voice")
            return {
                "status": "need_more" if voice_like_channel else "busy",
                "reply_voice": voice_prompt,
                "msg_out": t(
                    lang,
                    "busy_text",
                    opt1=format_dt_short(opts[0]),
                    opt2=format_dt_short(opts[1]),
                ),
                "lang": lang,
            }
        return {
            "status": "recovery",
            "reply_voice": t(lang, "all_busy_voice"),
            "msg_out": t(lang, "all_busy_text"),
            "lang": lang,
        }

    # Apply reschedule if pending
    if c.get("pending") and c["pending"].get("reschedule_event_id"):
        deleted = delete_calendar_event(
            settings["calendar_id"], c["pending"]["reschedule_event_id"]
        )
        if not deleted:
            return {
                "status": "cancel_failed",
                "reply_voice": t(lang, "cancel_failed"),
                "msg_out": t(lang, "cancel_failed"),
                "lang": lang,
            }
        c["pending"] = None

    # Final booking
    final_name = normalize_name(c.get("name")) or "Client"
    final_service = apply_service_aliases(c.get("service"), service_aliases) or settings["services_hint"]
    create_calendar_event(
        settings["calendar_id"],
        dt_start,
        APPT_MINUTES,
        f"{settings['biz_name']} - {final_service}",
        build_event_description(tenant_id, final_name, raw_phone),
    )
    c["state"] = "BOOKED"
    c["name"] = final_name
    c["service"] = final_service
    c["datetime_iso"] = dt_start.isoformat()
    db_save_conversation(tenant_id, user_key, c)
    return {
        "status": "booked",
        "reply_voice": t(lang, "booking_confirmed"),
        "msg_out": t(
            lang,
            "booking_confirmed_text",
            service=final_service,
            when=format_dt_short(dt_start),
        ),
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
    result = handle_user_text(tenant["_id"], caller, speech, "voice", lang)

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
    result = handle_user_text(
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
    result = handle_user_text(
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
    tenant = get_tenant(tenant_id)
    if not tenant.get("_id"):
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not oauth_ready():
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")
    return {"auth_url": build_google_oauth_url(tenant["_id"]), "tenant_id": tenant["_id"]}

@app.get("/google/callback")
def google_callback(code: str = "", state: str = ""):
    if not oauth_ready():
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")
    state_data = parse_google_oauth_state(state)
    tenant_id = str(state_data.get("tenant_id") or "").strip()
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    token_data = exchange_google_code_for_tokens(code)
    access_token = str(token_data.get("access_token") or "").strip()
    refresh_token = str(token_data.get("refresh_token") or "").strip() or None
    expires_in = int(token_data.get("expires_in") or 0)
    scope = str(token_data.get("scope") or "").strip() or None
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to exchange OAuth code")
    token_expiry = now_ts() + timedelta(seconds=expires_in) if expires_in else None
    userinfo = fetch_google_userinfo(access_token)
    google_email = str(userinfo.get("email") or "").strip() or None
    upsert_tenant_google_account(
        tenant_id=tenant_id,
        google_email=google_email,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expiry=token_expiry,
        scope=scope,
    )
    mark_tenant_google_connected(tenant_id, True, owner_email=google_email)
    calendars = fetch_google_calendar_list(access_token)
    return {
        "status": "connected",
        "tenant_id": tenant_id,
        "google_email": google_email,
        "calendars_found": len(calendars),
        "next": "/google/calendars?tenant_id=" + tenant_id,
    }

@app.get("/google/calendars")
def google_calendars(tenant_id: str):
    acct = get_tenant_google_account(tenant_id)
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
    ]
    return {"tenant_id": tenant_id, "items": simplified}

@app.post("/google/select_calendar")
async def google_select_calendar(request: Request):
    data = await request.json()
    tenant_id = str(data.get("tenant_id") or "").strip()
    calendar_id = str(data.get("calendar_id") or "").strip()
    if not tenant_id or not calendar_id:
        raise HTTPException(status_code=400, detail="tenant_id and calendar_id are required")
    select_tenant_calendar_id(tenant_id, calendar_id)

    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = {c["name"] for c in cols}
    sets = []
    params: Dict[str, Any] = {"tid": tenant_id}
    if "onboarding_completed" in col_names:
        sets.append("onboarding_completed=true")
    if "updated_at" in col_names:
        sets.append("updated_at=NOW()")
    if sets:
        with engine.begin() as conn:
            conn.execute(text(f"UPDATE tenants SET {', '.join(sets)} WHERE {pk}=:tid"), params)

    return {"status": "ok", "tenant_id": tenant_id, "calendar_id": calendar_id}


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


def validate_tenant_config(tenant: dict):
    missing = []
    for f in REQUIRED_TENANT_FIELDS:
        if not tenant.get(f):
            missing.append(f)

    if missing:
        logger.error(f"tenant_config_invalid tenant_id={tenant.get('id')} missing={missing}")
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

@app.post("/onboarding/create_tenant")
def onboarding_create_tenant(payload: dict = Body(...)):
    business_name = (payload.get("business_name") or "").strip()
    owner_email = (payload.get("owner_email") or "").strip()
    phone_number = normalize_incoming_to_number(payload.get("phone_number") or "")
    business_type = (payload.get("business_type") or "barbershop").strip()
    timezone_value = (payload.get("timezone") or "Europe/Riga").strip()
    language_value = get_lang((payload.get("language") or "lv").strip())

    if not business_name:
        raise HTTPException(status_code=400, detail="business_name required")

    tenant_id = re.sub(r"[^a-zA-Z0-9_]+", "_", business_name.lower()).strip("_")
    if not tenant_id:
        tenant_id = "tenant_" + uuid.uuid4().hex[:8]
    tenant_id = tenant_id + "_" + uuid.uuid4().hex[:4]

    cols = tenants_columns()
    col_names = {c["name"] for c in cols}

    fields = {
        "id": tenant_id,
        "business_name": business_name,
        "owner_email": owner_email,
        "status": "active",
        "timezone": timezone_value,
        "subscription_status": "trial",
        "google_connected": False,
        "onboarding_completed": False,
        "business_type": business_type,
        "language": language_value,
        "phone_number": phone_number or None,
        "plan": "starter",
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
        conn.execute(
            text(f"INSERT INTO tenants ({sql_cols}) VALUES ({sql_params})"),
            insert_vals,
        )

    if phone_number:
        upsert_phone_route(phone_number, tenant_id)

    google_path = f"/google/connect?tenant_id={tenant_id}"
    return {
        "tenant_id": tenant_id,
        "business_name": business_name,
        "phone_number": phone_number or None,
        "onboarding_google_url": f"{SERVER_BASE_URL}{google_path}" if SERVER_BASE_URL else google_path,
    }
