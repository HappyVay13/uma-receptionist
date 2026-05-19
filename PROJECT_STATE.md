# PROJECT_STATE — Repliq

Current stage: Stage 34 — Production Regression Test Matrix

Completed milestones:
- Stage 24: Free Conversational Slot Router hotfixes
- Stage 25: AI Response Composer
- Stage 25.5: Conversational Closure Layer
- Stage 26: Conversational Semantic Router
- Stage 27 / 27.1: Entity Persistence + LV service matching hotfixes
- Stage 28: Confirmation Finalization & State Exit Hardening
- Stage 29: After-time Window Router
- Stage 30: Conversational Negotiation Engine
- Stage 31: Human Scheduling Intelligence
- Stage 32: Contextual Slot Refinement Memory
- Stage 33: Deterministic Soft Conversational UX
- Stage 34: Production Regression Test Matrix

Active focus:
Protect working conversational behavior before further feature expansion.

Stage 34 additions:
- Centralized regression matrix in `repliq/legacy_app.py`
- Read-only endpoint: `/dialogue/regression_matrix`
- Regression coverage for RU/LV booking, after-time windows, fuzzy time windows, refinement memory, confirmation finalization, and parser protections.

Known protected behaviors:
- `после 14:00` / `pēc 14:00` must mean a window after 14:00, not exact 14:00.
- `вечером` / `vakarā` must route into an evening window.
- `не так поздно`, `чуть раньше`, `можно позже` must refine the current flow, not reset it.
- Offered slot choices like `10:00` must select an offered slot.
- Date tokens like `15.05` must not be parsed as time `15:05`.
- Confirmation must finalize booking and exit confirm-loop.

Next recommended stage:
Stage 35 — Regression Runner / Dev QA Dashboard
