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
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from client.api_client import ApiClient
from services.i18n import t
from ui.components import Btn
from ui.theme import S
from ui.widgets import SectionHeader

logger = logging.getLogger(__name__)


_STATUS_STYLES = {
    "online": "color: #22c55e; font-weight: bold;",
    "offline": "color: #ef4444; font-weight: bold;",
    "unknown": "color: #6b7280; font-style: italic;",
}


class _StatusCard(QFrame):
    def __init__(self, parent: QWidget, title: str, status: str = "unknown", detail: str = ""):
        super().__init__(parent)
        self.setProperty("role", "card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S["3"], S["3"], S["3"], S["3"])
        layout.setSpacing(S["1"])

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


class _ActionButton(QPushButton):
    def __init__(self, parent: QWidget, text: str, command=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        if command:
            self.clicked.connect(command)


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
        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(5000)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        layout.setSpacing(S["3"])

        header = SectionHeader(self, t("api.dashboard_title", default="API Dashboard"))
        layout.addWidget(header)

        self._status_grid = QGridLayout()
        self._status_grid.setSpacing(S["3"])
        layout.addLayout(self._status_grid)

        actions_row = QHBoxLayout()
        self._test_btn = Btn(self, "Test API", command=self._test_api, variant="secondary")
        actions_row.addWidget(self._test_btn)
        self._refresh_btn = Btn(self, "Refresh", command=self._refresh_status, variant="secondary")
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
        while self._status_grid.count():
            item = self._status_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        online = self._api.is_online()
        status = "online" if online else "offline"

        api_card = _StatusCard(self, "API Server", status,
                               "https://api.operionerp.xyz" if online else "Unreachable")
        self._status_grid.addWidget(api_card, 0, 0)

        if online:
            try:
                health = self._api.health_check()
                db_stat = health.get("database", "unknown")
                db_card = _StatusCard(self, "Database", "online", str(db_stat))
                self._status_grid.addWidget(db_card, 0, 1)

                ver = health.get("version", "")
                ver_card = _StatusCard(self, "API Version", "online", f"v{ver}")
                self._status_grid.addWidget(ver_card, 1, 0)
            except Exception as e:
                err_card = _StatusCard(self, "Error", "offline", str(e))
                self._status_grid.addWidget(err_card, 0, 1)

        self._add_log(f"API {'ONLINE' if online else 'OFFLINE'}")

    def _test_api(self) -> None:
        try:
            health = self._api.health_check()
            self._add_log(f"Health OK: {health}")
        except Exception as e:
            self._add_log(f"Test failed: {e}")

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
