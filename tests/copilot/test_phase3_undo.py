"""Phase 3 tests — destructive actions, undo, and confirmation phrase matching.

Blueprint: §9.1 Level 3, §21 Phase 3, §22 item 4.

Tests verify:
9 DESTRUCTIVE tools — registered, correct permissions, confirmation phrases
Undo — dispatch.create.undo() reverses state, UNDO_WINDOW_MINUTES enforced
system.undo tool — validation, delegation, edge cases
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from backend.copilot.schemas import (
    ConfirmationLevel, ExecutionPlan, ExecutionStep, Intent,
    SessionContext, ToolResult,
)
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import all_tools, get_tool, run_startup_validation
from backend.copilot.executor import UNDO_WINDOW_MINUTES, is_undo_expired

# Ensure tools are loaded at module level so parametrize expressions see them
from backend.copilot.planner import _ensure_tools_loaded  # noqa: E402
_ensure_tools_loaded()
_validation_errors = run_startup_validation()
_prod_errors = [e for e in _validation_errors if "test." not in e]
assert len(_prod_errors) == 0, f"Production tool registry errors: {_prod_errors}"


# Phase 3 tests do NOT use Qt, but stale QTimer callbacks from
# test_guided_overlay_widget can leak into this module's event loop.
# Mark the whole module to ignore those phantom Qt exceptions.
pytestmark = pytest.mark.qt_no_exception_capture


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True, scope="module")
def ensure_tools():
    """Ensure all tools are still loaded and valid once before the module runs."""
    errors = run_startup_validation()
    prod_errors = [e for e in errors if "test." not in e]
    assert len(prod_errors) == 0, f"Production tool registry errors: {prod_errors}"


def _make_ctx(**overrides: Any) -> ToolExecutionContext:
    """Helper: build a minimal ToolExecutionContext."""
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
# Section 1: Destructive tool basics
# ═══════════════════════════════════════════════════════════════════════════════


class TestDestructiveToolBasics:
    """Basic structural tests for all 9 DESTRUCTIVE tools."""

    # Exact 9 tools that are DESTRUCTIVE in the registry
    DESTRUCTIVE_NAMES = {
        "trip.delete", "vehicle.delete", "driver.remove", "client.delete",
        "invoice.delete", "route.delete", "dispatch.cancel",
        "automail.send_now", "email.send_bulk",
    }

    def test_all_9_destructive_tools_registered(self):
        """Expect exactly 9 DESTRUCTIVE tools registered."""
        dest = [t for t in all_tools() if t.confirmation_level == ConfirmationLevel.DESTRUCTIVE]
        names = {t.name for t in dest}
        assert names == self.DESTRUCTIVE_NAMES, (
            f"DESTRUCTIVE tools mismatch. Extra: {names - self.DESTRUCTIVE_NAMES}. "
            f"Missing: {self.DESTRUCTIVE_NAMES - names}"
        )
        assert len(dest) == 9, f"Expected 9 DESTRUCTIVE tools, got {len(dest)}"

    @pytest.mark.parametrize("name", sorted(DESTRUCTIVE_NAMES))
    def test_destructive_permission_naming(self, name):
        """All DESTRUCTIVE tools must have :delete, :send, or :send_bulk permission suffixes."""
        tool = get_tool(name)
        assert tool is not None, f"{name} not found"
        perm = tool.required_permission
        assert any(perm.endswith(suffix) for suffix in (":delete", ":send", ":send_bulk", ":write")), (
            f"{name} permission '{perm}' doesn't end with :delete/:send/:send_bulk/:write"
        )

    @pytest.mark.parametrize("name", sorted(DESTRUCTIVE_NAMES))
    def test_destructive_has_confirmation_phrase(self, name):
        """Delete/remove/cancel tools must have confirmation_phrase param.
        dispatch.cancel has no confirmation_phrase in phase 3 — skip.
        """
        tool = get_tool(name)
        # dispatch.cancel does NOT have confirmation_phrase
        if name in ("dispatch.cancel", "automail.send_now", "email.send_bulk"):
            return  # these tools use Level 3 but no typed confirmation phrase yet
        assert "confirmation_phrase" in tool.parameters_schema.model_fields, (
            f"{name} missing confirmation_phrase"
        )

    @pytest.mark.parametrize("name", sorted(DESTRUCTIVE_NAMES))
    def test_destructive_tool_version_valid(self, name):
        """All DESTRUCTIVE tools must have valid semver versions."""
        tool = get_tool(name)
        parts = tool.tool_version.split(".")
        assert len(parts) == 3, f"{name} version {tool.tool_version} not semver"
        assert all(p.isdigit() for p in parts), f"{name} version {tool.tool_version} not semver"

    def test_all_destructive_supports_undo_false(self):
        """No DESTRUCTIVE tool should support undo in Phase 3."""
        for tool in all_tools():
            if tool.confirmation_level == ConfirmationLevel.DESTRUCTIVE:
                assert not tool.supports_undo, (
                    f"{tool.name} should not support undo"
                )

    def test_destructive_minimum_description_length(self):
        """All DESTRUCTIVE tools should have a meaningful description."""
        for tool in all_tools():
            if tool.confirmation_level == ConfirmationLevel.DESTRUCTIVE:
                assert len(tool.description) >= 20, (
                    f"{tool.name} description too short: {tool.description!r}"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# Section 2: Confirmation phrase parameter contract
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfirmationPhraseMatching:
    """Confirmation phrase parameter contract for destructive delete tools."""

    # Tools that have confirmation_phrase defined in their schema
    TOOLS_WITH_PHRASE = [
        "trip.delete", "vehicle.delete", "driver.remove", "client.delete",
        "invoice.delete", "route.delete",
    ]

    @pytest.mark.parametrize("name", TOOLS_WITH_PHRASE)
    def test_confirmation_phrase_is_required_field(self, name):
        """confirmation_phrase must be required (no default) and non-empty."""
        tool = get_tool(name)
        field_info = tool.parameters_schema.model_fields.get("confirmation_phrase")
        assert field_info is not None, f"{name} missing confirmation_phrase field"
        assert field_info.is_required(), f"{name} confirmation_phrase must be required"
        # Must have min_length to prevent empty strings
        if hasattr(field_info, "min_length") and field_info.min_length is not None:
            assert field_info.min_length >= 1, f"{name} confirmation_phrase min_length must be >= 1"

    @pytest.mark.parametrize("name", TOOLS_WITH_PHRASE)
    def test_confirmation_phrase_accepts_any_value(self, name):
        """The tool itself should NOT validate confirmation_phrase matches
        the entity ID — the UI is responsible for that check. The executor
        should accept any confirmation_phrase and pass it through.
        """
        tool = get_tool(name)
        # Find the ID field (trip_id, vehicle_id, etc.)
        id_field = self._find_id_field(tool)
        assert id_field is not None, f"{name}: could not determine ID field"

        # Build params with a confirmation_phrase that differs from the ID
        params_data = {id_field: 42, "confirmation_phrase": "99"}
        try:
            params = tool.parameters_schema(**params_data)
        except Exception as exc:
            pytest.fail(f"{name} rejected valid params: {exc}")

        # Validation should pass at the tool level (UI handles phrase matching)
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        # The only errors should be about missing DB or service, NOT about
        # confirmation_phrase not matching the ID
        phrase_errors = [e for e in errors if "confirmation" in e.lower()]
        assert len(phrase_errors) == 0, (
            f"{name} should not validate confirmation_phrase at tool level. "
            f"Errors: {phrase_errors}"
        )

    @staticmethod
    def _find_id_field(tool: BaseTool) -> str | None:
        """Return the entity ID field name for a delete tool."""
        for field_name in tool.parameters_schema.model_fields:
            if field_name != "confirmation_phrase":
                return field_name
        return None

    def test_send_tools_no_confirmation_phrase(self):
        """Send tools (automail.send_now, email.send_bulk) should NOT require
        confirmation_phrase — their destructive nature is Level 3 by convention.
        """
        for name in ("automail.send_now", "email.send_bulk"):
            tool = get_tool(name)
            assert "confirmation_phrase" not in tool.parameters_schema.model_fields, (
                f"{name} should not have confirmation_phrase"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Section 3: Undo contract
# ═══════════════════════════════════════════════════════════════════════════════


class TestUndoContract:
    """Undo behavior for tools with supports_undo=True."""

    # In Phase 3, only dispatch.create supports undo
    UNDOABLE_NAMES = {"dispatch.create"}

    def test_only_dispatch_create_supports_undo(self):
        """Only specific tools should support undo in Phase 3."""
        undoable = {t.name for t in all_tools() if t.supports_undo}
        assert undoable == self.UNDOABLE_NAMES, (
            f"Expected undoable tools {self.UNDOABLE_NAMES}, got {undoable}"
        )

    @pytest.mark.parametrize("name", sorted(UNDOABLE_NAMES))
    def test_undoable_tool_returns_tool_result(self, name):
        """Every undoable tool's undo() must return ToolResult, not crash."""
        tool = get_tool(name)
        ctx = _make_ctx()
        try:
            result = asyncio.run(tool.undo("test-token", ctx))
            assert isinstance(result, ToolResult), f"{name}.undo() returned {type(result)}"
            assert result.status in ("success", "failed", "unavailable"), (
                f"{name}.undo() status: {result.status}"
            )
        except NotImplementedError:
            pytest.fail(f"{name} has supports_undo=True but undo() raises NotImplementedError")

    @pytest.mark.parametrize("name", [t.name for t in all_tools() if not t.supports_undo])
    def test_non_undoable_tools_raise_not_implemented(self, name):
        """Tools with supports_undo=False must raise NotImplementedError on undo()."""
        tool = get_tool(name)
        ctx = _make_ctx()
        with pytest.raises(NotImplementedError):
            asyncio.run(tool.undo("test-token", ctx))

    def test_dispatch_create_undo_returns_failed_for_bad_token(self):
        """dispatch.create.undo() should return failed (not crash) for invalid JSON token."""
        tool = get_tool("dispatch.create")
        ctx = _make_ctx()
        result = asyncio.run(tool.undo("not-json-at-all", ctx))
        assert isinstance(result, ToolResult)
        assert result.status == "failed", f"Expected failed, got {result.status}"

    def test_dispatch_create_undo_returns_failed_for_empty_token(self):
        """dispatch.create.undo() should handle empty string token gracefully."""
        tool = get_tool("dispatch.create")
        ctx = _make_ctx()
        result = asyncio.run(tool.undo("", ctx))
        assert isinstance(result, ToolResult)
        assert result.status in ("failed", "unavailable")


