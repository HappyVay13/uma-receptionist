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

RECOVERY_BOOKING_LINK = os.getenv("RECOVERY_BOOKING_LINK", "https://google.com")

# Appointment defaults
APPT_MINUTES = int(os.getenv("APPT_MINUTES", "30"))
WORK_START_HHMM = os.getenv("WORK_START_HHMM", "09:00")
WORK_END_HHMM = os.getenv("WORK_END_HHMM", "18:00")

SMS_TEMPLATES = {
    "en": {
        "request": "{name}, request received: {service} / {time}. We will confirm shortly.",
        "confirmed": "{name}, booking CONFIRMED: {service} / {time}. Address: {addr}. Link: {link}",
        "busy": "That time is busy. Available: {opt1} or {opt2}. Reply 1 or 2. Link: {link}",
        "recovery": "Missed us? Reply with time and service or use: {link}",
    },
    "ru": {
        "request": "{name}, заявка принята: {service} / {time}. Сейчас подтвердим.",
        "confirmed": "{name}, ЗАПИСЬ ПОДТВЕРЖДЕНА: {service} / {time}. Адрес: {addr}. Ссылка: {link}",
        "busy": "Это время занято. Есть варианты: {opt1} или {opt2}. Ответьте 1 или 2. Ссылка: {link}",
        "recovery": "Не дозвонились? Напишите услугу и время или используйте: {link}",
    },
    "lv": {
        "request": "{name}, pieprasījums saņemts: {service} / {time}. Drīz apstiprināsim.",
        "confirmed": "{name}, REZERVĀCIJA APSTIPRINĀTA: {service} / {time}. Adrese: {addr}. Saite: {link}",
        "busy": "Šis laiks ir aizņemts. Varianti: {opt1} vai {opt2}. Atbildi 1 vai 2. Saite: {link}",
        "recovery": "Neizdevās sazvanīt? Atsūti pakalpojumu un laiku vai izmanto: {link}",
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
            "sms_flags": {},
            "last_offer": None,  # for future SMS dialog options
        }
        SESSIONS[call_sid] = s
    return s


def get_lang(s: Dict[str, Any]) -> str:
    return s.get("lang") if s.get("lang") in ("en", "ru", "lv") else "en"


def twiml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")


def openai_chat_json(system: str, user: str) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        return {"intent": "book", "service": None, "time_text": None, "name": None, "phone": None}

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
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
        return
    client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages.create(from_=TWILIO_FROM_NUMBER, to=to_number, body=body)


def send_sms_once(call_sid: str, key: str, to_number: str, body: str):
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
    - expects a HH:MM somewhere in the text
    - date: today/tomorrow/послезавтра keywords (EN/RU/LV)
    If no date keyword -> assumes today (for MVP).
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

    info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    _GCAL = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return _GCAL


def is_slot_busy(dt_start: datetime, dt_end: datetime) -> bool:
    svc = get_gcal()
    if svc is None:
        return False  # if calendar not configured, don't block
    body = {
        "timeMin": dt_start.isoformat(),
        "timeMax": dt_end.isoformat(),
        "items": [{"id": GOOGLE_CALENDAR_ID}],
    }
    fb = svc.freebusy().query(body=body).execute()
    busy = fb["calendars"][GOOGLE_CALENDAR_ID].get("busy", [])
    return len(busy) > 0


def find_next_two_slots(dt_start: datetime, duration_min: int) -> Optional[Tuple[datetime, datetime]]:
    """
    Looks for next two free slots in 30-min steps within business hours, same day.
    """
    step = 30
    candidate = dt_start
    found: List[datetime] = []
    for _ in range(40):  # up to ~20 hours scanning max (safe)
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
    created = svc.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
    return created.get("htmlLink")


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
            q = "Please say exact time, like 15 30."
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

    # We have all fields -> attempt booking in Google Calendar
    lang = get_lang(s)
    name = s.get("name") or ("Hello" if lang == "en" else ("Sveiki" if lang == "lv" else "Здравствуйте"))

    dt_start = parse_time_text_to_dt(s.get("time_text") or "")
    if dt_start is None or not in_business_hours(dt_start, APPT_MINUTES):
        # Can't parse / outside hours -> treat as request, send link
        vr.say("Thank you. We will confirm by SMS.")
        if s.get("phone"):
            body = f"{BUSINESS['name']}: " + SMS_TEMPLATES[lang]["request"].format(
                name=name, service=s.get("service"), time=s.get("time_text"), hours=BUSINESS["hours"], link=RECOVERY_BOOKING_LINK
            )
            send_sms_once(call_sid, "confirm", s["phone"], body)
        s["status"] = "captured"
        return twiml(vr)

    dt_end = dt_start + timedelta(minutes=APPT_MINUTES)

    if is_slot_busy(dt_start, dt_end):
        # Offer next 2 slots
        opts = find_next_two_slots(dt_start, APPT_MINUTES)
        vr.say("Thank you. We will confirm by SMS.")
        if s.get("phone"):
            if opts:
                opt1, opt2 = opts
                fmt1 = opt1.strftime("%Y-%m-%d %H:%M")
                fmt2 = opt2.strftime("%Y-%m-%d %H:%M")
                body = f"{BUSINESS['name']}: " + SMS_TEMPLATES[lang]["busy"].format(
                    opt1=fmt1, opt2=fmt2, link=RECOVERY_BOOKING_LINK
                )
            else:
                body = f"{BUSINESS['name']}: " + SMS_TEMPLATES[lang]["recovery"].format(link=RECOVERY_BOOKING_LINK)
            send_sms_once(call_sid, "confirm", s["phone"], body)
        s["status"] = "captured"
        return twiml(vr)

    # Create event
    summary = f"{BUSINESS['name']} — {s.get('service')}"
    desc = f"Name: {s.get('name')}\nPhone: {s.get('phone')}\nService: {s.get('service')}\nRequested: {s.get('time_text')}\nSource: call"
    link = create_calendar_event(dt_start, APPT_MINUTES, summary, desc) or RECOVERY_BOOKING_LINK

    vr.say("Thank you. Booking confirmed by SMS.")

    if s.get("phone"):
        when_str = dt_start.strftime("%Y-%m-%d %H:%M")
        body = f"{BUSINESS['name']}: " + SMS_TEMPLATES[lang]["confirmed"].format(
            name=name,
            service=s.get("service"),
            time=when_str,
            hours=BUSINESS["hours"],
            addr=BUSINESS["address"],
            link=link,
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
