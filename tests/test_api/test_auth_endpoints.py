"""Integration tests for the auth API endpoints (``/api/v1/auth``).

POST /token  — login
POST /logout — clear cookie
GET  /me    — current user info
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/auth"


class TestAuthTokenEndpoint:
    """POST /api/v1/auth/token"""

    def test_login_success_admin(self, app):
        """Valid admin login returns 200 with tokens (via env-var gateway)."""
        import os
        import bcrypt
        from tests.conftest import OPERION_TEST_JWT_SECRET
        os.environ.setdefault("OPERION_JWT_SECRET_KEY", OPERION_TEST_JWT_SECRET)
        os.environ["OPERION_ADMIN_EMAIL"] = "admin@test.com"
        # Use bcrypt directly instead of passlib
        pw_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt(rounds=4)).decode()
        os.environ["OPERION_ADMIN_PASSWORD_HASH"] = pw_hash

        client = TestClient(app)
        resp = client.post(f"{BASE}/token", data={
            "username": "admin@test.com",
            "password": "admin123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

        for k in ("OPERION_ADMIN_EMAIL", "OPERION_ADMIN_PASSWORD_HASH",
                  "OPERION_JWT_SECRET_KEY"):
            os.environ.pop(k, None)

    def _login_admin(self, app, remember=None):
        """Perform an admin-gateway login (env-var based, zero DB).

        Returns the raw TestClient response so callers can inspect the
        refresh_token cookie.  Cleans up the env vars it sets.
        """
        import os
        import bcrypt
        from tests.conftest import OPERION_TEST_JWT_SECRET
        os.environ.setdefault("OPERION_JWT_SECRET_KEY", OPERION_TEST_JWT_SECRET)
        os.environ["OPERION_ADMIN_EMAIL"] = "admin@test.com"
        pw_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt(rounds=4)).decode()
        os.environ["OPERION_ADMIN_PASSWORD_HASH"] = pw_hash

        data = {"username": "admin@test.com", "password": "admin123"}
        if remember is not None:
            data["remember"] = remember

        try:
            resp = TestClient(app).post(f"{BASE}/token", data=data)
        finally:
            for k in ("OPERION_ADMIN_EMAIL", "OPERION_ADMIN_PASSWORD_HASH",
                      "OPERION_JWT_SECRET_KEY"):
                os.environ.pop(k, None)
        return resp

    def test_login_remember_true_sets_30_day_cookie(self, app):
        """remember=true → refresh cookie max-age ≈ 30 days (2_592_000s)."""
        resp = self._login_admin(app, remember="true")
        assert resp.status_code == 200
        set_cookie = resp.headers.get("set-cookie", "")
        assert "refresh_token=" in set_cookie
        assert "Max-Age=2592000" in set_cookie

    def test_login_remember_false_sets_7_day_cookie(self, app):
        """remember=false → refresh cookie max-age ≈ 7 days (604_800s)."""
        resp = self._login_admin(app, remember="false")
        assert resp.status_code == 200
        set_cookie = resp.headers.get("set-cookie", "")
        assert "refresh_token=" in set_cookie
        assert "Max-Age=604800" in set_cookie

    def test_login_default_remember_sets_session_cookie(self, app):
        """No remember field → session cookie (max-age ≈ 7 days), like False."""
        resp = self._login_admin(app)
        assert resp.status_code == 200
        set_cookie = resp.headers.get("set-cookie", "")
        assert "refresh_token=" in set_cookie
        assert "Max-Age=604800" in set_cookie

    def test_login_wrong_password_returns_401(self, app):
        """Wrong password returns 401."""
        import os
        from tests.conftest import OPERION_TEST_JWT_SECRET
        os.environ.setdefault("OPERION_JWT_SECRET_KEY", OPERION_TEST_JWT_SECRET)
        os.environ["OPERION_ADMIN_EMAIL"] = "admin@test.com"
        os.environ["OPERION_ADMIN_PASSWORD_HASH"] = "$2b$12$dummyhashdummyhashdummyhashdummyhashdummy"
        from backend.api.v1.auth import _failed_attempts
        _failed_attempts.clear()

        client = TestClient(app)
        resp = client.post(f"{BASE}/token", data={
            "username": "admin@test.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

        for k in ("OPERION_ADMIN_EMAIL", "OPERION_ADMIN_PASSWORD_HASH",
                  "OPERION_JWT_SECRET_KEY"):
            os.environ.pop(k, None)

    def test_login_unknown_user_returns_401(self, app):
        """Unknown user returns 401."""
        import os
        from tests.conftest import OPERION_TEST_JWT_SECRET
        os.environ.setdefault("OPERION_JWT_SECRET_KEY", OPERION_TEST_JWT_SECRET)
        os.environ["OPERION_ADMIN_EMAIL"] = "realadmin@test.com"
        os.environ["OPERION_ADMIN_PASSWORD_HASH"] = "$2b$12$dummyhash"
        from backend.api.v1.auth import _failed_attempts
        _failed_attempts.clear()

        client = TestClient(app)
        resp = client.post(f"{BASE}/token", data={
            "username": "unknown@test.com",
            "password": "somepass",
        })
        assert resp.status_code == 401

        for k in ("OPERION_ADMIN_EMAIL", "OPERION_ADMIN_PASSWORD_HASH",
                  "OPERION_JWT_SECRET_KEY"):
            os.environ.pop(k, None)

    def test_login_missing_fields_returns_422(self, app):
        """Missing form fields returns 422."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/token", data={})
        assert resp.status_code == 422

    def test_login_missing_password_returns_422(self, app):
        """Missing password returns 422."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/token", data={"username": "user@test.com"})
        assert resp.status_code == 422


class TestAuthLogoutEndpoint:
    """POST /api/v1/auth/logout"""

    def test_logout_clears_cookie(self, app):
        """Logout clears the refresh_token cookie."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/logout", json={"refresh_token": "some-token"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        # Verify Set-Cookie header clears the cookie
        set_cookie = resp.headers.get("set-cookie", "")
        assert "refresh_token=" in set_cookie
        assert "Max-Age=0" in set_cookie or "expires=" in set_cookie

    def test_logout_without_body_still_succeeds(self, app):
        """Logout succeeds even without a stored refresh token."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/logout", json={"refresh_token": "dummy"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAuthMeEndpoint:
    """GET /api/v1/auth/me — requires authentication."""

    def test_me_without_token_returns_401(self, app):
        """No token returns 401."""
        client = TestClient(app)
        resp = client.get(f"{BASE}/me")
        assert resp.status_code == 401

    def test_me_with_mock_token_returns_user(self, client_with_mocks):
        """Authenticated request returns user info."""
        client, mocks = client_with_mocks
        resp = client.get(f"{BASE}/me")
        assert resp.status_code == 200
        data = resp.json()
        # Response wraps user info under "user" key
        user = data.get("user", data)
        assert user["email"] == "test@test.com"
        assert user["role"] == "admin"


# ═══════════════════════════════════════════════════════════════════════
# MFA login challenge (Gate-34 A1/A3b) — real DB users
# ═══════════════════════════════════════════════════════════════════════


def _totp_now(secret: str) -> str:
    """RFC 6238 TOTP code for *secret* at the current 30-second step."""
    import base64
    import hashlib
    import hmac
    import struct
    import time

    key = base64.b32decode(secret.upper().encode("ascii"), casefold=True)
    counter = int(time.time() // 30)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    trunc_offset = digest[-1] & 0x0F
    trunc = struct.unpack(">I", digest[trunc_offset: trunc_offset + 4])[0] & 0x7FFFFFFF
    return f"{trunc % 1_000_000:06d}"


def _mfa_enc_key() -> str:
    """Encryption key used by encrypt_at_rest for seeded TOTP secrets."""
    from backend.config import get_settings

    s = get_settings()
    return s.mfa_secret_encryption_key or s.jwt_secret_key


class TestLoginMfaIntegration:
    """Real-DB mid-login MFA challenge flow (frontend-pinned shape)."""

    MFA_EMAIL = "mfa-int@test.com"
    PLAIN_EMAIL = "plain-int@test.com"
    PASSWORD = "mfa-int-pw"

    @pytest.fixture(autouse=True)
    def _mfa_login_db(self):
        """Seed a throwaway SQLite DB with one MFA + one plain user."""
        import bcrypt
        import tempfile
        import uuid
        from config import Config
        from database.db_manager import DatabaseManager
        from backend.api.v1 import auth as auth_module
        from backend.security import encrypt_at_rest, generate_totp_secret

        self._db_path = os.path.join(
            tempfile.gettempdir(), f"test_login_mfa_{uuid.uuid4().hex[:12]}.db",
        )
        os.environ["OPERION_DB_PATH"] = self._db_path
        Config.DB_PATH = self._db_path
        import backend.dependencies as deps
        deps._db_instance = None

        self._secret = generate_totp_secret()
        h = bcrypt.hashpw(self.PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
        db = DatabaseManager(self._db_path)
        db.conn.execute(
            "INSERT OR REPLACE INTO companies (id, company_name, is_active) VALUES (1, 'MfaCo', 1)"
        )
        db.conn.execute(
            "INSERT INTO users (id, email, password_hash, role, company_id, mfa_enabled, mfa_secret) "
            "VALUES (1, ?, ?, 'dispatcher', 1, 1, ?)",
            (self.MFA_EMAIL, h, encrypt_at_rest(self._secret, _mfa_enc_key())),
        )
        db.conn.execute(
            "INSERT INTO users (id, email, password_hash, role, company_id, mfa_enabled) "
            "VALUES (2, ?, ?, 'dispatcher', 1, 0)",
            (self.PLAIN_EMAIL, h),
        )
        db.conn.commit()
        db.close()
        auth_module._mfa_sessions.clear()
        auth_module._mfa_fail_counts.clear()
        auth_module._mfa_locks.clear()
        auth_module._failed_attempts.clear()
        yield

    def _login(self, client, email: str):
        return client.post(
            f"{BASE}/token", data={"username": email, "password": self.PASSWORD},
        )

    def test_mfa_login_returns_exact_challenge_shape(self, app):
        """MFA user -> {mfa_required, mfa_session_token, token_type} and nothing else."""
        client = TestClient(app)
        resp = self._login(client, self.MFA_EMAIL)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {"mfa_required", "mfa_session_token", "token_type"}
        assert body["mfa_required"] is True
        assert isinstance(body["mfa_session_token"], str) and len(body["mfa_session_token"]) > 20
        assert body["token_type"] == "bearer"

    def test_mfa_login_issues_no_tokens_pre_verify(self, app):
        """No access/refresh token and no refresh cookie before the 2FA."""
        client = TestClient(app)
        resp = self._login(client, self.MFA_EMAIL)
        body = resp.json()
        assert "access_token" not in body
        assert "refresh_token" not in body
        assert "expires_in" not in body
        assert "refresh_token=" not in resp.headers.get("set-cookie", "")

    def test_mfa_verify_completes_login_and_session_is_single_use(self, app):
        """Correct TOTP -> tokens; reusing the session token is rejected."""
        client = TestClient(app)
        challenge = self._login(client, self.MFA_EMAIL).json()
        verify = client.post(
            f"{BASE}/mfa/verify",
            json={
                "mfa_session_token": challenge["mfa_session_token"],
                "code": _totp_now(self._secret),
            },
        )
        assert verify.status_code == 200, verify.text
        body = verify.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        # F2: the MFA login recorded an auth_sessions row (session list/revoke).
        from database.db_manager import DatabaseManager

        _db = DatabaseManager(self._db_path)
        try:
            sessions = _db.conn.execute(
                "SELECT COUNT(*) FROM auth_sessions WHERE user_email = ?",
                (self.MFA_EMAIL,),
            ).fetchone()[0]
        finally:
            _db.close()
        assert sessions == 1, "MFA login should record an auth_sessions row (F2)"
        replay = client.post(
            f"{BASE}/mfa/verify",
            json={
                "mfa_session_token": challenge["mfa_session_token"],
                "code": _totp_now(self._secret),
            },
        )
        assert replay.status_code == 401, replay.text

    def test_non_mfa_user_login_has_no_challenge(self, app):
        """Plain user -> normal token response (no mfa_required key)."""
        client = TestClient(app)
        resp = self._login(client, self.PLAIN_EMAIL)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert "mfa_required" not in body
        assert "mfa_session_token" not in body

    def test_admin_gateway_bypasses_mfa(self, app):
        """Env-var admin login issues tokens directly (no MFA challenge)."""
        import bcrypt
        from tests.conftest import OPERION_TEST_JWT_SECRET

        os.environ.setdefault("OPERION_JWT_SECRET_KEY", OPERION_TEST_JWT_SECRET)
        os.environ["OPERION_ADMIN_EMAIL"] = "admin-int@test.com"
        os.environ["OPERION_ADMIN_PASSWORD_HASH"] = bcrypt.hashpw(
            b"admin123", bcrypt.gensalt(rounds=4)
        ).decode()
        try:
            client = TestClient(app)
            resp = client.post(f"{BASE}/token", data={
                "username": "admin-int@test.com", "password": "admin123",
            })
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert "access_token" in body
            assert "mfa_required" not in body
        finally:
            for k in ("OPERION_ADMIN_EMAIL", "OPERION_ADMIN_PASSWORD_HASH",
                      "OPERION_JWT_SECRET_KEY"):
                os.environ.pop(k, None)
