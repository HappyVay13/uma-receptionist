import re
import unicodedata
from typing import Optional

def fold_match_text(text: Optional[str]) -> str:
    if not text:
        return ""

    text = text.lower().strip()

    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )

    text = re.sub(r"[^\w]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text
