"""Migration Center API — export, import, and physical archive endpoints.

These endpoints expose the existing local migration services
(``services/migration/emigrate_service.py``, ``import_service.py`` and
``physical_archive_service.py``) over HTTP so the Migration Center tabs keep
working in remote (API-only) mode.  The services run against the same database
layer the desktop app uses, so no import/export logic is re-implemented here.

Endpoint contract::

    GET  /migration/export?kind=trips|clients|invoices&format=csv|json|xlsx|zip
         → file download (CSV / JSON / Excel / ZIP-of-CSV); optional
           ``fields`` (comma-separated), ``date_from``/``date_to`` query
           params applied server-side to the exported rows
    GET  /migration/count?kind=trips|clients|invoices|drivers|trucks
         → {"kind": ..., "count": N} — total row count for an entity kind,
           via the same repository layer the export uses (400 on unknown kind)
    POST /migration/preview (multipart: file + kind [+ dedup_action]
                             [+ columns_map])
         → {"columns", "sample_rows", "total_rows", "duplicate_rows",
            "validation_failures", "valid_rows", "errors"}
    POST /migration/import  (multipart: file + kind [+ dedup_action]
                             [+ columns_map])
         → {"total_rows", "valid_rows", "committed", "duplicates_skipped",
            "validation_failures", "imported", "skipped", "errors": [...]}
    POST /migration/archive (multipart: file + entity_type/entity_id/notes)
         → the per-document processing record
    POST /migration/archive/{doc_id}/confirm
         body {"confirmed": bool, "notes": str}
         → the updated per-document record (404 for unknown doc_id)
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import zipfile
from datetime import date, datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.middleware.input_sanitizer import sanitize_free_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/migration", tags=["migration"])

# ── Kind → entity mapping ────────────────────────────────────────────────
# Accepts both the plural query forms (trips/clients/invoices) and the
# singular entity values used by the Migration Center tabs (trip, client,
# driver, truck, invoice).
_KIND_TO_ENTITY: dict[str, str] = {
    "trip": "trip",
    "trips": "trip",
    "client": "client",
    "clients": "client",
    "driver": "driver",
    "drivers": "driver",
    "truck": "truck",
    "trucks": "truck",
    "invoice": "invoice",
    "invoices": "invoice",
}

_SUPPORTED_EXPORT_FORMATS = {"csv", "json", "xlsx", "zip"}

# File-extension → ImportFormat key (as used by ``ImportService``).
_IMPORT_FORMAT_BY_SUFFIX = {
    ".csv": "csv",
    ".xls": "excel",
    ".xlsx": "excel",
    ".json": "json",
    ".xml": "xml",
}

# Tab duplicate-resolution values → ``ImportService.commit`` dedup actions.
_DEDUP_ACTION_ALIASES = {
    "skip": "skip",
    "overwrite": "overwrite",
    "update": "overwrite",
    "keep_both": "import",
    "import": "import",
}

# Candidate date columns per entity — used to apply the export endpoint's
# server-side ``date_from`` / ``date_to`` range filter (mirrors the date
# range the EmigrateTab sends with its local export).
_ENTITY_DATE_COLUMNS: dict[str, list[str]] = {
    "trip": ["start_date", "departure_date", "arrival_date", "created_at", "updated_at"],
    "client": ["created_at", "updated_at"],
    "driver": ["hire_date", "created_at", "updated_at"],
    "truck": ["created_at", "updated_at"],
    "invoice": ["issue_date", "due_date", "created_at", "updated_at"],
}


def _cleanup_temp(path: str) -> None:
    """Delete a temp export/upload file; never raises."""
    try:
        os.unlink(path)
    except OSError:
        pass


def _parse_date_value(value: Any) -> Optional[date]:
    """Best-effort parse of a row value into a ``date``; ``None`` if not a date."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None
    return None


def _apply_date_range_filter(
    rows: list[dict[str, Any]],
    date_from: Optional[str],
    date_to: Optional[str],
    date_columns: list[str],
) -> list[dict[str, Any]]:
    """Keep rows whose date columns fall inside ``[date_from, date_to]``.

    A row is retained when *any* of its candidate date columns parses to a
    date within the inclusive range; rows without a parseable date in any
    candidate column are excluded once a bound is requested.
    """
    if not date_from and not date_to:
        return rows
    lower = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else None
    upper = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else None
    kept: list[dict[str, Any]] = []
    for row in rows:
        in_range = False
        for col in date_columns:
            parsed = _parse_date_value(row.get(col))
            if parsed is None:
                continue
            if lower is not None and parsed < lower:
                continue
            if upper is not None and parsed > upper:
                continue
            in_range = True
            break
        if in_range:
            kept.append(row)
    return kept


