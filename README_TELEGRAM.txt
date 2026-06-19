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

Stage 59 readiness:
- GET /telegram/readiness?tenant_id=clinic_demo
- GET /channels/telegram/readiness?tenant_id=clinic_demo

The readiness endpoint is read-only. It does not call Telegram APIs or set webhooks. It reports whether Telegram text channel config is ready for a controlled pilot smoke test.
