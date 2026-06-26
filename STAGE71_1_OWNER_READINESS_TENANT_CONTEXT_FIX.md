# Stage 71.1 — Owner Readiness / Tenant Context Fix

## Status
Implemented in archive, awaiting deploy verification.

## Goal
Close the Stage 71 follow-up issues found during live verification:

1. `tenant_owner_email_missing` remained visible even though owner bootstrap/login/dashboard worked.
2. Several owner/admin/self-serve UI surfaces could fall back to `default` even when the test tenant is `clinic_demo`.

## Implemented changes

### Owner readiness fix
- Added safe tenant schema migration:
  - `owner_email TEXT`
- `POST /owner/accounts/bootstrap` now syncs the bootstrapped owner email into the tenant profile if the tenant owner email is empty.
- `POST /tenant/owner/bind` also syncs owner email into tenant profile if empty.
- `/owner/auth/readiness` now resolves owner readiness through active `owner_tenant_access` rows when `tenant.owner_email` is missing.
- Readiness exposes:
  - `tenant.owner_email`
  - `tenant.effective_owner_email`
  - `tenant.owner_email_source`
- Login code value and hash remain hidden.

### Tenant config UI fix
- Added editable Owner email field to `/tenant/config/ui`.
- `POST /tenant/config/update` accepts and validates `owner_email`.
- Secrets remain masked/hidden.

### Tenant context fix
Added Stage 71.1 tenant-context resolver for UI/admin/owner surfaces. Priority:

1. explicit `?tenant_id=...` query param;
2. explicit non-default function argument;
3. owner session tenant;
4. admin session tenant;
5. env private-demo defaults: `REPLIQ_UI_DEFAULT_TENANT_ID`, `REPLIQ_PRIVATE_DEMO_TENANT_ID`, `TEST_TENANT_ID`, `TELEGRAM_DEFAULT_TENANT_ID`;
6. existing `clinic_demo` private-demo tenant when `TENANT_ID_DEFAULT=default`;
7. original `TENANT_ID_DEFAULT` fallback.

Applied to:
- admin login/session redirect context;
- owner readiness/accounts/bootstrap/bind/login/session/dashboard context;
- tenant config JSON/UI context;
- control center JSON/UI/readiness context;
- public SaaS audit JSON/UI context;
- dashboard JSON/UI context.

## Not changed
- booking routing;
- slot generation;
- date/time parsing;
- price side-question logic;
- confirmation;
- cancel;
- reschedule;
- Google Calendar event runtime;
- Telegram webhook runtime;
- dialogue QA evaluator;
- voice/calls;
- LLM orchestration core.

## Expected post-deploy checks

1. `/dialogue/qa` returns `50/50 passed`.
2. `/owner/auth/readiness?tenant_id=clinic_demo`:
   - `stage = 71.1`
   - `owner_auth_foundation_ready = true`
   - `tenant_ownership_binding_ready = true`
   - no `tenant_owner_email_missing` warning after bootstrap/bind or owner_email save.
3. `/tenant/config/ui?tenant_id=clinic_demo`:
   - Owner email field is visible;
   - save works;
   - secrets are still not exposed.
4. `/owner/dashboard/ui?tenant_id=clinic_demo` opens after owner session.
5. `/control-center/ui?tenant_id=clinic_demo`, `/dashboard?tenant_id=clinic_demo`, `/public-saas/gap-audit/ui?tenant_id=clinic_demo` preserve `clinic_demo` context.
6. `public_saas_ready` remains `false`.
