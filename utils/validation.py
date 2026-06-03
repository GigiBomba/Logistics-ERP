import re
from typing import Any, Optional


def validate_plate(plate: str) -> bool:
    return bool(re.match(r"^[A-Z0-9]{2,10}$", plate.strip().upper()))


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def validate_positive_number(value: Any) -> Optional[float]:
    try:
        v = float(value)
        if v > 0:
            return v
    except (ValueError, TypeError):
        pass
    return None
