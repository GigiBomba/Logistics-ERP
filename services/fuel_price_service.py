import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from typing import Optional

import requests

from services.base_worker import GracefulWorker
from utils.formatting import format_age
from utils.resource_path import data_path, resource_path

logger = logging.getLogger("fuel_price")

FALLBACK_FILE = resource_path("data/fallback_fuel_prices.json")
CACHE_FILE = data_path("data/fuel_prices_cache.json")
CACHE_TTL_SECONDS = 86400  # 24 hours
REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
SCRAPE_URL = "https://www.globalpetrolprices.com/{country}/diesel_prices/"

# Country code -> full country name mapping for URL building
# IMPORTANT: Country names must be capitalized (e.g., "Germany" not "germany")
_COUNTRY_URL_NAMES = {
    "RO": "Romania",
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "PT": "Portugal",
    "NL": "Netherlands",
    "BE": "Belgium",
    "AT": "Austria",
    "PL": "Poland",
    "CZ": "Czech-Republic",
    "SK": "Slovakia",
    "HU": "Hungary",
    "BG": "Bulgaria",
    "GR": "Greece",
    "HR": "Croatia",
    "RS": "Serbia",
    "SI": "Slovenia",
    "UA": "Ukraine",
    "TR": "Turkey",
    "UK": "United-Kingdom",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "FI": "Finland",
    "LT": "Lithuania",
    "LV": "Latvia",
    "EE": "Estonia",
    "CH": "Switzerland",
}

# Price sanity bounds (EUR/L)
_PRICE_MIN = 0.80
_PRICE_MAX = 3.00


