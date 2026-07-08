"""Tests for the alert card delegate."""
from __future__ import annotations
import pytest

class TestAlertCardDelegate:
    def test_creation(self, qt_widget, qtbot):
        from ui.delegates.alert_card_delegate import AlertCardDelegate
        delegate = AlertCardDelegate(qt_widget)
        assert delegate is not None

    def test_size_hint(self, qt_widget, qtbot):
        from PySide6.QtCore import QSize, QModelIndex
        from ui.delegates.alert_card_delegate import AlertCardDelegate
        delegate = AlertCardDelegate(qt_widget)
        index = QModelIndex()
        size = delegate.sizeHint(None, index)
        assert isinstance(size, QSize)
        assert size.width() > 0
        assert size.height() > 0
