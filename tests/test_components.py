"""Tests for the UI component factory helpers."""
from __future__ import annotations
import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QFrame

class TestLabel:
    def test_creates_label_with_role(self, qt_widget, qtbot):
        from ui.components import Label
        lbl = Label(qt_widget, "Hello", role="muted")
        qtbot.addWidget(lbl)
        assert lbl.text() == "Hello"
        assert lbl.property("role") == "muted"

class TestPageTitle:
    def test_page_title(self, qt_widget, qtbot):
        from ui.components import PageTitle
        lbl = PageTitle(qt_widget, "Dashboard")
        qtbot.addWidget(lbl)
        assert lbl.text() == "Dashboard"

class TestSectionTitle:
    def test_section_title(self, qt_widget, qtbot):
        from ui.components import SectionTitle
        lbl = SectionTitle(qt_widget, "Revenue")
        qtbot.addWidget(lbl)
        assert lbl.text() == "REVENUE"

class TestFieldLabel:
    def test_field_label(self, qt_widget, qtbot):
        from ui.components import FieldLabel
        lbl = FieldLabel(qt_widget, "Email")
        qtbot.addWidget(lbl)
        assert lbl.text() == "EMAIL"

class TestMonoLabel:
    def test_mono_label(self, qt_widget, qtbot):
        from ui.components import MonoLabel
        lbl = MonoLabel(qt_widget, "12345")
        qtbot.addWidget(lbl)
        assert lbl.text() == "12345"

    def test_mono_label_lg_size(self, qt_widget, qtbot):
        from ui.components import MonoLabel
        lbl = MonoLabel(qt_widget, "100", size="lg")
        qtbot.addWidget(lbl)

class TestBtn:
    def test_button_text_and_variant(self, qt_widget, qtbot):
        from ui.components import Btn
        btn = Btn(qt_widget, "Submit", variant="primary")
        qtbot.addWidget(btn)
        assert btn.text() == "Submit"
        assert btn.property("variant") == "primary"

    def test_button_sm_size(self, qt_widget, qtbot):
        from ui.components import Btn
        btn = Btn(qt_widget, "Small", size="sm")
        qtbot.addWidget(btn)
        assert btn.property("size") == "sm"

    def test_button_command(self, qt_widget, qtbot):
        from ui.components import Btn
        from PySide6.QtCore import Qt
        clicks = []
        btn = Btn(qt_widget, "Click", command=lambda: clicks.append(1))
        qtbot.addWidget(btn)
        qtbot.mouseClick(btn, Qt.LeftButton)
        assert clicks == [1]

    def test_button_danger_variant(self, qt_widget, qtbot):
        from ui.components import Btn
        btn = Btn(qt_widget, "Delete", variant="danger")
        qtbot.addWidget(btn)
        assert btn.property("variant") == "danger"

class TestCard:
    def test_card_creation(self, qt_widget, qtbot):
        from ui.components import Card
        card = Card(qt_widget)
        qtbot.addWidget(card)
        assert card.objectName() == "card"
        assert card.layout() is not None

    def test_card_no_padding(self, qt_widget, qtbot):
        from ui.components import Card
        card = Card(qt_widget, padding=False)
        qtbot.addWidget(card)

class TestCardHeader:
    def test_card_header(self, qt_widget, qtbot):
        from ui.components import CardHeader
        from PySide6.QtWidgets import QVBoxLayout
        container = QFrame(qt_widget)
        layout = QVBoxLayout(container)
        header = CardHeader(layout, title="Test", subtitle="Sub")
        qtbot.addWidget(container)

class TestDivider:
    def test_horizontal_divider(self, qt_widget, qtbot):
        from ui.components import Divider
        d = Divider(qt_widget)
        qtbot.addWidget(d)
        assert d.frameShape() == QFrame.Shape.HLine

    def test_vertical_divider(self, qt_widget, qtbot):
        from ui.components import Divider
        d = Divider(qt_widget, vertical=True)
        qtbot.addWidget(d)
        assert d.frameShape() == QFrame.Shape.VLine

class TestSectionDivider:
    def test_section_divider(self, qt_widget, qtbot):
        from ui.components import SectionDivider
        d = SectionDivider(qt_widget, "Summary")
        qtbot.addWidget(d)

class TestKPICard:
    def test_kpi_card(self, qt_widget, qtbot):
        from ui.components import KPICard
        card = KPICard(qt_widget, "Revenue", "€1,234", subtitle="+12%")
        qtbot.addWidget(card)
        assert hasattr(card, "value_label")
        assert hasattr(card, "title_label")

    def test_kpi_card_no_subtitle(self, qt_widget, qtbot):
        from ui.components import KPICard
        card = KPICard(qt_widget, "Trips", "42")
        qtbot.addWidget(card)

class TestCompactKPICard:
    def test_compact_kpi_creation(self, qt_widget, qtbot):
        from ui.components import CompactKPICard
        card = CompactKPICard(qt_widget, label="Revenue", value="€5,000", trend="+15%", trend_positive=True)
        qtbot.addWidget(card)
        assert hasattr(card, "value_label")
        assert hasattr(card, "title_label")

class TestStatusBadge:
    def test_status_badge_delivered(self, qt_widget, qtbot):
        from ui.components import StatusBadge
        badge = StatusBadge(qt_widget, status_key="delivered")
        qtbot.addWidget(badge)

    def test_status_badge_planned(self, qt_widget, qtbot):
        from ui.components import StatusBadge
        badge = StatusBadge(qt_widget, status_key="planned")
        qtbot.addWidget(badge)

    def test_status_badge_cancelled(self, qt_widget, qtbot):
        from ui.components import StatusBadge
        badge = StatusBadge(qt_widget, status_key="cancelled")
        qtbot.addWidget(badge)

    def test_status_badge_unknown_key(self, qt_widget, qtbot):
        from ui.components import StatusBadge
        badge = StatusBadge(qt_widget, status_key="nonexistent", text="Custom")
        qtbot.addWidget(badge)

class TestEmptyState:
    def test_empty_state_creation(self, qt_widget, qtbot):
        from ui.components import EmptyState
        state = EmptyState(qt_widget, title="Nothing here", subtitle="Add some data")
        qtbot.addWidget(state)

    def test_empty_state_with_cta(self, qt_widget, qtbot):
        from ui.components import Btn, EmptyState
        cta = Btn(qt_widget, "Add Item")
        state = EmptyState(qt_widget, title="Empty", cta_button=cta)
        qtbot.addWidget(state)

class TestGetIcon:
    def test_get_icon_returns_icon(self):
        from ui.components import get_icon
        from PySide6.QtGui import QIcon
        icon = get_icon("fa5s.home")
        assert isinstance(icon, QIcon)

    def test_get_icon_with_color(self):
        from ui.components import get_icon
        icon = get_icon("fa5s.home", color="#6366F1")
        assert icon is not None
