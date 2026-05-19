# REPLIQ_RULES

Core rule:
LLM is an understanding layer only. Calendar actions and business decisions remain controlled by orchestration.

Forbidden regressions:
- Do not treat `после 14:00` / `pēc 14:00` as exact 14:00.
- Do not re-ask service/date when the current flow already contains them.
- Do not repeat the same offered slots after user rejects them.
- Do not switch language randomly inside an active flow.
- Do not create duplicate calendar bookings on repeated confirmation.
- Do not loop in `AWAITING_CONFIRM` after a clear yes/no.
- Do not parse date tokens like `15.05` as time.

Scheduling UX rules:
- If requested slot is busy, suggest 2–4 alternatives.
- If user gives fuzzy time (`вечером`, `после обеда`, `pēc darba`), route to a time window.
- If user says `раньше/позже/не так поздно/не так рано`, refine the existing context.
- Preserve booking flow unless user clearly cancels or restarts.

Stage 34 QA rule:
Before adding new conversational features, run the Stage 34 regression scenarios manually or through a future regression runner.
