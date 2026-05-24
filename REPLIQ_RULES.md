# Repliq Conversational Rules

Core rule: LLM is an understanding layer only. Booking actions remain controlled by orchestration/state logic.

Stage 36 recovery rules:
- Do not reset an active booking flow on vague answers.
- Preserve known service/date/time whenever possible.
- If user says they do not know, offer context-aware slots if date/service are known.
- If user rejects the day, move to date selection.
- If user rejects the time, move to time selection.
- If user asks to wait, preserve state and acknowledge without clearing context.
- Existing Stage 24–35 behavior must remain protected by `/dialogue/qa`.


## Stage 36.1 — Semantic Recovery Continuity
- Preserves fuzzy time windows across recovery turns such as not tomorrow -> day after tomorrow.
- Improves uncertain/hold recovery language without changing booking actions.
- Booking/calendar execution logic remains unchanged.

## Stage 36.2 Rule
If the user corrects the day and then gives a new date, Repliq must immediately continue slot offering using the existing service and fuzzy time context. Do not ask for the date again when the new date is already provided.