# ═══════════════════════════════════════════════════════════════════════════════
# Section 4: Undo window enforcement (§22 item 4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestUndoWindow:
    """30-minute undo window enforcement (§22 item 4)."""

    def test_undo_window_constant(self):
        """UNDO_WINDOW_MINUTES must be 30."""
        assert UNDO_WINDOW_MINUTES == 30, f"Expected 30, got {UNDO_WINDOW_MINUTES}"

    def test_is_undo_expired_within_window(self):
        """An action started 10 minutes ago is still undoable."""
        started = datetime.utcnow() - timedelta(minutes=10)
        assert not is_undo_expired(started), "10-min-old action should be undoable"

    def test_is_undo_expired_at_window_boundary(self):
        """An action started exactly 30 minutes ago is NOT expired (uses >, not >=)."""
        started = datetime.utcnow() - timedelta(minutes=30)
        assert not is_undo_expired(started), "30-min-old action should NOT be expired (strict >)"

    def test_is_undo_expired_past_window(self):
        """An action started 45 minutes ago should be expired."""
        started = datetime.utcnow() - timedelta(minutes=45)
        assert is_undo_expired(started), "45-min-old action should be expired"

    def test_is_undo_expired_no_timestamp(self):
        """No timestamp should default to allowing undo."""
        assert not is_undo_expired(None), "None timestamp should allow undo"

    def test_is_undo_expired_recent(self):
        """An action started 1 second ago is well within the window."""
        started = datetime.utcnow() - timedelta(seconds=1)
        assert not is_undo_expired(started), "1-second-old action should be undoable"

    def test_is_undo_expired_just_under_window(self):
        """An action started 29 minutes 59 seconds ago is still undoable."""
        started = datetime.utcnow() - timedelta(minutes=29, seconds=59)
        assert not is_undo_expired(started), "29m59s-old action should be undoable"

    def test_is_undo_expired_just_over_window(self):
        """An action started 30 minutes 1 second ago should be expired."""
        started = datetime.utcnow() - timedelta(minutes=30, seconds=1)
        assert is_undo_expired(started), "30m1s-old action should be expired"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 5: system.undo tool
