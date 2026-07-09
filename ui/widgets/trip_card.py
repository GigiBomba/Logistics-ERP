"""QtTripCard — PySide6 trip card widget for the dispatch board.

Replaces ``ui/widgets/trip_card.py`` (CTkFrame). A self-contained card
showing trip ID, status chip, truck/driver assignment rows, route,
dates, alerts, and live GPS position. Supports click-to-select with
Ctrl+modifier, drag initiation, clickable assignment labels, and
inline error messages with auto-dismiss.

All styling is driven by the global QSS theme via the ``role="card"``
property selector and per-widget ``fontRole`` properties. Minimal inline
stylesheets are used only for dynamic state (hover, selection, delayed).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.theme import COLORS, S

logger = logging.getLogger(__name__)


class QtTripCard(QFrame):
    """Dispatch board trip card with status chip, assignments, and live position.

    A QFrame-based card that reproduces the CTkFrame ``TripCard`` API for the
    PySide6 migration. Appearance is controlled by the global QSS theme via
    the ``role="card"`` property, with dynamic inline overrides for hover
    and selection states.

    Layout (vertical content area, left accent bar):
        Row 1 — trip ID + status chip + delayed chip
        Row 2 — truck icon + truck plate (clickable) + clear button
        Row 3 — "⚡ Assign Both" link (clickable)
        Row 4 — driver icon + driver name (clickable) + clear button
        Row 5 — route text (origin → destination)
        Row 6 — departure / ETA dates
        Row 7 — alerts count banner (conditional)
        Row 8 — live position indicator (hidden by default)
    """

    CARD_BG = COLORS["bg_surface"]
    CARD_BG_HOVER = COLORS["bg_elevated"]
    CARD_BORDER = COLORS["border"]
    CARD_BORDER_HOVER = COLORS["accent"]
    LEFT_ACCENT_WIDTH = 4

    STATUS_COLORS = {
        "Planned": COLORS["chip_planned"],
        "Loading": COLORS["chip_loading"],
        "In Transit": COLORS["chip_transit"],
        "Delivered": COLORS["chip_delivered"],
        "Cancelled": COLORS["chip_cancelled"],
    }

    STATUS_TRANSLATION_KEYS = {
        "Planned": "dispatch_board.col_planned",
        "Loading": "dispatch_board.col_loading",
        "In Transit": "dispatch_board.col_in_transit",
        "Delivered": "dispatch_board.col_delivered",
        "Cancelled": "dispatch_board.col_cancelled",
    }

    DELAYED_COLOR = COLORS["danger"]
    DELAYED_BG = COLORS["danger_dim"]

    def __init__(
        self,
        parent: QWidget | None = None,
        trip_data: dict[str, Any] | None = None,
        on_click: Callable[[dict[str, Any]], None] | None = None,
        on_drag_start: Callable[[QWidget, QMouseEvent], None] | None = None,
        on_assign_truck: Callable[[QWidget], None] | None = None,
        on_assign_driver: Callable[[QWidget], None] | None = None,
        on_select_changed: Callable[[QWidget, bool], None] | None = None,
        on_assign_both: Callable[[QWidget], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self.setFrameShape(QFrame.StyledPanel)

        self.trip_data: dict[str, Any] = trip_data or {}
        self._on_click = on_click
        self._on_drag_start = on_drag_start
        self._on_assign_truck = on_assign_truck
        self._on_assign_driver = on_assign_driver
        self._on_select_changed = on_select_changed
        self._on_assign_both = on_assign_both

        # ── State flags ───────────────────────────────────────────────────
        self._hovered = False
        self._selected = False
        self._delayed = False
        self._drag_start_pos: QPoint | None = None
        self._dragging = False

        # ── Widget references (populated by _build_card) ──────────────────
        self._accent_bar: QFrame | None = None
        self._content_widget: QWidget | None = None
        self._chip_frame: QFrame | None = None
        self._chip_lbl: QLabel | None = None
        self._delayed_chip: QFrame | None = None
        self._truck_lbl: QLabel | None = None
        self._truck_clear_btn: QLabel | None = None
        self._driver_lbl: QLabel | None = None
        self._driver_clear_btn: QLabel | None = None
        self._both_lbl: QLabel | None = None
        self._route_lbl: QLabel | None = None
        self._date_lbl: QLabel | None = None
        self._alert_frame: QFrame | None = None
        self._live_row: QWidget | None = None
        self._live_speed: QLabel | None = None
        self._error_lbl: QLabel | None = None
        self._error_timer: QTimer | None = None

        self._build_card()

        if on_click:
            self.setCursor(Qt.PointingHandCursor)

    # ── Card construction ──────────────────────────────────────────────────

    def _build_card(self) -> None:
        """Build the complete card UI from ``self.trip_data``."""
        d = self.trip_data
        status = d.get("status", "Planned")
        accent_color = self.STATUS_COLORS.get(status, COLORS["chip_planned"])

        # Outer horizontal layout: accent bar | content
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # ── Left accent bar ─────────────────────────────────────────────
        self._accent_bar = QFrame()
        self._accent_bar.setFixedWidth(self.LEFT_ACCENT_WIDTH)
        self._accent_bar.setStyleSheet(
            f"background-color: {accent_color}; border: none; border-radius: 0px;"
        )
        outer_layout.addWidget(self._accent_bar)

        # ── Content area ────────────────────────────────────────────────
        self._content_widget = QWidget()
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(S["3"], S["2"], S["3"], S["2"])
        content_layout.setSpacing(S["1"])

        # Row 1 — trip ID + status chip + delayed chip
        row1 = QWidget()
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(S["1"])

        trip_id = d.get("trip_id", t("common.na"))
        id_lbl = QLabel(str(trip_id))
        id_lbl.setProperty("fontRole", "small")
        row1_layout.addWidget(id_lbl)

        row1_layout.addStretch(1)

        # Delayed chip (hidden by default)
        self._delayed_chip = QFrame()
        self._delayed_chip.setStyleSheet(
            f"background-color: {self.DELAYED_COLOR}; border-radius: 3px;"
        )
        delayed_chip_layout = QHBoxLayout(self._delayed_chip)
        delayed_chip_layout.setContentsMargins(S["1"], 1, S["1"], 1)
        delayed_chip_layout.setSpacing(0)
        delayed_lbl = QLabel(t("dispatch_board.delayed"))
        delayed_lbl.setProperty("fontRole", "label")
        delayed_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
        delayed_chip_layout.addWidget(delayed_lbl)
        if d.get("delayed", False):
            row1_layout.addWidget(self._delayed_chip)
        else:
            self._delayed_chip.hide()

        # Status chip
        self._chip_frame = QFrame()
        self._chip_frame.setStyleSheet(
            f"background-color: {accent_color}; border-radius: 3px;"
        )
        chip_frame_layout = QHBoxLayout(self._chip_frame)
        chip_frame_layout.setContentsMargins(S["1"], 1, S["1"], 1)
        chip_frame_layout.setSpacing(0)
        translation_key = self.STATUS_TRANSLATION_KEYS.get(status)
        self._chip_lbl = QLabel(
            t(translation_key if translation_key is not None else status)
        )
        self._chip_lbl.setProperty("fontRole", "label")
        self._chip_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
        chip_frame_layout.addWidget(self._chip_lbl)
        row1_layout.addWidget(self._chip_frame)

        content_layout.addWidget(row1)

        # Row 2 — truck icon + truck plate (clickable)
        truck_row = QWidget()
        truck_row.setSizePolicy(
            truck_row.sizePolicy().horizontalPolicy(),
            truck_row.sizePolicy().verticalPolicy(),
        )
        truck_row_layout = QHBoxLayout(truck_row)
        truck_row_layout.setContentsMargins(0, 0, 0, 0)
        truck_row_layout.setSpacing(S["1"])

        truck_icon = QLabel("\U0001f69a")
        truck_icon.setProperty("fontRole", "label")
        truck_icon.setStyleSheet(f"color: {COLORS['text_muted']};")
        truck_row_layout.addWidget(truck_icon)

        plate = d.get("truck_plate", "")
        plate_text = plate if plate else t("dispatch_board.assign_truck")
        plate_color = COLORS["text_primary"] if plate else COLORS["text_muted"]
        self._truck_lbl = QLabel(plate_text)
        self._truck_lbl.setProperty("fontRole", "small")
        self._truck_lbl.setStyleSheet(f"color: {plate_color};")
        self._truck_lbl.setCursor(Qt.PointingHandCursor)
        self._truck_lbl.mousePressEvent = self._on_truck_click  # type: ignore[assignment]
        truck_row_layout.addWidget(self._truck_lbl)

        truck_row_layout.addStretch(1)

        # Clear button (only if plate is set)
        if plate:
            self._truck_clear_btn = QLabel("\u2715")
            self._truck_clear_btn.setProperty("fontRole", "label")
            self._truck_clear_btn.setStyleSheet(f"color: {COLORS['text_muted']};")
            self._truck_clear_btn.setCursor(Qt.PointingHandCursor)
            self._truck_clear_btn.mousePressEvent = self._on_truck_clear  # type: ignore[assignment]
            truck_row_layout.addWidget(self._truck_clear_btn)

        content_layout.addWidget(truck_row)

        # Row 3 — "⚡ Assign Both" link (clickable)
        both_row = QWidget()
        both_row_layout = QHBoxLayout(both_row)
        both_row_layout.setContentsMargins(S["5"], 0, 0, 0)
        both_row_layout.setSpacing(0)

        self._both_lbl = QLabel("\u26a1 " + t("dispatch_board.assign_both"))
        self._both_lbl.setProperty("fontRole", "small")
        self._both_lbl.setStyleSheet(f"color: {COLORS['accent']};")
        self._both_lbl.setCursor(Qt.PointingHandCursor)
        self._both_lbl.mousePressEvent = self._on_both_click  # type: ignore[assignment]
        both_row_layout.addWidget(self._both_lbl)
        both_row_layout.addStretch(1)

        content_layout.addWidget(both_row)

        # Row 4 — driver icon + driver name (clickable)
        driver_row = QWidget()
        driver_row_layout = QHBoxLayout(driver_row)
        driver_row_layout.setContentsMargins(0, 0, 0, 0)
        driver_row_layout.setSpacing(S["1"])

        driver_icon = QLabel("\U0001f464")
        driver_icon.setProperty("fontRole", "label")
        driver_icon.setStyleSheet(f"color: {COLORS['text_muted']};")
        driver_row_layout.addWidget(driver_icon)

        driver = d.get("driver_name", "")
        driver_text = driver if driver else t("dispatch_board.assign_driver")
        driver_color = COLORS["text_primary"] if driver else COLORS["text_muted"]
        self._driver_lbl = QLabel(driver_text)
        self._driver_lbl.setProperty("fontRole", "small")
        self._driver_lbl.setStyleSheet(f"color: {driver_color};")
        self._driver_lbl.setCursor(Qt.PointingHandCursor)
        self._driver_lbl.mousePressEvent = self._on_driver_click  # type: ignore[assignment]
        driver_row_layout.addWidget(self._driver_lbl)

        driver_row_layout.addStretch(1)

        # Clear button (only if driver is set)
        if driver:
            self._driver_clear_btn = QLabel("\u2715")
            self._driver_clear_btn.setProperty("fontRole", "label")
            self._driver_clear_btn.setStyleSheet(f"color: {COLORS['text_muted']};")
            self._driver_clear_btn.setCursor(Qt.PointingHandCursor)
            self._driver_clear_btn.mousePressEvent = self._on_driver_clear  # type: ignore[assignment]
            driver_row_layout.addWidget(self._driver_clear_btn)

        content_layout.addWidget(driver_row)

        # Row 5 — route text (origin → destination)
        route_row = QWidget()
        route_row_layout = QHBoxLayout(route_row)
        route_row_layout.setContentsMargins(0, 0, 0, 0)
        route_row_layout.setSpacing(0)

        origin = d.get("origin", "?")
        destination = d.get("destination", "?")
        route_text = f"{origin} \u2192 {destination}"
        self._route_lbl = QLabel(route_text)
        self._route_lbl.setProperty("fontRole", "muted")
        self._route_lbl.setWordWrap(True)
        route_row_layout.addWidget(self._route_lbl)

        content_layout.addWidget(route_row)

        # Row 6 — departure / ETA dates
        date_row = QWidget()
        date_row_layout = QHBoxLayout(date_row)
        date_row_layout.setContentsMargins(0, 0, 0, 0)
        date_row_layout.setSpacing(0)

        departure = d.get("departure_date", "")
        eta = d.get("eta", "")
        date_parts: list[str] = []
        if departure:
            date_parts.append(f"\u25b6 {departure}")
        if eta:
            date_parts.append(f"\u25c0 {eta}")
        date_text = "  ".join(date_parts) if date_parts else ""
        if date_text:
            self._date_lbl = QLabel(date_text)
            self._date_lbl.setProperty("fontRole", "muted")
            date_row_layout.addWidget(self._date_lbl)
            content_layout.addWidget(date_row)

        # Row 7 — alerts count (conditional)
        alerts_count = d.get("alerts_count", 0)
        if alerts_count and alerts_count > 0:
            self._alert_frame = QFrame()
            self._alert_frame.setStyleSheet(
                f"background-color: {COLORS['danger']}; border-radius: 3px;"
            )
            alert_layout = QHBoxLayout(self._alert_frame)
            alert_layout.setContentsMargins(S["1"], 1, S["1"], 1)
            alert_layout.setSpacing(0)
            alert_lbl = QLabel(
                f"\u26a0 {alerts_count} {t('dispatch_board.alerts')}"
            )
            alert_lbl.setProperty("fontRole", "label")
            alert_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
            alert_layout.addWidget(alert_lbl)
            content_layout.addWidget(self._alert_frame)

        # Row 8 — live position indicator (hidden by default)
        self._live_row = QWidget()
        live_layout = QHBoxLayout(self._live_row)
        live_layout.setContentsMargins(0, 0, 0, 0)
        live_layout.setSpacing(S["1"])

        live_dot = QLabel("\u25cf " + t("dispatch_board.live"))
        live_dot.setProperty("fontRole", "label")
        live_dot.setStyleSheet(f"color: {COLORS['success']};")
        live_layout.addWidget(live_dot)

        self._live_speed = QLabel("")
        self._live_speed.setProperty("fontRole", "mono")
        self._live_speed.setStyleSheet(f"color: {COLORS['text_secondary']};")
        live_layout.addWidget(self._live_speed)
        live_layout.addStretch(1)

        self._live_row.hide()
        content_layout.addWidget(self._live_row)

        # Finalise layout
        outer_layout.addWidget(self._content_widget, 1)

    # ── Public API ─────────────────────────────────────────────────────────

    def set_live_position(self, position: Any) -> None:
        """Show or hide the live-speed indicator on the card.

        *position* must be an object with ``.status`` and ``.speed_kmh``
        attributes (e.g. a named tuple or dataclass).
        """
        if position and position.status == "moving" and position.speed_kmh > 3:
            self._live_speed.setText(f"{position.speed_kmh:.0f} km/h")
            self._live_row.show()
        else:
            self._live_row.hide()

    def update_truck(self, truck_plate: str, truck_id: Any = None) -> None:
        """Update the displayed truck plate and optionally store the ID."""
        self.trip_data["truck_plate"] = truck_plate
        if truck_id is not None:
            self.trip_data["truck_id"] = truck_id

        if truck_plate:
            self._truck_lbl.setText(truck_plate)
            self._truck_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
            if self._truck_clear_btn is None:
                truck_row = self._truck_lbl.parent()
                if truck_row is not None:
                    self._truck_clear_btn = QLabel("\u2715")
                    self._truck_clear_btn.setProperty("fontRole", "label")
                    self._truck_clear_btn.setStyleSheet(
                        f"color: {COLORS['text_muted']};"
                    )
                    self._truck_clear_btn.setCursor(Qt.PointingHandCursor)
                    self._truck_clear_btn.mousePressEvent = self._on_truck_clear  # type: ignore[assignment]
                    # Insert clear button before the stretch (last widget)
                    truck_row.layout().addWidget(self._truck_clear_btn)
        else:
            self._truck_lbl.setText(t("dispatch_board.assign_truck"))
            self._truck_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
            if self._truck_clear_btn is not None:
                self._truck_clear_btn.deleteLater()
                self._truck_clear_btn = None

    def update_driver(self, driver_name: str, driver_id: Any = None) -> None:
        """Update the displayed driver name and optionally store the ID."""
        self.trip_data["driver_name"] = driver_name
        if driver_id is not None:
            self.trip_data["driver_id"] = driver_id

        if driver_name:
            self._driver_lbl.setText(driver_name)
            self._driver_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
            if self._driver_clear_btn is None:
                driver_row = self._driver_lbl.parent()
                if driver_row is not None:
                    self._driver_clear_btn = QLabel("\u2715")
                    self._driver_clear_btn.setProperty("fontRole", "label")
                    self._driver_clear_btn.setStyleSheet(
                        f"color: {COLORS['text_muted']};"
                    )
                    self._driver_clear_btn.setCursor(Qt.PointingHandCursor)
                    self._driver_clear_btn.mousePressEvent = self._on_driver_clear  # type: ignore[assignment]
                    driver_row.layout().addWidget(self._driver_clear_btn)
        else:
            self._driver_lbl.setText(t("dispatch_board.assign_driver"))
            self._driver_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
            if self._driver_clear_btn is not None:
                self._driver_clear_btn.deleteLater()
                self._driver_clear_btn = None

    def set_delayed(self, delayed: bool, minutes_overdue: int = 0) -> None:
        """Toggle delayed state and optionally display overdue duration."""
        if delayed == self._delayed:
            return
        self._delayed = delayed

        if delayed:
            self._accent_bar.setStyleSheet(
                f"background-color: {self.DELAYED_COLOR}; border: none; border-radius: 0px;"
            )
            self._delayed_chip.show()
            self._update_card_style()
            if self._date_lbl is not None:
                if minutes_overdue >= 60:
                    hours = minutes_overdue // 60
                    overdue_text = t("dispatch_board.hours_overdue").format(hours=hours)
                else:
                    overdue_text = t("dispatch_board.minutes_overdue").format(
                        minutes=minutes_overdue
                    )
                self._date_lbl.setText(overdue_text)
                self._date_lbl.setStyleSheet(f"color: {self.DELAYED_COLOR};")
        else:
            status = self.trip_data.get("status", "Planned")
            accent_color = self.STATUS_COLORS.get(status, COLORS["chip_planned"])
            self._accent_bar.setStyleSheet(
                f"background-color: {accent_color}; border: none; border-radius: 0px;"
            )
            self._delayed_chip.hide()
            self._update_card_style()
            if self._date_lbl is not None:
                departure = self.trip_data.get("departure_date", "")
                eta = self.trip_data.get("eta", "")
                date_parts: list[str] = []
                if departure:
                    date_parts.append(f"\u25b6 {departure}")
                if eta:
                    date_parts.append(f"\u25c0 {eta}")
                date_text = "  ".join(date_parts) if date_parts else ""
                self._date_lbl.setText(date_text)
                self._date_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")

    def update_data(self, new_data: dict[str, Any]) -> None:
        """Bulk-update the card from a new data dictionary.

        Updates status, truck plate, driver name, and alerts count.
        The internal ``trip_data`` dict is replaced with a shallow copy.
        """
        old_status = self.trip_data.get("status", "")
        new_status = new_data.get("status", "")
        self.trip_data = dict(new_data)

        if new_status != old_status:
            self._set_status(new_status)

        if self._truck_lbl is not None:
            new_plate = new_data.get("truck_plate", "")
            self.trip_data["truck_plate"] = new_plate
            if new_plate:
                self._truck_lbl.setText(new_plate)
                self._truck_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
            else:
                self._truck_lbl.setText(t("dispatch_board.assign_truck"))
                self._truck_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")

        if self._driver_lbl is not None:
            new_driver = new_data.get("driver_name", "")
            self.trip_data["driver_name"] = new_driver
            if new_driver:
                self._driver_lbl.setText(new_driver)
                self._driver_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
            else:
                self._driver_lbl.setText(t("dispatch_board.assign_driver"))
                self._driver_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")

        new_alerts = new_data.get("alerts_count", 0)
        self.trip_data["alerts_count"] = new_alerts

        # Update route label
        if self._route_lbl is not None:
            origin = new_data.get("origin", "?")
            destination = new_data.get("destination", "?")
            route_text = f"{origin} \u2192 {destination}"
            self._route_lbl.setText(route_text)

        # Update date label
        if self._date_lbl is not None:
            departure = new_data.get("departure_date", "")
            eta = new_data.get("eta", "")
            date_parts_local: list[str] = []
            if departure:
                date_parts_local.append(f"\u25b6 {departure}")
            if eta:
                date_parts_local.append(f"\u25c0 {eta}")
            date_text = "  ".join(date_parts_local) if date_parts_local else ""
            self._date_lbl.setText(date_text)
            self._date_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")

        # Reset delayed state (will be re-evaluated by caller)
        self.set_delayed(False, 0)

    def set_selected(self, selected: bool) -> None:
        """Set the selected state and update the card border."""
        if self._selected != selected:
            self._selected = selected
            self._update_selection_visual()

    def is_selected(self) -> bool:
        """Return whether the card is currently selected."""
        return self._selected

    def show_error(self, field: str, message: str) -> None:
        """Display an inline error banner that auto-dismisses after 3 seconds.

        *field* is accepted for API compatibility but currently unused.
        """
        # Remove any existing error indicator
        self._dismiss_error()

        self._error_lbl = QLabel(message)
        self._error_lbl.setProperty("fontRole", "label")
        self._error_lbl.setStyleSheet(
            f"background-color: {COLORS['danger']};"
            f"color: {COLORS['text_primary']};"
            f"padding: 2px 6px;"
            f"border-radius: 3px;"
        )
        self._error_lbl.setWordWrap(True)

        if self._content_widget is not None:
            self._content_widget.layout().addWidget(self._error_lbl)

        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.timeout.connect(self._dismiss_error)
        self._error_timer.start(3000)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _dismiss_error(self) -> None:
        """Remove the error banner and stop the dismiss timer."""
        if self._error_lbl is not None:
            self._content_widget.layout().removeWidget(self._error_lbl)
            self._error_lbl.deleteLater()
            self._error_lbl = None
        if self._error_timer is not None:
            self._error_timer.stop()
            self._error_timer = None

    def _set_status(self, status: str) -> None:
        """Update accent bar, chip colour, and chip text for a new status."""
        self.trip_data["status"] = status
        accent_color = self.STATUS_COLORS.get(status, COLORS["chip_planned"])
        self._accent_bar.setStyleSheet(
            f"background-color: {accent_color}; border: none; border-radius: 0px;"
        )
        self._chip_frame.setStyleSheet(
            f"background-color: {accent_color}; border-radius: 3px;"
        )
        translation_key = self.STATUS_TRANSLATION_KEYS.get(status)
        self._chip_lbl.setText(
            t(translation_key if translation_key is not None else status)
        )
        self._chip_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")

    def _update_card_style(self) -> None:
        """Recompute the card background from current hover/delayed state."""
        bg = self.DELAYED_BG if self._delayed else (
            self.CARD_BG_HOVER if self._hovered else self.CARD_BG
        )
        self.setStyleSheet(
            f"QtTripCard {{"
            f"  background-color: {bg};"
            f"}}"
        )
        if self._content_widget is not None:
            self._content_widget.setStyleSheet(
                f"QWidget {{"
                f"  background-color: {bg};"
                f"}}"
            )

    def _update_selection_visual(self) -> None:
        """Set the card border to reflect selection state.

        Calls ``_update_card_style`` for the background, then applies
        the appropriate border via an inline stylesheet on ``self``.
        """
        self._update_card_style()

        if self._selected:
            # accent border — overrides global QSS via inline stylesheet
            self.setStyleSheet(
                self.styleSheet() + "\n"
                f"QtTripCard {{"
                f"  border: 2px solid {COLORS['accent']};"
                f"}}"
            )
        else:
            # Restore the default border from global QSS by clearing
            # the border override and re-applying only the background.
            self.setStyleSheet(
                f"QtTripCard {{"
                f"  background-color: {self.DELAYED_BG if self._delayed else (self.CARD_BG_HOVER if self._hovered else self.CARD_BG)};"
                f"}}"
            )

    # ── Hover events ───────────────────────────────────────────────────────

    def enterEvent(self, event: Any) -> None:
        """Apply hover background and accent border colour."""
        self._hovered = True
        self._update_card_style()
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:
        """Restore default background and border colour."""
        self._hovered = False
        self._update_card_style()
        super().leaveEvent(event)

    # ── Mouse / drag events ────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Record the press position for drag detection."""
        self._drag_start_pos = event.position().toPoint()
        self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Initiate drag if the pointer moves past the threshold (5 px)."""
        if self._drag_start_pos is None:
            return

        if not self._dragging:
            pos = event.position().toPoint()
            dx = abs(pos.x() - self._drag_start_pos.x())
            dy = abs(pos.y() - self._drag_start_pos.y())
            if dx > 5 or dy > 5:
                self._dragging = True
                if self._on_drag_start is not None:
                    self._on_drag_start(self, event)
        elif self._on_drag_start is not None:
            self._on_drag_start(self, event)
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """On release without drag: handle click or Ctrl+click select."""
        if not self._dragging:
            if event.modifiers() & Qt.ControlModifier:
                self._selected = not self._selected
                self._update_selection_visual()
                if self._on_select_changed is not None:
                    self._on_select_changed(self, self._selected)
            elif self._on_click is not None:
                self._on_click(self.trip_data)

        self._dragging = False
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    # ── Click handlers for assignment labels ───────────────────────────────

    def _on_truck_click(self, event: QMouseEvent) -> None:
        """Trigger the *on_assign_truck* callback."""
        if self._on_assign_truck is not None:
            self._on_assign_truck(self)

    def _on_driver_click(self, event: QMouseEvent) -> None:
        """Trigger the *on_assign_driver* callback."""
        if self._on_assign_driver is not None:
            self._on_assign_driver(self)

    def _on_both_click(self, event: QMouseEvent) -> None:
        """Trigger the *on_assign_both* callback."""
        if self._on_assign_both is not None:
            self._on_assign_both(self)

    def _on_truck_clear(self, event: QMouseEvent) -> None:
        """Trigger the *on_assign_truck* callback with ``clear=True``."""
        if self._on_assign_truck is not None:
            self._on_assign_truck(self, clear=True)

    def _on_driver_clear(self, event: QMouseEvent) -> None:
        """Trigger the *on_assign_driver* callback with ``clear=True``."""
        if self._on_assign_driver is not None:
            self._on_assign_driver(self, clear=True)
