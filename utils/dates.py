from datetime import datetime, timedelta
from typing import Optional


def parse_date(date_str: str, fmt: str = "%Y-%m-%d") -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], fmt)
    except (ValueError, TypeError):
        return None


def parse_date_safe(date_str: str) -> Optional[datetime]:
    """Parse date in either ISO or DD/MM/YYYY format for transition support."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str.strip()[:len(fmt)], fmt)
        except (ValueError, IndexError):
            continue
    return None


def format_date(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
    return dt.strftime(fmt)


def format_date_for_display(dt: datetime) -> str:
    """Format date for UI display using locale standard (DD/MM/YYYY)."""
    return dt.strftime("%d/%m/%Y")


def days_ago(date_str: str, fmt: str = "%Y-%m-%d") -> Optional[int]:
    dt = parse_date(date_str, fmt)
    if dt is None:
        return None
    return (datetime.now() - dt).days


def is_expired(date_str: str, fmt: str = "%Y-%m-%d") -> bool:
    days = days_ago(date_str, fmt)
    if days is None:
        return False
    return days > 0
