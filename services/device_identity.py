"""Per-install device identity for the offline-first sync layer (Phase A).

Each desktop install gets a stable UUID that identifies it to the sync
server.  The id is generated on first use and persisted in ``sync_meta``
(key ``device_id``), so it is stable across restarts and across engine
instances sharing the same database.

NOTE: the identity is per DATABASE FILE, not per install — a copied or
restored DB on a second desktop silently shares the same ``device_id``.
That is acceptable for v1 (a restored backup is the same logical device);
a per-install identity would require storing the id outside the DB.

Multi-device support: the server's ``sync_server_map`` is keyed per device
(``(company_id, device_id, entity_type, local_id)``), so two desktops with
colliding local ids map to distinct server rows instead of overwriting each
other.
"""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)

_DEVICE_ID_KEY = "device_id"


class DeviceIdentity:
    """Resolves and caches the per-install device id.

    ``device_id`` may be injected (tests / explicit override); otherwise it
    is read from ``sync_meta`` or generated + persisted on first use.
    """

    def __init__(self, db, device_id: str | None = None) -> None:
        self._db = db
        self._device_id: str = device_id if device_id is not None else ""
        self._resolved = device_id is not None

    def get(self) -> str:
        """Return the stable device id, generating + persisting it if needed."""
        if self._resolved:
            return self._device_id
        row = self._db.conn.execute(
            "SELECT value FROM sync_meta WHERE key = ?", (_DEVICE_ID_KEY,)
        ).fetchone()
        if row is not None:
            value = row["value"]
            if value:
                self._device_id = str(value)
                self._resolved = True
                return self._device_id
        # Race-hardened first generation: INSERT OR IGNORE so a concurrent
        # instance's write wins (INSERT OR REPLACE would let two racing
        # instances each keep a different UUID and clobber each other).  Then
        # re-read the persisted value — if another instance won, adopt it.
        self._device_id = str(uuid.uuid4())
        self._db.conn.execute(
            "INSERT OR IGNORE INTO sync_meta (key, value) VALUES (?, ?)",
            (_DEVICE_ID_KEY, self._device_id),
        )
        self._db.conn.commit()
        row = self._db.conn.execute(
            "SELECT value FROM sync_meta WHERE key = ?", (_DEVICE_ID_KEY,)
        ).fetchone()
        if row is not None and row["value"]:
            self._device_id = str(row["value"])
        self._resolved = True
        return self._device_id
