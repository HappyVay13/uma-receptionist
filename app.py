import os
import json
import re
import urllib.parse
import base64
from datetime import datetime, timedelta, timezone, date
from typing import Dict, Any, Optional, Tuple, List

import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, StreamingResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client as TwilioClient
from sqlalchemy import text

# Google APIs
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Postgres
from db.database import engine, SessionLocal


app = FastAPI()

# =========================
# CONFIG
# =========================
TZ = timezone(timedelta(hours=2))  # Europe/Riga (+02:00)

# Multi-tenant MVP: one default tenant id
TENANT_ID_DEFAULT = (os.getenv("DEFAULT_CLIENT_ID", "default") or "default").strip()

# Business defaults (can be overridden per-tenant later)
BUSINESS = {
    "name": os.getenv("BIZ_NAME", "Repliq").strip(),
    "address": os.getenv("BIZ_ADDRESS", "Rēzekne").strip(),
    "hours": os.getenv("BIZ_HOURS", "09:00 - 18:00").strip(),
    "services": os.getenv("BIZ_SERVICES", "vīriešu un sieviešu frizūra").strip(),
}

# Recovery link
RECOVERY_BOOKING_LINK = os.getenv("RECOVERY_BOOKING_LINK", "https://repliq.app/book").strip()

# Appointments
APPT_MINUTES = int(os.getenv("APPT_MINUTES", "30"))
WORK_START_HHMM = os.getenv("WORK_START_HHMM", "09:00").strip()
WORK_END_HHMM = os.getenv("WORK_END_HHMM", "18:00").strip()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

# Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()

# Google Calendar
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "").strip()

# Google TTS
GOOGLE_TTS_VOICE_NAME = (
    os.getenv("GOOGLE_TTS_VOICE_NAME", "").strip()
    or os.getenv("GOOGLE_TTS_VOICE", "").strip()
    or "lv-LV-Standard-A"
)
GOOGLE_TTS_LANGUAGE_CODE = os.getenv("GOOGLE_TTS_LANGUAGE_CODE", "lv-LV").strip()
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "").strip().rstrip("/")

# ElevenLabs (optional)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()

# Trial/active/inactive
CLIENT_STATUS = (os.getenv("CLIENT_STATUS", "trial") or "trial").strip().lower()  # trial|active|inactive
TRIAL_END_ISO = (os.getenv("TRIAL_END_ISO", "") or "").strip()


# =========================
# TIME HELPERS
# =========================
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

TRIAL_END_DT = parse_dt_any_tz(TRIAL_END_ISO)

def client_allowed() -> Tuple[bool, str]:
    st = (CLIENT_STATUS or "trial").lower()
    if st == "inactive":
        return False, "inactive"
    if st == "trial":
        if TRIAL_END_DT and now_ts() > TRIAL_END_DT:
            return False, "trial_expired"
    return True, "ok"


# =========================
# BASIC UTILS
# =========================
def twiml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")

def _short(s: Optional[str], n: int) -> str:
    return (s or "").strip()[:n]

def _parse_hhmm(hhmm: str) -> Tuple[int, int]:
    hh, mm = hhmm.split(":")
    return int(hh), int(mm)

def get_lang(value: Optional[str]) -> str:
    return value if value in ("en", "ru", "lv") else "lv"

def stt_locale_for_lang(lang: str) -> str:
    lang = get_lang(lang)
    if lang == "ru":
        return "ru-RU"
    if lang == "lv":
        return "lv-LV"
    return "en-US"

def norm_user_key(phone: str) -> str:
    p = (phone or "").strip()
    p = p.replace("whatsapp:", "")
    p = re.sub(r"[^\d+]", "", p)
    return p or "unknown"

def detect_language(text_: str) -> str:
    t = (text_ or "").strip().lower()
    if re.search(r"[āēīūčšžģķļņĀĒĪŪČŠŽĢĶĻŅ]", t):
        return "lv"
    if re.search(r"[а-яА-Я]", t):
        return "ru"
    # LV without diacritics (common)
    lv_tokens = [
        "labdien", "sveiki", "ludzu", "paldies", "pierakst", "pieraksts",
        "rit", "parit", "sodien", "cikos", "kad", "diena", "gribu", "velos", "vajag"
    ]
    score = sum(1 for tok in lv_tokens if tok in t)
    return "lv" if score >= 2 else "en"


