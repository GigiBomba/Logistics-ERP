"""Tests for CountryExclusionsPanel — collapsible country exclusions widget."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QFrame

from ui.widgets import StyledCheckBox


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_avoidance():
    """CountryAvoidanceManager with a few countries."""
    mgr = MagicMock()
    mgr.get_all_countries.return_value = {
        "RO": "Romania",
        "HU": "Hungary",
        "BG": "Bulgaria",
        "DE": "Germany",
        "AT": "Austria",
    }
    mgr.get_selected.return_value = ["RO", "BG"]
    return mgr


@pytest.fixture
def panel(qt_widget, qtbot, mock_avoidance):
    """Create CountryExclusionsPanel with mocked avoidance."""
    from ui.views.country_exclusions_panel import CountryExclusionsPanel

    p = CountryExclusionsPanel(
        parent=qt_widget,
        avoidance=mock_avoidance,
        on_change=None,
    )
    qtbot.addWidget(p)
    yield p


@pytest.fixture
def panel_with_callback(qt_widget, qtbot, mock_avoidance):
    """Create CountryExclusionsPanel with a change callback."""
    from ui.views.country_exclusions_panel import CountryExclusionsPanel

    callback = MagicMock()
    p = CountryExclusionsPanel(
        parent=qt_widget,
        avoidance=mock_avoidance,
        on_change=callback,
    )
    qtbot.addWidget(p)
    yield p, callback


# =========================================================================
# Tests
# =========================================================================


class TestCountryExclusionsPanelInit:
    """Construction and default state."""

    def test_creation(self, panel):
        assert panel is not None
        assert panel.avoidance is not None

    def test_initial_collapsed(self, panel):
        """Panel starts collapsed."""
        assert not panel._expanded
        assert not panel._chips_container.isVisible()

    def test_toggle_button_exists(self, panel):
        assert hasattr(panel, "_toggle_btn")
        assert isinstance(panel._toggle_btn, QPushButton)

    def test_header_label_exists(self, panel):
        assert hasattr(panel, "_header_label")
        assert isinstance(panel._header_label, QLabel)

    def test_count_label_exists(self, panel):
        assert hasattr(panel, "_count_label")
        assert isinstance(panel._count_label, QLabel)

    def test_chips_container_exists(self, panel):
        assert hasattr(panel, "_chips_container")
        assert isinstance(panel._chips_container, QFrame)

    def test_checkboxes_populated(self, panel):
        """All countries from avoidance have checkboxes."""
        assert len(panel._checkboxes) == 5

    def test_checkbox_country_codes(self, panel):
        codes = {
            cb.property("country_code") for cb in panel._checkboxes
        }
        assert codes == {"RO", "HU", "BG", "DE", "AT"}

    def test_previously_selected_are_checked(self, panel):
        ro_cb = next(
            cb for cb in panel._checkboxes
            if cb.property("country_code") == "RO"
        )
        bg_cb = next(
            cb for cb in panel._checkboxes
            if cb.property("country_code") == "BG"
        )
        assert ro_cb.isChecked()
        assert bg_cb.isChecked()

    def test_count_label_initial_value(self, panel):
        """Count label shows number of selected countries (2)."""
        assert panel._count_label.text() == "2"

    def test_toggle_triangle_indicator(self, panel):
        """Collapsed state shows right-pointing triangle."""
        assert "\u25b8" in panel._toggle_btn.text()


class TestCountryExclusionsPanelToggle:
    """Collapse/expand behaviour."""

    def test_toggle_expands(self, panel):
        panel._toggle_section()
        assert panel._expanded
        # _toggle_section calls setVisible(True) on the chips container;
        # in headless environments isVisible() may not reflect it, but
        # the text indicator shows the state change.
        assert "\u25be" in panel._toggle_btn.text()  # down triangle

    def test_toggle_collapses(self, panel):
        panel._toggle_section()  # expand
        panel._toggle_section()  # collapse
        assert not panel._expanded
        assert not panel._chips_container.isVisible()
        assert "\u25b8" in panel._toggle_btn.text()  # right triangle

    def test_toggle_click_via_button(self, panel, qtbot):
        qtbot.mouseClick(panel._toggle_btn, Qt.LeftButton)
        assert panel._expanded

    def test_expanded_collapsed_toggle(self, panel):
        panel._toggle_section()
        assert panel._expanded
        panel._toggle_section()
        assert not panel._expanded


class TestCountryExclusionsPanelActions:
    """Country toggle and notification."""

    def test_country_toggle_calls_avoidance(self, panel, mock_avoidance):
        """Toggling a checkbox calls avoidance.toggle."""
        hu_cb = next(
            cb for cb in panel._checkboxes
            if cb.property("country_code") == "HU"
        )
        hu_cb.setChecked(True)
        mock_avoidance.toggle.assert_called_with("HU")

    def test_country_toggle_updates_count(self, panel):
        """Toggling a checkbox updates the count label."""
        hu_cb = next(
            cb for cb in panel._checkboxes
            if cb.property("country_code") == "HU"
        )
        hu_cb.setChecked(True)
        assert panel._count_label.text() == "2"  # still 2 because mock doesn't change

    def test_country_toggle_calls_callback(self, panel_with_callback):
        """Toggling a checkbox invokes the on_change callback."""
        panel, callback = panel_with_callback
        hu_cb = next(
            cb for cb in panel._checkboxes
            if cb.property("country_code") == "HU"
        )
        hu_cb.setChecked(True)
        callback.assert_called_once()

    def test_get_selected_delegates(self, panel, mock_avoidance):
        """get_selected delegates to avoidance.get_selected (called during init too)."""
        panel.get_selected()
        assert mock_avoidance.get_selected.call_count >= 2

    def test_set_selected_refreshes(self, panel, mock_avoidance):
        panel.set_selected(["DE"])
        mock_avoidance.set_selected.assert_called_with(["DE"])

    def test_set_selected_updates_checkboxes(self, panel, mock_avoidance):
        """After set_selected, checkboxes reflect new selection."""
        mock_avoidance.get_selected.return_value = ["DE"]
        panel.set_selected(["DE"])
        de_cb = next(
            cb for cb in panel._checkboxes
            if cb.property("country_code") == "DE"
        )
        assert de_cb.isChecked()
        ro_cb = next(
            cb for cb in panel._checkboxes
            if cb.property("country_code") == "RO"
        )
        assert not ro_cb.isChecked()
        assert panel._count_label.text() == "1"


class TestCountryExclusionsPanelRefresh:
    """Refresh and state management."""

    def test_refresh_updates_checkboxes(self, panel, mock_avoidance):
        """refresh() re-syncs checkboxes with avoidance state."""
        mock_avoidance.get_selected.return_value = ["HU", "AT"]
        panel.refresh()
        hu_cb = next(
            cb for cb in panel._checkboxes
            if cb.property("country_code") == "HU"
        )
        at_cb = next(
            cb for cb in panel._checkboxes
            if cb.property("country_code") == "AT"
        )
        assert hu_cb.isChecked()
        assert at_cb.isChecked()
        assert not any(
            cb.isChecked() and cb.property("country_code") in ("RO", "BG")
            for cb in panel._checkboxes
        )

    def test_refresh_updates_count_label(self, panel, mock_avoidance):
        mock_avoidance.get_selected.return_value = ["HU", "AT", "DE"]
        panel.refresh()
        assert panel._count_label.text() == "3"

    def test_refresh_blocks_signals(self, panel, mock_avoidance):
        """refresh() should not trigger on_change."""
        orig_on_change = MagicMock()
        panel.on_change = orig_on_change
        mock_avoidance.get_selected.return_value = []
        panel.refresh()
        orig_on_change.assert_not_called()

    def test_notify_calls_on_change(self, panel):
        callback = MagicMock()
        panel.on_change = callback
        panel._notify()
        callback.assert_called_once()

    def test_notify_no_callback_does_not_crash(self, panel):
        panel.on_change = None
        panel._notify()  # should not raise

    def test_empty_countries_list(self, qt_widget, qtbot):
        """Panel with no countries does not crash."""
        from ui.views.country_exclusions_panel import CountryExclusionsPanel

        empty_avoidance = MagicMock()
        empty_avoidance.get_all_countries.return_value = {}
        empty_avoidance.get_selected.return_value = []

        p = CountryExclusionsPanel(
            parent=qt_widget,
            avoidance=empty_avoidance,
        )
        qtbot.addWidget(p)
        assert len(p._checkboxes) == 0
        assert p._count_label.text() == "0"
        p._toggle_section()  # should not crash
        p.close()
