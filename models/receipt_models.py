from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from .common import ServiceResult


class ReceiptLineItem(BaseModel):
    description: str
    amount: float
    quantity: float = 1.0


class ReceiptCreate(BaseModel):
    client_id: int
    trip_id: Optional[int] = None
    invoice_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    receipt_date: date
    currency: str = "EUR"
    items: list[ReceiptLineItem] = []
    total_amount: Optional[float] = None
    notes: str = ""


class ReceiptResult(BaseModel):
    id: int
    receipt_number: str
    client_id: int
    client_name: str
    trip_id: Optional[int] = None
    invoice_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    vehicle_plate: str = ""
    receipt_date: date
    currency: str
    items: list[ReceiptLineItem]
    total_amount: float
    notes: str = ""
    pdf_path: Optional[str] = None
    created_at: Optional[datetime] = None


ReceiptCreateResult = ServiceResult[ReceiptResult]
