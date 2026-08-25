"""Sync outbox service — the capture-layer read/drain API (Phase 1).

The outbox is written by SQLite triggers (see
``DatabaseManager._ensure_outbox_triggers``); this service is the
read/drain API the sync engine (Phase 2+) uses to push pending rows to
the cloud API and to coordinate echo suppression during pull-apply
(Phase 4).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from database import schema as _schema
from database.time_utils import utc_now_iso

logger = logging.getLogger(__name__)

_SYNC_IN_PROGRESS_KEY = "sync_in_progress"

# Reverse of ``SYNCABLE_ENTITIES`` (entity type → table name).  Built once
# at import; all values are distinct so the reverse lookup is unambiguous.
_ENTITY_TYPE_TO_TABLE = {v: k for k, v in _schema.SYNCABLE_ENTITIES.items()}


class SyncOutboxService:
    """Read/drain API over the ``sync_outbox`` / ``sync_meta`` tables."""

    def __init__(self, db) -> None:
        self.db = db

    def pending(self, limit: int = 500) -> list[dict]:
        """Return unsynced outbox rows FIFO (oldest first).

        Rows where ``synced_at IS NULL``, ordered by ``id ASC`` so the
        push lane replays local writes in the order they happened.
        """
        rows = self.db.conn.execute(
            "SELECT id, entity_type, op, local_id, payload_json, retry_count "
            "FROM sync_outbox WHERE synced_at IS NULL "
            "ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def entity_type_to_table(self, entity_type: str) -> Optional[str]:
        """Map a SINGULAR entity type (e.g. ``'trip'``) to its table name.

        Uses the canonical ``SYNCABLE_ENTITIES`` mapping (table → entity
        type) in reverse.  Returns ``None`` for unknown entity types — the
        SQL-injection guard for ``resolve_payload``: the table name always
        comes from this mapping, never from caller input.
        """
        return _ENTITY_TYPE_TO_TABLE.get(entity_type)

    def resolve_payload(self, entity_type: str, local_id: int) -> Optional[dict]:
        """Re-read the current local row for INSERT/UPDATE ops.

        Returns a column→value dict (``sqlite3.Row`` → dict), or ``None``
        if the row no longer exists (e.g. deleted before push).  For
        DELETE ops the payload is already captured in ``payload_json`` at
        delete time, so this returns ``None`` (the row is gone).

        ``entity_type`` is the SINGULAR entity type (e.g. ``'trip'``, as
        stored in ``sync_outbox.entity_type`` by the capture triggers).  It
        is validated against ``SYNCABLE_ENTITIES`` (reverse lookup) to
        prevent SQL injection via the table name.
        """
        table = self.entity_type_to_table(entity_type)
        if table is None:
            logger.warning("resolve_payload: unknown entity_type %r", entity_type)
            return None
        try:
            row = self.db.conn.execute(
                f"SELECT * FROM {table} WHERE id = ?", (local_id,)
            ).fetchone()
        except Exception as e:
            logger.warning("resolve_payload failed for %s/%s: %s", entity_type, local_id, e)
            return None
        return dict(row) if row is not None else None

    def mark_synced(self, outbox_id: int, server_id: Optional[str] = None) -> None:
        """Mark an outbox row as confirmed by the server.

        ``server_id`` is accepted for forward compatibility with the push
        lane; the current schema has no column to persist it, so only
        ``synced_at`` is stamped (canonical UTC via ``utc_now_iso``).
        """
        self.db.conn.execute(
            "UPDATE sync_outbox SET synced_at = ? WHERE id = ?",
            (utc_now_iso(), outbox_id),
        )
        self.db.conn.commit()

    def mark_retry(self, outbox_id: int) -> None:
        """Increment the retry counter for a failed push."""
        self.db.conn.execute(
            "UPDATE sync_outbox SET retry_count = retry_count + 1 WHERE id = ?",
            (outbox_id,),
        )
        self.db.conn.commit()

    def mark_synced_for(self, entity_type: str, local_id: int) -> None:
        """Mark all pending outbox rows for (entity_type, local_id) as synced.

        Used by conflict resolution ("Take server") — after the server row is
        applied locally there is nothing left to push for that row, so the
        pending INSERT/UPDATE/DELETE ops are dropped instead of re-pushed.
        """
        self.db.conn.execute(
            "UPDATE sync_outbox SET synced_at = ? "
            "WHERE entity_type = ? AND local_id = ? AND synced_at IS NULL",
            (utc_now_iso(), entity_type, local_id),
        )
        self.db.conn.commit()

    def bump_delete_payload_updated_at(self, entity_type: str, local_id: int) -> bool:
        """Bump the frozen DELETE payload's ``updated_at`` to now (keep-local, R3).

        For a HARD-deleted row the DELETE payload is frozen at delete time
        (the outbox DELETE trigger serializes ``OLD.*`` into ``payload_json``)
        and the push lane never re-reads the row, so the row can no longer be
        re-stamped in place.  Bumping the frozen payload's ``updated_at``
        gives the re-push a fresh ``base_updated_at`` so the DELETE wins on
        the next sync instead of conflicting forever.

        Returns True if a pending DELETE op was bumped, False otherwise.
        """
        for row in self.pending(limit=500):
            if row["entity_type"] != entity_type or row["local_id"] != local_id:
                continue
            if row["op"] != "DELETE":
                continue
            try:
                payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
            except (TypeError, ValueError):
                logger.warning(
                    "bump_delete_payload_updated_at: invalid payload_json for outbox %s",
                    row["id"],
                )
                continue
            payload["updated_at"] = utc_now_iso()
            self.db.conn.execute(
                "UPDATE sync_outbox SET payload_json = ? WHERE id = ?",
                (json.dumps(payload), row["id"]),
            )
            self.db.conn.commit()
            return True
        return False

    def set_sync_in_progress(self, flag: bool) -> None:
        """Set/clear the echo-suppression flag in ``sync_meta``.

        MUST be set to ``True`` by the sync engine around pull-apply
        (Phase 4) so the outbox capture triggers skip rows written by the
        apply path.
        """
        self.db.conn.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value) VALUES (?, ?)",
            (_SYNC_IN_PROGRESS_KEY, "1" if flag else "0"),
        )
        self.db.conn.commit()

    def get_meta(self, key: str) -> Optional[str]:
        """Return a ``sync_meta`` value, or None when unset."""
        row = self.db.conn.execute(
            "SELECT value FROM sync_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        """Set a ``sync_meta`` value (Phase C: binary-upload tracking)."""
        self.db.conn.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.db.conn.commit()

    def prune(self, days: int = 30) -> int:
        """Delete synced outbox rows older than *days* days.

        Returns the number of rows deleted.  The cutoff uses the canonical
        UTC format (``strftime('%Y-%m-%dT%H:%M:%SZ', ...)``) so the string
        comparison against ``synced_at`` is exact.
        """
        cur = self.db.conn.execute(
            "DELETE FROM sync_outbox WHERE synced_at IS NOT NULL "
            "AND synced_at < strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?)",
            (f"-{days} days",),
        )
        self.db.conn.commit()
        return cur.rowcount