# Stage 34 — Production Regression Test Matrix

Use these tests after every hotfix touching parsing, orchestration, scheduling, language, confirmation, or response UX.

## RU

1. `хочу записаться на консультацию на послезавтра после 14:00`
Expected: offers multiple slots after 14:00, not exact 14:00 confirmation.

2. `хочу записаться на консультацию завтра вечером`
Expected: evening options, no service/date re-ask.

3. After offered slots: `не так поздно`
Expected: same booking flow, earlier refined alternatives, no repeated same slots.

4. After confirm: `да, подходит`
Expected: booking finalizes, no confirm-loop.

## LV

5. `gribu pierakstīties uz konsultāciju parīt pēc 14:00`
Expected: offers multiple slots after 14:00.

6. `gribu pierakstīties uz konsultāciju rīt vakarā`
Expected: evening window, Latvian reply.

7. After offered slots: `var mazliet agrāk?`
Expected: refined earlier alternatives, same flow.

8. After confirm: `jā, der`
Expected: booking finalizes, no confirm-loop.

## Parser protections

9. `gribu pierakstīties uz konsultāciju 15.05 10:00`
Expected: date 15.05 + time 10:00. Forbidden: time 15:05.

10. Flow: `gribu pierakstīties rīt 14:00` → `konsultācija` → `10:00`
Expected: selects offered slot 10:00. Forbidden: repeats old 14:00 busy message.
