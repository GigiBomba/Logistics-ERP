from __future__ import annotations

import logging
import os
import re
import sqlite3
import threading
import warnings
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

_emitted_warnings: set = set()

# Fixed session-level advisory-lock key used to serialize the PostgreSQL
# schema build across processes/workers (uvicorn workers, Celery workers,
# pytest-xdist workers) that all boot the same database concurrently.
# Session-level advisory locks are released when the session ends, so a
# crashed worker can never leave the schema permanently locked.
_PG_SCHEMA_ADVISORY_LOCK_KEY = 0x0F1207A1


def _deprecated(msg: str) -> None:
    if msg not in _emitted_warnings:
        _emitted_warnings.add(msg)
        warnings.warn(msg, DeprecationWarning, stacklevel=3)


def _split_pg_statements(sql: str) -> list:
    """Split PostgreSQL SQL into individual statements, preserving $$-delimited blocks.

    PL/pgSQL function bodies use ``$$ ... $$`` delimiters and may contain
    semicolons.  Naive ``sql.split(';')`` would break these blocks.
    """
    import re
    statements = []
    # Replace $$-delimited blocks with a placeholder so semicolons
    # inside them are not treated as statement terminators.
    dollar_blocks = []
    def _replace_dollar(m):
        dollar_blocks.append(m.group(0))
        return f"\x00DOLLAR{len(dollar_blocks)-1}\x00"
    # Match $$...$$ blocks (non-greedy, across newlines)
    protected = re.sub(r'\$\$.*?\$\$', _replace_dollar, sql, flags=re.DOTALL)
    # Strip line comments BEFORE splitting on ';' — a '--' comment that
    # itself contains a semicolon (e.g. "… `created_at`; the old index…")
    # would otherwise produce an executable fragment after the split.
    # Dollar-quoted blocks are already placeholders, so their contents
    # (which may legitimately contain '--') are safe from this pass.
    no_comments = []
    for line in protected.split("\n"):
        idx = line.find("--")
        if idx != -1:
            line = line[:idx]
        no_comments.append(line)
    protected = "\n".join(no_comments)
    for part in protected.split(";"):
        # Restore dollar blocks, strip whitespace
        stmt = part.strip()
        if not stmt:
            continue
        # Restore $$ blocks (don't clear dollar_blocks — subsequent
        # statements may also need placeholder replacement).
        for i, block in enumerate(dollar_blocks):
            stmt = stmt.replace(f"\x00DOLLAR{i}\x00", block)
        if stmt.strip():
            statements.append(stmt.strip())
    return statements


from database import schema as _schema
from database.connection_pool import (
    ConnectionPool,
    PostgresConnectionPool,
    pool_active,
    pool_idle,
    pool_max,
    pool_min,
)

# ── Phase A (multi-device): sync_server_map device_id migration (PG) ──────
# The old unique key (company_id, entity_type, local_id) may exist as an
# inline UNIQUE CONSTRAINT (constraint-named) or as a standalone
# CREATE UNIQUE INDEX.  Both are discovered and dropped by the DO block
# below; the standalone-index loop deliberately excludes the PRIMARY KEY
# backing index (ix.indisprimary) and any constraint-backed index
# (pg_constraint.conindid = indexrelid) so it never tries to DROP the PK.
# Each EXECUTE is wrapped in a PL/pgSQL sub-block so one bad drop cannot
# roll back the rest of the migration.
_PG_SYNC_SERVER_MAP_DROP_OLD = """
    DO $$
    DECLARE obj text;
    BEGIN
        FOR obj IN
            SELECT 'ALTER TABLE sync_server_map DROP CONSTRAINT ' || quote_ident(c.conname)
            FROM pg_constraint c
            WHERE c.conrelid = 'sync_server_map'::regclass AND c.contype = 'u'
              AND NOT EXISTS (
                  SELECT 1 FROM unnest(c.conkey) AS k(attnum)
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
                  WHERE a.attname = 'device_id')
        LOOP
            BEGIN
                EXECUTE obj;
            EXCEPTION WHEN OTHERS THEN NULL;
            END;
        END LOOP;
        FOR obj IN
            SELECT 'DROP INDEX ' || quote_ident(i.relname)
            FROM pg_index ix
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_class t ON t.oid = ix.indrelid
            WHERE t.relname = 'sync_server_map' AND ix.indisunique
              AND ix.indisprimary = FALSE
              AND NOT EXISTS (SELECT 1 FROM pg_constraint c WHERE c.conindid = ix.indexrelid)
              AND NOT EXISTS (
                  SELECT 1 FROM unnest(ix.indkey::int2[]) AS k(attnum)
                  JOIN pg_attribute a ON a.attrelid = ix.indrelid AND a.attnum = k.attnum
                  WHERE a.attname = 'device_id')
        LOOP
            BEGIN
                EXECUTE obj;
            EXCEPTION WHEN OTHERS THEN NULL;
            END;
        END LOOP;
    END $$;
"""

_PG_SYNC_SERVER_MAP_ADD_NEW = """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname =
            'sync_server_map_company_id_device_id_entity_type_local_id_key') THEN
            ALTER TABLE sync_server_map ADD CONSTRAINT
            sync_server_map_company_id_device_id_entity_type_local_id_key
            UNIQUE (company_id, device_id, entity_type, local_id);
        END IF;
    END $$;
"""


