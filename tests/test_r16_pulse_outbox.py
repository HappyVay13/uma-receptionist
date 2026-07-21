from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
import requests
from sqlalchemy import create_engine, inspect, text

from integrations.pulse_booking_events import (
    OUTBOX_DELIVERED,
    OUTBOX_FAILED,
    OUTBOX_RETRY,
    PendingBookingEvent,
    PulseBookingOutbox,
    PulsePublisherConfig,
    PulsePublisherConfigurationError,
    R11_SCHEMA_VERSION,
    drop_pulse_outbox_tables,
    enqueue_booking_event,
    ensure_pulse_outbox_tables,
)

SECRET = "r16-shared-signing-secret-with-at-least-32-bytes"
START = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)


@dataclass
class MutableClock:
    value: datetime = START

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return dict(self._payload)


@pytest.fixture
def engine(tmp_path):
    value = create_engine(f"sqlite+pysqlite:///{tmp_path / 'r16.db'}")
    ensure_pulse_outbox_tables(value)
    try:
        yield value
    finally:
        value.dispose()


def config(**overrides) -> PulsePublisherConfig:
    values = {
        "enabled": True,
        "webhook_url": "http://testserver/integrations/receptionist/v1/events",
        "signing_secret": SECRET,
        "request_timeout_seconds": 1.0,
        "max_attempts": 3,
        "retry_base_seconds": 1,
        "retry_max_seconds": 8,
        "poll_seconds": 1.0,
        "batch_size": 20,
        "lease_seconds": 10,
        "worker_enabled": False,
    }
    values.update(overrides)
    return PulsePublisherConfig(**values)


def event(
    *,
    event_type: str = "booking.created",
    tenant_id: str = "clinic_demo",
    booking_ref: str = "google-event-100",
    starts_at: datetime | None = datetime(2026, 7, 19, 9, 0, tzinfo=UTC),
) -> PendingBookingEvent:
    return PendingBookingEvent(
        event_type=event_type,
        tenant_id=tenant_id,
        booking_ref=booking_ref,
        starts_at=starts_at,
        service_ref="consultation",
        location_ref=tenant_id if event_type != "booking.cancelled" else None,
        occurred_at=START,
    )


def enqueue(engine, value: PendingBookingEvent | None = None, max_attempts: int = 3) -> str:
    with engine.begin() as conn:
        return str(
            enqueue_booking_event(
                conn,
                value or event(),
                max_attempts=max_attempts,
            )
        )


def row(engine, event_id: str) -> dict:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM pulse_booking_event_outbox WHERE event_id=:event_id"),
            {"event_id": event_id},
        ).mappings().one()
        return dict(result)


def make_due(engine, event_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE pulse_booking_event_outbox "
                "SET next_attempt_at='2000-01-01 00:00:00+00:00' "
                "WHERE event_id=:event_id"
            ),
            {"event_id": event_id},
        )


def test_configuration_requires_safe_url_and_redacts_secret() -> None:
    unsafe = config(webhook_url="http://pulse.example.com/webhook")
    with pytest.raises(PulsePublisherConfigurationError):
        unsafe.validate()
    embedded_credential = config(
        webhook_url="https://token:persistent-secret@pulse.example.com/webhook"
    )
    with pytest.raises(PulsePublisherConfigurationError):
        embedded_credential.validate()
    query_secret = config(webhook_url="https://pulse.example.com/webhook?token=secret")
    with pytest.raises(PulsePublisherConfigurationError):
        query_secret.validate()
    too_short = config(signing_secret="short")
    with pytest.raises(PulsePublisherConfigurationError):
        too_short.validate()
    rendered = repr(config())
    assert SECRET not in rendered
    assert "<redacted>" in rendered


def test_runtime_schema_upgrade_downgrade_reupgrade_preserves_other_data(tmp_path) -> None:
    database = create_engine(f"sqlite+pysqlite:///{tmp_path / 'schema.db'}")
    with database.begin() as conn:
        conn.execute(text("CREATE TABLE conversations (id INTEGER PRIMARY KEY, state TEXT)"))
        conn.execute(text("INSERT INTO conversations (id, state) VALUES (1, 'BOOKED')"))
    ensure_pulse_outbox_tables(database)
    ensure_pulse_outbox_tables(database)
    assert {"pulse_booking_versions", "pulse_booking_event_outbox"}.issubset(
        set(inspect(database).get_table_names())
    )
    drop_pulse_outbox_tables(database)
    assert "pulse_booking_event_outbox" not in inspect(database).get_table_names()
    with database.connect() as conn:
        assert conn.execute(text("SELECT state FROM conversations WHERE id=1")).scalar_one() == "BOOKED"
    ensure_pulse_outbox_tables(database)
    assert "pulse_booking_event_outbox" in inspect(database).get_table_names()
    database.dispose()


