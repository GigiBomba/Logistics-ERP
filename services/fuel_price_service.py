import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from typing import Dict, Optional

import requests

logger = logging.getLogger("fuel_price")

FALLBACK_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fallback_fuel_prices.json")
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fuel_prices_cache.json")
CACHE_TTL_SECONDS = 3600  # 1 hour
REQUEST_TIMEOUT = 5
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
SCRAPE_URL = "https://www.globalpetrolprices.com/{country}/diesel_prices/"

# Country code -> full country name mapping for URL building
_COUNTRY_URL_NAMES = {
    "RO": "Romania",
    "DE": "germany",
    "FR": "france",
    "IT": "italy",
    "ES": "spain",
    "PT": "portugal",
    "NL": "netherlands",
    "BE": "belgium",
    "AT": "austria",
    "PL": "poland",
    "CZ": "czech-republic",
    "SK": "slovakia",
    "HU": "hungary",
    "BG": "bulgaria",
    "GR": "greece",
    "HR": "croatia",
    "RS": "serbia",
    "SI": "slovenia",
    "UA": "ukraine",
    "TR": "turkey",
    "UK": "united-kingdom",
    "SE": "sweden",
    "NO": "norway",
    "DK": "denmark",
    "FI": "finland",
    "LT": "lithuania",
    "LV": "latvia",
    "EE": "estonia",
    "CH": "switzerland",
}

# Price sanity bounds (EUR/L)
_PRICE_MIN = 0.80
_PRICE_MAX = 2.50


class FuelPriceService:
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
        self._prices: Dict[str, float] = {}
        self._last_updated: Optional[float] = None
        self._fallback_prices: Dict[str, float] = {}
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

    def get_prices_all(self) -> Dict[str, float]:
        return dict(self._prices) if self._prices else dict(self._fallback_prices)

    def refresh_if_stale(self) -> bool:
        if self._last_updated is None:
            return self.refresh()
        age = time.time() - self._last_updated
        if age > CACHE_TTL_SECONDS:
            logger.info("Fuel prices stale (age=%.0fs > TTL=%ds), refreshing", age, CACHE_TTL_SECONDS)
            return self.refresh()
        return True

    def refresh(self, background: bool = True) -> bool:
        if self._refresh_in_progress:
            logger.debug("Fuel price refresh already in progress, skipping")
            return True
        self._refresh_in_progress = True
        if background:
            t = threading.Thread(target=self._do_refresh_all, daemon=True)
            t.start()
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
        age = self.age_seconds()
        if age is None:
            return "never"
        if age < 60:
            return f"{age:.0f}s"
        if age < 3600:
            return f"{age/60:.0f}m"
        return f"{age/3600:.1f}h"

    # ── Internal fetch ─────────────────────────────────────────────────

    def _do_refresh_all(self) -> bool:
        """Fetch prices for all configured countries. Returns True if ANY country succeeded."""
        success_count = 0
        fail_count = 0
        countries = list(_COUNTRY_URL_NAMES.keys())

        for code in countries:
            try:
                price = self._fetch_single_country(code)
                if price is not None:
                    self._prices[code] = price
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.warning("Failed to fetch fuel price for %s: %s", code, e)
                fail_count += 1

        if success_count > 0:
            self._last_updated = time.time()
            self._last_fetch_ok = True
            self._save_cache()
            logger.info("Fuel prices refreshed: %d OK, %d failed", success_count, fail_count)
        else:
            self._last_fetch_ok = False
            logger.warning("Fuel prices ALL %d countries failed, using fallback", fail_count)
            # Ensure fallback values are at least available
            for code, price in self._fallback_prices.items():
                self._prices.setdefault(code, price)

        self._refresh_in_progress = False
        return success_count > 0

    def _fetch_single_country(self, country_code: str) -> Optional[float]:
        """Scrape globalpetrolprices.com for diesel price in EUR/L."""
        url_name = _COUNTRY_URL_NAMES.get(country_code)
        if not url_name:
            return None

        url = SCRAPE_URL.format(country=url_name)
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT,
                           headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
            if r.status_code != 200:
                logger.debug("HTTP %d for %s", r.status_code, url)
                return None

            # Try multiple patterns in order of reliability
            html = r.text
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
                            logger.debug("Fuel price %s: %.3f EUR/L", country_code, p)
                            return round(p, 3)
                    except ValueError:
                        continue

            logger.debug("No valid price pattern found for %s", country_code)
            return None
        except requests.exceptions.Timeout:
            logger.debug("Timeout fetching fuel price for %s", country_code)
            return None
        except requests.exceptions.ConnectionError as e:
            logger.debug("Connection error for %s: %s", country_code, e)
            return None
        except Exception as e:
            logger.debug("Error fetching %s: %s", country_code, e)
            return None

    # ── Fallback defaults ──────────────────────────────────────────────

    def _load_fallback(self):
        """Load bundled fallback prices from JSON file."""
        try:
            if os.path.isfile(FALLBACK_FILE):
                with open(FALLBACK_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._fallback_prices = data.get("prices", {})
                # Copy fallback into main prices dict as starting point
                for code, price in self._fallback_prices.items():
                    self._prices.setdefault(code, price)
                logger.info("Loaded %d fallback fuel prices from %s", len(self._fallback_prices), FALLBACK_FILE)
            else:
                logger.warning("Fallback fuel prices file not found: %s", FALLBACK_FILE)
                self._fallback_prices = {"DEFAULT": 1.55}
                self._prices = {"DEFAULT": 1.55}
        except Exception as e:
            logger.error("Failed to load fallback fuel prices: %s", e)
            self._fallback_prices = {"DEFAULT": 1.55}
            self._prices = {"DEFAULT": 1.55}

    # ── Cache persistence ──────────────────────────────────────────────

    def _load_cache(self):
        try:
            if os.path.isfile(CACHE_FILE):
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cached = data.get("prices", {})
                ts = data.get("timestamp")
                for code, price in cached.items():
                    self._prices[code] = price
                if ts:
                    self._last_updated = ts
                self._last_fetch_ok = True
                logger.info("Loaded fuel price cache: %d countries (age=%s)",
                            len(cached), self._age_str())
        except Exception as e:
            logger.warning("Failed to load fuel price cache: %s", e)

    def _save_cache(self):
        try:
            data = {
                "timestamp": self._last_updated,
                "prices": self._prices,
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug("Fuel prices saved to cache (%d countries)", len(self._prices))
        except Exception as e:
            logger.warning("Failed to save fuel price cache: %s", e)
