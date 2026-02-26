import os
import json
import re
from datetime import datetime, timedelta, timezone, date
from typing import Dict, Any, Optional, Tuple, List

import requests
from fastapi import FastAPI, Request
from fastapi.responses import Response
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
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

# Google Calendar
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "")

# Short SMS templates (trial-safe). Always uses RECOVERY_BOOKING_LINK (short).
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

# =========================
# STORAGE
# =========================

# Minimal per-call session (only language + SMS dedupe per call)
CALL_SESSIONS: Dict[str, Dict[str, Any]] = {}

# Conversation memory keyed by normalized phone number (works across voice/SMS/WhatsApp)
CONV: Dict[str, Dict[str, Any]] = {}

# Cached Google service
_GCAL = None


# =========================
# HELPERS
# =========================

def now_ts() -> datetime:
    return datetime.now(TZ)


def today_local() -> date:
    # IMPORTANT: base "today" on Europe/Riga, not server UTC
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
            "lang": "en",
            "sms_flags": {},  # per call anti-duplicate
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


def send_sms(to_number: str, body: str):
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
        print("SMS skipped: Twilio env vars missing")
        return
    try:
        client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(from_=TWILIO_FROM_NUMBER, to=to_number, body=body)
        print("SMS sent:", {"to": to_number, "sid": msg.sid, "status": msg.status})
    except Exception as e:
        print("SMS send error:", {"to": to_number, "err": repr(e)})


def send_sms_once_for_call(call_sid: str, key: str, to_number: str, body: str):
    s = get_call_session(call_sid)
    flags = s.setdefault("sms_flags", {})
    if flags.get(key):
        return
    send_sms(to_number, body)
    flags[key] = True


