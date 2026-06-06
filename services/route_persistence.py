"""Build and persist route history records (data layer orchestration)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.constraint_engine import TruckConstraintEngine
from services.cost_engine import CostEngineService
from services.route_history_service import RouteHistoryRecord, RouteHistoryService
from services.route_state import RouteStateManager
from utils.perf_log import perf_timer


class RoutePersistenceService:
    def __init__(
        self,
        history_service: RouteHistoryService,
        route_state: RouteStateManager,
        cost_engine: Optional[CostEngineService] = None,
    ) -> None:
        self.history = history_service
        self.route_state = route_state
        self.cost_engine = cost_engine or CostEngineService()

    def build_record(
        self,
        *,
        route: Dict[str, Any],
        truck: Any,
        profile: str,
        stops_state: List[Dict[str, Any]],
        stop_addresses: Dict[str, str],
        excluded_countries: List[str],
        **kwargs: Any,
    ) -> RouteHistoryRecord:
        truck_id = TruckConstraintEngine._get_truck_value(truck, "id") if truck else None
        plate = TruckConstraintEngine._get_truck_value(truck, "plate_number") if truck else None
        model = TruckConstraintEngine._get_truck_value(truck, "model") if truck else None

        truck_payload = {
            "id": truck_id,
            "plate_number": plate,
            "model": model,
        }

        route_points = route.get("stops") if isinstance(route.get("stops"), list) else []
        stops_snapshot = []
        for idx, stop in enumerate(stops_state):
            stop_id = stop.get("id")
            address = stop_addresses.get(stop_id) if stop_id else None
            address = address or stop.get("address")
            item = {
                "position": idx,
                "type": stop.get("type"),
                "address": address,
                "resolved": stop.get("resolved"),
                "lat": stop.get("lat"),
                "lon": stop.get("lon"),
            }
            if idx < len(route_points):
                try:
                    item["lat"] = route_points[idx][0]
                    item["lon"] = route_points[idx][1]
                except Exception:
                    pass
            stops_snapshot.append(item)

        return RouteHistoryRecord(
            stops=stops_snapshot,
            geometry=route.get("geometry", []),
            total_distance_km=route.get("distance_km"),
            duration_min=route.get("duration_min"),
            truck_id=str(truck_id) if truck_id is not None else None,
            truck_label=" - ".join([p for p in [str(plate or ""), str(model or "")] if p]) or None,
            truck=truck_payload,
            profile=profile,
            excluded_countries=excluded_countries or route.get("excluded_countries_requested") or [],
            countries_traversed=route.get("detected_countries") or [],
        )

    def save_calculated_route(
        self,
        *,
        route: Dict[str, Any],
        truck: Any,
        profile: str,
        stops_state: List[Dict[str, Any]],
        stop_addresses: Dict[str, str],
        excluded_countries: List[str],
        cost_info: Dict[str, Any],
    ) -> int:
        with perf_timer("history_save"):
            record = self.build_record(
                route=route,
                truck=truck,
                profile=profile,
                stops_state=stops_state,
                stop_addresses=stop_addresses,
                excluded_countries=excluded_countries,
            )
            route_id = self.history.save_route(record)
            route["history_id"] = route_id
            self.route_state.on_route_calculated(route_id, record, source="route_planner")
            return route_id

    def commit_route(
        self,
        route_id: int,
        truck_id: Optional[str] = None,
    ) -> None:
        """Mark a draft route as committed and sync truck assignment."""
        self.history.commit_route(route_id)
        if truck_id:
            try:
                self.history.assign_route_to_truck(route_id, truck_id)
            except Exception:
                pass

    @staticmethod
    def record_to_planner_route(record: RouteHistoryRecord) -> Dict[str, Any]:
        return {
            "distance_km": record.total_distance_km or 0,
            "duration_min": record.duration_min or 0,
            "geometry": record.geometry or [],
            "stops": [
                (s.get("lat"), s.get("lon"))
                for s in record.stops
                if s.get("lat") is not None and s.get("lon") is not None
            ],
            "profile": record.profile,
            "detected_countries": record.countries_traversed,
            "excluded_countries_requested": record.excluded_countries,
            "cached": True,
        }

    @staticmethod
    def normalize_history_stops(record: RouteHistoryRecord) -> List[Dict[str, Any]]:
        from services.stop_factory import normalize_existing_stop

        stops = []
        source_stops = record.stops or []
        for idx, stop in enumerate(source_stops):
            stop_type = stop.get("type")
            if not stop_type:
                stop_type = "start" if idx == 0 else ("destination" if idx == len(source_stops) - 1 else "stop")
            stops.append(
                normalize_existing_stop({
                    "type": stop_type,
                    "address": stop.get("address") or stop.get("value") or "",
                    "lat": stop.get("lat"),
                    "lon": stop.get("lon"),
                    "resolved": bool(stop.get("lat") is not None and stop.get("lon") is not None),
                })
            )
        return stops
