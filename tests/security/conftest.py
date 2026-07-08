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

import os
# ⚠ Set OPERION_DB_PATH before any other import that reads Config.DB_PATH.
# Config.DB_PATH is evaluated at module-import time, so the env var must be
# set before ANY test module or dependency imports from config.py.
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "test_security.db")
os.environ["OPERION_DB_PATH"] = TEST_DB_PATH
os.environ["OPERION_RATE_LIMIT"] = "10000"  # Disable effective rate limiting for tests

import bcrypt
import json
import pytest
import tempfile
from datetime import datetime
from fastapi.testclient import TestClient
from typing import Any, Dict, Optional

# Passwords
ADMIN_PW = "test-admin-pw-123"
DISPATCHER_PW = "dispatcher-pw-456"


def _clean_test_db():
    for suffix in ("", "-wal", "-shm"):
        p = TEST_DB_PATH + suffix
        if os.path.isfile(p):
            os.remove(p)


def _make_dispatcher_token(client, email, password):
    """Log in as a dispatcher user and return the access token."""
    resp = client.post("/api/v1/auth/token", data={
        "username": email,
        "password": password,
    })
    # May fail if DB users not seeded yet — handled by fixture ordering
    return resp.json()["access_token"] if resp.status_code == 200 else None


def _seed_test_data():
    """Directly insert two companies + users + sample data into the test DB."""
    from config import Config
    from database.db_manager import DatabaseManager

    db = DatabaseManager(TEST_DB_PATH)
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
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
    db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Session-scoped fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def app():
    """Create the FastAPI app with test env vars."""
    _clean_test_db()
    os.environ["OPERION_JWT_SECRET_KEY"] = "test-secret-key-32-chars-for-testing-only!!"
    admin_hash = bcrypt.hashpw(ADMIN_PW.encode(), bcrypt.gensalt(rounds=4)).decode()
    os.environ["OPERION_ADMIN_EMAIL"] = "admin-a@test.com"
    os.environ["OPERION_ADMIN_PASSWORD_HASH"] = admin_hash
    os.environ["OPERION_ENV"] = "test"

    _seed_test_data()

    from backend.main import app as fastapi_app
    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    """Return a TestClient bound to the test app."""
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════════
# Token fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def tokens(client):
    """Return dict with tokens for all test users."""
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
    """Return a DatabaseManager connected to the test DB for direct DB verification."""
    from database.db_manager import DatabaseManager
    return DatabaseManager(TEST_DB_PATH)


def create_test_trip(client, headers, overrides: dict = None) -> Dict[str, Any]:
    """POST /api/v1/trips/ and return the response JSON."""
    data = {
        "client_name": "E2E Test Client",
        "driver_name": "E2E Driver",
        "truck_number": "E2E-TRUCK",
        "status": "Planned",
    }
    if overrides:
        data.update(overrides)
    try:
        resp = client.post("/api/v1/trips/", json=data, headers=headers)
        return resp.json() if resp.status_code == 200 else {"error": resp.text, "status": resp.status_code}
    except Exception as e:
        return {"error": str(e), "status": 500}


def create_test_client(client, headers, name: str = "E2E Client", overrides: dict = None) -> Dict[str, Any]:
    """POST /api/v1/clients/ and return the response JSON."""
    data = {"email": "e2e@test.com", "phone": "+40-700-000-000"}
    if overrides:
        data.update(overrides)
    try:
        resp = client.post(f"/api/v1/clients/?name={name}", json=data, headers=headers)
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
    """POST /api/v1/fleet/trucks/ and return the response JSON."""
    data = {"plate_number": "E2E-001", "manufacturer": "TestTruck", "year": 2026, "model": "E2E Model", "status": "Active"}
    if overrides:
        data.update(overrides)
    try:
        resp = client.post("/api/v1/fleet/trucks/", json=data, headers=headers)
        return resp.json() if resp.status_code == 200 else {"error": resp.text, "status": resp.status_code}
    except Exception as e:
        return {"error": str(e), "status": 500}


def upload_test_document(client, headers, filename: str = "test.pdf",
                         content: bytes = None, mime: str = "application/pdf") -> Dict[str, Any]:
    """POST /api/v1/documents/upload and return the response JSON."""
    if content is None:
        content = b"%PDF-1.4 fake pdf content for testing"
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
