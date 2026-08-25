"""Shared fixtures for the security test suite.

Creates two test companies (A, B) each with a dispatcher user
and sample data (trips, clients, drivers, trucks). All tests
use a temporary SQLite database created fresh per test run.

Fixtures provided:
- client: FastAPI TestClient
- admin_token / auth_admin: admin user (env-var, no company scope)
- company_a_token / auth_a: Company A dispatcher
- company_b_token / auth_b: Company B dispatcher
- sample_data: dict of {trip_id, client_id, driver_id, truck_id} for each company
"""
from __future__ import annotations


import os
import uuid
# ⚠ Set OPERION_DB_PATH before any other import that reads Config.DB_PATH.
# Config.DB_PATH is evaluated at module-import time, so the env var must be
# set before ANY test module or dependency imports from config.py.
# Use a unique DB path per session to avoid conflicts with other test suites
# (e.g. E2E tests) that also set OPERION_DB_PATH at import time.
_TEST_DB_FILENAME = f"test_security_{uuid.uuid4().hex[:8]}.db"
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", _TEST_DB_FILENAME)
os.environ["OPERION_DB_PATH"] = TEST_DB_PATH
os.environ["OPERION_RATE_LIMIT"] = "10000"  # Disable effective rate limiting for tests
os.environ.pop("OPERION_API_KEY", None)  # Ensure API key middleware stays disabled

import bcrypt
import json
import sys
import pytest
import tempfile
from datetime import datetime
from fastapi.testclient import TestClient
from typing import Any, Dict, Optional

# Passwords
ADMIN_PW = "test-admin-pw-123"
DISPATCHER_PW = "dispatcher-pw-456"


def _clean_test_db():
    """Remove the test database files entirely.
    
    Only safe to call when NO SQLite connections exist. On Windows,
    SQLite holds file locks even after connection close, so this
    should only be called from fixture *setup* (before any app
    requests) or from a session-finalizer.
    """
    for suffix in ("", "-wal", "-shm"):
        p = TEST_DB_PATH + suffix
        if os.path.isfile(p):
            try:
                os.remove(p)
            except PermissionError:
                pass  # File still locked — the next setup will clean it


def _truncate_tables():
    """Delete all rows from known tables so the DB can be re-seeded.
    
    Also checkpoints and truncates the WAL to avoid locks when the
    next module connects. Should only be called after all connections
    from the current module are closed (i.e. in fixture teardown).
    """
    import sqlite3
    try:
        conn = sqlite3.connect(TEST_DB_PATH, timeout=2)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA journal_mode=DELETE")  # Switch off WAL so we can checkpoint
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for (tname,) in tables:
            conn.execute(f"DELETE FROM [{tname}]")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
        conn.close()
    except Exception:
        pass  # If the DB doesn't exist yet, that's fine


def _make_dispatcher_token(client, email, password):
    """Log in as a dispatcher user and return the access token."""
    resp = client.post("/api/v1/auth/token", data={
        "username": email,
        "password": password,
    })
    # May fail if DB users not seeded yet — handled by fixture ordering
    return resp.json()["access_token"] if resp.status_code == 200 else None


