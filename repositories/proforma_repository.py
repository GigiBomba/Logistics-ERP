"""Proforma repository — all proforma invoice DB access consolidated here."""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

logger = logging.getLogger(__name__)

PROFORMA_NUMBER_FORMATS: dict[str, tuple[str, str]] = {
    "prof_year_seq": ("PROF-{year}-{seq:04d}", "PROF-2026-0001"),
    "prof_seq":      ("PROF-{seq:06d}",          "PROF-000042"),
}
DEFAULT_PROFORMA_FORMAT_KEY = "prof_year_seq"


class ProformaRepository(BaseRepository):
    TABLE = "proforma_invoices"
    COLUMNS = [
        "id", "proforma_number", "issue_date", "valid_until",
        "client_name", "client_address", "client_vat", "client_phone", "client_email",
        "description", "notes", "line_items_json", "subtotal",
        "discount_type", "discount_value", "discount_amount",
        "tax_rate", "tax_amount", "grand_total", "currency", "mode", "status",
        "logo_path", "signature_path", "stamp_path", "company_color",
        "pdf_path", "created_at", "updated_at", "company_id",
    ]

    def create(
        self,
        proforma_number: str,
        issue_date: str = "",
        valid_until: str = "",
        client_name: str = "",
        client_address: str = "",
        client_vat: str = "",
        client_phone: str = "",
        client_email: str = "",
        description: str = "",
        notes: str = "",
        line_items: Optional[List[Dict[str, Any]]] = None,
        subtotal: float = 0,
        discount_type: str = "",
        discount_value: float = 0,
        discount_amount: float = 0,
        tax_rate: float = 0,
        tax_amount: float = 0,
        grand_total: float = 0,
        currency: str = "EUR",
        mode: str = "client",
        status: str = "Draft",
        logo_path: str = "",
        signature_path: str = "",
        stamp_path: str = "",
        company_color: str = "#6366f1",
        commit: bool = True,
    ) -> Optional[int]:
        now = datetime.now().isoformat()
        try:
            data = {
                "proforma_number": proforma_number, "issue_date": issue_date,
                "valid_until": valid_until,
                "client_name": client_name, "client_address": client_address,
                "client_vat": client_vat, "client_phone": client_phone,
                "client_email": client_email,
                "description": description, "notes": notes,
                "line_items_json": json.dumps(line_items or []), "subtotal": subtotal,
                "discount_type": discount_type, "discount_value": discount_value,
                "discount_amount": discount_amount,
                "tax_rate": tax_rate, "tax_amount": tax_amount, "grand_total": grand_total,
                "currency": currency, "mode": mode, "status": status,
                "logo_path": logo_path, "signature_path": signature_path,
                "stamp_path": stamp_path, "company_color": company_color,
                "created_at": now, "updated_at": now,
            }
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
            logger.warning("ProformaRepository.create failed for %s: %s", proforma_number, exc)
            return None

    def get_by_id(self, proforma_id: int) -> Optional[Dict[str, Any]]:
        row = self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (proforma_id,) + self._company_params(),
        )
        if row and row.get("line_items_json"):
            try:
                row["line_items"] = json.loads(row["line_items_json"])
            except (json.JSONDecodeError, TypeError):
                row["line_items"] = []
        return row

    def get_by_number(self, proforma_number: str) -> Optional[Dict[str, Any]]:
        row = self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE proforma_number = ? {self._company_filter()}",
            (proforma_number,) + self._company_params(),
        )
        if row and row.get("line_items_json"):
            try:
                row["line_items"] = json.loads(row["line_items_json"])
            except (json.JSONDecodeError, TypeError):
                row["line_items"] = []
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
        proforma_id: int,
        **kwargs,
    ) -> bool:
        self._validate_columns(kwargs, extra_allowed={"company_id"})
        allowed = {
            "issue_date", "valid_until",
            "client_name", "client_address", "client_vat", "client_phone", "client_email",
            "description", "notes",
            "line_items_json", "subtotal",
            "discount_type", "discount_value", "discount_amount",
            "tax_rate", "tax_amount", "grand_total",
            "currency", "mode", "status",
            "logo_path", "signature_path", "stamp_path", "company_color",
            "pdf_path",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [proforma_id]
        try:
            self._execute(
                f"UPDATE {self.TABLE} SET {set_clause} WHERE id = ? {self._company_filter()}",
                tuple(values) + self._company_params(),
            )
            return True
        except Exception as exc:
            logger.warning("ProformaRepository.update failed for id %s: %s", proforma_id, exc)
            return False

    def update_status(self, proforma_id: int, status: str) -> bool:
        return self.update(proforma_id, status=status)

    def delete(self, proforma_id: int, commit: bool = True) -> bool:
        try:
            self._execute(
                f"DELETE FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
                (proforma_id,) + self._company_params(),
                commit=commit,
            )
            return True
        except Exception as exc:
            logger.warning("ProformaRepository.delete failed for id %s: %s", proforma_id, exc)
            return False

    def count_by_status(self, status: str) -> int:
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE} WHERE status = ? {self._company_filter()}",
            (status,) + self._company_params(),
        )
        return int(row["cnt"]) if row else 0

    def get_next_number(self, format_key: Optional[str] = None) -> str:
        year = datetime.now().year
        fmt_key = format_key or DEFAULT_PROFORMA_FORMAT_KEY
        template = PROFORMA_NUMBER_FORMATS.get(fmt_key, PROFORMA_NUMBER_FORMATS[DEFAULT_PROFORMA_FORMAT_KEY])[0]
        row = self._fetchone(
            f"SELECT COALESCE(MAX(id), 0) + 1 AS nxt FROM {self.TABLE} WHERE 1=1 {self._company_filter()}",
            self._company_params(),
        )
        nxt = int(row["nxt"]) if row else 1
        return template.format(year=year, seq=nxt)
