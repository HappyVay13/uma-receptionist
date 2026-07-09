# Repliq Project State

Current stage: Stage 93 — Public Signup → Owner Workspace End-to-End Polish.

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


Stage 91.1 confirmed production baseline:
- Stage 91.1 — Owner Account Logout / Auth Guard Hotfix was deployed and confirmed by user.
- Production `/dialogue/qa` result: 50/50 passed.
- User confirmed all other Stage 91.1 checks were OK.
- Stage 91 account/profile/account-billing pages require owner login and do not open without owner session/admin-only login.

Stage 92 confirmed production baseline:
- Stage 92 — Tenant Data Quality / Setup Health Guard was deployed and confirmed by user.
- Production `/dialogue/qa` result: 50/50 passed.
- User confirmed all other Stage 92 checks were OK.
- Owner setup-health/data-quality surfaces and strict owner auth boundaries were confirmed working.

Stage 93 archive status:
- Stage 93 — Public Signup → Owner Workspace End-to-End Polish implemented in archive, awaiting deploy verification.
- Adds a strict owner-only get-started/welcome handoff after public signup.
- Adds admin-protected signup-to-workspace E2E readiness only; readiness does not create test tenants.
- Reuses existing Stage 72 signup, Stage 71 owner session/binding, Stage 80 workspace, Stage 92 setup health and Stage 78 launch lock.
- No receptionist runtime, booking, Calendar, Telegram, billing/payment, auth-token, CSRF, rate-limit, magic-link, QA evaluator or LLM orchestration behavior is changed.

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

## Stage 79 — Launch UX / Public Onboarding Polish

Status: closed after deploy verification. User reported `/dialogue/qa` = 50/50 passed and all Stage 79 checks OK.

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
- Added Stage 79 Launch UX readiness aggregation over Stage 78 final lock, public signup, owner auth, owner/admin separation, and billing visibility.
- Polished public signup from technical Stage 72 wording to customer-facing workspace wording.
- Public signup UI hides raw one-time login/magic-link values in its technical details block.
- Public signup API response main links are now owner-safe and do not include admin setup links.
- Owner dashboard payload includes Stage 79 mature SMB UX metadata.
- Owner dashboard UI now presents as `Repliq Workspace` with owner-safe quickstart actions.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/launch` opens publicly.
- `/public/signup` opens and still creates tenant + owner session.
- `/launch-ux/readiness?tenant_id=clinic_demo` returns `stage=79` and `launch_ux_polish_ready=true` when Stage 78 remains ready.
- `/public-onboarding/readiness?tenant_id=clinic_demo`, `/smb/launch/readiness?tenant_id=clinic_demo`, and `/mature-smb/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/dashboard/ui?tenant_id=<owner_tenant>` opens and shows owner-safe workspace/quickstart UI.
- `/owner/billing/ui?tenant_id=<owner_tenant>` still works.
- `/public-saas/final-readiness?tenant_id=clinic_demo` remains the source of truth for `public_saas_ready`.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.



## Stage 80 — Tenant Workspace UX / Owner Setup Completion

Status: closed after deploy verification. User reported `/dialogue/qa` = 50/50 passed and all Stage 80 checks OK. The `clinic_demo` workspace checklist correctly showed `workspace_setup_complete=false` only because `business_profile.language` was missing; this was expected tenant data attention, not a Stage 80 failure.

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
- Added setup-completion task model for business profile, service catalog, business memory/FAQ, Google Calendar, Telegram, billing, owner auth, and Stage 78 launch lock.
- Added owner-safe setup checklist / next-actions workspace UI.
- Integrated Stage 80 workspace/setup links and metadata into the owner dashboard payload.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/tenant-workspace/readiness?tenant_id=clinic_demo` returns `stage=80`.
- `/owner/setup/ui?tenant_id=<owner_tenant>` opens with a valid owner session.
- `/owner/workspace/ui?tenant_id=<owner_tenant>` opens with a valid owner session.
- `/owner/setup?tenant_id=<owner_tenant>` returns Stage 80 setup-completion JSON.
- Owner dashboard/billing remain owner-safe.
- Stage 78 remains the source of truth for `public_saas_ready`.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.


## Stage 81 — Tenant Business Profile / Workspace Settings UX

Status: closed after deploy verification and Stage 81.1 hotfix. User reported `/dialogue/qa` = 50/50 passed and all Stage 81/81.1 checks OK.

Scope:
- Added owner-safe business profile/settings endpoints:
  - `GET /owner/business-profile`
  - `GET /owner/business-profile/ui`
  - `GET /owner/workspace/settings`
  - `GET /owner/workspace/settings/ui`
  - `POST /owner/business-profile/update`
- Added admin-protected readiness endpoints:
  - `GET /business-profile/readiness`
  - `GET /owner-business-profile/readiness`
  - `GET /workspace-settings/readiness`
  - `GET /tenant/business-profile/readiness`
- Owner update is limited to non-secret business profile fields: business name, language, timezone, work_start and work_end.
- Integrated business profile edit links into owner workspace/dashboard setup flow.
- Added Stage 74 owner-scope CSRF/browser-write protection for the owner business profile write endpoint.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/business-profile/readiness?tenant_id=clinic_demo` returns `stage=81`.
- `/owner/business-profile/ui?tenant_id=<owner_tenant>` opens with valid owner session.
- Saving language/profile fields through owner UI returns `ok=true`.
- `/tenant-workspace/readiness?tenant_id=clinic_demo` reflects the updated business profile completion state.
- Owner dashboard/workspace/billing remain owner-safe.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.

## Stage 81.1 — Business Profile Language Persistence Hotfix
- Fixes Stage 81 owner business-profile UX where the language selector could show `lv` but readiness still reported `missing=language` on older tenant schemas.
- Ensures `tenants.language` exists, backfills empty values to `lv`, and sets `lv` as the default for future rows.
- Does not change receptionist booking/dialogue/calendar/Telegram/billing/runtime semantics.


## Stage 82 — Service Catalog Owner UX / Setup Completion Polish

Status: closed after deploy verification. User reported `/dialogue/qa` = 50/50 passed and all Stage 82 checks OK.

Scope:
- Added owner-safe service catalog endpoints:
  - `GET /owner/services`
  - `GET /owner/services/ui`
  - `GET /owner/service-catalog`
  - `GET /owner/service-catalog/ui`
  - `POST /owner/services/update`
  - `POST /owner/service-catalog/update`
- Added admin-protected readiness endpoints:
  - `GET /owner-services/readiness`
  - `GET /owner-service-catalog/readiness`
  - `GET /service-catalog/owner/readiness`
  - `GET /workspace/services/readiness`
- Added owner-safe service catalog model, setup completion status, next actions, and service JSON editor UI.
- Owner update is limited to non-secret service catalog fields: names, aliases, descriptions, duration, price, currency, active status, and service key.
- Owner service update syncs runtime service lists and managed price facts through the existing Stage 66 service catalog logic.
- Integrated owner services links into owner dashboard/workspace setup flow.
- Added Stage 74 owner-scope CSRF/browser-write protection for owner service catalog write endpoints.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/owner-services/readiness?tenant_id=clinic_demo` returns `stage=82` and `service_catalog_owner_ux_ready=true` when routes/security are ready.
- `/owner-service-catalog/readiness?tenant_id=clinic_demo`, `/service-catalog/owner/readiness?tenant_id=clinic_demo`, and `/workspace/services/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/services/ui?tenant_id=<owner_tenant>` opens with valid owner session or super-admin bypass.
- Saving services through owner UI returns `ok=true` and keeps at least one active runtime service.
- `/tenant-workspace/readiness?tenant_id=clinic_demo` points the service catalog next-action to owner-safe `/owner/services/ui` instead of admin builder.
- Owner dashboard/workspace/billing remain owner-safe.
- Stage 78 remains the source of truth for `public_saas_ready`; `enterprise_saas_ready=false` remains explicit.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.

