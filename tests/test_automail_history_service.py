"""Tests for HistoryService."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.automail.history_service import HistoryService


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock):
    svc = HistoryService(db_mock)
    svc._repo = MagicMock()
    return svc


def test_init_no_db():
    with pytest.raises(ValueError):
        HistoryService(db=None)


def test_get_email_history(service):
    service._repo.get_email_history = MagicMock(return_value=(
        [{"id": 1, "trip_id": 1, "recipient": "a@b.com", "subject": "Test",
          "timestamp": "2026-06-01", "status": "sent"}],
        1,
    ))
    results, total = service.get_email_history(page=0, page_size=20)
    assert total == 1
    assert len(results) == 1
    assert results[0]["recipient"] == "a@b.com"


def test_get_email_history_with_search(service):
    service._repo.get_email_history = MagicMock(return_value=([], 2))
    results, total = service.get_email_history(search="test", page=0, page_size=20)
    assert total == 2


def test_get_email_history_with_status_filter(service):
    service._repo.get_email_history = MagicMock(return_value=([{"id": 1, "status": "sent"}], 1))
    results, total = service.get_email_history(status_filter="sent")
    assert total == 1


def test_get_stats(service):
    service._repo.get_email_stats = MagicMock(return_value={"emails_sent": 10, "emails_failed": 2})
    # Mock _fetchone for overdue query (called via repo)
    service._repo._fetchone = MagicMock(return_value={"total": 5000.0, "cnt": 3})
    stats = service.get_stats(days=30)
    assert stats["emails_sent"] == 10
    assert stats["emails_failed"] == 2
    assert stats["total_outstanding_amount"] == 5000.0
    assert stats["overdue_invoice_count"] == 3


def test_search_emails(service):
    service._repo.search_emails = MagicMock(return_value=[
        {"id": 1, "recipient": "a@b.com", "subject": "Reminder",
         "timestamp": "2026-06-01", "status": "sent", "trip_id": 1}
    ])
    results = service.search_emails("test")
    assert len(results) == 1
    assert results[0]["recipient"] == "a@b.com"
