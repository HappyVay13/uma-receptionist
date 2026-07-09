# CX-4.1 — Public Header Section Active State Hotfix

Status: deployed, verified and closed.

## Scope
Fixes the public header active underline for the landing-page section links Product, How it works, and Security in LV/RU/EN.

## Root cause
The home page was rendered with `active="product"`, so Product received server-side `aria-current="page"`. Support was a separate page and also received a server-side active state. The `#how` and `#security` links changed only the URL fragment and had no fragment-aware active-state synchronization.

## Fix
- Adds `data-rp-section` to desktop and mobile section links.
- Synchronizes `aria-current="page"` from the current URL hash.
- Updates the state on initial load, click, and `hashchange`.
- Keeps Product as the default active item on the landing page when no recognized hash is present.
- Bumps only the public UI asset version to `cx4.1` for cache invalidation.

## Boundaries
No route, POST handler, auth, signup, owner session, booking, calendar, Telegram, billing, database, or orchestration semantics were changed.

## Verification result

User confirmed `/dialogue/qa = 50/50 passed` and all remaining CX-4.1 checks normal across LV/RU/EN.
