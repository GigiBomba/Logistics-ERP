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


# ── Password reset token store ──────────────────────────────────────────
# In-memory dict: reset_token_hash -> {email, expires_at}
_reset_tokens: Dict[str, Dict[str, Any]] = {}
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


def _issue_tokens(email: str, role: str, response: Optional[Response] = None) -> Dict[str, Any]:
    """Create and persist an access token + refresh token pair.

    If *response* is provided, the refresh token is also set as an httpOnly
    cookie for the web frontend (prevents XSS theft).

    Returns the response dict with both tokens.
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

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",  # nosec B105
        "expires_in": settings.access_token_expire_minutes * 60,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/token")
async def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Dict[str, Any]:
    """Authenticate and return an access token + refresh token pair.

    The **admin gateway** is checked first using environment variables.
    Admin authentication is **zero-database**.

    The refresh token is also set as an httpOnly cookie on the response
    for XSS-resistant browser storage.
    """
    settings = BackendSettings()
    email = form_data.username.strip().lower()
    client_ip = request.client.host if request.client else "unknown"

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
            return _issue_tokens(email, "admin", response)
        # No admin hash configured — fall through to database check below

    # ── Gate 2: Database users table (future-proof fallback) ───────────
    async for db in get_db():
        try:
            cursor = db.conn.execute(
                "SELECT id, email, password_hash, role FROM users "
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
        logger.info("Login successful for %s from %s", email, client_ip)
        return _issue_tokens(user["email"], user.get("role", "dispatcher"), response)

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
    body: RefreshTokenRequest,
) -> Dict[str, Any]:
    """Exchange a valid refresh token for a new access token.

    The refresh token is read from:
    1. The ``refresh_token`` httpOnly cookie (web frontend)
    2. The request body ``{"refresh_token": "..."}`` (desktop client, fallback)

    The refresh token is looked up in the server-side store (Redis or
    in-memory dict).  If found and not expired, a new short-lived access
    token is issued.
    """
    # Read from cookie first (XSS-safe), then fall back to body (desktop client)
    refresh_token: str = request.cookies.get("refresh_token", "") or body.refresh_token
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
def logout(request: Request, response: Response, body: LogoutRequest) -> Dict[str, str]:
    """Revoke a refresh token.

    Reads the refresh token from:
    1. The ``refresh_token`` httpOnly cookie (web frontend)
    2. The request body ``{"refresh_token": "..."}`` (desktop client, fallback)
    """
    refresh_token: str = request.cookies.get("refresh_token", "") or body.refresh_token
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
def forgot_password(body: ForgotPasswordRequest) -> Dict[str, str]:
    """Request a password reset token.

    Returns 200 regardless of whether the email exists (anti-enumeration).
    In production the token would be sent via email; for development/testing
    it is stored in the in-memory ``_reset_tokens`` dict.
    """
    email = body.email.strip().lower()
    if email:
        token = _generate_reset_token()
        token_hash = _hash_reset_token(token)
        _reset_tokens[token_hash] = {
            "email": email,
            "expires_at": time.time() + _RESET_TOKEN_EXPIRE_SECONDS,
        }
    return {"status": "ok", "detail": "If the email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest) -> Dict[str, str]:
    """Reset a user's password using a valid reset token."""
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
    stored = _reset_tokens.get(token_hash)

    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "Invalid or expired reset token.",
            },
        )

    if time.time() > stored["expires_at"]:
        _reset_tokens.pop(token_hash, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "Reset token has expired.",
            },
        )

    # Update password in the database
    email = stored["email"]
    from backend.security import hash_password
    pw_hash = hash_password(new_password)
    from backend.dependencies import get_db
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        gen = get_db()
        db = None
        try:
            while True:
                db = loop.run_until_complete(gen.__anext__())
                break
            db.conn.execute(
                "UPDATE users SET password_hash = ? WHERE email = ?",
                (pw_hash, email),
            )
            db.conn.commit()
        finally:
            loop.run_until_complete(gen.aclose())
            loop.close()
    except Exception as exc:
        logger.warning("Password reset DB update failed for %s: %s", email, exc)
        pass  # Token still consumed even if DB fails (anti-enumeration)

    # Consume the token (single-use)
    _reset_tokens.pop(token_hash, None)
    return {"status": "ok", "detail": "Password has been reset successfully."}
