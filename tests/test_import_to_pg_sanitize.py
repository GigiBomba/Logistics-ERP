"""Tests for scripts/import_to_pg.py trips FK sanitation (Database_Rework P0.8).

schema_pg.sql declares ``fk_trips_driver`` / ``fk_trips_truck`` as NOT VALID
foreign keys (ON DELETE SET NULL) so the boot stays safe on legacy SQLite rows
whose driver_id/truck_id reference drivers/trucks that were deleted later.
``ALTER TABLE trips VALIDATE CONSTRAINT`` would reject those orphan rows, so
the importer must NULL them BEFORE validating.

Verified here:
* offline (no PostgreSQL needed): a synthetic dump containing trips with one
  orphan driver_id and one orphan truck_id is imported; the orphan ids are
  NULLed, orphan counts are reported, and VALIDATE runs for both constraints;
  older PG schemas without the constraints get a warning and skip VALIDATE;
  the step can be disabled via ``sanitize_fks=False``.
* live PostgreSQL (skipped when unavailable): same on the REAL
  ``DatabaseManager`` path — orphan values are NULL after import and
  ``pg_constraint.convalidated`` becomes true for both FKs.
"""
from __future__ import annotations

import json
import os
import re

import pytest

from scripts.import_to_pg import TRIPS_FK_SANITIZE, import_from_json

TEST_DSN = os.environ.get(
    "OPERION_TEST_POSTGRES_DSN",
    "postgresql://operion:operion_test_ci@localhost:5432/operion_test_san",
)

#: Per-file isolated database name — this module owns ``operion_test_san`` so
#: its own schema build / DDL can never collide with other test files' on the
#: shared ``operion_test`` database (xdist `-n 2` concurrent runs).
_TEST_DB_NAME = "operion_test_san"

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


# ── Synthetic dump + offline fake ──────────────────────────────────────────


def _write_dump(tmp_path, tables: dict) -> str:
    """Write a synthetic export dump and return its path."""
    path = tmp_path / "dump_sanitize.json"
    path.write_text(
        json.dumps({"exported_at": "2026-01-01T00:00:00", "tables": tables}),
        encoding="utf-8",
    )
    return str(path)


def _synthetic_tables() -> dict:
    """drivers/trucks/trips with one valid and one orphan ref each in trips.

    Trips row ``id=10`` references real driver 1 / truck 2; trips row ``id=11``
    references deleted driver 999 / truck 888 (the legacy-dump orphan case).
    """
    return {
        "drivers": [
            {"id": 1, "name": "D1", "created_at": "2026-01-01",
             "updated_at": "2026-01-01 00:00:00"}
        ],
        "trucks": [
            {"id": 2, "plate_number": "B-01-ABC", "updated_at": "2026-01-01 00:00:00"}
        ],
        "trips": [
            {"id": 10, "driver_id": 1, "truck_id": 2},
            {"id": 11, "driver_id": 999, "truck_id": 888},
        ],
    }


def _schema_rows() -> list:
    """information_schema.columns rows for the three synthetic tables.

    ``is_generated`` is 'NEVER' for every column (the generated trips.month is
    simply not present, so the importer never tries to insert it).
    """
    columns = {
        "drivers": {"id": "bigint", "name": "text", "created_at": "text",
                    "updated_at": "timestamp with time zone"},
        "trucks": {"id": "bigint", "plate_number": "text",
                   "updated_at": "timestamp with time zone"},
        "trips": {"id": "bigint", "driver_id": "integer", "truck_id": "integer"},
    }
    return [
        {"table_name": table, "column_name": col, "data_type": dtype,
         "is_generated": "NEVER"}
        for table, cols in columns.items()
        for col, dtype in cols.items()
    ]


