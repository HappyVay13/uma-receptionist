# Stage 67 — Business Memory / FAQ Builder

## Purpose

Stage 67 adds a protected self-serve Business Memory / FAQ builder for the text-first Repliq receptionist.

This stage is an admin/self-serve configuration layer only. It does not change booking orchestration, slot generation, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, regression evaluator, or voice/call runtime.

## Added endpoints

Protected by Stage 61/62 admin session/token:

- `GET /business-memory/readiness?tenant_id=...`
- `GET /business-memory/builder/readiness?tenant_id=...`
- `GET /tenant/business-memory/readiness?tenant_id=...`
- `GET /faq/readiness?tenant_id=...`
- `GET /tenant/business-memory?tenant_id=...`
- `GET /business-memory/builder?tenant_id=...`
- `GET /business-memory/builder/ui?tenant_id=...`
- `GET /tenant/business-memory/builder?tenant_id=...`
- `POST /tenant/business-memory/update`
- `POST /business-memory/update`

## What the builder edits

The builder exposes multilingual text fields when they exist in the tenant schema:

- `business_memory_lv`, `business_memory_ru`, `business_memory_en`
- `faq_lv`, `faq_ru`, `faq_en`
- `booking_rules_lv`, `booking_rules_ru`, `booking_rules_en`
- optional generic fields such as `business_memory`, `faq`, `booking_rules`, `policies`

## Runtime behavior

The existing receptionist runtime already reads business memory / FAQ fields through the current tenant memory logic. Stage 67 only makes those fields easier to inspect and edit.

No new LLM routing, booking actions, calendar mutations, or Telegram behavior changes were introduced.

## Security

All builder/readiness/update routes are protected by the existing Stage 61/62 admin access layer. Public SaaS auth is still not considered complete.

`public_saas_ready` remains `false` until owner auth, tenant ownership checks, billing, CSRF/rate limits, and SaaS-grade account controls are implemented.

## Verification

Expected checks after deploy:

- `/dialogue/qa` remains `50/50 passed`
- `/business-memory/readiness?tenant_id=clinic_demo` returns `stage = 67`
- `/business-memory/builder?tenant_id=clinic_demo` opens through admin session
- `/tenant/business-memory?tenant_id=clinic_demo` returns editable memory fields
- `/tenant/business-memory/update` saves changes through admin session/token
- `/onboarding/wizard`, `/tenant/config/ui`, and `/dashboard` contain Business Memory links
- unauthenticated access to `/tenant/business-memory?tenant_id=clinic_demo` returns `401 admin_token_required`
