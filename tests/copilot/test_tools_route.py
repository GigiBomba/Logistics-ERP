"""Comprehensive unit tests for the Route domain tools.

Tools:
- route.calculate          — SAFE, read-only
- route.estimate_cost      — SAFE, read-only
- route.plan_multistop     — SAFE, read-only

Tests cover:
- BaseTool contract for each tool
- Parameter schema validation
- validate() behaviour
- execute() with mocked services (success, edge cases)
- Error handling (missing services, exceptions, invalid inputs)
- Internal helper functions (_get_truck_dict, _legs_from_graphhopper_response,
  _haversine_distance, _compute_legs_from_stops, _build_stop_distances,
  _format_stops, _cost_result_to_dict, _build_multistop_data)

Blueprint: §9.1 — Route tools, Level 0 SAFE.
"""

from __future__ import annotations

import asyncio
import math
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

CALC_TOOL = "route.calculate"
COST_TOOL = "route.estimate_cost"
MULTISTOP_TOOL = "route.plan_multistop"


# ── Helpers ──────────────────────────────────────────────────────────────────


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


def _mk_service_result(success: bool = True, data: dict | None = None):
    """Build a mock ServiceResult-like object."""
    r = MagicMock()
    r.success = success
    r.data = data
    r.errors = []
    return r


# ═══════════════════════════════════════════════════════════════════════════════
# 1. route.calculate
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouteCalculateContract:
    """BaseTool contract for route.calculate."""

    def test_tool_is_registered(self):
        assert get_tool(CALC_TOOL) is not None

    def test_tool_name(self):
        assert get_tool(CALC_TOOL).name == CALC_TOOL

    def test_tool_version_is_semver(self):
        t = get_tool(CALC_TOOL)
        parts = t.tool_version.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts)

    def test_description_non_empty(self):
        assert get_tool(CALC_TOOL).description.strip()

    def test_required_permission(self):
        assert get_tool(CALC_TOOL).required_permission == "routes:read"

    def test_confirmation_level_safe(self):
        assert get_tool(CALC_TOOL).confirmation_level == ConfirmationLevel.SAFE

    def test_supports_undo_false(self):
        assert not get_tool(CALC_TOOL).supports_undo

    def test_parameters_schema_is_basemodel(self):
        assert issubclass(get_tool(CALC_TOOL).parameters_schema, BaseModel)

    def test_parameters_schema_has_expected_fields(self):
        fields = get_tool(CALC_TOOL).parameters_schema.model_fields
        assert "stops" in fields
        assert "profile" in fields
        assert "truck_id" in fields
        assert "avoid_countries" in fields

    def test_stops_required_profile_has_default(self):
        fields = get_tool(CALC_TOOL).parameters_schema.model_fields
        assert fields["stops"].is_required()
        assert not fields["profile"].is_required()
        assert fields["profile"].default == "truck"

    def test_undo_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            asyncio.run(get_tool(CALC_TOOL).undo("token", _make_ctx()))


class TestRouteCalculateParams:
    """Schema validation for route.calculate."""

    def test_accepts_two_stops(self):
        tool = get_tool(CALC_TOOL)
        params = tool.parameters_schema(stops=["Berlin", "Warsaw"])
        assert params.stops == ["Berlin", "Warsaw"]

    def test_accepts_multiple_stops(self):
        tool = get_tool(CALC_TOOL)
        params = tool.parameters_schema(stops=["A", "B", "C", "D"])
        assert len(params.stops) == 4

    def test_accepts_profile_and_truck_id(self):
        tool = get_tool(CALC_TOOL)
        params = tool.parameters_schema(stops=["A", "B"], profile="car", truck_id=5)
        assert params.profile == "car"
        assert params.truck_id == 5

    def test_accepts_avoid_countries(self):
        tool = get_tool(CALC_TOOL)
        params = tool.parameters_schema(stops=["A", "B"], avoid_countries=["BY", "UA"])
        assert params.avoid_countries == ["BY", "UA"]

    def test_rejects_single_stop_via_validate(self):
        """Pydantic schema may not enforce min stops, but validate() does."""
        tool = get_tool(CALC_TOOL)
        params = tool.parameters_schema(stops=["Berlin"])
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert len(errors) > 0
        assert any("stops" in e.lower() or "two" in e.lower() for e in errors)

    def test_rejects_empty_stops(self):
        tool = get_tool(CALC_TOOL)
        # Empty list passes schema but validate catches it
        params = tool.parameters_schema(stops=[])
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert len(errors) > 0

    def test_validate_accepts_two_stops(self):
        tool = get_tool(CALC_TOOL)
        params = tool.parameters_schema(stops=["Berlin", "Warsaw"])
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert errors == []


