"""Tests for ProformaService."""
import json
import os
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest

from services.invoicing.proforma_service import ProformaService


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def prefs_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock, prefs_mock):
    with patch.object(ProformaService, "__init__", return_value=None):
        svc = ProformaService.__new__(ProformaService)
        svc.db = db_mock
        svc.prefs = prefs_mock
        svc.generator = MagicMock()
        svc._event_bus = MagicMock()
        svc._client_repo = MagicMock()
        svc._proforma_repo = MagicMock()
        svc._drafts_dir = tempfile.mkdtemp()
        return svc


def test_get_format_key(service):
    service.prefs.get_setting.return_value = None
    from services.invoicing.proforma_service import DEFAULT_PROFORMA_FORMAT_KEY
    key = service.get_format_key()
    assert key == DEFAULT_PROFORMA_FORMAT_KEY


def test_set_format_key(service):
    from services.invoicing.proforma_service import PROFORMA_NUMBER_FORMATS
    PROFORMA_NUMBER_FORMATS["test"] = "PROF-{seq}"
    service.set_format_key("test")
    service.prefs.save_setting.assert_called_with("proforma_number_format", "test")


def test_generate(service):
    service.generator.generate_rich.return_value = "/path/to/proforma.pdf"
    data = {"mode": "client"}
    path = service.generate(data)
    assert path == "/path/to/proforma.pdf"
    service.generator.generate_rich.assert_called_with(data, document_type="proforma")


def test_generate_and_record(service):
    service.generator.generate_rich.return_value = "/path/to/pf.pdf"
    service._proforma_repo.get_next_number.return_value = "PROF-000001"
    service._proforma_repo.create.return_value = 99

    data = {
        "mode": "client",
        "client": {"name": "Client A", "email": "a@b.com"},
        "subtotal": 1000, "grand_total": 1190, "currency": "EUR",
    }

    with patch("os.path.isfile", return_value=True), \
         patch("services.document_service.DocumentService") as mock_ds:
        path = service.generate_and_record(data)
        assert path == "/path/to/pf.pdf"
        service._proforma_repo.create.assert_called_once()
        service._event_bus.publish.assert_called_once()


def test_save_draft(service):
    result = service.save_draft({"amount": 100}, "test_draft")
    assert result is True


def test_save_draft_empty(service):
    result = service.save_draft({}, "  ")
    assert result is False


def test_load_draft(service):
    draft_path = os.path.join(service._drafts_dir, "mydraft.json")
    with open(draft_path, "w") as f:
        json.dump({"amount": 500}, f)
    result = service.load_draft("mydraft")
    assert result == {"amount": 500}


def test_load_draft_not_found(service):
    assert service.load_draft("nonexistent") is None


def test_list_drafts(service):
    for name in ["d1.json", "d2.json"]:
        with open(os.path.join(service._drafts_dir, name), "w") as f:
            f.write("{}")
    drafts = service.list_drafts()
    assert "d1" in drafts


def test_send_email_no_recipient(service):
    with pytest.raises(ValueError):
        service.send_email(1, "")


@patch("services.invoicing.proforma_service.NotificationCenter")
def test_send_email_no_smtp(mock_nc, service):
    service.prefs.get_smtp_config.return_value = {}
    with pytest.raises(ValueError):
        service.send_email(1, "test@test.com")


@patch("services.invoicing.proforma_service.NotificationCenter")
def test_send_email_success(mock_nc, service):
    service.prefs.get_smtp_config.return_value = {
        "smtp_server": "smtp.test.com", "smtp_port": "587",
        "smtp_user": "user", "smtp_password": "pass",
    }
    nc_instance = MagicMock()
    mock_nc.return_value = nc_instance
    nc_instance.send_email.return_value = True

    service.generator.generate_rich.return_value = "/path/to/pf.pdf"
    service._proforma_repo.get_next_number.return_value = "PROF-001"

    with patch("os.path.isfile", return_value=True), \
         patch("os.path.exists", return_value=True):
        result = service.send_email(
            1, "test@test.com", proforma_data={"client": {"name": "Client"}},
        )
        assert result is True
        nc_instance.send_email.assert_called_once()
