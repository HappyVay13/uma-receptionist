# CX-2 — Owner Workspace Full Migration

## Purpose

Migrate every remaining client-owner workspace page to the shared responsive shell and persistent LV/RU/EN interface language introduced in CX-1, without changing the underlying APIs or runtime behavior.

## Migrated owner page families

1. Business profile / workspace settings
2. Services / service catalog
3. Business Memory / FAQ
4. Price consistency
5. Calendar / availability
6. Telegram channel
7. Final launch checklist
8. Client preview / demo
9. Conversation analytics
10. Lead follow-ups
11. Account / profile / account-billing
12. Setup health / data quality
13. Launch smoke / demo tenant
14. Mature SMB readiness lock
15. Billing / subscription

All existing UI aliases use the same migrated handler and shell.

## Shared navigation

The owner shell now groups navigation into:

- Overview
- Setup
- Operations
- Launch
- Account

Desktop uses a persistent sidebar. Smaller screens use the existing mobile menu with the same grouped routes.

## Localization

- Supported UI languages: LV, RU, EN.
- Preference source: `?ui_lang=`, then `repliq_ui_lang`, then browser language, then English fallback.
- UI language does not update tenant language, Business Memory language or receptionist dialogue language.
- The compatibility adapter translates only known UI phrases and known setup labels.
- Tenant content, service names, FAQ entries and customer messages are not translated.

## Compatibility model

Existing page-specific HTML and JavaScript logic remains the source of page behavior. CX-2 wraps those pages in the shared shell and applies centralized visual/localization adaptation. Existing endpoint URLs and fetch calls are preserved.

No database migration is required.

## Readiness endpoints

Admin-protected:

- `GET /client-experience/owner-workspace/readiness`
- `GET /owner-ui/full-migration/readiness`
- `GET /ui/localization/full-readiness`

Expected core fields:

- `stage = CX-2`
- `cx2_ready = true`
- `owner_workspace_full_migration_ready = true`
- `migrated_owner_page_count = 15`
- `migrated_route_count = 34`
- `supported_ui_languages = [lv, ru, en]`
- `next_phase = CX-3_public_website_signup_authentication`
- `client_experience_polish_complete = false`
- `enterprise_saas_ready = false`

## Security boundary

CX-2 adds no write route and changes no auth route. Owner, strict-owner and super-admin support boundaries remain defined by the existing Stage 61/62/71/91.1 rules.

The shared UI does not expose:

- admin tokens;
- owner login codes;
- magic-link tokens or hashes;
- Google credentials;
- Telegram tokens or webhook secrets;
- billing-provider secrets;
- raw customer identifiers.

## Runtime boundary

Unchanged:

- dialogue and booking orchestration;
- slots and time parsing;
- confirmation, cancel and reschedule;
- Google Calendar event runtime;
- Telegram runtime;
- billing semantics;
- analytics and follow-up data sources;
- external message delivery;
- QA evaluator and LLM orchestration.
