"""Line items table and totals mixin for QtProformaEditor."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import Btn, SectionTitle
from ui.theme import S
from ui.widgets import (
    StyledComboBox,
    StyledLineEdit,
    StyledTableWidget,
    StyledTextEdit,
)


class LineItemsMixin:
    """Mixin providing line-items table and totals UI + logic.

    Designed to be mixed into ``QtProformaEditor`` — expects the host to
    provide ``self._scroll`` (ScrollableFormContainer), ``self._make_card()``,
    ``self._recalc_task`` (DebouncedTask), and the proforma-data attributes
    (``_addon_items``, ``_tax_rate``, etc.).
    """

    # ══════════════════════════════════════════════════════════════════════
    # LINE ITEMS TABLE
    # ══════════════════════════════════════════════════════════════════════

    def _build_line_items_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["2"])

        self._lit_header_label = SectionTitle(container, t("proforma_editor.line_items"))
        layout.addWidget(self._lit_header_label)

        # Line items table
        self._items_table = StyledTableWidget()
        self._items_table.setColumnCount(4)
        self._items_table.setHorizontalHeaderLabels([
            t("proforma_editor.description"),
            t("proforma_editor.quantity"),
            t("proforma_editor.unit_price"),
            t("proforma_editor.total"),
        ])
        self._items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self._items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self._items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self._items_table.setColumnWidth(1, 80)
        self._items_table.setColumnWidth(2, 120)
        self._items_table.setColumnWidth(3, 120)
        self._items_table.cellChanged.connect(self._on_table_cell_changed)
        layout.addWidget(self._items_table)

        # Add row button
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self._add_row_btn = Btn(container, "+ " + t("proforma_editor.add_row"), variant="ghost")
        self._add_row_btn.clicked.connect(self._add_row)
        btn_layout.addWidget(self._add_row_btn)
        btn_layout.addStretch()
        layout.addWidget(btn_row)

        # Description
        self._desc_label = QLabel(t("proforma_editor.description"))
        self._desc_label.setProperty("fontRole", "label")
        layout.addWidget(self._desc_label)
        self._desc_text_edit = StyledTextEdit()
        self._desc_text_edit.textChanged.connect(self._on_description_changed)
        self._desc_text_edit.setMaximumHeight(80)
        layout.addWidget(self._desc_text_edit)

        self._scroll.add_widget(container)

    # ══════════════════════════════════════════════════════════════════════
    # TOTALS SECTION
    # ══════════════════════════════════════════════════════════════════════

    def _build_totals_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        # Financial controls header
        self._financial_header = SectionTitle(container, t("proforma_editor.financial_controls"))
        layout.addWidget(self._financial_header)

        # Controls row
        controls = QWidget()
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(S["3"])

        # Tax rate
        self._tax_label = QLabel(t("proforma_editor.tax_rate"))
        self._tax_label.setProperty("fontRole", "label")
        ctrl_layout.addWidget(self._tax_label)
        self._tax_combo = StyledComboBox()
        self._tax_combo.addItems(["0", "5", "9", "19", "20", "21", "24", "27"])
        self._tax_combo.setCurrentText(self._tax_rate)
        self._tax_combo.currentTextChanged.connect(self._on_tax_rate_changed)
        self._tax_combo.setFixedWidth(80)
        ctrl_layout.addWidget(self._tax_combo)

        # Discount type
        self._discount_label = QLabel(t("proforma_editor.discount"))
        self._discount_label.setProperty("fontRole", "label")
        ctrl_layout.addWidget(self._discount_label)
        self._disc_type_combo = StyledComboBox()
        self._disc_type_combo.addItems([
            t("proforma_editor.discount_percentage"),
            t("proforma_editor.discount_fixed"),
        ])
        self._disc_type_combo.currentTextChanged.connect(self._on_discount_type_changed)
        self._disc_type_combo.setFixedWidth(120)
        ctrl_layout.addWidget(self._disc_type_combo)

        # Discount value
        self._disc_entry = StyledLineEdit("0")
        self._disc_entry.setFixedWidth(80)
        self._disc_entry.textChanged.connect(self._on_discount_value_changed)
        ctrl_layout.addWidget(self._disc_entry)

        # Currency
        self._currency_label = QLabel(t("proforma_editor.currency"))
        self._currency_label.setProperty("fontRole", "label")
        ctrl_layout.addWidget(self._currency_label)
        self._curr_combo = StyledComboBox()
        self._curr_combo.addItems(["EUR", "USD", "GBP", "RON", "HUF", "CZK", "PLN", "BGN"])
        self._curr_combo.setCurrentText(self._currency)
        self._curr_combo.currentTextChanged.connect(self._on_currency_changed)
        self._curr_combo.setFixedWidth(80)
        ctrl_layout.addWidget(self._curr_combo)

        ctrl_layout.addStretch()
        layout.addWidget(controls)

        # Totals display card
        totals_card = self._make_card()
        totals_layout = totals_card.layout()
        totals_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        totals_layout.setSpacing(S["2"])

        self._subtotal_title = QLabel(t("proforma_editor.subtotal"))
        self._subtotal_title.setProperty("fontRole", "label")
        totals_layout.addWidget(self._subtotal_title)
        self._canvas_subtotal_label = QLabel("0.00 EUR")
        self._canvas_subtotal_label.setProperty("fontRole", "body")
        totals_layout.addWidget(self._canvas_subtotal_label)

        self._tax_title = QLabel(t("proforma_editor.tax"))
        self._tax_title.setProperty("fontRole", "label")
        totals_layout.addWidget(self._tax_title)
        self._canvas_tax_label = QLabel("0.00 EUR")
        self._canvas_tax_label.setProperty("fontRole", "body")
        totals_layout.addWidget(self._canvas_tax_label)

        self._discount_title = QLabel(t("proforma_editor.discount"))
        self._discount_title.setProperty("fontRole", "label")
        totals_layout.addWidget(self._discount_title)
        self._canvas_discount_label = QLabel("0.00 EUR")
        self._canvas_discount_label.setProperty("fontRole", "body")
        totals_layout.addWidget(self._canvas_discount_label)

        self._grand_title = QLabel(t("proforma_editor.grand_total"))
        self._grand_title.setProperty("fontRole", "label")
        totals_layout.addWidget(self._grand_title)
        self._canvas_grand_label = QLabel("0.00 EUR")
        self._canvas_grand_label.setProperty("fontRole", "body-bold")
        totals_layout.addWidget(self._canvas_grand_label)

        layout.addWidget(totals_card)
        self._scroll.add_widget(container)

    # ══════════════════════════════════════════════════════════════════════
    # LINE ITEM OPERATIONS
    # ══════════════════════════════════════════════════════════════════════

    def _add_default_item(self) -> None:
        self._add_row()
        # Set default item description
        if self._items_table.rowCount() > 0:
            self._items_table.blockSignals(True)
            item = self._items_table.item(0, 0)
            if item:
                item.setText("Transport services")
            self._items_table.blockSignals(False)

    def _add_row(self) -> None:
        self._items_table.blockSignals(True)
        row = self._items_table.rowCount()
        self._items_table.insertRow(row)
        self._items_table.setItem(row, 0, QTableWidgetItem(""))
        self._items_table.setItem(row, 1, QTableWidgetItem("1"))
        self._items_table.setItem(row, 2, QTableWidgetItem("0.00"))
        total_item = QTableWidgetItem("0.00")
        total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
        self._items_table.setItem(row, 3, total_item)
        self._items_table.blockSignals(False)

    def _sync_items_from_table(self) -> None:
        self._addon_items = []
        for row in range(self._items_table.rowCount()):
            desc_item = self._items_table.item(row, 0)
            qty_item = self._items_table.item(row, 1)
            price_item = self._items_table.item(row, 2)
            if not desc_item or not qty_item or not price_item:
                continue
            desc = desc_item.text().strip()
            try:
                qty = float(qty_item.text() or "0")
            except ValueError:
                qty = 0
            try:
                unit_price = float(price_item.text() or "0")
            except ValueError:
                unit_price = 0
            total = qty * unit_price
            # Update total column
            total_item = self._items_table.item(row, 3)
            if total_item:
                total_item.setText(f"{total:.2f}")
            if desc or total != 0:
                self._addon_items.append({
                    "description": desc,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "amount": total,
                })

    def _recalc_all(self) -> None:
        self._sync_items_from_table()
        # Subtotal
        subtotal = sum(item.get("amount", 0) for item in self._addon_items)
        # Discount
        try:
            disc_val = float(self._discount_value or "0")
        except ValueError:
            disc_val = 0
        if self._discount_type == "percentage" and disc_val > 0:
            discount_amount = subtotal * (disc_val / 100)
        else:
            discount_amount = disc_val if self._discount_type == "fixed" else 0
        if discount_amount > subtotal:
            discount_amount = subtotal
        after_discount = subtotal - discount_amount
        # Tax
        try:
            tax_rate = float(self._tax_rate or "0")
        except ValueError:
            tax_rate = 0
        tax_amount = after_discount * (tax_rate / 100)
        grand_total = after_discount + tax_amount
        self._update_totals_display(subtotal, tax_amount, discount_amount, grand_total)

    def _update_totals_display(
        self,
        subtotal: float = 0,
        tax_amount: float = 0,
        discount_amount: float = 0,
        grand_total: float = 0,
    ) -> None:
        curr = self._currency
        self._canvas_subtotal_label.setText(f"{subtotal:,.2f} {curr}")
        self._canvas_tax_label.setText(f"{tax_amount:,.2f} {curr}")
        self._canvas_discount_label.setText(f"{discount_amount:,.2f} {curr}")
        self._canvas_grand_label.setText(f"{grand_total:,.2f} {curr}")

    # ══════════════════════════════════════════════════════════════════════
    # SIGNAL HANDLERS
    # ══════════════════════════════════════════════════════════════════════

    def _on_table_cell_changed(self, row: int, col: int) -> None:
        self._sync_items_from_table()
        self._recalc_all()

    def _on_description_changed(self) -> None:
        self._description = self._desc_text_edit.toPlainText()

    def _on_tax_rate_changed(self, text: str) -> None:
        self._tax_rate = text
        self._recalc_all()

    def _on_discount_type_changed(self, text: str) -> None:
        if text == t("proforma_editor.discount_percentage"):
            self._discount_type = "percentage"
        else:
            self._discount_type = "fixed"
        self._recalc_all()

    def _on_discount_value_changed(self, text: str) -> None:
        self._discount_value = text
        self._recalc_all()

    def _on_currency_changed(self, text: str) -> None:
        self._currency = text
        self._update_totals_display()
