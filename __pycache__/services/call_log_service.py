import logging
from typing import Any, Callable, Dict, Optional

from sqlalchemy import text

log = logging.getLogger("repliq")


def log_call_event(
    *,
    engine,
    norm_user_key_fn: Callable[[str], str],
    infer_intent_fn: Callable[[str, str, Optional[Dict[str, Any]]], str],
    default_tenant_id: str,
    tenant_id: str,
    user_id: str,
    channel: str,
    raw_text: str,
    result: Dict[str, Any],
    conv: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        conv = conv or {}
        intent = infer_intent_fn(raw_text, str((result or {}).get("status") or "").strip(), conv)
        service = str(conv.get("service") or "").strip() or None
        datetime_iso = str(conv.get("datetime_iso") or "").strip() or None
        status = str((result or {}).get("status") or "").strip() or "unknown"
        ai_reply = str((result or {}).get("msg_out") or (result or {}).get("reply_voice") or "").strip() or None

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO call_logs
                    (tenant_id, user_id, channel, intent, service, datetime_iso, status, raw_text, ai_reply)
                    VALUES
                    (:tenant_id, :user_id, :channel, :intent, :service, :datetime_iso, :status, :raw_text, :ai_reply)
                    """
                ),
                {
                    "tenant_id": (tenant_id or "").strip() or default_tenant_id,
                    "user_id": norm_user_key_fn(user_id),
                    "channel": (channel or "").strip().lower() or "unknown",
                    "intent": intent,
                    "service": service,
                    "datetime_iso": datetime_iso,
                    "status": status,
                    "raw_text": (raw_text or "").strip(),
                    "ai_reply": ai_reply,
                },
            )
    except Exception as e:
        log.error("call_log_write_failed tenant_id=%s user_id=%s err=%s", tenant_id, user_id, e)
