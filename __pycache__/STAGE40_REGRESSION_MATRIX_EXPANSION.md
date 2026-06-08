# Stage 40 — Regression Matrix Expansion

## Purpose
Stage 40 expands the production QA regression matrix after the Stage 39 baseline was confirmed in production.

## Confirmed input baseline
- Stage 39 deployed by user.
- `/dialogue/qa`: 15/15 passed after deployment.
- Stage 38 price side-question regression remained closed.

## Scope
Regression coverage expansion only.

No changes were made to:
- booking routing;
- conversational response generation;
- calendar checks;
- state transitions;
- service catalog logic;
- business-memory answer logic;
- regression evaluator rules.

## Code change
Updated `STAGE34_REGRESSION_TEST_MATRIX` in `repliq/legacy_app.py`.

The matrix now contains 28 scenarios total:
- existing protected scenarios: 15;
- new Stage 40 scenarios: 13.

## New Stage 40 scenarios
Added coverage for:
- RU/LV location side-questions during active booking flow;
- LV price side-question followed by numeric slot choice;
- RU/LV later-time refinement after offered slots;
- RU/LV other-day recovery after offered slots;
- RU standalone location FAQ;
- LV standalone hours FAQ;
- RU/LV location side-question followed by numeric slot choice;
- RU/LV standalone services FAQ.

## Local validation
Local validation was performed with a controlled QA harness:
- synthetic `clinic_demo` tenant configuration;
- calendar safe mode;
- deterministic conversation store;
- no OpenAI calls;
- no calendar writes.

Result:
- `total=28`
- `passed=28`
- `warnings=0`
- `failed=0`

Production confirmation still requires deploying this archive and checking `/dialogue/qa` on Render.

## Discovered candidate gaps not added as required Stage 40 checks
During candidate selection, two additional useful checks were tried locally but were not added to the production matrix because they did not pass the current behavior:

1. RU price side-question inside active booking flow:
   - example: `сколько это стоит?` after RU booking slot options;
   - observed locally: booking flow was preserved, but the answer used a fallback price clarification instead of grounded `10 евро`.

2. LV hours side-question inside active booking flow:
   - example: `cikos jūs strādājat?` after LV booking slot options;
   - observed locally: flow shifted toward date selection instead of answering hours and preserving the same offered slots.

These are not part of Stage 40 because Stage 40 is a regression expansion checkpoint, not a behavior-fix stage.

## Recommended next stage
Stage 41 should analyze and fix the two discovered side-question gaps only after fresh production `/dialogue/qa` output confirms Stage 40 behavior.
