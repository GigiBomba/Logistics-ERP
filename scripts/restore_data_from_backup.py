"""Restore business data from the latest backup into the current schema.
Seeds company + admin user if missing.

NOTE: This script uses ``sqlite3.connect()`` directly and will NOT work
with a PostgreSQL backend.  It is strictly SQLite-only.

Usage:
    py scripts/restore_data_from_backup.py
"""
from __future__ import annotations
import glob
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load .env before anything else
from dotenv import load_dotenv
dotenv_path = os.path.join(PROJECT_ROOT, ".env")
if os.path.isfile(dotenv_path):
    load_dotenv(dotenv_path)

from config import Config
from database.db_manager import DatabaseManager
from utils.resource_path import data_path

BACKUP_DIR = data_path("data/backups")


def get_latest_backup() -> str:
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "*.db")))
    if not backups:
        print("No backup files found.")
        sys.exit(1)
    latest = backups[-1]
    print(f"Using backup: {latest}")
    return latest


def table_exists(conn, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def copy_table(src, dst, table: str, columns: list[str], placeholders: list[str],
               extra_columns: dict[str, object] | None = None):
    col_list = ", ".join(columns)
    ph_list = ", ".join(placeholders)
    dst_cols = col_list
    if extra_columns:
        dst_cols += ", " + ", ".join(extra_columns.keys())
        ph_list += ", " + ", ".join(["?"] * len(extra_columns))

    rows = src.execute(f"SELECT {col_list} FROM \"{table}\"").fetchall()
    if not rows:
        print(f"  {table}: 0 rows (nothing to copy)")
        return

    for row in rows:
        values = list(row)
        if extra_columns:
            values.extend(extra_columns.values())
        try:
            dst.execute(
                f"INSERT OR IGNORE INTO \"{table}\" ({dst_cols}) VALUES ({ph_list})",
                values
            )
        except Exception as e:
            print(f"  {table}: skipped row: {e}")

    print(f"  {table}: {len(rows)} rows copied")


def main():
    print("=" * 60)
    print("  Operion - Data Restoration Utility")
    print("=" * 60)

    db = DatabaseManager(Config.DB_PATH)

    # Step 1: Seed company + admin user
    admin_email = os.environ.get("OPERION_ADMIN_EMAIL", "")
    admin_hash = os.environ.get("OPERION_ADMIN_PASSWORD_HASH", "")

    existing_company = db.conn.execute("SELECT id FROM companies LIMIT 1").fetchone()
    company_id = 1
    if not existing_company:
        db.conn.execute(
            "INSERT INTO companies (id, company_name, subscription_tier, is_active) "
            "VALUES (?, ?, ?, 1)",
            (company_id, "Default Company", "starter")
        )
        db.conn.commit()
        print(f"\nCompany created (id={company_id})")
    else:
        company_id = existing_company[0]
        print(f"\nCompany already exists (id={company_id})")

    existing_user = db.conn.execute(
        "SELECT id FROM users WHERE email=?", (admin_email,)
    ).fetchone()
    if not existing_user and admin_email and admin_hash:
        pwd_hash = admin_hash
        if not pwd_hash.startswith("$2"):
            from backend.security import hash_password
            pwd_hash = hash_password(admin_hash)
        db.conn.execute(
            "INSERT INTO users (email, password_hash, role, company_id, is_active) "
            "VALUES (?, ?, ?, ?, 1)",
            (admin_email, pwd_hash, "admin", company_id)
        )
        db.conn.commit()
        print(f"Admin user created: {admin_email}")
    elif existing_user:
        print(f"Admin user already exists: {admin_email}")
    else:
        print("No admin credentials in .env - skipping user seed")

    # Step 2: Copy data from latest backup
    backup_path = get_latest_backup()
    src = sqlite3.connect(backup_path)
    src.row_factory = sqlite3.Row

    try:
        print(f"\n--- Copying data from backup ---")

        tables_config = [
            ("trips", ["id", "created_at", "truck_number", "driver_name", "client_name",
                        "distance_km", "total_price_eur", "rate_per_km", "gross_per_km",
                        "net_profit", "start_date", "end_date", "payment_date", "extra_costs",
                        "fuel_cost", "toll_cost", "salary_cost", "currency", "status",
                        "context_json", "route_history_v2_id", "truck_consumption_l_per_100km"],
             {"company_id": company_id}),
            ("trucks", ["id", "plate_number", "model", "manufacturer", "year", "vin",
                         "fuel_consumption", "mileage", "monthly_rate", "status",
                         "insurance_expiry", "inspection_expiry", "maintenance_due",
                         "active_status"],
             {"company_id": company_id}),
            ("drivers", ["id", "name", "phone", "email", "license_number", "license_category",
                          "license_expiry", "medical_expiry", "hire_date", "monthly_salary",
                          "notes", "is_active", "created_at", "updated_at"],
             {"company_id": company_id}),
            ("invoices", ["id", "trip_id", "invoice_number", "issue_date", "due_date",
                           "total_amount", "status"],
             {"company_id": company_id}),
            ("route_history_v2", ["id", "route_fingerprint", "metadata_version", "created_at",
                                   "last_calculated_at", "calculation_count", "stops_json",
                                   "geometry_compressed", "geometry_encoding", "total_distance_km",
                                   "duration_min", "truck_id", "truck_label", "truck_json",
                                   "profile", "excluded_countries_json", "toll_estimates_json",
                                   "fuel_estimates_json", "profit_estimates_json",
                                   "countries_traversed_json", "route_summary_json", "archived_at"],
             {"company_id": company_id, "is_committed": 0}),
            ("route_events", ["id", "route_id", "event_type", "payload_json", "created_at"],
             None),
            ("truck_route_assignments", ["id", "truck_id", "route_id", "status", "assigned_at",
                                          "started_at", "completed_at", "archived_at", "notes"],
             None),
            ("driver_truck_assignments", ["id", "driver_id", "truck_id", "assigned_at"],
             None),
            ("email_logs", ["id", "trip_id", "recipient", "subject", "timestamp",
                             "status", "error_msg"],
             None),
            ("settings", ["key", "value"], None),
        ]

        for table, columns, extra in tables_config:
            if not table_exists(src, table):
                print(f"  {table}: not found in backup (skipped)")
                continue
            if not table_exists(db.conn, table):
                print(f"  {table}: not found in target (skipped)")
                continue
            placeholders = ["?"] * len(columns)
            try:
                copy_table(src, db.conn, table, columns, placeholders, extra_columns=extra)
            except Exception as e:
                print(f"  {table}: error - {e}")

        db.conn.commit()
    finally:
        src.close()
        db.close()

    print()
    print("Restoration complete. Restart the app to see your data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
