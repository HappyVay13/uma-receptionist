# PROJECT_STATE — Repliq

Current stage: Stage 33 — Soft Conversational UX Layer

Completed stages relevant to current runtime:
- Stage 24: Free Conversational Slot Router
- Stage 25: AI Response Composer
- Stage 25.5: Conversational Closure Layer
- Stage 26: Conversational Semantic Router
- Stage 27: Entity Persistence Layer
- Stage 27.1: Service/entity hotfixes
- Stage 29: After-time Window Router
- Stage 30: Conversational Negotiation Engine
- Stage 31: Human Scheduling Intelligence
- Stage 32: Conversational Context Persistence
- Stage 33: Soft Conversational UX Layer

Active focus:
- Production-grade conversational receptionist UX.
- Keep orchestration deterministic; LLM remains understanding layer only.
- Improve customer-facing wording without changing booking/calendar decisions.

Stage 33 changes:
- Added deterministic soft UX wording layer after humanize/composer and before usage warnings.
- Softens booking confirmations, slot offers, date/service prompts, booked responses.
- Preserves all concrete slot labels and does not change state, status, service, datetime or calendar actions.

Known constraints:
- Avoid destructive refactors.
- Preserve Stage 30–32 negotiation and context memory behavior.
- Keep multilingual LV/RU/EN consistency.
