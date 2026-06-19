# Stage 58 — Auth / Access Boundaries for Admin Surfaces

## Purpose

Stage 58 is a read-only security/access-boundary audit layer for the current text-first MVP admin/demo surfaces.

It does not enforce new authentication yet. Enforcing auth would be a separate behavior/ops stage because it can affect demo/dev endpoints, dashboard access, tenant setup flows, and regression execution.

## What was added

- `GET /access/readiness?tenant_id=...`
- `GET /admin/access/readiness?tenant_id=...` alias
- `access_boundaries_readiness` metadata in `/internal/readiness`
- `access_boundaries_readiness` metadata in `/tenant/config`
- `access_boundaries_readiness` metadata in `/tenant/config/update`
- Access readiness links in `/tenant/config/ui`
- Access readiness link in `/dashboard`

## What Stage 58 reports

- Current admin access model.
- Whether config API still hides secrets.
- Whether the tenant is private-demo ready.
- Whether public SaaS access boundaries are ready.
- Which surfaces are safe for private demo/internal pilot review.
- Which surfaces must not be exposed publicly yet.
- Required work before public SaaS admin/client access.

## Expected status

For the current state, `/access/readiness` is expected to return `status=attention`, not `ready`, because public SaaS auth/tenant ownership enforcement is not implemented yet.

This is intentional and factual:

- Private/demo readiness can be true.
- Public SaaS readiness should remain false until auth and tenant ownership guards are added.

## Current known access boundary facts

- `tenant_id` in a URL is not authentication.
- Admin/demo endpoints are still suitable only for controlled private demo/internal pilot use.
- `/tenant/config` and `/tenant/config/ui` should keep hiding service account JSON and private keys.
- Write/admin endpoints such as `/tenant/config/update`, `/tenant/change_plan`, `/tenants`, `/tenants/ui`, and dev endpoints should not be publicly exposed without auth.

## Scope guard

Stage 58 does not change:

- booking routing
- slot generation
- date/time parsing
- price side-questions
- confirmation flow
- cancellation
- reschedule
- Google Calendar create/update/delete runtime paths
- regression evaluator
- voice/call runtime

The active MVP remains text-first receptionist. Voice/calls remain future phase.

## Verification

Run after deploy:

- `/dialogue/qa` — expected `50/50 passed`
- `/internal/readiness?tenant_id=clinic_demo`
- `/access/readiness?tenant_id=clinic_demo`
- `/tenant/config?tenant_id=clinic_demo`
- `/tenant/config/ui?tenant_id=clinic_demo`
- `/dashboard?tenant_id=clinic_demo`

Expected:

- `/dialogue/qa = 50/50 passed`
- `/internal/readiness = ok`
- `access_boundaries_readiness.stage = 58`
- `/access/readiness.status = attention`
- `/access/readiness.private_demo_ready = true`
- `/access/readiness.public_saas_ready = false`
- `/tenant/config/ui` contains an Access readiness link
- `/dashboard` contains an access readiness link
