import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.settings import (
    BUSINESS_BREAKS_JSON,
    BUSINESS_BUFFER_MINUTES,
    BUSINESS_DAYS_OFF,
    BUSINESS_MIN_NOTICE_MINUTES,
    BUSINESS_WEEKLY_HOURS_JSON,
)


def _safe_json_obj(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    txt = str(value).strip()
    if not txt:
        return None
    try:
        return json.loads(txt)
    except Exception:
        return None

def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(value)
    except Exception:
        return default

def _normalize_weekday_key(value: str) -> Optional[str]:
    low = (value or "").strip().lower()
    mapping = {
        "mon": "mon", "monday": "mon", "1": "mon",
        "tue": "tue", "tues": "tue", "tuesday": "tue", "2": "tue",
        "wed": "wed", "wednesday": "wed", "3": "wed",
        "thu": "thu", "thur": "thu", "thurs": "thu", "thursday": "thu", "4": "thu",
        "fri": "fri", "friday": "fri", "5": "fri",
        "sat": "sat", "saturday": "sat", "6": "sat",
        "sun": "sun", "sunday": "sun", "0": "sun", "7": "sun",
    }
    return mapping.get(low)

def _weekday_key_for_date(dt_value: datetime) -> str:
    keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    return keys[dt_value.weekday()]

def default_weekly_hours(work_start: str, work_end: str) -> Dict[str, Optional[List[str]]]:
    return {k: [work_start, work_end] for k in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]}

def tenant_business_rules(tenant: Dict[str, Any], work_start: str, work_end: str) -> Dict[str, Any]:
    weekly_hours = default_weekly_hours(work_start, work_end)
    src_weekly = (
        tenant.get("weekly_hours_json")
        or tenant.get("business_hours_json")
        or tenant.get("working_hours_json")
        or BUSINESS_WEEKLY_HOURS_JSON
    )
    parsed_weekly = _safe_json_obj(src_weekly)
    if isinstance(parsed_weekly, dict):
        for raw_key, value in parsed_weekly.items():
            wk = _normalize_weekday_key(str(raw_key))
            if not wk:
                continue
            if value in (None, False, "closed", "off"):
                weekly_hours[wk] = None
            elif isinstance(value, (list, tuple)) and len(value) >= 2:
                weekly_hours[wk] = [str(value[0]).strip(), str(value[1]).strip()]
            elif isinstance(value, dict):
                start = str(value.get("start") or value.get("from") or "").strip()
                end = str(value.get("end") or value.get("to") or "").strip()
                if start and end:
                    weekly_hours[wk] = [start, end]

    days_off: set[str] = set()
    src_days_off = tenant.get("days_off") or tenant.get("days_off_json") or BUSINESS_DAYS_OFF
    parsed_days_off = _safe_json_obj(src_days_off)
    if isinstance(parsed_days_off, list):
        for item in parsed_days_off:
            wk = _normalize_weekday_key(str(item))
            if wk:
                days_off.add(wk)
    else:
        for part in str(src_days_off or "").split(","):
            wk = _normalize_weekday_key(part)
            if wk:
                days_off.add(wk)
    for wk in list(days_off):
        weekly_hours[wk] = None

    breaks_by_day = {k: [] for k in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]}
    src_breaks = tenant.get("breaks_json") or tenant.get("breaks") or BUSINESS_BREAKS_JSON
    parsed_breaks = _safe_json_obj(src_breaks)
    if isinstance(parsed_breaks, dict):
        for raw_key, value in parsed_breaks.items():
            wk = _normalize_weekday_key(str(raw_key))
            if not wk:
                continue
            vals = value if isinstance(value, list) else [value]
            for interval in vals:
                if isinstance(interval, (list, tuple)) and len(interval) >= 2:
                    breaks_by_day[wk].append([str(interval[0]).strip(), str(interval[1]).strip()])
                elif isinstance(interval, dict):
                    start = str(interval.get("start") or interval.get("from") or "").strip()
                    end = str(interval.get("end") or interval.get("to") or "").strip()
                    if start and end:
                        breaks_by_day[wk].append([start, end])
    elif isinstance(parsed_breaks, list):
        # global breaks applied to every day
        for wk in breaks_by_day:
            for interval in parsed_breaks:
                if isinstance(interval, (list, tuple)) and len(interval) >= 2:
                    breaks_by_day[wk].append([str(interval[0]).strip(), str(interval[1]).strip()])

    holidays: List[str] = []
    src_holidays = tenant.get("holidays_json") or tenant.get("holidays")
    parsed_holidays = _safe_json_obj(src_holidays)
    if isinstance(parsed_holidays, list):
        holidays = [str(x).strip() for x in parsed_holidays if str(x).strip()]
    elif isinstance(parsed_holidays, str) and parsed_holidays.strip():
        holidays = [parsed_holidays.strip()]

    min_notice_minutes = _safe_int(
        tenant.get("min_notice_minutes")
        or tenant.get("lead_time_min")
        or tenant.get("minimum_notice_minutes")
        or BUSINESS_MIN_NOTICE_MINUTES,
        0,
    )
    buffer_minutes = _safe_int(
        tenant.get("buffer_minutes")
        or tenant.get("booking_buffer_min")
        or tenant.get("service_buffer_minutes")
        or BUSINESS_BUFFER_MINUTES,
        0,
    )

    return {
        "weekly_hours": weekly_hours,
        "days_off": sorted(days_off),
        "breaks": breaks_by_day,
        "holidays": holidays,
        "min_notice_minutes": max(0, min_notice_minutes),
        "buffer_minutes": max(0, buffer_minutes),
    }

