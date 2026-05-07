"""Unified outbound messaging for Repliq channels.

This module is intentionally small: it does not contain booking logic or
conversation logic. It only routes outbound text to the correct transport.

Current supported transports:
- sms / whatsapp / voice fallback via Twilio client
- telegram via Telegram Bot API
- dev / webchat are no-op style transports for internal flows
"""

import logging
from typing import Any, Dict, Optional

log = logging.getLogger("repliq.messaging")


def normalize_channel(channel: str) -> str:
    ch = (channel or "").strip().lower()
    aliases = {
        "wa": "whatsapp",
        "whats_app": "whatsapp",
        "tg": "telegram",
        "text": "sms",
        "twilio_sms": "sms",
        "twilio_whatsapp": "whatsapp",
    }
    return aliases.get(ch, ch or "unknown")


def channel_supports_outbound_messaging(channel: str) -> bool:
    return normalize_channel(channel) in {"sms", "whatsapp", "telegram", "webchat", "dev", "voice"}


def send_channel_message(
    channel: str,
    to: Any,
    text: str,
    tenant_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Send a message through the selected channel.

    Returns a small normalized result dict. Exceptions are swallowed and logged
    so channel failures do not crash webhook handlers.
    """
    ch = normalize_channel(channel)
    body = (text or "").strip() or "..."
    metadata = metadata or {}

    try:
        if ch in {"sms", "whatsapp", "voice"}:
            from integrations.twilio_client import send_message as twilio_send_message

            twilio_send_message(str(to), body)
            return {"ok": True, "channel": ch, "to": str(to), "tenant_id": tenant_id}

        if ch == "telegram":
            from channels.telegram import telegram_send_message

            return telegram_send_message(to, body)

        if ch in {"dev", "webchat"}:
            log.info(
                "send_channel_message_noop channel=%s tenant_id=%s to=%s text_preview=%s",
                ch,
                tenant_id or "",
                to,
                body[:120],
            )
            return {"ok": True, "channel": ch, "noop": True, "tenant_id": tenant_id}

        log.warning("send_channel_message_unsupported channel=%s tenant_id=%s", ch, tenant_id or "")
        return {"ok": False, "channel": ch, "error": "unsupported_channel", "tenant_id": tenant_id}

    except Exception as exc:
        log.exception("send_channel_message_failed channel=%s tenant_id=%s to=%s", ch, tenant_id or "", to)
        return {"ok": False, "channel": ch, "error": str(exc), "tenant_id": tenant_id}
