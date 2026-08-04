from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

class TripBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_name: str = ""
    loading_city: str = ""
    loading_country: Optional[str] = None
    delivery_city: str = ""
    delivery_country: Optional[str] = None


class TripResponse(TripBase):
    model_config = ConfigDict(extra="ignore")

    id: int
    status: str
    created_at: str


class TripSearchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = ""
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    driver_id: Optional[int] = None
    truck_id: Optional[int] = None
    page: int = 0
    page_size: int = 20


class TripCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: int = Field(..., gt=0)
    route_id: Optional[int] = None
    truck_id: Optional[int] = None
    driver_id: Optional[int] = None
    reference: str = ""
    start_date: str = ""
    end_date: Optional[str] = None
    promised_date: Optional[str] = None
    price_eur: float = 0.0
    currency: str = "EUR"
    distance_km: Optional[float] = None
    notes: str = ""
    truck_plate: str = ""
    driver_name: str = ""
    client_name: str = ""
    status: str = "Planned"
    loading_city: str = ""
    loading_country: Optional[str] = None
    delivery_city: str = ""
    delivery_country: Optional[str] = None
    fuel_cost: Optional[float] = None
    toll_cost: Optional[float] = None
    salary_cost: Optional[float] = None
    extra_costs: Optional[float] = None
    payment_date: Optional[str] = None
    net_profit: Optional[float] = None
    rate_per_km: Optional[float] = None


class TripUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: Optional[int] = None
    route_id: Optional[int] = None
    truck_id: Optional[int] = None
    driver_id: Optional[int] = None
    reference: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    promised_date: Optional[str] = None
    price_eur: Optional[float] = None
    currency: Optional[str] = None
    distance_km: Optional[float] = None
    notes: Optional[str] = None
    truck_plate: Optional[str] = None
    driver_name: Optional[str] = None
    client_name: Optional[str] = None
    status: Optional[str] = None
    loading_city: Optional[str] = None
    loading_country: Optional[str] = None
    delivery_city: Optional[str] = None
    delivery_country: Optional[str] = None
    fuel_cost: Optional[float] = None
    toll_cost: Optional[float] = None
    salary_cost: Optional[float] = None
    extra_costs: Optional[float] = None
    payment_date: Optional[str] = None
    net_profit: Optional[float] = None
    rate_per_km: Optional[float] = None


class TripConflictCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Optional[int] = None
    trip_id_num: Optional[int] = None
    truck_number: Optional[str] = None
    truck_plate: Optional[str] = None
    truck_id: Optional[int] = None
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    distance_km: Optional[float] = None