## Stage 83 — Business Memory / FAQ Owner UX Polish

Status: closed after deploy verification. User reported `/dialogue/qa` = 50/50 passed and all Stage 83 checks OK.

Scope:
- Added owner-safe Business Memory / FAQ endpoints:
  - `GET /owner/business-memory`
  - `GET /owner/business-memory/ui`
  - `GET /owner/faq`
  - `GET /owner/faq/ui`
  - `POST /owner/business-memory/update`
  - `POST /owner/faq/update`
- Added admin-protected readiness endpoints:
  - `GET /owner-business-memory/readiness`
  - `GET /owner-faq/readiness`
  - `GET /business-memory/owner/readiness`
  - `GET /workspace/memory/readiness`
- Added owner-safe business memory/FAQ model, setup completion, language coverage, next actions, and UI for receptionist facts.
- Owner update is limited to non-secret business memory/FAQ fields: multilingual business memory, FAQ, booking rules, generic memory, generic FAQ, booking rules, and policies.
- Integrated Business Memory / FAQ links into owner dashboard/workspace/setup flow.
- Stage 80 business_memory next_action now points to owner-safe `/owner/business-memory/ui` instead of requiring support/admin builder.
- Added Stage 74 owner-scope CSRF/browser-write protection for owner memory/FAQ write endpoints.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/owner-business-memory/readiness?tenant_id=clinic_demo` returns `stage=83` and `business_memory_owner_ux_ready=true` when routes/security are ready.
- `/owner-faq/readiness?tenant_id=clinic_demo`, `/business-memory/owner/readiness?tenant_id=clinic_demo`, and `/workspace/memory/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/business-memory/ui?tenant_id=<owner_tenant>` opens with a valid owner session or super-admin bypass.
- Saving memory/FAQ through owner UI returns `ok=true` and updates readiness/content completion.
- `/tenant-workspace/readiness?tenant_id=clinic_demo` points the business_memory next-action to owner-safe `/owner/business-memory/ui`.
- Owner dashboard/workspace/services/billing remain owner-safe.
- Stage 78 remains the source of truth for `public_saas_ready`; `enterprise_saas_ready=false` remains explicit.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.


## Stage 84 — Service Catalog / Business Memory Consistency Guard

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added read-only consistency guard between service catalog prices and Business Memory / FAQ text.
- Added admin-protected readiness endpoints:
  - `GET /service-memory/consistency/readiness`
  - `GET /catalog-memory/consistency/readiness`
  - `GET /price-consistency/readiness`
  - `GET /workspace/price-consistency/readiness`
- Added owner-safe read-only endpoints:
  - `GET /owner/price-consistency`
  - `GET /owner/price-consistency/ui`
  - `GET /owner/catalog-memory-consistency`
  - `GET /owner/catalog-memory-consistency/ui`
- Integrated price consistency metadata into owner Business Memory JSON/UI and owner service/memory update responses.
- Service Catalog remains the source of truth for prices. Business Memory remains contextual text for policies, FAQ, exceptions and explanations.
- Stage 84 does not auto-delete or rewrite owner memory; it surfaces conflicts, duplicates, stale managed blocks and unmatched manual price lines as attention metadata.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/service-memory/consistency/readiness?tenant_id=clinic_demo` returns `stage=84` and `service_catalog_memory_consistency_ready=true` when infrastructure is ready.
- `/catalog-memory/consistency/readiness?tenant_id=clinic_demo`, `/price-consistency/readiness?tenant_id=clinic_demo`, and `/workspace/price-consistency/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/price-consistency/ui?tenant_id=<owner_tenant>` opens with valid owner session or super-admin bypass.
- `/owner/business-memory?tenant_id=<owner_tenant>` includes `price_consistency`.
- `/owner/business-memory/ui?tenant_id=<owner_tenant>` shows price consistency status.
- Owner services, memory, workspace, dashboard and billing remain OK.
- Stage 78 remains the source of truth for `public_saas_ready`; `enterprise_saas_ready=false` remains explicit.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.

## Stage 84 — Service Catalog / Business Memory Consistency Guard Verification Update

Status: closed after deploy verification. User reported `/dialogue/qa` = 50/50 passed and all Stage 84 checks OK.

Verified:
- Service-memory consistency readiness works.
- Catalog-memory consistency readiness works.
- Price consistency readiness works.
- Owner price consistency UI works.
- Owner business memory, services, workspace, dashboard and billing remain OK.
- Service Catalog is treated as the source of truth for prices while Business Memory remains context.

## Stage 85 — Calendar Owner UX / Availability Setup Polish

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added owner-safe calendar/availability endpoints:
  - `GET /owner/calendar`
  - `GET /owner/calendar/ui`
  - `GET /owner/availability`
  - `GET /owner/availability/ui`
  - `POST /owner/availability/update`
- Added admin-protected readiness endpoints:
  - `GET /owner-calendar/readiness`
  - `GET /calendar-owner/readiness`
  - `GET /availability/readiness`
  - `GET /workspace/calendar/readiness`
