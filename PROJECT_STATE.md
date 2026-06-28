# Repliq Project State

Current stage: Stage 76 — Email Verification / Magic Link Auth Foundation.

Production regression baseline before Stage 40:
- Stage 39 was deployed and confirmed by user: `/dialogue/qa` = 15/15 passed.
- Previous failing scenario `stage38_lv_price_side_question` is closed.
- Calendar safe mode baseline remains active for QA/regression context.
- Tenant used in QA baseline: `clinic_demo`.

Stage 40 confirmed production baseline:
- Stage 40 was deployed and confirmed by user: `/dialogue/qa` = 28/28 passed.
- Regression matrix expanded from 15 to 28 scenarios.

Stage 41 production result:
- Stage 41 was deployed by user.
- Production `/dialogue/qa` result: 29/30 passed.
- Failing scenario: `stage41_ru_price_side_question`.
- Failure reason: RU price side-question preserved booking flow but did not answer a grounded service price.

Stage 41.1 confirmed production baseline:
- Adds cross-language business-memory fallback for service price lookup.
- User confirmed production `/dialogue/qa` after deploy: 30/30 passed.
- Regression matrix remains 30 scenarios.

Stage 40 scope:
- Regression matrix expansion only.
- No conversational behavior changes.
- No routing changes.
- No calendar/booking execution changes.
- No regression evaluator relaxation.

Protected baseline:
- Stage 24 parser/offered-slot/no-confirm hotfixes
- Stage 30 after-time negotiation window
- Stage 31 fuzzy scheduling intelligence
- Stage 32 contextual refinement memory
- Stage 33 soft conversational UX
- Stage 34 regression matrix
- Stage 35 QA runner with clinic_demo + calendar-safe mode + calibrated evaluator
- Stage 36 advanced conversation recovery
- Stage 37 temporal semantic engine and Latvian relative-date recovery
- Stage 38 business-memory FAQ / side-question handling inside active booking flows
- Stage 40 regression expansion to 28 scenarios
- Stage 41 side-question coverage hardening
- Stage 41.1 cross-language price memory fallback
- Stage 42 production readiness audit checkpoint
- Stage 43A production hardening/readiness checks
- Stage 44 cancellation/reschedule regression harness
- Stage 45 reschedule flow completion
- Stage 45.1 reschedule slot evaluator calibration
- Stage 46 calendar runtime cancel/reschedule hardening
- Stage 47 live calendar E2E smoke audit and baseline sync
- Stage 48 text MVP UX scope hardening
- Stage 49 text channel production smoke audit
- Stage 50 text MVP launch demo readiness
- Stage 51 tenant config / business memory admin hardening
- Stage 52 demo UI / tenant config UX hardening
- Stage 52.1 service catalog localization polish
- Stage 53 client demo script and demo mode readiness
- Stage 54 launch readiness lock
- Stage 55 pilot client setup / tenant onboarding polish
- Stage 56 business memory / FAQ admin polish
- Stage 57 basic analytics / usage visibility
- Stage 58 auth/access boundaries readiness
- Stage 59 Telegram text channel smoke readiness
- Stage 59.1 Telegram language/menu hardening
- Stage 60 Telegram live smoke lock
- Stage 61 admin access enforcement
- Stage 62 admin login / session layer
- Stage 63 tenant creation / signup foundation
- Stage 64 self-serve onboarding wizard
- Stage 65 Google Calendar OAuth self-serve
- Stage 66 service catalog builder
- Stage 67 business memory / FAQ builder
- Stage 68 Telegram bot self-serve setup
- Stage 69 client dashboard self-serve control center
- Stage 70 public SaaS readiness gap audit
- Stage 71 owner auth / public client account foundation
- Stage 71.1 owner readiness / tenant context fix
- Stage 72 public signup boundary / owner signup flow foundation
- Stage 73 billing / subscription gate foundation
- Stage 73.1 billing update route import hotfix
- Stage 74 CSRF / browser write hardening foundation

## Stage 36 — Advanced Conversation Recovery

Stage 36 adds a deterministic recovery layer inside active booking flows. It is designed to preserve existing orchestration and avoid resetting the conversation when the user gives incomplete, hesitant, or corrective answers.

### Stage 36.1 — Semantic Recovery Continuity
- Preserves fuzzy time windows across recovery turns such as not tomorrow -> day after tomorrow.
- Improves uncertain/hold recovery language without changing booking actions.
- Booking/calendar execution logic remains unchanged.

### Stage 36.2 — Conversational Continuity Smoothing
- Added direct date refinement continuation inside recovery flow.
- Fixed redundant ask-date loop after `ne rīt` -> `parīt`.
- Preserves fuzzy time preferences when changing day.

### Stage 36.3 — Semantic Date Shift Continuity
- Preserves fuzzy time windows when user changes date after rejecting the previous one, e.g. `ne rīt` -> `parīt`.

## Stage 37 — Temporal Semantic Engine
- Added centralized temporal recovery for relative dates.
- Latvian `rīt/parīt/aizparīt` maps to +1/+2/+3 days in the current project logic.
- Date-shift recovery preserves fuzzy time context and avoids morning fallback.

### Stage 37.1 — Temporal Engine Window Preservation
- Fixed fuzzy time window persistence for `rīt vakarā`.
- Fixed negative-only `ne rīt` so it does not resolve back to tomorrow.
- `parīt` and `aizparīt` regenerate contextual evening slots instead of morning fallback.

### Stage 37.2 — Direct Slot Regeneration After Temporal Replacement
- Fixed direct slot regeneration after `parīt` / `aizparīt` in temporal recovery flows.
- Preserves `vakarā` / fuzzy time window across replacement-date turns.
- Added slot-ack guard for `jā, der` while offered slots are visible.

### Stage 37.3 — LV Confirm Intent Guard
- Fixed Latvian positive acknowledgement detection in offered-slot state.
- `jā, der` chooses the first offered slot and asks for booking confirmation.
- Prevents accidental fallback to `AWAITING_DATE`.

## Stage 38 — Business Memory Intelligence / FAQ Rules Hardening
- Generic FAQ/business-memory answers across tenant business types.
- Side-question handling preserves active booking flow.
- Added regression scenarios for price, hours and location questions.

### Stage 38.1 — Price Side-question FAQ Fix
- Price side-questions inside active booking flow are answered from business memory/service context.
- Existing booking context is preserved.
- No calendar/orchestration booking logic changed.

### Stage 38.2 — Price FAQ Inline Answer
- Added LV `cik tas maksā?` price handling.
- Added `eiro` price extraction from business memory lines.
- Preserves booking context after answering price.

### Stage 38.3 — Preserve Business FAQ Answer Through Soft UX Layer
- Root cause of the final Stage 38 fail was the final Stage 33 soft UX layer overwriting a valid FAQ+flow answer with a generic slot prompt.
- `stage33_soft_conversational_ux()` now returns early when the result contains `flow_preserved` or `stage38_business_faq`.
- This preserves combined responses such as price answer + current slot options.
- No booking/calendar execution logic was changed.

## Stage 39 — Regression Baseline Lock & Project State Sync
- Updated project state documentation to the confirmed post-Stage-38 baseline.
- Updated conversational rules to include Stage 38.3 final guard behavior.
- Added a Stage 39 checkpoint document.
- Corrected Stage 38.3/38.4 notes so they describe the factual working mechanism instead of a non-existent standalone guard function.
- Code behavior intentionally unchanged.


