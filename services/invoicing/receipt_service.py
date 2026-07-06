"""Receipt service — receipt lifecycle: generate PDF, persist, save draft, email."""
import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

from repositories.receipt_repository import (
    DEFAULT_FORMAT_KEY,
    RECEIPT_NUMBER_FORMATS,
    ReceiptRepository,
)
from services.invoicing.receipt_generator import ReceiptGenerator
from services.operations.event_bus import RECEIPT_CREATED, EventBus
from utils.number_to_words import number_to_words
from utils.resource_path import data_path

class ReceiptService:
    def __init__(self, db, prefs=None):
        self.db = db
        self.prefs = prefs
        self.generator = ReceiptGenerator()
        self._event_bus = EventBus()
        self._receipt_repo = ReceiptRepository(db) if db else None
        self._drafts_dir = data_path("receipt_drafts")
        if not os.path.exists(self._drafts_dir):
            os.makedirs(self._drafts_dir)

    # ── Public API ───────────────────────────────────────────────────

    def get_format_key(self) -> str:
        """Return the current receipt number format key from preferences."""
        if self.prefs:
            return self.prefs.get_setting("receipt_number_format") or DEFAULT_FORMAT_KEY
        return DEFAULT_FORMAT_KEY

    def set_format_key(self, fmt_key: str) -> None:
        """Persist the receipt number format key to preferences."""
        if self.prefs and fmt_key in RECEIPT_NUMBER_FORMATS:
            self.prefs.save_setting("receipt_number_format", fmt_key)

    def generate(self, receipt_data: dict) -> str:
        """Generate a receipt PDF (does not persist to DB or Document Center).

        Auto-calculates financial fields if missing.
        """
        self._calculate_financials(receipt_data)
        return self.generator.generate(receipt_data)

    def generate_and_record(self, receipt_data: dict) -> str:
        """Generate receipt PDF, persist to DB, register in Document Center,
        publish event.

        Returns the PDF path.
        """
        # Resolve receipt number
        receipt_number = receipt_data.get("receipt_number", "")
        if not receipt_number and self._receipt_repo:
            fmt_key = receipt_data.get("_format_key", self.get_format_key())
            receipt_number = self._receipt_repo.get_next_number(format_key=fmt_key)
            receipt_data["receipt_number"] = receipt_number

        # Set issue_date if missing
        if not receipt_data.get("issue_date"):
            receipt_data["issue_date"] = datetime.now().strftime("%Y-%m-%d")

        # Auto-calculate financials
        self._calculate_financials(receipt_data)

        # Generate PDF
        path = self.generator.generate(receipt_data)

        # Persist to DB
        if self._receipt_repo:
            receipt_id = self._receipt_repo.create(
                receipt_number=receipt_data.get("receipt_number", ""),
                receipt_type=receipt_data.get("receipt_type", "customer_payment"),
                issue_date=receipt_data.get("issue_date", ""),
                payment_date=receipt_data.get("payment_date", ""),
                currency=receipt_data.get("currency", "EUR"),
                company_name=receipt_data.get("company_name", ""),
                company_address=receipt_data.get("company_address", ""),
                company_vat=receipt_data.get("company_vat", ""),
                company_reg=receipt_data.get("company_reg", ""),
                company_phone=receipt_data.get("company_phone", ""),
                company_email=receipt_data.get("company_email", ""),
                received_from_name=receipt_data.get("received_from_name", ""),
                received_from_address=receipt_data.get("received_from_address", ""),
                received_from_vat=receipt_data.get("received_from_vat", ""),
                received_from_reg=receipt_data.get("received_from_reg", ""),
                received_from_contact=receipt_data.get("received_from_contact", ""),
                received_by_name=receipt_data.get("received_by_name", ""),
                received_by_address=receipt_data.get("received_by_address", ""),
                received_by_vat=receipt_data.get("received_by_vat", ""),
                received_by_reg=receipt_data.get("received_by_reg", ""),
                received_by_contact=receipt_data.get("received_by_contact", ""),
                payment_method=receipt_data.get("payment_method", ""),
                reference_number=receipt_data.get("reference_number", ""),
                transaction_id=receipt_data.get("transaction_id", ""),
                bank_reference=receipt_data.get("bank_reference", ""),
                invoice_reference=receipt_data.get("invoice_reference", ""),
                related_trip_id=receipt_data.get("related_trip_id"),
                driver_id=receipt_data.get("driver_id"),
                vehicle_id=receipt_data.get("vehicle_id"),
                trailer_id=receipt_data.get("trailer_id"),
                purpose=receipt_data.get("purpose", ""),
                amount=receipt_data.get("amount", 0),
                vat_rate=receipt_data.get("vat_rate", 0),
                vat_amount=receipt_data.get("vat_amount", 0),
                total=receipt_data.get("total", 0),
                amount_words=receipt_data.get("amount_words", ""),
                notes=receipt_data.get("notes", ""),
                status="Generated",
                logo_path=receipt_data.get("logo_path", ""),
                signature_path=receipt_data.get("signature_path", ""),
                stamp_path=receipt_data.get("stamp_path", ""),
                attachments_json=json.dumps(receipt_data.get("attachments", [])),
                employee_name=receipt_data.get("employee_name", ""),
                department=receipt_data.get("department", ""),
                expense_category=receipt_data.get("expense_category", ""),
                mileage=receipt_data.get("mileage", 0),
                fuel=receipt_data.get("fuel", 0),
                accommodation=receipt_data.get("accommodation", 0),
                meals=receipt_data.get("meals", 0),
                parking=receipt_data.get("parking", 0),
                tolls=receipt_data.get("tolls", 0),
                other_expense=receipt_data.get("other_expense", 0),
                pickup_location=receipt_data.get("pickup_location", ""),
                delivery_location=receipt_data.get("delivery_location", ""),
                route=receipt_data.get("route", ""),
                dispatcher=receipt_data.get("dispatcher", ""),
                language=receipt_data.get("language", "en"),
            )
            if receipt_id is not None:
                receipt_data["_record_id"] = receipt_id
                self._event_bus.publish(RECEIPT_CREATED, {
                    "receipt_id": receipt_id,
                    "receipt_number": receipt_number,
                    "total": receipt_data.get("total", 0),
                    "receipt_type": receipt_data.get("receipt_type", ""),
                })
            else:
                logger.warning("Receipt DB record creation failed — PDF exists at %s without DB entry", path)

        # Register in Document Center
        if os.path.isfile(path):
            try:
                from services.document_service import DocumentService
                ds = DocumentService(self.db)
                ds.register_existing(
                    file_path=path,
                    title=f"Receipt {os.path.basename(path)}",
                    category="receipts",
                    tags=["receipt", receipt_data.get("receipt_type", "")],
                )
            except Exception:
                logger.warning("Failed to register receipt in Document Center", exc_info=True)

        return path

    # ── Draft system ─────────────────────────────────────────────────

    def save_draft(self, data: dict, name: str) -> bool:
        """Save a receipt draft JSON file."""
        if not name.strip():
            return False
        draft = dict(data)
        draft["_draft_saved_at"] = datetime.now().isoformat()
        path = os.path.join(self._drafts_dir, f"{name.strip()}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(draft, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def load_draft(self, name: str) -> Optional[dict]:
        """Load a receipt draft by name (without .json)."""
        path = os.path.join(self._drafts_dir, f"{name}.json")
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def list_drafts(self) -> list[str]:
        """Return draft names sorted newest-first by filename."""
        if not os.path.isdir(self._drafts_dir):
            return []
        try:
            drafts = []
            for fn in os.listdir(self._drafts_dir):
                if fn.endswith(".json"):
                    drafts.append(fn[:-5])
            return sorted(drafts, reverse=True)
        except Exception:
            return []

    def delete_draft(self, name: str) -> bool:
        """Delete a draft by name."""
        path = os.path.join(self._drafts_dir, f"{name}.json")
        try:
            if os.path.isfile(path):
                os.remove(path)
                return True
            return False
        except Exception:
            return False

    # ── Internal helpers ─────────────────────────────────────────────

    @staticmethod
    def _calculate_financials(data: dict) -> None:
        """Calculate VAT amount, total, and amount-in-words if missing."""
        amount = float(data.get("amount", 0))
        vat_rate = float(data.get("vat_rate", 0))
        if not data.get("vat_amount") or float(data.get("vat_amount", 0)) == 0:
            data["vat_amount"] = round(amount * vat_rate / 100, 2)
        if not data.get("total") or float(data.get("total", 0)) == 0:
            data["total"] = amount + float(data["vat_amount"])
        if not data.get("amount_words"):
            try:
                lang = data.get("language", "en")
                currency = data.get("currency", "EUR")
                total_val = float(data["total"])
                if total_val > 0:
                    data["amount_words"] = number_to_words(total_val, currency, lang)
            except (ValueError, KeyError):
                pass
