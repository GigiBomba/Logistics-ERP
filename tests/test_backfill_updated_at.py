"""Tests for the NULL ``updated_at`` backfill (scripts/backfill_updated_at.py).

Covers the Phase E oracle re-check: the PG branch previously used
``db.conn.execute`` (a raw psycopg2 connection — no such method), referenced a
``sync_meta`` table that does not exist in schema_pg.sql, and unconditionally
COALESCED against ``created_at`` even when the table lacks that column
(``client_tags``), which made every table iteration fail and exit 0 rows.

Verified here:
* SQLite: NULL rows stamped with ``created_at``; the stamping trigger does NOT
  overwrite the COALESCE value; the trigger is active again afterwards.
* SQLite: ``client_tags`` (no ``created_at`` column) falls back to the epoch.
* PostgreSQL (live DB, skipped when unavailable): same, using the REAL
  ``DatabaseManager.execute`` path (cursor creation + placeholder adaptation)
  and ``ALTER TABLE ... DISABLE/ENABLE TRIGGER ALL`` suppression.
"""
from __future__ import annotations

import os

import pytest

from scripts.backfill_updated_at import EPOCH, backfill

TEST_DSN = os.environ.get(
    "OPERION_TEST_POSTGRES_DSN",
    "postgresql://operion:operion_test_ci@localhost:5432/operion_test",
)


# ── SQLite (unit) ──────────────────────────────────────────────────────────


@pytest.fixture
def sqldb(tmp_path):
    from database.db_manager import DatabaseManager

    db = DatabaseManager(str(tmp_path / "app.db"))
    yield db
    db.close()


def _seed_null_updated_at(db, table, columns, values):
    """Insert a row with NULL updated_at by suppressing the stamping trigger."""
    db.execute(
        "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('sync_in_progress', '1')"
    )
    try:
        db.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({', '.join(['?'] * len(values))})",
            values,
        )
    finally:
        db.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('sync_in_progress', '0')"
        )
    db.conn.commit()


def test_sqlite_stamps_null_rows_with_created_at(sqldb):
    """A NULL updated_at trip gets its created_at stamp, not now()."""
    _seed_null_updated_at(
        sqldb, "trips",
        "truck_number, driver_name, client_name, distance_km, created_at, updated_at, company_id",
        ("BF-1", "D", "C", 100.0, "2026-07-15T08:00:00Z", None, 0),
    )
    stamped = backfill(sqldb, engine="sqlite")
    assert stamped >= 1

    row = sqldb.conn.execute(
        "SELECT updated_at FROM trips WHERE truck_number = 'BF-1'"
    ).fetchone()
    assert row["updated_at"] == "2026-07-15T08:00:00Z"
    assert row["updated_at"] != EPOCH


def test_sqlite_client_tags_epoch_fallback(sqldb):
    """client_tags has no created_at column — must fall back to the epoch
    instead of failing with 'no such column' and being skipped."""
    sqldb.execute(
        "INSERT INTO clients (name, created_at, updated_at, company_id) "
        "VALUES ('C', '2026-07-15T08:00:00Z', '2026-07-15T08:00:00Z', 0)"
    )
    _seed_null_updated_at(
        sqldb, "client_tags", "client_id, tag, updated_at", (1, "urgent", None)
    )
    stamped = backfill(sqldb, engine="sqlite")
    assert stamped >= 1

    row = sqldb.conn.execute(
        "SELECT updated_at FROM client_tags WHERE tag = 'urgent'"
    ).fetchone()
    assert row["updated_at"] == EPOCH


def test_sqlite_trigger_restored_after_backfill(sqldb):
    """The stamping trigger must be active again once the backfill finishes."""
    _seed_null_updated_at(
        sqldb, "trips",
        "truck_number, created_at, updated_at, company_id",
        ("BF-2", "2026-07-15T08:00:00Z", None, 0),
    )
    backfill(sqldb, engine="sqlite")

    sqldb.execute(
        "UPDATE trips SET truck_number = 'BF-2b' WHERE truck_number = 'BF-2'"
    )
    row = sqldb.conn.execute(
        "SELECT updated_at FROM trips WHERE truck_number = 'BF-2b'"
    ).fetchone()
    assert row["updated_at"] is not None
    assert row["updated_at"] != "2026-07-15T08:00:00Z"  # trigger stamped now()


def test_sqlite_idempotent(sqldb):
    """A second run has nothing left to stamp."""
    _seed_null_updated_at(
        sqldb, "trips",
        "truck_number, created_at, updated_at, company_id",
        ("BF-3", "2026-07-15T08:00:00Z", None, 0),
    )
    assert backfill(sqldb, engine="sqlite") >= 1
    assert backfill(sqldb, engine="sqlite") == 0


# ── PostgreSQL integration (skip when unavailable) ─────────────────────────


@pytest.fixture(scope="module")
def pg_schema():
    """Build the real PG schema (idempotent) so trips/clients/client_tags exist.

    ``operion_test`` may be freshly created (or schema-less); the deployment
    path — ``DatabaseManager(dsn, engine="postgresql")`` — runs schema_pg.sql
    + Alembic + ``_apply_pg_extra_ddl`` and is safe to run repeatedly.  Each
    statement runs in its own autocommit transaction, so a single failure
    cannot abort the rest of the build.
    """
    from database.db_manager import DatabaseManager

    try:
        db = DatabaseManager(TEST_DSN, engine="postgresql")
    except Exception as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    db.close()


