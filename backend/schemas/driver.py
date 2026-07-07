from typing import Optional

from pydantic import BaseModel, ConfigDict


class DriverBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = ""
    phone: str = ""
    email: str = ""
    license_number: str = ""
    license_category: str = ""
    license_expiry: Optional[str] = None
    medical_expiry: Optional[str] = None
    hire_date: Optional[str] = None
    monthly_salary: float = 0.0
    notes: str = ""
    is_active: bool = True


class DriverCreate(DriverBase):
    pass


class DriverResponse(DriverBase):
    id: int
    created_at: str = ""
    updated_at: str = ""


class DriverUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    license_number: Optional[str] = None
    license_category: Optional[str] = None
    license_expiry: Optional[str] = None
    medical_expiry: Optional[str] = None
    hire_date: Optional[str] = None
    monthly_salary: Optional[float] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
