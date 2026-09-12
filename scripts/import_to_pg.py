#!/usr/bin/env python
"""Import JSON dump into PostgreSQL.

Usage:
    python scripts/import_to_pg.py --input dump_postgres.json [--dsn postgresql://...]

Requires the JSON dump produced by scripts/export_to_pg.py.
"""
from __future__ import annotations


import base64
import json
import os
import re
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager

# SQLite-internal tables that must never be imported (no PG counterpart).
# The export walks ``sqlite_master`` and picks up sqlite_sequence / FTS
# shadow tables alongside real tables.
SQLITE_INTERNAL_TABLES = ("sqlite_", "documents_fts", "documents_fts_")

#: Trips -> drivers/trucks FK constraints declared NOT VALID in schema_pg.sql
#: (Phase D of Database_Rework P0.8).  Legacy SQLite dumps may carry trips
#: whose driver/truck rows were deleted later; the importer NULLs those orphan
#: ids, then VALIDATES the constraints so they become fully enforced.
TRIPS_FK_SANITIZE = (
    ("driver_id", "drivers", "fk_trips_driver"),
    ("truck_id", "trucks", "fk_trips_truck"),
)

_TEMPORAL_TYPES = {
    "timestamp with time zone",
    "timestamp without time zone",
    "date",
    "time with time zone",
    "time without time zone",
}

_DD_MM_YYYY = re.compile(
    r"^(\d{2})/(\d{2})/(\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$"
)


def _coerce(value, data_type: str):
    """Adapt a SQLite value to a PG column's declared type.

    - temporal columns: ``''`` → None; ``dd/mm/yyyy[ HH:MM[:SS]]`` → ISO
      (SQLite rows carry Romanian-format dates that PG rejects)
    - bytea columns: ``{"__b64__": ...}`` (export marker) → decoded bytes
    - uuid columns: values that are not valid UUIDs → None (nullable only;
      NOT NULL uuid columns with garbage still fail loudly)
    """
    if value is None:
        return None
    if data_type in _TEMPORAL_TYPES:
        if isinstance(value, str):
            s = value.strip()
            if s == "":
                return None
            m = _DD_MM_YYYY.match(s)
            if m:
                d, mo, y, h, mi, se = m.groups()
                if h:
                    return f"{y}-{mo}-{d} {h}:{mi}:{se or '00'}"
                return f"{y}-{mo}-{d}"
            # Digit-only junk (test/seed garbage like "31231") is not a
            # parseable date — drop it rather than fail the whole table.
            if s.isdigit():
                return None
        return value
    if data_type == "boolean":
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "t", "yes", "y")
        return value
    if data_type == "bytea":
        if isinstance(value, dict) and value.get("__b64__"):
            try:
                return base64.b64decode(value["__b64__"])
            except Exception:
                return value
        return value
    if data_type == "uuid":
        try:
            uuid.UUID(str(value))
            return value
        except (ValueError, AttributeError):
            return None
    return value


def _pg_schema_map(db) -> dict:
    """Return {table: {column: (data_type, is_generated)}} for tables on PG.

    Tables absent from PG (e.g. auth_sessions — documented as not ported)
    are omitted so the import skips them instead of failing.
    Generated columns (e.g. trips.month) cannot be inserted explicitly and
    are excluded from the insert column list.
    """
    rows = db.rows_to_dicts(
        db.execute(
            "SELECT table_name, column_name, data_type, is_generated "
            "FROM information_schema.columns"
        ).fetchall()
    )
    schema: dict = {}
    for r in rows:
        schema.setdefault(r["table_name"], {})[r["column_name"]] = (
            r["data_type"],
            r["is_generated"] == "ALWAYS",
        )
    return schema


