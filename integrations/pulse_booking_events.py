"""Durable Receptionist -> Pulse booking-event publisher (R19).

The module deliberately keeps Pulse delivery outside the authoritative booking flow.
Booking code stores an immutable versioned envelope in a database outbox in the same local
transaction that persists the final conversation state. A worker later signs and sends
that exact body. Transient failures are retried with bounded exponential backoff; the
same event ID and body are reused for every attempt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

import requests
from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection

log = logging.getLogger("repliq.pulse_outbox")

LEGACY_R11_SCHEMA_VERSION = "2026-07-14"
R19_SCHEMA_VERSION = "2026-07-22"
# Backward-compatible import name used by the existing publisher/tests. New events use R19.
R11_SCHEMA_VERSION = R19_SCHEMA_VERSION
R11_EVENT_TYPES = frozenset(
    {"booking.created", "booking.rescheduled", "booking.cancelled"}
)

OUTBOX_PENDING = "pending"
OUTBOX_SENDING = "sending"
OUTBOX_RETRY = "retry"
OUTBOX_DELIVERED = "delivered"
OUTBOX_FAILED = "failed"

_TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


class PulsePublisherConfigurationError(ValueError):
    """Raised when the publisher is enabled with unsafe or incomplete settings."""


@dataclass(frozen=True, slots=True, repr=False)
class PulsePublisherConfig:
    enabled: bool
    webhook_url: str
    signing_secret: str
    request_timeout_seconds: float = 5.0
    max_attempts: int = 8
    retry_base_seconds: int = 30
    retry_max_seconds: int = 3600
    poll_seconds: float = 5.0
    batch_size: int = 20
    lease_seconds: int = 60
    worker_enabled: bool = True
    allow_insecure_http: bool = False

    def __repr__(self) -> str:  # do not expose the shared secret in logs/debug output
        return (
            "PulsePublisherConfig("
            f"enabled={self.enabled!r}, webhook_url={self.webhook_url!r}, "
            "signing_secret=<redacted>, "
            f"request_timeout_seconds={self.request_timeout_seconds!r}, "
            f"max_attempts={self.max_attempts!r}, "
            f"retry_base_seconds={self.retry_base_seconds!r}, "
            f"retry_max_seconds={self.retry_max_seconds!r}, "
            f"poll_seconds={self.poll_seconds!r}, batch_size={self.batch_size!r}, "
            f"lease_seconds={self.lease_seconds!r}, worker_enabled={self.worker_enabled!r})"
        )

    def validate(self) -> None:
        if not self.enabled:
            return
        parsed = urlparse((self.webhook_url or "").strip())
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise PulsePublisherConfigurationError(
                "PULSE_RECEPTIONIST_WEBHOOK_URL must be an absolute HTTP(S) URL"
            )
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise PulsePublisherConfigurationError(
                "PULSE_RECEPTIONIST_WEBHOOK_URL must not contain credentials, query parameters, or fragments"
            )
        local_http = parsed.scheme == "http" and parsed.hostname in {
            "localhost",
            "127.0.0.1",
            "::1",
            "testserver",
        }
        if parsed.scheme != "https" and not (self.allow_insecure_http or local_http):
            raise PulsePublisherConfigurationError(
                "PULSE_RECEPTIONIST_WEBHOOK_URL must use HTTPS in production"
            )
        if len((self.signing_secret or "").encode("utf-8")) < 32:
            raise PulsePublisherConfigurationError(
                "PULSE_RECEPTIONIST_WEBHOOK_SIGNING_SECRET must contain at least 32 bytes"
            )
        if not (0.5 <= float(self.request_timeout_seconds) <= 60.0):
            raise PulsePublisherConfigurationError(
                "PULSE_RECEPTIONIST_REQUEST_TIMEOUT_SECONDS must be between 0.5 and 60"
            )
        if not (1 <= int(self.max_attempts) <= 25):
            raise PulsePublisherConfigurationError(
                "PULSE_RECEPTIONIST_MAX_ATTEMPTS must be between 1 and 25"
            )
        if not (1 <= int(self.retry_base_seconds) <= 86400):
            raise PulsePublisherConfigurationError(
                "PULSE_RECEPTIONIST_RETRY_BASE_SECONDS must be between 1 and 86400"
            )
        if not (
            int(self.retry_base_seconds)
            <= int(self.retry_max_seconds)
            <= 7 * 86400
        ):
            raise PulsePublisherConfigurationError(
                "PULSE_RECEPTIONIST_RETRY_MAX_SECONDS must be >= base and <= 604800"
            )
        if not (0.5 <= float(self.poll_seconds) <= 300.0):
            raise PulsePublisherConfigurationError(
                "PULSE_RECEPTIONIST_POLL_SECONDS must be between 0.5 and 300"
            )
        if not (1 <= int(self.batch_size) <= 200):
            raise PulsePublisherConfigurationError(
                "PULSE_RECEPTIONIST_BATCH_SIZE must be between 1 and 200"
            )
        if not (10 <= int(self.lease_seconds) <= 3600):
            raise PulsePublisherConfigurationError(
                "PULSE_RECEPTIONIST_LEASE_SECONDS must be between 10 and 3600"
            )


@dataclass(frozen=True, slots=True)
class PendingBookingEvent:
    event_type: str
    tenant_id: str
    booking_ref: str
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    duration_minutes: Optional[int]
    service_ref: Optional[str]
    location_ref: Optional[str]
    occurred_at: datetime

    def validate(self) -> None:
        if self.event_type not in R11_EVENT_TYPES:
            raise ValueError(f"unsupported R11 event type: {self.event_type}")
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.booking_ref or "").strip():
            raise ValueError("booking_ref is required")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.event_type in {"booking.created", "booking.rescheduled"}:
            if not str(self.location_ref or "").strip():
                raise ValueError("location_ref is required for created/rescheduled events")
            if self.starts_at is None:
                raise ValueError("starts_at is required for created/rescheduled events")
            if self.ends_at is None:
                raise ValueError("ends_at is required for created/rescheduled events")
            if self.duration_minutes is None:
                raise ValueError("duration_minutes is required for created/rescheduled events")
        if self.starts_at is not None:
            if self.starts_at.tzinfo is None or self.starts_at.utcoffset() is None:
                raise ValueError("starts_at must be timezone-aware")
        if self.ends_at is not None:
            if self.ends_at.tzinfo is None or self.ends_at.utcoffset() is None:
                raise ValueError("ends_at must be timezone-aware")
        if self.duration_minutes is not None:
            if not (1 <= int(self.duration_minutes) <= 1440):
                raise ValueError("duration_minutes must be between 1 and 1440")
        if self.starts_at is not None and self.ends_at is not None:
            if self.ends_at <= self.starts_at:
                raise ValueError("ends_at must be after starts_at")
            if self.duration_minutes is not None:
                actual_seconds = int((self.ends_at - self.starts_at).total_seconds())
                if actual_seconds != int(self.duration_minutes) * 60:
                    raise ValueError("duration_minutes must match starts_at/ends_at")


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    event_id: str
    status: str
    attempt_count: int
    http_status: Optional[int]
    error_category: Optional[str]


def utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _canonical_body(payload: Dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sign_r11_body(secret: str, timestamp: int, body: bytes) -> str:
    message = str(int(timestamp)).encode("ascii") + b"." + body
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"v1={digest}"


def ensure_pulse_outbox_tables(engine: Engine) -> None:
    """Create R16 tables using the repository's existing idempotent runtime-DDL style."""

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS pulse_booking_versions (
                    tenant_id TEXT NOT NULL,
                    booking_ref TEXT NOT NULL,
                    aggregate_version INTEGER NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tenant_id, booking_ref)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS pulse_booking_event_outbox (
                    event_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    booking_ref TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    aggregate_version INTEGER NOT NULL,
                    schema_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL,
                    next_attempt_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    lease_token TEXT,
                    lease_expires_at TIMESTAMP WITH TIME ZONE,
                    last_attempt_at TIMESTAMP WITH TIME ZONE,
                    last_http_status INTEGER,
                    last_error_category TEXT,
                    acknowledgement_json TEXT,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    sent_at TIMESTAMP WITH TIME ZONE,
                    confirmed_at TIMESTAMP WITH TIME ZONE,
                    failed_at TIMESTAMP WITH TIME ZONE,
                    UNIQUE (tenant_id, booking_ref, aggregate_version)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_pulse_booking_event_outbox_due
                ON pulse_booking_event_outbox (status, next_attempt_at, created_at)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_pulse_booking_event_outbox_booking
                ON pulse_booking_event_outbox (tenant_id, booking_ref, aggregate_version)
                """
            )
        )


def drop_pulse_outbox_tables(engine: Engine) -> None:
    """Rollback helper for the repository's runtime-DDL schema convention.

    The outbox is dropped before its aggregate-version table. Booking and
    conversation data are not touched. Operators must disable the publisher and
    drain/export pending events before invoking this helper.
    """

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS pulse_booking_event_outbox"))
        conn.execute(text("DROP TABLE IF EXISTS pulse_booking_versions"))


def _next_aggregate_version(
    conn: Connection, *, tenant_id: str, booking_ref: str
) -> int:
    result = conn.execute(
        text(
            """
            INSERT INTO pulse_booking_versions
                (tenant_id, booking_ref, aggregate_version, updated_at)
            VALUES
                (:tenant_id, :booking_ref, 1, CURRENT_TIMESTAMP)
            ON CONFLICT (tenant_id, booking_ref)
            DO UPDATE SET
                aggregate_version = pulse_booking_versions.aggregate_version + 1,
                updated_at = CURRENT_TIMESTAMP
            RETURNING aggregate_version
            """
        ),
        {"tenant_id": tenant_id, "booking_ref": booking_ref},
    ).scalar_one()
    return int(result)


def enqueue_booking_event(
    conn: Connection,
    event: PendingBookingEvent,
    *,
    max_attempts: int,
) -> Optional[str]:
    """Persist one immutable R19 event using an existing DB transaction.

    Returns the event ID. The caller intentionally skips creation when the integration
    is disabled; when enabled, configuration is validated before this function is used.
    """

    event.validate()
    tenant_id = str(event.tenant_id).strip()
    booking_ref = str(event.booking_ref).strip()
    event_type = str(event.event_type).strip()
    aggregate_version = _next_aggregate_version(
        conn, tenant_id=tenant_id, booking_ref=booking_ref
    )
    identity_material = (
        f"{R11_SCHEMA_VERSION}|{tenant_id}|{booking_ref}|"
        f"{aggregate_version}|{event_type}"
    ).encode("utf-8")
    event_id = "repliq_" + hashlib.sha256(identity_material).hexdigest()[:48]

    booking_payload: Dict[str, Any] = {
        "booking_ref": booking_ref,
        "location_ref": str(event.location_ref).strip() if event.location_ref else None,
        "starts_at": _iso(event.starts_at),
        "ends_at": _iso(event.ends_at),
        "duration_minutes": int(event.duration_minutes) if event.duration_minutes is not None else None,
        "service_ref": str(event.service_ref).strip() if event.service_ref else None,
    }
    payload = {
        "schema_version": R11_SCHEMA_VERSION,
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": _iso(event.occurred_at),
        "tenant_ref": tenant_id,
        "aggregate_version": aggregate_version,
        "booking": booking_payload,
    }
    body = _canonical_body(payload)
    digest = hashlib.sha256(body).hexdigest()
    conn.execute(
        text(
            """
            INSERT INTO pulse_booking_event_outbox (
                event_id, tenant_id, booking_ref, event_type, aggregate_version,
                schema_version, payload_json, payload_sha256, status,
                attempt_count, max_attempts, next_attempt_at, created_at
            ) VALUES (
                :event_id, :tenant_id, :booking_ref, :event_type, :aggregate_version,
                :schema_version, :payload_json, :payload_sha256, :status,
                0, :max_attempts, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "event_id": event_id,
            "tenant_id": tenant_id,
            "booking_ref": booking_ref,
            "event_type": event_type,
            "aggregate_version": aggregate_version,
            "schema_version": R11_SCHEMA_VERSION,
            "payload_json": body.decode("utf-8"),
            "payload_sha256": digest,
            "status": OUTBOX_PENDING,
            "max_attempts": int(max_attempts),
        },
    )
    return event_id


