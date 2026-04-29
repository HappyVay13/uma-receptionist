import logging
from typing import Optional

from twilio.rest import Client as TwilioClient

from config.settings import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_FROM_NUMBER,
    TWILIO_WHATSAPP_FROM,
)

log = logging.getLogger("repliq")


def twilio_client() -> Optional[TwilioClient]:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        return None
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_message(to_number: str, body: str):
    client = twilio_client()
    if not client:
        log.warning("Twilio client not configured; message skipped")
        return

    to_number = (to_number or "").strip()
    is_wa = to_number.startswith("whatsapp:")
    from_number = TWILIO_WHATSAPP_FROM if is_wa else TWILIO_FROM_NUMBER
    if not from_number:
        log.warning("Twilio from number missing; message skipped")
        return

    try:
        client.messages.create(from_=from_number, to=to_number, body=body)
    except Exception as e:
        log.error("Twilio send error: %s", e)
