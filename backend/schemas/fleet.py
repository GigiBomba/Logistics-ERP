from __future__ import annotations


from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel

class TruckBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plate: str = ""
    brand: str = ""
    year: int = 0


class TruckResponse(TruckBase):
    model_config = ConfigDict(extra="ignore")

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


class GpsBatchRequest(RootModel[Annotated[List[GpsPing], Field(max_length=500)]]):
    """Batch of GPS pings for ``POST /fleet/gps/batch``.

    Capped at 500 pings so an oversized batch cannot build a huge IN-clause
    or flood the cache; FastAPI rejects larger batches with 422.
    """
