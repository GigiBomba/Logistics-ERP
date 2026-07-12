from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from .common import ServiceResult


class ProformaCreate(BaseModel):
    client_id: int
    trip_id: Optional[int] = None
    issue_date: date
    valid_until: date
    currency: str = "EUR"
    items: list[dict] = []  # flexible line items
    notes: str = ""


class ProformaResult(BaseModel):
    id: int
    proforma_number: str
    client_id: int
    client_name: str
    trip_id: Optional[int] = None
    issue_date: date
    valid_until: date
    currency: str
    total_amount: float
    status: str
    notes: str = ""
    pdf_path: Optional[str] = None
    created_at: Optional[datetime] = None


ProformaCreateResult = ServiceResult[ProformaResult]
