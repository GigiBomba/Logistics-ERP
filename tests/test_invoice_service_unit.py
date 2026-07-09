"""Unit tests for InvoiceService — all dependencies mocked."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.invoicing.service import InvoiceService
from tests.test_helpers import make_db


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def prefs_mock():
    prefs = MagicMock()
    prefs.get_setting.return_value = None
    return prefs


@pytest.fixture
def service(db_mock, prefs_mock):
    """Build InvoiceService with mocked prefs.  Internal dependencies are replaced
    after construction so we can control every layer."""
    svc = InvoiceService(db_mock, prefs=prefs_mock)
    svc.generator = MagicMock()
    svc._client_repo = MagicMock()
    svc._event_bus = MagicMock()
    return svc


# ── get_format_key ───────────────────────────────────────────────────

def test_get_format_key_default(db_mock):
    """When prefs is None, get_format_key returns DEFAULT_INVOICE_FORMAT_KEY."""
    from repositories.invoice_repository import DEFAULT_INVOICE_FORMAT_KEY
    svc = InvoiceService(db_mock, prefs=None)
    assert svc.get_format_key() == DEFAULT_INVOICE_FORMAT_KEY


def test_get_format_key_from_prefs(service, prefs_mock):
    """When prefs has a stored value, get_format_key returns it."""
    prefs_mock.get_setting.return_value = "inv_seq"
    result = service.get_format_key()
    assert result == "inv_seq"
    prefs_mock.get_setting.assert_called_once_with("invoice_number_format")


# ── set_format_key ───────────────────────────────────────────────────

def test_set_format_key(service, prefs_mock):
    """set_format_key saves a valid format key via prefs."""
    service.set_format_key("inv_seq")
    prefs_mock.save_setting.assert_called_once_with("invoice_number_format", "inv_seq")


def test_set_format_key_invalid_ignored(service, prefs_mock):
    """set_format_key does nothing when the key is not in INVOICE_NUMBER_FORMATS."""
    service.set_format_key("bogus_format")
    prefs_mock.save_setting.assert_not_called()


# ── _enrich_trip_with_client ─────────────────────────────────────────

def test_enrich_trip_with_client_no_client_id(service):
    """When trip_data has no client_id, the dict is returned unchanged."""
    trip = {"id": 1, "client_name": "ACME"}
    result = service._enrich_trip_with_client(trip)
    assert result == trip
    service._client_repo.get_by_id.assert_not_called()


def test_enrich_trip_with_client_found(service):
    """Client enrichment populates vat, address, phone, email, contact."""
    service._client_repo.get_by_id.return_value = {
        "vat_number": "RO123",
        "address": "Str. Unirii 10",
        "phone": "+401234567",
        "email": "client@example.com",
        "contact_person": "John Doe",
    }
    trip = {"id": 1, "client_id": 42, "client_name": "ACME"}
    result = service._enrich_trip_with_client(trip)

    service._client_repo.get_by_id.assert_called_once_with(42)
    assert result["client_vat"] == "RO123"
    assert result["client_address"] == "Str. Unirii 10"
    assert result["client_phone"] == "+401234567"
    assert result["client_email"] == "client@example.com"
    assert result["client_contact"] == "John Doe"
    # Original keys are preserved
    assert result["id"] == 1
    assert result["client_id"] == 42


def test_enrich_trip_with_client_not_found(service):
    """When client is not found, trip_data is returned unmodified."""
    service._client_repo.get_by_id.return_value = None
    trip = {"id": 1, "client_id": 99}
    result = service._enrich_trip_with_client(trip)
    assert result == trip
    assert "client_vat" not in result


# ── generate ─────────────────────────────────────────────────────────

def test_generate_delegates_to_generator(service):
    """generate enriches trip_data and forwards to InvoiceGenerator.generate."""
    service._client_repo.get_by_id.return_value = {
        "vat_number": "RO123",
        "address": "",
        "phone": "",
        "email": "",
        "contact_person": "",
    }
    service.generator.generate.return_value = "/tmp/invoices/INV-2026-0042_client.pdf"

    trip_data = {"id": 1, "client_id": 10, "total_price_eur": 1500.0}
    result = service.generate(trip_data, mode="client")

    # Enrichment was called
    service._client_repo.get_by_id.assert_called_once_with(10)
    # Generator was called with enriched data
    service.generator.generate.assert_called_once()
    call_args = service.generator.generate.call_args
    assert call_args[0][0]["client_vat"] == "RO123"
    assert call_args[1] == {"mode": "client"}
    assert result == "/tmp/invoices/INV-2026-0042_client.pdf"


# ── create_record ────────────────────────────────────────────────────

def test_create_record_calls_db(service, db_mock):
    """create_record delegates to db.create_invoice_record."""
    service.create_record(trip_id=1, inv_number="INV-2026-0001",
                          amount=1500.0, due_date="2026-08-09")
    db_mock.create_invoice_record.assert_called_once_with(
        1, "INV-2026-0001", 1500.0, "2026-08-09"
    )


# ── generate_and_record ──────────────────────────────────────────────

@patch("services.document_service.DocumentService")
@patch("services.invoicing.service.os.path.isfile")
def test_generate_and_record_client_mode(mock_isfile, mock_ds_cls, service, db_mock):
    """generate_and_record in client mode records an invoice and registers the document."""
    mock_isfile.return_value = True
    mock_ds = MagicMock()
    mock_ds_cls.return_value = mock_ds

    service._client_repo.get_by_id.return_value = {
        "vat_number": "RO123", "address": "", "phone": "",
        "email": "", "contact_person": "",
    }
    service.generator.generate.return_value = "/tmp/invoices/INV-2026-0001_client.pdf"
    service._event_bus = MagicMock()

    trip_data = {
        "id": 42, "client_id": 10, "client_name": "ACME",
        "total_price_eur": 2000.0,
    }
    path = service.generate_and_record(trip_data, mode="client")

    # Generator called
    service.generator.generate.assert_called_once()
    # create_record was called
    db_mock.create_invoice_record.assert_called_once()
    # Event published
    service._event_bus.publish.assert_called()
    publish_args = service._event_bus.publish.call_args
    assert publish_args[0][0] == "invoice.created"

    # Document registration
    mock_ds.register_existing.assert_called_once()
    reg_args = mock_ds.register_existing.call_args[1]
    assert reg_args["category"] == "invoices"
    assert reg_args["entity_id"] == 42
    assert "invoice" in reg_args["tags"]

    assert path == "/tmp/invoices/INV-2026-0001_client.pdf"


@patch("services.document_service.DocumentService")
@patch("services.invoicing.service.os.path.isfile")
def test_generate_and_record_company_mode(mock_isfile, mock_ds_cls, service, db_mock):
    """generate_and_record in company (internal) mode skips invoice DB record but still
    registers the document."""
    mock_isfile.return_value = True
    mock_ds = MagicMock()
    mock_ds_cls.return_value = mock_ds

    service._client_repo.get_by_id.return_value = {
        "vat_number": "", "address": "", "phone": "",
        "email": "", "contact_person": "",
    }
    service.generator.generate.return_value = "/tmp/invoices/INV-2026-0001_internal.pdf"
    service._event_bus = MagicMock()

    trip_data = {"id": 7, "total_price_eur": 3000.0}
    path = service.generate_and_record(trip_data, mode="company")

    # In company mode, create_record is NOT called (mode != "client")
    db_mock.create_invoice_record.assert_not_called()
    service._event_bus.publish.assert_not_called()

    # Document registration still happens
    mock_ds.register_existing.assert_called_once()
    reg_args = mock_ds.register_existing.call_args[1]
    assert "company" in reg_args["tags"]

    assert path == "/tmp/invoices/INV-2026-0001_internal.pdf"


# ── send_invoice_email ───────────────────────────────────────────────

def test_send_invoice_email_missing_recipient(service):
    """send_invoice_email raises ValueError when recipient is empty."""
    with pytest.raises(ValueError, match="Recipient email address is required"):
        service.send_invoice_email(trip_id=1, recipient="")

    with pytest.raises(ValueError, match="Recipient email address is required"):
        service.send_invoice_email(trip_id=1, recipient=None)  # type: ignore[arg-type]
