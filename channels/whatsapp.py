"""WhatsApp channel adapter."""

from fastapi.responses import Response


async def handle_whatsapp_incoming(request, runtime):
    form = await request.form()
    to_num = str(form.get("To", "")).replace("whatsapp:", "")
    from_num = str(form.get("From", ""))
    body = str(form.get("Body", "")).strip()

    tenant = runtime["resolve_tenant_for_incoming"](to_num)
    runtime["log_tenant_resolution"]("whatsapp", to_num, tenant)
    if not runtime["tenant_is_resolved"](tenant):
        runtime["send_message"](
            from_num,
            runtime["t"](runtime["detect_language"](body), "service_unavailable_text"),
        )
        return Response(status_code=204)

    result = runtime["handle_user_text_with_logging"](
        tenant["_id"], from_num, body, "whatsapp", runtime["detect_language"](body)
    )
    biz = runtime["tenant_settings"](tenant, result["lang"])["biz_name"]
    runtime["send_message"](from_num, f"{biz}: {result['msg_out']}")
    return Response(status_code=204)
