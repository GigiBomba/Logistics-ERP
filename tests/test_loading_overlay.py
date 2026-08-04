"""Tests for the loading overlay widget."""
from __future__ import annotations
import pytest

class TestLoadingOverlay:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.loading_overlay import LoadingOverlay
        overlay = LoadingOverlay(qt_widget)
        qtbot.addWidget(overlay)

    def test_show_hide(self, qt_widget, qtbot):
        from ui.widgets.loading_overlay import LoadingOverlay
        qt_widget.show()
        overlay = LoadingOverlay(qt_widget)
        qtbot.addWidget(overlay)
        overlay.show()
        assert overlay.isVisible()
        overlay.hide()
        assert not overlay.isVisible()

    def test_set_message(self, qt_widget, qtbot):
        from ui.widgets.loading_overlay import LoadingOverlay
        overlay = LoadingOverlay(qt_widget)
        qtbot.addWidget(overlay)
        overlay.set_text("Loading...")
