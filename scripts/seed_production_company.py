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

import os
import sys
import traceback
from pathlib import Path

# ── Load .env so BackendSettings picks up OPERION_JWT_SECRET_KEY etc. ───
_dotenv_path = Path(__file__).resolve().parent.parent / ".env"
if _dotenv_path.exists():
    with open(_dotenv_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _val = _line.split("=", 1)
            _key = _key.strip()
            _val = _val.strip().strip("\"'")
            if not os.environ.get(_key):
                os.environ[_key] = _val

from backend.security import hash_password
from config import Config
from database.db_manager import DatabaseManager


def _fetch_user(db, email: str):
    """Return existing user row or None."""
    return db.conn.execute(
        "SELECT id, email, role, company_id FROM users WHERE email = ?",
        (email,),
    ).fetchone()


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

    manager_email = input("Enter Manager Email: ").strip().lower()
    if not manager_email:
        print("ERROR: Manager email cannot be empty.")
        return 1

    manager_password = input("Enter Manager Password: ")
    if not manager_password:
        print("ERROR: Manager password cannot be empty.")
        return 1

    # ── Provision ─────────────────────────────────────────────────────
    db = DatabaseManager(Config.DB_PATH)

    existing = _fetch_user(db, manager_email)

    if existing is not None:
        print(f"\n⚠ Email '{manager_email}' already exists (user id={existing['id']}, "
              f"company id={existing['company_id']}).")
        print("  [1] Update this user's password + point to a NEW company")
        print("  [2] Abort and use a different email")
        choice = input("Choose [1/2] (default 2): ").strip()
        if choice != "1":
            print("Seed aborted. Use a different email and re-run.")
            db.close()
            return 1
        # Fall through: will create a new company and update the user

    try:
        # Step 1 — Create company
        cursor = db.conn.execute(
            "INSERT INTO companies (company_name, subscription_tier) "
            "VALUES (?, ?)",
            (company_name, "starter"),
        )
        company_id = cursor.lastrowid
        print(f"\n✓ Company created (id={company_id})")

        # Step 2 — Hash password (bcrypt)
        hashed = hash_password(manager_password)

        # Step 3 — Create or update the manager user
        if existing is not None:
            db.conn.execute(
                "UPDATE users SET password_hash = ?, company_id = ?, "
                "is_active = 1, role = 'manager' WHERE email = ?",
                (hashed, company_id, manager_email),
            )
            print(f"✓ Manager updated: {manager_email} → reassigned to company {company_id}")
        else:
            db.conn.execute(
                "INSERT INTO users (email, password_hash, role, company_id, is_active) "
                "VALUES (?, ?, ?, ?, 1)",
                (manager_email, hashed, "manager", company_id),
            )
            print(f"✓ Manager created: {manager_email}")

        db.conn.commit()
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
