import logging
import os
import re
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional, Tuple

import requests
from fastapi import HTTPException, Request

log = logging.getLogger("repliq.telegram")

TELEGRAM_API_BASE = "https://api.telegram.org"

# Stage 68: tenant-level Telegram setup can temporarily override the env token/secret
# for one webhook request. Existing env-based Telegram runtime remains the fallback.
_TELEGRAM_BOT_TOKEN_OVERRIDE: ContextVar[str] = ContextVar("telegram_bot_token_override", default="")
_TELEGRAM_WEBHOOK_SECRET_OVERRIDE: ContextVar[str] = ContextVar("telegram_webhook_secret_override", default="")


def telegram_set_runtime_config(bot_token: str = "", webhook_secret: str = "") -> Tuple[Any, Any]:
    bot_ctx = _TELEGRAM_BOT_TOKEN_OVERRIDE.set((bot_token or "").strip())
    secret_ctx = _TELEGRAM_WEBHOOK_SECRET_OVERRIDE.set((webhook_secret or "").strip())
    return bot_ctx, secret_ctx


def telegram_reset_runtime_config(tokens: Tuple[Any, Any]) -> None:
    bot_ctx, secret_ctx = tokens
    _TELEGRAM_BOT_TOKEN_OVERRIDE.reset(bot_ctx)
    _TELEGRAM_WEBHOOK_SECRET_OVERRIDE.reset(secret_ctx)


TELEGRAM_REMOVE_KEYBOARD = {"remove_keyboard": True}


def _telegram_outgoing_text_without_internal_leaks(text: str) -> str:
    """Strip accidental internal prompt/memory labels from Telegram-visible text.

    Stage 59.1 guard: Telegram must never expose fields such as
    business_memory_lv:... to the customer. If a model/rewrite layer leaks an
    internal label before the actual follow-up question, keep the follow-up
    question and drop the leaked prefix.
    """
    body = str(text or "").strip()
    if not body:
        return body

    leak_pattern = re.compile(
        r"\b(?:business_memory(?:_[a-z]{2})?|faq(?:_[a-z]{2})?|booking_rules(?:_[a-z]{2})?|env_memory)\s*:",
        flags=re.IGNORECASE,
    )
    if not leak_pattern.search(body):
        return body

    # If the leaked memory prefix is followed by a normal next-question prompt,
    # preserve the next question and remove everything before it.
    prompt_markers = [
        "Uz kuru", "Kuru", "Pasakiet", "Labi", "Skaidrs",
        "На какой", "Какой", "Подскажите", "Хорошо", "Понял",
        "Which", "What day", "What date", "Sure", "Okay",
    ]
    marker_positions = [body.find(marker) for marker in prompt_markers if body.find(marker) > 0]
    if marker_positions:
        return body[min(marker_positions):].strip()

    cleaned = leak_pattern.sub("", body)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :-\n\t")
    return cleaned


