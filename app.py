import os
import json
import re
import urllib.parse
from datetime import datetime, timedelta, timezone, date
from typing import Dict, Any, Optional, Tuple, List

import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, StreamingResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client as TwilioClient

from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import texttospeech

app = FastAPI()

# =========================
# CONFIG
# =========================
TZ = timezone(timedelta(hours=2))  # Europe/Riga (+02:00)
SESSION_TTL_MIN = 30

BUSINESS = {
    "name": os.getenv("BIZ_NAME", "Repliq"),
    "address": os.getenv("BIZ_ADDRESS", "Rēzekne"),
    "hours": os.getenv("BIZ_HOURS", "09:00 - 18:00"),
    "services": os.getenv("BIZ_SERVICES", "мужские и женские стрижки"),
}

# IMPORTANT: short link to avoid Twilio trial SMS length issues
RECOVERY_BOOKING_LINK = os.getenv("RECOVERY_BOOKING_LINK", "https://repliq.app/book")

# Appointments
APPT_MINUTES = int(os.getenv("APPT_MINUTES", "30"))
WORK_START_HHMM = os.getenv("WORK_START_HHMM", "09:00")
WORK_END_HHMM = os.getenv("WORK_END_HHMM", "18:00")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")

# SMS sender (regular phone number, e.g. +1... or +371...)
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

# WhatsApp sender (must be like "whatsapp:+14155238886" for sandbox or approved WA sender)
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")

# Google Calendar + Google TTS (reuse same Service Account JSON)
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "")

# ElevenLabs (for RU/EN)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")

# Your public base URL, e.g. https://repliq.onrender.com (NO trailing slash)
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "").strip().rstrip("/")

# -------------------------
# Minimal Trial / Active / Inactive
# -------------------------
# CLIENT_STATUS: trial | active | inactive
CLIENT_STATUS = os.getenv("CLIENT_STATUS", "trial").strip().lower()
# TRIAL_END_ISO: e.g. "2026-03-15T00:00:00+02:00" or "...Z"
TRIAL_END_ISO = os.getenv("TRIAL_END_ISO", "").strip()


def now_ts() -> datetime:
    return datetime.now(TZ)


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


TRIAL_END_DT = parse_dt_any_tz(TRIAL_END_ISO)


def client_allowed() -> Tuple[bool, str]:
    """
    Returns (allowed, reason).
    reason: ok | inactive | trial_expired
    """
    st = (CLIENT_STATUS or "trial").lower()
    if st == "inactive":
        return False, "inactive"
    if st == "trial":
        if TRIAL_END_DT and now_ts() > TRIAL_END_DT:
            return False, "trial_expired"
    return True, "ok"


def not_available_message(lang: str) -> str:
    lang = get_lang(lang)
    if lang == "lv":
        return "Atvainojiet, šis numurs pašlaik nav pieejams."
    if lang == "ru":
        return "Извините, этот номер сейчас недоступен."
    return "Sorry, this number is currently unavailable."


# -------------------------
# Short templates (trial-safe)
# -------------------------
SMS_TEMPLATES = {
    "en": {
        "confirmed": "Booked: {service} {time}. Addr: {addr}. {link}",
        "busy": "Busy. 1){opt1} 2){opt2}. Reply 1/2. {link}",
        "ask_service": "Which service? Example: men's haircut. {link}",
        "ask_time": "When? Example: tomorrow 15:10. {link}",
        "ask_name": "Your name? {link}",
        "recovery": "Book via: {link}",
    },
    "ru": {
        "confirmed": "Запись: {service} {time}. Адрес: {addr}. {link}",
        "busy": "Занято. 1){opt1} 2){opt2}. Ответ 1/2. {link}",
        "ask_service": "Какая услуга? Пример: мужская стрижка. {link}",
        "ask_time": "Когда? Пример: завтра 15:10. {link}",
        "ask_name": "Как вас зовут? {link}",
        "recovery": "Запись: {link}",
    },
    "lv": {
        "confirmed": "Pieraksts: {service} {time}. Adrese: {addr}. {link}",
        "busy": "Aizņemts. 1){opt1} 2){opt2}. Atbildi 1/2. {link}",
        "ask_service": "Kāds pakalpojums? Piem.: vīriešu frizūra. {link}",
        "ask_time": "Kad? Piem.: rīt 15:10. {link}",
        "ask_name": "Jūsu vārds? {link}",
        "recovery": "Pieraksts: {link}",
    },
}

