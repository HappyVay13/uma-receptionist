# Stage 73.1 — Billing Update Route Import Hotfix

Status: implemented in hotfix archive, awaiting deploy verification.

## Root cause

Stage 73 added `POST /tenant/billing/update` with this route signature:

```python
def tenant_billing_update(payload: TenantBillingUpdateRequest):
```

In the current legacy single-file app, `TenantBillingUpdateRequest` is declared later in the file. Render runs Python 3.14, and FastAPI inspects endpoint annotations during route registration. That caused import/startup failure before the app could start:

```text
NameError: name 'TenantBillingUpdateRequest' is not defined
```

## Fix

The route signature now avoids the forward model reference at import time:

```python
def tenant_billing_update(payload: dict = Body(...)):
```

The same Pydantic model is still used, but instantiated at request handling time:

```python
TenantBillingUpdateRequest(**(payload or {}))
```

This keeps validation behavior while making app import/startup safe.

## Files changed

- `repliq/legacy_app.py`
- `PROJECT_STATE.md`
- `REPLIQ_RULES.md`
- `STAGE73_1_BILLING_UPDATE_ROUTE_IMPORT_HOTFIX.md`

## Not changed

- booking routing;
- slot generation;
- date/time parsing;
- price side-question logic;
- confirmation;
- cancel/reschedule;
- Google Calendar runtime;
- Telegram webhook runtime;
- dialogue QA evaluator;
- LLM orchestration;
- billing semantics from Stage 73.

## Local checks

- `python -m py_compile app.py repliq/legacy_app.py channels/telegram.py db/runtime_tables.py config/settings.py`
- `python -m compileall -q app.py repliq channels config core db integrations services saas uma`
- AST parse check
- Static FastAPI endpoint annotation scan: no endpoint uses a request-model annotation defined later in the file.
- Static `/tenant/billing/update` route check.

## Expected deploy verification

- Render app starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/billing/readiness?tenant_id=clinic_demo` returns Stage 73 readiness.
- `/tenant/billing?tenant_id=clinic_demo` remains admin protected.
- `POST /tenant/billing/update` remains admin protected and validates payload at call time.
- `/owner/billing?tenant_id=<owner_tenant>` still works with owner session.
- `/public-saas/readiness?tenant_id=clinic_demo` still shows billing/subscription as foundation while `public_saas_ready=false` remains.
