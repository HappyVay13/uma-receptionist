import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from config.settings import APPT_MINUTES, BUSINESS_FALLBACK
from core.language import get_lang


def _slugify_service_key(value: str) -> str:
    low = (value or "").strip().lower()
    low = re.sub(r"[^a-z0-9а-яёāēīūčšžģķļņ]+", "_", low, flags=re.IGNORECASE)
    return low.strip("_") or f"service_{uuid.uuid4().hex[:6]}"

def _ensure_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(x).strip() for x in value if str(x).strip()]
    txt = str(value).strip()
    if not txt:
        return []
    try:
        parsed = json.loads(txt)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in txt.split(",") if x.strip()]

def parse_service_catalog(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    parsed = value
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return []
        try:
            parsed = json.loads(txt)
        except Exception:
            return []
    if not isinstance(parsed, list):
        return []

    out: List[Dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        base_name = str(item.get("name") or item.get("name_lv") or item.get("display_name") or item.get("key") or "").strip()
        if not base_name:
            continue
        key = str(item.get("key") or _slugify_service_key(base_name)).strip()
        try:
            duration_min = int(item.get("duration_min") or APPT_MINUTES)
        except Exception:
            duration_min = APPT_MINUTES
        aliases = _ensure_list(item.get("aliases"))
        aliases_lv = _ensure_list(item.get("aliases_lv"))
        aliases_ru = _ensure_list(item.get("aliases_ru"))
        aliases_en = _ensure_list(item.get("aliases_en"))
        if not aliases_lv and aliases:
            aliases_lv = aliases[:]
        if not aliases_ru and aliases:
            aliases_ru = aliases[:]
        if not aliases_en and aliases:
            aliases_en = aliases[:]
        out.append({
            "key": key,
            "name_lv": str(item.get("name_lv") or base_name).strip(),
            "name_ru": str(item.get("name_ru") or item.get("name") or base_name).strip(),
            "name_en": str(item.get("name_en") or item.get("name") or base_name).strip(),
            "duration_min": max(5, duration_min),
            "aliases_lv": aliases_lv,
            "aliases_ru": aliases_ru,
            "aliases_en": aliases_en,
        })
    return out

def fallback_service_catalog(tenant: Dict[str, Any]) -> List[Dict[str, Any]]:
    names: Dict[str, List[str]] = {
        "lv": [x.strip() for x in str(tenant.get("services_lv") or BUSINESS_FALLBACK["services_lv"]).split(",") if x.strip()],
        "ru": [x.strip() for x in str(tenant.get("services_ru") or BUSINESS_FALLBACK["services_ru"]).split(",") if x.strip()],
        "en": [x.strip() for x in str(tenant.get("services_en") or BUSINESS_FALLBACK["services_en"]).split(",") if x.strip()],
    }
    max_len = max(len(names["lv"]), len(names["ru"]), len(names["en"]), 1)
    catalog: List[Dict[str, Any]] = []
    for i in range(max_len):
        lv_name = names["lv"][i] if i < len(names["lv"]) else names["lv"][0]
        ru_name = names["ru"][i] if i < len(names["ru"]) else (names["ru"][0] if names["ru"] else lv_name)
        en_name = names["en"][i] if i < len(names["en"]) else (names["en"][0] if names["en"] else lv_name)
        catalog.append({
            "key": _slugify_service_key(lv_name),
            "name_lv": lv_name,
            "name_ru": ru_name,
            "name_en": en_name,
            "duration_min": APPT_MINUTES,
            "aliases_lv": [lv_name],
            "aliases_ru": [ru_name],
            "aliases_en": [en_name],
        })
    return catalog

def tenant_service_catalog(tenant: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("service_catalog", "services_catalog", "service_catalog_json", "services_json"):
        catalog = parse_service_catalog(tenant.get(key))
        if catalog:
            return catalog
    env_catalog = parse_service_catalog(os.getenv("BIZ_SERVICE_CATALOG", "").strip())
    if env_catalog:
        return env_catalog
    return fallback_service_catalog(tenant)

def get_service_item_by_key(catalog: List[Dict[str, Any]], service_key: Optional[str]) -> Optional[Dict[str, Any]]:
    sk = str(service_key or "").strip()
    if not sk:
        return None
    for item in catalog:
        if str(item.get("key") or "").strip() == sk:
            return item
    return None

def service_display_name(service_item: Optional[Dict[str, Any]], lang: str) -> str:
    if not service_item:
        return ""
    lang = get_lang(lang)
    return str(service_item.get(f"name_{lang}") or service_item.get("name_lv") or service_item.get("key") or "").strip()

def service_duration_min(service_item: Optional[Dict[str, Any]]) -> int:
    if not service_item:
        return APPT_MINUTES
    try:
        return max(5, int(service_item.get("duration_min") or APPT_MINUTES))
    except Exception:
        return APPT_MINUTES

def service_group_key(service_item: Optional[Dict[str, Any]]) -> str:
    if not service_item:
        return ""
    hay = " ".join([
        str(service_item.get("key") or ""),
        str(service_item.get("name_lv") or ""),
        str(service_item.get("name_ru") or ""),
        str(service_item.get("name_en") or ""),
        " ".join(service_item.get("aliases_lv") or []),
        " ".join(service_item.get("aliases_ru") or []),
        " ".join(service_item.get("aliases_en") or []),
    ]).lower()
    if any(x in hay for x in ["combo", "комбо", "kombo", "haircut and beard", "стрижка и борода", "frizūra un bārda", "matu griezums un bārda"]):
        return "combo"
    has_hair = any(x in hay for x in ["friz", "haircut", "стриж", "matu griez", "griezum"])
    has_beard = any(x in hay for x in ["bārd", "barda", "beard", "бород"])
    if has_hair and has_beard:
        return "combo"
    if has_beard:
        return "beard"
    if has_hair:
        return "haircut"
    return ""

def find_service_item_by_group(catalog: List[Dict[str, Any]], group: str) -> Optional[Dict[str, Any]]:
    for item in catalog:
        if service_group_key(item) == group:
            return item
    return None

def combined_service_display(lang: str, primary_item: Optional[Dict[str, Any]], addon_item: Optional[Dict[str, Any]]) -> str:
    primary = service_display_name(primary_item, lang)
    addon = service_display_name(addon_item, lang)
    if primary and addon:
        return f"{primary} + {addon}"
    return primary or addon or ""

def build_confirm_upsell_prompt(lang: str, when_text: str, haircut_item: Optional[Dict[str, Any]], beard_item: Optional[Dict[str, Any]]) -> str:
    haircut_name = service_display_name(haircut_item, lang)
    beard_name = service_display_name(beard_item, lang) or ("bārdu" if lang == "lv" else "бороду" if lang == "ru" else "a beard trim")
    if lang == "ru":
        return f"Отлично — можем записать вас на {haircut_name} {when_text}. Если хотите, можем добавить и {beard_name}. Добавляем?"
    if lang == "en":
        return f"Great — we can book your {haircut_name} for {when_text}. If you want, we can add {beard_name} too. Shall I add it?"
    return f"Lieliski — varam pierakstīt jūs uz {haircut_name} {when_text}. Ja vēlaties, varam pievienot arī {beard_name}. Vai pievienojam?"

def build_confirm_upsell_resolution(lang: str, when_text: str, added: bool, haircut_item: Optional[Dict[str, Any]], beard_item: Optional[Dict[str, Any]]) -> str:
    haircut_name = service_display_name(haircut_item, lang)
    beard_name = service_display_name(beard_item, lang) or ("bārdas kopšanu" if lang == "lv" else "подравнивание бороды" if lang == "ru" else "a beard trim")
    if added:
        if lang == "ru":
            return f"Отлично 👍 Добавил {beard_name}. Ваша запись подтверждена на {when_text}."
        if lang == "en":
            return f"Great 👍 I added {beard_name}. Your booking is confirmed for {when_text}."
        return f"Lieliski 👍 Pievienoju arī {beard_name}. Jūsu pieraksts ir apstiprināts uz {when_text}."
    if lang == "ru":
        return f"Хорошо 👍 Оставляем {haircut_name}. Ваша запись подтверждена на {when_text}."
    if lang == "en":
        return f"No problem 👍 We’ll keep {haircut_name}. Your booking is confirmed for {when_text}."
    return f"Labi 👍 Paliekam pie {haircut_name}. Jūsu pieraksts ir apstiprināts uz {when_text}."

def service_catalog_summary(catalog: List[Dict[str, Any]], lang: str) -> str:
    parts = []
    for item in catalog:
        display = service_display_name(item, lang)
        dur = service_duration_min(item)
        if display:
            parts.append(f"{display} ({dur} min)")
    return ", ".join(parts)

def service_alias_map_from_catalog(catalog: List[Dict[str, Any]], lang: str) -> Dict[str, str]:
    lang = get_lang(lang)
    out: Dict[str, str] = {}
    for item in catalog:
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        display = service_display_name(item, lang)
        for alias in [display] + list(item.get(f"aliases_{lang}") or []):
            a = str(alias or "").strip().lower()
            if a:
                out[a] = key
    return out

def canonical_service_key_from_text(text_: Optional[str], alias_map: Dict[str, str]) -> Optional[str]:
    low = (text_ or "").strip().lower()
    if not low:
        return None
    norm_low = re.sub(r"\s+", " ", re.sub(r"[^\wĀ-žА-Яа-яЁё]+", " ", low, flags=re.UNICODE)).strip()
    if low in alias_map:
        return alias_map[low]
    if norm_low in alias_map:
        return alias_map[norm_low]
    # Prefer longest alias first so generic words don't beat specific phrases
    for alias in sorted(alias_map.keys(), key=len, reverse=True):
        if not alias:
            continue
        norm_alias = re.sub(r"\s+", " ", re.sub(r"[^\wĀ-žА-Яа-яЁё]+", " ", alias, flags=re.UNICODE)).strip()
        if alias in low or (norm_alias and norm_alias in norm_low):
            return alias_map[alias]
    return None

def ensure_default_barbershop_aliases(catalog: List[Dict[str, Any]], alias_map: Dict[str, str], lang: str) -> Dict[str, str]:
    out = dict(alias_map)
    haircut_keys = []
    beard_keys = []
    combo_keys = []
    for item in catalog:
        key = str(item.get("key") or "").strip()
        hay = " ".join([
            key,
            str(item.get("name_lv") or ""),
            str(item.get("name_ru") or ""),
            str(item.get("name_en") or ""),
            " ".join(item.get("aliases_lv") or []),
            " ".join(item.get("aliases_ru") or []),
            " ".join(item.get("aliases_en") or []),
        ]).lower()
        if any(x in hay for x in ["friz", "haircut", "стриж", "matu griez", "griezum"]):
            haircut_keys.append(key)
        if any(x in hay for x in ["bārd", "barda", "beard", "бород"]):
            beard_keys.append(key)
        if any(x in hay for x in ["combo", "комбо", "kombo"]):
            combo_keys.append(key)

    def add_many(key: Optional[str], aliases: List[str]):
        if not key:
            return
        for a in aliases:
            aa = a.strip().lower()
            if aa and aa not in out:
                out[aa] = key

    haircut_key = haircut_keys[0] if haircut_keys else None
    beard_key = beard_keys[0] if beard_keys else None
    combo_key = combo_keys[0] if combo_keys else None

    add_many(haircut_key, [
        "matu griezums", "matu griezumu", "griezums", "griezumu",
        "apgriezt matus", "apgriezt", "frizūra", "frizura", "frizūru", "frizuru",
        "vīriešu frizūra", "viriesu frizura", "vīriešu frizūru", "viriesu frizuru",
        "vīriešu matu griezums", "viriesu matu griezums", "vīriešu matu griezumu", "viriesu matu griezumu",
        "подстричься", "стрижка", "стрижку", "мужская стрижка", "мужскую стрижку",
        "haircut", "mens haircut", "men's haircut", "cut hair", "trim hair"
    ])
    add_many(beard_key, [
        "bārda", "barda", "bārdu", "bardu", "bārdas korekcija", "bārdas korekciju",
        "bārdas trim", "bārdas trimu", "beard trim", "beard", "борода", "бороду", "подровнять бороду"
    ])
    add_many(combo_key, [
        "combo", "kombo", "комбо",
        "matu griezums un bārda", "matu griezumu un bārdu",
        "frizūra un bārda", "frizūru un bārdu",
        "haircut and beard", "стрижка и борода", "стрижку и бороду"
    ])
    return out

