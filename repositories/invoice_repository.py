"""Invoice repository — all invoice DB access consolidated here."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class InvoiceRepository(BaseRepository):
    TABLE = "invoices"

    def get_by_id(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ?", (invoice_id,)
        )

    def get_by_trip_id(self, trip_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE trip_id = ?", (trip_id,)
        )

    def get_by_number(self, inv_number: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE invoice_number = ?", (inv_number,)
        )

    def get_by_client_id(self, client_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        return self._fetchall(
            """SELECT i.*, t.client_name, t.truck_number, t.start_date, t.status AS trip_status
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ?
               ORDER BY i.issue_date DESC
               LIMIT ?""",
            (client_id, limit),
        )

    def get_outstanding_by_client(self, client_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            """SELECT i.*, t.client_name, t.truck_number, t.start_date
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ? AND i.status = 'Unpaid'
               ORDER BY i.due_date ASC""",
            (client_id,),
        )

    def get_outstanding_balance(self, client_id: int) -> float:
        row = self._fetchone(
            """SELECT COALESCE(SUM(i.total_amount), 0) AS balance
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ? AND i.status = 'Unpaid'""",
            (client_id,),
        )
        return round(float(row["balance"]), 2) if row else 0.0

    def get_overdue_by_client(self, client_id: int) -> List[Dict[str, Any]]:
        from datetime import datetime
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return self._fetchall(
            """SELECT i.*, t.client_name, t.truck_number, t.start_date
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ? AND i.status = 'Unpaid' AND i.due_date < ?
               ORDER BY i.due_date ASC""",
            (client_id, today),
        )

    def get_all(self, limit: int = 500) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} ORDER BY issue_date DESC LIMIT ?",
            (limit,),
        )

    def get_by_status(self, status: str, limit: int = 200) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT i.*, t.client_name FROM {self.TABLE} i JOIN trips t ON t.id = i.trip_id WHERE i.status = ? ORDER BY i.due_date ASC LIMIT ?",
            (status, limit),
        )

    def get_payment_summary(self, client_id: int) -> Optional[Dict[str, Any]]:
        from datetime import datetime
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return self._fetchone(
            """SELECT
                 COALESCE(SUM(i.total_amount), 0) AS total_billed,
                 COALESCE(SUM(CASE WHEN i.status = 'Paid' THEN i.total_amount ELSE 0 END), 0) AS total_paid,
                 COALESCE(SUM(CASE WHEN i.status = 'Unpaid' THEN i.total_amount ELSE 0 END), 0) AS unpaid,
                 COALESCE(SUM(CASE WHEN i.status = 'Unpaid' AND i.due_date < ? THEN i.total_amount ELSE 0 END), 0) AS overdue
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ?""",
            (today, client_id),
        )

    def get_invoice_count(self, client_id: int) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM invoices i JOIN trips t ON t.id = i.trip_id WHERE t.client_id = ?",
            (client_id,),
        )
        return int(row["cnt"]) if row else 0
