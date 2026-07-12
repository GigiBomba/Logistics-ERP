"""Tests for the receipt editor LineItemsMixin.

Tests the mixin in isolation via a test host widget that inherits
from both QWidget and the mixin, as documented in the project pattern.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem, QWidget

from ui.views.receipt_editor.line_items import LineItemsMixin


# ── Test host ──────────────────────────────────────────────────────────────

class ReceiptLineItemsHost(QWidget, LineItemsMixin):
    """Host that mixes in LineItemsMixin for isolated unit testing.

    Calls ``_build_line_items_section()`` during ``__init__`` so the
    table widget and total labels are available immediately.

    Stores the returned container as ``_container`` to prevent the
    Qt object tree from being garbage-collected (the container is
    the parent of all created sub-widgets).
    """

    def __init__(self) -> None:
        super().__init__()
        self._container = self._build_line_items_section()


# ── Safe-float tests (static) ──────────────────────────────────────────────

class TestSafeFloat:
    """Unit tests for the static ``_safe_float`` parser."""

    def test_normal_decimal(self) -> None:
        assert ReceiptLineItemsHost._safe_float("123.45") == 123.45

    def test_comma_as_decimal_separator(self) -> None:
        assert ReceiptLineItemsHost._safe_float("123,45") == 123.45

    def test_empty_string(self) -> None:
        assert ReceiptLineItemsHost._safe_float("") == 0.0

    def test_only_whitespace(self) -> None:
        assert ReceiptLineItemsHost._safe_float("   ") == 0.0

    def test_non_numeric_string(self) -> None:
        assert ReceiptLineItemsHost._safe_float("abc") == 0.0

    def test_none_value(self) -> None:
        assert ReceiptLineItemsHost._safe_float(None) == 0.0

    def test_integer_string(self) -> None:
        assert ReceiptLineItemsHost._safe_float("42") == 42.0

    def test_negative_number(self) -> None:
        assert ReceiptLineItemsHost._safe_float("-10.50") == -10.5


# ── Initialisation ─────────────────────────────────────────────────────────

class TestInit:
    """Verify the mixin sets up its UI components correctly."""

    def test_table_created(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        assert hasattr(host, "_line_items_table")
        assert host._line_items_table.columnCount() == 4

    def test_table_headers(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        headers = [
            host._line_items_table.horizontalHeaderItem(i).text()
            for i in range(4)
        ]
        # i18n keys are returned as-is when no translation is loaded
        assert all(h.startswith("receipt.line_items.") for h in headers)

    def test_totals_labels_created(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        assert hasattr(host, "_canvas_subtotal_label")
        assert hasattr(host, "_canvas_tax_label")
        assert hasattr(host, "_canvas_discount_label")
        assert hasattr(host, "_canvas_grand_label")

    def test_totals_labels_start_at_zero(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        for label_name in ("_canvas_subtotal_label", "_canvas_tax_label",
                           "_canvas_discount_label", "_canvas_grand_label"):
            text = getattr(host, label_name).text()
            assert text.startswith("0.00"), f"{label_name} = {text!r}"

    def test_line_items_list_initialised(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        assert host._line_items == []

    def test_header_label_created(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        assert hasattr(host, "_lit_header_label")

    def test_section_title_has_upper_text(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        text = host._lit_header_label.text()
        # translation key returned, just check it exists
        assert isinstance(text, str) and len(text) > 0


# ── Row operations ─────────────────────────────────────────────────────────

class TestAddItemRow:
    """Tests for ``_add_item_row``."""

    def test_adds_one_row(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row()
        assert host._line_items_table.rowCount() == 1

    def test_adds_multiple_rows(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row()
        host._add_item_row()
        host._add_item_row()
        assert host._line_items_table.rowCount() == 3

    def test_sets_default_values(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row()
        assert host._line_items_table.item(0, 0).text() == ""
        assert host._line_items_table.item(0, 1).text() == "1"
        assert host._line_items_table.item(0, 2).text() == "0.00"

    def test_uses_provided_values(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="Widget", qty="3", price="12.50")
        assert host._line_items_table.item(0, 0).text() == "Widget"
        assert host._line_items_table.item(0, 1).text() == "3"
        assert host._line_items_table.item(0, 2).text() == "12.50"

    def test_total_column_is_read_only(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row()
        total_item = host._line_items_table.item(0, 3)
        assert total_item is not None
        assert not (total_item.flags() & Qt.ItemIsEditable), \
            "Total column must not be user-editable"

    def test_add_row_triggers_calculation(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        with pytest.MonkeyPatch().context() as mp:
            calc = MagicMock()
            mp.setattr(host, "_calculate_totals", calc)
            host._add_item_row()
            calc.assert_called_once()


class TestRemoveItem:
    """Tests for ``_remove_item``."""

    def test_removes_selected_row(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="Keep")
        host._add_item_row(desc="Remove")
        host._line_items_table.setCurrentCell(1, 0)
        host._remove_item()
        assert host._line_items_table.rowCount() == 1
        assert host._line_items_table.item(0, 0).text() == "Keep"

    def test_remove_with_no_selection_does_nothing(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row()
        host._add_item_row()
        host._remove_item()  # no current row
        assert host._line_items_table.rowCount() == 2

    def test_remove_on_empty_table_does_nothing(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._remove_item()  # empty, no current row
        assert host._line_items_table.rowCount() == 0

    def test_remove_triggers_calculation(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row()
        host._line_items_table.setCurrentCell(0, 0)
        with pytest.MonkeyPatch().context() as mp:
            calc = MagicMock()
            mp.setattr(host, "_calculate_totals", calc)
            host._remove_item()
            calc.assert_called_once()


# ── Sync items from table ──────────────────────────────────────────────────

class TestSyncItemsFromTable:
    """Tests for ``_sync_items_from_table``."""

    def test_reads_single_row(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="Bolts", qty="10", price="1.50")
        host._sync_items_from_table()
        assert len(host._line_items) == 1
        item = host._line_items[0]
        assert item["description"] == "Bolts"
        assert item["quantity"] == 10.0
        assert item["unit_price"] == 1.5
        assert item["amount"] == 15.0

    def test_reads_multiple_rows(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="A", qty="2", price="10")
        host._add_item_row(desc="B", qty="3", price="20")
        host._sync_items_from_table()
        assert len(host._line_items) == 2
        assert host._line_items[0]["amount"] == 20.0
        assert host._line_items[1]["amount"] == 60.0

    def test_updates_total_column(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="Nuts", qty="4", price="2.25")
        host._sync_items_from_table()
        assert host._line_items_table.item(0, 3).text() == "9.00"

    def test_empty_table_returns_empty_list(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._sync_items_from_table()
        assert host._line_items == []

    def test_skips_empty_description_with_zero_total(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="", qty="0", price="0")
        host._sync_items_from_table()
        assert len(host._line_items) == 0

    def test_includes_item_when_description_present_but_zero_total(
        self, qtbot
    ) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="Freebie", qty="0", price="0")
        host._sync_items_from_table()
        assert len(host._line_items) == 1

    def test_handles_missing_items_gracefully(self, qtbot) -> None:
        """Row with a missing QTableWidgetItem should be skipped."""
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._line_items_table.blockSignals(True)
        host._line_items_table.insertRow(0)
        # only set column 0, leave others as None
        host._line_items_table.setItem(0, 0, QTableWidgetItem("orphan"))
        host._line_items_table.blockSignals(False)
        host._sync_items_from_table()
        assert host._line_items == []


# ── Calculation ────────────────────────────────────────────────────────────

class TestCalculateTotals:
    """Tests for ``_calculate_totals`` (no discount/tax attributes)."""

    def test_zero_when_no_items(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._calculate_totals()
        assert host._canvas_subtotal_label.text().startswith("0.00")

    def test_subtotal_only(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="X", qty="5", price="4")
        host._calculate_totals()
        assert "20.00" in host._canvas_subtotal_label.text()

    def test_subtotal_sums_all_items(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="A", qty="2", price="10")  # 20
        host._add_item_row(desc="B", qty="3", price="5")   # 15
        host._calculate_totals()
        assert "35.00" in host._canvas_subtotal_label.text()

    def test_no_discount_when_not_on_host(self, qtbot) -> None:
        """If _discount_value / _discount_type are absent, discount is 0."""
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="X", qty="10", price="10")
        host._calculate_totals()
        assert "0.00" in host._canvas_discount_label.text()
        assert "100.00" in host._canvas_grand_label.text()

    def test_no_tax_when_not_on_host(self, qtbot) -> None:
        """If _tax_rate is absent, tax is 0."""
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="X", qty="10", price="10")
        host._calculate_totals()
        assert "0.00" in host._canvas_tax_label.text()

    def test_fixed_discount(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "15"
        host._discount_type = "fixed"
        host._add_item_row(desc="X", qty="10", price="10")
        host._calculate_totals()
        assert "100.00" in host._canvas_subtotal_label.text()
        assert "15.00" in host._canvas_discount_label.text()
        assert "85.00" in host._canvas_grand_label.text()

    def test_percentage_discount(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "10"
        host._discount_type = "percentage"
        host._add_item_row(desc="X", qty="50", price="2")
        host._calculate_totals()
        # subtotal = 100, discount = 10% = 10
        assert "10.00" in host._canvas_discount_label.text()
        assert "90.00" in host._canvas_grand_label.text()

    def test_discount_capped_at_subtotal(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "999"
        host._discount_type = "fixed"
        host._add_item_row(desc="X", qty="1", price="50")
        host._calculate_totals()
        assert "50.00" in host._canvas_discount_label.text()
        assert "0.00" in host._canvas_grand_label.text()

    def test_tax_applied_after_discount(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "10"
        host._discount_type = "fixed"
        host._tax_rate = "19"
        host._add_item_row(desc="X", qty="100", price="1")
        host._calculate_totals()
        # subtotal = 100, discount = 10, after_discount = 90
        # tax = 90 * 0.19 = 17.10
        assert "100.00" in host._canvas_subtotal_label.text()
        assert "10.00" in host._canvas_discount_label.text()
        assert "17.10" in host._canvas_tax_label.text()
        assert "107.10" in host._canvas_grand_label.text()

    def test_discount_with_zero_rate_percentage(self, qtbot) -> None:
        """Percentage discount with value 0 should not apply."""
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "0"
        host._discount_type = "percentage"
        host._add_item_row(desc="X", qty="5", price="10")
        host._calculate_totals()
        assert "0.00" in host._canvas_discount_label.text()
        assert "50.00" in host._canvas_grand_label.text()

    def test_discount_value_none(self, qtbot) -> None:
        """_discount_value being None should be handled gracefully."""
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = None
        host._discount_type = "fixed"
        host._add_item_row(desc="X", qty="5", price="10")
        host._calculate_totals()
        assert "0.00" in host._canvas_discount_label.text()

    def test_tax_rate_none(self, qtbot) -> None:
        """_tax_rate being None should be handled gracefully."""
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._tax_rate = None
        host._add_item_row(desc="X", qty="5", price="10")
        host._calculate_totals()
        assert "0.00" in host._canvas_tax_label.text()

    def test_non_percentage_discount_type_gives_zero_discount(
        self, qtbot
    ) -> None:
        """If _discount_type is anything other than 'percentage' or 'fixed', discount is 0."""
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "25"
        host._discount_type = "unknown_type"
        host._add_item_row(desc="X", qty="10", price="10")
        host._calculate_totals()
        assert "0.00" in host._canvas_discount_label.text()


# ── Total display ──────────────────────────────────────────────────────────

class TestUpdateTotalDisplay:
    """Tests for ``_update_total_display``."""

    def test_updates_all_labels(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._currency = "USD"
        host._update_total_display(
            subtotal=100.0,
            tax_amount=19.0,
            discount_amount=10.0,
            grand_total=109.0,
        )
        assert host._canvas_subtotal_label.text() == "100.00 USD"
        assert host._canvas_tax_label.text() == "19.00 USD"
        assert host._canvas_discount_label.text() == "10.00 USD"
        assert host._canvas_grand_label.text() == "109.00 USD"

    def test_default_currency_is_eur(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        # No _currency set; mixin defaults to "EUR"
        host._update_total_display(subtotal=50.0)
        assert "EUR" in host._canvas_subtotal_label.text()

    def test_currency_from_attribute(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._currency = "GBP"
        host._update_total_display(subtotal=99.99)
        assert "99.99 GBP" in host._canvas_subtotal_label.text()

    def test_formats_thousands(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._update_total_display(subtotal=1234567.89)
        # The format is {subtotal:,.2f} -> 1,234,567.89
        assert "1,234,567.89" in host._canvas_subtotal_label.text()


# ── Signal handler ─────────────────────────────────────────────────────────

class TestOnTableCellChanged:
    """Tests for ``_on_table_cell_changed``."""

    def test_triggers_calculate_totals(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="X", qty="1", price="10")
        # Change quantity and notify via handler
        host._line_items_table.item(0, 1).setText("5")
        host._on_table_cell_changed(0, 1)
        # Quantity changed from 1 to 5 -> subtotal now 50
        assert "50.00" in host._canvas_subtotal_label.text()


# ── Edge cases ─────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Boundary and edge-case scenarios."""

    def test_comma_decimal_in_table(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._line_items_table.blockSignals(True)
        host._line_items_table.insertRow(0)
        host._line_items_table.setItem(0, 0, QTableWidgetItem("Test"))
        host._line_items_table.setItem(0, 1, QTableWidgetItem("2,5"))
        host._line_items_table.setItem(0, 2, QTableWidgetItem("10,50"))
        total_item = QTableWidgetItem("0.00")
        total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
        host._line_items_table.setItem(0, 3, total_item)
        host._line_items_table.blockSignals(False)
        host._sync_items_from_table()
        assert len(host._line_items) == 1
        assert host._line_items[0]["quantity"] == 2.5
        assert host._line_items[0]["unit_price"] == 10.5
        assert host._line_items[0]["amount"] == 26.25

    def test_many_rows_performance(self, qtbot) -> None:
        """Adding 100 rows should not crash."""
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        for i in range(100):
            host._add_item_row(desc=f"Item {i}", qty="1", price="1")
        assert host._line_items_table.rowCount() == 100

    def test_remove_last_row(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="Only")
        host._line_items_table.setCurrentCell(0, 0)
        host._remove_item()
        assert host._line_items_table.rowCount() == 0
        # NOTE: _sync_items_from_table returns early when empty without
        # clearing _line_items, so stale data may remain in the list.

    def test_recalculate_after_removing_all_rows(self, qtbot) -> None:
        host = ReceiptLineItemsHost()
        qtbot.addWidget(host)
        host._add_item_row(desc="X", qty="5", price="10")
        host._line_items_table.setCurrentCell(0, 0)
        host._remove_item()
        assert "0.00" in host._canvas_subtotal_label.text()
