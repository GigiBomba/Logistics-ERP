"""Format route calculation results and errors for the UI (no Tk)."""
from __future__ import annotations

from typing import Any

from services.currency_service import CURRENCY_SYMBOLS
from services.i18n import t

# Module-level singleton to avoid creating a new ExchangeRateService instance per call
_exchange_rate_service: Any = None
def _get_exchange_rate_service():
    global _exchange_rate_service
    if _exchange_rate_service is None:
        from services.exchange_rate_service import ExchangeRateService
        _exchange_rate_service = ExchangeRateService()
    return _exchange_rate_service

def _fmt_unit(value: int, singular_key: str, plural_key: str) -> str:
    """Return '1 day' or '2 days' using the correct i18n key."""
    return f"{value} {t(singular_key if value == 1 else plural_key)}"


def format_duration_minutes(duration_min: float) -> str:
    """Convert minutes to human-readable day / hour / minute breakdown.

    90 min  → '1 hour, 30 min'
    1500 min → '1 day, 1 hour'
    45 min   → '45 min'
    0 min    → '0 min'
    """
    total = int(abs(float(duration_min or 0)))
    if total == 0:
        return f"0 {t('result.minutes')}"

    days = total // 1440
    remainder = total % 1440
    hours = remainder // 60
    minutes = remainder % 60

    parts = []
    if days > 0:
        parts.append(_fmt_unit(days, "result.day", "result.days"))
    if hours > 0:
        parts.append(_fmt_unit(hours, "result.hour", "result.hours"))
    if minutes > 0 or not parts:
        parts.append(_fmt_unit(minutes, "result.minute", "result.minutes"))

    return ", ".join(parts)


def format_success_info(
    route: dict[str, Any],
    cost_info: dict[str, Any],
    stops_count: int,
    preferred_currency: str = "EUR",
) -> str:
    distance = float(route.get("distance_km") or 0)
    duration = float(route.get("duration_min") or 0)
    cached = route.get("cached", False)
    cache_indicator = " ⚡(cached)" if cached else ""
    lines = [
        f"✅ {t('result.distance').format(round(distance, 1))}{cache_indicator}",
        f"⏱️ {t('result.duration').format(format_duration_minutes(duration))}",
        f"📍 {t('result.stops').format(stops_count)}",
        f"⛽ {t('result.fuel').format(round(float(cost_info.get('fuel_liters') or 0), 1))}",
    ]
    if cost_info.get("fuel_cost"):
        fuel_cost = float(cost_info.get("fuel_cost") or 0)
        if preferred_currency.upper() != "EUR":
            fuel_cost = _get_exchange_rate_service().convert(fuel_cost, "EUR", preferred_currency.upper())
        symbol = CURRENCY_SYMBOLS.get(preferred_currency.upper(), preferred_currency.upper())
        lines.append(f"💰 {t('result.fuel_cost').format(f'{fuel_cost:.2f} {symbol}')}")
    return "\n".join(lines)


def format_history_loaded_info(record) -> str:
    duration = float(record.duration_min or 0)
    info = t("result.history_loaded")
    dist = t("result.distance").format(round(float(record.total_distance_km or 0), 1))
    dur = t("result.duration").format(format_duration_minutes(duration))
    return f"📂 {info}\n✅ {dist}\n⏱️ {dur}"


def parse_error_message(result: dict[str, Any]) -> tuple[str, str] | None:
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
    elif "actively refused" in lower or "connection refused" in lower or "can't connect" in lower:
        user_msg = t("result.routing_server_off")
    elif "connection" in lower:
        user_msg = t("result.connection_error").format("routing server")
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


def extract_route_from_result(result: Any) -> dict[str, Any] | None:
    if isinstance(result, dict):
        return result if result.get("distance_km") is not None else None
    if isinstance(result, list) and result:
        first = result[0]
        return first if isinstance(first, dict) else None
    return None
