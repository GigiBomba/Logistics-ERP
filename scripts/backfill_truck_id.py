"""Backfill trips.truck_id from trucks.plate_number via trips.truck_number.

Usage:
    py scripts/backfill_truck_id.py --dry-run     # preview
    py scripts/backfill_truck_id.py --migrate      # apply
    py scripts/backfill_truck_id.py --validate     # verify
"""
from __future__ import annotations


import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DB_PATH = "data/cashflow.db"
BACKUP_DIR = os.path.join("data", "backups")


def _backup_db() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"cashflow_backup_PRE_TRUCK_ID_{ts}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def _ensure_column(conn: sqlite3.Connection) -> None:
    """Add truck_id column if it does not exist."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(trips)").fetchall()]
    if "truck_id" not in cols:
        conn.execute("ALTER TABLE trips ADD COLUMN truck_id INTEGER REFERENCES trucks(id)")
        conn.commit()
        print("Added truck_id column to trips table.")


def _migrate(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """Populate trips.truck_id from trucks.plate_number matching trips.truck_number."""
    _ensure_column(conn)

    # Count eligible trips
    total = conn.execute(
        "SELECT COUNT(*) FROM trips WHERE truck_number IS NOT NULL AND truck_number != ''"
    ).fetchone()[0]

    # Find trips with NULL truck_id that have a truck_number
    null_count = conn.execute(
        "SELECT COUNT(*) FROM trips "
        "WHERE truck_id IS NULL AND truck_number IS NOT NULL AND truck_number != ''"
    ).fetchone()[0]

    # Find unmatched plate numbers
    unmatched = conn.execute(
        "SELECT DISTINCT tr.truck_number FROM trips tr "
        "WHERE tr.truck_number IS NOT NULL AND tr.truck_number != '' "
        "  AND NOT EXISTS (SELECT 1 FROM trucks t WHERE t.plate_number = tr.truck_number)"
    ).fetchall()
    unmatched_plates = [r[0] for r in unmatched]

    if dry_run:
        print(f"  Total trips with truck_number: {total}")
        print(f"  Trips needing backfill (truck_id IS NULL): {null_count}")
        print(f"  Would match via plate_number: {null_count - len(unmatched_plates)}"
              if unmatched_plates
              else f"  All {null_count} trips would be matched.")
        if unmatched_plates:
            print(f"  Unmatched plates ({len(unmatched_plates)}):")
            for p in unmatched_plates:
                print(f"    - '{p}'")
        return {
            "total_with_plate": total,
            "null_truck_id": null_count,
            "matched": null_count - len(unmatched_plates),
            "unmatched": len(unmatched_plates),
            "unmatched_plates": unmatched_plates,
        }

    updated = 0
    orphaned = 0

    # Backfill: match by plate_number
    result = conn.execute(
        "UPDATE trips SET truck_id = ("
        "  SELECT t.id FROM trucks t WHERE t.plate_number = trips.truck_number"
        ") WHERE truck_id IS NULL AND truck_number IS NOT NULL AND truck_number != ''"
    )
    updated = result.rowcount

    # Validate remaining orphans
    orphaned = conn.execute(
        "SELECT COUNT(*) FROM trips "
        "WHERE truck_id IS NULL AND truck_number IS NOT NULL AND truck_number != ''"
    ).fetchone()[0]

    conn.commit()
    print(f"Backfilled {updated} trip(s) with truck_id")
    if orphaned:
        print(f"WARNING: {orphaned} trip(s) still have no truck_id (unmatched plates)")
        remaining = conn.execute(
            "SELECT DISTINCT truck_number FROM trips "
            "WHERE truck_id IS NULL AND truck_number IS NOT NULL AND truck_number != ''"
        ).fetchall()
        for (plate,) in remaining:
            print(f"  - '{plate}' (no matching truck in trucks table)")

    return {
        "total_with_plate": total,
        "null_truck_id": null_count,
        "updated": updated,
        "orphaned": orphaned,
    }


def _validate(conn: sqlite3.Connection) -> int:
    """Verify backfill integrity."""
    issues = 0

    # Check for trips with truck_number but no truck_id
    orphans = conn.execute(
        "SELECT COUNT(*) FROM trips "
        "WHERE truck_id IS NULL AND truck_number IS NOT NULL AND truck_number != ''"
    ).fetchone()[0]
    if orphans > 0:
        print(f"WARNING: {orphans} trip(s) have truck_number but no truck_id (orphan references)")
        details = conn.execute(
            "SELECT id, truck_number FROM trips "
            "WHERE truck_id IS NULL AND truck_number IS NOT NULL AND truck_number != ''"
        ).fetchall()
        for tid, plate in details:
            print(f"  Trip #{tid}: truck_number='{plate}'")
        issues += orphans
    else:
        print("OK: All trips with truck_number have a truck_id")

    # Check for trips with truck_id but no matching truck (dangling FK)
    dangling = conn.execute(
        "SELECT COUNT(*) FROM trips "
        "WHERE truck_id IS NOT NULL "
        "  AND NOT EXISTS (SELECT 1 FROM trucks WHERE id = trips.truck_id)"
    ).fetchone()[0]
    if dangling > 0:
        print(f"WARNING: {dangling} trip(s) have truck_id that does not match any truck")
        details = conn.execute(
            "SELECT id, truck_id, truck_number FROM trips "
            "WHERE truck_id IS NOT NULL "
            "  AND NOT EXISTS (SELECT 1 FROM trucks WHERE id = trips.truck_id)"
        ).fetchall()
        for tid, trk_id, plate in details:
            print(f"  Trip #{tid}: truck_id={trk_id}, truck_number='{plate}'")
        issues += dangling
    else:
        print("OK: No dangling truck_id references")

    # Summary stats
    total_trips = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    with_truck = conn.execute("SELECT COUNT(*) FROM trips WHERE truck_id IS NOT NULL").fetchone()[0]
    total_trucks = conn.execute("SELECT COUNT(*) FROM trucks").fetchone()[0]
    print(f"Trips total: {total_trips}, with truck_id: {with_truck}, trucks total: {total_trucks}")

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill trips.truck_id from plate_number")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview without changes")
    group.add_argument("--migrate", action="store_true", help="Execute backfill")
    group.add_argument("--validate", action="store_true", help="Verify integrity")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    if args.dry_run:
        conn = sqlite3.connect(DB_PATH)
        _migrate(conn, dry_run=True)
        conn.close()
    elif args.migrate:
        _backup_db()
        conn = sqlite3.connect(DB_PATH)
        _migrate(conn)
        conn.close()
    elif args.validate:
        conn = sqlite3.connect(DB_PATH)
        issues = _validate(conn)
        conn.close()
        sys.exit(0 if issues == 0 else 1)


if __name__ == "__main__":
    main()
