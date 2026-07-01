# Stage 87.1 — Launch Review UI Bootstrap Hotfix

## Status
Implemented as a minimal hotfix after Stage 87 deploy UI observation.

## Observed issue
The owner launch checklist page loaded, but the browser-side UI did not initialize correctly:

- `tenant_id` field stayed empty on `/owner/launch-review/ui?tenant_id=clinic_demo`.
- Manual tenant input + `Load` did not trigger visible loading.
- `Workspace`, `Dashboard`, and `Logout` buttons did not respond.

## Root cause from code inspection
The Stage 87 launch review HTML used a dense one-line inline script with inline `onclick` handlers and several nested template literals. The backend route definitions and Stage 87 JSON/readiness aggregation remained intact, but the UI bootstrap was fragile: if the browser failed to initialize that script, none of the global functions used by inline buttons existed and the tenant field was never populated.

## Fix
Replaced only `stage87_owner_launch_review_html()` with a more defensive owner UI bootstrap:

- Reads `tenant_id` directly from `window.location.search` first.
- Falls back to backend-provided `DEFAULT_TENANT_ID`, then `clinic_demo`.
- Populates the tenant input on boot before loading JSON.
- Uses explicit button IDs and `onclick` bindings from JS instead of relying only on inline handlers.
- Exposes `loadReview`, `go`, and `encTenant` on `window` for compatibility.
- Replaces `String.replaceAll()` usage with regex-based escaping for broader browser compatibility.
- Avoids nested template literal rendering in the launch checklist UI.
- Shows a visible error in the Raw block if `/owner/launch-review` returns non-JSON, HTTP error, or fetch failure.

## Scope intentionally not changed

- No backend readiness logic changed.
- No owner/session auth logic changed.
- No owner write routes added.
- No CSRF paths added.
- No booking, slots, date parsing, price side-question, cancel/reschedule, Calendar runtime, Telegram runtime, billing, abuse/rate-limit, magic-link, LLM orchestration, or QA evaluator changes.

## Verification expected

- `/owner/launch-review/ui?tenant_id=clinic_demo` pre-fills `clinic_demo` immediately.
- `Load` triggers `/owner/launch-review?tenant_id=clinic_demo` and renders status/review items/next actions or visible JSON error.
- `Workspace` navigates to `/owner/workspace/ui?tenant_id=clinic_demo`.
- `Dashboard` navigates to `/owner/dashboard/ui?tenant_id=clinic_demo`.
- `Logout` navigates to `/owner/logout`.
- `/dialogue/qa` remains 50/50 passed.
