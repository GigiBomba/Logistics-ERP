"""PySide6 Export Data tab — select, filter, format, and export data.

Provides a simple form with entity selection, field picker, date range
filter, format radio buttons, output path, and a progress bar.
"""

from __future__ import annotations

import logging
import os
import threading

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import Btn, Card, CardHeader, EmptyState, Label, StatusBadge
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_ELEVATED,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_INFO_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    DANGER_TEXT,
    FONT_SIZE_BASE,
    FONT_SIZE_SM,
    FONT_WEIGHT_MEDIUM,
    SP,
    SUCCESS_TEXT,
    WARNING_TEXT,
)

logger = logging.getLogger(__name__)

# ── Graceful service imports ──────────────────────────────────────────

try:
    from services.migration.emigrate_service import EmigrateService
    from services.migration.progress_tracker import MigrationProgressTracker
except ImportError:
    EmigrateService = None
    MigrationProgressTracker = None

ENTITIES = [
    ("trip", t("migration.entity_trips", "Trips")),
    ("client", t("migration.entity_clients", "Clients")),
    ("driver", t("migration.entity_drivers", "Drivers")),
    ("truck", t("migration.entity_trucks", "Trucks")),
    ("invoice", t("migration.entity_invoices", "Invoices")),
]

FORMATS = [
    ("csv", t("migration.format_csv", "CSV")),
    ("excel", t("migration.format_excel", "Excel")),
    ("json", t("migration.format_json", "JSON")),
]

FORMAT_EXTENSIONS = {
    "csv": ".csv",
    "excel": ".xlsx",
    "json": ".json",
}

# Example fields per entity — in production these would come from a service
ENTITY_FIELDS = {
    "trip": [
        "id", "client", "driver", "truck", "origin", "destination",
        "departure_date", "arrival_date", "revenue", "cost", "profit",
    ],
    "client": [
        "id", "name", "contact_person", "phone", "email", "address",
        "city", "country", "vat_number", "notes",
    ],
    "driver": [
        "id", "name", "license_number", "phone", "email", "hire_date",
        "status",
    ],
    "truck": [
        "id", "plate", "make", "model", "year", "vin", "tare_weight",
        "max_load", "status",
    ],
    "invoice": [
        "id", "number", "client", "issue_date", "due_date", "amount",
        "vat", "total", "status",
    ],
}