# =========================
# DB: TENANT SEED (FIX FOR FK)
# =========================
def _tenants_pk_column() -> Optional[str]:
    """
    Detects PK-like column name in tenants table.
    Returns "id" or "tenant_id" if exists, else None.
    """
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='tenants'
        """)).fetchall()
    cols = {r[0] for r in rows}
    if "id" in cols:
        return "id"
    if "tenant_id" in cols:
        return "tenant_id"
    return None

def ensure_tenant(tenant_id: str):
    """
    Ensures row exists in tenants for FK integrity.
    Works even if tenants PK column is id or tenant_id.
    """
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    pk = _tenants_pk_column()
    if not pk:
        # If table tenants exists but unknown pk naming, do nothing (safer) — but FK would still fail.
        # Better to raise a clear error:
        raise RuntimeError("Cannot detect tenants PK column (expected id or tenant_id).")

    sql = f"INSERT INTO tenants ({pk}) VALUES (:tid) ON CONFLICT ({pk}) DO NOTHING"
    with engine.begin() as conn:
        conn.execute(text(sql), {"tid": tenant_id})


@app.on_event("startup")
def _startup():
    # Ensure default tenant exists to satisfy FK: conversations.tenant_id -> tenants
    ensure_tenant(TENANT_ID_DEFAULT)


# =========================
# DB: CONVERSATIONS (RAW SQL, matches your schema)
# =========================
def db_get_or_create_conv(tenant_id: str, user_key: str, default_lang: str) -> Dict[str, Any]:
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    ensure_tenant(tenant_id)

    user_key = norm_user_key(user_key)
    default_lang = get_lang(default_lang)

    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT tenant_id, user_key, lang_lock, state, service, name, datetime_iso, time_text, pending_json
            FROM conversations
            WHERE tenant_id=:tid AND user_key=:uk
            LIMIT 1
        """), {"tid": tenant_id, "uk": user_key}).fetchone()

        if row:
            pending = None
            if row[8]:
                try:
                    pending = json.loads(row[8])
                except Exception:
                    pending = None
            return {
                "lang": get_lang(row[2]),
                "state": row[3],
                "service": row[4],
                "name": row[5],
                "datetime_iso": row[6],
                "time_text": row[7],
                "pending": pending,
            }

        conn.execute(text("""
            INSERT INTO conversations
            (tenant_id, user_key, lang_lock, state, service, name, datetime_iso, time_text, pending_json, updated_at)
            VALUES (:tid, :uk, :lang, 'NEW', NULL, NULL, NULL, NULL, NULL, NOW())
        """), {"tid": tenant_id, "uk": user_key, "lang": default_lang})

    return {
        "lang": default_lang,
        "state": "NEW",
        "service": None,
        "name": None,
        "datetime_iso": None,
        "time_text": None,
        "pending": None,
    }

