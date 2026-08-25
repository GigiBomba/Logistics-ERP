"""Organization management endpoints.

All endpoints require dispatcher+ auth.
Membership management (invite/remove) requires owner or admin role within the org.
"""
from __future__ import annotations


import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.errors import ErrorCode
from backend.utils.rate_limit import check_rate_limit
from backend.db import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/organizations", tags=["organizations"])


# ── Helpers ─────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    slug = re.sub(r'[^\w\s-]', '', text.lower().strip())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def _unique_org_slug(db: DatabaseManager, base_slug: str, exclude_id: Optional[int] = None) -> str:
    """Ensure org slug uniqueness."""
    slug = base_slug
    counter = 1
    while True:
        query = "SELECT id FROM organizations WHERE slug = ?"
        params: List[Any] = [slug]
        if exclude_id is not None:
            query += " AND id != ?"
            params.append(exclude_id)
        existing = db.execute(query, tuple(params)).fetchone()
        if not existing:
            return slug
        counter += 1
        slug = f"{base_slug}-{counter}"


def _get_org_by_slug(db: DatabaseManager, slug: str) -> Optional[Dict[str, Any]]:
    row = db.execute("SELECT * FROM organizations WHERE slug = ?", (slug,)).fetchone()
    return dict(row) if row else None


def _get_membership(db: DatabaseManager, org_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Get the current user's membership in an org."""
    row = db.execute(
        "SELECT * FROM org_members WHERE org_id = ? AND user_id = ? AND status = 'active'",
        (org_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def _check_org_access(
    db: DatabaseManager,
    org_id: int,
    user_id: int,
    required_roles: Optional[List[str]] = None,
):
    """Check user has access to org, optionally with specific role."""
    membership = _get_membership(db, org_id, user_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": ErrorCode.NOT_FOUND.value, "detail": "Organization not found."},
        )
    if required_roles and membership["role"] not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ErrorCode.INSUFFICIENT_PERMISSIONS.value,
                "detail": "Insufficient permissions.",
            },
        )
    return membership


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("")
def list_organizations(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return all organizations the current user is a member of."""
    rows = db.execute(
        "SELECT o.id, o.name, o.slug, o.logo_url, o.is_active, o.created_at, o.updated_at, "
        "o.subscription_tier, "
        "(SELECT COUNT(*) FROM org_members WHERE org_id = o.id AND status = 'active') as member_count, "
        "mu.role as user_role "
        "FROM organizations o "
        "JOIN org_members mu ON mu.org_id = o.id AND mu.user_id = ? "
        "WHERE mu.status = 'active' "
        "ORDER BY o.name",
        (current_user["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{slug}")
def get_organization(
    slug: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return a single organization by slug."""
    org = _get_org_by_slug(db, slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": ErrorCode.NOT_FOUND.value, "detail": "Organization not found."},
        )
    # Verify user is a member
    _check_org_access(db, org["id"], current_user["id"])
    return org


@router.post("", status_code=201)
def create_organization(
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Create a new organization. The creator is added as an owner."""
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "name is required.",
            },
        )

    slug = data.get("slug") or _slugify(name)
    slug = _unique_org_slug(db, slug)

    cursor = db.execute(
        "INSERT INTO organizations (name, slug, logo_url, website, industry, "
        "size, address, city, country, postal_code, phone, vat_number) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, slug, data.get("logo_url"), data.get("website"),
         data.get("industry"), data.get("size"), data.get("address"),
         data.get("city"), data.get("country"), data.get("postal_code"),
         data.get("phone"), data.get("vat_number")),
    )
    org_id = cursor.lastrowid

    # Add creator as owner
    db.execute(
        "INSERT INTO org_members (org_id, user_id, role, status) VALUES (?, ?, 'owner', 'active')",
        (org_id, current_user["id"]),
    )
    db.commit()

    row = db.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
    return dict(row)


@router.patch("/{slug}")
def update_organization(
    slug: str,
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Partially update an organization (owner or admin only)."""
    org = _get_org_by_slug(db, slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Organization not found.",
            },
        )

    _check_org_access(db, org["id"], current_user["id"], required_roles=["owner", "admin"])

    update_fields: Dict[str, Any] = {}
    for field in ("name", "logo_url", "website", "industry", "size",
                  "address", "city", "country", "postal_code", "phone", "vat_number"):
        if field in data:
            update_fields[field] = data[field]

    if "name" in data and data["name"]:
        update_fields["name"] = data["name"].strip()

    if "slug" in data and data["slug"] and data["slug"] != slug:
        update_fields["slug"] = _unique_org_slug(db, data["slug"], exclude_id=org["id"])

    if not update_fields:
        return org

    set_clause = ", ".join(f"{k} = ?" for k in update_fields)
    values = tuple(update_fields.values()) + (org["id"],)
    db.execute(
        f"UPDATE organizations SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
        values,
    )
    db.commit()

    row = db.execute("SELECT * FROM organizations WHERE id = ?", (org["id"],)).fetchone()
    return dict(row)


@router.get("/{slug}/members")
def list_members(
    slug: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """List members of an organization."""
    org = _get_org_by_slug(db, slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Organization not found.",
            },
        )
    _check_org_access(db, org["id"], current_user["id"])

    rows = db.execute(
        "SELECT m.id, m.org_id, m.user_id, m.role, m.joined_at, m.status, "
        "u.display_name as name, u.email "
        "FROM org_members m "
        "JOIN users u ON u.id = m.user_id "
        "WHERE m.org_id = ? "
        "ORDER BY m.joined_at",
        (org["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("/{slug}/invitations")
def invite_member(
    slug: str,
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Invite a user to join an organization (owner or admin only)."""
    org = _get_org_by_slug(db, slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Organization not found.",
            },
        )
    _check_org_access(db, org["id"], current_user["id"], required_roles=["owner", "admin"])

    email = data.get("email", "").strip().lower()
    role = data.get("role", "member")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "email is required.",
            },
        )
    if role not in ("admin", "member"):
        role = "member"

    # Check if user is already a member
    existing = db.execute(
        "SELECT id FROM org_members m JOIN users u ON u.id = m.user_id "
        "WHERE m.org_id = ? AND u.email = ?",
        (org["id"], email),
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": ErrorCode.DUPLICATE_RESOURCE.value,
                "detail": "User is already a member of this organization.",
            },
        )

    # Generate invitation token
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()

    cursor = db.execute(
        "INSERT INTO org_invitations (org_id, email, role, token, invited_by, status, expires_at) "
        "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
        (org["id"], email, role, token, current_user["id"], expires_at),
    )
    db.commit()

    row = db.execute("SELECT * FROM org_invitations WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


@router.delete("/{slug}/members/{member_id}")
def remove_member(
    slug: str,
    member_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Remove a member from an organization (owner or admin only)."""
    org = _get_org_by_slug(db, slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Organization not found.",
            },
        )

    membership = _check_org_access(db, org["id"], current_user["id"], required_roles=["owner", "admin"])

    # Cannot remove yourself if you're the only owner
    target = db.execute(
        "SELECT * FROM org_members WHERE id = ? AND org_id = ?",
        (member_id, org["id"]),
    ).fetchone()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Member not found.",
            },
        )

    target = dict(target)
    if target["role"] == "owner" and membership["role"] == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ErrorCode.INSUFFICIENT_PERMISSIONS.value,
                "detail": "Admin cannot remove an owner.",
            },
        )

    # Prevent removing the last owner
    if target["role"] == "owner":
        owner_count = db.execute(
            "SELECT COUNT(*) FROM org_members WHERE org_id = ? AND role = 'owner' AND status = 'active'",
            (org["id"],),
        ).fetchone()[0]
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": ErrorCode.VALIDATION_ERROR.value,
                    "detail": "Cannot remove the last owner.",
                },
            )

    # Soft delete: set status to 'suspended'
    db.execute(
        "UPDATE org_members SET status = 'suspended' WHERE id = ?",
        (member_id,),
    )
    db.commit()
    return {"status": "ok"}


