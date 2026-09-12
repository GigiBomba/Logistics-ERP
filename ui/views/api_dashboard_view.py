"""API Dashboard tab — monitor the backend API health, view endpoint
status, and manage Redis/Celery connection status from the Document Center.
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from client.api_client import ApiClient
from services.i18n import t
from ui.components import Btn
from ui.design_tokens import (
    COLOR_ERROR_DEFAULT,
    COLOR_NEUTRAL_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    SP,
)
from ui.widgets import SectionHeader
from ui.worker_pool import WorkerPool

logger = logging.getLogger(__name__)


_STATUS_STYLES = {
    "online": f"color: {COLOR_SUCCESS_DEFAULT}; font-weight: bold;",
    "offline": f"color: {COLOR_ERROR_DEFAULT}; font-weight: bold;",
    "unknown": f"color: {COLOR_NEUTRAL_DEFAULT}; font-style: italic;",
}


class _StatusCard(QFrame):
    def __init__(self, parent: QWidget, title: str, status: str = "unknown", detail: str = ""):
        super().__init__(parent)
        self.setProperty("role", "card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["3"], SP["3"], SP["3"], SP["3"])
        layout.setSpacing(SP["1"])

        self._title = QLabel(title, self)
        self._title.setProperty("fontRole", "label")
        layout.addWidget(self._title)

        self._status = QLabel(status, self)
        self._status.setStyleSheet(_STATUS_STYLES.get(status, _STATUS_STYLES["unknown"]))
        layout.addWidget(self._status)

        self._detail = QLabel(detail, self)
        self._detail.setProperty("fontRole", "small")
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)

    def update_status(self, status: str, detail: str = "") -> None:
        self._status.setText(status)
        self._status.setStyleSheet(_STATUS_STYLES.get(status, _STATUS_STYLES["unknown"]))
        self._detail.setText(detail)


class QtApiDashboardView(QWidget):
    """Embedded API monitoring dashboard for the Document Center.

    Shows API connection status, Redis/Celery health, and quick actions.
    Auto-refreshes every 5 seconds.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        api_client: Optional[ApiClient] = None,
    ):
        super().__init__(parent)
        self.db = db
        self._api = api_client or ApiClient()
        self._refreshing = False
        self._status_cards: dict[tuple[int, int], "_StatusCard"] = {}
        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(30_000)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        layout.setSpacing(SP["3"])

        header = SectionHeader(self, t("api.dashboard_title", default="API Dashboard"))
        layout.addWidget(header)

        self._status_grid = QGridLayout()
        self._status_grid.setSpacing(SP["3"])
        layout.addLayout(self._status_grid)

        actions_row = QHBoxLayout()
        self._test_btn = Btn(
            self, t("api.test_api", default="Test API"),
            command=self._test_api, variant="secondary",
        )
        self._refresh_btn = Btn(
            self, t("common.refresh", default="Refresh"),
            command=self._refresh_status, variant="secondary",
        )
        actions_row.addWidget(self._test_btn)
        actions_row.addWidget(self._refresh_btn)
        actions_row.addStretch()
        layout.addLayout(actions_row)

        logs_header = QLabel(t("api.recent_logs", default="Connection Log"))
        logs_header.setProperty("fontRole", "label")
        layout.addWidget(logs_header)

        self._log_scroll = QScrollArea()
        self._log_scroll.setWidgetResizable(True)
        self._log_scroll.setFrameShape(QFrame.NoFrame)
        self._log_content = QWidget()
        self._log_layout = QVBoxLayout(self._log_content)
        self._log_layout.setAlignment(Qt.AlignTop)
        self._log_scroll.setWidget(self._log_content)
        layout.addWidget(self._log_scroll, 1)

        self._refresh_status()

    def wakeup(self) -> None:
        self._refresh_status()

    def _refresh_status(self) -> None:
        """Poll API status off the UI thread; skip if a poll is in flight."""
        if self._refreshing:
            return
        self._refreshing = True
        WorkerPool.run(
            fn=self._do_status_check,
            on_result=self._apply_status,
            on_error=self._apply_error,
        )

    def _do_status_check(self) -> dict:
        """Run the HTTP checks on the worker thread."""
        online = self._api.is_online()
        result: dict = {"online": online}
        if online:
            try:
                result["health"] = self._api.health_check()
            except Exception as e:
                result["error"] = str(e)
        return result

    def _apply_status(self, result: dict) -> None:
        self._refreshing = False
        online = bool(result.get("online"))
        health = result.get("health")
        error = result.get("error")

        desired: dict[tuple[int, int], tuple[str, str, str]] = {}
        desired[(0, 0)] = (
            t("api.server", default="API Server"),
            "online" if online else "offline",
            "https://api.operionerp.xyz" if online
            else t("api.unreachable", default="Unreachable"),
        )
        if online and error is None:
            db_stat = health.get("database", "unknown") if health else "unknown"
            desired[(0, 1)] = (
                t("api.database", default="Database"), "online", str(db_stat)
            )
            ver = health.get("version", "") if health else ""
            desired[(1, 0)] = (
                t("api.version", default="API Version"), "online", f"v{ver}"
            )
        elif error is not None:
            desired[(0, 1)] = (
                t("api.error", default="Error"), "offline", str(error)
            )

        self._reconcile_status_cards(desired)
        self._add_log(
            t("api.log_status", default="API {state}").format(
                state=(
                    t("api.online", default="ONLINE")
                    if online else t("api.offline", default="OFFLINE")
                )
            )
        )

    def _apply_error(self, msg: str) -> None:
        self._refreshing = False
        self._reconcile_status_cards({
            (0, 0): (
                t("api.server", default="API Server"), "offline",
                t("api.unreachable", default="Unreachable"),
            ),
            (0, 1): (t("api.error", default="Error"), "offline", msg),
        })
        self._add_log(f"{t('api.log_error', default='API error')}: {msg}")

    def _reconcile_status_cards(self, desired: dict) -> None:
        """Update existing cards in place; only add/remove when needed."""
        # Remove cards that should no longer be shown.
        for key in list(self._status_cards):
            if key not in desired:
                w = self._status_cards.pop(key)
                self._status_grid.removeWidget(w)
                w.deleteLater()
        # Update existing cards in place; create missing ones.
        for (row, col), (title, status, detail) in desired.items():
            card = self._status_cards.get((row, col))
            if card is None:
                card = _StatusCard(self, title, status, detail)
                self._status_cards[(row, col)] = card
                self._status_grid.addWidget(card, row, col)
            else:
                card.update_status(status, detail)

    def _test_api(self) -> None:
        WorkerPool.run(
            fn=self._api.health_check,
            on_result=lambda h: self._add_log(
                f"{t('api.health_ok', default='Health OK')}: {h}"
            ),
            on_error=lambda msg: self._add_log(
                f"{t('api.test_failed', default='Test failed')}: {msg}"
            ),
        )

    def _add_log(self, msg: str) -> None:
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        lbl = QLabel(f"[{ts}] {msg}", self._log_content)
        lbl.setProperty("fontRole", "mono")
        lbl.setWordWrap(True)
        self._log_layout.addWidget(lbl)
        if self._log_layout.count() > 100:
            item = self._log_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        scroll = self._log_scroll.verticalScrollBar()
        if scroll:
            scroll.setValue(scroll.maximum())

    def shutdown(self) -> None:
        self._refresh_timer.stop()
