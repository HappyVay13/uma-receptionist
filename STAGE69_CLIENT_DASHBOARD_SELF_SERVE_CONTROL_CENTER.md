# Stage 69 — Client Dashboard Self-Serve Control Center

Status: implemented locally in this archive, pending deploy verification.

## Purpose

Create one protected self-serve control center for the current text-first SaaS MVP so an admin/client can see what is configured, what needs attention, and where to click next.

This stage aggregates existing readiness/builders only. It does not change receptionist runtime behavior.

## Added endpoints

Protected by the existing Stage 61/62 admin access layer:

- `GET /control-center`
- `GET /control-center/ui`
- `GET /control-center/readiness`
- `GET /self-serve/control-center`
- `GET /self-serve/control-center/readiness`
- `GET /client/dashboard`
- `GET /client/dashboard/ui`
- `GET /client/control-center`
- `GET /client/control-center/ui`

## Aggregated blocks

The control center reads existing readiness payloads for:

- tenant business profile and working hours;
- service catalog builder/runtime catalog;
- Business Memory / FAQ Builder;
- Google Calendar self-serve setup;
- Telegram bot setup;
- Telegram live smoke lock;
- usage/dashboard visibility;
- launch readiness;
- access boundaries.

## Security

- Raw Google service account JSON is not exposed.
- Raw Telegram bot token is not exposed.
- Raw Telegram webhook secret is not exposed.
- Control-center endpoints are protected by the current admin session/shared-token MVP layer.
- `public_saas_ready` remains `false`.

## Not changed

- booking routing;
- slot generation;
- date/time parsing;
- price side-question logic;
- confirmation;
- cancel/reschedule;
- Google Calendar event create/update/delete runtime;
- Telegram webhook runtime;
- dialogue QA evaluator;
- voice/calls.

## Verification

Expected after deploy:

- `/dialogue/qa` returns 50/50 passed.
- `/control-center/ui?tenant_id=clinic_demo` opens after admin login/session.
- `/control-center/readiness?tenant_id=clinic_demo` returns `stage=69`.
- `private_admin_ready=true` unless admin/session env is missing.
- `public_saas_ready=false`.
- `/internal/readiness?tenant_id=clinic_demo` includes `client_control_center_readiness`.
- `/tenant/config?tenant_id=clinic_demo` includes `client_control_center_readiness` and does not expose secrets.
- `/tenant/config/ui?tenant_id=clinic_demo` and `/dashboard?tenant_id=clinic_demo` show control-center links.
