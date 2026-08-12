"""Mobile history endpoints (blueprint §6.8).

  - GET  /mobile/history/trips?status&client_id&start_date&end_date&page&page_size
        -> PaginatedResponse[TripHistoryOut]        [require_dispatcher]
  - GET  /mobile/history/routes?page&page_size&start_date&end_date
        -> PaginatedResponse[RouteHistoryOut]       [require_dispatcher]
  - POST /mobile/history/trips/export {format, filters} -> 202 {job_id}
        [require_dispatcher + can_export_data]
  - GET  /mobile/history/trips/export/{job_id}/status -> {status, download_url?}
        [require_dispatcher]

Company scoping: trips carry ``company_id`` (tenant migrations); every query
here scopes explicitly on ``current_user["company_id"]``.

Route scoping: ``route_history_v2`` gets its ``company_id`` column from the
runtime tenant migrations (db_manager ``_tenant_tables``).  For robustness we
detect the column at runtime and scope when present; otherwise the query is
company-agnostic (documented — this only affects databases created before the
migration, where routes were never tenant-attributed).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.common import PaginatedResponse
from backend.schemas.mobile import (
    ExportJobStatusResponse,
    RouteHistoryOut,
    TripHistoryExportJobResponse,
    TripHistoryExportRequest,
    TripHistoryOut,
)
from repositories.export_job_repository import ExportJobRepository
from services.permission_service import PermissionService

router = APIRouter(prefix="/history", tags=["mobile_history"])


def _check_export_permission(db: DatabaseManager, user_id: int) -> None:
    """Gate async exports with the real PermissionService (can_export_data)."""
    if not user_id:
        return
    result = PermissionService(db).can_export_data(user_id)
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.reason or "Permission denied")


def _table_has_column(db: DatabaseManager, table: str, column: str) -> bool:
    try:
        cols = [r[1] for r in db.conn.execute(f"PRAGMA table_info({table})").fetchall()]
        return column in cols
    except Exception:
        return False


# ── Trips history ────────────────────────────────────────────────────────


@router.get("/trips", response_model=PaginatedResponse[TripHistoryOut])
def list_trip_history(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    status: str = Query("", description="Exact match on real trip status"),
    client_id: Optional[int] = Query(None),
    start_date: str = Query(""),
    end_date: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """Paginated, company-scoped trip history with filters."""
    company_id = current_user["company_id"]
    clauses = ["company_id = ?"]
    params: list = [company_id]
    if status:
        clauses.append("status = ?")
        params.append(status)
    if client_id:
        clauses.append("client_id = ?")
        params.append(client_id)
    if start_date:
        clauses.append("start_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("start_date <= ?")
        params.append(end_date)
    where = " AND ".join(clauses)

    cnt = db.execute(
        f"SELECT COUNT(*) AS cnt FROM trips WHERE {where}", tuple(params)
    ).fetchone()
    total = dict(cnt)["cnt"] if cnt else 0

    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT id, client_name, truck_number, driver_name, place_of_loading, "
        f"delivery_country, status, start_date, end_date, distance_km, "
        f"total_price_eur, net_profit "
        f"FROM trips WHERE {where} ORDER BY start_date DESC, id DESC "
        f"LIMIT ? OFFSET ?",
        tuple(params) + (page_size, offset),
    ).fetchall()

    items = []
    for raw in rows:
        r = dict(raw)
        items.append(
            TripHistoryOut(
                id=r["id"],
                client_name=r["client_name"] or "",
                truck_number=r["truck_number"] or "",
                driver_name=r["driver_name"] or "",
                origin=r["place_of_loading"] or "",
                destination=r["delivery_country"] or "",
                status=r["status"] or "",
                start_date=r["start_date"],
                end_date=r["end_date"],
                distance_km=r["distance_km"],
                total_price_eur=r["total_price_eur"],
                net_profit=r["net_profit"],
            )
        )
    return PaginatedResponse.from_items(
        items=items, total=total, page=page, page_size=page_size
    )


# ── Route history ────────────────────────────────────────────────────────


@router.get("/routes", response_model=PaginatedResponse[RouteHistoryOut])
def list_route_history(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    start_date: str = Query(""),
    end_date: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """Paginated route history from route_history_v2 (excludes deleted)."""
    company_id = current_user["company_id"]
    clauses = ["(deleted_at IS NULL OR deleted_at = '')"]
    params: list = []
    if _table_has_column(db, "route_history_v2", "company_id"):
        clauses.append("company_id = ?")
        params.append(company_id)
    if start_date:
        clauses.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("created_at <= ?")
        params.append(end_date)
    where = " AND ".join(clauses)

    cnt = db.execute(
        f"SELECT COUNT(*) AS cnt FROM route_history_v2 WHERE {where}", tuple(params)
    ).fetchone()
    total = dict(cnt)["cnt"] if cnt else 0

    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT id, route_fingerprint, stops_json, total_distance_km, "
        f"duration_min, created_at FROM route_history_v2 "
        f"WHERE {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        tuple(params) + (page_size, offset),
    ).fetchall()

    items = []
    for raw in rows:
        r = dict(raw)
        origin, destination = _route_endpoints(r.get("stops_json") or "")
        items.append(
            RouteHistoryOut(
                id=r["id"],
                name=r["route_fingerprint"] or "",
                origin=origin,
                destination=destination,
                total_distance_km=r["total_distance_km"],
                duration_min=r["duration_min"],
                created_at=r["created_at"],
            )
        )
    return PaginatedResponse.from_items(
        items=items, total=total, page=page, page_size=page_size
    )


def _route_endpoints(stops_json: str) -> tuple[Optional[str], Optional[str]]:
    """Derive origin/destination from the first/last stop if derivable.

    ``stops_json`` is a JSON array of stop objects; each stop may carry
    ``city``/``name``/``address``/``location`` — we use the first available
    label per stop.  Returns ``(None, None)`` when nothing is derivable.
    """
    try:
        stops = json.loads(stops_json)
    except (ValueError, TypeError):
        return None, None
    if not isinstance(stops, list) or not stops:
        return None, None

    def _label(stop: Any) -> Optional[str]:
        if not isinstance(stop, dict):
            return None
        for key in ("city", "name", "address", "location", "label"):
            value = stop.get(key)
            if value:
                return str(value)
        return None

    first = _label(stops[0])
    last = _label(stops[-1]) if len(stops) > 1 else None
    return first, last


# ── Route thumbnail (schematic PNG) ───────────────────────────────────────
# On-demand render: generation is fast (a few ms on a 320×180 supersampled
# canvas), so no caching layer is added — every request re-renders from the
# stored geometry blob.  Geometry is decoded with the repo's exact zlib-json
# contract (see ``RouteHistoryService._compress_json``).

_THUMB_WIDTH = 320
_THUMB_HEIGHT = 180
_THUMB_PADDING = 16          # px margin around the geometry bbox (at 1×)
_THUMB_SCALE = 4             # supersample factor → LANCZOS anti-aliasing
_THUMB_LINE_WIDTH = 3        # polyline width in output pixels
_THUMB_BG = (248, 250, 252)      # slate-50 light background
_THUMB_FRAME = (203, 213, 225)   # slate-300 subtle bounding frame
_THUMB_LINE = (37, 99, 235)      # blue-600 polyline / dot


def _decode_route_geometry(raw) -> List[List[float]]:
    """Decode ``route_history_v2.geometry_compressed`` → ``[[lat, lon], ...]``.

    The writer stores ``zlib.compress(json.dumps([(lat, lon), ...]))`` — the
    decompressed JSON is a list of ``[lat, lon]`` arrays (lat first, lon
    second).  Returns ``[]`` for a missing / empty / undecodable blob or an
    empty coordinate list (caller turns that into a 404).
    """
    if not raw:
        return []
    import zlib

    try:
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        if not isinstance(raw, bytes):
            return []
        decoded = json.loads(zlib.decompress(raw).decode("utf-8"))
    except Exception:
        return []
    if not isinstance(decoded, list) or not decoded:
        return []

    coords: List[List[float]] = []
    for pt in decoded:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        try:
            lat, lon = float(pt[0]), float(pt[1])
        except (TypeError, ValueError):
            continue
        if lat != lat or lon != lon:  # NaN guard
            continue
        coords.append([lat, lon])
    return coords


def _render_route_thumbnail(
    coords: List[List[float]],
    width: int = _THUMB_WIDTH,
    height: int = _THUMB_HEIGHT,
    padding: int = _THUMB_PADDING,
) -> Optional[bytes]:
    """Render a schematic polyline PNG for a coordinate list.

    Coordinates are normalized to the geometry bounding box (lat inverted →
    north-up) with *padding* on each side, drawn on a supersampled canvas and
    downscaled with LANCZOS for anti-aliasing.  Degenerate inputs (single
    point / zero extent in either axis) never crash — the geometry collapses
    to a centered dot with the bounding frame; a 2-point route renders as a
    straight segment.  Returns ``None`` only when no drawable coordinate
    remains.
    """
    import io

    from PIL import Image, ImageDraw

    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    lat_span = max_lat - min_lat
    lon_span = max_lon - min_lon

    scale = _THUMB_SCALE
    sw, sh = width * scale, height * scale
    spad = padding * scale
    img = Image.new("RGB", (sw, sh), _THUMB_BG)
    draw = ImageDraw.Draw(img)

    inner = (spad, spad, sw - spad, sh - spad)  # left, top, right, bottom

    def _px(value: float, vmin: float, span: float, lo: float, hi: float, invert: bool) -> float:
        if span <= 0:
            return (lo + hi) / 2.0
        ratio = (value - vmin) / span
        return lo + (1.0 - ratio if invert else ratio) * (hi - lo)

    pts = [
        (
            _px(c[1], min_lon, lon_span, inner[0], inner[2], invert=False),
            _px(c[0], min_lat, lat_span, inner[1], inner[3], invert=True),
        )
        for c in coords
    ]
    if not pts:
        return None

    if lat_span <= 0 and lon_span <= 0:
        # Degenerate: single point / zero extent → dot + frame, never crash.
        cx, cy = pts[0]
        r = max(5 * scale, 2)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_THUMB_LINE)
    else:
        draw.line(pts, fill=_THUMB_LINE, width=_THUMB_LINE_WIDTH * scale, joint="curve")

    draw.rectangle([0, 0, sw - 1, sh - 1], outline=_THUMB_FRAME, width=scale)

    out = img.resize((width, height), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


@router.get("/routes/{route_id}/thumbnail")
def route_thumbnail(
    route_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Schematic polyline PNG for a route-history row (company-scoped).

    200 → ``image/png``; 404 when the route is missing / belongs to another
    company / is soft-deleted / has no decodable geometry.  Rendered on
    demand from the stored ``geometry_compressed`` blob — no cache (fast).
    """
    company_id = current_user["company_id"]
    clauses = ["id = ?", "(deleted_at IS NULL OR deleted_at = '')"]
    params: list = [route_id]
    if _table_has_column(db, "route_history_v2", "company_id"):
        clauses.append("company_id = ?")
        params.append(company_id)
    where = " AND ".join(clauses)

    row = db.execute(
        f"SELECT geometry_compressed, geometry_encoding "
        f"FROM route_history_v2 WHERE {where}",
        tuple(params),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Route not found")

    coords = _decode_route_geometry(dict(row).get("geometry_compressed"))
    if not coords:
        raise HTTPException(status_code=404, detail="Route geometry unavailable")

    png = _render_route_thumbnail(coords)
    if png is None:
        raise HTTPException(status_code=404, detail="Route geometry unavailable")
    return Response(content=png, media_type="image/png")


# ── Async trips export ───────────────────────────────────────────────────


@router.post("/trips/export", response_model=TripHistoryExportJobResponse, status_code=202)
def create_trips_export(
    body: TripHistoryExportRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Enqueue a trips history export (gate: can_export_data — dispatcher allowed).

    Creates an ``export_jobs`` row (status=processing) and dispatches the
    Celery task.  In test environments ``task_always_eager=True`` runs the
    job synchronously before this returns, so the job is typically already
    ``success``/``error`` by the time the client polls.
    """
    _check_export_permission(db, current_user.get("id") or 0)
    company_id = current_user["company_id"]

    job_id = ExportJobRepository(db).create(
        kind="trips_export",
        # Gate-29 A4: record the requesting user so the Celery task can call
        # the typed ExportService PDF path with a real user id (0 = system/
        # internal-admin convention).
        params={
            "format": body.format,
            "filters": body.filters.model_dump(exclude_none=True),
            "user_id": current_user.get("id") or 0,
        },
        company_id=company_id,
        status="processing",
    )

    from backend.celery_app.tasks.export_tasks import export_trips_job
    from backend.celery_app.tasks.export_tasks import _extract_db_path

    export_trips_job.apply_async(  # type: ignore[attr-defined]
        args=(job_id, company_id),
        kwargs={"db_path": _extract_db_path(db), "engine": getattr(db, "_engine", "sqlite")},
    )
    return TripHistoryExportJobResponse(job_id=job_id)


@router.get("/trips/export/{job_id}/status", response_model=ExportJobStatusResponse)
def trips_export_status(
    job_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Poll an export job; returns a signed 10-min download URL once success."""
    company_id = current_user["company_id"]
    job = ExportJobRepository(db).get(job_id, company_id=company_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")

    status = job.get("status") or "processing"
    download_url = None
    if status == "success" and job.get("result_path"):
        from backend.services.local_download_service import (
            KIND_EXPORT_FILE,
            create_download_token,
        )
        from datetime import datetime, timedelta, timezone

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=600)
        token = create_download_token(
            record_id=job_id,
            company_id=company_id,
            kind=KIND_EXPORT_FILE,
            expires_at=expires_at,
        )
        download_url = f"/api/v1/mobile/company/export/download/{token}"
    return ExportJobStatusResponse(status=status, download_url=download_url)
