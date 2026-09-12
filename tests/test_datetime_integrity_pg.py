"""PostgreSQL integration tests for the Phase-D datetime-integrity work.

Verifies the end state the deployment path is meant to produce on a live
PostgreSQL database — ``database/schema_pg.sql`` + Alembic
(``g8c9d0e1f2f0_datetime_integrity_timestamptz`` then
``o8g9b0c2e5f6_datetime_integrity_phase_d_followup``) +
``DatabaseManager._apply_pg_extra_ddl``:

* T1  every Phase-D target column is native ``timestamp with time zone``.
* T2  the migrations' verbatim ``ALTER COLUMN ... TYPE TIMESTAMPTZ USING
      CASE`` semantics on a scratch table: ``''`` → NULL, date-only →
      UTC midnight, full ISO-8601 preserved, NULL stays NULL.
* T3  the ``stamp_updated_at()`` trigger writes native TIMESTAMPTZ stamps
      (UTC canonical, seconds precision) regardless of session timezone,
      and a later UPDATE re-stamps to a new value.
* T4  DB-level date arithmetic on the converted invoice columns.
* T5  date-only ingest lands as UTC midnight (not local midnight).
* T6  the recreated ``trips.month`` generated column (over TIMESTAMPTZ
      ``created_at``) yields ``YYYY-MM``.

Like ``test_backfill_updated_at.py`` this file owns a per-file isolated
database so its schema build / DDL can never collide with other test files'
on the shared ``operion_test`` database (xdist ``-n 2`` concurrent runs).
It skips cleanly when PostgreSQL is unreachable — there is NO ``postgresql``
marker; the ``pg_schema`` / ``pg_conn`` fixtures are the gate.
"""
from __future__ import annotations

import os
import re
import time
import uuid

import pytest

TEST_DSN = os.environ.get(
    "OPERION_TEST_POSTGRES_DSN",
    "postgresql://operion:operion_test_ci@localhost:5432/operion_test_dt",
)

#: Per-file isolated database name — this module owns ``operion_test_dt`` so
#: its own schema build / migrations can never collide with other test
#: files' on the shared ``operion_test`` database (xdist `-n 2` concurrent
#: runs).
_TEST_DB_NAME = "operion_test_dt"

#: Admin DSN: connect to the always-existing ``operion_test`` database so the
#: (superuser) ``operion`` role can issue CREATE/DROP DATABASE for the
#: per-file database above.
_BASE_DSN = "postgresql://operion:operion_test_ci@localhost:5432/operion_test"


def _ensure_test_db() -> None:
    """Create a CLEAN per-file test database (drop stale + recreate).

    No-op when ``OPERION_TEST_POSTGRES_DSN`` is set explicitly — the caller
    pointed us at a database of their choosing, and we must not touch it.

    S3-NF-PGT (Stage 3 remediation): a stale ``operion_test_dt`` left behind
    by a crashed/aborted run can carry a partial ``alembic_version`` — the
    next boot's ``alembic upgrade head`` would then silently skip the
    g8c9/o8g9 TIMESTAMPTZ migrations and leave the Phase-D columns as TEXT.
    Guaranteeing a fresh per-file database every run (mirroring
    ``test_backfill_updated_at.py``'s per-file discipline) makes the test
    exercise the full migration chain from scratch.
    """
    if os.environ.get("OPERION_TEST_POSTGRES_DSN"):
        return
    import psycopg2
    from psycopg2 import sql as pgsql

    try:
        conn = psycopg2.connect(_BASE_DSN)
        conn.autocommit = True  # CREATE/DROP DATABASE cannot run inside a transaction
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (_TEST_DB_NAME,))
        if cur.fetchone():
            # Never force-kill another session's connections — if any remain,
            # leave the DB in place (the CREATE below is then a no-op for
            # existing tables) rather than wedging another worker's build.
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
        cur.execute(
            pgsql.SQL("CREATE DATABASE {}").format(pgsql.Identifier(_TEST_DB_NAME))
        )
        cur.close()
        conn.close()
    except Exception:
        # Best-effort: the DB may already exist (idempotent) or PG may be
        # unreachable (the pg_schema fixture skips).
        pass


def _drop_test_db() -> None:
    """Drop the per-file test database at module teardown (best-effort)."""
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


# Create the per-file database BEFORE the first fixture connects.
_ensure_test_db()


# ── PostgreSQL integration (skip when unavailable) ─────────────────────────


