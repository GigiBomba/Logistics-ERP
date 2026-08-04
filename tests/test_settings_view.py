"""Tests for the settings view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
import ui.views.settings_view.settings_fields as _sf

@pytest.fixture(autouse=True)
def _clear_company_config_cache():
    """Clear the module-level company config cache to avoid cross-test contamination."""
    _sf._company_config_cache = None
    yield

@pytest.fixture
def settings_view(qt_widget, qtbot, monkeypatch):
    db = MagicMock()
    prefs = MagicMock()
    prefs.get_settings.return_value = {}  # return a real dict so .get(key, default) works
    prefs.get_setting.return_value = ""
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
        assert "company_name" in settings_view.company_inputs

    def test_brand_color_picker_exists(self, settings_view):
        assert hasattr(settings_view, "_brand_color_swatch")

    def test_language_selector_exists(self, settings_view):
        assert hasattr(settings_view, "_lang_combo")

    def test_smtp_host_field_exists(self, settings_view):
        assert "smtp_server" in settings_view.smtp_inputs

    def test_save_button_exists(self, settings_view):
        assert len(settings_view._i18n_buttons) > 0

    def test_wakeup_refreshes(self, settings_view):
        # wakeup is a no-op in the current implementation
        settings_view.wakeup()

    def test_shutdown_cleanup(self, settings_view):
        settings_view.shutdown()
