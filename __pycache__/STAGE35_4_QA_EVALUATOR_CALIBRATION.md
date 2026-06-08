# Stage 35.4 — QA Evaluator Calibration

Purpose: calibrate the Stage 35 regression evaluator without changing production booking/orchestration logic.

Changes:
- Detects earlier/later refinement by comparing offered slot windows between turns.
- Treats fuzzy evening/after-time windows as valid when multiple windowed options are offered.
- Correctly handles soft confirmation flows where a positive response after slot options selects the first slot and moves to `AWAITING_CONFIRM` instead of finalizing immediately.
- Prevents false `confirm_loop` failures for expected slot-confirmation prompts.
- Keeps `calendar_safe_mode` behavior from Stage 35.3.

Expected result: fewer false failures in `/dialogue/qa` while preserving real regression detection.
