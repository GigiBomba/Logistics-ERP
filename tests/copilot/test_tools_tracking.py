"""Comprehensive unit tests for the Tracking domain tools.

Tools:
- tracking.get_live_positions  — SAFE, read-only
- tracking.get_vehicle_history — SAFE, read-only

Tests cover:
- BaseTool contract for each tool
- Parameter schema validation
- validate() behaviour
- execute() with mocked FleetTrackingService (success, service failure, exception)
- Error handling (service unavailable, unexpected exceptions)

Blueprint: §9.1 — Tracking, Level 0.
"""

import asyncio
from datetime import datetime
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

LIVE_POSITIONS_TOOL = "tracking.get_live_positions"
VEHICLE_HISTORY_TOOL = "tracking.get_vehicle_history"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_ctx(**overrides: Any) -> ToolExecutionContext:
    """Build a minimal ToolExecutionContext."""
    kwargs: dict = dict(
        company_id=1,
        user_id=1,
        role="dispatcher",
        session_context=SessionContext(),
        services={},
    )
    kwargs.update(overrides)
    return ToolExecutionContext(**kwargs)


def _mock_vehicle_position(
    device_id: str = "42",
    name: str = "TRUCK-001",
    lat: float = 52.5200,
    lon: float = 13.4050,
    speed: float = 65.0,
    heading: float = 180.0,
    status: str = "moving",
) -> Any:
    """Build a mock VehiclePosition-like dataclass instance."""
    pos = MagicMock()
    pos.device_id = device_id
    pos.name = name
    pos.latitude = lat
    pos.longitude = lon
    pos.speed_kmh = speed
    pos.heading = heading
    pos.timestamp = datetime(2025, 6, 15, 10, 30, 0)
    pos.status = status
    pos.address = "Berlin, DE"
    pos.odometer_km = 123456.0
    pos.ignition_on = True
    return pos


