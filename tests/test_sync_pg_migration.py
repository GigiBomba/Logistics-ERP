"""Tests for the Phase A sync_server_map PostgreSQL migration.

Covers the defect where the standalone-index loop of
``_migrate_sync_server_map_device_id_pg`` selected EVERY unique index whose
key lacks ``device_id`` — including the PRIMARY KEY backing index
(``sync_server_map_pkey``), whose DROP raises "cannot drop index because
constraint requires it" and aborts the whole DO block.

Two layers:
1. Unit tests (no live PostgreSQL) — assert the generated DO-block SQL
   excludes the PK / constraint-backed indexes and wraps each EXECUTE so one
   bad drop cannot roll back the rest.
2. PG integration tests (skip when PostgreSQL is unavailable) — build a
   legacy ``sync_server_map`` in BOTH legacy forms (inline UNIQUE constraint
   and standalone ``CREATE UNIQUE INDEX``), run the real migration method,
   and assert the old key is gone, the new 4-column key exists,
   ``sync_server_map_pkey`` is NOT dropped, and a second device's INSERT for
   a colliding local_id succeeds.
"""
from __future__ import annotations

import os

import pytest

from database.db_manager import (
    _PG_SYNC_SERVER_MAP_ADD_NEW,
    _PG_SYNC_SERVER_MAP_DROP_OLD,
    _split_pg_statements,
)

TEST_DSN = os.environ.get(
    "OPERION_TEST_POSTGRES_DSN",
    "postgresql://operion:operion_test_ci@localhost:5432/operion_test",
)

LEGACY_INLINE_UNIQUE = """
CREATE TABLE sync_server_map (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    local_id INTEGER NOT NULL,
    server_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (company_id, entity_type, local_id)
)
"""

LEGACY_STANDALONE_INDEX = """
CREATE TABLE sync_server_map (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    company_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    local_id INTEGER NOT NULL,
    server_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (id)
)
"""


# ── Unit tests (no live PostgreSQL) ───────────────────────────────────────


class TestDropOldSql:
    def test_excludes_primary_key_index(self):
        """The standalone-index loop must not select the PK backing index."""
        assert "ix.indisprimary = FALSE" in _PG_SYNC_SERVER_MAP_DROP_OLD

    def test_excludes_constraint_backed_indexes(self):
        """Constraint-backed indexes (e.g. a UNIQUE constraint's index) are
        dropped via DROP CONSTRAINT, never via DROP INDEX."""
        assert "c.conindid = ix.indexrelid" in _PG_SYNC_SERVER_MAP_DROP_OLD

    def test_drop_executes_are_exception_wrapped(self):
        """Each EXECUTE must be wrapped so one bad drop can't roll back the rest."""
        assert _PG_SYNC_SERVER_MAP_DROP_OLD.count(
            "EXCEPTION WHEN OTHERS THEN NULL"
        ) >= 2  # one per LOOP

    def test_parses_as_single_plpgsql_statement(self):
        """_split_pg_statements must not split inside the $$ block."""
        stmts = _split_pg_statements(_PG_SYNC_SERVER_MAP_DROP_OLD)
        assert len(stmts) == 1
        assert "DO $$" in stmts[0]
        stmts_new = _split_pg_statements(_PG_SYNC_SERVER_MAP_ADD_NEW)
        assert len(stmts_new) == 1
        assert "DO $$" in stmts_new[0]

    def test_add_new_key_constraint_present(self):
        assert "UNIQUE (company_id, device_id, entity_type, local_id)" in (
            _PG_SYNC_SERVER_MAP_ADD_NEW
        )


# ── PG integration tests (skip when PostgreSQL is unavailable) ────────────


def _connect():
    import psycopg2
    from psycopg2.extras import RealDictCursor

    return psycopg2.connect(TEST_DSN, cursor_factory=RealDictCursor, connect_timeout=5)


@pytest.fixture
def pg_conn():
    try:
        conn = _connect()
        conn.autocommit = True
    except Exception as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield conn
    try:
        conn.close()
    except Exception:
        pass


def _reset_legacy(pg_conn, ddl, extra_index_sql=None):
    """Drop sync_server_map and recreate it in a legacy (pre-Phase-A) form."""
    cur = pg_conn.cursor()
    cur.execute("DROP TABLE IF EXISTS sync_server_map CASCADE")
    cur.execute(ddl)
    if extra_index_sql:
        cur.execute(extra_index_sql)
    cur.execute(
        "INSERT INTO sync_server_map (company_id, entity_type, local_id, server_id, created_at) "
        "VALUES (1, 'client', 1, 100, '2026-08-01T00:00:00Z')"
    )


