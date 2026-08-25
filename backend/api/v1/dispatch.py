"""Dispatch board API — remote-mode endpoints for the desktop dispatch board.

These endpoints replace the desktop view's local-DB service layer
(``services/dispatch_service/``) so the board can run against the FastAPI
backend.  They compose EXISTING services/repositories — no business logic
is duplicated here:

  - GET  /dispatch/board                       — trips grouped by kanban column + counts
  - GET  /dispatch/driver-hours                — weekly driving hours per driver vs tacho limits
  - PATCH /dispatch/trips/{trip_id}/status     — validated status transition + conflict check
  - GET  /dispatch/trips/{trip_id}/detail      — trip + client summary + alerts + linked documents + route stops
  - PATCH /dispatch/trips/{trip_id}/assignment — assign/clear a trip's truck and/or driver
  - POST  /dispatch/assignments/bulk           — apply a truck/driver assignment to many trips
  - GET   /dispatch/trips/{trip_id}/delay      — trip delay evaluation (mirrors the local board rules)
  - POST  /dispatch/trips/{trip_id}/delay-alerts — create/resolve a trip's delay alert (AlertManager)
  - GET   /dispatch/slots/next                 — next available slot for a driver and/or truck

Column semantics mirror ``services.dispatch_service.dispatch_service``
(``STATUS_TO_COLUMN`` / ``COLUMN_KEYS``); the driver-hours computation
mirrors the local dispatch board (``ui/views/dispatch_board/board_actions.py``
and ``services/operations/maintenance_engine.evaluate_driver_hours``).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.db import DatabaseManager
from backend.dependencies import get_db, get_trip_service
from backend.dependencies_security import require_dispatcher
from backend.services.trip_service import TripService
from models.trip_models import TripUpdate
from repositories.client_repository import ClientRepository
from repositories.driver_repository import DriverRepository
from repositories.fleet_repository import FleetRepository
from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
from repositories.trip_repository import TripRepository
from services.operations.event_bus import VALID_TRANSITIONS
from services.tacho_service import EU_MAX_WEEKLY_DRIVING_MINUTES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dispatch", tags=["dispatch"])

# ── Canonical status → column mapping (mirrors dispatch_service.py) ──────
STATUS_TO_COLUMN: dict[str, str] = {
    "Planned": "Planned",
    "Scheduled": "Planned",
    "Pending": "Planned",
    "Loading": "Loading",
    "Preparing": "Loading",
    "Pickup": "Loading",
    "In Transit": "In Transit",
    "InTransit": "In Transit",
    "Active": "In Transit",
    "InProgress": "In Transit",
    "Delivered": "Delivered",
    "Completed": "Delivered",
    "Done": "Delivered",
    "Invoiced": "Delivered",
    "Paid": "Delivered",
    "Cancelled": "Cancelled",
}

COLUMN_KEYS = ["Planned", "Loading", "In Transit", "Delivered", "Cancelled"]

# EU weekly driving cap (Regulation (EC) 561/2006) — 56h/week, in hours.
WEEKLY_LIMIT_HOURS: float = EU_MAX_WEEKLY_DRIVING_MINUTES / 60.0

# Status aliases normalised before transition validation (mirrors
# ``services/operations/trip_status_workflow.py``).
_STATUS_NORMALIZATION = {
    "InTransit": "In Transit",
    "Active": "In Transit",
    "InProgress": "In Transit",
}


def _normalize_status(status: str) -> str:
    return _STATUS_NORMALIZATION.get(status, status)


class TripStatusUpdateRequest(BaseModel):
    """Request body for a trip status transition."""

    status: str


def _resolve_route(trip: dict[str, Any], route_repo: Any) -> tuple[str, str]:
    """Resolve origin/destination from ``route_history_v2`` summary (best-effort).

    Mirrors ``DispatchService._resolve_route`` — no-op when route data is
    unavailable or unparseable.
    """
    route_id = trip.get("route_history_v2_id")
    if not route_id or route_repo is None:
        return "", ""
    try:
        route = route_repo.get_by_id(int(route_id))
        if not route:
            return "", ""
        summary = route.get("route_summary_json")
        if not summary:
            return "", ""
        summary_data = json.loads(summary) if isinstance(summary, str) else summary
        return (
            summary_data.get("origin", "") or "",
            summary_data.get("destination", "") or "",
        )
    except Exception as exc:
        logger.warning(
            "dispatch: failed to resolve route for trip #%s: %s",
            trip.get("id"), exc,
        )
        return "", ""


def _build_card_data(
    trip: dict[str, Any],
    route_repo: Any,
    column: str,
) -> dict[str, Any]:
    """Build a single board-card dict from a trip row (mirrors ``_build_card_data``)."""
    trip_id = trip.get("id", 0)
    origin, destination = _resolve_route(trip, route_repo)
    return {
        "trip_id": f"#{trip_id}",
        "trip_id_num": trip_id,
        "column": column,
        "status": trip.get("status", "Planned"),
        "truck_plate": trip.get("truck_number", "") or "",
        "truck_id": trip.get("truck_id"),
        "driver_name": trip.get("driver_name", "") or "",
        "driver_id": trip.get("driver_id"),
        "origin": origin,
        "destination": destination,
        "departure_date": trip.get("start_date", "") or "",
        "eta": trip.get("end_date", "") or "",
        "alerts_count": 0,
    }


def _get_trip_alerts(db: DatabaseManager, trip_id: int) -> list[dict[str, Any]]:
    """Return active alerts linked to a trip (reuses the AlertManager service).

    The alert manager is the same singleton the ``/alerts`` router uses; the
    trip filter matches the in-memory ``Alert.trip_id`` (string form).
    """
    try:
        from services.operations.alert_manager import AlertManager
        manager = AlertManager(db)
        alerts = manager.get_active_alerts(limit=2000)
        filtered = [a for a in alerts if a.trip_id == str(trip_id)]
        return [
            {
                "id": a.id,
                "type": a.type.value,
                "severity": a.severity.value,
                "title": a.title,
                "message": a.message,
                "created_at": a.created_at,
            }
            for a in filtered
        ]
    except Exception as exc:
        logger.warning(
            "dispatch: failed to load alerts for trip #%d: %s", trip_id, exc,
        )
        return []


# ── 1. Board data ─────────────────────────────────────────────────────────


@router.get("/board")
def get_dispatch_board(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    delivered_window_days: int = Query(
        30, ge=0, le=365,
        description="Keep Delivered/Cancelled trips newer than this many days",
    ),
    limit: int = Query(200, ge=1, le=2000, description="Max trips per status"),
    service: TripService = Depends(get_trip_service),
):
    """Return dispatch-board data: trips grouped by kanban column + counts.

    Mirrors ``DispatchService.get_dispatch_board_data`` column semantics
    (status → column mapping, delivered/cancelled cutoff window, card shape).
    """
    company_id = current_user.get("company_id", 0)
    cutoff = (date.today() - timedelta(days=delivered_window_days)).strftime("%Y-%m-%d")
    route_repo = getattr(service, "_route_repo", None)

    column_trips: dict[str, list[dict[str, Any]]] = {col: [] for col in COLUMN_KEYS}

    # Fetch per-status through TripService (company-scoped) and bucket by column.
    try:
        seen: set[int] = set()
        for raw_status in STATUS_TO_COLUMN:
            trips = service.get_filtered(
                search="", status=raw_status, limit=limit, company_id=company_id,
            )
            for trip in trips or []:
                trip_id = trip.get("id")
                if trip_id is None or trip_id in seen:
                    continue
                seen.add(trip_id)

                column = STATUS_TO_COLUMN.get(trip.get("status", ""))
                if not column:
                    continue

                # Delivered/cancelled trips outside the window are hidden.
                if column in ("Delivered", "Cancelled"):
                    trip_date = trip.get("end_date", "") or trip.get("created_at", "")
                    trip_date = str(trip_date)[:10] if trip_date else ""
                    if trip_date and trip_date < cutoff:
                        continue

                column_trips[column].append(_build_card_data(trip, route_repo, column))
    except Exception as exc:
        logger.error("dispatch: failed to load board data: %s", exc, exc_info=True)

    status_counts = {col: len(column_trips[col]) for col in COLUMN_KEYS}
    flat_trips = [card for col in COLUMN_KEYS for card in column_trips[col]]
    return {"columns": status_counts, "trips": flat_trips}


# ── 2. Driver hours vs tacho limits ───────────────────────────────────────


@router.get("/driver-hours")
def get_driver_hours(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    week_start: str = Query(
        "", description="ISO date YYYY-MM-DD starting the 7-day window (default: last 7 days)",
    ),
    db: DatabaseManager = Depends(get_db),
):
    """Return weekly driving hours per driver vs the EU tacho limit.

    Mirrors the LOCAL dispatch board computation (``board_actions.py`` /
    ``MaintenanceEngine.evaluate_driver_hours``): sums ``driving_minutes``
    from ``tacho_driver_activity`` over the window, collects stored
    violations, and flags the weekly 56h EU cap.
    """
    company_id = current_user.get("company_id", 0)

    if week_start:
        try:
            start = date.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Invalid week_start — expected ISO date (YYYY-MM-DD).",
            )
        end = start + timedelta(days=6)
    else:
        end = date.today()
        start = end - timedelta(days=6)

    driver_repo = DriverRepository(db)
    activity_repo = TachoDriverActivityRepository(db)

    items: list[dict[str, Any]] = []
    try:
        drivers = driver_repo.get_all(limit=1000, company_id=company_id) or []
    except Exception as exc:
        logger.error("dispatch: failed to list drivers: %s", exc, exc_info=True)
        drivers = []

    for driver in drivers:
        if not driver.get("is_active"):
            continue
        driver_id = driver.get("id")
        driver_name = driver.get("name") or driver.get("driver_name") or ""
        week_hours = 0.0
        violations: list[str] = []

        try:
            records = activity_repo.get_by_driver(
                driver_id, start, company_id=company_id,
            ) or []
            # Filter the window end in memory (repo supports ``date_from`` only).
            records = [
                r for r in records
                if str(r.get("activity_date", ""))[:10] <= end.isoformat()
            ]
            week_hours = round(
                sum(r.get("driving_minutes", 0) or 0 for r in records) / 60.0, 2,
            )

            # Stored per-day violations (same source the local board counts).
            for record in records:
                raw = record.get("violations")
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                if isinstance(parsed, list):
                    violations.extend(str(v) for v in parsed)
        except Exception as exc:
            logger.warning(
                "dispatch: failed to compute hours for driver %s: %s",
                driver_id, exc,
            )

        if week_hours > WEEKLY_LIMIT_HOURS:
            violations.append(
                f"Weekly driving {week_hours:.1f}h exceeds {WEEKLY_LIMIT_HOURS:.0f}h EU limit"
            )

        items.append({
            "driver_id": driver_id,
            "driver_name": driver_name,
            "week_hours": week_hours,
            "weekly_limit_hours": WEEKLY_LIMIT_HOURS,
            "violations": violations,
        })

    return {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "drivers": items,
    }


# ── 3. Status transitions (validated + conflict-checked) ──────────────────


@router.patch("/trips/{trip_id}/status")
def update_trip_status(
    trip_id: int,
    data: TripStatusUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: TripService = Depends(get_trip_service),
    db: DatabaseManager = Depends(get_db),
):
    """Transition a trip to a new status (validated + conflict-checked).

    Reuses the existing transition logic: ``VALID_TRANSITIONS`` from the
    operations event bus for validation, ``TripService.update`` for the
    mutation (company-scoped), and ``TripConflictService`` for the
    post-update conflict check (same service as ``POST /trips/conflicts/check``).
    """
    company_id = current_user.get("company_id", 0)
    trip = service.get_by_id(trip_id, company_id=company_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    old_status = trip.get("status", "")
    new_status = data.status
    normalized_old = _normalize_status(old_status)
    normalized_new = _normalize_status(new_status)

    valid_targets = VALID_TRANSITIONS.get(normalized_old, [])
    if normalized_new not in valid_targets:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot transition trip #{trip_id} from '{old_status}' "
                f"to '{new_status}' — valid options: {valid_targets}"
            ),
        )

    result = service.update(
        trip_id, TripUpdate(status=normalized_new), company_id=company_id,
    )
    if not result.success:
        code = result.errors[0].code if result.errors else "unknown"
        if code == "not_found":
            raise HTTPException(status_code=404, detail="Trip not found")
        status = 500 if code in ("internal_error",) else 400
        raise HTTPException(status_code=status, detail=result.errors[0].message)

    updated = service.get_by_id(trip_id, company_id=company_id)
    conflicts: list[dict[str, Any]] = []
    if updated:
        try:
            from services.conflict_service import TripConflictService
            conflicts = TripConflictService(db).check_conflicts(
                updated, company_id=company_id,
            ) or []
        except Exception as exc:
            logger.warning(
                "dispatch: conflict check failed after trip #%d transition: %s",
                trip_id, exc,
            )

    return {"trip": updated, "conflicts": conflicts}


# ── 4. Trip detail panel ──────────────────────────────────────────────────


@router.get("/trips/{trip_id}/detail")
def get_trip_detail(
    trip_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: TripService = Depends(get_trip_service),
    db: DatabaseManager = Depends(get_db),
):
    """Return trip detail panel data: trip + client summary + alerts + documents.

    Also resolves the trip's route stops from ``route_history_v2.stops_json``
    (via ``trips.route_history_v2_id``) and returns them parsed under
    ``stops`` (``null`` when the trip has no route / stops).  Composes
    existing repositories/services only — no business logic is duplicated here.
    """
    company_id = current_user.get("company_id", 0)
    trip = service.get_by_id(trip_id, company_id=company_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # ── Client summary ────────────────────────────────────────────────
    client_summary: Optional[dict[str, Any]] = None
    if trip.get("client_id"):
        client = ClientRepository(db).get_by_id(
            int(trip["client_id"]), company_id=company_id,
        )
        if client:
            client_summary = {
                "id": client.get("id"),
                "name": client.get("name", ""),
                "email": client.get("email", ""),
                "phone": client.get("phone", ""),
                "vat_number": client.get("vat_number", ""),
                "address": client.get("address", ""),
                "country": client.get("country", ""),
                "payment_terms_days": client.get("payment_terms_days"),
                "is_active": client.get("is_active"),
            }

    # ── Alerts (reuses the same AlertManager as /alerts) ──────────────
    alerts = _get_trip_alerts(db, trip_id)

    # ── Linked documents (from trips.documents_attached) ──────────────
    document_ids = TripRepository(db).get_documents_attached(trip_id) or []

    # ── Route stops (route_history_v2.stops_json) ─────────────────────
    # Route data lives in ``route_history_v2`` (linked via
    # ``trips.route_history_v2_id``); ``stops_json`` is read through the
    # same repository the local path uses (``TripService.get_route_stops_json``
    # → ``RouteRepository.get_stops_json``).  The JSON is parsed here so the
    # response carries the stop list itself; missing / unparseable / absent
    # routes yield ``null``.
    stops: Optional[list] = None
    route_id = trip.get("route_history_v2_id")
    if route_id:
        try:
            route_repo = getattr(service, "_route_repo", None)
            if route_repo is None:
                from repositories.route_repository import RouteRepository
                route_repo = RouteRepository(db)
            stops_json = route_repo.get_stops_json(int(route_id))
            if stops_json:
                parsed = json.loads(stops_json)
                if isinstance(parsed, list):
                    stops = parsed
        except Exception as exc:
            logger.warning(
                "dispatch: failed to load route stops for trip #%d: %s",
                trip_id, exc,
            )
            stops = None

    return {
        "trip": trip,
        "client": client_summary,
        "alerts": {"count": len(alerts), "items": alerts},
        "documents": {"count": len(document_ids), "document_ids": document_ids},
        "stops": stops,
    }


# ── 5. Trip assignment (truck / driver) ────────────────────────────────────


class TripAssignmentRequest(BaseModel):
    """Request body for assigning a truck and/or driver to a trip.

    ``truck_id``/``driver_id`` may be ``null`` to **clear** the field; a key
    that is absent from the payload leaves the field untouched (so assigning
    only a truck never clears an existing driver).
    """

    truck_id: Optional[int] = None
    driver_id: Optional[int] = None


class BulkAssignmentRequest(BaseModel):
    """Request body for bulk truck/driver assignment across trips.

    Same semantics as :class:`TripAssignmentRequest` (null clears, absent key
    leaves untouched), applied best-effort to every ``trip_ids`` entry.
    """

    trip_ids: list[int] = []
    truck_id: Optional[int] = None
    driver_id: Optional[int] = None


def _build_assignment_update(
    db: DatabaseManager,
    data: TripAssignmentRequest | BulkAssignmentRequest,
    provided: set[str],
    company_id: int,
) -> dict[str, Any]:
    """Resolve the ``TripUpdate`` fields for an assignment payload.

    Validates referenced truck/driver existence (company-scoped, mirrors
    ``TripService._validate_external_refs``) and derives the display fields
    (``truck_plate`` / ``driver_name``) from the referenced rows exactly like
    the local board's ``_assign_truck_to_trip`` / ``_assign_driver_to_trip``.
    Raises ``HTTPException(400)`` for a referenced-but-missing entity.
    """
    update_fields: dict[str, Any] = {}
    if "truck_id" in provided:
        if data.truck_id is not None:
            truck = FleetRepository(db).get_by_id(data.truck_id, company_id=company_id)
            if not truck:
                raise HTTPException(
                    status_code=400,
                    detail=f"Truck with id {data.truck_id} not found",
                )
            update_fields["truck_id"] = data.truck_id
            update_fields["truck_plate"] = truck.get("plate_number", "") or ""
        else:
            update_fields["truck_id"] = None
            update_fields["truck_plate"] = ""
    if "driver_id" in provided:
        if data.driver_id is not None:
            driver = DriverRepository(db).get_by_id(data.driver_id, company_id=company_id)
            if not driver:
                raise HTTPException(
                    status_code=400,
                    detail=f"Driver with id {data.driver_id} not found",
                )
            update_fields["driver_id"] = data.driver_id
            update_fields["driver_name"] = driver.get("name", "") or ""
        else:
            update_fields["driver_id"] = None
            update_fields["driver_name"] = ""
    return update_fields


def _record_driver_truck_pairing(db: DatabaseManager, driver_id: int, truck_id: int) -> None:
    """Record a driver↔truck pairing via ``DriverTruckService`` (best-effort).

    Mirrors the local board's paired-assignment flow (``_assign_both_to_trip``),
    which also persists the pairing into ``driver_truck_assignment``.  Failures
    are logged, never raised — the trip update is already committed.
    """
    try:
        from services.driver_truck_service import DriverTruckService
        DriverTruckService(db)._do_assign_driver_to_truck(driver_id, truck_id)
    except Exception as exc:
        logger.warning(
            "dispatch: failed to record driver %d ↔ truck %d pairing: %s",
            driver_id, truck_id, exc,
        )


@router.patch("/trips/{trip_id}/assignment")
def update_trip_assignment(
    trip_id: int,
    data: TripAssignmentRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: TripService = Depends(get_trip_service),
    db: DatabaseManager = Depends(get_db),
):
    """Assign a truck and/or driver to a trip (company-scoped).

    Mirrors the local board's ``_assign_truck_to_trip`` / ``_assign_driver_to_trip``:
    ``TripService.update`` (validated + company-scoped) applies the change, and a
    driver↔truck pairing is recorded via ``DriverTruckService`` when both fields
    are present.  ``truck_id``/``driver_id`` may be ``null`` to clear the field.

    Returns ``{"trip": {...}}`` (the updated trip row) on success.
    """
    company_id = current_user.get("company_id", 0)
    trip = service.get_by_id(trip_id, company_id=company_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    provided = data.model_fields_set
    if not provided:
        raise HTTPException(
            status_code=400,
            detail="No assignment fields provided — send truck_id and/or driver_id.",
        )

    update_fields = _build_assignment_update(db, data, provided, company_id)
    result = service.update(
        trip_id, TripUpdate(**update_fields), company_id=company_id,
    )
    if not result.success:
        code = result.errors[0].code if result.errors else "unknown"
        if code == "not_found":
            raise HTTPException(status_code=404, detail="Trip not found")
        status = 500 if code in ("internal_error",) else 400
        raise HTTPException(status_code=status, detail=result.errors[0].message)

    if data.driver_id is not None and data.truck_id is not None:
        _record_driver_truck_pairing(db, data.driver_id, data.truck_id)

    updated = service.get_by_id(trip_id, company_id=company_id)
    return {"trip": updated}


@router.post("/assignments/bulk")
def bulk_update_assignments(
    data: BulkAssignmentRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: TripService = Depends(get_trip_service),
    db: DatabaseManager = Depends(get_db),
):
    """Apply a truck/driver assignment to multiple trips (best-effort).

    Each trip goes through the same company-scoped ``TripService.update`` path
    as :func:`update_trip_assignment`.  Returns::

        {"updated": [trip_id, ...], "failed": [{"trip_id": ..., "error": ...}, ...]}

    so callers can report partial success per trip.
    """
    company_id = current_user.get("company_id", 0)
    provided = data.model_fields_set
    if not provided.intersection({"truck_id", "driver_id"}):
        raise HTTPException(
            status_code=400,
            detail="No assignment fields provided — send truck_id and/or driver_id.",
        )

    # Resolve/validate the assignment fields once — they apply to every trip.
    update_fields = _build_assignment_update(db, data, provided, company_id)

    updated: list[int] = []
    failed: list[dict[str, Any]] = []
    for trip_id in data.trip_ids or []:
        try:
            trip = service.get_by_id(trip_id, company_id=company_id)
            if not trip:
                failed.append({"trip_id": trip_id, "error": "Trip not found"})
                continue
            result = service.update(
                trip_id, TripUpdate(**update_fields), company_id=company_id,
            )
            if not result.success:
                msg = result.errors[0].message if result.errors else "Update failed"
                failed.append({"trip_id": trip_id, "error": msg})
                continue
            updated.append(trip_id)
        except HTTPException as exc:
            failed.append({"trip_id": trip_id, "error": exc.detail})
        except Exception as exc:
            logger.warning(
                "dispatch: bulk assignment failed for trip #%s: %s", trip_id, exc,
            )
            failed.append({"trip_id": trip_id, "error": str(exc)})

    if data.driver_id is not None and data.truck_id is not None:
        _record_driver_truck_pairing(db, data.driver_id, data.truck_id)

    return {"updated": updated, "failed": failed}


# ── 6. Delay evaluation / delay alerts / next-available slot ─────────────
# These endpoints give remote mode the delay indicators, delay alerts and
# next-available-slot queries the local board already has.  Each composes the
# EXACT local logic: ``DispatchService.evaluate_trip_delay`` /
# ``create_delay_alert`` / ``resolve_delay_alert`` and
# ``TripConflictService.get_next_available_slot`` /
# ``get_next_available_slot_for_driver`` — nothing is re-invented here.


class DelayAlertRequest(BaseModel):
    """Request body for creating or resolving a trip delay alert.

    ``resolved=False`` (default) creates a delay alert mirroring the local
    ``DispatchService.create_delay_alert`` (unresolved duplicates are
    skipped); ``resolved=True`` resolves the trip's active delay alert
    mirroring ``DispatchService.resolve_delay_alert``.  ``minutes_overdue`` is
    optional — the server computes the trip's delay with the same rules the
    board uses unless the caller supplies it (the local board always evaluates
    before creating).
    """

    resolved: bool = False
    notes: str = ""
    minutes_overdue: Optional[int] = None


def _trip_card_data(trip: dict[str, Any], trip_id: int) -> dict[str, Any]:
    """Build the card-style dict the local delay rules read (mirrors ``_build_card_data``)."""
    return {
        "trip_id_num": trip_id,
        "status": trip.get("status", "Planned"),
        "departure_date": trip.get("start_date", "") or "",
        "eta": trip.get("end_date", "") or "",
        "truck_plate": trip.get("truck_number", "") or "",
        "driver_name": trip.get("driver_name", "") or "",
    }


def _evaluate_trip_delay(trip: dict[str, Any], trip_id: int) -> tuple[bool, int]:
    """Evaluate a trip row's delay using the EXACT local board rules.

    Delegates to ``DispatchService.evaluate_trip_delay``
    (``services/dispatch_service/dispatch_service.py``) — the same pure
    function the desktop board calls.  In Transit trips are delayed once past
    their ETA, Loading once past departure + 2h, Planned once past departure
    + 24h; every other status is never delayed.
    """
    from services.dispatch_service.dispatch_service import DispatchService
    return DispatchService.evaluate_trip_delay(_trip_card_data(trip, trip_id))


def _delay_threshold_hours(status: str) -> float:
    """Grace period (hours) the local rules apply per status group."""
    if status in ("Loading", "Preparing", "Pickup"):
        return 2.0
    if status in ("Planned", "Scheduled", "Pending"):
        return 24.0
    return 0.0


def _delay_reason(status: str, delay_hours: float) -> str:
    """Human-readable reason a trip is delayed (``None`` when on time)."""
    if status in ("In Transit", "InTransit", "Active", "InProgress"):
        return f"Trip is {delay_hours:.1f}h past its ETA"
    if status in ("Loading", "Preparing", "Pickup"):
        return f"Trip is {delay_hours:.1f}h past the loading deadline (departure + 2h)"
    if status in ("Planned", "Scheduled", "Pending"):
        return f"Trip departure was {delay_hours:.1f}h ago (24h threshold)"
    return f"Trip is {delay_hours:.1f}h overdue"


@router.get("/trips/{trip_id}/delay")
def evaluate_trip_delay(
    trip_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: TripService = Depends(get_trip_service),
):
    """Evaluate whether a trip is delayed (mirrors the local board rules).

    Uses the exact local delay logic (``DispatchService.evaluate_trip_delay``
    in ``services/dispatch_service/dispatch_service.py``).  Returns::

        {"delayed": bool, "delay_hours": float, "threshold_hours": float,
         "reason": str | null}

    ``delay_hours`` is the time past the threshold (``0.0`` when not delayed);
    ``threshold_hours`` is the status's grace period (``0`` / ``2`` / ``24``).
    404 when the trip does not exist.
    """
    company_id = current_user.get("company_id", 0)
    trip = service.get_by_id(trip_id, company_id=company_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    delayed, minutes = _evaluate_trip_delay(trip, trip_id)
    delay_hours = round(minutes / 60.0, 2) if delayed else 0.0
    return {
        "delayed": delayed,
        "delay_hours": delay_hours,
        "threshold_hours": _delay_threshold_hours(trip.get("status", "")),
        "reason": _delay_reason(trip.get("status", ""), delay_hours) if delayed else None,
    }


def _alert_to_dict(alert: Any) -> Optional[dict[str, Any]]:
    """Serialize an ``AlertManager.Alert`` (``to_dict``) for the API response."""
    if alert is None:
        return None
    try:
        return alert.to_dict()
    except Exception:
        logger.warning("dispatch: failed to serialize alert %r", alert, exc_info=True)
        return None


def _create_delay_alert(
    db: DatabaseManager, trip: dict[str, Any], trip_id: int,
    minutes_overdue: int, notes: str = "",
) -> Any:
    """Create a delay alert mirroring ``DispatchService.create_delay_alert``.

    Skips (returns ``None``) when an unresolved ``trip_delay`` alert already
    exists for the trip — the local duplicate check.
    """
    from services.operations.alert_manager import AlertManager, AlertType, Severity
    manager = AlertManager(db)
    existing = manager.get_alerts(
        alert_type=AlertType.TRIP_DELAY, resolved=False, limit=1000,
    )
    for alert in existing:
        if alert.trip_id == str(trip_id):
            logger.info(
                "dispatch: duplicate delay alert skipped for trip #%d", trip_id,
            )
            return None

    severity = Severity.CRITICAL if minutes_overdue > 120 else Severity.WARNING
    truck_plate = trip.get("truck_number", "") or ""
    driver_name = trip.get("driver_name", "") or ""
    metadata: dict[str, Any] = {
        "minutes_overdue": minutes_overdue,
        "status": trip.get("status", ""),
    }
    if notes:
        metadata["notes"] = notes
    return manager.create_alert(
        alert_type=AlertType.TRIP_DELAY,
        severity=severity,
        title=f"Trip #{trip_id} — Delay",
        message=(
            f"Trip #{trip_id} is {minutes_overdue} minutes overdue"
            f" (truck: {truck_plate or 'N/A'}, driver: {driver_name or 'N/A'})"
        ),
        truck_id=truck_plate if truck_plate else None,
        trip_id=str(trip_id),
        metadata=metadata,
    )


def _resolve_delay_alert(db: DatabaseManager, trip_id: int) -> Any:
    """Resolve the trip's active delay alert mirroring ``DispatchService.resolve_delay_alert``."""
    from services.operations.alert_manager import AlertManager, AlertType
    manager = AlertManager(db)
    existing = manager.get_alerts(
        alert_type=AlertType.TRIP_DELAY, resolved=False, limit=1000,
    )
    for alert in existing:
        if alert.trip_id == str(trip_id):
            manager.resolve_alert(alert.id)
            logger.info("dispatch: resolved delay alert for trip #%d", trip_id)
            return alert
    return None


