# R16 COMPLETION REPORT

## Stage name

`R16 — Receptionist → Pulse Production Booking Event Publisher`

## Status

`R16 COMPLETE — AWAITING DEPLOYMENT VERIFICATION`

Stage implementation, local automatic verification, cross-repository contract E2E, schema lifecycle checks, security scan and clean-archive extraction retest are complete. The live Render deployment, live Google Calendar smoke and protected `/dialogue/qa: 50/50 passed` remain operator acceptance gates.

## Baseline analysis

### Receptionist authoritative flow

- Booking creation and rescheduling are finalized by `book_appointment_for_datetime()` in `repliq/legacy_app.py`.
- Creation becomes authoritative only after `create_calendar_event()` returns a successful Google Calendar event result.
- Rescheduling becomes authoritative only after `update_calendar_event()` returns success for the existing Google event ID.
- Cancellation uses the existing event lookup and `delete_calendar_event()` path; R16 factors the successful mutation into `cancel_authoritative_booking()` so the same authoritative Google event ID is used by the contract.
- Every successful create/reschedule/cancel caller persists the final conversation through `db_save_conversation()` before the HTTP response is returned to the user.
- The local transaction boundary is `with engine.begin()` in `db/conversations.py`.
- The original Receptionist archive contained no Pulse publisher, no persistent integration-event table, no delivery worker and no retry/recovery mechanism.

### Pulse R11 receiver

The unchanged Pulse R15A archive already contains the complete R11 receiver:

- endpoint `POST /integrations/receptionist/v1/events`;
- contract version `2026-07-14`;
- event types `booking.created`, `booking.rescheduled`, `booking.cancelled`;
- HMAC-SHA256 verification over `timestamp + "." + exact raw body`;
- bounded timestamp replay protection;
- explicit source tenant connection and external location binding;
- persistent inbox;
- event-ID idempotency and payload-conflict detection;
- monotonic booking aggregate versions;
- deterministic duplicate/out-of-order handling.

### Exact integration gap

Pulse could receive signed fixture/test events, but Receptionist did not create or durably deliver production events from its real booking application flows. A temporary Pulse outage therefore had no recoverable Receptionist-side event state because no publisher existed.

### Why the implementation is safe

- No Pulse HTTP call occurs inside the booking path or local database transaction.
- After the successful Google Calendar mutation, the final conversation state and immutable Pulse outbox row commit in one local database transaction.
- The user-facing handler returns only after that local commit.
- Delivery happens asynchronously from persistent state.
- A process restart after the outbox commit is recoverable.
- A lost acknowledgement causes the exact same event ID and body to be delivered again; Pulse returns its stored idempotent result.
- Higher versions for one tenant/booking cannot overtake an undelivered lower version.
- Stage 35 Calendar Safe Mode / `/dialogue/qa` fixture operations are explicitly excluded from the production outbox.

R16 does not introduce a distributed two-phase transaction with Google Calendar. The existing application operation is considered committed only after Google Calendar success plus the local `db_save_conversation()` transaction; the success response is not returned before that point.

## Implementation summary

### Publisher and persistent outbox

Added `integrations/pulse_booking_events.py` with:

- immutable R11 payload creation;
- deterministic stable event IDs;
- tenant-scoped aggregate versions;
- payload SHA-256 integrity verification;
- persistent statuses: `pending`, `sending`, `retry`, `delivered`, `failed`;
- PostgreSQL `FOR UPDATE SKIP LOCKED` claiming;
- portable SQLite claim path for tests;
- expiring delivery leases for restart recovery;
- same-booking version ordering;
- bounded exponential backoff;
- maximum attempt / failed state;
- manual retry and manual dispatch;
- safe acknowledgement allow-list;
- safe status summary.

### Signing

- R11 schema version: `2026-07-14`.
- Signature: `v1=<HMAC-SHA256>` over exact stored body.
- Each retry reuses the exact body and event ID but receives a fresh timestamp/signature inside the Pulse replay window.
- The signing secret comes only from environment-backed settings.

