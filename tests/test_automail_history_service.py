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


def test_search_emails_empty(service):
    service._repo.search_emails = MagicMock(return_value=[])
    results = service.search_emails("nonexistent")
    assert results == []


def test_get_stats_empty_db(service):
    service._repo.get_email_stats = MagicMock(return_value={"emails_sent": 0, "emails_failed": 0})
    service._repo._fetchone = MagicMock(return_value=None)
    stats = service.get_stats(days=30)
    assert stats["emails_sent"] == 0
    assert stats["emails_failed"] == 0
    assert stats["total_outstanding_amount"] == 0.0
    assert stats["overdue_invoice_count"] == 0


def test_get_stats_zero_values(service):
    service._repo.get_email_stats = MagicMock(return_value={"emails_sent": 0, "emails_failed": 0})
    service._repo._fetchone = MagicMock(return_value={"total": 0, "cnt": 0})
    stats = service.get_stats(days=30)
    assert stats["emails_sent"] == 0
    assert stats["emails_failed"] == 0
    assert stats["total_outstanding_amount"] == 0.0
    assert stats["overdue_invoice_count"] == 0


def test_get_stats_different_days(service):
    service._repo.get_email_stats = MagicMock(return_value={"emails_sent": 5, "emails_failed": 1})
    service._repo._fetchone = MagicMock(return_value={"total": 1000.0, "cnt": 2})
    stats = service.get_stats(days=7)
    service._repo.get_email_stats.assert_called_with(7)
    assert stats["emails_sent"] == 5


def test_get_email_history_default_params(service):
    """Default page=0 and page_size=20."""
    service._repo.get_email_history = MagicMock(return_value=([], 0))
    results, total = service.get_email_history()
    service._repo.get_email_history.assert_called_with("", "", 0, 20)
    assert results == []
    assert total == 0


def test_get_email_history_pagination(service):
    """Pagination parameters are passed through."""
    service._repo.get_email_history = MagicMock(return_value=([{"id": 1}], 50))
    results, total = service.get_email_history(page=2, page_size=10)
    service._repo.get_email_history.assert_called_with("", "", 2, 10)
    assert total == 50


def test_get_email_history_empty(service):
    service._repo.get_email_history = MagicMock(return_value=([], 0))
    results, total = service.get_email_history(search="zzz_nonexistent_zzz")
    assert results == []
    assert total == 0
