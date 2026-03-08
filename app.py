import os
import json
import re
import urllib.parse
import base64
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Dict, Any, Optional, Tuple, List

import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client as TwilioClient
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from sqlalchemy import text

from google.oauth2 import service_account
from googleapiclient.discovery import build

from db.database import engine  # expects engine in db/database.py


# -------------------------
# LOGGING
# -------------------------
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("repliq")

app = FastAPI()

# -------------------------
# CORS (for Voice SDK / web demo)
# -------------------------
VOICE_SDK_ORIGINS = os.getenv("VOICE_SDK_ORIGINS", "*").strip()
origins = (
    [o.strip() for o in VOICE_SDK_ORIGINS.split(",") if o.strip()]
    if VOICE_SDK_ORIGINS != "*"
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# CONFIG
# -------------------------
TZ = timezone(timedelta(hours=2))  # Europe/Riga

TENANT_ID_DEFAULT = (os.getenv("DEFAULT_CLIENT_ID", "default") or "default").strip()
RECOVERY_BOOKING_LINK = os.getenv(
    "RECOVERY_BOOKING_LINK", "https://repliq.app/book"
).strip()

APPT_MINUTES = int(os.getenv("APPT_MINUTES", "30"))
WORK_START_HHMM_DEFAULT = os.getenv("WORK_START_HHMM", "09:00").strip()
WORK_END_HHMM_DEFAULT = os.getenv("WORK_END_HHMM", "18:00").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()

# Twilio Voice SDK (WebRTC) token minting
TWILIO_API_KEY_SID = os.getenv("TWILIO_API_KEY_SID", "").strip()
TWILIO_API_KEY_SECRET = os.getenv("TWILIO_API_KEY_SECRET", "").strip()
TWILIO_TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID", "").strip()

SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "").strip().rstrip("/")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

GOOGLE_TTS_VOICE_NAME = (
    os.getenv("GOOGLE_TTS_VOICE_NAME", "").strip()
    or os.getenv("GOOGLE_TTS_VOICE", "").strip()
    or "lv-LV-Standard-A"
)
GOOGLE_TTS_LANGUAGE_CODE = os.getenv("GOOGLE_TTS_LANGUAGE_CODE", "lv-LV").strip()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()

GOOGLE_CALENDAR_ID_FALLBACK = os.getenv("GOOGLE_CALENDAR_ID", "").strip()
CLIENT_STATUS_FALLBACK = (
    (os.getenv("CLIENT_STATUS", "trial") or "trial").strip().lower()
)
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

# -------------------------
# NEW: MULTI-TENANT DB HELPERS
# -------------------------


