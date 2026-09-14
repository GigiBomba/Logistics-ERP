#!/usr/bin/env python
"""Validate PostgreSQL migration - compare SQLite and PostgreSQL data.

Row-count comparison always runs; unless ``--skip-extended`` is given the
following extended families are also reported under ``results["checks"]``
(each family appends ``{"check": name, "passed": [...], "failed": [...],
"errors": [...]}``):

* ``null_rates``          - NULL fraction of key columns per critical table
                            (trips.client_name / trips.truck_number /
                            invoices.invoice_number / documents.doc_number)
                            within +/-1% between engines.
* ``fk_orphans``          - trips.driver_id -> drivers, trips.truck_id ->
                            trucks, invoices.trip_id -> trips,
                            alerts.trip_id -> trips; orphan counts are
                            reported (info-level fail with breakdown; the
                            run is never aborted).
* ``monetary_rounding``   - full-table SUM and AVG over NUMERIC money columns
                            (invoices.total_amount, trips.total_price_eur,
                            receipts.total) agree to 2dp within 0.01
                            (rounded before compare; Decimal-safe).  Both
                            engines use the identical metric; a row-count
                            divergence (e.g. an aborted import) is reported as
                            such instead of a numeric mismatch.
* ``timestamp_formats``   - ISO-8601 regex pass-rate on sampled datetime
                            columns (trips.created_at / trips.start_date).
                            Type-aware: PG TIMESTAMPTZ is rendered via
                            ``to_char(col AT TIME ZONE 'UTC', ...)`` while a
                            legacy TEXT column is matched against the raw
                            value.
* ``unique_sampling``     - duplicate counts on invoice_number, doc_number,
                            proforma_number must be zero on both engines.

Usage:
    python scripts/validate_migration.py [--sqlite data/cashflow.db]
        [--pg-dsn postgresql://...] [--skip-extended] [--sample-size 200]
"""
from __future__ import annotations


import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager


# ── Small query helpers ────────────────────────────────────────────────────


def _scalar(db, sql: str, params: tuple = ()) -> dict:
    """Run *sql* and return the first row as a dict ({} when empty)."""
    rows = db.rows_to_dicts(db.execute(sql, params).fetchall())
    return rows[0] if rows else {}


