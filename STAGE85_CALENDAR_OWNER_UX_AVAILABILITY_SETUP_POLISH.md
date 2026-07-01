# Stage 85 — Calendar Owner UX / Availability Setup Polish

## Status

Implemented in archive. Awaiting Render deploy verification.

## Purpose

Continue the Mature SMB SaaS phase by adding an owner-safe calendar/availability workspace area. The owner can see calendar readiness and edit non-secret availability settings without entering admin config surfaces.

## Added owner-safe endpoints

- `GET /owner/calendar`
- `GET /owner/calendar/ui`
- `GET /owner/availability`
- `GET /owner/availability/ui`
- `POST /owner/availability/update`

## Added admin-protected readiness endpoints

- `GET /owner-calendar/readiness`
- `GET /calendar-owner/readiness`
- `GET /availability/readiness`
- `GET /workspace/calendar/readiness`

## Owner editable fields

Only these non-secret availability fields can be changed through Stage 85:

- `timezone`
- `work_start`
- `work_end`

`weekly_hours_json` is only synchronized from the start/end fallback if the column exists.

## Security boundaries

- Owner endpoints are protected by Stage 71 owner session and tenant binding.
- `POST /owner/availability/update` is protected by Stage 74 owner CSRF/browser-write hardening.
- Readiness endpoints are protected by Stage 61/62 admin auth.
- Owner UI does not expose Google access tokens, refresh tokens, service account JSON, credential material, admin OAuth links, or tenant config links.
- Google OAuth/calendar selection remain support-controlled in this stage.

## Not changed

- Receptionist dialogue
- Booking routing
- Slot generation
- Date/time parsing
- Price side-question logic
- Confirmation
- Cancellation/rescheduling
- Google Calendar event runtime
- Telegram webhook runtime
- Billing semantics
- Abuse/rate-limit semantics
- Magic-link semantics
- LLM orchestration
- Dialogue QA evaluator
- Voice/calls

## Verification checklist

- `/health`
- `/dialogue/qa` → expected `50/50 passed`
- `/owner-calendar/readiness?tenant_id=clinic_demo`
- `/calendar-owner/readiness?tenant_id=clinic_demo`
- `/availability/readiness?tenant_id=clinic_demo`
- `/workspace/calendar/readiness?tenant_id=clinic_demo`
- `/owner/calendar/ui?tenant_id=<owner_tenant>`
- `/owner/availability/ui?tenant_id=<owner_tenant>`
- Save availability through owner UI → expected `ok=true`
- `/tenant-workspace/readiness?tenant_id=clinic_demo` → Google Calendar next action should point to `/owner/calendar/ui`
- Owner dashboard/workspace/services/memory/billing remain OK

## Expected readiness fields

- `stage=85`
- `calendar_owner_ux_ready=true`
- `owner_calendar_setup_ready=true`
- `availability_setup_ready=true`
- `google_tokens_exposed=false`
- `admin_oauth_links_exposed_to_owner=false`
- `receptionist_calendar_runtime_changed=false`
- `enterprise_saas_ready=false`