VOICE_PROMPTS = {
    "en": {
        "greet": "Hello. Please say what you need. You can also press 1 for English, 2 for Russian, 3 for Latvian.",
        "continue": "Please continue.",
        "bye": "Goodbye.",
        "need_service": "Please say the service.",
        "need_time": "Please say date and time.",
        "need_name": "Please say your name.",
        "outside": "Sorry, outside working hours. Please choose another time.",
        "busy": "That time is busy. I sent options by message.",
        "booked": "Thank you. Booking confirmed by message.",
        "retry": "Sorry, I couldn't hear you.",
    },
    "ru": {
        "greet": "Здравствуйте. Скажите, пожалуйста, что вам нужно. Можно нажать 1 — английский, 2 — русский, 3 — латышский.",
        "continue": "Продолжайте, пожалуйста.",
        "bye": "До свидания.",
        "need_service": "Скажите, пожалуйста, услугу.",
        "need_time": "Скажите, пожалуйста, дату и время.",
        "need_name": "Скажите, пожалуйста, как вас зовут.",
        "outside": "Мы не работаем в это время. Назовите другое время.",
        "busy": "Это время занято. Я отправил варианты сообщением.",
        "booked": "Спасибо. Подтверждение отправил сообщением.",
        "retry": "Я вас не расслышал.",
    },
    "lv": {
        "greet": "Labdien! Sakiet, lūdzu, ko vēlaties. Var arī nospiest 1 angliski, 2 krieviski, 3 latviski.",
        "continue": "Lūdzu, turpiniet.",
        "bye": "Uz redzēšanos.",
        "need_service": "Kādu pakalpojumu vēlaties?",
        "need_time": "Lūdzu, sakiet datumu un laiku.",
        "need_name": "Kā jūs sauc?",
        "outside": "Mēs nestrādājam šajā laikā. Lūdzu, izvēlieties citu laiku.",
        "busy": "Šis laiks ir aizņemts. Nosūtīju variantus ziņā.",
        "booked": "Paldies. Apstiprinājumu nosūtīju ziņā.",
        "retry": "Es jūs nesadzirdēju.",
    },
}

# =========================
# STORAGE
# =========================
CALL_SESSIONS: Dict[str, Dict[str, Any]] = {}  # per-call: lang + sms dedupe
CONV: Dict[str, Dict[str, Any]] = {}           # per-user across channels
_GCAL = None
_TTS = None


# =========================
# HELPERS
# =========================
def today_local() -> date:
    return datetime.now(TZ).date()


def cleanup_call_sessions():
    cutoff = now_ts() - timedelta(minutes=SESSION_TTL_MIN)
    dead = []
    for sid, s in CALL_SESSIONS.items():
        created = datetime.fromisoformat(s.get("created_at"))
        if created < cutoff:
            dead.append(sid)
    for sid in dead:
        CALL_SESSIONS.pop(sid, None)


def get_call_session(call_sid: str) -> Dict[str, Any]:
    s = CALL_SESSIONS.get(call_sid)
    if not s:
        s = {
            "created_at": now_ts().isoformat(),
            "lang": None,
            "sms_flags": {},
        }
        CALL_SESSIONS[call_sid] = s
    return s


def twiml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")


def norm_user_key(phone: str) -> str:
    p = (phone or "").strip()
    p = p.replace("whatsapp:", "")
    p = re.sub(r"[^\d+]", "", p)
    return p or "unknown"


def get_lang(value: Optional[str]) -> str:
    return value if value in ("en", "ru", "lv") else "en"