### Authoritative application integration

- Real `booking.created` is attached only after successful Google Calendar insert.
- Real `booking.rescheduled` reuses the existing Google event ID and increments the booking aggregate version.
- Real `booking.cancelled` reuses the deleted Google event ID and increments the aggregate version.
- `db_save_conversation()` validates that the event tenant equals the conversation tenant and writes conversation + outbox atomically.
- Dialogue prompts, intent routing, locale behavior and user-facing responses were not changed.

### Retry and recovery

- Timeout, network failure, 408, 425, 429 and 5xx are transient.
- 401/403, 409, 422 and `accepted=false` are permanent operator-review states.
- Retry delay is bounded exponential backoff.
- An expired `sending` lease is reclaimed after restart.
- Manual retry preserves event identity and payload.

### Test/production isolation

Stage 35 regression fixtures use synthetic Calendar events. `attach_pulse_booking_event()` now ignores events while Calendar Safe Mode is active, preventing `/dialogue/qa` test traffic from entering the production Pulse inbox.

### Pulse changes

`Pulse archive unchanged — R15A archive remains authoritative.`

No Pulse source file was modified. The existing R11 receiver passed the complete R15A regression and focused contract suite.

## Changed files

### Added

```text
R16_COMPLETION_REPORT.md
R16_PULSE_BOOKING_EVENT_RUNBOOK.md
integrations/pulse_booking_events.py
scripts/pulse_outbox.py
tests/conftest.py
tests/test_r16_authoritative_application_flows.py
tests/test_r16_conversation_atomicity.py
tests/test_r16_pulse_outbox.py
```

### Updated

```text
README.md
config/settings.py
db/conversations.py
repliq/legacy_app.py
```

### Removed

```text
None.
```

## Database migrations

### Receptionist

`No new Alembic migration.`

The Receptionist archive has no Alembic environment. R16 follows the repository's existing idempotent runtime-DDL convention and creates only:

```text
pulse_booking_versions
pulse_booking_event_outbox
```

Verified lifecycle:

```text
python scripts/pulse_outbox.py schema-upgrade
PASS — both tables present

python scripts/pulse_outbox.py schema-status
PASS — both tables present, pending_events=0

python scripts/pulse_outbox.py schema-downgrade --confirm R16-DROP-OUTBOX
PASS — both R16 tables removed; unrelated data preserved by test

python scripts/pulse_outbox.py schema-upgrade
PASS — both tables recreated
```

`alembic current` / `alembic check`: not applicable to Receptionist because no Alembic environment exists in the supplied archive.

### Pulse

No new migration and no source changes.

Existing R15A migration state was verified:

```text
python -m alembic upgrade head
PASS

python -m alembic current
20260714_0013 (head)

python -m alembic check
No new upgrade operations detected.
```

## Automatic tests

### Receptionist R16 suite

```text
python -m pytest -q
21 passed, 144 warnings in 2.59s
```

The warnings are Python 3.13 SQLite datetime-adapter deprecation warnings from SQLAlchemy test execution; no test failed or was skipped.

Coverage includes:

- exact R11 payload and schema version;
- create/reschedule/cancel application flows;
- atomic conversation + outbox transaction;
- rollback of state, event and aggregate version;
- stable event identity and immutable payload across retry;
- raw-body HMAC signature;
- timeout/network/503 retry;
- bounded failed state;
- permanent auth/contract/conflict errors;
- restart recovery from expired lease;
- payload integrity failure;
- tenant isolation and same booking reference across tenants;
- ordered delivery for aggregate versions;
- acknowledgement redaction;
- webhook URL credential/query rejection;
- Stage 35 QA fixture exclusion;
- runtime schema upgrade/downgrade/re-upgrade.

### Pulse full baseline

