import logging
import time
from typing import Optional

from models.common import ServiceResult
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
        self._rate_cache: dict[str, tuple[float, float]] = {}  # key -> (rate, timestamp)
        logger.info("CurrencyService initialized")

    def get_symbol(self, code: str) -> str:
        return CURRENCY_SYMBOLS.get(code, code)

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        """NON-DETERMINISTIC: Uses live exchange rates from external API.

        AI Co-Pilot: Use :meth:`convert_with_cache` with ``force_refresh=False`` for deterministic replay.
        Cache TTL: 3600 seconds.
        """
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
        """NON-DETERMINISTIC: Fetches live rates from external API.

        AI Co-Pilot: Results are cached automatically. Use :meth:`get_cached_rate` for deterministic replay.
        Cache TTL: 3600 seconds.
        """
        return self._exchange.refresh_if_stale()

    # ── Cache-aware methods (deterministic when using cache) ──────────

    def get_cached_rate(self, from_currency: str, to_currency: str, max_age_seconds: int = 3600) -> Optional[float]:
        """Get cached conversion rate if fresh enough.

        Returns ``None`` if no fresh cached rate is available — caller should fall back
        to the live :meth:`convert` method.

        Args:
            from_currency: Source currency code (e.g. "EUR").
            to_currency: Target currency code (e.g. "USD").
            max_age_seconds: Maximum allowed age of cached rate in seconds (default 3600).

        Returns:
            The cached rate, or ``None`` if stale or missing.
        """
        if from_currency == to_currency:
            return 1.0
        key = f"{from_currency.upper()}/{to_currency.upper()}"
        cached = self._rate_cache.get(key)
        if cached is None:
            return None
        rate, ts = cached
        age = time.time() - ts
        if age > max_age_seconds:
            return None
        return rate

    def convert_with_cache(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        force_refresh: bool = False,
        max_cache_age: int = 3600,
    ) -> ServiceResult[float]:
        """Convert currency with optional cache control.

        AI-friendly: pass ``force_refresh=False`` (default) for deterministic replay.

        Args:
            amount: The monetary amount to convert.
            from_currency: Source currency code.
            to_currency: Target currency code.
            force_refresh: If ``True``, bypass cache and call the live API.
            max_cache_age: Maximum age of cache in seconds (default 3600).

        Returns:
            A ``ServiceResult`` containing the converted amount.
        """
        if from_currency == to_currency:
            return ServiceResult(success=True, data=amount)

        # Try cache first (unless force_refresh is requested)
        if not force_refresh:
            cached_rate = self.get_cached_rate(from_currency, to_currency, max_cache_age)
            if cached_rate is not None:
                result = amount * cached_rate
                logger.debug("Cache hit: %.2f %s -> %.2f %s (rate=%.6f)",
                             amount, from_currency, result, to_currency, cached_rate)
                return ServiceResult(success=True, data=result)

        # Live conversion via exchange service
        try:
            rate_from = self._exchange.get_rate(from_currency)
            rate_to = self._exchange.get_rate(to_currency)
            if rate_from == 0 or rate_to == 0:
                return ServiceResult(
                    success=False,
                    data=amount,
                    errors=[{"message": f"Zero rate for {from_currency} or {to_currency}", "code": "ZERO_RATE"}],
                )
            eur_amount = amount / rate_from
            converted = eur_amount * rate_to

            # Seed the cache
            key = f"{from_currency.upper()}/{to_currency.upper()}"
            effective_rate = converted / amount if amount != 0 else rate_to / rate_from
            self._rate_cache[key] = (effective_rate, time.time())

            logger.debug("Live conversion: %.2f %s -> %.2f %s", amount, from_currency, converted, to_currency)
            return ServiceResult(success=True, data=converted)
        except Exception as exc:
            logger.error("Conversion failed: %s", exc)
            return ServiceResult(
                success=False,
                data=amount,
                errors=[{"message": str(exc), "code": "CONVERSION_ERROR"}],
            )