def sanitize_trips_orphan_fks(db, stats: dict, trips_columns: dict) -> dict:
    """NULL orphan trips.driver_id/truck_id refs, then VALIDATE the FKs.

    schema_pg.sql adds ``fk_trips_driver`` / ``fk_trips_truck`` as NOT VALID
    (ON DELETE SET NULL) so booting stays safe on legacy rows whose driver or
    truck was deleted.  ``ALTER TABLE trips VALIDATE CONSTRAINT`` would reject
    those orphan rows, so they are NULLed first (orphan counts are logged
    before the cleanup for auditability).  Older PG schemas that never received
    the constraints get a warning and are skipped.

    Logs and mutates ``stats`` (adds ``trips_fk_orphans`` and
    ``trips_fk_validated``); never raises — per-constraint failures are logged
    and counted instead of aborting the import.
    """
    stats.setdefault("trips_fk_orphans", {})
    stats.setdefault("trips_fk_validated", [])
    for column, ref_table, constraint in TRIPS_FK_SANITIZE:
        if column not in trips_columns:
            print(
                f"  trips: {column} column missing in PG schema, "
                f"{constraint} VALIDATE skipped"
            )
            continue
        # Count orphans BEFORE nulling so the operator can audit the cleanup.
        orphan_count = 0
        try:
            cur = db.execute(
                f"SELECT COUNT(*) AS cnt FROM trips t WHERE t.{column} IS NOT NULL "
                f"AND NOT EXISTS (SELECT 1 FROM {ref_table} d "
                f"WHERE d.id = t.{column})"
            )
            # Pool connections use RealDictCursor, so the row is a dict here;
            # tolerate a plain tuple too for non-pool callers.
            row = cur.fetchone()
            orphan_count = row["cnt"] if isinstance(row, dict) else row[0]
        except Exception as e:
            print(f"  trips: {column} orphan count ERROR - {e}")
        stats["trips_fk_orphans"][column] = orphan_count
        if orphan_count:
            print(
                f"  trips: {orphan_count} orphan {column} -> {ref_table}(id), "
                f"NULLing before VALIDATE"
            )
        try:
            db.execute(
                f"UPDATE trips SET {column} = NULL WHERE {column} IS NOT NULL "
                f"AND {column} NOT IN (SELECT id FROM {ref_table})"
            )
        except Exception as e:
            stats["errors"] += 1
            print(f"  trips: {column} sanitize UPDATE ERROR - {e}")
        # Guarded VALIDATE: skip with a warning when the constraint is absent
        # (older PG schemas predating the Phase D ALTERs).
        exists = False
        try:
            cur = db.execute(
                "SELECT 1 FROM information_schema.table_constraints "
                "WHERE table_name = 'trips' AND constraint_name = %s "
                "AND constraint_type = 'FOREIGN KEY'",
                (constraint,),
            )
            exists = cur.fetchone() is not None
        except Exception as e:
            print(f"  trips: {constraint} existence check ERROR - {e}")
        if not exists:
            print(f"  trips: {constraint} not found in PG schema, VALIDATE skipped")
            continue
        try:
            db.execute(f"ALTER TABLE trips VALIDATE CONSTRAINT {constraint}")
            stats["trips_fk_validated"].append(constraint)
            print(f"  trips: VALIDATE CONSTRAINT {constraint} OK")
        except Exception as e:
            stats["errors"] += 1
            print(f"  trips: VALIDATE CONSTRAINT {constraint} ERROR - {e}")
    return stats


