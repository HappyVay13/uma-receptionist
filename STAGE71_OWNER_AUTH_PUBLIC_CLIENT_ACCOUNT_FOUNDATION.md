# Stage 71 — Owner Auth / Public Client Account Foundation

Status: implemented, pending deployment verification.

## Purpose

Stage 71 starts closing the Stage 70 public SaaS blocker around owner auth and tenant ownership.

This stage is a foundation layer only. It does not make `public_saas_ready=true`.

## What was added

- Separate signed owner session cookie: `repliq_owner_session`.
- Owner account storage foundation:
  - `owner_accounts`
  - `owner_tenant_access`
- Owner-to-tenant binding model.
- Protected admin bootstrap endpoint for issuing an owner login/setup code.
- Public owner login page using owner email + setup code.
- Owner-safe read-only dashboard surface.
- Owner auth readiness payload.
- Stage 70 gap audit integration so owner auth appears as foundation rather than missing.

## New endpoints

Admin/session protected:

- `GET /owner/auth/readiness?tenant_id=clinic_demo`
- `GET /owner/readiness?tenant_id=clinic_demo`
- `GET /tenant/owner/readiness?tenant_id=clinic_demo`
- `GET /owner/accounts?tenant_id=clinic_demo`
- `POST /owner/accounts/bootstrap`
- `POST /tenant/owner/bind`

Public owner auth/session:

- `GET /owner/login?tenant_id=clinic_demo`
- `POST /owner/login`
- `GET /owner/logout`
- `POST /owner/logout`
- `GET /owner/session?tenant_id=clinic_demo`

Owner-session protected:

- `GET /owner/dashboard?tenant_id=clinic_demo`
- `GET /owner/dashboard/ui?tenant_id=clinic_demo`
- `GET /owner/control-center?tenant_id=clinic_demo`
- `GET /owner/control-center/ui?tenant_id=clinic_demo`

## Security notes

- Owner login/setup codes are never returned by readiness endpoints.
- Login code hashes are not exposed.
- The setup code is returned only by the protected admin endpoint `/owner/accounts/bootstrap`.
- Existing admin write/config surfaces remain protected by Stage 61/62 admin access.
- Owner dashboard is read-only in Stage 71.
- Super-admin/admin session can open owner surfaces for support/private demo.
- `public_saas_ready` remains `false`.

## Not changed

- booking routing
- slot generation
- date/time parsing
- price side-question logic
- confirmation
- cancel
- reschedule
- Google Calendar event runtime
- Telegram webhook runtime
- dialogue QA evaluator
- voice/calls
- LLM orchestration core

## Post-deploy checks

1. `/dialogue/qa` should remain `50/50 passed`.
2. `/owner/auth/readiness?tenant_id=clinic_demo` should return `stage=71`.
3. `/owner/accounts/bootstrap` should create/bind an owner and return a login code only once in the protected response.
4. `/owner/login?tenant_id=clinic_demo` should create an owner session with the generated code.
5. `/owner/dashboard/ui?tenant_id=clinic_demo` should open after owner login.
6. `/owner/dashboard/ui?tenant_id=clinic_demo` without owner/admin session should return owner login required.
7. `/public-saas/readiness?tenant_id=clinic_demo` should still return `public_saas_ready=false`.
