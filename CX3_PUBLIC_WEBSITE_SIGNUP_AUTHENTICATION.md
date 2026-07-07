# CX-3 — Public Website / Signup / Authentication

## Status

Deployed, verified and closed.

## Purpose

Replace the technical public entrypoints with one professional, responsive and localized Repliq public experience while preserving the verified Mature SMB backend and owner-auth behavior.

## Added public experience

- Public website: `/`, `/home`, `/launch`, `/launch/ui`, `/public/launch`, `/public/launch/ui`
- Signup: `/public/signup`, `/public/signup/ui`
- Owner authentication presentation: `/owner/login`, `/owner/magic-login`, `/owner/logout`
- Information pages: `/privacy`, `/privacy-policy`, `/terms`, `/terms-of-service`, `/contact`, `/support`
- Assets: `/assets/repliq-public.css`, `/assets/repliq-public.js`, `/favicon.svg`

## Localization

- Supported UI languages: LV, RU, EN.
- Selection order remains query `ui_lang`, `repliq_ui_lang` cookie, browser language, English fallback.
- The signup business-language field is intentionally separate from website/interface language.
- Translation catalogs are centralized in `repliq/public_ui.py`.

## Preserved runtime

The exact existing POST handler implementations remain unchanged:

- `stage72_public_signup_submit`
- `owner_login_submit`
- `stage76_owner_magic_login_submit`
- `owner_logout_api`

This preserves:

- tenant creation;
- owner binding and session creation;
- honeypot/rate limits/abuse protection;
- CSRF boundary;
- one-time magic-token behavior;
- signed owner-session cookies;
- existing redirects and API payloads.

## Truthful limitations

- No automatic checkout or live billing-provider promise.
- Public contact email is rendered only when configured through environment variables.
- Privacy and Terms content requires legal-entity-specific review before broad commercial launch.
- No GDPR or enterprise-readiness claim.

## Readiness

Admin-protected aliases:

- `/client-experience/public-site/readiness`
- `/public-site/readiness`
- `/public-auth/readiness`

Expected:

- `stage=CX-3`
- `status=ready`
- `cx3_ready=true`
- `public_website_ready=true`
- `blocking=[]`
- `client_experience_polish_complete=false`
- `next_phase=CX-4_responsive_accessibility_brand_polish`
- `enterprise_saas_ready=false`

## Post-deploy verification

1. `/health`
2. `/dialogue/qa` — expected 50/50 passed
3. CX-1 and CX-2 readiness remain ready
4. CX-3 readiness is ready through admin login
5. Test every public page in LV/RU/EN
6. Test mobile navigation at 375 px and 768 px
7. Complete one controlled signup test only if a new test tenant is acceptable
8. Test owner login and logout with an existing owner account
9. Confirm business language does not change when switching public UI language

## CX-3.1 hotfix update

The first deployed CX-3 public shell exposed a shared frontend failure mode: language switching and mobile-menu state both required the same external JavaScript asset. CX-3.1 removes that dependency for essential navigation.

Changes:
- language controls are real GET links rather than JavaScript-only buttons;
- current path and query parameters are retained while replacing only `ui_lang`;
- mobile navigation uses native `details/summary`;
- shared public assets use version `cx3.1` to invalidate cached CX-3.0 assets;
- JavaScript remains optional enhancement only.

Updated readiness expectation:
- `stage=CX-3.1`
- `public_language_switcher_no_js_required=true`
- `mobile_menu_native_details_ready=true`
- `public_asset_cache_busted_for_hotfix=true`

## CX-3.2 hotfix update

CX-3.1 fixed direct language switching and mobile-menu behavior, but it did not persist the selected language server-side. Public links that opened the root page without `ui_lang` could therefore fall back to the browser language.

CX-3.2:
- sets `repliq_ui_lang` on every public HTML response;
- includes the active language in Product, How it works and Security links on desktop and mobile;
- bumps the public UI version to `cx3.2`;
- preserves all existing POST/auth/runtime behavior.

Updated readiness expectation:
- `stage=CX-3.2`
- `public_language_cookie_server_persisted=true`
- `public_navigation_language_explicit=true`
- `public_asset_cache_busted_for_hotfix=true`
