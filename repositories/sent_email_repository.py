"""Sent-email dedup repository — prevents double-send on Celery retry.

The ``sent_emails`` table carries ``UNIQUE(document_id, recipient)`` so a
retried ``build_email_package`` cannot email the same document twice to the
same recipient.  ``claim()`` atomically inserts a ``pending`` row (``INSERT OR
IGNORE`` → ``ON CONFLICT DO NOTHING`` on PostgreSQL); only the call that
actually inserted the row owns the send.
"""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class SentEmailRepository(BaseRepository):
    TABLE = "sent_emails"
    COLUMNS = [
        "id", "document_id", "recipient", "status", "sent_at", "created_at",
        "company_id",
    ]

    def claim(self, document_id: int, recipient: str) -> bool:
        """Atomically claim a send for ``(document_id, recipient)``.

        Inserts a ``pending`` row and commits immediately.  Returns ``True``
        if the row was inserted (this caller owns the send); ``False`` when a
        send is already in flight or complete for that pair — the caller
        should skip sending and log a warning.
        """
        now = self._now()
        data = self._set_company_from_context({
            "document_id": document_id,
            "recipient": recipient,
            "status": "pending",
            "created_at": now,
        })
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        query = self._adapt_query(
            f"INSERT OR IGNORE INTO sent_emails ({cols}) VALUES ({vals})"
        )
        cursor = self.db.execute(query, tuple(data.values()))
        self.db.conn.commit()
        return cursor.rowcount > 0

    def mark_sent(self, document_id: int, recipient: str) -> None:
        """Record a successful send for ``(document_id, recipient)``."""
        query = self._adapt_query(
            f"UPDATE sent_emails SET status = 'sent', sent_at = ? "
            f"WHERE document_id = ? AND recipient = ? {self._company_filter()}"
        )
        self.db.execute(
            query,
            (self._now(), document_id, recipient) + self._company_params(),
        )
        self.db.conn.commit()

    def remove_pending(self, document_id: int, recipient: str) -> None:
        """Drop any claim so a retry can re-attempt the send."""
        query = self._adapt_query(
            f"DELETE FROM sent_emails WHERE document_id = ? AND recipient = ? "
            f"{self._company_filter()}"
        )
        self.db.execute(
            query, (document_id, recipient) + self._company_params(),
        )
        self.db.conn.commit()

    def get_by_document(self, document_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE document_id = ? "
            f"{self._company_filter()} ORDER BY id",
            (document_id,) + self._company_params(),
        )

    @staticmethod
    def _now() -> str:
        from datetime import datetime
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"
