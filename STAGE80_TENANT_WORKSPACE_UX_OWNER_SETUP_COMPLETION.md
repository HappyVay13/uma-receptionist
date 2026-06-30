# Stage 80 — Tenant Workspace UX / Owner Setup Completion

Status: implemented in archive, awaiting deploy verification.

Purpose: continue the Mature SMB SaaS phase by turning the owner workspace into a practical setup-completion surface for real SMB clients, while keeping admin/support configuration surfaces separated from the client owner UI.

Scope:
- Added owner-safe workspace/setup endpoints:
  - `GET /owner/setup`
  - `GET /owner/setup/ui`
  - `GET /owner/workspace`
  - `GET /owner/workspace/ui`
  - `GET /owner/workspace/setup`
  - `GET /owner/workspace/setup/ui`
- Added admin-protected Stage 80 readiness endpoints:
  - `GET /tenant-workspace/readiness`
  - `GET /workspace/readiness`
  - `GET /owner-setup/readiness`
  - `GET /owner/setup-completion/readiness`
- Added Stage 80 setup-completion payload with tasks for:
  - business profile
  - service catalog
  - business memory / FAQ
  - Google Calendar
  - Telegram text channel
  - billing/subscription gate
  - owner auth
  - Stage 78 launch lock
- Added owner-safe workspace UI with setup checklist, next actions, completion percentage, and links to owner dashboard/billing/session.
- Integrated Stage 80 metadata into the existing owner dashboard payload and quickstart links.

Security / boundaries:
- Stage 80 readiness endpoints are protected by Stage 61/62 admin auth.
- Stage 80 owner workspace/setup endpoints are protected by Stage 71 owner session and tenant binding.
- Owner workspace links are owner-safe and do not expose admin write/config links.
- Support-controlled setup items are shown as support-controlled instead of exposing admin configuration screens.
- Raw admin tokens, owner login codes, magic tokens/hashes, Telegram tokens, Google credentials, CSRF secrets, raw IPs, and subject hashes are not exposed.
- Stage 78 remains the source of truth for `public_saas_ready`.
- `enterprise_saas_ready` remains false.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/tenant-workspace/readiness?tenant_id=clinic_demo` returns `stage=80`.
- `/workspace/readiness?tenant_id=clinic_demo`, `/owner-setup/readiness?tenant_id=clinic_demo`, and `/owner/setup-completion/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/setup/ui?tenant_id=<owner_tenant>` opens for a valid owner session.
- `/owner/workspace/ui?tenant_id=<owner_tenant>` opens for a valid owner session.
- `/owner/setup?tenant_id=<owner_tenant>` returns Stage 80 setup-completion JSON.
- Owner dashboard still opens and includes Stage 80 workspace/setup links.
- Owner billing still works.
- `/public-saas/final-readiness?tenant_id=clinic_demo` remains the Stage 78 launch lock source of truth.

Notes:
- `tenant_workspace_ux_ready=true` means the Stage 80 workspace/readiness/security surfaces are wired correctly.
- `workspace_setup_complete=false` or `status=attention` can be normal if some tenant setup tasks still need support/admin completion.
- Setup incompleteness should appear in `warnings`/`next_actions`, not as a receptionist core regression.

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

Enterprise note: Stage 80 is Mature SMB SaaS workspace/setup UX, not enterprise maturity. `enterprise_saas_ready` remains false.
