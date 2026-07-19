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

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.dependencies import get_db
from backend.dependencies_security import get_current_user, require_dispatcher
from backend.schemas.mobile import (
    ApprovalActionRequest,
    DeviceRegisterRequest,
    DispatcherAlertResponse,
    DispatcherDriverResponse,
    DispatcherJobResponse,
    DispatcherOverviewResponse,
    DriverMyDayResponse,
    DriverTransportDetailResponse,
    DriverTransportResponse,
    DriverVehicleResponse,
    FleetPositionResponse,
    MobileExpenseCreateRequest,
    MobileExpenseResponse,
    MobileMessageResponse,
    MobileMessageSendRequest,
    RouteInstruction,
    RoutePoint,
    RouteShareResponse,
    StatusUpdateRequest,
    SyncResponse,
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
    from backend.services.route_service import RouteService

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

    if query:
        try:
            rows = db.execute(query, params).fetchall()
            records = [dict(r) for r in rows]
        except Exception as exc:
            logger.warning("Sync query failed for %s: %s", entity, exc)
            records = []

        # Persist the cursor
        try:
            db.execute(
                """INSERT OR REPLACE INTO sync_cursors
                   (user_id, company_id, entity_type, cursor, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (current_user["id"], company_id, entity, new_cursor, new_cursor),
            )
            db.commit()
        except Exception:
            pass

        return SyncResponse(records=records, cursor=new_cursor, has_more=len(records) >= 100)

    return SyncResponse(records=[], cursor=new_cursor)


# ══════════════════════════════════════════════════════════════════════
#  DISPATCHER / MANAGER ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

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

    return DispatcherOverviewResponse(
        active_jobs=active_jobs,
        active_drivers=active_drivers,
        open_alerts=alerts,
        vehicles_on_road=vehicles_on_road,
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
):
    """Return active jobs for the dispatcher."""
    company_id = current_user["company_id"]

    rows = db.execute(
        """SELECT t.id, t.cmr_number AS reference, t.driver_name, t.truck_number,
                  t.status, t.place_of_loading AS loading_city,
                  t.delivery_country AS delivery_city, t.created_at AS updated_at
           FROM trips t
           WHERE t.company_id = ?
             AND t.status NOT IN ('Delivered', 'Cancelled', 'Paid')
           ORDER BY t.created_at DESC
           LIMIT 200""",
        (company_id,),
    ).fetchall()

    return [
        DispatcherJobResponse(
            id=r["id"],
            load_info=r.get("reference", ""),
            driver_name=r.get("driver_name", ""),
            vehicle_plate=r.get("truck_number", ""),
            status=r.get("status", ""),
            origin=r.get("loading_city", ""),
            destination=r.get("delivery_city", ""),
            last_updated=r.get("updated_at"),
        )
        for r in (dict(r) for r in rows)
    ]


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