def detect_language(text: str) -> str:
    """
    Stronger detector:
    - Cyrillic -> ru
    - Latvian diacritics -> lv
    - Latvian ASCII keywords (rit/parit/viriesu/frizura...) -> lv
    - else -> en
    """
    t = (text or "").lower()

    if re.search(r"[а-яА-Я]", t):
        return "ru"

    if re.search(r"[āēīūčšžģķļņ]", t):
        return "lv"

    lv_keywords = [
        "rit", "parit", "pec", "dien", "pulksten",
        "frizur", "viries", "sievies", "pakalpoj", "pierakst",
        "labdien", "ludzu", "mans vards", "jusu vards",
        "aiznem", "aizņem", "apstiprin", "apstiprinā",
    ]
    if any(k in t for k in lv_keywords):
        return "lv"

    return "en"


def stt_locale_for_lang(lang: str) -> str:
    lang = get_lang(lang)
    if lang == "ru":
        return "ru-RU"
    if lang == "lv":
        return "lv-LV"
    return "en-US"


def _short(s: Optional[str], n: int) -> str:
    return (s or "").strip()[:n]


def _parse_hhmm(hhmm: str) -> Tuple[int, int]:
    hh, mm = hhmm.split(":")
    return int(hh), int(mm)


def in_business_hours(dt_start: datetime, duration_min: int) -> bool:
    ws_h, ws_m = _parse_hhmm(WORK_START_HHMM)
    we_h, we_m = _parse_hhmm(WORK_END_HHMM)

    day_start = dt_start.replace(hour=ws_h, minute=ws_m, second=0, microsecond=0)
    day_end = dt_start.replace(hour=we_h, minute=we_m, second=0, microsecond=0)
    dt_end = dt_start + timedelta(minutes=duration_min)
    return (dt_start >= day_start) and (dt_end <= day_end)


# =========================
# OPENAI
# =========================
def openai_chat_json(system: str, user: str) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        return {"service": None, "time_text": None, "datetime_iso": None, "name": None, "phone": None}

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": OPENAI_MODEL,
        "temperature": 0.2,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers=headers, json=payload, timeout=25)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    return json.loads(content)


# =========================
# TWILIO MESSAGING (SMS/WA)
# =========================
def _twilio_client() -> Optional[TwilioClient]:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        return None
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_message(to_number: str, body: str):
    """
    Unified sender via REST:
      - If to_number starts with 'whatsapp:' -> uses TWILIO_WHATSAPP_FROM
      - Else -> uses TWILIO_FROM_NUMBER (SMS)
    """
    client = _twilio_client()
    if not client:
        print("Message skipped: Twilio env vars missing")
        return

    to_number = (to_number or "").strip()
    is_wa = to_number.startswith("whatsapp:")

    from_number = TWILIO_WHATSAPP_FROM if is_wa else TWILIO_FROM_NUMBER
    if not from_number:
        print("Message skipped: FROM number missing for", "whatsapp" if is_wa else "sms")
        return

    try:
        msg = client.messages.create(from_=from_number, to=to_number, body=body)
        print("Message sent:", {"to": to_number, "sid": msg.sid, "status": msg.status})
    except Exception as e:
        print("Message send error:", {"to": to_number, "err": repr(e)})


def send_once_for_call(call_sid: str, key: str, to_number: str, body: str):
    s = get_call_session(call_sid)
    flags = s.setdefault("sms_flags", {})
    if flags.get(key):
        return
    send_message(to_number, body)
    flags[key] = True


