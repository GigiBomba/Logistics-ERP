"""Staging harness DB bootstrap — schema init + idempotent staging-user seeding.

Used by ``scripts/start_staging.ps1`` (and runnable directly):

    python -m scripts.staging_seed [--env-file .env.staging] [--db PATH]

What it does
------------
1. Parses the staging env file (default ``.env.staging``) and applies every
   key as a REAL process environment variable **before** any backend import.
   The repo-root ``.env`` is loaded by ``backend/main.py`` via python-dotenv
   with override=False, so the staging values set here always win.
2. Ensures the SQLite schema through ``database.db_manager.DatabaseManager`` —
   the exact init path the API itself uses at startup
   (``_create_tables_and_indices`` + ``_run_column_migrations`` +
   ``_migrate_legacy_data`` + mobile tables).  For SQLite this is the
   repository's schema-init path (``alembic upgrade head`` is only used for
   the PostgreSQL / Freight-Exchange tables, see database/db_manager.py).
3. Idempotently seeds the staging smoke users (dispatcher + driver), a linked
   driver record, one truck and one current trip for the driver so the smoke
   chain (tests/staging/test_staging_smoke.py) has real data to read.

Seeding mirrors the conventions in ``tests/security/conftest.py``:
companies → users (bcrypt password hashes) → drivers → trips.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Dict, Optional

# ── Path bootstrap: make the repo root importable when run as a script ──
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_DEFAULT_ENV_FILE = os.path.join(_REPO_ROOT, ".env.staging")


# ═══════════════════════════════════════════════════════════════════════════
# Env-file parsing / application
# ═══════════════════════════════════════════════════════════════════════════

def parse_env_file(path: str) -> Dict[str, str]:
    """Parse a simple ``KEY=VALUE`` env file.  Returns ``{}`` if missing.

    - ``#`` comments and blank lines are skipped
    - inline ``# comment`` after a value is stripped (no quoting support)
    - double/single quotes around a value are removed
    """
    result: Dict[str, str] = {}
    if not os.path.isfile(path):
        return result
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            # Strip a trailing inline comment (space + #)
            if " #" in value:
                value = value.split(" #", 1)[0].rstrip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            result[key] = value
    return result


def apply_env(vars: Dict[str, str]) -> None:
    """Set every entry as a process environment variable.

    Empty-string values are set explicitly (not removed) so python-dotenv's
    override=False cannot repopulate them from the repo-root ``.env``.
    """
    for key, value in vars.items():
        os.environ[key] = value


# ═══════════════════════════════════════════════════════════════════════════
# Schema + seed
# ═══════════════════════════════════════════════════════════════════════════

def ensure_schema(db_path: str) -> None:
    """Create/upgrade the full app schema at *db_path* (repo init path)."""
    from database.db_manager import DatabaseManager

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    db = DatabaseManager(db_path)  # noqa: F841 — schema init happens in __init__
    db.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"


def _bcrypt_hash(password: str) -> str:
    import bcrypt

    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=4)).decode()


def seed_staging_data(db_path: str, cfg: Dict[str, str]) -> Dict[str, int]:
    """Idempotently seed the staging company, users, driver, truck and trip.

    *cfg* must contain ``STAGING_*`` credentials (from the env file + env
    overrides).  Returns a dict with the inserted/known ids::

        {"company_id", "dispatcher_user_id", "driver_user_id", "driver_id",
         "trip_id"}

    Mirrors ``tests/security/conftest.py::_seed_test_data``.
    """
    dispatcher_email = cfg.get("STAGING_DISPATCHER_EMAIL", "staging.dispatcher@operion.test")
    dispatcher_pw = cfg.get("STAGING_DISPATCHER_PASSWORD", "Staging-123!")
    driver_email = cfg.get("STAGING_DRIVER_EMAIL", "staging.driver@operion.test")
    driver_pw = cfg.get("STAGING_DRIVER_PASSWORD", "Staging-123!")

    now = _now_iso()

    # ── Schema first ─────────────────────────────────────────────────────
    ensure_schema(db_path)

    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        # ── Company 1 ───────────────────────────────────────────────────
        # NOTE: tier must be 'enterprise' — the only value that satisfies BOTH
        # the companies.subscription_tier CHECK (starter/professional/enterprise)
        # AND backend.copilot.schemas.GlobalContext.subscription_tier
        # (Literal["pro","business","enterprise"]).  Any other tier makes
        # POST /api/v1/copilot/chat fail pydantic validation (pre-existing
        # mismatch — see docs/staging-runbook.md §3.3).
        conn.execute(
            "INSERT OR IGNORE INTO companies "
            "(id, company_name, subscription_tier, is_active, created_at, updated_at) "
            "VALUES (?, ?, 'enterprise', 1, ?, ?)",
            (1, "Staging Company", now, now),
        )
        conn.execute(
            "UPDATE companies SET subscription_tier = 'enterprise', is_active = 1 WHERE id = 1"
        )

        dispatcher_hash = _bcrypt_hash(dispatcher_pw)
        driver_hash = _bcrypt_hash(driver_pw)

        # ── Users ───────────────────────────────────────────────────────
        conn.execute(
            "INSERT OR IGNORE INTO users "
            "(email, password_hash, role, company_id, is_active, display_name, created_at) "
            "VALUES (?, ?, 'dispatcher', 1, 1, 'Staging Dispatcher', ?)",
            (dispatcher_email, dispatcher_hash, now),
        )
        conn.execute(
            "INSERT OR IGNORE INTO users "
            "(email, password_hash, role, company_id, is_active, display_name, created_at) "
            "VALUES (?, ?, 'driver', 1, 1, 'Staging Driver', ?)",
            (driver_email, driver_hash, now),
        )
        # Refresh the hash on every run (passwords may have changed in cfg).
        conn.execute(
            "UPDATE users SET password_hash = ?, is_active = 1 WHERE email = ?",
            (dispatcher_hash, dispatcher_email),
        )
        conn.execute(
            "UPDATE users SET password_hash = ?, is_active = 1 WHERE email = ?",
            (driver_hash, driver_email),
        )

        dispatcher_row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (dispatcher_email,)
        ).fetchone()
        driver_user_row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (driver_email,)
        ).fetchone()
        dispatcher_user_id = int(dispatcher_row["id"])
        driver_user_id = int(driver_user_row["id"])

        # ── Driver record linked to the driver user (by email + user_id) ─
        conn.execute(
            "INSERT OR IGNORE INTO drivers "
            "(name, email, user_id, company_id, is_active, created_at, updated_at) "
            "VALUES ('Staging Driver', ?, ?, 1, 1, ?, ?)",
            (driver_email, driver_user_id, now, now),
        )
        driver_row = conn.execute(
            "SELECT id FROM drivers WHERE email = ? AND company_id = 1",
            (driver_email,),
        ).fetchone()
        driver_id = int(driver_row["id"])

        # Link the user row back to the driver record (defensive — the mobile
        # endpoints resolve drivers by email first, user_id as fallback).
        conn.execute("UPDATE users SET driver_id = ? WHERE id = ?", (driver_id, driver_user_id))

        # ── Truck for company 1 ──────────────────────────────────────────
        conn.execute(
            "INSERT OR IGNORE INTO trucks "
            "(id, plate_number, manufacturer, model, status, active_status, company_id) "
            "VALUES (1, 'STG-01-XXX', 'Volvo', 'FH Staging', 'Active', 1, 1)"
        )

        # ── One current trip for the driver (smoke chain data) ──────────
        trip = conn.execute(
            "SELECT id FROM trips WHERE cmr_number = 'STG-SMOKE-1001'"
        ).fetchone()
        if trip is None:
            cur = conn.execute(
                """INSERT INTO trips
                   (company_id, cmr_number, driver_id, driver_name, truck_number,
                    status, place_of_loading, loading_country, delivery_country,
                    start_date, end_date, created_at)
                   VALUES (1, 'STG-SMOKE-1001', ?, 'Staging Driver', 'STG-01-XXX',
                           'In Transit', 'Berlin', 'DE', 'Paris',
                           ?, ?, ?)""",
                (driver_id, now, "2026-08-01T18:00:00Z", now),
            )
            trip_id = int(cur.lastrowid)
        else:
            trip_id = int(trip["id"])

        conn.commit()
    finally:
        conn.close()

    return {
        "company_id": 1,
        "dispatcher_user_id": dispatcher_user_id,
        "driver_user_id": driver_user_id,
        "driver_id": driver_id,
        "trip_id": trip_id,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Staging harness DB bootstrap")
    parser.add_argument(
        "--env-file",
        default=_DEFAULT_ENV_FILE,
        help="Path to the staging env file (default: .env.staging)",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Database path override (default: OPERION_DB_PATH from the env file)",
    )
    args = parser.parse_args(argv)

    env = parse_env_file(args.env_file)
    if not env:
        print(f"[staging_seed] WARNING: no env file found at {args.env_file} — using defaults")

    # Apply the env BEFORE importing anything that reads it.
    apply_env(env)

    db_path = args.db or env.get("OPERION_DB_PATH") or "data/staging.db"
    print(f"[staging_seed] DB path: {os.path.abspath(db_path)}")
    print("[staging_seed] Ensuring schema (DatabaseManager init path)...")
    ensure_schema(db_path)
    ids = seed_staging_data(db_path, env)
    print(
        "[staging_seed] Seeded: company={company_id} dispatcher_user={dispatcher_user_id} "
        "driver_user={driver_user_id} driver={driver_id} trip={trip_id}".format(**ids)
    )
    print("[staging_seed] Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