def tenants_columns() -> List[Dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
            SELECT column_name, is_nullable, column_default, data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='tenants'
            ORDER BY ordinal_position
        """
            )
        ).fetchall()
    return [
        {"name": r[0], "nullable": (r[1] == "YES"), "default": r[2], "type": r[3]}
        for r in rows
    ]


def tenants_pk(cols: List[Dict[str, Any]]) -> str:
    names = {c["name"] for c in cols}
    if "id" in names:
        return "id"
    if "tenant_id" in names:
        return "tenant_id"
    return "id"


def get_tenant_by_phone(to_number: str) -> Dict[str, Any]:
    to_number = (to_number or "").strip().replace("whatsapp:", "")
    if not to_number or to_number.lower() == "unknown":
        return get_tenant(TENANT_ID_DEFAULT)

    cols = tenants_columns()
    col_names = [c["name"] for c in cols]
    pk = tenants_pk(cols)

    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"SELECT {', '.join(col_names)} FROM tenants WHERE phone_number=:num LIMIT 1"
            ),
            {"num": to_number},
        ).fetchone()

    if not row:
        return get_tenant(TENANT_ID_DEFAULT)

    out: Dict[str, Any] = {}
    for i, name in enumerate(col_names):
        out[name] = row[i]
    out["_id"] = out.get(pk) or TENANT_ID_DEFAULT
    return out


def default_value_for_tenant_column(col_name: str, data_type: str) -> Any:
    n = col_name.lower()
    if n in ("business_name", "name"):
        return BUSINESS_FALLBACK["business_name"]
    if n in ("address", "business_address"):
        return BUSINESS_FALLBACK["address"]
    if n in ("services_lv",):
        return BUSINESS_FALLBACK["services_lv"]
    if n in ("services_ru",):
        return BUSINESS_FALLBACK["services_ru"]
    if n in ("services_en",):
        return BUSINESS_FALLBACK["services_en"]
    if n in ("services", "business_services"):
        return BUSINESS_FALLBACK["services_lv"]
    if n in ("work_start", "work_start_hhmm"):
        return BUSINESS_FALLBACK["work_start"]
    if n in ("work_end", "work_end_hhmm"):
        return BUSINESS_FALLBACK["work_end"]
    if n in ("status", "client_status"):
        return CLIENT_STATUS_FALLBACK
    if n in ("trial_end", "trial_end_at"):
        dt = parse_dt_any_tz(TRIAL_END_ISO_FALLBACK)
        return dt or (now_ts() + timedelta(days=14))
    if n in ("calendar_id", "google_calendar_id"):
        return GOOGLE_CALENDAR_ID_FALLBACK or ""
    if n in ("created_at", "updated_at"):
        return now_ts()
    dt = (data_type or "").lower()
    if "timestamp" in dt:
        return now_ts()
    if dt == "date":
        return today_local()
    if dt in ("integer", "bigint", "smallint"):
        return 0
    if dt in ("numeric", "double precision", "real"):
        return 0
    if dt == "boolean":
        return False
    if dt in ("json", "jsonb"):
        return {}
    return ""


def ensure_tenant_row(tenant_id: str) -> None:
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    cols = tenants_columns()
    pk = tenants_pk(cols)
    insert_cols = [pk]
    params: Dict[str, Any] = {"tid": tenant_id}
    for c in cols:
        name = c["name"]
        if name == pk:
            continue
        if (not c["nullable"]) and (c["default"] is None):
            insert_cols.append(name)
            params[name] = default_value_for_tenant_column(name, c["type"])
    col_sql = ", ".join(insert_cols)
    val_sql = ", ".join([":tid" if x == pk else f":{x}" for x in insert_cols])
    sql = f"INSERT INTO tenants ({col_sql}) VALUES ({val_sql}) ON CONFLICT ({pk}) DO NOTHING"
    with engine.begin() as conn:
        conn.execute(text(sql), params)


def get_tenant(tenant_id: str) -> Dict[str, Any]:
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    ensure_tenant_row(tenant_id)
    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = [c["name"] for c in cols]
    select_cols = ", ".join(col_names)
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {select_cols} FROM tenants WHERE {pk}=:tid LIMIT 1"),
            {"tid": tenant_id},
        ).fetchone()
    out: Dict[str, Any] = {"_id": tenant_id}
    if not row:
        return out
    for i, name in enumerate(col_names):
        out[name] = row[i]
    return out


# -------------------------
# TIME HELPERS
# -------------------------
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
    except:
        return None


# -------------------------
# TEXT / LANG HELPERS
# -------------------------
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
    p = (phone or "").strip().replace("whatsapp:", "")
    p = re.sub(r"[^\d+]", "", p)
    return p or "unknown"


def normalize_voice_caller(raw_from: str) -> str:
    v = (raw_from or "").strip()
    if v.startswith("client:"):
        v = v[len("client:") :]
    return v


def detect_language(text_: str) -> str:
    t = (text_ or "").strip().lower()
    if re.search(r"[āēīūčšžģķļņĀĒĪŪČŠŽĢĶĻŅ]", t):
        return "lv"
    if re.search(r"[а-яА-Я]", t):
        return "ru"
    lv_tokens = [
        "labdien",
        "sveiki",
        "ludzu",
        "paldies",
        "pierakst",
        "rit",
        "parit",
        "sodien",
        "cikos",
        "kad",
    ]
    score = sum(1 for tok in lv_tokens if tok in t)
    return "lv" if score >= 2 else "en"


def _short(s: Optional[str], n: int) -> str:
    return (s or "").strip()[:n]


def _parse_hhmm(hhmm: str) -> Tuple[int, int]:
    hh, mm = hhmm.split(":")
    return int(hh), int(mm)


def twiml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")


# -------------------------
# DB: CONVERSATIONS
# -------------------------
def db_get_or_create_conversation(
    tenant_id: str, user_key: str, default_lang: str
) -> Dict[str, Any]:
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    user_key = norm_user_key(user_key)
    default_lang = get_lang(default_lang)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
            SELECT lang_lock, state, service, name, datetime_iso, time_text, pending_json
            FROM conversations
            WHERE tenant_id=:tid AND user_key=:uk
            LIMIT 1
        """
            ),
            {"tid": tenant_id, "uk": user_key},
        ).fetchone()
        if row:
            pending = None
            if row[6]:
                try:
                    pending = json.loads(row[6])
                except:
                    pending = None
            return {
                "lang": get_lang(row[0]),
                "state": row[1] or "NEW",
                "service": row[2],
                "name": row[3],
                "datetime_iso": row[4],
                "time_text": row[5],
                "pending": pending,
            }
        conn.execute(
            text(
                """
            INSERT INTO conversations
              (tenant_id, user_key, lang_lock, state, updated_at)
            VALUES
              (:tid, :uk, :lang, 'NEW', NOW())
        """
            ),
            {"tid": tenant_id, "uk": user_key, "lang": default_lang},
        )
    return {
        "lang": default_lang,
        "state": "NEW",
        "service": None,
        "name": None,
        "datetime_iso": None,
        "time_text": None,
        "pending": None,
    }


