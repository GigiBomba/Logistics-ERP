"""Backfill NULL ``updated_at`` rows on every syncable table.

Phase E / R3 rollout step: the delta since-filter always re-includes NULL
``updated_at`` rows (``updated_at IS NULL`` safety net) because a row that is
never written is never stamped.  After this backfill, those rows have a real
watermark and the delta stops re-fetching them every cycle.

For each syncable table:

    UPDATE <table>
    SET updated_at = COALESCE(updated_at, created_at, '1970-01-01T00:00:00Z')
    WHERE updated_at IS NULL

* ``created_at`` is preferred when present (the row's real birth time); rows
  without a ``created_at`` column (e.g. ``client_tags``) or with both NULL
  fall back to the epoch so they stay well below any real cursor.
* The ``updated_at`` stamping trigger (BEFORE UPDATE, both engines) would
  overwrite the COALESCE value with ``now()`` — it is suppressed around the
  UPDATE: the ``sync_in_progress`` flag on SQLite, ``ALTER TABLE ... DISABLE
  TRIGGER ALL`` on PostgreSQL (re-enabled in a finally).
* Idempotent — safe to run repeatedly.
* Engine-aware: ``?``/``%s`` placeholders and both the desktop SQLite DB and
  the server PostgreSQL DB are supported (``--dsn`` for PG).

Run on the SERVER DB (PG) after deploying the Phase E endpoint, and optionally
on each desktop DB during the next app upgrade:

    python scripts/backfill_updated_at.py                     # data/*.db (SQLite)
    python scripts/backfill_updated_at.py --db data/app.db
    python scripts/backfill_updated_at.py --dsn postgres://... --engine postgresql
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import schema as _schema  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("backfill_updated_at")

EPOCH = "1970-01-01T00:00:00Z"


def _table_columns(db, table: str, pg: bool) -> set:
    """Return the lowercase column-name set of a syncable table."""
    if pg:
        # ``db.execute`` adapts ? -> %s and returns a RealDictCursor for PG.
        cur = db.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = %s",
            (table,),
        )
        return {row["column_name"] for row in cur.fetchall()}
    cols = db.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in cols}


def _suppress_stamp_trigger(db, table: str, pg: bool) -> None:
    """Stop the updated_at stamping trigger from firing during the UPDATE.

    SQLite: the stamping triggers consult the ``sync_in_progress`` sync_meta
    flag (database/schema.py) — set it.
    PostgreSQL: the ``stamp_updated_at()`` triggers are plain user triggers
    (CREATE TRIGGER ... BEFORE UPDATE); ``ALTER TABLE ... DISABLE TRIGGER ALL``
    silences them.  ``sync_meta`` does NOT exist in schema_pg.sql, so there is
    no flag to set there.  The DISABLE is transactional: if the UPDATE below
    fails and the transaction rolls back, the DISABLE rolls back with it.
    """
    if pg:
        db.execute(f'ALTER TABLE "{table}" DISABLE TRIGGER ALL')
    else:
        db.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value) "
            "VALUES ('sync_in_progress', '1')"
        )


def _restore_stamp_trigger(db, table: str, pg: bool) -> None:
    """Re-enable the stamping trigger (always, even after a failed UPDATE)."""
    if pg:
        db.execute(f'ALTER TABLE "{table}" ENABLE TRIGGER ALL')
    else:
        db.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value) "
            "VALUES ('sync_in_progress', '0')"
        )


def backfill(db, engine: str = "sqlite") -> int:
    """Stamp NULL updated_at on every syncable table.  Returns rows updated."""
    pg = engine == "postgresql"
    total = 0
    for table in _schema.SYNCABLE_TABLES:
        try:
            columns = _table_columns(db, table, pg)
            if "updated_at" not in columns:
                continue
            # Build the COALESCE per table: only reference created_at when the
            # column actually exists (client_tags has none) — otherwise the
            # UPDATE would fail with "no such column" and be skipped.
            if pg:
                # PG columns are a mix of TIMESTAMPTZ (updated_at on most
                # syncable tables) and TEXT (created_at on many legacy ones).
                # COALESCE refuses to unify timestamptz + text, so cast every
                # branch to timestamptz.  A cast of an already-timestamptz
                # column is a no-op; ISO-8601 TEXT values parse cleanly.
                if "created_at" in columns:
                    coalesce = (
                        "COALESCE(updated_at::timestamptz, "
                        "created_at::timestamptz, %s::timestamptz)"
                    )
                else:
                    coalesce = "COALESCE(updated_at::timestamptz, %s::timestamptz)"
            else:
                if "created_at" in columns:
                    coalesce = "COALESCE(updated_at, created_at, ?)"
                else:
                    coalesce = "COALESCE(updated_at, ?)"
            _suppress_stamp_trigger(db, table, pg)
            try:
                cur = db.execute(
                    f"UPDATE {table} SET updated_at = {coalesce} "
                    f"WHERE updated_at IS NULL",
                    (EPOCH,),
                )
                db.conn.commit()
                n = cur.rowcount if cur.rowcount is not None else 0
                if n:
                    logger.info("  %-28s %d row(s) stamped", table, n)
                total += n
            finally:
                # Re-enable triggers even on failure.  If the UPDATE errored,
                # the implicit PG transaction is aborted — roll back first so
                # the ENABLE (and the next table) can run on this connection.
                try:
                    db.conn.rollback()
                except Exception:
                    pass
                _restore_stamp_trigger(db, table, pg)
                db.conn.commit()
        except Exception as exc:
            logger.warning("  %-28s skipped (%s)", table, str(exc)[:100])
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None, help="SQLite DB path (default: data/app.db, data/staging.db)")
    parser.add_argument("--dsn", default=None, help="PostgreSQL DSN (engine=postgresql)")
    parser.add_argument("--engine", default="sqlite", choices=["sqlite", "postgresql"])
    args = parser.parse_args()

    if args.engine == "postgresql":
        from database.db_manager import DatabaseManager

        if not args.dsn:
            parser.error("--dsn is required when --engine postgresql")
        db = DatabaseManager(args.dsn, engine="postgresql")
        total = backfill(db, engine="postgresql")
        db.close()
        logger.info("Done — %d NULL updated_at row(s) stamped (PG).", total)
        return

    paths = [args.db] if args.db else [os.path.join("data", "app.db")]
    grand_total = 0
    for db_path in paths:
        if not os.path.isfile(db_path):
            logger.warning("DB not found: %s (skipping)", db_path)
            continue
        from database.db_manager import DatabaseManager

        db = DatabaseManager(db_path)
        total = backfill(db, engine="sqlite")
        db.close()
        logger.info("  %s: %d NULL updated_at row(s) stamped.", db_path, total)
        grand_total += total
    logger.info("Done — %d NULL updated_at row(s) stamped (SQLite).", grand_total)


if __name__ == "__main__":
    main()
