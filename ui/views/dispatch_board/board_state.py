"""Dispatch board — data loading, filtering, search, caches, threading."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import QTimer

from services.i18n import t
from ui.design_tokens import BORDER_DEFAULT, COLOR_NEUTRAL_DEFAULT, INFO, SUCCESS, WARNING
from utils.dates import parse_date

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

STATUS_TO_COLUMN = {
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

COLUMN_DEFS = [
    ("Planned", "dispatch_board.col_planned", BORDER_DEFAULT),
    ("Loading", "dispatch_board.col_loading", WARNING),
    ("In Transit", "dispatch_board.col_in_transit", INFO),
    ("Delivered", "dispatch_board.col_delivered", SUCCESS),
    ("Cancelled", "dispatch_board.col_cancelled", COLOR_NEUTRAL_DEFAULT),
]

DELIVERED_DEFAULT_DAYS = 30
CANCELLED_MAX = 3
DELIVERED_INITIAL_MAX = 4


class BoardStateMixin:
    """Mixin providing data loading, filtering, search, and cache logic."""

    _delivered_show_all: bool = False

    # ── Data loading ──────────────────────────────────────────────────────────

    def _start_load(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._alert_counts.clear()
        if self.ops:
            pass  # Keep undo stack intact across refreshes
        for col in self._columns.values():
            col.show_loading()
        self._load_thread = threading.Thread(target=self._load_data_background, daemon=True)
        self._load_thread.start()

    def _load_data_background(self) -> None:
        try:
            self._preload_alerts()

            all_statuses = list(STATUS_TO_COLUMN.keys())
            all_trips = []
            if self._trip_service is not None:
                all_trips = self._trip_service.get_by_statuses(all_statuses)

            column_trips: dict[str, list[dict[str, Any]]] = {
                col: [] for col, _, _ in COLUMN_DEFS
            }

            cutoff = (datetime.now() - timedelta(days=self._delivered_days)).strftime("%Y-%m-%d")

            for trip in all_trips:
                raw_status = trip.get("status", "")
                column = STATUS_TO_COLUMN.get(raw_status)
                if not column:
                    continue

                if column in ("Delivered", "Cancelled"):
                    trip_date = trip.get("end_date", "") or trip.get("created_at", "")
                    trip_date = trip_date[:10] if len(trip_date) >= 10 else trip_date
                    if trip_date and trip_date < cutoff:
                        continue

                card_data = self._build_card_data(trip)
                column_trips[column].append(card_data)

            # ── Limit recent completed/cancelled trips ─────────────────────────
            # Cancelled: show only the last CANCELLED_MAX
            cancelled_trips = column_trips.get("Cancelled", [])
            cancelled_trips.sort(
                key=lambda t: t.get("eta", "") or t.get("departure_date", "") or "",
                reverse=True,
            )
            if len(cancelled_trips) > CANCELLED_MAX:
                column_trips["Cancelled"] = cancelled_trips[:CANCELLED_MAX]

            # Delivered: show only the last DELIVERED_INITIAL_MAX unless "show all"
            if not self._delivered_show_all:
                delivered_trips = column_trips.get("Delivered", [])
                delivered_trips.sort(
                    key=lambda t: t.get("eta", "") or t.get("departure_date", "") or "",
                    reverse=True,
                )
                if len(delivered_trips) > DELIVERED_INITIAL_MAX:
                    column_trips["Delivered"] = delivered_trips[:DELIVERED_INITIAL_MAX]

            self._dispatch(lambda ct=column_trips: self._populate_columns(ct))

        except Exception as e:
            logger.warning("Dispatch board data load failed: %s", e)
            self._dispatch(lambda err=str(e): self._show_error_all(err))

    def _preload_alerts(self) -> None:
        if not self.ops:
            return
        try:
            alerts = self.ops.get_active_alerts(limit=2000)
            for alert in alerts:
                trip_id = getattr(alert, "trip_id", None)
                if trip_id is not None:
                    try:
                        tid = int(trip_id)
                    except (ValueError, TypeError):
                        continue
                    self._alert_counts[tid] = self._alert_counts.get(tid, 0) + 1
        except Exception:
            logger.debug("Could not preload alerts", exc_info=True)

    def _build_card_data(self, trip: dict[str, Any]) -> dict[str, Any]:
        trip_id = trip.get("id", 0)
        status = trip.get("status", "Planned")
        truck_plate = trip.get("truck_number", "") or ""
        driver_name = trip.get("driver_name", "") or ""
        driver_id = trip.get("driver_id")
        truck_id = trip.get("truck_id")

        if driver_id and not driver_name:
            driver_name = self._resolve_driver_name(driver_id)

        origin, destination = self._resolve_route(trip)

        departure = trip.get("start_date", "") or ""
        eta = trip.get("end_date", "") or ""

        alerts_count = self._alert_counts.get(trip_id, 0)

        return {
            "trip_id": f"{t('dispatch_board.trip_id_prefix')}{trip_id}",
            "trip_id_num": trip_id,
            "status": status,
            "truck_plate": truck_plate,
            "truck_id": truck_id,
            "driver_name": driver_name,
            "driver_id": driver_id,
            "origin": origin,
            "destination": destination,
            "departure_date": departure,
            "eta": eta,
            "alerts_count": alerts_count,
        }

    def _resolve_driver_name(self, driver_id: int) -> str:
        if driver_id in self._driver_cache:
            cached = self._driver_cache[driver_id]
            return cached.get("name", "") if cached else ""
        try:
            driver = self._driver_repo.get_by_id(driver_id)
            self._driver_cache[driver_id] = driver
            return driver.get("name", "") if driver else ""
        except Exception:
            self._driver_cache[driver_id] = None
            return ""

    def _resolve_route(self, trip: dict[str, Any]):
        route_id = trip.get("route_history_v2_id")
        if not route_id:
            return "", ""

        route_key = str(route_id)
        if route_key in self._route_cache:
            cached = self._route_cache[route_key]
            if cached is None:
                return "", ""
            return cached.get("origin", ""), cached.get("destination", "")

        try:
            route = self._route_repo.get_by_id(int(route_id))
            if not route:
                self._route_cache[route_key] = None
                return "", ""

            origin, destination = self._extract_stops(route)
            result = {"origin": origin, "destination": destination}
            self._route_cache[route_key] = result
            return origin, destination
        except Exception:
            self._route_cache[route_key] = None
            return "", ""

    def _extract_stops(self, route: dict[str, Any]):
        summary = route.get("route_summary_json")
        if summary:
            try:
                summary_data = json.loads(summary) if isinstance(summary, str) else summary
                origin = summary_data.get("origin", "")
                dest = summary_data.get("destination", "")
                if origin or dest:
                    return origin, dest
            except (json.JSONDecodeError, TypeError):
                pass

        stops_raw = route.get("stops_json", "")
        if not stops_raw:
            return "", ""

        try:
            stops = json.loads(stops_raw) if isinstance(stops_raw, str) else stops_raw
        except (json.JSONDecodeError, TypeError):
            return "", ""

        if not stops or not isinstance(stops, list):
            return "", ""

        def _label(stop):
            if isinstance(stop, dict):
                return stop.get("address") or stop.get("label") or stop.get("value") or ""
            if isinstance(stop, (list, tuple)) and len(stop) >= 3:
                return str(stop[2]) if stop[2] else ""
            return ""

        origin = _label(stops[0]) if stops else ""
        destination = _label(stops[-1]) if stops else ""
        return origin, destination

    def _populate_columns(self, column_trips: dict[str, list[dict[str, Any]]]) -> None:
        self._loading = False
        all_cards = []
        for status_key, col in self._columns.items():
            trips = column_trips.get(status_key, [])
            col.set_trips(trips)
            all_cards.extend(trips)
        self._all_card_data = all_cards
        self._update_status_counts(column_trips)

        QTimer.singleShot(100, self._evaluate_all_delays)
        QTimer.singleShot(200, self._refresh_live_indicators)
        QTimer.singleShot(500, self._run_conflict_scan)
        QTimer.singleShot(600, self._refresh_side_panels)
        QTimer.singleShot(700, self._apply_filters)

    def _update_status_counts(self, column_trips: dict[str, list[dict[str, Any]]]) -> None:
        if not hasattr(self, "_status_cards") or self._status_cards is None:
            return
        for status_key, card in self._status_cards.items():
            count = len(column_trips.get(status_key, []))
            card.set_value(str(count))

    def _show_error_all(self, error_msg: str) -> None:
        self._loading = False
        for col in self._columns.values():
            col.show_error(error_msg)

    # ── Live position tracking ────────────────────────────────────────────────

    def _get_truck_position(self, truck_id, positions=None):
        if not truck_id:
            return None
        try:
            from services.fleet_tracking_service import fleet_tracking_service
            if positions is None:
                if not fleet_tracking_service.is_configured():
                    return None
                positions = fleet_tracking_service.get_positions()
            truck = self._fleet_repo.get_by_id(int(truck_id))
            if not truck:
                return None
            plate = (truck.get("plate_number") or "").upper()
            device_id = truck.get("tracking_device_id") or ""
            for pos in positions:
                if ((pos.name or "").upper() == plate
                        or pos.device_id == device_id):
                    return pos
        except Exception:
            pass
        return None

    def _refresh_live_indicators(self) -> None:
        if getattr(self, '_destroyed', False):
            return
        try:
            self.isVisible()
        except RuntimeError:
            return
        try:
            from services.fleet_tracking_service import fleet_tracking_service
            if not fleet_tracking_service.is_configured():
                return
            positions = fleet_tracking_service.get_positions()
            for col in self._columns.values():
                for card in col._cards:
                    status = card.trip_data.get("status", "")
                    truck_id = card.trip_data.get("truck_id")
                    if status == "In Transit" and truck_id:
                        pos = self._get_truck_position(truck_id, positions=positions)
                        card.set_live_position(pos)
                    else:
                        card.set_live_position(None)
        except Exception:
            pass

    def _on_load_older_delivered(self) -> None:
        self._delivered_show_all = True
        self._start_load()

    # ── Tab switching ─────────────────────────────────────────────────────────

    def _on_tab_switch(self, tab_id: str) -> None:
        if tab_id == "alerts":
            self._alerts_panel.refresh(self._all_card_data)
        elif tab_id == "timeline":
            self._timeline.refresh(self._all_card_data)

    # ── Search / Filter ───────────────────────────────────────────────────────

    def _on_search_filter(self, query: str, statuses: list) -> None:
        self._search_query = query
        self._search_statuses = statuses
        self._apply_filters()

    def _apply_filters(self) -> None:
        if getattr(self, '_destroyed', False):
            return
        visible = 0
        total = 0
        for col in self._columns.values():
            for card in col._cards:
                total += 1
                status = card.trip_data.get("status", "")
                column = STATUS_TO_COLUMN.get(status, "")
                show = True

                if column not in self._search_statuses:
                    show = False

                if show and self._search_query:
                    text = " ".join([
                        str(card.trip_data.get("trip_id", "")),
                        str(card.trip_data.get("truck_plate", "")),
                        str(card.trip_data.get("driver_name", "")),
                        str(card.trip_data.get("origin", "")),
                        str(card.trip_data.get("destination", "")),
                        str(card.trip_data.get("status", "")),
                    ]).lower()
                    if self._search_query not in text:
                        show = False

                if show:
                    card.show()
                    visible += 1
                else:
                    card.hide()

        self._search_bar.set_result_count(visible, total)

        has_data = total > 0
        if has_data and visible == 0:
            self._board_stack.setCurrentIndex(1)
        else:
            self._board_stack.setCurrentIndex(0)

    # ── Conflict scan ─────────────────────────────────────────────────────────

    def _run_conflict_scan(self) -> None:
        if getattr(self, '_destroyed', False):
            return
        try:
            all_trips = self._trip_service.get_all(limit=2000)
            active_trips = [
                t for t in all_trips
                if t.get("status", "") not in (
                    "Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced"
                )
            ]
            conflict_found = False
            trip_conflict_map: dict[int, list] = {}

            for trip in active_trips:
                conflicts = self._conflict_service.check_conflicts(trip)
                if conflicts:
                    tid = trip.get("id")
                    if tid not in trip_conflict_map:
                        trip_conflict_map[tid] = []
                    trip_conflict_map[tid] = conflicts
                    conflict_found = True

            self._conflict_alerts = trip_conflict_map
            if conflict_found:
                logger.info("Conflict scan: %d trips with resource conflicts", len(trip_conflict_map))
        except Exception:
            logger.debug("Conflict scan failed", exc_info=True)

    def _refresh_side_panels(self) -> None:
        if getattr(self, '_destroyed', False):
            return
        try:
            self._alerts_panel.refresh(self._all_card_data)
        except Exception:
            logger.warning("Failed to refresh alerts panel", exc_info=True)
        try:
            self._timeline.refresh(self._all_card_data)
        except Exception:
            logger.warning("Failed to refresh timeline", exc_info=True)
