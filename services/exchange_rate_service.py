import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Optional

import requests

from utils.resource_path import data_path

logger = logging.getLogger("exchange_rate")

CACHE_FILE = data_path("data/exchange_rates_cache.json")
CACHE_TTL_SECONDS = 3600  # 1 hour
REQUEST_TIMEOUT = 5
BASE_CURRENCY = "EUR"

from config import Config
from services.base_worker import GracefulWorker
from utils.formatting import format_age

PRIMARY_API = Config.CURRENCY_API_PRIMARY
FALLBACK_API = Config.CURRENCY_API_FALLBACK

_DEFAULT_RATES: dict[str, float] = {
    "EUR": 1.0,
    "RON": 4.97,
    "USD": 1.08,
    "GBP": 0.86,
    "BGN": 1.96,
    "PLN": 4.32,
    "CZK": 24.8,
    "HUF": 395.0,
    "HRK": 7.54,
    "RSD": 117.0,
    "SEK": 11.2,
    "NOK": 11.8,
    "DKK": 7.46,
    "CHF": 0.94,
    "TRY": 34.5,
    "UAH": 44.0,
}


class ExchangeRateService(GracefulWorker):
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        GracefulWorker.__init__(self)
        self._rates: dict[str, float] = dict(_DEFAULT_RATES)
        self._rates_lock = threading.RLock()
        self._last_updated: Optional[float] = None
        self._last_fetch_ok: bool = False
        self._refresh_in_progress = False
        self._load_cache()
        logger.info("ExchangeRateService initialized (cached=%s age=%s)",
                     self._last_fetch_ok,
                     self._age_str())

    # ── Public API ─────────────────────────────────────────────────────

    def get_rate(self, currency_code: str) -> float:
        """Get the exchange rate for a currency relative to EUR.

        Returns cached rates; does NOT fetch live data.
        """
        if currency_code == BASE_CURRENCY:
            return 1.0
        with self._rates_lock:
            rate = self._rates.get(currency_code)
        if rate is None:
            logger.warning("Unknown currency %s, treating as 1:1 with EUR", currency_code)
            return 1.0
        return rate

    def get_all_rates(self) -> dict[str, float]:
        """Return all cached exchange rates (does NOT fetch live data).

        AI Co-Pilot: This method is deterministic — it returns the in-memory cached rates.
        Use :meth:`refresh` to fetch fresh rates.
        """
        with self._rates_lock:
            return dict(self._rates)

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        """NON-DETERMINISTIC: Converts using rates that may be live or cached.

        If rates are stale (older than 24× TTL), a warning is logged but the stale
        rates are still used. Call :meth:`refresh` explicitly to force an update.

        AI Co-Pilot: Use ``CurrencyService.convert_with_cache()`` for deterministic
        replay with explicit cache control.
        Cache TTL: 3600 seconds.
        """
        if from_currency == to_currency:
            return amount
        rate_from = self.get_rate(from_currency)
        rate_to = self.get_rate(to_currency)
        if rate_from == 0 or rate_to == 0:
            logger.error("Zero rate encountered: from=%s(%f) to=%s(%f)",
                         from_currency, rate_from, to_currency, rate_to)
            return amount
        age = self.age_seconds()
        if age is not None and age > CACHE_TTL_SECONDS * 24:
            logger.warning("Using exchange rates that are %.0f hours old (%.0f days)",
                           age / 3600, age / 86400)
        eur_amount = amount / rate_from
        return eur_amount * rate_to

    def refresh_if_stale(self) -> bool:
        """Refresh exchange rates if the cache is older than TTL (3600s).

        AI Co-Pilot: This is conditionally non-deterministic — it only fetches live
        data when the cache is stale. Use :meth:`get_rate` / :meth:`get_all_rates`
        for deterministic reads.
        """
        with self._rates_lock:
            if self._last_updated is None:
                return self.refresh(background=False)
            age = time.time() - self._last_updated
            if age > CACHE_TTL_SECONDS:
                logger.info("Exchange rates stale (age=%.0fs > TTL=%ds), refreshing", age, CACHE_TTL_SECONDS)
                return self.refresh(background=False)
        return True

    def refresh(self, background: bool = True) -> bool:
        """NON-DETERMINISTIC: Fetches live exchange rates from external API.

        AI Co-Pilot: Use :meth:`get_rate` / :meth:`get_all_rates` for deterministic replay.
        Cache TTL: 3600 seconds.
        """
        with self._rates_lock:
            if self._refresh_in_progress:
                logger.debug("Exchange rate refresh already in progress, skipping")
                return True
            self._refresh_in_progress = True
        if background:
            self._spawn("exchange-rate-refresh", self._do_refresh)
            return True
        return self._do_refresh()

    # ── Internal ───────────────────────────────────────────────────────

    def _do_refresh(self) -> bool:
        urls = [PRIMARY_API, FALLBACK_API]
        for url in urls:
            try:
                logger.info("Fetching exchange rates from %s ...", url)
                r = requests.get(url, timeout=REQUEST_TIMEOUT)
                if r.status_code == 200:
                    data = r.json()
                    raw = data.get("rates", {})
                    with self._rates_lock:
                        for code, rate in raw.items():
                            self._rates[code] = float(rate)
                        self._rates[BASE_CURRENCY] = 1.0
                        self._last_updated = time.time()
                        self._last_fetch_ok = True
                        self._refresh_in_progress = False
                    self._save_cache()
                    logger.info("Exchange rates refreshed OK (%s): %d currencies", url, len(raw))
                    return True
                else:
                    logger.warning("Exchange rate API %s returned HTTP %d", url, r.status_code)
            except requests.exceptions.Timeout:
                logger.warning("Exchange rate API %s timeout (%ds)", url, REQUEST_TIMEOUT)
            except requests.exceptions.ConnectionError as e:
                logger.warning("Exchange rate API %s connection error: %s", url, e)
            except Exception as e:
                logger.error("Exchange rate API %s unexpected error: %s", url, e)

        with self._rates_lock:
            self._last_fetch_ok = False
            self._refresh_in_progress = False
        return False

    def is_available(self) -> bool:
        """Check whether the service has fresh exchange rate data available.

        Returns ``True`` if a fetch was ever successful and the cache is younger
        than 24× TTL (i.e. 24 hours). Deterministic — does not trigger a fetch.
        """
        if not self._last_fetch_ok:
            return False
        age = self.age_seconds()
        if age is None:
            return False
        if age > CACHE_TTL_SECONDS * 24:
            return False
        return True

    def last_updated_str(self) -> str:
        """Return a human-readable string of when rates were last fetched.

        Deterministic — returns the cached timestamp.
        """
        if self._last_updated is None:
            return "never"
        return datetime.fromtimestamp(self._last_updated).strftime("%d/%m/%Y %H:%M")

    def age_seconds(self) -> Optional[float]:
        if self._last_updated is None:
            return None
        return time.time() - self._last_updated

    def _age_str(self) -> str:
        return format_age(self.age_seconds())

    # ── Cache persistence ──────────────────────────────────────────────

    def _load_cache(self):
        try:
            if os.path.isfile(CACHE_FILE):
                with open(CACHE_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                with self._rates_lock:
                    self._rates.update(data.get("rates", {}))
                ts = data.get("timestamp")
                if ts:
                    self._last_updated = ts
                    self._last_fetch_ok = True
                    logger.info("Loaded exchange rates from cache (age=%s)", self._age_str())
        except Exception as e:
            logger.warning("Failed to load exchange rate cache: %s", e)

    def _save_cache(self):
        try:
            data = {
                "timestamp": self._last_updated,
                "rates": self._rates,
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug("Exchange rates saved to cache")
        except Exception as e:
            logger.warning("Failed to save exchange rate cache: %s", e)