## Stage 40 — Regression Matrix Expansion
- Expanded `STAGE34_REGRESSION_TEST_MATRIX` from 15 to 28 scenarios.
- Added protections around side-questions inside active booking flows, numeric slot choice after side-questions, later-time refinement, other-day recovery, and standalone FAQ coverage.
- No conversation/routing behavior was changed.
- No evaluator rules were relaxed.
- Local controlled QA harness result: 28/28 passed.
- Production `/dialogue/qa` must be checked after deploy to confirm the new baseline.
- Candidate gaps discovered but not added as required passing checks: RU price side-question inside booking flow and LV hours side-question inside booking flow. These should be handled as a separate Stage 41 after Stage 40 deploy confirmation.


## Stage 41 — Side-question Coverage Hardening
- Closed the two Stage 40 candidate gaps:
  - RU price side-question inside active booking flow;
  - LV hours side-question inside active booking flow.
- `_extract_price_from_line()` now recognizes Russian `евро` price strings.
- LV hours FAQ markers now cover `cikos jūs strādājat?`-style phrasing.
- Regression evaluator now recognizes grounded `евро` / `стоит` / `darba laiks` FAQ answers.
- Expanded regression matrix from 28 to 30 scenarios.
- Local controlled QA harness result: 30/30 passed.
- Production `/dialogue/qa` must be checked after deploy.


## Stage 41.1 — Cross-language Price Memory Fallback
- Fixes production Stage 41 regression result `29/30 passed`.
- Root cause: the RU price FAQ branch could parse `евро`, but the grounded price line was present in LV business memory, not in the current RU memory blob.
- Added read-only cross-language tenant business-memory lookup for price extraction before falling back to unknown-price text.
- No booking routing, calendar logic, state transitions, or evaluator expectations changed.
- Expected production `/dialogue/qa` after deploy: 30/30 passed.


## Stage 42 — Regression Baseline Lock 30/30 & Production Readiness Audit
- Documentation and audit checkpoint only.
- User confirmed Stage 41.1 production `/dialogue/qa` = 30/30 passed.
- No conversational behavior, booking routing, calendar logic, state transitions, or evaluator expectations changed.
- Added `STAGE42_PRODUCTION_READINESS_AUDIT.md` with detailed analysis of current production readiness and Stage 43 options A/B/C.
- Factual conclusion: cancellation/rescheduling code already exists, but has no regression coverage in the current 30-scenario matrix.
- Recommended next stage: Stage 43A — Production Hardening & Readiness Checks, followed by a separate cancellation/reschedule regression harness.


## Stage 43A — Production Hardening & Readiness Checks
- Production-hardening checkpoint after confirmed Stage 42 `/dialogue/qa` = 30/30 passed.
- Adds internal readiness aggregation endpoint: `GET /internal/readiness`.
- Endpoint reports env flag presence, DB connectivity, runtime table visibility, Twilio/Google/TTS readiness flags, tenant readiness, and QA baseline metadata.
- Does not expose secret values.
- Does not run regression scenarios.
- Does not change conversational behavior, booking routing, calendar logic, state transitions, FAQ/business-memory logic, cancellation/rescheduling behavior, or evaluator rules.
- Recommended next stage remains Stage 44 — Cancellation/Reschedule Regression Harness.


## Stage 44 — Cancellation/Reschedule Regression Harness
- Regression-harness stage after confirmed Stage 43A `/dialogue/qa` = 30/30 passed and `/internal/readiness` = ok.
- Adds Stage 44 cancellation/reschedule scenarios to the existing QA matrix.
- Expands protected regression coverage from 30 to 40 scenarios.
- Adds regression-only calendar event fixture support inside Stage 35 calendar safe mode.
- The fixture is available only while `_STAGE35_CALENDAR_SAFE_MODE` is active and only for scenarios that explicitly define `calendar_event_fixture`.
- Runtime calendar behavior outside regression safe mode is unchanged.
- Cancellation/rescheduling behavior itself is not changed in this stage.
- Protected facts covered by new scenarios:
  - RU/LV cancellation with no active booking returns no active booking;
  - RU/LV cancellation with a safe-mode fixture reaches cancelled status;
  - RU/LV reschedule with no active booking returns no active booking;
  - RU/LV reschedule with a safe-mode fixture starts reschedule flow and preserves `reschedule_event_id`;
  - RU/LV abort during reschedule keeps the current booking.
- Candidate Stage 45 gap intentionally not added as required passing QA: full natural reschedule continuation after `перенести запись` / `pārcelt pierakstu` followed by a date-only or fuzzy-date answer. The existing flow starts reschedule, but continuation still needs dedicated root-cause analysis before behavior changes.


## Stage 45 — Reschedule Flow Completion
- Behavior-hardening stage after confirmed Stage 44 `/dialogue/qa` = 40/40 passed.
- Root cause found in existing reschedule continuation: after `перенести запись` / `pārcelt pierakstu`, Repliq stored `reschedule_event_id`, but did not persist the original service from the matched calendar event into the active booking context.
- Because the active reschedule context had no service, the next fuzzy date/time answer such as `послезавтра вечером` / `parīt vakarā` could fall into service-selection prompts instead of regenerating new slots.
- Added deterministic service inference from the existing calendar event summary/description, e.g. `Clinic Demo - konsultācija`, during reschedule start.
- Existing `book_appointment_for_datetime()` update path remains the execution point for actual calendar update when `pending.reschedule_event_id` is present.
- Added four Stage 45 regression scenarios covering full RU/LV reschedule completion by positive slot acknowledgement and numeric slot choice.
- Regression matrix expands from 40 to 44 scenarios.
- Runtime calendar update behavior is unchanged outside the existing reschedule path; Stage 35 safe mode still prevents real calendar mutation in `/dialogue/qa`.


## Stage 45.1 — Reschedule Slot Evaluator Calibration
- Hotfix after Stage 45 production `/dialogue/qa` returned 40/44 passed.
- The four failing scenarios were the new full reschedule flows only.
- QA output showed the actual reschedule behavior was successful: reschedule started, `reschedule_event_id` stayed present, new slots were offered, confirmation was reached, and final confirmation completed.
- The only missing expected token was `multiple_slot_options`.
- Root cause: Stage 35 evaluator checked the final assistant turn first. In a full reschedule flow the final turn contains only the confirmed time, while the multiple slot offer happened on the earlier slot-generation turn.
- Updated evaluator detection to count multiple offered times on any individual turn via existing `_turn_times()`.
- No conversational behavior, booking routing, cancellation/reschedule runtime logic, or calendar update logic changed.
- Expected production `/dialogue/qa` after deploy: 44/44 passed.

## Stage 46 — Calendar Runtime Cancel/Reschedule Hardening
- Behavior/runtime hardening stage after confirmed Stage 45.1 production `/dialogue/qa` = 44/44 passed.
- Root cause found in the completed reschedule path: `book_appointment_for_datetime()` correctly chose `update_calendar_event()` when `pending.reschedule_event_id` existed, but the final customer-facing text was later rewritten by the humanize/AI/Stage 33 soft UX layers as a generic new-booking confirmation such as “записал вас” / “pierakstīju jūs”.
- Added explicit reschedule completion metadata on successful update-path finalization: `calendar_action=update_event`, `reschedule_finalized=True`, and `preserve_text=True`.
- Stage 33 now respects `preserve_text` / `reschedule_finalized` and does not rewrite completed reschedule wording into a generic booking message.
- Cancellation success now exposes `calendar_action=delete_event` for regression/audit visibility.
- QA runner now records safe metadata (`calendar_action`, `reschedule_finalized`) per turn so the safe-mode regression suite can verify delete/update routing without mutating Google Calendar.
- Added Stage 46 regression scenarios for RU/LV cancellation delete-path coverage and RU/LV reschedule update-path + final-text coverage.
- Regression matrix expands from 44 to 48 scenarios.
- Real Google Calendar mutation is still disabled in `/dialogue/qa` by Stage 35 calendar safe mode; runtime functions outside safe mode still call `delete_calendar_event()` and `update_calendar_event()` as before.
- Expected production `/dialogue/qa` after deploy: 48/48 passed.

