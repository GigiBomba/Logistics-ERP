"""Comprehensive unit tests for export.* Co-Pilot tools.

Tests cover:
- BaseTool contract compliance for both export tools
- Tool execution with mocked ExportService
- Parameter schema validation (Pydantic level)
- Tool-level validate() logic
- Error handling (service failure, no DB, exceptions)

Blueprint: §9 — Registry enforcement.
"""
from __future__ import annotations


import asyncio
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


def _make_export_result(success: bool = True, file_path: str = "/tmp/report.pdf",
                        errors: list = None) -> MagicMock:
    """Build a mock ExportService result (ServiceResult-based)."""
    result = MagicMock()
    result.success = success
    result.errors = errors or []

    data = MagicMock()
    data.file_path = file_path
    result.data = data if success else None
    return result


# ═══════════════════════════════════════════════════════════════════════════
#  BaseTool contract — both export tools
# ═══════════════════════════════════════════════════════════════════════════

EXPORT_TOOL_NAMES = [
    "export.generate_pdf_report",
    "export.generate_excel",
]


class TestExportToolContract:
    """Every export tool must satisfy the BaseTool contract."""

    @pytest.mark.parametrize("name", EXPORT_TOOL_NAMES)
    def test_tool_registered(self, name):
        tool = get_tool(name)
        assert tool is not None, f"Tool '{name}' not found in registry"

    @pytest.mark.parametrize("name", EXPORT_TOOL_NAMES)
    def test_tool_has_name(self, name):
        tool = get_tool(name)
        assert tool.name == name

    @pytest.mark.parametrize("name", EXPORT_TOOL_NAMES)
    def test_tool_has_semver_version(self, name):
        tool = get_tool(name)
        import re
        assert re.match(r"^\d+\.\d+\.\d+$", tool.tool_version)

    @pytest.mark.parametrize("name", EXPORT_TOOL_NAMES)
    def test_tool_has_description(self, name):
        tool = get_tool(name)
        assert tool.description and tool.description.strip()

    @pytest.mark.parametrize("name", EXPORT_TOOL_NAMES)
    def test_tool_has_permission(self, name):
        tool = get_tool(name)
        assert tool.required_permission and tool.required_permission.strip()
        assert tool.required_permission == "export:write"

    @pytest.mark.parametrize("name", EXPORT_TOOL_NAMES)
    def test_tool_has_parameters_schema(self, name):
        tool = get_tool(name)
        from pydantic import BaseModel
        assert issubclass(tool.parameters_schema, BaseModel)

    @pytest.mark.parametrize("name", EXPORT_TOOL_NAMES)
    def test_tool_not_deprecated(self, name):
        tool = get_tool(name)
        assert not tool.deprecated

    @pytest.mark.parametrize("name", EXPORT_TOOL_NAMES)
    def test_tool_confirmation_level(self, name):
        tool = get_tool(name)
        assert tool.confirmation_level == ConfirmationLevel.INFORMATIONAL

    @pytest.mark.parametrize("name", EXPORT_TOOL_NAMES)
    def test_tool_supports_undo_correct(self, name):
        tool = get_tool(name)
        assert tool.supports_undo is False

    @pytest.mark.parametrize("name", EXPORT_TOOL_NAMES)
    def test_validate_returns_list(self, name, ctx):
        tool = get_tool(name)
        params = tool.parameters_schema(entity_type="trip")
        errors = asyncio.run(tool.validate(params, ctx))
        assert isinstance(errors, list)

    @pytest.mark.parametrize("name", EXPORT_TOOL_NAMES)
    def test_execute_returns_tool_result(self, name, ctx):
        tool = get_tool(name)
        params = tool.parameters_schema(entity_type="trip")
        result = asyncio.run(tool.execute(params, ctx))
        assert isinstance(result, ToolResult)
        assert result.status in ("success", "failed", "unavailable", "permission_denied", "needs_confirmation")
        assert result.message_key and result.message_key.strip()


# ═══════════════════════════════════════════════════════════════════════════
#  Parameter schema validation
#  Both export tools share ExportParams — tests apply to both.
# ═══════════════════════════════════════════════════════════════════════════


class TestExportParams:
    """ExportParams (shared by both export tools) schema edge cases."""

    @pytest.mark.parametrize("tool_name", EXPORT_TOOL_NAMES)
    def test_accepts_minimal_params(self, tool_name):
        tool = get_tool(tool_name)
        params = tool.parameters_schema(entity_type="trip")
        assert params.entity_type == "trip"
        assert params.entity_ids == []
        assert params.template == "default"
        assert params.language == "en"
        assert params.include_logo is True

    @pytest.mark.parametrize("tool_name", EXPORT_TOOL_NAMES)
    def test_accepts_all_params(self, tool_name):
        tool = get_tool(tool_name)
        params = tool.parameters_schema(
            entity_type="invoice",
            entity_ids=[1, 2, 3],
            template="detailed",
            language="ro",
            include_logo=False,
        )
        assert params.entity_type == "invoice"
        assert params.entity_ids == [1, 2, 3]
        assert params.template == "detailed"
        assert params.language == "ro"
        assert params.include_logo is False

    @pytest.mark.parametrize("tool_name", EXPORT_TOOL_NAMES)
    def test_validate_rejects_unsupported_entity_type(self, tool_name, ctx):
        tool = get_tool(tool_name)
        params = tool.parameters_schema(entity_type="bogus")
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("entity_type" in e.lower() for e in errors)

    @pytest.mark.parametrize("tool_name", EXPORT_TOOL_NAMES)
    def test_validate_rejects_unsupported_language(self, tool_name, ctx):
        tool = get_tool(tool_name)
        params = tool.parameters_schema(entity_type="trip", language="de")
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("language" in e.lower() for e in errors)

    @pytest.mark.parametrize("tool_name", EXPORT_TOOL_NAMES)
    def test_validate_supported_entity_types(self, tool_name, ctx):
        tool = get_tool(tool_name)
        supported = {"trip", "invoice", "receipt", "cmr", "dispatch_board", "analytics"}
        for etype in supported:
            params = tool.parameters_schema(entity_type=etype)
            errors = asyncio.run(tool.validate(params, ctx))
            entity_errors = [e for e in errors if "entity_type" in e.lower()]
            assert len(entity_errors) == 0, f"Entity type '{etype}' should be valid"

    @pytest.mark.parametrize("tool_name", EXPORT_TOOL_NAMES)
    def test_validate_supported_languages(self, tool_name, ctx):
        tool = get_tool(tool_name)
        for lang in ("en", "ro"):
            params = tool.parameters_schema(entity_type="trip", language=lang)
            errors = asyncio.run(tool.validate(params, ctx))
            lang_errors = [e for e in errors if "language" in e.lower()]
            assert len(lang_errors) == 0, f"Language '{lang}' should be valid"


