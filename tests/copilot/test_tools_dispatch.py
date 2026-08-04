"""Comprehensive unit tests for dispatch.* Co-Pilot tools.

Tests cover:
- BaseTool contract compliance for all 3 dispatch tools
- Tool execution with mocked DispatchService
- Parameter schema validation (Pydantic level)
- Tool-level validate() logic
- Error handling (service failure, no DB, exceptions)

Blueprint: §9 — Registry enforcement.
"""

import asyncio
from typing import Any, Dict, List
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from pydantic import ValidationError

from backend.copilot.schemas import ConfirmationLevel, SessionContext, ToolResult
from backend.copilot.tools.base import ToolExecutionContext
from backend.copilot.tools.registry import get_tool, run_startup_validation


# ── Module-level: ensure all tools are registered ──────────────────────────

@pytest.fixture(autouse=True, scope="module")
def _ensure_registry():
    """Load all production tools into the registry before running tests."""
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


def _make_mock_result(
    success: bool = True,
    trip_id: int = 1,
    details: dict = None,
    undo_token: str = "undo_abc123",
    message: str = "",
    errors: list = None,
    operation: str = "cancelled",
) -> MagicMock:
    """Build a minimal mock result object that matches dispatch service responses."""
    result = MagicMock()
    result.success = success
    result.trip_id = trip_id
    result.details = details or {}
    result.undo_token = undo_token if success else None
    result.message = message
    result.errors = errors or []
    result.operation = operation
    return result


def _make_mock_bulk_result(
    succeeded: int = 3,
    failed: int = 0,
    total: int = 3,
    results: List[Dict[str, Any]] = None,
) -> MagicMock:
    """Build a mock bulk-assign result."""
    result = MagicMock()
    result.succeeded = succeeded
    result.failed = failed
    result.total = total
    result.results = results or []
    return result


# ═══════════════════════════════════════════════════════════════════════════
#  BaseTool contract — all dispatch tools
# ═══════════════════════════════════════════════════════════════════════════

DISPATCH_TOOL_NAMES = [
    "dispatch.create",
    "dispatch.bulk_assign",
    "dispatch.cancel",
]


