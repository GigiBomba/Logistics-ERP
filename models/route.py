from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RouteStop:
    lat: float
    lon: float
    label: str = ""

    def to_tuple(self) -> Tuple[float, float, str]:
        return (self.lat, self.lon, self.label)


@dataclass
class Route:
    id: Optional[int] = None
    origin: str = ""
    destination: str = ""
    distance_km: float = 0.0
    duration_min: float = 0.0
    geometry: List[Tuple[float, float]] = field(default_factory=list)
    stops: List[RouteStop] = field(default_factory=list)
    profile: str = "truck"
    created_at: str = ""
    total_cost_eur: float = 0.0
    toll_eur: float = 0.0

    @staticmethod
    def from_history_record(record: Any) -> "Route":
        import json
        geo = json.loads(record.geometry_json) if hasattr(record, "geometry_json") and record.geometry_json else []
        stops_raw = json.loads(record.stops_json) if hasattr(record, "stops_json") and record.stops_json else []
        stops = [RouteStop(lat=s[0], lon=s[1], label=s[2] if len(s) > 2 else "") for s in stops_raw]
        return Route(
            id=record.id if hasattr(record, "id") else None,
            origin=record.origin if hasattr(record, "origin") else "",
            destination=record.destination if hasattr(record, "destination") else "",
            distance_km=float(record.total_distance_km) if hasattr(record, "total_distance_km") and record.total_distance_km else 0.0,
            duration_min=float(record.duration_min) if hasattr(record, "duration_min") and record.duration_min else 0.0,
            geometry=geo,
            stops=stops,
            profile=record.profile if hasattr(record, "profile") else "truck",
            created_at=record.last_calculated_at if hasattr(record, "last_calculated_at") else "",
            total_cost_eur=float(record.total_cost_eur) if hasattr(record, "total_cost_eur") and record.total_cost_eur else 0.0,
            toll_eur=float(record.toll_eur) if hasattr(record, "toll_eur") and record.toll_eur else 0.0,
        )
