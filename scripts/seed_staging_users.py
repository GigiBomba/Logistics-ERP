"""Seed the local staging database with test users (driver + dispatcher).

Run via scripts/start_staging.bat, or directly:
    python scripts/seed_staging_users.py

Creates ``data/staging.db`` (schema via DatabaseManager), seeds company 1 and
two bcrypt-hashed users (password ``staging-pass``), plus a driver record for
the driver user so driver-facing mobile endpoints resolve cleanly.
"""
from __future__ import annotations


import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.security import hash_password  # noqa: E402
from database.db_manager import DatabaseManager  # noqa: E402

STAGING_USERS = [
    # (email, role, display_name)
    ("driver@staging.local", "driver", "Staging Driver"),
    ("dispatcher@staging.local", "dispatcher", "Staging Dispatcher"),
]
STAGING_PASSWORD = "staging-pass"


def seed_staging_users(db_path: str = "data/staging.db") -> DatabaseManager:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
    db = DatabaseManager(db_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    db.conn.execute(
        "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier) "
        "VALUES (1, 'Staging Company', 'starter')"
    )

    for email, role, name in STAGING_USERS:
        db.conn.execute(
            "INSERT OR IGNORE INTO users "
            "(email, password_hash, role, company_id, is_active, created_at) "
            "VALUES (?, ?, ?, 1, 1, ?)",
            (email, hash_password(STAGING_PASSWORD), role, now),
        )
        if role == "driver":
            # Link the driver row (user_id matches the users.id autoincrement).
            row = db.conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            if row is not None:
                db.conn.execute(
                    "INSERT OR IGNORE INTO drivers "
                    "(name, email, user_id, company_id, is_active, created_at, updated_at) "
                    "VALUES (?, ?, ?, 1, 1, ?, ?)",
                    (name, email, row["id"], now, now),
                )
    db.conn.commit()
    return db


if __name__ == "__main__":
    seed_staging_users()
    print("Staging DB seeded: data/staging.db (driver@staging.local / dispatcher@staging.local, password: staging-pass)")
