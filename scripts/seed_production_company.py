"""One-time production seeding utility.

Opens an interactive terminal prompt to collect company and manager
credentials, then provisions the company and manager user in the
database.

Usage:
    py -3.9 scripts/seed_production_company.py

After successful execution the script can be kept for future use
(re-run for additional tenants).  No credentials are hardcoded or
logged.
"""

import sys
import traceback
import warnings

# Suppress noisy passlib/bcrypt compatibility warning
warnings.filterwarnings("ignore", message="error reading bcrypt version")
warnings.filterwarnings("ignore", category=UserWarning, module="passlib")

from backend.security import hash_password
from config import Config
from database.db_manager import DatabaseManager

def main() -> int:
    print("=" * 60)
    print("  Operion — Production Company Seed Utility")
    print("=" * 60)
    print()

    # ── Prompt for inputs (never hardcode) ────────────────────────────
    company_name = input("Enter Company Name: ").strip()
    if not company_name:
        print("ERROR: Company name cannot be empty.")
        return 1

    manager_email = input("Enter Manager Email: ").strip()
    if not manager_email:
        print("ERROR: Manager email cannot be empty.")
        return 1

    manager_password = input("Enter Manager Password: ")
    if not manager_password:
        print("ERROR: Manager password cannot be empty.")
        return 1

    # ── Provision ─────────────────────────────────────────────────────
    db = DatabaseManager(Config.DB_PATH)

    try:
        # Step 1 — Create company
        cursor = db.conn.execute(
            "INSERT INTO companies (company_name, subscription_tier) "
            "VALUES (?, ?)",
            (company_name, "starter"),
        )
        company_id = cursor.lastrowid
        db.conn.commit()
        print(f"\n✓ Company created (id={company_id})")

        # Step 2 — Hash password (bcrypt, from Phase 0 security module)
        hashed = hash_password(manager_password)

        # Step 3 — Create manager user
        db.conn.execute(
            "INSERT INTO users (email, password_hash, role, company_id, is_active) "
            "VALUES (?, ?, ?, ?, 1)",
            (manager_email, hashed, "manager", company_id),
        )
        db.conn.commit()
        print(f"✓ Manager created: {manager_email}")
        print()
        print(f"Company:     {company_name}")
        print(f"Manager:     {manager_email}")
        print("Tier:        starter")
        print(f"Company ID:  {company_id}")
        print()
        print("Seeding complete. You can now log in as the manager.")
        return 0

    except Exception:
        db.conn.rollback()
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
