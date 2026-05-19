# PROJECT_STATE — Repliq

Current stage: **Stage 35 — Regression Runner / QA Dashboard**

## Completed milestones
- Stage 24: Offered slot choice + parser protection
- Stage 30: Conversational negotiation windows
- Stage 31: Human scheduling intelligence
- Stage 32: Context persistence and slot refinement memory
- Stage 33: Soft conversational UX layer
- Stage 34: Production regression matrix
- Stage 35: Internal QA dashboard and regression runner

## Active endpoints
- `/dialogue/regression_matrix` — machine-readable regression matrix
- `/dialogue/qa` — Stage 35 visual QA dashboard
- `/dialogue/regression_run/{scenario_id}` — run one scenario
- `/dialogue/regression_run_all` — run regression suite

## Notes
Stage 35 is a tooling layer. It should not change customer booking behavior directly. It is designed to protect Stage 24 and Stage 30–33 from future regressions.

## Next recommended stage
Stage 36 — Advanced Conversation Recovery & Edge Case Hardening.
