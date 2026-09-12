from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ReceiptGenerateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    receipt_data: Optional[Dict[str, Any]] = Field(None, description="Receipt data payload")
    # Fields commonly used by the receipt generator
    receipt_number: Optional[str] = Field(None, max_length=100)
    receipt_type: str = Field(default="payment", max_length=50)
    issue_date: Optional[str] = None
    payment_date: Optional[str] = None
    currency: str = Field(default="EUR", max_length=3)
    amount: Decimal = Decimal("0")
    total: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    notes: Optional[str] = Field(None, max_length=2000)
    language: str = Field(default="en", max_length=5)
