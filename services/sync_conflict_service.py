"""Sync conflict journal service (Phase 4a).

Records push items the server rejected with status ``'conflict'`` (the
server row changed after the client's ``base_updated_at``) so the UI
(Phase 4b) can surface them and let the user resolve each one
(keep-local / take-server).  The journal is desktop-side bookkeeping — it
is NOT a syncable entity.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from database.time_utils import utc_now_iso

logger = logging.getLogger(__name__)


class SyncConflictService:
    """Read/write API over the ``sync_conflicts`` journal table."""

    def __init__(self, db) -> None:
        self.db = db

    def record(
        self,
        entity_type: str,
        local_id: int,
        server_id: Optional[int] = None,
        local_payload: Optional[dict] = None,
        server_payload: Optional[dict] = None,
    ) -> int:
        """Journal a conflict for a push item the server rejected.

        ``local_payload`` (what the client tried to push) and
        ``server_payload`` (the server's current row) are dicts; they are
        JSON-serialized for storage.  Returns the conflict row id.

        Dedup (R3): the engine re-pushes a conflicted outbox row every cycle,
        so the same (entity_type, local_id) would otherwise accumulate one
        unresolved journal row per cycle.  If an unresolved row already
        exists for that row, the existing id is returned and nothing is
        inserted.
        """
        existing = self.db.conn.execute(
            "SELECT id FROM sync_conflicts "
            "WHERE entity_type = ? AND local_id = ? AND resolved = 0 "
            "ORDER BY id LIMIT 1",
            (entity_type, local_id),
        ).fetchone()
        if existing is not None:
            return existing["id"]
        cur = self.db.conn.execute(
            "INSERT INTO sync_conflicts "
            "(entity_type, local_id, server_id, local_payload, server_payload, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                entity_type,
                local_id,
                server_id,
                json.dumps(local_payload) if local_payload is not None else None,
                json.dumps(server_payload) if server_payload is not None else None,
                utc_now_iso(),
            ),
        )
        self.db.conn.commit()
        return cur.lastrowid

    def list_unresolved(self) -> list[dict]:
        """Return all unresolved conflicts (oldest first)."""
        rows = self.db.conn.execute(
            "SELECT * FROM sync_conflicts WHERE resolved = 0 ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_resolved(self, conflict_id: int) -> None:
        """Mark a conflict as resolved (user chose keep-local / take-server)."""
        self.db.conn.execute(
            "UPDATE sync_conflicts SET resolved = 1 WHERE id = ?", (conflict_id,)
        )
        self.db.conn.commit()

    def restamp_local_updated_at(self, entity_type: str, local_id: int) -> bool:
        """Re-stamp the local row's ``updated_at`` to now (keep-local, R3).

        A bare ``UPDATE <table> SET updated_at = <now>`` is intentionally NOT
        captured by the outbox triggers (they fire on ``AFTER UPDATE OF`` the
        business columns, excluding ``updated_at``), so the existing pending
        outbox row re-pushes with a fresh ``base_updated_at`` on the next
        sync and wins — otherwise the server rejects the unchanged row again
        and the conflict loops forever.

        Returns True if a row was restamped, False if the entity type is
        unknown or the local row no longer exists.
        """
        from services.sync_outbox_service import SyncOutboxService

        table = SyncOutboxService(self.db).entity_type_to_table(entity_type)
        if table is None:
            logger.warning("restamp_local_updated_at: unknown entity_type %r", entity_type)
            return False
        cur = self.db.conn.execute(
            f"UPDATE {table} SET updated_at = ? WHERE id = ?",
            (utc_now_iso(), local_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0