# Stage 59.1 — Telegram Text Channel Language/Menu Hardening

## Scope
Stage 59.1 fixes Telegram-channel UX issues discovered during live Telegram smoke after Stage 59 readiness was green.

The active MVP remains text-first receptionist behavior. Voice/calls remain future scope.

## Factual trigger
Live Telegram smoke showed:
- Telegram webhook was installed and bot responded.
- Telegram counters increased / already had activity.
- RU booking flow could switch to LV after short replies such as slot choice `2` and confirmation `Да`.
- The old persistent LV reply keyboard (`Jauns pieraksts`, `Mani pieraksti`, etc.) created a separate menu-routing layer and caused UX/state issues.
- A Telegram reply exposed raw internal memory label text such as `business_memory_lv:`.

## What changed
- Disabled the old persistent Telegram reply keyboard for MVP free-text mode.
- `/start` and help now send simple text instructions with `remove_keyboard`.
- Telegram replies now always remove old persistent keyboards instead of attaching the old menu.
- Short neutral replies (`2`, bare HH:MM times, `да`, `jā`, `ok`, etc.) return an empty language hint so the core can preserve the active conversation language.
- Old LV menu button texts are handled defensively, but are not required for the MVP.
- Added Telegram outgoing-text guard against internal prompt/config labels such as `business_memory_lv:`.
- Added an AI response composer guard that rejects composed replies containing internal prompt/config labels.
- `/telegram/readiness` now reports `stage = 59.1` and includes `stage59_1_hardening` metadata.

## What did not change
- Booking routing.
- Slot generation.
- Date/time parsing.
- Price side-question handling.
- Confirmation finalization.
- Cancellation.
- Reschedule.
- Google Calendar create/update/delete runtime actions.
- Regression evaluator.
- Voice/call runtime.

## Expected production result
After deploy:
- `/dialogue/qa` remains `50/50 passed`.
- `/internal/readiness?tenant_id=clinic_demo` includes `telegram_text_channel_readiness.stage = 59.1`.
- `/telegram/readiness?tenant_id=clinic_demo` returns `status = ready` when Telegram env remains configured.
- `/telegram/readiness.stage59_1_hardening.legacy_reply_keyboard_disabled = true`.
- Telegram `/start` removes the old persistent menu.
- RU free-text Telegram smoke stays in RU after `2` and `Да`.
- Telegram does not show `business_memory_lv:` or similar internal labels to the customer.

## Manual smoke checklist
1. Redeploy Stage 59.1.
2. Run `/dialogue/qa` and confirm `50/50 passed`.
3. Open `/telegram/readiness?tenant_id=clinic_demo` and confirm `stage=59.1`.
4. Open Telegram bot and send `/start`; old menu should disappear.
5. Run RU free-text smoke:
   - `Хочу записаться на консультацию завтра вечером`
   - `Сколько это стоит?`
   - `2`
   - `Да`
   - `Хочу перенести запись`
   - `Послезавтра вечером`
   - `2`
   - `Да`
   - `Отменить запись`
6. Verify Google Calendar: one event after booking, same event after reschedule, no active event after cancel.
7. Confirm no raw `business_memory_*:` labels appear in Telegram replies.
