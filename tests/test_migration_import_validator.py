"""Unit tests for ImportValidator — per-entity field validation."""
from __future__ import annotations

import pytest

from services.migration.types import EntityType
from tests.test_helpers import make_db


@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def validator(db):
    from services.migration.import_validator import ImportValidator

    return ImportValidator()


class TestFieldSchema:
    """Verify FIELD_SCHEMA covers all entity types."""

    def test_has_all_six_entity_types(self, validator):
        assert len(validator.FIELD_SCHEMA) == 6
        for entity in EntityType:
            assert entity in validator.FIELD_SCHEMA, f"Missing schema for {entity}"

    def test_each_entity_has_required_and_optional(self, validator):
        for entity, schema in validator.FIELD_SCHEMA.items():
            assert "required" in schema, f"{entity} missing required"
            assert "optional" in schema, f"{entity} missing optional"
            assert isinstance(schema["required"], list)
            assert isinstance(schema["optional"], list)

    def test_clients_required_includes_name(self, validator):
        schema = validator.FIELD_SCHEMA[EntityType.CLIENT]
        assert "name" in schema["required"]

    def test_drivers_required_includes_name(self, validator):
        schema = validator.FIELD_SCHEMA[EntityType.DRIVER]
        assert "name" in schema["required"]

    def test_trucks_required_includes_plate_number(self, validator):
        schema = validator.FIELD_SCHEMA[EntityType.TRUCK]
        assert "plate_number" in schema["required"]

    def test_trips_required_includes_truck_number(self, validator):
        schema = validator.FIELD_SCHEMA[EntityType.TRIP]
        assert "truck_number" in schema["required"]

    def test_documents_has_required_fields(self, validator):
        schema = validator.FIELD_SCHEMA[EntityType.DOCUMENT]
        assert "title" in schema["required"]
        assert "file_path" in schema["required"]

    def test_invoices_required_includes_invoice_number(self, validator):
        schema = validator.FIELD_SCHEMA[EntityType.INVOICE]
        assert "invoice_number" in schema["required"]


