import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config.settings import TZ

WEEKDAY_HINTS = {
    0: ["monday", "mondays", "monday's", "next monday", "понедельник", "понедельника", "в понедельник", "на понедельник", "pirmdien", "pirmdiena", "pirmdienas", "uz pirmdienu", "pirmdien vakarā", "pirmdienas vakarā", "pirmdien vakara", "pirmdienas vakara", "pirmdienu"],
    1: ["tuesday", "tuesdays", "tuesday's", "next tuesday", "вторник", "вторника", "во вторник", "на вторник", "otrdien", "otrdiena", "otrdienas", "uz otrdienu", "otrdien vakarā", "otrdienas vakarā", "otrdien vakara", "otrdienas vakara", "otrdienu"],
    2: ["wednesday", "wednesdays", "wednesday's", "next wednesday", "среда", "среду", "среды", "в среду", "на среду", "trešdien", "tresdien", "trešdiena", "tresdiena", "trešdienas", "tresdienas", "uz trešdienu", "uz tresdienu", "trešdien vakarā", "tresdien vakarā", "trešdienas vakarā", "tresdienas vakarā", "trešdien vakara", "tresdien vakara", "trešdienu", "tresdienu"],
    3: ["thursday", "thursdays", "thursday's", "next thursday", "четверг", "четверга", "в четверг", "на четверг", "ceturtdien", "ceturtdiena", "ceturtdienas", "uz ceturtdienu", "ceturtdien vakarā", "ceturtdienas vakarā", "ceturtdien vakara", "ceturtdienu"],
    4: ["friday", "fridays", "friday's", "next friday", "пятница", "пятницу", "пятницы", "в пятницу", "на пятницу", "piektdien", "piektdiena", "piektdienas", "uz piektdienu", "piektdien vakarā", "piektdienas vakarā", "piektdien vakara", "piektdienu"],
    5: ["saturday", "saturdays", "saturday's", "next saturday", "суббота", "субботу", "субботы", "в субботу", "на субботу", "sestdien", "sestdiena", "sestdienas", "uz sestdienu", "sestdien vakarā", "sestdienas vakarā", "sestdien vakara", "sestdienu"],
    6: ["sunday", "sundays", "sunday's", "next sunday", "воскресенье", "воскресенья", "в воскресенье", "на воскресенье", "svētdien", "svetdien", "svētdiena", "svetdiena", "svētdienas", "svetdienas", "uz svētdienu", "uz svetdienu", "svētdien vakarā", "svetdien vakarā", "svētdienas vakarā", "svetdienas vakarā", "svētdien vakara", "svetdien vakara", "svētdienu", "svetdienu"],
}

def now_ts() -> datetime:
    return datetime.now(TZ)


def today_local() -> date:
    return now_ts().date()


def parse_dt_any_tz(iso: str) -> Optional[datetime]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    except Exception:
        return None

def _parse_hhmm(hhmm: str) -> Tuple[int, int]:
    hh, mm = hhmm.split(":")
    return int(hh), int(mm)

def format_dt_short(dt: Optional[datetime]) -> str:
    return dt.strftime("%d.%m %H:%M") if dt else ""

def _phrase_in_text(src: str, phrase: str) -> bool:
    src = (src or "").lower().strip()
    phrase = (phrase or "").lower().strip()
    if not src or not phrase:
        return False
    pattern = r"(?<![\wĀ-žА-Яа-яЁё])" + re.escape(phrase) + r"(?![\wĀ-žА-Яа-яЁё])"
    return re.search(pattern, src, flags=re.IGNORECASE | re.UNICODE) is not None


def _contains_any_phrase(src: str, phrases: List[str]) -> bool:
    return any(_phrase_in_text(src, p) for p in (phrases or []))


def parse_time_text_to_dt(text_: str) -> Optional[datetime]:
    src = (text_ or "")
    m = re.search(r"\b([01]?\d|2[0-3])[:. ]([0-5]\d)\b", src.lower())
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    base = today_local()
    t_low = src.lower()

    if _contains_any_phrase(t_low, ["parīt", "послезавтра", "day after tomorrow"]):
        base += timedelta(days=2)
    elif _contains_any_phrase(t_low, ["rīt", "rit", "завтра", "tomorrow"]):
        base += timedelta(days=1)

    dm = re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", src)
    if dm:
        dd, mo = int(dm.group(1)), int(dm.group(2))
        yy = dm.group(3)
        year = int(yy) + 2000 if yy and len(yy) == 2 else int(yy) if yy else base.year
        try:
            return datetime(year, mo, dd, hh, mm, tzinfo=TZ)
        except Exception:
            pass

    return datetime(base.year, base.month, base.day, hh, mm, tzinfo=TZ)


