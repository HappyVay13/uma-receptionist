import json
import re
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import text

from config.settings import TENANT_ID_DEFAULT
from core.language import get_lang
from core.parsing_time import sanitize_conversation_time_text
from db.database import engine
from integrations.pulse_booking_events import (
    LEGACY_R11_SCHEMA_VERSION,
    PendingBookingEvent,
    enqueue_booking_event,
    publisher_config_from_settings,
    wake_default_worker,
)


def norm_user_key(phone: str) -> str:
    raw = (phone or "").strip().replace("whatsapp:", "")
    if not raw:
        return "unknown"
    phone_like = re.sub(r"[^\d+]", "", raw)
    digits = re.sub(r"\D", "", phone_like)
    if len(digits) >= 7:
        return phone_like or "unknown"
    safe = re.sub(r"[^a-zA-Z0-9_:\-]", "_", raw).strip("_")
    return safe or "unknown"


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
                except Exception:
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


def _pending_booking_event(value: Any) -> PendingBookingEvent:
    if isinstance(value, PendingBookingEvent):
        return value
    if not isinstance(value, dict):
        raise ValueError("pending Pulse event metadata must be a mapping")
    occurred_at = value.get("occurred_at")
    starts_at = value.get("starts_at")
    ends_at = value.get("ends_at")
    if isinstance(occurred_at, str):
        occurred_at = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    if isinstance(starts_at, str) and starts_at:
        starts_at = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
    if isinstance(ends_at, str) and ends_at:
        ends_at = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
    return PendingBookingEvent(
        event_type=str(value.get("event_type") or ""),
        tenant_id=str(value.get("tenant_id") or ""),
        booking_ref=str(value.get("booking_ref") or ""),
        starts_at=starts_at,
        service_ref=(str(value.get("service_ref")).strip() if value.get("service_ref") else None),
        location_ref=(str(value.get("location_ref")).strip() if value.get("location_ref") else None),
        occurred_at=occurred_at,
        contract_version=str(value.get("contract_version") or LEGACY_R11_SCHEMA_VERSION),
        ends_at=ends_at,
        duration_minutes=(
            int(value.get("duration_minutes"))
            if value.get("duration_minutes") is not None
            else None
        ),
    )


def db_save_conversation(tenant_id: str, user_key: str, c: Dict[str, Any]) -> None:
    """Persist conversation state and an optional Pulse booking event atomically.

    The booking flow attaches ``_pulse_outbox_event`` only after Google Calendar has
    confirmed create/update/delete. When Pulse publishing is enabled, the final local
    conversation state and immutable outbox row commit in the same DB transaction.
    No HTTP request is performed here.
    """

    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    user_key = norm_user_key(user_key)
    pending_json = (
        json.dumps(c["pending"], ensure_ascii=False) if c.get("pending") else None
    )
    pulse_event_value = c.get("_pulse_outbox_event")
    publisher_config = publisher_config_from_settings()
    pulse_event = (
        _pending_booking_event(pulse_event_value)
        if pulse_event_value and publisher_config.enabled
        else None
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
            UPDATE conversations
            SET lang_lock=:lang, state=:state, service=:service, name=:name,
                datetime_iso=:dtiso, time_text=:tt, pending_json=:pj,
                updated_at=NOW()
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
                "tt": sanitize_conversation_time_text(c.get("time_text")),
                "pj": pending_json,
            },
        )
        if pulse_event is not None:
            if pulse_event.tenant_id.strip() != tenant_id:
                raise ValueError("Pulse event tenant does not match conversation tenant")
            enqueue_booking_event(
                conn,
                pulse_event,
                max_attempts=publisher_config.max_attempts,
            )

    c.pop("_pulse_outbox_event", None)
    if pulse_event is not None:
        wake_default_worker()
