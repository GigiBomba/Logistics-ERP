import json
import logging
import threading
import tkinter as tk
import customtkinter as ctk
from datetime import datetime, timedelta
from tkinter import messagebox
from typing import Any, Dict, List, Optional

from ui.styles import Theme
from ui.widgets.kanban_column import KanbanColumn
from ui.widgets.trip_card import TripCard
from utils.dates import parse_date
from services.i18n import t, register_listener, unregister_listener
from repositories.trip_repository import TripRepository
from repositories.fleet_repository import FleetRepository
from repositories.driver_repository import DriverRepository
from repositories.route_repository import RouteRepository
from services.operations.trip_status_engine import TripStatusEngine
from services.operations.event_bus import (
    EventBus, TRIP_CREATED, TRIP_STATUS_CHANGED, TRIP_UPDATED, TRIP_ASSIGNED,
    ALERT_CREATED, ALERT_RESOLVED, TRUCK_UPDATED, DRIVER_UPDATED, DRIVER_DELETED,
)
from services.operations.alert_manager import AlertManager, AlertType, Severity
from services.trip_service import TripService
from services.driver_truck_service import DriverTruckService
from services.conflict_service import TripConflictService
from services.fleet_tracking_service import fleet_tracking_service
from ui.widgets.assignment_dropdown import AssignmentDropdown
from utils.tk_helpers import safe_destroy
from ui.theme import COLORS, FONTS

logger = logging.getLogger(__name__)

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
}

COLUMN_DEFS = [
    ("Planned", "dispatch_board.col_planned", COLORS["chip_planned"]),
    ("Loading", "dispatch_board.col_loading", COLORS["chip_loading"]),
    ("In Transit", "dispatch_board.col_in_transit", COLORS["chip_transit"]),
    ("Delivered", "dispatch_board.col_delivered", COLORS["chip_delivered"]),
]

DELIVERED_DEFAULT_DAYS = 30


