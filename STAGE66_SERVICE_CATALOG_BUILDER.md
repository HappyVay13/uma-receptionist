# Stage 66 — Service Catalog Builder

## Purpose

Add a protected self-serve UI and readiness layer for managing tenant services without editing raw JSON.

## Added endpoints

- `GET /service-catalog/builder?tenant_id=...`
- `GET /service-catalog/builder/ui?tenant_id=...`
- `GET /tenant/service-catalog/builder?tenant_id=...`
- `GET /tenant/service-catalog?tenant_id=...`
- `POST /tenant/service-catalog/update`
- `POST /service-catalog/update`
- `GET /service-catalog/readiness?tenant_id=...`
- `GET /tenant/service-catalog/readiness?tenant_id=...`
- `GET /services/readiness?tenant_id=...`

## Behavior

The builder edits:

- service key
- active/inactive state
- LV/RU/EN names
- duration
- price/currency
- LV/RU/EN aliases

On save it writes the normalized catalog to the tenant service catalog column and optionally syncs:

- `services_lv/services_ru/services_en`
- managed service price facts in `business_memory_lv/business_memory_ru/business_memory_en`

Inactive services are preserved in builder data but excluded from runtime service parsing.

## Non-goals

This stage does not change receptionist dialogue orchestration, slot generation, booking, cancel/reschedule, Telegram webhook handling, Google Calendar event runtime, or QA evaluator behavior.

## Security

All builder/readiness/update paths are protected by the Stage 61/62 admin session/token layer. Public SaaS readiness remains false until owner auth, tenant ownership, billing, CSRF, and public abuse protection are implemented.
