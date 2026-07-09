"""Tests for CurrencyService."""
from __future__ import annotations

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


def test_format_bgn_prefix(service_fixture):
    """BGN should use prefix symbol format like USD/GBP."""
    result = service_fixture.format(100.0, "BGN")
    assert result.startswith("лв")
    assert "100.00" in result


def test_format_ron_suffix(service_fixture):
    """RON should use suffix symbol format."""
    result = service_fixture.format(250.0, "RON")
    assert result.endswith("lei")
    assert "250.00" in result


def test_format_large_number_with_commas(service_fixture):
    """Large numbers should be formatted with thousand separators."""
    result = service_fixture.format(1234567.89, "EUR")
    assert "1,234,567.89" in result


def test_format_zero_amount(service_fixture):
    """Zero amount should be formatted correctly."""
    result = service_fixture.format(0, "EUR")
    assert "0.00" in result
    assert "€" in result


def test_format_negative_amount(service_fixture):
    """Negative amounts should be formatted correctly."""
    result = service_fixture.format(-50.5, "EUR")
    assert "-50.50" in result
    assert "€" in result


def test_convert_same_currency(service_fixture):
    """Converting between the same currency should return the amount unchanged."""
    service_fixture._exchange.convert.return_value = 100.0
    result = service_fixture.convert(100.0, "EUR", "EUR")
    assert result == 100.0


def test_convert_zero_amount(service_fixture):
    """Converting zero amount should return zero."""
    service_fixture._exchange.convert.return_value = 0.0
    result = service_fixture.convert(0.0, "EUR", "USD")
    assert result == 0.0


def test_get_symbol_lowercase(service_fixture):
    """get_symbol with lowercase code should return the code as fallback."""
    result = service_fixture.get_symbol("eur")
    assert result == "eur"  # case-sensitive lookup; lowercase not in dict


def test_get_symbol_unsupported(service_fixture):
    """Unsupported currency codes return the code itself."""
    result = service_fixture.get_symbol("XYZ")
    assert result == "XYZ"


def test_format_many_decimals(service_fixture):
    """Format with a custom number of decimals."""
    result = service_fixture.format(1.23456, "EUR", decimals=4)
    assert "1.2346" in result  # rounded to 4 decimal places


@pytest.fixture
def service_fixture():
    return CurrencyService(exchange_service=MagicMock())
