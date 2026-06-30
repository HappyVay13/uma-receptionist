# Stage 83 — Business Memory / FAQ Owner UX Polish

## Goal
Move Business Memory / FAQ editing from admin-only builder into an owner-safe SMB workspace surface.

## Added owner-safe endpoints
- `GET /owner/business-memory`
- `GET /owner/business-memory/ui`
- `GET /owner/faq`
- `GET /owner/faq/ui`
- `POST /owner/business-memory/update`
- `POST /owner/faq/update`

## Added readiness endpoints
- `GET /owner-business-memory/readiness`
- `GET /owner-faq/readiness`
- `GET /business-memory/owner/readiness`
- `GET /workspace/memory/readiness`

## Security
- Owner routes require Stage 71 owner session and tenant binding.
- Owner write routes are added to Stage 74 owner CSRF/browser-write hardening.
- Readiness routes are protected by Stage 61/62 admin auth.
- Owner UI does not expose admin builder/config links as primary owner navigation.
- No raw admin tokens, owner login codes, magic tokens, token hashes, CSRF secrets, IP hashes, Telegram tokens, Google credentials, or secrets are exposed.

## Not changed
Receptionist dialogue, booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls are not changed.

## Verification
- `/dialogue/qa` remains 50/50 passed.
- `/owner-business-memory/readiness?tenant_id=clinic_demo` returns Stage 83 readiness.
- `/owner/business-memory/ui?tenant_id=<owner_tenant>` opens with owner session or super-admin bypass.
- Owner memory/FAQ save returns `ok=true`.
- Stage 80 business_memory next-action points to `/owner/business-memory/ui`.
