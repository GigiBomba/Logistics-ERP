import math
import re
from typing import Any, Optional, Tuple

_RE_PLATE_CLEAN = re.compile(r'[\s\-_]+')
_RE_PLATE_VALID = re.compile(r'^[A-Z0-9]{2,12}$')
_RE_EMAIL_VALID = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')


def validate_plate(plate: str) -> bool:
    cleaned = _RE_PLATE_CLEAN.sub('', plate.strip().upper())
    return bool(_RE_PLATE_VALID.match(cleaned))


def validate_email(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    return bool(_RE_EMAIL_VALID.match(email.strip()))


def validate_positive_number(value: Any) -> Optional[float]:
    try:
        v = float(value)
        if math.isinf(v) or math.isnan(v):
            return None
        if v > 0:
            return v
    except (ValueError, TypeError):
        pass
    return None


def validate_plate_with_reason(plate: str) -> Tuple[bool, Optional[str]]:
    if not plate or not plate.strip():
        return False, "Plate number is empty"
    cleaned = _RE_PLATE_CLEAN.sub('', plate.strip().upper())
    if not _RE_PLATE_VALID.match(cleaned):
        return False, f"Invalid plate format: '{plate}' (allowed: 2-12 alphanumeric chars)"
    return True, None


def validate_email_with_reason(email: str) -> Tuple[bool, Optional[str]]:
    if not email or not email.strip():
        return False, "Email address is empty"
    if len(email) > 254:
        return False, "Email address exceeds maximum length (254 characters)"
    if not _RE_EMAIL_VALID.match(email.strip()):
        return False, f"Invalid email format: '{email}'"
    return True, None