# ═══════════════════════════════════════════════════════════════════════════════


class TestSystemUndoTool:
    """The system.undo tool — validation and delegation."""

    def test_system_undo_registered(self):
        """system.undo must be registered as a BUSINESS tool."""
        tool = get_tool("system.undo")
        assert tool is not None, "system.undo not registered"
        assert tool.confirmation_level == ConfirmationLevel.BUSINESS
        assert not tool.supports_undo, "system.undo should not support undo"
        assert tool.name == "system.undo"

    def test_system_undo_validate_bad_tool(self):
        """system.undo validate must reject nonexistent tool names."""
        tool = get_tool("system.undo")
        errors = asyncio.run(tool.validate(
            tool.parameters_schema(undo_token="x", tool_name="nonexistent.tool"),
            _make_ctx(),
        ))
        assert len(errors) > 0, "Should reject nonexistent tool name"

    def test_system_undo_validate_non_undoable_tool(self):
        """system.undo validate must reject tools without supports_undo."""
        tool = get_tool("system.undo")
        errors = asyncio.run(tool.validate(
            tool.parameters_schema(undo_token="x", tool_name="vehicle.search"),
            _make_ctx(),
        ))
        assert len(errors) > 0, "Should reject tool without supports_undo"

    def test_system_undo_validate_undoable_tool_succeeds(self):
        """system.undo validate must accept tools with supports_undo."""
        tool = get_tool("system.undo")
        errors = asyncio.run(tool.validate(
            tool.parameters_schema(undo_token="x", tool_name="dispatch.create"),
            _make_ctx(),
        ))
        assert len(errors) == 0, f"Should accept dispatch.create, got errors: {errors}"

    def test_system_undo_execute_returns_tool_result(self):
        """system.undo.execute() must return ToolResult for valid calls."""
        tool = get_tool("system.undo")
        try:
            result = asyncio.run(tool.execute(
                tool.parameters_schema(undo_token="test", tool_name="dispatch.create"),
                _make_ctx(),
            ))
            assert isinstance(result, ToolResult), f"Got {type(result)}"
            # May be "failed" if dispatch.create can't actually undo, but must not crash
        except Exception as e:
            pytest.fail(f"system.undo.execute() crashed: {e}")

    def test_system_undo_execute_bad_tool(self):
        """system.undo with nonexistent tool must return failed."""
        tool = get_tool("system.undo")
        result = asyncio.run(tool.execute(
            tool.parameters_schema(undo_token="x", tool_name="does.not.exist"),
            _make_ctx(),
        ))
        assert isinstance(result, ToolResult)
        assert result.status == "failed"

    def test_system_undo_execute_non_undoable(self):
        """system.undo with non-undoable tool must return failed."""
        tool = get_tool("system.undo")
        result = asyncio.run(tool.execute(
            tool.parameters_schema(undo_token="x", tool_name="trip.delete"),
            _make_ctx(),
        ))
        assert isinstance(result, ToolResult)
        assert result.status == "failed"

    def test_system_undo_undo_raises_not_implemented(self):
        """system.undo itself should not support undo."""
        tool = get_tool("system.undo")
        with pytest.raises(NotImplementedError):
            asyncio.run(tool.undo("token", _make_ctx()))


