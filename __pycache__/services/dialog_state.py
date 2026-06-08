from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

STATE_NEW = "NEW"
STATE_AWAITING_SERVICE = "AWAITING_SERVICE"
STATE_AWAITING_DATE = "AWAITING_DATE"
STATE_AWAITING_TIME = "AWAITING_TIME"
STATE_AWAITING_CONFIRM = "AWAITING_CONFIRM"
STATE_POST_BOOKING_UPSELL = "POST_BOOKING_UPSELL"
STATE_BOOKED = "BOOKED"
STATE_CANCELLED = "CANCELLED"

ACTIVE_BOOKING_STATES = {
    STATE_AWAITING_SERVICE,
    STATE_AWAITING_DATE,
    STATE_AWAITING_TIME,
    STATE_AWAITING_CONFIRM,
}

YES_WORDS = {
    "lv": {"jā", "ja", "jaa", "labi", "der", "ok", "okej", "apstiprinu"},
    "ru": {"да", "ага", "ок", "хорошо", "подтверждаю"},
    "en": {"yes", "yeah", "yep", "ok", "okay", "confirm"},
}

NO_WORDS = {
    "lv": {"nē", "ne", "nee"},
    "ru": {"нет", "неа"},
    "en": {"no", "nope"},
}

HESITATION_WORDS = {
    "lv": {"nezinu", "grūti pateikt", "gruti pateikt", "varbūt vēlāk", "varbut velak", "neesmu drošs", "neesmu droš a", "neesmu droša", "nav svarīgi", "nav svarigi"},
    "ru": {"не знаю", "не уверен", "не уверена", "может позже", "пока не знаю", "затрудняюсь"},
    "en": {"not sure", "i am not sure", "i'm not sure", "maybe later", "dont know", "don't know", "not certain"},
}

def get_lang_safe(lang: Optional[str]) -> str:
    low = str(lang or "lv").strip().lower()
    return low if low in {"lv", "ru", "en"} else "lv"

def conversation_state(c: Dict[str, Any]) -> str:
    state = str((c or {}).get("state") or STATE_NEW).strip().upper()
    allowed = {STATE_NEW, STATE_AWAITING_SERVICE, STATE_AWAITING_DATE, STATE_AWAITING_TIME, STATE_AWAITING_CONFIRM, STATE_POST_BOOKING_UPSELL, STATE_BOOKED, STATE_CANCELLED}
    return state if state in allowed else STATE_NEW

def is_active_booking_flow(c: Dict[str, Any]) -> bool:
    pending = (c or {}).get("pending") or {}
    return conversation_state(c or {}) in ACTIVE_BOOKING_STATES or bool(pending.get("booking_intent"))

def get_offered_slots(pending: Dict[str, Any]) -> List[str]:
    pending = pending or {}
    slots = pending.get("offered_slots")
    if isinstance(slots, list):
        return [str(x).strip() for x in slots if str(x).strip()]
    out: List[str] = []
    for key in ("opt1_iso", "opt2_iso"):
        val = str(pending.get(key) or "").strip()
        if val:
            out.append(val)
    return out

def set_offered_slots(pending: Dict[str, Any], slots: List[datetime]) -> Dict[str, Any]:
    pending = pending or {}
    offered = [dt.isoformat() for dt in slots if dt]
    pending["offered_slots"] = offered
    pending["opt1_iso"] = offered[0] if len(offered) > 0 else None
    pending["opt2_iso"] = offered[1] if len(offered) > 1 else None
    return pending

def clear_offered_slots(pending: Dict[str, Any]) -> Dict[str, Any]:
    pending = pending or {}
    for key in ("offered_slots", "opt1_iso", "opt2_iso"):
        pending.pop(key, None)
    return pending

def is_yes_text(text_: Optional[str], lang: str) -> bool:
    low = (text_ or "").strip().lower()
    if not low:
        return False
    allowed = set().union(*YES_WORDS.values())
    allowed.update(YES_WORDS.get(get_lang_safe(lang), set()))
    return low in allowed

def is_no_text(text_: Optional[str], lang: str) -> bool:
    low = (text_ or "").strip().lower()
    if not low:
        return False
    allowed = set().union(*NO_WORDS.values())
    allowed.update(NO_WORDS.get(get_lang_safe(lang), set()))
    return low in allowed

def is_short_ack_text(text_: Optional[str], lang: str) -> bool:
    low = (text_ or "").strip().lower()
    if not low:
        return False
    short_acks = {
        "lv": {"labi", "skaidrs", "ok", "okej", "der", "nu labi"},
        "ru": {"ок", "хорошо", "ладно", "давай", "понятно", "угу"},
        "en": {"ok", "okay", "sure", "alright", "got it"},
    }
    allowed = set().union(*short_acks.values())
    allowed.update(short_acks.get(get_lang_safe(lang), set()))
    return low in allowed

