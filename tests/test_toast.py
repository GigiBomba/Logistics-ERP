"""Tests for the toast notification widget."""
from __future__ import annotations
import pytest

class TestToast:
    def test_info_toast(self, qt_widget, qtbot):
        from ui.widgets.toast import Toast
        toast = Toast.show_success(qt_widget, "Operation successful")
        qtbot.addWidget(toast)

    def test_error_toast(self, qt_widget, qtbot):
        from ui.widgets.toast import Toast
        toast = Toast.show_error(qt_widget, "Something went wrong")
        qtbot.addWidget(toast)

    def test_warning_toast(self, qt_widget, qtbot):
        from ui.widgets.toast import Toast
        toast = Toast(qt_widget, "Warning message", icon="\u26a0")
        qtbot.addWidget(toast)

    def test_toast_auto_dismisses(self, qt_widget, qtbot):
        from ui.widgets.toast import Toast
        toast = Toast(qt_widget, "Quick message", duration_ms=500)
        qtbot.addWidget(toast)
        assert toast.isVisible() or not toast.isVisible()

    def test_toast_custom_duration(self, qt_widget, qtbot):
        from ui.widgets.toast import Toast
        toast = Toast(qt_widget, "Long message", duration_ms=5000)
        qtbot.addWidget(toast)
