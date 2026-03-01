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

from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleAuthRequest

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
    "services": os.getenv("BIZ_SERVICES", "matu griezumi"),  # лучше держать нейтрально/не RU
}

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

# SMS sender (regular phone number, e.g. +371...)
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

# WhatsApp sender (sandbox or approved WA sender)
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")  # e.g. "whatsapp:+14155238886"

# Google Calendar
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "")

# Google Cloud TTS (Latvian)
# Можно положить тот же service account JSON, что и для календаря
GOOGLE_TTS_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_TTS_SERVICE_ACCOUNT_JSON", "") or GOOGLE_SERVICE_ACCOUNT_JSON
GOOGLE_TTS_VOICE = os.getenv("GOOGLE_TTS_VOICE", "lv-LV-Wavenet-B")  # мужской/официальный
GOOGLE_TTS_AUDIO = os.getenv("GOOGLE_TTS_AUDIO", "MP3")  # MP3 / OGG_OPUS / LINEAR16

# ElevenLabs (EN/RU можно оставить потом)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "").strip().rstrip("/")

# -------------------------
# Trial / Active / Inactive
# -------------------------
CLIENT_STATUS = os.getenv("CLIENT_STATUS", "trial").strip().lower()  # trial | active | inactive
TRIAL_END_ISO = os.getenv("TRIAL_END_ISO", "").strip()

def now_ts() -> datetime:
    return datetime.now(TZ)

def today_local() -> date:
    return datetime.now(TZ).date()

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

def get_lang(value: Optional[str]) -> str:
    return value if value in ("en", "ru", "lv") else "lv"  # по умолчанию LV

def detect_language(text: str) -> str:
    t = text or ""
    if re.search(r"[āēīūčšžģķļņĀĒĪŪČŠŽĢĶĻŅ]", t):
        return "lv"
    if re.search(r"[а-яА-Я]", t):
        return "ru"
    return "en"

def stt_locale_for_lang(lang: str) -> str:
    lang = get_lang(lang)
    if lang == "ru":
        return "ru-RU"
    if lang == "lv":
        return "lv-LV"
    return "en-US"

def not_available_message(lang: str) -> str:
    lang = get_lang(lang)
    if lang == "lv":
        return "Atvainojiet, šis numurs pašlaik nav pieejams."
    if lang == "ru":
        return "Извините, этот номер сейчас недоступен."
    return "Sorry, this number is currently unavailable."

# =========================
# COPY (Voice + Msg)
# =========================
VOICE_TEXT = {
    "lv": {
        "greet_1": "Labdien! Jūs esat sazvanījis Repliq.",
        "greet_2": "Kā varu palīdzēt?",
        "lang_hint": "Ja vēlaties, nospiediet: 1 angliski, 2 krieviski, 3 latviski.",
        "no_hear": "Atvainojiet, nedzirdēju. Uz redzēšanos.",
        "ask_more": "Lūdzu, turpiniet.",
        "confirm_voice": "Paldies! Pierakstu apstiprinājumu nosūtīšu ziņā.",
        "busy_voice": "Šis laiks ir aizņemts. Nosūtīju alternatīvas ziņā.",
        "ask_service": "Kāds pakalpojums jums nepieciešams?",
        "ask_time": "Kurā dienā un cikos jums ir ērti?",
        "ask_name": "Kā jūs sauc?",
    },
    "en": {
        "greet_1": "Hello! You reached Repliq.",
        "greet_2": "How can I help you?",
        "lang_hint": "If you prefer: press 1 English, 2 Russian, 3 Latvian.",
        "no_hear": "Sorry, I could not hear you. Goodbye.",
        "ask_more": "Please continue.",
        "confirm_voice": "Thank you. I will send confirmation by message.",
        "busy_voice": "That time is busy. I sent options by message.",
        "ask_service": "Which service do you need?",
        "ask_time": "What day and time works for you?",
        "ask_name": "What is your name?",
    },
    "ru": {
        "greet_1": "Здравствуйте! Вы позвонили в Repliq.",
        "greet_2": "Чем могу помочь?",
        "lang_hint": "Если хотите: нажмите 1 английский, 2 русский, 3 латышский.",
        "no_hear": "Извините, не расслышала. До свидания.",
        "ask_more": "Пожалуйста, продолжайте.",
        "confirm_voice": "Спасибо! Подтверждение отправлю сообщением.",
        "busy_voice": "Это время занято. Отправила варианты сообщением.",
        "ask_service": "Какая услуга вам нужна?",
        "ask_time": "На какой день и время вам удобно?",
        "ask_name": "Как вас зовут?",
    },
}

