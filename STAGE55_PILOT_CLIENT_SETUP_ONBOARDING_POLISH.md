# Stage 55 — Pilot Client Setup / Tenant Onboarding Polish

## Purpose

Stage 55 prepares the text-first Repliq MVP for a first pilot/client setup workflow after the Stage 54 launch readiness lock.

This is not a receptionist behavior stage. It adds read-only pilot setup readiness metadata and small onboarding/admin UX clarifications.

## Factual inputs from Stage 54 deployment

The user provided screenshots showing:

- `/onboarding/status?tenant_id=clinic_demo` reported `google_connected=true`, `calendar_selected=true`, `onboarding_completed=true`, `next_step=done`, but also `persisted_onboarding_completed=false`.
- `/google/calendars/ui?tenant_id=clinic_demo` showed Google connected but “No calendars available for this account”, while other readiness/dashboard surfaces showed a selected calendar and live booking already worked.
- `/dashboard?tenant_id=clinic_demo` showed Ready, Google connected, Calendar selected, and no blocking setup issues.
- `/tenant/config/ui`, `/tenant/config`, and `/launch/readiness` were already demo-safe after Stage 52–54.

## Changes

### New endpoint

Added:

```http
GET /pilot/setup/readiness?tenant_id=clinic_demo
```

It returns read-only pilot setup metadata:

- pilot setup status
- current text-first MVP scope
- onboarding effective vs persisted state
- selected calendar status
- setup gates
- blocking/warnings
- pilot setup checklist
- safe links

### Internal readiness

`/internal/readiness?tenant_id=...` now includes:

```json
"pilot_setup_readiness": {
  "stage": "55"
}
```

### Onboarding status clarity

`/onboarding/status` now exposes:

- `persisted_state_matches_effective`
- `effective_completion_source`

This makes the observed runtime/persisted onboarding difference explicit instead of ambiguous.

### Google calendars UI polish

`/google/calendars` now includes selected-calendar metadata.

`/google/calendars/ui` now handles the case where Google returns an empty calendar list but the tenant already has a saved selected calendar. In that case the UI shows a “Currently selected calendar” fallback instead of looking blocked.

### Tenant config UI links

`/tenant/config/ui` now includes Pilot setup links in the header and quick links.

## Non-goals

Stage 55 does not change:

- booking routing
- slot generation
- date/time parsing
- price/business side-question behavior
- slot confirmation flow
- cancellation behavior
- reschedule behavior
- Google Calendar create/update/delete runtime behavior
- regression evaluator
- voice/call runtime

## Safety

The new pilot readiness endpoint is read-only. It does not:

- call LLMs
- create tenants
- mutate tenant config
- mutate conversations
- create/update/delete Google Calendar events
- expose tenant secrets

## Expected verification after deploy

```text
/dialogue/qa = 50/50 passed
/internal/readiness?tenant_id=clinic_demo = ok
/pilot/setup/readiness?tenant_id=clinic_demo returns stage=55
/tenant/config/ui?tenant_id=clinic_demo has Pilot setup link/button
/google/calendars/ui?tenant_id=clinic_demo does not look blocked when a calendar_id is already selected
```

## Commit message

```text
Stage 55: add pilot setup onboarding readiness polish
```
