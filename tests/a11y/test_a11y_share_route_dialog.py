"""Accessibility tests for ShareRouteDialog.

Gap: ShareRouteDialog does not set accessibleName or accessibleDescription.
Child buttons (Copy, Export, Google Maps, Save & Open Folder, Close) also lack
accessibleName — tests will FAIL, documenting the accessibility gap.
"""
from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from tests.a11y.conftest import (
    assert_accessible_description_not_empty,
    assert_accessible_name_not_empty,
)


class TestShareRouteDialogA11y:
    """ShareRouteDialog — modal dialog for sharing routes (gap: no accessibleName/Description)."""

    def test_dialog_accessible_name(self, qt_widget, qtbot):
        """ShareRouteDialog should expose an accessibleName for screen readers."""
        from ui.dialogs.share_route_dialog import ShareRouteDialog

        dialog = ShareRouteDialog(
            parent=qt_widget,
            share_url="https://operion.app/route?stops=test",
        )
        qtbot.addWidget(dialog)
        assert_accessible_name_not_empty(dialog)

    def test_dialog_accessible_description(self, qt_widget, qtbot):
        """ShareRouteDialog should expose an accessibleDescription."""
        from ui.dialogs.share_route_dialog import ShareRouteDialog

        dialog = ShareRouteDialog(
            parent=qt_widget,
            share_url="https://operion.app/route?stops=test",
        )
        qtbot.addWidget(dialog)
        assert_accessible_description_not_empty(dialog)

    def test_copy_button_accessible_name(self, qt_widget, qtbot):
        """Copy button should have an accessibleName (gap)."""
        from ui.dialogs.share_route_dialog import ShareRouteDialog

        dialog = ShareRouteDialog(
            parent=qt_widget,
            share_url="https://operion.app/route?stops=test",
        )
        qtbot.addWidget(dialog)
        buttons = dialog.findChildren(QPushButton)
        copy_btn = next((b for b in buttons if "Copy" in b.text()), None)
        if copy_btn:
            assert_accessible_name_not_empty(copy_btn)

    def test_export_button_accessible_name(self, qt_widget, qtbot):
        """Export File button should have an accessibleName (gap)."""
        from ui.dialogs.share_route_dialog import ShareRouteDialog

        dialog = ShareRouteDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        buttons = dialog.findChildren(QPushButton)
        export_btn = next((b for b in buttons if "Export" in b.text()), None)
        if export_btn:
            assert_accessible_name_not_empty(export_btn)

    def test_gmaps_button_accessible_name(self, qt_widget, qtbot):
        """Google Maps button should have an accessibleName (gap)."""
        from ui.dialogs.share_route_dialog import ShareRouteDialog

        dialog = ShareRouteDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        buttons = dialog.findChildren(QPushButton)
        gmaps_btn = next((b for b in buttons if "Google" in b.text()), None)
        if gmaps_btn:
            assert_accessible_name_not_empty(gmaps_btn)

    def test_share_os_button_accessible_name(self, qt_widget, qtbot):
        """Save & Open Folder button should have an accessibleName (gap)."""
        from ui.dialogs.share_route_dialog import ShareRouteDialog

        dialog = ShareRouteDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        buttons = dialog.findChildren(QPushButton)
        os_btn = next((b for b in buttons if "Folder" in b.text()), None)
        if os_btn:
            assert_accessible_name_not_empty(os_btn)

    def test_close_button_accessible_name(self, qt_widget, qtbot):
        """Close button should have an accessibleName (gap)."""
        from ui.dialogs.share_route_dialog import ShareRouteDialog

        dialog = ShareRouteDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        buttons = dialog.findChildren(QPushButton)
        close_btn = next((b for b in buttons if "Close" in b.text()), None)
        if close_btn:
            assert_accessible_name_not_empty(close_btn)
