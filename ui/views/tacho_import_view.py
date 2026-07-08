"""PySide6 tachograph import view — two-panel import + history.

Replaces ``ui/views/tacho_import_view.py``. Left panel has import controls
(info box, import buttons, progress, result card); right panel has the import
history table.
"""

from __future__ import annotations

import contextlib
import logging
import threading

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services.i18n import register_listener, t, unregister_listener
from services.tacho_service import TachoService
from ui.components import (
    Btn,
    Card,
    CardHeader,
    EmptyState,
    Label,
    PageTitle,
    StatusBadge,
)
from ui.design_tokens import (
    COLOR_BG_ELEVATED,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_INFO_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    DANGER_TEXT,
    FONT_SIZE_BASE,
    FONT_WEIGHT_MEDIUM,
    SP,
    SUCCESS_TEXT,
    WARNING_DIM,
    WARNING_TEXT,
)

from ui.widgets import StyledTableWidget

logger = logging.getLogger(__name__)


class QtTachoImportView(QWidget):
    """Tachograph import view with import panel (left) and history (right)."""

    # Cross-thread signal: the import worker emits this from a non-GUI
    # thread; Qt marshals the slot to the GUI thread.  (Previously we
    # used ``QTimer.singleShot(0, ...)`` from the worker, but Qt creates
    # the timer in the calling thread and its event loop never runs, so
    # the result never reached the UI.)
    import_completed = Signal(dict)

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        api_client=None,
    ):
        super().__init__(parent)
        self.db = db
        self._api_client = api_client
        if self._api_client is not None:
            from client.remote_tacho import RemoteTachoService
            self.tacho_service = RemoteTachoService(self._api_client)
        else:
            self.tacho_service = TachoService(db) if db else None

        self.import_completed.connect(self._on_import_complete)
        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        self._build_ui()
        self._refresh_history()

    # ── UI build ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(SP["5"], SP["4"], SP["5"], SP["4"])
        main_layout.setSpacing(SP["4"])

        # Left panel — import controls (45 %)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(SP["3"])

        # Right panel — history table (55 %)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SP["3"])

        main_layout.addWidget(left_panel, 45)
        main_layout.addWidget(right_panel, 55)

        self._build_page_heading(left_layout)
        self._build_import_card(left_layout)
        self._build_result_card(left_layout)
        self._build_history_table(right_panel, right_layout)

    # ── Left panel ────────────────────────────────────────────────────────────

    def _build_page_heading(self, layout: QVBoxLayout):
        header = QFrame()
        header.setFixedHeight(72)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(SP["5"], 0, SP["5"], 0)
        header_layout.setSpacing(SP["3"])
        title = PageTitle(None, t("tacho.title"))
        header_layout.addWidget(title)
        subtitle = Label(None, t("tacho.subtitle"), role="secondary")
        header_layout.addWidget(subtitle)
        header_layout.addStretch()
        layout.addWidget(header)

    def _build_import_card(self, layout: QVBoxLayout):
        card = Card(None)
        card_layout = card.layout()
        card_layout.setSpacing(SP["3"])

        CardHeader(card_layout, t("tacho.import_card_title"))

        # Drop zone
        self._drop_zone = QFrame()
        self._drop_zone.setAcceptDrops(True)
        self._drop_zone.setMinimumHeight(140)
        self._drop_zone.setStyleSheet(
            f"QFrame{{"
            f"  background: {COLOR_BG_ELEVATED};"
            f"  border: 1px dashed {COLOR_BORDER_MEDIUM};"
            f"  border-radius: 8px;"
            f"}}"
            f"QFrame:hover{{"
            f"  border-color: {COLOR_INFO_DEFAULT};"
            f"}}"
        )
        drop_layout = QVBoxLayout(self._drop_zone)
        drop_layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        drop_layout.setSpacing(SP["2"])
        drop_layout.setAlignment(Qt.AlignCenter)

        drop_icon = QLabel("\u2B06")  # up arrow
        drop_icon.setAlignment(Qt.AlignCenter)
        drop_icon.setStyleSheet(f"font-size: 28px; color: {COLOR_TEXT_TERTIARY}; background: transparent; border: none;")
        drop_layout.addWidget(drop_icon)

        drop_hint = QLabel(t("tacho.drop_hint", "Trage\u021Bi fi\u0219ierele aici sau ap\u0103sa\u021Bi pentru a selecta"))
        drop_hint.setAlignment(Qt.AlignCenter)
        drop_hint.setStyleSheet(
            f"font-size: {FONT_SIZE_BASE}px; font-weight: {FONT_WEIGHT_MEDIUM}; "
            f"color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none;"
        )
        drop_layout.addWidget(drop_hint)

        drop_sub = QLabel(t("tacho.drop_supported", "DDD / TGD / alte fi\u0219iere tahograf"))
        drop_sub.setAlignment(Qt.AlignCenter)
        drop_sub.setStyleSheet(
            f"font-size: 11px; color: {COLOR_TEXT_TERTIARY}; background: transparent; border: none;"
        )
        drop_layout.addWidget(drop_sub)

        # Click to select
        self._drop_zone.mousePressEvent = lambda e: self._browse_and_import()

        card_layout.addWidget(self._drop_zone)

        # How-it-works steps (compact)
        steps = Label(None, t("tacho.import_steps"), role="muted")
        steps.setWordWrap(True)
        steps.setStyleSheet(f"padding: {SP['2']}px; color: {COLOR_TEXT_TERTIARY};")
        card_layout.addWidget(steps)

        # Import buttons
        self._btn_driver = Btn(
            card,
            t("tacho.import_driver_card"),
            variant="primary",
            command=self._import_driver_card,
        )
        card_layout.addWidget(self._btn_driver)

        self._btn_vehicle = Btn(
            card,
            t("tacho.import_vehicle_unit"),
            variant="secondary",
            command=self._import_vehicle_unit,
        )
        self._btn_vehicle.setStyleSheet(
            f"QPushButton{{"
            f"  border: 1px solid {COLOR_BORDER_SUBTLE};"
            f"}}"
            f"QPushButton:hover{{"
            f"  border-color: {COLOR_INFO_DEFAULT};"
            f"}}"
        )
        card_layout.addWidget(self._btn_vehicle)

        # Progress label (hidden initially)
        self._progress_lbl = Label(None, "", role="muted")
        self._progress_lbl.setVisible(False)
        card_layout.addWidget(self._progress_lbl)

        layout.addWidget(card)

    def _browse_and_import(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("tacho.select_file", "Selecteaz\u0103 fi\u0219ier tahograf"),
            "",
            "Tachograph files (*.ddd *.DDD *.tgd *.TGD);;All files (*.*)",
        )
        if file_path:
            self._run_import(file_path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._drop_zone.setStyleSheet(
                f"QFrame{{"
                f"  background: {COLOR_BG_ELEVATED};"
                f"  border: 1px dashed {COLOR_INFO_DEFAULT};"
                f"  border-radius: 8px;"
                f"}}"
            )

    def dragLeaveEvent(self, event):
        self._drop_zone.setStyleSheet(
            f"QFrame{{"
            f"  background: {COLOR_BG_ELEVATED};"
            f"  border: 1px dashed {COLOR_BORDER_MEDIUM};"
            f"  border-radius: 8px;"
            f"}}"
            f"QFrame:hover{{"
            f"  border-color: {COLOR_INFO_DEFAULT};"
            f"}}"
        )

    def dropEvent(self, event: QDropEvent):
        self._drop_zone.setStyleSheet(
            f"QFrame{{"
            f"  background: {COLOR_BG_ELEVATED};"
            f"  border: 1px dashed {COLOR_BORDER_MEDIUM};"
            f"  border-radius: 8px;"
            f"}}"
            f"QFrame:hover{{"
            f"  border-color: {COLOR_INFO_DEFAULT};"
            f"}}"
        )
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self._run_import(path)

    def _build_result_card(self, layout: QVBoxLayout):
        self._result_card = Card(None)
        self._result_card.setVisible(False)
        result_layout = self._result_card.layout()
        result_layout.setSpacing(SP["2"])

        # Large result icon (checkmark / cross)
        self._result_icon = QLabel("")
        self._result_icon.setProperty("fontRole", "result-icon")
        result_layout.addWidget(self._result_icon)

        # Summary message
        self._result_msg = QLabel("")
        self._result_msg.setProperty("fontRole", "body")
        self._result_msg.setWordWrap(True)
        result_layout.addWidget(self._result_msg)

        # Detail line (driver, plate, calibration, days, odometer)
        self._result_detail = QLabel("")
        self._result_detail.setProperty("fontRole", "small")
        self._result_detail.setWordWrap(True)
        self._result_detail.setVisible(False)
        result_layout.addWidget(self._result_detail)

        # Violations warning chip
        self._result_violations = QLabel("")
        self._result_violations.setProperty("fontRole", "label")
        self._result_violations.setVisible(False)
        self._result_violations.setStyleSheet(
            f"background-color: {WARNING_DIM};"
            f"color: {WARNING_TEXT};"
            f"border-radius: 4px; padding: 2px 8px;"
        )
        result_layout.addWidget(self._result_violations)

        layout.addWidget(self._result_card)

    # ── Right panel ──────────────────────────────────────────────────────────

    def _build_history_table(self, parent: QWidget, layout: QVBoxLayout):
        self._history_card = Card(None)
        CardHeader(self._history_card.layout(), t("tacho.import_history"))

        self._history_table = StyledTableWidget(
            parent,
            columns=[
                ("imported_at", t("tacho.hdr_date"), 110),
                ("file_type", t("tacho.hdr_type"), 90),
                ("file_name", t("tacho.hdr_file"), 160),
                ("records_imported", t("tacho.hdr_records"), 70),
                ("parse_status", t("tacho.hdr_status"), 70),
            ],
        )
        self._history_table.setMinimumHeight(120)
        self._history_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        # Formatter for status: raw key → colored display text
        self._history_table._formatters["parse_status"] = self._format_status
        self._history_table.set_data([])

        self._history_table_container = QStackedWidget()
        self._history_table_container.addWidget(self._history_table)

        self._history_empty = EmptyState(
            icon_name="mdi6.file-import-outline",
            title=t("tacho.history_empty_title", "Niciun import"),
            subtitle=t("tacho.history_empty_subtitle", "Importa\u021Bi un fi\u0219ier tahograf pentru a vedea istoricul"),
        )
        self._history_table_container.addWidget(self._history_empty)

        self._history_card.layout().addWidget(self._history_table_container, 1)
        layout.addWidget(self._history_card, 1)

    # ── History ──────────────────────────────────────────────────────────────

    def _refresh_history(self):
        try:
            imports = (
                self.tacho_service.get_import_history(limit=50)
                if self.tacho_service
                else []
            )
        except Exception:
            logger.exception("Failed to load import history")
            imports = []

        rows = [self._format_history_row(imp) for imp in imports]
        self._history_table.set_data(rows)

        if not rows:
            self._history_table_container.setCurrentWidget(self._history_empty)
        else:
            self._history_table_container.setCurrentWidget(self._history_table)
            self._add_table_tooltips()
            self._color_status_column()

    def _add_table_tooltips(self):
        for r in range(self._history_table.rowCount()):
            for c in range(self._history_table.columnCount()):
                item = self._history_table.item(r, c)
                if item is None:
                    continue
                cid = self._history_table._column_ids[c]
                raw = self._history_table._data[r].get(cid, "")
                full = self._history_table._data[r].get(f"{cid}_raw", item.text())
                if len(str(item.text())) >= 15 or cid in ("file_name", "file_type"):
                    item.setToolTip(str(full))
                if cid == "file_name" and len(str(full)) > 12:
                    text = str(full)
                    mid = len(text) // 2
                    item.setText(text[:mid] + "..." + text[-mid:])

    def _color_status_column(self):
        status_col = self._history_table._column_ids.index("parse_status")
        for r, row_data in enumerate(self._history_table._data):
            raw = row_data.get("parse_status_raw", "ok")
            color_map = {
                "ok": SUCCESS_TEXT,
                "error": DANGER_TEXT,
                "partial": WARNING_TEXT,
            }
            color = color_map.get(raw, COLOR_TEXT_PRIMARY)
            item = self._history_table.item(r, status_col)
            if item:
                item.setForeground(QColor(color))

    def _format_status(self, value: str) -> str:
        return value

    @staticmethod
    def _format_history_row(imp: dict) -> dict:
        # Format date
        imp_at = imp.get("imported_at", "")
        if isinstance(imp_at, str) and len(imp_at) >= 10:
            date_str = imp_at[:10]
        else:
            date_str = str(imp_at)[:10]

        # Translate file type
        ftype = imp.get("file_type", "")
        if ftype == "driver_card":
            type_label = t("tacho.type_driver")
        elif ftype == "vehicle_unit":
            type_label = t("tacho.type_vehicle")
        else:
            type_label = ftype

        # Translate status — preserve raw key for badge coloring
        status = imp.get("parse_status", "ok")
        status_map = {
            "ok": t("tacho.status_ok"),
            "error": t("tacho.status_error"),
            "partial": t("tacho.status_partial"),
        }
        status_label = status_map.get(status, status)

        records = imp.get("records_imported", "")
        file_name = imp.get("file_name", "—")
        return {
            "imported_at": date_str,
            "file_type": type_label,
            "file_type_raw": ftype,
            "file_name": file_name,
            "file_name_raw": file_name,
            "records_imported": str(records) if records else "",
            "parse_status": status_label,
            "parse_status_raw": status,
        }

    # ── Import actions ───────────────────────────────────────────────────────

    def _import_driver_card(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("tacho.select_driver_card"),
            "",
            "DDD files (*.ddd *.DDD);;"
            "All tachograph files (*.ddd *.DDD *.tgd *.TGD);;"
            "All files (*.*)",
        )
        if file_path:
            self._run_import(file_path)

    def _import_vehicle_unit(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("tacho.select_vehicle_unit"),
            "",
            "DDD files (*.ddd *.DDD);;"
            "All tachograph files (*.ddd *.DDD *.tgd *.TGD);;"
            "All files (*.*)",
        )
        if file_path:
            self._run_import(file_path)

    def _run_import(self, file_path: str):
        service = self.tacho_service
        if service is None:
            self._show_result_error(t("tacho.unknown_error"))
            return

        self._show_progress(t("tacho.importing"))
        self._result_card.setVisible(False)

        def do_import():
            try:
                result = service.import_ddd_file(file_path)
            except Exception as e:
                logger.exception("Import thread error")
                result = {"success": False, "error": str(e)}
            # ``Signal.emit`` is thread-safe — the connected slot runs on
            # the GUI thread where widget updates are valid.
            self.import_completed.emit(result)

        threading.Thread(target=do_import, daemon=True).start()

    def _show_progress(self, text: str):
        self._progress_lbl.setText(text)
        self._progress_lbl.setVisible(True)

    def _hide_progress(self):
        self._progress_lbl.setText("")
        self._progress_lbl.setVisible(False)

    def _on_import_complete(self, result: dict):
        self._hide_progress()
        if result.get("success"):
            self._show_result_success(result)
        else:
            self._show_result_error(result.get("error", t("tacho.unknown_error")))
        self._refresh_history()

    def _show_result_success(self, result: dict):
        self._result_card.setVisible(True)
        self._result_icon.setText("\u2713")  # ✓
        self._result_icon.setStyleSheet(
            f"color: {SUCCESS_TEXT}; font-size: 24px;"
        )
        self._result_msg.setText(
            result.get("summary", t("tacho.import_successful"))
        )

        detail_parts = []
        driver = result.get("driver_name")
        if driver and driver != "Unknown Driver":
            detail_parts.append(
                f"{t('tacho.result_driver')}: {driver}"
            )
        if result.get("plate"):
            detail_parts.append(
                f"{t('tacho.result_plate')}: {result['plate']}"
            )
        if result.get("calibration_expiry"):
            detail_parts.append(
                f"{t('tacho.result_calibration')}: {result['calibration_expiry']}"
            )
        if result.get("days_imported"):
            detail_parts.append(
                f"{t('tacho.result_days')}: {result['days_imported']}"
            )
        if result.get("odometer_km"):
            detail_parts.append(
                f"{t('tacho.result_odometer')}: {result['odometer_km']:.0f} km"
            )

        if detail_parts:
            self._result_detail.setText("  |  ".join(detail_parts))
            self._result_detail.setVisible(True)
        else:
            self._result_detail.setVisible(False)

        violations = result.get("violations_found", 0)
        if violations > 0:
            self._result_violations.setText(
                t("tacho.violations_warning").format(count=violations)
            )
            self._result_violations.setVisible(True)
        else:
            self._result_violations.setVisible(False)

    def _show_result_error(self, error: str):
        self._result_card.setVisible(True)
        self._result_icon.setText("\u2717")  # ✗
        self._result_icon.setStyleSheet(
            f"color: {DANGER_TEXT}; font-size: 24px;"
        )
        self._result_msg.setText(error)
        self._result_detail.setVisible(False)
        self._result_violations.setVisible(False)

    # ── i18n ─────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        QTimer.singleShot(0, self._rebuild_ui)

    def _rebuild_ui(self) -> None:
        """Refresh translations on language change by rebuilding the UI."""
        # Clear all widgets
        while self.layout().count():
            item = self.layout().takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._build_ui()
        self._refresh_history()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Refresh history when the view becomes active."""
        self._refresh_history()

    def shutdown(self) -> None:
        """Clean up i18n listener when the view is destroyed."""
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)
