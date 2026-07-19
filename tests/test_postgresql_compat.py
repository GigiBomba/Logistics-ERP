"""PostgreSQL compatibility tests — validate schema, migrations, and CRUD.

These tests require a running PostgreSQL instance.  Set the environment
variable ``OPERION_TEST_PG_DSN`` to enable them::

    set OPERION_TEST_PG_DSN=postgresql://postgres:postgres@localhost:5432/operion_test

Without this variable the entire module is skipped.
"""

from __future__ import annotations

import os
import sys
import pytest

PG_DSN = os.environ.get("OPERION_TEST_PG_DSN", "")
PG_AVAILABLE = bool(PG_DSN)

pytestmark = pytest.mark.skipif(not PG_AVAILABLE, reason="OPERION_TEST_PG_DSN not set")


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def pg_db():
    """Create a PostgreSQL DatabaseManager, run schema, yield, then tear down."""
    # Ensure operion is importable
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from database.db_manager import DatabaseManager

    db = DatabaseManager(PG_DSN, engine="postgresql", pool_min=1, pool_max=2)
    # _init_db() is called automatically in __init__
    yield db
    db.close()


@pytest.fixture
def pg_clean(pg_db):
    """Provide a PG DatabaseManager with clean state between tests."""
    return pg_db


# ── Schema tests ────────────────────────────────────────────────────────────


class TestPostgresSchema:
    """Validate that schema_pg.sql creates all expected objects."""

    def test_schema_migrations_table_exists(self, pg_clean):
        assert pg_clean._table_exists("schema_migrations")

    def test_core_tables_exist(self, pg_clean):
        for tbl in ("trips", "invoices", "trucks", "drivers", "clients",
                     "documents", "companies", "users", "settings"):
            assert pg_clean._table_exists(tbl), f"Table {tbl} missing"

    def test_operation_tables_exist(self, pg_clean):
        for tbl in ("alerts", "operation_events", "trip_status_history",
                     "maintenance_records", "maintenance_schedules",
                     "truck_health_scores"):
            assert pg_clean._table_exists(tbl), f"Table {tbl} missing"

    def test_route_tables_exist(self, pg_clean):
        for tbl in ("routes", "route_history", "route_history_v2",
                     "route_events", "truck_route_assignments"):
            assert pg_clean._table_exists(tbl), f"Table {tbl} missing"

    def test_document_tables_exist(self, pg_clean):
        for tbl in ("document_links", "document_versions", "contracts",
                     "document_templates", "document_pipeline_runs",
                     "document_package", "document_package_items"):
            assert pg_clean._table_exists(tbl), f"Table {tbl} missing"

    def test_receipt_proforma_exist(self, pg_clean):
        for tbl in ("receipts", "proforma_invoices"):
            assert pg_clean._table_exists(tbl)

    def test_automail_tables_exist(self, pg_clean):
        for tbl in ("automail_templates", "automail_schedules",
                     "automail_client_overrides", "automail_settings"):
            assert pg_clean._table_exists(tbl)

    def test_tacho_tables_exist(self, pg_clean):
        for tbl in ("tacho_imports", "tacho_driver_activity", "tacho_vehicle_data"):
            assert pg_clean._table_exists(tbl)

    def test_cmr_tables_exist(self, pg_clean):
        for tbl in ("cmr_counter", "cmr_audit_log", "successive_carriers"):
            assert pg_clean._table_exists(tbl)

    def test_auth_tables_exist(self, pg_clean):
        for tbl in ("api_keys", "oauth2_clients", "webhook_events", "waitlist_entries"):
            assert pg_clean._table_exists(tbl)

    def test_schema_migration_versions(self, pg_clean):
        rows = pg_clean.rows_to_dicts(
            pg_clean.execute("SELECT version, name FROM schema_migrations ORDER BY version").fetchall()
        )
        versions = {r["version"]: r["name"] for r in rows}
        assert 1 in versions, "V1 missing"
        assert 2 in versions, "V2 missing"
        assert 3 in versions, "V3 missing"
        assert 4 in versions, "V4 missing"

    def test_search_vector_column_exists(self, pg_clean):
        """Documents table should have tsvector column for FTS replacement."""
        assert pg_clean._column_exists("documents", "search_vector")

    def test_soft_delete_columns(self, pg_clean):
        """Business tables should have deleted_at columns."""
        for tbl in ("trips", "invoices", "clients", "drivers", "trucks"):
            assert pg_clean._column_exists(tbl, "deleted_at"), f"{tbl}.deleted_at missing"

    def test_company_id_on_new_tables(self, pg_clean):
        """P0.6 tables should have company_id."""
        for tbl in ("client_contacts", "client_tags", "document_links", "document_versions"):
            assert pg_clean._column_exists(tbl, "company_id"), f"{tbl}.company_id missing"

    def test_pipeline_triggers_exist(self, pg_clean):
        """PL/pgSQL trigger functions should exist."""
        funcs = pg_clean.rows_to_dicts(
            pg_clean.execute(
                "SELECT proname FROM pg_proc "
                "WHERE proname IN ('validate_pipeline_stage', 'validate_pipeline_status', "
                "'documents_search_update')"
            ).fetchall()
        )
        names = {r["proname"] for r in funcs}
        assert "validate_pipeline_stage" in names
        assert "validate_pipeline_status" in names
        assert "documents_search_update" in names


