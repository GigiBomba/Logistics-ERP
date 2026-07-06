"""RBAC dependency gates for FastAPI.

Usage in route definitions::

    from backend.dependencies_security import get_current_user, require_admin

    @router.get("/admin/something")
    async def admin_only_route(
        current_user: Dict[str, Any] = Depends(require_admin),
    ):
        ...
"""

import logging
from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from backend.config import BackendSettings
from backend.dependencies import get_db
from backend.security import decode_access_token

logger = logging.getLogger(__name__)

# Tell FastAPI where the token endpoint lives so the automatic
# OAuth2 flow can redirect / prompt the client appropriately.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> Dict[str, Any]:
    """Decode the JWT and return the active user context.

    *Admin identity* is resolved from environment variables —
    **zero database access**.
    *Standard users* are looked up in the ``users`` table.

    Returns:
        A dict with at least ``id``, ``email``, ``role``, and ``is_admin``.

    Raises:
        HTTPException (401): If the token is missing, expired, or invalid.
    """
    settings = BackendSettings()

    try:
        payload: Dict[str, Any] = decode_access_token(token)
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    email: str = payload.get("sub", "")
    role: str = payload.get("role", "")

    if not email or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing required claims.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Admin identity — resolved from env, zero DB access ──────────────
    if email == settings.admin_email:
        return {
            "id": 0,
            "email": email,
            "role": role,
            "is_admin": True,
            "company_id": 0,
            "company_name": None,
        }

    # ── Standard user — look up in the database ─────────────────────────
    async for db in get_db():
        try:
            cursor = db.conn.execute(
                "SELECT u.id, u.email, u.role, u.company_id, "
                "c.company_name, c.subscription_tier "
                "FROM users u "
                "LEFT JOIN companies c ON c.id = u.company_id "
                "WHERE u.email = ? AND u.is_active = 1",
                (email,),
            )
            row = cursor.fetchone()
        except Exception as exc:
            logger.debug("Users table query failed for %s: %s", email, exc)
            row = None

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found or inactive.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user: Dict[str, Any] = dict(row)
        user["is_admin"] = False
        return user

    # Should never reach here
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Authentication service unavailable.",
    )


async def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Require the authenticated user to have the ``admin`` role.

    Raises:
        HTTPException (403): If the user is not an admin.
    """
    if not current_user.get("is_admin") and current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return current_user


async def require_dispatcher(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Require the authenticated user to be either an admin or a dispatcher.

    Raises:
        HTTPException (403): If the user has neither role.
    """
    role: str = current_user.get("role", "")
    if role not in ("admin", "dispatcher"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dispatcher or admin privileges required.",
        )
    return current_user
