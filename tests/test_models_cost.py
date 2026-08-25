"""Tests for cost_models.py — Cost breakdown, per-km calculations, currency conversion fields."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from models.cost_models import (
    CostEstimateRequest,
    CostBreakdown,
    CostEstimateResult,
)


class TestCostEstimateRequest:
    @pytest.mark.parametrize(
        "distance_km, fuel_type, consumption, fuel_price, toll, driver_rate, days, currency",
        [
            (150.0, "diesel", 33.5, 1.45, 25.0, 200.0, 1.0, "EUR"),
            (500.0, "diesel", 30.0, 1.50, 0.0, 250.0, 2.0, "RON"),
            (100.0, "electric", 20.0, 0.30, 10.0, 0.0, 0.5, "EUR"),
            (1000.0, "diesel", None, None, 50.0, 300.0, 3.0, "USD"),
            (1.0, "diesel", 25.0, 1.55, 0.0, 0.0, 1.0, "EUR"),
        ],
    )
    def test_cost_estimate_valid(self, distance_km, fuel_type, consumption, fuel_price, toll, driver_rate, days, currency):
        req = CostEstimateRequest(
            distance_km=distance_km,
            fuel_type=fuel_type,
            consumption_l_per_100km=consumption,
            fuel_price_per_liter=fuel_price,
            toll_cost_eur=toll,
            driver_daily_rate=driver_rate,
            days=days,
            currency=currency,
        )
        assert req.distance_km == distance_km
        assert req.fuel_type == fuel_type
        assert req.currency == currency

    @pytest.mark.parametrize("distance", [0, -1, -100.5])
    def test_distance_non_positive_raises(self, distance):
        with pytest.raises(ValidationError, match="Distance must be positive"):
            CostEstimateRequest(distance_km=distance)

    def test_cost_estimate_defaults(self):
        req = CostEstimateRequest(distance_km=100.0)
        assert req.fuel_type == "diesel"
        assert req.toll_cost_eur == 0.0
        assert req.driver_daily_rate == 0.0
        assert req.days == 1.0
        assert req.extra_costs == {}
        assert req.currency == "EUR"
        assert req.truck_id is None
        assert req.consumption_l_per_100km is None
        assert req.fuel_price_per_liter is None

    def test_cost_estimate_with_extra_costs(self):
        req = CostEstimateRequest(
            distance_km=200.0,
            extra_costs={"parking": 50.0, "ferry": 120.0},
            truck_id=5,
        )
        assert req.extra_costs["parking"] == 50.0
        assert len(req.extra_costs) == 2
        assert req.truck_id == 5

    def test_cost_estimate_with_truck_id(self):
        req = CostEstimateRequest(distance_km=300.0, truck_id=10)
        assert req.truck_id == 10


class TestCostBreakdown:
    def test_cost_breakdown_valid(self):
        b = CostBreakdown(
            fuel_cost=145.35,
            toll_cost=25.0,
            driver_cost=200.0,
            extra_costs={"parking": 15.0},
            total_cost=385.35,
            cost_per_km=2.57,
            currency="EUR",
        )
        assert b.fuel_cost == 145.35
        assert b.total_cost == 385.35
        assert b.cost_per_km == 2.57

    def test_cost_breakdown_empty_extras(self):
        b = CostBreakdown(
            fuel_cost=0,
            toll_cost=0,
            driver_cost=0,
            total_cost=0,
            cost_per_km=0,
            currency="EUR",
        )
        assert b.extra_costs == {}

    @pytest.mark.parametrize("cost_per_km, total_cost", [(0.0, 0.0), (1.5, 150.0), (10.75, 1075.0)])
    def test_cost_breakdown_parametrize(self, cost_per_km, total_cost):
        b = CostBreakdown(
            fuel_cost=50,
            toll_cost=10,
            driver_cost=100,
            total_cost=total_cost,
            cost_per_km=cost_per_km,
            currency="EUR",
        )
        assert b.cost_per_km == cost_per_km
        assert b.total_cost == total_cost


class TestCostEstimateResult:
    def test_cost_estimate_result(self):
        breakdown = CostBreakdown(
            fuel_cost=100.0,
            toll_cost=20.0,
            driver_cost=200.0,
            total_cost=320.0,
            cost_per_km=1.6,
            currency="EUR",
        )
        r = CostEstimateResult(
            distance_km=200.0,
            days=1.0,
            breakdown=breakdown,
            truck_info="Volvo FH - AB123CD",
        )
        assert r.distance_km == 200.0
        assert r.breakdown.total_cost == 320.0
        assert r.truck_info == "Volvo FH - AB123CD"

    def test_cost_estimate_result_default_truck_info(self):
        breakdown = CostBreakdown(
            fuel_cost=0, toll_cost=0, driver_cost=0,
            total_cost=0, cost_per_km=0, currency="EUR",
        )
        r = CostEstimateResult(distance_km=100.0, days=1.0, breakdown=breakdown)
        assert r.truck_info == ""
