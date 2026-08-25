"""Tests for calculator_models.py — CalculationRequest, TripCalculationResult."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from models.calculator_models import CalculationRequest, TripCalculationResult


class TestCalculationRequest:
    """Valid construction, field validators, boundary values, negative rejection."""

    @pytest.mark.parametrize(
        "km, price_eur, fuel_price, days, consum_litri",
        [
            (1000.0, 2000.0, 1.50, 3.0, 30.0),
            (0.001, 0.0, 0.001, 1.0, 0.001),
            (1.0, 100.0, 2.0, 1.0, 10.0),
            (500.0, 0.0, 1.80, 5.0, 25.5),
            (10_000.0, 50_000.0, 0.50, 14.0, 40.0),
        ],
    )
    def test_valid_construction(self, km, price_eur, fuel_price, days, consum_litri):
        """All valid combinations pass validation."""
        r = CalculationRequest(
            km=km,
            price_eur=price_eur,
            fuel_price=fuel_price,
            days=days,
            consum_litri=consum_litri,
        )
        assert r.km == km
        assert r.price_eur == price_eur
        assert r.fuel_price == fuel_price
        assert r.days == days
        assert r.consum_litri == consum_litri

    def test_default_days(self):
        """days defaults to 1.0 when omitted."""
        r = CalculationRequest(
            km=100.0,
            price_eur=500.0,
            fuel_price=1.50,
            consum_litri=30.0,
        )
        assert r.days == 1.0

    def test_default_sal_in_and_taxa_in(self):
        """sal_in and taxa_in default to 0.0."""
        r = CalculationRequest(
            km=100.0,
            price_eur=500.0,
            fuel_price=1.50,
            consum_litri=30.0,
        )
        assert r.sal_in == 0.0
        assert r.taxa_in == 0.0

    def test_optional_extra_in_and_fuel_cost_override(self):
        """extra_in and fuel_cost_override default to None."""
        r = CalculationRequest(
            km=100.0,
            price_eur=500.0,
            fuel_price=1.50,
            consum_litri=30.0,
        )
        assert r.extra_in is None
        assert r.fuel_cost_override is None

    @pytest.mark.parametrize(
        "km",
        [0.0, -0.001, -1.0, -1000.0],
    )
    def test_km_must_be_positive(self, km):
        """km <= 0 raises ValidationError."""
        with pytest.raises(ValidationError, match="Distance"):
            CalculationRequest(
                km=km,
                price_eur=500.0,
                fuel_price=1.50,
                consum_litri=30.0,
            )

    @pytest.mark.parametrize(
        "price_eur",
        [-0.001, -1.0, -1000.0],
    )
    def test_price_must_be_non_negative(self, price_eur):
        """Negative price_eur raises ValidationError."""
        with pytest.raises(ValidationError, match="Price"):
            CalculationRequest(
                km=100.0,
                price_eur=price_eur,
                fuel_price=1.50,
                consum_litri=30.0,
            )

    def test_price_zero_is_valid(self):
        """price_eur=0 is allowed (non-negative)."""
        r = CalculationRequest(
            km=100.0,
            price_eur=0.0,
            fuel_price=1.50,
            consum_litri=30.0,
        )
        assert r.price_eur == 0.0

    @pytest.mark.parametrize(
        "fuel_price",
        [0.0, -0.001, -1.0],
    )
    def test_fuel_price_must_be_positive(self, fuel_price):
        """fuel_price <= 0 raises ValidationError."""
        with pytest.raises(ValidationError, match="Fuel price"):
            CalculationRequest(
                km=100.0,
                price_eur=500.0,
                fuel_price=fuel_price,
                consum_litri=30.0,
            )

    @pytest.mark.parametrize(
        "days",
        [0.0, -0.001, -1.0],
    )
    def test_days_must_be_positive(self, days):
        """days <= 0 raises ValidationError."""
        with pytest.raises(ValidationError, match="Days"):
            CalculationRequest(
                km=100.0,
                price_eur=500.0,
                fuel_price=1.50,
                days=days,
                consum_litri=30.0,
            )

    @pytest.mark.parametrize(
        "consum_litri",
        [0.0, -0.001, -1.0],
    )
    def test_consumption_must_be_positive(self, consum_litri):
        """consum_litri <= 0 raises ValidationError."""
        with pytest.raises(ValidationError, match="Consumption"):
            CalculationRequest(
                km=100.0,
                price_eur=500.0,
                fuel_price=1.50,
                consum_litri=consum_litri,
            )

    def test_missing_required_field_raises(self):
        """Omitting km (required) raises ValidationError."""
        with pytest.raises(ValidationError):
            CalculationRequest(
                price_eur=500.0,
                fuel_price=1.50,
                consum_litri=30.0,
            )

    def test_all_optional_fields(self):
        """Explicit values for all optional fields are accepted."""
        r = CalculationRequest(
            km=200.0,
            price_eur=1000.0,
            fuel_price=1.60,
            days=2.0,
            consum_litri=28.0,
            extra_in=50.0,
            sal_in=100.0,
            taxa_in=20.0,
            fuel_cost_override=450.0,
        )
        assert r.extra_in == 50.0
        assert r.sal_in == 100.0
        assert r.taxa_in == 20.0
        assert r.fuel_cost_override == 450.0


class TestTripCalculationResult:
    """Default fields, correct types for all fields."""

    def test_all_fields_set(self):
        """All fields are present and typed correctly."""
        r = TripCalculationResult(
            km=1000.0,
            price_eur=2000.0,
            fuel_price=1.50,
            days=3.0,
            consum_litri=30.0,
            total_income=2000.0,
            fuel_consumed_liters=300.0,
            fuel_cost=450.0,
            toll_cost=100.0,
            salary_cost=300.0,
            extra_costs=50.0,
            net_profit=1100.0,
            profit_per_km=1.10,
            margin_percent=55.0,
            cost_per_km=0.90,
        )
        assert isinstance(r.km, float)
        assert isinstance(r.price_eur, float)
        assert isinstance(r.fuel_price, float)
        assert isinstance(r.days, float)
        assert isinstance(r.net_profit, float)
        assert isinstance(r.profit_per_km, float)
        assert isinstance(r.margin_percent, float)
        assert isinstance(r.cost_per_km, float)
        assert r.currency == "EUR"

    def test_default_values(self):
        """Fields with defaults: extra_in, sal_in, taxa_in, toll_cost,
        salary_cost, extra_costs, gross_per_km all default to 0.0."""
        r = TripCalculationResult(
            km=500.0,
            price_eur=1000.0,
            fuel_price=1.50,
            days=1.0,
            consum_litri=30.0,
            total_income=1000.0,
            fuel_consumed_liters=150.0,
            fuel_cost=225.0,
            net_profit=775.0,
            profit_per_km=1.55,
            margin_percent=77.5,
            cost_per_km=0.45,
        )
        assert r.extra_in == 0.0
        assert r.sal_in == 0.0
        assert r.taxa_in == 0.0
        assert r.toll_cost == 0.0
        assert r.salary_cost == 0.0
        assert r.extra_costs == 0.0
        assert r.gross_per_km == 0.0

    def test_currency_default(self):
        """currency defaults to 'EUR'."""
        r = TripCalculationResult(
            km=100.0,
            price_eur=200.0,
            fuel_price=1.50,
            days=1.0,
            consum_litri=30.0,
            total_income=200.0,
            fuel_consumed_liters=30.0,
            fuel_cost=45.0,
            net_profit=155.0,
            profit_per_km=1.55,
            margin_percent=77.5,
            cost_per_km=0.45,
        )
        assert r.currency == "EUR"

    def test_float_type_enforced(self):
        """Integer inputs are coerced to float by Pydantic."""
        r = TripCalculationResult(
            km=100,
            price_eur=200,
            fuel_price=1,
            days=1,
            consum_litri=30,
            total_income=200,
            fuel_consumed_liters=30,
            fuel_cost=45,
            net_profit=155,
            profit_per_km=1.55,
            margin_percent=77.5,
            cost_per_km=0.45,
        )
        assert isinstance(r.km, float)
        assert isinstance(r.price_eur, float)
        assert r.km == 100.0

    def test_missing_required_field_raises(self):
        """Omitting a required field (e.g. km) raises ValidationError."""
        with pytest.raises(ValidationError):
            TripCalculationResult(
                price_eur=2000.0,
                fuel_price=1.50,
                days=3.0,
                consum_litri=30.0,
                total_income=2000.0,
                fuel_consumed_liters=300.0,
                fuel_cost=450.0,
                net_profit=1100.0,
                profit_per_km=1.10,
                margin_percent=55.0,
                cost_per_km=0.90,
            )
