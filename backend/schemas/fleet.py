
from typing import Optional

from pydantic import BaseModel, ConfigDict

class TruckBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plate: str = ""
    brand: str = ""
    year: int = 0


class TruckResponse(TruckBase):
    id: int
    is_active: bool = True


class GpsPing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    truck_id: int
    latitude: float
    longitude: float
    speed_kmh: float = 0.0
    heading: int = 0
    timestamp: str = ""
    driver_id: Optional[int] = None


class GpsPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    truck_id: int
    latitude: float
    longitude: float
    speed_kmh: float = 0.0
    heading: int = 0
    recorded_at: str = ""
    driver_id: Optional[int] = None
