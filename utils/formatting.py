from datetime import datetime
from typing import Any, Dict, Optional


def format_currency(value: float, decimals: int = 2, symbol: str = "€") -> str:
    return f"{value:,.{decimals}f}{symbol}"


def format_duration(minutes: float) -> str:
    if minutes <= 0:
        return "0 min"
    if minutes >= 1440:
        d = minutes / 1440
        return f"{d:.1f}d"
    if minutes >= 60:
        h = minutes / 60
        return f"{h:.1f}h"
    return f"{int(minutes)} min"


def format_distance(km: float, decimals: int = 1) -> str:
    return f"{km:,.{decimals}f} km"


def format_percentage(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"
