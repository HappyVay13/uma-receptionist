# Stage 72 — Public Signup Boundary / Owner Signup Flow Foundation

## Status

Implemented in archive. Pending deployment verification.

## Goal

Create a dedicated public signup boundary for SaaS onboarding without exposing the existing admin/demo tenant creation surfaces.

## Added endpoints

Public, not Stage 61 admin-token protected:

- `GET /public/signup`
- `GET /public/signup/ui`
- `POST /public/signup`
- `GET /public/signup/readiness`
- `GET /public/signup/boundary/readiness`
- `GET /signup/public/readiness`

Existing protected admin/demo routes are intentionally kept protected:

- `/signup`
- `/signup/ui`
- `/tenant/create`
- `/tenant/create/ui`
- `/onboarding/create_tenant`

## Runtime behavior

`POST /public/signup`:

1. Validates public signup is enabled.
2. Requires a real owner email.
3. Requires accepted terms.
4. Rejects honeypot-field submissions.
5. Applies public signup rate-limit checks.
6. Creates the tenant through the existing Stage 63 tenant creation flow.
7. Creates/updates the owner account through Stage 71.
8. Binds the owner to the new tenant.
9. Sets the signed owner session cookie.
10. Returns owner dashboard/onboarding links.
11. Returns the owner login code once for the foundation flow.

## Added table

`public_signup_events`

Purpose:

- record signup attempts;
- support hashed-IP hourly rate limits;
- support owner-email daily limits;
- avoid exposing raw IP hashes in responses.

## Security notes

- Admin token is not required for `/public/signup`.
- Admin token is not exposed.
- Owner login code hash is not exposed.
- Telegram token/secret are not exposed.
- Google service account JSON is not exposed.
- Existing admin tenant creation remains protected.
- Full public SaaS is still not ready because billing, CSRF, email verification/magic link, stronger abuse controls, and full client-owner/super-admin separation are still not complete.

## Integrations

- `/internal/readiness` now includes `public_signup_boundary_readiness`.
- Stage 70 public SaaS audit now detects Stage 72 and reports public signup boundary as `foundation` when ready.

## Not changed

- booking routing;
- slot generation;
- date/time parsing;
- price side-question logic;
- confirmation;
- cancel/reschedule;
- Google Calendar event runtime;
- Telegram webhook runtime;
- dialogue QA evaluator;
- voice/calls;
- LLM orchestration core.

## Expected deployment checks

1. `/dialogue/qa` returns `50/50 passed`.
2. `/public/signup/readiness?tenant_id=clinic_demo` returns `stage=72`.
3. `/public/signup` opens without admin session/token.
4. `/signup` and `/tenant/create` still require admin session/token.
5. Public signup creates a new test tenant and owner session.
6. New owner dashboard opens for the created tenant.
7. `/public-saas/readiness?tenant_id=clinic_demo` shows public signup boundary as foundation while `public_saas_ready=false` remains.
