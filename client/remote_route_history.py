"""API-backed route history service wrapper for remote-only client mode.

Mirrors ``services.route_history_service.RouteHistoryService``.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("remote_route_history")


class RemoteRouteHistoryService:
    """API-backed substitute for RouteHistoryService."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    def search_routes(self, search: str = "", truck: str = "",
                       profile: str = "", include_archived: bool = False,
                       sort_by: str = "", sort_dir: str = "") -> list:
        resp = self._api.list_route_history(limit=200)
        items = resp.get("items", [])
        if search:
            items = [i for i in items if search.lower() in str(i).lower()]
        return items

    def load_route(self, route_id: int) -> Optional[dict]:
        try:
            return self._api.get_route_history(route_id)
        except Exception:
            return None

    def get_statistics(self, include_archived: bool = False) -> dict:
        return self._api.get_route_statistics()

    def duplicate_route(self, route_id: int) -> Optional[int]:
        try:
            resp = self._api.duplicate_route(route_id)
            return resp.get("new_route_id")
        except Exception:
            return None

    def archive_route(self, route_id: int) -> bool:
        try:
            self._api.archive_route(route_id)
            return True
        except Exception:
            return False

    def delete_route(self, route_id: int) -> bool:
        try:
            self._api.delete_route_history(route_id)
            return True
        except Exception:
            return False

    def export_route(self, route_id: int, fmt: str = "json") -> Any:
        return self._api.export_route(route_id, fmt=fmt)