```text
python -m pytest -q --ignore=tests/test_migrations.py
258 passed in 22.65s

python -m pytest -q tests/test_migrations.py
4 passed in 21.14s
```

Total Pulse baseline:

```text
262 passed
```

### Focused R11 contract suite

```text
python -m pytest -q tests/test_receptionist_integration_contract.py
13 passed in 1.49s
```

### Cross-repository E2E

```text
python cross_repo_r16_e2e.py
{"duplicate_retry": true, "pulse_booking_projections": 1, "pulse_inbox_events": 3, "sender_events": 3, "sender_statuses": ["delivered", "delivered", "delivered"]}
elapsed=2.61s
```

The test sends create → reschedule → cancel to the real Pulse receiver. It simulates Pulse committing the first event while Receptionist loses the acknowledgement. The retry uses the same event/body, Pulse reports `duplicate=true`, three inbox events produce one booking projection, and the final projection is cancelled.

### Compilation/import

```text
python -m compileall -q .
PASS
```

```text
import integrations.pulse_booking_events
PASS — schema 2026-07-14 and all three R11 event types loaded
```

### Final archive packaging and extraction retest

```text
Archive: Repliq_Receptionist_R16.zip
Archive hygiene: PASS
Files packaged: 197
No __pycache__, .pytest_cache, .venv, .env, local database, log or nested archive files
Credential-pattern scan: PASS
```

After extracting the ZIP into a new clean directory:

```text
python -m pytest -q
21 passed, 144 warnings in 3.08s

python -m compileall -q .
PASS

import integrations.pulse_booking_events
PASS
```

## Regression status

```text
Receptionist automated R16 regression: 21/21 passed
Pulse automated regression: 262/262 passed
Pulse R11 focused contract regression: 13/13 passed
Cross-repository R16 E2E: passed
```

The supplied Receptionist archive does not include an offline database fixture capable of executing the entire protected live regression runner without the deployed tenant/configuration database. The matrix remains exactly 50 scenarios and the R16 application-flow test confirms the matrix count is unchanged.

Mandatory post-deployment gate:

```text
/dialogue/qa: 50/50 passed
```

## Security verification

- No signing secret is stored in the event payload or database.
- No signing secret, Authorization header, database credential, phone, email or dialogue text is logged by the publisher.
- `PulsePublisherConfig.__repr__` redacts the secret.
- Webhook URLs containing embedded credentials, query parameters or fragments are rejected.
- Production HTTP requires HTTPS unless explicitly permitted for local/test operation.
- Signature validation is performed by the unchanged Pulse R11 receiver before JSON parsing.
- Timestamp replay protection remains enforced by Pulse.
- Exact duplicate delivery remains idempotent.
- Reusing an event ID with a different payload remains a Pulse conflict.
- Receptionist validates event tenant equals conversation tenant.
- Pulse requires an explicit source-tenant connection and explicit external-location binding.
- Same booking references in different tenants use separate aggregate-version identities.
- QA fixture events are excluded from production delivery.
- Operational HTTP endpoints use existing Repliq admin authentication; write endpoints also use existing CSRF boundaries for browser sessions.
- Final archive hygiene scan confirmed no `.env`, token file, local database, logs, cache directories or detected credential patterns.

## Rollback

### Receptionist code rollback

1. Set `PULSE_RECEPTIONIST_PUBLISHER_ENABLED=false`.
2. Inspect pending events with `python scripts/pulse_outbox.py status`.
3. Prefer delivering or exporting pending events before reverting code.
4. Deploy the previous CX-5 Receptionist archive.
5. Leave the two R16 tables intact unless data loss has been explicitly accepted. They are ignored by the previous code and preserve pending events for a later R16 re-deploy.

### Pending events

- If the code is rolled back while R16 tables remain, pending events stay durable but are not delivered by the old version.
- Re-deploying R16 resumes recovery from those rows.
- Do not recreate events manually; this avoids creating a second logical event/version.
- Pulse remains duplicate-safe if an event was committed remotely but its local acknowledgement was lost.

