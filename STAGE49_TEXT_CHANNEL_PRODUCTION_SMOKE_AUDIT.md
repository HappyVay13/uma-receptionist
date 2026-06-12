# Stage 49 — Text Channel Production Smoke Audit

## Baseline
- Confirmed before this stage: Stage 48 deployed with `/dialogue/qa = 50/50 passed`.
- Confirmed before this stage: `/internal/readiness?tenant_id=clinic_demo` returned `status = ok`, `qa.protected_baseline = 50/50`, `scenario_count = 50`, and product scope `current_mvp_channel = text`.
- Current launch scope: Repliq MVP is a text-first receptionist. Voice/calls are future scope.

## Purpose
Stage 49 prepares the production smoke audit for the text MVP. It does not expand conversation behavior. It makes the live smoke scope visible in documentation and readiness metadata, then defines the exact manual checks that should be run through a real text channel.

## Code impact
No conversational behavior was changed.

Changed runtime surface only:
- `/internal/readiness` now includes read-only `text_channel_smoke` metadata.

The metadata is informational only. It does not run a smoke test, call an LLM, create/update/delete Google Calendar events, or change conversation state.

## Factual protected baseline
The current safe-mode regression proof is:

```text
/dialogue/qa = 50/50 passed
```

This protects booking, side-questions, localized RU text UX, cancellation, reschedule start/abort/full flow, and safe calendar action metadata.

## Recommended first smoke channel
Use `/dev_chat_ui` first. It is the lowest-risk text channel because it avoids Telegram/WhatsApp transport noise while still using the same backend conversation logic.

Recommended order:
1. `/dev_chat_ui` or `/dev_chat` with `tenant_id=clinic_demo`.
2. Telegram text smoke after dev channel is clean.
3. WhatsApp text smoke after dev channel is clean.
4. Voice/calls are not part of this stage.

## Test user IDs
Use unique user IDs/phone keys so `find_next_event_by_phone()` can reliably locate the test event in Google Calendar.

Suggested IDs:

```text
stage49_text_smoke_ru_001
stage49_text_smoke_lv_001
```

## Smoke checklist A — readiness and regression
Before live conversation checks:

```text
/dialogue/qa
/internal/readiness?tenant_id=clinic_demo
```

Expected:

```text
/dialogue/qa = 50/50 passed
/internal/readiness.status = ok
/internal/readiness.qa.protected_baseline = 50/50
/internal/readiness.product_scope.current_mvp_channel = text
/internal/readiness.text_channel_smoke.stage = 49
```

## Smoke checklist B — RU text booking with side question
Use user id:

```text
stage49_text_smoke_ru_001
```

Messages:

```text
хочу записаться на консультацию завтра вечером
сколько это стоит?
2
да
```

Expected app behavior:
- replies remain Russian;
- price answer is localized, for example `консультация стоит 10 евро`;
- no raw `konsultācija стоит 10 eiro` customer-facing text;
- booking flow is preserved after the price question;
- slot selection reaches final booked state.

Expected Google Calendar behavior:
- exactly one event is created for this user id/phone;
- event description contains the same test user id/phone and tenant id;
- no duplicate event is created during side-question handling.

## Smoke checklist C — RU reschedule existing booking
Continue with the same RU user id after checklist B.

Messages:

```text
перенести запись
послезавтра вечером
2
да
```

Expected app behavior:
- Repliq finds the existing booking;
- offers new slots;
- final wording says the appointment was moved/rescheduled, not that a new appointment was created.

Expected Google Calendar behavior:
- the existing event is updated to the new selected time;
- there is not a second duplicate event for the same user id/phone.

## Smoke checklist D — RU cancel updated booking
Continue with the same RU user id after checklist C.

Message:

```text
отменить запись
```

Expected app behavior:
- cancellation succeeds in Russian.

Expected Google Calendar behavior:
- the updated event is removed or no longer appears as an active upcoming booking;
- a repeated `отменить запись` should return no active booking.

## Smoke checklist E — LV text path
Use separate user id:

```text
stage49_text_smoke_lv_001
```

Messages:

```text
gribu pierakstīties uz konsultāciju rīt vakarā
cik tas maksā?
2
jā
pārcelt pierakstu
parīt vakarā
2
jā
atcelt pierakstu
```

Expected:
- replies remain Latvian;
- price answer is grounded;
- one event is created;
- reschedule updates the same event;
- cancel removes the event;
- no duplicate event remains.

## Pass criteria
Stage 49 live smoke is considered passed only when all are true:

- `/dialogue/qa = 50/50 passed` remains true after deploy.
- `/internal/readiness?tenant_id=clinic_demo` returns `status = ok`.
- RU smoke path creates one event, updates that same event, then cancels it.
- LV smoke path creates one event, updates that same event, then cancels it.
- RU replies do not expose raw Latvian service/price labels when a localized display is available.
- Reschedule final text is action-specific.
- No duplicate Google Calendar events remain after reschedule.

## Safety boundaries
- This stage does not add regression scenarios.
- This stage does not change text routing, booking state transitions, date/time parsing, cancellation, reschedule, or Google Calendar mutation logic.
- This stage does not add voice/call requirements.
- Any smoke failure must be handled in a separate fix stage with exact transcript and calendar observation.
