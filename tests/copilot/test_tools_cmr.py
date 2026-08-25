"""Comprehensive unit tests for document.generate_cmr Co-Pilot tool.

Tests cover:
- BaseTool contract compliance
- Tool execution with mocked CMRGenerator
- Parameter schema validation (Pydantic level)
- Tool-level validate() logic
- Error handling (service failure, no DB, exceptions, legacy fallback)

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


def _make_service_result(success: bool = True, file_path: str = "/tmp/cmr_42.pdf",
                         cmr_number: str = "CMR-001", errors: list = None):
    """Build a ServiceResult as returned by CMRGenerator.

    Uses the real ``CmrGenerateResult`` (ServiceResult[CmrResult]) so that
    the tool's ``isinstance(raw, ServiceResult)`` check passes.
    """
    from datetime import datetime
    from models.cmr_models import CmrGenerateResult, CmrResult
    from models.common import ErrorDetail

    if errors is None:
        errors = []
    return CmrGenerateResult(
        success=success,
        data=CmrResult(
            cmr_number=cmr_number,
            trip_id=1,
            file_path=file_path,
            copies=4,
            generated_at=datetime.now(),
        ) if success else None,
        errors=[ErrorDetail(field="", message=e, code="ERROR") for e in errors],
    )


# ═══════════════════════════════════════════════════════════════════════════
#  BaseTool contract
# ═══════════════════════════════════════════════════════════════════════════

CMR_TOOL_NAME = "document.generate_cmr"


class TestCmrToolContract:
    """document.generate_cmr must satisfy the BaseTool contract."""

    def test_tool_registered(self):
        tool = get_tool(CMR_TOOL_NAME)
        assert tool is not None, f"Tool '{CMR_TOOL_NAME}' not found in registry"

    def test_tool_has_name(self):
        tool = get_tool(CMR_TOOL_NAME)
        assert tool.name == CMR_TOOL_NAME

    def test_tool_has_semver_version(self):
        tool = get_tool(CMR_TOOL_NAME)
        import re
        assert re.match(r"^\d+\.\d+\.\d+$", tool.tool_version)

    def test_tool_has_description(self):
        tool = get_tool(CMR_TOOL_NAME)
        assert tool.description and tool.description.strip()

    def test_tool_has_permission(self):
        tool = get_tool(CMR_TOOL_NAME)
        assert tool.required_permission and tool.required_permission.strip()
        assert tool.required_permission == "documents:write"

    def test_tool_has_parameters_schema(self):
        tool = get_tool(CMR_TOOL_NAME)
        from pydantic import BaseModel
        assert issubclass(tool.parameters_schema, BaseModel)

    def test_tool_not_deprecated(self):
        tool = get_tool(CMR_TOOL_NAME)
        assert not tool.deprecated

    def test_tool_confirmation_level(self):
        tool = get_tool(CMR_TOOL_NAME)
        assert tool.confirmation_level == ConfirmationLevel.INFORMATIONAL

    def test_tool_supports_undo_correct(self):
        tool = get_tool(CMR_TOOL_NAME)
        assert tool.supports_undo is False

    def test_validate_returns_list(self, ctx):
        tool = get_tool(CMR_TOOL_NAME)
        params = tool.parameters_schema(trip_id=1)
        errors = asyncio.run(tool.validate(params, ctx))
        assert isinstance(errors, list)

    def test_execute_returns_tool_result(self, ctx):
        tool = get_tool(CMR_TOOL_NAME)
        params = tool.parameters_schema(trip_id=1)
        result = asyncio.run(tool.execute(params, ctx))
        assert isinstance(result, ToolResult)
        assert result.status in ("success", "failed", "unavailable", "permission_denied", "needs_confirmation")
        assert result.message_key and result.message_key.strip()


# ═══════════════════════════════════════════════════════════════════════════
#  Parameter schema validation
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateCmrParams:
    """document.generate_cmr parameter schema edge cases."""

    def test_accepts_minimal_params(self):
        tool = get_tool(CMR_TOOL_NAME)
        params = tool.parameters_schema(trip_id=1)
        assert params.trip_id == 1
        assert params.language == "en"
        assert params.copies == 4
        assert params.include_efti is True
        assert params.adr_class is None
        assert params.adr_un_number is None

    def test_accepts_all_params(self):
        tool = get_tool(CMR_TOOL_NAME)
        params = tool.parameters_schema(
            trip_id=42,
            language="ro",
            copies=2,
            include_efti=False,
            adr_class="3",
            adr_un_number="UN1203",
        )
        assert params.trip_id == 42
        assert params.language == "ro"
        assert params.copies == 2
        assert params.include_efti is False
        assert params.adr_class == "3"
        assert params.adr_un_number == "UN1203"

    def test_rejects_trip_id_zero(self):
        tool = get_tool(CMR_TOOL_NAME)
        with pytest.raises(ValidationError):
            tool.parameters_schema(trip_id=0)

    def test_rejects_trip_id_negative(self):
        tool = get_tool(CMR_TOOL_NAME)
        with pytest.raises(ValidationError):
            tool.parameters_schema(trip_id=-1)

    def test_rejects_copies_below_min(self):
        tool = get_tool(CMR_TOOL_NAME)
        with pytest.raises(ValidationError):
            tool.parameters_schema(trip_id=1, copies=0)

    def test_rejects_copies_above_max(self):
        tool = get_tool(CMR_TOOL_NAME)
        with pytest.raises(ValidationError):
            tool.parameters_schema(trip_id=1, copies=11)

    def test_validate_rejects_unsupported_language(self, ctx):
        tool = get_tool(CMR_TOOL_NAME)
        params = tool.parameters_schema(trip_id=1, language="xx")
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("xx" in e for e in errors)

    def test_validate_supported_languages(self, ctx):
        tool = get_tool(CMR_TOOL_NAME)
        for lang in ("en", "ro", "de", "fr"):
            params = tool.parameters_schema(trip_id=1, language=lang)
            errors = asyncio.run(tool.validate(params, ctx))
            assert len(errors) == 0

    def test_validate_accepts_valid(self, ctx):
        tool = get_tool(CMR_TOOL_NAME)
        params = tool.parameters_schema(trip_id=5, language="de", copies=3)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  Execution — mocked CMRGenerator
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateCmrExecution:
    """document.generate_cmr execute() with mocked CMRGenerator."""

    @patch("services.invoicing.cmr_generator.CMRGenerator")
    def test_execute_success(self, MockGenerator, ctx_with_db):
        """Successful CMR generation returns file path and CMR number."""
        tool = get_tool(CMR_TOOL_NAME)

        mock_gen = MagicMock()
        mock_gen.generate.return_value = _make_service_result(
            success=True,
            file_path="/tmp/cmr_42.pdf",
            cmr_number="CMR-2024-001",
        )
        MockGenerator.return_value = mock_gen

        params = tool.parameters_schema(trip_id=42, language="en", copies=4)
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        assert result.data["file_paths"] == ["/tmp/cmr_42.pdf"]
        assert result.data["cmr_number"] == "CMR-2024-001"
        assert result.message_key == "copilot.tool.document.generate_cmr_ok"
        # Verify generate was called with CmrGenerateRequest and user_id
        mock_gen.generate.assert_called_once()
        call_args = mock_gen.generate.call_args
        assert call_args[0][1] == 42  # user_id

    @patch("services.invoicing.cmr_generator.CMRGenerator")
    def test_execute_with_adr_params(self, MockGenerator, ctx_with_db):
        """ADR params are accepted (even if not yet passed to the generator)."""
        tool = get_tool(CMR_TOOL_NAME)

        mock_gen = MagicMock()
        mock_gen.generate.return_value = _make_service_result(
            success=True,
            file_path="/tmp/cmr_adr.pdf",
            cmr_number="CMR-ADR-001",
        )
        MockGenerator.return_value = mock_gen

        params = tool.parameters_schema(
            trip_id=10,
            adr_class="3",
            adr_un_number="UN1203",
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"

    @patch("services.invoicing.cmr_generator.CMRGenerator")
    def test_execute_legacy_fallback(self, MockGenerator, ctx_with_db):
        """When generator returns a string (legacy path), returns failed."""
        tool = get_tool(CMR_TOOL_NAME)

        mock_gen = MagicMock()
        mock_gen.generate.return_value = "/tmp/legacy_cmr.pdf"  # str, not ServiceResult
        MockGenerator.return_value = mock_gen

        params = tool.parameters_schema(trip_id=1)
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert "legacy path" in result.message_params.get("error", "").lower()

    @patch("services.invoicing.cmr_generator.CMRGenerator")
    def test_execute_service_failure(self, MockGenerator, ctx_with_db):
        """When generator returns unsuccessful result, returns failed."""
        tool = get_tool(CMR_TOOL_NAME)

        mock_gen = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.errors = [MagicMock(message="Trip not found")]
        mock_result.data = None
        mock_gen.generate.return_value = mock_result
        MockGenerator.return_value = mock_gen

        params = tool.parameters_schema(trip_id=999)
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.document.generate_cmr_failed"

    @patch("services.invoicing.cmr_generator.CMRGenerator")
    def test_execute_success_no_data(self, MockGenerator, ctx_with_db):
        """Generator returns success but no data — should be treated as failure."""
        tool = get_tool(CMR_TOOL_NAME)

        mock_gen = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = None
        mock_result.errors = []
        mock_gen.generate.return_value = mock_result
        MockGenerator.return_value = mock_gen

        params = tool.parameters_schema(trip_id=1)
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"

    def test_execute_no_db(self, ctx):
        """Without db, returns unavailable."""
        tool = get_tool(CMR_TOOL_NAME)
        params = tool.parameters_schema(trip_id=1)
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "unavailable"
        assert result.message_key == "copilot.tool.db_unavailable"

    @patch("services.invoicing.cmr_generator.CMRGenerator")
    def test_execute_exception(self, MockGenerator, ctx_with_db):
        """Exception is caught and returned as failed."""
        tool = get_tool(CMR_TOOL_NAME)
        mock_gen = MagicMock()
        mock_gen.generate.side_effect = RuntimeError("Generator crashed")
        MockGenerator.return_value = mock_gen

        params = tool.parameters_schema(trip_id=1)
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.document.generate_cmr_failed"