SMS_TEMPLATES = {
    "lv": {
        "confirmed": "Pieraksts: {service} {time}. Adrese: {addr}. {link}",
        "busy": "Aizņemts. 1){opt1} 2){opt2}. Atbildi 1/2. {link}",
        "ask_service": "Kāds pakalpojums? Piem.: vīriešu frizūra. {link}",
        "ask_time": "Kad? Piem.: rīt 15:10. {link}",
        "ask_name": "Jūsu vārds? {link}",
        "recovery": "Pieraksts: {link}",
    },
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
}

# =========================
# STORAGE (in-memory MVP)
# =========================
CALL_SESSIONS: Dict[str, Dict[str, Any]] = {}
CONV: Dict[str, Dict[str, Any]] = {}
_GCAL = None
_G_TTS_TOKEN_CACHE: Dict[str, Any] = {"token": None, "exp": None}

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
        s = {"created_at": now_ts().isoformat(), "lang": None, "sms_flags": {}}
        CALL_SESSIONS[call_sid] = s
    return s

def twiml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")

def norm_user_key(phone: str) -> str:
    p = (phone or "").strip()
    p = p.replace("whatsapp:", "")
    p = re.sub(r"[^\d+]", "", p)
    return p or "unknown"

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

def send_once_for_call(call_sid: str, key: str, to_number: str, body: str):
    s = get_call_session(call_sid)
    flags = s.setdefault("sms_flags", {})
    if flags.get(key):
        return
    send_message(to_number, body)
    flags[key] = True

def render_sms(lang: str, key: str, **kwargs) -> str:
    lang = get_lang(lang)
    tmpl = SMS_TEMPLATES.get(lang, SMS_TEMPLATES["en"]).get(key, SMS_TEMPLATES["en"][key])
    return tmpl.format(**kwargs)

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
# OPENAI (extract)
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
# DATETIME PARSING (fallback)
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

    m_iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
    if m_iso:
        y, mo, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        try:
            base = date(y, mo, d)
        except ValueError:
            return None
    else:
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
            if any(k in t for k in ["day after tomorrow", "послезавтра", "parīt", "parit"]):
                base = base + timedelta(days=2)
            elif any(k in t for k in ["tomorrow", "завтра", "rīt", "rit"]):
                base = base + timedelta(days=1)
            else:
                m_ru = re.search(r"через\s+(\d{1,2})\s*(дн|дня|дней)", t)
                m_en = re.search(r"\bin\s+(\d{1,2})\s+days\b", t)
                m_lv = re.search(r"pēc\s+(\d{1,2})\s+dien", t)
                if m_ru:
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
        body = {"timeMin": dt_start.isoformat(), "timeMax": dt_end.isoformat(), "items": [{"id": GOOGLE_CALENDAR_ID}]}
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
    for _ in range(48):  # ~24h
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
# GOOGLE CLOUD TTS (Latvian) via REST + OAuth token from Service Account
# =========================
def gtts_enabled() -> bool:
    return bool(GOOGLE_TTS_SERVICE_ACCOUNT_JSON and SERVER_BASE_URL)

