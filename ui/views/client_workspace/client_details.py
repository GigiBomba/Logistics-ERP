"""Per-client detail tabs — profile, KPIs, contacts, tags, payment, timeline."""

from __future__ import annotations

import contextlib
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import (
    Btn,
    KPICard,
    SectionTitle,
)
from ui.design_tokens import SP
from ui.theme import COLORS
from ui.widgets import (
    ScrollableFormContainer,
    StyledComboBox,
    StyledLineEdit,
    field,
)
from ui.widgets.client_activity_timeline import QtClientActivityTimeline


# ======================================================================
# Client detail tab  (profile + KPIs + contacts + tags + payment + timeline)
# ======================================================================


class _QtClientDetailsTab(QWidget):
    """Scrollable detail tab showing profile, KPIs, contacts, tags, payment
    summary, and activity timeline for a selected client."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = ScrollableFormContainer(self)
        self._content = scroll.content
        layout.addWidget(scroll, 1)

        self._current_client_id: int | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self, service, client_id: int) -> None:
        """Rebuild the entire detail tab for the given client."""
        self._current_client_id = client_id
        self._clear_content()
        self._build(service, client_id)

    # ------------------------------------------------------------------
    # Content management
    # ------------------------------------------------------------------

    def _clear_content(self) -> None:
        layout = self._content.layout()
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _build(self, service, client_id: int) -> None:
        """Fetch dashboard data and build all sections."""
        dash = service.get_client_dashboard(client_id)
        client = dash.get("client", {})
        contacts = dash.get("contacts", [])
        tags = dash.get("tags", [])

        self._build_profile_section(client, dash, service)
        self._build_kpi_section(dash)
        self._build_contacts_section(contacts, service, client_id)
        self._build_tags_section(tags, service, client_id)

        with contextlib.suppress(Exception):
            self._build_payment_summary(service, client_id)

        with contextlib.suppress(Exception):
            self._build_timeline(service, client_id)

        self._content.layout().addStretch()

    # ------------------------------------------------------------------
    # Profile section
    # ------------------------------------------------------------------

    def _build_profile_section(self, client: dict, dash: dict,
                                service) -> None:
        cl = self._content.layout()

        name = client.get("name", "???")
        header_widget = SectionTitle(self._content, name)
        cl.addWidget(header_widget)

        # Client type badge + rating + status row.
        meta_row = QFrame()
        meta_layout = QHBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(SP["2"])

        c_type = client.get("client_type", "")
        if c_type:
            type_lbl = QLabel(c_type)
            type_lbl.setProperty("fontRole", "label")
            type_lbl.setStyleSheet(f"color: {COLORS['accent_text']};")
            meta_layout.addWidget(type_lbl)

        rating = client.get("rating") or 0
        if rating:
            stars = "\u2605" * int(rating) + "\u2606" * (5 - int(rating))
            star_lbl = QLabel(stars)
            star_lbl.setProperty("fontRole", "small")
            star_lbl.setStyleSheet(f"color: {COLORS['warning']};")
            meta_layout.addWidget(star_lbl)

        meta_layout.addStretch()

        is_active = client.get("is_active", 1)
        status_text = "Active" if is_active else "Inactive"
        status_color = COLORS["success"] if is_active else COLORS["text_muted"]
        status_lbl = QLabel(status_text)
        status_lbl.setProperty("fontRole", "label")
        status_lbl.setStyleSheet(f"color: {status_color};")
        meta_layout.addWidget(status_lbl)

        cl.addWidget(meta_row)

        # Contact details row.
        details = []
        if client.get("contact_person"):
            details.append(f"\U0001f464 {client['contact_person']}")
        if client.get("phone"):
            details.append(f"\U0001f4de {client['phone']}")
        if client.get("email"):
            details.append(f"\u2709 {client['email']}")
        if client.get("vat_number"):
            details.append(f"{t('client.vat', default='VAT:')} {client['vat_number']}")

        if details:
            details_row = QFrame()
            details_layout = QHBoxLayout(details_row)
            details_layout.setContentsMargins(0, 0, 0, 0)
            details_layout.setSpacing(SP["3"])
            for d in details:
                lbl = QLabel(d)
                lbl.setProperty("fontRole", "small")
                details_layout.addWidget(lbl)
            cl.addWidget(details_row)

        # Extra info row.
        extra = []
        if client.get("address"):
            extra.append(client["address"])
        if client.get("notes"):
            extra.append(client["notes"])
        if client.get("payment_terms_days"):
            extra.append(t("client.terms_days", default="Terms: {} days").format(client["payment_terms_days"]))
        if client.get("credit_limit_eur"):
            extra.append("Limit: \u20ac{:,}".format(int(client["credit_limit_eur"])))

        if extra:
            extra_row = QFrame()
            extra_layout = QHBoxLayout(extra_row)
            extra_layout.setContentsMargins(0, 0, 0, 0)
            extra_layout.setSpacing(SP["3"])
            for e in extra:
                lbl = QLabel(e)
                lbl.setProperty("fontRole", "small")
                extra_layout.addWidget(lbl)
            cl.addWidget(extra_row)

    # ------------------------------------------------------------------
    # KPI section
    # ------------------------------------------------------------------

    def _build_kpi_section(self, dash: dict) -> None:
        cl = self._content.layout()

        header_widget = SectionTitle(self._content, t("client.section_kpis"))
        cl.addWidget(header_widget)

        total_rev = dash.get("total_revenue", 0) or 0
        total_trips = dash.get("total_trips", 0) or 0
        total_km = dash.get("total_km", 0) or 0
        last_30 = dash.get("trips_last_30_days", 0) or 0
        total_profit = dash.get("total_profit", 0) or 0
        avg_profit = dash.get("avg_profit", 0) or 0
        outstanding = dash.get("outstanding_balance", 0) or 0
        last_trip = dash.get("last_trip_date", "\u2014")
        if last_trip and len(str(last_trip)) > 10:
            last_trip = str(last_trip)[:10]

        row1 = QFrame()
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(SP["2"])

        row1_layout.addWidget(KPICard(self._content, t("client.kpi_total_revenue"),
                                       f"\u20ac {total_rev:,.0f}"))
        row1_layout.addWidget(KPICard(self._content, t("client.kpi_total_trips"),
                                       str(total_trips)))
        row1_layout.addWidget(KPICard(self._content, t("client.kpi_total_km"),
                                       f"{total_km:,.0f} km"))
        row1_layout.addWidget(KPICard(self._content, t("client.kpi_last_30d"),
                                       str(last_30)))
        cl.addWidget(row1)

        row2 = QFrame()
        row2_layout = QHBoxLayout(row2)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(SP["2"])

        profit_card = KPICard(self._content, t("client.kpi_total_profit"),
                               f"\u20ac {total_profit:,.0f}")
        profit_card.setProperty("role", "kpi-card")
        cl.addWidget(row2)

        row2_layout.addWidget(profit_card)
        row2_layout.addWidget(KPICard(self._content, t("client.kpi_avg_profit"),
                                       f"\u20ac {avg_profit:,.0f}"))
        row2_layout.addWidget(KPICard(self._content, t("client.kpi_outstanding"),
                                       f"\u20ac {outstanding:,.0f}"))
        row2_layout.addWidget(KPICard(self._content, t("client.kpi_last_trip"),
                                       str(last_trip)))
        cl.addWidget(row2)

    # ------------------------------------------------------------------
    # Contacts section
    # ------------------------------------------------------------------

    def _build_contacts_section(self, contacts: list, service,
                                 client_id: int) -> None:
        if not contacts:
            return

        cl = self._content.layout()
        header_widget = SectionTitle(self._content, t("client.section_contacts"))
        cl.addWidget(header_widget)

        for c in contacts:
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(SP["2"])

            name_text = c.get("full_name", "")
            if c.get("is_primary"):
                name_text += " \u2605"
            name_lbl = QLabel(name_text)
            name_lbl.setProperty("fontRole", "body_bold")
            row_layout.addWidget(name_lbl)

            title = c.get("title", "")
            if title:
                title_lbl = QLabel(title)
                title_lbl.setProperty("fontRole", "small")
                row_layout.addWidget(title_lbl)

            phone = c.get("phone", "")
            email = c.get("email", "")
            contact_info = "  ".join(p for p in (phone, email) if p)
            if contact_info:
                info_lbl = QLabel(contact_info)
                info_lbl.setProperty("fontRole", "small")
                row_layout.addWidget(info_lbl)

            row_layout.addStretch()

            row_layout.addWidget(Btn(
                row, text=t("common.edit", default="Edit"),
                command=lambda cid=c["id"]: self._edit_contact(cid, service, client_id),
                variant="secondary",
            ))
            row_layout.addWidget(Btn(
                row, text="\u2716",
                command=lambda cid=c["id"]: self._delete_contact(cid, service),
                variant="danger",
            ))
            cl.addWidget(row)

        cl.addWidget(Btn(
            self._content, text="+ " + t("client.add_contact"),
            command=lambda: self._add_contact(service, client_id),
            variant="secondary",
        ))

    def _add_contact(self, service, client_id: int) -> None:
        dialog = _QtContactDialog(
            self._content, service, client_id=client_id,
            on_save=lambda: self._rebuild(service),
        )
        dialog.exec()

    def _edit_contact(self, contact_id: int, service, client_id: int) -> None:
        contacts = service.get_contacts(client_id)
        ct_data = next((c for c in contacts if c["id"] == contact_id), None)
        dialog = _QtContactDialog(
            self._content, service, client_id=client_id,
            contact_data=ct_data,
            on_save=lambda: self._rebuild(service),
        )
        dialog.exec()

    def _delete_contact(self, contact_id: int, service) -> None:
        reply = QMessageBox.question(
            self._content, t("common.confirm"),
            t("client.confirm_delete_contact"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            service.delete_contact(contact_id)
            if self._current_client_id is not None:
                self._rebuild(service)

    def _rebuild(self, service) -> None:
        if self._current_client_id is not None:
            self.refresh(service, self._current_client_id)

    # ------------------------------------------------------------------
    # Tags section
    # ------------------------------------------------------------------

    def _build_tags_section(self, tags: list, service, client_id: int) -> None:
        cl = self._content.layout()
        header_widget = SectionTitle(self._content, t("client.section_tags"))
        cl.addWidget(header_widget)

        tag_names = [t_row.get("tag", t_row) for t_row in tags]
        if not tag_names:
            no_tags = QLabel(t("client.no_tags"))
            no_tags.setProperty("fontRole", "small")
            cl.addWidget(no_tags)
        else:
            chips_row = QFrame()
            chips_layout = QHBoxLayout(chips_row)
            chips_layout.setContentsMargins(0, 0, 0, 0)
            chips_layout.setSpacing(SP["1"])
            for tag in tag_names:
                chip = QLabel(f"  {tag}  ")
                chip.setProperty("fontRole", "label")
                chip.setStyleSheet(
                    f"background-color: {COLORS['accent_dim']}; "
                    f"color: {COLORS['accent_text']}; "
                    f"border-radius: 4px; padding: 2px 4px;"
                )
                chips_layout.addWidget(chip)
            cl.addWidget(chips_row)

        # Add-tag row
        add_row = QFrame()
        add_layout = QHBoxLayout(add_row)
        add_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.setSpacing(SP["1"])

        self._tag_entry = StyledLineEdit(
            placeholder=t("client.tag_placeholder"),
        )
        add_layout.addWidget(self._tag_entry)

        add_layout.addWidget(Btn(
            add_row, text="+",
            command=lambda: self._add_tag(service, client_id),
            variant="secondary",
        ))
        cl.addWidget(add_row)

    def _add_tag(self, service, client_id: int) -> None:
        tag = (self._tag_entry.text() or "").strip()
        if tag:
            service.add_tag(client_id, tag)
            self._tag_entry.clear()
            if self._current_client_id is not None:
                self._rebuild(service)

    # ------------------------------------------------------------------
    # Payment summary section
    # ------------------------------------------------------------------

    def _build_payment_summary(self, service, client_id: int) -> None:
        pay = service.get_payment_summary(client_id)
        if not pay or not pay.get("invoice_count"):
            return

        cl = self._content.layout()
        header_widget = SectionTitle(self._content, t("client.section_payment"))
        cl.addWidget(header_widget)

        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(SP["2"])

        row_layout.addWidget(KPICard(
            self._content, t("client.billed", default="Billed"), f"\u20ac {pay['total_billed']:,.0f}",
        ))
        row_layout.addWidget(KPICard(
            self._content, t("client.paid", default="Paid"), f"\u20ac {pay['total_paid']:,.0f}",
        ))
        row_layout.addWidget(KPICard(
            self._content, t("client.unpaid", default="Unpaid"), f"\u20ac {pay['unpaid']:,.0f}",
        ))
        overdue_card = KPICard(
            self._content, t("client.overdue", default="Overdue"), f"\u20ac {pay['overdue']:,.0f}",
        )
        row_layout.addWidget(overdue_card)
        cl.addWidget(row)

    # ------------------------------------------------------------------
    # Activity timeline section
    # ------------------------------------------------------------------

    def _build_timeline(self, service, client_id: int) -> None:
        cl = self._content.layout()
        header_widget = SectionTitle(self._content, t("client.section_timeline"))
        cl.addWidget(header_widget)

        timeline = QtClientActivityTimeline(
            self._content, service=service, client_id=client_id,
        )
        cl.addWidget(timeline)


# ======================================================================
# Contact dialog  (used by details tab)
# ======================================================================


class _QtContactDialog(QDialog):
    """Add / edit contact dialog."""

    FIELDS: list[tuple] = [
        ("full_name",    "client.field_full_name"),
        ("title",        "client.field_title"),
        ("phone",        "client.field_phone"),
        ("email",        "client.field_email"),
        ("contact_type", "client.field_contact_type"),
    ]

    COMBO_FIELDS = {"contact_type"}

    def __init__(
        self,
        parent: QWidget | None,
        service: Any,
        client_id: int,
        contact_data: dict[str, Any] | None = None,
        on_save=None,
    ):
        super().__init__(parent)
        self.service = service
        self.client_id = client_id
        self.contact_data = contact_data
        self.on_save = on_save
        self._editing = contact_data is not None

        self.setWindowTitle(
            t("client.edit_contact") if self._editing else t("client.new_contact"),
        )
        self.setMinimumSize(400, 380)
        self.setModal(True)

        self._entries: dict[str, Any] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = ScrollableFormContainer(self, max_width=400)
        layout.addWidget(scroll, 1)

        for key, i18n_key in self.FIELDS:
            if key in self.COMBO_FIELDS:
                entry = StyledComboBox(
                    values=["primary", "billing", "operations", "management", "other"],
                )
                default = (self.contact_data or {}).get(key, "operations")
                idx = entry.findText(default)
                if idx >= 0:
                    entry.setCurrentIndex(idx)
            else:
                entry = StyledLineEdit()
                if self.contact_data is not None:
                    val = self.contact_data.get(key) or ""
                    entry.setText(str(val))

            self._entries[key] = entry
            fw = field(scroll.content, t(i18n_key), entry)
            scroll.add_widget(fw)

        scroll.add_stretch()

        btn_bar = QFrame()
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(SP["5"], 0, SP["5"], SP["4"])
        btn_layout.addStretch()
        btn_layout.addWidget(Btn(
            btn_bar, text=t("client.save_button"),
            command=self._save, variant="success",
        ))
        layout.addWidget(btn_bar)

    def _save(self) -> None:
        name_entry = self._entries["full_name"]
        name_val = name_entry.currentText() if isinstance(name_entry, StyledComboBox) else name_entry.text()
        name_val = name_val.strip()
        if not name_val:
            QMessageBox.warning(
                self, t("common.warning"), t("client.name_required"),
            )
            return

        data: dict[str, str] = {}
        for k, v in self._entries.items():
            val = v.currentText().strip() if isinstance(v, StyledComboBox) else v.text().strip()
            data[k] = val

        if self._editing and self.contact_data is not None:
            self.service.update_contact(self.contact_data["id"], **data)
        else:
            self.service.add_contact(self.client_id, **data)

        if self.on_save is not None:
            self.on_save()
        self.accept()
