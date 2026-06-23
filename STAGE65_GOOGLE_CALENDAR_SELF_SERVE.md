# Stage 65 — Google Calendar OAuth Self-Serve

## Scope

Stage 65 hardens the Google Calendar self-serve setup path for the SaaS transition. It is focused on connection/readiness and protected setup UX, not receptionist dialogue logic.

## Added / updated endpoints

- `GET /google/self-serve/readiness?tenant_id=...`
- `GET /google/calendar/self-serve/readiness?tenant_id=...`
- `GET /calendar/self-serve/readiness?tenant_id=...`
- `GET /google/connect?tenant_id=...` is now protected by Stage 61/62 admin session/token.
- `GET /google/calendars?tenant_id=...` is now protected by Stage 61/62 admin session/token.
- `GET /google/calendars/ui?tenant_id=...` is now protected by Stage 61/62 admin session/token.
- `POST /google/select_calendar` is now protected by Stage 61/62 admin session/token.

`/google/callback` remains available for the Google OAuth redirect and is not protected by the shared admin-token middleware.

## Readiness gates

The Stage 65 readiness payload checks:

- tenant exists;
- Stage 61 admin token is configured;
- Stage 62 admin session secret is available;
- Google OAuth env is configured;
- `tenant_google_accounts` table is present;
- Google setup paths are protected;
- Google account is connected;
- a working calendar has been selected.

## Non-goals

Stage 65 does not:

- change booking routing;
- change slot generation;
- change date/time parsing;
- change price side-question logic;
- change cancellation or reschedule flows;
- change Google Calendar event create/update/delete runtime;
- change Telegram webhook handling;
- change dialogue QA evaluator;
- add billing;
- add final public SaaS owner auth or tenant ownership checks.

## Expected baseline

- `/dialogue/qa` must remain `50/50 passed`.
- Existing Stage 64 onboarding wizard must still work.
- `public_saas_ready` remains `false` until owner auth, tenant ownership, billing, CSRF, and rate-limit stages exist.
