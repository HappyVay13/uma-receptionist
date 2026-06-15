# Stage 52.1 — Service Catalog Localization Polish

## Purpose

Stage 52.1 is a small demo/admin UI polish stage after Stage 52.

The Stage 52 `/tenant/config/ui` became demo-safe, but the Service catalog preview table could still display raw/minimal `service_catalog_json` labels in RU/EN columns, for example `konsultācija`, `Serviss`, `Atbalsts`, even when the client-facing service lists already contained localized names.

## Scope

This stage is UI/readiness polish only.

It does not change:

- receptionist dialogue behavior;
- booking routing;
- slot generation;
- date/time parsing;
- price side-question handling;
- cancellation;
- reschedule;
- Google Calendar create/update/delete runtime paths;
- regression evaluator rules;
- voice/call runtime.

## Changes

- Updated `/tenant/config/ui` service catalog preview rendering.
- The preview now uses the client-facing service lists when available:
  - `services_lv` for LV display;
  - `services_ru` for RU display;
  - `services_en` for EN display.
- The canonical `service_catalog_json` keys remain unchanged for runtime matching.
- Added a small UI note explaining that the preview uses client-facing names while advanced JSON keys remain canonical.
- Updated `tenant_config_ui` readiness metadata to Stage `52.1` and added:
  - `service_catalog_preview_uses_client_facing_names = true`.

## Expected result

For `clinic_demo`, the service preview should show:

| Key | LV | RU | EN |
| --- | --- | --- | --- |
| konsultācija | konsultācija | Консультация | Consultation |
| serviss | Serviss | Сервис | Service |
| atbalsts | Atbalsts | Помощь | Support |

## Expected verification

After deploy:

- `/dialogue/qa` remains `50/50 passed`.
- `/internal/readiness?tenant_id=clinic_demo` remains `status=ok`.
- `/tenant/config?tenant_id=clinic_demo` remains secret-safe.
- `/tenant/config/ui?tenant_id=clinic_demo` service preview shows localized RU/EN names.

