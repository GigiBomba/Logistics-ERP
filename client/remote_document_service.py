"""API-backed document service wrapper for remote-only client mode.

Mirrors ``services.document_service.DocumentService`` so the Document
Center view (``ui/views/document_center/document_center.py``) can accept it
as a drop-in substitute when running without a local database.

Endpoint availability notes
---------------------------
The backend ``backend/api/v1/documents.py`` implements:
    GET    /documents/                  list/search (PaginatedResponse)
    GET    /documents/categories        categories + counts
    GET    /documents/{doc_id}          single document
    GET    /documents/{doc_id}/read     document + ocr + links + versions + expiry
    POST   /documents/upload            single-file upload
    PATCH  /documents/{doc_id}          metadata update (title/category/tags/
                                        description/expiry_date)
    DELETE /documents/{doc_id}          hard delete

It does NOT implement dedicated routes for links (POST/DELETE
``/documents/{id}/links``), tags, versions, expiry, zip download, email or
archive.  Where a dedicated route is missing this wrapper either:
  * uses the closest working endpoint (e.g. links/versions read from the
    ``read`` payload, tag/expiry writes via PATCH of the full field set), or
  * returns a graceful stub value and logs a warning (see the ``⚠`` notes).
"""

from __future__ import annotations

import json
import logging
import os
import zipfile
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("remote_document")

# Static facet lists used when the bounded facet scan finds nothing
# (the backend exposes no facet endpoints).
_KNOWN_ENTITY_TYPES = [
    "trip", "truck", "driver", "client",
    "invoice", "receipt", "maintenance", "other",
]
_KNOWN_MIME_TYPES = [
    "application/pdf", "image/jpeg", "image/png", "image/tiff",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain", "text/csv",
]
_IMAGE_MIME = {"image/png", "image/jpeg", "image/gif", "image/bmp", "image/tiff"}

_DEFAULT_PAGE_SIZE = 100