def db_save_conversation(tenant_id: str, user_key: str, c: Dict[str, Any]) -> None:
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    user_key = norm_user_key(user_key)
    pending_json = (
        json.dumps(c["pending"], ensure_ascii=False) if c.get("pending") else None
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            UPDATE conversations
            SET lang_lock=:lang, state=:state, service=:service, name=:name,
                datetime_iso=:dtiso, time_text=:tt, pending_json=:pj, updated_at=NOW()
            WHERE tenant_id=:tid AND user_key=:uk
        """
            ),
            {
                "tid": tenant_id,
                "uk": user_key,
                "lang": get_lang(c.get("lang")),
                "state": c.get("state") or "NEW",
                "service": c.get("service"),
                "name": c.get("name"),
                "dtiso": c.get("datetime_iso"),
                "tt": c.get("time_text"),
                "pj": pending_json,
            },
        )


# -------------------------
# SaaS ACCESS CONTROL
# -------------------------
def tenant_allowed(tenant: Dict[str, Any]) -> Tuple[bool, str]:
    st = (
        tenant.get("status")
        or tenant.get("client_status")
        or CLIENT_STATUS_FALLBACK
        or "trial"
    ).lower()
    if st == "inactive":
        return False, "inactive"
    if st == "trial":
        te = tenant.get("trial_end") or tenant.get("trial_end_at")
        dt = parse_dt_any_tz(te) if isinstance(te, str) else te
        if not dt:
            dt = parse_dt_any_tz(TRIAL_END_ISO_FALLBACK)
        if dt and now_ts() > dt:
            return False, "trial_expired"
    return True, "ok"


def tenant_calendar_id(tenant: Dict[str, Any]) -> str:
    for key in ("calendar_id", "google_calendar_id", "calendarId"):
        if tenant.get(key):
            return str(tenant.get(key))
    return GOOGLE_CALENDAR_ID_FALLBACK or ""


def tenant_services_for_lang(tenant: Dict[str, Any], lang: str) -> str:
    lang = get_lang(lang)
    if lang == "lv" and tenant.get("services_lv"):
        return str(tenant.get("services_lv"))
    if lang == "ru" and tenant.get("services_ru"):
        return str(tenant.get("services_ru"))
    if lang == "en" and tenant.get("services_en"):
        return str(tenant.get("services_en"))
    if tenant.get("services"):
        return str(tenant.get("services"))
    return BUSINESS_FALLBACK[f"services_{lang}"]


def tenant_settings(tenant: Dict[str, Any], lang: str) -> Dict[str, Any]:
    biz_name = str(
        tenant.get("business_name")
        or tenant.get("name")
        or BUSINESS_FALLBACK["business_name"]
    )
    addr = str(tenant.get("address") or BUSINESS_FALLBACK["address"])
    return {
        "biz_name": biz_name,
        "addr": addr,
        "services_hint": tenant_services_for_lang(tenant, lang),
        "work_start": str(tenant.get("work_start") or WORK_START_HHMM_DEFAULT),
        "work_end": str(tenant.get("work_end") or WORK_END_HHMM_DEFAULT),
        "calendar_id": tenant_calendar_id(tenant),
    }


# -------------------------
# TWILIO / OPENAI / GOOGLE
# -------------------------
def twilio_client():
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        return None
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_message(to_number: str, body: str):
    client = twilio_client()
    if not client:
        return
    to_number = (to_number or "").strip()
    is_wa = to_number.startswith("whatsapp:")
    from_number = TWILIO_WHATSAPP_FROM if is_wa else TWILIO_FROM_NUMBER
    if not from_number:
        return
    try:
        client.messages.create(from_=from_number, to=to_number, body=body)
    except Exception as e:
        log.error(f"Twilio send error: {e}")


def openai_chat_json(system: str, user: str) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        return {"service": None, "time_text": None, "datetime_iso": None, "name": None}
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        if r.status_code == 200:
            return json.loads(r.json()["choices"][0]["message"]["content"])
    except:
        pass
    return {}


_GCAL = None


def get_gcal():
    global _GCAL
    if _GCAL:
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
    except:
        return None


def is_slot_busy(calendar_id: str, dt_start: datetime, dt_end: datetime) -> bool:
    svc = get_gcal()
    if not svc or not calendar_id:
        return False
    body = {
        "timeMin": dt_start.isoformat(),
        "timeMax": dt_end.isoformat(),
        "items": [{"id": calendar_id}],
    }
    try:
        fb = svc.freebusy().query(body=body).execute()
        return len(fb["calendars"][calendar_id].get("busy", [])) > 0
    except:
        return False


def create_calendar_event(
    calendar_id: str,
    dt_start: datetime,
    duration_min: int,
    summary: str,
    description: str,
):
    svc = get_gcal()
    if not svc or not calendar_id:
        return None
    dt_end = dt_start + timedelta(minutes=duration_min)
    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": dt_start.isoformat(), "timeZone": "Europe/Riga"},
        "end": {"dateTime": dt_end.isoformat(), "timeZone": "Europe/Riga"},
    }
    return (
        svc.events()
        .insert(calendarId=calendar_id, body=event)
        .execute()
        .get("htmlLink")
    )


# -------------------------
# TTS / VOICE OUTPUT
# -------------------------
_TTS = None


def get_google_tts():
    global _TTS
    if _TTS:
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
    except:
        return None


def google_tts_mp3(text_: str, lang_code: str, voice_name: str) -> bytes:
    svc = get_google_tts()
    if not svc or not text_:
        return b""
    body = {
        "input": {"text": text_[:350]},
        "voice": {"languageCode": lang_code, "name": voice_name},
        "audioConfig": {"audioEncoding": "MP3"},
    }
    try:
        resp = svc.text().synthesize(body=body).execute()
        return base64.b64decode(resp["audioContent"])
    except:
        return b""
    # -------------------------


# CALENDAR LOGIC (Business Hours & Slots)
# -------------------------
def in_business_hours(
    dt_start: datetime, duration_min: int, work_start: str, work_end: str
) -> bool:
    try:
        ws_h, ws_m = _parse_hhmm(work_start)
        we_h, we_m = _parse_hhmm(work_end)
        day_start = dt_start.replace(hour=ws_h, minute=ws_m, second=0, microsecond=0)
        day_end = dt_start.replace(hour=we_h, minute=we_m, second=0, microsecond=0)
        return (
            dt_start >= day_start
            and (dt_start + timedelta(minutes=duration_min)) <= day_end
        )
    except:
        return False


def find_next_two_slots(
    calendar_id: str,
    dt_start: datetime,
    duration_min: int,
    work_start: str,
    work_end: str,
):
    step, found = 30, []
    candidate = dt_start + timedelta(minutes=step)
    for _ in range(48):
        if in_business_hours(candidate, duration_min, work_start, work_end):
            if not is_slot_busy(
                calendar_id, candidate, candidate + timedelta(minutes=duration_min)
            ):
                found.append(candidate)
                if len(found) == 2:
                    return found[0], found[1]
        candidate += timedelta(minutes=step)
    return None


def find_next_event_by_phone(calendar_id: str, phone: str):
    svc = get_gcal()
    if not svc or not calendar_id:
        return None
    now = now_ts().isoformat()
    try:
        events = (
            svc.events()
            .list(
                calendarId=calendar_id,
                timeMin=now,
                singleEvents=True,
                orderBy="startTime",
                maxResults=20,
            )
            .execute()
        )
        for ev in events.get("items", []):
            if phone in (ev.get("description") or ""):
                return ev
    except:
        pass
    return None


def delete_calendar_event(calendar_id: str, event_id: str):
    svc = get_gcal()
    if svc and calendar_id:
        try:
            svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            log.info(f"Deleted calendar event: calendar_id={calendar_id}, event_id={event_id}")
            return True
        except Exception as e:
            log.error(f"Delete calendar event failed: calendar_id={calendar_id}, event_id={event_id}, err={e}")
            return False
    return False


# -------------------------
# DATE PARSING Fallbacks
# -------------------------
def parse_time_text_to_dt(text_: str) -> Optional[datetime]:
    m = re.search(r"\b([01]?\d|2[0-3])[:. ]([0-5]\d)\b", (text_ or "").lower())
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    base = today_local()
    t_low = text_.lower()
    if any(k in t_low for k in ["parīt", "послезавтра", "day after tomorrow"]):
        base += timedelta(days=2)
    elif any(k in t_low for k in ["rīt", "rit", "завтра", "tomorrow"]):
        base += timedelta(days=1)
    return datetime(base.year, base.month, base.day, hh, mm, tzinfo=TZ)


def parse_dt_from_iso_or_fallback(
    datetime_iso: Optional[str], time_text: Optional[str], raw_text: Optional[str]
) -> Optional[datetime]:
    dt = parse_dt_any_tz((datetime_iso or "").strip())
    return dt if dt else parse_time_text_to_dt(f"{time_text or ''} {raw_text or ''}")


# -------------------------
# CORE LOGIC: handle_user_text
# -------------------------
def handle_user_text(
    tenant_id: str, raw_phone: str, text_in: str, channel: str, lang_hint: str
) -> Dict[str, Any]:
    msg = (text_in or "").strip()
    tenant = get_tenant(tenant_id)
    allowed, _ = tenant_allowed(tenant)
    l_hint = get_lang(lang_hint)

    if not allowed:
        return {
            "status": "blocked",
            "reply_voice": "Atvainojiet, serviss nav pieejams.",
            "msg_out": "Serviss nav pieejams.",
            "lang": l_hint,
        }

    user_key = norm_user_key(raw_phone)
    c = db_get_or_create_conversation(tenant_id, user_key, l_hint)
    lang = get_lang(c["lang"])
    settings = tenant_settings(tenant, lang)

    # Intents: Reschedule / Cancel
    t_low = msg.lower()
    if any(w in t_low for w in ["pārcelt", "перенести", "reschedule"]):
        ev = find_next_event_by_phone(settings["calendar_id"], raw_phone)
        if not ev:
            return {
                "status": "no_booking",
                "reply_voice": "Jums nav aktīvu pierakstu.",
                "msg_out": "Jums nav aktīvu pierakstu.",
                "lang": lang,
            }
        dt_old = parse_dt_any_tz(ev["start"]["dateTime"])
        c["pending"] = {
            "reschedule_event_id": ev["id"],
            "reschedule_old_iso": ev["start"]["dateTime"],
        }
        db_save_conversation(tenant_id, user_key, c)
        ws = dt_old.strftime("%d.%m %H:%M") if dt_old else ""
        return {
            "status": "reschedule_wait",
            "reply_voice": f"Pieraksts {ws}. Uz kuru laiku pārcelt?",
            "msg_out": f"Pieraksts {ws}. Uz kuru laiku pārcelt?",
            "lang": lang,
        }

    if any(w in t_low for w in ["atcelt", "отменить", "cancel"]):
        ev = find_next_event_by_phone(settings["calendar_id"], raw_phone)
        if not ev:
            return {
                "status": "no_booking",
                "reply_voice": "Jums nav aktīvu pierakstu.",
                "msg_out": "Jums nav aktīvu pierakstu.",
                "lang": lang,
            }

        deleted = delete_calendar_event(settings["calendar_id"], ev["id"])
        if not deleted:
            return {
                "status": "cancel_failed",
                "reply_voice": "Neizdevās atcelt pierakstu. Mēģiniet vēlreiz.",
                "msg_out": "Neizdevās atcelt pierakstu. Mēģiniet vēlreiz.",
                "lang": lang,
            }

        return {
            "status": "cancelled",
            "reply_voice": "Pieraksts atcelts.",
            "msg_out": "Pieraksts atcelts.",
            "lang": lang,
        }

    # 1/2 Selection
    if msg in ("1", "2") and c.get("pending") and "opt1_iso" in c["pending"]:
        p = c["pending"]
        dt_sel = parse_dt_any_tz(p["opt1_iso"] if msg == "1" else p["opt2_iso"])
        svc = p.get("service") or c.get("service") or settings["services_hint"]
        nm = p.get("name") or c.get("name") or "Klients"
        create_calendar_event(
            settings["calendar_id"],
            dt_sel,
            APPT_MINUTES,
            f"{settings['biz_name']} - {svc}",
            f"Name: {nm}\nPhone: {raw_phone}",
        )
        c["pending"], c["state"], c["datetime_iso"] = None, "BOOKED", dt_sel.isoformat()
        db_save_conversation(tenant_id, user_key, c)
        return {
            "status": "booked",
            "reply_voice": "Paldies, pieraksts apstпирrināts!",
            "msg_out": f"Apstiprināts: {dt_sel.strftime('%d.%m %H:%M')}",
            "lang": lang,
        }

    # AI Extraction
    sys_pt = f"Receptionist for {settings['biz_name']}. Hours: {settings['work_start']}-{settings['work_end']}. Services: {settings['services_hint']}. Return JSON: service, time_text, datetime_iso, name."
    usr_pt = f"Today: {now_ts().date()}. User: {msg}. Lang: {lang}."
    data = openai_chat_json(sys_pt, usr_pt)

    if data.get("service"):
        c["service"] = data["service"]
    if data.get("name"):
        c["name"] = data["name"]
    dt_start = parse_dt_from_iso_or_fallback(
        data.get("datetime_iso"), data.get("time_text"), msg
    )
    if not dt_start:
        dt_start = parse_dt_any_tz(c.get("datetime_iso") or "")
    if dt_start:
        c["datetime_iso"] = dt_start.isoformat()
    db_save_conversation(tenant_id, user_key, c)

    # Validations... (продолжение логики в Части 5)
    # (Продолжение handle_user_text)
    if not c.get("service"):
        return {
            "status": "need_more",
            "reply_voice": "Kādu pakalpojumu vēlaties?",
            "msg_out": "Kādu pakalсовуму vēlaties?",
            "lang": lang,
        }
    if not dt_start:
        return {
            "status": "need_more",
            "reply_voice": "Kad un cikos jums būtu ērti?",
            "msg_out": "Kad un cikos jums būtu ērti?",
            "lang": lang,
        }
    if not c.get("name"):
        return {
            "status": "need_more",
            "reply_voice": "Kā jūs sauc?",
            "msg_out": "Kā jūs sauc?",
            "lang": lang,
        }

    # Business hours check
    if not in_business_hours(
        dt_start, APPT_MINUTES, settings["work_start"], settings["work_end"]
    ):
        opts = find_next_two_slots(
            settings["calendar_id"],
            dt_start,
            APPT_MINUTES,
            settings["work_start"],
            settings["work_end"],
        )
        if opts:
            c["pending"] = {
                "opt1_iso": opts[0].isoformat(),
                "opt2_iso": opts[1].isoformat(),
                "service": c["service"],
                "name": c["name"],
            }
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "busy",
                "reply_voice": "Šajā laikā nestrādājam. Nosūtu brīvos laikus ziņā.",
                "msg_out": f"Nestradajam. Varianti: 1){opts[0].strftime('%H:%M')} 2){opts[1].strftime('%H:%M')}",
                "lang": lang,
            }
        return {
            "status": "recovery",
            "reply_voice": "Atvainojiet, visi laiki ir aizņemti.",
            "msg_out": "Visi laiki aizņemti. Mēģiniet vēlāk.",
            "lang": lang,
        }

    # Busy check
    if is_slot_busy(
        settings["calendar_id"], dt_start, dt_start + timedelta(minutes=APPT_MINUTES)
    ):
        opts = find_next_two_slots(
            settings["calendar_id"],
            dt_start,
            APPT_MINUTES,
            settings["work_start"],
            settings["work_end"],
        )
        if opts:
            c["pending"] = {
                "opt1_iso": opts[0].isoformat(),
                "opt2_iso": opts[1].isoformat(),
                "service": c["service"],
                "name": c["name"],
            }
            db_save_conversation(tenant_id, user_key, c)
            return {
                "status": "busy",
                "reply_voice": "Šis laiks ir aizņemts. Nosūtu variantus ziņā.",
                "msg_out": f"Aizņemts. Varianti: 1){opts[0].strftime('%H:%M')} 2){opts[1].strftime('%H:%M')}",
                "lang": lang,
            }
        return {
            "status": "recovery",
            "reply_voice": "Visi laiki aizņemti.",
            "msg_out": "Nav brīvu laiku.",
            "lang": lang,
        }

    # Apply Reschedule if pending
    if c.get("pending") and c["pending"].get("reschedule_event_id"):
        delete_calendar_event(
            settings["calendar_id"], c["pending"]["reschedule_event_id"]
        )
        c["pending"] = None

    # Final Booking
    create_calendar_event(
        settings["calendar_id"],
        dt_start,
        APPT_MINUTES,
        f"{settings['biz_name']} - {c['service']}",
        f"Name: {c['name']}\nPhone: {raw_phone}",
    )
    c["state"] = "BOOKED"
    db_save_conversation(tenant_id, user_key, c)
    return {
        "status": "booked",
        "reply_voice": "Paldies! Pieraksts apstiprināts.",
        "msg_out": f"Apstiprināts: {c['service']} {dt_start.strftime('%d.%m %H:%M')}",
        "lang": lang,
    }


# -------------------------
# TWILIO ENDPOINTS
# -------------------------


@app.post("/voice/incoming")
async def voice_incoming(request: Request):
    form = await request.form()
    to_num = str(form.get("To", ""))
    tenant = get_tenant_by_phone(to_num)
    biz = tenant_settings(tenant, "lv")["biz_name"]

    vr = VoiceResponse()
    g = Gather(
        input="speech",
        action="/voice/intent",
        method="POST",
        timeout=7,
        language="lv-LV",
    )
    say_or_play(g, f"Labdien! Jūs sazvanījāt {biz}. Kā varu palīdzēt?", "lv")
    vr.append(g)
    return twiml(vr)


@app.post("/voice/intent")
async def voice_intent(request: Request):
    form = await request.form()
    to_num = str(form.get("To", ""))
    caller = normalize_voice_caller(str(form.get("From", "")))
    speech = str(form.get("SpeechResult", "")).strip()

    tenant = get_tenant_by_phone(to_num)
    result = handle_user_text(tenant["_id"], caller, speech, "voice", "lv")

    vr = VoiceResponse()
    say_or_play(vr, result["reply_voice"], result["lang"])
    if result["status"] == "need_more":
        vr.append(
            Gather(
                input="speech",
                action="/voice/intent",
                method="POST",
                timeout=7,
                language="lv-LV",
            )
        )
    else:
        vr.hangup()

    # Send SMS confirmation after call if booked
    if result["status"] == "booked" and caller != "unknown":
        send_message(
            caller,
            f"{tenant_settings(tenant, result['lang'])['biz_name']}: {result['msg_out']}",
        )

    return twiml(vr)


@app.post("/sms/incoming")
async def sms_incoming(request: Request):
    form = await request.form()
    to_num = str(form.get("To", ""))
    from_num = str(form.get("From", ""))
    body = str(form.get("Body", "")).strip()

    tenant = get_tenant_by_phone(to_num)
    result = handle_user_text(
        tenant["_id"], from_num, body, "sms", detect_language(body)
    )
    biz = tenant_settings(tenant, result["lang"])["biz_name"]
    send_message(from_num, f"{biz}: {result['msg_out']}")
    return Response(status_code=204)


@app.post("/whatsapp/incoming")
async def whatsapp_incoming(request: Request):
    form = await request.form()
    to_num = str(form.get("To", "")).replace("whatsapp:", "")
    from_num = str(form.get("From", ""))
    body = str(form.get("Body", "")).strip()

    tenant = get_tenant_by_phone(to_num)
    result = handle_user_text(
        tenant["_id"], from_num, body, "whatsapp", detect_language(body)
    )
    biz = tenant_settings(tenant, result["lang"])["biz_name"]
    send_message(from_num, f"{biz}: {result['msg_out']}")
    return Response(status_code=204)


# -------------------------
# BROWSER SDK TOKEN
# -------------------------
@app.get("/voice/token")
def get_voice_token(client_id: str = "default"):
    if not (
        TWILIO_ACCOUNT_SID
        and TWILIO_API_KEY_SID
        and TWILIO_API_KEY_SECRET
        and TWILIO_TWIML_APP_SID
    ):
        raise HTTPException(status_code=500, detail="Twilio Voice SDK config missing")

    token = AccessToken(
        TWILIO_ACCOUNT_SID,
        TWILIO_API_KEY_SID,
        TWILIO_API_KEY_SECRET,
        identity=client_id,
    )
    grant = VoiceGrant(
        outgoing_application_sid=TWILIO_TWIML_APP_SID, incoming_allow=True
    )
    token.add_grant(grant)
    return {"token": token.to_jwt(), "identity": client_id}


@app.on_event("startup")
def _startup():
    ensure_tenant_row(TENANT_ID_DEFAULT)


@app.get("/health")
def health():
    return {"status": "ok", "tz": str(TZ)}
