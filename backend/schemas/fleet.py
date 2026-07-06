
from typing import Optional

from pydantic import BaseModel

class TruckBase(BaseModel):
    plate: str = ""
    brand: str = ""
    year: int = 0


class TruckResponse(TruckBase):
    id: int
    is_active: bool = True


class GpsPing(BaseModel):
    truck_id: int
    latitude: float
    longitude: float
    speed_kmh: float = 0.0
    heading: int = 0
    timestamp: str = ""
    driver_id: Optional[int] = None


class GpsPosition(BaseModel):
    truck_id: int
    latitude: float
    longitude: float
    speed_kmh: float = 0.0
    heading: int = 0
    recorded_at: str = ""
    driver_id: Optional[int] = None
