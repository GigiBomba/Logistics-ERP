from datetime import datetime, timedelta
from typing import Optional


def parse_date(date_str: str, fmt: str = "%d/%m/%Y") -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], fmt)
    except (ValueError, TypeError):
        return None


def format_date(dt: datetime, fmt: str = "%d/%m/%Y") -> str:
    return dt.strftime(fmt)


def days_ago(date_str: str, fmt: str = "%d/%m/%Y") -> Optional[int]:
    dt = parse_date(date_str, fmt)
    if dt is None:
        return None
    return (datetime.now() - dt).days


def is_expired(date_str: str, fmt: str = "%d/%m/%Y") -> bool:
    days = days_ago(date_str, fmt)
    if days is None:
        return False
    return days > 0
