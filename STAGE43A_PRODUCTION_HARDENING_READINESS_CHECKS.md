# Stage 43A — Production Hardening & Readiness Checks

## Scope

Stage 43A is a production-hardening checkpoint before cancellation/rescheduling work.

This stage intentionally avoids conversational behavior changes.

## Confirmed baseline before Stage 43A

User confirmed after Stage 42 deploy:

- `/dialogue/qa` = 30/30 passed.
- Stage 41.1 cross-language price memory fallback is closed.
- Stage 42 documentation/audit checkpoint is deployed.

## What changed

Added a safe internal readiness report endpoint:

- `GET /internal/readiness`
- optional query parameter: `tenant_id`

The endpoint aggregates production-readiness signals without running regression scenarios.

It reports:

- app/stage metadata;
- timezone;
- environment flag presence only, never secret values;
- database connectivity;
- expected runtime table visibility;
- Twilio configuration readiness;
- Google Calendar configuration readiness;
- TTS configuration flags;
- tenant readiness via the existing tenant readiness helpers;
- protected QA baseline metadata.

## What did not change

Stage 43A does not change:

- booking routing;
- calendar slot generation;
- calendar create/update/delete behavior;
- conversation state transitions;
- FAQ/business-memory answer logic;
- side-question behavior;
- regression evaluator rules;
- cancellation/rescheduling behavior.

## Why this stage was needed

The existing code already had several separate production surfaces:

- `/health`;
- `/tenant/status`;
- `/tenant/config`;
- `/tenant/overview`;
- onboarding helpers;
- tenant readiness helpers;
- Twilio validation;
- Sentry optional initialization;
- Google OAuth/service-account helpers.

But there was no single read-only production readiness report that combined env, DB, integration and tenant state in one place.

Stage 43A adds that aggregation without changing the runtime conversational flow.

## Readiness status model

The endpoint returns one of:

- `ok` — no detected readiness issues;
- `degraded` — app is reachable, but one or more configuration/readiness issues exist;
- `error` — database connectivity check failed.

Issues are returned as machine-readable strings in the `issues` array.

Examples:

- `env_missing:DATABASE_URL`
- `env_missing:OPENAI_API_KEY`
- `env_missing:TWILIO_AUTH_TOKEN`
- `google_calendar_credentials_missing`
- `tenant_not_ready`
- `table_missing_or_unreadable:usage_events`

## Safety notes

- The readiness report does not expose secret values.
- The readiness report does not call LLMs.
- The readiness report does not run `/dialogue/qa`.
- The readiness report does not create, delete, reschedule, or update calendar events.
- The readiness report does not modify conversation state.

## Tests run locally

- `python -m py_compile repliq/legacy_app.py app.py`

Full production confirmation still requires Render checks after deploy:

- `/health`
- `/internal/readiness?tenant_id=clinic_demo`
- `/dialogue/qa`

Expected QA result after deploy:

- `/dialogue/qa` = 30/30 passed.

## Recommended next step

After Stage 43A is deployed and `/dialogue/qa` remains 30/30 passed, proceed to:

- Stage 44 — Cancellation/Reschedule Regression Harness

Cancellation/rescheduling code already exists, but must first be protected by a dedicated safe-mode regression harness before behavior fixes or expansion.
