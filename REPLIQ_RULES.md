# Repliq Conversational Rules

Core rule: LLM is an understanding layer only. Booking actions remain controlled by orchestration/state logic.

Current protected baseline:
- `/dialogue/qa` confirmed after Stage 75 deploy: 50/50 passed. Stage 76 must preserve this baseline.
- Stage 41.1 hardens cross-language grounded price lookup while preserving booking flow.
- Stage 42 is a documentation/audit checkpoint only.
- Stage 43A adds production readiness checks without changing conversational behavior.
- Stage 44 adds cancellation/reschedule regression harness coverage without changing runtime cancellation/rescheduling behavior.
- Stage 45 may complete reschedule continuation only after preserving `reschedule_event_id` and the original calendar-event service context.
- Do not change conversational behavior unless a new archive + logs/regression output prove the need.

## Global production rules
- Do not reset an active booking flow unless the user clearly cancels or starts a new incompatible task.
- Preserve known service/date/time whenever possible.
- Preserve offered slots while answering side-questions inside an active booking flow.
- Do not answer from invented business facts. Use tenant settings, service catalog, business memory, or known runtime state.
- Booking/calendar actions must remain deterministic and orchestration-controlled.
- Do not relax regression evaluator rules to make tests pass.

## Stage 36 recovery rules
- Do not reset an active booking flow on vague answers.
- Preserve known service/date/time whenever possible.
- If user says they do not know, offer context-aware slots if date/service are known.
- If user rejects the day, move to date selection.
- If user rejects the time, move to time selection.
- If user asks to wait, preserve state and acknowledge without clearing context.
- Existing Stage 24–35 behavior must remain protected by `/dialogue/qa`.

### Stage 36.1 — Semantic Recovery Continuity
- Preserves fuzzy time windows across recovery turns such as not tomorrow -> day after tomorrow.
- Improves uncertain/hold recovery language without changing booking actions.
- Booking/calendar execution logic remains unchanged.

### Stage 36.2 Rule
If the user corrects the day and then gives a new date, Repliq must immediately continue slot offering using the existing service and fuzzy time context. Do not ask for the date again when the new date is already provided.

### Stage 36.3 Rule
Semantic Date Shift Continuity preserves fuzzy time windows when user changes date after rejecting the previous one, e.g. `ne rīt` -> `parīt`.

## Stage 37 — Temporal Semantic Engine
- Added centralized temporal recovery for relative dates.
- Latvian `rīt/parīt/aizparīt` maps to +1/+2/+3 days in the current project logic.
- Date-shift recovery preserves fuzzy time context and avoids morning fallback.

### Stage 37.1 — Temporal Engine Window Preservation
- Fixed fuzzy time window persistence for `rīt vakarā`.
- Fixed negative-only `ne rīt` so it does not resolve back to tomorrow.
- `parīt` and `aizparīt` should regenerate contextual evening slots instead of morning fallback.

### Stage 37.2 temporal rules
- If the user gives a replacement relative date (`parīt`, `aizparīt`) inside an active booking flow, regenerate slots immediately.
- Do not ask for the date again after a replacement date was provided.
- If the user says `jā, der` while slot options are visible, treat it as choosing the first offered slot and move to confirmation.

### Stage 37.3 Rule
When the user is in `AWAITING_TIME` and offered slots exist, short positive Latvian replies such as `jā, der`, `ja der`, `der`, `labi`, or `apstiprinu` must select the first offered slot and move to `AWAITING_CONFIRM`. They must not re-open date selection.

## Stage 38 — Business Memory Intelligence / FAQ Rules Hardening
- Generic FAQ/business-memory answers across tenant business types.
- Side-question handling preserves active booking flow.
- Regression scenarios protect price, hours and location questions.

### Stage 38.1 — Price Side-question FAQ Fix
- Price side-questions inside active booking flow are answered from business memory/service context.
- Existing booking context is preserved.
- No calendar/orchestration booking logic changed.

### Stage 38.2 Rule
When the user asks a price question during an active booking flow, answer the price from grounded business memory/service data first, then continue the same booking flow with the existing offered slots.

### Stage 38.3 Rule
If a result already contains a preserved active-flow FAQ answer (`flow_preserved` or `stage38_business_faq`), final text polishing layers must not rewrite it into a generic slot prompt.

Required behavior for price side-question during booking:
1. Answer the grounded price from service/business memory.
2. Keep the active booking state.
3. Repeat or continue the current slot-selection prompt.
4. Keep the same reply language.

Example protected scenario:
- `gribu pierakstīties uz konsultāciju rīt vakarā`
- `cik tas maksā?`
- `jā, der`

Expected:
- price answered;
- booking flow preserved;
- Latvian reply preserved;
- positive acknowledgement selects the first offered slot for confirmation.

## Stage 39 — Regression Baseline Lock & Project State Sync
- Documentation checkpoint only.
- No routing changes.
- No booking/calendar behavior changes.
- No evaluator relaxation.
- Future changes must start from the confirmed 15/15 baseline.


## Stage 40 — Regression Matrix Expansion Rules
- Stage 40 may add regression scenarios, but must not change booking routing or response generation.
- New scenarios must protect already-working behavior only.
- Do not add known-failing candidate checks into the main `/dialogue/qa` matrix unless the same stage also performs a root-cause fix and proves the full matrix passes.
- Do not relax evaluator rules to make new tests pass.
- Candidate gaps discovered during Stage 40 are backlog items for Stage 41, not hidden fixes.

Stage 40 candidate gaps for Stage 41 analysis:
1. RU price side-question inside active booking flow should answer grounded price and preserve slots.
2. LV hours side-question inside active booking flow should answer hours and preserve slots.


## Stage 41 — Side-question Coverage Hardening Rules
- RU price side-questions inside active booking flow must answer grounded service price and preserve the existing slot-selection flow.
- Russian business-memory prices written as `10 евро` are valid grounded prices and must be extracted by `_extract_price_from_line()`.
- LV hours side-questions such as `cikos jūs strādājat?` inside active booking flow must be handled as business FAQ, not as missing date/time.
- After answering the side-question, Repliq must keep the same active booking state and continue with offered slots.
- Regression matrix now protects 30 scenarios total after Stage 41.


### Stage 41.1 Rule
If a price question is asked inside an active booking flow and the current language business-memory blob does not contain the price, Repliq may search the tenant's other language business-memory fields for the same service before falling back to an unknown-price response. This is allowed only for grounded FAQ lookup and must not change booking state, calendar logic, or slot generation.


## Stage 42 — Production Readiness Audit Rules
- Stage 42 is documentation-only.
- Confirmed protected baseline is `/dialogue/qa` = 30/30 passed.
- Do not change booking routing, calendar behavior, state transitions, side-question behavior, or evaluator logic during Stage 42.
- Cancellation/rescheduling must not be modified blindly: existing code must first be protected with a dedicated safe-mode regression harness.
- SaaS tenant foundation must not be treated as production-ready until tenant/admin access, config validation, and readiness checks are protected by tests.
- Recommended next stage is Stage 43A production hardening before behavior expansion.


## Stage 43A — Production Hardening Rules
- Stage 43A may add read-only/internal readiness checks only.
- Do not change booking routing, calendar behavior, state transitions, side-question handling, cancellation/rescheduling behavior, or evaluator logic during Stage 43A.
- Readiness endpoints must not expose secret values; they may report boolean presence flags only.
- Readiness endpoints must not run `/dialogue/qa`, call LLMs, mutate conversation state, or create/update/delete calendar events.
- Protected baseline remains `/dialogue/qa` = 30/30 passed.
- Cancellation/rescheduling remains a separate future stage and must first be covered by a dedicated regression harness.