def db_save_conv(tenant_id: str, user_key: str, c: Dict[str, Any]):
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    ensure_tenant(tenant_id)

    user_key = norm_user_key(user_key)

    pending_json = None
    if c.get("pending"):
        pending_json = json.dumps(c["pending"], ensure_ascii=False)

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE conversations
            SET lang_lock=:lang,
                state=:state,
                service=:service,
                name=:name,
                datetime_iso=:dtiso,
                time_text=:tt,
                pending_json=:pj,
                updated_at=NOW()
            WHERE tenant_id=:tid AND user_key=:uk
        """), {
            "tid": tenant_id,
            "uk": user_key,
            "lang": get_lang(c.get("lang")),
            "state": c.get("state") or "NEW",
            "service": c.get("service"),
            "name": c.get("name"),
            "dtiso": c.get("datetime_iso"),
            "tt": c.get("time_text"),
            "pj": pending_json,
        })


# =========================
# TWILIO MESSAGING
# =========================
def _twilio_client() -> Optional[TwilioClient]:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        return None
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def send_message(to_number: str, body: str):
    client = _twilio_client()
    if not client:
        print("Message skipped: Twilio creds missing")
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
# GOOGLE CALENDAR
# =========================
_GCAL = None

def get_gcal():
    global _GCAL
    if _GCAL is not None:
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
        print("GCAL init error:", repr(e))
        return None

def is_slot_busy(dt_start: datetime, dt_end: datetime) -> bool:
    svc = get_gcal()
    if svc is None or not GOOGLE_CALENDAR_ID:
        return False
    try:
        body = {"timeMin": dt_start.isoformat(), "timeMax": dt_end.isoformat(), "items": [{"id": GOOGLE_CALENDAR_ID}]}
        fb = svc.freebusy().query(body=body).execute()
        busy = fb["calendars"][GOOGLE_CALENDAR_ID].get("busy", [])
        return len(busy) > 0
    except Exception as e:
        print("GCAL freebusy error:", repr(e))
        return False

def create_calendar_event(dt_start: datetime, duration_min: int, summary: str, description: str) -> Optional[str]:
    svc = get_gcal()
    if svc is None or not GOOGLE_CALENDAR_ID:
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

def in_business_hours(dt_start: datetime, duration_min: int) -> bool:
    ws_h, ws_m = _parse_hhmm(WORK_START_HHMM)
    we_h, we_m = _parse_hhmm(WORK_END_HHMM)
    day_start = dt_start.replace(hour=ws_h, minute=ws_m, second=0, microsecond=0)
    day_end = dt_start.replace(hour=we_h, minute=we_m, second=0, microsecond=0)
    dt_end = dt_start + timedelta(minutes=duration_min)
    return (dt_start >= day_start) and (dt_end <= day_end)

def find_next_two_slots(dt_start: datetime, duration_min: int) -> Optional[Tuple[datetime, datetime]]:
    step = 30
    candidate = dt_start + timedelta(minutes=step)
    found: List[datetime] = []
    for _ in range(48):
        if in_business_hours(candidate, duration_min):
            if not is_slot_busy(candidate, candidate + timedelta(minutes=duration_min)):
                found.append(candidate)
                if len(found) == 2:
                    return found[0], found[1]
        candidate = candidate + timedelta(minutes=step)
    return None


# =========================
# GOOGLE TTS + ELEVEN
# =========================
_TTS = None

def google_tts_enabled() -> bool:
    return bool(GOOGLE_SERVICE_ACCOUNT_JSON and SERVER_BASE_URL)

def get_google_tts():
    global _TTS
    if _TTS is not None:
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
        print("TTS init error:", repr(e))
        return None

def google_tts_mp3(text_: str, lang_code: str, voice_name: str) -> bytes:
    svc = get_google_tts()
    if svc is None:
        return b""
    safe_text = (text_ or "").strip()
    if not safe_text:
        return b""
    if len(safe_text) > 350:
        safe_text = safe_text[:350]
    body = {
        "input": {"text": safe_text},
        "voice": {"languageCode": lang_code, "name": voice_name},
        "audioConfig": {"audioEncoding": "MP3"},
    }
    try:
        resp = svc.text().synthesize(body=body).execute()
        return base64.b64decode(resp["audioContent"])
    except Exception as e:
        print("Google TTS error:", repr(e))
        return b""

@app.get("/tts/google")
def tts_google(text: str):
    audio = google_tts_mp3(text, GOOGLE_TTS_LANGUAGE_CODE, GOOGLE_TTS_VOICE_NAME)
    if not audio:
        raise HTTPException(status_code=500, detail="Google TTS failed")
    return StreamingResponse(iter([audio]), media_type="audio/mpeg")

def eleven_enabled() -> bool:
    return bool(ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID and SERVER_BASE_URL)

def eleven_mp3(text_: str) -> bytes:
    if not (ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID):
        return b""
    safe_text = (text_ or "").strip()
    if not safe_text:
        return b""
    if len(safe_text) > 240:
        safe_text = safe_text[:240]

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    payload = {"text": safe_text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.4, "similarity_boost": 0.7}}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        if r.status_code == 200 and r.content:
            return r.content
        print("Eleven error:", r.status_code, r.text[:250])
        return b""
    except Exception as e:
        print("Eleven request error:", repr(e))
        return b""

@app.get("/tts/eleven")
def tts_eleven(text: str):
    audio = eleven_mp3(text)
    if not audio:
        raise HTTPException(status_code=500, detail="Eleven TTS failed")
    return StreamingResponse(iter([audio]), media_type="audio/mpeg")

def say_or_play(vr: VoiceResponse, text_: str, lang: str):
    t = (text_ or "").strip() or "OK."
    lang = get_lang(lang)

    if lang == "lv":
        q = urllib.parse.quote_plus(t)
        url = f"{SERVER_BASE_URL}/tts/google?text={q}" if SERVER_BASE_URL else ""
        if url:
            vr.play(url)
        else:
            vr.say(t, language="lv-LV")
        return

    if eleven_enabled():
        q = urllib.parse.quote_plus(t)
        vr.play(f"{SERVER_BASE_URL}/tts/eleven?text={q}")
        return

    if lang == "ru":
        vr.say(t, language="ru-RU")
    elif lang == "en":
        vr.say(t, language="en-US")
    else:
        vr.say(t)


# =========================
# DATE PARSING
# =========================
def parse_time_text_to_dt(text_: str) -> Optional[datetime]:
    if not text_:
        return None
    t = text_.lower()

    m = re.search(r"\b([01]?\d|2[0-3])[:. ]([0-5]\d)\b", t)
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2))

    base = today_local()

    # explicit ISO YYYY-MM-DD
    m_iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
    if m_iso:
        y, mo, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        try:
            base = date(y, mo, d)
        except ValueError:
            return None
    else:
        # explicit DD.MM(.YYYY)? or DD/MM(/YYYY)?
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
                    y = y + 1
            try:
                base = date(y, mo, d)
            except ValueError:
                return None
        else:
            if any(k in t for k in ["day after tomorrow", "послезавтра", "parīt", "parit"]):
                base = today_local() + timedelta(days=2)
            elif any(k in t for k in ["tomorrow", "завтра", "rīt", "rit"]):
                base = today_local() + timedelta(days=1)

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
        except Exception:
            pass
    combined = f"{time_text or ''} {raw_text or ''}".strip()
    return parse_time_text_to_dt(combined)


# =========================
# TEMPLATES
# =========================
MSG_TEMPLATES = {
    "lv": {
        "confirmed": "Pieraksts: {service} {time}. Adrese: {addr}. {link}",
        "busy": "Aizņemts. 1){opt1} 2){opt2}. Atbildi 1/2. {link}",
        "ask_service": "Kāds pakalpojums? Piem.: vīriešu frizūra. {link}",
        "ask_time": "Kad un cikos? Piem.: rīt 15:10. {link}",
        "ask_name": "Jūsu vārds? {link}",
        "recovery": "Pieraksts: {link}",
        "unavailable": "Atvainojiet, serviss pašlaik nav pieejams.",
    },
    "ru": {
        "confirmed": "Запись: {service} {time}. Адрес: {addr}. {link}",
        "busy": "Занято. 1){opt1} 2){opt2}. Ответ 1/2. {link}",
        "ask_service": "Какая услуга? Пример: мужская стрижка. {link}",
        "ask_time": "Когда и во сколько? Пример: завтра 15:10. {link}",
        "ask_name": "Как вас зовут? {link}",
        "recovery": "Запись: {link}",
        "unavailable": "Извините, сервис сейчас недоступен.",
    },
    "en": {
        "confirmed": "Booked: {service} {time}. Addr: {addr}. {link}",
        "busy": "Busy. 1){opt1} 2){opt2}. Reply 1/2. {link}",
        "ask_service": "Which service? Example: men's haircut. {link}",
        "ask_time": "When? Example: tomorrow 15:10. {link}",
        "ask_name": "Your name? {link}",
        "recovery": "Book: {link}",
        "unavailable": "Sorry, service is currently unavailable.",
    },
}

VOICE_TEXT = {
    "lv": {
        "need_service": "Kādu pakalpojumu vēlaties?",
        "need_time": "Kad un cikos jums būtu ērti?",
        "need_name": "Kā jūs sauc?",
        "confirmed": "Paldies! Pieraksts apstiprināts.",
        "busy": "Šis laiks ir aizņemts. Nosūtu alternatīvas ziņā.",
        "recovery": "Lūdzu, izmantojiet saiti pierakstam.",
        "outside_hours": "Atvainojiet, tas ir ārpus darba laika. Izvēlieties citu laiku.",
        "unavailable": "Atvainojiet, serviss pašlaik nav pieejams.",
    },
    "ru": {
        "need_service": "Какая услуга вам нужна?",
        "need_time": "Когда вам удобно?",
        "need_name": "Как вас зовут?",
        "confirmed": "Спасибо! Запись подтверждена.",
        "busy": "Это время занято. Я отправлю альтернативы сообщением.",
        "recovery": "Пожалуйста, используйте ссылку для записи.",
        "outside_hours": "Это вне рабочего времени. Выберите другое время.",
        "unavailable": "Извините, сервис сейчас недоступен.",
    },
    "en": {
        "need_service": "Which service do you need?",
        "need_time": "When would you like to come?",
        "need_name": "What is your name?",
        "confirmed": "Thanks! Your booking is confirmed.",
        "busy": "That time is busy. I'll send two alternatives by message.",
        "recovery": "Please use the booking link.",
        "outside_hours": "That's outside business hours. Please choose another time.",
        "unavailable": "Sorry, service is currently unavailable.",
    },
}

def render_msg(lang: str, key: str, **kwargs) -> str:
    lang = get_lang(lang)
    tmpl = MSG_TEMPLATES.get(lang, MSG_TEMPLATES["lv"]).get(key) or MSG_TEMPLATES["lv"][key]
    return tmpl.format(**kwargs)


# =========================
# CORE LOGIC
# =========================
def handle_user_text(tenant_id: str, raw_phone: str, text_: str, channel: str, lang_hint: str) -> Dict[str, Any]:
    msg = (text_ or "").strip()
    user_key = norm_user_key(raw_phone)

    if not lang_hint or lang_hint not in ("en", "ru", "lv"):
        lang_hint = detect_language(msg) if msg else "lv"

    c = db_get_or_create_conv(tenant_id, user_key, lang_hint)
    lang = get_lang(c.get("lang") or lang_hint)

    def finalize(result: Dict[str, Any]) -> Dict[str, Any]:
        c["lang"] = get_lang(result.get("lang") or c.get("lang") or lang)
        db_save_conv(tenant_id, user_key, c)
        return result

    # explicit language switch (simple)
    if msg:
        low = msg.lower()
        if any(x in low for x in ["latviski", "latviešu", "latviesu"]):
            lang = "lv"; c["lang"] = "lv"
        elif any(x in low for x in ["по-русски", "по русски", "русский", "krieviski"]):
            lang = "ru"; c["lang"] = "ru"
        elif any(x in low for x in ["english", "in english", "angliski"]):
            lang = "en"; c["lang"] = "en"

    # option 1/2 flow
    if msg in ("1", "2") and c.get("pending"):
        pending = c["pending"] or {}
        chosen_iso = pending.get("opt1_iso") if msg == "1" else pending.get("opt2_iso")

        dt_start = None
        if chosen_iso:
            try:
                dt_start = datetime.fromisoformat(chosen_iso)
                if dt_start.tzinfo is None:
                    dt_start = dt_start.replace(tzinfo=TZ)
                else:
                    dt_start = dt_start.astimezone(TZ)
            except Exception:
                dt_start = None

        if not dt_start:
            c["pending"] = None
            return finalize({
                "status": "need_more",
                "reply_voice": VOICE_TEXT[lang]["need_time"],
                "msg_out": render_msg(lang, "ask_time", link=RECOVERY_BOOKING_LINK),
                "lang": lang,
            })

        service = pending.get("service") or c.get("service") or BUSINESS["services"]
        name = pending.get("name") or c.get("name") or ("Klients" if lang == "lv" else ("Клиент" if lang == "ru" else "Client"))

        summary = f"{BUSINESS['name']} — {_short(service, 60)}"
        desc = f"Name: {name}\nPhone: {raw_phone}\nService: {service}\nSource: {channel} (option {msg})\n"
        create_calendar_event(dt_start, APPT_MINUTES, summary, desc)

        c["pending"] = None
        c["service"] = service
        c["name"] = name
        c["datetime_iso"] = dt_start.isoformat()
        c["time_text"] = dt_start.strftime("%Y-%m-%d %H:%M")

        when_str = dt_start.strftime("%d.%m %H:%M")
        return finalize({
            "status": "booked",
            "reply_voice": VOICE_TEXT[lang]["confirmed"],
            "msg_out": render_msg(lang, "confirmed", service=_short(service, 40), time=when_str, addr=_short(BUSINESS["address"], 35), link=RECOVERY_BOOKING_LINK),
            "lang": lang,
        })

    # OpenAI extraction
    data = {"service": None, "time_text": None, "datetime_iso": None, "name": None, "phone": None}
    if msg:
        system = f"""