def _run_real_migration(pg_conn):
    """Run the REAL migration method against the live connection.

    The method lives on ``DatabaseManager`` and touches ``self.conn``; bind a
    minimal stub that hands the method the live psycopg2 connection.
    """
    from database.db_manager import DatabaseManager

    class _ConnHolder:
        def __init__(self, conn):
            self._conn = conn

        def get_cached_connection(self):
            return self._conn

    db = DatabaseManager.__new__(DatabaseManager)
    db._engine = "postgresql"
    db._pg_pool = _ConnHolder(pg_conn)
    db._migrate_sync_server_map_device_id_pg()


def _assert_migrated(pg_conn):
    cur = pg_conn.cursor()

    # Old 3-column unique key must be gone (both forms).
    cur.execute(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'sync_server_map'::regclass AND contype = 'u'"
    )
    unique_constraints = [r["conname"] for r in cur.fetchall()]
    assert "sync_server_map_company_id_entity_type_local_id_key" not in unique_constraints

    # New 4-column key exists.
    assert (
        "sync_server_map_company_id_device_id_entity_type_local_id_key"
        in unique_constraints
    )

    # PRIMARY KEY backing index must NOT have been dropped.
    cur.execute(
        "SELECT i.relname FROM pg_index ix "
        "JOIN pg_class i ON i.oid = ix.indexrelid "
        "JOIN pg_class t ON t.oid = ix.indrelid "
        "WHERE t.relname = 'sync_server_map' AND ix.indisprimary"
    )
    pk_indexes = [r["relname"] for r in cur.fetchall()]
    assert "sync_server_map_pkey" in pk_indexes

    # A second device's INSERT for the same local_id must succeed — with the
    # old 3-column key this would violate UNIQUE(company_id, entity_type,
    # local_id) and raise.
    cur.execute(
        "INSERT INTO sync_server_map "
        "(company_id, device_id, entity_type, local_id, server_id, created_at) "
        "VALUES (1, 'device-B', 'client', 1, 200, '2026-08-01T00:00:00Z')"
    )
    cur.execute("SELECT COUNT(*) AS n FROM sync_server_map")
    assert cur.fetchone()["n"] == 2

    # Clean up the second-device row so the next test starts from one row.
    cur.execute("DELETE FROM sync_server_map WHERE device_id = 'device-B'")


def test_migration_legacy_inline_unique_constraint(pg_conn):
    """Legacy form (a): old unique key as an inline UNIQUE constraint."""
    _reset_legacy(pg_conn, LEGACY_INLINE_UNIQUE)
    _run_real_migration(pg_conn)
    _assert_migrated(pg_conn)


def test_migration_legacy_standalone_unique_index(pg_conn):
    """Legacy form (b): old unique key as a standalone CREATE UNIQUE INDEX."""
    _reset_legacy(
        pg_conn,
        LEGACY_STANDALONE_INDEX,
        extra_index_sql=(
            "CREATE UNIQUE INDEX sync_server_map_old_key_idx "
            "ON sync_server_map (company_id, entity_type, local_id)"
        ),
    )
    _run_real_migration(pg_conn)

    # The standalone old-key index must have been dropped.
    cur = pg_conn.cursor()
    cur.execute(
        "SELECT 1 FROM pg_class WHERE relname = 'sync_server_map_old_key_idx'"
    )
    assert cur.fetchone() is None
    _assert_migrated(pg_conn)


def test_migration_fresh_table_is_noop(pg_conn):
    """A fresh (already migrated) table is left untouched (idempotent)."""
    _reset_legacy(pg_conn, LEGACY_INLINE_UNIQUE)
    _run_real_migration(pg_conn)  # first pass migrates it
    _run_real_migration(pg_conn)  # second pass must be a no-op

    cur = pg_conn.cursor()
    cur.execute(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'sync_server_map'::regclass AND contype = 'u'"
    )
    unique_constraints = [r["conname"] for r in cur.fetchall()]
    assert (
        "sync_server_map_company_id_device_id_entity_type_local_id_key"
        in unique_constraints
    )
    # A second device's INSERT still succeeds after the re-run.
    cur.execute(
        "INSERT INTO sync_server_map "
        "(company_id, device_id, entity_type, local_id, server_id, created_at) "
        "VALUES (1, 'device-C', 'client', 1, 300, '2026-08-01T00:00:00Z')"
    )
    cur.execute("SELECT COUNT(*) AS n FROM sync_server_map")
    assert cur.fetchone()["n"] == 2
    cur.execute("DELETE FROM sync_server_map WHERE device_id = 'device-C'")


# ── B1/B2: company_id on the 5 newly scoped tables (PG) ───────────────────


