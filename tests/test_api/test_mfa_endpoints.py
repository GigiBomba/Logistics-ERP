"""Integration tests for the MFA (TOTP two-factor) endpoints.

Covers the Gate-34 A1/A3a/A3b contract:

- POST /api/v1/auth/mfa/enroll      (auth)   start enrollment -> secret/uri/QR
- POST /api/v1/auth/mfa/confirm     (auth)   verify code -> enable + backup codes
- POST /api/v1/auth/mfa/disable     (auth)   disable after password re-auth
- POST /api/v1/auth/mfa/verify      (public) complete login with TOTP code
- POST /api/v1/auth/mfa/backup-code (public) complete login with a recovery code
- GET  /api/v1/auth/me/mfa-status   (auth)   mfa_enabled status

Each test gets a throwaway SQLite DB seeded with a non-MFA user (id 1) and an
MFA-enabled user (id 2) whose TOTP secret is known to the test.  Response
shapes match the pinned frontend contract (website/src/api/endpoints.ts).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import tempfile
import time
import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient

# Env setup BEFORE backend imports (mirrors tests/test_api/test_mobile_mutation.py)
_TEST_DB = os.path.join(tempfile.gettempdir(), f"test_mfa_{uuid.uuid4().hex[:12]}.db")
os.environ.setdefault("OPERION_DB_PATH", _TEST_DB)
os.environ["OPERION_DB_ENGINE"] = "sqlite"
os.environ["OPERION_ENV"] = "test"
os.environ["OPERION_JWT_SECRET_KEY"] = "test-jwt-secret-key-for-testing!!"

from config import Config  # noqa: E402

Config.DB_PATH = _TEST_DB

import backend.dependencies as deps  # noqa: E402
from backend.api.v1 import auth as auth_module  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.security import create_access_token, encrypt_at_rest, generate_totp_secret  # noqa: E402

MFA_EMAIL = "mfa@test.com"
PLAIN_EMAIL = "plain@test.com"
PASSWORD = "mfa-test-pw"
MFA_SECRET = generate_totp_secret()  # seeded for the MFA-enabled user


def _enc_key() -> str:
    s = get_settings()
    return s.mfa_secret_encryption_key or s.jwt_secret_key


def _totp(secret: str, offset: int = 0) -> str:
    """RFC 6238 TOTP code for *secret* at the current step + *offset*."""
    key = base64.b32decode(secret.upper().encode("ascii"), casefold=True)
    counter = int(time.time() // 30) + offset
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    trunc_offset = digest[-1] & 0x0F
    trunc = struct.unpack(">I", digest[trunc_offset: trunc_offset + 4])[0] & 0x7FFFFFFF
    return f"{trunc % 1_000_000:06d}"


def _token_for(email: str) -> str:
    """Return a real JWT for *email* (validated by get_current_user)."""
    return create_access_token(data={"sub": email, "role": "dispatcher"})


def _seed_backup_code(db, user_id: int, code: str) -> None:
    db.conn.execute(
        "INSERT INTO mfa_backup_codes (user_id, code_hash) VALUES (?, ?)",
        (user_id, bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")),
    )
    db.conn.commit()


@pytest.fixture(autouse=True)
def seeded_db():
    """Fresh DB with a non-MFA + an MFA-enabled user; resets shared state."""
    Config.DB_PATH = _TEST_DB
    deps._db_instance = None
    db = deps.init_db()
    db.conn.execute("DELETE FROM mfa_backup_codes")
    db.conn.execute("DELETE FROM auth_sessions")
    db.conn.execute("DELETE FROM users")
    db.conn.execute(
        "INSERT OR REPLACE INTO companies (id, company_name, is_active) VALUES (1, 'MfaCo', 1)"
    )
    h = bcrypt.hashpw(PASSWORD.encode("utf-8"), bcrypt.gensalt(rounds=4)).decode("utf-8")
    db.conn.execute(
        "INSERT INTO users (id, email, password_hash, role, company_id, mfa_enabled, mfa_secret) "
        "VALUES (1, ?, ?, 'dispatcher', 1, 0, NULL)",
        (PLAIN_EMAIL, h),
    )
    db.conn.execute(
        "INSERT INTO users (id, email, password_hash, role, company_id, mfa_enabled, mfa_secret) "
        "VALUES (2, ?, ?, 'dispatcher', 1, 1, ?)",
        (MFA_EMAIL, h, encrypt_at_rest(MFA_SECRET, _enc_key())),
    )
    db.conn.commit()
    auth_module._mfa_sessions.clear()
    auth_module._mfa_fail_counts.clear()
    auth_module._mfa_locks.clear()
    auth_module._failed_attempts.clear()
    yield
    auth_module._mfa_sessions.clear()
    auth_module._mfa_fail_counts.clear()
    auth_module._mfa_locks.clear()


@pytest.fixture
def app(seeded_db):
    from fastapi import FastAPI
    from backend.api.v1.router import api_v1_router

    app = FastAPI()
    app.include_router(api_v1_router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def _login_mfa(client) -> dict:
    resp = client.post("/api/v1/auth/token", data={"username": MFA_EMAIL, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _auth_hdr(email: str) -> dict:
    return {"Authorization": f"Bearer {_token_for(email)}"}


# ═══════════════════════════════════════════════════════════════════════
# Enroll
# ═══════════════════════════════════════════════════════════════════════


class TestEnroll:
    def test_enroll_returns_pinned_contract(self, client):
        resp = client.post("/api/v1/auth/mfa/enroll", json={}, headers=_auth_hdr(PLAIN_EMAIL))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {"secret", "otpauth_uri", "qr_payload"}
        assert len(body["secret"]) == 32
        assert body["otpauth_uri"].startswith("otpauth://totp/Operion:")
        assert "algorithm=SHA1" in body["otpauth_uri"]
        assert "digits=6" in body["otpauth_uri"]
        assert "period=30" in body["otpauth_uri"]
        assert body["qr_payload"].startswith("data:image/png;base64,")

    def test_enroll_admin_rejected(self, app):
        from backend.dependencies_security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: {
            "id": 0, "email": "admin@test.com", "role": "admin",
            "is_admin": True, "company_id": 0,
        }
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/mfa/enroll", json={})
        assert resp.status_code == 400, resp.text

    def test_enroll_already_enabled_returns_409(self, client):
        resp = client.post("/api/v1/auth/mfa/enroll", json={}, headers=_auth_hdr(MFA_EMAIL))
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["error_code"] == "auth/mfa-already-enabled"


# ═══════════════════════════════════════════════════════════════════════
# Confirm
# ═══════════════════════════════════════════════════════════════════════


class TestConfirm:
    def test_confirm_enables_mfa_and_returns_backup_codes(self, client):
        enroll = client.post(
            "/api/v1/auth/mfa/enroll", json={}, headers=_auth_hdr(PLAIN_EMAIL)
        ).json()
        code = _totp(enroll["secret"])
        resp = client.post(
            "/api/v1/auth/mfa/confirm", json={"code": code}, headers=_auth_hdr(PLAIN_EMAIL)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {"mfa_enabled", "backup_codes"}
        assert body["mfa_enabled"] is True
        assert len(body["backup_codes"]) == 10
        assert all(
            set(c) <= set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
            for c in body["backup_codes"]
        )

    def test_confirm_wrong_code_returns_400(self, client):
        client.post("/api/v1/auth/mfa/enroll", json={}, headers=_auth_hdr(PLAIN_EMAIL))
        resp = client.post(
            "/api/v1/auth/mfa/confirm", json={"code": "000000"}, headers=_auth_hdr(PLAIN_EMAIL)
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"]["error_code"] == "auth/mfa-invalid-code"

    def test_confirm_without_enroll_returns_400(self, client):
        resp = client.post(
            "/api/v1/auth/mfa/confirm", json={"code": "123456"}, headers=_auth_hdr(PLAIN_EMAIL)
        )
        assert resp.status_code == 400, resp.text

    def test_confirm_already_enabled_returns_409(self, client):
        resp = client.post(
            "/api/v1/auth/mfa/confirm", json={"code": "123456"}, headers=_auth_hdr(MFA_EMAIL)
        )
        assert resp.status_code == 409, resp.text


# ═══════════════════════════════════════════════════════════════════════
# Disable
# ═══════════════════════════════════════════════════════════════════════


class TestDisable:
    def _enable_plain(self, client):
        enroll = client.post(
            "/api/v1/auth/mfa/enroll", json={}, headers=_auth_hdr(PLAIN_EMAIL)
        ).json()
        client.post(
            "/api/v1/auth/mfa/confirm", json={"code": _totp(enroll["secret"])},
            headers=_auth_hdr(PLAIN_EMAIL),
        )

    def test_disable_with_correct_password(self, client):
        self._enable_plain(client)
        resp = client.post(
            "/api/v1/auth/mfa/disable", json={"password": PASSWORD}, headers=_auth_hdr(PLAIN_EMAIL)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"mfa_enabled": False}
        status = client.get("/api/v1/auth/me/mfa-status", headers=_auth_hdr(PLAIN_EMAIL)).json()
        assert status == {"mfa_enabled": False}

    def test_disable_with_wrong_password_returns_401(self, client):
        self._enable_plain(client)
        resp = client.post(
            "/api/v1/auth/mfa/disable", json={"password": "wrong-password"},
            headers=_auth_hdr(PLAIN_EMAIL),
        )
        assert resp.status_code == 401, resp.text

    def test_disable_admin_rejected(self, app):
        from backend.dependencies_security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: {
            "id": 0, "email": "admin@test.com", "role": "admin",
            "is_admin": True, "company_id": 0,
        }
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/mfa/disable", json={"password": "x"})
        assert resp.status_code == 400, resp.text


# ═══════════════════════════════════════════════════════════════════════
# Verify (public — completes the mid-login MFA flow)
# ═══════════════════════════════════════════════════════════════════════


class TestVerify:
    def test_verify_success_returns_tokens(self, client):
        """Valid TOTP -> access token in body; refresh token only in cookie."""
        challenge = _login_mfa(client)
        tok = challenge["mfa_session_token"]
        resp = client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_session_token": tok, "code": _totp(MFA_SECRET)},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" not in body  # cookie-only (A3b)
        assert body["token_type"] == "bearer"
        assert "expires_in" in body
        assert "refresh_token=" in resp.headers.get("set-cookie", "")

    def test_verify_records_auth_session(self, client):
        """F2: MFA logins insert an auth_sessions row (session list/revoke)."""
        from database.db_manager import DatabaseManager

        challenge = _login_mfa(client)
        resp = client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_session_token": challenge["mfa_session_token"], "code": _totp(MFA_SECRET)},
        )
        assert resp.status_code == 200, resp.text
        db = DatabaseManager(_TEST_DB)
        try:
            count = db.conn.execute(
                "SELECT COUNT(*) FROM auth_sessions WHERE user_email = ?",
                (MFA_EMAIL,),
            ).fetchone()[0]
        finally:
            db.close()
        assert count == 1, "MFA login should record an auth_sessions row (F2)"

    def test_verify_invalid_code_returns_401(self, client):
        challenge = _login_mfa(client)
        resp = client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_session_token": challenge["mfa_session_token"], "code": "000000"},
        )
        assert resp.status_code == 401, resp.text

    def test_verify_invalid_session_returns_401(self, client):
        resp = client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_session_token": "bogus-session-token", "code": _totp(MFA_SECRET)},
        )
        assert resp.status_code == 401, resp.text

    def test_verify_failure_bodies_are_uniform(self, client):
        """Invalid session and invalid code return identical 401 bodies."""
        bad_session = client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_session_token": "bogus", "code": _totp(MFA_SECRET)},
        )
        challenge = _login_mfa(client)
        bad_code = client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_session_token": challenge["mfa_session_token"], "code": "000000"},
        )
        assert bad_session.status_code == bad_code.status_code == 401
        assert bad_session.json() == bad_code.json()
        assert bad_session.json()["detail"]["detail"] == "Invalid or expired verification code."

    def test_verify_locks_after_three_failures(self, client):
        """3 wrong codes lock the session token; the 4th (correct) still 401s."""
        challenge = _login_mfa(client)
        tok = challenge["mfa_session_token"]
        for _ in range(3):
            resp = client.post(
                "/api/v1/auth/mfa/verify",
                json={"mfa_session_token": tok, "code": "000000"},
            )
            assert resp.status_code == 401, resp.text
        resp = client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_session_token": tok, "code": _totp(MFA_SECRET)},
        )
        assert resp.status_code == 401, resp.text

    def test_verify_session_is_single_use(self, client):
        """A consumed session token can never complete a second login."""
        challenge = _login_mfa(client)
        tok = challenge["mfa_session_token"]
        first = client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_session_token": tok, "code": _totp(MFA_SECRET)},
        )
        assert first.status_code == 200, first.text
        replay = client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_session_token": tok, "code": _totp(MFA_SECRET)},
        )
        assert replay.status_code == 401, replay.text


# ═══════════════════════════════════════════════════════════════════════
# Backup codes
# ═══════════════════════════════════════════════════════════════════════


class TestBackupCode:
    _CODE = "BACKUPCODE1"

    def test_backup_code_success_returns_tokens(self, client):
        from database.db_manager import DatabaseManager

        db = DatabaseManager(_TEST_DB)
        _seed_backup_code(db, 2, self._CODE)
        db.close()
        challenge = _login_mfa(client)
        resp = client.post(
            "/api/v1/auth/mfa/backup-code",
            json={"mfa_session_token": challenge["mfa_session_token"], "backup_code": self._CODE},
        )
        assert resp.status_code == 200, resp.text
        assert "access_token" in resp.json()
        assert "refresh_token" not in resp.json()
        # F1: the claim stamps used_at (Python-bound timestamp) and F2:
        # the login also records an auth_sessions row.
        db = DatabaseManager(_TEST_DB)
        try:
            used = db.conn.execute(
                "SELECT used_at FROM mfa_backup_codes WHERE user_id = 2"
            ).fetchone()
            sessions = db.conn.execute(
                "SELECT COUNT(*) FROM auth_sessions WHERE user_email = ?",
                (MFA_EMAIL,),
            ).fetchone()[0]
        finally:
            db.close()
        assert used is not None and used["used_at"] is not None, "used_at must be stamped (F1)"
        assert sessions == 1, "MFA backup-code login should record an auth_sessions row (F2)"

    def test_backup_code_is_single_use(self, client):
        from database.db_manager import DatabaseManager

        db = DatabaseManager(_TEST_DB)
        _seed_backup_code(db, 2, self._CODE)
        db.close()
        challenge = _login_mfa(client)
        ok = client.post(
            "/api/v1/auth/mfa/backup-code",
            json={"mfa_session_token": challenge["mfa_session_token"], "backup_code": self._CODE},
        )
        assert ok.status_code == 200, ok.text
        # The session token is consumed -> second use of the same token fails.
        replay = client.post(
            "/api/v1/auth/mfa/backup-code",
            json={"mfa_session_token": challenge["mfa_session_token"], "backup_code": self._CODE},
        )
        assert replay.status_code == 401, replay.text
        # A FRESH session presenting the now-used code also fails (atomic claim).
        challenge2 = _login_mfa(client)
        used = client.post(
            "/api/v1/auth/mfa/backup-code",
            json={"mfa_session_token": challenge2["mfa_session_token"], "backup_code": self._CODE},
        )
        assert used.status_code == 401, used.text

    def test_backup_code_invalid_returns_401(self, client):
        challenge = _login_mfa(client)
        resp = client.post(
            "/api/v1/auth/mfa/backup-code",
            json={"mfa_session_token": challenge["mfa_session_token"], "backup_code": "NOPE1234"},
        )
        assert resp.status_code == 401, resp.text

    def test_backup_code_invalid_session_returns_401(self, client):
        resp = client.post(
            "/api/v1/auth/mfa/backup-code",
            json={"mfa_session_token": "bogus", "backup_code": self._CODE},
        )
        assert resp.status_code == 401, resp.text


# ═══════════════════════════════════════════════════════════════════════
# Status
# ═══════════════════════════════════════════════════════════════════════


class TestMfaStatus:
    def test_status_enabled(self, client):
        resp = client.get("/api/v1/auth/me/mfa-status", headers=_auth_hdr(MFA_EMAIL))
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"mfa_enabled": True}

    def test_status_disabled(self, client):
        resp = client.get("/api/v1/auth/me/mfa-status", headers=_auth_hdr(PLAIN_EMAIL))
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"mfa_enabled": False}

    def test_status_admin_returns_false(self, app):
        from backend.dependencies_security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: {
            "id": 0, "email": "admin@test.com", "role": "admin",
            "is_admin": True, "company_id": 0,
        }
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/auth/me/mfa-status")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"mfa_enabled": False}