# Stage 35 — Regression Runner / QA Dashboard

## Purpose
Stage 35 turns the Stage 34 regression matrix into an internal QA dashboard and runner.

## Endpoints
- `GET /dialogue/qa` — visual dashboard
- `GET /dialogue/regression_run/{scenario_id}` — run one scenario
- `GET /dialogue/regression_run_all` — run all scenarios
- `GET /dialogue/regression_matrix` — raw matrix

## Notes
The runner uses real backend conversation handling through the dev channel. It is meant for internal QA and should be used against test tenants.
