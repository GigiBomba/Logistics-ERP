"""Tests for the settings view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def settings_view(qt_widget, qtbot, monkeypatch):
    db = MagicMock()
    prefs = MagicMock()
    ops = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.settings_view", fromlist=["QtSettingsView"]).QtSettingsView(
        qt_widget, db=db, prefs=prefs, ops=ops, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

class TestQtSettingsView:
    def test_creation(self, settings_view):
        assert settings_view.db is not None

    def test_company_section_exists(self, settings_view):
        assert hasattr(settings_view, "_company_name")

    def test_brand_color_picker_exists(self, settings_view):
        assert hasattr(settings_view, "_brand_color_btn")

    def test_language_selector_exists(self, settings_view):
        assert hasattr(settings_view, "_lang_combo")

    def test_smtp_host_field_exists(self, settings_view):
        assert hasattr(settings_view, "_smtp_host")

    def test_save_button_exists(self, settings_view):
        assert hasattr(settings_view, "_save_btn")

    def test_wakeup_refreshes(self, settings_view):
        settings_view.prefs.load = MagicMock()
        settings_view.wakeup()
        settings_view.prefs.load.assert_called()

    def test_shutdown_cleanup(self, settings_view):
        settings_view.shutdown()
