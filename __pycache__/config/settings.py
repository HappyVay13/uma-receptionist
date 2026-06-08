import logging
import os
from datetime import timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
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
            environment=os.getenv("ENVIRONMENT", "production"),
        )
        _SENTRY_MIDDLEWARE_CLASS = SentryAsgiMiddleware
        logger.info("Sentry initialized")
    except Exception as e:
        logger.error(f"Sentry init failed: {e}")

TZ = ZoneInfo("Europe/Riga") if ZoneInfo is not None else timezone(timedelta(hours=2))

VOICE_SDK_ORIGINS = os.getenv("VOICE_SDK_ORIGINS", "*").strip()

TENANT_ID_DEFAULT = (os.getenv("DEFAULT_CLIENT_ID", "default") or "default").strip()
TEST_TENANT_ID = (os.getenv("TEST_TENANT_ID", "") or "").strip()
ALLOW_DEFAULT_TENANT_FALLBACK = (
    (os.getenv("ALLOW_DEFAULT_TENANT_FALLBACK", "false") or "false").strip().lower()
    in ("1", "true", "yes", "on")
)
RECOVERY_BOOKING_LINK = os.getenv("RECOVERY_BOOKING_LINK", "https://repliq.app/book").strip()

APPT_MINUTES = int(os.getenv("APPT_MINUTES", "30"))
WORK_START_HHMM_DEFAULT = os.getenv("WORK_START_HHMM", "09:00").strip()
WORK_END_HHMM_DEFAULT = os.getenv("WORK_END_HHMM", "18:00").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
LLM_INTELLIGENCE_ENABLED = (
    (os.getenv("LLM_INTELLIGENCE_ENABLED", "true") or "true").strip().lower()
    in ("1", "true", "yes", "on")
)
LLM_INTENT_MIN_CONFIDENCE = float((os.getenv("LLM_INTENT_MIN_CONFIDENCE", "0.60") or "0.60").strip())

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_VALIDATE_SIGNATURE = (
    (os.getenv("TWILIO_VALIDATE_SIGNATURE", "true") or "true").strip().lower()
    in ("1", "true", "yes", "on")
)
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()
BOOKING_CONFIRMATION_ENABLED = (
    (os.getenv("BOOKING_CONFIRMATION_ENABLED", "true") or "true").strip().lower()
    in ("1", "true", "yes", "on")
)
AUTO_SEND_CONFIRMATION_FOR_TEXT_CHANNELS = (
    (os.getenv("AUTO_SEND_CONFIRMATION_FOR_TEXT_CHANNELS", "false") or "false").strip().lower()
    in ("1", "true", "yes", "on")
)

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
CLIENT_STATUS_FALLBACK = ((os.getenv("CLIENT_STATUS", "trial") or "trial").strip().lower())
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


def get_sentry_middleware_class():
    return _SENTRY_MIDDLEWARE_CLASS