def _seed_test_data(db_path=None):
    """Directly insert two companies + users + sample data into the test DB."""
    if db_path is None:
        db_path = os.environ.get("OPERION_DB_PATH", TEST_DB_PATH)
    # Use DatabaseManager for schema creation (handles all tables, migrations, indexes)
    from database.db_manager import DatabaseManager
    db = DatabaseManager(db_path)
    db.close()
    
    # Re-open with raw sqlite3 for seeding (avoids lock contention during import)
    import sqlite3
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=1000")
    db = type('_', (), {'conn': conn})()
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # ── Ensure columns required by mobile endpoints and Pydantic models ──
    for col_ddl in [
        "ALTER TABLE trips ADD COLUMN reference TEXT DEFAULT ''",
        "ALTER TABLE trips ADD COLUMN loading_city TEXT DEFAULT ''",
        "ALTER TABLE trips ADD COLUMN delivery_city TEXT DEFAULT ''",
        "ALTER TABLE trips ADD COLUMN updated_at TEXT",
        "ALTER TABLE trips ADD COLUMN notes TEXT DEFAULT ''",
        "ALTER TABLE trips ADD COLUMN loading_lat REAL",
        "ALTER TABLE trips ADD COLUMN loading_lng REAL",
        "ALTER TABLE trips ADD COLUMN delivery_lat REAL",
        "ALTER TABLE trips ADD COLUMN delivery_lng REAL",
    ]:
        col_name = col_ddl.split()[3]
        try:
            cols = {r[1] for r in db.conn.execute("PRAGMA table_info(trips)").fetchall()}
            if col_name not in cols:
                db.conn.execute(col_ddl)
        except Exception:
            pass
    dispatcher_hash = bcrypt.hashpw(DISPATCHER_PW.encode(), bcrypt.gensalt(rounds=4)).decode()

    # ── Companies ──────────────────────────────────────────────────
    db.conn.execute(
        "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, 1, ?, ?)",
        (1, "Company A", "professional", now, now),
    )
    db.conn.execute(
        "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier, is_active, created_at, updated_at) "
        "VALUES (?, ?, ?, 1, ?, ?)",
        (2, "Company B", "starter", now, now),
    )

    # ── Users (dispatchers) ─────────────────────────────────────────
    db.conn.execute(
        "INSERT OR IGNORE INTO users (email, password_hash, role, company_id, is_active, created_at) "
        "VALUES (?, ?, 'dispatcher', 1, 1, ?)",
        ("dispatcher-a@test.com", dispatcher_hash, now),
    )
    db.conn.execute(
        "INSERT OR IGNORE INTO users (email, password_hash, role, company_id, is_active, created_at) "
        "VALUES (?, ?, 'dispatcher', 2, 1, ?)",
        ("dispatcher-b@test.com", dispatcher_hash, now),
    )

    # ── Sample data: Company A ──────────────────────────────────────
    db.conn.execute(
        "INSERT OR IGNORE INTO clients (id, name, email, phone, is_active, created_at, company_id) "
        "VALUES (1, 'Client A-1', 'client-a1@test.com', '+40-700-000-001', 1, ?, 1)", (now,))
    db.conn.execute(
        "INSERT OR IGNORE INTO clients (id, name, email, phone, is_active, created_at, company_id) "
        "VALUES (2, 'Client A-2', 'client-a2@test.com', '+40-700-000-002', 1, ?, 1)", (now,))

    db.conn.execute(
        "INSERT OR IGNORE INTO drivers (id, name, phone, email, is_active, created_at, updated_at, company_id) "
        "VALUES (1, 'Driver A-1', '+40-711-000-001', 'driver-a1@test.com', 1, ?, ?, 1)", (now, now))
    db.conn.execute(
        "INSERT OR IGNORE INTO drivers (id, name, phone, email, is_active, created_at, updated_at, company_id) "
        "VALUES (2, 'Driver A-2', '+40-711-000-002', 'driver-a2@test.com', 1, ?, ?, 1)", (now, now))

    db.conn.execute(
        "INSERT OR IGNORE INTO trucks (id, plate_number, model, status, active_status, company_id) "
        "VALUES (1, 'AB-01-AAA', 'Volvo FH', 'Active', 1, 1)")
    db.conn.execute(
        "INSERT OR IGNORE INTO trucks (id, plate_number, model, status, active_status, company_id) "
        "VALUES (2, 'AB-02-BBB', 'Scania R', 'Active', 1, 1)")

    db.conn.execute(
        "INSERT OR IGNORE INTO trips (id, client_name, driver_name, truck_number, status, "
        "created_at, start_date, company_id) "
        "VALUES (1, 'Client A-1', 'Driver A-1', 'AB-01-AAA', 'Planned', ?, ?, 1)", (now, now))
    db.conn.execute(
        "INSERT OR IGNORE INTO trips (id, client_name, driver_name, truck_number, status, "
        "created_at, start_date, company_id) "
        "VALUES (2, 'Client A-2', 'Driver A-2', 'AB-02-BBB', 'In Transit', ?, ?, 1)", (now, now))

    # ── Sample data: Company B ──────────────────────────────────────
    db.conn.execute(
        "INSERT OR IGNORE INTO clients (id, name, email, phone, is_active, created_at, company_id) "
        "VALUES (3, 'Client B-1', 'client-b1@test.com', '+40-700-000-003', 1, ?, 2)", (now,))
    db.conn.execute(
        "INSERT OR IGNORE INTO clients (id, name, email, phone, is_active, created_at, company_id) "
        "VALUES (4, 'Client B-2', 'client-b2@test.com', '+40-700-000-004', 1, ?, 2)", (now,))

    db.conn.execute(
        "INSERT OR IGNORE INTO drivers (id, name, phone, email, is_active, created_at, updated_at, company_id) "
        "VALUES (3, 'Driver B-1', '+40-711-000-003', 'driver-b1@test.com', 1, ?, ?, 2)", (now, now))
    db.conn.execute(
        "INSERT OR IGNORE INTO drivers (id, name, phone, email, is_active, created_at, updated_at, company_id) "
        "VALUES (4, 'Driver B-2', '+40-711-000-004', 'driver-b2@test.com', 1, ?, ?, 2)", (now, now))

    db.conn.execute(
        "INSERT OR IGNORE INTO trucks (id, plate_number, model, status, active_status, company_id) "
        "VALUES (3, 'CD-03-CCC', 'MAN TGX', 'Active', 1, 2)")
    db.conn.execute(
        "INSERT OR IGNORE INTO trucks (id, plate_number, model, status, active_status, company_id) "
        "VALUES (4, 'CD-04-DDD', 'Iveco S-Way', 'Active', 1, 2)")

    db.conn.execute(
        "INSERT OR IGNORE INTO trips (id, client_name, driver_name, truck_number, status, "
        "created_at, start_date, company_id) "
        "VALUES (3, 'Client B-1', 'Driver B-1', 'CD-03-CCC', 'Delivered', ?, ?, 2)", (now, now))
    db.conn.execute(
        "INSERT OR IGNORE INTO trips (id, client_name, driver_name, truck_number, status, "
        "created_at, start_date, company_id) "
        "VALUES (4, 'Client B-2', 'Driver B-2', 'CD-04-DDD', 'Loading', ?, ?, 2)", (now, now))

    db.conn.commit()
    db.conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Module-scoped fixtures — each test module gets a fresh app/client/DB