## Stage 47 — Live Calendar E2E Smoke Audit & Baseline Sync
- Audit/checklist stage after confirmed Stage 46 production `/dialogue/qa` = 48/48 passed.
- Updates internal readiness QA baseline metadata from 44/44 to 48/48 so `/internal/readiness` reflects the current protected regression baseline.
- Adds `STAGE47_LIVE_CALENDAR_E2E_SMOKE_AUDIT.md` with the manual live Google Calendar smoke checklist.
- No conversational behavior, booking routing, cancellation/reschedule runtime logic, slot generation, date parsing, side-question behavior, or Google Calendar mutation functions were changed.
- Live smoke is still required because `/dialogue/qa` runs in Stage 35 calendar safe mode and intentionally does not create/update/delete real Google Calendar events.
- Pass criteria for live smoke: real booking creates one event, reschedule updates the same event without duplication, cancellation removes it, and `/dialogue/qa` remains 48/48.



## Stage 48 — Text MVP UX Scope Hardening
- Current MVP scope is text receptionist first. Voice/calls remain future expansion only.
- Adds read-only `product_scope` metadata to `/internal/readiness` so active MVP scope is explicit.
- Hardens Russian customer-facing text so raw Latvian minimal-catalog labels such as `konsultācija` and price token `eiro` are not exposed when safe localized text is available.
- Adds text-only helpers for localized service/price display. These helpers do not mutate canonical service keys, booking state, slot generation, or calendar payloads.
- Expands regression matrix from 48 to 50 scenarios with RU text UX guards.
- Expected production `/dialogue/qa` after deploy: 50/50 passed.


## Stage 49 — Text Channel Production Smoke Audit
- Stage 49 is a text-first MVP audit/checklist stage.
- User-confirmed baseline before this stage: Stage 48 deployed with `/dialogue/qa = 50/50 passed` and `/internal/readiness = ok`.
- No conversational routing, booking, cancellation, reschedule, slot generation, date parsing, or calendar mutation logic is changed.
- `/internal/readiness` now exposes read-only `text_channel_smoke` metadata so the current production smoke scope is visible without running or mutating anything.
- Recommended first live channel remains `/dev_chat_ui`; Telegram/WhatsApp text can be checked later as integration smoke, while voice/calls remain future scope.

## Stage 50 — Text MVP Launch Demo Readiness
- Stage 50 is a launch/demo readiness metadata and documentation stage after confirmed Stage 49 live text smoke success.
- User reported that all proposed text smoke tests across RU/LV/EN worked and appointments were created successfully.
- No conversational routing, booking, cancellation, reschedule, slot generation, date parsing, side-question handling, or Google Calendar mutation logic is changed.
- `/internal/readiness` now exposes read-only `client_demo_readiness` metadata with Stage 50 demo scope, recommended demo channel, demo paths, and explicit non-scope items.
- Active MVP scope remains text-first receptionist; voice/calls remain future phase.
- Current protected regression baseline remains `/dialogue/qa = 50/50 passed`.
- Recommended next stage: Stage 51 — Tenant Config / Business Memory Admin Hardening.


## Stage 51 — Tenant Config / Business Memory Admin Hardening
- Stage 51 is an admin/readiness hardening stage after confirmed Stage 50 production `/dialogue/qa = 50/50 passed` and `/internal/readiness = ok`.
- No receptionist conversational behavior is changed: booking, price side-questions, slot selection, confirmation, cancellation, reschedule, date parsing, slot generation, and Google Calendar create/update/delete paths remain untouched.
- Adds read-only tenant admin readiness metadata for tenant config and business memory.
- Adds `GET /tenant/admin/readiness?tenant_id=...` as a safe admin audit endpoint.
- `/tenant/config` and `/tenant/config/update` responses now include `admin_readiness` so the current tenant config state is visible after loading or saving settings.
- `/internal/readiness` now includes `tenant_admin_config` for the requested tenant.
- Stage 51 checks editable SaaS/admin surfaces: business identity, timezone, hours JSON, service catalog source, business memory language coverage, Google/calendar setup, service account presence, and runtime missing items.
- The new audit endpoints do not call LLMs, mutate tenant config, mutate conversations, or create/update/delete Google Calendar events.
- Current protected regression baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 52 — Demo UI / Tenant Config UX Hardening
- Reworked `/tenant/config/ui` from a technical editor into a demo-safe text-first MVP admin surface.
- Added visible readiness/status cards, service catalog preview, business memory guidance, quick links, and collapsed advanced JSON settings.
- Existing Google service account JSON is no longer loaded into the UI; the field is paste-to-replace only.
- `/tenant/config` and `/tenant/config/update` now return secret-safe tenant/settings views with configured flags instead of raw secret values.
- Added Stage 52 config UI hardening metadata to `/internal/readiness` and tenant config responses.
- No receptionist core behavior, regression evaluator, or Google Calendar runtime logic changed.
- Expected production baseline after deploy remains `/dialogue/qa` = 50/50 passed.

## Stage 52.1 — Service Catalog Localization Polish
- Small demo/admin UI polish after Stage 52.
- `/tenant/config/ui` service catalog preview now uses client-facing `services_lv`, `services_ru`, and `services_en` names when available, so the preview does not show raw/minimal LV labels in RU/EN columns.
- Canonical `service_catalog_json` keys remain unchanged for runtime matching.
- Adds `service_catalog_preview_uses_client_facing_names=true` to tenant config UI readiness metadata.
- No receptionist core behavior, regression evaluator, Google Calendar runtime logic, booking, cancellation, reschedule, side-question handling, slot generation, or date parsing changed.
- Expected production baseline remains `/dialogue/qa = 50/50 passed`.



## Stage 53 — Client Demo Script & Demo Mode Readiness
- Stage 53 is a read-only demo script/readiness stage after confirmed Stage 52.1 production `/dialogue/qa = 50/50 passed`.
- Adds `GET /demo/script?tenant_id=...` with a deterministic text-first demo script, pages-to-open checklist, RU/LV demo messages, calendar checks, fallback plan, and known limitations.
- `/internal/readiness` now exposes `client_demo_script` metadata for the requested tenant.
- `/tenant/config/ui` quick links now include the demo script endpoint for easier client-demo preparation.
- The endpoint is read-only and does not call LLMs, mutate conversations, change tenant config, or create/update/delete Google Calendar events.
- No receptionist core behavior, regression evaluator, Google Calendar runtime logic, booking, cancellation, reschedule, side-question handling, slot generation, or date parsing changed.
- Active MVP scope remains text-first receptionist. Voice/calls remain future scope.
- Expected production baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 54 — Launch Readiness Lock
- Stage 54 is a read-only launch/demo lock checkpoint after confirmed Stage 53 production `/dialogue/qa = 50/50 passed` and demo script readiness.
- No receptionist core behavior is changed: booking, price side-questions, slot selection, confirmation, cancellation, reschedule, date parsing, slot generation, and Google Calendar create/update/delete paths remain untouched.
- Adds `GET /launch/readiness?tenant_id=...` as a safe launch-readiness summary endpoint.
- Adds `launch_readiness_lock` metadata to `/internal/readiness` for the requested tenant.
- Adds Launch readiness links to `/tenant/config/ui` and quick links so the demo/admin surface has a final launch gate view.
- The launch lock summarizes: protected regression baseline, text-first MVP scope, tenant readiness, tenant admin readiness, demo-safe config UI, demo script readiness, manual live smoke status, demo order, do-not-promise items, and post-MVP backlog.
- The new endpoint is read-only. It does not call LLMs, run demo flows, mutate conversations, change tenant config, or create/update/delete calendar events.
- Current protected regression baseline remains `/dialogue/qa = 50/50 passed`.
- If production `/launch/readiness` returns `status=locked` and `/dialogue/qa` remains 50/50, Repliq can be treated as text MVP demo/pilot candidate.

