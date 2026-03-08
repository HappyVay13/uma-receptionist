# -------------------------
# CALENDAR LOGIC (Search/Reschedule/Cancel)
# -------------------------
def in_business_hours(dt_start: datetime, duration_min: int, work_start: str, work_end: str) -> bool:
    try:
        ws_h, ws_m = _parse_hhmm(work_start)
        we_h, we_m = _parse_hhmm(work_end)
        day_start = dt_start.replace(hour=ws_h, minute=ws_m, second=0, microsecond=0)
        day_end = dt_start.replace(hour=we_h, minute=we_m, second=0, microsecond=0)
        return dt_start >= day_start and (dt_start + timedelta(minutes=duration_min)) <= day_end
    except: return False

def find_next_two_slots(calendar_id: str, dt_start: datetime, duration_min: int, work_start: str, work_end: str):
    step, found = 30, []
    candidate = dt_start + timedelta(minutes=step)
    for _ in range(48): # Ищем в пределах 24 часов
        if in_business_hours(candidate, duration_min, work_start, work_end):
            if not is_slot_busy(calendar_id, candidate, candidate + timedelta(minutes=duration_min)):
                found.append(candidate)
                if len(found) == 2: return found[0], found[1]
        candidate += timedelta(minutes=step)
    return None

def find_next_event_by_phone(calendar_id: str, phone: str):
    svc = get_gcal()
    if not (svc and calendar_id): return None
    now = now_ts().isoformat()
    try:
        events = svc.events().list(calendarId=calendar_id, timeMin=now, singleEvents=True, orderBy="startTime", maxResults=15).execute()
        for ev in events.get("items", []):
            if phone in (ev.get("description") or ""): return ev
    except: pass
    return None

def delete_calendar_event(calendar_id: str, event_id: str):
    svc = get_gcal()
    if svc and calendar_id:
        try: svc.events().delete(calendarId=calendar_id, eventId=event_id).execute(); return True
        except: return False
    return False

# -------------------------
# TTS LOGIC
# -------------------------
_TTS = None
def get_google_tts():
    global _TTS
    if _TTS: return _TTS
    if not GOOGLE_SERVICE_ACCOUNT_JSON: return None
    info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    _TTS = build("texttospeech", "v1", credentials=creds, cache_discovery=False)
    return _TTS

def google_tts_mp3(text_in: str, lang_code: str, voice_name: str) -> bytes:
    svc = get_google_tts()
    if not (svc and text_in): return b""
    body = {"input": {"text": text_in[:300]}, "voice": {"languageCode": lang_code, "name": voice_name}, "audioConfig": {"audioEncoding": "MP3"}}
    resp = svc.text().synthesize(body=body).execute()
    return base64.b64decode(resp["audioContent"])

@app.get("/tts/google")
def tts_google(text: str):
    audio = google_tts_mp3(text, GOOGLE_TTS_LANGUAGE_CODE, GOOGLE_TTS_VOICE_NAME)
    return StreamingResponse(iter([audio]), media_type="audio/mpeg")

def say_or_play(vr: VoiceResponse, text_in: str, lang: str):
    t = (text_in or "").strip()
    if not t: return
    lang = get_lang(lang)
    if lang == "lv" and SERVER_BASE_URL:
        vr.play(f"{SERVER_BASE_URL}/tts/google?text={urllib.parse.quote_plus(t)}")
    else:
        vr.say(t, language=stt_locale_for_lang(lang))