class FuelPriceService(GracefulWorker):
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
        self._prices: dict[str, float] = {}
        self._prices_lock = threading.Lock()
        self._last_updated: Optional[float] = None
        self._fallback_prices: dict[str, float] = {}
        self._last_fetch_ok: bool = False
        self._refresh_in_progress = False
        self._load_fallback()
        self._load_cache()
        # Merge: cache overrides fallback for countries that were successfully fetched
        logger.info("FuelPriceService initialized (countries=%d, cached=%s, age=%s)",
                     len(self._prices),
                     self._last_fetch_ok,
                     self._age_str())

    # ── Public API ─────────────────────────────────────────────────────

    def get_price(self, country_code: str, currency: str = "EUR") -> float:
        with self._prices_lock:
            price_eur = self._prices.get(country_code.upper())
            if price_eur is None:
                price_eur = self._prices.get("DEFAULT")
        if price_eur is None:
            price_eur = self._fallback_prices.get("DEFAULT", 1.55)

        if currency.upper() == "EUR":
            return price_eur

        from services.exchange_rate_service import ExchangeRateService
        fx = ExchangeRateService()
        local_price = fx.convert(price_eur, "EUR", currency.upper())
        logger.debug("Fuel price %s -> %s: %.4f EUR -> %.4f %s",
                     country_code, currency, price_eur, local_price, currency)
        return local_price

    def get_prices_all(self) -> dict[str, float]:
        with self._prices_lock:
            prices = dict(self._prices) if self._prices else None
        return prices if prices else dict(self._fallback_prices)

    def refresh_if_stale(self) -> bool:
        if self._last_updated is None:
            return self.refresh()
        age = time.time() - self._last_updated
        if age > CACHE_TTL_SECONDS:
            logger.info("Fuel prices stale (age=%.0fs > TTL=%ds), refreshing", age, CACHE_TTL_SECONDS)
            return self.refresh()
        else:
            logger.info("Fetched prices for %d countries from globalpetrolprices (cached)", len(self._prices))
        return True

    def refresh(self, background: bool = True) -> bool:
        if self._refresh_in_progress:
            logger.debug("Fuel price refresh already in progress, skipping")
            return True
        self._refresh_in_progress = True
        if background:
            self._spawn("fuel-price-refresh", self._do_refresh_all)
            return True
        return self._do_refresh_all()

    def get_price_for_country(self, country_code: str) -> float:
        return self.get_price(country_code)

    def is_available(self) -> bool:
        return self._last_fetch_ok or bool(self._prices)

    def last_updated_str(self) -> str:
        if self._last_updated is None:
            return "never"
        return datetime.fromtimestamp(self._last_updated).strftime("%d/%m/%Y %H:%M")

    def age_seconds(self) -> Optional[float]:
        if self._last_updated is None:
            return None
        return time.time() - self._last_updated

    def _age_str(self) -> str:
        return format_age(self.age_seconds())

    # ── Internal fetch ─────────────────────────────────────────────────

    def _do_refresh_all(self) -> bool:
        """Fetch prices for all configured countries. Returns True if ANY country succeeded."""
        success_count = 0
        fail_count = 0
        failed_countries = []
        countries = list(_COUNTRY_URL_NAMES.keys())

        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=8) as executor:
            future_map = {executor.submit(self._fetch_single_country, code): code for code in countries}
            for future in as_completed(future_map):
                code = future_map[future]
                try:
                    price = future.result()
                    if price is not None:
                        with self._prices_lock:
                            self._prices[code] = price
                        success_count += 1
                    else:
                        fail_count += 1
                        failed_countries.append(code)
                except Exception as e:
                    logger.warning("Failed to fetch fuel price for %s: %s", code, e)
                    fail_count += 1
                    failed_countries.append(code)

        if success_count > 0:
            self._last_updated = time.time()
            self._last_fetch_ok = True
            self._save_cache()
            logger.info("Fetched prices for %d countries from globalpetrolprices (live)", success_count)
            if fail_count > 0:
                logger.warning("Failed to fetch %d countries: %s", fail_count, ", ".join(failed_countries))
        else:
            self._last_fetch_ok = False
            logger.warning("Fuel prices ALL %d countries failed, using fallback", fail_count)
            logger.warning("Failed countries: %s", ", ".join(failed_countries))
            # Ensure fallback values are at least available
            with self._prices_lock:
                for code, price in self._fallback_prices.items():
                    self._prices.setdefault(code, price)

        self._refresh_in_progress = False
        return success_count > 0

    def _fetch_single_country(self, country_code: str) -> Optional[float]:
        """Scrape globalpetrolprices.com for diesel price in EUR/L."""
        import traceback
        url_name = _COUNTRY_URL_NAMES.get(country_code)
        if not url_name:
            return None

        url = SCRAPE_URL.format(country=url_name)
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT,
                           headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
            if r.status_code != 200:
                logger.warning("HTTP %d for %s (URL: %s)", r.status_code, country_code, url)
                return None

            html = r.text

            # Try to extract EUR price directly (e.g., "EUR 1.93 per liter")
            eur_match = re.search(r'EUR\s*(\d+\.\d+)\s*per liter', html, re.IGNORECASE)
            if eur_match:
                eur_price = float(eur_match.group(1))
                if _PRICE_MIN < eur_price < _PRICE_MAX:
                    logger.debug("Fuel price %s: %.3f EUR/L (direct)", country_code, eur_price)
                    return round(eur_price, 3)

            # Try to extract USD price and convert to EUR
            usd_match = re.search(r'USD\s*(\d+\.\d+)\s*per liter', html, re.IGNORECASE)
            if usd_match:
                usd_price = float(usd_match.group(1))
                from services.exchange_rate_service import ExchangeRateService
                fx = ExchangeRateService()
                eur_price = fx.convert(usd_price, "USD", "EUR")
                if _PRICE_MIN < eur_price < _PRICE_MAX:
                    logger.debug("Fuel price %s: %.3f USD/L -> %.3f EUR/L", country_code, usd_price, eur_price)
                    return round(eur_price, 3)

            # Fallback: try other patterns for EUR
            patterns = [
                r'(\d+\.\d+)\s*(?:EUR|€|euro)',
                r'price.*?(\d+\.\d+)\s*(?:EUR|€)',
                r'(\d+[.,]\d+)\s*(?:EUR|€|euro)',
            ]
            for pat in patterns:
                matches = re.findall(pat, html, re.IGNORECASE)
                for m in matches:
                    try:
                        p = float(m.replace(",", "."))
                        if _PRICE_MIN < p < _PRICE_MAX:
                            logger.debug("Fuel price %s: %.3f EUR/L (pattern)", country_code, p)
                            return round(p, 3)
                    except ValueError:
                        continue

            logger.warning("No valid price pattern found for %s (HTML length: %d)", country_code, len(html))
            return None
        except requests.exceptions.Timeout as e:
            logger.warning("Timeout fetching fuel price for %s: %s", country_code, e)
            return None
        except requests.exceptions.ConnectionError as e:
            logger.warning("Connection error for %s: %s", country_code, e)
            return None
        except Exception as e:
            logger.warning("Error fetching %s: %s\n%s", country_code, type(e).__name__, traceback.format_exc())
            return None

    # ── Fallback defaults ──────────────────────────────────────────────

    def _load_fallback(self):
        """Load bundled fallback prices from JSON file."""
        try:
            if os.path.isfile(FALLBACK_FILE):
                with open(FALLBACK_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                self._fallback_prices = data.get("prices", {})
                # Copy fallback into main prices dict as starting point
                with self._prices_lock:
                    for code, price in self._fallback_prices.items():
                        self._prices.setdefault(code, price)
                logger.info("Loaded %d fallback fuel prices from %s", len(self._fallback_prices), FALLBACK_FILE)
            else:
                logger.warning("Fallback fuel prices file not found: %s", FALLBACK_FILE)
                self._fallback_prices = {"DEFAULT": 1.55}
                with self._prices_lock:
                    self._prices = {"DEFAULT": 1.55}
        except Exception as e:
            logger.error("Failed to load fallback fuel prices: %s", e)
            self._fallback_prices = {"DEFAULT": 1.55}
            with self._prices_lock:
                self._prices = {"DEFAULT": 1.55}

    # ── Cache persistence ──────────────────────────────────────────────

    def _load_cache(self):
        try:
            if os.path.isfile(CACHE_FILE):
                with open(CACHE_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                cached = data.get("prices", {})
                ts = data.get("timestamp")
                source = data.get("source", "unknown")
                with self._prices_lock:
                    for code, price in cached.items():
                        self._prices[code] = price
                if ts:
                    self._last_updated = ts
                self._last_fetch_ok = True
                logger.info("Loaded fuel price cache: %d countries from %s (age=%s)",
                            len(cached), source, self._age_str())
        except Exception as e:
            logger.warning("Failed to load fuel price cache: %s", e)

    def _save_cache(self):
        try:
            data = {
                "fetched_at": datetime.fromtimestamp(self._last_updated).isoformat() if self._last_updated else None,
                "timestamp": self._last_updated,
                "source": "globalpetrolprices",
                "prices": self._prices,
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug("Fuel prices saved to cache (%d countries)", len(self._prices))
        except Exception as e:
            logger.warning("Failed to save fuel price cache: %s", e)
