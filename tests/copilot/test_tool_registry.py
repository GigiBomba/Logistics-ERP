"""Tool registry tests — prove validation fails loudly for malformed tools.

Blueprint: §9 — Registry enforcement.

IMPORTANT: This module registers fixture tools (with names starting with
``test.``) into the global ``_registry``.  The module-scoped autouse fixture
``_cleanup_test_tools`` unregisters them after this module finishes, so they
don't leak into subsequent test files that run ``validate_registry()`` or
``run_startup_validation()`` (e.g. ``test_copilot_load.py``).
"""

import pytest
from pydantic import BaseModel, ConfigDict

from backend.copilot.schemas import ConfirmationLevel, SessionContext
from backend.copilot.tools.base import BaseTool, ToolResult, ToolExecutionContext
from backend.copilot.tools.registry import (
    _registry,
    register_tool,
    all_tools,
    get_tool,
    available_tools,
    validate_registry,
)


@pytest.fixture(autouse=True, scope="module")
def _cleanup_test_tools():
    """Module-scoped autouse: yield runs all tests, then unregisters fixture tools."""
    yield
    test_tool_names = [name for name in _registry.keys() if name.startswith("test.")]
    for name in test_tool_names:
        del _registry[name]


# ── Fixture tools for testing ──────────────────────────────────────────────

class _DummyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = ""


@register_tool
class _ValidTool(BaseTool):
    name = "test.valid"
    tool_version = "1.0.0"
    description = "A valid tool for testing"
    required_permission = "test:read"
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = _DummyParams

    async def validate(self, params, ctx): return []
    async def execute(self, params, ctx): return ToolResult(status="success", message_key="test.ok")


@register_tool
class _NoPermissionTool(BaseTool):
    name = "test.no_permission"
    tool_version = "1.0.0"
    description = "Missing required_permission"
    required_permission = ""        # INVALID: empty
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = _DummyParams

    async def validate(self, params, ctx): return []
    async def execute(self, params, ctx): return ToolResult(status="success", message_key="test.ok")


@register_tool
class _NoVersionTool(BaseTool):
    name = "test.no_version"
    tool_version = ""               # INVALID: empty
    description = "Missing tool_version"
    required_permission = "test:read"
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = _DummyParams

    async def validate(self, params, ctx): return []
    async def execute(self, params, ctx): return ToolResult(status="success", message_key="test.ok")


@register_tool
class _BadSchemaTool(BaseTool):
    name = "test.bad_schema"
    tool_version = "1.0.0"
    description = "Non-Pydantic parameters_schema"
    required_permission = "test:read"
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = dict          # INVALID: not a BaseModel subclass

    async def validate(self, params, ctx): return []
    async def execute(self, params, ctx): return ToolResult(status="success", message_key="test.ok")


@register_tool
class _DeprecatedTool(BaseTool):
    name = "test.deprecated"
    tool_version = "1.0.0"
    description = "A deprecated tool"
    required_permission = "test:read"
    confirmation_level = ConfirmationLevel.SAFE
    deprecated = True
    parameters_schema = _DummyParams

    async def validate(self, params, ctx): return []
    async def execute(self, params, ctx): return ToolResult(status="success", message_key="test.ok")


# ── Tests ──────────────────────────────────────────────────────────────────

class TestToolRegistration:
    def test_valid_tool_registers(self):
        from backend.copilot.tools.registry import _registry
        assert "test.valid" in _registry

    def test_get_tool_returns_tool(self):
        tool = get_tool("test.valid")
        assert tool is not None
        assert tool.name == "test.valid"
        assert tool.tool_version == "1.0.0"

    def test_get_tool_returns_none_for_unknown(self):
        assert get_tool("nonexistent") is None

    def test_available_tools_excludes_deprecated(self):
        avail = available_tools()
        names = [t.name for t in avail]
        assert "test.deprecated" not in names
        assert "test.valid" in names

    def test_available_tools_includes_deprecated_when_requested(self):
        avail = available_tools(deprecated=True)
        names = [t.name for t in avail]
        assert "test.deprecated" in names

    def test_all_tools_includes_deprecated(self):
        all_t = all_tools()
        names = [t.name for t in all_t]
        assert "test.deprecated" in names


class TestRegistryValidation:
    def test_validation_catches_missing_permission(self):
        errors = validate_registry()
        error_msgs = "\n".join(errors)
        assert any("test.no_permission" in e for e in errors), f"Expected no_permission error, got: {error_msgs}"

    def test_validation_catches_empty_version(self):
        errors = validate_registry()
        assert any("test.no_version" in e for e in errors)

    def test_validation_catches_non_pydantic_schema(self):
        errors = validate_registry()
        assert any("test.bad_schema" in e for e in errors)

    def test_validation_fails_on_malformed_tools(self):
        """Blueprint requirement: validation fails loudly if any tool is malformed."""
        errors = validate_registry()
        # There should be at least 3 errors (no_permission, no_version, bad_schema)
        assert len(errors) >= 3, f"Expected >= 3 errors, got {len(errors)}: {errors}"


class TestToolExecutionContext:
    def test_execution_context_no_db(self):
        """ToolExecutionContext must NOT contain a raw DB session (§1, §9)."""
        ctx = ToolExecutionContext(
            company_id=1, user_id=1, role="dispatcher",
            session_context=SessionContext(),
            services={},
        )
        assert not hasattr(ctx, "db")
        assert not hasattr(ctx, "db_session")

    def test_execution_context_services_only(self):
        """Services are injected pre-instantiated — tools never touch DB directly."""
        ctx = ToolExecutionContext(
            company_id=1, user_id=1, role="dispatcher",
            session_context=SessionContext(),
            services={"fleet": "mock_fleet_service", "dispatch": "mock_dispatch_service"},
        )
        assert "fleet" in ctx.services
        assert "dispatch" in ctx.services
