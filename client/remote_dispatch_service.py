"""API-backed dispatch service wrapper for remote-only client mode.

Mirrors the board-facing surface of ``services.dispatch_service.DispatchService``
and the service calls made by ``ui/views/dispatch_board/`` (``board_actions.py``,
``board_state.py``) so the dispatch board can run against the FastAPI backend
instead of a local database.

Backend contracts (``backend/api/v1/dispatch.py`` + existing trips router):

  - GET   /dispatch/board                    → columns + trips (board cards)
  - GET   /dispatch/driver-hours             → weekly driving hours per driver
  - PATCH /dispatch/trips/{trip_id}/status   → validated status transition + conflicts
  - GET   /dispatch/trips/{trip_id}/detail   → trip + client + alerts + documents
  - PATCH /dispatch/trips/{trip_id}/assignment → assign/clear a trip's truck/driver
  - POST  /dispatch/assignments/bulk         → apply a truck/driver assignment to many trips
  - POST  /trips/conflicts/check             → resource conflict check (existing)
  - GET   /dispatch/trips/{trip_id}/delay    → delay evaluation (same rules as local)
  - POST  /dispatch/trips/{trip_id}/delay-alerts → create/resolve a trip delay alert
  - GET   /dispatch/slots/next               → next available slot for driver/truck

Methods that used to be stubbed (delay evaluation / delay-alert
creation/resolution, next-available-slot queries) now call the endpoints
above and degrade gracefully (``None``/``False``/``(False, 0)``) on API
failure.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("remote_dispatch")

# Column order mirrors ``COLUMN_KEYS`` in the backend dispatch router.
_COLUMN_KEYS = ["Planned", "Loading", "In Transit", "Delivered", "Cancelled"]

# Sentinel distinguishing "field omitted" (leave untouched) from an explicit
# ``None`` (clear the field).  The backend PATCH/POST assignment endpoints
# treat an absent key as untouched and a null value as a clear.
_UNSET = object()


class _DelayEvaluation(dict):
    """Result of :meth:`RemoteDispatchService.evaluate_trip_delay`.

    The backend returns ``{"delayed", "delay_hours", "threshold_hours",
    "reason"}``.  Local callers unpack the result the way they unpack the
    local ``DispatchService`` tuple
    (``is_delayed, minutes = evaluate_trip_delay(...)``), so this dict also
    iterates as ``(delayed, minutes_overdue)`` — both access styles work.
    """

    def __iter__(self):
        return iter((self.get("delayed", False), self.get("minutes_overdue", 0)))


class RemoteDispatchService:
    """API-backed substitute for the dispatch board's service layer."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    @staticmethod
    def _query_params(**kwargs: Any) -> dict:
        """Strip ``None``/empty-string values from query params.

        Mirrors ``ApiClient._clean_params`` without depending on the client
        instance, so the wrapper keeps a predictable surface for mocks.
        """
        return {k: v for k, v in kwargs.items() if v is not None and v != ""}

    # ── Board data ─────────────────────────────────────────────────────────

    def get_board_data(
        self, delivered_window_days: int = 30, limit: int = 200,
    ) -> dict:
        """Return dispatch-board data from ``GET /dispatch/board``.

        Shape: ``{"columns": {column: count}, "trips": [card, ...]}`` — each
        card already carries a ``column`` key (the backend builds the card
        shape including route origin/destination and the delivered/cancelled
        cutoff window).

        The API client returns the JSON body directly (no ``{"data": ...}``
        wrapper); a wrapper is unwrapped defensively if one ever appears.
        On failure an empty board ``{"columns": {}, "trips": []}`` is returned
        so the view degrades gracefully.
        """
        try:
            resp = self._api._get(
                "/api/v1/dispatch/board",
                params=self._query_params(
                    delivered_window_days=delivered_window_days,
                    limit=limit,
                ),
            )
            if isinstance(resp, dict) and isinstance(resp.get("data"), dict):
                resp = resp["data"]
            if not isinstance(resp, dict):
                logger.warning(
                    "dispatch: unexpected board response shape: %r", resp,
                )
                return {"columns": {}, "trips": []}
            return {
                "columns": resp.get("columns", {}) or {},
                "trips": resp.get("trips", []) or [],
            }
        except Exception:
            logger.warning("dispatch: get_board_data failed", exc_info=True)
            return {"columns": {}, "trips": []}

    def get_dispatch_board_data(self, **kwargs: Any) -> dict:
        """Alias for :meth:`get_board_data` (local ``DispatchService`` name).

        ``filters``-style kwargs from the local service are not supported by
        the backend endpoint; only ``delivered_window_days``/``limit`` pass
        through (ignored kwargs are accepted for interface parity).
        """
        delivered_window_days = kwargs.get("delivered_window_days", 30)
        limit = kwargs.get("limit", 200)
        return self.get_board_data(
            delivered_window_days=delivered_window_days, limit=limit,
        )

    # ── Driver hours vs tacho limits ───────────────────────────────────────

    def get_driver_hours(self, week_start: Optional[str] = None) -> dict:
        """Return weekly driving hours from ``GET /dispatch/driver-hours``.

        ``week_start`` is an ISO date (YYYY-MM-DD) starting the 7-day window;
        when omitted the backend defaults to the last 7 days.

        Returns ``{"week_start": ..., "week_end": ..., "drivers": [...]}``;
        each driver entry is ``{driver_id, driver_name, week_hours,
        weekly_limit_hours, violations: [...]}``.  Empty values on failure.
        """
        try:
            resp = self._api._get(
                "/api/v1/dispatch/driver-hours",
                params=self._query_params(week_start=week_start),
            )
            if not isinstance(resp, dict):
                logger.warning(
                    "dispatch: unexpected driver-hours response shape: %r", resp,
                )
                return {"week_start": "", "week_end": "", "drivers": []}
            return {
                "week_start": resp.get("week_start", ""),
                "week_end": resp.get("week_end", ""),
                "drivers": resp.get("drivers", []) or [],
            }
        except Exception:
            logger.warning("dispatch: get_driver_hours failed", exc_info=True)
            return {"week_start": "", "week_end": "", "drivers": []}

    # ── Status transitions (validated + conflict-checked) ──────────────────

    def update_trip_status(self, trip_id: int, status: str) -> dict:
        """Transition a trip via ``PATCH /dispatch/trips/{id}/status``.

        Returns ``{"trip": {...}, "conflicts": [...]}``.  The backend
        validates the transition (400 on illegal transitions) and runs the
        conflict check after the mutation.  On failure (invalid transition,
        missing trip, network error) ``trip`` is ``None`` and ``conflicts``
        empty — the caller can distinguish failure by ``result["trip"]``.
        """
        try:
            resp = self._api._patch(
                f"/api/v1/dispatch/trips/{trip_id}/status",
                json_data={"status": status},
            )
            if not isinstance(resp, dict):
                return {"trip": None, "conflicts": []}
            return {
                "trip": resp.get("trip"),
                "conflicts": resp.get("conflicts", []) or [],
            }
        except Exception:
            logger.warning(
                "dispatch: update_trip_status(%s, %r) failed",
                trip_id, status, exc_info=True,
            )
            return {"trip": None, "conflicts": []}

    def transition_status(self, trip_id: int, new_status: str) -> dict:
        """Alias for :meth:`update_trip_status` (local ``DispatchService`` name)."""
        return self.update_trip_status(trip_id, new_status)

    def bulk_update_status(self, trip_ids, status: str) -> dict:
        """Bulk status change composed from the single-trip PATCH endpoint.

        No dedicated bulk endpoint exists, so each trip is transitioned via
        ``PATCH /dispatch/trips/{id}/status`` (existing endpoint).

        Returns ``{"updated": n, "failed": m}``.
        """
        updated = 0
        failed = 0
        for trip_id in trip_ids or []:
            result = self.update_trip_status(trip_id, status)
            if result.get("trip") is not None:
                updated += 1
            else:
                failed += 1
        return {"updated": updated, "failed": failed}

    # ── Trip assignment (truck / driver) ──────────────────────────────────

    @staticmethod
    def _assignment_payload(truck_id: Any, driver_id: Any) -> dict:
        """Build an assignment payload from (possibly sentinel) field values.

        Only fields the caller explicitly provided are included.  An explicit
        ``None`` is sent as a JSON ``null`` (clear the field); an omitted
        field is skipped so the backend leaves it untouched.
        """
        payload: dict[str, Any] = {}
        if truck_id is not _UNSET:
            payload["truck_id"] = truck_id
        if driver_id is not _UNSET:
            payload["driver_id"] = driver_id
        return payload

    @staticmethod
    def _log_value(value: Any) -> Any:
        """Render a sentinel default as ``None`` for log messages."""
        return None if value is _UNSET else value

    def assign_trip(self, trip_id: int, truck_id: Any = _UNSET, driver_id: Any = _UNSET) -> dict:
        """Assign a truck and/or driver to a trip via
        ``PATCH /dispatch/trips/{id}/assignment``.

        Args:
            trip_id: The trip to update.
            truck_id: Truck id to assign, ``None`` to clear the truck, or
                omit to leave the truck untouched.
            driver_id: Driver id to assign, ``None`` to clear the driver, or
                omit to leave the driver untouched.

        Returns ``{"trip": {...}}``.  ``trip`` is ``None`` when the
        assignment fails (missing trip, unknown truck/driver, network error)
        — callers distinguish success by ``result["trip"]``, mirroring
        :meth:`update_trip_status`.
        """
        try:
            resp = self._api._patch(
                f"/api/v1/dispatch/trips/{trip_id}/assignment",
                json_data=self._assignment_payload(truck_id, driver_id),
            )
            if not isinstance(resp, dict):
                return {"trip": None}
            return {"trip": resp.get("trip")}
        except Exception:
            logger.warning(
                "dispatch: assign_trip(%s, truck_id=%r, driver_id=%r) failed",
                trip_id,
                self._log_value(truck_id),
                self._log_value(driver_id),
                exc_info=True,
            )
            return {"trip": None}

    def bulk_assign(self, trip_ids, truck_id: Any = _UNSET, driver_id: Any = _UNSET) -> dict:
        """Apply a truck/driver assignment to many trips via
        ``POST /dispatch/assignments/bulk``.

        Args:
            trip_ids: Iterable of trip ids to update.
            truck_id: Truck id to assign, ``None`` to clear the truck, or
                omit to leave the truck untouched.
            driver_id: Driver id to assign, ``None`` to clear the driver, or
                omit to leave the driver untouched.

        The backend updates each trip independently (best-effort) and reports
        partial success.  Returns ``{"updated": [...trip ids],
        "failed": [{"trip_id", "error"}, ...]}`` — empty lists on failure.
        """
        payload = self._assignment_payload(truck_id, driver_id)
        if not payload:
            logger.warning(
                "dispatch: bulk_assign called with no assignment fields",
            )
            return {"updated": [], "failed": []}
        try:
            resp = self._api._post(
                "/api/v1/dispatch/assignments/bulk",
                json_data={"trip_ids": list(trip_ids or []), **payload},
            )
            if not isinstance(resp, dict):
                return {"updated": [], "failed": []}
            return {
                "updated": resp.get("updated", []) or [],
                "failed": resp.get("failed", []) or [],
            }
        except Exception:
            logger.warning(
                "dispatch: bulk_assign(trip_ids=%r, truck_id=%r, driver_id=%r) failed",
                trip_ids,
                self._log_value(truck_id),
                self._log_value(driver_id),
                exc_info=True,
            )
            return {"updated": [], "failed": []}

    # ── Trip detail panel ─────────────────────────────────────────────────

    def get_trip_detail(self, trip_id: int) -> Optional[dict]:
        """Return trip detail panel data from ``GET /dispatch/trips/{id}/detail``.

        Shape: ``{"trip": {...}, "client": {...}, "alerts": {"count", "items"},
        "documents": {"count", "document_ids"}}``.

        Returns ``None`` when the trip is missing (404) or the API raises.
        """
        try:
            return self._api._get(f"/api/v1/dispatch/trips/{trip_id}/detail")
        except Exception:
            logger.warning(
                "dispatch: get_trip_detail(%s) failed", trip_id, exc_info=True,
            )
            return None

    # ── Conflict check (existing trips endpoint) ───────────────────────────

    def check_conflicts(self, trip_data: dict) -> list:
        """Run the resource conflict check via ``POST /trips/conflicts/check``.

        Mirrors ``TripConflictService.check_conflicts`` as used by the board
        assignment dropdowns.  Returns the conflict list (``trip_id``,
        ``overlap_description``, ...) — empty when there are no conflicts or
        the API raises.
        """
        try:
            resp = self._api._post(
                "/api/v1/trips/conflicts/check", json_data=trip_data,
            )
            if not isinstance(resp, dict):
                return []
            return resp.get("conflicts", []) or []
        except Exception:
            logger.warning("dispatch: check_conflicts failed", exc_info=True)
            return []

    # ── Delay evaluation / alerts ────────────────────────────────────────
    # Real calls to ``GET /dispatch/trips/{id}/delay`` and
    # ``POST /dispatch/trips/{id}/delay-alerts``.  Each method keeps the local
    # ``DispatchService`` calling convention (card-data dict accepted wherever
    # the board passes one) so existing call sites work unchanged.

    @staticmethod
    def _resolve_trip_id(trip_data_or_id: Any) -> Optional[int]:
        """Extract a numeric trip id from a card-data dict or an int.

        The local ``DispatchService`` interface is called with a card-data
        dict (``trip_id_num`` / ``trip_id``); remote callers may pass the
        numeric id directly.
        """
        if isinstance(trip_data_or_id, dict):
            value = trip_data_or_id.get(
                "trip_id_num", trip_data_or_id.get("trip_id"),
            )
        else:
            value = trip_data_or_id
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def evaluate_trip_delay(
        self, trip_data_or_id: Any, now: Optional[datetime] = None,
    ) -> Any:
        """Evaluate a trip's delay via ``GET /dispatch/trips/{id}/delay``.

        Accepts either a card-data dict (the local ``DispatchService``
        calling convention) or a numeric trip id.  Returns a dict-like
        ``{"delayed", "delay_hours", "threshold_hours", "reason"}`` result
        (also unpackable as ``(is_delayed, minutes_overdue)`` like the local
        ``DispatchService``), or ``(False, 0)`` on API failure so the board's
        delay indicators degrade gracefully.

        ``now`` is accepted for interface parity with the local service and
        ignored — the backend evaluates at server time.
        """
        trip_id = self._resolve_trip_id(trip_data_or_id)
        if trip_id is None:
            return False, 0
        try:
            resp = self._api._get(f"/api/v1/dispatch/trips/{trip_id}/delay")
            if not isinstance(resp, dict):
                logger.warning(
                    "dispatch: unexpected delay response for trip %s: %r",
                    trip_id, resp,
                )
                return False, 0
            delayed = bool(resp.get("delayed", False))
            delay_hours = float(resp.get("delay_hours") or 0.0)
            return _DelayEvaluation({
                "delayed": delayed,
                "delay_hours": delay_hours,
                "threshold_hours": resp.get("threshold_hours", 0.0),
                "reason": resp.get("reason"),
                "minutes_overdue": int(round(delay_hours * 60)),
            })
        except Exception:
            logger.warning(
                "dispatch: evaluate_trip_delay(%s) failed", trip_id, exc_info=True,
            )
            return False, 0

    def create_delay_alert(
        self, trip_data_or_id: Any, minutes_overdue: Optional[int] = None,
        resolved: bool = False, notes: str = "",
    ) -> Optional[dict]:
        """Create (or resolve) a trip's delay alert via
        ``POST /dispatch/trips/{id}/delay-alerts``.

        Mirrors ``DispatchService.create_delay_alert``: the board calls it
        with a card-data dict + ``minutes_overdue`` after a positive delay
        evaluation; remote callers may also pass the numeric trip id (and the
        optional ``resolved``/``notes`` fields mirror the endpoint contract).
        Returns the created alert dict, or ``None`` when skipped (duplicate
        alert, trip not delayed, or API error).
        """
        trip_id = self._resolve_trip_id(trip_data_or_id)
        if trip_id is None:
            return None
        payload: dict[str, Any] = {"resolved": resolved, "notes": notes}
        if minutes_overdue is not None:
            payload["minutes_overdue"] = minutes_overdue
        try:
            resp = self._api._post(
                f"/api/v1/dispatch/trips/{trip_id}/delay-alerts",
                json_data=payload,
            )
            if not isinstance(resp, dict):
                return None
            return resp.get("alert")
        except Exception:
            logger.warning(
                "dispatch: create_delay_alert(trip=%s, resolved=%r) failed",
                trip_id, resolved, exc_info=True,
            )
            return None

    def resolve_delay_alert(self, trip_id: int, notes: str = "") -> Any:
        """Resolve a trip's active delay alert via
        ``POST /dispatch/trips/{id}/delay-alerts`` (``resolved=True``).

        Mirrors ``DispatchService.resolve_delay_alert``.  Returns the resolved
        alert dict, ``None`` when no active delay alert exists, or ``False``
        on API error (graceful degradation).
        """
        try:
            resp = self._api._post(
                f"/api/v1/dispatch/trips/{trip_id}/delay-alerts",
                json_data={"resolved": True, "notes": notes},
            )
            if not isinstance(resp, dict):
                return False
            return resp.get("alert")
        except Exception:
            logger.warning(
                "dispatch: resolve_delay_alert(%s) failed", trip_id, exc_info=True,
            )
            return False

    # ── Next-available-slot queries ─────────────────────────────────────

    def get_next_available_slot(
        self, driver_id: Optional[int] = None, truck_id: Optional[int] = None,
        start_at: Optional[str] = None,
    ) -> Optional[dict]:
        """Return the next available start time via ``GET /dispatch/slots/next``.

        Shape: ``{"start_at": iso | None, "reason": str | None}`` —
        ``start_at`` is ``None`` when the resource is free at the desired
        start.  Returns ``None`` on API error.
        """
        try:
            resp = self._api._get(
                "/api/v1/dispatch/slots/next",
                params=self._query_params(
                    driver_id=driver_id,
                    truck_id=truck_id,
                    start_at=start_at,
                ),
            )
            if not isinstance(resp, dict):
                return None
            return {
                "start_at": resp.get("start_at"),
                "reason": resp.get("reason"),
            }
        except Exception:
            logger.warning("dispatch: get_next_available_slot failed", exc_info=True)
            return None

    def get_next_available_slot_for_driver(
        self, driver_id: int, start_at: Optional[str] = None,
    ) -> Optional[dict]:
        """Return the next available start time for a driver (same endpoint)."""
        return self.get_next_available_slot(driver_id=driver_id, start_at=start_at)
