from typing import Optional

from pydantic import BaseModel, Field


class CompanyConfigUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    company_name: Optional[str] = Field(None, max_length=255)
    cui: Optional[str] = Field(None, max_length=100)
    reg_number: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    logo_path: Optional[str] = Field(None, max_length=500)
    company_color: Optional[str] = Field(None, max_length=50)
    signature_path: Optional[str] = Field(None, max_length=500)
    stamp_path: Optional[str] = Field(None, max_length=500)


class SettingUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    value: str = Field(default="", max_length=2000)
