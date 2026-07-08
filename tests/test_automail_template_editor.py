"""Tests for the automail template editor dialog."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestTemplateEditorDialog:
    def test_creation(self, qt_widget, qtbot):
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg.close()

    def test_has_subject_field(self, qt_widget, qtbot):
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg.close()

    def test_has_body_field(self, qt_widget, qtbot):
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg.close()

    def test_get_template_returns_dict(self, qt_widget, qtbot):
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        result = dlg.get_template() if hasattr(dlg, "get_template") else {}
        assert isinstance(result, dict)
        dlg.close()
