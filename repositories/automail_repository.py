"""AutoMail repository — all automail configuration DB access.

Provides CRUD for templates, schedules, client overrides, and
settings.  Follows the same pattern as other repositories in this
package.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from repositories import BaseRepository

logger = logging.getLogger(__name__)


class AutoMailRepository(BaseRepository):
    """Data access for AutoMail / Dunner configuration tables."""

    # ── Templates ──────────────────────────────────────────────────────────

    def get_all_templates(self) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM automail_templates ORDER BY is_default DESC, name ASC"
        )

    def get_template_by_id(self, template_id: int) -> Optional[dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM automail_templates WHERE id = ?", (template_id,)
        )

    def get_default_template(self) -> Optional[dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM automail_templates WHERE is_default = 1 LIMIT 1"
        )

    _TEMPLATE_COLS = {"name", "subject", "body_text", "body_html", "variables_json", "is_default"}

    def create_template(self, data: dict[str, Any]) -> int:
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        data = {k: v for k, v in data.items() if k in self._TEMPLATE_COLS}
        data["created_at"] = now
        data["updated_at"] = now
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO automail_templates ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def update_template(self, template_id: int, data: dict[str, Any]) -> None:
        data = dict(data)
        data["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE automail_templates SET {sets} WHERE id = ?",
            tuple(data.values()) + (template_id,),
        )

    def delete_template(self, template_id: int) -> None:
        self._execute(
            "DELETE FROM automail_templates WHERE id = ?", (template_id,)
        )

    # ── Schedules ──────────────────────────────────────────────────────────

    def get_all_schedules(self) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT s.*, t.name AS template_name "
            "FROM automail_schedules s "
            "LEFT JOIN automail_templates t ON t.id = s.template_id "
            "ORDER BY s.sort_order ASC"
        )

    def get_active_schedules(self) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT s.*, t.name AS template_name, t.subject, t.body_text, t.body_html "
            "FROM automail_schedules s "
            "LEFT JOIN automail_templates t ON t.id = s.template_id "
            "WHERE s.is_active = 1 "
            "ORDER BY s.sort_order ASC"
        )

    def get_schedule_by_id(self, schedule_id: int) -> Optional[dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM automail_schedules WHERE id = ?", (schedule_id,)
        )

    _SCHEDULE_COLS = {
        "name", "trigger_type", "days_offset", "template_id",
        "is_active", "sort_order", "attach_invoice", "attach_cmr", "attach_all_docs",
    }

    def create_schedule(self, data: dict[str, Any]) -> int:
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        data = {k: v for k, v in data.items() if k in self._SCHEDULE_COLS}
        if "sort_order" not in data:
            max_row = self._fetchone(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS nxt FROM automail_schedules"
            )
            data["sort_order"] = max_row["nxt"] if max_row else 0
        data["created_at"] = now
        data["updated_at"] = now
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO automail_schedules ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def update_schedule(self, schedule_id: int, data: dict[str, Any]) -> None:
        data = {k: v for k, v in data.items() if k in self._SCHEDULE_COLS}
        if not data:
            logger.warning("update_schedule called with no valid columns for schedule #%d", schedule_id)
            return
        data["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE automail_schedules SET {sets} WHERE id = ?",
            tuple(data.values()) + (schedule_id,),
        )

    def delete_schedule(self, schedule_id: int) -> None:
        self._execute(
            "DELETE FROM automail_schedules WHERE id = ?", (schedule_id,)
        )

    def reorder_schedules(self, ordered_ids: list[int]) -> None:
        """Update ``sort_order`` for all given IDs in the order provided."""
        for idx, sid in enumerate(ordered_ids):
            self._execute(
                "UPDATE automail_schedules SET sort_order = ? WHERE id = ?",
                (idx, sid),
                commit=False,
            )
        self.commit_transaction()

    # ── Client Overrides ───────────────────────────────────────────────────

    def get_override(self, client_id: int) -> Optional[dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM automail_client_overrides WHERE client_id = ?",
            (client_id,),
        )

    def get_all_overrides(self) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM automail_client_overrides"
        )

    def upsert_override(self, client_id: int, data: dict[str, Any]) -> None:
        """Insert or update a client override."""
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        existing = self.get_override(client_id)
        if existing:
            data["updated_at"] = now
            sets = ", ".join(f"{k} = ?" for k in data)
            self._execute(
                f"UPDATE automail_client_overrides SET {sets} WHERE client_id = ?",
                tuple(data.values()) + (client_id,),
            )
        else:
            data["client_id"] = client_id
            data["created_at"] = now
            data["updated_at"] = now
            cols = ", ".join(data.keys())
            vals = ", ".join("?" for _ in data)
            self._execute_insert(
                f"INSERT INTO automail_client_overrides ({cols}) VALUES ({vals})",
                tuple(data.values()),
            )

    def delete_override(self, client_id: int) -> None:
        self._execute(
            "DELETE FROM automail_client_overrides WHERE client_id = ?",
            (client_id,),
        )

    # ── Settings ───────────────────────────────────────────────────────────

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self._fetchone(
            "SELECT value FROM automail_settings WHERE key = ?", (key,)
        )
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self._execute(
            "INSERT OR REPLACE INTO automail_settings (key, value) VALUES (?, ?)",
            (key, value),
        )

    def get_all_settings(self) -> dict[str, str]:
        rows = self._fetchall("SELECT key, value FROM automail_settings")
        return {r["key"]: r["value"] for r in rows}

    def log_manual_send(self, invoice_id: int, trip_id: int, recipient: str) -> None:
        from datetime import datetime
        self._execute(
            "INSERT INTO invoice_reminders "
            "(invoice_id, trip_id, reminder_type, days_offset, sent_at, recipient_email, status) "
            "VALUES (?, ?, 'manual_send', 0, ?, ?, 'sent')",
            (invoice_id, trip_id, datetime.now().isoformat(), recipient),
        )

    def log_email(self, trip_id: Optional[int], recipient: str, subject: str, status: str = "sent") -> None:
        from datetime import datetime
        self._execute(
            "INSERT INTO email_logs (trip_id, recipient, subject, timestamp, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (trip_id, recipient, subject, datetime.now().isoformat(), status),
        )

    def skip_reminder(self, invoice_id: int, trip_id: int) -> None:
        from datetime import datetime
        self._execute(
            "INSERT INTO invoice_reminders "
            "(invoice_id, trip_id, reminder_type, days_offset, sent_at, recipient_email, status) "
            "VALUES (?, ?, 'manual_skip', 0, ?, '', 'skipped')",
            (invoice_id, trip_id, datetime.now().isoformat()),
        )

    def cancel_all_reminders(self, invoice_id: int, trip_id: int) -> None:
        from datetime import datetime
        self._execute(
            "INSERT INTO invoice_reminders "
            "(invoice_id, trip_id, reminder_type, days_offset, sent_at, recipient_email, status) "
            "VALUES (?, ?, 'manual_cancel_all', 0, ?, '', 'cancelled')",
            (invoice_id, trip_id, datetime.now().isoformat()),
        )

    def get_sent_reminder_count(self, invoice_id: int) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM invoice_reminders "
            "WHERE invoice_id = ? AND status IN ('sent', 'scheduled')",
            (invoice_id,),
        )
        return row["cnt"] if row else 0

    def get_email_history(self, search: str = "", status_filter: str = "",
                          page: int = 0, page_size: int = 20) -> tuple[list[dict[str, Any]], int]:
        offset = page * page_size
        conditions = ["1=1"]
        params: list = []
        if search:
            conditions.append(
                "(e.subject LIKE ? OR e.recipient LIKE ? "
                "OR COALESCE(i.invoice_number, '') LIKE ? "
                "OR COALESCE(t.client_name, '') LIKE ?)"
            )
            like = f"%{search}%"
            params.extend([like, like, like, like])
        if status_filter:
            conditions.append("e.status = ?")
            params.append(status_filter)
        where = " AND ".join(conditions)
        count_row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM email_logs e "
            f"LEFT JOIN invoices i ON e.trip_id = i.trip_id "
            f"LEFT JOIN trips t ON e.trip_id = t.id "
            f"WHERE {where}",
            tuple(params),
        )
        total = count_row["cnt"] if count_row else 0
        rows = self._fetchall(
            f"SELECT e.id, e.trip_id, e.recipient, e.subject, e.timestamp, e.status, "
            f"i.invoice_number, i.total_amount, i.due_date, "
            f"t.client_name "
            f"FROM email_logs e "
            f"LEFT JOIN invoices i ON e.trip_id = i.trip_id "
            f"LEFT JOIN trips t ON e.trip_id = t.id "
            f"WHERE {where} "
            f"ORDER BY e.timestamp DESC "
            f"LIMIT ? OFFSET ?",
            tuple(params) + (page_size, offset),
        )
        return rows, total

    def get_email_stats(self, days: int = 30) -> dict[str, Any]:
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        sent_row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM email_logs "
            "WHERE timestamp >= ? AND status = 'sent'",
            (cutoff,),
        )
        emails_sent = sent_row["cnt"] if sent_row else 0
        failed_row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM email_logs "
            "WHERE timestamp >= ? AND status IN ('failed', 'error')",
            (cutoff,),
        )
        emails_failed = failed_row["cnt"] if failed_row else 0
        return {"emails_sent": emails_sent, "emails_failed": emails_failed}

    def search_emails(self, query: str) -> list[dict[str, Any]]:
        like = f"%{query}%"
        return self._fetchall(
            "SELECT e.id, e.trip_id, e.recipient, e.subject, e.timestamp, e.status, "
            "i.invoice_number, t.client_name "
            "FROM email_logs e "
            "LEFT JOIN invoices i ON e.trip_id = i.trip_id "
            "LEFT JOIN trips t ON e.trip_id = t.id "
            "WHERE e.subject LIKE ? OR e.recipient LIKE ? "
            "OR i.invoice_number LIKE ? OR t.client_name LIKE ? "
            "ORDER BY e.timestamp DESC LIMIT 50",
            (like, like, like, like),
        )

    def get_reminder_status(self, invoice_id: int, trip_id: int,
                            reminder_type: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM invoice_reminders "
            "WHERE invoice_id = ? AND trip_id = ? AND reminder_type = ? "
            "ORDER BY id DESC LIMIT 1",
            (invoice_id, trip_id, reminder_type),
        )

    def get_reminder_counts(self, status: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM invoice_reminders WHERE status = ?",
            (status,),
        )
        return row["cnt"] if row else 0

    def get_unpaid_invoices_for_reminders(self, search: str = "") -> list[dict[str, Any]]:
        query = """
            SELECT
                i.id          AS invoice_id,
                i.invoice_number,
                i.due_date,
                i.total_amount,
                i.issue_date,
                t.id          AS trip_id,
                t.client_name,
                t.client_id,
                COALESCE(t.currency, 'EUR') AS currency,
                c.email       AS client_email,
                c.name        AS client_company_name
            FROM invoices i
            JOIN trips t ON t.id = i.trip_id
            LEFT JOIN clients c ON c.id = t.client_id
            WHERE i.status = 'Unpaid'
              AND i.due_date IS NOT NULL
              AND i.due_date != ''
        """
        params: list[Any] = []
        if search:
            query += " AND (i.invoice_number LIKE ? OR t.client_name LIKE ? OR c.email LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])
        query += " ORDER BY i.due_date ASC"
        return self._fetchall(query, tuple(params))

    def get_recent_email_logs(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self._fetchall(
            "SELECT id, recipient, subject, timestamp, status "
            "FROM email_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return rows