# =========================
# TIME PARSING (fallback)
# =========================
def parse_time_text_to_dt(text: str) -> Optional[datetime]:
    if not text:
        return None

    t = text.lower()

    m = re.search(r"\b([01]?\d|2[0-3])[:. ]([0-5]\d)\b", t)
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2))

    base = today_local()

    # explicit ISO date
    m_iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
    if m_iso:
        y, mo, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        try:
            base = date(y, mo, d)
        except ValueError:
            return None
    else:
        # explicit dd.mm(.yyyy) or dd/mm(/yyyy)
        m_dm = re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b", t)
        if m_dm:
            d = int(m_dm.group(1))
            mo = int(m_dm.group(2))
            y_raw = m_dm.group(3)
            if y_raw:
                y = int(y_raw)
                if y < 100:
                    y += 2000
            else:
                y = base.year
                try:
                    candidate = date(y, mo, d)
                except ValueError:
                    return None
                if candidate < base:
                    y += 1
            try:
                base = date(y, mo, d)
            except ValueError:
                return None
        else:
            # relative
            m_ru = re.search(r"через\s+(\d{1,2})\s*(дн|дня|дней)", t)
            m_en = re.search(r"\bin\s+(\d{1,2})\s+days\b", t)
            m_lv = re.search(r"pēc\s+(\d{1,2})\s+dien", t)

            if any(k in t for k in ["day after tomorrow", "послезавтра", "после завтра", "parīt", "parit"]):
                base = today_local() + timedelta(days=2)
            elif any(k in t for k in ["tomorrow", "завтра", "rīt", "rit"]):
                base = base + timedelta(days=1)
            elif m_ru:
                base = base + timedelta(days=int(m_ru.group(1)))
            elif m_en:
                base = base + timedelta(days=int(m_en.group(1)))
            elif m_lv:
                base = base + timedelta(days=int(m_lv.group(1)))

    return datetime(base.year, base.month, base.day, hh, mm, tzinfo=TZ)


def parse_dt_from_iso_or_fallback(datetime_iso: Optional[str], time_text: Optional[str], raw_text: Optional[str]) -> Optional[datetime]:
    iso = (datetime_iso or "").strip()
    if iso:
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ)
            else:
                dt = dt.astimezone(TZ)
            return dt
        except Exception as e:
            print("datetime_iso parse error:", repr(e))

    combined = f"{time_text or ''} {raw_text or ''}".strip()
    return parse_time_text_to_dt(combined)


# =========================
# ELEVENLABS (RU/EN)
# =========================
def generate_eleven_audio(text: str) -> bytes:
    if not (ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID):
        return b""

    safe_text = (text or "").strip()
    if not safe_text:
        return b""
    if len(safe_text) > 240:
        safe_text = safe_text[:240]

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": safe_text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.7},
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        if r.status_code == 200 and r.content:
            return r.content
        print("ElevenLabs error:", r.status_code, r.text[:300])
        return b""
    except Exception as e:
        print("ElevenLabs request error:", repr(e))
        return b""


# =========================
# GOOGLE TTS (LV)
# =========================
def get_google_tts():
    global _TTS
    if _TTS is not None:
        return _TTS

    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        return None

    info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(info)
    _TTS = texttospeech.TextToSpeechClient(credentials=creds)
    return _TTS


def generate_google_lv_mp3(text: str) -> bytes:
    client = get_google_tts()
    if client is None:
        return b""

    t = (text or "").strip()
    if not t:
        return b""
    if len(t) > 300:
        t = t[:300]

    synthesis_input = texttospeech.SynthesisInput(text=t)

    voice = texttospeech.VoiceSelectionParams(
        language_code="lv-LV",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        # later we can lock exact name="lv-LV-..." if you want
    )

    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

    resp = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )
    return resp.audio_content or b""


@app.get("/tts")
def tts(text: str, lang: str = "en"):
    """
    Twilio <Play> endpoint. Returns audio/mpeg.
    - lv -> Google TTS
    - ru/en -> ElevenLabs
    """
    lang = get_lang(lang)

    if lang == "lv":
        audio = generate_google_lv_mp3(text)
        if not audio:
            raise HTTPException(status_code=500, detail="Google LV TTS failed")
        return StreamingResponse(iter([audio]), media_type="audio/mpeg")

    audio = generate_eleven_audio(text)
    if not audio:
        raise HTTPException(status_code=500, detail="TTS failed (Eleven)")
    return StreamingResponse(iter([audio]), media_type="audio/mpeg")


def play_tts(vr: VoiceResponse, text: str, lang: str):
    """
    Always use /tts play when SERVER_BASE_URL set (so LV uses Google).
    """
    t = (text or "").strip() or "OK."
    lang = get_lang(lang)

    if SERVER_BASE_URL:
        q = urllib.parse.quote_plus(t)
        vr.play(f"{SERVER_BASE_URL}/tts?lang={lang}&text={q}")
        return

    # emergency fallback (shouldn't happen in prod)
    vr.say(t, language=stt_locale_for_lang(lang))


