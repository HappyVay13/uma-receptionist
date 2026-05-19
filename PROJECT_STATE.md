# PROJECT_STATE.md

Current stage: Stage 32 — Conversational Context Persistence

Completed recent stages:
- Stage 24: Free Conversational Slot Router
- Stage 25: AI Response Composer
- Stage 25.5: Conversational Closure Layer
- Stage 26: Conversational Semantic Router
- Stage 27: Entity Persistence Layer
- Stage 27.1: Service/entity matching hotfix
- Stage 28: Confirmation finalization and state exit hardening
- Stage 29: After-time window router
- Stage 30: Conversational negotiation windows
- Stage 31: Human scheduling intelligence
- Stage 32: Contextual slot refinement memory

Active focus:
- Production-grade conversational scheduling UX
- Short-term booking-flow memory
- Avoiding repeated offered slots
- Natural refinement phrases: earlier/later/not so early/not so late

Known target behavior:
- “после 14:00” must be treated as a time window, not exact 14:00.
- “вечером / утром / после обеда” must offer multiple slots.
- “не так поздно / не так рано / чуть позже / чуть раньше” must refine current offered slots.
- Confirmed bookings must exit confirmation flow and avoid duplicate booking loops.

Main file:
- repliq/legacy_app.py

Deployment:
- Replace repliq/legacy_app.py, commit, push to GitHub, let Render auto-deploy.
