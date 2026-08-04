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
    ]

    def claim(self, document_id: int, recipient: str) -> bool:
        """Atomically claim a send for ``(document_id, recipient)``.

        Inserts a ``pending`` row and commits immediately.  Returns ``True``
        if the row was inserted (this caller owns the send); ``False`` when a
        send is already in flight or complete for that pair — the caller
        should skip sending and log a warning.
        """
        now = self._now()
        query = self._adapt_query(
            "INSERT OR IGNORE INTO sent_emails "
            "(document_id, recipient, status, created_at) "
            "VALUES (?, ?, 'pending', ?)"
        )
        cursor = self.db.conn.execute(query, (document_id, recipient, now))
        self.db.conn.commit()
        return cursor.rowcount > 0

    def mark_sent(self, document_id: int, recipient: str) -> None:
        """Record a successful send for ``(document_id, recipient)``."""
        query = self._adapt_query(
            "UPDATE sent_emails SET status = 'sent', sent_at = ? "
            "WHERE document_id = ? AND recipient = ?"
        )
        self.db.conn.execute(query, (self._now(), document_id, recipient))
        self.db.conn.commit()

    def remove_pending(self, document_id: int, recipient: str) -> None:
        """Drop any claim so a retry can re-attempt the send."""
        query = self._adapt_query(
            "DELETE FROM sent_emails WHERE document_id = ? AND recipient = ?"
        )
        self.db.conn.execute(query, (document_id, recipient))
        self.db.conn.commit()

    def get_by_document(self, document_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE document_id = ? ORDER BY id",
            (document_id,),
        )

    @staticmethod
    def _now() -> str:
        from datetime import datetime
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"
