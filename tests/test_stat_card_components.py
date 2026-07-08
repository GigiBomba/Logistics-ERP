"""Tests for StatCard, StatCardRow, and StatCardRowContainer."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QLabel

from ui.design_tokens import COLOR_ACCENT_PRIMARY, COLOR_TEXT_TERTIARY
from ui.widgets.stat_card import StatCard
from ui.widgets.stat_card_row import StatCardRow, StatCardRowContainer


class TestStatCard:
    def test_construction(self, qt_widget, qtbot):
        card = StatCard(qt_widget, label="Test", value="42", status_dot_color="#22C55E")
        qtbot.addWidget(card)
        assert card._label_lbl.text() == "Test"
        assert card._value_lbl.text() == "42"
        assert card._dot is not None

    def test_no_dot_by_default(self, qt_widget, qtbot):
        card = StatCard(qt_widget, label="Label")
        qtbot.addWidget(card)
        assert card._dot is None

    def test_set_value_updates_text(self, qt_widget, qtbot):
        card = StatCard(qt_widget, label="X", value="0")
        qtbot.addWidget(card)
        card.set_value("999")
        assert card._value_lbl.text() == "999"

    def test_set_label_updates_text(self, qt_widget, qtbot):
        card = StatCard(qt_widget, label="Old")
        qtbot.addWidget(card)
        card.set_label("New Label")
        assert card._label_lbl.text() == "New Label"

    def test_set_value_color(self, qt_widget, qtbot):
        card = StatCard(qt_widget, label="X", value="0")
        qtbot.addWidget(card)
        card.set_value_color(COLOR_ACCENT_PRIMARY)
        assert COLOR_ACCENT_PRIMARY in card._value_lbl.styleSheet()

    def test_value_label_property(self, qt_widget, qtbot):
        card = StatCard(qt_widget, label="X", value="42")
        qtbot.addWidget(card)
        assert card.value_label is card._value_lbl
        assert isinstance(card.value_label, QLabel)

    def test_minimum_height(self, qt_widget, qtbot):
        card = StatCard(qt_widget, label="X")
        qtbot.addWidget(card)
        assert card.minimumHeight() == 88

    def test_object_name(self, qt_widget, qtbot):
        card = StatCard(qt_widget, label="X")
        qtbot.addWidget(card)
        assert card.objectName() == "stat-card"

    def test_hover_toggles_property(self, qt_widget, qtbot):
        card = StatCard(qt_widget, label="X")
        qtbot.addWidget(card)
        assert card.property("hovered") is None or card.property("hovered") is False
        # Simulate enter
        event_enter = QEnterEvent(card.pos(), card.pos(), card.pos())
        card.enterEvent(event_enter)
        assert card.property("hovered") is True
        # Simulate leave
        card.leaveEvent(event_enter)
        assert card.property("hovered") is False

    def test_status_dot_toggle(self, qt_widget, qtbot):
        card = StatCard(qt_widget, label="X", status_dot_color="#22C55E")
        qtbot.addWidget(card)
        qt_widget.show()
        assert card._dot is not None
        assert card._dot.isVisible()
        card.set_status_dot(None)
        assert not card._dot.isVisible()
        card.set_status_dot("#EF4444")
        assert card._dot.isVisible()
        assert "#EF4444" in card._dot.styleSheet()


class TestStatCardRow:
    def test_initial_state(self, qt_widget, qtbot):
        row = StatCardRow(qt_widget)
        qtbot.addWidget(row)
        assert row.card_count() == 0

    def test_add_card(self, qt_widget, qtbot):
        row = StatCardRow(qt_widget)
        qtbot.addWidget(row)
        card = StatCard(label="A", value="1")
        row.add_card(card)
        assert row.card_count() == 1
        assert card.minimumWidth() == 200
        assert card.maximumWidth() == 320

    def test_add_multiple_cards(self, qt_widget, qtbot):
        row = StatCardRow(qt_widget)
        qtbot.addWidget(row)
        for i in range(3):
            row.add_card(StatCard(label=str(i), value=str(i)))
        assert row.card_count() == 3

    def test_clear_removes_all(self, qt_widget, qtbot):
        row = StatCardRow(qt_widget)
        qtbot.addWidget(row)
        row.add_card(StatCard(label="A", value="1"))
        row.add_card(StatCard(label="B", value="2"))
        row.clear()
        assert row.card_count() == 0

    def test_width_distribution_min_width(self, qt_widget, qtbot):
        """When available width is tight, cards get min-width (200px)."""
        row = StatCardRow(qt_widget)
        qtbot.addWidget(row)
        for i in range(5):
            row.add_card(StatCard(label=str(i), value=str(i)))
        # Simulate narrow width
        row.resize(900, 100)
        row._distribute()
        for card in row._cards:
            assert card.minimumWidth() == 200
            assert card.maximumWidth() == 200

    def test_width_distribution_even(self, qt_widget, qtbot):
        """When plenty of width, cards get evenly distributed up to 320px."""
        row = StatCardRow(qt_widget)
        qtbot.addWidget(row)
        for i in range(5):
            row.add_card(StatCard(label=str(i), value=str(i)))
        row.resize(1800, 100)
        row._distribute()
        # All cards should have the same width within [200, 320]
        min_w = min(c.minimumWidth() for c in row._cards)
        max_w = max(c.maximumWidth() for c in row._cards)
        assert min_w == max_w
        assert 200 <= min_w <= 320


class TestStatCardRowContainer:
    def test_construction(self, qt_widget, qtbot):
        container = StatCardRowContainer(qt_widget)
        qtbot.addWidget(container)
        assert container.row is not None
        assert container.card_count() == 0

    def test_add_card_delegates(self, qt_widget, qtbot):
        container = StatCardRowContainer(qt_widget)
        qtbot.addWidget(container)
        card = StatCard(label="X", value="0")
        container.add_card(card)
        assert container.card_count() == 1
        assert container.row.card_count() == 1

    def test_clear_delegates(self, qt_widget, qtbot):
        container = StatCardRowContainer(qt_widget)
        qtbot.addWidget(container)
        container.add_card(StatCard(label="A", value="1"))
        container.add_card(StatCard(label="B", value="2"))
        container.clear()
        assert container.card_count() == 0
