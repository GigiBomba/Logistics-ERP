"""PySide6 generators view — unified Invoice + CMR document generation UI.

Replaces ``ui/views/generators_view.py``. A persistent trip selector sits at the
top; below it a ``QTabWidget`` switches between invoice editing and CMR document
generation with language control, action buttons and copy-status tracking.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import qtawesome as qta

from models.cmr_models import CmrGenerateRequest
from services.client_service import ClientService
from services.fleet_service import FleetService
from services.i18n import register_listener, t, unregister_listener
from ui.performance_timer import PerfTimer
from ui.worker_pool import WorkerPool
from services.route_service import RouteService
from services.trip_service import TripService
from ui.components import (
    Btn,
    Card,
    Divider,
    EmptyState,
    FieldLabel,
    Label,
    PageTitle,
    SectionTitle,
)
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_ELEVATED,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_INFO_DEFAULT,
    COLOR_INFO_SUBTLE,
    COLOR_SUCCESS_SUBTLE,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    FONT_MONO,
    FONT_SIZE_LG,
    FONT_SIZE_SM,
    SP,
)

from ui.views.cmr_form_view import QtCmrFormView
from ui.views.invoice_editor import QtInvoiceEditor
from ui.views.receipt_editor import QtReceiptEditor
from ui.widgets import (
    ActionButton,
    StyledComboBox,
)

logger = logging.getLogger(__name__)

_COPY_META = {
    "Sender":        {"color": COLOR_ERROR_TEXT,     "bg": COLOR_ERROR_SUBTLE,   "icon": "\U0001F4E4"},
    "Consignee":     {"color": COLOR_INFO_DEFAULT,   "bg": COLOR_INFO_SUBTLE,    "icon": "\U0001F4E5"},
    "Carrier":       {"color": COLOR_SUCCESS_TEXT,   "bg": COLOR_SUCCESS_SUBTLE, "icon": "\U0001F69B"},
    "Administrative": {"color": COLOR_TEXT_SECONDARY, "bg": COLOR_BG_OVERLAY,    "icon": "\U0001F4C1"},
}

_COPY_ACCENT_COLORS = {
    "Sender":        "#6366f1",
    "Consignee":     "#1e1b4b",
    "Carrier":       "#052e16",
    "Administrative": "#27272a",
}

_COPY_SUFFIX_KEYS = {
    "Sender":        "generators.cmr_copy_sender",
    "Consignee":     "generators.cmr_copy_consignee",
    "Carrier":       "generators.cmr_copy_carrier",
    "Administrative": "generators.cmr_copy_admin",
}


# ══════════════════════════════════════════════════════════════════════════════
#  QtGeneratorsView
# ══════════════════════════════════════════════════════════════════════════════


class QtGeneratorsView(QWidget):
    """Generators workspace — tabbed Invoice + CMR document generation.

    Designed for embedded use in a QStackedWidget.  A persistent trip
    selector sits at the top; below it a QTabWidget switches between:

    * **Invoice** — scrollable form for building and previewing invoices.
    * **CMR** — consignment note form with language selectors, generate
      actions, and per-copy open/status tracking.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs: Any | None = None,
        client_service=None,
        fleet_service=None,
        trip_service=None,
        driver_repo=None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs
        self._client_svc_instance = client_service
        self._fleet_svc_instance = fleet_service
        self._trip_svc_instance = trip_service
        self._cmr_doc_service = None
        self._driver_repo = driver_repo

        # ── State ───────────────────────────────────────────────────────
        self._trips_list: list[dict[str, Any]] = []
        self._cmr_last_paths: dict[str, str] = {}
        self._cmr_filled_trip_id: int | None = None

        self._copy_labels: dict[str, tuple[QLabel, QLabel, ActionButton]] = {}
        self._cmr_status_lbl: QLabel | None = None
        self._cmr_lang1_combo: StyledComboBox | None = None
        self._cmr_lang2_combo: StyledComboBox | None = None
        self._invoice_built = False
        self._cmr_built = False
        self._receipt_built = False
        self._proforma_built = False

        # ── i18n tracking ───────────────────────────────────────────────
        self._i18n_labels: list[tuple[QLabel, str]] = []
        self._i18n_buttons: list[tuple[ActionButton, str]] = []
        self._i18n_sections: dict[str, QLabel] = {}
        self._language_callback = self._on_language_changed

        # ── Build ───────────────────────────────────────────────────────
        self._build_ui()
        register_listener(self._language_callback)
        self._listener_registered = True

    # ──────────────────────────────────────────────────────────────────────────
    #  Typed service properties (lazy singleton)
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def _trip_svc(self) -> TripService:
        """Lazily-initialised TripService singleton — @property for consistency."""
        if self._trip_svc_instance is None:
            self._trip_svc_instance = TripService(self.db)
        return self._trip_svc_instance

    @property
    def _client_svc(self) -> ClientService:
        """Lazily-initialised ClientService singleton — @property for consistency."""
        if self._client_svc_instance is None:
            self._client_svc_instance = ClientService(self.db)
        return self._client_svc_instance

    @property
    def _fleet_svc(self) -> FleetService:
        """Lazily-initialised FleetService singleton — @property for consistency."""
        if self._fleet_svc_instance is None:
            self._fleet_svc_instance = FleetService(self.db)
        return self._fleet_svc_instance

    @property
    def _cmr_doc_svc(self) -> "DocumentService":
        """Lazily-initialised DocumentService singleton (lazy import)."""
        if self._cmr_doc_service is None:
            from services.document_service import DocumentService  # noqa: late import
            self._cmr_doc_service = DocumentService(self.db)
        return self._cmr_doc_service

    # ──────────────────────────────────────────────────────────────────────────
    #  UI Build
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setAccessibleName("Document generators")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_header(layout)

        # Stacked widget: page 0 = empty state, page 1 = tab content
        self._content_stack = QStackedWidget()

        self._empty_state = EmptyState(
            self,
            icon_name="fa5s.file-alt",
            title=t("generators.empty_title", default="Select a trip to generate documents"),
            subtitle=t("generators.empty_desc", default="Choose a trip from the selector above or create a new trip first."),
        )
        self._empty_state.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._content_stack.addWidget(self._empty_state)

        self._tab_content_widget = QWidget()
        self._tab_content_layout = QVBoxLayout(self._tab_content_widget)
        self._tab_content_layout.setContentsMargins(0, 0, 0, 0)
        self._tab_content_layout.setSpacing(0)
        self._content_stack.addWidget(self._tab_content_widget)

        self._build_tab_content(self._tab_content_layout)

        layout.addWidget(self._content_stack, 1)
        self._refresh_trip_lists()

    # ── Header row (title + trip selector) ──────────────────────────────

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        header = QFrame()
        header.setObjectName("card")
        header.setFixedHeight(72)
        hdr_layout = QHBoxLayout(header)
        hdr_layout.setContentsMargins(SP["10"], SP["4"], SP["10"], SP["4"])

        title_block = QWidget()
        title_vlyt = QVBoxLayout(title_block)
        title_vlyt.setContentsMargins(0, 0, 0, 0)
        title_vlyt.setSpacing(SP["1"])

        title_lbl = PageTitle(header, t("generators.title"))
        title_vlyt.addWidget(title_lbl)
        self._i18n_labels.append((title_lbl, "generators.title"))

        subtitle_lbl = Label(header, t("generators.subtitle"), role="secondary")
        title_vlyt.addWidget(subtitle_lbl)
        self._i18n_labels.append((subtitle_lbl, "generators.subtitle"))

        hdr_layout.addWidget(title_block, 1)

        # ── Trip selector ────────────────────────────────────────────
        trip_block = QWidget()
        trip_hlyt = QHBoxLayout(trip_block)
        trip_hlyt.setContentsMargins(0, 0, 0, 0)
        trip_hlyt.setSpacing(SP["2"])

        trip_label = FieldLabel(trip_block, t("generators.trip_label"))
        trip_hlyt.addWidget(trip_label)
        self._i18n_labels.append((trip_label, "generators.trip_label"))

        self._trip_combo = StyledComboBox(
            trip_block,
            values=[],
            state="readonly",
        )
        self._trip_combo.setMinimumWidth(340)
        self._trip_combo.currentTextChanged.connect(self._on_global_trip_selected)
        trip_hlyt.addWidget(self._trip_combo)

        refresh_btn = Btn(
            trip_block,
            "\u21BB",
            command=self._refresh_trip_lists,
            variant="secondary",
        )
        refresh_btn.setFixedWidth(36)
        refresh_btn.setFixedHeight(36)
        trip_hlyt.addWidget(refresh_btn)

        hdr_layout.addWidget(trip_block)

        parent_layout.addWidget(header)

    # ── QTabWidget ─────────────────────────────────────────────────────

    def _build_tab_content(self, parent_layout: QVBoxLayout) -> None:
        self._tab_widget = QTabWidget()
        self._tab_widget.setProperty("role", "generators-tabs")
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        parent_layout.addWidget(self._tab_widget, 1)

        # Invoice tab — empty page; content built lazily on first access
        self._invoice_tab = QWidget()
        invoice_layout = QVBoxLayout(self._invoice_tab)
        invoice_layout.setContentsMargins(0, 0, 0, 0)
        self._tab_widget.addTab(self._invoice_tab, "")

        # CMR tab — empty page
        self._cmr_tab = QWidget()
        cmr_layout = QVBoxLayout(self._cmr_tab)
        cmr_layout.setContentsMargins(0, 0, 0, 0)
        cmr_layout.setSpacing(0)
        self._tab_widget.addTab(self._cmr_tab, "")

        # Receipt tab — empty page
        self._receipt_tab = QWidget()
        receipt_layout = QVBoxLayout(self._receipt_tab)
        receipt_layout.setContentsMargins(0, 0, 0, 0)
        self._tab_widget.addTab(self._receipt_tab, "")

        # Proforma tab — empty page
        self._proforma_tab = QWidget()
        proforma_layout = QVBoxLayout(self._proforma_tab)
        proforma_layout.setContentsMargins(0, 0, 0, 0)
        proforma_layout.setSpacing(0)
        self._tab_widget.addTab(self._proforma_tab, "")

        # Set tab text after construction so refresh_translations can
        # update them later.
        self._refresh_tab_titles()

    def _refresh_tab_titles(self) -> None:
        """Update QTabWidget tab labels from translation keys."""
        self._tab_widget.setTabText(0, t("generators.doc_invoice_title"))
        self._tab_widget.setTabText(1, t("generators.doc_cmr_title"))
        self._tab_widget.setTabText(2, t("generators.doc_receipt_title"))
        self._tab_widget.setTabText(3, t("generators.doc_proforma_title", "Proforma"))

    # ── Invoice tab content ────────────────────────────────────────────

    def _build_invoice_tab(self, layout: QVBoxLayout) -> None:
        """Embed the full QtInvoiceEditor in the invoice tab."""
        self._full_invoice_editor = QtInvoiceEditor(
            self._invoice_tab, db=self.db, prefs=self.prefs,
        )
        layout.addWidget(self._full_invoice_editor, 1)

    # ── CMR tab content ───────────────────────────────────────────────

    def _build_cmr_tab(self, layout: QVBoxLayout) -> None:
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        # ── LEFT panel — Full CMRFormView (24-box UN/CEFACT) ─────────
        self._cmr_form_view = QtCmrFormView(self._cmr_tab, db=self.db)
        splitter.addWidget(self._cmr_form_view)
        splitter.setStretchFactor(0, 1)

        # ── RIGHT panel — Options + Actions + Copies (≈340px) ─────────
        right_panel = QWidget()
        right_lyt = QVBoxLayout(right_panel)
        right_lyt.setContentsMargins(SP["3"], 0, 0, 0)
        right_lyt.setSpacing(SP["4"])

        # Options card (languages)
        options_card = self._build_cmr_options_card(right_panel)
        right_lyt.addWidget(options_card)

        # Actions card
        actions_card = self._build_cmr_actions_card(right_panel)
        right_lyt.addWidget(actions_card)

        # Copies panel
        copies_panel = self._build_cmr_copies_panel()
        right_lyt.addWidget(copies_panel, 1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 0)

        layout.addWidget(splitter, 1)

    # ── Options card (languages) ─────────────────────────────────

    def _build_cmr_options_card(self, parent: QWidget) -> QFrame:
        """Language selection card for the centre panel."""
        card = Card(parent)
        title_lbl = SectionTitle(card, t("generators.cmr_options_title"))
        card.layout().addWidget(title_lbl)
        self._i18n_sections["generators.cmr_options_title"] = title_lbl
        card.layout().addWidget(Divider(card))

        lang_codes = self.prefs.get_available_languages() if self.prefs else ["en", "ro"]
        lang_display = []
        for c in lang_codes:
            try:
                dn = self.prefs.get_language_display_name(c) if self.prefs else c
                lang_display.append(f"{dn} ({c})")
            except Exception:
                lang_display.append(c)

        self._cmr_lang1_container, self._cmr_lang1_combo = self._build_lang_combo(
            card, t("generators.cmr_primary_language"), lang_display, 0)
        card.layout().addWidget(self._cmr_lang1_container)

        self._cmr_lang2_container, self._cmr_lang2_combo = self._build_lang_combo(
            card, t("generators.cmr_secondary_language"), lang_display,
            1 if len(lang_display) > 1 else 0)
        card.layout().addWidget(self._cmr_lang2_container)

        return card

    # ── Actions card ──────────────────────────────────────────────

    def _build_cmr_actions_card(self, parent: QWidget) -> QFrame:
        """Action buttons card for the centre panel."""
        card = Card(parent)
        title_lbl = SectionTitle(card, t("generators.cmr_actions_title"))
        card.layout().addWidget(title_lbl)
        self._i18n_sections["generators.cmr_actions_title"] = title_lbl
        card.layout().addWidget(Divider(card))

        # ── Progress bar (hidden by default) ──────────────────────────
        self._cmr_progress_bar = QProgressBar()
        self._cmr_progress_bar.setRange(0, 0)  # indeterminate
        self._cmr_progress_bar.setFixedHeight(4)
        self._cmr_progress_bar.setTextVisible(False)
        self._cmr_progress_bar.setVisible(False)
        self._cmr_progress_bar.setStyleSheet(f"""
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
        card.layout().addWidget(self._cmr_progress_bar)

        # ── Preview button ────────────────────────────────────────────
        btn_preview = Btn(
            card,
            t("cmr.preview", "Preview"),
            command=self._preview_cmr,
            variant="secondary",
            icon_name="fa5s.eye",
        )
        btn_preview.setFixedHeight(38)
        card.layout().addWidget(btn_preview)
        self._i18n_buttons.append((btn_preview, "cmr.preview"))

        btn_single = Btn(
            card,
            f"\U0001F4E4  {t('generators.cmr_generate_single')}",
            command=self._generate_cmr,
            variant="secondary",
        )
        btn_single.setFixedHeight(38)
        card.layout().addWidget(btn_single)
        self._i18n_buttons.append((btn_single, "generators.cmr_generate_single"))

        btn_all = Btn(
            card,
            f"\U0001F680  {t('generators.cmr_generate_all')}",
            command=self._generate_all_copies,
            variant="primary",
        )
        btn_all.setFixedHeight(42)
        card.layout().addWidget(btn_all)
        self._i18n_buttons.append((btn_all, "generators.cmr_generate_all"))

        return card

    # ── Copies panel ──────────────────────────────────────────────

    def _build_cmr_copies_panel(self) -> QWidget:
        """Right-side panel showing copy rows with accent bars + status chips."""
        panel = Card(self._cmr_tab)
        title_lbl = SectionTitle(panel, t("generators.cmr_copies_title"))
        panel.layout().addWidget(title_lbl)
        self._i18n_sections["generators.cmr_copies_title"] = title_lbl
        panel.layout().addWidget(Divider(panel))

        self._cmr_status_lbl = Label(panel, t("generators.cmr_status_ready"), role="muted")
        panel.layout().addWidget(self._cmr_status_lbl)
        self._i18n_labels.append((self._cmr_status_lbl, "generators.cmr_status_ready"))

        copies_grid = QWidget()
        copies_grid_vlyt = QVBoxLayout(copies_grid)
        copies_grid_vlyt.setContentsMargins(0, 0, 0, 0)
        copies_grid_vlyt.setSpacing(SP["1"])

        self._copy_labels = {}
        for suffix in ["Sender", "Consignee", "Carrier", "Administrative"]:
            meta = self._copy_meta(suffix)
            accent_color = _COPY_ACCENT_COLORS[suffix]
            suffix_key = _COPY_SUFFIX_KEYS[suffix]

            row = QFrame()
            row.setProperty("role", "card")
            row.setFixedHeight(44)
            row.setStyleSheet(
                "QFrame[role=\"card\"] { background-color: #111113; }"
            )
            row_lyt = QHBoxLayout(row)
            row_lyt.setContentsMargins(0, 0, 0, 0)
            row_lyt.setSpacing(0)

            # Left accent bar
            accent_bar = QFrame()
            accent_bar.setFixedWidth(3)
            accent_bar.setStyleSheet(
                f"background-color: {accent_color}; border: none; border-radius: 2px;"
            )
            row_lyt.addWidget(accent_bar)

            # Content area
            content = QWidget()
            content_lyt = QHBoxLayout(content)
            content_lyt.setContentsMargins(SP["2"], 0, SP["2"], 0)
            content_lyt.setSpacing(SP["2"])

            icon_lbl = QLabel(meta["icon"])
            icon_lbl.setFixedWidth(22)
            icon_lbl.setStyleSheet(f"color: {meta['color']}; font-size: 12px;")
            content_lyt.addWidget(icon_lbl)

            copy_name_lbl = Label(content, t(suffix_key), role="muted")
            content_lyt.addWidget(copy_name_lbl)

            copy_status_lbl = Label(content, t("generators.cmr_not_generated"), role="muted")
            content_lyt.addWidget(copy_status_lbl, 1)

            open_btn = Btn(
                content,
                t("generators.open_pdf"),
                command=lambda s=suffix: self._open_copy(s),
                variant="ghost",
            )
            open_btn.setFixedHeight(22)
            open_btn.setFixedWidth(46)
            open_btn.setEnabled(False)
            content_lyt.addWidget(open_btn)

            row_lyt.addWidget(content, 1)
            copies_grid_vlyt.addWidget(row)
            self._copy_labels[suffix] = (copy_name_lbl, copy_status_lbl, open_btn)

        panel.layout().addWidget(copies_grid)
        panel.layout().addStretch(1)
        return panel

    def _build_lang_combo(
        self,
        parent: QWidget,
        label_text: str,
        values: list[str],
        default_index: int,
    ) -> tuple[QWidget, StyledComboBox]:
        """Build a labelled language combo-box.

        Returns ``(container, combo)`` so callers can reference both for
        layout and value extraction.
        """
        container = QWidget()
        vlyt = QVBoxLayout(container)
        vlyt.setContentsMargins(0, 0, 0, 0)
        vlyt.setSpacing(SP["1"])

        lbl = FieldLabel(container, label_text)
        vlyt.addWidget(lbl)

        combo = StyledComboBox(values=values, state="readonly")
        vlyt.addWidget(combo)
        if values and 0 <= default_index < len(values):
            combo.setCurrentIndex(default_index)

        return container, combo

    @staticmethod
    def _copy_meta(suffix: str) -> dict[str, Any]:
        return _COPY_META.get(suffix, {
            "color": COLOR_TEXT_SECONDARY,
            "bg": COLOR_BG_ELEVATED,
            "icon": "\U0001F4C4",
        })

    # ── Receipt tab content ───────────────────────────────────────────

    def _build_receipt_tab(self, layout: QVBoxLayout) -> None:
        """Embed the full QtReceiptEditor in the Receipt tab."""
        self._receipt_editor = QtReceiptEditor(
            self._receipt_tab, db=self.db, prefs=self.prefs,
        )
        layout.addWidget(self._receipt_editor, 1)

    # ── Proforma tab ───────────────────────────────────────────────────

    def _build_proforma_tab(self, layout: QVBoxLayout) -> None:
        """Embed the full QtProformaEditor in the Proforma tab."""
        try:
            from ui.views.proforma_editor import QtProformaEditor
        except Exception:
            logger.exception("Failed to import QtProformaEditor")
            return None
        try:
            self._proforma_editor = QtProformaEditor(
                self._proforma_tab, db=self.db, prefs=self.prefs,
            )
            layout.addWidget(self._proforma_editor, 1)
        except Exception:
            logger.exception("Failed to construct QtProformaEditor")

    # ── Tab switching ──────────────────────────────────────────────────

    def _on_tab_changed(self, index: int) -> None:
        """Lazy init: build tab content on first access, then wakeup."""
        if index == 0 and not self._invoice_built:
            self._invoice_built = True
            self._build_invoice_tab(self._invoice_tab.layout())
            if self._full_invoice_editor:
                self._full_invoice_editor.wakeup()
            self._refresh_trip_lists()
        elif index == 1 and not self._cmr_built:
            self._cmr_built = True
            self._build_cmr_tab(self._cmr_tab.layout())
            self._refresh_trip_lists()
        elif index == 2 and not self._receipt_built:
            self._receipt_built = True
            self._build_receipt_tab(self._receipt_tab.layout())
            if self._receipt_editor:
                self._receipt_editor.wakeup()
            self._refresh_trip_lists()
        elif index == 3 and not self._proforma_built:
            self._proforma_built = True
            self._build_proforma_tab(self._proforma_tab.layout())
            if hasattr(self, "_proforma_editor") and self._proforma_editor:
                self._proforma_editor.wakeup()
            self._refresh_trip_lists()

    # ──────────────────────────────────────────────────────────────────────────
    #  Trip handling
    # ──────────────────────────────────────────────────────────────────────────

    def _format_trip_label(self, trip: dict[str, Any]) -> str:
        """Build a display label for a trip."""
        return t("invoice.trip_list_format").format(
            id=trip["id"],
            truck_number=trip.get("truck_number", ""),
            client_name=trip.get("client_name", ""),
            created_at=trip.get("created_at", "")[:10] if trip.get("created_at") else "",
        )

    def _refresh_trip_lists(self) -> None:
        """Fetch trips from the database and populate the trip combo in-place."""
        with PerfTimer("generators.refresh_trip_lists"):
            WorkerPool.run(
                fn=self._trip_svc.get_all,
                on_result=self._on_trips_loaded,
                on_error=self._on_trips_error,
            )

    def _on_trips_loaded(self, trips: list[dict[str, Any]]) -> None:
        self._trips_list = trips

        # Toggle empty state vs tab content
        if not trips:
            self._content_stack.setCurrentIndex(0)
            self._trip_combo.clear()
            return
        else:
            self._content_stack.setCurrentIndex(1)

        # Build lookup of current combo items and new items keyed by trip id
        current = {self._trip_combo.itemData(i): i for i in range(self._trip_combo.count())}
        new = {trip["id"]: self._format_trip_label(trip) for trip in trips}

        # Remove combo items whose trip was deleted
        for vid in list(current.keys()):
            if vid not in new:
                self._trip_combo.removeItem(current[vid])

        # Add combo items for new trips
        for vid, label in new.items():
            if vid not in current:
                self._trip_combo.addItem(label, vid)

    def _on_trips_error(self, msg: str) -> None:
        logger.warning("Could not refresh trip lists: %s", msg)

    def _on_global_trip_selected(self, choice: str = "") -> None:
        trip_id = self._trip_combo.currentData()
        if trip_id is None:
            return
        trip = self._trip_svc.get_by_id(trip_id)
        if not trip:
            return
        if self._cmr_built:
            if trip.get("id") != self._cmr_filled_trip_id:
                self._cmr_filled_trip_id = None
            self._auto_fill_cmr(trip)
        if self._receipt_built and self._receipt_editor:
            self._auto_fill_receipt(trip)

    def _auto_fill_cmr(self, trip: dict[str, Any]) -> None:
        """Auto-fill the CMR form fields from the selected trip."""
        if not self.db:
            return
        trip_id = trip.get("id")
        if trip_id is not None and trip_id == self._cmr_filled_trip_id:
            return
        self._cmr_filled_trip_id = trip_id

        from services.invoicing.config_manager import load_company_config
        conf = load_company_config()

        client_data: dict[str, Any] = {}
        truck_data: dict[str, Any] = {}
        driver_data: dict[str, Any] = {}

        if trip.get("client_id"):
            try:
                client_data = self._client_svc.get_by_id(trip["client_id"]) or {}
            except Exception as e:
                logger.warning("Could not load clients for CMR autofill: %s", e)
        if trip.get("truck_id"):
            try:
                truck_data = self._fleet_svc.get_truck(trip["truck_id"]) or {}
            except Exception as e:
                logger.warning("Could not load truck for CMR autofill: %s", e)
        if trip.get("driver_id"):
            try:
                driver_data = self._driver_repo.get_by_id(trip["driver_id"]) or {}
            except Exception as e:
                logger.warning("Could not load driver for CMR autofill: %s", e)

        if hasattr(self, "_cmr_form_view") and self._cmr_form_view is not None:
            self._cmr_form_view.fill_from_trip(trip, conf, client_data, truck_data, driver_data)

        if trip.get("route_history_v2_id"):
            self._fill_stops_from_route(trip["route_history_v2_id"])

    def _fill_stops_from_route(self, route_id: int) -> None:
        """Extract origin/destination from route stops and fill CMR fields.

        Delegates JSON parsing and route data extraction to RouteService.
        """
        try:
            stops_json = self._trip_svc.get_route_stops_json(route_id)
            if not stops_json:
                return
            # Delegate JSON parsing / extraction to RouteService
            origin, destination = RouteService.parse_route_stops(stops_json)
            if not origin and not destination:
                return
            if hasattr(self, "_cmr_form_view") and self._cmr_form_view is not None:
                entries = self._cmr_form_view._cmr_entries
                if origin and "place_of_loading" in entries:
                    w = entries["place_of_loading"]
                    if hasattr(w, "setText"):
                        w.setText(origin)
                if destination and "destination" in entries:
                    w = entries["destination"]
                    if hasattr(w, "setText"):
                        w.setText(destination)
        except Exception as e:
            logger.debug("Could not fill stops from route %d: %s", route_id, e)

    def _auto_fill_receipt(self, trip: dict) -> None:
        """Auto-fill receipt logistics fields from the selected trip."""
        if not self.db:
            return
        try:
            pickup = ""
            delivery = ""
            if trip.get("route_history_v2_id"):
                stops_json = self._trip_svc.get_route_stops_json(trip["route_history_v2_id"])
                if stops_json:
                    stops = json.loads(stops_json)
                    if isinstance(stops, list) and len(stops) >= 2:
                        pickup = stops[0].get("address", "")
                        delivery = stops[-1].get("address", "")

            if hasattr(self._receipt_editor, "_pickup_location_entry") and pickup:
                self._receipt_editor._pickup_location_entry.setText(pickup)
            if hasattr(self._receipt_editor, "_delivery_location_entry") and delivery:
                self._receipt_editor._delivery_location_entry.setText(delivery)
        except Exception as e:
            logger.debug("Could not auto-fill receipt from trip %s: %s", trip.get("id"), e)

    # ──────────────────────────────────────────────────────────────────────────
    #  Invoice actions
    # ──────────────────────────────────────────────────────────────────────────

    def _preview_invoice(self) -> None:
        """Preview the invoice using the embedded editor's generator."""
        if hasattr(self, "_full_invoice_editor") and self._full_invoice_editor is not None:
            self._full_invoice_editor._on_generate()

    # ──────────────────────────────────────────────────────────────────────────
    #  CMR generation
    # ──────────────────────────────────────────────────────────────────────────

    def _collect_cmr_data(self) -> dict[str, Any] | None:
        """Collect CMR form data from the embedded CMRFormView + language selections."""
        trip_id = self._trip_combo.currentData()
        if trip_id is None:
            return None
        trip = self._trip_svc.get_by_id(trip_id)
        if not trip:
            return None

        trip_data = dict(trip)
        trip_data["trip_id"] = trip_id

        # Get all form fields from the embedded CMRFormView
        if hasattr(self, "_cmr_form_view") and self._cmr_form_view is not None:
            form_data = self._cmr_form_view.get_data()
            trip_data.update(form_data)

        def _extract_lang(combo: StyledComboBox | None) -> str | None:
            if combo is None:
                return None
            val = combo.currentText()
            if not val:
                return None
            parts = val.split("(")
            if len(parts) > 1:
                return parts[-1].rstrip(")").strip()
            return val.strip()

        lang1 = _extract_lang(self._cmr_lang1_combo)
        lang2 = _extract_lang(self._cmr_lang2_combo)
        if lang1:
            trip_data["cmr_language"] = lang1
        if lang2:
            trip_data["cmr_language_secondary"] = lang2

        return trip_data

    def _generate_cmr(self) -> None:
        """Generate a single CMR document for the selected trip using the typed API.

        Delegates PDF generation to ``CMRGenerator.generate(CmrGenerateRequest, user_id)``
        and document registration to ``_cmr_doc_svc``.
        """
        if self._cmr_status_lbl is None:
            return
        trip_data = self._collect_cmr_data()
        if trip_data is None:
            QMessageBox.warning(
                self,
                t("generators.cmr_generate"),
                t("generators.cmr_select_trip"),
            )
            return
        self._cmr_progress_bar.setVisible(True)
        trip_id = trip_data["trip_id"]
        try:
            from services.invoicing.cmr_generator import CMRGenerator
            gen = CMRGenerator(db=self.db, prefs=self.prefs)

            # Build typed request — the generator handles output dir and numbering internally
            request = CmrGenerateRequest(
                trip_id=trip_id,
                language=trip_data.get("cmr_language", "ro"),
                copies=1,
                sender_name=trip_data.get("consignor_name", ""),
                sender_address=trip_data.get("consignor_address", ""),
                carrier_name=trip_data.get("carrier_name", ""),
                carrier_license=trip_data.get("carrier_license", ""),
                remarks=trip_data.get("carrier_instructions", ""),
            )
            # user_id=0 falls back gracefully when auth context is unavailable
            result = gen.generate(request, user_id=0)
            if not result.success:
                err_msg = result.errors[0].message if result.errors else "Unknown error"
                raise Exception(err_msg)
            filepath = result.data.file_path

        except Exception as e:
            self._cmr_progress_bar.setVisible(False)
            QMessageBox.critical(
                self,
                t("generators.cmr_generate"),
                t("generators.cmr_error").format(error=str(e)),
            )
            return

        try:
            self._cmr_doc_svc.register_existing(
                filepath,
                title=t("generators.cmr_trip_title", default="CMR Trip #{}").format(trip_id),
                category="trips",
                entity_type="trip",
                entity_id=trip_id,
                tags=["cmr", "generated"],
            )
        except Exception:
            logger.warning("CMR registration in Document Center skipped", exc_info=True)

        # Determine correct copy suffix based on generating role
        cmr_role = trip_data.get("generating_role", "consignor")
        copy_suffix = "Sender" if cmr_role == "consignor" else "Consignee"
        self._cmr_last_paths[copy_suffix] = filepath
        self._cmr_status_lbl.setText(
            t("generators.cmr_generated").format(path=os.path.basename(filepath))
        )
        self._cmr_status_lbl.setProperty("role", "success")
        self._cmr_status_lbl.style().unpolish(self._cmr_status_lbl)
        self._cmr_status_lbl.style().polish(self._cmr_status_lbl)
        self._update_copy_status(copy_suffix, filepath)
        self._cmr_progress_bar.setVisible(False)
        logger.info("CMR generated for trip %d: %s", trip_id, filepath)

    def _preview_cmr(self) -> None:
        """Generate a single CMR and show in an in-app preview modal."""
        if self._cmr_status_lbl is None:
            return
        trip_data = self._collect_cmr_data()
        if trip_data is None:
            QMessageBox.warning(
                self,
                t("generators.cmr_generate"),
                t("generators.cmr_select_trip"),
            )
            return

        self._cmr_progress_bar.setVisible(True)
        trip_id = trip_data["trip_id"]
        try:
            from services.invoicing.cmr_generator import CMRGenerator
            gen = CMRGenerator(db=self.db, prefs=self.prefs)

            request = CmrGenerateRequest(
                trip_id=trip_id,
                language=trip_data.get("cmr_language", "ro"),
                copies=1,
                sender_name=trip_data.get("consignor_name", ""),
                sender_address=trip_data.get("consignor_address", ""),
                carrier_name=trip_data.get("carrier_name", ""),
                carrier_license=trip_data.get("carrier_license", ""),
                remarks=trip_data.get("carrier_instructions", ""),
            )
            result = gen.generate(request, user_id=0)
            if not result.success:
                err_msg = result.errors[0].message if result.errors else "Unknown error"
                raise Exception(err_msg)
            filepath = result.data.file_path
        except Exception as e:
            self._cmr_progress_bar.setVisible(False)
            QMessageBox.critical(
                self,
                t("generators.cmr_generate"),
                t("generators.cmr_error").format(error=str(e)),
            )
            return

        self._cmr_progress_bar.setVisible(False)

        # Show in-app preview modal
        if filepath and os.path.isfile(filepath):
            self._preview_modal(filepath)

    def _preview_modal(self, filepath: str) -> None:
        """Show a preview dialog for a generated document.

        Falls back to a summary dialog with an Open button when PDF
        rendering is not available.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(t("cmr.preview", "Document Preview"))
        dialog.setFixedSize(480, 280)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(SP["8"], SP["6"], SP["8"], SP["6"])
        layout.setSpacing(SP["4"])
        layout.setAlignment(Qt.AlignCenter)

        # Icon
        icon_lbl = QLabel()
        pdf_icon = qta.icon("fa5s.file-pdf", color=COLOR_ACCENT_PRIMARY)
        icon_lbl.setPixmap(pdf_icon.pixmap(64, 64))
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        # Message
        msg_lbl = QLabel(t("generators.cmr_generated", "Document generated successfully"))
        msg_lbl.setAlignment(Qt.AlignCenter)
        msg_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_LG}px; font-weight: 600;"
        )
        layout.addWidget(msg_lbl)

        # File path
        path_lbl = QLabel(os.path.basename(filepath))
        path_lbl.setAlignment(Qt.AlignCenter)
        path_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; "
            f"font-family: '{FONT_MONO}'; font-size: {FONT_SIZE_SM}px;"
        )
        path_lbl.setWordWrap(True)
        layout.addWidget(path_lbl)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(SP["3"])
        btn_layout.addStretch()

        close_btn = Btn(dialog, t("common.close", "Close"), variant="ghost", command=dialog.close)
        close_btn.setFixedWidth(100)
        btn_layout.addWidget(close_btn)

        open_btn = Btn(
            dialog,
            t("generators.open_pdf", "Open in Viewer"),
            variant="primary",
            command=lambda: (
                os.startfile(os.path.abspath(filepath)),
                dialog.close(),
            ),
        )
        open_btn.setFixedWidth(140)
        btn_layout.addWidget(open_btn)

        layout.addLayout(btn_layout)

        dialog.exec()

    def _generate_all_copies(self) -> None:
        """Generate all CMR copies (Sender, Consignee, Carrier, Administrative).

        Uses the typed ``CMRGenerator.generate_all_copies(CmrGenerateRequest, user_id)``
        API — numbering, DB updates, and output directory creation are handled inside
        the generator. Background threading is kept here to keep the UI responsive;
        the generator itself remains synchronous.
        """
        if self._cmr_status_lbl is None:
            return
        trip_data = self._collect_cmr_data()
        if trip_data is None:
            QMessageBox.warning(
                self,
                t("generators.cmr_generate"),
                t("generators.cmr_select_trip"),
            )
            return
        trip_id = trip_data["trip_id"]

        self._cmr_progress_bar.setVisible(True)
        self._cmr_status_lbl.setText(
            t("generators.cmr_status_generating")
        )
        self._cmr_status_lbl.setProperty("role", "warning")
        self._cmr_status_lbl.style().unpolish(self._cmr_status_lbl)
        self._cmr_status_lbl.style().polish(self._cmr_status_lbl)

        from services.invoicing.cmr_generator import CMRGenerator
        gen = CMRGenerator(db=self.db, prefs=self.prefs)

        # Build typed request — numbering (cmr_number / cmr_seq) is handled
        # internally by the generator; no more direct _next_cmr_number() call.
        request = CmrGenerateRequest(
            trip_id=trip_id,
            language=trip_data.get("cmr_language", "ro"),
            copies=4,
            include_stamps=True,
            sender_name=trip_data.get("consignor_name", ""),
            sender_address=trip_data.get("consignor_address", ""),
            carrier_name=trip_data.get("carrier_name", ""),
            carrier_license=trip_data.get("carrier_license", ""),
            remarks=trip_data.get("carrier_instructions", ""),
        )

        def _run() -> None:
            registered_paths: dict[str, str] = {}
            try:
                # Typed API — handles permission check, trip lookup,
                # numbering, PDF generation, and DB update internally.
                result = gen.generate_all_copies(request, user_id=0)
                if not result.success:
                    err_msg = result.errors[0].message if result.errors else "Unknown error"
                    raise Exception(err_msg)

                cmr_number = result.data.cmr_number
                # Reconstruct per-copy paths from the known CMR naming convention
                # (mirrors CMRGenerator._build_single_copy).
                output_dir = os.path.join("data", "documents", "trips", str(trip_id))
                safe_num = cmr_number.replace("/", "_").replace("\\", "_").replace(" ", "_")
                for suffix in ["Sender", "Consignee", "Carrier", "Administrative"]:
                    path = os.path.join(output_dir, f"CMR_{safe_num}_{suffix}_Copy.pdf")
                    if os.path.isfile(path):
                        registered_paths[suffix] = path

            except Exception as e:
                err_msg = str(e)
                def _err() -> None:
                    if self._cmr_status_lbl is not None:
                        self._cmr_status_lbl.setText(
                            t("generators.cmr_error").format(error=err_msg)
                        )
                        self._cmr_status_lbl.setProperty("role", "danger")
                        self._cmr_status_lbl.style().unpolish(self._cmr_status_lbl)
                        self._cmr_status_lbl.style().polish(self._cmr_status_lbl)
                    if hasattr(self, "_cmr_progress_bar"):
                        self._cmr_progress_bar.setVisible(False)
                QTimer.singleShot(0, _err)
                logger.error("CMR generation failed: %s", err_msg)
                return

            def _register() -> None:
                if self._cmr_status_lbl is None:
                    return
                if not self.db:
                    logger.warning("CMR: no database reference, skipping registration")
                    return

                # DB update (cmr_number / cmr_seq) is done by the typed API
                # with skip_db_update=False inside generate_all_copies.

                # Register each copy with DocumentService
                try:
                    for suffix, path in registered_paths.items():
                        with contextlib.suppress(Exception):
                            self._cmr_doc_svc.register_existing(
                                path,
                                title=t("generators.cmr_copy_title",
                                        default="CMR Trip #{} - {} COPY").format(trip_id, suffix.upper()),
                                category="trips",
                                entity_type="trip",
                                entity_id=trip_id,
                                tags=["cmr", suffix.lower(), "generated"],
                            )
                except Exception:
                    pass

                self._cmr_last_paths.update(registered_paths)
                base = os.path.basename(next(iter(registered_paths.values()))) if registered_paths else ""
                self._cmr_status_lbl.setText(
                    t("generators.cmr_all_generated").format(path=base)
                )
                self._cmr_status_lbl.setProperty("role", "success")
                self._cmr_status_lbl.style().unpolish(self._cmr_status_lbl)
                self._cmr_status_lbl.style().polish(self._cmr_status_lbl)
                for suffix, path in registered_paths.items():
                    self._update_copy_status(suffix, path)
                if hasattr(self, "_cmr_progress_bar"):
                    self._cmr_progress_bar.setVisible(False)

            QTimer.singleShot(0, _register)

        threading.Thread(target=_run, daemon=True, name=f"cmr-gen-{trip_id}").start()

    def _update_copy_status(self, suffix: str, path: str) -> None:
        """Update the status label and enable the open button for a given copy."""
        if suffix in self._copy_labels:
            name_lbl, status_lbl, btn = self._copy_labels[suffix]
            suffix_key = _COPY_SUFFIX_KEYS[suffix]
            name_lbl.setText(t(suffix_key))
            status_lbl.setText(
                t("generators.cmr_generated_status", "generated")
            )
            status_lbl.setProperty("role", "success")
            status_lbl.style().unpolish(status_lbl)
            status_lbl.style().polish(status_lbl)
            btn.setEnabled(True)
            btn.clicked.disconnect()
            btn.clicked.connect(lambda checked=False, p=path: self._open_path(p))

    def _open_copy(self, suffix: str) -> None:
        """Open the last generated PDF for the given copy suffix."""
        if suffix in self._cmr_last_paths:
            path = self._cmr_last_paths[suffix]
            self._open_path(path)

    def _open_path(self, path: str) -> None:
        """Open a file with the OS default application."""
        if path and os.path.isfile(path):
            try:
                os.startfile(os.path.abspath(path))
            except Exception as e:
                logger.warning("Could not open %s: %s", path, e)

    # ──────────────────────────────────────────────────────────────────────────
    #  i18n
    # ──────────────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        """React to language change events from the i18n service."""
        QTimer.singleShot(0, self.refresh_translations)

    def refresh_translations(self) -> None:
        """Update all visible text to the current language."""
        # Static labels
        for widget, key in self._i18n_labels:
            with contextlib.suppress(Exception):
                widget.setText(t(key))

        # Buttons
        for widget, key in self._i18n_buttons:
            with contextlib.suppress(Exception):
                widget.setText(t(key))

        # Section header labels
        for text_key, lbl in self._i18n_sections.items():
            with contextlib.suppress(Exception):
                lbl.setText(t(text_key))

        # Tab titles
        self._refresh_tab_titles()

        # Trip combo items (they contain translated format strings)
        self._rebuild_trip_combo_labels()

        # Copy status rows show generated / not generated status
        gen_text = t("generators.cmr_generated_status", "generated")
        not_gen = t("generators.cmr_not_generated")
        for suffix, (name_lbl, status_lbl, btn) in self._copy_labels.items():
            suffix_key = _COPY_SUFFIX_KEYS.get(suffix, suffix)
            name_lbl.setText(t(suffix_key))
            if suffix not in self._cmr_last_paths:
                status_lbl.setText(not_gen)
                status_lbl.setProperty("role", "muted")
                status_lbl.style().unpolish(status_lbl)
                status_lbl.style().polish(status_lbl)
                btn.setEnabled(False)
            else:
                status_lbl.setText(gen_text)
                status_lbl.setProperty("role", "success")
                status_lbl.style().unpolish(status_lbl)
                status_lbl.style().polish(status_lbl)

    def _rebuild_trip_combo_labels(self) -> None:
        """Rebuild trip combo display labels when the language changes."""
        if not self._trips_list:
            return
        current_id = self._trip_combo.currentData()

        for trip in self._trips_list:
            vid = trip["id"]
            label = self._format_trip_label(trip)
            idx = self._trip_combo.findData(vid)
            if idx >= 0:
                self._trip_combo.setItemText(idx, label)

        # Restore selection by id
        if current_id is not None:
            idx = self._trip_combo.findData(current_id)
            if idx >= 0:
                self._trip_combo.setCurrentIndex(idx)

    # ──────────────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Called when the view becomes visible (e.g. stacked widget switch)."""
        if not getattr(self, "_listener_registered", False):
            register_listener(self._language_callback)
            self._listener_registered = True
        self._refresh_trip_lists()

    def handle_nav_data(self, data: dict[str, Any]) -> None:
        """Auto-select a trip from navigation data (e.g. alert click, quick document action).

        Supported data keys:
            ``trip_id`` (int) — pre-select this trip in the combo.
            ``tab`` (int) — switch to this tab index (0=Invoice, 1=CMR, 2=Receipt, 3=Proforma).
        """
        trip_id = data.get("trip_id")
        if trip_id:
            # Ensure trip list is loaded
            if not self._trips_list:
                self._refresh_trip_lists()
            # Find the item index for this trip_id
            idx = self._trip_combo.findData(int(trip_id))
            if idx >= 0:
                QTimer.singleShot(100, lambda i=idx: self._trip_combo.setCurrentIndex(i))

        tab_index = data.get("tab")
        if tab_index is not None and isinstance(tab_index, int) and 0 <= tab_index < self._tab_widget.count():
            QTimer.singleShot(150, lambda ti=tab_index: self._tab_widget.setCurrentIndex(ti))

    def shutdown(self) -> None:
        """Clean up resources when the view is destroyed / hidden."""
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)
        self._listener_registered = False
