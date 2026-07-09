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

    COLUMNS_AUTOMAIL_TEMPLATES = [
        "id", "name", "subject", "body_text", "body_html", "variables_json",
        "is_default", "created_at", "updated_at", "company_id",
    ]
    COLUMNS_AUTOMAIL_SCHEDULES = [
        "id", "name", "trigger_type", "days_offset", "template_id",
        "is_active", "sort_order", "attach_invoice", "attach_cmr",
        "attach_all_docs", "created_at", "updated_at", "company_id",
    ]
    COLUMNS_AUTOMAIL_OVERRIDES = [
        "id", "client_id", "template_id", "is_active", "override_json",
        "is_disabled", "custom_template_id", "custom_days_offset",
        "custom_trigger_type", "skip_attachments", "notes",
        "created_at", "updated_at", "company_id",
    ]
    COLUMNS_AUTOMAIL_SETTINGS = [
        "key", "value", "company_id",
    ]
    COLUMNS_EMAIL_LOGS = [
        "id", "trip_id", "recipient", "subject", "timestamp", "status", "company_id",
    ]
    COLUMNS_INVOICE_REMINDERS = [
        "id", "invoice_id", "trip_id", "reminder_type", "days_offset",
        "sent_at", "recipient_email", "status", "company_id",
    ]

    # ── Templates ──────────────────────────────────────────────────────────

    def get_all_templates(self) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM automail_templates WHERE 1=1 " + self._company_filter() + " ORDER BY is_default DESC, name ASC",
            self._company_params(),
        )

    def get_template_by_id(self, template_id: int) -> Optional[dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM automail_templates WHERE id = ? " + self._company_filter(),
            (template_id,) + self._company_params(),
        )

    def get_default_template(self) -> Optional[dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM automail_templates WHERE is_default = 1 " + self._company_filter() + " LIMIT 1",
            self._company_params(),
        )

    _TEMPLATE_COLS = {"name", "subject", "body_text", "body_html", "variables_json", "is_default"}

    def create_template(self, data: dict[str, Any]) -> int:
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_AUTOMAIL_TEMPLATES))
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        data = {k: v for k, v in data.items() if k in self._TEMPLATE_COLS}
        data["created_at"] = now
        data["updated_at"] = now
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO automail_templates ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def update_template(self, template_id: int, data: dict[str, Any]) -> None:
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_AUTOMAIL_TEMPLATES))
        data = dict(data)
        data["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE automail_templates SET {sets} WHERE id = ? {self._company_filter()}",
            tuple(data.values()) + (template_id,) + self._company_params(),
        )

    def delete_template(self, template_id: int) -> None:
        self._execute(
            "DELETE FROM automail_templates WHERE id = ? " + self._company_filter(),
            (template_id,) + self._company_params(),
        )

    # ── Schedules ──────────────────────────────────────────────────────────

    def get_all_schedules(self) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT s.*, t.name AS template_name "
            "FROM automail_schedules s "
            "LEFT JOIN automail_templates t ON t.id = s.template_id "
            "WHERE 1=1 " + self._company_filter("s") + " "
            "ORDER BY s.sort_order ASC",
            self._company_params(),
        )

    def get_active_schedules(self) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT s.*, t.name AS template_name, t.subject, t.body_text, t.body_html "
            "FROM automail_schedules s "
            "LEFT JOIN automail_templates t ON t.id = s.template_id "
            "WHERE s.is_active = 1 " + self._company_filter("s") + " "
            "ORDER BY s.sort_order ASC",
            self._company_params(),
        )

    def get_schedule_by_id(self, schedule_id: int) -> Optional[dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM automail_schedules WHERE id = ? " + self._company_filter(),
            (schedule_id,) + self._company_params(),
        )

    _SCHEDULE_COLS = {
        "name", "trigger_type", "days_offset", "template_id",
        "is_active", "sort_order", "attach_invoice", "attach_cmr", "attach_all_docs",
    }

    def create_schedule(self, data: dict[str, Any]) -> int:
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_AUTOMAIL_SCHEDULES))
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        data = {k: v for k, v in data.items() if k in self._SCHEDULE_COLS}
        if "sort_order" not in data:
            max_row = self._fetchone(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS nxt FROM automail_schedules "
                + self._company_filter(),
                self._company_params(),
            )
            data["sort_order"] = max_row["nxt"] if max_row else 0
        data["created_at"] = now
        data["updated_at"] = now
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO automail_schedules ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def update_schedule(self, schedule_id: int, data: dict[str, Any]) -> None:
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_AUTOMAIL_SCHEDULES))
        data = {k: v for k, v in data.items() if k in self._SCHEDULE_COLS}
        if not data:
            logger.warning("update_schedule called with no valid columns for schedule #%d", schedule_id)
            return
        data["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE automail_schedules SET {sets} WHERE id = ? {self._company_filter()}",
            tuple(data.values()) + (schedule_id,) + self._company_params(),
        )

    def delete_schedule(self, schedule_id: int) -> None:
        self._execute(
            "DELETE FROM automail_schedules WHERE id = ? " + self._company_filter(),
            (schedule_id,) + self._company_params(),
        )

    def reorder_schedules(self, ordered_ids: list[int]) -> None:
        """Update ``sort_order`` for all given IDs in the order provided."""
        company_filter = self._company_filter()
        company_params = self._company_params()
        for idx, sid in enumerate(ordered_ids):
            self._execute(
                f"UPDATE automail_schedules SET sort_order = ? WHERE id = ? {company_filter}",
                (idx, sid) + company_params,
                commit=False,
            )
        self.commit_transaction()

    # ── Client Overrides ───────────────────────────────────────────────────

    def get_override(self, client_id: int) -> Optional[dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM automail_client_overrides WHERE client_id = ? "
            + self._company_filter(),
            (client_id,) + self._company_params(),
        )

    def get_all_overrides(self) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM automail_client_overrides WHERE 1=1 " + self._company_filter(),
            self._company_params(),
        )

    def upsert_override(self, client_id: int, data: dict[str, Any]) -> None:
        """Insert or update a client override."""
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_AUTOMAIL_OVERRIDES))
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        existing = self.get_override(client_id)
        if existing:
            data["updated_at"] = now
            sets = ", ".join(f"{k} = ?" for k in data)
            self._execute(
                f"UPDATE automail_client_overrides SET {sets} WHERE client_id = ? {self._company_filter()}",
                tuple(data.values()) + (client_id,) + self._company_params(),
            )
        else:
            data["client_id"] = client_id
            data["created_at"] = now
            data["updated_at"] = now
            data = self._set_company_from_context(data)
            cols = ", ".join(data.keys())
            vals = ", ".join("?" for _ in data)
            self._execute_insert(
                f"INSERT INTO automail_client_overrides ({cols}) VALUES ({vals})",
                tuple(data.values()),
            )

    def delete_override(self, client_id: int) -> None:
        self._execute(
            "DELETE FROM automail_client_overrides WHERE client_id = ? "
            + self._company_filter(),
            (client_id,) + self._company_params(),
        )

    # ── Settings ───────────────────────────────────────────────────────────

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self._fetchone(
            "SELECT value FROM automail_settings WHERE key = ? " + self._company_filter(),
            (key,) + self._company_params(),
        )
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        data = {"key": key, "value": value}
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_AUTOMAIL_SETTINGS))
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        self._execute(
            f"INSERT OR REPLACE INTO automail_settings ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def get_all_settings(self) -> dict[str, str]:
        rows = self._fetchall(
            "SELECT key, value FROM automail_settings WHERE 1=1 " + self._company_filter(),
            self._company_params(),
        )
        return {r["key"]: r["value"] for r in rows}

    def log_manual_send(self, invoice_id: int, trip_id: int, recipient: str) -> None:
        from datetime import datetime
        data = {
            "invoice_id": invoice_id, "trip_id": trip_id,
            "reminder_type": "manual_send", "days_offset": 0,
            "sent_at": datetime.now().isoformat(), "recipient_email": recipient,
            "status": "sent",
        }
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_INVOICE_REMINDERS))
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        self._execute(
            f"INSERT INTO invoice_reminders ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def log_email(self, trip_id: Optional[int], recipient: str, subject: str, status: str = "sent") -> None:
        from datetime import datetime
        data = {
            "trip_id": trip_id, "recipient": recipient, "subject": subject,
            "timestamp": datetime.now().isoformat(), "status": status,
        }
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_EMAIL_LOGS))
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        self._execute(
            f"INSERT INTO email_logs ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def skip_reminder(self, invoice_id: int, trip_id: int) -> None:
        from datetime import datetime
        data = {
            "invoice_id": invoice_id, "trip_id": trip_id,
            "reminder_type": "manual_skip", "days_offset": 0,
            "sent_at": datetime.now().isoformat(), "recipient_email": "",
            "status": "skipped",
        }
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_INVOICE_REMINDERS))
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        self._execute(
            f"INSERT INTO invoice_reminders ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def cancel_all_reminders(self, invoice_id: int, trip_id: int) -> None:
        from datetime import datetime
        data = {
            "invoice_id": invoice_id, "trip_id": trip_id,
            "reminder_type": "manual_cancel_all", "days_offset": 0,
            "sent_at": datetime.now().isoformat(), "recipient_email": "",
            "status": "cancelled",
        }
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_INVOICE_REMINDERS))
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        self._execute(
            f"INSERT INTO invoice_reminders ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def get_sent_reminder_count(self, invoice_id: int) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM invoice_reminders "
            "WHERE invoice_id = ? AND status IN ('sent', 'scheduled') "
            + self._company_filter(),
            (invoice_id,) + self._company_params(),
        )
        return row["cnt"] if row else 0

    def get_email_history(self, search: str = "", status_filter: str = "",
                          page: int = 0, page_size: int = 20) -> tuple[list[dict[str, Any]], int]:
        offset = page * page_size
        company_filter = self._company_filter("e")
        company_params = list(self._company_params())
        conditions = [f"1=1 {company_filter}".strip()] if company_filter else ["1=1"]
        params: list = company_params if company_filter else []
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
            "WHERE timestamp >= ? AND status = 'sent' "
            + self._company_filter(),
            (cutoff,) + self._company_params(),
        )
        emails_sent = sent_row["cnt"] if sent_row else 0
        failed_row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM email_logs "
            "WHERE timestamp >= ? AND status IN ('failed', 'error') "
            + self._company_filter(),
            (cutoff,) + self._company_params(),
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
            "WHERE (e.subject LIKE ? OR e.recipient LIKE ? "
            "OR i.invoice_number LIKE ? OR t.client_name LIKE ?) "
            + self._company_filter("e") + " "
            "ORDER BY e.timestamp DESC LIMIT 50",
            (like, like, like, like) + self._company_params(),
        )

    def get_reminder_status(self, invoice_id: int, trip_id: int,
                            reminder_type: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM invoice_reminders "
            "WHERE invoice_id = ? AND trip_id = ? AND reminder_type = ? "
            + self._company_filter() + " "
            "ORDER BY id DESC LIMIT 1",
            (invoice_id, trip_id, reminder_type) + self._company_params(),
        )

    def get_reminder_counts(self, status: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM invoice_reminders WHERE status = ? "
            + self._company_filter(),
            (status,) + self._company_params(),
        )
        return row["cnt"] if row else 0

    def get_unpaid_invoices_for_reminders(self, search: str = "") -> list[dict[str, Any]]:
        query = f"""
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
              {self._company_filter('t')}
        """
        params: list[Any] = list(self._company_params())
        if search:
            query += " AND (i.invoice_number LIKE ? OR t.client_name LIKE ? OR c.email LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])
        query += " ORDER BY i.due_date ASC"
        return self._fetchall(query, tuple(params))

    def get_recent_email_logs(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self._fetchall(
            "SELECT id, recipient, subject, timestamp, status "
            "FROM email_logs WHERE 1=1 " + self._company_filter() + " "
            "ORDER BY id DESC LIMIT ?",
            self._company_params() + (limit,),
        )
        return rows
