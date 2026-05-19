# REPLIQ_RULES

Core principle:
LLM is an understanding layer only. Business actions are executed by orchestration/backend logic.

Forbidden regressions:
- Do not treat time windows like “после 14:00”, “pēc 14:00”, “вечером”, “after lunch” as exact timestamps.
- Do not lose booking context during service/date/time negotiation.
- Do not repeat the same slots immediately after user rejects them.
- Do not switch language randomly mid-dialog.
- Do not create duplicate bookings on repeated confirmations.
- Do not allow a wording/composer layer to change calendar decisions, dates, services, offered slots, state, or status.

Conversational UX rules:
- If a requested slot is unavailable, offer 2–4 alternatives when possible.
- If the user says earlier/later/not so late/not so early, refine the current offer instead of restarting.
- Confirmation messages should sound like a human receptionist, but must preserve exact booking facts.
- Soft UX can rewrite wording only; orchestration remains authoritative.
