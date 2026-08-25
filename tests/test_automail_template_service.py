"""Tests for TemplateService and module-level functions."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.automail.template_service import (
    TemplateService,
    get_available_variables,
    get_sample_context,
    render_template,
)


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock):
    svc = TemplateService(db_mock)
    svc._repo = MagicMock()
    return svc


def test_get_available_variables():
    vars = get_available_variables()
    assert len(vars) > 0
    names = [v["name"] for v in vars]
    assert "invoice_number" in names
    assert "total_amount" in names
    assert "client_name" in names


def test_get_sample_context():
    ctx = get_sample_context()
    assert ctx["invoice_number"] is not None
    assert ctx["total_amount"] is not None
    assert ctx["client_name"] is not None
    assert "(sample)" in ctx["invoice_number"]


def test_render_template():
    template = "Dear {client_name}, your invoice {invoice_number} is due."
    context = {"client_name": "ACME", "invoice_number": "INV-001"}
    result = render_template(template, context)
    assert result == "Dear ACME, your invoice INV-001 is due."


def test_render_template_unknown_variable():
    template = "Hello {unknown_var}, your {invoice_number}"
    context = {"invoice_number": "INV-001"}
    result = render_template(template, context)
    assert "{unknown_var}" in result
    assert "INV-001" in result


def test_render_template_none_value():
    template = "Value: {amount}"
    context = {"amount": None}
    result = render_template(template, context)
    assert result == "Value: "


def test_get_all_templates(service):
    service._repo.get_all_templates.return_value = [{"id": 1}]
    assert service.get_all_templates() == [{"id": 1}]


def test_get_template_by_id(service):
    service._repo.get_template_by_id.return_value = {"id": 1, "name": "Test"}
    result = service.get_template_by_id(1)
    assert result["id"] == 1


def test_get_template_by_id_not_found(service):
    service._repo.get_template_by_id.return_value = None
    assert service.get_template_by_id(999) is None


def test_get_default_template(service):
    service._repo.get_default_template.return_value = {"id": 1}
    assert service.get_default_template() == {"id": 1}


def test_create_template(service):
    service._repo.create_template.return_value = 42
    service._repo.get_template_by_id.return_value = {"id": 42, "name": "Test"}
    data = {"name": "Test", "subject": "Hello"}
    result = service.create_template(data)
    assert result.success is True
    assert result.data["id"] == 42
    service._repo.create_template.assert_called_with(data)


def test_update_template(service):
    service.update_template(1, {"subject": "Updated"})
    service._repo.update_template.assert_called_with(1, {"subject": "Updated"})


def test_delete_template(service):
    service.delete_template(1)
    service._repo.delete_template.assert_called_with(1)


def test_render_email(service):
    template = {
        "subject": "Invoice {invoice_number}",
        "body_text": "Dear {client_name}, your invoice",
        "body_html": "<p>Dear {client_name}</p>",
    }
    context = {"invoice_number": "INV-001", "client_name": "ACME"}
    subject, body_text, body_html = service.render_email(template, context)
    assert subject == "Invoice INV-001"
    assert "ACME" in body_text
    assert "ACME" in body_html


def test_render_email_sanitizes_subject(service):
    template = {"subject": "Hello\nWorld", "body_text": "", "body_html": ""}
    subject, _, _ = service.render_email(template, {})
    assert "\n" not in subject


def test_preview_email(service):
    template = {"subject": "Test", "body_text": "Body", "body_html": ""}
    subject, body_text, body_html = service.preview_email(template)
    assert "Preview" in body_text
    assert "Preview" in body_html


def test_render_template_empty_string():
    result = render_template("", {"key": "val"})
    assert result == ""


def test_render_template_html_preserved():
    template = "<p>Dear {client_name},</p><br/><p>Amount: {total_amount}</p>"
    context = {"client_name": "ACME", "total_amount": "500"}
    result = render_template(template, context)
    assert "<p>Dear ACME,</p>" in result
    assert "500" in result


def test_render_email_empty_context(service):
    template = {
        "subject": "Invoice {invoice_number}",
        "body_text": "Amount: {total_amount}",
        "body_html": "",
    }
    subject, body_text, body_html = service.render_email(template, {})
    assert "{invoice_number}" in subject
    assert "{total_amount}" in body_text


def test_render_email_no_subject_key(service):
    template = {"body_text": "Hello {name}", "body_html": ""}
    subject, body_text, body_html = service.render_email(template, {"name": "John"})
    assert subject == ""
    assert "John" in body_text
    assert body_html == ""


def test_render_email_subject_sanitizes_tabs(service):
    template = {"subject": "Inv\t\t\tDetails", "body_text": "", "body_html": ""}
    subject, _, _ = service.render_email(template, {})
    assert "\t" not in subject


def test_preview_email_with_custom_context(service):
    template = {"subject": "{custom_var}", "body_text": "Value: {custom_var}", "body_html": ""}
    custom_ctx = {"custom_var": "MyValue"}
    subject, body_text, body_html = service.preview_email(template, sample_context=custom_ctx)
    assert "MyValue" in subject
    assert "Preview" in body_text


def test_get_available_variables_structure():
    vars = get_available_variables()
    for v in vars:
        assert "name" in v
        assert "label" in v
        assert "example" in v
        assert "description" in v


def test_get_default_template_not_found(service):
    service._repo.get_default_template.return_value = None
    assert service.get_default_template() is None
