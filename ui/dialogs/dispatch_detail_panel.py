"""PySide6 side-drawer panel for viewing/editing trip details from the dispatch board.

Replaces ``ui.widgets.dispatch_detail_panel.DispatchDetailPanel``
(CTkToplevel) with a non-modal QFrame side drawer using widgets from
``ui.qt_widgets``.
"""

from __future__ import annotations

import contextlib
from typing import Any, Callable

import qtawesome as qta
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from services.operations.event_bus import TRIP_UPDATED, VALID_TRANSITIONS, EventBus
from services.trip_service import TripService
from ui.design_tokens import (
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_ELEVATED,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_INFO_DEFAULT,
    COLOR_NEUTRAL_SUBTLE,
    COLOR_SUCCESS_SUBTLE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    COLOR_WARNING_SUBTLE,
    RADIUS_SM,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SP,
    TEXT_WHITE,
)
from ui.widgets import (
    ActionButton,
    ScrollableFormContainer,
    StyledComboBox,
    StyledLineEdit,
)
from ui.widgets.layout_utils import clear_layout

STATUS_TO_COLUMN_UI = {
    "Planned": COLOR_NEUTRAL_SUBTLE,
    "Loading": COLOR_WARNING_SUBTLE,
    "In Transit": COLOR_INFO_DEFAULT,
    "Delivered": COLOR_SUCCESS_SUBTLE,
    "Cancelled": COLOR_NEUTRAL_SUBTLE,
}