You are Repliq, an AI receptionist.

Business:
- Name: {BUSINESS['name']}
- Hours: {BUSINESS['hours']}
- Services: {BUSINESS['services']}

Return STRICT JSON with keys:
service: string|null
time_text: string|null
datetime_iso: string|null   # ISO 8601 with Europe/Riga timezone (+02:00)
name: string|null
phone: string|null
Rules:
- Convert relative dates (rīt/parīt/tomorrow/day after tomorrow) when possible.
- If unclear, set datetime_iso=null.
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

    if data.get("service"):
        c["service"] = data["service"]
    if data.get("name"):
        c["name"] = data["name"]

    dt_start = parse_dt_from_iso_or_fallback(data.get("datetime_iso"), data.get("time_text"), msg)
    if dt_start:
        c["datetime_iso"] = dt_start.isoformat()
        c["time_text"] = dt_start.strftime("%Y-%m-%d %H:%M")

    if not c.get("service"):
        return finalize({
            "status": "need_more",
            "reply_voice": VOICE_TEXT[lang]["need_service"],
            "msg_out": render_msg(lang, "ask_service", link=RECOVERY_BOOKING_LINK),
            "lang": lang,
        })

    if not dt_start:
        return finalize({
            "status": "need_more",
            "reply_voice": VOICE_TEXT[lang]["need_time"],
            "msg_out": render_msg(lang, "ask_time", link=RECOVERY_BOOKING_LINK),
            "lang": lang,
        })

    if not c.get("name"):
        return finalize({
            "status": "need_more",
            "reply_voice": VOICE_TEXT[lang]["need_name"],
            "msg_out": render_msg(lang, "ask_name", link=RECOVERY_BOOKING_LINK),
            "lang": lang,
        })

    if not in_business_hours(dt_start, APPT_MINUTES):
        return finalize({
            "status": "need_more",
            "reply_voice": VOICE_TEXT[lang]["outside_hours"],
            "msg_out": render_msg(lang, "ask_time", link=RECOVERY_BOOKING_LINK),
            "lang": lang,
        })

    dt_end = dt_start + timedelta(minutes=APPT_MINUTES)
    if is_slot_busy(dt_start, dt_end):
        opts = find_next_two_slots(dt_start, APPT_MINUTES)
        if opts:
            opt1, opt2 = opts
            c["pending"] = {"opt1_iso": opt1.isoformat(), "opt2_iso": opt2.isoformat(), "service": c.get("service"), "name": c.get("name")}
            return finalize({
                "status": "busy",
                "reply_voice": VOICE_TEXT[lang]["busy"],
                "msg_out": render_msg(lang, "busy", opt1=opt1.strftime("%d.%m %H:%M"), opt2=opt2.strftime("%d.%m %H:%M"), link=RECOVERY_BOOKING_LINK),
                "lang": lang,
            })
        return finalize({
            "status": "recovery",
            "reply_voice": VOICE_TEXT[lang]["recovery"],
            "msg_out": render_msg(lang, "recovery", link=RECOVERY_BOOKING_LINK),
            "lang": lang,
        })

    service = c.get("service") or BUSINESS["services"]
    name = c.get("name") or ("Klients" if lang == "lv" else ("Клиент" if lang == "ru" else "Client"))

    summary = f"{BUSINESS['name']} — {_short(service, 60)}"
    desc = f"Name: {name}\nPhone: {raw_phone}\nService: {service}\nOriginal: {msg}\nSource: {channel}\n"
    create_calendar_event(dt_start, APPT_MINUTES, summary, desc)

    when_str = dt_start.strftime("%d.%m %H:%M")
    return finalize({
        "status": "booked",
        "reply_voice": VOICE_TEXT[lang]["confirmed"],
        "msg_out": render_msg(lang, "confirmed", service=_short(service, 40), time=when_str, addr=_short(BUSINESS["address"], 35), link=RECOVERY_BOOKING_LINK),
        "lang": lang,
    })


