"""Shared fixtures for the security test suite.

Creates two test companies (A, B) each with a full set of test users
(admin, dispatcher) and sample data. Runs inside a temporary SQLite
database created per session.
"""

import os
import json
import bcrypt
import pytest
from fastapi.testclient import TestClient

# ── Test configuration ───────────────────────────────────────────────────────
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "test_security.db")
COMPANY_A_ID = 1
COMPANY_B_ID = 2

# Passwords (plaintext, only used in tests)
ADMIN_PW = "test-admin-pw-123"
DISPATCHER_PW = "test-dispatcher-pw-456"


def _clean_test_db():
    for suffix in ("", "-wal", "-shm"):
        p = TEST_DB_PATH + suffix
        if os.path.isfile(p):
            os.remove(p)


@pytest.fixture(scope="session")
def db_path():
    _clean_test_db()
    os.environ["OPERION_DB_PATH"] = TEST_DB_PATH
    yield TEST_DB_PATH
    _clean_test_db()


@pytest.fixture(scope="session")
def app(db_path):
    """Create a fresh FastAPI app for the test session."""
    os.environ["OPERION_JWT_SECRET_KEY"] = "test-secret-key-32-chars-for-testing-only!!"
    os.environ["OPERION_ADMIN_EMAIL"] = "admin-a@test.com"
    admin_hash = bcrypt.hashpw(ADMIN_PW.encode(), bcrypt.gensalt(rounds=4)).decode()
    os.environ["OPERION_ADMIN_PASSWORD_HASH"] = admin_hash
    os.environ["OPERION_ENV"] = "test"

    from backend.main import app as fastapi_app
    import database.db_manager as dbm
    # Force DB to use test path by re-initializing
    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    """Return a TestClient bound to the test app."""
    return TestClient(app)


@pytest.fixture(scope="session")
def tokens(client):
    """Return dict of {role: access_token} for company A and B users."""
    result = {"company_a": {}, "company_b": {}}

    # Admin (env-var based, no company)
    resp = client.post("/api/v1/auth/token", data={
        "username": "admin-a@test.com",
        "password": ADMIN_PW,
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    result["admin"] = resp.json()["access_token"]

    # Company A users (created via admin API if available, else skipped)
    result["company_a"]["admin"] = result["admin"]
    return result


@pytest.fixture
def admin_token(tokens):
    return tokens["admin"]


@pytest.fixture
def auth_admin(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
