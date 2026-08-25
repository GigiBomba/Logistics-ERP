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

    def get_cost_monthly(self, date_from: str = "") -> dict:
        return self._api.get_maintenance_cost_monthly(date_from=date_from)

    def get_cost_by_truck_monthly(self, date_from: str = "") -> dict:
        return self._api.get_maintenance_cost_by_truck_monthly(date_from=date_from)

    def get_truck_summary(self, date_from: str = "") -> dict:
        return self._api.get_maintenance_truck_summary(date_from=date_from)

    def get_top_categories(self, date_from: str = "") -> dict:
        return self._api.get_maintenance_top_categories(date_from=date_from)

    def get_all(self) -> list:
        try:
            resp = self._api.list_trucks()
            return resp.get("items", []) if resp else []
        except Exception:
            return []

    # ── View-facing aliases (maintenance analytics view) ─────────────────
    # The maintenance analytics view calls the local ``FleetRepository``
    # method names; the backend endpoints wrap the rows in ``{"data": [...]}``
    # so these aliases unwrap them into plain lists.

    def get_maintenance_cost_truck_monthly(self, date_from: str = "") -> list:
        resp = self._api.get_maintenance_cost_by_truck_monthly(date_from=date_from)
        return resp.get("data", []) if resp else []

    def get_maintenance_cost_monthly(self, date_from: str = "") -> list:
        resp = self._api.get_maintenance_cost_monthly(date_from=date_from)
        return resp.get("data", []) if resp else []

    def get_maintenance_truck_summary(self, date_from: str = "") -> list:
        resp = self._api.get_maintenance_truck_summary(date_from=date_from)
        return resp.get("data", []) if resp else []

    def get_maintenance_most_expensive_category(self, date_from: str = "") -> list:
        resp = self._api.get_maintenance_top_categories(date_from=date_from)
        return resp.get("data", []) if resp else []
