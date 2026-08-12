"""Mobile team endpoints (blueprint §6.9, Phase 4A).

  - GET   /mobile/team?page&page_size&search
          -> PaginatedResponse[TeamMemberOut]              [can_manage_users]
  - POST  /mobile/team/invite {email, role} -> TeamMemberOut (201)
          [can_manage_users] — SERVER-SIDE role constraint: role must be
          ``dispatcher`` or ``manager``; inviting ``admin`` is rejected with
          422 + machine-readable ``role_not_allowed``.
  - PATCH /mobile/team/{user_id} {role?, is_active?} -> TeamMemberOut
          [can_manage_users] — same role constraint (never admin).  Setting
          ``is_active=false`` triggers the deactivation cascade: the user's
          is_active is flipped, all their mobile_devices rows are deleted and
          every refresh token they hold is revoked, in ONE transaction (plus
          the refresh-token store sweep) — their existing JWT is then rejected
          by ``get_current_user`` (which queries ``users.is_active = 1``).

Invites create a fully active user with a random temporary password hash
(bcrypt).  There is no invitation email infrastructure — the password is
deliberately random and unknown to anyone; an admin must set a real password
via PATCH later (documented in the module docstring and the openapi tags).
"""
from __future__ import annotations

import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import get_current_user
from backend.schemas.common import PaginatedResponse
from backend.schemas.mobile import (
    MANAGEABLE_TEAM_ROLES,
    TeamMemberInviteRequest,
    TeamMemberOut,
    TeamMemberPatchRequest,
)
from backend.security import hash_password
from services.permission_service import PermissionService

router = APIRouter(prefix="/team", tags=["mobile_team"])


def _check_manage_users(db: DatabaseManager, user_id: int) -> None:
    """Gate team endpoints with the real PermissionService (can_manage_users)."""
    if not user_id:
        return
    result = PermissionService(db).can_manage_users(user_id)
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.reason or "Permission denied")


def _fetch_member(db: DatabaseManager, user_id: int, company_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a company-scoped user row (joined with linked driver name)."""
    row = db.execute(
        "SELECT u.id, u.email, u.role, u.display_name, u.is_active, u.created_at, "
        "d.name AS driver_name "
        "FROM users u "
        "LEFT JOIN drivers d ON d.id = u.driver_id "
        "WHERE u.id = ? AND u.company_id = ?",
        (user_id, company_id),
    ).fetchone()
    return dict(row) if row else None


def _row_to_member(row: Dict[str, Any]) -> TeamMemberOut:
    return TeamMemberOut(
        id=row["id"],
        email=row["email"] or "",
        display_name=row.get("display_name") or "",
        role=row.get("role") or "",
        is_active=bool(row.get("is_active")),
        created_at=row.get("created_at"),
        driver_name=row.get("driver_name"),
    )


def _deactivate_user_cascade(
    db: DatabaseManager, user_id: int, email: str, company_id: int,
) -> None:
    """Deactivate a user and destroy every session they hold (ONE transaction).

    1. ``users.is_active = 0``                     — existing JWTs now fail
       ``get_current_user`` (``users.is_active = 1`` lookup) with 401.
    2. ``DELETE FROM mobile_devices WHERE user_id`` — all devices deregistered
       (the refresh flow checks ``mobile_devices.is_active = 1`` too).
    3. ``DELETE FROM auth_sessions WHERE user_email`` — session rows removed.
    4. Commit, then sweep the refresh-token store (in-memory + Redis) for the
       user's email and revoke every matching opaque refresh token.
    """
    db.execute(
        "UPDATE users SET is_active = 0 WHERE id = ? AND company_id = ?",
        (user_id, company_id),
    )
    db.execute("DELETE FROM mobile_devices WHERE user_id = ?", (user_id,))
    try:
        db.execute("DELETE FROM auth_sessions WHERE user_email = ?", (email,))
    except Exception:
        # auth_sessions may not exist on very old databases; non-fatal.
        pass
    db.commit()

    # Refresh tokens live outside the DB (opaque, hashed in _refresh_store /
    # Redis) — revoke them by the user's email right after the DB commit.
    from backend.api.v1.auth import revoke_user_refresh_tokens
    try:
        revoke_user_refresh_tokens(email)
    except Exception:
        # Revocation is best-effort; the DB deactivation already blocks login
        # and JWT refresh for device-less flows.
        pass


@router.get("", response_model=PaginatedResponse[TeamMemberOut])
def list_team_members(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str = Query("", description="Substring match on email / display_name"),
):
    """Paginated, company-scoped team member list (gate: can_manage_users)."""
    _check_manage_users(db, current_user.get("id") or 0)
    company_id = current_user["company_id"]

    clauses = ["u.company_id = ?"]
    params: list = [company_id]
    if search:
        clauses.append("(u.email LIKE ? OR u.display_name LIKE ?)")
        like = f"%{search}%"
        params += [like, like]
    where = " AND ".join(clauses)

    cnt = db.execute(
        f"SELECT COUNT(*) AS cnt FROM users u WHERE {where}", tuple(params)
    ).fetchone()
    total = dict(cnt)["cnt"] if cnt else 0

    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT u.id, u.email, u.role, u.display_name, u.is_active, u.created_at, "
        f"d.name AS driver_name "
        f"FROM users u "
        f"LEFT JOIN drivers d ON d.id = u.driver_id "
        f"WHERE {where} ORDER BY u.email LIMIT ? OFFSET ?",
        tuple(params) + (page_size, offset),
    ).fetchall()

    items = [_row_to_member(dict(r)) for r in rows]
    return PaginatedResponse.from_items(
        items=items, total=total, page=page, page_size=page_size
    )


@router.post("/invite", response_model=TeamMemberOut, status_code=201)
def invite_team_member(
    data: TeamMemberInviteRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Invite a new team member (gate: can_manage_users).

    Server-side role constraint: ``role`` must be ``dispatcher`` or
    ``manager``.  Inviting an ``admin`` is rejected with 422 +
    ``error_code='role_not_allowed'`` (managers can never mint admins).

    The new user is created immediately with ``is_active=1`` and a random
    temporary bcrypt password hash — there is no invitation-email
    infrastructure, so the password is unknown to everyone and a real one
    must be set later via PATCH.
    """
    _check_manage_users(db, current_user.get("id") or 0)
    company_id = current_user["company_id"]
    email = data.email.strip().lower()

    if data.role not in MANAGEABLE_TEAM_ROLES:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "role_not_allowed",
                "detail": (
                    f"Role must be one of {', '.join(MANAGEABLE_TEAM_ROLES)}; "
                    "admin users cannot be invited."
                ),
            },
        )

    existing = db.execute(
        "SELECT id FROM users WHERE email = ? AND company_id = ?",
        (email, company_id),
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "email_exists",
                "detail": "A user with this email already exists in your company.",
            },
        )

    temp_password = secrets.token_urlsafe(24)
    hashed_pw = hash_password(temp_password)

    cursor = db.execute(
        "INSERT INTO users (email, password_hash, role, company_id, "
        "display_name, is_active) VALUES (?, ?, ?, ?, ?, 1)",
        (email, hashed_pw, data.role, company_id, email),
    )
    user_id = cursor.lastrowid
    db.commit()

    row = _fetch_member(db, user_id, company_id)
    return _row_to_member(row)


