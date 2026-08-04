"""Comprehensive unit tests for the Tahograph import tool (tahograf.import_file).

Tests cover:
- BaseTool contract (name, description, permissions, parameters_schema, confirmation_level)
- Parameter schema validation (valid, empty, edge cases)
- validate() behaviour
- execute() with mocked TachoService (success, service failure, exception)
- Error handling (missing db, missing data, etc.)

Blueprint: §9 — Registry enforcement, §9.1 Level 1 INFORMATIONAL.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from backend.copilot.schemas import ConfirmationLevel, SessionContext, ToolResult
from backend.copilot.tools.base import ToolExecutionContext
from backend.copilot.tools.registry import get_tool, run_startup_validation

# Ensure tools are loaded
from backend.copilot.planner import _ensure_tools_loaded  # noqa: E402
_ensure_tools_loaded()
_validation_errors = run_startup_validation()
_prod_errors = [e for e in _validation_errors if "test." not in e]
assert len(_prod_errors) == 0, f"Production tool registry errors: {_prod_errors}"

TOOL_NAME = "tahograf.import_file"


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_ctx(**overrides: Any) -> ToolExecutionContext:
    """Build a minimal ToolExecutionContext."""
    kwargs: dict = dict(
        company_id=1,
        user_id=1,
        role="admin",
        session_context=SessionContext(),
        services={},
    )
    kwargs.update(overrides)
    return ToolExecutionContext(**kwargs)


def _make_mock_import_result(
    import_id: int = 42,
    driver_activities: int = 3,
    warnings: list[str] | None = None,
    success: bool = True,
    errors: list | None = None,
) -> MagicMock:
    """Build a mock ServiceResult-like object wrapping TachoImportResult-like data."""
    mock_data = MagicMock()
    mock_data.import_id = import_id
    mock_data.driver_activities = driver_activities
    mock_data.warnings = warnings or []
    mock_data.vehicle_activities = 2

    mock_result = MagicMock()
    mock_result.success = success
    mock_result.data = mock_data
    mock_result.errors = errors or []
    return mock_result


# ═══════════════════════════════════════════════════════════════════════════════
# 1. BaseTool contract
# ═══════════════════════════════════════════════════════════════════════════════


class TestTachoImportFileContract:
    """Verify the tool meets BaseTool contract requirements."""

    def test_tool_is_registered(self):
        tool = get_tool(TOOL_NAME)
        assert tool is not None, f"Tool '{TOOL_NAME}' not found in registry"

    def test_tool_name(self):
        tool = get_tool(TOOL_NAME)
        assert tool.name == TOOL_NAME

    def test_tool_version_is_semver(self):
        tool = get_tool(TOOL_NAME)
        parts = tool.tool_version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_description_is_non_empty(self):
        tool = get_tool(TOOL_NAME)
        assert tool.description and tool.description.strip()

    def test_required_permission(self):
        tool = get_tool(TOOL_NAME)
        assert tool.required_permission == "tacho:write"

    def test_confirmation_level(self):
        tool = get_tool(TOOL_NAME)
        assert tool.confirmation_level == ConfirmationLevel.INFORMATIONAL

    def test_supports_undo_false(self):
        tool = get_tool(TOOL_NAME)
        assert not tool.supports_undo

    def test_deprecated_false(self):
        tool = get_tool(TOOL_NAME)
        assert not tool.deprecated

    def test_parameters_schema_is_basemodel(self):
        tool = get_tool(TOOL_NAME)
        assert issubclass(tool.parameters_schema, BaseModel)

    def test_parameters_schema_has_expected_fields(self):
        tool = get_tool(TOOL_NAME)
        fields = tool.parameters_schema.model_fields
        assert "file_path" in fields
        assert "driver_id" in fields
        assert "vehicle_id" in fields

    def test_parameters_schema_file_path_is_required(self):
        tool = get_tool(TOOL_NAME)
        assert tool.parameters_schema.model_fields["file_path"].is_required()

    def test_parameters_schema_driver_id_is_optional(self):
        tool = get_tool(TOOL_NAME)
        assert not tool.parameters_schema.model_fields["driver_id"].is_required()

    def test_parameters_schema_vehicle_id_is_optional(self):
        tool = get_tool(TOOL_NAME)
        assert not tool.parameters_schema.model_fields["vehicle_id"].is_required()

    def test_undo_raises_not_implemented(self):
        tool = get_tool(TOOL_NAME)
        with pytest.raises(NotImplementedError):
            asyncio.run(tool.undo("token", _make_ctx()))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Parameter schema validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestTachoImportParamsSchema:
    """Pydantic schema-level validation."""

    def test_accepts_valid_file_path(self):
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(file_path="/data/tacho/export.ddd")
        assert params.file_path == "/data/tacho/export.ddd"
        assert params.driver_id is None
        assert params.vehicle_id is None

    def test_accepts_valid_path_with_all_optionals(self):
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(
            file_path="/data/tacho/export.ddd",
            driver_id=5,
            vehicle_id=10,
        )
        assert params.file_path == "/data/tacho/export.ddd"
        assert params.driver_id == 5
        assert params.vehicle_id == 10

    def test_rejects_empty_file_path_min_length(self):
        """Pydantic schema rejects empty string (min_length=1)."""
        tool = get_tool(TOOL_NAME)
        with pytest.raises(ValidationError):
            tool.parameters_schema(file_path="")

    def test_accepts_different_file_extensions(self):
        tool = get_tool(TOOL_NAME)
        for ext in [".ddd", ".c1b", ".esm", ".DDD", ".C1B"]:
            params = tool.parameters_schema(file_path=f"/path/to/file{ext}")
            assert params.file_path == f"/path/to/file{ext}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. validate()
# ═══════════════════════════════════════════════════════════════════════════════


class TestTachoImportValidate:
    """Tool-level validate() behaviour."""

    def test_validate_accepts_valid_path(self):
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(file_path="/data/tacho/export.ddd")
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert isinstance(errors, list)
        assert len(errors) == 0

    def test_validate_accepts_path_with_optionals(self):
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(
            file_path="/data/tacho/export.ddd", driver_id=1, vehicle_id=2,
        )
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert isinstance(errors, list)
        assert len(errors) == 0

    def test_validate_rejects_empty_path(self):
        """validate() should catch empty file_path (strip check)."""
        tool = get_tool(TOOL_NAME)
        # Use model_construct to bypass Pydantic min_length and test tool.validate()
        params = tool.parameters_schema.model_construct(file_path="")
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert len(errors) > 0
        assert any("file_path" in e for e in errors)

    def test_validate_returns_empty_list_for_valid(self):
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(file_path="/valid/path.ddd")
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert errors == []


# ═══════════════════════════════════════════════════════════════════════════════
# 4. execute() — success path
# ═══════════════════════════════════════════════════════════════════════════════


class TestTachoImportExecuteSuccess:
    """execute() with mocked TachoService returning success."""

    def test_execute_returns_tool_result(self):
        """execute() must always return ToolResult."""
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(file_path="/data/tacho/export.ddd")

        ctx = _make_ctx(services={"db": MagicMock()})
        result = asyncio.run(tool.execute(params, ctx))

        assert isinstance(result, ToolResult)

    def test_execute_success_with_import_id(self):
        """Successful import returns import_id in data."""
        with patch("backend.services.tacho_service.TachoService") as mock_tacho_service_class:
            mock_service = MagicMock()
            mock_service.import_file.return_value = _make_mock_import_result(import_id=99)
            mock_tacho_service_class.return_value = mock_service

            tool = get_tool(TOOL_NAME)
            params = tool.parameters_schema(file_path="/data/tacho/export.ddd")
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            assert result.data is not None
            assert result.data["import_id"] == 99
            assert result.data["driver_hours_analyzed"] == 3
            assert result.message_key == "copilot.tool.tacho.import_file_ok"

    def test_execute_success_with_warnings(self):
        """Successful import includes warnings list."""
        with patch("backend.services.tacho_service.TachoService") as mock_tacho_service_class:
            mock_service = MagicMock()
            mock_service.import_file.return_value = _make_mock_import_result(
                warnings=["Speed limit exceeded", "Missing rest period"],
            )
            mock_tacho_service_class.return_value = mock_service

            tool = get_tool(TOOL_NAME)
            params = tool.parameters_schema(file_path="/data/tacho/export.ddd")
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            assert len(result.data["warnings"]) == 2
            assert "Speed limit exceeded" in result.data["warnings"]

    def test_execute_with_driver_and_vehicle_ids(self):
        """driver_id and vehicle_id are passed through to TachoService.import_file()."""
        with patch("backend.services.tacho_service.TachoService") as mock_tacho_service_class:
            mock_service = MagicMock()
            mock_service.import_file.return_value = _make_mock_import_result()
            mock_tacho_service_class.return_value = mock_service

            tool = get_tool(TOOL_NAME)
            params = tool.parameters_schema(
                file_path="/data/tacho/export.ddd", driver_id=7, vehicle_id=14,
            )
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            # Verify the service was called with the right params
            call_args = mock_service.import_file.call_args
            assert call_args is not None
            request = call_args[0][0]
            assert request.driver_id == 7
            assert request.vehicle_id == 14
            assert request.file_path == "/data/tacho/export.ddd"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. execute() — error handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestTachoImportExecuteErrors:
    """Error handling in execute()."""

    def test_execute_no_db_returns_unavailable(self):
        """When db is not in services, must return unavailable."""
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(file_path="/data/tacho/export.ddd")
        ctx = _make_ctx(services={})  # No db
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "unavailable"
        assert result.message_key == "copilot.tool.db_unavailable"

    def test_execute_db_is_none_returns_unavailable(self):
        """When db is None in services, must return unavailable."""
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(file_path="/data/tacho/export.ddd")
        ctx = _make_ctx(services={"db": None})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "unavailable"

    def test_execute_service_returns_failed(self):
        """When TachoService returns unsuccessful result, tool returns failed."""
        with patch("backend.services.tacho_service.TachoService") as mock_tacho_service_class:
            mock_service = MagicMock()
            from models.common import ErrorDetail
            mock_service.import_file.return_value = _make_mock_import_result(
                success=False,
                errors=[ErrorDetail(field="file", message="Invalid file format", code="INVALID_FILE")],
            )
            mock_tacho_service_class.return_value = mock_service

            tool = get_tool(TOOL_NAME)
            params = tool.parameters_schema(file_path="/data/tacho/bad.ddd")
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "failed"
            assert result.message_key == "copilot.tool.tacho.import_file_failed"

    def test_execute_service_returns_no_data(self):
        """When TachoService returns success but data is None, tool returns failed."""
        with patch("backend.services.tacho_service.TachoService") as mock_tacho_service_class:
            mock_service = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.data = None
            mock_result.errors = []
            mock_service.import_file.return_value = mock_result
            mock_tacho_service_class.return_value = mock_service

            tool = get_tool(TOOL_NAME)
            params = tool.parameters_schema(file_path="/data/tacho/export.ddd")
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "failed"
            assert result.message_key == "copilot.tool.tacho.import_file_failed"

    def test_execute_service_raises_exception(self):
        """When TachoService raises an unexpected exception, tool returns failed."""
        with patch("backend.services.tacho_service.TachoService") as mock_tacho_service_class:
            mock_service = MagicMock()
            mock_service.import_file.side_effect = RuntimeError("Disk I/O error")
            mock_tacho_service_class.return_value = mock_service

            tool = get_tool(TOOL_NAME)
            params = tool.parameters_schema(file_path="/data/tacho/export.ddd")
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "failed"
            assert "Disk I/O error" in result.message_params.get("error", "")

    def test_execute_service_empty_errors(self):
        """When success=False and errors list is empty, tool still returns failed."""
        with patch("backend.services.tacho_service.TachoService") as mock_tacho_service_class:
            mock_service = MagicMock()
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.data = None
            mock_result.errors = []
            mock_service.import_file.return_value = mock_result
            mock_tacho_service_class.return_value = mock_service

            tool = get_tool(TOOL_NAME)
            params = tool.parameters_schema(file_path="/data/tacho/export.ddd")
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "failed"
            assert result.message_key == "copilot.tool.tacho.import_file_failed"

    def test_execute_message_params_include_import_id(self):
        """Success message_params include import_id, driver_activities, warnings_count."""
        with patch("backend.services.tacho_service.TachoService") as mock_tacho_service_class:
            mock_service = MagicMock()
            mock_service.import_file.return_value = _make_mock_import_result(
                import_id=7, driver_activities=5, warnings=["warn"],
            )
            mock_tacho_service_class.return_value = mock_service

            tool = get_tool(TOOL_NAME)
            params = tool.parameters_schema(file_path="/data/tacho/export.ddd")
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            assert result.message_params.get("import_id") == 7
            assert result.message_params.get("driver_activities") == 5
            assert result.message_params.get("warnings_count") == 1
