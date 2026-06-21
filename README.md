# uma-receptionist
## Stage 61 — Admin Access Enforcement

Stage 61 adds a minimal shared admin-token protection layer for internal/admin/demo surfaces. Set `REPLIQ_ADMIN_TOKEN` in the deployment environment before opening protected admin pages. Use `X-Repliq-Admin-Token` or `Authorization: Bearer <token>` for API checks; for browser checks open a protected page once with `?admin_token=<token>` to set the HttpOnly admin cookie. This is an MVP/private-admin access layer, not final public SaaS authentication.
