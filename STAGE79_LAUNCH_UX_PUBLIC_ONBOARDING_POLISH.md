# Stage 79 — Launch UX / Public Onboarding Polish

Status: implemented in archive, awaiting deploy verification.

Purpose: start the Mature SMB SaaS phase after Stage 78 by polishing the client-facing public signup, public launch page, and owner workspace UX while preserving the Stage 78 launch lock and all security boundaries.

Scope:
- Added public launch landing pages:
  - `GET /launch`
  - `GET /launch/ui`
  - `GET /public/launch`
  - `GET /public/launch/ui`
- Added admin-protected Stage 79 readiness endpoints:
  - `GET /launch-ux/readiness`
  - `GET /public-onboarding/readiness`
  - `GET /smb/launch/readiness`
  - `GET /mature-smb/readiness`
- Added Stage 79 launch UX readiness payload with gates for:
  - Stage 78 final launch lock still ready
  - public signup boundary still public and usable
  - public launch entrypoint remains public
  - owner workspace home is owner-session bound
  - owner billing remains visible to owner
  - Stage 79 readiness endpoints are admin protected
- Polished public signup copy from technical Stage 72 wording to client-facing workspace wording.
- Public signup UI no longer renders raw login code / magic-link token / magic-link URL in its technical details block; values are replaced with `[returned_once_hidden_in_launch_ui]` in the UI details.
- Public signup API response now returns owner-safe links only in its main `links` block and marks admin setup links as not exposed to public signup.
- Added Stage 79 metadata to the owner dashboard payload.
- Owner dashboard UI renamed to a customer-facing `Repliq Workspace` and now shows an owner-safe quickstart block.

Security / boundaries:
- Stage 79 readiness endpoints are protected by Stage 61/62 admin auth.
- Public launch pages are public GET pages only.
- Public signup remains public and rate-limited.
- Owner dashboard and owner billing remain protected by Stage 71 owner session and tenant binding.
- Admin write/config links are not exposed in the public signup response main links block.
- Raw admin tokens, login-code hashes, magic-token hashes, CSRF secrets, raw IPs, Telegram tokens, and Google credentials are not exposed.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/launch` opens as a public customer-facing landing page.
- `/public/signup` opens with the new customer-facing wording.
- `/launch-ux/readiness?tenant_id=clinic_demo` returns `stage=79` and `launch_ux_polish_ready=true` when Stage 78 gates remain ready.
- `/public-onboarding/readiness?tenant_id=clinic_demo` works and is admin-protected.
- `/smb/launch/readiness?tenant_id=clinic_demo` works and is admin-protected.
- `/mature-smb/readiness?tenant_id=clinic_demo` works and is admin-protected.
- Public signup still creates a tenant/owner session.
- Public signup UI technical details hide one-time secret values.
- Public signup API response main `links` block contains owner-safe links only.
- `/owner/dashboard/ui?tenant_id=<owner_tenant>` opens and shows the Stage 79 workspace/quickstart UI.
- `/owner/billing/ui?tenant_id=<owner_tenant>` still works.
- `/public-saas/final-readiness?tenant_id=clinic_demo` remains OK and continues to be the source of truth for `public_saas_ready`.

Not changed:
- receptionist dialogue routing
- slot generation
- date/time parsing
- price side-question logic
- confirmation
- cancellation/rescheduling
- Google Calendar event runtime
- Telegram webhook runtime
- billing semantics
- CSRF semantics
- abuse/rate-limit semantics
- magic-link semantics
- dialogue QA evaluator
- LLM orchestration
- voice/calls

Enterprise note: Stage 79 is Mature SMB SaaS launch UX polish, not enterprise maturity. `enterprise_saas_ready` remains false.