- Added owner-visible calendar status without exposing Google access tokens, refresh tokens, service account credentials, or raw calendar secrets.
- Added owner-editable availability fields: `timezone`, `work_start`, `work_end`.
- Google OAuth connection and working calendar selection remain support-controlled in this SMB phase; owner sees status and next actions without receiving admin OAuth/config links.
- Integrated Stage 85 calendar/availability links into owner dashboard/workspace/setup flow.
- Stage 80 Google Calendar next-action now points to owner-safe `/owner/calendar/ui`.
- Added Stage 74 owner-scope CSRF/browser-write protection for `POST /owner/availability/update`.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/owner-calendar/readiness?tenant_id=clinic_demo` returns `stage=85` and `calendar_owner_ux_ready=true` when routes/security are ready.
- `/calendar-owner/readiness?tenant_id=clinic_demo`, `/availability/readiness?tenant_id=clinic_demo`, and `/workspace/calendar/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/calendar/ui?tenant_id=<owner_tenant>` and `/owner/availability/ui?tenant_id=<owner_tenant>` open with valid owner session or super-admin bypass.
- Saving availability returns `ok=true` and updates timezone/working hours only.
- `/tenant-workspace/readiness?tenant_id=clinic_demo` points the Google Calendar next-action to owner-safe `/owner/calendar/ui`.
- Owner dashboard/workspace/services/memory/billing remain owner-safe.
- Stage 78 remains the source of truth for `public_saas_ready`; `enterprise_saas_ready=false` remains explicit.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.

## Stage 85 — Calendar Owner UX / Availability Setup Polish Verification Update

Status: closed after deploy verification. User reported `/dialogue/qa` = 50/50 passed and all Stage 85 checks OK.

Verified:
- Owner calendar readiness works.
- Calendar owner readiness works.
- Availability readiness works.
- Workspace calendar readiness works.
- Owner calendar UI works.
- Owner availability UI/update works.
- Owner dashboard, workspace and billing remain OK.
- Stage 80 Google Calendar next-action points to owner-safe `/owner/calendar/ui`.

## Stage 86 — Telegram Owner UX / Channel Setup Polish

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added owner-safe Telegram channel endpoints:
  - `GET /owner/telegram`
  - `GET /owner/telegram/ui`
  - `GET /owner/channels/telegram`
  - `GET /owner/channels/telegram/ui`
- Added admin-protected readiness endpoints:
  - `GET /owner-telegram/readiness`
  - `GET /telegram-owner/readiness`
  - `GET /workspace/telegram/readiness`
  - `GET /channels/telegram/owner/readiness`
- Added owner-visible Telegram status without exposing raw bot token, raw webhook secret, masked token, admin setup links, or webhook setup write actions.
- Telegram setup remains support-controlled in this SMB phase; owner sees channel status, webhook metadata status, usage/smoke status and next actions.
- Integrated Stage 86 Telegram links into owner dashboard/workspace/setup flow.
- Stage 80 Telegram channel next-action now points to owner-safe `/owner/telegram/ui`.
- No owner write endpoint was added in Stage 86.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/owner-telegram/readiness?tenant_id=clinic_demo` returns `stage=86` and `telegram_owner_ux_ready=true` when routes/security are ready.
- `/telegram-owner/readiness?tenant_id=clinic_demo`, `/workspace/telegram/readiness?tenant_id=clinic_demo`, and `/channels/telegram/owner/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/telegram/ui?tenant_id=<owner_tenant>` and `/owner/channels/telegram/ui?tenant_id=<owner_tenant>` open with valid owner session or super-admin bypass.
- `/tenant-workspace/readiness?tenant_id=clinic_demo` points the Telegram next-action to owner-safe `/owner/telegram/ui`.
- Owner dashboard/workspace/services/memory/calendar/billing remain owner-safe.
- Stage 78 remains the source of truth for `public_saas_ready`; `enterprise_saas_ready=false` remains explicit.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.

## Stage 86 — Telegram Owner UX / Channel Setup Polish Verification Update

Status: closed after deploy verification. User reported `/dialogue/qa` = 50/50 passed and all Stage 86 checks OK.

Verified:
- Owner Telegram readiness works.
- Telegram owner readiness works.
- Workspace Telegram readiness works.
- Channels Telegram owner readiness works.
- Owner Telegram UI works.
- Owner Telegram/channel UI works.
- Owner workspace, dashboard and billing remain OK.
- Stage 80 Telegram channel next-action points to owner-safe `/owner/telegram/ui`.

## Stage 87 — Owner Workspace Final Setup Review / Launch Checklist Polish

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added owner-safe final setup review endpoints:
  - `GET /owner/launch-review`
  - `GET /owner/launch-review/ui`
  - `GET /owner/setup-review`
  - `GET /owner/setup-review/ui`
  - `GET /owner/launch-checklist`
  - `GET /owner/launch-checklist/ui`
- Added admin-protected readiness endpoints:
  - `GET /owner-workspace/final-review/readiness`
  - `GET /workspace/final-review/readiness`
  - `GET /owner-launch-checklist/readiness`
  - `GET /launch-checklist/owner/readiness`
- Added owner-safe final checklist aggregation across:
  - Stage 80 workspace setup
  - Stage 81 business profile
  - Stage 82 services
  - Stage 83 Business Memory / FAQ
  - Stage 84 price consistency
  - Stage 85 calendar/availability
  - Stage 86 Telegram
  - Stage 73 billing
  - Stage 78 public launch lock
  - Stage 71 owner auth
  - Stage 77 owner/admin separation