@pytest.fixture(scope="module")
def pg_schema():
    """Build the real PG schema (idempotent) via the deployment path.

    ``DatabaseManager(dsn, engine="postgresql")`` runs schema_pg.sql +
    Alembic + ``_apply_pg_extra_ddl`` and is safe to run repeatedly.  Each
    statement runs in its own autocommit transaction, so a single failure
    cannot abort the rest of the build.

    S3-NF-PGT (Stage 3 remediation): ``DatabaseManager._run_alembic_upgrade()``
    invokes ``alembic upgrade head`` WITHOUT passing the DSN — ``alembic/env.py
    get_url()`` resolves the URL from the environment (``OPERION_DB_ENGINE``,
    then ``BackendSettings`` / ``OPERION_POSTGRES_DSN``), defaulting to the
    SQLite dev DB.  Without these env vars the g8c9/o8g9 TIMESTAMPTZ
    migrations were being applied to ``data/cashflow.db`` (alembic stamped it
    ``a9b0c1d2e3f4``) while the PG test DB kept its schema_pg.sql TEXT
    columns.  Set both vars for the duration of the boot so Alembic targets
    THIS database (same idiom as tests/migrations/test_all_migrations.py).
    """
    from database.db_manager import DatabaseManager

    old_engine = os.environ.get("OPERION_DB_ENGINE")
    old_dsn = os.environ.get("OPERION_POSTGRES_DSN")
    os.environ["OPERION_DB_ENGINE"] = "postgresql"
    os.environ["OPERION_POSTGRES_DSN"] = TEST_DSN
    try:
        try:
            db = DatabaseManager(TEST_DSN, engine="postgresql")
        except Exception as exc:
            pytest.skip(f"PostgreSQL unavailable: {exc}")
        db.close()
    finally:
        if old_engine is None:
            os.environ.pop("OPERION_DB_ENGINE", None)
        else:
            os.environ["OPERION_DB_ENGINE"] = old_engine
        if old_dsn is None:
            os.environ.pop("OPERION_POSTGRES_DSN", None)
        else:
            os.environ["OPERION_POSTGRES_DSN"] = old_dsn
    yield
    _drop_test_db()


@pytest.fixture
def pg_conn(pg_schema):
    import psycopg2
    from psycopg2.extras import RealDictCursor

    try:
        conn = psycopg2.connect(TEST_DSN, cursor_factory=RealDictCursor, connect_timeout=5)
        conn.autocommit = False
    except Exception as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield conn
    try:
        conn.rollback()
    except Exception:
        pass
    try:
        conn.close()
    except Exception:
        pass


def _pg_scalar(pg_conn, sql, params=()):
    """Run a scalar query whose SELECT list is `... AS v`, return the value."""
    cur = pg_conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    return row["v"] if row is not None else None


def _pg_canonical_ts(pg_conn, sql, params=()):
    """Run a scalar query whose SELECT list is `... AS ts`, return the value."""
    cur = pg_conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    return row["ts"] if row is not None else None


def _canonical(column: str) -> str:
    """SQL expression rendering a timestamptz column as a Z-suffixed UTC string."""
    return (
        f"to_char({column} AT TIME ZONE 'UTC', "
        f"'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')"
    )


# ── T1: native column types ────────────────────────────────────────────────

# Every Phase-D target column (g8c9d0e1f2f0 + o8g9b0c2e5f6 + schema-owned),
# exactly as the plan's critical tables specify.
_PHASE_D_TIMESTAMP_COLUMNS = [
    # trips
    ("trips", "deleted_at"),
    ("trips", "created_at"),
    ("trips", "start_date"),
    # invoices
    ("invoices", "issue_date"),
    ("invoices", "due_date"),
    ("invoices", "created_at"),
    # route_history_v2
    ("route_history_v2", "last_calculated_at"),
    ("route_history_v2", "archived_at"),
    # trip_status_history
    ("trip_status_history", "created_at"),
    # truck_route_assignments (schema_pg.sql ~323-334)
    ("truck_route_assignments", "assigned_at"),
    ("truck_route_assignments", "started_at"),
    ("truck_route_assignments", "completed_at"),
    ("truck_route_assignments", "archived_at"),
    # gps_telemetry
    ("gps_telemetry", "recorded_at"),
    # operation_events
    ("operation_events", "created_at"),
    # documents
    ("documents", "expiry_date"),
]


