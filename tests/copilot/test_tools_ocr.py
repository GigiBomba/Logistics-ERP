"""Comprehensive unit tests for document.ocr_* Co-Pilot tools.

Tests cover:
- BaseTool contract compliance for both OCR tools
- Tool execution with mocked DocumentService, pipeline, DocumentGrouper
- Parameter schema validation (Pydantic level)
- Tool-level validate() logic
- Error handling (service failure, no DB, pipeline fallback, exceptions)

Blueprint: §9 — Registry enforcement.
"""
from __future__ import annotations


import asyncio
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.copilot.schemas import ConfirmationLevel, SessionContext, ToolResult
from backend.copilot.tools.base import ToolExecutionContext
from backend.copilot.tools.registry import get_tool, run_startup_validation


# ── Module-level setup ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True, scope="module")
def _ensure_registry():
    run_startup_validation()
    yield


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def ctx():
    return ToolExecutionContext(
        company_id=1,
        user_id=42,
        role="dispatcher",
        session_context=SessionContext(),
        services={},
    )


@pytest.fixture
def ctx_with_db():
    return ToolExecutionContext(
        company_id=1,
        user_id=42,
        role="dispatcher",
        session_context=SessionContext(),
        services={"db": MagicMock()},
    )


@pytest.fixture
def temp_pdf():
    """Create a temporary file for testing file-path validation."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 mock content")
        path = f.name
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  BaseTool contract — both OCR tools
# ═══════════════════════════════════════════════════════════════════════════

OCR_TOOL_NAMES = [
    "document.ocr_import",
    "document.ocr_confirm_match",
]


class TestOcrToolContract:
    """Every OCR tool must satisfy the BaseTool contract."""

    @pytest.mark.parametrize("name", OCR_TOOL_NAMES)
    def test_tool_registered(self, name):
        tool = get_tool(name)
        assert tool is not None, f"Tool '{name}' not found in registry"

    @pytest.mark.parametrize("name", OCR_TOOL_NAMES)
    def test_tool_has_name(self, name):
        tool = get_tool(name)
        assert tool.name == name

    @pytest.mark.parametrize("name", OCR_TOOL_NAMES)
    def test_tool_has_semver_version(self, name):
        tool = get_tool(name)
        import re
        assert re.match(r"^\d+\.\d+\.\d+$", tool.tool_version)

    @pytest.mark.parametrize("name", OCR_TOOL_NAMES)
    def test_tool_has_description(self, name):
        tool = get_tool(name)
        assert tool.description and tool.description.strip()

    @pytest.mark.parametrize("name", OCR_TOOL_NAMES)
    def test_tool_has_permission(self, name):
        tool = get_tool(name)
        assert tool.required_permission and tool.required_permission.strip()
        assert tool.required_permission == "documents:write"

    @pytest.mark.parametrize("name", OCR_TOOL_NAMES)
    def test_tool_has_parameters_schema(self, name):
        tool = get_tool(name)
        from pydantic import BaseModel
        assert issubclass(tool.parameters_schema, BaseModel)

    @pytest.mark.parametrize("name", OCR_TOOL_NAMES)
    def test_tool_not_deprecated(self, name):
        tool = get_tool(name)
        assert not tool.deprecated

    def test_ocr_import_confirmation_level(self):
        tool = get_tool("document.ocr_import")
        assert tool.confirmation_level == ConfirmationLevel.INFORMATIONAL

    def test_ocr_confirm_match_confirmation_level(self):
        tool = get_tool("document.ocr_confirm_match")
        assert tool.confirmation_level == ConfirmationLevel.BUSINESS

    @pytest.mark.parametrize("name", OCR_TOOL_NAMES)
    def test_tool_supports_undo_correct(self, name):
        tool = get_tool(name)
        assert tool.supports_undo is False

    @pytest.mark.parametrize("name", OCR_TOOL_NAMES)
    def test_validate_returns_list(self, name, ctx, temp_pdf):
        tool = get_tool(name)
        if name == "document.ocr_import":
            params = tool.parameters_schema(file_path=temp_pdf)
        elif name == "document.ocr_confirm_match":
            params = tool.parameters_schema(
                document_id=1, matched_entity_type="client", matched_entity_id=5,
            )
        else:
            params = tool.parameters_schema()
        errors = asyncio.run(tool.validate(params, ctx))
        assert isinstance(errors, list)

    @pytest.mark.parametrize("name", OCR_TOOL_NAMES)
    def test_execute_returns_tool_result(self, name, ctx, temp_pdf):
        tool = get_tool(name)
        if name == "document.ocr_import":
            params = tool.parameters_schema(file_path=temp_pdf)
        elif name == "document.ocr_confirm_match":
            params = tool.parameters_schema(
                document_id=1, matched_entity_type="client", matched_entity_id=5,
            )
        else:
            params = tool.parameters_schema()
        result = asyncio.run(tool.execute(params, ctx))
        assert isinstance(result, ToolResult)
        assert result.status in ("success", "failed", "unavailable", "permission_denied", "needs_confirmation")
        assert result.message_key and result.message_key.strip()


# ═══════════════════════════════════════════════════════════════════════════
#  Parameter schema validation — OcrImport
# ═══════════════════════════════════════════════════════════════════════════


class TestOcrImportParams:
    """document.ocr_import parameter schema edge cases."""

    def test_accepts_minimal_params(self, temp_pdf):
        tool = get_tool("document.ocr_import")
        params = tool.parameters_schema(file_path=temp_pdf)
        assert params.file_path == temp_pdf
        assert params.document_type == "auto"
        assert params.language == "auto"
        assert params.client_id is None

    def test_accepts_all_params(self, temp_pdf):
        tool = get_tool("document.ocr_import")
        params = tool.parameters_schema(
            file_path=temp_pdf,
            document_type="invoice",
            language="ro",
            client_id=5,
        )
        assert params.document_type == "invoice"
        assert params.language == "ro"
        assert params.client_id == 5

    def test_rejects_empty_file_path(self):
        tool = get_tool("document.ocr_import")
        with pytest.raises(ValidationError):
            tool.parameters_schema(file_path="")

    def test_rejects_extra_fields(self):
        tool = get_tool("document.ocr_import")
        with pytest.raises(ValidationError):
            tool.parameters_schema(file_path="/tmp/test.pdf", extra="x")

    def test_validate_rejects_nonexistent_file(self, ctx):
        tool = get_tool("document.ocr_import")
        params = tool.parameters_schema(file_path="/nonexistent/file.pdf")
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("not found" in e.lower() for e in errors)

    def test_validate_accepts_existing_file(self, ctx, temp_pdf):
        tool = get_tool("document.ocr_import")
        params = tool.parameters_schema(file_path=temp_pdf)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  Parameter schema validation — OcrConfirmMatch
# ═══════════════════════════════════════════════════════════════════════════


class TestOcrConfirmMatchParams:
    """document.ocr_confirm_match parameter schema edge cases."""

    def test_accepts_valid_params(self):
        tool = get_tool("document.ocr_confirm_match")
        params = tool.parameters_schema(
            document_id=1, matched_entity_type="client", matched_entity_id=5,
        )
        assert params.document_id == 1
        assert params.matched_entity_type == "client"
        assert params.matched_entity_id == 5

    def test_rejects_document_id_zero(self):
        tool = get_tool("document.ocr_confirm_match")
        with pytest.raises(ValidationError):
            tool.parameters_schema(
                document_id=0, matched_entity_type="client", matched_entity_id=5,
            )

    def test_rejects_entity_id_zero(self):
        tool = get_tool("document.ocr_confirm_match")
        with pytest.raises(ValidationError):
            tool.parameters_schema(
                document_id=1, matched_entity_type="client", matched_entity_id=0,
            )

    def test_rejects_extra_fields(self):
        tool = get_tool("document.ocr_confirm_match")
        with pytest.raises(ValidationError):
            tool.parameters_schema(
                document_id=1, matched_entity_type="client", matched_entity_id=5,
                extra="x",
            )

    def test_validate_rejects_invalid_entity_type(self, ctx):
        tool = get_tool("document.ocr_confirm_match")
        params = tool.parameters_schema(
            document_id=1, matched_entity_type="bogus", matched_entity_id=5,
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("bogus" in e for e in errors)

    def test_validate_valid_entity_types(self, ctx):
        tool = get_tool("document.ocr_confirm_match")
        for etype in ("client", "trip", "invoice"):
            params = tool.parameters_schema(
                document_id=1, matched_entity_type=etype, matched_entity_id=5,
            )
            errors = asyncio.run(tool.validate(params, ctx))
            assert len(errors) == 0, f"Entity type '{etype}' should be valid"

    def test_validate_passes_valid(self, ctx):
        tool = get_tool("document.ocr_confirm_match")
        params = tool.parameters_schema(
            document_id=10, matched_entity_type="trip", matched_entity_id=42,
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  Execution — document.ocr_import
# ═══════════════════════════════════════════════════════════════════════════


class TestOcrImportExecution:
    """document.ocr_import execute() with mocked DocumentService and pipeline."""

    @patch("services.document_automation.pipeline.run_for_existing_document")
    @patch("backend.services.document_service.DocumentService")
    def test_execute_pipeline_success(
        self, MockDocService, MockPipeline, ctx_with_db, temp_pdf,
    ):
        """Full OCR pipeline completes successfully."""
        tool = get_tool("document.ocr_import")

        mock_service = MagicMock()
        mock_service.upload_legacy.return_value = 42
        MockDocService.return_value = mock_service

        MockPipeline.return_value = {
            "extracted": {"amount": 1500.00, "currency": "EUR"},
            "confidence": 0.95,
        }

        params = tool.parameters_schema(
            file_path=temp_pdf, document_type="invoice", language="ro",
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        assert result.data["document_id"] == 42
        assert result.data["extracted_data"]["amount"] == 1500.00
        assert result.data["confidence"] == 0.95
        assert result.data["status"] == "completed"
        assert result.message_key == "copilot.tool.document.ocr_import_ok"
        mock_service.upload_legacy.assert_called_once()
        MockPipeline.assert_called_once()

    @patch("services.document_automation.pipeline.run_for_existing_document")
    @patch("backend.services.document_service.DocumentService")
    def test_execute_pipeline_fallback(
        self, MockDocService, MockPipeline, ctx_with_db, temp_pdf,
    ):
        """When full pipeline fails, falls back to basic extraction."""
        tool = get_tool("document.ocr_import")

        mock_service = MagicMock()
        mock_service.upload_legacy.return_value = 42
        mock_service.get_by_id.return_value = {
            "mime_type": "application/pdf",
            "file_path": temp_pdf,
        }
        mock_service.extract_text.return_value = "Extracted invoice text line 1"
        MockDocService.return_value = mock_service

        MockPipeline.side_effect = RuntimeError("Pipeline crashed")

        params = tool.parameters_schema(file_path=temp_pdf)
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        assert result.data["document_id"] == 42
        assert result.data["status"] == "extracted"
        assert "Extracted" in result.data["text"]
        assert result.message_key == "copilot.tool.document.ocr_import_ok"

    @patch("services.document_automation.pipeline.run_for_existing_document")
    @patch("backend.services.document_service.DocumentService")
    def test_execute_pipeline_fallback_no_doc(
        self, MockDocService, MockPipeline, ctx_with_db, temp_pdf,
    ):
        """When fallback get_by_id returns None, exception propagates."""
        tool = get_tool("document.ocr_import")

        mock_service = MagicMock()
        mock_service.upload_legacy.return_value = 42
        mock_service.get_by_id.return_value = None
        MockDocService.return_value = mock_service

        MockPipeline.side_effect = RuntimeError("Pipeline crashed")

        params = tool.parameters_schema(file_path=temp_pdf)
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"

    @patch("backend.services.document_service.DocumentService")
    def test_execute_upload_failed(self, MockDocService, ctx_with_db, temp_pdf):
        """When upload_legacy returns falsy, returns failed."""
        tool = get_tool("document.ocr_import")

        mock_service = MagicMock()
        mock_service.upload_legacy.return_value = None
        MockDocService.return_value = mock_service

        params = tool.parameters_schema(file_path=temp_pdf)
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.document.create_failed"

    def test_execute_no_db(self, ctx, temp_pdf):
        """Without db, returns unavailable."""
        tool = get_tool("document.ocr_import")
        params = tool.parameters_schema(file_path=temp_pdf)
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "unavailable"
        assert result.message_key == "copilot.error.no_db"

    @patch("backend.services.document_service.DocumentService")
    def test_execute_exception(self, MockDocService, ctx_with_db, temp_pdf):
        """Top-level exception is caught."""
        tool = get_tool("document.ocr_import")

        mock_service = MagicMock()
        mock_service.upload_legacy.side_effect = RuntimeError("Upload failed")
        MockDocService.return_value = mock_service

        params = tool.parameters_schema(file_path=temp_pdf)
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.unexpected"


# ═══════════════════════════════════════════════════════════════════════════
#  Execution — document.ocr_confirm_match
# ═══════════════════════════════════════════════════════════════════════════


class TestOcrConfirmMatchExecution:
    """document.ocr_confirm_match execute() with mocked services."""

    @patch("backend.services.document_service.DocumentService")
    def test_execute_link_to_client(self, MockDocService, ctx_with_db):
        """Link document to a client entity."""
        tool = get_tool("document.ocr_confirm_match")

        mock_service = MagicMock()
        mock_service.link_document.return_value = True
        MockDocService.return_value = mock_service

        params = tool.parameters_schema(
            document_id=1, matched_entity_type="client", matched_entity_id=5,
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        assert result.data["document_id"] == 1
        assert result.data["linked_to_type"] == "client"
        assert result.data["linked_to_id"] == 5
        mock_service.link_document.assert_called_once_with(1, "client", 5)

    @patch("backend.services.document_service.DocumentService")
    def test_execute_link_to_invoice(self, MockDocService, ctx_with_db):
        """Link document to an invoice entity."""
        tool = get_tool("document.ocr_confirm_match")

        mock_service = MagicMock()
        mock_service.link_document.return_value = True
        MockDocService.return_value = mock_service

        params = tool.parameters_schema(
            document_id=2, matched_entity_type="invoice", matched_entity_id=10,
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        mock_service.link_document.assert_called_once_with(2, "invoice", 10)

    @patch("services.document_automation.document_grouper.DocumentGrouper")
    def test_execute_link_to_trip(self, MockGrouper, ctx_with_db):
        """Linking to a trip uses DocumentGrouper."""
        tool = get_tool("document.ocr_confirm_match")

        mock_grouper = MagicMock()
        mock_grouper.link_existing_document_to_trip.return_value = True
        MockGrouper.return_value = mock_grouper

        params = tool.parameters_schema(
            document_id=3, matched_entity_type="trip", matched_entity_id=15,
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        mock_grouper.link_existing_document_to_trip.assert_called_once_with(
            doc_id=3, trip_id=15, extracted={},
        )

    @patch("backend.services.document_service.DocumentService")
    def test_execute_link_failed(self, MockDocService, ctx_with_db):
        """When link_document returns False, returns failed."""
        tool = get_tool("document.ocr_confirm_match")

        mock_service = MagicMock()
        mock_service.link_document.return_value = False
        MockDocService.return_value = mock_service

        params = tool.parameters_schema(
            document_id=1, matched_entity_type="client", matched_entity_id=5,
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.document.ocr_match_failed"

    @patch("services.document_automation.document_grouper.DocumentGrouper")
    def test_execute_trip_link_failed(self, MockGrouper, ctx_with_db):
        """When DocumentGrouper returns False, returns failed."""
        tool = get_tool("document.ocr_confirm_match")

        mock_grouper = MagicMock()
        mock_grouper.link_existing_document_to_trip.return_value = False
        MockGrouper.return_value = mock_grouper

        params = tool.parameters_schema(
            document_id=3, matched_entity_type="trip", matched_entity_id=15,
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"

    def test_execute_no_db(self, ctx):
        """Without db, returns unavailable."""
        tool = get_tool("document.ocr_confirm_match")
        params = tool.parameters_schema(
            document_id=1, matched_entity_type="client", matched_entity_id=5,
        )
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "unavailable"
        assert result.message_key == "copilot.error.no_db"

    @patch("backend.services.document_service.DocumentService")
    def test_execute_exception(self, MockDocService, ctx_with_db):
        """Top-level exception is caught."""
        tool = get_tool("document.ocr_confirm_match")

        mock_service = MagicMock()
        mock_service.link_document.side_effect = RuntimeError("Link failed")
        MockDocService.return_value = mock_service

        params = tool.parameters_schema(
            document_id=1, matched_entity_type="client", matched_entity_id=5,
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.unexpected"
