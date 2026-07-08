"""Authentication endpoints.

POST /api/v1/auth/token   — Exchange credentials for JWT + refresh token.
POST /api/v1/auth/refresh — Exchange a refresh token for a new JWT.
POST /api/v1/auth/logout  — Revoke a refresh token.
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from backend.config import BackendSettings
from backend.dependencies import get_db
from backend.security import (
    create_access_token,
    generate_refresh_token,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Brute-force lockout ─────────────────────────────────────────────────────
# Tracks failed login attempts per normalized email.
# After FAILED_LOGIN_THRESHOLD attempts within LOCKOUT_WINDOW seconds,
# further attempts are blocked for LOCKOUT_DURATION seconds.
FAILED_LOGIN_THRESHOLD = 5
LOCKOUT_WINDOW = 300       # 5 minutes
LOCKOUT_DURATION = 900     # 15 minutes
_failed_attempts: Dict[str, list] = {}  # email -> [timestamps]


def _check_lockout(email: str) -> None:
    now = time.time()
    attempts = _failed_attempts.get(email, [])
    attempts[:] = [t for t in attempts if now - t < LOCKOUT_WINDOW]
    if len(attempts) >= FAILED_LOGIN_THRESHOLD:
        oldest = attempts[0] if attempts else now
        retry_after = int(LOCKOUT_DURATION - (now - oldest))
        if retry_after > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many login attempts. Please try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )


def _record_failure(email: str) -> None:
    now = time.time()
    if email not in _failed_attempts:
        _failed_attempts[email] = []
    _failed_attempts[email].append(now)
    # Trim old entries
    _failed_attempts[email][:] = [
        t for t in _failed_attempts[email] if now - t < LOCKOUT_WINDOW
    ]


def _clear_lockout(email: str) -> None:
    _failed_attempts.pop(email, None)

# ── Refresh token store ───────────────────────────────────────────────────────
# In-memory dict keyed by SHA-256 hash of the refresh token.
# Falls back to in-memory if Redis is unavailable.
_refresh_store: Dict[str, Dict[str, Any]] = {}


def _store_refresh(token_hash: str, payload: Dict[str, Any]) -> None:
    """Store a refresh token (in-memory or Redis)."""
    settings = BackendSettings()
    try:
        if settings.redis_url:
            import redis as _redis
            r = _redis.Redis.from_url(settings.redis_url, socket_timeout=2)
            r.setex(
                f"refresh:{token_hash}",
                settings.refresh_token_expire_days * 86400,
                json.dumps(payload),
            )
            r.close()
            return
    except Exception:
        logger.debug("Redis unavailable for refresh token store — using in-memory.")
    _refresh_store[token_hash] = payload


def _get_refresh(token_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieve a stored refresh token payload."""
    settings = BackendSettings()
    try:
        if settings.redis_url:
            import redis as _redis
            r = _redis.Redis.from_url(settings.redis_url, socket_timeout=2)
            raw = r.get(f"refresh:{token_hash}")
            r.close()
            if raw:
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Failed to parse refresh token payload from Redis")
                    return None
            return None
    except Exception:
        logger.debug("Redis unavailable for refresh token lookup — using in-memory.")
    return _refresh_store.get(token_hash)


def _delete_refresh(token_hash: str) -> None:
    """Remove a refresh token."""
    settings = BackendSettings()
    try:
        if settings.redis_url:
            import redis as _redis
            r = _redis.Redis.from_url(settings.redis_url, socket_timeout=2)
            r.delete(f"refresh:{token_hash}")
            r.close()
            return
    except Exception:
        pass
    _refresh_store.pop(token_hash, None)


def _hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of *token*."""
    return hashlib.sha256(token.encode()).hexdigest()


def _issue_tokens(email: str, role: str) -> Dict[str, Any]:
    """Create and persist an access token + refresh token pair.

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

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/token")
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Dict[str, Any]:
    """Authenticate and return an access token + refresh token pair.

    The **admin gateway** is checked first using environment variables.
    Admin authentication is **zero-database**.
    """
    settings = BackendSettings()
    email = form_data.username.strip().lower()
    client_ip = request.client.host if request.client else "unknown"

    # ── Brute-force lockout check ──────────────────────────────────────
    _check_lockout(email)

    # ── Gate 1: Admin gateway (env-var driven, zero DB) ────────────────
    if email == settings.admin_email:
        if not settings.admin_password_hash:
            logger.warning("Admin login attempted but no password hash configured [%s]", client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        is_valid: bool = await asyncio.get_event_loop().run_in_executor(
            None, verify_password,
            form_data.password, settings.admin_password_hash,
        )
        if not is_valid:
            _record_failure(email)
            logger.warning("Failed admin login attempt for %s from %s", email, client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        _clear_lockout(email)
        logger.info("Admin login successful for %s from %s", email, client_ip)
        return _issue_tokens(email, "admin")

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
                    detail="Invalid credentials.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user = dict(row)
        except HTTPException:
            raise
        except Exception as exc:
            logger.debug("Users table query failed for %s from %s: %s", email, client_ip, exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials.",
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
                detail="Invalid credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        _clear_lockout(email)
        logger.info("Login successful for %s from %s", email, client_ip)
        return _issue_tokens(user["email"], user.get("role", "dispatcher"))

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Authentication service unavailable.",
    )


@router.post("/refresh")
async def refresh_access_token(
    body: Dict[str, str],
) -> Dict[str, Any]:
    """Exchange a valid refresh token for a new access token.

    Request body: ``{"refresh_token": "<opaque 128-char hex>"}``

    The refresh token is looked up in the server-side store (Redis or
    in-memory dict).  If found and not expired, a new short-lived access
    token is issued.
    """
    refresh_token: str = body.get("refresh_token", "")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token is required.",
        )

    token_hash = _hash_token(refresh_token)
    payload = _get_refresh(token_hash)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found or revoked.",
        )

    expires_at: float = payload.get("expires_at", 0)
    if time.time() >= expires_at:
        _delete_refresh(token_hash)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired — please re-authenticate.",
        )

    # Rotate: delete old refresh token, issue new pair
    _delete_refresh(token_hash)
    email: str = payload["email"]
    role: str = payload["role"]
    return _issue_tokens(email, role)


@router.post("/logout")
async def logout(body: Dict[str, str]) -> Dict[str, str]:
    """Revoke a refresh token."""
    refresh_token: str = body.get("refresh_token", "")
    if refresh_token:
        _delete_refresh(_hash_token(refresh_token))
    return {"status": "ok", "detail": "Logged out."}
