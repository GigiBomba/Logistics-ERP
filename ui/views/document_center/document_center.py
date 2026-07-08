"""PySide6 document management view.

Replaces ``ui/views/document_center_view.py``.  Provides a three-panel layout
with category/filter sidebar, a scrollable document list with rich rows, and
a detail/preview panel with tag, expiry, version management.

Usage as embedded widget::

    doc_view = QtDocumentCenterView(parent_widget, db)
    some_layout.addWidget(doc_view)
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.document_service import IMAGE_MIME, DocumentService
from services.i18n import t
from ui.base_view import BaseView
from services.operations.event_bus import (
    DOCUMENT_OCR_RAN,
    DOCUMENT_UPLOADED,
    INVOICE_CREATED,
    PROFORMA_CREATED,
    RECEIPT_CREATED,
)
from ui.components import Btn, FieldLabel
from ui.theme import COLORS, S
from ui.widgets import (
    SectionHeader,
    StyledComboBox,
    StyledLineEdit,
)
from ui.widgets.debounced_line_edit import DebouncedLineEdit
from ui.widgets.layout_utils import clear_layout

from ui.views.document_center.document_actions import DocumentActionsMixin

logger = logging.getLogger(__name__)

PAGE_SIZE = 20


class _CategoryButton(QPushButton):
    """A flat category button in the sidebar."""

    def __init__(
        self,
        parent: QWidget,
        text: str,
        active: bool = False,
        command=None,
    ):
        super().__init__(text, parent)
        self.setProperty("category-btn", "true")
        self.setProperty("active", "true" if active else "false")
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if command:
            self.clicked.connect(command)


class _DocRow(QFrame):
    """A rich document row widget used inside the scrollable list."""

    def __init__(
        self,
        parent: QWidget,
        doc: dict,
        on_toggle_select: Callable[[int, bool], None],
        on_show_detail: Callable[[dict | None], None],
        on_open: Callable[[dict], None],
        on_email: Callable[[dict], None],
        on_delete: Callable[[dict], None],
        selected_ids: set,
        doc_service=None,
    ):
        super().__init__(parent)
        self._doc = doc
        self._doc_id = doc["id"]
        self._on_toggle_select = on_toggle_select
        self._on_show_detail = on_show_detail
        self._doc_service = doc_service

        self.setProperty("role", "doc-row")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(80)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(S["3"], S["2"], S["3"], S["2"])
        layout.setSpacing(S["2"])
        # ── Checkbox ──────────────────────────────────────────────────────
        self._cb = QCheckBox(self)
        self._cb.setChecked(self._doc_id in selected_ids)
        self._cb.stateChanged.connect(self._on_check_changed)
        layout.addWidget(self._cb)

        # ── Icon / thumbnail ──────────────────────────────────────────────
        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(96, 72)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setProperty("role", "doc-icon")
        thumb = self._get_thumbnail()
        if thumb:
            pm = QPixmap(thumb)
            if not pm.isNull():
                pm = pm.scaled(88, 66, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._icon_label.setPixmap(pm)
        if not self._icon_label.pixmap() or self._icon_label.pixmap().isNull():
            self._icon_label.setText(self._icon_for(doc.get("mime_type", "")))
        layout.addWidget(self._icon_label)

        # ── Info column ───────────────────────────────────────────────────
        info_col = QWidget(self)
        info_col.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        info_layout = QVBoxLayout(info_col)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        title_text = doc.get("title", doc.get("file_name", ""))[:70]
        title_lbl = QLabel(title_text, info_col)
        title_lbl.setProperty("fontRole", "body_bold")
        title_lbl.setProperty("role", "doc-title")
        info_layout.addWidget(title_lbl)

        meta_parts: list[str] = []
        doc_num = doc.get("doc_number", "")
        if doc_num:
            meta_parts.append(doc_num)
        size = doc.get("file_size", 0)
        if size < 1024:
            meta_parts.append(f"{size} B")
        elif size < 1024 * 1024:
            meta_parts.append(f"{size / 1024:.1f} KB")
        else:
            meta_parts.append(f"{size / (1024 * 1024):.1f} MB")
        upload = doc.get("uploaded_at", "")[:10]
        if upload:
            meta_parts.append(upload)
        # Show the linked trip ID if the document is associated with one.
        if doc.get("entity_type") == "trip" and doc.get("entity_id"):
            meta_parts.append(f"Trip #{doc['entity_id']}")
        meta_lbl = QLabel("  ".join(meta_parts), info_col)
        meta_lbl.setProperty("fontRole", "small")
        meta_lbl.setProperty("role", "doc-meta")
        info_layout.addWidget(meta_lbl)

        # Tags
        tags_str = doc.get("tags", "[]")
        try:
            tag_list = json.loads(tags_str)
        except (json.JSONDecodeError, TypeError):
            tag_list = []
        if tag_list:
            tag_row = QWidget(info_col)
            tag_row_layout = QHBoxLayout(tag_row)
            tag_row_layout.setContentsMargins(0, 0, 0, 0)
            tag_row_layout.setSpacing(2)
            for tg in tag_list[:4]:
                chip = QLabel(tg, tag_row)
                chip.setProperty("role", "tag-chip")
                tag_row_layout.addWidget(chip)
            tag_row_layout.addStretch()
            info_layout.addWidget(tag_row)

        layout.addWidget(info_col, 1)

        # ── Action buttons ────────────────────────────────────────────────
        actions = QWidget(self)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(2)

        view_btn = Btn(
            actions, text=t("docs.view"), command=lambda: on_open(doc),
            variant="secondary", size="md",
        )
        view_btn.setMinimumWidth(80)
        view_btn.setFixedHeight(32)
        view_btn.adjustSize()
        actions_layout.addWidget(view_btn)

        email_btn = Btn(
            actions, text=t("docs.email"), command=lambda: on_email(doc),
            variant="secondary", size="md",
        )
        email_btn.setMinimumWidth(80)
        email_btn.setFixedHeight(32)
        email_btn.adjustSize()
        actions_layout.addWidget(email_btn)

        del_btn = Btn(
            actions, text=t("docs.delete"), command=lambda: on_delete(doc),
            variant="ghost",
        )
        del_btn.setMinimumWidth(80)
        del_btn.setFixedHeight(32)
        del_btn.adjustSize()
        actions_layout.addWidget(del_btn)

        layout.addWidget(actions)

        # ── Click detail binding ──────────────────────────────────────────
        self.mousePressEvent = lambda e: on_show_detail(doc)
        title_lbl.mousePressEvent = lambda e: on_show_detail(doc)
        meta_lbl.mousePressEvent = lambda e: on_show_detail(doc)

    def _get_thumbnail(self) -> str | None:
        """Resolve the thumbnail path from the document service."""
        if self._doc_service is not None:
            try:
                return self._doc_service.get_thumbnail_path(self._doc_id)
            except Exception:
                pass
        return None

    @staticmethod
    def _icon_for(mime_type: str) -> str:
        if mime_type == "application/pdf":
            return "\U0001F4C4"
        if mime_type in IMAGE_MIME:
            return "\U0001F5BC"
        if "spreadsheet" in mime_type or mime_type == "text/csv":
            return "\U0001F4CA"
        if "word" in mime_type or mime_type == "text/plain":
            return "\U0001F4C3"
        if mime_type == "application/zip":
            return "\U0001F4E6"
        return "\U0001F4CE"

    def _on_check_changed(self, state: int) -> None:
        checked = state == Qt.Checked
        self._on_toggle_select(self._doc_id, checked)


class QtDocumentCenterView(BaseView, DocumentActionsMixin):
    """Document management view for embedding in a QStackedWidget.

    Three-panel layout:
        Left sidebar   — categories + filters
        Center list    — search, sort, document rows, pager
        Right sidebar  — detail preview + actions
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs: Any = None,
        ops: Any = None,
        document_service=None,
        api_client: Any = None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs
        self.ops = ops
        self._api_client = api_client
        self._service = document_service if document_service is not None else (DocumentService(db) if db is not None else None)
        self._page = 0
        self._total = 0
        self._total_pages = 0
        self._docs: list[dict[str, Any]] = []
        self._active_category: str = ""
        self._sort_order: str = "uploaded_at DESC"
        self._filters_visible = False
        self._selected_ids: set = set()
        self._current_detail_doc: dict[str, Any] | None = None
        self._thumbnail_service = self._service  # for resolving thumbnails
        self._automation_view: QWidget | None = None

        # ── Admin panel (Dual-Gate — injected at runtime, never at boot) ──
        self._admin_tab_injected: bool = False
        self._admin_panel_view: QWidget | None = None
        self._admin_tab_index: int = -1
        self._admin_auth_in_progress: bool = False

        # ── On-demand OCR worker (single-doc) ─────────────────────────────
        self._ocr_worker: Any | None = None
        self._ocr_busy: bool = False

        # ── i18n ──────────────────────────────────────────────────────────
        self._language_callback = self._on_language_changed
        self._register_i18n(self._language_callback)

        # ── Event bus subscriptions — auto-refresh when docs are added ───
        self._subscribe(DOCUMENT_UPLOADED, self._on_document_event)
        self._subscribe(INVOICE_CREATED, self._on_document_event)
        self._subscribe(PROFORMA_CREATED, self._on_document_event)
        self._subscribe(RECEIPT_CREATED, self._on_document_event)

        # ── Build UI ──────────────────────────────────────────────────────
        self._build_ui()

        # ── Cleanup hook ──────────────────────────────────────────────────
        self.destroyed.connect(self.shutdown)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Re-fetch categories and documents from the service."""
        if self._service is None:
            return
        self._load_categories()
        self._load_documents()

    def wakeup(self) -> None:
        """Called when the view becomes active (e.g. tab switch)."""
        self.refresh()

    def _on_document_event(self, _event_data=None) -> None:
        """Auto-refresh when a document is uploaded or invoice is created."""
        if not getattr(self, "_event_subscribed", False):
            return
        QTimer.singleShot(500, self._safe_refresh)

    def _safe_refresh(self) -> None:
        """Refresh without crashing on missing DB (e.g. during test setup)."""
        with contextlib.suppress(Exception):
            self.refresh()

    def shutdown(self) -> None:
        """Clean up listeners and resources."""
        self._stop_ocr_worker()
        if hasattr(self, "_api_dashboard_view") and self._api_dashboard_view is not None:
            if hasattr(self._api_dashboard_view, "shutdown"):
                with contextlib.suppress(Exception):
                    self._api_dashboard_view.shutdown()
        # Eject admin panel if it was injected
        self._eject_admin_tab()
        super().shutdown()

    def _stop_ocr_worker(self) -> None:
        """Cancel / discard the on-demand OCR worker if running."""
        worker = self._ocr_worker
        if worker is None:
            return
        try:
            worker.stop_event.set()
            worker.requestInterruption()
            if worker.isRunning():
                worker.wait(2000)
        except Exception:
            pass
        self._ocr_worker = None
        self._ocr_busy = False

    # ------------------------------------------------------------------
    # i18n
    # ------------------------------------------------------------------

    def _on_language_changed(self, _lang: str) -> None:
        """Rebuild translatable text when the language changes."""
        self._update_translations()
        if hasattr(self, "_refresh_tab_titles"):
            self._refresh_tab_titles()
        self.refresh()

    def _update_translations(self) -> None:
        """Update all visible translated labels."""
        # Sidebar
        self._sidebar_header.label.setText(t("docs.title"))
        self._filter_toggle.setText(t("docs.filters"))
        self._upload_btn.setText(f"  {t('docs.upload')}")

        # Center toolbar
        self._sort_combo.setItemText(0, t("docs.sort_newest"))
        self._sort_combo.setItemText(1, t("docs.sort_oldest"))
        self._sort_combo.setItemText(2, t("docs.sort_name_az"))
        self._sort_combo.setItemText(3, t("docs.sort_name_za"))
        self._sort_combo.setItemText(4, t("docs.sort_size_lg"))
        self._sort_combo.setItemText(5, t("docs.sort_size_sm"))
        self._search_entry.setPlaceholderText(t("docs.search_placeholder"))

        # Batch bar
        if hasattr(self, "_batch_zip_btn") and self._batch_zip_btn is not None:
            self._batch_zip_btn.setText(t("docs.download_zip"))
        if hasattr(self, "_batch_del_btn") and self._batch_del_btn is not None:
            self._batch_del_btn.setText(t("docs.batch_delete"))

        # Pager
        self._update_page_label()

        # Detail sidebar
        self._detail_header.label.setText(t("docs.details"))

        # Filter panel
        self._rebuild_filter_panel_if_visible()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the tabbed Document Center.

        Two sub-tabs:
            * **Documents** — the original three-panel layout
            * **Automation** — the Operion Document Automation
              pipeline (drop-zone + run list + detail panel)
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._tab_widget = QTabWidget()
        self._tab_widget.setProperty("role", "document-center-tabs")
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self._tab_widget, 1)

        # ── Tab 1: Documents (three-panel layout) ───────────────────────
        self._documents_page = QWidget()
        self._documents_layout = QHBoxLayout(self._documents_page)
        self._documents_layout.setContentsMargins(0, 0, 0, 0)
        self._documents_layout.setSpacing(0)
        # Column weights matching the original 20:50:30 ratio
        self._build_sidebar()
        self._documents_layout.addWidget(self._sidebar, 20)

        self._build_center()
        self._documents_layout.addWidget(self._center_panel, 50)

        self._build_detail_sidebar()
        self._documents_layout.addWidget(self._detail_panel, 30)
        self._tab_widget.addTab(self._documents_page, "")

        # ── Tab 2: Automation ───────────────────────────────────────────
        self._automation_page = QWidget()
        self._automation_layout = QVBoxLayout(self._automation_page)
        self._automation_layout.setContentsMargins(0, 0, 0, 0)
        self._automation_layout.setSpacing(0)
        self._automation_view = self._build_automation_view()
        if self._automation_view is not None:
            self._automation_layout.addWidget(self._automation_view, 1)
        self._tab_widget.addTab(self._automation_page, "")

        # ── Tab 3: API Dashboard ─────────────────────────────────────────
        self._api_dashboard_page = QWidget()
        self._api_dashboard_layout = QVBoxLayout(self._api_dashboard_page)
        self._api_dashboard_layout.setContentsMargins(0, 0, 0, 0)
        self._api_dashboard_layout.setSpacing(0)
        self._api_dashboard_view = None
        try:
            from ui.views.api_dashboard_view import QtApiDashboardView
            self._api_dashboard_view = QtApiDashboardView(
                self._api_dashboard_page,
                db=self.db,
                api_client=getattr(self, '_api_client', None),
            )
            self._api_dashboard_layout.addWidget(self._api_dashboard_view, 1)
        except Exception:
            logger.exception("Failed to construct QtApiDashboardView")
        self._tab_widget.addTab(self._api_dashboard_page, "")

        self._refresh_tab_titles()
        self.refresh()

    # ── Automation sub-tab ─────────────────────────────────────────────

    def _build_automation_view(self) -> QWidget | None:
        """Lazy import to avoid a hard dependency on the automation module.

        Returning ``None`` is fine — the tab still exists, just empty.
        """
        try:
            from ui.views.automation_view import QtAutomationView
        except Exception:
            logger.exception("Failed to import QtAutomationView")
            return None
        try:
            return QtAutomationView(
                self._automation_page,
                db=self.db,
                prefs=self.prefs,
                ops=self.ops,
                api_client=self._api_client,
            )
        except Exception:
            logger.exception("Failed to construct QtAutomationView")
            return None

    # ── Admin panel — conditional runtime injection (Dual-Gate) ───────

    def _try_inject_admin_tab(self) -> bool:
        """Conditionally inject the admin panel as a 4th tab.

        If the tab is already injected, returns ``True`` immediately.
        Otherwise, triggers the auth gate — if the user authenticates
        as admin, the tab is created and injected via ``addTab()``.

        Returns:
            ``True`` if the admin tab is available after this call.
        """
        if self._admin_tab_injected:
            return True

        if self._admin_auth_in_progress:
            return False

        self._admin_auth_in_progress = True
        try:
            from client.auth_manager import require_admin_async

            if not require_admin_async(self):
                return False

            # ── Build the admin panel page ─────────────────────────────
            self._admin_panel_page = QWidget()
            admin_layout = QVBoxLayout(self._admin_panel_page)
            admin_layout.setContentsMargins(0, 0, 0, 0)
            admin_layout.setSpacing(0)

            from ui.views.admin_panel_view import QtAdminPanelView
            self._admin_panel_view = QtAdminPanelView(
                self._admin_panel_page,
                db=self.db,
                api_client=getattr(self, "_api_client", None),
            )
            admin_layout.addWidget(self._admin_panel_view, 1)

            # Inject into QTabWidget — this is the ONLY time addTab is
            # called for the admin panel.
            self._tab_widget.addTab(self._admin_panel_page, "")
            self._admin_tab_index = self._tab_widget.count() - 1
            self._tab_widget.setTabText(
                self._admin_tab_index,
                t("admin.tab_title", default="Admin Panel"),
            )
            self._admin_tab_injected = True

            # Switch to the new tab
            self._tab_widget.setCurrentIndex(self._admin_tab_index)
            if hasattr(self._admin_panel_view, "wakeup"):
                self._admin_panel_view.wakeup()
            return True

        except Exception:
            logger.exception("Failed to inject admin tab")
            return False
        finally:
            self._admin_auth_in_progress = False

    def _eject_admin_tab(self) -> None:
        """Remove the admin tab from the QTabWidget (logout / expiry)."""
        if not self._admin_tab_injected:
            return
        try:
            if self._admin_tab_index >= 0:
                self._tab_widget.removeTab(self._admin_tab_index)
        except Exception:
            logger.exception("Failed to eject admin tab")
        self._admin_panel_view = None
        self._admin_panel_page = None
        self._admin_tab_index = -1
        self._admin_tab_injected = False

    # ── Admin trigger handler ─────────────────────────────────────────

    def _on_admin_trigger_clicked(self) -> None:
        """Handle the admin access button click.

        If admin tab is already injected → switch to it.
        If not → attempt auth and injection.
        """
        if self._admin_tab_injected:
            self._tab_widget.setCurrentIndex(self._admin_tab_index)
        else:
            if self._try_inject_admin_tab():
                if hasattr(self._admin_panel_view, "wakeup"):
                    self._admin_panel_view.wakeup()

    def _on_token_expired(self) -> None:
        """Handle token expiry — eject admin tab and clear auth state.

        Connected to ``auth_manager.clear_auth()`` in the main window or
        called from the ApiClient 401 handler chain.
        """
        self._eject_admin_tab()
        from client.auth_manager import clear_auth
        clear_auth()

    def _refresh_tab_titles(self) -> None:
        """Update QTabWidget tab labels from translation keys."""
        self._tab_widget.setTabText(
            0, t("docs.tab_documents", default="Documents")
        )
        self._tab_widget.setTabText(
            1, t("automation.tab_title", default="Automation")
        )
        self._tab_widget.setTabText(
            2, t("api.tab_title", default="API Dashboard")
        )
        # Admin tab (index 3) — only update if injected
        if self._admin_tab_injected and self._admin_tab_index >= 0:
            self._tab_widget.setTabText(
                self._admin_tab_index,
                t("admin.tab_title", default="Admin Panel"),
            )

    def _on_tab_changed(self, index: int) -> None:
        """Forward tab changes to the embedded views' ``wakeup`` hooks."""
        if index == 1 and self._automation_view is not None:
            try:
                if hasattr(self._automation_view, "wakeup"):
                    self._automation_view.wakeup()
                if hasattr(self._automation_view, "_refresh_from_db"):
                    self._automation_view._refresh_from_db()
            except Exception:
                logger.exception("Failed to wake automation view")
        elif index == 2 and self._api_dashboard_view is not None:
            try:
                if hasattr(self._api_dashboard_view, "wakeup"):
                    self._api_dashboard_view.wakeup()
            except Exception:
                logger.exception("Failed to wake API dashboard view")
        elif (
            self._admin_tab_injected
            and index == self._admin_tab_index
            and self._admin_panel_view is not None
        ):
            try:
                if hasattr(self._admin_panel_view, "wakeup"):
                    self._admin_panel_view.wakeup()
            except Exception:
                logger.exception("Failed to wake admin panel view")

    # ── Left sidebar ───────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        self._sidebar = QWidget(self)
        self._sidebar.setProperty("role", "sidebar")
        layout = QVBoxLayout(self._sidebar)
        layout.setContentsMargins(S["3"], S["4"], S["3"], S["4"])
        layout.setSpacing(S["2"])

        # Header
        self._sidebar_header = SectionHeader(self._sidebar, t("docs.title"))
        layout.addWidget(self._sidebar_header)

        # Category frame
        self._cat_frame = QWidget(self._sidebar)
        self._cat_layout = QVBoxLayout(self._cat_frame)
        self._cat_layout.setContentsMargins(0, 0, 0, 0)
        self._cat_layout.setSpacing(1)
        layout.addWidget(self._cat_frame)

        # Filter toggle
        self._filter_toggle = Btn(self._sidebar, t("docs.filters"), variant="ghost")
        self._filter_toggle.setProperty("role", "filter-toggle")
        self._filter_toggle.setCursor(Qt.PointingHandCursor)
        self._filter_toggle.clicked.connect(self._toggle_filters)
        layout.addWidget(self._filter_toggle)

        # Filter panel (hidden initially)
        self._filter_panel = QWidget(self._sidebar)
        self._filter_panel_layout = QVBoxLayout(self._filter_panel)
        self._filter_panel_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_panel_layout.setSpacing(S["2"])
        self._filter_panel.setVisible(False)
        layout.addWidget(self._filter_panel)

        layout.addStretch()

        # Upload button
        self._upload_btn = Btn(
            self._sidebar,
            text=f"  {t('docs.upload')}",
            command=self._upload_dialog,
            variant="primary",
        )
        layout.addWidget(self._upload_btn)

    def _toggle_filters(self) -> None:
        self._filters_visible = not self._filters_visible
        self._filter_panel.setVisible(self._filters_visible)
        if self._filters_visible:
            self._populate_filter_panel()

    def _populate_filter_panel(self) -> None:
        # Clear existing filter widgets
        clear_layout(self._filter_panel_layout)

        # Entity type
        entity_lbl = FieldLabel(self._filter_panel, t("docs.filter_entity"))
        self._filter_panel_layout.addWidget(entity_lbl)

        etypes = [""] + (self._service.get_entity_types() if self._service else [])
        self._entity_type_combo = StyledComboBox(
            self._filter_panel, values=etypes,
        )
        self._entity_type_combo.currentTextChanged.connect(
            lambda _: self._apply_filters()
        )
        self._filter_panel_layout.addWidget(self._entity_type_combo)

        # Date from
        df_lbl = FieldLabel(self._filter_panel, t("docs.filter_date_from"))
        self._filter_panel_layout.addWidget(df_lbl)

        self._date_from_entry = StyledLineEdit(
            self._filter_panel, placeholder="YYYY-MM-DD",
        )
        self._filter_panel_layout.addWidget(self._date_from_entry)

        # Date to
        dt_lbl = FieldLabel(self._filter_panel, t("docs.filter_date_to"))
        self._filter_panel_layout.addWidget(dt_lbl)

        self._date_to_entry = StyledLineEdit(
            self._filter_panel, placeholder="YYYY-MM-DD",
        )
        self._filter_panel_layout.addWidget(self._date_to_entry)

        # Mime type
        mt_lbl = FieldLabel(self._filter_panel, t("docs.filter_type"))
        self._filter_panel_layout.addWidget(mt_lbl)

        mtypes = [""] + [
            m.split("/")[-1] if "/" in m else m
            for m in (self._service.get_mime_types() if self._service else [])
        ]
        self._mime_type_combo = StyledComboBox(
            self._filter_panel, values=mtypes,
        )
        self._mime_type_combo.currentTextChanged.connect(
            lambda _: self._apply_filters()
        )
        self._filter_panel_layout.addWidget(self._mime_type_combo)

        # Apply / Clear buttons
        btn_row = QWidget(self._filter_panel)
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(S["2"])

        apply_btn = Btn(
            btn_row, text=t("docs.filter_apply"), command=self._apply_filters,
            variant="primary",
        )
        btn_row_layout.addWidget(apply_btn)

        clear_btn = Btn(
            btn_row, text=t("docs.filter_clear"), command=self._clear_filters,
            variant="ghost",
        )
        btn_row_layout.addWidget(clear_btn)

        self._filter_panel_layout.addWidget(btn_row)

    def _rebuild_filter_panel_if_visible(self) -> None:
        if self._filters_visible:
            self._populate_filter_panel()

    def _build_category_tree(self, categories: list[dict[str, Any]]) -> None:
        clear_layout(self._cat_layout)

        total_count = sum(r["cnt"] for r in categories) if categories else 0
        all_btn = _CategoryButton(
            self._cat_frame,
            text=f"  {t('docs.cat_all')}  ({total_count})",
            active=(self._active_category == ""),
            command=lambda: self._filter_category(""),
        )
        self._cat_layout.addWidget(all_btn)

        cat_labels: dict[str, str] = {
            "maintenance": t("docs.cat_maintenance"),
            "invoices": t("docs.cat_invoices"),
            "proformas": t("docs.cat_proformas"),
            "receipts": t("docs.cat_receipts"),
            "trips": t("docs.cat_trips"),
            "drivers": t("docs.cat_drivers"),
            "vehicles": t("docs.cat_vehicles"),
            "other": t("docs.cat_other"),
        }
        cat_counts = {r["category"]: r["cnt"] for r in categories}
        for cat_key in ["maintenance", "invoices", "proformas", "receipts", "trips", "drivers", "vehicles", "other"]:
            count = cat_counts.get(cat_key, 0)
            label = cat_labels.get(cat_key, cat_key)
            active = self._active_category == cat_key
            btn = _CategoryButton(
                self._cat_frame,
                text=f"  {label}  ({count})",
                active=active,
                command=lambda c=cat_key: self._filter_category(c),
            )
            self._cat_layout.addWidget(btn)

    # ── Center list area ──────────────────────────────────────────────

    def _build_center(self) -> None:
        self._center_panel = QWidget(self)
        self._center_panel.setProperty("role", "center-panel")
        layout = QVBoxLayout(self._center_panel)
        layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        layout.setSpacing(S["2"])

        # ── Toolbar ───────────────────────────────────────────────────────
        toolbar = QWidget(self._center_panel)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(S["3"])

        # Sort combo
        sort_vals = [
            t("docs.sort_newest"), t("docs.sort_oldest"),
            t("docs.sort_name_az"), t("docs.sort_name_za"),
            t("docs.sort_size_lg"), t("docs.sort_size_sm"),
        ]
        self._sort_combo = StyledComboBox(toolbar, values=sort_vals)
        self._sort_combo.setCurrentIndex(0)
        self._sort_combo.currentTextChanged.connect(self._on_sort_change)
        toolbar_layout.addWidget(self._sort_combo)

        # Search entry
        self._search_entry = DebouncedLineEdit(
            toolbar, placeholder=t("docs.search_placeholder"),
        )
        self._search_entry.debouncedTextChanged.connect(self._on_search)
        toolbar_layout.addWidget(self._search_entry, 1)

        # Select all
        self._select_all_cb = QCheckBox(toolbar)
        self._select_all_cb.stateChanged.connect(self._toggle_select_all)
        toolbar_layout.addWidget(self._select_all_cb)

        # Admin access trigger (small shield icon; expands on click)
        self._admin_trigger = Btn(
            toolbar, text=t("admin.login_button", default="Admin"),
            command=self._on_admin_trigger_clicked, variant="ghost",
        )
        self._admin_trigger.setFixedWidth(60)
        self._admin_trigger.setFixedHeight(28)
        toolbar_layout.addWidget(self._admin_trigger)

        layout.addWidget(toolbar)

        # ── Batch bar ─────────────────────────────────────────────────────
        self._batch_bar = QWidget(self._center_panel)
        self._batch_bar.setVisible(False)
        batch_layout = QHBoxLayout(self._batch_bar)
        batch_layout.setContentsMargins(0, 0, 0, 0)
        batch_layout.setSpacing(S["2"])

        self._batch_zip_btn = Btn(
            self._batch_bar, text=t("docs.download_zip"),
            command=self._download_zip_selected, variant="secondary",
        )
        batch_layout.addWidget(self._batch_zip_btn)

        self._batch_del_btn = Btn(
            self._batch_bar, text=t("docs.batch_delete"),
            command=self._batch_delete_selected, variant="danger",
        )
        batch_layout.addWidget(self._batch_del_btn)

        batch_layout.addStretch()
        layout.addWidget(self._batch_bar)

        # ── Document list (scroll area) ───────────────────────────────────
        self._list_scroll = QScrollArea(self._center_panel)
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QFrame.NoFrame)
        self._list_scroll.setProperty("role", "doc-list-scroll")

        self._list_content = QWidget(self._list_scroll)
        self._list_layout = QVBoxLayout(self._list_content)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(S["2"])
        self._list_layout.setAlignment(Qt.AlignTop)
        self._list_scroll.setWidget(self._list_content)

        layout.addWidget(self._list_scroll, 1)

        # ── Pager ─────────────────────────────────────────────────────────
        pager = QWidget(self._center_panel)
        pager_layout = QHBoxLayout(pager)
        pager_layout.setContentsMargins(0, 0, 0, 0)

        self._page_label = QLabel("", pager)
        self._page_label.setProperty("fontRole", "small")
        self._page_label.setProperty("role", "page-label")
        pager_layout.addWidget(self._page_label)

        pager_layout.addStretch()

        self._prev_btn = Btn(
            pager, text=t("docs.prev"), command=self._prev_page,
            variant="secondary",
        )
        pager_layout.addWidget(self._prev_btn)

        self._next_btn = Btn(
            pager, text=t("docs.next"), command=self._next_page,
            variant="secondary",
        )
        pager_layout.addWidget(self._next_btn)

        layout.addWidget(pager)

    # ── Detail sidebar ────────────────────────────────────────────────

    def _build_detail_sidebar(self) -> None:
        self._detail_panel = QWidget(self)
        self._detail_panel.setProperty("role", "detail-sidebar")
        layout = QVBoxLayout(self._detail_panel)
        layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        layout.setSpacing(S["2"])

        # Header
        self._detail_header = SectionHeader(self._detail_panel, t("docs.details"))
        layout.addWidget(self._detail_header)

        # Detail content (scrollable)
        self._detail_scroll = QScrollArea(self._detail_panel)
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setFrameShape(QFrame.NoFrame)

        self._detail_content = QWidget(self._detail_scroll)
        self._detail_content_layout = QVBoxLayout(self._detail_content)
        self._detail_content_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_content_layout.setSpacing(S["2"])
        self._detail_content_layout.setAlignment(Qt.AlignTop)
        self._detail_scroll.setWidget(self._detail_content)

        layout.addWidget(self._detail_scroll, 1)

        # Action buttons at bottom
        self._detail_actions = QWidget(self._detail_panel)
        self._detail_actions_layout = QVBoxLayout(self._detail_actions)
        self._detail_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_actions_layout.setSpacing(S["2"])
        layout.addWidget(self._detail_actions)

        self._show_detail(None)

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _load_categories(self) -> None:
        if self._service is None:
            return
        categories = self._service.get_categories()
        self._build_category_tree(categories)

    def _load_documents(self) -> None:
        if self._service is None:
            return
        clear_layout(self._list_layout)

        query = self._search_entry.text().strip()
        date_from = self._date_from_entry.text().strip() if (
            self._filters_visible and hasattr(self, "_date_from_entry")
        ) else ""
        date_to = self._date_to_entry.text().strip() if (
            self._filters_visible and hasattr(self, "_date_to_entry")
        ) else ""
        entity_type = self._entity_type_combo.currentText().strip() if (
            self._filters_visible and hasattr(self, "_entity_type_combo")
        ) else ""
        mime_filter = self._mime_type_combo.currentText().strip() if (
            self._filters_visible and hasattr(self, "_mime_type_combo")
        ) else ""

        try:
            if query:
                result = self._service.fts_search(
                    query=query, category=self._active_category,
                    entity_type=entity_type, order=self._sort_order,
                    page=self._page, page_size=PAGE_SIZE,
                )
            else:
                result = self._service.advanced_search(
                    query=query, category=self._active_category,
                    entity_type=entity_type, date_from=date_from, date_to=date_to,
                    mime_type=mime_filter, order=self._sort_order,
                    page=self._page, page_size=PAGE_SIZE,
                )
        except Exception:
            logger.exception("Document search failed")
            result = {"items": [], "total": 0, "total_pages": 0}

        self._docs = result["items"]
        self._total = result["total"]
        self._total_pages = result["total_pages"]
        self._update_page_label()

        # Show/hide batch bar
        self._batch_bar.setVisible(bool(self._selected_ids))

        if not self._docs:
            empty_lbl = QLabel(t("docs.no_documents"), self._list_content)
            empty_lbl.setProperty("fontRole", "body")
            empty_lbl.setProperty("role", "empty-label")
            empty_lbl.setAlignment(Qt.AlignCenter)
            self._list_layout.addWidget(empty_lbl, 0, Qt.AlignCenter)
            self._show_detail(None)
            return

        for doc in self._docs:
            row = _DocRow(
                self._list_content,
                doc,
                on_toggle_select=self._toggle_select,
                on_show_detail=self._show_detail,
                on_open=self._open_document,
                on_email=self._email_document,
                on_delete=self._delete_document,
                selected_ids=self._selected_ids,
                doc_service=self._service,
            )
            self._list_layout.addWidget(row)

        # Add stretcher to keep rows top-aligned
        self._list_layout.addStretch(1)

    # ------------------------------------------------------------------
    # Filter actions
    # ------------------------------------------------------------------

    def _apply_filters(self) -> None:
        self._page = 0
        self._selected_ids.clear()
        self._load_documents()

    def _clear_filters(self) -> None:
        if hasattr(self, "_entity_type_combo"):
            self._entity_type_combo.setCurrentIndex(0)
        if hasattr(self, "_date_from_entry"):
            self._date_from_entry.clear()
        if hasattr(self, "_date_to_entry"):
            self._date_to_entry.clear()
        if hasattr(self, "_mime_type_combo"):
            self._mime_type_combo.setCurrentIndex(0)
        self._apply_filters()

    def _filter_category(self, category: str) -> None:
        self._active_category = category
        self._page = 0
        self._selected_ids.clear()
        self.refresh()

    def _on_search(self) -> None:
        self._page = 0
        self._selected_ids.clear()
        self._load_documents()

    def _on_sort_change(self, choice: str) -> None:
        sort_map = {
            t("docs.sort_newest"): "uploaded_at DESC",
            t("docs.sort_oldest"): "uploaded_at ASC",
            t("docs.sort_name_az"): "title ASC",
            t("docs.sort_name_za"): "title DESC",
            t("docs.sort_size_lg"): "file_size DESC",
            t("docs.sort_size_sm"): "file_size ASC",
        }
        self._sort_order = sort_map.get(choice, "uploaded_at DESC")
        self._page = 0
        self._selected_ids.clear()
        self._load_documents()

    # ------------------------------------------------------------------
    # Paging
    # ------------------------------------------------------------------

    def _prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._selected_ids.clear()
            self._load_documents()

    def _next_page(self) -> None:
        if self._page < self._total_pages - 1:
            self._page += 1
            self._selected_ids.clear()
            self._load_documents()

    def _update_page_label(self) -> None:
        self._page_label.setText(
            f"{self._page + 1} / {max(1, self._total_pages)}  ({self._total})"
        )

    # ------------------------------------------------------------------
    # Detail panel
    # ------------------------------------------------------------------

    def _show_detail(self, doc: dict[str, Any] | None) -> None:
        self._current_detail_doc = doc
        clear_layout(self._detail_content_layout)
        clear_layout(self._detail_actions_layout)

        if doc is None:
            select_lbl = QLabel(t("docs.select_document"), self._detail_content)
            select_lbl.setProperty("fontRole", "small")
            select_lbl.setProperty("role", "detail-placeholder")
            select_lbl.setWordWrap(True)
            self._detail_content_layout.addWidget(select_lbl)
            return

        c = self._detail_content
        cl = self._detail_content_layout

        # Title
        title = doc.get("title", doc.get("file_name", ""))
        title_lbl = QLabel(title, c)
        title_lbl.setProperty("fontRole", "body_bold")
        title_lbl.setWordWrap(True)
        cl.addWidget(title_lbl)

        # Document number
        doc_num = doc.get("doc_number", "")
        if doc_num:
            num_lbl = QLabel(doc_num, c)
            num_lbl.setProperty("fontRole", "mono")
            cl.addWidget(num_lbl)

        # Size + mime
        size = doc.get("file_size", 0)
        if size < 1024:
            sz = f"{size} B"
        elif size < 1024 * 1024:
            sz = f"{size / 1024:.1f} KB"
        else:
            sz = f"{size / (1024 * 1024):.1f} MB"
        size_lbl = QLabel(f"{sz} | {doc.get('mime_type', '')}", c)
        size_lbl.setProperty("fontRole", "small")
        size_lbl.setWordWrap(True)
        cl.addWidget(size_lbl)

        # ── Tags ──────────────────────────────────────────────────────────
        tags_header = QLabel(t("docs.tags_label"), c)
        tags_header.setProperty("fontRole", "label")
        cl.addWidget(tags_header)

        tag_frame = QWidget(c)
        tag_frame_layout = QHBoxLayout(tag_frame)
        tag_frame_layout.setContentsMargins(0, 0, 0, 0)
        tag_frame_layout.setSpacing(3)

        tags_str = doc.get("tags", "[]")
        try:
            tag_list = json.loads(tags_str)
        except (json.JSONDecodeError, TypeError):
            tag_list = []

        for tg in tag_list:
            chip = QLabel(tg, tag_frame)
            chip.setProperty("role", "tag-chip")
            chip.setProperty("removable", "true")
            chip.mousePressEvent = lambda e, t=tg, d=doc: self._remove_tag(d["id"], t)
            tag_frame_layout.addWidget(chip)

        tag_frame_layout.addStretch()
        cl.addWidget(tag_frame)

        # Add tag entry
        add_tag_row = QWidget(c)
        add_tag_layout = QHBoxLayout(add_tag_row)
        add_tag_layout.setContentsMargins(0, 0, 0, 0)
        add_tag_layout.setSpacing(S["2"])

        self._tag_entry = StyledLineEdit(add_tag_row, placeholder=t("docs.add_tag"))
        add_tag_layout.addWidget(self._tag_entry, 1)

        add_tag_btn = Btn(
            add_tag_row, text="+",
            command=lambda: self._add_tag_action(doc["id"]),
            variant="ghost",
        )
        add_tag_btn.setFixedWidth(24)
        add_tag_layout.addWidget(add_tag_btn)

        cl.addWidget(add_tag_row)

        # ── Linked entities ───────────────────────────────────────────────
        links = self._service.get_links(doc["id"]) if self._service else []
        if links:
            links_header = QLabel(t("docs.linked_to"), c)
            links_header.setProperty("fontRole", "label")
            cl.addWidget(links_header)
            for lk in links:
                lk_lbl = QLabel(
                    f"  {lk['linked_entity_type']} #{lk['linked_entity_id']}",
                    c,
                )
                lk_lbl.setProperty("fontRole", "small")
                cl.addWidget(lk_lbl)

        # ── Expiry date ───────────────────────────────────────────────────
        expiry = doc.get("expiry_date", "")
        exp_header = QLabel(t("docs.expiry_label"), c)
        exp_header.setProperty("fontRole", "label")
        cl.addWidget(exp_header)

        exp_row = QWidget(c)
        exp_layout = QHBoxLayout(exp_row)
        exp_layout.setContentsMargins(0, 0, 0, 0)
        exp_layout.setSpacing(S["2"])

        self._expiry_entry = StyledLineEdit(
            exp_row, text=expiry, placeholder="YYYY-MM-DD",
        )
        exp_layout.addWidget(self._expiry_entry, 1)

        set_exp_btn = Btn(
            exp_row, text=t("docs.set_expiry"),
            command=lambda: self._set_expiry(doc["id"]),
            variant="secondary",
        )
        exp_layout.addWidget(set_exp_btn)

        cl.addWidget(exp_row)

        # ── Versions ──────────────────────────────────────────────────────
        versions = self._service.get_versions(doc["id"]) if self._service else []
        if versions:
            ver_header = QLabel(t("docs.versions_label"), c)
            ver_header.setProperty("fontRole", "label")
            cl.addWidget(ver_header)
            for v in versions[:5]:
                vframe = QWidget(c)
                vlayout = QHBoxLayout(vframe)
                vlayout.setContentsMargins(0, 0, 0, 0)
                vlayout.setSpacing(S["2"])

                vtext = (
                    f"v{v['version_number']}: "
                    f"{v.get('comment', v['created_at'][:10])}"
                )
                v_lbl = QLabel(vtext, vframe)
                v_lbl.setProperty("fontRole", "small")
                vlayout.addWidget(v_lbl, 1)

                restore_btn = Btn(
                    vframe, text=t("docs.restore"), variant="ghost",
                    command=lambda _, d=doc, vn=v["version_number"]: self._restore_version(d["id"], vn),
                )
                vlayout.addWidget(restore_btn)

                cl.addWidget(vframe)

        # Upload version button
        upload_ver_btn = Btn(
            c, text=t("docs.upload_version"), variant="secondary",
            command=lambda _, d=doc: self._upload_version_dialog(d["id"]),
        )
        cl.addWidget(upload_ver_btn)

        # ── OCR status + on-demand re-run ─────────────────────────────────
        ocr_header = QLabel(t("docs.ocr_section", default="OCR"), c)
        ocr_header.setProperty("fontRole", "label")
        cl.addWidget(ocr_header)

        ocr_run_at = doc.get("ocr_run_at", "") or ""
        ocr_engine = doc.get("ocr_engine", "") or ""
        doc.get("ocr_text", "") or ""
        extracted_raw = doc.get("extracted_data_json", "") or "{}"
        try:
            extracted = json.loads(extracted_raw) if extracted_raw else {}
        except (json.JSONDecodeError, TypeError):
            extracted = {}

        if ocr_run_at:
            status_line = QLabel(
                f"  {t('docs.ocr_last_run', default='Last run')}: "
                f"{ocr_run_at}   ({ocr_engine or '?'})",
                c,
            )
            status_line.setProperty("fontRole", "small")
            status_line.setWordWrap(True)
            cl.addWidget(status_line)
        else:
            none_lbl = QLabel(
                f"  {t('docs.ocr_not_run', default='OCR has not been run on this document yet.')}",
                c,
            )
            none_lbl.setProperty("fontRole", "small")
            none_lbl.setProperty("role", "detail-placeholder")
            none_lbl.setWordWrap(True)
            cl.addWidget(none_lbl)

        if extracted:
            extracted_keys = ", ".join(sorted(extracted.keys()))[:120]
            extracted_lbl = QLabel(
                f"  {t('docs.ocr_fields', default='Extracted')}: {extracted_keys}",
                c,
            )
            extracted_lbl.setProperty("fontRole", "small")
            extracted_lbl.setWordWrap(True)
            cl.addWidget(extracted_lbl)

        rerun_btn = Btn(
            c,
            text=t("docs.rerun_ocr", default="Re-run OCR"),
            variant="secondary",
            command=lambda _, d=doc: self._on_rerun_ocr_clicked(d),
        )
        if self._ocr_busy:
            rerun_btn.setEnabled(False)
        cl.addWidget(rerun_btn)

        # ── Link to trip (explicit click; never auto-attached) ────────────
        link_btn = Btn(
            c,
            text=t("docs.link_to_trip", default="Link to trip…"),
            variant="ghost",
            command=lambda _, d=doc: self._on_link_to_trip_clicked(d),
        )
        cl.addWidget(link_btn)

        # ── Bottom action buttons ─────────────────────────────────────────
        act = self._detail_actions
        al = self._detail_actions_layout

        view_btn = Btn(
            act, text=t("docs.view"), command=lambda: self._open_document(doc),
            variant="primary",
        )
        al.addWidget(view_btn)

        dl_btn = Btn(
            act, text=t("docs.download_zip"), variant="secondary",
            command=lambda: self._download_single_zip(doc),
        )
        al.addWidget(dl_btn)

        email_btn = Btn(
            act, text=t("docs.email"), variant="secondary",
            command=lambda: self._email_document(doc),
        )
        al.addWidget(email_btn)

        archive_btn = Btn(
            act, text=t("docs.archive"), variant="ghost",
            command=lambda: self._archive_document(doc),
        )
        al.addWidget(archive_btn)

    def _add_tag_action(self, doc_id: int) -> None:
        tag = self._tag_entry.text().strip() if hasattr(self, "_tag_entry") else ""
        if tag and self._service:
            self._service.add_tag(doc_id, tag)
            self._tag_entry.clear()
            self._refresh_detail(doc_id)

    def _remove_tag(self, doc_id: int, tag: str) -> None:
        if self._service:
            self._service.remove_tag(doc_id, tag)
            self._refresh_detail(doc_id)

    def _set_expiry(self, doc_id: int) -> None:
        date = self._expiry_entry.text().strip() if hasattr(self, "_expiry_entry") else ""
        if date and self._service:
            self._service.set_expiry_date(doc_id, date)
            self._show_toast(t("docs.expiry_saved") if callable(t) else "Expiry date saved")
            self._refresh_detail(doc_id)

    def _restore_version(self, doc_id: int, version_number: int) -> None:
        reply = QMessageBox.question(
            self,
            t("docs.confirm_restore"),
            t("docs.confirm_restore_msg").format(v=version_number),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes and self._service:
            self._service.restore_version(doc_id, version_number)
            self._show_toast(f"Restored version {version_number}")
            self._refresh_detail(doc_id)

    def _upload_version_dialog(self, doc_id: int) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("docs.upload_version"),
            "",
            "All Supported (*.pdf *.png *.jpg *.jpeg *.docx *.xlsx *.csv *.txt *.zip);;All Files (*.*)",
        )
        if not path:
            return
        comment, ok = QInputDialog.getText(
            self, t("docs.upload_version"), t("docs.version_comment"),
        )
        if not ok:
            comment = ""
        try:
            if self._service:
                self._service.upload_new_version(doc_id, path, comment or "", "user")
                self._show_toast(t("docs.version_uploaded") if callable(t) else "New version uploaded")
        except Exception as e:
            QMessageBox.critical(self, t("docs.version_error"), str(e))
        self._refresh_detail(doc_id)

    def _refresh_detail(self, doc_id: int) -> None:
        if self._service is None:
            return
        doc = self._service.get_by_id(doc_id)
        if doc:
            self._show_detail(doc)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _toggle_select(self, doc_id: int, checked: bool) -> None:
        if checked:
            self._selected_ids.add(doc_id)
        else:
            self._selected_ids.discard(doc_id)
        self._batch_bar.setVisible(bool(self._selected_ids))

    def _toggle_select_all(self) -> None:
        if self._select_all_cb.isChecked():
            self._selected_ids = {d["id"] for d in self._docs}
        else:
            self._selected_ids.clear()
        self._load_documents()
        self._batch_bar.setVisible(bool(self._selected_ids))

    # ------------------------------------------------------------------
    # Toast
    # ------------------------------------------------------------------

    def _show_toast(self, msg: str) -> None:
        """Show a temporary toast notification."""
        try:
            from ui.widgets.toast import Toast

            Toast.show_success(self, msg, anchor=self)
        except ImportError:
            logger.info("Toast widget unavailable; message: %s", msg)


