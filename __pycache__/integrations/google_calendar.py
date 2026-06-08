import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config.settings import GOOGLE_SERVICE_ACCOUNT_JSON
from core.parsing_time import now_ts

log = logging.getLogger("repliq")

_GCAL = None
_GCAL_BY_KEY: Dict[str, Any] = {}


def calendar_is_configured(calendar_id: str) -> bool:
    return bool((calendar_id or "").strip())


def _norm_user_key(phone: str) -> str:
    raw = (phone or "").strip().replace("whatsapp:", "")
    if not raw:
        return "unknown"
    phone_like = re.sub(r"[^\d+]", "", raw)
    digits = re.sub(r"\D", "", phone_like)
    if len(digits) >= 7:
        return phone_like or "unknown"
    safe = re.sub(r"[^a-zA-Z0-9_:\-]", "_", raw).strip("_")
    return safe or "unknown"


def _normalize_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        return str(value[0]).strip() if value else None
    if isinstance(value, dict):
        for k in ("name", "first_name", "full_name"):
            if value.get(k):
                return str(value[k]).strip()
        vals = [str(v).strip() for v in value.values() if str(v).strip()]
        return vals[0] if vals else None
    txt = str(value).strip()
    return txt or None


def tenant_event_marker(tenant_id: str) -> str:
    return f"Tenant ID: {tenant_id}"


def build_event_description(tenant_id: str, client_name: str, raw_phone: str) -> str:
    return f"Name: {client_name}\nPhone: {raw_phone}\n{tenant_event_marker(tenant_id)}"


def event_belongs_to_tenant(ev: Dict[str, Any], tenant_id: str, phone: str) -> bool:
    desc = ev.get("description") or ""
    marker = tenant_event_marker(tenant_id)
    phone_norm = _norm_user_key(phone)
    desc_norm = _norm_user_key(desc)
    if marker in desc:
        return bool(phone_norm and phone_norm in desc_norm)
    return bool((phone_norm and phone_norm in desc_norm) or (phone and phone in desc))


def extract_name_from_event_description(description: str) -> Optional[str]:
    text_ = str(description or "")
    m = re.search(r"^Name:\s*(.+)$", text_, flags=re.IGNORECASE | re.MULTILINE)
    if m:
        return _normalize_name(m.group(1))
    m = re.search(r"^Имя:\s*(.+)$", text_, flags=re.IGNORECASE | re.MULTILINE)
    if m:
        return _normalize_name(m.group(1))
    return None


def get_gcal(service_account_json: Optional[str] = None):
    global _GCAL, _GCAL_BY_KEY
    effective_json = (service_account_json or GOOGLE_SERVICE_ACCOUNT_JSON or "").strip()
    if not effective_json:
        return None
    if effective_json == (GOOGLE_SERVICE_ACCOUNT_JSON or "").strip() and _GCAL is not None:
        return _GCAL
    if effective_json in _GCAL_BY_KEY:
        return _GCAL_BY_KEY[effective_json]
    try:
        info = json.loads(effective_json)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/calendar"]
        )
        svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        _GCAL_BY_KEY[effective_json] = svc
        if effective_json == (GOOGLE_SERVICE_ACCOUNT_JSON or "").strip():
            _GCAL = svc
        return svc
    except Exception as e:
        log.error("Google Calendar init failed: %s", e)
        return None


def is_slot_busy(calendar_id: str, dt_start: datetime, dt_end: datetime, buffer_minutes: int = 0, service_account_json: Optional[str] = None) -> bool:
    svc = get_gcal(service_account_json)
    if not svc or not calendar_id:
        return False
    window_start = dt_start - timedelta(minutes=max(0, int(buffer_minutes or 0)))
    window_end = dt_end + timedelta(minutes=max(0, int(buffer_minutes or 0)))
    body = {
        "timeMin": window_start.isoformat(),
        "timeMax": window_end.isoformat(),
        "items": [{"id": calendar_id}],
    }
    try:
        fb = svc.freebusy().query(body=body).execute()
        return len(fb["calendars"][calendar_id].get("busy", [])) > 0
    except Exception as e:
        log.error("Calendar freebusy failed: %s", e)
        return False


def create_calendar_event(
    calendar_id: str,
    dt_start: datetime,
    duration_min: int,
    summary: str,
    description: str,
    service_account_json: Optional[str] = None,
):
    svc = get_gcal(service_account_json)
    if not svc or not calendar_id:
        return None
    dt_end = dt_start + timedelta(minutes=duration_min)
    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": dt_start.isoformat(), "timeZone": "Europe/Riga"},
        "end": {"dateTime": dt_end.isoformat(), "timeZone": "Europe/Riga"},
    }
    try:
        return (
            svc.events()
            .insert(calendarId=calendar_id, body=event)
            .execute()
            .get("htmlLink")
        )
    except Exception as e:
        log.error("Create calendar event failed: %s", e)
        return None


def update_calendar_event(
    calendar_id: str,
    event_id: str,
    dt_start: datetime,
    duration_min: int,
    summary: str,
    description: str,
    service_account_json: Optional[str] = None,
):
    svc = get_gcal(service_account_json)
    if not svc or not calendar_id or not event_id:
        return None
    dt_end = dt_start + timedelta(minutes=duration_min)
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": dt_start.isoformat(), "timeZone": "Europe/Riga"},
        "end": {"dateTime": dt_end.isoformat(), "timeZone": "Europe/Riga"},
    }
    try:
        return (
            svc.events()
            .patch(calendarId=calendar_id, eventId=event_id, body=body)
            .execute()
            .get("htmlLink")
        )
    except Exception as e:
        log.error("Update calendar event failed: %s", e)
        return None


def find_next_event_by_phone(calendar_id: str, phone: str, tenant_id: Optional[str] = None, service_account_json: Optional[str] = None):
    svc = get_gcal(service_account_json)
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
            if tenant_id:
                if event_belongs_to_tenant(ev, tenant_id, phone):
                    return ev
            else:
                desc = ev.get("description") or ""
                phone_norm = _norm_user_key(phone)
                if phone_norm and phone_norm in _norm_user_key(desc):
                    return ev
                if phone in desc:
                    return ev
    except Exception as e:
        log.error("Find next event failed: %s", e)
    return None


def delete_calendar_event(calendar_id: str, event_id: str, service_account_json: Optional[str] = None):
    svc = get_gcal(service_account_json)
    if svc and calendar_id:
        try:
            svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            log.info(
                "Deleted calendar event: calendar_id=%s, event_id=%s",
                calendar_id,
                event_id,
            )
            return True
        except Exception as e:
            log.error(
                "Delete calendar event failed: calendar_id=%s, event_id=%s, err=%s",
                calendar_id,
                event_id,
                e,
            )
            return False
    return False
