import json
import re
from typing import Dict, Optional

from config.settings import VOICE_CLIENT_TENANT_MAP, VOICE_DEMO_TENANT_ID


def normalize_incoming_to_number(raw_value: str) -> str:
    v = (raw_value or "").strip()
    if v.startswith("whatsapp:"):
        v = v[len("whatsapp:"):]
    if v.startswith("sip:"):
        v = v[len("sip:"):]
    if v.startswith("client:"):
        v = v[len("client:"):]
    v = re.sub(r"[^\d+]", "", v)
    if v and not v.startswith("+") and v.isdigit():
        v = "+" + v
    return v


def looks_like_phone_number(raw_value: str) -> bool:
    v = normalize_incoming_to_number(raw_value)
    digits = re.sub(r"\D", "", v)
    return len(digits) >= 7


def parse_voice_client_tenant_map() -> Dict[str, str]:
    txt = (VOICE_CLIENT_TENANT_MAP or "").strip()
    out: Dict[str, str] = {}
    if not txt:
        return out
    try:
        parsed = json.loads(txt)
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                ks = str(k).strip()
                vs = str(v).strip()
                if ks and vs:
                    out[ks] = vs
            return out
    except Exception:
        pass
    for part in txt.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        left, right = part.split(":", 1)
        left = left.strip()
        right = right.strip()
        if left and right:
            out[left] = right
    return out


def tenant_id_from_client_identity(client_identity: str) -> Optional[str]:
    ident = (client_identity or "").strip()
    if ident.startswith("client:"):
        ident = ident[len("client:"):]

    m = re.match(r"^tenant__([^_]+(?:_[^_]+)*)__.+$", ident)
    if m:
        return m.group(1)

    m2 = re.match(r"^tenant:([^:]+):.+$", ident)
    if m2:
        return m2.group(1)

    mapped = parse_voice_client_tenant_map().get(ident)
    if mapped:
        return mapped

    if VOICE_DEMO_TENANT_ID:
        return VOICE_DEMO_TENANT_ID

    return None
