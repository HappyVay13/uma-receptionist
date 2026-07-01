# Stage 87.2 — Launch Review Readiness Fast Path Hotfix

## Status
Built after Stage 87.1.

## Problem
`/owner/launch-review/ui?tenant_id=clinic_demo` bootstrapped after Stage 87.1, but the JSON load stayed on `Loading launch checklist...`.
`/owner-workspace/final-review/readiness?tenant_id=clinic_demo` also kept loading.

Root cause in Stage 87.0/87.1: the final review endpoint ran a deep cross-stage readiness fan-out in one browser request. A slow nested dependency could block the whole owner page.

## Fix
Stage 87.2 changes `stage87_owner_workspace_final_review_core()` to a fast owner-safe checklist model:
- uses tenant data and direct lightweight helpers only;
- avoids deep nested readiness aggregation on the owner launch-review request;
- keeps full detailed readiness links available separately for admin/support;
- keeps the UI read-only and owner-safe.

## Changed files
- `repliq/legacy_app.py`
- `PROJECT_STATE.md`
- `REPLIQ_RULES.md`
- `STAGE87_2_LAUNCH_REVIEW_READINESS_FAST_PATH_HOTFIX.md`

## Not changed
- booking routing
- slots
- date/time parsing
- price side-question logic
- cancel/reschedule
- Google Calendar runtime
- Telegram runtime
- billing semantics
- CSRF
- abuse/rate-limit
- magic-link
- QA evaluator
- LLM orchestration
- voice/calls

## Expected deploy checks
- `/health`
- `/dialogue/qa`
- `/owner/launch-review/ui?tenant_id=clinic_demo`
- `/owner/launch-review?tenant_id=clinic_demo`
- `/owner-workspace/final-review/readiness?tenant_id=clinic_demo`
- `/owner/workspace/ui?tenant_id=clinic_demo`
- `/owner/dashboard/ui?tenant_id=clinic_demo`

Expected:
- `/dialogue/qa = 50/50 passed`
- Launch review UI loads actual checklist instead of staying on Loading.
- Final review readiness returns JSON quickly.
- Response contains `stage=87.2`, `fast_path=true`, `owner_workspace_final_review_ready=true` if route/security checks pass.
