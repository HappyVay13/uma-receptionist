# Stage 51 — Tenant Config / Business Memory Admin Hardening

## Scope
Stage 51 hardens the admin/readiness layer for tenant configuration and business memory after the text-first receptionist core was confirmed stable.

This stage does not change receptionist behavior.

## Baseline before Stage 51
- Stage 50 deployed.
- `/dialogue/qa` confirmed by user: 50/50 passed.
- `/internal/readiness` confirmed by user: ok.
- Text-first MVP scope confirmed.
- Live text smoke had been reported as successful after Stage 49.

## Factual code audit
Existing code already had:
- `/tenant/config` JSON endpoint.
- `/tenant/config/ui` HTML config editor.
- `POST /tenant/config/update`.
- `/tenant/status` and `/tenant/overview`.
- Tenant onboarding and Google Calendar selection paths.
- Business memory fields: `business_memory_lv`, `business_memory_ru`, `business_memory_en`.
- Service catalog parsing via `service_catalog`, `services_catalog`, `service_catalog_json`, `services_json`, env fallback, then language-services fallback.

The gap was visibility, not receptionist flow: there was no dedicated safe admin-readiness payload showing whether tenant config/business memory was suitable for client-facing SaaS/admin use.

## Changes
Added read-only helper:

```text
tenant_admin_config_readiness_payload()
```

Added safe endpoint:

```text
GET /tenant/admin/readiness?tenant_id=...
```

Extended existing responses with admin readiness metadata:

```text
GET /tenant/config
POST /tenant/config/update
GET /internal/readiness
```

## What the admin readiness checks cover
- Business name.
- Timezone.
- Work start/end.
- Google connected status.
- Calendar selected status.
- Service-account presence flag only, not secret contents.
- Service catalog source and item count.
- JSON syntax/type checks for editable JSON config fields.
- Business memory coverage for LV/RU/EN.
- Runtime missing items.

## Safety guarantees
The Stage 51 endpoint and metadata do not:
- call LLMs;
- mutate tenant config;
- mutate conversations;
- create, update, or delete Google Calendar events;
- expose service account JSON, OAuth tokens, or other secrets.

## Unchanged
- Booking flow.
- Price side-question flow.
- Slot selection/confirmation.
- Cancellation.
- Reschedule.
- Google Calendar create/update/delete functions.
- Regression evaluator.
- Voice/call runtime.

## Expected production check after deploy

```text
/dialogue/qa = 50/50 passed
/internal/readiness = ok
tenant_admin_config.stage = 51
GET /tenant/admin/readiness?tenant_id=clinic_demo returns safe admin config metadata
```

## Recommended next stage
Stage 52 — Business Memory / Service Catalog Client Editor UX Hardening.
