# Stage 60 — Telegram Live Smoke Lock

## Purpose
Lock Telegram as the first external text channel for controlled pilot use after Stage 59.1 was verified in production.

## Factual trigger
The user reported that Stage 59.1 works: Telegram text flow is stable, RU flow no longer switches to LV after short replies, the old LV menu issue is resolved/disabled, and raw `business_memory_*` labels no longer leak.

## Scope
Read-only readiness/lock metadata and admin links only.

## Changes
- Added `stage60_telegram_live_smoke_lock_payload()`.
- Added endpoints:
  - `GET /telegram/live-smoke/readiness?tenant_id=...`
  - `GET /telegram/smoke/readiness?tenant_id=...`
  - `GET /channels/telegram/live-smoke/readiness?tenant_id=...`
- Added `telegram_live_smoke_lock` to `/internal/readiness`.
- Added `telegram_live_smoke_lock` to `/tenant/config` and `/tenant/config/update`.
- Added Telegram smoke lock links to `/tenant/config/ui` and `/dashboard`.

## Non-goals
- No receptionist core changes.
- No Telegram API calls from readiness.
- No webhook mutation from readiness.
- No LLM calls from readiness.
- No conversation or tenant mutation from readiness.
- No Google Calendar create/update/delete from readiness.
- No public SaaS security claim.

## Expected after deploy
- `/dialogue/qa = 50/50 passed`
- `/internal/readiness?tenant_id=clinic_demo` includes `telegram_live_smoke_lock.stage = 60`
- `/telegram/live-smoke/readiness?tenant_id=clinic_demo` returns `status = locked` if Telegram usage is visible in the selected window; otherwise `attention` with `telegram_activity_not_visible_in_usage_window`.
- `/tenant/config/ui` contains Telegram smoke lock link.
- `/dashboard` contains Telegram smoke lock link.

## Commit message
Stage 60: lock Telegram live smoke readiness