class RemoteDocumentService:
    """API-backed substitute for ``services.document_service.DocumentService``.

    Every public method mirrors the local service's name and signature so the
    Document Center view can swap implementations without changes.  Methods
    that cannot be performed over the API (local file operations, server-side
    version restore, etc.) return graceful stub values documented inline.
    """

    def __init__(self, api_client) -> None:
        self._api = api_client
        self._facet_cache: Optional[Dict[str, Any]] = None

    # ── Response normalisation ────────────────────────────────────────
    # The backend serialises ``tags`` as a JSON list and
    # ``extracted_data_json`` as a dict, but the local repository hands the
    # view JSON-encoded strings.  Normalise so ``json.loads`` in the view
    # keeps working.

    @staticmethod
    def _normalise_document(doc: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(doc, dict):
            return doc
        out = dict(doc)
        tags = out.get("tags")
        if isinstance(tags, list):
            out["tags"] = json.dumps(tags)
        extracted = out.get("extracted_data_json")
        if isinstance(extracted, dict):
            out["extracted_data_json"] = json.dumps(extracted)
        return out

    @staticmethod
    def _parse_tags(raw: Any) -> list:
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return []
        return list(raw) if raw else []

    def _items_from(self, resp: Any) -> List[Dict[str, Any]]:
        """Pull the ``items`` list out of a paginated API response."""
        if not isinstance(resp, dict):
            return []
        items = resp.get("items") or []
        return [self._normalise_document(d) for d in items if isinstance(d, dict)]

    def _scan_documents(self, max_pages: int = 10,
                        page_size: int = _DEFAULT_PAGE_SIZE) -> list[Dict[str, Any]]:
        """Page over all non-archived documents (bounded)."""
        docs: list[Dict[str, Any]] = []
        try:
            for page in range(max_pages):
                resp = self._api.list_documents(page=page, page_size=page_size)
                items = self._items_from(resp)
                if not items:
                    break
                docs.extend(items)
                if len(items) < page_size:
                    break
        except Exception:
            logger.debug("_scan_documents failed", exc_info=True)
        return docs

    # ── Facets ────────────────────────────────────────────────────────

    def _load_facets(self) -> Dict[str, Any]:
        """Best-effort facet scan: distinct entity/mime types + tags.

        The backend has no facet endpoints, so derive them by paging over
        recent documents (bounded).  Falls back to static known lists.
        """
        if self._facet_cache is not None:
            return self._facet_cache
        entity_types: set = set()
        mime_types: set = set()
        tags: set = set()
        try:
            for page in range(5):
                resp = self._api.list_documents(page=page, page_size=_DEFAULT_PAGE_SIZE)
                items = resp.get("items") or [] if isinstance(resp, dict) else []
                if not items:
                    break
                for doc in items:
                    et = doc.get("entity_type")
                    if et:
                        entity_types.add(et)
                    mt = doc.get("mime_type")
                    if mt:
                        mime_types.add(mt)
                    for tg in self._parse_tags(doc.get("tags")):
                        tags.add(tg)
                if len(items) < _DEFAULT_PAGE_SIZE:
                    break
        except Exception:
            logger.debug("Facet scan failed; falling back to static lists", exc_info=True)
        self._facet_cache = {
            "entity_types": sorted(entity_types) or _KNOWN_ENTITY_TYPES,
            "mime_types": sorted(mime_types) or _KNOWN_MIME_TYPES,
            "tags": sorted(tags),
        }
        return self._facet_cache

    def get_entity_types(self) -> list[str]:
        return list(self._load_facets()["entity_types"])

    def get_mime_types(self) -> list[str]:
        return list(self._load_facets()["mime_types"])

    def get_all_tags(self) -> list[str]:
        return list(self._load_facets()["tags"])

    def get_categories(self) -> list[dict[str, Any]]:
        """Categories with counts.

        The backend returns ``[{"category", "count"}]``; the view expects the
        local repository's ``{"category", "cnt"}`` shape, so the key is
        renamed here.
        """
        try:
            rows = self._api.get_document_categories()
        except Exception:
            logger.debug("get_categories failed", exc_info=True)
            return []
        result: list[dict[str, Any]] = []
        for r in rows or []:
            if isinstance(r, dict):
                result.append({
                    "category": r.get("category", ""),
                    "cnt": r.get("cnt", r.get("count", 0)),
                })
        return result

    # ── Fetch / search ────────────────────────────────────────────────

    def get_by_id(self, doc_id: int, company_id=None) -> Optional[Dict[str, Any]]:
        try:
            doc = self._api.get_document(doc_id)
        except Exception:
            logger.debug("get_document failed for id=%s", doc_id, exc_info=True)
            return None
        return self._normalise_document(doc) if isinstance(doc, dict) else None

    def get(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Mirror ``DocumentService.get``: document dict, or None."""
        return self.get_by_id(document_id)

    def read_document_info(self, doc_id: int) -> Dict[str, Any]:
        try:
            return self._api.read_document_info(doc_id)
        except Exception:
            logger.debug("read_document_info failed for id=%s", doc_id, exc_info=True)
            return {}

    def list_documents(self, query: str = "", category: str = "",
                       entity_type: str = "", date_from: str = "",
                       date_to: str = "", mime_type: str = "",
                       order: str = "uploaded_at DESC", page: int = 0,
                       page_size: int = 20) -> Dict[str, Any]:
        """Paginated search — returns ``{items, total, total_pages}``."""
        try:
            resp = self._api.list_documents(
                query=query, category=category, entity_type=entity_type,
                date_from=date_from, date_to=date_to, mime_type=mime_type,
                order=order, page=page, page_size=page_size,
            )
        except Exception:
            logger.debug("list_documents failed", exc_info=True)
            return {"items": [], "total": 0, "total_pages": 0}
        if not isinstance(resp, dict):
            return {"items": [], "total": 0, "total_pages": 0}
        return {
            "items": self._items_from(resp),
            "total": resp.get("total", len(resp.get("items") or [])),
            "total_pages": resp.get("total_pages", 0),
        }

    def advanced_search(self, query: str = "", category: str = "",
                        entity_type: str = "", entity_id: Optional[int] = None,
                        date_from: str = "", date_to: str = "",
                        mime_type: str = "", tag: str = "",
                        order: str = "uploaded_at DESC",
                        page: int = 0, page_size: int = 20) -> Dict[str, Any]:
        # The backend list endpoint accepts the shared filters but not a
        # dedicated ``tag`` param; it is dropped here.
        return self.list_documents(
            query=query, category=category, entity_type=entity_type,
            date_from=date_from, date_to=date_to, mime_type=mime_type,
            order=order, page=page, page_size=page_size,
        )

    def fts_search(self, query: str = "", category: str = "",
                   entity_type: str = "", order: str = "uploaded_at DESC",
                   page: int = 0, page_size: int = 20) -> Dict[str, Any]:
        # The backend list route performs the FTS-backed advanced search
        # whenever a query is supplied.
        return self.list_documents(
            query=query, category=category, entity_type=entity_type,
            order=order, page=page, page_size=page_size,
        )

    def search(self, query: str = "", category: str = "",
               entity_type: str = "", entity_id: Optional[int] = None,
               order: str = "uploaded_at DESC",
               page: int = 0, page_size: int = 20) -> Dict[str, Any]:
        return self.advanced_search(
            query=query, category=category, entity_type=entity_type,
            entity_id=entity_id, order=order, page=page, page_size=page_size,
        )

    def list_all(self, entity_type: str = "",
                 entity_id: Optional[int] = None) -> list[Dict[str, Any]]:
        """Mirror ``DocumentService.list_all`` (flat list of documents)."""
        if entity_type and entity_id is not None:
            return self.get_documents_for_entity(entity_type, entity_id)
        return self._scan_documents()

    def get_documents_for_entity(self, entity_type: str,
                                 entity_id: int) -> list[Dict[str, Any]]:
        """Documents linked to an entity.

        The backend list endpoint filters by ``entity_type`` only, so the
        ``entity_id`` filter is applied client-side over bounded pages.
        """
        docs: list[Dict[str, Any]] = []
        try:
            for page in range(5):
                resp = self._api.list_documents(
                    entity_type=entity_type, page=page, page_size=_DEFAULT_PAGE_SIZE,
                )
                items = self._items_from(resp)
                if not items:
                    break
                docs.extend(d for d in items if d.get("entity_id") == entity_id)
                if len(items) < _DEFAULT_PAGE_SIZE:
                    break
        except Exception:
            logger.debug("get_documents_for_entity failed", exc_info=True)
        return docs

    # ── Links ─────────────────────────────────────────────────────────

    def get_links(self, doc_id: int) -> list[Dict[str, Any]]:
        """Linked entities.

        The dedicated ``/documents/{id}/links`` route is not implemented
        server-side, so the link list is read from the ``read`` payload
        (which carries ``linked_entities``).
        """
        info = self.read_document_info(doc_id)
        links = info.get("linked_entities") or []
        return [l for l in links if isinstance(l, dict)]

    def link_document(self, doc_id: int, entity_type: str,
                      entity_id: int, relation_type: str = "attached") -> bool:
        """⚠ Unsupported in remote mode.

        The backend implements no ``POST /documents/{id}/links`` route, so
        this returns ``False`` (the local service's boolean contract).
        """
        logger.warning(
            "link_document(%s, %s, %s) unsupported in remote mode",
            doc_id, entity_type, entity_id,
        )
        return False

    def unlink_document(self, link_id: int) -> bool:
        """⚠ Unsupported in remote mode (no unlink route) — returns False."""
        logger.warning("unlink_document(%s) unsupported in remote mode", link_id)
        return False

    def link_to_entity(self, document_id: int, entity_type: str,
                       entity_id: int) -> Optional[Dict[str, Any]]:
        """Mirror ``DocumentService.link_to_entity`` (document dict on success)."""
        if not self.link_document(document_id, entity_type, entity_id):
            return None
        return self.get(document_id)

    # ── Versions ──────────────────────────────────────────────────────

    def get_versions(self, doc_id: int) -> list[Dict[str, Any]]:
        """Version list, read from the ``read`` payload (see ``get_links``)."""
        info = self.read_document_info(doc_id)
        versions = info.get("versions") or []
        return [v for v in versions if isinstance(v, dict)]

    def upload_new_version(self, doc_id: int, source_path: str,
                           comment: str = "", uploaded_by: str = "") -> Optional[int]:
        """⚠ Unsupported — the backend has no document-version upload route."""
        logger.warning("upload_new_version(%s) unsupported in remote mode", doc_id)
        return None

    def add_version(self, doc_id: int, source_path: str,
                    comment: str = "", uploaded_by: str = "") -> Optional[int]:
        """Alias kept for parity with the versioning sub-service API."""
        return self.upload_new_version(doc_id, source_path, comment, uploaded_by)

    def restore_version(self, doc_id: int, version_number: int) -> bool:
        """⚠ Unsupported — no restore route on the backend."""
        logger.warning(
            "restore_version(%s, %s) unsupported in remote mode",
            doc_id, version_number,
        )
        return False

    # ── Tags ──────────────────────────────────────────────────────────

    def _patch_fields(self, doc_id: int, fields: Dict[str, Any]) -> bool:
        try:
            self._api._patch(f"/api/v1/documents/{doc_id}", json_data=fields)
            return True
        except Exception:
            logger.debug("PATCH document %s failed", doc_id, exc_info=True)
            return False

    def add_tag(self, doc_id: int, tag: str) -> bool:
        doc = self.get_by_id(doc_id)
        if not doc:
            return False
        tags = self._parse_tags(doc.get("tags"))
        if tag in tags:
            return True
        return self._patch_fields(doc_id, {"tags": tags + [tag]})

    def remove_tag(self, doc_id: int, tag: str) -> bool:
        doc = self.get_by_id(doc_id)
        if not doc:
            return False
        tags = self._parse_tags(doc.get("tags"))
        if tag not in tags:
            return True
        return self._patch_fields(doc_id, {"tags": [t for t in tags if t != tag]})

    def set_tags(self, doc_id: int, tags: list) -> None:
        self._patch_fields(doc_id, {"tags": list(tags or [])})

    # ── Expiry ────────────────────────────────────────────────────────

    def set_expiry_date(self, doc_id: int, expiry_date: str) -> None:
        self._patch_fields(doc_id, {"expiry_date": expiry_date})

    def get_expiry_info(self, doc_id: int) -> Dict[str, Any]:
        """Return ``{"expiry": ..., "is_expired": ...}`` for a document."""
        info = self.read_document_info(doc_id)
        return {
            "expiry": info.get("expiry", ""),
            "is_expired": info.get("is_expired", False),
        }

    @staticmethod
    def _expiry_date(doc: Dict[str, Any]) -> Optional[date]:
        exp = doc.get("expiry_date")
        if not exp:
            return None
        try:
            return date.fromisoformat(str(exp)[:10])
        except ValueError:
            return None

    def get_expiring(self, days_ahead: int = 30) -> list[Dict[str, Any]]:
        """Docs whose expiry_date falls within ``days_ahead`` days.

        The backend exposes no expiry endpoint, so this scans documents
        client-side (bounded) and filters by ``expiry_date``.
        """
        today = date.today()
        horizon = today + timedelta(days=days_ahead)
        result: list[Dict[str, Any]] = []
        for doc in self._scan_documents():
            exp = self._expiry_date(doc)
            if exp is not None and today <= exp <= horizon:
                result.append(doc)
        return result

    def get_overdue(self) -> list[Dict[str, Any]]:
        today = date.today()
        return [d for d in self._scan_documents()
                if (exp := self._expiry_date(d)) is not None and exp < today]

    def evaluate_document_expiries(self, alert_mgr=None, db=None) -> int:
        """⚠ Server-side scheduled job — remote mode is a no-op returning 0."""
        return 0

    # ── Upload / update / delete ──────────────────────────────────────

    def upload(self, source_path: str, title: str = "",
               category: str = "", entity_type: str = "",
               entity_id: Optional[int] = None,
               description: str = "", tags: Optional[list[str]] = None,
               uploaded_by: str = "", company_id=None) -> Optional[int]:
        """Upload a single file and return the new document id.

        The backend upload route accepts category/entity_type/entity_id/
        uploaded_by only; ``title``/``description``/``tags`` are applied via
        a follow-up PATCH when provided.
        """
        try:
            resp = self._api.upload_document(
                source_path, category=category, entity_type=entity_type,
                entity_id=entity_id, uploaded_by=uploaded_by or "user",
            )
        except Exception:
            logger.debug("upload failed for %s", source_path, exc_info=True)
            return None
        doc_id = resp.get("id") if isinstance(resp, dict) else None
        if not doc_id:
            return None
        patch: Dict[str, Any] = {}
        if title:
            patch["title"] = title
        if description:
            patch["description"] = description
        if tags is not None:
            patch["tags"] = list(tags)
        if patch:
            self._patch_fields(doc_id, patch)
        return doc_id

    def upload_document(self, request, user_id: int = 0,
                        company_id=None) -> Dict[str, Any]:
        """Typed-request variant mirroring ``DocumentService.upload_document``.

        Accepts any object exposing the ``DocumentUpload`` attributes
        (``source_path``, ``title``, ``category``, ``entity_type``,
        ``entity_id``, ``description``, ``tags``).  Returns the remote shape
        of the local ``DocumentUploadResult``: ``{"success", "data", ...}``.
        """
        req = request
        try:
            doc_id = self.upload(
                req.source_path,
                title=getattr(req, "title", ""),
                category=getattr(req, "category", ""),
                entity_type=getattr(req, "entity_type", ""),
                entity_id=getattr(req, "entity_id", None),
                description=getattr(req, "description", ""),
                tags=getattr(req, "tags", None),
                uploaded_by="user",
            )
        except Exception as exc:
            return {"success": False, "data": None, "error": str(exc)}
        if not doc_id:
            return {"success": False, "data": None, "error": "Upload returned no document ID"}
        return {"success": True, "data": self.get_by_id(doc_id)}

    def batch_upload(self, paths: list, category: str = "",
                     entity_type: str = "", entity_id: Optional[int] = None,
                     uploaded_by: str = "",
                     tags: Optional[list[str]] = None) -> Dict[str, Any]:
        """Batch upload matching the local service's result shape.

        No backend batch route exists, so each file goes through the
        single-file endpoint and results are aggregated under ``uploaded`` /
        ``duplicates`` / ``rejected`` / ``failed``.
        """
        results: Dict[str, Any] = {
            "uploaded": [], "duplicates": [], "failed": [], "rejected": [],
        }
        for src in paths:
            fname = os.path.basename(src)
            if not os.path.isfile(src):
                results["rejected"].append({"file": fname, "reason": "File not found"})
                continue
            try:
                doc_id = self.upload(
                    src, category=category, entity_type=entity_type,
                    entity_id=entity_id, uploaded_by=uploaded_by or "user",
                    tags=tags,
                )
                if doc_id:
                    results["uploaded"].append({"file": fname, "id": doc_id})
                else:
                    results["failed"].append({"file": fname, "reason": "Upload failed"})
            except Exception as e:
                results["failed"].append({"file": fname, "reason": str(e)})
        return results

    def update_metadata(self, doc_id: int, title: str = "",
                        description: str = "",
                        tags: Optional[list[str]] = None) -> bool:
        """Mirror ``DocumentService.update_metadata`` via PATCH /{doc_id}."""
        fields: Dict[str, Any] = {}
        if title:
            fields["title"] = title
        if description is not None:
            fields["description"] = description
        if tags is not None:
            fields["tags"] = list(tags)
        if not fields:
            return False
        return self._patch_fields(doc_id, fields)

    def update_document(self, doc_id: int, **fields: Any) -> Optional[Dict[str, Any]]:
        """PATCH a document and return the refreshed document dict."""
        if not self._patch_fields(doc_id, fields):
            return None
        return self.get_by_id(doc_id)

    def delete(self, doc_id: int) -> bool:
        try:
            self._api.delete_document(doc_id)
            return True
        except Exception:
            logger.debug("delete failed for id=%s", doc_id, exc_info=True)
            return False

    def delete_document(self, document_id: int, user_id: int = 0) -> Dict[str, Any]:
        """Typed variant returning ``{"success", "data"}`` (pre-delete doc)."""
        doc = self.get_by_id(document_id)
        ok = self.delete(document_id)
        return {"success": ok, "data": doc}

    def delete_batch(self, doc_ids: list) -> int:
        count = 0
        for did in doc_ids or []:
            if self.delete(did):
                count += 1
        return count

    def archive(self, doc_id: int) -> None:
        """⚠ No-op — the backend has no archive route (DELETE is the only
        mutation).  Mirrors the local service's ``None`` return."""
        logger.warning("archive(%s) unsupported in remote mode", doc_id)

    # ── Email / zip / files (local-only operations) ───────────────────

    def email_document(self, document_id: int, recipient: str, user_id: int = 0,
                       prefs: Optional[Any] = None) -> bool:
        """⚠ Unsupported — the backend has no document-email endpoint."""
        logger.warning("email_document(%s) unsupported in remote mode", document_id)
        return False

    def download_zip(self, doc_ids: list, output_path: str) -> str:
        """⚠ No server-side zip route — writes an empty archive with a note.

        Returns ``output_path`` so the caller receives a valid file handle.
        """
        try:
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(
                    "README.txt",
                    "Download zip is not supported in remote mode.\n",
                )
        except OSError as e:
            raise ValueError(f"Failed to write archive: {e}") from e
        return output_path

    def get_file_path(self, doc_id: int) -> Optional[str]:
        """⚠ Files live on the server in remote mode — always None."""
        return None

    def get_thumbnail_path(self, doc_id: int) -> Optional[str]:
        """⚠ Thumbnails are generated server-side — always None."""
        return None

    # ── OCR ───────────────────────────────────────────────────────────

    def run_ocr(self, document_id: int, engine: str = "auto") -> Dict[str, Any]:
        """Report server-side OCR status for a document.

        Note: unlike the local re-run path this cannot re-run OCR over a
        local file; it delegates to ``POST /ocr/run`` and returns the
        server's current OCR state.
        """
        try:
            return self._api.run_ocr(document_id, engine=engine)
        except Exception:
            logger.debug("run_ocr failed for id=%s", document_id, exc_info=True)
            return {}

    def get_ocr_status(self, doc_id: int) -> Dict[str, Any]:
        try:
            return self._api.get_ocr_status(doc_id)
        except Exception:
            logger.debug("get_ocr_status failed for id=%s", doc_id, exc_info=True)
            return {}

    def extract_text(self, file_path: str, mime_type: str) -> str:
        """⚠ Local-only operation (file on disk) — returns empty string."""
        return ""

    @staticmethod
    def is_image(mime_type: str) -> bool:
        return mime_type in _IMAGE_MIME

    # ── Misc ──────────────────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        return self._api.health_check()
