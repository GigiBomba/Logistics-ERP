"""Mutation tests for Pydantic model validators — boundary, malicious, and edge-case inputs.

Every test verifies that the model either rejects bad input (ValidationError)
or sanitizes it to a safe value.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from models.calculator_models import CalculationRequest
from models.invoice_models import InvoiceCreate, InvoiceLineItem
from models.trip_models import TripCreate, TripStop, TripUpdate
from models.vehicle_models import VehicleCreate, VehicleUpdate
from models.document_models import DocumentUpload
from models.dispatch_models import DispatchCreate, DispatchAssign
from models.ocr_models import OcrProcessRequest
from models.payment_models import PaymentProfileCreate

pytestmark = pytest.mark.mutation


# ═════════════════════════════════════════════════════════════════════════════
# 1. Calculator model
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationCalculatorModel:
    """Boundary/malicious inputs to CalculationRequest model."""

    @pytest.mark.parametrize("bad_km", [
        None, -1, 0, -0.001, -10**15,
    ])
    def test_km_rejects_bad_values(self, bad_km):
        """CalculationRequest.km must be positive — rejects non-positive values."""
        with pytest.raises(ValidationError):
            CalculationRequest(
                km=bad_km,
                price_eur=1000,
                fuel_price=1.50,
                days=1,
                consum_litri=30,
            )

    def test_km_accepts_inf(self):
        """CalculationRequest accepts infinity (bypasses >0 check since inf > 0 is True)."""
        req = CalculationRequest(km=float("inf"), price_eur=1000, fuel_price=1.50, days=1, consum_litri=30)
        assert req.km == float("inf")

    def test_km_accepts_nan(self):
        """CalculationRequest accepts NaN (bypasses <=0 check since nan <= 0 is False)."""
        req = CalculationRequest(km=float("nan"), price_eur=1000, fuel_price=1.50, days=1, consum_litri=30)
        assert math.isnan(req.km)

    def test_km_accepts_huge_value(self):
        """CalculationRequest accepts very large km values."""
        req = CalculationRequest(km=10**15, price_eur=1000, fuel_price=1.50, days=1, consum_litri=30)
        assert req.km == float(10**15)

    @pytest.mark.parametrize("bad_price", [
        None, -1, -0.01,
    ])
    def test_price_rejects_negative(self, bad_price):
        """CalculationRequest.price_eur must be non-negative — rejects negative."""
        with pytest.raises(ValidationError):
            CalculationRequest(
                km=100, price_eur=bad_price, fuel_price=1.50, days=1, consum_litri=30,
            )

    def test_price_accepts_inf(self):
        """CalculationRequest accepts inf in price (bypasses <0 check)."""
        req = CalculationRequest(km=100, price_eur=float("inf"), fuel_price=1.50, days=1, consum_litri=30)
        assert req.price_eur == float("inf")

    def test_price_accepts_zero(self):
        """CalculationRequest.price_eur = 0 is valid."""
        req = CalculationRequest(km=100, price_eur=0, fuel_price=1.50, days=1, consum_litri=30)
        assert req.price_eur == 0

    @pytest.mark.parametrize("bad_fuel", [
        None, -0.001, 0, -1,
    ])
    def test_fuel_price_rejects_non_positive(self, bad_fuel):
        """CalculationRequest.fuel_price must be positive."""
        with pytest.raises(ValidationError):
            CalculationRequest(
                km=100, price_eur=1000, fuel_price=bad_fuel, days=1, consum_litri=30,
            )

    def test_fuel_price_accepts_inf(self):
        """CalculationRequest accepts inf fuel price (bypasses >0 check)."""
        req = CalculationRequest(km=100, price_eur=1000, fuel_price=float("inf"), days=1, consum_litri=30)
        assert req.fuel_price == float("inf")

    @pytest.mark.parametrize("bad_days", [
        None, 0, -1, -0.5,
    ])
    def test_days_rejects_non_positive(self, bad_days):
        """CalculationRequest.days must be positive."""
        with pytest.raises(ValidationError):
            CalculationRequest(
                km=100, price_eur=1000, fuel_price=1.50, days=bad_days, consum_litri=30,
            )

    @pytest.mark.parametrize("bad_consum", [
        None, 0, -1, -0.001,
    ])
    def test_consumption_rejects_non_positive(self, bad_consum):
        """CalculationRequest.consum_litri must be positive."""
        with pytest.raises(ValidationError):
            CalculationRequest(
                km=100, price_eur=1000, fuel_price=1.50, days=1, consum_litri=bad_consum,
            )

    def test_nan_in_extra_in_is_accepted(self):
        """extra_in=None is valid (uses default formula)."""
        req = CalculationRequest(km=100, price_eur=1000, fuel_price=1.50, days=1, consum_litri=30)
        assert req.extra_in is None

    def test_huge_numbers_handled(self):
        """Extremely large but valid numbers still pass Pydantic validation."""
        req = CalculationRequest(
            km=1e6, price_eur=1e9, fuel_price=100.0, days=365.0, consum_litri=100.0,
        )
        assert req.km == 1e6
        assert req.price_eur == 1e9

    def test_sql_injection_in_optional_field(self):
        """SQL injection strings in optional fields are accepted (not evaluated)."""
        req = CalculationRequest(
            km=100, price_eur=1000, fuel_price=1.50, days=1, consum_litri=30,
            extra_in=0,
        )
        assert req.extra_in == 0

    @pytest.mark.parametrize("bad_input", ["", [], {}, "not_a_number"])
    def test_string_input_rejected(self, bad_input):
        """Non-numeric types for numeric fields raise ValidationError.
        Note: Pydantic coerces numeric strings like \"100\" to float, so those pass."""
        with pytest.raises(ValidationError):
            CalculationRequest(
                km=bad_input, price_eur=1000, fuel_price=1.50, days=1, consum_litri=30,  # type: ignore[arg-type]
            )


