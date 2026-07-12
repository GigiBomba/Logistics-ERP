"""Email history and statistics for AutoMail.

Queries the existing ``email_logs`` and ``invoice_reminders`` tables
to provide a searchable, filterable history view and aggregate
statistics for the timeline dashboard.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from models.common import ServiceResult, ErrorDetail
from repositories.automail_repository import AutoMailRepository

logger = logging.getLogger(__name__)


class HistoryService:
    """Service for email history queries and statistics."""

    def __init__(self, db) -> None:
        if db is None:
            raise ValueError("HistoryService requires a valid db connection")
        self._db = db
        self._repo = AutoMailRepository(db)

    def get_history(
        self,
        client_id: Optional[int] = None,
        limit: int = 100,
    ) -> ServiceResult[list[dict]]:
        """Return email history, optionally filtered by client.

        Args:
            client_id: Optional client ID to filter by.
            limit: Maximum number of records to return (default 100).

        Returns:
            ServiceResult containing a list of email log dicts.
        """
        try:
            if client_id is not None:
                rows = self._repo._fetchall(
                    "SELECT e.id, e.trip_id, e.recipient, e.subject, "
                    "e.timestamp, e.status, "
                    "i.invoice_number, t.client_name "
                    "FROM email_logs e "
                    "LEFT JOIN invoices i ON e.trip_id = i.trip_id "
                    "LEFT JOIN trips t ON e.trip_id = t.id "
                    "WHERE t.client_id = ? "
                    + self._repo._company_filter("e")
                    + " "
                    "ORDER BY e.timestamp DESC LIMIT ?",
                    (client_id,) + self._repo._company_params() + (limit,),
                )
            else:
                rows = self._repo.get_recent_email_logs(limit)
            logger.info("Retrieved %d history entries", len(rows))
            return ServiceResult(success=True, data=rows)
        except Exception as exc:
            logger.error("Failed to get email history: %s", exc)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="history_failed")],
            )

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