## Stage 44 — Cancellation/Reschedule Regression Harness Rules
- Stage 44 may add regression-safe test fixtures, but only inside Stage 35 calendar safe mode.
- Runtime `find_next_event_by_phone`, `delete_calendar_event`, and `update_calendar_event` behavior must remain unchanged outside regression safe mode.
- Regression fixtures must be explicit per scenario via `calendar_event_fixture`; no real Google Calendar events may be read, created, updated, or deleted by `/dialogue/qa`.
- Do not change cancellation/rescheduling user-facing behavior during Stage 44.
- Protected Stage 44 behaviors:
  - no active booking cancellation/reschedule returns a grounded no-active-booking response;
  - fixture-backed cancellation reaches `cancelled`;
  - fixture-backed reschedule starts `reschedule_wait` and stores `reschedule_event_id`;
  - aborting reschedule clears reschedule pending data and keeps the current booking.
- Full reschedule continuation is Stage 45 scope and must start with root-cause analysis from QA output/logs.


## Stage 45 — Reschedule Flow Completion Rules
- Reschedule continuation must preserve `reschedule_event_id`, `reschedule_old_iso`, `reschedule_summary`, and `reschedule_description` until final confirmation or explicit abort.
- When a reschedule starts from an existing calendar event, infer and persist the original service from the event summary/description if possible. This prevents asking for the service again after `перенести запись` / `pārcelt pierakstu`.
- A new date/time answer inside reschedule flow must regenerate slots using the preserved service and language.
- A numeric slot choice or positive acknowledgement after reschedule slot options must move to confirmation.
- Final yes confirmation must call the existing reschedule update path, not create a separate new booking.
- Stage 35 calendar safe mode must still prevent real Google Calendar mutation during `/dialogue/qa`.
- Do not relax evaluator rules to make Stage 45 pass.


## Stage 45.1 — Reschedule Slot Evaluator Calibration Rules
- Stage 45.1 may only correct QA evaluator detection for multi-slot offers already present in the conversation.
- Do not change conversational routing, slot generation, cancellation/reschedule runtime logic, or calendar mutation logic in this stage.
- A full reschedule flow may end with a single confirmed time in the final assistant turn; `multiple_slot_options` must therefore be detected from the turn where slot options were actually offered, not only from the final turn.
- The evaluator may use existing `pending.offered_slots` and visible assistant text via `_turn_times()` to determine whether multiple slot options were presented.

## Stage 46 — Calendar Runtime Cancel/Reschedule Hardening Rules
- Completed reschedule flows must preserve action-specific wording: the final reply must say that the appointment was moved/rescheduled, not that a new booking was made.
- The reschedule finalization path must continue using `update_calendar_event()` whenever `pending.reschedule_event_id` is present.
- The cancellation success path must continue using `delete_calendar_event()` and may expose safe audit metadata such as `calendar_action=delete_event`.
- Safe metadata added for regression/audit (`calendar_action`, `reschedule_finalized`) must not expose secrets or Google event contents beyond already-visible action type.
- Stage 35 calendar safe mode must continue preventing real Google Calendar create/update/delete mutation during `/dialogue/qa`.
- Do not change slot generation, service inference, date parsing, or booking side-question behavior in Stage 46 unless a new root cause is proven by QA output/code.

## Stage 47 — Live Calendar E2E Smoke Audit Rules
- Stage 47 is an audit/checklist and baseline-sync stage.
- Do not change conversational routing, slot generation, date parsing, business FAQ/side-question handling, cancellation flow, reschedule flow, or Google Calendar create/update/delete functions during Stage 47.
- `/dialogue/qa` remains the safe-mode regression proof and must stay 48/48.
- Live Google Calendar behavior must be verified manually through a real channel because regression safe mode intentionally does not mutate Google Calendar.
- Live smoke must confirm that booking creates one event, reschedule updates that same event, cancellation deletes it, and no duplicate calendar event is left behind.
- If live smoke fails, handle it as a separate Stage 47.1 using the exact transcript, channel, user id/phone, and observed calendar result.



## Stage 48 — Text MVP UX Scope Rules
- Repliq MVP must be treated as a text-first receptionist. Voice/calls are future scope and must not drive current stage design unless the user explicitly switches phases.
- Existing voice/TTS/Twilio infrastructure may remain, but it is not the active launch product surface.
- Customer-facing text should not expose raw foreign-language service labels when a safe localized display is available.
- Text localization helpers must affect output text only; they must not change canonical service keys, service matching, booking state, slot generation, or calendar payloads.
- Russian price side-question replies should use Russian-facing service/price text such as `консультация стоит 10 евро`, not mixed labels such as `konsultācija стоит 10 eiro`.
- Stage 48 must preserve the Stage 46 calendar guarantees and Stage 47 live-smoke assumptions.


## Stage 49 — Text Channel Production Smoke Audit Rules
- Stage 49 is not a behavior-expansion stage. It must not change booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, or Google Calendar create/update/delete logic.
- The active launch surface remains text-first receptionist behavior. Do not design Stage 49 around voice/calls.
- The first production smoke channel should be `/dev_chat_ui` or `/dev_chat` with `tenant_id=clinic_demo`; Telegram/WhatsApp text can be tested afterward as channel integration smoke.
- `/dialogue/qa` remains the safe-mode regression proof and must stay 50/50.
- Live smoke must verify real text behavior and real Google Calendar side effects manually: create one event, reschedule the same event without duplicates, cancel the updated event, and preserve RU/LV response language.
- Readiness metadata may expose smoke checklist scope, but readiness endpoints must not run the smoke test, call LLMs, mutate conversation state, or create/update/delete calendar events.
- Any failing live smoke result must be handled in a separate fix stage using the exact transcript, channel, test user id/phone, and observed calendar result.

## Stage 50 — Text MVP Launch Demo Readiness Rules
- Stage 50 is not a behavior-expansion stage. It must not change booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, or Google Calendar create/update/delete logic.
- The active MVP launch surface remains text-first receptionist behavior.
- Voice/calls must remain explicitly marked as future scope and must not drive Stage 50 demo readiness.
- `/internal/readiness` may expose read-only client demo metadata, but must not run a demo, call an LLM, mutate conversation state, or create/update/delete Google Calendar events.
- Client demo should start from `/dev_chat_ui`, then optionally proceed to Telegram/WhatsApp text integration smoke.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.
- Any live demo issue must be handled as a separate fix stage using exact transcript, channel, user id/phone, and observed calendar result.


## Stage 51 — Tenant Config / Business Memory Admin Hardening Rules
- Stage 51 must not change receptionist behavior, booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, or Google Calendar mutation logic.
- The active MVP remains text-first receptionist. Voice/calls remain future scope.
- Tenant/admin readiness must be read-only metadata only. It must not call an LLM, mutate tenant rows, mutate conversations, or create/update/delete Google Calendar events.
- New admin checks may report warnings/blockers for business identity, timezone, hours JSON, service catalog source, business memory language coverage, Google/calendar setup, service account presence, and runtime missing items.
- `/tenant/admin/readiness`, `/tenant/config`, `/tenant/config/update`, and `/internal/readiness` may expose safe config status, but must not expose secret values such as service account JSON contents or OAuth tokens.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.
- Any future change that rejects tenant config updates or changes the admin UI editing model must be handled as a separate behavior/admin stage after explicit root-cause analysis.


## Stage 52 — Demo UI / Tenant Config UX Hardening Rules
- Stage 52 may change tenant/admin UI and read-only readiness metadata only.
- Do not change booking routing, slot generation, date/time parsing, side-question behavior, cancellation, reschedule, Google Calendar runtime actions, or regression evaluator rules.
- `/tenant/config/ui` must be demo-safe and text-first MVP oriented.
- Existing service account JSON/private keys must not be displayed in the config UI. Credential editing is paste-to-replace only.
- `/tenant/config` and config update responses must not expose raw tenant secrets. They may expose boolean configured flags.
- Optional advanced schedule JSON fields may remain empty without making the tenant look blocked when Stage 51 readiness is ready.
- Voice/call/TTS surfaces remain future scope and must not be positioned as current MVP behavior.

