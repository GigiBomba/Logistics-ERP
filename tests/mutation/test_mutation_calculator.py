from __future__ import annotations

import pytest

from services.calculator import TripCalculator

pytestmark = pytest.mark.mutation


class TestKillMutationCalculator:
    """Mutation-killing tests for TripCalculator.calculate()."""

    def test_sal_in_zero_uses_default_salary(self):
        """Kill: sal_in > 0 -> >= 0 mutation (sal_in=0 should use default, not 0)."""
        result = TripCalculator.calculate(
            km=1000, price_eur=3000, fuel_price=1.50,
            days=3, consum_litri=30, sal_in=0,
        )
        # 0 > 0 is False -> days * 100.0 = 300.0
        # 0 >= 0 is True  -> salary_cost = 0 (WRONG)
        assert result.salary_cost == 300.0

    def test_taxa_in_zero_uses_default_toll(self):
        """Kill: taxa_in > 0 -> >= 0 mutation (taxa_in=0 should use default, not 0)."""
        result = TripCalculator.calculate(
            km=500, price_eur=1500, fuel_price=1.50,
            days=1, consum_litri=30, taxa_in=0,
        )
        # 0 > 0 is False -> km * 0.22 = 110.0
        # 0 >= 0 is True -> toll_cost = 0 (WRONG)
        assert result.toll_cost == 110.0

    def test_extra_in_zero_used_as_is(self):
        """Kill: extra_in is not None -> is None mutation (extra_in=0 should be used as-is)."""
        result = TripCalculator.calculate(
            km=1000, price_eur=3000, fuel_price=1.50,
            days=3, consum_litri=30, extra_in=0,
        )
        # 0 is not None is True  -> extra_costs = 0
        # 0 is None is False     -> falls to default formula (WRONG)
        assert result.extra_costs == 0.0

    def test_extra_in_none_uses_default_formula(self):
        """Kill: extra_in=None branch verification (default formula used)."""
        result = TripCalculator.calculate(
            km=1000, price_eur=3000, fuel_price=1.50,
            days=3, consum_litri=30, extra_in=None,
        )
        expected = round(1000 * 0.03 + 3 * 12.0, 2)  # 30 + 36 = 66.0
        assert result.extra_costs == expected

    def test_fuel_override_zero_does_not_override(self):
        """Kill: fuel_cost_override > 0 -> >= 0 mutation (0 should NOT override)."""
        result = TripCalculator.calculate(
            km=1000, price_eur=3000, fuel_price=1.50,
            days=1, consum_litri=30, fuel_cost_override=0,
        )
        expected_fuel = (1000 / 100) * 30 * 1.50  # 450.0
        # 0 > 0 is False -> calculated = 450.0
        # 0 >= 0 is True -> fuel_cost = 0 (WRONG)
        assert result.fuel_cost == pytest.approx(expected_fuel, abs=0.01)

    def test_km_zero_does_not_divide_by_zero(self):
        """Kill: km > 0 -> >= 0 mutation (km=0 should give rate_per_km=0, not ZeroDivisionError)."""
        result = TripCalculator.calculate(
            km=0, price_eur=1000, fuel_price=1.50,
            days=1, consum_litri=30,
        )
        # 0 > 0 is False -> rate_net_km = 0
        # 0 >= 0 is True -> net_profit / 0 -> ZeroDivisionError (WRONG)
        assert result.rate_per_km == 0.0
        assert result.gross_per_km == 0.0

    def test_price_zero_does_not_divide_by_zero(self):
        """Kill: price_eur > 0 -> >= 0 mutation (price=0 should give margin=0, not ZeroDivisionError)."""
        result = TripCalculator.calculate(
            km=500, price_eur=0, fuel_price=1.50,
            days=1, consum_litri=30,
        )
        # 0 > 0 is False -> margin = 0
        # 0 >= 0 is True -> net_profit / 0 -> ZeroDivisionError (WRONG)
        assert result.margin_percent == 0.0

    def test_extra_cost_constant_formula_verification(self):
        """Kill: constant change — EXTRA_COST_PER_KM formula is verified explicitly.

        If Config.EXTRA_COST_PER_KM or Config.EXTRA_COST_PER_DAY changes, this
        test fails, alerting to unintended constant drift.
        """
        km, days = 1000, 3
        result = TripCalculator.calculate(
            km=km, price_eur=3000, fuel_price=1.50,
            days=days, consum_litri=30,
        )
        # Explicit formula with current constants: 0.03/km + 12.0/day
        expected_extra = round(km * 0.03 + days * 12.0, 2)
        assert result.extra_costs == expected_extra
