# Stage 41.1 — Cross-language Price Memory Fallback

## Purpose
Stage 41.1 fixes the production `/dialogue/qa` failure after Stage 41 deploy:

- total: 30;
- passed: 29;
- failed: 1;
- failing scenario: `stage41_ru_price_side_question`.

## Confirmed production symptom
Scenario:

```text
хочу записаться на консультацию завтра вечером
сколько это стоит?
да, подходит
```

Observed in production QA:

- booking flow was preserved;
- slots were repeated;
- `да, подходит` still moved to confirmation;
- but the price answer was not grounded and said to уточнить цену у специалиста;
- evaluator missed `business_faq_answered`.

## Root cause
Stage 41 correctly added Russian `евро` extraction to `_extract_price_from_line()`, but this did not solve the production case because the grounded price was not available in the current RU business-memory blob.

The active booking service was `konsultācija`, and the grounded price line was available in LV business memory as:

```text
Konsultācija - 10 eiro
```

The RU FAQ branch searched only the current-language `business_memory_ru` payload first. If that payload mentioned the service but did not include a price, Repliq fell back to:

```text
По услуге konsultācija лучше уточнить цену у специалиста...
```

So the issue was not only price-token parsing. It was a missing cross-language grounded-memory fallback.

## Fix
Added a read-only helper:

```text
tenant_business_memory_all_languages()
```

In the price FAQ branch, if the current-language business-memory line does not contain a price, Repliq now searches tenant business-memory fields across LV/RU/EN/generic memory before falling back to the unknown-price answer.

This is restricted to grounded FAQ lookup and does not modify:

- booking routing;
- calendar logic;
- slot generation;
- state transitions;
- evaluator expectations.

## Expected result
For the RU side-question inside an active booking flow, Repliq should now answer with a grounded price found in tenant memory, while preserving the current slots.

Expected production QA after deploy:

```text
/dialogue/qa = 30/30 passed
```
