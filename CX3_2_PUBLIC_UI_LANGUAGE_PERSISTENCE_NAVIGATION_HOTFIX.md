# CX-3.2 — Public UI Language Persistence / Navigation Hotfix

## Status

Implemented in archive, awaiting deploy verification.

## Production issue

After CX-3.1, LV/RU/EN switching worked on the current page, but navigation could intermittently return the interface to Latvian. The issue was most visible when opening Product, How it works or Security from the public menu.

## Exact root cause

CX-3.1 changed the language controls into normal server-side links, but the selected `ui_lang` was not persisted by the server in the `repliq_ui_lang` cookie. Several public navigation links opened the root page without an explicit `ui_lang` query parameter. On those requests the language resolver fell back to the browser `Accept-Language`; for a Latvian browser this returned LV.

## Fix

- Every public HTML response now persists the resolved language in the first-party `repliq_ui_lang` cookie.
- The cookie is non-sensitive, scoped to `/`, uses `SameSite=Lax`, and is valid for one year.
- Product, How it works and Security links now include the current `ui_lang` explicitly before the URL fragment.
- The same explicit language propagation is applied in desktop and mobile public navigation.
- Shared public asset version is bumped to `cx3.2`.

## Preserved behavior

The following POST handlers are unchanged:

- `POST /public/signup`
- `POST /owner/login`
- `POST /owner/magic-login`
- `POST /owner/logout`

No database schema, booking, Calendar, Telegram, billing, analytics, follow-up, QA or LLM runtime behavior is changed.

## Expected verification

- Select RU or EN on any public page.
- Navigate through Product, How it works, Security, Support, Login, Signup, Privacy, Terms and Contact.
- The selected UI language remains unchanged.
- Reload a page without `ui_lang`; the saved cookie restores the selected language.
- Mobile navigation continues to use native `details/summary` behavior.
- `/client-experience/public-site/readiness` reports `stage=CX-3.2`, `cx3_ready=true`, `public_language_cookie_server_persisted=true`, and `public_navigation_language_explicit=true`.
- `/dialogue/qa` remains 50/50 passed.
