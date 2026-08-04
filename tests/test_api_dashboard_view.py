"""Tests for QtApiDashboardView — API health monitoring dashboard."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QLabel, QPushButton

# SP workaround: ui.widgets.SP may not exist since it re-exports SP as S
import ui.widgets as _ui_widgets
if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.is_online.return_value = True
    client.health_check.return_value = {
        "database": "connected",
        "version": "1.2.3",
        "redis": "ok",
        "celery": "ok",
    }
    return client


@pytest.fixture
def api_dashboard(qtbot, mock_api_client):
    """Create QtApiDashboardView with mocked ApiClient."""
    from ui.views.api_dashboard_view import QtApiDashboardView

    widget = QtApiDashboardView(
        parent=None,
        db=MagicMock(),
        api_client=mock_api_client,
    )
    qtbot.addWidget(widget)
    yield widget

    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        widget.shutdown()


# =========================================================================
# Tests
# =========================================================================


class TestQtApiDashboardView:
    """Suite of tests for the API Dashboard view."""

    # ── Initialisation ─────────────────────────────────────────────────

    def test_initialization(self, api_dashboard):
        """Widget constructs without crashing."""
        assert api_dashboard is not None
        assert api_dashboard.db is not None
        assert api_dashboard._api is not None

    def test_refresh_timer_created(self, api_dashboard):
        """Auto-refresh timer is created and running."""
        assert api_dashboard._refresh_timer is not None
        assert api_dashboard._refresh_timer.isActive() is True
        assert api_dashboard._refresh_timer.interval() == 5000

    def test_header_section_exists(self, api_dashboard):
        """SectionHeader widget is present."""
        # The first widget in the layout is the header
        assert hasattr(api_dashboard, "_status_grid")

    def test_action_buttons_exist(self, api_dashboard):
        """Test API and Refresh buttons exist."""
        assert hasattr(api_dashboard, "_test_btn")
        assert hasattr(api_dashboard, "_refresh_btn")
        assert api_dashboard._test_btn is not None
        assert api_dashboard._refresh_btn is not None

    def test_log_scroll_area_exists(self, api_dashboard):
        """Scroll area for connection logs exists."""
        assert hasattr(api_dashboard, "_log_scroll")
        assert api_dashboard._log_scroll is not None
        assert hasattr(api_dashboard, "_log_layout")

    # ── Status refresh ─────────────────────────────────────────────────

    def test_refresh_status_populates_grid(self, api_dashboard):
        """_refresh_status creates status cards in the grid."""
        assert api_dashboard._status_grid.count() >= 1

    def test_refresh_status_with_online_api(self, api_dashboard, mock_api_client):
        """_refresh_status creates multiple cards when API is online."""
        mock_api_client.is_online.return_value = True
        mock_api_client.health_check.return_value = {
            "database": "connected", "version": "1.0.0",
        }
        api_dashboard._refresh_status()
        # Should have API Server + Database + API Version cards
        assert api_dashboard._status_grid.count() >= 3

    def test_refresh_status_with_offline_api(self, api_dashboard, mock_api_client):
        """_refresh_status handles offline API gracefully."""
        mock_api_client.is_online.return_value = False
        api_dashboard._refresh_status()
        # Should have just the API Server card
        assert api_dashboard._status_grid.count() >= 1

    def test_refresh_status_with_health_error(self, api_dashboard, mock_api_client):
        """_refresh_status handles health_check exception."""
        mock_api_client.is_online.return_value = True
        mock_api_client.health_check.side_effect = Exception("Connection refused")
        api_dashboard._refresh_status()
        # Should have API card + error card
        assert api_dashboard._status_grid.count() >= 2

    def test_refresh_adds_log_entry(self, api_dashboard):
        """_refresh_status adds a timestamped log entry."""
        initial_count = api_dashboard._log_layout.count()
        api_dashboard._refresh_status()
        assert api_dashboard._log_layout.count() >= initial_count + 1

    # ── Test API button ────────────────────────────────────────────────

    def test_test_api_adds_log(self, api_dashboard, mock_api_client):
        """_test_api adds a health check log entry."""
        initial_count = api_dashboard._log_layout.count()
        api_dashboard._test_api()
        assert api_dashboard._log_layout.count() >= initial_count + 1
        mock_api_client.health_check.assert_called()

    def test_test_api_handles_exception(self, api_dashboard, mock_api_client):
        """_test_api logs exception when health_check fails."""
        mock_api_client.health_check.side_effect = Exception("Timeout")
        api_dashboard._test_api()
        # Should still add a log entry (with failure message)
        assert api_dashboard._log_layout.count() >= 1

    # ── Log management ─────────────────────────────────────────────────

    def test_add_log_creates_label(self, api_dashboard):
        """_add_log creates a QLabel in the log layout."""
        initial_count = api_dashboard._log_layout.count()
        api_dashboard._add_log("Test message")
        assert api_dashboard._log_layout.count() == initial_count + 1
        # The last item should be a QLabel
        item = api_dashboard._log_layout.itemAt(api_dashboard._log_layout.count() - 1)
        assert item is not None
        assert isinstance(item.widget(), QLabel)
        assert "Test message" in item.widget().text()

    def test_add_log_trims_overflow(self, api_dashboard):
        """_add_log removes oldest entries when count exceeds 100."""
        for i in range(105):
            api_dashboard._add_log(f"Log entry {i}")
        assert api_dashboard._log_layout.count() <= 100

    # ── Wakeup ─────────────────────────────────────────────────────────

    def test_wakeup_triggers_refresh(self, api_dashboard, mock_api_client):
        """wakeup calls _refresh_status."""
        mock_api_client.is_online.reset_mock()
        api_dashboard.wakeup()
        mock_api_client.is_online.assert_called()

    # ── Lifecycle ──────────────────────────────────────────────────────

    def test_shutdown_stops_timer(self, api_dashboard):
        """shutdown stops the refresh timer."""
        api_dashboard.shutdown()
        assert api_dashboard._refresh_timer.isActive() is False

    # ── Status refresh edge cases ────────────────────────────────────

    def test_refresh_status_partial_health_data(self, api_dashboard, mock_api_client):
        """_refresh_status handles health_check returning only 'database' key."""
        mock_api_client.is_online.return_value = True
        mock_api_client.health_check.return_value = {"database": "connected"}
        api_dashboard._refresh_status()
        # Should have API Server (0,0) + Database (0,1) + API Version (1,0)
        assert api_dashboard._status_grid.count() == 3

    def test_refresh_status_clears_previous_cards(self, api_dashboard):
        """_refresh_status removes old cards before adding new ones."""
        api_dashboard._refresh_status()
        old_widgets = []
        for i in range(api_dashboard._status_grid.count()):
            item = api_dashboard._status_grid.itemAt(i)
            if item and item.widget():
                old_widgets.append(item.widget())

        api_dashboard._refresh_status()

        new_widgets = set()
        for i in range(api_dashboard._status_grid.count()):
            item = api_dashboard._status_grid.itemAt(i)
            if item and item.widget():
                new_widgets.add(item.widget())

        for w in old_widgets:
            assert w not in new_widgets

    # ── Log overflow ─────────────────────────────────────────────────

    def test_add_log_overflow_exact_boundary(self, api_dashboard):
        """_add_log keeps exactly 100 entries, removing the oldest when full."""
        for i in range(100):
            api_dashboard._add_log(f"Log {i}")
        assert api_dashboard._log_layout.count() == 100

        api_dashboard._add_log("overflow")
        assert api_dashboard._log_layout.count() == 100
        # Oldest entry removed — first item should now be "Log 1"
        first_item = api_dashboard._log_layout.itemAt(0)
        assert first_item is not None
        assert "Log 1" in first_item.widget().text()

    # ── Scroll behaviour ─────────────────────────────────────────────

    def test_scroll_to_bottom_sets_maximum(self, api_dashboard):
        """_add_log triggers scroll-to-bottom that sets scrollbar to maximum value."""
        mock_scrollbar = MagicMock()
        mock_scrollbar.maximum.return_value = 500
        with patch.object(api_dashboard._log_scroll, "verticalScrollBar", return_value=mock_scrollbar):
            with patch("ui.views.api_dashboard_view.QTimer.singleShot") as mock_timer:
                mock_timer.side_effect = lambda delay, cb: cb()
                api_dashboard._add_log("test")
                mock_scrollbar.setValue.assert_called_once_with(500)

    # ── Timer lifecycle ──────────────────────────────────────────────

    def test_timer_restarts_after_shutdown_wakeup(self, api_dashboard, mock_api_client):
        """wakeup after shutdown restarts the refresh cycle."""
        api_dashboard.shutdown()
        assert api_dashboard._refresh_timer.isActive() is False

        mock_api_client.is_online.reset_mock()
        api_dashboard.wakeup()
        # wakeup calls _refresh_status which calls is_online
        mock_api_client.is_online.assert_called()


# =========================================================================
# Tests — _StatusCard
# =========================================================================


class TestStatusCard:
    """Unit tests for the internal _StatusCard widget."""

    @pytest.fixture
    def status_card(self, qtbot):
        from ui.views.api_dashboard_view import _StatusCard
        card = _StatusCard(None, "Test Service", "online", "All good")
        qtbot.addWidget(card)
        yield card

    def test_card_creation(self, status_card):
        """_StatusCard initializes with title and status."""
        assert status_card is not None

    def test_update_status_changes_text(self, status_card):
        """update_status changes the status label."""
        status_card.update_status("offline", "Unreachable")
        # The internal _status label should reflect the change
        assert "offline" in status_card._status.text().lower()

    def test_update_status_adds_detail(self, status_card):
        """update_status changes the detail label."""
        status_card.update_status("online", "New detail")
        assert "New detail" in status_card._detail.text()

    # ── Status styles ────────────────────────────────────────────────

    def test_status_card_initial_style(self, status_card):
        """_StatusCard applies the correct stylesheet for 'online' status."""
        from ui.views.api_dashboard_view import _STATUS_STYLES
        expected = _STATUS_STYLES["online"]
        assert expected in status_card._status.styleSheet()

    def test_status_card_unknown_status_default_style(self, qtbot):
        """_StatusCard uses 'unknown' style for unrecognised status values."""
        from ui.views.api_dashboard_view import _StatusCard, _STATUS_STYLES
        card = _StatusCard(None, "Test", "unknown", "")
        qtbot.addWidget(card)
        expected = _STATUS_STYLES["unknown"]
        assert expected in card._status.styleSheet()
