# REPLIQ_RULES

## Core principle
LLM is an understanding layer only. Orchestration and calendar actions remain deterministic backend responsibilities.

## Forbidden regressions
- Do not treat `после 14:00` / `pēc 14:00` as exact 14:00 confirmation.
- Do not repeat busy slot loops.
- Do not switch language randomly between RU/LV/EN.
- Do not ask again for service/date when it is already known.
- Do not create duplicate bookings from confirmation loops.
- Do not remove Stage 34/35 QA endpoints without replacing them.

## QA before future stages
Before adding new scheduling/conversation logic, run:
- `/dialogue/qa`
- `/dialogue/regression_matrix`
- selected `/dialogue/regression_run/{scenario_id}` checks

## Current focus
Production-grade conversational UX, not voice-first behavior.
