"""Invoice repository — all invoice DB access consolidated here."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

INVOICE_NUMBER_FORMATS: dict[str, tuple[str, str]] = {
    "inv_year_seq": ("INV-{year}-{seq:04d}", "INV-2026-0001"),
    "inv_seq":      ("INV-{seq:06d}",          "INV-000042"),
    "year_inv_seq": ("{year}-INV-{seq:04d}",  "2026-INV-0001"),
}
DEFAULT_INVOICE_FORMAT_KEY = "inv_year_seq"


class InvoiceRepository(BaseRepository):
    TABLE = "invoices"
    COLUMNS = [
        "id", "trip_id", "invoice_number", "issue_date", "due_date",
        "total_amount", "status", "company_id",
        "client_id", "currency", "notes", "line_items_json",
        "subtotal_net", "total_vat", "total_gross",
        "pdf_path", "created_at", "updated_at",
    ]
    COLUMNS_INVOICE_REMINDERS = [
        "id", "invoice_id", "trip_id", "reminder_type", "days_offset",
        "sent_at", "recipient_email", "status", "company_id",
    ]

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def update(self, invoice_id: int, data: Dict[str, Any]) -> None:
        self._validate_columns(data)
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ? {self._company_filter()}",
            tuple(data.values()) + (invoice_id,) + self._company_params(),
        )

    def delete(self, invoice_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (invoice_id,) + self._company_params(),
        )

    def get_by_id(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (invoice_id,) + self._company_params(),
        )

    def get_by_trip_id(self, trip_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE trip_id = ? {self._company_filter()}",
            (trip_id,) + self._company_params(),
        )

    def get_by_number(self, inv_number: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE invoice_number = ? {self._company_filter()}",
            (inv_number,) + self._company_params(),
        )

    def get_by_client_id(self, client_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT i.*, t.client_name, t.truck_number, t.start_date, t.status AS trip_status
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ? {self._company_filter('i')}
               ORDER BY i.issue_date DESC
               LIMIT ?""",
            (client_id,) + self._company_params() + (limit,),
        )

    def get_outstanding_by_client(self, client_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT i.*, t.client_name, t.truck_number, t.start_date
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ? AND i.status = 'Unpaid' {self._company_filter('i')}
               ORDER BY i.due_date ASC""",
            (client_id,) + self._company_params(),
        )

    def get_outstanding_balance(self, client_id: int) -> float:
        row = self._fetchone(
            f"""SELECT COALESCE(SUM(i.total_amount), 0) AS balance
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ? AND i.status = 'Unpaid' {self._company_filter('i')}""",
            (client_id,) + self._company_params(),
        )
        return round(float(row["balance"]), 2) if row else 0.0

    def get_overdue_by_client(self, client_id: int) -> List[Dict[str, Any]]:
        from datetime import datetime
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return self._fetchall(
            f"""SELECT i.*, t.client_name, t.truck_number, t.start_date
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ? AND i.status = 'Unpaid' AND i.due_date < ? {self._company_filter('i')}
               ORDER BY i.due_date ASC""",
            (client_id, today) + self._company_params(),
        )

    def get_all(self, limit: int = 500) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE 1=1 {self._company_filter()} ORDER BY issue_date DESC LIMIT ?",
            self._company_params() + (limit,),
        )

    def get_by_status(self, status: str, limit: int = 200) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT i.*, t.client_name FROM {self.TABLE} i JOIN trips t ON t.id = i.trip_id WHERE i.status = ? {self._company_filter('i')} ORDER BY i.due_date ASC LIMIT ?",
            (status,) + self._company_params() + (limit,),
        )

    def get_payment_summary(self, client_id: int) -> Optional[Dict[str, Any]]:
        from datetime import datetime
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return self._fetchone(
            f"""SELECT
                 COALESCE(SUM(i.total_amount), 0) AS total_billed,
                 COALESCE(SUM(CASE WHEN i.status = 'Paid' THEN i.total_amount ELSE 0 END), 0) AS total_paid,
                 COALESCE(SUM(CASE WHEN i.status = 'Unpaid' THEN i.total_amount ELSE 0 END), 0) AS unpaid,
                 COALESCE(SUM(CASE WHEN i.status = 'Unpaid' AND i.due_date < ? THEN i.total_amount ELSE 0 END), 0) AS overdue
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ? {self._company_filter('i')}""",
            (today, client_id) + self._company_params(),
        )

    def get_dunner_due_invoices(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT
                i.id          AS invoice_id,
                i.invoice_number,
                i.due_date,
                i.total_amount,
                i.issue_date,
                t.id          AS trip_id,
                t.client_name,
                t.client_id,
                t.truck_number AS truck_plate,
                t.driver_name,
                COALESCE(t.currency, 'EUR') AS currency,
                c.email       AS client_email,
                c.name        AS client_company_name,
                c.contact_person AS client_contact
            FROM invoices i
            JOIN trips t ON t.id = i.trip_id
            LEFT JOIN clients c ON c.id = t.client_id
            WHERE i.status = 'Unpaid'
              AND i.due_date IS NOT NULL
              AND i.due_date != ''
              {self._company_filter('i')}
            ORDER BY i.due_date ASC""",
            self._company_params(),
        )

    def get_unpaid_with_client_trip_data(self, status: str = "Unpaid") -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT i.*, t.client_name, t.truck_number, t.start_date, t.status AS trip_status
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE i.status = ? {self._company_filter('i')}
               ORDER BY i.due_date ASC""",
            (status,) + self._company_params(),
        )

    def get_client_email(self, client_name: str) -> Optional[str]:
        from repositories.client_repository import ClientRepository
        return ClientRepository(self.db).get_client_email_by_name(client_name)

    def has_reminder_been_sent(self, invoice_id: int, reminder_type: str) -> bool:
        row = self._fetchone(
            f"SELECT 1 FROM invoice_reminders "
            f"WHERE invoice_id = ? AND reminder_type = ? AND status = 'sent' {self._company_filter()} LIMIT 1",
            (invoice_id, reminder_type) + self._company_params(),
        )
        return row is not None

    def get_reminder_count(self, invoice_id: int) -> int:
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM invoice_reminders "
            f"WHERE invoice_id = ? AND status = 'sent' {self._company_filter()}",
            (invoice_id,) + self._company_params(),
        )
        return int(row["cnt"]) if row else 0

    def insert_reminder(self, invoice_id: int, trip_id: int, reminder_type: str,
                        days_offset: int, sent_at: str, recipient_email: str,
                        status: str = "sent") -> int:
        data = {
            "invoice_id": invoice_id,
            "trip_id": trip_id,
            "reminder_type": reminder_type,
            "days_offset": days_offset,
            "sent_at": sent_at,
            "recipient_email": recipient_email,
            "status": status,
        }
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_INVOICE_REMINDERS))
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO invoice_reminders ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def get_invoice_count(self, client_id: int) -> int:
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM invoices i JOIN trips t ON t.id = i.trip_id WHERE t.client_id = ? {self._company_filter('i')}",
            (client_id,) + self._company_params(),
        )
        return int(row["cnt"]) if row else 0

    def get_next_number(self, format_key: Optional[str] = None) -> str:
        """Generate the next invoice number using the configured format."""
        year = datetime.now().year
        fmt_key = format_key or DEFAULT_INVOICE_FORMAT_KEY
        template = INVOICE_NUMBER_FORMATS.get(fmt_key, INVOICE_NUMBER_FORMATS[DEFAULT_INVOICE_FORMAT_KEY])[0]
        row = self._fetchone(
            f"SELECT COALESCE(MAX(id), 0) + 1 AS nxt FROM {self.TABLE} WHERE 1=1 {self._company_filter()}",
            self._company_params(),
        )
        nxt = int(row["nxt"]) if row else 1
        return template.format(year=year, seq=nxt)