def _get_gtts_access_token() -> Optional[str]:
    if not GOOGLE_TTS_SERVICE_ACCOUNT_JSON:
        return None
    # cache ~50 min
    token = _G_TTS_TOKEN_CACHE.get("token")
    exp = _G_TTS_TOKEN_CACHE.get("exp")
    if token and exp and now_ts() < exp:
        return token

    try:
        info = json.loads(GOOGLE_TTS_SERVICE_ACCOUNT_JSON)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        req = GoogleAuthRequest()
        creds.refresh(req)
        token = creds.token
        # set exp ~50 minutes from now
        _G_TTS_TOKEN_CACHE["token"] = token
        _G_TTS_TOKEN_CACHE["exp"] = now_ts() + timedelta(minutes=50)
        return token
    except Exception as e:
        print("GTTS token error:", repr(e))
        return None

def generate_google_tts_mp3(text: str, lang: str = "lv") -> bytes:
    if not GOOGLE_TTS_SERVICE_ACCOUNT_JSON:
        return b""
    token = _get_gtts_access_token()
    if not token:
        return b""

    safe = (text or "").strip()
    if not safe:
        return b""
    if len(safe) > 260:
        safe = safe[:260]

    # Latvian voice selection
    # If later you найдёшь женский LV голос в списке Google, просто поменяй GOOGLE_TTS_VOICE env
    body = {
        "input": {"text": safe},
        "voice": {"languageCode": "lv-LV", "name": GOOGLE_TTS_VOICE},
        "audioConfig": {"audioEncoding": GOOGLE_TTS_AUDIO},
    }

    try:
        r = requests.post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            timeout=20,
        )
        if r.status_code != 200:
            print("GTTS synth error:", r.status_code, r.text[:250])
            return b""
        data = r.json()
        audio_b64 = data.get("audioContent")
        if not audio_b64:
            return b""
        return base64.b64decode(audio_b64)
    except Exception as e:
        print("GTTS request error:", repr(e))
        return b""

@app.get("/gtts")
def gtts(text: str):
    if not GOOGLE_TTS_SERVICE_ACCOUNT_JSON:
        raise HTTPException(status_code=503, detail="Google TTS not configured")
    audio = generate_google_tts_mp3(text, "lv")
    if not audio:
        raise HTTPException(status_code=500, detail="TTS failed")
    return StreamingResponse(iter([audio]), media_type="audio/mpeg")

# =========================
# ELEVEN (optional for EN/RU)
# =========================
def eleven_enabled() -> bool:
    return bool(ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID and SERVER_BASE_URL)

def generate_eleven_audio(text: str) -> bytes:
    if not (ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID):
        return b""
    safe_text = (text or "").strip()
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
        print("ElevenLabs error:", r.status_code, r.text[:200])
        return b""
    except Exception as e:
        print("ElevenLabs request error:", repr(e))
        return b""

@app.get("/tts")
def tts(text: str):
    if not (ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID):
        raise HTTPException(status_code=503, detail="ElevenLabs not configured")
    audio = generate_eleven_audio(text)
    if not audio:
        raise HTTPException(status_code=500, detail="TTS generation failed")
    return StreamingResponse(iter([audio]), media_type="audio/mpeg")

def say_or_play(vr_or_gather, text: str, lang: str):
    """
    Главная функция голоса:
      - LV: Google TTS -> <Play> (красиво)
      - RU/EN: ElevenLabs если настроен, иначе Twilio Say
    """
    t = (text or "").strip() or "OK."
    lang = get_lang(lang)

    # Latvian via Google TTS (Play)
    if lang == "lv" and gtts_enabled():
        q = urllib.parse.quote_plus(t)
        url = f"{SERVER_BASE_URL}/gtts?text={q}"
        vr_or_gather.play(url)
        return

    # EN/RU via ElevenLabs (Play)
    if lang in ("en", "ru") and eleven_enabled():
        q = urllib.parse.quote_plus(t)
        url = f"{SERVER_BASE_URL}/tts?text={q}"
        vr_or_gather.play(url)
        return

    # fallback Twilio Say
    if lang == "lv":
        vr_or_gather.say(t, language="lv-LV")
    elif lang == "ru":
        vr_or_gather.say(t, language="ru-RU")
    else:
        vr_or_gather.say(t)

