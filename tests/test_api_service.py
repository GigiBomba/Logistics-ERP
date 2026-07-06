"""Tests for APIService."""
from unittest.mock import MagicMock, patch

import pytest

from services.api_service import APIService


@pytest.fixture
def service():
    svc = APIService()
    svc._fuel_service = MagicMock()
    svc._exchange_service = MagicMock()
    return svc


def test_get_diesel_price(service):
    service._fuel_service.get_price.return_value = 1.65
    result = service.get_diesel_price("RO")
    assert result == 1.65
    service._fuel_service.get_price.assert_called_with("RO")


def test_get_diesel_price_default(service):
    service._fuel_service.get_price.return_value = 1.70
    result = service.get_diesel_price()
    assert result == 1.70
    service._fuel_service.get_price.assert_called_with("DEFAULT")


def test_get_rates(service):
    service._exchange_service.get_all_rates.return_value = {"EUR": 1.0, "RON": 4.97}
    result = service.get_rates()
    assert result == {"EUR": 1.0, "RON": 4.97}


def test_refresh_fuel_prices(service):
    service._fuel_service.refresh_if_stale.return_value = True
    assert service.refresh_fuel_prices() is True
    service._fuel_service.refresh_if_stale.assert_called_once()


def test_refresh_exchange_rates(service):
    service._exchange_service.refresh_if_stale.return_value = True
    assert service.refresh_exchange_rates() is True
    service._exchange_service.refresh_if_stale.assert_called_once()


@patch("services.api_service.FuelPriceService")
@patch("services.api_service.ExchangeRateService")
def test_init_creates_services(mock_exc, mock_fuel):
    svc = APIService()
    assert svc._fuel_service is not None
    assert svc._exchange_service is not None
