from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from .common import ServiceResult, UndoToken


class DispatchCreate(BaseModel):
    trip_id: int
    truck_id: Optional[int] = None
    driver_id: Optional[int] = None
    scheduled_departure: Optional[datetime] = None
    priority: int = 0


class DispatchAssign(BaseModel):
    dispatch_id: int
    truck_id: int
    driver_id: int


class DispatchCancel(BaseModel):
    dispatch_id: int
    reason: str = ""


class DispatchResult(BaseModel):
    id: int
    trip_id: int
    truck_id: Optional[int] = None
    truck_plate: str = ""
    driver_id: Optional[int] = None
    driver_name: str = ""
    status: str
    scheduled_departure: Optional[datetime] = None
    priority: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class UnassignedTrip(BaseModel):
    trip_id: int
    reference: str
    client_name: str
    pickup: str
    delivery: str
    distance_km: float
    priority: int = 0


class AvailableTruck(BaseModel):
    truck_id: int
    plate: str
    location: str = ""
    available_from: Optional[datetime] = None
    capacity_kg: Optional[int] = None


class DispatchBoardResult(BaseModel):
    assigned: list[DispatchResult]
    unassigned: list[UnassignedTrip]
    available_trucks: list[AvailableTruck]


DispatchCreateResult = ServiceResult[DispatchResult]
DispatchBoardResult_Typed = ServiceResult[DispatchBoardResult]
