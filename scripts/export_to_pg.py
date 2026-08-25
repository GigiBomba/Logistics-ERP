#!/usr/bin/env python
"""Export SQLite database to JSON for PostgreSQL import.

Usage:
    python scripts/export_to_pg.py [--output dump.json] [--db-path data/cashflow.db]
"""
from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager


def json_default(o):
    """JSON-serialize non-primitive values.

    BLOB bytes (e.g. route_history_v2.geometry_compressed) must survive the
    JSON round-trip into a PG bytea column: encode as base64 (import_to_pg
    decodes them back into bytes for bytea columns).
    """
    if isinstance(o, (bytes, bytearray)):
        return {"__b64__": base64.b64encode(bytes(o)).decode("ascii")}
    return str(o)


def export_to_json(db_path: str, output_path: str):
    """Export all tables from SQLite to a JSON file."""
    db = DatabaseManager(db_path, engine="sqlite")
    try:
        dump = {"exported_at": datetime.now().isoformat(), "tables": {}}
        # Get all table names
        tables = [r["name"] for r in db.rows_to_dicts(
            db.conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        )]
        for table in tables:
            try:
                rows = db.rows_to_dicts(
                    db.conn.execute(f"SELECT * FROM \"{table}\"").fetchall()
                )
                dump["tables"][table] = rows
                print(f"  {table}: {len(rows)} rows")
            except Exception as e:
                print(f"  {table}: SKIPPED ({e})")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dump, f, default=json_default, indent=2)
        print(f"\nExported {len(dump['tables'])} tables to {output_path}")
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export SQLite to JSON for PostgreSQL import")
    parser.add_argument("--output", default="dump_postgres.json", help="Output JSON file")
    parser.add_argument("--db-path", default="data/cashflow.db", help="SQLite database path")
    args = parser.parse_args()
    export_to_json(args.db_path, args.output)
