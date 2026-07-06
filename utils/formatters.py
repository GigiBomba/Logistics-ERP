"""Data formatting utilities for Operion ERP.

All user-visible numbers must pass through these formatters — no raw
float-to-string conversions in the UI layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

# Color constants (local copies avoid circular via ui.design_tokens)
_COLOR_SUCCESS_TEXT = "#34D399"
_COLOR_ERROR_TEXT = "#F87171"
_COLOR_TEXT_SECONDARY = "#8E8EA0"


def fmt_currency(value: float, currency: str = "€", decimals: int = 2) -> str:
    """Format as '€ 39 563.00' with space thousands separator."""
    if value is None:
        value = 0.0
    value = float(value)
    sign = "-" if value < 0 else ""
    abs_val = abs(value)
    formatted = f"{abs_val:,.{decimals}f}"
    formatted = formatted.replace(",", " ")
    return f"{sign}{currency} {formatted}"


def fmt_distance(km: float) -> str:
    """Format as '4 734 km' (integer, space thousands separator)."""
    if km is None:
        km = 0.0
    val = round(float(km))
    return f"{val:,.0f} km".replace(",", " ")


def fmt_rate(value: float) -> str:
    """Format as '€ 0.97/km' (2 decimal places max)."""
    if value is None:
        value = 0.0
    return f"€ {float(value):.2f}/km"


def fmt_date(date_str: str) -> str:
    """Convert '2026-06-19' to '19.06.2026'."""
    if not date_str:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y"):
        try:
            dt = datetime.strptime(str(date_str).strip(), fmt)
            return dt.strftime("%d.%m.%Y")
        except ValueError:
            continue
    return str(date_str)


def fmt_profit_color(value: float) -> str:
    """Return appropriate color token for profit value."""
    if value > 0:
        return _COLOR_SUCCESS_TEXT
    if value < 0:
        return _COLOR_ERROR_TEXT
    return _COLOR_TEXT_SECONDARY


def fmt_number(value: float, decimals: int = 2) -> str:
    """Generic number with space thousands separator and fixed decimals."""
    if value is None:
        value = 0.0
    formatted = f"{value:,.{decimals}f}"
    formatted = formatted.replace(",", " ")
    return formatted


def fmt_percentage(value: float, decimals: int = 1) -> str:
    """Percentage with given decimal places."""
    if value is None:
        value = 0.0
    return f"{value:.{decimals}f}%"
