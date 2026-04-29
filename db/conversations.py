import json
import re
from typing import Any, Dict

from sqlalchemy import text

from config.settings import TENANT_ID_DEFAULT
from core.language import get_lang
from core.parsing_time import sanitize_conversation_time_text
from db.database import engine


def norm_user_key(phone: str) -> str:
    raw = (phone or "").strip().replace("whatsapp:", "")
    if not raw:
        return "unknown"
    phone_like = re.sub(r"[^\d+]", "", raw)
    digits = re.sub(r"\D", "", phone_like)
    if len(digits) >= 7:
        return phone_like or "unknown"
    safe = re.sub(r"[^a-zA-Z0-9_:\-]", "_", raw).strip("_")
    return safe or "unknown"


def db_get_or_create_conversation(
    tenant_id: str, user_key: str, default_lang: str
) -> Dict[str, Any]:
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    user_key = norm_user_key(user_key)
    default_lang = get_lang(default_lang)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
            SELECT lang_lock, state, service, name, datetime_iso, time_text, pending_json
            FROM conversations
            WHERE tenant_id=:tid AND user_key=:uk
            LIMIT 1
        """
            ),
            {"tid": tenant_id, "uk": user_key},
        ).fetchone()
        if row:
            pending = None
            if row[6]:
                try:
                    pending = json.loads(row[6])
                except Exception:
                    pending = None
            return {
                "lang": get_lang(row[0]),
                "state": row[1] or "NEW",
                "service": row[2],
                "name": row[3],
                "datetime_iso": row[4],
                "time_text": row[5],
                "pending": pending,
            }
        conn.execute(
            text(
                """
            INSERT INTO conversations
              (tenant_id, user_key, lang_lock, state, updated_at)
            VALUES
              (:tid, :uk, :lang, 'NEW', NOW())
        """
            ),
            {"tid": tenant_id, "uk": user_key, "lang": default_lang},
        )
    return {
        "lang": default_lang,
        "state": "NEW",
        "service": None,
        "name": None,
        "datetime_iso": None,
        "time_text": None,
        "pending": None,
    }


def db_save_conversation(tenant_id: str, user_key: str, c: Dict[str, Any]) -> None:
    tenant_id = (tenant_id or "").strip() or TENANT_ID_DEFAULT
    user_key = norm_user_key(user_key)
    pending_json = (
        json.dumps(c["pending"], ensure_ascii=False) if c.get("pending") else None
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            UPDATE conversations
            SET lang_lock=:lang, state=:state, service=:service, name=:name,
                datetime_iso=:dtiso, time_text=:tt, pending_json=:pj, updated_at=NOW()
            WHERE tenant_id=:tid AND user_key=:uk
        """
            ),
            {
                "tid": tenant_id,
                "uk": user_key,
                "lang": get_lang(c.get("lang")),
                "state": c.get("state") or "NEW",
                "service": c.get("service"),
                "name": c.get("name"),
                "dtiso": c.get("datetime_iso"),
                "tt": sanitize_conversation_time_text(c.get("time_text")),
                "pj": pending_json,
            },
        )
