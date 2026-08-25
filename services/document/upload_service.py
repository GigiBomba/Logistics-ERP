"""Upload service — file validation, upload, duplicate detection, registration."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
from datetime import datetime
from typing import Any

from database.db_manager import DatabaseManager
from repositories.document_repository import DocumentRepository
from repositories.fleet_repository import FleetRepository
from services.operations.event_bus import (
    DOCUMENT_LINKED,
    DOCUMENT_UPLOADED,
    EventBus,
)

logger = logging.getLogger("document_upload_service")

DOCUMENTS_ROOT = os.path.join("data", "documents")
MAX_UPLOAD_SIZE = 20 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".docx",
    ".xlsx", ".csv", ".txt", ".zip", ".gif", ".bmp",
}

BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".ps1", ".sh", ".msi", ".com",
    ".scr", ".vbs", ".jar", ".reg", ".dll",
}

MIME_MAP = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".zip": "application/zip",
}

CATEGORY_MAP = {
    "maintenance_record": "maintenance",
    "truck": "vehicles",
    "driver": "drivers",
    "trip": "trips",
    "invoice": "invoices",
    "client": "other",
}


class UploadService:

    def __init__(self, db: DatabaseManager, repo: DocumentRepository) -> None:
        self.db = db
        self._repo = repo
        self._event_bus = EventBus()

    def validate_file(self, source_path: str) -> tuple[bool, str | None]:
        if not os.path.isfile(source_path):
            return False, "File not found"
        ext = os.path.splitext(source_path)[1].lower()
        if ext in BLOCKED_EXTENSIONS:
            return False, f"File type '{ext}' is blocked for security"
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"File type '{ext}' is not supported"
        file_size = os.path.getsize(source_path)
        if file_size > MAX_UPLOAD_SIZE:
            return False, f"File too large ({file_size} bytes, max {MAX_UPLOAD_SIZE})"
        return True, None

    def check_duplicate(self, source_path: str) -> int | None:
        file_hash = self._compute_sha256(source_path)
        existing = self._repo.get_by_hash(file_hash)
        return existing["id"] if existing else None

    def upload(self, source_path: str, title: str = "",
               category: str = "", entity_type: str = "",
               entity_id: int | None = None,
               description: str = "", tags: list[str] | None = None,
               uploaded_by: str = "",
               company_id: int | None = None) -> int | None:
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f"Source file not found: {source_path}")

        file_name = os.path.basename(source_path)
        ext = os.path.splitext(file_name)[1].lower()

        if ext in BLOCKED_EXTENSIONS:
            raise ValueError(f"File type '{ext}' is not allowed")

        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"File type '{ext}' is not supported")

        file_size = os.path.getsize(source_path)
        if file_size > MAX_UPLOAD_SIZE:
            raise ValueError(
                f"File too large ({file_size} bytes). Max is {MAX_UPLOAD_SIZE} bytes"
            )

        file_hash = self._compute_sha256(source_path)

        existing = self._repo.get_by_hash(file_hash)
        if existing:
            link_entity_type = entity_type if entity_type else existing.get("entity_type", "")
            link_entity_id = entity_id if entity_id is not None else existing.get("entity_id", 0)
            new_link = self._repo.add_link(
                existing["id"], link_entity_type,
                link_entity_id,
                "attached",
                datetime.now().isoformat(),
            )
            if new_link > 0:
                self._event_bus.publish(DOCUMENT_LINKED, {
                    "document_id": existing["id"],
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                })
            return existing["id"]

        if not category and entity_type:
            category = CATEGORY_MAP.get(entity_type, "other")
        if not category:
            category = "other"

        safe_name = self._sanitize_filename(file_name)
        target_dir = self._ensure_category_dir(category)
        target_path = self._unique_path(target_dir, safe_name)

        shutil.copy2(source_path, target_path)

        mime_type = MIME_MAP.get(ext, "application/octet-stream")

        now = datetime.now().isoformat()
        if not title:
            title = os.path.splitext(file_name)[0]

        doc_number = self._repo.get_next_doc_number()
        tags_json = json.dumps(tags if tags else [])

        doc_id = self._repo.create(
            doc_number=doc_number,
            title=title,
            category=category,
            entity_type=entity_type or "",
            entity_id=entity_id,
            file_path=target_path,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            tags=tags_json,
            description=description,
            uploaded_by=uploaded_by,
            uploaded_at=now,
            updated_at=now,
            company_id=company_id,
        )

        if entity_type and entity_id is not None:
            self._repo.add_link(
                doc_id, entity_type, entity_id, "attached", now,
            )

        self._event_bus.publish(DOCUMENT_UPLOADED, {
            "document_id": doc_id,
            "doc_number": doc_number,
            "category": category,
            "entity_type": entity_type,
            "entity_id": entity_id,
        })

        logger.info("Document %s uploaded: %s", doc_number, title)
        return doc_id

    def batch_upload(self, paths: list, category: str = "",
                     entity_type: str = "", entity_id: int | None = None,
                     uploaded_by: str = "",
                     tags: list[str] | None = None,
                     company_id: int | None = None) -> dict[str, Any]:
        results = {"uploaded": [], "duplicates": [], "failed": [], "rejected": []}
        for src in paths:
            fname = os.path.basename(src)
            try:
                valid, err = self.validate_file(src)
                if not valid:
                    results["rejected"].append({"file": fname, "reason": err})
                    continue
                dup_id = self.check_duplicate(src)
                if dup_id:
                    results["duplicates"].append({"file": fname, "existing_id": dup_id})
                    if entity_type and entity_id is not None:
                        from datetime import datetime

                        from services.operations.event_bus import (
                            DOCUMENT_LINKED,
                            EventBus,
                        )
                        rid = self._repo.add_link(
                            dup_id, entity_type, entity_id,
                            "attached", datetime.now().isoformat(),
                        )
                        if rid > 0:
                            EventBus().publish(DOCUMENT_LINKED, {
                                "document_id": dup_id,
                                "entity_type": entity_type,
                                "entity_id": entity_id,
                            })
                    continue
                doc_id = self.upload(
                    src, category=category, entity_type=entity_type,
                    entity_id=entity_id, uploaded_by=uploaded_by, tags=tags,
                    company_id=company_id,
                )
                if doc_id:
                    results["uploaded"].append({"file": fname, "id": doc_id})
                else:
                    results["failed"].append({"file": fname, "reason": "unknown"})
            except Exception as e:
                results["failed"].append({"file": fname, "reason": str(e)})
        return results

    def register_existing(self, file_path: str, title: str = "",
                          category: str = "", entity_type: str = "",
                          entity_id: int | None = None,
                          description: str = "",
                          tags: list[str] | None = None,
                          is_migration: bool = False,
                          copy_type: str = "",
                          cmr_number: str = "",
                          cmr_metadata: str = "",
                          is_signed: int = 0,
                          commit: bool = True,
                          company_id: int | None = None) -> int | None:
        if not os.path.isfile(file_path):
            logger.warning("register_existing: file not found: %s", file_path)
            return None

        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_name)[1].lower()
        file_size = os.path.getsize(file_path)

        if is_migration:
            existing_count = self._repo._fetchone(
                f"SELECT COUNT(*) AS cnt FROM {self._repo.TABLE} "
                f"WHERE file_name = ? AND category = ?",
                (file_name, category),
            )
            if existing_count and existing_count.get("cnt", 0) > 0:
                return None

        existing_by_path = self._repo._fetchone(
            f"SELECT id FROM {self._repo.TABLE} WHERE file_path = ? AND is_archived = 0",
            (file_path,),
        )
        if existing_by_path:
            return 0 if is_migration else existing_by_path["id"]

        file_hash = self._compute_sha256(file_path)
        existing = self._repo.get_by_hash(file_hash)
        if existing:
            return 0 if is_migration else existing["id"]

        if not category and entity_type:
            category = CATEGORY_MAP.get(entity_type, "other")
        if not category:
            category = "other"

        mime_type = MIME_MAP.get(ext, "application/octet-stream")
        now = datetime.now().isoformat()
        if not title:
            title = os.path.splitext(file_name)[0]

        doc_number = self._repo.get_next_doc_number(commit=commit)
        tags_json = json.dumps(tags if tags else [])

        doc_id = self._repo.create(
            doc_number=doc_number,
            title=title,
            category=category,
            entity_type=entity_type or "",
            entity_id=entity_id,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            tags=tags_json,
            description=description,
            uploaded_by="system",
            uploaded_at=now,
            updated_at=now,
            copy_type=copy_type,
            cmr_number=cmr_number,
            cmr_metadata_json=cmr_metadata,
            is_signed=is_signed,
            commit=commit,
            company_id=company_id,
        )

        if entity_type and entity_id is not None:
            self._repo.add_link(doc_id, entity_type, entity_id, "attached", now,
                                commit=commit)

        # Publish event so the Document Center and other subscribers
        # can refresh without polling.
        try:
            if doc_id and not is_migration:
                self._event_bus.publish(DOCUMENT_UPLOADED, {
                    "document_id": doc_id,
                    "doc_number": doc_number,
                    "category": category or "",
                    "entity_type": entity_type or "",
                    "entity_id": entity_id,
                })
        except Exception:
            logger.debug("register_existing: event publish failed for doc %d", doc_id)

        return doc_id

    # ── Migration ─────────────────────────────────────────────────────

    def migrate_existing_attachments(self) -> int:
        rows = FleetRepository(self.db).get_maintenance_records_with_attachments()
        count = 0
        for row in rows:
            path = row["attachment_path"].strip()
            if not path or not os.path.isfile(path):
                continue
            doc_id = self.register_existing(
                file_path=path,
                title=f"Maintenance {row['maintenance_type']} {row['date'][:10] if row.get('date') else ''}",
                category="maintenance",
                entity_type="maintenance_record",
                entity_id=row["id"],
                tags=["maintenance", row.get("maintenance_type", "")],
                is_migration=True,
            )
            if doc_id:
                count += 1
        if count:
            logger.info("Migrated %d existing maintenance attachments to Document Center", count)
        return count

    def migrate_existing_invoices(self) -> int:
        invoices_dir = os.path.join("invoices")
        if not os.path.isdir(invoices_dir):
            return 0
        count = 0
        for fname in os.listdir(invoices_dir):
            if not fname.endswith(".pdf"):
                continue
            fpath = os.path.join(invoices_dir, fname)
            doc_id = self.register_existing(
                file_path=fpath,
                title=fname.replace(".pdf", ""),
                category="invoices",
                entity_type="invoice",
                entity_id=0,
                tags=["invoice"],
                is_migration=True,
            )
            if doc_id:
                count += 1
        if count:
            logger.info("Migrated %d existing invoice PDFs to Document Center", count)
        return count

    def migrate_all(self) -> int:
        return self.migrate_existing_attachments() + self.migrate_existing_invoices()

    # ── Helpers ───────────────────────────────────────────────────────

    def _compute_sha256(self, file_path: str) -> str:
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
    def _sanitize_category(category: str) -> str:
        """Make a category safe to use as a directory name.

        R2 (security): category arrives via the sync push payload raw (only
        the /upload endpoint sanitizes it).  Strip path separators and ``..``
        so a ``"../../.."`` category can never escape ``DOCUMENTS_ROOT``.
        """
        if not category:
            return "other"
        safe = re.sub(r"[\\/]", "_", str(category))
        safe = safe.replace("..", "_")
        safe = safe.strip(" .")
        return safe or "other"

    @staticmethod
    def _ensure_category_dir(category: str) -> str:
        d = os.path.join(DOCUMENTS_ROOT, UploadService._sanitize_category(category))
        os.makedirs(d, exist_ok=True)
        return d

    @staticmethod
    def _unique_path(target_dir: str, filename: str) -> str:
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(target_dir, filename)
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(target_dir, f"{base}_{counter}{ext}")
            counter += 1
        return candidate
