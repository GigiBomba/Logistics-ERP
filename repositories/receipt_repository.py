"""Receipt repository — all receipt DB access consolidated here."""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

logger = logging.getLogger(__name__)

RECEIPT_NUMBER_FORMATS: dict[str, tuple[str, str]] = {
    "rct_year_seq": ("RCT-{year}-{seq:06d}", "RCT-2026-000184"),
    "rec_seq":      ("REC-{seq:06d}",          "REC-000592"),
    "year_rct_seq": ("{year}-RCT-{seq:05d}",  "2026-RCT-00125"),
}
DEFAULT_FORMAT_KEY = "rct_year_seq"


class ReceiptRepository(BaseRepository):
    TABLE = "receipts"
    COLUMNS = [
        "id", "receipt_number", "receipt_type", "issue_date", "payment_date",
        "currency", "company_name", "company_address", "company_vat", "company_reg",
        "company_phone", "company_email", "received_from_name", "received_from_address",
        "received_from_vat", "received_from_reg", "received_from_contact",
        "received_by_name", "received_by_address", "received_by_vat", "received_by_reg",
        "received_by_contact", "payment_method", "reference_number", "transaction_id",
        "bank_reference", "invoice_reference", "related_trip_id", "driver_id",
        "vehicle_id", "trailer_id", "purpose", "amount", "vat_rate", "vat_amount",
        "total", "amount_words", "notes", "status", "logo_path", "signature_path",
        "stamp_path", "attachments_json", "employee_name", "department",
        "expense_category", "mileage", "fuel", "accommodation", "meals", "parking",
        "tolls", "other_expense", "pickup_location", "delivery_location", "route",
        "dispatcher", "language", "created_at", "updated_at", "company_id",
        "client_id", "pdf_path",
    ]

    def create(
        self,
        receipt_number: str,
        receipt_type: str = "customer_payment",
        issue_date: str = "",
        payment_date: str = "",
        currency: str = "EUR",
        company_name: str = "",
        company_address: str = "",
        company_vat: str = "",
        company_reg: str = "",
        company_phone: str = "",
        company_email: str = "",
        received_from_name: str = "",
        received_from_address: str = "",
        received_from_vat: str = "",
        received_from_reg: str = "",
        received_from_contact: str = "",
        received_by_name: str = "",
        received_by_address: str = "",
        received_by_vat: str = "",
        received_by_reg: str = "",
        received_by_contact: str = "",
        payment_method: str = "",
        reference_number: str = "",
        transaction_id: str = "",
        bank_reference: str = "",
        invoice_reference: str = "",
        related_trip_id: Optional[int] = None,
        driver_id: Optional[int] = None,
        vehicle_id: Optional[int] = None,
        trailer_id: Optional[int] = None,
        purpose: str = "",
        amount: float = 0,
        vat_rate: float = 0,
        vat_amount: float = 0,
        total: float = 0,
        amount_words: str = "",
        notes: str = "",
        status: str = "Draft",
        logo_path: str = "",
        signature_path: str = "",
        stamp_path: str = "",
        attachments_json: str = "[]",
        employee_name: str = "",
        department: str = "",
        expense_category: str = "",
        mileage: float = 0,
        fuel: float = 0,
        accommodation: float = 0,
        meals: float = 0,
        parking: float = 0,
        tolls: float = 0,
        other_expense: float = 0,
        pickup_location: str = "",
        delivery_location: str = "",
        route: str = "",
        dispatcher: str = "",
        language: str = "en",
        client_id: Optional[int] = None,
        pdf_path: str = "",
        commit: bool = True,
    ) -> Optional[int]:
        now = datetime.now().isoformat()
        try:
            data = {
                "receipt_number": receipt_number,
                "receipt_type": receipt_type,
                "issue_date": issue_date,
                "payment_date": payment_date,
                "currency": currency,
                "company_name": company_name,
                "company_address": company_address,
                "company_vat": company_vat,
                "company_reg": company_reg,
                "company_phone": company_phone,
                "company_email": company_email,
                "received_from_name": received_from_name,
                "received_from_address": received_from_address,
                "received_from_vat": received_from_vat,
                "received_from_reg": received_from_reg,
                "received_from_contact": received_from_contact,
                "received_by_name": received_by_name,
                "received_by_address": received_by_address,
                "received_by_vat": received_by_vat,
                "received_by_reg": received_by_reg,
                "received_by_contact": received_by_contact,
                "payment_method": payment_method,
                "reference_number": reference_number,
                "transaction_id": transaction_id,
                "bank_reference": bank_reference,
                "invoice_reference": invoice_reference,
                "related_trip_id": related_trip_id,
                "driver_id": driver_id,
                "vehicle_id": vehicle_id,
                "trailer_id": trailer_id,
                "purpose": purpose,
                "amount": amount,
                "vat_rate": vat_rate,
                "vat_amount": vat_amount,
                "total": total,
                "amount_words": amount_words,
                "notes": notes,
                "status": status,
                "logo_path": logo_path,
                "signature_path": signature_path,
                "stamp_path": stamp_path,
                "attachments_json": attachments_json,
                "employee_name": employee_name,
                "department": department,
                "expense_category": expense_category,
                "mileage": mileage,
                "fuel": fuel,
                "accommodation": accommodation,
                "meals": meals,
                "parking": parking,
                "tolls": tolls,
                "other_expense": other_expense,
                "pickup_location": pickup_location,
                "delivery_location": delivery_location,
                "route": route,
                "dispatcher": dispatcher,
                "language": language,
                "created_at": now,
                "updated_at": now,
            }
            if client_id is not None:
                data["client_id"] = client_id
            if pdf_path:
                data["pdf_path"] = pdf_path
            self._validate_columns(data, extra_allowed={"company_id"})
            data = self._set_company_from_context(data)
            cols = ", ".join(data.keys())
            vals = ", ".join("?" for _ in data)
            return self._execute_insert(
                f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
                tuple(data.values()),
                commit=commit,
            )
        except Exception as exc:
            logger.warning("ReceiptRepository.create failed for %s: %s", receipt_number, exc)
            return None

    def get_by_id(self, receipt_id: int) -> Optional[Dict[str, Any]]:
        row = self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (receipt_id,) + self._company_params(),
        )
        if row and row.get("attachments_json"):
            try:
                row["attachments"] = json.loads(row["attachments_json"])
            except (json.JSONDecodeError, TypeError):
                row["attachments"] = []
        return row

    def get_by_number(self, receipt_number: str) -> Optional[Dict[str, Any]]:
        row = self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE receipt_number = ? {self._company_filter()}",
            (receipt_number,) + self._company_params(),
        )
        if row and row.get("attachments_json"):
            try:
                row["attachments"] = json.loads(row["attachments_json"])
            except (json.JSONDecodeError, TypeError):
                row["attachments"] = []
        return row

    def get_all(self, limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE 1=1 {self._company_filter()} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            self._company_params() + (limit, offset),
        )

    def get_by_status(self, status: str, limit: int = 200) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE status = ? {self._company_filter()} ORDER BY created_at DESC LIMIT ?",
            (status,) + self._company_params() + (limit,),
        )

    def update(
        self,
        receipt_id: int,
        **kwargs,
    ) -> bool:
        self._validate_columns(kwargs, extra_allowed={"company_id"})
        allowed = {
            "receipt_type", "issue_date", "payment_date", "currency",
            "company_name", "company_address", "company_vat",
            "company_reg", "company_phone", "company_email",
            "received_from_name", "received_from_address",
            "received_from_vat", "received_from_reg", "received_from_contact",
            "received_by_name", "received_by_address",
            "received_by_vat", "received_by_reg", "received_by_contact",
            "payment_method",
            "reference_number", "transaction_id",
            "bank_reference", "invoice_reference",
            "related_trip_id", "driver_id", "vehicle_id", "trailer_id",
            "purpose",
            "amount", "vat_rate", "vat_amount", "total", "amount_words",
            "notes", "status",
            "logo_path", "signature_path", "stamp_path",
            "attachments_json",
            "employee_name", "department", "expense_category",
            "mileage", "fuel", "accommodation", "meals", "parking", "tolls", "other_expense",
            "pickup_location", "delivery_location", "route", "dispatcher",
            "language", "client_id", "pdf_path",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [receipt_id]
        try:
            self._execute(
                f"UPDATE {self.TABLE} SET {set_clause} WHERE id = ? {self._company_filter()}",
                tuple(values) + self._company_params(),
            )
            return True
        except Exception as exc:
            logger.warning("ReceiptRepository.update failed for id %s: %s", receipt_id, exc)
            return False

    def update_status(self, receipt_id: int, status: str) -> bool:
        return self.update(receipt_id, status=status)

    def delete(self, receipt_id: int, commit: bool = True) -> bool:
        try:
            self._execute(
                f"DELETE FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
                (receipt_id,) + self._company_params(),
                commit=commit,
            )
            return True
        except Exception as exc:
            logger.warning("ReceiptRepository.delete failed for id %s: %s", receipt_id, exc)
            return False

    def count_by_status(self, status: str) -> int:
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE} WHERE status = ? {self._company_filter()}",
            (status,) + self._company_params(),
        )
        return int(row["cnt"]) if row else 0

    def search_by_trip(self, trip_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE related_trip_id = ? {self._company_filter()} ORDER BY created_at DESC LIMIT ?",
            (trip_id,) + self._company_params() + (limit,),
        )

    def search_by_driver(self, driver_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE driver_id = ? {self._company_filter()} ORDER BY created_at DESC LIMIT ?",
            (driver_id,) + self._company_params() + (limit,),
        )

    def get_next_number(self, format_key: Optional[str] = None) -> str:
        """Generate the next receipt number using a transaction-safe sequence."""
        year = datetime.now().year
        fmt_key = format_key or DEFAULT_FORMAT_KEY
        entry = RECEIPT_NUMBER_FORMATS.get(fmt_key, RECEIPT_NUMBER_FORMATS[DEFAULT_FORMAT_KEY])
        template = entry[0]
        series = fmt_key

        self._execute(
            "INSERT OR IGNORE INTO invoice_number_sequences (series, year, last_number) VALUES (?, ?, 0)",
            (series, year),
            commit=False,
        )
        row = self._fetchone(
            "SELECT last_number FROM invoice_number_sequences WHERE series = ? AND year = ?",
            (series, year),
        )
        nxt = (int(row["last_number"]) if row else 0) + 1
        self._execute(
            "UPDATE invoice_number_sequences SET last_number = ? WHERE series = ? AND year = ?",
            (nxt, series, year),
            commit=False,
        )
        self.db.conn.commit()
        return template.format(year=year, seq=nxt)
