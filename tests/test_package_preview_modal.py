"""Tests for the package preview modal."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestPackagePreviewDialog:
    def test_creation(self, qt_widget, qtbot):
        from ui.views.package_preview_modal import PackagePreviewDialog
        dlg = PackagePreviewDialog(qt_widget, db=MagicMock())
        qtbot.addWidget(dlg)
        dlg.close()

    def test_has_document_list(self, qt_widget, qtbot):
        from ui.views.package_preview_modal import PackagePreviewDialog
        dlg = PackagePreviewDialog(qt_widget, db=MagicMock())
        qtbot.addWidget(dlg)
        dlg.close()

    def test_has_send_button(self, qt_widget, qtbot):
        from ui.views.package_preview_modal import PackagePreviewDialog
        dlg = PackagePreviewDialog(qt_widget, db=MagicMock())
        qtbot.addWidget(dlg)
        dlg.close()
