"""API-backed invoice service wrapper for remote-only client mode.

Mirrors ``services.invoicing.service.InvoiceService`` for generating
invoices and sending invoice emails via the API.

``generate`` / ``generate_and_record`` return the PDF as ``bytes``.  Since
the backend now assigns the invoice sequence number server-side for
``POST /api/v1/invoices/generate``, the assigned number is surfaced on the
returned object as ``result.record`` (e.g. ``{"invoice_number":
"INV-2026-0042", "id": 12}``) and mirrored on ``service.last_record``.
The return type stays ``bytes``-compatible so existing callers that write
the PDF to disk are unaffected.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("remote_invoice")


class GeneratedInvoice(bytes):
    """PDF bytes that carry the server-assigned invoice record (``.record``).

    Subclasses ``bytes`` so callers that treat the result as raw PDF data
    (file writes, byte comparisons) keep working unchanged.  When the API
    surfaced the assigned number/record in the response it is available as
    ``result.record`` (a dict, possibly empty).
    """

    def __new__(cls, pdf: bytes, record: Optional[Dict[str, Any]] = None):
        obj = super().__new__(cls, pdf)
        obj.record = record or {}
        return obj


class RemoteInvoiceService:
    """API-backed substitute for InvoiceService."""

    def __init__(self, api_client) -> None:
        self._api = api_client
        self.last_record: Dict[str, Any] = {}

    def generate(self, trip_data: Dict[str, Any], mode: str = "client") -> bytes:
        result = self._api.generate_invoice(trip_data, mode=mode)
        record = getattr(result, "record", None)
        self.last_record = record or {}
        return GeneratedInvoice(result, record=record)

    def generate_and_record(self, trip_data: Dict[str, Any],
                            mode: str = "client") -> bytes:
        # The backend persists the invoice server-side and assigns the
        # sequence number when none is supplied.  Return the PDF bytes with
        # the surfaced record so callers can read the assigned number.
        result = self._api.generate_invoice(trip_data, mode=mode)
        record = getattr(result, "record", None)
        self.last_record = record or {}
        return GeneratedInvoice(result, record=record)

    def send_invoice_email(self, trip_id: int, recipient: str,
                           trip_data: Optional[Dict[str, Any]] = None,
                           mode: str = "client") -> bool:
        try:
            resp = self._api.send_invoice_email(
                invoice_id=trip_id,
                recipient=recipient,
                trip_data=trip_data or {},
                mode=mode,
            )
            return resp.get("status") == "sent"
        except Exception:
            return False

    def create_record(self, trip_id: int, inv_number: str, amount: float,
                      due_date: str) -> None:
        """Record the invoice in the backend.

        ``generate``/``generate_and_record`` already persist the invoice
        server-side (with the server-assigned sequence number), so no local
        record is needed — this is a no-op kept for API parity with the
        local ``InvoiceService``.
        """
        return None
