#!/usr/bin/env python
"""Import JSON dump into PostgreSQL.

Usage:
    python scripts/import_to_pg.py --input dump_postgres.json [--dsn postgresql://...]

Requires the JSON dump produced by scripts/export_to_pg.py.
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager


def import_from_json(input_path: str, dsn: str) -> dict:
    """Import all tables from a JSON dump into PostgreSQL."""
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Dump file not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        dump = json.load(f)

    tables = dump.get("tables", {})
    if not tables:
        raise ValueError("No tables found in dump file")

    db = DatabaseManager(dsn, engine="postgresql", pool_min=2, pool_max=10)
    stats = {"total_tables": len(tables), "total_rows": 0, "errors": 0, "skipped": []}

    # Disable FK checks during import for speed
    try:
        db.execute("SET session_replication_role = 'replica'")
    except Exception:
        pass

    # Imports with no FK dependencies first, then the rest
    ordered_tables = _topological_sort(tables)

    for table in ordered_tables:
        rows = tables.get(table, [])
        if not rows:
            stats["skipped"].append(table)
            print(f"  {table}: empty, skipped")
            continue

        try:
            # Get column names from first row
            columns = list(rows[0].keys())
            col_list = ", ".join(f'"{c}"' for c in columns)
            placeholders = ", ".join("%s" for _ in columns)

            # Batch insert in chunks of 500
            chunk = 0
            for i in range(0, len(rows), 500):
                batch = rows[i:i + 500]
                values = []
                params = []
                for row in batch:
                    values.append(f"({placeholders})")
                    params.extend(row.get(c) for c in columns)

                db.execute(
                    f"INSERT INTO \"{table}\" ({col_list}) VALUES {', '.join(values)} ON CONFLICT DO NOTHING",
                    tuple(params),
                )
                chunk += 1

            db.commit()
            stats["total_rows"] += len(rows)
            print(f"  {table}: {len(rows)} rows imported")
        except Exception as e:
            stats["errors"] += 1
            db.rollback()
            print(f"  {table}: ERROR — {e}")

    # Re-enable FK checks
    try:
        db.execute("SET session_replication_role = 'origin'")
    except Exception:
        pass

    # Reset sequences to max id
    for table in ordered_tables:
        if "id" in tables.get(table, [{}])[0]:
            try:
                db.execute(
                    f"SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM \"{table}\"), 1))",
                    (table,),
                )
            except Exception:
                pass

    db.close()
    return stats


def _topological_sort(tables: dict) -> list:
    """Order tables so FK dependencies come first."""
    # Known FK dependency order
    priority = [
        "companies", "users", "drivers", "trucks", "clients",
        "client_contacts", "client_tags", "routes", "route_history_v2",
        "trips", "invoices", "proforma_invoices", "receipts",
        "documents", "document_links", "document_versions", "contracts",
        "maintenance_records", "maintenance_schedules",
        "driver_truck_assignments", "truck_route_assignments",
        "successive_carriers", "cmr_counter", "cmr_audit_log",
        "tacho_imports", "tacho_driver_activity", "tacho_vehicle_data",
        "alerts", "operation_events", "trip_status_history",
        "document_pipeline_runs", "document_package", "document_package_items",
        "automail_templates", "automail_schedules", "automail_client_overrides",
        "email_logs", "invoice_reminders",
        "api_keys", "oauth2_clients", "webhook_events", "waitlist_entries",
        "gps_telemetry", "settings", "schema_migrations",
    ]
    result = []
    for t in priority:
        if t in tables:
            result.append(t)
    # Append any tables not in the priority list
    for t in tables:
        if t not in result:
            result.append(t)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import JSON dump into PostgreSQL")
    parser.add_argument("--input", default="dump_postgres.json", help="JSON dump file")
    parser.add_argument("--dsn", default=os.environ.get(
        "OPERION_POSTGRES_DSN", "postgresql://operion:operion@localhost:5432/operion"
    ), help="PostgreSQL DSN")
    args = parser.parse_args()

    print(f"Importing {args.input} → PostgreSQL")
    print(f"Started: {datetime.now().isoformat()}")
    stats = import_from_json(args.input, args.dsn)
    print(f"\nDone: {stats['total_rows']} rows in {stats['total_tables']} tables "
          f"({stats['errors']} errors, {len(stats['skipped'])} skipped)")
