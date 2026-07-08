"""Tests for services.invoicing.generator — InvoiceGenerator (proforma and invoice PDF generation)."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from services.invoicing.generator import InvoiceGenerator


@pytest.fixture
def generator():
    """Create an InvoiceGenerator with mocked reports_dir to avoid file-system pollution."""
    with patch("services.invoicing.generator.data_path") as mock_data_path:
        tmp_dir = tempfile.mkdtemp()
        mock_data_path.return_value = tmp_dir
        gen = InvoiceGenerator()
        gen.reports_dir = tmp_dir
        yield gen
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def min_proforma_data():
    return {
        "mode": "client",
        "invoice_number": "PROF-2026-0001",
        "issue_date": "2026-07-09",
        "due_date": "2026-08-08",
        "valid_until": "2026-08-08",
        "payment_terms": "Net 30",
        "currency": "EUR",
        "company": {
            "company_name": "Test Trans SRL",
            "cui": "RO123456",
            "reg_number": "J12/345/2024",
            "address": "Str. Test, Nr. 10",
            "phone": "+40123456789",
            "email": "office@test.ro",
        },
        "client": {
            "name": "Client A",
            "address": "Str. Client, Nr. 5",
            "vat_number": "DE987654",
            "phone": "+4912345678",
            "email": "client@example.com",
        },
        "subtotal": 1000.0,
        "total_tax": 190.0,
        "discount": 0,
        "grand_total": 1190.0,
        "tax_rate": 19,
        "discount_type": "",
        "discount_value": 0,
    }


# =============================================================================
# Test generate_rich — Proforma mode
# =============================================================================


class TestGenerateRichProforma:
    """Test proforma invoice generation via generate_rich(document_type='proforma')."""

    def test_basic_proforma_generation(self, generator, min_proforma_data):
        """Basic proforma generation returns a valid PDF path."""
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(min_proforma_data, document_type="proforma")
            assert path is not None
            assert path.endswith(".pdf")
            mock_doc.build.assert_called_once()

    def test_proforma_with_addon_items(self, generator, min_proforma_data):
        """Proforma with addon_items renders without error."""
        data = dict(min_proforma_data)
        data["addon_items"] = [
            {"description": "Extra service", "amount": 150.0},
            {"description": "Waiting time", "amount": 75.0},
        ]
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_with_tax_calculation(self, generator, min_proforma_data):
        """Proforma with price_pre_vat and vat_percent calculates correctly."""
        data = dict(min_proforma_data)
        data["trip_price"] = 1190.0
        data["price_pre_vat"] = 1000.0
        data["vat_percent"] = 19.0
        del data["subtotal"]
        del data["total_tax"]
        del data["grand_total"]
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_vat_mismatch_raises(self, generator, min_proforma_data):
        """Mismatched VAT calculation raises ValueError."""
        data = dict(min_proforma_data)
        data["trip_price"] = 1200.0
        data["price_pre_vat"] = 1000.0
        data["vat_percent"] = 19.0
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate"):
            with pytest.raises(ValueError, match="VAT mismatch"):
                generator.generate_rich(data, document_type="proforma")

    def test_proforma_vat_price_pre_exceeds_trip(self, generator, min_proforma_data):
        """price_pre_vat exceeding trip_price raises ValueError."""
        data = dict(min_proforma_data)
        data["trip_price"] = 800.0
        data["price_pre_vat"] = 1000.0
        data["vat_percent"] = 19.0
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate"):
            with pytest.raises(ValueError, match="exceeds trip_price"):
                generator.generate_rich(data, document_type="proforma")

    def test_proforma_with_discount_positive(self, generator, min_proforma_data):
        """Positive discount is displayed with minus sign."""
        data = dict(min_proforma_data)
        data["discount"] = 100.0
        data["grand_total"] = 1090.0
        data["discount_type"] = "percentage"
        data["discount_value"] = 10
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_with_negative_discount(self, generator, min_proforma_data):
        """Negative discount (adjustment) shows with plus sign."""
        data = dict(min_proforma_data)
        data["discount"] = -50.0
        data["grand_total"] = 1240.0
        data["discount_type"] = "fixed"
        data["discount_value"] = 50
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_different_currency(self, generator, min_proforma_data):
        """USD currency renders without issues."""
        data = dict(min_proforma_data)
        data["currency"] = "USD"
        data["grand_total"] = 1190.0
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_with_notes(self, generator, min_proforma_data):
        """Notes text is included in the story."""
        data = dict(min_proforma_data)
        data["notes"] = "Payment due within 30 days of receipt."
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_with_signature_and_stamp(self, generator, min_proforma_data):
        """Signature and stamp paths included."""
        data = dict(min_proforma_data)
        data["signature_path"] = "/tmp/test_sig.png"
        data["stamp_path"] = "/tmp/test_stamp.png"
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls, \
             patch("os.path.isfile", return_value=True):
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_with_loading_unloading_stops(self, generator, min_proforma_data):
        """Loading/unloading stops in trip details."""
        data = dict(min_proforma_data)
        data["loading_stops"] = ["Paris", "Lyon"]
        data["unloading_stops"] = ["Marseille"]
        data["distance"] = 800
        data["truck_plate"] = "AB-123-CD"
        data["driver_name"] = "John Doe"
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_internal_mode(self, generator, min_proforma_data):
        """Internal mode includes cost breakdown."""
        data = dict(min_proforma_data)
        data["mode"] = "internal"
        data["trip_data"] = {
            "total_price_eur": 2000.0,
            "fuel_cost": 500.0,
            "toll_cost": 200.0,
            "salary_cost": 400.0,
            "extra_costs": 100.0,
            "net_profit": 800.0,
        }
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_calls_draw_watermark(self, generator, min_proforma_data):
        """Proforma document should call build with _draw_watermark."""
        with patch.object(generator, "_draw_watermark") as mock_wm, \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            generator.generate_rich(min_proforma_data, document_type="proforma")
            # build is called with onFirstPage and onLaterPages for proforma
            args, kwargs = mock_doc.build.call_args
            assert "onFirstPage" in kwargs
            assert "onLaterPages" in kwargs

    def test_proforma_no_watermark_for_invoice(self, generator, min_proforma_data):
        """Invoice (not proforma) should NOT call _draw_watermark."""
        data = dict(min_proforma_data)
        data["invoice_number"] = "INV-2026-0001"
        with patch.object(generator, "_draw_watermark") as mock_wm, \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            generator.generate_rich(data, document_type="invoice")
            args, kwargs = mock_doc.build.call_args
            assert "onFirstPage" not in kwargs

    def test_proforma_with_description(self, generator, min_proforma_data):
        """Description text renders without issue."""
        data = dict(min_proforma_data)
        data["description"] = "Transport services for Q3 2026"
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_custom_company_color(self, generator, min_proforma_data):
        """Custom company_color hex string is applied."""
        data = dict(min_proforma_data)
        data["company_color"] = "#FF5733"
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_invalid_company_color_fallback(self, generator, min_proforma_data):
        """Invalid company_color hex falls back to default."""
        data = dict(min_proforma_data)
        data["company_color"] = "not-a-color"
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_with_logo_path(self, generator, min_proforma_data):
        """Logo path handling (file not found — should skip gracefully)."""
        data = dict(min_proforma_data)
        data["logo_path"] = "/nonexistent/logo.png"
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_proforma_zero_discount_not_displayed(self, generator, min_proforma_data):
        """Discount of 0 should not appear in totals (no extra row)."""
        data = dict(min_proforma_data)
        data["discount"] = 0.0
        data["discount_type"] = ""
        data["discount_value"] = 0
        with patch.object(generator, "_draw_watermark"), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="proforma")
            assert path is not None
            mock_doc.build.assert_called_once()


# =============================================================================
# Test generate_rich — Invoice mode (not proforma)
# =============================================================================


class TestGenerateRichInvoice:
    """Tests for regular invoice generation (document_type='invoice')."""

    def test_basic_invoice_generation(self, generator, min_proforma_data):
        """Basic invoice returns a valid PDF path."""
        data = dict(min_proforma_data)
        data["invoice_number"] = "INV-2026-0001"
        with patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="invoice")
            assert path is not None
            assert "INV" in os.path.basename(path)
            mock_doc.build.assert_called_once()

    def test_invoice_no_proforma_disclaimer(self, generator, min_proforma_data):
        """Invoice should not contain the proforma disclaimer."""
        data = dict(min_proforma_data)
        data["invoice_number"] = "INV-2026-0001"
        with patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate_rich(data, document_type="invoice")
            assert path is not None
            mock_doc.build.assert_called_once()


# =============================================================================
# Test generate (original simpler method)
# =============================================================================


class TestGenerate:
    """Tests for the original InvoiceGenerator.generate() method."""

    def test_generate_client_mode(self, generator):
        """Basic generate in client mode."""
        conf = {
            "company_name": "Test Trans SRL",
            "cui": "RO123456",
            "reg_number": "J12/345/2024",
            "address": "Str. Test",
            "phone": "+401234567",
        }
        trip_data = {
            "id": 1,
            "client_name": "Client A",
            "client_vat": "DE123",
            "client_address": "Berlin",
            "client_phone": "+49123456",
            "client_email": "c@a.com",
            "truck_number": "AB-123-CD",
            "driver_name": "John",
            "distance_km": 500,
            "start_date": "2026-07-01",
            "end_date": "2026-07-02",
            "total_price_eur": 1000.0,
            "fuel_cost": 200.0,
            "toll_cost": 100.0,
            "salary_cost": 300.0,
            "extra_costs": 50.0,
            "net_profit": 350.0,
            "currency": "EUR",
            "created_at": "2026-07-01",
        }
        with patch("services.invoicing.generator.load_company_config", return_value=conf), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate(trip_data, mode="client")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_generate_internal_mode(self, generator):
        """Basic generate in internal mode (shows cost breakdown)."""
        conf = {
            "company_name": "Test Trans SRL",
            "cui": "RO123456",
            "reg_number": "J12/345/2024",
            "address": "Str. Test",
            "phone": "+401234567",
        }
        trip_data = {
            "id": 2,
            "client_name": "Client B",
            "truck_number": "CD-456-EF",
            "driver_name": "Jane",
            "distance_km": 300,
            "start_date": "2026-07-03",
            "end_date": "2026-07-04",
            "total_price_eur": 2000.0,
            "fuel_cost": 400.0,
            "toll_cost": 150.0,
            "salary_cost": 500.0,
            "extra_costs": 100.0,
            "net_profit": 850.0,
            "currency": "EUR",
            "created_at": "2026-07-03",
        }
        with patch("services.invoicing.generator.load_company_config", return_value=conf), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate(trip_data, mode="internal")
            assert path is not None
            mock_doc.build.assert_called_once()

    def test_generate_missing_trip_id(self, generator):
        """Trip without id handles gracefully (defaults to 1)."""
        conf = {
            "company_name": "Test Trans SRL", "cui": "RO123456",
            "reg_number": "J12/345/2024", "address": "Str. Test",
            "phone": "+401234567",
        }
        trip_data = {
            "client_name": "Client C",
            "truck_number": "EF-789-GH",
            "distance_km": 100,
            "total_price_eur": 500.0,
            "created_at": "2026-07-05",
        }
        with patch("services.invoicing.generator.load_company_config", return_value=conf), \
             patch("services.invoicing.generator.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            path = generator.generate(trip_data, mode="client")
            assert path is not None
            mock_doc.build.assert_called_once()