class _FakeCursor:
    def __init__(self, rows=None, rowcount=0):
        self._rows = rows if rows is not None else []
        self.rowcount = rowcount

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    """Offline DatabaseManager stand-in.

    Records every SQL statement and answers the info-schema / constraint /
    orphan-count queries the import + sanitize flow issues, so
    ``import_from_json`` can be exercised without a live PostgreSQL.
    """

    def __init__(self, schema_rows, existing_constraints=(), orphan_counts=None):
        self.schema_rows = schema_rows
        self.existing_constraints = set(existing_constraints)
        self.orphan_counts = dict(orphan_counts or {})
        self.calls = []  # (sql, params)
        self.closed = False

    def rows_to_dicts(self, rows):
        return list(rows)

    def execute(self, query, params=()):
        self.calls.append((query, tuple(params)))
        low = query.lower()
        # Schema map query (import phase).
        if "information_schema.columns" in low:
            return _FakeCursor(rows=self.schema_rows)
        # Guarded VALIDATE existence check (sanitize phase).
        if "information_schema.table_constraints" in low:
            name = params[0] if params else ""
            return _FakeCursor(rows=[(1,)] if name in self.existing_constraints else [])
        # Orphan count query (sanitize phase) — identify the column.
        if "count(*)" in low:
            col = re.search(r"t\.(\w+)\s+IS\s+NOT\s+NULL", query, re.IGNORECASE)
            col = col.group(1) if col else "?"
            return _FakeCursor(rows=[(self.orphan_counts.get(col, 0),)])
        return _FakeCursor()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True


def _run_import(tmp_path, monkeypatch, tables, *, sanitize_fks=True, **fake_kwargs):
    """Run the full import flow against a recording fake DatabaseManager."""
    import scripts.import_to_pg as mod

    fake = _FakeDB(schema_rows=_schema_rows(), **fake_kwargs)
    monkeypatch.setattr(mod, "DatabaseManager", lambda dsn, **kw: fake)
    stats = import_from_json(
        _write_dump(tmp_path, tables), "postgresql://fake", sanitize_fks=sanitize_fks
    )
    return fake, stats


# ── Offline tests ──────────────────────────────────────────────────────────


def test_orphan_trip_fks_nulled_and_validated(tmp_path, monkeypatch):
    """Legacy orphan driver_id/truck_id are NULLed, then both FKs VALIDATE."""
    fake, stats = _run_import(
        tmp_path,
        monkeypatch,
        _synthetic_tables(),
        existing_constraints=("fk_trips_driver", "fk_trips_truck"),
        orphan_counts={"driver_id": 1, "truck_id": 1},
    )

    # Orphan counts were logged before the cleanup.
    assert stats["trips_fk_orphans"] == {"driver_id": 1, "truck_id": 1}
    assert stats["trips_fk_validated"] == ["fk_trips_driver", "fk_trips_truck"]
    assert stats["errors"] == 0
    assert stats["total_rows"] == 4  # 1 driver + 1 truck + 2 trips

    # The exact UPDATE statements from the spec ran.
    updates = [sql for sql, _ in fake.calls if sql.startswith("UPDATE trips SET")]
    assert updates == [
        "UPDATE trips SET driver_id = NULL WHERE driver_id IS NOT NULL "
        "AND driver_id NOT IN (SELECT id FROM drivers)",
        "UPDATE trips SET truck_id = NULL WHERE truck_id IS NOT NULL "
        "AND truck_id NOT IN (SELECT id FROM trucks)",
    ]

    # Count -> UPDATE -> VALIDATE per constraint, driver first then truck.
    order = {sql: i for i, (sql, _) in enumerate(fake.calls)}
    assert order["UPDATE trips SET driver_id = NULL WHERE driver_id IS NOT NULL "
                  "AND driver_id NOT IN (SELECT id FROM drivers)"] < order[
        "UPDATE trips SET truck_id = NULL WHERE truck_id IS NOT NULL "
        "AND truck_id NOT IN (SELECT id FROM trucks)"
    ]
    for update_sql, validate_sql in (
        (updates[0], "ALTER TABLE trips VALIDATE CONSTRAINT fk_trips_driver"),
        (updates[1], "ALTER TABLE trips VALIDATE CONSTRAINT fk_trips_truck"),
    ):
        assert order[update_sql] < order[validate_sql], (
            f"{validate_sql} ran before the orphan cleanup"
        )

    validates = [sql for sql, _ in fake.calls if "VALIDATE CONSTRAINT" in sql]
    assert validates == [
        "ALTER TABLE trips VALIDATE CONSTRAINT fk_trips_driver",
        "ALTER TABLE trips VALIDATE CONSTRAINT fk_trips_truck",
    ]

    # Orphan count queries ran for both columns before their updates.
    counts = [sql for sql, _ in fake.calls if "count(*)" in sql.lower()]
    assert len(counts) == 2
    assert order[counts[0]] < order[updates[0]]
    assert order[counts[1]] < order[updates[1]]