def _fetch_export_rows(service: Any, entity_type: Any) -> list[dict[str, Any]]:
    """Fetch export rows from the entity repository (same source the local
    ``EmigrateService.export`` uses for its csv/json writers)."""
    repo = service._get_repo(entity_type)
    try:
        rows = repo.get_all()
    except Exception:
        table = getattr(repo, "TABLE", f"{entity_type.value}s")
        try:
            rows = repo._fetchall(f"SELECT * FROM {table}")
        except Exception as exc:
            raise RuntimeError(
                f"Failed to fetch {entity_type.value} data: {exc}",
            ) from exc
    return list(rows or [])


def _parse_columns_map(columns_map: Optional[str]) -> dict[str, str]:
    """Parse the optional ``columns_map`` form field (JSON source→target)."""
    if not columns_map:
        return {}
    try:
        mapping_dict = json.loads(columns_map)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid columns_map JSON: {exc}",
        ) from exc
    if not isinstance(mapping_dict, dict):
        raise HTTPException(
            status_code=400,
            detail="columns_map must be a JSON object mapping source columns "
                   "to target fields",
        )
    return {str(k): str(v) for k, v in mapping_dict.items()}


def _document_record(
    doc: Optional[dict[str, Any]],
    confirmed: bool = True,
    notes: str = "",
) -> dict[str, Any]:
    """Shape a documents row into the per-document archive record."""
    if not doc:
        return {
            "doc_id": None,
            "confirmed": confirmed,
            "notes": notes,
            "doc_type": "unknown",
            "needs_confirmation": True,
            "extracted": {},
            "match_result": None,
            "error": "not found",
        }
    extracted: dict[str, Any] = {}
    raw = doc.get("extracted_data_json") or "{}"
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            extracted = parsed
    except (json.JSONDecodeError, TypeError):
        extracted = {}
    return {
        "doc_id": doc.get("id"),
        "confirmed": confirmed,
        "notes": notes,
        "doc_type": doc.get("doc_type") or "unknown",
        "needs_confirmation": False,
        "extracted": extracted,
        "match_result": doc.get("match_result"),
        "error": None,
    }


