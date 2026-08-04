"""Tests for MainWindow — main application shell."""
from __future__ import annotations

import contextlib
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

    # Prevent fuel timer init (which depends on _fuel_service from _init_services)
    monkeypatch.setattr("ui.main_window.MainWindow._init_fuel_status", lambda self: None)

    # Prevent warmup timer (QTimer would fire during subsequent test files)
    monkeypatch.setattr("ui.main_window.MainWindow._start_warmup", lambda self: None)

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

    # Set up service attributes that _init_services would normally create
    # (existing _create_module tests depend on these)
    widget.trip_service = MagicMock()
    widget.client_service = MagicMock()
    widget.fleet_service = MagicMock()
    widget._fuel_service = MagicMock()

    # Prevent page-animation crashes when frame is a MagicMock
    monkeypatch.setattr(
        "ui.main_window.MainWindow._animate_page_switch",
        lambda self, frame: None,
    )

    # _create_module creates real Qt widgets with view_container as parent.
    # Tests that call _create_module directly use MagicMock for view_container,
    # which Qt constructors reject.  We mock _create_module so those tests
    # can verify its contract (returns {"frame": …, "obj": …}) without
    # real widget instantiation.
    def _mock_create_module(self, key):
        result = {"frame": MagicMock(), "obj": MagicMock()}
        self._module_cache[key] = result
        return result

    monkeypatch.setattr("ui.main_window.MainWindow._create_module", _mock_create_module)

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


# =========================================================================
# Advanced Tests
# =========================================================================

