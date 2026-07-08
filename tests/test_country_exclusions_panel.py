"""Tests for the country exclusions panel."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestCountryExclusionsPanel:
    def test_creation(self, qt_widget, qtbot):
        from ui.views.country_exclusions_panel import CountryExclusionsPanel
        panel = CountryExclusionsPanel(qt_widget)
        qtbot.addWidget(panel)

    def test_set_excluded_countries(self, qt_widget, qtbot):
        from ui.views.country_exclusions_panel import CountryExclusionsPanel
        panel = CountryExclusionsPanel(qt_widget)
        qtbot.addWidget(panel)
        panel.set_excluded_countries(["HU", "UA", "BG"])

    def test_get_excluded_countries(self, qt_widget, qtbot):
        from ui.views.country_exclusions_panel import CountryExclusionsPanel
        panel = CountryExclusionsPanel(qt_widget)
        qtbot.addWidget(panel)
        countries = panel.get_excluded_countries()
        assert isinstance(countries, list)
