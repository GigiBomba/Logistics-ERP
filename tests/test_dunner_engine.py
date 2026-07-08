"""Tests for DunnerEngine."""
from __future__ import annotations

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


@patch("services.operations.dunner_engine.AutoMailRepository")
@patch("services.operations.dunner_engine.ReminderService")
@patch("services.operations.dunner_engine.TemplateService")
def test_evaluate_all_skips_when_days_mismatch(mock_template, mock_reminder, mock_repo, engine):
    """When days_past_due doesn't match any schedule target, no reminder is sent."""
    engine._rules.get.return_value = True
    engine._notification_center = MagicMock()
    engine._db = MagicMock()

    mock_repo_instance = MagicMock()
    mock_repo.return_value = mock_repo_instance
    mock_repo_instance.get_active_schedules.return_value = [
        {"id": 1, "name": "day_30", "template_id": 1}
    ]
    mock_repo_instance.get_all_templates.return_value = {1: {"id": 1, "subject": "Test", "body": "Body"}}
    mock_repo_instance.get_all_overrides.return_value = {}
    mock_repo_instance.get_all_settings.return_value = {}
    mock_repo_instance.get_reminder_count.return_value = 0

    # Set up _fetch_due_invoices to return an invoice with a non-matching due date
    from datetime import date, timedelta
    due = (date.today() - timedelta(days=10)).isoformat()

    engine._fetch_due_invoices = MagicMock(return_value=[
        {"invoice_id": 1, "trip_id": 10, "client_id": 1, "due_date": due,
         "invoice_number": "INV-001", "total_amount": 1000, "currency": "EUR",
         "client_email": "c@c.com", "client_company_name": "Client",
         "client_name": "Client", "client_contact": "", "truck_plate": "",
         "driver_name": ""}
    ])

    # ReminderService._compute_target_days would return something else
    mock_reminder._compute_target_days.return_value = 30
    engine._resolve_client_email = MagicMock(return_value="c@c.com")

    result = engine.evaluate_all()
    assert result == 0  # no reminders sent because days_past_due (10) != target (30)


@patch("services.operations.dunner_engine.AutoMailRepository")
@patch("services.operations.dunner_engine.TemplateService")
def test_evaluate_all_client_override_disabled(mock_template, mock_repo, engine):
    """When client override has is_disabled=True, skip that invoice."""
    engine._rules.get.return_value = True
    engine._notification_center = MagicMock()
    engine._db = MagicMock()

    mock_repo_instance = MagicMock()
    mock_repo.return_value = mock_repo_instance
    mock_repo_instance.get_active_schedules.return_value = [
        {"id": 1, "name": "day_30", "template_id": 1}
    ]
    mock_repo_instance.get_all_templates.return_value = {1: {"id": 1, "subject": "Test", "body": "Body"}}
    mock_repo_instance.get_all_overrides.return_value = {1: {"is_disabled": True, "client_id": 1}}
    mock_repo_instance.get_all_settings.return_value = {}
    mock_repo_instance.has_reminder_been_sent.return_value = False
    mock_repo_instance.get_reminder_count.return_value = 0

    from datetime import date, timedelta
    due = (date.today() - timedelta(days=30)).isoformat()
    engine._fetch_due_invoices = MagicMock(return_value=[
        {"invoice_id": 1, "trip_id": 10, "client_id": 1, "due_date": due,
         "invoice_number": "INV-001", "total_amount": 1000, "currency": "EUR",
         "client_email": "c@c.com", "client_company_name": "Client",
         "client_name": "Client", "client_contact": "", "truck_plate": "",
         "driver_name": ""}
    ])
    engine._resolve_client_email = MagicMock(return_value="c@c.com")

    result = engine.evaluate_all()
    assert result == 0


@patch("services.operations.dunner_engine.AutoMailRepository")
@patch("services.operations.dunner_engine.TemplateService")
def test_evaluate_all_max_reminders_reached(mock_template, mock_repo, engine):
    """When max reminders reached for an invoice, skip it."""
    engine._rules.get.return_value = True
    engine._notification_center = MagicMock()
    engine._db = MagicMock()

    mock_repo_instance = MagicMock()
    mock_repo.return_value = mock_repo_instance
    mock_repo_instance.get_active_schedules.return_value = [
        {"id": 1, "name": "day_30", "template_id": 1}
    ]
    mock_repo_instance.get_all_templates.return_value = {1: {"id": 1, "subject": "Test", "body": "Body"}}
    mock_repo_instance.get_all_overrides.return_value = {}
    mock_repo_instance.get_all_settings.return_value = {"max_reminders_per_invoice": "5"}
    mock_repo_instance.get_reminder_count.return_value = 5  # already at max

    from datetime import date, timedelta
    due = (date.today() - timedelta(days=30)).isoformat()
    engine._fetch_due_invoices = MagicMock(return_value=[
        {"invoice_id": 1, "trip_id": 10, "client_id": 1, "due_date": due,
         "invoice_number": "INV-001", "total_amount": 1000, "currency": "EUR",
         "client_email": "c@c.com", "client_company_name": "Client",
         "client_name": "Client", "client_contact": "", "truck_plate": "",
         "driver_name": ""}
    ])
    engine._resolve_client_email = MagicMock(return_value="c@c.com")
    # Override _has_been_sent to return False so it passes the "already sent" check
    engine._has_been_sent = MagicMock(return_value=False)

    result = engine.evaluate_all()
    assert result == 0


