# Stage 37 — Temporal Semantic Engine

Purpose: stabilize conversational date understanding and temporal recovery for production booking UX.

Added:
- centralized relative date parsing for Latvian/Russian/English recovery turns;
- Latvian support: `rīt` = +1, `parīt` = +2, `aizparīt` = +3;
- early temporal recovery before LLM/entity routing;
- `ne rīt → parīt/aizparīt` continuation without resetting booking flow;
- preservation of fuzzy time windows like `vakarā`, `pēc darba`, `after 14:00`;
- anti-morning fallback for semantic date shifts;
- Stage 37 temporal regression scenarios.

Safety:
- no calendar write behavior changed;
- no booking confirmation logic changed;
- existing Stage 24–36 behavior remains guarded by regression matrix.
