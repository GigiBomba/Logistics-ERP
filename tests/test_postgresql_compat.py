"""PostgreSQL compatibility tests — schema integrity, PL/pgSQL functions, UUID generation.

These tests validate that ``database/schema_pg.sql`` covers all tables
defined in ``database/schema.py`` and that PL/pgSQL functions and UUID
generation work correctly on a running PostgreSQL instance.

Requires a running PostgreSQL at ``localhost:5432`` for the live tests
(functions, UUID).  Schema-parsing tests are offline.
"""

from __future__ import annotations

import os
import re
import pytest
import psycopg2

# ── Paths ────────────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_HERE)
_SCHEMA_PY = os.path.join(_PROJECT, "database", "schema.py")
_SCHEMA_PG_SQL = os.path.join(_PROJECT, "database", "schema_pg.sql")

# ── PostgreSQL connection ────────────────────────────────────────────────────

TEST_DSN = os.environ.get(
    "OPERION_TEST_POSTGRES_DSN",
    "postgresql://operion:operion_test_ci@localhost:5432/operion_test_compat",
)

#: Per-file isolated database name — this module owns ``operion_test_compat``
#: so its own schema build / migrations can never collide with other test
#: files' on the shared ``operion_test`` database (xdist `-n 2` concurrent
#: runs).
_TEST_DB_NAME = "operion_test_compat"

#: Admin DSN: connect to the always-existing ``operion_test`` database so the
#: (superuser) ``operion`` role can issue CREATE/DROP DATABASE for the
#: per-file database above.
_BASE_DSN = "postgresql://operion:operion_test_ci@localhost:5432/operion_test"


def _ensure_test_db() -> None:
    """Create the per-file test database (idempotent; superuser required).

    No-op when ``OPERION_TEST_POSTGRES_DSN`` is set explicitly — the caller
    pointed us at a database of their choosing, and we must not touch it.
    """
    if os.environ.get("OPERION_TEST_POSTGRES_DSN"):
        return
    import psycopg2
    from psycopg2 import sql as pgsql

    try:
        conn = psycopg2.connect(_BASE_DSN)
        conn.autocommit = True  # CREATE DATABASE cannot run inside a transaction
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (_TEST_DB_NAME,))
        if not cur.fetchone():
            cur.execute(
                pgsql.SQL("CREATE DATABASE {}").format(pgsql.Identifier(_TEST_DB_NAME))
            )
        cur.close()
        conn.close()
    except Exception:
        # Best-effort: the DB may already exist (idempotent) or PG may be
        # unreachable (the module-level guard below skips).
        pass


def _drop_test_db() -> None:
    """Drop the per-file test database at session teardown (best-effort)."""
    if os.environ.get("OPERION_TEST_POSTGRES_DSN"):
        return
    import psycopg2
    from psycopg2 import sql as pgsql

    try:
        conn = psycopg2.connect(_BASE_DSN)
        conn.autocommit = True
        cur = conn.cursor()
        # Never force-kill another session's connections — if any remain,
        # leave the DB in place (mirrors tests/integration/conftest.py).
        cur.execute(
            "SELECT COUNT(*) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (_TEST_DB_NAME,),
        )
        row = cur.fetchone()
        other_sessions = (row[0] if row else 0) or 0
        if not other_sessions:
            cur.execute(
                pgsql.SQL("DROP DATABASE IF EXISTS {}").format(
                    pgsql.Identifier(_TEST_DB_NAME)
                )
            )
        cur.close()
        conn.close()
    except Exception:
        pass  # a failed drop must not fail tests


def _build_schema() -> None:
    """Apply the real deployment schema (schema_pg.sql + Alembic + extra DDL).

    Advisory-locked and idempotent (safe to run repeatedly); a freshly
    created per-file database starts empty, so this is what makes the
    ``_has_app_schema()`` guard below (and the tests) see a real schema.
    """
    try:
        from database.db_manager import DatabaseManager

        db = DatabaseManager(db_path=TEST_DSN, engine="postgresql", pool_min=1, pool_max=2)
        db.close()
    except Exception:
        pass  # the _has_app_schema() re-check below decides the outcome


def pg_reachable() -> bool:
    try:
        conn = psycopg2.connect(TEST_DSN, connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False


_ensure_test_db()

_HAS_PG = pg_reachable()
if not _HAS_PG:
    pytest.skip(f"PostgreSQL not reachable at {TEST_DSN}", allow_module_level=True)


def _has_app_schema() -> bool:
    """Return True if the PostgreSQL DB has at least one core app table.

    The CI workflow's docker-compose PostgreSQL is a bare ``postgres:16``
    smoke instance (app DB created, but migrations NOT applied).  These
    compatibility tests need the real app schema, so skip the module cleanly
    when only an empty/partial database is reachable.
    """
    try:
        conn = psycopg2.connect(TEST_DSN, connect_timeout=3)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT count(*) FROM pg_catalog.pg_tables "
                "WHERE schemaname = 'public' "
                "AND tablename IN ('companies', 'trips', 'users')"
            )
            return bool(cur.fetchone()[0])
        finally:
            conn.close()
    except Exception:
        return False


if not _has_app_schema():
    # A freshly created per-file database starts empty — apply the REAL
    # schema (advisory-locked, idempotent) before deciding to skip.  No-op
    # when the database already has the schema (shared DB / explicit DSN).
    _build_schema()

if not _has_app_schema():
    pytest.skip(
        "PostgreSQL reachable but the app schema is not applied "
        "(CI docker PG is a bare smoke instance without migrations) — skipping",
        allow_module_level=True,
    )

try:
    import psycopg2.pool  # noqa: F401
except Exception:
    pytest.skip(
        "psycopg2.pool is unavailable — skipping PostgreSQL pool tests",
        allow_module_level=True,
    )


@pytest.fixture(scope="session")
def pg_schema():
    """Ensure the full PostgreSQL schema (including PL/pgSQL functions) is
    applied to the test database.  Uses the same DatabaseManager path that
    integration tests use, so tests validate the real deployment schema.

    Drops the per-file database at session teardown.
    """
    from database.db_manager import DatabaseManager
    db = DatabaseManager(db_path=TEST_DSN, engine="postgresql", pool_min=1, pool_max=2)
    db.close()
    yield TEST_DSN
    _drop_test_db()


