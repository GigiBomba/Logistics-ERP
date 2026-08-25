"""Multi-Factor Authentication (TOTP) endpoints.

Routers
-------
``mfa_router`` (prefix ``/auth/mfa``)
    - POST /auth/mfa/enroll        (auth)   Start MFA enrollment.
    - POST /auth/mfa/confirm       (auth)   Verify the TOTP code + enable MFA.
    - POST /auth/mfa/disable       (auth)   Disable MFA (password re-auth).
    - POST /auth/mfa/verify        (public) Complete login with a TOTP code.
    - POST /auth/mfa/backup-code   (public) Complete login with a backup code.

``mfa_me_router`` (prefix ``/auth/me``)
    - GET  /auth/me/mfa-status     (auth)   Whether the caller has MFA on.

TOTP is implemented with the stdlib only (RFC 6238, HMAC-SHA1, 30s step,
6 digits). The TOTP secret is XOR-encrypted at rest using the server key
(see ``backend.security.encrypt_at_rest``) and backup codes are stored as
bcrypt hashes with single-use enforcement.
"""
from __future__ import annotations


import asyncio
import secrets
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

# ⚠️ DEPENDENCY GAP (Gate-34 A1): `_consume_mfa_session` does NOT exist in auth.py yet —
# this module MUST NOT be included in router.py until that helper is implemented,
# otherwise create_app() raises ImportError at startup (concurrent-agent work-in-progress).
from backend.api.v1.auth import _consume_mfa_session, _issue_tokens
from backend.config import BackendSettings
from backend.dependencies import get_db
from backend.dependencies_security import get_current_user
from backend.errors import ErrorCode
from backend.security import (
    build_otpauth_uri,
    decrypt_at_rest,
    encrypt_at_rest,
    generate_totp_secret,
    verify_password,
    verify_totp,
)

logger = __import__("logging").getLogger(__name__)

mfa_router = APIRouter(prefix="/auth/mfa", tags=["mfa"])
mfa_me_router = APIRouter(prefix="/auth/me", tags=["mfa"])

# ── Backup codes ──────────────────────────────────────────────────────────
# 8 random chars drawn from a 32-char alphabet (no 0/O/1/I ambiguity) with
# the best-effort entropy of 8 x 5 = 40 bits per code. Stored only as bcrypt
# hashes; a deliberately lower cost keeps the one-time confirm endpoint fast
# (codes are machine-generated with high entropy, not user-chosen passwords).
_BACKUP_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_BACKUP_CODE_LENGTH = 8
_BACKUP_CODE_BCRYPT_ROUNDS = 10


# ── Request schemas ───────────────────────────────────────────────────────


class MFACodeRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=8, description="6-digit TOTP code")


class MFADisableRequest(BaseModel):
    password: str = Field(..., min_length=1, description="Current account password")


class MFAVerifyRequest(BaseModel):
    mfa_session_token: str = Field(..., min_length=1)
    code: str = Field(..., min_length=6, max_length=8)


class MFABackupCodeRequest(BaseModel):
    mfa_session_token: str = Field(..., min_length=1)
    backup_code: str = Field(..., min_length=1)


# ── Helpers ───────────────────────────────────────────────────────────────


def _encryption_key() -> str:
    settings = BackendSettings()
    return settings.mfa_secret_encryption_key or settings.jwt_secret_key


def _reject_admin(current_user: Dict[str, Any]) -> None:
    """MFA lives on DB users; the env-var admin identity has no DB row."""
    if current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "MFA is not supported for the platform admin account.",
            },
        )


def _generate_backup_codes(count: int) -> List[str]:
    return [
        "".join(secrets.choice(_BACKUP_CODE_ALPHABET) for _ in range(_BACKUP_CODE_LENGTH))
        for _ in range(count)
    ]


def _hash_backup_codes_sync(codes: List[str]) -> List[str]:
    return [
        bcrypt.hashpw(
            c.encode("utf-8"),
            bcrypt.gensalt(rounds=_BACKUP_CODE_BCRYPT_ROUNDS),
        ).decode("utf-8")
        for c in codes
    ]


async def _hash_backup_codes(codes: List[str]) -> List[str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _hash_backup_codes_sync, codes)


