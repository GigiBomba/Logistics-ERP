"""Document Center service — upload, search, link management.

This module is maintained as a backward-compatible facade that delegates
to focused services under ``services/document/``.

New code should use the focused services directly.
"""
import contextlib
import json
import logging
import os
import warnings
import zipfile
from datetime import datetime
from typing import Any, Dict, Optional

from database.db_manager import DatabaseManager
from models.common import ErrorDetail, ServiceResult
from models.document_models import (
    DocumentListResult,
    DocumentResult,
    DocumentUpload,
    DocumentUploadResult,
)
from repositories.audit_repository import AuditRepository
from repositories.document_repository import DocumentRepository
from services.operations.event_bus import (
    DOCUMENT_ARCHIVED,
    DOCUMENT_DELETED,
    DOCUMENT_LINKED,
    DOCUMENT_UNLINKED,
    EventBus,
)
from services.permission_service import PermissionService

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
        self._perm = PermissionService(db)
        self._services: dict = {}
        self._cache: Any = None

    def _get_cache(self):
        if self._cache is None:
            try:
                from backend.cache import get_cache
                self._cache = get_cache()
            except (ImportError, OSError, ValueError):
                logger.debug("Cache backend unavailable, disabling cache")
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

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _to_document_result(doc: dict[str, Any]) -> DocumentResult:
        """Convert a repository dict to a typed DocumentResult."""
        tags_raw = doc.get("tags", "[]")
        if isinstance(tags_raw, str):
            try:
                tags = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                tags = []
        else:
            tags = tags_raw or []

        return DocumentResult(
            id=doc["id"],
            title=doc.get("title", ""),
            category=doc.get("category", ""),
            entity_type=doc.get("entity_type", ""),
            entity_id=doc.get("entity_id"),
            filename=doc.get("file_name", ""),
            file_size=doc.get("file_size", 0),
            mime_type=doc.get("mime_type", ""),
            tags=tags,
            description=doc.get("description", ""),
            ocr_processed=bool(doc.get("ocr_run_at")),
            thumbnail_path=doc.get("thumbnail_path"),
            created_at=doc.get("uploaded_at"),
            updated_at=doc.get("updated_at"),
        )

    @staticmethod
    def _result_error(msg: str, code: str = "ERROR") -> ServiceResult:
        return ServiceResult(success=False, errors=[ErrorDetail(message=msg, code=code)])

    @staticmethod
    def _result_ok(data) -> ServiceResult:
        return ServiceResult(success=True, data=data)

    # ── Typed API ───────────────────────────────────────────────────────

    def upload_document(self, request: DocumentUpload, user_id: int,
                        company_id=None) -> DocumentUploadResult:
        """Upload a document using a typed request model.

        Args:
            request: The document upload details.
            user_id: The ID of the user performing the upload.
            company_id: Optional JWT-derived tenant id.  When provided the
                document row is **created** company-scoped in the same
                INSERT — there is no post-insert UPDATE window where the
                row exists unscoped (blueprint §1.8 / M2).

        Returns:
            A ``ServiceResult`` containing the uploaded document details,
            or an error result if the upload fails.
        """
        perm = self._perm.can_upload_document(user_id)
        if not perm.allowed:
            return self._result_error(perm.reason, "FORBIDDEN")

        try:
            doc_id = self.upload_svc.upload(
                source_path=request.source_path,
                title=request.title,
                category=request.category,
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                description=request.description,
                tags=request.tags,
                uploaded_by=str(user_id),
                company_id=company_id,
            )
        except (FileNotFoundError, ValueError, OSError) as exc:
            logger.error("Upload failed for %s: %s", request.source_path, exc)
            return self._result_error(str(exc), "UPLOAD_FAILED")

        if doc_id:
            doc = self._repo.get_by_id(doc_id)
            if doc:
                file_path = doc.get("file_path", "")
                mime_type = doc.get("mime_type", "")
                if file_path and (mime_type == "application/pdf" or mime_type.startswith("image/")):
                    self.ocr.enqueue_ocr(doc_id, file_path, mime_type)
                logger.info(
                    "Document uploaded: id=%d title=%s category=%s by user=%d",
                    doc_id, request.title, request.category, user_id,
                )
                return self._result_ok(self._to_document_result(doc))

        return self._result_error("Upload returned no document ID", "UPLOAD_FAILED")

    def get(self, document_id: int) -> DocumentUploadResult:
        """Retrieve a single document by ID.

        Args:
            document_id: The document ID.

        Returns:
            A ``ServiceResult`` containing the document, or an error if not found.
        """
        doc = self.get_by_id(document_id)
        if not doc:
            return self._result_error(f"Document {document_id} not found", "NOT_FOUND")
        return self._result_ok(self._to_document_result(doc))

    def list_all(self, entity_type: str = "",
                 entity_id: Optional[int] = None) -> DocumentListResult:
        """List documents, optionally filtered by entity.

        Args:
            entity_type: Filter by entity type (e.g. "trip", "client").
            entity_id: Filter by entity ID.

        Returns:
            A ``ServiceResult`` containing a list of documents.
        """
        if entity_type and entity_id is not None:
            docs = self._repo.get_documents_for_entity(entity_type, entity_id)
        else:
            # Use the search service to fetch all non-archived documents
            result = self.search_svc.search(
                query="", category="", entity_type="",
                entity_id=None, order="uploaded_at DESC",
                page=0, page_size=10000,
            )
            docs = result.get("items", [])

        results = [self._to_document_result(d) for d in docs]
        return self._result_ok(results)

    def delete_document(self, document_id: int, user_id: int) -> DocumentUploadResult:
        """Delete a document by ID.

        Args:
            document_id: The document ID to delete.
            user_id: The ID of the user requesting deletion.

        Returns:
            A ``ServiceResult`` containing the deleted document details,
            or an error if deletion fails.
        """
        perm = self._perm.can_delete_document(user_id)
        if not perm.allowed:
            return self._result_error(perm.reason, "FORBIDDEN")

        doc = self._repo.get_by_id(document_id)
        if not doc:
            return self._result_error(f"Document {document_id} not found", "NOT_FOUND")

        result = self._to_document_result(doc)

        # -- inline deletion logic (old delete implementation) --
        if doc.get("file_path"):
            try:
                if os.path.isfile(doc["file_path"]):
                    os.remove(doc["file_path"])
            except OSError as e:
                logger.warning("Failed to delete file %s: %s", doc["file_path"], e)
        self._cleanup_thumbnails(document_id)
        self._cleanup_versions(document_id)
        self._repo.remove_all_links(document_id)
        self._repo.delete(document_id)
        cache = self._get_cache()
        if cache:
            cache.delete(self._cache_key(document_id))
            cache.flush_pattern("doc:*")
        self._event_bus.publish(DOCUMENT_DELETED, {"document_id": document_id})
        self._log_audit("document.deleted", f"Deleted document {document_id}")

        logger.info("Document deleted: id=%d by user=%d", document_id, user_id)
        return self._result_ok(result)

    def email_document(self, document_id: int, recipient: str, user_id: int,
                       prefs: Optional[Dict[str, Any]] = None) -> ServiceResult[bool]:
        """Email a document to a recipient.

        Args:
            document_id: The document ID to email.
            recipient: The email address of the recipient.
            user_id: The ID of the user sending the email.
            prefs: Optional caller-supplied preferences used to resolve the
                SMTP config.  Accepts either a ``PreferencesManager``-like
                object exposing ``get_smtp_config()`` (as the desktop UI
                passes) or a dict of SMTP settings (as the Celery task
                passes).  When provided, its SMTP config takes precedence
                over the DB-backed preferences store.

        Returns:
            A ``ServiceResult[bool]`` indicating success or failure.
        """
        perm = self._perm.can_email_document(user_id)
        if not perm.allowed:
            return ServiceResult(success=False, errors=[ErrorDetail(message=perm.reason, code="FORBIDDEN")])

        doc = self._repo.get_by_id(document_id)
        if not doc or not os.path.isfile(doc.get("file_path", "")):
            return ServiceResult(success=False, errors=[ErrorDetail(
                message="Document file not found", code="FILE_NOT_FOUND",
            )])

        from services.operations.notification_center import NotificationCenter
        nc = NotificationCenter(self.db)
        # SMTP config: prefer caller-supplied prefs (per-user/company SMTP),
        # falling back to the DB-backed preferences store.
        smtp_config = None
        if prefs is not None:
            try:
                if hasattr(prefs, "get_smtp_config"):
                    smtp_config = prefs.get_smtp_config()
                elif isinstance(prefs, dict):
                    smtp_config = prefs
            except (OSError, ValueError, AttributeError):
                logger.debug("Failed to load SMTP config from passed prefs")
                smtp_config = None
        if not smtp_config:
            try:
                from services.preferences import PreferencesManager
                prefs_svc = PreferencesManager(self.db)
                smtp_config = prefs_svc.get_smtp_config()
            except (ImportError, OSError, ValueError):
                logger.debug("Failed to load SMTP config from preferences")
                smtp_config = None

        if not smtp_config or not smtp_config.get("smtp_server"):
            return ServiceResult(success=False, errors=[ErrorDetail(
                message="SMTP not configured", code="SMTP_NOT_CONFIGURED",
            )])

        nc.configure_smtp(
            smtp_config.get("smtp_server", ""),
            int(smtp_config.get("smtp_port", "587")),
            smtp_config.get("smtp_user", ""),
            smtp_config.get("smtp_password", ""),
        )
        subject = f"Document: {doc.get('title', doc.get('file_name', ''))}"
        body = f"Please find attached: {doc.get('title', '')}\n\nDocument ID: {doc.get('doc_number', '')}"
        result = nc.send_email(recipient, subject, body, attachments=[doc["file_path"]])
        ok = bool(result) if hasattr(result, "success") else bool(result)
        if ok:
            self._log_audit("document.emailed", f"Emailed {doc.get('doc_number')} to {recipient}")
            logger.info("Document emailed: id=%d to=%s by user=%d", document_id, recipient, user_id)
        return ServiceResult(success=ok, data=result)

    def link_to_entity(self, document_id: int, entity_type: str,
                       entity_id: int) -> DocumentUploadResult:
        """Link a document to an entity.

        Args:
            document_id: The document ID.
            entity_type: The entity type (e.g. "trip", "client").
            entity_id: The entity ID.

        Returns:
            A ``ServiceResult`` containing the linked document details.
        """
        ok = self.link_document(document_id, entity_type, entity_id)
        if not ok:
            return self._result_error(
                f"Failed to link document {document_id} to {entity_type}:{entity_id}",
                "LINK_FAILED",
            )
        return self.get(document_id)

    # ── Backward-compatible wrappers (deprecated) ───────────────────────

    def upload(self, source_path: str, title: str = "",
               category: str = "", entity_type: str = "",
               entity_id: Optional[int] = None,
               description: str = "", tags: Optional[list[str]] = None,
               uploaded_by: str = "", company_id=None) -> Optional[int]:
        """DEPRECATED: Use ``upload_document(DocumentUpload, user_id)`` instead."""
        warnings.warn(
            "upload(source_path, ...) is deprecated; use upload_document(DocumentUpload, user_id)",
            DeprecationWarning, stacklevel=2,
        )
        return self.upload_legacy(
            source_path, title=title, category=category,
            entity_type=entity_type, entity_id=entity_id,
            description=description, tags=tags, uploaded_by=uploaded_by,
        )

    def delete(self, doc_id: int) -> bool:
        """DEPRECATED: Use ``delete_document(document_id, user_id)`` instead."""
        warnings.warn(
            "delete(doc_id) is deprecated; use delete_document(document_id, user_id)",
            DeprecationWarning, stacklevel=2,
        )
        return self.delete_legacy(doc_id)

    def upload_legacy(self, source_path: str, title: str = "",
                      category: str = "", entity_type: str = "",
                      entity_id: Optional[int] = None,
                      description: str = "", tags: Optional[list[str]] = None,
                      uploaded_by: str = "") -> Optional[int]:
        """Legacy kwargs-based upload (called by deprecated ``upload()`` wrapper)."""
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
                        page: int = 0, page_size: int = 20,
                        company_id=None) -> dict[str, Any]:
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

    def get_by_id(self, doc_id: int, company_id=None) -> Optional[dict[str, Any]]:
        """Fetch a document by ID, optionally tenant-checked.

        ``company_id`` (the JWT-derived company, per blueprint §1.8) is
        honored when provided: a document belonging to a different company
        is treated as not found.  When ``company_id`` is falsy (admin /
        desktop flows) the document is returned unscoped.

        Tenant-checked reads always hit the database — the shared cache key
        is company-blind (``doc:<id>``), so a cached copy written by another
        company could otherwise be served across tenants.
        """
        cache = self._get_cache()
        doc = None
        if not company_id and cache:
            cached = cache.get(self._cache_key(doc_id))
            if cached is not None:
                doc = cached
        if doc is None:
            doc = self._repo.get_by_id(doc_id)
            if doc and not company_id and cache:
                cache.set(self._cache_key(doc_id), doc, ttl=300)
        # Tenant check at read time — never leak a document across companies.
        if doc and company_id and doc.get("company_id") != company_id:
            return None
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

    def delete_legacy(self, doc_id: int) -> bool:
        """Legacy delete (called by deprecated ``delete()`` wrapper)."""
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

    # ── Email (deprecated) ─────────────────────────────────────────────

    def email_document_legacy(self, doc_id: int, recipient: str,
                              smtp_config: Optional[dict[str, str]] = None,
                              prefs=None) -> bool:
        """DEPRECATED: Use ``email_document(document_id, recipient, user_id)`` instead."""
        warnings.warn(
            "email_document(doc_id, recipient, smtp_config=, prefs=) is deprecated; "
            "use email_document(document_id, recipient, user_id)",
            DeprecationWarning, stacklevel=2,
        )
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
        except (OSError, ValueError, ImportError, RuntimeError) as e:
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
        except (ImportError, OSError, RuntimeError, ValueError):
            logger.debug("PyMuPDF thumbnail failed for %s, using placeholder", pdf_path)

        # Fallback: placeholder with page count
        try:
            from PIL import Image, ImageDraw
            from pypdf import PdfReader
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
        except (OSError, ValueError, RuntimeError):
            logger.debug("Fallback PDF thumbnail failed for %s", pdf_path)
            return None

    # ── Audit Log ──────────────────────────────────────────────────────

    def _log_audit(self, event_type: str, description: str) -> None:
        # Backward-compatible wrapper: extract entity_type from event_type prefix
        entity_type = event_type.split(".")[0] if "." in event_type else ""
        self._audit_repo.log_event(
            event_type=event_type,
            entity_type=entity_type,
            data={"description": description},
        )

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
