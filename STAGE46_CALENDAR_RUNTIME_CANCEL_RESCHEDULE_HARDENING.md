# Stage 46 — Calendar Runtime Cancel/Reschedule Hardening

## Baseline
- Confirmed before this stage: Stage 45.1 deployed with `/dialogue/qa = 44/44 passed`.

## Factual root cause
The full reschedule flow already reached the correct update branch in `book_appointment_for_datetime()` when `pending.reschedule_event_id` was present. However, after the calendar update path returned, later wording layers (`humanize_result`, AI composer, and Stage 33 soft UX) treated the result as a generic `booked` status and could rewrite the final reply as a new-booking confirmation.

Observed Stage 45 QA examples showed final text such as “записал вас” / “pierakstīju jūs” even though the flow was a reschedule. That is misleading for production runtime because the user asked to move an existing appointment, not create a new one.

## Changes
- Successful reschedule finalization now returns safe metadata:
  - `calendar_action = update_event`
  - `reschedule_finalized = True`
  - `preserve_text = True`
- Stage 33 soft UX now respects `preserve_text` / `reschedule_finalized` and does not rewrite completed reschedule wording.
- Successful cancellation returns `calendar_action = delete_event`.
- Stage 35 QA runner records safe per-turn metadata: `calendar_action` and `reschedule_finalized`.
- Regression evaluator can now verify:
  - `calendar_delete_path`
  - `calendar_update_path`
  - `reschedule_final_text`
- Added four Stage 46 scenarios, expanding the matrix from 44 to 48.

## Safety boundaries
- No real Google Calendar mutation is performed by `/dialogue/qa`; Stage 35 safe mode remains active.
- No slot generation, service inference, date parsing, side-question flow, or cancellation/reschedule start behavior was changed.
- Runtime still uses the existing production functions outside safe mode:
  - `delete_calendar_event()` for cancellation
  - `update_calendar_event()` for reschedule finalization

## Expected deploy check
- `/dialogue/qa = 48/48 passed`