def parse_dt_from_iso_or_fallback(
    datetime_iso: Optional[str], time_text: Optional[str], raw_text: Optional[str]
) -> Optional[datetime]:
    dt = parse_dt_any_tz((datetime_iso or "").strip())
    return dt if dt else parse_time_text_to_dt(f"{time_text or ''} {raw_text or ''}")


def parse_explicit_time_parts(text_: Optional[str]) -> Optional[Tuple[int, int]]:
    src = (text_ or "").lower().strip()
    if not src:
        return None

    # 14:30 / 14.30 / 14 30
    m = re.search(r"\b([01]?\d|2[0-3])[:. ]([0-5]\d)\b", src)
    if m:
        return int(m.group(1)), int(m.group(2))

    # 2pm / 2 pm / 2:30pm / 2.30 pm
    m = re.search(r"\b(1[0-2]|0?[1-9])(?:[:. ]([0-5]\d))?\s*(am|pm)\b", src)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm == "pm" and hh != 12:
            hh += 12
        if ampm == "am" and hh == 12:
            hh = 0
        return hh, mm

    # plain hour like 14
    if re.fullmatch(r"([01]?\d|2[0-3])", src):
        return int(src), 0
    return None


def has_explicit_time(text_: Optional[str]) -> bool:
    return parse_explicit_time_parts(text_) is not None


def has_date_reference(text_: Optional[str]) -> bool:
    src = (text_ or "").lower().strip()
    if not src:
        return False
    if re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", src):
        return True
    keywords = [
        "rīt", "rit", "parīt", "šodien", "sodien", "šorīt", "sorit", "šovakar", "sovakar",
        "завтра", "послезавтра", "сегодня", "сегодня утром", "сегодня днем", "сегодня днём", "сегодня вечером",
        "tomorrow", "day after tomorrow", "today", "this morning", "this afternoon", "this evening", "tonight",
        "next monday", "next tuesday", "next wednesday", "next thursday", "next friday", "next saturday", "next sunday",
    ]
    if _contains_any_phrase(src, keywords):
        return True
    for hints in WEEKDAY_HINTS.values():
        if _contains_any_phrase(src, hints):
            return True
    return False


def combine_date_with_explicit_time(base_iso: Optional[str], time_source: Optional[str]) -> Optional[datetime]:
    base_dt = parse_dt_any_tz((base_iso or "").strip())
    parts = parse_explicit_time_parts(time_source)
    if not base_dt or not parts:
        return None
    hh, mm = parts
    return base_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)

