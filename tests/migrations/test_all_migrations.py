"""Comprehensive migration tests for all Alembic revisions.

Covers:
  - Upgrade all migrations from empty DB, verify final schema
  - Downgrade through each revision, verify schema at each step
  - Per-migration upgrade adds expected columns/tables
  - Per-migration downgrade removes them
  - Idempotency: running upgrade again is safe
  - Data preservation: migration preserves existing data

Uses SQLite for testing.  PostgreSQL-specific types are compiled
via SQLAlchemy ``@compiles`` rules so they work on SQLite.
"""

from __future__ import annotations

import datetime
import os
import sqlite3
import uuid as _uuid
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.compiler import compiles

# Note: SQLite does not support ``now()`` or ``gen_random_uuid()`` as
# server_default functions.  These defaults are fine for schema creation
# (SQLite accepts them in DDL), but INSERT statements must provide
# explicit values.  The data-preservation tests below provide explicit
# timestamps and IDs to work around this SQLite limitation.

if TYPE_CHECKING:
    pass

# ── PostgreSQL → SQLite type compilations ──────────────────────────────


@compiles(postgresql.JSONB, "sqlite")
def _compile_jsonb_sqlite(
    type_: postgresql.JSONB,
    compiler: sa.sql.compiler.SQLCompiler,
    **kw: object,
) -> str:
    """Compile postgresql.JSONB to JSON for SQLite."""
    del type_, compiler, kw
    return "JSON"


# ── Constants ───────────────────────────────────────────────────────────

PROJECT_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
ALEMBIC_DIR = os.path.join(PROJECT_DIR, "alembic")

# Each migration's metadata for parametrised tests
ALL_REVISIONS: list[dict] = [
    {
        "id": "a1b2c3d4e5f1",
        "down": None,
        "doc": "create freight_exchange_connections",
        "creates_tables": ["freight_exchange_connections"],
        "adds_columns": {},
        "indexes": ["idx_freight_connections_company"],
    },
    {
        "id": "b2c3d4e5f6a2",
        "down": "a1b2c3d4e5f1",
        "doc": "create saved_searches",
        "creates_tables": ["saved_searches"],
        "adds_columns": {},
        "indexes": ["idx_saved_searches_company", "idx_saved_searches_user"],
    },
    {
        "id": "c3d4e5f6a7b3",
        "down": "b2c3d4e5f6a2",
        "doc": "add trips source columns",
        "creates_tables": [],
        "adds_columns": {"trips": ["source", "source_provider_id", "source_reference_id"]},
        "indexes": [],
    },
    {
        "id": "d4e5f6a7b8c4",
        "down": "c3d4e5f6a7b3",
        "doc": "create copilot_audit_log",
        "creates_tables": ["copilot_audit_log"],
        "adds_columns": {},
        "indexes": ["idx_copilot_audit_company_time", "idx_copilot_audit_conversation"],
    },
    {
        "id": "e5f6a7b8c9d5",
        "down": "d4e5f6a7b8c4",
        "doc": "create conversation_summary",
        "creates_tables": ["conversation_summary"],
        "adds_columns": {},
        "indexes": ["idx_conversation_summary_company", "idx_conversation_summary_user"],
    },
    {
        "id": "f6a7b8c9d0e6",
        "down": "e5f6a7b8c9d5",
        "doc": "create copilot_reasoning_graphs",
        "creates_tables": ["copilot_reasoning_graphs"],
        "adds_columns": {},
        "indexes": [
            "idx_copilot_reasoning_company_time",
            "idx_copilot_reasoning_conversation",
            "idx_copilot_reasoning_graph_gin",
        ],
    },
    {
        "id": "a7b8c9d0e1f7",
        "down": "f6a7b8c9d0e6",
        "doc": "create copilot_insights",
        "creates_tables": ["copilot_insights"],
        "adds_columns": {},
        "indexes": ["idx_copilot_insights_company", "idx_copilot_insights_type"],
    },
    {
        "id": "a8b9c0d1e2f3",
        "down": "a7b8c9d0e1f7",
        "doc": "create documentation_chunks",
        "creates_tables": ["documentation_chunks"],
        "adds_columns": {},
        "indexes": ["idx_doc_chunks_lang", "idx_doc_chunks_article"],
    },
    {
        "id": "a9b0c1d2e3f4",
        "down": "a8b9c0d1e2f3",
        "doc": "create user_workflow_familiarity",
        "creates_tables": ["user_workflow_familiarity"],
        "adds_columns": {},
        "indexes": ["idx_user_wf_company", "idx_user_wf_user"],
    },
    {
        "id": "a9b0c1d2e3f5",
        "down": "f6a7b8c9d0e6",
        "doc": "Trans.eu Phase 1 — user tokens, freight offers, webhook tables",
        "creates_tables": [
            "trans_eu_user_tokens",
            "trans_eu_freight_offers",
            "trans_eu_webhook_events",
            "trans_eu_webhook_events_failed",
        ],
        "adds_columns": {"freight_exchange_connections": ["user_id"]},
        "indexes": [
            "idx_trans_eu_freight_offers_company",
            "idx_trans_eu_freight_offers_freight_id",
        ],
    },
    {
        "id": "f7b8c9d0e1f8",
        "down": ("a9b0c1d2e3f4", "a9b0c1d2e3f5"),
        "doc": "Financial precision — migrate monetary columns to NUMERIC",
        "creates_tables": [],
        "adds_columns": {},
        "indexes": [],
    },
    {
        "id": "g8c9d0e1f2f0",
        "down": "f7b8c9d0e1f8",
        "doc": "Datetime integrity — convert TEXT timestamps to TIMESTAMPTZ",
        "creates_tables": [],
        "adds_columns": {},
        "indexes": [],
    },
]

