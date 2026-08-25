"""Migrate all DD/MM/YYYY text dates to ISO 8601 (YYYY-MM-DD) format.

Usage:
    py scripts/migrate_dates.py --dry-run      # preview changes
    py scripts/migrate_dates.py --migrate       # apply migration
    py scripts/migrate_dates.py --rollback      # reverse migration
    py scripts/migrate_dates.py --validate      # check all dates are ISO
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


def _ddmmyyyy_to_iso(val):
    """Convert DD/MM/YYYY → YYYY-MM-DD. Returns unchanged if not matching format."""
    if not val or not isinstance(val, str):
        return val
    if val.startswith("20") and len(val) >= 10 and val[4] == "-":  # already ISO
        return val
    parts = val.strip().split("/")
    if len(parts) == 3 and len(parts[2]) >= 4:
        return f"{parts[2][:4]}-{parts[1]}-{parts[0]}"
    return val


def _iso_to_ddmmyyyy(val):
    """Convert YYYY-MM-DD → DD/MM/YYYY."""
    if not val or not isinstance(val, str):
        return val
    if "/" in val:  # already DD/MM/YYYY
        return val
    parts = val.strip().split("-")
    if len(parts) == 3 and len(parts[0]) == 4:
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return val


def _ddmmyyyy_hhmm_to_iso(val):
    """Convert DD/MM/YYYY HH:MM → YYYY-MM-DD HH:MM."""
    if not val or not isinstance(val, str):
        return val
    if val.startswith("20") and len(val) >= 10 and val[4] == "-":
        return val
    if len(val) < 16:
        return _ddmmyyyy_to_iso(val)
    date_part = val[:10]
    time_part = val[11:16] if len(val) > 11 else ""
    date_iso = _ddmmyyyy_to_iso(date_part)
    if time_part:
        return f"{date_iso} {time_part}"
    return date_iso


def _iso_hhmm_to_ddmmyyyy(val):
    """Convert YYYY-MM-DD HH:MM → DD/MM/YYYY HH:MM."""
    if not val or not isinstance(val, str):
        return val
    if "/" in val:
        return val
    if len(val) < 16:
        return _iso_to_ddmmyyyy(val)
    date_part = val[:10]
    time_part = val[11:16] if len(val) > 11 else ""
    date_ddmmyyyy = _iso_to_ddmmyyyy(date_part)
    if time_part:
        return f"{date_ddmmyyyy} {time_part}"
    return date_ddmmyyyy


DATE_ONLY_COLUMNS = [
    ("trips", "start_date", _ddmmyyyy_to_iso),
    ("trips", "end_date", _ddmmyyyy_to_iso),
    ("trips", "payment_date", _ddmmyyyy_to_iso),
    ("invoices", "issue_date", _ddmmyyyy_to_iso),
    ("invoices", "due_date", _ddmmyyyy_to_iso),
    ("maintenance_records", "date", _ddmmyyyy_to_iso),
    ("maintenance_schedules", "fixed_expiry_date", _ddmmyyyy_to_iso),
    ("maintenance_schedules", "last_done_date", _ddmmyyyy_to_iso),
    ("trucks", "insurance_expiry", _ddmmyyyy_to_iso),
    ("trucks", "inspection_expiry", _ddmmyyyy_to_iso),
    ("drivers", "license_expiry", _ddmmyyyy_to_iso),
    ("drivers", "medical_expiry", _ddmmyyyy_to_iso),
    ("drivers", "hire_date", _ddmmyyyy_to_iso),
]

DATETIME_COLUMNS = [
    ("trips", "created_at", _ddmmyyyy_hhmm_to_iso),
]

MIXED_COLUMNS = [
    ("trucks", "tachograph_expiry", _ddmmyyyy_to_iso),
]


def _count_rows(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _backup_db():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"cashflow_backup_PRE_ISO_{ts}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def _migrate(conn, dry_run=False):
    changed = 0
    # Date-only columns
    for table, col, converter in DATE_ONLY_COLUMNS:
        rows = conn.execute(
            f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL AND {col} != ''"
        ).fetchall()
        for row_id, val in rows:
            new_val = converter(val)
            if new_val != val:
                changed += 1
                if not dry_run:
                    conn.execute(
                        f"UPDATE {table} SET {col} = ? WHERE id = ?",
                        (new_val, row_id),
                    )
                if dry_run:
                    print(f"  {table}.{col} id={row_id}: '{val}' -> '{new_val}'")
        if dry_run:
            print(f"  {table}.{col}: {len(rows)} rows scanned, "
                  f"{sum(1 for _,v in rows if converter(v) != v)} would change")

    # DateTime columns
    for table, col, converter in DATETIME_COLUMNS:
        rows = conn.execute(
            f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL AND {col} != ''"
        ).fetchall()
        for row_id, val in rows:
            new_val = converter(val)
            if new_val != val:
                changed += 1
                if not dry_run:
                    conn.execute(
                        f"UPDATE {table} SET {col} = ? WHERE id = ?",
                        (new_val, row_id),
                    )
                if dry_run:
                    print(f"  {table}.{col} id={row_id}: '{val}' -> '{new_val}'")
        if dry_run:
            print(f"  {table}.{col}: {len(rows)} rows scanned")

    # Mixed-format columns (tachograph_expiry — already has some ISO)
    for table, col, converter in MIXED_COLUMNS:
        rows = conn.execute(
            f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL AND {col} != ''"
        ).fetchall()
        for row_id, val in rows:
            if val and val.startswith("20") and len(val) >= 10 and val[4] == "-":
                continue  # already ISO, skip
            new_val = converter(val)
            if new_val != val:
                changed += 1
                if not dry_run:
                    conn.execute(
                        f"UPDATE {table} SET {col} = ? WHERE id = ?",
                        (new_val, row_id),
                    )
                if dry_run:
                    print(f"  {table}.{col} id={row_id}: '{val}' -> '{new_val}'")

    if not dry_run:
        conn.commit()
        print(f"Migration complete. {changed} values updated.")
    return changed


def _rollback(conn, dry_run=False):
    changed = 0
    reverse = {
        _ddmmyyyy_to_iso: _iso_to_ddmmyyyy,
        _ddmmyyyy_hhmm_to_iso: _iso_hhmm_to_ddmmyyyy,
    }
    for table, col, converter in DATE_ONLY_COLUMNS:
        rev = reverse[converter]
        rows = conn.execute(
            f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL AND {col} != ''"
        ).fetchall()
        for row_id, val in rows:
            new_val = rev(val)
            if new_val != val:
                changed += 1
                if not dry_run:
                    conn.execute(
                        f"UPDATE {table} SET {col} = ? WHERE id = ?",
                        (new_val, row_id),
                    )
        if dry_run:
            print(f"  {table}.{col}: {len(rows)} rows scanned")

    for table, col, converter in DATETIME_COLUMNS:
        rev = reverse[converter]
        rows = conn.execute(
            f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL AND {col} != ''"
        ).fetchall()
        for row_id, val in rows:
            new_val = rev(val)
            if new_val != val:
                changed += 1
                if not dry_run:
                    conn.execute(
                        f"UPDATE {table} SET {col} = ? WHERE id = ?",
                        (new_val, row_id),
                    )
        if dry_run:
            print(f"  {table}.{col}: {len(rows)} rows scanned")

    if not dry_run:
        conn.commit()
        print(f"Rollback complete. {changed} values restored.")
    return changed


def _validate(conn):
    all_columns = (
        [(t, c) for t, c, _ in DATE_ONLY_COLUMNS]
        + [(t, c) for t, c, _ in DATETIME_COLUMNS]
        + [(t, c) for t, c, _ in MIXED_COLUMNS]
    )
    issues = []
    for table, col in all_columns:
        rows = conn.execute(
            f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL AND {col} != ''"
        ).fetchall()
        for row_id, val in rows:
            if not val:
                continue
            # Check if ISO format
            date_part = val.strip()[:10]
            if len(date_part) == 10:
                parts = date_part.split("-")
                if len(parts) == 3 and len(parts[0]) == 4 and parts[0].startswith("20"):
                    try:
                        datetime.strptime(date_part, "%Y-%m-%d")
                        continue
                    except ValueError:
                        pass
            issues.append(f"  {table}.{col} id={row_id}: '{val}'")
    if issues:
        print(f"Found {len(issues)} non-ISO dates:")
        for i in issues[:20]:
            print(i)
        if len(issues) > 20:
            print(f"  ... and {len(issues) - 20} more")
    else:
        print("All dates validated — ISO format.")
    return len(issues)


def main():
    parser = argparse.ArgumentParser(description="Date format migration: DD/MM/YYYY → ISO 8601")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    group.add_argument("--migrate", action="store_true", help="Apply migration")
    group.add_argument("--rollback", action="store_true", help="Reverse migration")
    group.add_argument("--validate", action="store_true", help="Check all dates are ISO")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    if args.dry_run:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        print("=== DRY RUN (no changes will be made) ===\n")
        _migrate(conn, dry_run=True)
        print("\n=== DRY RUN COMPLETE ===")
        conn.close()

    elif args.migrate:
        backup_path = _backup_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        counts_before = {t: _count_rows(conn, t) for t, _, _ in DATE_ONLY_COLUMNS}
        _migrate(conn)
        counts_after = {t: _count_rows(conn, t) for t, _, _ in DATE_ONLY_COLUMNS}
        for t in counts_before:
            if counts_before[t] != counts_after[t]:
                print(f"WARNING: {t} row count changed: {counts_before[t]} -> {counts_after[t]}")
            else:
                print(f"  {t}: {counts_before[t]} rows (unchanged)")
        conn.close()
        print(f"\nBackup saved at: {backup_path}")

    elif args.rollback:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        _rollback(conn)
        conn.close()

    elif args.validate:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        issues = _validate(conn)
        conn.close()
        sys.exit(0 if issues == 0 else 1)


if __name__ == "__main__":
    main()
