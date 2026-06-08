from __future__ import annotations

from typing import Any, Callable, Dict

class ConversationEngine:
    """Thin stage-8 facade around the existing legacy conversation handler.

    This class is intentionally small for this migration step. It lets the app
    start depending on an explicit conversation engine object without rewriting
    the full booking flow in one risky deploy.
    """

    def __init__(self, handler: Callable[..., Dict[str, Any]]):
        self.handler = handler

    def handle_user_text(self, tenant_id: str, raw_phone: str, text_in: str, channel: str, lang_hint: str, source: str = "runtime") -> Dict[str, Any]:
        return self.handler(tenant_id, raw_phone, text_in, channel, lang_hint, source=source)


def create_conversation_engine(handler: Callable[..., Dict[str, Any]]) -> ConversationEngine:
    return ConversationEngine(handler)
