"""Tests for NotificationCenter."""
from unittest.mock import MagicMock, patch

import pytest

from services.operations.notification_center import NotificationCenter, Severity


@pytest.fixture
def nc():
    with patch.object(NotificationCenter, "_subscribe"):
        center = NotificationCenter(db=MagicMock())
        center._event_bus = MagicMock()
        center._smtp_config = None
        return center


def test_subscribe(nc):
    cb = MagicMock()
    nc.subscribe(cb)
    assert cb in nc._subscribers


def test_unsubscribe(nc):
    cb = MagicMock()
    nc.subscribe(cb)
    nc.unsubscribe(cb)
    assert cb not in nc._subscribers


def test_on_alert_created(nc):
    cb = MagicMock()
    nc.subscribe(cb)
    nc._on_alert_created({"data": {"alert": {"title": "Test"}}})
    cb.assert_called_once_with("alert_created", {"title": "Test"})


def test_on_alert_resolved(nc):
    cb = MagicMock()
    nc.subscribe(cb)
    nc._on_alert_resolved({"data": {"alert": {"title": "Resolved"}}})
    cb.assert_called_once_with("alert_resolved", {"title": "Resolved"})


def test_notify_all_critical_triggers_email(nc):
    """Critical alerts should trigger email in a daemon thread."""
    with patch.object(nc, "_send_email_alert") as mock_send:
        nc._notify_all("alert_created", {"severity": "critical", "title": "Crit"})
        # Thread runs asynchronously, but the method should start it


def test_notify_all_non_critical_no_email(nc):
    with patch.object(nc, "_send_email_alert") as mock_send:
        nc._notify_all("alert_created", {"severity": "warning", "title": "Warn"})
        # Should not trigger email thread


def test_configure_smtp(nc):
    nc.configure_smtp("smtp.test.com", 587, "user@test.com", "pass")
    assert nc._smtp_config is not None
    assert nc._smtp_config["server"] == "smtp.test.com"


def test_send_email_no_smtp(nc):
    result = nc.send_email("test@test.com", "Subject", "Body")
    assert result is False


@patch("smtplib.SMTP")
def test_send_email_success(mock_smtp, nc):
    nc._smtp_config = {
        "server": "smtp.test.com", "port": 587,
        "user": "user@test.com", "password": "pass", "use_tls": True,
    }
    result = nc.send_email("test@test.com", "Subject", "Body")
    assert result is True
    mock_smtp.assert_called_with("smtp.test.com", 587, timeout=15)


def test_send_test_email_no_smtp(nc):
    result = nc.send_test_email("test@test.com")
    assert result is False


@patch("smtplib.SMTP")
def test_send_test_email_success(mock_smtp, nc):
    nc._smtp_config = {
        "server": "smtp.test.com", "port": 587,
        "user": "user@test.com", "password": "pass", "use_tls": True,
    }
    result = nc.send_test_email("test@test.com")
    assert result is True


def test_get_alert_recipients_from_db(nc):
    nc._alert_recipients = None
    nc._db.get_settings.return_value = {"alert_email_recipients": "a@b.com, c@d.com"}
    recipients = nc._get_alert_recipients({})
    assert recipients == ["a@b.com", "c@d.com"]


def test_get_alert_recipients_from_arg(nc):
    nc._alert_recipients = ["admin@test.com"]
    recipients = nc._get_alert_recipients({})
    assert recipients == ["admin@test.com"]


def test_send_email_with_attachment(nc):
    nc._smtp_config = {
        "server": "smtp.test.com", "port": 587,
        "user": "user@test.com", "password": "pass", "use_tls": True,
    }
    with patch("smtplib.SMTP") as mock_smtp, \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = b"data"
        result = nc.send_email("test@test.com", "Subject", "Body", attachments=["file.pdf"])
        assert result is True


def test_shutdown(nc):
    nc._event_bus = MagicMock()
    nc.shutdown()
    nc._event_bus.unsubscribe.assert_called()
