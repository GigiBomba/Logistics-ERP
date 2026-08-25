from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from .common import ServiceResult


class PaymentProfileCreate(BaseModel):
    name: str
    bank_name: str = ""
    iban: str = ""
    swift: str = ""
    currency: str = "EUR"
    is_default: bool = False


class PaymentProfileResult(BaseModel):
    id: int
    name: str
    bank_name: str
    iban: str
    swift: str
    currency: str
    is_default: bool


class PaymentBatchRequest(BaseModel):
    profile_id: int
    invoice_ids: list[int] = []
    driver_ids: list[int] = []
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class PaymentBatchResult(BaseModel):
    batch_id: int
    file_path: str
    row_count: int
    total_amount: float
    currency: str
    generated_at: datetime


PaymentBatchCreateResult = ServiceResult[PaymentBatchResult]
