from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime
from .common import ServiceResult, UndoToken


class InvoiceLineItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_of_measure: str = "buc"  # buc, kg, km, l, ore, etc.
    unit_price: float
    discount_percent: float = 0.0
    discount_amount: float = 0.0
    taxable_amount: Optional[float] = None  # net after discount
    vat_rate: float = 19.0  # percentage
    total_net: Optional[float] = None  # net total for this line
    vat_amount: Optional[float] = None
    line_total: Optional[float] = None  # gross total for this line


INVOICE_TYPES = [
    "invoice",        # factură fiscală standard
    "storno",         # factură de stornare (credit note)
    "proforma",       # factură proformă (non-fiscală)
    "receipt",        # chitanță
    "advance",        # factură de avans
    "final",          # factură finală
    "correction",     # factură de corecție
]

INVOICE_STATUSES = [
    "draft",
    "finalized",
    "xml_generated",
    "cancelled",
    "paid",
]

INVOICE_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft":         ["finalized", "cancelled"],
    "finalized":     ["xml_generated", "cancelled", "paid"],
    "xml_generated": ["paid", "draft"],
    "paid":          [],
    "cancelled":     [],
}


class InvoiceCreate(BaseModel):
    client_id: int
    trip_id: Optional[int] = None
    invoice_date: date
    due_date: date
    currency: str = "EUR"
    exchange_rate: float = 1.0
    invoice_type: str = "invoice"
    line_items: list[InvoiceLineItem] = []
    notes: str = ""

    @field_validator("due_date")
    @classmethod
    def due_after_invoice_date(cls, v: date, info) -> date:
        if "invoice_date" in info.data and v < info.data["invoice_date"]:
            raise ValueError("Due date must be on or after invoice date")
        return v

    @field_validator("invoice_type")
    @classmethod
    def validate_invoice_type(cls, v: str) -> str:
        if v not in INVOICE_TYPES:
            raise ValueError(f"Invalid invoice type: {v}. Must be one of {INVOICE_TYPES}")
        return v


class InvoiceUpdate(BaseModel):
    client_id: Optional[int] = None
    trip_id: Optional[int] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    invoice_type: Optional[str] = None
    line_items: Optional[list[InvoiceLineItem]] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    amount_paid: Optional[float] = None


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
    exchange_rate: float = 1.0
    invoice_type: str = "invoice"
    line_items: list[InvoiceLineItem] = []
    subtotal_net: float
    total_vat: float
    total_gross: float
    amount_paid: float = 0.0
    amount_remaining: float = 0.0
    status: str = "draft"
    notes: str
    pdf_path: Optional[str] = None
    # e-Factura XML artifact tracking: the XML FILE is the legal deliverable
    # (UBL CIUS-RO via xml_export.py).  The invoice generator never submits to
    # ANAF — there is no submission reference / submitted-at / response state.
    efactura_status: str = ""
    efactura_xml_path: Optional[str] = None
    # Audit
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


InvoiceCreateResult = ServiceResult[InvoiceResult]
InvoiceListResult = ServiceResult[list[InvoiceResult]]
