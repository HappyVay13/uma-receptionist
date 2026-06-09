# Stage 41 — Side-question Coverage Hardening

## Purpose
Stage 41 closes the two candidate gaps discovered during Stage 40 regression expansion:

1. RU price side-question inside an active booking flow.
2. LV hours side-question inside an active booking flow.

## Confirmed input baseline
- Stage 40 was deployed by the user.
- Production `/dialogue/qa`: 28/28 passed.
- Stage 40 matrix expansion is the current protected baseline before Stage 41.

## Root cause summary

### 1. RU price side-question
Scenario:
- `хочу записаться на консультацию завтра вечером`
- `сколько это стоит?`
- `да, подходит`

Observed before Stage 41:
- booking flow was preserved;
- slots were repeated;
- the answer did not use the grounded `10 евро` price.

Root cause:
- `try_barbershop_faq()` found the current service from active booking state;
- `_memory_line_for_service()` could match the service memory line;
- `_extract_price_from_line()` did not recognize Russian `евро` as a price token, only `€`, `eur`, and `eiro`.

Fix:
- `_extract_price_from_line()` now recognizes `10 евро` style price strings.

### 2. LV hours side-question
Scenario:
- `gribu pierakstīties uz konsultāciju rīt vakarā`
- `cikos jūs strādājat?`
- `jā, der`

Observed before Stage 41:
- booking flow was active;
- the bot did not answer business hours;
- the flow could move toward missing datetime/date handling instead of FAQ+flow follow-up.

Root cause:
- `try_barbershop_faq()` had LV hours markers such as `cikos strād`, but the real phrase contained an inserted pronoun: `cikos jūs strādājat?`;
- because that phrase did not match the FAQ detector, the turn continued into booking-flow missing-field logic.

Fix:
- added explicit LV hours markers for `cikos jūs strād`, `cikos jus strad`, and related variants.

## Regression matrix changes
Added two Stage 41 scenarios to `STAGE34_REGRESSION_TEST_MATRIX`:

1. `stage41_ru_price_side_question`
2. `stage41_lv_hours_side_question`

Total matrix size after Stage 41:
- before: 28 scenarios;
- after: 30 scenarios.

## Evaluator calibration
The evaluator now recognizes grounded FAQ answers containing:
- `евро` / `стоит` for Russian price answers;
- `darba laiks` for Latvian business-hours answers from business memory.

This is not a relaxation of expected behavior; it aligns detection with actual grounded FAQ answer formats already used by business memory.

## Local validation
Local controlled QA harness:
- total: 30;
- passed: 30;
- warnings: 0;
- failed: 0.

Syntax validation:
- `python -m py_compile repliq/legacy_app.py app.py` passed.

## Production validation required
After deployment, check:

```text
/dialogue/qa
```

Expected:

```text
30/30 passed
```
