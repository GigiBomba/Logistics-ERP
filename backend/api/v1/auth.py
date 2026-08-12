"""Authentication endpoints.

POST /api/v1/auth/token   — Exchange credentials for JWT + refresh token.
POST /api/v1/auth/refresh — Exchange a refresh token for a new JWT.
POST /api/v1/auth/logout  — Revoke a refresh token.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from backend.config import BackendSettings
from backend.dependencies import get_db
from backend.errors import ErrorCode
from backend.services.email_provider import get_email_provider
from database.db_manager import DatabaseManager
from backend.schemas.auth import (
    ForgotPasswordRequest,
    LogoutRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
)
from backend.security import (
    create_access_token,
    generate_refresh_token,
    verify_password,
)
from backend.services.turnstile import require_turnstile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_env = os.environ.get("OPERION_ENV", "development")

# ── Redis client (lazy, shared) ───────────────────────────────────────────
_redis_client: Optional[object] = None


def _get_redis():
    """Return a shared Redis client, or None if unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    redis_url = os.environ.get("OPERION_REDIS_URL", "")
    redis_password = os.environ.get("OPERION_REDIS_PASSWORD", "")
    if not redis_url:
        return None
    try:
        import redis as _redis
        client = _redis.Redis.from_url(redis_url, socket_timeout=2, password=redis_password or None)
        client.ping()
        _redis_client = client
    except Exception:
        _redis_client = None  # don't retry every request
    return _redis_client


# ── Brute-force lockout ─────────────────────────────────────────────────────
# Tracks failed login attempts per normalized email.
# After FAILED_LOGIN_THRESHOLD attempts within LOCKOUT_WINDOW seconds,
# further attempts are blocked for LOCKOUT_DURATION seconds.
# Uses Redis when available for consistent state across workers.
FAILED_LOGIN_THRESHOLD = 5
LOCKOUT_WINDOW = 300       # 5 minutes
LOCKOUT_DURATION = 900     # 15 minutes
_failed_attempts: Dict[str, list] = {}  # email -> [timestamps] (in-memory fallback)


def _lockout_key(email: str) -> str:
    return f"lockout:{email}"


def _check_lockout(email: str) -> None:
    # Try Redis first
    r = _get_redis()
    if r is not None:
        try:
            key = _lockout_key(email)
            count = r.llen(key)
            if count is not None and count >= FAILED_LOGIN_THRESHOLD:
                ttl = r.ttl(key)
                if ttl and ttl > 0:
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail={
                                "error_code": ErrorCode.ACCOUNT_LOCKED.value,
                                "detail": f"Too many login attempts. Please try again in {ttl} seconds.",
                            },
                            headers={"Retry-After": str(ttl)},
                        )
            return
        except HTTPException:
            raise
        except Exception:
            pass  # fall through to in-memory

    # In-memory fallback
    now = time.time()
    attempts = _failed_attempts.get(email, [])
    attempts[:] = [t for t in attempts if now - t < LOCKOUT_WINDOW]
    if len(attempts) >= FAILED_LOGIN_THRESHOLD:
        oldest = attempts[0] if attempts else now
        retry_after = int(LOCKOUT_DURATION - (now - oldest))
        if retry_after > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": ErrorCode.ACCOUNT_LOCKED.value,
                    "detail": f"Too many login attempts. Please try again in {retry_after} seconds.",
                },
                headers={"Retry-After": str(retry_after)},
            )


def _record_failure(email: str) -> None:
    r = _get_redis()
    if r is not None:
        try:
            key = _lockout_key(email)
            r.lpush(key, time.time())
            r.ltrim(key, 0, FAILED_LOGIN_THRESHOLD - 1)
            r.expire(key, LOCKOUT_WINDOW)
            return
        except Exception:
            pass  # fall through to in-memory

    now = time.time()
    if email not in _failed_attempts:
        _failed_attempts[email] = []
    _failed_attempts[email].append(now)
    _failed_attempts[email][:] = [
        t for t in _failed_attempts[email] if now - t < LOCKOUT_WINDOW
    ]


def _clear_lockout(email: str) -> None:
    r = _get_redis()
    if r is not None:
        try:
            r.delete(_lockout_key(email))
            return
        except Exception:
            pass
    _failed_attempts.pop(email, None)


