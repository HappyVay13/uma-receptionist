# Stage 38.3 — Price Side-question Routing Fix

## Problem
Inside an active booking flow, the message `cik tas maksā?` was being handled as a generic AWAITING_TIME continuation/slot reminder instead of a business FAQ side-question.

## Root cause
The price FAQ handler existed, but it was placed after earlier booking-recovery/slot-reminder branches in the active flow router. Because of that, the runtime could preserve the booking flow but fail to answer the actual price question.

## Fix
Added a deterministic `stage38_price_side_question_guard` that runs at the top of the active booking flow router, before Stage 36 recovery and generic slot reminder logic.

The guard:
- detects price questions in LV/RU/EN;
- resolves the current selected service from conversation/pending state;
- answers from business memory/service configuration via the existing FAQ helper;
- preserves booking context and offered slots;
- returns the user to the same booking flow.

## Expected behavior
`gribu pierakstīties uz konsultāciju rīt vakarā`
→ offered slots

`cik tas maksā?`
→ price answer + same offered slots

`jā, der`
→ first offered slot selected for confirmation
