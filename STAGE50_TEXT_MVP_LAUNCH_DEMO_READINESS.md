# Stage 50 — Text MVP Launch Demo Readiness

## Baseline
- Confirmed before this stage: Stage 49 deployed with `/dialogue/qa = 50/50 passed`.
- Confirmed before this stage: `/internal/readiness?tenant_id=clinic_demo` returned `status = ok`, `qa.protected_baseline = 50/50`, `scenario_count = 50`, `product_scope.current_mvp_channel = text`, and `text_channel_smoke.stage = 49`.
- User manually ran the proposed live text smoke checks across RU/LV/EN text flows and reported that the proposed tests worked and appointments were created successfully.
- Current launch scope remains text-first receptionist. Voice/calls are future phase only.

## Purpose
Stage 50 prepares Repliq for a client-facing text MVP demo. It does not add new receptionist behavior. It makes the demo scope and boundaries explicit in readiness metadata and documentation so the next work can focus on demo packaging, tenant settings, business memory/service catalog management, and client onboarding.

## Code impact
No conversational behavior was changed.

Changed runtime surface only:
- `/internal/readiness` now includes read-only `client_demo_readiness` metadata.

The metadata is informational only. It does not run a demo, call an LLM, mutate conversation state, or create/update/delete Google Calendar events.

## Current demo candidate status
A tenant is considered a demo candidate only if readiness status is `ok` and tenant readiness is `ready`.

For the current protected baseline, expected readiness after deploy:

```text
/internal/readiness.status = ok
/internal/readiness.qa.protected_baseline = 50/50
/internal/readiness.product_scope.current_mvp_channel = text
/internal/readiness.client_demo_readiness.stage = 50
/internal/readiness.client_demo_readiness.status = candidate
```

## Recommended client demo order
Use `/dev_chat_ui` first, because it isolates the core text receptionist from Telegram/WhatsApp transport noise.

Recommended 3–5 minute demo:
1. Show readiness: `/internal/readiness?tenant_id=clinic_demo`.
2. Show `/dev_chat_ui` as the text demo channel.
3. Run RU booking with price side-question:
   - `хочу записаться на консультацию завтра вечером`
   - `сколько это стоит?`
   - `2`
   - `да`
4. Show the created Google Calendar event.
5. Run RU reschedule:
   - `перенести запись`
   - `послезавтра вечером`
   - `2`
   - `да`
6. Show the same Google Calendar event updated, not duplicated.
7. Run cancel:
   - `отменить запись`
8. Show the event removed.
9. Optionally show the LV path if the audience cares about multilingual behavior.

## Demo positioning
Position Repliq as:
- text-first AI receptionist for SMB appointments;
- appointment booking/reschedule/cancel assistant;
- Google Calendar-connected receptionist;
- multilingual text receptionist with RU/LV protected regression and EN smoke tested manually;
- SaaS-ready direction, but not yet a fully polished SaaS dashboard product.

Do not position current MVP as:
- production voice agent;
- phone-call receptionist;
- finished multi-tenant SaaS self-serve platform;
- fully client-admin editable business memory/service catalog without further hardening.

## What is ready to show
- Text booking flow.
- Side questions inside booking flow.
- Localized RU price UX.
- Slot choice and confirmation.
- Reschedule using calendar update path.
- Cancel using calendar delete path.
- Readiness endpoint showing text-first scope and baseline.

## What should be hardened next
Recommended next stage after Stage 50:

```text
Stage 51 — Tenant Config / Business Memory Admin Hardening
```

Reason: the text receptionist core is now stable, so the next practical product layer is safer client/business configuration:
- service catalog editing;
- price/business memory editing;
- opening hours/address editing;
- tenant config validation;
- clearer admin UI boundaries;
- safe preview/test before client launch.

## Safety boundaries
- Do not change booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, or Google Calendar mutation logic during Stage 50.
- Do not add voice/call requirements to the active MVP scope.
- Readiness metadata may expose demo scope, but must not run smoke/demo flows or mutate live data.
- Any live demo issue must be handled in a separate fix stage with exact transcript, channel, user id/phone, and observed Google Calendar result.
