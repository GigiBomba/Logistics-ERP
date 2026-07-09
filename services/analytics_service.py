"""Comprehensive analytics service — fleet, financial, client, route, driver, document."""

import threading
import time
from typing import Any, Optional

class AnalyticsService:
    CACHE_TTL = 300.0

    def __init__(self, db):
        self.db = db
        from repositories.analytics_repository import AnalyticsRepository
        self._repo = AnalyticsRepository(db)
        self._caches: dict[tuple, tuple[Any, float, tuple]] = {}
        self._cache_lock = threading.Lock()
        # Per-key locks to prevent cache stampede (only one compute per key at a time)
        self._key_locks: dict[tuple, threading.Lock] = {}
        self._key_locks_lock = threading.Lock()

    def _get_key_lock(self, key: tuple) -> threading.Lock:
        with self._key_locks_lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            return self._key_locks[key]

    def _cached(self, cache_key: str, func, *args):
        now = time.time()
        key = (cache_key, args)
        # Fast check under main cache lock
        with self._cache_lock:
            cache_entry = self._caches.get(key)
            if cache_entry:
                data, ts, ck = cache_entry
                if ck == args and (now - ts) < self.CACHE_TTL:
                    return data
        # Per-key lock prevents concurrent computation of the same key
        per_key_lock = self._get_key_lock(key)
        with per_key_lock:
            # Double-check under per-key lock (another thread may have stored while we waited)
            with self._cache_lock:
                cache_entry = self._caches.get(key)
                if cache_entry:
                    data, ts, ck = cache_entry
                    if ck == args and (now - ts) < self.CACHE_TTL:
                        return data
            # Compute — only this thread runs for this key
            result = func(*args)
            with self._cache_lock:
                self._caches[key] = (result, time.time(), args)
            return result

    def invalidate(self):
        with self._cache_lock:
            self._caches.clear()

    def _parse_dates(self, from_date: Optional[str], to_date: Optional[str]):
        from_d = from_date or None
        to_d = to_date or None
        return from_d, to_d

    # ── Legacy (compat with old analytics_view) ──

    def get_data(self, from_date=None, to_date=None) -> tuple:
        return self._cached("get_data", self._repo.get_analytics_data, from_date, to_date)

    # ── Financial ─────────────────────────────────────────────────

    def get_financial(self, from_date=None, to_date=None):
        return self._cached("financial", self._repo.get_financial_analytics, from_date, to_date)

    def get_revenue_by_client(self, from_date=None, to_date=None):
        return self._cached("rev_client", self._repo.get_revenue_by_client, from_date, to_date)

    def get_revenue_by_country(self, from_date=None, to_date=None):
        return self._cached("rev_country", self._repo.get_revenue_by_country, from_date, to_date)

    # ── Route ─────────────────────────────────────────────────────

    def get_route_profitability(self, from_date=None, to_date=None):
        return self._cached("route_profit", self._repo.get_route_profitability, from_date, to_date)

    # ── Client ────────────────────────────────────────────────────

    def get_client_analytics(self, from_date=None, to_date=None):
        return self._cached("client", self._repo.get_client_analytics, from_date, to_date)

    # ── Fleet ─────────────────────────────────────────────────────

    def get_fleet(self, from_date=None, to_date=None):
        return self._cached("fleet", self._repo.get_fleet_analytics, from_date, to_date)

    def get_maintenance_alerts(self):
        return self._cached("maint", self._repo.get_maintenance_alerts)

    # ── Driver ────────────────────────────────────────────────────

    def get_driver(self, from_date=None, to_date=None):
        return self._cached("driver", self._repo.get_driver_analytics, from_date, to_date)

    # ── Document ──────────────────────────────────────────────────

    def get_document(self):
        return self._cached("docs", self._repo.get_document_analytics)

    # ── Analytics 2.0: Additional methods ─────────────────────────

    def get_monthly_financial(self, months: int = 24, from_date=None, to_date=None):
        return self._cached("monthly_fin", self._repo.get_monthly_financial_summary, months, from_date, to_date)

    def get_client_growth(self, months: int = 12, from_date=None, to_date=None):
        return self._cached("client_growth", self._repo.get_client_growth, months, from_date, to_date)

    def get_truck_utilization(self):
        return self._cached("truck_util", self._repo.get_truck_utilization)

    def get_document_upload_trend(self, months: int = 12):
        return self._cached("doc_trend", self._repo.get_document_upload_trend, months)

    def get_driver_tacho_violations(self):
        return self._cached("tacho_viol", self._repo.get_driver_tacho_violations)

    def get_profit_per_km_by_country(self):
        return self._cached("country_ppm", self._repo.get_profit_per_km_by_country)

    def get_revenue_concentration(self):
        return self._cached("rev_conc", self._repo.get_revenue_concentration)

    def get_driver_profit_per_km(self):
        return self._cached("driver_ppm", self._repo.get_driver_profit_per_km)

    # ── New Analytics 2.0: Phase 2 queries ──────────────────────────

    def get_trip_status_distribution(self, from_date=None, to_date=None):
        return self._cached("status_dist", self._repo.get_trip_status_distribution, from_date, to_date)

    def get_cost_breakdown(self, months: int = 12, from_date=None, to_date=None):
        return self._cached("cost_breakdown", self._repo.get_cost_breakdown, months, from_date, to_date)

    def get_monthly_trip_volume(self, months: int = 12, from_date=None, to_date=None):
        return self._cached("trip_volume", self._repo.get_monthly_trip_volume, months, from_date, to_date)

    def get_profit_vs_distance(self, limit: int = 100):
        return self._cached("profit_dist", self._repo.get_profit_vs_distance, limit)

    def get_truck_age_distribution(self):
        return self._cached("truck_age", self._repo.get_truck_age_distribution)

    def get_driver_efficiency_trend(self, months: int = 12):
        return self._cached("driver_eff_trend", self._repo.get_driver_efficiency_trend, months)

    def get_client_retention(self):
        return self._cached("client_retention", self._repo.get_client_retention)

    def get_revenue_quarterly(self, quarters: int = 8, from_date=None, to_date=None):
        return self._cached("rev_quarterly", self._repo.get_revenue_quarterly, quarters, from_date, to_date)

    def get_invoice_aging(self):
        return self._cached("invoice_aging", self._repo.get_invoice_aging)

    def get_client_payment_timeline(self, from_date=None, to_date=None):
        return self._cached("client_payment_tl", self._repo.get_client_payment_timeline, from_date, to_date)

    def get_driver_monthly_activity(self, months: int = 12, from_date=None, to_date=None):
        return self._cached("driver_monthly", self._repo.get_driver_monthly_activity, months, from_date, to_date)

    def get_driver_comparison(self, from_date=None, to_date=None):
        return self._cached("driver_comp", self._repo.get_driver_comparison, from_date, to_date)
