"""Tests for CostEngineService."""
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