# Base tables that must exist before running migrations (referenced by FK / ADD COLUMN)
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
}

# Expected column sets for tables created by migrations.
# Note: ``trips`` is a base table, not migration-created.
EXPECTED_COLUMNS: dict[str, set[str]] = {
    "freight_exchange_connections": {
        "id", "company_id", "provider_id", "credentials_encrypted",
        "session_state", "status", "last_health_check_at",
        "last_health_check_status", "connected_at", "created_at",
    },
    "saved_searches": {
        "id", "company_id", "user_id", "label", "filters",
        "provider_ids", "created_at", "last_refreshed_at",
    },
    "trips": {
        "id", "description", "status", "created_at",
        "source", "source_provider_id", "source_reference_id",
    },
    "copilot_audit_log": {
        "id", "company_id", "user_id", "conversation_id", "plan_id",
        "step_id", "tool_name", "tool_version", "parameters",
        "permission_checked", "permission_granted", "confidence_score",
        "confirmation_level", "status", "result", "error", "model_used",
        "provider_id", "prompt_version", "execution_time_ms",
        "started_at", "finished_at", "created_at", "corrects_audit_id",
    },
    "conversation_summary": {
        "id", "company_id", "user_id", "started_at", "ended_at",
        "turn_count", "outcome", "pinned_provider_id", "pinned_model_id",
        "pinned_prompt_version", "created_at",
    },
    "copilot_reasoning_graphs": {
        "id", "company_id", "conversation_id", "plan_id", "status",
        "root_node_id", "graph", "created_at", "finalized_at",
    },
    "copilot_insights": {
        "id", "company_id", "insight_type", "payload", "severity",
        "status", "created_at", "read_at", "dismissed_at",
    },
    "documentation_chunks": {
        "id", "article_id", "title_key", "content", "language",
        "embedding", "corpus_version", "created_at", "updated_at",
    },
    "user_workflow_familiarity": {
        "id", "company_id", "user_id", "workflow_id",
        "times_completed", "last_completed_at", "familiarity_level",
    },
    "trans_eu_user_tokens": {
        "id", "company_id", "user_id", "trans_eu_account_id",
        "access_token_encrypted", "refresh_token_encrypted", "scope",
        "expires_at", "api_key_encrypted", "client_id",
        "client_secret_encrypted", "status", "connected_at",
        "last_used_at", "last_refreshed_at",
    },
    "trans_eu_freight_offers": {
        "id", "company_id", "user_id", "trans_eu_freight_id",
        "trans_eu_reference_number", "status", "publication_status",
        "publication_type", "origin", "destination", "pickup_from",
        "pickup_to", "delivery_from", "delivery_to", "price_amount",
        "price_currency", "distance_km", "trailer_type", "adr",
        "weight_kg", "raw_payload", "externally_modified_at",
        "operion_trip_id", "trans_eu_order_id", "created_at", "updated_at",
    },
    "trans_eu_webhook_events": {
        "id", "company_id", "trans_eu_event_id", "event_name",
        "occurred_at", "payload", "status", "processed_at",
        "error_message", "created_at",
    },
    "trans_eu_webhook_events_failed": {
        "id", "company_id", "trans_eu_event_id", "event_name",
        "payload", "error_message", "error_type", "attempt_count",
        "max_attempts", "next_retry_at", "status", "created_at",
    },
}


