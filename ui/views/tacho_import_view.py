"""PySide6 tachograph import view — two-panel import + history.

Replaces ``ui/views/tacho_import_view.py``. Left panel has import controls
(info box, import buttons, progress, result card); right panel has the import
history table.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
)

from services.i18n import t, register_listener, unregister_listener
from services.tacho_service import TachoService
from ui.theme import COLORS, S
from ui.widgets import ActionButton, StyledTableWidget, SectionHeader

logger = logging.getLogger(__name__)


class QtTachoImportView(QWidget):
    """Tachograph import view with import panel (left) and history (right)."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
    ):
        super().__init__(parent)
        self.db = db
        self.tacho_service = TachoService(db) if db else None

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        self._build_ui()
        self._refresh_history()

    # ── UI build ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(S["5"], S["4"], S["5"], S["4"])
        main_layout.setSpacing(S["4"])

        # Left panel — import controls (45 %)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(S["3"])

        # Right panel — history table (55 %)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(S["3"])

        main_layout.addWidget(left_panel, 45)
        main_layout.addWidget(right_panel, 55)

        self._build_page_heading(left_layout)
        self._build_import_card(left_layout)
        self._build_result_card(left_layout)
        self._build_history_table(right_panel, right_layout)

    # ── Left panel ────────────────────────────────────────────────────────────

    def _build_page_heading(self, layout: QVBoxLayout):
        title = QLabel(t("tacho.title"))
        title.setProperty("fontRole", "display")
        layout.addWidget(title)

        subtitle = QLabel(t("tacho.subtitle"))
        subtitle.setProperty("fontRole", "muted")
        layout.addWidget(subtitle)

    def _build_import_card(self, layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("role", "card")
        card.setFrameShape(QFrame.StyledPanel)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(S["5"], S["4"], S["5"], S["4"])
        content_layout.setSpacing(S["3"])

        # Section header
        content_layout.addWidget(
            SectionHeader(content, t("tacho.import_card_title"))
        )

        # How-it-works info box
        info = QFrame()
        info.setProperty("role", "info-box")
        info.setFrameShape(QFrame.StyledPanel)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(S["3"], S["2"], S["3"], S["2"])
        info_layout.setSpacing(S["1"])

        info_title = QLabel(t("tacho.how_it_works"))
        info_title.setProperty("fontRole", "body-bold")
        info_layout.addWidget(info_title)

        steps = QLabel(t("tacho.import_steps"))
        steps.setProperty("fontRole", "small")
        steps.setWordWrap(True)
        info_layout.addWidget(steps)

        content_layout.addWidget(info)

        # Import buttons
        self._btn_driver = ActionButton(
            content,
            t("tacho.import_driver_card"),
            command=self._import_driver_card,
            variant="primary",
        )
        content_layout.addWidget(self._btn_driver)

        self._btn_vehicle = ActionButton(
            content,
            t("tacho.import_vehicle_unit"),
            command=self._import_vehicle_unit,
            variant="secondary",
        )
        content_layout.addWidget(self._btn_vehicle)

        # Progress label (hidden initially)
        self._progress_lbl = QLabel("")
        self._progress_lbl.setProperty("fontRole", "body")
        self._progress_lbl.setVisible(False)
        content_layout.addWidget(self._progress_lbl)

        card_layout.addWidget(content)
        layout.addWidget(card)

    def _build_result_card(self, layout: QVBoxLayout):
        self._result_card = QFrame()
        self._result_card.setProperty("role", "card")
        self._result_card.setFrameShape(QFrame.StyledPanel)
        self._result_card.setVisible(False)
        result_layout = QVBoxLayout(self._result_card)
        result_layout.setContentsMargins(S["5"], S["4"], S["5"], S["4"])
        result_layout.setSpacing(S["2"])

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
            f"background-color: {COLORS['warning_dim']};"
            f"color: {COLORS['text_warning']};"
            f"border-radius: 4px; padding: 2px 8px;"
        )
        result_layout.addWidget(self._result_violations)

        layout.addWidget(self._result_card)

    # ── Right panel ──────────────────────────────────────────────────────────

    def _build_history_table(self, parent: QWidget, layout: QVBoxLayout):
        layout.addWidget(SectionHeader(parent, t("tacho.import_history")))

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
        layout.addWidget(self._history_table, 1)

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

        # Translate status
        status = imp.get("parse_status", "ok")
        status_map = {
            "ok": t("tacho.status_ok"),
            "error": t("tacho.status_error"),
            "partial": t("tacho.status_partial"),
        }
        status_label = status_map.get(status, status)

        records = imp.get("records_imported", "")
        return {
            "imported_at": date_str,
            "file_type": type_label,
            "file_name": imp.get("file_name", "—"),
            "records_imported": str(records) if records else "",
            "parse_status": status_label,
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
            QTimer.singleShot(0, lambda r=result: self._on_import_complete(r))

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
            f"color: {COLORS['text_success']}; font-size: 24px;"
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
            f"color: {COLORS['text_danger']}; font-size: 24px;"
        )
        self._result_msg.setText(error)
        self._result_detail.setVisible(False)
        self._result_violations.setVisible(False)

    # ── i18n ─────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        QTimer.singleShot(0, self._rebuild_ui)

    def _rebuild_ui(self) -> None:
        """Refresh translations on language change.

        A full rebuild of static labels would require destroying and
        recreating widgets. For simplicity we refresh the dynamic table
        content; static labels in the left panel are rebuilt by the
        parent view manager when appropriate.
        """
        self._refresh_history()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Refresh history when the view becomes active."""
        self._refresh_history()

    def shutdown(self) -> None:
        """Clean up i18n listener when the view is destroyed."""
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