- Added owner launch review link into owner dashboard/workspace link payloads.
- No new owner write endpoint was added.
- Calendar and Telegram support-controlled states are shown as owner-visible attention items without exposing admin setup links or secrets.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/owner-workspace/final-review/readiness?tenant_id=clinic_demo` returns `stage=87` and `owner_workspace_final_review_ready=true` when route/security wiring is ready.
- `/workspace/final-review/readiness?tenant_id=clinic_demo`, `/owner-launch-checklist/readiness?tenant_id=clinic_demo`, and `/launch-checklist/owner/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/launch-review/ui?tenant_id=clinic_demo`, `/owner/setup-review/ui?tenant_id=clinic_demo`, and `/owner/launch-checklist/ui?tenant_id=clinic_demo` open with valid owner session or super-admin bypass.
- Owner dashboard/workspace links include owner-safe launch review link.
- Owner services, business memory, price consistency, calendar, Telegram and billing remain owner-safe.
- Stage 78 remains the source of truth for `public_saas_ready`; `enterprise_saas_ready=false` remains explicit.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.

## Stage 87.1 — Launch Review UI Bootstrap Hotfix

Status: implemented in archive, awaiting deploy verification.

Reason:
- After Stage 87 deploy, `/owner/launch-review/ui?tenant_id=clinic_demo` opened but the client-side UI did not initialize: tenant field stayed empty, Load did not fetch, and Workspace/Dashboard/Logout buttons did not respond.

Fix:
- Replaced only `stage87_owner_launch_review_html()` with a defensive browser bootstrap.
- Tenant is now read from URL query first, then backend default, then `clinic_demo` fallback.
- Tenant input is populated immediately on boot.
- Buttons now use explicit JS bindings by element id.
- UI no longer relies on fragile nested template-literal rendering for checklist cards.
- HTML escaping now uses regex replacement instead of `replaceAll()`.
- Fetch failures and non-OK JSON responses are shown in the Raw launch checklist block.

Expected verification:
- `/owner/launch-review/ui?tenant_id=clinic_demo` immediately shows `clinic_demo` in the tenant input.
- Load, Workspace, Dashboard, and Logout buttons respond.
- `/owner/launch-review?tenant_id=clinic_demo` still returns Stage 87 payload when owner session or super-admin bypass is valid.
- `/dialogue/qa` remains 50/50 passed.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.


## Stage 87.2 — Launch Review Readiness Fast Path Hotfix
- Built after Stage 87.1.
- Replaces deep Stage 87 final-review aggregation with fast owner-safe checklist path to prevent launch-review UI/readiness hanging.
- Does not change receptionist runtime, booking, Calendar runtime, Telegram runtime, billing semantics, CSRF, abuse limits, magic-link, QA evaluator, LLM or voice.

## Stage 88 — Owner Demo / Client Preview Mode Polish

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added owner-safe dry-run demo/client preview endpoints:
  - `GET /owner/demo`
  - `GET /owner/demo/ui`
  - `POST /owner/demo/preview`
  - `GET /owner/client-preview`
  - `GET /owner/client-preview/ui`
  - `POST /owner/client-preview/message`
- Added admin-protected readiness endpoints:
  - `GET /owner-demo/readiness`
  - `GET /client-preview/readiness`
  - `GET /workspace/demo/readiness`
  - `GET /demo/owner/readiness`
- Owner preview uses tenant service catalog, Business Memory / FAQ, working hours and safe deterministic reply logic.
- Service Catalog remains the source of truth for prices in preview answers.
- Preview mode explicitly reports `dry_run=true` and does not create calendar events, persist conversation state, send Telegram/SMS/WhatsApp messages, or trigger booking confirmation.
- Added owner demo/client preview links into owner dashboard/workspace/final-review link payloads.
- `POST /owner/demo/preview` and `POST /owner/client-preview/message` are owner-protected and covered by Stage 74 owner browser-write/CSRF hardening.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/owner-demo/readiness?tenant_id=clinic_demo` returns `stage=88`, `owner_demo_preview_ready=true`, `client_preview_mode_ready=true`, `dry_run_only=true`.
- `/client-preview/readiness?tenant_id=clinic_demo`, `/workspace/demo/readiness?tenant_id=clinic_demo`, and `/demo/owner/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/demo/ui?tenant_id=clinic_demo` opens with valid owner session or super-admin bypass.
- Sending a preview message returns a reply with `dry_run=true`, `calendar_event_created=false`, `conversation_persisted=false`, and `external_customer_message_sent=false`.
- Owner workspace/dashboard/launch-review links remain working and include owner demo/client preview links.
- Stage 78 remains the source of truth for `public_saas_ready`; `enterprise_saas_ready=false` remains explicit.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook/runtime, SMS/WhatsApp send paths, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.

## Stage 89 — Owner Analytics / Conversation Visibility Polish

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added owner-safe read-only analytics/conversation visibility endpoints:
  - `GET /owner/analytics`
  - `GET /owner/analytics/ui`
  - `GET /owner/conversation-insights`
  - `GET /owner/conversation-insights/ui`
- Added admin-protected readiness endpoints:
  - `GET /owner-analytics/readiness`
  - `GET /workspace/analytics/readiness`
  - `GET /conversation-visibility/readiness`
  - `GET /analytics/owner/readiness`
- Uses existing `call_logs` for live interaction visibility and optional `usage_events` summary metadata when available.
- Exposes live totals, unique hashed customer refs, channel/status breakdown, question categories, service interest, price questions, inferred answer source visibility, and recent redacted/truncated snippets.
- Clearly marks Stage 88 preview history as not persisted by design.
- Added owner analytics links into owner dashboard/workspace payloads.
- No new owner write endpoint was added.
- No new tables or runtime persistence writes were added.
- `enterprise_saas_ready=false` remains explicit.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/owner-analytics/readiness?tenant_id=clinic_demo` returns `stage=89` and remains admin-protected.
- `/workspace/analytics/readiness?tenant_id=clinic_demo`, `/conversation-visibility/readiness?tenant_id=clinic_demo`, and `/analytics/owner/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/analytics/ui?tenant_id=clinic_demo` and `/owner/conversation-insights/ui?tenant_id=clinic_demo` open with valid owner session or super-admin bypass.
- Owner workspace/dashboard links include conversation insights.
- Stage 88 preview remains dry-run only and still reports `conversation_persisted=false`.
- Stage 78 remains the source of truth for public SaaS readiness; `enterprise_saas_ready=false` remains explicit.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook/runtime, SMS/WhatsApp send paths, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.


## Stage 89 — Owner Analytics / Conversation Visibility Polish Verification Update

Status: closed after deploy verification. User reported `/dialogue/qa` = 50/50 passed and all Stage 89 checks OK.

Verified:
- Owner analytics readiness works.
- Workspace analytics readiness works.
- Conversation visibility readiness works.
- Analytics owner readiness works.
- Owner analytics / conversation insights UI works.
- Owner workspace, dashboard, launch review and preview remain OK.
- Stage 88 preview remains dry-run/no-persistence and analytics does not overclaim preview history.
- `enterprise_saas_ready=false` remains explicit.

## Stage 90 — Owner Notifications / Lead Follow-up Visibility

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added owner-safe read-only follow-up visibility endpoints:
  - `GET /owner/notifications`
  - `GET /owner/notifications/ui`
  - `GET /owner/follow-ups`
  - `GET /owner/follow-ups/ui`
  - `GET /owner/lead-followup`
  - `GET /owner/lead-followup/ui`
- Added admin-protected readiness endpoints:
  - `GET /owner-notifications/readiness`
  - `GET /workspace/notifications/readiness`
  - `GET /lead-follow-up/readiness`
  - `GET /notifications/owner/readiness`
- Stage 90 uses existing `call_logs` and, when available, `conversations` only.
- Follow-up candidates are inferred from existing status/intent/message metadata such as `need_more`, `busy`, `booking_failed`, `no_booking`, `recovery`, `reschedule_wait`, `cancel_failed`, unresolved booking-like intents and price/info questions.
- Owner UI shows priority, reason, channel visibility, active conversation state counts, redacted/truncated snippets and hashed customer refs.
- No automatic owner notification delivery was added.
- No Telegram/SMS/WhatsApp/customer message sends were added.
- No new notification table or runtime write was added.
- Dashboard/workspace owner link payloads include owner notifications/follow-up links.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/owner-notifications/readiness?tenant_id=clinic_demo` returns `stage=90` and `enterprise_saas_ready=false`.
- `/workspace/notifications/readiness?tenant_id=clinic_demo`, `/lead-follow-up/readiness?tenant_id=clinic_demo`, and `/notifications/owner/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/notifications/ui?tenant_id=clinic_demo`, `/owner/follow-ups/ui?tenant_id=clinic_demo`, and `/owner/lead-followup/ui?tenant_id=clinic_demo` open with valid owner session or super-admin bypass.
- Owner dashboard/workspace links include owner-safe notifications/follow-up links.
- Stage 89 analytics UI remains OK.
- Stage 88 preview still returns `conversation_persisted=false`.
- Stage 78 remains the source of truth for `public_saas_ready`; `enterprise_saas_ready=false` remains explicit.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook/runtime, SMS/WhatsApp send paths, billing semantics, auth/session semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.