@pytest.fixture
def pg_conn(pg_schema):
    import psycopg2
    from psycopg2.extras import RealDictCursor

    try:
        conn = psycopg2.connect(TEST_DSN, cursor_factory=RealDictCursor, connect_timeout=5)
        conn.autocommit = False
    except Exception as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield conn
    try:
        conn.rollback()
    except Exception:
        pass
    try:
        conn.close()
    except Exception:
        pass


def _make_pg_db(pg_conn):
    """Bind the REAL DatabaseManager.execute/conn code path to a live conn.

    Mirrors the stub pattern in test_sync_pg_migration.py; adds the pool
    bookkeeping methods (``record_query``/``record_error``) that
    ``DatabaseManager.execute`` calls so the real method is exercised.
    """
    from database.db_manager import DatabaseManager

    class _ConnHolder:
        def __init__(self, conn):
            self._conn = conn

        def get_cached_connection(self):
            return self._conn

        def record_query(self):
            pass

        def record_error(self):
            pass

    db = DatabaseManager.__new__(DatabaseManager)
    db._engine = "postgresql"
    db._pg_pool = _ConnHolder(pg_conn)
    return db


def _pg_insert_null_updated_at(pg_conn, sql, params):
    """Insert a row with NULL updated_at (INSERT stamping trigger suppressed)."""
    cur = pg_conn.cursor()
    cur.execute("ALTER TABLE trips DISABLE TRIGGER ALL")
    try:
        cur.execute(sql, params)
    finally:
        cur.execute("ALTER TABLE trips ENABLE TRIGGER ALL")
    pg_conn.commit()


def _pg_canonical_ts(pg_conn, sql, params=()):
    """Run a scalar query whose SELECT list is `... AS ts`, return the value."""
    cur = pg_conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    return row["ts"] if row else None


def test_pg_backfill_stamps_created_at_and_reenables_triggers(pg_conn):
    """PG: a NULL updated_at trip gets its created_at stamp (NOT now()), and
    the stamping trigger fires again for later updates."""
    _pg_insert_null_updated_at(
        pg_conn,
        "INSERT INTO trips (truck_number, created_at, updated_at) "
        "VALUES ('PG-BF-1', '2026-07-15T08:00:00Z', NULL)",
        (),
    )
    row_id = _pg_canonical_ts(
        pg_conn, "SELECT id AS ts FROM trips WHERE truck_number = 'PG-BF-1'"
    )
    assert row_id is not None

    stamped = backfill(_make_pg_db(pg_conn), engine="postgresql")
    assert stamped >= 1

    stamped_ts = _pg_canonical_ts(
        pg_conn,
        "SELECT to_char(updated_at AT TIME ZONE 'UTC', "
        "'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') AS ts FROM trips WHERE id = %s",
        (row_id,),
    )
    assert stamped_ts == "2026-07-15T08:00:00Z", f"trigger overwrote COALESCE: {stamped_ts}"

    # Trigger must be re-enabled: a later UPDATE stamps now(), not created_at.
    cur = pg_conn.cursor()
    cur.execute(
        "UPDATE trips SET truck_number = 'PG-BF-1x' WHERE id = %s", (row_id,)
    )
    pg_conn.commit()
    after_ts = _pg_canonical_ts(
        pg_conn,
        "SELECT to_char(updated_at AT TIME ZONE 'UTC', "
        "'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') AS ts FROM trips WHERE id = %s",
        (row_id,),
    )
    assert after_ts != "2026-07-15T08:00:00Z", "stamping trigger not re-enabled"

    cur = pg_conn.cursor()
    cur.execute("DELETE FROM trips WHERE id = %s", (row_id,))
    pg_conn.commit()


def test_pg_backfill_client_tags_epoch_fallback(pg_conn):
    """PG: client_tags has no created_at column — epoch fallback, not a
    'no such column' skip."""
    cur = pg_conn.cursor()
    cur.execute(
        "INSERT INTO clients (name, created_at) "
        "VALUES ('PG-BF-CLIENT', '2026-07-15T08:00:00Z') RETURNING id"
    )
    client_id = cur.fetchone()["id"]
    cur.execute("ALTER TABLE client_tags DISABLE TRIGGER ALL")
    try:
        cur.execute(
            "INSERT INTO client_tags (client_id, tag, updated_at) VALUES (%s, 'x', NULL)",
            (client_id,),
        )
    finally:
        cur.execute("ALTER TABLE client_tags ENABLE TRIGGER ALL")
    pg_conn.commit()

    stamped = backfill(_make_pg_db(pg_conn), engine="postgresql")
    assert stamped >= 1

    ts = _pg_canonical_ts(
        pg_conn,
        "SELECT to_char(updated_at AT TIME ZONE 'UTC', "
        "'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') AS ts FROM client_tags WHERE client_id = %s",
        (client_id,),
    )
    assert ts == EPOCH, f"client_tags not stamped with epoch: {ts}"

    cur = pg_conn.cursor()
    cur.execute("DELETE FROM client_tags WHERE client_id = %s", (client_id,))
    cur.execute("DELETE FROM clients WHERE id = %s", (client_id,))
    pg_conn.commit()
