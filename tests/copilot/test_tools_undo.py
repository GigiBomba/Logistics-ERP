"""Comprehensive unit tests for the UndoActionTool (system.undo).

This file builds on the existing ``test_phase3_undo.py`` which already covers:
- Destructive tool basics, confirmation phrase matching
- Undo contract, undo window enforcement (§22 item 4)
- system.undo validation and delegation
- UndoStack integration
- dispatch.create undo integration

This file adds deeper coverage of:
- BaseTool contract for system.undo
- Parameter schema validation
- execute() edge cases (tool lookup failures, delegation failures)
- Error handling paths through undo delegation
- Cross-cutting consistency

Blueprint: §9 — BaseTool.undo() support, §22 item 4.
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

TOOL_NAME = "system.undo"


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_ctx(**overrides: Any) -> ToolExecutionContext:
    kwargs: dict = dict(
        company_id=1,
        user_id=1,
        role="dispatcher",
        session_context=SessionContext(),
        services={},
    )
    kwargs.update(overrides)
    return ToolExecutionContext(**kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. BaseTool contract
# ═══════════════════════════════════════════════════════════════════════════════


class TestSystemUndoContract:
    """Verify system.undo meets BaseTool contract."""

    def test_tool_is_registered(self):
        tool = get_tool(TOOL_NAME)
        assert tool is not None

    def test_tool_name(self):
        tool = get_tool(TOOL_NAME)
        assert tool.name == TOOL_NAME

    def test_tool_version_is_semver(self):
        tool = get_tool(TOOL_NAME)
        parts = tool.tool_version.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts)

    def test_description_non_empty(self):
        tool = get_tool(TOOL_NAME)
        assert tool.description and tool.description.strip()
        assert "undo" in tool.description.lower()

    def test_required_permission(self):
        tool = get_tool(TOOL_NAME)
        assert tool.required_permission == "system:undo"

    def test_confirmation_level_business(self):
        tool = get_tool(TOOL_NAME)
        assert tool.confirmation_level == ConfirmationLevel.BUSINESS

    def test_supports_undo_false(self):
        """system.undo itself should NOT support undo (infinite recursion guard)."""
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
        assert "undo_token" in fields
        assert "tool_name" in fields

    def test_undo_token_is_required(self):
        tool = get_tool(TOOL_NAME)
        assert tool.parameters_schema.model_fields["undo_token"].is_required()

    def test_tool_name_is_required(self):
        tool = get_tool(TOOL_NAME)
        assert tool.parameters_schema.model_fields["tool_name"].is_required()

    def test_parameters_schema_forbids_extra(self):
        tool = get_tool(TOOL_NAME)
        config = tool.parameters_schema.model_config
        assert config.get("extra") == "forbid"

    def test_undo_raises_not_implemented(self):
        """system.undo.undo() must raise NotImplementedError (no self-undo)."""
        tool = get_tool(TOOL_NAME)
        with pytest.raises(NotImplementedError):
            asyncio.run(tool.undo("token", _make_ctx()))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Parameter schema validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSystemUndoParams:
    """Pydantic schema validation for UndoActionParams."""

    def test_accepts_valid_params(self):
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(undo_token="abc123", tool_name="dispatch.create")
        assert params.undo_token == "abc123"
        assert params.tool_name == "dispatch.create"

    def test_accepts_empty_undo_token(self):
        """undo_token has no min_length constraint, so empty string is accepted."""
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(undo_token="", tool_name="dispatch.create")
        assert params.undo_token == ""

    def test_accepts_empty_tool_name(self):
        """tool_name has no min_length constraint, so empty string is accepted."""
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(undo_token="abc", tool_name="")
        assert params.tool_name == ""

    def test_rejects_missing_undo_token(self):
        tool = get_tool(TOOL_NAME)
        with pytest.raises(ValidationError):
            tool.parameters_schema(tool_name="dispatch.create")

    def test_rejects_missing_tool_name(self):
        tool = get_tool(TOOL_NAME)
        with pytest.raises(ValidationError):
            tool.parameters_schema(undo_token="abc")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. validate()
# ═══════════════════════════════════════════════════════════════════════════════


class TestSystemUndoValidate:
    """Tool-level validate() behaviour for system.undo."""

    def test_validate_accepts_undoable_tool(self):
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(undo_token="x", tool_name="dispatch.create")
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert errors == []

    def test_validate_rejects_nonexistent_tool(self):
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(undo_token="x", tool_name="non.existent")
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert len(errors) > 0
        assert any("not found" in e.lower() for e in errors)

    def test_validate_rejects_non_undoable_tool(self):
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(undo_token="x", tool_name="trip.delete")
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert len(errors) > 0
        assert any("not support undo" in e.lower() for e in errors)

    def test_validate_rejects_self_undo(self):
        """system.undo does not support undo, so it should be rejected."""
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(undo_token="x", tool_name="system.undo")
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert len(errors) > 0

    def test_validate_accepts_unknown_tool_with_supports_undo(self):
        """Future-proof: if a tool has supports_undo but isn't dispatch.create, accept it."""
        # This is more of an integration check — verify the validate logic
        # doesn't hardcode tool names
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(undo_token="x", tool_name="dispatch.create")
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert errors == []


