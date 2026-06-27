# Stage 76 — Email Verification / Magic Link Auth Foundation

Status: implemented in archive, awaiting deploy verification.

## Scope

Stage 76 adds owner email verification and one-time magic-link auth foundation for public self-service SaaS.

Added:

- `owner_magic_links` table for one-time magic-link tokens.
- Safe token storage: only HMAC token hashes are stored; raw tokens are returned once.
- `owner_accounts.email_verified_at` column via safe `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
- Admin-protected magic-link bootstrap endpoint.
- Public owner magic-login endpoint.
- Public signup integration: signup still returns the legacy setup code, but also returns a one-time magic link/token for Stage 76 foundation.
- Owner session integration: successful magic login sets the existing HttpOnly `repliq_owner_session` cookie.
- Email/readiness endpoints.
- Control Center integration.
- Public SaaS audit integration.

## New endpoints

Admin-protected readiness:

- `GET /email/readiness`
- `GET /email-verification/readiness`
- `GET /magic-link/readiness`
- `GET /owner/magic-link/readiness`

Admin-protected write:

- `POST /owner/magic-link/bootstrap`

Public owner auth:

- `GET /owner/magic-login`
- `POST /owner/magic-login`

## Security model

- Magic tokens are one-time tokens.
- Magic tokens expire after a short TTL.
- Raw magic tokens are not stored.
- Token hashes are not exposed in readiness or UI outputs.
- Successful magic login marks `email_verified_at` and sets the existing owner session cookie.
- Legacy Stage 71 setup-code login remains supported for compatibility.
- Admin magic-link bootstrap is behind Stage 61/62 admin auth and Stage 74 browser-write hardening.
- Public magic login is not admin protected because it is the public auth entry point.

## Email delivery note

Stage 76 does not send real outbound email by itself. It creates the magic-link/auth foundation and returns the link/token once. If an email provider is configured later, outbound delivery can be added without changing the receptionist runtime.

Readiness may warn:

- `email_delivery_provider_not_configured_foundation_returns_link_once`
- `magic_link_secret_uses_owner_session_secret_fallback`

These warnings are acceptable for Stage 76 foundation. They are not dialogue/runtime blockers.

## Expected verification after deploy

- Render deploy starts successfully.
- `/dialogue/qa` = `50/50 passed`.
- `/email/readiness?tenant_id=clinic_demo` returns `stage=76`.
- `/magic-link/readiness?tenant_id=clinic_demo` works.
- `/owner/magic-link/bootstrap` creates a one-time magic link for a bound owner.
- `/owner/magic-login?token=...` or `POST /owner/magic-login` logs the owner in and sets owner session.
- `/owner/session?tenant_id=<tenant>` shows `authenticated=true` and email verification metadata after magic login.
- `/public/signup` still works and returns owner login code plus magic-link foundation fields.
- `/public-saas/readiness?tenant_id=clinic_demo` includes email/magic-link readiness while `public_saas_ready=false` remains.

## Not changed

Receptionist core was not changed:

- booking routing
- slot generation
- date/time parsing
- price side-question logic
- confirmation
- cancel/reschedule
- Google Calendar event runtime
- Telegram webhook runtime
- billing semantics
- CSRF semantics
- dialogue QA evaluator
- LLM orchestration
- voice/calls
