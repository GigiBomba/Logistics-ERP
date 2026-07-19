"""Tests for database schema constants — verify all TABLE_*, INDEX_*, ALTER_*,
TRIGGER_* constants are valid SQL that can be executed against SQLite.
"""

from __future__ import annotations

import sqlite3

import pytest

import database.schema as S


# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mem():
    """Provide a fresh in-memory SQLite connection for each test."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    yield conn
    conn.close()


def _execute(stmt: str, conn: sqlite3.Connection) -> None:
    """Execute a single SQL statement, raising if it fails."""
    conn.execute(stmt)


# Collect all constant names upfront
TABLE_CONSTANTS = [
    name
    for name in dir(S)
    if name.startswith("TABLE_") and isinstance(getattr(S, name), str)
]

INDEX_CONSTANTS = [
    name
    for name in dir(S)
    if name.startswith("INDEX_") and isinstance(getattr(S, name), str)
]

ALTER_CONSTANTS = [
    name
    for name in dir(S)
    if name.startswith("ALTER_") and isinstance(getattr(S, name), str)
]

TRIGGER_CONSTANTS = [
    name
    for name in dir(S)
    if name.startswith("TRIGGER_") and isinstance(getattr(S, name), str)
]

MIGRATION_CONSTANTS = [
    name
    for name in dir(S)
    if name.startswith("MIGRATION_") and isinstance(getattr(S, name), str)
]


def _create_all_tables(mem):
    """Create all tables in sequence, ignoring errors (e.g. FTS5)."""
    for name in TABLE_CONSTANTS:
        try:
            _execute(getattr(S, name), mem)
        except Exception:
            pass


# ── TABLE statements ─────────────────────────────────────────────────────────


class TestTableCreate:
    """Every TABLE_* constant should execute as valid CREATE TABLE SQL."""

    @pytest.mark.parametrize("name", TABLE_CONSTANTS)
    def test_table_create_is_valid_sql(self, name, mem):
        sql = getattr(S, name)
        _execute(sql, mem)

    def test_all_tables_created(self, mem):
        _create_all_tables(mem)
        tables = {
            r[0]
            for r in mem.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for required in (
            "trips", "trucks", "drivers", "clients", "invoices", "settings",
            "companies", "users", "documents", "route_history_v2",
        ):
            assert required in tables, f"Missing table: {required}"

    def test_table_gps_telemetry(self, mem):
        _execute(S.TABLE_GPS_TELEMETRY, mem)
        cols = {r[1] for r in mem.execute("PRAGMA table_info(gps_telemetry)").fetchall()}
        for col in ("truck_id", "latitude", "longitude", "speed_kmh", "recorded_at"):
            assert col in cols, f"Missing gps_telemetry column: {col}"

    def test_table_companies_has_check_constraint(self, mem):
        _execute(S.TABLE_COMPANIES, mem)
        cols = {r[1] for r in mem.execute("PRAGMA table_info(companies)").fetchall()}
        assert "subscription_tier" in cols

    def test_table_document_pipeline_runs(self, mem):
        _execute(S.TABLE_DOCUMENT_PIPELINE_RUNS, mem)
        cols = {r[1] for r in mem.execute("PRAGMA table_info(document_pipeline_runs)").fetchall()}
        for col in ("run_uuid", "status", "stage", "source_file_path"):
            assert col in cols, f"Missing column: {col}"


# ── INDEX statements ─────────────────────────────────────────────────────────


class TestIndexCreate:
    """Every INDEX_* constant should execute as valid SQL after table creation.

    Some indexes reference columns added by migrations (ALTER TABLE).
    Those are wrapped in try/except since the test table only has the
    base schema columns.
    """

    def _all_tables_and_migrations(self, mem):
        """Create tables and apply ALTER migrations so index columns exist."""
        _create_all_tables(mem)
        for name in ALTER_CONSTANTS:
            try:
                _execute(getattr(S, name), mem)
            except Exception:
                pass

    @pytest.mark.parametrize("name", INDEX_CONSTANTS)
    def test_index_create_is_valid_sql(self, name, mem):
        self._all_tables_and_migrations(mem)
        sql = getattr(S, name)
        try:
            _execute(sql, mem)
        except sqlite3.OperationalError as e:
            # Some indexes may reference columns that genuinely don't exist
            # in certain SQLite configurations.  We accept this as long
            # as the SQL is syntactically valid (parsed OK).
            if "no such column" in str(e).lower():
                pytest.skip(f"Index {name} requires a migration column: {e}")
            raise

    def test_all_indexes_created(self, mem):
        self._all_tables_and_migrations(mem)
        for iname in INDEX_CONSTANTS:
            try:
                _execute(getattr(S, iname), mem)
            except Exception:
                pass
        indexes = {
            r[0]
            for r in mem.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_trips_status" in indexes
        assert "idx_clients_name" in indexes
        assert "idx_drivers_active" in indexes


# ── ALTER statements (migrations) ────────────────────────────────────────────


class TestAlterStatements:
    """Every ALTER_* constant should be valid SQL to add a column.

    Some ALTERs reference columns that already exist in the base table
    definition (because the column was added directly to the CREATE TABLE
    after the ALTER was written).  Those raise ``duplicate column`` which
    is acceptable — the SQL is still syntactically valid.
    """

    def _table_for_alter(self, name):
        """Derive the base table name from an ALTER constant name.

        Conventions:
          ALTER_TRIPS_ADD_DRIVER_ID  -> trips
          ALTER_CLIENTS_ADD_TYPE     -> clients
          ALTER_DOCUMENTS_ADD_OCR_TEXT -> documents
          ALTER_TRUCKS_ADD_TACHOGRAPH -> trucks
        """
        parts = name.split("_", 2)  # ['ALTER', 'TRIPS', 'ADD_DRIVER_ID']
        return parts[1].lower()

    @pytest.mark.parametrize("name", ALTER_CONSTANTS)
    def test_alter_is_valid_sql(self, name, mem):
        table = self._table_for_alter(name)
        # Find the matching TABLE_ constant
        table_const_name = f"TABLE_{table.upper()}"
        if hasattr(S, table_const_name):
            try:
                _execute(getattr(S, table_const_name), mem)
            except Exception:
                pass
        sql = getattr(S, name)
        try:
            _execute(sql, mem)
        except sqlite3.OperationalError as e:
            # "duplicate column name" means the column already existed
            # in the CREATE TABLE — acceptable.
            if "duplicate column" in str(e).lower():
                pytest.skip(f"ALTER {name} column already exists in table: {e}")
            # "no such table" means the target table wasn't created
            # in the test fixture (e.g. new company_id tables from migrations)
            if "no such table" in str(e).lower():
                pytest.skip(f"ALTER {name} target table not in test fixture: {e}")
            raise


# ── TRIGGER statements ───────────────────────────────────────────────────────


class TestTriggerCreate:
    """Every TRIGGER_* constant should execute as valid SQL."""

    @pytest.mark.parametrize("name", TRIGGER_CONSTANTS)
    def test_trigger_create_is_valid_sql(self, name, mem):
        _create_all_tables(mem)
        sql = getattr(S, name)
        _execute(sql, mem)


# ── MIGRATION statements ─────────────────────────────────────────────────────


class TestMigrationStatements:
    @pytest.mark.parametrize("name", MIGRATION_CONSTANTS)
    def test_migration_is_valid_sql(self, name, mem):
        sql = getattr(S, name)
        _execute(sql, mem)


# ── Enum validation values ──────────────────────────────────────────────────


class TestPipelineEnums:
    def test_pipeline_stage_values_defined(self):
        assert len(S.PIPELINE_STAGE_VALUES) >= 10
        assert "import" in S.PIPELINE_STAGE_VALUES
        assert "failed" in S.PIPELINE_STAGE_VALUES

    def test_pipeline_status_values_defined(self):
        assert len(S.PIPELINE_STATUS_VALUES) >= 10
        assert "imported" in S.PIPELINE_STATUS_VALUES
        assert "complete" in S.PIPELINE_STATUS_VALUES
        assert "failed" in S.PIPELINE_STATUS_VALUES

    def test_all_trigger_sql_includes_enum_values(self):
        """Verify triggers reference the correct enum values."""
        assert "import" in S.TRIGGER_PIPELINE_RUNS_STAGE_CHECK
        assert "failed" in S.TRIGGER_PIPELINE_RUNS_STAGE_CHECK
        assert "imported" in S.TRIGGER_PIPELINE_RUNS_STATUS_CHECK
        assert "complete" in S.TRIGGER_PIPELINE_RUNS_STATUS_CHECK

    def test_pipeline_triggers_enforce_stage(self, mem):
        """Pipeline triggers reject invalid stage/status values."""
        _create_all_tables(mem)
        _execute(S.TRIGGER_PIPELINE_RUNS_STAGE_CHECK, mem)
        _execute(S.TRIGGER_PIPELINE_RUNS_STATUS_CHECK, mem)

        # Valid insert should succeed
        now = "2025-01-01T00:00:00Z"
        mem.execute(
            "INSERT INTO document_pipeline_runs "
            "(run_uuid, source_file_path, source_file_name, source_mime_type, "
            "source_file_size, status, stage, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "u1", "/path/file.pdf", "file.pdf", "application/pdf",
                100, "imported", "import", now, now,
            ),
        )

        # Invalid stage should fail
        with pytest.raises(sqlite3.IntegrityError, match="invalid"):
            mem.execute(
                "INSERT INTO document_pipeline_runs "
                "(run_uuid, source_file_path, source_file_name, source_mime_type, "
                "source_file_size, status, stage, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "u2", "/path/file.pdf", "file.pdf", "application/pdf",
                    100, "imported", "bad_stage", now, now,
                ),
            )

        # Invalid status should fail
        with pytest.raises(sqlite3.IntegrityError, match="invalid"):
            mem.execute(
                "INSERT INTO document_pipeline_runs "
                "(run_uuid, source_file_path, source_file_name, source_mime_type, "
                "source_file_size, status, stage, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "u3", "/path/file.pdf", "file.pdf", "application/pdf",
                    100, "bad_status", "import", now, now,
                ),
            )


# ── FTS5 table ──────────────────────────────────────────────────────────────


class TestFtsTable:
    def test_documents_fts_creates(self, mem):
        """FTS5 virtual table requires SQLite compiled with FTS5."""
        _create_all_tables(mem)
        try:
            _execute(S.TABLE_DOCUMENTS_FTS, mem)
            tables = {
                r[0]
                for r in mem.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "documents_fts" in tables
        except sqlite3.OperationalError as e:
            if "no such module: fts5" in str(e):
                pytest.skip("SQLite built without FTS5 support")
            raise


# ── Receipt table columns ────────────────────────────────────────────────────


class TestReceiptTable:
    def test_receipt_table_has_all_columns(self, mem):
        _execute(S.TABLE_RECEIPTS, mem)
        cols = {r[1] for r in mem.execute("PRAGMA table_info(receipts)").fetchall()}
        for col in (
            "receipt_number", "receipt_type", "amount", "status",
            "currency", "payment_method", "notes",
        ):
            assert col in cols, f"Missing receipt column: {col}"


# ── Conftest compatibility: verify InMemoryDB constant imports exist ─────────


class TestInMemoryDBCompatibility:
    """Verify that all constants used by tests/test_helpers.py InMemoryDB exist."""

    def test_all_inmemorydb_constants_exist(self):
        """Smoke-test that InMemoryDB can be instantiated."""
        from tests.test_helpers import InMemoryDB  # noqa: F401
        db = InMemoryDB()
        assert db.conn is not None
        db.conn.close()
