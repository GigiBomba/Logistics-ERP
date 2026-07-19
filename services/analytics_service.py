"""Comprehensive analytics service — fleet, financial, client, route, driver, document."""

import logging
import threading
import time
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

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

    def invalidate(self, company_id=None):
        with self._cache_lock:
            self._caches.clear()

    def _parse_dates(self, date_from: Optional[str] = None, date_to: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None):
        start = date_from if date_from is not None else from_date
        end = date_to if date_to is not None else to_date
        return start or None, end or None

    # ── Legacy (compat with old analytics_view) ──

    def get_data(self, company_id=None, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None) -> tuple:
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_data: from_date=%s, to_date=%s, source_provider=%s", from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("get_data", self._repo.get_analytics_data, from_date, to_date)
            logger.info("Analytics get_data returned %s items", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_data returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_data failed: from_date=%s, to_date=%s — %s", from_date, to_date, e, exc_info=True)
            raise

    # ── Financial ─────────────────────────────────────────────────

    def get_financial(self, company_id=None, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_financial: from_date=%s, to_date=%s, source_provider=%s", from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("financial", self._repo.get_financial_analytics, from_date, to_date)
            logger.info("Analytics get_financial completed")
            if not result:
                logger.warning("Analytics get_financial returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_financial failed: from_date=%s, to_date=%s — %s", from_date, to_date, e, exc_info=True)
            raise

    def get_revenue_by_client(self, company_id=None, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_revenue_by_client: from_date=%s, to_date=%s, source_provider=%s", from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("rev_client", self._repo.get_revenue_by_client, from_date, to_date)
            logger.info("Analytics get_revenue_by_client returned %s clients", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_revenue_by_client returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_revenue_by_client failed: from_date=%s, to_date=%s — %s", from_date, to_date, e, exc_info=True)
            raise

    def get_revenue_by_country(self, company_id=None, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_revenue_by_country: from_date=%s, to_date=%s, source_provider=%s", from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("rev_country", self._repo.get_revenue_by_country, from_date, to_date)
            logger.info("Analytics get_revenue_by_country returned %s countries", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_revenue_by_country returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_revenue_by_country failed: from_date=%s, to_date=%s — %s", from_date, to_date, e, exc_info=True)
            raise

    # ── Route ─────────────────────────────────────────────────────

    def get_route_profitability(self, company_id=None, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_route_profitability: from_date=%s, to_date=%s, source_provider=%s", from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("route_profit", self._repo.get_route_profitability, from_date, to_date)
            logger.info("Analytics get_route_profitability returned %s routes", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_route_profitability returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_route_profitability failed: from_date=%s, to_date=%s — %s", from_date, to_date, e, exc_info=True)
            raise

    # ── Client ────────────────────────────────────────────────────

    def get_client_analytics(self, company_id=None, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_client_analytics: from_date=%s, to_date=%s, source_provider=%s", from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("client", self._repo.get_client_analytics, from_date, to_date)
            logger.info("Analytics get_client_analytics returned %s clients", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_client_analytics returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_client_analytics failed: from_date=%s, to_date=%s — %s", from_date, to_date, e, exc_info=True)
            raise

    # ── Fleet ─────────────────────────────────────────────────────

    def get_fleet(self, company_id=None, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_fleet: from_date=%s, to_date=%s, source_provider=%s", from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("fleet", self._repo.get_fleet_analytics, from_date, to_date)
            logger.info("Analytics get_fleet returned %s trucks", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_fleet returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_fleet failed: from_date=%s, to_date=%s — %s", from_date, to_date, e, exc_info=True)
            raise

    def get_maintenance_alerts(self, company_id=None):
        logger.info("Analytics get_maintenance_alerts")
        try:
            result = self._cached("maint", self._repo.get_maintenance_alerts)
            logger.info("Analytics get_maintenance_alerts returned %s alerts", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_maintenance_alerts returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_maintenance_alerts failed — %s", e, exc_info=True)
            raise

    # ── Driver ────────────────────────────────────────────────────

    def get_driver(self, company_id=None, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_driver: from_date=%s, to_date=%s, source_provider=%s", from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("driver", self._repo.get_driver_analytics, from_date, to_date)
            logger.info("Analytics get_driver returned %s drivers", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_driver returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_driver failed: from_date=%s, to_date=%s — %s", from_date, to_date, e, exc_info=True)
            raise

    # ── Document ──────────────────────────────────────────────────

    def get_document(self, company_id=None):
        logger.info("Analytics get_document")
        try:
            result = self._cached("docs", self._repo.get_document_analytics)
            logger.info("Analytics get_document returned %s documents", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_document returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_document failed — %s", e, exc_info=True)
            raise

    # ── Analytics 2.0: Additional methods ─────────────────────────

    def get_monthly_financial(self, company_id=None, months: int = 24, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_monthly_financial: months=%s, from_date=%s, to_date=%s, source_provider=%s", months, from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("monthly_fin", self._repo.get_monthly_financial_summary, months, from_date, to_date)
            logger.info("Analytics get_monthly_financial returned %s months", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_monthly_financial returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_monthly_financial failed: months=%s, from_date=%s, to_date=%s — %s", months, from_date, to_date, e, exc_info=True)
            raise

    def get_client_growth(self, company_id=None, months: int = 12, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_client_growth: months=%s, from_date=%s, to_date=%s, source_provider=%s", months, from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("client_growth", self._repo.get_client_growth, months, from_date, to_date)
            logger.info("Analytics get_client_growth completed")
            if not result:
                logger.warning("Analytics get_client_growth returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_client_growth failed: months=%s, from_date=%s, to_date=%s — %s", months, from_date, to_date, e, exc_info=True)
            raise

    def get_truck_utilization(self, company_id=None):
        logger.info("Analytics get_truck_utilization")
        try:
            result = self._cached("truck_util", self._repo.get_truck_utilization)
            logger.info("Analytics get_truck_utilization returned %s trucks", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_truck_utilization returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_truck_utilization failed — %s", e, exc_info=True)
            raise

    def get_document_upload_trend(self, company_id=None, months: int = 12):
        logger.info("Analytics get_document_upload_trend: months=%s", months)
        try:
            result = self._cached("doc_trend", self._repo.get_document_upload_trend, months)
            logger.info("Analytics get_document_upload_trend returned %s entries", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_document_upload_trend returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_document_upload_trend failed: months=%s — %s", months, e, exc_info=True)
            raise

    def get_driver_tacho_violations(self, company_id=None):
        logger.info("Analytics get_driver_tacho_violations")
        try:
            result = self._cached("tacho_viol", self._repo.get_driver_tacho_violations)
            logger.info("Analytics get_driver_tacho_violations returned %s violations", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_driver_tacho_violations returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_driver_tacho_violations failed — %s", e, exc_info=True)
            raise

    def get_profit_per_km_by_country(self, company_id=None):
        logger.info("Analytics get_profit_per_km_by_country")
        try:
            result = self._cached("country_ppm", self._repo.get_profit_per_km_by_country)
            logger.info("Analytics get_profit_per_km_by_country returned %s countries", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_profit_per_km_by_country returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_profit_per_km_by_country failed — %s", e, exc_info=True)
            raise

    def get_revenue_concentration(self, company_id=None):
        logger.info("Analytics get_revenue_concentration")
        try:
            result = self._cached("rev_conc", self._repo.get_revenue_concentration)
            logger.info("Analytics get_revenue_concentration returned %s entries", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_revenue_concentration returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_revenue_concentration failed — %s", e, exc_info=True)
            raise

    def get_driver_profit_per_km(self, company_id=None):
        logger.info("Analytics get_driver_profit_per_km")
        try:
            result = self._cached("driver_ppm", self._repo.get_driver_profit_per_km)
            logger.info("Analytics get_driver_profit_per_km returned %s drivers", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_driver_profit_per_km returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_driver_profit_per_km failed — %s", e, exc_info=True)
            raise

    # ── New Analytics 2.0: Phase 2 queries ──────────────────────────

    def get_trip_status_distribution(self, company_id=None, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_trip_status_distribution: from_date=%s, to_date=%s, source_provider=%s", from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("status_dist", self._repo.get_trip_status_distribution, from_date, to_date)
            logger.info("Analytics get_trip_status_distribution returned %s statuses", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_trip_status_distribution returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_trip_status_distribution failed: from_date=%s, to_date=%s — %s", from_date, to_date, e, exc_info=True)
            raise

    def get_cost_breakdown(self, company_id=None, months: int = 12, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_cost_breakdown: months=%s, from_date=%s, to_date=%s, source_provider=%s", months, from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("cost_breakdown", self._repo.get_cost_breakdown, months, from_date, to_date)
            logger.info("Analytics get_cost_breakdown returned %s entries", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_cost_breakdown returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_cost_breakdown failed: months=%s, from_date=%s, to_date=%s — %s", months, from_date, to_date, e, exc_info=True)
            raise

    def get_monthly_trip_volume(self, company_id=None, months: int = 12, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_monthly_trip_volume: months=%s, from_date=%s, to_date=%s, source_provider=%s", months, from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("trip_volume", self._repo.get_monthly_trip_volume, months, from_date, to_date)
            logger.info("Analytics get_monthly_trip_volume returned %s months", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_monthly_trip_volume returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_monthly_trip_volume failed: months=%s, from_date=%s, to_date=%s — %s", months, from_date, to_date, e, exc_info=True)
            raise

    def get_profit_vs_distance(self, company_id=None, limit: int = 100):
        logger.info("Analytics get_profit_vs_distance: limit=%s", limit)
        try:
            result = self._cached("profit_dist", self._repo.get_profit_vs_distance, limit)
            logger.info("Analytics get_profit_vs_distance returned %s trips", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_profit_vs_distance returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_profit_vs_distance failed: limit=%s — %s", limit, e, exc_info=True)
            raise

    def get_truck_age_distribution(self):
        logger.info("Analytics get_truck_age_distribution")
        try:
            result = self._cached("truck_age", self._repo.get_truck_age_distribution)
            logger.info("Analytics get_truck_age_distribution returned %s trucks", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_truck_age_distribution returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_truck_age_distribution failed — %s", e, exc_info=True)
            raise

    def get_driver_efficiency_trend(self, months: int = 12):
        logger.info("Analytics get_driver_efficiency_trend: months=%s", months)
        try:
            result = self._cached("driver_eff_trend", self._repo.get_driver_efficiency_trend, months)
            logger.info("Analytics get_driver_efficiency_trend returned %s entries", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_driver_efficiency_trend returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_driver_efficiency_trend failed: months=%s — %s", months, e, exc_info=True)
            raise

    def get_client_retention(self, company_id=None):
        logger.info("Analytics get_client_retention")
        try:
            result = self._cached("client_retention", self._repo.get_client_retention)
            logger.info("Analytics get_client_retention returned %s entries", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_client_retention returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_client_retention failed — %s", e, exc_info=True)
            raise

    def get_revenue_quarterly(self, company_id=None, quarters: int = 8, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_revenue_quarterly: quarters=%s, from_date=%s, to_date=%s, source_provider=%s", quarters, from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("rev_quarterly", self._repo.get_revenue_quarterly, quarters, from_date, to_date)
            logger.info("Analytics get_revenue_quarterly returned %s quarters", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_revenue_quarterly returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_revenue_quarterly failed: quarters=%s, from_date=%s, to_date=%s — %s", quarters, from_date, to_date, e, exc_info=True)
            raise

    def get_invoice_aging(self, company_id=None):
        logger.info("Analytics get_invoice_aging")
        try:
            result = self._cached("invoice_aging", self._repo.get_invoice_aging)
            logger.info("Analytics get_invoice_aging returned %s entries", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_invoice_aging returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_invoice_aging failed — %s", e, exc_info=True)
            raise

    def get_client_payment_timeline(self, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_client_payment_timeline: from_date=%s, to_date=%s, source_provider=%s", from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("client_payment_tl", self._repo.get_client_payment_timeline, from_date, to_date)
            logger.info("Analytics get_client_payment_timeline returned %s entries", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_client_payment_timeline returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_client_payment_timeline failed: from_date=%s, to_date=%s — %s", from_date, to_date, e, exc_info=True)
            raise

    def get_driver_monthly_activity(self, company_id=None, months: int = 12, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_driver_monthly_activity: months=%s, from_date=%s, to_date=%s, source_provider=%s", months, from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("driver_monthly", self._repo.get_driver_monthly_activity, months, from_date, to_date)
            logger.info("Analytics get_driver_monthly_activity returned %s entries", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_driver_monthly_activity returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_driver_monthly_activity failed: months=%s, from_date=%s, to_date=%s — %s", months, from_date, to_date, e, exc_info=True)
            raise

    def get_driver_comparison(self, company_id=None, date_from=None, date_to=None, from_date=None, to_date=None, source_provider=None):
        from_date = date_from if date_from is not None else from_date
        to_date = date_to if date_to is not None else to_date
        logger.info("Analytics get_driver_comparison: from_date=%s, to_date=%s, source_provider=%s", from_date, to_date, source_provider)

        # Build conditions with source provider filter
        conditions = []
        params: list = []
        if from_date:
            conditions.append("t.created_at >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("t.created_at <= ?")
            params.append(to_date)
        if source_provider:
            if source_provider == "freight_exchange":
                conditions.append("t.source = 'freight_exchange'")
            else:
                conditions.append("t.source_provider_id = ?")
                params.append(source_provider)

        try:
            result = self._cached("driver_comp", self._repo.get_driver_comparison, from_date, to_date)
            logger.info("Analytics get_driver_comparison returned %s drivers", len(result) if result else 0)
            if not result:
                logger.warning("Analytics get_driver_comparison returned empty result")
            return result
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("Analytics get_driver_comparison failed: from_date=%s, to_date=%s — %s", from_date, to_date, e, exc_info=True)
            raise

    # ── Overdue / Alerts ─────────────────────────────────────────────

    def get_overdue_data(self):
        """Fetch overdue invoice data and return formatted alerts with total.

        Business logic formerly in AnalyticsRepository.get_overdue_data()
        has been moved here: alert-type classification, message formatting,
        and aggregation of the total overdue amount.

        Returns:
            tuple[list[dict], float]:
                - alerts: list of {"type": "RED"|"YELLOW", "msg": str}
                - total_overdue_amount: sum of overdue invoice amounts
        """
        try:
            overdue_rows, neg_margin_rows = self._repo.get_overdue_data()
        except (ValueError, RuntimeError, TypeError) as e:
            logger.error("get_overdue_data: failed to fetch raw data — %s", e, exc_info=True)
            return [], 0.0

        today = datetime.now()
        alerts: list[dict] = []
        total_overdue_amount = 0.0

        # ── Process overdue invoices ─────────────────────────────────
        for r in overdue_rows:
            days_late = r.get("days_late")
            if days_late is None:
                logger.debug("get_overdue_data: skipping row with missing days_late (inv=%s)", r.get("invoice_number"))
                continue

            if days_late > 0:
                # Overdue → RED alert
                total_overdue_amount += r["total_amount"]
                alerts.append({
                    "type": "RED",
                    "msg": f"Factura {r['invoice_number']} ({r['client_name']}) intarziata cu {days_late} zile!",
                })
            elif days_late >= -3:
                # Due within 3 days → YELLOW alert
                alerts.append({
                    "type": "YELLOW",
                    "msg": f"Factura {r['invoice_number']} expira in {-days_late} zile.",
                })

        # ── Process negative-margin trips ────────────────────────────
        for nm in neg_margin_rows:
            alerts.append({
                "type": "RED",
                "msg": f"ATENTIE: Cursa #{nm['id']} ({nm['truck_number']}) are profit NEGATIV!",
            })

        logger.info(
            "get_overdue_data: %d overdue invoices processed, "
            "%d negative-margin alerts, total_overdue_amount=%.2f",
            len(overdue_rows),
            len(neg_margin_rows),
            total_overdue_amount,
        )

        return alerts, total_overdue_amount