### Schema rollback

No Alembic rollback is required. Optional destructive removal:

```text
PULSE_RECEPTIONIST_PUBLISHER_ENABLED=false
python scripts/pulse_outbox.py schema-downgrade --confirm R16-DROP-OUTBOX
```

The command refuses to run while publishing is enabled and refuses pending-event loss unless `--allow-pending-loss` is explicitly supplied.

### Pulse rollback

No Pulse rollback is needed because Pulse was not changed. R15A remains authoritative.

## Known limitations

- Live Render deployment, live Google Calendar create/reschedule/cancel and `/dialogue/qa` have not been executed from this local environment.
- Pulse integration connection and external location binding must exist before enabling the Receptionist publisher.
- The current Receptionist data model has one authoritative calendar/location per tenant; R16 therefore uses the Receptionist tenant ID as `external_location_ref`. Multiple independent locations/calendars per tenant require a later explicitly approved contract-mapping stage.
- Permanent Pulse auth/contract/tenant/binding errors enter `failed` state and intentionally block later versions of the same booking until the operator fixes and retries the earlier event.
- Manual retry preserves the cumulative attempt counter; a successful next attempt is accepted, while another failure returns the event to `failed` for further operator review.
- No production hardware, Tuya or Shelly device was connected in R16.

## Commit messages

```text
Receptionist commit message:
feat(receptionist): publish durable signed booking events to Pulse
```

```text
Pulse commit message:
Not applicable — Pulse source archive unchanged.
```

## Exact user tests

### A. Receptionist deployment checks

1. Configure Render environment without printing the secret:

```text
PULSE_RECEPTIONIST_PUBLISHER_ENABLED=true
PULSE_RECEPTIONIST_WEBHOOK_URL=https://<PULSE_HOST>/integrations/receptionist/v1/events
PULSE_RECEPTIONIST_WEBHOOK_SIGNING_SECRET=<same 32+ byte secret as Pulse>
PULSE_RECEPTIONIST_WORKER_ENABLED=true
```

Expected: deployment starts successfully. Do not paste the secret into chat or screenshots.

2. Open health:

```bash
curl -sS https://<RECEPTIONIST_HOST>/health
```

Expected fields:

```text
status=ok
pulse_booking_publisher_enabled=true
pulse_booking_worker_enabled=true
pulse_booking_secret_configured=true
pulse_booking_secret_exposed=false
```

Output contains no secret.

3. Check outbox using the existing admin token stored in a local shell variable:

```bash
curl -sS \
  -H "X-Repliq-Admin-Token: $REPLIQ_ADMIN_TOKEN" \
  https://<RECEPTIONIST_HOST>/internal/pulse/outbox
```

Expected: HTTP 200, counts object, `signing_secret_exposed=false`. The command line contains the admin token variable name, not the token value. Do not send terminal history containing expanded credentials.

4. In the Render shell:

```bash
python scripts/pulse_outbox.py schema-status
```

Expected: both R16 tables are `true`.

On error send: HTTP status, safe JSON body, Render traceback with secrets redacted, and the output of `schema-status`.

### B. Pulse deployment checks

1. Configure Pulse:

```text
PULSE_ENABLE_RECEPTIONIST_INTEGRATION=true
PULSE_RECEPTIONIST_WEBHOOK_SIGNING_SECRET=<same secret as Receptionist>
```

2. Verify migrations:

