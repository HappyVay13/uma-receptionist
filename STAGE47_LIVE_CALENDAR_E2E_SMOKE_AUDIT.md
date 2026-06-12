# Stage 47 — Live Calendar E2E Smoke Audit & Baseline Sync

## Baseline
- Confirmed before this stage: Stage 46 deployed with `/dialogue/qa = 48/48 passed`.
- Git status after Stage 46 was reported clean and synced with `origin/main`.

## Purpose
Stage 47 does not change the conversational runtime. It locks the confirmed Stage 46 regression baseline in project documentation/readiness metadata and defines the live Google Calendar smoke test that should be executed manually through a real channel.

## Factual static audit from code
The current runtime code has the following calendar action paths:

1. New booking final confirmation
   - Uses `create_calendar_event()` when there is no `pending.reschedule_event_id`.
   - Stage 35 calendar safe mode skips real create during `/dialogue/qa`.

2. Cancellation
   - Detects cancel intent.
   - Uses `find_next_event_by_phone()` to locate the next matching event.
   - Uses `delete_calendar_event()` for successful cancellation.
   - Returns safe metadata: `calendar_action = delete_event`.

3. Reschedule
   - Detects reschedule intent.
   - Uses `find_next_event_by_phone()` to locate the existing event.
   - Stores `reschedule_event_id`, old time, summary, description, and inferred service in pending state.
   - On final confirmation, `book_appointment_for_datetime()` uses `update_calendar_event()` when `pending.reschedule_event_id` is present.
   - Returns safe metadata: `calendar_action = update_event`, `reschedule_finalized = True`, `preserve_text = True`.

## Why live smoke is still needed
`/dialogue/qa` proves the decision flow and safe metadata under Stage 35 calendar safe mode, but it intentionally does not mutate real Google Calendar. Therefore real Google Calendar behavior must be checked manually before treating the calendar runtime path as production-proven.

## Recommended live smoke channel
Use the lowest-risk channel first:

1. `/dev_chat_ui` or `/dev_chat` with tenant `clinic_demo`.
2. Then Telegram or Twilio/WhatsApp only after dev-channel smoke is clean.

Use a unique test user id/phone per run, for example:

```text
stage47_live_smoke_001
```

This matters because `find_next_event_by_phone()` searches upcoming Google Calendar events by the user key stored in the event description.

## Live smoke checklist

### A. Readiness check
Open:

```text
/internal/readiness?tenant_id=clinic_demo
```

Expected:

```text
status = ok
qa.protected_baseline = 48/48
```

### B. Create a real test booking
Reset the test conversation first if using dev channel.

Send:

```text
хочу записаться на консультацию завтра вечером
```

Then select/confirm the first offered slot:

```text
да, подходит
да
```

Expected in app response:
- booking reaches final booked state;
- text says the user is booked for the selected time.

Expected in Google Calendar:
- exactly one event is created for the test user;
- event summary contains the service, for example `konsultācija`;
- event description contains the test user key/phone and tenant id.

### C. Reschedule the same real test booking
Using the same user id/phone, send:

```text
перенести запись
послезавтра вечером
2
да
```

Expected in app response:
- reschedule starts from the existing event;
- new slot options are offered;
- final text says the appointment was moved/rescheduled, not that a brand-new appointment was created.

Expected in Google Calendar:
- the original event is updated to the new selected time;
- there is not a duplicate second event for the same test user;
- event description still contains the same test user key/phone and tenant id.

### D. Cancel the same real test booking
Using the same user id/phone, send:

```text
отменить запись
```

Expected in app response:
- cancellation succeeds;
- text says the appointment was cancelled.

Expected in Google Calendar:
- the test event is removed or no longer appears as an active upcoming event;
- a repeated cancellation request returns no active booking.

### E. Latvian smoke variant
Repeat the same create/reschedule/cancel path with a separate test user id:

```text
stage47_live_smoke_lv_001
```

Suggested messages:

```text
gribu pierakstīties uz konsultāciju rīt vakarā
jā, der
jā
pārcelt pierakstu
parīt vakarā
2
jā
atcelt pierakstu
```

Expected:
- same calendar behavior as RU path;
- Latvian language is preserved.

## Pass criteria
Stage 47 live smoke is considered passed only if all of the following are true:

- `/dialogue/qa = 48/48 passed` remains true after deploy.
- `/internal/readiness?tenant_id=clinic_demo` returns `status = ok`.
- Real booking creates exactly one Google Calendar event.
- Real reschedule updates that existing event instead of creating a duplicate.
- Real cancellation removes the updated event.
- Final reschedule wording is action-specific, not generic new-booking wording.

## Safety boundaries
- This stage does not add new regression scenarios.
- This stage does not change slot generation, date parsing, side-question handling, booking flow, cancellation flow, or reschedule flow.
- This stage does not add endpoints that mutate calendar data.
- Any live Google Calendar issue discovered during smoke testing must be handled in a separate Stage 47.1 with the exact failing transcript/calendar observation.
