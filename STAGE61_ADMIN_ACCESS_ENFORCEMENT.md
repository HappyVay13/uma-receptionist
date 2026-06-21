# Stage 61 — Admin Access Enforcement

## Purpose

Stage 61 adds a minimal shared-admin-token access layer for internal/admin/demo surfaces as the next step from private demo toward self-serve SaaS readiness.

This stage does not implement full public SaaS authentication. Public SaaS still requires per-user login/session handling, tenant ownership checks, role separation, and browser write hardening.

## What changed

- Added Stage 61 admin access middleware.
- Protected admin/internal/demo surfaces with a shared admin token when `REPLIQ_ADMIN_ACCESS_ENFORCEMENT` is enabled.
- Enforcement is enabled by default.
- The admin token is read from `REPLIQ_ADMIN_TOKEN`, `ADMIN_ACCESS_TOKEN`, or `ADMIN_TOKEN`.
- Accepted auth forms:
  - `X-Repliq-Admin-Token: <token>`
  - `Authorization: Bearer <token>`
  - `?admin_token=<token>` for first browser entry
  - `repliq_admin_token` HttpOnly cookie set after a valid query-token entry
- Added `GET /admin/access/enforcement/readiness?tenant_id=...` and alias `GET /admin/access/enforcement?tenant_id=...`.
- `/internal/readiness`, `/tenant/config`, and `/tenant/config/update` now include `admin_access_enforcement` metadata.
- `/tenant/config/ui` and `/dashboard` now link to Admin access enforcement readiness.

## Protected surfaces

Stage 61 protects the current admin/demo/readiness surfaces including:

- `/tenant/config/ui`
- `/tenant/config`
- `/tenant/config/update`
- `/tenant/admin/readiness`
- `/internal/readiness`
- `/launch/readiness`
- `/pilot/setup/readiness`
- `/business-memory/readiness`
- `/usage/readiness`
- `/access/readiness`
- `/telegram/readiness`
- `/telegram/live-smoke/readiness`
- `/telegram/status`
- `/telegram/set-webhook`
- `/dashboard`
- `/analytics`
- `/usage`
- `/bookings`
- `/conversations`
- `/activity`
- `/tenants`
- `/tenants/ui`
- `/dev_chat`
- `/dev_chat_ui`
- `/onboarding/ui`
- `/onboarding/status`

## Not protected by this stage

- `/dialogue/qa` remains available for production regression checks.
- `/telegram/webhook` remains available for Telegram because it uses Telegram webhook secret validation.
- `/google/callback` remains available for the OAuth redirect flow.
- `/health` remains available for platform health checks.

## Safety rules

Stage 61 must not change receptionist behavior:

- booking routing
- slot generation
- date/time parsing
- price side-questions
- confirmation flow
- cancellation
- reschedule
- Google Calendar create/update/delete runtime
- regression evaluator
- Telegram webhook handling

## Deployment note

Before deploying Stage 61, set `REPLIQ_ADMIN_TOKEN` in Render to a long random value. Do not paste the token into chat logs or screenshots.

Browser check pattern:

```text
/tenant/config/ui?tenant_id=clinic_demo&admin_token=<token>
```

The server will set an HttpOnly cookie for subsequent admin UI fetches.

API check pattern:

```text
curl -H "X-Repliq-Admin-Token: <token>" "https://uma-receptionist.onrender.com/internal/readiness?tenant_id=clinic_demo"
```

## Expected checks

- `/dialogue/qa = 50/50 passed`
- protected admin endpoints without token return `401 admin_token_required`
- protected admin endpoints with token work
- `/internal/readiness` includes `admin_access_enforcement.stage = 61`
- `admin_access_enforcement.admin_access_enforced = true`
- `admin_access_enforcement.private_demo_ready = true`
- `admin_access_enforcement.public_saas_ready = false`