# ── SQLite compatibility ────────────────────────────────────────────────
# SQLite does not support ALTER TABLE ADD COLUMN with a FOREIGN KEY
# constraint.  We make Alembic's SQLite DDL impl a no-op for constraint
# addition so that the column itself is still added successfully.


def _patch_sqlite_add_constraint() -> None:
    """Make ``SqliteImpl.add_constraint`` a no-op.

    This allows ADD COLUMN with ForeignKey to work on SQLite — the
    constraint is silently dropped, but the column itself is created.
    """
    import alembic.ddl.sqlite as _ddl_sqlite

    def _noop(self: object, constraint: object) -> None:
        pass  # silently drop the constraint

    _ddl_sqlite.SQLiteImpl.add_constraint = _noop


_patch_sqlite_add_constraint()


# ── Helpers ─────────────────────────────────────────────────────────────


def _get_alembic_url(cfg: Config) -> str:
    url = cfg.get_main_option("sqlalchemy.url")
    assert url is not None, "sqlalchemy.url not configured"
    return url


def _ensure_base_tables(cfg: Config) -> str:
    """Create base tables (companies, users, trips) so FK / ADD COLUMN work."""
    url = _get_alembic_url(cfg)
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        for ddl in BASE_TABLES_SQL.values():
            conn.execute(sa.text(ddl))
    engine.dispose()
    return url


def _tables(url: str) -> set[str]:
    """Return set of table names in the database."""
    engine = sa.create_engine(url)
    try:
        insp = inspect(engine)
        return set(insp.get_table_names())
    finally:
        engine.dispose()


def _columns(url: str, table: str) -> set[str]:
    """Return set of column names for *table*."""
    engine = sa.create_engine(url)
    try:
        insp = inspect(engine)
        cols = insp.get_columns(table)
        return {c["name"] for c in cols}
    finally:
        engine.dispose()


def _indexes(url: str, table: str) -> set[str]:
    """Return set of index names for *table*."""
    engine = sa.create_engine(url)
    try:
        insp = inspect(engine)
        idxs = insp.get_indexes(table)
        return {i["name"] for i in idxs if i["name"] is not None}
    finally:
        engine.dispose()


def _count_rows(url: str, table: str) -> int:
    engine = sa.create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(sa.text(f"SELECT COUNT(*) FROM {table}"))
        return result.scalar()  # type: ignore[union-attr]


def _find_index_table(url: str, idx_name: str) -> str | None:
    """Return the table name that owns the given index, or None.

    Only searches tables that actually exist in the database.
    """
    existing = _tables(url)
    for known_tbl in list(EXPECTED_COLUMNS.keys()) + list(BASE_TABLES_SQL.keys()):
        if known_tbl not in existing:
            continue
        if idx_name in _indexes(url, known_tbl):
            return known_tbl
    return None


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def alembic_config(tmp_path, monkeypatch) -> Config:
    """Create an Alembic Config pointed at a temporary SQLite database.

    The project's ``env.py`` determines the DB URL dynamically via
    ``get_url()``, which checks ``OPERION_DB_ENGINE`` then
    ``OPERION_POSTGRES_DSN``.  We set those env vars to force the
    SQLite path we control.
    """
    db_path = tmp_path / "test_migrations.db"
    dsn = f"sqlite:///{db_path}"
    monkeypatch.setenv("OPERION_DB_ENGINE", "postgresql")
    monkeypatch.setenv("OPERION_POSTGRES_DSN", dsn)
    cfg = Config(os.path.join(ALEMBIC_DIR, "..", "alembic.ini"))
    cfg.set_main_option("script_location", ALEMBIC_DIR)
    cfg.set_main_option("sqlalchemy.url", dsn)
    return cfg


