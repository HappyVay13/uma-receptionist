# Stage 38.4 — Early Price Side-question Guard

## Root cause

The previous Stage 38 price side-question handling was placed inside `free_router_handle_turn()`.
That was too late in the runtime execution path. During an active booking flow, earlier booking
routers could keep the conversation in `AWAITING_TIME` and repeat offered slots before the FAQ
price handler executed.

Failing scenario:

1. `gribu pierakstīties uz konsultāciju rīt vakarā`
2. bot offers evening slots
3. `cik tas maksā?`
4. bot repeated slots instead of answering price

## Fix

Added an early Stage 38.4 guard directly in `handle_user_text()` immediately after:

- tenant/settings/service/business memory load
- conversation state normalization
- pending context load

and before:

- Stage 37 temporal routing
- LLM semantic routing
- Stage 31 time-window routing
- generic slot-selection/recovery routing

The guard only activates when:

- the user message is a price question, and
- the conversation is already inside an active booking flow.

It answers the price through the existing Stage 38 FAQ/business-memory path, preserves booking
context, and appends the current booking follow-up/slot options.

## Safety

No existing booking/date/time parsing logic was changed.
No calendar booking behavior was changed.
No regression evaluator logic was relaxed.