@pytest.mark.parametrize(
    "table_name,column_name",
    _PHASE_D_TIMESTAMP_COLUMNS,
)
def test_pg_phase_d_columns_are_timestamptz(pg_conn, table_name, column_name):
    """Every Phase-D target column is native ``timestamp with time zone``."""
    data_type = _pg_scalar(
        pg_conn,
        "SELECT data_type AS v FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s AND column_name = %s",
        (table_name, column_name),
    )
    assert data_type == "timestamp with time zone", (
        f"{table_name}.{column_name}: expected 'timestamp with time zone', "
        f"got {data_type!r}"
    )


# ── T2: USING CASE conversion semantics ────────────────────────────────────


def test_pg_using_case_conversion_semantics(pg_conn):
    """The migrations' verbatim ALTER...USING CASE: ''→NULL, date-only→UTC
    midnight, full ISO preserved, NULL stays NULL."""
    cur = pg_conn.cursor()
    cur.execute("DROP TABLE IF EXISTS dt_scratch_usecase")
    cur.execute("CREATE TABLE dt_scratch_usecase (label TEXT, ts_col TEXT)")
    cur.execute(
        "INSERT INTO dt_scratch_usecase (label, ts_col) "
        "VALUES (%s, %s), (%s, %s), (%s, %s), (%s, %s)",
        ("empty", "", "date", "2026-07-21", "iso", "2026-07-21T08:30:00Z",
         "null", None),
    )
    # Verbatim from g8c9d0e1f2f0 / o8g9b0c2e5f6 nullable-column USING CASE.
    cur.execute(
        """
        ALTER TABLE dt_scratch_usecase
        ALTER COLUMN ts_col TYPE TIMESTAMPTZ
        USING CASE
            WHEN ts_col = '' OR ts_col IS NULL THEN NULL
            WHEN ts_col ~ '^\\d{4}-\\d{2}-\\d{2}$' THEN (ts_col || 'T00:00:00Z')::TIMESTAMPTZ
            ELSE ts_col::TIMESTAMPTZ
        END
        """
    )
    pg_conn.commit()
    try:
        # The scratch column is now native timestamptz.
        data_type = _pg_scalar(
            pg_conn,
            "SELECT data_type AS v FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'dt_scratch_usecase' "
            "AND column_name = 'ts_col'",
        )
        assert data_type == "timestamp with time zone", data_type

        # '' → NULL
        assert _pg_scalar(
            pg_conn, "SELECT (ts_col IS NULL) AS v FROM dt_scratch_usecase WHERE label = %s",
            ("empty",),
        ) is True, "'' should convert to NULL"

        # NULL stays NULL
        assert _pg_scalar(
            pg_conn, "SELECT (ts_col IS NULL) AS v FROM dt_scratch_usecase WHERE label = %s",
            ("null",),
        ) is True, "NULL should stay NULL"

        # date-only → UTC midnight
        assert _pg_canonical_ts(
            pg_conn,
            "SELECT " + _canonical("ts_col") + " AS ts FROM dt_scratch_usecase WHERE label = %s",
            ("date",),
        ) == "2026-07-21T00:00:00Z"

        # full ISO preserved
        assert _pg_canonical_ts(
            pg_conn,
            "SELECT " + _canonical("ts_col") + " AS ts FROM dt_scratch_usecase WHERE label = %s",
            ("iso",),
        ) == "2026-07-21T08:30:00Z"
    finally:
        cur.execute("DROP TABLE IF EXISTS dt_scratch_usecase")
        pg_conn.commit()


# ── T3: updated_at trigger stamps native timestamptz ───────────────────────


_STAMP_RE = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"


def test_pg_updated_at_trigger_stamps_native_timestamptz(pg_conn):
    """The stamping trigger writes a native TIMESTAMPTZ (UTC canonical) even
    when the session timezone is not UTC; a later UPDATE re-stamps."""
    truck = f"DT-PG-T3-{uuid.uuid4().hex[:8]}"
    cur = pg_conn.cursor()
    cur.execute("SET TIME ZONE 'America/New_York'")
    try:
        cur.execute("INSERT INTO trips (truck_number) VALUES (%s)", (truck,))
        pg_conn.commit()

        first = _pg_canonical_ts(
            pg_conn,
            "SELECT " + _canonical("updated_at") + " AS ts FROM trips WHERE truck_number = %s",
            (truck,),
        )
        if first is None:
            pytest.fail("updated_at was not stamped on INSERT")
        assert re.fullmatch(
            _STAMP_RE, first or ""
        ), f"updated_at not a canonical UTC stamp: {first!r}"

        # The stamp is stored as a real timestamptz column.
        pg_type = _pg_scalar(
            pg_conn,
            "SELECT pg_typeof(updated_at)::text AS v FROM trips WHERE truck_number = %s",
            (truck,),
        )
        assert pg_type == "timestamp with time zone", pg_type

        # Cross a second boundary so the second-precision re-stamp differs.
        time.sleep(1.1)
        cur.execute(
            "UPDATE trips SET client_name = 'T3' WHERE truck_number = %s", (truck,)
        )
        pg_conn.commit()

        second = _pg_canonical_ts(
            pg_conn,
            "SELECT " + _canonical("updated_at") + " AS ts FROM trips WHERE truck_number = %s",
            (truck,),
        )
        assert second != first, "updated_at was not re-stamped on UPDATE"
        assert re.fullmatch(
            _STAMP_RE, second or ""
        ), f"re-stamped updated_at malformed: {second!r}"
    finally:
        cur.execute("SET TIME ZONE 'UTC'")
        try:
            cur.execute("DELETE FROM trips WHERE truck_number = %s", (truck,))
            pg_conn.commit()
        except Exception:
            pg_conn.rollback()


