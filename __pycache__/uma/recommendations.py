from __future__ import annotations

from typing import Any, Dict, List

from uma.signals import build_uma_signals


def _rec(priority: str, area: str, title: str, why: str, action: str) -> Dict[str, str]:
    return {"priority": priority, "area": area, "title": title, "why": why, "action": action}


def build_uma_recommendations(engine, tenant: Dict[str, Any], days: int = 14) -> Dict[str, Any]:
    signals_payload = build_uma_signals(engine, tenant, days=days)
    summary = signals_payload.get("summary") or {}
    signals = {str(s.get("type")): s for s in signals_payload.get("signals") or []}
    recommendations: List[Dict[str, str]] = []

    if "low_data" in signals:
        recommendations.append(_rec(
            "medium",
            "data",
            "Run more real conversations before judging performance",
            "UMA needs enough real client messages to detect useful patterns.",
            "Test 10-20 realistic booking, FAQ, cancel, and reschedule conversations across RU/LV/EN.",
        ))

    if "missed_demand" in signals:
        recommendations.append(_rec(
            "high",
            "availability",
            "Review unavailable-time replies and business hours",
            "Several clients hit busy/recovery/no-booking states. This can mean demand exists but the system cannot convert it.",
            "Check working hours, breaks, service durations, buffer minutes, and suggested alternative slots.",
        ))

    if "low_booking_conversion" in signals:
        recommendations.append(_rec(
            "high",
            "conversion",
            "Shorten the path from first message to booking confirmation",
            "Booking conversion is low compared with total dialogues.",
            "Make the first booking response ask for only the missing piece: service, day, or time — not all at once.",
        ))

    if "faq_pressure" in signals:
        recommendations.append(_rec(
            "medium",
            "knowledge",
            "Turn repeated questions into tenant business memory",
            "Clients are asking info questions often. These should become structured FAQ/business rules.",
            "Add prices, address, parking, service durations, cancellation rules, and popular services into business_memory and service_catalog_json.",
        ))

    if "conversation_friction" in signals:
        recommendations.append(_rec(
            "medium",
            "dialogue",
            "Improve clarification prompts",
            "Many conversations remain in need_more/reschedule_wait states.",
            "Make prompts more specific and offer clickable/numbered options for chat channels.",
        ))

    top_services = signals_payload.get("top_services") or []
    if top_services:
        first = top_services[0]
        recommendations.append(_rec(
            "low",
            "growth",
            "Use the most booked service as the default sales path",
            f"The leading booked service is {first.get('service')}.",
            "Show this service first in onboarding, dashboard examples, demo flows, and upsell prompts.",
        ))

    if not recommendations:
        recommendations.append(_rec(
            "low",
            "operations",
            "No major issues detected in this window",
            "UMA did not find strong negative signals yet.",
            "Keep collecting data and compare booking rate, friction events, and FAQ pressure weekly.",
        ))

    return {
        "tenant_id": signals_payload.get("tenant_id"),
        "window_days": signals_payload.get("window_days"),
        "summary": summary,
        "recommendations": recommendations,
    }
