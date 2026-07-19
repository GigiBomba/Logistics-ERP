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
from pathlib import Path
from typing import Any, Dict, Generator

import psycopg2  # type: ignore[import-untyped]
import pytest
from psycopg2 import sql as pgsql
from psycopg2.extras import RealDictCursor

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


def _run_migrations(dsn: str) -> None:
    """Apply all Alembic migrations to the test database.

    Uses the project's ``alembic.ini`` configuration and overrides the
    ``sqlalchemy.url`` to point at the test database.
    """
    from alembic.command import upgrade
    from alembic.config import Config

    project_root = Path(__file__).parents[2]
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", dsn)
    alembic_cfg.attributes["configure_logger"] = False
    upgrade(alembic_cfg, "head")
    logger.info("Alembic migrations applied to test database")


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
    """Apply Alembic migrations to the test database (once per session).

    Yields the DSN so that connection fixtures can use it.
    """
    _run_migrations(pg_database)
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
    pg_session.execute("SAVEPOINT test_sp")
    yield pg_session
    pg_session.execute("ROLLBACK TO SAVEPOINT test_sp")


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
    cur.execute(
        "INSERT INTO companies (company_name) VALUES ('Test Company') RETURNING id"
    )
    company_id = cur.fetchone()["id"]

    cur.execute(
        "INSERT INTO users (email, password_hash, role, display_name, is_active, company_id) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        ("admin@test.com", "hash", "admin", "Admin", True, company_id),
    )
    user_id = cur.fetchone()["id"]

    cur.execute(
        "INSERT INTO clients (name, company_id, vat_number, address, email, phone, country) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        ("Test Client", company_id, "", "", "", "", ""),
    )
    client_id = cur.fetchone()["id"]

    cur.execute(
        "INSERT INTO trucks (plate_number, company_id, active_status) "
        "VALUES (%s, %s, %s) RETURNING id",
        ("B-001-AAA", company_id, True),
    )
    truck_id = cur.fetchone()["id"]

    cur.execute(
        "INSERT INTO drivers (name, company_id) VALUES (%s, %s) RETURNING id",
        ("Test Driver", company_id),
    )
    driver_id = cur.fetchone()["id"]

    return {
        "company_id": company_id,
        "user_id": user_id,
        "client_id": client_id,
        "truck_id": truck_id,
        "driver_id": driver_id,
    }
