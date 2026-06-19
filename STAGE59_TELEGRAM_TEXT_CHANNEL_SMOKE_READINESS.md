# Stage 59 — Telegram Text Channel Smoke Readiness

## Scope
Stage 59 adds a read-only readiness/smoke layer for the Telegram text channel after Stage 58 access boundary audit.

The active MVP remains text-first receptionist behavior. Voice/calls remain future scope.

## What changed
- Added `GET /telegram/readiness?tenant_id=...`.
- Added alias `GET /channels/telegram/readiness?tenant_id=...`.
- Added `telegram_text_channel_readiness` metadata to `/internal/readiness`.
- Added `telegram_text_channel_readiness` metadata to `/tenant/config` and `/tenant/config/update` responses.
- Added Telegram readiness links to `/tenant/config/ui` and `/dashboard`.
- Kept existing Telegram runtime endpoints unchanged:
  - `GET /telegram/status`
  - `POST /telegram/set-webhook`
  - `POST /telegram/webhook`

## What the readiness endpoint checks
- Tenant exists and is runtime-ready.
- Telegram bot token is configured as a boolean flag only.
- Telegram webhook secret is configured as a boolean flag only.
- Recommended tenant-specific webhook URL.
- Existing channel routes.
- Usage/call-log visibility for Telegram channel activity.
- Manual Telegram smoke script for RU/LV booking, price side-question, reschedule, and cancel.

## Safety
The Stage 59 readiness endpoint is read-only:
- It does not call Telegram APIs.
- It does not set or change webhooks.
- It does not call LLMs.
- It does not mutate tenant config.
- It does not mutate conversations.
- It does not create, update, or delete Google Calendar events.
- It does not expose Telegram bot token or webhook secret values.

## Expected production result
After deploy:
- `/dialogue/qa` remains `50/50 passed`.
- `/internal/readiness?tenant_id=clinic_demo` includes `telegram_text_channel_readiness.stage = 59`.
- `/telegram/readiness?tenant_id=clinic_demo` returns `status = ready`, `attention`, or `blocked` depending on actual environment config.
- If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_WEBHOOK_SECRET` is missing, the endpoint should report `attention` with explicit warnings, not pretend Telegram is ready.
- `/tenant/config/ui` contains Telegram readiness link.
- `/dashboard` contains Telegram readiness link.

## Manual smoke checklist
1. Open `/telegram/status`.
2. Confirm `has_bot_token=true` and `has_webhook_secret=true` before pilot smoke.
3. Set webhook with `POST /telegram/set-webhook?tenant_id=clinic_demo`.
4. Open the Telegram bot and send `/start`.
5. Run booking → price side-question → slot confirmation → reschedule → cancel.
6. Verify Google Calendar: one event after booking, same event after reschedule, no event after cancel.

## Non-goals
- No Telegram UX rewrite.
- No auth enforcement.
- No voice/call behavior.
- No changes to booking/cancel/reschedule runtime logic.
- No changes to regression evaluator.
