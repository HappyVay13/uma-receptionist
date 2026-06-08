# Repliq Project State

Current stage: Stage 39 — Regression Baseline Lock & Project State Sync.

Production regression baseline:
- `/dialogue/qa` confirmed by user after Stage 38.3 deploy: 15/15 passed.
- Previous failing scenario `stage38_lv_price_side_question` is closed.
- Calendar safe mode baseline remains active for QA/regression context.
- Tenant used in QA baseline: `clinic_demo`.

Stage 39 scope:
- Documentation/state synchronization only.
- No conversational behavior changes.
- No routing changes.
- No calendar/booking execution changes.
- No regression evaluator relaxation.

Protected baseline:
- Stage 24 parser/offered-slot/no-confirm hotfixes
- Stage 30 after-time negotiation window
- Stage 31 fuzzy scheduling intelligence
- Stage 32 contextual refinement memory
- Stage 33 soft conversational UX
- Stage 34 regression matrix
- Stage 35 QA runner with clinic_demo + calendar-safe mode + calibrated evaluator
- Stage 36 advanced conversation recovery
- Stage 37 temporal semantic engine and Latvian relative-date recovery
- Stage 38 business-memory FAQ / side-question handling inside active booking flows

## Stage 36 — Advanced Conversation Recovery

Stage 36 adds a deterministic recovery layer inside active booking flows. It is designed to preserve existing orchestration and avoid resetting the conversation when the user gives incomplete, hesitant, or corrective answers.

### Stage 36.1 — Semantic Recovery Continuity
- Preserves fuzzy time windows across recovery turns such as not tomorrow -> day after tomorrow.
- Improves uncertain/hold recovery language without changing booking actions.
- Booking/calendar execution logic remains unchanged.

### Stage 36.2 — Conversational Continuity Smoothing
- Added direct date refinement continuation inside recovery flow.
- Fixed redundant ask-date loop after `ne rīt` -> `parīt`.
- Preserves fuzzy time preferences when changing day.

### Stage 36.3 — Semantic Date Shift Continuity
- Preserves fuzzy time windows when user changes date after rejecting the previous one, e.g. `ne rīt` -> `parīt`.

## Stage 37 — Temporal Semantic Engine
- Added centralized temporal recovery for relative dates.
- Latvian `rīt/parīt/aizparīt` maps to +1/+2/+3 days in the current project logic.
- Date-shift recovery preserves fuzzy time context and avoids morning fallback.

### Stage 37.1 — Temporal Engine Window Preservation
- Fixed fuzzy time window persistence for `rīt vakarā`.
- Fixed negative-only `ne rīt` so it does not resolve back to tomorrow.
- `parīt` and `aizparīt` regenerate contextual evening slots instead of morning fallback.

### Stage 37.2 — Direct Slot Regeneration After Temporal Replacement
- Fixed direct slot regeneration after `parīt` / `aizparīt` in temporal recovery flows.
- Preserves `vakarā` / fuzzy time window across replacement-date turns.
- Added slot-ack guard for `jā, der` while offered slots are visible.

### Stage 37.3 — LV Confirm Intent Guard
- Fixed Latvian positive acknowledgement detection in offered-slot state.
- `jā, der` chooses the first offered slot and asks for booking confirmation.
- Prevents accidental fallback to `AWAITING_DATE`.

## Stage 38 — Business Memory Intelligence / FAQ Rules Hardening
- Generic FAQ/business-memory answers across tenant business types.
- Side-question handling preserves active booking flow.
- Added regression scenarios for price, hours and location questions.

### Stage 38.1 — Price Side-question FAQ Fix
- Price side-questions inside active booking flow are answered from business memory/service context.
- Existing booking context is preserved.
- No calendar/orchestration booking logic changed.

### Stage 38.2 — Price FAQ Inline Answer
- Added LV `cik tas maksā?` price handling.
- Added `eiro` price extraction from business memory lines.
- Preserves booking context after answering price.

### Stage 38.3 — Preserve Business FAQ Answer Through Soft UX Layer
- Root cause of the final Stage 38 fail was the final Stage 33 soft UX layer overwriting a valid FAQ+flow answer with a generic slot prompt.
- `stage33_soft_conversational_ux()` now returns early when the result contains `flow_preserved` or `stage38_business_faq`.
- This preserves combined responses such as price answer + current slot options.
- No booking/calendar execution logic was changed.

## Stage 39 — Regression Baseline Lock & Project State Sync
- Updated project state documentation to the confirmed post-Stage-38 baseline.
- Updated conversational rules to include Stage 38.3 final guard behavior.
- Added a Stage 39 checkpoint document.
- Corrected Stage 38.3/38.4 notes so they describe the factual working mechanism instead of a non-existent standalone guard function.
- Code behavior intentionally unchanged.
