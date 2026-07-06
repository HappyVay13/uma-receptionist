# Stage 95.1 — Analytics / Follow-up Data Source Compatibility Hotfix

Status: implemented in archive, awaiting deploy verification.

## Production evidence

After Stage 95 deploy, `/mature-smb/final-readiness` was blocked by:

- `stage90_notifications_followup_not_ready`
- `stage89_analytics_visibility_not_ready`

Render logs showed the exact causes:

1. `stage93_dependency_failed dependency=stage90_notifications_followup err=name 'STAGE88_PRICE_MARKERS' is not defined`
2. PostgreSQL `UndefinedColumn`: `usage_events.event_name` does not exist. The existing schema/write path uses `usage_type`.

The `//mature-smb/...` 404 in the same log was caused by a double slash in the manually opened URL and is unrelated to readiness.

## Root cause

Stage 89 introduced helper functions:

- `stage88_price_markers()`
- `stage88_duration_markers()`
- `stage88_hours_markers()`

But `stage89_message_category()` referenced non-existent uppercase constants instead. Stage 90 calls this categorizer, so its readiness was caught by the Stage 90.1 exception guard and returned an empty diagnostic payload.

Separately, Stage 89 queried `COUNT(DISTINCT event_name)` from `usage_events`, while the canonical table column and insertion path use `usage_type`. This caused the analytics query transaction to fail even though `call_logs` itself was available.

## Changes

- Reuse the existing Stage 88 marker helper functions in `stage89_message_category()`.
- Query `COUNT(DISTINCT usage_type)` in the Stage 89 usage-events summary.
- Keep Stage 95 gates unchanged.
- No production schema migration or DBeaver write is required.

## Safety boundaries

Stage 95.1 does not change:

- dialogue or booking orchestration;
- slots/date parsing/price-side-question runtime;
- confirmation/cancel/reschedule;
- Google Calendar or Telegram runtime;
- notification delivery or external sends;
- conversation persistence;
- billing/payment runtime;
- owner/admin auth, CSRF, abuse protection or magic links;
- QA evaluator, LLM orchestration or voice/calls.

## Expected post-deploy result

- Stage 89 readiness returns `ready` or `ready_empty`, with `data_sources.call_logs=true`, and without `call_logs_query_failed:ProgrammingError`.
- Stage 90 readiness returns Stage `90` rather than guarded Stage `90.1`, with `owner_notifications_ready=true` and `lead_followup_visibility_ready=true`, assuming route protections remain healthy.
- Stage 95 no longer lists the Stage 89/90 blockers.
- `/dialogue/qa` remains 50/50 passed.
- Client-experience localization/visual polish remains a separate post-lock phase.
