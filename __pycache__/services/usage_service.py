import logging
from typing import Any, Callable, Dict, Optional

from sqlalchemy import text

log = logging.getLogger("repliq")


def usage_type_from_event(
    raw_text: str,
    result: Dict[str, Any],
    conv: Optional[Dict[str, Any]] = None,
    infer_intent_fn: Optional[Callable[[str, str, Optional[Dict[str, Any]]], str]] = None,
) -> str:
    status = str((result or {}).get("status") or "").strip().lower()
    intent = "unknown"
    if infer_intent_fn is not None:
        intent = infer_intent_fn(raw_text, status, conv)

    if status == "booked":
        return "booking"
    if intent == "reschedule":
        return "reschedule"
    if intent == "cancel":
        return "cancel"
    if intent == "info" or status == "info":
        return "faq"
    return "message"


def record_usage_event(
    *,
    engine,
    ensure_usage_events_table_fn: Callable[[], None],
    usage_event_is_billable_fn: Callable[[str, str], bool],
    norm_user_key_fn: Callable[[str], str],
    infer_intent_fn: Callable[[str, str, Optional[Dict[str, Any]]], str],
    default_tenant_id: str,
    tenant_id: str,
    user_id: str,
    channel: str,
    raw_text: str,
    result: Dict[str, Any],
    conv: Optional[Dict[str, Any]] = None,
    source: str = "runtime",
) -> None:
    try:
        ensure_usage_events_table_fn()
        usage_type = usage_type_from_event(raw_text, result, conv, infer_intent_fn=infer_intent_fn)
        billable = usage_event_is_billable_fn(channel, source)
        status = str((result or {}).get("status") or "").strip() or None
        tenant_value = (tenant_id or "").strip() or default_tenant_id
        user_value = norm_user_key_fn(user_id)
        channel_value = (channel or "").strip().lower() or "unknown"
        source_value = (source or "runtime").strip().lower() or "runtime"

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO usage_events
                    (tenant_id, user_id, channel, usage_type, usage_units, billable, source, status)
                    VALUES
                    (:tenant_id, :user_id, :channel, :usage_type, :usage_units, :billable, :source, :status)
                    """
                ),
                {
                    "tenant_id": tenant_value,
                    "user_id": user_value,
                    "channel": channel_value,
                    "usage_type": usage_type,
                    "usage_units": 1,
                    "billable": billable,
                    "source": source_value,
                    "status": status,
                },
            )
        log.info(
            "usage_event_written tenant_id=%s user_id=%s channel=%s usage_type=%s billable=%s status=%s",
            tenant_value,
            user_value,
            channel_value,
            usage_type,
            billable,
            status or "",
        )
    except Exception as e:
        log.error("usage_event_write_failed tenant_id=%s user_id=%s err=%s", tenant_id, user_id, e)
