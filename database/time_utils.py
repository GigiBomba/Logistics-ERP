"""Canonical UTC timestamp helpers for the offline-first sync layer.

The sync layer (outbox ordering, last-write-wins conflict resolution,
delta pull) depends on reliable ``updated_at`` timestamps.  This module
is the single source of truth for the canonical format:

    ``YYYY-MM-DDTHH:MM:SSZ``  (UTC, seconds precision, ``Z`` suffix)

SQLite triggers use the equivalent SQL expression
``strftime('%Y-%m-%dT%H:%M:%SZ','now')``; PostgreSQL triggers stamp a native
``TIMESTAMPTZ`` at seconds precision via
``date_trunc('second', clock_timestamp())`` (session-TZ-independent; read
back as ``updated_at AT TIME ZONE 'UTC'`` to get the canonical ``...Z``
string).
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return the canonical UTC timestamp: ``YYYY-MM-DDTHH:MM:SSZ``.

    Seconds precision, UTC, ``Z`` suffix — the exact format the sync
    layer expects for ``updated_at`` / ``created_at`` values.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")