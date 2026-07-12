"""Tests for automail_models.py — Template variables, schedule recurrence, recipient config."""
import pytest
from datetime import date, datetime
from pydantic import ValidationError
from models.automail_models import (
    EmailTemplateCreate,
    SendReminderRequest,
    SendReminderResult,
)


class TestEmailTemplateCreate:
    @pytest.mark.parametrize(
        "name, subject, body_html, language, type_",
        [
            ("Reminder", "Payment Reminder", "<p>Dear {{client}}</p>", "ro", "reminder"),
            ("Invoice", "Your Invoice", "<p>Invoice {{number}}</p>", "en", "invoice"),
            ("Dunning", "Final Notice", "<p>Overdue {{amount}}</p>", "ro", "dunning"),
            ("Welcome", "Welcome", "<p>Hello</p>", "en", "reminder"),
        ],
    )
    def test_template_create_valid(self, name, subject, body_html, language, type_):
        t = EmailTemplateCreate(name=name, subject=subject, body_html=body_html, language=language, type=type_)
        assert t.name == name
        assert t.subject == subject
        assert t.language == language
        assert t.type == type_

    def test_template_create_defaults(self):
        t = EmailTemplateCreate(name="Test", subject="Subject", body_html="<p>Body</p>")
        assert t.language == "ro"
        assert t.type == "reminder"

    @pytest.mark.parametrize("name", ["", "   ", "\t\n"])
    def test_template_name_empty_raises(self, name):
        with pytest.raises(ValidationError, match="Template name is required"):
            EmailTemplateCreate(name=name, subject="S", body_html="<p>B</p>")

    def test_template_name_stripped(self):
        t = EmailTemplateCreate(name="  My Template  ", subject="S", body_html="<p>B</p>")
        assert t.name == "My Template"

    def test_template_body_html_not_empty(self):
        t = EmailTemplateCreate(name="Test", subject="S", body_html="<p>Content</p>")
        assert t.body_html == "<p>Content</p>"


class TestSendReminderRequest:
    @pytest.mark.parametrize(
        "template_id, client_id, recipient_email",
        [
            (1, 10, "client@example.com"),
            (2, 20, "test@domain.ro"),
            (3, 30, "user@sub.domain.co.uk"),
        ],
    )
    def test_reminder_valid(self, template_id, client_id, recipient_email):
        r = SendReminderRequest(
            template_id=template_id,
            client_id=client_id,
            recipient_email=recipient_email,
        )
        assert r.template_id == template_id
        assert r.client_id == client_id
        assert r.recipient_email == recipient_email

    @pytest.mark.parametrize("email", ["invalid", "noatsign", "plainaddress", ""])
    def test_reminder_invalid_email_raises(self, email):
        with pytest.raises(ValidationError, match="Invalid email address"):
            SendReminderRequest(
                template_id=1,
                client_id=1,
                recipient_email=email,
            )

    def test_reminder_defaults(self):
        r = SendReminderRequest(
            template_id=1,
            client_id=1,
            recipient_email="a@b.com",
        )
        assert r.invoice_id is None
        assert r.trip_id is None
        assert r.send_date is None
        assert r.attachments == []

    def test_reminder_with_optional_fields(self):
        sd = date(2026, 8, 1)
        r = SendReminderRequest(
            template_id=5,
            client_id=50,
            invoice_id=100,
            trip_id=200,
            recipient_email="client@firma.ro",
            send_date=sd,
            attachments=[1, 2, 3],
        )
        assert r.invoice_id == 100
        assert r.trip_id == 200
        assert r.send_date == sd
        assert r.attachments == [1, 2, 3]


class TestSendReminderResult:
    def test_reminder_result_success(self):
        now = datetime.now()
        r = SendReminderResult(
            email_id=42,
            sent_to="client@example.com",
            template_name="Reminder Template",
            sent_at=now,
            success=True,
        )
        assert r.email_id == 42
        assert r.success is True
        assert r.error_message == ""

    def test_reminder_result_failure(self):
        now = datetime.now()
        r = SendReminderResult(
            email_id=43,
            sent_to="client@example.com",
            template_name="Reminder",
            sent_at=now,
            success=False,
            error_message="SMTP connection refused",
        )
        assert r.success is False
        assert r.error_message == "SMTP connection refused"