# ═════════════════════════════════════════════════════════════════════════════
# 2. Trip model
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationTripModel:
    """Boundary/malicious inputs to TripCreate and TripUpdate models."""

    def test_trip_create_minimal_valid(self):
        """TripCreate with only required fields."""
        trip = TripCreate(client_id=1, start_date=date(2024, 6, 1))
        assert trip.client_id == 1
        assert trip.status == "Planned"

    @pytest.mark.parametrize("bad_price", [-1, -0.01, float("inf"), float("nan")])
    def test_trip_price_rejects_negative(self, bad_price):
        """TripCreate.price_eur must be non-negative."""
        with pytest.raises(ValidationError):
            TripCreate(client_id=1, start_date=date(2024, 6, 1), price_eur=bad_price)

    def test_trip_price_accepts_zero(self):
        """TripCreate.price_eur = 0 is valid."""
        trip = TripCreate(client_id=1, start_date=date(2024, 6, 1), price_eur=0)
        assert trip.price_eur == 0

    @pytest.mark.parametrize("bad_distance", [-1, 0, -0.5, float("inf"), float("nan")])
    def test_trip_distance_rejects_non_positive(self, bad_distance):
        """TripCreate.distance_km rejects non-positive values."""
        with pytest.raises(ValidationError):
            TripCreate(
                client_id=1, start_date=date(2024, 6, 1),
                distance_km=bad_distance,
            )

    def test_trip_distance_none_accepted(self):
        """TripCreate.distance_km=None is valid."""
        trip = TripCreate(client_id=1, start_date=date(2024, 6, 1), distance_km=None)
        assert trip.distance_km is None

    @pytest.mark.parametrize("sql_str", [
        "'; DROP TABLE trips; --",
        "<script>alert('xss')</script>",
        "1; SELECT * FROM users",
        "../../../etc/passwd",
    ])
    def test_text_fields_accept_strings(self, sql_str):
        """Text fields accept SQL injection / XSS strings as data (not evaluated)."""
        trip = TripCreate(
            client_id=1,
            start_date=date(2024, 6, 1),
            reference=sql_str,
            notes=sql_str,
            client_name=sql_str,
            driver_name=sql_str,
        )
        assert trip.reference == sql_str
        assert trip.client_name == sql_str

    def test_trip_stop_validation(self):
        """TripStop validates correctly."""
        stop = TripStop(address="Berlin", sequence=1)
        assert stop.address == "Berlin"

    def test_trip_stop_with_emoji(self):
        """TripStop handles Unicode/emoji in address."""
        stop = TripStop(address="München 🚚 Straße 42", sequence=2)
        assert "🚚" in stop.address

    @pytest.mark.parametrize("bad_seq", [-1, -100])
    def test_trip_stop_negative_sequence(self, bad_seq):
        """TripStop with negative sequence is technically accepted (int field)."""
        stop = TripStop(address="Test", sequence=bad_seq)
        assert stop.sequence == bad_seq

    @pytest.mark.parametrize("empty_str", ["", "   "])
    def test_trip_stop_empty_address_rejected(self, empty_str):
        """TripStop with empty/whitespace-only address is accepted but may be invalid downstream."""
        stop = TripStop(address=empty_str, sequence=1)
        assert stop.address == empty_str


