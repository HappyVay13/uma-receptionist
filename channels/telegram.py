import logging
import os
from typing import Any, Callable, Dict, Optional

import requests
from fastapi import HTTPException, Request

log = logging.getLogger("repliq.telegram")

TELEGRAM_API_BASE = "https://api.telegram.org"


def telegram_bot_token() -> str:
    return (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


def telegram_webhook_secret() -> str:
    return (os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()


def telegram_config_status(default_tenant_id: str = "", server_base_url: str = "") -> Dict[str, Any]:
    token = telegram_bot_token()
    secret = telegram_webhook_secret()
    recommended_webhook_url = ""
    if server_base_url:
        recommended_webhook_url = server_base_url.rstrip("/") + "/telegram/webhook"
        if default_tenant_id:
            recommended_webhook_url += f"?tenant_id={default_tenant_id}"
    return {
        "ok": True,
        "channel": "telegram",
        "configured": bool(token),
        "has_bot_token": bool(token),
        "has_webhook_secret": bool(secret),
        "default_tenant_id": default_tenant_id or None,
        "recommended_webhook_url": recommended_webhook_url or None,
    }


def telegram_api_url(method: str) -> str:
    token = telegram_bot_token()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    return f"{TELEGRAM_API_BASE}/bot{token}/{method}"


def telegram_send_message(chat_id: Any, text: str) -> Dict[str, Any]:
    token = telegram_bot_token()
    if not token:
        log.error("telegram_send_message_failed reason=missing_token chat_id=%s", chat_id)
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN is not configured"}

    body = (text or "").strip()
    if not body:
        body = "..."

    try:
        response = requests.post(
            telegram_api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": body[:3900],
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        if response.status_code == 200:
            return response.json()
        log.error(
            "telegram_send_message_failed status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        return {"ok": False, "status_code": response.status_code, "body": response.text[:500]}
    except Exception as exc:
        log.error("telegram_send_message_exception chat_id=%s err=%s", chat_id, exc)
        return {"ok": False, "error": str(exc)}


def telegram_set_webhook_request(webhook_url: str) -> Dict[str, Any]:
    token = telegram_bot_token()
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN is not configured"}

    payload: Dict[str, Any] = {
        "url": (webhook_url or "").strip(),
        "drop_pending_updates": False,
        "allowed_updates": ["message", "edited_message", "callback_query"],
    }
    secret = telegram_webhook_secret()
    if secret:
        payload["secret_token"] = secret

    try:
        response = requests.post(telegram_api_url("setWebhook"), json=payload, timeout=20)
        data = response.json() if response.text else {}
        if response.status_code == 200 and data.get("ok"):
            return {
                "ok": True,
                "webhook_url": payload["url"],
                "telegram_response": data,
                "uses_secret_token": bool(secret),
            }
        return {
            "ok": False,
            "status_code": response.status_code,
            "telegram_response": data or response.text[:500],
        }
    except Exception as exc:
        log.error("telegram_set_webhook_exception err=%s", exc)
        return {"ok": False, "error": str(exc)}


def _validate_telegram_secret(request: Request) -> None:
    required = telegram_webhook_secret()
    if not required:
        return
    received = (request.headers.get("X-Telegram-Bot-Api-Secret-Token") or "").strip()
    if received != required:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")


def _message_from_update(update: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(update, dict):
        return {}
    if isinstance(update.get("message"), dict):
        return update["message"]
    if isinstance(update.get("edited_message"), dict):
        return update["edited_message"]
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        msg = callback.get("message") if isinstance(callback.get("message"), dict) else {}
        data = str(callback.get("data") or "").strip()
        if data and msg:
            msg = dict(msg)
            msg["text"] = data
            msg["_callback_query_id"] = callback.get("id")
            msg["from"] = callback.get("from") or msg.get("from")
            return msg
    return {}


def _extract_chat_id(message: Dict[str, Any]) -> Optional[Any]:
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    return chat.get("id")


def _extract_user_key(message: Dict[str, Any], chat_id: Any) -> str:
    user = message.get("from") if isinstance(message.get("from"), dict) else {}
    user_id = user.get("id") or chat_id
    username = str(user.get("username") or "").strip()
    if username:
        return f"telegram:{user_id}:{username}"
    return f"telegram:{user_id}"


def _extract_text(message: Dict[str, Any]) -> str:
    text = str(message.get("text") or "").strip()
    if text:
        return text
    caption = str(message.get("caption") or "").strip()
    if caption:
        return caption
    return ""


async def handle_telegram_incoming(
    request: Request,
    default_tenant_id: str,
    get_tenant: Callable[[str], Dict[str, Any]],
    tenant_is_resolved: Callable[[Dict[str, Any]], bool],
    tenant_settings_func: Callable[[Dict[str, Any], str], Dict[str, Any]],
    handle_user_text_with_logging: Callable[..., Dict[str, Any]],
    detect_language_func: Callable[[str], str],
    unavailable_text_func: Callable[[str], str],
) -> Dict[str, Any]:
    _validate_telegram_secret(request)

    if not telegram_bot_token():
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN is not configured")

    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Telegram JSON update")

    message = _message_from_update(update)
    if not message:
        return {"ok": True, "ignored": True, "reason": "unsupported_update"}

    chat_id = _extract_chat_id(message)
    if chat_id is None:
        return {"ok": True, "ignored": True, "reason": "missing_chat_id"}

    text_in = _extract_text(message)
    if not text_in:
        telegram_send_message(chat_id, "Lūdzu, atsūtiet ziņu tekstā.")
        return {"ok": True, "ignored": True, "reason": "empty_text"}

    tenant_id = (default_tenant_id or "").strip()
    tenant = get_tenant(tenant_id) if tenant_id else {}
    lang = detect_language_func(text_in)

    if not tenant_is_resolved(tenant):
        telegram_send_message(chat_id, unavailable_text_func(lang))
        return {"ok": True, "tenant_id": tenant_id or None, "status": "unavailable"}

    user_key = _extract_user_key(message, chat_id)

    try:
        result = handle_user_text_with_logging(
            tenant_id=tenant.get("_id") or tenant_id,
            raw_phone=user_key,
            text_in=text_in,
            channel="telegram",
            lang_hint=lang,
            source="telegram",
        )
    except Exception as exc:
        log.exception("telegram_core_failed tenant_id=%s chat_id=%s", tenant_id, chat_id)
        telegram_send_message(chat_id, unavailable_text_func(lang))
        return {"ok": True, "tenant_id": tenant_id, "status": "core_error", "error": str(exc)}

    reply = str(result.get("msg_out") or result.get("reply_voice") or "").strip()
    if not reply:
        reply = unavailable_text_func(result.get("lang") or lang)

    telegram_send_message(chat_id, reply)

    try:
        settings = tenant_settings_func(tenant, result.get("lang") or lang)
        business_name = settings.get("biz_name")
    except Exception:
        business_name = None

    return {
        "ok": True,
        "tenant_id": tenant.get("_id") or tenant_id,
        "channel": "telegram",
        "business_name": business_name,
        "chat_id": chat_id,
        "status": result.get("status"),
    }
