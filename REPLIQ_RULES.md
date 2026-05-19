# REPLIQ_RULES.md

Core principle:
LLM is the understanding layer only. Calendar actions and booking decisions are executed by orchestration/backend logic.

Conversational scheduling rules:
1. Exact time phrases like “в 14:00” may be treated as exact slot requests.
2. Window phrases like “после 14:00”, “вечером”, “после обеда”, “after work”, “pēc darba” must produce multiple available slots.
3. If a user rejects offered slots with “не так поздно”, “не так рано”, “чуть позже”, “чуть раньше”, the system must refine the current context, not restart the booking flow.
4. Rejected offered slots should not be repeated immediately.
5. The assistant should minimize unnecessary questions and preserve booking context.
6. Language must remain consistent with the user’s actual message.
7. Confirmation loops are forbidden: after a confirmed booking, state must exit to BOOKED.

Forbidden regressions:
- Treating “после 14:00” as exactly 14:00.
- Repeating the same confirmation after user says yes/no.
- Forgetting service/date/time during active booking flow.
- Random language switching.
- Creating duplicate calendar events from repeated confirmations.