# -------------------------
# CORE HANDLER: handle_user_text
# -------------------------
def handle_user_text(tenant_id: str, raw_phone: str, text_in: str, channel: str, lang_hint: str) -> Dict[str, Any]:
    tenant = get_tenant(tenant_id)
    allowed, _ = tenant_allowed(tenant)
    l_hint = get_lang(lang_hint)
    
    if not allowed:
        return {"status": "blocked", "reply_voice": "Atvainojiet, serviss nav pieejams.", "msg_out": "Serviss nav pieejams.", "lang": l_hint}

    user_key = norm_user_key(raw_phone)
    c = db_get_or_create_conversation(tenant_id, user_key, l_hint)
    lang = c["lang"]
    settings = tenant_settings(tenant, lang)

    # 1. AI Extraction
    system = f"Receptionist for {settings['biz_name']}. Hours: {settings['work_start']}-{settings['work_end']}. Services: {settings['services_hint']}. Return JSON: service, datetime_iso, name."
    ai_data = openai_chat_json(system, f"User: {text_in}. Today: {now_ts().date()}.")
    
    # 2. Update conversation state
    if ai_data.get("service"): c["service"] = ai_data["service"]
    if ai_data.get("name"): c["name"] = ai_data["name"]
    dt_target = parse_dt_any_tz(ai_data.get("datetime_iso")) or parse_dt_any_tz(c.get("datetime_iso"))
    
    # 3. Validation Logic
    if not c["service"]:
        return {"status": "need_more", "reply_voice": "Kādu pakalpojumu vēlaties?", "msg_out": "Kādu pakalpojumu vēlaties?", "lang": lang}
    if not dt_target:
        return {"status": "need_more", "reply_voice": "Kad un cikos?", "msg_out": "Kad и cikos?", "lang": lang}
    
    # 4. Availability Check
    if is_slot_busy(settings["calendar_id"], dt_target, dt_target + timedelta(minutes=APPT_MINUTES)):
        opts = find_next_two_slots(settings["calendar_id"], dt_target, APPT_MINUTES, settings["work_start"], settings["work_end"])
        if opts:
            c["pending"] = {"opt1": opts[0].isoformat(), "opt2": opts[1].isoformat()}
            db_save_conversation(tenant_id, user_key, c)
            return {"status": "busy", "reply_voice": "Laiks aizņemts. Nosūtu variantus.", "msg_out": f"Aizņemts. Varianti: 1) {opts[0].strftime('%H:%M')} 2) {opts[1].strftime('%H:%M')}", "lang": lang}

    # 5. Book
    create_calendar_event(settings["calendar_id"], dt_target, APPT_MINUTES, f"{c['service']} ({c['name']})", f"Phone: {raw_phone}")
    c["state"] = "BOOKED"
    db_save_conversation(tenant_id, user_key, c)
    return {"status": "booked", "reply_voice": "Paldies, pieraksts apstiprināts!", "msg_out": f"Apstiprināts: {dt_target.strftime('%H:%M')}", "lang": lang}

# -------------------------
# ENDPOINTS (Final)
# -------------------------
@app.post("/voice/incoming")
async def voice_incoming(request: Request):
    form = await request.form()
    to_num = str(form.get("To", ""))
    tenant = get_tenant_by_phone(to_num)
    biz = tenant_settings(tenant, "lv")["biz_name"]
    
    vr = VoiceResponse()
    g = Gather(input="speech", action="/voice/intent", method="POST", timeout=7, language="lv-LV")
    say_or_play(g, f"Labdien! Jūs sazvanījāt {biz}. Kā varu palīdzēt?", "lv")
    vr.append(g)
    return twiml(vr)

@app.post("/voice/intent")
async def voice_intent(request: Request):
    form = await request.form()
    to_num, caller = str(form.get("To", "")), normalize_voice_caller(str(form.get("From", "")))
    speech = str(form.get("SpeechResult", "")).strip()
    
    tenant = get_tenant_by_phone(to_num)
    result = handle_user_text(tenant["_id"], caller, speech, "voice", "lv")
    
    vr = VoiceResponse()
    say_or_play(vr, result["reply_voice"], result["lang"])
    if result["status"] == "need_more":
        vr.append(Gather(input="speech", action="/voice/intent", timeout=7, language="lv-LV"))
    else: vr.hangup()
    return twiml(vr)

@app.post("/sms/incoming")
async def sms_incoming(request: Request):
    form = await request.form()
    to_num, from_num, body = str(form.get("To", "")), str(form.get("From", "")), str(form.get("Body", "")).strip()
    tenant = get_tenant_by_phone(to_num)
    result = handle_user_text(tenant["_id"], from_num, body, "sms", "lv")
    send_message(from_num, result["msg_out"])
    return Response(status_code=204)

@app.post("/whatsapp/incoming")
async def whatsapp_incoming(request: Request):
    form = await request.form()
    to_num = str(form.get("To", "")).replace("whatsapp:","")
    from_num, body = str(form.get("From", "")), str(form.get("Body", "")).strip()
    tenant = get_tenant_by_phone(to_num)
    result = handle_user_text(tenant["_id"], from_num, body, "whatsapp", "lv")
    send_message(from_num, result["msg_out"])
    return Response(status_code=204)

@app.on_event("startup")
def _startup(): ensure_tenant_row(TENANT_ID_DEFAULT)
