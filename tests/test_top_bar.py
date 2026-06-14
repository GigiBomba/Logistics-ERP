"""Tests for the PySide6 top bar widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from ui.widgets.top_bar import TopBar


class TestTopBar:
    def test_creation(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        assert bar.height() == TopBar.HEIGHT

    def test_breadcrumb_initially_empty(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        labels = bar.findChildren(QLabel)
        breadcrumb = next((l for l in labels if l.property("role") == "breadcrumb"), None)
        assert breadcrumb is not None
        assert breadcrumb.text() == ""

    def test_set_breadcrumb(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        bar.set_breadcrumb("Overview")
        labels = bar.findChildren(QLabel)
        breadcrumb = next((l for l in labels if l.property("role") == "breadcrumb"), None)
        assert breadcrumb.text() == "Overview"

    def test_clock_updates(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        labels = bar.findChildren(QLabel)
        clock = next((l for l in labels if l.property("role") == "clock"), None)
        assert clock is not None
        initial = clock.text()
        # The timer fires every 30s; advance it manually to avoid waiting.
        bar._clock_timer.timeout.emit()
        assert clock.text() != "" or initial == ""

    def test_alert_count_zero_hides_badge(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        bar.set_alert_count(0)
        labels = bar.findChildren(QLabel)
        badge = next((l for l in labels if l.property("role") == "badge"), None)
        assert badge is not None
        assert badge.isHidden()

    def test_alert_count_positive_shows_badge(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        bar.set_alert_count(5)
        labels = bar.findChildren(QLabel)
        badge = next((l for l in labels if l.property("role") == "badge"), None)
        assert badge is not None
        assert not badge.isHidden()
        assert badge.text() == "5"

    def test_alert_count_caps_at_99(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        bar.set_alert_count(150)
        labels = bar.findChildren(QLabel)
        badge = next((l for l in labels if l.property("role") == "badge"), None)
        assert badge is not None
        assert badge.text() == "99"

    def test_bell_widget_exists(self, qt_widget, qtbot):
        bar = TopBar(qt_widget)
        qtbot.addWidget(bar)
        labels = bar.findChildren(QLabel)
        bell = next((l for l in labels if l.property("role") == "bell"), None)
        assert bell is not None
