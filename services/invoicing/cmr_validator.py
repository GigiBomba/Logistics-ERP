"""CMR data validator — ensures all mandatory fields are present and values are sane
before PDF generation. Returns a list of (severity, field, message) tuples.

Severity levels:
    "error"   — blocks generation (mandatory missing, invalid numeric)
    "warning" — advisory (suboptimal but acceptable)
"""
from __future__ import annotations


import re
from typing import Any, Optional

MANDATORY_FIELDS = [
    ("consignor_name", "Consignor (Sender) name"),
    ("client_name", "Consignee name"),
    ("place_of_loading", "Place of loading"),
    ("place_of_delivery", "Place of delivery"),
    ("cargo_description", "Nature of goods"),
    ("carrier_name", "Carrier name"),
    ("truck_plate", "Vehicle plate"),
]

NUMERIC_FIELDS_POSITIVE = [
    ("package_count", "Package count", int),
    ("gross_weight_kg", "Gross weight (kg)", float),
]

# ── Real-time per-field validation rules ──────────────────────────
# Numeric key-validated fields: regex that every typed character must satisfy
KEY_NUMERIC_FIELDS = {
    "package_count":     r"^\d*$",
    "gross_weight_kg":     r"^\d*\.?\d*$",
    "volume_m3":           r"^\d*\.?\d*$",
    "cod_amount":          r"^\d*\.?\d*$",
    "carriage_sender":     r"^\d*\.?\d*$",
    "carriage_consignee":  r"^\d*\.?\d*$",
    "supplementary_sender":    r"^\d*\.?\d*$",
    "supplementary_consignee": r"^\d*\.?\d*$",
    "customs_sender":      r"^\d*\.?\d*$",
    "customs_consignee":   r"^\d*\.?\d*$",
    "other_sender":        r"^\d*\.?\d*$",
    "other_consignee":     r"^\d*\.?\d*$",
}

# FocusOut-validated fields: full pattern must match when leaving field
BLUR_FORMAT_FIELDS = {
    "place_of_loading_date": (r"^\d{4}-\d{2}-\d{2}$",
                              "Date must be YYYY-MM-DD"),
    "issue_date":            (r"^\d{4}-\d{2}-\d{2}$",
                              "Date must be YYYY-MM-DD"),
    "delivery_country":      (r"^[A-Za-z]{2}$",
                              "Use 2-letter ISO country code"),
    "loading_country":       (r"^[A-Za-z]{2}$",
                              "Use 2-letter ISO country code"),
    "hs_code":               (r"^\d{4,6}(\.\d{2,4})?$",
                              "HS code: e.g. 8708.99"),
}


class FieldValidator:
    """Real-time field validator for CMR form inputs.

    Usage:
        v = FieldValidator()
        is_ok = v.validate_keystroke("package_count", new_value_after_char)
        err_msg = v.validate_blur("issue_date", "2026-06-07")  # None if ok
    """

    def __init__(self):
        self._num_patterns = {}
        for key, pat in KEY_NUMERIC_FIELDS.items():
            self._num_patterns[key] = re.compile(pat)

    def validate_keystroke(self, field_key: str, proposed_value: str) -> bool:
        """Return True if proposed_value is acceptable for field_key."""
        pattern = self._num_patterns.get(field_key)
        if pattern is None:
            return True  # no rule for this field
        return bool(pattern.match(proposed_value))

    def validate_blur(self, field_key: str, value: str) -> Optional[str]:
        """Return error message if value fails format check, else None."""
        rule = BLUR_FORMAT_FIELDS.get(field_key)
        if rule is None:
            return None
        pattern, error_msg = rule
        value = (value or "").strip()
        if not value:
            return None  # empty is not an error during typing
        if not re.match(pattern, value):
            return error_msg
        return None

    def field_has_numeric_rule(self, field_key: str) -> bool:
        return field_key in self._num_patterns

    def field_has_blur_rule(self, field_key: str) -> bool:
        return field_key in BLUR_FORMAT_FIELDS


def validate_cmr(data: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Validate CMR trip data. Returns list of (severity, field, message)."""
    issues = []

    if not isinstance(data, dict):
        return [("error", "__root__", "CMR data must be a dictionary")]

    for key, label in MANDATORY_FIELDS:
        value = data.get(key, "")
        # Special case: place_of_delivery can also be stored as "destination"
        if key == "place_of_delivery" and not value:
            value = data.get("destination", "")
        if not value or (isinstance(value, str) and not value.strip()):
            issues.append(("error", key, f"{label} is mandatory"))

    for key, label, _ in NUMERIC_FIELDS_POSITIVE:
        raw = data.get(key, "")
        if raw and raw != "—":
            try:
                val = float(raw)
                if val <= 0:
                    issues.append(("error", key, f"{label} must be positive"))
            except (ValueError, TypeError):
                issues.append(("error", key, f"{label} is not a valid number"))

    if data.get("volume_m3"):
        try:
            v = float(data["volume_m3"])
            if v < 0:
                issues.append(("error", "volume_m3", "Volume cannot be negative"))
        except (ValueError, TypeError):
            issues.append(("error", "volume_m3", "Volume is not a valid number"))

    payer = str(data.get("carriage_payer", "")).lower()
    if payer and payer not in ("sender", "consignee"):
        issues.append(("warning", "carriage_payer",
                       f"Unexpected payer value '{payer}'; expected 'Sender' or 'Consignee'"))

    cod_raw = data.get("cod_amount", "")
    if cod_raw:
        try:
            cod_val = float(cod_raw)
            if cod_val <= 0:
                issues.append(("error", "cod_amount", "COD amount must be positive"))
        except (ValueError, TypeError):
            issues.append(("error", "cod_amount", "COD amount is not a valid number"))

    if not data.get("hs_code"):
        issues.append(("warning", "hs_code", "HS customs code is missing (recommended)"))

    if data.get("distance_km"):
        try:
            d = float(data["distance_km"])
            if d <= 0:
                issues.append(("warning", "distance_km", "Distance should be positive"))
        except (ValueError, TypeError):
            pass

    return issues


def has_errors(issues: list[tuple[str, str, str]]) -> bool:
    return any(sev == "error" for sev, _, _ in issues)


def format_issues(issues: list[tuple[str, str, str]]) -> str:
    """Format validation issues for display in a messagebox."""
    if not issues:
        return ""
    errors = [f"  [{sev.upper()}] {msg}" for sev, _, msg in issues]
    return "\n".join(errors)
