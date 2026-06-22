# Stage 64 — Self-Serve Onboarding Wizard

## Scope

Stage 64 adds a protected self-serve onboarding wizard/checklist for tenants that already exist after Stage 63 tenant creation.

This stage is intentionally a UI/readiness layer. It does not change the receptionist core, dialogue routing, booking, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, or the regression evaluator.

## Added endpoints

- `GET /onboarding/wizard?tenant_id=<tenant_id>`
- `GET /onboarding/wizard/ui?tenant_id=<tenant_id>`
- `GET /onboarding/wizard/readiness?tenant_id=<tenant_id>`
- `GET /onboarding/checklist/readiness?tenant_id=<tenant_id>`
- `GET /self-serve/onboarding/readiness?tenant_id=<tenant_id>`

All Stage 64 endpoints are protected by the Stage 61/62 admin session/token layer.

## Wizard checklist

The wizard exposes these onboarding steps:

1. Business profile
2. Services
3. Prices / FAQ price facts
4. Business memory / FAQ
5. Google Calendar connection
6. Working calendar selection
7. Telegram text channel
8. Final text smoke lock

## Readiness payload

`stage64_onboarding_wizard_readiness_payload()` returns:

- `stage = 64`
- `status`
- `onboarding_wizard_ready`
- `onboarding_wizard_complete`
- `self_serve_onboarding_ready`
- `step_count`
- `complete_step_count`
- per-step completion data
- quick links for the wizard, tenant config, dashboard, Google Calendar, Telegram readiness, and Telegram smoke lock

## Integration points

Stage 64 is included in:

- `/internal/readiness`
- `/tenant/config`
- `/tenant/config/update` response
- `/tenant/config/ui` links
- `/dashboard` links and toolbar
- `onboarding_links_payload()`

## Public SaaS status

`public_saas_ready` remains `false`.

The wizard is a required self-serve SaaS building block, but public launch still requires per-owner auth, tenant ownership enforcement, billing/subscription lifecycle, CSRF/rate limiting for browser write endpoints, and production owner login delivery.
