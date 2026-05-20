# Repliq Project State

Current stage: Stage 36 — Advanced Conversation Recovery.

Baseline preserved:
- Stage 24 parser/offered-slot/no-confirm hotfixes
- Stage 30 after-time negotiation window
- Stage 31 fuzzy scheduling intelligence
- Stage 32 contextual refinement memory
- Stage 33 soft conversational UX
- Stage 34 regression matrix
- Stage 35 QA runner with clinic_demo + calendar-safe mode + calibrated evaluator

Stage 36 adds a deterministic recovery layer inside active booking flows. It is designed to preserve existing orchestration and avoid resetting the conversation when the user gives incomplete, hesitant, or corrective answers.
