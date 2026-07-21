from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_create_reschedule_cancel_application_flows_emit_one_versioned_event_each(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "application-flow.db"
    script = r'''
import json
import sys
import types
from datetime import UTC, datetime, timedelta
from sqlalchemy import event as sqlalchemy_event, text


def module(name):
    value = types.ModuleType(name)
    sys.modules[name] = value
    return value


class Dummy:
    def __init__(self, *args, **kwargs):
        pass
    def __getattr__(self, name):
        return lambda *args, **kwargs: Dummy()
    def __str__(self):
        return ""


twilio = module("twilio"); twilio.__path__ = []
twiml = module("twilio.twiml"); twiml.__path__ = []
voice = module("twilio.twiml.voice_response"); voice.VoiceResponse = Dummy; voice.Gather = Dummy
jwt = module("twilio.jwt"); jwt.__path__ = []
access = module("twilio.jwt.access_token"); access.__path__ = []; access.AccessToken = Dummy
grants = module("twilio.jwt.access_token.grants"); grants.VoiceGrant = Dummy
rest = module("twilio.rest"); rest.Client = Dummy
validator = module("twilio.request_validator"); validator.RequestValidator = Dummy

google = module("google"); google.__path__ = []
oauth2 = module("google.oauth2"); oauth2.__path__ = []
service_account = module("google.oauth2.service_account")
class Credentials:
    @classmethod
    def from_service_account_info(cls, *args, **kwargs):
        return cls()
service_account.Credentials = Credentials
oauth2.service_account = service_account
googleapi = module("googleapiclient"); googleapi.__path__ = []
discovery = module("googleapiclient.discovery"); discovery.build = lambda *args, **kwargs: None

import repliq.legacy_app as legacy
from db.conversations import db_save_conversation
from integrations.pulse_booking_events import ensure_pulse_outbox_tables

sqlalchemy_event.listen(
    legacy.engine,
    "connect",
    lambda dbapi_connection, _: dbapi_connection.create_function(
        "NOW", 0, lambda: datetime.now(UTC).isoformat()
    ),
)

with legacy.engine.begin() as conn:
    conn.execute(text("""
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
    """))
    conn.execute(text("""
        INSERT INTO conversations
            (tenant_id, user_key, lang_lock, state, service, updated_at)
        VALUES
            ('clinic_demo', '+37120000000', 'ru', 'AWAITING_CONFIRM', 'consultation', CURRENT_TIMESTAMP)
    """))
ensure_pulse_outbox_tables(legacy.engine)
qa_matrix = legacy.stage34_regression_test_matrix()
assert qa_matrix['total'] == 50
assert len(qa_matrix['items']) == 50

# Stage 35 uses synthetic Calendar fixtures. Its events must never enter the
# production outbox when the publisher is enabled.
legacy.STAGE35_CALENDAR_SAFE_MODE_ENABLED = True
safe_token = legacy._STAGE35_CALENDAR_SAFE_MODE.set(True)
try:
    qa_state = {}
    legacy.attach_pulse_booking_event(
        qa_state,
        event_type="booking.created",
        tenant_id="clinic_demo",
        booking_ref="stage35-dummy-event",
        starts_at=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
        ends_at=datetime(2026, 7, 20, 8, 30, tzinfo=UTC),
        duration_minutes=30,
        service_ref="consultation",
    )
    assert "_pulse_outbox_event" not in qa_state
finally:
    legacy._STAGE35_CALENDAR_SAFE_MODE.reset(safe_token)
legacy.STAGE35_CALENDAR_SAFE_MODE_ENABLED = False

legacy.calendar_is_configured = lambda calendar_id: True
legacy.is_closed_day_for_rules = lambda dt, rules: False
legacy.violates_min_notice = lambda dt, rules: False
legacy.in_business_hours = lambda *args, **kwargs: True
legacy.is_slot_busy = lambda *args, **kwargs: False
legacy.create_calendar_event = lambda *args, **kwargs: {
    "id": "google-event-r16-e2e",
    "htmlLink": "https://calendar.invalid/private-link",
}
legacy.update_calendar_event = lambda *args, **kwargs: "https://calendar.invalid/private-updated-link"
legacy.delete_calendar_event = lambda *args, **kwargs: True

catalog = [{
    "key": "consultation",
    "name_lv": "Konsultācija",
    "name_ru": "Консультация",
    "name_en": "Consultation",
    "duration_min": 30,
}]
settings = {
    "calendar_id": "calendar@example.invalid",
    "service_account_json": None,
    "biz_name": "Clinic Demo",
    "services_hint": "Consultation",
    "work_start": "08:00",
    "work_end": "18:00",
    "business_rules": None,
}
slot_1 = datetime(2026, 7, 20, 9, 0, tzinfo=UTC)
create_state = {
    "lang": "ru",
    "state": legacy.STATE_AWAITING_CONFIRM,
    "service": "consultation",
    "name": "Client",
    "datetime_iso": slot_1.isoformat(),
    "time_text": None,
    "pending": {"booking_intent": True, "service": "consultation", "name": "Client"},
}
created = legacy.book_appointment_for_datetime(
    "clinic_demo", "+37120000000", "dev", "ru", create_state,
    settings, catalog, slot_1, require_confirmation=False,
)
assert created["status"] == "booked"
assert create_state["_pulse_outbox_event"]["event_type"] == "booking.created"
assert create_state["_pulse_outbox_event"]["booking_ref"] == "google-event-r16-e2e"
db_save_conversation("clinic_demo", "+37120000000", create_state)

slot_2 = datetime(2026, 7, 20, 11, 0, tzinfo=UTC)
reschedule_state = {
    "lang": "ru",
    "state": legacy.STATE_AWAITING_CONFIRM,
    "service": "consultation",
    "name": "Client",
    "datetime_iso": slot_2.isoformat(),
    "time_text": None,
    "pending": {
        "booking_intent": True,
        "service": "consultation",
        "name": "Client",
        "reschedule_event_id": "google-event-r16-e2e",
        "reschedule_old_iso": slot_1.isoformat(),
        "reschedule_summary": "Clinic Demo - Consultation",
        "reschedule_description": "tenant=clinic_demo",
    },
}
rescheduled = legacy.book_appointment_for_datetime(
    "clinic_demo", "+37120000000", "dev", "ru", reschedule_state,
    settings, catalog, slot_2, require_confirmation=False,
)
assert rescheduled["status"] == "booked"
assert reschedule_state["_pulse_outbox_event"]["event_type"] == "booking.rescheduled"
assert reschedule_state["_pulse_outbox_event"]["booking_ref"] == "google-event-r16-e2e"
db_save_conversation("clinic_demo", "+37120000000", reschedule_state)

cancel_state = {
    "lang": "ru",
    "state": legacy.STATE_BOOKED,
    "service": "consultation",
    "name": "Client",
    "datetime_iso": slot_2.isoformat(),
    "time_text": None,
    "pending": None,
}
assert legacy.cancel_authoritative_booking(
    cancel_state,
    tenant_id="clinic_demo",
    calendar_id=settings["calendar_id"],
    calendar_event={
        "id": "google-event-r16-e2e",
        "start": {"dateTime": slot_2.isoformat()},
        "end": {"dateTime": (slot_2 + timedelta(minutes=30)).isoformat()},
    },
    service_account_json=None,
) is True
assert cancel_state["_pulse_outbox_event"]["event_type"] == "booking.cancelled"
db_save_conversation("clinic_demo", "+37120000000", cancel_state)

with legacy.engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT event_id, event_type, aggregate_version, tenant_id, booking_ref, payload_json
        FROM pulse_booking_event_outbox
        ORDER BY aggregate_version
    """)).mappings().all()
    conversation = conn.execute(text("""
        SELECT state, datetime_iso FROM conversations
        WHERE tenant_id='clinic_demo' AND user_key='+37120000000'
    """)).one()

assert [row["event_type"] for row in rows] == [
    "booking.created", "booking.rescheduled", "booking.cancelled"
]
assert [row["aggregate_version"] for row in rows] == [1, 2, 3]
assert len({row["event_id"] for row in rows}) == 3
assert {row["tenant_id"] for row in rows} == {"clinic_demo"}
assert {row["booking_ref"] for row in rows} == {"google-event-r16-e2e"}
assert conversation[0] == legacy.STATE_CANCELLED
assert conversation[1] is None
for row in rows:
    payload = json.loads(row["payload_json"])
    assert payload["schema_version"] == "2026-07-22"
    assert payload["tenant_ref"] == "clinic_demo"
    assert payload["booking"]["booking_ref"] == "google-event-r16-e2e"
    if payload["event_type"] in {"booking.created", "booking.rescheduled"}:
        assert payload["booking"]["duration_minutes"] == 30
        assert payload["booking"]["ends_at"] is not None
    assert "private-link" not in row["payload_json"]
print(json.dumps({"events": len(rows), "versions": [r["aggregate_version"] for r in rows], "qa_cases": qa_matrix['total']}))
'''
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
            "PULSE_RECEPTIONIST_PUBLISHER_ENABLED": "true",
            "PULSE_RECEPTIONIST_WEBHOOK_URL": "http://testserver/integrations/receptionist/v1/events",
            "PULSE_RECEPTIONIST_WEBHOOK_SIGNING_SECRET": "r16-shared-signing-secret-with-at-least-32-bytes",
            "PULSE_RECEPTIONIST_WORKER_ENABLED": "false",
            "STAGE35_CALENDAR_SAFE_MODE": "false",
            "PYTHONPATH": str(project_root),
        }
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    assert json.loads(completed.stdout.strip().splitlines()[-1]) == {
        "events": 3,
        "versions": [1, 2, 3],
        "qa_cases": 50,
    }
