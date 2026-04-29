"""Voice channel adapter for Twilio Voice.

The endpoint-specific TwiML and Voice SDK token logic lives here.
Core tenant resolution, dialog handling, TTS and persistence are still
injected from legacy_app during the staged refactor.
"""

import re
from fastapi import HTTPException
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse, Gather


async def handle_voice_incoming(request, runtime):
    form = await request.form()
    to_num = str(form.get("To", ""))
    caller = runtime["normalize_voice_caller"](str(form.get("From", "")))
    tenant = runtime["resolve_voice_tenant_for_incoming"](to_num, caller)
    runtime["log_tenant_resolution"]("voice", to_num, tenant)
    if not runtime["tenant_is_resolved"](tenant):
        vr = VoiceResponse()
        runtime["say_or_play"](vr, runtime["t"]("lv", "service_unavailable_voice"), "lv")
        vr.hangup()
        return runtime["twiml"](vr)

    biz = runtime["tenant_settings"](tenant, "lv")["biz_name"]
    c = runtime["db_get_or_create_conversation"](tenant["_id"], caller, "lv")
    lang = runtime["get_lang"](c.get("lang")) if caller != "unknown" else "lv"

    vr = VoiceResponse()
    g = Gather(
        input="speech dtmf",
        action="/voice/language",
        method="POST",
        timeout=7,
        speech_timeout="auto",
        num_digits=1,
        language=runtime["stt_locale_for_lang"](lang),
    )
    runtime["say_or_play"](g, runtime["t"](lang, "greeting", biz=biz), lang)
    vr.append(g)
    runtime["say_or_play"](vr, runtime["t"](lang, "voice_fallback"), lang)
    return runtime["twiml"](vr)


async def handle_voice_language(request, runtime):
    form = await request.form()
    to_num = str(form.get("To", ""))
    caller = runtime["normalize_voice_caller"](str(form.get("From", "")))
    speech = str(form.get("SpeechResult", "")).strip()
    digits = str(form.get("Digits", "")).strip()

    tenant = runtime["resolve_voice_tenant_for_incoming"](to_num, caller)
    runtime["log_tenant_resolution"]("voice_language", to_num, tenant)
    if not runtime["tenant_is_resolved"](tenant):
        vr = VoiceResponse()
        runtime["say_or_play"](vr, runtime["t"]("lv", "service_unavailable_voice"), "lv")
        vr.hangup()
        return runtime["twiml"](vr)

    c = runtime["db_get_or_create_conversation"](tenant["_id"], caller, "lv")
    selected_lang = runtime["detect_language_choice"](speech, digits) or runtime["get_lang"](c.get("lang"))
    c["lang"] = selected_lang
    runtime["db_save_conversation"](tenant["_id"], caller, c)

    vr = VoiceResponse()
    g = Gather(
        input="speech",
        action="/voice/intent",
        method="POST",
        timeout=7,
        speech_timeout="auto",
        language=runtime["stt_locale_for_lang"](selected_lang),
    )
    runtime["say_or_play"](g, runtime["t"](selected_lang, "how_help"), selected_lang)
    vr.append(g)
    runtime["say_or_play"](vr, runtime["t"](selected_lang, "voice_fallback"), selected_lang)
    return runtime["twiml"](vr)


async def handle_voice_intent(request, runtime):
    form = await request.form()
    to_num = str(form.get("To", ""))
    caller = runtime["normalize_voice_caller"](str(form.get("From", "")))
    speech = str(form.get("SpeechResult", "")).strip()

    tenant = runtime["resolve_voice_tenant_for_incoming"](to_num, caller)
    runtime["log_tenant_resolution"]("voice_intent", to_num, tenant)
    if not runtime["tenant_is_resolved"](tenant):
        vr = VoiceResponse()
        runtime["say_or_play"](vr, runtime["t"]("lv", "service_unavailable_voice"), "lv")
        vr.hangup()
        return runtime["twiml"](vr)

    c = runtime["db_get_or_create_conversation"](tenant["_id"], caller, runtime["detect_language"](speech))
    lang = runtime["resolve_reply_language"](speech, c.get("lang") or runtime["detect_language"](speech))
    result = runtime["handle_user_text_with_logging"](tenant["_id"], caller, speech, "voice", lang)

    vr = VoiceResponse()
    runtime["say_or_play"](vr, result["reply_voice"], result["lang"])
    if result["status"] in ("need_more", "reschedule_wait", "greeting", "identity", "info"):
        g = Gather(
            input="speech",
            action="/voice/intent",
            method="POST",
            timeout=7,
            speech_timeout="auto",
            language=runtime["stt_locale_for_lang"](result["lang"]),
        )
        runtime["say_or_play"](g, runtime["gather_followup_prompt"](result), result["lang"])
        vr.append(g)
        runtime["say_or_play"](vr, runtime["t"](result["lang"], "voice_fallback"), result["lang"])
    else:
        vr.hangup()

    if (
        result["status"] in ("booked", "busy", "cancelled")
        and caller != "unknown"
        and runtime["channel_supports_messaging"]("voice", caller)
    ):
        biz_name = runtime["tenant_settings"](tenant, result["lang"])["biz_name"]
        runtime["send_message"](caller, f"{biz_name}: {result['msg_out']}")

    return runtime["twiml"](vr)


def build_voice_token_payload(client_id: str, tenant_id: str, runtime):
    if not (
        runtime["TWILIO_ACCOUNT_SID"]
        and runtime["TWILIO_API_KEY_SID"]
        and runtime["TWILIO_API_KEY_SECRET"]
        and runtime["TWILIO_TWIML_APP_SID"]
    ):
        raise HTTPException(status_code=500, detail="Twilio Voice SDK config missing")

    clean_client_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", (client_id or "default")).strip("_") or "default"
    clean_tenant_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", (tenant_id or "")).strip("_")
    identity = f"tenant__{clean_tenant_id}__{clean_client_id}" if clean_tenant_id else clean_client_id

    token = AccessToken(
        runtime["TWILIO_ACCOUNT_SID"],
        runtime["TWILIO_API_KEY_SID"],
        runtime["TWILIO_API_KEY_SECRET"],
        identity=identity,
    )
    grant = VoiceGrant(
        outgoing_application_sid=runtime["TWILIO_TWIML_APP_SID"],
        incoming_allow=True,
    )
    token.add_grant(grant)
    return {"token": token.to_jwt(), "identity": identity, "tenant_id": clean_tenant_id or None}
