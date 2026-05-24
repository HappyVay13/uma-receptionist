# Repliq Conversational Rules

Core rule: LLM is an understanding layer only. Booking actions remain controlled by orchestration/state logic.

Stage 36 recovery rules:
- Do not reset an active booking flow on vague answers.
- Preserve known service/date/time whenever possible.
- If user says they do not know, offer context-aware slots if date/service are known.
- If user rejects the day, move to date selection.
- If user rejects the time, move to time selection.
- If user asks to wait, preserve state and acknowledge without clearing context.
- Existing Stage 24–35 behavior must remain protected by `/dialogue/qa`.


## Stage 36.1 — Semantic Recovery Continuity
- Preserves fuzzy time windows across recovery turns such as not tomorrow -> day after tomorrow.
- Improves uncertain/hold recovery language without changing booking actions.
- Booking/calendar execution logic remains unchanged.

## Stage 36.2 Rule
If the user corrects the day and then gives a new date, Repliq must immediately continue slot offering using the existing service and fuzzy time context. Do not ask for the date again when the new date is already provided.

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


## Stage 37.2 temporal rules
- If the user gives a replacement relative date (`parīt`, `aizparīt`) inside an active booking flow, regenerate slots immediately.
- Do not ask for the date again after a replacement date was provided.
- If the user says `jā, der` while slot options are visible, treat it as choosing the first offered slot and move to confirmation.

## Stage 37.3 Rule
When the user is in `AWAITING_TIME` and offered slots exist, short positive Latvian replies such as `jā, der`, `ja der`, `der`, `labi`, or `apstiprinu` must select the first offered slot and move to `AWAITING_CONFIRM`. They must not re-open date selection.


## Stage 38 — Business Memory Intelligence / FAQ Rules Hardening
- Generic FAQ/business-memory answers across tenant business types.
- Side-question handling preserves active booking flow.
- Added regression scenarios for price, hours and location questions.


## Stage 38.1 — Price Side-question FAQ Fix
- Price side-questions inside active booking flow are answered from business memory/service context.
- Existing booking context is preserved.
- No calendar/orchestration booking logic changed.
