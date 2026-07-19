#!/usr/bin/env python
"""Validate PostgreSQL migration — compare row counts between SQLite and PostgreSQL.

Usage:
    python scripts/validate_migration.py [--sqlite data/cashflow.db] [--pg-dsn postgresql://...]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager


def validate(sqlite_path: str, pg_dsn: str) -> dict:
    """Compare row counts between SQLite and PostgreSQL databases."""
    sqlite = DatabaseManager(sqlite_path, engine="sqlite")
    pg = DatabaseManager(pg_dsn, engine="postgresql")

    results = {"passed": [], "failed": [], "errors": []}

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

        # Print report
        print(f"\n{'='*60}")
        print(f"Migration Validation Report")
        print(f"{'='*60}")

        if results["passed"]:
            print(f"\n✅ PASSED ({len(results['passed'])} tables):")
            for table, count in results["passed"]:
                print(f"  {table:<35} {count:>8,} rows")

        if results["failed"]:
            print(f"\n❌ FAILED ({len(results['failed'])} tables):")
            for table, sql, pg_cnt, diff in results["failed"]:
                print(f"  {table:<35} SQLite={sql:>8,}  PG={pg_cnt:>8,}  diff={diff:+}")

        if results["errors"]:
            print(f"\n⚠ ERROR ({len(results['errors'])} tables):")
            for table, err in results["errors"]:
                print(f"  {table:<35} {err}")

        total_passed = len(results["passed"])
        total = total_passed + len(results["failed"]) + len(results["errors"])
        print(f"\nSummary: {total_passed}/{total} tables match")

    finally:
        sqlite.close()
        pg.close()

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate SQLite → PostgreSQL migration")
    parser.add_argument("--sqlite", default="data/cashflow.db", help="SQLite DB path")
    parser.add_argument("--pg-dsn", default=os.environ.get(
        "OPERION_POSTGRES_DSN", "postgresql://operion:operion@localhost:5432/operion"
    ), help="PostgreSQL DSN")
    args = parser.parse_args()

    validate(args.sqlite, args.pg_dsn)