class TestRouteCalculateExecute:
    """Execute behaviour for route.calculate."""

    def test_execute_missing_service_returns_failed(self):
        tool = get_tool(CALC_TOOL)
        params = tool.parameters_schema(stops=["Berlin", "Warsaw"])
        ctx = _make_ctx()  # No route_service
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "failed"
        assert result.message_key == "copilot.route.error.service_unavailable"

    def test_execute_missing_service_has_reason(self):
        tool = get_tool(CALC_TOOL)
        params = tool.parameters_schema(stops=["Berlin", "Warsaw"])
        ctx = _make_ctx()
        result = asyncio.run(tool.execute(params, ctx))
        assert result.data is not None
        assert "reason" in result.data

    def test_execute_with_mocked_service_success(self):
        tool = get_tool(CALC_TOOL)
        params = tool.parameters_schema(stops=["Berlin", "Warsaw"])

        mock_route = MagicMock()
        mock_route.calculate_route.return_value = {
            "distance_km": 572.0,
            "duration_min": 345.0,
            "geometry": [[52.52, 13.40], [52.23, 14.10], [52.27, 21.00]],
        }

        ctx = _make_ctx(services={"route_service": mock_route})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["distance_km"] == 572.0
        assert result.data["duration_min"] == 345.0
        assert len(result.data["geometry"]) == 3
        assert result.message_key == "copilot.route.calculate.success"

    def test_execute_with_truck_id_and_cost_engine(self):
        """When truck_id is provided and cost_engine is available, fuel estimate is appended."""
        tool = get_tool(CALC_TOOL)
        params = tool.parameters_schema(stops=["Berlin", "Warsaw"], truck_id=5)

        mock_route = MagicMock()
        mock_route.calculate_route.return_value = {
            "distance_km": 572.0,
            "duration_min": 345.0,
            "geometry": [],
        }

        mock_fleet = MagicMock()
        mock_fleet.get.return_value = _mk_service_result(
            data=MagicMock(model_dump=lambda: {"id": 5, "plate_number": "TRUCK-001"}),
        )

        mock_cost = MagicMock()
        cost_data = MagicMock()
        cost_data.breakdown.fuel_cost = 150.0
        cost_data.breakdown.toll_cost = 30.0
        cost_data.breakdown.total_cost = 200.0
        cost_data.breakdown.cost_per_km = 0.35
        cost_data.breakdown.currency = "EUR"
        mock_cost.estimate_for_truck.return_value = _mk_service_result(data=cost_data)

        ctx = _make_ctx(services={
            "route_service": mock_route,
            "fleet_service": mock_fleet,
            "cost_engine_service": mock_cost,
        })
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert "fuel_estimate" in result.data
        assert result.data["fuel_estimate"]["total_cost"] == 200.0

    def test_execute_with_truck_id_but_no_fleet_service(self):
        """If truck_id is given but no fleet_service, calculation still proceeds."""
        tool = get_tool(CALC_TOOL)
        params = tool.parameters_schema(stops=["Berlin", "Warsaw"], truck_id=5)

        mock_route = MagicMock()
        mock_route.calculate_route.return_value = {"distance_km": 100.0, "duration_min": 60.0, "geometry": []}

        ctx = _make_ctx(services={"route_service": mock_route})  # No fleet_service
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"

    def test_execute_handles_route_service_exception(self):
        tool = get_tool(CALC_TOOL)
        params = tool.parameters_schema(stops=["Berlin", "Warsaw"])

        mock_route = MagicMock()
        mock_route.calculate_route.side_effect = RuntimeError("Routing engine timeout")

        ctx = _make_ctx(services={"route_service": mock_route})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert "Routing engine timeout" in str(result.message_params.get("error", ""))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. route.estimate_cost
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouteEstimateCostContract:
    """BaseTool contract for route.estimate_cost."""

    def test_tool_is_registered(self):
        assert get_tool(COST_TOOL) is not None

    def test_tool_name(self):
        assert get_tool(COST_TOOL).name == COST_TOOL

    def test_tool_version_is_semver(self):
        t = get_tool(COST_TOOL)
        assert len(t.tool_version.split(".")) == 3

    def test_required_permission(self):
        assert get_tool(COST_TOOL).required_permission == "routes:read"

    def test_confirmation_level_safe(self):
        assert get_tool(COST_TOOL).confirmation_level == ConfirmationLevel.SAFE

    def test_parameters_schema_is_basemodel(self):
        assert issubclass(get_tool(COST_TOOL).parameters_schema, BaseModel)

    def test_parameters_schema_fields(self):
        fields = get_tool(COST_TOOL).parameters_schema.model_fields
        assert "distance_km" in fields
        assert "truck_id" in fields
        assert "country_code" in fields

    def test_distance_km_has_gt_0(self):
        field = get_tool(COST_TOOL).parameters_schema.model_fields["distance_km"]
        assert field.metadata is not None

    def test_undo_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            asyncio.run(get_tool(COST_TOOL).undo("token", _make_ctx()))


