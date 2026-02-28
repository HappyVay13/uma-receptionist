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
from twilio.rest import Client as TwilioClient

from google.oauth2 import service_account
from googleapiclient.discovery import build

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
    "services": os.getenv("BIZ_SERVICES", "vīriešu un sieviešu frizūra"),
}

# Short link to avoid Twilio trial SMS length issues
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

# WhatsApp sender (must be like "whatsapp:+14155238886" for sandbox or approved WA sender)
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")

# Google Calendar
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "")

# ElevenLabs (optional) – used for RU/EN if configured
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
# Your public base URL, e.g. https://repliq.onrender.com (NO trailing slash)
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "").strip().rstrip("/")

# -------------------------
# Minimal Trial / Active / Inactive
# -------------------------
CLIENT_STATUS = os.getenv("CLIENT_STATUS", "trial").strip().lower()  # trial | active | inactive
TRIAL_END_ISO = os.getenv("TRIAL_END_ISO", "").strip()  # "2026-03-15T00:00:00+02:00" or "...Z"


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
# Templates (short, human)
# -------------------------
SMS_TEMPLATES = {
    "lv": {
        "confirmed": "Pieraksts apstiprināts:\n{service}\n{time}\nAdrese: {addr}\n{link}",
        "busy": "Šis laiks ir aizņemts.\n1) {opt1}\n2) {opt2}\nAtbildi 1 vai 2.\n{link}",
        "ask_service": "Kāds pakalpojums? Piem.: vīriešu frizūra.\n{link}",
        "ask_time": "Kad vēlaties? Piem.: rīt 15:10.\n{link}",
        "ask_name": "Kāds ir jūsu vārds?\n{link}",
        "recovery": "Pieraksts: {link}",
    },
    "ru": {
        "confirmed": "Запись подтверждена:\n{service}\n{time}\nАдрес: {addr}\n{link}",
        "busy": "Это время занято.\n1) {opt1}\n2) {opt2}\nОтветьте 1 или 2.\n{link}",
        "ask_service": "Какая услуга? Пример: мужская стрижка.\n{link}",
        "ask_time": "Когда? Пример: завтра 15:10.\n{link}",
        "ask_name": "Как вас зовут?\n{link}",
        "recovery": "Запись: {link}",
    },
    "en": {
        "confirmed": "Booked:\n{service}\n{time}\nAddr: {addr}\n{link}",
        "busy": "That time is busy.\n1) {opt1}\n2) {opt2}\nReply 1 or 2.\n{link}",
        "ask_service": "Which service? Example: men's haircut.\n{link}",
        "ask_time": "When? Example: tomorrow 15:10.\n{link}",
        "ask_name": "Your name?\n{link}",
        "recovery": "Book: {link}",
    },
}


def voice_text(lang: str, key: str) -> str:
    lang = get_lang(lang)
    lv = {
        "greet_1": f"Labdien! Jūs esat sazvanījuši {BUSINESS['name']}.",
        "greet_2": "Kā varu palīdzēt?",
        "ask_service": "Kāds pakalpojums jūs interesē?",
        "ask_time": "Kad vēlaties pierakstu?",
        "ask_name": "Kāds ir jūsu vārds?",
        "busy": "Šis laiks jau ir aizņemts. Nosūtīju variantus ziņā.",
        "booked": "Lieliski. Nosūtīju apstiprinājumu.",
        "continue": "Lūdzu, turpiniet.",
        "no_hear": "Atvainojiet, nedzirdēju. Uz redzēšanos.",
    }
    ru = {
        "greet_1": f"Здравствуйте! Вы позвонили в {BUSINESS['name']}.",
        "greet_2": "Чем могу помочь?",
        "ask_service": "Какая услуга вам нужна?",
        "ask_time": "На какую дату и время хотите записаться?",
        "ask_name": "Как вас зовут?",
        "busy": "Это время занято. Я отправил варианты сообщением.",
        "booked": "Отлично. Я отправил подтверждение.",
        "continue": "Пожалуйста, продолжайте.",
        "no_hear": "Извините, я вас не услышал. До свидания.",
    }
    en = {
        "greet_1": f"Hello! You reached {BUSINESS['name']}.",
        "greet_2": "How can I help?",
        "ask_service": "Which service do you need?",
        "ask_time": "What date and time works for you?",
        "ask_name": "What is your name?",
        "busy": "That time is busy. I sent options by message.",
        "booked": "Great. I sent a confirmation.",
        "continue": "Please continue.",
        "no_hear": "Sorry, I couldn't hear you. Goodbye.",
    }
    return (lv if lang == "lv" else ru if lang == "ru" else en).get(key, "OK.")