def telegram_bot_token() -> str:
    override = (_TELEGRAM_BOT_TOKEN_OVERRIDE.get("") or "").strip()
    return override or (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


def telegram_webhook_secret() -> str:
    override = (_TELEGRAM_WEBHOOK_SECRET_OVERRIDE.get("") or "").strip()
    return override or (os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()


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


def telegram_api_url(method: str, bot_token: str = "") -> str:
    token = (bot_token or telegram_bot_token()).strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    return f"{TELEGRAM_API_BASE}/bot{token}/{method}"


def telegram_send_message(chat_id: Any, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    token = telegram_bot_token()
    if not token:
        log.error("telegram_send_message_failed reason=missing_token chat_id=%s", chat_id)
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN is not configured"}

    body = _telegram_outgoing_text_without_internal_leaks(text)
    if not body:
        body = "..."

    try:
        payload = {
            "chat_id": chat_id,
            "text": body[:3900],
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        response = requests.post(
            telegram_api_url("sendMessage"),
            json=payload,
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




# Stage 59.1: keep Telegram as a free-text channel for MVP.
# The old persistent LV reply keyboard is intentionally removed because it
# created a separate menu-routing layer and caused language/state drift.
TELEGRAM_MAIN_MENU = TELEGRAM_REMOVE_KEYBOARD


def telegram_send_main_menu(chat_id: Any, text: str = "Rakstiet brīvā tekstā, ko vēlaties izdarīt.") -> Dict[str, Any]:
    return telegram_send_message(chat_id, text, reply_markup=TELEGRAM_REMOVE_KEYBOARD)


def _telegram_help_text(lang: str = "") -> str:
    lang = (lang or "").strip().lower()
    if lang == "ru":
        return (
            "Repliq работает как текстовый администратор. Напишите обычным текстом, например: "
            "«Хочу записаться на консультацию завтра вечером»."
        )
    if lang == "en":
        return (
            "Repliq works as a text receptionist. Just write naturally, for example: "
            "I want to book a consultation tomorrow evening."
        )
    return (
        "Repliq darbojas kā teksta administrators. Rakstiet brīvā tekstā, piemēram: "
        "“Gribu pierakstīties uz konsultāciju rīt vakarā”."
        "\n\nМожно писать по-русски: «Хочу записаться на консультацию завтра вечером»."
    )


def _normalize_command_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _is_start_text(text: str) -> bool:
    return _normalize_command_text(text) in {"/start", "start"}


def _is_restart_text(text: str) -> bool:
    low = _normalize_command_text(text)
    return low in {
        "/reset", "reset", "restart",
        "📅 jauns pieraksts", "jauns pieraksts", "sākt jaunu pierakstu", "sakt jaunu pierakstu",
        "gribu jaunu pierakstu", "vēlos pierakstīties", "velos pierakstities",
        "новая запись", "хочу записаться", "записаться", "new booking", "book appointment",
    }


def _canonical_restart_message(text: str, lang_hint: str = "") -> str:
    low = _normalize_command_text(text)
    if low in {"новая запись", "хочу записаться", "записаться"}:
        return "хочу записаться"
    if low in {"new booking", "book appointment"}:
        return "i want to book an appointment"
    return "gribu pierakstīties"


def _is_help_text(text: str) -> bool:
    low = _normalize_command_text(text)
    return low in {"ℹ️ palīdzība", "palīdzība", "palidziba", "/help", "help", "помощь"}


def _is_my_bookings_text(text: str) -> bool:
    low = _normalize_command_text(text)
    return low in {"📋 mani pieraksti", "mani pieraksti", "my bookings", "мои записи"}


def _is_reschedule_text(text: str) -> bool:
    low = _normalize_command_text(text)
    return low in {"🔄 pārcelt pierakstu", "pārcelt pierakstu", "parcelt pierakstu", "перенести запись", "reschedule"}


def _is_cancel_text(text: str) -> bool:
    low = _normalize_command_text(text)
    return low in {"❌ atcelt pierakstu", "atcelt pierakstu", "отменить запись", "cancel booking"}


def _telegram_lang_hint(text: str, detect_language_func: Callable[[str], str]) -> str:
    low = _normalize_command_text(text)
    # Short acknowledgements, slot numbers and bare times are language-neutral.
    # Let the core keep the existing conversation language.
    if low in {"ok", "okay", "okej", "labi", "der", "jā", "ja", "да", "ага", "yes"}:
        return ""
    if low.isdigit() and len(low) <= 2:
        return ""
    if re.fullmatch(r"\d{1,2}[:.]\d{2}", low):
        return ""
    return detect_language_func(text)

def telegram_set_webhook_request(webhook_url: str, bot_token: str = "", webhook_secret: str = "") -> Dict[str, Any]:
    token = (bot_token or telegram_bot_token()).strip()
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN is not configured"}

    payload: Dict[str, Any] = {
        "url": (webhook_url or "").strip(),
        "drop_pending_updates": False,
        "allowed_updates": ["message", "edited_message", "callback_query"],
    }
    secret = (webhook_secret or telegram_webhook_secret()).strip()
    if secret:
        payload["secret_token"] = secret

    try:
        response = requests.post(telegram_api_url("setWebhook", bot_token=token), json=payload, timeout=20)
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


def telegram_get_webhook_info_request(bot_token: str = "") -> Dict[str, Any]:
    token = (bot_token or telegram_bot_token()).strip()
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN is not configured"}
    try:
        response = requests.get(telegram_api_url("getWebhookInfo", bot_token=token), timeout=20)
        data = response.json() if response.text else {}
        if response.status_code == 200 and data.get("ok"):
            result = data.get("result") if isinstance(data.get("result"), dict) else {}
            return {
                "ok": True,
                "telegram_response": data,
                "webhook_url": result.get("url"),
                "pending_update_count": result.get("pending_update_count"),
                "last_error_date": result.get("last_error_date"),
                "last_error_message": result.get("last_error_message"),
            }
        return {
            "ok": False,
            "status_code": response.status_code,
            "telegram_response": data or response.text[:500],
        }
    except Exception as exc:
        log.error("telegram_get_webhook_info_exception err=%s", exc)
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
    reset_conversation_func: Optional[Callable[[str, str], None]] = None,
    tenant_bot_token_func: Optional[Callable[[str], str]] = None,
    tenant_webhook_secret_func: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    runtime_tenant_id = (default_tenant_id or "").strip()
    bot_token = tenant_bot_token_func(runtime_tenant_id) if tenant_bot_token_func and runtime_tenant_id else ""
    webhook_secret = tenant_webhook_secret_func(runtime_tenant_id) if tenant_webhook_secret_func and runtime_tenant_id else ""
    ctx_tokens = telegram_set_runtime_config(bot_token or "", webhook_secret or "")
    try:
        return await _handle_telegram_incoming_with_config(
            request=request,
            default_tenant_id=default_tenant_id,
            get_tenant=get_tenant,
            tenant_is_resolved=tenant_is_resolved,
            tenant_settings_func=tenant_settings_func,
            handle_user_text_with_logging=handle_user_text_with_logging,
            detect_language_func=detect_language_func,
            unavailable_text_func=unavailable_text_func,
            reset_conversation_func=reset_conversation_func,
        )
    finally:
        telegram_reset_runtime_config(ctx_tokens)


async def _handle_telegram_incoming_with_config(
    request: Request,
    default_tenant_id: str,
    get_tenant: Callable[[str], Dict[str, Any]],
    tenant_is_resolved: Callable[[Dict[str, Any]], bool],
    tenant_settings_func: Callable[[Dict[str, Any], str], Dict[str, Any]],
    handle_user_text_with_logging: Callable[..., Dict[str, Any]],
    detect_language_func: Callable[[str], str],
    unavailable_text_func: Callable[[str], str],
    reset_conversation_func: Optional[Callable[[str, str], None]] = None,
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
        telegram_send_message(chat_id, "Lūdzu, atsūtiet ziņu tekstā.", reply_markup=TELEGRAM_REMOVE_KEYBOARD)
        return {"ok": True, "ignored": True, "reason": "empty_text"}

    tenant_id = (default_tenant_id or "").strip()
    tenant = get_tenant(tenant_id) if tenant_id else {}
    # Stage 59.1: do not force LV for neutral short replies such as "2" or "да".
    # Empty lang hint lets the core preserve the existing conversation language.
    lang = _telegram_lang_hint(text_in, detect_language_func)
    user_key = _extract_user_key(message, chat_id)

    if _is_start_text(text_in) or _is_help_text(text_in):
        if _is_start_text(text_in) and reset_conversation_func and tenant_id:
            try:
                reset_conversation_func(tenant_id, user_key)
            except Exception as exc:
                log.error("telegram_start_reset_failed tenant_id=%s user_key=%s err=%s", tenant_id, user_key, exc)
        telegram_send_message(chat_id, _telegram_help_text(lang), reply_markup=TELEGRAM_REMOVE_KEYBOARD)
        return {"ok": True, "tenant_id": tenant_id or None, "status": "text_help"}

    if _is_restart_text(text_in):
        if reset_conversation_func and tenant_id:
            try:
                reset_conversation_func(tenant_id, user_key)
            except Exception as exc:
                log.error("telegram_reset_failed tenant_id=%s user_key=%s err=%s", tenant_id, user_key, exc)
        text_in = _canonical_restart_message(text_in, lang)
        lang = _telegram_lang_hint(text_in, detect_language_func)

    if _is_my_bookings_text(text_in):
        telegram_send_message(
            chat_id,
            "Šajā MVP varu palīdzēt ar jaunu pierakstu, pārcelšanu vai atcelšanu. Rakstiet brīvā tekstā, ko vēlaties izdarīt.",
            reply_markup=TELEGRAM_REMOVE_KEYBOARD,
        )
        return {"ok": True, "tenant_id": tenant_id or None, "status": "my_bookings_not_supported_text_mvp"}
    elif _is_reschedule_text(text_in):
        text_in = "vēlos pārcelt pierakstu"
        lang = "lv"
    elif _is_cancel_text(text_in):
        text_in = "vēlos atcelt pierakstu"
        lang = "lv"

    if not tenant_is_resolved(tenant):
        telegram_send_message(chat_id, unavailable_text_func(lang or "lv"), reply_markup=TELEGRAM_REMOVE_KEYBOARD)
        return {"ok": True, "tenant_id": tenant_id or None, "status": "unavailable"}

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
        telegram_send_message(chat_id, unavailable_text_func(lang or "lv"), reply_markup=TELEGRAM_REMOVE_KEYBOARD)
        return {"ok": True, "tenant_id": tenant_id, "status": "core_error", "error": str(exc)}

    reply = str(result.get("msg_out") or result.get("reply_voice") or "").strip()
    if not reply:
        reply = unavailable_text_func(result.get("lang") or lang or "lv")

    if str(result.get("status") or "").strip().lower() in {"booked", "cancelled"}:
        telegram_send_message(chat_id, reply, reply_markup=TELEGRAM_REMOVE_KEYBOARD)
        if reset_conversation_func and tenant_id:
            try:
                reset_conversation_func(tenant.get("_id") or tenant_id, user_key)
            except Exception as exc:
                log.error("telegram_auto_reset_after_done_failed tenant_id=%s user_key=%s err=%s", tenant_id, user_key, exc)
    else:
        telegram_send_message(chat_id, reply, reply_markup=TELEGRAM_REMOVE_KEYBOARD)

    try:
        settings = tenant_settings_func(tenant, result.get("lang") or lang or "lv")
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
