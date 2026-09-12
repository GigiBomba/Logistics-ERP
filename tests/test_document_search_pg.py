"""Offline SQL-capture tests for the PostgreSQL full-text search switch.

``fts_search()`` / ``fts_search_count()`` previously built ILIKE term loops in
the ``postgresql`` branch, ignoring the ``search_vector tsvector`` column
(schema_pg.sql §FTS) that the ``documents_search_update()`` trigger maintains.
This unit switches the PG path to ``search_vector @@ plainto_tsquery(...)``;
the SQLite FTS5 path must stay byte-identical.

The tests are fully offline: they mirror the ``_make_pg_db`` stub pattern from
test_backfill_updated_at.py — build the repository against a DatabaseManager
stub whose ``_engine`` selects the branch, mock ``_fetchall``/``_fetchone``,
and assert on the produced SQL/params.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repositories.document_repository import DocumentRepository


class _StubDB:
    """Minimal DatabaseManager stand-in carrying only the engine flag."""

    def __init__(self, engine: str) -> None:
        self._engine = engine


@pytest.fixture
def pg_repo() -> DocumentRepository:
    repo = DocumentRepository(_StubDB("postgresql"))
    repo._fetchall = MagicMock(return_value=[])
    repo._fetchone = MagicMock(return_value={"cnt": 3})
    return repo


@pytest.fixture
def sqlite_repo() -> DocumentRepository:
    repo = DocumentRepository(_StubDB("sqlite"))
    repo._fetchall = MagicMock(return_value=[])
    repo._fetchone = MagicMock(return_value={"cnt": 3})
    return repo


# ── PostgreSQL: tsvector path ────────────────────────────────────────────


def test_pg_fts_search_uses_tsvector(pg_repo):
    """PG fts_search must match the tsvector column, never ILIKE."""
    pg_repo.fts_search(query="invoice", category="invoices", limit=10, offset=5)

    sql, params = pg_repo._fetchall.call_args[0]
    assert "d.search_vector @@ plainto_tsquery('english', ?)" in sql
    assert "ILIKE" not in sql
    assert "d.title ILIKE" not in sql
    # SELECT list / joins unchanged (d.* + documents table).
    assert sql.startswith("SELECT d.* FROM documents d")
    assert "LIMIT ? OFFSET ?" in sql
    assert params == ("invoice", "invoices", 10, 5)


def test_pg_fts_search_count_uses_tsvector(pg_repo):
    """PG fts_search_count must match the tsvector column too."""
    assert pg_repo.fts_search_count(query="invoice", category="invoices") == 3

    sql, params = pg_repo._fetchone.call_args[0]
    assert "d.search_vector @@ plainto_tsquery('english', ?)" in sql
    assert "ILIKE" not in sql
    assert sql.startswith("SELECT COUNT(*) AS cnt FROM documents d")
    assert params == ("invoice", "invoices")


def test_pg_multi_word_query_is_single_tsquery_param(pg_repo):
    """A multi-word query becomes ONE plainto_tsquery param, no term loop."""
    pg_repo.fts_search(query="  invoice   may  ")

    sql, params = pg_repo._fetchall.call_args[0]
    assert sql.count("plainto_tsquery") == 1
    assert "%" not in sql
    assert " OR " not in sql
    assert params[0] == "invoice   may"  # stripped, single bound value


def test_pg_placeholders_adapt_to_percent_s(pg_repo):
    """The raw ? placeholder is adapted to %s for the PG driver."""
    pg_repo.fts_search(query="invoice")

    sql, _ = pg_repo._fetchall.call_args[0]
    adapted = pg_repo._adapt_query(sql)
    assert "plainto_tsquery('english', %s)" in adapted
    assert "?" not in adapted


def test_pg_empty_query_keeps_guard(pg_repo):
    """Empty query keeps the old guard: no search condition appended."""
    pg_repo.fts_search(query="")

    sql, params = pg_repo._fetchall.call_args[0]
    assert "plainto_tsquery" not in sql
    assert "documents_fts" not in sql
    assert params == (20, 0)  # only the LIMIT/OFFSET tail remains


def test_pg_whitespace_query_preserved_by_guard(pg_repo):
    """The guard is ``if query:`` (unchanged), so whitespace-only input still
    enters the branch — the query is then stripped to an empty tsquery value."""
    pg_repo.fts_search(query="   ")

    sql, params = pg_repo._fetchall.call_args[0]
    assert "plainto_tsquery('english', ?)" in sql
    assert params == ("", 20, 0)


# ── SQLite: FTS5 path unchanged ─────────────────────────────────────────


def test_sqlite_fts_search_still_uses_fts_match(sqlite_repo):
    """SQLite fts_search must keep emitting the documents_fts MATCH query."""
    sqlite_repo.fts_search(query="invoice")

    sql, params = sqlite_repo._fetchall.call_args[0]
    assert "documents_fts WHERE documents_fts MATCH ?" in sql
    assert "search_vector" not in sql
    assert "ILIKE" not in sql
    assert params[0] == '"invoice"'


def test_sqlite_fts_search_count_still_uses_fts_match(sqlite_repo):
    """SQLite fts_search_count must keep emitting documents_fts MATCH."""
    assert sqlite_repo.fts_search_count(query="invoice") == 3

    sql, params = sqlite_repo._fetchone.call_args[0]
    assert "documents_fts WHERE documents_fts MATCH ?" in sql
    assert "search_vector" not in sql
    assert "ILIKE" not in sql
    assert params[0] == '"invoice"'


def test_sqlite_fts_search_byte_identical_contract(sqlite_repo):
    """The SQLite SQL shape (SELECT list, join/table, order, limit) is
    unchanged by the PG switch — same statement skeleton as before."""
    sqlite_repo.fts_search(query="invoice", category="invoices", limit=20, offset=0)

    sql, params = sqlite_repo._fetchall.call_args[0]
    assert sql.startswith("SELECT d.* FROM documents d")
    assert "ORDER BY uploaded_at DESC LIMIT ? OFFSET ?" in sql
    assert params == ('"invoice"', "invoices", 20, 0)


# ── NF1: NULL search_vector backfill on the native-PG boot path ──────────
#
# On a PG database that predates the ``search_vector`` column (the
# ``ALTER TABLE documents ADD COLUMN IF NOT EXISTS search_vector tsvector``
# upgrade), every existing document carries a NULL vector and is unfindable
# via ``fts_search``/``fts_search_count`` until edited.  The import path
# backfills (scripts/import_to_pg.py); the native-PG boot path must too —
# ``DatabaseManager._apply_pg_extra_ddl`` runs after Alembic on every boot.
#
# These tests are fully offline: they capture the real extra-DDL statements
# with a recording connection and pin the finder/backfill SQL contract.


class _CaptureCursor:
    """Cursor stand-in that records every executed statement."""

    def __init__(self, sink: list) -> None:
        self._sink = sink

    def execute(self, sql, params=None):  # noqa: D401 - mirrors DB-API cursor
        self._sink.append(sql)

    def close(self) -> None:
        pass


class _CaptureConn:
    def __init__(self, sink: list) -> None:
        self._sink = sink

    def cursor(self) -> _CaptureCursor:
        return _CaptureCursor(self._sink)


class _CaptureConnHolder:
    def __init__(self, conn: _CaptureConn) -> None:
        self._conn = conn

    def get_cached_connection(self) -> _CaptureConn:
        return self._conn


def _capture_pg_extra_ddl() -> list:
    """Run the REAL ``_apply_pg_extra_ddl`` against a recording connection.

    Returns the exact, fully-concatenated DDL strings the boot path would
    execute — no PostgreSQL connection required.
    """
    from database.db_manager import DatabaseManager

    sink: list = []
    db = DatabaseManager.__new__(DatabaseManager)
    db._engine = "postgresql"
    db._pg_pool = _CaptureConnHolder(_CaptureConn(sink))
    db._apply_pg_extra_ddl()
    return sink


def test_pg_extra_ddl_contains_null_search_vector_backfill():
    """The native-PG boot extra-DDL list must contain the one-shot NULL
    ``search_vector`` backfill (NF1)."""
    backfills = [
        s for s in _capture_pg_extra_ddl()
        if "UPDATE documents SET search_vector" in s
    ]
    assert backfills, (
        "DatabaseManager._apply_pg_extra_ddl has no search_vector backfill — "
        "NULL vectors on pre-column PG DBs stay unfindable at boot (NF1)"
    )
    assert len(backfills) == 1, f"expected exactly one backfill, got {backfills!r}"

    stmt = " ".join(backfills[0].split())
    assert "to_tsvector('english'," in stmt
    # Mirrors DocumentRepository.rebuild_fts_index exactly: same columns, order.
    assert (
        "COALESCE(title,'') || ' ' || COALESCE(description,'') || ' ' "
        "|| COALESCE(text_content,''))" in stmt
    ), f"backfill expression must mirror rebuild_fts_index, got: {stmt}"
    # Idempotent: targets only NULL vectors.
    assert stmt.endswith("WHERE search_vector IS NULL"), (
        f"backfill must be NULL-only (idempotent), got: {stmt}"
    )


def test_null_search_vector_not_matched_until_backfill(pg_repo):
    """NULL ``search_vector`` rows are not matched by the tsvector query until
    the boot backfill runs.

    Offline: pin both halves of the contract on the generated SQL.  SQL
    three-valued logic makes ``NULL @@ tsquery`` evaluate to NULL (not TRUE),
    so a bare ``search_vector @@ ...`` predicate excludes NULL rows — and the
    boot backfill fills exactly the rows where ``search_vector IS NULL``.
    """
    # 1) The finder never falls back to unindexed/NULL rows.
    pg_repo.fts_search(query="invoice")
    search_sql, _ = pg_repo._fetchall.call_args[0]
    assert "d.search_vector @@ plainto_tsquery('english', ?)" in search_sql
    assert "search_vector IS NULL" not in search_sql, (
        "fts_search must not special-case NULL vectors; they are not matched"
    )
    assert "d.search_vector IS NOT NULL" not in search_sql

    # 2) The boot backfill targets exactly the rows the finder skips.
    backfills = [
        s for s in _capture_pg_extra_ddl()
        if "UPDATE documents SET search_vector" in s
    ]
    assert len(backfills) == 1
    assert " ".join(backfills[0].split()).endswith("WHERE search_vector IS NULL")