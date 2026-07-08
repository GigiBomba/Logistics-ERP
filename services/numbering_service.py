"""Document number generation service.

Centralizes invoice, proforma, and receipt number generation.
Extracted from invoice_editor.py, proforma_editor.py, and receipt_editor.py.
"""

from __future__ import annotations

from typing import Any

from repositories.invoice_repository import (
    DEFAULT_INVOICE_FORMAT_KEY as INV_DEFAULT_FMT,
    INVOICE_NUMBER_FORMATS,
)
from repositories.proforma_repository import DEFAULT_PROFORMA_FORMAT_KEY as PROF_DEFAULT_FMT
from repositories.receipt_repository import DEFAULT_FORMAT_KEY


class NumberingService:
    """Generates sequential document numbers based on configurable formats."""

    def __init__(self, db):
        self._inv_repo = None
        self._prof_repo = None
        self._rec_repo = None
        self._db = db

    # ── Lazily initialize repos ──────────────────────────────────

    def _get_inv_repo(self):
        if self._inv_repo is None:
            from repositories.invoice_repository import InvoiceRepository
            self._inv_repo = InvoiceRepository(self._db)
        return self._inv_repo

    def _get_prof_repo(self):
        if self._prof_repo is None:
            from repositories.proforma_repository import ProformaRepository
            self._prof_repo = ProformaRepository(self._db)
        return self._prof_repo

    def _get_rec_repo(self):
        if self._rec_repo is None:
            from repositories.receipt_repository import ReceiptRepository
            self._rec_repo = ReceiptRepository(self._db)
        return self._rec_repo

    # ── Number generation ────────────────────────────────────────

    def next_invoice_number(self, format_key: str = INV_DEFAULT_FMT) -> str:
        """Generate the next invoice number for the given format."""
        return self._get_inv_repo().get_next_number(format_key=format_key)

    def next_proforma_number(self, format_key: str = PROF_DEFAULT_FMT) -> str:
        """Generate the next proforma number."""
        return self._get_prof_repo().get_next_number(format_key=format_key)

    def next_receipt_number(self, format_key: str = DEFAULT_FORMAT_KEY) -> str:
        """Generate the next receipt number."""
        return self._get_rec_repo().get_next_number(format_key=format_key)

    # ── Format resolution ────────────────────────────────────────

    def resolve_invoice_format_key(self, display_text: str, current_key: str) -> str:
        """Map a display text back to the format key.

        Args:
            display_text: The user-visible format description.
            current_key: Fallback key if no match found.

        Returns:
            The matching format key.
        """
        for key, (_, label) in INVOICE_NUMBER_FORMATS.items():
            if label == display_text:
                return key
        return current_key

    def available_invoice_formats(self) -> list[str]:
        """Return display labels for all available invoice formats."""
        return [label for _, label in INVOICE_NUMBER_FORMATS.values()]