# ──────────────────────────────────────────────────────────────────────────────
# Standalone document dialog opener
# ──────────────────────────────────────────────────────────────────────────────

def open_entity_documents(parent: QWidget, db, entity_type: str, entity_id: int, title: str = ""):
    """Open a modal dialog showing documents linked to an entity.

    This is the PySide6 equivalent of the CTk ``open_entity_documents`` helper.
    It creates a QDialog with a document list, upload button, and view/unlink
    actions per row.

    Args:
        parent:  The parent QWidget for the dialog.
        db:      The database instance.
        entity_type: "trip", "truck", "driver", etc.
        entity_id:   Primary key of the entity.
        title:   Optional display title for the dialog header.
    """

    service = DocumentService(db)

    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Documents — {title}" if title else "Entity Documents")
    dlg.setMinimumSize(650, 500)
    dlg.setStyleSheet(
        f"QDialog {{ background-color: {COLORS['bg_base']}; }}"
        f"QLabel {{ color: {COLORS['text_primary']}; }}"
    )

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(S["5"], S["5"], S["5"], S["5"])
    layout.setSpacing(S["3"])

    # ── Header ────────────────────────────────────────────────────────────
    header = QFrame()
    header.setStyleSheet("QFrame { background: transparent; }")
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 0)

    count_label = QLabel(f"{title} (0 docs)")
    count_label.setProperty("fontRole", "h3")
    header_layout.addWidget(count_label, 1)

    upload_btn = Btn(dlg, t("docs.upload"), variant="primary")
    header_layout.addWidget(upload_btn)
    layout.addWidget(header)

    # ── Scrollable list area ───────────────────────────────────────────────
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setStyleSheet(
        f"QScrollArea {{ background-color: {COLORS['bg_base']}; border: none; }}"
    )
    list_container = QWidget()
    list_container.setStyleSheet(f"QWidget {{ background-color: {COLORS['bg_base']}; }}")
    list_layout = QVBoxLayout(list_container)
    list_layout.setContentsMargins(0, 0, 0, 0)
    list_layout.setSpacing(S["2"])
    list_layout.setAlignment(Qt.AlignTop)
    scroll.setWidget(list_container)
    layout.addWidget(scroll, 1)

    # ── Build / refresh list ───────────────────────────────────────────────
    def _refresh():
        # Clear existing rows
        while list_layout.count():
            item = list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        docs = service.get_documents_for_entity(entity_type, entity_id)
        count_label.setText(f"{title} ({len(docs)} docs)")

        if not docs:
            empty = QLabel(t("docs.no_documents"))
            empty.setProperty("fontRole", "muted")
            empty.setAlignment(Qt.AlignCenter)
            list_layout.addWidget(empty)
            return

        for doc in docs:
            row = QFrame()
            row.setProperty("role", "card")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(S["3"], S["2"], S["3"], S["2"])
            row_layout.setSpacing(S["3"])

            # Icon
            mime = doc.get("mime_type", "")
            icon_char = "\U0001F4C1" if mime and "folder" in mime else (
                "\U0001F4CE" if mime and "image" in mime else "\U0001F4C4"
            )
            icon_lbl = QLabel(icon_char)
            icon_lbl.setFixedWidth(30)
            icon_lbl.setAlignment(Qt.AlignCenter)
            row_layout.addWidget(icon_lbl)

            # Info
            info = QLabel(
                f"{doc.get('title', doc.get('file_name', ''))}\n"
                f"{doc.get('doc_number', '')} | "
                f"{_fmt_size(doc.get('file_size', 0))} | "
                f"{str(doc.get('uploaded_at', ''))[:10]}"
            )
            info.setProperty("fontRole", "body")
            row_layout.addWidget(info, 1)

            # Actions
            view_btn = Btn(row, t("docs.view"), variant="ghost")
            view_btn.setFixedWidth(50)
            def _open_doc(d: dict) -> None:
                path = service.get_file_path(d["id"])
                if path:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            view_btn.clicked.connect(lambda checked, d=doc: _open_doc(d))
            row_layout.addWidget(view_btn)

            unlink_btn = Btn(row, t("docs.unlink"), variant="ghost")
            unlink_btn.setFixedWidth(50)
            unlink_btn.clicked.connect(
                lambda checked, d=doc: _unlink_and_refresh(d["id"])
            )
            row_layout.addWidget(unlink_btn)

            list_layout.addWidget(row)

    def _unlink_and_refresh(doc_id: int):
        links = service.get_links(doc_id)
        for lk in links:
            if (lk["linked_entity_type"] == entity_type
                    and lk["linked_entity_id"] == entity_id):
                service.unlink_document(lk["id"])
                break
        _refresh()

    def _upload():
        paths, _ = QFileDialog.getOpenFileNames(
            dlg,
            t("docs.upload_title"),
            "",
            "All Supported (*.pdf *.png *.jpg *.jpeg *.docx *.xlsx *.csv *.txt *.zip);;All Files (*.*)",
        )
        if not paths:
            return
        for src in paths:
            with contextlib.suppress(Exception):
                service.upload(
                    source_path=src,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    uploaded_by="user",
                )
        _refresh()

    upload_btn.clicked.connect(_upload)
    _refresh()

    dlg.exec()


def _fmt_size(size: int) -> str:
    """Format file size in human-readable form."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"
