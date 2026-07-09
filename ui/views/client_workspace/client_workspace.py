"""Main QtClientWorkspace class — UI, client table, tabs, CRUD, dialogs.

Contains the top-level :class:`QtClientWorkspace` widget along with the
client-form, merge, and other dialogs used for client management.
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
from ui.design_tokens import SP
from ui.theme import COLORS
from ui.widgets import (
    ScrollableFormContainer,
    StyledComboBox,
    StyledLineEdit,
    StyledTableWidget,
    field,
)
from ui.widgets.debounced_line_edit import DebouncedLineEdit
from ui.views.client_workspace.client_details import _QtClientDetailsTab

# ======================================================================
# Column definitions  (id, label/i18n_key, width, translate)
# ======================================================================

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


# ======================================================================
# Main workspace
# ======================================================================


class QtClientWorkspace(QWidget):
    """Client management workspace with tabbed detail views."""

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs: dict | None = None,
        ops=None,
        client_service=None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs
        self.ops = ops
        self.service = client_service
        self._selected_id: int | None = None
        self._all_clients: list[dict[str, Any]] = []

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        self._build_ui()
        self._load_data()

        self.destroyed.connect(self._cleanup)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # i18n
    # ------------------------------------------------------------------

    def _on_language_changed(self, _lang: str) -> None:
        self._update_translations()
        self._load_data()

    def _update_translations(self) -> None:
        labels = _resolve_client_labels()
        self._table.setHorizontalHeaderLabels(labels)
        self._search_entry.setPlaceholderText(t("common.search"))
        self._title_label.setText(t("client.title"))
        self._new_btn.setText("+ " + t("client.new_button"))
        self._edit_btn.setText(t("client.edit_button"))
        self._deact_btn.setText(t("client.deactivate_button"))

        self._tabs.setTabText(0, t("client.tab_manager", "Manager"))
        self._tabs.setTabText(1, t("client.tab_automail", "AutoMail"))

        self._client_tabs.setTabText(0, t("client.tab_details", "Details"))
        self._client_tabs.setTabText(1, t("client.tab_trips", "Trips"))
        self._client_tabs.setTabText(2, t("client.tab_invoices", "Invoices"))
        self._client_tabs.setTabText(3, t("client.tab_revenue", "Revenue"))

        trips_labels = [t(label) for _, label, _ in _TRIPS_COLUMNS]
        self._trips_table.setHorizontalHeaderLabels(trips_labels)
        inv_labels = [t(label) for _, label, _ in _INVOICE_COLUMNS]
        self._invoices_table.setHorizontalHeaderLabels(inv_labels)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Outer tabs: Manager | AutoMail
        self._tabs = QTabWidget()
        self._tabs.setProperty("role", "client-workspace-tabs")
        self._tabs.currentChanged.connect(self._on_outer_tab_changed)

        # ── Tab 0: Manager (client table + detail tabs) ──────────────
        manager_page = QWidget()
        manager_layout = QVBoxLayout(manager_page)
        manager_layout.setContentsMargins(0, 0, 0, 0)
        manager_layout.setSpacing(0)

        self._build_manager_top_bar(manager_layout)
        self._build_client_detail_area(manager_layout)

        self._tabs.addTab(manager_page, t("client.tab_manager", "Manager"))

        # ── Tab 1: AutoMail ──────────────────────────────────────────
        from ui.views.automail_view import QtAutoMailView

        self._automail_view = QtAutoMailView(
            self,
            db=self.db,
            prefs=self.prefs,
            ops=self.ops,
        )
        self._tabs.addTab(self._automail_view, t("client.tab_automail", "AutoMail"))

        layout.addWidget(self._tabs, 1)

    def _build_manager_top_bar(self, parent_layout: QVBoxLayout) -> None:
        top = QFrame()
        top.setFixedHeight(72)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(SP["10"], 0, SP["10"], 0)
        top_layout.setSpacing(SP["3"])

        self._title_label = PageTitle(None, t("client.title"))
        top_layout.addWidget(self._title_label)

        top_layout.addSpacing(SP["3"])

        self._search_entry = DebouncedLineEdit(
            placeholder=t("common.search"),
        )
        self._search_entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._search_entry.debouncedTextChanged.connect(self._on_search_changed)
        top_layout.addWidget(self._search_entry, 1)

        top_layout.addStretch()

        self._new_btn = Btn(
            self,
            text="+ " + t("client.new_button"),
            command=self._open_form_new,
        )
        top_layout.addWidget(self._new_btn)

        parent_layout.addWidget(top)

    def _build_client_detail_area(self, parent_layout: QVBoxLayout) -> None:
        """Build the client table, action bar, and per-client tabbed detail area."""
        split = QFrame()
        split_layout = QVBoxLayout(split)
        split_layout.setContentsMargins(SP["5"], 0, SP["5"], SP["5"])
        split_layout.setSpacing(SP["3"])

        # ── Client table ─────────────────────────────────────────────
        columns = _client_columns_for_table()
        self._table = StyledTableWidget(self, columns=columns)
        self._table.rowSelected.connect(self._on_row_selected)
        self._table.rowDoubleClicked.connect(self._on_row_double_clicked)
        self._table.setMaximumHeight(500)
        split_layout.addWidget(self._table)

        # ── Action bar ───────────────────────────────────────────────
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

        # ── Per-client detail tabs ───────────────────────────────────
        self._client_tabs = QTabWidget()
        self._client_tabs.setProperty("role", "client-detail-tabs")
        self._client_tabs.currentChanged.connect(self._on_client_tab_changed)

        # Details tab
        self._details_tab = _QtClientDetailsTab(self._client_tabs)
        self._client_tabs.addTab(self._details_tab, t("client.tab_details", "Details"))

        # Trips tab
        trips_cols = _trips_columns_for_table()
        self._trips_table = StyledTableWidget(self._client_tabs, columns=trips_cols)
        self._client_tabs.addTab(self._trips_table, t("client.tab_trips", "Trips"))

        # Invoices tab
        inv_cols = _invoice_columns_for_table()
        self._invoices_table = StyledTableWidget(self._client_tabs, columns=inv_cols)
        self._client_tabs.addTab(self._invoices_table, t("client.tab_invoices", "Invoices"))

        # Revenue tab
        self._revenue_tab = QWidget()
        revenue_layout = QVBoxLayout(self._revenue_tab)
        revenue_layout.setContentsMargins(0, 0, 0, 0)
        self._revenue_chart: Any = None  # QtClientRevenueChart
        self._client_tabs.addTab(self._revenue_tab, t("client.tab_revenue", "Revenue"))

        # Disable detail tabs until a client is selected
        self._client_tabs.setEnabled(False)

        split_layout.addWidget(self._client_tabs, 1)
        parent_layout.addWidget(split, 1)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_changed(self) -> None:
        self._load_data()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_data(self) -> None:
        if self.service is None:
            return

        query = self._search_entry.text().strip()
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

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_row_selected(self, row_data: dict) -> None:
        self._selected_id = row_data.get("id")
        self._show_detail(self._selected_id)

    def _on_row_double_clicked(self, row_data: dict) -> None:
        self._selected_id = row_data.get("id")
        self._open_form_edit()

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------

    def _on_outer_tab_changed(self, index: int) -> None:
        """Handle switching between Manager and AutoMail tabs."""
        if index == 1 and hasattr(self, "_automail_view"):
            self._automail_view._ensure_wired()

    def _on_client_tab_changed(self, index: int) -> None:
        """Refresh active client detail tab content when switching tabs."""
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
            self._client_tabs.setEnabled(False)
            return

        self._client_tabs.setEnabled(True)

        idx = self._client_tabs.currentIndex()
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

        if self._revenue_chart is not None:
            self._revenue_chart.deleteLater()
            self._revenue_chart = None

        from ui.widgets.client_revenue_chart import QtClientRevenueChart

        self._revenue_chart = QtClientRevenueChart(
            self._revenue_tab,
            service=self.service,
            client_id=self._selected_id,
        )
        tab_layout = self._revenue_tab.layout()
        if tab_layout is not None:
            tab_layout.addWidget(self._revenue_chart)
        else:
            from PySide6.QtWidgets import QVBoxLayout
            tab_layout = QVBoxLayout(self._revenue_tab)
            tab_layout.addWidget(self._revenue_chart)

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

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
            self._client_tabs.setEnabled(False)
            self._load_data()


# ======================================================================
# Client form dialog
# ======================================================================


class _QtClientFormDialog(QDialog):
    """Add / edit client dialog."""

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


# ======================================================================
# Merge dialog
# ======================================================================


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
