import logging
import os
import sqlite3
import threading
import warnings
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

_emitted_warnings: set = set()


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
    for part in protected.split(";"):
        # Restore dollar blocks, strip comments and whitespace
        stmt = part.strip()
        if not stmt:
            continue
        # Restore $$ blocks
        for i, block in enumerate(dollar_blocks):
            stmt = stmt.replace(f"\x00DOLLAR{i}\x00", block)
        dollar_blocks.clear()
        # Skip comment-only statements
        lines = [l for l in stmt.split("\n") if l.strip() and not l.strip().startswith("--")]
        clean = "\n".join(lines).strip()
        if clean:
            statements.append(clean)
    return statements


from database import schema as _schema
from database.connection_pool import ConnectionPool, PostgresConnectionPool

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
        if self._engine == "postgresql":
            self._init_pg(db_path)
        else:
            self._pool = ConnectionPool(db_path, timeout=30)
        self._init_db()
        self.user_company_id: Optional[int] = None
        self.user_role: str = ""

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
                return {
                    "engine": "postgresql",
                    "pool": self._pg_pool.stats,
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

        Thin wrapper around ``self.conn.execute`` that adapts ``?`` → ``%s``
        for PostgreSQL.  Callers should use this instead of
        ``self.conn.execute()`` directly for cross-engine compatibility.
        """
        return self.conn.execute(self._adapt_placeholders(query), params)

    def executemany(self, query: str, seq_of_params):
        """Execute a SQL statement against all parameter sequences.

        PostgreSQL-compatible wrapper around ``self.conn.executemany``.
        """
        return self.conn.executemany(self._adapt_placeholders(query), seq_of_params)

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
        in PostgreSQL-compatible syntax.
        """
        if self._engine == "postgresql":
            self._init_pg_schema()
        else:
            self._create_tables_and_indices()
            self._run_column_migrations()
            self._migrate_legacy_data()

        # Run Alembic migrations for Freight Exchange tables (PostgreSQL only)
        if self._engine == "postgresql":
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
                logger.warning("Alembic migrations skipped (non-fatal): %s", e)

        # Ensure mobile tables exist (best-effort, non-critical)
        try:
            from backend.api.v1.mobile import ensure_mobile_tables
            ensure_mobile_tables(self)
        except Exception:
            pass  # mobile tables are non-critical

    def _init_pg_schema(self):
        """Execute PostgreSQL schema from schema_pg.sql."""
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

        # Split by semicolons while preserving $$...$$ blocks (PL/pgSQL functions).
        # $$-delimited blocks may contain semicolons that must not be split.
        statements = _split_pg_statements(sql)
        for stmt in statements:
            if not stmt:
                continue
            try:
                self.conn.execute(stmt)
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug("Skipping existing object: %s", str(e)[:80])
                else:
                    logger.warning("PG schema statement failed: %s — %s", str(e)[:120], stmt[:80])

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
            S.INDEX_TRIPS_CLIENT_ID, S.INDEX_TRIPS_PAYMENT_DATE,
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
            S.INDEX_DOCUMENTS_EXPIRY_DATE,
            S.INDEX_DOC_LINKS_DOCUMENT, S.INDEX_DOC_LINKS_ENTITY,
            S.TABLE_DOCUMENT_VERSIONS, S.INDEX_VERSIONS_DOCUMENT,
            S.TABLE_CONTRACTS, S.INDEX_CONTRACTS_CLIENT, S.INDEX_CONTRACTS_STATUS,
            S.INDEX_CONTRACTS_END_DATE,
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
            # Multi-tenant company_id indexes
            S.INDEX_TRIPS_COMPANY, S.INDEX_INVOICES_COMPANY,
            S.INDEX_TRUCKS_COMPANY, S.INDEX_DRIVERS_COMPANY,
            S.INDEX_ROUTES_COMPANY, S.INDEX_ROUTE_HISTORY_COMPANY,
            S.INDEX_ROUTE_HISTORY_V2_COMPANY, S.INDEX_ALERTS_COMPANY,
            S.INDEX_OPERATION_EVENTS_COMPANY, S.INDEX_TRIP_STATUS_HISTORY_COMPANY,
            S.INDEX_MAINTENANCE_RECORDS_COMPANY, S.INDEX_MAINTENANCE_SCHEDULES_COMPANY,
            S.INDEX_TRUCK_HEALTH_SCORES_COMPANY, S.INDEX_RECEIPTS_COMPANY,
            S.INDEX_GPS_TELEMETRY_COMPANY, S.INDEX_PIPELINE_RUNS_COMPANY,
            S.INDEX_DOCUMENT_PACKAGE_COMPANY, S.INDEX_PROFORMA_COMPANY,
            S.INDEX_CONTRACTS_COMPANY, S.INDEX_TACHO_IMPORTS_COMPANY,
            # Additional performance indexes
            S.INDEX_INVOICES_STATUS, S.INDEX_GPS_TRUCK_TIME,
            S.INDEX_CMR_AUDIT_EVENT_TYPE, S.INDEX_CMR_AUDIT_CREATED,
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
        ]
        for stmt in exec_stmts:
            try:
                self.conn.execute(stmt)
            except Exception as e:
                logger.warning("Schema statement failed (may be harmless): %s", e)
        try:
            self.conn.execute(S.INDEX_TRIPS_MONTH)
        except Exception:
            pass
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
            self.conn.execute(S.INDEX_DOCUMENTS_EXPIRY_DATE)
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
            for stmt in (S.TABLE_DOCUMENTS_FTS, S.TRIGGER_DOCUMENTS_FTS_INSERT,
                         S.TRIGGER_DOCUMENTS_FTS_DELETE, S.TRIGGER_DOCUMENTS_FTS_UPDATE):
                try:
                    self.conn.execute(stmt)
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
                cols = [r[1] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
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
                cols = [r[1] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
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
            ("consignee_contact_name", "ALTER TABLE clients ADD COLUMN consignee_contact_name TEXT DEFAULT ''"),
            ("consignee_contact_phone", "ALTER TABLE clients ADD COLUMN consignee_contact_phone TEXT DEFAULT ''"),
        ])

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
        ]
        for table, alter_sql in _tenant_tables:
            self._ensure_column(table, "company_id", alter_sql)
            # Backfill any rows that still have NULL company_id (legacy data)
            try:
                self.conn.execute(
                    f"UPDATE {table} SET company_id = 1 WHERE company_id IS NULL"
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
        _soft_delete_tables = [
            "trips", "invoices", "clients", "drivers", "trucks",
            "routes", "route_history_v2", "receipts", "contracts",
            "proforma_invoices", "maintenance_records", "maintenance_schedules",
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

        # ── Audit log: add entity tracking columns to operation_events ───
        _audit_columns = [
            ("entity_type", "ALTER TABLE operation_events ADD COLUMN entity_type TEXT"),
            ("entity_id", "ALTER TABLE operation_events ADD COLUMN entity_id TEXT"),
            ("user_id", "ALTER TABLE operation_events ADD COLUMN user_id INTEGER DEFAULT 0"),
        ]
        for col_name, alter_sql in _audit_columns:
            try:
                cols = [r[1] for r in self.conn.execute("PRAGMA table_info(operation_events)").fetchall()]
                if col_name not in cols:
                    self.conn.execute(alter_sql)
            except Exception as e:
                logger.warning("Migration step failed for operation_events.%s: %s", col_name, e)

        # ── Additional performance indexes ───────────────────────────────
        for idx_stmt in (
            S.INDEX_INVOICES_STATUS,
            S.INDEX_GPS_TRUCK_TIME,
            S.INDEX_CMR_AUDIT_EVENT_TYPE,
            S.INDEX_CMR_AUDIT_CREATED,
            S.INDEX_EMAIL_LOGS_TRIP,
            S.INDEX_EMAIL_LOGS_STATUS,
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

        # ── Migration: settings table → composite PK (key, company_id) ──
        try:
            cols = [r[1] for r in self.conn.execute(
                "PRAGMA table_info(settings)"
            ).fetchall()]
            pk_cols = [r[1] for r in self.conn.execute(
                "PRAGMA table_info(settings)"
            ).fetchall() if r[5] > 0]  # r[5] = pk flag
            # Old schema: key TEXT PRIMARY KEY (pk_cols = ["key"])
            # New schema: composite PRIMARY KEY (key, company_id)
            if pk_cols == ["key"] and "company_id" not in pk_cols:
                logger.info("Migrating settings table to composite PK (key, company_id)")
                fk_was_on = self.conn.execute("PRAGMA foreign_keys").fetchone()[0]
                if fk_was_on:
                    self.conn.execute("PRAGMA foreign_keys=OFF")
                self.conn.execute("BEGIN IMMEDIATE")
                self.conn.execute("""
                    CREATE TABLE settings_new (
                        key TEXT NOT NULL,
                        value TEXT,
                        company_id INTEGER REFERENCES companies(id),
                        PRIMARY KEY (key, company_id)
                    )
                """)
                self.conn.execute("""
                    INSERT INTO settings_new (key, value, company_id)
                    SELECT key, value, COALESCE(company_id, 1) FROM settings
                """)
                self.conn.execute("DROP TABLE settings")
                self.conn.execute("ALTER TABLE settings_new RENAME TO settings")
                self.conn.commit()
                if fk_was_on:
                    self.conn.execute("PRAGMA foreign_keys=ON")
                logger.info("Settings table migration to composite PK complete")
        except Exception as e:
            logger.warning("Settings table migration failed (may be already migrated): %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

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
        # Alerts and status history → cascade with trip
        self._ensure_foreign_key("alerts", "trip_id", "trips", on_delete="CASCADE")
        self._ensure_foreign_key("trip_status_history", "trip_id", "trips", on_delete="CASCADE")

        try:
            self.conn.commit()
        except Exception as e:
            logger.warning("Migration step failed: %s", e)

        self._seed_automail_defaults()

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
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
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

    def get_settings(self, keys: List[str]) -> Dict[str, str]:
        company_filter = ""
        params: List[Any] = list(keys)
        if self.user_company_id is not None:
            company_filter = " AND company_id = ?"
            params.append(self.user_company_id)
        rows = self.conn.execute(
            f"SELECT key, value FROM settings WHERE key IN ({','.join('?' * len(keys))}){company_filter}",
            params,
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def save_setting(self, key: str, value: str) -> None:
        if self.user_company_id is not None:
            self.conn.execute(
                "INSERT OR REPLACE INTO settings (key, value, company_id) VALUES (?, ?, ?)",
                (key, value, self.user_company_id),
            )
        else:
            self.conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value),
            )
        self.conn.commit()

    def get_setting(self, key: str) -> Optional[str]:
        res = self.get_settings([key])
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
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                truck_id INTEGER,
                date TEXT,
                category TEXT,
                description TEXT,
                amount REAL,
                company_id INTEGER
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

