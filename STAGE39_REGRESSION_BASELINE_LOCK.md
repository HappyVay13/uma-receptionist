# Stage 39 — Regression Baseline Lock & Project State Sync

## Purpose
Stage 39 is a documentation and baseline checkpoint after Stage 38 was confirmed as passing in production QA.

## Confirmed baseline
- `/dialogue/qa`: 15/15 passed, confirmed by user after Stage 38.3 deploy.
- Previously failing scenario: `stage38_lv_price_side_question`.
- Failing symptom before fix: booking flow was preserved and slots were repeated, but the price answer was missing.
- Confirmed target behavior: answer service price, preserve booking flow, repeat/continue offered slots.

## Scope
Documentation/state sync only.

No changes were made to:
- conversational routing;
- booking orchestration;
- calendar checks;
- parser behavior;
- service catalog logic;
- regression evaluator logic.

## Files updated
- `PROJECT_STATE.md`
- `REPLIQ_RULES.md`
- `STAGE38_3_PRICE_SIDE_QUESTION_ROUTING_FIX.md`
- `STAGE38_4_EARLY_PRICE_SIDE_QUESTION_GUARD.md`

## File added
- `STAGE39_REGRESSION_BASELINE_LOCK.md`

## Stage 38 final runtime finding
The final Stage 38 failure was caused by a late text-rewrite layer, not by missing price FAQ data.

The working protection is in `stage33_soft_conversational_ux()`:
- if `flow_preserved` is set, return the result unchanged;
- if `stage38_business_faq` is set, return the result unchanged.

This keeps combined answers intact:
- grounded business FAQ answer;
- current booking-flow follow-up;
- same language;
- same pending booking context.

## Regression scenarios protected by the current baseline
The QA baseline protects:
- Stage 30 RU/LV after-time window handling;
- Stage 31 RU/LV fuzzy evening scheduling;
- Stage 32 RU/LV contextual refinement;
- Stage 33 RU/LV positive acknowledgement flow;
- Stage 24 parser/date-time and offered-slot protections;
- Stage 37 LV `parīt` / `aizparīt` temporal recovery;
- Stage 38 LV price side-question inside booking flow;
- Stage 38 RU hours FAQ;
- Stage 38 LV location FAQ.

## Next recommended stage
Stage 40 should only be selected after a fresh archive + fresh logs/regression output show a concrete production need.

Recommended safe directions:
1. production hardening audit without behavior changes;
2. routing map extraction/documentation;
3. regression matrix expansion for additional side-questions;
4. technical debt cleanup only after exact execution-flow mapping.
