"""Tests for the share route dialog."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def share_route(qt_widget, qtbot):
    route_data = {
        "route_id": "abc123",
        "share_url": "https://example.com/route/abc123",
        "stops": [{"lat": 44.4, "lng": 26.1, "address": "Bucharest"}],
    }
    dlg = __import__("ui.dialogs.share_route_dialog", fromlist=["QtShareRouteDialog"]).QtShareRouteDialog(
        parent=qt_widget, route_data=route_data,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()

class TestQtShareRouteDialog:
    def test_creation(self, share_route):
        assert share_route._route_data is not None

    def test_copy_link_button_exists(self, share_route):
        assert hasattr(share_route, "_btn_copy_url")

    def test_export_button_exists(self, share_route):
        assert hasattr(share_route, "_btn_export_file")

    def test_google_maps_button_exists(self, share_route):
        assert hasattr(share_route, "_btn_google_maps")

    def test_url_displayed(self, share_route):
        assert hasattr(share_route, "_url_label")
        assert len(share_route._url_label.text()) > 0

    def test_dialog_is_modal(self, share_route):
        assert share_route.isModal()
