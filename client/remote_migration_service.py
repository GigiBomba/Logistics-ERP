"""API-backed migration service wrapper for remote-only client mode.

Mirrors the surface that the Migration Center tabs
(``ui/views/migration_center/``) call so the tabs can run against the FastAPI
backend instead of a local database.

Backend contracts (``backend/api/v1/migration.py``):

  - GET  /migration/export?kind=trips|clients|invoices&format=csv|json|xlsx|zip
         → raw file bytes (via ``ApiClient._download``); optional ``fields``,
           ``date_from`` and ``date_to`` query params are applied server-side
  - GET  /migration/count?kind=trips|clients|invoices|drivers|trucks
         → {"kind": ..., "count": N}
  - POST /migration/preview (multipart file + kind [+ dedup_action]
                             [+ columns_map])
         → {"columns", "sample_rows", "total_rows", "duplicate_rows",
            "validation_failures", "valid_rows", "errors"}
  - POST /migration/import  (multipart file + kind [+ dedup_action]
                             [+ columns_map])
         → {"total_rows", "valid_rows", "committed", "duplicates_skipped",
            "validation_failures", "imported", "skipped", "errors": [...]}
  - POST /migration/archive (multipart file + entity_type/entity_id/notes)
         → per-document processing record
  - POST /migration/archive/{doc_id}/confirm  body {"confirmed", "notes"}
         → the updated per-document record (404 for unknown doc_id)

Everything the tabs need is now backed by an endpoint; the file-based
preview/validate/confirm stubs have been replaced with real API calls.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger("remote_migration")

# Tab entity key → API kind (backend accepts both singular and plural).
_ENTITY_TO_KIND = {
    "trip": "trips",
    "client": "clients",
    "driver": "drivers",
    "truck": "trucks",
    "invoice": "invoices",
}


class RemoteMigrationService:
    """API-backed substitute for the Migration Center service layer."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    # ── Core API operations ────────────────────────────────────────────────

    def export_data(
        self,
        kind: str,
        fmt: str,
        fields: Optional[list] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> bytes:
        """Download an export file for *kind*/*fmt* as raw bytes.

        ``fmt`` may be ``csv``, ``json``, ``xlsx`` or ``zip`` (``excel`` is
        normalised to ``xlsx``).  *fields* (list of column names), *date_from*
        and *date_to* (``YYYY-MM-DD``) are applied server-side by the backend.
        """
        api_fmt = "xlsx" if fmt == "excel" else fmt
        params = {"kind": kind, "format": api_fmt}
        if fields:
            params["fields"] = ",".join(str(f) for f in fields)
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return self._api._download(
            "/api/v1/migration/export",
            params=params,
        )

    def import_file(
        self,
        filename: str,
        content: bytes,
        kind: str,
        dedup_action: str = "skip",
        columns_map: Optional[dict] = None,
    ) -> dict:
        """Upload *content* (named *filename*) and import it as *kind*.

        *columns_map* is an optional dict mapping source column names to
        target entity fields; it is JSON-encoded and applied server-side by
        the backend.  Returns the backend stats dict (``imported``,
        ``skipped``, ``errors``, …).  Raises on API/HTTP errors so callers can
        surface them as failures.
        """
        files = {"file": (filename, content)}
        data: dict[str, str] = {"kind": kind}
        if dedup_action:
            data["dedup_action"] = dedup_action
        if columns_map:
            data["columns_map"] = json.dumps(columns_map)
        return self._api._post("/api/v1/migration/import", files=files, data=data)

    def archive_document(self, file_path: str, meta: Optional[dict] = None) -> dict:
        """Upload *file_path* and run the physical archive pipeline.

        *meta* may carry ``entity_type`` / ``entity_id`` / ``notes``.  Returns
        the per-document record from the backend.
        """
        meta = meta or {}
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            data = {
                "entity_type": str(meta.get("entity_type") or "migration"),
                "entity_id": str(meta.get("entity_id") or ""),
                "notes": str(meta.get("notes") or ""),
            }
            return self._api._post(
                "/api/v1/migration/archive", files=files, data=data,
            )

    # ── EmigrateTab (export) surface ───────────────────────────────────────

    def count_records(self, entity_type: str, filters: Optional[dict] = None) -> int:
        """Return the record count for *entity_type* via ``GET /migration/count``.

        *filters* (date range, …) is accepted for signature compatibility with
        the tab; the backend counts all rows of the entity, mirroring the local
        ``EmigrateService.count_records`` fallback (the entity repositories have
        no filtered ``count``).  Returns ``0`` on API/HTTP errors so the export
        tab's record preview degrades gracefully.
        """
        kind = _ENTITY_TO_KIND.get(entity_type, entity_type)
        try:
            resp = self._api._get(
                "/api/v1/migration/count", params={"kind": kind},
            )
        except Exception as exc:
            logger.warning(
                "migration: count_records(%s) failed: %s", entity_type, exc,
            )
            return 0
        if not isinstance(resp, dict):
            logger.warning(
                "migration: count_records(%s) returned non-dict payload: %r",
                entity_type, resp,
            )
            return 0
        try:
            return int(resp.get("count", 0))
        except (TypeError, ValueError):
            logger.warning(
                "migration: count_records(%s) returned malformed count: %r",
                entity_type, resp.get("count"),
            )
            return 0

    def export(
        self,
        entity_type: str,
        fmt: str,
        output_path: str,
        filters: Optional[dict] = None,
        field_selection: Optional[list] = None,
        progress_cb: Optional[Any] = None,
    ) -> Optional[str]:
        """Export *entity_type* to *output_path* via the backend.

        ``csv``, ``json``, ``excel``/``xlsx`` and ``zip`` map to a backend
        endpoint.  Field selection (*field_selection*) and date filters
        (``date_from``/``date_to`` inside *filters*) are applied server-side
        through the export query parameters.
        """
        kind = _ENTITY_TO_KIND.get(entity_type, entity_type)
        if fmt not in ("csv", "json", "excel", "xlsx", "zip"):
            logger.warning(
                "migration: export fmt=%r has no backend endpoint in remote "
                "mode — export aborted", fmt,
            )
            return None
        filters = filters or {}
        try:
            content = self.export_data(
                kind,
                fmt,
                fields=field_selection,
                date_from=filters.get("date_from"),
                date_to=filters.get("date_to"),
            )
        except Exception as exc:
            logger.warning("migration: export failed for %s/%s", entity_type, fmt, exc_info=True)
            return None
        try:
            with open(output_path, "wb") as f:
                f.write(content)
        except OSError as exc:
            logger.warning("migration: failed to write export to %s: %s", output_path, exc)
            return None
        return output_path

    # ── ImmigrateSoftwareTab (import) surface ──────────────────────────────

    def preview_file(
        self,
        filename: str,
        content: bytes,
        kind: str,
        dedup_action: Optional[str] = None,
        columns_map: Optional[dict] = None,
    ) -> dict:
        """Upload *content* (named *filename*) and parse it for preview.

        Returns the backend preview dict: ``{"columns", "sample_rows",
        "total_rows", "duplicate_rows", "validation_failures", "valid_rows",
        "errors"}``.  *columns_map* (optional) applies the wizard's
        column-mapping server-side before validation/duplicate detection.
        """
        files = {"file": (filename, content)}
        data: dict[str, str] = {"kind": kind}
        if dedup_action:
            data["dedup_action"] = dedup_action
        if columns_map:
            data["columns_map"] = json.dumps(columns_map)
        return self._api._post(
            "/api/v1/migration/preview", files=files, data=data,
        )

    def preview(
        self,
        path: str,
        fmt: str,
        entity_type: str,
        mapping: Optional[dict] = None,
    ) -> dict:
        """Preview *path* through ``POST /migration/preview``.

        Returns the backend preview dict keyed by the tab's expected columns
        (``columns``, ``sample_rows``).  The full response is cached so the
        subsequent ``validate_all`` call can reuse the server-side validation
        and duplicate data.  *mapping* (optional) carries the wizard's
        ``{"columns": {source: target}}`` selection.
        """
        kind = _ENTITY_TO_KIND.get(entity_type, entity_type)
        columns_map = None
        if isinstance(mapping, dict) and mapping.get("columns"):
            columns_map = mapping["columns"]
        try:
            with open(path, "rb") as f:
                content = f.read()
            filename = os.path.basename(path)
        except (OSError, TypeError) as exc:
            logger.warning("migration: cannot read %s: %s", path, exc)
            return {
                "columns": [],
                "sample_rows": [],
                "total_rows": 0,
                "duplicate_rows": [],
                "validation_failures": 0,
                "valid_rows": 0,
                "errors": [{"message": str(exc)}],
            }
        try:
            result = self.preview_file(filename, content, kind, columns_map=columns_map)
        except Exception as exc:
            logger.warning("migration: preview failed for %s", path, exc_info=True)
            result = {
                "columns": [],
                "sample_rows": [],
                "total_rows": 0,
                "duplicate_rows": [],
                "validation_failures": 0,
                "valid_rows": 0,
                "errors": [{"message": str(exc)}],
            }
        self._last_preview = result
        return result

    def validate_all(self, rows: list, entity_type: str) -> dict:
        """Return the server-side validation summary for the last preview.

        ``rows`` is accepted for signature compatibility with the tab; the
        validation/duplicate data comes from the most recent
        ``POST /migration/preview`` response cached on this service.
        """
        preview = self._last_preview or {}
        return {
            "valid_rows": preview.get("valid_rows", 0),
            "validation_failures": preview.get("validation_failures", 0),
            "duplicates_skipped": 0,
            "errors": preview.get("errors", []),
            "duplicates": preview.get("duplicate_rows", []),
        }

    def import_data(
        self,
        path: str,
        mapping: Optional[dict] = None,
        duplicate_action: str = "skip",
        progress_callback: Optional[Any] = None,
        **kwargs: Any,
    ) -> dict:
        """Import *path* through ``POST /migration/import``.

        Accepts the tab's ``(path, mapping, duplicate_action, progress_callback)``
        call signature.  The entity/kind is read from ``mapping["entity_type"]``
        (or the ``entity_type`` kwarg) and the column mapping from
        ``mapping["columns"]`` is passed as ``columns_map`` so the backend
        applies it server-side.

        When ``progress_callback`` is provided it is invoked with the tab's
        ``(stage, percent, message)`` signature at honest stage boundaries: 0
        at start, ~40 once the file is read/upload prepared, ~70 as the import
        request is submitted, and 100 when the response arrives (the import is
        a single synchronous request — stage-based progress, no fake
        streaming).  Returns a dict shaped for the tab:
        ``{"success", "stats": {...}, "imported", "skipped", "errors"}``.
        """
        entity_type = "client"
        if isinstance(mapping, dict) and mapping.get("entity_type"):
            entity_type = str(mapping["entity_type"])
        entity_type = kwargs.get("entity_type", entity_type)
        kind = _ENTITY_TO_KIND.get(entity_type, entity_type)

        def report(stage: str, percent: int, message: str) -> None:
            """Invoke the tab's ``(stage, percent, message)`` callback safely."""
            if progress_callback is None:
                return
            try:
                progress_callback(stage, percent, message)
            except Exception:
                logger.debug(
                    "migration: progress_callback raised for stage=%s", stage,
                    exc_info=True,
                )

        report("import", 0, f"Starting remote import of {kind}...")

        try:
            with open(path, "rb") as f:
                content = f.read()
            filename = os.path.basename(path)
        except (OSError, TypeError) as exc:
            logger.warning("migration: cannot read %s: %s", path, exc)
            return {"success": False, "error": str(exc)}

        columns_map = None
        if isinstance(mapping, dict) and mapping.get("columns"):
            columns_map = mapping["columns"]

        report("validating", 40, f"Prepared {kind} import file for upload")

        try:
            # Single synchronous request: the server runs preview → validate →
            # commit inside the call.  Report 70 as the request is submitted,
            # then 100 once the response arrives (stage-based progress — no
            # fake streaming of the synchronous upload).
            report("committing", 70, f"Submitting {kind} import to server...")
            result = self.import_file(
                filename, content, kind,
                dedup_action=duplicate_action or "skip",
                columns_map=columns_map,
            )
        except Exception as exc:
            logger.warning("migration: import failed for %s", path, exc_info=True)
            report("failed", 100, f"Import failed: {exc}")
            return {"success": False, "error": str(exc)}

        committed = result.get("committed", result.get("imported", 0))
        skipped = result.get("skipped", 0)
        errors = result.get("errors", [])
        report(
            "complete", 100,
            f"Import complete: {committed} committed, {skipped} skipped, "
            f"{len(errors)} failed",
        )
        return {
            "success": True,
            "stats": {
                "total_rows": result.get("total_rows", 0),
                "valid_rows": result.get("valid_rows", 0),
                "committed": committed,
                "duplicates_skipped": result.get("duplicates_skipped", 0),
                "validation_failures": result.get("validation_failures", 0),
            },
            "imported": result.get("imported", committed),
            "skipped": skipped,
            "errors": errors,
        }

    # ── ImmigratePhysicalTab (archive) surface ─────────────────────────────

    def process_document(self, file_path: str) -> dict:
        """Process one physical document via ``POST /migration/archive``.

        Returns the record shaped for the tab: ``{"success", "file_path",
        "doc_id", "doc_type", "confidence", "needs_confirmation", "error", …}``.
        """
        try:
            record = self.archive_document(file_path, {"entity_type": "migration"})
        except Exception as exc:
            logger.warning(
                "migration: process_document(%s) failed", file_path, exc_info=True,
            )
            return {
                "file_path": file_path,
                "success": False,
                "error": str(exc),
                "doc_type": "unknown",
                "confidence": 0.0,
            }
        if not isinstance(record, dict):
            record = {}
        doc_id = record.get("doc_id")
        error = record.get("error")
        return {
            "file_path": file_path,
            "success": bool(doc_id) and not error,
            "doc_id": doc_id,
            "doc_type": record.get("doc_type", "unknown"),
            "confidence": record.get("confidence", 0.0),
            "needs_confirmation": record.get("needs_confirmation", True),
            "extracted": record.get("extracted", {}),
            "match_result": record.get("match_result"),
            "error": error,
        }

    def confirm_document(
        self,
        doc_id: int,
        confirmed: Any = True,
        notes: str = "",
    ) -> dict:
        """Confirm a scanned document via ``POST /migration/archive/{id}/confirm``.

        Returns the updated per-document record.  Backward compatible with the
        tab's ``confirm_document(doc_id, corrections)`` call: when *confirmed*
        is a dict it is treated as extracted-field corrections and the
        confirmation flag defaults to ``True``.
        """
        if isinstance(confirmed, dict):
            # Tab passes corrections as the second positional argument.
            confirmed = True
        try:
            return self._api._post(
                f"/api/v1/migration/archive/{doc_id}/confirm",
                json_data={"confirmed": bool(confirmed), "notes": str(notes)},
            )
        except Exception as exc:
            logger.warning(
                "migration: confirm_document(%s) failed", doc_id, exc_info=True,
            )
            return {
                "doc_id": doc_id,
                "confirmed": False,
                "notes": str(notes),
                "error": str(exc),
            }
