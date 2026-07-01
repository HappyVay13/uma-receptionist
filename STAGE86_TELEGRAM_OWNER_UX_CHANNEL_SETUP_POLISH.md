# Stage 86 — Telegram Owner UX / Channel Setup Polish

## Status

Implemented in archive. Awaiting Render deploy verification.

## Purpose

Continue the Mature SMB SaaS phase by adding an owner-safe Telegram channel workspace area. The owner can see Telegram channel readiness, webhook metadata status, and next actions without entering admin Telegram setup screens or seeing secrets.

## Added owner-safe endpoints

- `GET /owner/telegram`
- `GET /owner/telegram/ui`
- `GET /owner/channels/telegram`
- `GET /owner/channels/telegram/ui`

## Added admin-protected readiness endpoints

- `GET /owner-telegram/readiness`
- `GET /telegram-owner/readiness`
- `GET /workspace/telegram/readiness`
- `GET /channels/telegram/owner/readiness`

## Owner editable fields

None. Stage 86 is read-only for owner clients.

Telegram bot token, webhook secret and webhook setting remain support-controlled in this SMB phase.

## Security boundaries

- Owner endpoints are protected by Stage 71 owner session and tenant binding.
- Readiness endpoints are protected by Stage 61/62 admin auth.
- No new owner write endpoint was added, so no new Stage 74 owner CSRF path is required.
- Owner UI does not expose raw bot token, webhook secret, masked token values, admin Telegram setup links, or webhook setup write actions.
- Super-admin support links are returned only when opened through explicit admin/session bypass.

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
- Telegram incoming-message handling
- Telegram send-message handling
- Billing semantics
- CSRF semantics
- Abuse/rate-limit semantics
- Magic-link semantics
- LLM orchestration
- Dialogue QA evaluator
- Voice/calls

## Verification checklist

- `/health`
- `/dialogue/qa` → expected `50/50 passed`
- `/owner-telegram/readiness?tenant_id=clinic_demo`
- `/telegram-owner/readiness?tenant_id=clinic_demo`
- `/workspace/telegram/readiness?tenant_id=clinic_demo`
- `/channels/telegram/owner/readiness?tenant_id=clinic_demo`
- `/owner/telegram/ui?tenant_id=<owner_tenant>`
- `/owner/channels/telegram/ui?tenant_id=<owner_tenant>`
- `/owner/telegram?tenant_id=<owner_tenant>`
- `/tenant-workspace/readiness?tenant_id=clinic_demo` → Telegram next action should point to `/owner/telegram/ui`
- Owner dashboard/workspace/services/memory/calendar/billing remain OK

## Expected readiness fields

- `stage=86`
- `telegram_owner_ux_ready=true`
- `owner_telegram_setup_ready=true`
- `owner_visible_channel_status=true`
- `raw_telegram_bot_token_exposed=false`
- `raw_telegram_webhook_secret_exposed=false`
- `masked_token_exposed_to_owner=false`
- `admin_telegram_setup_links_exposed_to_owner=false`
- `telegram_webhook_runtime_changed=false`
- `enterprise_saas_ready=false`
