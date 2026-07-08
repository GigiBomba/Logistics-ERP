from typing import Optional

from pydantic import BaseModel, ConfigDict

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
