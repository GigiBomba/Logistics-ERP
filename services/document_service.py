"""Document Center service — upload, search, link management."""
import hashlib
import json
import logging
import os
import queue
import shutil
import threading
import time
import zipfile
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database.db_manager import DatabaseManager
from repositories.document_repository import DocumentRepository
from services.operations.event_bus import (
    EventBus,
    DOCUMENT_UPLOADED,
    DOCUMENT_ARCHIVED,
    DOCUMENT_DELETED,
    DOCUMENT_LINKED,
    DOCUMENT_UNLINKED,
)

logger = logging.getLogger("document_service")

DOCUMENTS_ROOT = os.path.join("data", "documents")
THUMBS_ROOT = os.path.join("data", "documents", ".thumbnails")

MAX_UPLOAD_SIZE = 20 * 1024 * 1024
MAX_OCR_WORKERS = 2
MAX_OPERATION_EVENTS = 5000
MAX_VERSIONS_PER_DOC = 20
MAX_PDF_SIZE_FOR_OCR = 50 * 1024 * 1024
MAX_OCR_TEXT_LENGTH = 5000

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

IMAGE_MIME = {"image/png", "image/jpeg", "image/gif", "image/bmp"}

THUMB_SIZE = (160, 120)


class DocumentService:
    _ocr_queue: queue.Queue = queue.Queue()
    _ocr_workers: list = []
    _ocr_running = True
    _ocr_lock = threading.Lock()
    _ocr_db = None

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._repo = DocumentRepository(db)
        self._event_bus = EventBus()
        DocumentService._start_ocr_workers(db)

    @classmethod
    def _start_ocr_workers(cls, db):
        with cls._ocr_lock:
            if cls._ocr_workers:
                return
            cls._ocr_db = db
            cls._ocr_running = True
            for i in range(MAX_OCR_WORKERS):
                t = threading.Thread(target=cls._ocr_worker, daemon=True,
                                     name=f"ocr-worker-{i}")
                t.start()
                cls._ocr_workers.append(t)

    @classmethod
    def _ocr_worker(cls):
        while cls._ocr_running:
            try:
                doc_id, file_path, mime_type = cls._ocr_queue.get(timeout=2)
            except queue.Empty:
                continue
            try:
                db = cls._ocr_db
                if db is None:
                    logger.debug("OCR worker: no database reference, skipping")
                    continue
                svc = cls(db)
                text = svc.extract_text(file_path, mime_type)
                if text:
                    svc._repo.update(doc_id, text_content=text,
                                     updated_at=datetime.now().isoformat())
            except Exception as e:
                logger.debug("OCR worker failed for doc %d: %s", doc_id, e)
            finally:
                cls._ocr_queue.task_done()

    @classmethod
    def shutdown(cls):
        cls._ocr_running = False
        for t in cls._ocr_workers:
            t.join(timeout=3)
        cls._ocr_workers.clear()

    # ── Upload ─────────────────────────────────────────────────────────

    def validate_file(self, source_path: str) -> Tuple[bool, Optional[str]]:
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

    def check_duplicate(self, source_path: str) -> Optional[int]:
        file_hash = self._compute_sha256(source_path)
        existing = self._repo.get_by_hash(file_hash)
        return existing["id"] if existing else None

    def upload(self, source_path: str, title: str = "",
               category: str = "", entity_type: str = "",
               entity_id: Optional[int] = None,
               description: str = "", tags: Optional[List[str]] = None,
               uploaded_by: str = "") -> Optional[int]:
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

        if mime_type == "application/pdf" or mime_type.startswith("image/"):
            self._enqueue_ocr(doc_id, target_path, mime_type)

        logger.info("Document %s uploaded: %s", doc_number, title)
        return doc_id

    def _enqueue_ocr(self, doc_id: int, file_path: str, mime_type: str) -> None:
        if not os.path.isfile(file_path):
            return
        size = os.path.getsize(file_path)
        if size > MAX_PDF_SIZE_FOR_OCR:
            logger.debug("Skipping OCR for large file %s (%d bytes)", file_path, size)
            return
        try:
            DocumentService._ocr_queue.put_nowait((doc_id, file_path, mime_type))
        except queue.Full:
            logger.debug("OCR queue full, skipping doc %d", doc_id)

    def batch_upload(self, paths: list, category: str = "",
                     entity_type: str = "", entity_id: Optional[int] = None,
                     uploaded_by: str = "",
                     tags: Optional[List[str]] = None) -> Dict[str, Any]:
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
                        self.link_document(dup_id, entity_type, entity_id)
                    continue
                doc_id = self.upload(
                    src, category=category, entity_type=entity_type,
                    entity_id=entity_id, uploaded_by=uploaded_by, tags=tags,
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
                          entity_id: Optional[int] = None,
                          description: str = "",
                          tags: Optional[List[str]] = None,
                          is_migration: bool = False,
                          copy_type: str = "",
                          cmr_number: str = "",
                          cmr_metadata: str = "",
                          is_signed: int = 0) -> Optional[int]:
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

        doc_number = self._repo.get_next_doc_number()
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
        )

        if entity_type and entity_id is not None:
            self._repo.add_link(doc_id, entity_type, entity_id, "attached", now)

        return doc_id

    # ── Advanced Search ────────────────────────────────────────────────

    def advanced_search(self, query: str = "", category: str = "",
                        entity_type: str = "", entity_id: Optional[int] = None,
                        date_from: str = "", date_to: str = "",
                        mime_type: str = "", tag: str = "",
                        order: str = "uploaded_at DESC",
                        page: int = 0, page_size: int = 20) -> Dict[str, Any]:
        offset = page * page_size
        total = self._repo.advanced_search_count(
            query, category, entity_type, entity_id,
            date_from, date_to, mime_type, tag,
        )
        rows = self._repo.advanced_search(
            query, category, entity_type, entity_id,
            date_from, date_to, mime_type, tag,
            order, page_size, offset,
        )
        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    def search(self, query: str = "", category: str = "",
               entity_type: str = "", entity_id: Optional[int] = None,
               order: str = "uploaded_at DESC",
               page: int = 0, page_size: int = 20) -> Dict[str, Any]:
        offset = page * page_size
        total = self._repo.search_count(query, category, entity_type, entity_id)
        rows = self._repo.search(
            query, category, entity_type, entity_id, order,
            page_size, offset,
        )
        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    def get_categories(self) -> List[Dict[str, Any]]:
        return self._repo.count_by_category()

    def get_all_tags(self) -> List[str]:
        return self._repo.get_all_tags()

    def get_entity_types(self) -> List[str]:
        return self._repo.get_distinct_entity_types()

    def get_mime_types(self) -> List[str]:
        return self._repo.get_distinct_mime_types()

    # ── Tag Management ─────────────────────────────────────────────────

    def add_tag(self, doc_id: int, tag: str) -> bool:
        return self._repo.add_tag(doc_id, tag)

    def remove_tag(self, doc_id: int, tag: str) -> bool:
        return self._repo.remove_tag(doc_id, tag)

    def set_tags(self, doc_id: int, tags: list) -> None:
        self._repo.set_tags(doc_id, tags)

    # ── Document operations ────────────────────────────────────────────

    def get_by_id(self, doc_id: int) -> Optional[Dict[str, Any]]:
        return self._repo.get_by_id(doc_id)

    def get_links(self, doc_id: int) -> List[Dict[str, Any]]:
        return self._repo.get_links(doc_id)

    def get_documents_for_entity(self, entity_type: str,
                                 entity_id: int) -> List[Dict[str, Any]]:
        return self._repo.get_documents_for_entity(entity_type, entity_id)

    def link_document(self, doc_id: int, entity_type: str,
                      entity_id: int, relation_type: str = "attached") -> bool:
        rid = self._repo.add_link(
            doc_id, entity_type, entity_id, relation_type,
            datetime.now().isoformat(),
        )
        if rid > 0:
            self._event_bus.publish(DOCUMENT_LINKED, {
                "document_id": doc_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
            })
            return True
        return False

    def unlink_document(self, link_id: int) -> bool:
        link = self._fetch_link(link_id)
        if link:
            self._repo.remove_link(link_id)
            self._event_bus.publish(DOCUMENT_UNLINKED, {
                "document_id": link["document_id"],
                "link_id": link_id,
            })
            return True
        return False

    def _fetch_link(self, link_id: int) -> Optional[Dict[str, Any]]:
        return self._repo._fetchone(
            f"SELECT * FROM {self._repo.TABLE_LINKS} WHERE id = ?",
            (link_id,),
        )

    def update_metadata(self, doc_id: int, title: str = "",
                        description: str = "",
                        tags: Optional[List[str]] = None) -> bool:
        fields = {"updated_at": datetime.now().isoformat()}
        if title:
            fields["title"] = title
        if description is not None:
            fields["description"] = description
        if tags is not None:
            fields["tags"] = json.dumps(tags)
        if len(fields) > 1:
            self._repo.update(doc_id, **fields)
            return True
        return False

    def archive(self, doc_id: int) -> None:
        self._repo.archive(doc_id)
        self._event_bus.publish(DOCUMENT_ARCHIVED, {"document_id": doc_id})

    def delete(self, doc_id: int) -> bool:
        doc = self._repo.get_by_id(doc_id)
        if doc and doc.get("file_path"):
            try:
                if os.path.isfile(doc["file_path"]):
                    os.remove(doc["file_path"])
            except OSError as e:
                logger.warning("Failed to delete file %s: %s", doc["file_path"], e)
        self._cleanup_thumbnails(doc_id)
        self._cleanup_versions(doc_id)
        self._repo.remove_all_links(doc_id)
        self._repo.delete(doc_id)
        self._event_bus.publish(DOCUMENT_DELETED, {"document_id": doc_id})
        self._log_audit("document.deleted", f"Deleted document {doc_id}")
        return True

    def delete_batch(self, doc_ids: list) -> int:
        if not doc_ids:
            return 0
        count = 0
        for did in doc_ids:
            doc = self._repo.get_by_id(did)
            if doc and doc.get("file_path") and os.path.isfile(doc["file_path"]):
                try:
                    os.remove(doc["file_path"])
                except OSError:
                    pass
            self._cleanup_thumbnails(did)
            self._cleanup_versions(did)
            self._repo.remove_all_links(did)
        count = self._repo.delete_batch(doc_ids)
        self._event_bus.publish(DOCUMENT_DELETED, {"document_id": 0, "batch_count": len(doc_ids)})
        self._log_audit("document.batch_deleted", f"Batch deleted {len(doc_ids)} documents")
        return count

    def _cleanup_thumbnails(self, doc_id: int) -> None:
        thumb_name = f"thumb_{doc_id}.png"
        thumb_path = os.path.join(THUMBS_ROOT, thumb_name)
        if os.path.isfile(thumb_path):
            try:
                os.remove(thumb_path)
            except OSError:
                pass

    def _cleanup_versions(self, doc_id: int) -> None:
        versions = self._repo.get_versions(doc_id)
        for v in versions:
            try:
                if os.path.isfile(v["file_path"]):
                    os.remove(v["file_path"])
            except OSError:
                pass
        self._repo.delete_versions(doc_id)
        version_dir = os.path.join(DOCUMENTS_ROOT, ".versions", str(doc_id))
        if os.path.isdir(version_dir):
            try:
                os.rmdir(version_dir)
            except OSError:
                pass

    def open_file(self, doc_id: int) -> bool:
        doc = self._repo.get_by_id(doc_id)
        if doc and doc.get("file_path") and os.path.isfile(doc["file_path"]):
            os.startfile(os.path.abspath(doc["file_path"]))
            return True
        return False

    def is_image(self, mime_type: str) -> bool:
        return mime_type in IMAGE_MIME

    # ── Email ──────────────────────────────────────────────────────────

    def email_document(self, doc_id: int, recipient: str,
                       smtp_config: Optional[Dict[str, str]] = None,
                       prefs=None) -> bool:
        doc = self._repo.get_by_id(doc_id)
        if not doc or not os.path.isfile(doc.get("file_path", "")):
            return False

        if not smtp_config and prefs:
            try:
                smtp_config = prefs.get_smtp_config()
            except Exception:
                pass
        if not smtp_config or not smtp_config.get("smtp_server"):
            return False

        from services.operations.notification_center import NotificationCenter
        nc = NotificationCenter(self.db)
        nc.configure_smtp(
            smtp_config.get("smtp_server", ""),
            int(smtp_config.get("smtp_port", "587")),
            smtp_config.get("smtp_user", ""),
            smtp_config.get("smtp_password", ""),
        )
        subject = f"Document: {doc.get('title', doc.get('file_name', ''))}"
        body = f"Please find attached: {doc.get('title', '')}\n\nDocument ID: {doc.get('doc_number', '')}"
        ok = nc.send_email(recipient, subject, body, attachments=[doc["file_path"]])
        if ok:
            self._log_audit("document.emailed", f"Emailed {doc.get('doc_number')} to {recipient}")
        return ok

    # ── Zip Download ───────────────────────────────────────────────────

    def download_zip(self, doc_ids: list, output_path: str) -> str:
        canonical = os.path.realpath(output_path)
        safe_base = os.path.realpath(os.path.join("data", "documents"))
        if not canonical.startswith(safe_base + os.sep) and canonical != os.path.realpath(output_path[:len(safe_base)]):
            raise ValueError(f"Output path must be within {safe_base}")
        docs = self._repo.get_ids_by_ids(doc_ids)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for doc in docs:
                fpath = doc.get("file_path", "")
                if fpath and os.path.isfile(fpath):
                    arcname = doc.get("file_name", os.path.basename(fpath))
                    zf.write(fpath, arcname)
        self._log_audit("document.downloaded_zip", f"Downloaded {len(docs)} documents as zip")
        return output_path

    # ── Thumbnails ─────────────────────────────────────────────────────

    def get_thumbnail_path(self, doc_id: int) -> Optional[str]:
        doc = self._repo.get_by_id(doc_id)
        if not doc or not doc.get("file_path"):
            return None
        file_path = doc["file_path"]
        if not os.path.isfile(file_path):
            return None
        os.makedirs(THUMBS_ROOT, exist_ok=True)
        thumb_name = f"thumb_{doc_id}.png"
        thumb_path = os.path.join(THUMBS_ROOT, thumb_name)
        if os.path.isfile(thumb_path):
            return thumb_path
        return self._generate_thumbnail(file_path, thumb_path, doc.get("mime_type", ""))

    def _generate_thumbnail(self, file_path: str, thumb_path: str,
                            mime_type: str) -> Optional[str]:
        try:
            if self.is_image(mime_type):
                from PIL import Image
                with Image.open(file_path) as img:
                    img.thumbnail(THUMB_SIZE, Image.LANCZOS)
                    img.save(thumb_path, "PNG")
                return thumb_path
            elif mime_type == "application/pdf":
                return self._pdf_thumbnail(file_path, thumb_path)
        except Exception as e:
            logger.debug("Thumbnail generation failed for %s: %s", file_path, e)
        return None

    def _pdf_thumbnail(self, pdf_path: str, thumb_path: str) -> Optional[str]:
        try:
            from PyPDF2 import PdfReader
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return None
        try:
            reader = PdfReader(pdf_path)
            if len(reader.pages) == 0:
                return None
            img = Image.new("RGB", THUMB_SIZE, "#1c1c1f")
            d = ImageDraw.Draw(img)
            d.text((10, 50), "PDF\n%d page(s)" % len(reader.pages),
                   fill="#a1a1aa")
            img.save(thumb_path, "PNG")
            return thumb_path
        except Exception:
            return None

    # ── Audit Log ──────────────────────────────────────────────────────

    def _log_audit(self, event_type: str, description: str) -> None:
        try:
            import uuid
            now = datetime.now().isoformat()
            ev_id = uuid.uuid4().hex[:12]
            payload = json.dumps({"event": event_type, "description": description})
            self.db.conn.execute(
                "INSERT INTO operation_events (id, event_type, data_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (ev_id, event_type, payload, now),
            )
            self.db.conn.execute(
                "DELETE FROM operation_events WHERE id NOT IN ("
                "SELECT id FROM operation_events ORDER BY created_at DESC LIMIT ?"
                ")",
                (MAX_OPERATION_EVENTS,),
            )
            self.db.conn.commit()
        except Exception as e:
            logger.debug("Audit log write failed: %s", e)

    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.db.conn.execute(
            "SELECT * FROM operation_events WHERE event_type LIKE 'document.%' "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return self.db.rows_to_dicts(rows)

    # ── Migration ──────────────────────────────────────────────────────

    def migrate_existing_attachments(self) -> int:
        rows = self.db.rows_to_dicts(
            self.db.conn.execute(
                "SELECT id, truck_id, maintenance_type, date, attachment_path "
                "FROM maintenance_records "
                "WHERE attachment_path IS NOT NULL AND attachment_path != ''"
            ).fetchall()
        )
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

    # ── P2: FTS5 Full-Text Search ───────────────────────────────────

    def fts_search(self, query: str = "", category: str = "",
                   entity_type: str = "", order: str = "uploaded_at DESC",
                   page: int = 0, page_size: int = 20) -> Dict[str, Any]:
        offset = page * page_size
        if query:
            total = self._repo.fts_search_count(query, category, entity_type)
            rows = self._repo.fts_search(query, category, entity_type, order, page_size, offset)
        else:
            total = self._repo.advanced_search_count(query, category, entity_type)
            rows = self._repo.advanced_search(query, category, entity_type, order=order,
                                              limit=page_size, offset=offset)
        return {
            "items": rows, "total": total, "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    # ── P2: OCR Text Extraction ─────────────────────────────────────

    def extract_text(self, file_path: str, mime_type: str) -> str:
        if not os.path.isfile(file_path):
            return ""
        try:
            if mime_type == "application/pdf":
                return self._extract_pdf_text(file_path)
            elif mime_type.startswith("image/"):
                return self._extract_image_text(file_path)
        except Exception as e:
            logger.debug("OCR extraction skipped for %s: %s", file_path, e)
        return ""

    def _extract_pdf_text(self, file_path: str) -> str:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            parts = []
            for page in reader.pages[:5]:
                txt = page.extract_text()
                if txt:
                    parts.append(txt)
            return "\n".join(parts)[:MAX_OCR_TEXT_LENGTH]
        except Exception:
            return ""

    def _extract_image_text(self, file_path: str) -> str:
        try:
            from PIL import Image
            import pytesseract
            with Image.open(file_path) as img:
                return pytesseract.image_to_string(img)[:MAX_OCR_TEXT_LENGTH]
        except (ImportError, Exception):
            return ""

    # ── P2: Document Expiration ─────────────────────────────────────

    def set_expiry_date(self, doc_id: int, expiry_date: str) -> None:
        self._repo.update(doc_id, expiry_date=expiry_date,
                          updated_at=datetime.now().isoformat())

    def get_expiring(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        return self._repo.get_expiring_documents(days_ahead)

    def get_overdue(self) -> List[Dict[str, Any]]:
        return self._repo.get_overdue_documents()

    def evaluate_document_expiries(self, alert_mgr=None, db=None) -> int:
        if alert_mgr is None:
            from services.operations.alert_manager import AlertManager, AlertType, Severity
            alert_mgr = AlertManager()
        count = 0
        overdue = self.get_overdue()
        for doc in overdue:
            alert_mgr.create_alert(
                alert_type=AlertType.DOCUMENT_EXPIRY.value if hasattr(AlertType, 'DOCUMENT_EXPIRY') else "document_expiry",
                severity=Severity.CRITICAL.value,
                title=f"Document expired: {doc.get('title', doc.get('file_name', ''))}",
                message=f"Document {doc.get('doc_number')} expired on {doc.get('expiry_date')}",
                truck_id=None,
                trip_id=None,
                metadata={"document_id": doc["id"], "doc_number": doc.get("doc_number", "")},
            )
            count += 1
        expiring = self.get_expiring(30)
        for doc in expiring:
            alert_mgr.create_alert(
                alert_type=AlertType.DOCUMENT_EXPIRY.value if hasattr(AlertType, 'DOCUMENT_EXPIRY') else "document_expiry",
                severity=Severity.WARNING.value,
                title=f"Document expiring: {doc.get('title', doc.get('file_name', ''))}",
                message=f"Document {doc.get('doc_number')} expires on {doc.get('expiry_date')}",
                truck_id=None, trip_id=None,
                metadata={"document_id": doc["id"], "doc_number": doc.get("doc_number", "")},
            )
            count += 1
        return count

    # ── P2: Document Versioning ─────────────────────────────────────

    def get_versions(self, doc_id: int) -> List[Dict[str, Any]]:
        return self._repo.get_versions(doc_id)

    def upload_new_version(self, doc_id: int, source_path: str,
                           comment: str = "", uploaded_by: str = "") -> Optional[int]:
        doc = self._repo.get_by_id(doc_id)
        if not doc:
            return None
        valid, err = self.validate_file(source_path)
        if not valid:
            raise ValueError(err)

        count = self._repo.get_version_count(doc_id)
        next_ver = count + 1

        versions = self._repo.get_versions(doc_id)
        while len(versions) >= MAX_VERSIONS_PER_DOC:
            oldest = versions[-1]
            try:
                if os.path.isfile(oldest["file_path"]):
                    os.remove(oldest["file_path"])
            except OSError:
                pass
            self._repo._execute(
                "DELETE FROM document_versions WHERE id = ?", (oldest["id"],),
            )
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

    # ── P2: Contracts ───────────────────────────────────────────────

    def create_contract(self, doc_id: int, client_id: int,
                        contract_type: str = "transport",
                        start_date: str = "", end_date: str = "",
                        value_eur: float = 0, payment_terms: str = "",
                        auto_renewal: bool = False,
                        renewal_notice_days: int = 30,
                        notes: str = "") -> int:
        now = datetime.now().isoformat()
        return self._repo.create_contract(
            doc_id, client_id, contract_type, start_date, end_date,
            value_eur, payment_terms, 1 if auto_renewal else 0,
            renewal_notice_days, notes, now, now,
        )

    def get_contracts(self, client_id: Optional[int] = None,
                      status: str = "") -> List[Dict[str, Any]]:
        return self._repo.get_contracts(client_id, status)

    def get_contract(self, contract_id: int) -> Optional[Dict[str, Any]]:
        return self._repo.get_contract_by_id(contract_id)

    def update_contract_status(self, contract_id: int, status: str) -> None:
        now = datetime.now().isoformat()
        self._repo.update_contract(contract_id, status=status, updated_at=now)

    def get_expiring_contracts(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        return self._repo.get_expiring_contracts(days_ahead)

    # ── P2: Templates ───────────────────────────────────────────────

    def create_template(self, name: str, description: str = "",
                        category: str = "general",
                        template_type: str = "pdf",
                        fields: Optional[List[Dict]] = None) -> int:
        now = datetime.now().isoformat()
        fields_json = json.dumps(fields if fields else [])
        return self._repo.create_template(
            name, description, category, template_type, fields_json, now, now,
        )

    def get_templates(self, category: str = "") -> List[Dict[str, Any]]:
        return self._repo.get_templates(category)

    def generate_from_template(self, template_id: int,
                               context: Dict[str, str],
                               output_dir: str = "") -> Optional[str]:
        template_rec = self._repo.get_template_by_id(template_id)
        if not template_rec:
            return None

        fields = json.loads(template_rec.get("fields_json", "[]"))
        cat = template_rec["category"]
        ttype = template_rec["template_type"]

        if cat == "cmr" and ttype == "pdf":
            from services.invoicing.cmr_generator import CMRGenerator
            gen = CMRGenerator(db=self.db)
            if not output_dir:
                output_dir = os.path.join(DOCUMENTS_ROOT, "trips")
            os.makedirs(output_dir, exist_ok=True)
            trip_id = context.get("trip_id", "unknown")
            filepath = gen.generate(context, output_dir)
            return filepath

        if cat == "contract" and ttype == "pdf":
            return self._generate_contract_pdf(context, output_dir)

        return None

    def _generate_contract_pdf(self, context: Dict[str, str],
                               output_dir: str) -> Optional[str]:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import cm

        os.makedirs(output_dir, exist_ok=True)
        filename = f"Contract_{context.get('client_name', 'Unknown')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        filepath = os.path.join(output_dir, filename)

        doc = SimpleDocTemplate(filepath, pagesize=A4,
                                leftMargin=1.5*cm, rightMargin=1.5*cm,
                                topMargin=1.5*cm, bottomMargin=1.5*cm)
        styles = getSampleStyleSheet()
        story = []
        title_style = ParagraphStyle("CTitle", parent=styles["Title"],
                                     fontSize=18, textColor=colors.HexColor("#1a73e8"))
        story.append(Paragraph("<b>CONTRACT</b>", title_style))
        story.append(Spacer(1, 0.5*cm))

        for k, v in context.items():
            story.append(Paragraph(f"<b>{k}:</b> {v}", styles["Normal"]))
            story.append(Spacer(1, 0.2*cm))

        story.append(Spacer(1, 2*cm))
        story.append(Paragraph("Signed: ________________    Date: ________________", styles["Normal"]))
        doc.build(story)
        return filepath

    # ── P2: Rebuild FTS index ───────────────────────────────────────

    def rebuild_fts(self) -> None:
        self._repo.rebuild_fts_index()

    # ── Helpers ────────────────────────────────────────────────────────

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
    def _ensure_category_dir(category: str) -> str:
        d = os.path.join(DOCUMENTS_ROOT, category)
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