# ── T4: date arithmetic on converted invoice columns ───────────────────────


def test_pg_invoice_date_arithmetic(pg_conn):
    """issue_date → due_date is a native 30-day span after conversion."""
    inv = f"DT-PG-T4-{uuid.uuid4().hex[:8]}"
    cur = pg_conn.cursor()
    cur.execute(
        "INSERT INTO invoices (invoice_number, issue_date, due_date) "
        "VALUES (%s, %s, %s)",
        (inv, "2026-07-01T00:00:00Z", "2026-07-31T00:00:00Z"),
    )
    pg_conn.commit()
    try:
        days = _pg_scalar(
            pg_conn,
            "SELECT EXTRACT(DAY FROM "
            "(due_date AT TIME ZONE 'UTC') - (issue_date AT TIME ZONE 'UTC'))::int AS v "
            "FROM invoices WHERE invoice_number = %s",
            (inv,),
        )
        assert days == 30, f"expected 30-day diff, got {days!r}"
    finally:
        cur = pg_conn.cursor()
        cur.execute("DELETE FROM invoices WHERE invoice_number = %s", (inv,))
        pg_conn.commit()


# ── T5: date-only ingest lands at UTC midnight ─────────────────────────────


def test_pg_date_only_ingest_lands_at_utc_midnight(pg_conn):
    """A date-only string ingested into a converted timestamptz column is
    stored as UTC midnight (not local midnight)."""
    truck = f"DT-PG-T5-{uuid.uuid4().hex[:8]}"
    cur = pg_conn.cursor()
    cur.execute("SET TIME ZONE 'UTC'")
    try:
        cur.execute(
            "INSERT INTO trips (truck_number, start_date) VALUES (%s, %s)",
            (truck, "2026-07-21"),
        )
        pg_conn.commit()

        ts = _pg_canonical_ts(
            pg_conn,
            "SELECT " + _canonical("start_date") + " AS ts FROM trips WHERE truck_number = %s",
            (truck,),
        )
        assert ts == "2026-07-21T00:00:00Z", f"expected UTC midnight, got {ts!r}"

        pg_type = _pg_scalar(
            pg_conn,
            "SELECT pg_typeof(start_date)::text AS v FROM trips WHERE truck_number = %s",
            (truck,),
        )
        assert pg_type == "timestamp with time zone", pg_type
    finally:
        cur.execute("SET TIME ZONE 'UTC'")
        try:
            cur.execute("DELETE FROM trips WHERE truck_number = %s", (truck,))
            pg_conn.commit()
        except Exception:
            pg_conn.rollback()


# ── T6: trips.month generated column over TIMESTAMPTZ created_at ───────────


def test_pg_trips_month_generated_column(pg_conn):
    """The recreated ``trips.month`` generated column derives YYYY-MM from the
    (now timestamptz) created_at in UTC."""
    truck = f"DT-PG-T6-{uuid.uuid4().hex[:8]}"
    cur = pg_conn.cursor()
    cur.execute(
        "INSERT INTO trips (truck_number, created_at) VALUES (%s, %s)",
        (truck, "2026-07-15T08:00:00Z"),
    )
    pg_conn.commit()
    try:
        month = _pg_scalar(
            pg_conn, "SELECT month AS v FROM trips WHERE truck_number = %s", (truck,)
        )
        assert month == "2026-07", f"expected '2026-07', got {month!r}"
    finally:
        cur = pg_conn.cursor()
        cur.execute("DELETE FROM trips WHERE truck_number = %s", (truck,))
        pg_conn.commit()