@pytest.fixture(scope="function")
def db_url(alembic_config: Config) -> str:
    """Database URL from the alembic config."""
    return _get_alembic_url(alembic_config)


@pytest.fixture(scope="function")
def db_with_base_tables(alembic_config: Config, db_url: str) -> str:
    """Create base tables on a fresh database."""
    _ensure_base_tables(alembic_config)
    return db_url


@pytest.fixture(scope="function")
def migrated_db(alembic_config: Config, db_with_base_tables: str) -> str:
    """Apply all migrations up to heads, returning the DB path."""
    command.upgrade(alembic_config, "heads")
    return db_with_base_tables


# ═══════════════════════════════════════════════════════════════════════
#  Upgrade All
# ═══════════════════════════════════════════════════════════════════════


class TestUpgradeAll:
    """Apply ALL migrations from empty DB and verify final schema."""

    def test_all_migration_tables_exist(
        self, alembic_config: Config, migrated_db: str,
    ) -> None:
        url = _get_alembic_url(alembic_config)
        tables = _tables(url)

        expected = set(EXPECTED_COLUMNS.keys())
        missing = expected - tables
        assert not missing, f"Missing migration-created tables: {missing}"

    def test_all_expected_columns_present(
        self, alembic_config: Config, migrated_db: str,
    ) -> None:
        url = _get_alembic_url(alembic_config)
        for table, expected_cols in EXPECTED_COLUMNS.items():
            actual = _columns(url, table)
            missing = expected_cols - actual
            assert not missing, (
                f"Table '{table}' missing columns: {missing}"
            )

    def test_alembic_version_table_exists(
        self, alembic_config: Config, migrated_db: str,
    ) -> None:
        url = _get_alembic_url(alembic_config)
        tables = _tables(url)
        assert "alembic_version" in tables, (
            "alembic_version table missing after upgrade"
        )

    def test_alembic_version_has_correct_revision(
        self, alembic_config: Config, migrated_db: str,
    ) -> None:
        url = _get_alembic_url(alembic_config)
        engine = sa.create_engine(url)
        with engine.connect() as conn:
            result = conn.execute(
                sa.text("SELECT version_num FROM alembic_version")
            )
            version = result.scalar()
        engine.dispose()
        assert version is not None, "alembic_version is empty"
        # The sole head is g8c9d0e1f2f0
        assert version == "g8c9d0e1f2f0", (
            f"Unexpected alembic_version: {version}"
        )

    def test_all_indexes_present(
        self, alembic_config: Config, migrated_db: str,
    ) -> None:
        url = _get_alembic_url(alembic_config)
        built_indexes: set[str] = set()
        for table in _tables(url):
            built_indexes.update(_indexes(url, table))
        for rev in ALL_REVISIONS:
            for idx in rev["indexes"]:
                assert idx in built_indexes, f"Index '{idx}' not found after full upgrade"


# ═══════════════════════════════════════════════════════════════════════
#  Downgrade All
# ═══════════════════════════════════════════════════════════════════════


class TestDowngradeAll:
    """Go down through each revision and verify schema is correct."""

    def test_full_downgrade_to_base_removes_all_migration_tables(
        self, alembic_config: Config, db_url: str,
    ) -> None:
        _ensure_base_tables(alembic_config)
        command.upgrade(alembic_config, "heads")
        assert "freight_exchange_connections" in _tables(db_url)

        command.downgrade(alembic_config, "base")
        tables = _tables(db_url)
        # Only check migration-created tables, not base tables
        for table in EXPECTED_COLUMNS:
            if table in BASE_TABLES_SQL:
                continue  # trips is a base table, not migration-created
            assert table not in tables, (
                f"Table '{table}' still exists after full downgrade"
            )

    def test_full_downgrade_preserves_base_tables(
        self, alembic_config: Config, db_url: str,
    ) -> None:
        _ensure_base_tables(alembic_config)
        command.upgrade(alembic_config, "heads")
        command.downgrade(alembic_config, "base")
        tables = _tables(db_url)
        for table in BASE_TABLES_SQL:
            assert table in tables, f"Base table '{table}' removed by downgrade"

    def test_alembic_version_empty_after_downgrade(
        self, alembic_config: Config, db_url: str,
    ) -> None:
        """After downgrade to base, alembic_version is empty (no rows)."""
        _ensure_base_tables(alembic_config)
        command.upgrade(alembic_config, "heads")
        command.downgrade(alembic_config, "base")
        engine = sa.create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(
                sa.text("SELECT COUNT(*) FROM alembic_version")
            )
            count = result.scalar()
        engine.dispose()
        assert count == 0, (
            f"alembic_version has {count} rows after full downgrade "
            f"(expected 0)"
        )

    def test_downgrade_is_idempotent(
        self, alembic_config: Config, db_url: str,
    ) -> None:
        """Calling downgrade to base twice is safe."""
        _ensure_base_tables(alembic_config)
        command.upgrade(alembic_config, "heads")
        command.downgrade(alembic_config, "base")
        command.downgrade(alembic_config, "base")  # second call
        # Should not raise


