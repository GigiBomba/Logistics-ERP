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

import qtawesome as qta

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_ERROR_SUBTLE,
    COLOR_INFO_DEFAULT,
    COLOR_NEUTRAL_SUBTLE,
    COLOR_SUCCESS_DEFAULT,
    COLOR_SUCCESS_SUBTLE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    COLOR_WARNING_SUBTLE,
    SP,
)

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

    CARD_BG = COLOR_BG_OVERLAY
    CARD_BG_HOVER = COLOR_BG_OVERLAY
    CARD_BORDER = COLOR_BORDER_SUBTLE
    CARD_BORDER_HOVER = COLOR_ACCENT_PRIMARY
    LEFT_ACCENT_WIDTH = 4

    STATUS_COLORS = {
        "Planned": COLOR_NEUTRAL_SUBTLE,
        "Loading": COLOR_WARNING_SUBTLE,
        "In Transit": COLOR_INFO_DEFAULT,
        "Delivered": COLOR_SUCCESS_SUBTLE,
        "Cancelled": COLOR_NEUTRAL_SUBTLE,
    }

    STATUS_TRANSLATION_KEYS = {
        "Planned": "dispatch_board.col_planned",
        "Loading": "dispatch_board.col_loading",
        "In Transit": "dispatch_board.col_in_transit",
        "Delivered": "dispatch_board.col_delivered",
        "Cancelled": "dispatch_board.col_cancelled",
    }

    DELAYED_COLOR = COLOR_ERROR_DEFAULT
    DELAYED_BG = COLOR_ERROR_SUBTLE

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
        on_status_change: Callable[[QWidget, str], None] | None = None,
        on_navigate_to_generators: Callable[[int, int], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self.setFrameShape(QFrame.StyledPanel)

        self.setAccessibleName("Trip Card")
        self.setAccessibleDescription("Trip information card")

        self.trip_data: dict[str, Any] = trip_data or {}
        self._on_click = on_click
        self._on_drag_start = on_drag_start
        self._on_assign_truck = on_assign_truck
        self._on_assign_driver = on_assign_driver
        self._on_select_changed = on_select_changed
        self._on_assign_both = on_assign_both
        self._on_status_change = on_status_change
        self._on_navigate_to_generators = on_navigate_to_generators

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
        accent_color = self.STATUS_COLORS.get(status, COLOR_NEUTRAL_SUBTLE)

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
        content_layout.setContentsMargins(SP["2"], SP["1"], SP["2"], SP["1"])
        content_layout.setSpacing(0)

        # Row 1 — [truck icon] trip ID + status chip + delayed chip
        row1 = QWidget()
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(0)

        # Subtle truck icon by status color
        status = d.get("status", "Planned")
        accent_color = self.STATUS_COLORS.get(status, COLOR_NEUTRAL_SUBTLE)
        truck_icon = QLabel()
        truck_icon.setPixmap(
            qta.icon("fa5s.truck", color=accent_color).pixmap(14, 14)
        )
        truck_icon.setStyleSheet("background: transparent; border: none;")
        row1_layout.addWidget(truck_icon)

        row1_layout.addSpacing(SP["1"])

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
        delayed_chip_layout.setContentsMargins(SP["1"], 1, SP["1"], 1)
        delayed_chip_layout.setSpacing(0)
        delayed_lbl = QLabel(t("dispatch_board.delayed"))
        delayed_lbl.setProperty("fontRole", "label")
        delayed_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
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
        chip_frame_layout.setContentsMargins(SP["1"], 1, SP["1"], 1)
        chip_frame_layout.setSpacing(0)
        translation_key = self.STATUS_TRANSLATION_KEYS.get(status)
        self._chip_lbl = QLabel(
            t(translation_key if translation_key is not None else status)
        )
        self._chip_lbl.setProperty("fontRole", "label")
        self._chip_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
        chip_frame_layout.addWidget(self._chip_lbl)
        row1_layout.addWidget(self._chip_frame)

        content_layout.addWidget(row1)

        # ── Quick actions (hidden by default, shown on hover) ─────────────
        self._actions_container = QWidget()
        self._actions_container.setFixedHeight(20)
        actions_layout = QHBoxLayout(self._actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(2)

        def _make_action_btn(symbol: str, tooltip: str, target_status: str | None) -> QPushButton:
            btn = QPushButton(symbol)
            btn.setFixedSize(18, 18)
            btn.setFlat(True)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton {"
                "  border: none; border-radius: 3px; font-size: 10px;"
                f"  color: {COLOR_TEXT_TERTIARY}; background: transparent;"
                "}"
                "QPushButton:hover {"
                f"  background-color: {COLOR_BG_HOVER};"
                f"  color: {COLOR_TEXT_PRIMARY};"
                "}"
            )
            if target_status is not None:
                btn.clicked.connect(
                    lambda checked=False, ts=target_status: self._on_status_change_clicked(ts)
                )
            actions_layout.addWidget(btn)
            return btn

        self._btn_view = _make_action_btn("\U0001f441", t("dispatch_board.view_details", default="View Details"), None)
        self._btn_view.clicked.connect(self._on_view_clicked)

        status = d.get("status", "Planned")
        self._btn_start = _make_action_btn("\u25b6", "Start Loading", "Loading")
        self._btn_start.setVisible(status == "Planned")

        self._btn_transit = _make_action_btn("\U0001f69a", "Mark In Transit", "In Transit")
        self._btn_transit.setVisible(status == "Loading")

        self._btn_deliver = _make_action_btn("\u2713", "Mark Delivered", "Delivered")
        self._btn_deliver.setVisible(status == "In Transit")

        self._btn_cancel = _make_action_btn("\u2715", "Cancel Trip", "Cancelled")
        self._btn_cancel.setVisible(status in ("Planned", "Loading"))

        # Documents button — visible for all statuses
        self._btn_docs = QPushButton()
        self._btn_docs.setIcon(qta.icon("fa5s.file-invoice", color=COLOR_TEXT_TERTIARY))
        self._btn_docs.setFixedSize(18, 18)
        self._btn_docs.setFlat(True)
        self._btn_docs.setToolTip(t("dispatch_board.documents", default="Documents"))
        self._btn_docs.setCursor(Qt.PointingHandCursor)
        self._btn_docs.setStyleSheet(
            "QPushButton {"
            "  border: none; border-radius: 3px;"
            f"  color: {COLOR_TEXT_TERTIARY}; background: transparent;"
            "}"
            "QPushButton:hover {"
            f"  background-color: {COLOR_BG_HOVER};"
            f"  color: {COLOR_TEXT_PRIMARY};"
            "}"
        )
        self._btn_docs.clicked.connect(self._on_documents_clicked)
        actions_layout.addWidget(self._btn_docs)

        actions_layout.addStretch(1)
        self._actions_container.hide()
        content_layout.addWidget(self._actions_container)

        # Row 2 — truck icon + truck plate (clickable)
        truck_row = QWidget()
        truck_row.setSizePolicy(
            truck_row.sizePolicy().horizontalPolicy(),
            truck_row.sizePolicy().verticalPolicy(),
        )
        truck_row_layout = QHBoxLayout(truck_row)
        truck_row_layout.setContentsMargins(0, 0, 0, 0)
        truck_row_layout.setSpacing(0)

        truck_icon = QLabel("\U0001f69a")
        truck_icon.setProperty("fontRole", "label")
        truck_icon.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        truck_row_layout.addWidget(truck_icon)

        plate = d.get("truck_plate", "")
        plate_text = plate if plate else t("dispatch_board.assign_truck")
        plate_color = COLOR_TEXT_PRIMARY if plate else COLOR_TEXT_TERTIARY
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
            self._truck_clear_btn.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
            self._truck_clear_btn.setCursor(Qt.PointingHandCursor)
            self._truck_clear_btn.mousePressEvent = self._on_truck_clear  # type: ignore[assignment]
            truck_row_layout.addWidget(self._truck_clear_btn)

        content_layout.addWidget(truck_row)

        # Row 3 — "⚡ Assign Both" link (clickable)
        both_row = QWidget()
        both_row_layout = QHBoxLayout(both_row)
        both_row_layout.setContentsMargins(SP["5"], 0, 0, 0)
        both_row_layout.setSpacing(0)

        self._both_lbl = QLabel("\u26a1 " + t("dispatch_board.assign_both"))
        self._both_lbl.setProperty("fontRole", "small")
        self._both_lbl.setStyleSheet(f"color: {COLOR_ACCENT_PRIMARY};")
        self._both_lbl.setCursor(Qt.PointingHandCursor)
        self._both_lbl.mousePressEvent = self._on_both_click  # type: ignore[assignment]
        both_row_layout.addWidget(self._both_lbl)
        both_row_layout.addStretch(1)

        content_layout.addWidget(both_row)

        # Row 4 — driver icon + driver name (clickable)
        driver_row = QWidget()
        driver_row_layout = QHBoxLayout(driver_row)
        driver_row_layout.setContentsMargins(0, 0, 0, 0)
        driver_row_layout.setSpacing(0)

        driver_icon = QLabel("\U0001f464")
        driver_icon.setProperty("fontRole", "label")
        driver_icon.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        driver_row_layout.addWidget(driver_icon)

        driver = d.get("driver_name", "")
        driver_text = driver if driver else t("dispatch_board.assign_driver")
        driver_color = COLOR_TEXT_PRIMARY if driver else COLOR_TEXT_TERTIARY
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
            self._driver_clear_btn.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
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
                f"background-color: {COLOR_ERROR_DEFAULT}; border-radius: 3px;"
            )
            alert_layout = QHBoxLayout(self._alert_frame)
            alert_layout.setContentsMargins(SP["1"], 1, SP["1"], 1)
            alert_layout.setSpacing(0)
            alert_lbl = QLabel(
                f"\u26a0 {alerts_count} {t('dispatch_board.alerts')}"
            )
            alert_lbl.setProperty("fontRole", "label")
            alert_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
            alert_layout.addWidget(alert_lbl)
            content_layout.addWidget(self._alert_frame)

        # Row 8 — live position indicator (hidden by default)
        self._live_row = QWidget()
        live_layout = QHBoxLayout(self._live_row)
        live_layout.setContentsMargins(0, 0, 0, 0)
        live_layout.setSpacing(0)

        live_dot = QLabel("\u25cf " + t("dispatch_board.live"))
        live_dot.setProperty("fontRole", "label")
        live_dot.setStyleSheet(f"color: {COLOR_SUCCESS_DEFAULT};")
        live_layout.addWidget(live_dot)

        self._live_speed = QLabel("")
        self._live_speed.setProperty("fontRole", "mono")
        self._live_speed.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY};")
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
            self._truck_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
            if self._truck_clear_btn is None:
                truck_row = self._truck_lbl.parent()
                if truck_row is not None:
                    self._truck_clear_btn = QLabel("\u2715")
                    self._truck_clear_btn.setProperty("fontRole", "label")
                    self._truck_clear_btn.setStyleSheet(
                        f"color: {COLOR_TEXT_TERTIARY};"
                    )
                    self._truck_clear_btn.setCursor(Qt.PointingHandCursor)
                    self._truck_clear_btn.mousePressEvent = self._on_truck_clear  # type: ignore[assignment]
                    # Insert clear button before the stretch (last widget)
                    truck_row.layout().addWidget(self._truck_clear_btn)
        else:
            self._truck_lbl.setText(t("dispatch_board.assign_truck"))
            self._truck_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
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
            self._driver_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
            if self._driver_clear_btn is None:
                driver_row = self._driver_lbl.parent()
                if driver_row is not None:
                    self._driver_clear_btn = QLabel("\u2715")
                    self._driver_clear_btn.setProperty("fontRole", "label")
                    self._driver_clear_btn.setStyleSheet(
                        f"color: {COLOR_TEXT_TERTIARY};"
                    )
                    self._driver_clear_btn.setCursor(Qt.PointingHandCursor)
                    self._driver_clear_btn.mousePressEvent = self._on_driver_clear  # type: ignore[assignment]
                    driver_row.layout().addWidget(self._driver_clear_btn)
        else:
            self._driver_lbl.setText(t("dispatch_board.assign_driver"))
            self._driver_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
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
            accent_color = self.STATUS_COLORS.get(status, COLOR_NEUTRAL_SUBTLE)
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
                self._date_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")

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
                self._truck_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
            else:
                self._truck_lbl.setText(t("dispatch_board.assign_truck"))
                self._truck_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")

        if self._driver_lbl is not None:
            new_driver = new_data.get("driver_name", "")
            self.trip_data["driver_name"] = new_driver
            if new_driver:
                self._driver_lbl.setText(new_driver)
                self._driver_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
            else:
                self._driver_lbl.setText(t("dispatch_board.assign_driver"))
                self._driver_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")

        new_alerts = new_data.get("alerts_count", 0)
        self._update_alert_badge(new_alerts)

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
            self._date_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")

        # Update clear buttons for truck/driver
        self._sync_truck_clear_button()
        self._sync_driver_clear_button()

        # Reset delayed state (will be re-evaluated by caller)
        self.set_delayed(False, 0)

    def _sync_truck_clear_button(self) -> None:
        """Ensure truck clear button matches current truck_plate state."""
        if self._truck_lbl is None:
            return
        has_plate = bool(self.trip_data.get("truck_plate", ""))
        if has_plate and self._truck_clear_btn is None:
            truck_row = self._truck_lbl.parent()
            if truck_row is not None:
                self._truck_clear_btn = QLabel("\u2715")
                self._truck_clear_btn.setProperty("fontRole", "label")
                self._truck_clear_btn.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
                self._truck_clear_btn.setCursor(Qt.PointingHandCursor)
                self._truck_clear_btn.mousePressEvent = self._on_truck_clear  # type: ignore[assignment]
                truck_row.layout().addWidget(self._truck_clear_btn)
        elif not has_plate and self._truck_clear_btn is not None:
            self._truck_clear_btn.deleteLater()
            self._truck_clear_btn = None

    def _sync_driver_clear_button(self) -> None:
        """Ensure driver clear button matches current driver_name state."""
        if self._driver_lbl is None:
            return
        has_driver = bool(self.trip_data.get("driver_name", ""))
        if has_driver and self._driver_clear_btn is None:
            driver_row = self._driver_lbl.parent()
            if driver_row is not None:
                self._driver_clear_btn = QLabel("\u2715")
                self._driver_clear_btn.setProperty("fontRole", "label")
                self._driver_clear_btn.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
                self._driver_clear_btn.setCursor(Qt.PointingHandCursor)
                self._driver_clear_btn.mousePressEvent = self._on_driver_clear  # type: ignore[assignment]
                driver_row.layout().addWidget(self._driver_clear_btn)
        elif not has_driver and self._driver_clear_btn is not None:
            self._driver_clear_btn.deleteLater()
            self._driver_clear_btn = None

    def _update_alert_badge(self, count: int) -> None:
        """Recreate the alert banner with *count* alerts, or remove it."""
        if self._alert_frame is not None:
            self._content_widget.layout().removeWidget(self._alert_frame)
            self._alert_frame.deleteLater()
            self._alert_frame = None

        if count > 0:
            self._alert_frame = QFrame()
            self._alert_frame.setStyleSheet(
                f"background-color: {COLOR_ERROR_DEFAULT}; border-radius: 3px;"
            )
            alert_layout = QHBoxLayout(self._alert_frame)
            alert_layout.setContentsMargins(SP["1"], 1, SP["1"], 1)
            alert_layout.setSpacing(0)
            alert_lbl = QLabel(
                f"\u26a0 {count} {t('dispatch_board.alerts')}"
            )
            alert_lbl.setProperty("fontRole", "label")
            alert_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
            alert_layout.addWidget(alert_lbl)
            self._content_widget.layout().addWidget(self._alert_frame)

    def update_alert_count(self, count: int) -> None:
        """Public method to update the alert count and badge on the card."""
        self.trip_data["alerts_count"] = count
        self._update_alert_badge(count)

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
            f"background-color: {COLOR_ERROR_DEFAULT};"
            f"color: {COLOR_TEXT_PRIMARY};"
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
        accent_color = self.STATUS_COLORS.get(status, COLOR_NEUTRAL_SUBTLE)
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
        self._chip_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")

    def _update_card_style(self) -> None:
        """Recompute the card background and border from current state."""
        bg = self.DELAYED_BG if self._delayed else (
            self.CARD_BG_HOVER if self._hovered else self.CARD_BG
        )
        border = (
            f"2px solid {COLOR_ACCENT_PRIMARY}" if self._selected else "none"
        )
        self.setStyleSheet(
            f"QtTripCard {{"
            f"  background-color: {bg};"
            f"  border: {border};"
            f"}}"
        )
        if self._content_widget is not None:
            self._content_widget.setStyleSheet(
                f"QWidget {{"
                f"  background-color: {bg};"
                f"}}"
            )

    def _update_selection_visual(self) -> None:
        """Update the card border to reflect selection state."""
        self._update_card_style()

    # ── Hover events ───────────────────────────────────────────────────────

    def enterEvent(self, event: Any) -> None:
        """Apply hover background, accent border, and show quick actions."""
        self._hovered = True
        self._update_card_style()
        self._actions_container.show()
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:
        """Restore default background, border, and hide quick actions."""
        self._hovered = False
        self._update_card_style()
        self._actions_container.hide()
        super().leaveEvent(event)

    # ── Quick action handlers ──────────────────────────────────────────────

    def _on_view_clicked(self) -> None:
        """Trigger the card's main click handler (opens detail drawer)."""
        if self._on_click is not None:
            self._on_click(self.trip_data)

    def _on_status_change_clicked(self, target_status: str) -> None:
        """Trigger the status change callback with the target status."""
        if self._on_status_change is not None:
            self._on_status_change(self, target_status)

    def _on_documents_clicked(self) -> None:
        """Show a context menu with document generation options."""
        menu = QMenu(self)
        menu.setStyleSheet(
            f"background-color: {COLOR_BG_ELEVATED};"
            f"color: {COLOR_TEXT_PRIMARY};"
            "border: 1px solid " + COLOR_BORDER_SUBTLE + ";"
            "border-radius: 4px;"
        )

        act_invoice = QAction(qta.icon("fa5s.file-invoice-dollar"), t("dispatch_board.generate_invoice", default="Generate Invoice"), self)
        act_cmr = QAction(qta.icon("fa5s.file-alt"), t("dispatch_board.generate_cmr", default="Generate CMR"), self)
        act_receipt = QAction(qta.icon("fa5s.receipt"), t("dispatch_board.generate_receipt", default="Generate Receipt"), self)

        act_invoice.triggered.connect(lambda checked=False: self._on_generate_document(0))
        act_cmr.triggered.connect(lambda checked=False: self._on_generate_document(1))
        act_receipt.triggered.connect(lambda checked=False: self._on_generate_document(2))

        menu.addAction(act_invoice)
        menu.addAction(act_cmr)
        menu.addAction(act_receipt)

        menu.exec(self._btn_docs.mapToGlobal(self._btn_docs.rect().bottomLeft()))

    def _on_generate_document(self, tab_index: int) -> None:
        """Navigate to the Generators view with the trip pre-selected and the correct tab active."""
        trip_id = self.trip_data.get("trip_id_num") or self.trip_data.get("trip_id")
        if trip_id is not None and self._on_navigate_to_generators is not None:
            self._on_navigate_to_generators(int(trip_id), tab_index)

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
                # QDrag.exec() is synchronous; reset drag state afterward
                self._dragging = False
                self._drag_start_pos = None
                return
        else:
            # Already dragging — forward move events
            if self._on_drag_start is not None:
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