class TestRouteEstimateCostParams:
    """Schema validation for route.estimate_cost."""

    def test_accepts_valid_distance(self):
        tool = get_tool(COST_TOOL)
        params = tool.parameters_schema(distance_km=100.0)
        assert params.distance_km == 100.0
        assert params.truck_id is None
        assert params.country_code == "DEFAULT"

    def test_accepts_truck_id_and_country(self):
        tool = get_tool(COST_TOOL)
        params = tool.parameters_schema(distance_km=250.5, truck_id=3, country_code="RO")
        assert params.truck_id == 3
        assert params.country_code == "RO"

    def test_rejects_zero_distance(self):
        tool = get_tool(COST_TOOL)
        with pytest.raises(ValidationError):
            tool.parameters_schema(distance_km=0)

    def test_rejects_negative_distance(self):
        tool = get_tool(COST_TOOL)
        with pytest.raises(ValidationError):
            tool.parameters_schema(distance_km=-10)

    def test_validate_accepts_positive_distance(self):
        tool = get_tool(COST_TOOL)
        params = tool.parameters_schema(distance_km=1.0)
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert errors == []


class TestRouteEstimateCostExecute:
    """Execute behaviour for route.estimate_cost."""

    def test_execute_with_truck_id_success(self):
        """When truck_id is provided, uses estimate_for_truck path."""
        with patch("services.cost_engine.CostEngineService") as mock_cost_engine_class:
            cost_data = MagicMock()
            cost_data.data.breakdown.fuel_cost = 120.0
            cost_data.data.breakdown.toll_cost = 25.0
            cost_data.data.breakdown.driver_cost = 80.0
            cost_data.data.breakdown.total_cost = 225.0
            cost_data.data.breakdown.cost_per_km = 0.45
            cost_data.data.breakdown.currency = "EUR"
            cost_data.data.breakdown.extra_costs = {}
            cost_data.success = True
            cost_data.errors = []

            mock_engine = MagicMock()
            mock_engine.estimate_for_truck.return_value = cost_data
            mock_cost_engine_class.return_value = mock_engine

            tool = get_tool(COST_TOOL)
            params = tool.parameters_schema(distance_km=500.0, truck_id=3)
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            assert result.data["total_cost"] == 225.0
            assert result.data["fuel_cost"] == 120.0
            assert result.data["cost_per_km"] == 0.45
            assert result.message_key == "copilot.route.estimate_cost.success"

    def test_execute_with_truck_id_returns_failed(self):
        """When estimate_for_truck fails, tool returns failed."""
        with patch("services.cost_engine.CostEngineService") as mock_cost_engine_class:
            cost_data = MagicMock()
            cost_data.success = False
            cost_data.errors = [MagicMock(message="Truck not found")]
            cost_data.data = None

            mock_engine = MagicMock()
            mock_engine.estimate_for_truck.return_value = cost_data
            mock_cost_engine_class.return_value = mock_engine

            tool = get_tool(COST_TOOL)
            params = tool.parameters_schema(distance_km=500.0, truck_id=99)
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "failed"
            assert result.message_key == "copilot.route.estimate_cost.error"

    def test_execute_without_truck_id_uses_legacy_path(self):
        """When no truck_id, uses the legacy estimate() path."""
        with patch("services.cost_engine.CostEngineService") as mock_cost_engine_class:
            cost_data = MagicMock()
            cost_data.success = True
            cost_data.errors = []
            cost_data.data.breakdown.fuel_cost = 100.0
            cost_data.data.breakdown.toll_cost = 20.0
            cost_data.data.breakdown.driver_cost = 0.0
            cost_data.data.breakdown.extra_costs = {}
            cost_data.data.breakdown.total_cost = 120.0
            cost_data.data.breakdown.cost_per_km = 0.24
            cost_data.data.breakdown.currency = "EUR"

            mock_engine = MagicMock()
            mock_engine.estimate.return_value = cost_data
            mock_cost_engine_class.return_value = mock_engine

            tool = get_tool(COST_TOOL)
            params = tool.parameters_schema(distance_km=500.0)
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            assert result.data["total_cost"] == 120.0
            assert result.data["breakdown"]["total_cost"] == 120.0

    def test_execute_with_cost_engine_in_services(self):
        """CostEngineService in ctx.services is preferred over fresh instance."""
        with patch("services.cost_engine.CostEngineService") as mock_cost_engine_class:
            cost_data = MagicMock()
            cost_data.success = True
            cost_data.errors = []
            cost_data.data.breakdown.fuel_cost = 50.0
            cost_data.data.breakdown.toll_cost = 10.0
            cost_data.data.breakdown.driver_cost = 0.0
            cost_data.data.breakdown.extra_costs = {}
            cost_data.data.breakdown.total_cost = 60.0
            cost_data.data.breakdown.cost_per_km = 0.30
            cost_data.data.breakdown.currency = "EUR"

            mock_engine = MagicMock()
            mock_engine.estimate.return_value = cost_data

            tool = get_tool(COST_TOOL)
            params = tool.parameters_schema(distance_km=200.0)
            ctx = _make_ctx(services={"cost_engine_service": mock_engine})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            # Should NOT have created a new CostEngineService (no import needed)
            mock_cost_engine_class.assert_not_called()

    def test_execute_handles_exception(self):
        """Unexpected exceptions are caught and returned as failed."""
        with patch("services.cost_engine.CostEngineService") as mock_cost_engine_class:
            mock_engine = MagicMock()
            mock_engine.estimate.side_effect = ValueError("Invalid calculation")
            mock_cost_engine_class.return_value = mock_engine

            tool = get_tool(COST_TOOL)
            params = tool.parameters_schema(distance_km=100.0)
            ctx = _make_ctx()
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "failed"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. route.plan_multistop
# ═══════════════════════════════════════════════════════════════════════════════