def import_from_json(input_path: str, dsn: str, sanitize_fks: bool = True) -> dict:
    """Import all tables from a JSON dump into PostgreSQL.

    ``sanitize_fks`` (default True) enables the post-import trips FK step:
    orphan driver_id/truck_id values (rows referencing deleted drivers/trucks
    in legacy dumps) are NULLed and the NOT VALID constraints from
    schema_pg.sql are validated.  Pass False to skip it.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Dump file not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        dump = json.load(f)

    tables = dump.get("tables", {})
    if not tables:
        raise ValueError("No tables found in dump file")

    db = DatabaseManager(dsn, engine="postgresql", pool_min=2, pool_max=10)
    pg_schema = _pg_schema_map(db)
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
        if table.startswith(SQLITE_INTERNAL_TABLES):
            stats["skipped"].append(table)
            print(f"  {table}: SQLite-internal, skipped")
            continue
        col_types = pg_schema.get(table)
        if col_types is None:
            stats["skipped"].append(table)
            print(f"  {table}: NOT in PG schema, skipped")
            continue

        try:
            # Get column names from first row; exclude PG generated columns
            # (e.g. trips.month — GENERATED ALWAYS) which reject explicit values.
            columns = [c for c in rows[0].keys() if not col_types.get(c, ("", False))[1]]
            if not columns:
                stats["skipped"].append(table)
                print(f"  {table}: only generated columns, skipped")
                continue
            col_list = ", ".join(f'"{c}"' for c in columns)
            placeholders = ", ".join("%s" for _ in columns)

            # schema_pg.sql defines id columns as GENERATED ALWAYS AS IDENTITY,
            # which rejects explicit id values unless OVERRIDING SYSTEM VALUE
            # is used.  Migration must preserve source ids (FK integrity), so
            # override whenever the row set carries an id column.
            overriding = " OVERRIDING SYSTEM VALUE" if "id" in columns else ""

            # Batch insert in chunks of 500
            chunk = 0
            for i in range(0, len(rows), 500):
                batch = rows[i:i + 500]
                values = []
                params = []
                for row in batch:
                    values.append(f"({placeholders})")
                    params.extend(
                        _coerce(row.get(c), col_types.get(c, ("", False))[0])
                        for c in columns
                    )

                db.execute(
                    f"INSERT INTO \"{table}\" ({col_list}){overriding} "
                    f"VALUES {', '.join(values)} ON CONFLICT DO NOTHING",
                    tuple(params),
                )
                chunk += 1

            db.commit()
            stats["total_rows"] += len(rows)
            print(f"  {table}: {len(rows)} rows imported")
        except Exception as e:
            stats["errors"] += 1
            db.rollback()
            print(f"  {table}: ERROR - {e}")

    # Re-enable FK checks
    try:
        db.execute("SET session_replication_role = 'origin'")
    except Exception:
        pass

    # Backfill documents.search_vector: the import ran with
    # session_replication_role = 'replica', which suppressed the
    # documents_search_update trigger — imported rows have an empty vector.
    # Touch one indexed column so the BEFORE UPDATE trigger recomputes it.
    if "documents" in tables and pg_schema.get("documents") is not None:
        try:
            cur = db.execute('UPDATE documents SET title = title')
            db.commit()
            print(f"  documents: search_vector backfilled ({cur.rowcount} rows)")
        except Exception as e:
            print(f"  documents: search_vector backfill ERROR - {e}")

    # Trips -> drivers/trucks FK sanitation (Phase D): schema_pg.sql declares
    # fk_trips_driver / fk_trips_truck NOT VALID (ON DELETE SET NULL), so
    # legacy SQLite dumps whose trips reference deleted drivers/trucks stay
    # boot-safe.  NULL those orphans and VALIDATE the constraints here — this
    # must happen after all tables are imported (FK checks re-enabled above)
    # and before the sequence resets below.
    if sanitize_fks and pg_schema.get("trips") is not None:
        try:
            sanitize_trips_orphan_fks(db, stats, pg_schema["trips"])
            db.commit()
        except Exception as e:
            stats["errors"] += 1
            print(f"  trips: FK sanitize/validate step ERROR - {e}")

    # Reset sequences to max id
    for table in ordered_tables:
        rows = tables.get(table, [])
        if not rows or table.startswith(SQLITE_INTERNAL_TABLES):
            continue
        if pg_schema.get(table) is None:
            continue
        if "id" in rows[0]:
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
    parser.add_argument(
        "--skip-fk-sanitize",
        action="store_true",
        help="Skip trips.driver_id/truck_id orphan cleanup and FK VALIDATE",
    )
    args = parser.parse_args()

    print(f"Importing {args.input} -> PostgreSQL")
    print(f"Started: {datetime.now().isoformat()}")
    stats = import_from_json(args.input, args.dsn, sanitize_fks=not args.skip_fk_sanitize)
    print(f"\nDone: {stats['total_rows']} rows in {stats['total_tables']} tables "
          f"({stats['errors']} errors, {len(stats['skipped'])} skipped)")
