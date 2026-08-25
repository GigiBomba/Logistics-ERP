from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime

from .common import ServiceResult, UndoToken


class TripStop(BaseModel):
    address: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    sequence: int
    arrival: Optional[datetime] = None
    departure: Optional[datetime] = None
    type: str = "pickup"  # pickup, delivery, rest


class TripCreate(BaseModel):
    client_id: int
    route_id: Optional[int] = None
    truck_id: Optional[int] = None
    driver_id: Optional[int] = None
    reference: str = ""
    start_date: date
    end_date: Optional[date] = None
    promised_date: Optional[date] = None
    price_eur: float = 0.0
    currency: str = "EUR"
    distance_km: Optional[float] = None
    stops: list[TripStop] = []
    notes: str = ""

    # Financial/cost breakdown fields (stored alongside trip)
    truck_plate: str = ""
    driver_name: str = ""
    client_name: str = ""
    payment_date: Optional[date] = None
    status: str = "Planned"
    net_profit: Optional[float] = None
    rate_per_km: Optional[float] = None
    gross_per_km: Optional[float] = None
    fuel_cost: Optional[float] = None
    toll_cost: Optional[float] = None
    salary_cost: Optional[float] = None
    extra_costs: Optional[float] = None
    truck_consumption_l_per_100km: Optional[float] = None
    price_pre_vat: Optional[float] = None
    vat_percent: Optional[float] = None
    source: str = "manual"
    source_provider_id: Optional[str] = None
    source_reference_id: Optional[str] = None

    @field_validator("price_eur")
    @classmethod
    def price_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Price cannot be negative")
        return v

    @field_validator("distance_km")
    @classmethod
    def distance_must_be_positive(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("Distance must be positive if provided")
        return v


class TripUpdate(BaseModel):
    client_id: Optional[int] = None
    truck_id: Optional[int] = None
    driver_id: Optional[int] = None
    reference: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    promised_date: Optional[date] = None
    price_eur: Optional[float] = None
    currency: Optional[str] = None
    distance_km: Optional[float] = None
    stops: Optional[list[TripStop]] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    source_provider_id: Optional[str] = None
    source_reference_id: Optional[str] = None
    truck_plate: Optional[str] = None
    driver_name: Optional[str] = None
    client_name: Optional[str] = None


class TripResult(BaseModel):
    id: int
    client_id: int
    client_name: str = ""
    route_id: Optional[int] = None
    truck_id: Optional[int] = None
    truck_plate: str = ""
    driver_id: Optional[int] = None
    driver_name: str = ""
    reference: str
    start_date: date
    end_date: Optional[date] = None
    price_eur: float
    currency: str
    distance_km: Optional[float] = None
    status: str
    profit: Optional[float] = None
    cost: Optional[float] = None
    margin_pct: Optional[float] = None
    rate_per_km: Optional[float] = None
    gross_per_km: Optional[float] = None
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


TripCreateResult = ServiceResult[TripResult]
TripListResult = ServiceResult[list[TripResult]]
