from __future__ import annotations

from typing import Any, Dict, List


def build_business_memory_candidates(signals_payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """Suggest business-memory entries from repeated friction/FAQ questions."""
    out: List[Dict[str, str]] = []
    for item in signals_payload.get("repeated_questions_or_friction") or []:
        text_value = str(item.get("text") or "").strip()
        if not text_value:
            continue
        out.append({
            "source": "conversation_pattern",
            "candidate": text_value,
            "reason": f"Repeated or unresolved client phrase ({item.get('count', 1)}x).",
        })
    return out[:10]
