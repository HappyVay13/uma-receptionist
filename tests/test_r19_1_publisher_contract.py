from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from integrations.pulse_booking_events import (
    LEGACY_R11_SCHEMA_VERSION,
    R19_SCHEMA_VERSION,
    PendingBookingEvent,
    enqueue_booking_event,
    ensure_pulse_outbox_tables,
)

START = datetime(2026, 7, 22, 9, 0, tzinfo=UTC)


def _engine(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'r19_1.db'}")
    ensure_pulse_outbox_tables(engine)
    return engine


def _payload(engine, event: PendingBookingEvent) -> dict:
    with engine.begin() as conn:
        event_id = enqueue_booking_event(conn, event, max_attempts=3)
    with engine.connect() as conn:
        raw = conn.execute(
            text("SELECT payload_json FROM pulse_booking_event_outbox WHERE event_id=:event_id"),
            {"event_id": event_id},
        ).scalar_one()
    return json.loads(raw)


def test_legacy_contract_remains_byte_shape_compatible(tmp_path) -> None:
    engine = _engine(tmp_path)
    payload = _payload(
        engine,
        PendingBookingEvent(
            event_type="booking.created",
            tenant_id="clinic_demo",
            booking_ref="legacy-booking",
            starts_at=START,
            service_ref="consultation",
            location_ref="clinic_demo",
            occurred_at=START,
        ),
    )
    assert payload["schema_version"] == LEGACY_R11_SCHEMA_VERSION == "2026-07-14"
    assert payload["booking"] == {
        "booking_ref": "legacy-booking",
        "location_ref": "clinic_demo",
        "service_ref": "consultation",
        "starts_at": "2026-07-22T09:00:00Z",
    }
    engine.dispose()


def test_r19_contract_emits_exact_end_time_and_duration(tmp_path) -> None:
    engine = _engine(tmp_path)
    end = START + timedelta(minutes=45)
    payload = _payload(
        engine,
        PendingBookingEvent(
            event_type="booking.created",
            tenant_id="clinic_demo",
            booking_ref="r19-booking",
            starts_at=START,
            service_ref="consultation",
            location_ref="clinic_demo",
            occurred_at=START,
            contract_version=R19_SCHEMA_VERSION,
            ends_at=end,
            duration_minutes=45,
        ),
    )
    assert payload["schema_version"] == "2026-07-22"
    assert payload["booking"]["starts_at"] == "2026-07-22T09:00:00Z"
    assert payload["booking"]["ends_at"] == "2026-07-22T09:45:00Z"
    assert payload["booking"]["duration_minutes"] == 45
    engine.dispose()


@pytest.mark.parametrize(
    "ends_at,duration_minutes,error",
    [
        (None, 45, "ends_at is required"),
        (START + timedelta(minutes=45), None, "duration_minutes is required"),
        (START + timedelta(minutes=45), 30, "must match"),
    ],
)
def test_r19_contract_rejects_incomplete_or_inconsistent_duration(
    ends_at, duration_minutes, error
) -> None:
    event = PendingBookingEvent(
        event_type="booking.created",
        tenant_id="clinic_demo",
        booking_ref="invalid-r19-booking",
        starts_at=START,
        service_ref="consultation",
        location_ref="clinic_demo",
        occurred_at=START,
        contract_version=R19_SCHEMA_VERSION,
        ends_at=ends_at,
        duration_minutes=duration_minutes,
    )
    with pytest.raises(ValueError, match=error):
        event.validate()


def test_r19_cancel_allows_missing_historical_end_time(tmp_path) -> None:
    engine = _engine(tmp_path)
    payload = _payload(
        engine,
        PendingBookingEvent(
            event_type="booking.cancelled",
            tenant_id="clinic_demo",
            booking_ref="cancelled-booking",
            starts_at=None,
            service_ref="consultation",
            location_ref="clinic_demo",
            occurred_at=START,
            contract_version=R19_SCHEMA_VERSION,
        ),
    )
    assert payload["schema_version"] == "2026-07-22"
    assert payload["booking"]["ends_at"] is None
    assert payload["booking"]["duration_minutes"] is None
    engine.dispose()
