"""Tests for the shared FlowLayout."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from ui.widgets.flow_layout import FlowLayout


class TestFlowLayout:
    def test_construction(self, qt_widget, qtbot):
        layout = FlowLayout(qt_widget, margin=0, spacing=8)
        qtbot.addWidget(qt_widget)
        assert layout.count() == 0
        assert layout.spacing() == 8

    def test_add_widget(self, qt_widget, qtbot):
        layout = FlowLayout(qt_widget, margin=0, spacing=4)
        qtbot.addWidget(qt_widget)
        lbl = QLabel("Hello")
        layout.addWidget(lbl)
        assert layout.count() == 1

    def test_add_multiple_widgets(self, qt_widget, qtbot):
        layout = FlowLayout(qt_widget, margin=0, spacing=4)
        qtbot.addWidget(qt_widget)
        for i in range(5):
            layout.addWidget(QLabel(f"Item {i}"))
        assert layout.count() == 5

    def test_item_at_out_of_range(self, qt_widget, qtbot):
        layout = FlowLayout(qt_widget, margin=0, spacing=4)
        qtbot.addWidget(qt_widget)
        layout.addWidget(QLabel("Item"))
        assert layout.itemAt(0) is not None
        assert layout.itemAt(1) is None
        assert layout.itemAt(-1) is None

    def test_take_at(self, qt_widget, qtbot):
        layout = FlowLayout(qt_widget, margin=0, spacing=4)
        qtbot.addWidget(qt_widget)
        lbl = QLabel("Removable")
        layout.addWidget(lbl)
        layout.addWidget(QLabel("Keep"))
        taken = layout.takeAt(0)
        assert taken is not None
        assert layout.count() == 1

    def test_has_height_for_width(self, qt_widget, qtbot):
        layout = FlowLayout(qt_widget, margin=0, spacing=4)
        qtbot.addWidget(qt_widget)
        assert layout.hasHeightForWidth() is True

    def test_expanding_directions(self, qt_widget, qtbot):
        layout = FlowLayout(qt_widget, margin=0, spacing=4)
        qtbot.addWidget(qt_widget)
        directions = layout.expandingDirections()
        assert directions == Qt.Orientations(Qt.Orientation(0))

    def test_size_hint_with_items(self, qt_widget, qtbot):
        layout = FlowLayout(qt_widget, margin=0, spacing=4)
        qtbot.addWidget(qt_widget)
        layout.addWidget(QLabel("X"))
        hint = layout.sizeHint()
        assert hint.width() > 0
        assert hint.height() > 0

    def test_minimum_size_grows_with_items(self, qt_widget, qtbot):
        layout = FlowLayout(qt_widget, margin=0, spacing=4)
        qtbot.addWidget(qt_widget)
        min1 = layout.minimumSize()
        layout.addWidget(QLabel("A"))
        min2 = layout.minimumSize()
        # Minimum size should grow (or stay same) after adding a widget
        assert min2.width() >= min1.width()
        assert min2.height() >= min1.height()

    def test_clear_removes_all(self, qt_widget, qtbot):
        layout = FlowLayout(qt_widget, margin=0, spacing=4)
        qtbot.addWidget(qt_widget)
        for i in range(3):
            layout.addWidget(QLabel(f"L{i}"))
        assert layout.count() == 3
        while layout.count():
            item = layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        assert layout.count() == 0