# =========================
# STORAGE
# =========================
CALL_SESSIONS: Dict[str, Dict[str, Any]] = {}  # per-call (voice)
CONV: Dict[str, Dict[str, Any]] = {}  # per-user conversation (voice/sms/whatsapp)
_GCAL = None


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
        s = {"created_at": now_ts().isoformat(), "lang": None, "sms_flags": {}, "caller": None}
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
    return value if value in ("en", "ru", "lv") else "lv"  # default LV for your market


def detect_language(text: str) -> str:
    """
    Lightweight detector:
      - Latvian special letters -> lv
      - Cyrillic -> ru
      - otherwise -> en
    """
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


def _twilio_client() -> Optional[TwilioClient]:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        return None
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_message(to_number: str, body: str):
    """
    Unified sender:
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


def send_sms_once_for_call(call_sid: str, key: str, to_number: str, body: str):
    s = get_call_session(call_sid)
    flags = s.setdefault("sms_flags", {})
    if flags.get(key):
        return
    send_message(to_number, body)
    flags[key] = True


def parse_time_text_to_dt(text: str) -> Optional[datetime]:
    """
    Fallback parser (RU/EN/LV):
    - time HH:MM / HH MM / HH.MM
    - relative: tomorrow / day after tomorrow / in N days / через N дней / pēc N dien...
    - explicit: YYYY-MM-DD, DD.MM(.YYYY), DD/MM(/YYYY)
    - weekdays (basic)
    """
    if not text:
        return None

    t = text.lower()

    # time
    m = re.search(r"\b([01]?\d|2[0-3])[:. ]([0-5]\d)\b", t)
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2))

    base = today_local()

    # explicit ISO date YYYY-MM-DD
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
            # relative days
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
            else:
                weekdays_en = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                weekdays_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
                weekdays_lv = [
                    "pirmdiena",
                    "otrdiena",
                    "trešdiena",
                    "ceturtdiena",
                    "piektdiena",
                    "sestdiena",
                    "svētdiena",
                ]

                def find_weekday() -> Optional[int]:
                    for i, w in enumerate(weekdays_en):
                        if w in t:
                            return i
                    for i, w in enumerate(weekdays_ru):
                        if w in t:
                            return i
                    for i, w in enumerate(weekdays_lv):
                        if w in t:
                            return i
                    return None

                wd = find_weekday()
                if wd is not None:
                    today_wd = base.weekday()
                    delta = (wd - today_wd) % 7
                    if delta == 0:
                        delta = 7
                    if any(k in t for k in [" next ", "следующ", "nākam"]):
                        delta += 7
                    base = base + timedelta(days=delta)

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


def render_msg(lang: str, key: str, **kwargs) -> str:
    lang = get_lang(lang)
    tmpl = SMS_TEMPLATES[lang].get(key) or SMS_TEMPLATES["en"][key]
    return tmpl.format(**kwargs)


# =========================
# ELEVENLABS TTS (optional for RU/EN)
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


@app.get("/tts")
def tts(text: str):
    """
    Twilio <Play> endpoint. Returns audio/mpeg.
    Used for RU/EN only when ElevenLabs is configured.
    """
    if not (ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID):
        raise HTTPException(status_code=503, detail="ElevenLabs not configured")
    audio = generate_eleven_audio(text)
    if not audio:
        raise HTTPException(status_code=500, detail="TTS generation failed")
    return StreamingResponse(iter([audio]), media_type="audio/mpeg")


def say_or_play(vr: VoiceResponse, text: str, lang: str):
    """
    LV -> Twilio TTS in lv-LV (simple & reliable).
    RU/EN -> ElevenLabs if configured, else Twilio say().
    """
    t = (text or "").strip() or "OK."
    lang = get_lang(lang)

    if lang == "lv":
        vr.say(t, language="lv-LV")
        return

    if eleven_enabled():
        q = urllib.parse.quote_plus(t)
        tts_url = f"{SERVER_BASE_URL}/tts?text={q}"
        vr.play(tts_url)
        return

    if lang == "ru":
        vr.say(t, language="ru-RU")
        return

    vr.say(t, language="en-US")


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
    for _ in range(48):  # up to ~24h scanning by 30m steps
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
# CONVERSATION (fix WA lang + human voice)
# =========================
def get_conv(user_key: str, default_lang: str) -> Dict[str, Any]:
    c = CONV.get(user_key)
    if not c:
        c = {
            "created_at": now_ts().isoformat(),
            "updated_at": now_ts().isoformat(),
            "lang": get_lang(default_lang),  # fixed once
            "history": [],
            "service": None,
            "name": None,
            "datetime_iso": None,
            "time_text": None,
            "pending": None,  # {"opt1_iso":..., "opt2_iso":..., "service":..., "name":...}
        }
        CONV[user_key] = c

    # ✅ Do NOT overwrite language on every message. Only set if missing.
    if not c.get("lang"):
        c["lang"] = get_lang(default_lang)

    c["updated_at"] = now_ts().isoformat()
    return c


def handle_user_text(user_key: str, text: str, channel: str, lang_hint: str, raw_phone: str) -> Dict[str, Any]:
    """
    Returns dict:
      - status: 'need_more'|'booked'|'busy'|'recovery'
      - reply_voice: short text for TTS
      - out_text: optional SMS/WA text (WITHOUT business prefix)
      - lang: chosen language
    """
    msg = (text or "").strip()
    # ✅ If user is selecting offered options 1/2, keep previous language (do NOT re-detect).
    if msg in ("1", "2"):
        c0 = get_conv(user_key, "lv")
        lang_hint = get_lang(c0.get("lang"))
    else:
        if not lang_hint or lang_hint not in ("en", "ru", "lv"):
            lang_hint = detect_language(msg)

    c = get_conv(user_key, lang_hint)
    lang = get_lang(c.get("lang"))

    c["history"].append({"ts": now_ts().isoformat(), "channel": channel, "text": msg})

    # 0) If user replied with 1/2 and we have pending offer -> book it
    if msg in ("1", "2") and c.get("pending"):
        lang = get_lang(c.get("lang"))  # ✅ make sure we use stored language
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
                "reply_voice": voice_text(lang, "ask_time"),
                "out_text": render_msg(lang, "ask_time", link=RECOVERY_BOOKING_LINK),
                "lang": lang,
            }

        service = pending.get("service") or c.get("service")
        name = pending.get("name") or c.get("name") or "Klients"

        summary = f"{BUSINESS['name']} — {_short(service, 60)}"
        desc = f"Name: {name}\nPhone: {raw_phone}\nService: {service}\nSource: {channel} (option {msg})\n"
        create_calendar_event(dt_start, APPT_MINUTES, summary, desc)

        c["pending"] = None
        c["service"] = service
        c["name"] = name
        c["datetime_iso"] = dt_start.isoformat()
        c["time_text"] = dt_start.strftime("%Y-%m-%d %H:%M")

        when_str = dt_start.strftime("%d.%m %H:%M")
        out_text = render_msg(
            lang,
            "confirmed",
            service=_short(service, 60),
            time=when_str,
            addr=_short(BUSINESS.get("address"), 60),
            link=RECOVERY_BOOKING_LINK,
        )
        return {"status": "booked", "reply_voice": voice_text(lang, "booked"), "out_text": out_text, "lang": lang}

    # 1) Extract fields using OpenAI (preferred)
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
- Understand natural speech. The user may say only "Can I book?" or "Tomorrow afternoon".
- If user provides relative date (rīt / parīt / tomorrow / day after tomorrow / через 2 дня), convert to datetime_iso in Europe/Riga timezone when possible.
- If unclear: set datetime_iso = null and keep time_text short.
- Do NOT invent missing details.
- Keep values short.
"""
    user = (
        f"Today (Europe/Riga) is {now_ts().strftime('%Y-%m-%d')}.\n"
        f"User said: {msg}\n"
        f"Channel: {channel}\n"
        f"User phone: {raw_phone}\n"
        f"Preferred language: {lang}\n"
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

    # 2) Determine dt_start (model ISO -> fallback)
    dt_start = parse_dt_from_iso_or_fallback(c.get("datetime_iso"), c.get("time_text"), msg)
    if dt_start:
        c["datetime_iso"] = dt_start.isoformat()

    # 3) Ask missing fields (human voice)
    if not c.get("service"):
        return {
            "status": "need_more",
            "reply_voice": voice_text(lang, "ask_service"),
            "out_text": render_msg(lang, "ask_service", link=RECOVERY_BOOKING_LINK),
            "lang": lang,
        }

    if not dt_start:
        return {
            "status": "need_more",
            "reply_voice": voice_text(lang, "ask_time"),
            "out_text": render_msg(lang, "ask_time", link=RECOVERY_BOOKING_LINK),
            "lang": lang,
        }

    if not c.get("name"):
        return {
            "status": "need_more",
            "reply_voice": voice_text(lang, "ask_name"),
            "out_text": render_msg(lang, "ask_name", link=RECOVERY_BOOKING_LINK),
            "lang": lang,
        }

    # 4) Business hours
    if not in_business_hours(dt_start, APPT_MINUTES):
        return {
            "status": "need_more",
            "reply_voice": voice_text(lang, "ask_time"),
            "out_text": render_msg(lang, "ask_time", link=RECOVERY_BOOKING_LINK),
            "lang": lang,
        }

    # 5) Busy check -> offer 2 options
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
            out_text = render_msg(
                lang,
                "busy",
                opt1=opt1.strftime("%d.%m %H:%M"),
                opt2=opt2.strftime("%d.%m %H:%M"),
                link=RECOVERY_BOOKING_LINK,
            )
            return {"status": "busy", "reply_voice": voice_text(lang, "busy"), "out_text": out_text, "lang": lang}

        return {
            "status": "recovery",
            "reply_voice": render_msg(lang, "recovery", link=RECOVERY_BOOKING_LINK),
            "out_text": render_msg(lang, "recovery", link=RECOVERY_BOOKING_LINK),
            "lang": lang,
        }

    # 6) Book
    service = c.get("service")
    name = c.get("name") or "Klients"

    summary = f"{BUSINESS['name']} — {_short(service, 60)}"
    desc = (
        f"Name: {name}\n"
        f"Phone: {raw_phone}\n"
        f"Service: {service}\n"
        f"Original: {msg}\n"
        f"Model time_text: {c.get('time_text')}\n"
        f"Model datetime_iso: {c.get('datetime_iso')}\n"
        f"Source: {channel}\n"
    )
    create_calendar_event(dt_start, APPT_MINUTES, summary, desc)

    when_str = dt_start.strftime("%d.%m %H:%M")
    out_text = render_msg(
        lang,
        "confirmed",
        service=_short(service, 60),
        time=when_str,
        addr=_short(BUSINESS.get("address"), 60),
        link=RECOVERY_BOOKING_LINK,
    )
    return {"status": "booked", "reply_voice": voice_text(lang, "booked"), "out_text": out_text, "lang": lang}


# =========================
# HEALTH (Render)
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
# ROUTES: VOICE
# =========================
@app.post("/voice/incoming")
async def voice_incoming(request: Request):
    """
    Human LV greeting + optional language keypad + natural speech.
    """
    cleanup_call_sessions()
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    caller = str(form.get("From", ""))

    cs = get_call_session(call_sid)
    cs["caller"] = caller

    vr = VoiceResponse()

    allowed, _ = client_allowed()
    if not allowed:
        say_or_play(vr, not_available_message("lv"), "lv")
        vr.hangup()
        return twiml(vr)

    # ✅ Human greeting with company name
    say_or_play(vr, voice_text("lv", "greet_1"), "lv")
    say_or_play(vr, voice_text("lv", "greet_2"), "lv")

    g = Gather(
        input="speech dtmf",
        num_digits=1,
        action="/voice/intent",
        method="POST",
        timeout=7,
        speech_timeout="auto",
        language="lv-LV",
    )
    g.say("Ja vēlaties, nospiediet: 1 angliski, 2 krieviski, 3 latviski.", language="lv-LV")
    vr.append(g)

    say_or_play(vr, voice_text("lv", "no_hear"), "lv")
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
        say_or_play(vr, not_available_message("lv"), "lv")
        vr.hangup()
        return twiml(vr)

    # Force language by DTMF if user pressed digit
    if digits in ("1", "2", "3"):
        cs["lang"] = "en" if digits == "1" else ("ru" if digits == "2" else "lv")

    # If no forced language yet – detect from speech, but default to LV
    if not cs.get("lang"):
        cs["lang"] = detect_language(speech) if speech else "lv"

    lang = get_lang(cs.get("lang"))

    result = handle_user_text(
        user_key=user_key,
        text=speech,
        channel="voice",
        lang_hint=lang,
        raw_phone=caller,
    )

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
        g.say(voice_text(cs["lang"], "continue"), language=stt_locale_for_lang(cs["lang"]))
        vr.append(g)
        say_or_play(vr, voice_text(cs["lang"], "no_hear"), cs["lang"])
    else:
        vr.hangup()

    out_text = result.get("out_text")
    if out_text and caller and caller != "unknown":
        send_sms_once_for_call(
            call_sid,
            f"voice_{result.get('status','x')}",
            caller,
            f"{BUSINESS['name']}: {out_text}",
        )

    return twiml(vr)


@app.post("/voice/status")
async def voice_status(request: Request):
    """
    Optional: Twilio status callback.
    If call ends without booking, send recovery message ONCE.
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
                send_sms_once_for_call(call_sid, "recovery", caller, body)

    return Response(content="ok", media_type="text/plain")


# =========================
# ROUTES: SMS (INCOMING)
# =========================
@app.post("/sms/incoming")
async def sms_incoming(request: Request):
    form = await request.form()
    from_number = str(form.get("From", ""))
    body_in = str(form.get("Body", "")).strip()

    allowed, _ = client_allowed()
    if not allowed:
        lang = detect_language(body_in) or "lv"
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

    out_text = result.get("out_text") or render_msg(get_lang(lang_hint), "recovery", link=RECOVERY_BOOKING_LINK)
    send_message(from_number, f"{BUSINESS['name']}: {out_text}")
    return Response(content="ok", media_type="text/plain")


# =========================
# ROUTES: WHATSAPP (INCOMING)
# =========================
@app.post("/whatsapp/incoming")
async def whatsapp_incoming(request: Request):
    form = await request.form()
    from_number = str(form.get("From", ""))  # e.g. 'whatsapp:+371...'
    body_in = str(form.get("Body", "")).strip()

    allowed, _ = client_allowed()
    if not allowed:
        lang = detect_language(body_in) or "lv"
        send_message(from_number, f"{BUSINESS['name']}: {not_available_message(lang)}")
        return Response(content="ok", media_type="text/plain")

    user_key = norm_user_key(from_number)

    # ✅ WhatsApp language: if user replies 1/2 -> keep stored language (handled in handle_user_text)
    lang_hint = detect_language(body_in)

    result = handle_user_text(
        user_key=user_key,
        text=body_in,
        channel="whatsapp",
        lang_hint=lang_hint,
        raw_phone=from_number,
    )

    out_text = result.get("out_text") or render_msg(get_lang(lang_hint), "recovery", link=RECOVERY_BOOKING_LINK)
    send_message(from_number, f"{BUSINESS['name']}: {out_text}")

    # Return plain 200 OK (Twilio will not send extra messages from this response)
    return Response(content="ok", media_type="text/plain")
