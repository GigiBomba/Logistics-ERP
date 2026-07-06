"""API-backed analytics service wrapper for remote-only client mode.

Mirrors ``services.analytics_service.AnalyticsService`` so that views
can call ``get_financial()``, ``get_fleet()``, etc. without knowing
whether they're talking to a local DB or a remote API.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("remote_analytics")


class RemoteAnalyticsService:
    """API-backed substitute for ``AnalyticsService``.

    Every method delegates to the corresponding ``ApiClient`` method.
    The public API (method names, parameter signatures, return types)
    matches the local ``AnalyticsService`` exactly.
    """

    def __init__(self, api_client) -> None:
        self._api = api_client

    def get_data(self, from_date: Optional[str] = None,
                 to_date: Optional[str] = None) -> dict:
        return self._api.get_analytics_overview()

    def get_financial(self, from_date: Optional[str] = None,
                      to_date: Optional[str] = None):
        return self._api.get_analytics_financial(
            from_date=from_date or "", to_date=to_date or "")

    def get_revenue_by_client(self, from_date: Optional[str] = None,
                              to_date: Optional[str] = None):
        return self._api.get_analytics_revenue_by_client(
            from_date=from_date or "", to_date=to_date or "")

    def get_revenue_by_country(self, from_date: Optional[str] = None,
                               to_date: Optional[str] = None):
        return self._api.get_analytics_financial_by_country(
            from_date=from_date or "", to_date=to_date or "")

    def get_route_profitability(self, from_date: Optional[str] = None,
                                to_date: Optional[str] = None):
        return self._api.get_analytics_route_profitability(
            from_date=from_date or "", to_date=to_date or "")

    def get_client_analytics(self, from_date: Optional[str] = None,
                             to_date: Optional[str] = None):
        return self._api.get_analytics_client(
            from_date=from_date or "", to_date=to_date or "")

    def get_fleet(self, from_date: Optional[str] = None,
                  to_date: Optional[str] = None):
        return self._api.get_analytics_fleet(
            from_date=from_date or "", to_date=to_date or "")

    def get_maintenance_alerts(self):
        return self._api.get_analytics_maintenance_alerts()

    def get_driver(self, from_date: Optional[str] = None,
                   to_date: Optional[str] = None):
        return self._api.get_analytics_driver(
            from_date=from_date or "", to_date=to_date or "")

    def get_document(self):
        return self._api.get_analytics_document()

    def get_monthly_financial(self, months: int = 24,
                              from_date: Optional[str] = None,
                              to_date: Optional[str] = None):
        return self._api.get_analytics_financial_monthly(
            months=months, from_date=from_date or "", to_date=to_date or "")

    def get_client_growth(self, months: int = 12,
                          from_date: Optional[str] = None,
                          to_date: Optional[str] = None):
        return self._api.get_analytics_client_growth(
            months=months, from_date=from_date or "", to_date=to_date or "")

    def get_truck_utilization(self):
        return self._api.get_analytics_fleet_utilization()

    def get_document_upload_trend(self, months: int = 12):
        return self._api.get_analytics_document_upload_trend(months=months)

    def get_driver_tacho_violations(self):
        return self._api.get_analytics_driver_violations()

    def get_profit_per_km_by_country(self):
        return self._api.get_analytics_route_by_country()

    def get_revenue_concentration(self):
        return self._api.get_analytics_client_concentration()

    def get_driver_profit_per_km(self):
        return self._api.get_analytics_driver_profit_per_km()

    def get_trip_status_distribution(self, from_date: Optional[str] = None,
                                     to_date: Optional[str] = None):
        return self._api.get_analytics_financial_trip_status(
            from_date=from_date or "", to_date=to_date or "")

    def get_cost_breakdown(self, months: int = 12,
                           from_date: Optional[str] = None,
                           to_date: Optional[str] = None):
        return self._api.get_analytics_financial_cost_breakdown(
            months=months, from_date=from_date or "", to_date=to_date or "")

    def get_monthly_trip_volume(self, months: int = 12,
                                from_date: Optional[str] = None,
                                to_date: Optional[str] = None):
        return self._api.get_analytics_financial_trip_volume(
            months=months, from_date=from_date or "", to_date=to_date or "")

    def get_profit_vs_distance(self, limit: int = 100):
        return self._api.get_analytics_route_profit_vs_distance(limit=limit)

    def get_truck_age_distribution(self):
        return self._api._get("/api/v1/analytics/fleet/utilization")

    def get_driver_efficiency_trend(self, months: int = 12):
        return self._api.get_analytics_driver_monthly_activity(months=months)

    def get_client_retention(self):
        return self._api.get_analytics_client_retention()

    def get_revenue_quarterly(self, quarters: int = 8,
                              from_date: Optional[str] = None,
                              to_date: Optional[str] = None):
        return self._api.get_analytics_financial_quarterly(
            quarters=quarters, from_date=from_date or "", to_date=to_date or "")

    def get_invoice_aging(self):
        return self._api.get_analytics_financial_invoice_aging()

    def get_client_payment_timeline(self, from_date: Optional[str] = None,
                                    to_date: Optional[str] = None):
        return self._api.get_analytics_revenue_by_client(
            from_date=from_date or "", to_date=to_date or "")

    def get_driver_monthly_activity(self, months: int = 12,
                                    from_date: Optional[str] = None,
                                    to_date: Optional[str] = None):
        return self._api.get_analytics_driver_monthly_activity(
            months=months, from_date=from_date or "", to_date=to_date or "")

    def get_driver_comparison(self, from_date: Optional[str] = None,
                              to_date: Optional[str] = None):
        return self._api.get_analytics_driver_comparison(
            from_date=from_date or "", to_date=to_date or "")

    def invalidate(self):
        self._api.invalidate_analytics_cache()
