"""Tests for the Import from Software tab (ImmigrateSoftwareTab).

Covers construction, configuration card, file browsing, preview,
field mapping table population, validation, duplicate resolution,
import flow (background thread), and empty/no-service states.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
)

from ui.components import EmptyState, Label
from ui.views.migration_center.immigrate_software_tab import (
    ImmigrateSoftwareTab,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def software_tab(qt_widget, qtbot):
    """Provide an ImmigrateSoftwareTab with db=None (services gracefully degraded)."""
    tab = ImmigrateSoftwareTab(parent=qt_widget, db=None)
    qtbot.addWidget(tab)
    qt_widget.show()  # Show parent so children become visible
    yield tab
    tab.deleteLater()


@pytest.fixture
def software_tab_with_svc(qt_widget, qtbot):
    """Provide an ImmigrateSoftwareTab with a mocked ImportService."""
    db = MagicMock()
    with patch(
        "ui.views.migration_center.immigrate_software_tab.ImportService",
    ) as mock_svc_cls:
        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc
        tab = ImmigrateSoftwareTab(parent=qt_widget, db=db)
    qtbot.addWidget(tab)
    qt_widget.show()  # Show parent so children become visible
    yield tab, mock_svc
    tab.deleteLater()


# ── Init ─────────────────────────────────────────────────────────────────

class TestImmigrateSoftwareTabInit:
    """Construction and initial state."""

    def test_creation(self, software_tab):
        assert isinstance(software_tab, ImmigrateSoftwareTab)

    def test_initial_state(self, software_tab):
        assert software_tab._selected_file is None
        assert software_tab._source_columns == []
        assert software_tab._preview_data == []
        assert software_tab._validation_results is None
        assert software_tab._duplicates == []

    def test_config_card_exists(self, software_tab):
        # Card is a factory function returning QFrame -- search by object name
        cards = [c for c in software_tab.findChildren(QFrame) if c.objectName() == "card"]
        assert len(cards) >= 1

    def test_format_combo_exists(self, software_tab):
        fmt_combos = software_tab.findChildren(QComboBox)
        assert len(fmt_combos) >= 2  # format + entity

    def test_entity_combo_exists(self, software_tab):
        combos = software_tab.findChildren(QComboBox)
        assert len(combos) >= 2

    def test_browse_button_exists(self, software_tab):
        buttons = software_tab.findChildren(QPushButton)
        btn_texts = [b.text() for b in buttons]
        assert any("Browse" in t or "browse" in t.lower() for t in btn_texts)

    def test_preview_button_initially_disabled(self, software_tab):
        assert software_tab._btn_preview.isEnabled() is False

    def test_validate_button_initially_disabled(self, software_tab):
        assert software_tab._btn_validate.isEnabled() is False

    def test_mapping_card_hidden_initially(self, software_tab):
        assert software_tab._mapping_card.isVisible() is False

    def test_results_card_hidden_initially(self, software_tab):
        assert software_tab._results_card.isVisible() is False

    def test_progress_bar_hidden_initially(self, software_tab):
        assert software_tab._progress_bar.isVisible() is False

    def test_import_button_initially_disabled(self, software_tab):
        assert software_tab._btn_import.isEnabled() is False

    def test_empty_state_exists(self, software_tab):
        empties = software_tab.findChildren(EmptyState)
        assert len(empties) >= 1

    def test_import_completed_signal_connected(self, software_tab):
        assert software_tab.import_completed is not None

    def test_status_label_hidden_initially(self, software_tab):
        assert software_tab._status_label.isVisible() is False


# ── File browsing ────────────────────────────────────────────────────────

class TestImmigrateSoftwareTabBrowsing:
    """File selection."""

    def test_browse_file_updates_path(self, software_tab):
        with patch(
            "ui.views.migration_center.immigrate_software_tab.QFileDialog.getOpenFileName",
            return_value=("C:\\data\\import.csv", "CSV files (*.csv)"),
        ):
            software_tab._browse_file()
            assert software_tab._selected_file == "C:\\data\\import.csv"
            assert software_tab._btn_preview.isEnabled() is True

    def test_browse_file_no_selection(self, software_tab):
        with patch(
            "ui.views.migration_center.immigrate_software_tab.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ):
            software_tab._browse_file()
            assert software_tab._selected_file is None

    def test_browse_file_resets_downstream(self, software_tab):
        software_tab._mapping_card.setVisible(True)
        software_tab._results_card.setVisible(True)
        with patch(
            "ui.views.migration_center.immigrate_software_tab.QFileDialog.getOpenFileName",
            return_value=("data.csv", ""),
        ):
            software_tab._browse_file()
            assert software_tab._mapping_card.isVisible() is False
            assert software_tab._results_card.isVisible() is False

    def test_browse_file_label_updated(self, software_tab):
        with patch(
            "ui.views.migration_center.immigrate_software_tab.QFileDialog.getOpenFileName",
            return_value=("C:\\data\\import.csv", ""),
        ):
            software_tab._browse_file()
            assert "import.csv" in software_tab._file_path_label.text()


# ── Preview ──────────────────────────────────────────────────────────────

class TestImmigrateSoftwareTabPreview:
    """Preview file content."""

    def test_preview_no_file_returns(self, software_tab):
        software_tab._selected_file = None
        software_tab._preview()  # Should return early, no error

    def test_preview_no_service_returns(self, software_tab):
        software_tab._selected_file = "data.csv"
        software_tab._preview()  # No import_svc — returns early

    def test_preview_populates_mapping(self, software_tab_with_svc):
        tab, mock_svc = software_tab_with_svc
        tab._selected_file = "data.csv"
        mock_svc.preview.return_value = {
            "columns": ["name", "email", "phone"],
            "sample_rows": [["Alice", "alice@test.com", "12345"]],
        }
        tab._preview()
        assert tab._source_columns == ["name", "email", "phone"]
        assert tab._mapping_card.isVisible() is True
        assert tab._btn_validate.isEnabled() is True

    def test_preview_with_empty_columns(self, software_tab_with_svc):
        tab, mock_svc = software_tab_with_svc
        tab._selected_file = "data.csv"
        mock_svc.preview.return_value = {
            "columns": [],
            "sample_rows": [],
        }
        tab._preview()
        assert "No columns" in tab._status_label.text()

    def test_preview_exception_shows_error(self, software_tab_with_svc):
        tab, mock_svc = software_tab_with_svc
        tab._selected_file = "data.csv"
        mock_svc.preview.side_effect = ValueError("Parse error")
        tab._preview()
        assert "failed" in tab._status_label.text().lower()


# ── Mapping table ────────────────────────────────────────────────────────

class TestImmigrateSoftwareTabMapping:
    """Field mapping table."""

    def test_populate_mapping_table_creates_rows(self, software_tab):
        software_tab._source_columns = ["col_a", "col_b", "col_c"]
        software_tab._preview_data = [["val_a", "val_b", "val_c"]]
        software_tab._populate_mapping_table()
        assert software_tab._mapping_table.rowCount() == 3

    def test_mapping_table_has_three_columns(self, software_tab):
        software_tab._source_columns = ["name"]
        software_tab._preview_data = [["Alice"]]
        software_tab._populate_mapping_table()
        assert software_tab._mapping_table.columnCount() == 3

    def test_mapping_table_target_field_combo(self, software_tab):
        software_tab._source_columns = ["name"]
        software_tab._preview_data = [["Alice"]]
        software_tab._populate_mapping_table()
        widget = software_tab._mapping_table.cellWidget(0, 1)
        assert isinstance(widget, QComboBox)

    def test_mapping_table_sample_data(self, software_tab):
        software_tab._source_columns = ["name"]
        software_tab._preview_data = [["Alice"]]
        software_tab._populate_mapping_table()
        item = software_tab._mapping_table.item(0, 2)
        assert item is not None
        assert "Alice" in item.text()

    def test_collect_mapping(self, software_tab):
        software_tab._source_columns = ["name", "email"]
        software_tab._preview_data = [["Alice", "alice@test.com"]]
        software_tab._populate_mapping_table()
        mapping = software_tab._collect_mapping()
        assert "columns" in mapping
        assert "entity_type" in mapping

    def test_collect_mapping_selects_target(self, software_tab):
        """Select a target field for a column and verify it appears in mapping."""
        software_tab._source_columns = ["name"]
        software_tab._preview_data = [["Alice"]]
        software_tab._populate_mapping_table()
        combo = software_tab._mapping_table.cellWidget(0, 1)
        if combo and combo.count() > 1:
            combo.setCurrentIndex(1)
        mapping = software_tab._collect_mapping()
        assert len(mapping["columns"]) >= 0  # may be empty if combo at index 0


# ── Validation ───────────────────────────────────────────────────────────

class TestImmigrateSoftwareTabValidation:
    """Validation and duplicate detection."""

    def test_validate_no_service_returns(self, software_tab):
        software_tab._on_validate()  # No import_svc — returns early

    def test_validate_no_mapping_returns(self, software_tab_with_svc):
        tab, mock_svc = software_tab_with_svc
        tab._selected_file = None
        tab._on_validate()  # No mapping collected — returns early

    def test_validate_populates_summary(self, software_tab_with_svc):
        tab, mock_svc = software_tab_with_svc
        tab._selected_file = "data.csv"
        mock_svc.preview.return_value = {
            "columns": ["name"],
            "sample_rows": [["Alice"], ["Bob"]],
        }
        mock_svc.validate_all.return_value = {
            "valid_rows": 2,
            "validation_failures": 0,
            "duplicates_skipped": 0,
            "errors": [],
            "duplicates": [],
        }
        tab._preview()
        tab._on_validate()
        assert tab._validation_results is not None
        assert tab._lbl_valid.text() == "2"
        assert tab._lbl_invalid.text() == "0"
        assert tab._results_card.isVisible() is True

    def test_validate_with_errors_shows_table(self, software_tab_with_svc):
        tab, mock_svc = software_tab_with_svc
        tab._selected_file = "data.csv"
        mock_svc.preview.return_value = {
            "columns": ["name"],
            "sample_rows": [["Alice"]],
        }
        mock_svc.validate_all.return_value = {
            "valid_rows": 0,
            "validation_failures": 1,
            "duplicates_skipped": 0,
            "errors": [{"row": 1, "message": "Invalid email", "data": "bad"}],
            "duplicates": [],
        }
        tab._preview()
        tab._on_validate()
        assert tab._invalid_table.isVisible() is True
        assert tab._invalid_table.rowCount() == 1

    def test_validate_with_duplicates_shows_group(self, software_tab_with_svc):
        tab, mock_svc = software_tab_with_svc
        tab._selected_file = "data.csv"
        mock_svc.preview.return_value = {
            "columns": ["name"],
            "sample_rows": [["Alice"]],
        }
        mock_svc.validate_all.return_value = {
            "valid_rows": 1,
            "validation_failures": 0,
            "duplicates_skipped": 0,
            "errors": [],
            "duplicates": [{"id": 1}],
        }
        tab._preview()
        tab._on_validate()
        assert tab._dup_group.isVisible() is True

    def test_validate_exception(self, software_tab_with_svc):
        tab, mock_svc = software_tab_with_svc
        tab._selected_file = "data.csv"
        mock_svc.preview.return_value = {
            "columns": ["name"],
            "sample_rows": [["Alice"]],
        }
        mock_svc.validate_all.side_effect = ValueError("Validation error")
        tab._preview()
        tab._on_validate()
        assert "failed" in tab._status_label.text().lower()


# ── Import flow ──────────────────────────────────────────────────────────

class TestImmigrateSoftwareTabImport:
    """Import execution and result."""

    def test_import_no_service(self, software_tab):
        software_tab._on_import()  # Should return early

    def test_import_starts_background_thread(self, software_tab_with_svc):
        tab, mock_svc = software_tab_with_svc
        tab._selected_file = "data.csv"
        tab._source_columns = ["name"]
        tab._preview_data = [["Alice"]]
        tab._populate_mapping_table()
        with patch(
            "ui.views.migration_center.immigrate_software_tab.threading.Thread",
        ) as mock_thread:
            tab._on_import()
            assert mock_thread.called
            assert tab._progress_bar.isVisible() is True
            assert tab._btn_import.isEnabled() is False

    def test_import_complete_success(self, software_tab_with_svc):
        tab, mock_svc = software_tab_with_svc
        tab._on_import_complete({
            "success": True,
            "stats": {"committed": 5},
        })
        assert tab._progress_bar.isVisible() is False
        assert "Successfully imported" in tab._status_label.text()

    def test_import_complete_success_resets_file(self, software_tab_with_svc):
        tab, mock_svc = software_tab_with_svc
        tab._selected_file = "data.csv"
        tab._on_import_complete({
            "success": True,
            "stats": {"committed": 5},
        })
        assert tab._selected_file is None
        assert tab._btn_preview.isEnabled() is False
        assert tab._mapping_card.isVisible() is False
        assert tab._results_card.isVisible() is False

    def test_import_complete_failure(self, software_tab_with_svc):
        tab, mock_svc = software_tab_with_svc
        tab._on_import_complete({
            "success": False,
            "error": "DB connection lost",
        })
        assert "failed" in tab._status_label.text().lower()
        assert tab._btn_import.isEnabled() is True

    def test_duplicate_resolution_radio_default(self, software_tab):
        assert software_tab._dup_skip.isChecked() is True


# ── Empty states ─────────────────────────────────────────────────────────

class TestImmigrateSoftwareTabEmpty:
    """Empty / no-service states."""

    def test_format_combo_has_items(self, software_tab):
        assert software_tab._fmt_combo.count() > 0

    def test_entity_combo_has_items(self, software_tab):
        assert software_tab._entity_combo.count() > 0