# =========================
# GOOGLE CALENDAR
# =========================
def get_gcal():
    global _GCAL
    if _GCAL is not None:
        return _GCAL

    if not (GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_CALENDAR_ID):
        return None

    try:
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        _GCAL = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return _GCAL
    except Exception as e:
        print("GCAL init error:", repr(e))
        return None


def is_slot_busy(dt_start: datetime, dt_end: datetime) -> bool:
    svc = get_gcal()
    if svc is None:
        return False
    try:
        body = {
            "timeMin": dt_start.isoformat(),
            "timeMax": dt_end.isoformat(),
            "items": [{"id": GOOGLE_CALENDAR_ID}],
        }
        fb = svc.freebusy().query(body=body).execute()
        busy = fb["calendars"][GOOGLE_CALENDAR_ID].get("busy", [])
        return len(busy) > 0
    except Exception as e:
        print("GCAL freebusy error:", repr(e))
        return False


def find_next_two_slots(dt_start: datetime, duration_min: int) -> Optional[Tuple[datetime, datetime]]:
    step = 30
    candidate = dt_start
    found: List[datetime] = []
    for _ in range(48):  # ~24 hours by 30m
        if in_business_hours(candidate, duration_min):
            if not is_slot_busy(candidate, candidate + timedelta(minutes=duration_min)):
                found.append(candidate)
                if len(found) == 2:
                    return found[0], found[1]
        candidate = candidate + timedelta(minutes=step)
    return None


def create_calendar_event(dt_start: datetime, duration_min: int, summary: str, description: str) -> Optional[str]:
    svc = get_gcal()
    if svc is None:
        return None

    dt_end = dt_start + timedelta(minutes=duration_min)
    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": dt_start.isoformat(), "timeZone": "Europe/Riga"},
        "end": {"dateTime": dt_end.isoformat(), "timeZone": "Europe/Riga"},
    }

    try:
        created = svc.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
        return created.get("htmlLink")
    except Exception as e:
        print("GCAL insert error:", repr(e))
        return None


# =========================
# CORE (UNIFIED)
# =========================
def get_conv(user_key: str, default_lang: str) -> Dict[str, Any]:
    c = CONV.get(user_key)
    if not c:
        c = {
            "created_at": now_ts().isoformat(),
            "updated_at": now_ts().isoformat(),
            "lang": get_lang(default_lang),
            "history": [],
            "service": None,
            "name": None,
            "datetime_iso": None,
            "time_text": None,
            "pending": None,  # {"opt1_iso":..., "opt2_iso":..., "service":..., "name":...}
        }
        CONV[user_key] = c

    if default_lang in ("en", "ru", "lv"):
        c["lang"] = get_lang(default_lang)

    c["updated_at"] = now_ts().isoformat()
    return c


def render_msg(lang: str, key: str, **kwargs) -> str:
    lang = get_lang(lang)
    tmpl = SMS_TEMPLATES[lang].get(key) or SMS_TEMPLATES["en"][key]
    return tmpl.format(**kwargs)