# ═══════════════════════════════════════════════════════════════════════
#  Per-Migration: Upgrade
# ═══════════════════════════════════════════════════════════════════════


class TestPerMigrationUpgrade:
    """Each migration adds the expected tables/columns when upgraded."""

    @pytest.mark.parametrize(
        "rev_info",
        ALL_REVISIONS,
        ids=[r["id"] for r in ALL_REVISIONS],
    )
    def test_upgrade_adds_expected_schema(
        self,
        alembic_config: Config,
        db_url: str,
        rev_info: dict,
    ) -> None:
        # Each parametrised invocation gets its own tmp_path → fresh database
        _ensure_base_tables(alembic_config)

        # Upgrade to this specific revision (Alembic applies ancestors)
        command.upgrade(alembic_config, rev_info["id"])

        # ── Verify tables were created ───────────────────────────────
        tables = _tables(db_url)
        for tbl in rev_info["creates_tables"]:
            assert tbl in tables, (
                f"Migration {rev_info['id']} should create table "
                f"'{tbl}' but it's missing"
            )
            actual_cols = _columns(db_url, tbl)
            expected_cols = EXPECTED_COLUMNS.get(tbl, set())
            missing_cols = expected_cols - actual_cols
            assert not missing_cols, (
                f"Table '{tbl}' created by {rev_info['id']} is "
                f"missing columns: {missing_cols}"
            )

        # ── Verify columns were added to existing tables ─────────────
        for tbl, col_list in rev_info["adds_columns"].items():
            actual_cols = _columns(db_url, tbl)
            for col in col_list:
                assert col in actual_cols, (
                    f"Migration {rev_info['id']} should add column "
                    f"'{col}' to '{tbl}'"
                )

        # ── Verify indexes exist ─────────────────────────────────────
        for idx in rev_info["indexes"]:
            owner = _find_index_table(db_url, idx)
            assert owner is not None, (
                f"Index '{idx}' not found after migration {rev_info['id']}"
            )


# ═══════════════════════════════════════════════════════════════════════
#  Per-Migration: Downgrade
# ═══════════════════════════════════════════════════════════════════════


class TestPerMigrationDowngrade:
    """Each migration removes the expected tables/columns when downgraded."""

    @pytest.mark.parametrize(
        "rev_info",
        ALL_REVISIONS,
        ids=[r["id"] for r in ALL_REVISIONS],
    )
    def test_downgrade_removes_schema(
        self,
        alembic_config: Config,
        db_url: str,
        rev_info: dict,
    ) -> None:
        _ensure_base_tables(alembic_config)

        # Upgrade to this revision
        command.upgrade(alembic_config, rev_info["id"])

        # Verify the schema IS present before downgrade
        for tbl in rev_info["creates_tables"]:
            assert tbl in _tables(db_url), (
                f"Table '{tbl}' should exist before downgrade"
            )

        # Downgrade one step (to parent revision or base)
        target = rev_info["down"] or "base"
        if isinstance(target, tuple):
            target = target[0]  # merge revision: use first parent
        command.downgrade(alembic_config, target)

        # ── Verify tables were removed ───────────────────────────────
        tables_after = _tables(db_url)
        for tbl in rev_info["creates_tables"]:
            assert tbl not in tables_after, (
                f"Table '{tbl}' still exists after downgrade "
                f"from {rev_info['id']}"
            )

        # ── Verify columns were removed ──────────────────────────────
        for tbl, col_list in rev_info["adds_columns"].items():
            if tbl in _tables(db_url):
                actual_cols = _columns(db_url, tbl)
                for col in col_list:
                    assert col not in actual_cols, (
                        f"Column '{col}' still exists in '{tbl}' "
                        f"after downgrade from {rev_info['id']}"
                    )


