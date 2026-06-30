"""PySide6 client workspace with tabbed detail views.

Replaces ``ui/client_workspace.py``. Embeds a searchable client table with
a QTabWidget for per-client details (profile, trips, invoices, revenue chart).

Usage as embedded widget::

    workspace = QtClientWorkspace(parent_widget, db)
"""

from __future__ import annotations

import contextlib
from typing import Any

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.client_service import ClientService
from services.i18n import register_listener, t, unregister_listener
from ui.components import (
    Btn,
    KPICard,
    PageTitle,
    SectionTitle,
)
from ui.design_tokens import (
    SP,
)
from ui.theme import COLORS
from ui.widgets import (
    ScrollableFormContainer,
    StyledComboBox,
    StyledLineEdit,
    StyledTableWidget,
    field,
)
from ui.widgets.client_activity_timeline import QtClientActivityTimeline
from ui.widgets.client_revenue_chart import QtClientRevenueChart

# ──────────────────────────────────────────────────────────────────────────────
# Column definitions  (id, label/i18n_key, width, translate)
# ──────────────────────────────────────────────────────────────────────────────

_CLIENT_COLUMNS: list[tuple] = [
    ("id",      "ID",                   40,  False),
    ("name",    "client.table_name",    180, True),
    ("contact", "client.table_contact", 130, True),
    ("phone",   "client.table_phone",   110, True),
    ("email",   "client.table_email",   150, True),
    ("trips",   "client.table_trips",    60, True),
]

_TRIPS_COLUMNS: list[tuple] = [
    ("start_date",     "history.table_date",   90),
    ("truck_number",   "history.table_truck",  100),
    ("distance_km",    "history.table_km",      65),
    ("total_price_eur","client.table_revenue",  85),
    ("net_profit",     "history.table_profit",  85),
    ("status",         "edit_trip.field_status",90),
]

_INVOICE_COLUMNS: list[tuple] = [
    ("invoice_number", "client.table_inv_number", 130),
    ("total_amount",   "client.table_amount",      90),
    ("due_date",       "client.table_due_date",   100),
    ("status",         "client.table_inv_status",  90),
]


def _resolve_client_labels() -> list[str]:
    return [t(key) if translate else key
            for _, key, _, translate in _CLIENT_COLUMNS]


def _client_columns_for_table() -> list[tuple]:
    labels = _resolve_client_labels()
    return [(cid, labels[i], width)
            for i, (cid, _, width, _) in enumerate(_CLIENT_COLUMNS)]


def _trips_columns_for_table() -> list[tuple]:
    return [(cid, t(label), width)
            for cid, label, width in _TRIPS_COLUMNS]


def _invoice_columns_for_table() -> list[tuple]:
    return [(cid, t(label), width)
            for cid, label, width in _INVOICE_COLUMNS]


# ──────────────────────────────────────────────────────────────────────────────
# Search entry  (tk-style placeholder)
# ──────────────────────────────────────────────────────────────────────────────


