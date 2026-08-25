from __future__ import annotations


from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ClientBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = ""
    email: str = ""
    phone: str = ""
    address: Optional[str] = None


class ClientResponse(ClientBase):
    model_config = ConfigDict(extra="ignore")

    id: int
    is_active: bool = True
    created_at: str = ""


class ClientCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    company_code: str = ""
    vat_number: str = ""
    address: str = ""
    city: str = ""
    country: str = ""
    email: str = ""
    phone: str = ""
    notes: str = ""
    contact_person: str = ""
    client_type: str = ""
    payment_terms_days: int = 30
    credit_limit_eur: float = 0.0
    default_rate_per_km: float | None = None
    rating: int | None = Field(None, ge=1, le=5)
    eori_number: str = ""


class ClientUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    company_code: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    contact_person: Optional[str] = None
    client_type: Optional[str] = None
    payment_terms_days: Optional[int] = None
    credit_limit_eur: Optional[float] = None
    default_rate_per_km: Optional[float] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    eori_number: Optional[str] = None


class ClientContactAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Keys match ContactRepository.COLUMNS and the desktop contact dialog
    # (_QtContactDialog FIELDS: full_name, title, phone, email, contact_type).
    full_name: str = Field(..., max_length=255)
    contact_type: str = ""
    title: str = ""
    phone: str = ""
    email: str = ""


class ClientContactUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Partial update: every field is optional; the PATCH route applies only
    # the fields actually present (model_dump(exclude_unset=True)).
    full_name: Optional[str] = Field(None, max_length=255)
    contact_type: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class ClientTagAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: str = Field(..., max_length=255)


class ClientMergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_id: int = Field(..., gt=0)
    to_id: int = Field(..., gt=0)
