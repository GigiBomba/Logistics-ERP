"""Line items table and totals mixin for QtInvoiceEditor."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import Btn, Divider, SectionTitle
from ui.design_tokens import SP
from ui.widgets import (
    StyledComboBox,
    StyledLineEdit,
    StyledTableWidget,
    field,
)


class LineItemsMixin:
    """Mixin providing line-items table and totals UI + logic.

    Designed to be mixed into ``QtInvoiceEditor`` — expects the host to
    provide ``self._scroll`` (ScrollableFormContainer), ``self._make_card()``,
    ``self._recalc_task`` (DebouncedTask), and the invoice-data attributes
    (``_addon_items``, ``_tax_rate``, etc.).
    """

    # ══════════════════════════════════════════════════════════════════════
    # LINE ITEMS TABLE
    # ══════════════════════════════════════════════════════════════════════

    def _build_line_items_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP["3"])

        self._lit_header_label = SectionTitle(container, t("invoice_editor.line_items"))
        layout.addWidget(self._lit_header_label)

        card = self._make_card()
        card_layout = card.layout()
        card_layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        card_layout.setSpacing(SP["2"])

        # Line items table
        self._items_table = StyledTableWidget(
            parent=card,
            columns=[
                ("idx", "#", 30),
                ("description", t("invoice_editor.description"), 300),
                ("amount", t("invoice_editor.amount"), 100),
            ],
        )
        self._items_table.setMinimumHeight(150)
        # Single-click (or F2 / typing) into a cell drops the user
        # straight into edit mode.  ``DoubleClicked`` would force the
        # user to click twice on every row, which is hostile to
        # spreadsheet-style workflows.
        self._items_table.setEditTriggers(
            QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )
        self._items_table.cellChanged.connect(self._on_table_cell_changed)
        # ``currentCellChanged`` fires when the user clicks out of a
        # cell.  We use it to re-format the *previous* amount cell on
        # focus-leave rather than on every keystroke (which would
        # reset the cursor to position 0 mid-typing).
        self._items_table.currentCellChanged.connect(
            self._on_table_current_cell_changed
        )
        self._last_amount_row: int | None = None
        card_layout.addWidget(self._items_table)

        # Button row
        btn_row = QWidget()
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(SP["2"])

        self._add_row_btn = Btn(
            btn_row, "+ " + t("invoice_editor.add_row"), variant="secondary"
        )
        self._add_row_btn.clicked.connect(self._add_addon_row)
        btn_row_layout.addWidget(self._add_row_btn)

        remove_btn = Btn(
            btn_row, "\u2716 " + t("invoice_editor.remove_row"), variant="ghost"
        )
        remove_btn.clicked.connect(self._remove_selected_addon)
        btn_row_layout.addWidget(remove_btn)

        btn_row_layout.addStretch()
        card_layout.addWidget(btn_row)

        layout.addWidget(card)
        self._scroll.add_widget(container)

    def _sync_table_to_items(self) -> None:
        """Refresh the table widget from ``_addon_items``."""
        self._items_table.blockSignals(True)
        self._items_table.setRowCount(len(self._addon_items))
        for r, item in enumerate(self._addon_items):
            # Index
            idx_item = QTableWidgetItem(str(r + 1))
            idx_item.setFlags(idx_item.flags() & ~Qt.ItemIsEditable)
            self._items_table.setItem(r, 0, idx_item)

            # Description
            desc = item.get("description", "")
            desc_item = QTableWidgetItem(desc)
            self._items_table.setItem(r, 1, desc_item)

            # Amount
            amt = item.get("amount", 0)
            amt_item = QTableWidgetItem(f"{amt:.2f}")
            self._items_table.setItem(r, 2, amt_item)

        self._items_table.blockSignals(False)
        self._recalc_all()

    def _on_table_cell_changed(self, row: int, col: int) -> None:
        if row >= len(self._addon_items):
            return
        item = self._addon_items[row]
        widget_item = self._items_table.item(row, col)
        if widget_item is None:
            return
        text = widget_item.text()
        if col == 1:
            item["description"] = text
        elif col == 2:
            # Update the parsed amount so totals stay in sync, but do
            # *not* reformat the cell here — that would reset the
            # cursor to position 0 mid-typing.  Reformatting happens
            # on focus-leave via ``_on_table_current_cell_changed``.
            try:
                item["amount"] = round(float(text or "0"), 2)
            except ValueError:
                item["amount"] = 0.0
            self._last_amount_row = row
        self._recalc_all()

    def _on_table_current_cell_changed(
        self, current_row: int, current_col: int, previous_row: int, previous_col: int
    ) -> None:
        """Reformat the *previous* amount cell on focus-leave so the
        user sees ``1.50`` instead of ``1.5`` when they tab away,
        without ever disrupting the cell they're currently typing in.
        """
        if previous_col != 2:
            return
        if previous_row < 0 or previous_row >= len(self._addon_items):
            return
        if previous_row == current_row and previous_col == current_col:
            return
        widget_item = self._items_table.item(previous_row, 2)
        if widget_item is None:
            return
        amount = self._addon_items[previous_row].get("amount", 0.0)
        formatted = f"{float(amount):.2f}"
        if widget_item.text() != formatted:
            # ``blockSignals`` so ``_on_table_cell_changed`` doesn't
            # re-fire and clobber the user's just-committed value.
            self._items_table.blockSignals(True)
            widget_item.setText(formatted)
            self._items_table.blockSignals(False)
        self._last_amount_row = None

    def _add_addon_row(self, data: dict | None = None) -> None:
        if data is None:
            data = {"description": "", "amount": 0.0}
        self._addon_items.append(data)
        self._sync_table_to_items()

    def _remove_selected_addon(self) -> None:
        row = self._items_table.currentRow()
        if row < 0 or len(self._addon_items) <= 1:
            return
        del self._addon_items[row]
        self._sync_table_to_items()

    def _add_default_addon_item(self) -> None:
        if not self._addon_items:
            self._addon_items = [{"description": "", "amount": 0.0}]
        self._sync_table_to_items()

    # ══════════════════════════════════════════════════════════════════════
    # TOTALS SECTION
    # ══════════════════════════════════════════════════════════════════════

    def _build_totals_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP["3"])

        header = SectionTitle(container, t("invoice_editor.totals"))
        layout.addWidget(header)

        card = self._make_card()
        card_layout = card.layout()
        card_layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        card_layout.setSpacing(SP["3"])

        # Financial controls
        self._financial_header = QLabel(t("invoice_editor.financial_controls").upper())
        self._financial_header.setProperty("fontRole", "section")
        card_layout.addWidget(self._financial_header)

        # Tax rate
        tax_row = QWidget()
        tax_row_layout = QHBoxLayout(tax_row)
        tax_row_layout.setContentsMargins(0, 0, 0, 0)
        tax_row_layout.setSpacing(SP["2"])

        self._tax_label = QLabel(t("invoice_editor.tax_rate"))
        self._tax_label.setProperty("fontRole", "label")
        tax_row_layout.addWidget(self._tax_label)

        self._tax_combo = StyledComboBox(values=["0", "5", "9", "19", "20", "21", "24", "25"])
        self._tax_combo.setCurrentText(self._tax_rate)
        self._tax_combo.currentTextChanged.connect(self._on_tax_rate_changed)
        self._tax_combo.setFixedWidth(80)
        tax_row_layout.addWidget(self._tax_combo)

        pct_label = QLabel(t("common.percent"))
        pct_label.setProperty("fontRole", "label")
        tax_row_layout.addWidget(pct_label)
        tax_row_layout.addStretch()

        card_layout.addWidget(tax_row)

        # Discount
        disc_row = QWidget()
        disc_row_layout = QHBoxLayout(disc_row)
        disc_row_layout.setContentsMargins(0, 0, 0, 0)
        disc_row_layout.setSpacing(SP["2"])

        self._discount_label = QLabel(t("invoice_editor.discount"))
        self._discount_label.setProperty("fontRole", "label")
        disc_row_layout.addWidget(self._discount_label)

        disc_values = [
            t("invoice_editor.discount_percentage"),
            t("invoice_editor.discount_fixed"),
        ]
        self._disc_type_combo = StyledComboBox(values=disc_values)
        self._disc_type_combo.setCurrentText(disc_values[0])
        self._discount_type = disc_values[0]
        self._disc_type_combo.currentTextChanged.connect(self._on_discount_type_changed)
        self._disc_type_combo.setFixedWidth(100)
        disc_row_layout.addWidget(self._disc_type_combo)

        self._disc_entry = StyledLineEdit(text=self._discount_value, height=32)
        self._disc_entry.setFixedWidth(70)
        self._disc_entry.textChanged.connect(self._on_discount_value_changed)
        disc_row_layout.addWidget(self._disc_entry)

        self._disc_symbol_lbl = QLabel(t("common.percent"))
        self._disc_symbol_lbl.setProperty("fontRole", "label")
        disc_row_layout.addWidget(self._disc_symbol_lbl)
        disc_row_layout.addStretch()

        card_layout.addWidget(disc_row)

        # Currency
        curr_row = QWidget()
        curr_row_layout = QHBoxLayout(curr_row)
        curr_row_layout.setContentsMargins(0, 0, 0, 0)
        curr_row_layout.setSpacing(SP["2"])

        self._currency_label = QLabel(t("invoice_editor.currency"))
        self._currency_label.setProperty("fontRole", "label")
        curr_row_layout.addWidget(self._currency_label)

        self._curr_combo = StyledComboBox(values=["EUR", "RON", "USD", "GBP"])
        self._curr_combo.setCurrentText(self._currency)
        self._curr_combo.currentTextChanged.connect(self._on_currency_changed)
        self._curr_combo.setFixedWidth(80)
        curr_row_layout.addWidget(self._curr_combo)
        curr_row_layout.addStretch()

        card_layout.addWidget(curr_row)

        # Separator
        card_layout.addWidget(Divider())

        # Totals display
        self._subtotal_title = QLabel(t("invoice_editor.subtotal"))
        self._subtotal_title.setProperty("fontRole", "label")
        card_layout.addWidget(self._subtotal_title)
        self._subtotal_lbl = QLabel(t("common.zero_amount"))
        self._subtotal_lbl.setProperty("fontRole", "body")
        self._subtotal_lbl.setAlignment(Qt.AlignRight)
        card_layout.addWidget(self._subtotal_lbl)

        self._tax_title = QLabel(t("invoice_editor.tax"))
        self._tax_title.setProperty("fontRole", "label")
        card_layout.addWidget(self._tax_title)
        self._tax_lbl = QLabel(t("common.zero_amount"))
        self._tax_lbl.setProperty("fontRole", "body")
        self._tax_lbl.setAlignment(Qt.AlignRight)
        card_layout.addWidget(self._tax_lbl)

        self._discount_title = QLabel(t("invoice_editor.discount"))
        self._discount_title.setProperty("fontRole", "label")
        card_layout.addWidget(self._discount_title)
        self._discount_lbl = QLabel(t("common.zero_amount"))
        self._discount_lbl.setProperty("fontRole", "body")
        self._discount_lbl.setAlignment(Qt.AlignRight)
        card_layout.addWidget(self._discount_lbl)

        self._grand_title = QLabel(t("invoice_editor.grand_total"))
        self._grand_title.setProperty("fontRole", "label")
        card_layout.addWidget(self._grand_title)
        self._grand_lbl = QLabel(t("common.zero_amount"))
        self._grand_lbl.setProperty("fontRole", "body-bold")
        self._grand_lbl.setAlignment(Qt.AlignRight)
        card_layout.addWidget(self._grand_lbl)

        # Canvas totals (also shown in preview area)
        canvas_totals_card = QFrame()
        canvas_totals_card.setProperty("role", "card-inner")
        canvas_totals_layout = QVBoxLayout(canvas_totals_card)
        canvas_totals_layout.setContentsMargins(SP["3"], SP["3"], SP["3"], SP["3"])
        canvas_totals_layout.setSpacing(SP["1"])

        self._canvas_subtotal_label = QLabel(t("invoice_editor.subtotal"))
        self._canvas_subtotal_label.setProperty("fontRole", "label")
        canvas_totals_layout.addWidget(self._canvas_subtotal_label)
        self._canvas_subtotal = QLabel(t("common.zero_amount"))
        self._canvas_subtotal.setProperty("fontRole", "body")
        self._canvas_subtotal.setAlignment(Qt.AlignRight)
        canvas_totals_layout.addWidget(self._canvas_subtotal)

        self._canvas_tax_label = QLabel(t("invoice_editor.tax"))
        self._canvas_tax_label.setProperty("fontRole", "label")
        canvas_totals_layout.addWidget(self._canvas_tax_label)
        self._canvas_tax = QLabel(t("common.zero_amount"))
        self._canvas_tax.setProperty("fontRole", "body")
        self._canvas_tax.setAlignment(Qt.AlignRight)
        canvas_totals_layout.addWidget(self._canvas_tax)

        self._canvas_discount_label = QLabel(t("invoice_editor.discount"))
        self._canvas_discount_label.setProperty("fontRole", "label")
        canvas_totals_layout.addWidget(self._canvas_discount_label)
        self._canvas_discount = QLabel(t("common.zero_amount"))
        self._canvas_discount.setProperty("fontRole", "body")
        self._canvas_discount.setAlignment(Qt.AlignRight)
        canvas_totals_layout.addWidget(self._canvas_discount)

        canvas_totals_layout.addWidget(Divider())

        self._canvas_grand_label = QLabel(t("invoice_editor.grand_total"))
        self._canvas_grand_label.setProperty("fontRole", "body-bold")
        canvas_totals_layout.addWidget(self._canvas_grand_label)
        self._canvas_grand = QLabel(t("common.zero_amount"))
        self._canvas_grand.setProperty("fontRole", "body-bold")
        self._canvas_grand.setAlignment(Qt.AlignRight)
        canvas_totals_layout.addWidget(self._canvas_grand)

        card_layout.addWidget(canvas_totals_card)

        layout.addWidget(card)
        self._scroll.add_widget(container)

    def _on_tax_rate_changed(self, text: str) -> None:
        self._tax_rate = text
        self._recalc_all()

    def _on_discount_type_changed(self, text: str) -> None:
        self._discount_type = text
        is_percent = text == t("invoice_editor.discount_percentage")
        self._disc_symbol_lbl.setText(t("common.percent") if is_percent else self._get_currency_symbol(self._currency))
        self._recalc_all()

    def _on_discount_value_changed(self, text: str) -> None:
        self._discount_value = text
        self._recalc_all()

    def _on_currency_changed(self, text: str) -> None:
        self._currency = text
        self._recalc_all()

    # ══════════════════════════════════════════════════════════════════════
    # CALCULATIONS
    # ══════════════════════════════════════════════════════════════════════

    def _recalc_all(self) -> None:
        """Debounced recalculation (called directly from 12+ signal handlers)."""
        self._recalc_task.schedule()

    def _calculate_totals(self) -> dict[str, float]:
        """Compute invoice totals from current form state.

        Delegates the arithmetic to a single shared helper so that both
        the preview UI (``_refresh_totals_display``) and the PDF data
        collector (``_collect_invoice_data``) use the same logic.

        For DB-persisted invoices with typed line items,
        ``InvoiceService.recalculate()`` provides the service-level equivalent.
        For new invoices, ``InvoiceService.create(InvoiceCreate(...))`` auto-calculates
        line-item totals from quantity/unit_price/vat_rate.
        """
        try:
            tax_rate = float(self._tax_rate or 0)
            disc_val = float(self._discount_value or 0)
            trip_price = float(self._trip_base_price or 0)
        except ValueError:
            tax_rate = 0
            disc_val = 0
            trip_price = 0

        # Trip base price + addon items → subtotal
        subtotal = round(trip_price, 2)
        for item in self._addon_items:
            try:
                amt = round(float(item.get("amount", 0) or 0), 2)
            except ValueError:
                amt = 0.0
            item["amount"] = amt
            subtotal = round(subtotal + amt, 2)

        total_tax = round(subtotal * (tax_rate / 100), 2)

        # Discount (percentage or fixed)
        is_percent = self._discount_type == t("invoice_editor.discount_percentage")
        discount = round(subtotal * (disc_val / 100), 2) if is_percent else round(disc_val, 2)

        grand_total = round(subtotal + total_tax - discount, 2)

        return {
            "subtotal": subtotal,
            "total_tax": total_tax,
            "discount": discount,
            "grand_total": grand_total,
            "is_percent": is_percent,
            "tax_rate": tax_rate,
            "disc_value": disc_val,
            "trip_price": trip_price,
        }

    def _refresh_totals_display(self) -> None:
        """Update all totals displays based on addon items and settings.

        Calculation is delegated to ``_calculate_totals()`` so the same
        arithmetic is shared with ``_collect_invoice_data()``.
        """
        calc = self._calculate_totals()
        currency = self._currency
        sym = self._get_currency_symbol(currency)

        # Update side panel totals
        self._subtotal_lbl.setText(f"{sym}{calc['subtotal']:,.2f}")
        self._tax_lbl.setText(f"{sym}{calc['total_tax']:,.2f}")
        discount_sign = "-" if calc["discount"] > 0 else ""
        self._discount_lbl.setText(f"{discount_sign}{sym}{calc['discount']:,.2f}")
        self._grand_lbl.setText(f"{sym}{calc['grand_total']:,.2f}")

        # Update canvas totals
        self._canvas_subtotal.setText(f"{sym}{calc['subtotal']:,.2f}")
        self._canvas_tax.setText(f"{sym}{calc['total_tax']:,.2f}")
        canvas_discount_sign = "-" if calc["discount"] > 0 else ""
        self._canvas_discount.setText(f"{canvas_discount_sign}{sym}{calc['discount']:,.2f}")
        self._canvas_grand.setText(f"{sym}{calc['grand_total']:,.2f}")

        # Update discount symbol
        if calc["is_percent"]:
            self._disc_symbol_lbl.setText(t("common.percent"))
        else:
            self._disc_symbol_lbl.setText(sym)

    def _get_currency_symbol(self, code: str) -> str:
        symbols = {"EUR": "\u20AC", "RON": "lei", "USD": "$", "GBP": "\u00A3"}
        return symbols.get(code, code)
