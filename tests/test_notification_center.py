"""Tests for NotificationCenter."""
from unittest.mock import MagicMock, patch

import pytest

from repositories.settings_repository import SettingsRepository
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
    with patch.object(SettingsRepository, "get_settings_by_keys", return_value={"alert_email_recipients": "a@b.com, c@d.com"}):
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


# ── Alert push payload contract (Phase-5) ───────────────────────────────────
# The backend has NO FCM push sender (firebase-admin is not even installed):
# device tokens are stored via POST /mobile/devices/register but nothing in
# backend/services consumes them for outbound pushes.  The alert/approval
# event payload published on the EventBus is therefore ALREADY data-only —
# a plain structured dict (Alert.to_dict()) with the exact fields the mobile
# router parses (type / id / title / message) — with NO FCM notification-type
# wrapper.  These tests pin that contract so the mobile lane can build rich
# data-only notifications with inline actions on top of it.


def test_alert_event_payload_is_data_only(nc):
    """Subscribers receive structured data, never an FCM notification wrapper."""
    captured = {}

    def cb(event_type, alert_data):
        captured["event"] = event_type
        captured["data"] = alert_data

    nc.subscribe(cb)
    alert_payload = {
        "type": "compliance_warning",
        "id": "abc123",
        "severity": "warning",
        "title": "Tacho expiry in 5 days",
        "message": "Driver card expires soon",
        "truck_id": "1",
        "trip_id": None,
        "created_at": "2026-08-04T10:00:00",
    }
    nc._on_alert_created({"data": {"alert": alert_payload}})

    data = captured["data"]
    # The fields the mobile router parses must be top-level structured data.
    assert captured["event"] == "alert_created"
    assert data["type"] == "compliance_warning"
    assert data["id"] == "abc123"
    assert data["title"] == "Tacho expiry in 5 days"
    assert data["message"] == "Driver card expires soon"
    # Data-only: NO FCM notification-type wrapper, no auto-display fields.
    assert "notification" not in data
    assert "body" not in data
    assert "click_action" not in data


def test_approval_payload_keeps_alert_id_for_actions(nc):
    """Approval flow needs the alert id to route approve/reject actions."""
    captured = {}

    def cb(event_type, alert_data):
        captured["data"] = alert_data

    nc.subscribe(cb)
    nc._on_alert_created({"data": {"alert": {"id": "alert-42", "type": "approval",
                                             "title": "Approve expense", "message": "€150"}}})
    # The mobile approval endpoints key off the alert id — it must survive as
    # a top-level data field for inline approve/reject actions.
    assert captured["data"]["id"] == "alert-42"
    assert captured["data"]["type"] == "approval"