def handle_user_text(user_key: str, text: str, channel: str, lang_hint: str, raw_phone: str) -> Dict[str, Any]:
    """
    Returns:
      - status: need_more|booked|busy|recovery
      - voice_key: key for VOICE_PROMPTS
      - msg_out: message text to send (already localized, without BUSINESS prefix)
      - lang: chosen language
    """
    if not lang_hint or lang_hint not in ("en", "ru", "lv"):
        lang_hint = detect_language(text)

    c = get_conv(user_key, lang_hint)
    lang = get_lang(c.get("lang"))

    msg = (text or "").strip()
    c["history"].append({"ts": now_ts().isoformat(), "channel": channel, "text": msg})

    # 0) option reply 1/2
    if msg in ("1", "2") and c.get("pending"):
        pending = c["pending"]
        chosen_iso = pending["opt1_iso"] if msg == "1" else pending["opt2_iso"]
        try:
            dt_start = datetime.fromisoformat(chosen_iso).astimezone(TZ)
        except Exception:
            dt_start = None

        if not dt_start:
            c["pending"] = None
            return {
                "status": "need_more",
                "voice_key": "need_time",
                "msg_out": render_msg(lang, "ask_time", link=RECOVERY_BOOKING_LINK),
                "lang": lang,
            }

        service = pending.get("service") or c.get("service")
        name = pending.get("name") or c.get("name") or "Client"

        summary = f"{BUSINESS['name']} — {_short(service, 60)}"
        desc = f"Name: {name}\nPhone: {raw_phone}\nService: {service}\nSource: {channel} (option {msg})\n"
        create_calendar_event(dt_start, APPT_MINUTES, summary, desc)

        c["pending"] = None
        c["service"] = service
        c["name"] = name
        c["datetime_iso"] = dt_start.isoformat()
        c["time_text"] = dt_start.strftime("%Y-%m-%d %H:%M")

        when_str = dt_start.strftime("%m-%d %H:%M")
        out = render_msg(
            lang, "confirmed",
            service=_short(service, 40),
            time=when_str,
            addr=_short(BUSINESS.get("address"), 35),
            link=RECOVERY_BOOKING_LINK,
        )
        return {"status": "booked", "voice_key": "booked", "msg_out": out, "lang": lang}

    # 1) Extract via OpenAI
    system = f"""
You are Repliq, an AI receptionist for a small business.

Business:
- Name: {BUSINESS['name']}
- Hours: {BUSINESS['hours']}
- Services: {BUSINESS['services']}

Return STRICT JSON with keys:
service: string|null
time_text: string|null
datetime_iso: string|null   # ISO 8601 with timezone offset, Europe/Riga
name: string|null
phone: string|null

Rules:
- Convert explicit/relative dates (tomorrow/day after tomorrow/in N days/weekday) if possible.
- If unclear, set datetime_iso = null and keep time_text if present.
"""
    user = (
        f"Today (Europe/Riga) is {now_ts().strftime('%Y-%m-%d')}.\n"
        f"User said: {msg}\n"
        f"Channel: {channel}\n"
        f"User phone: {raw_phone}\n"
        f"Language hint: {lang}\n"
    )

    try:
        data = openai_chat_json(system, user)
    except Exception as e:
        print("OpenAI error:", repr(e))
        data = {"service": None, "time_text": None, "datetime_iso": None, "name": None, "phone": None}

    if data.get("service"):
        c["service"] = data["service"]
    if data.get("name"):
        c["name"] = data["name"]
    if data.get("datetime_iso"):
        c["datetime_iso"] = data["datetime_iso"]
    if data.get("time_text"):
        c["time_text"] = data["time_text"]

    # 2) dt_start
    dt_start = parse_dt_from_iso_or_fallback(c.get("datetime_iso"), c.get("time_text"), msg)
    if dt_start:
        c["datetime_iso"] = dt_start.isoformat()

    # 3) missing fields
    if not c.get("service"):
        return {"status": "need_more", "voice_key": "need_service",
                "msg_out": render_msg(lang, "ask_service", link=RECOVERY_BOOKING_LINK), "lang": lang}

    if not dt_start:
        return {"status": "need_more", "voice_key": "need_time",
                "msg_out": render_msg(lang, "ask_time", link=RECOVERY_BOOKING_LINK), "lang": lang}

    if not c.get("name"):
        return {"status": "need_more", "voice_key": "need_name",
                "msg_out": render_msg(lang, "ask_name", link=RECOVERY_BOOKING_LINK), "lang": lang}

    # 4) business hours
    if not in_business_hours(dt_start, APPT_MINUTES):
        return {"status": "need_more", "voice_key": "outside",
                "msg_out": render_msg(lang, "ask_time", link=RECOVERY_BOOKING_LINK), "lang": lang}

    # 5) busy check
    dt_end = dt_start + timedelta(minutes=APPT_MINUTES)
    if is_slot_busy(dt_start, dt_end):
        opts = find_next_two_slots(dt_start, APPT_MINUTES)
        if opts:
            opt1, opt2 = opts
            c["pending"] = {
                "opt1_iso": opt1.isoformat(),
                "opt2_iso": opt2.isoformat(),
                "service": c.get("service"),
                "name": c.get("name"),
            }
            out = render_msg(
                lang, "busy",
                opt1=opt1.strftime("%m-%d %H:%M"),
                opt2=opt2.strftime("%m-%d %H:%M"),
                link=RECOVERY_BOOKING_LINK,
            )
            return {"status": "busy", "voice_key": "busy", "msg_out": out, "lang": lang}

        out = render_msg(lang, "recovery", link=RECOVERY_BOOKING_LINK)
        return {"status": "recovery", "voice_key": "need_time", "msg_out": out, "lang": lang}

    # 6) book
    service = c.get("service")
    name = c.get("name") or "Client"

    summary = f"{BUSINESS['name']} — {_short(service, 60)}"
    desc = (
        f"Name: {name}\nPhone: {raw_phone}\nService: {service}\n"
        f"Original: {msg}\nModel time_text: {c.get('time_text')}\nModel datetime_iso: {c.get('datetime_iso')}\n"
        f"Source: {channel}\n"
    )
    create_calendar_event(dt_start, APPT_MINUTES, summary, desc)

    when_str = dt_start.strftime("%m-%d %H:%M")
    out = render_msg(
        lang, "confirmed",
        service=_short(service, 40),
        time=when_str,
        addr=_short(BUSINESS.get("address"), 35),
        link=RECOVERY_BOOKING_LINK,
    )
    return {"status": "booked", "voice_key": "booked", "msg_out": out, "lang": lang}


