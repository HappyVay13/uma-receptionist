# CX-3.1 — Public Language Switcher / Mobile Menu Hotfix

## Confirmed issue

Across `/`, signup, owner auth, Privacy, Terms, Contact and Support pages:
- selecting RU or EN did not change the rendered language;
- smartphone navigation immediately collapsed or did not remain usable.

## Root cause

Essential public controls were JavaScript-only. The language selector used buttons whose navigation existed only inside `/assets/repliq-public.js`, and the mobile menu used the same asset to toggle a CSS class. A failed, blocked or stale asset therefore broke both controls together.

## Correction

- LV/RU/EN controls are now regular same-origin links.
- Links are generated from the current request and retain every existing query parameter except `ui_lang`, which is replaced.
- This preserves tenant, next and magic-token parameters.
- Mobile navigation now uses native HTML `details/summary` behavior.
- Shared public asset version is bumped to `cx3.1`.
- JavaScript is retained only for optional enhancement and utility helpers.

## Preserved behavior

No changes to signup, owner-login, magic-login or logout POST handlers, sessions, tokens, CSRF, abuse protection, tenant creation or receptionist runtime.
