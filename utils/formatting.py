from datetime import datetime
from typing import Any, Dict, Optional


def format_currency(value: float, decimals: int = 2, symbol: str = "€") -> str:
    return f"{value:,.{decimals}f}{symbol}"


def format_duration(minutes: float) -> str:
    """Human-readable day / hour / minute breakdown (no i18n, short form)."""
    total = int(abs(float(minutes or 0)))
    if total == 0:
        return "0 min"
    days = total // 1440
    remainder = total % 1440
    hours = remainder // 60
    mins = remainder % 60
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if mins > 0 or not parts:
        parts.append(f"{mins}min")
    return " ".join(parts)


def format_distance(km: float, decimals: int = 1) -> str:
    return f"{km:,.{decimals}f} km"


def format_percentage(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"
