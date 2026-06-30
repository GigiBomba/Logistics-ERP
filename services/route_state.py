"""Central route state management for ERP-wide route synchronization."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any

from services.route_history_service import RouteEventBus, RouteHistoryRecord, RouteHistoryService
from services.trip_context import TripContextService

@dataclass
class ActiveRouteState:
    route_id: int | None = None
    route: RouteHistoryRecord | None = None


class RouteStateManager:
    """Coordinates active route state, events, calculator sync, and fleet hooks."""

    _instances: dict[int, RouteStateManager] = {}

    def __new__(cls, db):
        key = id(getattr(db, "conn", db))
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls)
            cls._instances[key]._initialized = False
        return cls._instances[key]

    def __init__(self, db) -> None:
        if getattr(self, "_initialized", False):
            return
        self.db = db
        self.history = RouteHistoryService(db)
        self.trip_context = TripContextService()
        self._state = ActiveRouteState()
        self._initialized = True

    def set_active_route(self, route_id: int, source: str = "system") -> RouteHistoryRecord | None:
        """Set and broadcast the current active route."""
        route = self.history.load_route(route_id)
        if not route:
            return None
        self.history.set_active_route(route_id)
        self._state = ActiveRouteState(route_id=route_id, route=route)
        self.sync_to_trip_context(route)
        self.history.record_event(route_id, "route_updated", {"source": source, "active_route": True})
        return route

    def get_active_route(self) -> ActiveRouteState:
        """Return active route state, loading from DB settings if needed."""
        if self._state.route_id and self._state.route:
            return self._state
        route_id = self.history.get_active_route_id()
        if route_id:
            route = self.history.load_route(route_id)
            self._state = ActiveRouteState(route_id=route_id, route=route)
        return self._state

    def on_route_calculated(self, route_id: int, route: RouteHistoryRecord, source: str = "route_planner") -> None:
        """Handle successful route calculations across ERP modules."""
        self._state = ActiveRouteState(route_id=route_id, route=route)
        self.history.set_active_route(route_id)
        if route.truck_id:
            with contextlib.suppress(Exception):
                self.history.assign_route_to_truck(route_id, route.truck_id, status="active", notes=f"source={source}")
        self.sync_to_trip_context(route)
        self.history.record_event(route_id, "route_calculated", {"source": source})

    def sync_to_trip_context(self, route: RouteHistoryRecord) -> None:
        """Sync latest route/cost data to profit calculator and trip planner listeners."""
        self.trip_context.set_active_trip_info(
            distance_km=route.total_distance_km,
            duration_min=route.duration_min,
            route_history_v2_id=self._state.route_id,
        )

    def complete_active_route(self) -> bool:
        """Complete the current active route and publish route_completed."""
        state = self.get_active_route()
        if not state.route_id:
            return False
        ok = self.history.complete_route(state.route_id)
        self.history.record_event(state.route_id, "route_completed", {"source": "route_state"})
        return ok

    def archive_route(self, route_id: int) -> bool:
        """Archive through the central state manager."""
        ok = self.history.archive_route(route_id)
        if ok and self._state.route_id == route_id:
            self._state = ActiveRouteState()
        return ok

    def subscribe(self, event_type: str, callback) -> None:
        RouteEventBus.subscribe(event_type, callback)

    def unsubscribe(self, event_type: str, callback) -> None:
        RouteEventBus.unsubscribe(event_type, callback)

    def tracking_snapshot(self) -> dict[str, Any]:
        """Future fleet tracking integration point."""
        state = self.get_active_route()
        route = state.route
        return {
            "active_route_id": state.route_id,
            "truck_id": route.truck_id if route else None,
            "profile": route.profile if route else None,
            "distance_km": route.total_distance_km if route else None,
            "duration_min": route.duration_min if route else None,
            "countries": route.countries_traversed if route else [],
        }
