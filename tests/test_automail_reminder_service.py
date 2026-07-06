"""Tests for ReminderService."""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from services.automail.reminder_service import ReminderService


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock):
    svc = ReminderService(db_mock)
    svc._repo = MagicMock()
    return svc


def test_init_no_db():
    with pytest.raises(ValueError):
        ReminderService(db=None)


def test_get_active_schedules(service):
    service._repo.get_active_schedules.return_value = [{"id": 1}]
    assert service.get_active_schedules() == [{"id": 1}]


def test_get_all_schedules(service):
    service._repo.get_all_schedules.return_value = [{"id": 1}]
    assert service.get_all_schedules() == [{"id": 1}]


def test_get_reminder_status_for_invoice_no_due_date(service):
    result = service.get_reminder_status_for_invoice(1, "", 1)
    assert result == []


def test_get_reminder_status_for_invoice_invalid_date(service):
    result = service.get_reminder_status_for_invoice(1, "bad-date", 1)
    assert result == []


def test_compute_target_days_before():
    sched = {"trigger_type": "days_before_due", "days_offset": 3}
    assert ReminderService._compute_target_days(sched) == -3


def test_compute_target_days_after():
    sched = {"trigger_type": "days_after_due", "days_offset": 5}
    assert ReminderService._compute_target_days(sched) == 5


def test_compute_target_days_on_due():
    sched = {"trigger_type": "on_due_date", "days_offset": 0}
    assert ReminderService._compute_target_days(sched) == 0


def test_compute_scheduled_date(service):
    sched = {"trigger_type": "days_after_due", "days_offset": 3}
    due = date(2026, 6, 15)
    result = service._compute_scheduled_date(due, sched)
    assert result == date(2026, 6, 18)


def test_calculate_next_reminder_no_date(service):
    assert service.calculate_next_reminder("") is None


def test_calculate_next_reminder_invalid_date(service):
    assert service.calculate_next_reminder("bad") is None


def test_should_skip_client_disabled(service):
    override = {"is_disabled": True}
    assert service.should_skip(1, client_override=override) is True


def test_should_skip_max_reminders(service):
    service._count_sent_reminders = MagicMock(return_value=10)
    assert service.should_skip(1, max_reminders=5) is True


def test_should_skip_not_skipped(service):
    service._count_sent_reminders = MagicMock(return_value=1)
    assert service.should_skip(1, max_reminders=5) is False


def test_skip_next_reminder(service):
    service._repo.skip_reminder = MagicMock(return_value=None)
    result = service.skip_next_reminder(1, 1)
    assert result is True
    service._repo.skip_reminder.assert_called_with(1, 1)


def test_cancel_all_reminders(service):
    service._repo.cancel_all_reminders = MagicMock(return_value=None)
    result = service.cancel_all_reminders(1, 1)
    assert result is True


def test_is_overdue(service):
    assert service._is_overdue("2020-01-01", date.today()) is True
    assert service._is_overdue("2099-01-01", date.today()) is False


def test_is_overdue_invalid(service):
    assert service._is_overdue("bad", date.today()) is False


def test_fetch_unpaid_invoices(service):
    service._repo.get_unpaid_invoices_for_reminders.return_value = []
    result = service._fetch_unpaid_invoices()
    assert result == []


def test_fetch_unpaid_invoices_with_search(service):
    service._repo.get_unpaid_invoices_for_reminders.return_value = []
    result = service._fetch_unpaid_invoices(search="test")
    assert result == []


def test_get_sent_reminders(service):
    service._repo.get_reminder_status = MagicMock(return_value=[])
    assert service._get_sent_reminders(1) == []


def test_count_sent_reminders(service):
    service._repo.get_sent_reminder_count = MagicMock(return_value=3)
    assert service._count_sent_reminders(1) == 3


def test_get_reminder_status_for_all_active(service):
    service._fetch_unpaid_invoices = MagicMock(return_value=[])
    results, total = service.get_reminder_status_for_all_active()
    assert results == []
    assert total == 0
