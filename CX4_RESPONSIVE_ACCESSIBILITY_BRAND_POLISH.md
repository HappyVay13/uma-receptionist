# CX-4 — Responsive / Accessibility / Brand Polish

Status: implemented in archive; awaiting deploy verification.

## Purpose

CX-4 unifies the public website and owner workspace around one minimal Repliq identity and hardens their responsive/accessibility behavior without changing product runtime, authentication or write semantics.

## Brand direction

The previous violet rounded tile is retained as a continuity cue, but the generic `R` is replaced by a custom reply-loop monogram:

- the vertical stem and rounded bowl read as `R`;
- the diagonal exit reads as the tail of `Q`;
- the full loop also suggests a reply/message flow;
- the mark remains legible at favicon and mobile-header sizes.

The wordmark is now lowercase `repliq`. It is stored as SVG outlines rather than browser text, so its geometry is consistent and does not depend on a font being installed or downloaded. The final `q` carries the violet accent.

Primary identity colors:

- ink: `#17142B`;
- violet: `#6757F5`;
- secondary violet: `#9A5CFF`;
- soft surface: `#F8F7FB`.

## Brand assets

Read-only routes:

- `/favicon.svg`
- `/assets/repliq-brand-mark.svg`
- `/assets/repliq-brand-lockup.svg`
- `/assets/repliq-brand-lockup-dark.svg`

The same inline mark and outlined wordmark are used by public and owner shells.

## Responsive polish

Public UI:

- refined desktop/tablet/mobile breakpoints at 1040, 860, 640 and 420 px;
- single-column forms, cards and CTA layouts on small screens;
- full-width mobile CTA buttons;
- fixed-width-safe language selector and native mobile menu;
- mobile footer restructuring;
- no horizontal overflow in 375/390/768/1440 px test renders.

Owner UI:

- responsive sidebar collapse below 980 px;
- native `details/summary` mobile navigation;
- one- and two-column adaptive card grids;
- safe overflow for tables and technical payloads;
- smaller mobile spacing without shrinking controls below practical tap size;
- explicit `ui_lang` preservation in owner navigation.

## Accessibility foundation

Added to both public and owner shells:

- skip-to-content link;
- stable `main-content` landmark;
- visible `:focus-visible` states;
- minimum practical interactive-control heights;
- semantic active-page indication;
- native mobile disclosure navigation;
- reduced-motion behavior;
- forced-colors/high-contrast handling;
- decorative logo SVGs hidden from assistive technology while brand links retain accessible names;
- responsive tables and media constraints.

## Language behavior

- LV/RU/EN remains separate from tenant/business language.
- Public server-side language persistence from CX-3.2 is preserved.
- Owner navigation now carries `ui_lang` explicitly.
- Owner HTML responses persist `repliq_ui_lang` with the same non-sensitive one-year first-party cookie policy.

## Readiness endpoints

Admin-protected aliases:

- `/client-experience/polish/readiness`
- `/ui/accessibility/readiness`
- `/brand/readiness`

Expected result:

- `stage=CX-4`
- `status=ready`
- `cx4_ready=true`
- `accessibility_foundation_ready=true`
- `brand_identity_ready=true`
- `shared_brand_assets_ready=true`
- `blocking=[]`
- `client_experience_polish_complete=false`
- `next_phase=CX-5_client_experience_readiness_lock`
- `enterprise_saas_ready=false`

## Runtime/security boundary

Unchanged:

- public signup POST implementation;
- owner login POST implementation;
- magic-login POST implementation;
- logout POST implementation;
- owner/admin/strict-owner access boundaries;
- CSRF and rate-limit behavior;
- tenant creation and owner-session semantics;
- booking, slots, parsing, side questions, confirmation, cancellation and rescheduling;
- Google Calendar runtime;
- Telegram runtime;
- billing semantics;
- analytics/follow-up data sources;
- QA evaluator and LLM orchestration;
- database schema and external sends.

No new POST routes or database writes were added.

## Manual verification still required

- Chrome and Edge desktop;
- Firefox desktop;
- Android Chrome;
- iOS Safari when available;
- 375, 390, 768 and desktop widths;
- keyboard-only navigation;
- mobile menu open/close behavior;
- LV/RU/EN persistence across public and owner navigation;
- `/dialogue/qa = 50/50 passed`.

The brand mark is a project identity draft. A trademark/name-conflict review remains appropriate before broad commercial launch.
