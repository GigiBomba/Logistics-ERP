"""Support ticket endpoints.

POST /api/v1/support/tickets       — Create a support ticket.
GET  /api/v1/support/tickets       — List tickets for the current company.
GET  /api/v1/support/tickets/:id   — Get a single ticket.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.errors import ErrorCode
from backend.db import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/tickets", status_code=201)
def create_ticket(
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Create a new support ticket."""
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")
    subject = data.get("subject", "").strip()
    description = data.get("description", "").strip()
    priority = data.get("priority", "medium")

    if not subject or not description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "subject and description are required.",
            },
        )

    if priority not in ("low", "medium", "high", "urgent"):
        priority = "medium"

    cursor = db.conn.execute(
        "INSERT INTO support_tickets (company_id, user_id, subject, description, priority) "
        "VALUES (?, ?, ?, ?, ?)",
        (company_id, user_id, subject, description, priority),
    )
    db.conn.commit()

    ticket_id = cursor.lastrowid

    # Return the created ticket
    row = db.conn.execute(
        "SELECT id, subject, description, status, priority, created_at, updated_at "
        "FROM support_tickets WHERE id = ?",
        (ticket_id,),
    ).fetchone()

    return dict(row)


@router.get("/tickets")
def list_tickets(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """List support tickets for the current company."""
    company_id = current_user.get("company_id")

    rows = db.conn.execute(
        "SELECT id, subject, status, priority, created_at, updated_at "
        "FROM support_tickets WHERE company_id = ? "
        "ORDER BY created_at DESC",
        (company_id,),
    ).fetchall()

    return [dict(r) for r in rows]


@router.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Get a single support ticket by ID."""
    company_id = current_user.get("company_id")

    row = db.conn.execute(
        "SELECT id, subject, description, status, priority, created_at, updated_at "
        "FROM support_tickets WHERE id = ? AND company_id = ?",
        (ticket_id, company_id),
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Ticket not found.",
            },
        )

    return dict(row)
