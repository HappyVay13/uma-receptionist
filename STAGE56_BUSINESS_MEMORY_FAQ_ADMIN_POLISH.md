# Stage 56 — Business Memory / FAQ Admin Polish

## Scope
Stage 56 is a read-only admin/readiness and UI polish stage for business memory and FAQ content. It keeps the active MVP as a text-first receptionist and leaves voice/calls as future scope.

## Root cause / reason
After Stage 55, pilot setup was ready, but the next client/admin bottleneck was business knowledge editing: prices, services, address, hours, and FAQ-style facts were editable as raw text, but there was no dedicated readiness view explaining whether memory was usable across LV/RU/EN or whether service facts were covered.

## Changes
- Added `stage56_business_memory_admin_readiness_payload()`.
- Added `GET /business-memory/readiness?tenant_id=...`.
- Added `business_memory_admin` metadata to `/internal/readiness`.
- Added `business_memory_admin` metadata to `/tenant/config` and `/tenant/config/update`.
- Added Memory readiness links/buttons to `/tenant/config/ui`.
- Added a business memory readiness panel in `/tenant/config/ui` showing LV/RU/EN readiness, line counts, and price-fact counts.

## Safety
The new endpoint and UI metadata are read-only. They do not call LLMs, mutate tenant config, mutate conversations, or create/update/delete Google Calendar events. Existing save behavior remains through `/tenant/config/update`.

## Expected production checks
- `/dialogue/qa = 50/50 passed`
- `/internal/readiness?tenant_id=clinic_demo` includes `business_memory_admin.stage = 56`
- `/business-memory/readiness?tenant_id=clinic_demo` returns `status = ready` for current demo tenant
- `/tenant/config/ui?tenant_id=clinic_demo` contains Memory readiness link/button and LV/RU/EN memory readiness panel
