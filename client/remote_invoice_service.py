"""API-backed invoice service wrapper for remote-only client mode.

Mirrors ``services.invoicing.service.InvoiceService`` for generating
invoices and sending invoice emails via the API.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("remote_invoice")


class RemoteInvoiceService:
    """API-backed substitute for InvoiceService."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    def generate(self, trip_data: Dict[str, Any], mode: str = "client") -> str:
        return self._api.generate_invoice(trip_data, mode=mode)

    def generate_and_record(self, trip_data: Dict[str, Any],
                            mode: str = "client") -> str:
        path = self._api.generate_invoice(trip_data, mode=mode)
        return path

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
