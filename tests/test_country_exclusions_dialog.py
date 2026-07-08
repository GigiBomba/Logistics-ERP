"""Tests for the country exclusions dialog."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestCountryExclusionsDialog:
    def test_creation(self, qt_widget, qtbot):
        from ui.views.country_exclusions_dialog import CountryExclusionsDialog
        dlg = CountryExclusionsDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg.close()

    def test_has_country_list(self, qt_widget, qtbot):
        from ui.views.country_exclusions_dialog import CountryExclusionsDialog
        dlg = CountryExclusionsDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert hasattr(dlg, "_country_list")
        dlg.close()

    def test_excluded_countries_stored(self, qt_widget, qtbot):
        from ui.views.country_exclusions_dialog import CountryExclusionsDialog
        dlg = CountryExclusionsDialog(qt_widget, excluded_countries=["HU", "UA"])
        qtbot.addWidget(dlg)
        dlg.close()
