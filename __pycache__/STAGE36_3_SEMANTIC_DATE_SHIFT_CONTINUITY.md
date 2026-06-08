# Stage 36.3 — Semantic Date Shift Continuity

## Purpose
Fix recovery continuity when a user rejects the current date and then provides a replacement date.

Example:
- `rīt vakarā`
- `ne rīt`
- `parīt`

Expected behavior:
- preserve the original fuzzy time preference (`vakarā` / evening);
- do not re-enter a generic date-question loop;
- immediately regenerate contextual slots for the new date;
- avoid morning fallback such as `09:00 / 09:30` when evening context exists.

## Change
Added an early Stage 36.3 guard in the active booking flow before generic partial datetime persistence.

When state is `AWAITING_DATE` and the next user message contains a recoverable date, the system directly calls contextual slot generation while preserving Stage 36 time-window memory.

## Safety
- Does not change calendar booking creation.
- Does not change Stage 24–35 regression matrix logic.
- Only affects active booking recovery flow after a date-rejection/refinement.
