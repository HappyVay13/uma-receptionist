# Stage 91.1 — Owner Account Logout / Auth Guard Hotfix

Status: deployed and verified by user. Production `/dialogue/qa` = 50/50 passed; all other Stage 91.1 checks OK.

Reason:
- After Stage 91 deploy, the owner account UI appeared to remain accessible after logout in the browser.
- External no-cookie check against the deployed URL returned 401, so the endpoint was not fully public without cookies.
- Code audit found that Stage 91 account/profile/billing routes still allowed the Stage 62 super-admin support bypass, and `/admin/logout` cleared only admin cookies while `/owner/logout` cleared only owner cookies. In a browser that had both sessions, logging out of one session could leave the other session able to open owner surfaces.

Scope:
- Stage 91 account/profile/billing JSON and UI now require a strict Stage 71 owner session + tenant binding.
- Stage 62 super-admin bypass is disabled for these Stage 91 owner account center routes:
  - `GET /owner/account`
  - `GET /owner/account/ui`
  - `GET /owner/profile`
  - `GET /owner/profile/ui`
  - `GET /owner/account-billing`
  - `GET /owner/account-billing/ui`
- Stage 91 readiness routes remain admin-protected.
- `/admin/logout` now clears both admin and owner session cookies for the browser.
- `/owner/logout` now clears both owner and admin session cookies for the browser.

Security:
- No owner POST routes were added.
- No CSRF path was added because the hotfix remains read-only except existing logout endpoints.
- No raw admin tokens, owner login codes, magic tokens, hashes, billing secrets, Google credentials, Telegram credentials, or service account JSON are exposed.
- `tenant_id` remains not auth.
- Existing already-issued cookies can only be cleared by visiting `/admin/logout` or `/owner/logout` after deploy; after that, Stage 91 account center should require owner login again.

No runtime behavior changes:
- No receptionist dialogue changes.
- No booking/slots/date parsing/side-question/cancel/reschedule changes.
- No Google Calendar runtime changes.
- No Telegram runtime changes.
- No billing/payment runtime changes.
- No notification sends or external sends.
- No LLM orchestration or QA evaluator changes.

Expected verification:
- Visit `/admin/logout` or `/owner/logout` once after deploy to clear any old browser sessions.
- `/owner/account/ui?tenant_id=clinic_demo` should require owner login after logout.
- `/owner/profile/ui?tenant_id=clinic_demo` should require owner login after logout.
- `/owner/account-billing/ui?tenant_id=clinic_demo` should require owner login after logout.
- With a valid owner session, the pages should open normally.
- `/dialogue/qa` remains 50/50 passed.
- `enterprise_saas_ready=false` remains explicit.
