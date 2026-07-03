# Stage 90.1 — Notification Links 500 Guard Hotfix

Status: implemented in archive, awaiting deploy verification.

Reason:
- After Stage 90 deploy, user reported that notification/follow-up related links returned Internal Server Error.
- Local sandbox route registration and stubbed route smoke did not reproduce the 500 from the archive alone.
- Exact Render traceback was not available in chat at hotfix time.

Scope:
- Added narrow Stage 90.1 guard helpers around Stage 90 notification/follow-up visibility paths.
- Stage 90.1 returns an owner-safe empty/diagnostic payload instead of raising unhandled server exceptions from optional analytics/follow-up data access.
- Stage 90.1 keeps owner UI render path guarded so `/owner/notifications/ui`, `/owner/follow-ups/ui`, and `/owner/lead-followup/ui` should not return 500 because of tenant context/UI bootstrap exceptions.
- Stage 90.1 keeps readiness routes guarded so `/owner-notifications/readiness`, `/workspace/notifications/readiness`, `/lead-follow-up/readiness`, and `/notifications/owner/readiness` return a safe diagnostic payload instead of 500 if Stage 90 data collection fails.

No behavior expansion:
- No notification sends were added.
- No Telegram/SMS/WhatsApp/email/customer sends were added.
- No notification queue/background job was added.
- No new table or runtime write was added.
- No owner POST route was added.
- No Stage 74 CSRF path was added.

Security:
- Owner routes remain Stage 71 owner-session protected.
- Readiness routes remain Stage 61/62 admin protected.
- The fallback payload exposes only exception class names/reason codes, not secrets, raw SQL, tokens, stack traces, raw user IDs, or raw user keys.
- `enterprise_saas_ready=false` remains explicit.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` remains 50/50 passed.
- Notification/follow-up links no longer return Internal Server Error.
- `/owner-notifications/readiness?tenant_id=clinic_demo` returns JSON and does not 500.
- `/workspace/notifications/readiness?tenant_id=clinic_demo` returns JSON and does not 500.
- `/lead-follow-up/readiness?tenant_id=clinic_demo` returns JSON and does not 500.
- `/notifications/owner/readiness?tenant_id=clinic_demo` returns JSON and does not 500.
- `/owner/notifications/ui?tenant_id=clinic_demo` opens with valid owner session or super-admin bypass.
- `/owner/follow-ups/ui?tenant_id=clinic_demo` opens with valid owner session or super-admin bypass.
- `/owner/lead-followup/ui?tenant_id=clinic_demo` opens with valid owner session or super-admin bypass.
- Stage 89 analytics UI remains OK.
- Stage 88 preview remains dry-run and still returns `conversation_persisted=false`.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook/runtime, SMS/WhatsApp send paths, billing semantics, auth/session semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.