def _round2(value):
    """Round a numeric value to 2dp (Decimal-safe); None stays None."""
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _money_close(a, b) -> bool:
    """Two rounded money values agree within 0.01 (None-safe)."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= Decimal("0.01")


_ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


def _pg_column_types(pg, spec) -> dict:
    """Return ``{(table, column): data_type}`` for the *spec* columns on PG.

    A single ``information_schema.columns`` lookup covers every sampled
    column.  Data types come back lower-cased; missing columns are simply
    absent from the mapping (the caller reports that as a check error).
    """
    conditions = " OR ".join(
        "(table_name = ? AND column_name = ?)" for _ in spec
    )
    params = tuple(p for table, col in spec for p in (table, col))
    rows = pg.rows_to_dicts(
        pg.execute(
            "SELECT table_name, column_name, data_type "
            f"FROM information_schema.columns WHERE {conditions}",
            params,
        ).fetchall()
    )
    return {
        (r.get("table_name"), r.get("column_name")): str(
            r.get("data_type") or ""
        ).strip().lower()
        for r in rows
    }


# ── Extended validation families ───────────────────────────────────────────


def _check_null_rates(sqlite, pg) -> dict:
    """NULL fraction of key columns within 1% between engines."""
    check = {"check": "null_rates", "passed": [], "failed": [], "errors": []}
    spec = [
        ("trips", "client_name"),
        ("trips", "truck_number"),
        ("invoices", "invoice_number"),
        ("documents", "doc_number"),
    ]
    for table, col in spec:
        try:
            sql = (
                f'SELECT COUNT(*) AS total, COUNT(*) - COUNT("{col}") AS nulls '
                f'FROM "{table}"'
            )
            s = _scalar(sqlite, sql)
            p = _scalar(pg, sql)
            s_rate = (s["nulls"] / s["total"]) if s.get("total") else 0.0
            p_rate = (p["nulls"] / p["total"]) if p.get("total") else 0.0
            entry = (table, col, round(s_rate, 4), round(p_rate, 4))
            if abs(s_rate - p_rate) <= 0.01:
                check["passed"].append(entry)
            else:
                check["failed"].append(entry)
        except Exception as e:
            check["errors"].append((table, col, str(e)[:100]))
    return check


def _check_fk_orphans(sqlite, pg) -> dict:
    """Count orphaned FK references (info-level; never aborts the run)."""
    check = {"check": "fk_orphans", "passed": [], "failed": [], "errors": []}
    spec = [
        ("trips", "driver_id", "drivers"),
        ("trips", "truck_id", "trucks"),
        ("invoices", "trip_id", "trips"),
        ("alerts", "trip_id", "trips"),
    ]
    for child, fk, parent in spec:
        try:
            sql = (
                f'SELECT COUNT(*) AS cnt FROM "{child}" c '
                f'LEFT JOIN "{parent}" p ON c."{fk}" = p."id" '
                f'WHERE c."{fk}" IS NOT NULL AND p."id" IS NULL'
            )
            s_cnt = _scalar(sqlite, sql).get("cnt") or 0
            p_cnt = _scalar(pg, sql).get("cnt") or 0
            entry = (child, fk, parent, s_cnt, p_cnt)
            if s_cnt == 0 and p_cnt == 0:
                check["passed"].append(entry)
            else:
                check["failed"].append(entry)
        except Exception as e:
            check["errors"].append((child, fk, parent, str(e)[:100]))
    return check


def _check_monetary_rounding(sqlite, pg) -> dict:
    """Full-table SUM and AVG over money columns agree to 2dp within 0.01.

    The comparison is metric-explicit and identical on both engines: the same
    ``SUM(col)`` and ``AVG(col)`` are computed over the whole table.  A row
    count (``COUNT(*)``) is fetched in the same query; when the engines
    disagree on row count (e.g. an import error aborted a table, or duplicate
    keys were dropped) the divergence is reported with the missing-row count
    instead of a misleading SUM/AVG numeric mismatch.
    """
    check = {"check": "monetary_rounding", "passed": [], "failed": [], "errors": []}
    spec = [
        ("invoices", "total_amount"),
        ("trips", "total_price_eur"),
        ("receipts", "total"),
    ]
    for table, col in spec:
        try:
            sql = (
                f'SELECT SUM("{col}") AS s, AVG("{col}") AS a, '
                f'COUNT(*) AS n, COUNT("{col}") AS c FROM "{table}"'
            )
            s = _scalar(sqlite, sql)
            p = _scalar(pg, sql)
            s_n, p_n = s.get("n"), p.get("n")
            if s_n != p_n:
                if s_n is None or p_n is None:
                    detail = f"row counts unknown (SQLite={s_n}, PG={p_n})"
                else:
                    detail = (
                        f"row-count divergence: SQLite={s_n}, PG={p_n}, "
                        f"missing={p_n - s_n}"
                    )
                check["failed"].append((table, col, detail, s_n, p_n))
                continue
            s_sum, s_avg = _round2(s.get("s")), _round2(s.get("a"))
            p_sum, p_avg = _round2(p.get("s")), _round2(p.get("a"))
            entry = (table, col, s_sum, s_avg, p_sum, p_avg)
            if _money_close(s_sum, p_sum) and _money_close(s_avg, p_avg):
                check["passed"].append(entry)
            else:
                check["failed"].append(entry)
        except Exception as e:
            check["errors"].append((table, col, str(e)[:100]))
    return check


def _check_timestamp_formats(sqlite, pg, sample_size: int = 200) -> dict:
    """ISO-8601 pass-rate on sampled datetime columns per engine.

    Type-aware: the PG column's ``information_schema.columns.data_type`` is
    looked up first.  A real timestamp column is rendered through
    ``to_char(col AT TIME ZONE 'UTC', ...)``; a legacy TEXT column (the
    export/import path writes datetimes as TEXT, only the native alembic path
    converts to TIMESTAMPTZ) is compared as-is with the ISO-8601 regex — the
    ``AT TIME ZONE`` render raises ``function pg_catalog.timezone(unknown,
    text) does not exist`` on TEXT.  Type-lookup failures are reported as
    check errors instead of aborting the run.
    """
    check = {"check": "timestamp_formats", "passed": [], "failed": [], "errors": []}
    spec = [
        ("trips", "created_at"),
        ("trips", "start_date"),
    ]
    try:
        pg_types = _pg_column_types(pg, spec)
    except Exception as e:
        for table, col in spec:
            check["errors"].append((table, col, f"PG type lookup failed: {str(e)[:80]}"))
        return check

    for table, col in spec:
        try:
            pg_type = pg_types.get((table, col), "")
            if not pg_type:
                check["errors"].append(
                    (table, col, "PG data_type lookup returned no result")
                )
                continue
            s_sql = (
                f'SELECT "{col}" AS v FROM "{table}" '
                f'WHERE "{col}" IS NOT NULL AND "{col}" != \'\' LIMIT ?'
            )
            if "timestamp" in pg_type:
                p_sql = (
                    f"SELECT to_char(\"{col}\" AT TIME ZONE 'UTC', "
                    f"'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') AS v "
                    f'FROM "{table}" WHERE "{col}" IS NOT NULL LIMIT ?'
                )
            else:
                # TEXT/date columns have no timezone to render: apply the
                # ISO-8601 regex to the raw stored value directly.
                p_sql = (
                    f'SELECT "{col}" AS v FROM "{table}" '
                    f'WHERE "{col}" IS NOT NULL AND "{col}" != \'\' LIMIT ?'
                )
            s_rows = sqlite.rows_to_dicts(
                sqlite.execute(s_sql, (sample_size,)).fetchall()
            )
            p_rows = pg.rows_to_dicts(pg.execute(p_sql, (sample_size,)).fetchall())
            s_vals = [r.get("v") for r in s_rows if r.get("v")]
            p_vals = [r.get("v") for r in p_rows if r.get("v")]
            s_rate = (
                sum(1 for v in s_vals if _ISO8601_RE.fullmatch(str(v))) / len(s_vals)
                if s_vals else 1.0
            )
            p_rate = (
                sum(1 for v in p_vals if _ISO8601_RE.fullmatch(str(v))) / len(p_vals)
                if p_vals else 1.0
            )
            entry = (
                table, col, len(s_vals), round(s_rate, 4),
                len(p_vals), round(p_rate, 4),
            )
            if abs(s_rate - p_rate) <= 0.01:
                check["passed"].append(entry)
            else:
                check["failed"].append(entry)
        except Exception as e:
            check["errors"].append((table, col, str(e)[:100]))
    return check


def _check_unique_sampling(sqlite, pg) -> dict:
    """Duplicate counts on key unique columns must be zero on both engines."""
    check = {"check": "unique_sampling", "passed": [], "failed": [], "errors": []}
    spec = [
        ("invoices", "invoice_number"),
        ("documents", "doc_number"),
        ("proforma_invoices", "proforma_number"),
    ]
    for table, col in spec:
        try:
            sql = (
                f'SELECT COUNT("{col}") AS nonnull, COUNT(DISTINCT "{col}") AS distincts '
                f'FROM "{table}"'
            )
            s = _scalar(sqlite, sql)
            p = _scalar(pg, sql)
            s_dups = (s.get("nonnull") or 0) - (s.get("distincts") or 0)
            p_dups = (p.get("nonnull") or 0) - (p.get("distincts") or 0)
            entry = (table, col, s_dups, p_dups)
            if s_dups == 0 and p_dups == 0:
                check["passed"].append(entry)
            else:
                check["failed"].append(entry)
        except Exception as e:
            check["errors"].append((table, col, str(e)[:100]))
    return check


def validate(
    sqlite_path: str,
    pg_dsn: str,
    skip_extended: bool = False,
    sample_size: int = 200,
) -> dict:
    """Compare SQLite and PostgreSQL databases.

    Row counts are always compared.  Unless ``skip_extended`` is True the
    five extended families (null rates, FK orphans, monetary rounding,
    timestamp formats, unique sampling) are also run and stored in
    ``results["checks"]`` — each family appends ``{"check": name,
    "passed": [...], "failed": [...], "errors": [...]}``.  The top-level
    ``passed`` / ``failed`` / ``errors`` keys stay row-count-only for
    backward compatibility.
    """
    sqlite = DatabaseManager(sqlite_path, engine="sqlite")
    pg = DatabaseManager(pg_dsn, engine="postgresql")

    results = {"passed": [], "failed": [], "errors": [], "checks": []}

    try:
        # Get all table names from SQLite
        tables = [
            r["name"] for r in sqlite.rows_to_dicts(
                sqlite.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            )
        ]

        for table in tables:
            try:
                sqlite_count = sqlite.rows_to_dicts(
                    sqlite.conn.execute(f'SELECT COUNT(*) AS cnt FROM "{table}"').fetchall()
                )[0]["cnt"]

                pg_count = pg.rows_to_dicts(
                    pg.execute(f'SELECT COUNT(*) AS cnt FROM "{table}"').fetchall()
                )[0]["cnt"]

                if sqlite_count == pg_count:
                    results["passed"].append((table, sqlite_count))
                else:
                    results["failed"].append(
                        (table, sqlite_count, pg_count, pg_count - sqlite_count)
                    )
            except Exception as e:
                results["errors"].append((table, str(e)[:100]))

        if not skip_extended:
            results["checks"] = [
                _check_null_rates(sqlite, pg),
                _check_fk_orphans(sqlite, pg),
                _check_monetary_rounding(sqlite, pg),
                _check_timestamp_formats(sqlite, pg, sample_size),
                _check_unique_sampling(sqlite, pg),
            ]

        # Print report
        print(f"\n{'='*60}")
        print(f"Migration Validation Report")
        print(f"{'='*60}")

        if results["passed"]:
            print(f"\n[OK] PASSED ({len(results['passed'])} tables):")
            for table, count in results["passed"]:
                print(f"  {table:<35} {count:>8,} rows")

        if results["failed"]:
            print(f"\n[FAIL] FAILED ({len(results['failed'])} tables):")
            for table, sql, pg_cnt, diff in results["failed"]:
                print(f"  {table:<35} SQLite={sql:>8,}  PG={pg_cnt:>8,}  diff={diff:+}")

        if results["errors"]:
            print(f"\n[ERR] ERROR ({len(results['errors'])} tables):")
            for table, err in results["errors"]:
                print(f"  {table:<35} {err}")

        if results["checks"]:
            print(f"\n{'='*60}")
            print(f"Extended Validation Checks")
            print(f"{'='*60}")
            for check in results["checks"]:
                status = (
                    "OK" if not check["failed"] and not check["errors"] else "FAIL"
                )
                print(
                    f"\n[{status}] {check['check']}: "
                    f"{len(check['passed'])} passed, "
                    f"{len(check['failed'])} failed, "
                    f"{len(check['errors'])} errors"
                )
                for item in check["passed"]:
                    print(f"  [OK]   {item}")
                for item in check["failed"]:
                    print(f"  [FAIL] {item}")
                for item in check["errors"]:
                    print(f"  [ERR]  {item}")

        total_passed = len(results["passed"])
        total = total_passed + len(results["failed"]) + len(results["errors"])
        print(f"\nSummary: {total_passed}/{total} tables match")

    finally:
        sqlite.close()
        pg.close()

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate SQLite -> PostgreSQL migration")
    parser.add_argument("--sqlite", default="data/cashflow.db", help="SQLite DB path")
    parser.add_argument("--pg-dsn", default=os.environ.get(
        "OPERION_POSTGRES_DSN", "postgresql://operion:operion@localhost:5432/operion"
    ), help="PostgreSQL DSN")
    parser.add_argument(
        "--skip-extended",
        action="store_true",
        help="Skip the extended validation checks (null rates, FK orphans, "
             "monetary rounding, timestamp formats, unique sampling)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=200,
        help="Rows sampled per column in the timestamp-format check "
             "(default: 200)",
    )
    args = parser.parse_args()

    validate(
        args.sqlite,
        args.pg_dsn,
        skip_extended=args.skip_extended,
        sample_size=args.sample_size,
    )
