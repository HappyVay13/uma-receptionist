# R19 Receptionist → Pulse Booking End-Time Runbook

## Scope

R19 changes only the Pulse booking-event publisher metadata. Dialogue orchestration, booking confirmation, Google Calendar writes, Telegram behavior, owner UI and billing are not redesigned.

## Deployment order

1. Deploy Repliq Pulse 0.19.0 first.
2. Verify Pulse `/health/live` reports `0.19.0` and `/health/ready` expects schema `20260722_0017`.
3. Deploy this Receptionist archive with the existing Pulse publisher environment variables unchanged.
4. Run `/dialogue/qa` and require `50/50 passed`.

## Emitted timing

For successful create/reschedule operations Receptionist calculates:

```text
ends_at = starts_at + service.duration_min
duration_minutes = service.duration_min
```

The immutable outbox payload uses contract version `2026-07-22`.

Cancellation reads `start.dateTime` and `end.dateTime` from the authoritative Google Calendar event when available. Cancellation remains valid without timing fields.

## Expected payload excerpt

```json
{
  "schema_version": "2026-07-22",
  "booking": {
    "starts_at": "2026-07-22T09:00:00Z",
    "ends_at": "2026-07-22T09:45:00Z",
    "duration_minutes": 45
  }
}
```

## Verification

Create two real bookings with different service durations. In Pulse status verify:

```text
cleanup_timing_source = booking_end
booking_ends_at = expected end
cleanup_scheduled_for = booking_ends_at + cleanup_delay_minutes
```

Reschedule one booking to a service/time with another duration and verify the new event version replaces both the end time and cleanup action timing.

## Rollback

Roll back Receptionist before rolling Pulse below 0.19.0. Pulse 0.19.0 itself can safely receive both `2026-07-14` and `2026-07-22` events.
