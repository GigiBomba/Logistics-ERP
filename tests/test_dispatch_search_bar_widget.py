"""Tests for QtDispatchSearchBar — search/filter bar widget-level tests.

Covers construction, text input, checkbox toggling, clear button, result
count label, debounced input, and cleanup.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel

from ui.widgets.dispatch_search_bar import (
    QtDispatchSearchBar,
    STATUS_OPTIONS,
    _STATUS_COLORS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def search_bar(qtbot):
    """Search bar with a Mock callback."""
    callback = MagicMock()
    bar = QtDispatchSearchBar(on_search=callback)
    qtbot.addWidget(bar)
    yield bar, callback


@pytest.fixture
def search_bar_no_callback(qtbot):
    """Search bar with no callback."""
    bar = QtDispatchSearchBar()
    qtbot.addWidget(bar)
    yield bar


# ── TestQtDispatchSearchBarInit — Construction ────────────────────────────────


class TestQtDispatchSearchBarInit:
    """Verify the widget is created with correct UI elements."""

    def test_creation(self, search_bar):
        bar, _ = search_bar
        assert isinstance(bar, QtDispatchSearchBar)

    def test_creation_with_callback(self, search_bar):
        bar, callback = search_bar
        assert bar._on_search is callback

    def test_ui_elements_exist(self, search_bar):
        bar, _ = search_bar
        assert hasattr(bar, "_entry")
        assert bar._entry is not None
        assert hasattr(bar, "_checkboxes")
        assert len(bar._checkboxes) == 5
        assert hasattr(bar, "_result_lbl")
        assert bar._result_lbl is not None

    def test_status_checkboxes_all_checked_initially(self, search_bar):
        bar, _ = search_bar
        for status in STATUS_OPTIONS:
            cb = bar._checkboxes[status]
            assert cb.isChecked(), f"Checkbox for {status} should be checked"

    def test_colored_dots_exist(self, search_bar):
        """Each status should have a colored dot QLabel with correct style."""
        bar, _ = search_bar
        # Find all 8x8 QLabel dots in the widget hierarchy
        dots = [
            child
            for child in bar.findChildren(QLabel)
            if child.minimumWidth() == 8 and child.minimumHeight() == 8
        ]
        # We expect at least one dot per status
        assert len(dots) >= len(STATUS_OPTIONS)
        # Verify each dot has a background-color stylesheet matching the status color
        stylesheets = {d.styleSheet() for d in dots if "background-color" in (d.styleSheet() or "")}
        for status, color in _STATUS_COLORS.items():
            expected = f"background-color: {color}"
            assert any(expected in ss for ss in stylesheets), (
                f"No dot found with color style for {status} ({color})"
            )


# ── TestQtDispatchSearchBarSearchTextChanged — Text input fires callback ──────


class TestQtDispatchSearchBarSearchTextChanged:
    """Changing the search text should fire the callback with query and statuses."""

    def test_text_change_fires_callback(self, search_bar, qtbot):
        bar, callback = search_bar
        bar._entry.setText("test")
        # Wait for debounce timer (default 300ms)
        qtbot.wait(350)
        callback.assert_called_once()
        args, _ = callback.call_args
        assert args[0] == "test"  # query (lowercase stripped)
        assert sorted(args[1]) == sorted(STATUS_OPTIONS)  # all statuses

    def test_text_change_with_unchecked_statuses(self, search_bar, qtbot):
        bar, callback = search_bar
        # Uncheck "Delivered" and "Cancelled"
        bar._checkboxes["Delivered"].setChecked(False)
        bar._checkboxes["Cancelled"].setChecked(False)
        callback.reset_mock()

        bar._entry.setText("filtered")
        qtbot.wait(350)
        callback.assert_called_once()
        args, _ = callback.call_args
        assert args[0] == "filtered"
        expected_statuses = ["Planned", "Loading", "In Transit"]
        assert sorted(args[1]) == sorted(expected_statuses)


# ── TestQtDispatchSearchBarStatusCheckboxToggle — Checkbox toggle ─────────────


class TestQtDispatchSearchBarStatusCheckboxToggle:
    """Toggling a status checkbox should fire the callback."""

    def test_toggle_fires_callback(self, search_bar, qtbot):
        bar, callback = search_bar
        callback.reset_mock()
        bar._checkboxes["Planned"].setChecked(False)
        qtbot.wait(50)
        callback.assert_called_once()
        args, _ = callback.call_args
        assert "Planned" not in args[1]

    def test_recheck_fires_callback(self, search_bar, qtbot):
        bar, callback = search_bar
        # Uncheck then re-check
        bar._checkboxes["Planned"].setChecked(False)
        callback.reset_mock()
        bar._checkboxes["Planned"].setChecked(True)
        qtbot.wait(50)
        callback.assert_called_once()
        args, _ = callback.call_args
        assert "Planned" in args[1]


# ── TestQtDispatchSearchBarClear — Clear button ───────────────────────────────


class TestQtDispatchSearchBarClear:
    """The clear button should reset the search bar state."""

    def test_clear_resets_text(self, search_bar, qtbot):
        bar, callback = search_bar
        bar._entry.setText("some query")
        qtbot.wait(50)
        bar._clear()
        assert bar._entry.text() == ""

    def test_clear_resets_all_checkboxes(self, search_bar, qtbot):
        bar, callback = search_bar
        bar._checkboxes["Delivered"].setChecked(False)
        bar._checkboxes["Cancelled"].setChecked(False)
        bar._clear()
        for status in STATUS_OPTIONS:
            assert bar._checkboxes[status].isChecked(), (
                f"{status} should be checked after clear"
            )

    def test_clear_fires_search_callback(self, search_bar, qtbot):
        bar, callback = search_bar
        callback.reset_mock()
        bar._clear()
        # _clear calls _fire_search() directly
        callback.assert_called_once()


# ── TestQtDispatchSearchBarResultCount — Result label ─────────────────────────


class TestQtDispatchSearchBarResultCount:
    """set_result_count should update the result count label."""

    def test_result_count_when_filtered(self, search_bar):
        bar, _ = search_bar
        bar.set_result_count(3, 10)
        label = bar._result_lbl
        assert label is not None
        text = label.text()
        assert "3" in text
        assert "10" in text

    def test_result_count_when_all_visible(self, search_bar):
        bar, _ = search_bar
        bar.set_result_count(10, 10)
        label = bar._result_lbl
        assert label is not None
        text = label.text()
        assert "10" in text

    def test_result_count_when_no_label(self, search_bar_no_callback):
        bar = search_bar_no_callback
        bar._result_lbl = None
        # Should not raise
        bar.set_result_count(5, 20)


# ── TestQtDispatchSearchBarNoCallback — No callback ──────────────────────────


class TestQtDispatchSearchBarNoCallback:
    """Operations without a callback should not crash."""

    def test_search_without_callback_no_crash(self, search_bar_no_callback, qtbot):
        bar = search_bar_no_callback
        bar._entry.setText("test")
        qtbot.wait(50)


# ── TestQtDispatchSearchBarDestroy — Cleanup ──────────────────────────────────


class TestQtDispatchSearchBarDestroy:
    """_destroy() should clear references and schedule deletion."""

    def test_destroy_clears_references(self, search_bar):
        bar, callback = search_bar
        bar._destroy()
        assert bar._on_search is None
        assert bar._checkboxes == {}
        assert bar._result_lbl is None


# ── TestQtDispatchSearchBarDebouncedText — Debounce behavior ──────────────────


class TestQtDispatchSearchBarDebouncedText:
    """The debounced text input should not fire on every keystroke."""

    def test_debounce_only_fires_once_after_rapid_changes(
        self, search_bar, qtbot
    ):
        bar, callback = search_bar
        callback.reset_mock()
        # Simulate rapid typing
        for ch in "hello":
            bar._entry.setText(bar._entry.text() + ch)
            qtbot.wait(30)  # small delay but less than debounce (300ms)
        # Wait for debounce timer to fire
        qtbot.wait(400)
        # The callback should have been called at most once (debounced)
        assert callback.call_count == 1
