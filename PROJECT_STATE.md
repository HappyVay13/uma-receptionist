# Repliq Project State

Current stage: Stage 36 — Advanced Conversation Recovery.

Baseline preserved:
- Stage 24 parser/offered-slot/no-confirm hotfixes
- Stage 30 after-time negotiation window
- Stage 31 fuzzy scheduling intelligence
- Stage 32 contextual refinement memory
- Stage 33 soft conversational UX
- Stage 34 regression matrix
- Stage 35 QA runner with clinic_demo + calendar-safe mode + calibrated evaluator

Stage 36 adds a deterministic recovery layer inside active booking flows. It is designed to preserve existing orchestration and avoid resetting the conversation when the user gives incomplete, hesitant, or corrective answers.


## Stage 36.1 — Semantic Recovery Continuity
- Preserves fuzzy time windows across recovery turns such as not tomorrow -> day after tomorrow.
- Improves uncertain/hold recovery language without changing booking actions.
- Booking/calendar execution logic remains unchanged.

## Stage 36.2 — Conversational Continuity Smoothing
- Added direct date refinement continuation inside recovery flow.
- Fixed redundant ask-date loop after `ne rīt` -> `parīt`.
- Preserves fuzzy time preferences when changing day.

## Stage 36.3
Semantic Date Shift Continuity added: preserves fuzzy time windows when user changes date after rejecting the previous one, e.g. `ne rīt` -> `parīt`.


## Stage 37 — Temporal Semantic Engine
- Added centralized temporal recovery for relative dates.
- Latvian `rīt/parīt/aizparīt` now maps to +1/+2/+3 days.
- Date-shift recovery preserves fuzzy time context and avoids morning fallback.

## Stage 37.1 — Temporal Engine Window Preservation
- Fixed fuzzy time window persistence for `rīt vakarā`.
- Fixed negative-only `ne rīt` so it does not resolve back to tomorrow.
- `parīt` and `aizparīt` should now regenerate contextual evening slots instead of morning fallback.

