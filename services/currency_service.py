import logging
from typing import Optional

from services.exchange_rate_service import ExchangeRateService

logger = logging.getLogger("currency")

CURRENCY_SYMBOLS: dict[str, str] = {
    "EUR": "€",
    "RON": "lei",
    "USD": "$",
    "GBP": "£",
    "BGN": "лв",
    "PLN": "zł",
    "CZK": "Kč",
    "HUF": "Ft",
    "HRK": "kn",
    "RSD": "дин",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
    "CHF": "Fr",
    "TRY": "₺",
    "UAH": "₴",
}

SUPPORTED_CURRENCIES = sorted(CURRENCY_SYMBOLS.keys())


class CurrencyService:
    def __init__(self, exchange_service: Optional[ExchangeRateService] = None):
        self._exchange = exchange_service or ExchangeRateService()
        logger.info("CurrencyService initialized")

    def get_symbol(self, code: str) -> str:
        return CURRENCY_SYMBOLS.get(code, code)

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        return self._exchange.convert(amount, from_currency, to_currency)

    def format(self, amount: float, currency_code: str, decimals: int = 2) -> str:
        symbol = self.get_symbol(currency_code)
        formatted = f"{amount:,.{decimals}f}"
        if currency_code in ("USD", "GBP", "BGN"):
            return f"{symbol}{formatted}"
        return f"{formatted} {symbol}"

    def get_rate(self, code: str) -> float:
        return self._exchange.get_rate(code)

    def refresh_rates(self, background: bool = True) -> bool:
        return self._exchange.refresh_if_stale()
