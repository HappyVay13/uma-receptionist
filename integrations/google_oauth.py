import base64
import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from config.settings import (
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET,
    GOOGLE_OAUTH_REDIRECT_URI,
    GOOGLE_OAUTH_SCOPE,
)
from core.parsing_time import now_ts

log = logging.getLogger("repliq")


def oauth_ready() -> bool:
    return bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET and GOOGLE_OAUTH_REDIRECT_URI)


def build_google_oauth_state(tenant_id: str) -> str:
    payload = {"tenant_id": tenant_id, "ts": now_ts().isoformat()}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def parse_google_oauth_state(state: str) -> Dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode((state or "").encode("utf-8")).decode("utf-8")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def build_google_oauth_url(tenant_id: str) -> str:
    params = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_OAUTH_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": build_google_oauth_state(tenant_id),
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def exchange_google_code_for_tokens(code_value: str) -> Dict[str, Any]:
    data = {
        "code": code_value,
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    try:
        r = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=30)
        if r.status_code == 200:
            return r.json()
        log.error("google_token_exchange_failed status=%s body=%s", r.status_code, r.text[:500])
    except Exception as e:
        log.error("google_token_exchange_exception err=%s", e)
    return {}


def fetch_google_userinfo(access_token: str) -> Dict[str, Any]:
    if not access_token:
        return {}
    try:
        r = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()
        log.error("google_userinfo_failed status=%s body=%s", r.status_code, r.text[:300])
    except Exception as e:
        log.error("google_userinfo_exception err=%s", e)
    return {}


def fetch_google_calendar_list(access_token: str) -> List[Dict[str, Any]]:
    if not access_token:
        return []
    try:
        r = requests.get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("items", []) if isinstance(data, dict) else []
        log.error("google_calendar_list_failed status=%s body=%s", r.status_code, r.text[:300])
    except Exception as e:
        log.error("google_calendar_list_exception err=%s", e)
    return []


def token_expiry_from_google(expires_in: Any):
    try:
        seconds = int(expires_in)
    except Exception:
        return None
    if seconds <= 0:
        return None
    return now_ts() + timedelta(seconds=seconds)


def google_calendar_choice(calendars: List[Dict[str, Any]]) -> Optional[str]:
    if not calendars:
        return None
    for cal in calendars:
        if cal.get("primary") and str(cal.get("id") or "").strip():
            return str(cal.get("id")).strip()
    if len(calendars) == 1 and str(calendars[0].get("id") or "").strip():
        return str(calendars[0].get("id")).strip()
    return None
