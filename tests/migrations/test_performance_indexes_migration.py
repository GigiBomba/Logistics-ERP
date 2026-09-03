"""Performance-index migration tests for k4c5d6e7f8a1.

DB4/DB6 — verifies ``upgrade`` creates the three covering indexes and
``downgrade`` removes exactly those indexes again, on a throwaway SQLite
database (same harness style as ``test_all_migrations.py``).

DB5 (``trips.driver_name``) is deliberately skipped and this file proves why:
``database/schema.py`` and ``database/schema_pg.sql`` already create
``idx_trips_driver_name ON trips(driver_name)`` at init time on both
engines, and the migration module does not touch trips.
"""

from __future__ import annotations

import os

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.compiler import compiles

PROJECT_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
ALEMBIC_DIR = os.path.join(PROJECT_DIR, "alembic")


# ── SQLite compatibility (mirrors tests/migrations/test_all_migrations.py) ──
# Upgrading the full chain to k4c5d6e7f8a1 passes through migrations that
# use PostgreSQL-only types/constraints; these patches make them compile on
# the throwaway SQLite database.


@compiles(postgresql.JSONB, "sqlite")
def _compile_jsonb_sqlite(
    type_: postgresql.JSONB,
    compiler: sa.sql.compiler.SQLCompiler,
    **kw: object,
) -> str:
    """Compile postgresql.JSONB to JSON for SQLite."""
    del type_, compiler, kw
    return "JSON"


def _patch_sqlite_add_constraint() -> None:
    """Make ``SqliteImpl.add_constraint`` a no-op (SQLite cannot ADD COLUMN
    with a FOREIGN KEY constraint)."""
    import alembic.ddl.sqlite as _ddl_sqlite

    def _noop(self: object, constraint: object) -> None:
        pass  # silently drop the constraint

    _ddl_sqlite.SQLiteImpl.add_constraint = _noop


_patch_sqlite_add_constraint()

REV_UP = "k4c5d6e7f8a1"
REV_DOWN = "j2b3c4d5e6f0"

EXPECTED_INDEXES: dict[str, tuple[str, list[str]]] = {
    "idx_expenses_company": ("expenses", ["company_id"]),
    "idx_maintenance_records_company_truck_date": (
        "maintenance_records",
        ["company_id", "truck_id", "date"],
    ),
    "idx_tacho_driver_activity_company_driver_date": (
        "tacho_driver_activity",
        ["company_id", "driver_id", "activity_date"],
    ),
}

BASE_TABLES_SQL: dict[str, str] = {
    "companies": """
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    """,
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            login TEXT
        )
    """,
    "trips": """
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY,
            description TEXT,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "expenses": """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            truck_id INTEGER,
            date TEXT
        )
    """,
    "maintenance_records": """
        CREATE TABLE IF NOT EXISTS maintenance_records (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            truck_id INTEGER,
            date TEXT NOT NULL
        )
    """,
    "tacho_driver_activity": """
        CREATE TABLE IF NOT EXISTS tacho_driver_activity (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            driver_id INTEGER,
            activity_date DATE NOT NULL
        )
    """,
}


@pytest.fixture(scope="function")
def cfg(tmp_path, monkeypatch) -> Config:
    """Alembic Config pointed at a temporary SQLite database."""
    db_path = tmp_path / "test_perf_indexes.db"
    dsn = f"sqlite:///{db_path}"
    monkeypatch.setenv("OPERION_DB_ENGINE", "postgresql")
    monkeypatch.setenv("OPERION_POSTGRES_DSN", dsn)
    cfg = Config(os.path.join(ALEMBIC_DIR, "..", "alembic.ini"))
    cfg.set_main_option("script_location", ALEMBIC_DIR)
    cfg.set_main_option("sqlalchemy.url", dsn)
    return cfg


def _create_base_tables(cfg: Config) -> str:
    url = cfg.get_main_option("sqlalchemy.url")
    assert url is not None, "sqlalchemy.url not configured"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        for ddl in BASE_TABLES_SQL.values():
            conn.execute(sa.text(ddl))
    engine.dispose()
    return url


def _index_names(url: str, table: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        insp = inspect(engine)
        return {i["name"] for i in insp.get_indexes(table) if i["name"] is not None}
    finally:
        engine.dispose()


class TestPerformanceIndexesMigration:
    def test_upgrade_creates_all_indexes(self, cfg: Config) -> None:
        url = _create_base_tables(cfg)
        command.upgrade(cfg, REV_UP)
        for name, (table, _cols) in EXPECTED_INDEXES.items():
            assert name in _index_names(url, table), (
                f"Index '{name}' missing on '{table}' after upgrade"
            )

    def test_downgrade_drops_all_indexes(self, cfg: Config) -> None:
        url = _create_base_tables(cfg)
        command.upgrade(cfg, REV_UP)
        for name, (table, _cols) in EXPECTED_INDEXES.items():
            assert name in _index_names(url, table)

        command.downgrade(cfg, REV_DOWN)
        for name, (table, _cols) in EXPECTED_INDEXES.items():
            assert name not in _index_names(url, table), (
                f"Index '{name}' still present on '{table}' after downgrade"
            )

    def test_downgrade_then_upgrade_cycle(self, cfg: Config) -> None:
        """Full cycle restores the indexes (reversible)."""
        url = _create_base_tables(cfg)
        command.upgrade(cfg, REV_UP)
        command.downgrade(cfg, REV_DOWN)
        command.upgrade(cfg, REV_UP)
        for name, (table, _cols) in EXPECTED_INDEXES.items():
            assert name in _index_names(url, table)

    def test_upgrade_is_idempotent(self, cfg: Config) -> None:
        """Second upgrade run must not raise."""
        url = _create_base_tables(cfg)
        command.upgrade(cfg, REV_UP)
        command.upgrade(cfg, REV_UP)  # IF NOT EXISTS → no-op
        for name, (table, _cols) in EXPECTED_INDEXES.items():
            assert name in _index_names(url, table)

    def test_db5_trips_driver_name_intentionally_skipped(self) -> None:
        """DB5 is not in this migration — schema.py/schema_pg.sql already
        create ``idx_trips_driver_name`` on both engines."""
        from alembic.script import ScriptDirectory

        script = ScriptDirectory(ALEMBIC_DIR)
        module = next(
            rev.module for rev in script.walk_revisions()
            if rev.revision == "k4c5d6e7f8a1"
        )
        assert all(table != "trips" for _name, table, _cols in module.INDEXES), (
            "DB5 (trips.driver_name) must NOT be added here — schema.py and "
            "schema_pg.sql already create idx_trips_driver_name at init time."
        )

    def test_db5_schema_already_declares_driver_name_index(self) -> None:
        """Read-only proof that the skipped DB5 index already exists in the
        canonical schema files for both engines."""
        schema_py = open(
            os.path.join(PROJECT_DIR, "database", "schema.py"), encoding="utf-8"
        ).read()
        schema_pg = open(
            os.path.join(PROJECT_DIR, "database", "schema_pg.sql"), encoding="utf-8"
        ).read()
        assert "idx_trips_driver_name ON trips(driver_name)" in schema_py
        assert "idx_trips_driver_name ON trips(driver_name)" in schema_pg