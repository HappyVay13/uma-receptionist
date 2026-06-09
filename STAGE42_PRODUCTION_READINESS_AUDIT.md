# Stage 42 — Regression Baseline Lock 30/30 & Production Readiness Audit

## Purpose
Stage 42 is a documentation and audit checkpoint after Stage 41.1 production confirmation.

Confirmed production baseline from user:

```text
/dialogue/qa = 30/30 passed
```

Stage 42 intentionally does not change conversational behavior, routing, calendar logic, or regression evaluator rules.

## Files audited

Main runtime file:

```text
repliq/legacy_app.py — 12,365 lines
```

Python project shape observed:

```text
84 Python files
legacy_app.py contains 375 top-level functions and 5 top-level classes
```

Important modules present:

```text
channels/sms.py
channels/whatsapp.py
channels/telegram.py
channels/voice.py
config/settings.py
core/language.py
core/parsing_time.py
db/conversations.py
db/runtime_tables.py
integrations/google_calendar.py
integrations/twilio_validation.py
services/conversation_engine.py
services/dialog_state.py
services/intent_parser.py
services/tenant_service.py
saas/lifecycle.py
```

## Regression baseline

Current matrix size:

```text
30 scenarios
```

Coverage by stage:

```text
Stage 24: 2
Stage 30: 2
Stage 31: 2
Stage 32: 2
Stage 33: 2
Stage 37: 2
Stage 38: 3
Stage 40: 13
Stage 41: 2
```

Coverage by category:

```text
after_time_window: 2
fuzzy_time_window: 2
contextual_refinement: 4
soft_ux_confirmation: 2
parser_regression: 1
slot_choice_regression: 1
temporal_semantic_recovery: 4
business_memory_side_question: 8
business_memory_hours: 2
business_memory_location: 2
business_memory_services: 2
```

Protected scenario IDs:

```text
stage30_ru_after_1400_window
stage30_lv_after_1400_window
stage31_ru_evening_fuzzy
stage31_lv_evening_fuzzy
stage32_ru_not_so_late_refinement
stage32_lv_slightly_earlier_refinement
stage33_ru_soft_confirm
stage33_lv_soft_confirm
parser_date_time_protection
offered_slot_choice_protection
stage37_lv_parit_recovery
stage37_lv_aizparit_recovery
stage38_lv_price_side_question
stage38_ru_hours_question
stage38_lv_location_question
stage40_ru_location_side_question
stage40_lv_location_side_question
stage40_lv_price_then_slot_number
stage40_lv_later_refinement
stage40_ru_later_refinement
stage40_lv_other_day_after_slots
stage40_ru_other_day_after_slots
stage40_ru_standalone_location
stage40_lv_standalone_hours
stage40_lv_location_then_slot_number
stage40_ru_location_then_slot_number
stage40_lv_services_standalone
stage40_ru_services_standalone
stage41_ru_price_side_question
stage41_lv_hours_side_question
```

## Current execution architecture

### 1. Core runtime is still legacy_app.py

`services/conversation_engine.py` is a thin facade around the existing legacy handler. The real booking state machine, regression runner, channel endpoints, tenant dashboard endpoints, Google endpoints, and most orchestration remain in `repliq/legacy_app.py`.

This means Repliq is production-functional but still monolith-heavy.

### 2. LLM/orchestration separation exists

The code contains explicit orchestration actions:

```text
continue_legacy
faq
greet
identity
hours
start_booking
cancel
reschedule
ask_date
clarify_time
clarify_confirm
choose_slot
confirm_yes
confirm_no
```

The orchestration tool registry also separates calendar tools from FAQ tools:

```text
check_availability
create_booking
cancel_booking
reschedule_booking
get_business_info
```

This matches the project rule that LLM should be an understanding layer, not the action executor.

### 3. Stage 38–41 side-question logic is now protected

Important factual mechanisms:

- `try_barbershop_faq()` handles FAQ/business-memory answers.
- `faq_with_flow_followup()` preserves active booking flow after FAQ answers.
- `stage33_soft_conversational_ux()` has a guard so it does not overwrite `flow_preserved` / `stage38_business_faq` answers.
- Stage 41.1 adds cross-language business-memory lookup for price extraction.

