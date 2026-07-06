"""Tests for CurrencyService."""
from unittest.mock import MagicMock, patch

import pytest

from services.currency_service import CurrencyService, CURRENCY_SYMBOLS


def test_get_symbol():
    service = CurrencyService(exchange_service=MagicMock())
    assert service.get_symbol("EUR") == "€"
    assert service.get_symbol("USD") == "$"
    assert service.get_symbol("RON") == "lei"
    assert service.get_symbol("XYZ") == "XYZ"  # fallback


def test_convert():
    mock_exchange = MagicMock()
    mock_exchange.convert.return_value = 4.95
    service = CurrencyService(exchange_service=mock_exchange)
    result = service.convert(100, "EUR", "RON")
    assert result == 4.95
    mock_exchange.convert.assert_called_with(100, "EUR", "RON")


def test_format_eur():
    service = CurrencyService(exchange_service=MagicMock())
    result = service.format(1234.5, "EUR")
    # EUR uses suffix format: "1,234.50 €"
    assert "€" in result
    assert "1,234.50" in result
    assert result == "1,234.50 €"


def test_format_usd():
    service = CurrencyService(exchange_service=MagicMock())
    result = service.format(99.99, "USD")
    assert result.startswith("$")
    assert "99.99" in result


def test_format_with_decimals():
    service = CurrencyService(exchange_service=MagicMock())
    result = service.format(42, "EUR", decimals=0)
    assert "42" in result


def test_get_rate():
    mock_exchange = MagicMock()
    mock_exchange.get_rate.return_value = 4.97
    service = CurrencyService(exchange_service=mock_exchange)
    assert service.get_rate("RON") == 4.97
    mock_exchange.get_rate.assert_called_with("RON")


def test_refresh_rates():
    mock_exchange = MagicMock()
    mock_exchange.refresh_if_stale.return_value = True
    service = CurrencyService(exchange_service=mock_exchange)
    assert service.refresh_rates() is True
    mock_exchange.refresh_if_stale.assert_called_once()


@patch("services.currency_service.ExchangeRateService")
def test_default_exchange_service(mock_ers):
    mock_ers_instance = MagicMock()
    mock_ers.return_value = mock_ers_instance
    _ = CurrencyService()
    mock_ers.assert_called_once()
