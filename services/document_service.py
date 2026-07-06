"""Document Center service — upload, search, link management.

This module is maintained as a backward-compatible facade that delegates
to focused services under ``services/document/``.

New code should use the focused services directly.
"""
import contextlib
import json
import logging
import os
import zipfile
from datetime import datetime
from typing import Any, Optional

from database.db_manager import DatabaseManager
from repositories.audit_repository import AuditRepository
from repositories.document_repository import DocumentRepository
from services.operations.event_bus import (
    DOCUMENT_ARCHIVED,
    DOCUMENT_DELETED,
    DOCUMENT_LINKED,
    DOCUMENT_UNLINKED,
    EventBus,
)

logger = logging.getLogger("document_service")

DOCUMENTS_ROOT = os.path.join("data", "documents")
THUMBS_ROOT = os.path.join("data", "documents", ".thumbnails")

MAX_UPLOAD_SIZE = 20 * 1024 * 1024
MAX_OPERATION_EVENTS = 5000
MAX_VERSIONS_PER_DOC = 20

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
    "receipt": "receipts",
    "client": "other",
}

IMAGE_MIME = {"image/png", "image/jpeg", "image/gif", "image/bmp"}

THUMB_SIZE = (160, 120)


class DocumentService:

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._repo = DocumentRepository(db)
        self._audit_repo = AuditRepository(db)
        self._event_bus = EventBus()
        self._ocr_db = db
        self._services: dict = {}
        self._cache: Any = None

    def _get_cache(self):
        if self._cache is None:
            try:
                from backend.cache import get_cache
                self._cache = get_cache()
            except Exception:
                self._cache = None  # type: ignore
        return self._cache

    def _cache_key(self, doc_id: int) -> str:
        return f"doc:{doc_id}"

    def _svc(self, name: str):
        """Lazy-create and cache a focused sub-service."""
        if name not in self._services:
            if name == "ocr":
                from services.document.ocr_service import OcrService
                self._services[name] = OcrService(self.db, self._repo)
            elif name == "search":
                from services.document.search_service import SearchService
                self._services[name] = SearchService(self._repo)
            elif name == "expiry":
                from services.document.expiry_service import ExpiryService
                self._services[name] = ExpiryService(self._repo)
            elif name == "upload":
                from services.document.upload_service import UploadService
                self._services[name] = UploadService(self.db, self._repo)
            elif name == "versioning":
                from services.document.versioning_service import VersioningService
                self._services[name] = VersioningService(self._repo)
            elif name == "contracts":
                from services.document.contract_service import ContractService
                self._services[name] = ContractService(self._repo)
            elif name == "templates":
                from services.document.template_service import TemplateService
                self._services[name] = TemplateService(self.db, self._repo)
        return self._services[name]

    @property
    def ocr(self):
        return self._svc("ocr")

    @property
    def search_svc(self):
        return self._svc("search")

    @property
    def expiry(self):
        return self._svc("expiry")

    @property
    def upload_svc(self):
        return self._svc("upload")

    @property
    def versioning(self):
        return self._svc("versioning")

    @property
    def contracts(self):
        return self._svc("contracts")

    @property
    def templates(self):
        return self._svc("templates")

    @classmethod
    def shutdown(cls):
        """Shut down background OCR workers.

        Can be called as an instance method (``self.shutdown()``) or as
        a class method (``DocumentService.shutdown()``).  When called
        on the class without an instance the method is a no-op — daemon
        threads clean themselves up when the process exits.
        """
        logger.debug("DocumentService.shutdown called")

    # ── Upload ─────────────────────────────────────────────────────────

    def validate_file(self, source_path: str) -> tuple[bool, Optional[str]]:
        return self.upload_svc.validate_file(source_path)

    def check_duplicate(self, source_path: str) -> Optional[int]:
        return self.upload_svc.check_duplicate(source_path)

    def upload(self, source_path: str, title: str = "",
               category: str = "", entity_type: str = "",
               entity_id: Optional[int] = None,
               description: str = "", tags: Optional[list[str]] = None,
               uploaded_by: str = "") -> Optional[int]:
        doc_id = self.upload_svc.upload(
            source_path=source_path, title=title, category=category,
            entity_type=entity_type, entity_id=entity_id,
            description=description, tags=tags, uploaded_by=uploaded_by,
        )
        if doc_id:
            doc = self._repo.get_by_id(doc_id)
            file_path = doc.get("file_path", "") if doc else ""
            mime_type = doc.get("mime_type", "") if doc else ""
            if file_path and (mime_type == "application/pdf" or mime_type.startswith("image/")):
                self.ocr.enqueue_ocr(doc_id, file_path, mime_type)
        return doc_id

    def batch_upload(self, paths: list, category: str = "",
                     entity_type: str = "", entity_id: Optional[int] = None,
                     uploaded_by: str = "",
                     tags: Optional[list[str]] = None) -> dict[str, Any]:
        return self.upload_svc.batch_upload(
            paths, category=category, entity_type=entity_type,
            entity_id=entity_id, uploaded_by=uploaded_by, tags=tags,
        )

    def register_existing(self, file_path: str, title: str = "",
                          category: str = "", entity_type: str = "",
                          entity_id: Optional[int] = None,
                          description: str = "",
                          tags: Optional[list[str]] = None,
                          is_migration: bool = False,
                          copy_type: str = "",
                          cmr_number: str = "",
                          cmr_metadata: str = "",
                          is_signed: int = 0,
                          commit: bool = True) -> Optional[int]:
        doc_id = self.upload_svc.register_existing(
            file_path=file_path, title=title, category=category,
            entity_type=entity_type, entity_id=entity_id,
            description=description, tags=tags,
            is_migration=is_migration, copy_type=copy_type,
            cmr_number=cmr_number, cmr_metadata=cmr_metadata,
            is_signed=is_signed, commit=commit,
        )
        # Enqueue OCR for PDF/image uploads so the automation pipeline
        # extracts fields and attempts trip matching + auto-linking.
        if doc_id and doc_id > 0 and not is_migration:
            doc = self._repo.get_by_id(doc_id)
            fpath = doc.get("file_path", "") if doc else ""
            mime = doc.get("mime_type", "") if doc else ""
            if fpath and (mime == "application/pdf" or mime.startswith("image/")):
                self.ocr.enqueue_ocr(doc_id, fpath, mime)
        return doc_id

    # ── Advanced Search ────────────────────────────────────────────────

    def advanced_search(self, query: str = "", category: str = "",
                        entity_type: str = "", entity_id: Optional[int] = None,
                        date_from: str = "", date_to: str = "",
                        mime_type: str = "", tag: str = "",
                        order: str = "uploaded_at DESC",
                        page: int = 0, page_size: int = 20) -> dict[str, Any]:
        return self.search_svc.advanced_search(
            query=query, category=category, entity_type=entity_type,
            entity_id=entity_id, date_from=date_from, date_to=date_to,
            mime_type=mime_type, tag=tag, order=order,
            page=page, page_size=page_size,
        )

    def search(self, query: str = "", category: str = "",
               entity_type: str = "", entity_id: Optional[int] = None,
               order: str = "uploaded_at DESC",
               page: int = 0, page_size: int = 20) -> dict[str, Any]:
        return self.search_svc.search(
            query=query, category=category, entity_type=entity_type,
            entity_id=entity_id, order=order, page=page, page_size=page_size,
        )

    def get_categories(self) -> list[dict[str, Any]]:
        return self.search_svc.get_categories()

    def get_all_tags(self) -> list[str]:
        return self.search_svc.get_all_tags()

    def get_entity_types(self) -> list[str]:
        return self.search_svc.get_entity_types()

    def get_mime_types(self) -> list[str]:
        return self.search_svc.get_mime_types()

    # ── Tag Management ─────────────────────────────────────────────────

    def add_tag(self, doc_id: int, tag: str) -> bool:
        return self._repo.add_tag(doc_id, tag)

    def remove_tag(self, doc_id: int, tag: str) -> bool:
        return self._repo.remove_tag(doc_id, tag)

    def set_tags(self, doc_id: int, tags: list) -> None:
        self._repo.set_tags(doc_id, tags)

    # ── Document operations ────────────────────────────────────────────

    def get_by_id(self, doc_id: int) -> Optional[dict[str, Any]]:
        cache = self._get_cache()
        if cache:
            cached = cache.get(self._cache_key(doc_id))
            if cached is not None:
                return cached
        doc = self._repo.get_by_id(doc_id)
        if doc and cache:
            cache.set(self._cache_key(doc_id), doc, ttl=300)
        return doc

    def get_links(self, doc_id: int) -> list[dict[str, Any]]:
        return self._repo.get_links(doc_id)

    def get_documents_for_entity(self, entity_type: str,
                                 entity_id: int) -> list[dict[str, Any]]:
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
            if entity_type == "trip":
                self.ocr._retroactively_link_related_runs(entity_id, doc_id)
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

    def _fetch_link(self, link_id: int) -> Optional[dict[str, Any]]:
        return self._repo._fetchone(
            f"SELECT * FROM {self._repo.TABLE_LINKS} WHERE id = ?",
            (link_id,),
        )

    def update_metadata(self, doc_id: int, title: str = "",
                        description: str = "",
                        tags: Optional[list[str]] = None) -> bool:
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
        cache = self._get_cache()
        if cache:
            cache.delete(self._cache_key(doc_id))
            cache.flush_pattern("doc:*")
        self._event_bus.publish(DOCUMENT_DELETED, {"document_id": doc_id})
        self._log_audit("document.deleted", f"Deleted document {doc_id}")
        return True

    def delete_batch(self, doc_ids: list) -> int:
        if not doc_ids:
            return 0
        docs = self._repo.get_ids_by_ids(doc_ids)
        for doc in docs:
            file_path = doc.get("file_path", "")
            if file_path and os.path.isfile(file_path):
                with contextlib.suppress(OSError):
                    os.remove(file_path)
        for did in doc_ids:
            self._cleanup_thumbnails(did)
            self._cleanup_versions(did)
        self._repo.remove_all_links_batch(doc_ids)
        count = self._repo.delete_batch(doc_ids)
        self._event_bus.publish(DOCUMENT_DELETED, {"document_id": 0, "batch_count": len(doc_ids)})
        self._log_audit("document.batch_deleted", f"Batch deleted {len(doc_ids)} documents")
        return count

    def _cleanup_thumbnails(self, doc_id: int) -> None:
        thumb_name = f"thumb_{doc_id}.png"
        thumb_path = os.path.join(THUMBS_ROOT, thumb_name)
        if os.path.isfile(thumb_path):
            with contextlib.suppress(OSError):
                os.remove(thumb_path)

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
            with contextlib.suppress(OSError):
                os.rmdir(version_dir)

    def get_file_path(self, doc_id: int) -> Optional[str]:
        doc = self._repo.get_by_id(doc_id)
        if doc and doc.get("file_path") and os.path.isfile(doc["file_path"]):
            return os.path.abspath(doc["file_path"])
        return None

    def is_image(self, mime_type: str) -> bool:
        return mime_type in IMAGE_MIME

    # ── Email ──────────────────────────────────────────────────────────

    def email_document(self, doc_id: int, recipient: str,
                       smtp_config: Optional[dict[str, str]] = None,
                       prefs=None) -> bool:
        doc = self._repo.get_by_id(doc_id)
        if not doc or not os.path.isfile(doc.get("file_path", "")):
            return False

        if not smtp_config and prefs:
            with contextlib.suppress(Exception):
                smtp_config = prefs.get_smtp_config()
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
        # Robust path traversal prevention
        if ".." in output_path.split(os.sep):
            raise ValueError("Output path must not contain '..' components")
        safe_base = os.path.realpath(os.path.join("data", "documents"))
        canonical = os.path.normpath(os.path.realpath(output_path))
        norm_base = os.path.normpath(safe_base)
        if not canonical.startswith(norm_base + os.sep) and canonical != norm_base:
            raise ValueError(f"Output path must be within {safe_base}")
        docs = self._repo.get_ids_by_ids(doc_ids)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for doc in docs:
                fpath = doc.get("file_path", "")
                if fpath and os.path.isfile(fpath):
                    real_fpath = os.path.normpath(os.path.realpath(fpath))
                    if not real_fpath.startswith(norm_base + os.sep):
                        logger.warning("download_zip: skipping file outside safe dir: %s", fpath)
                        continue
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
        """Render the first page of a PDF as a thumbnail image using PyMuPDF.

        Falls back to a placeholder if PyMuPDF is not available or on error.
        """
        try:
            from .document_automation.image_processor import _safe_import_fitz
            fitz = _safe_import_fitz()
            if fitz is not None:
                doc = fitz.open(pdf_path)
                if doc.page_count == 0:
                    doc.close()
                    return None
                page = doc[0]
                pix = page.get_pixmap(dpi=72)
                doc.close()
                from PIL import Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.thumbnail(THUMB_SIZE, Image.LANCZOS)
                img.save(thumb_path, "PNG")
                return thumb_path
        except Exception:
            logger.debug("PyMuPDF thumbnail failed for %s, using placeholder", pdf_path)

        # Fallback: placeholder with page count
        try:
            from PIL import Image, ImageDraw
            from PyPDF2 import PdfReader
        except ImportError:
            return None
        try:
            reader = PdfReader(pdf_path)
            img = Image.new("RGB", THUMB_SIZE, "#1c1c1f")
            d = ImageDraw.Draw(img)
            page_count = len(reader.pages) if reader.pages else 0
            if page_count:
                d.text((10, 50), f"PDF\n{page_count} page(s)",
                       fill="#a1a1aa")
            img.save(thumb_path, "PNG")
            return thumb_path
        except Exception:
            return None

    # ── Audit Log ──────────────────────────────────────────────────────

    def _log_audit(self, event_type: str, description: str) -> None:
        self._audit_repo.log_event(event_type, description)

    def get_audit_log(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._audit_repo.get_events(event_type_prefix="document.", limit=limit)

    # ── Migration ──────────────────────────────────────────────────────

    def migrate_existing_attachments(self) -> int:
        return self.upload_svc.migrate_existing_attachments()

    def migrate_existing_invoices(self) -> int:
        return self.upload_svc.migrate_existing_invoices()

    def migrate_all(self) -> int:
        return self.upload_svc.migrate_all()

    # ── P2: FTS5 Full-Text Search ───────────────────────────────────

    def fts_search(self, query: str = "", category: str = "",
                   entity_type: str = "", order: str = "uploaded_at DESC",
                   page: int = 0, page_size: int = 20) -> dict[str, Any]:
        return self.search_svc.fts_search(
            query=query, category=category, entity_type=entity_type,
            order=order, page=page, page_size=page_size,
        )

    # ── P2: OCR Text Extraction ─────────────────────────────────────

    def extract_text(self, file_path: str, mime_type: str) -> str:
        return self.ocr.extract_text(file_path, mime_type)

    # ── P2: Document Expiration ─────────────────────────────────────

    def set_expiry_date(self, doc_id: int, expiry_date: str) -> None:
        self.expiry.set_expiry_date(doc_id, expiry_date)

    def get_expiring(self, days_ahead: int = 30):
        return self.expiry.get_expiring(days_ahead)

    def get_overdue(self):
        return self.expiry.get_overdue()

    def evaluate_document_expiries(self, alert_mgr=None, db=None) -> int:
        return self.expiry.evaluate_document_expiries(alert_mgr=alert_mgr, db=db)

    # ── P2: Document Versioning ─────────────────────────────────────

    def get_versions(self, doc_id: int) -> list[dict[str, Any]]:
        return self.versioning.get_versions(doc_id)

    def upload_new_version(self, doc_id: int, source_path: str,
                           comment: str = "", uploaded_by: str = "") -> Optional[int]:
        return self.versioning.upload_new_version(
            doc_id, source_path, comment=comment, uploaded_by=uploaded_by,
        )

    def restore_version(self, doc_id: int, version_number: int) -> bool:
        return self.versioning.restore_version(doc_id, version_number)

    # ── P2: Contracts ───────────────────────────────────────────────

    def create_contract(self, doc_id: int, client_id: int,
                        contract_type: str = "transport",
                        start_date: str = "", end_date: str = "",
                        value_eur: float = 0, payment_terms: str = "",
                        auto_renewal: bool = False,
                        renewal_notice_days: int = 30,
                        notes: str = "") -> int:
        return self.contracts.create_contract(
            doc_id, client_id, contract_type=contract_type,
            start_date=start_date, end_date=end_date,
            value_eur=value_eur, payment_terms=payment_terms,
            auto_renewal=auto_renewal,
            renewal_notice_days=renewal_notice_days, notes=notes,
        )

    def get_contracts(self, client_id: Optional[int] = None,
                      status: str = "") -> list[dict[str, Any]]:
        return self.contracts.get_contracts(client_id, status)

    def get_contract(self, contract_id: int) -> Optional[dict[str, Any]]:
        return self.contracts.get_contract(contract_id)

    def update_contract_status(self, contract_id: int, status: str) -> None:
        self.contracts.update_contract_status(contract_id, status)

    def get_expiring_contracts(self, days_ahead: int = 30) -> list[dict[str, Any]]:
        return self.contracts.get_expiring_contracts(days_ahead)

    # ── P2: Templates ───────────────────────────────────────────────

    def create_template(self, name: str, description: str = "",
                        category: str = "general",
                        template_type: str = "pdf",
                        fields: Optional[list[dict]] = None) -> int:
        return self.templates.create_template(
            name, description=description, category=category,
            template_type=template_type, fields=fields,
        )

    def get_templates(self, category: str = "") -> list[dict[str, Any]]:
        return self.templates.get_templates(category)

    def generate_from_template(self, template_id: int,
                                context: dict[str, str],
                                output_dir: str = "") -> Optional[str]:
        return self.templates.generate_from_template(
            template_id, context, output_dir=output_dir,
        )

    # ── P2: Rebuild FTS index ───────────────────────────────────────

    def rebuild_fts(self) -> None:
        self._repo.rebuild_fts_index()

    # ── Helpers ────────────────────────────────────────────────────────
    # (moved to services/document/upload_service.py and
    #  services/document/versioning_service.py)