## Stage 52.1 — Service Catalog Localization Polish Rules
- Stage 52.1 may only polish tenant/admin UI preview and read-only readiness metadata.
- Do not change receptionist behavior, booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, Google Calendar runtime actions, or regression evaluator rules.
- Service catalog preview may use client-facing service lists for display, but canonical service keys and `service_catalog_json` matching data must remain stable.
- `/tenant/config` and `/tenant/config/ui` must remain demo-safe and must not expose service account/private key contents or OAuth tokens.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.



## Stage 53 — Client Demo Script & Demo Mode Readiness Rules
- Stage 53 may add read-only demo script/checklist metadata and documentation only.
- Do not change receptionist behavior, booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, Google Calendar runtime actions, or regression evaluator rules.
- `/demo/script` and readiness demo metadata must not call LLMs, mutate conversation state, change tenant config, or create/update/delete Google Calendar events.
- The demo script must position Repliq as a text-first receptionist MVP. Voice/calls remain future scope and must not be presented as current launch behavior.
- Demo checks may include RU/LV scripted messages, calendar verification steps, and fallback guidance.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 54 — Launch Readiness Lock Rules
- Stage 54 may add read-only launch readiness/checkpoint metadata and documentation only.
- Do not change receptionist behavior, booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, Google Calendar runtime actions, or regression evaluator rules.
- `/launch/readiness` and readiness launch-lock metadata must not call LLMs, run demos, mutate conversation state, change tenant config, or create/update/delete Google Calendar events.
- The launch lock must position Repliq as a text-first receptionist MVP. Voice/calls remain future scope and must not be presented as current launch behavior.
- Launch readiness may summarize demo status, tenant/admin readiness, safe config UI, protected regression baseline, manual live smoke status, known limitations, and post-MVP backlog.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.
- If launch/demo/pilot validation fails, handle it as a separate stage using exact endpoint output, live transcript, channel, tenant id, and observed calendar result.

## Stage 55 — Pilot Client Setup / Tenant Onboarding Polish Rules
- Stage 55 may add read-only pilot setup readiness metadata, onboarding status clarity, and admin/setup UI links only.
- Do not change receptionist behavior, booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, Google Calendar runtime create/update/delete behavior, or regression evaluator rules.
- `/pilot/setup/readiness` must not call LLMs, create tenants, mutate tenant config, mutate conversation state, or create/update/delete Google Calendar events.
- The active MVP remains text-first receptionist. Voice/calls remain future scope and must not be positioned as current pilot scope.
- Onboarding status may distinguish effective runtime completion from persisted onboarding flags so pilot/admin screens are not confusing.
- Google calendars UI should not look blocked when a selected `calendar_id` already exists even if the OAuth calendar-list endpoint returns no items.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 56 — Business Memory / FAQ Admin Polish Rules
- Stage 56 may add read-only business memory / FAQ admin readiness metadata and admin UI guidance only.
- Do not change receptionist behavior, booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, Google Calendar runtime create/update/delete behavior, or regression evaluator rules.
- `/business-memory/readiness` must not call LLMs, mutate tenant config, mutate conversation state, or create/update/delete Google Calendar events.
- Business memory readiness may inspect LV/RU/EN memory text, service mentions, price lines, address/hours hints, and line counts for admin guidance.
- Business memory UI polish may show guidance and readiness summaries, but saving behavior must remain compatible with existing `/tenant/config/update`.
- The active MVP remains text-first receptionist. Voice/calls remain future scope and must not be positioned as current pilot scope.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 57 — Basic Analytics / Usage Visibility Rules
- Stage 57 may add read-only analytics/usage visibility metadata, dashboard links, and documentation only.
- Do not change receptionist behavior, booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, Google Calendar runtime create/update/delete behavior, or regression evaluator rules.
- `/usage/readiness` and `/analytics/readiness` must not call LLMs, mutate tenant config, mutate conversation state, or create/update/delete Google Calendar events.
- Usage/analytics readiness may inspect existing `call_logs`, `usage_events`, and `dialogue_audit_events` tables and summarize safe counts for pilot/admin visibility.
- Treat dev/test traffic as smoke/visibility data, not billing proof.
- The active MVP remains text-first receptionist. Voice/calls remain future scope and must not be positioned as current pilot scope.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 58 — Auth / Access Boundaries for Admin Surfaces Rules
- Stage 58 may add read-only access-boundary audit/readiness metadata, admin UI links, and documentation only.
- Do not change receptionist behavior, booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, Google Calendar runtime create/update/delete behavior, or regression evaluator rules.
- `/access/readiness` and `/admin/access/readiness` must not call LLMs, mutate tenant config, mutate conversation state, or create/update/delete Google Calendar events.
- Stage 58 must be factual about access boundaries: URL `tenant_id` is not authentication.
- Do not silently claim public SaaS security readiness if admin auth and tenant ownership checks are not enforced.
- Current admin/demo surfaces may be marked private-demo/internal-pilot ready, but public SaaS readiness must remain false until auth enforcement is implemented.
- `/tenant/config` and admin UI must keep hiding service account JSON, private keys, OAuth tokens, and client secrets.
- Any actual auth enforcement, middleware, session handling, admin token verification, or tenant ownership restriction must be a separate stage because it may affect dashboard/dev/admin routes and regression execution.
- The active MVP remains text-first receptionist. Voice/calls remain future scope and must not be positioned as current pilot scope.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 59 — Telegram Text Channel Smoke Readiness Rules
- Stage 59 may add read-only Telegram text-channel readiness metadata, smoke checklist links, and documentation only.
- Do not change receptionist behavior, booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, Google Calendar runtime create/update/delete behavior, or regression evaluator rules.
- `/telegram/readiness` and `/channels/telegram/readiness` must not call Telegram APIs, set webhooks, call LLMs, mutate tenant config, mutate conversation state, or create/update/delete Google Calendar events.
- Telegram token and webhook secret values must never be exposed; only boolean configured flags may be shown.
- Telegram is current-scope only as a text channel. Voice/calls remain future scope and must not be positioned as part of this stage.
- If Telegram env config is missing, report `attention` with warnings instead of claiming pilot readiness.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 59.1 — Telegram Text Channel Language/Menu Hardening Rules
- Stage 59.1 may change only Telegram channel adapter behavior and safe prompt-leak guardrails needed to stabilize Telegram text smoke.
- Do not change core receptionist orchestration: booking routing, slot generation, date/time parsing, price side-question handling, cancellation, reschedule, Google Calendar runtime create/update/delete behavior, or regression evaluator rules.
- Telegram MVP policy is free-text first. Do not reintroduce persistent Telegram reply keyboards until menu state, language, and appointment-list flows are implemented as a separate tested product layer.
- `/start` should show text instructions and remove old keyboards; it should not present a persistent LV-only menu.
- Short neutral replies in Telegram must not force Latvian if the active conversation is Russian or English.
- Customer-facing Telegram messages must not expose internal labels such as `business_memory_lv:`, `faq_ru:`, `booking_rules_en:`, or `env_memory:`.
- `/telegram/readiness` may expose only safe boolean/status metadata. Token/secret values must never be exposed.
- The active MVP remains text-first receptionist. Voice/calls remain future scope.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 60 — Telegram Live Smoke Lock Rules
- Stage 60 may add read-only Telegram live-smoke lock metadata, smoke acceptance criteria, admin UI links, and documentation only.
- Do not change receptionist behavior, booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, Google Calendar runtime create/update/delete behavior, or regression evaluator rules.
- `/telegram/live-smoke/readiness`, `/telegram/smoke/readiness`, and `/channels/telegram/live-smoke/readiness` must not call Telegram APIs, set webhooks, call LLMs, mutate tenant config, mutate conversation state, or create/update/delete Google Calendar events.
- Stage 60 may record the user-reported live smoke result after Stage 59.1, but it must still expose factual readiness gates and dependencies.
- Telegram is current-scope only as a text channel. Voice/calls remain future scope and must not be positioned as part of this stage.
- Public SaaS readiness remains false until real admin auth, self-serve onboarding, tenant isolation, and billing are implemented.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 61 — Admin Access Enforcement Rules
- Stage 61 may add a minimal shared-admin-token access middleware for admin/internal/demo surfaces.
- Do not change receptionist behavior, booking routing, slot generation, date/time parsing, side-question handling, cancellation, reschedule, Google Calendar runtime create/update/delete behavior, Telegram webhook handling, or regression evaluator rules.
- Stage 61 must fail closed for protected admin surfaces when enforcement is enabled but no admin token is configured.
- The admin token value must never be logged, returned by endpoints, exposed in UI, or included in documentation examples.
- Protected API checks may use `X-Repliq-Admin-Token` or `Authorization: Bearer <token>`.
- Browser checks may use `?admin_token=<token>` only as a bootstrap path; the server should set an HttpOnly cookie for subsequent same-origin admin UI fetches.
- `/dialogue/qa` must remain available for production regression checks.
- `/telegram/webhook` must not be protected by the shared admin token because Telegram must be able to call it; it remains protected by Telegram webhook secret validation.
- `/google/callback` must remain available for OAuth redirect flow.
- Stage 61 must not claim public SaaS readiness. Shared admin token protection is only an MVP/private-admin layer until per-user auth, tenant ownership, role separation, and CSRF/session hardening are implemented.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 62 admin session rules
- Protected admin/internal surfaces remain protected by Stage 61 access enforcement.
- Browser admin use should prefer `/admin/login` and the signed `repliq_admin_session` cookie instead of repeatedly passing `admin_token` in URLs.
- Stage 62 is not final public SaaS authentication; per-owner identity, tenant ownership, role checks, and CSRF remain future stages.
- Do not expose admin token values in responses, logs, screenshots, or documentation.
- Do not change receptionist core behavior while adding auth/session UI.

