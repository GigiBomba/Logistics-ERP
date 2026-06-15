import re
from typing import Any, Optional, Tuple


def validate_plate(plate: str) -> bool:
    cleaned = re.sub(r'[\s\-_]+', '', plate.strip().upper())
    return bool(re.match(r'^[A-Z0-9]{2,12}$', cleaned))


def validate_email(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$', email.strip()))


def validate_positive_number(value: Any) -> Optional[float]:
    try:
        v = float(value)
        if v > 0:
            return v
    except (ValueError, TypeError):
        pass
    return None


def validate_plate_with_reason(plate: str) -> Tuple[bool, Optional[str]]:
    if not plate or not plate.strip():
        return False, "Plate number is empty"
    cleaned = re.sub(r'[\s\-_]+', '', plate.strip().upper())
    if not re.match(r'^[A-Z0-9]{2,12}$', cleaned):
        return False, f"Invalid plate format: '{plate}' (allowed: 2-12 alphanumeric chars)"
    return True, None


def validate_email_with_reason(email: str) -> Tuple[bool, Optional[str]]:
    if not email or not email.strip():
        return False, "Email address is empty"
    if len(email) > 254:
        return False, "Email address exceeds maximum length (254 characters)"
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$', email.strip()):
        return False, f"Invalid email format: '{email}'"
    return True, None
