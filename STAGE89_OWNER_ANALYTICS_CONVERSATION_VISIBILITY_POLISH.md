# Stage 89 — Owner Analytics / Conversation Visibility Polish

Status: implemented in archive, awaiting deploy verification.

## Scope

Stage 89 adds owner-safe, read-only conversation visibility for the Mature SMB SaaS owner workspace.

Added owner endpoints:
- `GET /owner/analytics`
- `GET /owner/analytics/ui`
- `GET /owner/conversation-insights`
- `GET /owner/conversation-insights/ui`

Added admin-protected readiness endpoints:
- `GET /owner-analytics/readiness`
- `GET /workspace/analytics/readiness`
- `GET /conversation-visibility/readiness`
- `GET /analytics/owner/readiness`

## Data model

Stage 89 uses existing runtime data only:
- `call_logs` for live interaction visibility.
- `usage_events` as optional summary metadata when the table exists.
- Stage 88 preview is explicitly reported as dry-run and not persisted.

Stage 89 does not create new tables and does not add runtime writes.

## Owner-safe visibility

The owner payload/UI exposes:
- live interaction totals for a selected window;
- unique customer count using stable hash refs instead of raw `user_id`;
- channel/status breakdown;
- customer question categories;
- service-interest visibility from `call_logs.service` or deterministic catalog text matching;
- price-question visibility;
- inferred answer-source visibility;
- recent interaction snippets with basic redaction/truncation;
- explicit limitations around preview persistence and inferred source metadata.

## Security

- Owner routes are protected by Stage 71 owner session + tenant binding.
- Readiness routes are protected by Stage 61/62 admin auth.
- No owner POST route was added.
- No Stage 74 owner browser-write/CSRF path was added because Stage 89 is read-only.
- Raw customer IDs are not exposed in owner payloads.
- Message snippets are redacted/truncated.
- No secrets, raw tokens, Telegram credentials, Google credentials, CSRF values, magic-link tokens, or admin setup links are exposed to owner UI.
- `tenant_id` remains context only, not authentication.

## Non-goals / unchanged areas

Stage 89 does not change:
- receptionist dialogue runtime;
- booking routing;
- slot generation;
- date/time parsing;
- price side-question runtime;
- confirmation/cancel/reschedule runtime;
- Google Calendar runtime;
- Telegram runtime;
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
- `/owner-analytics/readiness?tenant_id=clinic_demo` returns `stage=89` and `enterprise_saas_ready=false`.
- `/workspace/analytics/readiness?tenant_id=clinic_demo`, `/conversation-visibility/readiness?tenant_id=clinic_demo`, and `/analytics/owner/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/analytics/ui?tenant_id=clinic_demo` opens with valid owner session or super-admin bypass.
- `/owner/conversation-insights/ui?tenant_id=clinic_demo` opens with valid owner session or super-admin bypass.
- Owner workspace/dashboard links include conversation insights.
- Stage 88 preview still returns `conversation_persisted=false` and is not written to analytics history.
- Stage 78 remains the source of truth for public SaaS readiness; `enterprise_saas_ready=false` remains explicit.