def test_exact_r11_payload_versions_and_tenant_isolation(engine) -> None:
    first = enqueue(engine)
    second = enqueue(engine, event(event_type="booking.rescheduled"))
    other_tenant = enqueue(
        engine,
        event(tenant_id="tenant_b", booking_ref="google-event-100"),
    )

    first_row = row(engine, first)
    second_row = row(engine, second)
    other_row = row(engine, other_tenant)
    payload = json.loads(first_row["payload_json"])

    assert set(payload) == {
        "schema_version",
        "event_id",
        "event_type",
        "occurred_at",
        "tenant_ref",
        "aggregate_version",
        "booking",
    }
    assert payload["schema_version"] == R11_SCHEMA_VERSION == "2026-07-14"
    assert payload["event_id"] == first
    assert payload["event_type"] == "booking.created"
    assert payload["tenant_ref"] == "clinic_demo"
    assert payload["aggregate_version"] == 1
    assert payload["booking"] == {
        "booking_ref": "google-event-100",
        "location_ref": "clinic_demo",
        "service_ref": "consultation",
        "starts_at": "2026-07-19T09:00:00Z",
    }
    assert second_row["aggregate_version"] == 2
    assert other_row["aggregate_version"] == 1
    assert len({first, second, other_tenant}) == 3


def test_cancel_contract_allows_optional_location_and_start(engine) -> None:
    event_id = enqueue(
        engine,
        event(event_type="booking.cancelled", starts_at=None),
    )
    payload = json.loads(row(engine, event_id)["payload_json"])
    assert payload["event_type"] == "booking.cancelled"
    assert payload["booking"]["location_ref"] is None
    assert payload["booking"]["starts_at"] is None


def test_event_and_version_roll_back_together(engine) -> None:
    with pytest.raises(RuntimeError):
        with engine.begin() as conn:
            enqueue_booking_event(conn, event(), max_attempts=3)
            raise RuntimeError("force rollback")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM pulse_booking_event_outbox")).scalar_one() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM pulse_booking_versions")).scalar_one() == 0
    assert enqueue(engine).startswith("repliq_")
    assert row(engine, enqueue(engine, event(event_type="booking.rescheduled")))["aggregate_version"] == 2


def test_valid_delivery_uses_exact_body_and_r11_signature(engine) -> None:
    event_id = enqueue(engine)
    captured: list[dict] = []

    def post(url, *, data, headers, timeout):
        captured.append({"url": url, "data": data, "headers": headers, "timeout": timeout})
        return FakeResponse(200, {"accepted": True, "duplicate": False, "action": "preparation_scheduled"})

    clock = MutableClock()
    outbox = PulseBookingOutbox(engine, config(), http_post=post, clock=clock)
    result = outbox.dispatch_due()

    assert len(result) == 1
    assert result[0].event_id == event_id
    assert result[0].status == OUTBOX_DELIVERED
    assert captured[0]["data"] == row(engine, event_id)["payload_json"].encode("utf-8")
    timestamp = captured[0]["headers"]["X-Repliq-Timestamp"]
    expected = hmac.new(
        SECRET.encode(),
        timestamp.encode("ascii") + b"." + captured[0]["data"],
        hashlib.sha256,
    ).hexdigest()
    assert captured[0]["headers"]["X-Repliq-Signature"] == f"v1={expected}"
    assert row(engine, event_id)["status"] == OUTBOX_DELIVERED


def test_timeout_retry_reuses_event_id_and_immutable_payload(engine) -> None:
    event_id = enqueue(engine)
    calls: list[bytes] = []

    def post(url, *, data, headers, timeout):
        calls.append(data)
        if len(calls) == 1:
            raise requests.Timeout("sensitive endpoint details must not be stored")
        return FakeResponse(200, {"accepted": True, "duplicate": True, "action": "duplicate"})

    clock = MutableClock()
    outbox = PulseBookingOutbox(engine, config(), http_post=post, clock=clock)
    first = outbox.dispatch_due()[0]
    assert first.status == OUTBOX_RETRY
    assert row(engine, event_id)["last_error_category"] == "network_timeout"
    clock.advance(2)
    make_due(engine, event_id)
    second = outbox.dispatch_due()[0]
    assert second.status == OUTBOX_DELIVERED
    assert calls[0] == calls[1]
    assert json.loads(calls[0])["event_id"] == event_id
    assert row(engine, event_id)["attempt_count"] == 2


def test_transient_503_reaches_bounded_failed_state_and_manual_retry(engine) -> None:
    event_id = enqueue(engine, max_attempts=2)
    responses = [
        FakeResponse(503, {"detail": "temporary"}),
        FakeResponse(503, {"detail": "temporary"}),
        FakeResponse(200, {"accepted": True, "duplicate": True}),
    ]
    bodies: list[bytes] = []

    def post(url, *, data, headers, timeout):
        bodies.append(data)
        return responses.pop(0)

    clock = MutableClock()
    outbox = PulseBookingOutbox(engine, config(max_attempts=2), http_post=post, clock=clock)
    assert outbox.dispatch_due()[0].status == OUTBOX_RETRY
    clock.advance(2)
    make_due(engine, event_id)
    assert outbox.dispatch_due()[0].status == OUTBOX_FAILED
    failed = row(engine, event_id)
    assert failed["attempt_count"] == 2
    assert failed["last_http_status"] == 503
    assert outbox.retry_failed(event_id=event_id) == 1
    make_due(engine, event_id)
    assert outbox.dispatch_due()[0].status == OUTBOX_DELIVERED
    assert bodies[0] == bodies[1] == bodies[2]


