from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Trip:
    id: int
    truck_number: str = ""
    driver_name: str = ""
    client_name: str = ""
    distance_km: float = 0.0
    total_price_eur: float = 0.0
    net_profit: float = 0.0
    gross_per_km: float = 0.0
    status: str = "Planned"
    created_at: str = ""
    route_history_v2_id: Optional[str] = None
    driver_id: Optional[int] = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Trip":
        return Trip(
            id=int(d.get("id", 0)),
            truck_number=str(d.get("truck_number", "")),
            driver_name=str(d.get("driver_name", "")),
            client_name=str(d.get("client_name", "")),
            distance_km=float(d.get("distance_km") or 0),
            total_price_eur=float(d.get("total_price_eur") or 0),
            net_profit=float(d.get("net_profit") or 0),
            gross_per_km=float(d.get("gross_per_km") or 0),
            status=str(d.get("status", "Planned")),
            created_at=str(d.get("created_at", "")),
            route_history_v2_id=str(d["route_history_v2_id"]) if d.get("route_history_v2_id") else None,
            driver_id=int(d["driver_id"]) if d.get("driver_id") else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "truck_number": self.truck_number,
            "driver_name": self.driver_name,
            "client_name": self.client_name,
            "distance_km": self.distance_km,
            "total_price_eur": self.total_price_eur,
            "net_profit": self.net_profit,
            "gross_per_km": self.gross_per_km,
            "status": self.status,
            "created_at": self.created_at,
            "route_history_v2_id": self.route_history_v2_id,
            "driver_id": self.driver_id,
        }
