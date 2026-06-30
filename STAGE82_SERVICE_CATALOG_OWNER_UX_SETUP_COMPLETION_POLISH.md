# Stage 82 — Service Catalog Owner UX / Setup Completion Polish

## Goal

Continue the Mature SMB SaaS phase by giving the client owner an owner-safe service catalog screen. The owner can review and update service names, duration, prices, aliases, descriptions, active status, and service keys without opening super-admin configuration screens.

## Added endpoints

Owner-safe:

- `GET /owner/services`
- `GET /owner/services/ui`
- `GET /owner/service-catalog`
- `GET /owner/service-catalog/ui`
- `POST /owner/services/update`
- `POST /owner/service-catalog/update`

Admin-protected readiness:

- `GET /owner-services/readiness`
- `GET /owner-service-catalog/readiness`
- `GET /service-catalog/owner/readiness`
- `GET /workspace/services/readiness`

## Security model

- Owner service routes are protected by Stage 71 signed owner session and tenant ownership binding.
- Super-admin may open owner surfaces only through explicit Stage 61/62 admin bypass.
- Owner write routes are protected by Stage 74 owner-scope CSRF/browser-write hardening.
- Owner UI does not expose admin service catalog builder or tenant config links as primary navigation.
- No raw admin tokens, owner login codes, magic tokens, token hashes, CSRF secrets, Telegram tokens, Google credentials, raw IPs, or subject hashes are exposed.

## Runtime impact

The receptionist runtime semantics are not changed. The Stage 82 owner update writes through the same Stage 66 service catalog normalization/sync model, so saved services remain compatible with existing runtime service catalog logic and managed price facts.

## Expected verification

- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/owner-services/readiness?tenant_id=clinic_demo` returns `stage=82`.
- `service_catalog_owner_ux_ready=true`.
- `owner_service_catalog_update_ready=true`.
- `/owner/services/ui?tenant_id=<owner_tenant>` opens with owner session or super-admin bypass.
- Saving through owner UI returns `ok=true`.
- `/tenant-workspace/readiness?tenant_id=clinic_demo` uses owner-safe services next action.
- Owner dashboard/workspace/billing still work.

## Not changed

- Booking routing
- Slot generation
- Date/time parsing
- Price side-question logic
- Confirmation
- Cancel/reschedule
- Google Calendar event runtime
- Telegram webhook runtime
- Billing semantics
- CSRF semantics
- Abuse/rate-limit semantics
- Magic-link semantics
- Dialogue QA evaluator
- LLM orchestration
- Voice/calls
