"""Mobile API endpoints — driver and dispatcher mobile surfaces.

All endpoints reuse existing services/repositories.  No business logic
is duplicated here — these are thin wrappers that:
  1. Scope data to the authenticated user / company
  2. Return condensed DTOs optimised for mobile bandwidth
  3. Provide aggregate endpoints that combine multiple data sources

Database tables required (created by ``_ensure_mobile_tables``):
  - mobile_devices  — FCM/APNs device tokens
  - mobile_messages — driver ↔ dispatcher chat messages
  - sync_cursors    — per-user, per-entity sync cursors
"""
from __future__ import annotations


import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from backend.dependencies import get_db
from backend.dependencies_security import get_current_user, require_dispatcher
from backend.schemas.mobile import (
    ActivityItem,
    ApprovalActionRequest,
    DeviceRegisterRequest,
    DispatcherAlertResponse,
    DispatcherDriverResponse,
    DispatcherJobResponse,
    DispatcherOverviewResponse,
    DriverMyDayResponse,
    DriverTripOverviewResponse,
    DriverTransportDetailResponse,
    DriverTransportResponse,
    DriverVehicleResponse,
    DownloadCategory,
    DownloadManifestEntry,
    DownloadRequest,
    FleetPositionResponse,
    MobileExpenseCreateRequest,
    MobileExpenseResponse,
    MobileMessageResponse,
    MobileMessageSendRequest,
    ReassignRequest,
    RevenueTrendPoint,
    RouteInstruction,
    RoutePoint,
    RouteShareResponse,
    StatusUpdateRequest,
    SyncResponse,
    TachoDayBucket,
    TachoTimelineOut,
    VehicleDocumentResponse,
)
from backend.db import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mobile", tags=["mobile"])


# ──────────────────────────────────────────────────────────────────────
#  Database initialisation — called once at app startup
# ──────────────────────────────────────────────────────────────────────

_MOBILE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS mobile_devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    company_id  INTEGER NOT NULL,
    device_id   TEXT    NOT NULL DEFAULT '',
    device_name TEXT    NOT NULL DEFAULT '',
    token       TEXT    NOT NULL,
    platform    TEXT    NOT NULL DEFAULT 'android',
    is_active   INTEGER NOT NULL DEFAULT 1,
    last_seen   TEXT,
    ip_address  TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(company_id, device_id)
);

