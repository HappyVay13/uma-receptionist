# Stage 48 — Text MVP UX Scope Hardening

## Purpose

Stage 48 locks the current MVP product scope as a text-first receptionist and hardens Russian text UX for customer-facing replies that previously could expose raw Latvian labels from minimal tenant data.

The user clarified the product direction after Stage 47:

- current launch scope: text receptionist;
- voice/calls: future expansion, not the active MVP channel.

## Factual root cause

The runtime can correctly route booking, FAQ, cancellation and reschedule flows, but some customer-facing text was built directly from tenant service catalog values.

For tenants where the service catalog only contains a Latvian service label such as `konsultācija`, Russian replies could expose mixed-language text, for example:

- `konsultācija стоит 10 eiro`;
- confirmation variants could include raw service labels in Russian text.

This was a text UX issue only. It did not affect routing, slot generation, booking state, or calendar actions.

## Changes

### 1. Text-MVP product scope metadata

`/internal/readiness` now includes a read-only `product_scope` block:

```json
{
  "current_mvp_channel": "text",
  "active_receptionist_mode": "text_first",
  "voice_calls_scope": "future_phase"
}
```

Voice/TTS/Twilio readiness flags may still exist as infrastructure, but they are not treated as the active MVP product scope.

### 2. Localized service display helper

Added safe text-only helpers:

- `text_mvp_localized_service_name(...)`
- `text_mvp_localized_price(...)`

These helpers affect customer-facing text only. They do not mutate service keys, service catalog records, booking context, or calendar payloads.

### 3. Russian price/confirmation text hardening

Known minimal-catalog labels are localized for Russian output when safe:

- `konsultācija` / `konsultacija` -> `консультация`
- `eiro` / `EUR` -> `евро`

The Russian confirmation text now avoids awkward raw service interpolation and uses a safer form:

- `на услугу «консультация»`

### 4. Regression expansion

Regression matrix expanded:

- before Stage 48: 48 scenarios;
- after Stage 48: 50 scenarios.

Added scenarios:

- `stage48_ru_price_side_question_localized_text`
- `stage48_ru_slot_number_confirmation_localized_service_text`

Added evaluator tokens:

- `ru_text_localized`
- `localized_ru_price_text`
- forbidden `raw_lv_service_text_in_ru_reply`

## What was not changed

Stage 48 does not change:

- booking routing;
- service matching;
- slot generation;
- date/time parsing;
- cancellation logic;
- reschedule logic;
- Google Calendar create/update/delete functions;
- live calendar behavior;
- voice/call runtime paths.

## Expected production checks after deploy

```text
/dialogue/qa = 50/50 passed
/internal/readiness = ok
qa.protected_baseline = 50/50
product_scope.current_mvp_channel = text
product_scope.voice_calls_scope = future_phase
```
