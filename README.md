# uma-receptionist
## Stage 62 — Admin Login / Session Layer

Stage 62 adds `/admin/login`, `/admin/logout`, `/admin/session`, and `/admin/session/readiness`. The existing `REPLIQ_ADMIN_TOKEN` is used as the MVP admin credential; successful browser login sets a signed HttpOnly session cookie so protected admin pages can be opened without repeatedly passing `admin_token` in URLs. This is still a private-admin/self-serve transition layer, not final public SaaS per-user auth.

## Stage 61 — Admin Access Enforcement

Stage 61 adds a minimal shared admin-token protection layer for internal/admin/demo surfaces. Set `REPLIQ_ADMIN_TOKEN` in the deployment environment before opening protected admin pages. Use `X-Repliq-Admin-Token` or `Authorization: Bearer <token>` for API checks; for browser checks open a protected page once with `?admin_token=<token>` to set the HttpOnly admin cookie. This is an MVP/private-admin access layer, not final public SaaS authentication.