class TestRoutePlanMultistopContract:
    """BaseTool contract for route.plan_multistop."""

    def test_tool_is_registered(self):
        assert get_tool(MULTISTOP_TOOL) is not None

    def test_tool_name(self):
        assert get_tool(MULTISTOP_TOOL).name == MULTISTOP_TOOL

    def test_tool_version_is_semver(self):
        t = get_tool(MULTISTOP_TOOL)
        assert len(t.tool_version.split(".")) == 3

    def test_required_permission(self):
        assert get_tool(MULTISTOP_TOOL).required_permission == "routes:read"

    def test_confirmation_level_safe(self):
        assert get_tool(MULTISTOP_TOOL).confirmation_level == ConfirmationLevel.SAFE

    def test_parameters_schema_is_basemodel(self):
        assert issubclass(get_tool(MULTISTOP_TOOL).parameters_schema, BaseModel)

    def test_parameters_schema_fields(self):
        fields = get_tool(MULTISTOP_TOOL).parameters_schema.model_fields
        assert "stops" in fields
        assert "profile" in fields
        assert "optimize" in fields
        assert "avoid_countries" in fields

    def test_optimize_defaults_to_false(self):
        fields = get_tool(MULTISTOP_TOOL).parameters_schema.model_fields
        assert fields["optimize"].default is False

    def test_undo_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            asyncio.run(get_tool(MULTISTOP_TOOL).undo("token", _make_ctx()))


