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

# ====== BASIC CONFIG ======
TZ = timezone(timedelta(hours=2))  # Europe/Riga (+02:00)
SESSION_TTL_MIN = 30

BUSINESS = {
    "name": os.getenv("BIZ_NAME", "Repliq"),
    "address": os.getenv("BIZ_ADDRESS", "Rēzekne"),
    "hours": os.getenv("BIZ_HOURS", "09:00 - 18:00"),
    "services": os.getenv("BIZ_SERVICES", "мужские и женские стрижки"),
}

# IMPORTANT: set to your short link e.g. https://repliq.app/book
RECOVERY_BOOKING_LINK = os.getenv("RECOVERY_BOOKING_LINK", "https://repliq.app/book")

# Appointment defaults
APPT_MINUTES = int(os.getenv("APPT_MINUTES", "30"))
WORK_START_HHMM = os.getenv("WORK_START_HHMM", "09:00")
WORK_END_HHMM = os.getenv("WORK_END_HHMM", "18:00")

# Short SMS templates (Twilio Trial length safe). We ALWAYS include RECOVERY_BOOKING_LINK (short),
# never the long Google Calendar htmlLink.
SMS_TEMPLATES = {
    "en": {
        "confirmed": "Booked: {service} {time}. Addr: {addr}. {link}",
        "busy": "Busy. 1){opt1} 2){opt2}. Reply 1/2. {link}",
        "recovery": "Book via: {link}",
    },
    "ru": {
        "confirmed": "Запись: {service} {time}. Адрес: {addr}. {link}",
        "busy": "Занято. 1){opt1} 2){opt2}. Ответ 1/2. {link}",
        "recovery": "Запись: {link}",
    },
    "lv": {
        "confirmed": "Pieraksts: {service} {time}. Adrese: {addr}. {link}",
        "busy": "Aizņemts. 1){opt1} 2){opt2}. Atbildi 1/2. {link}",
        "recovery": "Pieraksts: {link}",
    },
}

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

# In-memory sessions for MVP (later swap to Redis/DB)
SESSIONS: Dict[str, Dict[str, Any]] = {}

# Cached Google service
_GCAL = None


def now_ts() -> datetime:
    return datetime.now(TZ)


def cleanup_sessions():
    cutoff = now_ts() - timedelta(minutes=SESSION_TTL_MIN)
    dead = []
    for sid, s in SESSIONS.items():
        created = datetime.fromisoformat(s.get("created_at"))
        if created < cutoff:
            dead.append(sid)
    for sid in dead:
        SESSIONS.pop(sid, None)


def get_session(call_sid: str) -> Dict[str, Any]:
    s = SESSIONS.get(call_sid)
    if not s:
        s = {
            "created_at": now_ts().isoformat(),
            "lang": None,
            "name": None,
            "phone": None,
            "service": None,
            "time_text": None,
            "status": "new",
            "sms_flags": {},  # anti-duplicate per call
        }
        SESSIONS[call_sid] = s
    return s


def get_lang(s: Dict[str, Any]) -> str:
    return s.get("lang") if s.get("lang") in ("en", "ru", "lv") else "en"


def twiml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")


def openai_chat_json(system: str, user: str) -> Dict[str, Any]:
    """
    Returns parsed JSON dict.
    """
    if not OPENAI_API_KEY:
        return {"service": None, "time_text": None, "name": None, "phone": None}

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


def parse_phone(text: str) -> Optional[str]:
    digits = re.sub(r"[^\d+]", "", text)
    return digits if len(digits) >= 8 else None


def send_sms(to_number: str, body: str):
    # Helpful logs for debugging Twilio trial issues
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
        print("SMS skipped: Twilio env vars missing")
        return
    try:
        client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(from_=TWILIO_FROM_NUMBER, to=to_number, body=body)
        print("SMS sent:", {"to": to_number, "sid": msg.sid, "status": msg.status})
    except Exception as e:
        print("SMS send error:", {"to": to_number, "err": repr(e)})


def send_sms_once(call_sid: str, key: str, to_number: str, body: str):
    """
    Prevent duplicate SMS per call session.
    key: 'recovery' | 'confirm'
    """
    s = get_session(call_sid)
    flags = s.setdefault("sms_flags", {})
    if flags.get(key):
        return
    send_sms(to_number, body)
    flags[key] = True


def normalize_time_request(text: str) -> str:
    return text.strip()[:120]


def _parse_hhmm(hhmm: str) -> Tuple[int, int]:
    hh, mm = hhmm.split(":")
    return int(hh), int(mm)