def normalize_phrase_text(text_: Optional[str]) -> str:
    low = (text_ or "").strip().lower()
    low = re.sub(r"[\,\.\!\?\;\:\-_/]+", " ", low)
    return re.sub(r"\s+", " ", low).strip()

def is_hesitation_text(text_: Optional[str], lang: str) -> bool:
    low = normalize_phrase_text(text_)
    if not low:
        return False
    allowed = set().union(*HESITATION_WORDS.values())
    allowed.update(HESITATION_WORDS.get(get_lang_safe(lang), set()))
    if low in allowed:
        return True
    return any(phrase in low for phrase in allowed if phrase)

def is_other_day_text(text_: Optional[str], lang: str) -> bool:
    low = normalize_phrase_text(text_)
    if not low:
        return False
    phrases = {
        "lv": {"citu dienu", "labak citu dienu", "labāk citu dienu", "cita diena", "ne citu dienu", "vēlos citu dienu"},
        "ru": {"другой день", "на другой день", "давайте другой день", "лучше другой день", "другая дата"},
        "en": {"other day", "another day", "different day", "better another day", "lets do another day", "let's do another day"},
    }
    allowed = set().union(*phrases.values())
    allowed.update(phrases.get(get_lang_safe(lang), set()))
    return any(phrase in low for phrase in allowed if phrase)

def detect_time_shift_direction(text_: Optional[str], lang: str) -> Optional[str]:
    low = normalize_phrase_text(text_)
    if not low:
        return None
    earlier = {
        "lv": {"agrāk", "agrak", "nedaudz agrāk", "drusku agrāk", "mazliet agrāk", "ātrāk", "atrak"},
        "ru": {"раньше", "пораньше", "чуть раньше", "немного раньше"},
        "en": {"earlier", "a bit earlier", "slightly earlier"},
    }
    later = {
        "lv": {"vēlāk", "velak", "nedaudz vēlāk", "drusku vēlāk", "mazliet vēlāk"},
        "ru": {"позже", "попозже", "чуть позже", "немного позже"},
        "en": {"later", "a bit later", "slightly later"},
    }
    all_earlier = set().union(*earlier.values())
    all_later = set().union(*later.values())
    all_earlier.update(earlier.get(get_lang_safe(lang), set()))
    all_later.update(later.get(get_lang_safe(lang), set()))
    if any(p in low for p in all_earlier if p):
        return "earlier"
    if any(p in low for p in all_later if p):
        return "later"
    return None

def reset_booking_context(c: Dict[str, Any], keep_name: bool = True) -> Dict[str, Any]:
    c = c or {}
    preserved_name = c.get("name") if keep_name else None
    c["service"] = None
    c["datetime_iso"] = None
    c["time_text"] = None
    c["pending"] = {"booking_intent": True}
    c["state"] = STATE_AWAITING_SERVICE
    c["name"] = preserved_name if keep_name else None
    return c

def normalize_booking_state(c: Dict[str, Any]) -> Dict[str, Any]:
    c = c or {}
    pending = c.get("pending") or {}
    state = conversation_state(c)
    original_state = state
    service_key = str(c.get("service") or pending.get("service") or "").strip()
    confirm_iso = str(pending.get("confirm_slot_iso") or "").strip()
    awaiting_time_date_iso = str(pending.get("awaiting_time_date_iso") or "").strip()
    offered_slots = get_offered_slots(pending)
    has_booking_intent = bool(pending.get("booking_intent"))
    booked_dt = str(c.get("datetime_iso") or "").strip()
    upsell_active = bool(pending.get("upsell_offer_active"))
    if original_state == STATE_POST_BOOKING_UPSELL and (upsell_active or confirm_iso):
        state = STATE_POST_BOOKING_UPSELL
    elif confirm_iso:
        state = STATE_AWAITING_CONFIRM
    elif offered_slots or awaiting_time_date_iso:
        state = STATE_AWAITING_TIME
    elif service_key and state not in (STATE_POST_BOOKING_UPSELL, STATE_BOOKED, STATE_CANCELLED):
        state = STATE_AWAITING_DATE if not booked_dt else state
    elif has_booking_intent and not service_key:
        state = STATE_AWAITING_SERVICE
    elif state in ACTIVE_BOOKING_STATES and not service_key:
        state = STATE_AWAITING_SERVICE
    if state in (STATE_BOOKED, STATE_CANCELLED) and has_booking_intent:
        state = STATE_AWAITING_SERVICE if not service_key else STATE_AWAITING_DATE
    c["state"] = state
    c["pending"] = pending or None
    return c
