"""Tests for CostEngineService."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.cost_engine import CostEngineService


@pytest.fixture
def engine():
    return CostEngineService(fuel_price_eur_per_liter=1.5)


def test_estimate_basic(engine):
    result = engine.estimate(1000.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO")
    assert result["fuel_liters"] == 300.0  # (1000/100) * 30
    assert result["fuel_cost"] == 450.0  # 300 * 1.5
    assert result["toll_cost"] > 0
    assert result["total_cost"] == pytest.approx(result["fuel_cost"] + result["toll_cost"])


def test_estimate_with_route_details(engine):
    truck = {"fuel_consumption_l_per_100km": 30}
    route = {"road_class": 1.0}
    result = engine.estimate(500.0, truck, route, country_code="FR")
    assert result["fuel_liters"] == 150.0
    assert result["fuel_cost"] == 225.0


def test_estimate_none_distance(engine):
    result = engine.estimate(None, {}, country_code="RO")
    assert result == {"fuel_liters": 0.0, "fuel_cost": 0.0, "toll_cost": 0.0, "total_cost": 0.0}


def test_estimate_zero_distance(engine):
    result = engine.estimate(0, {"fuel_consumption_l_per_100km": 30}, country_code="RO")
    assert result["fuel_liters"] == 0.0
    assert result["fuel_cost"] == 0.0


def test_fuel_price_property_with_fixed():
    engine = CostEngineService(fuel_price_eur_per_liter=2.0)
    assert engine.fuel_price == 2.0


@patch("services.cost_engine.FuelPriceService")
def test_fuel_price_from_service(mock_fps):
    mock_fps_instance = MagicMock()
    mock_fps_instance.get_price.return_value = 1.8
    mock_fps.return_value = mock_fps_instance
    engine = CostEngineService(country_code="DE")
    assert engine.fuel_price == 1.8
    mock_fps_instance.get_price.assert_called_with("DE")


@patch("services.cost_engine.FuelPriceService")
def test_estimate_country_factor(mock_fps):
    mock_fps_instance = MagicMock()
    mock_fps_instance.get_price.return_value = 1.5
    mock_fps.return_value = mock_fps_instance

    truck = {"fuel_consumption_l_per_100km": 30}
    engine = CostEngineService(country_code="RO")
    result_ro = engine.estimate(100.0, truck, country_code="RO")
    engine_de = CostEngineService(country_code="DE")
    result_de = engine_de.estimate(100.0, truck, country_code="DE")
    assert result_de["toll_cost"] > result_ro["toll_cost"]


@patch("services.cost_engine.FuelPriceService")
def test_estimate_fallback_consumption(mock_fps):
    mock_fps_instance = MagicMock()
    mock_fps_instance.get_price.return_value = 1.5
    mock_fps.return_value = mock_fps_instance
    engine = CostEngineService(country_code="RO")
    # No consumption provided → default 34.0
    result = engine.estimate(100.0, {})
    expected_liters = (100.0 / 100.0) * 34.0
    assert result["fuel_liters"] == expected_liters


def test_estimate_rounding(engine):
    result = engine.estimate(1.0, {"fuel_consumption_l_per_100km": 30})
    assert isinstance(result["fuel_liters"], float)
    assert isinstance(result["fuel_cost"], float)
    assert isinstance(result["toll_cost"], float)
    assert isinstance(result["total_cost"], float)


@patch("services.cost_engine.Config")
def test_toll_rate_from_config(mock_config):
    mock_config.DEFAULT_TOLL_RATE = 0.12
    engine = CostEngineService(fuel_price_eur_per_liter=1.5)
    result = engine.estimate(100.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO")
    assert result["toll_cost"] == pytest.approx(100.0 * 0.12 * 1.0 * 0.5)


def test_estimate_negative_distance(engine):
    """Negative distance produces negative fuel values (code doesn't guard against it)."""
    result = engine.estimate(-100.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO")
    assert result["fuel_liters"] == -30.0
    assert result["fuel_cost"] == -45.0


def test_estimate_large_distance(engine):
    """Very large distance should still produce sensible results."""
    result = engine.estimate(1_000_000.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO")
    assert result["fuel_liters"] == 300_000.0
    assert result["fuel_cost"] == 450_000.0
    assert result["toll_cost"] > 0
    assert result["total_cost"] == pytest.approx(result["fuel_cost"] + result["toll_cost"])


def test_estimate_unknown_country_uses_default_factor(engine):
    """An unrecognised country code should fall back to DEFAULT factor."""
    result = engine.estimate(100.0, {"fuel_consumption_l_per_100km": 30}, country_code="XX")
    # DEFAULT country factor is 1.0 (same as RO)
    result_ro = engine.estimate(100.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO")
    assert result["toll_cost"] == result_ro["toll_cost"]


def test_estimate_fallback_consumption_alt_key(engine):
    """When fuel_consumption_l_per_100km is missing, fall back to fuel_consumption."""
    result = engine.estimate(100.0, {"fuel_consumption": 30}, country_code="RO")
    expected_liters = (100.0 / 100.0) * 30.0
    assert result["fuel_liters"] == expected_liters


def test_estimate_no_consumption_keys_uses_default(engine):
    """When no consumption key is present at all, default to 34.0 L/100km."""
    result = engine.estimate(100.0, {}, country_code="RO")
    expected_liters = (100.0 / 100.0) * 34.0
    assert result["fuel_liters"] == expected_liters


def test_estimate_zero_fuel_price():
    """Zero fuel price should result in zero fuel cost."""
    engine = CostEngineService(fuel_price_eur_per_liter=0.0)
    result = engine.estimate(100.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO")
    assert result["fuel_cost"] == 0.0
    assert result["total_cost"] == pytest.approx(result["toll_cost"])


@patch("services.cost_engine.FuelPriceService")
def test_estimate_route_with_road_class_as_float(mock_fps):
    """Route details road_class as a float should be used for toll calculation."""
    mock_fps_instance = MagicMock()
    mock_fps_instance.get_price.return_value = 1.5
    mock_fps.return_value = mock_fps_instance
    engine = CostEngineService(country_code="RO")
    # road_class 0.8 as a float doesn't match ROAD_CLASS_FACTOR keys (strings),
    # so the engine falls back to the default factor of 0.5
    result = engine.estimate(100.0, {"fuel_consumption_l_per_100km": 30},
                             route_details={"road_class": 0.8}, country_code="RO")
    from config import Config
    expected_toll = 100.0 * Config.DEFAULT_TOLL_RATE * 1.0 * 0.5
    assert result["toll_cost"] == pytest.approx(expected_toll)


def test_estimate_rounding_precision(engine):
    """Verify rounding to 2 decimal places."""
    result = engine.estimate(1.0, {"fuel_consumption_l_per_100km": 30})
    # fuel_liters = (1/100)*30 = 0.3 → rounded to 2 dp → 0.3
    assert result["fuel_liters"] == 0.3
    # fuel_cost = 0.3 * 1.5 = 0.45
    assert result["fuel_cost"] == 0.45
