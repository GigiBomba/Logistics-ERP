"""API-backed driver service wrapper for remote-only client mode.

Mirrors ``services.driver_truck_service.DriverTruckService`` and
``repositories.driver_repository.DriverRepository`` so views can
perform driver CRUD and driver-truck assignment through the API.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("remote_driver")


class RemoteDriverService:
    """API-backed substitute for DriverRepository + DriverTruckService."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    def get_all(self, limit: int = 500, offset: int = 0) -> list:
        resp = self._api.list_drivers(limit=limit, offset=offset)
        return resp.get("items", []) if resp else []

    def get_by_id(self, driver_id: int) -> Optional[dict]:
        try:
            return self._api.get_driver(driver_id)
        except Exception:
            return None

    def create(self, data: dict) -> int:
        try:
            resp = self._api.create_driver(data)
            return resp.get("id", 0)
        except Exception:
            return 0

    def update(self, driver_id: int, data: dict) -> None:
        self._api.update_driver(driver_id, data)

    def delete(self, driver_id: int) -> None:
        self._api.delete_driver(driver_id)

    def assign_driver_to_truck(self, driver_id: int, truck_id: int) -> dict:
        return self._api.assign_driver_to_truck(driver_id, truck_id)

    def unassign_driver(self, driver_id: int) -> Optional[int]:
        try:
            resp = self._api.unassign_driver(driver_id)
            return resp.get("truck_id")
        except Exception:
            return None

    def get_truck_plate_for_driver(self, driver_id: int) -> str:
        try:
            resp = self._api.get_driver_truck_plate(driver_id)
            return resp.get("plate", "")
        except Exception:
            return ""

    def get_driver_name_for_truck(self, truck_id: int) -> str:
        try:
            result = self._api._get(f"/api/v1/drivers/by-truck/{truck_id}")
            return result.get("name", "")
        except Exception:
            return ""

    def get_tacho_activity(self, driver_id: int, from_date: str = "",
                           limit: int = 100) -> list:
        resp = self._api.get_driver_tacho_activity(
            driver_id, from_date=from_date, limit=limit)
        return resp.get("items", []) if resp else []

    def get_plates_by_driver_ids(self, driver_ids: list) -> dict:
        """Return ``{driver_id: plate}`` for the given driver ids.

        Mirrors ``DriverTruckAssignmentRepository.get_plates_by_driver_ids``.
        No bulk endpoint exists on the backend, so this composes one
        ``GET /drivers/{id}/truck-plate`` call per driver id; drivers that
        have no truck / fail to resolve map to ``""``.
        """
        result: dict = {}
        for did in driver_ids or []:
            try:
                resp = self._api.get_driver_truck_plate(did)
                plate = resp.get("plate", "") if isinstance(resp, dict) else ""
            except Exception:
                plate = ""
            result[did] = plate
        return result

    def get_active_trucks(self) -> list:
        """Return the active truck list.

        The backend exposes only ``GET /fleet/trucks`` (no active-only
        filter), so trucks are filtered client-side on ``is_active``
        (``active_status`` is honoured as a fallback key for local-shaped
        rows).
        """
        try:
            resp = self._api.list_trucks()
        except Exception:
            return []
        items = resp.get("items", []) if isinstance(resp, dict) else (resp or [])
        result = []
        for truck in items:
            if not isinstance(truck, dict):
                continue
            if truck.get("is_active", truck.get("active_status", 0)):
                result.append(truck)
        return result
