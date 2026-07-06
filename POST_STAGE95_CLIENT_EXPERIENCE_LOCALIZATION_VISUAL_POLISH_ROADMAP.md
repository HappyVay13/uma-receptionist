# Post-Stage 95 — Client Experience / Localization / Visual Polish Roadmap

Status: active. Stage 95 technical core, CX-1 and CX-2 are deployed and verified; CX-3 is implemented and awaits deploy verification.

## Boundary

Stage 95 closes the current technical Mature SMB product phase. This roadmap is a separate customer-facing polish phase and must not change booking/dialogue/runtime behavior unless a concrete regression is discovered.

## Required workstreams

### 1. UI inventory and shared shell

- Inventory every public, signup, login, owner and support-facing page.
- Separate client-facing pages from internal admin/dev surfaces.
- Introduce one shared header/navigation/footer and responsive page shell.
- Remove inconsistent one-off navigation patterns from client-facing pages.

### 2. LV/RU/ENG localization foundation

- Add a persistent LV/RU/ENG selector to every client-facing page.
- Define one translation dictionary/source of truth rather than duplicating strings in each HTML function.
- Preserve the selected language across navigation, login, signup and owner sessions.
- Define fallback behavior for missing translations.
- Keep tenant business language separate from the dashboard UI language where necessary.

### 3. Owner workspace visual system

- Shared typography, spacing, cards, tables, buttons, forms, badges, states and notifications.
- Consistent sidebar/top navigation across workspace, setup, services, memory, calendar, Telegram, analytics, follow-ups, account and readiness pages.
- Clear empty, loading, error, blocked and success states.
- Mobile and tablet layouts.

### 4. Public website

- Professional Repliq landing page.
- Product explanation, use cases, supported channels and booking flows.
- Pricing/plan presentation based only on the actual billing model.
- Signup/login calls to action.
- Privacy, terms, contact and support entrypoints.
- LV/RU/ENG content.

### 5. Accessibility and cross-browser polish

- Keyboard navigation and visible focus states.
- Semantic labels and form errors.
- Contrast and readable text sizes.
- Chrome/Edge/Firefox/Safari and mobile browser checks.
- No horizontal overflow or broken layouts at common viewport sizes.

### 6. Final client-experience regression

- Test language switching and persistence on all client-facing pages.
- Test every navigation link and logout boundary.
- Verify owner/admin separation after shared navigation changes.
- Re-run `/dialogue/qa` and all protected readiness/auth checks.
- Confirm that design/localization changes did not alter booking, Calendar, Telegram, billing or LLM runtime behavior.

## Readiness rule

The polished client launch must remain false until this phase is deployed and verified. Stage 95 technical readiness must not be reinterpreted as completion of this roadmap.

## Implementation status update

- CX-1 — Shared UI Shell / Localization Foundation: deployed, verified and closed.
- CX-2 — Owner Workspace Full Migration: deployed, verified and closed.
- CX-3 — Public Website / Signup / Authentication: implemented in archive, awaiting deploy verification.
- CX-4 — Responsive / Accessibility / Brand Polish: not started.
- CX-5 — Client Experience Readiness Lock: not started.
