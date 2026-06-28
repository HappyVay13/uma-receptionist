# Stage 77 — Client-owner vs Super-admin Separation Hardening

## Purpose

Harden the boundary between client-owner surfaces and super-admin/admin surfaces before the final public SaaS readiness lock.

## Scope

Added:

- Stage 77 readiness endpoints:
  - `GET /owner-admin-separation/readiness`
  - `GET /client-owner/separation/readiness`
  - `GET /security/owner-admin-separation/readiness`
  - `GET /tenant/isolation/readiness`
- Explicit owner/admin/public/external webhook surface maps.
- Owner dashboard payload now returns Stage 77 separation metadata.
- Owner dashboard primary `links` block contains only owner-safe links.
- Super-admin support links are separated into `super_admin_support_links` and only returned when the request is opened through admin auth.
- Owner billing UI in owner mode shows only owner-safe navigation.
- Stage 69 Control Center integration.
- Stage 70 Public SaaS gap audit integration.

## Security behavior

- Client-owner surfaces remain protected by the Stage 71 signed owner session and tenant binding.
- Super-admin/admin surfaces remain protected by Stage 61/62 admin auth.
- `tenant_id` is explicitly not authentication.
- Owner UI does not expose admin config/write links.
- Super-admin support bypass remains explicit and marked.

## Not changed

- Booking routing
- Slot generation
- Date/time parsing
- Price side-question handling
- Confirmation/cancel/reschedule
- Google Calendar event runtime
- Telegram webhook runtime
- Billing semantics
- CSRF semantics
- Abuse/rate-limit semantics
- Dialogue QA evaluator
- LLM orchestration
- Voice/calls

## Verification

Expected after deploy:

- Render deploy live.
- `/dialogue/qa` = 50/50 passed.
- `/owner-admin-separation/readiness?tenant_id=clinic_demo` returns `stage=77` and `client_owner_superadmin_separation_ready=true`.
- `/tenant/isolation/readiness?tenant_id=clinic_demo` works.
- Owner dashboard opens for an owner session and does not show admin Control Center/Public SaaS audit links.
- Owner billing UI opens read-only for an owner session and does not show admin Control Center/Public SaaS audit links.
- Admin-only routes remain admin protected.
- `/public-saas/readiness?tenant_id=clinic_demo` includes Stage 77 and keeps `public_saas_ready=false`.