## Stage 55 — Pilot Client Setup / Tenant Onboarding Polish
- Stage 55 is a pilot setup/readiness hardening stage after confirmed Stage 54 launch readiness lock.
- No receptionist core behavior is changed: booking, price side-questions, slot confirmation, cancellation, reschedule, date parsing, slot generation, regression evaluator, and Google Calendar create/update/delete paths remain untouched.
- Adds `GET /pilot/setup/readiness?tenant_id=...` as a read-only pilot setup summary endpoint.
- `/internal/readiness` now includes `pilot_setup_readiness` for the requested tenant.
- `/onboarding/status` now makes effective vs persisted onboarding completion explicit with `persisted_state_matches_effective` and `effective_completion_source`.
- `/google/calendars` now returns selected-calendar metadata, and `/google/calendars/ui` no longer looks blocked when Google returns an empty calendar list but a selected calendar is already saved.
- `/tenant/config/ui` now links to Pilot setup from the header and quick links.
- Stage 55 keeps the active MVP scope text-first; voice/calls remain future scope.
- Expected production baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 56 — Business Memory / FAQ Admin Polish
- Stage 56 is an admin/readiness and UI polish stage after confirmed Stage 55 pilot setup readiness.
- No receptionist core behavior is changed: booking, price side-questions, slot confirmation, cancellation, reschedule, date parsing, slot generation, regression evaluator, and Google Calendar create/update/delete paths remain untouched.
- Adds `GET /business-memory/readiness?tenant_id=...` as a read-only business memory / FAQ admin readiness endpoint.
- `/internal/readiness` now includes `business_memory_admin` for the requested tenant.
- `/tenant/config` and `/tenant/config/update` responses now include `business_memory_admin` metadata so the admin UI can show memory readiness without exposing secrets.
- `/tenant/config/ui` now links to Memory readiness and shows a business-memory readiness panel with LV/RU/EN line and price-fact counts.
- Stage 56 checks whether business memory is configured per language, whether each client-facing service appears in the relevant memory text, and whether useful price/address/hours facts are present as guidance.
- The new endpoint is read-only. It does not call LLMs, mutate tenant config, mutate conversations, or create/update/delete Google Calendar events.
- Active MVP scope remains text-first receptionist. Voice/calls remain future scope.
- Expected production baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 57 — Basic Analytics / Usage Visibility
- Stage 57 is an analytics/readiness and admin visibility stage after confirmed Stage 56 production `/dialogue/qa = 50/50 passed`.
- No receptionist core behavior is changed: booking, price side-questions, slot confirmation, cancellation, reschedule, date parsing, slot generation, regression evaluator, and Google Calendar create/update/delete runtime paths remain untouched.
- Adds `GET /usage/readiness?tenant_id=...` and alias `GET /analytics/readiness?tenant_id=...` as read-only usage/analytics readiness endpoints.
- `/internal/readiness` now includes `usage_analytics_readiness` for the requested tenant.
- `/tenant/config` and `/tenant/config/update` responses now include `usage_analytics_readiness` metadata so admin surfaces can show analytics visibility status without mutating anything.
- `/tenant/config/ui` now links to Usage readiness; the dashboard JSON links also expose usage readiness.
- Stage 57 summarizes existing dashboard/usage visibility: analytics totals, window usage, channels, top services, plan/limit usage, usage events breakdown, table checks, and safe links.
- The new endpoint is read-only. It does not call LLMs, mutate tenant config, mutate conversations, or create/update/delete Google Calendar events.
- Active MVP scope remains text-first receptionist. Voice/calls remain future scope.
- Expected production baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 58 — Auth / Access Boundaries for Admin Surfaces
- Stage 58 is a read-only access-boundary audit/readiness stage after confirmed Stage 57 production `/dialogue/qa = 50/50 passed`.
- No receptionist core behavior is changed: booking, price side-questions, slot confirmation, cancellation, reschedule, date parsing, slot generation, regression evaluator, and Google Calendar create/update/delete runtime paths remain untouched.
- Adds `GET /access/readiness?tenant_id=...` and alias `GET /admin/access/readiness?tenant_id=...` as read-only admin/access boundary readiness endpoints.
- `/internal/readiness` now includes `access_boundaries_readiness` for the requested tenant.
- `/tenant/config` and `/tenant/config/update` responses now include `access_boundaries_readiness` metadata.
- `/tenant/config/ui` and `/dashboard` now link to Access readiness.
- Stage 58 intentionally does not enforce auth yet. It documents that current admin/demo surfaces are private-demo/internal-pilot only until real admin authentication and tenant ownership checks are added.
- Expected `/access/readiness.status` is `attention`, with `private_demo_ready=true` and `public_saas_ready=false` until auth is implemented.
- The endpoint is read-only. It does not call LLMs, mutate tenant config, mutate conversations, or create/update/delete Google Calendar events.
- Active MVP scope remains text-first receptionist. Voice/calls remain future scope.
- Expected production baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 59 — Telegram Text Channel Smoke Readiness
- Stage 59 is a read-only Telegram text-channel readiness/smoke stage after confirmed Stage 58 production `/dialogue/qa = 50/50 passed`.
- No receptionist core behavior is changed: booking, price side-questions, slot confirmation, cancellation, reschedule, date parsing, slot generation, regression evaluator, and Google Calendar create/update/delete runtime paths remain untouched.
- Adds `GET /telegram/readiness?tenant_id=...` and alias `GET /channels/telegram/readiness?tenant_id=...`.
- `/internal/readiness` now includes `telegram_text_channel_readiness` for the requested tenant.
- `/tenant/config` and `/tenant/config/update` responses now include `telegram_text_channel_readiness` metadata.
- `/tenant/config/ui` and `/dashboard` now link to Telegram readiness.
- Stage 59 treats Telegram as an external text channel only. Voice/calls remain future scope.
- The readiness endpoint checks Telegram configuration flags, webhook-secret presence, tenant readiness, usage visibility, and manual smoke steps without exposing token/secret values.
- The endpoint is read-only. It does not call Telegram APIs, set webhooks, call LLMs, mutate tenant config, mutate conversations, or create/update/delete Google Calendar events.
- Expected production baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 59.1 — Telegram Text Channel Language/Menu Hardening
- Stage 59.1 is a targeted Telegram text-channel hardening stage after live Telegram smoke revealed channel-level UX bugs.
- Factual trigger: webhook worked and Telegram responded, but RU free-text flow switched to LV after short slot/confirmation replies, and the old persistent LV Telegram menu created state/menu-routing issues.
- Receptionist core behavior remains unchanged: booking routing, slot generation, date/time parsing, price side-question handling, cancellation, reschedule, Google Calendar runtime actions, and regression evaluator logic are not changed.
- Telegram is kept as a free-text text channel for the MVP. The old persistent LV reply keyboard is disabled/removed by sending `remove_keyboard` instead of a custom menu.
- `/start` and help now show simple text instructions and remove the old keyboard.
- Short neutral Telegram replies such as `2`, `10:00`, `да`, `jā`, and `ok` no longer force LV as `lang_hint`; the core can preserve the active conversation language.
- Old LV menu button text is handled defensively, but menu buttons are no longer required for the MVP flow.
- Telegram outgoing text is guarded against accidental internal prompt/memory labels such as `business_memory_lv:`.
- `/telegram/readiness` now reports `stage = 59.1` and includes `stage59_1_hardening` metadata.
- Active MVP scope remains text-first receptionist. Voice/calls remain future scope.
- Expected production baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 60 — Telegram Live Smoke Lock
- Stage 60 is a read-only Telegram live-smoke lock stage after Stage 59.1 was verified by the user in production.
- User-reported factual trigger: Telegram text flow works after Stage 59.1; RU short replies no longer switch to LV, old LV menu no longer breaks the flow, and raw business-memory labels no longer leak.
- No receptionist core behavior is changed: booking routing, slot generation, date/time parsing, price side-question handling, confirmation, cancellation, reschedule, Google Calendar runtime actions, and regression evaluator logic are not changed.
- Adds `GET /telegram/live-smoke/readiness?tenant_id=...` with aliases `GET /telegram/smoke/readiness?tenant_id=...` and `GET /channels/telegram/live-smoke/readiness?tenant_id=...`.
- `/internal/readiness` now includes `telegram_live_smoke_lock` for the requested tenant.
- `/tenant/config` and `/tenant/config/update` responses now include `telegram_live_smoke_lock` metadata.
- `/tenant/config/ui` and `/dashboard` now link to Telegram smoke lock.
- Stage 60 locks Telegram as the first external text channel for controlled pilot use, while public SaaS readiness remains false until auth/self-serve stages are implemented.
- The endpoint is read-only. It does not call Telegram APIs, set webhooks, call LLMs, mutate tenant config, mutate conversations, or create/update/delete Google Calendar events.
- Active MVP scope remains text-first receptionist. Voice/calls remain future scope.
- Expected production baseline remains `/dialogue/qa = 50/50 passed`.

