"""Tests for the automail editor panel."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestAutomailEditorPanel:
    def test_creation(self, qt_widget, qtbot):
        from ui.views.automail.editor_panel import AutomailEditorPanel
        panel = AutomailEditorPanel(qt_widget)
        qtbot.addWidget(panel)

    def test_has_template_selector(self, qt_widget, qtbot):
        from ui.views.automail.editor_panel import AutomailEditorPanel
        panel = AutomailEditorPanel(qt_widget)
        qtbot.addWidget(panel)

    def test_has_subject_field(self, qt_widget, qtbot):
        from ui.views.automail.editor_panel import AutomailEditorPanel
        panel = AutomailEditorPanel(qt_widget)
        qtbot.addWidget(panel)

    def test_has_body_editor(self, qt_widget, qtbot):
        from ui.views.automail.editor_panel import AutomailEditorPanel
        panel = AutomailEditorPanel(qt_widget)
        qtbot.addWidget(panel)

    def test_set_template(self, qt_widget, qtbot):
        from ui.views.automail.editor_panel import AutomailEditorPanel
        panel = AutomailEditorPanel(qt_widget)
        qtbot.addWidget(panel)
        panel.set_template({"subject": "Monthly Report", "body": "Dear {{client}},"})
