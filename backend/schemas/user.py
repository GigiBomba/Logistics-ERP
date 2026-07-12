"""User management request and response schemas."""
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


class UserResponse(BaseModel):
    """User response returned from list / get endpoints."""

    model_config = {"from_attributes": True}

    id: int
    email: str = ""
    role: str = ""
    display_name: str = ""
    is_active: bool = True
    created_at: str = ""
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
