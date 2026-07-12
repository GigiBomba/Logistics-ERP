"""Tests for the invoice editor line-items and totals mixin (LineItemsMixin).

The mixin is tested via a minimal test host widget that provides the
required interface methods ``LineItemsMixin`` expects on ``self``.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from services.i18n import t
from ui.views.invoice_editor.line_items import LineItemsMixin


# ── Test host ──────────────────────────────────────────────────────────────────


class LineItemsTestHost(QWidget, LineItemsMixin):
    """Minimal widget that provides the interface LineItemsMixin requires.

    The real production host (QtInvoiceEditor) defines attributes like
    ``_scroll``, ``_make_card``, ``_recalc_task``, etc.  Here we
    provide lightweight stubs so we can verify the mixin builds its
    sections and calculates totals without crashing.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 500)

        # ── State attributes the mixin expects ──────────────────────────
        self._addon_items: list[dict[str, Any]] = []

        # Financial state
        self._tax_rate: str = "19"
        self._discount_value: str = "0"
        self._discount_type: str = "Percentage"
        self._currency: str = "EUR"
        self._trip_base_price: str = "0.00"

        # Fields that get set by _build_totals_section
        self._subtotal_lbl: QWidget | None = None
        self._tax_lbl: QWidget | None = None
        self._discount_lbl: QWidget | None = None
        self._grand_lbl: QWidget | None = None
        self._canvas_subtotal: QWidget | None = None
        self._canvas_tax: QWidget | None = None
        self._canvas_discount: QWidget | None = None
        self._canvas_grand: QWidget | None = None
        self._disc_symbol_lbl: QWidget | None = None

        # ── Scroll container stub ───────────────────────────────────────
        self._scroll = MagicMock()
        self._scroll.add_widget = MagicMock()

        # ── Debounced recalculation task ────────────────────────────────
        self._recalc_task = MagicMock()
        self._recalc_task.schedule = MagicMock()

        # ── Root layout ─────────────────────────────────────────────────
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)

    # ── Stub implementations ───────────────────────────────────────────────

    def _make_card(self) -> QFrame:
        """Stub that returns a simple QFrame with a layout."""
        card = QFrame(self)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(4)
        return card

    def _recalc_all(self) -> None:
        """Schedule recalculation via the debounced task."""
        self._recalc_task.schedule()

    def _get_currency_symbol(self, code: str) -> str:
        """Return currency symbol for code."""
        symbols = {"EUR": "\u20AC", "RON": "lei", "USD": "$", "GBP": "\u00A3"}
        return symbols.get(code, code)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def host(qtbot):
    """Create the test host widget for LineItemsMixin tests."""
    w = LineItemsTestHost()
    qtbot.addWidget(w)
    yield w


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestLineItemsMixin:
    """Tests for line-items table and totals section."""

    # ── Build sections ─────────────────────────────────────────────────────

    def test_build_line_items_section(self, host):
        """_build_line_items_section creates the table and buttons."""
        assert not hasattr(host, "_items_table")  # not built yet
        host._build_line_items_section()

        assert hasattr(host, "_items_table")
        assert host._items_table is not None
        # Table should have at least 3 columns: index, description, amount
        assert host._items_table.columnCount() >= 3

        # Buttons should exist
        assert hasattr(host, "_add_row_btn")
        assert host._add_row_btn is not None

    def test_build_totals_section(self, host):
        """_build_totals_section creates all total display labels."""
        host._build_totals_section()

        # Side-panel totals
        assert hasattr(host, "_subtotal_lbl")
        assert hasattr(host, "_tax_lbl")
        assert hasattr(host, "_discount_lbl")
        assert hasattr(host, "_grand_lbl")

        # Canvas totals
        assert hasattr(host, "_canvas_subtotal")
        assert hasattr(host, "_canvas_tax")
        assert hasattr(host, "_canvas_discount")
        assert hasattr(host, "_canvas_grand")

        # Financial controls
        assert hasattr(host, "_tax_combo")
        assert hasattr(host, "_disc_type_combo")
        assert hasattr(host, "_disc_entry")
        assert hasattr(host, "_curr_combo")

    def test_build_both_sections(self, host):
        """Both sections can be built without error."""
        host._build_line_items_section()
        host._build_totals_section()
        assert host._items_table is not None

    # ── Add / remove rows ──────────────────────────────────────────────────

    def test_add_addon_row_default(self, host):
        """_add_addon_row appends a default item."""
        host._build_line_items_section()
        assert len(host._addon_items) == 0

        host._add_addon_row()
        assert len(host._addon_items) == 1
        assert host._addon_items[0] == {"description": "", "amount": 0.0}

    def test_add_addon_row_with_data(self, host):
        """_add_addon_row appends the provided data."""
        host._build_line_items_section()
        data = {"description": "Test item", "amount": 150.0}
        host._add_addon_row(data)
        assert len(host._addon_items) == 1
        assert host._addon_items[0] == data

    def test_add_default_addon_item_empty(self, host):
        """_add_default_addon_item creates one item when list is empty."""
        host._build_line_items_section()
        host._addon_items = []
        host._add_default_addon_item()
        assert len(host._addon_items) == 1

    def test_add_default_addon_item_nonempty(self, host):
        """_add_default_addon_item does nothing when items exist."""
        host._build_line_items_section()
        host._addon_items = [{"description": "Existing", "amount": 50.0}]
        host._add_default_addon_item()
        assert len(host._addon_items) == 1  # unchanged

    def test_remove_selected_addon_no_selection(self, host):
        """_remove_selected_addon is safe when no row is selected."""
        host._build_line_items_section()
        host._add_addon_row()
        host._add_addon_row()
        assert len(host._addon_items) == 2
        # No selection, so removal should be a no-op
        host._remove_selected_addon()
        assert len(host._addon_items) == 2

    # ── Table sync ─────────────────────────────────────────────────────────

    def test_sync_table_to_items(self, host):
        """_sync_table_to_items populates the table from _addon_items."""
        host._build_line_items_section()
        host._addon_items = [
            {"description": "Item A", "amount": 100.0},
            {"description": "Item B", "amount": 250.50},
        ]
        host._sync_table_to_items()
        assert host._items_table.rowCount() == 2

    # ── Totals calculation ─────────────────────────────────────────────────

    def test_calculate_totals_empty(self, host):
        """_calculate_totals returns zeros when there are no items."""
        result = host._calculate_totals()
        assert result["subtotal"] == 0.0
        assert result["total_tax"] == 0.0
        assert result["discount"] == 0.0
        assert result["grand_total"] == 0.0
        assert result["tax_rate"] == 19.0

    def test_calculate_totals_with_items(self, host):
        """_calculate_totals handles addon items correctly."""
        host._addon_items = [
            {"description": "Item 1", "amount": 100.0},
            {"description": "Item 2", "amount": 50.0},
        ]
        host._tax_rate = "19"
        host._discount_value = "0"
        host._trip_base_price = "0.00"
        result = host._calculate_totals()
        assert result["subtotal"] == 150.0
        assert result["total_tax"] == 28.50  # 150 * 0.19
        assert result["grand_total"] == 178.50

    def test_calculate_totals_with_trip_price(self, host):
        """_calculate_totals includes trip base price in subtotal."""
        host._addon_items = [
            {"description": "Item 1", "amount": 200.0},
        ]
        host._trip_base_price = "500.00"
        result = host._calculate_totals()
        assert result["subtotal"] == 700.0
        assert result["total_tax"] == 133.0  # 700 * 0.19
        assert result["grand_total"] == 833.0

    def test_calculate_totals_with_percent_discount(self, host):
        """_calculate_totals applies percentage discount."""
        host._addon_items = [{"description": "Item", "amount": 1000.0}]
        host._discount_value = "10"
        host._discount_type = t("invoice_editor.discount_percentage")
        result = host._calculate_totals()
        assert result["subtotal"] == 1000.0
        assert result["discount"] == 100.0  # 10%
        assert result["grand_total"] == 1090.0  # 1000 + 190 - 100

    def test_calculate_totals_with_fixed_discount(self, host):
        """_calculate_totals applies fixed discount."""
        host._addon_items = [{"description": "Item", "amount": 1000.0}]
        host._discount_value = "50"
        # Any string that is NOT the percentage key works as fixed
        host._discount_type = "fixed"
        result = host._calculate_totals()
        assert result["subtotal"] == 1000.0
        assert result["discount"] == 50.0
        assert result["grand_total"] == 1140.0  # 1000 + 190 - 50

    def test_calculate_totals_invalid_values(self, host):
        """_calculate_totals handles invalid numeric values gracefully."""
        host._tax_rate = "not-a-number"
        host._discount_value = "also-bad"
        host._trip_base_price = "bad"
        result = host._calculate_totals()
        assert result["subtotal"] == 0.0
        assert result["tax_rate"] == 0.0
        assert result["disc_value"] == 0.0
        assert result["trip_price"] == 0.0

    def test_calculate_totals_invalid_item_amount(self, host):
        """_calculate_totals handles addon items with invalid amounts."""
        host._addon_items = [{"description": "Bad", "amount": "invalid"}]
        result = host._calculate_totals()
        assert result["subtotal"] == 0.0

    # ── Tax rate changes ───────────────────────────────────────────────────

    def test_on_tax_rate_changed(self, host):
        """_on_tax_rate_changed updates rate and triggers recalc."""
        host._on_tax_rate_changed("20")
        assert host._tax_rate == "20"
        host._recalc_task.schedule.assert_called_once()

    # ── Discount type changes ──────────────────────────────────────────────

    def test_on_discount_type_changed(self, host):
        """_on_discount_type_changed updates type and triggers recalc."""
        host._build_totals_section()
        host._on_discount_type_changed("fixed")
        assert host._discount_type == "fixed"
        host._recalc_task.schedule.assert_called()

    # ── Discount value changes ─────────────────────────────────────────────

    def test_on_discount_value_changed(self, host):
        """_on_discount_value_changed updates value and triggers recalc."""
        host._on_discount_value_changed("25")
        assert host._discount_value == "25"
        host._recalc_task.schedule.assert_called_once()

    # ── Currency changes ───────────────────────────────────────────────────

    def test_on_currency_changed(self, host):
        """_on_currency_changed updates currency and triggers recalc."""
        host._on_currency_changed("RON")
        assert host._currency == "RON"
        host._recalc_task.schedule.assert_called_once()

    # ── Currency symbol helper ─────────────────────────────────────────────

    def test_get_currency_symbol_known(self, host):
        """_get_currency_symbol returns the correct symbol for known codes."""
        assert host._get_currency_symbol("EUR") == "\u20AC"
        assert host._get_currency_symbol("RON") == "lei"
        assert host._get_currency_symbol("USD") == "$"
        assert host._get_currency_symbol("GBP") == "\u00A3"

    def test_get_currency_symbol_unknown(self, host):
        """_get_currency_symbol returns the code itself for unknown codes."""
        assert host._get_currency_symbol("CHF") == "CHF"

    # ── Table cell handling ────────────────────────────────────────────────

    def test_on_table_cell_changed_out_of_bounds(self, host):
        """_on_table_cell_changed is safe for rows beyond _addon_items."""
        host._build_line_items_section()
        # Should not crash
        host._on_table_cell_changed(99, 1)

    def test_on_table_current_cell_changed_no_previous(self, host):
        """_on_table_current_cell_changed is safe with no previous cell."""
        host._build_line_items_section()
        host._on_table_current_cell_changed(0, 0, -1, -1)

    # ── Refresh totals display ─────────────────────────────────────────────

    def test_refresh_totals_display(self, host):
        """_refresh_totals_display updates all labels without error."""
        host._build_totals_section()
        host._addon_items = [{"description": "Item", "amount": 100.0}]
        host._refresh_totals_display()
        # Labels should have been updated with formatted values
        assert host._subtotal_lbl is not None
        assert host._grand_lbl is not None