# =========================
# CONVERSATION (unified)
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

    # не перетираем язык, если сообщение это просто "1" или "2"
    if default_lang in ("en", "ru", "lv"):
        c["lang"] = get_lang(default_lang)

    c["updated_at"] = now_ts().isoformat()
    return c

def handle_user_text(user_key: str, text: str, channel: str, lang_hint: Optional[str], raw_phone: str) -> Dict[str, Any]:
    msg = (text or "").strip()

    # Если это выбор 1/2 — не делаем detect_language("1") => en
    if msg in ("1", "2"):
        c_existing = CONV.get(user_key)
        if c_existing and c_existing.get("lang") in ("en", "ru", "lv"):
            lang_hint = c_existing["lang"]

    if not lang_hint or lang_hint not in ("en", "ru", "lv"):
        lang_hint = detect_language(msg)

    c = get_conv(user_key, lang_hint)
    lang = get_lang(c.get("lang"))

    c["history"].append({"ts": now_ts().isoformat(), "channel": channel, "text": msg})

    # 0) option selection
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
                "reply_voice": VOICE_TEXT[lang]["ask_time"],
                "sms_out": render_sms(lang, "ask_time", link=RECOVERY_BOOKING_LINK),
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

        when_str = dt_start.strftime("%d.%m %H:%M")
        sms_out = render_sms(lang, "confirmed", service=_short(service, 40), time=when_str, addr=_short(BUSINESS.get("address"), 35), link=RECOVERY_BOOKING_LINK)
        return {"status": "booked", "reply_voice": VOICE_TEXT[lang]["confirm_voice"], "sms_out": sms_out, "lang": lang}

    # 1) OpenAI extraction
    system = f"""
You are Repliq, an AI receptionist for a small business.

Business:
- Name: {BUSINESS['name']}
- Hours: {BUSINESS['hours']}
- Services: {BUSINESS['services']}

Return STRICT JSON with keys:
service: string|null
time_text: string|null
datetime_iso: string|null   # ISO 8601 with timezone offset, e.g. 2026-02-27T15:10:00+02:00
name: string|null
phone: string|null

Rules:
- Convert relative dates: tomorrow / day after tomorrow / rīt / parīt / завтра / послезавтра.
- If unclear -> datetime_iso = null.
- Keep values short.
"""
    user = (
        f"Today (Europe/Riga): {now_ts().strftime('%Y-%m-%d')}.\n"
        f"User said: {msg}\nChannel: {channel}\nUser phone: {raw_phone}\nLanguage hint: {lang}\n"
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

    dt_start = parse_dt_from_iso_or_fallback(c.get("datetime_iso"), c.get("time_text"), msg)
    if dt_start:
        c["datetime_iso"] = dt_start.isoformat()

    # 2) Ask missing
    if not c.get("service"):
        return {"status": "need_more", "reply_voice": VOICE_TEXT[lang]["ask_service"], "sms_out": render_sms(lang, "ask_service", link=RECOVERY_BOOKING_LINK), "lang": lang}

    if not dt_start:
        return {"status": "need_more", "reply_voice": VOICE_TEXT[lang]["ask_time"], "sms_out": render_sms(lang, "ask_time", link=RECOVERY_BOOKING_LINK), "lang": lang}

    if not c.get("name"):
        return {"status": "need_more", "reply_voice": VOICE_TEXT[lang]["ask_name"], "sms_out": render_sms(lang, "ask_name", link=RECOVERY_BOOKING_LINK), "lang": lang}

    # 3) Business hours
    if not in_business_hours(dt_start, APPT_MINUTES):
        return {"status": "need_more", "reply_voice": VOICE_TEXT[lang]["ask_time"], "sms_out": render_sms(lang, "ask_time", link=RECOVERY_BOOKING_LINK), "lang": lang}

    # 4) Busy check -> ALWAYS offer options if busy (even повторно)
    dt_end = dt_start + timedelta(minutes=APPT_MINUTES)
    if is_slot_busy(dt_start, dt_end):
        opts = find_next_two_slots(dt_start, APPT_MINUTES)
        if opts:
            opt1, opt2 = opts
            c["pending"] = {"opt1_iso": opt1.isoformat(), "opt2_iso": opt2.isoformat(), "service": c.get("service"), "name": c.get("name")}
            sms_out = render_sms(lang, "busy", opt1=opt1.strftime("%d.%m %H:%M"), opt2=opt2.strftime("%d.%m %H:%M"), link=RECOVERY_BOOKING_LINK)
            return {"status": "busy", "reply_voice": VOICE_TEXT[lang]["busy_voice"], "sms_out": sms_out, "lang": lang}
        return {"status": "recovery", "reply_voice": VOICE_TEXT[lang]["ask_time"], "sms_out": render_sms(lang, "recovery", link=RECOVERY_BOOKING_LINK), "lang": lang}

    # 5) Book
    service = c.get("service")
    name = c.get("name") or "Client"

    summary = f"{BUSINESS['name']} — {_short(service, 60)}"
    desc = f"Name: {name}\nPhone: {raw_phone}\nService: {service}\nOriginal: {msg}\nModel time_text: {c.get('time_text')}\nModel datetime_iso: {c.get('datetime_iso')}\nSource: {channel}\n"
    create_calendar_event(dt_start, APPT_MINUTES, summary, desc)

    when_str = dt_start.strftime("%d.%m %H:%M")
    sms_out = render_sms(lang, "confirmed", service=_short(service, 40), time=when_str, addr=_short(BUSINESS.get("address"), 35), link=RECOVERY_BOOKING_LINK)
    return {"status": "booked", "reply_voice": VOICE_TEXT[lang]["confirm_voice"], "sms_out": sms_out, "lang": lang}

# =========================
# HEALTH (Render)
# =========================
@app.get("/health")
async def health():
    allowed, reason = client_allowed()
    return {"ok": True, "ts": now_ts().isoformat(), "client_status": CLIENT_STATUS, "trial_end": TRIAL_END_DT.isoformat() if TRIAL_END_DT else None, "allowed": allowed, "reason": reason}

# =========================
# VOICE
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

    allowed, reason = client_allowed()
    if not allowed:
        say_or_play(vr, not_available_message("lv"), "lv")
        vr.hangup()
        return twiml(vr)

    g = Gather(
        input="speech dtmf",
        num_digits=1,
        action="/voice/intent",
        method="POST",
        timeout=7,
        speech_timeout="auto",
        language="lv-LV",  # сразу слушаем латышский
    )

    # Всё приветствие + подсказка языков — через say_or_play (LV => Google TTS)
    say_or_play(g, VOICE_TEXT["lv"]["greet_1"], "lv")
    say_or_play(g, VOICE_TEXT["lv"]["greet_2"], "lv")
    say_or_play(g, VOICE_TEXT["lv"]["lang_hint"], "lv")

    vr.append(g)

    say_or_play(vr, VOICE_TEXT["lv"]["no_hear"], "lv")
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

    allowed, reason = client_allowed()
    if not allowed:
        vr = VoiceResponse()
        say_or_play(vr, not_available_message("lv"), "lv")
        vr.hangup()
        return twiml(vr)

    # forced language via digits
    if digits in ("1", "2", "3"):
        cs["lang"] = "en" if digits == "1" else ("ru" if digits == "2" else "lv")
    if not cs.get("lang"):
        cs["lang"] = detect_language(speech)

    lang = get_lang(cs.get("lang"))
    result = handle_user_text(user_key=user_key, text=speech, channel="voice", lang_hint=lang, raw_phone=caller)
    cs["lang"] = get_lang(result.get("lang") or lang)

    vr = VoiceResponse()
    say_or_play(vr, result.get("reply_voice") or "OK.", cs["lang"])

    if result.get("status") == "need_more":
        g = Gather(
            input="speech",
            action="/voice/intent",
            method="POST",
            timeout=7,
            speech_timeout="auto",
            language=stt_locale_for_lang(cs["lang"]),
        )
        say_or_play(g, VOICE_TEXT[cs["lang"]]["ask_more"], cs["lang"])
        vr.append(g)
        say_or_play(vr, VOICE_TEXT[cs["lang"]]["no_hear"], cs["lang"])
    else:
        vr.hangup()

    sms_out = result.get("sms_out")
    if sms_out and caller and caller != "unknown":
        send_once_for_call(call_sid, f"msg_{result.get('status','x')}", caller, f"{BUSINESS['name']}: {sms_out}")

    return twiml(vr)

@app.post("/voice/status")
async def voice_status(request: Request):
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
                body = f"{BUSINESS['name']}: " + render_sms(lang, "recovery", link=RECOVERY_BOOKING_LINK)
                send_once_for_call(call_sid, "recovery", caller, body)

    # ВАЖНО: не возвращаем "ok" текстом → чтобы не было мусора
    return Response(status_code=204)

# =========================
# SMS INCOMING
# =========================
@app.post("/sms/incoming")
async def sms_incoming(request: Request):
    form = await request.form()
    from_number = str(form.get("From", ""))
    body_in = str(form.get("Body", "")).strip()

    allowed, reason = client_allowed()
    if not allowed:
        lang = detect_language(body_in) or "lv"
        send_message(from_number, f"{BUSINESS['name']}: {not_available_message(lang)}")
        return Response(status_code=204)

    user_key = norm_user_key(from_number)
    lang_hint = detect_language(body_in)

    result = handle_user_text(user_key=user_key, text=body_in, channel="sms", lang_hint=lang_hint, raw_phone=from_number)

    sms_out = result.get("sms_out")
    if sms_out:
        send_message(from_number, f"{BUSINESS['name']}: {sms_out}")
    else:
        lang = get_lang(CONV.get(user_key, {}).get("lang") or lang_hint)
        send_message(from_number, f"{BUSINESS['name']}: " + render_sms(lang, "recovery", link=RECOVERY_BOOKING_LINK))

    return Response(status_code=204)

# =========================
# WHATSAPP INCOMING
# =========================
@app.post("/whatsapp/incoming")
async def whatsapp_incoming(request: Request):
    form = await request.form()
    from_number = str(form.get("From", ""))  # e.g. 'whatsapp:+371...'
    body_in = str(form.get("Body", "")).strip()

    allowed, reason = client_allowed()
    if not allowed:
        lang = detect_language(body_in) or "lv"
        send_message(from_number, f"{BUSINESS['name']}: {not_available_message(lang)}")
        return Response(status_code=204)

    user_key = norm_user_key(from_number)

    # ключ: если пользователь пишет "1" или "2" — язык не пересчитываем
    lang_hint = None
    if body_in.strip() not in ("1", "2"):
        lang_hint = detect_language(body_in)

    result = handle_user_text(user_key=user_key, text=body_in, channel="whatsapp", lang_hint=lang_hint, raw_phone=from_number)

    sms_out = result.get("sms_out")
    if sms_out:
        send_message(from_number, f"{BUSINESS['name']}: {sms_out}")
    else:
        lang = get_lang(CONV.get(user_key, {}).get("lang") or (lang_hint or "lv"))
        send_message(from_number, f"{BUSINESS['name']}: " + render_sms(lang, "recovery", link=RECOVERY_BOOKING_LINK))

    # ВАЖНО: чтобы Twilio НЕ слал "ok" отдельным сообщением — возвращаем 204
    return Response(status_code=204)
