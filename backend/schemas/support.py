"""Support ticket request/response schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CreateTicketRequest(BaseModel):
    """Payload for filing a support ticket.

    Matches the client-side ``CreateTicketRequest`` in
    ``website/src/api/endpoints.ts`` (subject, description, optional priority,
    optional category).
    """

    subject: str = Field(
        ..., min_length=1, max_length=200, description="Ticket subject."
    )
    description: str = Field(
        ..., min_length=1, description="Detailed description of the issue."
    )
    priority: Optional[str] = Field(
        None,
        pattern=r"^(low|medium|high|urgent)$",
        description="Ticket priority (low, medium, high or urgent).",
    )
    category: Optional[str] = Field(
        None,
        description="Free-form ticket category (e.g. 'bug', 'billing', 'feature').",
    )


class TicketResponse(BaseModel):
    """Support ticket representation returned to the client."""

    id: str = Field(..., description="Ticket ID for reference/persistence.")
    subject: str = Field(..., description="Ticket subject.")
    status: str = Field("open", description="Ticket status.")
    priority: Optional[str] = Field(None, description="Ticket priority.")
    category: Optional[str] = Field(None, description="Ticket category.")
    created_at: Optional[str] = Field(None, description="Ticket creation timestamp.")
    updated_at: Optional[str] = Field(None, description="Ticket last-update timestamp.")