# Stage 81.1 — Business Profile Language Persistence Hotfix

## Purpose
Fix Stage 81 owner business-profile UX when the UI shows `lv` but Stage 80/81 readiness still reports `missing=language`.

## Root cause
Stage 81 UI defaulted the `<select>` to `lv` when the tenant profile returned an empty language.
On older database revisions, the `tenants` table could be missing the dedicated `language` column.
The Stage 81 update path only persisted fields that exist in the table schema, so `language` could be accepted by the UI flow but not actually stored.

## Fix
`ensure_tenants_lifecycle_columns()` now ensures the tenant profile language column exists:

- `ALTER TABLE tenants ADD COLUMN IF NOT EXISTS language TEXT`
- backfills empty/null language values to `lv`
- sets database default for future tenants to `lv`

This aligns database persistence with the existing receptionist fallback behavior, where missing language already effectively falls back to Latvian.

## Changed files
- `repliq/legacy_app.py`
- `PROJECT_STATE.md`
- `REPLIQ_RULES.md`
- `STAGE81_1_BUSINESS_PROFILE_LANGUAGE_PERSISTENCE_HOTFIX.md`

## Not changed
- booking routing
- slots
- date/time parsing
- price side-question logic
- confirmation
- cancel/reschedule
- Google Calendar runtime
- Telegram runtime
- billing semantics
- CSRF semantics
- abuse/rate-limit semantics
- magic-link semantics
- dialogue QA evaluator
- LLM orchestration
- voice/calls

## Expected deploy checks
- `/health` OK
- `/dialogue/qa` remains `50/50 passed`
- `/owner/business-profile/ui?tenant_id=clinic_demo` saves language
- `/business-profile/readiness?tenant_id=clinic_demo` no longer reports `missing=["language"]` after migration/update
- `/tenant-workspace/readiness?tenant_id=clinic_demo` moves closer to 100% or 100% if no other gaps remain
