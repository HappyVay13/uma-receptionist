# Stage 93 — Public Signup → Owner Workspace End-to-End Polish

Status: implemented in archive, awaiting deploy verification.

## Goal

Close the UX handoff between the existing public signup flow and the authenticated owner workspace without changing tenant creation, auth-token, booking, Calendar, Telegram, billing/payment or receptionist runtime semantics.

## Factual starting point from the Stage 92 archive

- `POST /public/signup` already creates a tenant through the existing onboarding creation path.
- It already bootstraps an owner account, binds the owner to the new tenant and sets the signed Stage 71 owner session cookie.
- The successful signup UI previously opened the general owner dashboard directly.
- Stage 80 already provides owner workspace/setup completion data.
- Stage 92 already provides owner-safe setup health/data quality visibility.
- There was no dedicated post-signup owner onboarding handoff page.

## Added strict owner-only handoff routes

- `GET /owner/get-started`
- `GET /owner/get-started/ui`
- `GET /owner/welcome`
- `GET /owner/welcome/ui`

These routes are read-only and require a signed owner session bound to the requested tenant. Admin/super-admin sessions are not accepted for these pages.

The handoff shows:

- workspace completion summary from Stage 80;
- setup health summary from Stage 92;
- recommended owner-safe setup actions;
- links to workspace, setup health, launch review, client preview, account center and dashboard;
- no admin setup links or raw credentials.

## Added admin-protected readiness routes

- `GET /public-signup-workspace/readiness`
- `GET /signup-owner-workspace/readiness`
- `GET /owner-workspace/e2e/readiness`
- `GET /smb/onboarding/e2e/readiness`

Readiness checks wiring and boundaries only. It does not create a test tenant or submit public signup.

## Public signup polish

- Successful signup now returns `owner_get_started` as the primary owner handoff link.
- Existing owner workspace/dashboard/setup-health/launch-review/account/billing links remain available.
- `Continue setup` opens the strict owner-only get-started page while the owner session created by signup is active.
- One-time login code/magic-link compatibility remains unchanged in the API response; public and handoff UIs do not render the raw values in technical details.

## Security

- Owner handoff routes are Stage 71 owner-protected and strict owner-only.
- Readiness routes are Stage 61/62 admin-protected.
- No owner POST route and no new CSRF path.
- No admin links or readiness dependency snapshots in the owner handoff payload.
- No owner email, raw login code, login-code hash, magic token/hash, CSRF secret, admin token, Google credential, Telegram secret or billing-provider secret is exposed.
- `tenant_id` is not authentication.
- `enterprise_saas_ready=false` remains explicit.

## Not changed

- receptionist dialogue runtime
- booking/slots/date-time parsing
- price side-question behavior
- cancel/reschedule
- Google Calendar runtime
- Telegram runtime
- SMS/WhatsApp sends
- billing/payment semantics
- owner/admin credential semantics
- CSRF and abuse/rate-limit semantics
- magic-link semantics
- QA evaluator
- LLM orchestration
- voice/calls

## Expected post-deploy verification

- `/health` works.
- `/dialogue/qa` remains 50/50 passed.
- Stage 93 readiness endpoints return `stage=93` through admin login.
- `/public/signup` remains public.
- A successful test signup creates the tenant/owner session and `Continue setup` opens the new owner get-started page.
- Without owner login, and with admin login only, Stage 93 owner handoff pages return owner-session-required.
- With the valid owner session, get-started/welcome/workspace/setup-health/launch-review pages open without 500.
- `enterprise_saas_ready=false`.
