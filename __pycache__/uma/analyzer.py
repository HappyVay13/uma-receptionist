from __future__ import annotations

from typing import Any, Dict

from uma.memory import build_business_memory_candidates
from uma.recommendations import build_uma_recommendations
from uma.signals import build_uma_signals


def build_uma_insights(engine, tenant: Dict[str, Any], days: int = 14) -> Dict[str, Any]:
    signals_payload = build_uma_signals(engine, tenant, days=days)
    recommendations_payload = build_uma_recommendations(engine, tenant, days=days)
    return {
        "tenant_id": signals_payload.get("tenant_id"),
        "window_days": signals_payload.get("window_days"),
        "summary": signals_payload.get("summary") or {},
        "signals": signals_payload.get("signals") or [],
        "top_services": signals_payload.get("top_services") or [],
        "channels": signals_payload.get("channels") or [],
        "intents": signals_payload.get("intents") or [],
        "memory_candidates": build_business_memory_candidates(signals_payload),
        "recommendations": recommendations_payload.get("recommendations") or [],
    }
