# Stage 35.3 — QA Runner Calendar-Safe Mode

This hotfix keeps the Stage 35 regression runner focused on conversational QA instead of external Google Calendar API availability.

## What changed
- Regression runner uses `clinic_demo` by default.
- During `source="regression_runner"`, Stage 35 enables a scoped calendar-safe mode.
- Calendar `freebusy` calls are skipped only inside regression runner execution.
- Calendar event creation/update/delete are replaced with dummy safe results only inside regression runner execution.
- Normal dev_chat, Telegram, webchat, and production booking flows continue using real calendar logic.

## Env flag
`STAGE35_CALENDAR_SAFE_MODE=1` by default.
Set to `0` only if you intentionally want regression runner to hit real Google Calendar.

## Test
Open `/dialogue/qa` and run full regression suite.
The result should not fail because of Google Calendar SSL/freebusy errors.