@router.get("/export")
def export_data(
    kind: str = Query(..., description="trips|clients|invoices"),
    fmt: str = Query("csv", alias="format", description="csv|json|xlsx|zip"),
    fields: Optional[str] = Query(
        None, description="Comma-separated field names to include in the export",
    ),
    date_from: Optional[str] = Query(
        None, description="Inclusive lower date bound (YYYY-MM-DD)",
    ),
    date_to: Optional[str] = Query(
        None, description="Inclusive upper date bound (YYYY-MM-DD)",
    ),
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Download entity data as CSV, JSON, Excel (.xlsx) or ZIP-of-CSV.

    Rows are fetched from the same repository layer ``EmigrateService`` uses,
    then filtered/selected server-side (``fields``, ``date_from``, ``date_to``)
    and written with ``EmigrateService``'s own writers.  The temp file is
    removed after the response has been fully sent.
    """
    entity_key = _KIND_TO_ENTITY.get((kind or "").lower())
    if entity_key is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported export kind: {kind!r}. "
                f"Supported: trips|clients|invoices"
            ),
        )
    format_key = (fmt or "").lower()
    if format_key not in _SUPPORTED_EXPORT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported export format: {fmt!r}. "
                f"Supported: csv|json|xlsx|zip"
            ),
        )

    # Validate the optional date bounds up front so malformed values produce a
    # clean 400 instead of a 500 inside the filter.
    for label, bound in (("date_from", date_from), ("date_to", date_to)):
        if bound is not None:
            try:
                datetime.strptime(bound, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid {label} {bound!r}: expected YYYY-MM-DD",
                )

    from services.migration.emigrate_service import EmigrateService
    from services.migration.types import EntityType

    entity_type = EntityType(entity_key)
    service = EmigrateService(db)

    field_selection = None
    if fields:
        field_selection = [f.strip() for f in fields.split(",") if f.strip()]

    rows = _fetch_export_rows(service, entity_type)
    rows = _apply_date_range_filter(
        rows, date_from, date_to, _ENTITY_DATE_COLUMNS.get(entity_key, []),
    )
    if field_selection:
        rows = [
            {k: v for k, v in row.items() if k in field_selection}
            for row in rows
        ]

    suffix = (
        ".json" if format_key == "json"
        else ".xlsx" if format_key == "xlsx"
        else ".csv"
    )
    tmp_path: str = ""
    download_path: str = ""
    media_type = "application/octet-stream"
    ext = format_key
    try:
        raw = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)  # noqa: SIM115
        raw.close()
        tmp_path = raw.name

        if format_key == "zip":
            # ZIP-of-CSV envelope: reuse the CSV writer, then archive it.
            EmigrateService._write_csv(rows, tmp_path)
            zip_path = f"{tmp_path}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(tmp_path, arcname=os.path.basename(tmp_path))
            os.unlink(tmp_path)
            download_path = zip_path
            media_type = "application/zip"
        elif format_key == "xlsx":
            EmigrateService._write_excel(rows, tmp_path)
            download_path = tmp_path
            media_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        elif format_key == "json":
            EmigrateService._write_json(rows, tmp_path)
            download_path = tmp_path
            media_type = "application/json"
        else:
            EmigrateService._write_csv(rows, tmp_path)
            download_path = tmp_path
            media_type = "text/csv"
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Export failed for kind=%s format=%s", kind, fmt,
        )
        _cleanup_temp(tmp_path)
        _cleanup_temp(f"{tmp_path}.zip")
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}")

    filename = (
        f"{entity_key}s_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{ext}"
    )
    return FileResponse(
        download_path,
        media_type=media_type,
        filename=filename,
        background=BackgroundTask(_cleanup_temp, download_path),
    )


@router.get("/count")
def count_entity_records(
    kind: str = Query(..., description="trips|clients|invoices|drivers|trucks"),
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return the total row count for an entity kind.

    Mirrors the local ``EmigrateService.count_records`` (the exact method the
    export tab's record-preview label calls) so remote mode reports the same
    numbers as local mode.  Tenant scoping is applied exactly as the export
    endpoint applies it — through the same repository layer (``COUNT(*)`` on
    the entity table with the repository's company filter).  Returns
    ``{"kind": ..., "count": N}``; 400 for an unknown *kind*.
    """
    entity_key = _KIND_TO_ENTITY.get((kind or "").lower())
    if entity_key is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported count kind: {kind!r}. "
                f"Supported: trips|clients|invoices|drivers|trucks"
            ),
        )

    from services.migration.emigrate_service import EmigrateService
    from services.migration.types import EntityType

    service = EmigrateService(db)
    count = service.count_records(EntityType(entity_key))
    return {"kind": (kind or "").lower(), "count": int(count or 0)}


