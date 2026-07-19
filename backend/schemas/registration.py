"""Public registration request schemas."""

from pydantic import BaseModel, Field


class RegistrationRequest(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=72)
    display_name: str = ""
    company_name: str = Field(min_length=1)
