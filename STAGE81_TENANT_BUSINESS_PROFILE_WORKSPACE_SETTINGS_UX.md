# Stage 81 — Tenant Business Profile / Workspace Settings UX

Status: implemented in archive, awaiting deploy verification.

## Scope

Stage 81 continues the Mature SMB SaaS phase after Stage 80.

It adds an owner-safe business profile/settings surface so a client owner can complete practical workspace setup fields without opening the super-admin tenant config UI.

## Added owner-safe endpoints

- `GET /owner/business-profile`
- `GET /owner/business-profile/ui`
- `GET /owner/workspace/settings`
- `GET /owner/workspace/settings/ui`
- `POST /owner/business-profile/update`

The write endpoint is limited to non-secret business profile fields:

- `business_name`
- `language`
- `timezone`
- `work_start`
- `work_end`

## Added admin-protected readiness endpoints

- `GET /business-profile/readiness`
- `GET /owner-business-profile/readiness`
- `GET /workspace-settings/readiness`
- `GET /tenant/business-profile/readiness`

## Security boundaries

- Owner profile/settings routes are protected by the Stage 71 owner session and tenant binding.
- Super-admin support bypass remains available and explicit.
- `POST /owner/business-profile/update` is included in Stage 74 owner browser write/CSRF protection.
- Stage 81 readiness routes are protected by Stage 61/62 admin auth.
- Owner UI does not expose admin tenant config links as primary owner navigation.
- Raw admin tokens, owner login codes, magic tokens, token hashes, Telegram tokens, Google credentials, CSRF secrets, raw IPs and subject hashes are not exposed.

## Expected checks

- Render deploy starts successfully.
- `/dialogue/qa` remains `50/50 passed`.
- `/business-profile/readiness?tenant_id=clinic_demo` returns `stage=81`.
- `/owner-business-profile/readiness?tenant_id=clinic_demo` works and is admin-protected.
- `/workspace-settings/readiness?tenant_id=clinic_demo` works and is admin-protected.
- `/owner/business-profile/ui?tenant_id=<owner_tenant>` opens with valid owner session.
- `/owner/workspace/settings/ui?tenant_id=<owner_tenant>` opens with valid owner session.
- Saving language/timezone/working hours through owner UI returns `ok=true`.
- Stage 80 workspace setup completion reflects the updated business profile fields.
- Owner dashboard/workspace/billing remain owner-safe.

## Explicit non-scope

Stage 81 does not change receptionist dialogue, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook runtime, billing semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, QA evaluator rules, or voice/calls.
