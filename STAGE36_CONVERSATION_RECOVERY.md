# Stage 36 — Advanced Conversation Recovery

Goal: make Repliq resilient to chaotic, incomplete, or corrective user messages inside booking flows.

Added:
- `stage36_advanced_recovery_if_needed(...)`
- uncertain answer handling: `не знаю`, `nezinu`, `not sure`
- availability recovery: `что есть`, `kas ir pieejams`, `what options`
- hold/pause handling: `подожди`, `pagaidi`, `wait`
- different day recovery: `не завтра`, `citu dienu`, `another day`
- different time recovery: `другое время`, `citu laiku`, `different time`
- context-slot offering from known booking context

Safety contract:
- no calendar actions are created directly by Stage 36
- no booking finalization is triggered by recovery alone
- service/date/time context is preserved unless user explicitly rejects it
- Stage 36 runs only inside active booking flow