## Stage 90.1 — Notification Links 500 Guard Hotfix

Status: implemented in archive, awaiting deploy verification.

Reason:
- After Stage 90 deploy, notification/follow-up related links returned Internal Server Error.
- The exact Render traceback was not available in chat at hotfix time.
- Local stubbed route smoke from the Stage 90 archive did not reproduce the 500, so this hotfix is a narrow server-side guard around Stage 90 endpoints rather than a broad rewrite.

Scope:
- Added Stage 90.1 safe guards for notification/follow-up readiness, JSON payload, and UI bootstrap paths.
- If optional Stage 90 data access fails, endpoints now return owner-safe empty/diagnostic payloads instead of unhandled 500 responses.
- Exception details exposed to owner/admin responses are limited to reason codes and exception class names only.
- Stage 90 remains read-only visibility only.

No runtime behavior changes:
- No notification sends.
- No external customer messages.
- No Telegram/SMS/WhatsApp/email sends.
- No notification queue/background job.
- No runtime writes.
- No booking/dialogue/Calendar/Telegram runtime changes.

Expected verification:
- `/dialogue/qa` = 50/50 passed.
- Notification/follow-up links no longer return Internal Server Error.
- Stage 90 readiness endpoints return JSON without 500.
- Stage 90 owner UI endpoints open with valid owner session or super-admin bypass.
- Stage 89 analytics, Stage 88 preview, owner workspace, owner dashboard and launch review remain OK.
- `enterprise_saas_ready=false` remains explicit.

## Stage 90.1 — Notification Links 500 Guard Hotfix Verification Update

Status: closed after deploy verification. User reported notification/follow-up links now work, `/dialogue/qa` = 50/50 passed, and all other checks OK.

Verified:
- Notification/follow-up links no longer return Internal Server Error.
- Stage 90 readiness endpoints and owner UI paths work.
- `/dialogue/qa` remains 50/50 passed.
- Stage 90 remains read-only visibility only; no notification sends or runtime writes were added.

## Stage 91 — Owner Account / Profile / Billing UX Polish

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added owner-safe read-only account/profile/billing center endpoints:
  - `GET /owner/account`
  - `GET /owner/account/ui`
  - `GET /owner/profile`
  - `GET /owner/profile/ui`
  - `GET /owner/account-billing`
  - `GET /owner/account-billing/ui`
- Added admin-protected readiness endpoints:
  - `GET /owner-account/readiness`
  - `GET /owner-profile/readiness`
  - `GET /workspace/account/readiness`
  - `GET /account-billing/readiness`