# ── CRUD tests ──────────────────────────────────────────────────────────────


class TestPostgresCRUD:
    """Validate basic CRUD works through the DatabaseManager abstraction."""

    def test_execute_select(self, pg_clean):
        result = pg_clean.execute("SELECT 1 AS one").fetchone()
        assert result is not None
        assert dict(result)["one"] == 1

    def test_placeholder_adaptation(self, pg_clean):
        """? placeholders should be converted to %s for PostgreSQL."""
        result = pg_clean.execute("SELECT ?::text AS val", ("hello",)).fetchone()
        assert dict(result)["val"] == "hello"

    def test_commit_rollback(self, pg_clean):
        """commit() and rollback() should not raise."""
        pg_clean.commit()
        pg_clean.rollback()

    def test_row_to_dict_pg(self, pg_clean):
        """row_to_dict should handle PostgreSQL RealDictCursor results."""
        row = pg_clean.execute("SELECT 1 AS n, 'x' AS s").fetchone()
        d = pg_clean.row_to_dict(row)
        assert d == {"n": 1, "s": "x"}

    def test_insert_and_select(self, pg_clean):
        """Basic INSERT and SELECT should work with engine-agnostic execute()."""
        pg_clean.execute("INSERT INTO companies (company_name) VALUES (%s)", ("TestCo",))
        pg_clean.commit()
        rows = pg_clean.rows_to_dicts(
            pg_clean.execute("SELECT company_name FROM companies WHERE company_name = %s", ("TestCo",)).fetchall()
        )
        assert len(rows) == 1
        assert rows[0]["company_name"] == "TestCo"

    def test_insert_returning_id(self, pg_clean):
        """INSERT ... RETURNING id should work."""
        result = pg_clean.execute(
            "INSERT INTO companies (company_name) VALUES (%s) RETURNING id",
            ("ReturnCo",),
        ).fetchone()
        assert result is not None
        cid = dict(result)["id"]
        assert cid > 0
        # cleanup
        pg_clean.execute("DELETE FROM companies WHERE id = %s", (cid,))
        pg_clean.commit()


# ── Repository compatibility tests ──────────────────────────────────────────


class TestPostgresRepositories:
    """Smoke-test that repositories work with PostgreSQL."""

    def test_settings_repo_upsert_get(self, pg_clean):
        from repositories.settings_repository import SettingsRepository
        repo = SettingsRepository(pg_clean)
        repo.upsert_setting("test_key", "test_value")
        val = repo.get_setting_value("test_key")
        assert val == "test_value"

    def test_settings_repo_table_names(self, pg_clean):
        from repositories.settings_repository import SettingsRepository
        repo = SettingsRepository(pg_clean)
        tables = repo.get_table_names()
        assert "trips" in tables
        assert "companies" in tables

    def test_company_repo_create(self, pg_clean):
        from repositories.client_repository import ClientRepository
        repo = ClientRepository(pg_clean)
        cid = repo.create({
            "name": "PG Test Client",
            "created_at": "2026-01-01",
        })
        assert cid > 0

    def test_trip_repo_basic(self, pg_clean):
        from repositories.trip_repository import TripRepository
        repo = TripRepository(pg_clean)
        tid = repo.create({
            "created_at": "2026-01-01",
            "status": "Planned",
        })
        assert tid > 0
        trip = repo.get_by_id(tid)
        assert trip is not None
        assert trip["status"] == "Planned"
