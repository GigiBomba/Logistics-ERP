from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime
from .common import ServiceResult


class DriverCreate(BaseModel):
    name: str
    email: str = ""
    phone: str = ""
    license_number: str = ""
    license_expiry: Optional[date] = None
    hours_worked: float = 0.0
    max_hours_per_day: float = 9.0
    status: str = "active"

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Driver name is required")
        return v.strip()


class DriverUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    license_number: Optional[str] = None
    license_expiry: Optional[date] = None
    hours_worked: Optional[float] = None
    max_hours_per_day: Optional[float] = None
    status: Optional[str] = None


class DriverHoursCheck(BaseModel):
    driver_id: int
    check_date: date
    planned_hours: float = 0.0


class DriverHoursResult(BaseModel):
    driver_id: int
    driver_name: str
    hours_worked_today: float
    hours_worked_week: float
    max_hours_per_day: float
    available_hours_today: float
    is_compliant: bool
    warnings: list[str] = []


class DriverResult(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    license_number: str
    license_expiry: Optional[date] = None
    hours_worked: float
    max_hours_per_day: float
    status: str
    current_truck_id: Optional[int] = None
    current_truck_plate: str = ""
    created_at: Optional[datetime] = None


class TruckAssignment(BaseModel):
    driver_id: int
    truck_id: int
    assigned_at: Optional[datetime] = None
    unassigned_at: Optional[datetime] = None


DriverCreateResult = ServiceResult[DriverResult]
DriverHoursCheckResult = ServiceResult[DriverHoursResult]
