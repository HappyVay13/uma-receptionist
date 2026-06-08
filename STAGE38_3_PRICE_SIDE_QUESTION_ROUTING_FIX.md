# Stage 38.3 — Preserve Business FAQ Answer Through Soft UX Layer

## Problem
Inside an active booking flow, the message `cik tas maksā?` produced a valid business FAQ answer internally, but the final user-visible response only repeated offered slots.

Failing scenario:
1. `gribu pierakstīties uz konsultāciju rīt vakarā`
2. bot offers evening slots
3. `cik tas maksā?`
4. bot repeats slots but does not answer the price

## Factual root cause
The price FAQ path was able to resolve the current service and produce a grounded answer such as:

`konsultācija maksā 10 eiro.`

The active booking follow-up composer was also able to preserve the booking flow and append the current slot options.

The visible failure happened later: the final Stage 33 soft conversational UX layer saw `status=need_more`, `state=AWAITING_TIME`, and existing offered slots, then rewrote `msg_out` / `reply_voice` into a generic slot prompt. That removed the FAQ answer from the final response.

## Fix
`stage33_soft_conversational_ux()` now returns early when the result already contains either:

- `flow_preserved`
- `stage38_business_faq`

This prevents the final wording layer from collapsing a combined FAQ+flow answer into a plain slot reminder.

## Safety
- No booking state transition logic changed.
- No calendar logic changed.
- No service/date/time parser logic changed.
- No regression evaluator rules changed.

## Expected behavior
`gribu pierakstīties uz konsultāciju rīt vakarā`
→ offered slots

`cik tas maksā?`
→ price answer + same booking-flow slot prompt

`jā, der`
→ first offered slot selected for confirmation