## Stage 61 — Admin Access Enforcement
- Stage 61 adds a minimal shared-admin-token access layer for internal/admin/demo surfaces after Telegram text was locked as the first external text channel.
- Enforcement is enabled by default and reads the admin token from `REPLIQ_ADMIN_TOKEN`, `ADMIN_ACCESS_TOKEN`, or `ADMIN_TOKEN`.
- Protected surfaces accept `X-Repliq-Admin-Token`, `Authorization: Bearer <token>`, `?admin_token=<token>` for browser bootstrap, or the HttpOnly `repliq_admin_token` cookie set after valid query-token entry.
- Adds `GET /admin/access/enforcement/readiness?tenant_id=...` and alias `GET /admin/access/enforcement?tenant_id=...`.
- `/internal/readiness`, `/tenant/config`, and `/tenant/config/update` responses now include `admin_access_enforcement` metadata.
- `/tenant/config/ui` and `/dashboard` now link to Admin access enforcement readiness.
- Protected surfaces include config UI/JSON/update, internal/readiness, launch/pilot/memory/usage/access/Telegram readiness, dashboard/analytics/usage/bookings/conversations/activity, tenant list/admin surfaces, dev chat/dev logs, and onboarding admin screens.
- `/dialogue/qa` remains unprotected for production regression checks. `/telegram/webhook` remains unprotected by the admin-token layer because it is the Telegram callback and is protected by Telegram secret-token validation. `/google/callback` remains available for OAuth redirect flow.
- This is not final public SaaS auth: public SaaS still requires per-user login/session, tenant ownership checks, role separation, and CSRF/session hardening.
- Receptionist core behavior is unchanged: booking, side-questions, confirmation, cancellation, reschedule, slot generation, date parsing, Google Calendar runtime actions, Telegram webhook handling, and regression evaluator are not changed.
- Expected production baseline remains `/dialogue/qa = 50/50 passed`.


## Stage 62 — Admin Login / Session Layer

Stage 62 adds a browser login/session layer over Stage 61 protected admin surfaces. `/admin/login` accepts the configured `REPLIQ_ADMIN_TOKEN` and sets a signed HttpOnly `repliq_admin_session` cookie. `/admin/logout` clears admin cookies. `/admin/session` reports current browser auth status. `/admin/session/readiness` and `/internal/readiness` expose Stage 62 readiness metadata. This does not change receptionist core behavior or Telegram/Calendar runtime.

## Stage 63 — Tenant Creation / Signup Flow Foundation

Status: implemented in archive, pending deploy verification.

Stage 63 starts the self-serve SaaS transition by hardening tenant creation and exposing a protected signup/create-tenant UI. The receptionist runtime is unchanged.

Added:
- `/tenant/creation/readiness` and `/signup/readiness`
- `/signup`, `/signup/ui`, `/tenant/create/ui` aliases for the existing onboarding create UI
- `tenant_slug` support with validation/reserved slugs/collision checks
- Stage 63 readiness in `/internal/readiness` and `/tenant/config`
- Create tenant links in `/dashboard` and `/tenant/config/ui`
- Stage 61/62 protection coverage for `POST /tenant/create`

Public SaaS readiness remains false until owner identity, tenant ownership, billing, and public signup abuse protection are implemented.

## Stage 64 — Self-Serve Onboarding Wizard

Status: implemented locally in this archive, pending deploy verification.

Added protected onboarding wizard/readiness layer:
- `/onboarding/wizard`
- `/onboarding/wizard/ui`
- `/onboarding/wizard/readiness`
- `/onboarding/checklist/readiness`
- `/self-serve/onboarding/readiness`

Wizard checklist covers business profile, services, prices, business memory/FAQ, Google Calendar connection, calendar selection, Telegram text channel, and final Telegram smoke lock.

Receptionist core was not changed. Voice/calls remain future phase.

## Stage 65 — Google Calendar OAuth Self-Serve

Status: implemented locally in this archive, pending deploy verification.

Stage 65 hardens Google Calendar setup as a protected self-serve flow after the Stage 64 onboarding wizard. The receptionist runtime is unchanged.

Added:
- `/google/self-serve/readiness`
- `/google/calendar/self-serve/readiness`
- `/calendar/self-serve/readiness`
- Stage 65 readiness metadata in `/internal/readiness`, `/tenant/config`, and `/tenant/config/update`
- Google self-serve readiness link in onboarding links and Google Calendar UI
- Stage 61/62 protection coverage for `/google/connect`, `/google/calendars`, `/google/calendars/ui`, and `POST /google/select_calendar`

`/google/callback` remains available for Google OAuth redirect. Public SaaS readiness remains false until owner auth, tenant ownership, billing, CSRF, and public abuse protection are implemented.

## Stage 66 — Service Catalog Builder

Status: implemented locally in this archive, pending deploy verification.

Stage 66 adds a protected self-serve service catalog builder so an admin can manage services without editing raw tenant JSON. Receptionist runtime orchestration remains unchanged.

Added:
- `/service-catalog/builder` and `/service-catalog/builder/ui`
- `/tenant/service-catalog` JSON preview
- `POST /tenant/service-catalog/update`
- `/service-catalog/readiness`, `/tenant/service-catalog/readiness`, and `/services/readiness`
- Stage 66 readiness metadata in `/internal/readiness`, `/tenant/config`, and `/tenant/config/update`
- Service catalog links in onboarding links, dashboard, tenant config UI, and onboarding wizard service/prices steps

Builder saves normalized catalog data to the tenant service catalog column, syncs `services_lv/services_ru/services_en`, and can update a managed service-price block in business memory so price side-questions stay grounded.

Public SaaS readiness remains false until owner auth, tenant ownership, billing, CSRF, and public rate limits exist.