## Stage 63 rules — Tenant creation / signup foundation

- Tenant creation routes must stay protected by Stage 61/62 admin session/token until public SaaS auth, owner identity, tenant ownership checks, billing, CSRF, and rate limits exist.
- `/tenant/create` and `/onboarding/create_tenant` must not become public unauthenticated write endpoints.
- Tenant slug creation must validate length, allowed characters, reserved words, and collisions.
- Stage 63 must not change receptionist core behavior: booking, cancel, reschedule, price side-questions, Telegram webhook, Google Calendar event runtime, and regression evaluator are out of scope.
- `public_saas_ready` must remain false for this stage.

## Stage 64 rules — Self-Serve Onboarding Wizard

- Stage 64 is a protected admin/session onboarding wizard layer, not a dialogue-core change.
- Do not expose the wizard publicly without future owner auth, tenant ownership, billing, CSRF, and rate-limit stages.
- `/onboarding/wizard*` and `/self-serve/onboarding/readiness` must remain protected by Stage 61/62 admin auth.
- The wizard may show incomplete steps as `attention`; this is not a regression failure if the tenant still needs Google Calendar, prices, memory, or channel setup.
- Do not modify booking, cancellation, rescheduling, Telegram webhook, Google Calendar event runtime, or regression QA for wizard-only changes.

## Stage 65 rules — Google Calendar OAuth Self-Serve

- Stage 65 may harden Google Calendar setup/readiness and protected self-serve setup paths only.
- `/google/connect`, `/google/calendars`, `/google/calendars/ui`, and `/google/select_calendar` must be protected by Stage 61/62 admin session/token.
- `/google/callback` must remain available for the Google OAuth redirect flow and must not be protected by the admin-token middleware.
- Stage 65 readiness may expose safe booleans/status only. It must not expose Google access tokens, refresh tokens, OAuth client secrets, service account JSON, or private keys.
- Stage 65 must not change receptionist core behavior: booking, cancellation, rescheduling, side-question handling, Telegram webhook, Google Calendar event create/update/delete runtime, and regression QA are out of scope.
- `public_saas_ready` must remain false for this stage until owner auth, tenant ownership checks, billing, CSRF, and public rate limits exist.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 66 rules — Service Catalog Builder

- Stage 66 may add protected service catalog builder/readiness/admin UI only.
- `/service-catalog/builder`, `/tenant/service-catalog`, and `POST /tenant/service-catalog/update` must remain protected by Stage 61/62 admin session/token.
- Service catalog updates may write tenant config fields only: service catalog JSON, `services_lv/services_ru/services_en`, and a managed service-price block in business memory.
- Do not expose secrets or admin token values in builder/readiness responses.
- Do not change receptionist core orchestration: booking, cancellation, rescheduling, date/time parsing, slot generation, Telegram webhook, Google Calendar event create/update/delete runtime, and regression QA remain out of scope.
- `public_saas_ready` must remain false for this stage until owner auth, tenant ownership checks, billing, CSRF, and public rate limits exist.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 67 rules — Business Memory / FAQ Builder

- Business memory / FAQ builder is an admin/self-serve configuration surface only.
- Do not change booking routing, slot generation, confirmation, cancel, reschedule, Google Calendar event runtime, Telegram webhook handling, or dialogue regression behavior in this stage.
- Keep all Business Memory / FAQ builder routes protected by Stage 61/62 admin access.
- Business memory should contain one fact per line for predictable receptionist answers.
- Do not store secrets, API keys, private calendar credentials, or private client data in business memory or FAQ fields.
- `public_saas_ready` remains false until owner auth, tenant ownership checks, billing, CSRF/rate limits, and production account controls are implemented.


## Stage 73 — Billing / Subscription Gate Foundation Rules

- Stage 73 may add billing/subscription readiness, manual tenant billing metadata, admin billing UI/update endpoints, owner read-only billing surfaces, and public SaaS audit integration only.
- Stage 73 must not integrate a live payment provider unless explicitly requested in a later stage. Stripe/payment provider secrets must not be accepted, logged, returned, or documented in this stage.
- Admin billing routes must remain protected by Stage 61/62 admin session/token:
  - `/billing/readiness`
  - `/billing/subscription/readiness`
  - `/tenant/billing/readiness`
  - `/tenant/billing`
  - `/tenant/billing/ui`
  - `/tenant/billing/update`
  - `/billing`
  - `/billing/ui`
- Owner billing routes must require the Stage 71 signed owner session or the existing super-admin bypass:
  - `/owner/billing`
  - `/owner/billing/ui`
  - `/owner/subscription`
  - `/owner/subscription/ui`
- Owner billing is read-only in this stage. Owner surfaces must not expose admin billing writes.
- Manual lifecycle statuses may include `trial`, `active`, `past_due`, `suspended`, `inactive`, and `expired`.
- `suspended`, `inactive`, and `expired` are blocked lifecycle states. `past_due` is allowed with attention metadata until a later billing automation stage changes policy.
- Runtime gate metadata may be exposed, but receptionist core behavior must not be changed in this stage.
- Do not change booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar runtime create/update/delete behavior, Telegram webhook handling, LLM orchestration, or regression evaluator rules.
- `public_saas_ready` must remain false after Stage 73 until CSRF/browser write hardening, abuse/rate limits, email verification/magic-link auth, and full client-owner vs super-admin separation are complete.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 73.1 rules — Billing Update Route Import Hotfix

