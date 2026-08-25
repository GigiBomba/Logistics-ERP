"""PySide6 Migration Center view — import/export hub with three tabs.

Uses ``QtDispatchTabs`` for a horizontal tab bar hosting:
  1. ImmigrateSoftwareTab — digital import wizard (CSV/Excel/JSON/XML)
  2. ImmigratePhysicalTab  — physical archive scanner (PDF/JPG/PNG + OCR)
  3. EmigrateTab           — data export (CSV/Excel/JSON)
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from services.i18n import register_listener, t, unregister_listener
from ui.components import Label, PageTitle
from ui.design_tokens import COLOR_TEXT_SECONDARY, FONT_SIZE_SM, SP
from ui.widgets.dispatch_tabs import QtDispatchTabs

logger = logging.getLogger(__name__)


class QtMigrationCenterView(QWidget):
    """Migration Center — import/export hub with three tabs."""

    def __init__(self, parent, db=None, prefs=None, ops=None, migration_service=None):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs
        self.ops = ops
        # In remote (API-only) mode an API-backed service is injected and the
        # tabs use it instead of the DB-backed local services.
        self.migration_service = migration_service

        self._build_ui()
        self._i18n_id = register_listener(self._on_language_changed)

    # ── Lazy tab properties ──────────────────────────────────────────

    @property
    def _tab_software(self):
        if not hasattr(self, '_tab_software_cache'):
            from ui.views.migration_center.immigrate_software_tab import (
                ImmigrateSoftwareTab,
            )
            self._tab_software_cache = ImmigrateSoftwareTab(
                self._tabs, db=self.db, migration_service=self.migration_service,
            )
        return self._tab_software_cache

    @property
    def _tab_physical(self):
        if not hasattr(self, '_tab_physical_cache'):
            from ui.views.migration_center.immigrate_physical_tab import (
                ImmigratePhysicalTab,
            )
            self._tab_physical_cache = ImmigratePhysicalTab(
                self._tabs, db=self.db, migration_service=self.migration_service,
            )
        return self._tab_physical_cache

    @property
    def _tab_emigrate(self):
        if not hasattr(self, '_tab_emigrate_cache'):
            from ui.views.migration_center.emigrate_tab import EmigrateTab
            self._tab_emigrate_cache = EmigrateTab(
                self._tabs, db=self.db, migration_service=self.migration_service,
            )
        return self._tab_emigrate_cache

    def _tab_with_desc(self, tab_widget: QWidget, desc_text: str) -> QWidget:
        """Wrap a tab widget with a description label below its header."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP["1"])
        desc = QLabel(desc_text)
        desc.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        layout.addWidget(tab_widget, 1)
        return container

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["5"], SP["4"], SP["5"], SP["4"])
        layout.setSpacing(SP["3"])

        # ── Page header ────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(SP["3"])

        self._title = PageTitle(self, t("migration.title", "Migration Center"))
        header_row.addWidget(self._title)

        self._subtitle = Label(
            self,
            t("migration.subtitle", "Import and export your data"),
            role="secondary",
        )
        header_row.addWidget(self._subtitle)
        header_row.addStretch()
        layout.addLayout(header_row)

        # ── Tab container ──────────────────────────────────────────────
        self._tabs = QtDispatchTabs(self)
        layout.addWidget(self._tabs, 1)

        # Tab 0 — software (eager; visible by default)
        self._tabs.add_tab(
            "software",
            t("migration.tab_software", "Import from Software"),
            self._tab_with_desc(
                self._tab_software,
                t("migration.software_desc",
                  "Import digital records from CSV, Excel, JSON or XML files with column mapping and validation."),
            ),
        )

        # Tabs 1 & 2 — lazy placeholders; real panels created on first switch
        self._physical_holder = QWidget(self._tabs)
        self._tabs.add_tab(
            "physical",
            t("migration.tab_physical", "Physical Archive"),
            self._physical_holder,
        )

        self._emigrate_holder = QWidget(self._tabs)
        self._tabs.add_tab(
            "emigrate",
            t("migration.tab_emigrate", "Export Data"),
            self._emigrate_holder,
        )

        self._tabs.on_switch(self._on_tab_changed)

    # ── Tab switch handler (lazy init) ───────────────────────────────

    def _on_tab_changed(self, tab_id: str) -> None:
        """Lazy-init the real tab panel on first visit."""
        # Resolve the real panel (triggers lazy property / deferred import)
        if tab_id == "software":
            tab = self._tab_software
        elif tab_id == "physical":
            tab = self._tab_physical
        elif tab_id == "emigrate":
            tab = self._tab_emigrate
        else:
            return

        # Wrap with description label on first visit
        holder = getattr(self, f"_{tab_id}_holder", None)
        if holder is not None:
            desc_key = {
                "software": "migration.software_desc",
                "physical": "migration.physical_desc",
                "emigrate": "migration.emigrate_desc",
            }.get(tab_id, "")
            desc_text = t(desc_key, default="") if desc_key else ""
            wrapped = self._tab_with_desc(tab, desc_text) if desc_text else tab
            self._tabs.set_tab_panel(tab_id, wrapped)
            setattr(self, f"_{tab_id}_holder", None)

        if hasattr(tab, "wakeup"):
            tab.wakeup()

    # ── i18n ──────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        """Update all displayed text when the UI language changes."""
        self._title.setText(t("migration.title", "Migration Center"))
        self._subtitle.setText(t("migration.subtitle", "Import and export your data"))
        self._tabs.refresh_translations({
            "software": t("migration.tab_software", "Import from Software"),
            "physical": t("migration.tab_physical", "Physical Archive"),
            "emigrate": t("migration.tab_emigrate", "Export Data"),
        })

    # ── Lifecycle hooks ───────────────────────────────────────────────

    def wakeup(self):
        pass

    def shutdown(self):
        """Clean up i18n listener and per-tab resources."""
        if self._i18n_id is not None:
            unregister_listener(self._i18n_id)
            self._i18n_id = None