## Stage 67 — Business Memory / FAQ Builder

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added protected Business Memory / FAQ builder UI and JSON/update endpoints.
- Added Stage 67 readiness payload for multilingual memory/FAQ coverage.
- Added builder links to onboarding/config/dashboard surfaces.
- Kept receptionist core, Telegram webhook, calendar runtime, regression evaluator, and voice/call runtime unchanged.

Expected verification:
- `/dialogue/qa` = 50/50 passed.
- `/business-memory/readiness?tenant_id=clinic_demo` returns `stage=67` and builder readiness.
- `/business-memory/builder?tenant_id=clinic_demo` opens via admin session.
- `/tenant/business-memory?tenant_id=clinic_demo` is protected and returns editable memory fields.
- `/tenant/business-memory/update` saves protected changes.

## Stage 68 — Telegram Bot Self-Serve Setup

Status: closed by deploy verification.

Confirmed after deploy:
- `/dialogue/qa` = 50/50 passed.
- Telegram setup UI works.
- Telegram webhook status is correct.
- `tenant_id=clinic_demo` webhook is set.
- Telegram bot answers.
- Telegram token and webhook secret are not exposed.
- Readiness/config/UI/security checks passed.

Public self-serve SaaS remains not fully ready yet.

## Stage 69 — Client Dashboard Self-Serve Control Center

Status: closed by deploy verification.

Scope:
- Added protected control center JSON/readiness/UI endpoints:
  - `/control-center`
  - `/control-center/ui`
  - `/control-center/readiness`
  - `/self-serve/control-center`
  - `/self-serve/control-center/readiness`
  - `/client/dashboard`
  - `/client/dashboard/ui`
  - `/client/control-center`
  - `/client/control-center/ui`
- Aggregates existing tenant setup/readiness blocks into one protected self-serve control center:
  - business profile and working hours;
  - service catalog;
  - Business Memory / FAQ;
  - Google Calendar self-serve;
  - Telegram setup;
  - Telegram smoke lock;
  - usage/dashboard visibility;
  - launch/access readiness references.
- Added control-center links to onboarding links, dashboard, tenant config UI, `/tenant/config`, `/tenant/config/update`, and `/internal/readiness`.
- Added Stage 69 paths to Stage 61/62 protected admin surfaces.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, dialogue QA evaluator, and voice/calls were not changed.

Confirmed after deploy:
- `/dialogue/qa` = 50/50 passed.
- Control Center readiness/UI links/security checks passed.
- Public self-serve SaaS remains not fully ready yet.


## Stage 70 — Public SaaS Readiness Gap Audit

Status: closed by deploy verification.

Scope:
- Added protected public SaaS readiness/gap-audit JSON and UI endpoints.
- Added `public_saas_gap_audit_readiness` to `/internal/readiness`, `/tenant/config`, and `/tenant/config/update`.
- Added Public SaaS audit links to onboarding links, Control Center links, dashboard quick links, and tenant config UI quick links.
- Kept `public_saas_ready=false` by design.

The audit reports the factual blockers before public SaaS launch:
- per-owner public auth missing;
- tenant ownership / role checks missing;
- public signup boundary not open yet;
- billing/subscription lifecycle foundation only;
- CSRF/public browser write hardening missing;
- client-owner and super-admin surfaces not separated;
- public SaaS ops/rate limits/billing-grade usage proof not complete.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, dialogue QA evaluator, and voice/calls were not changed.

Confirmed after deploy:
- `/dialogue/qa` = 50/50 passed.
- Public SaaS gap audit/readiness/UI links/security checks passed.
- `public_saas_ready` remains false by design.

## Stage 71 — Owner Auth / Public Client Account Foundation

Status: implemented, pending deployment verification.

Summary:
- Added owner account/session foundation for client-owner access.
- Added owner_accounts and owner_tenant_access runtime tables.
- Added admin-protected owner bootstrap/bind endpoints.
- Added public owner login/logout/session endpoints.
- Added owner-session-protected read-only owner dashboard/control-center surfaces.
- Integrated owner auth foundation into internal readiness and public SaaS gap audit.
- public_saas_ready remains false by design.
- Receptionist core, booking, calendar runtime, Telegram runtime, and dialogue QA evaluator were not changed.


## Stage 71.1 — Owner Readiness / Tenant Context Fix

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added safe `owner_email` tenant column migration via `ALTER TABLE IF NOT EXISTS`.
- Updated owner bootstrap/bind flow to sync `owner_email` into tenant profile when the field is empty.
- Updated owner readiness so an active `owner_tenant_access` binding is enough to satisfy ownership readiness even if legacy tenant profile was missing `owner_email`.
- Added Owner email field to Tenant Config UI and update payload.
- Improved tenant context resolution for owner/auth/dashboard, tenant config, control center, public SaaS audit, admin login and dashboard surfaces so `clinic_demo` context is preserved instead of falling back to `default` when a session/query/default-demo tenant is available.

Expected verification:
- `/dialogue/qa` = 50/50 passed.
- `/owner/auth/readiness?tenant_id=clinic_demo` no longer shows `tenant_owner_email_missing` after bootstrap/bind or owner_email save.
- `/tenant/config/ui?tenant_id=clinic_demo` shows Owner email and saves it without exposing codes/secrets.
- Owner dashboard/login/session still work with `clinic_demo`.
- Control Center / Tenant config / Dashboard default to `clinic_demo` when opened from a `clinic_demo` session or explicit query.
- public_saas_ready remains false by design.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, dialogue QA evaluator, and voice/calls were not changed.

## Stage 72 — Public Signup Boundary / Owner Signup Flow Foundation

Status: deployed and verified by user. `/dialogue/qa` = 50/50 passed. Public signup, owner session/dashboard, protected legacy signup routes and security checks were reported OK.

Scope:
- Added dedicated public signup boundary endpoints that are not Stage 61 admin-token protected:
  - `GET /public/signup`
  - `GET /public/signup/ui`
  - `POST /public/signup`
  - `GET /public/signup/readiness`
  - `GET /public/signup/boundary/readiness`
  - `GET /signup/public/readiness`
- Kept existing legacy/admin tenant creation routes protected:
  - `/signup`
  - `/signup/ui`
  - `/tenant/create`
  - `/tenant/create/ui`
  - `/onboarding/create_tenant`
- Public signup creates:
  - tenant/business profile through the existing Stage 63 creation path;
  - owner account through Stage 71 owner auth foundation;
  - owner-to-tenant binding;
  - signed owner session cookie;
  - one-time owner login code for the foundation flow.
- Added public signup event/rate-limit table:
  - `public_signup_events`
- Added foundation write-boundary checks:
  - owner email required;
  - accepted terms required;
  - honeypot field check;
  - IP-hash hourly limit;
  - owner-email daily limit;
  - raw IP hash not exposed in responses.
- Integrated Stage 72 readiness into:
  - `/internal/readiness` as `public_signup_boundary_readiness`;
  - Stage 70 public SaaS gap audit.
- Updated Stage 70 public signup gap from `not_public_yet` to `foundation` when Stage 72 readiness is OK.
- `public_saas_ready` remains false by design.

Still not done before full public SaaS:
- billing/subscription gate;
- email verification or magic-link auth;
- CSRF hardening for owner browser writes;
- production-grade rate limits/abuse controls;
- full client-owner vs super-admin surface separation.

Expected verification:
- `/dialogue/qa` = 50/50 passed.
- `/public/signup/readiness?tenant_id=clinic_demo` returns `stage=72` and `public_signup_boundary_ready=true` unless disabled by env.
- `/public/signup` opens without admin login/token.
- `/signup` and `/tenant/create` remain admin protected.
- Public signup creates a new test tenant, creates owner binding, sets owner session cookie, and opens `/owner/dashboard/ui?tenant_id=<new_tenant>`.
- Owner login code hash is not exposed.
- Admin token and system secrets are not exposed.
- `/public-saas/readiness?tenant_id=clinic_demo` shows public signup boundary as foundation while `public_saas_ready=false` remains.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, dialogue QA evaluator, and voice/calls were not changed.


