from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class InvoiceGenerateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    trip_id: int = Field(..., gt=0)
    mode: str = Field(default="client", max_length=50)
    invoice_number: Optional[str] = Field(None, max_length=100)
    language: str = Field(default="en", max_length=5)
    additional_notes: Optional[str] = Field(None, max_length=2000)

    # Trip data fields used by the invoice service internals
    client_name: str = ""
    total_price_eur: float = 0.0
    client_id: Optional[int] = None
    created_at: Optional[str] = None


class InvoiceSendEmailRequest(BaseModel):
    model_config = {"extra": "forbid"}

    recipient_email: str = Field(..., max_length=255)
    trip_id: Optional[int] = None
    trip_data: Optional[Dict[str, Any]] = None
    mode: str = Field(default="client", max_length=50)
    subject: Optional[str] = Field(None, max_length=255)
    message: Optional[str] = Field(None, max_length=2000)
