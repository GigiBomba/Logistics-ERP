from __future__ import annotations

from decimal import Decimal

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
    price_eur: Decimal = Decimal("0.0")
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
    net_profit: Optional[Decimal] = None
    rate_per_km: Optional[Decimal] = None
    gross_per_km: Optional[Decimal] = None
    fuel_cost: Optional[Decimal] = None
    toll_cost: Optional[Decimal] = None
    salary_cost: Optional[Decimal] = None
    extra_costs: Optional[Decimal] = None
    truck_consumption_l_per_100km: Optional[float] = None
    price_pre_vat: Optional[Decimal] = None
    vat_percent: Optional[Decimal] = None
    source: str = "manual"
    source_provider_id: Optional[str] = None
    source_reference_id: Optional[str] = None

    @field_validator("price_eur")
    @classmethod
    def price_must_be_non_negative(cls, v: Decimal) -> Decimal:
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
    price_eur: Optional[Decimal] = None
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
    price_eur: Decimal
    currency: str
    distance_km: Optional[float] = None
    status: str
    profit: Optional[Decimal] = None
    cost: Optional[Decimal] = None
    margin_pct: Optional[Decimal] = None
    rate_per_km: Optional[Decimal] = None
    gross_per_km: Optional[Decimal] = None
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Trans.eu externally-managed flag (TransEU_Architecture.md §9.3):
    # 1 = dispatch changes are read-only in Operion.  Read-only in this
    # model — it is set by the Trans.eu sync services, never by manual edits.
    externally_managed: int = 0


TripCreateResult = ServiceResult[TripResult]
TripListResult = ServiceResult[list[TripResult]]