- Stage 73.1 is a startup hotfix only.
- The only code-level change allowed is making the Stage 73 billing update route import-safe on Render/Python 3.14.
- The `/tenant/billing/update` route must remain admin protected by the existing Stage 61/62 middleware.
- Billing update validation must continue to use `TenantBillingUpdateRequest`; moving model instantiation from route annotation time to call time is acceptable.
- Do not change booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar runtime, Telegram webhook handling, LLM orchestration, or regression evaluator rules.
- `public_saas_ready` must remain false after this hotfix.


## Stage 74 rules — CSRF / Browser Write Hardening Foundation

- Stage 74 may add CSRF/browser-write hardening, readiness endpoints, and public SaaS audit/control-center metadata only.
- Cookie-authenticated admin/owner browser writes must pass same-origin browser metadata or a signed CSRF token.
- Explicit admin token header/bearer/query usage may bypass CSRF for automation/API scripts, because those calls do not rely on browser session cookies.
- CSRF readiness endpoints must remain protected by Stage 61/62 admin auth:
  - `/csrf/readiness`
  - `/security/csrf/readiness`
  - `/browser-write/readiness`
  - `/browser-write-hardening/readiness`
- `/csrf/token` must not expose raw session secrets, admin tokens, owner session secrets, or CSRF secrets.
- Public signup may remain public, but cross-site browser POSTs must be blocked by Stage 74 browser metadata/token checks.
- External channel webhooks must not be placed behind browser CSRF checks: Telegram, SMS, WhatsApp, and voice webhook routes are not browser UI writes.
- Do not change booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, billing semantics, LLM orchestration, or regression evaluator rules.
- `public_saas_ready` must remain false after Stage 74 until production abuse/rate limits, email verification/magic-link auth, and full client-owner vs super-admin separation are complete.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 75 rules — Abuse Protection / Rate Limits Hardening Foundation

- Stage 75 may add abuse/rate-limit readiness, safe abuse-event storage, and route-level gates for admin login, owner login, public signup, and public CSRF token issuance only.
- Stage 75 must not expose raw IP addresses, subject hashes, admin tokens, owner login codes, owner login code hashes, session secrets, CSRF secrets, Telegram tokens, or Google credentials.
- Stage 75 readiness endpoints must remain protected by Stage 61/62 admin auth:
  - `/abuse/readiness`
  - `/security/abuse/readiness`
  - `/rate-limits/readiness`
  - `/abuse-protection/readiness`
- Stage 72 public signup-specific rate limits must remain active. Stage 75 may add a shared abuse ledger around them but must not remove Stage 72 checks.
- Admin login and owner login must continue to work for valid credentials.
- Public signup must remain usable from the same-origin public signup UI.
- External channel webhooks must not be blocked by this browser/public-account abuse stage: Telegram, SMS, WhatsApp, and voice webhook routes are out of scope.
- Do not change booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, billing semantics, LLM orchestration, or regression evaluator rules.
- `public_saas_ready` must remain false after Stage 75 until email verification/magic-link auth, client-owner vs super-admin separation hardening, and final public SaaS readiness lock are complete.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 76 — Email Verification / Magic Link Auth Rules

- Magic-link auth is an owner-auth layer only; it must not change receptionist dialogue behavior.
- Raw magic tokens may be returned once by public signup or protected admin bootstrap, but must not be stored raw.
- Readiness endpoints must not expose token hashes, login-code hashes, admin tokens, raw IPs, or subject hashes.
- Successful magic-link login sets the existing Stage 71 HttpOnly owner session cookie and marks owner email verified.
- Legacy owner setup-code login remains supported during this foundation stage.
- Real outbound email delivery is not required for Stage 76 foundation; absence of an email provider may be a readiness warning, not a dialogue/runtime blocker.
- Public SaaS readiness remains false until client-owner vs super-admin separation and final launch gate stages are closed.


## Stage 77 — Client-owner vs Super-admin Separation Hardening Rules

- Stage 77 may add readiness/audit metadata, route/surface maps, and owner-safe UI link hardening only.
- Owner surfaces must remain bound to the Stage 71 signed owner session and `owner_tenant_access`; `tenant_id` query params must never be treated as authentication.
- Super-admin/admin surfaces must remain protected by Stage 61/62 admin auth.
- Owner-facing dashboards and billing pages must not expose admin write/config links in their primary owner `links`/UI navigation.
- Super-admin support bypass may remain for private support/admin review, but it must be explicit and marked as a bypass.
- Stage 77 readiness endpoints must be admin-protected:
  - `/owner-admin-separation/readiness`
  - `/client-owner/separation/readiness`
  - `/security/owner-admin-separation/readiness`
  - `/tenant/isolation/readiness`
- Do not change booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, billing semantics, CSRF semantics, abuse/rate-limit semantics, LLM orchestration, or regression evaluator rules.
- `public_saas_ready` must remain false after Stage 77 until the final Stage 78 public SaaS readiness lock is closed.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 77 — Client-owner vs Super-admin Separation Hardening Rules

- Stage 77 may add readiness/audit metadata, route/surface maps, and owner-safe UI link hardening only.
- Owner surfaces must remain bound to the Stage 71 signed owner session and `owner_tenant_access`; `tenant_id` query params must never be treated as authentication.
- Super-admin/admin surfaces must remain protected by Stage 61/62 admin auth.
- Owner-facing dashboards and billing pages must not expose admin write/config links in their primary owner `links`/UI navigation.
- Super-admin support bypass may remain for private support/admin review, but it must be explicit and marked as a bypass.
- Stage 77 readiness endpoints must be admin-protected:
  - `/owner-admin-separation/readiness`
  - `/client-owner/separation/readiness`
  - `/security/owner-admin-separation/readiness`
  - `/tenant/isolation/readiness`
- Do not change booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, billing semantics, CSRF semantics, abuse/rate-limit semantics, LLM orchestration, or regression evaluator rules.
- `public_saas_ready` must remain false after Stage 77 until the final Stage 78 public SaaS readiness lock is closed.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 77.1 rule note

Stage 77.1 is a narrow readiness endpoint hotfix only. It fixes a runtime type mismatch in the Stage 77 owner/admin separation readiness payload. It must not change receptionist dialogue, booking, calendar, Telegram, billing, CSRF, abuse/rate-limit, or magic-link flows.

## Stage 78 — Final Public SaaS Readiness Lock Rules

- Stage 78 is a read-only final launch readiness gate for controlled public self-service SMB MVP.
- Stage 78 may set `public_saas_ready=true` only when all final gates are ready.
- Stage 78 must keep `enterprise_saas_ready=false`; enterprise maturity is a later phase.
- Stage 78 readiness endpoints must be admin-protected:
  - `/public-saas/final-readiness`
  - `/public-saas/launch-readiness`
  - `/public-saas/ready`
  - `/launch/self-service/readiness`
  - `/self-service/launch/readiness`
- Stage 78 may integrate into Stage 70 `/public-saas/readiness` and the Control Center readiness payload.
- Stage 78 must not change receptionist dialogue, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 79 — Launch UX / Public Onboarding Polish Rules

- Stage 79 starts the Mature SMB SaaS phase after Stage 78.
- Stage 79 may polish public launch/signup UI, owner workspace UI, owner-safe links, and readiness/audit metadata only.
- Stage 79 must keep Stage 78 as the source of truth for `public_saas_ready`.
- Stage 79 must keep `enterprise_saas_ready=false`; enterprise maturity is a later phase.
- Stage 79 readiness endpoints must be protected by Stage 61/62 admin auth:
  - `/launch-ux/readiness`
  - `/public-onboarding/readiness`
  - `/smb/launch/readiness`
  - `/mature-smb/readiness`
