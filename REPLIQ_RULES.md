# Repliq Conversational Rules

Core rule: LLM is an understanding layer only. Booking actions remain controlled by orchestration/state logic.

Current protected baseline:
- `/dialogue/qa` confirmed after Stage 51 deploy: 50/50 passed. Stage 52 must preserve this baseline.
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

