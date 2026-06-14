"""PySide6 dialog for viewing/editing trip details from the dispatch board.

Replaces ``ui.widgets.dispatch_detail_panel.DispatchDetailPanel``
(CTkToplevel) with a modal QDialog using widgets from ``ui.qt_widgets``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from services.operations.event_bus import VALID_TRANSITIONS, EventBus, TRIP_UPDATED
from services.trip_service import TripService
from ui.theme import COLORS, S
from ui.qt_widgets import (
    ActionButton,
    StyledComboBox,
    StyledLineEdit,
    ScrollableFormContainer,
)


STATUS_TO_COLUMN_UI = {
    "Planned": COLORS["chip_planned"],
    "Loading": COLORS["chip_loading"],
    "In Transit": COLORS["chip_transit"],
    "Delivered": COLORS["chip_delivered"],
    "Cancelled": COLORS["chip_cancelled"],
}


class QtDispatchDetailPanel(QDialog):
    """Modal dialog showing full trip detail with edit capability."""

    def __init__(
        self,
        parent: Optional[QWidget],
        trip_data: dict,
        db: Any,
        on_save: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        ops: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("dispatch_board.detail_title"))
        self.setFixedSize(480, 620)
        self.setWindowModality(Qt.ApplicationModal)

        self._trip_data: dict = dict(trip_data)
        self._db = db
        self._on_save: Optional[Callable] = on_save
        self._on_close_cb: Optional[Callable] = on_close
        self._ops = ops
        self._editing: bool = False
        self._edit_widgets: Dict[str, Any] = {}
        self._trip_service = TripService(db)

        self._build()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = ScrollableFormContainer(self, max_width=440)
        layout.addWidget(scroll, 1)

        # Header
        self._build_header(scroll)

        # Fields container — swapped between view & edit
        self._fields_frame = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_frame)
        self._fields_layout.setContentsMargins(0, 0, 0, 0)
        self._fields_layout.setSpacing(S["2"])
        scroll.add_widget(self._fields_frame)
        self._build_fields_view()

        # Alerts container
        self._alerts_frame = QWidget()
        self._alerts_layout = QVBoxLayout(self._alerts_frame)
        self._alerts_layout.setContentsMargins(0, 0, 0, 0)
        self._alerts_layout.setSpacing(S["1"])
        scroll.add_widget(self._alerts_frame)
        self._build_alerts()

        scroll.add_stretch()

        # Button row (fixed at bottom, outside scroll)
        self._build_button_row(layout)

    # ── Header ───────────────────────────────────────────────────────────────

    def _build_header(self, scroll: ScrollableFormContainer) -> None:
        header = QWidget()
        hdr_layout = QVBoxLayout(header)
        hdr_layout.setContentsMargins(0, 0, 0, S["3"])
        hdr_layout.setSpacing(S["1"])

        trip_id = str(self._trip_data.get("trip_id", ""))
        trip_lbl = QLabel(trip_id)
        trip_lbl.setProperty("fontRole", "h2")
        trip_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
        hdr_layout.addWidget(trip_lbl)

        status = self._trip_data.get("status", "Planned")
        chip_color = STATUS_TO_COLUMN_UI.get(status, COLORS["chip_planned"])
        chip = QLabel(status)
        chip.setProperty("fontRole", "label")
        chip.setStyleSheet(
            f"background-color: {chip_color};"
            f" color: {COLORS['text_primary']};"
            f" padding: 2px 8px; border-radius: 4px;"
        )
        chip.setFixedHeight(22)
        chip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        hdr_layout.addWidget(chip)

        scroll.add_widget(header)

    # ── View fields ──────────────────────────────────────────────────────────

    def _build_fields_view(self) -> None:
        self._clear_layout(self._fields_layout)

        fields = [
            (
                "dispatch_board.detail_truck",
                "truck_plate",
                lambda v: v or t("common.na"),
            ),
            (
                "dispatch_board.detail_driver",
                "driver_name",
                lambda v: v or t("common.na"),
            ),
            (
                "dispatch_board.detail_route",
                None,
                lambda v: (
                    f"{self._trip_data.get('origin', '?')}"
                    f" \u2192 {self._trip_data.get('destination', '?')}"
                ),
            ),
            (
                "dispatch_board.detail_departure",
                "departure_date",
                lambda v: v or t("common.na"),
            ),
            (
                "dispatch_board.detail_eta",
                "eta",
                lambda v: v or t("common.na"),
            ),
            (
                "dispatch_board.detail_distance",
                "distance_km",
                lambda v: f"{v} km" if v else "",
            ),
            (
                "dispatch_board.detail_price",
                "total_price_eur",
                lambda v: f"{v:,.2f}" if v else "",
            ),
            (
                "dispatch_board.detail_net_profit",
                "net_profit",
                lambda v: f"{v:,.2f}" if v else "",
            ),
        ]

        for label_key, data_key, fmt_fn in fields:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(S["2"])

            label = QLabel(t(label_key))
            label.setProperty("fontRole", "label")
            label.setStyleSheet(f"color: {COLORS['text_muted']};")
            label.setFixedWidth(100)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            row_layout.addWidget(label)

            value = (
                fmt_fn(self._trip_data)
                if data_key is None
                else fmt_fn(self._trip_data.get(data_key, ""))
            )
            value_lbl = QLabel(str(value))
            value_lbl.setProperty("fontRole", "body")
            value_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
            value_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            row_layout.addWidget(value_lbl, 1)

            self._fields_layout.addWidget(row)

    # ── Edit fields ──────────────────────────────────────────────────────────

    def _build_fields_edit(self) -> None:
        self._clear_layout(self._fields_layout)
        self._edit_widgets = {}

        status = self._trip_data.get("status", "Planned")
        valid_targets = VALID_TRANSITIONS.get(status, [])

        # Status combo
        self._make_edit_row(
            "dispatch_board.detail_status",
            StyledComboBox(values=list(valid_targets)),
            "status",
        )

        # Departure
        self._make_edit_row(
            "dispatch_board.detail_departure",
            StyledLineEdit(text=self._trip_data.get("departure_date", "")),
            "departure_date",
        )

        # ETA
        self._make_edit_row(
            "dispatch_board.detail_eta",
            StyledLineEdit(text=self._trip_data.get("eta", "")),
            "eta",
        )

        # Distance
        dist_val = self._trip_data.get("distance_km", "")
        self._make_edit_row(
            "dispatch_board.detail_distance",
            StyledLineEdit(text=str(dist_val) if dist_val else ""),
            "distance_km",
        )

    def _make_edit_row(
        self, label_key: str, widget: QWidget, widget_key: str
    ) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(S["2"])

        label = QLabel(t(label_key))
        label.setProperty("fontRole", "label")
        label.setStyleSheet(f"color: {COLORS['text_muted']};")
        label.setFixedWidth(100)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        row_layout.addWidget(label)

        row_layout.addWidget(widget, 1)
        self._edit_widgets[widget_key] = widget
        self._fields_layout.addWidget(row)

    # ── Alerts ───────────────────────────────────────────────────────────────

    def _build_alerts(self) -> None:
        self._clear_layout(self._alerts_layout)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setFrameShadow(QFrame.Plain)
        div.setStyleSheet(f"color: {COLORS['border']};")
        div.setFixedHeight(1)
        self._alerts_layout.addWidget(div)

        if not self._editing:
            title = QLabel(t("dispatch_board.detail_alerts_for_trip"))
            title.setProperty("fontRole", "h3")
            title.setStyleSheet(f"color: {COLORS['text_primary']};")
            title.setContentsMargins(0, S["1"], 0, S["2"])
            self._alerts_layout.addWidget(title)

            trip_id_num = self._trip_data.get("trip_id_num")
            if self._ops and trip_id_num:
                all_alerts = self._ops.get_alerts(resolved=False, limit=200)
                tid_str = str(trip_id_num)
                alerts = [
                    a
                    for a in all_alerts
                    if str(getattr(a, "trip_id", "")) == tid_str
                ][:20]
                if alerts:
                    for alert in alerts:
                        sev_value = getattr(alert.severity, "value", "")
                        sev_color = {
                            "critical": COLORS["danger"],
                            "warning": COLORS["warning"],
                        }.get(sev_value, COLORS["info"])

                        arow = QWidget()
                        arow.setStyleSheet(
                            f"background-color: {COLORS['bg_elevated']};"
                            f" border-radius: 4px;"
                        )
                        arow.setFixedHeight(28)
                        arow_layout = QHBoxLayout(arow)
                        arow_layout.setContentsMargins(S["2"], 0, S["2"], 0)
                        arow_layout.setSpacing(S["2"])

                        sev_lbl = QLabel(sev_value.upper())
                        sev_lbl.setFixedWidth(60)
                        sev_lbl.setAlignment(Qt.AlignCenter)
                        sev_lbl.setStyleSheet(
                            f"background-color: {sev_color};"
                            f" color: #ffffff;"
                            f" border-radius: 3px; padding: 1px 4px;"
                        )
                        arow_layout.addWidget(sev_lbl)

                        msg_lbl = QLabel(getattr(alert, "message", "")[:80])
                        msg_lbl.setProperty("fontRole", "label")
                        msg_lbl.setStyleSheet(
                            f"color: {COLORS['text_secondary']};"
                            f" background: transparent;"
                        )
                        msg_lbl.setSizePolicy(
                            QSizePolicy.Expanding, QSizePolicy.Preferred
                        )
                        arow_layout.addWidget(msg_lbl, 1)

                        self._alerts_layout.addWidget(arow)
                else:
                    self._alerts_layout.addWidget(self._no_alerts_label())
            else:
                self._alerts_layout.addWidget(self._no_alerts_label())

    def _no_alerts_label(self) -> QLabel:
        lbl = QLabel(t("dispatch_board.detail_no_alerts"))
        lbl.setProperty("fontRole", "label")
        lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        return lbl

    # ── Button row ───────────────────────────────────────────────────────────

    def _build_button_row(self, parent_layout: QVBoxLayout) -> None:
        self._btn_widget = QWidget()
        self._btn_widget.setFixedHeight(52)
        self._btn_widget.setStyleSheet(
            f"background-color: {COLORS['bg_elevated']};"
        )
        self._btn_layout = QHBoxLayout(self._btn_widget)
        self._btn_layout.setContentsMargins(S["3"], S["2"], S["3"], S["2"])
        self._btn_layout.setSpacing(S["2"])

        self._rebuild_buttons()
        parent_layout.addWidget(self._btn_widget)

    def _rebuild_buttons(self) -> None:
        # Clear existing buttons
        while self._btn_layout.count():
            item = self._btn_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._btn_layout.addStretch(1)

        if self._editing:
            save_btn = ActionButton(
                self._btn_widget,
                text=t("dispatch_board.detail_save"),
                command=self._save_changes,
                color=COLORS["accent"],
            )
            self._btn_layout.addWidget(save_btn)

            cancel_btn = ActionButton(
                self._btn_widget,
                text=t("dispatch_board.detail_cancel"),
                command=self._cancel_edit,
                variant="ghost",
            )
            self._btn_layout.addWidget(cancel_btn)
        else:
            edit_btn = ActionButton(
                self._btn_widget,
                text=t("dispatch_board.detail_edit_button"),
                command=self._enter_edit_mode,
                color=COLORS["accent"],
            )
            self._btn_layout.addWidget(edit_btn)

            close_btn = ActionButton(
                self._btn_widget,
                text=t("dispatch_board.detail_close"),
                command=self._close,
                variant="ghost",
            )
            self._btn_layout.addWidget(close_btn)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # ── Edit mode transitions ────────────────────────────────────────────────

    def _enter_edit_mode(self) -> None:
        self._editing = True
        self._edit_widgets = {}
        self._build_fields_edit()
        self._build_alerts()
        self._rebuild_buttons()

    def _cancel_edit(self) -> None:
        self._editing = False
        self._edit_widgets = {}
        self._build_fields_view()
        self._build_alerts()
        self._rebuild_buttons()

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save_changes(self) -> None:
        trip_id = self._trip_data.get("trip_id_num") or self._trip_data.get("id")
        if not trip_id:
            self._show_inline_error("Cannot identify trip.")
            return

        changes: Dict[str, Any] = {}
        status_w = self._edit_widgets.get("status")
        if status_w:
            new_status = status_w.currentText()
            if new_status:
                changes["status"] = new_status
                self._trip_data["status"] = new_status

        for field in ("departure_date", "eta"):
            w = self._edit_widgets.get(field)
            if w:
                val = w.text().strip()
                if val:
                    changes[field] = val
                    self._trip_data[field] = val

        dist_w = self._edit_widgets.get("distance_km")
        if dist_w:
            val = dist_w.text().strip()
            if val:
                try:
                    changes["distance_km"] = float(val)
                except ValueError:
                    pass

        if not changes:
            self._cancel_edit()
            return

        try:
            self._trip_service.update(int(trip_id), changes)
            EventBus().publish(
                TRIP_UPDATED,
                {"trip_id": int(trip_id), "changes": changes},
            )
            if self._on_save:
                self._on_save(self._trip_data)
        except Exception as e:
            self._show_inline_error(str(e))
            return

        self._editing = False
        self._edit_widgets = {}
        self._build_fields_view()
        self._build_alerts()
        self._rebuild_buttons()

    def _show_inline_error(self, msg: str) -> None:
        self._clear_layout(self._fields_layout)

        err = QLabel(msg)
        err.setStyleSheet(
            f"background-color: {COLORS['danger']};"
            f" color: #ffffff;"
            f" border-radius: 6px; padding: 8px 12px;"
        )
        err.setWordWrap(True)
        self._fields_layout.addWidget(err)

        QTimer.singleShot(3000, self._dismiss_error)

    def _dismiss_error(self) -> None:
        self._cancel_edit()

    # ── Close ────────────────────────────────────────────────────────────────

    def _close(self) -> None:
        if self._on_close_cb:
            self._on_close_cb()
        self.accept()

    def reject(self) -> None:
        """Also fire the close callback when the user presses Esc / X."""
        if self._on_close_cb:
            self._on_close_cb()
        super().reject()