```bash
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

Expected:

```text
20260714_0013 (head)
No new upgrade operations detected.
```

3. Confirm that the Pulse database has an active Receptionist integration connection with:

```text
source_tenant_ref=<exact Receptionist tenant_id>
```

4. Confirm an external location binding with:

```text
external_location_ref=<same exact Receptionist tenant_id>
```

Expected: it resolves to the intended Pulse tenant/location. These IDs are references, not credentials.

On error send: Pulse safe application logs, response error code, tenant public ID, integration connection public ID and location public ID. Do not send the signing secret or database URL.

### C. End-to-end integration checks

Run in this order for one isolated test customer/tenant.

1. Create a booking through the real Receptionist application flow.

Expected:

```text
Receptionist booking succeeds normally.
outbox contains booking.created with status delivered.
Pulse integration inbox contains one processed event.
Pulse booking projection is scheduled.
```

2. Reschedule the same booking.

Expected:

```text
booking.rescheduled uses the same booking_ref.
aggregate_version increases from 1 to 2.
Pulse updates the same booking projection.
```

3. Cancel the same booking.

Expected:

```text
booking.cancelled uses the same booking_ref.
aggregate_version increases from 2 to 3.
Pulse projection becomes cancelled.
```

4. Inspect safe sender state:

```bash
curl -sS \
  -H "X-Repliq-Admin-Token: $REPLIQ_ADMIN_TOKEN" \
  https://<RECEPTIONIST_HOST>/internal/pulse/outbox
```

Expected: no failed event for the test booking. Output contains event/tenant/booking references but no customer phone/email or secret.

On error send: event ID, event type, tenant reference, booking reference, attempt count, status, last error category, and redacted logs from both services.

### D. Full `/dialogue/qa` regression

1. Open the protected QA dashboard with existing admin authentication.
2. Run the full regression suite.

Expected acceptance gate:

```text
50/50 passed
0 failed
```

Also verify that running QA does not increase the production outbox count. Compare `/internal/pulse/outbox` before and after the QA run.

On error send: failed scenario IDs, expected-missing fields, forbidden hits, statuses/states and assistant replies. This output can contain test dialogue text but must not contain production customer data or credentials.

### E. Failure/retry checks

1. Temporarily set an unreachable Pulse host only in a controlled test deployment, or stop Pulse briefly after the test booking path is ready.
2. Create one booking.

Expected:

```text
Receptionist still reports the booking result correctly.
outbox status becomes retry.
last_error_category is network_timeout, network_error, transport_error, or pulse_http_503.
```

3. Restore Pulse.
4. Force or wait for retry:

```bash
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -H "X-Repliq-Admin-Token: $REPLIQ_ADMIN_TOKEN" \
  -d '{"limit":20}' \
  https://<RECEPTIONIST_HOST>/internal/pulse/outbox/dispatch
```

Expected: the same event ID becomes `delivered`.

5. Simulate lost acknowledgement by restarting Receptionist after Pulse receives the event but before local confirmation only in a controlled environment.

Expected: expired lease is reclaimed; retry receives `duplicate=true`; no duplicate Pulse effect exists.

6. For a permanent test failure, deliberately use a wrong secret only in a disposable environment.

Expected: Pulse returns 401; event becomes `failed`; no automatic tight retry. Restore the correct secret and run:

```bash
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -H "X-Repliq-Admin-Token: $REPLIQ_ADMIN_TOKEN" \
  -d '{"event_id":"<EVENT_ID>"}' \
  https://<RECEPTIONIST_HOST>/internal/pulse/outbox/retry
```

Then dispatch or wait for the worker. Do not paste either secret into logs, screenshots or chat.

## User actions required

`USER ACTION REQUIRED: YES`

1. Deploy Pulse R15A with the R11 integration enabled and the shared secret configured.
2. Confirm/create the Pulse source-tenant connection and tenant-ID location binding.
3. Deploy `Repliq_Receptionist_R16.zip` with the same shared secret and the production Pulse webhook URL.
4. Run sections A–E above.
5. Send back the safe outputs: Receptionist `/health`, outbox status, Pulse migration current/check, one create/reschedule/cancel event chain, failure/retry result and `/dialogue/qa: 50/50 passed`.

Do not send secrets, full environment dumps, database URLs, Authorization headers, customer phone/email or production dialogue text.
