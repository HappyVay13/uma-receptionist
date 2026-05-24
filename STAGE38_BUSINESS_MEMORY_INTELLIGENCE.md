# Stage 38 — Business Memory Intelligence / FAQ Rules Hardening

## Goal
Make Repliq answer business questions more safely and keep the booking flow alive when a user asks side questions during scheduling.

## Added
- Generic FAQ/business-memory handling across tenant business types, not only barbershop.
- Business hours answers from tenant settings or memory.
- Location answers from tenant settings.
- Service/price/duration answers with safer fallbacks.
- Side-question preservation inside active booking flows.
- Regression coverage for FAQ during booking and standalone business questions.

## Safety contract
- Booking orchestration remains authoritative.
- FAQ answers do not create bookings.
- Active booking flow is preserved after a business side-question.
- Unknown prices are not hallucinated; the assistant asks to clarify service or says to confirm with the business.
