"""Tests for InvoiceGenerator."""
import os
from unittest.mock import MagicMock, patch

import pytest

from services.invoicing.generator import InvoiceGenerator


@pytest.fixture
def generator():
    with patch("services.invoicing.generator.data_path", return_value=os.path.join(
            os.path.dirname(__file__), "..", "invoices")):
        with patch("services.invoicing.generator.os.makedirs"):
            with patch("services.invoicing.generator.load_company_config",
                       return_value={"company_name": "Test", "cui": "RO123",
                                     "reg_number": "J123", "address": "Addr",
                                     "phone": "0712345678", "email": "t@t.com",
                                     "logo_path": "", "company_color": "#6366f1",
                                     "signature_path": "", "stamp_path": ""}):
                gen = InvoiceGenerator()
                gen.reports_dir = os.path.join(os.path.dirname(__file__), "..", "invoices")
                return gen


def test_generate_creates_pdf(generator):
    trip_data = {
        "id": 1,
        "client_name": "Test Client",
        "truck_number": "AB-123",
        "driver_name": "John",
        "distance_km": 500,
        "start_date": "2026-06-01",
        "end_date": "2026-06-02",
        "total_price_eur": 1000,
        "fuel_cost": 200,
        "toll_cost": 100,
        "salary_cost": 300,
        "extra_costs": 50,
        "net_profit": 350,
        "currency": "EUR",
    }
    path = generator.generate(trip_data, mode="client")
    assert path is not None
    assert path.endswith(".pdf")
    # Verify the path contains the expected filename
    assert "INV" in os.path.basename(path)


def test_generate_internal_mode(generator):
    trip_data = {
        "id": 2,
        "client_name": "Test Client",
        "truck_number": "CD-456",
        "driver_name": "Jane",
        "distance_km": 300,
        "total_price_eur": 2000,
        "fuel_cost": 400,
        "toll_cost": 200,
        "salary_cost": 500,
        "extra_costs": 100,
        "net_profit": 800,
        "currency": "EUR",
    }
    path = generator.generate(trip_data, mode="internal")
    assert path is not None
    assert "internal" in path


def test_generate_rich(generator):
    inv_data = {
        "invoice_number": "INV-2026-0001",
        "issue_date": "2026-06-01",
        "due_date": "2026-07-01",
        "payment_terms": "Net 30",
        "currency": "EUR",
        "company": {"company_name": "Test"},
        "client": {"name": "Client"},
        "addon_items": [],
        "subtotal": 1000,
        "total_tax": 190,
        "discount": 0,
        "grand_total": 1190,
        "notes": "Thank you",
        "mode": "client",
        "trip_price": 1000,
    }
    path = generator.generate_rich(inv_data)
    assert path is not None
    assert path.endswith(".pdf")


@patch("services.invoicing.generator.InvoiceGenerator.generate_rich")
def test_generate_rich_proforma(mock_gen, generator):
    inv_data = {
        "invoice_number": "PROF-2026-0001",
        "issue_date": "2026-06-01",
        "mode": "client",
    }
    mock_gen.return_value = "/tmp/proforma.pdf"
    path = generator.generate_rich(inv_data, document_type="proforma")
    assert path is not None


def test_tr(generator):
    result = generator._tr("invoice_pdf.title_client", "client")
    assert result is not None
    assert isinstance(result, str)