- Public launch pages may be public GET pages only and must not expose secrets or admin state.
- Public signup must remain public, same-origin safe, abuse/rate-limit protected, and usable.
- Public signup UI must not render raw login codes, magic-link tokens, token hashes, admin tokens, CSRF secrets, raw IPs, Telegram tokens, or Google credentials in its visible technical details block.
- Public signup response main links should remain owner-safe; admin setup links must not be exposed as primary public signup links.
- Owner dashboard and owner billing must remain bound to Stage 71 owner session and tenant ownership binding.
- Owner UI must not expose admin write/config links in primary owner navigation.
- Do not change receptionist dialogue, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 80 — Tenant Workspace UX / Owner Setup Completion Rules

- Stage 80 continues the Mature SMB SaaS phase after Stage 79.
- Stage 80 may add owner-safe workspace/setup-completion UX, readiness metadata, and owner dashboard links only.
- Stage 80 must keep Stage 78 as the source of truth for `public_saas_ready`.
- Stage 80 must keep `enterprise_saas_ready=false`; enterprise maturity is a later phase.
- Stage 80 readiness endpoints must be protected by Stage 61/62 admin auth:
  - `/tenant-workspace/readiness`
  - `/workspace/readiness`
  - `/owner-setup/readiness`
  - `/owner/setup-completion/readiness`
- Stage 80 owner workspace/setup endpoints must be protected by Stage 71 owner session and tenant binding:
  - `/owner/setup`
  - `/owner/setup/ui`
  - `/owner/workspace`
  - `/owner/workspace/ui`
  - `/owner/workspace/setup`
  - `/owner/workspace/setup/ui`
- Owner-facing workspace/setup UI must not expose admin write/config links in primary owner navigation.
- Support-controlled setup gaps may be shown as next actions, but admin configuration links must stay hidden from client owners.
- Do not expose raw admin tokens, owner login codes, magic tokens, magic-token hashes, CSRF secrets, raw IPs, subject hashes, Telegram tokens, or Google credentials.
- Do not change receptionist dialogue, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 81 — Tenant Business Profile / Workspace Settings UX Rules

- Stage 81 continues the Mature SMB SaaS phase after Stage 80.
- Stage 81 may add owner-safe business profile/workspace settings UX, readiness metadata, and links only.
- Owner editable fields are limited to non-secret business profile fields: `business_name`, `language`, `timezone`, `work_start`, `work_end`.
- Stage 81 readiness endpoints must be protected by Stage 61/62 admin auth:
  - `/business-profile/readiness`
  - `/owner-business-profile/readiness`
  - `/workspace-settings/readiness`
  - `/tenant/business-profile/readiness`
- Stage 81 owner settings endpoints must be protected by Stage 71 owner session and tenant binding:
  - `/owner/business-profile`
  - `/owner/business-profile/ui`
  - `/owner/workspace/settings`
  - `/owner/workspace/settings/ui`
  - `/owner/business-profile/update`
- `POST /owner/business-profile/update` must remain protected by Stage 74 owner browser write/CSRF hardening.
- Owner-facing profile/settings UI must not expose super-admin tenant config links in primary owner navigation.
- Do not expose raw admin tokens, owner login codes, magic tokens, magic-token hashes, CSRF secrets, raw IPs, subject hashes, Telegram tokens, Google credentials, or other tenant secrets.
- Stage 78 remains the source of truth for `public_saas_ready`.
- `enterprise_saas_ready` remains false; enterprise maturity is a later phase.
- Do not change receptionist dialogue, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, billing semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 81.1 — Business Profile Language Persistence Hotfix
- Fixes Stage 81 owner business-profile UX where the language selector could show `lv` but readiness still reported `missing=language` on older tenant schemas.
- Ensures `tenants.language` exists, backfills empty values to `lv`, and sets `lv` as the default for future rows.
- Does not change receptionist booking/dialogue/calendar/Telegram/billing/runtime semantics.


## Stage 82 — Service Catalog Owner UX / Setup Completion Polish Rules

- Stage 82 continues the Mature SMB SaaS phase after Stage 81.1.
- Stage 82 may add owner-safe service catalog UX, owner service setup completion metadata, readiness endpoints, and owner dashboard/workspace links only.
- Owner editable service fields are limited to non-secret service catalog fields: `key`, `active`, `name_lv`, `name_ru`, `name_en`, `duration_min`, `price`, `currency`, `aliases_lv`, `aliases_ru`, `aliases_en`, `description_lv`, `description_ru`, `description_en`.
- Stage 82 readiness endpoints must be protected by Stage 61/62 admin auth:
  - `/owner-services/readiness`
  - `/owner-service-catalog/readiness`
  - `/service-catalog/owner/readiness`
  - `/workspace/services/readiness`
- Stage 82 owner service endpoints must be protected by Stage 71 owner session and tenant binding:
  - `/owner/services`
  - `/owner/services/ui`
  - `/owner/service-catalog`
  - `/owner/service-catalog/ui`
  - `/owner/services/update`
  - `/owner/service-catalog/update`
- `POST /owner/services/update` and `POST /owner/service-catalog/update` must remain protected by Stage 74 owner browser write/CSRF hardening.
- Owner-facing service UI must not expose super-admin tenant config links or admin service catalog builder links in primary owner navigation.
- Super-admin support links may appear only when opened through explicit admin/session bypass and must be clearly separated from owner links.
- Do not expose raw admin tokens, owner login codes, magic tokens, magic-token hashes, CSRF secrets, raw IPs, subject hashes, Telegram tokens, Google credentials, or other tenant secrets.
- Stage 78 remains the source of truth for `public_saas_ready`.
- `enterprise_saas_ready` remains false; enterprise maturity is a later phase.
- Do not change receptionist dialogue, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, billing semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 83 — Business Memory / FAQ Owner UX Polish Rules

- Stage 83 continues the Mature SMB SaaS phase after Stage 82.
- Stage 83 may add owner-safe Business Memory / FAQ UX, owner memory setup completion metadata, readiness endpoints, and owner dashboard/workspace links only.
- Owner editable memory fields are limited to non-secret receptionist fact fields: `business_memory_lv`, `business_memory_ru`, `business_memory_en`, `faq_lv`, `faq_ru`, `faq_en`, `booking_rules_lv`, `booking_rules_ru`, `booking_rules_en`, `business_memory`, `faq`, `booking_rules`, `policies`.
- Stage 83 readiness endpoints must be protected by Stage 61/62 admin auth:
  - `/owner-business-memory/readiness`
  - `/owner-faq/readiness`
  - `/business-memory/owner/readiness`
  - `/workspace/memory/readiness`
- Stage 83 owner memory/FAQ endpoints must be protected by Stage 71 owner session and tenant binding:
  - `/owner/business-memory`
  - `/owner/business-memory/ui`
  - `/owner/faq`
  - `/owner/faq/ui`
  - `/owner/business-memory/update`
  - `/owner/faq/update`
- `POST /owner/business-memory/update` and `POST /owner/faq/update` must remain protected by Stage 74 owner browser write/CSRF hardening.
- Owner-facing memory/FAQ UI must not expose super-admin tenant config links or admin Business Memory builder links in primary owner navigation.
- Super-admin support links may appear only when opened through explicit admin/session bypass and must be clearly separated from owner links.
- Do not expose raw admin tokens, owner login codes, magic tokens, magic-token hashes, CSRF secrets, raw IPs, subject hashes, Telegram tokens, Google credentials, or other tenant secrets.
- Stage 78 remains the source of truth for `public_saas_ready`.
- `enterprise_saas_ready` remains false; enterprise maturity is a later phase.
- Do not change receptionist dialogue, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 84 — Service Catalog / Business Memory Consistency Guard Rules

