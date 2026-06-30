# Stage 84 — Service Catalog / Business Memory Consistency Guard

Status: implemented in archive, awaiting deploy verification.

## Purpose

Stage 84 adds a read-only consistency guard between the owner-managed service catalog and Business Memory / FAQ content.

The rule is explicit:

- Service Catalog is the source of truth for services, durations and prices.
- Business Memory is contextual knowledge: policies, exceptions, address, FAQ, booking rules and explanatory text.
- The managed block between `# Repliq service catalog prices` and `# /Repliq service catalog prices` is generated from the service catalog and may be used by the receptionist for price facts.
- Manual price lines outside the managed block are allowed, but they are checked and surfaced as attention/warnings when they conflict with catalog prices or duplicate them.

## Added endpoints

Admin-protected readiness endpoints:

- `GET /service-memory/consistency/readiness`
- `GET /catalog-memory/consistency/readiness`
- `GET /price-consistency/readiness`
- `GET /workspace/price-consistency/readiness`

Owner-safe read-only endpoints:

- `GET /owner/price-consistency`
- `GET /owner/price-consistency/ui`
- `GET /owner/catalog-memory-consistency`
- `GET /owner/catalog-memory-consistency/ui`

## What it checks

- Current catalog price lines by language.
- Managed price block presence and sync state in `business_memory_lv`, `business_memory_ru`, and `business_memory_en`.
- Manual price-like lines outside the managed block.
- Manual lines that conflict with matching service catalog prices.
- Manual lines that duplicate service catalog prices.
- Manual price-like lines that do not map to a known active catalog service.

## Expected behavior

The guard reports:

- `service_catalog_memory_consistency_ready=true` when the guard infrastructure, route protection and tenant catalog/memory model are available.
- `price_consistency_clean=true` only when there are no hard price conflicts and managed blocks are in sync with the service catalog.
- `status=attention` when manual Business Memory price text needs cleanup, while route/security infrastructure remains ready.

## Security

- Readiness routes are protected by Stage 61/62 admin auth.
- Owner routes are protected by Stage 71 owner session and tenant binding.
- No write endpoint is added in Stage 84.
- No auto-delete or automatic rewriting of owner Business Memory is performed.
- No raw admin tokens, owner login codes, magic tokens, CSRF secrets, raw IPs, subject hashes, Telegram tokens, Google credentials or other tenant secrets are exposed.

## Not changed

Receptionist core was not changed. Booking routing, slots, date/time parsing, price side-question logic, confirmation, cancellation, rescheduling, Google Calendar event runtime, Telegram webhook runtime, billing semantics, CSRF semantics, abuse/rate-limit semantics, magic-link semantics, dialogue QA evaluator, LLM orchestration, and voice/calls were not changed.

## Deploy verification checklist

- Render deploy starts successfully.
- `/dialogue/qa` = 50/50 passed.
- `/service-memory/consistency/readiness?tenant_id=clinic_demo` returns `stage=84`.
- `/catalog-memory/consistency/readiness?tenant_id=clinic_demo`, `/price-consistency/readiness?tenant_id=clinic_demo`, and `/workspace/price-consistency/readiness?tenant_id=clinic_demo` work and remain admin-protected.
- `/owner/price-consistency/ui?tenant_id=<owner_tenant>` opens with a valid owner session or super-admin bypass.
- `/owner/business-memory?tenant_id=<owner_tenant>` includes `price_consistency` metadata.
- `/owner/business-memory/ui?tenant_id=<owner_tenant>` shows price consistency status.
- Owner services, memory, workspace, dashboard, and billing remain OK.
- Stage 78 remains the source of truth for `public_saas_ready`.
- `enterprise_saas_ready=false` remains explicit.
