from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

from .common import ServiceResult


class ClientContact(BaseModel):
    name: str
    email: str = ""
    phone: str = ""
    position: str = ""


class ClientCreate(BaseModel):
    name: str
    company_code: str = ""
    vat_number: str = ""
    address: str = ""
    city: str = ""
    county: str = ""
    country: str = ""
    email: str = ""
    phone: str = ""
    notes: str = ""
    contacts: list[ClientContact] = []

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Client name is required")
        return v.strip()


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    company_code: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    country: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class ClientResult(BaseModel):
    id: int
    name: str
    company_code: str
    vat_number: str
    address: str
    city: str
    county: str = ""
    country: str
    email: str
    phone: str
    notes: str
    trip_count: int = 0
    invoice_count: int = 0
    total_revenue: float = 0.0
    contacts: list[ClientContact] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


ClientCreateResult = ServiceResult[ClientResult]
ClientListResult = ServiceResult[list[ClientResult]]
