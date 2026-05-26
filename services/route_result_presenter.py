"""Format route calculation results and errors for the UI (no Tk)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from services.i18n import t


def format_duration_minutes(duration_min: float) -> str:
    duration = float(duration_min or 0)
    if duration >= 1440:
        return f"{duration / 1440:.1f} {t('result.days')}"
    if duration >= 60:
        return f"{duration / 60:.1f} {t('result.hours')}"
    return f"{duration:.0f} {t('result.minutes')}"


def format_success_info(
    route: Dict[str, Any],
    cost_info: Dict[str, Any],
    stops_count: int,
) -> str:
    distance = float(route.get("distance_km") or 0)
    duration = float(route.get("duration_min") or 0)
    cached = route.get("cached", False)
    cache_indicator = " ⚡(cached)" if cached else ""
    lines = [
        f"✅ {t('result.distance').format(distance)}{cache_indicator}",
        f"⏱️ {t('result.duration').format(format_duration_minutes(duration))}",
        f"📍 {t('result.stops').format(stops_count)}",
        f"⛽ {t('result.fuel').format(float(cost_info.get('fuel_liters') or 0))}",
    ]
    if cost_info.get("fuel_cost"):
        lines.append(f"💰 {t('result.fuel_cost').format(float(cost_info.get('fuel_cost') or 0))}")
    return "\n".join(lines)


def format_history_loaded_info(record) -> str:
    duration = float(record.duration_min or 0)
    info = t("result.history_loaded")
    dist = t("result.distance").format(float(record.total_distance_km or 0))
    dur = t("result.duration").format(format_duration_minutes(duration))
    return f"📂 {info}\n✅ {dist}\n⏱️ {dur}"


def parse_error_message(result: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """Return (user_message, severity) or None if not an error dict."""
    if not isinstance(result, dict) or not result.get("error"):
        return None
    error_type = result.get("error_type", "Error")
    error_msg = str(result.get("error", "Unknown error"))
    lower = error_msg.lower()

    if "timeout" in lower:
        user_msg = t("result.timeout_error")
    elif "geocode" in lower or "could not geocode" in lower:
        user_msg = f"📍 {t('result.geocode_error')}:\n{error_msg}"
    elif "connection" in lower:
        user_msg = t("result.connection_error").format("192.168.0.93:8989")
    elif "invalid" in lower or "coordinates" in lower:
        user_msg = f"📍 {t('result.invalid_coords')}:\n{error_msg}"
    elif "too far" in lower or "not found" in lower:
        user_msg = t("result.route_not_found_msg")
    elif "at least 2" in lower:
        user_msg = f"📍 {t('result.need_2_stops')}"
    elif "duplicate" in lower:
        user_msg = f"📍 {t('result.duplicate_stops')}"
    else:
        user_msg = t("result.generic_error").format(error_type, error_msg)
    return user_msg, "danger"


def extract_route_from_result(result: Any) -> Optional[Dict[str, Any]]:
    if isinstance(result, list) and result:
        first = result[0]
        return first if isinstance(first, dict) else None
    return None
