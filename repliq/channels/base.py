from dataclasses import dataclass
from typing import Optional

@dataclass
class IncomingMessage:
    tenant_id: str
    user_id: str
    text: str
    channel: str
    lang_hint: Optional[str] = None
    source: str = "runtime"

@dataclass
class OutgoingMessage:
    text: str
    channel: str
    status: str = "ok"
