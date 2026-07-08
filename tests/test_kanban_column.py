"""Tests for the kanban column widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def kanban_column(qt_widget, qtbot):
    column = __import__("ui.widgets.kanban_column", fromlist=["QtKanbanColumn"]).QtKanbanColumn(
        parent=qt_widget,
        status="planned",
        title="Planned",
        color="#6366F1",
    )
    qtbot.addWidget(column)
    yield column

class TestQtKanbanColumn:
    def test_creation(self, kanban_column):
        assert kanban_column._status == "planned"
        assert kanban_column._title == "Planned"

    def test_title_label_created(self, kanban_column):
        assert hasattr(kanban_column, "_title_label")

    def test_count_label_created(self, kanban_column):
        assert hasattr(kanban_column, "_count_label")

    def test_scroll_area_created(self, kanban_column):
        assert hasattr(kanban_column, "_scroll_area")

    def test_set_cards_populates(self, kanban_column):
        cards = [{"id": 1, "client": "Test", "status": "planned"}]
        kanban_column.set_cards(cards)
        assert hasattr(kanban_column, "_cards")

    def test_add_card_appends(self, kanban_column):
        card_data = {"id": 1, "client": "Test", "status": "planned"}
        kanban_column.add_card(card_data)

    def test_remove_card_removes(self, kanban_column):
        card_data = {"id": 1, "client": "Test", "status": "planned"}
        kanban_column.add_card(card_data)
        kanban_column.remove_card(1)
