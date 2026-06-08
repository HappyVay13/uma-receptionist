# Stage 38.2 — Price FAQ Inline Answer

Goal: when a client asks price during an active booking flow, Repliq must answer the price first and then preserve the booking context.

Fixes:
- `cik tas maksā?`
- `cik maksā konsultācija?`
- `сколько стоит?`
- `how much does it cost?`

Expected behavior:
- answer price from business memory/service config;
- keep current booking context;
- remind available slots;
- do not reset to AWAITING_DATE;
- do not ask service again.