# ── Refresh token store ───────────────────────────────────────────────────────
# In-memory dict keyed by SHA-256 hash of the refresh token.
# Falls back to in-memory if Redis is unavailable.
_refresh_store: Dict[str, Dict[str, Any]] = {}


def _store_refresh(token_hash: str, payload: Dict[str, Any]) -> None:
    """Store a refresh token (Redis preferred, in-memory fallback)."""
    r = _get_redis()
    if r is not None:
        settings = BackendSettings()
        try:
            r.setex(
                f"refresh:{token_hash}",
                settings.refresh_token_expire_days * 86400,
                json.dumps(payload),
            )
            return
        except Exception:
            if _env == "production":
                logger.error("Redis write failed in _store_refresh — falling back to in-memory.")
            else:
                logger.debug("Redis unavailable for refresh token store — using in-memory.")
    _refresh_store[token_hash] = payload


def _get_refresh(token_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieve a stored refresh token payload."""
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(f"refresh:{token_hash}")
            if raw:
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Failed to parse refresh token payload from Redis")
                    return None
            return None
        except Exception:
            if _env == "production":
                logger.error("Redis read failed in _get_refresh — falling back to in-memory.")
            else:
                logger.debug("Redis unavailable for refresh token lookup — using in-memory.")
    return _refresh_store.get(token_hash)


def _delete_refresh(token_hash: str) -> None:
    """Remove a refresh token."""
    r = _get_redis()
    if r is not None:
        try:
            r.delete(f"refresh:{token_hash}")
            return
        except Exception:
            if _env == "production":
                logger.error("Redis delete failed in _delete_refresh — falling back to in-memory.")
    _refresh_store.pop(token_hash, None)


# ── MFA session token store ────────────────────────────────────────────────
# Short-lived (~5 min), single-use token issued mid-login when the user has
# MFA enabled. It carries the verified identity until the TOTP / backup-code
# challenge completes. Redis preferred, in-memory fallback.
_mfa_sessions: Dict[str, Dict[str, Any]] = {}


def _create_mfa_session(email: str, role: str) -> str:
    """Issue a short-lived, single-use MFA challenge token."""
    import secrets
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    settings = BackendSettings()
    expires_at = time.time() + settings.mfa_session_ttl_seconds
    r = _get_redis()
    if r is not None:
        try:
            r.setex(
                f"mfa_session:{token_hash}",
                settings.mfa_session_ttl_seconds,
                json.dumps({"email": email, "role": role, "expires_at": expires_at}),
            )
            return token
        except Exception:
            if _env == "production":
                logger.error("Redis write failed in _create_mfa_session — using in-memory.")
    _mfa_sessions[token_hash] = {
        "email": email,
        "role": role,
        "expires_at": expires_at,
    }
    return token


def _consume_mfa_session(token: str) -> Optional[Dict[str, Any]]:
    """Validate and consume (single-use) an MFA session token.

    Returns the session payload (``{"email", "role"}``) or ``None`` if the
    token is missing, expired, already used, or invalid.
    """
    if not token:
        return None
    token_hash = _hash_token(token)
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(f"mfa_session:{token_hash}")
            if raw:
                r.delete(f"mfa_session:{token_hash}")  # single-use
                try:
                    payload = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return None
                if time.time() >= payload.get("expires_at", 0):
                    return None
                return payload
            return None
        except Exception:
            if _env == "production":
                logger.error("Redis read failed in _consume_mfa_session — using in-memory.")
    payload = _mfa_sessions.pop(token_hash, None)
    if payload is None:
        return None
    if time.time() >= payload.get("expires_at", 0):
        return None
    return payload


# ── Password reset tokens (DB-backed) ──────────────────────────────────
# Only the SHA-256 hash of the token is stored, in the
# password_reset_tokens table (see database/schema.py). The raw token
# travels only inside the emailed reset link.
_RESET_TOKEN_EXPIRE_SECONDS = 3600  # 1 hour


def _generate_reset_token() -> str:
    """Generate a cryptographically random reset token."""
    import secrets
    return secrets.token_urlsafe(32)


def _hash_reset_token(token: str) -> str:
    """Hash a reset token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def _hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of *token*."""
    return hashlib.sha256(token.encode()).hexdigest()


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Set the refresh token as an httpOnly, secure, SameSite=Strict cookie.

    This protects the refresh token from XSS-based theft in the web frontend.
    The desktop client reads the refresh token from the response body instead.
    """
    settings = BackendSettings()
    max_age = settings.refresh_token_expire_days * 86400
    is_secure = _env == "production"
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=max_age,
        expires=max_age,
        path="/api/v1/auth",
        domain=None,
        secure=is_secure,
        httponly=True,
        samesite="strict",
    )