class DispatchBoardView:
    def __init__(self, parent, db, prefs=None, ops=None, embedded=False):
        self._embedded = embedded
        if embedded:
            self.win = None
            self.frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)
            self._tk_root = parent.winfo_toplevel()
        else:
            self.win = ctk.CTkToplevel(parent)
            self.win.title(f"\U0001f4cb {t('dispatch_board.title')}")
            self.win.geometry("1400x850")
            Theme.apply(self.win)
            self.win.configure(fg_color=Theme.BG)
            self.frame = self.win
            self._tk_root = self.win

        self.db = db
        self.prefs = prefs
        self.ops = ops
        self._i18n_widgets = []
        self._columns: Dict[str, KanbanColumn] = {}
        self._loading = False
        self._delivered_days = DELIVERED_DEFAULT_DAYS

        self._trip_repo = TripRepository(db)
        self._fleet_repo = FleetRepository(db)
        self._driver_repo = DriverRepository(db)
        self._route_repo = RouteRepository(db)
        self._status_engine = TripStatusEngine(db)
        self._event_bus = EventBus()
        self._trip_service = TripService(db)
        self._alert_mgr = AlertManager()
        self._dta_service = DriverTruckService(db)
        self._conflict_service = TripConflictService(db)

        self._driver_cache: Dict[int, Optional[Dict]] = {}
        self._route_cache: Dict[int, Optional[Dict]] = {}
        self._alert_counts: Dict[int, int] = {}
        self._delay_timer_id = None
        self._event_handlers = {}
        self._after_ids: list = []

        self._drag_data = {
            "card": None,
            "ghost": None,
            "source_column": None,
            "target_column": None,
        }

        self._build_ui()
        self._subscribe_events()
        self._start_load()

        register_listener(self._on_language_changed)
        if self.win:
            self.win.protocol("WM_DELETE_WINDOW", self._on_close)
            self.win.bind("<Destroy>", self._on_destroy)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_close(self):
        if self.win:
            self.win.destroy()

    def _on_destroy(self, event=None):
        if event is not None and event.widget != (self.win or self.frame):
            return
        for aid in self._after_ids:
            try:
                self._tk_root.after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()
        ghost = self._drag_data.get("ghost")
        if ghost:
            try:
                ghost.destroy()
            except Exception:
                pass
        self._unsubscribe_events()
        if self._delay_timer_id:
            self._tk_root.after_cancel(self._delay_timer_id)
            self._delay_timer_id = None
        try:
            self._status_engine.shutdown()
        except Exception:
            pass
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        try:
            if self.win:
                self.win.title(f"\U0001f4cb {t('dispatch_board.title')}")
            self._title_lbl.config(text=t("dispatch_board.title"))
            self._subtitle_lbl.config(text=t("dispatch_board.subtitle"))
        except Exception:
            pass
        for col in self._columns.values():
            col.refresh_title()

    def _build_ui(self):
        header = ctk.CTkFrame(self.frame, fg_color=Theme.SURFACE)
        header.pack(fill="x")

        self._title_lbl = ctk.CTkLabel(header, text=t("dispatch_board.title"),
                                      fg_color=Theme.SURFACE, text_color=Theme.TEXT,
                                      font=FONTS["h2"])
        self._title_lbl.pack(side="left")
        self._i18n_tag(self._title_lbl, "dispatch_board.title")

        self._subtitle_lbl = ctk.CTkLabel(header, text=t("dispatch_board.subtitle"),
                                         fg_color=Theme.SURFACE, text_color=Theme.MUTED,
                                         font=FONTS["label"])
        self._subtitle_lbl.pack(side="left", padx=(16, 0))
        self._i18n_tag(self._subtitle_lbl, "dispatch_board.subtitle")

        self._refresh_btn = ctk.CTkButton(header, text=f"\u21bb {t('dispatch_board.refresh')}",
                                         fg_color=Theme.ACCENT, text_color=Theme.TEXT,
                                          font=FONTS["small"],
                                         cursor="hand2",
                                         command=self._start_load)
        self._refresh_btn.pack(side="right")

        board = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        board.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        for i, (status_key, title_key, accent_color) in enumerate(COLUMN_DEFS):
            is_delivered = (status_key == "Delivered")
            col = KanbanColumn(board, status_key=status_key, title_key=title_key,
                               accent_color=accent_color,
                               on_card_click=self._on_card_click,
                               on_drag_start=self._on_drag_start,
                               on_assign_truck=self._on_assign_truck,
                               on_assign_driver=self._on_assign_driver,
                               show_load_older=is_delivered,
                               on_load_older=self._on_load_older_delivered,
                               on_retry=lambda sk=status_key: self._start_load())
            col.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 4, 0))
            self._columns[status_key] = col

    def _start_load(self):
        if self._loading:
            return
        self._loading = True
        for col in self._columns.values():
            col.show_loading()
        thread = threading.Thread(target=self._load_data_background, daemon=True)
        thread.start()

    def _load_data_background(self):
        try:
            self._alert_counts.clear()

            self._preload_alerts()

            all_statuses = list(STATUS_TO_COLUMN.keys())
            all_trips = self._trip_repo.get_by_statuses(all_statuses)

            column_trips: Dict[str, List[Dict[str, Any]]] = {col: [] for col, _, _ in COLUMN_DEFS}

            cutoff = (datetime.now() - timedelta(days=self._delivered_days)).strftime("%d/%m/%Y")

            for trip in all_trips:
                raw_status = trip.get("status", "")
                column = STATUS_TO_COLUMN.get(raw_status)
                if not column:
                    continue

                if column == "Delivered":
                    created = trip.get("created_at", "")
                    trip_date = created[:10] if len(created) >= 10 else created
                    if trip_date and trip_date < cutoff:
                        continue

                card_data = self._build_card_data(trip)
                column_trips[column].append(card_data)

            self._safe_after(0, lambda: self._populate_columns(column_trips))

        except Exception as e:
            logger.exception("Dispatch board data load failed")
            self._safe_after(0, lambda err=str(e): self._show_error_all(err))

    def _preload_alerts(self):
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

    def _build_card_data(self, trip: Dict[str, Any]) -> Dict[str, Any]:
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

    def _resolve_route(self, trip: Dict[str, Any]):
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

    def _extract_stops(self, route: Dict[str, Any]):
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

    def _populate_columns(self, column_trips: Dict[str, List[Dict[str, Any]]]):
        self._loading = False
        for status_key, col in self._columns.items():
            trips = column_trips.get(status_key, [])
            col.set_trips(trips)
        self._safe_after(100, self._evaluate_all_delays)
        self._safe_after(5000, self._start_delay_timer)
        # Refresh live position indicators on In Transit cards
        self._safe_after(200, self._refresh_live_indicators)
        self._schedule_live_refresh()

    def _show_error_all(self, error_msg: str):
        self._loading = False
        for col in self._columns.values():
            col.show_error(error_msg)

    def _get_truck_position(self, truck_id, positions=None):
        if not truck_id:
            return None
        try:
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

    def _refresh_live_indicators(self):
        if not fleet_tracking_service.is_configured():
            return
        try:
            positions = fleet_tracking_service.get_positions()
            by_plate = {}
            by_device = {}
            for pos in positions:
                if pos.name:
                    by_plate[pos.name.upper()] = pos
                if pos.device_id:
                    by_device[pos.device_id] = pos

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

    def _schedule_live_refresh(self):
        self._safe_after(30_000, self._refresh_live_indicators_and_reschedule)

    def _refresh_live_indicators_and_reschedule(self):
        self._refresh_live_indicators()
        self._schedule_live_refresh()

    def _on_load_older_delivered(self):
        self._delivered_days += 30
        self._start_load()

    def _on_card_click(self, trip_data):
        pass

    def _on_drag_start(self, card, event):
        if self._drag_data["ghost"]:
            return

        self._drag_data["card"] = card
        source_col = self._find_column_for_card(card)
        self._drag_data["source_column"] = source_col

        ghost = tk.Toplevel(self._tk_root)
        ghost.overrideredirect(True)
        ghost.attributes("-topmost", True)
        ghost.attributes("-alpha", 0.8)
        ghost.configure(bg=Theme.SURFACE2)

        ghost_lbl = tk.Label(ghost, text=card.trip_data.get("trip_id", ""),
                            bg=Theme.SURFACE2, fg=Theme.TEXT,
                            font=FONTS["small"],
                            padx=12, pady=8)
        ghost_lbl.pack()

        x = self._tk_root.winfo_pointerx() - 30
        y = self._tk_root.winfo_pointery() - 60
        ghost.geometry(f"+{x}+{y}")

        self._drag_data["ghost"] = ghost

        self._tk_root.bind("<B1-Motion>", self._on_drag_motion)
        self._tk_root.bind("<ButtonRelease-1>", self._on_drop)

    def _on_drag_motion(self, event):
        ghost = self._drag_data["ghost"]
        if not ghost:
            return

        x = self._tk_root.winfo_pointerx() - 30
        y = self._tk_root.winfo_pointery() - 60
        ghost.geometry(f"+{x}+{y}")

        ghost.withdraw()
        widget_under_cursor = self._tk_root.winfo_containing(event.x_root, event.y_root)
        ghost.deiconify()
        target_col = self._find_column_for_widget(widget_under_cursor)

        if target_col != self._drag_data["target_column"]:
            if self._drag_data["target_column"]:
                self._drag_data["target_column"].unhighlight_drop_zone()
            if target_col:
                target_col.highlight_drop_zone()
            self._drag_data["target_column"] = target_col

    def _on_drop(self, event):
        ghost = self._drag_data["ghost"]
        if ghost:
            ghost.destroy()

        self._tk_root.unbind("<B1-Motion>")
        self._tk_root.unbind("<ButtonRelease-1>")

        target_col = self._drag_data["target_column"]
        if target_col:
            target_col.unhighlight_drop_zone()

        card = self._drag_data["card"]
        source_col = self._drag_data["source_column"]

        if target_col and target_col != source_col and card:
            trip_id = card.trip_data.get("trip_id_num")
            old_status = source_col.status_key
            new_status = target_col.status_key

            self._handle_transition(trip_id, old_status, new_status, card, source_col, target_col)

        self._drag_data = {
            "card": None,
            "ghost": None,
            "source_column": None,
            "target_column": None,
        }

    def _find_column_for_card(self, card):
        for col in self._columns.values():
            if card in col._cards:
                return col
        return None

    def _find_column_for_widget(self, widget):
        if not widget:
            return None
        for col in self._columns.values():
            if self._widget_is_child(col, widget):
                return col
        return None

    def _widget_is_child(self, parent, child):
        while child:
            if child == parent:
                return True
            try:
                child = child.master
            except Exception:
                break
        return False

    def _handle_transition(self, trip_id, old_status, new_status, card, source_col, target_col):
        column_order = ["Planned", "Loading", "In Transit", "Delivered"]
        old_idx = column_order.index(old_status) if old_status in column_order else -1
        new_idx = column_order.index(new_status) if new_status in column_order else -1

        is_backward = new_idx < old_idx

        if is_backward:
            confirmed = messagebox.askyesno(
                t("dispatch_board.confirm_title"),
                t("dispatch_board.confirm_backward").format(old_status, new_status)
            )
            if not confirmed:
                return

        # Immediate visual feedback: create a new card in the target (correct master),
        # remove and destroy the original, and handle rollback on failure.
        card_backup = dict(card.trip_data)

        # create new card in the target scrollable frame (so its master is correct)
        new_card = TripCard(
            target_col._scroll_frame,
            {**card_backup, "status": new_status},
            on_click=self._on_card_click,
            on_drag_start=self._on_drag_start,
            on_assign_truck=self._on_assign_truck,
            on_assign_driver=self._on_assign_driver
        )

        target_col.add_card(new_card)

        if source_col:
            # remove visual reference from source list and destroy original widget
            source_col.remove_card(card)
            try:
                card.destroy()
            except Exception:
                pass

        # update visual state on the new card
        new_card.trip_data["status"] = new_status
        if hasattr(new_card, "_set_status"):
            new_card._set_status(new_status)

        try:
            if self.ops:
                ok = self.ops.force_trip_status(trip_id, new_status)
                if not ok:
                    raise RuntimeError(f"Status transition failed for trip {trip_id}")
            else:
                self._status_engine.transition(trip_id, new_status)
            self._show_success_toast(t("dispatch_board.transition_success").format(new_status))
        except Exception as e:
            # Rollback visual on failure: remove the new card and recreate the original in source
            try:
                target_col.remove_card(new_card)
                new_card.destroy()
            except Exception:
                pass

            # restore original card in the source column
            restored = TripCard(
                source_col._scroll_frame if source_col else self._columns.get(old_status)._scroll_frame,
                {**card_backup, "status": old_status},
                on_click=self._on_card_click,
                on_drag_start=self._on_drag_start,
                on_assign_truck=self._on_assign_truck,
                on_assign_driver=self._on_assign_driver
            )
            if source_col:
                source_col.add_card(restored)

            self._show_error_toast(t("dispatch_board.transition_error").format(old_status, new_status))

    def _show_success_toast(self, msg):
        toast = tk.Toplevel(self._tk_root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg=Theme.ACCENT_SUCCESS)

        lbl = tk.Label(toast, text=msg, bg=Theme.ACCENT_SUCCESS, fg=Theme.TEXT,
                      font=FONTS["small"], padx=16, pady=8)
        lbl.pack()

        x = self._tk_root.winfo_x() + self._tk_root.winfo_width() // 2 - 100
        y = self._tk_root.winfo_y() + 80
        toast.geometry(f"+{x}+{y}")

        self._safe_after(2500, lambda: safe_destroy(toast))

    def _show_error_toast(self, msg):
        toast = tk.Toplevel(self._tk_root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg=Theme.DANGER)

        lbl = tk.Label(toast, text=msg, bg=Theme.DANGER, fg=Theme.TEXT,
                      font=FONTS["small"], padx=16, pady=8)
        lbl.pack()

        x = self._tk_root.winfo_x() + self._tk_root.winfo_width() // 2 - 100
        y = self._tk_root.winfo_y() + 80
        toast.geometry(f"+{x}+{y}")

        self._safe_after(3000, lambda: safe_destroy(toast))

    def _on_assign_truck(self, card, clear=False):
        if clear:
            self._clear_truck_assignment(card)
            return

        def fetch_trucks():
            active_trucks = self._fleet_repo.get_active_trucks()
            card_data = card.trip_data

            truck_conflicts = {}
            for truck_entry in active_trucks:
                plate = truck_entry.get("plate_number", "")
                conflicts = self._conflict_service.check_conflicts({
                    "truck_plate": plate,
                    "start_date": card_data.get("departure_date", ""),
                    "end_date": card_data.get("eta", ""),
                    "distance_km": 0,
                })
                conf = [c for c in conflicts if c.get("trip_id") != card_data.get("trip_id_num")]
                if conf:
                    truck_conflicts[plate] = conf

            items = []
            for truck in active_trucks:
                plate = truck.get("plate_number", "")
                model = truck.get("model", "")
                truck_id = truck.get("id")

                conflicting = truck_conflicts.get(plate)
                available = not conflicting
                if conflicting:
                    trip_ref = conflicting[0].get("trip_id", "")
                    overlap = conflicting[0].get("overlap_description", "")
                    status_text = t("dispatch_board.unavailable_overlap").format(f"{t('dispatch_board.trip_id_prefix')}{trip_ref} ({overlap})")
                else:
                    status_text = ""

                items.append({
                    "id": truck_id,
                    "label": plate,
                    "sublabel": model,
                    "available": available,
                    "status_text": status_text,
                    "plate": plate,
                })

            items.sort(key=lambda x: (not x["available"], x["label"]))
            return items

        def on_select(truck_id):
            self._assign_truck_to_trip(card, truck_id)

        dropdown = AssignmentDropdown(
            self._tk_root, card._truck_lbl,
            t("dispatch_board.select_truck"),
            fetch_trucks, on_select,
            on_close=lambda: card.set_dropdown(None)
        )
        card.set_dropdown(dropdown)

    def _on_assign_driver(self, card, clear=False):
        if clear:
            self._clear_driver_assignment(card)
            return

        def fetch_drivers():
            active_drivers = self._driver_repo.get_active_drivers()
            card_data = card.trip_data

            driver_conflicts = {}
            for d in active_drivers:
                did = d.get("id")
                conflicts = self._conflict_service.check_conflicts({
                    "driver_id": did,
                    "start_date": card_data.get("departure_date", ""),
                    "end_date": card_data.get("eta", ""),
                    "distance_km": 0,
                })
                conf = [c for c in conflicts if c.get("trip_id") != card_data.get("trip_id_num")]
                if conf:
                    driver_conflicts[did] = conf

            items = []
            for driver in active_drivers:
                driver_id = driver.get("id")
                name = driver.get("name", "")
                license_cat = driver.get("license_category", "")

                conflicting = driver_conflicts.get(driver_id)
                available = not conflicting
                if conflicting:
                    trip_ref = conflicting[0].get("trip_id", "")
                    status_text = t("dispatch_board.unavailable_overlap").format(f"{t('dispatch_board.trip_id_prefix')}{trip_ref}")
                else:
                    status_text = ""

                items.append({
                    "id": driver_id,
                    "label": name,
                    "sublabel": license_cat,
                    "available": available,
                    "status_text": status_text,
                    "name": name,
                })

            items.sort(key=lambda x: (not x["available"], x["label"]))
            return items

        def on_select(driver_id):
            self._assign_driver_to_trip(card, driver_id)

        dropdown = AssignmentDropdown(
            self._tk_root, card._driver_lbl,
            t("dispatch_board.select_driver"),
            fetch_drivers, on_select,
            on_close=lambda: card.set_dropdown(None)
        )
        card.set_dropdown(dropdown)

    def _assign_truck_to_trip(self, card, truck_id):
        try:
            truck = self._fleet_repo.get_by_id(truck_id)
            if not truck:
                raise ValueError(t("dispatch_board.truck_not_found"))
            
            plate = truck.get("plate_number", "")
            trip_id = card.trip_data.get("trip_id_num")
            
            self._trip_service.update(trip_id, {"truck_number": plate})
            
            card.update_truck(plate, truck_id)
            
            self._event_bus.publish(TRIP_ASSIGNED, {
                "trip_id": trip_id,
                "truck_id": truck_id,
            })
            
            logger.info("Assigned truck %s to trip %d", plate, trip_id)
        except Exception as e:
            logger.error("Failed to assign truck: %s", e)
            card.show_error("truck", str(e))

    def _assign_driver_to_trip(self, card, driver_id):
        try:
            driver = self._driver_repo.get_by_id(driver_id)
            if not driver:
                raise ValueError(t("dispatch_board.driver_not_found"))
            
            name = driver.get("name", "")
            trip_id = card.trip_data.get("trip_id_num")
            
            self._trip_service.update(trip_id, {"driver_id": driver_id, "driver_name": name})
            
            card.update_driver(name, driver_id)
            
            self._event_bus.publish(TRIP_ASSIGNED, {
                "trip_id": trip_id,
                "driver_id": driver_id,
            })
            
            logger.info("Assigned driver %s to trip %d", name, trip_id)
        except Exception as e:
            logger.error("Failed to assign driver: %s", e)
            card.show_error("driver", str(e))

    def _clear_truck_assignment(self, card):
        try:
            trip_id = card.trip_data.get("trip_id_num")
            self._trip_service.update(trip_id, {"truck_number": ""})
            card.update_truck("", None)
            
            logger.info("Cleared truck assignment for trip %d", trip_id)
        except Exception as e:
            logger.error("Failed to clear truck: %s", e)
            card.show_error("truck", str(e))

    def _clear_driver_assignment(self, card):
        try:
            trip_id = card.trip_data.get("trip_id_num")
            self._trip_service.update(trip_id, {"driver_id": None, "driver_name": ""})
            card.update_driver("", None)
            
            logger.info("Cleared driver assignment for trip %d", trip_id)
        except Exception as e:
            logger.error("Failed to clear driver: %s", e)
            card.show_error("driver", str(e))

    def _start_delay_timer(self):
        if self._delay_timer_id:
            self._tk_root.after_cancel(self._delay_timer_id)
        self._delay_timer_id = self._safe_after(300000, self._start_delay_timer)
        self._evaluate_all_delays()

    def _evaluate_all_delays(self):
        try:
            if not self._tk_root.winfo_exists():
                return
        except tk.TclError:
            return
        try:
            now = datetime.now()
            for col in self._columns.values():
                for card in col._cards:
                    trip_data = card.trip_data
                    is_delayed, minutes_overdue = self._is_trip_delayed(trip_data, now)
                    card.set_delayed(is_delayed, minutes_overdue)
                    if is_delayed:
                        self._create_delay_alert(card, minutes_overdue)
        except Exception:
            logger.debug("Delay evaluation skipped", exc_info=True)

    def _dispatch(self, fn):
        try:
            self._safe_after(0, fn)
        except tk.TclError:
            pass

    def _subscribe_events(self):
        handlers = {
            TRIP_CREATED: self._on_trip_created_ev,
            TRIP_STATUS_CHANGED: self._on_status_changed_ev,
            TRIP_UPDATED: self._on_trip_updated_ev,
            TRIP_ASSIGNED: self._on_trip_assigned_ev,
            ALERT_CREATED: self._on_alert_created_ev,
            ALERT_RESOLVED: self._on_alert_resolved_ev,
            TRUCK_UPDATED: self._on_truck_updated_ev,
            DRIVER_UPDATED: self._on_driver_updated_ev,
            DRIVER_DELETED: self._on_driver_deleted_ev,
        }
        for event_type, handler in handlers.items():
            self._event_bus.subscribe(event_type, handler)
            self._event_handlers[event_type] = handler
        logger.debug("DispatchBoardView subscribed to %d event types", len(handlers))

    def _unsubscribe_events(self):
        for event_type, handler in list(self._event_handlers.items()):
            try:
                self._event_bus.unsubscribe(event_type, handler)
            except Exception:
                pass
        self._event_handlers.clear()
        logger.debug("DispatchBoardView unsubscribed all events")

    def _on_trip_created_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_trip_created(e))

    def _on_status_changed_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_status_changed(e))

    def _on_trip_updated_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_trip_updated(e))

    def _on_trip_assigned_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_trip_assigned(e))

    def _on_alert_created_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_alert_created(e))

    def _on_alert_resolved_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_alert_resolved(e))

    def _on_truck_updated_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_truck_updated(e))

    def _on_driver_updated_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_driver_updated(e))

    def _on_driver_deleted_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_driver_deleted(e))

    def _handle_trip_created(self, ev):
        data = ev.get("data", {})
        trip_id = data.get("trip_id")
        if not trip_id:
            return
        try:
            trip = self._trip_repo.get_by_id(int(trip_id))
            if not trip:
                return
            card_data = self._build_card_data(trip)
            planned_col = self._columns.get("Planned")
            if planned_col:
                card = TripCard(planned_col._inner_frame, card_data,
                                on_click=self._on_card_click,
                                on_drag_start=self._on_drag_start,
                                on_assign_truck=self._on_assign_truck,
                                on_assign_driver=self._on_assign_driver)
                planned_col.add_card(card, index=0)
            logger.debug("Trip %d card added to Planned column", trip_id)
        except Exception:
            logger.debug("Failed to handle trip.created for %s", trip_id, exc_info=True)

    def _handle_status_changed(self, ev):
        try:
            data = ev.get("data", {})
            trip_id = data.get("trip_id")
            new_status = data.get("new_status")
            if not trip_id or not new_status:
                return
            column_key = STATUS_TO_COLUMN.get(new_status)
            if not column_key:
                return
            card = self._find_card_by_trip_id(trip_id)
            if not card:
                return
            target = self._columns.get(column_key)
            if not target:
                return
            source = self._find_column_for_card(card)
            if source == target:
                card.trip_data["status"] = new_status
                card.set_delayed(False, 0)
                return

            card_data = dict(card.trip_data)
            card_data["status"] = new_status

            if source:
                source.remove_card(card)
            card.destroy()

            new_card = TripCard(target._inner_frame, card_data,
                               on_click=self._on_card_click,
                               on_drag_start=self._on_drag_start,
                               on_assign_truck=self._on_assign_truck,
                               on_assign_driver=self._on_assign_driver)
            target.add_card(new_card, index=0)

            if new_status == "Delivered":
                self._resolve_delay_alert(new_card)
            self._evaluate_single_delay(new_card)
            logger.debug("Trip %d moved to %s column via event", trip_id, column_key)
        except Exception:
            logger.exception("Failed to handle status change for trip %s", trip_id)

    def _handle_trip_updated(self, ev):
        data = ev.get("data", {})
        trip_id = data.get("trip_id")
        if not trip_id:
            return
        self._refresh_card_in_place(trip_id)

    def _handle_trip_assigned(self, ev):
        data = ev.get("data", {})
        trip_id = data.get("trip_id")
        if not trip_id:
            return
        card = self._find_card_by_trip_id(trip_id)
        if not card:
            return
        try:
            trip = self._trip_service.get_by_id(trip_id)
            if trip:
                card.trip_data["truck_plate"] = trip.get("truck_number", "")
                card.trip_data["driver_name"] = trip.get("driver_name", "")
                card.trip_data["driver_id"] = trip.get("driver_id")
                card.update_truck(trip.get("truck_number", ""))
                card.update_driver(trip.get("driver_name", ""), trip.get("driver_id"))
        except Exception:
            logger.debug("Failed to refresh assignment for trip %d", trip_id, exc_info=True)

    def _handle_alert_created(self, ev):
        data = ev.get("data", {})
        alert = data.get("alert", {})
        trip_id = alert.get("trip_id")
        if not trip_id:
            return
        try:
            tid = int(trip_id)
        except (ValueError, TypeError):
            return
        self._alert_counts[tid] = self._alert_counts.get(tid, 0) + 1
        card = self._find_card_by_trip_id(tid)
        if card:
            card.trip_data["alerts_count"] = self._alert_counts[tid]

    def _handle_alert_resolved(self, ev):
        data = ev.get("data", {})
        alert = data.get("alert", {})
        trip_id = alert.get("trip_id")
        if not trip_id:
            return
        try:
            tid = int(trip_id)
        except (ValueError, TypeError):
            return
        current = self._alert_counts.get(tid, 0)
        self._alert_counts[tid] = max(0, current - 1)
        card = self._find_card_by_trip_id(tid)
        if card:
            card.trip_data["alerts_count"] = self._alert_counts.get(tid, 0)

    def _handle_truck_updated(self, ev):
        data = ev.get("data", {})
        truck_id = data.get("truck_id")
        truck_plate = data.get("plate_number")
        if not truck_id and not truck_plate:
            return
        for col in self._columns.values():
            for card in col._cards:
                card_plate = card.trip_data.get("truck_plate", "")
                card_truck_id = card.trip_data.get("truck_id")
                if (truck_plate and card_plate == truck_plate) or \
                   (truck_id is not None and card_truck_id == truck_id):
                    try:
                        trip_id = card.trip_data.get("trip_id_num")
                        self._refresh_card_in_place(trip_id)
                    except Exception:
                        pass

    def _handle_driver_updated(self, ev):
        try:
            data = ev.get("data", {})
            driver_id = data.get("driver_id")
            if not driver_id:
                return
            for col in self._columns.values():
                for card in col._cards:
                    if card.trip_data.get("driver_id") == driver_id:
                        card.update_driver(
                            data.get("name", card.trip_data.get("driver_name", "")),
                            driver_id,
                        )
        except Exception:
            pass

    def _handle_driver_deleted(self, ev):
        try:
            data = ev.get("data", {})
            driver_id = data.get("driver_id")
            if not driver_id:
                return
            for col in self._columns.values():
                for card in col._cards:
                    if card.trip_data.get("driver_id") == driver_id:
                        card.update_driver("", None)
        except Exception:
            pass

    def _find_card_by_trip_id(self, trip_id):
        for col in self._columns.values():
            for card in col._cards:
                if card.trip_data.get("trip_id_num") == trip_id:
                    return card
        return None

    def _refresh_card_in_place(self, trip_id):
        card = self._find_card_by_trip_id(trip_id)
        if not card:
            return
        try:
            trip = self._trip_service.get_by_id(trip_id)
            if not trip:
                return
            card.trip_data["truck_plate"] = trip.get("truck_number", "")
            card.trip_data["driver_name"] = trip.get("driver_name", "")
            card.trip_data["driver_id"] = trip.get("driver_id")
            card.trip_data["eta"] = trip.get("end_date", "")
            card.trip_data["departure_date"] = trip.get("start_date", "")
            card.update_truck(trip.get("truck_number", ""))
            card.update_driver(trip.get("driver_name", ""), trip.get("driver_id"))
            card.trip_data["alerts_count"] = self._alert_counts.get(trip_id, 0)
            self._evaluate_single_delay(card)
        except Exception:
            logger.debug("Failed to refresh card for trip %d", trip_id, exc_info=True)

    def _evaluate_single_delay(self, card):
        try:
            now = datetime.now()
            is_delayed, minutes_overdue = self._is_trip_delayed(card.trip_data, now)
            card.set_delayed(is_delayed, minutes_overdue)
            if is_delayed:
                self._create_delay_alert(card, minutes_overdue)
        except Exception:
            pass

    def _is_trip_delayed(self, trip_data: dict, now: datetime):
        status = trip_data.get("status", "")
        eta = trip_data.get("eta", "")
        departure = trip_data.get("departure_date", "")
        
        if status in ("In Transit", "InTransit", "Active", "InProgress"):
            if not eta:
                return False, 0
            try:
                eta_dt = self._parse_date(eta)
                if not eta_dt:
                    return False, 0
                if now > eta_dt:
                    minutes = int((now - eta_dt).total_seconds() / 60)
                    return True, minutes
            except Exception:
                pass
        
        elif status in ("Loading", "Preparing", "Pickup"):
            if not departure:
                return False, 0
            try:
                dep_dt = self._parse_date(departure)
                if not dep_dt:
                    return False, 0
                threshold = dep_dt + timedelta(hours=2)
                if now > threshold:
                    minutes = int((now - threshold).total_seconds() / 60)
                    return True, minutes
            except Exception:
                pass
        
        elif status in ("Planned", "Scheduled", "Pending"):
            if not departure:
                return False, 0
            try:
                dep_dt = self._parse_date(departure)
                if not dep_dt:
                    return False, 0
                threshold = now - timedelta(hours=24)
                if dep_dt < threshold:
                    minutes = int((threshold - dep_dt).total_seconds() / 60)
                    return True, minutes
            except Exception:
                pass
        
        return False, 0

    def _parse_date(self, date_str: str):
        return parse_date(date_str, "%d/%m/%Y")

    def _create_delay_alert(self, card, minutes_overdue: int):
        trip_id = card.trip_data.get("trip_id_num")
        if not trip_id:
            return
        
        existing = self._alert_mgr.get_alerts(
            alert_type=AlertType.TRIP_DELAY,
            resolved=False,
            limit=1000
        )
        for alert in existing:
            if alert.trip_id == str(trip_id):
                return
        
        severity = Severity.CRITICAL if minutes_overdue > 120 else Severity.WARNING
        truck_plate = card.trip_data.get("truck_plate", "")
        driver_name = card.trip_data.get("driver_name", "")
        
        title = t("dispatch_board.delay_alert_title").format(trip_id)
        message = t("dispatch_board.delay_alert_message").format(
            minutes_overdue, truck_plate or t("common.na"), driver_name or t("common.na")
        )
        
        self._alert_mgr.create_alert(
            alert_type=AlertType.TRIP_DELAY,
            severity=severity,
            title=title,
            message=message,
            truck_id=truck_plate if truck_plate else None,
            trip_id=str(trip_id),
            metadata={
                "minutes_overdue": minutes_overdue,
                "status": card.trip_data.get("status", ""),
            }
        )
        logger.info("Created delay alert for trip %d (%d minutes overdue)", trip_id, minutes_overdue)

    def _resolve_delay_alert(self, card):
        trip_id = card.trip_data.get("trip_id_num")
        if not trip_id:
            return
        
        existing = self._alert_mgr.get_alerts(
            alert_type=AlertType.TRIP_DELAY,
            resolved=False,
            limit=1000
        )
        for alert in existing:
            if alert.trip_id == str(trip_id):
                self._alert_mgr.resolve_alert(alert.id)
                logger.info("Resolved delay alert for trip %d", trip_id)
                return

    def _safe_after(self, ms, callback):
        try:
            aid = self._tk_root.after(ms, callback)
            self._after_ids.append(aid)
            return aid
        except tk.TclError:
            return None
