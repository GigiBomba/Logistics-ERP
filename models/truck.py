from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Truck:
    id: int
    plate_number: str = ""
    model: str = ""
    manufacturer: str = ""
    year: Optional[int] = None
    vin: str = ""
    mileage: float = 0.0
    fuel_consumption: float = 0.0
    monthly_rate: float = 0.0
    status: str = "active"
    insurance_expiry: Optional[str] = None
    inspection_expiry: Optional[str] = None
    maintenance_due: Optional[str] = None
    tachograph_expiry: Optional[str] = None
    active_status: int = 1

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Truck":
        return Truck(
            id=int(d.get("id", 0)),
            plate_number=str(d.get("plate_number", "")),
            model=str(d.get("model", "")),
            manufacturer=str(d.get("manufacturer", "")),
            year=int(d["year"]) if d.get("year") else None,
            vin=str(d.get("vin", "")),
            mileage=float(d.get("mileage") or 0),
            fuel_consumption=float(d.get("fuel_consumption") or 0),
            monthly_rate=float(d.get("monthly_rate") or 0),
            status=str(d.get("status", "active")),
            insurance_expiry=str(d["insurance_expiry"]) if d.get("insurance_expiry") else None,
            inspection_expiry=str(d["inspection_expiry"]) if d.get("inspection_expiry") else None,
            maintenance_due=str(d["maintenance_due"]) if d.get("maintenance_due") else None,
            tachograph_expiry=str(d["tachograph_expiry"]) if d.get("tachograph_expiry") else None,
            active_status=int(d.get("active_status", 1)),
        )