def parse_time_text_to_dt(time_text: str) -> Optional[datetime]:
    """
    MVP parser:
    - looks for HH:MM (or HH MM / HH.MM) in text
    - date keywords: today/tomorrow/послезавтра (EN/RU/LV)
    default date: today
    """
    if not time_text:
        return None

    m = re.search(r"\b([01]?\d|2[0-3])[:. ]([0-5]\d)\b", time_text)
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2))

    t = time_text.lower()
    d = date.today()

    if any(k in t for k in ["tomorrow", "завтра", "rīt", "rit"]):
        d = d + timedelta(days=1)
    elif any(k in t for k in ["day after tomorrow", "послезавтра", "parīt", "parit"]):
        d = d + timedelta(days=2)

    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=TZ)


def in_business_hours(dt_start: datetime, duration_min: int) -> bool:
    ws_h, ws_m = _parse_hhmm(WORK_START_HHMM)
    we_h, we_m = _parse_hhmm(WORK_END_HHMM)

    day_start = dt_start.replace(hour=ws_h, minute=ws_m, second=0, microsecond=0)
    day_end = dt_start.replace(hour=we_h, minute=we_m, second=0, microsecond=0)
    dt_end = dt_start + timedelta(minutes=duration_min)

    return (dt_start >= day_start) and (dt_end <= day_end)


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
    for _ in range(40):
        if in_business_hours(candidate, duration_min):
            if not is_slot_busy(candidate, candidate + timedelta(minutes=duration_min)):
                found.append(candidate)
                if len(found) == 2:
                    return found[0], found[1]
        candidate = candidate + timedelta(minutes=step)
    return None


def create_calendar_event(dt_start: datetime, duration_min: int, summary: str, description: str) -> Optional[str]:
    """
    Creates event and returns htmlLink (NOT used in SMS to avoid trial length issues).
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


def _short(s: Optional[str], n: int) -> str:
    return (s or "").strip()[:n]


# ====== ROUTES ======

@app.post("/voice/incoming")
async def voice_incoming(request: Request):
    cleanup_sessions()
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    caller = str(form.get("From", ""))

    s = get_session(call_sid)
    s["caller"] = caller

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

    s = get_session(call_sid)
    s["caller"] = caller

    # 1=EN, 2=RU, 3=LV
    if digit == "1":
        s["lang"] = "en"
        stt_lang = "en-US"
    elif digit == "3":
        s["lang"] = "lv"
        stt_lang = "lv-LV"
    else:
        s["lang"] = "ru"
        stt_lang = "ru-RU"

    vr = VoiceResponse()

    # Keep voice prompts short to avoid ugly Twilio RU/LV TTS.
    prompt = "Please say: service and preferred time."

    g = Gather(
        input="speech",
        action="/voice/intent",
        method="POST",
        timeout=7,
        speech_timeout="auto",
        language=stt_lang,
    )
    g.say(prompt)
    vr.append(g)

    vr.say("Sorry, I couldn't hear you. Goodbye.")
    return twiml(vr)


@app.post("/voice/intent")
async def voice_intent(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    caller = str(form.get("From", ""))
    speech = str(form.get("SpeechResult", "")).strip()

    s = get_session(call_sid)
    s["caller"] = caller

    system = f"""
You are Repliq, an AI receptionist for a small business.
Business:
- Name: {BUSINESS['name']}
- Hours: {BUSINESS['hours']}
- Services: {BUSINESS['services']}

Return STRICT JSON with keys:
service: string|null
time_text: string|null
name: string|null
phone: string|null