# to avoid SQLite lock contention and token-invalidation across tests.
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def app(request):
    """Create the FastAPI app with test env vars (module-scoped — unique per module)."""
    # Use a unique DB file per module to avoid Windows SQLite file-lock
    # contention between modules.  The prior module's DB file + WAL/SHM
    # are simply abandoned; they will be deleted by _clean_test_db from
    # a fresh process or a manual cleanup.
    module_name = request.module.__name__.replace("tests.security.", "").replace(".", "_")
    _db_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "data",
        f"test_security_{module_name}_{uuid.uuid4().hex[:8]}.db",
    )
    os.environ["OPERION_DB_PATH"] = _db_path

    os.environ["OPERION_JWT_SECRET_KEY"] = "test-secret-key-32-chars-for-testing-only!!"
    admin_hash = bcrypt.hashpw(ADMIN_PW.encode(), bcrypt.gensalt(rounds=4)).decode()
    os.environ["OPERION_ADMIN_EMAIL"] = "admin-a@test.com"
    os.environ["OPERION_ADMIN_PASSWORD_HASH"] = admin_hash
    os.environ["OPERION_ENV"] = "test"

    # Clear in-memory login lockout state so the tokens fixture never fails
    # with "account locked".  Each module starts with a fresh lockout slate.
    from backend.api.v1.auth import _clear_lockout, _failed_attempts
    _failed_attempts.clear()
    for email in ("admin-a@test.com", "dispatcher-a@test.com", "dispatcher-b@test.com",
                  "driver-a@test.com", "driver-b@test.com"):
        _clear_lockout(email)

    # Create the schema via DatabaseManager on the unique DB file
    from database.db_manager import DatabaseManager
    dbu = DatabaseManager(_db_path)
    dbu.close()

    # Reset the global DatabaseManager singleton so init_db() creates a
    # fresh connection to *our* DB (not a stale one from a prior module).
    if "backend.dependencies" in sys.modules:
        _bd = sys.modules["backend.dependencies"]
        if _bd._db_instance is not None:
            _bd._db_instance.close()
            _bd._db_instance = None
    # Force Config.DB_PATH to our unique DB file.  tests/test_security_verification.py
    # (and tests/chaos/test_chaos_celery.py) importlib.reload the config chain,
    # which REPLACES ``config.Config`` with a NEW class object.  ``backend.dependencies``
    # still references the ORIGINAL class, and ``init_db()`` reads THAT reference —
    # so update it too, otherwise the app queries a stale worker DB (e.g. trips with
    # NULL created_at → 422 in TripResponse) instead of this module's seeded file.
    from config import Config
    Config.DB_PATH = _db_path
    if "backend.dependencies" in sys.modules:
        _bd = sys.modules["backend.dependencies"]
        if getattr(_bd, "Config", None) is not None:
            _bd.Config.DB_PATH = _db_path
    # Disable the API-key middleware for this module (another module may have
    # left OPERION_API_KEY set, which enables it and 401s every request without
    # an X-API-Key header).  Reset BOTH the env var and the frozen class attr
    # the middleware reads at construction.
    os.environ.pop("OPERION_API_KEY", None)
    Config.API_KEY = ""
    try:
        import backend.middleware.auth_middleware as _auth_mw
        _auth_mw.Config.API_KEY = ""
    except Exception:
        pass



    # Prevent background threads from OcrService and ai_fallback that would
    # leak across test modules and cause timeouts (daemon threads from OCR
    # workers + 8-minute keepalive refresh thread).
    import services.document.ocr_service as _ocr_mod
    import services.document_automation.ai_fallback as _ai_mod
    _orig_ocr_init = _ocr_mod.OcrService.__init__
    _orig_start_workers = _ocr_mod.OcrService._start_ocr_workers

    def _noop_start(self):
        self._ocr_workers = []
        self._ocr_running = False

    _ocr_mod.OcrService._start_ocr_workers = _noop_start
    _ai_mod._schedule_keepalive_refresh = lambda: None

    from backend.main import app as fastapi_app
    
    # Seed test data via a fresh connection (app is already initialized)
    _seed_test_data()
    
    yield fastapi_app
    
    # Teardown: close the global DatabaseManager singleton so SQLite
    # connections are released and the DB file can be safely cleaned.
    # Without this, the connection pool from backend.dependencies.init_db()
    # keeps the file locked (especially on Windows).
    import backend.dependencies as _deps
    if _deps._db_instance is not None:
        _deps._db_instance.close()
        _deps._db_instance = None
    
    # Truncate all tables so the next module starts with a clean DB.
    # We use truncation instead of file deletion because some SQLite
    # connections may still be open (WAL checkpoint, etc.).
    _truncate_tables()