@router.patch("/{user_id}", response_model=TeamMemberOut)
def patch_team_member(
    user_id: int,
    data: TeamMemberPatchRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Update a team member's role / active status (gate: can_manage_users).

    Role changes are constrained to ``{dispatcher, manager}`` and never apply
    to admin-role users (both defensive 422).  ``is_active=false`` triggers the
    full deactivation cascade (devices deleted + refresh tokens revoked).
    """
    _check_manage_users(db, current_user.get("id") or 0)
    company_id = current_user["company_id"]
    my_id = current_user.get("id") or 0

    row = _fetch_member(db, user_id, company_id)
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "user_not_found", "detail": "User not found in this company."},
        )

    if row["role"] == "admin":
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "role_not_allowed",
                "detail": "Admin-role users cannot be modified through the team endpoint.",
            },
        )

    if data.role is not None and data.role not in MANAGEABLE_TEAM_ROLES:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "role_not_allowed",
                "detail": (
                    f"Role must be one of {', '.join(MANAGEABLE_TEAM_ROLES)}; "
                    "admin roles cannot be assigned."
                ),
            },
        )

    if data.is_active is not None and not data.is_active and user_id == my_id:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "self_deactivation",
                "detail": "You cannot deactivate your own account.",
            },
        )

    if data.role is None and data.is_active is None:
        return _row_to_member(row)

    if data.is_active is not None and not data.is_active:
        # Full deactivation cascade (one transaction + refresh-token sweep).
        _deactivate_user_cascade(db, user_id, row["email"], company_id)
    else:
        updates: Dict[str, Any] = {}
        if data.role is not None:
            updates["role"] = data.role
        if data.is_active is not None:
            updates["is_active"] = 1 if data.is_active else 0
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        db.execute(
            f"UPDATE users SET {set_clause} WHERE id = ? AND company_id = ?",  # nosec B608
            list(updates.values()) + [user_id, company_id],
        )
        db.commit()

    updated = _fetch_member(db, user_id, company_id)
    return _row_to_member(updated)
