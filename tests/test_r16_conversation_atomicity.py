from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event as sqlalchemy_event, text

from config import settings
from db import conversations
from integrations.pulse_booking_events import ensure_pulse_outbox_tables

SECRET = "r16-shared-signing-secret-with-at-least-32-bytes"


@pytest.fixture
def engine(tmp_path, monkeypatch):
    value = create_engine(f"sqlite+pysqlite:///{tmp_path / 'conversation.db'}")
    sqlalchemy_event.listen(
        value,
        "connect",
        lambda dbapi_connection, _: dbapi_connection.create_function(
            "NOW", 0, lambda: datetime.now(UTC).isoformat()
        ),
    )
    with value.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE conversations (
                    tenant_id TEXT NOT NULL,
                    user_key TEXT NOT NULL,
                    lang_lock TEXT,
                    state TEXT,
                    service TEXT,
                    name TEXT,
                    datetime_iso TEXT,
                    time_text TEXT,
                    pending_json TEXT,
                    updated_at TIMESTAMP,
                    PRIMARY KEY (tenant_id, user_key)
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO conversations "
                "(tenant_id, user_key, lang_lock, state, service, updated_at) "
                "VALUES ('clinic_demo', '+37120000000', 'ru', 'AWAITING_CONFIRM', 'consultation', CURRENT_TIMESTAMP)"
            )
        )
    ensure_pulse_outbox_tables(value)
    monkeypatch.setattr(conversations, "engine", value)
    monkeypatch.setattr(settings, "PULSE_RECEPTIONIST_PUBLISHER_ENABLED", True)
    monkeypatch.setattr(settings, "PULSE_RECEPTIONIST_WEBHOOK_URL", "http://testserver/integrations/receptionist/v1/events")
    monkeypatch.setattr(settings, "PULSE_RECEPTIONIST_WEBHOOK_SIGNING_SECRET", SECRET)
    monkeypatch.setattr(settings, "PULSE_RECEPTIONIST_WORKER_ENABLED", False)
    try:
        yield value
    finally:
        value.dispose()


def state() -> dict:
    return {
        "lang": "ru",
        "state": "BOOKED",
        "service": "consultation",
        "name": "Client",
        "datetime_iso": "2026-07-19T09:00:00+00:00",
        "time_text": None,
        "pending": None,
        "_pulse_outbox_event": {
            "event_type": "booking.created",
            "tenant_id": "clinic_demo",
            "booking_ref": "google-event-atomic",
            "location_ref": "clinic_demo",
            "starts_at": datetime(2026, 7, 19, 9, 0, tzinfo=UTC),
            "service_ref": "consultation",
            "occurred_at": datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
        },
    }


def test_conversation_state_and_outbox_commit_atomically(engine) -> None:
    value = state()
    conversations.db_save_conversation("clinic_demo", "+37120000000", value)
    assert "_pulse_outbox_event" not in value
    with engine.connect() as conn:
        conversation = conn.execute(
            text("SELECT state, datetime_iso FROM conversations WHERE tenant_id='clinic_demo'")
        ).one()
        event = conn.execute(
            text("SELECT tenant_id, booking_ref, status, payload_json FROM pulse_booking_event_outbox")
        ).one()
    assert conversation[0] == "BOOKED"
    assert conversation[1] == "2026-07-19T09:00:00+00:00"
    assert event[0:3] == ("clinic_demo", "google-event-atomic", "pending")
    assert json.loads(event[3])["tenant_ref"] == "clinic_demo"


def test_wrong_tenant_rolls_back_conversation_and_event(engine) -> None:
    value = state()
    value["_pulse_outbox_event"]["tenant_id"] = "tenant_b"
    with pytest.raises(ValueError, match="tenant"):
        conversations.db_save_conversation("clinic_demo", "+37120000000", value)
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT state FROM conversations WHERE tenant_id='clinic_demo'")
        ).scalar_one() == "AWAITING_CONFIRM"
        assert conn.execute(text("SELECT COUNT(*) FROM pulse_booking_event_outbox")).scalar_one() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM pulse_booking_versions")).scalar_one() == 0
    assert "_pulse_outbox_event" in value


def test_disabled_publisher_preserves_booking_state_without_creating_event(engine, monkeypatch) -> None:
    monkeypatch.setattr(settings, "PULSE_RECEPTIONIST_PUBLISHER_ENABLED", False)
    value = state()
    conversations.db_save_conversation("clinic_demo", "+37120000000", value)
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT state FROM conversations WHERE tenant_id='clinic_demo'")
        ).scalar_one() == "BOOKED"
        assert conn.execute(text("SELECT COUNT(*) FROM pulse_booking_event_outbox")).scalar_one() == 0
    assert "_pulse_outbox_event" not in value