@pytest.fixture(scope="module")
def client(app):
    """Return a TestClient bound to the test app (module-scoped)."""
    return TestClient(app, raise_server_exceptions=False)


# ═══════════════════════════════════════════════════════════════════════════════
# Token fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def tokens(client):
    """Return dict with tokens for all test users."""
    # Clear any leftover lockout state so all logins succeed
    from backend.api.v1.auth import _clear_lockout, _failed_attempts
    _failed_attempts.clear()
    for email in ("admin-a@test.com", "dispatcher-a@test.com", "dispatcher-b@test.com",
                  "driver-a@test.com", "driver-b@test.com"):
        _clear_lockout(email)

    result = {}

    # Admin
    r = client.post("/api/v1/auth/token", data={
        "username": "admin-a@test.com", "password": ADMIN_PW,
    })
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    result["admin"] = r.json()["access_token"]
    result["admin_refresh"] = r.json()["refresh_token"]

    # Company A dispatcher
    r = client.post("/api/v1/auth/token", data={
        "username": "dispatcher-a@test.com", "password": DISPATCHER_PW,
    })
    assert r.status_code == 200, f"Company A login failed: {r.text}"
    result["company_a"] = r.json()["access_token"]

    # Company B dispatcher
    r = client.post("/api/v1/auth/token", data={
        "username": "dispatcher-b@test.com", "password": DISPATCHER_PW,
    })
    assert r.status_code == 200, f"Company B login failed: {r.text}"
    result["company_b"] = r.json()["access_token"]

    return result


@pytest.fixture
def admin_token(tokens):
    return tokens["admin"]


