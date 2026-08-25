from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime
from .common import ServiceResult


class EmailTemplateCreate(BaseModel):
    name: str
    subject: str
    body_html: str
    language: str = "ro"
    type: str = "reminder"  # reminder, invoice, dunning

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Template name is required")
        return v.strip()


class SendReminderRequest(BaseModel):
    template_id: int
    client_id: int
    invoice_id: Optional[int] = None
    trip_id: Optional[int] = None
    recipient_email: str
    send_date: Optional[date] = None
    attachments: list[int] = []  # document IDs

    @field_validator("recipient_email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v


class SendReminderResult(BaseModel):
    email_id: int
    sent_to: str
    template_name: str
    sent_at: datetime
    success: bool
    error_message: str = ""


AutomailSendResult = ServiceResult[SendReminderResult]
