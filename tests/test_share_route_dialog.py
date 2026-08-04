"""Tests for the share route dialog."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

from ui.dialogs.share_route_dialog import ShareRouteDialog

@pytest.fixture
def share_route(qt_widget, qtbot):
    dlg = ShareRouteDialog(
        parent=qt_widget,
        share_url="https://example.com/route/abc123",
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()

class TestQtShareRouteDialog:
    def test_creation(self, share_route):
        assert share_route._share_url is not None

    def test_copy_link_button_exists(self, share_route):
        assert hasattr(share_route, "_url_field")

    def test_export_button_exists(self, share_route):
        assert hasattr(share_route, "_on_export_file_cb")

    def test_google_maps_button_exists(self, share_route):
        assert hasattr(share_route, "_on_open_in_gmaps_cb")

    def test_url_displayed(self, share_route):
        assert hasattr(share_route, "_url_field")
        assert len(share_route._url_field.text()) > 0

    def test_dialog_is_modal(self, share_route):
        assert share_route.isModal()
