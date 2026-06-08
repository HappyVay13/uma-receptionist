# Stage 38.4 — Archived Note / Superseded by Stage 38.3 Runtime Finding

## Status
This note is kept for project history only.

After factual code audit of the working Stage 38 archive, the confirmed production fix is not a standalone `stage38_price_side_question_guard` function and not a separate early guard in `handle_user_text()`.

The working mechanism is:

1. `try_barbershop_faq()` detects business FAQ / price questions.
2. The current selected service can be resolved from active booking context.
3. `faq_with_flow_followup()` combines the grounded FAQ answer with the active booking follow-up.
4. The result is marked with `flow_preserved` and `stage38_business_faq`.
5. `stage33_soft_conversational_ux()` returns early for those markers and does not overwrite the combined answer.

## Why this note exists
Earlier Stage 38 notes described an early price side-question guard. The final confirmed fix was different: the FAQ answer was already being formed, but the final soft UX layer removed it from the visible response.

## Safety contract
- Do not introduce another early guard unless a future regression proves it is necessary.
- Do not duplicate price-question logic across routers without execution-flow analysis.
- Preserve the current Stage 38.3 guard behavior because `/dialogue/qa` was confirmed as 15/15 passed after it.
