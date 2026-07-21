# Repliq Receptionist R19 Completion Report

## Stage

R19 — Booking End-Time Contract Publisher

## Software status

```text
Implementation complete
Pulse contract emitted: 2026-07-22
Database migration: not required
Production deployment pending
/dialogue/qa production regression pending
```

## Delivered

- Successful booking create emits timezone-aware `starts_at` and `ends_at`.
- Successful booking reschedule emits the new end time and duration.
- `duration_minutes` comes from the authoritative selected service catalog item.
- Cancellation includes Calendar end time and duration when available.
- Existing transactional outbox, immutable payload, signing, retry, ordering and tenant isolation remain intact.
- Stage 35 synthetic Calendar QA traffic remains excluded from the production Pulse outbox.

## Local test evidence

```text
Receptionist integration tests: 21 passed
Authoritative flow harness: create/reschedule/cancel passed
Regression matrix shape: 50 cases confirmed
Python compilation: passed
```

Production `/dialogue/qa 50/50` is intentionally not claimed until deployment.
