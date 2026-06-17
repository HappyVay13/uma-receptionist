# Stage 57 — Basic Analytics / Usage Visibility

## Purpose
Stage 57 adds a read-only analytics and usage visibility layer for the text-first MVP pilot/admin surface.

This stage does not change the receptionist core. It only exposes safer readiness metadata and links around existing dashboard and usage endpoints.

## Factual context
Before Stage 57, the project already had dashboard and JSON endpoints such as:

- `/dashboard`
- `/dashboard/analytics` / `/analytics`
- `/dashboard/usage` / `/usage`
- `/dashboard/chart-data` / `/chart-data`
- `/bookings`
- `/conversations`
- `/activity`

Stage 57 wraps those existing surfaces into a dedicated readiness endpoint for pilot/client review.

## Added endpoint

```text
GET /usage/readiness?tenant_id=clinic_demo&days=14
GET /analytics/readiness?tenant_id=clinic_demo&days=14
```

The endpoint returns:

- table visibility for `call_logs`, `usage_events`, and `dialogue_audit_events`;
- all-time analytics summary;
- selected-window usage summary;
- channels and top services;
- usage event units by type/channel;
- plan and dialog-limit visibility;
- safe links to dashboard/analytics/usage/bookings/conversations/activity.

## Readiness integration
`/internal/readiness` now includes:

```text
usage_analytics_readiness.stage = 57
usage_analytics_readiness.status = ready/blocked
usage_analytics_readiness.usage_visibility_ready = true/false
```

`/tenant/config` and `/tenant/config/update` also include `usage_analytics_readiness`.

## UI integration
`/tenant/config/ui` now has:

```text
Usage readiness
```

and dashboard JSON links now include `usage readiness`.

## Non-goals
Stage 57 does not change:

- booking routing;
- slot generation;
- date/time parsing;
- price/business side-question handling;
- confirmation flow;
- cancellation;
- reschedule;
- Google Calendar create/update/delete runtime paths;
- regression evaluator;
- voice/call runtime.

## Safety
The new readiness endpoint is read-only. It does not call LLMs, mutate tenant config, mutate conversations, or create/update/delete Google Calendar events.

## Expected production checks

```text
/dialogue/qa = 50/50 passed
/internal/readiness?tenant_id=clinic_demo = ok
/usage/readiness?tenant_id=clinic_demo = ready
/tenant/config/ui?tenant_id=clinic_demo contains Usage readiness
```

## Commit message

```text
Stage 57: add usage analytics visibility readiness
```
