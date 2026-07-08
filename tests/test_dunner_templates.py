"""Tests for dunner_templates module."""

from __future__ import annotations

import pytest

from services.operations.dunner_templates import (
    render_template,
    template_day_27,
    template_day_30,
    template_day_33,
)

# Sample data used across all template tests
SAMPLE_INVOICE = "INV-2024-001"
SAMPLE_AMOUNT = "1,250.00"
SAMPLE_CURRENCY = "EUR"
SAMPLE_DATE = "2026-07-15"
SAMPLE_COMPANY = "ACME Transport Ltd"


class TestRenderTemplate:
    def test_replaces_tokens(self):
        result = render_template("Hello {name}!", {"name": "World"})
        assert result == "Hello World!"

    def test_leaves_unknown_tokens_untouched(self):
        result = render_template("Hello {name}, your {item} is ready.", {"name": "Alice"})
        assert result == "Hello Alice, your {item} is ready."

    def test_multiple_tokens(self):
        result = render_template("{a} + {b} = {c}", {"a": "1", "b": "2", "c": "3"})
        assert result == "1 + 2 = 3"

    def test_none_value_replaced_with_empty(self):
        result = render_template("Value: {value}", {"value": None})
        assert result == "Value: "

    def test_no_placeholders(self):
        result = render_template("Plain text", {"key": "value"})
        assert result == "Plain text"

    def test_repeated_token(self):
        result = render_template("{x} + {x} = {y}", {"x": "2", "y": "4"})
        assert result == "2 + 2 = 4"

    def test_empty_context(self):
        result = render_template("{unchanged}", {})
        assert result == "{unchanged}"