# =========================
# HEALTH
# =========================
@app.get("/health")
async def health():
    allowed, reason = client_allowed()
    return {
        "ok": True,
        "ts": now_ts().isoformat(),
        "client_status": CLIENT_STATUS,
        "trial_end": TRIAL_END_DT.isoformat() if TRIAL_END_DT else None,
        "allowed": allowed,
        "reason": reason,
    }


# =========================
# VOICE (auto + DTMF override)
# =========================
@app.post("/voice/incoming")
async def voice_incoming(request: Request):
    cleanup_call_sessions()
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    caller = str(form.get("From", ""))

    cs = get_call_session(call_sid)
    cs["caller"] = caller

    vr = VoiceResponse()

    allowed, _ = client_allowed()
    if not allowed:
        play_tts(vr, not_available_message("lv"), "lv")
        vr.hangup()
        return twiml(vr)

    # Gather speech + optional dtmf 1/2/3
    g = Gather(
        input="speech dtmf",
        num_digits=1,
        action="/voice/intent",
        method="POST",
        timeout=7,
        speech_timeout="auto",
        language="lv-LV",  # start LV-friendly STT
    )

    # greet in LV (Google)
    if SERVER_BASE_URL:
        play_tts(g, VOICE_PROMPTS["lv"]["greet"], "lv")  # (Gather supports nested verbs)
    else:
        g.say(VOICE_PROMPTS["lv"]["greet"], language="lv-LV")

    vr.append(g)

    play_tts(vr, VOICE_PROMPTS["lv"]["retry"], "lv")
    vr.hangup()
    return twiml(vr)


