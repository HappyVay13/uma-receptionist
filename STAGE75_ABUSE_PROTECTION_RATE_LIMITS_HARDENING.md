# Stage 75 — Abuse Protection / Rate Limits Hardening Foundation

Status: implemented in archive, awaiting deploy verification.

## Scope

Stage 75 adds a production-oriented abuse/rate-limit foundation for public self-serve surfaces without changing receptionist core behavior.

Added:

- Central `abuse_events` ledger table with safe HMAC-hashed IP/subject metadata.
- Rate-limit gates for:
  - `POST /admin/login`
  - `POST /owner/login`
  - `POST /public/signup`
  - `GET /csrf/token?scope=public`
- Stage 75 readiness endpoints:
  - `GET /abuse/readiness`
  - `GET /security/abuse/readiness`
  - `GET /rate-limits/readiness`
  - `GET /abuse-protection/readiness`
- Control Center integration.
- Public SaaS gap audit integration.
- Safe event counts by bucket without exposing raw IPs, subject hashes, admin tokens, or owner login codes.

## Runtime policy

Default foundation limits:

- Admin login: IP hourly limit, default `30`.
- Owner login: IP hourly limit, default `30`; owner/tenant subject hourly limit, default `10`.
- Public signup: Stage 72 specific limits remain active; Stage 75 adds shared abuse ledger limits, default IP hourly `10`, subject daily `5`.
- Public CSRF token issuance: IP hourly limit, default `120`.

Environment overrides:

- `REPLIQ_ABUSE_PROTECTION_ENABLED`
- `REPLIQ_ABUSE_PROTECTION_FAIL_OPEN`
- `REPLIQ_ABUSE_PROTECTION_SECRET`
- `REPLIQ_ADMIN_LOGIN_IP_HOURLY_LIMIT`
- `REPLIQ_OWNER_LOGIN_IP_HOURLY_LIMIT`
- `REPLIQ_OWNER_LOGIN_SUBJECT_HOURLY_LIMIT`
- `REPLIQ_PUBLIC_SIGNUP_ABUSE_IP_HOURLY_LIMIT`
- `REPLIQ_PUBLIC_SIGNUP_ABUSE_SUBJECT_DAILY_LIMIT`
- `REPLIQ_PUBLIC_CSRF_TOKEN_IP_HOURLY_LIMIT`

`REPLIQ_ABUSE_PROTECTION_FAIL_OPEN` defaults to enabled for the foundation stage, so a temporary storage issue does not take down admin/owner access. Readiness reports this as a warning.

## Security boundaries

Stage 75 does not expose:

- raw IP addresses;
- subject hashes;
- admin token values;
- owner login code values;
- owner login code hashes;
- session secrets;
- CSRF secrets.

External channel webhooks are intentionally not placed behind Stage 75 blocking in this stage:

- `/telegram/webhook`
- `/sms/incoming`
- `/whatsapp/incoming`
- `/voice/incoming`
- `/voice/language`
- `/voice/intent`

## Public SaaS status

`public_saas_ready` remains `false` after Stage 75.

Remaining blockers:

- email verification / magic-link auth;
- client-owner vs super-admin separation hardening;
- final public SaaS readiness lock.

## Not touched

Stage 75 does not change:

- booking routing;
- slot generation;
- date/time parsing;
- price side-question logic;
- confirmation;
- cancel/reschedule;
- Google Calendar event runtime;
- Telegram webhook runtime;
- billing semantics;
- dialogue QA evaluator;
- LLM orchestration;
- voice/calls.

## Expected deploy verification

- Render deploy starts successfully.
- `/dialogue/qa` = `50/50 passed`.
- `/abuse/readiness?tenant_id=clinic_demo` works and returns `stage=75`.
- `/security/abuse/readiness?tenant_id=clinic_demo` works and is admin protected.
- `/rate-limits/readiness?tenant_id=clinic_demo` works.
- `/control-center/ui?tenant_id=clinic_demo` includes Abuse / rate limits.
- `/public-saas/readiness?tenant_id=clinic_demo` includes `abuse_rate_limits` and `public_rate_limits_integrated=true` while `public_saas_ready=false` remains.
- Admin login still works.
- Owner login still works.
- Public signup still works from the same-origin UI.