@router.post("/preview")
def preview_file(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    file: UploadFile = File(...),
    kind: str = Form(..., description="trip|client|driver|truck|invoice"),
    dedup_action: str = Form("skip", description="skip|update|keep_both"),
    columns_map: Optional[str] = Form(
        None,
        description="Optional JSON object: source_column -> target_field",
    ),
    db: DatabaseManager = Depends(get_db),
):
    """Parse an uploaded file and return a preview for the import wizard.

    Runs ``ImportService.preview`` on the uploaded bytes and mirrors the
    local preview/validate API surface: source columns, sample rows, total
    row count, duplicate candidates, and per-row validation failures.  When
    an optional ``columns_map`` is supplied it is applied via
    ``ImportService.apply_mapping`` first so validation/duplicates reflect
    the wizard's column-mapping step.
    """
    entity_key = _KIND_TO_ENTITY.get((kind or "").lower())
    if entity_key is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported import kind: {kind!r}",
        )
    raw_filename = file.filename or "upload.csv"
    suffix = os.path.splitext(raw_filename)[1].lower()
    fmt_key = _IMPORT_FORMAT_BY_SUFFIX.get(suffix)
    if fmt_key is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {suffix or 'unknown'!r}. "
                f"Supported: .csv, .xls, .xlsx, .json, .xml"
            ),
        )

    mapping_dict = _parse_columns_map(columns_map)

    from services.migration.import_service import ImportService
    from services.migration.types import EntityType, ImportFormat, MappingConfig

    entity_type = EntityType(entity_key)
    import_fmt = ImportFormat(fmt_key)

    mapping_config: Optional[MappingConfig] = None
    if mapping_dict:
        mapping_config = MappingConfig(
            source_columns=list(mapping_dict.keys()),
            target_fields=mapping_dict,
            entity_type=entity_type,
        )

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)  # noqa: SIM115
    try:
        content = file.file.read()
        temp.write(content)
        temp.close()

        service = ImportService(db)
        rows, schema_errors = service.preview(temp.name, import_fmt, entity_type)
        if mapping_config is not None:
            rows = service.apply_mapping(rows, mapping_config)

        # ── Columns (first-seen key order) ─────────────────────────────
        columns: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in columns:
                    columns.append(key)
        if not columns:
            columns = list((rows[0] or {}).keys()) if rows else []

        # ── Sample rows: list-of-lists aligned to columns (tab shape) ──
        sample_rows: list[list[str]] = []
        for row in rows[:10]:
            sample_rows.append([
                str(row.get(col, "") if row.get(col) is not None else "")
                for col in columns
            ])

        # ── Duplicate candidates ───────────────────────────────────────
        duplicate_rows: list[dict[str, Any]] = []
        for cand in service.check_duplicates(rows, entity_type):
            duplicate_rows.append({
                "existing": cand.existing,
                "incoming": cand.incoming,
                "entity_type": cand.entity_type.value,
                "score": cand.score,
                "matched_on": cand.matched_on,
            })

        # ── Per-row validation ─────────────────────────────────────────
        valid_rows, invalid_rows, _error_summary = service.validate_all(
            rows, entity_type,
        )
        errors: list[dict[str, Any]] = []
        for inv in invalid_rows:
            errors.append({
                "row": inv.get("row_index", 0),
                "message": "; ".join(inv.get("errors", [])),
                "data": inv.get("original", {}),
            })

        return {
            "columns": columns,
            "sample_rows": sample_rows,
            "total_rows": len(rows),
            "duplicate_rows": duplicate_rows,
            "validation_failures": len(invalid_rows),
            "valid_rows": len(valid_rows),
            "errors": errors,
            "schema_errors": list(schema_errors),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Preview failed for kind=%s file=%s", kind, raw_filename,
        )
        raise HTTPException(status_code=500, detail=f"Preview failed: {exc}")
    finally:
        _cleanup_temp(temp.name)


@router.post("/import")
def import_file(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    file: UploadFile = File(...),
    kind: str = Form(..., description="trip|client|driver|truck|invoice"),
    dedup_action: str = Form("skip", description="skip|update|keep_both"),
    columns_map: Optional[str] = Form(
        None,
        description="Optional JSON object: source_column -> target_field",
    ),
    db: DatabaseManager = Depends(get_db),
):
    """Import rows from an uploaded CSV / Excel / JSON / XML file.

    Runs ``ImportService`` on the uploaded bytes (written to a temp file first)
    and returns the full pipeline stats plus a per-row error list.  When a
    ``columns_map`` form field is provided it is parsed as a JSON dict of
    source column → target field and applied through ``ImportService.apply_mapping``
    before validation/commit (column-mapping step of the wizard).  The result
    shape mirrors ``ImportStats`` and adds ``imported``/``skipped``/``errors``
    convenience keys.
    """
    entity_key = _KIND_TO_ENTITY.get((kind or "").lower())
    if entity_key is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported import kind: {kind!r}",
        )
    raw_filename = file.filename or "upload.csv"
    suffix = os.path.splitext(raw_filename)[1].lower()
    fmt_key = _IMPORT_FORMAT_BY_SUFFIX.get(suffix)
    if fmt_key is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {suffix or 'unknown'!r}. "
                f"Supported: .csv, .xls, .xlsx, .json, .xml"
            ),
        )

    mapping_dict = _parse_columns_map(columns_map)

    from services.migration.import_service import ImportService
    from services.migration.types import (
        EntityType,
        ImportFormat,
        ImportStats,
        MappingConfig,
    )

    entity_type = EntityType(entity_key)
    import_fmt = ImportFormat(fmt_key)
    commit_action = _DEDUP_ACTION_ALIASES.get(
        (dedup_action or "").lower(), "skip",
    )

    mapping_config: Optional[MappingConfig] = None
    if mapping_dict:
        mapping_config = MappingConfig(
            source_columns=list(mapping_dict.keys()),
            target_fields=mapping_dict,
            entity_type=entity_type,
        )

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)  # noqa: SIM115
    try:
        content = file.file.read()
        temp.write(content)
        temp.close()

        service = ImportService(db)
        rows, schema_errors = service.preview(temp.name, import_fmt, entity_type)
        if mapping_config is not None:
            rows = service.apply_mapping(rows, mapping_config)
        valid_rows, invalid_rows, _error_summary = service.validate_all(
            rows, entity_type,
        )
        if valid_rows:
            stats = service.commit(
                valid_rows, entity_type, dedup_action=commit_action,
            )
        else:
            stats = ImportStats(total_rows=len(rows))

        errors: list[Any] = list(schema_errors)  # schema errors are str messages
        for inv in invalid_rows:
            errors.append({
                "row": inv.get("row_index", 0),
                "message": "; ".join(inv.get("errors", [])),
                "data": inv.get("original", {}),
            })

        return {
            "total_rows": stats.total_rows,
            "valid_rows": stats.valid_rows,
            "committed": stats.committed,
            "duplicates_skipped": stats.duplicates_skipped,
            "validation_failures": stats.validation_failures,
            "imported": stats.committed,
            "skipped": stats.duplicates_skipped + stats.validation_failures,
            "errors": errors,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Import failed for kind=%s file=%s", kind, raw_filename,
        )
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}")
    finally:
        _cleanup_temp(temp.name)


