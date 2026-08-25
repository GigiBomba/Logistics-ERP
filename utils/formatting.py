from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from utils.formatters import (
    fmt_currency as _fmt_currency,
    fmt_distance as _fmt_distance,
    fmt_date as _fmt_date,
    fmt_percentage as _fmt_percentage,
    fmt_number,
)


def format_currency(value: float, decimals: int = 2, symbol: str = "€") -> str:
    """Backward-compatible wrapper around fmt_currency."""
    return _fmt_currency(value, currency=symbol, decimals=decimals)


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
    """Backward-compatible wrapper. Uses integer km when decimals=0, otherwise legacy."""
    if decimals == 0:
        return _fmt_distance(km)
    return f"{km:,.{decimals}f} km"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Backward-compatible wrapper around fmt_percentage."""
    return _fmt_percentage(value, decimals=decimals)


def format_age(seconds: Optional[float]) -> str:
    """Human-readable age from seconds: '30s', '5m', '2.5h', 'never' for None."""
    if seconds is None:
        return "never"
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds/60:.0f}m"
    return f"{seconds/3600:.1f}h"
