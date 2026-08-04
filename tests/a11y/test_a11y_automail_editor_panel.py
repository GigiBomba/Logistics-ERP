"""Accessibility tests for EditorPanel (AutoMail template editor panel).

Gap: EditorPanel does not set accessibleName or accessibleDescription.
Child controls (combo, line edit, text edit, buttons) also lack accessibleName.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QToolButton

from tests.a11y.conftest import (
    assert_accessible_description_not_empty,
    assert_accessible_name_not_empty,
    collect_focusable_children,
)


class TestEditorPanelA11y:
    """EditorPanel — right panel: email template editor with HTML toolbar."""

    def test_panel_accessible_name(self, qt_widget, qtbot):
        """EditorPanel should expose an accessibleName (gap)."""
        from ui.views.automail.editor_panel import EditorPanel

        panel = EditorPanel(parent=qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel)

    def test_panel_accessible_description(self, qt_widget, qtbot):
        """EditorPanel should expose an accessibleDescription (gap)."""
        from ui.views.automail.editor_panel import EditorPanel

        panel = EditorPanel(parent=qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_description_not_empty(panel)

    def test_template_combo_accessible_name(self, qt_widget, qtbot):
        """Template selector combo should have an accessibleName (gap)."""
        from ui.views.automail.editor_panel import EditorPanel

        panel = EditorPanel(parent=qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._template_combo)

    def test_subject_edit_accessible_name(self, qt_widget, qtbot):
        """Subject line editor should have an accessibleName (gap)."""
        from ui.views.automail.editor_panel import EditorPanel

        panel = EditorPanel(parent=qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._subject_edit)

    def test_body_editor_accessible_name(self, qt_widget, qtbot):
        """Body HTML editor should have an accessibleName (gap)."""
        from ui.views.automail.editor_panel import EditorPanel

        panel = EditorPanel(parent=qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._body_editor)

    def test_template_edit_btn_accessible_name(self, qt_widget, qtbot):
        """Edit template button should have an accessibleName (gap)."""
        from ui.views.automail.editor_panel import EditorPanel

        panel = EditorPanel(parent=qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._edit_tpl_btn)

    def test_template_dup_btn_accessible_name(self, qt_widget, qtbot):
        """Duplicate template button should have an accessibleName (gap)."""
        from ui.views.automail.editor_panel import EditorPanel

        panel = EditorPanel(parent=qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._dup_tpl_btn)

    def test_template_new_btn_accessible_name(self, qt_widget, qtbot):
        """New template button should have an accessibleName (gap)."""
        from ui.views.automail.editor_panel import EditorPanel

        panel = EditorPanel(parent=qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._new_tpl_btn)

    def test_template_del_btn_accessible_name(self, qt_widget, qtbot):
        """Delete template button should have an accessibleName (gap)."""
        from ui.views.automail.editor_panel import EditorPanel

        panel = EditorPanel(parent=qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._del_tpl_btn)

    def test_save_template_btn_accessible_name(self, qt_widget, qtbot):
        """Save Template button should have an accessibleName (gap)."""
        from ui.views.automail.editor_panel import EditorPanel

        panel = EditorPanel(parent=qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._save_btn)

    def test_send_test_btn_accessible_name(self, qt_widget, qtbot):
        """Send Test button should have an accessibleName (gap)."""
        from ui.views.automail.editor_panel import EditorPanel

        panel = EditorPanel(parent=qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._test_btn)

    def test_format_toolbar_buttons_have_tooltips(self, qt_widget, qtbot):
        """Format toolbar buttons should have tooltips."""
        from ui.views.automail.editor_panel import EditorPanel

        panel = EditorPanel(parent=qt_widget)
        qtbot.addWidget(panel)
        toolbar_btns = panel._format_toolbar.findChildren(QToolButton)
        for btn in toolbar_btns:
            assert btn.toolTip(), (
                f"Toolbar button '{btn.text()}' is missing a tooltip"
            )
