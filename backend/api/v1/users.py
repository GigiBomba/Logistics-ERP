"""User management endpoints.

Every route in this module requires manager or admin privileges.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import get_db
from backend.dependencies_security import require_manager
from backend.schemas.user import UserCreateRequest, UserUpdateRequest
from backend.security import hash_password
from database.db_manager import DatabaseManager

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=Dict[str, Any])
async def list_users(
    current_user: Dict[str, Any] = Depends(require_manager),
    db: DatabaseManager = Depends(get_db),
):
    """Return all users belonging to the current user's company."""
    company_id = current_user["company_id"]

    cursor = db.conn.execute(
        "SELECT u.id, u.email, u.role, u.display_name, u.is_active, "
        "u.created_at, u.driver_id, d.name AS driver_name "
        "FROM users u "
        "LEFT JOIN drivers d ON d.id = u.driver_id "
        "WHERE u.company_id = ? "
        "ORDER BY u.role, u.email",
        (company_id,),
    )
    users = [dict(row) for row in cursor.fetchall()]
    return {"items": users, "total": len(users)}


@router.post("/", response_model=Dict[str, int], status_code=201)
async def create_user(
    data: UserCreateRequest,
    current_user: Dict[str, Any] = Depends(require_manager),
    db: DatabaseManager = Depends(get_db),
):
    """Create a new user (dispatcher or driver) in the current company."""
    company_id = current_user["company_id"]

    # ── Validate role ─────────────────────────────────────────────────
    if data.role not in ("dispatcher", "driver"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'dispatcher' or 'driver'.",
        )

    # ── Check email uniqueness within company ─────────────────────────
    existing = db.conn.execute(
        "SELECT id FROM users WHERE email = ? AND company_id = ?",
        (data.email, company_id),
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists in your company.",
        )

    # ── Hash password ─────────────────────────────────────────────────
    hashed_pw = hash_password(data.password)

    driver_id = None
    if data.role == "driver":
        cursor = db.conn.execute(
            "INSERT INTO drivers (name, email, company_id, is_active) "
            "VALUES (?, ?, ?, 1)",
            (data.display_name, data.email, company_id),
        )
        driver_id = cursor.lastrowid

    # ── Insert user ──────────────────────────────────────────────────
    cursor = db.conn.execute(
        "INSERT INTO users (email, password_hash, role, company_id, "
        "display_name, is_active, driver_id) "
        "VALUES (?, ?, ?, ?, ?, 1, ?)",
        (data.email, hashed_pw, data.role, company_id, data.display_name, driver_id),
    )
    user_id = cursor.lastrowid
    db.conn.commit()
    return {"id": user_id}


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_manager),
    db: DatabaseManager = Depends(get_db),
):
    """Update a user's profile, email, password, or active status."""
    company_id = current_user["company_id"]
    my_id = current_user["id"]

    # ── Verify user exists in same company ────────────────────────────
    row = db.conn.execute(
        "SELECT id FROM users WHERE id = ? AND company_id = ?",
        (user_id, company_id),
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # ── Prevent self-deactivation ────────────────────────────────────
    if data.is_active is not None and not data.is_active and user_id == my_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate yourself.",
        )

    # ── Build update fields ──────────────────────────────────────────
    update_fields: Dict[str, Any] = {}
    if data.display_name is not None:
        update_fields["display_name"] = data.display_name
    if data.is_active is not None:
        update_fields["is_active"] = 1 if data.is_active else 0
    if data.email is not None:
        update_fields["email"] = data.email
    if data.password is not None:
        update_fields["password_hash"] = hash_password(data.password)

    if not update_fields:
        return {"status": "updated"}

    set_clause = ", ".join(f"{k} = ?" for k in update_fields)
    values = list(update_fields.values()) + [user_id]
    db.conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
    db.conn.commit()
    return {"status": "updated"}


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: int,
    current_user: Dict[str, Any] = Depends(require_manager),
    db: DatabaseManager = Depends(get_db),
):
    """Deactivate (soft-delete) a user by setting is_active = 0."""
    company_id = current_user["company_id"]
    my_id = current_user["id"]

    # ── Verify user exists in same company ────────────────────────────
    row = db.conn.execute(
        "SELECT id FROM users WHERE id = ? AND company_id = ?",
        (user_id, company_id),
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # ── Prevent self-deactivation ────────────────────────────────────
    if user_id == my_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate yourself.",
        )

    db.conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    db.conn.commit()
    return {"status": "deactivated"}