# ═══════════════════════════════════════════════════════════════════════════════
# 1. tracking.get_live_positions
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetLivePositionsContract:
    """BaseTool contract for tracking.get_live_positions."""

    def test_tool_is_registered(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        assert tool is not None

    def test_tool_name(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        assert tool.name == LIVE_POSITIONS_TOOL

    def test_tool_version_is_semver(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        parts = tool.tool_version.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts)

    def test_description_is_non_empty(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        assert tool.description and tool.description.strip()

    def test_required_permission(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        assert tool.required_permission == "tracking:read"

    def test_confirmation_level_safe(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        assert tool.confirmation_level == ConfirmationLevel.SAFE

    def test_supports_undo_false(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        assert not tool.supports_undo

    def test_deprecated_false(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        assert not tool.deprecated

    def test_parameters_schema_is_basemodel(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        assert issubclass(tool.parameters_schema, BaseModel)

    def test_parameters_schema_has_force_refresh(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        fields = tool.parameters_schema.model_fields
        assert "force_refresh" in fields
        assert not fields["force_refresh"].is_required()
        assert fields["force_refresh"].default is True

    def test_parameters_schema_forbids_extra(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        config = tool.parameters_schema.model_config
        assert config.get("extra") == "forbid"

    def test_undo_raises_not_implemented(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        with pytest.raises(NotImplementedError):
            asyncio.run(tool.undo("token", _make_ctx()))


class TestGetLivePositionsExecute:
    """Execute behaviour for tracking.get_live_positions."""

    def test_execute_returns_tool_result(self):
        with patch("services.fleet_tracking_service.FleetTrackingService") as mock_tracking_service_class:
            mock_service = MagicMock()
            mock_service.get_positions.return_value = []
            mock_tracking_service_class.return_value = mock_service

            tool = get_tool(LIVE_POSITIONS_TOOL)
            params = tool.parameters_schema()  # defaults: force_refresh=True
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert isinstance(result, ToolResult)

    def test_execute_success_with_positions(self):
        with patch("services.fleet_tracking_service.FleetTrackingService") as mock_tracking_service_class:
            positions = [
                _mock_vehicle_position(device_id="1", name="TRUCK-001", lat=52.52, lon=13.40, speed=65.0),
                _mock_vehicle_position(device_id="2", name="TRUCK-002", lat=48.85, lon=2.35, speed=0.0, status="stopped"),
            ]
            mock_service = MagicMock()
            mock_service.get_positions.return_value = positions
            mock_tracking_service_class.return_value = mock_service

            tool = get_tool(LIVE_POSITIONS_TOOL)
            params = tool.parameters_schema(force_refresh=True)
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            assert result.data is not None
            assert len(result.data["positions"]) == 2
            assert result.data["positions"][0]["vehicle_id"] == "1"
            assert result.data["positions"][0]["name"] == "TRUCK-001"
            assert result.data["positions"][0]["latitude"] == 52.52
            assert result.data["positions"][0]["speed_kmh"] == 65.0
            assert result.message_key == "copilot.tracking.positions_fetched"
            assert result.message_params["count"] == 2

    def test_execute_with_force_refresh_false(self):
        """When force_refresh=False, the param is passed through."""
        with patch("services.fleet_tracking_service.FleetTrackingService") as mock_tracking_service_class:
            mock_service = MagicMock()
            mock_service.get_positions.return_value = []
            mock_tracking_service_class.return_value = mock_service

            tool = get_tool(LIVE_POSITIONS_TOOL)
            params = tool.parameters_schema(force_refresh=False)
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            mock_service.get_positions.assert_called_once_with(force_refresh=False)

    def test_execute_empty_positions(self):
        """No positions returns success with empty list."""
        with patch("services.fleet_tracking_service.FleetTrackingService") as mock_tracking_service_class:
            mock_service = MagicMock()
            mock_service.get_positions.return_value = []
            mock_tracking_service_class.return_value = mock_service

            tool = get_tool(LIVE_POSITIONS_TOOL)
            params = tool.parameters_schema()
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            assert result.data["positions"] == []

    def test_execute_handles_exception(self):
        """When FleetTrackingService raises, tool must return failed."""
        with patch("services.fleet_tracking_service.FleetTrackingService") as mock_tracking_service_class:
            mock_service = MagicMock()
            mock_service.get_positions.side_effect = RuntimeError("GPS adapter offline")
            mock_tracking_service_class.return_value = mock_service

            tool = get_tool(LIVE_POSITIONS_TOOL)
            params = tool.parameters_schema()
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "failed"
            assert "GPS adapter offline" in result.message_params.get("error", "")

    def test_execute_with_default_params_succeeds(self):
        """All params have defaults, so execute should work without kwargs."""
        tool = get_tool(LIVE_POSITIONS_TOOL)
        params = tool.parameters_schema()  # no args required
        ctx = _make_ctx()
        result = asyncio.run(tool.execute(params, ctx))
        assert isinstance(result, ToolResult)

    def test_validate_returns_empty_list(self):
        tool = get_tool(LIVE_POSITIONS_TOOL)
        params = tool.parameters_schema()
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert errors == []


# ═══════════════════════════════════════════════════════════════════════════════
# 2. tracking.get_vehicle_history
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetVehicleHistoryContract:
    """BaseTool contract for tracking.get_vehicle_history."""

    def test_tool_is_registered(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        assert tool is not None

    def test_tool_name(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        assert tool.name == VEHICLE_HISTORY_TOOL

    def test_tool_version_is_semver(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        parts = tool.tool_version.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts)

    def test_description_is_non_empty(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        assert tool.description and tool.description.strip()

    def test_required_permission(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        assert tool.required_permission == "tracking:read"

    def test_confirmation_level_safe(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        assert tool.confirmation_level == ConfirmationLevel.SAFE

    def test_supports_undo_false(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        assert not tool.supports_undo

    def test_deprecated_false(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        assert not tool.deprecated

    def test_parameters_schema_is_basemodel(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        assert issubclass(tool.parameters_schema, BaseModel)

    def test_parameters_schema_has_expected_fields(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        fields = tool.parameters_schema.model_fields
        assert "vehicle_id" in fields
        assert "date_from" in fields
        assert "date_to" in fields

    def test_parameters_schema_vehicle_id_required(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        assert tool.parameters_schema.model_fields["vehicle_id"].is_required()

    def test_parameters_schema_dates_optional(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        assert not tool.parameters_schema.model_fields["date_from"].is_required()
        assert not tool.parameters_schema.model_fields["date_to"].is_required()

    def test_parameters_schema_forbids_extra(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        config = tool.parameters_schema.model_config
        assert config.get("extra") == "forbid"

    def test_undo_raises_not_implemented(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        with pytest.raises(NotImplementedError):
            asyncio.run(tool.undo("token", _make_ctx()))


class TestGetVehicleHistoryParams:
    """Schema-level validation for tracking.get_vehicle_history."""

    def test_accepts_valid_vehicle_id(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        params = tool.parameters_schema(vehicle_id=5)
        assert params.vehicle_id == 5
        assert params.date_from is None
        assert params.date_to is None

    def test_accepts_vehicle_id_with_dates(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        params = tool.parameters_schema(
            vehicle_id=5,
            date_from="2025-01-01",
            date_to="2025-06-30",
        )
        assert params.vehicle_id == 5
        assert params.date_from == "2025-01-01"
        assert params.date_to == "2025-06-30"

    def test_rejects_missing_vehicle_id(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        with pytest.raises(ValidationError):
            tool.parameters_schema()  # vehicle_id is required


class TestGetVehicleHistoryExecute:
    """Execute behaviour for tracking.get_vehicle_history."""

    def test_execute_returns_tool_result(self):
        """execute() must always return ToolResult."""
        with patch("services.fleet_tracking_service.FleetTrackingService") as mock_tracking_service_class:
            mock_service = MagicMock()
            mock_service.get_positions.return_value = []
            mock_tracking_service_class.return_value = mock_service

            tool = get_tool(VEHICLE_HISTORY_TOOL)
            params = tool.parameters_schema(vehicle_id=1)
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert isinstance(result, ToolResult)

    def test_execute_success_with_matching_positions(self):
        """Vehicle history filters positions by device_id or plate."""
        with (
            patch("services.fleet_tracking_service.FleetTrackingService") as mock_tracking_service_class,
            patch("repositories.fleet_repository.FleetRepository") as mock_fleet_repo_class,
        ):
            positions = [
                _mock_vehicle_position(device_id="5", name="TRUCK-005", lat=52.52, lon=13.40),
                _mock_vehicle_position(device_id="99", name="OTHER-TRUCK", lat=48.85, lon=2.35),
            ]

            mock_service = MagicMock()
            mock_service.get_positions.return_value = positions
            mock_tracking_service_class.return_value = mock_service

            tool = get_tool(VEHICLE_HISTORY_TOOL)
            params = tool.parameters_schema(vehicle_id=5)
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            assert result.data is not None
            assert result.data["vehicle_id"] == 5
            assert len(result.data["positions"]) == 1
            assert result.data["positions"][0]["device_id"] == "5"
            assert result.message_key == "copilot.tracking.history_fetched"

    def test_execute_no_matching_positions(self):
        """When no positions match the vehicle_id, returns empty list."""
        with patch("services.fleet_tracking_service.FleetTrackingService") as mock_tracking_service_class:
            mock_service = MagicMock()
            mock_service.get_positions.return_value = [
                _mock_vehicle_position(device_id="1", name="TRUCK-001"),
                _mock_vehicle_position(device_id="2", name="TRUCK-002"),
            ]
            mock_tracking_service_class.return_value = mock_service

            tool = get_tool(VEHICLE_HISTORY_TOOL)
            params = tool.parameters_schema(vehicle_id=999)
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            assert len(result.data["positions"]) == 0

    def test_execute_handles_exception(self):
        """When FleetTrackingService raises, tool must return failed."""
        with patch("services.fleet_tracking_service.FleetTrackingService") as mock_tracking_service_class:
            mock_service = MagicMock()
            mock_service.get_positions.side_effect = RuntimeError("Service unavailable")
            mock_tracking_service_class.return_value = mock_service

            tool = get_tool(VEHICLE_HISTORY_TOOL)
            params = tool.parameters_schema(vehicle_id=1)
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "failed"
            assert "Service unavailable" in result.message_params.get("error", "")

    def test_execute_with_db_lookup_success(self):
        """When db is available, FleetRepository is used to resolve plate number."""
        with (
            patch("services.fleet_tracking_service.FleetTrackingService") as mock_tracking_service_class,
            patch("repositories.fleet_repository.FleetRepository") as mock_fleet_repo_class,
        ):
            positions = [
                _mock_vehicle_position(device_id="5", name="TRUCK-005", lat=52.52, lon=13.40),
            ]

            mock_service = MagicMock()
            mock_service.get_positions.return_value = positions
            mock_tracking_service_class.return_value = mock_service

            # Mock FleetRepository to return a truck with plate_number
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = {"plate_number": "TRUCK-005"}
            mock_fleet_repo_class.return_value = mock_repo

            tool = get_tool(VEHICLE_HISTORY_TOOL)
            params = tool.parameters_schema(vehicle_id=5)
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            assert len(result.data["positions"]) == 1

    def test_execute_with_db_lookup_failure_graceful(self):
        """FleetRepository failure is caught and does not crash the tool."""
        with (
            patch("services.fleet_tracking_service.FleetTrackingService") as mock_tracking_service_class,
            patch("repositories.fleet_repository.FleetRepository") as mock_fleet_repo_class,
        ):
            positions = [
                _mock_vehicle_position(device_id="5", name="TRUCK-005"),
            ]

            mock_service = MagicMock()
            mock_service.get_positions.return_value = positions
            mock_tracking_service_class.return_value = mock_service

            # FleetRepository raises
            mock_repo = MagicMock()
            mock_repo.get_by_id.side_effect = RuntimeError("DB error")
            mock_fleet_repo_class.return_value = mock_repo

            tool = get_tool(VEHICLE_HISTORY_TOOL)
            params = tool.parameters_schema(vehicle_id=5)
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            # Should still succeed (failure in plate lookup is non-fatal)
            assert result.status == "success"

    def test_validate_returns_empty_list(self):
        tool = get_tool(VEHICLE_HISTORY_TOOL)
        params = tool.parameters_schema(vehicle_id=1)
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert errors == []


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Cross-tool consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestTrackingDomainConsistency:
    """Consistency checks across both tracking tools."""

    def test_both_tools_have_same_permission(self):
        live = get_tool(LIVE_POSITIONS_TOOL)
        hist = get_tool(VEHICLE_HISTORY_TOOL)
        assert live.required_permission == hist.required_permission == "tracking:read"

    def test_both_tools_are_safe(self):
        live = get_tool(LIVE_POSITIONS_TOOL)
        hist = get_tool(VEHICLE_HISTORY_TOOL)
        assert live.confirmation_level == hist.confirmation_level == ConfirmationLevel.SAFE

    def test_both_tools_have_no_undo(self):
        live = get_tool(LIVE_POSITIONS_TOOL)
        hist = get_tool(VEHICLE_HISTORY_TOOL)
        assert not live.supports_undo
        assert not hist.supports_undo

    def test_tool_names_follow_dotted_convention(self):
        for name in [LIVE_POSITIONS_TOOL, VEHICLE_HISTORY_TOOL]:
            assert name.count(".") == 1
            parts = name.split(".")
            assert all(p.islower() for p in parts)
