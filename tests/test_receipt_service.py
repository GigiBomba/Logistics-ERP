"""Tests for ReceiptService."""
import json
import os
import tempfile
from unittest.mock import MagicMock, call, mock_open, patch

import pytest

from services.invoicing.receipt_service import ReceiptService


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def prefs_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock, prefs_mock):
    with patch.object(ReceiptService, "__init__", return_value=None):
        svc = ReceiptService.__new__(ReceiptService)
        svc.db = db_mock
        svc.prefs = prefs_mock
        svc.generator = MagicMock()
        svc._event_bus = MagicMock()
        svc._receipt_repo = MagicMock()
        svc._drafts_dir = tempfile.mkdtemp()
        return svc


def test_get_format_key(service):
    service.prefs.get_setting.return_value = None
    from services.invoicing.receipt_service import DEFAULT_FORMAT_KEY
    key = service.get_format_key()
    assert key == DEFAULT_FORMAT_KEY


def test_set_format_key(service):
    from services.invoicing.receipt_service import RECEIPT_NUMBER_FORMATS
    RECEIPT_NUMBER_FORMATS["test"] = "RCT-{seq}"
    service.set_format_key("test")
    service.prefs.save_setting.assert_called_with("receipt_number_format", "test")


def test_generate(service):
    service._calculate_financials = MagicMock()
    service.generator.generate.return_value = "/path/to/receipt.pdf"
    data = {"amount": 100, "vat_rate": 19}
    path = service.generate(data)
    assert path == "/path/to/receipt.pdf"
    service._calculate_financials.assert_called_once_with(data)


def test_generate_and_record(service):
    service._calculate_financials = MagicMock()
    service.generator.generate.return_value = "/path/to/rct.pdf"
    service._receipt_repo.get_next_number.return_value = "RCT-000001"
    service._receipt_repo.create.return_value = 42

    with patch("os.path.isfile", return_value=True), \
         patch("services.document_service.DocumentService") as mock_ds:
        data = {"amount": 500, "vat_rate": 0, "currency": "EUR",
                "received_from_name": "Client"}
        path = service.generate_and_record(data)
        assert path == "/path/to/rct.pdf"
        service._receipt_repo.create.assert_called_once()
        service._event_bus.publish.assert_called_once()


def test_generate_and_record_no_repo(service):
    service._receipt_repo = None
    service._calculate_financials = MagicMock()
    service.generator.generate.return_value = "/path/to/rct.pdf"
    data = {"amount": 100}
    path = service.generate_and_record(data)
    assert path == "/path/to/rct.pdf"


def test_save_draft(service):
    with patch("builtins.open", new_callable=mock_open) as mock_file:
        result = service.save_draft({"amount": 100}, "test_draft")
        assert result is True
        assert mock_file.called


def test_save_draft_empty_name(service):
    result = service.save_draft({"amount": 100}, "  ")
    assert result is False


def test_load_draft(service):
    draft_data = {"amount": 100}
    draft_path = os.path.join(service._drafts_dir, "mydraft.json")
    with open(draft_path, "w") as f:
        json.dump(draft_data, f)
    try:
        result = service.load_draft("mydraft")
        assert result == draft_data
    finally:
        os.unlink(draft_path)


def test_load_draft_not_found(service):
    result = service.load_draft("nonexistent")
    assert result is None


def test_list_drafts(service):
    # Create some draft files
    for name in ["draft1.json", "draft2.json"]:
        path = os.path.join(service._drafts_dir, name)
        with open(path, "w") as f:
            f.write("{}")
    drafts = service.list_drafts()
    assert "draft1" in drafts
    assert "draft2" in drafts


def test_delete_draft(service):
    draft_path = os.path.join(service._drafts_dir, "todel.json")
    with open(draft_path, "w") as f:
        json.dump({}, f)
    assert service.delete_draft("todel") is True
    assert os.path.isfile(draft_path) is False


def test_delete_draft_not_found(service):
    assert service.delete_draft("nonexistent") is False


def test_calculate_financials(service):
    data = {"amount": 100, "vat_rate": 19}
    service._calculate_financials(data)
    assert data["vat_amount"] == 19.0
    assert data["total"] == 119.0


def test_calculate_financials_with_existing(service):
    data = {"amount": 100, "vat_rate": 19, "vat_amount": 19.0, "total": 119.0}
    service._calculate_financials(data)
    # Should not recalculate
    assert data["vat_amount"] == 19.0
