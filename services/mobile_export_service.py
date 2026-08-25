"""Mobile export helpers — Phase 2A (analytics + history async export).

Shared by the analytics sync-export handler, the history export Celery task
and the download endpoint resolution.  Export files land in
``BackendSettings().export_dir`` (env ``OPERION_EXPORT_DIR``, default
``data/exports``), which the test-suite redirects to a temp dir.

Trip export format matrix (honest, REAL WINS):
  - csv  — stdlib ``csv`` writer (always available).
  - xlsx — openpyxl Workbook (installed; if the import fails at runtime the
           job errors with a clear message).
  - pdf  — reuses the existing desktop ``ExportService.generate_pdf``
           (reportlab, installed); on any failure the job errors with
           'PDF export unavailable'.
"""
from __future__ import annotations

import csv
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

EXPORT_FILE_EXTENSIONS = {"csv": ".csv", "xlsx": ".xlsx", "pdf": ".pdf"}


def get_export_dir() -> str:
    """Return the export directory, creating it if necessary.

    ``BackendSettings`` is server-only — the packaged desktop build ships no
    ``backend`` package — so the import is lazy + guarded with an env-var
    fallback (``OPERION_EXPORT_DIR``, default ``data/exports``).
    """
    export_dir = os.environ.get("OPERION_EXPORT_DIR")
    if not export_dir:
        try:
            from backend.config import BackendSettings
            export_dir = BackendSettings().export_dir
        except ImportError:
            export_dir = None
    export_dir = export_dir or "data/exports"
    os.makedirs(export_dir, exist_ok=True)
    return export_dir


# ── Trip query used by both the history list endpoint and the exporter ────

def build_trip_filters(filters: Optional[Dict[str, Any]], company_id: int) -> tuple:
    """Turn an export-filter dict into (where, params)."""
    clauses = ["company_id = ?"]
    params: list = [company_id]
    f = filters or {}
    if f.get("status"):
        clauses.append("status = ?")
        params.append(str(f["status"]))
    if f.get("client_id"):
        clauses.append("client_id = ?")
        params.append(int(f["client_id"]))
    if f.get("start_date"):
        clauses.append("start_date >= ?")
        params.append(str(f["start_date"]))
    if f.get("end_date"):
        clauses.append("start_date <= ?")
        params.append(str(f["end_date"]))
    return " AND ".join(clauses), params


def fetch_trips_for_export(db, company_id: int, filters: Optional[Dict[str, Any]]) -> list:
    """Fetch the trip rows for an export (company-scoped)."""
    where, params = build_trip_filters(filters, company_id)
    rows = db.execute(
        f"SELECT id, client_name, truck_number, driver_name, place_of_loading, "
        f"delivery_country, status, start_date, end_date, distance_km, "
        f"total_price_eur, net_profit "
        f"FROM trips WHERE {where} ORDER BY start_date DESC, id DESC",
        tuple(params),
    ).fetchall()
    return [dict(r) for r in rows]


def _write_csv(trips: list, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "id", "client_name", "truck_number", "driver_name", "origin",
            "destination", "status", "start_date", "end_date", "distance_km",
            "total_price_eur", "net_profit",
        ])
        for t in trips:
            writer.writerow([
                t.get("id"), t.get("client_name"), t.get("truck_number"),
                t.get("driver_name"), t.get("place_of_loading"),
                t.get("delivery_country"), t.get("status"), t.get("start_date"),
                t.get("end_date"), t.get("distance_km"),
                t.get("total_price_eur"), t.get("net_profit"),
            ])


def _write_xlsx(trips: list, path: str) -> None:
    from openpyxl import Workbook  # imported lazily; raises if not installed

    wb = Workbook()
    ws = wb.active
    ws.title = "Trips"
    ws.append([
        "id", "client_name", "truck_number", "driver_name", "origin",
        "destination", "status", "start_date", "end_date", "distance_km",
        "total_price_eur", "net_profit",
    ])
    for t in trips:
        ws.append([
            t.get("id"), t.get("client_name"), t.get("truck_number"),
            t.get("driver_name"), t.get("place_of_loading"),
            t.get("delivery_country"), t.get("status"), t.get("start_date"),
            t.get("end_date"), t.get("distance_km"),
            t.get("total_price_eur"), t.get("net_profit"),
        ])
    wb.save(path)


def _write_pdf(trips: list, path: str) -> None:
    """Reuse the desktop ExportService (deprecated list path) for the PDF.

    It writes to its own reports dir then we move the file into the export
    dir.  Any failure (import / generation) raises — the caller turns it into
    the honest 'PDF export unavailable' error status.
    """
    from services.export_service import ExportService

    svc = ExportService(db=None)
    generated = svc.generate_pdf(trips, os.path.basename(path))
    if not generated or not os.path.isfile(generated):
        raise RuntimeError("ExportService returned no file")
    if os.path.normpath(str(generated)) != os.path.normpath(path):
        import shutil
        shutil.move(str(generated), path)


def build_trips_export(db, company_id: int, fmt: str,
                       filters: Optional[Dict[str, Any]]) -> str:
    """Generate a trips export file; returns the absolute result path.

    Raises ``ValueError`` for unknown formats and ``RuntimeError`` when the
    requested format cannot be produced (xlsx without openpyxl / pdf failure).
    """
    if fmt not in EXPORT_FILE_EXTENSIONS:
        raise ValueError(f"Unsupported export format: {fmt!r}")

    trips = fetch_trips_for_export(db, company_id, filters)
    export_dir = get_export_dir()
    import time
    path = os.path.join(export_dir, f"trips_{fmt}_{company_id}_{int(time.time())}{EXPORT_FILE_EXTENSIONS[fmt]}")

    if fmt == "csv":
        _write_csv(trips, path)
    elif fmt == "xlsx":
        try:
            _write_xlsx(trips, path)
        except ImportError:
            raise RuntimeError("XLSX export unavailable: openpyxl is not installed")
    elif fmt == "pdf":
        try:
            _write_pdf(trips, path)
        except Exception as exc:  # honest — pdf cannot be produced
            logger.warning("PDF export unavailable: %s", exc)
            raise RuntimeError("PDF export unavailable") from exc

    if not os.path.isfile(path):
        raise RuntimeError("Export file was not written")
    return path
