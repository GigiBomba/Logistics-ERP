"""Backfill existing trip client_names into a new clients table.

Usage:
    py scripts/backfill_clients.py --dry-run     # preview
    py scripts/backfill_clients.py --migrate      # apply
    py scripts/backfill_clients.py --validate     # verify
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DB_PATH = "data/cashflow.db"
BACKUP_DIR = os.path.join("data", "backups")


def _backup_db():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"cashflow_backup_PRE_CLIENTS_{ts}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def _migrate(conn, dry_run=False):
    # Get distinct client_names from trips
    names = set()
    rows = conn.execute(
        "SELECT DISTINCT client_name FROM trips WHERE client_name IS NOT NULL AND client_name != ''"
    ).fetchall()
    for (name,) in rows:
        names.add(name.strip())

    if dry_run:
        print(f"  Would create {len(names)} client(s):")
        for n in sorted(names):
            print(f"    - '{n}'")
        print(f"  Would update trips to link client_id")
        return len(names)

    created = 0
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    for name in sorted(names):
        existing = conn.execute(
            "SELECT id FROM clients WHERE name = ?", (name,)
        ).fetchone()
        if existing:
            continue
        conn.execute(
            "INSERT INTO clients (name, created_at) VALUES (?, ?)",
            (name, now),
        )
        created += 1

    updated = 0
    for name in sorted(names):
        client_id = conn.execute(
            "SELECT id FROM clients WHERE name = ?", (name,)
        ).fetchone()[0]
        result = conn.execute(
            "UPDATE trips SET client_id = ? WHERE client_name = ? AND client_id IS NULL",
            (client_id, name),
        )
        updated += result.rowcount

    conn.commit()
    print(f"Created {created} client(s), updated {updated} trip(s)")
    return created + updated


def _validate(conn):
    rows = conn.execute(
        "SELECT COUNT(*) FROM trips WHERE client_name IS NOT NULL AND client_name != '' AND client_id IS NULL"
    ).fetchone()[0]
    client_count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    if rows > 0:
        print(f"WARNING: {rows} trips still have no client_id")
    else:
        print(f"OK: All trips with client_name have a client_id")
    print(f"Total clients: {client_count}")
    return rows


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--migrate", action="store_true")
    group.add_argument("--validate", action="store_true")
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
