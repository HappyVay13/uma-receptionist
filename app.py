import os
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

import requests
from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client as TwilioClient

app = FastAPI()

# ====== BASIC CONFIG (MVP v0) ======
TZ = timezone(timedelta(hours=2))  # Europe/Riga (+02:00) for MVP
SESSION_TTL_MIN = 30

BUSINESS = {
    "name": os.getenv("BIZ_NAME", "Repliq"),
    "address": os.getenv("BIZ_ADDRESS", "Rēzekne"),
    "hours": os.getenv("BIZ_HOURS", "09:00 - 18:00"),
    "services": os.getenv("BIZ_SERVICES", "мужские и женские стрижки"),
}

RECOVERY_BOOKING_LINK = os.getenv("RECOVERY_BOOKING_LINK", "https://google.com")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

# In-memory sessions for MVP (later swap to Redis/DB)
SESSIONS: Dict[str, Dict[str, Any]] = {}


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
            "sms_flags": {},  # anti-duplicate SMS flags
        }
        SESSIONS[call_sid] = s
    return s


def twiml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")


def openai_chat_json(system: str, user: str) -> Dict[str, Any]:
    """
    Returns parsed JSON dict. If something fails -> safe fallback dict.
    NOTE: Requires OpenAI billing enabled on platform.openai.com (ChatGPT Plus does NOT apply).
    """
    if not OPENAI_API_KEY:
        return {
            "intent": "book",
            "service": None,
            "time_text": None,
            "name": None,
            "phone": None,
            "need_human": True,
            "reply_ru": "Извините, сервис временно недоступен. Мы отправим SMS со ссылкой для записи.",
        }

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    payload = {
        "model": OPENAI_MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        # Ask for strict JSON
        "response_format": {"type": "json_object"},
    }

    r = requests.post(url, headers=headers, json=payload, timeout=25)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def parse_phone(text: str) -> Optional[str]:
    digits = re.sub(r"[^\d+]", "", text)
    if len(digits) >= 8:
        return digits
    return None


def send_sms(to_number: str, body: str):
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
        return
    client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages.create(from_=TWILIO_FROM_NUMBER, to=to_number, body=body)


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


# ====== ROUTES ======

@app.post("/voice/incoming")
async def voice_incoming(request: Request):
    """
    Entry point for incoming calls.
    Step 1: choose language by keypad (DTMF).
    """
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

    # If no input -> fallback + recovery SMS (only once)
    vr.say("We did not receive your choice. Goodbye.")
    if caller:
        send_sms_once(call_sid, "recovery", caller, f"{BUSINESS['name']}: Booking link: {RECOVERY_BOOKING_LINK}")
    return twiml(vr)


@app.post("/voice/lang")
async def voice_lang(request: Request):
    """
    Save language choice.
    Then gather speech: service + time.
    """
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

    # IMPORTANT: to avoid ugly Twilio RU voice, keep spoken prompt short + neutral
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

    vr.say("Sorry, I couldn't hear you. We will send you an SMS to book.")
    if caller:
        send_sms_once(call_sid, "recovery", caller, f"{BUSINESS['name']}: Booking link: {RECOVERY_BOOKING_LINK}")
    return twiml(vr)


@app.post("/voice/intent")
async def voice_intent(request: Request):
    """
    Parse speech with LLM to extract booking fields.
    Ask missing fields one by one.
    If collected: confirm + send SMS (Calendar integration later).
    """
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

Task: help customer book an appointment.
Return STRICT JSON with keys:
intent: "book" | "faq" | "other"
service: string|null
time_text: string|null
name: string|null
phone: string|null
need_human: boolean
reply_short: string  (short, neutral)
Rules:
- Ask ONE missing item at a time (service OR time OR name OR phone).
- If time is vague, ask for exact time like 15:30.
- Do not invent prices.
"""

    user = f"Customer said: {speech}\nCaller phone from network (may be empty): {caller}\nLanguage mode: {s.get('lang')}"
    try:
        data = openai_chat_json(system, user)
    except Exception:
        # Fallback: minimal capture attempt without LLM
        data = {
            "intent": "book",
            "service": None,
            "time_text": None,
            "name": None,
            "phone": caller if caller else None,
            "need_human": True,
            "reply_short": "OK.",
        }

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
        # Keep voice prompts short to avoid bad TTS. We handle language details in SMS later.
        if field == "service":
            q = "Please say the service. For example: men's haircut."
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
            language="en-US",  # neutral prompt
        )
        g.say(q)
        vr.append(g)

        vr.say("We will also send an SMS to finish booking.")
        if caller:
            send_sms_once(call_sid, "recovery", caller, f"{BUSINESS['name']}: Booking link: {RECOVERY_BOOKING_LINK}")
        return twiml(vr)

    # All fields collected -> capture request + SMS confirmation
    vr.say("Thank you. We will confirm by SMS.")
    if s.get("phone"):
        send_sms_once(
            call_sid,
            "confirm",
            s["phone"],
            f"{BUSINESS['name']}: Request received — {s['service']} / {s['time_text']}. "
            f"We work {BUSINESS['hours']}. If you need to change, use: {RECOVERY_BOOKING_LINK}"
        )
    s["status"] = "captured"
    return twiml(vr)


@app.post("/voice/fill")
async def voice_fill(request: Request):
    """
    Fill first missing field with the new speech and redirect back.
    """
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
    """
    Optional Twilio status callback: if call ends without captured booking -> recovery SMS (only once).
    """
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    call_status = str(form.get("CallStatus", ""))
    caller = str(form.get("From", ""))

    s = get_session(call_sid)

    if call_status in ("completed", "busy", "failed", "no-answer", "canceled"):
        if s.get("status") not in ("captured", "booked") and caller:
            send_sms_once(call_sid, "recovery", caller, f"{BUSINESS['name']}: Book here: {RECOVERY_BOOKING_LINK}")
            s["status"] = "recovery_sms_sent"

    return Response(content="ok", media_type="text/plain")
