"""Tachograph Pydantic models — typed contracts for AI-callable tacho services."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime

from .common import ServiceResult


class TachoImportRequest(BaseModel):
    file_path: str
    file_type: str = "ddd"  # ddd, c1b, c1b_zip, esm
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None

    @field_validator("file_path")
    @classmethod
    def path_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("File path is required")
        return v.strip()


class DriverActivity(BaseModel):
    driver_id: Optional[int] = None
    driver_name: str = ""
    date: date
    activity_type: str  # driving, rest, work, available
    start_time: datetime
    end_time: datetime
    duration_minutes: float


class VehicleActivity(BaseModel):
    vehicle_id: Optional[int] = None
    plate: str
    date: date
    odometer_start: float
    odometer_end: float
    distance_km: float
    max_speed: Optional[float] = None


class TachoImportResult(BaseModel):
    import_id: int
    file_path: str
    file_type: str
    status: str  # success, partial, failed
    driver_activities: int = 0
    vehicle_activities: int = 0
    errors: list[str] = []
    warnings: list[str] = []
    imported_at: Optional[datetime] = None


class DriverHoursAnalysis(BaseModel):
    driver_id: Optional[int] = None
    driver_name: str
    date: date
    total_driving_hours: float
    total_rest_hours: float
    total_work_hours: float
    is_compliant: bool  # within EU regulations
    violations: list[str] = []
    warnings: list[str] = []


class FleetTachoSummary(BaseModel):
    vehicle_id: Optional[int] = None
    plate: str
    date: date
    total_distance_km: float
    total_driving_hours: float
    average_speed: float
    max_speed: float
    driver_count: int


# -- Typed result aliases ------------------------------------------------

TachoImportOperationResult = ServiceResult[TachoImportResult]
TachoAnalysisResult = ServiceResult[DriverHoursAnalysis]
TachoFleetSummaryResult = ServiceResult[list[FleetTachoSummary]]
