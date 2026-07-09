from __future__ import annotations

import pytest

from config import Config
from services.cost_engine import CostEngineService

pytestmark = pytest.mark.mutation


class TestKillMutationCostEngine:
    """Mutation-killing tests for CostEngineService.estimate()."""

    def test_none_distance_returns_all_zeros(self):
        """Kill: distance_km is None guard removal (None -> all zeros)."""
        engine = CostEngineService(fuel_price_eur_per_liter=1.50)
        result = engine.estimate(distance_km=None, truck={})
        assert result == {
            'fuel_liters': 0.0,
            'fuel_cost': 0.0,
            'toll_cost': 0.0,
            'total_cost': 0.0,
        }

    def test_empty_truck_uses_default_consumption(self):
        """Kill: consumption fallback 'or 34.0' removal (empty dict -> 34.0)."""
        engine = CostEngineService(fuel_price_eur_per_liter=1.50)
        result = engine.estimate(distance_km=100.0, truck={})
        # (100 / 100) * 34.0 * 1.50 = 51.0 fuel cost
        assert result['fuel_liters'] == 34.0
        assert result['fuel_cost'] == 51.0

    def test_consumption_key_priority(self):
        """Kill: fuel_consumption_l_per_100km takes priority over fuel_consumption."""
        engine = CostEngineService(fuel_price_eur_per_liter=1.50)
        truck = {
            'fuel_consumption_l_per_100km': 30.0,
            'fuel_consumption': 35.0,
        }
        result = engine.estimate(distance_km=100.0, truck=truck)
        # Uses 30.0 (not 35.0): (100/100) * 30.0 = 30.0 liters
        assert result['fuel_liters'] == 30.0

    def test_unknown_country_uses_default_factor(self):
        """Kill: unknown country uses DEFAULT factor, not KeyError."""
        engine = CostEngineService(fuel_price_eur_per_liter=1.50)
        result = engine.estimate(
            distance_km=100.0,
            truck={'fuel_consumption_l_per_100km': 30.0},
            country_code='ZZ',
        )
        # DEFAULT factor = 1.0
        toll_expected = 100.0 * Config.DEFAULT_TOLL_RATE * 1.0 * 0.5
        assert result['toll_cost'] == pytest.approx(toll_expected, abs=0.01)

    def test_no_route_details_uses_default_road_factor(self):
        """Kill: no route_details -> default road_factor 0.5."""
        engine = CostEngineService(fuel_price_eur_per_liter=1.50)
        result = engine.estimate(
            distance_km=100.0,
            truck={'fuel_consumption_l_per_100km': 30.0},
            route_details=None,
        )
        # road_factor = 0.5 (default)
        toll_expected = 100.0 * Config.DEFAULT_TOLL_RATE * 1.0 * 0.5
        assert result['toll_cost'] == pytest.approx(toll_expected, abs=0.01)

    def test_results_are_rounded_to_two_decimals(self):
        """Kill: rounding removal (results should be rounded to 2 decimals)."""
        engine = CostEngineService(fuel_price_eur_per_liter=1.50)
        result = engine.estimate(
            distance_km=333.0,
            truck={'fuel_consumption_l_per_100km': 33.0},
        )
        for key in ('fuel_liters', 'fuel_cost', 'toll_cost', 'total_cost'):
            value = result[key]
            formatted = f"{value:.2f}"
            assert float(formatted) == value, (
                f"{key}={value} has more than 2 decimal places"
            )

    def test_default_toll_rate_constant_used(self):
        """Kill: Config.DEFAULT_TOLL_RATE usage verification.

        If the constant is replaced with an inline literal, changing the
        config constant won't affect the calculation.
        """
        engine = CostEngineService(fuel_price_eur_per_liter=1.50)
        result = engine.estimate(
            distance_km=200.0,
            truck={'fuel_consumption_l_per_100km': 30.0},
            country_code='RO',
        )
        # toll = 200.0 * Config.DEFAULT_TOLL_RATE * 1.0 * 0.5
        expected = 200.0 * Config.DEFAULT_TOLL_RATE * 1.0 * 0.5
        assert result['toll_cost'] == pytest.approx(expected, abs=0.01)

    def test_negative_distance_handling(self):
        """Kill: negative distance does not crash and produces negative costs."""
        engine = CostEngineService(fuel_price_eur_per_liter=1.50)
        result = engine.estimate(
            distance_km=-100.0,
            truck={'fuel_consumption_l_per_100km': 30.0},
        )
        # Negative distance -> negative fuel/toll/total
        assert result['fuel_liters'] == pytest.approx(-30.0, abs=0.01)
        assert result['fuel_cost'] < 0
        assert result['toll_cost'] < 0
        assert result['total_cost'] < 0
