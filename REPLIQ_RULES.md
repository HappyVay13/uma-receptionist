# Repliq Conversational Rules

Core rule: LLM is an understanding layer only. Booking actions remain controlled by orchestration/state logic.

Current protected baseline:
- `/dialogue/qa` confirmed after Stage 53 deploy: 50/50 passed. Stage 54 must preserve this baseline.
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