The current 30-scenario matrix protects these intersections.

## Existing production readiness pieces

### Tenant readiness and SaaS lifecycle

Present in code:

```text
REQUIRED_TENANT_FIELDS
SAAS_TENANT_FIELDS
normalize_subscription_status()
effective_subscription_status()
tenant_runtime_missing_items()
tenant_runtime_ready()
validate_tenant_config()
tenant_config_update()
/tenant/config
/tenant/config/update
/tenant/status
/tenant/overview
/tenants
/tenants/ui
/plans
/tenant/change_plan
```

This means the project already has SaaS foundation elements, but they are not yet backed by a dedicated regression matrix.

### Google Calendar / OAuth

Present in code:

```text
/google/connect
/google/callback
/google/calendars
/google/calendars/ui
/google/select_calendar
```

Also present:

```text
create_calendar_event()
update_calendar_event()
delete_calendar_event()
find_next_event_by_phone()
```

Booking, cancellation, and rescheduling are calendar-backed, but QA currently uses calendar safe mode and does not validate real Google Calendar side effects.

### Security / reliability pieces

Present in code:

```text
Sentry optional initialization via SENTRY_DSN
Twilio signature middleware
health endpoint
tenant runtime validation helpers
usage/call logs tables
phone route table
conversation persistence
```

Important factual note:

`VOICE_SDK_ORIGINS` defaults to `*`, and CORS is added with broad methods/headers. This is acceptable for local/dev flexibility, but it is a production hardening item before customer-facing SaaS scale.

## Cancellation / rescheduling analysis

### What already exists

Cancellation and rescheduling are not absent. They already exist in the runtime:

```text
ORCH_ACTION_CANCEL
ORCH_ACTION_RESCHEDULE
cancel_booking tool registry entry
reschedule_booking tool registry entry
explicit cancel/reschedule intent markers
find_next_event_by_phone()
delete_calendar_event()
update_calendar_event()
reschedule_event_id pending state
abort_reschedule_text()
```

Current cancellation flow:

1. Detect explicit cancel intent.
2. Find next event by phone / tenant.
3. Delete Google Calendar event.
4. Clear pending state.
5. Set conversation state to `CANCELLED`.

Current rescheduling flow:

1. Detect explicit reschedule intent.
2. Find next event by phone / tenant.
3. Store `reschedule_event_id`, old datetime, summary, description in pending.
4. Move state to `AWAITING_DATE`.
5. New date/time selection eventually calls `book_appointment_for_datetime()`.
6. If `reschedule_event_id` exists, it patches the existing calendar event instead of creating a new one.

### What is not protected yet

There are no cancellation/rescheduling scenarios in the current 30-scenario `/dialogue/qa` matrix.

So cancellation/rescheduling is code-present, but not regression-protected.

Known unprotected areas:

```text
cancel existing booking
cancel with no active booking
reschedule existing booking
reschedule with no active booking
reschedule same time
abort reschedule / keep current booking
reschedule date-only follow-up
reschedule fuzzy time follow-up
side-question during reschedule
language preservation during cancel/reschedule
```

### Why Stage 43B should not be a blind feature build

Because cancellation/rescheduling already exists. The next step is not “build from zero”. The next step should be:

1. add safe-mode regression coverage;
2. expose what currently fails;
3. only then patch root causes.

## Stage 43 options — factual analysis

### Stage 43A — Production Hardening

#### What is already present

```text
Twilio signature validation
Sentry optional setup
health endpoint
tenant readiness helpers
tenant config UI/update endpoints
usage analytics endpoints
call logs
phone routes
Google OAuth foundation
calendar safe mode for QA
```

#### Main gaps visible from archive

```text
No dedicated production readiness test suite.
No regression checks for tenant readiness/config update behavior.
No regression checks for Twilio signature middleware behavior.
No regression checks for Google OAuth/calendar connection edge cases.
CORS is broad by default.
Calendar safe mode protects tests but does not verify real Google side effects.
legacy_app.py is still the core runtime monolith.
```

