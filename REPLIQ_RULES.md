# Repliq Conversational Rules

Core rule: LLM is an understanding layer only. Booking actions remain controlled by orchestration/state logic.

Current protected baseline:
- `/dialogue/qa` confirmed after Stage 38.3: 15/15 passed.
- Stage 39 is documentation/state synchronization only.
- Do not change conversational behavior unless a new archive + logs/regression output prove the need.

## Global production rules
- Do not reset an active booking flow unless the user clearly cancels or starts a new incompatible task.
- Preserve known service/date/time whenever possible.
- Preserve offered slots while answering side-questions inside an active booking flow.
- Do not answer from invented business facts. Use tenant settings, service catalog, business memory, or known runtime state.
- Booking/calendar actions must remain deterministic and orchestration-controlled.
- Do not relax regression evaluator rules to make tests pass.

## Stage 36 recovery rules
- Do not reset an active booking flow on vague answers.
- Preserve known service/date/time whenever possible.
- If user says they do not know, offer context-aware slots if date/service are known.
- If user rejects the day, move to date selection.
- If user rejects the time, move to time selection.
- If user asks to wait, preserve state and acknowledge without clearing context.
- Existing Stage 24–35 behavior must remain protected by `/dialogue/qa`.

### Stage 36.1 — Semantic Recovery Continuity
- Preserves fuzzy time windows across recovery turns such as not tomorrow -> day after tomorrow.
- Improves uncertain/hold recovery language without changing booking actions.
- Booking/calendar execution logic remains unchanged.

### Stage 36.2 Rule
If the user corrects the day and then gives a new date, Repliq must immediately continue slot offering using the existing service and fuzzy time context. Do not ask for the date again when the new date is already provided.

### Stage 36.3 Rule
Semantic Date Shift Continuity preserves fuzzy time windows when user changes date after rejecting the previous one, e.g. `ne rīt` -> `parīt`.

## Stage 37 — Temporal Semantic Engine
- Added centralized temporal recovery for relative dates.
- Latvian `rīt/parīt/aizparīt` maps to +1/+2/+3 days in the current project logic.
- Date-shift recovery preserves fuzzy time context and avoids morning fallback.

### Stage 37.1 — Temporal Engine Window Preservation
- Fixed fuzzy time window persistence for `rīt vakarā`.
- Fixed negative-only `ne rīt` so it does not resolve back to tomorrow.
- `parīt` and `aizparīt` should regenerate contextual evening slots instead of morning fallback.

### Stage 37.2 temporal rules
- If the user gives a replacement relative date (`parīt`, `aizparīt`) inside an active booking flow, regenerate slots immediately.
- Do not ask for the date again after a replacement date was provided.
- If the user says `jā, der` while slot options are visible, treat it as choosing the first offered slot and move to confirmation.

### Stage 37.3 Rule
When the user is in `AWAITING_TIME` and offered slots exist, short positive Latvian replies such as `jā, der`, `ja der`, `der`, `labi`, or `apstiprinu` must select the first offered slot and move to `AWAITING_CONFIRM`. They must not re-open date selection.

## Stage 38 — Business Memory Intelligence / FAQ Rules Hardening
- Generic FAQ/business-memory answers across tenant business types.
- Side-question handling preserves active booking flow.
- Regression scenarios protect price, hours and location questions.

### Stage 38.1 — Price Side-question FAQ Fix
- Price side-questions inside active booking flow are answered from business memory/service context.
- Existing booking context is preserved.
- No calendar/orchestration booking logic changed.

### Stage 38.2 Rule
When the user asks a price question during an active booking flow, answer the price from grounded business memory/service data first, then continue the same booking flow with the existing offered slots.

### Stage 38.3 Rule
If a result already contains a preserved active-flow FAQ answer (`flow_preserved` or `stage38_business_faq`), final text polishing layers must not rewrite it into a generic slot prompt.

Required behavior for price side-question during booking:
1. Answer the grounded price from service/business memory.
2. Keep the active booking state.
3. Repeat or continue the current slot-selection prompt.
4. Keep the same reply language.

Example protected scenario:
- `gribu pierakstīties uz konsultāciju rīt vakarā`
- `cik tas maksā?`
- `jā, der`

Expected:
- price answered;
- booking flow preserved;
- Latvian reply preserved;
- positive acknowledgement selects the first offered slot for confirmation.

## Stage 39 — Regression Baseline Lock & Project State Sync
- Documentation checkpoint only.
- No routing changes.
- No booking/calendar behavior changes.
- No evaluator relaxation.
- Future changes must start from the confirmed 15/15 baseline.
