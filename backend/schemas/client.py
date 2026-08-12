
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ClientBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = ""
    email: str = ""
    phone: str = ""
    address: Optional[str] = None
    company_code: str = ""
    city: str = ""


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


class ClientContactAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=255)
    email: str = ""
    phone: str = ""
    position: str = ""


class ClientTagAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: str = Field(..., max_length=255)