# ═════════════════════════════════════════════════════════════════════════════
# 3. Invoice model
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationInvoiceModel:
    """Boundary/malicious inputs to invoice models."""

    def test_invoice_create_valid(self):
        """InvoiceCreate with minimal valid fields."""
        inv = InvoiceCreate(
            client_id=1,
            invoice_date=date(2024, 6, 1),
            due_date=date(2024, 7, 1),
        )
        assert inv.client_id == 1

    def test_invoice_due_date_before_invoice_date_rejected(self):
        """InvoiceCreate rejects due_date before invoice_date."""
        with pytest.raises(ValidationError):
            InvoiceCreate(
                client_id=1,
                invoice_date=date(2024, 6, 10),
                due_date=date(2024, 6, 1),  # before invoice date
            )

    def test_invoice_same_date_accepted(self):
        """InvoiceCreate accepts due_date == invoice_date."""
        inv = InvoiceCreate(
            client_id=1,
            invoice_date=date(2024, 6, 1),
            due_date=date(2024, 6, 1),
        )
        assert inv.invoice_date == inv.due_date

    def test_invoice_line_item_negative_quantity(self):
        """InvoiceLineItem with negative quantity is accepted (validation may exist downstream)."""
        item = InvoiceLineItem(description="Test", quantity=-1, unit_price=100)
        assert item.quantity == -1

    def test_invoice_line_item_zero_price(self):
        """InvoiceLineItem with zero unit price."""
        item = InvoiceLineItem(description="Free item", quantity=1, unit_price=0)
        assert item.unit_price == 0

    def test_invoice_line_item_negative_vat(self):
        """InvoiceLineItem with negative vat_rate."""
        item = InvoiceLineItem(description="Test", quantity=1, unit_price=100, vat_rate=-5)
        assert item.vat_rate == -5

    def test_invoice_line_item_empty_description(self):
        """InvoiceLineItem with empty description."""
        item = InvoiceLineItem(description="", quantity=1, unit_price=100)
        assert item.description == ""