## Stage 73 — Billing / Subscription Gate Foundation

Status: deployed and verified by user after Stage 73.1 hotfix; `/dialogue/qa` = 50/50 passed.

Scope:
- Added manual billing/subscription foundation for tenants without integrating a live payment provider.
- Added safe tenant billing columns for provider metadata, customer/subscription identifiers, current billing period end, last billing event time, and internal billing notes.
- Reused existing `plan`, `subscription_status`, `dialogs_per_month`, and `trial_end` lifecycle fields.
- Added `suspended` as a supported blocked lifecycle state. `past_due` remains allowed with attention metadata.
- Added admin-protected billing readiness, JSON, UI and update endpoints:
  - `GET /billing/readiness`
  - `GET /billing/subscription/readiness`
  - `GET /tenant/billing/readiness`
  - `GET /tenant/billing`
  - `GET /billing`
  - `GET /tenant/billing/ui`
  - `GET /billing/ui`
  - `POST /tenant/billing/update`
- Added owner-session-protected read-only billing endpoints:
  - `GET /owner/billing`
  - `GET /owner/subscription`
  - `GET /owner/billing/ui`
  - `GET /owner/subscription/ui`
- Integrated billing readiness/status into internal readiness, tenant config, owner dashboard, control center, and public SaaS gap audit.
- Stage 70 now reports billing/subscription lifecycle as `foundation` when Stage 73 checks pass.
- `public_saas_ready` remains false by design.

Expected verification:
- `/dialogue/qa` = 50/50 passed.
- `/billing/readiness?tenant_id=clinic_demo` returns `stage=73` and `billing_subscription_gate_foundation_ready=true` for an existing tenant.
- `/tenant/billing?tenant_id=clinic_demo` is admin protected and returns billing status.
- `/tenant/billing/ui?tenant_id=clinic_demo` opens after admin login.
- `POST /tenant/billing/update` updates manual plan/status/billing metadata without exposing secrets.
- `/owner/billing?tenant_id=<owner_tenant>` works only with valid owner session or super-admin bypass.
- `/owner/billing/ui?tenant_id=<owner_tenant>` is read-only for owner mode.
- `/public-saas/readiness?tenant_id=clinic_demo` shows billing/subscription as foundation while `public_saas_ready=false` remains.
- Stage 72 public signup and owner session flow remains working.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.

## Stage 73.1 — Billing Update Route Import Hotfix

Status: deployed and verified by user; `/dialogue/qa` = 50/50 passed.

Reason:
- Render deployed Stage 73 build successfully, but runtime import failed before app startup.
- Render traceback pointed to `@app.post("/tenant/billing/update")` and `NameError: name 'TenantBillingUpdateRequest' is not defined` during FastAPI route registration on Python 3.14.

Fix:
- Changed only the Stage 73 billing update route signature to avoid a forward reference to the request model at import/route-registration time.
- The route now accepts a raw request dict via `Body(...)` and instantiates `TenantBillingUpdateRequest` at call time, after module import is complete.
- Billing request validation remains handled by the same Pydantic model.

Not changed:
- booking routing;
- slot generation;
- date/time parsing;
- price side-question logic;
- confirmation;
- cancel/reschedule;
- Google Calendar runtime;
- Telegram webhook runtime;
- dialogue QA evaluator;
- LLM orchestration;
- Stage 73 billing logic semantics.

Expected verification:
- Render app starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/billing/readiness?tenant_id=clinic_demo` works.
- `/tenant/billing/update` remains admin protected and still validates payload through `TenantBillingUpdateRequest` at call time.
- `public_saas_ready` remains false.


## Stage 74 — CSRF / Browser Write Hardening Foundation

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added Stage 74 browser write hardening for cookie-authenticated admin/owner writes.
- Added same-origin Fetch Metadata / Origin / Referer checks for browser writes that rely on signed session cookies.
- Added signed CSRF token support via `X-Repliq-CSRF-Token` for admin, owner, and public scopes.
- Added explicit admin token header/bearer/query bypass for automation/API scripts that do not rely on browser session cookies.
- Added cross-site browser POST blocking for public signup while keeping public signup usable from the same-origin UI and non-browser API clients.
- Added Stage 74 readiness endpoints:
  - `GET /csrf/readiness`
  - `GET /security/csrf/readiness`
  - `GET /browser-write/readiness`
  - `GET /browser-write-hardening/readiness`
  - `GET /csrf/token`
- Added Stage 74 readiness into Control Center and Public SaaS gap audit.
- Stage 70 now reports browser write hardening as ready/foundation when Stage 74 checks pass.
- `public_saas_ready` remains false by design; remaining blockers are production abuse/rate limits, email verification/magic-link auth, and full client-owner vs super-admin separation hardening.

Protected/hardened write paths:
- Admin browser writes:
  - `/owner/accounts/bootstrap`
  - `/tenant/owner/bind`
  - `/google/select_calendar`
  - `/tenant/billing/update`
  - `/tenant/business-memory/update`
  - `/business-memory/update`
  - `/telegram/setup/update`
  - `/telegram/setup/set-webhook`
  - `/telegram/set-webhook`
  - `/onboarding/finish`
  - `/onboarding/create_tenant`
  - `/tenant/create`
  - `/tenant/change_plan`
  - `/tenant/service-catalog/update`
  - `/service-catalog/update`
  - `/tenant/config/update`
  - dev write/test helper endpoints already behind admin boundary.
- Owner browser writes:
  - `/owner/logout`
- Public browser writes:
  - `/public/signup`
- External channel webhooks are excluded from CSRF checks:
  - `/voice/incoming`
  - `/voice/language`
  - `/voice/intent`
  - `/sms/incoming`
  - `/whatsapp/incoming`
  - `/telegram/webhook`

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/csrf/readiness?tenant_id=clinic_demo` returns `stage=74` and `csrf_browser_write_hardening_ready=true`.
- `/security/csrf/readiness?tenant_id=clinic_demo` works and is admin protected.
- `/csrf/token?scope=admin&tenant_id=clinic_demo` works only with admin auth and does not expose raw secrets.
- Existing admin UIs still save configuration from same-origin browser pages:
  - tenant config update
  - service catalog update
  - business memory update
  - Telegram setup update
  - Google calendar selection
  - billing update
- `/public/signup` still works from the same-origin public signup UI.
- Cross-site browser POST attempts to protected cookie-authenticated write paths return Stage 74 `403`.
- `/public-saas/readiness?tenant_id=clinic_demo` includes `csrf_browser_write_hardening_ready=true` while `public_saas_ready=false` remains.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, dialogue QA evaluator, LLM orchestration, billing semantics, and voice/calls were not changed.

## Stage 75 — Abuse Protection / Rate Limits Hardening Foundation

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added central `abuse_events` ledger table with safe HMAC-hashed IP/subject metadata.
- Added rate-limit gates for admin login, owner login, public signup, and public CSRF token issuance.
- Added readiness endpoints:
  - `GET /abuse/readiness`
  - `GET /security/abuse/readiness`
  - `GET /rate-limits/readiness`
  - `GET /abuse-protection/readiness`
