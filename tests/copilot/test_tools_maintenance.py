"""Comprehensive unit tests for maintenance.schedule Co-Pilot tool.

Tests cover:
- BaseTool contract compliance
- Tool execution with mocked FleetMaintenanceService
- Parameter schema validation (Pydantic level + field_validator)
- Tool-level validate() logic
- Error handling (service failure, no DB, exceptions)

Blueprint: §9 — Registry enforcement.
"""

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


# ═══════════════════════════════════════════════════════════════════════════
#  BaseTool contract
# ═══════════════════════════════════════════════════════════════════════════

MAINTENANCE_TOOL_NAME = "maintenance.schedule"


class TestMaintenanceToolContract:
    """maintenance.schedule must satisfy the BaseTool contract."""

    def test_tool_registered(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        assert tool is not None, f"Tool '{MAINTENANCE_TOOL_NAME}' not found in registry"

    def test_tool_has_name(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        assert tool.name == MAINTENANCE_TOOL_NAME

    def test_tool_has_semver_version(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        import re
        assert re.match(r"^\d+\.\d+\.\d+$", tool.tool_version)

    def test_tool_has_description(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        assert tool.description and tool.description.strip()

    def test_tool_has_permission(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        assert tool.required_permission and tool.required_permission.strip()
        assert tool.required_permission == "maintenance:write"

    def test_tool_has_parameters_schema(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        from pydantic import BaseModel
        assert issubclass(tool.parameters_schema, BaseModel)

    def test_tool_not_deprecated(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        assert not tool.deprecated

    def test_tool_confirmation_level(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        assert tool.confirmation_level == ConfirmationLevel.BUSINESS

    def test_tool_supports_undo_correct(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        assert tool.supports_undo is False

    def test_validate_returns_list(self, ctx):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema(truck_id=1, maint_type="oil_change")
        errors = asyncio.run(tool.validate(params, ctx))
        assert isinstance(errors, list)

    def test_execute_returns_tool_result(self, ctx):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema(truck_id=1, maint_type="oil_change")
        result = asyncio.run(tool.execute(params, ctx))
        assert isinstance(result, ToolResult)
        assert result.status in ("success", "failed", "unavailable", "permission_denied", "needs_confirmation")
        assert result.message_key and result.message_key.strip()


# ═══════════════════════════════════════════════════════════════════════════
#  Parameter schema validation
# ═══════════════════════════════════════════════════════════════════════════


class TestMaintenanceScheduleParams:
    """maintenance.schedule parameter schema edge cases."""

    def test_accepts_minimal_params(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema(truck_id=1, maint_type="oil_change")
        assert params.truck_id == 1
        assert params.maint_type == "oil_change"
        assert params.interval_km is None
        assert params.interval_months is None
        assert params.fixed_expiry_date is None
        assert params.last_done_km is None
        assert params.last_done_date is None

    def test_accepts_all_params(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema(
            truck_id=5,
            maint_type="inspection",
            interval_km=15000.0,
            interval_months=6,
            fixed_expiry_date="2025-06-01",
            last_done_km=85000.0,
            last_done_date="2024-06-01",
        )
        assert params.truck_id == 5
        assert params.maint_type == "inspection"
        assert params.interval_km == 15000.0
        assert params.interval_months == 6
        assert params.fixed_expiry_date == "2025-06-01"
        assert params.last_done_km == 85000.0
        assert params.last_done_date == "2024-06-01"

    def test_rejects_truck_id_zero(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        with pytest.raises(ValidationError):
            tool.parameters_schema(truck_id=0, maint_type="oil_change")

    def test_rejects_truck_id_negative(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        with pytest.raises(ValidationError):
            tool.parameters_schema(truck_id=-1, maint_type="oil_change")

    def test_rejects_invalid_maint_type(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        with pytest.raises(ValidationError):
            tool.parameters_schema(truck_id=1, maint_type="invalid_type")

    def test_field_validator_lowers_maint_type(self):
        """field_validator lowercases and strips maint_type."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema(truck_id=1, maint_type="  OIL_CHANGE  ")
        assert params.maint_type == "oil_change"

    def test_valid_maint_types(self):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        for mt in ("oil_change", "brake_check", "tire_rotation", "inspection", "other"):
            params = tool.parameters_schema(truck_id=1, maint_type=mt)
            assert params.maint_type == mt

    def test_coerces_empty_fixed_expiry_date_to_none(self):
        """field_validator converts '' fixed_expiry_date to None."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema(
            truck_id=1, maint_type="other", fixed_expiry_date="",
        )
        assert params.fixed_expiry_date is None

    def test_coerces_empty_last_done_date_to_none(self):
        """field_validator converts '' last_done_date to None."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema(
            truck_id=1, maint_type="other", last_done_date="",
        )
        assert params.last_done_date is None

    def test_validate_checks_positive_truck_id(self, ctx):
        """validate() catches non-positive truck_id (bypass Pydantic gt=0)."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema.model_construct(truck_id=0, maint_type="oil_change")
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("truck_id" in e for e in errors)

    def test_validate_checks_maint_type(self, ctx):
        """validate() catches invalid maint_type."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema.model_construct(truck_id=1, maint_type="bogus")
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("maint_type" in e for e in errors)

    def test_validate_checks_non_negative_interval_km(self, ctx):
        """validate() catches negative interval_km."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema.model_construct(
            truck_id=1, maint_type="oil_change", interval_km=-1,
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("interval_km" in e for e in errors)

    def test_validate_checks_interval_months_at_least_one(self, ctx):
        """validate() catches interval_months < 1."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema.model_construct(
            truck_id=1, maint_type="oil_change", interval_months=0,
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("interval_months" in e for e in errors)

    def test_validate_checks_non_negative_last_done_km(self, ctx):
        """validate() catches negative last_done_km."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema.model_construct(
            truck_id=1, maint_type="brake_check", last_done_km=-5,
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("last_done_km" in e for e in errors)

    def test_validate_passes_valid_params(self, ctx):
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema(
            truck_id=1,
            maint_type="tire_rotation",
            interval_km=10000.0,
            interval_months=12,
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  Execution — mocked FleetMaintenanceService
# ═══════════════════════════════════════════════════════════════════════════


class TestMaintenanceScheduleExecution:
    """maintenance.schedule execute() with mocked FleetMaintenanceService."""

    @patch("backend.services.fleet_maintenance_service.FleetMaintenanceService")
    def test_execute_success_injected_service(self, MockService, ctx):
        """When fleet_maintenance_service is injected in ctx, use it."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)

        mock_svc = MagicMock()
        mock_svc.add_schedule.return_value = 42
        ctx.services["fleet_maintenance_service"] = mock_svc

        params = tool.parameters_schema(truck_id=10, maint_type="oil_change")
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["schedule_id"] == 42
        assert result.message_key == "copilot.maintenance.schedule.success"
        mock_svc.add_schedule.assert_called_once_with(
            truck_id=10, maint_type="oil_change",
            interval_km=None, interval_months=None,
            fixed_expiry_date="", last_done_km=None, last_done_date="",
        )

    @patch("backend.services.fleet_maintenance_service.FleetMaintenanceService")
    def test_execute_success_with_all_params(self, MockService, ctx):
        """All optional parameters are forwarded to the service."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)

        mock_svc = MagicMock()
        mock_svc.add_schedule.return_value = 99
        ctx.services["fleet_maintenance_service"] = mock_svc

        params = tool.parameters_schema(
            truck_id=5,
            maint_type="inspection",
            interval_km=15000.0,
            interval_months=6,
            fixed_expiry_date="2025-06-01",
            last_done_km=50000.0,
            last_done_date="2024-12-01",
        )
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        mock_svc.add_schedule.assert_called_once_with(
            truck_id=5, maint_type="inspection",
            interval_km=15000.0, interval_months=6,
            fixed_expiry_date="2025-06-01",
            last_done_km=50000.0, last_done_date="2024-12-01",
        )

    @patch("backend.services.fleet_maintenance_service.FleetMaintenanceService")
    def test_execute_builds_from_db_when_no_injected_service(self, MockService, ctx_with_db):
        """When service not injected, fall back to building from db."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)

        mock_svc = MagicMock()
        mock_svc.add_schedule.return_value = 77
        MockService.return_value = mock_svc

        params = tool.parameters_schema(truck_id=3, maint_type="brake_check")
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        assert result.data["schedule_id"] == 77
        MockService.assert_called_once()

    def test_execute_no_service_no_db(self, ctx):
        """When neither service nor db is available, returns unavailable."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)
        params = tool.parameters_schema(truck_id=1, maint_type="oil_change")
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "unavailable"
        assert result.message_key == "copilot.error.no_db"

    def test_execute_exception(self, ctx):
        """Service exception is caught and returned as failed."""
        tool = get_tool(MAINTENANCE_TOOL_NAME)

        mock_svc = MagicMock()
        mock_svc.add_schedule.side_effect = RuntimeError("Service error")
        ctx.services["fleet_maintenance_service"] = mock_svc

        params = tool.parameters_schema(truck_id=1, maint_type="other")
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.internal"