@router.post("/archive")
def archive_document(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    file: UploadFile = File(...),
    entity_type: str = Form("migration"),
    entity_id: Optional[int] = Form(None),
    notes: str = Form(""),
    db: DatabaseManager = Depends(get_db),
):
    """Archive one physical document through the OCR/classification pipeline.

    Writes the uploaded bytes to a temp file and hands them to
    ``PhysicalArchiveService.process_batch``, then returns the per-document
    record (doc_id, doc_type, confidence, needs_confirmation, extracted,
    match_result, error) enriched with the supplied metadata.

    ``process_batch`` is called directly (instead of ``process_document``)
    because the latter looks results up by basename while the batch keyed by
    full path, which always fell back to the ``{"status": "error"}`` shape.
    """
    raw_filename = file.filename or "upload.pdf"
    suffix = os.path.splitext(raw_filename)[1].lower() or ".pdf"

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)  # noqa: SIM115
    try:
        content = file.file.read()
        temp.write(content)
        temp.close()

        from services.migration.physical_archive_service import (
            PhysicalArchiveService,
        )

        service = PhysicalArchiveService(db)
        batch = service.process_batch([temp.name])
        result = batch.get(temp.name)
        if not isinstance(result, dict):
            result = {}
        result["filename"] = raw_filename
        result["entity_type"] = sanitize_free_text(entity_type, max_length=50)
        result["entity_id"] = entity_id
        result["notes"] = sanitize_free_text(notes, max_length=1000)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Archive failed for file=%s", raw_filename)
        raise HTTPException(status_code=500, detail=f"Archive failed: {exc}")
    finally:
        _cleanup_temp(temp.name)


@router.post("/archive/{doc_id}/confirm")
def confirm_archived_document(
    doc_id: int,
    confirmed: bool = Body(True, description="User confirmation of the scanned document"),
    notes: str = Body("", description="Optional reviewer notes"),
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Confirm (or reject) a scanned document after OCR review.

    Runs the local confirmation path (``PhysicalArchiveService.confirm_document``)
    which merges any reviewer notes into the extracted payload, then returns
    the updated per-document record.  Raises 404 for an unknown *doc_id*.
    """
    from repositories.document_repository import DocumentRepository
    from services.migration.physical_archive_service import PhysicalArchiveService

    repo = DocumentRepository(db)
    doc = repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(
            status_code=404, detail=f"Document {doc_id} not found",
        )

    service = PhysicalArchiveService(db)
    corrections: dict[str, Any] = {}
    clean_notes = sanitize_free_text(notes, max_length=1000)
    if clean_notes:
        corrections["notes"] = clean_notes
    if not confirmed:
        corrections["confirmation_status"] = "rejected"

    ok = service.confirm_document(doc_id=doc_id, corrections=corrections)
    if not ok:
        raise HTTPException(
            status_code=500, detail=f"Failed to confirm document {doc_id}",
        )

    updated = repo.get_by_id(doc_id)
    return _document_record(updated, confirmed=bool(confirmed), notes=clean_notes)
