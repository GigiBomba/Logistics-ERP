"""Tests for ExpiryService."""
from unittest.mock import MagicMock, patch

import pytest

from services.document.expiry_service import ExpiryService


@pytest.fixture
def repo_mock():
    return MagicMock()


@pytest.fixture
def service(repo_mock):
    return ExpiryService(repo_mock)


def test_set_expiry_date(service):
    service.set_expiry_date(1, "2026-12-31")
    service._repo.update.assert_called_with(1, expiry_date="2026-12-31",
                                            updated_at=service._repo.update.call_args[1]["updated_at"])


def test_get_expiring(service):
    service._repo.get_expiring_documents.return_value = [{"id": 1}]
    result = service.get_expiring(30)
    assert result == [{"id": 1}]
    service._repo.get_expiring_documents.assert_called_with(30)


def test_get_overdue(service):
    service._repo.get_overdue_documents.return_value = [{"id": 2}]
    result = service.get_overdue()
    assert result == [{"id": 2}]


def test_evaluate_document_expiries_with_alert_mgr(service):
    alert_mgr = MagicMock()
    service._repo.get_overdue_documents.return_value = [
        {"id": 1, "title": "Doc1", "doc_number": "DOC-001", "expiry_date": "2020-01-01"},
    ]
    service._repo.get_expiring_documents.return_value = []

    count = service.evaluate_document_expiries(alert_mgr=alert_mgr)
    assert count == 1
    alert_mgr.create_alert.assert_called_once()


def test_evaluate_document_expiries_no_alert_mgr(service):
    service._repo.get_overdue_documents.return_value = []
    service._repo.get_expiring_documents.return_value = []

    with patch("services.operations.alert_manager.AlertManager") as MockAM:
        mock_am = MagicMock()
        MockAM.return_value = mock_am
        count = service.evaluate_document_expiries()
        assert count == 0


def test_evaluate_expiring_docs(service):
    alert_mgr = MagicMock()
    service._repo.get_overdue_documents.return_value = []
    service._repo.get_expiring_documents.return_value = [
        {"id": 2, "title": "Doc2", "file_name": "doc2.pdf", "doc_number": "DOC-002",
         "expiry_date": "2026-07-01"},
    ]
    count = service.evaluate_document_expiries(alert_mgr=alert_mgr)
    assert count == 1
    alert_mgr.create_alert.assert_called_once()


def test_evaluate_both_overdue_and_expiring(service):
    alert_mgr = MagicMock()
    service._repo.get_overdue_documents.return_value = [
        {"id": 1, "title": "Overdue", "doc_number": "DOC-001", "expiry_date": "2020-01-01"},
    ]
    service._repo.get_expiring_documents.return_value = [
        {"id": 2, "title": "Expiring", "file_name": "doc2.pdf", "doc_number": "DOC-002",
         "expiry_date": "2026-07-01"},
    ]
    count = service.evaluate_document_expiries(alert_mgr=alert_mgr)
    assert count == 2
    assert alert_mgr.create_alert.call_count == 2
