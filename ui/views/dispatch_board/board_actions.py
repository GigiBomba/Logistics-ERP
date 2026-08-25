"""Dispatch board — bulk operations, drag-drop handling, status transitions, assignments."""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from PySide6.QtCore import QMimeData, QPoint, Qt, QTimer
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QWidget,
)

from models.trip_models import TripUpdate
from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
from services.i18n import t
from services.operations.alert_manager import AlertType, Severity
from services.operations.event_bus import TRIP_ASSIGNED, VALID_TRANSITIONS
from ui.widgets.assignment_dropdown import QtAssignmentDropdown
from ui.widgets.toast import Toast
from ui.widgets.trip_card import QtTripCard

logger = logging.getLogger(__name__)


class BoardActionsMixin:
    """Mixin providing board actions: drag-drop, bulk ops, assignment, transitions."""

    # ══════════════════════════════════════════════════════════════════════════
    # Detail panel (side drawer)
    # ══════════════════════════════════════════════════════════════════════════

    def _on_card_click(self, trip_data: dict) -> None:
        """Open the detail side drawer when a card is clicked."""
        self._open_detail_drawer(trip_data)

    def _on_detail_close(self) -> None:
        """Called when the detail drawer is dismissed."""
        pass

    def _on_status_change_card(self, card, target_status: str) -> None:
        """Handle quick-action status change from a trip card."""
        trip_id = card.trip_data.get("trip_id_num") or card.trip_data.get("trip_id")
        if not trip_id:
            return
        try:
            trip_id = int(trip_id)
        except (ValueError, TypeError):
            return

        source_col = self._find_column_for_card(card)
        if source_col is None:
            return
        source_status = source_col.status_key
        target_col = self._columns.get(target_status)
        if target_col is None:
            return

        self._handle_transition(
            trip_id,
            source_status,
            target_status,
            card,
            source_col,
            target_col,
        )

    def _on_navigate_to_generators(self, trip_id: int, tab_index: int) -> None:
        """Navigate to the Generators view with the trip pre-selected and the correct tab active."""
        if hasattr(self, "_on_navigate") and self._on_navigate is not None:
            self._on_navigate("invoices", {"trip_id": trip_id, "tab": tab_index})

    # ══════════════════════════════════════════════════════════════════════════
    # Quick Assign (from Alerts panel)
    # ══════════════════════════════════════════════════════════════════════════

    def _on_quick_assign_truck(self, item: dict) -> None:
        trip_id = item.get("trip_id_num") or item.get("trip_id")
        if not trip_id:
            return
        card = self._find_card_by_trip_id(trip_id)
        if card:
            self._tabs.switch_to("board")
            self._on_assign_truck(card)

    def _on_quick_assign_driver(self, item: dict) -> None:
        trip_id = item.get("trip_id_num") or item.get("trip_id")
        if not trip_id:
            return
        card = self._find_card_by_trip_id(trip_id)
        if card:
            self._tabs.switch_to("board")
            self._on_assign_driver(card)

    def _on_quick_assign_both(self, item: dict) -> None:
        trip_id = item.get("trip_id_num") or item.get("trip_id")
        if not trip_id:
            return
        card = self._find_card_by_trip_id(trip_id)
        if card:
            self._tabs.switch_to("board")
            self._on_assign_both(card)

    def _on_resolve_alert_refresh(self) -> None:
        self._alerts_panel.refresh(self._all_card_data)
        self._preload_alerts()
        for col in self._columns.values():
            for card in col._cards:
                trip_id = card.trip_data.get("trip_id_num")
                if trip_id:
                    card.trip_data["alerts_count"] = self._alert_counts.get(trip_id, 0)

    # ══════════════════════════════════════════════════════════════════════════
    # Bulk Selection
    # ══════════════════════════════════════════════════════════════════════════

    def _on_card_select_changed(self, card: QtTripCard, selected: bool) -> None:
        if selected:
            if card not in self._selected_cards:
                self._selected_cards.append(card)
        else:
            if card in self._selected_cards:
                self._selected_cards.remove(card)
        self._update_bulk_toolbar()

    def _clear_all_selections(self) -> None:
        for card in list(self._selected_cards):
            card.set_selected(False)
        self._selected_cards.clear()
        self._update_bulk_toolbar()

    def _update_bulk_toolbar(self) -> None:
        count = len(self._selected_cards)
        if count > 0:
            self._bulk_count_lbl.setText(
                t("dispatch_board.bulk_selected_count").format(n=count)
            )
            self._bulk_toolbar.show()
        else:
            self._bulk_toolbar.hide()

    def _on_bulk_assign_truck(self) -> None:
        if not self._selected_cards:
            return

        def fetch_trucks():
            if self._is_remote_mode():
                # Remote mode: no local fleet repo — list active trucks from
                # the API (when available); no conflict/block data.
                active_trucks = self._remote_active_trucks()
                items = []
                for truck in active_trucks:
                    items.append({
                        "id": truck.get("id"),
                        "label": truck.get("plate_number", ""),
                        "sublabel": truck.get("model", ""),
                        "available": True,
                        "status_text": "",
                    })
                items.sort(key=lambda x: x["label"])
                return items
            active_trucks = self._fleet_repo.get_active_trucks()
            items = []
            for truck in active_trucks:
                items.append({
                    "id": truck.get("id"),
                    "label": truck.get("plate_number", ""),
                    "sublabel": truck.get("model", ""),
                    "available": True,
                    "status_text": "",
                })
            items.sort(key=lambda x: x["label"])
            return items

        def on_select(truck_id):
            self._assign_truck_to_selected(truck_id)

        dropdown = QtAssignmentDropdown(
            self,
            anchor_widget=self._bulk_assign_truck_btn,
            title=t("dispatch_board.select_truck"),
            fetch_func=fetch_trucks,
            on_select=on_select,
        )
        dropdown.show_anchored(self._bulk_assign_truck_btn)

    def _on_bulk_assign_driver(self) -> None:
        if not self._selected_cards:
            return

        def fetch_drivers():
            if self._is_remote_mode():
                # Remote mode: no local driver repo — list active drivers from
                # the API (when available); no conflict/hours data.
                active_drivers = self._remote_active_drivers()
                items = []
                for d in active_drivers:
                    items.append({
                        "id": d.get("id"),
                        "label": d.get("name", ""),
                        "sublabel": d.get("license_category", ""),
                        "available": True,
                        "status_text": "",
                    })
                items.sort(key=lambda x: x["label"])
                return items
            active_drivers = self._driver_repo.get_active_drivers()
            items = []
            for d in active_drivers:
                items.append({
                    "id": d.get("id"),
                    "label": d.get("name", ""),
                    "sublabel": d.get("license_category", ""),
                    "available": True,
                    "status_text": "",
                })
            items.sort(key=lambda x: x["label"])
            return items

        def on_select(driver_id):
            self._assign_driver_to_selected(driver_id)

        dropdown = QtAssignmentDropdown(
            self,
            anchor_widget=self._bulk_assign_driver_btn,
            title=t("dispatch_board.select_driver"),
            fetch_func=fetch_drivers,
            on_select=on_select,
        )
        dropdown.show_anchored(self._bulk_assign_driver_btn)

    def _assign_truck_to_selected(self, truck_id: int) -> None:
        try:
            if self._is_remote_mode():
                trip_ids = [
                    card.trip_data.get("trip_id_num")
                    for card in self._selected_cards
                    if card.trip_data.get("trip_id_num")
                ]
                result = self._dispatch_service.bulk_assign(trip_ids, truck_id=truck_id)
                updated = result.get("updated", []) if isinstance(result, dict) else []
                failed = result.get("failed", []) if isinstance(result, dict) else []
                if updated:
                    self._show_toast(
                        t("dispatch_board.bulk_success").format(count=len(updated)),
                        "success",
                    )
                if failed:
                    self._show_toast(
                        t("dispatch_board.bulk_partial").format(
                            ok=len(updated), failed=len(failed),
                        ),
                        "warning",
                    )
                if not updated and not failed:
                    self._show_toast(t("dispatch_board.truck_not_found"), "error")
                self._refresh_after_remote_assignment()
                self._clear_all_selections()
                return
            truck = self._fleet_repo.get_by_id(truck_id)
            if not truck:
                return
            plate = truck.get("plate_number", "")
            ok_count = 0
            failed = 0
            for card in list(self._selected_cards):
                try:
                    trip_id = card.trip_data.get("trip_id_num")
                    self._trip_service.update(trip_id, TripUpdate(truck_plate=plate, truck_id=truck_id))
                    card.update_truck(plate, truck_id)
                    self._event_bus.publish(TRIP_ASSIGNED, {"trip_id": trip_id, "truck_id": truck_id})
                    ok_count += 1
                except Exception:
                    failed += 1
            if failed:
                self._show_toast(t("dispatch_board.bulk_partial").format(ok=ok_count, failed=failed), "warning")
            else:
                self._show_toast(t("dispatch_board.bulk_success").format(count=ok_count), "success")
            self._clear_all_selections()
        except Exception as e:
            self._show_toast(str(e), "error")

    def _assign_driver_to_selected(self, driver_id: int) -> None:
        try:
            if self._is_remote_mode():
                trip_ids = [
                    card.trip_data.get("trip_id_num")
                    for card in self._selected_cards
                    if card.trip_data.get("trip_id_num")
                ]
                result = self._dispatch_service.bulk_assign(trip_ids, driver_id=driver_id)
                updated = result.get("updated", []) if isinstance(result, dict) else []
                failed = result.get("failed", []) if isinstance(result, dict) else []
                if updated:
                    self._show_toast(
                        t("dispatch_board.bulk_success").format(count=len(updated)),
                        "success",
                    )
                if failed:
                    self._show_toast(
                        t("dispatch_board.bulk_partial").format(
                            ok=len(updated), failed=len(failed),
                        ),
                        "warning",
                    )
                if not updated and not failed:
                    self._show_toast(t("dispatch_board.driver_not_found"), "error")
                self._refresh_after_remote_assignment()
                self._clear_all_selections()
                return
            driver = self._driver_repo.get_by_id(driver_id)
            if not driver:
                return
            name = driver.get("name", "")
            ok_count = 0
            failed = 0
            for card in list(self._selected_cards):
                try:
                    trip_id = card.trip_data.get("trip_id_num")
                    self._trip_service.update(trip_id, TripUpdate(driver_id=driver_id, driver_name=name))
                    card.update_driver(name, driver_id)
                    self._event_bus.publish(TRIP_ASSIGNED, {"trip_id": trip_id, "driver_id": driver_id})
                    ok_count += 1
                except Exception:
                    failed += 1
            if failed:
                self._show_toast(t("dispatch_board.bulk_partial").format(ok=ok_count, failed=failed), "warning")
            else:
                self._show_toast(t("dispatch_board.bulk_success").format(count=ok_count), "success")
            self._clear_all_selections()
        except Exception as e:
            self._show_toast(str(e), "error")

    # ══════════════════════════════════════════════════════════════════════════
    # Undo / Redo
    # ══════════════════════════════════════════════════════════════════════════

    def _on_undo(self) -> None:
        if not self.ops:
            self._show_toast(t("dispatch_board.undo_nothing"), "error")
            return
        stack = self.ops.undo_stack
        cmd = stack.last_undo_command()
        if not cmd:
            self._show_toast(t("dispatch_board.undo_nothing"), "error")
            return
        ok = self.ops.undo_last()
        if ok:
            self._show_toast(
                t("dispatch_board.undo_success").format(
                    trip_id=cmd.trip_id, old_status=cmd.old_status, new_status=cmd.new_status
                ),
                "success",
            )
            QTimer.singleShot(500, self._start_load)

    def _on_redo(self) -> None:
        if not self.ops:
            self._show_toast(t("dispatch_board.redo_nothing"), "error")
            return
        stack = self.ops.undo_stack
        cmd = stack.last_redo_command()
        if not cmd:
            self._show_toast(t("dispatch_board.redo_nothing"), "error")
            return
        ok = self.ops.redo_last()
        if ok:
            self._show_toast(
                t("dispatch_board.redo_success").format(
                    trip_id=cmd.trip_id, old_status=cmd.old_status, new_status=cmd.new_status
                ),
                "success",
            )
            QTimer.singleShot(500, self._start_load)

    # ══════════════════════════════════════════════════════════════════════════
    # Drag-Drop
    # ══════════════════════════════════════════════════════════════════════════

    def _on_drag_start(self, card: QtTripCard, event: QMouseEvent) -> None:
        if self._drag_card is not None:
            return
        self._drag_card = card
        self._drag_source_col = self._find_column_for_card(card)

        drag = QDrag(card)
        mime = QMimeData()
        trip_id = card.trip_data.get("trip_id_num", "")
        mime.setText(str(trip_id))
        drag.setMimeData(mime)

        if self._drag_source_col is not None:
            self._drag_source_col.highlight_drop_zone()

        drag.exec(Qt.MoveAction)

        if self._drag_source_col is not None:
            self._drag_source_col.unhighlight_drop_zone()
        if self._drag_target_col is not None and self._drag_target_col != self._drag_source_col:
            self._drag_target_col.unhighlight_drop_zone()

        self._drag_card = None
        self._drag_source_col = None
        self._drag_target_col = None

    def _find_column_for_card(self, card: QtTripCard):
        for col in self._columns.values():
            if card in col._cards:
                return col
        return None

    def _find_column_for_widget(self, widget: QWidget | None):
        if widget is None:
            return None
        for col in self._columns.values():
            if self._widget_is_child(col, widget):
                return col
        return None

    def _widget_is_child(self, parent: QWidget, child: QWidget) -> bool:
        while child is not None:
            if child is parent:
                return True
            child = child.parentWidget()
        return False

    # ── Drag-Drop: accept drops on columns ──────────────────────────────────

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasText():
            return
        trip_id_str = event.mimeData().text()
        if not trip_id_str:
            return
        try:
            trip_id = int(trip_id_str)
        except ValueError:
            return

        target_col = self._find_column_for_widget(self.childAt(event.position().toPoint()))
        if target_col is None:
            return
        self._complete_card_drop(trip_id, target_col, event)

    def _on_card_dropped_on_column(self, trip_id: int) -> None:
        target_col = self.sender()
        if target_col is None:
            return
        self._complete_card_drop(trip_id, target_col, drop_event=None)

    def _complete_card_drop(
        self,
        trip_id: int,
        target_col,
        drop_event=None,
    ) -> None:
        card = self._find_card_by_trip_id(trip_id)
        if card is None:
            return
        source_col = self._find_column_for_card(card)
        if source_col is None or source_col == target_col:
            return
        if drop_event is not None:
            with contextlib.suppress(Exception):
                drop_event.accept()
        self._handle_transition(
            trip_id,
            source_col.status_key,
            target_col.status_key,
            card,
            source_col,
            target_col,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Status transition
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_transition(
        self,
        trip_id: int,
        old_status: str,
        new_status: str,
        card,
        source_col,
        target_col,
    ) -> None:
        column_order = ["Planned", "Loading", "In Transit", "Delivered", "Cancelled"]
        old_idx = column_order.index(old_status) if old_status in column_order else -1
        new_idx = column_order.index(new_status) if new_status in column_order else -1
        is_backward = new_idx < old_idx

        # Validate transition before showing any dialog
        valid_targets = VALID_TRANSITIONS.get(old_status, [])
        if new_status not in valid_targets:
            self._show_toast(
                f"Illegal transition: {old_status} \u2192 {new_status}",
                "error",
            )
            return

        if is_backward:
            reply = QMessageBox.question(
                self,
                t("dispatch_board.confirm_title"),
                t(
                    "dispatch_board.confirm_backward",
                    old_status=old_status,
                    new_status=new_status,
                    trip_id=trip_id,
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        card_backup = dict(card.trip_data)

        new_card = QtTripCard(
            target_col,
            {**card_backup, "status": new_status},
            on_click=self._on_card_click,
            on_drag_start=self._on_drag_start,
            on_assign_truck=self._on_assign_truck,
            on_assign_driver=self._on_assign_driver,
            on_select_changed=self._on_card_select_changed,
            on_assign_both=self._on_assign_both,
            on_status_change=self._on_status_change_card,
            on_navigate_to_generators=self._on_navigate_to_generators,
        )
        target_col.add_card(new_card)

        if source_col:
            # Remove from selection if selected (card is about to be destroyed)
            if card in self._selected_cards:
                self._selected_cards.remove(card)
                self._update_bulk_toolbar()
            source_col.remove_card(card)

        new_card.trip_data["status"] = new_status

        try:
            if getattr(self, "_db", None) is None and self._dispatch_service is not None:
                # Remote mode: the backend validates the transition.
                result = self._dispatch_service.transition_status(trip_id, new_status)
                if result is None or (
                    isinstance(result, dict) and result.get("trip") is None
                ):
                    raise RuntimeError(f"Status transition failed for trip {trip_id}")
            elif self.ops:
                ok = self.ops.force_trip_status(trip_id, new_status)
                if not ok:
                    raise RuntimeError(f"Status transition failed for trip {trip_id}")
            else:
                # Fallback: use TripService directly when no OperationsEngine.
                # Previously this used TripStatusEngine.transition() directly.
                self._trip_service.update(trip_id, TripUpdate(status=new_status))
                self._event_bus.publish(TRIP_STATUS_CHANGED, {
                    "trip_id": trip_id,
                    "old_status": old_status,
                    "new_status": new_status,
                })
            self._show_toast(
                t("dispatch_board.transition_success").format(new_status=new_status),
                "success",
            )
        except Exception:
            try:
                target_col.remove_card(new_card)
                new_card.deleteLater()
            except Exception:
                pass

            restored = QtTripCard(
                source_col if source_col else self._columns.get(old_status, self),
                {**card_backup, "status": old_status},
                on_click=self._on_card_click,
                on_drag_start=self._on_drag_start,
                on_assign_truck=self._on_assign_truck,
                on_assign_driver=self._on_assign_driver,
                on_select_changed=self._on_card_select_changed,
                on_assign_both=self._on_assign_both,
                on_status_change=self._on_status_change_card,
                on_navigate_to_generators=self._on_navigate_to_generators,
            )
            if source_col:
                source_col.add_card(restored)

            self._show_toast(
                t("dispatch_board.transition_error").format(
                    old_status=old_status, new_status=new_status
                ),
                "error",
            )

    # ══════════════════════════════════════════════════════════════════════════
    # Toast notifications
    # ══════════════════════════════════════════════════════════════════════════

    def _show_toast(self, message: str, variant: str = "success") -> None:
        icons = {"success": "\u2705", "error": "\u274c", "warning": "\u26a0\ufe0f"}
        icon = icons.get(variant, "\u2705")
        toast = Toast(self, message=message, icon=icon)
        toast.show_at(self, QPoint(self.width() // 2 - 100, 80))

    def _remote_readonly_guard(self) -> bool:
        """Return ``True`` when the board is in remote mode (assignments
        unavailable) and show a toast explaining so."""
        if getattr(self, "_db", None) is not None or self._dispatch_service is None:
            return False
        self._show_toast(
            t("dispatch_board.remote_assign_unavailable",
              default="Assignments are not available in remote mode"),
            "warning",
        )
        return True

    # ── Remote-mode assignment helpers ───────────────────────────────────
    # Assignment now has a backend surface (PATCH /dispatch/trips/{id}/assignment
    # + POST /dispatch/assignments/bulk), so the entry points below call the
    # remote dispatch service directly instead of ``_remote_readonly_guard``.

    def _is_remote_mode(self) -> bool:
        """``True`` when the board is running against the backend (no local DB)."""
        return getattr(self, "_db", None) is None and self._dispatch_service is not None

    def _refresh_after_remote_assignment(self) -> None:
        """Reload the board data after a successful remote assignment."""
        try:
            self._start_load()
        except Exception:
            logger.warning(
                "dispatch: board refresh after remote assignment failed", exc_info=True,
            )

    def _remote_active_trucks(self) -> list:
        """Return the active truck list for assignment dropdowns in remote mode.

        Uses the API client when available (mirrors ``RemoteDriverService``
        filtering); degrades to ``[]`` when no client is injected or the call
        fails, so the dropdown shows its empty state instead of crashing.
        """
        api = getattr(self, "_api_client", None)
        if api is None:
            return []
        try:
            resp = api.list_trucks()
            items = resp.get("items", []) if isinstance(resp, dict) else (resp or [])
            return [
                t for t in items
                if isinstance(t, dict) and t.get("is_active", t.get("active_status", 0))
            ]
        except Exception:
            logger.warning("dispatch: remote active trucks fetch failed", exc_info=True)
            return []

    def _remote_active_drivers(self) -> list:
        """Return the active driver list for assignment dropdowns in remote mode.

        Uses the API client when available; degrades to ``[]`` when no client
        is injected or the call fails.
        """
        api = getattr(self, "_api_client", None)
        if api is None:
            return []
        try:
            resp = api.list_drivers(limit=1000)
            items = resp.get("items", []) if isinstance(resp, dict) else (resp or [])
            return [
                d for d in items
                if isinstance(d, dict) and d.get("is_active", d.get("active_status", 0))
            ]
        except Exception:
            logger.warning("dispatch: remote active drivers fetch failed", exc_info=True)
            return []

    # ══════════════════════════════════════════════════════════════════════════
    # Assignment (single trip)
    # ══════════════════════════════════════════════════════════════════════════

    def _on_assign_truck(self, card, clear: bool = False) -> None:
        if clear:
            self._clear_truck_assignment(card)
            return

        def fetch_trucks():
            if self._is_remote_mode():
                # Remote mode: no local fleet repo / conflict service — list
                # active trucks from the API (when available) without
                # conflict/block data.
                active_trucks = self._remote_active_trucks()
                items = []
                for truck in active_trucks:
                    items.append({
                        "id": truck.get("id"),
                        "label": truck.get("plate_number", ""),
                        "sublabel": truck.get("model", ""),
                        "available": True,
                        "status_text": "",
                        "plate": truck.get("plate_number", ""),
                    })
                items.sort(key=lambda x: x["label"])
                return items
            active_trucks = self._fleet_repo.get_active_trucks()
            card_data = card.trip_data

            truck_conflicts: dict[str, list] = {}
            truck_blocks: dict[str, list] = {}
            now = datetime.now()
            for truck_entry in active_trucks:
                plate = truck_entry.get("plate_number", "")
                truck_id = truck_entry.get("id")

                conflicts = self._conflict_service.check_conflicts({
                    "truck_plate": plate,
                    "start_date": card_data.get("departure_date", ""),
                    "end_date": card_data.get("eta", ""),
                    "distance_km": 0,
                })
                conf = [c for c in conflicts if c.get("trip_id") != card_data.get("trip_id_num")]
                if conf:
                    truck_conflicts[plate] = conf

                blocks = []
                if truck_entry.get("status") == "In Service":
                    blocks.append(t("dispatch_board.resource_in_service"))
                try:
                    insurance = truck_entry.get("insurance_expiry", "")
                    if insurance:
                        exp = datetime.strptime(insurance, "%Y-%m-%d")
                        if now.date() > exp.date():
                            blocks.append(t("dispatch_board.resource_insurance_expired"))
                except Exception:
                    pass
                try:
                    inspection = truck_entry.get("inspection_expiry", "")
                    if inspection:
                        exp = datetime.strptime(inspection, "%Y-%m-%d")
                        if now.date() > exp.date():
                            blocks.append(t("dispatch_board.resource_inspection_expired"))
                except Exception:
                    pass
                try:
                    maint_due = truck_entry.get("maintenance_due")
                    mileage = truck_entry.get("mileage")
                    if maint_due is not None and mileage is not None:
                        if float(mileage) >= float(maint_due):
                            blocks.append(t("dispatch_board.resource_maintenance_due"))
                except Exception:
                    pass
                if blocks:
                    truck_blocks[plate] = blocks

            items = []
            for truck in active_trucks:
                plate = truck.get("plate_number", "")
                model = truck.get("model", "")
                truck_id = truck.get("id")

                conflicting = truck_conflicts.get(plate)
                blocked = truck_blocks.get(plate)
                available = not conflicting and not blocked

                if blocked:
                    status_text = t("dispatch_board.assign_truck_blocked").format(
                        reason=", ".join(blocked)
                    )
                elif conflicting:
                    trip_ref = conflicting[0].get("trip_id", "")
                    overlap = conflicting[0].get("overlap_description", "")
                    status_text = t("dispatch_board.unavailable_overlap").format(
                        f"{t('dispatch_board.trip_id_prefix')}{trip_ref} ({overlap})"
                    )
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

        dropdown = QtAssignmentDropdown(
            self,
            anchor_widget=card,
            title=t("dispatch_board.select_truck"),
            fetch_func=fetch_trucks,
            on_select=on_select,
        )
        dropdown.show_anchored(card)

    def _on_assign_driver(self, card, clear: bool = False) -> None:
        if clear:
            self._clear_driver_assignment(card)
            return

        def fetch_drivers():
            if self._is_remote_mode():
                # Remote mode: no local driver repo / conflict service — list
                # active drivers from the API (when available) without
                # conflict/hours/block data.
                active_drivers = self._remote_active_drivers()
                items = []
                for d in active_drivers:
                    name = d.get("name", "")
                    items.append({
                        "id": d.get("id"),
                        "label": name,
                        "sublabel": d.get("license_category", ""),
                        "available": True,
                        "status_text": "",
                        "name": name,
                    })
                items.sort(key=lambda x: x["label"])
                return items
            active_drivers = self._driver_repo.get_active_drivers()
            card_data = card.trip_data

            driver_conflicts: dict[int, list] = {}
            driver_blocks: dict[int, list] = {}
            driver_hours: dict[int, tuple] = {}
            now = datetime.now()
            cutoff_7 = date.today() - timedelta(days=7)
            if self._db is None:
                logger.warning("TachoDriverActivityRepository requires local database - not available in remote mode")
                tacho_repo = None
            else:
                tacho_repo = self._tacho_repo if self._tacho_repo is not None else TachoDriverActivityRepository(self._db)

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

                blocks = []
                try:
                    license_expiry = d.get("license_expiry", "")
                    if license_expiry:
                        exp = datetime.strptime(license_expiry, "%Y-%m-%d")
                        if now.date() > exp.date():
                            blocks.append(t("dispatch_board.resource_license_expired"))
                except Exception:
                    pass
                try:
                    medical_expiry = d.get("medical_expiry", "")
                    if medical_expiry:
                        exp = datetime.strptime(medical_expiry, "%Y-%m-%d")
                        if now.date() > exp.date():
                            blocks.append(t("dispatch_board.resource_medical_expired"))
                except Exception:
                    pass

                weekly_h = 0.0
                violations = 0
                try:
                    records = tacho_repo.get_by_driver(int(did or 0), cutoff_7)
                    weekly_h = sum(r.get("driving_minutes", 0) or 0 for r in records) / 60
                    violations = sum(
                        len(json.loads(r.get("violations") or "[]"))
                        for r in records
                    )
                except Exception:
                    pass
                if weekly_h > 56:
                    blocks.append(t("dispatch_board.driver_hours_exceeded", hours=weekly_h, max_h=56))
                driver_hours[did] = (weekly_h, violations)

                if blocks:
                    driver_blocks[did] = blocks

            items = []
            for driver in active_drivers:
                driver_id = driver.get("id")
                name = driver.get("name", "")
                license_cat = driver.get("license_category", "")
                wh, vc = driver_hours.get(driver_id, (0, 0))

                conflicting = driver_conflicts.get(driver_id)
                blocked = driver_blocks.get(driver_id)
                available = not conflicting and not blocked

                hours_label = t("dispatch_board.driver_hours_weekly", hours=wh, max_h=56)
                sublabel = f"{license_cat} | {hours_label}"
                if vc > 0:
                    sublabel += f" | \u26a0 {vc}"

                if blocked:
                    status_text = t("dispatch_board.assign_driver_blocked").format(
                        reason=", ".join(blocked)
                    )
                elif conflicting:
                    trip_ref = conflicting[0].get("trip_id", "")
                    status_text = t("dispatch_board.unavailable_overlap").format(
                        f"{t('dispatch_board.trip_id_prefix')}{trip_ref}"
                    )
                else:
                    status_text = ""

                items.append({
                    "id": driver_id,
                    "label": name,
                    "sublabel": sublabel,
                    "available": available,
                    "status_text": status_text,
                    "name": name,
                })

            items.sort(key=lambda x: (not x["available"], x["label"]))
            return items

        def on_select(driver_id):
            self._assign_driver_to_trip(card, driver_id)

        dropdown = QtAssignmentDropdown(
            self,
            anchor_widget=card,
            title=t("dispatch_board.select_driver"),
            fetch_func=fetch_drivers,
            on_select=on_select,
        )
        dropdown.show_anchored(card)

    def _score_items(self, truck_items: list, driver_items: list, card_data: dict) -> None:
        if self._db is None and self._dispatch_service is not None:
            # Remote mode: next-available-slot scoring comes from the backend
            # (GET /dispatch/slots/next).  Tacho/fuel/health inputs are not
            # available remotely, so only the slot term contributes to the
            # score (same formula as the local slot branch below).
            now = datetime.now()
            for item in truck_items:
                if not item["available"]:
                    continue
                score = 0
                slot = self._dispatch_service.get_next_available_slot(
                    truck_id=item.get("id"),
                )
                start_at = slot.get("start_at") if isinstance(slot, dict) else None
                if start_at:
                    try:
                        nf_dt = datetime.fromisoformat(start_at)
                        hours_until = max(0, (nf_dt - now).total_seconds() / 3600)
                        score += max(0, 40 - hours_until * 2)
                    except ValueError:
                        score += 40
                else:
                    score += 40
                item["score"] = round(score, 1)
            for item in driver_items:
                if not item["available"]:
                    continue
                score = 0
                slot = self._dispatch_service.get_next_available_slot(
                    driver_id=item.get("id"),
                )
                start_at = slot.get("start_at") if isinstance(slot, dict) else None
                if start_at:
                    try:
                        nf_dt = datetime.fromisoformat(start_at)
                        hours_until = max(0, (nf_dt - now).total_seconds() / 3600)
                        score += max(0, 40 - hours_until * 2)
                    except ValueError:
                        score += 40
                else:
                    score += 40
                item["score"] = round(score, 1)
            return
        now = datetime.now()

        for item in truck_items:
            if not item["available"]:
                continue
            score = 0
            truck_id = item.get("id")
            truck_plate = item.get("label", "")
            try:
                next_free = self._conflict_service.get_next_available_slot(
                    truck_plate=truck_plate, truck_id=truck_id
                )
                if next_free:
                    try:
                        nf_dt = datetime.strptime(next_free, "%d/%m/%Y %H:%M")
                        hours_until = max(0, (nf_dt - now).total_seconds() / 3600)
                        score += max(0, 40 - hours_until * 2)
                    except Exception:
                        logger.debug("Could not parse next_free date: %s", next_free, exc_info=True)
                        score += 40
                else:
                    score += 40
            except Exception:
                logger.debug("Could not compute next_free slot for truck", exc_info=True)
                score += 40

            try:
                truck = self._fleet_repo.get_by_id(int(truck_id)) if truck_id else None
                if truck:
                    fuel = float(truck.get("fuel_consumption") or 34)
                    score += max(0, 20 - (fuel - 20) * 1.5)
            except Exception:
                logger.debug("Failed to fetch truck fuel consumption", exc_info=True)
            try:
                health = self._fleet_repo.get_truck_health(int(truck_id)) if truck_id else None
                if health:
                    score += (float(health.get("score", 0)) / 100) * 10
            except Exception:
                logger.debug("Failed to fetch truck health score", exc_info=True)
            item["score"] = round(score, 1)

        for item in driver_items:
            if not item["available"]:
                continue
            score = 0
            driver_id = item.get("id")
            try:
                next_free = self._conflict_service.get_next_available_slot_for_driver(
                    int(driver_id)
                ) if driver_id else None
                if next_free:
                    try:
                        nf_dt = datetime.strptime(next_free, "%d/%m/%Y %H:%M")
                        hours_until = max(0, (nf_dt - now).total_seconds() / 3600)
                        score += max(0, 40 - hours_until * 2)
                    except Exception:
                        score += 40
                else:
                    score += 40
            except Exception:
                score += 40
            try:
                if self._db is None:
                    logger.warning("TachoDriverActivityRepository requires local database - not available in remote mode")
                    tacho_repo = None
                else:
                    tacho_repo = self._tacho_repo if self._tacho_repo is not None else TachoDriverActivityRepository(self._db)
                from datetime import date, timedelta
                records = tacho_repo.get_by_driver(
                    int(driver_id), date.today() - timedelta(days=7)
                )
                violations = sum(
                    len(json.loads(r.get("violations") or "[]")) for r in records
                )
                score += max(0, 10 - violations * 3)
            except Exception:
                pass
            item["score"] = round(score, 1)

    def _on_assign_both(self, card) -> None:
        from ui.dialogs.paired_assignment_dialog import QtPairedAssignmentDialog

        card_data = card.trip_data
        if self._is_remote_mode():
            # Remote mode: no local fleet/driver repos or conflict service —
            # list active resources from the API (when available).  Scoring is
            # skipped (no local tacho/conflict data); the common tail below
            # still opens the paired-assignment dialog with remote callbacks.
            truck_items = []
            for trk in self._remote_active_trucks():
                truck_items.append({
                    "id": trk.get("id"),
                    "label": trk.get("plate_number", ""),
                    "sublabel": trk.get("model", ""),
                    "available": True,
                    "status_text": "", "score": 0,
                })
            driver_items = []
            for d in self._remote_active_drivers():
                name = d.get("name", "")
                driver_items.append({
                    "id": d.get("id"),
                    "label": name,
                    "sublabel": d.get("license_category", ""),
                    "available": True,
                    "status_text": "", "score": 0,
                })
        else:
            active_trucks = self._fleet_repo.get_active_trucks()
            active_drivers = self._driver_repo.get_active_drivers()
            now = datetime.now()
            cutoff_7 = date.today() - timedelta(days=7)
            tacho_repo = (
                None
                if self._db is None
                else (
                    self._tacho_repo
                    if self._tacho_repo is not None
                    else TachoDriverActivityRepository(self._db)
                )
            )

            truck_items = []
            for trk in active_trucks:
                plate = trk.get("plate_number", "")
                model = trk.get("model", "")
                tid = trk.get("id")
                conflicts = self._conflict_service.check_conflicts({
                    "truck_plate": plate,
                    "start_date": card_data.get("departure_date", ""),
                    "end_date": card_data.get("eta", ""),
                    "distance_km": 0,
                })
                conf = [c for c in conflicts if c.get("trip_id") != card_data.get("trip_id_num")]
                blocks = []
                if trk.get("status") == "In Service":
                    blocks.append(t("dispatch_board.resource_in_service"))
                try:
                    ins_ = trk.get("insurance_expiry", "")
                    if ins_:
                        exp = datetime.strptime(ins_, "%Y-%m-%d")
                        if now.date() > exp.date():
                            blocks.append(t("dispatch_board.resource_insurance_expired"))
                except Exception:
                    logger.warning("Failed to validate insurance expiry for truck %s", plate, exc_info=True)
                try:
                    insp_ = trk.get("inspection_expiry", "")
                    if insp_:
                        exp = datetime.strptime(insp_, "%Y-%m-%d")
                        if now.date() > exp.date():
                            blocks.append(t("dispatch_board.resource_inspection_expired"))
                except Exception:
                    logger.warning("Failed to validate inspection expiry for truck %s", plate, exc_info=True)
                try:
                    md = trk.get("maintenance_due")
                    mi = trk.get("mileage")
                    if md is not None and mi is not None and float(mi) >= float(md):
                        blocks.append(t("dispatch_board.resource_maintenance_due"))
                except Exception:
                    logger.warning("Failed to validate maintenance due for truck %s", plate, exc_info=True)
                avail = not conf and not blocks
                st = ""
                if blocks:
                    st = ", ".join(blocks)
                elif conf:
                    st = t("dispatch_board.unavailable_overlap").format(
                        f"{t('dispatch_board.trip_id_prefix')}{conf[0].get('trip_id','?')}")
                truck_items.append({
                    "id": tid, "label": plate, "sublabel": model,
                    "available": avail, "status_text": st, "score": 0,
                })

            driver_items = []
            for d in active_drivers:
                did = d.get("id")
                name = d.get("name", "")
                lcat = d.get("license_category", "")
                conflicts = self._conflict_service.check_conflicts({
                    "driver_id": did,
                    "start_date": card_data.get("departure_date", ""),
                    "end_date": card_data.get("eta", ""),
                    "distance_km": 0,
                })
                conf = [c for c in conflicts if c.get("trip_id") != card_data.get("trip_id_num")]
                blocks = []
                try:
                    le = d.get("license_expiry", "")
                    if le:
                        exp = datetime.strptime(le, "%Y-%m-%d")
                        if now.date() > exp.date():
                            blocks.append(t("dispatch_board.resource_license_expired"))
                except Exception:
                    pass
                try:
                    me = d.get("medical_expiry", "")
                    if me:
                        exp = datetime.strptime(me, "%Y-%m-%d")
                        if now.date() > exp.date():
                            blocks.append(t("dispatch_board.resource_medical_expired"))
                except Exception:
                    pass
                weekly_h = 0.0
                try:
                    records = tacho_repo.get_by_driver(int(did or 0), cutoff_7)
                    weekly_h = sum(r.get("driving_minutes", 0) or 0 for r in records) / 60
                except Exception:
                    pass
                if weekly_h > 56:
                    blocks.append(t("dispatch_board.driver_hours_exceeded", hours=weekly_h, max_h=56))
                hours_label = t("dispatch_board.driver_hours_weekly", hours=weekly_h, max_h=56)
                avail = not conf and not blocks
                st = ""
                if blocks:
                    st = ", ".join(blocks)
                elif conf:
                    st = t("dispatch_board.unavailable_overlap").format(
                        f"{t('dispatch_board.trip_id_prefix')}{conf[0].get('trip_id','?')}")
                driver_items.append({
                    "id": did, "label": name, "sublabel": f"{lcat} | {hours_label}",
                    "available": avail, "status_text": st, "score": 0,
                })

        self._score_items(truck_items, driver_items, card_data)
        truck_items.sort(key=lambda x: (-x.get("score", 0), x["label"]))
        driver_items.sort(key=lambda x: (-x.get("score", 0), x["label"]))

        paired_hint = ""
        try:
            driver_tname = self._dta_service.get_driver_name_for_truck(
                card_data.get("truck_id")
            ) if card_data.get("truck_id") else None
            if driver_tname:
                paired_hint = t("dispatch_board.pair_suggestion").format(
                    driver=driver_tname, truck=card_data.get("truck_plate", "?")
                )
        except Exception:
            pass

        def do_assign_both(truck_id, driver_id):
            self._assign_both_to_trip(card, truck_id, driver_id)

        def do_assign_truck_only(truck_id):
            self._assign_truck_to_trip(card, truck_id)

        def do_assign_driver_only(driver_id):
            self._assign_driver_to_trip(card, driver_id)

        QtPairedAssignmentDialog(
            self, card_data,
            truck_items, driver_items,
            paired_hint=paired_hint,
            on_assign_both=do_assign_both,
            on_assign_truck=do_assign_truck_only,
            on_assign_driver=do_assign_driver_only,
        ).show()

    def _assign_both_to_trip(self, card, truck_id, driver_id) -> None:
        if self._is_remote_mode():
            # Remote mode: the PATCH assignment endpoint sets both fields in
            # one call and records the driver↔truck pairing server-side.
            try:
                trip_id = card.trip_data.get("trip_id_num")
                result = self._dispatch_service.assign_trip(
                    trip_id, truck_id=truck_id, driver_id=driver_id,
                )
                if result is None or (
                    isinstance(result, dict) and result.get("trip") is None
                ):
                    raise RuntimeError(t("dispatch_board.assignment_failed",
                                          default="Assignment failed"))
                self._refresh_after_remote_assignment()
                logger.info(
                    "Assigned truck %s + driver %s to trip %d (remote)",
                    truck_id, driver_id, trip_id,
                )
            except Exception as e:
                logger.error("Failed paired assignment: %s", e)
                card.show_error("both", str(e))
            return
        rolled_back_truck = False
        try:
            if truck_id is not None:
                self._assign_truck_to_trip(card, truck_id)
                rolled_back_truck = True
            if driver_id is not None:
                self._assign_driver_to_trip(card, driver_id)
            if truck_id is not None and driver_id is not None:
                with contextlib.suppress(Exception):
                    self._dta_service.assign_driver_to_truck(driver_id, truck_id)
        except Exception as e:
            if rolled_back_truck and truck_id is not None:
                with contextlib.suppress(Exception):
                    self._clear_truck_assignment(card)
            card.show_error("both", str(e))

    def _assign_truck_to_trip(self, card, truck_id: int) -> None:
        try:
            trip_id = card.trip_data.get("trip_id_num")
            if self._is_remote_mode():
                # Remote mode: PATCH the assignment via the backend; the
                # updated trip (with resolved plate) comes back in the result.
                result = self._dispatch_service.assign_trip(trip_id, truck_id=truck_id)
                if result is None or (
                    isinstance(result, dict) and result.get("trip") is None
                ):
                    raise RuntimeError(t("dispatch_board.truck_not_found"))
                trip = result.get("trip") if isinstance(result, dict) else None
                plate = ""
                if isinstance(trip, dict):
                    plate = (
                        trip.get("truck_plate", "")
                        or trip.get("truck_number", "")
                        or ""
                    )
                card.update_truck(plate, truck_id)
                self._refresh_after_remote_assignment()
                logger.info("Assigned truck %s to trip %d (remote)", truck_id, trip_id)
                return
            truck = self._fleet_repo.get_by_id(truck_id)
            if not truck:
                raise ValueError(t("dispatch_board.truck_not_found"))
            plate = truck.get("plate_number", "")
            self._trip_service.update(trip_id, TripUpdate(truck_plate=plate, truck_id=truck_id))
            card.update_truck(plate, truck_id)
            self._event_bus.publish(TRIP_ASSIGNED, {
                "trip_id": trip_id,
                "truck_id": truck_id,
            })
            logger.info("Assigned truck %s to trip %d", plate, trip_id)
        except Exception as e:
            logger.error("Failed to assign truck: %s", e)
            card.show_error("truck", str(e))

    def _assign_driver_to_trip(self, card, driver_id: int) -> None:
        try:
            trip_id = card.trip_data.get("trip_id_num")
            if self._is_remote_mode():
                # Remote mode: PATCH the assignment via the backend; the
                # updated trip (with resolved name) comes back in the result.
                result = self._dispatch_service.assign_trip(trip_id, driver_id=driver_id)
                if result is None or (
                    isinstance(result, dict) and result.get("trip") is None
                ):
                    raise RuntimeError(t("dispatch_board.driver_not_found"))
                trip = result.get("trip") if isinstance(result, dict) else None
                name = ""
                if isinstance(trip, dict):
                    name = trip.get("driver_name", "") or ""
                card.update_driver(name, driver_id)
                self._refresh_after_remote_assignment()
                logger.info("Assigned driver %s to trip %d (remote)", driver_id, trip_id)
                return
            driver = self._driver_repo.get_by_id(driver_id)
            if not driver:
                raise ValueError(t("dispatch_board.driver_not_found"))
            name = driver.get("name", "")
            self._trip_service.update(trip_id, TripUpdate(driver_id=driver_id, driver_name=name))
            card.update_driver(name, driver_id)
            self._event_bus.publish(TRIP_ASSIGNED, {
                "trip_id": trip_id,
                "driver_id": driver_id,
            })
            logger.info("Assigned driver %s to trip %d", name, trip_id)
        except Exception as e:
            logger.error("Failed to assign driver: %s", e)
            card.show_error("driver", str(e))

    def _clear_truck_assignment(self, card) -> None:
        try:
            trip_id = card.trip_data.get("trip_id_num")
            if self._is_remote_mode():
                result = self._dispatch_service.assign_trip(trip_id, truck_id=None)
                if result is None or (
                    isinstance(result, dict) and result.get("trip") is None
                ):
                    raise RuntimeError(t("dispatch_board.truck_not_found"))
                card.update_truck("", None)
                self._refresh_after_remote_assignment()
                logger.info("Cleared truck assignment for trip %d (remote)", trip_id)
                return
            self._trip_service.update(trip_id, TripUpdate(truck_plate="", truck_id=None))
            card.update_truck("", None)
            logger.info("Cleared truck assignment for trip %d", trip_id)
        except Exception as e:
            logger.error("Failed to clear truck: %s", e)
            card.show_error("truck", str(e))

    def _clear_driver_assignment(self, card) -> None:
        try:
            trip_id = card.trip_data.get("trip_id_num")
            if self._is_remote_mode():
                result = self._dispatch_service.assign_trip(trip_id, driver_id=None)
                if result is None or (
                    isinstance(result, dict) and result.get("trip") is None
                ):
                    raise RuntimeError(t("dispatch_board.driver_not_found"))
                card.update_driver("", None)
                self._refresh_after_remote_assignment()
                logger.info("Cleared driver assignment for trip %d (remote)", trip_id)
                return
            self._trip_service.update(trip_id, TripUpdate(driver_id=None, driver_name=""))
            card.update_driver("", None)
            logger.info("Cleared driver assignment for trip %d", trip_id)
        except Exception as e:
            logger.error("Failed to clear driver: %s", e)
            card.show_error("driver", str(e))

    # ══════════════════════════════════════════════════════════════════════════
    # Delay evaluation
    # ══════════════════════════════════════════════════════════════════════════

    def _evaluate_all_delays(self) -> None:
        if getattr(self, '_destroyed', False):
            return
        if self._dispatch_service is None:
            return
        for col in self._columns.values():
            for card in col._cards:
                card_data = card.trip_data
                if self._db is None:
                    # Remote mode: delay evaluation runs server-side
                    # (GET /dispatch/trips/{id}/delay).  The remote service
                    # returns the delay evaluation result (dict-like, also
                    # unpackable as a tuple); the delay indicator is set from
                    # it and the alert creation call is fired for late trips.
                    trip_id = card_data.get("trip_id_num") or card_data.get("trip_id")
                    if trip_id is None:
                        continue
                    result = self._dispatch_service.evaluate_trip_delay(trip_id)
                    if isinstance(result, dict):
                        is_delayed = bool(result.get("delayed", False))
                        minutes = int(round((result.get("delay_hours") or 0.0) * 60))
                    else:
                        is_delayed, minutes = False, 0
                    card.set_delayed(is_delayed, minutes)
                    if is_delayed:
                        self._dispatch_service.create_delay_alert(trip_id)
                    continue
                is_delayed, minutes = self._dispatch_service.evaluate_trip_delay(card_data)
                card.set_delayed(is_delayed, minutes)
                if is_delayed:
                    self._dispatch_service.create_delay_alert(card_data, minutes)

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
        from utils.dates import parse_date as _pd
        return _pd(date_str, "%d/%m/%Y")

    def _create_delay_alert(self, card, minutes_overdue: int) -> None:
        trip_id = card.trip_data.get("trip_id_num")
        if not trip_id:
            return

        existing = self._alert_mgr.get_alerts(
            alert_type=AlertType.TRIP_DELAY,
            resolved=False,
            limit=1000,
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
            },
        )
        logger.info("Created delay alert for trip %d (%d minutes overdue)", trip_id, minutes_overdue)

    # ══════════════════════════════════════════════════════════════════════════
    # Export
    # ══════════════════════════════════════════════════════════════════════════

    def _export_csv(self) -> None:
        from ui.dispatch.board_export import export_csv
        export_csv(self, self._all_card_data, self._show_toast)

    def _export_pdf(self) -> None:
        from ui.dispatch.board_export import export_pdf
        export_pdf(self, self._all_card_data, self._show_toast)
