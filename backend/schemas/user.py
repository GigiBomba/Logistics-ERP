"""User management request schemas."""
from typing import Optional

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    role: str  # "dispatcher" or "driver"
    display_name: str = ""


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)
    email: Optional[str] = None