@router.get("/{slug}/invitations")
def list_invitations(
    slug: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """List pending invitations for an organization (owner or admin only)."""
    org = _get_org_by_slug(db, slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Organization not found.",
            },
        )
    _check_org_access(db, org["id"], current_user["id"], required_roles=["owner", "admin"])

    rows = db.execute(
        "SELECT i.*, u.display_name as invited_by_name "
        "FROM org_invitations i "
        "LEFT JOIN users u ON u.id = i.invited_by "
        "WHERE i.org_id = ? AND i.status = 'pending' "
        "ORDER BY i.created_at DESC",
        (org["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("/invitations/{token}/accept")
def accept_invitation(
    token: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Accept an organization invitation.

    Abuse control: per-IP rate limit (the token is high-entropy so brute
    force is infeasible; this throttles mass attempt spam).

    Emits distinct machine-readable error codes so the client can render the
    right UX for each state:
    - token matches no invitation → 404 ``invitation/invalid``
    - invitation already expired (status ``expired``) → 400 ``invitation/expired``
    - invitation already accepted (status ``accepted``) → 409 ``invitation/already-accepted``
    - email mismatch → 403 ``auth/insufficient-permissions``
    """
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit("invite-accept", client_ip, 10, 600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
        )
    # Fetch by token WITHOUT filtering on status so accepted/expired rows are
    # visible and distinguishable from genuinely unknown tokens.
    row = db.execute(
        "SELECT * FROM org_invitations WHERE token = ?",
        (token,),
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.INVITATION_INVALID.value,
                "detail": "Invalid invitation token.",
            },
        )

    invitation = dict(row)

    if invitation["status"] == "expired":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.INVITATION_EXPIRED.value,
                "detail": "Invitation has expired.",
            },
        )

    if invitation["status"] == "accepted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": ErrorCode.INVITATION_ALREADY_ACCEPTED.value,
                "detail": "Invitation already accepted.",
            },
        )

    # Check user's email matches invited email
    user_email = current_user.get("email", "").strip().lower()
    if invitation["email"] != user_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ErrorCode.INSUFFICIENT_PERMISSIONS.value,
                "detail": "This invitation was sent to a different email address.",
            },
        )

    # Check expiry (status still 'pending' but expires_at already in the past)
    if invitation["expires_at"]:
        try:
            expires = datetime.fromisoformat(invitation["expires_at"])
            if expires < datetime.utcnow():
                db.execute("UPDATE org_invitations SET status = 'expired' WHERE id = ?", (invitation["id"],))
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error_code": ErrorCode.INVITATION_EXPIRED.value,
                        "detail": "Invitation has expired.",
                    },
                )
        except ValueError:
            pass

    # Add user as member
    cursor = db.execute(
        "INSERT INTO org_members (org_id, user_id, role, status) VALUES (?, ?, ?, 'active')",
        (invitation["org_id"], current_user["id"], invitation["role"]),
    )

    # Mark invitation as accepted
    db.execute(
        "UPDATE org_invitations SET status = 'accepted' WHERE id = ?",
        (invitation["id"],),
    )
    db.commit()

    row = db.execute("SELECT * FROM org_members WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)