def _issue_tokens(
    email: str,
    role: str,
    response: Optional[Response] = None,
    include_refresh_in_body: bool = True,
) -> Dict[str, Any]:
    """Create and persist an access token + refresh token pair.

    If *response* is provided, the refresh token is also set as an httpOnly
    cookie for the web frontend (prevents XSS theft).

    Per blueprint §3.1 the refresh token is delivered ONLY via the httpOnly
    cookie on the initial login flow (``include_refresh_in_body=False``).
    The body field is retained for transitional compatibility on
    /auth/refresh (desktop ERP migration happens in a later lane).

    Returns the response dict with the access token (and optionally the
    refresh token for transitional endpoints).
    """
    settings = BackendSettings()
    access_token = create_access_token(
        data={"sub": email, "role": role},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = generate_refresh_token()
    token_hash = _hash_token(refresh_token)

    expires_at = time.time() + settings.refresh_token_expire_days * 86400
    _store_refresh(token_hash, {
        "email": email,
        "role": role,
        "expires_at": expires_at,
    })

    if response is not None:
        _set_refresh_cookie(response, refresh_token)

    result: Dict[str, Any] = {
        "access_token": access_token,
        "token_type": "bearer",  # nosec B105
        "expires_in": settings.access_token_expire_minutes * 60,
    }
    if include_refresh_in_body:
        result["refresh_token"] = refresh_token
    return result


# ═════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/token")
async def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    turnstile_token: str = Form(""),
) -> Dict[str, Any]:
    """Authenticate and return an access token + refresh token pair.

    The **admin gateway** is checked first using environment variables.
    Admin authentication is **zero-database**.

    When the user has MFA enabled, **no tokens are issued** — the response
    carries ``{"mfa_required": true, "mfa_session_token": ...}`` and the
    client must complete the TOTP / backup-code challenge at
    ``/auth/mfa/verify`` or ``/auth/mfa/backup-code``.

    Per blueprint §3.1 the refresh token is returned ONLY as an httpOnly
    cookie (never in the response body) on this endpoint.

    ``turnstile_token`` is an optional form field (the web frontend sends
    it from the Turnstile widget). Desktop/mobile ERP clients do not send
    it — they pass through untouched, per the fail-open-for-absent policy
    documented in ``backend/services/turnstile.py``.
    """
    settings = BackendSettings()
    email = form_data.username.strip().lower()
    client_ip = request.client.host if request.client else "unknown"

    # ── Turnstile validation (bot protection) ─────────────────────────────
    # Validated when a token is present; pass-through when absent so the
    # desktop/mobile ERP clients (no widget) keep working.
    if turnstile_token:
        require_turnstile(turnstile_token, client_ip)

    # ── Brute-force lockout check ──────────────────────────────────────
    _check_lockout(email)

    # ── Gate 1: Admin gateway (env-var driven, zero DB) ────────────────
    if email == settings.admin_email.strip().lower():
        if settings.admin_password_hash:
            is_valid: bool = await asyncio.get_event_loop().run_in_executor(
                None, verify_password,
                form_data.password, settings.admin_password_hash,
            )
            if not is_valid:
                _record_failure(email)
                logger.warning("Failed admin login attempt for %s from %s", email, client_ip)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error_code": ErrorCode.INVALID_CREDENTIALS.value,
                        "detail": "Invalid credentials.",
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )

            _clear_lockout(email)
            logger.info("Admin login successful for %s from %s", email, client_ip)
            return _issue_tokens(email, "admin", response, include_refresh_in_body=False)
        # No admin hash configured — fall through to database check below

    # ── Gate 2: Database users table (future-proof fallback) ───────────
    async for db in get_db():
        try:
            cursor = db.conn.execute(
                "SELECT id, email, password_hash, role, mfa_enabled FROM users "
                "WHERE email = ? AND is_active = 1",
                (email,),
            )
            row = cursor.fetchone()
            if row is None:
                _record_failure(email)
                logger.warning("Failed login attempt (unknown user) for %s from %s", email, client_ip)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error_code": ErrorCode.INVALID_CREDENTIALS.value,
                        "detail": "Invalid credentials.",
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user = dict(row)
        except HTTPException:
            raise
        except Exception as exc:
            logger.debug("Users table query failed for %s from %s: %s", email, client_ip, exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": ErrorCode.INVALID_CREDENTIALS.value,
                    "detail": "Invalid credentials.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        pw_valid = await asyncio.get_event_loop().run_in_executor(
            None, verify_password,
            form_data.password, user["password_hash"],
        )
        if not pw_valid:
            _record_failure(email)
            logger.warning("Failed login attempt (bad password) for %s from %s", email, client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": ErrorCode.INVALID_CREDENTIALS.value,
                    "detail": "Invalid credentials.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        _clear_lockout(email)

        # ── MFA gate: password is correct — challenge the second factor ──
        if user.get("mfa_enabled"):
            mfa_session = _create_mfa_session(
                email=user["email"],
                role=user.get("role", "dispatcher"),
            )
            logger.info("MFA challenge issued for %s from %s", email, client_ip)
            return {"mfa_required": True, "mfa_session_token": mfa_session}

        logger.info("Login successful for %s from %s", email, client_ip)
        return _issue_tokens(
            user["email"],
            user.get("role", "dispatcher"),
            response,
            include_refresh_in_body=False,
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "detail": "Authentication service unavailable.",
        },
    )


