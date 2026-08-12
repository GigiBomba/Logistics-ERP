"""Avatar endpoints.

POST /api/v1/auth/me/avatar  — upload / replace the current user's avatar
GET  /api/v1/auth/me/avatar  — fetch the current user's avatar image

Hardening (blueprint §18c.2):
* MIME whitelist (PNG/JPEG/WebP) + magic-byte validation (415 on mismatch).
* 5 MB size cap.
* JPEG EXIF (APP1) stripped before persistence (stdlib — no Pillow).
* Deterministic storage path ``data/uploads/avatars/{user_id}.{ext}`` with
  a sanitized integer user id (no path traversal possible).
* Persistence: a ``documents`` row with ``category='avatar'``,
  ``entity_type='user'``, ``entity_id=<user_id>`` — chosen because the
  ``users`` table has no ``avatar_url`` column and adding one would require
  a schema.py edit (owned by another lane this wave).
"""

import hashlib
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.dependencies import get_db
from backend.dependencies_security import get_current_user
from backend.errors import ErrorCode
from backend.uploads import strip_exif, validate_magic_bytes
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth", "avatar"])

AVATAR_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
AVATAR_EXT_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
_MEDIA_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB

AVATARS_ROOT = os.path.join("data", "uploads", "avatars")
AVATAR_URL = "/api/v1/auth/me/avatar"


def _safe_user_id(current_user: Dict[str, Any]) -> int:
    """Return a validated non-negative integer user id (path-traversal safe)."""
    try:
        user_id = int(current_user.get("id"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "Invalid user identity.",
            },
        )
    if user_id < 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "Invalid user identity.",
            },
        )
    return user_id


def _avatar_path(user_id: int, ext: str) -> str:
    return os.path.join(AVATARS_ROOT, f"{user_id}{ext}")


def _resolve_existing_avatar(user_id: int) -> Optional[str]:
    """Return the stored avatar path for *user_id* (any known ext), or None."""
    for ext in (".png", ".jpg", ".webp"):
        path = _avatar_path(user_id, ext)
        if os.path.isfile(path):
            return path
    return None


@router.post("/me/avatar")
def upload_my_avatar(
    current_user: Dict[str, Any] = Depends(get_current_user),
    file: UploadFile = File(...),
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Upload/replace the authenticated user's avatar image."""
    user_id = _safe_user_id(current_user)

    mime = (file.content_type or "").lower()
    if mime not in AVATAR_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail={
                "error_code": ErrorCode.UNSUPPORTED_MEDIA_TYPE.value,
                "detail": "Only PNG, JPEG or WebP avatars are allowed.",
            },
        )

    # Read at most MAX+1 bytes so an oversized payload never fills memory.
    content = file.file.read(MAX_AVATAR_SIZE + 1)
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Avatar too large. Maximum size is 5 MB.",
        )
    if not content:
        raise HTTPException(
            status_code=400,
            detail="Empty file uploaded.",
        )

    # Magic-byte validation — never trust the declared MIME alone.
    if not validate_magic_bytes(content, mime):
        raise HTTPException(
            status_code=415,
            detail={
                "error_code": ErrorCode.UNSUPPORTED_MEDIA_TYPE.value,
                "detail": "File content does not match its declared type.",
            },
        )

    # Strip EXIF metadata from JPEG payloads before persistence.
    if mime == "image/jpeg":
        content = strip_exif(content)

    ext = AVATAR_EXT_BY_MIME[mime]
    os.makedirs(AVATARS_ROOT, exist_ok=True)
    path = _avatar_path(user_id, ext)

    # Replace any prior avatar (possibly with a different extension).
    old = _resolve_existing_avatar(user_id)
    if old and os.path.normpath(old) != os.path.normpath(path):
        try:
            os.remove(old)
        except OSError:
            logger.warning("Could not remove old avatar %s", old)

    with open(path, "wb") as f:
        f.write(content)

    # Persist a pointer row so the avatar is queryable and re-served after
    # restart.  Uses the existing `documents` table (no schema.py change).
    _persist_avatar_row(db, user_id, path, mime, content)

    logger.info("Avatar saved: user_id=%s mime=%s size=%d", user_id, mime, len(content))
    return {"avatar_url": AVATAR_URL}


@router.get("/me/avatar")
def get_my_avatar(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Return the authenticated user's avatar image."""
    user_id = _safe_user_id(current_user)
    path = _resolve_existing_avatar(user_id)
    if not path:
        raise HTTPException(status_code=404, detail="No avatar set.")
    media_type = _MEDIA_BY_EXT.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type)


def _persist_avatar_row(
    db: DatabaseManager,
    user_id: int,
    path: str,
    mime: str,
    content: bytes,
) -> None:
    """Insert/update a ``documents`` row (category='avatar') for the avatar."""
    now = datetime.now().isoformat()
    file_hash = hashlib.sha256(content).hexdigest()
    ext = os.path.splitext(path)[1].lower()
    size = len(content)

    existing = db.conn.execute(
        "SELECT id FROM documents "
        "WHERE category = 'avatar' AND entity_type = 'user' AND entity_id = ?",
        (user_id,),
    ).fetchone()
    try:
        if existing:
            db.conn.execute(
                "UPDATE documents SET file_path = ?, mime_type = ?, "
                "file_size = ?, file_hash = ?, uploaded_at = ?, updated_at = ? "
                "WHERE id = ?",
                (path, mime, size, file_hash, now, now, existing["id"]),
            )
        else:
            db.conn.execute(
                """INSERT INTO documents
                   (doc_number, title, category, entity_type, entity_id,
                    file_path, file_name, file_size, mime_type, file_hash,
                    tags, description, is_archived, uploaded_by,
                    uploaded_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)""",
                (
                    f"AV-{user_id}-{int(time.time())}",
                    f"avatar-{user_id}",
                    "avatar",
                    "user",
                    user_id,
                    path,
                    f"avatar{ext}",
                    size,
                    mime,
                    file_hash,
                    "[]",
                    "",
                    str(user_id),
                    now,
                    now,
                ),
            )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        logger.exception("Failed to persist avatar document row for user %s", user_id)
        raise
