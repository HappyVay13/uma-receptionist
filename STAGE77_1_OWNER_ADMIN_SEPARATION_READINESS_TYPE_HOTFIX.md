# Stage 77.1 — Owner/Admin Separation Readiness Type Hotfix

## Problem

After Stage 77 deploy, `/owner-admin-separation/readiness?tenant_id=clinic_demo` returned `Internal Server Error`.

## Root cause

The Stage 77 readiness payload attempted to union `STAGE76_PUBLIC_MAGIC_LOGIN_PATHS` with `STAGE72_PUBLIC_SIGNUP_PUBLIC_PATHS` using `|`. In the actual code, one collection is a `set` and the other is a `tuple`, causing a runtime `TypeError` when the readiness endpoint is called.

## Fix

Convert both collections to sets before union:

```python
set(STAGE76_PUBLIC_MAGIC_LOGIN_PATHS) | set(STAGE72_PUBLIC_SIGNUP_PUBLIC_PATHS)
```

## Scope

Changed only Stage 77 readiness payload construction.

Not changed:

- receptionist dialogue
- booking routing
- slot generation
- date/time parsing
- confirmation/cancel/reschedule
- Google Calendar runtime
- Telegram webhook runtime
- billing semantics
- CSRF semantics
- abuse/rate-limit semantics
- magic-link auth semantics
- QA evaluator

## Expected post-deploy checks

- `/health` works
- `/dialogue/qa` remains `50/50 passed`
- `/owner-admin-separation/readiness?tenant_id=clinic_demo` returns JSON, not 500
- `/tenant/isolation/readiness?tenant_id=clinic_demo` returns JSON, not 500
- `/public-saas/readiness?tenant_id=clinic_demo` opens and still has `public_saas_ready=false` before Stage 78