@router.post("/refresh")
def refresh_access_token(
    request: Request,
    response: Response,
    body: Optional[RefreshTokenRequest] = None,
) -> Dict[str, Any]:
    """Exchange a valid refresh token for a new access token.

    The refresh token is read from:
    1. The ``refresh_token`` httpOnly cookie (web frontend)
    2. The request body ``{"refresh_token": "..."}`` (desktop client,
       transitional fallback — the body is optional so a cookie-only
       refresh works with the web frontend)

    The refresh token is looked up in the server-side store (Redis or
    in-memory dict).  If found and not expired, a new short-lived access
    token is issued.
    """
    # Read from cookie first (XSS-safe), then fall back to body (desktop client)
    refresh_token: str = request.cookies.get("refresh_token", "") or (
        body.refresh_token if body else ""
    )
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "refresh_token cookie or body field is required.",
            },
        )

    token_hash = _hash_token(refresh_token)
    payload = _get_refresh(token_hash)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": ErrorCode.TOKEN_INVALID.value,
                "detail": "Refresh token not found or revoked.",
            },
        )

    expires_at: float = payload.get("expires_at", 0)
    if time.time() >= expires_at:
        _delete_refresh(token_hash)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": ErrorCode.TOKEN_EXPIRED.value,
                "detail": "Refresh token expired — please re-authenticate.",
            },
        )

    # Rotate: delete old refresh token, issue new pair
    _delete_refresh(token_hash)
    email: str = payload["email"]
    role: str = payload["role"]
    return _issue_tokens(email, role, response)


@router.post("/logout")
def logout(request: Request, response: Response, body: Optional[LogoutRequest] = None) -> Dict[str, str]:
    """Revoke a refresh token.

    Reads the refresh token from:
    1. The ``refresh_token`` httpOnly cookie (web frontend)
    2. The request body ``{"refresh_token": "..."}`` (desktop client,
       transitional fallback — the body is optional so a cookie-only
       logout works with the web frontend)
    """
    refresh_token: str = request.cookies.get("refresh_token", "") or (
        body.refresh_token if body else ""
    )
    if refresh_token:
        _delete_refresh(_hash_token(refresh_token))
    # Clear the cookie regardless
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
        secure=_env == "production",
        httponly=True,
        samesite="strict",
    )
    return {"status": "ok", "detail": "Logged out."}


