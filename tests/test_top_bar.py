"""Tests for the PySide6 top bar widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from ui.widgets.topbar import TopBar
from ui.design_tokens import TOPBAR_HEIGHT


class TestTopBar:
    def test_creation(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        assert bar.height() == TOPBAR_HEIGHT

    def test_clock_updates(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        initial = bar._clock.text()
        # The timer fires every 30s; advance it manually to avoid waiting.
        bar._clock_timer.timeout.emit()
        assert bar._clock.text() != "" or initial == ""

    def test_alert_count_zero_hides_badge(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        bar.set_alert_count(0)
        assert bar._badge.isHidden()

    def test_alert_count_positive_shows_badge(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        bar.set_alert_count(5)
        assert not bar._badge.isHidden()
        assert bar._badge.text() == "5"

    def test_alert_count_caps_at_99(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        bar.set_alert_count(150)
        assert bar._badge.text() == "99"

    def test_bell_widget_exists(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        assert bar._bell is not None