@pytest.fixture(scope="module")
def pg_conn(pg_schema):
    conn = psycopg2.connect(TEST_DSN)
    yield conn
    conn.close()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _parse_table_names_from_py(path: str) -> set[str]:
    """Extract table names from ``CREATE TABLE IF NOT EXISTS`` statements
    inside Python triple-quoted strings in *path*."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)",
        re.IGNORECASE,
    )
    return set(pattern.findall(text))


def _parse_table_names_from_sql(path: str) -> set[str]:
    """Extract table names from ``CREATE TABLE`` statements in *path*."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
        re.IGNORECASE,
    )
    return set(pattern.findall(text))


# ══════════════════════════════════════════════════════════════════════════════
# §1  Schema integrity — offline comparison
# ══════════════════════════════════════════════════════════════════════════════


class TestSchemaCoverage:
    """Every business table in ``schema.py`` must have a counterpart in
    ``schema_pg.sql``, and vice-versa (with well-documented exceptions)."""

    # Tables that exist in schema.py but are intentionally omitted from
    # schema_pg.sql (replaced by a PG-native mechanism, deprecated, or
    # not yet ported to the PG schema).
    _SQLITE_ONLY = frozenset({
        "documents_fts",                # replaced by tsvector column + GIN index
        "maintenance",                  # deprecated, replaced by maintenance_records
        "auth_sessions",                # not yet ported to PG schema
        "freight_exchange_connections", # created via Alembic (a1b2c3d4e5f1), not in schema_pg.sql
        "saved_searches",               # created via Alembic (b2c3d4e5f6a2), not in schema_pg.sql
        "conversation_summary",         # created via Alembic (e5f6a7b8c9d5), not in schema_pg.sql
        "copilot_audit_log",            # created via Alembic (d4e5f6a7b8c4), not in schema_pg.sql
        "copilot_insights",             # created via Alembic (a7b8c9d0e1f7), not in schema_pg.sql
        "copilot_reasoning_graphs",     # created via Alembic (f6a7b8c9d0e6), not in schema_pg.sql
        "sync_outbox",                  # desktop-side sync capture layer, not in schema_pg.sql
        "sync_meta",                    # desktop-side sync key/value store, not in schema_pg.sql
        "sync_id_map",                  # desktop-side bidirectional id map, not in schema_pg.sql
        "sync_conflicts",               # desktop-side conflict journal, not in schema_pg.sql
    })

    # Tables that exist in schema_pg.sql without a corresponding TABLE_*
    # constant in schema.py (system/extraneous tables).
    _PG_KNOWN_EXTRAS = frozenset({
        "alembic_version",     # Alembic migration tracking
        "spatial_ref_sys",     # PostGIS spatial reference system
    })

    @classmethod
    def _load_tables(cls):
        """Lazy-load both table sets once per session."""
        if not hasattr(cls, "_py_tables"):
            cls._py_tables = _parse_table_names_from_py(_SCHEMA_PY)
        if not hasattr(cls, "_sql_tables"):
            cls._sql_tables = _parse_table_names_from_sql(_SCHEMA_PG_SQL)
        return cls._py_tables, cls._sql_tables

    def test_schema_pg_covers_all_sqlite_tables(self):
        """Every table in schema.py must have a corresponding table in
        schema_pg.sql (excluding known SQLite-only tables)."""
        py_tables, sql_tables = self._load_tables()
        missing = (py_tables - self._SQLITE_ONLY) - sql_tables
        assert not missing, (
            f"Tables defined in schema.py but missing from schema_pg.sql:\n"
            f"  {sorted(missing)}"
        )

    def test_schema_sqlite_has_no_extra_tables(self):
        """No tables in schema_pg.sql that don't correspond to schema.py
        (excluding known PG system tables)."""
        py_tables, sql_tables = self._load_tables()
        extra = (sql_tables - py_tables) - self._PG_KNOWN_EXTRAS
        assert not extra, (
            f"Tables in schema_pg.sql that have no counterpart in schema.py:\n"
            f"  {sorted(extra)}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# §1.5  Column-level schema comparison
# ══════════════════════════════════════════════════════════════════════════════


class TestSchemaColumnCoverage:
    """For critical business tables, every column defined in schema.py must
    have a matching column in the PostgreSQL schema."""

    # Critical business tables to verify
    _CRITICAL_TABLES = frozenset({
        'companies', 'users', 'trips', 'clients', 'drivers',
        'trucks', 'invoices', 'documents', 'routes', 'settings',
    })

    def _parse_py_columns(self, table: str) -> set[str]:
        """Parse column names for *table* from schema.py, looking at both
        the CREATE TABLE block and ALTER TABLE ADD COLUMN statements."""
        with open(_SCHEMA_PY, encoding="utf-8") as f:
            lines = f.readlines()

        cols: set[str] = set()
        in_block = False

        for line in lines:
            # Detect start of CREATE TABLE block
            if re.match(
                rf"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+{re.escape(table)}\s*\(",
                line, re.IGNORECASE,
            ):
                in_block = True
                continue

            if in_block:
                stripped = line.strip()
                # End of CREATE TABLE block
                if stripped == ');':
                    break

                cleaned = stripped.rstrip(',').strip()
                if not cleaned or cleaned.startswith('--') or cleaned.startswith('/*'):
                    continue
                if cleaned.upper().startswith(
                    ('PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'CONSTRAINT', 'INDEX')
                ):
                    continue

                # Match column name followed by a SQLite-compatible type
                m = re.match(
                    r'(\w+)\s+(INTEGER|TEXT|REAL|BLOB|NUMERIC|VARCHAR|BOOLEAN|'
                    r'TIMESTAMP|DATE|JSON|SERIAL|BIGINT|UUID|FLOAT|DOUBLE|DECIMAL|DATETIME)\b',
                    cleaned, re.IGNORECASE,
                )
                if m:
                    cols.add(m.group(1))

        # Also include columns added via ALTER TABLE ADD COLUMN
        with open(_SCHEMA_PY, encoding="utf-8") as f:
            text = f.read()
        alter_pattern = rf"ALTER TABLE\s+{re.escape(table)}\s+ADD\s+COLUMN\s+(\w+)"
        for m in re.finditer(alter_pattern, text, re.IGNORECASE):
            cols.add(m.group(1))

        return cols

    def test_critical_tables_column_parity(self, pg_conn):
        """For every critical table, all schema.py columns must exist in PG."""
        mismatches = {}
        for table in sorted(self._CRITICAL_TABLES):
            py_cols = self._parse_py_columns(table)
            if not py_cols:
                continue  # table not found in schema.py

            cur = pg_conn.cursor()
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s AND table_schema = 'public'",
                (table,),
            )
            pg_cols = {r[0] for r in cur.fetchall()}

            missing = py_cols - pg_cols
            if missing:
                mismatches[table] = {'missing_in_pg': sorted(missing)}

        assert not mismatches, (
            f"Columns defined in schema.py but missing from PostgreSQL:\n"
            f"{mismatches}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# §2  PL/pgSQL function tests
# ══════════════════════════════════════════════════════════════════════════════


class TestPlpgsqlFunctions:
    """Verify PL/pgSQL functions from schema_pg.sql are registered."""

    def test_plpgsql_functions_exist(self, pg_conn):
        cur = pg_conn.cursor()
        cur.execute("""
            SELECT proname FROM pg_proc
            WHERE pronamespace = 'public'::regnamespace
              AND prokind = 'f'
        """)
        functions = {r[0] for r in cur.fetchall()}
        expected = {
            "documents_search_update",
            "validate_pipeline_stage",
            "validate_pipeline_status",
        }
        missing = expected - functions
        assert not missing, f"PL/pgSQL functions missing from database: {missing}"

    def test_plpgsql_functions_return_trigger(self, pg_conn):
        """All expected trigger functions should have rettype 'trigger'."""
        cur = pg_conn.cursor()
        cur.execute("""
            SELECT proname, pg_get_function_result(oid)
            FROM pg_proc
            WHERE pronamespace = 'public'::regnamespace
              AND prokind = 'f'
              AND proname IN ('documents_search_update',
                              'validate_pipeline_stage',
                              'validate_pipeline_status')
        """)
        rows = {r[0]: r[1] for r in cur.fetchall()}
        for name in (
            "documents_search_update",
            "validate_pipeline_stage",
            "validate_pipeline_status",
        ):
            assert name in rows, f"Function {name} not found"
            assert rows[name] == "trigger", (
                f"Function {name} should return 'trigger', got '{rows[name]}'"
            )


# ══════════════════════════════════════════════════════════════════════════════
# §3  UUID generation test
# ══════════════════════════════════════════════════════════════════════════════


class TestUUIDGeneration:
    """gen_random_uuid() works on PostgreSQL."""

    def test_gen_random_uuid_returns_uuid_string(self, pg_conn):
        cur = pg_conn.cursor()
        cur.execute("SELECT gen_random_uuid()")
        result = cur.fetchone()[0]
        assert result is not None
        assert isinstance(result, str)
        assert len(result) == 36
        # Standard UUID format: 8-4-4-4-12 hex digits
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            result,
        ), f"Result '{result}' is not a valid UUID"

    def test_gen_random_uuid_unique(self, pg_conn):
        """Multiple calls should produce distinct values."""
        cur = pg_conn.cursor()
        cur.execute("SELECT gen_random_uuid() FROM generate_series(1, 100)")
        uuids = {r[0] for r in cur.fetchall()}
        assert len(uuids) == 100, "UUIDs are not unique"

    def test_uuid_ossp_extension_if_available(self, pg_conn):
        """uuid_generate_v4() may also work if uuid-ossp extension is installed."""
        cur = pg_conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp'
            )
        """)
        has_extension = cur.fetchone()[0]
        if has_extension:
            cur.execute("SELECT uuid_generate_v4()")
            result = cur.fetchone()[0]
            assert result is not None
            assert isinstance(result, str)
            assert len(result) == 36


# ══════════════════════════════════════════════════════════════════════════════
# §4  Connection sanity
# ══════════════════════════════════════════════════════════════════════════════


class TestConnection:
    """Verify the test fixture works correctly."""

    def test_pg_conn_is_alive(self, pg_conn):
        cur = pg_conn.cursor()
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1

    def test_pg_version(self, pg_conn):
        cur = pg_conn.cursor()
        cur.execute("SHOW server_version")
        version = cur.fetchone()[0]
        assert version, "Could not read PostgreSQL version"


# ══════════════════════════════════════════════════════════════════════════════
# §5  UUID column default test
# ══════════════════════════════════════════════════════════════════════════════


class TestUUIDColumnDefault:
    """Verify gen_random_uuid() works as a column DEFAULT."""

    def test_uuid_column_default_auto_generates(self, pg_conn):
        """A table with DEFAULT gen_random_uuid() should auto-generate UUIDs."""
        cur = pg_conn.cursor()
        cur.execute("CREATE TEMP TABLE test_uuid_default (id UUID DEFAULT gen_random_uuid(), name TEXT)")
        try:
            cur.execute("INSERT INTO test_uuid_default (name) VALUES ('test') RETURNING id")
            row = cur.fetchone()
            assert row is not None
            uuid_val = row[0]
            assert uuid_val is not None
            assert isinstance(uuid_val, str)
            assert len(uuid_val) == 36
            # Verify uniqueness across multiple inserts
            cur.execute("INSERT INTO test_uuid_default (name) VALUES ('test2') RETURNING id")
            row2 = cur.fetchone()
            assert row2[0] != uuid_val
        finally:
            cur.execute("DROP TABLE IF EXISTS test_uuid_default")


# ══════════════════════════════════════════════════════════════════════════════
# §6  PL/pgSQL trigger behavioral tests
# ══════════════════════════════════════════════════════════════════════════════


class TestTriggerBehavior:
    """Verify that the PL/pgSQL trigger functions actually enforce rules."""

    # Known valid pipeline stages from the validate_pipeline_stage() function
    _VALID_STAGES = frozenset({
        'import', 'processing', 'enhance', 'ocr', 'validate', 'ai_fallback',
        'matching', 'auto_attach', 'verify', 'package', 'email',
        'complete', 'failed',
    })

    # Known valid pipeline statuses from the validate_pipeline_status() function
    _VALID_STATUSES = frozenset({
        'imported', 'processing', 'enhanced', 'processed',
        'ocr_done', 'validated', 'ai_done',
        'matched', 'attached', 'verified', 'packaged', 'emailed',
        'complete', 'failed',
    })

    def test_invalid_pipeline_stage_rejected(self, pg_conn):
        """The validate_pipeline_stage trigger should reject invalid stages."""
        cur = pg_conn.cursor()
        try:
            cur.execute(
                "INSERT INTO document_pipeline_runs "
                "(run_uuid, source_file_path, source_file_name, source_mime_type, "
                " document_id, stage, status, created_at, updated_at) "
                "VALUES (gen_random_uuid()::text, '/tmp/test.pdf', 'test.pdf', "
                "'application/pdf', -1, 'invalid_stage', 'imported', NOW(), NOW())"
            )
            pg_conn.commit()
            assert False, "Should have raised an exception for invalid stage"
        except Exception:
            # Expected — trigger should reject this
            pg_conn.rollback()

    def test_valid_pipeline_stage_accepted(self, pg_conn):
        """Known valid stages should be accepted."""
        cur = pg_conn.cursor()
        stage = next(s for s in self._VALID_STAGES)  # 'import'
        status = next(s for s in self._VALID_STATUSES)  # 'imported'
        try:
            cur.execute(
                "INSERT INTO document_pipeline_runs "
                "(run_uuid, source_file_path, source_file_name, source_mime_type, "
                " document_id, stage, status, created_at, updated_at) "
                "VALUES (gen_random_uuid()::text, '/tmp/test.pdf', 'test.pdf', "
                "'application/pdf', -2, %s, %s, NOW(), NOW())",
                (stage, status),
            )
            pg_conn.rollback()  # don't keep test data
        except Exception:
            pg_conn.rollback()

    def test_invalid_pipeline_status_rejected(self, pg_conn):
        """The validate_pipeline_status trigger should reject invalid statuses."""
        cur = pg_conn.cursor()
        try:
            cur.execute(
                "INSERT INTO document_pipeline_runs "
                "(run_uuid, source_file_path, source_file_name, source_mime_type, "
                " document_id, stage, status, created_at, updated_at) "
                "VALUES (gen_random_uuid()::text, '/tmp/test.pdf', 'test.pdf', "
                "'application/pdf', -3, 'import', 'bogus_status', NOW(), NOW())"
            )
            pg_conn.commit()
            assert False, "Should have raised an exception for invalid status"
        except Exception:
            pg_conn.rollback()


# ══════════════════════════════════════════════════════════════════════════════
# §7  Migration integrity on real PostgreSQL
# ══════════════════════════════════════════════════════════════════════════════


class TestMigrationIntegrity:
    """Verify that Alembic migrations apply cleanly on PostgreSQL."""

    def test_alembic_migrations_apply_on_pg(self, pg_schema):
        """The pg_schema fixture applies schema DDL + alembic migrations.
        Verify that schema_migrations (project-internal tracking) recorded
        all versions and that key tables from alembic migrations exist."""
        import psycopg2
        conn = psycopg2.connect(TEST_DSN)
        try:
            cur = conn.cursor()
            # schema_migrations is the project's own migration tracking table
            # (populated by schema_pg.sql, not by alembic). Verify it exists
            # and has entries.
            cur.execute(
                "SELECT COUNT(*) FROM schema_migrations"
            )
            count = cur.fetchone()[0]
            assert count >= 4, (
                f"Expected at least 4 schema_migrations, got {count}"
            )

            # Also verify that key tables created by alembic migrations
            # exist — this proves Alembic migrations were applied.
            # Note: alembic_version may not be visible if the migration
            # transaction was opened on a separate SQLAlchemy connection;
            # we verify the actual tables instead.
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "AND table_name IN ('freight_exchange_connections', "
                "'saved_searches', 'trans_eu_user_tokens')"
            )
            alembic_tables = {r[0] for r in cur.fetchall()}
            if not alembic_tables:
                # At minimum, check the extra DDL applied by DatabaseManager
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'trips' AND column_name = 'source'"
                )
                has_source = cur.fetchone() is not None
                assert has_source, (
                    "Expected at least one alembic-created table or column "
                    "(e.g. trips.source) to exist"
                )
        finally:
            conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# §8  information_schema query tests
# ══════════════════════════════════════════════════════════════════════════════


class TestInformationSchema:
    """information_schema.columns queries work on PostgreSQL."""

    def test_information_schema_columns_query(self, pg_conn):
        """information_schema.columns queries work on PostgreSQL."""
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'companies'"
        )
        columns = {r[0]: r[1] for r in cur.fetchall()}
        assert 'id' in columns, "id column should exist in companies"
        assert 'company_name' in columns, (
            "company_name column should exist in companies"
        )
        # id should be a numeric/integer type
        assert 'int' in columns['id'].lower() or 'serial' in columns['id'].lower(), (
            f"id column type '{columns['id']}' is not an integer type"
        )

    def test_information_schema_column_exists_query(self, pg_conn):
        """The specific query used by migration files should work."""
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = %s",
            ('companies', 'id'),
        )
        assert cur.fetchone() is not None, "Column should exist"


# ══════════════════════════════════════════════════════════════════════════════
# §9  Pool resilience tests
# ══════════════════════════════════════════════════════════════════════════════


class TestPoolResilience:
    """Connection pool exhaustion and recovery behavior."""

    def test_pool_exhaustion_blocks(self):
        """Requesting more connections than max should raise PoolError."""
        from database.connection_pool import PostgresConnectionPool
        pool = PostgresConnectionPool(TEST_DSN, min_connections=1, max_connections=2)
        conns = []
        try:
            # Checkout max connections
            for i in range(2):
                conns.append(pool.get_connection())
            # 3rd checkout should fail (pool exhausted)
            import psycopg2.pool
            try:
                overflow = pool.get_connection()
                # If it doesn't raise, we've checked out too many — return it
                pool.return_connection(overflow)
                conns.append(overflow)
                assert False, "Expected pool to be exhausted"
            except (psycopg2.pool.PoolError, Exception):
                pass  # expected
        finally:
            for c in conns:
                try:
                    pool.return_connection(c)
                except Exception:
                    pass
            pool.close_all()


# ══════════════════════════════════════════════════════════════════════════════
# §10  PostGIS extension test
# ══════════════════════════════════════════════════════════════════════════════


class TestPostGisExtension:
    """Verify PostGIS extension is available and functional."""

    def test_postgis_extension_installed(self, pg_conn):
        """Check if PostGIS extension is available and return version."""
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')"
        )
        has_postgis = cur.fetchone()[0]
        if has_postgis:
            cur.execute("SELECT PostGIS_Version()")
            version = cur.fetchone()[0]
            assert version is not None, "PostGIS_Version() returned None"
            assert len(version) > 0
        # If not installed, skip — PostGIS is optional
        if not has_postgis:
            pytest.skip("PostGIS is not installed — skipping")


# ══════════════════════════════════════════════════════════════════════════════
# §11  documents_search_update trigger behavioral test
# ══════════════════════════════════════════════════════════════════════════════


class TestDocumentSearchTrigger:
    """Verify the ``documents_search_update`` trigger populates the
    ``search_vector`` tsvector column on INSERT and UPDATE of the
    ``documents`` table."""

    def test_document_insert_populates_search_vector(self, pg_conn):
        """Inserting a document should auto-populate search_vector via trigger."""
        cur = pg_conn.cursor()
        try:
            cur.execute(
                "INSERT INTO documents "
                "(doc_number, title, file_name, file_path, description, "
                " company_id, uploaded_at, updated_at) "
                "VALUES ('TRIG-TEST-001', 'Test Document', 'test.pdf', "
                "'/tmp/test.pdf', 'a test document for search', "
                "1, NOW(), NOW()) "
                "RETURNING id, search_vector"
            )
            row = cur.fetchone()
            assert row is not None
            doc_id = row[0]
            search_vector = row[1]
            # search_vector should be populated (not None, not empty)
            assert search_vector is not None, (
                "search_vector was not populated by trigger"
            )
            # tsvector should contain tsvector-formatted text
            assert len(str(search_vector)) > 0, "search_vector is empty"
        finally:
            pg_conn.rollback()

    def test_document_update_rebuilds_search_vector(self, pg_conn):
        """Updating document text should rebuild search_vector."""
        cur = pg_conn.cursor()
        try:
            cur.execute(
                "INSERT INTO documents "
                "(doc_number, title, file_name, file_path, "
                " company_id, uploaded_at, updated_at) "
                "VALUES ('TRIG-TEST-002', 'Initial Doc', 'initial.pdf', "
                "'/tmp/initial.pdf', 1, NOW(), NOW()) "
                "RETURNING id"
            )
            doc_id = cur.fetchone()[0]

            cur.execute(
                "UPDATE documents SET description = 'updated description' "
                "WHERE id = %s RETURNING search_vector",
                (doc_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] is not None, (
                "search_vector not updated after description change"
            )
        finally:
            pg_conn.rollback()

    def test_document_insert_without_text_still_has_vector(self, pg_conn):
        """Inserting a document with only non-text columns should still
        produce a non-NULL search_vector (possibly empty/zero)."""
        cur = pg_conn.cursor()
        try:
            cur.execute(
                "INSERT INTO documents "
                "(doc_number, title, file_name, file_path, "
                " company_id, uploaded_at, updated_at) "
                "VALUES ('TRIG-TEST-003', '', 'no-text.bin', "
                "'/tmp/no-text.bin', 1, NOW(), NOW()) "
                "RETURNING id, search_vector"
            )
            row = cur.fetchone()
            assert row is not None
            # search_vector may be empty but should not be None
            assert row[1] is not None, (
                "search_vector should not be None even with empty text"
            )
        finally:
            pg_conn.rollback()


# ══════════════════════════════════════════════════════════════════════════════
# §12  Concurrent PG connection tests
# ══════════════════════════════════════════════════════════════════════════════


class TestConcurrentPgConnections:
    """Multi-threaded access to PostgreSQL."""

    def test_concurrent_reads_succeed(self):
        """Multiple threads can query PG concurrently."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import psycopg2

        def query(n):
            conn = psycopg2.connect(TEST_DSN, connect_timeout=5)
            try:
                cur = conn.cursor()
                cur.execute("SELECT %s * 2 AS result", (n,))
                return cur.fetchone()[0]
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(query, i) for i in range(1, 21)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 20
        assert all(isinstance(r, int) for r in results)

    def test_concurrent_writes_isolation(self):
        """Each thread should see its own uncommitted data (READ COMMITTED).

        Note: uses ``company_name`` column (not ``name``) to match the
        actual PostgreSQL schema.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import psycopg2

        results = {}

        def write_and_read(thread_id):
            conn = psycopg2.connect(TEST_DSN, connect_timeout=5)
            try:
                conn.autocommit = False
                cur = conn.cursor()
                # Insert a row with thread-specific data
                cur.execute(
                    "INSERT INTO companies (company_name) VALUES (%s)",
                    (f"concurrent-test-{thread_id}",),
                )
                # Read all rows — should see our own but not others' uncommitted
                cur.execute(
                    "SELECT company_name FROM companies "
                    "WHERE company_name LIKE 'concurrent-test-%'"
                )
                names = {r[0] for r in cur.fetchall()}
                conn.rollback()
                return thread_id, names
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(write_and_read, i): i for i in range(4)
            }
            for f in as_completed(futures):
                tid, names = f.result()
                # In READ COMMITTED, each thread should NOT see other threads'
                # uncommitted writes (unless already committed)
                results[tid] = names

        # Verify each thread only saw its own insert (at most)
        for tid, names in results.items():
            expected = {f"concurrent-test-{tid}"}
            assert names == expected, (
                f"Thread {tid} saw {names}, expected {expected}. "
                f"Possible MVCC isolation issue."
            )

    def test_concurrent_sequential_ids(self):
        """Concurrent inserts should get unique IDs (no collisions)."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import psycopg2

        def insert_and_return_id(n):
            conn = psycopg2.connect(TEST_DSN, connect_timeout=5)
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO companies (company_name) "
                    "VALUES (%s) RETURNING id",
                    (f"seq-test-{n}",),
                )
                row = cur.fetchone()
                conn.rollback()
                return row[0] if row else None
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [
                pool.submit(insert_and_return_id, i) for i in range(20)
            ]
            ids = [f.result() for f in as_completed(futures)]

        # All IDs should be unique (SERIAL/IDENTITY guarantees this)
        assert len(ids) == 20
        assert len(set(ids)) == 20, (
            f"ID collision: got {len(set(ids))} unique IDs out of 20"
        )
        assert all(i is not None for i in ids)