class TestTemplateDay27:
    def test_returns_subject_and_body(self):
        subject, body = template_day_27(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert isinstance(subject, str)
        assert isinstance(body, str)
        assert len(subject) > 0
        assert len(body) > 0

    def test_subject_contains_invoice_number(self):
        subject, _ = template_day_27(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert SAMPLE_INVOICE in subject

    def test_subject_contains_company_name(self):
        subject, _ = template_day_27(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert SAMPLE_COMPANY in subject

    def test_body_contains_invoice_number(self):
        _, body = template_day_27(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert SAMPLE_INVOICE in body

    def test_body_contains_total_amount(self):
        _, body = template_day_27(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert SAMPLE_AMOUNT in body

    def test_body_contains_currency(self):
        _, body = template_day_27(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert SAMPLE_CURRENCY in body

    def test_body_contains_due_date(self):
        _, body = template_day_27(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert SAMPLE_DATE in body

    def test_body_contains_company_name(self):
        _, body = template_day_27(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert SAMPLE_COMPANY in body

    def test_subject_matches_expected_pattern(self):
        subject, _ = template_day_27(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert "Upcoming Payment" in subject
        assert "Invoice" in subject

    def test_body_contains_day_context(self):
        _, body = template_day_27(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert "3 days" in body or "3-days" in body or "scheduled for payment" in body


class TestTemplateDay30:
    def test_returns_subject_and_body(self):
        subject, body = template_day_30(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert isinstance(subject, str)
        assert isinstance(body, str)

    def test_subject_contains_due_today(self):
        subject, _ = template_day_30(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert "Due Today" in subject

    def test_body_contains_all_fields(self):
        _, body = template_day_30(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert SAMPLE_INVOICE in body
        assert SAMPLE_AMOUNT in body
        assert SAMPLE_CURRENCY in body
        assert SAMPLE_DATE in body
        assert SAMPLE_COMPANY in body

    def test_body_mentions_due_today(self):
        _, body = template_day_30(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert "due today" in body.lower()


class TestTemplateDay33:
    def test_returns_subject_and_body(self):
        subject, body = template_day_33(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert isinstance(subject, str)
        assert isinstance(body, str)

    def test_subject_contains_past_due(self):
        subject, _ = template_day_33(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert "Past Due" in subject

    def test_body_contains_all_fields(self):
        _, body = template_day_33(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert SAMPLE_INVOICE in body
        assert SAMPLE_AMOUNT in body
        assert SAMPLE_CURRENCY in body
        assert SAMPLE_DATE in body
        assert SAMPLE_COMPANY in body

    def test_body_reflects_late_status(self):
        _, body = template_day_33(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert "due 3 days ago" in body.lower() or "not yet received" in body.lower()

    def test_body_suggests_forwarding_receipt(self):
        _, body = template_day_33(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert "receipt" in body.lower() or "transaction" in body.lower()


class TestAllTemplatesIncludeFields:
    """All templates should include invoice_number, total_amount, currency, due_date, company_name."""

    FIELDS = ["invoice_number", "total_amount", "currency", "due_date", "company_name"]

    @pytest.mark.parametrize("template_func", [
        template_day_27,
        template_day_30,
        template_day_33,
    ])
    def test_subject_includes_fields(self, template_func):
        """At minimum, the invoice_number and company_name should appear in subjects."""
        subject, body = template_func(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        # Subjects mention the critical identifiers
        assert SAMPLE_INVOICE in subject
        assert SAMPLE_COMPANY in subject

    @pytest.mark.parametrize("template_func", [
        template_day_27,
        template_day_30,
        template_day_33,
    ])
    def test_body_includes_all_fields(self, template_func):
        _, body = template_func(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert SAMPLE_INVOICE in body
        assert SAMPLE_AMOUNT in body
        assert SAMPLE_CURRENCY in body
        assert SAMPLE_DATE in body
        assert SAMPLE_COMPANY in body


class TestEdgeCases:
    def test_empty_strings(self):
        subject, body = template_day_27("", "", "", "", "")
        assert isinstance(subject, str)
        assert isinstance(body, str)

    def test_special_characters(self):
        subject, body = template_day_27(
            "INV/123",
            "$1,000.00",
            "USD",
            "2026-01-01",
            "O'Brien & Sons GmbH",
        )
        assert "INV/123" in subject
        assert "$1,000.00" in body
        assert "O'Brien" in body or "O&Brien" in body


class TestTemplateDay30Expanded:
    """Additional tests for template_day_30."""

    def test_body_contains_due_today_phrase(self):
        _, body = template_day_30(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert "due today" in body.lower()

    def test_body_mentions_remittance_advice(self):
        _, body = template_day_30(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert "remittance" in body.lower()


class TestTemplateDay33Expanded:
    """Additional tests for template_day_33."""

    def test_body_contains_3_days_ago(self):
        _, body = template_day_33(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert "3 days ago" in body.lower()

    def test_body_mentions_transaction_receipt(self):
        _, body = template_day_33(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert "receipt" in body.lower() or "transaction" in body.lower()


class TestAllSubjectsDistinct:
    """All three templates should have distinct subject lines."""

    def test_subjects_are_distinct(self):
        s27, _ = template_day_27(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        s30, _ = template_day_30(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        s33, _ = template_day_33(
            SAMPLE_INVOICE, SAMPLE_AMOUNT, SAMPLE_CURRENCY, SAMPLE_DATE, SAMPLE_COMPANY,
        )
        assert s27 != s30
        assert s30 != s33
        assert s27 != s33


class TestRenderTemplateExpanded:
    """Additional tests for render_template."""

    def test_replaces_overlapping_keys(self):
        """Overlapping keys should be replaced correctly (longer key after shorter)."""
        result = render_template("{key} and {key_extra}", {"key": "A", "key_extra": "B"})
        assert result == "A and B"

    def test_with_html_content(self):
        """HTML content in values should be treated as literal (no escaping)."""
        result = render_template("<p>{name}</p>", {"name": "<b>Bold</b>"})
        assert result == "<p><b>Bold</b></p>"

    def test_empty_template_string(self):
        """Empty template string should return empty string."""
        result = render_template("", {"key": "value"})
        assert result == ""

    def test_context_with_non_string_values(self):
        """Non-string context values should be converted to strings."""
        result = render_template("{a} + {b} = {c}", {"a": 1, "b": 2.5, "c": True})
        assert result == "1 + 2.5 = True"

    def test_newlines_are_preserved(self):
        """Newlines in the template should be preserved."""
        result = render_template("Line1\nLine2\n{name}", {"name": "Test"})
        assert result == "Line1\nLine2\nTest"
