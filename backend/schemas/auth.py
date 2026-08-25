"""Authentication request schemas.

These replace raw ``Dict[str, str]`` parameters in auth endpoints
so that input validation happens at the Pydantic boundary before
reaching the handler.
"""
from __future__ import annotations


from pydantic import BaseModel, Field


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="User email address",
    )


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=72)
