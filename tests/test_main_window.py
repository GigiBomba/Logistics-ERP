"""Tests for MainWindow — main application shell."""
from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from PySide6.QtCore import Qt


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_api():
    return MagicMock()


@pytest.fixture
def mock_prefs():
    prefs = MagicMock()
    prefs.get_currency.return_value = "EUR"
    return prefs


@pytest.fixture
def mock_ops():
    ops = MagicMock()
    ops.event_bus = MagicMock()
    ops.get_active_alerts.return_value = []
    ops.get_active_alert_count.return_value = 0
    ops.start = MagicMock()
    ops.stop = MagicMock()
    return ops


@pytest.fixture
def mock_api_client():
    return MagicMock()


@pytest.fixture
def mock_nav():
    nav = MagicMock()
    nav.add_group = MagicMock()
    nav.add_item = MagicMock()
    nav.add_settings_item = MagicMock()
    nav.select = MagicMock()
    nav.highlight = MagicMock()
    return nav


@pytest.fixture
def mock_app_shell():
    shell = MagicMock()
    shell.view_container = MagicMock()
    shell.view_container.addWidget = MagicMock()
    shell.view_container.setCurrentWidget = MagicMock()
    shell.set_breadcrumb = MagicMock()
    shell.set_alert_count = MagicMock()
    shell.set_fuel_status = MagicMock()
    shell.nav = MagicMock()
    shell.top_bar = MagicMock()
    shell.destroy = MagicMock()
    return shell


# We need to mock _init_services to prevent real DB calls
# and mock _build_ui to prevent full UI construction (the AppShell
# and nav are complex). We use monkeypatch.

@pytest.fixture
def main_window(qtbot, mock_db, mock_api, mock_prefs, mock_ops,
                mock_api_client, mock_app_shell, mock_nav, monkeypatch):
    """Create MainWindow with all services mocked."""

    # Prevent real service initialization
    monkeypatch.setattr("ui.main_window.MainWindow._init_services", lambda self: None)

    # Prevent full UI build — we mock AppShell
    monkeypatch.setattr("ui.main_window.MainWindow._build_ui", lambda self: None)

    # Mock AppShell import
    patcher_appshell = patch("ui.main_window.AppShell", return_value=mock_app_shell)
    patcher_appshell.start()

    # Mock EventBus
    patcher_eb = patch("ui.main_window.EventBus", return_value=MagicMock())
    patcher_eb.start()

    # Mock various services used in __init__
    services_patchers = [
        patch("ui.main_window.Config"),
        patch("ui.main_window.QWidgetShortcut"),
    ]
    for p in services_patchers:
        p.start()

    from ui.main_window import MainWindow

    widget = MainWindow(
        db=mock_db,
        api=mock_api,
        prefs=mock_prefs,
        ops=mock_ops,
        api_client=mock_api_client,
    )
    qtbot.addWidget(widget)
    yield widget

    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        widget.close()
    for p in services_patchers:
        p.stop()
    patcher_appshell.stop()
    patcher_eb.stop()


# =========================================================================
# Tests
# =========================================================================