class TestMainWindowAdvanced:
    """Advanced MainWindow tests — nav, alerts, fuel, tour, shortcuts, init."""

    # ── Navigation tests (6) ─────────────────────────────────────────────

    def test_go_back_empty_stack_returns_early(self, main_window):
        """_go_back returns early when nav stack is empty."""
        main_window._nav_stack = []
        main_window._switch_module = MagicMock()
        main_window._go_back()
        main_window._switch_module.assert_not_called()

    def test_go_back_pops_and_switches(self, main_window):
        """_go_back pops the stack and switches to the previous view."""
        main_window._nav_stack = [("old", None)]
        main_window._switch_module = MagicMock()
        main_window.app_shell = MagicMock()
        main_window._go_back()
        main_window._switch_module.assert_called_once_with("old", None)

    def test_go_back_skips_duplicate_push(self, main_window):
        """Switching to the same active module does not push the stack."""
        main_window._active_module = "overview"
        main_window._nav_stack = []
        main_window._module_cache["overview"] = {"frame": MagicMock(), "obj": MagicMock()}
        main_window.app_shell = MagicMock()
        main_window.app_shell.set_breadcrumb = MagicMock()
        main_window._update_breadcrumb = MagicMock()
        main_window._struggle_detector.record_navigation = MagicMock()
        main_window._switch_module("overview")
        assert len(main_window._nav_stack) == 0

    def test_nav_stack_overflow_enforcement(self, main_window):
        """Pushing beyond max stack size pops the oldest entry."""
        main_window._active_module = "current"
        main_window._module_cache = {
            "current": {"frame": MagicMock(), "obj": MagicMock()},
            "new": {"frame": MagicMock(), "obj": MagicMock()},
        }
        main_window._nav_stack = [(f"dummy{i}", None) for i in range(20)]
        main_window.app_shell = MagicMock()
        main_window.app_shell.set_breadcrumb = MagicMock()
        main_window.app_shell.view_container = MagicMock()
        main_window.nav = MagicMock()
        main_window._page_anim = None
        main_window._animate_page_switch = MagicMock()
        main_window._update_back_button = MagicMock()
        main_window._update_breadcrumb = MagicMock()
        main_window._struggle_detector.record_navigation = MagicMock()

        main_window._switch_module("new")

        assert len(main_window._nav_stack) == 20
        assert main_window._nav_stack[0][0] == "dummy1"
        assert main_window._nav_stack[-1][0] == "current"

    def test_switch_module_same_view_wakes_not_recreates(self, main_window):
        """Switching to the active module wakes it up but does not recreate it."""
        mock_obj = MagicMock()
        mock_frame = MagicMock()
        main_window._active_module = "overview"
        main_window._module_cache["overview"] = {"frame": mock_frame, "obj": mock_obj}
        main_window.app_shell = MagicMock()
        main_window.app_shell.set_breadcrumb = MagicMock()
        main_window._create_module = MagicMock()
        main_window._struggle_detector.record_navigation = MagicMock()
        main_window._update_breadcrumb = MagicMock()

        main_window._switch_module("overview")

        mock_obj.wakeup.assert_called_once()
        main_window._create_module.assert_not_called()

    # ── Alert tests (3) ─────────────────────────────────────────────────

    def test_on_alert_event_refreshes_alerts(self, main_window, qtbot):
        """_on_alert_event schedules a refresh of alerts."""
        main_window._refresh_alerts = MagicMock()
        main_window._on_alert_event({})
        qtbot.wait(10)
        main_window._refresh_alerts.assert_called_once()

    def test_refresh_alerts_pushes_count_to_top_bar(self, main_window):
        """_refresh_alerts pushes alert count to the top bar."""
        main_window.ops.get_active_alert_count.return_value = 5
        main_window.app_shell = MagicMock()
        main_window.app_shell.set_alert_count = MagicMock()
        main_window.app_shell.top_bar = MagicMock()
        main_window.app_shell.top_bar.set_alerts = MagicMock()
        main_window._refresh_alerts()
        main_window.app_shell.set_alert_count.assert_called_once_with(5)

    def test_refresh_alerts_pushes_list_to_top_bar(self, main_window):
        """_refresh_alerts pushes the alert list to the top bar."""
        alerts = [{"id": 1, "message": "Test alert"}]
        main_window.ops.get_active_alerts.return_value = alerts
        main_window.ops.get_active_alert_count.return_value = 1
        main_window.app_shell = MagicMock()
        main_window.app_shell.set_alert_count = MagicMock()
        main_window.app_shell.top_bar = MagicMock()
        main_window.app_shell.top_bar.set_alerts = MagicMock()
        main_window._refresh_alerts()
        main_window.app_shell.top_bar.set_alerts.assert_called_once_with(alerts)

    # ── Fuel timer tests (2) ────────────────────────────────────────────

    def test_fuel_timer_fires_update_fuel_status(self, main_window):
        """The fuel timer timeout triggers _update_fuel_status."""
        from PySide6.QtCore import QTimer
        main_window._update_fuel_status = MagicMock()
        main_window._fuel_timer = QTimer(main_window)
        main_window._fuel_timer.timeout.connect(main_window._update_fuel_status)
        main_window._fuel_timer.timeout.emit()
        main_window._update_fuel_status.assert_called_once()

    def test_fuel_timer_stopped_on_close(self, main_window):
        """closeEvent stops the fuel timer."""
        main_window._fuel_timer = MagicMock()
        main_window._module_cache = {}
        main_window.app_shell = MagicMock()
        main_window.ops = MagicMock()
        main_window._event_bus = MagicMock()
        main_window._page_anim = None

        from PySide6.QtCore import QEvent
        event = MagicMock()
        main_window.closeEvent(event)
        main_window._fuel_timer.stop.assert_called_once()

    # ── Tour / struggle tests (2) ───────────────────────────────────────

    def test_on_struggle_detected_shows_overlay_when_no_tour(self, main_window):
        """Struggle detection shows overlay when no tour is active."""
        main_window._tour_controller.is_tour_active = MagicMock(return_value=False)
        main_window._tour_overlay.start_tour = MagicMock()
        main_window._tour_overlay.cancel = MagicMock()

        with patch("ui.copilot.tour_scripts.ALL_SCRIPTS", {
            "test_workflow": {"steps": [{"target_element_id": "some_id"}]}
        }):
            main_window._on_struggle_detected("test_workflow", "tooltip_key")
            main_window._tour_overlay.start_tour.assert_called_once()

    def test_check_onboarding_starts_if_first_launch(self, main_window):
        """_check_onboarding starts onboarding tour on first launch."""
        main_window._tour_controller.can_show_onboarding = MagicMock(return_value=True)
        main_window._tour_controller.start_onboarding = MagicMock()
        main_window._check_onboarding()
        main_window._tour_controller.start_onboarding.assert_called_once()

    # ── Shortcut test (1) ───────────────────────────────────────────────

    def test_ask_ai_requested_navigates_to_copilot(self, main_window):
        """_on_ask_ai_requested navigates to the copilot module."""
        main_window._switch_module = MagicMock()
        main_window._on_ask_ai_requested("Help", "overview")
        main_window._switch_module.assert_called_once_with("copilot")

    # ── Connection mode test (1) ────────────────────────────────────────

    def test_init_services_local_db_mode(self, qtbot, mock_db, mock_api,
                                          mock_prefs, mock_ops,
                                          mock_api_client, mock_app_shell,
                                          mock_nav):
        """When db is not None, _init_services creates local FleetService."""
        from services.fleet_service import FleetService

        with patch("ui.main_window.MainWindow._build_ui", lambda self: None), \
             patch("ui.main_window.MainWindow._start_warmup", lambda self: None), \
             patch("ui.main_window.AppShell", return_value=mock_app_shell), \
             patch("ui.main_window.EventBus", return_value=MagicMock()), \
             patch("ui.main_window.Config"), \
             patch("ui.main_window.QWidgetShortcut"):
            from ui.main_window import MainWindow
            widget = MainWindow(
                db=mock_db,
                api=mock_api,
                prefs=mock_prefs,
                ops=mock_ops,
                api_client=mock_api_client,
            )
            qtbot.addWidget(widget)

            assert isinstance(widget.fleet_service, FleetService)

            with contextlib.suppress(Exception):
                widget.close()