def _row_mapping(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return dict(row)


class PulseBookingOutbox:
    def __init__(
        self,
        engine: Engine,
        config: PulsePublisherConfig,
        *,
        http_post: Optional[Callable[..., Any]] = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.engine = engine
        self.config = config
        self.config.validate()
        self._http_post = http_post or requests.post
        self._clock = clock

    def _claim_due(self, limit: Optional[int] = None) -> list[Dict[str, Any]]:
        batch = max(1, min(int(limit or self.config.batch_size), self.config.batch_size))
        now = self._clock().astimezone(UTC)
        lease_until = now + timedelta(seconds=self.config.lease_seconds)
        token = uuid.uuid4().hex
        dialect = self.engine.dialect.name
        with self.engine.begin() as conn:
            if dialect == "postgresql":
                rows = conn.execute(
                    text(
                        """
                        WITH due AS (
                            SELECT candidate.event_id
                            FROM pulse_booking_event_outbox AS candidate
                            WHERE (
                                (
                                    candidate.status IN ('pending', 'retry')
                                    AND candidate.next_attempt_at <= :now
                                ) OR (
                                    candidate.status = 'sending'
                                    AND candidate.lease_expires_at IS NOT NULL
                                    AND candidate.lease_expires_at <= :now
                                )
                            )
                            AND NOT EXISTS (
                                SELECT 1
                                FROM pulse_booking_event_outbox AS earlier
                                WHERE earlier.tenant_id = candidate.tenant_id
                                  AND earlier.booking_ref = candidate.booking_ref
                                  AND earlier.aggregate_version < candidate.aggregate_version
                                  AND earlier.status <> 'delivered'
                            )
                            ORDER BY candidate.created_at, candidate.event_id
                            FOR UPDATE SKIP LOCKED
                            LIMIT :limit
                        )
                        UPDATE pulse_booking_event_outbox AS outbox
                        SET status='sending',
                            attempt_count=outbox.attempt_count + 1,
                            last_attempt_at=:now,
                            lease_token=:token,
                            lease_expires_at=:lease_until
                        FROM due
                        WHERE outbox.event_id = due.event_id
                        RETURNING outbox.*
                        """
                    ),
                    {
                        "now": now,
                        "lease_until": lease_until,
                        "token": token,
                        "limit": batch,
                    },
                ).fetchall()
                return [_row_mapping(row) for row in rows]

            candidates = conn.execute(
                text(
                    """
                    SELECT candidate.event_id
                    FROM pulse_booking_event_outbox AS candidate
                    WHERE (
                        (
                            candidate.status IN ('pending', 'retry')
                            AND candidate.next_attempt_at <= :now
                        ) OR (
                            candidate.status = 'sending'
                            AND candidate.lease_expires_at IS NOT NULL
                            AND candidate.lease_expires_at <= :now
                        )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM pulse_booking_event_outbox AS earlier
                        WHERE earlier.tenant_id = candidate.tenant_id
                          AND earlier.booking_ref = candidate.booking_ref
                          AND earlier.aggregate_version < candidate.aggregate_version
                          AND earlier.status <> 'delivered'
                    )
                    ORDER BY candidate.created_at, candidate.event_id
                    LIMIT :limit
                    """
                ),
                {"now": now, "limit": batch},
            ).fetchall()
            claimed: list[Dict[str, Any]] = []
            for candidate in candidates:
                event_id = candidate[0]
                updated = conn.execute(
                    text(
                        """
                        UPDATE pulse_booking_event_outbox
                        SET status='sending',
                            attempt_count=attempt_count + 1,
                            last_attempt_at=:now,
                            lease_token=:token,
                            lease_expires_at=:lease_until
                        WHERE event_id=:event_id
                          AND ((status IN ('pending', 'retry') AND next_attempt_at <= :now)
                            OR (status='sending' AND lease_expires_at <= :now))
                        """
                    ),
                    {
                        "event_id": event_id,
                        "now": now,
                        "token": token,
                        "lease_until": lease_until,
                    },
                )
                if updated.rowcount:
                    row = conn.execute(
                        text(
                            "SELECT * FROM pulse_booking_event_outbox WHERE event_id=:event_id"
                        ),
                        {"event_id": event_id},
                    ).fetchone()
                    claimed.append(_row_mapping(row))
            return claimed

    def _mark_delivered(
        self, row: Dict[str, Any], *, http_status: int, acknowledgement: Dict[str, Any]
    ) -> DeliveryResult:
        now = self._clock().astimezone(UTC)
        safe_ack = {
            key: acknowledgement.get(key)
            for key in (
                "accepted",
                "duplicate",
                "action",
                "inbox_status",
                "reason_code",
                "booking_public_id",
                "preparation_plan_public_id",
                "preparation_status",
            )
            if key in acknowledgement
        }
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE pulse_booking_event_outbox
                    SET status='delivered',
                        last_http_status=:http_status,
                        last_error_category=NULL,
                        acknowledgement_json=:ack,
                        sent_at=COALESCE(sent_at, :now),
                        confirmed_at=:now,
                        lease_token=NULL,
                        lease_expires_at=NULL
                    WHERE event_id=:event_id AND lease_token=:lease_token
                    """
                ),
                {
                    "http_status": int(http_status),
                    "ack": json.dumps(safe_ack, ensure_ascii=False, separators=(",", ":")),
                    "now": now,
                    "event_id": row["event_id"],
                    "lease_token": row.get("lease_token"),
                },
            )
        return DeliveryResult(
            event_id=str(row["event_id"]),
            status=OUTBOX_DELIVERED,
            attempt_count=int(row["attempt_count"]),
            http_status=int(http_status),
            error_category=None,
        )

    def _mark_failure(
        self,
        row: Dict[str, Any],
        *,
        category: str,
        http_status: Optional[int],
        transient: bool,
    ) -> DeliveryResult:
        now = self._clock().astimezone(UTC)
        attempts = int(row["attempt_count"])
        max_attempts = int(row["max_attempts"])
        retrying = bool(transient and attempts < max_attempts)
        status = OUTBOX_RETRY if retrying else OUTBOX_FAILED
        delay = min(
            int(self.config.retry_max_seconds),
            int(self.config.retry_base_seconds) * (2 ** max(0, attempts - 1)),
        )
        next_attempt = now + timedelta(seconds=delay)
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE pulse_booking_event_outbox
                    SET status=:status,
                        next_attempt_at=:next_attempt_at,
                        last_http_status=:http_status,
                        last_error_category=:category,
                        failed_at=:failed_at,
                        lease_token=NULL,
                        lease_expires_at=NULL
                    WHERE event_id=:event_id AND lease_token=:lease_token
                    """
                ),
                {
                    "status": status,
                    "next_attempt_at": next_attempt,
                    "http_status": http_status,
                    "category": category[:80],
                    "failed_at": None if retrying else now,
                    "event_id": row["event_id"],
                    "lease_token": row.get("lease_token"),
                },
            )
        return DeliveryResult(
            event_id=str(row["event_id"]),
            status=status,
            attempt_count=attempts,
            http_status=http_status,
            error_category=category,
        )

    def _deliver_claimed(self, row: Dict[str, Any]) -> DeliveryResult:
        body = str(row["payload_json"]).encode("utf-8")
        digest = hashlib.sha256(body).hexdigest()
        if not hmac.compare_digest(digest, str(row["payload_sha256"])):
            return self._mark_failure(
                row,
                category="local_payload_integrity_error",
                http_status=None,
                transient=False,
            )
        timestamp = int(self._clock().astimezone(UTC).timestamp())
        headers = {
            "Content-Type": "application/json",
            "X-Repliq-Timestamp": str(timestamp),
            "X-Repliq-Signature": sign_r11_body(
                self.config.signing_secret, timestamp, body
            ),
        }
        try:
            response = self._http_post(
                self.config.webhook_url,
                data=body,
                headers=headers,
                timeout=float(self.config.request_timeout_seconds),
            )
        except requests.Timeout:
            return self._mark_failure(
                row, category="network_timeout", http_status=None, transient=True
            )
        except requests.RequestException:
            return self._mark_failure(
                row, category="network_error", http_status=None, transient=True
            )
        except Exception:
            # Custom transports used by operators/tests must not leak exception text.
            return self._mark_failure(
                row, category="transport_error", http_status=None, transient=True
            )

        status_code = int(getattr(response, "status_code", 0) or 0)
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}

        if 200 <= status_code < 300 and payload.get("accepted") is True:
            return self._mark_delivered(
                row, http_status=status_code, acknowledgement=payload
            )
        if status_code in _TRANSIENT_HTTP_STATUSES or status_code >= 500:
            return self._mark_failure(
                row,
                category=f"pulse_http_{status_code or 'unknown'}",
                http_status=status_code or None,
                transient=True,
            )
        if 200 <= status_code < 300:
            category = "pulse_rejected_event"
        elif status_code in {401, 403}:
            category = "pulse_authentication_rejected"
        elif status_code == 409:
            category = "pulse_event_conflict"
        elif status_code == 422:
            category = "pulse_contract_rejected"
        else:
            category = f"pulse_http_{status_code or 'unknown'}"
        return self._mark_failure(
            row,
            category=category,
            http_status=status_code or None,
            transient=False,
        )

    def dispatch_due(self, *, limit: Optional[int] = None) -> tuple[DeliveryResult, ...]:
        if not self.config.enabled:
            return ()
        results: list[DeliveryResult] = []
        for row in self._claim_due(limit=limit):
            result = self._deliver_claimed(row)
            results.append(result)
            log.info(
                "pulse_booking_event_delivery event_id=%s event_type=%s tenant_ref=%s "
                "booking_ref=%s attempt=%s status=%s error_category=%s",
                row.get("event_id"),
                row.get("event_type"),
                row.get("tenant_id"),
                row.get("booking_ref"),
                row.get("attempt_count"),
                result.status,
                result.error_category,
            )
        return tuple(results)

    def retry_failed(self, *, event_id: Optional[str] = None) -> int:
        params: Dict[str, Any] = {"now": self._clock().astimezone(UTC)}
        where = "status='failed'"
        if event_id:
            where += " AND event_id=:event_id"
            params["event_id"] = str(event_id).strip()
        with self.engine.begin() as conn:
            result = conn.execute(
                text(
                    f"""
                    UPDATE pulse_booking_event_outbox
                    SET status='retry', next_attempt_at=:now, failed_at=NULL,
                        lease_token=NULL, lease_expires_at=NULL
                    WHERE {where}
                    """
                ),
                params,
            )
            return int(result.rowcount or 0)

    def status_summary(self) -> Dict[str, Any]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM pulse_booking_event_outbox
                    GROUP BY status
                    ORDER BY status
                    """
                )
            ).fetchall()
            oldest = conn.execute(
                text(
                    """
                    SELECT event_id, event_type, tenant_id, booking_ref,
                           attempt_count, status, last_error_category, created_at,
                           next_attempt_at, confirmed_at
                    FROM pulse_booking_event_outbox
                    WHERE status <> 'delivered'
                    ORDER BY created_at, event_id
                    LIMIT 20
                    """
                )
            ).fetchall()
        return {
            "enabled": bool(self.config.enabled),
            "worker_enabled": bool(self.config.worker_enabled),
            "counts": {str(row[0]): int(row[1]) for row in rows},
            "pending_events": [
                {
                    "event_id": row[0],
                    "event_type": row[1],
                    "tenant_ref": row[2],
                    "booking_ref": row[3],
                    "attempt_count": int(row[4] or 0),
                    "status": row[5],
                    "last_error_category": row[6],
                    "created_at": str(row[7]) if row[7] is not None else None,
                    "next_attempt_at": str(row[8]) if row[8] is not None else None,
                    "confirmed_at": str(row[9]) if row[9] is not None else None,
                }
                for row in oldest
            ],
            "webhook_url_configured": bool(self.config.webhook_url),
            "signing_secret_configured": bool(self.config.signing_secret),
            "signing_secret_exposed": False,
        }


def publisher_config_from_settings() -> PulsePublisherConfig:
    from config import settings

    return PulsePublisherConfig(
        enabled=bool(settings.PULSE_RECEPTIONIST_PUBLISHER_ENABLED),
        webhook_url=str(settings.PULSE_RECEPTIONIST_WEBHOOK_URL or "").strip(),
        signing_secret=str(
            settings.PULSE_RECEPTIONIST_WEBHOOK_SIGNING_SECRET or ""
        ),
        request_timeout_seconds=float(
            settings.PULSE_RECEPTIONIST_REQUEST_TIMEOUT_SECONDS
        ),
        max_attempts=int(settings.PULSE_RECEPTIONIST_MAX_ATTEMPTS),
        retry_base_seconds=int(settings.PULSE_RECEPTIONIST_RETRY_BASE_SECONDS),
        retry_max_seconds=int(settings.PULSE_RECEPTIONIST_RETRY_MAX_SECONDS),
        poll_seconds=float(settings.PULSE_RECEPTIONIST_POLL_SECONDS),
        batch_size=int(settings.PULSE_RECEPTIONIST_BATCH_SIZE),
        lease_seconds=int(settings.PULSE_RECEPTIONIST_LEASE_SECONDS),
        worker_enabled=bool(settings.PULSE_RECEPTIONIST_WORKER_ENABLED),
        allow_insecure_http=bool(
            settings.PULSE_RECEPTIONIST_ALLOW_INSECURE_HTTP
        ),
    )


class PulseOutboxWorker:
    def __init__(self, outbox: PulseBookingOutbox) -> None:
        self.outbox = outbox
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not (self.outbox.config.enabled and self.outbox.config.worker_enabled):
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="repliq-pulse-outbox",
            daemon=True,
        )
        self._thread.start()
        log.info("pulse_booking_event_worker_started")

    def wake(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        log.info("pulse_booking_event_worker_stopped")

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.outbox.dispatch_due()
            except Exception as exc:  # safe category only; no request headers or secrets
                log.error(
                    "pulse_booking_event_worker_cycle_failed error_type=%s",
                    exc.__class__.__name__,
                )
            self._wake.wait(timeout=float(self.outbox.config.poll_seconds))
            self._wake.clear()


_default_worker: Optional[PulseOutboxWorker] = None


def install_default_worker(outbox: PulseBookingOutbox) -> PulseOutboxWorker:
    global _default_worker
    if _default_worker is None:
        _default_worker = PulseOutboxWorker(outbox)
    return _default_worker


def wake_default_worker() -> None:
    if _default_worker is not None:
        _default_worker.wake()


def stop_default_worker() -> None:
    if _default_worker is not None:
        _default_worker.stop()
