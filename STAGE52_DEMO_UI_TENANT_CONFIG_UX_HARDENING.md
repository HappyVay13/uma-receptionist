# Stage 52 — Demo UI / Tenant Config UX Hardening

## Purpose

Stage 52 hardens the tenant configuration surface for text-first MVP demo/admin use.

This is a UI/admin safety stage, not a receptionist behavior stage.

## Root cause / factual observation

The Stage 51 admin readiness endpoint reported `ready`, but the existing `/tenant/config/ui` was still a technical editor:

- It showed the page as `Tenant Config Editor` with mostly raw technical fields.
- There was no visible demo/readiness status in the UI.
- Optional JSON fields such as weekly hours, days off, breaks and holidays looked like missing configuration rather than optional advanced settings.
- `service_catalog_json` was shown as raw JSON without a human-readable preview.
- Existing Google service account JSON could be loaded into the editor, which is unsafe for demo/admin usage.
- `/tenant/config` returned raw tenant data, including secret-bearing fields, because it used the raw tenant view.

## Changes made

### 1. Demo-safe tenant config UI

Reworked `GET /tenant/config/ui` into a demo/admin surface with:

- text-first MVP framing;
- visible demo readiness badge;
- readiness/status cards;
- basic business settings section;
- client-facing services section;
- service catalog preview table;
- business memory / FAQ section;
- advanced JSON settings collapsed by default;
- Google service account hidden by default and editable only by paste-to-replace.

### 2. Secret-safe config API response

`GET /tenant/config` and `POST /tenant/config/update` now return safe tenant/config views:

- service account JSON is not exposed in response bodies;
- secret-like tenant fields are replaced with `null`;
- boolean `*_configured` flags indicate presence;
- resolved settings do not expose `service_account_json` value.

This does not change runtime calendar behavior. Runtime functions still use tenant/environment credentials internally.

### 3. Stage 52 readiness metadata

Added read-only config UI hardening metadata:

- `tenant_config_ui.stage = 52` in `/internal/readiness`;
- `config_ui_hardening.stage = 52` in `/tenant/config` and `/tenant/config/update` responses.

The metadata is read-only and does not call LLMs or mutate calendar/conversation state.

## What was not changed

Stage 52 did not change:

- booking routing;
- slot generation;
- date/time parsing;
- business FAQ/side-question behavior;
- cancellation;
- reschedule;
- Google Calendar create/update/delete runtime logic;
- regression evaluator;
- voice/call runtime.

## Expected production checks after deploy

- `/dialogue/qa` remains `50/50 passed`.
- `/internal/readiness?tenant_id=clinic_demo` remains `ok`.
- `/tenant/admin/readiness?tenant_id=clinic_demo` remains `ready`.
- `/tenant/config?tenant_id=clinic_demo` no longer exposes raw service account JSON/private key.
- `/tenant/config/ui?tenant_id=clinic_demo` displays a demo-safe UI with readiness/status cards and collapsed advanced sections.

## Stage name

Stage 52 — Demo UI / Tenant Config UX Hardening
