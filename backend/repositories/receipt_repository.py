"""Backend re-export for ``repositories.receipt_repository.ReceiptRepository``."""
from __future__ import annotations

from repositories.receipt_repository import ReceiptRepository, RECEIPT_NUMBER_FORMATS, DEFAULT_FORMAT_KEY
__all__ = ["ReceiptRepository", "RECEIPT_NUMBER_FORMATS", "DEFAULT_FORMAT_KEY"]
