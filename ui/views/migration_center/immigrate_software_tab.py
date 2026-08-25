"""PySide6 Import from Software tab — three-phase digital import wizard.

Workflow: Select source file → Map columns → Validate & Import.
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import Btn, Card, CardHeader, EmptyState, Label, StatusBadge
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_ELEVATED,
    COLOR_BG_OVERLAY,
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
    FONT_WEIGHT_SEMIBOLD,
    SP,
    SUCCESS_TEXT,
    WARNING_TEXT,
)

logger = logging.getLogger(__name__)

# ── Graceful service imports ──────────────────────────────────────────

try:
    from services.migration.import_service import ImportService
    from services.migration.progress_tracker import MigrationProgressTracker
except ImportError:
    ImportService = None
    MigrationProgressTracker = None

ENTITIES = [
    ("client", t("migration.entity_clients", "Clients")),
    ("driver", t("migration.entity_drivers", "Drivers")),
    ("truck", t("migration.entity_trucks", "Trucks")),
    ("trip", t("migration.entity_trips", "Trips")),
    ("invoice", t("migration.entity_invoices", "Invoices")),
]

FORMATS = [
    ("csv", "CSV"),
    ("excel", "Excel"),
    ("json", "JSON"),
    ("xml", "XML"),
]

# ── UI constants ──────────────────────────────────────────────────────

FILE_FILTERS = {
    "csv": "CSV files (*.csv *.CSV)",
    "excel": "Excel files (*.xlsx *.xls *.XLSX *.XLS)",
    "json": "JSON files (*.json *.JSON)",
    "xml": "XML files (*.xml *.XML)",
}
ALL_FILES_FILTER = "All files (*.*)"

# Real target fields per entity (mirrors ``ImportValidator.FIELD_SCHEMA``) —
# used to build the column-mapping dropdown so the collected ``columns_map``
# carries actual database field names the import pipeline can validate/commit.
ENTITY_TARGET_FIELDS = {
    "client": [
        "name", "phone", "email", "address", "vat_number", "country",
        "currency_preference", "contact_person", "notes", "is_active",
    ],
    "driver": [
        "name", "phone", "email", "license_number", "license_category",
        "license_expiry", "medical_expiry", "hire_date", "notes", "is_active",
    ],
    "truck": [
        "plate_number", "manufacturer", "model", "year", "vin",
        "fuel_consumption", "mileage", "monthly_rate", "status",
    ],
    "trip": [
        "truck_number", "driver_name", "client_name", "distance_km",
        "total_price_eur", "rate_per_km", "start_date", "end_date",
        "status", "cmr_number",
    ],
    "invoice": [
        "invoice_number", "trip_id", "issue_date", "due_date",
        "total_amount", "status",
    ],
}


class ImmigrateSoftwareTab(QWidget):
    """Tab 1: Import data from external software (CSV / Excel / JSON / XML)."""

    import_completed = Signal(dict)

    def __init__(self, parent, db=None, migration_service=None):
        super().__init__(parent)
        self.db = db
        # Remote mode injects an API-backed service; local mode builds the
        # DB-backed ImportService (unchanged behaviour).
        if migration_service is not None:
            self._import_svc = migration_service
        else:
            self._import_svc = ImportService(db) if (db and ImportService) else None

        # State
        self._selected_file: str | None = None
        self._source_columns: list[str] = []
        self._preview_data: list[list[str]] = []
        self._validation_results: dict | None = None
        self._duplicates: list[dict] = []

        self.import_completed.connect(self._on_import_complete)

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

        # ── 1. Configuration card ────────────────────────────────────
        self._cfg_card = Card(None)
        cfg_layout = self._cfg_card.layout()
        CardHeader(cfg_layout, t("migration.software_config_title", "Source Configuration"))

        # Format + Entity row
        row1 = QHBoxLayout()
        row1.setSpacing(SP["4"])

        fmt_group = QVBoxLayout()
        fmt_group.setSpacing(SP["1"])
        fmt_group.addWidget(Label(None, t("migration.format", "Format"), role="muted"))
        self._fmt_combo = QComboBox()
        for _val, label in FORMATS:
            self._fmt_combo.addItem(label)
        fmt_group.addWidget(self._fmt_combo)
        row1.addLayout(fmt_group, 1)

        ent_group = QVBoxLayout()
        ent_group.setSpacing(SP["1"])
        ent_group.addWidget(Label(None, t("migration.entity_type", "Entity Type"), role="muted"))
        self._entity_combo = QComboBox()
        for _val, label in ENTITIES:
            self._entity_combo.addItem(label)
        ent_group.addWidget(self._entity_combo)
        row1.addLayout(ent_group, 1)

        cfg_layout.addLayout(row1)

        # File picker row
        file_row = QHBoxLayout()
        file_row.setSpacing(SP["2"])
        self._file_path_label = Label(
            None,
            t("migration.no_file_selected", "No file selected"),
            role="secondary",
        )
        self._file_path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        file_row.addWidget(self._file_path_label, 1)
        self._btn_browse = Btn(
            None,
            t("migration.browse", "Browse\u2026"),
            variant="secondary",
            command=self._browse_file,
        )
        file_row.addWidget(self._btn_browse)
        cfg_layout.addLayout(file_row)

        # Preview button
        self._btn_preview = Btn(
            None,
            t("migration.preview", "Preview"),
            variant="primary",
            command=self._preview,
        )
        self._btn_preview.setEnabled(False)
        cfg_layout.addWidget(self._btn_preview)

        main_layout.addWidget(self._cfg_card)

        # ── 2. Field mapping card (hidden until preview) ────────────
        self._mapping_card = Card(None)
        self._mapping_card.setVisible(False)
        mapping_layout = self._mapping_card.layout()
        CardHeader(
            mapping_layout,
            t("migration.field_mapping_title", "Field Mapping"),
            subtitle=t("migration.field_mapping_subtitle", "Map source columns to target fields"),
        )

        self._mapping_table = QTableWidget()
        self._mapping_table.setColumnCount(3)
        self._mapping_table.setHorizontalHeaderLabels([
            t("migration.col_source", "Source Column"),
            t("migration.col_target", "Target Field"),
            t("migration.col_sample", "Sample Data"),
        ])
        self._mapping_table.horizontalHeader().setStretchLastSection(True)
        self._mapping_table.setAlternatingRowColors(True)
        self._mapping_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._mapping_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._mapping_table.verticalHeader().setVisible(False)
        self._mapping_table.setMinimumHeight(120)
        mapping_layout.addWidget(self._mapping_table, 1)

        # Validate button
        self._btn_validate = Btn(
            None,
            t("migration.validate", "Validate && Find Duplicates"),
            variant="primary",
            command=self._on_validate,
        )
        self._btn_validate.setEnabled(False)
        mapping_layout.addWidget(self._btn_validate)

        main_layout.addWidget(self._mapping_card)

        # ── 3. Results area (hidden until validation) ───────────────
        self._results_card = Card(None)
        self._results_card.setVisible(False)
        results_layout = self._results_card.layout()

        CardHeader(results_layout, t("migration.validation_results", "Validation Results"))

        # Summary row
        summary_row = QHBoxLayout()
        summary_row.setSpacing(SP["4"])
        self._lbl_valid = Label(None, "0", role="default")
        summary_row.addWidget(Label(None, t("migration.valid_rows", "Valid rows:"), role="secondary"))
        summary_row.addWidget(self._lbl_valid)
        self._lbl_invalid = Label(None, "0", role="default")
        summary_row.addWidget(Label(None, t("migration.invalid_rows", "Invalid:"), role="secondary"))
        summary_row.addWidget(self._lbl_invalid)
        self._lbl_duplicates = Label(None, "0", role="default")
        summary_row.addWidget(Label(None, t("migration.duplicates_found", "Duplicates:"), role="secondary"))
        summary_row.addWidget(self._lbl_duplicates)
        summary_row.addStretch()
        results_layout.addLayout(summary_row)

        # Invalid rows table
        self._invalid_table = QTableWidget()
        self._invalid_table.setColumnCount(3)
        self._invalid_table.setHorizontalHeaderLabels([
            t("migration.col_row", "Row"),
            t("migration.col_error", "Error"),
            t("migration.col_data", "Data"),
        ])
        self._invalid_table.horizontalHeader().setStretchLastSection(True)
        self._invalid_table.setAlternatingRowColors(True)
        self._invalid_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._invalid_table.verticalHeader().setVisible(False)
        self._invalid_table.setMinimumHeight(80)
        self._invalid_table.setVisible(False)
        results_layout.addWidget(self._invalid_table, 1)

        # Duplicate resolution area
        self._dup_group = QGroupBox(t("migration.duplicate_resolution", "Duplicate Resolution"))
        self._dup_group.setVisible(False)
        dup_layout = QVBoxLayout(self._dup_group)
        dup_layout.setSpacing(SP["2"])

        self._dup_label = Label(None, "", role="secondary")
        dup_layout.addWidget(self._dup_label)

        self._dup_skip = QRadioButton(t("migration.dup_skip", "Skip duplicates (keep existing)"))
        self._dup_skip.setChecked(True)
        self._dup_update = QRadioButton(t("migration.dup_update", "Update existing records"))
        self._dup_keep = QRadioButton(t("migration.dup_keep", "Keep both (create duplicates)"))
        dup_layout.addWidget(self._dup_skip)
        dup_layout.addWidget(self._dup_update)
        dup_layout.addWidget(self._dup_keep)

        results_layout.addWidget(self._dup_group)

        # Import button + progress
        self._btn_import = Btn(
            None,
            t("migration.import_rows", "Import 0 rows"),
            variant="primary",
            command=self._on_import,
        )
        self._btn_import.setEnabled(False)
        results_layout.addWidget(self._btn_import)

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        results_layout.addWidget(self._progress_bar)

        self._status_label = Label(None, "", role="muted")
        self._status_label.setVisible(False)
        results_layout.addWidget(self._status_label)

        main_layout.addWidget(self._results_card)

        # ── Empty state (no service) ─────────────────────────────────
        self._empty_state = EmptyState(
            None,
            icon_name="mdi6.file-import-outline",
            title=t("migration.software_empty_title", "Import from Software"),
            subtitle=t(
                "migration.software_empty_subtitle",
                "Select a file to begin importing data from external software.",
            ),
        )
        self._empty_state.setVisible(False)
        main_layout.addWidget(self._empty_state)

    # ── Event handlers ───────────────────────────────────────────────

    def _browse_file(self):
        """Open a file picker filtered by the selected format."""
        fmt_idx = self._fmt_combo.currentIndex()
        fmt_key = FORMATS[fmt_idx][0]
        fmt_filter = FILE_FILTERS.get(fmt_key, ALL_FILES_FILTER)

        file_path, selected_filter = QFileDialog.getOpenFileName(
            self,
            t("migration.select_file", "Select file to import"),
            "",
            f"{fmt_filter};;{ALL_FILES_FILTER}",
        )
        if file_path:
            self._selected_file = file_path
            self._file_path_label.setText(file_path)
            self._file_path_label.setStyleSheet(
                f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_SM}px;"
            )
            self._btn_preview.setEnabled(True)
            # Reset downstream state
            self._mapping_card.setVisible(False)
            self._results_card.setVisible(False)
            self._source_columns = []
            self._preview_data = []
            self._validation_results = None

    def _preview(self):
        """Read the selected file and show column mapping."""
        if not self._selected_file or not self._import_svc:
            return

        self._status_label.setText(t("migration.previewing", "Previewing file\u2026"))
        self._status_label.setVisible(True)

        try:
            fmt_key = FORMATS[self._fmt_combo.currentIndex()][0]
            entity_key = ENTITIES[self._entity_combo.currentIndex()][0]
            result = self._import_svc.preview(self._selected_file, fmt_key, entity_key)
            self._source_columns = result.get("columns", [])
            self._preview_data = result.get("sample_rows", [])

            if not self._source_columns:
                self._status_label.setText(
                    t("migration.preview_empty", "No columns found in file.")
                )
                return

            self._populate_mapping_table()
            self._mapping_card.setVisible(True)
            self._btn_validate.setEnabled(True)
            self._status_label.setVisible(False)

        except Exception as exc:
            logger.exception("Preview failed")
            self._status_label.setText(
                t("migration.preview_error", "Preview failed: {error}").format(error=str(exc))
            )

    def _populate_mapping_table(self):
        """Fill the mapping table with source columns and target field selectors."""
        self._mapping_table.setRowCount(len(self._source_columns))
        for row_idx, col_name in enumerate(self._source_columns):
            # Source column name (read-only)
            src_item = QTableWidgetItem(col_name)
            src_item.setFlags(src_item.flags() & ~Qt.ItemIsEditable)
            self._mapping_table.setItem(row_idx, 0, src_item)

            # Target field dropdown
            field_combo = QComboBox()
            field_combo.addItem("")  # Empty = skip
            entity_key = ENTITIES[self._entity_combo.currentIndex()][0]
            field_combo.addItems(ENTITY_TARGET_FIELDS.get(entity_key, []))
            self._mapping_table.setCellWidget(row_idx, 1, field_combo)

            # Sample data (first non-empty preview row)
            sample = ""
            for prow in self._preview_data:
                if row_idx < len(prow) and prow[row_idx].strip():
                    sample = prow[row_idx]
                    break
            sample_item = QTableWidgetItem(sample)
            sample_item.setFlags(sample_item.flags() & ~Qt.ItemIsEditable)
            sample_item.setForeground(Qt.gray)
            self._mapping_table.setItem(row_idx, 2, sample_item)

        self._mapping_table.resizeColumnsToContents()
        self._mapping_table.horizontalHeader().setStretchLastSection(True)

    def _on_validate(self):
        """Run validation and duplicate detection."""
        if not self._import_svc:
            return

        mapping = self._collect_mapping()
        if not mapping:
            return

        self._status_label.setText(t("migration.validating", "Validating data\u2026"))
        self._status_label.setVisible(True)
        self._btn_validate.setEnabled(False)

        try:
            entity_key = ENTITIES[self._entity_combo.currentIndex()][0]
            # Pass the collected column mapping so the backend validates the
            # MAPPED rows (preview returns the raw columns on first pass).
            preview_result = self._import_svc.preview(
                self._selected_file,
                FORMATS[self._fmt_combo.currentIndex()][0],
                entity_key,
                mapping=mapping,
            )
            rows = preview_result.get("sample_rows", [])
            results = self._import_svc.validate_all(rows, entity_key)
            self._validation_results = results
            self._duplicates = results.get("duplicates", [])

            # Update summary
            valid = results.get("valid_rows", 0)
            invalid = results.get("validation_failures", 0)
            dups = results.get("duplicates_skipped", 0)
            self._lbl_valid.setText(str(valid))
            self._lbl_invalid.setText(str(invalid))
            self._lbl_duplicates.setText(str(dups))

            # Invalid rows table
            errors = results.get("errors", [])
            if errors:
                self._invalid_table.setRowCount(len(errors))
                for i, err in enumerate(errors):
                    self._invalid_table.setItem(i, 0, QTableWidgetItem(str(err.get("row", ""))))
                    self._invalid_table.setItem(i, 1, QTableWidgetItem(str(err.get("message", ""))))
                    self._invalid_table.setItem(i, 2, QTableWidgetItem(str(err.get("data", ""))))
                self._invalid_table.resizeColumnsToContents()
                self._invalid_table.setVisible(True)
            else:
                self._invalid_table.setVisible(False)

            # Duplicates section
            if self._duplicates:
                self._dup_label.setText(
                    t("migration.dup_count", "{count} duplicate(s) found").format(
                        count=len(self._duplicates)
                    )
                )
                self._dup_group.setVisible(True)
            else:
                self._dup_group.setVisible(False)

            # Enable import if there are valid rows
            rows_to_import = valid - dups
            self._btn_import.setText(
                t("migration.import_rows", "Import {count} rows").format(count=rows_to_import)
            )
            self._btn_import.setEnabled(rows_to_import > 0)

            self._results_card.setVisible(True)
            self._status_label.setText(
                t("migration.validation_done", "Validation complete: {valid} valid, {invalid} errors").format(
                    valid=valid, invalid=invalid
                )
            )

        except Exception as exc:
            logger.exception("Validation failed")
            self._status_label.setText(
                t("migration.validation_error", "Validation failed: {error}").format(error=str(exc))
            )
        finally:
            self._btn_validate.setEnabled(True)

    def _collect_mapping(self) -> dict:
        """Build a mapping dict from the table widgets."""
        mapping = {"columns": {}, "entity_type": ENTITIES[self._entity_combo.currentIndex()][0]}
        for row_idx in range(self._mapping_table.rowCount()):
            src = self._mapping_table.item(row_idx, 0)
            widget = self._mapping_table.cellWidget(row_idx, 1)
            if src and widget and isinstance(widget, QComboBox):
                target = widget.currentText()
                if target:
                    mapping["columns"][src.text()] = target
        return mapping

    def _on_import(self):
        """Run the import in a background thread."""
        if not self._import_svc:
            return

        mapping = self._collect_mapping()
        dup_action = "skip"
        if self._dup_update.isChecked():
            dup_action = "update"
        elif self._dup_keep.isChecked():
            dup_action = "keep_both"

        self._btn_import.setEnabled(False)
        self._results_card.setVisible(True)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText(t("migration.importing", "Importing\u2026"))
        self._status_label.setVisible(True)

        def do_import():
            try:
                tracker = MigrationProgressTracker() if MigrationProgressTracker else None
                if tracker is not None:
                    # Qt delivers the emission from the worker thread to the
                    # GUI thread as a queued connection → safe widget access.
                    tracker.stage_changed.connect(self._on_import_progress)

                def progress_cb(stage, percent, message):
                    if tracker:
                        tracker.callback(stage, percent, message)

                result = self._import_svc.import_data(
                    self._selected_file,
                    mapping,
                    duplicate_action=dup_action,
                    progress_callback=progress_cb,
                )
            except Exception as exc:
                logger.exception("Import thread error")
                result = {"success": False, "error": str(exc)}
            self.import_completed.emit(result)

        threading.Thread(target=do_import, daemon=True).start()

    def _on_import_progress(self, stage: str, percent: int, message: str = "") -> None:
        """Update the import progress bar from the service's stage callback.

        Runs on the GUI thread: the ``MigrationProgressTracker`` emits
        ``stage_changed`` from the worker thread and Qt marshals it here.
        """
        try:
            self._progress_bar.setValue(percent)
        except Exception:
            logger.debug("Import progress update failed: stage=%s", stage, exc_info=True)

    def _on_import_complete(self, result: dict):
        """Handle the import result on the GUI thread."""
        self._progress_bar.setVisible(False)

        if result.get("success"):
            stats = result.get("stats", {})
            committed = stats.get("committed", 0)
            # Surface the full result counts — skipped rows (duplicates +
            # validation failures) and per-row errors — not just committed.
            skipped = result.get("skipped", stats.get("duplicates_skipped", 0))
            errors = result.get("errors", []) or []
            if skipped or errors:
                self._status_label.setText(
                    t(
                        "migration.import_success_detail",
                        "Successfully imported {count} records "
                        "({skipped} skipped, {errors} failed).",
                    ).format(count=committed, skipped=skipped, errors=len(errors))
                )
            else:
                self._status_label.setText(
                    t(
                        "migration.import_success",
                        "Successfully imported {count} records.",
                    ).format(count=committed)
                )
            self._status_label.setStyleSheet(f"color: {SUCCESS_TEXT};")
            # Reset for next import
            self._selected_file = None
            self._file_path_label.setText(t("migration.no_file_selected", "No file selected"))
            self._btn_preview.setEnabled(False)
            self._mapping_card.setVisible(False)
            self._results_card.setVisible(False)
        else:
            error = result.get("error", t("migration.unknown_error", "Unknown error"))
            self._status_label.setText(
                t("migration.import_failed", "Import failed: {error}").format(error=error)
            )
            self._status_label.setStyleSheet(f"color: {DANGER_TEXT};")
            self._btn_import.setEnabled(True)

    def _refresh_history(self):
        """Refresh import history (placeholder — called from main view)."""
        pass
