# Stage 74 — CSRF / Browser Write Hardening Foundation

## Status

Implemented in archive. Awaiting deploy verification.

## Goal

Close the browser-write hardening blocker from the public SaaS audit without changing receptionist core behavior.

Stage 74 adds a foundation CSRF/browser-write layer around cookie-authenticated admin and owner writes. It protects against cross-site browser writes that rely on signed session cookies while preserving same-origin UI flows and explicit admin-token automation.

## Added

- Same-origin Fetch Metadata / Origin / Referer checks for browser write requests.
- Signed CSRF token support via `X-Repliq-CSRF-Token`.
- CSRF token endpoint:
  - `GET /csrf/token`
- Admin-protected readiness aliases:
  - `GET /csrf/readiness`
  - `GET /security/csrf/readiness`
  - `GET /browser-write/readiness`
  - `GET /browser-write-hardening/readiness`
- Public signup cross-site browser POST blocking.
- Public SaaS audit integration.
- Control Center integration.

## Hardened browser write paths

Admin/session browser writes:

- `/owner/accounts/bootstrap`
- `/tenant/owner/bind`
- `/google/select_calendar`
- `/tenant/billing/update`
- `/tenant/business-memory/update`
- `/business-memory/update`
- `/telegram/setup/update`
- `/telegram/setup/set-webhook`
- `/telegram/set-webhook`
- `/onboarding/finish`
- `/onboarding/create_tenant`
- `/tenant/create`
- `/tenant/change_plan`
- `/tenant/service-catalog/update`
- `/service-catalog/update`
- `/tenant/config/update`
- selected dev write/test helper endpoints behind admin boundary

Owner/session browser writes:

- `/owner/logout`

Public browser writes:

- `/public/signup`

External webhook writes intentionally excluded:

- `/voice/incoming`
- `/voice/language`
- `/voice/intent`
- `/sms/incoming`
- `/whatsapp/incoming`
- `/telegram/webhook`

## Security behavior

Accepted for protected browser writes:

1. Same-origin browser metadata (`Sec-Fetch-Site: same-origin` or `none`).
2. Matching same-origin `Origin` or `Referer` fallback.
3. Valid signed CSRF token in `X-Repliq-CSRF-Token`.
4. Explicit admin token header/bearer/query for admin API automation.

Rejected:

- Cross-site browser writes relying only on admin/owner session cookies.
- Invalid or expired signed CSRF tokens.
- Invalid CSRF scope.

## Not changed

- Booking routing.
- Slot generation.
- Date/time parsing.
- Side-question handling.
- Confirmation.
- Cancellation/rescheduling.
- Google Calendar event runtime.
- Telegram webhook runtime.
- Billing semantics.
- Dialogue QA evaluator.
- LLM orchestration.
- Voice/calls.

## Expected deploy verification

- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/csrf/readiness?tenant_id=clinic_demo` returns `stage=74` and `csrf_browser_write_hardening_ready=true`.
- `/security/csrf/readiness?tenant_id=clinic_demo` works and is admin protected.
- `/csrf/token?scope=admin&tenant_id=clinic_demo` returns a token only when admin-authenticated and does not expose raw secrets.
- Existing same-origin admin UI writes still work.
- `/public/signup` still works from the public same-origin signup UI.
- `/public-saas/readiness?tenant_id=clinic_demo` includes Stage 74 readiness and keeps `public_saas_ready=false`.

## Remaining public SaaS blockers

- Stage 75 — Abuse Protection / Rate Limits Hardening.
- Stage 76 — Email Verification / Magic Link Auth Foundation.
- Stage 77 — Client-owner vs Super-admin Separation Hardening.
