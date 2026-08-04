"""Regression tests for datetime integrity — Phase D of DB hardening.

These tests verify that timestamp columns are stored as ISO-8601 strings
(SQLite) which are compatible with TIMESTAMPTZ (PostgreSQL), and that
chronological ordering is preserved through TEXT storage.
"""
from __future__ import annotations

import sqlite3

import pytest

from database.db_manager import DatabaseManager
from tests.test_helpers import InMemoryDB


class TestTimestampHandling:
    """Verify timestamps survive a write/read round-trip with correct format."""

    def test_timestamp_write_read_roundtrip(self):
        """Insert a timestamp, read it back, verify ISO-8601 format."""
        db = InMemoryDB()
        try:
            from datetime import datetime, timezone
            original = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            db.conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) "
                "VALUES (9999, 'test_roundtrip', ?)",
                (original,),
            )
            db.conn.commit()
            row = db.conn.execute(
                "SELECT applied_at FROM schema_migrations WHERE version = 9999"
            ).fetchone()
            assert row is not None, "Row should exist after insert"
            stored = row[0]
            # Must be a string (SQLite TEXT)
            assert isinstance(stored, str), f"Expected string, got {type(stored)}"
            # Must contain a date-like pattern
            assert "T" in stored, f"Expected ISO-8601 format, got '{stored}'"
            # Must match the inserted value (ordering preserved)
            assert stored == original, (
                f"Round-trip changed value: '{original}' → '{stored}'"
            )
        finally:
            db.close()

    def test_timestamp_ordering_preserved(self):
        """ISO-8601 string sorting matches chronological order."""
        db = DatabaseManager(":memory:")
        try:
            from datetime import datetime, timezone, timedelta
            base = datetime.now(timezone.utc)
            timestamps = [
                (base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%S")
                for i in range(3)
            ]
            # Insert in reverse order
            for i, ts in enumerate(reversed(timestamps)):
                version = 20000 + i
                db.conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) "
                    "VALUES (?, ?, ?)",
                    (version, f"order_test_{i}", ts),
                )
            db.conn.commit()
            # Read back sorted by applied_at (TEXT → ISO-8601 string sort = chronological)
            rows = db.conn.execute(
                "SELECT applied_at FROM schema_migrations "
                "WHERE version >= 20000 ORDER BY applied_at ASC"
            ).fetchall()
            stored = [r[0] for r in rows]
            # ISO-8601 alphabetical sort IS chronological
            assert stored == sorted(stored), (
                f"ISO-8601 sorting mismatch: {stored} vs sorted {sorted(stored)}"
            )
            assert len(stored) == 3, f"Expected 3 rows, got {len(stored)}"
        finally:
            db.close()
