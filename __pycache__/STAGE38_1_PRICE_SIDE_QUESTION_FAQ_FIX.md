# Stage 38.1 — Price Side-question FAQ Fix

## Goal
Fix price side-questions inside an active booking flow without resetting the scheduling context.

## Fixed
- `cik tas maksā?`
- `cik maksā konsultācija?`
- `сколько стоит?`
- `how much does it cost?`

## Behavior
When the user asks a price question during booking, Repliq now:
- answers from business memory/service context;
- uses the already selected service if the user says “it/this” instead of repeating the service name;
- preserves booking flow;
- returns to slot/confirmation flow instead of resetting to date selection.

## Safety
No calendar booking logic was changed.