@pytest.mark.parametrize(
    ("status_code", "category"),
    [
        (401, "pulse_authentication_rejected"),
        (403, "pulse_authentication_rejected"),
        (409, "pulse_event_conflict"),
        (422, "pulse_contract_rejected"),
    ],
)
def test_permanent_contract_and_auth_errors_are_not_retried(engine, status_code, category) -> None:
    event_id = enqueue(engine)
    outbox = PulseBookingOutbox(
        engine,
        config(),
        http_post=lambda *args, **kwargs: FakeResponse(status_code, {"detail": "rejected"}),
        clock=MutableClock(),
    )
    result = outbox.dispatch_due()[0]
    assert result.status == OUTBOX_FAILED
    stored = row(engine, event_id)
    assert stored["last_error_category"] == category
    assert stored["attempt_count"] == 1


def test_accepted_false_is_permanent_wrong_tenant_or_binding_rejection(engine) -> None:
    event_id = enqueue(engine)
    outbox = PulseBookingOutbox(
        engine,
        config(),
        http_post=lambda *args, **kwargs: FakeResponse(
            200,
            {"accepted": False, "reason_code": "unknown_tenant"},
        ),
        clock=MutableClock(),
    )
    assert outbox.dispatch_due()[0].status == OUTBOX_FAILED
    assert row(engine, event_id)["last_error_category"] == "pulse_rejected_event"


def test_restart_recovers_expired_sending_lease(engine) -> None:
    event_id = enqueue(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE pulse_booking_event_outbox SET status='sending', attempt_count=1, "
                "lease_token='old-process', lease_expires_at='2000-01-01 00:00:00+00:00' "
                "WHERE event_id=:event_id"
            ),
            {"event_id": event_id},
        )
    outbox = PulseBookingOutbox(
        engine,
        config(),
        http_post=lambda *args, **kwargs: FakeResponse(200, {"accepted": True, "duplicate": True}),
        clock=MutableClock(),
    )
    assert outbox.dispatch_due()[0].status == OUTBOX_DELIVERED
    assert row(engine, event_id)["attempt_count"] == 2


def test_payload_integrity_failure_blocks_transport(engine) -> None:
    event_id = enqueue(engine)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE pulse_booking_event_outbox SET payload_json='{}' WHERE event_id=:event_id"),
            {"event_id": event_id},
        )
    called = False

    def post(*args, **kwargs):
        nonlocal called
        called = True
        return FakeResponse(200, {"accepted": True})

    outbox = PulseBookingOutbox(engine, config(), http_post=post, clock=MutableClock())
    result = outbox.dispatch_due()[0]
    assert result.status == OUTBOX_FAILED
    assert result.error_category == "local_payload_integrity_error"
    assert called is False


def test_status_and_acknowledgement_never_expose_secret_or_arbitrary_response_data(engine) -> None:
    event_id = enqueue(engine)
    outbox = PulseBookingOutbox(
        engine,
        config(),
        http_post=lambda *args, **kwargs: FakeResponse(
            200,
            {
                "accepted": True,
                "duplicate": False,
                "action": "processed",
                "raw_secret": SECRET,
                "customer_email": "private@example.com",
            },
        ),
        clock=MutableClock(),
    )
    outbox.dispatch_due()
    stored = row(engine, event_id)
    assert SECRET not in (stored["acknowledgement_json"] or "")
    assert "private@example.com" not in (stored["acknowledgement_json"] or "")
    summary = json.dumps(outbox.status_summary(), sort_keys=True)
    assert SECRET not in summary
    assert "private@example.com" not in summary


def test_same_booking_versions_are_delivered_in_order_and_blocked_by_retry(engine) -> None:
    first = enqueue(engine)
    second = enqueue(engine, event(event_type="booking.rescheduled"))
    third = enqueue(engine, event(event_type="booking.cancelled", starts_at=None))
    calls: list[str] = []
    fail_first = {"value": True}

    def post(url, *, data, headers, timeout):
        payload = json.loads(data)
        calls.append(payload["event_id"])
        if fail_first["value"]:
            fail_first["value"] = False
            return FakeResponse(503, {"detail": "temporary"})
        return FakeResponse(200, {"accepted": True, "duplicate": False})

    outbox = PulseBookingOutbox(engine, config(), http_post=post, clock=MutableClock())
    assert outbox.dispatch_due()[0].status == OUTBOX_RETRY
    # Higher versions must not overtake an undelivered lower version.
    assert outbox.dispatch_due() == ()
    make_due(engine, first)
    assert outbox.dispatch_due()[0].event_id == first
    assert outbox.dispatch_due()[0].event_id == second
    assert outbox.dispatch_due()[0].event_id == third
    assert calls == [first, first, second, third]
