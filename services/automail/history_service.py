"""Email history and statistics for AutoMail.

Queries the existing ``email_logs`` and ``invoice_reminders`` tables
to provide a searchable, filterable history view and aggregate
statistics for the timeline dashboard.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from repositories.automail_repository import AutoMailRepository

logger = logging.getLogger(__name__)


class HistoryService:
    """Service for email history queries and statistics."""

    def __init__(self, db) -> None:
        if db is None:
            raise ValueError("HistoryService requires a valid db connection")
        self._db = db
        self._repo = AutoMailRepository(db)

    def get_email_history(
        self,
        search: str = "",
        status_filter: str = "",
        page: int = 0,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        return self._repo.get_email_history(search, status_filter, page, page_size)

    def get_stats(self, days: int = 30) -> dict[str, Any]:
        email_stats = self._repo.get_email_stats(days)
        overdue_row = self._repo._fetchone(
            "SELECT COALESCE(SUM(i.total_amount), 0) AS total, "
            "COUNT(*) AS cnt "
            "FROM invoices i "
            "JOIN trips t ON t.id = i.trip_id "
            "WHERE i.status = 'Unpaid' AND i.due_date < ? "
            "AND i.due_date IS NOT NULL AND i.due_date != ''",
            (datetime.now().strftime("%Y-%m-%d"),),
        )
        total_overdue_amount = float(overdue_row["total"]) if overdue_row else 0.0
        overdue_invoice_count = overdue_row["cnt"] if overdue_row else 0

        return {
            "emails_sent": email_stats["emails_sent"],
            "emails_failed": email_stats["emails_failed"],
            "total_outstanding_amount": total_overdue_amount,
            "overdue_invoice_count": overdue_invoice_count,
        }

    def search_emails(self, query: str) -> list[dict[str, Any]]:
        return self._repo.search_emails(query)
