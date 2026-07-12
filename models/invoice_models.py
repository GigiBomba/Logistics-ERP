from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime
from .common import ServiceResult, UndoToken


class InvoiceLineItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float
    vat_rate: float = 19.0  # percentage
    total_net: Optional[float] = None
    total_vat: Optional[float] = None
    total_gross: Optional[float] = None


class InvoiceCreate(BaseModel):
    client_id: int
    trip_id: Optional[int] = None
    invoice_date: date
    due_date: date
    currency: str = "EUR"
    line_items: list[InvoiceLineItem] = []
    notes: str = ""

    @field_validator("due_date")
    @classmethod
    def due_after_invoice_date(cls, v: date, info) -> date:
        if "invoice_date" in info.data and v < info.data["invoice_date"]:
            raise ValueError("Due date must be on or after invoice date")
        return v


class InvoiceUpdate(BaseModel):
    client_id: Optional[int] = None
    trip_id: Optional[int] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = None
    line_items: Optional[list[InvoiceLineItem]] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class InvoiceFinalizeRequest(BaseModel):
    invoice_id: int
    send_email: bool = False
    email_recipient: str = ""


class InvoiceResult(BaseModel):
    id: int
    invoice_number: str
    client_id: int
    client_name: str
    trip_id: Optional[int] = None
    trip_reference: str = ""
    invoice_date: date
    due_date: date
    currency: str
    line_items: list[InvoiceLineItem] = []
    subtotal_net: float
    total_vat: float
    total_gross: float
    status: str  # draft, finalized, cancelled, paid
    notes: str
    pdf_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


InvoiceCreateResult = ServiceResult[InvoiceResult]
InvoiceListResult = ServiceResult[list[InvoiceResult]]
