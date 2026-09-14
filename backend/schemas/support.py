"""Support ticket request/response schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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


# URL-encoded digest shape built by ``buildReportDigest`` in
# website/src/services/error-reporting.ts (encodeURIComponent output leaves
# only unreserved marks + %XX escapes).  Anything else — raw whitespace,
# free-form text that could smuggle PII — is rejected with 422.
ANONYMOUS_DIGEST_PATTERN = r"^[A-Za-z0-9\-_.!~*'()%]*$"


class AnonymousErrorReportRequest(BaseModel):
    """PII-free fatal-error digest from an unauthenticated visitor.

    Deliberately no free-form fields (no name/email/phone/etc.) — the only
    text is the URL-encoded error digest plus optional component stack and
    page URL.  Stored locally for later review; never proxied to the support
    service (there is no authenticated user to attribute a ticket to).
    """

    # Reject ANY field not defined above — this channel must never accept a
    # free-form PII field (email, phone, message body, ...).
    model_config = ConfigDict(extra="forbid")

    digest: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        pattern=ANONYMOUS_DIGEST_PATTERN,
        description="URL-encoded, PII-free fatal-error digest (≤4KB).",
    )
    component_stack: Optional[str] = Field(
        None,
        max_length=16384,
        description="React component stack trace (PII-free).",
    )
    url: Optional[str] = Field(
        None,
        max_length=2048,
        description="Page URL the error occurred on (query/hash stripped server-side).",
    )


class AnonymousErrorReportResponse(BaseModel):
    """Acknowledgment returned to the client (fire-and-forget)."""

    status: str = Field("recorded", description="Always 'recorded' on success.")