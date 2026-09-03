"""A4 regression tests: calculator view must load trucks/clients once at init
and skip the redundant reload in the debounced rebuild (manual Refresh forces).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtTest import QTest


def _make_view(qt_widget):
    from ui.views.calculator_view import QtCalculatorView

    fleet = MagicMock()
    fleet.get_trucks.return_value = [
        {"id": 1, "plate_number": "B-100", "model": "Scania", "fuel_consumption": 30.0}
    ]
    clients = MagicMock()
    clients.get_all.return_value = [{"id": 1, "name": "Client A"}]
    view = QtCalculatorView(
        parent=qt_widget,
        db=MagicMock(),
        fleet_service=fleet,
        trip_service=MagicMock(),
        client_service=clients,
        prefs=MagicMock(),
        ops=MagicMock(),
        fuel_service=MagicMock(),
        api=MagicMock(),
        api_client=MagicMock(),
    )
    return view, fleet, clients


def test_trucks_clients_load_once_at_init_and_rebuild_skips(qapp, qtbot, qt_widget):
    view, fleet, clients = _make_view(qt_widget)
    qtbot.addWidget(view)
    QTest.qWait(50)  # let the init singleShots run

    # Loaded exactly once at init.
    assert fleet.get_trucks.call_count == 1
    assert clients.get_all.call_count == 1

    # Debounced rebuild must NOT redundantly re-query (data already present).
    view._do_rebuild_dropdowns()
    assert fleet.get_trucks.call_count == 1
    assert clients.get_all.call_count == 1

    # Manual Refresh forces a reload.
    view._load_trucks(force=True)
    view._load_clients(force=True)
    assert fleet.get_trucks.call_count == 2
    assert clients.get_all.call_count == 2