class _SearchLineEdit(StyledLineEdit):
    """Search input with focus-driven placeholder behaviour.

    Mirrors the original ``ui/client_workspace.py`` pattern where the
    placeholder is shown as actual text and cleared on focus.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._placeholder: str = ""
        self._user_typed: bool = False

    # ── Public API ─────────────────────────────────────────────────────────

    def set_placeholder(self, text: str) -> None:
        """Update the placeholder text (shown when user has not typed)."""
        self._placeholder = text
        if not self._user_typed:
            blocked = self.blockSignals(True)
            self.setText(text)
            self.blockSignals(blocked)

    def search_value(self) -> str:
        """Return the current search query, or ``""`` if user never typed."""
        if not self._user_typed:
            return ""
        return self.text().strip()

    # ── Event overrides ────────────────────────────────────────────────────

    def focusInEvent(self, event) -> None:
        if not self._user_typed:
            self.clear()
        self._user_typed = True
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        if not self.text().strip():
            self._user_typed = False
            blocked = self.blockSignals(True)
            self.setText(self._placeholder)
            self.blockSignals(blocked)
        super().focusOutEvent(event)

    def keyPressEvent(self, event) -> None:
        self._user_typed = True
        super().keyPressEvent(event)


# ──────────────────────────────────────────────────────────────────────────────
# Main workspace
# ──────────────────────────────────────────────────────────────────────────────


class QtClientWorkspace(QWidget):
    """Client management workspace with tabbed detail views.

    Displays a searchable client table at the top, with a ``QTabWidget``
    below showing the selected client's details, trips, invoices, and
    revenue chart.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs: dict | None = None,
    ):
        super().__init__(parent)
        self.db = db
        self.service = ClientService(db) if db is not None else None
        self._selected_id: int | None = None
        self._all_clients: list[dict[str, Any]] = []

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        self._build_ui()
        self._load_data()

        self.destroyed.connect(self._cleanup)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def _cleanup(self) -> None:
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)

    def shutdown(self) -> None:
        """Release resources when the view is hidden."""
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)
        self._listener_registered = False

    def wakeup(self) -> None:
        """Refresh data when the view becomes active (QStackedWidget hook)."""
        if not getattr(self, "_listener_registered", False):
            register_listener(self._language_callback)
            self._listener_registered = True
        self._load_data()

    # ── i18n ───────────────────────────────────────────────────────────────

    def _on_language_changed(self, _lang: str) -> None:
        self._update_translations()
        self._load_data()

    def _update_translations(self) -> None:
        labels = _resolve_client_labels()
        self._table.setHorizontalHeaderLabels(labels)
        self._search_entry.set_placeholder(t("common.search"))
        self._title_label.setText(t("client.title"))
        self._new_btn.setText("+ " + t("client.new_button"))
        self._edit_btn.setText(t("client.edit_button"))
        self._deact_btn.setText(t("client.deactivate_button"))

        self._tabs.setTabText(0, t("client.tab_details", "Details"))
        self._tabs.setTabText(1, t("client.tab_trips", "Trips"))
        self._tabs.setTabText(2, t("client.tab_invoices", "Invoices"))
        self._tabs.setTabText(3, t("client.tab_revenue", "Revenue"))

        # Rebuild column labels for trips & invoices tables
        trips_labels = [t(label) for _, label, _ in _TRIPS_COLUMNS]
        self._trips_table.setHorizontalHeaderLabels(trips_labels)
        inv_labels = [t(label) for _, label, _ in _INVOICE_COLUMNS]
        self._invoices_table.setHorizontalHeaderLabels(inv_labels)

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_top_bar(layout)
        self._build_content_split(layout)

    def _build_top_bar(self, parent_layout: QVBoxLayout) -> None:
        top = QFrame()
        top.setFixedHeight(72)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(SP["10"], 0, SP["10"], 0)
        top_layout.setSpacing(SP["3"])

        self._title_label = PageTitle(None, t("client.title"))
        top_layout.addWidget(self._title_label)

        top_layout.addSpacing(SP["3"])

        self._search_entry = _SearchLineEdit()
        self._search_entry.set_placeholder(t("common.search"))
        self._search_entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._search_entry.textChanged.connect(self._on_search_changed)
        top_layout.addWidget(self._search_entry, 1)

        top_layout.addStretch()

        self._new_btn = Btn(
            self,
            text="+ " + t("client.new_button"),
            command=self._open_form_new,
        )
        top_layout.addWidget(self._new_btn)

        parent_layout.addWidget(top)

    def _build_content_split(self, parent_layout: QVBoxLayout) -> None:
        """Build the client table, action bar, and tabbed detail area."""
        split = QFrame()
        split_layout = QVBoxLayout(split)
        split_layout.setContentsMargins(SP["5"], 0, SP["5"], SP["5"])
        split_layout.setSpacing(SP["3"])

        # ── Client table ───────────────────────────────────────────────────
        columns = _client_columns_for_table()
        self._table = StyledTableWidget(self, columns=columns)
        self._table.rowSelected.connect(self._on_row_selected)
        self._table.rowDoubleClicked.connect(self._on_row_double_clicked)
        self._table.setMaximumHeight(280)
        split_layout.addWidget(self._table)

        # ── Action bar ─────────────────────────────────────────────────────
        bar = QFrame()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)

        self._edit_btn = Btn(
            self,
            text=t("client.edit_button"),
            command=self._open_form_edit,
        )
        bar_layout.addWidget(self._edit_btn)

        self._deact_btn = Btn(
            self,
            text=t("client.deactivate_button"),
            command=self._deactivate,
            variant="danger",
        )
        bar_layout.addWidget(self._deact_btn)

        bar_layout.addStretch()
        split_layout.addWidget(bar)

        # ── QTabWidget ─────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setProperty("role", "client-workspace-tabs")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Details tab
        self._details_tab = _QtClientDetailsTab(self._tabs)
        self._tabs.addTab(self._details_tab, t("client.tab_details", "Details"))

        # Trips tab
        trips_cols = _trips_columns_for_table()
        self._trips_table = StyledTableWidget(self._tabs, columns=trips_cols)
        self._tabs.addTab(self._trips_table, t("client.tab_trips", "Trips"))

        # Invoices tab
        inv_cols = _invoice_columns_for_table()
        self._invoices_table = StyledTableWidget(self._tabs, columns=inv_cols)
        self._tabs.addTab(self._invoices_table, t("client.tab_invoices", "Invoices"))

        # Revenue tab
        self._revenue_tab = QWidget()
        revenue_layout = QVBoxLayout(self._revenue_tab)
        revenue_layout.setContentsMargins(0, 0, 0, 0)
        self._revenue_chart: QtClientRevenueChart | None = None
        self._tabs.addTab(self._revenue_tab, t("client.tab_revenue", "Revenue"))

        # Disable tabs until a client is selected
        self._tabs.setEnabled(False)

        split_layout.addWidget(self._tabs, 1)
        parent_layout.addWidget(split, 1)

    # ── Search ─────────────────────────────────────────────────────────────

    def _on_search_changed(self) -> None:
        self._load_data()

    # ── Data loading ───────────────────────────────────────────────────────

    def _load_data(self) -> None:
        if self.service is None:
            return

        query = self._search_entry.search_value()
        if query:
            self._all_clients = self.service.search_advanced(
                query, include_inactive=True, limit=200,
            )
        else:
            self._all_clients = self.service.get_all_with_revenue(
                include_inactive=True,
            )

        rows: list[dict[str, Any]] = []
        for c in self._all_clients:
            rows.append({
                "id":         c["id"],
                "name":       c.get("name", ""),
                "contact":    c.get("contact_person") or "",
                "phone":      c.get("phone") or "",
                "email":      c.get("email") or "",
                "trips":      c.get("trip_count", 0) or 0,
                "_is_active": c.get("is_active", 1),
            })

        self._table.set_data(rows)

        # Gray out inactive rows.
        muted = QColor(COLORS["text_muted"])
        for r, row in enumerate(rows):
            if not row.get("_is_active", 1):
                for c in range(self._table.columnCount()):
                    item = self._table.item(r, c)
                    if item is not None:
                        item.setForeground(muted)

    # ── Selection ──────────────────────────────────────────────────────────

    def _on_row_selected(self, row_data: dict) -> None:
        self._selected_id = row_data.get("id")
        self._show_detail(self._selected_id)

    def _on_row_double_clicked(self, row_data: dict) -> None:
        self._selected_id = row_data.get("id")
        self._open_form_edit()

    # ── Tab management ─────────────────────────────────────────────────────

    def _on_tab_changed(self, index: int) -> None:
        """Refresh active tab content when switching tabs."""
        if self._selected_id is None or self.service is None:
            return
        if index == 0:
            self._details_tab.refresh(self.service, self._selected_id)
        elif index == 1:
            self._load_trips()
        elif index == 2:
            self._load_invoices()
        elif index == 3:
            self._load_revenue_chart()

    def _show_detail(self, client_id: int | None) -> None:
        """Populate all tabs with the selected client's data."""
        if client_id is None or self.service is None:
            self._tabs.setEnabled(False)
            return

        self._tabs.setEnabled(True)

        # Populate the currently visible tab; others are lazy-loaded on switch.
        idx = self._tabs.currentIndex()
        if idx == 0:
            self._details_tab.refresh(self.service, client_id)
        elif idx == 1:
            self._load_trips()
        elif idx == 2:
            self._load_invoices()
        elif idx == 3:
            self._load_revenue_chart()

    def _load_trips(self) -> None:
        """Load trips into the trips table."""
        if self._selected_id is None or self.service is None:
            return
        trips = self.service.get_client_trips(self._selected_id, limit=100)
        rows = []
        for t_row in trips:
            rows.append({
                "start_date":      (t_row.get("start_date") or t_row.get("created_at", ""))[:10],
                "truck_number":    t_row.get("truck_number", ""),
                "distance_km":     f"{t_row.get('distance_km', 0) or 0:,.0f}",
                "total_price_eur": f"\u20ac {t_row.get('total_price_eur', 0) or 0:,.0f}",
                "net_profit":      f"\u20ac {t_row.get('net_profit', 0) or 0:,.0f}",
                "status":          t_row.get("status", ""),
            })
        self._trips_table.set_data(rows)

    def _load_invoices(self) -> None:
        """Load invoices into the invoices table with colour-coded status."""
        if self._selected_id is None or self.service is None:
            return
        invoices = self.service.get_client_invoices(self._selected_id, limit=100)
        rows = []
        for inv in invoices:
            status = inv.get("status", "")
            rows.append({
                "invoice_number": inv.get("invoice_number", ""),
                "total_amount":   f"\u20ac {inv.get('total_amount', 0) or 0:,.0f}",
                "due_date":       inv.get("due_date", ""),
                "status":         status,
            })
        self._invoices_table.set_data(rows)

        # Colour-code the status column.
        green = QColor(COLORS["success"])
        amber = QColor(COLORS["warning"])
        for r, row in enumerate(rows):
            status = row.get("status", "")
            item = self._invoices_table.item(r, 3)
            if item is not None:
                item.setForeground(green if status == "Paid" else amber)

    def _load_revenue_chart(self) -> None:
        """Build or refresh the revenue chart tab."""
        if self._selected_id is None or self.service is None:
            return

        # Remove any existing chart widget.
        if self._revenue_chart is not None:
            self._revenue_chart.deleteLater()
            self._revenue_chart = None

        self._revenue_chart = QtClientRevenueChart(
            self._revenue_tab,
            service=self.service,
            client_id=self._selected_id,
        )
        self._revenue_tab.layout().addWidget(self._revenue_chart)

    # ── CRUD actions ──────────────────────────────────────────────────────

    def _open_form_new(self) -> None:
        if self.service is None:
            return
        dialog = _QtClientFormDialog(
            self, self.service, client_data=None, on_save=self._on_form_saved,
        )
        dialog.exec()

    def _open_form_edit(self) -> None:
        if self._selected_id is None or self.service is None:
            return
        client = self.service.get_by_id(self._selected_id)
        if client is None:
            return
        dialog = _QtClientFormDialog(
            self, self.service, client_data=client, on_save=self._on_form_saved,
        )
        dialog.exec()

    def _on_form_saved(self) -> None:
        self._load_data()
        if self._selected_id is not None:
            self._show_detail(self._selected_id)

    def _deactivate(self) -> None:
        if self._selected_id is None or self.service is None:
            return
        client = self.service.get_by_id(self._selected_id)
        if client is None:
            return
        count = self.service.get_trip_count(self._selected_id)
        msg = t("client.deactivate_confirm").format(name=client.get("name", ""))
        if count > 0:
            msg += t("client.deactivate_trips_warning").format(count=count)

        reply = QMessageBox.question(
            self,
            t("common.confirm"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.service.deactivate(self._selected_id)
            self._selected_id = None
            self._tabs.setEnabled(False)
            self._load_data()


# ──────────────────────────────────────────────────────────────────────────────
# Client detail tab  (profile + KPIs + contacts + tags + payment + timeline)
# ──────────────────────────────────────────────────────────────────────────────


class _QtClientDetailsTab(QWidget):
    """Scrollable detail tab showing profile, KPIs, contacts, tags, payment
    summary, and activity timeline for a selected client.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = ScrollableFormContainer(self)
        self._content = scroll.content
        layout.addWidget(scroll, 1)

        self._current_client_id: int | None = None

    # ── Public API ─────────────────────────────────────────────────────────

    def refresh(self, service, client_id: int) -> None:
        """Rebuild the entire detail tab for the given client."""
        self._current_client_id = client_id
        self._clear_content()
        self._build(service, client_id)

    # ── Content management ─────────────────────────────────────────────────

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

    # ── Profile section ────────────────────────────────────────────────────

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

    # ── KPI section ───────────────────────────────────────────────────────

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

    # ── Contacts section ──────────────────────────────────────────────────

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

    # ── Tags section ──────────────────────────────────────────────────────

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

    # ── Payment summary section ───────────────────────────────────────────

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

    # ── Activity timeline section ──────────────────────────────────────────

    def _build_timeline(self, service, client_id: int) -> None:
        cl = self._content.layout()
        header_widget = SectionTitle(self._content, t("client.section_timeline"))
        cl.addWidget(header_widget)

        timeline = QtClientActivityTimeline(
            self._content, service=service, client_id=client_id,
        )
        cl.addWidget(timeline)


# ──────────────────────────────────────────────────────────────────────────────
# Client form dialog
# ──────────────────────────────────────────────────────────────────────────────


class _QtClientFormDialog(QDialog):
    """Add / edit client dialog.

    Mirrors ``_ClientFormDialog`` from the original ``ui/client_workspace.py``.
    """

    FIELDS: list[tuple] = [
        ("name",               "client.field_name",            True),
        ("contact_person",     "client.field_contact",         False),
        ("phone",              "client.field_phone",           False),
        ("email",              "client.field_email",           False),
        ("address",            "client.field_address",         False),
        ("vat_number",         "client.field_vat",             False),
        ("client_type",        "client.field_type",            False),
        ("payment_terms_days", "client.field_payment_terms",   False),
        ("credit_limit_eur",   "client.field_credit_limit",    False),
        ("default_rate_per_km","client.field_default_rate",    False),
        ("rating",             "client.field_rating",          False),
        ("notes",              "client.field_notes",           False),
    ]

    COMBO_FIELDS = {"client_type"}

    def __init__(
        self,
        parent: QWidget | None,
        service: ClientService,
        client_data: dict[str, Any] | None = None,
        on_save=None,
    ):
        super().__init__(parent)
        self.service = service
        self.client_data = client_data
        self.on_save = on_save
        self._editing = client_data is not None

        self.setWindowTitle(
            t("client.edit_title") if self._editing else t("client.new_title"),
        )
        self.setMinimumSize(500, 600)
        self.setModal(True)

        self._entries: dict[str, Any] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = ScrollableFormContainer(self, max_width=500)
        layout.addWidget(scroll, 1)

        for key, i18n_key, _required in self.FIELDS:
            if key in self.COMBO_FIELDS:
                entry = StyledComboBox(
                    values=["", "Shipper", "Forwarder", "Broker", "Direct", "Other"],
                )
                if self.client_data is not None:
                    val = self.client_data.get(key) or ""
                    idx = entry.findText(val)
                    if idx >= 0:
                        entry.setCurrentIndex(idx)
            else:
                entry = StyledLineEdit()
                if self.client_data is not None:
                    val = self.client_data.get(key) or ""
                    entry.setText(str(val))
                if key == "notes":
                    entry.setFixedHeight(60)

            self._entries[key] = entry
            fw = field(scroll.content, t(i18n_key), entry)
            scroll.add_widget(fw)

        scroll.add_stretch()

        # Bottom button bar.
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
        name_entry = self._entries["name"]
        name = name_entry.currentText() if isinstance(name_entry, StyledComboBox) else name_entry.text()
        name = name.strip()
        if not name:
            QMessageBox.warning(
                self, t("common.warning"), t("client.name_required"),
            )
            return

        data: dict[str, Any] = {}
        for k, v in self._entries.items():
            val = v.currentText().strip() if isinstance(v, StyledComboBox) else v.text().strip()

            if k in ("payment_terms_days",):
                try:
                    val = int(val) if val else 30
                except ValueError:
                    val = 30
            elif k in ("credit_limit_eur",):
                try:
                    val = float(val) if val else 0
                except ValueError:
                    val = 0
            elif k in ("default_rate_per_km",):
                try:
                    val = float(val) if val else None
                except ValueError:
                    val = None
            elif k in ("rating",):
                try:
                    val = int(val) if val else None
                except ValueError:
                    val = None

            data[k] = val

        if self._editing and self.client_data is not None:
            self.service.update(self.client_data["id"], **data)
        else:
            existing = self.service._repo.get_by_name(name)
            if existing:
                QMessageBox.warning(
                    self,
                    t("common.warning"),
                    t("client.already_exists").format(name=name),
                )
                return
            self.service.create(**data)

        if self.on_save is not None:
            self.on_save()
        self.accept()


# ──────────────────────────────────────────────────────────────────────────────
# Contact dialog
# ──────────────────────────────────────────────────────────────────────────────


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
        service: ClientService,
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


# ──────────────────────────────────────────────────────────────────────────────
# Merge dialog
# ──────────────────────────────────────────────────────────────────────────────


class _QtMergeDialog(QDialog):
    """Merge source client into a target client."""

    def __init__(
        self,
        parent: QWidget | None,
        service: ClientService,
        source_id: int,
        on_done=None,
    ):
        super().__init__(parent)
        self.service = service
        self.source_id = source_id
        self.on_done = on_done

        self.setWindowTitle(t("client.merge_title"))
        self.setMinimumSize(450, 280)
        self.setModal(True)

        self._name_to_id: dict[str, int] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["5"], SP["5"], SP["5"], SP["5"])
        layout.setSpacing(SP["3"])

        source = self.service.get_by_id(self.source_id)
        source_lbl = QLabel(
            t("client.merge_source").format(
                name=source["name"] if source else "?",
            ),
        )
        source_lbl.setProperty("fontRole", "body_bold")
        layout.addWidget(source_lbl)

        target_lbl = QLabel(t("client.merge_target_label"))
        target_lbl.setProperty("fontRole", "label")
        layout.addWidget(target_lbl)

        all_clients = self.service.get_all_with_revenue(include_inactive=True)
        names = [c["name"] for c in all_clients if c["id"] != self.source_id]
        self._name_to_id = {c["name"]: c["id"]
                            for c in all_clients if c["id"] != self.source_id}

        self._target_combo = StyledComboBox(values=names)
        if names:
            self._target_combo.setCurrentIndex(0)
        layout.addWidget(self._target_combo)

        warn = QLabel(t("client.merge_warning"))
        warn.setProperty("fontRole", "small")
        warn.setWordWrap(True)
        layout.addWidget(warn)

        layout.addStretch()

        layout.addWidget(Btn(
            self, text=t("client.merge_execute"),
            command=self._execute, variant="danger",
        ))

    def _execute(self) -> None:
        target_name = self._target_combo.currentText()
        target_id = self._name_to_id.get(target_name)
        if not target_id:
            return

        source = self.service.get_by_id(self.source_id)
        msg = t("client.merge_final_confirm").format(
            target=target_name,
            source=source["name"] if source else "?",
        )
        reply = QMessageBox.question(
            self,
            t("client.merge_title"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.service.merge_clients(self.source_id, target_id)
            QMessageBox.information(
                self,
                t("client.merge_title"),
                f"Moved: {result['trips']} trips, "
                f"{result['invoices']} invoices, "
                f"{result['contacts']} contacts",
            )
        except Exception as ex:
            QMessageBox.critical(
                self, t("common.error"), str(ex),
            )

        if self.on_done is not None:
            self.on_done()
        self.accept()