# ═══════════════════════════════════════════════════════════════════════════
#  Execution — mocked ExportService
# ═══════════════════════════════════════════════════════════════════════════


class TestExportPdfReportExecution:
    """export.generate_pdf_report execute() with mocked ExportService."""

    @patch("backend.services.export_service.ExportService")
    def test_execute_success(self, MockExportService, ctx_with_db):
        tool = get_tool("export.generate_pdf_report")

        mock_service = MagicMock()
        mock_service.export.return_value = _make_export_result(
            success=True, file_path="/tmp/report_42.pdf",
        )
        MockExportService.return_value = mock_service

        params = tool.parameters_schema(
            entity_type="trip", entity_ids=[1, 2, 3], template="detailed",
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        assert result.data["file_path"] == "/tmp/report_42.pdf"
        assert result.data["format"] == "pdf"
        assert result.message_key == "copilot.tool.export.generate_pdf_ok"
        mock_service.export.assert_called_once()

    @patch("backend.services.export_service.ExportService")
    def test_execute_service_failure(self, MockExportService, ctx_with_db):
        tool = get_tool("export.generate_pdf_report")

        mock_service = MagicMock()
        mock_service.export.return_value = _make_export_result(
            success=False, errors=[MagicMock(message="No data for export")],
        )
        MockExportService.return_value = mock_service

        params = tool.parameters_schema(entity_type="trip")
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.export.generate_pdf_failed"

    @patch("backend.services.export_service.ExportService")
    def test_execute_success_no_data(self, MockExportService, ctx_with_db):
        """Export returns success but no data — returns failed."""
        tool = get_tool("export.generate_pdf_report")

        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = None
        mock_result.errors = []
        mock_service.export.return_value = mock_result
        MockExportService.return_value = mock_service

        params = tool.parameters_schema(entity_type="invoice")
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"

    def test_execute_no_db(self, ctx):
        tool = get_tool("export.generate_pdf_report")
        params = tool.parameters_schema(entity_type="trip")
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "unavailable"
        assert result.message_key == "copilot.tool.db_unavailable"

    @patch("backend.services.export_service.ExportService")
    def test_execute_exception(self, MockExportService, ctx_with_db):
        tool = get_tool("export.generate_pdf_report")
        mock_service = MagicMock()
        mock_service.export.side_effect = RuntimeError("Export engine crashed")
        MockExportService.return_value = mock_service

        params = tool.parameters_schema(entity_type="trip")
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.export.generate_pdf_failed"


class TestExportExcelExecution:
    """export.generate_excel execute() with mocked ExportService."""

    @patch("backend.services.export_service.ExportService")
    def test_execute_success(self, MockExportService, ctx_with_db):
        tool = get_tool("export.generate_excel")

        mock_service = MagicMock()
        mock_service.export.return_value = _make_export_result(
            success=True, file_path="/tmp/export_42.xlsx",
        )
        MockExportService.return_value = mock_service

        params = tool.parameters_schema(entity_type="receipt")
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        assert result.data["file_path"] == "/tmp/export_42.xlsx"
        assert result.data["format"] == "excel"
        assert result.message_key == "copilot.tool.export.generate_excel_ok"
        # Verify format was set to excel
        call_args = mock_service.export.call_args[0][0]
        assert call_args.format == "excel"

    @patch("backend.services.export_service.ExportService")
    def test_execute_service_failure(self, MockExportService, ctx_with_db):
        tool = get_tool("export.generate_excel")

        mock_service = MagicMock()
        mock_service.export.return_value = _make_export_result(
            success=False, errors=[MagicMock(message="Export failed")],
        )
        MockExportService.return_value = mock_service

        params = tool.parameters_schema(entity_type="trip")
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.export.generate_excel_failed"

    def test_execute_no_db(self, ctx):
        tool = get_tool("export.generate_excel")
        params = tool.parameters_schema(entity_type="trip")
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "unavailable"
        assert result.message_key == "copilot.tool.db_unavailable"

    @patch("backend.services.export_service.ExportService")
    def test_execute_exception(self, MockExportService, ctx_with_db):
        tool = get_tool("export.generate_excel")
        mock_service = MagicMock()
        mock_service.export.side_effect = RuntimeError("Excel generation error")
        MockExportService.return_value = mock_service

        params = tool.parameters_schema(entity_type="trip")
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.export.generate_excel_failed"