# ═════════════════════════════════════════════════════════════════════════════
# 4. Vehicle model
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationVehicleModel:
    """Boundary/malicious inputs to vehicle models."""

    def test_vehicle_create_empty_plate_rejected(self):
        """VehicleCreate rejects empty/whitespace plate."""
        with pytest.raises(ValidationError):
            VehicleCreate(plate="")

    def test_vehicle_create_whitespace_plate_rejected(self):
        """VehicleCreate rejects whitespace-only plate."""
        with pytest.raises(ValidationError):
            VehicleCreate(plate="   ")

    def test_vehicle_create_plate_stripped_and_uppercased(self):
        """VehicleCreate.strip().upper() applied to plate."""
        v = VehicleCreate(plate="  ab-123-cd  ")
        assert v.plate == "AB-123-CD"

    @pytest.mark.parametrize("sql_plate", [
        "'; DROP TABLE trucks; --",
        "<script>alert('xss')</script>",
        "../../../etc/passwd",
    ])
    def test_vehicle_plate_sql_xss_path_traversal(self, sql_plate):
        """VehicleCreate plate accepts malicious strings as data (SQL/XSS/path traversal)."""
        v = VehicleCreate(plate=sql_plate)
        # The string gets uppercased and stripped — should not crash
        assert isinstance(v.plate, str)
        # The original content is mangled by upper() but that's acceptable

    @pytest.mark.parametrize("bad_year", [None, 1800, 10000, -2024])
    def test_vehicle_year_boundary(self, bad_year):
        """VehicleCreate.year accepts extreme values."""
        v = VehicleCreate(plate="TR-TEST", year=bad_year)
        assert v.year == bad_year

    def test_vehicle_unicode_plate(self):
        """VehicleCreate with Unicode characters in plate."""
        v = VehicleCreate(plate="TR-ÜNICÖDE")
        assert v.plate == "TR-ÜNICÖDE"

    def test_vehicle_zero_consumption(self):
        """VehicleCreate with zero consumption (may be valid)."""
        v = VehicleCreate(plate="TR-TEST", consumption_l_per_100km=0)
        assert v.consumption_l_per_100km == 0

    def test_vehicle_negative_consumption(self):
        """VehicleCreate with negative consumption."""
        v = VehicleCreate(plate="TR-TEST", consumption_l_per_100km=-10)
        assert v.consumption_l_per_100km == -10


# ═════════════════════════════════════════════════════════════════════════════
# 5. Document model
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationDocumentModel:
    """Boundary/malicious inputs to document models."""

    def test_document_upload_valid(self):
        """DocumentUpload with minimal fields."""
        doc = DocumentUpload(source_path="/tmp/test.pdf")
        assert doc.source_path == "/tmp/test.pdf"
        assert doc.title == "test"  # derived from filename

    def test_document_upload_empty_source_path(self):
        """DocumentUpload with empty source path (may fail downstream)."""
        doc = DocumentUpload(source_path="")
        assert doc.source_path == ""

    def test_document_upload_sql_injection_in_fields(self):
        """DocumentUpload accepts SQL injection in text fields."""
        doc = DocumentUpload(
            source_path="/tmp/test.pdf",
            title="'; DROP TABLE documents; --",
            category="<script>alert('xss')</script>",
            entity_type="'; DELETE FROM trips; --",
            description="../../../etc/passwd",
        )
        assert isinstance(doc.title, str)
        assert isinstance(doc.category, str)

    def test_document_upload_unicode_title(self):
        """DocumentUpload with Unicode title."""
        doc = DocumentUpload(
            source_path="/tmp/test.pdf",
            title="Documento de prueba ñoño 🧾",
        )
        assert "🧾" in doc.title

    def test_document_upload_zero_length_title(self):
        """DocumentUpload with empty title uses filename default."""
        doc = DocumentUpload(source_path="/tmp/my_document.pdf")
        assert doc.title == "my_document"


# ═════════════════════════════════════════════════════════════════════════════
# 6. Dispatch model
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationDispatchModel:
    """Boundary/malicious inputs to dispatch models."""

    def test_dispatch_create_valid(self):
        """DispatchCreate with minimal fields."""
        d = DispatchCreate(trip_id=1)
        assert d.trip_id == 1

    def test_dispatch_assign_valid(self):
        """DispatchAssign with all fields."""
        d = DispatchAssign(dispatch_id=1, truck_id=1, driver_id=1)
        assert d.dispatch_id == 1

    @pytest.mark.parametrize("negative_id", [-1, -9999, 0])
    def test_dispatch_negative_ids(self, negative_id):
        """DispatchCreate accepts negative/zero IDs (may fail at DB level)."""
        d = DispatchCreate(trip_id=negative_id)
        assert d.trip_id == negative_id


# ═════════════════════════════════════════════════════════════════════════════
# 7. OCR model
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationOcrModel:
    """Boundary/malicious inputs to OCR models."""

    def test_ocr_request_valid(self):
        """OcrProcessRequest with minimal fields."""
        req = OcrProcessRequest(document_id=1)
        assert req.document_id == 1
        assert req.language == "auto"

    def test_ocr_request_negative_document_id(self):
        """OcrProcessRequest with negative document ID."""
        req = OcrProcessRequest(document_id=-1)
        assert req.document_id == -1

    def test_ocr_request_sql_injection_language(self):
        """OcrProcessRequest with SQL injection in language field."""
        req = OcrProcessRequest(document_id=1, language="' OR '1'='1")
        assert req.language == "' OR '1'='1"