- Stage 84 continues the Mature SMB SaaS phase after Stage 83.
- Service Catalog is the source of truth for service prices, durations and active service availability.
- Business Memory / FAQ is contextual text for policies, exceptions, address, booking rules and explanatory FAQ.
- Stage 84 may add read-only consistency checks, readiness metadata, owner-safe guidance UI and owner/dashboard/workspace links only.
- Stage 84 must not auto-delete, auto-overwrite, or silently rewrite owner Business Memory content.
- The managed block between `# Repliq service catalog prices` and `# /Repliq service catalog prices` remains generated from service catalog prices.
- Manual price-like lines outside the managed block must be surfaced as warnings/attention when they conflict with service catalog prices, duplicate catalog prices, or do not match any active catalog service.
- Stage 84 readiness endpoints must be protected by Stage 61/62 admin auth:
  - `/service-memory/consistency/readiness`
  - `/catalog-memory/consistency/readiness`
  - `/price-consistency/readiness`
  - `/workspace/price-consistency/readiness`
- Stage 84 owner consistency endpoints must be protected by Stage 71 owner session and tenant binding:
  - `/owner/price-consistency`
  - `/owner/price-consistency/ui`
  - `/owner/catalog-memory-consistency`
  - `/owner/catalog-memory-consistency/ui`
- No new write endpoint is allowed in Stage 84.
- Owner-facing consistency UI must not expose super-admin tenant config links or admin builder links in primary owner navigation.
- Super-admin support links may appear only when opened through explicit admin/session bypass and must be clearly separated from owner links.
- Do not expose raw admin tokens, owner login codes, magic tokens, magic-token hashes, CSRF secrets, raw IPs, subject hashes, Telegram tokens, Google credentials, or other tenant secrets.
- Stage 78 remains the source of truth for `public_saas_ready`.
- `enterprise_saas_ready` remains false; enterprise maturity is a later phase.
- Do not change receptionist dialogue, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 85 — Calendar Owner UX / Availability Setup Polish Rules

- Stage 85 continues the Mature SMB SaaS phase after Stage 84.
- Stage 85 may add owner-safe calendar status UX, availability setup UX, availability readiness metadata, owner/dashboard/workspace links, and an owner availability update endpoint only.
- Owner editable availability fields are limited to non-secret scheduling fields: `timezone`, `work_start`, and `work_end`.
- Stage 85 must not change Google Calendar event creation, update, delete, slot generation, booking routing, cancellation or reschedule runtime logic.
- Google OAuth connection and working calendar selection remain support-controlled in Stage 85 unless a later owner OAuth flow is explicitly implemented.
- Owner-facing calendar UI must not expose Google access tokens, refresh tokens, service account JSON, raw credential material, admin OAuth setup links, or super-admin config links in primary owner navigation.
- Stage 85 readiness endpoints must be protected by Stage 61/62 admin auth:
  - `/owner-calendar/readiness`
  - `/calendar-owner/readiness`
  - `/availability/readiness`
  - `/workspace/calendar/readiness`
- Stage 85 owner calendar/availability endpoints must be protected by Stage 71 owner session and tenant binding:
  - `/owner/calendar`
  - `/owner/calendar/ui`
  - `/owner/availability`
  - `/owner/availability/ui`
  - `/owner/availability/update`
- `POST /owner/availability/update` must remain protected by Stage 74 owner browser write/CSRF hardening.
- Super-admin support links may appear only when opened through explicit admin/session bypass and must be clearly separated from owner links.
- Do not expose raw admin tokens, owner login codes, magic tokens, magic-token hashes, CSRF secrets, raw IPs, subject hashes, Telegram tokens, Google credentials, or other tenant secrets.
- Stage 78 remains the source of truth for `public_saas_ready`.
- `enterprise_saas_ready` remains false; enterprise maturity is a later phase.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 86 — Telegram Owner UX / Channel Setup Polish Rules

- Stage 86 continues the Mature SMB SaaS phase after Stage 85.
- Stage 86 may add owner-safe Telegram channel status UX, Telegram readiness metadata, owner/dashboard/workspace links, and owner-visible next actions only.
- Stage 86 must not add an owner Telegram token/webhook secret write endpoint.
- Telegram bot token storage, webhook secret generation, webhook setting, and Telegram admin setup remain support-controlled in this SMB phase.
- Owner-facing Telegram UI must not expose raw Telegram bot tokens, raw webhook secrets, masked token values, admin setup links, webhook setup write actions, or super-admin config links in primary owner navigation.
- Stage 86 readiness endpoints must be protected by Stage 61/62 admin auth:
  - `/owner-telegram/readiness`
  - `/telegram-owner/readiness`
  - `/workspace/telegram/readiness`
  - `/channels/telegram/owner/readiness`
- Stage 86 owner Telegram endpoints must be protected by Stage 71 owner session and tenant binding:
  - `/owner/telegram`
  - `/owner/telegram/ui`
  - `/owner/channels/telegram`
  - `/owner/channels/telegram/ui`
- No new Stage 74 owner CSRF/browser-write path is required because Stage 86 adds no owner write endpoint.
- Super-admin support links may appear only when opened through explicit admin/session bypass and must be clearly separated from owner links.
- Stage 86 must not change Telegram webhook runtime, Telegram incoming-message handling, Telegram send-message handling, receptionist dialogue, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, or regression evaluator rules.
- Stage 78 remains the source of truth for `public_saas_ready`.
- `enterprise_saas_ready` remains false; enterprise maturity is a later phase.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 87 — Owner Workspace Final Setup Review / Launch Checklist Polish Rules

- Stage 87 continues the Mature SMB SaaS phase after Stage 86.
- Stage 87 may add owner-safe final setup review UX, launch checklist readiness metadata, owner/dashboard/workspace links, and owner-visible next actions only.
- Stage 87 must aggregate existing readiness from prior stages instead of changing receptionist runtime behavior.
- Stage 87 readiness must include business profile, services, Business Memory / FAQ, price consistency, calendar/availability, Telegram, billing, owner auth, owner/admin separation, workspace setup and Stage 78 public launch lock.
- Stage 87 must not add owner write endpoints.
- Stage 87 must not expose raw admin tokens, owner login codes, magic tokens, magic-token hashes, CSRF secrets, raw IPs, subject hashes, Telegram tokens, Google credentials, service account JSON, webhook secrets, billing provider secrets, or other tenant secrets.
- Stage 87 owner launch review endpoints must be protected by Stage 71 owner session and tenant binding:
  - `/owner/launch-review`
  - `/owner/launch-review/ui`
  - `/owner/setup-review`
  - `/owner/setup-review/ui`
  - `/owner/launch-checklist`
  - `/owner/launch-checklist/ui`
- Stage 87 readiness endpoints must be protected by Stage 61/62 admin auth:
  - `/owner-workspace/final-review/readiness`
  - `/workspace/final-review/readiness`
  - `/owner-launch-checklist/readiness`
  - `/launch-checklist/owner/readiness`
- No new Stage 74 owner CSRF/browser-write path is required because Stage 87 adds no owner write endpoint.
- Calendar and Telegram support-controlled setup states may appear as owner-visible attention items, but owner UI must not expose admin OAuth/setup links or secret write actions.
- Stage 78 remains the source of truth for `public_saas_ready`.
- `enterprise_saas_ready` remains false; enterprise maturity is a later phase.
- Do not change receptionist dialogue, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook handling, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 87.1 — Launch Review UI Bootstrap Hotfix Rules

