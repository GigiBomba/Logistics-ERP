"""Tests for the shared PySide6 widget wrappers."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from ui.widgets import (
    StyledLineEdit,
    StyledTextEdit,
    StyledComboBox,
    ActionButton,
    StyledCheckBox,
    StyledRadioButton,
    SectionHeader,
    KpiCard,
    ScrollableFormContainer,
    TwoColRow,
    section_header,
    kpi_card,
)
from ui.widgets.date_picker import QtDatePicker, make_date_entry


class TestStyledLineEdit:
    def test_placeholder_and_height(self, qt_widget, qtbot):
        edit = StyledLineEdit(qt_widget, placeholder="Type here", height=42)
        qtbot.addWidget(edit)
        assert edit.placeholderText() == "Type here"
        assert edit.height() == 42

    def test_text_set_on_init(self, qt_widget, qtbot):
        edit = StyledLineEdit(qt_widget, text="hello")
        qtbot.addWidget(edit)
        assert edit.text() == "hello"


class TestActionButton:
    def test_text_and_click(self, qt_widget, qtbot):
        clicked = []
        btn = ActionButton(qt_widget, "Click Me", command=lambda: clicked.append(1))
        qtbot.addWidget(btn)
        assert btn.text() == "Click Me"
        qtbot.mouseClick(btn, Qt.LeftButton)
        assert clicked == [1]

    def test_variant_property(self, qt_widget, qtbot):
        btn = ActionButton(qt_widget, "Save", variant="success")
        qtbot.addWidget(btn)
        assert btn.property("variant") == "success"

    def test_color_to_variant_mapping(self, qt_widget, qtbot):
        from ui.theme import COLORS
        btn = ActionButton(qt_widget, "Delete", color=COLORS["danger"])
        qtbot.addWidget(btn)
        assert btn.property("variant") == "danger"


class TestStyledCheckBox:
    def test_text_and_toggle(self, qt_widget, qtbot):
        cb = StyledCheckBox(qt_widget, text="Enable")
        qtbot.addWidget(cb)
        assert cb.text() == "Enable"
        assert not cb.isChecked()
        qtbot.mouseClick(cb, Qt.LeftButton)
        assert cb.isChecked()


class TestStyledRadioButton:
    def test_text(self, qt_widget, qtbot):
        rb = StyledRadioButton(qt_widget, text="Option A")
        qtbot.addWidget(rb)
        assert rb.text() == "Option A"


class TestStyledComboBox:
    def test_values(self, qt_widget, qtbot):
        combo = StyledComboBox(qt_widget, values=["A", "B", "C"])
        qtbot.addWidget(combo)
        assert combo.count() == 3
        assert combo.currentText() == "A"

    def test_readonly_state(self, qt_widget, qtbot):
        combo = StyledComboBox(qt_widget, state="readonly")
        qtbot.addWidget(combo)
        assert not combo.isEditable()


class TestStyledTextEdit:
    def test_placeholder_and_text(self, qt_widget, qtbot):
        te = StyledTextEdit(qt_widget, placeholder="Notes...", text="hello")
        qtbot.addWidget(te)
        assert te.placeholderText() == "Notes..."
        assert te.toPlainText() == "hello"


class TestSectionHeader:
    def test_label_text(self, qt_widget, qtbot):
        header = SectionHeader(qt_widget, "Section Title")
        qtbot.addWidget(header)
        labels = header.findChildren(QLabel)
        assert any(lbl.text() == "Section Title" for lbl in labels)

    def test_factory_return(self, qt_widget, qtbot):
        lbl = section_header(qt_widget, "Factory Title", _return=True)
        qtbot.addWidget(lbl)
        assert isinstance(lbl, QLabel)
        assert lbl.text() == "Factory Title"


class TestKpiCard:
    def test_title_and_value(self, qt_widget, qtbot):
        card = KpiCard(qt_widget, "Revenue", "€1,234")
        qtbot.addWidget(card)
        assert card.property("role") == "kpi-card"
        assert card.title_label.text() == "Revenue"
        assert card.value_label.text() == "€1,234"

    def test_set_value(self, qt_widget, qtbot):
        card = KpiCard(qt_widget, "Revenue", "€1,234")
        qtbot.addWidget(card)
        card.set_value("€5,678")
        assert card.value_label.text() == "€5,678"

    def test_factory(self, qt_widget, qtbot):
        card = kpi_card(qt_widget, "Profit", "€900")
        qtbot.addWidget(card)
        assert isinstance(card, KpiCard)


class TestScrollableFormContainer:
    def test_content_widget_exists(self, qt_widget, qtbot):
        container = ScrollableFormContainer(qt_widget, max_width=600)
        qtbot.addWidget(container)
        assert container.widget() is not None
        assert container.widget().maximumWidth() == 600

    def test_add_widget(self, qt_widget, qtbot):
        container = ScrollableFormContainer(qt_widget)
        qtbot.addWidget(container)
        lbl = QLabel("Field")
        container.add_widget(lbl)
        assert lbl.parentWidget() is container.content


class TestTwoColRow:
    def test_columns_created(self, qt_widget, qtbot):
        row = TwoColRow(qt_widget)
        qtbot.addWidget(row)
        assert row.left is not None
        assert row.right is not None

    def test_layout_helpers(self, qt_widget, qtbot):
        row = TwoColRow(qt_widget)
        qtbot.addWidget(row)
        left_layout = row.left_layout()
        right_layout = row.right_layout()
        assert left_layout is not None
        assert right_layout is not None


class TestQtDatePicker:
    def test_initial_empty_state(self, qt_widget, qtbot):
        picker = QtDatePicker(qt_widget)
        qtbot.addWidget(picker)
        assert picker.text() == ""
        assert picker.date() is None

    def test_set_date_qdate(self, qt_widget, qtbot):
        from PySide6.QtCore import QDate
        picker = QtDatePicker(qt_widget, date_pattern="yyyy-MM-dd")
        qtbot.addWidget(picker)
        picker.set_date(QDate(2026, 6, 13))
        assert picker.text() == "2026-06-13"
        assert picker.date_py() == __import__("datetime").date(2026, 6, 13)

    def test_set_date_string(self, qt_widget, qtbot):
        picker = QtDatePicker(qt_widget, date_pattern="yyyy-MM-dd")
        qtbot.addWidget(picker)
        picker.set_date("2025-12-25")
        assert picker.text() == "2025-12-25"

    def test_clear(self, qt_widget, qtbot):
        from PySide6.QtCore import QDate
        picker = QtDatePicker(qt_widget, initial_date=QDate(2026, 1, 1))
        qtbot.addWidget(picker)
        picker.clear()
        assert picker.text() == ""
        assert picker.date() is None

    def test_factory(self, qt_widget, qtbot):
        picker = make_date_entry(qt_widget, date_pattern="dd/MM/yyyy")
        qtbot.addWidget(picker)
        assert isinstance(picker, QtDatePicker)
