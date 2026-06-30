"""PySide6 trip history view.

Replaces ``ui/history_view.py``. Displays trip records in a sortable table
with filtering, invoice generation, PDF/Excel export, and delete actions.
"""

from __future__ import annotations

import contextlib
import logging
import os
from datetime import datetime, timedelta

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from services.export_service import ExportService
from services.i18n import register_listener, t, unregister_listener
from services.invoicing.service import InvoiceService
from services.preferences import PreferencesManager
from services.trip_service import TripService
from ui.components import Btn, Card, FieldLabel, Label, PageTitle
from ui.design_tokens import SP
from ui.theme import COLORS
from ui.widgets import (
    StyledComboBox,
    StyledTableWidget,
)
from utils.formatters import fmt_currency, fmt_distance, fmt_rate

logger = logging.getLogger(__name__)

STATUS_TAGS = {
    "Planificat": "info", "Planified": "info", "Planned": "planned",
    "In Transit": "transit", "InTransit": "transit", "Loading": "loading",
    "Delivered": "delivered", "Livrat": "delivered", "Completed": "delivered", "Done": "delivered",
    "Invoiced": "invoiced", "Facturat": "invoiced",
    "Paid": "paid", "Platit": "paid",
    "Archived": "archived", "Arhivat": "archived",
    "Cancelled": "cancelled", "Anulat": "cancelled",
}

STATUS_TAG_KEYS = {
    "planned":   COLORS.get("info", COLORS.get("accent", "#6366f1")),
    "loading":   COLORS.get("warning", "#f59e0b"),
    "transit":   COLORS.get("accent", "#6366f1"),
    "delivered": COLORS.get("success", "#22c55e"),
    "invoiced":  COLORS.get("warning", "#f59e0b"),
    "paid":      COLORS.get("success", "#22c55e"),
    "archived":  COLORS.get("text_muted", "#71717a"),
    "cancelled": COLORS.get("text_muted", "#71717a"),
}

_STATUS_TAG_LOOKUP = {k.strip().lower(): v for k, v in STATUS_TAGS.items()}


