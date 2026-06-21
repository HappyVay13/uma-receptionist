Repliq Telegram channel stage

Files:
- channels/telegram.py
- repliq/legacy_app.py

Required Render env var:
- TELEGRAM_BOT_TOKEN=<token from BotFather>

Recommended optional env vars:
- TELEGRAM_DEFAULT_TENANT_ID=clinic_demo
- TELEGRAM_WEBHOOK_SECRET=<random secret string>

After deploy:
1. Open /telegram/status
2. Set webhook:
   POST /telegram/set-webhook?tenant_id=clinic_demo
   or with explicit URL:
   POST /telegram/set-webhook?url=https://YOUR_RENDER_DOMAIN/telegram/webhook?tenant_id=clinic_demo

Telegram flow:
Telegram -> /telegram/webhook -> handle_user_text_with_logging -> Telegram sendMessage

Stage 59.1 MVP policy:
- Telegram is a free-text channel first.
- The old persistent LV reply keyboard is disabled/removed for MVP stability.
- /start sends text instructions and remove_keyboard.
- Short neutral replies such as 2, 10:00, ok, jā, да do not force Latvian; the core should preserve the active conversation language.
- Customer replies must not expose internal labels such as business_memory_lv: or faq_ru:.

Readiness:
- GET /telegram/readiness?tenant_id=clinic_demo
- GET /channels/telegram/readiness?tenant_id=clinic_demo

The readiness endpoint is read-only. It does not call Telegram APIs or set webhooks. It reports whether Telegram text channel config is ready for a controlled pilot smoke test and includes Stage 59.1 hardening metadata.


Stage 60 live smoke lock:
- GET /telegram/live-smoke/readiness?tenant_id=clinic_demo
- GET /telegram/smoke/readiness?tenant_id=clinic_demo
- GET /channels/telegram/live-smoke/readiness?tenant_id=clinic_demo

Stage 60 records the production Telegram smoke result after Stage 59.1 hardening was verified. It expects Telegram to stay as a free-text channel, preserve RU after short replies, keep the old LV reply keyboard disabled, and prevent raw business_memory labels from leaking.

The live-smoke lock endpoint is read-only. It does not call Telegram APIs, set webhooks, call LLMs, mutate tenant config, mutate conversations, or create/update/delete Google Calendar events.