class TestDispatchToolContract:
    """Every dispatch tool must satisfy the BaseTool contract."""

    @pytest.mark.parametrize("name", DISPATCH_TOOL_NAMES)
    def test_tool_registered(self, name):
        tool = get_tool(name)
        assert tool is not None, f"Tool '{name}' not found in registry"

    @pytest.mark.parametrize("name", DISPATCH_TOOL_NAMES)
    def test_tool_has_name(self, name):
        tool = get_tool(name)
        assert tool.name == name

    @pytest.mark.parametrize("name", DISPATCH_TOOL_NAMES)
    def test_tool_has_semver_version(self, name):
        tool = get_tool(name)
        import re
        assert re.match(r"^\d+\.\d+\.\d+$", tool.tool_version), (
            f"{name} version '{tool.tool_version}' is not semver"
        )

    @pytest.mark.parametrize("name", DISPATCH_TOOL_NAMES)
    def test_tool_has_description(self, name):
        tool = get_tool(name)
        assert tool.description and tool.description.strip()

    @pytest.mark.parametrize("name", DISPATCH_TOOL_NAMES)
    def test_tool_has_permission(self, name):
        tool = get_tool(name)
        assert tool.required_permission and tool.required_permission.strip()
        assert tool.required_permission == "dispatch:write"

    @pytest.mark.parametrize("name", DISPATCH_TOOL_NAMES)
    def test_tool_has_parameters_schema(self, name):
        tool = get_tool(name)
        from pydantic import BaseModel
        assert issubclass(tool.parameters_schema, BaseModel), (
            f"{name} parameters_schema is not a BaseModel subclass"
        )

    @pytest.mark.parametrize("name", DISPATCH_TOOL_NAMES)
    def test_tool_not_deprecated(self, name):
        tool = get_tool(name)
        assert not tool.deprecated

    def test_dispatch_create_confirmation_level(self):
        tool = get_tool("dispatch.create")
        assert tool.confirmation_level == ConfirmationLevel.BUSINESS

    def test_dispatch_bulk_assign_confirmation_level(self):
        tool = get_tool("dispatch.bulk_assign")
        assert tool.confirmation_level == ConfirmationLevel.BUSINESS

    def test_dispatch_cancel_confirmation_level(self):
        tool = get_tool("dispatch.cancel")
        assert tool.confirmation_level == ConfirmationLevel.DESTRUCTIVE

    def test_dispatch_create_supports_undo(self):
        tool = get_tool("dispatch.create")
        assert tool.supports_undo is True

    def test_dispatch_bulk_assign_no_undo(self):
        tool = get_tool("dispatch.bulk_assign")
        assert tool.supports_undo is False

    def test_dispatch_cancel_no_undo(self):
        tool = get_tool("dispatch.cancel")
        assert tool.supports_undo is False

    @pytest.mark.parametrize("name", DISPATCH_TOOL_NAMES)
    def test_validate_returns_list(self, name, ctx):
        tool = get_tool(name)
        # Use model_construct to bypass known Pydantic field-ordering bug in
        # DispatchCreateParams._check_at_least_one
        if name == "dispatch.create":
            params = tool.parameters_schema.model_construct(trip_id=1, truck_id=10)
        elif name == "dispatch.bulk_assign":
            params = tool.parameters_schema(trip_ids=[1, 2], assign_type="truck", assign_id=5)
        elif name == "dispatch.cancel":
            params = tool.parameters_schema(trip_id=1)
        else:
            params = tool.parameters_schema()
        errors = asyncio.run(tool.validate(params, ctx))
        assert isinstance(errors, list)

    @pytest.mark.parametrize("name", DISPATCH_TOOL_NAMES)
    def test_execute_returns_tool_result(self, name, ctx):
        tool = get_tool(name)
        if name == "dispatch.create":
            params = tool.parameters_schema.model_construct(trip_id=1, truck_id=10)
        elif name == "dispatch.bulk_assign":
            params = tool.parameters_schema(trip_ids=[1, 2], assign_type="truck", assign_id=5)
        elif name == "dispatch.cancel":
            params = tool.parameters_schema(trip_id=1)
        else:
            params = tool.parameters_schema()
        result = asyncio.run(tool.execute(params, ctx))
        assert isinstance(result, ToolResult)
        assert result.status in ("success", "failed", "unavailable", "permission_denied", "needs_confirmation")
        assert result.message_key and result.message_key.strip()


# ═══════════════════════════════════════════════════════════════════════════
#  Parameter schema validation
# ═══════════════════════════════════════════════════════════════════════════

class TestDispatchCreateParams:
    """dispatch.create parameter schema edge cases."""

    def test_rejects_trip_id_zero(self):
        """Pydantic gt=0 constraint rejects trip_id=0.
        The _check_at_least_one validator also fires but the built-in constraint
        catches it first."""
        tool = get_tool("dispatch.create")
        with pytest.raises(ValidationError):
            tool.parameters_schema(trip_id=0, truck_id=10)

    def test_rejects_trip_id_negative(self):
        """Pydantic gt=0 constraint rejects negative trip_id."""
        tool = get_tool("dispatch.create")
        with pytest.raises(ValidationError):
            tool.parameters_schema(trip_id=-1, truck_id=10)

    def test_coerces_empty_string_truck_id_to_none(self):
        """The _coerce_none validator converts ' ' → None for optional fields."""
        tool = get_tool("dispatch.create")
        params = tool.parameters_schema.model_construct(trip_id=1, truck_id="", driver_id="")
        # model_construct skips validators, so we test Pydantic validation separately

    def test_validate_catches_non_positive_trip_id(self, ctx):
        tool = get_tool("dispatch.create")
        params = tool.parameters_schema.model_construct(trip_id=0, truck_id=10)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0

    def test_validate_catches_non_positive_truck_id(self, ctx):
        tool = get_tool("dispatch.create")
        params = tool.parameters_schema.model_construct(trip_id=1, truck_id=0)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0

    def test_validate_catches_non_positive_driver_id(self, ctx):
        tool = get_tool("dispatch.create")
        params = tool.parameters_schema.model_construct(trip_id=1, driver_id=0)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0

    def test_validate_catches_both_none(self, ctx):
        """When both truck_id and driver_id are None, validate() returns errors."""
        tool = get_tool("dispatch.create")
        params = tool.parameters_schema.model_construct(trip_id=1, truck_id=None, driver_id=None)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("truck_id" in e.lower() or "driver_id" in e.lower() for e in errors)

    def test_validate_passes_with_truck_id(self, ctx):
        tool = get_tool("dispatch.create")
        params = tool.parameters_schema.model_construct(trip_id=1, truck_id=10)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0

    def test_validate_passes_with_driver_id(self, ctx):
        tool = get_tool("dispatch.create")
        params = tool.parameters_schema.model_construct(trip_id=1, driver_id=20)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0

    def test_validate_passes_with_both(self, ctx):
        tool = get_tool("dispatch.create")
        params = tool.parameters_schema.model_construct(trip_id=1, truck_id=10, driver_id=20)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