- Uses existing Stage 71 owner account/session/binding foundation, Stage 76 email verification metadata, Stage 81 business profile model, Stage 73 billing/subscription foundation, and Stage 80 workspace summary.
- Adds owner account/profile/billing links to owner dashboard/workspace payloads and adds an Account Center link to the existing owner billing UI.
- Owner account center is read-only. No owner account/profile write endpoint was added.
- No billing update route, payment provider checkout/customer portal, queue/background job, or external send was added.
- Owner email is shown only to the authenticated owner session. Super-admin owner-safe bypass does not expose owner email in the Stage 91 payload.
- `enterprise_saas_ready=false` remains explicit.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/owner-account/readiness?tenant_id=clinic_demo` returns `stage=91` and remains admin-protected.
- `/owner-profile/readiness?tenant_id=clinic_demo`, `/workspace/account/readiness?tenant_id=clinic_demo`, and `/account-billing/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/account/ui?tenant_id=clinic_demo`, `/owner/profile/ui?tenant_id=clinic_demo`, and `/owner/account-billing/ui?tenant_id=clinic_demo` open with valid owner session or super-admin bypass.
- Owner dashboard/workspace links include the account/profile/billing center.
- Existing `/owner/billing/ui?tenant_id=clinic_demo` still works and now links to Account Center.
- Stage 90 notification/follow-up links remain OK.
- Stage 89 analytics UI remains OK.
- Stage 88 preview still returns `conversation_persisted=false`.
- Stage 78 remains the source of truth for `public_saas_ready`; `enterprise_saas_ready=false` remains explicit.

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancel/reschedule, Google Calendar event runtime, Telegram webhook/runtime, SMS/WhatsApp send paths, billing semantics, auth/session semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.


## Stage 91.1 — Owner Account Logout / Auth Guard Hotfix

Status: implemented in archive, awaiting deploy verification.

Reason:
- After Stage 91 deploy, the owner account/profile/billing links appeared to remain accessible after logout in the same browser.
- External no-cookie check returned 401, so the account UI was not fully public without cookies.
- Code audit found two concrete issues for the browser-session case:
  - Stage 91 account/profile/billing routes still allowed Stage 62 super-admin support bypass.
  - `/admin/logout` cleared only admin cookies and `/owner/logout` cleared only owner cookies, so a browser with both sessions could still open owner pages after logging out of only one session.

Scope:
- Stage 91 account/profile/billing JSON and UI now require strict Stage 71 owner session + tenant binding.
- Stage 62 super-admin bypass is disabled for Stage 91 account/profile/billing center routes.
- `/admin/logout` clears both admin and owner session cookies.
- `/owner/logout` clears both owner and admin session cookies.
- Stage 91 readiness routes remain admin-protected.

Expected verification:
- After deploy, visit `/admin/logout` or `/owner/logout` once to clear existing browser cookies.
- Then `/owner/account/ui?tenant_id=clinic_demo`, `/owner/profile/ui?tenant_id=clinic_demo`, and `/owner/account-billing/ui?tenant_id=clinic_demo` should require owner login.
- With a valid owner session, the same pages should open normally.
- `/dialogue/qa` remains 50/50 passed.
- Existing Stage 90/90.1, Stage 89, Stage 88 and owner workspace/dashboard/launch-review checks remain OK.

## Stage 93 — Public Signup → Owner Workspace End-to-End Polish

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added strict owner-only post-signup handoff endpoints:
  - `GET /owner/get-started`
  - `GET /owner/get-started/ui`
  - `GET /owner/welcome`
  - `GET /owner/welcome/ui`
- Added admin-protected E2E readiness endpoints:
  - `GET /public-signup-workspace/readiness`
  - `GET /signup-owner-workspace/readiness`
  - `GET /owner-workspace/e2e/readiness`
  - `GET /smb/onboarding/e2e/readiness`
- Public signup success now returns `owner_get_started` as the primary handoff link while retaining owner workspace/dashboard/setup-health/launch-review/account/billing links.
- Public signup still creates the tenant, owner account, tenant binding and owner session through the existing Stage 72/71 flow.
- The signup UI now sends the authenticated owner to the owner-only get-started page instead of the generic dashboard.
- Owner dashboard/workspace link payloads include the get-started handoff.

Security / boundaries:
- Get-started/welcome routes require strict Stage 71 owner session + tenant binding.
- Stage 62 admin session / Stage 61 token bypass is not accepted for the Stage 93 owner handoff.
- Stage 93 readiness routes remain Stage 61/62 admin-protected.
- No owner POST route or new Stage 74 CSRF path was added.
- Owner handoff payload removes admin readiness dependencies/links and does not expose owner email, raw login codes, magic tokens, hashes, admin tokens, Google credentials, Telegram secrets or billing secrets.
- `tenant_id` remains context, not authentication.
- `enterprise_saas_ready=false` remains explicit.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` remains 50/50 passed.
- Stage 93 readiness endpoints return `stage=93` and remain admin-protected.
- `/public/signup` remains public.
- After a successful test signup, the response sets the owner session and `Continue setup` opens `/owner/get-started/ui?tenant_id=<new_tenant>`.
- Get-started/welcome routes do not open without owner login or with admin login only.
- With the valid owner session, get-started/welcome, workspace, setup-health and launch-review pages open without 500.
- Existing Stage 92/91.1/90.1/89/88 owner surfaces remain OK.
- Stage 78 remains the source of truth for platform `public_saas_ready`; `enterprise_saas_ready=false` remains explicit.



## Stage 93 — Public Signup → Owner Workspace End-to-End Polish Verification Update

Status: closed after deploy verification. User reported `/dialogue/qa` = 50/50 passed and all other Stage 93 checks OK.

Verified:
- Public signup → owner workspace/get-started handoff works.
- Stage 93 owner/admin auth boundaries work.
- Existing owner surfaces remain OK.
- `enterprise_saas_ready=false` remains explicit.

## Stage 94 — SMB Launch Smoke / Demo Tenant Hardening

Status: implemented in archive, awaiting deploy verification.

Scope:
- Added strict owner-only launch-smoke/demo-tenant JSON and UI routes.
- Added admin-protected Stage 94 readiness aliases.
- Aggregates Stage 93 signup E2E, Stage 92 required setup health, Stage 87.2 launch checklist, Stage 88 dry-run preview safety, and Stage 78 public SaaS lock.
- Adds a read-only manual smoke checklist and owner dashboard/get-started discoverability.
- Does not run dialogue QA/live dialogue, mutate Calendar/conversations, send external messages, create tenants, or change receptionist runtime.
- `enterprise_saas_ready=false` remains explicit.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` remains 50/50 passed.
- Stage 94 readiness returns `stage=94`.
- Stage 94 owner UI requires a valid owner session and does not accept admin-only login.
- Existing Stage 93/92/91.1/90.1/89/88/87 owner surfaces remain OK.


## Stage 94 — SMB Launch Smoke / Demo Tenant Hardening Verification Update

Status: closed after deploy verification. User reported `/dialogue/qa` = 50/50 passed and all other Stage 94 checks OK.

Verified:
- Stage 94 launch-smoke/demo-tenant readiness works.
- Stage 94 strict owner/admin boundaries work.
- Stage 88 preview safety remains intact.
- Existing Stage 93/92/91.1/90.1/89/88/87 owner surfaces remain OK.
- `enterprise_saas_ready=false` remains explicit.

## Stage 95 — Mature SMB SaaS Readiness Lock

Status: implemented in archive, awaiting deploy verification.

Scope:
- Adds a final read-only technical-core lock for the current Mature SMB SaaS phase.
- Aggregates Stage 94 launch smoke, Stage 93 signup handoff, Stage 92 setup health, Stage 91 account/profile/billing visibility, Stage 90 notifications/follow-up visibility, Stage 89 analytics visibility, Stage 88 preview safety, and Stage 78 controlled public SaaS lock.
- Adds strict owner-only readiness-lock UI/JSON and admin-protected final readiness aliases.
- Adds discoverability links from owner dashboard, workspace, get-started and launch-smoke payloads.
- Does not execute `/dialogue/qa`, live dialogue, Calendar mutations, conversation persistence, billing mutations or external sends.

Truthful readiness boundary:
- Stage 95 may declare `mature_smb_core_ready=true` and `technical_product_baseline_locked=true` when all technical gates pass.
- It explicitly keeps `polished_client_launch_ready=false`, `client_experience_polish_complete=false`, and `enterprise_saas_ready=false`.
- Client-facing LV/RU/ENG navigation, shared visual design system and professional public website are a separate required post-lock phase.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` remains 50/50 passed.
- Stage 95 readiness endpoints return `stage=95` through admin login.
- Stage 95 owner pages require a valid owner session and do not accept admin-only login.
- `mature_smb_core_ready=true` when the existing verified tenant gates remain healthy.
- `polished_client_launch_ready=false` and `post_lock_client_experience_phase_required=true` remain explicit.
- Existing Stage 94/93/92/91.1/90.1/89/88 owner surfaces remain OK.


