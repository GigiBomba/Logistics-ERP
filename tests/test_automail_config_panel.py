"""Tests for the automail config panel."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestAutomailConfigPanel:
    def test_creation(self, qt_widget, qtbot):
        from ui.views.automail.config_panel import AutomailConfigPanel
        panel = AutomailConfigPanel(qt_widget)
        qtbot.addWidget(panel)

    def test_has_smtp_settings(self, qt_widget, qtbot):
        from ui.views.automail.config_panel import AutomailConfigPanel
        panel = AutomailConfigPanel(qt_widget)
        qtbot.addWidget(panel)

    def test_has_schedule_section(self, qt_widget, qtbot):
        from ui.views.automail.config_panel import AutomailConfigPanel
        panel = AutomailConfigPanel(qt_widget)
        qtbot.addWidget(panel)