# ═══════════════════════════════════════════════════════════════════════
#  Idempotency
# ═══════════════════════════════════════════════════════════════════════


class TestIdempotency:
    """Running upgrade again is safe (no-op)."""

    def test_upgrade_twice_is_safe(
        self, alembic_config: Config, migrated_db: str,
    ) -> None:
        """Running ``alembic upgrade head`` a second time should not raise."""
        command.upgrade(alembic_config, "heads")
        url = _get_alembic_url(alembic_config)
        tables = _tables(url)
        for table in EXPECTED_COLUMNS:
            assert table in tables, f"Table '{table}' missing after second upgrade"

    def test_downgrade_then_upgrade_cycle(
        self, alembic_config: Config, db_url: str,
    ) -> None:
        """Downgrade to base then upgrade to head — full cycle."""
        _ensure_base_tables(alembic_config)
        command.upgrade(alembic_config, "heads")
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "heads")

        for table in EXPECTED_COLUMNS:
            assert table in _tables(db_url), (
                f"Table '{table}' missing after downgrade-upgrade cycle"
            )

    def test_multiple_downgrade_upgrade_cycles(
        self, alembic_config: Config, db_url: str,
    ) -> None:
        """Three full downgrade-upgrade cycles."""
        _ensure_base_tables(alembic_config)
        for _ in range(3):
            command.upgrade(alembic_config, "heads")
            command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "heads")
        for table in EXPECTED_COLUMNS:
            assert table in _tables(db_url), (
                f"Table '{table}' missing after multiple cycles"
            )


# ═══════════════════════════════════════════════════════════════════════
#  Data Preservation
# ═══════════════════════════════════════════════════════════════════════


class TestDataPreservation:
    """Migrations preserve existing data."""

    def _insert_seed_data(self, url: str) -> dict[str, list[dict]]:
        """Insert rows into a few migration-created tables.

        Provides explicit timestamps to avoid SQLite's lack of ``now()``.
        """
        engine = sa.create_engine(url)
        data: dict[str, list[dict]] = {}
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with engine.begin() as conn:
            row_id = str(_uuid.uuid4())
            conn.execute(
                sa.text("""
                    INSERT INTO freight_exchange_connections
                        (id, company_id, provider_id, credentials_encrypted,
                         session_state, status, created_at)
                    VALUES
                        (:id, 1, 'test_provider', 'encrypted',
                         '{}', 'connected', :ts)
                """),
                {"id": row_id, "ts": now_str},
            )
            data["freight_exchange_connections"] = [{"id": row_id}]

            search_id = str(_uuid.uuid4())
            conn.execute(
                sa.text("""
                    INSERT INTO saved_searches
                        (id, company_id, user_id, label, filters, created_at)
                    VALUES
                        (:id, 1, 1, 'test_search', '{}', :ts)
                """),
                {"id": search_id, "ts": now_str},
            )
            data["saved_searches"] = [{"id": search_id}]
        engine.dispose()
        return data

    def test_data_preserved_across_upgrade(
        self, alembic_config: Config, db_url: str,
    ) -> None:
        """Data in truck table survives ADD COLUMN migrations."""
        _ensure_base_tables(alembic_config)
        # Upgrade to just before the ADD COLUMN migration for trips
        command.upgrade(alembic_config, "b2c3d4e5f6a2")

        # Seed a row in the trips table (which exists as a base table)
        engine = sa.create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO trips (description, status) "
                    "VALUES ('preserve-test', 'draft')"
                )
            )
        engine.dispose()

        # Apply ADD COLUMN migration on trips
        command.upgrade(alembic_config, "c3d4e5f6a7b3")
        assert _count_rows(db_url, "trips") == 1, (
            "Data lost after ADD COLUMN migration"
        )

    def test_data_preserved_across_downgrade_upgrade(
        self, alembic_config: Config, db_url: str,
    ) -> None:
        """Data in base tables survives downgrade+upgrade cycle.

        Note: data in migration-created tables is lost when those
        tables are dropped during downgrade and recreated.  Data
        in base tables (not managed by Alembic) is preserved.
        """
        _ensure_base_tables(alembic_config)

        # Seed data in base table before any migration
        engine = sa.create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO trips (description, status) "
                    "VALUES ('base-data', 'draft')"
                )
            )
        engine.dispose()

        command.upgrade(alembic_config, "heads")
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "heads")

        # Base table data should survive
        assert _count_rows(db_url, "trips") == 1, (
            "Base table data lost after downgrade+upgrade"
        )

    def test_add_column_preserves_existing_rows(
        self, alembic_config: Config, db_url: str,
    ) -> None:
        """Adding columns to an existing table does not delete its rows."""
        _ensure_base_tables(alembic_config)
        command.upgrade(alembic_config, "b2c3d4e5f6a2")

        engine = sa.create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO trips (description, status) "
                    "VALUES ('preserve-test', 'draft')"
                )
            )
        engine.dispose()

        command.upgrade(alembic_config, "c3d4e5f6a7b3")
        assert _count_rows(db_url, "trips") == 1, (
            "Row count changed after ADD COLUMN migration"
        )

    def test_data_survives_branch_downgrade(
        self, alembic_config: Config, db_url: str,
    ) -> None:
        """Data in base table survives branch downgrade."""
        _ensure_base_tables(alembic_config)
        command.upgrade(alembic_config, "heads")

        # Seed a row in the trips base table
        engine = sa.create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO trips (description, status) "
                    "VALUES ('branch-test', 'active')"
                )
            )
        engine.dispose()

        # Downgrade past the branch point
        command.downgrade(alembic_config, "f6a7b8c9d0e6")

        # trips is a base table, so it should still exist with data
        assert _count_rows(db_url, "trips") == 1, (
            "Base table data lost after branch downgrade"
        )

        # Upgrade back
        command.upgrade(alembic_config, "heads")
        assert _count_rows(db_url, "trips") == 1, (
            "Base table data lost after branch re-upgrade"
        )