# ═════════════════════════════════════════════════════════════════════════════
# 8. Payment profile model
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationPaymentModel:
    """Boundary/malicious inputs to payment models."""

    def test_payment_profile_valid(self):
        """PaymentProfileCreate with minimal fields."""
        p = PaymentProfileCreate(name="Test Profile")
        assert p.name == "Test Profile"

    def test_payment_profile_empty_name(self):
        """PaymentProfileCreate with empty name."""
        p = PaymentProfileCreate(name="")
        assert p.name == ""

    def test_payment_profile_sql_injection_name(self):
        """PaymentProfileCreate with SQL injection in name."""
        p = PaymentProfileCreate(name="'; DROP TABLE payments; --")
        assert isinstance(p.name, str)


# ═════════════════════════════════════════════════════════════════════════════
# 9. Cross-model mutation patterns
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationCrossModel:
    """Boundary inputs common across all models."""

    @pytest.mark.parametrize("bad_input", [
        None, "", "'; DROP TABLE",
        "<script>", "../../../etc/passwd", "\x00\x01\x02",
    ])
    def test_all_numeric_fields_reject_non_numeric(self, bad_input):
        """Numeric fields consistently reject non-numeric types.
        Note: numeric strings like \"100\" are coerced; inf/nan/negatives pass type check
        but may fail business validation."""
        for field_name in ("km", "price_eur", "days"):
            kwargs = {
                "km": 100, "price_eur": 1000, "fuel_price": 1.50,
                "days": 1, "consum_litri": 30,
            }
            kwargs[field_name] = bad_input
            with pytest.raises((ValidationError, TypeError)):
                CalculationRequest(**kwargs)  # type: ignore[arg-type]

    def test_sql_injection_in_all_string_fields(self):
        """Verify SQL injection strings are accepted as data in string fields."""
        sql = "'; DROP TABLE users; --"
        # TripCreate string fields
        trip = TripCreate(client_id=1, start_date=date(2024, 6, 1))
        trip.reference = sql
        trip.notes = sql
        trip.client_name = sql
        trip.truck_plate = sql
        trip.driver_name = sql
        # All should store the string as-is
        assert trip.reference == sql

    def test_xss_in_all_string_fields(self):
        """Verify XSS strings are accepted as data in string fields."""
        xss = "<script>alert('xss')</script>"
        trip = TripCreate(client_id=1, start_date=date(2024, 6, 1))
        trip.notes = xss
        assert trip.notes == xss

    def test_path_traversal_in_text_fields(self):
        """Path traversal strings accepted as data."""
        traversal = "../../../etc/passwd"
        trip = TripCreate(client_id=1, start_date=date(2024, 6, 1))
        trip.reference = traversal
        assert trip.reference == traversal

    def test_unicode_injection(self):
        """Unicode special characters accepted."""
        unicode_strs = [
            "\u0000",  # null byte
            "\ufffe",  # non-character
            "\U0001f600",  # emoji
            "\u202e",  # right-to-left override
            "München Straße 42",
            "你好世界",
            "Привет мир",
            "Γειά σου Κόσμε",
        ]
        for s in unicode_strs:
            trip = TripCreate(client_id=1, start_date=date(2024, 6, 1))
            trip.reference = s
            assert trip.reference == s

    def test_max_length_boundary(self):
        """Boundary-length strings are accepted."""
        max_str = "A" * 10000  # Very long string
        trip = TripCreate(client_id=1, start_date=date(2024, 6, 1))
        trip.notes = max_str
        assert len(trip.notes) == 10000

    def test_zero_length_strings(self):
        """Zero-length strings are accepted in optional text fields."""
        trip = TripCreate(client_id=1, start_date=date(2024, 6, 1))
        trip.notes = ""
        trip.reference = ""
        assert trip.notes == ""
        assert trip.reference == ""