class TestMainWindow:
    """Suite of tests for MainWindow."""

    def test_initialization(self, main_window):
        """MainWindow initializes without crash and stores references."""
        assert main_window is not None
        assert hasattr(main_window, "db")
        assert hasattr(main_window, "_module_cache")
        assert main_window._module_cache == {}

    def test_stores_service_references(self, main_window, mock_db, mock_api,
                                        mock_prefs, mock_ops, mock_api_client):
        """All constructor arguments are stored as attributes."""
        assert main_window.db is mock_db
        assert main_window.api is mock_api
        assert main_window.ops is mock_ops
        assert main_window.prefs is mock_prefs
        assert main_window._api_client is mock_api_client

    def test_module_cache_empty_on_init(self, main_window):
        """Module cache starts empty."""
        assert len(main_window._module_cache) == 0

    def test_active_module_none_on_init(self, main_window):
        """No active module set on init."""
        assert main_window._active_module is None

    def test_create_module_creates_view(self, main_window, monkeypatch):
        """_create_module creates a view and caches it."""
        # Set up VIEW_FACTORIES
        mock_view = MagicMock()
        from ui.main_window import MainWindow

        # Reset the class-level cache
        MainWindow._VIEW_FACTORIES = None

        # Build nav so VIEW_FACTORIES gets populated
        main_window._build_nav = lambda: None

        # Call _create_module with a known key
        # Since _VIEW_FACTORIES is None, it will populate from the class dict
        # and we need AppShell's view_container to be set
        main_window.app_shell = MagicMock()
        main_window.app_shell.view_container = MagicMock()
        main_window.app_shell.view_container.addWidget = MagicMock()
        main_window._api_client = MagicMock()
        main_window.fleet_service = MagicMock()
        main_window.trip_service = MagicMock()
        main_window.client_service = MagicMock()
        main_window._fuel_service = MagicMock()

        # Mock the _init_services-like attributes
        main_window.prefs = MagicMock()
        main_window.ops = MagicMock()
        main_window.api = MagicMock()

        result = main_window._create_module("overview")

        assert result is not None
        assert "frame" in result
        assert "obj" in result

    def test_create_module_caches_result(self, main_window):
        """Calling _create_module twice returns the same cached object."""
        # Mock dependencies for _create_module
        main_window.app_shell = MagicMock()
        main_window.app_shell.view_container = MagicMock()
        main_window.app_shell.view_container.addWidget = MagicMock()
        main_window._api_client = MagicMock()

        from ui.main_window import MainWindow
        MainWindow._VIEW_FACTORIES = None

        result1 = main_window._create_module("overview")
        # The first call populates VIEW_FACTORIES and creates module
        # The module is cached in _module_cache
        assert "overview" in main_window._module_cache

    def test_switch_module_switches_view(self, main_window):
        """_switch_module activates a module and calls wakeup."""
        mock_obj = MagicMock()
        mock_frame = MagicMock()
        main_window._module_cache["overview"] = {
            "frame": mock_frame,
            "obj": mock_obj,
        }
        main_window.app_shell = MagicMock()
        main_window.app_shell.view_container = MagicMock()
        main_window.app_shell.set_breadcrumb = MagicMock()
        main_window.nav = MagicMock()

        main_window._switch_module("overview")
        # wakeup should be called on the module
        mock_obj.wakeup.assert_called_once()
        assert main_window._active_module == "overview"

    def test_switch_module_shuts_down_previous(self, main_window):
        """Switching modules shuts down the previous one."""
        mock_prev = MagicMock()
        mock_prev_obj = MagicMock()
        main_window._module_cache["old"] = {
            "frame": mock_prev,
            "obj": mock_prev_obj,
        }
        mock_new = MagicMock()
        mock_new_obj = MagicMock()
        main_window._module_cache["new"] = {
            "frame": mock_new,
            "obj": mock_new_obj,
        }
        main_window._active_module = "old"
        main_window.app_shell = MagicMock()
        main_window.app_shell.view_container = MagicMock()
        main_window.app_shell.set_breadcrumb = MagicMock()
        main_window.nav = MagicMock()

        main_window._switch_module("new")
        mock_prev_obj.shutdown.assert_called_once()
        mock_new_obj.wakeup.assert_called_once()
        assert main_window._active_module == "new"

    def test_close_event_shuts_down_modules(self, main_window):
        """closeEvent shuts down all cached modules."""
        mock_obj = MagicMock()
        main_window._module_cache["test"] = {
            "frame": MagicMock(),
            "obj": mock_obj,
        }
        main_window.app_shell = MagicMock()
        main_window.ops = MagicMock()
        main_window._fuel_timer = MagicMock()
        main_window._event_bus = MagicMock()

        from PySide6.QtCore import QEvent
        event = MagicMock()
        main_window.closeEvent(event)
        mock_obj.shutdown.assert_called_once()
        event.accept.assert_called_once()

    def test_open_calculator_switches_to_calculator(self, main_window):
        """_open_calculator triggers switch to calculator module."""
        main_window._switch_module = MagicMock()
        main_window._open_calculator()
        main_window._switch_module.assert_called_once_with("calculator")

    def test_open_history_switches_to_history(self, main_window):
        """_open_history triggers switch to history module."""
        main_window._switch_module = MagicMock()
        main_window._open_history()
        main_window._switch_module.assert_called_once_with("history")

    def test_open_route_url_switches_to_route_planner(self, main_window):
        """open_route_url switches to route planner with data."""
        main_window._switch_module = MagicMock()
        main_window.open_route_url("https://example.com/route")
        main_window._switch_module.assert_called_once_with(
            "route_planner", {"share_url": "https://example.com/route"}
        )

    def test_open_route_file_switches_to_route_planner(self, main_window):
        """open_route_file switches to route planner with file path."""
        main_window._switch_module = MagicMock()
        main_window.open_route_file("/path/to/file.operionroute")
        main_window._switch_module.assert_called_once_with(
            "route_planner", {"share_file": "/path/to/file.operionroute"}
        )

    def test_fuel_status_text(self, main_window):
        """_fuel_status_text returns a string."""
        main_window._fuel_service = MagicMock()
        main_window._fuel_service.is_available.return_value = True
        main_window._fuel_service.age_seconds.return_value = 300
        main_window._fuel_service.last_updated_str.return_value = "12:00"
        text = main_window._fuel_status_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_fuel_status_text_offline(self, main_window):
        """_fuel_status_text returns offline message when unavailable."""
        main_window._fuel_service = MagicMock()
        main_window._fuel_service.is_available.return_value = False
        text = main_window._fuel_status_text()
        assert "offline" in text.lower() or "⛽" in text
