from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

import requests

log = logging.getLogger("repliq.intent_parser")

ORCH_ACTION_CONTINUE = "continue_legacy"
ORCH_ACTION_FAQ = "faq"
ORCH_ACTION_GREET = "greet"
ORCH_ACTION_IDENTITY = "identity"
ORCH_ACTION_HOURS = "hours"
ORCH_ACTION_START_BOOKING = "start_booking"
ORCH_ACTION_CANCEL = "cancel"
ORCH_ACTION_RESCHEDULE = "reschedule"
ORCH_ACTION_ASK_DATE = "ask_date"
ORCH_ACTION_CLARIFY_TIME = "clarify_time"
ORCH_ACTION_CLARIFY_CONFIRM = "clarify_confirm"
ORCH_ACTION_CHOOSE_SLOT = "choose_slot"
ORCH_ACTION_CONFIRM_YES = "confirm_yes"
ORCH_ACTION_CONFIRM_NO = "confirm_no"

ORCHESTRATION_TOOLS: Dict[str, Dict[str, Any]] = {
    "check_availability": {"kind": "calendar", "description": "Find available slots in the tenant calendar."},
    "create_booking": {"kind": "calendar", "description": "Create a booking event in the tenant calendar."},
    "cancel_booking": {"kind": "calendar", "description": "Cancel an existing booking."},
    "reschedule_booking": {"kind": "calendar", "description": "Move an existing booking to a new time."},
    "get_business_info": {"kind": "faq", "description": "Return structured business information such as address, price, duration, or services."},
}

def normalize_llm_intent(value: Any) -> Optional[str]:
    low = str(value or "").strip().lower()
    if not low:
        return None
    mapping = {
        "book": "booking", "booking": "booking", "appointment": "booking", "new_booking": "booking",
        "reschedule": "reschedule", "move": "reschedule", "change_time": "reschedule",
        "cancel": "cancel", "cancellation": "cancel",
        "info": "info", "question": "info", "faq": "info",
        "other": "other", "unknown": "other",
    }
    return mapping.get(low, low if low in {"booking", "reschedule", "cancel", "info", "other"} else None)

def normalize_llm_confirmation(value: Any) -> Optional[str]:
    low = str(value or "").strip().lower()
    if low in {"yes", "confirm", "confirmed", "true", "1"}:
        return "yes"
    if low in {"no", "decline", "false", "0"}:
        return "no"
    return None

def openai_understand_message(system: str, user: str, *, api_key: str, model: str, timeout: int = 25) -> Dict[str, Any]:
    if not api_key:
        return {}
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": 0.1,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"},
            },
            timeout=timeout,
        )
        if r.status_code == 200:
            return json.loads(r.json()["choices"][0]["message"]["content"])
        log.error("OpenAI understand error status=%s body=%s", r.status_code, r.text[:500])
    except Exception as e:
        log.error("OpenAI understand request failed: %s", e)
    return {}

def orchestration_tool_registry() -> Dict[str, Dict[str, Any]]:
    return dict(ORCHESTRATION_TOOLS)

def default_orchestration_decision(understanding: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "action": ORCH_ACTION_CONTINUE,
        "next_state": understanding.get("state"),
        "reply_mode": "legacy",
        "needs_tool": False,
        "tool_name": None,
        "tool_args": {},
        "reason": "fallback_to_legacy_flow",
    }

def orchestrate_turn(
    *,
    c: Dict[str, Any],
    msg: str,
    lang: str,
    understanding: Dict[str, Any],
    conversation_state_fn: Callable[[Dict[str, Any]], str],
    min_confidence: float,
    state_awaiting_time: str,
    state_awaiting_confirm: str,
) -> Dict[str, Any]:
    decision = default_orchestration_decision(understanding)
    state = conversation_state_fn(c)
    active_flow = bool(understanding.get("active_flow"))
    signals = set(understanding.get("signals") or [])
    intent = understanding.get("intent")
    confidence = float(understanding.get("confidence") or 0.0)
    selected_slot_iso = ((understanding.get("entities") or {}).get("selected_slot_iso"))

    if understanding.get("faq_result"):
        decision.update({"action": ORCH_ACTION_FAQ, "needs_tool": True, "tool_name": "get_business_info", "reason": "faq_detected", "reply_mode": "direct"})
        return decision
    if not active_flow and "greeting_only" in signals:
        decision.update({"action": ORCH_ACTION_GREET, "reason": "greeting_only_detected", "reply_mode": "direct"})
        return decision
    if not active_flow and "identity_check" in signals:
        decision.update({"action": ORCH_ACTION_IDENTITY, "reason": "identity_check_detected", "reply_mode": "direct"})
        return decision
    if not active_flow and "hours_question" in signals:
        decision.update({"action": ORCH_ACTION_HOURS, "reason": "hours_question_detected", "reply_mode": "direct"})
        return decision
    if "cancel_request" in signals or (not active_flow and intent == "cancel" and confidence >= min_confidence):
        decision.update({"action": ORCH_ACTION_CANCEL, "needs_tool": True, "tool_name": "cancel_booking", "reason": "cancel_intent_detected"})
        return decision
    if "reschedule_request" in signals or (not active_flow and intent == "reschedule" and confidence >= min_confidence):
        decision.update({"action": ORCH_ACTION_RESCHEDULE, "needs_tool": True, "tool_name": "reschedule_booking", "reason": "reschedule_intent_detected"})
        return decision
    if "booking_opener" in signals or (not active_flow and intent == "booking" and confidence >= min_confidence):
        decision.update({"action": ORCH_ACTION_START_BOOKING, "next_state": "AWAITING_SERVICE", "reason": "booking_intent_detected", "reply_mode": "mixed"})
        if (understanding.get("entities") or {}).get("service_key"):
            decision["next_state"] = "AWAITING_DATE"
        return decision
    if state == state_awaiting_time:
        if "other_day" in signals:
            decision.update({"action": ORCH_ACTION_ASK_DATE, "next_state": "AWAITING_DATE", "reason": "other_day_in_time_selection", "reply_mode": "direct"})
            return decision
        if "hesitation" in signals:
            decision.update({"action": ORCH_ACTION_CLARIFY_TIME, "next_state": state_awaiting_time, "reason": "hesitation_in_time_selection", "reply_mode": "direct"})
            return decision
        if selected_slot_iso:
            decision.update({"action": ORCH_ACTION_CHOOSE_SLOT, "next_state": state_awaiting_confirm, "needs_tool": True, "tool_name": "check_availability", "tool_args": {"slot_iso": selected_slot_iso}, "reason": "slot_selected"})
            return decision
    if state == state_awaiting_confirm:
        if "other_day" in signals:
            decision.update({"action": ORCH_ACTION_ASK_DATE, "next_state": "AWAITING_DATE", "reason": "other_day_in_confirm", "reply_mode": "direct"})
            return decision
        if "hesitation" in signals:
            decision.update({"action": ORCH_ACTION_CLARIFY_CONFIRM, "next_state": state_awaiting_confirm, "reason": "hesitation_in_confirm", "reply_mode": "direct"})
            return decision
        if "yes" in signals or understanding.get("confirmation") == "yes":
            decision.update({"action": ORCH_ACTION_CONFIRM_YES, "needs_tool": True, "tool_name": "create_booking", "reason": "confirm_yes_detected"})
            return decision
        if "no" in signals or understanding.get("confirmation") == "no":
            decision.update({"action": ORCH_ACTION_CONFIRM_NO, "reason": "confirm_no_detected"})
            return decision
    return decision
