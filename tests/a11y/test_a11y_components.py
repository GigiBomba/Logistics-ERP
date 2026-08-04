"""Accessibility tests for UI components (components.py)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible

from ui.components import (
    Card,
    CompactKPICard,
    EmptyState,
    FieldLabel,
    FilterChip,
    SearchInput,
    StatusBadge,
    Toggle,
    UniversalCard,
)
from tests.a11y.conftest import (
    assert_accessible_description_not_empty,
    assert_accessible_name_not_empty,
)


class TestFieldLabelA11y:
    """FieldLabel — QLabel wrapper used for form field names."""

    def test_field_label_accessible_name(self, qt_widget):
        widget = FieldLabel(qt_widget, "Test Label")
        assert_accessible_name_not_empty(widget)

    def test_field_label_accessible_role(self, qt_widget):
        widget = FieldLabel(qt_widget, "Test")
        iface = QAccessible.queryAccessibleInterface(widget)
        assert iface is not None
        assert iface.role() == QAccessible.Role.StaticText


class TestCardA11y:
    """Card — basic QFrame surface container."""

    def test_card_accessible_name(self, qt_widget):
        widget = Card(qt_widget)
        assert_accessible_name_not_empty(widget)

    def test_card_accessible_description(self, qt_widget):
        widget = Card(qt_widget)
        assert_accessible_description_not_empty(widget)


class TestUniversalCardA11y:
    """UniversalCard — standardised info card with title + info rows."""

    def test_universal_card_accessible_name(self, qt_widget):
        widget = UniversalCard(qt_widget, title="Test Card")
        assert_accessible_name_not_empty(widget)

    def test_universal_card_accessible_description(self, qt_widget):
        widget = UniversalCard(qt_widget, title="Test Card")
        assert_accessible_description_not_empty(widget)


class TestCompactKPICardA11y:
    """CompactKPICard — compact KPI metric card with icon/value/trend."""

    def test_compact_kpi_card_accessible_name(self, qt_widget):
        widget = CompactKPICard(qt_widget, label="Test", value="123")
        assert_accessible_name_not_empty(widget)

    def test_compact_kpi_card_accessible_description(self, qt_widget):
        widget = CompactKPICard(qt_widget, label="Test", value="123")
        assert_accessible_description_not_empty(widget)


class TestStatusBadgeA11y:
    """StatusBadge — pill-shaped status label."""

    def test_status_badge_accessible_name(self, qt_widget):
        widget = StatusBadge(qt_widget, "delivered", "Delivered")
        assert_accessible_name_not_empty(widget)

    def test_status_badge_role(self, qt_widget):
        widget = StatusBadge(qt_widget, "delivered", "Delivered")
        iface = QAccessible.queryAccessibleInterface(widget)
        assert iface is not None
        assert iface.role() == QAccessible.Role.StaticText


class TestEmptyStateA11y:
    """EmptyState — empty-state placeholder with icon + text."""

    def test_empty_state_accessible_name(self, qt_widget):
        widget = EmptyState(qt_widget, title="No items", subtitle="Nothing to show")
        assert_accessible_name_not_empty(widget)

    def test_empty_state_accessible_description(self, qt_widget):
        widget = EmptyState(qt_widget, title="No items", subtitle="Nothing to show")
        assert_accessible_description_not_empty(widget)


class TestToggleA11y:
    """Toggle — on/off switch control."""

    def test_toggle_accessible_name(self, qt_widget):
        widget = Toggle(qt_widget)
        assert_accessible_name_not_empty(widget)

    def test_toggle_accessible_description(self, qt_widget):
        widget = Toggle(qt_widget)
        assert_accessible_description_not_empty(widget)

    def test_toggle_focusable(self, qt_widget):
        widget = Toggle(qt_widget)
        assert widget.focusPolicy() != Qt.FocusPolicy.NoFocus, (
            f"Toggle should have a non-zero focusPolicy, got {widget.focusPolicy()}"
        )


class TestFilterChipA11y:
    """FilterChip — clickable filter chip (regression: already has accessibleName)."""

    def test_filter_chip_accessible_name_not_empty(self, qt_widget):
        widget = FilterChip(qt_widget, text="Active")
        assert_accessible_name_not_empty(widget)


class TestSearchInputA11y:
    """SearchInput — search field (regression: already has accessibleName)."""

    def test_search_input_accessible_name_not_empty(self, qt_widget):
        widget = SearchInput(qt_widget, "Search trips...")
        assert_accessible_name_not_empty(widget)
