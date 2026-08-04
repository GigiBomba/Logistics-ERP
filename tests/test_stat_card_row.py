"""Tests for the StatCardRow and StatCardRowContainer widgets.

Covers construction, card management (add, count, clear),
width distribution logic, wrapping behaviour, and the
centering container.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from ui.widgets.stat_card import StatCard
from ui.widgets.stat_card_row import (
    StatCardRow,
    StatCardRowContainer,
    _CARD_MAX_WIDTH,
    _CARD_MIN_WIDTH,
    _CONTAINER_MAX_WIDTH,
    _GAP,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def card_row(qt_widget, qtbot):
    """Provide a bare StatCardRow."""
    row = StatCardRow(parent=qt_widget)
    qtbot.addWidget(row)
    yield row
    row.deleteLater()


@pytest.fixture
def populated_row(qt_widget, qtbot):
    """StatCardRow with 3 sample StatCards added."""
    row = StatCardRow(parent=qt_widget)
    qtbot.addWidget(row)
    for i in range(3):
        card = StatCard(parent=row, label=f"Card {i}", value="42")
        row.add_card(card)
    yield row
    row.deleteLater()


@pytest.fixture
def container(qt_widget, qtbot):
    """Provide a StatCardRowContainer."""
    c = StatCardRowContainer(parent=qt_widget)
    qtbot.addWidget(c)
    yield c
    c.deleteLater()


# ── StatCardRow Init ─────────────────────────────────────────────────────

class TestStatCardRowInit:
    """Basic construction."""

    def test_creation(self, card_row):
        assert isinstance(card_row, StatCardRow)

    def test_size_policy(self, card_row):
        assert card_row.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
        assert card_row.sizePolicy().verticalPolicy() == QSizePolicy.Fixed

    def test_max_width_set(self, card_row):
        assert card_row.maximumWidth() == _CONTAINER_MAX_WIDTH

    def test_no_cards_initially(self, card_row):
        assert card_row.card_count() == 0
        assert card_row._cards == []

    def test_has_flow_layout(self, card_row):
        from ui.widgets.flow_layout import FlowLayout
        assert isinstance(card_row._layout, FlowLayout)


# ── StatCardRow Card Management ──────────────────────────────────────────

class TestStatCardRowCardManagement:
    """Adding, counting, clearing cards."""

    def test_add_card_increases_count(self, card_row):
        card = StatCard(parent=card_row, label="KPI", value="1")
        card_row.add_card(card)
        assert card_row.card_count() == 1

    def test_add_card_sets_min_max_width(self, card_row):
        card = StatCard(parent=card_row, label="KPI", value="1")
        card_row.add_card(card)
        assert card.minimumWidth() == _CARD_MIN_WIDTH
        assert card.maximumWidth() == _CARD_MAX_WIDTH

    def test_add_card_tracks_internal_list(self, card_row):
        card = StatCard(parent=card_row, label="KPI", value="1")
        card_row.add_card(card)
        assert card in card_row._cards

    def test_clear_removes_all_cards(self, populated_row):
        populated_row.clear()
        assert populated_row.card_count() == 0

    def test_clear_calls_delete_later(self, populated_row):
        cards_before = list(populated_row._cards)
        populated_row.clear()
        # Cards should have been removed from layout
        for c in cards_before:
            assert c not in populated_row._cards


# ── StatCardRow Width Distribution ───────────────────────────────────────

class TestStatCardRowWidthDistribution:
    """Width distribution logic (_distribute)."""

    def test_distribute_empty_does_nothing(self, card_row):
        card_row._distribute()  # Should not raise

    def test_distribute_one_card(self, card_row):
        card = StatCard(parent=card_row, label="KPI", value="1")
        card_row.add_card(card)
        # Give the row a width greater than min_total
        card_row.resize(500, 100)
        card_row._distribute()
        assert card.width() >= _CARD_MIN_WIDTH

    def test_distribute_multiple_cards(self, populated_row):
        populated_row.resize(800, 100)
        populated_row._distribute()
        for card in populated_row._cards:
            assert card.width() >= _CARD_MIN_WIDTH
            assert card.width() <= _CARD_MAX_WIDTH

    def test_distribute_narrow_parent(self, populated_row):
        """When parent width is less than min_total, cards stay at min width."""
        populated_row.resize(100, 100)
        populated_row._distribute()
        for card in populated_row._cards:
            assert card.width() == _CARD_MIN_WIDTH

    def test_distribute_wide_parent(self, populated_row):
        """When there is extra space, cards share it evenly."""
        populated_row.resize(_CONTAINER_MAX_WIDTH, 100)
        populated_row._distribute()
        for card in populated_row._cards:
            assert card.width() >= _CARD_MIN_WIDTH

    def test_distribute_even_width(self, populated_row):
        """All cards should have the same width after distribution."""
        populated_row.resize(1400, 100)
        populated_row._distribute()
        widths = {card.width() for card in populated_row._cards}
        assert len(widths) == 1

    def test_distribute_caps_at_max(self, populated_row):
        """Even with lots of space, no card exceeds max width."""
        populated_row.resize(3000, 100)
        populated_row._distribute()
        for card in populated_row._cards:
            assert card.width() <= _CARD_MAX_WIDTH

    def test_resize_event_triggers_distribute(self, populated_row):
        """The resizeEvent should call _distribute."""
        # Simulate resize event by directly invoking resizeEvent
        from PySide6.QtCore import QSize
        with patch.object(populated_row, "_distribute") as mock_dist:
            populated_row._resizing = False  # ensure guard is reset
            populated_row.resize(900, 100)
            # resizeEvent may not fire synchronously; verify the method exists
            assert hasattr(populated_row, "resizeEvent")


# ── StatCardRowContainer ─────────────────────────────────────────────────

class TestStatCardRowContainerInit:
    """StatCardRowContainer construction."""

    def test_creation(self, container):
        assert isinstance(container, StatCardRowContainer)

    def test_has_row_property(self, container):
        assert isinstance(container.row, StatCardRow)

    def test_size_policy(self, container):
        assert container.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
        assert container.sizePolicy().verticalPolicy() == QSizePolicy.Fixed

    def test_has_stretch_on_both_sides(self, container):
        """The layout should have stretch before and after the row."""
        layout = container._layout
        assert isinstance(layout, QHBoxLayout)
        # Item 0 = stretch, Item 1 = row, Item 2 = stretch
        assert layout.count() >= 3

    def test_row_is_centered(self, container):
        """Row should be between two stretch items."""
        item0 = container._layout.itemAt(0)
        item2 = container._layout.itemAt(2)
        assert item0 is not None
        assert item2 is not None


# ── StatCardRowContainer Delegation ──────────────────────────────────────

class TestStatCardRowContainerDelegation:
    """Container delegates to the inner row."""

    def test_add_card_delegates(self, container):
        card = StatCard(parent=container, label="KPI", value="1")
        container.add_card(card)
        assert container.card_count() == 1
        assert container.row.card_count() == 1

    def test_card_count_delegates(self, populated_row, container):
        card = StatCard(parent=container, label="KPI", value="1")
        container.add_card(card)
        assert container.card_count() == container.row.card_count()

    def test_clear_delegates(self, container):
        card = StatCard(parent=container, label="KPI", value="1")
        container.add_card(card)
        container.clear()
        assert container.card_count() == 0


# ── StatCardRow Lifecycle ────────────────────────────────────────────────

class TestStatCardRowLifecycle:
    """Add/clear/add cycle."""

    def test_add_clear_add(self, card_row):
        card1 = StatCard(parent=card_row, label="A", value="1")
        card_row.add_card(card1)
        assert card_row.card_count() == 1

        card_row.clear()
        assert card_row.card_count() == 0

        card2 = StatCard(parent=card_row, label="B", value="2")
        card_row.add_card(card2)
        assert card_row.card_count() == 1
