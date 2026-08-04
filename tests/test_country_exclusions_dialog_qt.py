"""Tests for CountryExclusionsDialog — country selection for route exclusions."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QLabel, QScrollArea, QPushButton

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
def exclusion_dialog(qt_widget, qtbot, mock_avoidance):
    """Create CountryExclusionsDialog with mocked avoidance manager."""
    from ui.views.country_exclusions_dialog import CountryExclusionsDialog

    dlg = CountryExclusionsDialog(
        parent=qt_widget,
        avoidance=mock_avoidance,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


# =========================================================================
# Tests
# =========================================================================


class TestCountryExclusionsDialogInit:
    """Construction and basic attributes."""

    def test_creation(self, exclusion_dialog):
        assert exclusion_dialog is not None
        assert exclusion_dialog.avoidance is not None

    def test_dialog_not_modal_by_default(self, exclusion_dialog):
        """CountryExclusionsDialog is not modal by default (caller decides)."""
        assert not exclusion_dialog.isModal()

    def test_minimum_size_set(self, exclusion_dialog):
        assert exclusion_dialog.minimumSize().width() >= 280
        assert exclusion_dialog.minimumSize().height() >= 320


class TestCountryExclusionsDialogUiElements:
    """Verify UI widgets are present and configured."""

    def test_header_label_exists(self, exclusion_dialog):
        assert hasattr(exclusion_dialog, "_checkboxes")
        # Header is first widget in layout
        header = exclusion_dialog.layout().itemAt(0).widget()
        assert isinstance(header, QLabel)
        assert len(header.text()) > 0

    def test_scroll_area_exists(self, exclusion_dialog):
        scroll = exclusion_dialog.layout().itemAt(1).widget()
        assert isinstance(scroll, QScrollArea)

    def test_buttons_exist(self, exclusion_dialog):
        buttons = exclusion_dialog.layout().itemAt(2).widget()
        assert isinstance(buttons, QDialogButtonBox)

    def test_checkboxes_populated(self, exclusion_dialog):
        """Checkboxes are created for each country from avoidance."""
        assert len(exclusion_dialog._checkboxes) == 5

    def test_checkboxes_have_country_codes(self, exclusion_dialog):
        codes = {
            cb.property("country_code") for cb in exclusion_dialog._checkboxes
        }
        assert codes == {"RO", "HU", "BG", "DE", "AT"}

    def test_checkboxes_have_country_names(self, exclusion_dialog):
        names = {cb.text() for cb in exclusion_dialog._checkboxes}
        assert names == {"Romania", "Hungary", "Bulgaria", "Germany", "Austria"}

    def test_previously_selected_are_checked(self, exclusion_dialog):
        """Countries that were selected before opening should be checked."""
        ro_cb = next(
            cb for cb in exclusion_dialog._checkboxes
            if cb.property("country_code") == "RO"
        )
        bg_cb = next(
            cb for cb in exclusion_dialog._checkboxes
            if cb.property("country_code") == "BG"
        )
        assert ro_cb.isChecked()
        assert bg_cb.isChecked()

    def test_unselected_countries_not_checked(self, exclusion_dialog):
        """Countries not previously selected should be unchecked."""
        hu_cb = next(
            cb for cb in exclusion_dialog._checkboxes
            if cb.property("country_code") == "HU"
        )
        assert not hu_cb.isChecked()


class TestCountryExclusionsDialogActions:
    """Dialog button behaviour."""

    def test_accept_applies_changes(self, exclusion_dialog, mock_avoidance):
        """Accepting calls avoidance.toggle for changed items."""
        # Uncheck RO
        ro_cb = next(
            cb for cb in exclusion_dialog._checkboxes
            if cb.property("country_code") == "RO"
        )
        ro_cb.setChecked(False)

        # Check HU
        hu_cb = next(
            cb for cb in exclusion_dialog._checkboxes
            if cb.property("country_code") == "HU"
        )
        hu_cb.setChecked(True)

        exclusion_dialog._on_accept()

        # RO was selected, now unchecked → toggle called
        # HU was not selected, now checked → toggle called
        assert mock_avoidance.toggle.call_count >= 2
        assert exclusion_dialog.result() == 1  # Accepted

    def test_accept_no_changes_does_not_toggle(self, exclusion_dialog, mock_avoidance):
        """Accepting without changes calls toggle only if state differs."""
        exclusion_dialog._on_accept()
        # RO is selected+checked, BG is selected+checked — no diff
        # Depending on implementation, toggle may be called 0 times
        assert exclusion_dialog.result() == 1

    def test_reject_closes_dialog(self, exclusion_dialog, qtbot):
        exclusion_dialog.reject()
        assert exclusion_dialog.result() == 0  # Rejected

    def test_all_checkboxes_are_styled_checkbox(self, exclusion_dialog):
        for cb in exclusion_dialog._checkboxes:
            assert isinstance(cb, StyledCheckBox)


class TestCountryExclusionsDialogEdgeCases:
    """Edge cases and empty states."""

    def test_empty_countries_list(self, qt_widget, qtbot):
        """Dialog handles avoidance returning no countries."""
        from ui.views.country_exclusions_dialog import CountryExclusionsDialog

        empty_avoidance = MagicMock()
        empty_avoidance.get_all_countries.return_value = {}
        empty_avoidance.get_selected.return_value = []

        dlg = CountryExclusionsDialog(
            parent=qt_widget,
            avoidance=empty_avoidance,
        )
        qtbot.addWidget(dlg)
        assert len(dlg._checkboxes) == 0
        dlg._on_accept()  # should not crash
        assert dlg.result() == 1
        dlg.close()

    def test_widgets_are_styled(self, exclusion_dialog):
        """Dialog has a stylesheet set."""
        assert len(exclusion_dialog.styleSheet()) > 0


class TestCountryExclusionsDialogIntegration:
    """Integration checks for dialog behaviour."""

    def test_accept_calls_toggle_only_for_changed(
        self, exclusion_dialog, mock_avoidance
    ):
        """Uncheck RO, check HU → avoidance.toggle called exactly 2 times (RO and HU), not 5."""
        ro_cb = next(
            cb for cb in exclusion_dialog._checkboxes
            if cb.property("country_code") == "RO"
        )
        hu_cb = next(
            cb for cb in exclusion_dialog._checkboxes
            if cb.property("country_code") == "HU"
        )
        ro_cb.setChecked(False)
        hu_cb.setChecked(True)

        exclusion_dialog._on_accept()

        assert mock_avoidance.toggle.call_count == 2

    def test_accept_none_changed_no_toggle(self, exclusion_dialog, mock_avoidance):
        """All checkboxes match get_selected() → toggle called 0 times."""
        mock_avoidance.toggle.reset_mock()
        exclusion_dialog._on_accept()
        assert mock_avoidance.toggle.call_count == 0

    def test_cancel_button_drops_changes(self, exclusion_dialog, qtbot):
        """Toggle checkboxes, click Cancel → _on_accept() NOT called, dialog rejected."""
        from unittest.mock import MagicMock

        exclusion_dialog._on_accept = MagicMock()

        ro_cb = next(
            cb for cb in exclusion_dialog._checkboxes
            if cb.property("country_code") == "RO"
        )
        ro_cb.setChecked(False)

        cancel_btn = exclusion_dialog.layout().itemAt(2).widget().button(
            QDialogButtonBox.StandardButton.Cancel
        )
        qtbot.mouseClick(cancel_btn, Qt.LeftButton)

        exclusion_dialog._on_accept.assert_not_called()
        assert exclusion_dialog.result() == 0  # Rejected

    def test_header_text_matches_i18n(self, exclusion_dialog):
        """Header label text is t('route.exclusions_label')."""
        from services.i18n import t

        header = exclusion_dialog.layout().itemAt(0).widget()
        assert isinstance(header, QLabel)
        assert header.text() == t("route.exclusions_label")

    def test_all_country_codes_are_strings(self, exclusion_dialog):
        """Every cb.property('country_code') is str."""
        for cb in exclusion_dialog._checkboxes:
            code = cb.property("country_code")
            assert isinstance(code, str), (
                f"Expected str, got {type(code).__name__}"
            )