class QtHistoryView(QWidget):
    """Trip history browser with filters, invoice generation, and export."""

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        main_app=None,
        controller=None,
        prefs=None,
        ops=None,
    ):
        super().__init__(parent)
        self.db = db
        self.controller = controller
        self.prefs = prefs or (PreferencesManager(db) if db else None)
        self.ops = ops
        self._main_app = main_app or controller

        self.trip_service = TripService(db) if db else None
        self.invoice_service = InvoiceService(db, prefs=self.prefs) if db else None
        self.export_service = ExportService(prefs=self.prefs) if self.prefs else None

        self._limit = 200

        self._build_ui()
        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)
        self.refresh()

    # ── UI build ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["10"], SP["6"], SP["10"], SP["10"])
        layout.setSpacing(0)

        self._build_header(layout)
        self._build_filter_bar(layout)
        self._build_table_card(layout)
        self._build_action_bar(layout)

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        header = QFrame()
        header.setObjectName("card")
        header.setFixedHeight(72)
        hdr_layout = QVBoxLayout(header)
        hdr_layout.setContentsMargins(SP["10"], SP["4"], SP["10"], SP["4"])

        title = PageTitle(header, t("history.title"))
        hdr_layout.addWidget(title)

        subtitle = Label(header, t("history.subtitle"), role="secondary")
        hdr_layout.addWidget(subtitle)

        parent_layout.addWidget(header)

    def _build_filter_bar(self, layout: QVBoxLayout) -> None:
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, SP["2"], 0, SP["2"])
        bar_layout.setSpacing(SP["2"])

        lbl = FieldLabel(bar, f"\U0001f50d {t('history.search_label')}")
        bar_layout.addWidget(lbl)

        self.e_search = QLineEdit()
        self.e_search.setPlaceholderText(t("history.search_placeholder"))
        self.e_search.returnPressed.connect(self._on_search)
        bar_layout.addWidget(self.e_search, 1)

        self.c_status = StyledComboBox(bar)
        self.c_status.addItem("")
        self.c_status.addItems([
            "Planned", "In Transit", "Loading", "Delivered", "Invoiced", "Paid", "Archived",
        ])
        self.c_status.currentTextChanged.connect(self._on_status_filter_changed)
        bar_layout.addWidget(self.c_status)

        reset_btn = Btn(bar, t("history.reset_button"), command=self._reset, variant="secondary")
        bar_layout.addWidget(reset_btn)

        self._count_lbl = Label(bar, "", role="muted")
        bar_layout.addWidget(self._count_lbl)

        bar_layout.addStretch(1)
        layout.addWidget(bar)

    def _build_table_card(self, layout: QVBoxLayout) -> None:
        columns = [
            ("id", t("history.col_id"), 60),
            ("status", t("history.col_status"), 80),
            ("start_date", t("history.col_data"), 90),
            ("truck_number", t("history.col_camion"), 90),
            ("driver_name", t("history.col_driver"), 90),
            ("client_name", t("history.col_client"), 90),
            ("distance_km", t("history.col_km"), 70),
            ("gross_per_km", t("history.col_brut_km"), 70),
            ("net_profit", t("history.col_profit"), 80),
        ]
        card = Card(padding=False)
        self.table = StyledTableWidget(
            card,
            columns=columns,
            formatters={
                "distance_km": fmt_distance,
                "gross_per_km": lambda v: fmt_rate(float(v) if v else 0),
                "net_profit": lambda v: fmt_currency(float(v) if v else 0),
            },
        )
        self.table.horizontalHeader().setStretchLastSection(False)
        for i in range(len(columns)):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        # Align numeric columns to the right
        from PySide6.QtCore import Qt
        for cid in ("distance_km", "gross_per_km", "net_profit"):
            self.table.set_column_alignment(cid, Qt.AlignRight | Qt.AlignVCenter)
        card.layout().addWidget(self.table)
        layout.addWidget(card, 1)

    def _build_action_bar(self, layout: QVBoxLayout) -> None:
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, SP["2"], 0, 0)
        footer_layout.setSpacing(SP["2"])

        primary_btns = [
            ("history.button_invoice", self._generate_invoice, "primary"),
        ]
        secondary_btns = [
            ("history.button_export_pdf", self._export_pdf, "secondary"),
            ("history.button_export_excel", self._export_excel, "secondary"),
            ("history.button_email_invoice", self._send_invoice_email, "secondary"),
            ("history.button_view_route", self._view_route, "secondary"),
            ("history.button_documents", self._open_trip_documents, "secondary"),
            ("history.button_load_more", self._load_more, "secondary"),
        ]
        destructive_btns = [
            ("history.button_delete", self._delete, "danger"),
        ]
        for key, cmd, variant in primary_btns:
            btn = Btn(footer, t(key), command=cmd, variant=variant)
            footer_layout.addWidget(btn)
        footer_layout.addSpacing(SP["4"])
        for key, cmd, variant in secondary_btns:
            btn = Btn(footer, t(key), command=cmd, variant=variant)
            footer_layout.addWidget(btn)
        footer_layout.addStretch(1)
        for key, cmd, variant in destructive_btns:
            btn = Btn(footer, t(key), command=cmd, variant=variant)
            footer_layout.addWidget(btn)
        layout.addWidget(footer)

    # ── Data ───────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        if self.trip_service is None:
            return
        search = self.e_search.text().strip()
        status = self.c_status.currentText()
        trips = self.trip_service.get_filtered(search=search, status=status, limit=self._limit)

        data = []
        for trip in trips:
            profit = float(trip.get("net_profit", 0) or 0)
            data.append({
                "id": str(trip.get("id", "")),
                "start_date": str(trip.get("start_date", "")),
                "truck_number": str(trip.get("truck_number", "")),
                "driver_name": str(trip.get("driver_name", "")),
                "client_name": str(trip.get("client_name", "")),
                "distance_km": str(trip.get("distance_km", "")),
                "gross_per_km": str(trip.get("gross_per_km", "")),
                "net_profit": str(profit),
                "status": str(trip.get("status", "")),
                "_raw": trip,
            })
        self.table.set_data(data)
        self._apply_status_colors(data)
        self._apply_profit_colors(data)
        self._count_lbl.setText(f" ({len(trips)} / {self._limit})")

    def _apply_status_colors(self, data: list) -> None:
        col_idx = self.table._column_ids.index("status") if "status" in self.table._column_ids else -1
        if col_idx < 0:
            return
        for r, row in enumerate(data):
            raw = row.get("status", "")
            tag_key = _STATUS_TAG_LOOKUP.get(raw.strip().lower(), "")
            color = STATUS_TAG_KEYS.get(tag_key)
            if color:
                item = self.table.item(r, col_idx)
                if item:
                    from PySide6.QtGui import QColor
                    item.setForeground(QColor(color))

    def _apply_profit_colors(self, data: list) -> None:
        col_idx = self.table._column_ids.index("net_profit") if "net_profit" in self.table._column_ids else -1
        if col_idx < 0:
            return
        for r, row in enumerate(data):
            profit = float(row.get("net_profit", 0) or 0)
            item = self.table.item(r, col_idx)
            if item:
                from PySide6.QtGui import QColor, QFont

                from ui.design_tokens import (
                    COLOR_ERROR_TEXT,
                    COLOR_SUCCESS_TEXT,
                    COLOR_TEXT_SECONDARY,
                )
                if profit > 0:
                    color = COLOR_SUCCESS_TEXT
                elif profit < 0:
                    color = COLOR_ERROR_TEXT
                else:
                    color = COLOR_TEXT_SECONDARY
                item.setForeground(QColor(color))
                if abs(profit) > 1000:
                    font = item.font()
                    font.setWeight(QFont.Weight.Bold)
                    item.setFont(font)

    def _get_selection(self) -> tuple | None:
        data = self.table.selected_row_data()
        if not data:
            return None
        trip_id = int(data.get("id", 0))
        raw = data.get("_raw") or self.trip_service.get_by_id(trip_id)
        return (trip_id, raw, data)

    # ── Filters ────────────────────────────────────────────────────────────────

    def _on_search(self) -> None:
        self.refresh()

    def _on_status_filter_changed(self, _text: str) -> None:
        self.refresh()

    def _reset(self) -> None:
        self.e_search.clear()
        self.c_status.setCurrentIndex(0)
        self._limit = 200
        self.refresh()

    def _load_more(self) -> None:
        self._limit *= 2
        self.refresh()

    # ── Actions ────────────────────────────────────────────────────────────────

    def _generate_invoice(self) -> None:
        sel = self._get_selection()
        if not sel:
            return
        trip_id, trip_data, _ = sel
        try:
            self.invoice_service.generate(trip_data, mode="client")
            due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            self.invoice_service.create_record(trip_id, t("history.inv_prefix", default="INV-{}").format(trip_id), trip_data.get("total_price_eur", 0), due_date)
            QMessageBox.information(self, t("history.invoice_done"), t("history.invoice_done_msg"))
        except Exception as e:
            QMessageBox.critical(self, t("history.error"), str(e))

    def _export_pdf(self) -> None:
        sel = self._get_selection()
        if not sel:
            return
        _trip_id, trip_data, _ = sel
        try:
            path = self.export_service.export_trip_to_pdf(trip_data)
            os.startfile(path)
        except Exception as e:
            QMessageBox.critical(self, t("history.error"), str(e))

    def _export_excel(self) -> None:
        sel = self._get_selection()
        if not sel:
            return
        _trip_id, trip_data, _ = sel
        try:
            path = self.export_service.export_trip_to_excel(trip_data)
            os.startfile(path)
        except Exception as e:
            QMessageBox.critical(self, t("history.error"), str(e))

    def _send_invoice_email(self) -> None:
        sel = self._get_selection()
        if not sel:
            return
        trip_id, trip_data, _ = sel
        recipient, ok = QInputDialog.getText(
            self, t("history.email_recipient_title"), t("history.email_recipient_msg")
        )
        if not ok or not recipient:
            return
        try:
            self.invoice_service.send_invoice_email(trip_id, recipient, None, trip_data, "client")
            QMessageBox.information(self, t("history.email_done"), t("history.email_done_msg"))
        except Exception as e:
            QMessageBox.critical(self, t("history.error"), str(e))

    def _view_route(self) -> None:
        sel = self._get_selection()
        if not sel:
            return
        _trip_id, _trip_data, _ = sel
        if self.controller and hasattr(self.controller, "_switch_module"):
            self.controller._switch_module("route_planner")

    def _delete(self) -> None:
        sel = self._get_selection()
        if not sel:
            return
        trip_id = sel[0]
        if QMessageBox.question(
            self, t("history.confirm_delete_title"), t("history.confirm_delete_msg"),
        ) == QMessageBox.Yes:
            self.trip_service.delete(trip_id)
            self.refresh()

    def _open_trip_documents(self) -> None:
        sel = self._get_selection()
        if not sel:
            return
        trip_id = sel[0]
        try:
            from ui.views.document_center_view import open_entity_documents
            open_entity_documents(self, self.db, "trip", trip_id, t("history.trip_title", default="Trip #{}").format(trip_id))
        except Exception:
            logger.exception("Failed to open trip documents")

    # ── i18n ───────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        QTimer.singleShot(0, self.refresh)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        self.refresh()

    def shutdown(self) -> None:
        if hasattr(self, '_timer') and self._timer is not None:
            self._timer.stop()
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)
