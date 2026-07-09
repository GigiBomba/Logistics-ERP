"""Tests for email template rendering (document_automation.email_template)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.document_automation.email_template import (
    EmailTemplateService,
    _format_documents,
    _sanitize_header_value,
    render_template,
)
from services.document_automation.types import CustomerInfo
from tests.test_helpers import make_db


# ── render_template (pure) ───────────────────────────────────────────────

class TestRenderTemplate:
    """Tests for the module-level render_template function."""

    def test_render_template_replaces_variables(self):
        """Simple variable replacement works."""
        template = "Dear {name}, your {item} is ready."
        context = {"name": "John", "item": "invoice"}
        result = render_template(template, context)
        assert result == "Dear John, your invoice is ready."

    def test_render_template_leaves_missing_vars_as_is(self):
        """Missing variables are preserved in the output."""
        template = "Hello {name}, your {unknown_var}"
        context = {"name": "Alice"}
        result = render_template(template, context)
        assert result == "Hello Alice, your {unknown_var}"

    def test_render_template_none_value_becomes_empty(self):
        """A variable mapped to None becomes an empty string."""
        template = "Value: [{amount}]"
        context = {"amount": None}
        result = render_template(template, context)
        assert result == "Value: []"

    def test_render_template_empty_string(self):
        """Empty template returns empty string."""
        result = render_template("", {"key": "val"})
        assert result == ""

    def test_render_template_preserves_html(self):
        """HTML in the template is preserved after substitution."""
        template = "<p>Hello {name}</p>"
        result = render_template(template, {"name": "<b>World</b>"})
        assert result == "<p>Hello <b>World</b></p>"

    def test_render_template_multiple_occurrences(self):
        """A variable appearing multiple times is replaced each time."""
        template = "{x} + {x} = {y}"
        result = render_template(template, {"x": "1", "y": "2"})
        assert result == "1 + 1 = 2"

    def test_render_template_no_tokens(self):
        """Template without any tokens is returned unchanged."""
        template = "Plain text without tokens"
        result = render_template(template, {"anything": "value"})
        assert result == "Plain text without tokens"


# ── _sanitize_header_value ───────────────────────────────────────────────

class TestSanitizeHeaderValue:
    """Tests for the module-level _sanitize_header_value function."""

    def test_sanitize_header_removes_newlines(self):
        """CR and LF characters are replaced with space."""
        result = _sanitize_header_value("Hello\nWorld\rTest")
        assert "\n" not in result
        assert "\r" not in result
        assert result == "Hello World Test"

    def test_sanitize_header_removes_tabs_and_nulls(self):
        """Tab and null characters are replaced with space."""
        result = _sanitize_header_value("Subject\twith\0null")
        assert "\t" not in result
        assert "\0" not in result
        assert "Subject with null" == result

    def test_sanitize_header_strips_whitespace(self):
        """Leading/trailing whitespace is stripped."""
        result = _sanitize_header_value("  Hello World  ")
        assert result == "Hello World"

    def test_sanitize_header_none_becomes_empty(self):
        """A None value is handled gracefully and returns empty string."""
        result = _sanitize_header_value(None)  # type: ignore[arg-type]
        assert result == ""


# ── _format_documents ────────────────────────────────────────────────────

class TestFormatDocuments:
    """Tests for the module-level _format_documents function."""

    def test_format_documents_returns_bulleted_list(self):
        """Documents are formatted as a bulleted list with size."""
        docs = [
            {"file_name": "invoice.pdf", "file_size": 204800},
            {"file_name": "cmr.pdf", "file_size": 102400},
        ]
        result = _format_documents(docs)
        assert "invoice.pdf" in result
        assert "cmr.pdf" in result
        assert "KB" in result or "kB" in result

    def test_format_documents_empty_list(self):
        """Empty document list returns a fallback message."""
        result = _format_documents([])
        assert "no documents" in result.lower()

    def test_format_documents_uses_title_fallback(self):
        """When file_name is missing, falls back to title."""
        docs = [{"title": "scanned_doc", "file_size": 500}]
        result = _format_documents(docs)
        assert "scanned_doc" in result

    def test_format_documents_missing_size(self):
        """Missing or zero file_size shows '?'."""
        docs = [{"file_name": "doc.pdf", "file_size": 0}]
        result = _format_documents(docs)
        assert "doc.pdf" in result
        assert "?" in result

    def test_format_documents_large_file_in_mb(self):
        """File size > 1 MB is shown in MB."""
        docs = [{"file_name": "large.pdf", "file_size": 3 * 1024 * 1024}]
        result = _format_documents(docs)
        assert "3.0 MB" in result


# ── EmailTemplateService ─────────────────────────────────────────────────

class TestEmailTemplateService:
    """Tests for EmailTemplateService methods."""

    @pytest.fixture
    def sample_trip(self):
        return {
            "id": 42,
            "place_of_loading": "Rotterdam",
            "delivery_country": "Germany",
            "start_date": "2026-07-09T10:00:00",
            "client_name": "Test Client",
        }

    @pytest.fixture
    def sample_customer(self):
        return CustomerInfo(
            client={"name": "ACME Corp", "contact_person": "Alice Smith"},
            primary_contact={"full_name": "Alice Smith"},
            all_emails=["alice@acme.com"],
            default_email="alice@acme.com",
        )

    @pytest.fixture
    def sample_documents(self):
        return [
            {"file_name": "invoice.pdf", "file_size": 204800},
            {"file_name": "cmr.pdf", "file_size": 102400},
        ]

    # -- build_context --

    def test_build_context_with_all_fields(self, sample_trip, sample_customer, sample_documents):
        """build_context returns expected keys with correct values."""
        svc = EmailTemplateService(prefs=None)
        ctx = svc.build_context(sample_trip, sample_customer, sample_documents)

        assert ctx["trip_id"] == 42
        assert ctx["client_name"] == "ACME Corp"
        assert ctx["contact_name"] == "Alice Smith"
        assert ctx["origin"] == "Rotterdam"
        assert ctx["destination"] == "Germany"
        assert ctx["trip_date"] == "2026-07-09"
        assert "invoice.pdf" in ctx["document_list"]
        assert ctx["company_name"] == "Operion ERP"

    def test_build_context_customer_none_uses_fallback(self, sample_trip, sample_documents):
        """When customer is None, fallback values are used."""
        svc = EmailTemplateService(prefs=None)
        ctx = svc.build_context(sample_trip, None, sample_documents)

        assert ctx["client_name"] == "—"
        assert ctx["contact_name"] == "Sir/Madam"
        assert ctx["trip_id"] == 42

    def test_build_context_with_no_contact_uses_client_name(self, sample_trip, sample_documents):
        """When customer has no primary contact, fall back to client name."""
        customer = CustomerInfo(
            client={"name": "ACME Corp", "contact_person": ""},
            primary_contact=None,
            all_emails=["info@acme.com"],
            default_email="info@acme.com",
        )
        svc = EmailTemplateService(prefs=None)
        ctx = svc.build_context(sample_trip, customer, sample_documents)

        assert ctx["contact_name"] == "ACME Corp"

    def test_build_context_missing_trip_fields(self, sample_documents):
        """When trip fields are missing, origin/destination show '—'."""
        trip = {"id": 99}
        svc = EmailTemplateService(prefs=None)
        ctx = svc.build_context(trip, None, sample_documents)

        assert ctx["origin"] == "—"
        assert ctx["destination"] == "—"
        assert ctx["trip_date"] == "—"

    # -- render_subject --

    def test_render_subject_sanitizes_header_injection(self, sample_trip, sample_customer):
        """Subject is sanitised to remove header-injection characters."""
        trip = {**sample_trip, "id": "1\nBcc: evil@example.com"}
        svc = EmailTemplateService(prefs=None)
        subject = svc.render_subject(trip, sample_customer)
        assert "\n" not in subject
        assert "\r" not in subject
        assert subject == "Documents for Trip #1 Bcc: evil@example.com — ACME Corp"

    def test_render_subject_without_customer(self, sample_trip):
        """Subject renders even when customer is None."""
        svc = EmailTemplateService(prefs=None)
        subject = svc.render_subject(sample_trip, None)
        assert "Trip #42" in subject

    # -- render_body --

    def test_render_body_includes_document_list(self, sample_trip, sample_customer, sample_documents):
        """Body contains the formatted document list."""
        svc = EmailTemplateService(prefs=None)
        body = svc.render_body(sample_trip, sample_customer, sample_documents)
        assert "invoice.pdf" in body
        assert "cmr.pdf" in body
        assert "Dear Alice Smith" in body

    def test_render_body_empty_documents(self, sample_trip, sample_customer):
        """Body with empty document list shows fallback and still works."""
        svc = EmailTemplateService(prefs=None)
        body = svc.render_body(sample_trip, sample_customer, [])
        assert "no documents" in body.lower()
        assert "Rotterdam" in body

    def test_render_body_no_customer(self, sample_trip, sample_documents):
        """Body renders with Sir/Madam fallback when customer is None."""
        svc = EmailTemplateService(prefs=None)
        body = svc.render_body(sample_trip, None, sample_documents)
        assert "Sir/Madam" in body

    # -- get_company_name --

    def test_get_company_name_returns_default(self):
        """Without preferences, get_company_name returns 'Operion ERP'."""
        svc = EmailTemplateService(prefs=None)
        assert svc.get_company_name() == "Operion ERP"

    def test_get_company_name_from_prefs(self):
        """When preferences provide a custom name, that name is used."""
        prefs = MagicMock()
        prefs.get_setting.return_value = "My Transport Co"
        svc = EmailTemplateService(prefs=prefs)
        name = svc.get_company_name()
        assert name == "My Transport Co"
        prefs.get_setting.assert_called_once_with("automation_company_name", "Operion ERP")

    def test_get_company_name_prefs_exception_falls_back(self):
        """If preferences.get_setting raises, fall back to default."""
        prefs = MagicMock()
        prefs.get_setting.side_effect = RuntimeError("DB down")
        svc = EmailTemplateService(prefs=prefs)
        name = svc.get_company_name()
        assert name == "Operion ERP"

    # -- subject_template / body_template overrides --

    def test_subject_template_from_prefs(self):
        """Custom subject template from preferences is used."""
        prefs = MagicMock()
        prefs.get_setting.return_value = "Custom Subject {trip_id}"
        svc = EmailTemplateService(prefs=prefs)
        subject = svc.render_subject({"id": 7}, None)
        assert subject == "Custom Subject 7"

    def test_body_template_from_prefs(self):
        """Custom body template from preferences is used."""
        prefs = MagicMock()
        prefs.get_setting.return_value = "Custom Body {trip_id}"
        svc = EmailTemplateService(prefs=prefs)
        body = svc.render_body({"id": 7}, None, [])
        assert body == "Custom Body 7"