- Added Control Center integration.
- Added Public SaaS gap audit integration.
- Stage 72 public signup-specific limits remain active; Stage 75 adds a shared abuse ledger around public signup.
- `public_saas_ready` remains false by design; remaining blockers are email verification/magic-link auth, client-owner vs super-admin separation hardening, and final public SaaS readiness lock.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/abuse/readiness?tenant_id=clinic_demo` returns `stage=75`.
- `/rate-limits/readiness?tenant_id=clinic_demo` works.
- `/control-center/ui?tenant_id=clinic_demo` shows Abuse / rate limits.
- `/public-saas/readiness?tenant_id=clinic_demo` includes abuse/rate-limit readiness while `public_saas_ready=false` remains.
- Admin login, owner login, and public signup still work.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.


## Stage 76 — Email Verification / Magic Link Auth Foundation

Status: deployed and verified. `/dialogue/qa` = 50/50 passed. Stage 76 is closed.

Scope:
- Added one-time owner magic-link auth foundation.
- Added `owner_magic_links` table with HMAC token hashes only.
- Added `owner_accounts.email_verified_at` via safe schema extension.
- Added admin-protected readiness endpoints: `/email/readiness`, `/email-verification/readiness`, `/magic-link/readiness`, `/owner/magic-link/readiness`.
- Added admin-protected `POST /owner/magic-link/bootstrap`.
- Added public owner auth endpoints: `GET/POST /owner/magic-login`.
- Public signup now also returns one-time magic-link fields while preserving the Stage 71 setup-code fallback.
- Control Center and Public SaaS audit now include email/magic-link auth readiness.
- `public_saas_ready` remains false by design; remaining blockers are client-owner vs super-admin separation hardening and final public SaaS readiness lock.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/email/readiness?tenant_id=clinic_demo` returns `stage=76`.
- `/magic-link/readiness?tenant_id=clinic_demo` works.
- `/owner/magic-link/bootstrap` creates a one-time magic link/token for an existing bound owner.
- `/owner/magic-login?token=...` sets the owner session and marks owner email verified.
- `/owner/session?tenant_id=<tenant>` shows authenticated owner session after magic login.
- `/public/signup` still works.
- `/public-saas/readiness?tenant_id=clinic_demo` includes email/magic-link readiness while `public_saas_ready=false` remains.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.


## Stage 77 — Client-owner vs Super-admin Separation Hardening

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added owner/super-admin separation readiness endpoints:
  - `GET /owner-admin-separation/readiness`
  - `GET /client-owner/separation/readiness`
  - `GET /security/owner-admin-separation/readiness`
  - `GET /tenant/isolation/readiness`
- Added explicit route/surface map for owner-safe surfaces, admin-only surfaces, public auth surfaces, and external webhook surfaces.
- Hardened owner dashboard links so client owners no longer receive admin Control Center/Public SaaS/Billing readiness links in the owner `links` block.
- Hardened owner billing UI links in owner mode so it shows only owner-safe navigation.
- Added Stage 77 separation metadata to owner dashboard payload.
- Added Control Center integration.
- Added Public SaaS gap audit integration.
- `public_saas_ready` remains false by design until Stage 78 final launch readiness lock.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/owner-admin-separation/readiness?tenant_id=clinic_demo` returns `stage=77` and `client_owner_superadmin_separation_ready=true`.
- `/tenant/isolation/readiness?tenant_id=clinic_demo` works and is admin protected.
- `/owner/dashboard/ui?tenant_id=<owner_tenant>` opens for an owner session and does not show admin Control Center/Public SaaS audit links.
- `/owner/billing/ui?tenant_id=<owner_tenant>` opens read-only for an owner session and does not show admin Control Center/Public SaaS audit links.
- Admin-only routes like `/control-center/ui`, `/tenant/billing/ui`, `/public-saas/readiness`, `/owner/accounts/bootstrap`, and `/tenants/ui` remain admin protected.
- `/public-saas/readiness?tenant_id=clinic_demo` includes Stage 77 separation readiness while `public_saas_ready=false` remains.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.


## Stage 77 — Client-owner vs Super-admin Separation Hardening

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added owner/super-admin separation readiness endpoints:
  - `GET /owner-admin-separation/readiness`
  - `GET /client-owner/separation/readiness`
  - `GET /security/owner-admin-separation/readiness`
  - `GET /tenant/isolation/readiness`
- Added explicit route/surface map for owner-safe surfaces, admin-only surfaces, public auth surfaces, and external webhook surfaces.
- Hardened owner dashboard links so client owners no longer receive admin Control Center/Public SaaS/Billing readiness links in the owner `links` block.
- Hardened owner billing UI links in owner mode so it shows only owner-safe navigation.
- Added Stage 77 separation metadata to owner dashboard payload.
- Added Control Center integration.
- Added Public SaaS gap audit integration.
- `public_saas_ready` remains false by design until Stage 78 final launch readiness lock.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/owner-admin-separation/readiness?tenant_id=clinic_demo` returns `stage=77` and `client_owner_superadmin_separation_ready=true`.
- `/tenant/isolation/readiness?tenant_id=clinic_demo` works and is admin protected.
- `/owner/dashboard/ui?tenant_id=<owner_tenant>` opens for an owner session and does not show admin Control Center/Public SaaS audit links.
- `/owner/billing/ui?tenant_id=<owner_tenant>` opens read-only for an owner session and does not show admin Control Center/Public SaaS audit links.
- Admin-only routes like `/control-center/ui`, `/tenant/billing/ui`, `/public-saas/readiness`, `/owner/accounts/bootstrap`, and `/tenants/ui` remain admin protected.
- `/public-saas/readiness?tenant_id=clinic_demo` includes Stage 77 separation readiness while `public_saas_ready=false` remains.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.


## Stage 77.1 — Owner/Admin Separation Readiness Type Hotfix

Status: packaged hotfix.

Purpose: fix `/owner-admin-separation/readiness` and aliases returning 500 after Stage 77 due to a set/tuple union in readiness payload construction.

Fix: convert both public auth surface collections to sets before union. No receptionist dialogue, booking, Telegram, Google Calendar, billing, CSRF, abuse/rate-limit, or magic-link semantics changed.

## Stage 78 — Final Public SaaS Readiness Lock

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added final controlled public self-service SMB MVP readiness lock.
- Added admin-protected final readiness endpoints:
  - `GET /public-saas/final-readiness`
  - `GET /public-saas/launch-readiness`
  - `GET /public-saas/ready`
  - `GET /launch/self-service/readiness`
  - `GET /self-service/launch/readiness`
- Integrated the Stage 78 final lock into `/public-saas/readiness` and `/public-saas/gap-audit` while keeping the Stage 70 detailed audit available.
- Integrated the Stage 78 final lock into the Control Center readiness payload.
- Stage 78 can set `public_saas_ready=true` only when all final gates are ready.
- Stage 78 explicitly marks `enterprise_saas_ready=false`; enterprise maturity is a later phase.

Final gates:
- Tenant exists.
- Tenant runtime config is ready.
- Admin auth/session boundary is ready.
- Control Center routes are protected.
- Owner auth and tenant ownership binding are ready.
- Public signup boundary is ready.
- Billing/subscription foundation exists and runtime gate allows the tenant.
- CSRF/browser write hardening is enabled.
- Abuse/rate-limit protection is enabled.
- Email verification / magic-link foundation is ready.
- Owner vs super-admin separation and tenant isolation are ready.
- Stage 78 readiness endpoints are admin protected.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/public-saas/final-readiness?tenant_id=clinic_demo` returns `stage=78`.
- `/public-saas/final-readiness?tenant_id=clinic_demo` returns `public_saas_ready=true` only when every gate is ready.
- `/public-saas/readiness?tenant_id=clinic_demo` returns final launch lock integration and can surface `public_saas_ready=true`.
- `/control-center/ui?tenant_id=clinic_demo` still opens.
- Owner dashboard/billing surfaces remain owner-safe.
- Admin-only routes remain admin protected.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.
