from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

from .common import ServiceResult


class RouteStop(BaseModel):
    address: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    sequence: int = 0
    type: str = "waypoint"  # waypoint, pickup, delivery, start, end


class RouteCalculateRequest(BaseModel):
    stops: list[RouteStop]
    vehicle_profile: str = "truck"  # truck, car, bike
    avoid_tolls: bool = False
    avoid_highways: bool = False
    optimize: bool = True
    return_geometry: bool = True
    country_exclusions: list[str] = []

    @field_validator("stops")
    @classmethod
    def at_least_two_stops(cls, v: list[RouteStop]) -> list[RouteStop]:
        if len(v) < 2:
            raise ValueError("Route requires at least 2 stops")
        return v


class RouteResult(BaseModel):
    id: Optional[int] = None
    distance_km: float
    duration_minutes: float
    polyline: Optional[str] = None
    waypoints: list[RouteStop] = []
    toll_cost_eur: float = 0.0
    fuel_cost_eur: float = 0.0
    total_cost_eur: float = 0.0
    created_at: Optional[datetime] = None


RouteCalculationResult = ServiceResult[RouteResult]