@patch("services.operations.dunner_engine.AutoMailRepository")
@patch("services.operations.dunner_engine.TemplateService")
def test_evaluate_all_no_client_email(mock_template, mock_repo, engine):
    """When client has no email, skip the invoice."""
    engine._rules.get.return_value = True
    engine._notification_center = MagicMock()
    engine._db = MagicMock()

    mock_repo_instance = MagicMock()
    mock_repo.return_value = mock_repo_instance
    mock_repo_instance.get_active_schedules.return_value = [
        {"id": 1, "name": "day_30", "template_id": 1}
    ]
    mock_repo_instance.get_all_templates.return_value = {1: {"id": 1, "subject": "Test", "body": "Body"}}
    mock_repo_instance.get_all_overrides.return_value = {}
    mock_repo_instance.get_all_settings.return_value = {}
    mock_repo_instance.get_reminder_count.return_value = 0

    from datetime import date, timedelta
    due = (date.today() - timedelta(days=30)).isoformat()
    engine._fetch_due_invoices = MagicMock(return_value=[
        {"invoice_id": 1, "trip_id": 10, "client_id": 1, "due_date": due,
         "invoice_number": "INV-001", "total_amount": 1000, "currency": "EUR",
         "client_email": "", "client_company_name": "Client",
         "client_name": "Client", "client_contact": "", "truck_plate": "",
         "driver_name": ""}
    ])
    engine._resolve_client_email = MagicMock(return_value=None)

    result = engine.evaluate_all()
    assert result == 0


def test_has_been_sent_already_sent(engine):
    """_has_been_sent returns True when the reminder was already sent."""
    engine._db = MagicMock()
    with patch("services.operations.dunner_engine.InvoiceRepository") as mock_inv_cls:
        mock_inv = MagicMock()
        mock_inv.has_reminder_been_sent.return_value = True
        mock_inv_cls.return_value = mock_inv
        assert engine._has_been_sent(1, "day_30") is True


def test_has_been_sent_exception_returns_false(engine):
    """_has_been_sent returns False on exception."""
    engine._db = MagicMock()
    with patch("services.operations.dunner_engine.InvoiceRepository") as mock_inv_cls:
        mock_inv = MagicMock()
        mock_inv.has_reminder_been_sent.side_effect = Exception("DB error")
        mock_inv_cls.return_value = mock_inv
        assert engine._has_been_sent(1, "day_30") is False


def test_count_sent_for_invoice_exception_returns_zero(engine):
    """_count_sent_for_invoice returns 0 on exception."""
    engine._db = MagicMock()
    with patch("services.operations.dunner_engine.InvoiceRepository") as mock_inv_cls:
        mock_inv = MagicMock()
        mock_inv.get_reminder_count.side_effect = Exception("DB error")
        mock_inv_cls.return_value = mock_inv
        assert engine._count_sent_for_invoice(1) == 0


def test_resolve_client_email_fallback(engine):
    """_resolve_client_email falls back to ClientRepository name lookup."""
    engine._db = MagicMock()
    with patch("services.operations.dunner_engine.ClientRepository") as mock_cls:
        mock_cli = MagicMock()
        mock_cli.get_client_email_by_name.return_value = "found@name.com"
        mock_cls.return_value = mock_cli
        result = engine._resolve_client_email(
            {"client_email": "", "client_name": "Some Client"}
        )
        assert result == "found@name.com"
        mock_cli.get_client_email_by_name.assert_called_with("Some Client")


def test_resolve_client_email_fallback_fails(engine):
    """_resolve_client_email returns None when both paths fail."""
    engine._db = MagicMock()
    with patch("services.operations.dunner_engine.ClientRepository") as mock_cls:
        mock_cli = MagicMock()
        mock_cli.get_client_email_by_name.return_value = None
        mock_cls.return_value = mock_cli
        result = engine._resolve_client_email(
            {"client_email": "", "client_name": "Unknown"}
        )
        assert result is None


def test_fetch_due_invoices_exception(engine):
    """_fetch_due_invoices returns [] on exception."""
    with patch("services.operations.dunner_engine.InvoiceRepository") as mock_inv_cls:
        mock_inv = MagicMock()
        mock_inv.get_dunner_due_invoices.side_effect = Exception("DB error")
        mock_inv_cls.return_value = mock_inv
        result = engine._fetch_due_invoices()
        assert result == []


def test_collect_trip_documents_exception(engine):
    """_collect_trip_documents returns [] on exception."""
    with patch("services.operations.dunner_engine.PackageBuilder") as mock_builder:
        mock_builder_instance = MagicMock()
        mock_builder.return_value = mock_builder_instance
        mock_builder_instance.list_trip_documents.side_effect = Exception("Error")
        result = engine._collect_trip_documents(1)
        assert result == []


def test_log_sent_exception_logged(engine):
    """_log_sent should not raise on exception."""
    engine._db = MagicMock()
    with patch("services.operations.dunner_engine.InvoiceRepository") as mock_inv_cls:
        mock_inv = MagicMock()
        mock_inv.insert_reminder.side_effect = Exception("Insert error")
        mock_inv_cls.return_value = mock_inv
        # Should not raise
        engine._log_sent(invoice_id=1, trip_id=1, reminder_type="test",
                         days_offset=0, recipient_email="test@test.com")
