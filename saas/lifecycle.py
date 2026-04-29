from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from core.parsing_time import now_ts, parse_dt_any_tz
from config.settings import TRIAL_END_ISO_FALLBACK

SAAS_TENANT_FIELDS = {
    "onboarding_completed": False,
    "google_connected": False,
    "subscription_status": "trial",
    "plan": "starter",
    "owner_email": "",
}

LIFECYCLE_STATUS_ALIASES = {
    "enabled": "active",
    "paid": "active",
    "live": "active",
    "due": "past_due",
    "payment_failed": "past_due",
    "paused": "inactive",
    "disabled": "inactive",
    "cancelled": "inactive",
    "canceled": "inactive",
    "expired": "expired",
}

ALLOWED_SUBSCRIPTION_STATUSES = {"trial", "active", "past_due", "inactive", "expired"}

PLAN_ALIASES = {
    "growth": "pro",
    "enterprise": "business",
}

PLAN_CATALOG = {
    "starter": {
        "display_name": "Starter",
        "dialogs_per_month": 300,
        "llm_calls_per_month": 0,
        "llm_mode": "off",
        "includes_advanced_ai": False,
        "monthly_price": 0,
        "features": ["Basic booking flow", "Calendar integration", "SMS / WhatsApp support"],
    },
    "pro": {
        "display_name": "Pro",
        "dialogs_per_month": 1000,
        "llm_calls_per_month": 800,
        "llm_mode": "smart",
        "includes_advanced_ai": True,
        "monthly_price": 0,
        "features": ["Smarter routing", "FAQ support", "Priority SaaS limits"],
    },
    "ai": {
        "display_name": "AI",
        "dialogs_per_month": 2000,
        "llm_calls_per_month": 2500,
        "llm_mode": "full",
        "includes_advanced_ai": True,
        "monthly_price": 0,
        "features": ["Advanced LLM flows", "Higher monthly capacity", "Deeper AI coverage"],
    },
    "business": {
        "display_name": "Business",
        "dialogs_per_month": 3000,
        "llm_calls_per_month": 5000,
        "llm_mode": "full",
        "includes_advanced_ai": True,
        "monthly_price": 0,
        "features": ["High volume usage", "Multi-channel scale", "Business-grade limits"],
    },
}


def normalized_plan_name(value: Any) -> str:
    plan = str(value or "starter").strip().lower() or "starter"
    plan = PLAN_ALIASES.get(plan, plan)
    if plan not in PLAN_CATALOG:
        return "starter"
    return plan


def available_plan_catalog() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for plan_key, meta in PLAN_CATALOG.items():
        item = dict(meta)
        item["plan"] = plan_key
        out[plan_key] = item
    return out


def tenant_plan_defaults(tenant: Dict[str, Any]) -> Dict[str, Any]:
    plan = normalized_plan_name((tenant or {}).get("plan"))
    defaults = dict(PLAN_CATALOG.get(plan, PLAN_CATALOG["starter"]))
    defaults["plan"] = plan
    return defaults


def tenant_effective_dialog_limit(tenant: Dict[str, Any], defaults: Optional[Dict[str, Any]] = None) -> Tuple[int, bool]:
    defaults = dict(defaults or tenant_plan_defaults(tenant))
    raw_dialog_limit = (tenant or {}).get("dialogs_per_month")
    try:
        if raw_dialog_limit in (None, ""):
            return max(0, int(defaults.get("dialogs_per_month") or 0)), False
        return max(0, int(raw_dialog_limit or 0)), True
    except Exception:
        return max(0, int(defaults.get("dialogs_per_month") or 0)), False


def normalize_subscription_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    raw = LIFECYCLE_STATUS_ALIASES.get(raw, raw)
    if raw in ALLOWED_SUBSCRIPTION_STATUSES:
        return raw
    return "trial"


def normalize_tenant_saas_fields(tenant: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure SaaS lifecycle fields exist so older tenants do not break."""
    if not tenant:
        return tenant
    for k, v in SAAS_TENANT_FIELDS.items():
        if k not in tenant or tenant.get(k) is None:
            tenant[k] = v
    tenant["subscription_status"] = normalize_subscription_status(tenant.get("subscription_status"))
    tenant["plan"] = normalized_plan_name(tenant.get("plan")) if "plan" in tenant else "starter"
    return tenant


def tenant_trial_end_value(tenant: Dict[str, Any]) -> Optional[datetime]:
    te = (tenant or {}).get("trial_end") or (tenant or {}).get("trial_end_at")
    dt = parse_dt_any_tz(te) if isinstance(te, str) else te
    if not dt:
        dt = parse_dt_any_tz(TRIAL_END_ISO_FALLBACK)
    return dt


def effective_subscription_status(tenant: Dict[str, Any]) -> str:
    tenant = normalize_tenant_saas_fields(tenant or {})
    status = normalize_subscription_status(tenant.get("subscription_status"))
    if status == "trial":
        trial_end = tenant_trial_end_value(tenant)
        if trial_end and now_ts() > trial_end:
            return "expired"
    return status


def tenant_lifecycle_payload(tenant: Dict[str, Any]) -> Dict[str, Any]:
    tenant = normalize_tenant_saas_fields(tenant or {})
    trial_end = tenant_trial_end_value(tenant)
    subscription_status = normalize_subscription_status(tenant.get("subscription_status"))
    effective_status = effective_subscription_status(tenant)
    blocked = effective_status in {"inactive", "expired"}
    if effective_status == "past_due":
        blocked = False
    return {
        "subscription_status": subscription_status,
        "effective_status": effective_status,
        "trial_end": trial_end.isoformat() if hasattr(trial_end, "isoformat") else None,
        "blocked": blocked,
        "block_reason": "trial_expired" if effective_status == "expired" and subscription_status == "trial" else effective_status if blocked else None,
    }