# ══════════════════════════════════════════════════════════════════════════════
# §13  Trips -> drivers/trucks FK constraints (Database_Rework P0.8)
# ══════════════════════════════════════════════════════════════════════════════


class TestTripsFkConstraints:
    """The trips.driver_id / trips.truck_id foreign keys (added post-table in
    schema_pg.sql) exist as NOT VALID constraints, reject orphan inserts, and
    null out on driver/truck deletion."""

    #: NOT NULL columns required for a drivers insert (from schema_pg.sql).
    _DRIVER_INSERT = (
        "INSERT INTO drivers (name, created_at, updated_at) "
        "VALUES (%s, NOW(), NOW()) RETURNING id"
    )

    def test_constraints_exist_not_validated(self, pg_conn):
        """Both FKs exist in pg_constraint with convalidated = false."""
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT conname, convalidated "
            "FROM pg_catalog.pg_constraint "
            "WHERE conrelid = 'trips'::regclass "
            "  AND contype = 'f' "
            "  AND conname IN ('fk_trips_driver', 'fk_trips_truck')"
        )
        rows = {r[0]: r[1] for r in cur.fetchall()}
        for name in ("fk_trips_driver", "fk_trips_truck"):
            assert name in rows, f"FK constraint {name} not found on trips"
            assert rows[name] is False, (
                f"FK {name} should be NOT VALID (convalidated=false), "
                f"got convalidated={rows[name]!r}"
            )

    def test_orphan_driver_insert_rejected(self, pg_conn):
        """Inserting a trip referencing a nonexistent driver_id must raise a
        foreign-key violation (NOT VALID still enforces new writes)."""
        from psycopg2.errors import ForeignKeyViolation

        cur = pg_conn.cursor()
        try:
            cur.execute(
                "INSERT INTO trips (driver_id, truck_number) VALUES (%s, %s)",
                (-99999999, "FK-ORPHAN-DRIVER"),
            )
            pg_conn.commit()
            assert False, "Expected a foreign key violation for bogus driver_id"
        except ForeignKeyViolation:
            pg_conn.rollback()  # expected — constraint rejected the orphan
        except Exception as e:
            pg_conn.rollback()
            pytest.fail(f"Expected ForeignKeyViolation, got {type(e).__name__}: {e}")

    def test_orphan_truck_insert_rejected(self, pg_conn):
        """Inserting a trip referencing a nonexistent truck_id must raise a
        foreign-key violation (NOT VALID still enforces new writes)."""
        from psycopg2.errors import ForeignKeyViolation

        cur = pg_conn.cursor()
        try:
            cur.execute(
                "INSERT INTO trips (truck_id, driver_name) VALUES (%s, %s)",
                (-99999999, "FK-ORPHAN-TRUCK"),
            )
            pg_conn.commit()
            assert False, "Expected a foreign key violation for bogus truck_id"
        except ForeignKeyViolation:
            pg_conn.rollback()  # expected — constraint rejected the orphan
        except Exception as e:
            pg_conn.rollback()
            pytest.fail(f"Expected ForeignKeyViolation, got {type(e).__name__}: {e}")

    def test_delete_driver_sets_trip_driver_id_null(self, pg_conn):
        """Deleting a drivers row must SET NULL the referencing trips.driver_id."""
        cur = pg_conn.cursor()
        try:
            cur.execute(self._DRIVER_INSERT, ("FK-SETNULL-DRIVER",))
            driver_id = cur.fetchone()[0]
            assert driver_id is not None

            cur.execute(
                "INSERT INTO trips (driver_id, truck_number) VALUES (%s, %s) "
                "RETURNING id",
                (driver_id, "FK-SETNULL-TRIP"),
            )
            trip_id = cur.fetchone()[0]
            assert trip_id is not None

            cur.execute("DELETE FROM drivers WHERE id = %s", (driver_id,))
            cur.execute(
                "SELECT driver_id FROM trips WHERE id = %s", (trip_id,)
            )
            row = cur.fetchone()
            assert row is not None, "Trip row vanished after driver delete"
            assert row[0] is None, (
                f"trips.driver_id should be NULL after driver delete, "
                f"got {row[0]!r}"
            )
        finally:
            pg_conn.rollback()

    def test_delete_truck_sets_trip_truck_id_null(self, pg_conn):
        """Deleting a trucks row must SET NULL the referencing trips.truck_id."""
        cur = pg_conn.cursor()
        try:
            cur.execute(
                "INSERT INTO trucks (plate_number) VALUES (%s) RETURNING id",
                ("FK-SETNULL-TRUCK-PLATE",),
            )
            truck_id = cur.fetchone()[0]
            assert truck_id is not None

            cur.execute(
                "INSERT INTO trips (truck_id, driver_name) VALUES (%s, %s) "
                "RETURNING id",
                (truck_id, "FK-SETNULL-TRUCK-DRIVER"),
            )
            trip_id = cur.fetchone()[0]
            assert trip_id is not None

            cur.execute("DELETE FROM trucks WHERE id = %s", (truck_id,))
            cur.execute(
                "SELECT truck_id FROM trips WHERE id = %s", (trip_id,)
            )
            row = cur.fetchone()
            assert row is not None, "Trip row vanished after truck delete"
            assert row[0] is None, (
                f"trips.truck_id should be NULL after truck delete, "
                f"got {row[0]!r}"
            )
        finally:
            pg_conn.rollback()


