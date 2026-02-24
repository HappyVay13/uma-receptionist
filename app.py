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
    "name": os.getenv("BIZ_NAME", "Uma"),
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

# In-memory sessions for MVP
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
        }
        SESSIONS[call_sid] = s
    return s

def twiml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")

def openai_chat(system: str, user: str) -> Dict[str, Any]:
    """
    Returns parsed JSON dict. If something fails -> safe fallback dict.
    """
    if not OPENAI_API_KEY:
        return {
            "intent": "book",
            "service": None,
            "time_text": None,
            "name": None,
            "phone": None,
            "need_human": True,
            "reply_ru": "Извините, сервис временно недоступен. Мы отправим вам SMS со ссылкой для записи.",
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

def normalize_time_request(text: str) -> str:
    return text.strip()[:120]

# ====== ROUTES ======

@app.post("/voice/incoming")
async def voice_incoming(request: Request):
    """
    First entry point for incoming calls.
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
    g.say("Hello. For Latvian, press 1. For Russian, press 2.")
    vr.append(g)

    # If no input -> short fallback + recovery SMS
    vr.say("We did not receive your choice. Goodbye.")
    if caller:
        send_sms(caller, f"{BUSINESS['name']}: Booking link: {RECOVERY_BOOKING_LINK}")
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
    s["lang"] = "lv" if digit == "1" else "ru"

    vr = VoiceResponse()

    # MVP: Russian voice flow is primary; Latvian can still speak (STT may vary), plus SMS fallback.
    if s["lang"] == "ru":
        prompt = (
            f"Здравствуйте! Это {BUSINESS['name']}. "
            f"Мы работаем {BUSINESS['hours']}. "
            "Скажите, пожалуйста: мужская или женская стрижка, и на какое время вы хотите записаться."
        )
        stt_lang = "ru-RU"
    else:
        prompt = (
            f"Hello! This is {BUSINESS['name']}. "
            "Please say your request and preferred time. You may also speak Russian."
        )
        stt_lang = "lv-LV"

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
        send_sms(caller, f"{BUSINESS['name']}: Booking link: {RECOVERY_BOOKING_LINK}")
    return twiml(vr)

@app.post("/voice/intent")
async def voice_intent(request: Request):
    """
    Parse speech with LLM to extract booking fields.
    Then ask missing fields one by one.
    If collected: confirm + send SMS (Calendar integration will be next step).
    """
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    caller = str(form.get("From", ""))
    speech = str(form.get("SpeechResult", "")).strip()

    s = get_session(call_sid)
    s["caller"] = caller

    system = f"""
Ты — Uma, ИИ-администратор салона стрижек.
Бизнес:
- Название: {BUSINESS['name']}
- Часы: {BUSINESS['hours']}
- Услуги: {BUSINESS['services']}

Задача: помочь записаться.
Верни СТРОГО JSON со следующими ключами:
intent: "book" | "faq" | "other"
service: строка или null (например "мужская стрижка" / "женская стрижка")
time_text: строка или null (например "завтра 15:30")
name: строка или null
phone: строка или null (если нет — null)
need_human: true/false
reply_ru: короткий текст-ответ на русском, дружелюбный, без воды.

Правила:
- Если чего-то не хватает (имя/время/услуга/телефон), попроси ОДИН пункт за раз.
- Не придумывай цены.
- Не подтверждай конкретную запись как окончательную (календарь подключим позже), но можешь сказать "я зафиксировала заявку" и попросить уточнения.
"""

    user = f"Речь клиента: {speech}\nНомер из сети (если есть): {caller}\nРежим языка: {s.get('lang')}"
    try:
        data = openai_chat(system, user)
    except Exception:
        data = {
            "intent": "book",
            "service": None,
            "time_text": None,
            "name": None,
            "phone": caller if caller else None,
            "need_human": True,
            "reply_ru": "Поняла. Давайте уточним детали для записи.",
        }

    # Fill session from LLM
    s["service"] = data.get("service") or s.get("service")
    s["time_text"] = data.get("time_text") or s.get("time_text")
    s["name"] = data.get("name") or s.get("name")
    s["phone"] = data.get("phone") or s.get("phone") or (caller if caller else None)

    # Decide what's missing
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
        # Ask only one missing field
        field = missing[0]
        if field == "service":
            q = "Уточните, пожалуйста: мужская стрижка или женская стрижка?"
        elif field == "time":
            q = "На какое точное время вас записать? Скажите, пожалуйста, в формате пятнадцать тридцать."
        elif field == "name":
            q = "Как я могу к вам обращаться?"
        else:
            q = "Продиктуйте, пожалуйста, номер телефона."

        g = Gather(
            input="speech",
            action="/voice/fill",
            method="POST",
            timeout=7,
            speech_timeout="auto",
            language="ru-RU",
        )
        g.say(q)
        vr.append(g)

        # Fallback to SMS booking if no response
        vr.say("Если неудобно говорить, мы отправим вам SMS со ссылкой для записи.")
        if caller:
            send_sms(caller, f"{BUSINESS['name']}: Booking link: {RECOVERY_BOOKING_LINK}")
        return twiml(vr)

    # If we have all fields -> "confirm request" and SMS
    vr.say(
        f"Отлично, {s['name']}. Я зафиксировала заявку: {s['service']}, время: {s['time_text']}. "
        "Мы подтвердим запись сообщением."
    )

    if s.get("phone"):
        send_sms(
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
    Optional Twilio status callback: if call ends without captured booking -> recovery SMS.
    """
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    call_status = str(form.get("CallStatus", ""))
    caller = str(form.get("From", ""))

    s = get_session(call_sid)

    if call_status in ("completed", "busy", "failed", "no-answer", "canceled"):
        if s.get("status") not in ("captured", "booked") and caller:
            send_sms(caller, f"{BUSINESS['name']}: Book here: {RECOVERY_BOOKING_LINK}")
            s["status"] = "recovery_sms_sent"

    return Response(content="ok", media_type="text/plain")
