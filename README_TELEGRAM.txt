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