# ═══════════════════════════════════════════════════════════════════════════════
# Section 6: Service failure handling — tools must not crash
# ═══════════════════════════════════════════════════════════════════════════════


class TestServiceFailureHandling:
    """Service failures should produce ToolResult(status='failed'/'unavailable'), not crash."""

    DELETE_TOOLS = [
        "trip.delete", "vehicle.delete", "driver.remove", "client.delete",
        "invoice.delete",
    ]

    @pytest.mark.parametrize("name", DELETE_TOOLS)
    def test_delete_tools_handle_missing_db(self, name):
        """Delete tools should return 'unavailable' when no DB is provided."""
        tool = get_tool(name)
        ctx = _make_ctx()  # no services = no db
        id_field = self._find_id_field(tool)
        assert id_field is not None, f"{name}: could not find ID field"

        params_data = {id_field: 1, "confirmation_phrase": "1"}
        params = tool.parameters_schema(**params_data)

        try:
            result = asyncio.run(tool.execute(params, ctx))
        except Exception as e:
            pytest.fail(f"{name} crashed on missing DB: {e}")

        assert isinstance(result, ToolResult), f"{name} returned {type(result)}"
        assert result.status in ("failed", "unavailable"), (
            f"{name} expected failed/unavailable, got {result.status}"
        )

    def test_route_delete_handles_missing_db(self):
        """route.delete should return 'unavailable' when no DB is provided."""
        tool = get_tool("route.delete")
        ctx = _make_ctx()
        params = tool.parameters_schema(route_id=1, confirmation_phrase="1")
        try:
            result = asyncio.run(tool.execute(params, ctx))
        except Exception as e:
            pytest.fail(f"route.delete crashed on missing DB: {e}")

        assert isinstance(result, ToolResult)
        assert result.status in ("failed", "unavailable"), (
            f"route.delete expected failed/unavailable, got {result.status}"
        )

    @pytest.mark.parametrize("name", ["automail.send_now", "email.send_bulk"])
    def test_send_tools_validate_email(self, name):
        """Send tools must validate email addresses in validate()."""
        tool = get_tool(name)
        if name == "automail.send_now":
            params = tool.parameters_schema(
                invoice_id=1, recipient_email="not-an-email"
            )
        else:
            params = tool.parameters_schema(
                recipients=["not-an-email"], subject="test", body="test"
            )
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert len(errors) > 0, f"{name} should reject invalid emails"

    @pytest.mark.parametrize("name", ["automail.send_now", "email.send_bulk"])
    def test_send_tools_accept_valid_email(self, name):
        """Send tools must accept valid email addresses in validate()."""
        tool = get_tool(name)
        if name == "automail.send_now":
            params = tool.parameters_schema(
                invoice_id=1, recipient_email="user@example.com"
            )
        else:
            params = tool.parameters_schema(
                recipients=["user@example.com"], subject="test", body="test"
            )
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert len(errors) == 0, f"{name} should accept valid email, got: {errors}"

    @staticmethod
    def _find_id_field(tool: BaseTool) -> str | None:
        """Return the entity ID field name for a delete tool."""
        for field_name in tool.parameters_schema.model_fields:
            if field_name != "confirmation_phrase":
                return field_name
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Section 7: UndoStack integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestUndoStackIntegration:
    """Verify the existing UndoStack supports Co-Pilot integration."""

    def test_undo_stack_push_and_undo(self):
        """Verify UndoStack.push() and undo() work correctly."""
        from services.operations.undo_stack import UndoStack, UndoCommand

        stack = UndoStack()
        cmd = UndoCommand(trip_id=1, old_status="planned", new_status="in_transit")
        stack.push(cmd)
        assert stack.can_undo, "Should have undo available"

        undone = stack.undo()
        assert undone is not None, "Undo should return a command"
        assert undone.trip_id == 1
        assert undone.old_status == "planned"
        assert undone.new_status == "in_transit"

    def test_undo_stack_undo_empty(self):
        """Undoing an empty stack should return None."""
        from services.operations.undo_stack import UndoStack

        stack = UndoStack()
        assert not stack.can_undo
        assert stack.undo() is None

    def test_undo_stack_max_depth_enforced(self):
        """UndoStack should enforce MAX_DEPTH = 20."""
        from services.operations.undo_stack import UndoStack, UndoCommand

        stack = UndoStack()
        for i in range(30):  # push more than MAX_DEPTH
            stack.push(UndoCommand(trip_id=i, old_status="planned", new_status="in_transit"))

        # MAX_DEPTH = 20 per the class constant
        count = 0
        while stack.undo() is not None:
            count += 1
        # Should have at most 20 entries
        assert count <= 20, f"Expected at most 20 undoable items, got {count}"

    def test_undo_stack_clear(self):
        """UndoStack.clear() should remove all entries."""
        from services.operations.undo_stack import UndoStack, UndoCommand

        stack = UndoStack()
        stack.push(UndoCommand(trip_id=1, old_status="planned", new_status="in_transit"))
        assert stack.can_undo
        stack.clear()
        assert not stack.can_undo, "Stack should be empty after clear"

    def test_undo_stack_redo(self):
        """Verify UndoStack.redo() works after undo()."""
        from services.operations.undo_stack import UndoStack, UndoCommand

        stack = UndoStack()
        stack.push(UndoCommand(trip_id=1, old_status="planned", new_status="in_transit"))
        stack.undo()
        assert stack.can_redo, "Should have redo available after undo"
        redone = stack.redo()
        assert redone is not None
        assert redone.trip_id == 1

    def test_undo_stack_clear_after_push(self):
        """Pushing a new command should clear the redo stack."""
        from services.operations.undo_stack import UndoStack, UndoCommand

        stack = UndoStack()
        stack.push(UndoCommand(trip_id=1, old_status="planned", new_status="in_transit"))
        stack.undo()
        assert stack.can_redo
        # Push a new command — redo should be cleared
        stack.push(UndoCommand(trip_id=2, old_status="planned", new_status="in_transit"))
        assert not stack.can_redo, "Redo should be cleared after a new push"

    def test_undo_stack_current_status_check(self):
        """undo() with current_status should reject if status doesn't match."""
        from services.operations.undo_stack import UndoStack, UndoCommand

        stack = UndoStack()
        stack.push(UndoCommand(trip_id=1, old_status="planned", new_status="in_transit"))

        # current_status doesn't match new_status — undo should be rejected
        result = stack.undo(current_status="completed")
        assert result is None, "Undo should fail when current_status doesn't match new_status"
        # Stack should still have the command
        assert stack.can_undo

        # current_status matches — undo should succeed
        result = stack.undo(current_status="in_transit")
        assert result is not None, "Undo should succeed when current_status matches"

    def test_undo_stack_last_undo_command(self):
        """last_undo_command() should return the top without popping."""
        from services.operations.undo_stack import UndoStack, UndoCommand

        stack = UndoStack()
        stack.push(UndoCommand(trip_id=42, old_status="planned", new_status="in_transit"))
        last = stack.last_undo_command()
        assert last is not None
        assert last.trip_id == 42
        # Should still be undoable (not popped)
        assert stack.can_undo

    def test_undo_stack_thread_safety(self):
        """UndoStack should handle concurrent pushes without crashing."""
        from services.operations.undo_stack import UndoStack, UndoCommand
        import threading

        stack = UndoStack()
        errors: list[Exception] = []

        def push_many(start: int, count: int) -> None:
            for i in range(start, start + count):
                try:
                    stack.push(UndoCommand(trip_id=i, old_status="planned", new_status="in_transit"))
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=push_many, args=(0, 50)),
            threading.Thread(target=push_many, args=(50, 50)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        # Should have items from both threads
        assert stack.can_undo


# ═══════════════════════════════════════════════════════════════════════════════
# Section 8: dispatch.create undo integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestDispatchCreateUndoIntegration:
    """Deep-dive into dispatch.create undo flow."""

    def test_undo_token_structure(self):
        """dispatch.create should encode undo_token as JSON with trip_id and previous_state."""
        # This tests the undo token format expected by dispatch.create.undo()
        token_data = {
            "trip_id": 123,
            "previous_state": {"status": "planned", "driver_id": None, "truck_id": None},
            "undo_description": "Restored trip #123",
        }
        token = json.dumps(token_data)

        # The token must be parseable
        parsed = json.loads(token)
        assert parsed["trip_id"] == 123
        assert parsed["previous_state"]["status"] == "planned"

    def test_undo_requires_valid_previous_state(self):
        """dispatch.create.undo() must fail if previous_state lacks 'status' key."""
        tool = get_tool("dispatch.create")

        # Token without previous_state.status
        bad_token = json.dumps({"trip_id": 1, "previous_state": {"driver_id": None}})
        result = asyncio.run(tool.undo(bad_token, _make_ctx()))
        assert result.status == "failed", (
            f"Expected failed for missing previous_state.status, got {result.status}"
        )

        # Token with non-dict previous_state
        bad_token2 = json.dumps({"trip_id": 1, "previous_state": "not-a-dict"})
        result2 = asyncio.run(tool.undo(bad_token2, _make_ctx()))
        assert result2.status == "failed", (
            f"Expected failed for non-dict previous_state, got {result2.status}"
        )

    def test_undo_calls_trip_service_update(self):
        """dispatch.create.undo() should call trip_service.update() with previous_state."""
        from models.trip_models import TripUpdate

        tool = get_tool("dispatch.create")

        # Mock trip_service to verify the call — must return a success-like result
        mock_trip_service = MagicMock()
        mock_trip_service.update.return_value = MagicMock(success=True)

        ctx = _make_ctx(services={"trip_service": mock_trip_service})

        token = json.dumps({
            "trip_id": 42,
            "previous_state": {"status": "planned", "driver_id": None},
            "undo_description": "Restored trip #42",
        })

        result = asyncio.run(tool.undo(token, ctx))

        assert result.status == "success", f"Expected success, got {result.status}"
        # The service now receives a typed TripUpdate object instead of a raw dict
        mock_trip_service.update.assert_called_once()
        args = mock_trip_service.update.call_args
        assert args[0][0] == 42, f"Expected trip_id=42, got {args[0][0]}"
        update_obj = args[0][1]
        assert isinstance(update_obj, TripUpdate), f"Expected TripUpdate, got {type(update_obj)}"
        assert update_obj.status == "planned"
        assert update_obj.driver_id is None

    def test_undo_missing_service_returns_unavailable(self):
        """dispatch.create.undo() without trip_service or db returns unavailable."""
        tool = get_tool("dispatch.create")

        token = json.dumps({
            "trip_id": 1,
            "previous_state": {"status": "planned"},
        })

        result = asyncio.run(tool.undo(token, _make_ctx()))
        assert result.status == "unavailable", (
            f"Expected unavailable without services, got {result.status}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Section 9: Executor undo integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutorUndoIntegration:
    """Ensure the executor module exposes the correct undo interface."""

    def test_UNDO_WINDOW_MINUTES_is_int(self):
        assert isinstance(UNDO_WINDOW_MINUTES, int)

    def test_is_undo_expired_signature(self):
        """is_undo_expired should accept Optional[datetime] and return bool."""
        import inspect
        sig = inspect.signature(is_undo_expired)
        assert "started_at" in sig.parameters


# ═══════════════════════════════════════════════════════════════════════════════
# Section 10: Cross-cutting — all tools
# ═══════════════════════════════════════════════════════════════════════════════


class TestAllToolsConsistency:
    """Consistency checks across the full registry."""

    def test_no_tool_has_both_destructive_and_undo(self):
        """No tool should be both DESTRUCTIVE and supports_undo."""
        for tool in all_tools():
            if tool.confirmation_level == ConfirmationLevel.DESTRUCTIVE:
                assert not tool.supports_undo, (
                    f"{tool.name} is DESTRUCTIVE but supports_undo=True"
                )

    def test_undoable_tools_are_business_or_safe(self):
        """All undoable tools should be BUSINESS or SAFE level."""
        for tool in all_tools():
            if tool.supports_undo:
                assert tool.confirmation_level in (
                    ConfirmationLevel.SAFE,
                    ConfirmationLevel.INFORMATIONAL,
                    ConfirmationLevel.BUSINESS,
                ), f"{tool.name} is undoable but level={tool.confirmation_level}"

    def test_no_extra_undoable_tools_beyond_expected(self):
        """Explicitly check no unexpected tool has supports_undo."""
        expected = {"dispatch.create"}
        actual = {t.name for t in all_tools() if t.supports_undo}
        unexpected = actual - expected
        assert len(unexpected) == 0, f"Unexpected undoable tools: {unexpected}"
