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

import json
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

    def get_by_statuses(self, statuses: list, limit: Optional[int] = None) -> list:
        status_set = set(statuses)
        result: list = []
        seen: set = set()
        for st in statuses:
            for t in self.get_filtered(status=st, limit=limit if limit is not None else 1000):
                tid = t.get("id")
                if tid is not None and tid not in seen and t.get("status") in status_set:
                    seen.add(tid)
                    result.append(t)
        return result

    def get_top_trucks_by_revenue(self, month_start: str, month_end: str, limit: int = 4) -> list:
        resp = self._api.get_top_trucks_by_revenue(month_start, month_end, limit)
        return resp.get("items", []) if resp else []

    def delete(self, trip_id: int) -> bool:
        """Delete a trip via ``DELETE /trips/{trip_id}`` (backend-supported).

        Returns ``True`` on success, ``False`` if the API raised (mirrors
        the boolean contract the local ``TripService.delete`` exposes through
        ``ServiceResult.success``).
        """
        try:
            self._api.delete_trip(trip_id)
            return True
        except Exception:
            logger.debug("delete_trip(%s) failed", trip_id, exc_info=True)
            return False

    def get_route_stops_json(self, trip_id: int) -> Optional[str]:
        """Return the route stops for *trip_id* as a JSON **string**.

        Route data lives in ``route_history_v2.stops_json`` (linked via
        ``trips.route_history_v2_id``), so the stops are resolved through
        ``GET /dispatch/trips/{trip_id}/detail``, whose ``stops`` field
        carries the parsed stop objects.  Returns ``None`` when the trip has
        no route / stops, or on any API/HTTP error.

        NOTE: mirrors the local ``TripService.get_route_stops_json``
        contract, which returns a JSON string that callers ``json.loads()``.
        """
        try:
            resp = self._api._get(f"/api/v1/dispatch/trips/{trip_id}/detail")
        except Exception:
            return None
        if not isinstance(resp, dict):
            return None
        stops = resp.get("stops")
        if isinstance(stops, list):
            try:
                return json.dumps(stops)
            except Exception:
                return None
        return None


class RemoteClientService:
    """API-backed substitute for ``services.client_service.ClientService``."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    def get_all(self, include_inactive: bool = False) -> list:
        resp = self._api.list_clients(limit=1000, include_inactive=include_inactive)
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
        resp = self._api.list_clients(
            query=query, limit=limit, include_inactive=include_inactive,
        )
        return resp.get("items", []) if resp else []

    def create(self, name: str, **kwargs) -> int:
        try:
            # Flat payload matching ClientCreateRequest (extra="forbid").
            resp = self._api._post("/api/v1/clients/", json_data={"name": name, **kwargs})
            return resp.get("id", 0)
        except Exception:
            return 0

    def update(self, client_id: int, **kwargs) -> None:
        self._api._put(f"/api/v1/clients/{client_id}", json_data=kwargs)

    def get_all_with_revenue(self, include_inactive: bool = False) -> list:
        # Page through the API (backend caps page_size at 200) up to the
        # local LIMIT 500 parity cap, then enrich each client with its
        # dashboard revenue/trip_count. The backend does not truly slice the
        # no-query path, so dedupe by id and stop on a no-progress page.
        all_clients: list = []
        seen_ids: set = set()
        page = 1
        page_size = 200
        while len(all_clients) < 500:
            resp = self._api.list_clients(
                include_inactive=include_inactive, page=page, page_size=page_size,
            )
            items = resp.get("items", []) if resp else []
            if not items:
                break
            added = 0
            for c in items:
                cid = c.get("id")
                if cid is not None and cid in seen_ids:
                    continue
                if cid is not None:
                    seen_ids.add(cid)
                all_clients.append(c)
                added += 1
            if added == 0:
                # Re-returned an already-seen page — no further progress.
                break
            if len(items) < page_size:
                break
            page += 1
        for c in all_clients:
            cid = c.get("id")
            if cid:
                dash = self.get_client_dashboard(cid)
                # The backend dashboard exposes total_revenue/total_trips;
                # fall back to the short keys so both shapes are handled.
                c["revenue"] = dash.get("revenue", dash.get("total_revenue", 0))
                c["trip_count"] = dash.get("trip_count", dash.get("total_trips", 0))
        return all_clients

    def get_client_dashboard(self, client_id: int) -> dict:
        try:
            return self._api._get(f"/api/v1/clients/{client_id}/dashboard")
        except Exception:
            return {}

    def get_client_trips(self, client_id: int, limit: int = 100) -> list:
        resp = self._api.get_client_trips(client_id, limit=limit)
        return resp.get("items", []) if resp else []

    def get_client_invoices(self, client_id: int, limit: int = 100) -> list:
        resp = self._api.get_client_invoices(client_id, limit=limit)
        return resp.get("items", []) if resp else []

    def get_trip_count(self, client_id: int) -> int:
        resp = self._api.get_client_trip_count(client_id)
        return resp.get("count", 0) if resp else 0

    def deactivate(self, client_id: int) -> None:
        self._api.deactivate_client(client_id)

    def get_client_revenue_history(self, client_id: int, months: int = 12) -> list:
        resp = self._api.get_client_revenue_history(client_id, months=months)
        return resp if resp else []

    def merge_clients(self, from_id: int, to_id: int) -> dict:
        return self._api.merge_clients(from_id, to_id)

    def get_contacts(self, client_id: int) -> list:
        resp = self._api.get_client_contacts(client_id)
        return resp.get("items", []) if resp else []

    def add_contact(self, client_id: int, data: Optional[dict] = None, **kwargs) -> int:
        try:
            payload = dict(data or {})
            payload.update(kwargs)
            resp = self._api.add_client_contact(client_id, payload)
            return resp.get("id", 0)
        except Exception:
            return 0

    def update_contact(self, contact_id: int, **kwargs) -> None:
        self._api.update_client_contact(contact_id, kwargs)

    def delete_contact(self, contact_id: int) -> None:
        self._api.delete_client_contact(contact_id)

    def add_tag(self, client_id: int, tag: str) -> None:
        self._api.add_client_tag(client_id, tag)

    def get_payment_summary(self, client_id: int) -> dict:
        resp = self._api.get_client_payment_summary(client_id)
        return resp if resp else {}