def _bcrypt_check_sync(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


async def _verify_backup_code(user_id: int, candidate: str, db) -> bool:
    """Verify *candidate* against the user's unused backup codes.

    Marks the matched code as used (single-use enforcement) before
    returning ``True``. Single-use is enforced atomically (F2): the
    matched code is claimed with a conditional ``UPDATE`` that only wins
    while ``used_at IS NULL``, so two concurrent requests presenting the
    same code cannot both pass a read-check and issue tokens.
    """
    rows = db.conn.execute(
        "SELECT id, code_hash FROM mfa_backup_codes "
        "WHERE user_id = ? AND used_at IS NULL",
        (user_id,),
    ).fetchall()
    if not rows:
        return False
    loop = asyncio.get_event_loop()
    for row in rows:
        ok = await loop.run_in_executor(
            None, _bcrypt_check_sync, candidate, row["code_hash"]
        )
        if not ok:
            continue
        # Atomically claim the code: the UPDATE only modifies the row
        # while it is still unused. rowcount == 1 ⇒ we won the race and
        # the code is now consumed; rowcount == 0 ⇒ a concurrent request
        # already claimed it, so this code is already used → reject.
        cursor = db.conn.execute(
            "UPDATE mfa_backup_codes SET used_at = datetime('now') "
            "WHERE id = ? AND used_at IS NULL",
            (row["id"],),
        )
        db.conn.commit()
        if cursor.rowcount == 1:
            return True
        return False
    return False


def _problem(status_code: int, error_code: ErrorCode, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error_code": error_code.value, "detail": detail},
    )


# ═════════════════════════════════════════════════════════════════════════
# Enrollment (authenticated)
# ═════════════════════════════════════════════════════════════════════════


@mfa_router.post("/enroll", response_model=Dict[str, str])
async def mfa_enroll(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, str]:
    """Generate + persist a TOTP secret for the caller (not yet enabled).

    Returns the plaintext ``secret``, the ``otpauth_uri`` and a
    ``qr_payload`` (the otpauth URI) for the frontend QR renderer.
    The secret is XOR-encrypted at rest; ``mfa_enabled`` stays false
    until the code is confirmed via POST /confirm.
    """
    _reject_admin(current_user)
    settings = BackendSettings()

    async for db in get_db():
        row = db.conn.execute(
            "SELECT id, email, mfa_enabled FROM users WHERE email = ? AND is_active = 1",
            (current_user["email"],),
        ).fetchone()
        if row is None:
            raise _problem(404, ErrorCode.USER_NOT_FOUND, "User account not found.")
        if row["mfa_enabled"]:
            raise _problem(
                409, ErrorCode.MFA_ALREADY_ENABLED, "MFA is already enabled for this account."
            )

        secret = generate_totp_secret()
        uri = build_otpauth_uri(current_user["email"], secret, settings.mfa_issuer)
        db.conn.execute(
            "UPDATE users SET mfa_secret = ? WHERE id = ?",
            (encrypt_at_rest(secret, _encryption_key()), row["id"]),
        )
        db.conn.commit()
        logger.info("MFA enrollment started for %s", current_user["email"])
        return {"secret": secret, "otpauth_uri": uri, "qr_payload": uri}

    raise _problem(500, ErrorCode.INTERNAL_ERROR, "MFA service unavailable.")


@mfa_router.post("/confirm")
async def mfa_confirm(
    body: MFACodeRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Verify the TOTP code and enable MFA for the caller.

    On success generates 10 single-use backup codes, stores their bcrypt
    hashes, and returns the plaintext codes exactly once.
    """
    _reject_admin(current_user)
    settings = BackendSettings()

    async for db in get_db():
        row = db.conn.execute(
            "SELECT id, mfa_enabled, mfa_secret FROM users WHERE email = ? AND is_active = 1",
            (current_user["email"],),
        ).fetchone()
        if row is None:
            raise _problem(404, ErrorCode.USER_NOT_FOUND, "User account not found.")
        if row["mfa_enabled"]:
            raise _problem(409, ErrorCode.MFA_ALREADY_ENABLED, "MFA is already enabled for this account.")
        if not row["mfa_secret"]:
            raise _problem(400, ErrorCode.VALIDATION_ERROR, "Enroll first via POST /auth/mfa/enroll.")

        secret = decrypt_at_rest(row["mfa_secret"], _encryption_key())
        if not verify_totp(secret, body.code, window_steps=settings.mfa_totp_window_steps):
            raise _problem(400, ErrorCode.MFA_INVALID_CODE, "Invalid or expired verification code.")

        codes = _generate_backup_codes(settings.mfa_backup_codes_count)
        hashes = await _hash_backup_codes(codes)
        db.conn.execute("UPDATE users SET mfa_enabled = 1 WHERE id = ?", (row["id"],))
        db.conn.executemany(
            "INSERT INTO mfa_backup_codes (user_id, code_hash) VALUES (?, ?)",
            [(row["id"], h) for h in hashes],
        )
        db.conn.commit()
        logger.info("MFA enabled for user_id=%s", row["id"])
        return {"mfa_enabled": True, "backup_codes": codes}

    raise _problem(500, ErrorCode.INTERNAL_ERROR, "MFA service unavailable.")


@mfa_router.post("/disable")
async def mfa_disable(
    body: MFADisableRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, bool]:
    """Disable MFA after re-verifying the account password.

    Clears the TOTP secret and all backup codes.
    """
    _reject_admin(current_user)

    async for db in get_db():
        row = db.conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ? AND is_active = 1",
            (current_user["email"],),
        ).fetchone()
        if row is None:
            raise _problem(404, ErrorCode.USER_NOT_FOUND, "User account not found.")

        loop = asyncio.get_event_loop()
        pw_valid = await loop.run_in_executor(
            None, verify_password, body.password, row["password_hash"]
        )
        if not pw_valid:
            raise _problem(401, ErrorCode.INVALID_CREDENTIALS, "Incorrect password.")

        db.conn.execute(
            "UPDATE users SET mfa_enabled = 0, mfa_secret = NULL WHERE id = ?",
            (row["id"],),
        )
        db.conn.execute("DELETE FROM mfa_backup_codes WHERE user_id = ?", (row["id"],))
        db.conn.commit()
        logger.info("MFA disabled for user_id=%s", row["id"])
        return {"mfa_enabled": False}

    raise _problem(500, ErrorCode.INTERNAL_ERROR, "MFA service unavailable.")


# ═════════════════════════════════════════════════════════════════════════
# Login challenge (public — completes the mid-login MFA flow)
# ═════════════════════════════════════════════════════════════════════════


async def _complete_login(session: Dict[str, Any], response: Response) -> Dict[str, Any]:
    """Issue the full token pair after a successful second-factor check."""
    email: str = session["email"]
    role: str = session.get("role", "dispatcher")
    return _issue_tokens(email, role, response, include_refresh_in_body=False)


def _load_mfa_user(db, email: str):
    return db.conn.execute(
        "SELECT id, email, mfa_enabled, mfa_secret FROM users "
        "WHERE email = ? AND is_active = 1",
        (email,),
    ).fetchone()


@mfa_router.post("/verify")
async def mfa_verify(
    body: MFAVerifyRequest,
    response: Response,
) -> Dict[str, Any]:
    """Complete login with a TOTP code.

    Validates the short-lived single-use ``mfa_session_token`` obtained
    from POST /auth/token, verifies the TOTP code, then issues the full
    token pair (access token in the body, refresh token in an httpOnly
    cookie) exactly like a non-MFA login.
    """
    settings = BackendSettings()
    session = _consume_mfa_session(body.mfa_session_token)
    if session is None:
        raise _problem(401, ErrorCode.MFA_SESSION_INVALID, "Invalid or expired MFA session.")

    async for db in get_db():
        row = _load_mfa_user(db, session["email"])
        if row is None or not row["mfa_enabled"]:
            raise _problem(401, ErrorCode.MFA_SESSION_INVALID, "MFA is not enabled for this account.")

        secret = decrypt_at_rest(row["mfa_secret"], _encryption_key())
        if not verify_totp(secret, body.code, window_steps=settings.mfa_totp_window_steps):
            raise _problem(401, ErrorCode.MFA_INVALID_CODE, "Invalid or expired verification code.")

        logger.info("MFA login verified for %s", session["email"])
        return await _complete_login(session, response)

    raise _problem(500, ErrorCode.INTERNAL_ERROR, "MFA service unavailable.")


@mfa_router.post("/backup-code")
async def mfa_backup_code(
    body: MFABackupCodeRequest,
    response: Response,
) -> Dict[str, Any]:
    """Complete login with a single-use recovery backup code."""
    session = _consume_mfa_session(body.mfa_session_token)
    if session is None:
        raise _problem(401, ErrorCode.MFA_SESSION_INVALID, "Invalid or expired MFA session.")

    async for db in get_db():
        row = _load_mfa_user(db, session["email"])
        if row is None or not row["mfa_enabled"]:
            raise _problem(401, ErrorCode.MFA_SESSION_INVALID, "MFA is not enabled for this account.")

        candidate = body.backup_code.strip().upper()
        used = await _verify_backup_code(row["id"], candidate, db)
        if not used:
            raise _problem(
                401,
                ErrorCode.MFA_INVALID_CODE,
                "Invalid, already used, or exhausted backup code.",
            )

        logger.info("MFA backup-code login verified for %s", session["email"])
        return await _complete_login(session, response)

    raise _problem(500, ErrorCode.INTERNAL_ERROR, "MFA service unavailable.")


# ═════════════════════════════════════════════════════════════════════════
# Status
# ═════════════════════════════════════════════════════════════════════════


@mfa_me_router.get("/mfa-status")
async def mfa_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, bool]:
    """Return whether the authenticated caller has MFA enabled."""
    if current_user.get("is_admin"):
        return {"mfa_enabled": False}

    async for db in get_db():
        row = db.conn.execute(
            "SELECT mfa_enabled FROM users WHERE email = ?",
            (current_user["email"],),
        ).fetchone()
        return {"mfa_enabled": bool(row and row["mfa_enabled"])}

    raise _problem(500, ErrorCode.INTERNAL_ERROR, "MFA service unavailable.")