class QtDispatchDetailPanel(QFrame):
    """Non-modal side drawer showing full trip detail with edit capability.

    Emits ``close_requested`` when the user dismisses the drawer.
    """

    close_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        trip_data: dict | None = None,
        db: Any = None,
        on_save: Callable | None = None,
        on_close: Callable | None = None,
        ops: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "detail-drawer")
        self.setFixedWidth(480)

        # Style with design tokens
        self.setStyleSheet(f"""
            QtDispatchDetailPanel {{
                background-color: {COLOR_BG_ELEVATED};
                border-left: 1px solid {COLOR_BORDER_SUBTLE};
            }}
        """)

        self._trip_data: dict = dict(trip_data or {})
        self._db = db
        self._on_save: Callable | None = on_save
        self._on_close_cb: Callable | None = on_close
        self._ops = ops
        self._editing: bool = False
        self._edit_widgets: dict[str, Any] = {}
        self._trip_service = TripService(db) if db else None

        if on_close:
            self.close_requested.connect(on_close)

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
        self._fields_layout.setSpacing(SP["2"])
        scroll.add_widget(self._fields_frame)
        self._build_fields_view()

        # Alerts container
        self._alerts_frame = QWidget()
        self._alerts_layout = QVBoxLayout(self._alerts_frame)
        self._alerts_layout.setContentsMargins(0, 0, 0, 0)
        self._alerts_layout.setSpacing(SP["1"])
        scroll.add_widget(self._alerts_frame)
        self._build_alerts()

        scroll.add_stretch()

        # Button row (fixed at bottom, outside scroll)
        self._build_button_row(layout)

    # ── Header ───────────────────────────────────────────────────────────────

    def _build_header(self, scroll: ScrollableFormContainer) -> None:
        header = QWidget()
        hdr_layout = QVBoxLayout(header)
        hdr_layout.setContentsMargins(0, 0, 0, SP["3"])
        hdr_layout.setSpacing(SP["1"])

        # Title row with trip ID and close button
        title_row = QWidget()
        title_row_layout = QHBoxLayout(title_row)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        title_row_layout.setSpacing(0)

        trip_id = str(self._trip_data.get("trip_id", ""))
        trip_lbl = QLabel(trip_id)
        trip_lbl.setProperty("fontRole", "h2")
        trip_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
        title_row_layout.addWidget(trip_lbl)

        title_row_layout.addStretch(1)

        # Close button (× icon)
        self._close_btn = QPushButton()
        self._close_btn.setIcon(qta.icon("fa5s.times", color=COLOR_TEXT_TERTIARY))
        self._close_btn.setFlat(True)
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.clicked.connect(self._close)
        self._close_btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 4px; background: transparent; }}\n"
            f"QPushButton:hover {{ background-color: {COLOR_ACCENT_HOVER}; }}"
        )
        title_row_layout.addWidget(self._close_btn)

        hdr_layout.addWidget(title_row)

        status = self._trip_data.get("status", "Planned")
        chip_color = STATUS_TO_COLUMN_UI.get(status, COLOR_NEUTRAL_SUBTLE)
        chip = QLabel(status)
        chip.setProperty("fontRole", "label")
        chip.setStyleSheet(
            f"background-color: {chip_color};"
            f" color: {COLOR_TEXT_PRIMARY};"
            f" padding: 2px 8px; border-radius: 4px;"
        )
        chip.setFixedHeight(24)
        chip.setSizePolicy(
            getattr(QSizePolicy, "Maximum", QSizePolicy.Preferred),
            getattr(QSizePolicy, "Fixed", QSizePolicy.Fixed),
        )
        hdr_layout.addWidget(chip)

        scroll.add_widget(header)

    # ── View fields ──────────────────────────────────────────────────────────

    def _build_fields_view(self) -> None:
        clear_layout(self._fields_layout)

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
                "dispatch_board.detail_promised_date",
                "promised_date",
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
            row_layout.setSpacing(SP["2"])

            label = QLabel(t(label_key))
            label.setProperty("fontRole", "label")
            label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
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
            value_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
            value_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            row_layout.addWidget(value_lbl, 1)

            self._fields_layout.addWidget(row)

    # ── Edit fields ──────────────────────────────────────────────────────────

    def _build_fields_edit(self) -> None:
        clear_layout(self._fields_layout)
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

        # Promised delivery date (OTD)
        self._make_edit_row(
            "dispatch_board.detail_promised_date",
            StyledLineEdit(text=self._trip_data.get("promised_date", "")),
            "promised_date",
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
        row_layout.setSpacing(SP["2"])

        label = QLabel(t(label_key))
        label.setProperty("fontRole", "label")
        label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        label.setFixedWidth(100)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        row_layout.addWidget(label)

        row_layout.addWidget(widget, 1)
        self._edit_widgets[widget_key] = widget
        self._fields_layout.addWidget(row)

    # ── Alerts ───────────────────────────────────────────────────────────────

    def _build_alerts(self) -> None:
        clear_layout(self._alerts_layout)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setFrameShadow(QFrame.Plain)
        div.setStyleSheet(f"color: {COLOR_BORDER_SUBTLE};")
        div.setFixedHeight(1)
        self._alerts_layout.addWidget(div)

        if not self._editing:
            title = QLabel(t("dispatch_board.detail_alerts_for_trip"))
            title.setProperty("fontRole", "h3")
            title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
            title.setContentsMargins(0, SP["1"], 0, SP["2"])
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
                            "critical": COLOR_ERROR_DEFAULT,
                            "warning": COLOR_WARNING_DEFAULT,
                        }.get(sev_value, COLOR_INFO_DEFAULT)

                        arow = QWidget()
                        arow.setStyleSheet(
                            f"background-color: {COLOR_BG_OVERLAY};"
                            f" border-radius: 4px;"
                        )
                        arow.setFixedHeight(28)
                        arow_layout = QHBoxLayout(arow)
                        arow_layout.setContentsMargins(SP["2"], 0, SP["2"], 0)
                        arow_layout.setSpacing(SP["2"])

                        sev_lbl = QLabel(sev_value.upper())
                        sev_lbl.setFixedWidth(60)
                        sev_lbl.setAlignment(Qt.AlignCenter)
                        sev_lbl.setStyleSheet(
                            f"background-color: {sev_color};"
                            f" color: {TEXT_WHITE};"
                            f" border-radius: {RADIUS_SM}px; padding: 1px 4px;"
                        )
                        arow_layout.addWidget(sev_lbl)

                        msg_lbl = QLabel(getattr(alert, "message", "")[:80])
                        msg_lbl.setProperty("fontRole", "label")
                        msg_lbl.setStyleSheet(
                            f"color: {COLOR_TEXT_SECONDARY};"
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
        lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        return lbl

    # ── Button row ───────────────────────────────────────────────────────────

    def _build_button_row(self, parent_layout: QVBoxLayout) -> None:
        self._btn_widget = QWidget()
        self._btn_widget.setFixedHeight(48)
        self._btn_widget.setStyleSheet(
            f"background-color: {COLOR_BG_OVERLAY};"
        )
        self._btn_layout = QHBoxLayout(self._btn_widget)
        self._btn_layout.setContentsMargins(SP["3"], SP["2"], SP["3"], SP["2"])
        self._btn_layout.setSpacing(SP["2"])

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
                color=COLOR_ACCENT_PRIMARY,
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
                color=COLOR_ACCENT_PRIMARY,
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

        changes: dict[str, Any] = {}
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

        promised_w = self._edit_widgets.get("promised_date")
        if promised_w:
            val = promised_w.text().strip()
            if val:
                changes["promised_date"] = val
                self._trip_data["promised_date"] = val

        dist_w = self._edit_widgets.get("distance_km")
        if dist_w:
            val = dist_w.text().strip()
            if val:
                with contextlib.suppress(ValueError):
                    changes["distance_km"] = float(val)

        if not changes:
            self._cancel_edit()
            return

        try:
            from models.trip_models import TripUpdate
            mapped = {k: v for k, v in changes.items() if k in TripUpdate.model_fields}
            self._trip_service.update(int(trip_id), TripUpdate(**mapped))
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
        clear_layout(self._fields_layout)

        err = QLabel(msg)
        err.setStyleSheet(
            f"background-color: {COLOR_ERROR_DEFAULT};"
            f" color: {TEXT_WHITE};"
            f" border-radius: 6px; padding: 8px 12px;"
        )
        err.setWordWrap(True)
        self._fields_layout.addWidget(err)

        QTimer.singleShot(3000, self._dismiss_error)

    def _dismiss_error(self) -> None:
        self._cancel_edit()

    # ── Close ────────────────────────────────────────────────────────────────

    def _close(self) -> None:
        """Close the drawer: emit signal, fire callback, and hide."""
        if self._on_close_cb:
            self._on_close_cb()
        self.close_requested.emit()
        self.hide()

    # ── Public API ──────────────────────────────────────────────────────────

    def load_trip(
        self,
        trip_data: dict,
        db: Any = None,
        ops: Any = None,
        on_save: Callable | None = None,
        on_close: Callable | None = None,
    ) -> None:
        """Reload the panel with new trip data without rebuilding the shell."""
        self._trip_data = dict(trip_data)
        if db is not None:
            self._db = db
            self._trip_service = TripService(db)
        if ops is not None:
            self._ops = ops
        if on_save is not None:
            self._on_save = on_save
        if on_close is not None:
            # Disconnect previous callback to avoid duplicates
            if self._on_close_cb is not None:
                try:
                    self.close_requested.disconnect(self._on_close_cb)
                except (RuntimeError, TypeError):
                    pass
            self._on_close_cb = on_close
            self.close_requested.connect(on_close)

        self._editing = False
        self._edit_widgets = {}
        self._build_fields_view()
        self._build_alerts()
        self._rebuild_buttons()
