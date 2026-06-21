# Stage 62 — Admin Login / Session Layer

## Purpose

Stage 62 adds a browser-friendly admin login/session layer on top of the Stage 61 shared admin-token enforcement.

This stage is a self-serve SaaS transition step: operators no longer need to keep opening admin pages with `?admin_token=...`. Instead, `/admin/login` accepts the existing `REPLIQ_ADMIN_TOKEN`, then sets a signed HttpOnly admin session cookie.

## Scope

Changed files:

- `repliq/legacy_app.py`
- `PROJECT_STATE.md`
- `REPLIQ_RULES.md`
- `README.md`
- `STAGE62_ADMIN_LOGIN_SESSION_LAYER.md`

## Added endpoints

- `GET /admin/login`
- `POST /admin/login`
- `GET /admin/logout`
- `POST /admin/logout`
- `GET /admin/session`
- `GET /admin/session/readiness?tenant_id=clinic_demo`

## Behavior

- Protected admin surfaces still require Stage 61 access.
- Browser users can now open `/admin/login`, enter the shared admin token, and receive a signed session cookie.
- The session cookie is HttpOnly, SameSite=Lax, and Secure when `SERVER_BASE_URL` is HTTPS.
- Legacy token headers and `admin_token` query bootstrap remain supported for transition.
- Query-token bootstrap now writes the signed Stage 62 session cookie instead of relying on a raw-token browser cookie.
- Logout clears both the Stage 62 signed session cookie and the legacy Stage 61 raw-token cookie.

## Readiness

`/internal/readiness` now includes:

```json
"admin_session_readiness": {
  "stage": "62",
  "status": "ready",
  "admin_session_layer_ready": true
}
```

`/tenant/config` also includes `admin_session_readiness`.

## UI

Added admin session/login/logout links to:

- `/tenant/config/ui`
- `/dashboard`

## What this is not

Stage 62 is not final public SaaS authentication.

Still required before public SaaS:

- per-owner email/magic-link accounts;
- tenant owner identity in DB;
- tenant ownership checks;
- CSRF protection for browser write endpoints;
- client-owner vs super-admin role separation.

## Protected baseline

This stage does not change receptionist core behavior:

- no booking routing changes;
- no slot generation changes;
- no confirmation-flow changes;
- no cancel/reschedule changes;
- no Google Calendar runtime changes;
- no Telegram webhook changes;
- no regression evaluator changes.

## Verification

Run after deploy:

1. `/dialogue/qa` → expected `50/50 passed`.
2. Open a protected endpoint without auth → expected `admin_token_required`.
3. Open `/admin/login?tenant_id=clinic_demo` and log in with `REPLIQ_ADMIN_TOKEN`.
4. Open `/admin/session` → expected `authenticated=true`.
5. Open `/internal/readiness?tenant_id=clinic_demo` after login → expected OK through session cookie.
6. Open `/admin/session/readiness?tenant_id=clinic_demo` → expected `stage=62`, `status=ready`.

## Commit message

`Stage 62: add admin login session layer`