#### Recommended Stage 43A scope

Safe and useful scope:

```text
- add /health/details or internal readiness payload;
- add deterministic tenant-readiness audit endpoint or function;
- add regression/QA checks for tenant config readiness without changing booking behavior;
- document required production env vars;
- add structured production hardening checklist;
- do not refactor conversational routing yet.
```

Risk level: low to medium.

### Stage 43B — Cancellation / Rescheduling

#### What is already present

```text
cancel intent detection exists;
reschedule intent detection exists;
calendar event lookup exists;
calendar delete exists;
calendar patch/update exists;
reschedule pending state exists;
reschedule abort text exists;
reschedule finalization path exists in book_appointment_for_datetime().
```

#### Main gaps visible from archive

```text
No /dialogue/qa regression scenarios for cancellation.
No /dialogue/qa regression scenarios for rescheduling.
Safe-mode find_next_event_by_phone() currently returns None, so cancellation/rescheduling QA cannot pass without a controlled safe-mode event stub.
No protected scenarios around “нет, не переносить” / “lai paliek”.
No protected scenarios around side-questions during reschedule.
No protected scenarios around no-active-booking cancellation/reschedule.
```

#### Recommended Stage 43B scope

Do not start by changing user-facing behavior. First create a safe regression harness for existing cancel/reschedule code.

Best Stage 43B plan:

```text
Stage 43B.1 — Cancellation/Reschedule Regression Harness
- add calendar-safe-mode fake existing event support for QA only;
- add 4–6 scenarios that document current behavior;
- do not change production calendar behavior.

Stage 43B.2 — Cancellation UX Hardening
- fix only failures revealed by B.1;
- protect cancel existing booking, no booking, language preservation.

Stage 43B.3 — Reschedule UX Hardening
- fix only failures revealed by B.1;
- protect reschedule existing booking, same-time rejection, abort reschedule, final update path.
```

Risk level: medium to high if behavior is changed before tests; medium if test harness comes first.

### Stage 43C — SaaS Tenant Foundation

#### What is already present

```text
tenants table support;
phone_routes table support;
tenant config endpoints;
tenants UI;
dashboard UI;
onboarding UI;
Google OAuth calendar selection;
plan catalog;
subscription/lifecycle helpers;
usage analytics endpoints.
```

#### Main gaps visible from archive

```text
SaaS pieces exist but are not protected by regression scenarios.
There is no clear admin authentication layer visible for tenant/admin endpoints.
Tenant config update accepts many fields, but there is no dedicated validation test pack.
Plan prices are currently zero in PLAN_CATALOG.
Tenant dashboard is present, but this is not yet a hardened client-facing SaaS surface.
```

#### Recommended Stage 43C scope

Stage 43C should not come before hardening unless the goal is demo UI only.

Better order:

```text
1. Stage 43A production hardening
2. Stage 43B cancellation/reschedule harness + fixes
3. Stage 43C SaaS tenant foundation hardening
```

Risk level: medium if limited to docs/readiness checks; high if exposed as customer-facing SaaS without admin/auth hardening.

## Recommended next step

Recommended next stage:

```text
Stage 43A — Production Hardening & Readiness Checks
```

Why:

```text
- The conversational baseline is now healthy: 30/30.
- Cancellation/rescheduling already exists but is unprotected.
- SaaS tenant foundation exists but should not be exposed further without hardening.
- Production hardening can add safety without touching conversation behavior.
```

Then:

```text
Stage 44 — Cancellation/Reschedule Regression Harness
Stage 45 — Cancellation/Reschedule Behavior Fixes, only if Stage 44 reveals failures
Stage 46 — SaaS Tenant Foundation Hardening
```

## Stage 42 result

Stage 42 is documentation-only.

Code behavior changed:

```text
No
```

Files intentionally allowed to change:

```text
PROJECT_STATE.md
REPLIQ_RULES.md
STAGE42_PRODUCTION_READINESS_AUDIT.md
```

Required verification after deploy:

```text
/dialogue/qa = 30/30 passed
```
