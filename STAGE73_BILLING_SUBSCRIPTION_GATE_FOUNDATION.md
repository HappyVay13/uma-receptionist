# Stage 73 — Billing / Subscription Gate Foundation

Status: implemented in archive, awaiting deploy verification.

## Scope

Stage 73 adds a manual billing/subscription foundation for the existing self-serve SaaS path. It does not integrate Stripe or any live payment provider yet.

Added tenant billing fields via safe `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migration support:
- `billing_provider`
- `billing_customer_id`
- `billing_subscription_id`
- `billing_current_period_end`
- `billing_last_event_at`
- `billing_notes`

Existing lifecycle fields are reused and exposed consistently:
- `plan`
- `subscription_status`
- `dialogs_per_month`
- `trial_end`

Supported subscription statuses:
- `trial`
- `active`
- `past_due`
- `suspended`
- `inactive`
- `expired`

Aliases such as `paused`/`disabled` normalize to `suspended`; `cancelled`/`canceled` normalize to `inactive`.

## New protected admin endpoints

These routes are protected by the existing Stage 61/62 admin boundary:

- `GET /billing/readiness`
- `GET /billing/subscription/readiness`
- `GET /tenant/billing/readiness`
- `GET /tenant/billing`
- `GET /billing`
- `GET /tenant/billing/ui`
- `GET /billing/ui`
- `POST /tenant/billing/update`

Admin billing update supports:
- plan update;
- subscription status update;
- trial end update;
- billing provider metadata;
- billing customer/subscription identifiers;
- billing current period end;
- dialogs-per-month override/reset;
- internal billing notes.

No provider secrets are accepted, returned, or documented in this stage.

## New owner endpoints

These routes are protected by the existing Stage 71 signed owner session boundary, with the existing super-admin bypass preserved:

- `GET /owner/billing`
- `GET /owner/subscription`
- `GET /owner/billing/ui`
- `GET /owner/subscription/ui`

Owner billing is read-only in this stage. Owners can see their plan/status/runtime gate metadata but cannot update billing settings from owner surfaces.

## Integrated readiness surfaces

Stage 73 billing readiness is integrated into:

- `/internal/readiness`
- `/tenant/config`
- `/tenant/config/update`
- `/owner/dashboard`
- `/owner/dashboard/ui`
- `/control-center`
- `/control-center/readiness`
- `/public-saas/readiness`
- `/public-saas/gap-audit`
- `/public-saas/gap-audit/ui`

Stage 70 now marks billing/subscription lifecycle as `foundation` when the Stage 73 checks are ready, while `public_saas_ready` remains `false` by design.

## Runtime gate foundation

Stage 73 exposes billing/runtime gate metadata based on the existing SaaS lifecycle helpers.

- `trial`, `active` are allowed states.
- `past_due` remains allowed with attention metadata.
- `suspended`, `inactive`, and `expired` are blocked lifecycle states.

This stage adds metadata and admin controls only. It does not change booking dialogue, slot generation, confirmation, cancellation, rescheduling, Telegram webhook runtime, Google Calendar event mutation, or the QA evaluator.

## Expected verification after deploy

- `/dialogue/qa` = 50/50 passed.
- `/billing/readiness?tenant_id=clinic_demo` returns `stage=73` and `billing_subscription_gate_foundation_ready=true` for an existing tenant.
- `/tenant/billing?tenant_id=clinic_demo` returns billing status and is protected by admin session/token.
- `/tenant/billing/ui?tenant_id=clinic_demo` opens after admin login.
- `POST /tenant/billing/update` updates manual plan/status fields and does not expose secrets.
- `/owner/billing?tenant_id=<owner_tenant>` works only with a valid owner session or super-admin bypass.
- `/owner/billing/ui?tenant_id=<owner_tenant>` is read-only for owner mode.
- `/public-saas/readiness?tenant_id=clinic_demo` shows `billing_subscription` as foundation while `public_saas_ready=false` remains.
- Existing public signup and owner session flow from Stage 72 remains working.

## Security notes

- No Stripe/payment provider calls are made.
- No payment provider secret fields are exposed.
- No admin token is returned.
- No owner login code or login code hash is returned by billing surfaces.
- Owner billing is read-only in this stage.
- Admin billing write routes remain protected by Stage 61/62.

## Not changed

Receptionist core was not changed:

- booking routing;
- slot generation;
- date/time parsing;
- price side-question logic;
- confirmation;
- cancel/reschedule;
- Google Calendar event runtime;
- Telegram webhook runtime;
- dialogue QA evaluator;
- LLM orchestration;
- voice/calls.
