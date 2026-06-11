# Stage 45.1 — Reschedule Slot Evaluator Calibration

## Baseline before Stage 45.1
- Stage 45 was deployed.
- User reported production `/dialogue/qa` = 40/44 passed.
- The four failed scenarios were exactly the new Stage 45 full reschedule scenarios:
  - `stage45_ru_reschedule_full_slot_ack_confirm`
  - `stage45_lv_reschedule_full_slot_ack_confirm`
  - `stage45_ru_reschedule_slot_number_confirm`
  - `stage45_lv_reschedule_slot_number_confirm`

## QA finding
The actual conversation behavior in all four failed scenarios reached the intended reschedule flow:

1. Existing appointment was found through the Stage 35 safe-mode calendar fixture.
2. `reschedule_event_id` was preserved.
3. The new fuzzy date/time was understood.
4. Multiple new slot options were shown.
5. Slot acknowledgement or numeric slot choice moved to confirmation.
6. Final confirmation completed through the existing booked/reschedule-finalized path.

The only missing evaluator token was:

```text
multiple_slot_options
```

## Root cause
The evaluator detected `multiple_slot_options` using the final assistant turn first:

```python
if len(last_times or times) >= 2:
    observed.add("multiple_slot_options")
```

In a full reschedule flow, the final assistant turn usually contains only one confirmed time, while the actual multiple slot options were correctly offered on an earlier turn. Because `last_times` was truthy with one time, the fallback to all conversation times was skipped.

## Change
Evaluator detection now checks each individual turn for multiple offered times:

```python
if any(len(_turn_times(t)) >= 2 for t in turns):
    observed.add("multiple_slot_options")
```

This uses the existing `_turn_times()` helper, which reads both visible assistant text and `pending.offered_slots`.

## Scope
- No conversational behavior changed.
- No booking routing changed.
- No cancellation/reschedule runtime logic changed.
- No calendar mutation logic changed.
- Only QA evaluator detection for an already-present multi-slot offer was corrected.

## Expected result after deploy

```text
/dialogue/qa = 44/44 passed
```
