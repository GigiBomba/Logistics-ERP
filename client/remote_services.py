"""API-backed service wrappers for remote-only client mode.

Mirror the public APIs of ``FleetService``, ``TripService``, and
``ClientService`` so that ``MainWindow._init_services()`` can create
these in place of the DB-backed originals when ``db=None``.

Usage::

    from client.api_client import ApiClient
    from client.remote_services import RemoteFleetService
    api = ApiClient()
    fleet = RemoteFleetService(api)
    trucks = fleet.get_trucks()
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("remote_services")


class RemoteFleetService:
    """API-backed substitute for ``services.fleet_service.FleetService``."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    def get_trucks(self) -> list:
        resp = self._api.list_trucks()
        return resp.get("items", []) if resp else []

    def get_truck(self, truck_id: int) -> Optional[dict]:
        try:
            return self._api.get_truck(truck_id)
        except Exception:
            return None

    def add_truck(self, data: dict) -> int:
        try:
            resp = self._api._post("/api/v1/fleet/trucks", json_data=data)
            return resp.get("id", 0)
        except Exception:
            return 0

    def update_truck(self, truck_id: int, data: dict) -> None:
        self._api._put(f"/api/v1/fleet/trucks/{truck_id}", json_data=data)

    def delete_truck(self, truck_id: int) -> None:
        self._api._delete(f"/api/v1/fleet/trucks/{truck_id}")


class RemoteTripService:
    """API-backed substitute for ``services.trip_service.TripService``."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    def get_filtered(self, search: str = "", status: str = "", limit: int = 200) -> list:
        resp = self._api.list_trips(search=search, status=status, limit=limit)
        return resp.get("items", []) if resp else []

    def get_by_id(self, trip_id: int) -> Optional[dict]:
        try:
            return self._api.get_trip(trip_id)
        except Exception:
            return None

    def get_all(self, limit: int = 500) -> list:
        return self.get_filtered(limit=limit)

    def get_by_statuses(self, statuses: list) -> list:
        status_set = set(statuses)
        result: list = []
        seen: set = set()
        for st in statuses:
            for t in self.get_filtered(status=st, limit=1000):
                tid = t.get("id")
                if tid is not None and tid not in seen and t.get("status") in status_set:
                    seen.add(tid)
                    result.append(t)
        return result


class RemoteClientService:
    """API-backed substitute for ``services.client_service.ClientService``."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    def get_all(self, include_inactive: bool = False) -> list:
        resp = self._api.list_clients(limit=1000)
        return resp.get("items", []) if resp else []

    def get_by_id(self, client_id: int) -> Optional[dict]:
        try:
            return self._api.get_client(client_id)
        except Exception:
            return None

    def search(self, query: str, limit: int = 20) -> list:
        resp = self._api.list_clients(query=query, limit=limit)
        return resp.get("items", []) if resp else []

    def search_advanced(self, query: str, include_inactive: bool = False, limit: int = 200) -> list:
        return self.search(query, limit=limit)

    def create(self, name: str, **kwargs) -> int:
        try:
            resp = self._api._post("/api/v1/clients/", json_data={"name": name, "data": kwargs})
            return resp.get("id", 0)
        except Exception:
            return 0

    def update(self, client_id: int, **kwargs) -> None:
        self._api._put(f"/api/v1/clients/{client_id}", json_data=kwargs)

    def get_all_with_revenue(self, include_inactive: bool = False) -> list:
        clients = self.get_all(include_inactive=include_inactive)
        for c in clients:
            cid = c.get("id")
            if cid:
                dash = self.get_client_dashboard(cid)
                c["revenue"] = dash.get("revenue", 0)
                c["trip_count"] = dash.get("trip_count", 0)
        return clients

    def get_client_dashboard(self, client_id: int) -> dict:
        try:
            return self._api._get(f"/api/v1/clients/{client_id}/dashboard")
        except Exception:
            return {}
