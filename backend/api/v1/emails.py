"""Generic email-send API router.

Lets the remote-mode client send a customer package (or any text email)
through the server-side SMTP configuration.  Attachment files are
resolved server-side from ``document_ids`` so the client never needs the
underlying file paths.
"""
from __future__ import annotations


import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from database.db_manager import DatabaseManager

logger = logging.getLogger("api.emails")

router = APIRouter(prefix="/emails", tags=["emails"])


class EmailSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_address: str = Field(..., min_length=1)
    subject: str = ""
    body: str = ""
    html: bool = False
    trip_id: Optional[int] = None
    document_ids: List[int] = Field(default_factory=list)


def _resolve_attachments(db: DatabaseManager, document_ids: List[int]) -> List[str]:
    """Resolve document rows to existing file paths (server side)."""
    if not document_ids:
        return []
    from repositories.document_repository import DocumentRepository

    repo = DocumentRepository(db)
    paths: List[str] = []
    for doc_id in document_ids:
        try:
            row = repo.get_by_id(int(doc_id))
        except (TypeError, ValueError):
            continue
        path = row.get("file_path") if row else None
        if path and os.path.isfile(path):
            paths.append(path)
    return paths


def _build_notifier(db: DatabaseManager):
    from services.operations.notification_center import NotificationCenter
    from services.preferences import PreferencesManager

    cfg = PreferencesManager(db).get_smtp_config()
    if not cfg.get("smtp_server") or not cfg.get("smtp_user"):
        raise HTTPException(status_code=400, detail="SMTP not configured")

    nc = NotificationCenter(db)
    nc.configure_smtp(
        cfg.get("smtp_server", ""),
        int(cfg.get("smtp_port", "587")),
        cfg.get("smtp_user", ""),
        cfg.get("smtp_password", ""),
    )
    return nc


@router.post("/send")
def send_email(
    data: EmailSendRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    if not data.to_address.strip():
        raise HTTPException(status_code=400, detail="Recipient email is required")

    nc = _build_notifier(db)
    attachments = _resolve_attachments(db, data.document_ids)
    ok = nc.send_email(
        to_address=data.to_address.strip(),
        subject=data.subject,
        body=data.body,
        attachments=attachments,
        html=data.html,
        trip_id=data.trip_id,
    )
    if ok:
        return {"status": "sent", "recipient": data.to_address.strip()}
    return {"status": "failed", "detail": "Email sending failed"}