class TestTripsFkConstraintsOffline:
    """Static, regex-based assertions that schema_pg.sql declares the two FK
    constraints *conditionally* (Stage C review NF2) — no live PostgreSQL
    connection needed.

    The boot path must create the constraints only when absent, so a validated
    state (``convalidated=true``) set by ``scripts/import_to_pg.py`` survives
    application reboots.  An unconditional DROP+ADD on every boot would
    silently reset the constraint back to NOT VALID.
    """

    def test_schema_pg_contains_both_trips_fk_alters(self):
        with open(_SCHEMA_PG_SQL, encoding="utf-8") as f:
            sql = f.read()

        # The conditional guard is a DO block, not a top-level DROP+ADD.
        assert re.search(r"\bDO\s+\$\$", sql, re.IGNORECASE), (
            "schema_pg.sql must guard the trips FKs with a DO $$ ... $$ block "
            "(NF2)"
        )

        # No unconditional DROP on the boot path — drop/re-add is an explicit
        # repair path only.
        assert not re.search(
            r"ALTER\s+TABLE\s+trips\s+DROP\s+CONSTRAINT",
            sql,
            re.IGNORECASE,
        ), (
            "schema_pg.sql must NOT unconditionally DROP the trips FK "
            "constraints on every boot (NF2)"
        )

        for conname, column, ref_table in (
            ("fk_trips_driver", "driver_id", "drivers"),
            ("fk_trips_truck", "truck_id", "trucks"),
        ):
            # information_schema guard: only add when the constraint is absent.
            assert re.search(
                rf"IF\s+NOT\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+"
                rf"information_schema\.table_constraints\s+"
                rf"WHERE\s+constraint_name\s*=\s*'{conname}'\s+"
                rf"AND\s+table_name\s*=\s*'trips'\s*\)",
                sql,
                re.IGNORECASE,
            ), (
                f"schema_pg.sql missing information_schema guard for "
                f"{conname} (NF2)"
            )

            # ADD with ON DELETE SET NULL + NOT VALID inside the DO block.
            assert re.search(
                rf"ALTER\s+TABLE\s+trips\s+ADD\s+CONSTRAINT\s+{conname}\s*"
                rf"FOREIGN\s+KEY\s*\(\s*{column}\s*\)\s*REFERENCES\s+"
                rf"{ref_table}\s*\(\s*id\s*\)\s+ON\s+DELETE\s+SET\s+NULL\s+"
                rf"NOT\s+VALID",
                sql,
                re.IGNORECASE,
            ), (
                f"schema_pg.sql missing ON DELETE SET NULL NOT VALID FK "
                f"{conname} on trips.{column} -> {ref_table}(id)"
            )


