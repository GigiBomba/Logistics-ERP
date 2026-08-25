from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class PaymentProfileBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_name: str = ""
    recipient_type: str = "custom"
    bank_name: str = ""
    bank_account: str = ""
    bank_code: str = ""
    bank_bic: str = ""
    iban: str = ""
    payment_reference: str = ""
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    notes: str = ""
    is_active: bool = True


class PaymentProfileCreate(PaymentProfileBase):
    model_config = ConfigDict(extra="allow")


class PaymentProfileResponse(PaymentProfileBase):
    model_config = ConfigDict(extra="ignore")

    id: int
    created_at: str = ""
    updated_at: str = ""


class PaymentProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_name: Optional[str] = None
    recipient_type: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_code: Optional[str] = None
    bank_bic: Optional[str] = None
    iban: Optional[str] = None
    payment_reference: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PaymentRecipientOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    recipient_id: int
    recipient_type: str  # "client", "driver", or "custom"
    recipient_name: str
    bank_name: str = ""
    bank_account: str = ""
    bank_code: str = ""
    bank_bic: str = ""
    iban: str = ""
    payment_reference: str = ""


class PaymentBatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_id: int
    recipient_type: str  # "client", "driver", or "custom"
    recipient_name: str
    bank_name: str = ""
    bank_account: str = ""
    bank_code: str = ""
    bank_bic: str = ""
    iban: str = ""
    amount: float = 0.0
    currency: str = "EUR"
    payment_reference: str = ""


class PaymentBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PaymentBatchItem]
    batch_name: str = ""
