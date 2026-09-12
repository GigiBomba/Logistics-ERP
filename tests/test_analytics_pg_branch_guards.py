"""Verify-only regression: PG branches in analytics_repository are PG-clean.

The audit flagged ``JULIANDAY``/``SUBSTR(``/``DATE(`` SQLite-only constructs in
``repositories/analytics_repository.py`` (~lines 319, 768-769, 823 for
JULIANDAY; ~504/525 for the SUBSTR month expressions).  Re-verification
confirmed all of them sit inside engine-gated SQLite-only ``else:`` branches —
the ``_engine == "postgresql"`` branches already emit PG-compatible arithmetic.

This file pins that behaviour with capture-SQL tests (no production edits):

* with a ``postgresql`` engine stub, the SQL produced by each covered method
  contains NONE of ``JULIANDAY``, ``SUBSTR(``, ``DATE(``;
* flipping the stub to ``sqlite`` proves the SQLite-only branch is still the
  one being exercised (JULIANDAY present for the JULIANDAY methods, ``SUBSTR(``
  present for the SUBSTRING/SUBSTR methods).
"""
from __future__ import annotations

import pytest

from repositories.analytics_repository import AnalyticsRepository

#: Methods whose engine gate splits on JULIANDAY (SQLite-only branch).
JULIANDAY_METHODS = [
    "get_client_analytics",           # gate ~313, JULIANDAY ~319
    "get_client_payment_timeline",    # gate ~756, JULIANDAY ~768-769
    "get_driver_monthly_activity",    # gate ~817, JULIANDAY ~823
]

#: Methods whose engine gate splits on SUBSTR( (SQLite) vs SUBSTRING (PG).
#: ``get_client_growth`` (expr ~504) and ``get_document_upload_trend`` (expr
#: ~525) are the methods at the audit's referenced lines 504/525; there is no
#: ``get_monthly_revenue`` in this repository.
SUBSTR_METHODS = [
    "get_revenue_quarterly",
    "get_client_growth",
    "get_document_upload_trend",
]

ALL_METHODS = JULIANDAY_METHODS + SUBSTR_METHODS

#: SQLite-only constructs that must never appear in a PG-path query.
SQLITE_ONLY_MARKERS = ("JULIANDAY", "SUBSTR(", "DATE(")


def _make_db(engine):
    """Minimal ``DatabaseManager`` stub carrying only ``_engine``.

    Mirrors the ``_make_pg_db`` pattern from ``test_backfill_updated_at.py``
    (``DatabaseManager.__new__`` + ``_engine``); no connection is needed
    because ``_fetchall``/``_fetchone`` are mocked at the repo level.
    """
    from database.db_manager import DatabaseManager

    db = DatabaseManager.__new__(DatabaseManager)
    db._engine = engine
    return db


def _capture_sql(engine, method_name):
    """Call *method_name* against an engine stub and capture every SQL string.

    ``_fetchall``/``_fetchone`` are replaced with recorders that return empty
    results, so query construction is exercised without touching a real DB.
    Fails loudly when the method produced no SQL (SQL-construction errors are
    NOT swallowed).
    """
    repo = AnalyticsRepository(_make_db(engine))
    captured = []

    def _fake_fetchall(query, params=()):
        captured.append(query)
        return []

    def _fake_fetchone(query, params=()):
        captured.append(query)
        return None

    repo._fetchall = _fake_fetchall
    repo._fetchone = _fake_fetchone

    getattr(repo, method_name)()

    assert captured, (
        f"{method_name} produced no SQL on engine={engine!r} "
        "(query construction error?)"
    )
    return captured


@pytest.mark.parametrize("method_name", ALL_METHODS)
def test_pg_path_has_no_sqlite_only_sql(method_name):
    """PG branch must never emit JULIANDAY / SUBSTR( / DATE(."""
    queries = _capture_sql("postgresql", method_name)
    for sql in queries:
        for marker in SQLITE_ONLY_MARKERS:
            assert marker not in sql, (
                f"{method_name} PG path leaked SQLite-only {marker!r}:\n{sql}"
            )


@pytest.mark.parametrize("method_name", JULIANDAY_METHODS)
def test_sqlite_path_still_uses_julianday(method_name):
    """Flipping to sqlite must still exercise the JULIANDAY branch."""
    queries = _capture_sql("sqlite", method_name)
    assert any("JULIANDAY" in sql for sql in queries), (
        f"{method_name} SQLite path no longer exercises JULIANDAY:\n{queries}"
    )


@pytest.mark.parametrize("method_name", SUBSTR_METHODS)
def test_sqlite_path_still_uses_substr(method_name):
    """Flipping to sqlite must still exercise the SUBSTR( branch."""
    queries = _capture_sql("sqlite", method_name)
    assert any("SUBSTR(" in sql for sql in queries), (
        f"{method_name} SQLite path no longer exercises SUBSTR(:\n{queries}"
    )