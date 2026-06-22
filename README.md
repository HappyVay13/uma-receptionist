# uma-receptionist
## Stage 62 — Admin Login / Session Layer

Stage 62 adds `/admin/login`, `/admin/logout`, `/admin/session`, and `/admin/session/readiness`. The existing `REPLIQ_ADMIN_TOKEN` is used as the MVP admin credential; successful browser login sets a signed HttpOnly session cookie so protected admin pages can be opened without repeatedly passing `admin_token` in URLs. This is still a private-admin/self-serve transition layer, not final public SaaS per-user auth.

## Stage 61 — Admin Access Enforcement

Stage 61 adds a minimal shared admin-token protection layer for internal/admin/demo surfaces. Set `REPLIQ_ADMIN_TOKEN` in the deployment environment before opening protected admin pages. Use `X-Repliq-Admin-Token` or `Authorization: Bearer <token>` for API checks; for browser checks open a protected page once with `?admin_token=<token>` to set the HttpOnly admin cookie. This is an MVP/private-admin access layer, not final public SaaS authentication.

## Stage 63 — Tenant Creation / Signup Flow Foundation

Protected self-serve foundation endpoints:

- `GET /signup/ui`
- `GET /tenant/create/ui`
- `POST /tenant/create`
- `GET /tenant/creation/readiness?tenant_id=clinic_demo`

Tenant creation is protected by the Stage 61/62 admin token/session layer. This stage prepares the SaaS tenant creation flow but does not yet make Repliq public self-serve SaaS.

## Stage 64 — Self-Serve Onboarding Wizard

Stage 64 adds a protected self-serve onboarding wizard:

- `/onboarding/wizard?tenant_id=clinic_demo`
- `/onboarding/wizard/readiness?tenant_id=clinic_demo`
- `/self-serve/onboarding/readiness?tenant_id=clinic_demo`

The wizard is part of the self-serve SaaS path and summarizes business profile, services, prices, business memory/FAQ, Google Calendar, Telegram, and final smoke-lock readiness. It remains protected by the Stage 61/62 admin session/token layer.
