"""
Non-determinism contract for currency, exchange rate, and fuel price services.

These services rely on external data sources and are inherently non-deterministic.
Same inputs at different times WILL produce different outputs.

AI Co-Pilot Integration Notes:
- Cache results and pass a ``cache_timestamp`` parameter to force refresh
- Use the ``get_cached_*`` methods for deterministic replay
- All non-deterministic methods are explicitly marked
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class NonDeterminismWarning:
    """Marks a method as non-deterministic with reasoning."""

    method: str
    reason: str
    external_dependency: str
    cache_ttl_seconds: int
    last_updated: Optional[datetime] = None


# Registry of all non-deterministic operations
NON_DETERMINISTIC_OPERATIONS: dict[str, NonDeterminismWarning] = {
    "currency.convert": NonDeterminismWarning(
        method="CurrencyService.convert",
        reason="Uses live exchange rates from external API",
        external_dependency="Exchange rate provider (e.g., exchangerate-api.com)",
        cache_ttl_seconds=3600,  # 1 hour
    ),
    "currency.refresh_rates": NonDeterminismWarning(
        method="CurrencyService.refresh_rates",
        reason="Fetches live rates from external API",
        external_dependency="Exchange rate provider",
        cache_ttl_seconds=3600,
    ),
    "exchange_rate.refresh": NonDeterminismWarning(
        method="ExchangeRateService.refresh",
        reason="Fetches live exchange rates via HTTP",
        external_dependency="Exchange rate API",
        cache_ttl_seconds=3600,
    ),
    "fuel_price.refresh": NonDeterminismWarning(
        method="FuelPriceService.refresh",
        reason="Scrapes live fuel prices from globalpetrolprices.com",
        external_dependency="globalpetrolprices.com",
        cache_ttl_seconds=86400,  # 24 hours
    ),
}


def get_non_deterministic_operations() -> dict[str, NonDeterminismWarning]:
    """Return all non-deterministic operations for AI tool catalog."""
    return NON_DETERMINISTIC_OPERATIONS


def is_deterministic(method_name: str) -> bool:
    """Check if a method is deterministic."""
    return method_name not in NON_DETERMINISTIC_OPERATIONS