- Stage 87.1 is a narrow UI bootstrap hotfix for the Stage 87 owner launch review page.
- It may change only the owner launch review HTML/JavaScript bootstrap and documentation.
- It must not change Stage 87 readiness aggregation semantics.
- It must not add owner write routes or CSRF paths.
- It must keep `/owner/launch-review`, `/owner/setup-review`, and `/owner/launch-checklist` protected by Stage 71 owner session and tenant binding.
- It must keep readiness endpoints admin-protected.
- It must not expose admin setup links or secrets to owner users.
- It must not change receptionist dialogue, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar runtime, Telegram webhook handling, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 87.2 Guardrail
Stage 87 owner launch-review pages must not perform deep cross-stage readiness fan-out in the browser request. Use fast owner-safe checklist data and link to deeper admin/support diagnostics separately.

## Stage 88 — Owner Demo / Client Preview Mode Polish Rules

- Stage 88 continues the Mature SMB SaaS phase after Stage 87.2.
- Stage 88 may add owner-safe dry-run demo/client preview UX, readiness metadata, owner dashboard/workspace links, and preview-only reply generation.
- Stage 88 must not call live booking confirmation, Google Calendar mutation, Telegram send-message runtime, SMS/WhatsApp send runtime, or conversation persistence.
- Stage 88 must keep Service Catalog as the source of truth for prices. Business Memory may provide context/FAQ text only.
- Stage 88 preview responses must explicitly remain dry-run and must expose safety flags such as `calendar_event_created=false`, `conversation_persisted=false`, and `external_customer_message_sent=false`.
- Stage 88 readiness endpoints must be protected by Stage 61/62 admin auth:
  - `/owner-demo/readiness`
  - `/client-preview/readiness`
  - `/workspace/demo/readiness`
  - `/demo/owner/readiness`
- Stage 88 owner preview endpoints must be protected by Stage 71 owner session and tenant binding:
  - `/owner/demo`
  - `/owner/demo/ui`
  - `/owner/demo/preview`
  - `/owner/client-preview`
  - `/owner/client-preview/ui`
  - `/owner/client-preview/message`
- Stage 88 owner preview write endpoints must be protected by Stage 74 owner browser write/CSRF hardening:
  - `/owner/demo/preview`
  - `/owner/client-preview/message`
- Stage 88 owner UI must not expose raw admin tokens, owner login codes, magic tokens, magic-token hashes, CSRF secrets, Telegram tokens, Google credentials, service account JSON, webhook secrets, billing provider secrets, or other tenant secrets.
- Stage 88 must not change receptionist dialogue runtime, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar runtime, Telegram webhook handling, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 89 — Owner Analytics / Conversation Visibility Polish Rules

- Stage 89 continues the Mature SMB SaaS phase after Stage 88.
- Stage 89 may add owner-safe, read-only analytics/conversation visibility endpoints, UI, readiness metadata, dashboard/workspace links, and documentation only.
- Stage 89 must use existing data only. It must not add new runtime conversation writes just to support analytics.
- Stage 89 must not persist Stage 88 preview messages. Stage 88 preview remains dry-run only.
- Stage 89 must clearly mark preview history as unavailable/not persisted instead of overclaiming preview analytics.
- Stage 89 owner analytics endpoints must be protected by Stage 71 owner session and tenant binding:
  - `/owner/analytics`
  - `/owner/analytics/ui`
  - `/owner/conversation-insights`
  - `/owner/conversation-insights/ui`
- Stage 89 readiness endpoints must be protected by Stage 61/62 admin auth:
  - `/owner-analytics/readiness`
  - `/workspace/analytics/readiness`
  - `/conversation-visibility/readiness`
  - `/analytics/owner/readiness`
- No new Stage 74 owner CSRF/browser-write path is required because Stage 89 is read-only.
- Owner analytics UI must not expose raw admin tokens, owner login codes, magic tokens, magic-token hashes, CSRF secrets, raw IPs, raw customer identifiers, Telegram tokens, Google credentials, service account JSON, webhook secrets, billing provider secrets, or other tenant secrets.
- Owner analytics may show redacted/truncated message snippets and stable customer refs, but must not expose raw `user_id` values.
- Answer-source visibility must be labeled as inferred from existing metadata unless a future stage adds explicit runtime trace metadata.
- Stage 89 must not change receptionist dialogue runtime, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar runtime, Telegram webhook/runtime, SMS/WhatsApp send paths, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, voice/calls, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.
- Stage 78 remains the source of truth for `public_saas_ready`.
- `enterprise_saas_ready` remains false; enterprise maturity is a later phase.


## Stage 90 — Owner Notifications / Lead Follow-up Visibility Rules

- Stage 90 continues the Mature SMB SaaS phase after Stage 89.
- Stage 90 may add owner-safe, read-only notification/follow-up visibility endpoints, UI, readiness metadata, dashboard/workspace links, and documentation only.
- Stage 90 must use existing data only. It must not add new runtime conversation writes, notification writes, delivery queues, background jobs, or external send calls.
- Follow-up candidates must be clearly labeled as inferred from existing `call_logs`/`conversations` metadata unless a future stage adds explicit lead/follow-up tracking.
- Stage 90 must not send owner notifications, Telegram messages, SMS, WhatsApp messages, emails, or customer follow-up messages.
- Stage 90 owner notification/follow-up endpoints must be protected by Stage 71 owner session and tenant binding:
  - `/owner/notifications`
  - `/owner/notifications/ui`
  - `/owner/follow-ups`
  - `/owner/follow-ups/ui`
  - `/owner/lead-followup`
  - `/owner/lead-followup/ui`
- Stage 90 readiness endpoints must be protected by Stage 61/62 admin auth:
  - `/owner-notifications/readiness`
  - `/workspace/notifications/readiness`
  - `/lead-follow-up/readiness`
  - `/notifications/owner/readiness`
- No new Stage 74 owner CSRF/browser-write path is required because Stage 90 is read-only.
- Owner notification/follow-up UI must not expose raw admin tokens, owner login codes, magic tokens, magic-token hashes, CSRF secrets, raw IPs, raw customer identifiers, Telegram tokens, Google credentials, service account JSON, webhook secrets, billing provider secrets, or other tenant secrets.
- Owner follow-up visibility may show redacted/truncated message snippets and stable customer refs, but must not expose raw `user_id` or raw `user_key` values.
- Stage 90 must not change receptionist dialogue runtime, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar runtime, Telegram webhook/runtime, SMS/WhatsApp send paths, billing semantics, auth/session semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, voice/calls, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.
- Stage 78 remains the source of truth for `public_saas_ready`.
- `enterprise_saas_ready` remains false; enterprise maturity is a later phase.

## Stage 90.1 — Notification Links 500 Guard Hotfix Rules

- Stage 90.1 is a hotfix for Stage 90 notification/follow-up links returning Internal Server Error after deploy.
- Stage 90.1 may only add narrow guards/fallback payloads around Stage 90 notification/follow-up readiness, JSON, and UI paths.
- Stage 90.1 must not add notification sends, external messages, queue jobs, background jobs, new write paths, or new runtime persistence.
- Stage 90.1 must not expose stack traces, raw SQL, raw user IDs, raw user keys, tokens, secrets, webhook credentials, Google credentials, Telegram secrets, billing secrets, magic tokens, CSRF secrets, or admin tokens.
- Stage 90.1 owner notification/follow-up endpoints remain Stage 71 owner-session protected.
- Stage 90.1 readiness endpoints remain Stage 61/62 admin protected.
- No Stage 74 CSRF path is required because the hotfix remains read-only.
- Stage 90.1 must not change receptionist dialogue runtime, booking routing, slot generation, date/time parsing, side-question handling, confirmation, cancellation, rescheduling, Google Calendar runtime, Telegram webhook/runtime, SMS/WhatsApp send paths, billing semantics, auth/session semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, LLM orchestration, voice/calls, or regression evaluator rules.
- Current protected baseline remains `/dialogue/qa = 50/50 passed`.
- `enterprise_saas_ready` remains false; enterprise maturity is a later phase.