_LEGACY_NO_COMPANY_TABLES = {
    "driver_truck_assignments": """
        CREATE TABLE driver_truck_assignments (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            driver_id INTEGER NOT NULL UNIQUE,
            truck_id INTEGER NOT NULL,
            assigned_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            updated_at TIMESTAMPTZ
        )
    """,
    "email_logs": """
        CREATE TABLE email_logs (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            trip_id INTEGER,
            recipient TEXT, subject TEXT, timestamp TEXT,
            status TEXT, error_msg TEXT, updated_at TIMESTAMPTZ
        )
    """,
    "invoice_reminders": """
        CREATE TABLE invoice_reminders (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            invoice_id INTEGER NOT NULL, trip_id INTEGER NOT NULL,
            reminder_type TEXT NOT NULL, days_offset INTEGER NOT NULL,
            sent_at TEXT NOT NULL, recipient_email TEXT NOT NULL,
            status TEXT DEFAULT 'sent', updated_at TIMESTAMPTZ
        )
    """,
    "tacho_driver_activity": """
        CREATE TABLE tacho_driver_activity (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            import_id INTEGER NOT NULL, driver_id INTEGER,
            activity_date DATE NOT NULL,
            driving_minutes INTEGER DEFAULT 0, work_minutes INTEGER DEFAULT 0,
            rest_minutes INTEGER DEFAULT 0, avail_minutes INTEGER DEFAULT 0,
            distance_km DOUBLE PRECISION DEFAULT 0,
            violations TEXT, country_codes TEXT, updated_at TIMESTAMPTZ
        )
    """,
    "tacho_vehicle_data": """
        CREATE TABLE tacho_vehicle_data (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            import_id INTEGER NOT NULL, truck_id INTEGER,
            vu_serial_number TEXT, calibration_date DATE, calibration_expiry DATE,
            odometer_km DOUBLE PRECISION, k_factor INTEGER, w_factor INTEGER,
            speed_violations INTEGER DEFAULT 0,
            recorded_from DATE, recorded_to DATE, updated_at TIMESTAMPTZ
        )
    """,
}


def _run_pg_extra_ddl(pg_conn):
    """Run the real ``_apply_pg_extra_ddl`` (B1/B2 company_id migration)."""
    from database.db_manager import DatabaseManager

    class _ConnHolder:
        def __init__(self, conn):
            self._conn = conn

        def get_cached_connection(self):
            return self._conn

    db = DatabaseManager.__new__(DatabaseManager)
    db._engine = "postgresql"
    db._pg_pool = _ConnHolder(pg_conn)
    db._apply_pg_extra_ddl()


def test_pg_company_id_migration_newly_scoped_tables(pg_conn):
    """B1+B2: pre-existing tables (no company_id) get it via _apply_pg_extra_ddl."""
    cur = pg_conn.cursor()
    # Drop in dependency-safe order (child-first is not needed — no FKs kept).
    for t in list(_LEGACY_NO_COMPANY_TABLES.keys()):
        cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    for ddl in _LEGACY_NO_COMPANY_TABLES.values():
        cur.execute(ddl)
    pg_conn.commit()

    _run_pg_extra_ddl(pg_conn)

    for t in _LEGACY_NO_COMPANY_TABLES:
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = 'company_id'",
            (t,),
        )
        assert cur.fetchone() is not None, f"{t} missing company_id after migration"
    print(f"B1/B2: company_id added to {len(_LEGACY_NO_COMPANY_TABLES)} tables")

    # Idempotent: a second run is a no-op (no error, columns still present).
    _run_pg_extra_ddl(pg_conn)
    for t in _LEGACY_NO_COMPANY_TABLES:
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = 'company_id'",
            (t,),
        )
        assert cur.fetchone() is not None, f"{t} lost company_id on re-run"


def test_pg_driver_truck_assignment_push_succeeds_after_migration(pg_conn):
    """B1: after migration, a driver_truck_assignment INSERT with company_id works.

    The legacy table DDL has no FK constraints, so no parent rows are needed.
    """
    cur = pg_conn.cursor()
    for t in list(_LEGACY_NO_COMPANY_TABLES.keys()):
        cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    for ddl in _LEGACY_NO_COMPANY_TABLES.values():
        cur.execute(ddl)
    pg_conn.commit()
    _run_pg_extra_ddl(pg_conn)

    cur.execute(
        "INSERT INTO driver_truck_assignments "
        "(driver_id, truck_id, assigned_at, company_id) "
        "VALUES (1, 1, '2026-08-01T00:00:00Z', 1)"
    )
    pg_conn.commit()
    cur.execute("SELECT company_id FROM driver_truck_assignments")
    row = cur.fetchone()
    assert row is not None and row["company_id"] == 1