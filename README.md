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

## Stage 65 — Google Calendar OAuth Self-Serve

Stage 65 adds a protected Google Calendar self-serve readiness layer:

- `/google/self-serve/readiness?tenant_id=clinic_demo`
- `/google/calendar/self-serve/readiness?tenant_id=clinic_demo`
- `/calendar/self-serve/readiness?tenant_id=clinic_demo`

The Google setup flow is now part of the protected admin/session self-serve path: `/google/connect`, `/google/calendars`, `/google/calendars/ui`, and `POST /google/select_calendar` require Stage 61/62 admin auth. `/google/callback` remains available for the Google OAuth redirect.

## Stage 66 — Service Catalog Builder

Stage 66 adds a protected service catalog builder/readiness layer:

- `/service-catalog/builder?tenant_id=clinic_demo`
- `/tenant/service-catalog?tenant_id=clinic_demo`
- `/service-catalog/readiness?tenant_id=clinic_demo`
- `POST /tenant/service-catalog/update`

The builder lets the admin manage service names LV/RU/EN, duration, price, currency, aliases, and active/inactive state. Saving syncs service names into the tenant service fields and can sync a managed price block into business memory for FAQ/price side-questions. The flow remains protected by Stage 61/62 admin session/token and does not make Repliq public SaaS yet.

## Stage 67 — Business Memory / FAQ Builder

Stage 67 adds a protected self-serve editor for multilingual business memory, FAQ, and booking rules.

New protected surfaces:

- `/business-memory/builder?tenant_id=clinic_demo`
- `/tenant/business-memory?tenant_id=clinic_demo`
- `/business-memory/readiness?tenant_id=clinic_demo`
- `POST /tenant/business-memory/update`

The builder is intended for business facts such as address, working hours, cancellation rules, price clarifications, and FAQ lines. Runtime receptionist logic is unchanged; saved memory fields are consumed by the existing FAQ/side-question flow.


## CX-5 — Client Experience Readiness Lock

Admin-protected read-only aliases:

- `/client-experience/final-readiness`
- `/client-experience/readiness-lock`
- `/polished-client-launch/readiness`

CX-5 aggregates CX-1 through CX-4.1 and validates the final LV/RU/EN public/owner client-experience route, auth-boundary, responsive/accessibility/brand and public auth method contracts. It adds no write route or runtime behavior change. Expected protected regression after deploy: `/dialogue/qa = 50/50 passed`.