class EmigrateTab(QWidget):
    """Tab 3: Export data from Operion to an external file."""

    export_completed = Signal(str)

    def __init__(self, parent, db=None, migration_service=None):
        super().__init__(parent)
        self.db = db
        # Remote mode injects an API-backed service; local mode builds the
        # DB-backed EmigrateService (unchanged behaviour).
        if migration_service is not None:
            self._emigrate_svc = migration_service
        else:
            self._emigrate_svc = (
                EmigrateService(db) if (db and EmigrateService) else None
            )

        # State
        self._output_path: str | None = None
        self._selected_fields: list[str] = []

        self.export_completed.connect(self._on_export_complete)

        self._build_ui()

    # ── UI build ──────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(SP["6"], SP["4"], SP["6"], SP["6"])
        main_layout.setSpacing(SP["5"])
        main_layout.setAlignment(Qt.AlignTop)

        # ── 1. What to export card ───────────────────────────────────
        self._what_card = Card(None)
        what_layout = self._what_card.layout()
        CardHeader(
            what_layout,
            t("migration.export_what_title", "What to Export"),
            subtitle=t(
                "migration.export_what_subtitle",
                "Choose the entity type and optional filters",
            ),
        )

        # Entity selector
        ent_group = QVBoxLayout()
        ent_group.setSpacing(SP["1"])
        ent_group.addWidget(
            Label(None, t("migration.entity_type", "Entity Type"), role="muted")
        )
        self._entity_combo = QComboBox()
        for _val, label in ENTITIES:
            self._entity_combo.addItem(label)
        self._entity_combo.currentIndexChanged.connect(self._on_entity_changed)
        ent_group.addWidget(self._entity_combo)
        what_layout.addLayout(ent_group)

        # Field selection checkboxes (auto-populated)
        self._fields_group = QGroupBox(
            t("migration.export_fields", "Include Fields")
        )
        self._fields_group.setCheckable(True)
        self._fields_group.setChecked(True)
        self._fields_layout = QVBoxLayout(self._fields_group)
        self._fields_layout.setSpacing(SP["1"])
        self._fields_layout.setContentsMargins(SP["3"], SP["3"], SP["3"], SP["3"])
        self._field_checkboxes: list[QCheckBox] = []
        what_layout.addWidget(self._fields_group)

        # Date range filter
        date_row = QHBoxLayout()
        date_row.setSpacing(SP["2"])

        date_from_group = QVBoxLayout()
        date_from_group.setSpacing(SP["1"])
        date_from_group.addWidget(
            Label(None, t("migration.export_from", "From"), role="muted")
        )
        # Default to start of current year
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDate(QDate.currentDate().addMonths(-1))
        self._date_from.setDisplayFormat("yyyy-MM-dd")
        self._date_from.setSpecialValueText(" ")
        date_from_group.addWidget(self._date_from)
        date_row.addLayout(date_from_group)

        date_to_group = QVBoxLayout()
        date_to_group.setSpacing(SP["1"])
        date_to_group.addWidget(
            Label(None, t("migration.export_to", "To"), role="muted")
        )
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setDisplayFormat("yyyy-MM-dd")
        date_to_group.addWidget(self._date_to)
        date_row.addLayout(date_to_group)

        what_layout.addLayout(date_row)

        # Row count preview
        self._row_count_label = Label(
            None,
            t("migration.export_row_count", "Records to export: \u2014"),
            role="secondary",
        )
        what_layout.addWidget(self._row_count_label)

        main_layout.addWidget(self._what_card)

        # ── 2. Export format card ────────────────────────────────────
        self._format_card = Card(None)
        format_layout = self._format_card.layout()
        CardHeader(
            format_layout,
            t("migration.export_format_title", "Export Format"),
        )

        self._format_radios: list[QRadioButton] = []
        for _val, label in FORMATS:
            rb = QRadioButton(label)
            self._format_radios.append(rb)
            format_layout.addWidget(rb)
        # Default to first format
        if self._format_radios:
            self._format_radios[0].setChecked(True)

        format_layout.addSpacing(SP["2"])

        # Output path
        output_row = QHBoxLayout()
        output_row.setSpacing(SP["2"])
        self._output_path_label = Label(
            None,
            t("migration.export_no_path", "No output location selected"),
            role="secondary",
        )
        self._output_path_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        output_row.addWidget(self._output_path_label, 1)

        self._btn_browse_output = Btn(
            None,
            t("migration.export_browse", "Browse\u2026"),
            variant="secondary",
            command=self._browse_output,
        )
        output_row.addWidget(self._btn_browse_output)
        format_layout.addLayout(output_row)

        main_layout.addWidget(self._format_card)

        # ── 3. Export action card ────────────────────────────────────
        self._export_card = Card(None)
        export_layout = self._export_card.layout()
        CardHeader(
            export_layout,
            t("migration.export_action_title", "Export"),
        )

        self._btn_export = Btn(
            None,
            t("migration.export_start", "Export Data"),
            variant="primary",
            command=self._start_export,
        )
        export_layout.addWidget(self._btn_export)

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        export_layout.addWidget(self._progress_bar)

        self._status_label = Label(None, "", role="muted")
        self._status_label.setVisible(False)
        export_layout.addWidget(self._status_label)

        main_layout.addWidget(self._export_card)

        # ── Empty state (no service) ─────────────────────────────────
        self._empty_state = EmptyState(
            None,
            icon_name="mdi6.export-variant",
            title=t("migration.export_empty_title", "Export Data"),
            subtitle=t(
                "migration.export_empty_subtitle",
                "Select an entity and format to export data from Operion.",
            ),
        )
        self._empty_state.setVisible(False)
        main_layout.addWidget(self._empty_state)

        # Populate initial fields
        self._on_entity_changed()

    # ── Event handlers ───────────────────────────────────────────────

    def _on_entity_changed(self):
        """Populate field checkboxes when the entity type changes."""
        # Clear existing checkboxes
        for cb in self._field_checkboxes:
            self._fields_layout.removeWidget(cb)
            cb.deleteLater()
        self._field_checkboxes.clear()

        entity_key = ENTITIES[self._entity_combo.currentIndex()][0]
        fields = ENTITY_FIELDS.get(entity_key, [])

        for field in fields:
            cb = QCheckBox(field)
            cb.setChecked(True)
            self._field_checkboxes.append(cb)
            self._fields_layout.addWidget(cb)

        self._fields_layout.addStretch()
        self._update_row_count()

    def _get_selected_fields(self) -> list[str]:
        """Return list of checked field names."""
        return [
            cb.text() for cb in self._field_checkboxes if cb.isChecked()
        ]

    def _get_format_key(self) -> str:
        """Return the key for the selected format radio button."""
        for idx, rb in enumerate(self._format_radios):
            if rb.isChecked():
                return FORMATS[idx][0]
        return FORMATS[0][0]

    def _browse_output(self):
        """Open a save-file dialog with the correct extension filter."""
        fmt_key = self._get_format_key()
        ext = FORMAT_EXTENSIONS.get(fmt_key, ".csv")
        filter_map = {
            "csv": "CSV files (*.csv)",
            "excel": "Excel files (*.xlsx)",
            "json": "JSON files (*.json)",
        }
        selected_filter = filter_map.get(fmt_key, "All files (*.*)")

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            t("migration.export_save_as", "Save export as\u2026"),
            "",
            f"{selected_filter};;All files (*.*)",
        )
        if file_path:
            # Ensure extension matches format
            if not file_path.lower().endswith(ext):
                file_path += ext
            self._output_path = file_path
            self._output_path_label.setText(file_path)
            self._output_path_label.setStyleSheet(
                f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_SM}px;"
            )

    def _update_row_count(self):
        """Query the count of records that would be exported."""
        if not self._emigrate_svc:
            return

        entity_key = ENTITIES[self._entity_combo.currentIndex()][0]
        filters = self._build_filters()

        try:
            count = self._emigrate_svc.count_records(entity_key, filters)
            self._row_count_label.setText(
                t("migration.export_row_count_val", "Records to export: {count}").format(
                    count=count
                )
            )
        except Exception as exc:
            logger.exception("Row count query failed")
            self._row_count_label.setText(
                t("migration.export_row_count_err", "Records to export: \u2014")
            )

    def _build_filters(self) -> dict:
        """Build a filter dict from the current UI state."""
        filters = {}
        if self._date_from.date() != self._date_from.minimumDate():
            filters["date_from"] = self._date_from.date().toString("yyyy-MM-dd")
        if self._date_to.date() != self._date_to.minimumDate():
            filters["date_to"] = self._date_to.date().toString("yyyy-MM-dd")
        return filters

    def _start_export(self):
        """Run the export in a background thread."""
        if not self._emigrate_svc:
            return

        entity_key = ENTITIES[self._entity_combo.currentIndex()][0]
        fmt_key = self._get_format_key()
        fields = self._get_selected_fields()
        filters = self._build_filters()
        output_path = self._output_path

        if not output_path:
            self._status_label.setText(
                t("migration.export_need_path", "Please select an output location.")
            )
            self._status_label.setVisible(True)
            return

        self._btn_export.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText(t("migration.exporting", "Exporting\u2026"))
        self._status_label.setStyleSheet("")
        self._status_label.setVisible(True)

        def do_export():
            try:
                tracker = MigrationProgressTracker() if MigrationProgressTracker else None

                def progress_cb(stage, percent, message):
                    if tracker:
                        tracker.callback(stage, percent, message)

                result = self._emigrate_svc.export(
                    entity_type=entity_key,
                    fmt=fmt_key,
                    output_path=output_path,
                    filters=filters,
                    field_selection=fields if fields else None,
                    progress_cb=progress_cb,
                )
                final_path = result  # result is already a file path string
            except Exception as exc:
                logger.exception("Export thread error")
                final_path = None
            self.export_completed.emit(final_path or "")

        threading.Thread(target=do_export, daemon=True).start()

    def _on_export_complete(self, output_path: str):
        """Handle the export result on the GUI thread."""
        self._progress_bar.setVisible(False)
        self._btn_export.setEnabled(True)

        if output_path:
            try:
                size_bytes = os.path.getsize(output_path)
                size_str = self._format_file_size(size_bytes)
            except OSError:
                size_str = ""

            self._status_label.setText(
                t(
                    "migration.export_success",
                    "Export complete: {path} ({size})",
                ).format(path=output_path, size=size_str)
            )
            self._status_label.setStyleSheet(f"color: {SUCCESS_TEXT};")

            # Show "Open file" button
            self._btn_open_file = Btn(
                None,
                t("migration.export_open_file", "Open file"),
                variant="primary",
                command=lambda: self._open_file(output_path),
            )
            self._export_card.layout().addWidget(self._btn_open_file)
        else:
            self._status_label.setText(
                t("migration.export_failed", "Export failed. Check the logs for details.")
            )
            self._status_label.setStyleSheet(f"color: {DANGER_TEXT};")

    @staticmethod
    def _format_file_size(bytes_count: int) -> str:
        """Format a byte count into a human-readable string."""
        if bytes_count < 1024:
            return f"{bytes_count} B"
        elif bytes_count < 1024 * 1024:
            return f"{bytes_count / 1024:.1f} KB"
        else:
            return f"{bytes_count / (1024 * 1024):.1f} MB"

    def _open_file(self, path: str):
        """Open the exported file with the system default application."""
        try:
            import subprocess
            subprocess.Popen(["explorer", path.replace("/", "\\")], shell=True)
        except Exception as exc:
            logger.warning("Could not open file: %s", exc)