Rules:
- Ask ONE missing item at a time if needed.
- Do not invent prices.
"""

    user = f"Customer said: {speech}\nCaller phone: {caller}\nLanguage: {s.get('lang')}"
    try:
        data = openai_chat_json(system, user)
    except Exception:
        data = {"service": None, "time_text": None, "name": None, "phone": caller if caller else None}

    # Fill session from LLM
    s["service"] = data.get("service") or s.get("service")
    s["time_text"] = data.get("time_text") or s.get("time_text")
    s["name"] = data.get("name") or s.get("name")
    s["phone"] = data.get("phone") or s.get("phone") or (caller if caller else None)

    missing = []
    if not s.get("service"):
        missing.append("service")
    if not s.get("time_text"):
        missing.append("time")
    if not s.get("name"):
        missing.append("name")
    if not s.get("phone"):
        missing.append("phone")

    vr = VoiceResponse()

    if missing:
        field = missing[0]
        if field == "service":
            q = "Please say the service."
        elif field == "time":
            q = "Please say exact time, like 15 10."
        elif field == "name":
            q = "Please say your name."
        else:
            q = "Please say your phone number."

        g = Gather(
            input="speech",
            action="/voice/fill",
            method="POST",
            timeout=7,
            speech_timeout="auto",
            language="en-US",
        )
        g.say(q)
        vr.append(g)

        vr.say("Please continue.")
        return twiml(vr)

    # All fields collected -> attempt booking
    lang = get_lang(s)
    name = s.get("name") or ("Hello" if lang == "en" else ("Sveiki" if lang == "lv" else "Здравствуйте"))

    dt_start = parse_time_text_to_dt(s.get("time_text") or "")
    if dt_start is None or not in_business_hours(dt_start, APPT_MINUTES):
        # Can't parse / outside hours -> send recovery link
        vr.say("Thank you. We will confirm by SMS.")
        if s.get("phone"):
            service_short = _short(s.get("service"), 40)
            time_short = _short(s.get("time_text"), 25)
            addr_short = _short(BUSINESS.get("address"), 35)
            body = f"{BUSINESS['name']}: " + SMS_TEMPLATES[lang]["recovery"].format(link=RECOVERY_BOOKING_LINK)
            # Keep "confirm" key to avoid sending another SMS later for this call
            send_sms_once(call_sid, "confirm", s["phone"], body)
        s["status"] = "captured"
        return twiml(vr)

    dt_end = dt_start + timedelta(minutes=APPT_MINUTES)

    if is_slot_busy(dt_start, dt_end):
        opts = find_next_two_slots(dt_start, APPT_MINUTES)
        vr.say("Thank you. We will confirm by SMS.")
        if s.get("phone"):
            if opts:
                opt1, opt2 = opts
                fmt1 = opt1.strftime("%m-%d %H:%M")
                fmt2 = opt2.strftime("%m-%d %H:%M")
                body = f"{BUSINESS['name']}: " + SMS_TEMPLATES[lang]["busy"].format(
                    opt1=fmt1,
                    opt2=fmt2,
                    link=RECOVERY_BOOKING_LINK,
                )
            else:
                body = f"{BUSINESS['name']}: " + SMS_TEMPLATES[lang]["recovery"].format(link=RECOVERY_BOOKING_LINK)
            send_sms_once(call_sid, "confirm", s["phone"], body)
        s["status"] = "captured"
        return twiml(vr)

    # Create event (ignore returned htmlLink in SMS to avoid trial length)
    summary = f"{BUSINESS['name']} — {_short(s.get('service'), 60)}"
    desc = f"Name: {s.get('name')}\nPhone: {s.get('phone')}\nService: {s.get('service')}\nRequested: {s.get('time_text')}\nSource: call"
    create_calendar_event(dt_start, APPT_MINUTES, summary, desc)

    vr.say("Thank you. Booking confirmed by SMS.")

    if s.get("phone"):
        when_str = dt_start.strftime("%m-%d %H:%M")
        service_short = _short(s.get("service"), 40)
        addr_short = _short(BUSINESS.get("address"), 35)

        body = f"{BUSINESS['name']}: " + SMS_TEMPLATES[lang]["confirmed"].format(
            service=service_short,
            time=when_str,
            addr=addr_short,
            link=RECOVERY_BOOKING_LINK,
        )
        send_sms_once(call_sid, "confirm", s["phone"], body)

    s["status"] = "booked"
    return twiml(vr)


@app.post("/voice/fill")
async def voice_fill(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", "")).strip()

    s = get_session(call_sid)

    if not s.get("service"):
        s["service"] = speech
    elif not s.get("time_text"):
        s["time_text"] = normalize_time_request(speech)
    elif not s.get("name"):
        s["name"] = speech
    elif not s.get("phone"):
        s["phone"] = parse_phone(speech) or speech

    vr = VoiceResponse()
    vr.redirect("/voice/intent")
    return twiml(vr)


@app.post("/voice/status")
async def voice_status(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    call_status = str(form.get("CallStatus", ""))
    caller = str(form.get("From", ""))

    s = get_session(call_sid)

    if call_status in ("completed", "busy", "failed", "no-answer", "canceled"):
        if s.get("status") not in ("captured", "booked") and caller:
            lang = get_lang(s)
            body = f"{BUSINESS['name']}: " + SMS_TEMPLATES[lang]["recovery"].format(link=RECOVERY_BOOKING_LINK)
            send_sms_once(call_sid, "recovery", caller, body)
            s["status"] = "recovery_sms_sent"

    return Response(content="ok", media_type="text/plain")
