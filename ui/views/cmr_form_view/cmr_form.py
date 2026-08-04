"""PySide6 CMR consignment note form view — UN/CEFACT-aligned, 24-box editor.

Split from ``cmr_form_view.py``.  The form section builders live in
``cmr_fields.py``.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any

import qtawesome as qta
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import Btn, Card, CardHeader, Divider, EmptyState, Label, PageTitle
from ui.design_tokens import (
    ACCENT_TEXT,
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_HOVER,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_SUCCESS_SUBTLE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    COLOR_WARNING_SUBTLE,
    FONT_SIZE_SM,
    FONT_WEIGHT_SEMIBOLD,
    SP,
    SPACE_1,
)
from ui.form_utils import add_required_indicator
from ui.widgets import (
    ScrollableFormContainer,
    StyledComboBox,
    StyledLineEdit,
    StyledTextEdit,
    field,
)
from ui.widgets.signature_pad import QtSignaturePad

from ui.views.cmr_form_view.cmr_fields import CmrFieldsMixin

logger = logging.getLogger(__name__)

PAYMENT_OPTIONS = ["", "Sender", "Consignee"]


class QtCmrFormView(CmrFieldsMixin, QWidget):
    """CMR consignment note form — UN/CEFACT 24-box editor.

    Wraps a ``ScrollableFormContainer`` with heading, role selector, section
    cards for each CMR box group, and a bottom action bar.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs=None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs

        # ── State ──────────────────────────────────────────────────────────────
        self._adr_rows: list[QWidget] = []
        self._successive_carrier_rows: list[QWidget] = []
        self._financial_rows: list[tuple[str, str]] = []
        self._cmr_entries: dict[str, Any] = {}
        self._cmr_error_labels: list[tuple[QWidget, QLabel, bool]] = []

        self._consignor_role_active: bool = True
        self._last_trip_data: dict | None = None

        # ── Build ──────────────────────────────────────────────────────────────
        self._build_ui()

    # ══════════════════════════════════════════════════════════════════════════
    # UI Construction
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Stacked widget: page 0 = empty state, page 1 = form
        self._cmr_stack = QStackedWidget()
        layout.addWidget(self._cmr_stack, 1)

        # Page 0: Empty state (shown when no trip is selected)
        self._cmr_empty_page = QWidget()
        empty_layout = QVBoxLayout(self._cmr_empty_page)
        empty_layout.setAlignment(Qt.AlignCenter)
        self._cmr_empty_state = EmptyState(
            parent=self._cmr_empty_page,
            icon_name="fa5s.file-alt",
            title=t("cmr.empty_title", "Select a trip"),
            subtitle=t("cmr.empty_desc", "Choose a trip to generate CMR documents."),
        )
        empty_layout.addWidget(self._cmr_empty_state)
        self._cmr_stack.addWidget(self._cmr_empty_page)

        # Page 1: Form
        self._cmr_form_page = QWidget()
        form_layout = QVBoxLayout(self._cmr_form_page)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(0)

        # Scrollable form container holds everything
        self._scroll_container = ScrollableFormContainer(self._cmr_form_page, max_width=1200)
        self._scroll_container.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        form_layout.addWidget(self._scroll_container, 1)

        # Shortcut to the content widget inside the scroll container
        self._content = self._scroll_container.content

        self._build_page_heading()
        self._build_role_selector()

        # ── 5 collapsible sections ──────────────────────────────────────
        # Sections 1-3 expanded by default, 4-5 collapsed
        self._build_section_parties()        # Boxes 1–2, 18–19
        self._build_section_goods()          # Boxes 6–12
        self._build_section_route()          # Boxes 3–5 + vehicle/driver
        self._build_section_instructions()   # Boxes 13–17 + Box 20
        self._build_section_signatures()     # Boxes 21–24

        # Bottom action bar (inside the scroll so it scrolls with the form)
        self._build_action_bar()

        # Initialize navigator state after all fields are built
        self._update_box_navigator()
        self._connect_box_signals()

        self._cmr_stack.addWidget(self._cmr_form_page)
        self._cmr_stack.setCurrentIndex(0)  # Start at empty state

    # ── Box navigator state ─────────────────────────────────────────────────

    _BOX_FIELDS: dict[int, list[str]] = {
        1:  ["consignor_name"],
        2:  ["consignee_name"],
        3:  ["place_of_loading", "loading_country"],
        4:  ["destination", "delivery_country"],
        5:  ["documents_attached"],
        6:  ["cargo_marks"],
        7:  ["package_count"],
        8:  ["package_type"],
        9:  ["cargo_description"],
        10: ["hs_code"],
        11: ["gross_weight_kg"],
        12: ["volume_m3"],
        13: ["carrier_instructions"],
        14: ["carrier_reservations"],
        15: ["carriage_payer"],
        16: ["cod_amount"],
        17: ["special_agreements", "distance_km"],
        18: ["carrier_name"],
        19: [],
        20: [],
        21: ["issue_place"],
        22: [],
        23: [],
        24: [],
    }

    def _update_box_navigator(self):
        for box_num, field_keys in self._BOX_FIELDS.items():
            badge = self._box_badges.get(box_num)
            if badge is None:
                continue
            has_content = any(
                self._field_has_content(k) for k in field_keys
            )
            if has_content:
                badge.setStyleSheet(
                    f"background-color: {COLOR_SUCCESS_SUBTLE};"
                    f"color: {COLOR_SUCCESS_DEFAULT};"
                    f"border-radius: 4px; font-size: 7px; font-weight: bold;"
                )
            elif field_keys:
                badge.setStyleSheet(
                    f"background-color: {COLOR_WARNING_SUBTLE};"
                    f"color: {COLOR_WARNING_DEFAULT};"
                    f"border-radius: 4px; font-size: 7px; font-weight: bold;"
                )
            else:
                badge.setStyleSheet(
                    f"background-color: {COLOR_ACCENT_SUBTLE};"
                    f"color: {ACCENT_TEXT};"
                    f"border-radius: 4px; font-size: 7px; font-weight: bold;"
                )

    def _field_has_content(self, key: str) -> bool:
        widget = self._cmr_entries.get(key)
        if widget is None:
            return False
        if hasattr(widget, "toPlainText"):
            return bool(widget.toPlainText().strip())
        if hasattr(widget, "text"):
            return bool(widget.text().strip())
        if hasattr(widget, "date"):
            return True
        return False

    def _connect_box_signals(self):
        for field_keys in self._BOX_FIELDS.values():
            for key in field_keys:
                widget = self._cmr_entries.get(key)
                if widget is None:
                    continue
                if hasattr(widget, "textChanged"):
                    widget.textChanged.connect(self._update_box_navigator)
                elif hasattr(widget, "dateChanged"):
                    widget.dateChanged.connect(self._update_box_navigator)
                elif hasattr(widget, "currentIndexChanged"):
                    widget.currentIndexChanged.connect(self._update_box_navigator)
                elif hasattr(widget, "valueChanged"):
                    widget.valueChanged.connect(self._update_box_navigator)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _build_page_heading(self):
        heading = QWidget()
        heading_layout = QVBoxLayout(heading)
        heading_layout.setContentsMargins(0, 0, 0, SP["3"])
        heading_layout.setSpacing(SP["1"])

        self._page_title = PageTitle(
            heading, t("cmr.title", "CMR International Consignment Note")
        )
        heading_layout.addWidget(self._page_title)

        self._page_subtitle = Label(
            heading,
            t("cmr.subtitle", "UN/CEFACT 24-Box Layout — Boxes 1 to 24 in order"),
            role="secondary",
        )
        heading_layout.addWidget(self._page_subtitle)

        # Mini box navigator
        nav = QWidget()
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(0, SP["1"], 0, 0)
        nav_layout.setSpacing(2)
        self._box_badges = {}
        for i in range(1, 25):
            badge = QLabel(str(i))
            badge.setFixedSize(18, 18)
            badge.setAlignment(Qt.AlignCenter)
            badge.setProperty("role", "box-badge")
            badge.setStyleSheet(
                f"background-color: {COLOR_ACCENT_SUBTLE};"
                f"color: {ACCENT_TEXT};"
                f"border-radius: 4px; font-size: 7px; font-weight: bold;"
            )
            nav_layout.addWidget(badge)
            self._box_badges[i] = badge
        nav_layout.addStretch(1)
        heading_layout.addWidget(nav)

        self._scroll_container.add_widget(heading)

    def _build_role_selector(self):
        """Role toggle using the standard toggle-button pattern:
        active = primary (filled indigo), inactive = secondary (outlined).
        Reuse this pattern for any binary either/or choice."""
        card = Card()
        card.layout().setSpacing(SP["2"])

        label = Label(card, t("cmr.select_role", "SELECT YOUR ROLE"), role="section-title")
        card.layout().addWidget(label)
        card.layout().addWidget(Divider())

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(SP["2"])

        self._role_consignor_btn = Btn(
            row,
            t("cmr.role_consignor", "I am the Consignor (Sender)"),
            command=lambda: self._set_role(True),
            variant="primary",
        )
        self._role_consignor_btn.setFixedHeight(42)
        row_layout.addWidget(self._role_consignor_btn, 1)

        self._role_consignee_btn = Btn(
            row,
            t("cmr.role_consignee", "I am the Consignee (Receiver)"),
            command=lambda: self._set_role(False),
            variant="secondary",
        )
        self._role_consignee_btn.setFixedHeight(42)
        row_layout.addWidget(self._role_consignee_btn, 1)

        card.layout().addWidget(row)
        self._scroll_container.add_widget(card)

    def _make_card(self) -> QFrame:
        """Create a section card using the design system Card()."""
        return Card()

    def _section_card(self, title: str, subtitle: str) -> QWidget:
        """Create a themed card with CardHeader and return the content widget.

        Callers pack form fields into the returned widget's layout.
        NOTE: This is an alias kept for the mixin; new code should use
        ``_make_collapsible_section`` for collapsible behavior.
        """
        card = Card()
        CardHeader(card.layout(), title=title, subtitle=subtitle)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SP["3"])
        card.layout().addWidget(content)

        self._scroll_container.add_widget(card)
        return content

    def _make_collapsible_section(
        self, title: str, subtitle: str, expanded: bool = True
    ) -> tuple[QFrame, QWidget]:
        """Create a Card with a clickable collapsible header.

        Returns ``(card_frame, content_widget)``.  The content widget's
        visibility is toggled when the header is clicked.
        """
        card = Card()

        # ── Clickable header button ───────────────────────────────────
        icon_char = "\u25BC" if expanded else "\u25B6"
        header_btn = QPushButton(f"{icon_char}  {title}")
        header_btn.setFlat(True)
        header_btn.setCursor(Qt.PointingHandCursor)
        header_btn.setFixedHeight(32)
        header_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                font-size: {FONT_SIZE_SM}px;
                font-weight: {FONT_WEIGHT_SEMIBOLD};
                color: {COLOR_TEXT_PRIMARY};
                padding: 0;
                border: none;
                background: transparent;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                color: {COLOR_ACCENT_PRIMARY};
            }}
        """)

        # Subtitle label
        sub_lbl = QLabel(subtitle)
        sub_lbl.setProperty("role", "muted")
        sub_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 10px;")

        # ── Divider ───────────────────────────────────────────────────
        div = Divider()

        # ── Collapsible content container ─────────────────────────────
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SP["3"])
        content_widget.setVisible(expanded)

        # Assemble card
        card.layout().addWidget(header_btn)
        if subtitle:
            card.layout().addWidget(sub_lbl)
        card.layout().addWidget(div)
        card.layout().addWidget(content_widget)

        self._scroll_container.add_widget(card)

        # ── Toggle logic ──────────────────────────────────────────────
        def _toggle():
            new_expanded = not content_widget.isVisible()
            content_widget.setVisible(new_expanded)
            new_icon = "\u25BC" if new_expanded else "\u25B6"
            header_btn.setText(f"{new_icon}  {title}")

        header_btn.clicked.connect(_toggle)

        return card, content_widget

    # ── 5 consolidated section builders ─────────────────────────────

    def _build_section_parties(self):
        """Section 1: Parties — Consignor, Consignee, Carrier (Boxes 1-2, 18-19)."""
        _card, content = self._make_collapsible_section(
            t("cmr.section_parties", "Parties"),
            t("cmr.section_parties_sub",
              "Boxes 1, 2, 18, 19 — Sender, Receiver & Carrier"),
            expanded=True,
        )
        # Sub-section: Sender & Consignee
        self._build_parties_card(content=content)
        # Sub-section: Carrier info
        self._build_carrier_card(content=content)

    def _build_section_goods(self):
        """Section 2: Goods — Cargo details (Boxes 6-12)."""
        _card, content = self._make_collapsible_section(
            t("cmr.section_cargo", "Goods Specifications"),
            t("cmr.section_cargo_sub",
              "Boxes 6 to 12 — Cargo marks, packages, weight, volume, HS code"),
            expanded=True,
        )
        self._build_cargo_card(content=content)

    def _build_section_route(self):
        """Section 3: Route — Route details & transport means (Boxes 3-5 + vehicle)."""
        _card, content = self._make_collapsible_section(
            t("cmr.section_route_title", "Route & Transport"),
            t("cmr.section_route_sub",
              "Boxes 3, 4, 5 — Place of loading, delivery, vehicle & driver"),
            expanded=True,
        )
        self._build_route_card(content=content)
        self._build_vehicle_card(content=content)

    def _build_section_instructions(self):
        """Section 4: Instructions — Special instructions, charges (Boxes 13-17, 20)."""
        _card, content = self._make_collapsible_section(
            t("cmr.section_instructions_title", "Instructions & Charges"),
            t("cmr.section_instructions_sub",
              "Boxes 13 to 17, 20 — Instructions, payment, COD, charges"),
            expanded=False,
        )
        self._build_instructions_card(content=content)
        self._build_charges_card(content=content)

    def _build_section_signatures(self):
        """Section 5: Signatures — Issue place, date & signatures (Boxes 21-24)."""
        _card, content = self._make_collapsible_section(
            t("cmr.section_signatures_title", "Issue & Signatures"),
            t("cmr.section_signatures_sub",
              "Boxes 21 to 24 — Place, date of issue and party signatures"),
            expanded=False,
        )
        self._build_issue_signatures_card(content=content)

    def _two_col_pane(self, parent: QWidget) -> tuple[QWidget, QWidget]:
        """Return (left, right) widgets with a vertical divider between them."""
        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(SP["3"])

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(SP["3"])
        wrapper_layout.addWidget(left, 1)

        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setFrameShadow(QFrame.Plain)
        vline.setFixedWidth(1)
        vline.setStyleSheet(f"background-color: {COLOR_BORDER_SUBTLE};")
        wrapper_layout.addWidget(vline)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SP["3"])
        wrapper_layout.addWidget(right, 1)

        parent_layout = parent.layout()
        if parent_layout is None:
            parent.setLayout(QVBoxLayout())
            parent_layout = parent.layout()
            parent_layout.setContentsMargins(0, 0, 0, 0)
            parent_layout.setSpacing(0)
        parent_layout.addWidget(wrapper)
        return left, right

    def _box_field(
        self,
        parent: QWidget,
        box_num: int | None,
        label_en: str,
        label_ro: str,
        kind: str = "entry",
        required: bool = False,
        **kwargs,
    ) -> QWidget:
        """Themed field with accent badge + bilingual label.

        Parameters
        ----------
        parent : QWidget
            Container to add the field into.
        box_num : int or None
            CMR box number (None for supplementary fields).
        label_en, label_ro : str
            Bilingual field labels.
        kind : str
            ``"entry"`` (single-line), ``"textbox"`` (multi-line),
            ``"combobox"`` (dropdown).
        required : bool
            If True, a red asterisk is added to the label.
        **kwargs
            Forwarded to the underlying widget constructor.
        """
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(SP["1"])

        # Label row with optional badge
        lbl_row = QWidget()
        lbl_layout = QHBoxLayout(lbl_row)
        lbl_layout.setContentsMargins(0, 0, 0, 0)
        lbl_layout.setSpacing(SP["2"])

        if box_num is not None:
            badge = QLabel(str(box_num))
            badge.setFixedSize(30, 20)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                f"background-color: {COLOR_ACCENT_SUBTLE};"
                f"color: {ACCENT_TEXT};"
                f"border-radius: 4px; font-weight: bold; font-size: 10px;"
            )
            lbl_layout.addWidget(badge)

        label = QLabel(f"{label_en} / {label_ro}")
        label.setProperty("fontRole", "label")
        label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        lbl_layout.addWidget(label)
        lbl_layout.addStretch(1)

        container_layout.addWidget(lbl_row)

        # Required indicator
        if required:
            add_required_indicator(label)

        # Input widget
        placeholder = kwargs.pop("placeholder", None)
        if kind == "entry":
            w = StyledLineEdit(container, placeholder=placeholder, **kwargs)
        elif kind == "textbox":
            height = kwargs.pop("height", 90)
            w = StyledTextEdit(container, placeholder=placeholder, height=height, **kwargs)
        elif kind == "combobox":
            values = kwargs.pop("values", [])
            w = StyledComboBox(container, values=values, **kwargs)
        else:
            w = StyledLineEdit(container, placeholder=placeholder, **kwargs)

        container_layout.addWidget(w)

        # Error label (hidden by default) — only for required fields
        if required:
            err_lbl = QLabel()
            err_lbl.setProperty("role", "field-error")
            err_lbl.setVisible(False)
            err_lbl.setWordWrap(True)
            container_layout.addWidget(err_lbl)
            self._cmr_error_labels.append((w, err_lbl, required))

        # Add to parent layout
        parent_layout = parent.layout()
        if parent_layout is None:
            parent_layout = QVBoxLayout(parent)
            parent_layout.setContentsMargins(0, 0, 0, 0)
            parent_layout.setSpacing(SP["3"])
            parent.setLayout(parent_layout)
        parent_layout.addWidget(container)

        return w

    def _compact_box(
        self, parent: QWidget, box_num: int, label: str, col: int, max_col: int = 3
    ) -> StyledLineEdit:
        """Compact grid cell for the goods table (single-line entry)."""
        # We use a simple vertical layout approach since we can't easily
        # grid inside a horizontal layout. Instead, the caller should use
        # a QGridLayout or QHBoxLayout-based approach.
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(SP["1"])

        lbl_row = QWidget()
        lbl_layout = QHBoxLayout(lbl_row)
        lbl_layout.setContentsMargins(0, 0, 0, 0)
        lbl_layout.setSpacing(SP["1"])

        badge = QLabel(str(box_num))
        badge.setFixedSize(26, 18)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background-color: {COLOR_ACCENT_SUBTLE};"
            f"color: {ACCENT_TEXT};"
            f"border-radius: 3px; font-weight: bold; font-size: 8px;"
        )
        lbl_layout.addWidget(badge)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;")
        lbl_layout.addWidget(lbl)
        lbl_layout.addStretch(1)

        container_layout.addWidget(lbl_row)

        e = StyledLineEdit(container, height=32)
        container_layout.addWidget(e)

        # Add to parent layout — assumes parent uses QHBoxLayout or QGridLayout
        parent_layout = parent.layout()
        if parent_layout and isinstance(parent_layout, QHBoxLayout):
            parent_layout.addWidget(container, 1)
        elif parent_layout and hasattr(parent_layout, "addWidget"):
            parent_layout.addWidget(container, col, 0)

        return e

    # ── Bottom action bar ────────────────────────────────────────────────

    def _build_action_bar(self):
        """Action buttons for Preview, Generate, Print, Save + progress bar."""
        bar = QWidget()
        bar_layout = QVBoxLayout(bar)
        bar_layout.setContentsMargins(0, SP["4"], 0, 0)
        bar_layout.setSpacing(SP["2"])

        # ── Progress bar (hidden by default) ──────────────────────────
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {COLOR_BORDER_SUBTLE};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {COLOR_ACCENT_PRIMARY};
                border-radius: 2px;
            }}
        """)
        bar_layout.addWidget(self._progress_bar)

        # ── Button row ────────────────────────────────────────────────
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(SP["3"])

        self._btn_preview = Btn(
            btn_row,
            t("cmr.preview", "Preview"),
            variant="secondary",
            icon_name="fa5s.eye",
        )
        self._btn_preview.setFixedHeight(38)
        btn_layout.addWidget(self._btn_preview)

        self._btn_generate = Btn(
            btn_row,
            t("cmr.generate", "Generate CMR"),
            variant="primary",
            command=self._on_generate_clicked,
        )
        self._btn_generate.setFixedHeight(38)
        btn_layout.addWidget(self._btn_generate)

        self._btn_print = Btn(
            btn_row,
            t("cmr.print", "Print"),
            variant="secondary",
        )
        self._btn_print.setFixedHeight(38)
        btn_layout.addWidget(self._btn_print)

        btn_layout.addStretch(1)

        self._btn_save = Btn(
            btn_row,
            t("cmr.save", "Save"),
            variant="secondary",
        )
        self._btn_save.setFixedHeight(38)
        btn_layout.addWidget(self._btn_save)

        bar_layout.addWidget(btn_row)

        self._bottom_bar = bar
        self._scroll_container.add_widget(bar)

    # ── Role selection ────────────────────────────────────────────────────

    def _set_role(self, is_consignor: bool):
        if self._consignor_role_active == is_consignor:
            return
        self._consignor_role_active = is_consignor
        self._update_role_buttons()
        if self._last_trip_data:
            self.fill_from_trip(**self._last_trip_data)

    def _update_role_buttons(self):
        if self._consignor_role_active:
            self._role_consignor_btn.setProperty("variant", "primary")
            self._role_consignee_btn.setProperty("variant", "secondary")
        else:
            self._role_consignor_btn.setProperty("variant", "secondary")
            self._role_consignee_btn.setProperty("variant", "primary")
        # Force style refresh
        self._role_consignor_btn.style().unpolish(self._role_consignor_btn)
        self._role_consignor_btn.style().polish(self._role_consignor_btn)
        self._role_consignee_btn.style().unpolish(self._role_consignee_btn)
        self._role_consignee_btn.style().polish(self._role_consignee_btn)

    # ══════════════════════════════════════════════════════════════════════
    # Validation
    # ══════════════════════════════════════════════════════════════════════

    def validate_required_fields(self) -> bool:
        """Validate all required CMR fields.

        Shows inline error messages for empty required fields.
        Returns True if all required fields are filled.
        """
        has_errors = False
        for widget, err_lbl, _required in self._cmr_error_labels:
            value = ""
            if hasattr(widget, "toPlainText"):
                value = widget.toPlainText().strip()
            elif hasattr(widget, "text"):
                value = widget.text().strip()

            if not value:
                err_lbl.setText(t("common.field_required", default="This field is required"))
                err_lbl.setVisible(True)
                if hasattr(widget, "setProperty"):
                    widget.setProperty("validation", "error")
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                has_errors = True
            else:
                err_lbl.setVisible(False)
                if hasattr(widget, "setProperty"):
                    widget.setProperty("validation", "")
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)

        return not has_errors

    def _on_generate_clicked(self) -> None:
        """Validate required fields before generating the CMR."""
        if not self.validate_required_fields():
            # Scroll to first error
            for widget, err_lbl, _required in self._cmr_error_labels:
                if err_lbl.isVisible():
                    # Focus the first field with an error
                    if hasattr(widget, "setFocus"):
                        widget.setFocus()
                    break
            return
        # Validation passed — the external caller handles generation.
        # If the caller connected a callback via command, it would fire here.
        # Otherwise, emit a signal or call a stored callback.

    # ══════════════════════════════════════════════════════════════════════
    # Data collection
    # ══════════════════════════════════════════════════════════════════════

    def _get_adr_data(self) -> list[dict] | None:
        if not self._adr_toggle.isChecked():
            return None
        items = []
        for row in self._adr_rows:
            entries = list(row.findChildren(StyledLineEdit))
            if len(entries) >= 6:
                items.append({
                    "un_no": entries[0].text().strip(),
                    "adr_class": entries[1].text().strip(),
                    "packing_group": entries[2].text().strip(),
                    "tunnel_code": entries[3].text().strip(),
                    "quantity": entries[4].text().strip(),
                    "net_weight": entries[5].text().strip(),
                })
        return items if items else None

    def _get_successive_carriers(self) -> list[dict]:
        result = []
        for frame in self._successive_carrier_rows:
            entries = frame.findChildren(StyledLineEdit)
            if len(entries) >= 6:
                result.append({
                    "carrier_name": entries[0].text().strip(),
                    "carrier_address": entries[1].text().strip(),
                    "carrier_country": entries[2].text().strip(),
                    "vehicle_plate": entries[3].text().strip(),
                    "trailer_plate": entries[4].text().strip(),
                    "driver_name": entries[5].text().strip(),
                    "from_location": entries[6].text().strip()
                    if len(entries) > 6 else "",
                    "to_location": entries[7].text().strip()
                    if len(entries) > 7 else "",
                })
        return result

    def _get_financial_data(self) -> dict:
        result = {}
        for sk, ck in self._financial_rows:
            s_w = self._cmr_entries.get(sk)
            c_w = self._cmr_entries.get(ck)
            result[sk] = s_w.text().strip() if s_w else ""
            result[ck] = c_w.text().strip() if c_w else ""
        return result

    # ══════════════════════════════════════════════════════════════════════
    # Auto-fill
    # ══════════════════════════════════════════════════════════════════════

    def fill_from_trip(
        self,
        trip: dict | None = None,
        company_conf: dict | None = None,
        client_data: dict | None = None,
        truck_data: dict | None = None,
        driver_data: dict | None = None,
    ):
        """Populate form fields from trip, company, and client data."""
        self._last_trip_data = {
            "trip": trip, "company_conf": company_conf,
            "client_data": client_data, "truck_data": truck_data,
            "driver_data": driver_data,
        }
        if not trip:
            self._cmr_stack.setCurrentIndex(0)
            return

        self._cmr_stack.setCurrentIndex(1)

        conf = company_conf or {}
        client = client_data or {}
        truck = truck_data or {}
        driver = driver_data or {}

        if self._consignor_role_active:
            # Company → Box 1 (Consignor / Sender)
            sender_lines = []
            sender_lines.append(conf.get("company_name", ""))
            sender_lines.append(conf.get("address", ""))
            cui = conf.get("cui", "")
            eori = conf.get("eori_number", "")
            phone = conf.get("phone", "")
            if cui:
                sender_lines.append(f"{t('cmr.vat_cui', default='VAT/CUI:')} {cui}")
            if eori:
                sender_lines.append(f"{t('cmr.eori', default='EORI:')} {eori}")
            if phone:
                sender_lines.append(f"{t('cmr.tel', default='Tel:')} {phone}")
            self._set_entry(
                self._cmr_entries.get("consignor_name"),
                "\n".join(line for line in sender_lines if line),
            )

            # Client → Box 2 (Consignee)
            c_lines = []
            c_lines.append(trip.get("client_name", client.get("name", "")))
            c_lines.append(client.get("address", ""))
            c_vat = client.get("vat_number", "")
            c_eori = client.get("eori_number", "")
            c_contact = client.get("consignee_contact_name", "")
            c_phone = client.get("consignee_contact_phone", client.get("phone", ""))
            if c_vat:
                c_lines.append(f"{t('cmr.vat', default='VAT:')} {c_vat}")
            if c_eori:
                c_lines.append(f"{t('cmr.eori', default='EORI:')} {c_eori}")
            if c_contact or c_phone:
                c_lines.append(f"{t('cmr.contact', default='Contact:')} {c_contact}, {c_phone}".strip(", "))
            self._set_entry(
                self._cmr_entries.get("consignee_name"),
                "\n".join(line for line in c_lines if line),
            )
        else:
            # Client → Box 1 (Consignor)
            sender_lines = []
            sender_lines.append(trip.get("client_name", client.get("name", "")))
            sender_lines.append(client.get("address", ""))
            c_vat = client.get("vat_number", "")
            c_eori = client.get("eori_number", "")
            c_contact = client.get("consignee_contact_name", "")
            c_phone = client.get("consignee_contact_phone", client.get("phone", ""))
            if c_vat:
                sender_lines.append(f"{t('cmr.vat', default='VAT:')} {c_vat}")
            if c_eori:
                sender_lines.append(f"{t('cmr.eori', default='EORI:')} {c_eori}")
            if c_contact or c_phone:
                sender_lines.append(f"{t('cmr.contact', default='Contact:')} {c_contact}, {c_phone}".strip(", "))
            self._set_entry(
                self._cmr_entries.get("consignor_name"),
                "\n".join(line for line in sender_lines if line),
            )

            # Company → Box 2 (Consignee)
            c_lines = []
            c_lines.append(conf.get("company_name", ""))
            c_lines.append(conf.get("address", ""))
            cui = conf.get("cui", "")
            eori = conf.get("eori_number", "")
            phone = conf.get("phone", "")
            if cui:
                c_lines.append(f"{t('cmr.vat_cui', default='VAT/CUI:')} {cui}")
            if eori:
                c_lines.append(f"{t('cmr.eori', default='EORI:')} {eori}")
            if phone:
                c_lines.append(f"{t('cmr.tel', default='Tel:')} {phone}")
            self._set_entry(
                self._cmr_entries.get("consignee_name"),
                "\n".join(line for line in c_lines if line),
            )

        # Carrier — always from company config
        carr_lines = []
        carr_lines.append(conf.get("company_name", ""))
        carr_lines.append(conf.get("address", ""))
        c_phone = conf.get("phone", "")
        c_email = conf.get("email", "")
        c_reg = conf.get("reg_number", "")
        if c_phone:
            carr_lines.append(f"{t('cmr.tel', default='Tel:')} {c_phone}")
        if c_email:
            carr_lines.append(f"{t('cmr.email', default='Email:')} {c_email}")
        if c_reg:
            carr_lines.append(f"{t('cmr.reg_no', default='Reg No:')} {c_reg}")
        self._set_entry(
            self._cmr_entries.get("carrier_name"),
            "\n".join(line for line in carr_lines if line),
        )

        # Vehicle plates
        plate = truck.get("plate_number", trip.get("truck_number", ""))
        trailer = truck.get("trailer_plate", trip.get("trailer_plate", ""))
        self._set_entry(self._cmr_entries.get("truck_plate"), plate)
        self._set_entry(self._cmr_entries.get("trailer_plate"), trailer)

        # Driver
        dname = driver.get("name", trip.get("driver_name", ""))
        dlic = driver.get("license_number", trip.get("driver_license", ""))
        self._set_entry(self._cmr_entries.get("driver_name"), dname)
        self._set_entry(self._cmr_entries.get("driver_license"), dlic)

        # Locations
        self._set_entry(
            self._cmr_entries.get("destination"),
            trip.get("destination", trip.get("unloading_address", "")),
        )
        self._set_entry(
            self._cmr_entries.get("delivery_country"),
            trip.get("delivery_country", ""),
        )
        self._set_entry(
            self._cmr_entries.get("place_of_loading"),
            trip.get("place_of_loading",
                     trip.get("loading_address", trip.get("origin", ""))),
        )
        self._set_entry(
            self._cmr_entries.get("place_of_loading_date"),
            trip.get("place_of_loading_date", trip.get("start_date", "")),
        )
        self._set_entry(
            self._cmr_entries.get("loading_country"),
            trip.get("loading_country", ""),
        )
        self._set_entry(
            self._cmr_entries.get("documents_attached"),
            trip.get("documents_attached", ""),
        )

        # Cargo
        self._set_entry(
            self._cmr_entries.get("cargo_marks"),
            trip.get("cargo_marks", ""),
        )
        self._set_entry(
            self._cmr_entries.get("cargo_description"),
            trip.get("cargo_description", ""),
        )
        self._set_entry(
            self._cmr_entries.get("package_count"),
            trip.get("package_count", ""),
        )
        self._set_entry(
            self._cmr_entries.get("package_type"),
            trip.get("package_type", ""),
        )
        self._set_entry(
            self._cmr_entries.get("gross_weight_kg"),
            trip.get("gross_weight_kg", ""),
        )
        self._set_entry(
            self._cmr_entries.get("volume_m3"),
            trip.get("volume_m3", ""),
        )
        self._set_entry(
            self._cmr_entries.get("hs_code"),
            trip.get("hs_code", ""),
        )
        self._set_entry(
            self._cmr_entries.get("carrier_reservations"),
            trip.get("carrier_reservations", ""),
        )
        self._set_entry(
            self._cmr_entries.get("carrier_instructions"),
            trip.get("carrier_instructions", ""),
        )

        # Payment
        payer = trip.get("carriage_payer", "")
        payer_w = self._cmr_entries.get("carriage_payer")
        if payer_w and payer in ["Sender", "Consignee"]:
            idx = payer_w.findText(payer)
            if idx >= 0:
                payer_w.setCurrentIndex(idx)

        # Special agreements
        self._set_entry(
            self._cmr_entries.get("special_agreements"),
            trip.get("special_agreements", ""),
        )

        # COD & Issue
        self._set_entry(
            self._cmr_entries.get("cod_amount"),
            trip.get("cod_amount", ""),
        )
        self._set_entry(
            self._cmr_entries.get("distance_km"),
            trip.get("distance_km", ""),
        )
        self._set_entry(
            self._cmr_entries.get("issue_place"),
            trip.get("issue_place", conf.get("address", "")),
        )
        self._set_entry(
            self._cmr_entries.get("issue_date"),
            trip.get("issue_date", ""),
        )

        # Signature paths from config
        sig_path = conf.get("signature_path", "")
        for k in ["sender", "carrier"]:
            pad = getattr(self, f"sig_{k}_pad", None)
            if pad is not None and sig_path:
                pad.set_path(sig_path)

    # ══════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════

    # ── Progress helpers ──────────────────────────────────────────────

    def show_progress(self):
        """Show the indeterminate progress bar."""
        if hasattr(self, "_progress_bar"):
            self._progress_bar.setVisible(True)

    def hide_progress(self):
        """Hide the progress bar."""
        if hasattr(self, "_progress_bar"):
            self._progress_bar.setVisible(False)

    def get_preview_button(self):
        """Return the preview button for external connection."""
        return getattr(self, "_btn_preview", None)

    def get_progress_bar(self):
        """Return the progress bar for external visibility control."""
        return getattr(self, "_progress_bar", None)

    def get_bottom_frame(self) -> QWidget | None:
        """Return the bottom action bar for adding additional controls.

        Parent views can pack their controls here so they scroll with the form.
        """
        return getattr(self, "_bottom_bar", None) or self

    def clear(self):
        """Reset all form fields to their default / empty state."""
        for _, widget in self._cmr_entries.items():
            try:
                if isinstance(widget, StyledTextEdit):
                    widget.clear()
                elif isinstance(widget, StyledComboBox):
                    widget.setCurrentIndex(0)
                elif isinstance(widget, StyledLineEdit):
                    widget.clear()
                elif isinstance(widget, QDateEdit):
                    widget.setDate(QDate.currentDate())
            except Exception:
                pass

        for row in self._adr_rows:
            row.deleteLater()
        self._adr_rows.clear()

        for row in self._successive_carrier_rows:
            row.deleteLater()
        self._successive_carrier_rows.clear()

        self._adr_toggle.setChecked(False)
        self._adr_content_wrapper.setVisible(False)

        for k in ["sender", "carrier", "consignee"]:
            pad = getattr(self, f"sig_{k}_pad", None)
            if pad is not None:
                pad._clear()

        self._consignor_role_active = True
        self._update_role_buttons()
        self._last_trip_data = None

    def _set_entry(self, widget: QWidget | None, value: Any):
        """Set the value of a form widget, handling different widget types."""
        if widget is None:
            return
        str_val = str(value) if value is not None else ""

        if isinstance(widget, StyledTextEdit):
            widget.clear()
            if str_val:
                widget.setPlainText(str_val)
        elif isinstance(widget, StyledComboBox):
            idx = widget.findText(str_val)
            if idx >= 0:
                widget.setCurrentIndex(idx)
            else:
                widget.setCurrentIndex(0)
        elif isinstance(widget, QDateEdit):
            if str_val:
                try:
                    qd = QDate.fromString(str_val, "yyyy-MM-dd")
                    if qd.isValid():
                        widget.setDate(qd)
                except Exception:
                    pass
        elif isinstance(widget, StyledLineEdit):
            widget.setText(str_val)

    # ══════════════════════════════════════════════════════════════════════
    # Data export
    # ══════════════════════════════════════════════════════════════════════

    def get_data(self) -> dict[str, Any]:
        """Collect all form fields into a flat dict for the CMR generator.

        Returns a dict compatible with ``CMRGenerator.generate()`` /
        ``generate_all_copies()``.
        """
        data: dict[str, Any] = {}
        for key, widget in self._cmr_entries.items():
            if isinstance(widget, StyledLineEdit):
                data[key] = widget.text()
            elif isinstance(widget, StyledTextEdit):
                data[key] = widget.toPlainText()
            elif isinstance(widget, QDateEdit):
                data[key] = widget.date().toString("yyyy-MM-dd")
            elif isinstance(widget, QCheckBox):
                data[key] = widget.isChecked()

        data["generating_role"] = "consignor" if self._consignor_role_active else "consignee"

        # Role-based autofill: fill in company name/address based on role
        if self._last_trip_data:
            conf = self._last_trip_data.get("company_conf") or {}
            if self._consignor_role_active and not data.get("consignor_name"):
                data["consignor_name"] = conf.get("company_name", "")
                data["consignor_address"] = conf.get("address", "")
                data["consignor_vat"] = conf.get("cui", "")
                data["consignor_phone"] = conf.get("phone", "")
                data["consignor_eori"] = ""
                data["client_name"] = data.get("consignee_name", "")
                data["client_address"] = data.get("consignee_address", "")
            else:
                data["consignor_name"] = data.get("consignor_name", "")
                data["consignor_address"] = data.get("consignor_address", "")
                data["client_name"] = data.get("consignor_name", "")
                data["client_address"] = data.get("consignor_address", "")
                data["consignee_name"] = conf.get("company_name", "")
                data["consignee_address"] = conf.get("address", "")
                data["consignee_vat"] = conf.get("cui", "")
                data["consignee_phone"] = conf.get("phone", "")

        # Signature pad paths — pads are stored as ``self.sig_{key}_pad`` attributes
        for pad_key in ["sender", "carrier", "consignee"]:
            pad = getattr(self, f"sig_{pad_key}_pad", None)
            if pad is not None:
                path = getattr(pad, "save_path", None) or getattr(pad, "image_path", None)
                if path:
                    data[f"sig_{pad_key}_path"] = path

        # ADR rows
        adr_entries = []
        for row in self._adr_rows:
            entries = row.findChildren(StyledLineEdit)
            if len(entries) >= 6:
                adr_entries.append({
                    'un_no': entries[0].text().strip(),
                    'adr_class': entries[1].text().strip(),
                    'packing_group': entries[2].text().strip(),
                    'tunnel_code': entries[3].text().strip(),
                    'quantity': entries[4].text().strip(),
                    'net_weight': entries[5].text().strip(),
                })
        if adr_entries:
            data['adr_info_json'] = json.dumps(adr_entries)

        # Successive carriers
        successive = []
        for frame in self._successive_carrier_rows:
            entries = frame.findChildren(StyledLineEdit)
            if len(entries) >= 6:
                successive.append({
                    'carrier_name': entries[0].text().strip(),
                    'carrier_address': entries[1].text().strip(),
                    'carrier_country': entries[2].text().strip(),
                    'vehicle_plate': entries[3].text().strip(),
                    'trailer_plate': entries[4].text().strip(),
                    'driver_name': entries[5].text().strip(),
                    'from_location': entries[6].text().strip()
                    if len(entries) > 6 else '',
                    'to_location': entries[7].text().strip()
                    if len(entries) > 7 else '',
                })
        if successive:
            data['successive_carriers_json'] = json.dumps(successive)

        # Financial grid (Box 20)
        financial = {}
        for key in ['carriage_sender', 'carriage_consignee',
                     'supplementary_sender', 'supplementary_consignee',
                     'customs_sender', 'customs_consignee',
                     'other_sender', 'other_consignee']:
            w = self._cmr_entries.get(key)
            if w is None:
                financial[key] = ''
            elif isinstance(w, StyledLineEdit):
                financial[key] = w.text().strip()
            elif isinstance(w, StyledComboBox):
                financial[key] = w.currentText().strip()
            else:
                financial[key] = str(w) if w else ''
        if financial:
            data["financial_grid"] = financial

        # Truck/driver fields from CMR boxes
        data["truck_plate"] = data.get("truck_plate", "")
        data["driver_name"] = data.get("driver_name", "")

        # Place, country, and address fields
        data["place_of_loading"] = data.get("place_of_loading", "")
        data["destination"] = data.get("destination", "")
        data["loading_country"] = data.get("loading_country", "")
        data["delivery_country"] = data.get("delivery_country", "")
        data["distance_km"] = data.get("distance_km", "")
        # consignee_name is a multiline field containing the full consignee details;
        # expose a consignee_address alias for downstream consumers.
        if not data.get("consignee_address"):
            data["consignee_address"] = data.get("consignee_name", "")
        if not data.get("client_address"):
            data["client_address"] = data.get("consignee_name", "")

        return data

    # ══════════════════════════════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════════════════════════════

    def wakeup(self) -> None:
        """Called when the view becomes active."""
        pass

    def shutdown(self) -> None:
        """Called when the view is discarded."""
        pass
