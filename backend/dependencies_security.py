"""RBAC dependency gates for FastAPI.

Usage in route definitions::

    from backend.dependencies_security import (
        get_current_user,
        require_admin,
        require_manager,
        require_dispatcher,
        require_active_subscription,
    )

    @router.get("/admin/something")
    async def admin_only_route(
        current_user: Dict[str, Any] = Depends(require_admin),
    ):
        ...
"""

import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import PyJWTError as JWTError

from backend.config import BackendSettings
from backend.dependencies import get_db, set_request_user_context
from backend.errors import ErrorCode
from backend.security import decode_access_token

logger = logging.getLogger(__name__)

# Tell FastAPI where the token endpoint lives so the automatic
# OAuth2 flow can redirect / prompt the client appropriately.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Tiers that count as "paid" for trial enforcement (audit F1).
PAID_TIERS = {"professional", "enterprise", "pro", "business"}


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
            detail={
                "error_code": ErrorCode.TOKEN_INVALID.value,
                "detail": "Invalid or expired access token.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    email: str = payload.get("sub", "")
    role: str = payload.get("role", "")

    if not email or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": ErrorCode.TOKEN_INVALID.value,
                "detail": "Token payload missing required claims.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Admin identity — resolved from env, zero DB access ──────────────
    if email == settings.admin_email:
        user = {
            "id": 0,
            "email": email,
            "role": role,
            "is_admin": True,
            "company_id": 0,
            "company_name": None,
        }
        set_request_user_context(company_id=0, role=role)
        return user

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
                detail={
                    "error_code": ErrorCode.USER_NOT_FOUND.value,
                    "detail": "User account not found or inactive.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        user: Dict[str, Any] = dict(row)
        user["is_admin"] = False
        set_request_user_context(
            company_id=user.get("company_id"),
            role=user.get("role", ""),
        )
        return user

    # Should never reach here
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "detail": "Authentication service unavailable.",
        },
    )


async def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Require the authenticated user to have the ``admin`` role.

    Raises:
        HTTPException (403): If the user is not an admin.
    """
    if not current_user.get("is_admin") and current_user.get("role") != "admin":
        logger.warning(
            "Authorization denied: user=%s role=%s required=%s endpoint=%s",
            current_user.get("email", "unknown"),
            current_user.get("role", "unknown"),
            "admin",
            "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ErrorCode.INSUFFICIENT_PERMISSIONS.value,
                "detail": "Admin privileges required.",
            },
        )
    return current_user


async def require_manager(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Require admin or manager role.

    Raises:
        HTTPException (403): If the user is neither an admin nor a manager.
    """
    role: str = current_user.get("role", "")
    if role not in ("admin", "manager") and not current_user.get("is_admin"):
        logger.warning(
            "Authorization denied: user=%s role=%s required=%s endpoint=%s",
            current_user.get("email", "unknown"),
            current_user.get("role", "unknown"),
            "manager",
            "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ErrorCode.INSUFFICIENT_PERMISSIONS.value,
                "detail": "Manager or admin privileges required.",
            },
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
    if role not in ("admin", "manager", "dispatcher"):
        logger.warning(
            "Authorization denied: user=%s role=%s required=%s endpoint=%s",
            current_user.get("email", "unknown"),
            current_user.get("role", "unknown"),
            "dispatcher",
            "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ErrorCode.INSUFFICIENT_PERMISSIONS.value,
                "detail": "Dispatcher or admin privileges required.",
            },
        )
    return current_user


async def require_active_subscription(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Require the company's subscription to be active (trial not expired).

    Implements audit F1 backend enforcement: a company whose provisioned
    14-day trial has lapsed and which has no paid tier is locked with
    HTTP 402 Payment Required on protected ERP endpoints.

    Rules:
    * Platform admin (env identity, company_id 0) always passes.
    * Paid tiers (professional/enterprise/pro/business) always pass.
    * No trial provisioned (``trial_ends_at`` NULL, e.g. legacy companies
      created before trial provisioning) → pass (never lock retroactively).
    * Trial expired → 402 with ``billing/subscription-expired``.

    Raises:
        HTTPException (402): If the company's trial has expired.
    """
    # Admin (env identity, company_id 0) bypass.
    if current_user.get("is_admin") or not current_user.get("company_id"):
        return current_user

    company_id = int(current_user["company_id"])

    async for db_conn in get_db():
        try:
            row = db_conn.conn.execute(
                "SELECT subscription_tier, trial_ends_at FROM companies WHERE id = ?",
                (company_id,),
            ).fetchone()
        except Exception as exc:
            logger.warning("Subscription gate query failed for company %s: %s", company_id, exc)
            return current_user  # fail-open on DB errors (auth already passed)

        if row is None:
            return current_user

        # Cancel-grace (F3): a canceled subscription remains usable until its
        # current_period_end. Once that lapses the company is locked with 402.
        # Other statuses fall through to the existing tier/trial logic.
        try:
            sub = db_conn.conn.execute(
                "SELECT status, current_period_end FROM subscriptions WHERE company_id = ?",
                (company_id,),
            ).fetchone()
        except Exception as exc:
            logger.warning("Subscription grace query failed for company %s: %s", company_id, exc)
            sub = None

        if sub is not None and (sub["status"] or "").strip().lower() == "canceled":
            period_end = sub["current_period_end"]
            if period_end:
                try:
                    end = datetime.fromisoformat(str(period_end).replace("Z", "+00:00"))
                except ValueError:
                    end = None
                if end is not None:
                    if end.tzinfo is not None:
                        ended = end.astimezone().replace(tzinfo=None) < datetime.utcnow()
                    else:
                        ended = end < datetime.utcnow()
                    if not ended:
                        return current_user  # grace window still open — pass
            # Canceled with no / lapsed current_period_end → lock.
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error_code": ErrorCode.SUBSCRIPTION_EXPIRED.value,
                    "detail": "Your subscription has ended. Renew to continue using Operion.",
                },
            )

        tier: str = (row["subscription_tier"] or "starter").strip().lower()
        if tier in PAID_TIERS:
            return current_user

        trial_ends: Any = row["trial_ends_at"]
        if not trial_ends:
            return current_user  # no trial provisioned — never lock retroactively

        try:
            end = datetime.fromisoformat(str(trial_ends).replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Unparseable trial_ends_at for company %s: %r", company_id, trial_ends)
            return current_user  # fail-open on malformed data

        if end.tzinfo is not None:
            expired = end.astimezone().replace(tzinfo=None) < datetime.utcnow()
        else:
            expired = end < datetime.utcnow()

        if expired:
            logger.warning(
                "Subscription gate: company %s trial expired at %s",
                company_id, trial_ends,
            )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error_code": ErrorCode.SUBSCRIPTION_EXPIRED.value,
                    "detail": "Your free trial has ended. Choose a plan to continue using Operion.",
                },
            )
        return current_user

    # Async generator yielded nothing (defensive — fail open).
    return current_user
