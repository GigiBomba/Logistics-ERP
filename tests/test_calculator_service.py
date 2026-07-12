"""Comprehensive unit tests for the TripCalculator service layer.

This tests the pure business logic in ``services/calculator.py``,
*not* the Qt view (which is tested in ``test_calculator_view.py``).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from services.calculator import TripCalculator, TripResult


# ──────────────────────────────────────────────────────────────
# Basic Happy Path
# ──────────────────────────────────────────────────────────────

class TestCalculatorService:
    """Test suite for TripCalculator (service-layer business logic)."""

    def test_basic_calculation_returns_tripresult(self):
        """A standard calculation returns a properly typed TripResult."""
        result = TripCalculator.calculate_raw(
            km=1000, price_eur=2000, fuel_price=1.50,
            days=3, consum_litri=30,
        )
        assert isinstance(result, TripResult)
        assert isinstance(result.net_profit, float)
        assert isinstance(result.fuel_cost, float)
        assert isinstance(result.toll_cost, float)
        assert isinstance(result.salary_cost, float)
        assert isinstance(result.extra_costs, float)
        assert isinstance(result.rate_per_km, float)
        assert isinstance(result.gross_per_km, float)
        assert isinstance(result.margin_percent, float)

    # ──────────────────────────────────────────────────────────
    # Cost calculation: fuel
    # ──────────────────────────────────────────────────────────

    def test_fuel_cost_calculation(self):
        """Fuel cost = (km / 100) * consumption * fuel_price."""
        km, consum, fuel_price = 1000, 30, 1.50
        expected_fuel = (km / 100) * consum * fuel_price  # 300 * 1.50 = 450.0
        result = TripCalculator.calculate_raw(
            km=km, price_eur=3000, fuel_price=fuel_price,
            days=1, consum_litri=consum,
        )
        assert result.fuel_cost == pytest.approx(expected_fuel, abs=0.01)

    def test_fuel_cost_zero_consumption(self):
        """Zero fuel consumption yields zero fuel cost."""
        result = TripCalculator.calculate_raw(
            km=500, price_eur=1000, fuel_price=1.50,
            days=1, consum_litri=0,
        )
        assert result.fuel_cost == 0.0

    def test_fuel_cost_override(self):
        """fuel_cost_override takes precedence over calculated fuel."""
        result = TripCalculator.calculate_raw(
            km=1000, price_eur=2000, fuel_price=1.50,
            days=1, consum_litri=30,
            fuel_cost_override=500.0,
        )
        assert result.fuel_cost == 500.0

    def test_fuel_cost_override_zero_ignored(self):
        """fuel_cost_override = 0 is ignored; calculated value is used."""
        result = TripCalculator.calculate_raw(
            km=1000, price_eur=2000, fuel_price=1.50,
            days=1, consum_litri=30,
            fuel_cost_override=0,
        )
        # Expected: (1000/100) * 30 * 1.50 = 450.0
        assert result.fuel_cost == pytest.approx(450.0, abs=0.01)

    # ──────────────────────────────────────────────────────────
    # Cost calculation: toll
    # ──────────────────────────────────────────────────────────

    def test_toll_cost_default(self):
        """Default toll = km * Config.DEFAULT_TOLL_RATE (0.22)."""
        km = 500
        expected_toll = km * 0.22  # 110.0
        result = TripCalculator.calculate_raw(
            km=km, price_eur=1500, fuel_price=1.50,
            days=1, consum_litri=30,
        )
        assert result.toll_cost == pytest.approx(expected_toll, abs=0.01)

    def test_toll_cost_override(self):
        """Explicit toll overrides the auto-calculated toll."""
        result = TripCalculator.calculate_raw(
            km=500, price_eur=1500, fuel_price=1.50,
            days=1, consum_litri=30,
            taxa_in=200.0,
        )
        assert result.toll_cost == 200.0

    # ──────────────────────────────────────────────────────────
    # Cost calculation: salary
    # ──────────────────────────────────────────────────────────

    def test_salary_cost_default(self):
        """Default salary = days * Config.DEFAULT_DRIVER_SALARY (100)."""
        days = 4
        expected_salary = days * 100.0  # 400.0
        result = TripCalculator.calculate_raw(
            km=500, price_eur=2000, fuel_price=1.50,
            days=days, consum_litri=30,
        )
        assert result.salary_cost == pytest.approx(expected_salary, abs=0.01)

    def test_salary_cost_override(self):
        """Explicit salary overrides auto-calculated default."""
        result = TripCalculator.calculate_raw(
            km=500, price_eur=2000, fuel_price=1.50,
            days=4, consum_litri=30,
            sal_in=350.0,
        )
        assert result.salary_cost == 350.0

    def test_salary_cost_zero_days(self):
        """Zero days with default salary gives zero salary cost."""
        result = TripCalculator.calculate_raw(
            km=500, price_eur=2000, fuel_price=1.50,
            days=0, consum_litri=30,
        )
        assert result.salary_cost == 0.0

    # ──────────────────────────────────────────────────────────
    # Cost calculation: extra costs
    # ──────────────────────────────────────────────────────────

    def test_extra_costs_default(self):
        """Default extra = km*0.03 + days*12, rounded to 2dp."""
        km, days = 1000, 3
        expected = round(km * 0.03 + days * 12.0, 2)  # 30 + 36 = 66.0
        result = TripCalculator.calculate_raw(
            km=km, price_eur=3000, fuel_price=1.50,
            days=days, consum_litri=30,
        )
        assert result.extra_costs == expected

    def test_extra_costs_override(self):
        """Explicit extra costs override the auto-calculated value."""
        result = TripCalculator.calculate_raw(
            km=1000, price_eur=3000, fuel_price=1.50,
            days=3, consum_litri=30,
            extra_in=50.0,
        )
        assert result.extra_costs == 50.0

    def test_extra_costs_zero_override(self):
        """extra_in = 0 is accepted (zero extra costs)."""
        result = TripCalculator.calculate_raw(
            km=1000, price_eur=3000, fuel_price=1.50,
            days=3, consum_litri=30,
            extra_in=0.0,
        )
        assert result.extra_costs == 0.0

    # ──────────────────────────────────────────────────────────
    # Profit calculation
    # ──────────────────────────────────────────────────────────

    def test_net_profit(self):
        """net_profit = price_eur - (fuel + toll + salary + extra)."""
        # Manually compute expected values
        km, price, fuel_price, days, consum = 1000, 3000, 1.50, 2, 30
        fuel = (km / 100) * consum * fuel_price          # 450.0
        toll = km * 0.22                                  # 220.0
        salary = days * 100.0                             # 200.0
        extra = round(km * 0.03 + days * 12.0, 2)        # 30 + 24 = 54.0
        total_costs = fuel + toll + salary + extra        # 924.0
        expected_profit = round(price - total_costs, 2)   # 2076.0

        result = TripCalculator.calculate_raw(
            km=km, price_eur=price, fuel_price=fuel_price,
            days=days, consum_litri=consum,
        )
        assert result.net_profit == expected_profit

    def test_net_profit_negative(self):
        """When costs exceed revenue, net_profit is negative."""
        result = TripCalculator.calculate_raw(
            km=1000, price_eur=100, fuel_price=2.0,
            days=5, consum_litri=40,
        )
        assert result.net_profit < 0

    def test_profit_margin_percent(self):
        """margin_percent = (net_profit / price_eur) * 100."""
        km, price, fuel_price, days, consum = 500, 1500, 1.40, 1, 28
        fuel = (km / 100) * consum * fuel_price           # 196.0
        toll = km * 0.22                                   # 110.0
        salary = days * 100.0                              # 100.0
        extra = round(km * 0.03 + days * 12.0, 2)         # 15 + 12 = 27.0
        total_costs = fuel + toll + salary + extra         # 433.0
        net_profit = round(price - total_costs, 2)         # 1067.0
        expected_margin = round((net_profit / price) * 100, 1)  # 71.1

        result = TripCalculator.calculate_raw(
            km=km, price_eur=price, fuel_price=fuel_price,
            days=days, consum_litri=consum,
        )
        assert result.margin_percent == expected_margin

    # ──────────────────────────────────────────────────────────
    # Rate per km & gross per km
    # ──────────────────────────────────────────────────────────

    @pytest.mark.parametrize("km,price,fuel_price,days,consum", [
        (1000, 2000, 1.50, 2, 30),
        (500, 1500, 1.40, 1, 28),
        (200, 800, 1.60, 1, 32),
    ])
    def test_rate_per_km(self, km, price, fuel_price, days, consum):
        """rate_per_km = net_profit / km."""
        result = TripCalculator.calculate_raw(
            km=km, price_eur=price, fuel_price=fuel_price,
            days=days, consum_litri=consum,
        )
        expected_rate = round(result.net_profit / km, 2)
        assert result.rate_per_km == expected_rate

    @pytest.mark.parametrize("km,price", [
        (1000, 2000),
        (500, 1500),
        (200, 800),
    ])
    def test_gross_per_km(self, km, price):
        """gross_per_km = price_eur / km."""
        result = TripCalculator.calculate_raw(
            km=km, price_eur=price, fuel_price=1.50,
            days=1, consum_litri=30,
        )
        expected_gross = round(price / km, 2)
        assert result.gross_per_km == expected_gross

    # ──────────────────────────────────────────────────────────
    # Edge cases
    # ──────────────────────────────────────────────────────────

    def test_zero_distance(self):
        """Zero distance: rate_per_km and gross_per_km are 0 (no div-by-zero)."""
        result = TripCalculator.calculate_raw(
            km=0, price_eur=1000, fuel_price=1.50,
            days=1, consum_litri=30,
        )
        assert result.net_profit is not None
        assert result.rate_per_km == 0.0
        assert result.gross_per_km == 0.0

    def test_zero_price(self):
        """Zero revenue: margin_percent is 0 (no div-by-zero)."""
        result = TripCalculator.calculate_raw(
            km=500, price_eur=0, fuel_price=1.50,
            days=1, consum_litri=30,
        )
        assert result.margin_percent == 0.0
        assert result.net_profit < 0  # costs exceed zero revenue

    @pytest.mark.parametrize("km,price,fuel_price,days,consum", [
        (10_000, 50_000, 2.0, 30, 33),
        (100, 10_000, 0.80, 1, 20),
    ])
    def test_large_numbers(self, km, price, fuel_price, days, consum):
        """Large distances and prices should not overflow or produce NaN."""
        result = TripCalculator.calculate_raw(
            km=km, price_eur=price, fuel_price=fuel_price,
            days=days, consum_litri=consum,
        )
        assert result.fuel_cost >= 0
        assert not (result.net_profit != result.net_profit)  # not NaN
        assert result.margin_percent != float("inf")

    def test_very_large_inputs_produce_finite_values(self):
        """Stress test with very large values to ensure stability."""
        result = TripCalculator.calculate_raw(
            km=1_000_000, price_eur=5_000_000, fuel_price=9.99,
            days=365, consum_litri=50,
        )
        assert all(
            getattr(result, field) != float("inf")
            and not (getattr(result, field) != getattr(result, field))  # not NaN
            for field in TripResult.__dataclass_fields__
        )

    # ──────────────────────────────────────────────────────────
    # Rounding
    # ──────────────────────────────────────────────────────────

    @pytest.mark.parametrize("field", [
        "net_profit", "fuel_cost", "toll_cost",
        "salary_cost", "extra_costs", "rate_per_km", "gross_per_km",
    ])
    def test_financial_fields_rounded_to_two_decimals(self, field):
        """Financial fields are always rounded to 2 decimal places."""
        result = TripCalculator.calculate_raw(
            km=333, price_eur=1999.99, fuel_price=1.559,
            days=2, consum_litri=30,
        )
        value = getattr(result, field)
        # Round-trip through string formatting to check decimal places
        formatted = f"{value:.2f}"
        assert float(formatted) == value, (
            f"{field}={value} has more than 2 decimal places"
        )

    def test_margin_percent_rounded_to_one_decimal(self):
        """margin_percent is rounded to 1 decimal place."""
        result = TripCalculator.calculate_raw(
            km=333, price_eur=1999.99, fuel_price=1.559,
            days=2, consum_litri=30,
        )
        formatted = f"{result.margin_percent:.1f}"
        assert float(formatted) == result.margin_percent

    # ──────────────────────────────────────────────────────────
    # All-parameters-override (full manual control)
    # ──────────────────────────────────────────────────────────

    def test_all_overrides(self):
        """When all overrides are provided, defaults are skipped."""
        result = TripCalculator.calculate_raw(
            km=1000, price_eur=5000, fuel_price=1.50,
            days=5, consum_litri=30,
            extra_in=100.0,
            sal_in=600.0,
            taxa_in=250.0,
            fuel_cost_override=400.0,
        )
        assert result.fuel_cost == 400.0
        assert result.toll_cost == 250.0
        assert result.salary_cost == 600.0
        assert result.extra_costs == 100.0
        # Total costs = 400 + 250 + 600 + 100 = 1350
        # Net profit = 5000 - 1350 = 3650
        assert result.net_profit == 3650.0

    # ──────────────────────────────────────────────────────────
    # Varied / random-like scenarios
    # ──────────────────────────────────────────────────────────

    @pytest.mark.parametrize("km,price,fuel_price,days,consum,exp_fuel,exp_toll,exp_salary,exp_extra", [
        # No overrides — all defaults
        (1000, 3000, 1.50, 2, 30, 450.0, 220.0, 200.0, round(1000*0.03+2*12.0, 2)),
        # Short trip, low consumption
        (150, 400, 1.60, 1, 25, round(1.5*25*1.6, 2), 33.0, 100.0, round(150*0.03+1*12.0, 2)),
        # Long trip, high consumption, expensive fuel
        (2500, 8000, 1.80, 5, 35, round(25*35*1.8, 2), 550.0, 500.0, round(2500*0.03+5*12.0, 2)),
    ])
    def test_varied_scenarios(self, km, price, fuel_price, days, consum,
                              exp_fuel, exp_toll, exp_salary, exp_extra):
        """Multiple plausible trip configurations produce correct costs."""
        result = TripCalculator.calculate_raw(
            km=km, price_eur=price, fuel_price=fuel_price,
            days=days, consum_litri=consum,
        )
        assert result.fuel_cost == pytest.approx(exp_fuel, abs=0.01)
        assert result.toll_cost == pytest.approx(exp_toll, abs=0.01)
        assert result.salary_cost == pytest.approx(exp_salary, abs=0.01)
        assert result.extra_costs == pytest.approx(exp_extra, abs=0.01)

    # ── Smoke tests: backward-compat raw API ──────────────────

    def test_calculate_raw_static_method(self):
        """TripCalculator.calculate_raw can be called as a static method."""
        result = TripCalculator.calculate_raw(
            km=1, price_eur=10, fuel_price=1.0,
            days=1, consum_litri=10,
        )
        assert isinstance(result, TripResult)

    def test_calculate_raw_via_instance(self):
        """TripCalculator().calculate_raw also works."""
        calc = TripCalculator()
        result = calc.calculate_raw(
            km=1, price_eur=10, fuel_price=1.0,
            days=1, consum_litri=10,
        )
        assert isinstance(result, TripResult)

    # ── Smoke tests: typed Pydantic API ─────────────────────

    def test_calculate_typed_returns_operation_result(self):
        """TripCalculator().calculate returns CalculationOperationResult."""
        from models.calculator_models import CalculationRequest

        calc = TripCalculator()
        request = CalculationRequest(
            km=100, price_eur=500, fuel_price=1.50,
            days=1, consum_litri=30,
        )
        result = calc.calculate(request)
        assert result.success is True
        assert result.data is not None

    def test_calculate_typed_result_fields(self):
        """Typed calculate returns all expected fields."""
        from models.calculator_models import CalculationRequest

        calc = TripCalculator()
        request = CalculationRequest(
            km=1000, price_eur=3000, fuel_price=1.50,
            days=2, consum_litri=30,
        )
        result = calc.calculate(request)
        assert result.success is True
        data = result.data
        assert data.km == 1000.0
        assert data.total_income == 3000.0
        assert data.fuel_consumed_liters == pytest.approx(300.0, abs=0.01)
        assert data.fuel_cost == pytest.approx(450.0, abs=0.01)
        assert data.net_profit is not None
        assert data.profit_per_km is not None
        assert data.margin_percent is not None
        assert data.cost_per_km is not None
        assert data.currency == "EUR"
