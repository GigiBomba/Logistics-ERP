"""PostgreSQL-backed shared fixtures for integration tests.

These fixtures replace the older SQLite-based ``test_db`` / ``seeded_db``
fixtures that were in this file.  All integration tests that need a real
database should depend on ``pg_db`` (function-scoped, auto-rollback) or
``pg_session`` (session-scoped, useful for session-level setup).

Typical usage
-------------

.. code:: python

    import pytest
    from tests.test_data import make_trip, make_client
    from repositories.trip_repository import TripRepository

    @pytest.mark.integration
    async def test_trip_crud(pg_db, test_data):
        repo = TripRepository(pg_db)
        trip = make_trip(client_id=test_data["client"].id)
        trip_id = repo.create(trip)
        assert repo.get_by_id(trip_id) is not None
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Generator

import psycopg2  # type: ignore[import-untyped]
import pytest
from psycopg2 import sql as pgsql
from psycopg2.extras import RealDictCursor

from database.tenant_context import clear_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Default DSN used when ``OPERION_TEST_POSTGRES_DSN`` is not set.
DEFAULT_TEST_DSN = "postgresql://operion:operion_test@localhost:5432/operion_test"

#: Name of the database (parsed from the DSN).
#: We keep it separate so we can create/drop it against the ``postgres`` DB.
DEFAULT_TEST_DB_NAME = "operion_test"


def _parse_db_name(dsn: str) -> str:
    """Extract the database name from a PostgreSQL DSN."""
    from urllib.parse import urlparse

    parsed = urlparse(dsn)
    name = parsed.path.lstrip("/")
    return name or DEFAULT_TEST_DB_NAME


def _admin_dsn(dsn: str) -> str:
    """Return a DSN that connects to the ``postgres`` maintenance database."""
    return dsn.rsplit("/", 1)[0] + "/postgres"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_database(dsn: str) -> None:
    """Create the test database if it does not exist.

    Connects to the ``postgres`` maintenance database so we can issue
    ``CREATE DATABASE``.
    """
    db_name = _parse_db_name(dsn)
    admin = _admin_dsn(dsn)
    try:
        conn = psycopg2.connect(admin)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
        )
        if not cur.fetchone():
            cur.execute(pgsql.SQL("CREATE DATABASE {}").format(pgsql.Identifier(db_name)))
            logger.info("Created test database '%s'", db_name)
        cur.close()
        conn.close()
    except psycopg2.OperationalError as exc:
        pytest.skip(f"PostgreSQL is not available — skipping integration tests: {exc}")


def _drop_database(dsn: str) -> None:
    """Drop the test database after the session finishes."""
    db_name = _parse_db_name(dsn)
    admin = _admin_dsn(dsn)
    try:
        conn = psycopg2.connect(admin)
        conn.autocommit = True
        cur = conn.cursor()
        # Terminate other connections so DROP DATABASE succeeds
        cur.execute(
            pgsql.SQL(
                "SELECT pg_terminate_backend(pg_stat_activity.pid) "
                "FROM pg_stat_activity "
                "WHERE pg_stat_activity.datname = %s AND pid <> pg_backend_pid()"
            ),
            (db_name,),
        )
        cur.execute(pgsql.SQL("DROP DATABASE IF EXISTS {}").format(pgsql.Identifier(db_name)))
        logger.info("Dropped test database '%s'", db_name)
        cur.close()
        conn.close()
    except Exception:
        logger.warning("Could not drop test database '%s' (may not exist)", db_name)


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def db_url() -> str:
    """Return the PostgreSQL DSN for the test database.

    Override by setting ``OPERION_TEST_POSTGRES_DSN``.
    """
    return os.environ.get("OPERION_TEST_POSTGRES_DSN", DEFAULT_TEST_DSN)


@pytest.fixture(scope="session")
def pg_database(db_url: str) -> Generator[str, None, None]:
    """Create the test database once per session and drop it on teardown.

    Yields the DSN so that other session-scoped fixtures can connect.
    """
    _ensure_database(db_url)
    yield db_url
    _drop_database(db_url)


@pytest.fixture(scope="session")
def pg_migrations(pg_database: str) -> str:
    """Create full PostgreSQL schema + run alembic migrations.

    Uses ``DatabaseManager(engine="postgresql")`` which calls
    ``_init_pg_schema()`` (50 tables from ``schema_pg.sql``) then runs
    Alembic migrations via ``_init_db()``.

    Yields the DSN so that connection fixtures can use it.
    """
    from database.db_manager import DatabaseManager

    db = DatabaseManager(db_path=pg_database, engine="postgresql", pool_min=1, pool_max=2)
    db.close()
    logger.info("Full PostgreSQL schema + migrations applied to test database")
    return pg_database


@pytest.fixture(scope="session")
def pg_session(pg_migrations: str) -> Generator[Any, None, None]:
    """Session-scoped PostgreSQL connection with applied migrations.

    This connection persists for the entire test session.  Do **not** use
    it directly in tests — use ``pg_db`` instead, which wraps each test in
    a rolled-back transaction.

    Yields a ``psycopg2.connection`` with ``RealDictCursor`` factory.
    """
    conn = psycopg2.connect(pg_migrations, cursor_factory=RealDictCursor)
    conn.autocommit = False
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Function-scoped fixtures (used by tests)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def pg_db(pg_session: Any) -> Generator[Any, None, None]:
    """Function-scoped PostgreSQL connection with automatic rollback.

    Every test that uses ``pg_db`` gets a transaction that is rolled back
    when the test finishes, leaving the database in a clean state for the
    next test.

    Because this is ``autouse=True``, it applies to **every** test in the
    ``tests/integration/`` directory.  If a test does not touch the database
    the overhead is minimal (a ``BEGIN`` + ``ROLLBACK`` round-trip).
    """
    # Clear any tenant context that may have leaked from a previous
    # test (contextvars.ContextVar survives across sync test functions).
    clear_context()
    # psycopg2 connections do not expose .execute() directly;
    # we must create a cursor first.
    cur = pg_session.cursor()
    cur.execute("SAVEPOINT test_sp")
    cur.close()
    yield pg_session
    cur = pg_session.cursor()
    cur.execute("ROLLBACK TO SAVEPOINT test_sp")
    cur.close()


# ---------------------------------------------------------------------------
# seeded_db — DatabaseManager-compatible wrapper for pg_db
# ---------------------------------------------------------------------------


class _Psycopg2Connection:
    """Lightweight wrapper around a psycopg2 connection that adds ``.execute()``
    and provides savepoint-safe transaction control.

    ``sqlite3.Connection`` has a native ``execute()`` method; psycopg2
    connections do not because they are implemented as a C extension type
    without ``__dict__``.  This wrapper delegates all standard methods
    (``cursor``, ``commit``, ``rollback``, ``close``) to the underlying
    connection and provides an ``execute()`` that mirrors the SQLite API.

    **Savepoint safety** — Repositories may call ``commit()``, ``rollback()``
    or issue ``COMMIT`` / ``ROLLBACK`` SQL statements during test execution.
    These would commit/rollback the outer transaction and destroy the
    savepoint that ``pg_db`` relies on for test isolation.  This wrapper
    intercepts those operations and translates them to savepoint operations.
    """

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def cursor(self, *args: Any, **kwargs: Any) -> Any:
        return self._conn.cursor(*args, **kwargs)

    def commit(self) -> None:
        """No-op: we are inside a savepoint managed by ``pg_db``.

        Committing the outer connection would destroy the savepoint
        and prevent ``pg_db`` from rolling back changes at test end.
        """
        pass

    def rollback(self) -> None:
        """Rollback the savepoint instead of the full transaction."""
        cur = self._conn.cursor()
        cur.execute("ROLLBACK TO SAVEPOINT test_sp")
        cur.close()

    def close(self) -> None:
        self._conn.close()

    def execute(self, query: str, params: Any = None) -> Any:
        """Execute a query, handling placeholders and transaction control.

        - Converts ``?`` placeholders to ``%s`` for PostgreSQL.
        - Intercepts ``COMMIT`` / ``ROLLBACK`` / ``BEGIN`` SQL statements
          that would break savepoint isolation.
        """
        q = query.strip().rstrip(";").strip()
        q_upper = q.upper()

        # ── Transaction-control interception ──────────────────────────
        if q_upper in ("COMMIT",):
            # No-op — same rationale as commit() above.
            cur = self._conn.cursor()
            return cur

        if q_upper in ("ROLLBACK",):
            # Translate to savepoint rollback.
            cur = self._conn.cursor()
            cur.execute("ROLLBACK TO SAVEPOINT test_sp")
            return cur

        if q_upper.startswith("BEGIN"):
            # We are already inside a transaction (managed by pg_db).
            cur = self._conn.cursor()
            return cur

        # ── Normal query execution ────────────────────────────────────
        # Convert ? placeholders to %s for psycopg2
        if params is not None:
            adapted = q.replace("?", "%s")
        else:
            adapted = q
        cur = self._conn.cursor()
        if params is not None:
            cur.execute(adapted, params)
        else:
            cur.execute(adapted)
        return cur


class _DbAdapter:
    """Minimal adapter that wraps a psycopg2 connection as DatabaseManager.

    Tests and services expect a ``DatabaseManager``-like object with a
    ``.conn`` property, ``.execute()``, ``.row_to_dict()``, and
    ``.rows_to_dicts()``.  This adapter delegates those calls to the
    underlying ``pg_db`` connection (which is inside the SAVEPOINT
    transaction), avoiding the overhead and connection-pool churn of
    creating a full ``DatabaseManager`` per test.
    """

    def __init__(self, conn: Any) -> None:
        self._conn = conn
        self._engine = "postgresql"
        # psycopg2 is a C extension type that does not allow setting
        # arbitrary attributes (no __dict__).  Wrap it in a helper
        # that adds the ``.execute()`` method for API parity with
        # ``sqlite3.Connection``.
        self._wrapped_conn = _Psycopg2Connection(conn)

    @property
    def conn(self) -> _Psycopg2Connection:
        return self._wrapped_conn

    @staticmethod
    def row_to_dict(row: Any) -> Any:
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        return dict(row)

    @staticmethod
    def rows_to_dicts(rows: Any) -> list:
        if not rows:
            return []
        return [_DbAdapter.row_to_dict(r) for r in rows]

    def execute(self, query: str, params: tuple = ()) -> Any:
        return self._wrapped_conn.execute(query, params)


@pytest.fixture
def seeded_db(pg_db: Any, test_data: Dict[str, Any]) -> _DbAdapter:
    """Provide a ``DatabaseManager``-compatible wrapper for the test
    database connection.

    Includes pre-seeded test data (company, admin user, client, truck,
    driver) so that tests can immediately use ``user_id=1``,
    ``client_id=1``, ``truck_id=1``, ``driver_id=1`` without having
    to set up records themselves.

    The wrapper stays inside ``pg_db``'s SAVEPOINT transaction, so all
    changes are rolled back after each test.
    """
    return _DbAdapter(pg_db)


# ---------------------------------------------------------------------------
# Test data helpers (using factories)
# ---------------------------------------------------------------------------


@pytest.fixture
def make_trip():
    """Return a ``TripCreate`` instance with sensible defaults.

    See ``tests.test_data.factories.make_trip`` for available overrides.
    """
    from tests.test_data.factories import make_trip as _make_trip
    return _make_trip


@pytest.fixture
def make_client():
    """Return a ``ClientCreate`` instance with sensible defaults."""
    from tests.test_data.factories import make_client as _make_client
    return _make_client


@pytest.fixture
def make_driver():
    """Return a ``DriverCreate`` instance with sensible defaults."""
    from tests.test_data.factories import make_driver as _make_driver
    return _make_driver


@pytest.fixture
def make_user():
    """Return a ``UserCreateRequest`` instance with sensible defaults."""
    from tests.test_data.factories import make_user as _make_user
    return _make_user


@pytest.fixture
def make_vehicle():
    """Return a ``VehicleCreate`` instance with sensible defaults."""
    from tests.test_data.factories import make_vehicle as _make_vehicle
    return _make_vehicle


@pytest.fixture
def make_invoice():
    """Return an ``InvoiceCreate`` instance with sensible defaults."""
    from tests.test_data.factories import make_invoice as _make_invoice
    return _make_invoice


# ---------------------------------------------------------------------------
# Seeded test data (optional convenience)
# ---------------------------------------------------------------------------


@pytest.fixture
def test_data(
    pg_db: Any,
) -> Dict[str, Any]:
    """Insert a minimal set of seed records and return their IDs.

    The inserted rows are automatically rolled back after each test via the
    ``pg_db`` fixture.

    Returns a dictionary with keys:

    * ``company_id``
    * ``user_id``
    * ``client_id``
    * ``truck_id``
    * ``driver_id``

    Example::

        def test_something(pg_db, test_data):
            uid = test_data["user_id"]
            # ...
    """
    cur = pg_db.cursor()
    from datetime import datetime as _dt
    _now = _dt.utcnow().isoformat(timespec="seconds")

    # Use OVERRIDING SYSTEM VALUE to force id=1 for seed records.
    # PostgreSQL IDENTITY sequences do NOT roll back with savepoints,
    # so without this each successive test would get different IDs
    # (2, 3, 4, …) and fail when looking for hardcoded IDs like 1.
    # Insert seed records with forced id=1 so tests can hardcode these IDs.
    # OVERRIDING SYSTEM VALUE bypasses the IDENTITY sequence, which is
    # necessary because sequences do NOT roll back with savepoints.
    cur.execute(
        "INSERT INTO companies (id, company_name) "
        "OVERRIDING SYSTEM VALUE VALUES (1, 'Test Company')"
    )
    company_id = 1

    cur.execute(
        "INSERT INTO users (id, email, password_hash, role, display_name, is_active, company_id) "
        "OVERRIDING SYSTEM VALUE VALUES (1, %s, %s, %s, %s, %s, %s)",
        ("admin@test.com", "hash", "admin", "Admin", 1, company_id),
    )
    user_id = 1

    cur.execute(
        "INSERT INTO clients (id, name, company_id, vat_number, address, email, phone, country, created_at) "
        "OVERRIDING SYSTEM VALUE VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s)",
        ("Test Client", company_id, "", "", "", "", "", _now),
    )
    client_id = 1

    cur.execute(
        "INSERT INTO trucks (id, plate_number, company_id, active_status) "
        "OVERRIDING SYSTEM VALUE VALUES (1, %s, %s, %s)",
        ("B-001-AAA", company_id, 1),
    )
    truck_id = 1

    cur.execute(
        "INSERT INTO drivers (id, name, company_id, created_at, updated_at) "
        "OVERRIDING SYSTEM VALUE VALUES (1, %s, %s, %s, %s)",
        ("Test Driver", company_id, _now, _now),
    )
    driver_id = 1

    # Advance IDENTITY sequences past 1 so that auto-generated
    # inserts (those without OVERRIDING SYSTEM VALUE) do not
    # collide with our forced ids.
    for seq_table in ("companies", "users", "clients", "trucks", "drivers"):
        cur.execute(f"ALTER SEQUENCE {seq_table}_id_seq RESTART WITH 1000")

    return {
        "company_id": company_id,
        "user_id": user_id,
        "client_id": client_id,
        "truck_id": truck_id,
        "driver_id": driver_id,
    }