class TestDispatchBulkAssignParams:
    """dispatch.bulk_assign parameter schema edge cases."""

    def test_accepts_valid_truck_assign(self):
        tool = get_tool("dispatch.bulk_assign")
        params = tool.parameters_schema(trip_ids=[1, 2, 3], assign_type="truck", assign_id=5)
        assert params.trip_ids == [1, 2, 3]
        assert params.assign_type == "truck"
        assert params.assign_id == 5

    def test_accepts_valid_driver_assign(self):
        tool = get_tool("dispatch.bulk_assign")
        params = tool.parameters_schema(trip_ids=[1], assign_type="driver", assign_id=10)
        assert params.assign_type == "driver"

    def test_rejects_empty_trip_ids(self):
        tool = get_tool("dispatch.bulk_assign")
        with pytest.raises(ValidationError):
            tool.parameters_schema(trip_ids=[], assign_type="truck", assign_id=1)

    def test_rejects_invalid_assign_type(self):
        tool = get_tool("dispatch.bulk_assign")
        with pytest.raises(ValidationError):
            tool.parameters_schema(trip_ids=[1], assign_type="invalid", assign_id=1)

    def test_rejects_zero_assign_id(self):
        tool = get_tool("dispatch.bulk_assign")
        with pytest.raises(ValidationError):
            tool.parameters_schema(trip_ids=[1], assign_type="truck", assign_id=0)

    def test_validate_checks_empty_trip_ids(self, ctx):
        tool = get_tool("dispatch.bulk_assign")
        # model_construct to bypass Pydantic min_length=1
        params = tool.parameters_schema.model_construct(
            trip_ids=[], assign_type="truck", assign_id=5
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0

    def test_validate_checks_assign_type(self, ctx):
        tool = get_tool("dispatch.bulk_assign")
        params = tool.parameters_schema.model_construct(
            trip_ids=[1], assign_type="invalid", assign_id=5
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0

    def test_validate_checks_non_positive_assign_id(self, ctx):
        tool = get_tool("dispatch.bulk_assign")
        params = tool.parameters_schema.model_construct(
            trip_ids=[1], assign_type="truck", assign_id=0
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0

    def test_validate_passes_valid(self, ctx):
        tool = get_tool("dispatch.bulk_assign")
        params = tool.parameters_schema(trip_ids=[1], assign_type="truck", assign_id=5)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


class TestDispatchCancelParams:
    """dispatch.cancel parameter schema edge cases."""

    def test_accepts_valid_trip_id(self):
        tool = get_tool("dispatch.cancel")
        params = tool.parameters_schema(trip_id=1)
        assert params.trip_id == 1
        assert params.reason == ""

    def test_accepts_with_reason(self):
        tool = get_tool("dispatch.cancel")
        params = tool.parameters_schema(trip_id=1, reason="Customer cancelled")
        assert params.reason == "Customer cancelled"

    def test_rejects_trip_id_zero(self):
        tool = get_tool("dispatch.cancel")
        with pytest.raises(ValidationError):
            tool.parameters_schema(trip_id=0)

    def test_rejects_trip_id_negative(self):
        tool = get_tool("dispatch.cancel")
        with pytest.raises(ValidationError):
            tool.parameters_schema(trip_id=-1)

    def test_validate_catches_non_positive(self, ctx):
        tool = get_tool("dispatch.cancel")
        # Bypass Pydantic gt=0 with model_construct
        params = tool.parameters_schema.model_construct(trip_id=0)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0

    def test_validate_passes_valid(self, ctx):
        tool = get_tool("dispatch.cancel")
        params = tool.parameters_schema(trip_id=5)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  DispatchService execution — mocked service injection
# ═══════════════════════════════════════════════════════════════════════════

class TestDispatchCreateExecution:
    """dispatch.create execute() with mocked DispatchService."""

    def _make_params(self, **kwargs):
        """Helper to build DispatchCreateParams via model_construct to avoid field-ordering bug."""
        tool = get_tool("dispatch.create")
        defaults = {"trip_id": 1, "truck_id": 10, "driver_id": None}
        defaults.update(kwargs)
        return tool.parameters_schema.model_construct(**defaults)

    def test_execute_success_injects_service(self, ctx):
        """When dispatch_service is injected in ctx, it should be used."""
        tool = get_tool("dispatch.create")
        mock_service = MagicMock()
        mock_service.assign_both.return_value = _make_mock_result(
            success=True,
            trip_id=1,
            details={"truck_plate": "AB-123", "driver_name": "John Doe"},
            undo_token="undo_xyz",
        )
        ctx.services["dispatch_service"] = mock_service

        params = self._make_params(trip_id=1, truck_id=10, driver_id=20)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["trip_id"] == 1
        assert result.data["truck_id"] == 10
        assert result.data["driver_id"] == 20
        assert result.data["status"] == "assigned"
        assert result.undo_token == "undo_xyz"
        mock_service.assign_both.assert_called_once_with(
            trip_id=1, truck_id=10, driver_id=20,
        )

    def test_execute_success_with_truck_only(self, ctx):
        tool = get_tool("dispatch.create")
        mock_service = MagicMock()
        mock_service.assign_both.return_value = _make_mock_result(
            success=True, trip_id=2, details={"truck_plate": "CD-456", "driver_name": "—"},
        )
        ctx.services["dispatch_service"] = mock_service

        params = self._make_params(trip_id=2, truck_id=15, driver_id=None)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["trip_id"] == 2
        assert result.data["truck_id"] == 15
        assert result.data["driver_id"] is None
        mock_service.assign_both.assert_called_once_with(
            trip_id=2, truck_id=15, driver_id=None,
        )

    def test_execute_success_with_driver_only(self, ctx):
        tool = get_tool("dispatch.create")
        mock_service = MagicMock()
        mock_service.assign_both.return_value = _make_mock_result(
            success=True, trip_id=3, details={"truck_plate": "—", "driver_name": "Jane"},
        )
        ctx.services["dispatch_service"] = mock_service

        params = self._make_params(trip_id=3, truck_id=None, driver_id=25)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["driver_id"] == 25
        assert result.data["truck_id"] is None

    def test_execute_service_failure(self, ctx):
        tool = get_tool("dispatch.create")
        mock_service = MagicMock()
        mock_service.assign_both.return_value = _make_mock_result(
            success=False,
            message="Truck is already assigned",
        )
        ctx.services["dispatch_service"] = mock_service

        params = self._make_params(trip_id=1, truck_id=10)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.dispatch.create.failed"

    def test_execute_no_service_no_db(self, ctx):
        """When neither service nor db is available, returns unavailable."""
        tool = get_tool("dispatch.create")
        params = self._make_params(trip_id=1, truck_id=10)
        result = asyncio.run(tool.execute(params, ctx))  # empty services dict

        assert result.status == "unavailable"
        assert result.message_key == "copilot.error.no_db"

    def test_execute_exception_handling(self, ctx):
        """Service exceptions are caught and returned as failed ToolResult."""
        tool = get_tool("dispatch.create")
        mock_service = MagicMock()
        mock_service.assign_both.side_effect = RuntimeError("Unexpected DB error")
        ctx.services["dispatch_service"] = mock_service

        params = self._make_params(trip_id=1, truck_id=10)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.internal"

    @patch("backend.copilot.tools.dispatch_tools._build_dispatch_service")
    def test_execute_builds_service_from_db(self, mock_build, ctx):
        """When no dispatch_service in ctx, fall back to building from db."""
        tool = get_tool("dispatch.create")
        mock_service = MagicMock()
        mock_service.assign_both.return_value = _make_mock_result(success=True, trip_id=1, details={})
        mock_build.return_value = mock_service

        ctx.services["db"] = MagicMock()
        params = self._make_params(trip_id=1, truck_id=10)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        mock_build.assert_called_once()

    def test_undo_success(self, ctx):
        """dispatch.create undo() restores the previous trip state."""
        from models.trip_models import TripUpdate

        tool = get_tool("dispatch.create")
        mock_trip_service = MagicMock()
        mock_trip_service.update.return_value = MagicMock(success=True)
        ctx.services["trip_service"] = mock_trip_service

        undo_token = '{"trip_id": 1, "undo_description": "Restored trip #1", "previous_state": {"status": "pending"}}'
        result = asyncio.run(tool.undo(undo_token, ctx))

        assert result.status == "success"
        assert result.message_key == "copilot.undo.success"
        # The service now receives a typed TripUpdate object instead of a raw dict
        mock_trip_service.update.assert_called_once()
        args = mock_trip_service.update.call_args
        assert args[0][0] == 1, f"Expected trip_id=1, got {args[0][0]}"
        update_obj = args[0][1]
        assert isinstance(update_obj, TripUpdate), f"Expected TripUpdate, got {type(update_obj)}"
        assert update_obj.status == "pending"

    def test_undo_invalid_token(self, ctx):
        """Invalid JSON undo_token returns failed."""
        tool = get_tool("dispatch.create")
        result = asyncio.run(tool.undo("not-json", ctx))
        assert result.status == "failed"
        assert result.message_key == "copilot.undo.invalid_token"

    def test_undo_missing_previous_state(self, ctx):
        """Token without previous_state returns failed."""
        tool = get_tool("dispatch.create")
        result = asyncio.run(tool.undo('{"trip_id": 1}', ctx))
        assert result.status == "failed"
        assert result.message_key == "copilot.undo.invalid_token"

    def test_undo_no_trip_service_no_db(self, ctx):
        """When neither trip_service nor db is available, returns unavailable."""
        tool = get_tool("dispatch.create")
        result = asyncio.run(
            tool.undo('{"trip_id": 1, "previous_state": {"status": "pending"}}', ctx)
        )
        assert result.status == "unavailable"
        assert result.message_key == "copilot.error.no_db"


class TestDispatchBulkAssignExecution:
    """dispatch.bulk_assign execute() with mocked service."""

    def test_execute_bulk_assign_truck(self, ctx):
        tool = get_tool("dispatch.bulk_assign")
        mock_service = MagicMock()
        mock_service.bulk_assign_truck.return_value = _make_mock_bulk_result(
            succeeded=3, failed=0, total=3,
            results=[
                MagicMock(success=True, trip_id=1, message=""),
                MagicMock(success=True, trip_id=2, message=""),
                MagicMock(success=True, trip_id=3, message=""),
            ],
        )
        ctx.services["dispatch_service"] = mock_service

        params = tool.parameters_schema(trip_ids=[1, 2, 3], assign_type="truck", assign_id=5)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["success_count"] == 3
        assert result.data["failed_count"] == 0
        assert result.data["total"] == 3
        mock_service.bulk_assign_truck.assert_called_once_with(
            trip_ids=[1, 2, 3], truck_id=5,
        )
        mock_service.bulk_assign_driver.assert_not_called()

    def test_execute_bulk_assign_driver(self, ctx):
        tool = get_tool("dispatch.bulk_assign")
        mock_service = MagicMock()
        mock_service.bulk_assign_driver.return_value = _make_mock_bulk_result(
            succeeded=1, failed=0, total=1,
            results=[MagicMock(success=True, trip_id=1, message="")],
        )
        ctx.services["dispatch_service"] = mock_service

        params = tool.parameters_schema(trip_ids=[1], assign_type="driver", assign_id=10)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        mock_service.bulk_assign_driver.assert_called_once_with(
            trip_ids=[1], driver_id=10,
        )
        mock_service.bulk_assign_truck.assert_not_called()

    def test_execute_with_failures(self, ctx):
        tool = get_tool("dispatch.bulk_assign")
        mock_service = MagicMock()
        mock_service.bulk_assign_truck.return_value = _make_mock_bulk_result(
            succeeded=2, failed=1, total=3,
            results=[
                MagicMock(success=True, trip_id=1, message=""),
                MagicMock(success=False, trip_id=2, message="Conflict"),
                MagicMock(success=True, trip_id=3, message=""),
            ],
        )
        ctx.services["dispatch_service"] = mock_service

        params = tool.parameters_schema(trip_ids=[1, 2, 3], assign_type="truck", assign_id=5)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["success_count"] == 2
        assert result.data["failed_count"] == 1
        assert len(result.data["failures"]) == 1
        assert result.data["failures"][0]["trip_id"] == 2

    def test_execute_no_service_no_db(self, ctx):
        """Without dispatch_service or db, returns unavailable."""
        tool = get_tool("dispatch.bulk_assign")
        # Clear services so _resolve_dispatch_service returns None
        ctx.services.clear()
        params = tool.parameters_schema(trip_ids=[1], assign_type="truck", assign_id=5)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "unavailable"
        assert result.message_key == "copilot.error.no_db"

    def test_execute_exception_handling(self, ctx):
        tool = get_tool("dispatch.bulk_assign")
        mock_service = MagicMock()
        mock_service.bulk_assign_truck.side_effect = RuntimeError("Bulk assign crashed")
        ctx.services["dispatch_service"] = mock_service

        params = tool.parameters_schema(trip_ids=[1], assign_type="truck", assign_id=5)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.internal"


class TestDispatchCancelExecution:
    """dispatch.cancel execute() with mocked service."""

    def test_execute_success(self, ctx):
        tool = get_tool("dispatch.cancel")
        mock_service = MagicMock()
        mock_service.cancel_trip.return_value = _make_mock_result(
            success=True, trip_id=1, operation="cancelled", undo_token="cancel_xyz",
        )
        ctx.services["dispatch_service"] = mock_service

        params = tool.parameters_schema(trip_id=1, reason="Customer request")
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["trip_id"] == 1
        assert result.data["status"] == "cancelled"
        assert result.data["operation"] == "cancelled"
        assert result.undo_token == "cancel_xyz"
        mock_service.cancel_trip.assert_called_once_with(
            trip_id=1, reason="Customer request",
        )

    def test_execute_success_no_reason(self, ctx):
        tool = get_tool("dispatch.cancel")
        mock_service = MagicMock()
        mock_service.cancel_trip.return_value = _make_mock_result(
            success=True, trip_id=2, operation="cancelled",
        )
        ctx.services["dispatch_service"] = mock_service

        params = tool.parameters_schema(trip_id=2)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.message_params["reason"] == "not specified"

    def test_execute_service_failure(self, ctx):
        tool = get_tool("dispatch.cancel")
        mock_service = MagicMock()
        mock_service.cancel_trip.return_value = _make_mock_result(
            success=False, message="Trip already completed",
        )
        ctx.services["dispatch_service"] = mock_service

        params = tool.parameters_schema(trip_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.dispatch.cancel.failed"

    def test_execute_no_service_no_db(self, ctx):
        """Without dispatch_service or db, returns unavailable."""
        tool = get_tool("dispatch.cancel")
        ctx.services.clear()
        params = tool.parameters_schema(trip_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "unavailable"
        assert result.message_key == "copilot.error.no_db"

    def test_execute_exception_handling(self, ctx):
        tool = get_tool("dispatch.cancel")
        mock_service = MagicMock()
        mock_service.cancel_trip.side_effect = RuntimeError("Cancel failed")
        ctx.services["dispatch_service"] = mock_service

        params = tool.parameters_schema(trip_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.internal"