class TestValidateRow:
    """Test validate_row returns (bool, list[str], dict) tuple."""

    def test_return_type(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "Test"}, EntityType.CLIENT
        )
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)
        assert isinstance(cleaned, dict)

    def test_valid_client(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "Test Client"}, EntityType.CLIENT
        )
        assert is_valid is True
        assert errors == []
        assert cleaned == {"name": "Test Client"}

    def test_missing_client_name(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"email": "test@test.com"}, EntityType.CLIENT
        )
        assert is_valid is False
        assert any("name" in e for e in errors)

    def test_empty_client_name(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": ""}, EntityType.CLIENT
        )
        assert is_valid is False
        assert any("name" in e for e in errors)

    def test_whitespace_client_name(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "   "}, EntityType.CLIENT
        )
        assert is_valid is False
        assert any("name" in e for e in errors)

    # ── Email validation ──────────────────────────────────────────────

    def test_valid_email(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "Test", "email": "test@example.com"}, EntityType.CLIENT
        )
        assert is_valid is True
        assert cleaned.get("email") == "test@example.com"

    def test_invalid_email_format(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "Test", "email": "not-an-email"}, EntityType.CLIENT
        )
        assert is_valid is False
        assert any("email" in e.lower() for e in errors)
        assert "email" not in cleaned

    def test_empty_email_is_invalid(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "Test", "email": ""}, EntityType.CLIENT
        )
        # Empty string email fails email validation
        assert is_valid is False
        assert any("email" in e.lower() for e in errors)

    def test_email_missing_at_sign(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "Test", "email": "usermissingdomain"}, EntityType.CLIENT
        )
        assert is_valid is False
        assert any("email" in e.lower() for e in errors)

    # ── Phone validation ──────────────────────────────────────────────

    def test_valid_phone(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "Test", "phone": "+40 123 456 789"}, EntityType.CLIENT
        )
        assert is_valid is True
        assert cleaned.get("phone") == "+40 123 456 789"

    def test_invalid_phone_too_short(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "Test", "phone": "123"}, EntityType.CLIENT
        )
        assert is_valid is False
        assert any("phone" in e.lower() for e in errors)
        assert "phone" not in cleaned

    def test_invalid_phone_special_chars(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "Test", "phone": "abc-def-ghij"}, EntityType.CLIENT
        )
        # The phone regex allows dashes and digits, so "abc-def-ghij" has invalid chars
        assert any("phone" in e.lower() for e in errors) or not is_valid

    # ── Year validation ───────────────────────────────────────────────

    def test_valid_year(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"plate_number": "AB123CD", "year": 2023}, EntityType.TRUCK
        )
        assert is_valid is True
        assert cleaned.get("year") == 2023

    def test_valid_year_string(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"plate_number": "AB123CD", "year": "2023"}, EntityType.TRUCK
        )
        assert is_valid is True

    def test_invalid_year_string(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"plate_number": "AB123CD", "year": "abcd"}, EntityType.TRUCK
        )
        assert is_valid is False
        assert any("year" in e.lower() for e in errors)
        assert "year" not in cleaned

    def test_year_out_of_range_low(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"plate_number": "AB123CD", "year": 1800}, EntityType.TRUCK
        )
        assert is_valid is False
        assert any("out of range" in e.lower() for e in errors)
        assert "year" not in cleaned

    def test_year_out_of_range_high(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"plate_number": "AB123CD", "year": 2100}, EntityType.TRUCK
        )
        assert is_valid is False
        assert any("out of range" in e.lower() for e in errors)

    def test_year_too_low_boundary(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"plate_number": "AB123CD", "year": 1899}, EntityType.TRUCK
        )
        assert is_valid is False
        assert any("out of range" in e.lower() for e in errors)

    def test_year_valid_boundary_low(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"plate_number": "AB123CD", "year": 1900}, EntityType.TRUCK
        )
        assert is_valid is True

    def test_year_valid_boundary_high(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"plate_number": "AB123CD", "year": 2035}, EntityType.TRUCK
        )
        assert is_valid is True

    # ── Driver validation ─────────────────────────────────────────────

    def test_valid_driver(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "John Doe"}, EntityType.DRIVER
        )
        assert is_valid is True
        assert cleaned == {"name": "John Doe"}

    def test_missing_driver_name(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {}, EntityType.DRIVER
        )
        assert is_valid is False
        assert any("name" in e for e in errors)

    # ── Truck validation ──────────────────────────────────────────────

    def test_valid_truck(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"plate_number": "AB123CD"}, EntityType.TRUCK
        )
        assert is_valid is True
        assert cleaned == {"plate_number": "AB123CD"}

    def test_missing_truck_plate(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"manufacturer": "Volvo"}, EntityType.TRUCK
        )
        assert is_valid is False
        assert any("plate_number" in e for e in errors)

    def test_empty_truck_plate(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"plate_number": ""}, EntityType.TRUCK
        )
        assert is_valid is False
        assert any("plate_number" in e for e in errors)

    # ── Trip validation ───────────────────────────────────────────────

    def test_valid_trip(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"truck_number": "AB123CD"}, EntityType.TRIP
        )
        assert is_valid is True
        assert cleaned == {"truck_number": "AB123CD"}

    def test_missing_trip_truck_number(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"client_name": "Test"}, EntityType.TRIP
        )
        assert is_valid is False
        assert any("truck_number" in e for e in errors)

    # ── Document validation ───────────────────────────────────────────

    def test_valid_document(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"title": "Contract", "file_path": "/path/doc.pdf"}, EntityType.DOCUMENT
        )
        assert is_valid is True
        assert cleaned["title"] == "Contract"
        assert cleaned["file_path"] == "/path/doc.pdf"

    def test_document_missing_title(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"file_path": "/path/doc.pdf"}, EntityType.DOCUMENT
        )
        assert is_valid is False
        assert any("title" in e for e in errors)

    def test_document_missing_file_path(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"title": "Contract"}, EntityType.DOCUMENT
        )
        assert is_valid is False
        assert any("file_path" in e for e in errors)

    # ── Invoice validation ────────────────────────────────────────────

    def test_valid_invoice(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"invoice_number": "INV-001"}, EntityType.INVOICE
        )
        assert is_valid is True
        assert cleaned == {"invoice_number": "INV-001"}

    def test_missing_invoice_number(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"total_amount": 1000}, EntityType.INVOICE
        )
        assert is_valid is False
        assert any("invoice_number" in e for e in errors)

    # ── Unknown entity type ───────────────────────────────────────────

    def test_unknown_entity_type(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "Test"}, "unknown_type"  # type: ignore[arg-type]
        )
        # Should not crash; returns valid with no errors (no schema)
        assert is_valid is True
        assert errors == []
        assert cleaned == {}

    # ── Unknown columns are silently dropped ─────────────────────────

    def test_unknown_columns_dropped(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "Test", "unknown_field": "should_be_dropped", "another_unknown": 42},
            EntityType.CLIENT,
        )
        assert is_valid is True
        assert "name" in cleaned
        assert "unknown_field" not in cleaned
        assert "another_unknown" not in cleaned

    def test_many_unknown_columns_dropped(self, validator):
        row = {"name": "Valid", "x1": 1, "x2": 2, "x3": 3, "x4": 4}
        is_valid, errors, cleaned = validator.validate_row(row, EntityType.CLIENT)
        assert is_valid is True
        assert cleaned == {"name": "Valid"}

    # ── None values ──────────────────────────────────────────────────

    def test_none_values_skipped(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": "Test", "phone": None, "email": None}, EntityType.CLIENT
        )
        assert is_valid is True
        assert "phone" not in cleaned
        assert "email" not in cleaned

    def test_required_field_with_none(self, validator):
        is_valid, errors, cleaned = validator.validate_row(
            {"name": None}, EntityType.CLIENT
        )
        assert is_valid is False
        assert any("name" in e for e in errors)

    # ── Multiple errors ──────────────────────────────────────────────

    def test_multiple_missing_fields(self, validator):
        is_valid, errors, cleaned = validator.validate_row({}, EntityType.CLIENT)
        assert is_valid is False
        assert any("name" in e for e in errors)
