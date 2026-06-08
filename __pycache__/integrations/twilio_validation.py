import logging
from typing import Optional
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator

from config.settings import TWILIO_AUTH_TOKEN, TWILIO_VALIDATE_SIGNATURE

log = logging.getLogger("repliq")


def twilio_request_validator() -> Optional[RequestValidator]:
    if not (TWILIO_VALIDATE_SIGNATURE and TWILIO_AUTH_TOKEN):
        return None
    try:
        return RequestValidator(TWILIO_AUTH_TOKEN)
    except Exception as e:
        log.error("Twilio validator init failed: %s", e)
        return None


def should_validate_twilio_request(path: str) -> bool:
    p = (path or "").lower()

    # Browser / SDK endpoints must not require Twilio signature.
    if p.startswith("/voice/token"):
        return False

    # Real Twilio webhook endpoints.
    if (
        p.startswith("/voice/incoming")
        or p.startswith("/voice/language")
        or p.startswith("/voice/intent")
        or p.startswith("/sms")
        or p.startswith("/whatsapp")
    ):
        return True

    return False


def install_twilio_signature_middleware(app):
    @app.middleware("http")
    async def validate_twilio_signature_middleware(request: Request, call_next):
        if not should_validate_twilio_request(request.url.path):
            return await call_next(request)

        validator = twilio_request_validator()
        if validator is None:
            return await call_next(request)

        signature = request.headers.get("X-Twilio-Signature", "").strip()
        if not signature:
            log.warning("twilio_signature_missing path=%s", request.url.path)
            return Response(content="Invalid Twilio signature", status_code=403)

        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8", errors="ignore")
        parsed = parse_qs(body_text, keep_blank_values=True)
        form_data = {k: v[-1] if isinstance(v, list) and v else "" for k, v in parsed.items()}
        url = str(request.url)

        try:
            is_valid = validator.validate(url, form_data, signature)
        except Exception as e:
            log.error("twilio_signature_validation_error path=%s err=%s", request.url.path, e)
            return Response(content="Invalid Twilio signature", status_code=403)

        if not is_valid:
            log.warning("twilio_signature_invalid path=%s", request.url.path)
            return Response(content="Invalid Twilio signature", status_code=403)

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        request._receive = receive
        return await call_next(request)

    return validate_twilio_signature_middleware
