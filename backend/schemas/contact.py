"""Contact form request/response schemas."""

from typing import Optional

from pydantic import BaseModel, Field


class ContactRequest(BaseModel):
    """Public contact form payload."""

    name: str = Field(..., min_length=2, max_length=200, description="Sender name")
    email: str = Field(..., description="Email address (normalized to lowercase in handler)")
    subject: str = Field(..., min_length=3, max_length=200, description="Message subject")
    message: str = Field(..., min_length=10, max_length=5000, description="Message body")
    hp_field: Optional[str] = Field(None, description="Honeypot — leave empty")
    turnstile_token: Optional[str] = Field(None, description="Cloudflare Turnstile token (unvalidated in Phase 1)")


class ContactResponse(BaseModel):
    """Response returned after a successful contact message submission."""

    status: str = Field("received", description="Status of the submission")
