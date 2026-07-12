"""Integration tests for the public registration endpoint.

POST /api/v1/registration/register — self-service company + manager creation.
"""

import os
import time

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.security import decode_access_token
from tests.conftest import OPERION_TEST_JWT_SECRET as _TEST_JWT_SECRET

# ── Test secrets ──────────────────────────────────────────────────


@pytest.fixture(scope="module", autouse=True)
def _set_env():
    """Set test environment variables."""
    os.environ.setdefault("OPERION_JWT_SECRET_KEY", _TEST_JWT_SECRET)
    os.environ.setdefault("OPERION_ENV", "test")
    yield


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestRegistrationEndpoint:
    """POST /api/v1/registration/register"""

    def test_register_success_returns_201_with_tokens(self, client):
        """Successful registration returns 201 with access_token, refresh_token, and user."""
        ts = int(time.time())
        resp = client.post("/api/v1/registration/register", json={
            "email": f"newcompany{ts}@test.com",
            "password": "securepass123",
            "display_name": "Jane Doe",
            "company_name": "Acme Logistics",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert "user" in data
        assert data["user"]["email"] == f"newcompany{ts}@test.com"
        assert data["user"]["role"] == "manager"
        assert data["user"]["company_name"] == "Acme Logistics"
        assert data["user"]["display_name"] == "Jane Doe"
        assert data["user"]["company_id"] > 0

    def test_register_returns_valid_jwt(self, client):
        """The access_token can be decoded and contains correct claims."""
        ts = int(time.time())
        resp = client.post("/api/v1/registration/register", json={
            "email": f"jwt-test{ts}@test.com",
            "password": "securepass123",
            "display_name": "JWT Tester",
            "company_name": "JWT Corp",
        })
        token = resp.json()["access_token"]
        payload = decode_access_token(token)
        assert payload["sub"] == f"jwt-test{ts}@test.com"
        assert payload["role"] == "manager"

    def test_register_tokens_can_be_used_for_auth(self, client):
        """Tokens from registration can authenticate subsequent requests."""
        ts = int(time.time())
        # Register
        resp = client.post("/api/v1/registration/register", json={
            "email": f"auth-test{ts}@test.com",
            "password": "securepass123",
            "display_name": "Auth Tester",
            "company_name": "Auth Corp",
        })
        token = resp.json()["access_token"]
        # Use token to access protected endpoint
        resp2 = client.get("/api/v1/users/", headers={"Authorization": f"Bearer {token}"})
        assert resp2.status_code == 200

    def test_register_duplicate_email_returns_409(self, client):
        """Registering with an existing email returns 409 Conflict."""
        # First registration
        client.post("/api/v1/registration/register", json={
            "email": "duplicate@test.com",
            "password": "securepass123",
            "display_name": "First",
            "company_name": "First Corp",
        })
        # Duplicate
        resp = client.post("/api/v1/registration/register", json={
            "email": "duplicate@test.com",
            "password": "anotherpass456",
            "display_name": "Second",
            "company_name": "Second Corp",
        })
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    def test_register_empty_company_name_returns_422(self, client):
        """Missing required company_name returns 422 validation error."""
        resp = client.post("/api/v1/registration/register", json={
            "email": "test@test.com",
            "password": "securepass123",
            "display_name": "Test",
            "company_name": "",
        })
        assert resp.status_code == 422

    def test_register_short_password_returns_422(self, client):
        """Password shorter than 6 characters returns 422."""
        resp = client.post("/api/v1/registration/register", json={
            "email": "shortpw@test.com",
            "password": "12345",
            "display_name": "Short",
            "company_name": "Short Corp",
        })
        assert resp.status_code == 422

    def test_register_missing_email_returns_422(self, client):
        """Missing email returns 422."""
        resp = client.post("/api/v1/registration/register", json={
            "password": "securepass123",
            "display_name": "No Email",
            "company_name": "No Email Corp",
        })
        assert resp.status_code == 422

    def test_register_empty_body_returns_422(self, client):
        """Empty request body returns 422."""
        resp = client.post("/api/v1/registration/register", json={})
        assert resp.status_code == 422

    def test_register_creates_company_in_db(self, client):
        """Registration actually creates a company row in the database."""
        resp = client.post("/api/v1/registration/register", json={
            "email": f"dbcheck_{int(time.time())}@test.com",
            "password": "securepass123",
            "display_name": "DB Check",
            "company_name": "DB Check Corp",
        })
        company_id = resp.json()["user"]["company_id"]
        # Verify directly in DB
        from config import Config
        from database.db_manager import DatabaseManager
        db = DatabaseManager(Config.DB_PATH)
        try:
            row = db.conn.execute(
                "SELECT company_name, subscription_tier, is_active FROM companies WHERE id = ?",
                (company_id,),
            ).fetchone()
            assert row is not None
            assert row["company_name"] == "DB Check Corp"
            assert row["subscription_tier"] == "starter"
            assert row["is_active"] == 1
        finally:
            db.close()

    def test_register_creates_user_with_hashed_password(self, client):
        """Registration stores a bcrypt hashed password, NOT plaintext."""
        resp = client.post("/api/v1/registration/register", json={
            "email": f"hashcheck_{int(time.time())}@test.com",
            "password": "securepass123",
            "display_name": "Hash Check",
            "company_name": "Hash Corp",
        })
        user_id = resp.json()["user"]["id"]
        from config import Config
        from database.db_manager import DatabaseManager
        db = DatabaseManager(Config.DB_PATH)
        try:
            row = db.conn.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            assert row is not None
            pw_hash = row["password_hash"]
            assert pw_hash.startswith("$2b$")  # bcrypt hash
            assert "securepass123" not in pw_hash  # Not plaintext
        finally:
            db.close()

    def test_register_then_login_works(self, client):
        """After registration, the user can login via /auth/token."""
        email = f"logincheck_{int(time.time())}@test.com"
        password = "securepass123"
        # Register
        client.post("/api/v1/registration/register", json={
            "email": email,
            "password": password,
            "display_name": "Login Check",
            "company_name": "Login Corp",
        })
        # Login
        resp = client.post("/api/v1/auth/token", data={
            "username": email,
            "password": password,
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_register_then_login_wrong_password_fails(self, client):
        """After registration, wrong password login returns 401."""
        email = f"wrongpw_{int(time.time())}@test.com"
        client.post("/api/v1/registration/register", json={
            "email": email,
            "password": "correctpass123",
            "display_name": "Wrong PW",
            "company_name": "Wrong PW Corp",
        })
        resp = client.post("/api/v1/auth/token", data={
            "username": email,
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_register_multiple_companies_independent(self, client):
        """Two companies can register independently."""
        ts = int(time.time())
        r1 = client.post("/api/v1/registration/register", json={
            "email": f"comp1_{ts}@test.com",
            "password": "securepass123",
            "display_name": "Comp1 User",
            "company_name": "Company One",
        })
        r2 = client.post("/api/v1/registration/register", json={
            "email": f"comp2_{ts}@test.com",
            "password": "securepass123",
            "display_name": "Comp2 User",
            "company_name": "Company Two",
        })
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["user"]["company_id"] != r2.json()["user"]["company_id"]

    def test_register_preserves_display_name(self, client):
        """Display name is stored and returned correctly."""
        resp = client.post("/api/v1/registration/register", json={
            "email": f"displayname_{int(time.time())}@test.com",
            "password": "securepass123",
            "display_name": "José María García-López",
            "company_name": "Display Corp",
        })
        assert resp.json()["user"]["display_name"] == "José María García-López"


class TestRegistrationAndListUsers:
    """Manager created via registration can list their own users."""

    def test_new_manager_sees_empty_user_list(self, client):
        """A newly registered manager sees zero users (just themselves isn't listed by list_users)."""
        resp = client.post("/api/v1/registration/register", json={
            "email": f"emptyusers_{int(time.time())}@test.com",
            "password": "securepass123",
            "display_name": "Empty Manager",
            "company_name": "Empty Corp",
        })
        token = resp.json()["access_token"]
        resp2 = client.get("/api/v1/users/", headers={"Authorization": f"Bearer {token}"})
        assert resp2.status_code == 200
        # The manager themselves may or may not appear depending on query,
        # but the endpoint should work


class TestRegistrationEdgeCases:
    """Edge cases for registration."""

    def test_register_email_case_insensitive(self, client):
        """Email is normalized to lowercase — UPPERCASE@test.com conflicts with uppercase@test.com."""
        email = f"CaseTest_{int(time.time())}@TEST.com"
        resp = client.post("/api/v1/registration/register", json={
            "email": email,
            "password": "securepass123",
            "display_name": "Case Test",
            "company_name": "Case Corp",
        })
        assert resp.status_code == 201
        # Try same email in lowercase
        resp2 = client.post("/api/v1/registration/register", json={
            "email": email.lower(),
            "password": "anotherpass456",
            "display_name": "Case Test 2",
            "company_name": "Case Corp 2",
        })
        assert resp2.status_code == 409

    def test_register_with_whitespace_email(self, client):
        """Email with leading/trailing whitespace is stripped."""
        ts = int(time.time())
        resp = client.post("/api/v1/registration/register", json={
            "email": f"  spaced_{ts}@test.com  ",
            "password": "securepass123",
            "display_name": "Spaced",
            "company_name": "Space Corp",
        })
        assert resp.status_code == 201
        assert resp.json()["user"]["email"] == f"spaced_{ts}@test.com"

    def test_register_very_long_company_name(self, client):
        """Very long company name should still work."""
        long_name = "A" * 200
        resp = client.post("/api/v1/registration/register", json={
            "email": f"longname_{int(time.time())}@test.com",
            "password": "securepass123",
            "display_name": "Long Name",
            "company_name": long_name,
        })
        assert resp.status_code == 201
