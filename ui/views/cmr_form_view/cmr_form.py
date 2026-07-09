"""PySide6 CMR consignment note form view — UN/CEFACT-aligned, 24-box editor.

Split from ``cmr_form_view.py``.  The form section builders live in
``cmr_fields.py``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import Btn, Card, CardHeader, Divider, Label, PageTitle
from ui.theme import COLORS, S
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

        # Scrollable form container holds everything
        self._scroll_container = ScrollableFormContainer(self, max_width=1200)
        self._scroll_container.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        layout.addWidget(self._scroll_container, 1)

        # Shortcut to the content widget inside the scroll container
        self._content = self._scroll_container.content

        self._build_page_heading()
        self._build_role_selector()
        self._build_parties_card()            # Boxes 1–2
        self._build_route_card()              # Boxes 3–5
        self._build_vehicle_card()            # Vehicle & driver
        self._build_cargo_card()              # Boxes 6–12
        self._build_instructions_card()       # Boxes 13–17
        self._build_carrier_card()            # Boxes 18–19
        self._build_charges_card()            # Box 20
        self._build_issue_signatures_card()   # Boxes 21–24

        # Bottom action bar (inside the scroll so it scrolls with the form)
        self._build_action_bar()

        # Initialize navigator state after all fields are built
        self._update_box_navigator()
        self._connect_box_signals()

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
                    f"background-color: {COLORS['success_dim']};"
                    f"color: {COLORS['success']};"
                    f"border-radius: 4px; font-size: 7px; font-weight: bold;"
                )
            elif field_keys:
                badge.setStyleSheet(
                    f"background-color: {COLORS['warning_dim']};"
                    f"color: {COLORS['warning']};"
                    f"border-radius: 4px; font-size: 7px; font-weight: bold;"
                )
            else:
                badge.setStyleSheet(
                    f"background-color: {COLORS['accent_dim']};"
                    f"color: {COLORS['accent_text']};"
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

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _build_page_heading(self):
        heading = QWidget()
        heading_layout = QVBoxLayout(heading)
        heading_layout.setContentsMargins(0, 0, 0, S["3"])
        heading_layout.setSpacing(S["1"])

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
        nav_layout.setContentsMargins(0, S["1"], 0, 0)
        nav_layout.setSpacing(2)
        self._box_badges = {}
        for i in range(1, 25):
            badge = QLabel(str(i))
            badge.setFixedSize(18, 18)
            badge.setAlignment(Qt.AlignCenter)
            badge.setProperty("role", "box-badge")
            badge.setStyleSheet(
                f"background-color: {COLORS['accent_dim']};"
                f"color: {COLORS['accent_text']};"
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
        card.layout().setSpacing(S["2"])

        label = Label(card, t("cmr.select_role", "SELECT YOUR ROLE"), role="section-title")
        card.layout().addWidget(label)
        card.layout().addWidget(Divider())

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(S["2"])

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
        """
        card = Card()
        CardHeader(card.layout(), title=title, subtitle=subtitle)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(S["3"])
        card.layout().addWidget(content)

        self._scroll_container.add_widget(card)
        return content

    def _two_col_pane(self, parent: QWidget) -> tuple[QWidget, QWidget]:
        """Return (left, right) widgets with a vertical divider between them."""
        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(S["3"])

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(S["3"])
        wrapper_layout.addWidget(left, 1)

        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setFrameShadow(QFrame.Plain)
        vline.setFixedWidth(1)
        vline.setStyleSheet(f"background-color: {COLORS['border']};")
        wrapper_layout.addWidget(vline)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(S["3"])
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
        **kwargs
            Forwarded to the underlying widget constructor.
        """
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(S["1"])

        # Label row with optional badge
        lbl_row = QWidget()
        lbl_layout = QHBoxLayout(lbl_row)
        lbl_layout.setContentsMargins(0, 0, 0, 0)
        lbl_layout.setSpacing(S["2"])

        if box_num is not None:
            badge = QLabel(str(box_num))
            badge.setFixedSize(30, 20)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                f"background-color: {COLORS['accent_dim']};"
                f"color: {COLORS['accent_text']};"
                f"border-radius: 4px; font-weight: bold; font-size: 10px;"
            )
            lbl_layout.addWidget(badge)

        label = QLabel(f"{label_en} / {label_ro}")
        label.setProperty("fontRole", "label")
        label.setStyleSheet(f"color: {COLORS['text_muted']};")
        lbl_layout.addWidget(label)
        lbl_layout.addStretch(1)

        container_layout.addWidget(lbl_row)

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

        # Add to parent layout
        parent_layout = parent.layout()
        if parent_layout is None:
            parent_layout = QVBoxLayout(parent)
            parent_layout.setContentsMargins(0, 0, 0, 0)
            parent_layout.setSpacing(S["3"])
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
        container_layout.setSpacing(S["1"])

        lbl_row = QWidget()
        lbl_layout = QHBoxLayout(lbl_row)
        lbl_layout.setContentsMargins(0, 0, 0, 0)
        lbl_layout.setSpacing(S["1"])

        badge = QLabel(str(box_num))
        badge.setFixedSize(26, 18)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background-color: {COLORS['accent_dim']};"
            f"color: {COLORS['accent_text']};"
            f"border-radius: 3px; font-weight: bold; font-size: 8px;"
        )
        lbl_layout.addWidget(badge)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px;")
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
        """Action buttons for Generate, Print, Save."""
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, S["4"], 0, 0)
        bar_layout.setSpacing(S["3"])

        self._btn_generate = Btn(
            bar,
            t("cmr.generate", "Generate CMR"),
            variant="primary",
        )
        self._btn_generate.setFixedHeight(38)
        bar_layout.addWidget(self._btn_generate)

        self._btn_print = Btn(
            bar,
            t("cmr.print", "Print"),
            variant="secondary",
        )
        self._btn_print.setFixedHeight(38)
        bar_layout.addWidget(self._btn_print)

        bar_layout.addStretch(1)

        self._btn_save = Btn(
            bar,
            t("cmr.save", "Save"),
            variant="secondary",
        )
        self._btn_save.setFixedHeight(38)
        bar_layout.addWidget(self._btn_save)

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
            return

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

        # Signature pad paths
        sig_pad_keys = [
            ("sig_sender_path", "Sender"),
            ("sig_carrier_path", "Carrier"),
            ("sig_consignee_path", "Consignee"),
        ]
        for data_key, _ in sig_pad_keys:
            if data_key in self._cmr_entries:
                pad = self._cmr_entries[data_key]
                if hasattr(pad, "save_path") and pad.save_path:
                    data[data_key] = pad.save_path
                elif hasattr(pad, "image_path") and pad.image_path:
                    data[data_key] = pad.image_path

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

        # Place and country fields
        data["place_of_loading"] = data.get("place_of_loading", "")
        data["destination"] = data.get("destination", "")
        data["loading_country"] = data.get("loading_country", "")
        data["delivery_country"] = data.get("delivery_country", "")
        data["distance_km"] = data.get("distance_km", "")

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