def next_weekday_date(target_weekday: int, base: Optional[date] = None) -> date:
    base = base or today_local()
    days_ahead = (target_weekday - base.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base + timedelta(days=days_ahead)


def parse_date_only_text(text_: Optional[str]) -> Optional[datetime]:
    src = (text_ or "").lower().strip()
    if not src:
        return None

    dm = re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", src)
    if dm:
        dd, mo = int(dm.group(1)), int(dm.group(2))
        yy = dm.group(3)
        year = int(yy) + 2000 if yy and len(yy) == 2 else int(yy) if yy else today_local().year
        try:
            return datetime(year, mo, dd, 9, 0, tzinfo=TZ)
        except Exception:
            pass

    base = today_local()

    # Weekdays must win over relative substrings like "rīt" inside "rīta".
    for wd, hints in WEEKDAY_HINTS.items():
        if _contains_any_phrase(src, hints):
            d = next_weekday_date(wd, base)
            return datetime.combine(d, datetime.min.time(), tzinfo=TZ).replace(hour=9)

    if _contains_any_phrase(src, ["parīt", "послезавтра", "day after tomorrow"]):
        return datetime.combine(base + timedelta(days=2), datetime.min.time(), tzinfo=TZ).replace(hour=9)
    if _contains_any_phrase(src, ["rīt", "rit", "завтра", "tomorrow"]):
        return datetime.combine(base + timedelta(days=1), datetime.min.time(), tzinfo=TZ).replace(hour=9)
    if _contains_any_phrase(src, ["šodien", "sodien", "šorīt", "sorit", "šovakar", "sovakar", "сегодня", "сегодня утром", "сегодня днем", "сегодня днём", "сегодня вечером", "today", "this morning", "this afternoon", "this evening", "tonight"]):
        return datetime.combine(base, datetime.min.time(), tzinfo=TZ).replace(hour=9)

    return None


NATURAL_TIME_DEFAULTS = {
    "morning": 10,
    "midday": 12,
    "afternoon": 14,
    "evening": 17,
}

def detect_time_bucket(text_: Optional[str]) -> Optional[str]:
    src = (text_ or "").lower().strip()
    if not src:
        return None
    patterns = {
        "morning": [
            "no rīta", "no rita", "rīt no rīta", "rit no rita", "šorīt", "sorit", "rīta", "rita",
            "утром", "сегодня утром", "утра",
            "in the morning", "this morning", "morning"
        ],
        "midday": [
            "pusdienlaikā", "pusdienlaika", "ap pusdienlaiku", "днём", "днем", "сегодня днем", "сегодня днём", "at noon", "noon", "midday"
        ],
        "afternoon": [
            "pēcpusdienā", "pecpusdiena", "pecpusdienā", "šopēcpusdien", "sopecpusdien", "after lunch", "in the afternoon", "this afternoon", "afternoon", "днём", "днем", "после обеда"
        ],
        "evening": [
            "vakarā", "vakara", "vakaru", "uz vakaru", "vakarpusē", "vakarpuse", "šovakar", "sovakar",
            "вечером", "вечеру", "сегодня вечером", "к вечеру", "ближе к вечеру", "на вечер", "на вечернее время",
            "in the evening", "this evening", "later in the evening", "towards evening", "evening", "tonight",
            "pēc darba", "pec darba", "после работы", "after work"
        ],
    }
    for bucket, hints in patterns.items():
        if _contains_any_phrase(src, hints):
            return bucket
    return None

def parse_time_window(text_: Optional[str]) -> Optional[Tuple[int, int]]:
    src = (text_ or "").lower().strip()
    if not src:
        return None

    if _contains_any_phrase(src, ["pēc darba", "pec darba", "после работы", "after work"]):
        return (17, 21)
    if _contains_any_phrase(src, [
        "ближе к вечеру", "к вечеру", "на вечер", "на вечернее время",
        "uz vakaru", "vakarpusē", "vakarpuse", "vakaru",
        "towards evening", "later in the evening", "in the evening", "tonight"
    ]):
        return (16, 21)

    bucket = detect_time_bucket(src)
    if bucket == "morning":
        return (9, 12)
    if bucket == "midday":
        return (11, 14)
    if bucket == "afternoon":
        return (12, 17)
    if bucket == "evening":
        return (16, 21)
    return None

def has_natural_time_hint(text_: Optional[str]) -> bool:
    src = (text_ or "").lower().strip()
    if not src:
        return False
    if parse_explicit_time_parts(src):
        return True
    if detect_time_bucket(src):
        return True
    approx_markers = ["ap ", "apmēram", "apmeram", "kaut kur", "around", "about", "около", "примерно"]
    if any(m in src for m in approx_markers):
        return True
    return False


def sanitize_conversation_time_text(value: Any) -> Optional[str]:
    txt = str(value or "").strip()
    if not txt:
        return None
    # Store only short user-provided temporal hints to avoid DB truncation and polluted state.
    if len(txt) > 64:
        return None
    if has_explicit_time(txt) or has_date_reference(txt) or has_natural_time_hint(txt):
        return txt
    return None


def pending_time_window_tuple(pending: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    raw = (pending or {}).get("preferred_time_window")
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        try:
            return int(raw[0]), int(raw[1])
        except Exception:
            return None
    return None

def parse_natural_datetime(text_: Optional[str], base_iso: Optional[str] = None) -> Optional[datetime]:
    src = (text_ or "").lower().strip()
    if not src:
        return None

    base_dt = parse_dt_any_tz((base_iso or "").strip())
    date_dt = parse_date_only_text(src)
    if not date_dt and base_dt:
        date_dt = base_dt

    time_parts = parse_explicit_time_parts(src)

    if not time_parts:
        approx_patterns = [
            r"\bap\s+([01]?\d|2[0-3])\b",
            r"\bapmēram\s+([01]?\d|2[0-3])\b",
            r"\bapmeram\s+([01]?\d|2[0-3])\b",
            r"\bkaut\s+kur\s+([01]?\d|2[0-3])\b",
            r"\baround\s+([01]?\d|2[0-3])\b",
            r"\babout\s+([01]?\d|2[0-3])\b",
            r"\bоколо\s+([01]?\d|2[0-3])\b",
            r"\bпримерно\s+([01]?\d|2[0-3])\b",
        ]
        for pat in approx_patterns:
            m = re.search(pat, src)
            if m:
                time_parts = (int(m.group(1)), 0)
                break

    if not time_parts:
        bucket = detect_time_bucket(src)
        if bucket:
            time_parts = (NATURAL_TIME_DEFAULTS[bucket], 0)

    if date_dt and time_parts:
        hh, mm = time_parts
        return date_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)

    if date_dt and not time_parts and detect_time_bucket(src):
        hh = NATURAL_TIME_DEFAULTS[detect_time_bucket(src)]
        return date_dt.replace(hour=hh, minute=0, second=0, microsecond=0)

    if not date_dt and base_dt and time_parts:
        hh, mm = time_parts
        return base_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)

    return None
