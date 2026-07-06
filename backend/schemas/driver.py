from typing import Optional

from pydantic import BaseModel


class DriverBase(BaseModel):
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
