"""Comprehensive analytics service — fleet, financial, client, route, driver, document."""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class AnalyticsService:
    CACHE_TTL = 30.0

    def __init__(self, db):
        self.db = db
        self._caches: Dict[str, Tuple[Any, float, Tuple]] = {}

    def _cached(self, cache_key: str, func, *args):
        now = time.time()
        cache_entry = self._caches.get(cache_key)
        if cache_entry:
            data, ts, ck = cache_entry
            if ck == args and (now - ts) < self.CACHE_TTL:
                return data
        result = func(*args)
        self._caches[cache_key] = (result, now, args)
        return result

    def invalidate(self):
        self._caches.clear()

    def _parse_dates(self, from_date: Optional[str], to_date: Optional[str]):
        from_d = from_date or None
        to_d = to_date or None
        return from_d, to_d

    # ── Legacy (compat with old analytics_view) ──

    def get_data(self, from_date=None, to_date=None) -> tuple:
        return self._cached("get_data", self.db.get_analytics_data, from_date, to_date)

    # ── Financial ─────────────────────────────────────────────────

    def get_financial(self, from_date=None, to_date=None):
        return self._cached("financial", self.db.get_financial_analytics, from_date, to_date)

    def get_revenue_by_client(self, from_date=None, to_date=None):
        return self._cached("rev_client", self.db.get_revenue_by_client, from_date, to_date)

    def get_revenue_by_country(self, from_date=None, to_date=None):
        return self._cached("rev_country", self.db.get_revenue_by_country, from_date, to_date)

    # ── Route ─────────────────────────────────────────────────────

    def get_route_profitability(self, from_date=None, to_date=None):
        return self._cached("route_profit", self.db.get_route_profitability, from_date, to_date)

    # ── Client ────────────────────────────────────────────────────

    def get_client_analytics(self, from_date=None, to_date=None):
        return self._cached("client", self.db.get_client_analytics, from_date, to_date)

    # ── Fleet ─────────────────────────────────────────────────────

    def get_fleet(self, from_date=None, to_date=None):
        return self._cached("fleet", self.db.get_fleet_analytics, from_date, to_date)

    def get_maintenance_alerts(self):
        return self._cached("maint", self.db.get_maintenance_alerts)

    # ── Driver ────────────────────────────────────────────────────

    def get_driver(self, from_date=None, to_date=None):
        return self._cached("driver", self.db.get_driver_analytics, from_date, to_date)

    # ── Document ──────────────────────────────────────────────────

    def get_document(self):
        return self._cached("docs", self.db.get_document_analytics)

    # ── Analytics 2.0: Additional methods ─────────────────────────

    def get_monthly_financial(self, months: int = 24):
        return self._cached("monthly_fin", self.db.get_monthly_financial_summary, months)

    def get_client_growth(self, months: int = 12):
        return self._cached("client_growth", self.db.get_client_growth, months)

    def get_truck_utilization(self):
        return self._cached("truck_util", self.db.get_truck_utilization)

    def get_document_upload_trend(self, months: int = 12):
        return self._cached("doc_trend", self.db.get_document_upload_trend, months)

    def get_driver_tacho_violations(self):
        return self._cached("tacho_viol", self.db.get_driver_tacho_violations)

    def get_profit_per_km_by_country(self):
        return self._cached("country_ppm", self.db.get_profit_per_km_by_country)

    def get_revenue_concentration(self):
        return self._cached("rev_conc", self.db.get_revenue_concentration)

    def get_driver_profit_per_km(self):
        return self._cached("driver_ppm", self.db.get_driver_profit_per_km)
