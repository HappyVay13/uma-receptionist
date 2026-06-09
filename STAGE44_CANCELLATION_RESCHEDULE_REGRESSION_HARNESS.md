# Stage 44 — Cancellation/Reschedule Regression Harness

## Purpose

Stage 44 adds safe-mode regression coverage for existing cancellation and rescheduling paths.

This stage does **not** change runtime cancellation/rescheduling behavior.

## Factual starting point

Confirmed before Stage 44:

- Stage 43A deployed.
- `/dialogue/qa` = 30/30 passed.
- `/health` = ok.
- `/internal/readiness` = ok.
- Tenant readiness for `clinic_demo` = ready.

Existing code already contained cancellation/reschedule paths:

- `ORCH_ACTION_CANCEL`
- `ORCH_ACTION_RESCHEDULE`
- `find_next_event_by_phone()`
- `delete_calendar_event()`
- `update_calendar_event()`
- `pending["reschedule_event_id"]`
- `abort_reschedule_text()`

## Root cause for needing a harness

Before Stage 44, `/dialogue/qa` could not test successful cancellation or successful reschedule start because Stage 35 calendar safe mode intentionally skipped real calendar lookup:

```python
if stage35_calendar_safe_mode_active():
    return None
```

That meant cancellation/reschedule tests could only prove the `no active booking` branch. They could not safely exercise the branches where an existing calendar event is found.

## What Stage 44 adds

Stage 44 adds a regression-only event fixture:

- `_STAGE35_CALENDAR_EVENT_FIXTURE`
- `stage35_calendar_event_fixture()`
- `stage35_build_calendar_event_fixture()`

`find_next_event_by_phone()` now checks this fixture only when Stage 35 calendar safe mode is active. Outside safe mode, runtime behavior is unchanged.

## New regression scenarios

The matrix expands from 30 to 40 scenarios.

Added scenarios:

1. `stage44_ru_cancel_no_active_booking`
2. `stage44_lv_cancel_no_active_booking`
3. `stage44_ru_cancel_existing_booking`
4. `stage44_lv_cancel_existing_booking`
5. `stage44_ru_reschedule_no_active_booking`
6. `stage44_lv_reschedule_no_active_booking`
7. `stage44_ru_reschedule_existing_booking_start`
8. `stage44_lv_reschedule_existing_booking_start`
9. `stage44_ru_reschedule_abort`
10. `stage44_lv_reschedule_abort`

## Evaluator additions

The Stage 35 evaluator now detects:

- `cancel_reschedule_flow`
- `no_active_booking`
- `cancel_request_detected`
- `booking_cancelled`
- `reschedule_started`
- `reschedule_pending`
- `reschedule_aborted`
- `reschedule_finalized`

No existing evaluator expectations were relaxed.

## What Stage 44 does not do

Stage 44 does not fix full reschedule continuation.

Candidate Stage 45 issue:

After a user says `перенести запись` / `pārcelt pierakstu`, the system can start reschedule flow when an event is found. But the next natural answer such as `послезавтра вечером` / `parīt vakarā` needs separate execution-flow analysis.

Reason: current slot generation still depends on service/date/time context, while reschedule starts from a found event summary and `reschedule_event_id`. This should be handled as Stage 45, not hidden in the test harness.

## Expected production result

After deploy:

```text
/dialogue/qa = 40/40 passed
```
