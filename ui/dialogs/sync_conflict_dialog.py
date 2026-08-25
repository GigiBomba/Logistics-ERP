"""Sync conflict journal dialog (Phase 4b).

Lists unresolved conflicts from ``SyncConflictService.list_unresolved()``
and lets the user resolve each one:

* **Keep local** — marks the conflict resolved and requests a re-sync; the
  pending outbox row is re-pushed (the local payload wins).
* **Take server** — applies the server's row to the local database via
  ``SyncPullService.apply_server_row``, clears the pending outbox op, and
  marks the conflict resolved (the server version wins).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    COLOR_BG_BASE,
    COLOR_BG_CARD,
    COLOR_BG_HOVER,
    COLOR_BORDER_MEDIUM,
    COLOR_TEXT_PRIMARY,
    RADIUS_SM,
    SPACE_2,
    SPACE_6,
)

logger = logging.getLogger(__name__)


class SyncConflictDialog(QDialog):
    """Modal dialog listing unresolved sync conflicts with per-row actions."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        conflict_service=None,
        pull_service=None,
        outbox_service=None,
        engine=None,
    ) -> None:
        super().__init__(parent)
        self._conflict_service = conflict_service
        self._pull_service = pull_service
        self._outbox_service = outbox_service
        self._engine = engine
        self._conflicts: list[dict] = []
        self._build_ui()
        self._reload()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle(t("sync.conflicts_title", default="Sync Conflicts"))
        self.setAccessibleName("Sync Conflicts")
        self.setMinimumSize(760, 420)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BG_BASE}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE_2 * 2, SPACE_2 * 2, SPACE_2 * 2, SPACE_2 * 2)
        root.setSpacing(SPACE_2)

        title = QLabel(t("sync.conflicts_title", default="Sync Conflicts"), self)
        title.setProperty("fontRole", "h3")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        self._table = QTableWidget(0, 6, self)
        self._table.setHorizontalHeaderLabels([
            t("sync.entity", default="Entity"),
            t("sync.local_id", default="Local ID"),
            t("sync.server_id", default="Server ID"),
            t("sync.created", default="Created"),
            t("sync.resolved", default="Resolved"),
            t("sync.actions", default="Actions"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        root.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(t("common.close", default="Close"), self)
        close_btn.setStyleSheet(
            f"QPushButton {{ padding: {SPACE_2}px {SPACE_6}px; "
            f"border: 1px solid {COLOR_BORDER_MEDIUM}; "
            f"border-radius: {RADIUS_SM}px; background: {COLOR_BG_CARD}; "
            f"color: {COLOR_TEXT_PRIMARY}; }}"
            f"QPushButton:hover {{ background: {COLOR_BG_HOVER}; }}"
        )
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ── Data ─────────────────────────────────────────────────────────────

    def _reload(self) -> None:
        """Re-read unresolved conflicts and rebuild the table."""
        self._conflicts = (
            self._conflict_service.list_unresolved()
            if self._conflict_service is not None
            else []
        )
        self._table.setRowCount(len(self._conflicts))
        for row_idx, c in enumerate(self._conflicts):
            self._table.setItem(row_idx, 0, QTableWidgetItem(str(c.get("entity_type", ""))))
            self._table.setItem(row_idx, 1, QTableWidgetItem(str(c.get("local_id", ""))))
            self._table.setItem(row_idx, 2, QTableWidgetItem(str(c.get("server_id") or "")))
            self._table.setItem(row_idx, 3, QTableWidgetItem(str(c.get("created_at", ""))))
            self._table.setItem(row_idx, 4, QTableWidgetItem("Yes" if c.get("resolved") else "No"))
            self._table.setCellWidget(row_idx, 5, self._build_actions(c["id"]))

    def _build_actions(self, conflict_id: int) -> QWidget:
        actions = QWidget()
        lay = QHBoxLayout(actions)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        keep_btn = QPushButton(t("sync.keep_local", default="Keep local"), actions)
        keep_btn.setStyleSheet(
            f"QPushButton {{ padding: {SPACE_2}px {SPACE_6}px; "
            f"border: 1px solid {COLOR_BORDER_MEDIUM}; "
            f"border-radius: {RADIUS_SM}px; background: {COLOR_BG_CARD}; "
            f"color: {COLOR_TEXT_PRIMARY}; }}"
            f"QPushButton:hover {{ background: {COLOR_BG_HOVER}; }}"
        )
        keep_btn.clicked.connect(lambda checked=False, cid=conflict_id: self._keep_local(cid))

        take_btn = QPushButton(t("sync.take_server", default="Take server"), actions)
        take_btn.setStyleSheet(
            f"QPushButton {{ padding: {SPACE_2}px {SPACE_6}px; "
            f"border: 1px solid {COLOR_BORDER_MEDIUM}; "
            f"border-radius: {RADIUS_SM}px; background: {COLOR_BG_CARD}; "
            f"color: {COLOR_TEXT_PRIMARY}; }}"
            f"QPushButton:hover {{ background: {COLOR_BG_HOVER}; }}"
        )
        take_btn.clicked.connect(lambda checked=False, cid=conflict_id: self._take_server(cid))

        lay.addWidget(keep_btn)
        lay.addWidget(take_btn)
        return actions

    # ── Actions ──────────────────────────────────────────────────────────

    def _keep_local(self, conflict_id: int) -> None:
        """Keep the local version: re-stamp updated_at, mark resolved, re-push.

        Re-stamping the local row's ``updated_at`` BEFORE marking resolved
        gives the pending outbox row a fresh ``base_updated_at`` so the
        re-push wins on the next sync (R3) — otherwise the server rejects
        the unchanged row again and the conflict loops forever.

        For a HARD-deleted row there is no row to re-stamp (restamp returns
        False); the DELETE payload is frozen at delete time, so the frozen
        payload's ``updated_at`` is bumped instead — the DELETE re-pushes
        with a fresh base and wins.  If the row is gone and there is no
        pending DELETE op, there is nothing to re-push — the conflict is
        simply marked resolved.
        """
        conflict = next((c for c in self._conflicts if c["id"] == conflict_id), None)
        if conflict is None:
            return
        if self._conflict_service is not None:
            restamped = self._conflict_service.restamp_local_updated_at(
                conflict["entity_type"], conflict["local_id"]
            )
            if not restamped and self._outbox_service is not None:
                # Row is gone (hard-deleted): bump the frozen DELETE payload
                # so the re-push carries a fresh base_updated_at and wins.
                self._outbox_service.bump_delete_payload_updated_at(
                    conflict["entity_type"], conflict["local_id"]
                )
            self._conflict_service.mark_resolved(conflict_id)
        if self._engine is not None:
            self._engine.request_sync()
        self._reload()

    def _take_server(self, conflict_id: int) -> None:
        """Take the server version: apply it locally, clear the pending op.

        The outbox op is only cleared and the conflict only marked resolved
        when the server row was actually applied (S1) — a missing/invalid
        ``server_payload`` or a failed upsert must NOT silently drop the
        local edits; the conflict stays unresolved and the user is told.
        """
        conflict = next((c for c in self._conflicts if c["id"] == conflict_id), None)
        if conflict is None:
            return
        entity_type = conflict["entity_type"]
        local_id = conflict["local_id"]
        server_payload = None
        if conflict.get("server_payload"):
            try:
                server_payload = json.loads(conflict["server_payload"])
            except (TypeError, ValueError):
                logger.warning("conflict %s: invalid server_payload JSON", conflict_id)
        applied = False
        if server_payload is not None and self._pull_service is not None:
            try:
                applied = bool(self._pull_service.apply_server_row(entity_type, server_payload))
            except Exception as exc:
                logger.warning("conflict %s: apply_server_row failed: %s", conflict_id, exc)
                applied = False
        if not applied:
            QMessageBox.warning(
                self,
                t("sync.take_server_failed_title", default="Take Server Failed"),
                t(
                    "sync.take_server_failed_message",
                    default="Could not apply the server version. "
                    "The conflict was left unresolved.",
                ),
            )
            return
        if self._outbox_service is not None:
            self._outbox_service.mark_synced_for(entity_type, local_id)
        if self._conflict_service is not None:
            self._conflict_service.mark_resolved(conflict_id)
        self._reload()