def test_missing_constraints_skip_validate_without_error(tmp_path, monkeypatch):
    """Older PG schemas without the FKs still get orphans NULLed, VALIDATE skipped."""
    fake, stats = _run_import(
        tmp_path,
        monkeypatch,
        _synthetic_tables(),
        existing_constraints=(),  # legacy PG schema: constraints absent
        orphan_counts={"driver_id": 1, "truck_id": 0},
    )

    # Orphans were still sanitized...
    updates = [sql for sql, _ in fake.calls if sql.startswith("UPDATE trips SET")]
    assert len(updates) == 2
    assert stats["trips_fk_orphans"] == {"driver_id": 1, "truck_id": 0}

    # ...but neither VALIDATE ran (constraint absent -> warning + skip).
    assert stats["trips_fk_validated"] == []
    validates = [sql for sql, _ in fake.calls if "VALIDATE CONSTRAINT" in sql]
    assert validates == []
    assert stats["errors"] == 0


def test_sanitize_step_skippable(tmp_path, monkeypatch):
    """``sanitize_fks=False`` leaves the orphan ids untouched and skips VALIDATE."""
    fake, stats = _run_import(
        tmp_path,
        monkeypatch,
        _synthetic_tables(),
        sanitize_fks=False,
        existing_constraints=("fk_trips_driver", "fk_trips_truck"),
    )

    assert stats["total_rows"] == 4
    assert not any(sql.startswith("UPDATE trips SET") for sql, _ in fake.calls)
    assert not any("VALIDATE CONSTRAINT" in sql for sql, _ in fake.calls)
    assert "trips_fk_orphans" not in stats


# ── PostgreSQL integration (skip when unavailable) ─────────────────────────


@pytest.fixture(scope="module")
def pg_schema():
    """Build the real PG schema (idempotent) so trips/drivers/trucks exist.

    ``operion_test_san`` may be freshly created (or schema-less); the
    deployment path — ``DatabaseManager(dsn, engine="postgresql")`` — runs
    schema_pg.sql + Alembic + ``_apply_pg_extra_ddl`` and is safe to run
    repeatedly.  Each statement runs in its own autocommit transaction, so a
    single failure cannot abort the rest of the build.
    """
    from database.db_manager import DatabaseManager

    try:
        db = DatabaseManager(TEST_DSN, engine="postgresql")
    except Exception as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    db.close()
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


def test_live_import_nulls_orphans_and_validates(pg_conn, tmp_path):
    """Real PG: orphan ids are NULL after import and both FKs become valid.

    This exercises the whole ``import_from_json`` flow (including its own
    DatabaseManager/schema build) against the live database.  The FK
    constraints are created NOT VALID by schema_pg.sql, so the orphan rows can
    be inserted during the import (``session_replication_role = 'replica'``)
    and must be NULLed before VALIDATE succeeds.
    """
    stats = import_from_json(_write_dump(tmp_path, _synthetic_tables()), TEST_DSN)

    assert stats["trips_fk_orphans"] == {"driver_id": 1, "truck_id": 1}
    assert set(stats["trips_fk_validated"]) == {"fk_trips_driver", "fk_trips_truck"}
    assert stats["errors"] == 0

    # The orphan trip's refs were NULLed; the valid trip's refs were kept.
    cur = pg_conn.cursor()
    cur.execute("SELECT id, driver_id, truck_id FROM trips ORDER BY id")
    rows = {r["id"]: (r["driver_id"], r["truck_id"]) for r in cur.fetchall()}
    assert rows[10] == (1, 2)
    assert rows[11] == (None, None)

    # Both constraints are now validated (convalidated = true).
    cur.execute(
        "SELECT conname, convalidated FROM pg_catalog.pg_constraint "
        "WHERE conrelid = 'trips'::regclass AND contype = 'f' "
        "  AND conname IN ('fk_trips_driver', 'fk_trips_truck')"
    )
    validated = {r["conname"]: r["convalidated"] for r in cur.fetchall()}
    assert validated == {"fk_trips_driver": True, "fk_trips_truck": True}, (
        f"FKs not validated after sanitized import: {validated}"
    )

    # Clean up the imported rows so a second run / drop stays deterministic.
    cur.execute("DELETE FROM trips WHERE id IN (10, 11)")
    cur.execute("DELETE FROM trucks WHERE id = 2")
    cur.execute("DELETE FROM drivers WHERE id = 1")
    pg_conn.commit()