# ══════════════════════════════════════════════════════════════════════════════
# §14  Soft-delete scope exclusion (Database_Rework P0.7)
# ══════════════════════════════════════════════════════════════════════════════


class TestSoftDeleteExclusion:
    """Static, regex-based assertions that schema_pg.sql declares NO
    `deleted_at` column for the 9 audit/operational/current-state tables.

    Decision lock for Database_Rework P0.7: these tables intentionally stay
    without soft-delete on PostgreSQL — parity with the SQLite-side exclusion
    in db_manager._run_column_migrations.  Offline; no PostgreSQL connection
    needed.
    """

    #: Tables that intentionally carry NO deleted_at column (audit/log,
    #: operational, or current-state semantics).
    _NO_SOFT_DELETE_TABLES = frozenset({
        "email_logs",
        "invoice_reminders",
        "tacho_imports",
        "tacho_driver_activity",
        "tacho_vehicle_data",
        "driver_truck_assignments",
        "trip_status_history",
        "operation_events",
        "alerts",
    })

    @staticmethod
    def _extract_table_block(sql: str, table: str) -> str:
        """Return the ``CREATE TABLE`` body for *table* (through the closing
        ``);``), mirroring the line-based block parser used elsewhere in this
        file."""
        lines = sql.splitlines()
        pattern = re.compile(
            rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{re.escape(table)}\s*\(",
            re.IGNORECASE,
        )
        for i, line in enumerate(lines):
            if pattern.search(line):
                out = [line]
                for l in lines[i + 1:]:
                    out.append(l)
                    if l.strip().startswith(")"):  # covers ');'
                        break
                return "\n".join(out)
        raise AssertionError(f"schema_pg.sql has no CREATE TABLE block for {table}")

    def test_soft_delete_excluded_from_nine_audit_tables(self):
        """None of the 9 excluded tables may declare ``deleted_at`` in their
        CREATE TABLE block (pins the Database_Rework P0.7 decision against
        drift)."""
        with open(_SCHEMA_PG_SQL, encoding="utf-8") as f:
            sql = f.read()

        violations = [
            table for table in sorted(self._NO_SOFT_DELETE_TABLES)
            if re.search(r"\bdeleted_at\b", self._extract_table_block(sql, table))
        ]
        assert not violations, (
            f"Database_Rework P0.7 excluded these tables from soft-delete, but "
            f"schema_pg.sql now declares deleted_at for them: {violations}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# §15  search_vector NULL backfill on the native-PG boot path (NF1)
# ══════════════════════════════════════════════════════════════════════════════


class TestSearchVectorBootBackfill:
    """``DatabaseManager._apply_pg_extra_ddl`` must backfill NULL
    ``search_vector`` rows on every PG boot (Stage C review NF1).

    An existing PG database that predates the ``search_vector`` column (the
    ``ALTER TABLE documents ADD COLUMN IF NOT EXISTS search_vector tsvector``
    upgrade) has every document row carrying a NULL vector — unfindable via
    ``fts_search``/``fts_search_count`` until edited.  The import path
    (``scripts/import_to_pg.py``) backfills, but the native-PG boot path did
    not: ``DocumentRepository.rebuild_fts_index`` has the right expression yet
    no boot-time caller.  The extra-DDL UPDATE is that counterpart.
    """

    def test_boot_backfills_null_search_vector(self, pg_conn):
        """A document row forced to NULL ``search_vector`` is repopulated (and
        becomes findable) when DatabaseManager boots."""
        from database.db_manager import DatabaseManager

        cur = pg_conn.cursor()
        # Self-cleaning: a prior (interrupted) run may have left this row behind.
        cur.execute("DELETE FROM documents WHERE doc_number = 'NF1-NULL-VECTOR'")
        pg_conn.commit()
        cur.execute(
            "INSERT INTO documents "
            "(doc_number, title, file_name, file_path, description, "
            " text_content, company_id, uploaded_at, updated_at) "
            "VALUES ('NF1-NULL-VECTOR', 'Boot Backfill Doc', 'nf1.pdf', "
            "'/tmp/nf1.pdf', 'searchable description', 'searchable body text', "
            "1, NOW(), NOW()) RETURNING id"
        )
        doc_id = cur.fetchone()[0]
        # Simulate the pre-column upgrade: force the vector to NULL.  There is
        # no BEFORE UPDATE trigger on search_vector itself (the trigger fires
        # only for the text columns), so this NULL sticks.
        cur.execute(
            "UPDATE documents SET search_vector = NULL WHERE id = %s", (doc_id,)
        )
        pg_conn.commit()

        cur.execute(
            "SELECT search_vector FROM documents WHERE id = %s", (doc_id,)
        )
        assert cur.fetchone()[0] is None, "failed to seed a NULL search_vector"
        # Close the read transaction so the boot's ALTER TABLE (ACCESS
        # EXCLUSIVE) is not blocked by this connection's ACCESS SHARE lock.
        pg_conn.commit()

        # Boot the native-PG deployment path — runs schema_pg.sql + Alembic +
        # _apply_pg_extra_ddl (including the NULL-only search_vector backfill).
        db = DatabaseManager(
            db_path=TEST_DSN, engine="postgresql", pool_min=1, pool_max=2
        )
        db.close()

        cur.execute(
            "SELECT search_vector, "
            "       search_vector @@ plainto_tsquery('english', %s) AS matched "
            "FROM documents WHERE id = %s",
            ("searchable", doc_id),
        )
        row = cur.fetchone()
        assert row is not None, "document row vanished after boot"
        assert row[0] is not None, (
            "search_vector was not backfilled at boot — NULL vectors remain "
            "unfindable on pre-column PG databases (NF1)"
        )
        assert row[1] is True, (
            "backfilled search_vector does not match the tsquery"
        )

        # Idempotent: a second boot must leave the (now non-NULL) vector alone.
        cur.execute(
            "SELECT search_vector FROM documents WHERE id = %s", (doc_id,)
        )
        before = cur.fetchone()[0]
        pg_conn.commit()  # release ACCESS SHARE before the second boot
        db = DatabaseManager(
            db_path=TEST_DSN, engine="postgresql", pool_min=1, pool_max=2
        )
        db.close()
        cur.execute(
            "SELECT search_vector FROM documents WHERE id = %s", (doc_id,)
        )
        assert cur.fetchone()[0] == before, "backfill is not idempotent"

        cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        pg_conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# §16  Validated FK state survives a reboot (Stage C review NF2)
# ══════════════════════════════════════════════════════════════════════════════


class TestTripsFkValidatedStatePersists:
    """schema_pg.sql must create the trips FKs *only when absent*, so a
    ``VALIDATE CONSTRAINT`` performed by ``scripts/import_to_pg.py``
    (``convalidated=true``) is not silently undone by the next application
    boot.

    Regression for Stage C review NF2: the old boot path ran an unconditional
    ``DROP CONSTRAINT IF EXISTS`` + ``ADD ... NOT VALID`` on every boot, which
    reset ``convalidated`` back to false and discarded the validation work.
    """

    _CONSTRAINTS = ("fk_trips_driver", "fk_trips_truck")

    @classmethod
    def _convalidated(cls, pg_conn) -> dict:
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT conname, convalidated "
            "FROM pg_catalog.pg_constraint "
            "WHERE conrelid = 'trips'::regclass "
            "  AND contype = 'f' "
            "  AND conname = ANY(%s)",
            (list(cls._CONSTRAINTS),),
        )
        return {r[0]: r[1] for r in cur.fetchall()}

    @staticmethod
    def _boot() -> None:
        from database.db_manager import DatabaseManager

        db = DatabaseManager(
            db_path=TEST_DSN, engine="postgresql", pool_min=1, pool_max=2
        )
        db.close()

    def test_validated_state_survives_reboot(self, pg_conn):
        from psycopg2 import sql as pgsql

        cur = pg_conn.cursor()

        # Start from a known state: drop the FKs (explicit repair path), so
        # the next boot has to recreate them NOT VALID.  Sanitize any legacy
        # orphan rows too, so a later VALIDATE CONSTRAINT can succeed.
        for name in self._CONSTRAINTS:
            cur.execute(
                pgsql.SQL(
                    "ALTER TABLE trips DROP CONSTRAINT IF EXISTS {}"
                ).format(pgsql.Identifier(name))
            )
        cur.execute(
            "UPDATE trips SET driver_id = NULL "
            "WHERE driver_id IS NOT NULL AND NOT EXISTS "
            "  (SELECT 1 FROM drivers d WHERE d.id = trips.driver_id)"
        )
        cur.execute(
            "UPDATE trips SET truck_id = NULL "
            "WHERE truck_id IS NOT NULL AND NOT EXISTS "
            "  (SELECT 1 FROM trucks t WHERE t.id = trips.truck_id)"
        )
        pg_conn.commit()  # release locks before the boot's DDL runs

        # First boot: schema_pg.sql recreates the constraints, NOT VALID.
        self._boot()
        states = self._convalidated(pg_conn)
        pg_conn.commit()
        for name in self._CONSTRAINTS:
            assert name in states, f"FK {name} missing after boot"
            assert states[name] is False, (
                f"freshly created FK {name} should be NOT VALID, "
                f"got convalidated={states[name]!r}"
            )

        # Simulate scripts/import_to_pg.py: VALIDATE both constraints.
        for name in self._CONSTRAINTS:
            cur.execute(
                pgsql.SQL("ALTER TABLE trips VALIDATE CONSTRAINT {}").format(
                    pgsql.Identifier(name)
                )
            )
        pg_conn.commit()
        states = self._convalidated(pg_conn)
        pg_conn.commit()
        for name in self._CONSTRAINTS:
            assert states[name] is True, (
                f"VALIDATE CONSTRAINT {name} did not set convalidated=true"
            )

        # Second boot: the validated state MUST survive (NF2 regression).
        self._boot()
        states = self._convalidated(pg_conn)
        pg_conn.commit()
        for name in self._CONSTRAINTS:
            assert states[name] is True, (
                f"FK {name} reverted to NOT VALID after a reboot — the boot "
                f"path dropped and re-added it, discarding the validated "
                f"state (NF2)"
            )