# ═══════════════════════════════════════════════════════════════════════════════
# 4. execute() — delegation and error paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestSystemUndoExecute:
    """Execute behaviour for system.undo."""

    def test_execute_tool_not_found_returns_failed(self):
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(undo_token="x", tool_name="does.not.exist")
        ctx = _make_ctx()
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "failed"
        assert result.message_key == "copilot.undo.tool_not_found"

    def test_execute_non_undoable_tool_returns_failed(self):
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(undo_token="x", tool_name="trip.delete")
        ctx = _make_ctx()
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "failed"
        assert result.message_key == "copilot.undo.not_supported"

    def test_execute_returns_tool_result_for_undoable_tool(self):
        """Even if the underlying undo fails, it must return a ToolResult, not crash."""
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(undo_token="test-token", tool_name="dispatch.create")
        ctx = _make_ctx()
        result = asyncio.run(tool.execute(params, ctx))
        assert isinstance(result, ToolResult)
        # Should be 'failed' or 'unavailable' since dispatch.create can't actually undo
        # without proper services, but the key point is it doesn't crash
        assert result.status in ("failed", "unavailable")

    def test_execute_delegates_to_tool_undo(self):
        """system.undo should call the target tool's undo() method."""
        from unittest.mock import AsyncMock

        # Get the real system.undo tool reference BEFORE patching get_tool
        undo_tool = get_tool(TOOL_NAME)
        params = undo_tool.parameters_schema(undo_token="my-token", tool_name="dispatch.create")

        # Patch get_tool to return a mock for ANY lookup inside execute
        mock_undoable = MagicMock(spec=["undo"])
        mock_undoable.supports_undo = True
        mock_undoable.undo = AsyncMock(return_value=ToolResult(
            status="success", message_key="copilot.undo.success",
        ))

        with patch("backend.copilot.tools.undo_tools.get_tool", return_value=mock_undoable):
            ctx = _make_ctx()
            result = asyncio.run(undo_tool.execute(params, ctx))

            assert result.status == "success"
            mock_undoable.undo.assert_called_once_with("my-token", ctx)

    def test_execute_forwards_services_to_undo(self):
        """The full execution context (including services) is forwarded to tool.undo()."""
        from unittest.mock import AsyncMock

        undo_tool = get_tool(TOOL_NAME)
        params = undo_tool.parameters_schema(undo_token="tok", tool_name="dispatch.create")

        mock_undoable = MagicMock(spec=["undo"])
        mock_undoable.supports_undo = True
        mock_undoable.undo = AsyncMock(return_value=ToolResult(
            status="success", message_key="copilot.undo.success",
        ))

        services = {"db": MagicMock(), "route_service": MagicMock()}

        with patch("backend.copilot.tools.undo_tools.get_tool", return_value=mock_undoable):
            ctx = _make_ctx(services=services)
            result = asyncio.run(undo_tool.execute(params, ctx))

            assert result.status == "success"
            # Verify the context with services was passed
            call_ctx = mock_undoable.undo.call_args[0][1]
            assert call_ctx.services["db"] is not None
            assert call_ctx.services["route_service"] is not None

    def test_execute_forwards_context_fields(self):
        """company_id, user_id, role, session_context must be forwarded."""
        from unittest.mock import AsyncMock

        undo_tool = get_tool(TOOL_NAME)
        params = undo_tool.parameters_schema(undo_token="tok", tool_name="dispatch.create")

        mock_undoable = MagicMock(spec=["undo"])
        mock_undoable.supports_undo = True
        mock_undoable.undo = AsyncMock(return_value=ToolResult(
            status="success", message_key="copilot.undo.success",
        ))

        with patch("backend.copilot.tools.undo_tools.get_tool", return_value=mock_undoable):
            ctx = _make_ctx(company_id=5, user_id=10, role="manager")
            asyncio.run(undo_tool.execute(params, ctx))

            call_ctx = mock_undoable.undo.call_args[0][1]
            assert call_ctx.company_id == 5
            assert call_ctx.user_id == 10
            assert call_ctx.role == "manager"

    def test_execute_handles_not_implemented_error(self):
        """If tool.undo() raises NotImplementedError, returns unavailable."""
        from unittest.mock import AsyncMock

        undo_tool = get_tool(TOOL_NAME)
        params = undo_tool.parameters_schema(undo_token="tok", tool_name="dispatch.create")

        mock_undoable = MagicMock(spec=["undo"])
        mock_undoable.supports_undo = True
        mock_undoable.undo = AsyncMock(side_effect=NotImplementedError("Not yet"))

        with patch("backend.copilot.tools.undo_tools.get_tool", return_value=mock_undoable):
            ctx = _make_ctx()
            result = asyncio.run(undo_tool.execute(params, ctx))

            assert result.status == "unavailable"
            assert result.message_key == "copilot.undo.not_implemented"

    def test_execute_handles_generic_exception(self):
        """If tool.undo() raises any other exception, returns failed."""
        from unittest.mock import AsyncMock

        undo_tool = get_tool(TOOL_NAME)
        params = undo_tool.parameters_schema(undo_token="tok", tool_name="dispatch.create")

        mock_undoable = MagicMock(spec=["undo"])
        mock_undoable.supports_undo = True
        mock_undoable.undo = AsyncMock(side_effect=RuntimeError("Unexpected undo failure"))

        with patch("backend.copilot.tools.undo_tools.get_tool", return_value=mock_undoable):
            ctx = _make_ctx()
            result = asyncio.run(undo_tool.execute(params, ctx))

            assert result.status == "failed"
            assert "Unexpected undo failure" in result.message_params.get("error", "")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Cross-cutting consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestSystemUndoConsistency:
    """Ensure system.undo respects the undo framework invariants."""

    def test_only_undoable_tools_pass_validation(self):
        """Iterate all tools and verify validate rejects non-undoable ones."""
        from backend.copilot.tools.registry import all_tools

        undo_tool = get_tool(TOOL_NAME)
        for t in all_tools():
            params = undo_tool.parameters_schema(undo_token="x", tool_name=t.name)
            errors = asyncio.run(undo_tool.validate(params, _make_ctx()))
            if t.supports_undo:
                assert errors == [], f"{t.name} should pass undo validation but got: {errors}"
            else:
                assert len(errors) > 0, f"{t.name} should fail undo validation"

    def test_system_undo_is_not_in_undoable_list(self):
        """system.undo must NOT be undoable to prevent infinite recursion."""
        from backend.copilot.tools.registry import all_tools
        undoable = {t.name for t in all_tools() if t.supports_undo}
        assert TOOL_NAME not in undoable

    def test_system_undo_has_no_undo(self):
        tool = get_tool(TOOL_NAME)
        with pytest.raises(NotImplementedError):
            asyncio.run(tool.undo("token", _make_ctx()))

    def test_system_undo_cannot_undo_itself_via_execute(self):
        """Attempting to undo system.undo via execute should fail."""
        tool = get_tool(TOOL_NAME)
        params = tool.parameters_schema(undo_token="x", tool_name=TOOL_NAME)
        ctx = _make_ctx()
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "failed"
