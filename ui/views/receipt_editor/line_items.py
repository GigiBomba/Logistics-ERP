"""Line items table management and calculation for the receipt editor.

Provides a mixin that adds line-items table operations (add, remove, recalculate)
following the same pattern as ``proforma_editor.py`` and ``invoice_editor.py``.
"""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QTableWidgetItem, QWidget

from services.i18n import t
from ui.components import Btn, Label, SectionTitle
from ui.theme import COLORS, S
from ui.widgets import StyledLineEdit, StyledTableWidget

logger = logging.getLogger(__name__)


class LineItemsMixin:
    """Mixin that adds line-items table and calculation to ``QtReceiptEditor``.

    Expected attributes on the host (set by ``_build_line_items_section()``):
    * ``_line_items_table`` -- a ``StyledTableWidget`` for line items
    * ``_line_items`` -- ``list[dict]`` of parsed line items

    Optional display labels (set by ``_build_line_items_section()``):
    * ``_canvas_subtotal_label``, ``_canvas_tax_label``,
      ``_canvas_discount_label``, ``_canvas_grand_label``
    """

    # ── Safe float (shared utility) ────────────────────────────────────

    @staticmethod
    def _safe_float(val: str) -> float:
        """Parse a decimal string (commas OK) -> float, return 0 on failure."""
        try:
            return float(val.replace(",", ".")) if val.strip() else 0
        except (ValueError, AttributeError):
            return 0

    # ── Line items table construction ──────────────────────────────────

    def _build_line_items_section(self) -> QWidget:
        """Build and return a container widget with the items table + totals card.

        The caller should add the returned widget to the scroll area.
        This method creates ``self._line_items_table`` and the four totals labels.
        """
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        # ── Table card ──────────────────────────────────────────────────
        from ui.components import Card, Divider

        table_card = Card(container)
        table_layout = table_card.layout()

        self._lit_header_label = SectionTitle(table_card, t("receipt.section_line_items").upper())
        table_layout.addWidget(self._lit_header_label)
        table_layout.addWidget(Divider(table_card))

        self._line_items_table = StyledTableWidget()
        self._line_items_table.setColumnCount(4)
        self._line_items_table.setHorizontalHeaderLabels([
            t("receipt.line_items.description"),
            t("receipt.line_items.quantity"),
            t("receipt.line_items.unit_price"),
            t("receipt.line_items.total"),
        ])
        self._line_items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._line_items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self._line_items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self._line_items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self._line_items_table.setColumnWidth(1, 80)
        self._line_items_table.setColumnWidth(2, 120)
        self._line_items_table.setColumnWidth(3, 120)
        self._line_items_table.cellChanged.connect(self._on_table_cell_changed)
        table_layout.addWidget(self._line_items_table)

        # Add-row button
        add_row_btn = Btn(
            table_card,
            "+ " + t("receipt.line_items.add_row"),
            command=self._add_item_row,
            variant="ghost",
        )
        table_layout.addWidget(add_row_btn)

        # Remove selected button
        remove_btn = Btn(
            table_card,
            "\u2212 " + t("receipt.line_items.remove_selected"),
            command=self._remove_item,
            variant="ghost",
        )
        table_layout.addWidget(remove_btn)

        layout.addWidget(table_card, 1)

        # ── Totals card ────────────────────────────────────────────────
        totals_card = Card(container)
        totals_layout = totals_card.layout()

        self._totals_header = SectionTitle(totals_card, t("receipt.section_totals").upper())
        totals_layout.addWidget(self._totals_header)
        totals_layout.addWidget(Divider(totals_card))

        totals_layout.addWidget(Label(totals_card, t("receipt.line_items.subtotal"), role="label"))
        self._canvas_subtotal_label = Label(totals_card, "0.00", role="body-bold")
        totals_layout.addWidget(self._canvas_subtotal_label)

        totals_layout.addWidget(Label(totals_card, t("receipt.line_items.tax"), role="label"))
        self._canvas_tax_label = Label(totals_card, "0.00", role="body-bold")
        totals_layout.addWidget(self._canvas_tax_label)

        totals_layout.addWidget(Label(totals_card, t("receipt.line_items.discount"), role="label"))
        self._canvas_discount_label = Label(totals_card, "0.00", role="body-bold")
        totals_layout.addWidget(self._canvas_discount_label)

        totals_layout.addWidget(Label(totals_card, t("receipt.line_items.grand_total"), role="label"))
        self._canvas_grand_label = Label(totals_card, "0.00", role="body-bold")
        totals_layout.addWidget(self._canvas_grand_label)

        layout.addWidget(totals_card, 1)

        # Ensure the line items list exists
        if not hasattr(self, "_line_items"):
            self._line_items: list[dict[str, Any]] = []

        return container

    # ── Row operations ─────────────────────────────────────────────────

    def _add_item_row(self, desc: str = "", qty: str = "1", price: str = "0.00") -> None:
        """Insert a new row at the bottom of the items table."""
        self._line_items_table.blockSignals(True)
        row = self._line_items_table.rowCount()
        self._line_items_table.insertRow(row)
        self._line_items_table.setItem(row, 0, QTableWidgetItem(desc))
        self._line_items_table.setItem(row, 1, QTableWidgetItem(qty))
        self._line_items_table.setItem(row, 2, QTableWidgetItem(price))
        total_item = QTableWidgetItem("0.00")
        total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
        self._line_items_table.setItem(row, 3, total_item)
        self._line_items_table.blockSignals(False)

        self._calculate_totals()

    def _remove_item(self) -> None:
        """Remove the currently selected row from the items table."""
        row = self._line_items_table.currentRow()
        if row < 0 or row >= self._line_items_table.rowCount():
            return
        self._line_items_table.removeRow(row)
        self._calculate_totals()

    def _on_table_cell_changed(self, row: int, col: int) -> None:
        """Recalculate when any cell in the items table changes."""
        self._calculate_totals()

    # ── Calculation ────────────────────────────────────────────────────

    def _calculate_totals(self) -> None:
        """Read the items table, compute subtotal / tax / discount / grand total, and update display."""
        self._sync_items_from_table()

        # Subtotal = sum of all line item amounts
        subtotal = sum(
            item.get("amount", 0) for item in getattr(self, "_line_items", [])
        )

        # Discount (if the host has discount controls)
        discount_amount = 0
        if hasattr(self, "_discount_value"):
            try:
                disc_val = float(getattr(self, "_discount_value", "0") or "0")
            except (ValueError, TypeError):
                disc_val = 0
            disc_type = getattr(self, "_discount_type", "fixed")
            if disc_type == "percentage" and disc_val > 0:
                discount_amount = subtotal * (disc_val / 100)
            else:
                discount_amount = disc_val if disc_type == "fixed" else 0
            if discount_amount > subtotal:
                discount_amount = subtotal

        after_discount = subtotal - discount_amount

        # Tax (if the host has a tax rate control)
        tax_amount = 0
        if hasattr(self, "_tax_rate"):
            try:
                tax_rate = float(getattr(self, "_tax_rate", "0") or "0")
            except (ValueError, TypeError):
                tax_rate = 0
            tax_amount = after_discount * (tax_rate / 100)

        grand_total = after_discount + tax_amount

        self._update_total_display(subtotal, tax_amount, discount_amount, grand_total)

    def _sync_items_from_table(self) -> None:
        """Read all rows from ``self._line_items_table`` into ``self._line_items``."""
        if not hasattr(self, "_line_items_table") or self._line_items_table.rowCount() == 0:
            return
        items: list[dict[str, Any]] = []
        for row in range(self._line_items_table.rowCount()):
            desc_item = self._line_items_table.item(row, 0)
            qty_item = self._line_items_table.item(row, 1)
            price_item = self._line_items_table.item(row, 2)
            if not desc_item or not qty_item or not price_item:
                continue
            desc = desc_item.text().strip()
            qty = self._safe_float(qty_item.text())
            unit_price = self._safe_float(price_item.text())
            total = round(qty * unit_price, 2)
            # Update total column
            total_item = self._line_items_table.item(row, 3)
            if total_item:
                total_item.setText(f"{total:.2f}")
            if desc or total != 0:
                items.append({
                    "description": desc,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "amount": total,
                })
        self._line_items = items

    def _update_total_display(
        self,
        subtotal: float = 0,
        tax_amount: float = 0,
        discount_amount: float = 0,
        grand_total: float = 0,
    ) -> None:
        """Update the four total labels in the totals card."""
        curr = getattr(self, "_currency", "EUR")
        if hasattr(self, "_canvas_subtotal_label"):
            self._canvas_subtotal_label.setText(f"{subtotal:,.2f} {curr}")
        if hasattr(self, "_canvas_tax_label"):
            self._canvas_tax_label.setText(f"{tax_amount:,.2f} {curr}")
        if hasattr(self, "_canvas_discount_label"):
            self._canvas_discount_label.setText(f"{discount_amount:,.2f} {curr}")
        if hasattr(self, "_canvas_grand_label"):
            self._canvas_grand_label.setText(f"{grand_total:,.2f} {curr}")
