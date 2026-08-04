"""Tests for the proforma editor LineItemsMixin.

Tests the mixin in isolation via a test host widget that inherits
from both QWidget and the mixin, as documented in the project pattern.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QTableWidgetItem, QVBoxLayout, QWidget

from ui.views.proforma_editor.line_items import LineItemsMixin


# ── Helpers ─────────────────────────────────────────────────────────────────

def _set_row(
    table: QWidget, row: int, desc: str, qty: str, price: str
) -> None:
    """Insert cell items into an existing (empty) row.

    Must be called with the table's signals **blocked** to prevent
    ``cellChanged`` recursion (``_sync_items_from_table`` updates the
    total column, which emits ``cellChanged`` and re-enters the
    sync/recalc cycle).
    """
    table.setItem(row, 0, QTableWidgetItem(desc))
    table.setItem(row, 1, QTableWidgetItem(qty))
    table.setItem(row, 2, QTableWidgetItem(price))
    total_item = QTableWidgetItem("0.00")
    total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
    table.setItem(row, 3, total_item)


def _insert_row(
    host: ProformaLineItemsHost, desc: str, qty: str, price: str
) -> None:
    """Insert a row into the items table without triggering signals."""
    tbl = host._items_table
    tbl.blockSignals(True)
    row = tbl.rowCount()
    tbl.insertRow(row)
    _set_row(tbl, row, desc, qty, price)
    tbl.blockSignals(False)


# ── Test host ──────────────────────────────────────────────────────────────

class ProformaLineItemsHost(QWidget, LineItemsMixin):
    """Host that mixes in LineItemsMixin for isolated unit testing.

    Provides the required host attributes (``_scroll``, ``_make_card``,
    tax/discount/currency defaults) and calls both ``_build_line_items_section``
    and ``_build_totals_section`` during ``__init__``.

    Stores containers in ``_containers`` to prevent the Qt object tree
    from being garbage-collected (child widgets are parented to the
    containers, which are siblings of this host).
    """

    def __init__(self) -> None:
        super().__init__()

        # Captures container widgets so they don't get GC'd
        self._containers: list[QWidget] = []

        # Required by ``_build_line_items_section``
        self._scroll = MagicMock()
        self._scroll.add_widget = self._containers.append

        # Required by ``_build_totals_section`` / ``_recalc_all``
        self._tax_rate = "19"
        self._discount_type = "fixed"
        self._discount_value = "0"
        self._currency = "EUR"
        self._addon_items: list[dict] = []
        self._description = ""

        self._build_line_items_section()
        self._build_totals_section()

    def _make_card(self) -> QFrame:
        """Return a QFrame with a VBoxLayout, matching the host contract."""
        card = QFrame(self)
        QVBoxLayout(card)
        return card


# ── Initialisation ─────────────────────────────────────────────────────────

class TestInit:
    """Verify the mixin builds UI components correctly."""

    def test_items_table_created(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        assert hasattr(host, "_items_table")
        assert host._items_table.columnCount() == 4

    def test_items_table_headers(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        headers = [
            host._items_table.horizontalHeaderItem(i).text()
            for i in range(4)
        ]
        assert all(h.startswith("proforma_editor.") for h in headers)

    def test_totals_labels_created(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        assert hasattr(host, "_canvas_subtotal_label")
        assert hasattr(host, "_canvas_tax_label")
        assert hasattr(host, "_canvas_discount_label")
        assert hasattr(host, "_canvas_grand_label")

    def test_totals_labels_start_with_currency(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        assert "common.zero_eur" in host._canvas_subtotal_label.text()
        assert "common.zero_eur" in host._canvas_tax_label.text()
        assert "common.zero_eur" in host._canvas_discount_label.text()
        assert "common.zero_eur" in host._canvas_grand_label.text()

    def test_desc_text_edit_created(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        assert hasattr(host, "_desc_text_edit")

    def test_tax_combo_has_values(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        assert host._tax_combo.currentText() == "19"

    def test_currency_combo_set(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        assert host._curr_combo.currentText() == "EUR"

    def test_scroll_add_widget_called(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        assert len(host._containers) >= 2

    def test_addon_items_initialised(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        assert host._addon_items == []


# ── Row operations ─────────────────────────────────────────────────────────

class TestAddRow:
    """Tests for ``_add_row``."""

    def test_adds_one_row(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._add_row()
        assert host._items_table.rowCount() == 1

    def test_adds_multiple_rows(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._add_row()
        host._add_row()
        host._add_row()
        assert host._items_table.rowCount() == 3

    def test_sets_default_values(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._add_row()
        assert host._items_table.item(0, 0).text() == ""
        assert host._items_table.item(0, 1).text() == "1"
        assert host._items_table.item(0, 2).text() == "0.00"

    def test_total_column_is_read_only(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._add_row()
        item = host._items_table.item(0, 3)
        assert item is not None
        assert not (item.flags() & Qt.ItemIsEditable)


class TestAddDefaultItem:
    """Tests for ``_add_default_item``."""

    def test_adds_row_with_default_description(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._add_default_item()
        assert host._items_table.rowCount() == 1
        assert host._items_table.item(0, 0).text() == "Transport services"

    def test_adds_at_next_available_row(self, qtbot) -> None:
        """``_add_default_item`` inserts a row and sets the description on row 0."""
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._add_default_item()
        host._add_default_item()  # second call appends another default row
        assert host._items_table.rowCount() == 2
        # ``_add_default_item`` always sets *row 0* to "Transport services"
        assert host._items_table.item(0, 0).text() == "Transport services"
        # Row 1 is appended by ``_add_row`` with default empty text
        assert host._items_table.item(1, 0).text() == ""


# ── Sync items from table ──────────────────────────────────────────────────

class TestSyncItemsFromTable:
    """Tests for ``_sync_items_from_table``.

    Note: ``_sync_items_from_table`` updates the total column text,
    which emits ``cellChanged`` and triggers ``_on_table_cell_changed``
    (→ ``_sync_items_from_table`` + ``_recalc_all``) when the value
    actually changes. Tests that manipulate rows with non-default values
    wrap the sync call with ``blockSignals`` to avoid this recursion.
    """

    def test_reads_single_row(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        _insert_row(host, "Service", "2", "50.00")
        host._items_table.blockSignals(True)
        host._sync_items_from_table()
        host._items_table.blockSignals(False)
        assert len(host._addon_items) == 1
        item = host._addon_items[0]
        assert item["description"] == "Service"
        assert item["quantity"] == 2.0
        assert item["unit_price"] == 50.0
        assert item["amount"] == 100.0

    def test_reads_multiple_rows(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        _insert_row(host, "A", "2", "10")
        _insert_row(host, "B", "3", "20")
        host._items_table.blockSignals(True)
        host._sync_items_from_table()
        host._items_table.blockSignals(False)
        assert len(host._addon_items) == 2
        assert host._addon_items[0]["amount"] == 20.0
        assert host._addon_items[1]["amount"] == 60.0

    def test_updates_total_column(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        _insert_row(host, "X", "3", "4.50")
        host._items_table.blockSignals(True)
        host._sync_items_from_table()
        host._items_table.blockSignals(False)
        assert host._items_table.item(0, 3).text() == "13.50"

    def test_empty_table_clears_addon_items(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._addon_items = [{"description": "stale"}]
        host._sync_items_from_table()
        assert host._addon_items == []

    def test_skips_row_with_missing_item(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._items_table.blockSignals(True)
        host._items_table.insertRow(0)
        host._items_table.setItem(0, 0, QTableWidgetItem("orphan"))
        # columns 1 and 2 left as None
        host._items_table.blockSignals(False)
        host._sync_items_from_table()
        assert host._addon_items == []

    def test_skips_zero_amount_with_empty_desc(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        _insert_row(host, "", "0", "0")
        host._items_table.blockSignals(True)
        host._sync_items_from_table()
        host._items_table.blockSignals(False)
        assert host._addon_items == []

    def test_includes_item_when_desc_present_but_zero_total(
        self, qtbot
    ) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        _insert_row(host, "Free", "0", "10")
        host._items_table.blockSignals(True)
        host._sync_items_from_table()
        host._items_table.blockSignals(False)
        assert len(host._addon_items) == 1

    def test_invalid_number_returns_zero(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._items_table.blockSignals(True)
        host._items_table.insertRow(0)
        host._items_table.setItem(0, 0, QTableWidgetItem("X"))
        host._items_table.setItem(0, 1, QTableWidgetItem("abc"))
        host._items_table.setItem(0, 2, QTableWidgetItem("def"))
        total_item = QTableWidgetItem("0.00")
        total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
        host._items_table.setItem(0, 3, total_item)
        host._items_table.blockSignals(False)
        host._sync_items_from_table()
        assert len(host._addon_items) == 1
        assert host._addon_items[0]["quantity"] == 0
        assert host._addon_items[0]["unit_price"] == 0


# ── Recalculation ──────────────────────────────────────────────────────────

class TestRecalcAll:
    """Tests for ``_recalc_all``.

    ``_recalc_all`` calls ``_sync_items_from_table`` which updates
    the total column and may trigger ``cellChanged`` recursion.
    Tests here use ``blockSignals`` when the row data differs from
    the default (0.00) to avoid double-sync issues.
    """

    def test_zero_when_no_items(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._recalc_all()
        assert "0.00 EUR" in host._canvas_subtotal_label.text()

    def test_subtotal_only(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "0"
        host._tax_rate = "0"
        _insert_row(host, "X", "5", "20")
        host._items_table.blockSignals(True)
        host._recalc_all()
        host._items_table.blockSignals(False)
        assert "100.00 EUR" in host._canvas_subtotal_label.text()
        assert "0.00 EUR" in host._canvas_tax_label.text()
        assert "0.00 EUR" in host._canvas_discount_label.text()
        assert "100.00 EUR" in host._canvas_grand_label.text()

    def test_subtotal_sums_all_items(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "0"
        host._tax_rate = "0"
        _insert_row(host, "A", "2", "10")
        _insert_row(host, "B", "3", "5")
        host._items_table.blockSignals(True)
        host._recalc_all()
        host._items_table.blockSignals(False)
        assert "35.00 EUR" in host._canvas_subtotal_label.text()

    def test_fixed_discount(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "25"
        host._discount_type = "fixed"
        host._tax_rate = "0"
        _insert_row(host, "X", "10", "10")
        host._items_table.blockSignals(True)
        host._recalc_all()
        host._items_table.blockSignals(False)
        assert "100.00 EUR" in host._canvas_subtotal_label.text()
        assert "25.00 EUR" in host._canvas_discount_label.text()
        assert "75.00 EUR" in host._canvas_grand_label.text()

    def test_percentage_discount(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "15"
        host._discount_type = "percentage"
        host._tax_rate = "0"
        _insert_row(host, "X", "100", "2")
        host._items_table.blockSignals(True)
        host._recalc_all()
        host._items_table.blockSignals(False)
        # subtotal = 200, discount = 15% = 30
        assert "30.00 EUR" in host._canvas_discount_label.text()
        assert "170.00 EUR" in host._canvas_grand_label.text()

    def test_discount_capped_at_subtotal(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "500"
        host._discount_type = "fixed"
        host._tax_rate = "0"
        _insert_row(host, "X", "1", "50")
        host._items_table.blockSignals(True)
        host._recalc_all()
        host._items_table.blockSignals(False)
        assert "50.00 EUR" in host._canvas_discount_label.text()
        assert "0.00 EUR" in host._canvas_grand_label.text()

    def test_tax_applied_after_discount(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "10"
        host._discount_type = "fixed"
        host._tax_rate = "19"
        _insert_row(host, "X", "100", "1")
        host._items_table.blockSignals(True)
        host._recalc_all()
        host._items_table.blockSignals(False)
        # subtotal = 100, discount = 10, after = 90, tax = 17.10, grand = 107.10
        assert "100.00 EUR" in host._canvas_subtotal_label.text()
        assert "10.00 EUR" in host._canvas_discount_label.text()
        assert "17.10 EUR" in host._canvas_tax_label.text()
        assert "107.10 EUR" in host._canvas_grand_label.text()

    def test_negative_discount_value_is_applied_as_fixed(self, qtbot) -> None:
        """Source code does not clamp negative fixed discount values."""
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "-5"
        host._discount_type = "fixed"
        host._tax_rate = "0"
        _insert_row(host, "X", "10", "10")
        host._items_table.blockSignals(True)
        host._recalc_all()
        host._items_table.blockSignals(False)
        assert "-5.00 EUR" in host._canvas_discount_label.text()

    def test_empty_discount_value_string(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = ""
        host._discount_type = "fixed"
        host._tax_rate = "0"
        _insert_row(host, "X", "10", "10")
        host._items_table.blockSignals(True)
        host._recalc_all()
        host._items_table.blockSignals(False)
        assert "0.00 EUR" in host._canvas_discount_label.text()

    def test_empty_tax_rate_string(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "0"
        host._tax_rate = ""
        _insert_row(host, "X", "10", "10")
        host._items_table.blockSignals(True)
        host._recalc_all()
        host._items_table.blockSignals(False)
        assert "0.00 EUR" in host._canvas_tax_label.text()

    def test_invalid_discount_value_returns_zero(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "not-a-number"
        host._discount_type = "fixed"
        host._tax_rate = "0"
        _insert_row(host, "X", "10", "10")
        host._items_table.blockSignals(True)
        host._recalc_all()
        host._items_table.blockSignals(False)
        assert "0.00 EUR" in host._canvas_discount_label.text()

    def test_invalid_tax_rate_returns_zero(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "0"
        host._tax_rate = "abc"
        _insert_row(host, "X", "10", "10")
        host._items_table.blockSignals(True)
        host._recalc_all()
        host._items_table.blockSignals(False)
        assert "0.00 EUR" in host._canvas_tax_label.text()


# ── Total display ──────────────────────────────────────────────────────────

class TestUpdateTotalsDisplay:
    """Tests for ``_update_totals_display``."""

    def test_updates_all_labels(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._update_totals_display(
            subtotal=200.0,
            tax_amount=38.0,
            discount_amount=20.0,
            grand_total=218.0,
        )
        assert host._canvas_subtotal_label.text() == "200.00 EUR"
        assert host._canvas_tax_label.text() == "38.00 EUR"
        assert host._canvas_discount_label.text() == "20.00 EUR"
        assert host._canvas_grand_label.text() == "218.00 EUR"

    def test_uses_currency_from_host(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._currency = "USD"
        host._update_totals_display(subtotal=99.99, grand_total=99.99)
        assert "99.99 USD" in host._canvas_grand_label.text()

    def test_formats_thousands(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._update_totals_display(subtotal=1234567.89)
        assert "1,234,567.89" in host._canvas_subtotal_label.text()

    def test_defaults_to_zero(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._update_totals_display()
        assert "0.00 EUR" in host._canvas_subtotal_label.text()
        assert "0.00 EUR" in host._canvas_tax_label.text()
        assert "0.00 EUR" in host._canvas_discount_label.text()
        assert "0.00 EUR" in host._canvas_grand_label.text()


# ── Signal handlers ────────────────────────────────────────────────────────

class TestSignalHandlers:
    """Tests for individual signal handlers."""

    def test_on_table_cell_changed_syncs_and_recalcs(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        with pytest.MonkeyPatch().context() as mp:
            sync = MagicMock()
            recalc = MagicMock()
            mp.setattr(host, "_sync_items_from_table", sync)
            mp.setattr(host, "_recalc_all", recalc)
            host._on_table_cell_changed(0, 0)
            sync.assert_called_once()
            recalc.assert_called_once()

    def test_on_description_changed(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._desc_text_edit.setPlainText("New description text")
        host._on_description_changed()
        assert host._description == "New description text"

    def test_on_tax_rate_changed_updates_and_recalcs(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        with pytest.MonkeyPatch().context() as mp:
            recalc = MagicMock()
            mp.setattr(host, "_recalc_all", recalc)
            host._on_tax_rate_changed("24")
            assert host._tax_rate == "24"
            recalc.assert_called_once()

    def test_on_discount_type_changed_to_percentage(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        with pytest.MonkeyPatch().context() as mp:
            recalc = MagicMock()
            mp.setattr(host, "_recalc_all", recalc)
            # t() returns the key when no translation loaded
            host._on_discount_type_changed(
                "proforma_editor.discount_percentage"
            )
            assert host._discount_type == "percentage"
            recalc.assert_called_once()

    def test_on_discount_type_changed_to_fixed(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        with pytest.MonkeyPatch().context() as mp:
            recalc = MagicMock()
            mp.setattr(host, "_recalc_all", recalc)
            host._on_discount_type_changed("proforma_editor.discount_fixed")
            assert host._discount_type == "fixed"
            recalc.assert_called_once()

    def test_on_discount_value_changed(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        with pytest.MonkeyPatch().context() as mp:
            recalc = MagicMock()
            mp.setattr(host, "_recalc_all", recalc)
            host._on_discount_value_changed("15")
            assert host._discount_value == "15"
            recalc.assert_called_once()

    def test_on_currency_changed_updates_display(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        with pytest.MonkeyPatch().context() as mp:
            display = MagicMock()
            mp.setattr(host, "_update_totals_display", display)
            host._on_currency_changed("USD")
            assert host._currency == "USD"
            display.assert_called_once()


# ── Edge cases ─────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Boundary and edge-case scenarios."""

    def test_many_rows(self, qtbot) -> None:
        """Adding 50 rows should not crash."""
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        for _ in range(50):
            host._add_row()
        assert host._items_table.rowCount() == 50

    def test_recalc_after_clearing_table(self, qtbot) -> None:
        """Remove all rows and recalc — should go back to zero."""
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "0"
        host._tax_rate = "19"
        host._add_row()
        host._items_table.setRowCount(0)
        host._recalc_all()
        assert "0.00" in host._canvas_subtotal_label.text()
        assert "0.00" in host._canvas_tax_label.text()

    def test_negative_quantity_results_in_negative_amount(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "0"
        host._tax_rate = "0"
        _insert_row(host, "Credit", "-1", "50")
        host._items_table.blockSignals(True)
        host._recalc_all()
        host._items_table.blockSignals(False)
        assert "-50.00 EUR" in host._canvas_subtotal_label.text()

    def test_tax_rate_zero_does_not_affect_total(self, qtbot) -> None:
        host = ProformaLineItemsHost()
        qtbot.addWidget(host)
        host._discount_value = "0"
        host._tax_rate = "0"
        host._add_row()
        # Update via the mixin's own methods (signals managed internally)
        host._items_table.item(0, 0).setText("X")
        host._items_table.item(0, 1).setText("10")
        host._items_table.item(0, 2).setText("5")
        # The cellChanged handler will catch changes
        host._recalc_all()
        assert "50.00 EUR" in host._canvas_grand_label.text()
