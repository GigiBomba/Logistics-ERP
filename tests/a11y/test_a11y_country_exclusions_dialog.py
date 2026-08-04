"""Accessibility tests for CountryExclusionsDialog.

Gap: CountryExclusionsDialog does not set accessibleName or accessibleDescription.
Child StyledCheckBox widgets and QDialogButtonBox buttons also lack accessibleName.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from tests.a11y.conftest import (
    assert_accessible_description_not_empty,
    assert_accessible_name_not_empty,
)


class TestCountryExclusionsDialogA11y:
    """CountryExclusionsDialog — dialog for selecting countries to exclude."""

    @staticmethod
    def _make_avoidance_mock():
        avoidance = MagicMock()
        avoidance.get_all_countries.return_value = {
            "FR": "France",
            "DE": "Germany",
            "IT": "Italy",
            "ES": "Spain",
        }
        avoidance.get_selected.return_value = ["FR"]
        return avoidance

    def test_dialog_accessible_name(self, qt_widget, qtbot):
        """CountryExclusionsDialog should expose an accessibleName (gap)."""
        from ui.views.country_exclusions_dialog import CountryExclusionsDialog

        avoidance = self._make_avoidance_mock()
        dialog = CountryExclusionsDialog(parent=qt_widget, avoidance=avoidance)
        qtbot.addWidget(dialog)
        assert_accessible_name_not_empty(dialog)

    def test_dialog_accessible_description(self, qt_widget, qtbot):
        """CountryExclusionsDialog should expose an accessibleDescription (gap)."""
        from ui.views.country_exclusions_dialog import CountryExclusionsDialog

        avoidance = self._make_avoidance_mock()
        dialog = CountryExclusionsDialog(parent=qt_widget, avoidance=avoidance)
        qtbot.addWidget(dialog)
        assert_accessible_description_not_empty(dialog)

    def test_checkboxes_have_accessible_names(self, qt_widget, qtbot):
        """Each country checkbox should have an accessibleName (gap)."""
        from ui.views.country_exclusions_dialog import CountryExclusionsDialog
        from ui.widgets import StyledCheckBox

        avoidance = self._make_avoidance_mock()
        dialog = CountryExclusionsDialog(parent=qt_widget, avoidance=avoidance)
        qtbot.addWidget(dialog)
        checkboxes = dialog.findChildren(StyledCheckBox)
        assert len(checkboxes) >= 1, "Expected at least one StyledCheckBox"
        for cb in checkboxes:
            assert_accessible_name_not_empty(cb)

    def test_dialog_button_box_buttons_have_accessible_names(self, qt_widget, qtbot):
        """OK and Cancel buttons should have accessibleNames (gap)."""
        from ui.views.country_exclusions_dialog import CountryExclusionsDialog
        from PySide6.QtWidgets import QDialogButtonBox

        avoidance = self._make_avoidance_mock()
        dialog = CountryExclusionsDialog(parent=qt_widget, avoidance=avoidance)
        qtbot.addWidget(dialog)
        button_box = dialog.findChild(QDialogButtonBox)
        assert button_box is not None, "QDialogButtonBox not found"
        for btn in button_box.buttons():
            assert_accessible_name_not_empty(btn)

    def test_country_checkbox_count(self, qt_widget, qtbot):
        """Number of checkboxes should match number of countries returned."""
        from ui.views.country_exclusions_dialog import CountryExclusionsDialog
        from ui.widgets import StyledCheckBox

        avoidance = self._make_avoidance_mock()
        dialog = CountryExclusionsDialog(parent=qt_widget, avoidance=avoidance)
        qtbot.addWidget(dialog)
        checkboxes = dialog.findChildren(StyledCheckBox)
        expected = len(avoidance.get_all_countries())
        assert len(checkboxes) == expected, (
            f"Expected {expected} checkboxes, found {len(checkboxes)}"
        )
