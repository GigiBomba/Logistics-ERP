"""Tests for TemplateService."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.document.template_service import TemplateService


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def repo_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock, repo_mock):
    return TemplateService(db_mock, repo_mock)


def test_create_template(service):
    service._repo.create_template.return_value = 42
    tid = service.create_template(name="Test Template", description="A test",
                                  category="general", template_type="pdf",
                                  fields=[{"name": "field1"}])
    assert tid == 42
    service._repo.create_template.assert_called_once()


def test_get_templates(service):
    service._repo.get_templates.return_value = [{"id": 1}]
    result = service.get_templates(category="general")
    assert result == [{"id": 1}]
    service._repo.get_templates.assert_called_with("general")


def test_generate_from_template_not_found(service):
    service._repo.get_template_by_id.return_value = None
    result = service.generate_from_template(999, {})
    assert result is None


def test_generate_from_template_unknown_type(service):
    service._repo.get_template_by_id.return_value = {
        "id": 1, "category": "general", "template_type": "docx",
        "fields_json": "[]", "name": "Test",
    }
    result = service.generate_from_template(1, {})
    assert result is None


@patch("services.invoicing.cmr_generator.CMRGenerator")
def test_generate_cmr_template(mock_cmr_gen, service):
    mock_gen = MagicMock()
    mock_cmr_gen.return_value = mock_gen
    mock_gen.generate.return_value = "/path/to/cmr.pdf"
    service._repo.get_template_by_id.return_value = {
        "id": 1, "category": "cmr", "template_type": "pdf",
        "fields_json": "[]", "name": "CMR Template",
    }
    result = service.generate_from_template(1, {"trip_id": "42"})
    assert result == "/path/to/cmr.pdf"
    mock_gen.generate.assert_called_once()


@patch("services.document.template_service.os.makedirs")
@patch("reportlab.platypus.SimpleDocTemplate")
def test_generate_contract_pdf(mock_doc, mock_makedirs, service):
    service._repo.get_template_by_id.return_value = {
        "id": 2, "category": "contract", "template_type": "pdf",
        "fields_json": "[]", "name": "Contract Template",
    }
    with patch("os.path.exists", return_value=True):
        result = service.generate_from_template(2, {"client_name": "Test Client"})
        # Should generate a contract PDF
        assert result is not None
        assert result.endswith(".pdf")
