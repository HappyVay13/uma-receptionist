# Stage 63 — Tenant Creation / Signup Flow Foundation

## Scope

Stage 63 starts the self-serve SaaS transition by hardening and exposing a tenant creation / signup foundation.

This stage does **not** change the receptionist core. It does not modify booking, cancel, reschedule, price side-questions, Telegram runtime handling, Google Calendar event create/update/delete, or the dialogue regression evaluator.

## What changed

- Added Stage 63 readiness metadata:
  - `GET /tenant/creation/readiness?tenant_id=clinic_demo`
  - `GET /signup/readiness?tenant_id=clinic_demo`
- Added signup/create UI aliases:
  - `GET /signup`
  - `GET /signup/ui`
  - `GET /tenant/create/ui`
  - existing `GET /onboarding/ui` remains supported
- Hardened tenant creation API:
  - `POST /tenant/create`
  - `POST /onboarding/create_tenant`
- Added `tenant_slug` support with validation, reserved slugs, length limits, and collision checks.
- Added predictable generated tenant slugs when a slug is not supplied.
- Added Stage 63 readiness into `/internal/readiness` and `/tenant/config`.
- Added Create tenant links to `/dashboard` and `/tenant/config/ui`.
- Closed the previous protection gap where `/onboarding/create_tenant` was protected but `/tenant/create` was not listed in the Stage 61 protected path set.

## Security model

Tenant creation is still protected by Stage 61/62 admin session/token.

This is intentional. Public self-serve SaaS still needs owner identity, tenant ownership checks, billing/subscription lifecycle, CSRF/rate-limits, and public signup abuse protection.

`public_saas_ready` remains `false`.

## Verification

Recommended checks after deploy:

1. `/dialogue/qa` remains `50/50 passed`.
2. `/tenant/creation/readiness?tenant_id=clinic_demo` returns stage `63` and status `ready` or non-blocking `attention`.
3. `/signup/ui` opens while logged in with the Stage 62 admin session.
4. Creating a test tenant produces a tenant_id, default services, default business memory, onboarding links, and dashboard/config links.
5. `/tenant/create` without admin session/token is blocked by Stage 61/62 access enforcement.

## Known limitations

- This is not final public SaaS auth.
- This does not add billing.
- This does not add tenant ownership records.
- This does not add Google Calendar OAuth self-serve hardening beyond existing links.
- This does not add CSRF/rate-limit protection for a public unauthenticated signup page.
