"""PySide6 paired assignment dialog for assigning truck + driver to a trip.

Replaces ``ui.widgets.paired_assignment_dialog.PairedAssignmentDialog``
(CTkToplevel) with a modal QDialog using widgets from ``ui.qt_widgets``.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY, COLOR_ACCENT_SUBTLE, COLOR_BG_ELEVATED, COLOR_BG_OVERLAY,
    COLOR_ERROR_DEFAULT, COLOR_SUCCESS_DEFAULT, COLOR_TEXT_PRIMARY, COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT, FADE_MS, RADIUS_MD, RADIUS_SM, ROW_HEIGHT, SPACE_12,
)
from ui.design_tokens import SP as S
from ui.widgets import ActionButton

class QtPairedAssignmentDialog(QDialog):
    """Side-by-side truck and driver picker with paired suggestion.

    Args:
        parent: Parent widget (may be None).
        trip_data: Dictionary with trip_id, origin, destination keys.
        truck_items: List of dicts with id, label, sublabel, score,
            available, status_text keys.
        driver_items: Same shape as *truck_items*.
        paired_hint: Optional text shown above the button row.
        on_assign_both: Callable(truck_id, driver_id) when Assign Both
            is pressed.
        on_assign_truck: Callable(truck_id) when Truck Only is pressed.
        on_assign_driver: Callable(driver_id) when Driver Only is pressed.
    """

    def __init__(
        self,
        parent: QWidget | None,
        trip_data: dict,
        truck_items: list,
        driver_items: list,
        paired_hint: str = "",
        on_assign_both: Callable | None = None,
        on_assign_truck: Callable | None = None,
        on_assign_driver: Callable | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("dispatch_board.pair_title"))
        self.setAccessibleName("Paired assignment")
        self.setAccessibleDescription("Dialog for assigning truck and driver to a trip")
        self.setMinimumSize(480, 400)
        self.resize(600, 520)
        self.setWindowModality(Qt.ApplicationModal)

        self._trip_data: dict = trip_data
        self._truck_items: list = truck_items
        self._driver_items: list = driver_items
        self._paired_hint: str = paired_hint
        self._on_assign_both: Callable | None = on_assign_both
        self._on_assign_truck: Callable | None = on_assign_truck
        self._on_assign_driver: Callable | None = on_assign_driver

        self._selected_truck: int | None = None
        self._selected_driver: int | None = None
        self._truck_widgets: dict[int, QFrame] = {}
        self._driver_widgets: dict[int, QFrame] = {}
        self._both_btn: ActionButton | None = None
        self._truck_btn: ActionButton | None = None
        self._driver_btn: ActionButton | None = None

        self._build()
        self._auto_select_first_available()

        # ── Fade-in effect ─────────────────────────────────────────────
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        # Escape key dismisses (default QDialog behavior)

    def showEvent(self, event: QShowEvent) -> None:
        """Fade in the dialog on show."""
        super().showEvent(event)
        anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        anim.setDuration(FADE_MS)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()

    # ── Auto-select first available ──────────────────────────────────────────

    def _auto_select_first_available(self) -> None:
        for i, item in enumerate(self._truck_items):
            if item.get("available", True):
                self._select_truck(i)
                break
        for i, item in enumerate(self._driver_items):
            if item.get("available", True):
                self._select_driver(i)
                break

    # ── UI construction ──────────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_header(layout)
        self._build_hint(layout)
        self._build_lists(layout)
        self._build_paired_hint(layout)
        self._build_buttons(layout)

        self._update_buttons()

    def _build_header(self, layout: QVBoxLayout) -> None:
        header = QWidget()
        hdr_layout = QHBoxLayout(header)
        hdr_layout.setContentsMargins(S["4"], S["3"], S["4"], S["1"])

        trip_id = str(self._trip_data.get("trip_id", ""))
        trip_lbl = QLabel(trip_id)
        trip_lbl.setProperty("fontRole", "h2")
        trip_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
        hdr_layout.addWidget(trip_lbl)

        route = (
            f"{self._trip_data.get('origin', '?')}"
            f" \u2192 {self._trip_data.get('destination', '?')}"
        )
        route_lbl = QLabel(route)
        route_lbl.setProperty("fontRole", "small")
        route_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        hdr_layout.addWidget(route_lbl)

        hdr_layout.addStretch(1)
        layout.addWidget(header)

    def _build_hint(self, layout: QVBoxLayout) -> None:
        hint_lbl = QLabel(
            t(
                "dispatch_board.pair_hint",
                "Click a truck and a driver, then press Assign Both.",
            )
        )
        hint_lbl.setAccessibleName("Assignment hint")
        hint_lbl.setProperty("fontRole", "label")
        hint_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        hint_lbl.setContentsMargins(S["4"], 0, S["4"], S["1"])
        layout.addWidget(hint_lbl)

    def _build_lists(self, layout: QVBoxLayout) -> None:
        lists_frame = QWidget()
        lists_layout = QHBoxLayout(lists_frame)
        lists_layout.setContentsMargins(S["3"], S["1"], S["3"], S["2"])
        lists_layout.setSpacing(S["2"])

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(S["1"])
        lists_layout.addWidget(left, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(S["1"])
        lists_layout.addWidget(right, 1)

        layout.addWidget(lists_frame, 1)

        self._build_list_panel(
            left,
            "dispatch_board.pair_truck_label",
            self._truck_items,
            self._truck_widgets,
            self._select_truck,
        )
        self._build_list_panel(
            right,
            "dispatch_board.pair_driver_label",
            self._driver_items,
            self._driver_widgets,
            self._select_driver,
        )

    def _build_paired_hint(self, layout: QVBoxLayout) -> None:
        if not self._paired_hint:
            return
        wrapper = QWidget()
        wrapper.setContentsMargins(S["3"], 0, S["3"], S["1"])
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)

        hint_frame = QFrame()
        hint_frame.setStyleSheet(
            f"background-color: {COLOR_BG_ELEVATED}; border-radius: {RADIUS_MD}px;"
        )
        hint_frame_layout = QHBoxLayout(hint_frame)
        hint_frame_layout.setContentsMargins(S["2"], S["1"], S["2"], S["1"])

        hint_lbl = QLabel(self._paired_hint)
        hint_lbl.setProperty("fontRole", "small")
        hint_lbl.setStyleSheet(f"color: {COLOR_ACCENT_PRIMARY};")
        hint_frame_layout.addWidget(hint_lbl)

        wrapper_layout.addWidget(hint_frame)
        layout.addWidget(wrapper)

    def _build_buttons(self, layout: QVBoxLayout) -> None:
        btn_row = QWidget()
        btn_row.setFixedHeight(SPACE_12)
        btn_row.setStyleSheet(f"background-color: {COLOR_BG_OVERLAY};")
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(S["3"], S["2"], S["3"], S["2"])
        btn_layout.setSpacing(S["2"])

        cancel_btn = ActionButton(
            btn_row,
            text=t("dispatch_board.detail_cancel"),
            command=self.reject,
            variant="ghost",
        )
        cancel_btn.setAccessibleName("Cancel")
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch(1)

        self._both_btn = ActionButton(
            btn_row,
            text=t("dispatch_board.pair_assign_both"),
            command=self._do_assign_both,
            color=COLOR_ACCENT_PRIMARY,
        )
        self._both_btn.setAccessibleName("Assign both")
        btn_layout.addWidget(self._both_btn)

        self._truck_btn = ActionButton(
            btn_row,
            text=t("dispatch_board.pair_assign_truck_only"),
            command=self._do_assign_truck_only,
            variant="ghost",
        )
        self._truck_btn.setAccessibleName("Truck only")
        btn_layout.addWidget(self._truck_btn)

        self._driver_btn = ActionButton(
            btn_row,
            text=t("dispatch_board.pair_assign_driver_only"),
            command=self._do_assign_driver_only,
            variant="ghost",
        )
        self._driver_btn.setAccessibleName("Driver only")
        btn_layout.addWidget(self._driver_btn)

        layout.addWidget(btn_row)

    # ── List panel builder ───────────────────────────────────────────────────

    def _build_list_panel(
        self,
        parent: QWidget,
        title_key: str,
        items: list,
        widget_map: dict,
        select_fn: Callable[[int], None],
    ) -> None:
        parent_layout = parent.layout()

        title_lbl = QLabel(t(title_key))
        title_lbl.setAccessibleName(t(title_key))
        title_lbl.setProperty("fontRole", "h3")
        title_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
        title_lbl.setContentsMargins(S["2"], S["2"], S["2"], S["1"])
        parent_layout.addWidget(title_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background-color: {COLOR_BG_ELEVATED};")
        parent_layout.addWidget(scroll, 1)

        content = QWidget()
        content.setStyleSheet(f"background-color: {COLOR_BG_ELEVATED};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(S["1"], 0, S["1"], S["1"])
        content_layout.setSpacing(S["1"])
        content_layout.setAlignment(Qt.AlignTop)

        for idx, item in enumerate(items):
            row = self._build_item_row(content, item, idx, select_fn)
            content_layout.addWidget(row)
            widget_map[idx] = row

        scroll.setWidget(content)

    def _build_item_row(
        self,
        parent: QWidget,
        item: dict,
        idx: int,
        select_fn: Callable[[int], None],
    ) -> QFrame:
        row = QFrame(parent)
        row.setFrameShape(QFrame.NoFrame)
        row.setCursor(Qt.PointingHandCursor)
        row.setFixedHeight(ROW_HEIGHT)
        row.setStyleSheet(
            f"background-color: {COLOR_BG_ELEVATED}; border-radius: {RADIUS_SM}px;"
        )

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(S["1"], 0, S["1"], 0)
        row_layout.setSpacing(S["1"])

        avail = item.get("available", True)
        dot_color = COLOR_SUCCESS_DEFAULT if avail else COLOR_ERROR_DEFAULT

        dot = QFrame(row)
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(
            f"background-color: {dot_color}; border-radius: {RADIUS_SM}px;"
        )
        row_layout.addWidget(dot)

        score = item.get("score", 0)
        if avail and score > 70:
            star_lbl = QLabel("\u2b50")
            star_lbl.setFixedWidth(16)
            star_lbl.setStyleSheet("background: transparent;")
            row_layout.addWidget(star_lbl)

        fg = COLOR_TEXT_PRIMARY if avail else COLOR_TEXT_TERTIARY
        label_text = str(item.get("label", ""))[:24]
        label_widget = QLabel(label_text)
        label_widget.setProperty("fontRole", "small")
        label_widget.setStyleSheet(f"color: {fg}; background: transparent;")
        row_layout.addWidget(label_widget)

        sublabel_text = str(item.get("sublabel", ""))[:30]
        sublabel_widget = QLabel(sublabel_text)
        sublabel_widget.setProperty("fontRole", "label")
        sublabel_widget.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; background: transparent;"
        )
        sublabel_widget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        row_layout.addWidget(sublabel_widget, 1)

        st = item.get("status_text", "")
        if st:
            status_widget = QLabel(str(st)[:30])
            status_widget.setProperty("fontRole", "label")
            status_widget.setStyleSheet(
                f"color: {COLOR_WARNING_DEFAULT}; background: transparent;"
            )
            row_layout.addWidget(status_widget)

        row.mousePressEvent = lambda event, i=idx: select_fn(i)  # type: ignore[assignment]

        return row

    # ── Selection handlers ───────────────────────────────────────────────────

    def _select_truck(self, idx: int) -> None:
        self._selected_truck = idx
        for i, wid in self._truck_widgets.items():
            bg = COLOR_ACCENT_SUBTLE if i == idx else COLOR_BG_ELEVATED
            wid.setStyleSheet(
                f"background-color: {bg}; border-radius: {RADIUS_SM}px;"
            )
        self._update_buttons()

    def _select_driver(self, idx: int) -> None:
        self._selected_driver = idx
        for i, wid in self._driver_widgets.items():
            bg = COLOR_ACCENT_SUBTLE if i == idx else COLOR_BG_ELEVATED
            wid.setStyleSheet(
                f"background-color: {bg}; border-radius: {RADIUS_SM}px;"
            )
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_truck = self._selected_truck is not None
        has_driver = self._selected_driver is not None
        if self._both_btn is not None:
            self._both_btn.setEnabled(has_truck and has_driver)
        if self._truck_btn is not None:
            self._truck_btn.setEnabled(has_truck)
        if self._driver_btn is not None:
            self._driver_btn.setEnabled(has_driver)

    # ── Action callbacks ─────────────────────────────────────────────────────

    def _do_assign_both(self) -> None:
        if self._selected_truck is None or self._selected_driver is None:
            return
        truck_id = self._truck_items[self._selected_truck].get("id")
        driver_id = self._driver_items[self._selected_driver].get("id")
        if self._on_assign_both is not None:
            self._on_assign_both(truck_id, driver_id)
        self.accept()

    def _do_assign_truck_only(self) -> None:
        if self._selected_truck is None:
            return
        truck_id = self._truck_items[self._selected_truck].get("id")
        if self._on_assign_truck is not None:
            self._on_assign_truck(truck_id)
        self.accept()

    def _do_assign_driver_only(self) -> None:
        if self._selected_driver is None:
            return
        driver_id = self._driver_items[self._selected_driver].get("id")
        if self._on_assign_driver is not None:
            self._on_assign_driver(driver_id)
        self.accept()
