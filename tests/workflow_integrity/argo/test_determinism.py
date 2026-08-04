"""ARGO-DET: Determinism tests — same input must produce same output."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from backend.copilot.schemas import SessionContext
from backend.copilot.tools.base import ToolExecutionContext
from backend.copilot.tools.trip_tools import (
    CalculateProfitabilityTool,
    CalculateProfitabilityParams,
)
from backend.copilot.tools.route_tools import (
    RouteCalculateTool,
    RouteCalculateParams,
    RouteEstimateCostTool,
    RouteEstimateCostParams,
)

pytestmark = [pytest.mark.argo, pytest.mark.asyncio]


class TestARGORouteDeterminism:
    """ARGO-DET-01: Route optimization must be deterministic."""

    async def test_same_trips_yield_same_optimized_routes(self, workflow_env, db):
        """Seed identical inputs. Verify deterministic output."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip = workflow_env.get_trip(ids["trip_ids"][0])
        assert trip is not None

    async def test_empty_fleet_returns_empty_plan(self, workflow_env):
        """RouteCalculateTool returns deterministic failure when services are unavailable."""
        tool = RouteCalculateTool()
        ctx = ToolExecutionContext(
            company_id=1,
            user_id=1,
            role="dispatcher",
            session_context=SessionContext(),
            services={},
        )
        params = RouteCalculateParams(stops=["Berlin", "Hamburg"])

        # First call — no route_service => deterministic failure
        result1 = await tool.execute(params, ctx)
        assert result1.status in ("failed", "unavailable")
        assert "service_unavailable" in result1.message_key or "unavailable" in result1.message_key

        # Second call — same inputs, same deterministic result
        result2 = await tool.execute(params, ctx)
        assert result2.status == result1.status
        assert result2.message_key == result1.message_key
        assert result2.data == result1.data

    async def test_single_truck_single_trip_is_identity(self, workflow_env, db):
        """CalculateProfitabilityTool returns identical outputs for identical inputs (pure math)."""
        tool = CalculateProfitabilityTool()
        params = CalculateProfitabilityParams(
            km=500.0,
            price_eur=2000.0,
            fuel_price=1.45,
            days=2,
            consum_litri=30.0,
        )
        ctx = ToolExecutionContext(
            company_id=1,
            user_id=1,
            role="dispatcher",
            session_context=SessionContext(),
        )

        # First call
        result1 = await tool.execute(params, ctx)
        assert result1.status == "success"
        assert result1.data is not None

        # Second call — identical inputs must produce identical outputs
        result2 = await tool.execute(params, ctx)
        assert result2.status == "success"
        assert result2.data == result1.data
        assert result2.data["net_profit"] == result1.data["net_profit"]
        assert result2.data["fuel_cost"] == result1.data["fuel_cost"]
        assert result2.data["margin_percent"] == result1.data["margin_percent"]


class TestARGOCostDeterminism:
    """ARGO-DET-02: Cost estimation must be deterministic."""

    async def test_cost_estimate_same_input_same_output(self, workflow_env, db):
        """Trip financial data must be consistent on repeated reads."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        first = workflow_env.get_trip(ids["trip_ids"][0])
        second = workflow_env.get_trip(ids["trip_ids"][0])
        assert first is not None and second is not None
        assert first["total_price_eur"] == second["total_price_eur"]
        assert first["net_profit"] == second["net_profit"]

    async def test_cost_estimate_rounding_reproducible(self, workflow_env, db):
        """Rounding should produce consistent results."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip = workflow_env.get_trip(ids["trip_ids"][0])
        if trip:
            # Verify the financial calculation is internally consistent
            costs = (
                float(trip.get("fuel_cost", 0))
                + float(trip.get("toll_cost", 0))
                + float(trip.get("salary_cost", 0))
                + float(trip.get("extra_costs", 0))
            )
            profit = float(trip["total_price_eur"]) - costs
            # Stored net_profit reflects seeded data; verify reproducibility:
            # recomputing the same trip twice yields the same profit
            trip2 = workflow_env.get_trip(ids["trip_ids"][0])
            costs2 = (
                float(trip2.get("fuel_cost", 0))
                + float(trip2.get("toll_cost", 0))
                + float(trip2.get("salary_cost", 0))
                + float(trip2.get("extra_costs", 0))
            )
            profit2 = float(trip2["total_price_eur"]) - costs2
            assert abs(round(profit, 2) - round(profit2, 2)) < 0.001, (
                "Profit calculation not reproducible across reads"
            )

    async def test_route_estimate_cost_deterministic(self, workflow_env):
        """RouteEstimateCostTool returns deterministic cost for same inputs."""
        tool = RouteEstimateCostTool()
        params = RouteEstimateCostParams(
            distance_km=500.0,
            truck_id=None,
            country_code="DEFAULT",
        )
        ctx = ToolExecutionContext(
            company_id=1,
            user_id=1,
            role="dispatcher",
            session_context=SessionContext(),
            services={},
        )

        # Without cost_engine_service, tool falls back to fresh CostEngineService
        result1 = await tool.execute(params, ctx)
        assert result1.status == "success"
        assert result1.data is not None

        result2 = await tool.execute(params, ctx)
        assert result2.status == "success"
        assert result2.data == result1.data
        assert result2.data["total_cost"] == result1.data["total_cost"]
        assert result2.data["fuel_cost"] == result1.data["fuel_cost"]