def parse_time_text_to_dt(text: str) -> Optional[datetime]:
    """
    Fallback parser (RU/EN/LV):
    - time HH:MM / HH MM / HH.MM
    - relative: tomorrow / day after tomorrow / in N days / через N дней / pēc N dien...
    - explicit: YYYY-MM-DD, DD.MM(.YYYY), DD/MM(/YYYY)
    - weekdays: monday..sunday / понедельник..воскресенье / pirmdiena..svētdiena (+ next/следующий/nākam)
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
                # weekdays
                weekdays_en = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                weekdays_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
                weekdays_lv = ["pirmdiena", "otrdiena", "trešdiena", "ceturtdiena", "piektdiena", "sestdiena", "svētdiena"]

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
    # 1) model ISO (preferred)
    iso = (datetime_iso or "").strip()
    if iso:
        try:
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ)
            else:
                dt = dt.astimezone(TZ)
            return dt
        except Exception as e:
            print("datetime_iso parse error:", repr(e))

    # 2) fallback (time_text + raw text)
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
    for _ in range(48):  # up to ~24 hours scanning by 30m steps
        if in_business_hours(candidate, duration_min):
            if not is_slot_busy(candidate, candidate + timedelta(minutes=duration_min)):
                found.append(candidate)
                if len(found) == 2:
                    return found[0], found[1]
        candidate = candidate + timedelta(minutes=step)
    return None


def create_calendar_event(dt_start: datetime, duration_min: int, summary: str, description: str) -> Optional[str]:
    """
    Creates event. Returns htmlLink (NOT used in SMS due to trial length).
    Never raises.
    """
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
# CORE LOGIC (UNIFIED FOR VOICE/SMS/WHATSAPP)
# =========================

def get_conv(user_key: str, default_lang: str) -> Dict[str, Any]:
    c = CONV.get(user_key)
    if not c:
        c = {
            "created_at": now_ts().isoformat(),
            "updated_at": now_ts().isoformat(),
            "lang": get_lang(default_lang),
            "history": [],
            # collected fields
            "service": None,
            "name": None,
            "datetime_iso": None,
            "time_text": None,
            # last offer if busy
            "pending": None,  # {"opt1_iso":..., "opt2_iso":..., "service":..., "name":...}
        }
        CONV[user_key] = c
    # keep lang sticky unless explicitly changed later
    if default_lang in ("en", "ru", "lv"):
        c["lang"] = get_lang(default_lang)
    c["updated_at"] = now_ts().isoformat()
    return c


def render_sms(lang: str, key: str, **kwargs) -> str:
    lang = get_lang(lang)
    tmpl = SMS_TEMPLATES[lang].get(key) or SMS_TEMPLATES["en"][key]
    return tmpl.format(**kwargs)


def handle_user_text(user_key: str, text: str, channel: str, lang_hint: str, raw_phone: str) -> Dict[str, Any]:
    """
    Returns dict:
      - status: 'need_more'|'booked'|'busy'|'recovery'
      - reply_voice: short text for Twilio Say (English-ish)
      - sms_out: optional SMS text to send
    """
    c = get_conv(user_key, lang_hint)
    lang = get_lang(c.get("lang"))

    msg = (text or "").strip()
    c["history"].append({"ts": now_ts().isoformat(), "channel": channel, "text": msg})

    # 0) If user replied with 1/2 and we have pending offer -> book it
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
                "reply_voice": "Sorry. Please say date and time again.",
                "sms_out": render_sms(lang, "ask_time", link=RECOVERY_BOOKING_LINK),
            }

        service = pending.get("service") or c.get("service")
        name = pending.get("name") or c.get("name") or "Client"

        # book
        summary = f"{BUSINESS['name']} — {_short(service, 60)}"
        desc = (
            f"Name: {name}\n"
            f"Phone: {raw_phone}\n"
            f"Service: {service}\n"
            f"Source: {channel} (option {msg})\n"
        )
        create_calendar_event(dt_start, APPT_MINUTES, summary, desc)

        c["pending"] = None
        c["service"] = service
        c["name"] = name
        c["datetime_iso"] = dt_start.isoformat()
        c["time_text"] = dt_start.strftime("%Y-%m-%d %H:%M")

        when_str = dt_start.strftime("%m-%d %H:%M")
        sms_out = render_sms(
            lang,
            "confirmed",
            service=_short(service, 40),
            time=when_str,
            addr=_short(BUSINESS.get("address"), 35),
            link=RECOVERY_BOOKING_LINK,
        )
        return {
            "status": "booked",
            "reply_voice": "Thank you. Booking confirmed by SMS.",
            "sms_out": sms_out,
        }

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
- If customer provides a date (explicit like 12.03 or 2026-03-12) OR relative date (tomorrow / day after tomorrow / in 2 days / next Friday),
  convert to datetime_iso in Europe/Riga timezone (+02:00) when possible.
- If only time is provided, keep time_text and set datetime_iso = null.
- Do not invent dates; if unclear set datetime_iso = null.
- Keep values short.
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

    # Merge into conversation memory (keep previous if new is null)
    if data.get("service"):
        c["service"] = data["service"]
    if data.get("name"):
        c["name"] = data["name"]
    if data.get("datetime_iso"):
        c["datetime_iso"] = data["datetime_iso"]
    if data.get("time_text"):
        c["time_text"] = data["time_text"]

    # 2) Determine dt_start (model ISO -> fallback parse from time_text + raw)
    dt_start = parse_dt_from_iso_or_fallback(c.get("datetime_iso"), c.get("time_text"), msg)
    if dt_start:
        c["datetime_iso"] = dt_start.isoformat()

    # 3) Ask missing fields (one at a time)
    if not c.get("service"):
        return {
            "status": "need_more",
            "reply_voice": "Please say the service.",
            "sms_out": render_sms(lang, "ask_service", link=RECOVERY_BOOKING_LINK),
        }

    if not dt_start:
        return {
            "status": "need_more",
            "reply_voice": "Please say date and time.",
            "sms_out": render_sms(lang, "ask_time", link=RECOVERY_BOOKING_LINK),
        }

    if not c.get("name"):
        return {
            "status": "need_more",
            "reply_voice": "Please say your name.",
            "sms_out": render_sms(lang, "ask_name", link=RECOVERY_BOOKING_LINK),
        }

    # 4) Business hours check
    if not in_business_hours(dt_start, APPT_MINUTES):
        # Ask for another time (and provide link)
        return {
            "status": "need_more",
            "reply_voice": "Sorry, outside working hours. Please choose another time.",
            "sms_out": render_sms(lang, "ask_time", link=RECOVERY_BOOKING_LINK),
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
            sms_out = render_sms(
                lang,
                "busy",
                opt1=opt1.strftime("%m-%d %H:%M"),
                opt2=opt2.strftime("%m-%d %H:%M"),
                link=RECOVERY_BOOKING_LINK,
            )
            return {
                "status": "busy",
                "reply_voice": "That time is busy. I sent options by SMS.",
                "sms_out": sms_out,
            }
        # if no options found -> recovery
        return {
            "status": "recovery",
            "reply_voice": "Sorry. Please book via link.",
            "sms_out": render_sms(lang, "recovery", link=RECOVERY_BOOKING_LINK),
        }

    # 6) Book
    service = c.get("service")
    name = c.get("name") or "Client"

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

    when_str = dt_start.strftime("%m-%d %H:%M")
    sms_out = render_sms(
        lang,
        "confirmed",
        service=_short(service, 40),
        time=when_str,
        addr=_short(BUSINESS.get("address"), 35),
        link=RECOVERY_BOOKING_LINK,
    )
    return {
        "status": "booked",
        "reply_voice": "Thank you. Booking confirmed by SMS.",
        "sms_out": sms_out,
    }


# =========================
# ROUTES: VOICE
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
    g = Gather(num_digits=1, action="/voice/lang", method="POST", timeout=6)
    g.say("Hello. For English press 1. For Russian press 2. For Latvian press 3.")
    vr.append(g)
    vr.say("We did not receive your choice. Goodbye.")
    return twiml(vr)


@app.post("/voice/lang")
async def voice_lang(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    digit = str(form.get("Digits", ""))
    caller = str(form.get("From", ""))

    cs = get_call_session(call_sid)
    cs["caller"] = caller

    if digit == "1":
        cs["lang"] = "en"
        stt_lang = "en-US"
    elif digit == "3":
        cs["lang"] = "lv"
        stt_lang = "lv-LV"
    else:
        cs["lang"] = "ru"
        stt_lang = "ru-RU"

    vr = VoiceResponse()
    # Keep voice prompts short (Twilio TTS for RU/LV may sound bad)
    g = Gather(
        input="speech",
        action="/voice/intent",
        method="POST",
        timeout=7,
        speech_timeout="auto",
        language=stt_lang,
    )
    g.say("Please say: service and preferred time.")
    vr.append(g)
    vr.say("Sorry, I couldn't hear you. Goodbye.")
    return twiml(vr)


@app.post("/voice/intent")
async def voice_intent(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    caller = str(form.get("From", ""))
    speech = str(form.get("SpeechResult", "")).strip()

    cs = get_call_session(call_sid)
    lang = get_lang(cs.get("lang"))
    user_key = norm_user_key(caller)

    result = handle_user_text(
        user_key=user_key,
        text=speech,
        channel="voice",
        lang_hint=lang,
        raw_phone=caller,
    )

    vr = VoiceResponse()
    vr.say(result.get("reply_voice") or "OK.")

    # Send SMS if we have something to send
    sms_out = result.get("sms_out")
    if sms_out and caller and caller != "unknown":
        # key by status to avoid duplicates in the same call
        send_sms_once_for_call(call_sid, f"sms_{result.get('status','x')}", caller, f"{BUSINESS['name']}: {sms_out}")

    return twiml(vr)


@app.post("/voice/status")
async def voice_status(request: Request):
    """
    Optional: Twilio status callback.
    If call ends without booking, send recovery SMS ONCE.
    Enable in Twilio number settings if needed.
    """
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    call_status = str(form.get("CallStatus", ""))
    caller = str(form.get("From", ""))

    cs = get_call_session(call_sid)
    lang = get_lang(cs.get("lang"))

    if call_status in ("completed", "busy", "failed", "no-answer", "canceled"):
        # If no conversation state exists or no booking happened, send recovery.
        user_key = norm_user_key(caller)
        c = CONV.get(user_key, {})
        # If last action wasn't booked recently, push recovery.
        if caller and caller != "unknown":
            # lightweight: if user has no datetime_iso recorded, treat as not booked
            if not c.get("datetime_iso"):
                body = f"{BUSINESS['name']}: " + render_sms(lang, "recovery", link=RECOVERY_BOOKING_LINK)
                send_sms_once_for_call(call_sid, "recovery", caller, body)

    return Response(content="ok", media_type="text/plain")


# =========================
# ROUTES: SMS (INCOMING)
# =========================

@app.post("/sms/incoming")
async def sms_incoming(request: Request):
    """
    Twilio Messaging webhook for SMS.
    Configure your Twilio number: Messaging -> A MESSAGE COMES IN -> POST -> https://<your-domain>/sms/incoming
    """
    form = await request.form()
    from_number = str(form.get("From", ""))
    body_in = str(form.get("Body", "")).strip()

    user_key = norm_user_key(from_number)

    # If we don't have lang yet, default to RU for Latvia MVP, but keep safe:
    # (You can set it later via profile settings; for now we'll infer by script.)
    lang_hint = "ru"
    if re.search(r"[a-zA-Z]", body_in) and not re.search(r"[а-яА-Я]", body_in):
        lang_hint = "en"

    result = handle_user_text(
        user_key=user_key,
        text=body_in,
        channel="sms",
        lang_hint=lang_hint,
        raw_phone=from_number,
    )

    sms_out = result.get("sms_out")
    if sms_out:
        send_sms(from_number, f"{BUSINESS['name']}: {sms_out}")
    else:
        # If handler didn't request SMS, send minimal guidance
        lang = get_lang(CONV.get(user_key, {}).get("lang") or lang_hint)
        send_sms(from_number, f"{BUSINESS['name']}: " + render_sms(lang, "recovery", link=RECOVERY_BOOKING_LINK))

    return Response(content="ok", media_type="text/plain")


# =========================
# ROUTES: WHATSAPP (INCOMING) - READY FOR NEXT STEP
# =========================

@app.post("/whatsapp/incoming")
async def whatsapp_incoming(request: Request):
    """
    Twilio WhatsApp webhook.
    In Twilio WhatsApp Sandbox / Sender:
      When a message comes in -> POST -> https://<your-domain>/whatsapp/incoming
    """
    form = await request.form()
    from_number = str(form.get("From", ""))  # e.g. 'whatsapp:+371...'
    body_in = str(form.get("Body", "")).strip()

    user_key = norm_user_key(from_number)

    # Rough language hint:
    lang_hint = "ru"
    if re.search(r"[a-zA-Z]", body_in) and not re.search(r"[а-яА-Я]", body_in):
        lang_hint = "en"

    result = handle_user_text(
        user_key=user_key,
        text=body_in,
        channel="whatsapp",
        lang_hint=lang_hint,
        raw_phone=from_number,
    )

    sms_out = result.get("sms_out")
    # For WhatsApp, we also send via Twilio messages (same API, From must be WhatsApp-enabled).
    # Easiest MVP: just reuse send_sms; Twilio will route if From is whatsapp:+...
    # If your TWILIO_FROM_NUMBER is not whatsapp-enabled, skip for now.
    if sms_out:
        send_sms(from_number, f"{BUSINESS['name']}: {sms_out}")
    else:
        lang = get_lang(CONV.get(user_key, {}).get("lang") or lang_hint)
        send_sms(from_number, f"{BUSINESS['name']}: " + render_sms(lang, "recovery", link=RECOVERY_BOOKING_LINK))

    return Response(content="ok", media_type="text/plain")
