# Stage 70 — Public SaaS Readiness Gap Audit

Status: implemented in archive, pending deploy verification.

## Scope

Stage 70 adds a read-only factual public SaaS readiness gap audit.

It does not turn `public_saas_ready` to true. It makes the remaining public launch blockers explicit from the current code state while preserving the confirmed text-first MVP baseline.

## Added endpoints

Protected by the Stage 61/62 admin layer:

- `/public-saas/readiness`
- `/public-saas/gap-audit`
- `/public-saas/gap-audit/ui`
- `/public-saas/readiness/ui`
- `/saas/public-readiness`
- `/saas/public-readiness/ui`
- `/launch/public-readiness`
- `/launch/public-readiness/ui`

## What the audit reports

The audit aggregates existing readiness/self-serve blocks:

- Stage 61 admin access enforcement
- Stage 62 admin session layer
- Stage 58 access boundaries
- Stage 69 client control center
- Stage 54 launch readiness
- Stage 63 tenant creation
- Stage 64 onboarding wizard
- Stage 65 Google Calendar self-serve
- Stage 66 service catalog builder
- Stage 67 Business Memory / FAQ builder
- Stage 68 Telegram setup
- Stage 57 usage analytics

## Explicit public SaaS blockers

The audit keeps `public_saas_ready=false` and reports the current blockers:

- per-owner public auth is missing;
- tenant ownership / role checks are missing;
- public signup boundary is not open yet;
- billing/subscription lifecycle is only a foundation, not a provider-backed lifecycle;
- browser write endpoints need public-session CSRF/write hardening before public owner access;
- client-owner and super-admin surfaces are not separated yet;
- public SaaS ops/rate limits/billing-grade usage proof are not complete.

## Integrated surfaces

Stage 70 is exposed through:

- `/internal/readiness` as `public_saas_gap_audit_readiness`;
- `/tenant/config` and `/tenant/config/update` as `public_saas_gap_audit_readiness`;
- onboarding links payload;
- Control Center links;
- Dashboard quick links;
- Tenant Config UI quick links.

## Not changed

Receptionist core was not changed:

- booking routing;
- slot generation;
- date/time parsing;
- price side-question logic;
- confirmation;
- cancel/reschedule;
- Google Calendar event create/update/delete runtime;
- Telegram webhook runtime;
- dialogue QA evaluator;
- voice/calls.

## Expected verification

- `/dialogue/qa` = 50/50 passed.
- `/public-saas/readiness?tenant_id=clinic_demo` returns `stage=70`.
- `/public-saas/gap-audit/ui?tenant_id=clinic_demo` opens after admin login/session.
- `/internal/readiness?tenant_id=clinic_demo` includes `public_saas_gap_audit_readiness`.
- `/tenant/config?tenant_id=clinic_demo` includes `public_saas_gap_audit_readiness` and does not expose secrets.
- `/dashboard?tenant_id=clinic_demo` and `/tenant/config/ui?tenant_id=clinic_demo` include a Public SaaS audit link.
- `public_saas_ready` remains `false`.
