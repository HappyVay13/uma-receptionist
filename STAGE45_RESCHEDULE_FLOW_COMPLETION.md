# Stage 45 — Reschedule Flow Completion

## Baseline before Stage 45
- Stage 44 deployed successfully.
- User confirmed `/dialogue/qa` = 40/40 passed.
- Cancellation/reschedule harness exists and uses Stage 35 calendar safe mode fixtures.

## Root cause
Full reschedule continuation was not safely protected after `reschedule_event_id` was stored.

The start-reschedule branch found the existing calendar event and stored:

- `reschedule_event_id`
- `reschedule_old_iso`
- `reschedule_summary`
- `reschedule_description`

But it did not persist the original service into the active booking context. The existing calendar fixture summary contains the service, for example:

```text
Clinic Demo - konsultācija
```

Without service context, the next user message such as `послезавтра вечером` or `parīt vakarā` could be routed to service selection instead of slot regeneration.

## Change
Added deterministic service inference from matched calendar event metadata:

```text
infer_service_item_from_calendar_event()
```

It checks the calendar event summary and description against the tenant service catalog using existing service matching logic. When it finds the original service, it persists it via `remember_booking_service()` during reschedule start.

## Regression scenarios added
The matrix expands from 40 to 44 scenarios with:

- `stage45_ru_reschedule_full_slot_ack_confirm`
- `stage45_lv_reschedule_full_slot_ack_confirm`
- `stage45_ru_reschedule_slot_number_confirm`
- `stage45_lv_reschedule_slot_number_confirm`

These scenarios protect both RU/LV full reschedule completion paths:

1. Start reschedule from an existing calendar fixture.
2. Provide a new fuzzy date/time.
3. Choose an offered slot by positive acknowledgement or number.
4. Confirm the reschedule.
5. Finish through the existing `book_appointment_for_datetime()` reschedule update path.

## Non-goals
- No change to cancellation behavior.
- No change to normal booking behavior.
- No real calendar mutation during `/dialogue/qa`; safe mode remains active.
- No evaluator relaxation.

## Expected result after deploy

```text
/dialogue/qa = 44/44 passed
```
