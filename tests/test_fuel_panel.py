"""Tests for the fuel panel widget (modern PySide6 API).

The widget was renamed ``QtFuelPanel`` -> ``QtFuelPricePanel`` during the
PySide6 migration; the old ``set_fuel_price``/``set_country``/``update_timestamp``
methods were replaced by the collapsible ``QtFuelPricePanel`` API
(``refresh``/``_toggle``/``_draw_chart``/``_update_status``).
"""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

from ui.widgets.fuel_panel import QtFuelPricePanel


class TestQtFuelPanel:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.fuel_panel import QtFuelPricePanel
        panel = QtFuelPricePanel(qt_widget)
        qtbot.addWidget(panel)
        assert panel._body.isVisible() is False  # starts collapsed

    def test_refresh_draws_prices(self, qt_widget, qtbot):
        """refresh() updates the status label from the fuel service."""
        from ui.widgets.fuel_panel import QtFuelPricePanel
        panel = QtFuelPricePanel(qt_widget)
        qtbot.addWidget(panel)
        panel._fuel_service = MagicMock(
            last_updated_str=MagicMock(return_value="01/01/2026 12:00"),
            age_seconds=MagicMock(return_value=30),
            get_prices_all=MagicMock(return_value={"RO": 1.85, "DE": 1.72}),
        )
        panel.refresh()
        assert panel._status_lbl.text() != ""

    def test_toggle_expands_body(self, qt_widget, qtbot):
        """_toggle() shows the collapsible chart body."""
        from ui.widgets.fuel_panel import QtFuelPricePanel
        panel = QtFuelPricePanel(qt_widget)
        qtbot.addWidget(panel)
        assert panel._expanded is False
        assert panel._body.isHidden() is True
        panel._toggle()
        assert panel._expanded is True
        assert panel._body.isHidden() is False
        panel._toggle()
        assert panel._expanded is False
        assert panel._body.isHidden() is True

    def test_update_status_sets_label(self, qt_widget, qtbot):
        """_update_status() renders the 'not fetched' status when no data."""
        from ui.widgets.fuel_panel import QtFuelPricePanel
        panel = QtFuelPricePanel(qt_widget)
        qtbot.addWidget(panel)
        panel._fuel_service = MagicMock(
            last_updated_str=MagicMock(return_value="never"),
            age_seconds=MagicMock(return_value=None),
        )
        panel._update_status()
        assert panel._status_lbl.text() != ""

    def test_draw_chart_empty(self, qt_widget, qtbot):
        """_draw_chart() with no prices clears the chart without crashing."""
        from ui.widgets.fuel_panel import QtFuelPricePanel
        panel = QtFuelPricePanel(qt_widget)
        qtbot.addWidget(panel)
        panel._fuel_service = MagicMock(get_prices_all=MagicMock(return_value={}))
        panel._draw_chart()  # should not raise
        assert panel._chart._prices == []
