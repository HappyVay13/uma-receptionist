import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import text

from core.parsing_time import now_ts
from db.database import engine
from saas.lifecycle import normalize_tenant_saas_fields

log = logging.getLogger("repliq")


def tenants_columns() -> List[Dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
            SELECT column_name, is_nullable, column_default, data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='tenants'
            ORDER BY ordinal_position
        """
            )
        ).fetchall()
    return [
        {"name": r[0], "nullable": (r[1] == "YES"), "default": r[2], "type": r[3]}
        for r in rows
    ]


def tenants_pk(cols: List[Dict[str, Any]]) -> str:
    names = {c["name"] for c in cols}
    if "id" in names:
        return "id"
    if "tenant_id" in names:
        return "tenant_id"
    return "id"


def get_existing_tenant(tenant_id: str) -> Dict[str, Any]:
    tenant_id = (tenant_id or "").strip()
    if not tenant_id:
        return {}
    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = [c["name"] for c in cols]
    select_cols = ", ".join(col_names)
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {select_cols} FROM tenants WHERE {pk}=:tid LIMIT 1"),
            {"tid": tenant_id},
        ).fetchone()
    if not row:
        return {}
    out: Dict[str, Any] = {"_id": tenant_id}
    for i, name in enumerate(col_names):
        out[name] = row[i]
    return normalize_tenant_saas_fields(out)


def get_tenant_or_404(tenant_id: str) -> Dict[str, Any]:
    tenant = get_existing_tenant(tenant_id)
    if not tenant.get("_id"):
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def upsert_tenant_google_account(
    tenant_id: str,
    google_email: Optional[str],
    access_token: str,
    refresh_token: Optional[str],
    token_expiry: Optional[datetime],
    scope: Optional[str],
) -> None:
    tenant_id = (tenant_id or "").strip()
    if not tenant_id:
        return
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM tenant_google_accounts WHERE tenant_id=:tid"), {"tid": tenant_id})
        conn.execute(
            text(
                """
                INSERT INTO tenant_google_accounts
                (tenant_id, google_email, access_token, refresh_token, token_expiry, scope, created_at, updated_at)
                VALUES
                (:tid, :google_email, :access_token, :refresh_token, :token_expiry, :scope, NOW(), NOW())
                """
            ),
            {
                "tid": tenant_id,
                "google_email": google_email,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expiry": token_expiry,
                "scope": scope,
            },
        )


def get_tenant_google_account(tenant_id: str) -> Dict[str, Any]:
    tenant_id = (tenant_id or "").strip()
    if not tenant_id:
        return {}
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT tenant_id, google_email, access_token, refresh_token, token_expiry, scope, created_at, updated_at
                    FROM tenant_google_accounts
                    WHERE tenant_id=:tid
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"tid": tenant_id},
            ).fetchone()
        if not row:
            return {}
        keys = ["tenant_id", "google_email", "access_token", "refresh_token", "token_expiry", "scope", "created_at", "updated_at"]
        return {k: row[i] for i, k in enumerate(keys)}
    except Exception as e:
        log.error("get_tenant_google_account failed tenant_id=%s err=%s", tenant_id, e)
        return {}


def tenant_has_google_account(tenant_id: str) -> bool:
    acct = get_tenant_google_account(tenant_id)
    return bool(str(acct.get("access_token") or "").strip())


def tenant_google_connected_effective(tenant: Dict[str, Any]) -> bool:
    tenant = normalize_tenant_saas_fields(tenant or {})
    if bool(tenant.get("google_connected")):
        return True
    tenant_id = str(tenant.get("_id") or tenant.get("id") or "").strip()
    if not tenant_id:
        return False
    return tenant_has_google_account(tenant_id)


def mark_tenant_google_connected(tenant_id: str, is_connected: bool, owner_email: Optional[str] = None) -> None:
    tenant_id = (tenant_id or "").strip()
    if not tenant_id:
        return
    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = {c["name"] for c in cols}
    sets = []
    params: Dict[str, Any] = {"tid": tenant_id, "gc": is_connected}
    if "google_connected" in col_names:
        sets.append("google_connected=:gc")
    if owner_email and "owner_email" in col_names:
        sets.append("owner_email=:owner_email")
        params["owner_email"] = owner_email
    if tenant_has_google_account(tenant_id) and "google_connected" in col_names:
        sets.append("google_connected=true")
    if "updated_at" in col_names:
        sets.append("updated_at=NOW()")
    if not sets:
        return
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE tenants SET {', '.join(sets)} WHERE {pk}=:tid"), params)


def select_tenant_calendar_id(tenant_id: str, calendar_id: str) -> None:
    tenant_id = (tenant_id or "").strip()
    calendar_id = (calendar_id or "").strip()
    if not tenant_id or not calendar_id:
        return
    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = {c["name"] for c in cols}
    if "calendar_id" not in col_names:
        return
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE tenants SET calendar_id=:cid WHERE {pk}=:tid"), {"cid": calendar_id, "tid": tenant_id})


def sync_tenant_onboarding_state(tenant_id: str) -> Dict[str, Any]:
    tenant = get_tenant_or_404(tenant_id)
    cols = tenants_columns()
    pk = tenants_pk(cols)
    col_names = {c["name"] for c in cols}
    google_connected = tenant_google_connected_effective(tenant)
    calendar_selected = bool(str(tenant.get("calendar_id") or "").strip())
    onboarding_completed = bool(google_connected and calendar_selected)

    sets = []
    params: Dict[str, Any] = {"tid": tenant_id}
    if "google_connected" in col_names:
        sets.append("google_connected=:google_connected")
        params["google_connected"] = google_connected
    if "onboarding_completed" in col_names:
        sets.append("onboarding_completed=:onboarding_completed")
        params["onboarding_completed"] = onboarding_completed
    if "updated_at" in col_names:
        sets.append("updated_at=NOW()")

    if sets:
        with engine.begin() as conn:
            conn.execute(text(f"UPDATE tenants SET {', '.join(sets)} WHERE {pk}=:tid"), params)

    return get_tenant_or_404(tenant_id)
