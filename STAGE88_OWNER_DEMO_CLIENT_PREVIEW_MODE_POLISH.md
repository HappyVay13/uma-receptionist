# Stage 88 — Owner Demo / Client Preview Mode Polish

## Purpose

Give the client owner a safe preview/demo surface to see how Repliq would answer customer questions using the tenant's service catalog and Business Memory, without creating real bookings or sending real messages.

## Added owner-safe endpoints

- `GET /owner/demo`
- `GET /owner/demo/ui`
- `POST /owner/demo/preview`
- `GET /owner/client-preview`
- `GET /owner/client-preview/ui`
- `POST /owner/client-preview/message`

## Added admin-protected readiness endpoints

- `GET /owner-demo/readiness`
- `GET /client-preview/readiness`
- `GET /workspace/demo/readiness`
- `GET /demo/owner/readiness`

## Safety model

Preview mode is dry-run only:

- no calendar event is created;
- no live calendar mutation is called;
- no conversation state is persisted;
- no Telegram/SMS/WhatsApp customer message is sent;
- no booking confirmation is triggered;
- no admin setup links or secrets are exposed to owners.

## Source-of-truth model

- Service Catalog is the source of truth for prices.
- Business Memory / FAQ provides context and policy text.
- Working hours come from tenant settings/business profile.

## Not changed

Receptionist runtime, booking routing, slots, date/time parsing, price side-question runtime, confirmation, cancel/reschedule, Google Calendar runtime, Telegram webhook/runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, QA evaluator, LLM orchestration, and voice/calls were not changed.

## Verification

Expected checks after deploy:

- `/health`
- `/dialogue/qa`
- `/owner-demo/readiness?tenant_id=clinic_demo`
- `/client-preview/readiness?tenant_id=clinic_demo`
- `/workspace/demo/readiness?tenant_id=clinic_demo`
- `/demo/owner/readiness?tenant_id=clinic_demo`
- `/owner/demo/ui?tenant_id=clinic_demo`
- `/owner/demo?tenant_id=clinic_demo`
- `POST /owner/demo/preview?tenant_id=clinic_demo` through the owner UI
- `/owner/workspace/ui?tenant_id=clinic_demo`
- `/owner/dashboard/ui?tenant_id=clinic_demo`
- `/owner/launch-review/ui?tenant_id=clinic_demo`
