"""Tests for the upload integration view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtUploadIntegration:
    def test_creation(self, qt_widget, qtbot):
        from ui.views.upload_integration import QtUploadIntegration
        view = QtUploadIntegration(qt_widget)
        qtbot.addWidget(view)

    def test_has_upload_button(self, qt_widget, qtbot):
        from ui.views.upload_integration import QtUploadIntegration
        view = QtUploadIntegration(qt_widget)
        qtbot.addWidget(view)

    def test_has_drop_zone(self, qt_widget, qtbot):
        from ui.views.upload_integration import QtUploadIntegration
        view = QtUploadIntegration(qt_widget)
        qtbot.addWidget(view)
