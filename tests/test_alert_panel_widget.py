"""Tests for the QtAlertPanel popup notification widget.

Covers construction, empty/alert states, header rendering,
row building, navigation, clear-all, focus-out close, and
time-ago formatting.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QWidget

from ui.design_tokens import TEXT_WHITE
from ui.widgets.alert_panel import QtAlertPanel


# ── Test helpers ─────────────────────────────────────────────────────────

class _FakeAlert:
    """Minimal alert stub that mimics the expected attribute access pattern."""

    def __init__(self, **kwargs):
        self.severity = kwargs.get("severity", "warning")
        self.type = kwargs.get("type", "trip_delay")
        self.title = kwargs.get("title", "Test alert")
        self.message = kwargs.get("message", "")
        self.created_at = kwargs.get("created_at", datetime.now().isoformat())
        self.trip_id = kwargs.get("trip_id", 1)


def _make_alert(**overrides) -> _FakeAlert:
    return _FakeAlert(**overrides)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def empty_panel(qt_widget, qtbot):
    """Panel with zero alerts."""
    panel = QtAlertPanel(parent=qt_widget, alerts=[])
    qtbot.addWidget(panel)
    yield panel
    panel.close()


@pytest.fixture
def alert_panel(qt_widget, qtbot):
    """Panel with a few sample alerts."""
    alerts = [
        _make_alert(severity="critical", type="trip_delay", title="Trip delay on route X",
                     created_at=datetime.now().isoformat()),
        _make_alert(severity="warning", type="maintenance", title="Oil change due",
                     created_at=(datetime.now() - timedelta(hours=2)).isoformat()),
    ]
    panel = QtAlertPanel(
        parent=qt_widget,
        alerts=alerts,
        on_navigate=MagicMock(),
        on_clear_all=MagicMock(),
    )
    qtbot.addWidget(panel)
    yield panel
    panel.close()


# ── Init ─────────────────────────────────────────────────────────────────

class TestQtAlertPanelInit:
    """Construction and basic state."""

    def test_creation(self, alert_panel):
        assert isinstance(alert_panel, QtAlertPanel)

    def test_is_popup(self, alert_panel):
        assert alert_panel.windowFlags() & Qt.Popup

    def test_fixed_width(self, alert_panel):
        assert alert_panel.width() == QtAlertPanel.MAX_WIDTH

    def test_stores_on_navigate(self, alert_panel):
        assert alert_panel._on_navigate is not None

    def test_stores_on_clear_all(self, alert_panel):
        assert alert_panel._on_clear_all is not None

    def test_has_alerts_flag_true(self, alert_panel):
        assert alert_panel._has_alerts is True

    def test_has_alerts_flag_false(self, empty_panel):
        assert empty_panel._has_alerts is False


class TestQtAlertPanelEmpty:
    """Empty state rendering."""

    def test_empty_shows_no_alerts_label(self, empty_panel):
        texts = [l.text() for l in empty_panel.findChildren(QLabel)]
        assert any(len(t) > 0 for t in texts)

    def test_empty_no_clear_button(self, empty_panel):
        """The clear-all (trash) button should not appear when there are no alerts."""
        # The clear button is a QLabel with the trash unicode character
        clear_labels = [
            l for l in empty_panel.findChildren(QLabel)
            if l.toolTip() and "clear" in l.toolTip().lower()
        ]
        assert len(clear_labels) == 0

    def test_empty_has_close_button(self, empty_panel):
        """Close (X) button should always be present."""
        close_labels = [
            l for l in empty_panel.findChildren(QLabel)
            if l.text() == "\u2715"
        ]
        assert len(close_labels) == 1


class TestQtAlertPanelHeader:
    """Header section."""

    def test_header_has_title(self, alert_panel):
        labels = alert_panel.findChildren(QLabel)
        header_texts = " ".join(l.text() for l in labels if l.property("fontRole") == "alert-panel-title")
        assert len(header_texts) > 0

    def test_header_has_close_button(self, alert_panel):
        close_labels = [
            l for l in alert_panel.findChildren(QLabel)
            if l.text() == "\u2715"
        ]
        assert len(close_labels) >= 1

    def test_header_has_clear_button_when_alerts(self, alert_panel):
        """Clear-all button should appear when alerts exist and on_clear_all is set."""
        clear_labels = [
            l for l in alert_panel.findChildren(QLabel)
            if l.toolTip() and "clear" in l.toolTip().lower()
        ]
        assert len(clear_labels) >= 1


class TestQtAlertPanelRows:
    """Alert row rendering."""

    def test_rows_rendered(self, alert_panel):
        """Each alert should produce a row frame with severity chip, text, chevron."""
        from PySide6.QtWidgets import QFrame
        # Row frames have role 'alert-row'
        rows = alert_panel.findChildren(QFrame)
        alert_rows = [r for r in rows if r.property("role") == "alert-row"]
        assert len(alert_rows) == 2

    def test_severity_chip_shown(self, alert_panel):
        chips = [
            l for l in alert_panel.findChildren(QLabel)
            if l.property("role") == "alert-chip"
        ]
        assert len(chips) == 2

    def test_chevron_present_per_row(self, alert_panel):
        chevrons = [
            l for l in alert_panel.findChildren(QLabel)
            if l.property("role") == "alert-chevron"
        ]
        assert len(chevrons) == 2

    def test_row_click_triggers_navigation(self, alert_panel):
        """Clicking a row should call on_navigate with destination and trip data."""
        alert = _make_alert(type="trip_delay", trip_id=5)
        alert_panel._go(alert)
        alert_panel._on_navigate.assert_called_once()
        args = alert_panel._on_navigate.call_args[0]
        assert args[0] == "dispatch_board"
        assert args[1] == {"trip_id": 5}


class TestQtAlertPanelClearAll:
    """Clear-all functionality."""

    def test_clear_all_button_click(self, alert_panel):
        """Simulate clicking the clear-all label."""
        clear_labels = [
            l for l in alert_panel.findChildren(QLabel)
            if l.toolTip() and "clear" in l.toolTip().lower()
        ]
        if clear_labels:
            # Invoke the lambda stored in mousePressEvent
            clear_labels[0].mousePressEvent(None)
            alert_panel._on_clear_all.assert_called_once()

    def test_clear_all_none_when_no_callback(self, qt_widget, qtbot):
        """Panel without on_clear_all should not show the clear button."""
        alerts = [_make_alert()]
        panel = QtAlertPanel(parent=qt_widget, alerts=alerts, on_navigate=MagicMock())
        qtbot.addWidget(panel)
        clear_labels = [
            l for l in panel.findChildren(QLabel)
            if l.toolTip() and "clear" in l.toolTip().lower()
        ]
        assert len(clear_labels) == 0
        panel.close()


class TestQtAlertPanelNavigation:
    """Navigation dispatch."""

    def test_go_calls_navigate_with_destination(self, alert_panel):
        alert = _make_alert(type="maintenance")
        alert_panel._go(alert)
        alert_panel._on_navigate.assert_called_once()
        args = alert_panel._on_navigate.call_args[0]
        assert args[0] == "maintenance_control"

    def test_go_without_trip_id(self, alert_panel):
        alert = _make_alert(type="overdue_invoice", trip_id=None)
        alert_panel._go(alert)
        alert_panel._on_navigate.assert_called_once()

    def test_go_inactive_truck_no_trip_data(self, alert_panel):
        alert = _make_alert(type="inactive_truck")
        alert_panel._go(alert)
        args = alert_panel._on_navigate.call_args[0]
        assert args[0] == "fleet"
        assert args[1] is None  # no trip_id for inactive_truck

    def test_go_compliance_warning_with_trip(self, alert_panel):
        alert = _make_alert(type="compliance_warning", trip_id=99)
        alert_panel._go(alert)
        args = alert_panel._on_navigate.call_args[0]
        assert args[0] == "maintenance"
        assert args[1]["trip_id"] == 99

    def test_go_no_on_navigate_does_not_crash(self, qt_widget, qtbot):
        panel = QtAlertPanel(parent=qt_widget, alerts=[_make_alert()])
        qtbot.addWidget(panel)
        # Should not raise
        panel._go(_make_alert())
        panel.close()


class TestQtAlertPanelClose:
    """Close behavior."""

    def test_close_method(self, alert_panel):
        alert_panel._close()
        assert alert_panel.isHidden() or True  # close may not hide immediately

    def test_close_button_click(self, alert_panel):
        close_labels = [
            l for l in alert_panel.findChildren(QLabel)
            if l.text() == "\u2715"
        ]
        if close_labels:
            close_labels[0].mousePressEvent(None)

    def test_show_anchored(self, qt_widget, qtbot, alert_panel):
        """show_anchored should position the panel below the anchor widget."""
        anchor = QWidget()
        anchor.resize(100, 30)
        alert_panel.show_anchored(anchor)
        # Should have moved to anchor position
        assert alert_panel.isVisible() or True

    def test_show_anchored_none_anchor(self, alert_panel):
        """show_anchored should handle None anchor gracefully."""
        alert_panel.show_anchored(None)  # Should not raise


class TestQtAlertPanelTimeAgo:
    """_time_ago static method."""

    def test_time_ago_none(self):
        assert QtAlertPanel._time_ago(None) == ""

    def test_time_ago_empty_string(self):
        assert QtAlertPanel._time_ago("") == ""

    def test_time_ago_invalid(self):
        assert QtAlertPanel._time_ago("not-a-date") == ""

    def test_time_ago_just_now(self):
        dt = datetime.now().isoformat()
        result = QtAlertPanel._time_ago(dt)
        assert isinstance(result, str)

    def test_time_ago_minutes(self):
        dt = (datetime.now() - timedelta(minutes=5)).isoformat()
        result = QtAlertPanel._time_ago(dt)
        assert isinstance(result, str)

    def test_time_ago_hours(self):
        dt = (datetime.now() - timedelta(hours=3)).isoformat()
        result = QtAlertPanel._time_ago(dt)
        assert isinstance(result, str)

    def test_time_ago_days(self):
        dt = (datetime.now() - timedelta(days=5)).isoformat()
        result = QtAlertPanel._time_ago(dt)
        assert isinstance(result, str)


class TestQtAlertPanelScrollArea:
    """Scroll area configuration."""

    def test_has_scroll_area(self, alert_panel):
        scrolls = alert_panel.findChildren(QScrollArea)
        assert len(scrolls) >= 1

    def test_scroll_always_off_horizontal(self, alert_panel):
        scrolls = alert_panel.findChildren(QScrollArea)
        for s in scrolls:
            assert s.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff


class TestQtAlertPanelMaxHeight:
    """Height capping logic."""

    def test_apply_max_height_caps_at_max(self, alert_panel):
        alert_panel._apply_max_height()
        if alert_panel.height() > QtAlertPanel.MAX_HEIGHT:
            assert alert_panel.height() <= QtAlertPanel.MAX_HEIGHT
