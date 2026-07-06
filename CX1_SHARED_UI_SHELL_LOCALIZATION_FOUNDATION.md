# CX-1 — Shared UI Shell / Localization Foundation

Status: implemented in archive, awaiting deploy verification.

## Purpose

Create the first reusable client-facing UI foundation after the Stage 95 technical baseline lock.

CX-1 does not attempt to restyle every owner page. It establishes a shared shell, a separate persistent interface-language preference, and migrates four pilot page families without changing their existing API or authentication semantics.

## Added foundation

- `repliq/ui_foundation.py`
  - shared LV/RU/EN interface dictionary;
  - shared responsive shell;
  - shared owner navigation;
  - shared design tokens/components;
  - interface-language resolver;
  - persistent non-sensitive `repliq_ui_lang` cookie;
  - known owner setup-label translations.
- Public read-only assets:
  - `GET /assets/repliq-ui.css`
  - `GET /assets/repliq-ui.js`
- Admin-protected readiness aliases:
  - `GET /client-experience/foundation/readiness`
  - `GET /ui/localization/readiness`
  - `GET /owner-ui/shell/readiness`

## Migrated pilot pages

- `/owner/login`
- `/owner/dashboard/ui`
- `/owner/control-center/ui`
- `/owner/get-started/ui`
- `/owner/welcome/ui`
- `/owner/setup/ui`
- `/owner/workspace/ui`
- `/owner/workspace/setup/ui`

## Language boundary

UI language is separate from tenant/business language.

Resolution order:

1. explicit `?ui_lang=lv|ru|en`;
2. `repliq_ui_lang` browser cookie;
3. browser `Accept-Language`;
4. English fallback, preserving the previous default UI behavior.

Changing the language in the shared shell writes only the non-sensitive interface-language cookie and reloads the current page. It does not update tenant configuration or receptionist reply language.

## UX changes

- consistent Repliq header and owner navigation;
- desktop and mobile navigation;
- LV/RU/EN language switcher;
- shared cards, buttons, fields, badges, progress bars and details components;
- technical/raw payloads collapsed by default;
- customer-facing titles and actions replace prominent stage/debug wording on the pilot pages;
- existing JSON APIs and owner actions remain unchanged.

## Security and runtime boundary

- No owner POST route added.
- No CSRF write path added.
- No tenant/database write added.
- No auth boundary changed.
- `/owner/login` remains public.
- Existing owner-protected and strict-owner-only rules remain unchanged for the other pilot pages.
- Readiness aliases are Stage 61/62 admin-protected.
- Shared CSS/JS assets contain no tenant data, secrets, tokens or credentials.
- Booking, dialogue, Calendar, Telegram, billing, magic links, abuse protection, QA evaluator, LLM orchestration and external sends are unchanged.
- `client_experience_polish_complete=false` remains explicit because the remaining owner pages move in CX-2.
- `enterprise_saas_ready=false` remains explicit.

## Expected verification

- Render deploy starts successfully.
- `/dialogue/qa` remains 50/50 passed.
- CX-1 readiness returns `stage=CX-1`, `cx1_ready=true`, and no blockers.
- Login, dashboard, get-started and workspace render in LV/RU/EN.
- Selecting a UI language persists across the migrated pages.
- Changing UI language does not change the tenant business language.
- Existing owner/admin authentication behavior remains unchanged.
- Mobile navigation opens and all shared owner links preserve `tenant_id`.
- Raw technical payloads remain available only inside collapsed technical details.
