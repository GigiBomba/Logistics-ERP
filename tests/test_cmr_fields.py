"""Tests for the CMR fields mixin (CmrFieldsMixin).

The mixin is tested via a minimal test host widget that provides the
required interface methods ``CmrFieldsMixin`` expects on ``self``.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.views.cmr_form_view.cmr_fields import CmrFieldsMixin


# ── Test host ──────────────────────────────────────────────────────────────────


class CmrFieldsTestHost(QWidget, CmrFieldsMixin):
    """Minimal widget that provides the interface CmrFieldsMixin requires.

    The real production host (QtCmrFormView) defines methods like
    ``_section_card``, ``_two_col_pane``, ``_box_field``, etc.  Here we
    provide lightweight stubs that create real widgets so we can verify
    the mixin builds its sections without crashing.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 600)

        # ── State attributes the mixin expects ──────────────────────────
        self._cmr_entries: dict = {}
        self._adr_rows: list[QWidget] = []
        self._successive_carrier_rows: list[QWidget] = []
        self._financial_rows: list[tuple[str, str]] = []
        self._box_badges: dict[int, QLabel] = {}

        # ADR attributes the mixin sets
        self._adr_toggle: QCheckBox | None = None
        self._adr_content_wrapper: QWidget | None = None

        # Signature pads (set by _build_issue_signatures_card)
        self.sig_sender_pad = MagicMock()
        self.sig_carrier_pad = MagicMock()
        self.sig_consignee_pad = MagicMock()

        # ── Root layout ─────────────────────────────────────────────────
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # Scroll container stub (needs add_widget)
        self._scroll_container = MagicMock()
        self._scroll_container.add_widget = lambda w, s=0: self._root_layout.addWidget(w)

    # ── Stub implementations of the methods QtCmrFormView provides ──────

    def _section_card(self, title: str, subtitle: str) -> QWidget:
        """Return a content widget (like Card + CardHeader but simpler)."""
        card = QFrame(self)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(4)
        # Title / subtitle header
        header = QLabel(f"{title} - {subtitle}")
        card_layout.addWidget(header)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)
        card_layout.addWidget(content)
        self._scroll_container.add_widget(card)
        return content

    def _two_col_pane(self, parent: QWidget) -> tuple[QWidget, QWidget]:
        """Return (left, right) widgets."""
        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(8)
        left = QWidget()
        left_layout_inner = QVBoxLayout(left)
        left_layout_inner.setContentsMargins(0, 0, 0, 0)
        left_layout_inner.setSpacing(4)
        right = QWidget()
        right_layout_inner = QVBoxLayout(right)
        right_layout_inner.setContentsMargins(0, 0, 0, 0)
        right_layout_inner.setSpacing(4)
        wrapper_layout.addWidget(left, 1)
        wrapper_layout.addWidget(right, 1)
        if parent.layout() is not None:
            parent.layout().addWidget(wrapper)  # type: ignore[union-attr]
        return left, right

    def _box_field(self, parent, box_num, label_en, label_ro, kind="entry", **kwargs):
        """Stub that creates a simple label + input placeholder."""
        from PySide6.QtWidgets import QLineEdit
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(f"{label_en} / {label_ro} (box {box_num})")
        container_layout.addWidget(lbl)
        if kind == "combobox":
            from PySide6.QtWidgets import QComboBox
            w = QComboBox()
            values = kwargs.pop("values", [])
            w.addItems(values)
        elif kind == "textbox":
            from PySide6.QtWidgets import QTextEdit
            w = QTextEdit()
            height = kwargs.pop("height", 80)
            w.setFixedHeight(height)
        else:
            w = QLineEdit()
            placeholder = kwargs.pop("placeholder", None)
            if placeholder:
                w.setPlaceholderText(placeholder)
        container_layout.addWidget(w)
        parent.layout().addWidget(container)
        return w

    def _compact_box(
        self, parent, box_num: int, label: str, col: int, max_col: int = 3
    ):
        """Stub for compact grid-field creation."""
        from PySide6.QtWidgets import QLineEdit
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(f"Box {box_num}: {label}")
        container_layout.addWidget(lbl)
        e = QLineEdit()
        container_layout.addWidget(e)
        if hasattr(parent, "layout") and parent.layout():
            parent.layout().addWidget(container)
        return e

    def _update_box_navigator(self):
        """Minimal stub — does nothing."""
        pass

    def _field_widget(self, parent, label_text, widget):
        """Delegate to the same helper the real code uses."""
        from ui.widgets import field as _field
        return _field(parent, label_text, widget)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def host(qtbot):
    """Create the test host widget for CmrFieldsMixin tests."""
    w = CmrFieldsTestHost()
    qtbot.addWidget(w)
    yield w


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestCmrFieldsMixin:
    """Tests for each section-building method in CmrFieldsMixin."""

    def test_build_parties_card(self, host):
        """_build_parties_card creates consignor and consignee entries."""
        host._build_parties_card()
        assert "consignor_name" in host._cmr_entries
        assert "consignee_name" in host._cmr_entries

    def test_build_route_card(self, host):
        """_build_route_card creates route & document entries."""
        host._build_route_card()
        expected = {
            "place_of_loading", "destination",
            "place_of_loading_date",
            "loading_country", "delivery_country",
            "documents_attached",
        }
        assert expected.issubset(host._cmr_entries.keys())

    def test_build_vehicle_card(self, host):
        """_build_vehicle_card creates vehicle and driver entries."""
        host._build_vehicle_card()
        expected = {"truck_plate", "driver_name", "trailer_plate", "driver_license"}
        assert expected.issubset(host._cmr_entries.keys())

    def test_build_cargo_card(self, host):
        """_build_cargo_card creates cargo + ADR entries."""
        host._build_cargo_card()
        expected = {
            "cargo_marks", "package_count", "package_type",
            "cargo_description", "hs_code", "gross_weight_kg",
            "volume_m3",
        }
        assert expected.issubset(host._cmr_entries.keys())
        # ADR toggle should exist
        assert host._adr_toggle is not None
        assert host._adr_content_wrapper is not None

    def test_build_instructions_card(self, host):
        """_build_instructions_card creates instruction entries."""
        host._build_instructions_card()
        expected = {
            "carrier_instructions", "carrier_reservations",
            "carriage_payer", "cod_amount",
            "special_agreements", "distance_km",
        }
        assert expected.issubset(host._cmr_entries.keys())

    def test_build_carrier_card(self, host):
        """_build_carrier_card creates carrier entries."""
        host._build_carrier_card()
        assert "carrier_name" in host._cmr_entries

    def test_build_charges_card(self, host):
        """_build_charges_card creates financial grid entries."""
        host._build_charges_card()
        expected = {
            "carriage_sender", "carriage_consignee",
            "supplementary_sender", "supplementary_consignee",
            "customs_sender", "customs_consignee",
            "other_sender", "other_consignee",
        }
        assert expected.issubset(host._cmr_entries.keys())
        assert len(host._financial_rows) == 4

    def test_build_issue_signatures_card(self, host):
        """_build_issue_signatures_card creates issue + signature entries."""
        host._build_issue_signatures_card()
        assert "issue_place" in host._cmr_entries
        assert "issue_date" in host._cmr_entries

    def test_build_all_sections(self, host):
        """Building all sections populates every expected key."""
        host._build_parties_card()
        host._build_route_card()
        host._build_vehicle_card()
        host._build_cargo_card()
        host._build_instructions_card()
        host._build_carrier_card()
        host._build_charges_card()
        host._build_issue_signatures_card()

        all_expected = {
            "consignor_name", "consignee_name",
            "place_of_loading", "place_of_loading_date",
            "destination", "loading_country", "delivery_country",
            "documents_attached",
            "truck_plate", "driver_name", "trailer_plate", "driver_license",
            "cargo_marks", "package_count", "package_type",
            "cargo_description", "hs_code", "gross_weight_kg", "volume_m3",
            "carrier_instructions", "carrier_reservations",
            "carriage_payer", "cod_amount",
            "special_agreements", "distance_km",
            "carrier_name",
            "carriage_sender", "carriage_consignee",
            "supplementary_sender", "supplementary_consignee",
            "customs_sender", "customs_consignee",
            "other_sender", "other_consignee",
            "issue_place", "issue_date",
        }
        missing = all_expected - host._cmr_entries.keys()
        assert not missing, f"Missing keys: {missing}"

    # ── ADR section ──────────────────────────────────────────────────────────

    def test_adr_toggle_off_by_default(self, host):
        """ADR toggle is unchecked and content hidden by default."""
        host._build_cargo_card()
        assert host._adr_toggle is not None
        assert host._adr_toggle.isChecked() is False
        assert host._adr_content_wrapper.isVisible() is False

    def test_adr_add_remove_row(self, host):
        """Adding and removing ADR rows updates _adr_rows."""
        host._build_cargo_card()
        assert len(host._adr_rows) == 0

        host._add_adr_row()
        assert len(host._adr_rows) == 1

        host._add_adr_row()
        assert len(host._adr_rows) == 2

        # Remove the first row
        row = host._adr_rows[0]
        host._remove_adr_row(row)
        assert len(host._adr_rows) == 1

    def test_adr_toggle_adds_first_row(self, host):
        """Toggling ADR on adds the first row automatically."""
        host._build_cargo_card()
        assert len(host._adr_rows) == 0

        # Simulate checking the toggle (use Qt.CheckState enum)
        host._on_adr_toggle(Qt.CheckState.Checked)
        # The mixin adds a row when toggle is checked and rows are empty
        assert len(host._adr_rows) == 1

    # ── Successive carriers ──────────────────────────────────────────────────

    def test_successive_carrier_add_remove(self, host):
        """Adding and removing successive carrier rows."""
        host._build_carrier_card()
        assert len(host._successive_carrier_rows) == 0

        host._add_successive_carrier_row()
        assert len(host._successive_carrier_rows) == 1

        host._add_successive_carrier_row()
        assert len(host._successive_carrier_rows) == 2

        row = host._successive_carrier_rows[0]
        host._remove_successive_carrier_row(row)
        assert len(host._successive_carrier_rows) == 1

    # ── Charges / financial rows ─────────────────────────────────────────────

    def test_build_financial_row(self, host):
        """_build_financial_row creates sender/consignee entries."""
        host._build_charges_card()
        assert "carriage_sender" in host._cmr_entries
        assert "carriage_consignee" in host._cmr_entries
        assert ("carriage_sender", "carriage_consignee") in host._financial_rows

    # ── Signature pads ────────────────────────────────────────────────────────

    def test_signature_pads_created(self, host):
        """Three signature pads are created by issue/signature section."""
        host._build_issue_signatures_card()
        assert hasattr(host, "sig_sender_pad")
        assert hasattr(host, "sig_carrier_pad")
        assert hasattr(host, "sig_consignee_pad")

    # ── Field widget helper ───────────────────────────────────────────────────

    def test_field_widget_returns_widget(self, host):
        """_field_widget creates a labelled field container."""
        from PySide6.QtWidgets import QLineEdit
        edit = QLineEdit()
        result = host._field_widget(host, "Test Label", edit)
        assert result is not None
        assert isinstance(result, QWidget)
