"""Tests for the automail timeline panel."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestAutomailTimelinePanel:
    def test_creation(self, qt_widget, qtbot):
        from ui.views.automail.timeline_panel import AutomailTimelinePanel
        panel = AutomailTimelinePanel(qt_widget)
        qtbot.addWidget(panel)

    def test_set_history(self, qt_widget, qtbot):
        from ui.views.automail.timeline_panel import AutomailTimelinePanel
        panel = AutomailTimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        history = [
            {"id": 1, "subject": "Test", "sent_at": "2026-01-01", "recipient": "test@test.com", "status": "sent"},
        ]
        panel.set_history(history)

    def test_clear(self, qt_widget, qtbot):
        from ui.views.automail.timeline_panel import AutomailTimelinePanel
        panel = AutomailTimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        panel.clear()

    def test_refresh(self, qt_widget, qtbot):
        from ui.views.automail.timeline_panel import AutomailTimelinePanel
        panel = AutomailTimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        panel.refresh()
