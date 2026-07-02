# Stage 90 — Owner Notifications / Lead Follow-up Visibility

Status: implemented in archive, awaiting deploy verification.

## Scope

Stage 90 adds owner-safe, read-only visibility for conversations that may need manual owner review or lead follow-up.

Added owner endpoints:
- `GET /owner/notifications`
- `GET /owner/notifications/ui`
- `GET /owner/follow-ups`
- `GET /owner/follow-ups/ui`
- `GET /owner/lead-followup`
- `GET /owner/lead-followup/ui`

Added admin-protected readiness endpoints:
- `GET /owner-notifications/readiness`
- `GET /workspace/notifications/readiness`
- `GET /lead-follow-up/readiness`
- `GET /notifications/owner/readiness`

## Data model

Stage 90 uses existing runtime data only:
- `call_logs` for live interaction status/intent/message metadata.
- `conversations` for active conversation state visibility when the table is available.

Stage 90 does not create new tables, does not add runtime writes, and does not add a delivery queue.

## Follow-up visibility

The owner payload/UI exposes:
- follow-up candidate count;
- high/medium/low priority counts;
- inferred reasons such as busy/no-booking, need-more/recovery, reschedule-wait, failed booking/cancel, price question, and unresolved booking-like intent;
- observed channel visibility;
- active conversation state counts/items when available;
- recently resolved interactions;
- redacted/truncated snippets;
- stable hashed customer refs instead of raw IDs.

## Security

- Owner routes are protected by Stage 71 owner session + tenant binding.
- Readiness routes are protected by Stage 61/62 admin auth.
- No owner POST route was added.
- No Stage 74 owner browser-write/CSRF path was added because Stage 90 is read-only.
- No notification sends were added.
- No raw customer IDs or conversation `user_key` values are exposed.
- Message snippets are redacted/truncated.
- No secrets, raw tokens, Telegram credentials, Google credentials, CSRF values, magic-link tokens, billing secrets, or admin setup links are exposed to owner UI.
- `tenant_id` remains context only, not authentication.

## Non-goals / unchanged areas

Stage 90 does not change:
- receptionist dialogue runtime;
- booking routing;
- slot generation;
- date/time parsing;
- price side-question runtime;
- confirmation/cancel/reschedule runtime;
- Google Calendar runtime;
- Telegram runtime/webhook handling;
- SMS/WhatsApp send paths;
- billing semantics;
- auth/session semantics;
- CSRF semantics;
- abuse/rate-limit semantics;
- magic-link semantics;
- LLM orchestration;
- voice/calls;
- QA evaluator.

## Expected verification

- Render deploy starts successfully.
- `/dialogue/qa` remains `50/50 passed`.
- `/owner-notifications/readiness?tenant_id=clinic_demo` returns `stage=90` and `enterprise_saas_ready=false`.
- `/workspace/notifications/readiness?tenant_id=clinic_demo`, `/lead-follow-up/readiness?tenant_id=clinic_demo`, and `/notifications/owner/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/notifications/ui?tenant_id=clinic_demo`, `/owner/follow-ups/ui?tenant_id=clinic_demo`, and `/owner/lead-followup/ui?tenant_id=clinic_demo` open with valid owner session or super-admin bypass.
- Owner workspace/dashboard links include owner follow-up visibility links.
- Stage 89 analytics/insights UI remains OK.
- Stage 88 preview still returns `conversation_persisted=false`.
- Stage 78 remains the source of truth for public SaaS readiness; `enterprise_saas_ready=false` remains explicit.