class TestRoutePlanMultistopParams:
    """Schema and validate() for route.plan_multistop."""

    def test_accepts_valid_stops(self):
        tool = get_tool(MULTISTOP_TOOL)
        params = tool.parameters_schema(stops=["A", "B", "C"])
        assert len(params.stops) == 3

    def test_accepts_optimize_true(self):
        tool = get_tool(MULTISTOP_TOOL)
        params = tool.parameters_schema(stops=["A", "B"], optimize=True)
        assert params.optimize is True

    def test_validate_rejects_single_stop(self):
        tool = get_tool(MULTISTOP_TOOL)
        params = tool.parameters_schema(stops=["Only"])
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert len(errors) > 0

    def test_validate_accepts_two_stops(self):
        tool = get_tool(MULTISTOP_TOOL)
        params = tool.parameters_schema(stops=["Berlin", "Warsaw"])
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert errors == []


class TestRoutePlanMultistopExecute:
    """Execute behaviour for route.plan_multistop."""

    def test_execute_missing_service_returns_failed(self):
        tool = get_tool(MULTISTOP_TOOL)
        params = tool.parameters_schema(stops=["Berlin", "Warsaw"])
        ctx = _make_ctx()
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "failed"
        assert result.message_key == "copilot.route.error.service_unavailable"

    def test_execute_fixed_order_success(self):
        """Default path (no optimisation) returns ordered stops and distances."""
        tool = get_tool(MULTISTOP_TOOL)
        params = tool.parameters_schema(stops=["Berlin", "Poznan", "Warsaw"])

        mock_route = MagicMock()
        mock_route.calculate_route.return_value = {
            "distance_km": 572.0,
            "duration_min": 345.0,
            "stops": [[52.52, 13.40], [52.40, 16.93], [52.27, 21.00]],
            "graphhopper_response": {
                "paths": [{
                    "legs": [
                        {"distance": 270000, "time": 150 * 60000},
                        {"distance": 302000, "time": 195 * 60000},
                    ],
                }],
            },
        }

        ctx = _make_ctx(services={"route_service": mock_route})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["total_distance_km"] == 572.0
        assert result.data["total_duration_min"] == 345.0
        assert len(result.data["ordered_stops"]) == 3
        assert len(result.data["stop_distances"]) == 2
        assert result.message_key == "copilot.route.plan_multistop.success"

    def test_execute_with_optimize_applied(self):
        """When optimize=True and route succeeds, optimization_status='applied'."""
        tool = get_tool(MULTISTOP_TOOL)
        params = tool.parameters_schema(stops=["A", "B", "C"], optimize=True)

        mock_route = MagicMock()
        mock_route.calculate_route.return_value = {
            "distance_km": 500.0,
            "duration_min": 300.0,
            "stops": [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]],
            "graphhopper_response": {
                "paths": [{
                    "legs": [
                        {"distance": 200000, "time": 120 * 60000},
                        {"distance": 300000, "time": 180 * 60000},
                    ],
                }],
            },
        }

        ctx = _make_ctx(services={"route_service": mock_route})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data.get("optimization_status") == "applied"

    def test_execute_optimize_fallback_to_fixed(self):
        """When optimize=True but route_service raises, falls back to fixed order."""
        tool = get_tool(MULTISTOP_TOOL)
        params = tool.parameters_schema(stops=["A", "B"], optimize=True)

        mock_route = MagicMock()
        # First call (optimisation) raises
        mock_route.calculate_route.side_effect = [
            RuntimeError("Optimisation unavailable"),
            {"distance_km": 100.0, "duration_min": 60.0, "stops": [[1.0, 1.0], [2.0, 2.0]]},
        ]

        ctx = _make_ctx(services={"route_service": mock_route})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data.get("optimization_status") == "unavailable"

    def test_execute_fallback_to_haversine_legs(self):
        """When graphhopper_response has no legs, falls back to haversine computation."""
        tool = get_tool(MULTISTOP_TOOL)
        params = tool.parameters_schema(stops=["Berlin", "Warsaw"])

        mock_route = MagicMock()
        mock_route.calculate_route.return_value = {
            "distance_km": 572.0,
            "duration_min": 345.0,
            "stops": [[52.52, 13.40], [52.27, 21.00]],
            # No graphhopper_response or no legs — triggers haversine fallback
        }

        ctx = _make_ctx(services={"route_service": mock_route})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert len(result.data["stop_distances"]) == 1
        assert result.data["stop_distances"][0]["distance_km"] > 0

    def test_execute_handles_exception(self):
        tool = get_tool(MULTISTOP_TOOL)
        params = tool.parameters_schema(stops=["A", "B"])

        mock_route = MagicMock()
        mock_route.calculate_route.side_effect = RuntimeError("Routing failed")

        ctx = _make_ctx(services={"route_service": mock_route})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert "Routing failed" in str(result.message_params.get("error", ""))


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestInternalHelpers:
    """Unit tests for private helper functions in route_tools."""

    # -- _haversine_distance --

    def test_haversine_distance_zero(self):
        from backend.copilot.tools.route_tools import _haversine_distance
        d = _haversine_distance(52.52, 13.40, 52.52, 13.40)
        assert d == 0.0

    def test_haversine_distance_berlin_warsaw(self):
        from backend.copilot.tools.route_tools import _haversine_distance
        # Berlin ~52.52,13.40 -> Warsaw ~52.27,21.00 (~515 km)
        d = _haversine_distance(52.52, 13.40, 52.27, 21.00)
        assert 500 < d < 530

    def test_haversine_distance_symmetric(self):
        from backend.copilot.tools.route_tools import _haversine_distance
        d1 = _haversine_distance(0, 0, 10, 10)
        d2 = _haversine_distance(10, 10, 0, 0)
        assert abs(d1 - d2) < 0.001

    # -- _legs_from_graphhopper_response --

    def test_legs_from_empty_response(self):
        from backend.copilot.tools.route_tools import _legs_from_graphhopper_response
        assert _legs_from_graphhopper_response({}) == []

    def test_legs_from_missing_paths(self):
        from backend.copilot.tools.route_tools import _legs_from_graphhopper_response
        assert _legs_from_graphhopper_response({"graphhopper_response": {}}) == []

    def test_legs_from_empty_paths(self):
        from backend.copilot.tools.route_tools import _legs_from_graphhopper_response
        assert _legs_from_graphhopper_response({"graphhopper_response": {"paths": []}}) == []

    def test_legs_from_valid_response(self):
        from backend.copilot.tools.route_tools import _legs_from_graphhopper_response
        result = {
            "graphhopper_response": {
                "paths": [{
                    "legs": [
                        {"distance": 270000, "time": 150 * 60000},
                        {"distance": 302000, "time": 195 * 60000},
                    ],
                }],
            },
        }
        legs = _legs_from_graphhopper_response(result)
        assert len(legs) == 2
        assert abs(legs[0]["distance_km"] - 270.0) < 0.1
        assert abs(legs[0]["duration_min"] - 150.0) < 0.1
        assert abs(legs[1]["distance_km"] - 302.0) < 0.1

    # -- _compute_legs_from_stops --

    def test_compute_legs_less_than_two_stops(self):
        from backend.copilot.tools.route_tools import _compute_legs_from_stops
        assert _compute_legs_from_stops([[1, 1]], 100, 60) == []

    def test_compute_legs_two_stops(self):
        from backend.copilot.tools.route_tools import _compute_legs_from_stops
        legs = _compute_legs_from_stops(
            [[52.52, 13.40], [52.27, 21.00]], 572.0, 345.0,
        )
        assert len(legs) == 1
        assert legs[0]["distance_km"] > 0
        assert legs[0]["duration_min"] > 0

    def test_compute_legs_three_stops(self):
        from backend.copilot.tools.route_tools import _compute_legs_from_stops
        legs = _compute_legs_from_stops(
            [[0, 0], [5, 5], [10, 10]], 2000.0, 600.0,
        )
        assert len(legs) == 2
        # Both legs should have positive duration
        assert all(l["duration_min"] > 0 for l in legs)

    def test_compute_legs_handles_bad_coords(self):
        from backend.copilot.tools.route_tools import _compute_legs_from_stops
        legs = _compute_legs_from_stops(
            [[52.52, 13.40], ["invalid", 21.00]], 500.0, 300.0,
        )
        # Should not crash; invalid coords produce 0 distance
        assert len(legs) == 1

    # -- _build_stop_distances --

    def test_build_stop_distances(self):
        from backend.copilot.tools.route_tools import _build_stop_distances
        stops = ["A", "B", "C"]
        legs = [{"distance_km": 100.0, "duration_min": 60.0}, {"distance_km": 200.0, "duration_min": 120.0}]
        result = _build_stop_distances(stops, legs)
        assert len(result) == 2
        assert result[0]["from_stop"] == "A"
        assert result[0]["to_stop"] == "B"
        assert result[0]["distance_km"] == 100.0
        assert result[1]["from_stop"] == "B"
        assert result[1]["to_stop"] == "C"

    def test_build_stop_distances_fewer_legs(self):
        from backend.copilot.tools.route_tools import _build_stop_distances
        stops = ["A", "B", "C"]
        legs = [{"distance_km": 100.0, "duration_min": 60.0}]  # only 1 leg for 2 stops
        result = _build_stop_distances(stops, legs)
        assert len(result) == 2
        assert result[1]["distance_km"] == 0.0  # legs[i] missing

    # -- _format_stops --

    def test_format_stops_no_resolved_coords(self):
        from backend.copilot.tools.route_tools import _format_stops
        result = _format_stops([], ["A", "B"])
        assert result == ["A", "B"]

    def test_format_stops_with_matching_coords(self):
        from backend.copilot.tools.route_tools import _format_stops
        result = _format_stops([[52.52, 13.40], [52.27, 21.00]], ["Berlin", "Warsaw"])
        assert result == ["Berlin", "Warsaw"]

    def test_format_stops_mismatched_length(self):
        from backend.copilot.tools.route_tools import _format_stops
        # If resolved_coords differs from original_addresses length, use coords string
        result = _format_stops([[52.52, 13.40]], ["A", "B", "C"])
        assert result == ["52.520000,13.400000"]

    # -- _cost_result_to_dict --

    def test_cost_result_to_dict_none(self):
        from backend.copilot.tools.route_tools import _cost_result_to_dict
        assert _cost_result_to_dict(None) == {}

    def test_cost_result_to_dict_with_data(self):
        from backend.copilot.tools.route_tools import _cost_result_to_dict
        op_result = MagicMock()
        op_result.data.breakdown.fuel_cost = 100.0
        op_result.data.breakdown.toll_cost = 20.0
        op_result.data.breakdown.driver_cost = 50.0
        op_result.data.breakdown.total_cost = 170.0
        op_result.data.breakdown.cost_per_km = 0.34
        op_result.data.breakdown.currency = "EUR"
        op_result.data.breakdown.extra_costs = {}
        result = _cost_result_to_dict(op_result)
        assert result["fuel_cost"] == 100.0
        assert result["total_cost"] == 170.0
        assert result["breakdown"]["currency"] == "EUR"

    # -- _build_multistop_data --

    def test_build_multistop_data_with_gh_legs(self):
        from backend.copilot.tools.route_tools import _build_multistop_data
        gh_result = {
            "distance_km": 500.0,
            "duration_min": 300.0,
            "graphhopper_response": {
                "paths": [{
                    "legs": [
                        {"distance": 200000, "time": 120 * 60000},
                        {"distance": 300000, "time": 180 * 60000},
                    ],
                }],
            },
        }
        data = _build_multistop_data(gh_result, ["A", "B", "C"], [[0, 0], [1, 1], [2, 2]])
        assert data["total_distance_km"] == 500.0
        assert len(data["stop_distances"]) == 2

    def test_build_multistop_data_fallback_haversine(self):
        from backend.copilot.tools.route_tools import _build_multistop_data
        gh_result = {
            "distance_km": 500.0,
            "duration_min": 300.0,
            # No graphhopper_response -> GH legs will be empty
        }
        data = _build_multistop_data(gh_result, ["A", "B", "C"], [[0, 0], [1, 1], [2, 2]])
        assert data["total_distance_km"] == 500.0
        assert len(data["stop_distances"]) == 2

    # -- _get_truck_dict --

    def test_get_truck_dict_typed_path_success(self):
        from backend.copilot.tools.route_tools import _get_truck_dict
        mock_fleet = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        truck_data = MagicMock()
        truck_data.model_dump.return_value = {"id": 1, "plate_number": "TRUCK-001"}
        mock_result.data = truck_data
        mock_fleet.get.return_value = mock_result

        result = _get_truck_dict(mock_fleet, 1)
        assert result is not None
        assert result["id"] == 1
        assert result["plate_number"] == "TRUCK-001"

    def test_get_truck_dict_typed_path_failure_fallback(self):
        from backend.copilot.tools.route_tools import _get_truck_dict
        mock_fleet = MagicMock()
        # Typed path fails
        mock_fleet.get.side_effect = RuntimeError("DB error")
        # Fallback path succeeds
        mock_fleet.get_truck.return_value = {"id": 2, "plate_number": "TRUCK-002"}

        result = _get_truck_dict(mock_fleet, 2)
        assert result is not None
        assert result["id"] == 2

    def test_get_truck_dict_both_fail(self):
        from backend.copilot.tools.route_tools import _get_truck_dict
        mock_fleet = MagicMock()
        mock_fleet.get.side_effect = RuntimeError("Error")
        mock_fleet.get_truck.side_effect = RuntimeError("Also error")

        result = _get_truck_dict(mock_fleet, 99)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Cross-tool route domain consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouteDomainConsistency:
    """Consistency across all three route tools."""

    ROUTE_TOOLS = [CALC_TOOL, COST_TOOL, MULTISTOP_TOOL]

    def test_all_have_same_permission(self):
        for name in self.ROUTE_TOOLS:
            assert get_tool(name).required_permission == "routes:read"

    def test_all_are_safe(self):
        for name in self.ROUTE_TOOLS:
            assert get_tool(name).confirmation_level == ConfirmationLevel.SAFE

    def test_none_support_undo(self):
        for name in self.ROUTE_TOOLS:
            assert not get_tool(name).supports_undo

    def test_none_are_deprecated(self):
        for name in self.ROUTE_TOOLS:
            assert not get_tool(name).deprecated

    def test_all_have_semver(self):
        for name in self.ROUTE_TOOLS:
            parts = get_tool(name).tool_version.split(".")
            assert len(parts) == 3 and all(p.isdigit() for p in parts)