@pytest.fixture
def auth_admin(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def company_a_token(tokens):
    return tokens["company_a"]


@pytest.fixture
def auth_a(company_a_token):
    return {"Authorization": f"Bearer {company_a_token}"}


@pytest.fixture
def company_b_token(tokens):
    return tokens["company_b"]


@pytest.fixture
def auth_b(company_b_token):
    return {"Authorization": f"Bearer {company_b_token}"}


# ═══════════════════════════════════════════════════════════════════════════════
# E2E test helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_db():
    """Return a DatabaseManager connected to the test DB for direct DB verification.

    Reads the DB path from ``OPERION_DB_PATH`` at call time because the
    ``app`` fixture overrides it with a unique per-module file.  Using the
    module-level ``TEST_DB_PATH`` here made DB checks query a different
    (empty/stale) file, so company_id verifications always skipped.
    """
    from database.db_manager import DatabaseManager
    path = os.environ.get("OPERION_DB_PATH", TEST_DB_PATH)
    return DatabaseManager(path)


def create_test_trip(client, headers, overrides: dict = None, company_id: int = 1) -> Dict[str, Any]:
    """POST /api/v1/trips/ and return the response JSON.
    
    Uses the schema's required ``client_id`` field. Defaults to client_id=1
    (Client A-1 in Company A). Override via dict or *company_id*.
    
    Automatically removes the legacy ``truck_number`` field (replaced by
    ``truck_plate`` / ``truck_id`` in the Pydantic schema) and maps
    ``company_id`` to a valid ``client_id``.
    """
    data = {
        "client_name": "E2E Test Client",
        "driver_name": "E2E Driver",
        "status": "Planned",
    }
    # Map company_id to a valid client_id
    if company_id == 2:
        data["client_id"] = 3  # First client in Company B
    else:
        data["client_id"] = 1  # First client in Company A
    if overrides:
        data.update(overrides)
    # TripCreateRequest/TripCreate use ``truck_plate``; the DB column that
    # stores it is still ``truck_number``.  Map the legacy name to the schema
    # field so the value actually round-trips through create→GET (previously
    # it was silently dropped and the lifecycle assertion could never pass).
    if "truck_number" in data and "truck_plate" not in data:
        data["truck_plate"] = data.pop("truck_number")
    data.pop("truck_number", None)
    try:
        resp = client.post("/api/v1/trips/", json=data, headers=headers)
        return resp.json() if resp.status_code in (200, 201) else {"error": resp.text, "status": resp.status_code}
    except Exception as e:
        return {"error": str(e), "status": 500}


def create_test_client(client, headers, name: str = "E2E Client", overrides: dict = None) -> Dict[str, Any]:
    """POST /api/v1/clients/ and return the response JSON."""
    data = {"name": name, "email": "e2e@test.com", "phone": "+40-700-000-000"}
    if overrides:
        data.update(overrides)
    try:
        resp = client.post("/api/v1/clients/", json=data, headers=headers)
        return resp.json() if resp.status_code == 200 else {"error": resp.text, "status": resp.status_code}
    except Exception as e:
        return {"error": str(e), "status": 500}


def create_test_driver(client, headers, overrides: dict = None) -> Dict[str, Any]:
    """POST /api/v1/drivers/ and return the response JSON."""
    data = {"name": "E2E Driver", "phone": "+40-711-000-999", "email": "e2e-driver@test.com"}
    if overrides:
        data.update(overrides)
    try:
        resp = client.post("/api/v1/drivers/", json=data, headers=headers)
        return resp.json() if resp.status_code == 201 else {"error": resp.text, "status": resp.status_code}
    except Exception as e:
        return {"error": str(e), "status": 500}


def create_test_truck(client, headers, overrides: dict = None) -> Dict[str, Any]:
    """POST /api/v1/fleet/trucks/ and return the response JSON.

    Uses the non-slash URL to avoid 307 redirects from trailing-slash handling.
    """
    data = {"plate_number": "E2E-001", "manufacturer": "TestTruck", "year": 2026, "model": "E2E Model", "status": "Active"}
    if overrides:
        data.update(overrides)
    try:
        # Use URL without trailing slash to avoid 307 redirect
        resp = client.post("/api/v1/fleet/trucks", json=data, headers=headers)
        # Accept both 200 (direct) and 307 (redirect that would succeed on follow)
        if resp.status_code == 307:
            location = resp.headers.get("location", "")
            if location:
                resp = client.post(location, json=data, headers=headers)
        return resp.json() if resp.status_code == 200 else {"error": resp.text, "status": resp.status_code}
    except Exception as e:
        return {"error": str(e), "status": 500}


def _minimal_valid_pdf() -> bytes:
    """Return a minimal but valid PDF that pymupdf can open without crashing."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n190\n%%EOF"
    )


def upload_test_document(client, headers, filename: str = "test.pdf",
                         content: bytes = None, mime: str = "application/pdf") -> Dict[str, Any]:
    """POST /api/v1/documents/upload and return the response JSON."""
    if content is None:
        content = _minimal_valid_pdf()
    try:
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": (filename, content, mime)},
            data={"category": "test"},
            headers=headers,
        )
        return resp.json() if resp.status_code == 200 else {"error": resp.text, "status": resp.status_code}
    except Exception as e:
        return {"error": str(e), "status": 500}


def verify_db_company_id(table: str, record_id: int, expected_company_id: int) -> bool:
    """Query the test DB directly to verify a record's company_id."""
    db = get_db()
    try:
        row = db.conn.execute(
            f"SELECT company_id FROM {table} WHERE id = ?", (record_id,)
        ).fetchone()
        return row is not None and row["company_id"] == expected_company_id
    finally:
        db.close()