class DatabaseManager:
    def __init__(
        self,
        db_path: str,
        engine: str = "",
        pool_min: int = 2,
        pool_max: int = 20,
    ):
        self._engine = engine or os.environ.get("OPERION_DB_ENGINE", "sqlite")
        self._pg_pool: Optional[PostgresConnectionPool] = None
        self._pg_pool_min = pool_min
        self._pg_pool_max = pool_max
        self._local = threading.local()
        # tenant context now managed via tenant_context module
        if self._engine == "postgresql":
            # Celery tasks and other callers may pass Config.DB_PATH (a SQLite
            # file path) with engine=postgresql; resolve the real DSN here,
            # mirroring backend/dependencies.py. Only override when the given
            # value is clearly not a DSN (no "://").
            if "://" not in db_path:
                dsn = os.environ.get("OPERION_POSTGRES_DSN", "")
                if dsn:
                    db_path = dsn
            self._init_pg(db_path)
        else:
            self._pool = ConnectionPool(db_path, timeout=30)
        self._init_db()

    def _init_pg(self, dsn: str) -> None:
        """Initialise the PostgreSQL connection pool."""
        self._pg_pool = PostgresConnectionPool(
            dsn,
            min_connections=self._pg_pool_min,
            max_connections=self._pg_pool_max,
        )
        logger.info(
            "PostgreSQL pool initialised: min=%d max=%d",
            self._pg_pool_min, self._pg_pool_max,
        )

    def generate_uuid(self) -> str:
        """Return a new UUID string for use as a primary key value.

        PostgreSQL uses ``gen_random_uuid()`` as a column DEFAULT, so
        this is primarily needed for SQLite inserts where we must supply
        the value from Python.
        """
        import uuid
        return str(uuid.uuid4())

    @contextmanager
    def _get_connection(self) -> Generator[Any, None, None]:
        """Get a DB connection from the pool, with automatic return.

        For PostgreSQL: yields the current thread's cached connection
        (same as the ``conn`` property).  No explicit return is needed
        — it stays cached for the thread and is reclaimed on :meth:`close`.

        For SQLite: yields the current thread's dedicated connection
        via the existing ``ConnectionPool``.
        """
        if self._engine == "postgresql" and self._pg_pool:
            yield self._pg_pool.get_cached_connection()
        else:
            yield self._pool.conn

    @contextmanager
    def _borrow_connection(self) -> Generator[Any, None, None]:
        """Borrow a dedicated connection from the pool (not cached).

        Unlike ``_get_connection`` / the ``conn`` property, each call
        to this context manager obtains a *fresh* connection from the
        pool and returns it immediately on exit.  Use this in
        long-running or high-concurrency code paths where holding a
        connection for the lifetime of the thread is undesirable.

        For SQLite: falls back to the thread-local connection.
        """
        if self._engine == "postgresql" and self._pg_pool:
            conn = self._pg_pool.get_connection()
            try:
                yield conn
            finally:
                self._pg_pool.return_connection(conn)
        else:
            yield self._pool.conn

    @property
    def conn(self):
        """Return the current thread's database connection.

        For PostgreSQL: returns a thread-local cached connection from
        the pool.  The connection is kept for the thread's lifetime
        and returned to the pool on :meth:`close`.

        For SQLite: returns the thread-local connection managed by
        the existing ``ConnectionPool``.
        """
        if self._engine == "postgresql":
            if not self._pg_pool:
                raise RuntimeError("PostgreSQL pool not initialised")
            return self._pg_pool.get_cached_connection()
        return self._pool.conn

    def close(self):
        """Close the connection pool and release all resources."""
        if self._engine == "postgresql":
            if self._pg_pool:
                self._pg_pool.close_all()
                logger.info("PostgreSQL pool closed")
        else:
            self._pool.close_all()

    @property
    def health_stats(self) -> dict:
        """Return database connection health information."""
        if self._engine == "postgresql":
            if self._pg_pool:
                self._pg_pool.update_pool_stats()
                return {
                    "engine": "postgresql",
                    "pool": self._pg_pool.stats,
                    "prometheus": {
                        "pool_active": pool_active.labels(pool_name="postgresql")._value.get(),
                        "pool_idle": pool_idle.labels(pool_name="postgresql")._value.get(),
                        "pool_min": pool_min.labels(pool_name="postgresql")._value.get(),
                        "pool_max": pool_max.labels(pool_name="postgresql")._value.get(),
                    },
                }
            return {"engine": "postgresql", "pool": {"status": "uninitialised"}}
        return {"engine": "sqlite", "pool": {"status": "active"}}

    @staticmethod
    def row_to_dict(row):
        if row is None:
            return None
        # PostgreSQL (psycopg2 RealDictCursor) already returns dict-like;
        # SQLite (sqlite3.Row) needs explicit dict() conversion.
        if isinstance(row, dict):
            return row
        return dict(row)

    @staticmethod
    def rows_to_dicts(rows):
        if not rows:
            return []
        return [DatabaseManager.row_to_dict(r) for r in rows]

    # ── Centralised query adaptation ─────────────────────────────────

    def _adapt_placeholders(self, query: str) -> str:
        """Convert ``?`` placeholders to ``%s`` for PostgreSQL.

        Called automatically by :meth:`execute` and :meth:`executemany`.
        SQLite queries pass through unchanged.
        """
        if self._engine == "postgresql":
            return query.replace("?", "%s")
        return query

    def execute(self, query: str, params: tuple = ()):
        """Execute a SQL statement with engine-appropriate placeholders.

        For PostgreSQL (psycopg2): creates a cursor, executes, returns it.
        For SQLite: ``sqlite3.Connection.execute()`` returns a cursor directly.

        Callers should use this instead of ``self.conn.execute()`` directly
        for cross-engine compatibility.
        """
        try:
            if self._engine == "postgresql":
                cur = self.conn.cursor()
                cur.execute(self._adapt_placeholders(query), params)
                result = cur
            else:
                conn = self.conn
                was_in_tx = bool(getattr(conn, "in_transaction", False))
                try:
                    result = conn.execute(self._adapt_placeholders(query), params)
                except Exception:
                    # A failed DML inside sqlite's implicit transaction would
                    # leak the WAL write lock on this pooled connection.
                    self._rollback_if_implicit(conn, was_in_tx)
                    raise
            if self._engine == "postgresql" and self._pg_pool:
                self._pg_pool.record_query()
            return result
        except Exception:
            if self._engine == "postgresql" and self._pg_pool:
                self._pg_pool.record_error()
                # Clear the aborted implicit transaction so the cached
                # connection survives the failed statement.
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            raise

    def executemany(self, query: str, seq_of_params):
        """Execute a SQL statement against all parameter sequences.

        For PostgreSQL (psycopg2): creates a cursor, calls ``executemany``.
        For SQLite: ``sqlite3.Connection.executemany()`` returns a cursor directly.
        """
        if self._engine == "postgresql":
            try:
                cur = self.conn.cursor()
                cur.executemany(self._adapt_placeholders(query), seq_of_params)
                if self._pg_pool:
                    self._pg_pool.record_query()
                return cur
            except Exception:
                if self._pg_pool:
                    self._pg_pool.record_error()
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                raise
        conn = self.conn
        was_in_tx = bool(getattr(conn, "in_transaction", False))
        try:
            return conn.executemany(self._adapt_placeholders(query), seq_of_params)
        except Exception:
            self._rollback_if_implicit(conn, was_in_tx)
            raise

    @staticmethod
    def _rollback_if_implicit(conn, was_in_tx: bool) -> None:
        """Roll back a transaction that an aborted DML statement implicitly opened.

        Python's ``sqlite3`` (legacy ``isolation_level=""``) auto-issues
        ``BEGIN`` *before* the first INSERT/UPDATE/DELETE.  When that statement
        then raises (UNIQUE constraint, ``database is locked``, …) the implicit
        transaction stays open and — in WAL mode — the connection keeps the DB
        write lock indefinitely, wedging every other connection's writes.
        Callers managing their own transaction (``BEGIN IMMEDIATE``) started it
        before us (``was_in_tx``), so it is left for the caller to roll back.
        """
        if was_in_tx:
            return
        try:
            if hasattr(conn, "in_transaction") and conn.in_transaction:
                conn.rollback()
        except Exception:
            pass

    def commit(self):
        """Commit the current transaction (engine-agnostic)."""
        self.conn.commit()

    def rollback(self):
        """Rollback the current transaction (engine-agnostic)."""
        # PostgreSQL uses conn.rollback(), SQLite uses conn.execute("ROLLBACK")
        if self._engine == "postgresql":
            self.conn.rollback()
        else:
            self.conn.execute("ROLLBACK")

    # ── Read-only connection (engine-level sandbox) ───────────────────

    @staticmethod
    def open_readonly_connection(db_path: str) -> sqlite3.Connection:
        """Open a **read-only** SQLite connection to *db_path*.

        The connection is opened with ``uri=True&mode=ro``, which tells
        the SQLite engine to reject any write operation (INSERT, UPDATE,
        DELETE, DROP, etc.) at the file-system + engine level.  This is
        the primary sandbox for the ``POST /admin/db/query`` endpoint.

        For ``:memory:`` databases (testing), falls back to a normal
        connection — the engine-level sandbox cannot be applied, but
        string filtering still protects the endpoint.

        The caller is responsible for calling ``.close()`` on the
        returned connection.

        Raises:
            sqlite3.OperationalError: If the database file cannot be
                opened in read-only mode (e.g. missing file).
        """
        if db_path == ":memory:":
            # In-memory databases cannot use URI read-only mode.
            conn = sqlite3.connect(":memory:", timeout=10, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn

        uri = f"file:{os.path.abspath(db_path)}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Creează tabelele și indecșii necesari.

        Each migration method manages its own transactions internally;
        we do NOT wrap everything in a single BEGIN/COMMIT here to
        avoid nested transaction errors (SQLite does not support them).

        For PostgreSQL: executes schema_pg.sql which contains all DDL
        in PostgreSQL-compatible syntax, followed by Alembic migrations
        and the parity ``_pg_extra_ddl`` list.  The whole build is
        serialized per-database with a session-level advisory lock and
        runs in per-statement autocommit mode, so concurrent booters
        (uvicorn/Celery/pytest-xdist workers) cannot deadlock each
        other's DDL or leave a half-built schema behind.
        """
        if self._engine == "postgresql":
            self._init_pg_schema_locked()
            self._seed_sentinel_company()
        else:
            self._create_tables_and_indices()
            self._seed_sentinel_company()
            self._run_column_migrations()
            self._ensure_updated_at_triggers()
            self._ensure_outbox_triggers()
            self._ensure_documents_fts()
            self._migrate_legacy_data()

            # Ensure mobile tables exist (best-effort, non-critical)
            # PostgreSQL does not support AUTOINCREMENT — the SQL in
            # ensure_mobile_tables is SQLite-specific.  Mobile tables are
            # not part of schema_pg.sql, so skip entirely for PostgreSQL.
            try:
                from backend.api.v1.mobile import ensure_mobile_tables
                ensure_mobile_tables(self)
            except Exception:
                pass  # mobile tables are non-critical

    def _seed_sentinel_company(self) -> None:
        """Ensure the sentinel company (``id=0``) exists.

        Many production tables declare ``company_id ... DEFAULT 0
        REFERENCES companies(id)`` (documents, gps_telemetry, client_tags,
        ...) to mean "no company", and the environment-admin user resolves
        to ``company_id=0``.  Without a ``companies`` row with ``id=0``,
        every INSERT that relies on that DEFAULT fails with a FOREIGN KEY
        violation on a freshly-bootstrapped database.
        """
        try:
            if self._engine == "postgresql":
                self.conn.execute(
                    "INSERT INTO companies (id, company_name, subscription_tier, is_active) "
                    "OVERRIDING SYSTEM VALUE "
                    "VALUES (0, 'System', 'starter', 1) "
                    "ON CONFLICT (id) DO NOTHING"
                )
            else:
                self.conn.execute(
                    "INSERT OR IGNORE INTO companies "
                    "(id, company_name, subscription_tier, is_active) "
                    "VALUES (0, 'System', 'starter', 1)"
                )
            self.conn.commit()
        except Exception as e:
            logger.warning("Sentinel company seed failed: %s", e)

    def _init_pg_schema_locked(self) -> None:
        """Build the PostgreSQL schema serially per database.

        Multiple app/test processes (uvicorn workers, Celery workers,
        pytest-xdist workers) all run ``DatabaseManager.__init__`` →
        ``_init_db()`` on the SAME database at startup.  Without
        serialization, their DDL statements (``ALTER TABLE ... ADD
        COLUMN IF NOT EXISTS``, ``CREATE INDEX``) deadlock each other;
        PostgreSQL then aborts the deadlock victim's entire transaction,
        and every later statement in that worker fails with "current
        transaction is aborted" and is silently skipped — leaving the
        schema half-built (missing ``trips.source``, missing
        ``invoice_number_sequences``, ...).

        Fix:
        * a session-level advisory lock serializes the whole build
          (schema_pg.sql + Alembic + ``_pg_extra_ddl``) per database;
        * autocommit mode makes every DDL statement its own transaction,
          so each statement commits (releasing its locks) before the next
          runs, and a single failed statement cannot abort the rest.
        """
        conn = self.conn
        prev_autocommit = conn.autocommit
        conn.autocommit = True
        try:
            cur = conn.cursor()
            cur.execute("SELECT pg_advisory_lock(%s)", (_PG_SCHEMA_ADVISORY_LOCK_KEY,))
            cur.close()
        except Exception as e:
            logger.warning("Could not acquire schema advisory lock (continuing anyway): %s", e)

        try:
            self._init_pg_schema()
            self._run_alembic_upgrade()
            self._apply_pg_extra_ddl()
        finally:
            try:
                cur = conn.cursor()
                cur.execute("SELECT pg_advisory_unlock(%s)", (_PG_SCHEMA_ADVISORY_LOCK_KEY,))
                cur.close()
            except Exception as e:
                logger.warning("Could not release schema advisory lock: %s", e)
            conn.autocommit = prev_autocommit

    def _run_alembic_upgrade(self) -> None:
        """Run Alembic migrations (PostgreSQL only).

        Failures are logged at ERROR with the real exception instead of
        being silently swallowed, so an incomplete migration can never
        pass unnoticed.
        """
        try:
            from alembic.config import Config
            from alembic import command
            import os

            alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
            # Override the script_location to be absolute
            script_location = os.path.join(os.path.dirname(__file__), "..", "alembic")
            alembic_cfg.set_main_option("script_location", script_location)
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic migrations applied successfully")
        except Exception as e:
            logger.error("Alembic migrations failed: %s", e, exc_info=True)

    def _apply_pg_extra_ddl(self) -> None:
        """Apply additional PostgreSQL-compatible DDL.

        This is the part of the SQLite ``_run_column_migrations`` path
        that is not in schema_pg.sql or Alembic migrations.  These
        statements are all safe to run repeatedly (IF NOT EXISTS), and
        they run AFTER Alembic — so tables created by migrations (e.g.
        ``copilot_insights``) exist before indexes on them are built.
        """
        # Apply additional PostgreSQL-compatible DDL that is part of
        # the SQLite _run_column_migrations path but not in schema_pg.sql
        # or Alembic migrations.  These are all safe to run repeatedly.
        _pg_extra_ddl: list[str] = [
            # invoice_number_sequences table (used by InvoiceRepository)
            "CREATE TABLE IF NOT EXISTS invoice_number_sequences ("
            "  series TEXT NOT NULL,"
            "  year INTEGER NOT NULL,"
            "  last_number INTEGER NOT NULL DEFAULT 0,"
            "  PRIMARY KEY (series, year)"
            ")",
            # invoice_status_history table
            "CREATE TABLE IF NOT EXISTS invoice_status_history ("
            "  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,"
            "  invoice_id INTEGER NOT NULL,"
            "  from_status TEXT NOT NULL DEFAULT '',"
            "  to_status TEXT NOT NULL,"
            "  changed_by INTEGER DEFAULT 0,"
            "  changed_at TEXT NOT NULL,"
            "  reason TEXT DEFAULT ''"
            ")",
            # Invoices columns added by SQLite _run_column_migrations
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS client_id INTEGER",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'EUR'",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT ''",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS line_items_json TEXT DEFAULT '[]'",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS subtotal_net NUMERIC(12,2) DEFAULT 0",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS total_vat NUMERIC(12,2) DEFAULT 0",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS total_gross NUMERIC(12,2) DEFAULT 0",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS pdf_path TEXT DEFAULT ''",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS created_at TEXT",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(12,6) DEFAULT 1.0",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS invoice_type TEXT DEFAULT 'invoice'",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS amount_paid NUMERIC(12,2) DEFAULT 0",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS amount_remaining NUMERIC(12,2) DEFAULT 0",
            # e-Factura XML artifact tracking (the XML FILE is the legal
            # deliverable; no ANAF submission chain exists).
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS efactura_status TEXT DEFAULT ''",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS efactura_xml_path TEXT DEFAULT ''",
            # Trips source columns (Alembic migration c3d4e5f6a7b3)
            "ALTER TABLE trips ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'manual'",
            "ALTER TABLE trips ADD COLUMN IF NOT EXISTS source_provider_id TEXT",
            "ALTER TABLE trips ADD COLUMN IF NOT EXISTS source_reference_id TEXT",
            "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
            "CREATE INDEX IF NOT EXISTS idx_drivers_user ON drivers(user_id)",
            # SQLite-schema parity columns (drill-verified: the app reads
            # these on PG — mfa.py, subscriptions.py, fleet/driver forms).
            "ALTER TABLE companies ADD COLUMN IF NOT EXISTS trial_ends_at TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_secret TEXT",
            "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS bank_account TEXT DEFAULT ''",
            "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS bank_code TEXT DEFAULT ''",
            "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS bank_bic TEXT DEFAULT ''",
            "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS iban TEXT DEFAULT ''",
            "ALTER TABLE driver_truck_assignments ADD COLUMN IF NOT EXISTS active INTEGER NOT NULL DEFAULT 1",
            # Sent-email dedup table: tenant-scoped reads/writes
            "ALTER TABLE sent_emails ADD COLUMN IF NOT EXISTS company_id INTEGER",
            # Phase B (sync): the 5 tables whose company_id is only added by
            # migration on existing PG deployments (CREATE TABLE IF NOT
            # EXISTS is a no-op on pre-existing tables).  driver_truck_assignments
            # had NO company_id in schema_pg.sql at all (B1); the other four
            # (email_logs, invoice_reminders, tacho_driver_activity,
            # tacho_vehicle_data) gained it only in CREATE blocks (B2).
            "ALTER TABLE driver_truck_assignments ADD COLUMN IF NOT EXISTS company_id INTEGER",
            "CREATE INDEX IF NOT EXISTS idx_dta_company ON driver_truck_assignments(company_id)",
            "ALTER TABLE email_logs ADD COLUMN IF NOT EXISTS company_id INTEGER",
            "CREATE INDEX IF NOT EXISTS idx_email_logs_company ON email_logs(company_id)",
            "ALTER TABLE invoice_reminders ADD COLUMN IF NOT EXISTS company_id INTEGER",
            "CREATE INDEX IF NOT EXISTS idx_invoice_reminders_company ON invoice_reminders(company_id)",
            "ALTER TABLE tacho_driver_activity ADD COLUMN IF NOT EXISTS company_id INTEGER",
            "CREATE INDEX IF NOT EXISTS idx_tacho_driver_activity_company ON tacho_driver_activity(company_id)",
            "ALTER TABLE tacho_vehicle_data ADD COLUMN IF NOT EXISTS company_id INTEGER",
            "CREATE INDEX IF NOT EXISTS idx_tacho_vehicle_data_company ON tacho_vehicle_data(company_id)",
            # Phase B backfill: legacy rows get the lowest real company
            # (mirrors the SQLite _tenant_tables backfill).  Idempotent — a
            # no-op once no NULL company_id rows remain.
            "UPDATE driver_truck_assignments SET company_id = "
            "COALESCE(company_id, (SELECT MIN(id) FROM companies WHERE id > 0)) "
            "WHERE company_id IS NULL",
            "UPDATE email_logs SET company_id = "
            "COALESCE(company_id, (SELECT MIN(id) FROM companies WHERE id > 0)) "
            "WHERE company_id IS NULL",
            "UPDATE invoice_reminders SET company_id = "
            "COALESCE(company_id, (SELECT MIN(id) FROM companies WHERE id > 0)) "
            "WHERE company_id IS NULL",
            "UPDATE tacho_driver_activity SET company_id = "
            "COALESCE(company_id, (SELECT MIN(id) FROM companies WHERE id > 0)) "
            "WHERE company_id IS NULL",
            "UPDATE tacho_vehicle_data SET company_id = "
            "COALESCE(company_id, (SELECT MIN(id) FROM companies WHERE id > 0)) "
            "WHERE company_id IS NULL",
            # Copilot insights dedup — runs AFTER Alembic migrations so the
            # copilot_insights table (a7b8c9d0e1f7) already exists on fresh DBs.
            # payload is a json column on PG: btree cannot index it directly,
            # so the dedup key uses a (payload::text) expression index. A bare
            # ON CONFLICT DO NOTHING honors expression unique indexes, so the
            # INSERT OR IGNORE translation still dedups correctly.
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_copilot_insights_dedup "
            "ON copilot_insights(company_id, insight_type, (payload::text))",
            # R1 (Phase E): id tiebreak watermark column on sync_cursors.
            "ALTER TABLE sync_cursors ADD COLUMN IF NOT EXISTS last_id BIGINT NOT NULL DEFAULT 0",
        ]
        # B4 (settings scoping): migrate the PG settings PK from ``key`` to
        # the composite ``(key, company_id)`` so per-company settings work on
        # PostgreSQL (the SQLite settings table already has the composite PK).
        # Existing NULL-company_id rows (written before this fix) are backfilled
        # to the lowest real company, mirroring the Phase B tenant backfill.
        _pg_extra_ddl.extend([
            "DO $$ BEGIN "
            "  IF EXISTS (SELECT 1 FROM information_schema.table_constraints "
            "             WHERE table_name = 'settings' AND constraint_name = 'settings_pkey' "
            "               AND constraint_type = 'PRIMARY KEY') THEN "
            "    UPDATE settings SET company_id = "
            "      COALESCE(company_id, (SELECT MIN(id) FROM companies WHERE id > 0)) "
            "      WHERE company_id IS NULL; "
            "    ALTER TABLE settings DROP CONSTRAINT settings_pkey; "
            "    ALTER TABLE settings ADD CONSTRAINT settings_pkey PRIMARY KEY (key, company_id); "
            "  END IF; "
            "END $$",
        ])
        # Offline-first sync (Phase 0): ensure updated_at exists on every
        # syncable table for legacy PG deployments.  schema_pg.sql declares
        # updated_at inside CREATE TABLE IF NOT EXISTS blocks (no-op on
        # existing tables), so existing databases need the additive ALTER
        # here.  TIMESTAMPTZ matches the canonical trigger output
        # (to_char → 'YYYY-MM-DDTHH:MM:SSZ').  invoices is handled above;
        # expenses is created by schema_pg.sql with the column already.
        _pg_extra_ddl.extend(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ"
            for table in _schema.SYNCABLE_TABLES
            if table not in ("invoices", "expenses")
        )
        for ddl in _pg_extra_ddl:
            try:
                cur = self.conn.cursor()
                cur.execute(ddl)
                cur.close()
            except Exception as e:
                # ADD COLUMN IF NOT EXISTS is PostgreSQL 9.6+;
                # older versions raise, which is harmless.
                logger.debug("PG extra DDL skipped (may be pre-existing): %s — %s", str(e)[:120], ddl[:80])
        # Phase A (multi-device): sync_server_map device_id migration.  Run
        # separately so failures are logged at WARNING (a failed ADD would
        # silently leave the table with no unique key).
        self._migrate_sync_server_map_device_id_pg()

    def _init_pg_schema(self):
        """Execute PostgreSQL schema from schema_pg.sql.

        Runs in per-statement autocommit mode (enabled by
        :meth:`_init_pg_schema_locked`): every DDL statement is its own
        transaction, so each statement commits — releasing its table
        locks — before the next one runs, and a failed statement cannot
        abort the rest of the build.  This is what makes the schema build
        reliable when multiple processes boot the same database at once.
        """
        import os
        schema_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "schema_pg.sql",
        )
        if not os.path.isfile(schema_path):
            logger.error("PostgreSQL schema file not found: %s", schema_path)
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path, "r", encoding="utf-8") as f:
            sql = f.read()

        # The SQL file is ordered alphabetically/functionally, not by FK
        # dependency.  Pre-create the ``companies`` table so that every
        # subsequent ``REFERENCES companies(id)`` succeeds.
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                company_name TEXT NOT NULL,
                subscription_tier TEXT NOT NULL DEFAULT 'starter'
                    CHECK (subscription_tier IN ('starter', 'professional', 'enterprise')),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
                updated_at TEXT DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
            )
        """)
        cur.close()

        # Split by semicolons while preserving $$...$$ blocks (PL/pgSQL functions).
        # $$-delimited blocks may contain semicolons that must not be split.
        statements = _split_pg_statements(sql)
        for stmt in statements:
            if not stmt:
                continue
            # Autocommit mode is on, so each statement is already its own
            # transaction — a single failure (e.g. an index on a table a
            # later migration creates) rolls back only that statement and
            # cannot cascade to the remaining ones.
            try:
                cur = self.conn.cursor()
                cur.execute(stmt)
                cur.close()
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug("Skipping existing object: %s", str(e)[:80])
                else:
                    logger.error("PG schema statement failed: %s — %s", str(e)[:120], stmt[:80])

    def _create_tables_and_indices(self):
        """Execute all CREATE TABLE and CREATE INDEX statements."""
        S = _schema
        exec_stmts = [
            # Schema version tracking
            S.TABLE_SCHEMA_MIGRATIONS,
            # Core tables
            S.TABLE_TRIPS, S.TABLE_INVOICES,
            S.INDEX_INVOICES_ISSUE_DATE, S.INDEX_INVOICES_DUE_DATE,
            S.TABLE_TRUCKS,
            S.TABLE_ROUTES, S.TABLE_ROUTE_HISTORY,
            S.TABLE_ROUTE_HISTORY_V2,
            S.INDEX_ROUTE_HISTORY_V2_CREATED, S.INDEX_ROUTE_HISTORY_V2_LAST_CALCULATED,
            S.INDEX_ROUTE_HISTORY_V2_TRUCK, S.INDEX_ROUTE_HISTORY_V2_PROFILE,
            S.INDEX_ROUTE_HISTORY_V2_FINGERPRINT,
            S.TABLE_ROUTE_EVENTS, S.TABLE_TRUCK_ROUTE_ASSIGNMENTS,
            S.INDEX_ROUTE_EVENTS_ROUTE, S.INDEX_ROUTE_EVENTS_TYPE,
            S.INDEX_TRUCK_ROUTE_ASSIGNMENTS_TRUCK, S.INDEX_TRUCK_ROUTE_ASSIGNMENTS_ROUTE,
            S.INDEX_TRUCK_ROUTE_ASSIGNMENTS_STATUS,
            S.INDEX_TRIPS_DATE, S.INDEX_TRIPS_TRUCK, S.INDEX_TRIPS_CLIENT_NAME,
            S.INDEX_TRIPS_DRIVER_NAME, S.INDEX_TRIPS_STATUS, S.INDEX_TRIPS_CLIENT_STATUS,
            S.INDEX_TRIPS_START_DATE, S.INDEX_TRIPS_DELIVERY_COUNTRY,
            S.INDEX_TRIPS_LOADING_COUNTRY, S.INDEX_TRIPS_DRIVER_ID,
            S.INDEX_TRIPS_PAYMENT_DATE,
            S.TABLE_SETTINGS, S.TABLE_EMAIL_LOGS,
            # Dunner / Invoice Reminders
            S.TABLE_INVOICE_REMINDERS, S.INDEX_INVOICE_REMINDERS_LOOKUP,
            # Operations Engine
            S.TABLE_ALERTS, S.TABLE_OPERATION_EVENTS, S.TABLE_TRIP_STATUS_HISTORY,
            S.INDEX_ALERTS_TYPE, S.INDEX_ALERTS_TRUCK, S.INDEX_ALERTS_RESOLVED,
            S.INDEX_OPERATION_EVENTS_TYPE, S.INDEX_TRIP_STATUS_HISTORY_TRIP,
            # Fleet Maintenance
            S.TABLE_MAINTENANCE_RECORDS, S.TABLE_MAINTENANCE_SCHEDULES,
            S.TABLE_TRUCK_HEALTH_SCORES,
            S.INDEX_MAINTENANCE_RECORDS_TRUCK, S.INDEX_MAINTENANCE_RECORDS_TYPE,
            S.INDEX_MAINTENANCE_RECORDS_DATE, S.INDEX_MAINTENANCE_SCHEDULES_TRUCK,
            S.INDEX_MAINTENANCE_SCHEDULES_ACTIVE,
            # Drivers
            S.TABLE_DRIVERS, S.INDEX_DRIVERS_ACTIVE, S.TABLE_DRIVER_TRUCK_ASSIGNMENTS,
            S.INDEX_DTA_DRIVER, S.INDEX_DTA_TRUCK,
            # Tachograph
            S.TABLE_TACHO_IMPORTS, S.TABLE_TACHO_DRIVER_ACTIVITY,
            S.TABLE_TACHO_VEHICLE_DATA,
            S.INDEX_TACHO_DRIVER_DATE, S.INDEX_TACHO_VEHICLE_TRUCK, S.INDEX_TACHO_IMPORTS_HASH,
            # Clients
            S.TABLE_CLIENTS, S.INDEX_CLIENTS_NAME, S.INDEX_CLIENTS_ACTIVE,
            S.TABLE_CLIENT_CONTACTS, S.INDEX_CONTACTS_CLIENT,
            S.TABLE_CLIENT_TAGS, S.INDEX_TAGS_CLIENT,
            # Document Center
            S.TABLE_DOCUMENTS, S.TABLE_DOCUMENT_LINKS,
            S.INDEX_DOCUMENTS_CATEGORY, S.INDEX_DOCUMENTS_ENTITY,
            S.INDEX_DOCUMENTS_HASH, S.INDEX_DOCUMENTS_NUMBER,
            S.INDEX_DOC_LINKS_DOCUMENT, S.INDEX_DOC_LINKS_ENTITY,
            S.TABLE_DOCUMENT_VERSIONS, S.INDEX_VERSIONS_DOCUMENT,
            S.TABLE_CONTRACTS, S.INDEX_CONTRACTS_CLIENT, S.INDEX_CONTRACTS_STATUS,
            S.INDEX_CONTRACTS_END_DATE,
            # Sent-email dedup (roadmap 12) — AFTER documents (FK parent)
            S.TABLE_SENT_EMAILS, S.INDEX_SENT_EMAILS_STATUS,
            S.TABLE_DOCUMENT_TEMPLATES,
            # CMR
            S.TABLE_CMR_COUNTER, S.TABLE_SUCCESSIVE_CARRIERS,
            S.INDEX_SUCCESSIVE_CARRIERS_TRIP, S.TABLE_CMR_AUDIT_LOG,
            S.INDEX_CMR_AUDIT_TRIP, S.INDEX_CMR_AUDIT_NUMBER,
            # Document Automation Pipeline
            S.TABLE_DOCUMENT_PIPELINE_RUNS,
            S.INDEX_PIPELINE_RUNS_UUID, S.INDEX_PIPELINE_RUNS_STATUS,
            S.INDEX_PIPELINE_RUNS_TRIP, S.INDEX_PIPELINE_RUNS_HASH,
            S.TABLE_DOCUMENT_PACKAGE, S.INDEX_PACKAGE_TRIP,
            S.INDEX_PACKAGE_UUID, S.INDEX_PACKAGE_STATUS,
            S.TABLE_DOCUMENT_PACKAGE_ITEMS, S.INDEX_PACKAGE_ITEMS_PACKAGE,
            S.INDEX_PACKAGE_ITEMS_DOCUMENT,
            S.TRIGGER_PIPELINE_RUNS_STAGE_CHECK, S.TRIGGER_PIPELINE_RUNS_STAGE_UPDATE,
            S.TRIGGER_PIPELINE_RUNS_STATUS_CHECK, S.TRIGGER_PIPELINE_RUNS_STATUS_UPDATE,
            # Proforma Invoices
            S.TABLE_PROFORMA_INVOICES,
            S.INDEX_PROFORMA_NUMBER, S.INDEX_PROFORMA_CLIENT, S.INDEX_PROFORMA_STATUS,
            # Receipts
            S.TABLE_RECEIPTS,
            S.INDEX_RECEIPT_NUMBER, S.INDEX_RECEIPT_TYPE,
            S.INDEX_RECEIPT_STATUS, S.INDEX_RECEIPT_TRIP, S.INDEX_RECEIPT_DRIVER,
            # Expenses (syncable table — base schema since Phase 0)
            S.TABLE_EXPENSES,
            # AutoMail / Dunner
            S.TABLE_AUTOMAIL_TEMPLATES, S.TABLE_AUTOMAIL_SCHEDULES,
            S.TABLE_AUTOMAIL_CLIENT_OVERRIDES, S.TABLE_AUTOMAIL_SETTINGS,
            S.TABLE_GPS_TELEMETRY,
            # Companies (multi-tenant)
            S.TABLE_COMPANIES,
            S.INDEX_COMPANIES_NAME,
            # Users (authentication)
            S.TABLE_USERS,
            S.INDEX_USERS_EMAIL,
            S.INDEX_USERS_COMPANY,
            S.INDEX_AUTOMAIL_SCHEDULES_TEMPLATE,
            S.INDEX_AUTOMAIL_SCHEDULES_ACTIVE_SORT,
            S.INDEX_AUTOMAIL_CLIENT_OVERRIDES_CLIENT,
            S.INDEX_GPS_TRUCK, S.INDEX_GPS_RECORDED,
            # Copilot tables (SQLite mirror of the Alembic copilot_* tables).
            # NOTE: idx_gps_telemetry_unique / idx_copilot_insights_dedup are
            # created in _run_column_migrations AFTER legacy duplicates are
            # removed (dedupe-before-unique-index), not here.
            S.TABLE_COPILOT_AUDIT_LOG, S.TABLE_CONVERSATION_SUMMARY,
            S.TABLE_COPILOT_REASONING_GRAPHS, S.TABLE_COPILOT_INSIGHTS,
            # Multi-tenant company_id indexes (single + composite) are created
            # in _run_column_migrations too — their columns only exist after
            # the column migrations run.
            # Additional performance indexes
            S.INDEX_INVOICES_STATUS, S.INDEX_GPS_TRUCK_TIME,
            S.INDEX_CMR_AUDIT_EVENT_TYPE,
            S.INDEX_EMAIL_LOGS_TRIP, S.INDEX_EMAIL_LOGS_STATUS,
            # API Keys (per-partner authentication)
            S.TABLE_API_KEYS,
            S.INDEX_API_KEYS_PARTNER, S.INDEX_API_KEYS_ACTIVE,
            # OAuth2 Clients (client credentials grant)
            S.TABLE_OAUTH2_CLIENTS,
            S.INDEX_OAUTH2_CLIENTS_ID, S.INDEX_OAUTH2_CLIENTS_PARTNER,
            # Webhook Events (external partner integrations)
            S.TABLE_WEBHOOK_EVENTS,
            S.INDEX_WEBHOOK_EVENTS_PARTNER,
            S.INDEX_WEBHOOK_EVENTS_RECEIVED,
            S.INDEX_WEBHOOK_EVENTS_COMPANY,
            # Auth Sessions — active login session tracking
            S.TABLE_AUTH_SESSIONS,
            S.INDEX_AUTH_SESSIONS_COMPANY,
            S.INDEX_AUTH_SESSIONS_EMAIL,
            S.INDEX_AUTH_SESSIONS_TOKEN,
            # Waitlist — pre-launch marketing capture
            S.TABLE_WAITLIST_ENTRIES,
            S.INDEX_WAITLIST_EMAIL, S.INDEX_WAITLIST_STATUS,
            S.INDEX_WAITLIST_JOINED, S.INDEX_WAITLIST_SOURCE,
            S.INDEX_WAITLIST_REFERRAL,
            # Freight Exchange
            S.TABLE_FREIGHT_EXCHANGE_CONNECTIONS,
            S.INDEX_FREIGHT_CONNECTIONS_COMPANY,
            S.INDEX_FREIGHT_CONNECTIONS_PROVIDER,
            S.INDEX_FREIGHT_CONNECTIONS_STATUS,
            S.TABLE_SAVED_SEARCHES,
            S.INDEX_SAVED_SEARCHES_COMPANY,
            S.INDEX_SAVED_SEARCHES_USER,
            # Freight Exchange: local negotiation threads (no external push)
            S.TABLE_FREIGHT_NEGOTIATIONS,
            S.INDEX_FREIGHT_NEGOTIATIONS_COMPANY,
            S.INDEX_FREIGHT_NEGOTIATIONS_THREAD,
            S.INDEX_FREIGHT_NEGOTIATIONS_STATUS,
            # Mobile Phase 2: async export jobs
            S.TABLE_EXPORT_JOBS,
            S.INDEX_EXPORT_JOBS_COMPANY,
            S.INDEX_EXPORT_JOBS_STATUS,
            # Mobile Phase 2: devices / messages / sync cursors (Gate-31)
            S.TABLE_MOBILE_DEVICES,
            S.INDEX_MOBILE_DEVICES_USER,
            S.INDEX_MOBILE_DEVICES_COMPANY,
            S.INDEX_MOBILE_DEVICES_TOKEN,
            S.TABLE_MOBILE_MESSAGES,
            S.TABLE_SYNC_CURSORS,
            # Offline-first sync (Phase 2): server-side exactly-once id map
            S.TABLE_SYNC_SERVER_MAP,
            # Offline-first sync (Phase 1): outbox + meta tables.  The
            # capture triggers are created later in _ensure_outbox_triggers
            # (after column migrations) so the DELETE payload can reference
            # every live column.
            S.TABLE_SYNC_OUTBOX, S.INDEX_SYNC_OUTBOX_PENDING,
            S.TABLE_SYNC_META,
            # Offline-first sync (Phase 3b): desktop bidirectional id map
            S.TABLE_SYNC_ID_MAP,
            # Offline-first sync (Phase 4a): conflict journal
            S.TABLE_SYNC_CONFLICTS,
            # Offline-first sync (Phase D): hard-delete tombstones (server-side)
            S.TABLE_SYNC_TOMBSTONES,
        ]
        for stmt in exec_stmts:
            try:
                self.conn.execute(stmt)
            except Exception as e:
                logger.warning("Schema statement failed (may be harmless): %s", e)
        try:
            self.conn.execute(S.INDEX_TRIPS_START_DATE)
        except Exception:
            pass
        try:
            self.conn.execute(S.INDEX_TRIPS_DELIVERY_COUNTRY)
        except Exception:
            pass
        try:
            self.conn.execute(S.INDEX_TRIPS_LOADING_COUNTRY)
        except Exception:
            pass
        try:
            self.conn.execute(S.INDEX_TRIPS_DRIVER_ID)
        except Exception:
            pass
        try:
            self.conn.execute(S.INDEX_CONTRACTS_END_DATE)
        except Exception:
            pass
        # Freight Exchange: trips source columns
        for _alter_stmt in (
            S.ALTER_TRIPS_ADD_SOURCE,
            S.ALTER_TRIPS_ADD_SOURCE_PROVIDER,
            S.ALTER_TRIPS_ADD_SOURCE_REFERENCE,
        ):
            try:
                self.conn.execute(_alter_stmt)
            except Exception:
                pass
        # Document Center P2 (FTS5 is best-effort, SQLite only)
        if self._engine != "postgresql":
            try:
                self.conn.execute(S.MIGRATION_DOCUMENTS_FTS_V2)
            except Exception as e:
                logger.warning("FTS migration (drop old table) failed: %s", e)
            try:
                self.conn.execute(S.TABLE_DOCUMENTS_FTS)
            except Exception as e:
                logger.warning("Migration step failed: %s", e)
            # DROP the external-content FTS triggers BEFORE column migrations
            # run.  The triggers reference documents columns (text_content,
            # cmr_number, extracted_data_json, ...) that only exist AFTER
            # _run_column_migrations — creating them here on a fresh DB would
            # fail ("no such column") and leave the FTS index malformed.  They
            # are recreated in _ensure_documents_fts() after migrations run.
            for _fts_trigger in (
                S.TRIGGER_DOCUMENTS_FTS_INSERT,
                S.TRIGGER_DOCUMENTS_FTS_DELETE,
                S.TRIGGER_DOCUMENTS_FTS_UPDATE,
            ):
                # "CREATE TRIGGER IF NOT EXISTS documents_fts_ai AFTER INSERT ..."
                _name = _fts_trigger.split()[5]
                try:
                    self.conn.execute(f"DROP TRIGGER IF EXISTS {_name}")
                except Exception as e:
                    logger.warning("Migration step failed: %s", e)
        # Seed initial schema migration version
        try:
            self.conn.execute(S.SCHEMA_MIGRATIONS_SEED)
        except Exception as e:
            logger.warning("Schema migration seed failed: %s", e)

    def _table_exists(self, table: str) -> bool:
        """Check if a table exists (engine-agnostic)."""
        try:
            if self._engine == "postgresql":
                row = self.conn.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = %s", (table,)
                ).fetchone()
                return row is not None
            else:
                row = self.conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name=?", (table,)
                ).fetchone()
                return row is not None
        except Exception:
            return False

    def _column_exists(self, table: str, column: str) -> bool:
        """Check if a column exists in a table (engine-agnostic)."""
        try:
            if self._engine == "postgresql":
                row = self.conn.execute(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = %s AND column_name = %s",
                    (table, column),
                ).fetchone()
                return row is not None
            else:
                cols = [r[1] for r in self.conn.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()]
                return column in cols
        except Exception:
            return False

    def _index_exists(self, index: str) -> bool:
        """Check if an index exists (engine-agnostic)."""
        try:
            if self._engine == "postgresql":
                row = self.conn.execute(
                    "SELECT 1 FROM pg_indexes WHERE indexname = %s", (index,)
                ).fetchone()
                return row is not None
            else:
                row = self.conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='index' AND name=?", (index,)
                ).fetchone()
                return row is not None
        except Exception:
            return False

    def _ensure_column(self, table: str, column: str, alter_sql: str) -> None:
        """Add a column if it doesn't already exist in the table."""
        try:
            if self._engine == "postgresql":
                # Use information_schema for PostgreSQL
                row = self.conn.execute(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = %s AND column_name = %s",
                    (table, column),
                ).fetchone()
                if not row:
                    self.conn.execute(alter_sql)
            else:
                cols = [r[1] for r in self.conn.execute(f"PRAGMA table_xinfo({table})").fetchall()]
                if column not in cols:
                    self.conn.execute(alter_sql)
        except Exception as e:
            logger.warning("Migration step failed: %s", e)

    def _ensure_columns(self, table: str, migrations: list) -> None:
        """Add multiple columns to a table if they don't exist."""
        try:
            if self._engine == "postgresql":
                existing = set(r[0] for r in self.conn.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = %s", (table,)
                ).fetchall())
                for column, alter_sql in migrations:
                    if column not in existing:
                        try:
                            self.conn.execute(alter_sql)
                        except Exception as e:
                            logger.warning("Migration step failed for %s.%s: %s", table, column, e)
            else:
                cols = [r[1] for r in self.conn.execute(f"PRAGMA table_xinfo({table})").fetchall()]
                for column, alter_sql in migrations:
                    if column not in cols:
                        try:
                            self.conn.execute(alter_sql)
                        except Exception as e:
                            logger.warning("Migration step failed for %s.%s: %s", table, column, e)
        except Exception as e:
            logger.warning("Migration step failed for table %s: %s", table, e)

    def _ensure_foreign_key(self, table: str, column: str, ref_table: str, ref_column: str = "id", on_delete: str = "SET NULL") -> None:
        """Ensure a foreign key exists, creating it if possible.

        For PostgreSQL: executes ALTER TABLE ADD CONSTRAINT.
        For SQLite: enables the foreign_keys pragma and logs the relationship
        (SQLite does not support ALTER TABLE ADD CONSTRAINT after table creation).
        """
        if self._engine == "postgresql":
            fk_name = f"fk_{table}_{column}"
            try:
                self.conn.execute(f"""
                    ALTER TABLE {table} ADD CONSTRAINT {fk_name}
                    FOREIGN KEY ({column}) REFERENCES {ref_table}({ref_column})
                    ON DELETE {on_delete}
                """)
                logger.info("Added FK %s on %s.%s → %s.%s (CASCADE=%s)", fk_name, table, column, ref_table, ref_column, on_delete)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    raise
        else:
            self.conn.execute("PRAGMA foreign_keys = ON")
            logger.info("FK %s.%s → %s.%s enforced at app level (SQLite, ON DELETE %s)", table, column, ref_table, ref_column, on_delete)

    def _run_column_migrations(self):
        """Apply all schema migrations — add columns, indices that may be missing."""
        S = _schema
        self._ensure_columns("documents", [
            ("text_content", S.ALTER_DOCUMENTS_ADD_TEXT_CONTENT),
            ("expiry_date", S.ALTER_DOCUMENTS_ADD_EXPIRY_DATE),
            ("signed_by", S.ALTER_DOCUMENTS_ADD_SIGNED_BY),
            ("signed_at", S.ALTER_DOCUMENTS_ADD_SIGNED_AT),
            ("copy_type", "ALTER TABLE documents ADD COLUMN copy_type TEXT DEFAULT ''"),
            ("cmr_number", "ALTER TABLE documents ADD COLUMN cmr_number TEXT DEFAULT ''"),
            ("cmr_metadata_json", "ALTER TABLE documents ADD COLUMN cmr_metadata_json TEXT DEFAULT '{}'"),
            ("is_signed", "ALTER TABLE documents ADD COLUMN is_signed INTEGER DEFAULT 0"),
            ("extracted_data_json", S.ALTER_DOCUMENTS_ADD_EXTRACTED_DATA),
            ("automation_tags", S.ALTER_DOCUMENTS_ADD_AUTOMATION_TAGS),
            ("ocr_text", S.ALTER_DOCUMENTS_ADD_OCR_TEXT),
            ("ocr_run_at", S.ALTER_DOCUMENTS_ADD_OCR_RUN_AT),
            ("ocr_engine", S.ALTER_DOCUMENTS_ADD_OCR_ENGINE),
        ])
        try:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_copy_type ON documents(copy_type)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_cmr_number ON documents(cmr_number)")
        except Exception as e:
            logger.warning("Migration step failed: %s", e)

        self._ensure_columns("trips", [
            ("reference", "ALTER TABLE trips ADD COLUMN reference TEXT DEFAULT ''"),
            ("context_json", "ALTER TABLE trips ADD COLUMN context_json TEXT"),
            ("route_history_v2_id", "ALTER TABLE trips ADD COLUMN route_history_v2_id INTEGER REFERENCES route_history_v2(id)"),
            ("truck_consumption_l_per_100km", "ALTER TABLE trips ADD COLUMN truck_consumption_l_per_100km REAL"),
            ("client_id", "ALTER TABLE trips ADD COLUMN client_id INTEGER REFERENCES clients(id)"),
            ("driver_id", "ALTER TABLE trips ADD COLUMN driver_id INTEGER REFERENCES drivers(id)"),
            ("truck_id", S.ALTER_TRIPS_ADD_TRUCK_ID),
            ("price_pre_vat", "ALTER TABLE trips ADD COLUMN price_pre_vat REAL DEFAULT 0"),
            ("vat_percent", "ALTER TABLE trips ADD COLUMN vat_percent REAL DEFAULT 0"),
            ("cmr_number", "ALTER TABLE trips ADD COLUMN cmr_number TEXT"),
            ("cmr_sequence", "ALTER TABLE trips ADD COLUMN cmr_sequence INTEGER"),
            ("cargo_description", "ALTER TABLE trips ADD COLUMN cargo_description TEXT"),
            ("cargo_marks", "ALTER TABLE trips ADD COLUMN cargo_marks TEXT"),
            ("package_count", "ALTER TABLE trips ADD COLUMN package_count INTEGER"),
            ("package_type", "ALTER TABLE trips ADD COLUMN package_type TEXT"),
            ("gross_weight_kg", "ALTER TABLE trips ADD COLUMN gross_weight_kg REAL"),
            ("volume_m3", "ALTER TABLE trips ADD COLUMN volume_m3 REAL"),
            ("hs_code", "ALTER TABLE trips ADD COLUMN hs_code TEXT"),
            ("carrier_instructions", "ALTER TABLE trips ADD COLUMN carrier_instructions TEXT"),
            ("carrier_reservations", "ALTER TABLE trips ADD COLUMN carrier_reservations TEXT"),
            ("special_agreements", "ALTER TABLE trips ADD COLUMN special_agreements TEXT"),
            ("carriage_payer", "ALTER TABLE trips ADD COLUMN carriage_payer TEXT"),
            ("documents_attached", "ALTER TABLE trips ADD COLUMN documents_attached TEXT"),
            ("place_of_loading", "ALTER TABLE trips ADD COLUMN place_of_loading TEXT"),
            ("place_of_loading_date", "ALTER TABLE trips ADD COLUMN place_of_loading_date TEXT"),
            ("loading_country", "ALTER TABLE trips ADD COLUMN loading_country TEXT"),
            ("delivery_country", "ALTER TABLE trips ADD COLUMN delivery_country TEXT"),
            ("adr_info_json", "ALTER TABLE trips ADD COLUMN adr_info_json TEXT"),
            ("cmr_status", "ALTER TABLE trips ADD COLUMN cmr_status TEXT DEFAULT 'draft'"),
            ("cmr_remarks", "ALTER TABLE trips ADD COLUMN cmr_remarks TEXT"),
            ("transport_order_number", "ALTER TABLE trips ADD COLUMN transport_order_number TEXT DEFAULT ''"),
            ("dispatch_reference", "ALTER TABLE trips ADD COLUMN dispatch_reference TEXT DEFAULT ''"),
            ("promised_date", "ALTER TABLE trips ADD COLUMN promised_date TEXT"),
        ])
        try:
            self.conn.execute(S.INDEX_TRIPS_TRUCK_ID)
        except Exception as e:
            logger.warning("Migration step failed: %s", e)
        try:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_trips_cmr_status ON trips(cmr_status)")
        except Exception as e:
            logger.warning("Migration step failed: %s", e)
        try:
            self._ensure_column("trips", "month", S.ALTER_TRIPS_ADD_MONTH)
        except Exception as e:
            logger.warning(
                "Could not add month generated column (SQLite < 3.31 or unsupported): %s", e
            )
            # Fallback: add a regular TEXT column and backfill
            try:
                self._ensure_column(
                    "trips", "month",
                    "ALTER TABLE trips ADD COLUMN month TEXT",
                )
                self.conn.execute("UPDATE trips SET month = SUBSTR(created_at, 1, 7) WHERE month IS NULL AND created_at IS NOT NULL")
            except Exception as e2:
                logger.warning("Month column fallback also failed: %s", e2)

        self._ensure_column("trucks", "tachograph_expiry", "ALTER TABLE trucks ADD COLUMN tachograph_expiry TEXT")
        self._ensure_column("trucks", "tracking_device_id", S.ALTER_TRUCKS_ADD_TRACKING_DEVICE_ID)
        self._ensure_columns("trucks", [
            ("trailer_plate", "ALTER TABLE trucks ADD COLUMN trailer_plate TEXT DEFAULT ''"),
            ("max_payload_kg", "ALTER TABLE trucks ADD COLUMN max_payload_kg REAL DEFAULT 0"),
            ("cmr_insurance_number", "ALTER TABLE trucks ADD COLUMN cmr_insurance_number TEXT DEFAULT ''"),
            ("cmr_insurance_expiry", "ALTER TABLE trucks ADD COLUMN cmr_insurance_expiry TEXT DEFAULT ''"),
        ])

        self._ensure_columns("drivers", [
            ("passport_number", "ALTER TABLE drivers ADD COLUMN passport_number TEXT DEFAULT ''"),
            ("passport_expiry", "ALTER TABLE drivers ADD COLUMN passport_expiry TEXT DEFAULT ''"),
            ("adr_certificate", "ALTER TABLE drivers ADD COLUMN adr_certificate TEXT DEFAULT ''"),
            ("adr_certificate_expiry", "ALTER TABLE drivers ADD COLUMN adr_certificate_expiry TEXT DEFAULT ''"),
            ("driver_card_number", "ALTER TABLE drivers ADD COLUMN driver_card_number TEXT DEFAULT ''"),
        ])

        self._ensure_columns("clients", [
            ("client_type", S.ALTER_CLIENTS_ADD_TYPE),
            ("payment_terms_days", S.ALTER_CLIENTS_ADD_PAYMENT_TERMS),
            ("credit_limit_eur", S.ALTER_CLIENTS_ADD_CREDIT_LIMIT),
            ("default_rate_per_km", S.ALTER_CLIENTS_ADD_DEFAULT_RATE),
            ("rating", S.ALTER_CLIENTS_ADD_RATING),
            ("eori_number", "ALTER TABLE clients ADD COLUMN eori_number TEXT DEFAULT ''"),
            ("country", "ALTER TABLE clients ADD COLUMN country TEXT DEFAULT ''"),
            ("county", "ALTER TABLE clients ADD COLUMN county TEXT DEFAULT ''"),
            ("consignee_contact_name", "ALTER TABLE clients ADD COLUMN consignee_contact_name TEXT DEFAULT ''"),
            ("consignee_contact_phone", "ALTER TABLE clients ADD COLUMN consignee_contact_phone TEXT DEFAULT ''"),
        ])

        # ── Sent-email dedup table: tenant-scoped reads/writes ──
        self._ensure_column("sent_emails", "company_id", S.ALTER_SENT_EMAILS_ADD_COMPANY_ID)

        # ── Invoice table: add all columns required by InvoiceRepository ──
        self._ensure_columns("invoices", [
            ("client_id", "ALTER TABLE invoices ADD COLUMN client_id INTEGER REFERENCES clients(id)"),
            ("currency", "ALTER TABLE invoices ADD COLUMN currency TEXT DEFAULT 'EUR'"),
            ("notes", "ALTER TABLE invoices ADD COLUMN notes TEXT DEFAULT ''"),
            ("line_items_json", "ALTER TABLE invoices ADD COLUMN line_items_json TEXT DEFAULT '[]'"),
            ("subtotal_net", "ALTER TABLE invoices ADD COLUMN subtotal_net REAL DEFAULT 0"),
            ("total_vat", "ALTER TABLE invoices ADD COLUMN total_vat REAL DEFAULT 0"),
            ("total_gross", "ALTER TABLE invoices ADD COLUMN total_gross REAL DEFAULT 0"),
            ("pdf_path", "ALTER TABLE invoices ADD COLUMN pdf_path TEXT DEFAULT ''"),
            ("created_at", "ALTER TABLE invoices ADD COLUMN created_at TEXT"),
            ("updated_at", "ALTER TABLE invoices ADD COLUMN updated_at TEXT"),
            # Romanian e-Factura readiness fields
            ("exchange_rate", "ALTER TABLE invoices ADD COLUMN exchange_rate REAL DEFAULT 1.0"),
            ("invoice_type", "ALTER TABLE invoices ADD COLUMN invoice_type TEXT DEFAULT 'invoice'"),
            ("amount_paid", "ALTER TABLE invoices ADD COLUMN amount_paid REAL DEFAULT 0"),
            ("amount_remaining", "ALTER TABLE invoices ADD COLUMN amount_remaining REAL DEFAULT 0"),
            # E-Factura XML artifact tracking (the XML FILE is the legal
            # deliverable; no ANAF submission chain exists).
            ("efactura_status", "ALTER TABLE invoices ADD COLUMN efactura_status TEXT DEFAULT ''"),
            ("efactura_xml_path", "ALTER TABLE invoices ADD COLUMN efactura_xml_path TEXT DEFAULT ''"),
        ])

        # ── Invoice number sequence table (race-condition-safe) ──────────
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS invoice_number_sequences (
                    series TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    last_number INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (series, year)
                )
            """)
            logger.info("invoice_number_sequences table created")
        except Exception as e:
            logger.warning("Failed to create invoice_number_sequences: %s", e)

        # ── Invoice status history table ─────────────────────────────────
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS invoice_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
                    from_status TEXT NOT NULL DEFAULT '',
                    to_status TEXT NOT NULL,
                    changed_by INTEGER DEFAULT 0,
                    changed_at TEXT NOT NULL,
                    reason TEXT DEFAULT ''
                )
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_inv_status_history_invoice
                ON invoice_status_history(invoice_id)
            """)
            logger.info("invoice_status_history table created")
        except Exception as e:
            logger.warning("Failed to create invoice_status_history: %s", e)

        # ── Migration: make document_package.trip_id nullable ────────────
        try:
            cols = [r[1] for r in self.conn.execute(
                "PRAGMA table_info(document_package)"
            ).fetchall()]
            if "trip_id" in cols:
                # Check if trip_id is still NOT NULL
                info = self.conn.execute(
                    "PRAGMA table_info(document_package)"
                ).fetchall()
                for col in info:
                    if col[1] == "trip_id" and col[3] == 1:  # 1 = NOT NULL
                        fk_was_on = self.conn.execute(
                            "PRAGMA foreign_keys"
                        ).fetchone()[0]
                        if fk_was_on:
                            self.conn.execute("PRAGMA foreign_keys=OFF")
                        self.conn.execute("BEGIN IMMEDIATE")
                        self.conn.execute("""
                            CREATE TABLE document_package_new (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                trip_id INTEGER,
                                package_uuid TEXT UNIQUE NOT NULL,
                                status TEXT NOT NULL DEFAULT 'draft',
                                recipient_email TEXT DEFAULT '',
                                subject TEXT DEFAULT '',
                                body TEXT DEFAULT '',
                                email_message_id TEXT DEFAULT '',
                                sent_at TEXT,
                                error_message TEXT DEFAULT '',
                                created_at TEXT NOT NULL,
                                updated_at TEXT NOT NULL
                            )
                        """)
                        self.conn.execute("""
                            INSERT INTO document_package_new
                            SELECT * FROM document_package
                        """)
                        self.conn.execute("DROP TABLE document_package")
                        self.conn.execute(
                            "ALTER TABLE document_package_new "
                            "RENAME TO document_package"
                        )
                        self.conn.execute(
                            "CREATE INDEX IF NOT EXISTS idx_package_trip "
                            "ON document_package(trip_id)"
                        )
                        self.conn.execute(
                            "CREATE INDEX IF NOT EXISTS idx_package_uuid "
                            "ON document_package(package_uuid)"
                        )
                        self.conn.execute(
                            "CREATE INDEX IF NOT EXISTS idx_package_status "
                            "ON document_package(status)"
                        )
                        self.conn.commit()
                        if fk_was_on:
                            self.conn.execute("PRAGMA foreign_keys=ON")
                        logger.info(
                            "Migrated document_package.trip_id to nullable"
                        )
                        break
        except Exception as e:
            logger.warning(
                "Migration of document_package.trip_id failed: %s", e
            )
            try:
                self.conn.rollback()
            except Exception:
                pass

        # ── Migration: update status triggers to include "processed" ──
        try:
            self.conn.execute(
                "DROP TRIGGER IF EXISTS trg_pipeline_runs_status_check"
            )
            self.conn.execute(
                "DROP TRIGGER IF EXISTS trg_pipeline_runs_status_check_upd"
            )
            self.conn.execute(S.TRIGGER_PIPELINE_RUNS_STATUS_CHECK)
            self.conn.execute(S.TRIGGER_PIPELINE_RUNS_STATUS_UPDATE)
            logger.info("Recreated status triggers with 'processed' value")
        except Exception as e:
            logger.warning("Migration of status triggers failed: %s", e)

        # ── Users: add company_id (multi-tenant migration) ──────────────
        self._ensure_column(
            "users", "company_id",
            "ALTER TABLE users ADD COLUMN company_id "
            "INTEGER REFERENCES companies(id)",
        )
        try:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id)")
        except Exception as e:
            logger.warning("Migration step failed: %s", e)

        # ── RBAC: driver FK link on users table ──────────────────────────
        self._ensure_column(
            "users", "driver_id",
            "ALTER TABLE users ADD COLUMN driver_id INTEGER REFERENCES drivers(id)"
        )
        # ── RBAC: human-readable display name ────────────────────────────
        self._ensure_column(
            "users", "display_name",
            "ALTER TABLE users ADD COLUMN display_name TEXT DEFAULT ''"
        )

        # ── Multi-tenant: add company_id to all business tables ──────────
        # NOTE: SQLite cannot ADD COLUMN with NOT NULL + REFERENCES constraint
        # on an existing table. We add a nullable column, backfill, and enforce
        # NOT NULL at the application level (see _set_company_from_context).
        _tenant_tables = [
            ("trips", "ALTER TABLE trips ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("clients", "ALTER TABLE clients ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("trucks", "ALTER TABLE trucks ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("drivers", "ALTER TABLE drivers ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("invoices", "ALTER TABLE invoices ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("documents", "ALTER TABLE documents ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("route_history_v2", "ALTER TABLE route_history_v2 ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("receipts", "ALTER TABLE receipts ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("proforma_invoices", "ALTER TABLE proforma_invoices ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            # Additional tables that need company_id for multi-tenant support
            ("routes", "ALTER TABLE routes ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("route_history", "ALTER TABLE route_history ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("alerts", "ALTER TABLE alerts ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("operation_events", "ALTER TABLE operation_events ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("trip_status_history", "ALTER TABLE trip_status_history ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("maintenance_records", "ALTER TABLE maintenance_records ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("maintenance_schedules", "ALTER TABLE maintenance_schedules ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("truck_health_scores", "ALTER TABLE truck_health_scores ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("gps_telemetry", "ALTER TABLE gps_telemetry ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("document_pipeline_runs", "ALTER TABLE document_pipeline_runs ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("document_package", "ALTER TABLE document_package ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("contracts", "ALTER TABLE contracts ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("tacho_imports", "ALTER TABLE tacho_imports ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            # P0.6: Tables newly scoped to company_id
            ("client_contacts", "ALTER TABLE client_contacts ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("client_tags", "ALTER TABLE client_tags ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("document_links", "ALTER TABLE document_links ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("document_versions", "ALTER TABLE document_versions ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("export_jobs", "ALTER TABLE export_jobs ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            # Phase B: remaining syncable tables scoped to company_id
            ("driver_truck_assignments", "ALTER TABLE driver_truck_assignments ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("tacho_driver_activity", "ALTER TABLE tacho_driver_activity ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("tacho_vehicle_data", "ALTER TABLE tacho_vehicle_data ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("email_logs", "ALTER TABLE email_logs ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
            ("invoice_reminders", "ALTER TABLE invoice_reminders ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
        ]
        # Resolve the lowest existing *real* company id ONCE.  A hardcoded
        # backfill of ``company_id = 1`` fails under PRAGMA foreign_keys=ON
        # whenever companies(1) does not exist (old DBs whose lowest company
        # id is > 1), leaving legacy documents NULL → invisible to tenant
        # queries.  The sentinel company (id=0, seeded on bootstrap) is
        # excluded so legacy rows are attributed to the first real company,
        # not the "no company" sentinel.
        try:
            _min_cid_row = self.conn.execute(
                "SELECT MIN(id) FROM companies WHERE id != 0"
            ).fetchone()
            _min_company_id = _min_cid_row[0] if _min_cid_row and _min_cid_row[0] is not None else 1
        except Exception:
            _min_company_id = 1
        for table, alter_sql in _tenant_tables:
            self._ensure_column(table, "company_id", alter_sql)
            # Backfill any rows that still have NULL company_id (legacy data)
            try:
                self.conn.execute(
                    f"UPDATE {table} SET company_id = ? WHERE company_id IS NULL",
                    (_min_company_id,),
                )
            except Exception as e:
                logger.warning("Backfill failed for %s: %s", table, e)
            try:
                self.conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_company ON {table}(company_id)"
                )
            except Exception as e:
                logger.warning("Index creation failed for %s: %s", table, e)

        # ── P0.7: Soft delete columns ─────────────────────────────────────
        # 13 business tables carry ``deleted_at`` — the desktop services
        # soft-delete into it and the sync layer propagates it.  documents is
        # included so archiving/delete_document can stamp the column.
        _soft_delete_tables = [
            "trips", "invoices", "clients", "drivers", "trucks",
            "routes", "route_history_v2", "receipts", "contracts",
            "proforma_invoices", "maintenance_records", "maintenance_schedules",
            "documents",
            # Phase B: expenses gained a deleted_at column so DELETE soft-deletes.
            "expenses",
        ]
        for table in _soft_delete_tables:
            self._ensure_column(table, "deleted_at",
                f"ALTER TABLE {table} ADD COLUMN deleted_at TEXT")
            try:
                self.conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_deleted ON {table}(deleted_at)"
                )
            except Exception as e:
                logger.warning("Soft-delete index failed for %s: %s", table, e)

        # ── Offline-first sync (Phase 0): updated_at on syncable tables ──
        # The sync layer (outbox ordering, last-write-wins conflict
        # resolution, delta pull) depends on reliable updated_at stamps.
        # AFTER UPDATE triggers stamp the canonical UTC value; here we
        # ensure the column exists on legacy databases.  Idempotent via
        # _ensure_column (column-exists check).  invoices already gets
        # updated_at from the InvoiceRepository migration block above.
        _updated_at_tables = [
            "trips", "trucks", "maintenance_records", "maintenance_schedules",
            "client_contacts", "client_tags", "driver_truck_assignments",
            "tacho_imports", "tacho_driver_activity", "tacho_vehicle_data",
            "expenses", "successive_carriers", "trip_status_history",
            "document_links", "document_versions", "sent_emails",
            "email_logs", "invoice_reminders",
            # Phase D: route_history_v2 gains updated_at for the sync layer's
            # LWW + conflict checks (the base CREATE TABLE has no updated_at).
            "route_history_v2",
        ]
        for table in _updated_at_tables:
            if not self._table_exists(table):
                # e.g. expenses is created lazily by ensure_expenses_table;
                # its CREATE TABLE already carries updated_at.
                continue
            self._ensure_column(
                table, "updated_at",
                f"ALTER TABLE {table} ADD COLUMN updated_at TEXT",
            )

        # ── Expenses: legacy DBs created by ensure_expenses_table lack
        # created_at (the base schema now declares it via TABLE_EXPENSES). ──
        if self._table_exists("expenses"):
            self._ensure_column(
                "expenses", "created_at",
                "ALTER TABLE expenses ADD COLUMN created_at TEXT",
            )

        # ── Audit log: add entity tracking columns to operation_events ───
        # Column types/defaults mirror database/schema.py TABLE_OPERATION_EVENTS
        # exactly (entity_type TEXT, entity_id TEXT, user_id INTEGER DEFAULT 0),
        # so legacy DBs converge on the same schema as fresh inits.  The
        # operation_events.company_id column is already ensured by the tenant
        # table migration above (_tenant_tables).  _ensure_columns is
        # idempotent (IF NOT EXISTS semantics) and runs on every init.
        self._ensure_columns("operation_events", [
            ("entity_type", "ALTER TABLE operation_events ADD COLUMN entity_type TEXT"),
            ("entity_id", "ALTER TABLE operation_events ADD COLUMN entity_id TEXT"),
            ("user_id", "ALTER TABLE operation_events ADD COLUMN user_id INTEGER DEFAULT 0"),
        ])

        # ── Dedupe before unique indexes ─────────────────────────────────
        # A legacy DB may contain duplicate gps_telemetry rows (same
        # truck_id, recorded_at) or copilot_insights rows (same company_id,
        # insight_type, payload) created before the unique indexes existed.
        # CREATE UNIQUE INDEX would fail on them, so delete duplicates first
        # — guarded to only run when the index is missing (once it exists the
        # data is already unique).
        if not self._index_exists("idx_gps_telemetry_unique"):
            try:
                self.conn.execute(
                    "DELETE FROM gps_telemetry WHERE rowid NOT IN "
                    "(SELECT MIN(rowid) FROM gps_telemetry "
                    "GROUP BY truck_id, recorded_at)"
                )
            except Exception as e:
                logger.warning("Dedupe gps_telemetry failed: %s", e)
        if not self._index_exists("idx_copilot_insights_dedup"):
            try:
                self.conn.execute(
                    "DELETE FROM copilot_insights WHERE rowid NOT IN "
                    "(SELECT MIN(rowid) FROM copilot_insights "
                    "GROUP BY company_id, insight_type, payload)"
                )
            except Exception as e:
                logger.warning("Dedupe copilot_insights failed: %s", e)

        # ── Additional performance indexes ───────────────────────────────
        # These reference columns (month, expiry_date, client_id,
        # company_id, ...) that only exist AFTER the column migrations above,
        # so they are created here — NOT in _create_tables_and_indices —
        # for a zero-warning first init.
        for idx_stmt in (
            S.INDEX_INVOICES_STATUS,
            S.INDEX_GPS_TRUCK_TIME,
            S.INDEX_GPS_TELEMETRY_UNIQUE,
            S.INDEX_COPILOT_INSIGHTS_DEDUP,
            S.INDEX_CMR_AUDIT_EVENT_TYPE,
            S.INDEX_EMAIL_LOGS_TRIP,
            S.INDEX_EMAIL_LOGS_STATUS,
            S.INDEX_TRIPS_COMPANY_START_DATE,
            S.INDEX_TRIPS_COMPANY_STATUS,
            S.INDEX_TRIPS_COMPANY_CREATED,
            S.INDEX_TRUCKS_COMPANY_STATUS,
            S.INDEX_INVOICES_COMPANY_STATUS,
            S.INDEX_TRIPS_CLIENT_ID,
            S.INDEX_DOCUMENTS_EXPIRY_DATE,
            S.INDEX_TRIPS_MONTH,
        ):
            try:
                self.conn.execute(idx_stmt)
            except Exception as e:
                logger.warning("Index creation failed: %s", e)

        # ── Record schema migration version ──────────────────────────────
        self.conn.execute(S.TABLE_SCHEMA_MIGRATIONS)
        try:
            self.conn.execute(S.INSERT_SCHEMA_MIGRATION_V2)
        except Exception as e:
            logger.warning("Schema migration record failed: %s", e)

        try:
            self.conn.execute(S.INSERT_SCHEMA_MIGRATION_V3)
        except Exception as e:
            logger.warning("Schema migration V3 record failed: %s", e)

        try:
            self.conn.execute(S.INSERT_SCHEMA_MIGRATION_V4)
        except Exception as e:
            logger.warning("Schema migration V4 record failed: %s", e)

        try:
            self.conn.execute(S.INSERT_SCHEMA_MIGRATION_V5)
        except Exception as e:
            logger.warning("Schema migration V5 record failed: %s", e)

        try:
            self.conn.execute(S.INSERT_SCHEMA_MIGRATION_V6)
        except Exception as e:
            logger.warning("Schema migration V6 record failed: %s", e)

        try:
            self.conn.execute(S.INSERT_SCHEMA_MIGRATION_V7)
        except Exception as e:
            logger.warning("Schema migration V7 record failed: %s", e)

        try:
            self.conn.execute(S.INSERT_SCHEMA_MIGRATION_V8)
        except Exception as e:
            logger.warning("Schema migration V8 record failed: %s", e)

        try:
            self.conn.execute(S.INSERT_SCHEMA_MIGRATION_V9)
        except Exception as e:
            logger.warning("Schema migration V9 record failed: %s", e)

        # ── Migration: settings table → composite PK (key, company_id) ──
        # This rebuilds settings with a composite PRIMARY KEY.  It must
        # tolerate the surrounding transaction state: earlier steps in
        # _run_column_migrations (tenant backfill UPDATEs) have already opened
        # an implicit transaction, so issuing BEGIN IMMEDIATE here raised
        # "cannot start a transaction within a transaction" and the old
        # unconditional rollback in the except handler then discarded every
        # migration applied so far in that ambient transaction (including the
        # operation_events audit columns above).  We only BEGIN/COMMIT when no
        # transaction is already open and never roll back an ambient
        # transaction on failure.
        try:
            conn = self.conn
            settings_cols = [r[1] for r in conn.execute(
                "PRAGMA table_info(settings)"
            ).fetchall()]
            pk_cols = [r[1] for r in conn.execute(
                "PRAGMA table_info(settings)"
            ).fetchall() if r[5] > 0]  # r[5] = pk flag
            # Old schema: key TEXT PRIMARY KEY (pk_cols = ["key"])
            # New schema: composite PRIMARY KEY (key, company_id)
            if pk_cols == ["key"] and "company_id" not in pk_cols:
                logger.info("Migrating settings table to composite PK (key, company_id)")
                fk_was_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                was_in_tx = bool(getattr(conn, "in_transaction", False))
                # Very old settings tables have no company_id column at all;
                # add it (NULL default) so the INSERT ... SELECT below can
                # backfill the tenant scope.  SQLite permits ADD COLUMN with a
                # REFERENCES clause when the new column defaults to NULL.
                if "company_id" not in settings_cols:
                    conn.execute(
                        "ALTER TABLE settings ADD COLUMN company_id "
                        "INTEGER REFERENCES companies(id)"
                    )
                if fk_was_on and not was_in_tx:
                    conn.execute("PRAGMA foreign_keys=OFF")
                if not was_in_tx:
                    conn.execute("BEGIN IMMEDIATE")
                conn.execute("""
                    CREATE TABLE settings_new (
                        key TEXT NOT NULL,
                        value TEXT,
                        company_id INTEGER REFERENCES companies(id),
                        PRIMARY KEY (key, company_id)
                    )
                """)
                # Backfill legacy rows to the lowest real company (the sentinel
                # id=0 is excluded) rather than a hardcoded 1 — companies(1)
                # may not exist on migrated DBs and FK enforcement is on.
                conn.execute("""
                    INSERT INTO settings_new (key, value, company_id)
                    SELECT key, value,
                           COALESCE(company_id,
                                    (SELECT MIN(id) FROM companies WHERE id != 0))
                    FROM settings
                """)
                conn.execute("DROP TABLE settings")
                conn.execute("ALTER TABLE settings_new RENAME TO settings")
                if not was_in_tx:
                    conn.commit()
                if fk_was_on and not was_in_tx:
                    conn.execute("PRAGMA foreign_keys=ON")
                logger.info("Settings table migration to composite PK complete")
        except Exception as e:
            logger.warning("Settings table migration failed (may be already migrated): %s", e)
            try:
                # Roll back only when we opened the transaction ourselves;
                # inside an ambient transaction a rollback would silently
                # discard every other migration applied so far in this init.
                if not bool(getattr(self.conn, "in_transaction", False)):
                    self.conn.rollback()
            except Exception:
                pass

        # ── R1 (Phase E): id tiebreak watermark column on the desktop's
        # sync_cursors table (idempotent — existing tables lack it).
        self._ensure_column(
            "sync_cursors", "last_id",
            "ALTER TABLE sync_cursors ADD COLUMN last_id INTEGER NOT NULL DEFAULT 0",
        )

        # ── Ensure foreign key constraints (PostgreSQL ALTER, SQLite app-level) ──
        # Trips → core entities (SET NULL to preserve trip data when ref is deleted)
        self._ensure_foreign_key("trips", "client_id", "clients", on_delete="SET NULL")
        self._ensure_foreign_key("trips", "driver_id", "drivers", on_delete="SET NULL")
        self._ensure_foreign_key("trips", "truck_id", "trucks", on_delete="SET NULL")
        # Maintenance → cascade with truck
        self._ensure_foreign_key("maintenance_records", "truck_id", "trucks", on_delete="CASCADE")
        self._ensure_foreign_key("maintenance_schedules", "truck_id", "trucks", on_delete="CASCADE")
        self._ensure_foreign_key("truck_health_scores", "truck_id", "trucks", on_delete="CASCADE")
        # Driver-truck assignments → cascade with both sides
        self._ensure_foreign_key("driver_truck_assignments", "truck_id", "trucks", on_delete="CASCADE")
        self._ensure_foreign_key("driver_truck_assignments", "driver_id", "drivers", on_delete="CASCADE")
        self._ensure_column("driver_truck_assignments", "active",
                            "ALTER TABLE driver_truck_assignments ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        # Alerts and status history → cascade with trip
        self._ensure_foreign_key("alerts", "trip_id", "trips", on_delete="CASCADE")
        self._ensure_foreign_key("trip_status_history", "trip_id", "trips", on_delete="CASCADE")

        # Phase A (multi-device): add device_id to sync_server_map and rebuild
        # its UNIQUE key to (company_id, device_id, entity_type, local_id).
        self._migrate_sync_server_map_device_id()

        try:
            self.conn.commit()
        except Exception as e:
            logger.warning("Migration step failed: %s", e)

        self._seed_automail_defaults()

    def _migrate_sync_server_map_device_id(self) -> None:
        """Phase A: add device_id to sync_server_map and rebuild its UNIQUE key.

        Multi-device support keys the server id map by
        ``(company_id, device_id, entity_type, local_id)``.  For existing
        SQLite DBs the table must be rebuilt (SQLite cannot alter a UNIQUE
        constraint in place); legacy rows get ``device_id = ''`` (the
        single-device namespace).  Idempotent — skips when the table already
        has the device_id-aware key.
        """
        if self._engine == "postgresql":
            return
        # Clean up any leftover state from a previously interrupted migration.
        # This must run BEFORE the sync_server_map existence check below: a
        # crash between RENAME and CREATE leaves only sync_server_map_old (and
        # _create_tables_and_indices may have re-created an empty
        # sync_server_map).  sync_server_map_old always holds the authoritative
        # pre-migration data, so restore it and let the normal migration flow
        # re-run (idempotent).  This handles both crash points: between RENAME
        # and CREATE, and after CREATE before DROP.
        if self._table_exists("sync_server_map_old"):
            self.conn.execute("DROP TABLE IF EXISTS sync_server_map")
            self.conn.execute("ALTER TABLE sync_server_map_old RENAME TO sync_server_map")
            self.conn.commit()
        if not self._table_exists("sync_server_map"):
            return
        # Add the column if missing (fresh DBs already have it from CREATE
        # TABLE; legacy DBs get it via ALTER).
        self._ensure_column(
            "sync_server_map", "device_id",
            "ALTER TABLE sync_server_map ADD COLUMN device_id TEXT DEFAULT ''",
        )
        # Rebuild only when the unique index does NOT yet include device_id.
        # We cannot rely on the CREATE statement: SQLite's ALTER TABLE ADD
        # COLUMN rewrites sqlite_master.sql to include the new column, so
        # "device_id in sql" is true even when the UNIQUE key is still the
        # old (company, entity, local_id).  Inspect the actual index columns.
        indexes = self.conn.execute(
            "PRAGMA index_list(sync_server_map)"
        ).fetchall()
        for idx in indexes:
            if not idx["unique"]:
                continue
            cols = [r["name"] for r in self.conn.execute(
                f"PRAGMA index_info({idx['name']})"
            ).fetchall()]
            if "device_id" in cols:
                return  # already device_id-aware
        # Rebuild the table atomically.  Python sqlite3 legacy mode autocommits
        # DDL, so without an explicit transaction a crash between RENAME and
        # the INSERT would leave the new (empty) table present and the next
        # boot would skip the migration — silently losing the map.  SQLite DDL
        # IS transactional inside an explicit BEGIN IMMEDIATE, so wrap the
        # whole rebuild in one transaction and roll back on failure.
        was_in_tx = bool(getattr(self.conn, "in_transaction", False))
        try:
            if not was_in_tx:
                self.conn.execute("BEGIN IMMEDIATE")
            self.conn.execute("ALTER TABLE sync_server_map RENAME TO sync_server_map_old")
            self.conn.execute(_schema.TABLE_SYNC_SERVER_MAP)
            self.conn.execute(
                "INSERT INTO sync_server_map "
                "(company_id, device_id, entity_type, local_id, server_id, created_at) "
                "SELECT company_id, '', entity_type, local_id, server_id, created_at "
                "FROM sync_server_map_old"
            )
            self.conn.execute("DROP TABLE sync_server_map_old")
            if not was_in_tx:
                self.conn.commit()
            logger.info("sync_server_map rebuilt with device_id-aware unique key")
        except Exception as e:
            if not was_in_tx:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            logger.warning("sync_server_map device_id migration failed: %s", e)

    def _migrate_sync_server_map_device_id_pg(self) -> None:
        """Phase A: add device_id to sync_server_map and rebuild its UNIQUE key (PG).

        Name-independent: discovers and drops any old unique constraint OR
        standalone unique index on the (company_id, entity_type, local_id)
        key (via ``pg_constraint`` / ``pg_index``), then adds the new
        (company_id, device_id, entity_type, local_id) key if missing.  The
        DROP is gated on the old key actually existing, so it runs once (a
        one-time migration, not a per-boot rebuild).  Failures are logged at
        WARNING — a failed ADD would silently leave the table with no unique
        key.
        """
        if self._engine != "postgresql":
            return
        try:
            cur = self.conn.cursor()
            cur.execute(
                "ALTER TABLE sync_server_map ADD COLUMN IF NOT EXISTS device_id TEXT DEFAULT ''"
            )
            cur.close()
        except Exception as e:
            logger.warning("sync_server_map device_id column migration failed: %s", e)
            return
        # Drop any old unique constraint/index that does NOT include device_id.
        # The standalone-index loop excludes the PRIMARY KEY backing index and
        # any constraint-backed index (see _PG_SYNC_SERVER_MAP_DROP_OLD), and
        # each EXECUTE is wrapped so one bad drop cannot roll back the rest.
        try:
            cur = self.conn.cursor()
            cur.execute(_PG_SYNC_SERVER_MAP_DROP_OLD)
            cur.close()
        except Exception as e:
            logger.warning("sync_server_map old-key drop failed: %s", e)
        # Add the new unique key if missing.
        try:
            cur = self.conn.cursor()
            cur.execute(_PG_SYNC_SERVER_MAP_ADD_NEW)
            cur.close()
        except Exception as e:
            logger.warning("sync_server_map device_id unique key migration failed: %s", e)

    def _ensure_documents_fts(self) -> None:
        """Create the documents_fts external-content triggers and rebuild index.

        The FTS triggers reference documents columns (text_content,
        cmr_number, extracted_data_json, ...) that only exist AFTER
        ``_run_column_migrations`` runs, so they are created here — after
        migrations — and the index is rebuilt so existing rows are searchable.
        """
        if self._engine == "postgresql":
            return
        S = _schema
        try:
            for stmt in (S.TRIGGER_DOCUMENTS_FTS_INSERT,
                         S.TRIGGER_DOCUMENTS_FTS_DELETE,
                         S.TRIGGER_DOCUMENTS_FTS_UPDATE):
                self.conn.execute(stmt)
            self.conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
            self.conn.commit()
            logger.info("documents_fts triggers recreated and index rebuilt")
        except Exception as e:
            logger.warning("FTS trigger creation failed: %s", e)

    def _ensure_updated_at_triggers(self) -> None:
        """Create the ``updated_at`` stamping triggers (AFTER INSERT + AFTER UPDATE).

        Runs AFTER ``_run_column_migrations`` so the ``updated_at`` column
        exists on every syncable table (legacy DBs get it via ALTER first).
        The triggers are DROP + CREATE on every boot (NOT ``CREATE TRIGGER
        IF NOT EXISTS``): the ``sync_in_progress`` echo-suppression guard
        (added in the Phase 3 remediation pass) would otherwise never reach
        existing installs — ``IF NOT EXISTS`` silently keeps the old
        guard-less DDL.  The expenses table is created lazily by
        ``ensure_expenses_table``; if it does not exist yet the trigger
        creation is skipped and retried on the next boot.
        """
        if self._engine == "postgresql":
            return
        S = _schema
        dropped: set = set()
        for stmt in (*S.TRIGGERS_UPDATED_AT, *S.TRIGGERS_UPDATED_AT_INSERT):
            # "CREATE TRIGGER IF NOT EXISTS trg_<table>_updated_at AFTER UPDATE ..."
            m = re.search(r"\bON\s+(\w+)", stmt)
            table = m.group(1) if m else None
            if table is None or not self._table_exists(table):
                # e.g. expenses is created lazily by ensure_expenses_table;
                # the trigger is picked up on the next boot.
                continue
            try:
                # DROP both triggers ONCE per table so the sync_in_progress
                # guard is applied to existing installs (see docstring).
                # Dropping per-statement would delete the sibling trigger
                # created by the other statement in this loop.
                if table not in dropped:
                    dropped.add(table)
                    self.conn.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at")
                    self.conn.execute(f"DROP TRIGGER IF EXISTS trg_{table}_insert_updated_at")
                self.conn.execute(stmt)
            except Exception as e:
                logger.error("updated_at trigger creation failed for %s: %s", table, e)
        try:
            self.conn.commit()
        except Exception as e:
            logger.error("updated_at trigger commit failed: %s", e)

    def _ensure_outbox_triggers(self) -> None:
        """Create the ``sync_outbox`` capture triggers (AFTER INSERT/UPDATE/DELETE).

        Every write to a v1-push-scope table records an entry in
        ``sync_outbox`` so the sync engine (Phase 2+) can push it to the
        cloud API.  The DDL is generated programmatically per table because
        the DELETE payload needs the table's live column list
        (``PRAGMA table_info``) to build ``json_object('col', OLD."col",
        ...)`` — the row is gone by push time, so it must be serialized at
        delete time.

        Capture scope = Phase B: ALL of ``SYNCABLE_ENTITIES`` (25 tables).
        The Phase B push/pull lanes support every entity type, so every
        syncable table gets outbox triggers.  The 15 non-V1 tables previously
        got only the Phase 0 updated_at stamping triggers — the DROP+CREATE
        per boot now adds their outbox triggers automatically.

        ``entity_type`` is stored as the SINGULAR entity type from
        ``SYNCABLE_ENTITIES`` (e.g. ``'trip'``, not ``'trips'``) so it
        matches the push API contract (``backend/api/v1/sync.py``
        ``SUPPORTED_ENTITY_TYPES``).

        Echo suppression: all three triggers skip when
        ``sync_meta.sync_in_progress = '1'`` so the pull-apply path
        (Phase 4) does not re-capture rows it just wrote.

        The UPDATE trigger uses ``AFTER UPDATE OF <cols except updated_at>``
        so the nested ``updated_at`` stamp UPDATE fired by the Phase 0
        stamping triggers (which only touches ``updated_at``) does NOT
        produce a spurious outbox row — an INSERT yields exactly one
        outbox row (op='INSERT') and an UPDATE exactly one (op='UPDATE').

        The outbox triggers are DROP + CREATE on every boot (NOT
        ``CREATE TRIGGER IF NOT EXISTS``): the DELETE payload embeds the
        table's live column list, and ``IF NOT EXISTS`` would silently keep
        a stale column list after an ``ALTER TABLE ADD COLUMN`` migration.
        The updated_at stamping triggers stay ``CREATE TRIGGER IF NOT
        EXISTS`` (they embed no column lists).  Runs AFTER
        ``_run_column_migrations`` so every column (including ``updated_at``
        on legacy DBs) exists when the DDL is generated.
        """
        if self._engine == "postgresql":
            return
        for table, entity_type in _schema.SYNCABLE_ENTITIES.items():
            if not self._table_exists(table):
                continue
            try:
                col_info = [
                    r for r in self.conn.execute(
                        f"PRAGMA table_info({table})"
                    ).fetchall()
                ]
            except Exception as e:
                logger.error("outbox trigger: could not introspect %s: %s", table, e)
                continue
            if not col_info:
                continue
            cols = [r[1] for r in col_info]
            # Phase D: BLOB columns (e.g. route_history_v2.geometry_compressed)
            # cannot be serialized into the DELETE payload's json_object — SQLite
            # raises "JSON cannot hold BLOB values".  They are dropped from the
            # frozen payload (binary columns are not syncable anyway).
            blob_cols = {
                r[1] for r in col_info if (r[2] or "").upper() == "BLOB"
            }
            json_cols = [c for c in cols if c not in blob_cols]
            # Columns that can carry a business change — everything except
            # the trigger-stamped updated_at column.
            update_of_cols = [c for c in cols if c != "updated_at"]
            if not update_of_cols:
                logger.warning("outbox trigger: %s has no business columns, skipping", table)
                continue
            json_args = ", ".join(f"'{c}', OLD.\"{c}\"" for c in json_cols)
            # DROP first so the embedded json_object column list is rebuilt
            # fresh on every boot (see docstring).
            drop_statements = [
                f"DROP TRIGGER IF EXISTS trg_{table}_outbox_ai",
                f"DROP TRIGGER IF EXISTS trg_{table}_outbox_au",
                f"DROP TRIGGER IF EXISTS trg_{table}_outbox_ad",
            ]
            statements = [
                (
                    f"CREATE TRIGGER trg_{table}_outbox_ai "
                    f"AFTER INSERT ON {table} FOR EACH ROW "
                    f"WHEN NOT EXISTS (SELECT 1 FROM sync_meta WHERE key='sync_in_progress' AND value='1') "
                    f"BEGIN INSERT INTO sync_outbox (entity_type, op, local_id) "
                    f"VALUES ('{entity_type}', 'INSERT', NEW.id); END;"
                ),
                (
                    f"CREATE TRIGGER trg_{table}_outbox_au "
                    f"AFTER UPDATE OF {', '.join(update_of_cols)} ON {table} FOR EACH ROW "
                    f"WHEN NOT EXISTS (SELECT 1 FROM sync_meta WHERE key='sync_in_progress' AND value='1') "
                    f"BEGIN INSERT INTO sync_outbox (entity_type, op, local_id) "
                    f"VALUES ('{entity_type}', 'UPDATE', NEW.id); END;"
                ),
                (
                    f"CREATE TRIGGER trg_{table}_outbox_ad "
                    f"AFTER DELETE ON {table} FOR EACH ROW "
                    f"WHEN NOT EXISTS (SELECT 1 FROM sync_meta WHERE key='sync_in_progress' AND value='1') "
                    f"BEGIN INSERT INTO sync_outbox (entity_type, op, local_id, payload_json) "
                    f"VALUES ('{entity_type}', 'DELETE', OLD.id, json_object({json_args})); END;"
                ),
            ]
            for stmt in drop_statements + statements:
                try:
                    self.conn.execute(stmt)
                except Exception as e:
                    logger.error("outbox trigger creation failed for %s: %s", table, e)
        try:
            self.conn.commit()
        except Exception as e:
            logger.error("outbox trigger commit failed: %s", e)

    def _migrate_legacy_data(self):
        """One-off data migrations (legacy maintenance table, etc.)."""
        try:
            has_legacy = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance'"
            ).fetchone()
            has_records = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_records'"
            ).fetchone()
            if has_legacy and has_records:
                migrated = self.conn.execute("""
                    INSERT OR IGNORE INTO maintenance_records
                    (truck_id, maintenance_type, date, km, cost, notes, created_at)
                    SELECT truck_id, type, date, km_at_service, cost, description,
                           COALESCE(date, datetime('now'))
                    FROM maintenance
                """).rowcount
                if migrated > 0:
                    self.conn.execute("DROP TABLE maintenance")
                    self.conn.commit()
                    logger.info("Migrated %d legacy maintenance records and dropped old table", migrated)
        except Exception as e:
            logger.warning("Migration step failed: %s", e)

    def _seed_automail_defaults(self):
        """Seed default AutoMail templates, schedules, and settings if empty.

        This runs once on first database init to ensure the system is
        immediately usable with sensible defaults mirroring the original
        hardcoded DunnerEngine behavior.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            # Ensure tables exist before querying (handles DBs created
            # before automail tables were added to the schema).
            self.conn.execute(_schema.TABLE_AUTOMAIL_TEMPLATES)
            self.conn.execute(_schema.TABLE_AUTOMAIL_SCHEDULES)
            self.conn.execute(_schema.TABLE_AUTOMAIL_CLIENT_OVERRIDES)
            self.conn.execute(_schema.TABLE_AUTOMAIL_SETTINGS)

            # ── Seed templates if empty ──────────────────────────────────
            count = self.conn.execute(
                "SELECT COUNT(*) AS cnt FROM automail_templates"
            ).fetchone()["cnt"]
            if count == 0:
                templates = [
                    (
                        "Default",
                        "Payment Notice: Invoice {invoice_number} / {company_name}",
                        "Dear Accounts Payable Team,\n\n"
                        "This is an automated notification regarding invoice {invoice_number} "
                        "({total_amount} {currency}), due on {due_date}.\n\n"
                        "Please find the relevant documents attached.\n\n"
                        "Thank you for your prompt attention.\n\n"
                        "Best regards,\n{company_name}\n\nGenerated via Operion ERP",
                        "<p>Dear Accounts Payable Team,</p>"
                        "<p>This is an automated notification regarding invoice "
                        "<strong>{invoice_number}</strong> ({total_amount} {currency}), "
                        "due on <strong>{due_date}</strong>.</p>"
                        "<p>Please find the relevant documents attached.</p>"
                        "<p>Thank you for your prompt attention.</p>"
                        "<p>Best regards,<br>{company_name}</p>"
                        "<hr><small>Generated via Operion ERP</small>",
                        1,
                    ),
                    (
                        "Friendly",
                        "Upcoming Payment: Invoice {invoice_number} / {company_name}",
                        "Dear Accounts Payable Team,\n\n"
                        "This is a friendly reminder that invoice {invoice_number} "
                        "({total_amount} {currency}) is due on {due_date}.\n\n"
                        "Please let us know if you require any additional information.\n\n"
                        "Thank you for your continued partnership.\n\n"
                        "Best regards,\n{company_name}",
                        "<p>Dear Accounts Payable Team,</p>"
                        "<p>This is a friendly reminder that invoice "
                        "<strong>{invoice_number}</strong> ({total_amount} {currency}) "
                        "is due on <strong>{due_date}</strong>.</p>"
                        "<p>Please let us know if you require any additional information.</p>"
                        "<p>Thank you for your continued partnership.</p>"
                        "<p>Best regards,<br>{company_name}</p>",
                        0,
                    ),
                    (
                        "Professional",
                        "Invoice {invoice_number} — Payment Reminder / {company_name}",
                        "Dear Accounts Payable Team,\n\n"
                        "This is a professional reminder that invoice {invoice_number} "
                        "({total_amount} {currency}) is scheduled for payment on {due_date}.\n\n"
                        "Kindly ensure the payment is processed by the due date. "
                        "If already executed, please disregard this message.\n\n"
                        "Sincerely,\n{company_name}",
                        "<p>Dear Accounts Payable Team,</p>"
                        "<p>This is a professional reminder that invoice "
                        "<strong>{invoice_number}</strong> ({total_amount} {currency}) "
                        "is scheduled for payment on <strong>{due_date}</strong>.</p>"
                        "<p>Kindly ensure the payment is processed by the due date. "
                        "If already executed, please disregard this message.</p>"
                        "<p>Sincerely,<br>{company_name}</p>",
                        0,
                    ),
                    (
                        "Strict",
                        "URGENT: Invoice {invoice_number} / {company_name}",
                        "Dear Accounts Payable Team,\n\n"
                        "This is an urgent notification regarding invoice {invoice_number} "
                        "({total_amount} {currency}), originally due on {due_date}.\n\n"
                        "We must insist on immediate payment to avoid any disruption of services. "
                        "Please confirm the transfer date at your earliest convenience.\n\n"
                        "Regards,\n{company_name}",
                        "<p>Dear Accounts Payable Team,</p>"
                        "<p>This is an urgent notification regarding invoice "
                        "<strong>{invoice_number}</strong> ({total_amount} {currency}), "
                        "originally due on <strong>{due_date}</strong>.</p>"
                        "<p>We must insist on immediate payment to avoid any disruption "
                        "of services. Please confirm the transfer date at your earliest "
                        "convenience.</p>"
                        "<p>Regards,<br>{company_name}</p>",
                        0,
                    ),
                ]
                self.conn.executemany(
                    "INSERT INTO automail_templates "
                    "(name, subject, body_text, body_html, is_default, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [(t[0], t[1], t[2], t[3], t[4], now, now) for t in templates],
                )
                logger.info("Seeded %d default automail templates", len(templates))
            else:
                logger.debug("automail_templates already populated, skipping seed")

            # ── Seed schedules if empty ─────────────────────────────────
            count = self.conn.execute(
                "SELECT COUNT(*) AS cnt FROM automail_schedules"
            ).fetchone()["cnt"]
            if count == 0:
                default_tpl = self.conn.execute(
                    "SELECT id FROM automail_templates WHERE is_default = 1 LIMIT 1"
                ).fetchone()
                tpl_id = default_tpl["id"] if default_tpl else 1
                schedules = [
                    ("Day 27 Reminder",    "days_before_due", 3, tpl_id, 1, 0),
                    ("Due Date Notice",    "on_due_date",     0, tpl_id, 1, 1),
                    ("Day 33 Follow-Up",   "days_after_due",  3, tpl_id, 1, 2),
                ]
                self.conn.executemany(
                    "INSERT INTO automail_schedules "
                    "(name, trigger_type, days_offset, template_id, is_active, sort_order, "
                    " created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [(s[0], s[1], s[2], s[3], s[4], s[5], now, now) for s in schedules],
                )
                logger.info("Seeded %d default automail schedules", len(schedules))
            else:
                logger.debug("automail_schedules already populated, skipping seed")

            # ── Seed settings if empty ───────────────────────────────────
            count = self.conn.execute(
                "SELECT COUNT(*) AS cnt FROM automail_settings"
            ).fetchone()["cnt"]
            if count == 0:
                settings = [
                    ("enabled",                   "0"),
                    ("max_reminders_per_invoice",  "5"),
                    ("retry_attempts",             "3"),
                    ("business_hours_start",       "08:00"),
                    ("business_hours_end",         "18:00"),
                    ("skip_weekends",              "1"),
                ]
                self.conn.executemany(
                    "INSERT INTO automail_settings (key, value) VALUES (?, ?)",
                    settings,
                )
                logger.info("Seeded %d default automail settings", len(settings))
            else:
                logger.debug("automail_settings already populated, skipping seed")

            self.conn.commit()
        except Exception as e:
            logger.exception("Failed to seed automail defaults: %s", e)
            try:
                self.conn.execute("ROLLBACK")
            except Exception:
                pass

    # ── SETTINGS (canonical API, not deprecated) ─────────────────────

    def get_settings(self, keys: List[str], company_id: Optional[int] = None) -> Dict[str, str]:
        """Return the values of *keys*, company-scoped.

        ``company_id`` may be passed EXPLICITLY (B4: the HTTP path sets
        ``backend.dependencies._current_company_id``, NOT the tenant_context
        this method used to read — so endpoints MUST pass it or the query
        would leak all companies' settings).  When omitted, falls back to the
        tenant context (desktop / Celery paths).
        """
        from database.tenant_context import get_company_id
        cid = get_company_id() if company_id is None else company_id
        company_filter = ""
        params: List[Any] = list(keys)
        if cid is not None:
            company_filter = " AND company_id = ?"
            params.append(cid)
        ph = "?" if getattr(self, "_engine", "sqlite") != "postgresql" else "%s"
        rows = self.conn.execute(
            f"SELECT key, value FROM settings WHERE key IN ({','.join(ph * len(keys))}){company_filter}",
            params,
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def save_setting(self, key: str, value: str, company_id: Optional[int] = None) -> None:
        """Upsert a setting, company-scoped.

        ``company_id`` may be passed EXPLICITLY (B4 — see :meth:`get_settings`).
        On PostgreSQL the settings PK is composite ``(key, company_id)``, so
        the upsert uses ``ON CONFLICT``; on SQLite ``INSERT OR REPLACE``.
        """
        from database.tenant_context import get_company_id
        cid = get_company_id() if company_id is None else company_id
        if getattr(self, "_engine", "sqlite") == "postgresql":
            if cid is not None:
                self.conn.execute(
                    "INSERT INTO settings (key, value, company_id) VALUES (%s, %s, %s) "
                    "ON CONFLICT (key, company_id) DO UPDATE SET value = EXCLUDED.value",
                    (key, value, cid),
                )
            else:
                self.conn.execute(
                    "INSERT INTO settings (key, value, company_id) VALUES (%s, %s, NULL) "
                    "ON CONFLICT (key, company_id) DO UPDATE SET value = EXCLUDED.value",
                    (key, value),
                )
        else:
            if cid is not None:
                self.conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value, company_id) VALUES (?, ?, ?)",
                    (key, value, cid),
                )
            else:
                self.conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value),
                )
        self.conn.commit()

    def get_setting(self, key: str, company_id: Optional[int] = None) -> Optional[str]:
        res = self.get_settings([key], company_id=company_id)
        return res.get(key) if res else None

    # ── Schema version ────────────────────────────────────────────────

    def get_schema_version(self) -> int:
        """Return the latest applied schema migration version, or 0 if none."""
        try:
            row = self.conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            version = row[0] if row and row[0] else 0
            return version
        except Exception:
            return 0

    # ── DEPRECATED DELEGATION METHODS ─────────────────────────────────
    # These exist only for backward compatibility.
    # New code should use the proper Service / Repository classes.
    # Each method logs a DeprecationWarning on first call.

    _schema_cache: dict = {}

    def _valid_columns(self, table: str) -> set:
        if table not in self._schema_cache:
            rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            DatabaseManager._schema_cache[table] = {r[1] for r in rows}
        return DatabaseManager._schema_cache[table]

    def _validate_column_keys(self, data: dict, table: str) -> None:
        valid = self._valid_columns(table)
        invalid = set(data.keys()) - valid
        if invalid:
            raise ValueError(
                f"Invalid column(s) for {table}: {', '.join(sorted(invalid))}"
            )

    # ── Trip CRUD (deprecated — use TripRepository) ──────────────────

    def _trip_repo(self):
        from repositories.trip_repository import TripRepository
        return TripRepository(self)

    def add_trip(self, data: dict):
        _deprecated("DatabaseManager.add_trip — use TripRepository.create()")
        return self._trip_repo().create(data)

    def update_trip(self, trip_id, data: dict):
        _deprecated("DatabaseManager.update_trip — use TripRepository.update()")
        self._trip_repo().update(trip_id, data)

    def update_status(self, trip_id, status):
        _deprecated("DatabaseManager.update_status — use TripRepository.update()")
        self._trip_repo().update(trip_id, {"status": status})

    def delete_trip(self, trip_id):
        _deprecated("DatabaseManager.delete_trip — use TripRepository.delete()")
        self._trip_repo().delete(trip_id)

    def get_all_trips(self, limit: int = 500):
        _deprecated("DatabaseManager.get_all_trips — use TripRepository.get_all()")
        return self._trip_repo().get_all(limit=limit)

    def get_trip_by_id(self, trip_id):
        _deprecated("DatabaseManager.get_trip_by_id — use TripRepository.get_by_id()")
        return self._trip_repo().get_by_id(trip_id)

    def get_filtered_trips(self, search="", truck="", status="", limit: int = 200):
        _deprecated("DatabaseManager.get_filtered_trips — use TripRepository methods")
        return self._trip_repo().get_filtered(search=search, truck=truck, status=status, limit=limit)

    def get_unique_lists(self):
        _deprecated("DatabaseManager.get_unique_lists — query directly")
        trucks = [r[0] for r in self.conn.execute(
            "SELECT DISTINCT COALESCE(t.plate_number, trips.truck_number) "
            "FROM trips LEFT JOIN trucks t ON trips.truck_id = t.id "
            "WHERE trips.truck_number IS NOT NULL OR trips.truck_id IS NOT NULL"
        ).fetchall()]
        drivers = [r[0] for r in self.conn.execute("SELECT DISTINCT driver_name FROM trips WHERE driver_name IS NOT NULL").fetchall()]
        return trucks, drivers

    # ── Invoice linking (deprecated — use InvoiceRepository) ─────────

    def _invoice_repo(self):
        from repositories.invoice_repository import InvoiceRepository
        return InvoiceRepository(self)

    def create_invoice_record(self, trip_id, inv_number, amount, due_date):
        _deprecated("DatabaseManager.create_invoice_record — use InvoiceRepository.create()")
        from datetime import datetime as dt
        try:
            self.conn.execute("""
                INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status)
                VALUES (?, ?, ?, ?, ?, 'Unpaid')
            """, (trip_id, inv_number, dt.now().strftime("%Y-%m-%d"), due_date, amount))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def mark_invoice_as_paid(self, trip_id):
        _deprecated("DatabaseManager.mark_invoice_as_paid — use InvoiceRepository.mark_paid()")
        self.conn.execute("UPDATE invoices SET status = 'Paid' WHERE trip_id = ?", (trip_id,))
        self.conn.commit()

    def _proforma_repo(self):
        from repositories.proforma_repository import ProformaRepository
        return ProformaRepository(self)

    def create_proforma_record(
        self,
        proforma_number: str = "",
        issue_date: str = "",
        valid_until: str = "",
        client_name: str = "",
        client_address: str = "",
        client_vat: str = "",
        client_phone: str = "",
        client_email: str = "",
        description: str = "",
        notes: str = "",
        line_items_json: str = "[]",
        subtotal: float = 0,
        discount_type: str = "",
        discount_value: float = 0,
        discount_amount: float = 0,
        tax_rate: float = 0,
        tax_amount: float = 0,
        grand_total: float = 0,
        currency: str = "EUR",
        mode: str = "client",
        status: str = "Draft",
        logo_path: str = "",
        signature_path: str = "",
        stamp_path: str = "",
        company_color: str = "#6366f1",
    ) -> Optional[int]:
        """Insert a proforma invoice record. Returns the new row id or None on failure."""
        repo = self._proforma_repo()
        import json
        return repo.create(
            proforma_number=proforma_number,
            issue_date=issue_date,
            valid_until=valid_until,
            client_name=client_name,
            client_address=client_address,
            client_vat=client_vat,
            client_phone=client_phone,
            client_email=client_email,
            description=description,
            notes=notes,
            line_items=json.loads(line_items_json) if line_items_json else [],
            subtotal=subtotal,
            discount_type=discount_type,
            discount_value=discount_value,
            discount_amount=discount_amount,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            grand_total=grand_total,
            currency=currency,
            mode=mode,
            status=status,
            logo_path=logo_path,
            signature_path=signature_path,
            stamp_path=stamp_path,
            company_color=company_color,
        )

    def update_proforma(self, proforma_id: int, **kwargs) -> bool:
        """Update proforma invoice fields by id. Returns True on success."""
        repo = self._proforma_repo()
        return repo.update(proforma_id, **kwargs)

    # ── Truck CRUD (deprecated — use FleetRepository) ────────────────

    def _fleet_repo(self):
        from repositories.fleet_repository import FleetRepository
        return FleetRepository(self)

    def get_all_trucks(self, active_only=False):
        _deprecated("DatabaseManager.get_all_trucks — use FleetRepository.get_all()")
        if active_only:
            return self._fleet_repo().get_active_trucks()
        return self._fleet_repo().get_all()

    def get_truck_by_id(self, truck_id):
        _deprecated("DatabaseManager.get_truck_by_id — use FleetRepository.get_by_id()")
        return self._fleet_repo().get_by_id(truck_id)

    def add_truck(self, data: dict):
        _deprecated("DatabaseManager.add_truck — use FleetRepository.create()")
        return self._fleet_repo().create(data)

    def update_truck(self, truck_id, data: dict):
        _deprecated("DatabaseManager.update_truck — use FleetRepository.update()")
        self._fleet_repo().update(truck_id, data)

    def delete_truck(self, truck_id):
        _deprecated("DatabaseManager.delete_truck — use FleetRepository.delete()")
        self._fleet_repo().delete(truck_id)

    # ── Truck routes (deprecated — use TruckRouteAssignmentRepository) ─

    def get_truck_routes(self, truck_id, status=None):
        _deprecated("DatabaseManager.get_truck_routes — use TruckRouteAssignmentRepository")
        from repositories.truck_route_assignment_repository import TruckRouteAssignmentRepository
        repo = TruckRouteAssignmentRepository(self)
        return repo.get_by_truck(truck_id, status=status)

    # ── Expenses CRUD (deprecated — no dedicated repo yet) ────────────

    def ensure_expenses_table(self):
        _deprecated("DatabaseManager.ensure_expenses_table — create table directly")
        # The expenses table is part of the base schema (TABLE_EXPENSES) since
        # Phase 0; only legacy DBs created before that need the lazy CREATE.
        if self._table_exists("expenses"):
            return
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                truck_id INTEGER,
                date TEXT,
                category TEXT,
                description TEXT,
                amount REAL,
                company_id INTEGER,
                created_at TEXT,
                updated_at TEXT
            );
        """)
        self.conn.commit()

    def get_expenses(self, truck_id, company_id=None):
        _deprecated("DatabaseManager.get_expenses — query expenses table directly")
        if company_id is not None:
            return self.rows_to_dicts(self.conn.execute(
                "SELECT id, date, category, amount, description FROM expenses "
                "WHERE truck_id = ? AND company_id = ? ORDER BY date DESC",
                (truck_id, company_id),
            ).fetchall())
        return self.rows_to_dicts(self.conn.execute(
            "SELECT id, date, category, amount, description FROM expenses "
            "WHERE truck_id = ? ORDER BY date DESC",
            (truck_id,),
        ).fetchall())

    def add_expense(self, truck_id, date, category, description, amount, company_id=None):
        _deprecated("DatabaseManager.add_expense — insert into expenses table directly")
        cursor = self.conn.execute(
            "INSERT INTO expenses (truck_id, date, category, description, amount, company_id) "
            "VALUES (?,?,?,?,?,?)",
            (truck_id, date, category, description, amount, company_id),
        )
        self.conn.commit()
        return cursor.lastrowid

