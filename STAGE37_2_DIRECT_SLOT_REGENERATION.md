# Stage 37.2 — Direct Slot Regeneration After Temporal Replacement

Goal: fix temporal replacement flows after Stage 37.1.

Fixed:
- `parīt` / `aizparīt` after `ne rīt` now directly regenerate contextual slots.
- Preserves evening / after-work / fuzzy temporal window.
- Prevents staying in `AWAITING_DATE` after the user has already provided a replacement date.
- Adds a guard so `jā, der` in slot-offer state selects the first offered slot and moves to confirmation instead of re-entering date selection.
- Tightens QA evaluator for Stage 37 temporal scenarios.

Regression expectations:
- `/dialogue/qa` should pass all Stage 24–37 checks.
- Stage 37 scenarios must end with slot regeneration, not a date prompt.