@router.post("/trips/{trip_id}/delay-alerts")
def create_or_resolve_delay_alert(
    trip_id: int,
    data: DelayAlertRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: TripService = Depends(get_trip_service),
    db: DatabaseManager = Depends(get_db),
):
    """Create or resolve a trip's delay alert via the AlertManager.

    Mirrors the local ``DispatchService.create_delay_alert`` /
    ``resolve_delay_alert`` (``services/dispatch_service/dispatch_service.py``):

    * ``resolved=False`` (default): evaluates the trip's delay with the same
      rules as ``GET /trips/{id}/delay`` and creates a ``trip_delay`` alert
      (severity CRITICAL when more than 2h overdue).  A trip that is not
      currently delayed — or one that already has an unresolved delay alert —
      returns ``{"alert": None}`` (the local duplicate skip).
    * ``resolved=True``: resolves the trip's active delay alert.

    Returns ``{"alert": {...}}`` with the created/resolved alert, or
    ``{"alert": None}`` when nothing was created/resolved.  404 for an unknown
    trip.
    """
    company_id = current_user.get("company_id", 0)
    trip = service.get_by_id(trip_id, company_id=company_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if data.resolved:
        alert = _resolve_delay_alert(db, trip_id)
        return {"alert": _alert_to_dict(alert)}

    delayed, minutes = _evaluate_trip_delay(trip, trip_id)
    if not delayed and data.minutes_overdue is None:
        return {"alert": None}
    minutes_overdue = (
        data.minutes_overdue if data.minutes_overdue is not None else minutes
    )
    alert = _create_delay_alert(db, trip, trip_id, minutes_overdue, notes=data.notes)
    return {"alert": _alert_to_dict(alert)}


def _next_available_slot(
    slot_service: Any, trips: list[dict[str, Any]], baseline: datetime,
) -> Optional[datetime]:
    """Compute the latest ETA among *trips* past *baseline*.

    Mirrors the loop in ``TripConflictService.get_next_available_slot`` /
    ``get_next_available_slot_for_driver`` (``services/conflict_service.py``)
    with ``start_at`` substituted for ``datetime.now()`` as the baseline.
    Returns ``None`` when no active trip keeps the resource busy at/beyond
    *baseline* (i.e. the resource is free at the desired start).
    """
    latest_eta = baseline
    for trip in trips or []:
        dep = slot_service._get_departure(trip)
        if not dep:
            continue
        eta = slot_service._estimate_eta(trip, dep)
        if eta > latest_eta:
            latest_eta = eta
    return latest_eta if latest_eta > baseline else None


@router.get("/slots/next")
def get_next_available_slot(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    driver_id: Optional[int] = Query(
        None, ge=1, description="Driver id to check availability for",
    ),
    truck_id: Optional[int] = Query(
        None, ge=1, description="Truck id to check availability for",
    ),
    start_at: str = Query(
        "", description="Desired start time (ISO 8601); defaults to now",
    ),
    db: DatabaseManager = Depends(get_db),
):
    """Return the next available start time for a driver and/or truck.

    Mirrors ``TripConflictService.get_next_available_slot`` /
    ``get_next_available_slot_for_driver`` (``services/conflict_service.py``):
    the latest ETA among the resource's active trips is the next available
    slot; a resource whose ETAs are all before *start_at* is free at
    *start_at* (``start_at: null``).  When both ``driver_id`` and ``truck_id``
    are given, the trip can only start once BOTH are free, so the later of the
    two slots is returned.

    Returns ``{"start_at": iso | null, "reason": str | null}``.  400 when
    neither ``driver_id`` nor ``truck_id`` is provided.
    """
    if not driver_id and not truck_id:
        raise HTTPException(
            status_code=400,
            detail="Provide driver_id and/or truck_id to compute the next available slot.",
        )

    try:
        baseline = datetime.fromisoformat(start_at) if start_at else datetime.now()
    except ValueError:
        raise HTTPException(
            status_code=422, detail="Invalid start_at — expected ISO 8601.",
        )

    from services.conflict_service import TripConflictService
    slot_service = TripConflictService(db)

    slots: list[tuple[datetime, str]] = []
    if truck_id:
        trips = slot_service._trip_repo.get_active_for_truck(truck_id=truck_id)
        slot = _next_available_slot(slot_service, trips, baseline)
        if slot is not None:
            slots.append((slot, f"truck #{truck_id} busy until {slot.isoformat()}"))
    if driver_id:
        trips = slot_service._trip_repo.get_active_for_driver(driver_id)
        slot = _next_available_slot(slot_service, trips, baseline)
        if slot is not None:
            slots.append((slot, f"driver #{driver_id} busy until {slot.isoformat()}"))

    if not slots:
        return {"start_at": None, "reason": None}

    latest = max(slot for slot, _ in slots)
    reasons = [reason for slot, reason in slots if slot == latest]
    return {"start_at": latest.isoformat(), "reason": "; ".join(reasons)}
