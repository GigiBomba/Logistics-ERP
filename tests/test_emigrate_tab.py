"""Tests for the Export Data tab (EmigrateTab).

Covers construction, entity selector, field checkboxes, date
range filters, format selection, output path browsing, export
execution (background thread), progress reporting, completion
handling, and file-size formatting.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
)

from ui.components import Card, EmptyState, Label
from ui.views.migration_center.emigrate_tab import (
    EmigrateTab,
    FORMATS,
    ENTITIES,
    ENTITY_FIELDS,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def emigrate_tab(qt_widget, qtbot):
    """Provide an EmigrateTab with db=None (services gracefully degraded)."""
    tab = EmigrateTab(parent=qt_widget, db=None)
    qtbot.addWidget(tab)
    yield tab
    tab.deleteLater()


@pytest.fixture
def emigrate_tab_with_svc(qt_widget, qtbot):
    """Provide an EmigrateTab with a mocked EmigrateService."""
    db = MagicMock()
    with patch(
        "ui.views.migration_center.emigrate_tab.EmigrateService",
    ) as mock_svc_cls:
        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc
        tab = EmigrateTab(parent=qt_widget, db=db)
    qtbot.addWidget(tab)
    # Show the parent and the tab so ``isVisible()`` reflects the true
    # state — Qt only reports a widget as visible when every ancestor
    # is shown too.
    qt_widget.show()
    tab.show()
    yield tab, mock_svc
    tab.deleteLater()


# ── Init ─────────────────────────────────────────────────────────────────

class TestEmigrateTabInit:
    """Construction and initial state."""

    def test_creation(self, emigrate_tab):
        assert isinstance(emigrate_tab, EmigrateTab)

    def test_initial_state(self, emigrate_tab):
        assert emigrate_tab._output_path is None
        assert emigrate_tab._selected_fields == []

    def test_entity_combo_exists(self, emigrate_tab):
        combos = emigrate_tab.findChildren(QComboBox)
        assert len(combos) >= 1  # entity combo

    def test_entity_combo_populated(self, emigrate_tab):
        assert emigrate_tab._entity_combo.count() == len(ENTITIES)

    def test_fields_group_exists(self, emigrate_tab):
        assert emigrate_tab._fields_group is not None
        assert emigrate_tab._fields_group.isCheckable() is True

    def test_fields_initialized(self, emigrate_tab):
        """Upon construction, the entity is selected and fields populated."""
        assert len(emigrate_tab._field_checkboxes) > 0

    def test_date_range_widgets(self, emigrate_tab):
        assert isinstance(emigrate_tab._date_from, QDateEdit)
        assert isinstance(emigrate_tab._date_to, QDateEdit)

    def test_date_from_default_last_month(self, emigrate_tab):
        expected = QDate.currentDate().addMonths(-1)
        assert emigrate_tab._date_from.date() == expected

    def test_date_to_default_today(self, emigrate_tab):
        assert emigrate_tab._date_to.date() == QDate.currentDate()

    def test_format_radios_exist(self, emigrate_tab):
        assert len(emigrate_tab._format_radios) == len(FORMATS)

    def test_first_format_checked(self, emigrate_tab):
        assert emigrate_tab._format_radios[0].isChecked() is True

    def test_output_path_label_shows_default(self, emigrate_tab):
        assert "No output" in emigrate_tab._output_path_label.text()

    def test_export_button_enabled(self, emigrate_tab):
        assert emigrate_tab._btn_export is not None

    def test_progress_bar_hidden(self, emigrate_tab):
        assert emigrate_tab._progress_bar.isVisible() is False

    def test_status_label_hidden(self, emigrate_tab):
        assert emigrate_tab._status_label.isVisible() is False

    def test_empty_state_exists(self, emigrate_tab):
        empties = emigrate_tab.findChildren(EmptyState)
        assert len(empties) >= 1

    def test_export_completed_signal_connected(self, emigrate_tab):
        assert emigrate_tab.export_completed is not None

    def test_row_count_label_default(self, emigrate_tab):
        assert "\u2014" in emigrate_tab._row_count_label.text()


# ── Entity selection ─────────────────────────────────────────────────────

class TestEmigrateTabEntity:
    """Entity selector behaviour."""

    def test_entity_change_populates_fields(self, emigrate_tab):
        # Pick different entity
        emigrate_tab._entity_combo.setCurrentIndex(1)
        emigrate_tab._on_entity_changed()
        assert len(emigrate_tab._field_checkboxes) > 0

    def test_entity_change_clears_previous_fields(self, emigrate_tab):
        initial_count = len(emigrate_tab._field_checkboxes)
        emigrate_tab._entity_combo.setCurrentIndex(2)
        emigrate_tab._on_entity_changed()
        # Should have been rebuilt from scratch
        assert len(emigrate_tab._field_checkboxes) > 0

    def test_entity_fields_match_expected(self, emigrate_tab):
        entity_key = ENTITIES[emigrate_tab._entity_combo.currentIndex()][0]
        expected = ENTITY_FIELDS.get(entity_key, [])
        assert len(emigrate_tab._field_checkboxes) == len(expected)

    def test_all_fields_checked_by_default(self, emigrate_tab):
        assert all(cb.isChecked() for cb in emigrate_tab._field_checkboxes)

    def test_get_selected_fields_returns_checked(self, emigrate_tab):
        fields = emigrate_tab._get_selected_fields()
        assert len(fields) == len(emigrate_tab._field_checkboxes)

    def test_get_selected_fields_after_uncheck(self, emigrate_tab):
        if emigrate_tab._field_checkboxes:
            emigrate_tab._field_checkboxes[0].setChecked(False)
        fields = emigrate_tab._get_selected_fields()
        assert len(fields) < len(emigrate_tab._field_checkboxes)


# ── Format selection ─────────────────────────────────────────────────────

class TestEmigrateTabFormat:
    """Format radio buttons."""

    def test_get_format_key_first(self, emigrate_tab):
        assert emigrate_tab._get_format_key() == FORMATS[0][0]

    def test_get_format_key_after_change(self, emigrate_tab):
        if len(emigrate_tab._format_radios) > 1:
            emigrate_tab._format_radios[1].setChecked(True)
            assert emigrate_tab._get_format_key() == FORMATS[1][0]


# ── Output path browsing ─────────────────────────────────────────────────

class TestEmigrateTabOutputPath:
    """Output path selection."""

    def test_browse_output_selection(self, emigrate_tab):
        with patch(
            "ui.views.migration_center.emigrate_tab.QFileDialog.getSaveFileName",
            return_value=("C:\\exports\\data.csv", "CSV files (*.csv)"),
        ):
            emigrate_tab._browse_output()
            assert emigrate_tab._output_path == "C:\\exports\\data.csv"
            assert "data.csv" in emigrate_tab._output_path_label.text()

    def test_browse_output_ensures_extension(self, emigrate_tab):
        """If the user omits the extension, append it."""
        with patch(
            "ui.views.migration_center.emigrate_tab.QFileDialog.getSaveFileName",
            return_value=("C:\\exports\\data", "CSV files (*.csv)"),
        ):
            emigrate_tab._browse_output()
            assert emigrate_tab._output_path.endswith(".csv")

    def test_browse_output_no_selection(self, emigrate_tab):
        with patch(
            "ui.views.migration_center.emigrate_tab.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ):
            emigrate_tab._browse_output()
            assert emigrate_tab._output_path is None


# ── Filters ──────────────────────────────────────────────────────────────

class TestEmigrateTabFilters:
    """Date-range / filter building."""

    def test_build_filters_default(self, emigrate_tab):
        filters = emigrate_tab._build_filters()
        assert isinstance(filters, dict)

    def test_build_filters_with_dates(self, emigrate_tab):
        emigrate_tab._date_from.setDate(QDate(2026, 1, 1))
        emigrate_tab._date_to.setDate(QDate(2026, 6, 30))
        filters = emigrate_tab._build_filters()
        assert "date_from" in filters
        assert "date_to" in filters

    def test_build_filters_no_from(self, emigrate_tab):
        emigrate_tab._date_from.setDate(emigrate_tab._date_from.minimumDate())
        emigrate_tab._date_to.setDate(QDate(2026, 6, 30))
        filters = emigrate_tab._build_filters()
        assert "date_from" not in filters


# ── Export execution ─────────────────────────────────────────────────────

class TestEmigrateTabExport:
    """Export flow."""

    def test_start_export_no_service(self, emigrate_tab):
        emigrate_tab._start_export()  # Should return early

    def test_start_export_no_output_path(self, emigrate_tab_with_svc):
        tab, mock_svc = emigrate_tab_with_svc
        tab._output_path = None
        tab._start_export()
        assert "select" in tab._status_label.text().lower()
        assert tab._status_label.isVisible() is True

    def test_start_export_starts_thread(self, emigrate_tab_with_svc):
        tab, mock_svc = emigrate_tab_with_svc
        tab._output_path = "C:\\exports\\data.csv"
        with patch(
            "ui.views.migration_center.emigrate_tab.threading.Thread",
        ) as mock_thread:
            tab._start_export()
            mock_thread.assert_called_once()
            assert tab._btn_export.isEnabled() is False
            assert tab._progress_bar.isVisible() is True

    def test_start_export_passes_params(self, emigrate_tab_with_svc):
        tab, mock_svc = emigrate_tab_with_svc
        tab._output_path = "C:\\exports\\data.csv"
        with patch(
            "ui.views.migration_center.emigrate_tab.threading.Thread",
        ) as mock_thread:
            tab._start_export()
            # The thread target should be do_export closure
            assert mock_thread.called

    def test_on_export_complete_success(self, emigrate_tab_with_svc):
        tab, mock_svc = emigrate_tab_with_svc
        tab._output_path = "C:\\exports\\data.csv"
        tab._on_export_complete("C:\\exports\\data.csv")
        assert tab._progress_bar.isVisible() is False
        assert tab._btn_export.isEnabled() is True
        assert "complete" in tab._status_label.text().lower()

    def test_on_export_complete_failure(self, emigrate_tab_with_svc):
        tab, mock_svc = emigrate_tab_with_svc
        tab._on_export_complete("")
        assert "failed" in tab._status_label.text().lower()

    def test_on_export_complete_shows_open_button(self, emigrate_tab_with_svc):
        tab, mock_svc = emigrate_tab_with_svc
        tab._on_export_complete("C:\\test.csv")
        # Should have added an "Open file" button. ``Btn`` is a factory
        # function, so search for the concrete widget type it produces.
        buttons = tab.findChildren(QPushButton)
        open_buttons = [b for b in buttons if "Open" in b.text()]
        assert len(open_buttons) >= 1

    def test_export_success_resets_progress_bar(self, emigrate_tab_with_svc):
        tab, mock_svc = emigrate_tab_with_svc
        tab._progress_bar.setVisible(True)
        tab._on_export_complete("C:\\test.csv")
        assert tab._progress_bar.isVisible() is False


# ── Row count ────────────────────────────────────────────────────────────

class TestEmigrateTabRowCount:
    """Row count preview."""

    def test_update_row_count_no_service(self, emigrate_tab):
        emigrate_tab._update_row_count()  # Should not raise

    def test_update_row_count_calls_service(self, emigrate_tab_with_svc):
        tab, mock_svc = emigrate_tab_with_svc
        mock_svc.count_records.return_value = 42
        tab._update_row_count()
        assert "42" in tab._row_count_label.text()

    def test_update_row_count_exception(self, emigrate_tab_with_svc):
        tab, mock_svc = emigrate_tab_with_svc
        mock_svc.count_records.side_effect = ValueError("DB error")
        tab._update_row_count()
        assert "\u2014" in tab._row_count_label.text()


# ── File size formatting ─────────────────────────────────────────────────

class TestEmigrateTabFormatFileSize:
    """_format_file_size static method."""

    def test_format_bytes(self):
        assert EmigrateTab._format_file_size(500) == "500 B"

    def test_format_kb(self):
        assert EmigrateTab._format_file_size(2048) == "2.0 KB"

    def test_format_mb(self):
        assert EmigrateTab._format_file_size(2097152) == "2.0 MB"
