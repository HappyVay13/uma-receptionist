from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from sqlalchemy import text


def _tenant_id(tenant: Dict[str, Any]) -> str:
    return str(tenant.get("_id") or tenant.get("id") or tenant.get("tenant_id") or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return default


def _now_ts() -> Any:
    try:
        from core.parsing_time import now_ts
        return now_ts()
    except Exception:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc)


def _query_rows(engine, sql: str, params: Dict[str, Any]) -> List[Any]:
    try:
        with engine.connect() as conn:
            return list(conn.execute(text(sql), params).fetchall())
    except Exception:
        return []


def build_uma_signals(engine, tenant: Dict[str, Any], days: int = 14) -> Dict[str, Any]:
    """Build lightweight business signals from existing call_logs/usage_events.

    This is intentionally read-only and defensive. If the runtime tables are missing
    or empty, UMA returns an empty-but-valid signal payload instead of breaking Repliq.
    """
    tid = _tenant_id(tenant)
    days = max(1, min(_safe_int(days, 14), 90))
    since_ts = _now_ts() - timedelta(days=days)

    totals_rows = _query_rows(
        engine,
        """
        SELECT
          COUNT(*) AS total_dialogs,
          COUNT(*) FILTER (WHERE status='booked') AS bookings,
          COUNT(*) FILTER (WHERE status IN ('busy','recovery','booking_failed','no_booking','cancel_failed')) AS friction,
          COUNT(*) FILTER (WHERE status='info') AS info_requests,
          COUNT(*) FILTER (WHERE status='cancelled') AS cancellations,
          COUNT(*) FILTER (WHERE status IN ('need_more','reschedule_wait')) AS unfinished
        FROM call_logs
        WHERE tenant_id=:tenant_id AND created_at >= :since_ts
        """,
        {"tenant_id": tid, "since_ts": since_ts},
    )
    totals = totals_rows[0] if totals_rows else [0, 0, 0, 0, 0, 0]

    top_services_rows = _query_rows(
        engine,
        """
        SELECT COALESCE(NULLIF(TRIM(service), ''), 'unknown') AS service, COUNT(*) AS total
        FROM call_logs
        WHERE tenant_id=:tenant_id AND created_at >= :since_ts AND status='booked'
        GROUP BY COALESCE(NULLIF(TRIM(service), ''), 'unknown')
        ORDER BY total DESC, service ASC
        LIMIT 5
        """,
        {"tenant_id": tid, "since_ts": since_ts},
    )

    channel_rows = _query_rows(
        engine,
        """
        SELECT COALESCE(NULLIF(TRIM(channel), ''), 'unknown') AS channel, COUNT(*) AS total
        FROM call_logs
        WHERE tenant_id=:tenant_id AND created_at >= :since_ts
        GROUP BY COALESCE(NULLIF(TRIM(channel), ''), 'unknown')
        ORDER BY total DESC, channel ASC
        LIMIT 8
        """,
        {"tenant_id": tid, "since_ts": since_ts},
    )

    intent_rows = _query_rows(
        engine,
        """
        SELECT COALESCE(NULLIF(TRIM(intent), ''), 'unknown') AS intent, COUNT(*) AS total
        FROM call_logs
        WHERE tenant_id=:tenant_id AND created_at >= :since_ts
        GROUP BY COALESCE(NULLIF(TRIM(intent), ''), 'unknown')
        ORDER BY total DESC, intent ASC
        LIMIT 8
        """,
        {"tenant_id": tid, "since_ts": since_ts},
    )

    raw_text_rows = _query_rows(
        engine,
        """
        SELECT raw_text, COUNT(*) AS total
        FROM call_logs
        WHERE tenant_id=:tenant_id
          AND created_at >= :since_ts
          AND raw_text IS NOT NULL
          AND LENGTH(TRIM(raw_text)) > 2
          AND status IN ('info','need_more','busy','recovery','no_booking')
        GROUP BY raw_text
        ORDER BY total DESC, raw_text ASC
        LIMIT 10
        """,
        {"tenant_id": tid, "since_ts": since_ts},
    )

    total_dialogs = _safe_int(totals[0])
    bookings = _safe_int(totals[1])
    friction = _safe_int(totals[2])
    info_requests = _safe_int(totals[3])
    cancellations = _safe_int(totals[4])
    unfinished = _safe_int(totals[5])
    booking_rate = round(bookings / total_dialogs, 3) if total_dialogs else 0.0
    friction_rate = round(friction / total_dialogs, 3) if total_dialogs else 0.0

    signals: List[Dict[str, Any]] = []
    if total_dialogs == 0:
        signals.append({"type": "low_data", "severity": "info", "title": "Not enough data yet", "value": 0})
    if total_dialogs >= 5 and booking_rate < 0.25:
        signals.append({"type": "low_booking_conversion", "severity": "medium", "title": "Low booking conversion", "value": booking_rate})
    if friction >= 3 or friction_rate >= 0.25:
        signals.append({"type": "missed_demand", "severity": "high", "title": "Potential missed demand", "value": friction})
    if info_requests >= max(3, total_dialogs * 0.3):
        signals.append({"type": "faq_pressure", "severity": "medium", "title": "Clients ask repeated info questions", "value": info_requests})
    if unfinished >= max(3, total_dialogs * 0.3):
        signals.append({"type": "conversation_friction", "severity": "medium", "title": "Many conversations need follow-up", "value": unfinished})

    return {
        "tenant_id": tid,
        "window_days": days,
        "summary": {
            "total_dialogs": total_dialogs,
            "bookings": bookings,
            "booking_rate": booking_rate,
            "friction_events": friction,
            "friction_rate": friction_rate,
            "info_requests": info_requests,
            "cancellations": cancellations,
            "unfinished": unfinished,
        },
        "top_services": [{"service": str(r[0]), "count": _safe_int(r[1])} for r in top_services_rows],
        "channels": [{"channel": str(r[0]), "count": _safe_int(r[1])} for r in channel_rows],
        "intents": [{"intent": str(r[0]), "count": _safe_int(r[1])} for r in intent_rows],
        "repeated_questions_or_friction": [{"text": str(r[0]), "count": _safe_int(r[1])} for r in raw_text_rows],
        "signals": signals,
    }
