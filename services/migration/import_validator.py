"""Per-field validation pipeline for import rows.

Reuses ``utils.validation`` where possible and provides entity-specific
field schemas defining required and optional fields.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from services.migration.types import EntityType

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")


class ImportValidator:
    """Validates individual rows against entity-specific field schemas.

    Usage::

        validator = ImportValidator()
        is_valid, errors, cleaned = validator.validate_row(row, EntityType.CLIENT)
    """

    FIELD_SCHEMA: dict[EntityType, dict[str, list[str]]] = {
        EntityType.CLIENT: {
            "required": ["name"],
            "optional": [
                "phone", "email", "address", "vat_number",
                "country", "currency_preference", "notes", "eori_number",
                "contact_person", "is_active",
            ],
        },
        EntityType.DRIVER: {
            "required": ["name"],
            "optional": [
                "phone", "email", "license_number", "license_category",
                "license_expiry", "medical_expiry", "hire_date",
                "monthly_salary", "notes", "is_active",
                "passport_number", "passport_expiry",
                "adr_certificate", "adr_certificate_expiry",
                "driver_card_number",
            ],
        },
        EntityType.TRUCK: {
            "required": ["plate_number"],
            "optional": [
                "manufacturer", "model", "year", "vin",
                "fuel_consumption", "mileage", "monthly_rate", "status",
                "insurance_expiry", "inspection_expiry", "maintenance_due",
                "tachograph_expiry", "active_status", "trailer_plate",
                "max_payload_kg", "odometer_km",
            ],
        },
        EntityType.TRIP: {
            "required": ["truck_number"],
            "optional": [
                "truck_number", "driver_name", "client_name",
                "distance_km", "total_price_eur", "rate_per_km",
                "start_date", "end_date", "status",
                "loading_country", "delivery_country",
                "cmr_number", "cargo_description",
                "place_of_loading", "place_of_loading_date",
                "gross_weight_kg", "volume_m3", "package_count",
                "package_type",
            ],
        },
        EntityType.DOCUMENT: {
            "required": ["title", "file_path"],
            "optional": [
                "category", "entity_type", "entity_id",
                "description", "tags", "uploaded_by",
                "copy_type", "cmr_number", "is_signed",
            ],
        },
        EntityType.INVOICE: {
            "required": ["invoice_number"],
            "optional": [
                "trip_id", "issue_date", "due_date",
                "total_amount", "status",
            ],
        },
    }

    def validate_row(
        self,
        row: dict[str, Any],
        entity_type: EntityType,
    ) -> tuple[bool, list[str], dict[str, Any]]:
        """Validate a single row against the entity field schema.

        Returns:
            Tuple of ``(is_valid, errors, cleaned_row)`` where *cleaned_row*
            contains only recognised fields with per-field validation applied.
        """
        errors: list[str] = []
        cleaned: dict[str, Any] = {}
        schema = self.FIELD_SCHEMA.get(entity_type, {"required": [], "optional": []})
        allowed_fields = set(schema["required"] + schema["optional"])

        # ── Check required fields ──────────────────────────────────────
        for field in schema["required"]:
            value = row.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"Missing required field: '{field}'")

        # ── Validate and clean known fields ────────────────────────────
        for field, value in row.items():
            if field not in allowed_fields:
                continue
            if value is None:
                continue

            cleaned[field] = value

            # Per-field type / format validation
            if field == "email":
                is_valid_email, email_err = self._validate_email(value)
                if not is_valid_email:
                    errors.append(f"Invalid email '{value}': {email_err}")
                    cleaned.pop(field, None)

            elif field == "phone":
                is_valid_phone, phone_err = self._validate_phone(value)
                if not is_valid_phone:
                    errors.append(f"Invalid phone '{value}': {phone_err}")
                    cleaned.pop(field, None)

            elif field in ("year",):
                is_valid_yr, yr_err = self._validate_year(value)
                if not is_valid_yr:
                    errors.append(f"Invalid year '{value}': {yr_err}")
                    cleaned.pop(field, None)

        return len(errors) == 0, errors, cleaned

    # ── Per-field validators ───────────────────────────────────────────

    @staticmethod
    def _validate_email(value: Any) -> tuple[bool, str]:
        """Validate email format reusing the project's utility."""
        try:
            from utils.validation import validate_email_with_reason

            ok, reason = validate_email_with_reason(str(value))
            return ok, reason or ""
        except ImportError:
            pass
        # Fallback inline validation
        email = str(value).strip()
        if not email:
            return False, "Email address is empty"
        if len(email) > 254:
            return False, "Email address exceeds maximum length (254 characters)"
        import re as _re

        if not _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$", email):
            return False, f"Invalid email format: '{email}'"
        return True, ""

    @staticmethod
    def _validate_phone(value: Any) -> tuple[bool, str]:
        """Validate phone number format."""
        phone = str(value).strip()
        if not phone:
            return False, "Phone number is empty"
        if not _PHONE_RE.match(phone):
            return False, f"Invalid phone format: '{phone}' (allowed: + and 7-20 digits/dashes/spaces)"
        return True, ""

    @staticmethod
    def _validate_year(value: Any) -> tuple[bool, str]:
        """Validate a year value is in the 1900–2035 range."""
        try:
            year = int(str(value).strip())
        except (ValueError, TypeError):
            return False, f"Not a valid integer: '{value}'"
        if year < 1900 or year > 2035:
            return False, f"Year {year} is out of range (1900–2035)"
        return True, ""
