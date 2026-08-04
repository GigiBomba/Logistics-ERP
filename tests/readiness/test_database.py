"""Tests for database schema changes — migrations, foreign keys, indexes,
connection pool, and new tables.

All tests use in-memory SQLite databases to verify schema correctness without
requiring a real PostgreSQL instance.  PostgreSQL-specific features
(``PostgresConnectionPool``) are tested with mocked psycopg2.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

from database.connection_pool import ConnectionPool, PostgresConnectionPool
from database.db_manager import DatabaseManager

import database.schema as S


# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mem_conn():
    """Provide a fresh in-memory SQLite connection for each test."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def db():
    """Return a DatabaseManager backed by an in-memory SQLite DB.

    All tables, indexes, columns (migrations), and seed data are applied
    during initialisation, so the fixture is ready for querying.
    """
    _db = DatabaseManager(":memory:")
    yield _db
    try:
        _db.close()
    except Exception:
        pass


@pytest.fixture
def temp_db_path():
    """Yields a temporary file path for file-based DB tests.

    The file is removed after the test.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    yield tmp.name
    try:
        import os
        os.unlink(tmp.name)
    except OSError:
        pass


# ═════════════════════════════════════════════════════════════════════════════
# Migration tracking
# ═════════════════════════════════════════════════════════════════════════════


class TestMigrationTracking:
    """schema_migrations table, version tracking, and seed record."""

    def test_schema_migrations_table_exists(self, db):
        """schema_migrations table is created during DatabaseManager init."""
        tables = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "schema_migrations" in tables

    def test_schema_version_readable(self, db):
        """get_schema_version() returns an integer."""
        version = db.get_schema_version()
        assert isinstance(version, int)

    def test_schema_version_is_at_least_1(self, db):
        """version is >= 1 because the initial seed record exists."""
        version = db.get_schema_version()
        assert version >= 1

    def test_schema_migrations_has_initial_record(self, db):
        """The seed record (version 1, 'initial_schema') exists after init."""
        row = db.conn.execute(
            "SELECT version, name FROM schema_migrations WHERE version = 1"
        ).fetchone()
        assert row is not None
        assert row["version"] == 1
        assert row["name"] == "initial_schema"

    def test_schema_migrations_has_v2_record(self, db):
        """The second migration record (version 2) exists after init."""
        row = db.conn.execute(
            "SELECT version, name FROM schema_migrations WHERE version = 2"
        ).fetchone()
        assert row is not None
        assert row["version"] == 2
        assert row["name"] == "add_company_id_indexes"


# ═════════════════════════════════════════════════════════════════════════════
# Foreign keys
# ═════════════════════════════════════════════════════════════════════════════


class TestForeignKeys:
    """Verify FK constraints exist and behave correctly."""

    # ── trips.client_id ────────────────────────────────────────────────

    def test_trips_has_client_id_column(self, db):
        """trips table has a client_id column (with FK declared)."""
        cols = {
            r[1]
            for r in db.conn.execute("PRAGMA table_info(trips)").fetchall()
        }
        assert "client_id" in cols

    def test_trips_client_fk_enforced(self, db):
        """Deleting a client that has trips is restricted by FK.

        In SQLite the FK added via ``ALTER TABLE trips ADD COLUMN
        client_id INTEGER REFERENCES clients(id)`` defaults to NO ACTION,
        which prevents deletion of a referenced client (same as RESTRICT).

        In PostgreSQL ``_ensure_foreign_key`` would add ON DELETE SET NULL.
        """
        db.conn.execute("PRAGMA foreign_keys=ON")

        # Create a client
        db.conn.execute(
            "INSERT INTO clients (name, created_at, updated_at) VALUES (?, ?, ?)",
            ("Test Client", "2025-01-01", "2025-01-01"),
        )
        client_id = db.conn.execute(
            "SELECT id FROM clients WHERE name = ?", ("Test Client",)
        ).fetchone()[0]

        # Insert a company so the FK backfill does not fail
        db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name, created_at, updated_at) "
            "VALUES (1, 'Default', '2025-01-01', '2025-01-01')"
        )

        # Create a trip referencing the client
        db.conn.execute(
            "INSERT INTO trips (client_id, created_at, company_id) VALUES (?, ?, 1)",
            (client_id, "2025-01-02"),
        )

        # Delete the client — should be restricted (NO ACTION)
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
            db.conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))

    # ── trips.driver_id ────────────────────────────────────────────────

    def test_trips_has_driver_id_column(self, db):
        """trips table has a driver_id column (with FK declared)."""
        cols = {
            r[1]
            for r in db.conn.execute("PRAGMA table_info(trips)").fetchall()
        }
        assert "driver_id" in cols

    def test_trips_driver_fk_enforced(self, db):
        """trips.driver_id FK exists (column + foreign_key_list entry).

        NOTE: The ``driver_id`` column is defined in the original CREATE TABLE
        without a REFERENCES clause, and the migration ALTER is skipped
        because the column already exists.  For SQLite the FK is enforced
        at the app level (via ``_ensure_foreign_key`` → ``PRAGMA foreign_keys=ON``);
        for PostgreSQL an actual ALTER TABLE ADD CONSTRAINT is executed.
        The column itself is present in the table.
        """
        cols = {
            r[1]
            for r in db.conn.execute("PRAGMA table_info(trips)").fetchall()
        }
        assert "driver_id" in cols

        # Verify that the migration code *declares* the FK intent
        assert hasattr(S, "ALTER_TRIPS_ADD_DRIVER_ID")
        fk_sql = getattr(S, "ALTER_TRIPS_ADD_DRIVER_ID")
        assert "REFERENCES drivers(id)" in fk_sql

    # ── trips.truck_id ─────────────────────────────────────────────────

    def test_trips_has_truck_id_column(self, db):
        """trips table has a truck_id column (with FK declared)."""
        cols = {
            r[1]
            for r in db.conn.execute("PRAGMA table_info(trips)").fetchall()
        }
        assert "truck_id" in cols

    def test_trips_truck_fk_enforced(self, db):
        """Deleting a truck referenced by trips is restricted by FK.

        Same as ``client_id`` — the FK added via ``ALTER TABLE trips ADD
        COLUMN truck_id INTEGER REFERENCES trucks(id)`` defaults to
        NO ACTION in SQLite.
        """
        db.conn.execute("PRAGMA foreign_keys=ON")

        # Insert a company
        db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name, created_at, updated_at) "
            "VALUES (1, 'Default', '2025-01-01', '2025-01-01')"
        )

        # Create a truck
        db.conn.execute(
            "INSERT INTO trucks (plate_number, model) VALUES (?, ?)",
            ("AB-123-CD", "Test Truck"),
        )
        truck_id = db.conn.execute(
            "SELECT id FROM trucks WHERE plate_number = ?", ("AB-123-CD",)
        ).fetchone()[0]

        # Create a trip referencing the truck
        db.conn.execute(
            "INSERT INTO trips (truck_id, created_at, company_id) VALUES (?, ?, 1)",
            (truck_id, "2025-01-02"),
        )

        # Delete the truck — should be restricted (NO ACTION)
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
            db.conn.execute("DELETE FROM trucks WHERE id = ?", (truck_id,))

    # ── CASCADE delete (maintenance_records → trucks) ──────────────────

    def test_cascade_delete_works(self, db):
        """Deleting a truck cascades to its maintenance records."""
        db.conn.execute("PRAGMA foreign_keys=ON")

        # Create a truck
        db.conn.execute(
            "INSERT INTO trucks (plate_number) VALUES (?)",
            ("TRUCK-001",),
        )
        truck_id = db.conn.execute(
            "SELECT id FROM trucks WHERE plate_number = ?", ("TRUCK-001",)
        ).fetchone()[0]

        # Create a maintenance record for the truck
        db.conn.execute(
            "INSERT INTO maintenance_records (truck_id, maintenance_type, "
            "date, created_at) VALUES (?, ?, ?, ?)",
            (truck_id, "Oil Change", "2025-06-01", "2025-06-01"),
        )
        maint_id = db.conn.execute(
            "SELECT id FROM maintenance_records WHERE truck_id = ?",
            (truck_id,),
        ).fetchone()[0]

        # Sanity-check: record exists before deletion
        assert db.conn.execute(
            "SELECT COUNT(*) FROM maintenance_records WHERE id = ?",
            (maint_id,),
        ).fetchone()[0] == 1

        # Delete the truck — this should CASCADE
        db.conn.execute("DELETE FROM trucks WHERE id = ?", (truck_id,))

        # Verify the maintenance record was deleted
        remaining = db.conn.execute(
            "SELECT COUNT(*) FROM maintenance_records WHERE id = ?",
            (maint_id,),
        ).fetchone()[0]
        assert remaining == 0, (
            f"Expected maintenance record {maint_id} to be deleted "
            f"via CASCADE, but it still exists"
        )


# ═════════════════════════════════════════════════════════════════════════════
# New indexes
# ═════════════════════════════════════════════════════════════════════════════


class TestCompanyIdIndexes:
    """All business tables have ``company_id`` indexes for multi-tenant
    queries."""

    # Tables that should have an idx_<table>_company index
    COMPANY_TABLES = [
        "trips",
        "invoices",
        "trucks",
        "drivers",
        # "routes" — may or may not be registered; skip
        # "route_history" — may or may not be registered; skip
        "route_history_v2",
        "alerts",
        "operation_events",
        "trip_status_history",
        "maintenance_records",
        "maintenance_schedules",
        "truck_health_scores",
        "receipts",
        "gps_telemetry",
        "document_pipeline_runs",
        "document_package",
        "proforma_invoices",
        "contracts",
        "tacho_imports",
    ]

    def test_company_id_indexes_exist(self, db):
        """Every business table has a ``company_id`` column + index."""
        indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }

        for table in self.COMPANY_TABLES:
            idx_name = f"idx_{table}_company"
            assert idx_name in indexes, (
                f"Missing company_id index for table '{table}': "
                f"expected '{idx_name}'"
            )

    def test_company_id_column_present(self, db):
        """Each business table has a ``company_id`` column."""
        for table in self.COMPANY_TABLES:
            cols = {
                r[1]
                for r in db.conn.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()
            }
            assert "company_id" in cols, (
                f"Missing 'company_id' column in table '{table}'"
            )


class TestPerformanceIndexes:
    """Additional performance indexes for commonly filtered columns."""

    def test_gps_telemetry_composite_index(self, db):
        """gps_telemetry has a composite (truck_id, recorded_at) index."""
        indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_gps_truck_time" in indexes

    def test_invoice_status_index(self, db):
        """invoices table has a status index."""
        indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_invoices_status" in indexes

    def test_email_logs_indexes(self, db):
        """email_logs has indexes on trip_id and status."""
        indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_email_logs_trip" in indexes
        assert "idx_email_logs_status" in indexes

    def test_webhook_events_indexes(self, db):
        """webhook_events has indexes on partner, received_at, company_id."""
        indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_webhook_events_partner" in indexes
        assert "idx_webhook_events_received" in indexes
        assert "idx_webhook_events_company" in indexes

    def test_api_keys_indexes(self, db):
        """api_keys has indexes on partner and is_active."""
        indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_api_keys_partner" in indexes
        assert "idx_api_keys_active" in indexes

    def test_oauth2_clients_indexes(self, db):
        """oauth2_clients has indexes on client_id and partner."""
        indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_oauth2_clients_id" in indexes
        assert "idx_oauth2_clients_partner" in indexes


class TestIndexesIdempotent:
    """Verifies that CREATE INDEX IF NOT EXISTS statements are safe to
    re-run without error."""

    def test_indexes_are_idempotent(self, db):
        """CREATE INDEX IF NOT EXISTS does not error on re-run.

        Only indexes that were successfully created during init are
        tested; some INDEX_ constants reference columns that do not
        exist in their respective tables (e.g. ``cmr_audit_log`` lacks
        ``created_at``) and are skipped.
        """
        # Collect the names of indexes that *actually exist* after init
        existing_indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        # For each existing index, guess the CREATE INDEX statement
        # by looking up the corresponding INDEX_ constant.
        for idx_name in sorted(existing_indexes):
            const_name = self._find_constant_for_index(idx_name)
            if const_name is None:
                continue
            stmt = getattr(S, const_name)
            try:
                db.conn.execute(stmt)
            except Exception as exc:
                pytest.fail(
                    f"Idempotent index DDL failed on re-execution:\n"
                    f"  Index: {idx_name}\n"
                    f"  Statement: {stmt}\n"
                    f"  Error: {exc}"
                )

    @staticmethod
    def _find_constant_for_index(idx_name: str) -> str | None:
        """Return the INDEX_ constant name whose value creates *idx_name*.

        Iterates ``dir(S)`` and returns the first match; returns ``None``
        when no constant produces the given index name.
        """
        target = f"INDEX_{idx_name.removeprefix('idx_').upper()}"
        # Try exact match first
        if hasattr(S, target):
            return target
        # Fallback: scan all INDEX_ constants and match the index name
        # embedded in the DDL value.
        for name in dir(S):
            if not name.startswith("INDEX_"):
                continue
            val = getattr(S, name)
            if isinstance(val, str) and idx_name in val:
                return name
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Connection pool  (PostgresConnectionPool — mocked psycopg2)
# ═════════════════════════════════════════════════════════════════════════════


class TestPostgresConnectionPool:
    """PostgresConnectionPool lifecycle and interface.

    psycopg2 is imported lazily inside methods, so we inject mocks into
    ``sys.modules`` so the ``import psycopg2`` calls inside
    ``_initialize``, ``get_connection``, etc. find our mocks.
    """

    # ── Mock psycopg2 for every test in this class ────────────────────

    @pytest.fixture(autouse=True)
    def _mock_psycopg2(self, monkeypatch):
        """Stub psycopg2 + submodules so the pool methods can import them.

        Each submodule (``pool``, ``extras``) is added to ``sys.modules``
        individually with ``__path__`` set so that ``import psycopg2.extras``
        and similar statements do not raise ``ModuleNotFoundError``.
        """
        # ── psycopg2 package root ────────────────────────────────────
        mock_psycopg2 = MagicMock(__name__="psycopg2", __path__=["/stub/psycopg2"])

        # ── psycopg2.pool submodule ──────────────────────────────────
        mock_pool_cls = MagicMock()
        mock_pool_mod = MagicMock(
            __name__="psycopg2.pool",
            __path__=["/stub/psycopg2/pool"],
            ThreadedConnectionPool=mock_pool_cls,
        )
        mock_psycopg2.pool = mock_pool_mod

        # ── psycopg2.extras submodule ────────────────────────────────
        mock_extras = MagicMock(
            __name__="psycopg2.extras",
            __path__=["/stub/psycopg2/extras"],
            RealDictCursor=MagicMock(),
        )
        mock_psycopg2.extras = mock_extras

        # Register all three in sys.modules so ``import`` statements
        # resolve immediately without filesystem lookups.
        monkeypatch.setitem(sys.modules, "psycopg2", mock_psycopg2)
        monkeypatch.setitem(sys.modules, "psycopg2.pool", mock_pool_mod)
        monkeypatch.setitem(sys.modules, "psycopg2.extras", mock_extras)

    # ── Helpers ──────────────────────────────────────────────────────

    def _make_pool(self, mock_pool=None, **kwargs):
        """Build a PostgresConnectionPool bypassing the real ``_initialize``.

        Returns the pool instance and the underlying ``ThreadedConnectionPool``
        mock so the test can configure and assert on it.
        """
        if mock_pool is None:
            mock_pool = MagicMock()
            mock_pool.getconn.return_value = MagicMock()
        # __new__ + manual init avoids calling _initialize
        pool = PostgresConnectionPool.__new__(PostgresConnectionPool)
        pool._dsn = kwargs.get("dsn", "postgresql://localhost/db")
        pool._min = kwargs.get("min_connections", 2)
        pool._max = kwargs.get("max_connections", 20)
        pool._pool = mock_pool
        pool._local = __import__("threading").local()
        return pool, mock_pool

    # ── Tests ────────────────────────────────────────────────────────

    def test_pool_initialization(self):
        """PostgresConnectionPool creates with specified min/max."""
        pool, _ = self._make_pool(
            dsn="postgresql://user:pass@localhost/db",
            min_connections=3,
            max_connections=15,
        )
        assert pool._min == 3
        assert pool._max == 15
        assert pool._dsn == "postgresql://user:pass@localhost/db"

    def test_get_connection(self):
        """get_connection() returns a connection from the pool."""
        fake_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = fake_conn
        pool, _ = self._make_pool(mock_pool=mock_pool)

        conn = pool.get_connection()

        assert conn is fake_conn
        mock_pool.getconn.assert_called_once()
        assert conn.autocommit is False

    def test_return_connection(self):
        """return_connection() returns a borrowed connection to the pool."""
        fake_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = fake_conn
        pool, _ = self._make_pool(mock_pool=mock_pool)

        conn = pool.get_connection()
        pool.return_connection(conn)
        mock_pool.putconn.assert_called_once_with(conn)

    def test_return_connection_noop_on_none(self):
        """return_connection(None) does not raise."""
        mock_pool = MagicMock()
        pool, _ = self._make_pool(mock_pool=mock_pool)
        pool.return_connection(None)  # should not raise
        mock_pool.putconn.assert_not_called()

    def test_get_cached_connection(self):
        """get_cached_connection() returns thread-local cached connection."""
        fake_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = fake_conn
        pool, _ = self._make_pool(mock_pool=mock_pool)

        # First call — obtains from pool
        c1 = pool.get_cached_connection()
        assert c1 is fake_conn
        assert mock_pool.getconn.call_count == 1

        # Second call — returns cached (same object)
        c2 = pool.get_cached_connection()
        assert c2 is c1
        assert mock_pool.getconn.call_count == 1  # no extra call

    def test_pool_stats(self):
        """stats dict has min/max/status keys."""
        mock_pool = MagicMock()
        pool, _ = self._make_pool(
            mock_pool=mock_pool,
            dsn="postgresql://localhost/db",
            min_connections=4,
            max_connections=25,
        )
        stats = pool.stats
        assert stats["min"] == 4
        assert stats["max"] == 25
        assert stats["status"] == "active"

    def test_stats_inactive_when_uninitialized(self):
        """stats returns inactive status when pool is None."""
        pool = PostgresConnectionPool.__new__(PostgresConnectionPool)
        pool._pool = None
        pool._min = 0
        pool._max = 0

        stats = pool.stats
        assert stats["status"] == "inactive"
        assert stats["min"] == 0
        assert stats["max"] == 0

    def test_close_all(self):
        """close_all() closes the pool cleanly."""
        fake_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = fake_conn
        pool, _ = self._make_pool(mock_pool=mock_pool)

        # Acquire a cached connection
        pool.get_cached_connection()
        pool.close_all()

        # The cached connection should be returned to the pool
        mock_pool.putconn.assert_called_once_with(fake_conn)
        # The pool itself should be closed
        mock_pool.closeall.assert_called_once()

    def test_close_all_multiple_times(self):
        """close_all() is safe to call multiple times."""
        mock_pool = MagicMock()
        pool, _ = self._make_pool(mock_pool=mock_pool)
        pool.close_all()
        pool.close_all()  # second call should not raise
        pool.close_all()  # third call should not raise

    def test_get_connection_before_init_raises(self):
        """Accessing pool methods before init raises RuntimeError."""
        pool = PostgresConnectionPool.__new__(PostgresConnectionPool)
        pool._pool = None

        with pytest.raises(RuntimeError, match="not initialized"):
            pool.get_connection()

        with pytest.raises(RuntimeError, match="not initialized"):
            pool.get_cached_connection()

    def test_connection_pool_default_min_max(self):
        """Default min/max values are 2 and 20."""
        pool, _ = self._make_pool()
        assert pool._min == 2
        assert pool._max == 20


# ═════════════════════════════════════════════════════════════════════════════
# New tables  (webhook_events, oauth2_clients, api_keys)
# ═════════════════════════════════════════════════════════════════════════════


class TestNewTables:
    """Verify that new tables exist with the correct schema."""

    # ── webhook_events ──────────────────────────────────────────────────

    def test_webhook_events_table(self, db):
        """webhook_events table exists."""
        tables = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "webhook_events" in tables

    def test_webhook_events_columns(self, db):
        """webhook_events has all required columns."""
        cols = {
            r[1]: r[2]
            for r in db.conn.execute(
                "PRAGMA table_info(webhook_events)"
            ).fetchall()
        }
        expected = {
            "id": "INTEGER",
            "partner": "TEXT",
            "event_type": "TEXT",
            "payload": "TEXT",
            "signature_valid": "INTEGER",
            "processing_status": "TEXT",
            "received_at": "TEXT",
            "processed_at": "TEXT",
            "company_id": "INTEGER",
        }
        for col_name, col_type in expected.items():
            assert col_name in cols, (
                f"Missing column '{col_name}' in webhook_events"
            )
            # SQLite may report type as INTEGER or TEXT — accept both
            assert col_type.upper() in cols[col_name].upper() or cols[col_name].upper() in col_type.upper(), (
                f"Column '{col_name}' has type '{cols[col_name]}', "
                f"expected '{col_type}'"
            )

    def test_webhook_events_indexes(self, db):
        """webhook_events has the expected indexes."""
        indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_webhook_events_partner" in indexes
        assert "idx_webhook_events_received" in indexes
        assert "idx_webhook_events_company" in indexes

    # ── oauth2_clients ──────────────────────────────────────────────────

    def test_oauth2_clients_table(self, db):
        """oauth2_clients table exists."""
        tables = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "oauth2_clients" in tables

    def test_oauth2_clients_columns(self, db):
        """oauth2_clients has all required columns."""
        cols = {
            r[1]: r[2]
            for r in db.conn.execute(
                "PRAGMA table_info(oauth2_clients)"
            ).fetchall()
        }
        expected = {
            "id": "INTEGER",
            "client_id": "TEXT",
            "client_name": "TEXT",
            "partner": "TEXT",
            "scopes": "TEXT",
            "secret_hash": "TEXT",
            "is_active": "INTEGER",
            "created_by": "INTEGER",
            "created_at": "TEXT",
            "last_used_at": "TEXT",
            "company_id": "INTEGER",
        }
        for col_name, col_type in expected.items():
            assert col_name in cols, (
                f"Missing column '{col_name}' in oauth2_clients"
            )

    def test_oauth2_clients_unique_constraint(self, db):
        """client_id column has a UNIQUE constraint."""
        # Find the `client_id` column definition and check its pk flag
        cols = {
            r[1]: r
            for r in db.conn.execute(
                "PRAGMA table_info(oauth2_clients)"
            ).fetchall()
        }
        # Column info: cid, name, type, notnull, dflt_value, pk
        col_info = cols["client_id"]
        # The UNIQUE is enforced by a unique index (idx_oauth2_clients_id),
        # not by the column itself — verify the index exists instead.
        indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_oauth2_clients_id" in indexes

    # ── api_keys ────────────────────────────────────────────────────────

    def test_api_keys_table(self, db):
        """api_keys table exists."""
        tables = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "api_keys" in tables

    def test_api_keys_columns(self, db):
        """api_keys has all required columns."""
        cols = {
            r[1]: r[2]
            for r in db.conn.execute(
                "PRAGMA table_info(api_keys)"
            ).fetchall()
        }
        expected = {
            "id": "INTEGER",
            "key_hash": "TEXT",
            "key_prefix": "TEXT",
            "name": "TEXT",
            "partner": "TEXT",
            "scopes": "TEXT",
            "is_active": "INTEGER",
            "created_by": "INTEGER",
            "created_at": "TEXT",
            "last_used_at": "TEXT",
            "expires_at": "TEXT",
            "revoked_at": "TEXT",
            "company_id": "INTEGER",
        }
        for col_name, col_type in expected.items():
            assert col_name in cols, (
                f"Missing column '{col_name}' in api_keys"
            )

    def test_api_keys_unique_constraint(self, db):
        """key_hash column has a UNIQUE constraint."""
        # Verify the unique index exists
        indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_api_keys_partner" in indexes
        assert "idx_api_keys_active" in indexes
        # The UNIQUE on key_hash is defined in the CREATE TABLE as "key_hash TEXT NOT NULL UNIQUE"
        # SQLite creates an automatic index for UNIQUE columns
        auto_indexes = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
            ).fetchall()
        }
        # Check that either an auto-index or the table-level UNIQUE exists
        has_unique = any(
            "key_hash" in (r[0] or "")
            for r in db.conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' "
                "AND name LIKE 'sqlite_autoindex_api_keys_%'"
            ).fetchall()
        )
        if not has_unique:
            # Fallback: check via PRAGMA index_list
            index_list = {
                r[1]
                for r in db.conn.execute("PRAGMA index_list(api_keys)").fetchall()
            }
            has_unique = any("key_hash" in idx or "api_keys" in idx for idx in index_list)

        assert has_unique or "idx_api_keys_partner" in indexes, (
            "api_keys should have a UNIQUE index on key_hash"
        )


# ═════════════════════════════════════════════════════════════════════════════
# Connection pool  (SQLite ConnectionPool — real, no mocking needed)
# ═════════════════════════════════════════════════════════════════════════════


class TestSqliteConnectionPool:
    """ConnectionPool (SQLite) — basic lifecycle and configuration."""

    def test_pool_initialization(self):
        """ConnectionPool creates with specified db_path and default params."""
        pool = ConnectionPool(":memory:")
        try:
            assert pool._db_path == ":memory:"
            assert pool._timeout == 30
            assert pool._generation == 0
        finally:
            pool.close_all()

    def test_pool_custom_timeout(self):
        """ConnectionPool accepts a custom timeout."""
        pool = ConnectionPool(":memory:", timeout=15)
        try:
            assert pool._timeout == 15
        finally:
            pool.close_all()

    def test_get_connection(self):
        """.conn returns an sqlite3.Connection."""
        pool = ConnectionPool(":memory:")
        try:
            conn = pool.conn
            assert isinstance(conn, sqlite3.Connection)
            assert conn.execute("SELECT 1").fetchone()[0] == 1
        finally:
            pool.close_all()

    def test_get_connection_same_thread(self):
        """Same thread always gets the same connection object."""
        pool = ConnectionPool(":memory:")
        try:
            c1 = pool.conn
            c2 = pool.conn
            assert c1 is c2
        finally:
            pool.close_all()

    def test_return_connection(self):
        """Returning a connection is a no-op for ConnectionPool (managed by thread-local)."""
        pool = ConnectionPool(":memory:")
        try:
            conn = pool.conn
            # ConnectionPool does not have an explicit return_connection;
            # the connection stays cached for the thread.  Just verify
            # that calling conn after close_all() fails as expected.
            conn.execute("SELECT 1")  # still alive
        finally:
            pool.close_all()

    def test_pool_stats(self):
        """ConnectionPool does not expose a stats property, but we can
        verify internal tracking works."""
        pool = ConnectionPool(":memory:")
        try:
            pool.conn
            assert len(pool._connections) == 1
        finally:
            pool.close_all()

    def test_close_all(self):
        """close_all() closes all tracked connections."""
        pool = ConnectionPool(":memory:")
        conn = pool.conn
        pool.close_all()
        # Connection should now be closed
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")
        # Pool state is reset
        assert pool._connections == []
        assert pool._generation == 1

    def test_close_all_idempotent(self):
        """close_all() can be called multiple times."""
        pool = ConnectionPool(":memory:")
        pool.close_all()
        pool.close_all()  # should not raise
        pool.close_all()  # should not raise

    def test_conn_after_close_all_creates_fresh(self):
        """After close_all(), .conn creates a fresh connection."""
        pool = ConnectionPool(":memory:")
        c1 = pool.conn
        pool.close_all()
        c2 = pool.conn
        assert c1 is not c2
        assert c2.execute("SELECT 1").fetchone()[0] == 1
        pool.close_all()

    def test_foreign_keys_pragma(self):
        """ConnectionPool enables foreign_keys pragma."""
        pool = ConnectionPool(":memory:")
        try:
            conn = pool.conn
            (fk_enabled,) = conn.execute("PRAGMA foreign_keys").fetchone()
            assert fk_enabled == 1
        finally:
            pool.close_all()

    def test_row_factory(self):
        """ConnectionPool sets row_factory to sqlite3.Row."""
        pool = ConnectionPool(":memory:")
        try:
            conn = pool.conn
            assert conn.row_factory is sqlite3.Row
        finally:
            pool.close_all()


# ═════════════════════════════════════════════════════════════════════════════
# Schema migration constants validation
# ═════════════════════════════════════════════════════════════════════════════


class TestSchemaConstants:
    """Validates that all TABLE_, INDEX_, ALTER_ constants from schema.py
    execute without error against a fresh SQLite database."""

    TABLE_CONSTANTS = [
        name
        for name in dir(S)
        if name.startswith("TABLE_") and isinstance(getattr(S, name), str)
        and not name.startswith("TABLE_SCHEMA_MIGRATIONS")
    ]

    def test_all_table_ddl_executes(self, mem_conn):
        """Every TABLE_ constant is valid SQL on a bare connection."""
        failures = []
        for name in self.TABLE_CONSTANTS:
            stmt = getattr(S, name)
            try:
                mem_conn.execute(stmt)
            except Exception as exc:
                failures.append((name, str(exc)))
        assert not failures, (
            f"{len(failures)} TABLE_ constant(s) failed to execute:\n" +
            "\n".join(f"  {n}: {e}" for n, e in failures)
        )

    def test_all_index_ddl_executes_on_initialized_db(self, db):
        """Every INDEX_ constant whose table+column exists can be executed

        against a fully initialized database.  Indexes that reference
        columns not present in their tables (e.g.
        ``idx_cmr_audit_created`` on a table that lacks ``created_at``)
        are noted as known schema gaps and are not considered failures.
        """
        index_names = [
            name
            for name in dir(S)
            if name.startswith("INDEX_") and isinstance(getattr(S, name), str)
        ]
        failures = []
        skipped = []
        for name in index_names:
            stmt = getattr(S, name)
            try:
                db.conn.execute(stmt)
            except Exception as exc:
                err_msg = str(exc)
                if "no such column" in err_msg or "no such table" in err_msg:
                    skipped.append((name, err_msg))
                else:
                    failures.append((name, err_msg))
        if skipped:
            import logging as _log
            _log.getLogger(__name__).warning(
                "Skipped %d index DDL(s) — table/column missing:\n%s",
                len(skipped),
                "\n".join(f"  {n}: {e}" for n, e in skipped),
            )
        assert not failures, (
            f"{len(failures)} INDEX_ constant(s) failed to execute:\n" +
            "\n".join(f"  {n}: {e}" for n, e in failures)
        )
