"""Tests for the generators view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def generators_view(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.generators_view.QtGeneratorsView._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    prefs = MagicMock()
    client_service = MagicMock()
    fleet_service = MagicMock()
    trip_service = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.generators_view", fromlist=["QtGeneratorsView"]).QtGeneratorsView(
        qt_widget, db=db, prefs=prefs,
        client_service=client_service, fleet_service=fleet_service,
        trip_service=trip_service, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

class TestQtGeneratorsView:
    def test_creation(self, generators_view):
        assert generators_view.db is not None

    def test_invoice_generator_button(self, generators_view):
        assert hasattr(generators_view, "_btn_invoice")

    def test_receipt_generator_button(self, generators_view):
        assert hasattr(generators_view, "_btn_receipt")

    def test_proforma_generator_button(self, generators_view):
        assert hasattr(generators_view, "_btn_proforma")

    def test_cmr_generator_button(self, generators_view):
        assert hasattr(generators_view, "_btn_cmr")

    def test_recent_list_created(self, generators_view):
        assert hasattr(generators_view, "_recent_list")

    def test_shutdown_cleanup(self, generators_view):
        generators_view.shutdown()

    def test_wakeup_does_not_crash(self, generators_view):
        generators_view.wakeup()