CREATE TABLE IF NOT EXISTS mobile_messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id    INTEGER NOT NULL,
    sender_id     INTEGER NOT NULL,
    receiver_id   INTEGER NOT NULL,
    text          TEXT    NOT NULL,
    transport_id  INTEGER,
    is_read       INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sync_cursors (
    user_id      INTEGER NOT NULL,
    company_id   INTEGER NOT NULL,
    entity_type  TEXT    NOT NULL,
    cursor       TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, entity_type)
);
"""


def ensure_mobile_tables(db: DatabaseManager) -> None:
    """Create mobile-specific tables if they do not exist."""
    for statement in _MOBILE_TABLES_SQL.split(";"):
        stmt = statement.strip()
        if stmt:
            try:
                db.execute(stmt)
            except Exception as exc:
                logger.warning("Mobile table init: %s", exc)

    # ── Migration: add columns to existing mobile_devices table ──────────
    for alter_sql in [
        "ALTER TABLE mobile_devices ADD COLUMN device_id TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE mobile_devices ADD COLUMN device_name TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE mobile_devices ADD COLUMN last_seen TEXT",
        "ALTER TABLE mobile_devices ADD COLUMN ip_address TEXT NOT NULL DEFAULT ''",
    ]:
        try:
            db.execute(alter_sql)
        except Exception:
            pass  # column already exists

    # ── Migration: drop old UNIQUE if it exists (SQLite only) ──────────
    # SQLite cannot ALTER TABLE DROP CONSTRAINT, so we skip this step.
    # The old UNIQUE(user_id, token) constraint co-exists harmlessly with
    # the new UNIQUE(company_id, device_id) on existing tables.  The
    # DELETE+INSERT pattern in register_device handles both correctly.


# ──────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────

def _company_filter(params: Dict[str, Any], company_id: Any) -> str:
    """Append company_id to a param dict and return SQL filter clause."""
    params["_cid"] = company_id
    return "AND company_id = :_cid"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Contract status values for the mobile trip-overview screen.  The backend
# stores display statuses ('Planned', 'In Transit', ...) while the mobile
# contract (DriverTripOverview) uses the lowercase enum values below.
_TRIP_STATUS_TO_CONTRACT: Dict[str, Optional[str]] = {
    "planned": "planned",
    "loading": "loading",
    "in transit": "in_transit",
    "in_transit": "in_transit",
    "intransit": "in_transit",
    "delivered": "delivered",
    "completed": "delivered",
    "done": "delivered",
    "paid": "delivered",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}


def _map_trip_status(status: Any) -> Optional[str]:
    """Map a backend trip status string to the mobile contract enum value."""
    if not status:
        return None
    return _TRIP_STATUS_TO_CONTRACT.get(str(status).strip().lower())


# ══════════════════════════════════════════════════════════════════════
#  USER PROFILE SELF-SERVICE
# ══════════════════════════════════════════════════════════════════════


@router.get("/user/profile", response_model=Dict[str, Any])
def get_my_profile(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Return the current user's profile including linked driver info."""
    user_id = current_user["id"]

    # Admin users are resolved from env — no DB row exists for id=0
    if current_user.get("is_admin") or user_id == 0:
        return {
            "id": 0,
            "email": current_user.get("email", ""),
            "role": current_user.get("role", "admin"),
            "display_name": "Administrator",
            "driver_id": None,
            "is_active": True,
            "created_at": "",
            "driver": None,
        }

    row = db.execute(
        "SELECT id, email, role, display_name, driver_id, is_active, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    user = dict(row)
    # Add driver info if linked
    driver_info = None
    if user.get("driver_id"):
        dr = db.execute(
            "SELECT id, name, phone, license_number FROM drivers WHERE id = ?",
            (user["driver_id"],),
        ).fetchone()
        if dr:
            driver_info = dict(dr)
    user["driver"] = driver_info
    return user


@router.patch("/user/profile")
def update_my_profile(
    body: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Update the current user's display_name and email."""
    user_id = current_user["id"]
    updates = {}
    if "display_name" in body:
        updates["display_name"] = body["display_name"]
    if "email" in body:
        updates["email"] = body["email"]
    if not updates:
        return {"status": "no changes"}
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = tuple(list(updates.values()) + [user_id])
    db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
    db.commit()
    return {"status": "updated"}


# ══════════════════════════════════════════════════════════════════════
#  DRIVER ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@router.get("/driver/my-day", response_model=DriverMyDayResponse)
def driver_my_day(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Aggregate dashboard for the driver home screen."""
    user_id = current_user["id"]
    company_id = current_user["company_id"]
    driver_id = _resolve_driver_id(db, user_id, company_id)

    # Active transports count
    transport_count = 0
    next_stop = None
    next_stop_time = None
    recent_transports: List[Dict[str, Any]] = []

    if driver_id:
        transports = _get_driver_transports_raw(db, driver_id, company_id, limit=5)
        recent_transports = transports
        transport_count = len(transports)
        if transports:
            first = transports[0]
            next_stop = first.get("destination") or first.get("delivery_city")
            next_stop_time = first.get("scheduled_date") or first.get("start_date")

    # Unread messages
    unread = _count_unread_messages(db, user_id, company_id)

    # Recent messages
    recent_msgs = _get_recent_messages(db, user_id, company_id, limit=3)

    return DriverMyDayResponse(
        active_transports=transport_count,
        next_stop=next_stop,
        next_stop_time=next_stop_time,
        unread_messages=unread,
        recent_transports=[
            DriverTransportResponse(
                id=t["id"],
                load_info=t.get("reference", "") or t.get("load_info", ""),
                origin=t.get("loading_city", ""),
                destination=t.get("delivery_city", ""),
                status=t.get("status", ""),
                vehicle_plate=t.get("truck_plate", "") or t.get("truck_number", ""),
                scheduled_date=t.get("start_date"),
                last_updated=t.get("updated_at"),
            )
            for t in recent_transports
        ],
        recent_messages=[
            MobileMessageResponse(
                id=m["id"],
                sender_id=m["sender_id"],
                sender_name=m.get("sender_name", ""),
                receiver_id=m["receiver_id"],
                text=m["text"],
                timestamp=m.get("created_at"),
                is_read=bool(m.get("is_read", 0)),
            )
            for m in recent_msgs
        ],
    )


@router.get("/driver/trip-overview", response_model=DriverTripOverviewResponse)
def driver_trip_overview(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Overview of the driver's currently assigned trip.

    Returns HTTP 200 with every field null when the driver has no current
    trip assigned — the mobile app renders its empty state on that.
    ``company_id`` always comes from the JWT, never from client input.
    """
    user_id = current_user["id"]
    company_id = current_user["company_id"]
    driver_id = _resolve_driver_id(db, user_id, company_id)

    if not driver_id:
        return DriverTripOverviewResponse()

    # Current trip = most recent non-terminal trip assigned to this driver.
    # Terminal status list mirrors TripRepository.get_active_for_driver.
    row = db.execute(
        """SELECT t.id, t.cmr_number, t.place_of_loading, t.delivery_country,
                  t.status, t.start_date, t.end_date, t.created_at
           FROM trips t
           WHERE t.driver_id = ? AND t.company_id = ?
             AND (t.status IS NULL OR t.status = ''
                  OR UPPER(t.status) NOT IN ('DELIVERED', 'COMPLETED', 'DONE', 'CANCELLED', 'PAID'))
           ORDER BY t.created_at DESC
           LIMIT 1""",
        (driver_id, company_id),
    ).fetchone()

    if not row:
        return DriverTripOverviewResponse()

    r = dict(row)

    # status_since — most recent recorded status transition; falls back to
    # the trip's creation time when no status history has been recorded.
    status_changed_at = None
    try:
        hist = db.execute(
            "SELECT MAX(created_at) AS changed_at FROM trip_status_history WHERE trip_id = ?",
            (r["id"],),
        ).fetchone()
        status_changed_at = hist["changed_at"] if hist else None
    except Exception:
        pass  # trip_status_history may not exist in every deployment

    return DriverTripOverviewResponse(
        transport_id=str(r["id"]),
        load_info=(r.get("cmr_number") or "").strip() or None,
        origin=(r.get("place_of_loading") or "").strip() or None,
        destination=(r.get("delivery_country") or "").strip() or None,
        status=_map_trip_status(r.get("status")),
        status_since=status_changed_at or r.get("created_at"),
        eta=(r.get("end_date") or "").strip() or None,
        # end_date is a planned ETA (stale, not live telemetry) — "stale"
        # keeps it truthful while letting the app surface the value.
        eta_confidence="stale" if (r.get("end_date") or "").strip() else None,
    )


@router.get("/driver/transports", response_model=List[DriverTransportResponse])
def driver_transports(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """List all transports assigned to the current driver."""
    user_id = current_user["id"]
    company_id = current_user["company_id"]
    driver_id = _resolve_driver_id(db, user_id, company_id)

    if not driver_id:
        return []

    rows = _get_driver_transports_raw(db, driver_id, company_id, limit=100)

    return [
        DriverTransportResponse(
            id=r["id"],
            load_info=r.get("reference", "") or r.get("load_info", ""),
            origin=r.get("loading_city", ""),
            destination=r.get("delivery_city", ""),
            status=r.get("status", ""),
            vehicle_plate=r.get("truck_plate", "") or r.get("truck_number", ""),
            scheduled_date=r.get("start_date"),
            last_updated=r.get("updated_at"),
        )
        for r in rows
    ]


@router.get("/driver/transports/{transport_id}", response_model=DriverTransportDetailResponse)
def driver_transport_detail(
    transport_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Full detail for a single transport assigned to the driver."""
    company_id = current_user["company_id"]

    row = db.execute(
        """SELECT t.id, t.cmr_number AS reference, t.place_of_loading AS loading_city,
                  t.delivery_country AS delivery_city,
                  t.status, t.start_date, t.end_date, t.created_at AS updated_at,
                  t.truck_number, t.driver_name
           FROM trips t
           WHERE t.id = ? AND t.company_id = ?""",
        (transport_id, company_id),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Transport not found")

    r = dict(row)
    return DriverTransportDetailResponse(
        id=r["id"],
        load_info=r.get("reference", ""),
        origin=r.get("loading_city", ""),
        origin_lat=None,
        origin_lng=None,
        destination=r.get("delivery_city", ""),
        dest_lat=None,
        dest_lng=None,
        waypoints=[],
        status=r.get("status", ""),
        assigned_driver_name=r.get("driver_name", ""),
        vehicle_plate=r.get("truck_number", ""),
        scheduled_date=r.get("start_date"),
        delivered_date=r.get("end_date"),
        last_updated=r.get("updated_at"),
    )


@router.get("/driver/transports/{transport_id}/route-share", response_model=RouteShareResponse)
def get_route_share(
    transport_id: int,
    current_user: dict = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """
    Return route geometry and turn-by-turn instructions for a transport.
    Geometry is computed on-demand via GraphHopper; not persisted.
    """
    company_id = current_user["company_id"]

    # 1. Verify the transport exists and belongs to this user's company
    row = db.execute(
        """SELECT t.id, t.place_of_loading, t.delivery_country,
                  t.loading_country
           FROM trips t
           WHERE t.id = ? AND t.company_id = ?""",
        (transport_id, company_id),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Transport not found")

    return _build_route_share_response(db, row, transport_id)


@router.get("/driver/route-share", response_model=RouteShareResponse)
def get_driver_route_share(
    current_user: dict = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Route share for the driver's CURRENT transport — no ``transport_id``
    in the path.

    The server resolves the driver from the JWT (``_resolve_driver_id``) and
    uses the same current-trip query as ``/driver/trip-overview``, so the
    client can never influence which transport is shared (no IDOR surface).

    Empty behavior mirrors ``/driver/transports/{id}/route-share``: when the
    driver has no current transport the endpoint returns HTTP 404.
    """
    user_id = current_user["id"]
    company_id = current_user["company_id"]
    driver_id = _resolve_driver_id(db, user_id, company_id)

    if not driver_id:
        raise HTTPException(status_code=404, detail="Transport not found")

    # Current trip = most recent non-terminal trip assigned to this driver.
    # Terminal status list mirrors TripRepository.get_active_for_driver /
    # the mobile trip-overview endpoint.
    row = db.execute(
        """SELECT t.id, t.place_of_loading, t.delivery_country,
                  t.loading_country
           FROM trips t
           WHERE t.driver_id = ? AND t.company_id = ?
             AND (t.status IS NULL OR t.status = ''
                  OR UPPER(t.status) NOT IN ('DELIVERED', 'COMPLETED', 'DONE', 'CANCELLED', 'PAID'))
           ORDER BY t.created_at DESC
           LIMIT 1""",
        (driver_id, company_id),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Transport not found")

    return _build_route_share_response(db, row, row["id"])


def _build_route_share_response(db, row, transport_id: int) -> RouteShareResponse:
    """Compute on-demand route geometry and build a ``RouteShareResponse``.

    Shared by ``/driver/transports/{id}/route-share`` and
    ``/driver/route-share`` so both return identical payloads.
    """
    from backend.services.route_service import RouteService

    # 2. Build origin/destination addresses
    origin_address = (row.get("place_of_loading") or "").strip()
    dest_address = (row.get("delivery_country") or "").strip()

    if not origin_address or not dest_address:
        raise HTTPException(
            status_code=400,
            detail="Transport has no valid origin or destination address",
        )

    # 3. Calculate route via GraphHopper (geocodes addresses automatically)
    try:
        route_svc = RouteService()
        route_result = route_svc.calculate_route(
            stops=[origin_address, dest_address],
            stops_are_coordinates=False,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Route calculation failed: {str(e)}",
        )

    # 4. Build response
    geometry = route_result.get("geometry", [])
    instructions_raw = route_result.get("instructions", [])

    route_points = [RoutePoint(lat=lat, lng=lon) for lat, lon in geometry]
    route_instructions = [
        RouteInstruction(
            text_key=inst.get("text", ""),
            distance_meters=inst.get("distance_meters", 0),
            point_index=inst.get("point_index", 0),
        ) for inst in instructions_raw
    ]

    now = datetime.now(timezone.utc)
    return RouteShareResponse(
        transport_id=str(transport_id),
        points=route_points,
        instructions=route_instructions,
        total_distance_meters=route_result.get("distance_km", 0) * 1000,
        total_duration_seconds=int(route_result.get("duration_min", 0) * 60),
        generated_at=now.isoformat(),
        ttl_seconds=300,
    )


@router.patch("/transports/{transport_id}/status")
def update_transport_status(
    transport_id: int,
    body: StatusUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Update the status of a transport (driver or dispatcher)."""
    company_id = current_user["company_id"]

    # Verify the transport exists and belongs to this company
    existing = db.execute(
        "SELECT id, driver_id FROM trips WHERE id = ? AND company_id = ?",
        (transport_id, company_id),
    ).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Transport not found")

    # If the current user is a driver, verify they own this transport
    if current_user.get("role") == "driver":
        driver_id = _resolve_driver_id(db, current_user["id"], company_id)
        if driver_id and existing["driver_id"] != driver_id:
            raise HTTPException(status_code=403, detail="You do not own this transport")

    db.execute(
        "UPDATE trips SET status = ?, end_date = ? WHERE id = ?",
        (body.status, _now_iso(), transport_id),
    )
    db.commit()

    return {"status": body.status, "updated_at": _now_iso()}


@router.get("/driver/vehicle", response_model=DriverVehicleResponse)
def driver_vehicle(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Return the vehicle assigned to the current driver."""
    user_id = current_user["id"]
    company_id = current_user["company_id"]
    driver_id = _resolve_driver_id(db, user_id, company_id)

    if not driver_id:
        return DriverVehicleResponse(id=0)

    # Find the truck assigned to this driver via driver_truck_assignments
    row = db.execute(
        """SELECT t.id, t.plate_number, t.manufacturer AS brand, t.model, t.status
           FROM trucks t
           JOIN driver_truck_assignments dta ON dta.truck_id = t.id
           WHERE dta.driver_id = ? AND t.company_id = ?
           LIMIT 1""",
        (driver_id, company_id),
    ).fetchone()

    if not row:
        return DriverVehicleResponse(id=0)

    r = dict(row)

    # Vehicle documents
    docs: List[VehicleDocumentResponse] = []
    try:
        doc_rows = db.execute(
            """SELECT id, document_type, expiry_date
               FROM vehicle_documents
               WHERE vehicle_id = ? AND company_id = ?""",
            (r["id"], company_id),
        ).fetchall()
        for d in doc_rows:
            d = dict(d)
            expiry = d.get("expiry_date")
            is_expiring = False
            if expiry:
                try:
                    exp_date = datetime.fromisoformat(expiry)
                    is_expiring = (exp_date - datetime.now()).days < 30
                except (ValueError, TypeError):
                    pass
            docs.append(VehicleDocumentResponse(
                id=d["id"],
                document_type=d.get("document_type", ""),
                expiry_date=expiry,
                is_expiring_soon=is_expiring,
            ))
    except Exception:
        pass  # vehicle_documents table may not exist yet

    return DriverVehicleResponse(
        id=r["id"],
        plate=r.get("plate_number", ""),
        type="",
        brand=r.get("brand", ""),
        model=r.get("model", ""),
        status=r.get("status", ""),
        documents=docs,
    )


@router.get("/driver/tacho", response_model=TachoTimelineOut)
def get_driver_tacho_self(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
    start_date: str = Query("", description="ISO date YYYY-MM-DD (default: 6 days ago)"),
    end_date: str = Query("", description="ISO date YYYY-MM-DD (default: today)"),
):
    """Tachograph timeline for the CURRENT user's own driver profile.

    ANY authenticated role may call this (``get_current_user``): the driver is
    resolved server-side from the JWT via the shared ``_resolve_driver_id``
    helper (email-first, then ``drivers.user_id`` fallback) — never from a
    client-supplied id.  The timeline is built by the SAME
    ``build_tacho_timeline`` helper the dispatcher tacho endpoint uses, so both
    surfaces return identical buckets (default 7-day rolling window).
    """
    user_id = current_user["id"]
    company_id = current_user["company_id"]
    driver_id = _resolve_driver_id(db, user_id, company_id)
    if driver_id is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "driver_not_linked", "detail": "No driver profile linked to this user."},
        )

    from backend.api.v1.mobile.drivers import build_tacho_timeline

    return build_tacho_timeline(db, driver_id, start_date=start_date, end_date=end_date)


# ══════════════════════════════════════════════════════════════════════
#  DRIVER EXPENSES
# ══════════════════════════════════════════════════════════════════════


@router.get("/driver/expenses", response_model=List[MobileExpenseResponse])
def list_expenses(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """List expenses for the current driver."""
    user_id = current_user["id"]
    company_id = current_user["company_id"]
    driver_id = _resolve_driver_id(db, user_id, company_id)
    if not driver_id:
        return []
    rows = db.execute(
        """SELECT id, expense_category as expense_type, amount, currency,
                  issue_date as date, notes as description,
                  status
           FROM receipts
           WHERE driver_id = ? AND company_id = ?
           ORDER BY issue_date DESC LIMIT 100""",
        (driver_id, company_id),
    ).fetchall()
    return [MobileExpenseResponse(**dict(r)) for r in rows]


@router.post("/driver/expenses", response_model=Dict[str, int], status_code=201)
def create_expense(
    body: MobileExpenseCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Create a new expense for the driver."""
    user_id = current_user["id"]
    company_id = current_user["company_id"]
    driver_id = _resolve_driver_id(db, user_id, company_id)
    if not driver_id:
        raise HTTPException(status_code=400, detail="No driver profile linked")
    now = _now_iso()
    receipt_number = f"EXP-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    cursor = db.execute(
        """INSERT INTO receipts (company_id, driver_id, expense_category, amount, currency,
           issue_date, notes, receipt_number, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
        (company_id, driver_id, body.expense_type, body.amount,
         body.currency, body.date, body.description, receipt_number, now),
    )
    db.commit()
    return {"id": cursor.lastrowid}


# ══════════════════════════════════════════════════════════════════════
#  MESSAGING ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@router.get("/messages", response_model=List[MobileMessageResponse])
def list_messages(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Return all messages for the current user."""
    user_id = current_user["id"]
    company_id = current_user["company_id"]

    rows = db.execute(
        """SELECT m.id, m.sender_id, m.receiver_id, m.text, m.transport_id,
                  m.is_read, m.created_at,
                   COALESCE(s.display_name, s.email, '') AS sender_name
           FROM mobile_messages m
           LEFT JOIN users s ON s.id = m.sender_id
           WHERE (m.sender_id = ? OR m.receiver_id = ?)
             AND m.company_id = ?
           ORDER BY m.created_at DESC
           LIMIT 100""",
        (user_id, user_id, company_id),
    ).fetchall()

    return [
        MobileMessageResponse(
            id=r["id"],
            sender_id=r["sender_id"],
            sender_name=r.get("sender_name", ""),
            receiver_id=r["receiver_id"],
            text=r["text"],
            timestamp=r.get("created_at"),
            is_read=bool(r.get("is_read", 0)),
            transport_id=r.get("transport_id"),
        )
        for r in (dict(r) for r in rows)
    ]


@router.post("/messages", response_model=Dict[str, int], status_code=201)
def send_message(
    body: MobileMessageSendRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Send a message to another user."""
    user_id = current_user["id"]
    company_id = current_user["company_id"]

    cursor = db.execute(
        """INSERT INTO mobile_messages
           (company_id, sender_id, receiver_id, text, transport_id)
           VALUES (?, ?, ?, ?, ?)""",
        (company_id, user_id, body.receiver_id, body.text, body.transport_id),
    )
    msg_id = cursor.lastrowid
    db.commit()

    return {"id": msg_id}


# ══════════════════════════════════════════════════════════════════════
#  PUSH NOTIFICATION / DEVICE ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@router.post("/devices/register")
def register_device(
    body: DeviceRegisterRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Register a device token for push notifications.

    Uses DELETE + INSERT to handle upsert across both SQLite and PostgreSQL.
    """
    user_id = current_user["id"]
    company_id = current_user["company_id"]
    now = _now_iso()
    ip = request.client.host if request.client else ""

    # Remove any previous registration for this company+device
    db.execute(
        "DELETE FROM mobile_devices WHERE company_id = ? AND device_id = ?",
        (company_id, body.device_id),
    )

    db.execute(
        """INSERT INTO mobile_devices
           (user_id, company_id, device_id, device_name, token, platform,
            is_active, last_seen, ip_address)
           VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        (user_id, company_id, body.device_id, body.device_name or "",
         body.token, body.platform, now, ip),
    )
    db.commit()
    return {"status": "registered"}


@router.delete("/devices/register")
def unregister_device(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Unregister the current device from push notifications."""
    user_id = current_user["id"]

    db.execute(
        "UPDATE mobile_devices SET is_active = 0 WHERE user_id = ?",
        (user_id,),
    )
    db.commit()
    return {"status": "unregistered"}


@router.get("/devices")
def list_devices(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """List all devices registered for the current user's company.

    Only accessible by admin, manager, or dispatcher.
    """
    company_id = current_user["company_id"]

    rows = db.execute(
        """SELECT d.id, d.device_id, d.device_name, d.platform,
                  d.is_active, d.last_seen, d.created_at,
                  u.email AS user_email,
                  COALESCE(u.display_name, u.email) AS user_name
           FROM mobile_devices d
           LEFT JOIN users u ON u.id = d.user_id
           WHERE d.company_id = ?
           ORDER BY d.created_at DESC""",
        (company_id,),
    ).fetchall()

    return [dict(r) for r in rows]


@router.delete("/devices/{device_id:str}")
def deactivate_device(
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Deactivate a device by its UUID.

    Once deactivated, any subsequent refresh token issued for that device
    will be rejected.  Only accessible by admin, manager, or dispatcher.
    """
    company_id = current_user["company_id"]

    db.execute(
        "UPDATE mobile_devices SET is_active = 0 WHERE device_id = ? AND company_id = ?",
        (device_id, company_id),
    )
    db.commit()

    return {"status": "deactivated"}


# ══════════════════════════════════════════════════════════════════════
#  SYNC ENDPOINT
# ══════════════════════════════════════════════════════════════════════

@router.get("/sync", response_model=SyncResponse)
def delta_sync(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
    entity: str = Query("", description="Entity type to sync"),
    since: str = Query("", description="Cursor from last sync"),
    full: str = Query("", description="Set to 'true' for full sync"),
):
    """Delta-sync endpoint — returns changed records since last cursor.

    Currently a stub.  When ``entity`` is specified, queries the
    corresponding table for rows updated after ``since``.  Returns an
    empty result set until entity-specific sync logic is wired up.
    """
    company_id = current_user["company_id"]
    new_cursor = _now_iso()

    if not entity:
        return SyncResponse(records=[], cursor=new_cursor)

    # Build a query for the given entity type if the table exists
    query = ""
    params: tuple = ()
    is_full = full.lower() == "true"

    if entity == "transport" or entity == "trips":
        if is_full or not since:
            query = "SELECT * FROM trips WHERE company_id = ? ORDER BY updated_at DESC LIMIT 200"
            params = (company_id,)
        else:
            query = "SELECT * FROM trips WHERE company_id = ? AND updated_at > ? ORDER BY updated_at LIMIT 200"
            params = (company_id, since)

    elif entity == "message":
        user_id = current_user["id"]
        if is_full or not since:
            query = """SELECT * FROM mobile_messages
                       WHERE company_id = ? AND (sender_id = ? OR receiver_id = ?)
                       ORDER BY created_at DESC LIMIT 100"""
            params = (company_id, user_id, user_id)
        else:
            query = """SELECT * FROM mobile_messages
                       WHERE company_id = ? AND (sender_id = ? OR receiver_id = ?)
                         AND created_at > ?
                       ORDER BY created_at LIMIT 100"""
            params = (company_id, user_id, user_id, since)

    elif entity == "fleet":
        # Trucks have no created_at/updated_at columns, so ``since`` is a
        # monotonic id cursor (the endpoint returns ``cursor=str(max_id)``).
        if is_full or not since or not since.isdigit():
            query = "SELECT * FROM trucks WHERE company_id = ? ORDER BY id ASC LIMIT 200"
            params = (company_id,)
        else:
            query = "SELECT * FROM trucks WHERE company_id = ? AND id > ? ORDER BY id ASC LIMIT 200"
            params = (company_id, int(since))

    elif entity == "drivers":
        if is_full or not since:
            query = "SELECT * FROM drivers WHERE company_id = ? ORDER BY updated_at DESC LIMIT 200"
            params = (company_id,)
        else:
            query = "SELECT * FROM drivers WHERE company_id = ? AND updated_at > ? ORDER BY updated_at LIMIT 200"
            params = (company_id, since)

    elif entity == "clients":
        if is_full or not since:
            query = "SELECT * FROM clients WHERE company_id = ? ORDER BY updated_at DESC LIMIT 200"
            params = (company_id,)
        else:
            query = "SELECT * FROM clients WHERE company_id = ? AND updated_at > ? ORDER BY updated_at LIMIT 200"
            params = (company_id, since)

    if query:
        try:
            rows = db.execute(query, params).fetchall()
            records = [dict(r) for r in rows]
        except Exception as exc:
            logger.warning("Sync query failed for %s: %s", entity, exc)
            records = []

        # Fleet uses an id cursor (no timestamps); everything else uses the
        # request timestamp cursor.  Keep the fleet cursor monotonic even on
        # empty results so the client never re-syncs the whole fleet.
        if entity == "fleet":
            prev_id = int(since) if since.isdigit() else 0
            cursor = str(max((r["id"] for r in records), default=prev_id))
        else:
            cursor = new_cursor

        # Persist the cursor
        try:
            db.execute(
                """INSERT OR REPLACE INTO sync_cursors
                   (user_id, company_id, entity_type, cursor, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (current_user["id"], company_id, entity, cursor, cursor),
            )
            db.commit()
        except Exception:
            pass

        return SyncResponse(records=records, cursor=cursor, has_more=len(records) >= 100)

    return SyncResponse(records=[], cursor=new_cursor)


# ══════════════════════════════════════════════════════════════════════
#  DISPATCHER / MANAGER ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

def _coerce_int(raw) -> int:
    """Coerce *raw* to int; fall back to 0 for non-numeric values."""
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return 0


def _revenue_trend(db: DatabaseManager, company_id: int, months: int = 6) -> List[RevenueTrendPoint]:
    """Last *months* calendar months of company-scoped revenue.

    Revenue values come from the REAL analytics monthly-revenue query
    (``AnalyticsService.get_monthly_financial`` → ``AnalyticsRepository
    .get_monthly_financial_summary``) — no SQL is reimplemented here.  The
    tenant context is pinned so the repository's company filter applies.
    Calendar months with no trips are returned with ``revenue=0.0``.
    """
    from database.tenant_context import set_company_context
    from services.analytics_service import AnalyticsService

    # Last *months* calendar months, oldest → newest.
    now = datetime.now()
    keys = []
    y, m = now.year, now.month
    for _ in range(months):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y -= 1
            m = 12
    keys.reverse()

    try:
        set_company_context(company_id)
        # The real analytics query groups by month ASC + LIMIT — bound it to the
        # window with its own ``date_from``/``date_to`` so the returned months are
        # exactly the last *months* calendar months (not the oldest on file).
        y_end, m_end = int(keys[-1][:4]), int(keys[-1][5:7])
        if m_end == 12:
            window_end = f"{y_end + 1}-01-01"
        else:
            window_end = f"{y_end}-{m_end + 1:02d}-01"
        rows = AnalyticsService(db).get_monthly_financial(
            company_id=company_id,
            months=months,
            date_from=f"{keys[0]}-01",
            date_to=window_end,
        ) or []
    except Exception as exc:
        logger.warning("dispatcher overview revenue_trend failed: %s", exc)
        return []

    by_month = {}
    for r in rows:
        if isinstance(r, dict) and r.get("month"):
            try:
                by_month[str(r["month"])] = float(r.get("revenue") or 0.0)
            except (TypeError, ValueError):
                by_month[str(r["month"])] = 0.0

    return [RevenueTrendPoint(month=k, revenue=by_month.get(k, 0.0)) for k in keys]


def _recent_activity(db: DatabaseManager, company_id: int, cap: int = 10) -> List[ActivityItem]:
    """Union of the 5 most recent trips + 5 most recent alerts (company-scoped).

    Ordered by ``created_at`` descending and capped at *cap* (default 10).
    Uses the same per-entity queries the dispatcher jobs/alerts endpoints use.
    """
    items: List[ActivityItem] = []
    try:
        trips = db.execute(
            """SELECT id, COALESCE(NULLIF(cmr_number, ''), 'Trip #' || id) AS title, created_at
               FROM trips
               WHERE company_id = ?
               ORDER BY created_at DESC
               LIMIT 5""",
            (company_id,),
        ).fetchall()
        for r in (dict(r) for r in trips):
            items.append(ActivityItem(
                type="trip",
                id=r["id"],
                title=r.get("title") or "",
                created_at=r.get("created_at"),
            ))
    except Exception as exc:
        logger.warning("dispatcher overview recent_activity trips failed: %s", exc)

    try:
        alerts = db.execute(
            """SELECT id, title, created_at FROM alerts
               WHERE company_id = ?
               ORDER BY created_at DESC
               LIMIT 5""",
            (company_id,),
        ).fetchall()
        for r in (dict(r) for r in alerts):
            items.append(ActivityItem(
                type="alert",
                # alerts.id is TEXT (uuid hex in production) — the mobile
                # contract expects an int; coerce safely, 0 when not numeric.
                id=_coerce_int(r.get("id")),
                title=r.get("title") or "",
                created_at=r.get("created_at"),
            ))
    except Exception as exc:
        logger.warning("dispatcher overview recent_activity alerts failed: %s", exc)

    items.sort(key=lambda a: a.created_at or "", reverse=True)
    return items[:cap]


@router.get("/dispatcher/overview", response_model=DispatcherOverviewResponse)
def dispatcher_overview(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Aggregate dashboard for the dispatcher home screen."""
    company_id = current_user["company_id"]

    # Active jobs
    jobs = db.execute(
        """SELECT COUNT(*) as cnt FROM trips
           WHERE company_id = ? AND status NOT IN ('Delivered', 'Cancelled', 'Paid')""",
        (company_id,),
    ).fetchone()
    active_jobs = jobs["cnt"] if jobs else 0

    # Active drivers (those with an active trip)
    drivers = db.execute(
        """SELECT COUNT(DISTINCT driver_id) as cnt FROM trips
           WHERE company_id = ? AND driver_id IS NOT NULL
             AND status NOT IN ('Delivered', 'Cancelled')""",
        (company_id,),
    ).fetchone()
    active_drivers = drivers["cnt"] if drivers else 0

    # Open alerts
    alerts = 0
    try:
        a = db.execute(
            "SELECT COUNT(*) as cnt FROM alerts WHERE company_id = ? AND resolved = 0",
            (company_id,),
        ).fetchone()
        alerts = a["cnt"] if a else 0
    except Exception:
        pass

    # Vehicles on road
    trucks = db.execute(
        "SELECT COUNT(*) as cnt FROM trucks WHERE company_id = ? AND status = 'active'",
        (company_id,),
    ).fetchone()
    vehicles_on_road = trucks["cnt"] if trucks else 0

    # Revenue to date — sum of trip prices with start_date in the current
    # calendar month (month-to-date).  trips.start_date is ISO TEXT; the
    # lexicographic comparison with 'YYYY-MM-01' is valid for both date-only
    # and datetime-with-timezone values.  NULL/empty start_date is excluded.
    first_of_month = datetime.now().strftime("%Y-%m-01")
    rev = db.execute(
        """SELECT COALESCE(SUM(total_price_eur), 0) AS revenue
           FROM trips
           WHERE company_id = ?
             AND start_date IS NOT NULL AND start_date != ''
             AND start_date >= ?""",
        (company_id, first_of_month),
    ).fetchone()
    revenue_to_date = float(rev["revenue"]) if rev and rev["revenue"] is not None else 0.0

    return DispatcherOverviewResponse(
        active_jobs=active_jobs,
        active_drivers=active_drivers,
        open_alerts=alerts,
        vehicles_on_road=vehicles_on_road,
        revenue_to_date=revenue_to_date,
        revenue_trend=_revenue_trend(db, company_id),
        recent_activity=_recent_activity(db, company_id),
    )


@router.get("/dispatcher/fleet", response_model=List[FleetPositionResponse])
def dispatcher_fleet(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return current fleet positions."""
    company_id = current_user["company_id"]

    rows = db.execute(
        """SELECT t.id, t.plate_number, t.status,
                  COALESCE(d.name, '') AS driver_name
           FROM trucks t
           LEFT JOIN driver_truck_assignments dta ON dta.truck_id = t.id
           LEFT JOIN drivers d ON d.id = dta.driver_id
           WHERE t.company_id = ?
           LIMIT 200""",
        (company_id,),
    ).fetchall()

    return [
        FleetPositionResponse(
            vehicle_id=r["id"],
            plate=r.get("plate_number", ""),
            driver_name=r.get("driver_name", ""),
            lat=None,
            lng=None,
            status=r.get("status", ""),
            last_update=None,
        )
        for r in (dict(r) for r in rows)
    ]


@router.get("/dispatcher/jobs", response_model=List[DispatcherJobResponse])
def dispatcher_jobs(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    statuses: Optional[str] = Query(
        None,
        description="Comma-separated trip statuses to include, e.g. 'Delivered,Cancelled'. "
                    "When provided, the default NOT-IN exclusion is replaced by an IN filter "
                    "over these statuses.  Absent → existing behavior unchanged.",
    ),
):
    """Return active jobs for the dispatcher.

    Without ``statuses`` the historical NOT-IN exclusion applies (excludes
    Delivered / Cancelled / Paid).  With ``statuses`` the filter is an IN
    over the requested statuses (enables e.g. Kanban columns for delivered
    / cancelled work).
    """
    company_id = current_user["company_id"]

    status_list = [s.strip() for s in (statuses or "").split(",") if s.strip()]
    if status_list:
        placeholders = ", ".join("?" for _ in status_list)
        params: tuple = (company_id, *status_list)
        status_sql = f"t.status IN ({placeholders})"
    else:
        params = (company_id,)
        status_sql = "t.status NOT IN ('Delivered', 'Cancelled', 'Paid')"

    rows = db.execute(
        f"""SELECT t.id, t.cmr_number AS reference, t.driver_name, t.truck_number,
                   t.status, t.place_of_loading AS loading_city,
                   t.delivery_country AS delivery_city, t.created_at AS updated_at,
                   t.start_date, t.end_date
            FROM trips t
            WHERE t.company_id = ? AND {status_sql}
            ORDER BY t.created_at DESC
            LIMIT 200""",
        params,
    ).fetchall()

    def _safe(val):
        """Convert None to empty string, pass through everything else."""
        return "" if val is None else val

    return [
        DispatcherJobResponse(
            id=r["id"],
            load_info=_safe(r.get("reference")),
            driver_name=_safe(r.get("driver_name")),
            vehicle_plate=_safe(r.get("truck_number")),
            status=_safe(r.get("status")),
            origin=_safe(r.get("loading_city")),
            destination=_safe(r.get("delivery_city")),
            last_updated=r.get("updated_at"),
            start_date=r.get("start_date"),
            end_date=r.get("end_date"),
        )
        for r in (dict(r) for r in rows)
    ]


@router.post("/dispatcher/jobs/{transport_id}/reassign")
def reassign_transport(
    transport_id: int,
    data: ReassignRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Reassign a transport (trip) to an active driver (gate: require_dispatcher).

    Company-scoped (Gate-29 A1): the trip must belong to the caller's company
    (404 otherwise); the target driver must exist, belong to the same company
    and be active (404 otherwise).
    """
    company_id = current_user["company_id"]

    trip = db.execute(
        "SELECT id FROM trips WHERE id = ? AND company_id = ?",
        (transport_id, company_id),
    ).fetchone()
    if not trip:
        raise HTTPException(status_code=404, detail="Transport not found")

    driver = db.execute(
        "SELECT id FROM drivers WHERE id = ? AND company_id = ? AND is_active = 1",
        (data.driver_id, company_id),
    ).fetchone()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    db.execute(
        "UPDATE trips SET driver_id = ? WHERE id = ? AND company_id = ?",
        (data.driver_id, transport_id, company_id),
    )
    db.commit()

    return {"status": "reassigned", "transport_id": transport_id, "driver_id": data.driver_id}


@router.get("/dispatcher/drivers", response_model=List[DispatcherDriverResponse])
def dispatcher_drivers(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return driver list with status."""
    company_id = current_user["company_id"]

    rows = db.execute(
        """SELECT d.id, d.name,
                  (SELECT t.cmr_number FROM trips t
                   WHERE t.driver_id = d.id
                     AND t.status NOT IN ('Delivered', 'Cancelled')
                     AND t.company_id = d.company_id
                   LIMIT 1) AS current_transport,
                  (SELECT tk.plate_number FROM trucks tk
                   JOIN driver_truck_assignments dta ON dta.truck_id = tk.id
                   WHERE dta.driver_id = d.id
                     AND tk.company_id = d.company_id
                   LIMIT 1) AS current_vehicle
           FROM drivers d
           WHERE d.company_id = ? AND d.is_active = 1
           ORDER BY d.name
           LIMIT 200""",
        (company_id,),
    ).fetchall()

    results = []
    for r in rows:
        r = dict(r)
        # Determine driver status
        if r.get("current_transport"):
            driver_status = "driving"
        elif r.get("current_vehicle"):
            driver_status = "available"
        else:
            driver_status = "off"
        results.append(DispatcherDriverResponse(
            id=r["id"],
            name=r.get("name", ""),
            status=driver_status,
            current_transport=r.get("current_transport"),
            current_vehicle=r.get("current_vehicle"),
        ))
    return results


@router.get("/dispatcher/alerts", response_model=List[DispatcherAlertResponse])
def dispatcher_alerts(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return alert inbox for the dispatcher."""
    company_id = current_user["company_id"]

    try:
        rows = db.execute(
            """SELECT id, type AS alert_type, title, message, severity,
                      created_at, truck_id, trip_id
               FROM alerts
               WHERE company_id = ? AND resolved = 0
               ORDER BY created_at DESC
               LIMIT 100""",
            (company_id,),
        ).fetchall()
    except Exception:
        return []

    return [
        DispatcherAlertResponse(
            id=r["id"],
            type=r.get("alert_type", ""),
            title=r.get("title", ""),
            description=r.get("message", ""),
            severity=r.get("severity", ""),
            is_read=False,
            created_at=r.get("created_at"),
            related_entity_id=r.get("trip_id") or r.get("truck_id"),
            related_entity_type="trip" if r.get("trip_id") else "truck" if r.get("truck_id") else "",
        )
        for r in (dict(r) for r in rows)
    ]


@router.post("/dispatcher/approvals/{approval_id}/approve")
def approve_action(
    approval_id: int,
    body: ApprovalActionRequest = ApprovalActionRequest(),
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Approve a pending action (alert, expense, etc.)."""
    company_id = current_user["company_id"]

    # Mark the alert as resolved/approved
    try:
        db.execute(
            """UPDATE alerts SET resolved = 1, resolved_at = ?
               WHERE id = ? AND company_id = ?""",
            (_now_iso(), approval_id, company_id),
        )
        db.commit()
    except Exception as exc:
        logger.warning("approve_action failed for alert %s: %s", approval_id, exc)

    return {"status": "approved", "id": approval_id}


@router.post("/dispatcher/approvals/{approval_id}/reject")
def reject_action(
    approval_id: int,
    body: ApprovalActionRequest = ApprovalActionRequest(),
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Reject a pending action."""
    company_id = current_user["company_id"]

    try:
        db.execute(
            """UPDATE alerts SET resolved = 1, resolved_at = ?
               WHERE id = ? AND company_id = ?""",
            (_now_iso(), approval_id, company_id),
        )
        db.commit()
    except Exception as exc:
        logger.warning("reject_action failed for alert %s: %s", approval_id, exc)

    return {"status": "rejected", "id": approval_id}


@router.post("/dispatcher/transports", response_model=Dict[str, int], status_code=201)
def create_transport_mobile(
    body: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Create a new transport from mobile (simplified)."""
    company_id = current_user["company_id"]
    now = _now_iso()
    if body.get("start_date"):
        _validate_start_date(str(body["start_date"]))
    cursor = db.execute(
        """INSERT INTO trips (company_id, cmr_number, place_of_loading, delivery_country,
           driver_id, driver_name, truck_number, status, start_date, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'Planned', ?, ?, ?)""",
        (company_id,
         body.get("reference", ""),
         body.get("loading_city", ""),
         body.get("delivery_city", ""),
         body.get("driver_id"),
         body.get("driver_name", ""),
         body.get("truck_plate", ""),
         body.get("start_date", now),
         now, now),
    )
    db.commit()
    return {"id": cursor.lastrowid}


# ══════════════════════════════════════════════════════════════════════
#  LOCAL DOWNLOAD — signed short-lived URL manifest (blueprint §5.3)
# ══════════════════════════════════════════════════════════════════════

# Category mapping from the blueprint's 5 download categories onto the real
# data model.  Documents are the general bucket; invoices/receipts map to the
# document categories the invoicing pipeline writes; ocr_results are
# documents that have actually been OCR-processed (regardless of category);
# trip_history maps to the trips table (exported as JSON on demand).
_DOCUMENT_QUERIES = {
    DownloadCategory.documents: "category NOT IN ('invoice', 'invoices', 'receipt', 'receipts')",
    DownloadCategory.invoices: "category IN ('invoice', 'invoices')",
    DownloadCategory.receipts: "category IN ('receipt', 'receipts')",
    DownloadCategory.ocr_results: (
        "((ocr_run_at IS NOT NULL AND ocr_run_at != '') "
        "OR (ocr_text IS NOT NULL AND ocr_text != ''))"
    ),
}


def _build_download_url(token: str) -> str:
    """Return the absolute signed download URL for a token.

    The path is API-relative; the scheme/host are taken from the incoming
    request (or fall back to a relative URL for non-HTTP contexts).
    """
    return f"/api/v1/mobile/company/export/download/{token}"


@router.post("/company/export/manifest", response_model=List[DownloadManifestEntry])
def company_export_manifest(
    body: DownloadRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return the company-scoped file list for pull-on-demand local download.

    Blueprint §5.3: the response is a list of ``DownloadManifestEntry``
    whose ``download_url`` values carry an HMAC-signed, short-lived token
    (default 15 minutes) over ``{record_id, company_id, expiry}``.  Raw file
    bytes are never returned by this endpoint — the mobile client downloads
    each entry individually from the companion fetch endpoint.

    ``company_id`` always comes from the JWT — never from the client body.
    ``date_from``/``date_to`` filter on the record's upload/creation date
    (ISO YYYY-MM-DD).

    Pull-on-demand only — there is no background sync machinery behind this
    endpoint; OCR results stay server-side until the client explicitly pulls
    them.
    """
    from backend.services.local_download_service import (
        KIND_DOCUMENT,
        KIND_TRIP,
        create_download_token,
        download_token_ttl_seconds,
    )

    company_id = current_user["company_id"]

    if body.category is DownloadCategory.trip_history:
        return _trip_history_manifest(db, company_id, body)

    # ── Documents (documents / invoices / receipts / ocr_results) ──────
    category_clause = _DOCUMENT_QUERIES[body.category]
    params: list = [company_id]
    clauses = ["company_id = ?", "is_archived = 0", category_clause]

    if body.date_from:
        _validate_date_from(body.date_from)
        clauses.append("uploaded_at >= ?")
        params.append(body.date_from)
    if body.date_to:
        _validate_date_to(body.date_to)
        clauses.append("uploaded_at <= ?")
        if "T" not in body.date_to and " " not in body.date_to:
            params.append(f"{body.date_to}T23:59:59")
        else:
            params.append(body.date_to)

    where = " AND ".join(clauses)
    try:
        rows = db.execute(
            f"""SELECT id, category, file_name, file_size,
                       COALESCE(NULLIF(updated_at, ''), uploaded_at) AS modified_at
                FROM documents
                WHERE {where}
                ORDER BY modified_at DESC
                LIMIT 500""",
            tuple(params),
        ).fetchall()
    except Exception as exc:
        logger.warning("company_export_manifest query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Manifest query failed")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=download_token_ttl_seconds())

    entries: List[DownloadManifestEntry] = []
    for row in rows:
        r = dict(row)
        record_id = str(r["id"])
        token = create_download_token(
            record_id=record_id,
            company_id=company_id,
            kind=KIND_DOCUMENT,
            expires_at=expires_at,
        )
        entries.append(
            DownloadManifestEntry(
                record_id=record_id,
                filename=r.get("file_name", "") or "",
                size_bytes=int(r.get("file_size") or 0),
                download_url=_build_download_url(token),
                url_expires_at=expires_at.isoformat(),
            )
        )
    return entries


def _validate_date_param(value: str, field: str) -> None:
    """Strictly validate an ISO-8601 date-filter value before it reaches SQL."""
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid {field} — expected ISO-8601 "
                "(e.g. 2026-07-31 or 2026-07-31T23:59:59)"
            ),
        )


def _validate_date_to(date_to: str) -> None:
    """Strictly validate an ISO-8601 ``to_date`` before it reaches SQL."""
    _validate_date_param(date_to, "to_date")


def _validate_date_from(date_from: str) -> None:
    """Strictly validate an ISO-8601 ``from_date`` before it reaches SQL."""
    _validate_date_param(date_from, "from_date")


def _validate_start_date(value: str) -> None:
    """Validate a client-supplied ``start_date`` is a valid ISO date.

    Rejects malformed values with 422 so raw garbage never reaches
    ``trips.start_date``.  Mirrors ``_validate_date_param`` but returns 422.
    """
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Invalid start_date — expected ISO date (YYYY-MM-DD).",
        )


def _trip_history_manifest(
    db: DatabaseManager,
    company_id: Any,
    body: DownloadRequest,
) -> List[DownloadManifestEntry]:
    """Build manifest entries for the ``trip_history`` category (trips table).

    Trip history has no stored file — the fetch endpoint synthesizes a JSON
    export on demand, so ``size_bytes`` here is the serialized JSON length.
    """
    from backend.services.local_download_service import (
        KIND_TRIP,
        create_download_token,
        download_token_ttl_seconds,
    )

    params: list = [company_id]
    clauses = ["company_id = ?"]

    if body.date_from:
        _validate_date_from(body.date_from)
        clauses.append("COALESCE(NULLIF(created_at, ''), start_date) >= ?")
        params.append(body.date_from)
    if body.date_to:
        _validate_date_to(body.date_to)
        clauses.append("COALESCE(NULLIF(created_at, ''), start_date) <= ?")
        if "T" not in body.date_to and " " not in body.date_to:
            params.append(f"{body.date_to}T23:59:59")
        else:
            params.append(body.date_to)

    where = " AND ".join(clauses)
    try:
        rows = db.execute(
            f"""SELECT id, created_at, status, client_name, driver_name, truck_number,
                       place_of_loading, delivery_country, distance_km, total_price_eur,
                       currency
                FROM trips
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT 500""",
            tuple(params),
        ).fetchall()
    except Exception as exc:
        logger.warning("company_export_manifest trip_history query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Manifest query failed")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=download_token_ttl_seconds())

    entries: List[DownloadManifestEntry] = []
    for row in rows:
        r = dict(row)
        record_id = str(r["id"])
        payload = _serialize_trip(r)
        token = create_download_token(
            record_id=record_id,
            company_id=company_id,
            kind=KIND_TRIP,
            expires_at=expires_at,
        )
        entries.append(
            DownloadManifestEntry(
                record_id=record_id,
                filename=f"trip-{record_id}.json",
                size_bytes=len(payload.encode("utf-8")),
                download_url=_build_download_url(token),
                url_expires_at=expires_at.isoformat(),
            )
        )
    return entries


def _serialize_trip(row: Dict[str, Any]) -> str:
    """Serialize a trips-table row into the JSON bytes the download endpoint streams."""
    import json as _json

    payload = {
        "record_id": str(row.get("id")),
        "trip_id": row.get("id"),
        "status": row.get("status"),
        "client_name": row.get("client_name"),
        "driver_name": row.get("driver_name"),
        "truck_number": row.get("truck_number"),
        "origin": row.get("place_of_loading"),
        "destination": row.get("delivery_country"),
        "created_at": row.get("created_at"),
        "distance_km": row.get("distance_km"),
        "total_price": row.get("total_price_eur"),
        "currency": row.get("currency"),
    }
    return _json.dumps(payload, ensure_ascii=False, indent=2)


@router.get("/company/export/download/{token}")
def company_export_download(
    token: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Fetch the raw bytes for a manifest entry.

    Validates, in order:
      1. the HMAC signature (tampered tokens → 403),
      2. the embedded expiry (expired tokens → 403),
      3. the tenant at **fetch time**: the JWT's ``company_id`` must equal
         the token's embedded ``company_id`` — a signed URL minted for
         company Y cannot be replayed under company X's JWT (→ 403).

    Streams the stored document file (``FileResponse``, document MIME type)
    for ``document`` records, or a synthesized JSON export (``application/json``)
    for ``trip`` records.
    """
    from fastapi.responses import FileResponse, JSONResponse

    from backend.services.local_download_service import (
        KIND_DOCUMENT,
        KIND_EXPORT_FILE,
        KIND_TRIP,
        is_token_expired,
        verify_download_token,
    )

    payload = verify_download_token(token)
    if payload is None:
        raise HTTPException(status_code=403, detail="Invalid download token")
    if is_token_expired(payload):
        raise HTTPException(status_code=403, detail="Download token expired")

    # Tenant check at fetch time — never trust the URL alone.
    token_company_id = payload.get("company_id")
    if current_user.get("company_id") != token_company_id:
        raise HTTPException(
            status_code=403,
            detail="Download token does not belong to this company",
        )

    record_id = payload.get("record_id")
    kind = payload.get("kind")

    if kind == KIND_TRIP:
        row = db.execute(
            """SELECT id, created_at, status, client_name, driver_name, truck_number,
                      place_of_loading, delivery_country, distance_km, total_price_eur,
                      currency
               FROM trips
               WHERE id = ? AND company_id = ?""",
            (int(record_id), token_company_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Trip not found")
        content = _serialize_trip(dict(row))
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="trip-{record_id}.json"'},
        )

    if kind == KIND_DOCUMENT:
        row = db.execute(
            """SELECT id, file_path, file_name, mime_type
               FROM documents
               WHERE id = ? AND company_id = ? AND is_archived = 0""",
            (int(record_id), token_company_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        r = dict(row)
        file_path = r.get("file_path") or ""
        if not file_path or not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail="Document file not found")
        media_type = r.get("mime_type") or "application/octet-stream"
        return FileResponse(
            file_path,
            filename=r.get("file_name") or os.path.basename(file_path),
            media_type=media_type,
        )

    if kind == KIND_EXPORT_FILE:
        # Phase 2A: generated analytics/history export files.  The token's
        # record_id is the export_jobs row id; the file is resolved from the
        # company-scoped job row (never from the raw token value alone).
        job = db.execute(
            """SELECT id, status, result_path, company_id
               FROM export_jobs
               WHERE id = ? AND company_id = ?""",
            (int(record_id), token_company_id),
        ).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Export not found")
        j = dict(job)
        if j.get("status") != "success" or not j.get("result_path"):
            raise HTTPException(status_code=404, detail="Export not ready")
        export_path = j["result_path"]
        if not os.path.isfile(export_path):
            raise HTTPException(status_code=404, detail="Export file not found")
        # Defense-in-depth: the result_path lives in the export_jobs row, but
        # a corrupted/foreign row must never serve a file outside the export
        # directory (path-traversal guard; resolves symlinks first).
        from services.mobile_export_service import get_export_dir

        export_root = os.path.realpath(get_export_dir())
        try:
            inside_export_dir = os.path.commonpath(
                [os.path.realpath(export_path), export_root]
            ) == export_root
        except ValueError:  # different drives (Windows) → not inside
            inside_export_dir = False
        if not inside_export_dir:
            raise HTTPException(status_code=404, detail="Export file not found")
        ext = os.path.splitext(export_path)[1].lower()
        media_types = {".csv": "text/csv", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".pdf": "application/pdf"}
        return FileResponse(
            export_path,
            filename=os.path.basename(export_path),
            media_type=media_types.get(ext, "application/octet-stream"),
        )

    raise HTTPException(status_code=404, detail="Unknown record type")


# ══════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════

def _resolve_driver_id(db: DatabaseManager, user_id: int, company_id: Any) -> Optional[int]:
    """Resolve the driver_id for a given user.

    First tries matching by email (look up the user's email, then
    find a driver with that email).  Falls back to user_id column
    on the drivers table if the email match does not succeed.
    Returns ``None`` if no linked driver record is found.
    """
    # Primary: match by email
    user_row = db.execute(
        "SELECT email FROM users WHERE id = ? AND company_id = ? LIMIT 1",
        (user_id, company_id),
    ).fetchone()
    if user_row:
        email = user_row["email"]
        driver_by_email = db.execute(
            "SELECT id FROM drivers WHERE email = ? AND company_id = ? LIMIT 1",
            (email, company_id),
        ).fetchone()
        if driver_by_email:
            return driver_by_email["id"]

    # Fallback: match by user_id column (may not exist on all databases)
    row = db.execute(
        "SELECT id FROM drivers WHERE user_id = ? AND company_id = ? LIMIT 1",
        (user_id, company_id),
    ).fetchone()
    if row:
        return row["id"]

    return None


def _get_driver_transports_raw(
    db: DatabaseManager, driver_id: int, company_id: Any, *, limit: int = 100
) -> List[Dict[str, Any]]:
    rows = db.execute(
        """SELECT id, cmr_number AS reference, place_of_loading AS loading_city,
                  delivery_country AS delivery_city, status,
                  truck_number, start_date, created_at AS updated_at
           FROM trips
           WHERE driver_id = ? AND company_id = ?
           ORDER BY created_at DESC
           LIMIT ?""",
        (driver_id, company_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _count_unread_messages(db: DatabaseManager, user_id: int, company_id: Any) -> int:
    try:
        row = db.execute(
            """SELECT COUNT(*) AS cnt FROM mobile_messages
               WHERE receiver_id = ? AND company_id = ? AND is_read = 0""",
            (user_id, company_id),
        ).fetchone()
        return row["cnt"] if row else 0
    except Exception:
        return 0


def _get_recent_messages(
    db: DatabaseManager, user_id: int, company_id: Any, *, limit: int = 5
) -> List[Dict[str, Any]]:
    try:
        rows = db.execute(
            """SELECT m.id, m.sender_id, m.receiver_id, m.text, m.is_read, m.created_at,
                       COALESCE(s.display_name, s.email, '') AS sender_name
               FROM mobile_messages m
               LEFT JOIN users s ON s.id = m.sender_id
               WHERE (m.sender_id = ? OR m.receiver_id = ?)
                 AND m.company_id = ?
               ORDER BY m.created_at DESC
               LIMIT ?""",
            (user_id, user_id, company_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