## Stage 95.1 — Analytics / Follow-up Data Source Compatibility Hotfix

Status: implemented in archive, awaiting deploy verification.

Production evidence after Stage 95 deploy showed two code-level blockers:
- Stage 90/90.1 guarded `NameError` because Stage 89 message categorization referenced undefined `STAGE88_PRICE_MARKERS`, `STAGE88_DURATION_MARKERS`, and `STAGE88_HOURS_MARKERS` constants instead of the existing Stage 88 marker helper functions.
- Stage 89 queried `usage_events.event_name`, while the existing usage-events schema and write path use `usage_type`, causing PostgreSQL `UndefinedColumn` / SQLAlchemy `ProgrammingError`.

Hotfix scope:
- Replace the three undefined Stage 88 marker constant references with calls to the existing marker helper functions.
- Replace the Stage 89 distinct usage-event query column `event_name` with the existing `usage_type` column.
- Do not change production database schema or require DBeaver ALTER statements.
- Do not change booking, dialogue, Calendar, Telegram, billing, auth, CSRF, abuse protection, magic links, QA evaluator, LLM orchestration, or external-send runtime.

Expected verification:
- `/owner-analytics/readiness?tenant_id=clinic_demo&days=14` no longer contains `stage89:call_logs_query_failed:ProgrammingError`.
- `/owner-notifications/readiness?tenant_id=clinic_demo&days=14` no longer returns Stage 90.1 `stage90_exception_guarded` / `stage90_readiness_exception:NameError`.
- `/mature-smb/final-readiness?tenant_id=clinic_demo` no longer blocks on Stage 89/90 and may set `mature_smb_core_ready=true` when all other gates remain healthy.
- `/dialogue/qa` remains 50/50 passed.

## Stage 95 / 95.1 Verification Closure

Status: closed after deploy verification.

Verified by user:
- `/dialogue/qa` = 50/50 passed.
- Stage 89 analytics visibility works.
- Stage 90 notifications/follow-up visibility works.
- Stage 95 Mature SMB technical readiness lock works.
- Mature SMB technical product baseline is locked.

## CX-1 — Shared UI Shell / Localization Foundation

Status: implemented in archive, awaiting deploy verification.

Scope:
- Adds `repliq/ui_foundation.py` as the reusable client-facing shell/design/localization foundation.
- Adds separate persistent LV/RU/EN UI language selection via `repliq_ui_lang`; tenant business language is not changed.
- Adds shared CSS/JS assets and admin-protected CX-1 readiness aliases.
- Migrates owner login, dashboard/control-center, get-started/welcome and workspace/setup UI families.
- Collapses technical payloads by default while preserving them for diagnostics.
- Preserves all existing API, auth, tenant, booking, Calendar, Telegram, billing and dialogue runtime semantics.

Next phase after verification:
- CX-2 — Owner Workspace Full Migration.

## CX-1 — Shared UI Shell / Localization Foundation Verification Update

Status: closed after deploy verification.

Verified by user:
- `/dialogue/qa` = 50/50 passed.
- Shared owner shell and responsive navigation work.
- Separate LV/RU/EN UI language selection and `repliq_ui_lang` persistence work.
- Owner login, dashboard, get-started and workspace pilot pages work.
- Existing auth boundaries and tenant business language remain unchanged.

## CX-2 — Owner Workspace Full Migration

Status: implemented in archive, awaiting deploy verification.

