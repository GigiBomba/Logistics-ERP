"""Versioning service — document version management."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from datetime import datetime
from typing import Any

from repositories.audit_repository import AuditRepository
from repositories.document_repository import DocumentRepository

logger = logging.getLogger("document_versioning_service")

DOCUMENTS_ROOT = os.path.join("data", "documents")
MAX_VERSIONS_PER_DOC = 20
MAX_UPLOAD_SIZE = 20 * 1024 * 1024


class VersioningService:

    def __init__(self, repo: DocumentRepository) -> None:
        self._repo = repo

    def get_versions(self, doc_id: int) -> list[dict[str, Any]]:
        return self._repo.get_versions(doc_id)

    def upload_new_version(self, doc_id: int, source_path: str,
                           comment: str = "", uploaded_by: str = "") -> int | None:
        doc = self._repo.get_by_id(doc_id)
        if not doc:
            return None
        self._validate_file(source_path)

        count = self._repo.get_version_count(doc_id)
        next_ver = count + 1

        versions = self._repo.get_versions(doc_id)
        while len(versions) >= MAX_VERSIONS_PER_DOC:
            oldest = versions[-1]
            try:
                if os.path.isfile(oldest["file_path"]):
                    os.remove(oldest["file_path"])
                self._repo._execute(
                    "DELETE FROM document_versions WHERE id = ?",
                    (oldest["id"],),
                    commit=True,
                )
            except Exception:
                pass
            versions = self._repo.get_versions(doc_id)

        file_hash = self._compute_sha256(source_path)
        file_size = os.path.getsize(source_path)

        safe_name = self._sanitize_filename(os.path.basename(source_path))
        version_dir = os.path.join(DOCUMENTS_ROOT, ".versions", str(doc_id))
        os.makedirs(version_dir, exist_ok=True)
        version_path = self._unique_path(version_dir, f"v{next_ver}_{safe_name}")
        shutil.copy2(source_path, version_path)

        now = datetime.now().isoformat()
        self._repo.add_version(
            doc_id, next_ver, version_path, file_size, file_hash,
            comment, uploaded_by, now,
        )
        self._repo.update(doc_id, file_path=version_path, file_size=file_size,
                          file_hash=file_hash, updated_at=now)
        self._log_audit("document.version_added",
                        f"Version {next_ver} for document {doc_id}")
        return next_ver

    def restore_version(self, doc_id: int, version_number: int) -> bool:
        versions = self._repo.get_versions(doc_id)
        target = next((v for v in versions if v["version_number"] == version_number), None)
        if not target or not os.path.isfile(target["file_path"]):
            return False
        now = datetime.now().isoformat()
        self._repo.update(doc_id, file_path=target["file_path"],
                          file_size=target["file_size"],
                          file_hash=target["file_hash"],
                          updated_at=now)
        self._log_audit("document.version_restored",
                        f"Restored version {version_number} for document {doc_id}")
        return True

    # ── Helpers ───────────────────────────────────────────────────────

    ALLOWED_EXTENSIONS = {
        ".pdf", ".png", ".jpg", ".jpeg", ".docx",
        ".xlsx", ".csv", ".txt", ".zip", ".gif", ".bmp",
    }

    BLOCKED_EXTENSIONS = {
        ".exe", ".bat", ".ps1", ".sh", ".msi", ".com",
        ".scr", ".vbs", ".jar", ".reg", ".dll",
    }

    def _validate_file(self, source_path: str) -> None:
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f"File not found: {source_path}")
        ext = os.path.splitext(source_path)[1].lower()
        if ext in self.BLOCKED_EXTENSIONS:
            raise ValueError(f"File type '{ext}' is not allowed")
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(f"File type '{ext}' is not supported")
        file_size = os.path.getsize(source_path)
        if file_size > MAX_UPLOAD_SIZE:
            raise ValueError(
                f"File too large ({file_size} bytes). Max is {MAX_UPLOAD_SIZE} bytes"
            )

    @staticmethod
    def _compute_sha256(file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        name_parts = name.rsplit(".", 1)
        base = "".join(
            c for c in name_parts[0] if c.isalnum() or c in "_- "
        ).strip()
        ext = "".join(
            c for c in (name_parts[1] if len(name_parts) > 1 else "")
            if c.isalnum()
        ).lower()
        safe = f"{base}.{ext}" if ext else base
        if not safe or safe == ".":
            safe = "unnamed_file"
        return safe

    @staticmethod
    def _unique_path(target_dir: str, filename: str) -> str:
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(target_dir, filename)
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(target_dir, f"{base}_{counter}{ext}")
            counter += 1
        return candidate

    def _log_audit(self, event_type: str, description: str) -> None:
        entity_type = event_type.split(".")[0] if "." in event_type else ""
        AuditRepository(self._repo.db).log_event(
            event_type=event_type,
            entity_type=entity_type,
            data={"description": description},
        )
