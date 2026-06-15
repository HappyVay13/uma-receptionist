# Stage 53 — Client Demo Script & Demo Mode Readiness

## Purpose
Prepare Repliq for a controlled client demo as a text-first AI receptionist MVP.

## Confirmed baseline before this stage
- Stage 52.1 closed.
- `/dialogue/qa = 50/50 passed`.
- `/internal/readiness = ok`.
- `/tenant/config/ui` is demo-safe and service catalog preview uses client-facing names.
- Live text smoke was already reported as successful by the user after Stage 49.

## Changes
- Added `GET /demo/script?tenant_id=...`.
- Added `client_demo_script` metadata to `/internal/readiness`.
- Added a Demo script link/button to `/tenant/config/ui`.
- Updated project documentation and rules.

## What `/demo/script` contains
- Pages to open before demo.
- Demo story / talk track.
- RU and LV scripted client messages.
- Calendar verification checks.
- Fallback plan if a live demo step is slow or fails.
- Known limitations.

## Safety
This endpoint is read-only. It does not:
- call LLMs;
- mutate conversations;
- change tenant config;
- create calendar events;
- update calendar events;
- delete calendar events;
- expose secrets.

## Product scope
Current MVP is text-first receptionist behavior. Voice/calls remain future scope.

## Protected systems not changed
- Booking routing.
- Slot generation.
- Date/time parsing.
- Price side-questions.
- Confirmation flow.
- Cancellation.
- Reschedule.
- Google Calendar create/update/delete functions.
- Regression evaluator.
- Voice/call runtime.

## Expected production checks after deploy
- `/dialogue/qa = 50/50 passed`.
- `/internal/readiness?tenant_id=clinic_demo` includes `client_demo_script.stage = 53`.
- `/demo/script?tenant_id=clinic_demo` returns read-only demo script metadata.
- `/tenant/config/ui?tenant_id=clinic_demo` contains a Demo script quick link.
