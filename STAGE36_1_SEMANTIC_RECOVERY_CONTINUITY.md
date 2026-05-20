# Stage 36.1 — Semantic Recovery Continuity

## Purpose
Preserve fuzzy time preferences during recovery turns.

Examples:
- `tomorrow evening` → `not tomorrow` → `day after tomorrow` should still offer evening slots.
- `rīt vakarā` → `ne rīt` → `parīt` should still preserve `vakarā`.
- `nezinu` should help the user choose instead of dry-repeating the same state-machine prompt.

## Changes
- Persisted `preferred_time_window` into Stage 36 recovery memory keys.
- Restored fuzzy window after clearing concrete offered slots.
- Improved `ne rīt / не завтра / not tomorrow` recovery copy.
- Improved `nezinu / не знаю / not sure` response when slots already exist.
- Kept booking logic and calendar creation unchanged.

## Regression
Run `/dialogue/qa` full regression suite after deploy.