@app.post("/voice/intent")
async def voice_intent(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    caller = str(form.get("From", ""))
    speech = str(form.get("SpeechResult", "")).strip()
    digits = str(form.get("Digits", "")).strip()

    cs = get_call_session(call_sid)
    user_key = norm_user_key(caller)

    allowed, _ = client_allowed()
    if not allowed:
        vr = VoiceResponse()
        play_tts(vr, not_available_message("lv"), "lv")
        vr.hangup()
        return twiml(vr)

    # DTMF override (force language)
    if digits in ("1", "2", "3"):
        cs["lang"] = "en" if digits == "1" else ("ru" if digits == "2" else "lv")

    # auto-detect if not forced
    if not cs.get("lang"):
        cs["lang"] = detect_language(speech)

    lang = get_lang(cs.get("lang"))

    result = handle_user_text(
        user_key=user_key,
        text=speech,
        channel="voice",
        lang_hint=lang,
        raw_phone=caller,
    )

    lang = get_lang(result.get("lang") or lang)
    cs["lang"] = lang

    vr = VoiceResponse()

    voice_key = result.get("voice_key") or "booked"
    play_tts(vr, VOICE_PROMPTS[lang].get(voice_key, "OK."), lang)

    # If we need more, gather again
    if result.get("status") == "need_more":
        g = Gather(
            input="speech",
            action="/voice/intent",
            method="POST",
            timeout=7,
            speech_timeout="auto",
            language=stt_locale_for_lang(lang),
        )
        # short continue prompt
        if SERVER_BASE_URL:
            play_tts(g, VOICE_PROMPTS[lang]["continue"], lang)
        else:
            g.say(VOICE_PROMPTS[lang]["continue"], language=stt_locale_for_lang(lang))
        vr.append(g)
        play_tts(vr, VOICE_PROMPTS[lang]["bye"], lang)
        vr.hangup()
    else:
        vr.hangup()

    # Send ONE confirmation/busy/recovery SMS per call step (short link)
    out = result.get("msg_out")
    if out and caller and caller != "unknown":
        send_once_for_call(call_sid, f"confirm_{result.get('status','x')}", caller, f"{BUSINESS['name']}: {out}")

    return twiml(vr)


@app.post("/voice/status")
async def voice_status(request: Request):
    """
    Optional: Twilio status callback.
    If call ends without booking, send recovery ONCE.
    """
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    call_status = str(form.get("CallStatus", ""))
    caller = str(form.get("From", ""))

    cs = get_call_session(call_sid)
    lang = get_lang(cs.get("lang") or "lv")

    if call_status in ("completed", "busy", "failed", "no-answer", "canceled"):
        user_key = norm_user_key(caller)
        c = CONV.get(user_key, {})
        if caller and caller != "unknown":
            if not c.get("datetime_iso"):
                body = f"{BUSINESS['name']}: " + render_msg(lang, "recovery", link=RECOVERY_BOOKING_LINK)
                send_once_for_call(call_sid, "recovery", caller, body)

    return Response(content="ok", media_type="text/plain")


# =========================
# SMS (incoming) - REST reply (no TwiML)
# =========================
@app.post("/sms/incoming")
async def sms_incoming(request: Request):
    form = await request.form()
    from_number = str(form.get("From", ""))
    body_in = str(form.get("Body", "")).strip()

    allowed, _ = client_allowed()
    if not allowed:
        lang = detect_language(body_in) or "en"
        send_message(from_number, f"{BUSINESS['name']}: {not_available_message(lang)}")
        return Response(content="ok", media_type="text/plain")

    user_key = norm_user_key(from_number)
    lang_hint = detect_language(body_in)

    result = handle_user_text(
        user_key=user_key,
        text=body_in,
        channel="sms",
        lang_hint=lang_hint,
        raw_phone=from_number,
    )

    out = result.get("msg_out") or render_msg(get_lang(lang_hint), "recovery", link=RECOVERY_BOOKING_LINK)
    send_message(from_number, f"{BUSINESS['name']}: {out}")
    return Response(content="ok", media_type="text/plain")


# =========================
# WHATSAPP (incoming) - TwiML reply (prevents "ok" + duplicate)
# =========================
@app.post("/whatsapp/incoming")
async def whatsapp_incoming(request: Request):
    form = await request.form()
    from_number = str(form.get("From", ""))  # e.g. 'whatsapp:+371...'
    body_in = str(form.get("Body", "")).strip()

    resp = MessagingResponse()

    allowed, _ = client_allowed()
    if not allowed:
        lang = detect_language(body_in) or "en"
        resp.message(f"{BUSINESS['name']}: {not_available_message(lang)}")
        return Response(str(resp), media_type="application/xml")

    user_key = norm_user_key(from_number)
    lang_hint = detect_language(body_in)

    result = handle_user_text(
        user_key=user_key,
        text=body_in,
        channel="whatsapp",
        lang_hint=lang_hint,
        raw_phone=from_number,
    )

    out = result.get("msg_out") or render_msg(get_lang(lang_hint), "recovery", link=RECOVERY_BOOKING_LINK)
    resp.message(f"{BUSINESS['name']}: {out}")
    return Response(str(resp), media_type="application/xml")