# ═══════════════════════════════════════════════════════════════════════
#  Revision Chain Integrity
# ═══════════════════════════════════════════════════════════════════════


class TestRevisionChain:
    """Verify migration chain integrity (revision IDs, parent links)."""

    def test_all_revisions_have_valid_down_revision(self) -> None:
        """Every revision's down_revision references an existing revision or None."""
        rev_map = {r["id"]: r for r in ALL_REVISIONS}
        for rev in ALL_REVISIONS:
            if rev["down"] is not None:
                down = rev["down"]
                if isinstance(down, tuple):
                    assert all(d in rev_map for d in down), (
                        f"Revision {rev['id']} has down_revision "
                        f"{down} where not all parents are in the migration set"
                    )
                else:
                    assert down in rev_map, (
                        f"Revision {rev['id']} has down_revision "
                        f"{down} which is not in the migration set"
                    )

    def test_revision_ids_are_unique(self) -> None:
        ids = [r["id"] for r in ALL_REVISIONS]
        assert len(ids) == len(set(ids)), "Duplicate revision IDs found"

    def test_heads_match_expected(self) -> None:
        """The heads in the migration directory match expected heads."""
        from alembic.script import ScriptDirectory

        script = ScriptDirectory(ALEMBIC_DIR)
        heads = set(script.get_heads())
        expected_heads = {"g8c9d0e1f2f0"}
        assert heads == expected_heads, (
            f"Expected heads {expected_heads}, got {heads}"
        )

    def test_revision_count_matches(self) -> None:
        """Number of revisions in the directory matches our metadata."""
        from alembic.script import ScriptDirectory

        script = ScriptDirectory(ALEMBIC_DIR)
        revisions = list(script.walk_revisions())
        assert len(revisions) == len(ALL_REVISIONS), (
            f"Expected {len(ALL_REVISIONS)} revisions, "
            f"found {len(revisions)} in directory"
        )

    def test_all_revisions_have_upgrade_and_downgrade(self) -> None:
        """Every revision module has upgrade() and downgrade() functions."""
        from alembic.script import ScriptDirectory

        script = ScriptDirectory(ALEMBIC_DIR)
        for rev in script.walk_revisions():
            module = rev.module
            assert hasattr(module, "upgrade") and callable(module.upgrade), (
                f"Revision {rev.revision} missing upgrade()"
            )
            assert hasattr(module, "downgrade") and callable(module.downgrade), (
                f"Revision {rev.revision} missing downgrade()"
            )