# =========================
# HEALTH / DEBUG
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
        "google_tts_enabled": google_tts_enabled(),
        "google_tts_voice": GOOGLE_TTS_VOICE_NAME,
        "eleven_enabled": eleven_enabled(),
        "tenant_default": TENANT_ID_DEFAULT,
    }

@app.get("/debug/db")
def debug_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema='public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
        return {"db_connected": True, "tables": tables}
    except Exception as e:
        return {"db_connected": False, "error": str(e)}

@app.get("/debug/tenants")
def debug_tenants():
    try:
        pk = _tenants_pk_column()
        if not pk:
            return {"ok": False, "error": "cannot detect tenants pk"}
        with engine.connect() as conn:
            rows = conn.execute(text(f"SELECT {pk} FROM tenants ORDER BY {pk} LIMIT 50")).fetchall()
        return {"ok": True, "pk": pk, "tenants": [r[0] for r in rows]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# =========================
# ROUTES: VOICE
# =========================
CALL_SESSIONS: Dict[str, Dict[str, Any]] = {}

def cleanup_call_sessions():
    cutoff = now_ts() - timedelta(minutes=60)
    dead = []
    for sid, s in CALL_SESSIONS.items():
        try:
            created = datetime.fromisoformat(s.get("created_at"))
        except Exception:
            created = now_ts()
        if created < cutoff:
            dead.append(sid)
    for sid in dead:
        CALL_SESSIONS.pop(sid, None)

def get_call_session(call_sid: str) -> Dict[str, Any]:
    s = CALL_SESSIONS.get(call_sid)
    if not s:
        s = {"created_at": now_ts().isoformat(), "lang": None, "sms_flags": {}}
        CALL_SESSIONS[call_sid] = s
    return s

def send_sms_once_for_call(call_sid: str, key: str, to_number: str, body: str):
    s = get_call_session(call_sid)
    flags = s.setdefault("sms_flags", {})
    if flags.get(key):
        return
    send_message(to_number, body)
    flags[key] = True

@app.post("/voice/incoming")
async def voice_incoming(request: Request):
    cleanup_call_sessions()
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    caller = str(form.get("From", ""))

    allowed, _reason = client_allowed()
    cs = get_call_session(call_sid)
    cs["caller"] = caller

    vr = VoiceResponse()

    if not allowed:
        say_or_play(vr, VOICE_TEXT["lv"]["unavailable"], "lv")
        vr.hangup()
        return twiml(vr)

    g = Gather(
        input="speech dtmf",
        num_digits=1,
        action="/voice/intent",
        method="POST",
        timeout=7,
        speech_timeout="auto",
        language="lv-LV",
    )
    say_or_play(g, f"Labdien! Jūs sazvanījāt {BUSINESS['name']}.", "lv")
    g.say("Ja vēlaties: 1 angliski, 2 krieviski, 3 latviski.", language="lv-LV")
    g.say("Lūdzu, pasakiet, ko vēlaties pierakstīt.", language="lv-LV")
    vr.append(g)

    say_or_play(vr, "Atvainojiet, es jūs nedzirdēju. Uz redzēšanos!", "lv")
    return twiml(vr)

@app.post("/voice/intent")
async def voice_intent(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    caller = str(form.get("From", ""))
    speech = str(form.get("SpeechResult", "")).strip()
    digits = str(form.get("Digits", "")).strip()

    allowed, _reason = client_allowed()
    cs = get_call_session(call_sid)
    user_phone = caller or "unknown"

    vr = VoiceResponse()
    if not allowed:
        say_or_play(vr, VOICE_TEXT["lv"]["unavailable"], "lv")
        vr.hangup()
        return twiml(vr)

    if digits in ("1", "2", "3"):
        cs["lang"] = "en" if digits == "1" else ("ru" if digits == "2" else "lv")

    if not cs.get("lang"):
        cs["lang"] = detect_language(speech) if speech else "lv"

    lang = get_lang(cs.get("lang"))

    result = handle_user_text(
        tenant_id=TENANT_ID_DEFAULT,
        raw_phone=user_phone,
        text_=speech,
        channel="voice",
        lang_hint=lang,
    )

    cs["lang"] = get_lang(result.get("lang") or lang)
    say_or_play(vr, result.get("reply_voice") or "Labi.", cs["lang"])

    if result.get("status") == "need_more":
        g = Gather(
            input="speech",
            action="/voice/intent",
            method="POST",
            timeout=7,
            speech_timeout="auto",
            language=stt_locale_for_lang(cs["lang"]),
        )
        if cs["lang"] == "lv":
            g.say("Turpiniet, lūdzu.", language="lv-LV")
        elif cs["lang"] == "ru":
            g.say("Продолжайте, пожалуйста.", language="ru-RU")
        else:
            g.say("Please continue.", language="en-US")
        vr.append(g)
        say_or_play(vr, "Atvainojiet, es jūs nedzirdēju. Uz redzēšanos!", cs["lang"])
    else:
        vr.hangup()

    msg_out = result.get("msg_out")
    if msg_out and user_phone and user_phone != "unknown":
        send_sms_once_for_call(call_sid, f"{result.get('status','x')}", user_phone, f"{BUSINESS['name']}: {msg_out}")

    return twiml(vr)


# =========================
# ROUTES: SMS
# =========================
@app.post("/sms/incoming")
async def sms_incoming(request: Request):
    form = await request.form()
    from_number = str(form.get("From", ""))
    body_in = str(form.get("Body", "")).strip()

    allowed, _reason = client_allowed()
    if not allowed:
        lang = detect_language(body_in) if body_in else "lv"
        send_message(from_number, f"{BUSINESS['name']}: {MSG_TEMPLATES[get_lang(lang)]['unavailable']}")
        return Response(content="ok", media_type="text/plain")

    lang_hint = detect_language(body_in) if body_in else "lv"
    result = handle_user_text(TENANT_ID_DEFAULT, from_number, body_in, "sms", lang_hint)

    msg_out = result.get("msg_out") or render_msg(get_lang(result.get("lang")), "recovery", link=RECOVERY_BOOKING_LINK)
    send_message(from_number, f"{BUSINESS['name']}: {msg_out}")
    return Response(content="ok", media_type="text/plain")


# =========================
# ROUTES: WHATSAPP
# =========================
@app.post("/whatsapp/incoming")
async def whatsapp_incoming(request: Request):
    form = await request.form()
    from_number = str(form.get("From", ""))  # whatsapp:+371...
    body_in = str(form.get("Body", "")).strip()

    allowed, _reason = client_allowed()
    if not allowed:
        lang = detect_language(body_in) if body_in else "lv"
        send_message(from_number, f"{BUSINESS['name']}: {MSG_TEMPLATES[get_lang(lang)]['unavailable']}")
        return Response(content="ok", media_type="text/plain")

    # keep lang sticky for "1"/"2"
    if body_in in ("1", "2"):
        c = db_get_or_create_conv(TENANT_ID_DEFAULT, norm_user_key(from_number), "lv")
        lang_hint = c.get("lang") or "lv"
    else:
        lang_hint = detect_language(body_in) if body_in else "lv"

    result = handle_user_text(TENANT_ID_DEFAULT, from_number, body_in, "whatsapp", get_lang(lang_hint))

    msg_out = result.get("msg_out") or render_msg(get_lang(result.get("lang")), "recovery", link=RECOVERY_BOOKING_LINK)
    send_message(from_number, f"{BUSINESS['name']}: {msg_out}")
    return Response(content="ok", media_type="text/plain")
