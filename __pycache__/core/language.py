import re
from typing import Dict, List, Optional

def get_lang(value: Optional[str]) -> str:
    return value if value in ("en", "ru", "lv") else "lv"


def stt_locale_for_lang(lang: str) -> str:
    lang = get_lang(lang)
    if lang == "ru":
        return "ru-RU"
    if lang == "lv":
        return "lv-LV"
    return "en-US"


def tts_language_code_for_lang(lang: str) -> str:
    lang = get_lang(lang)
    if lang == "ru":
        return "ru-RU"
    if lang == "en":
        return "en-US"
    return "lv-LV"

LANG_HINTS = {
    "lv": {
        "strong": [
            "labdien", "sveiki", "lūdzu", "ludzu", "paldies", "pieraksts", "pierakstīties",
            "pierakstities", "frizētava", "frizetava", "barberšops", "bārda", "barda",
            "rīt", "rit", "parīt", "šodien", "sodien", "cikos", "pārcelt", "atcelt",
            "vai", "tas", "ir", "strādājat", "darba", "laiks"
        ],
        "weak": ["uz", "kad", "laiks", "diena", "meistars", "pakalpojums", "šodien", "rīt"],
    },
    "ru": {
        "strong": [
            "здравствуйте", "привет", "добрый", "запись", "записаться", "парикмахерская",
            "барбершоп", "стрижка", "борода", "завтра", "послезавтра", "сегодня",
            "перенести", "отменить", "время", "работаете", "это", "у вас", "можно"
        ],
        "weak": ["дата", "когда", "время", "мастер", "услуга", "запись", "сегодня", "завтра"],
    },
    "en": {
        "strong": [
            "hello", "hi", "appointment", "book", "booking", "cancel", "reschedule",
            "tomorrow", "today", "barbershop", "salon", "clinic", "open", "working",
            "hours", "service", "time", "name", "is this", "can i"
        ],
        "weak": ["when", "time", "date", "service", "today", "tomorrow"],
    },
}

GREETING_PATTERNS = {
    "lv": ["labdien", "sveiki", "čau", "cau", "halo", "alo"],
    "ru": ["здравствуйте", "добрый день", "добрый вечер", "привет", "алло", "але"],
    "en": ["hello", "hi", "good morning", "good afternoon", "hey"],
}

IDENTITY_CHECK_PATTERNS = [
    "vai tas ir", "vai jūs esat", "это ", "is this", "did i reach",
    "я туда попал", "это барбершоп", "это парикмахерская", "это клиника",
]

HOURS_PATTERNS = [
    "работаете", "во сколько", "часы работы", "открыты", "открыто",
    "strādājat", "darba laiks", "atvērts", "cikos strādājat",
    "open", "working hours", "what time are you open", "are you open",
]

BOOKING_OPENERS = [
    "можно записаться", "хочу записаться", "хотел записаться", "нужна запись",
    "gribu pierakstīties", "vēlos pierakstīties", "vai var pierakstīties",
    "i want to book", "i'd like to book", "can i book", "need an appointment",
]

def tokenize_lang_text(text_: str) -> List[str]:
    return re.findall(r"[A-Za-zĀ-žа-яА-ЯёЁ]+", (text_ or "").lower(), flags=re.UNICODE)

def detect_language_scores(text_: str) -> Dict[str, float]:
    raw = (text_ or "").strip()
    low = raw.lower()
    scores: Dict[str, float] = {"lv": 0.0, "ru": 0.0, "en": 0.0}
    if not low:
        scores["lv"] = 1.0
        return scores

    if re.search(r"[а-яё]", low, flags=re.IGNORECASE):
        scores["ru"] += 2.5
    if re.search(r"[āēīūčšžģķļņ]", low):
        scores["lv"] += 2.5
    latin_words = len(re.findall(r"[A-Za-z]+", low))
    if latin_words:
        scores["en"] += 0.2 * latin_words

    tokens = tokenize_lang_text(low)
    joined = " ".join(tokens)

    for lang_code, groups in LANG_HINTS.items():
        for tok in groups["strong"]:
            if tok in joined:
                scores[lang_code] += 2.0
        for tok in groups["weak"]:
            if tok in joined:
                scores[lang_code] += 0.7

    if any(ch in low for ch in ["ā", "ē", "ī", "ū", "č", "š", "ž", "ģ", "ķ", "ļ", "ņ"]):
        scores["lv"] += 1.2
    if re.search(r"[ёыэъ]", low):
        scores["ru"] += 1.0

    if any(x in low for x in ["hello", "appointment", "reschedule", "cancel", "book"]):
        scores["en"] += 2.5

    return scores

def detect_language(text_: str) -> str:
    scores = detect_language_scores(text_)
    lang, score = max(scores.items(), key=lambda x: x[1])
    return lang if score > 0 else "lv"

def resolve_reply_language(text_: str, current_lang: Optional[str]) -> str:
    current = get_lang(current_lang)
    scores = detect_language_scores(text_)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_lang, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    if top_score <= 0:
        return current
    if top_lang == current:
        return current

    margin = top_score - second_score
    if len(tokenize_lang_text(text_)) <= 2 and margin < 2.0:
        return current
    if margin >= 1.6:
        return top_lang
    if scores.get(current, 0.0) + 0.9 >= top_score:
        return current
    return top_lang

def is_greeting_only(text_: str) -> bool:
    low = (text_ or "").strip().lower()
    if not low:
        return False
    if len(tokenize_lang_text(low)) > 6:
        return False
    if any(p in low for p in IDENTITY_CHECK_PATTERNS + HOURS_PATTERNS + BOOKING_OPENERS):
        return False
    return any(any(g in low for g in patterns) for patterns in GREETING_PATTERNS.values())

def is_identity_check(text_: str) -> bool:
    low = (text_ or "").strip().lower()
    return any(p in low for p in IDENTITY_CHECK_PATTERNS)

def is_hours_question(text_: str) -> bool:
    low = (text_ or "").strip().lower()
    return any(p in low for p in HOURS_PATTERNS)

def is_booking_opener(text_: str) -> bool:
    low = (text_ or "").strip().lower()
    if not low:
        return False

    strong_phrases = [
        "gribu pierakstīties",
        "gribu pierakstities",
        "vēlos pierakstīties",
        "vēlos pierakstities",
        "velos pierakstities",
        "pierakstīties",
        "pierakstities",
        "pieraksts",
        "gribu rezervēt",
        "gribu rezervet",
        "vēlos rezervēt",
        "velos rezervet",
        "можно записаться",
        "хочу записаться",
        "нужна запись",
        "i want to book",
        "i'd like to book",
        "need an appointment",
    ]
    if any(p in low for p in strong_phrases):
        return True

    return any(p in low for p in BOOKING_OPENERS)

def detect_language_choice(text_: str, digits: str = "") -> Optional[str]:
    d = (digits or "").strip()
    if d == "1":
        return "lv"
    if d == "2":
        return "ru"
    if d == "3":
        return "en"
    t = (text_ or "").strip().lower()
    if not t:
        return None
    if any(x in t for x in ["latv", "latvie", "latvian", "vien", "one"]):
        return "lv"
    if any(x in t for x in ["рус", "kriev", "russian", "два", "two"]):
        return "ru"
    if any(x in t for x in ["english", "англ", "trīs", "tris", "three", "три"]):
        return "en"
    return detect_language(t)

