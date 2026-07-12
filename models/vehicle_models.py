from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime

from .common import ServiceResult


class VehicleCreate(BaseModel):
    plate: str
    brand: str = ""
    model: str = ""
    year: Optional[int] = None
    vin: str = ""
    max_weight_kg: Optional[int] = None
    fuel_type: str = "diesel"
    consumption_l_per_100km: Optional[float] = None
    insurance_expiry: Optional[date] = None
    technical_inspection_expiry: Optional[date] = None
    tachograph_calibration_expiry: Optional[date] = None
    status: str = "active"

    @field_validator("plate")
    @classmethod
    def plate_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Plate number is required")
        return v.strip().upper()


class VehicleUpdate(BaseModel):
    plate: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    vin: Optional[str] = None
    max_weight_kg: Optional[int] = None
    fuel_type: Optional[str] = None
    consumption_l_per_100km: Optional[float] = None
    insurance_expiry: Optional[date] = None
    technical_inspection_expiry: Optional[date] = None
    tachograph_calibration_expiry: Optional[date] = None
    status: Optional[str] = None


class VehicleSearchRequest(BaseModel):
    query: str = ""
    status: Optional[str] = None
    available_between: Optional[tuple[datetime, datetime]] = None
    min_capacity_kg: Optional[int] = None
    fuel_type: Optional[str] = None
    page: int = 1
    per_page: int = 20


class VehicleHealthScore(BaseModel):
    vehicle_id: int
    plate: str
    overall_score: float  # 0-100
    insurance_status: str
    technical_inspection_status: str
    tachograph_status: str
    maintenance_alerts: int
    next_maintenance_due: Optional[date] = None


class VehicleResult(BaseModel):
    id: int
    plate: str
    brand: str
    model: str
    year: Optional[int] = None
    vin: str = ""
    max_weight_kg: Optional[int] = None
    fuel_type: str
    consumption_l_per_100km: Optional[float] = None
    insurance_expiry: Optional[date] = None
    technical_inspection_expiry: Optional[date] = None
    tachograph_calibration_expiry: Optional[date] = None
    status: str
    health_score: Optional[VehicleHealthScore] = None
    current_location: Optional[str] = None
    created_at: Optional[datetime] = None


VehicleCreateResult = ServiceResult[VehicleResult]
VehicleSearchResult = ServiceResult[list[VehicleResult]]
