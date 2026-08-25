from __future__ import annotations

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


def validate_iban(iban: str) -> bool:
    """Validate IBAN (International Bank Account Number) using format + checksum."""
    if not iban:
        return True  # optional field
    cleaned = iban.strip().upper().replace(" ", "").replace("-", "")
    if not re.match(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}$", cleaned):
        return False
    reordered = cleaned[4:] + cleaned[:4]
    numeric = ""
    for c in reordered:
        numeric += c if c.isdigit() else str(ord(c) - 55)
    try:
        return int(numeric) % 97 == 1
    except (ValueError, OverflowError):
        return False


def validate_bic(bic: str) -> bool:
    """Validate BIC/SWIFT code format (6 + optional 3 chars)."""
    if not bic:
        return True  # optional field
    cleaned = bic.strip().upper().replace(" ", "")
    return bool(re.match(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$", cleaned))


def validate_bank_account(account: str) -> bool:
    """Validate local bank account number format."""
    if not account:
        return True  # optional field
    cleaned = account.strip().replace(" ", "").replace("-", "")
    return bool(re.match(r"^[A-Z0-9]{8,20}$", cleaned.upper()))


def validate_payment_info(info: dict) -> list:
    """Validate payment info dict — requires at least bank_account or IBAN."""
    errors = []
    has_account = bool(info.get("bank_account", "").strip())
    has_iban = bool(info.get("iban", "").strip())
    if not has_account and not has_iban:
        errors.append("Either bank account or IBAN is required")
    if info.get("iban"):
        if not validate_iban(info["iban"]):
            errors.append("Invalid IBAN format")
    if info.get("bank_bic"):
        if not validate_bic(info["bank_bic"]):
            errors.append("Invalid BIC/SWIFT format")
    if info.get("bank_account") and not has_account:
        if not validate_bank_account(info["bank_account"]):
            errors.append("Invalid bank account format")
    return errors
