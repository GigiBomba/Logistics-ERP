"""Visual regression tests for QtAlertPanel — proof of concept for Phase 9."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from ui.widgets.alert_panel import QtAlertPanel

pytestmark = pytest.mark.visual


class TestVisualAlertPanel:
    """Screenshot tests for the alert notification panel."""

    def test_alert_panel_empty(self, qt_widget, qtbot, assert_snapshot):
        """Empty panel — no alerts."""
        panel = QtAlertPanel(parent=qt_widget, alerts=[])
        qtbot.addWidget(panel)
        assert_snapshot(panel, delay_ms=100, resize=(380, 200))
        panel.close()

    def test_alert_panel_with_alerts(self, qt_widget, qtbot, assert_snapshot):
        """Panel populated with a few sample alerts."""
        from datetime import datetime

        alerts = [
            _make_alert("critical", "trip_delay", "Trip delay on route X",
                        datetime(2026, 7, 15, 10, 30).isoformat()),
            _make_alert("warning", "maintenance", "Oil change due",
                        datetime(2026, 7, 14, 9, 0).isoformat()),
            _make_alert("info", "overdue_invoice", "Invoice #1042 overdue",
                        datetime(2026, 7, 13, 18, 0).isoformat()),
        ]
        panel = QtAlertPanel(parent=qt_widget, alerts=alerts,
                             on_navigate=MagicMock(), on_clear_all=MagicMock())
        qtbot.addWidget(panel)
        assert_snapshot(panel, delay_ms=100, resize=(380, 300))
        panel.close()


def _make_alert(severity, alert_type, title, created_at):
    """Minimal fake alert for visual testing."""
    from collections import namedtuple
    Alert = namedtuple("Alert", ["severity", "type", "title", "message", "created_at", "trip_id"])
    return Alert(severity=severity, type=alert_type, title=title,
                 message=title, created_at=created_at, trip_id=1)
