# R16 — Receptionist → Pulse Production Booking Event Publisher

## Runtime contract

Receptionist publishes the existing Pulse R11 contract only:

- endpoint: `POST /integrations/receptionist/v1/events`
- schema: `2026-07-14`
- event types: `booking.created`, `booking.rescheduled`, `booking.cancelled`
- signature: `HMAC-SHA256(secret, unix_timestamp + "." + exact_raw_body)`

The booking flow never performs a synchronous Pulse call. After the authoritative
Google Calendar operation succeeds, the final conversation state and immutable event
envelope are committed together in the local database. A worker later delivers the
outbox row. Retries keep the same event ID and exact body; only the timestamp/signature
headers are regenerated.

Stage 35 Calendar Safe Mode (`/dialogue/qa`) uses synthetic events. Those fixtures are
explicitly excluded from the production outbox and therefore cannot reach Pulse.

## Required environment

```text
PULSE_RECEPTIONIST_PUBLISHER_ENABLED=true
PULSE_RECEPTIONIST_WEBHOOK_URL=https://<pulse-host>/integrations/receptionist/v1/events
PULSE_RECEPTIONIST_WEBHOOK_SIGNING_SECRET=<same 32+ byte secret configured in Pulse>
```

Optional controls:

```text
PULSE_RECEPTIONIST_REQUEST_TIMEOUT_SECONDS=5
PULSE_RECEPTIONIST_MAX_ATTEMPTS=8
PULSE_RECEPTIONIST_RETRY_BASE_SECONDS=30
PULSE_RECEPTIONIST_RETRY_MAX_SECONDS=3600
PULSE_RECEPTIONIST_POLL_SECONDS=5
PULSE_RECEPTIONIST_BATCH_SIZE=20
PULSE_RECEPTIONIST_LEASE_SECONDS=60
PULSE_RECEPTIONIST_WORKER_ENABLED=true
PULSE_RECEPTIONIST_ALLOW_INSECURE_HTTP=false
```

Pulse must separately have:

```text
PULSE_ENABLE_RECEPTIONIST_INTEGRATION=true
PULSE_RECEPTIONIST_WEBHOOK_SIGNING_SECRET=<same secret>
```

For each Receptionist tenant, Pulse requires a Receptionist connection whose
`source_tenant_ref` equals the Receptionist tenant ID. R16 uses that same tenant ID as
`external_location_ref`; bind it to the correct Pulse location before enabling delivery.

## Schema lifecycle

This repository has no Alembic environment. R16 follows its existing idempotent
runtime-DDL convention. Startup creates:

- `pulse_booking_versions`
- `pulse_booking_event_outbox`

Verification commands:

```bash
python scripts/pulse_outbox.py schema-upgrade
python scripts/pulse_outbox.py schema-status
```

Safe rollback requires disabling the publisher and draining pending events first:

```bash
python scripts/pulse_outbox.py schema-downgrade --confirm R16-DROP-OUTBOX
```

The downgrade drops only the two R16 tables. It does not touch conversations or Google
Calendar data. `--allow-pending-loss` exists only for an explicitly accepted destructive
rollback.

## Operations

Protected HTTP endpoints:

```text
GET  /internal/pulse/outbox
POST /internal/pulse/outbox/dispatch
POST /internal/pulse/outbox/retry
```

They use the existing Repliq admin protection and CSRF boundaries. CLI equivalents:

```bash
python scripts/pulse_outbox.py status
python scripts/pulse_outbox.py dispatch --limit 20
python scripts/pulse_outbox.py retry --event-id <event_id>
```

Safe observability includes event ID, event type, tenant reference, booking reference,
attempts, status, timestamps and error category. It excludes signing secrets,
Authorization headers, customer phone/email, dialogue text and arbitrary Pulse response
fields.

## Failure behavior

- Network timeout, 408, 425, 429 and 5xx: bounded exponential retry.
- 401/403, 409, 422 and accepted=false: permanent failed state for operator review.
- Process crash while sending: the lease expires and the event is reclaimed.
- Pulse committed but Receptionist missed the acknowledgement: retry uses the same body
  and Pulse returns its idempotent duplicate result.
- Higher aggregate versions cannot overtake an undelivered lower version for the same
  tenant and booking.
