"""PySide6 Migration Center view — import/export hub with three tabs.

Uses ``QtDispatchTabs`` for a horizontal tab bar hosting:
  1. ImmigrateSoftwareTab — digital import wizard (CSV/Excel/JSON/XML)
  2. ImmigratePhysicalTab  — physical archive scanner (PDF/JPG/PNG + OCR)
  3. EmigrateTab           — data export (CSV/Excel/JSON)
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from services.i18n import t
from ui.components import Label, PageTitle
from ui.design_tokens import COLOR_TEXT_SECONDARY, SP
from ui.views.migration_center.emigrate_tab import EmigrateTab
from ui.views.migration_center.immigrate_physical_tab import ImmigratePhysicalTab
from ui.views.migration_center.immigrate_software_tab import ImmigrateSoftwareTab
from ui.widgets.dispatch_tabs import QtDispatchTabs

logger = logging.getLogger(__name__)


class QtMigrationCenterView(QWidget):
    """Migration Center — import/export hub with three tabs."""

    def __init__(self, parent, db=None, prefs=None, ops=None):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs
        self.ops = ops

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["5"], SP["4"], SP["5"], SP["4"])
        layout.setSpacing(SP["3"])

        # ── Page header ────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(SP["3"])

        title = PageTitle(self, t("migration.title", "Migration Center"))
        header_row.addWidget(title)

        subtitle = Label(
            self,
            t("migration.subtitle", "Import and export your data"),
            role="secondary",
        )
        header_row.addWidget(subtitle)
        header_row.addStretch()
        layout.addLayout(header_row)

        # ── Tab container ──────────────────────────────────────────────
        self._tabs = QtDispatchTabs(self)
        layout.addWidget(self._tabs, 1)

        # Create tab panels
        self._tab_software = ImmigrateSoftwareTab(self._tabs, db=self.db)
        self._tab_physical = ImmigratePhysicalTab(self._tabs, db=self.db)
        self._tab_emigrate = EmigrateTab(self._tabs, db=self.db)

        # Register tabs
        self._tabs.add_tab(
            "software",
            t("migration.tab_software", "Import from Software"),
            self._tab_software,
        )
        self._tabs.add_tab(
            "physical",
            t("migration.tab_physical", "Physical Archive"),
            self._tab_physical,
        )
        self._tabs.add_tab(
            "emigrate",
            t("migration.tab_emigrate", "Export Data"),
            self._tab_emigrate,
        )

    # ── Lifecycle hooks ───────────────────────────────────────────────

    def wakeup(self):
        pass

    def shutdown(self):
        """Cleanup is handled per-tab during destruction."""
        pass
