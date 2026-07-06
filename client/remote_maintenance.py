"""API-backed maintenance service wrapper for remote-only client mode.

Mirrors the maintenance-related methods of ``FleetRepository`` so views
can fetch maintenance costs, summaries, and categories via the API.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("remote_maintenance")


class RemoteMaintenanceService:
    """API-backed substitute for FleetRepository maintenance methods."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    def get_summary(self) -> dict:
        return self._api.get_maintenance_summary()

    def get_cost_monthly(self, since: str = "") -> dict:
        return self._api.get_maintenance_cost_monthly(since=since)

    def get_cost_by_truck_monthly(self, since: str = "") -> dict:
        return self._api.get_maintenance_cost_by_truck_monthly(since=since)

    def get_truck_summary(self, since: str = "") -> dict:
        return self._api.get_maintenance_truck_summary(since=since)

    def get_top_categories(self, since: str = "") -> dict:
        return self._api.get_maintenance_top_categories(since=since)

    def get_all(self) -> list:
        try:
            resp = self._api.list_trucks()
            return resp.get("items", []) if resp else []
        except Exception:
            return []
