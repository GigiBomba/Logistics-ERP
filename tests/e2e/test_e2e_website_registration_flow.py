"""E2E: Full website registration → authentication → user management flow.

Simulates the real Operion website (React frontend) communicating with
the FastAPI backend. Tests the complete integration chain that was
previously broken (mocked auth).
"""

import os

# Speed up bcrypt for tests (default rounds=12 is too slow).
# Must be set before BackendSettings is first constructed.
os.environ.setdefault("OPERION_BCRYPT_ROUNDS", "4")

import pytest
from fastapi.testclient import TestClient

# Make fixtures from tests/security/conftest.py discoverable
pytest_plugins = ("tests.security.conftest",)

from tests.security.conftest import get_db, verify_db_company_id


class TestWebsiteRegistrationE2E:
    """Simulate a user visiting operion.io and signing up."""

    def test_full_registration_flow(self, client):
        """Complete flow: register → get tokens → access protected routes.

        This is the exact flow the React website executes after the bug fix:
        1. User fills registration form (email, password, name, company)
        2. POST /api/v1/registration/register → returns tokens + user
        3. Tokens stored in localStorage (simulated)
        4. User redirected to dashboard (simulated by accessing protected routes)
        5. User can access their company's resources
        """
        # ── Step 1: Website registration ────────────────────────────────
        resp = client.post("/api/v1/registration/register", json={
            "email": "website-user@test.com",
            "password": "website-pass-123",
            "display_name": "Website User",
            "company_name": "Website Logistics SRL",
        })
        assert resp.status_code == 201, f"Registration failed: {resp.text}"
        data = resp.json()

        # Extract tokens (what the React auth-provider stores in localStorage)
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        user = data["user"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Verify user object (what the React auth-provider stores)
        assert user["email"] == "website-user@test.com"
        assert user["role"] == "manager"
        assert user["display_name"] == "Website User"
        assert user["company_name"] == "Website Logistics SRL"
        assert user["company_id"] > 0
        company_id = user["company_id"]

        # ── Step 2: Verify database has the company ─────────────────────
        db = get_db()
        try:
            company = db.conn.execute(
                "SELECT * FROM companies WHERE id = ?", (company_id,)
            ).fetchone()
            assert company is not None
            assert company["company_name"] == "Website Logistics SRL"
            assert company["subscription_tier"] == "starter"
            assert company["is_active"] == 1

            # Verify user row
            db_user = db.conn.execute(
                "SELECT * FROM users WHERE email = ?", ("website-user@test.com",)
            ).fetchone()
            assert db_user is not None
            assert db_user["role"] == "manager"
            assert db_user["company_id"] == company_id
            assert db_user["is_active"] == 1
            assert db_user["password_hash"].startswith("$2b$")  # bcrypt
        finally:
            db.close()

        # ── Step 3: User accesses protected dashboard routes ────────────
        # Simulate the React app calling these endpoints with the stored token

        # List users in their company
        resp = client.get("/api/v1/users/", headers=headers)
        assert resp.status_code == 200
        users_data = resp.json()
        assert "items" in users_data

        # Health check (public, no auth needed — but verifies API is up)
        resp = client.get("/api/v1/health/", headers=headers)
        assert resp.status_code == 200

        # ── Step 4: Manager creates a dispatcher user ───────────────────
        resp = client.post("/api/v1/users/", json={
            "email": "dispatcher@website-logistics.com",
            "password": "dispatch-pass-456",
            "role": "dispatcher",
            "display_name": "Alice Dispatcher",
        }, headers=headers)
        assert resp.status_code == 201
        dispatcher_id = resp.json()["id"]

        # Verify dispatcher is in the same company
        db = get_db()
        try:
            dispatcher = db.conn.execute(
                "SELECT * FROM users WHERE id = ?", (dispatcher_id,)
            ).fetchone()
            assert dispatcher is not None
            assert dispatcher["role"] == "dispatcher"
            assert dispatcher["company_id"] == company_id
        finally:
            db.close()

        # ── Step 5: List users now includes the dispatcher ──────────────
        resp = client.get("/api/v1/users/", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        emails = [u["email"] for u in items]
        assert "dispatcher@website-logistics.com" in emails

        # ── Step 6: Dispatcher can login independently ──────────────────
        resp = client.post("/api/v1/auth/token", data={
            "username": "dispatcher@website-logistics.com",
            "password": "dispatch-pass-456",
        })
        assert resp.status_code == 200
        dispatcher_token = resp.json()["access_token"]
        dispatcher_headers = {"Authorization": f"Bearer {dispatcher_token}"}

        # Dispatcher CANNOT access manager-only user list (RBAC boundary)
        resp = client.get("/api/v1/users/", headers=dispatcher_headers)
        assert resp.status_code == 403

        # ── Step 7: Manager deactivates the dispatcher ──────────────────
        resp = client.delete(f"/api/v1/users/{dispatcher_id}", headers=headers)
        assert resp.status_code == 200

        # Dispatcher can no longer login
        resp = client.post("/api/v1/auth/token", data={
            "username": "dispatcher@website-logistics.com",
            "password": "dispatch-pass-456",
        })
        assert resp.status_code == 401

    def test_token_refresh_keeps_session_alive(self, client):
        """The website's auth-provider refresh flow works correctly.

        Simulates: access token expires → React calls /auth/refresh
        with stored refresh_token → gets new tokens → updates localStorage.
        """
        # Register
        resp = client.post("/api/v1/registration/register", json={
            "email": "refresh-e2e@test.com",
            "password": "securepass123",
            "display_name": "Refresh E2E",
            "company_name": "Refresh E2E Corp",
        })
        refresh_token = resp.json()["refresh_token"]
        old_access = resp.json()["access_token"]

        # Simulate token refresh (what auth-provider does on 401)
        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        new_access = resp.json()["access_token"]
        new_refresh = resp.json()["refresh_token"]

        # New tokens are different (rotation)
        assert new_access != old_access
        assert new_refresh != refresh_token

        # New access token works
        resp = client.get("/api/v1/users/", headers={
            "Authorization": f"Bearer {new_access}",
        })
        assert resp.status_code == 200

        # Old refresh token is now revoked
        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 401

    def test_logout_ends_session(self, client):
        """The website's logout flow properly revokes tokens.

        Simulates: user clicks logout → React calls /auth/logout with
        refresh_token → clears localStorage → refresh token is revoked.
        """
        # Register and get tokens
        resp = client.post("/api/v1/registration/register", json={
            "email": "logout-e2e@test.com",
            "password": "securepass123",
            "display_name": "Logout E2E",
            "company_name": "Logout E2E Corp",
        })
        refresh_token = resp.json()["refresh_token"]

        # Logout
        resp = client.post("/api/v1/auth/logout", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200

        # Refresh token is revoked
        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 401

    def test_password_reset_full_cycle(self, client):
        """The website's forgot-password → reset-password flow works.

        Simulates: user clicks "Forgot password" → enters email →
        receives reset link (token) → enters new password → logs in.
        """
        from backend.api.v1.auth import _reset_tokens

        # Register a user
        email = "pwreset-e2e@test.com"
        client.post("/api/v1/registration/register", json={
            "email": email,
            "password": "original-pass",
            "display_name": "PW Reset E2E",
            "company_name": "PW Reset Corp",
        })

        # Step 1: Forgot password
        resp = client.post("/api/v1/auth/forgot-password", json={
            "email": email,
        })
        assert resp.status_code == 200

        # Step 2: Extract token (in production this comes via email link)
        token = None
        for t, data in _reset_tokens.items():
            if data["email"] == email:
                token = t
                break
        assert token is not None, "Reset token not found in _reset_tokens store"

        # Step 3: Reset password
        resp = client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": "brand-new-pass-999",
        })
        assert resp.status_code == 200

        # Step 4: Login with new password
        resp = client.post("/api/v1/auth/token", data={
            "username": email,
            "password": "brand-new-pass-999",
        })
        assert resp.status_code == 200

        # Step 5: Old password fails
        resp = client.post("/api/v1/auth/token", data={
            "username": email,
            "password": "original-pass",
        })
        assert resp.status_code == 401

    def test_multi_tenant_isolation(self, client):
        """Companies registered through the website are isolated.

        Company A's manager cannot see Company B's users.
        """
        # Register Company A
        r1 = client.post("/api/v1/registration/register", json={
            "email": "company-a@test.com",
            "password": "securepass123",
            "display_name": "Manager A",
            "company_name": "Company Alpha",
        })
        token_a = r1.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Register Company B
        r2 = client.post("/api/v1/registration/register", json={
            "email": "company-b@test.com",
            "password": "securepass123",
            "display_name": "Manager B",
            "company_name": "Company Beta",
        })
        token_b = r2.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Company A creates a user
        client.post("/api/v1/users/", json={
            "email": "dispatcher-a@company-a.com",
            "password": "pass123456",
            "role": "dispatcher",
            "display_name": "Dispatcher A",
        }, headers=headers_a)

        # Company B creates a user
        client.post("/api/v1/users/", json={
            "email": "dispatcher-b@company-b.com",
            "password": "pass123456",
            "role": "dispatcher",
            "display_name": "Dispatcher B",
        }, headers=headers_b)

        # Company A only sees their users
        resp_a = client.get("/api/v1/users/", headers=headers_a)
        emails_a = [u["email"] for u in resp_a.json()["items"]]
        assert "dispatcher-a@company-a.com" in emails_a
        assert "dispatcher-b@company-b.com" not in emails_a

        # Company B only sees their users
        resp_b = client.get("/api/v1/users/", headers=headers_b)
        emails_b = [u["email"] for u in resp_b.json()["items"]]
        assert "dispatcher-b@company-b.com" in emails_b
        assert "dispatcher-a@company-a.com" not in emails_b

    def test_brute_force_lockout_on_login(self, client):
        """Brute-force protection on login via website.

        Simulates an attacker trying repeated passwords from the website.
        """
        # Register a user
        email = "lockout-e2e@test.com"
        client.post("/api/v1/registration/register", json={
            "email": email,
            "password": "real-password",
            "display_name": "Lockout E2E",
            "company_name": "Lockout Corp",
        })

        # 5 failed attempts
        for _ in range(5):
            resp = client.post("/api/v1/auth/token", data={
                "username": email,
                "password": "wrong-password",
            })
            assert resp.status_code == 401

        # 6th attempt is locked out
        resp = client.post("/api/v1/auth/token", data={
            "username": email,
            "password": "wrong-password",
        })
        assert resp.status_code == 429
        assert "Too many login attempts" in resp.json()["detail"]

        # Even correct password is blocked during lockout
        resp = client.post("/api/v1/auth/token", data={
            "username": email,
            "password": "real-password",
        })
        assert resp.status_code == 429


class TestWebsiteAPIIntegrity:
    """Verify data integrity between website and database."""

    def test_registration_data_persists(self, client):
        """Registered user data persists and can be retrieved after new connections."""
        email = "persist-e2e@test.com"
        resp = client.post("/api/v1/registration/register", json={
            "email": email,
            "password": "securepass123",
            "display_name": "Persist Test",
            "company_name": "Persist Corp",
        })
        company_id = resp.json()["user"]["company_id"]

        # Verify data directly from DB (simulating a fresh connection)
        db = get_db()
        try:
            user = db.conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
            assert user is not None
            assert user["is_active"] == 1

            company = db.conn.execute(
                "SELECT * FROM companies WHERE id = ?", (company_id,)
            ).fetchone()
            assert company is not None
            assert company["is_active"] == 1
        finally:
            db.close()

    def test_password_not_stored_in_plaintext(self, client):
        """Passwords are never stored as plaintext in the database."""
        email = "nopass-e2e@test.com"
        password = "securepass123"
        client.post("/api/v1/registration/register", json={
            "email": email,
            "password": password,
            "display_name": "No Plaintext",
            "company_name": "Secure Corp",
        })

        db = get_db()
        try:
            user = db.conn.execute(
                "SELECT password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()
            pw_hash = user["password_hash"]
            assert password not in pw_hash
            assert pw_hash.startswith("$2b$")
        finally:
            db.close()
