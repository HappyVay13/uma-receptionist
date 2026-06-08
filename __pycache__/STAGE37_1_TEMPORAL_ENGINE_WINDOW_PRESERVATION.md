# Stage 37.1 — Temporal Engine Window Preservation

Purpose: fix Stage 37 temporal recovery where short Latvian date corrections (`parīt`, `aizparīt`) and fuzzy date+window messages (`rīt vakarā`) were parsed as dates but lost the evening time window and fell back to morning slots.

Changes:
- Preserves fuzzy time windows from short temporal messages such as `rīt vakarā`.
- Prevents negative-only `ne rīt` from resolving back to tomorrow.
- Keeps `parīt` = +2 days and `aizparīt` = +3 days.
- Recomputes preferred time window before slot generation.
- Avoids stale offered slot reuse after temporal recovery.

Expected behavior:
- `gribu pierakstīties uz konsultāciju` → `rīt vakarā` offers evening slots.
- `ne rīt` asks for another date while preserving evening context.
- `parīt` or `aizparīt` immediately offers evening slots.
