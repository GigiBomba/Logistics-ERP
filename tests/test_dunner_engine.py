"""Tests for DunnerEngine."""
from unittest.mock import MagicMock, patch

import pytest

from services.operations.dunner_engine import DunnerEngine


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def engine(db_mock):
    nc = MagicMock()
    eng = DunnerEngine(db_mock, notification_center=nc)
    eng._rules = MagicMock()
    return eng


@patch("services.operations.dunner_engine.AutoMailRepository")
def test_evaluate_all_disabled(mock_repo, engine):
    engine._rules.get.return_value = False
    result = engine.evaluate_all()
    assert result == 0


def test_evaluate_all_no_notification_center(db_mock):
    eng = DunnerEngine(db_mock, notification_center=None)
    eng._rules = MagicMock()
    eng._rules.get.return_value = True
    result = eng.evaluate_all()
    assert result == 0


def test_evaluate_all_no_db():
    eng = DunnerEngine(db=None, notification_center=MagicMock())
    eng._rules = MagicMock()
    eng._rules.get.return_value = True
    result = eng.evaluate_all()
    assert result == 0


@patch("services.operations.dunner_engine.AutoMailRepository")
@patch("services.operations.dunner_engine.ReminderService")
@patch("services.operations.dunner_engine.TemplateService")
def test_evaluate_all_no_schedules(mock_template, mock_reminder, mock_repo, engine):
    engine._rules.get.return_value = True
    mock_repo_instance = MagicMock()
    mock_repo.return_value = mock_repo_instance
    mock_repo_instance.get_active_schedules.return_value = []
    result = engine.evaluate_all()
    assert result == 0


@patch("services.operations.dunner_engine.AutoMailRepository")
@patch("services.operations.dunner_engine.ReminderService")
@patch("services.operations.dunner_engine.TemplateService")
def test_evaluate_all_no_invoices(mock_template, mock_reminder, mock_repo, engine):
    engine._rules.get.return_value = True
    mock_repo_instance = MagicMock()
    mock_repo.return_value = mock_repo_instance
    mock_repo_instance.get_active_schedules.return_value = [{"id": 1, "name": "schedule_1"}]
    mock_repo_instance.get_all_templates.return_value = {}
    mock_repo_instance.get_all_overrides.return_value = {}
    mock_repo_instance.get_all_settings.return_value = {}
    engine._fetch_due_invoices = MagicMock(return_value=[])
    result = engine.evaluate_all()
    assert result == 0


def test_has_been_sent_no_db(engine):
    engine._db = None
    assert engine._has_been_sent(1, "test") is False


def test_count_sent_for_invoice_no_db(engine):
    engine._db = None
    assert engine._count_sent_for_invoice(1) == 0


def test_fetch_due_invoices(engine):
    with patch("services.operations.dunner_engine.InvoiceRepository") as mock_inv_cls:
        mock_inv = MagicMock()
        mock_inv.get_dunner_due_invoices.return_value = []
        mock_inv_cls.return_value = mock_inv
        result = engine._fetch_due_invoices()
        assert result == []


def test_resolve_client_email_direct(engine):
    result = engine._resolve_client_email({"client_email": "test@test.com"})
    assert result == "test@test.com"


def test_resolve_client_email_no_email(engine):
    result = engine._resolve_client_email({"client_email": "", "client_name": ""})
    assert result is None


def test_collect_trip_documents(engine):
    with patch("services.operations.dunner_engine.PackageBuilder") as mock_builder:
        mock_builder_instance = MagicMock()
        mock_builder.return_value = mock_builder_instance
        mock_builder_instance.list_trip_documents.return_value = []
        result = engine._collect_trip_documents(1)
        assert result == []


def test_log_sent(engine):
    engine._db = MagicMock()
    with patch("services.operations.dunner_engine.InvoiceRepository") as mock_inv_cls:
        mock_inv = MagicMock()
        mock_inv_cls.return_value = mock_inv
        engine._log_sent(invoice_id=1, trip_id=1, reminder_type="test",
                         days_offset=0, recipient_email="test@test.com")
        mock_inv.insert_reminder.assert_called_once()


def test_shutdown(engine):
    engine._event_bus = MagicMock()
    engine.shutdown()
    engine._event_bus.unsubscribe.assert_called_once()


def test_subscribe(engine):
    engine._event_bus = MagicMock()
    engine._subscribe()
    engine._event_bus.subscribe.assert_called_once()


def test_on_daily_check(engine):
    engine.evaluate_all = MagicMock()
    engine._on_daily_check({})
    engine.evaluate_all.assert_called_once()