Scope:
- Migrates all remaining client-owner workspace UI families to the shared CX shell.
- Adds a shared desktop sidebar and grouped mobile navigation across overview, setup, operations, launch and account sections.
- Adds centralized LV/RU/EN UI-copy translation for the remaining owner pages while keeping tenant/business language separate.
- Preserves existing JSON APIs, owner write endpoints, CSRF behavior, auth boundaries and tenant binding.
- Preserves the existing logic of business profile, services, Business Memory/FAQ, price consistency, Calendar, Telegram, launch review, client preview, analytics, follow-ups, account, setup health, launch smoke, readiness lock and billing pages.
- Collapses raw technical payload sections by default through the shared client UI adapter.
- Does not change booking/dialogue runtime, Calendar event runtime, Telegram runtime, billing semantics, external sends or database schema.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` remains 50/50 passed.
- CX-1 readiness remains `ready`.
- CX-2 readiness returns `stage=CX-2`, `cx2_ready=true` and `owner_workspace_full_migration_ready=true` through admin login.
- Every migrated owner page opens in LV/RU/EN with the same persistent UI language.
- Existing owner/admin and strict-owner-only boundaries remain unchanged.
- Existing page actions continue to call the same APIs and write routes.
- `client_experience_polish_complete=false` and `enterprise_saas_ready=false` remain explicit.

Next phase after verification:
- CX-3 — Public Website / Signup / Authentication.

## CX-2 — Owner Workspace Full Migration Verification Update

Status: closed after deploy verification.

Verified by user:
- `/dialogue/qa` = 50/50 passed.
- All remaining owner workspace sections render through the shared responsive shell.
- LV/RU/EN UI language selection and persistence work across owner pages.
- Shared sidebar/mobile navigation works.
- Existing owner/admin boundaries and page actions remain intact.

## CX-3 — Public Website / Signup / Authentication

Status: implemented in archive, awaiting deploy verification.

Scope:
- Adds a professional responsive public Repliq website at `/` and the existing launch aliases.
- Adds one shared public header/footer, mobile navigation, favicon and LV/RU/EN localization source of truth.
- Replaces the technical public signup page with a client-facing localized form while preserving the existing POST `/public/signup` implementation.
- Migrates owner login, magic-token login and logout confirmation to the same public visual system while preserving existing auth/session behavior.
- Adds localized Privacy, Terms, Contact and Support pages.
- Adds admin-protected CX-3 readiness aliases.
- Keeps UI language separate from tenant/business language through the existing `repliq_ui_lang` cookie.

Truthful public boundary:
- No automated checkout or live payment-provider claim is added.
- Contact/support email is optional through `REPLIQ_PUBLIC_CONTACT_EMAIL` / `REPLIQ_PUBLIC_SUPPORT_EMAIL`; when absent, the public page honestly states that pilot contact is provided during onboarding.
- Privacy and Terms pages are product-phase notices and explicitly require legal-entity-specific review before broad commercial launch.
- No GDPR compliance, enterprise maturity or legal-finality claim is made.

Runtime preservation:
- Existing POST implementations for public signup, owner login, magic login and logout are unchanged.
- Existing rate limits, honeypot, CSRF boundary, abuse protection, magic-token semantics, owner-session cookies and tenant creation behavior remain unchanged.
- Booking, dialogue, Calendar, Telegram, billing, analytics, follow-up and database schema behavior are unchanged.

Expected verification:
- Render deploy starts successfully.
- `/dialogue/qa` remains 50/50 passed.
- CX-1 and CX-2 readiness remain `ready`.
- CX-3 readiness returns `stage=CX-3`, `cx3_ready=true`, `public_website_ready=true` and empty `blocking` through admin login.
- `/`, `/public/signup`, `/owner/login`, `/owner/magic-login`, `/privacy`, `/terms`, `/contact` and `/support` render in LV/RU/EN.
- Public language choice persists between public pages and the owner workspace.
- Signup and owner login continue to create/use the same existing owner session.

Next phase after verification:
- CX-4 — Responsive / Accessibility / Brand Polish.

## CX-3.1 — Public Language Switcher / Mobile Menu Hotfix

Status: implemented in archive; awaiting deploy verification.

Production issue reported after CX-3 deploy:
- Public LV/RU/EN controls rendered, but choosing RU/EN did not navigate to a newly rendered language.
- At smartphone width, the public menu did not remain open after activation.

Exact design weakness corrected:
- Both controls depended on the external `/assets/repliq-public.js` asset for their essential behavior.
- CX-3.1 makes language switching normal server-resolved links that preserve the current path and query parameters.
- CX-3.1 replaces the JavaScript-toggled mobile menu with native HTML `details/summary` behavior.
- Public asset version is bumped from `cx3.0` to `cx3.1` to invalidate the old cached JS/CSS URL.

Runtime preservation:
- Existing signup, owner login, magic login and logout POST handlers remain unchanged.
- Magic-login token, tenant and next parameters are preserved when switching UI language.
- No database, booking, Calendar, Telegram, billing, analytics or dialogue runtime behavior changes.

Expected verification:
- `/dialogue/qa` remains 50/50 passed.
- CX-1 and CX-2 readiness remain ready.
- CX-3 readiness reports `stage=CX-3.1` and `cx3_ready=true`.
- Language switching works on all public pages even when public JavaScript is disabled.
- The mobile menu stays open until the user selects a link or closes the native disclosure.

## CX-3.2 — Public UI Language Persistence / Navigation Hotfix

Status: implemented in archive; awaiting deploy verification.

Production issue reported after CX-3.1:
- The selected RU/EN interface language could intermittently return to LV when navigating through public menu items.

Exact cause:
- CX-3.1 rendered server-side language links but did not persist the resolved language in `repliq_ui_lang` on the response.
- Product/How/Security links opened `/` without `ui_lang`, so the resolver used browser `Accept-Language` and selected LV on Latvian devices.

Correction:
- Every public HTML response now persists the resolved UI language in a first-party cookie.
- All public Product/How/Security menu links explicitly carry the current language.
- Public assets are versioned as `cx3.2`.

Runtime preservation:
- Signup, owner login, magic login and logout POST implementations remain unchanged.
- No database, booking, Calendar, Telegram, billing, analytics, follow-up, dialogue or QA runtime behavior changes.

Expected verification:
- RU/EN remains selected across every public menu transition and page reload.
- CX-3 readiness reports `stage=CX-3.2` and `cx3_ready=true`.
- `/dialogue/qa` remains 50/50 passed.


## CX-3.2 Verification Update

Status: deployed, verified and closed.

Verified by user:
- `/dialogue/qa` = 50/50 passed.
- Public LV/RU/EN switching works.
- Public mobile navigation works.
- RU/EN no longer fall back to LV during public navigation.
- Signup/auth/runtime baseline remains intact.

## CX-4 — Responsive / Accessibility / Brand Polish

Status: deployed, verified and closed after CX-4.1.

Scope:
- Replaces the generic rounded-square `R` with a custom reply-loop R/Q/message monogram while retaining the established violet identity.
- Adds an outlined lowercase `repliq` wordmark with an accented final `q`; no runtime font download is required for the wordmark.
- Uses the same brand lockup in public and owner shells.
- Adds shared SVG mark/lockup assets and an updated favicon.
- Adds skip links, focus-visible states, semantic active navigation, reduced-motion and forced-colors support.
- Refines public and owner layouts at desktop, tablet and mobile widths.
- Converts owner mobile navigation to native `details/summary`.
- Carries owner `ui_lang` through navigation and persists the non-sensitive UI language cookie.

Runtime preservation:
- Existing signup/login/magic-login/logout POST handler source remains unchanged.
- No POST routes, schema migrations, business writes or external sends are added.
- Booking, Calendar, Telegram, billing, analytics, QA and LLM runtime are unchanged.

Expected verification:
- `/dialogue/qa` remains 50/50 passed.
- CX-1, CX-2 and CX-3 readiness remain `ready`.
- CX-4 readiness reports `stage=CX-4`, `cx4_ready=true`, `blocking=[]`.
- Public and owner pages have no horizontal overflow at 375/390/768/desktop widths.
- Keyboard focus and skip links work.
- Public and owner mobile menus remain usable.
- LV/RU/EN persists across public and owner navigation.

Next phase after verification:
- CX-5 — Client Experience Readiness Lock.

## CX-4.1 — Public Header Section Active State Hotfix

Status: deployed, verified and closed.

Fixes fragment-aware active underline state for Product, How it works and Security across LV/RU/EN. User confirmed `/dialogue/qa = 50/50 passed` and all remaining checks normal.


## CX-5 — Client Experience Readiness Lock

Status: implemented in archive; awaiting deploy verification.

Scope:
- Adds admin-protected GET aliases `/client-experience/final-readiness`, `/client-experience/readiness-lock` and `/polished-client-launch/readiness`.
- Aggregates CX-1 through CX-4.1 readiness into one final client-experience lock.
- Validates public route openness, owner-session protection, no owner/admin overlap, LV/RU/EN scope and preserved GET/POST contracts for signup/login/magic-login/logout.
- Reports `client_experience_polish_complete=true` and `polished_client_launch_ready=true` only when all gates are healthy.
- Keeps `enterprise_saas_ready=false`.

Runtime preservation:
- Adds no POST route, database write, external send, schema migration or background job.
- Booking, dialogue, Calendar, Telegram, billing, analytics, QA, LLM and auth implementations remain unchanged.
- `/dialogue/qa` remains a manual operator regression and is expected to remain 50/50 passed.

Next planned product phase after verification:
- Repliq Pulse architecture and integration planning.