# ═════════════════════════════════════════════════════════════════════════════
# OAuth2 client credentials grant
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/token/client-credentials")
async def token_client_credentials(
    client_id: str = Form(...),
    client_secret: str = Form(...),
    scope: str = Form(""),
    db=Depends(get_db),
):
    """OAuth2 client credentials grant — for machine-to-machine authentication.

    Returns a JWT access token for the registered OAuth2 client.
    No refresh token is issued (clients should re-authenticate).
    """
    from backend.oauth2 import OAuth2Service

    oauth2 = OAuth2Service(db)
    result = oauth2.issue_token(client_id, client_secret, scope)

    if not result:
        raise HTTPException(
            status_code=401,
            detail={
                "error_code": "auth/invalid-client",
                "detail": "Invalid client credentials",
            },
        )

    logger.info(
        "OAuth2 client credentials token issued via /token/client-credentials: "
        "client_id=%s", client_id,
    )
    return result


@router.post("/forgot-password")
def forgot_password(
    body: ForgotPasswordRequest,
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, str]:
    """Request a password reset token.

    Returns 200 regardless of whether the email exists (anti-enumeration).
    When the user exists, a single-use, time-limited token is stored
    (SHA-256 hashed) in the ``password_reset_tokens`` table and emailed to
    the user via the configured email provider (Resend in production when
    RESEND_API_KEY is set, logging otherwise). Email delivery is
    best-effort and never fails the request.
    """
    email = body.email.strip().lower()
    if email:
        user = db.conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if user is not None:
            token = _generate_reset_token()
            token_hash = _hash_reset_token(token)
            expires_at = str(time.time() + _RESET_TOKEN_EXPIRE_SECONDS)
            db.conn.execute(
                "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) "
                "VALUES (?, ?, ?)",
                (user["id"], token_hash, expires_at),
            )
            db.conn.commit()
            _send_reset_email(email, token)
    return {"status": "ok", "detail": "If the email exists, a reset link has been sent."}


def _send_reset_email(email: str, token: str) -> None:
    """Best-effort password-reset email via the configured provider."""
    site_url = os.environ.get("OPERION_SITE_URL", "https://operionerp.xyz")
    link = f"{site_url}/reset-password?token={token}"
    subject = "Reset your Operion password"
    html = (
        "<p>We received a request to reset your Operion account password.</p>"
        f'<p><a href="{link}">Reset your password</a></p>'
        "<p>This link expires in 1 hour. If you didn't request this, "
        "you can safely ignore this email.</p>"
    )
    try:
        ok = get_email_provider().send(
            email,
            "password-reset",
            {
                "subject": subject,
                "html": html,
                "body": f"Reset your Operion password: {link}",
            },
        )
        if ok:
            logger.info("Password reset email sent to %s", email)
    except Exception as exc:
        logger.warning("Password reset email failed for %s: %s", email, exc)


@router.post("/reset-password")
def reset_password(
    body: ResetPasswordRequest,
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, str]:
    """Reset a user's password using a valid, unexpired, single-use token."""
    token = body.token
    new_password = body.new_password

    if not token or not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "token and new_password are required.",
            },
        )
    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "Password must be at least 6 characters.",
            },
        )

    token_hash = _hash_reset_token(token)
    row = db.conn.execute(
        "SELECT id, user_id, expires_at FROM password_reset_tokens "
        "WHERE token_hash = ?",
        (token_hash,),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "Invalid or expired reset token.",
            },
        )

    if time.time() > float(row["expires_at"]):
        db.conn.execute(
            "DELETE FROM password_reset_tokens WHERE id = ?", (row["id"],)
        )
        db.conn.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "Reset token has expired.",
            },
        )

    from backend.security import hash_password

    pw_hash = hash_password(new_password)
    db.conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (pw_hash, row["user_id"]),
    )
    # Consume the token (single-use)
    db.conn.execute(
        "DELETE FROM password_reset_tokens WHERE id = ?", (row["id"],)
    )
    db.conn.commit()
    return {"status": "ok", "detail": "Password has been reset successfully."}
