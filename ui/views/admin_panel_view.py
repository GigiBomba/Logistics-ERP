"""Admin Debug Panel — diagnostics, DB inspector, system info, health.

This widget is **never** instantiated at application boot.  It is
dynamically injected into the Document Center's ``QTabWidget`` only
after a successful admin JWT handshake (see Phase 3 Dual-Gate).

All data is fetched from the backend via ``ApiClient`` — there is
no local database fallback for admin features.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from client.api_client import ApiClient
from services.i18n import t
from ui.components import Btn
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_SUCCESS_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_TERTIARY,
    SP,
)
from ui.widgets import SectionHeader, StyledComboBox

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_STATUS_COLORS = {
    "ok": COLOR_SUCCESS_DEFAULT,
    "error": "#ef4444",
    "unavailable": "#6b7280",
    "warning": "#f59e0b",
}


def _val(val: Any, default: str = "—") -> str:
    """Return *val* as a string, or *default* if None/empty."""
    if val is None:
        return default
    s = str(val)
    return s if s else default


def _card(parent: QWidget, title: str, value: str, color: str = "") -> QFrame:
    """Return a small info card with title and value."""
    frame = QFrame(parent)
    frame.setProperty("role", "card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(SP["3"], SP["3"], SP["3"], SP["3"])
    layout.setSpacing(SP["1"])

    lbl = QLabel(title, frame)
    lbl.setProperty("fontRole", "small")
    layout.addWidget(lbl)

    val_lbl = QLabel(value, frame)
    val_lbl.setProperty("fontRole", "body_bold")
    if color:
        val_lbl.setStyleSheet(f"color: {color};")
    layout.addWidget(val_lbl)

    return frame


# ──────────────────────────────────────────────────────────────────────────────
# Generic async fetch worker
# ──────────────────────────────────────────────────────────────────────────────


class _FetchWorker(QObject):
    """QThread worker that fetches data from an admin API endpoint.

    Emits ``finished(data)`` on success or ``error(msg)`` on failure.
    """

    finished = Signal(object)  # data (dict or list)
    error = Signal(str)

    def __init__(
        self, api: ApiClient, method_name: str, *args: Any, **kwargs: Any,
    ) -> None:
        super().__init__()
        self._api = api
        self._method_name = method_name
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            method = getattr(self._api, self._method_name)
            data = method(*self._args, **self._kwargs)
            self.finished.emit(data)
        except Exception as exc:
            logger.debug("Admin fetch %s failed: %s", self._method_name, exc)
            self.error.emit(str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# Main admin panel view
# ──────────────────────────────────────────────────────────────────────────────


class QtAdminPanelView(QWidget):
    """Admin debug panel injected at runtime into the Document Center.

    Sub-tabs:
        0 — Diagnostics (latency, Celery, Redis, config flags)
        1 — Database Inspector (tables, schema, data, raw SQL)
        2 — Document Statistics
        3 — System Info / Env / Log tail
        4 — Health / Cache
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db: Any = None,
        api_client: Optional[ApiClient] = None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self._api = api_client or ApiClient()
        self._current_worker: Optional[_FetchWorker] = None
        self._current_thread: Optional[QThread] = None
        self._build_ui()

    # ── Lifecycle ─────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Refresh all sub-tab data."""
        self._fetch_diagnostics()

    def shutdown(self) -> None:
        """Stop any running workers."""
        self._stop_worker()

    def _stop_worker(self) -> None:
        if self._current_thread is not None and self._current_thread.isRunning():
            self._current_thread.quit()
            self._current_thread.wait(1000)
        self._current_worker = None
        self._current_thread = None

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setAccessibleName("Admin panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tab_widget = QTabWidget()
        self._tab_widget.setProperty("role", "admin-panel-tabs")
        layout.addWidget(self._tab_widget, 1)

        self._build_diagnostics_tab()     # index 0
        self._build_db_inspector_tab()    # index 1
        self._build_doc_stats_tab()       # index 2
        self._build_system_tab()          # index 3
        self._build_health_tab()          # index 4

        self._tab_widget.setTabText(0, t("admin.diagnostics", default="Diagnostics"))
        self._tab_widget.setTabText(1, t("admin.db_inspector", default="Database Inspector"))
        self._tab_widget.setTabText(2, t("admin.doc_stats", default="Document Statistics"))
        self._tab_widget.setTabText(3, t("admin.system_info", default="System Info"))
        self._tab_widget.setTabText(4, t("admin.health", default="Health"))

    # ═══════════════════════════════════════════════════════════════════
    # Sub-tab 0: Diagnostics
    # ═══════════════════════════════════════════════════════════════════

    def _build_diagnostics_tab(self) -> None:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        layout.setSpacing(SP["3"])

        header = SectionHeader(content, t("admin.diagnostics", default="Diagnostics"))
        layout.addWidget(header)

        self._diag_grid = QGridLayout()
        self._diag_grid.setSpacing(SP["3"])
        layout.addLayout(self._diag_grid)

        # Latency
        self._diag_latency = _card(content, t("admin.latency", default="Latency"), "—")
        self._diag_grid.addWidget(self._diag_latency, 0, 0)

        # Celery status
        celery_box = QGroupBox(t("admin.celery_status", default="Celery Status"), content)
        celery_layout = QVBoxLayout(celery_box)
        self._celery_active = QLabel("—")
        celery_layout.addWidget(QLabel(t("admin.active_tasks", default="Active Tasks:")))
        celery_layout.addWidget(self._celery_active)
        celery_layout.addWidget(QLabel(t("admin.scheduled_tasks", default="Scheduled:")))
        self._celery_scheduled = QLabel("—")
        celery_layout.addWidget(self._celery_scheduled)
        celery_layout.addWidget(QLabel(t("admin.queue_size", default="Queue Size:")))
        self._celery_queue = QLabel("—")
        celery_layout.addWidget(self._celery_queue)
        celery_layout.addWidget(QLabel(t("admin.workers_online", default="Workers Online:")))
        self._celery_workers = QLabel("—")
        celery_layout.addWidget(self._celery_workers)
        self._diag_grid.addWidget(celery_box, 0, 1)

        # Redis status
        redis_box = QGroupBox(t("admin.redis_status", default="Redis Status"), content)
        redis_layout = QVBoxLayout(redis_box)
        self._redis_connected = QLabel("—")
        redis_layout.addWidget(QLabel(t("admin.connected_label", default="Connected:")))
        redis_layout.addWidget(self._redis_connected)
        redis_layout.addWidget(QLabel(t("admin.memory_used", default="Memory Used:")))
        self._redis_memory = QLabel("—")
        redis_layout.addWidget(self._redis_memory)
        redis_layout.addWidget(QLabel(t("admin.keys_count", default="Keys:")))
        self._redis_keys = QLabel("—")
        redis_layout.addWidget(self._redis_keys)
        redis_layout.addWidget(QLabel(t("admin.hit_rate", default="Hit Rate:")))
        self._redis_hit_rate = QLabel("—")
        redis_layout.addWidget(self._redis_hit_rate)
        self._diag_grid.addWidget(redis_box, 0, 2)

        # Config flags
        cfg_box = QGroupBox(t("admin.config_flags", default="Configuration"), content)
        cfg_layout = QVBoxLayout(cfg_box)
        self._cfg_db_engine = QLabel("—")
        cfg_layout.addWidget(QLabel(t("admin.db_engine_label", default="DB Engine:")))
        cfg_layout.addWidget(self._cfg_db_engine)
        self._cfg_env_mode = QLabel("—")
        cfg_layout.addWidget(QLabel(t("admin.environment_label", default="Environment:")))
        cfg_layout.addWidget(self._cfg_env_mode)
        self._cfg_api_version = QLabel("—")
        cfg_layout.addWidget(QLabel(t("admin.api_version_label", default="API Version:")))
        cfg_layout.addWidget(self._cfg_api_version)
        self._cfg_debug = QLabel("—")
        cfg_layout.addWidget(QLabel(t("admin.debug_mode_label", default="Debug Mode:")))
        cfg_layout.addWidget(self._cfg_debug)
        self._diag_grid.addWidget(cfg_box, 0, 3)

        # Refresh button
        self._diag_refresh_btn = Btn(
            content, text=t("admin.refresh", default="Refresh"),
            command=self._fetch_diagnostics, variant="secondary",
        )
        layout.addWidget(self._diag_refresh_btn)

        layout.addStretch()
        scroll.setWidget(content)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        self._tab_widget.addTab(page, "")

    def _fetch_diagnostics(self) -> None:
        self._run_worker("get_admin_diagnostics", self._on_diagnostics)

    def _on_diagnostics(self, data: Dict[str, Any]) -> None:
        latency = data.get("latency_ms", "—")
        color = _STATUS_COLORS["ok"] if isinstance(latency, (int, float)) and latency < 1000 else _STATUS_COLORS["warning"]
        # Remove and delete the old latency card before creating a new one
        # to prevent widgets accumulating in the grid layout.
        old_card = self._diag_latency
        if old_card is not None:
            parent_widget = old_card.parentWidget() or self
            self._diag_grid.removeWidget(old_card)
            old_card.deleteLater()
        else:
            parent_widget = self
        self._diag_latency = _card(
            parent_widget,
            t("admin.latency", default="Latency"),
            f"{latency} ms" if isinstance(latency, (int, float)) else str(latency),
            color=color,
        )
        self._diag_grid.addWidget(self._diag_latency, 0, 0)

        celery = data.get("celery")
        if celery:
            self._celery_active.setText(_val(celery.get("active_tasks"), "0"))
            self._celery_scheduled.setText(_val(celery.get("scheduled_tasks"), "0"))
            self._celery_queue.setText(_val(celery.get("queue_size"), "0"))
            self._celery_workers.setText(_val(celery.get("workers_online"), "0"))
        else:
            for lbl in (self._celery_active, self._celery_scheduled, self._celery_queue, self._celery_workers):
                lbl.setText(t("admin.unavailable", default="Unavailable"))

        redis_data = data.get("redis")
        if redis_data and redis_data.get("connected"):
            self._redis_connected.setText("✓")
            self._redis_connected.setStyleSheet(f"color: {_STATUS_COLORS['ok']};")
            self._redis_memory.setText(f"{redis_data.get('memory_used_mb', '—')} MB")
            self._redis_keys.setText(_val(redis_data.get("keys_count")))
            self._redis_hit_rate.setText(f"{redis_data.get('hit_rate_pct', '—')}%")
        else:
            self._redis_connected.setText("✗")
            self._redis_connected.setStyleSheet(f"color: {_STATUS_COLORS['unavailable']};")
            self._redis_memory.setText("—")
            self._redis_keys.setText("—")
            self._redis_hit_rate.setText("—")

        cfg = data.get("config_flags", {})
        self._cfg_db_engine.setText(_val(cfg.get("db_engine")))
        self._cfg_env_mode.setText(_val(cfg.get("env_mode")))
        self._cfg_api_version.setText(_val(cfg.get("api_version")))
        self._cfg_debug.setText(str(cfg.get("debug_mode", False)))

    # ═══════════════════════════════════════════════════════════════════
    # Sub-tab 1: Database Inspector
    # ═══════════════════════════════════════════════════════════════════

    def _build_db_inspector_tab(self) -> None:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        layout.setSpacing(SP["3"])

        header = SectionHeader(content, t("admin.db_inspector", default="Database Inspector"))
        layout.addWidget(header)

        # Table selector row
        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel(t("admin.table_selector", default="Select table:")))
        self._table_combo = StyledComboBox(content, values=["—"])
        self._table_combo.currentTextChanged.connect(self._on_table_selected)
        selector_row.addWidget(self._table_combo, 1)
        refresh_tables_btn = Btn(
            content, text=t("admin.refresh", default="Refresh"),
            command=self._fetch_tables, variant="ghost",
        )
        selector_row.addWidget(refresh_tables_btn)
        layout.addLayout(selector_row)

        # Schema table
        schema_header = QLabel(t("admin.schema_label", default="Schema:"))
        schema_header.setProperty("fontRole", "label")
        layout.addWidget(schema_header)

        self._schema_table = QTableWidget(0, 3)
        self._schema_table.setHorizontalHeaderLabels(["Column", "Type", "PK"])
        self._schema_table.horizontalHeader().setStretchLastSection(True)
        self._schema_table.setMaximumHeight(200)
        layout.addWidget(self._schema_table)

        # Raw SQL query
        sql_header = QLabel(t("admin.query_placeholder", default="SELECT * FROM table LIMIT 100"))
        sql_header.setProperty("fontRole", "label")
        layout.addWidget(sql_header)

        self._sql_input = QTextEdit(content)
        self._sql_input.setPlaceholderText(t("admin.query_placeholder", default="SELECT * FROM table LIMIT 100"))
        self._sql_input.setMaximumHeight(80)
        self._sql_input.setStyleSheet(
            f"QTextEdit {{ padding: 4px; border: 1px solid {COLOR_BORDER_SUBTLE}; "
            f"border-radius: 4px; background: {COLOR_BG_OVERLAY}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-family: monospace; }}"
        )
        layout.addWidget(self._sql_input)

        execute_btn = Btn(
            content, text=t("admin.execute_query", default="Execute"),
            command=self._execute_query, variant="primary",
        )
        layout.addWidget(execute_btn)

        # Results table
        self._query_results = QTableWidget(0, 0)
        self._query_results.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._query_results, 1)

        scroll.setWidget(content)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        self._tab_widget.addTab(page, "")

    def _on_table_selected(self, table_name: str) -> None:
        if table_name and table_name != "—":
            self._run_worker(
                "get_admin_db_table_schema",
                self._on_table_schema,
                table_name,
            )

    def _on_table_schema(self, data: Any) -> None:
        columns = data if isinstance(data, list) else []
        self._schema_table.setRowCount(len(columns))
        for i, col in enumerate(columns):
            self._schema_table.setItem(i, 0, QTableWidgetItem(_val(col.get("name"))))
            self._schema_table.setItem(i, 1, QTableWidgetItem(_val(col.get("type"))))
            self._schema_table.setItem(i, 2, QTableWidgetItem("✓" if col.get("pk") else ""))

    def _execute_query(self) -> None:
        sql = self._sql_input.toPlainText().strip()
        if not sql:
            return
        self._run_worker(
            "execute_admin_query",
            self._on_query_result,
            sql,
        )

    def _on_query_result(self, data: Any) -> None:
        rows = data if isinstance(data, list) else []
        if not rows:
            self._query_results.setRowCount(0)
            self._query_results.setColumnCount(1)
            self._query_results.setHorizontalHeaderLabels([t("admin.no_data", default="No data")])
            return

        headers = list(rows[0].keys())
        self._query_results.setColumnCount(len(headers))
        self._query_results.setHorizontalHeaderLabels(headers)
        self._query_results.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, col in enumerate(headers):
                self._query_results.setItem(r_idx, c_idx, QTableWidgetItem(_val(row.get(col))))

    def _fetch_tables(self) -> None:
        self._run_worker("get_admin_db_tables", self._on_tables)

    def _on_tables(self, data: Any) -> None:
        tables = data if isinstance(data, list) else []
        names = [t["name"] for t in tables] if tables else ["—"]
        self._table_combo.clear()
        for name in names:
            self._table_combo.addItem(name)

    # ═══════════════════════════════════════════════════════════════════
    # Sub-tab 2: Document Statistics
    # ═══════════════════════════════════════════════════════════════════

    def _build_doc_stats_tab(self) -> None:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        layout.setSpacing(SP["3"])

        header = SectionHeader(content, t("admin.doc_stats", default="Document Statistics"))
        layout.addWidget(header)

        self._doc_grid = QGridLayout()
        self._doc_grid.setSpacing(SP["3"])
        layout.addLayout(self._doc_grid)

        self._doc_total = _card(content, t("admin.total_docs", default="Total Documents"), "—")
        self._doc_grid.addWidget(self._doc_total, 0, 0)
        self._doc_storage = _card(content, t("admin.storage_used", default="Storage Used"), "—")
        self._doc_grid.addWidget(self._doc_storage, 0, 1)
        self._doc_ocr = _card(content, t("admin.ocr_coverage", default="OCR Coverage"), "—")
        self._doc_grid.addWidget(self._doc_ocr, 0, 2)
        self._doc_orphans = _card(content, t("admin.orphan_docs", default="Orphan Documents"), "—")
        self._doc_grid.addWidget(self._doc_orphans, 0, 3)

        # Category breakdown
        self._doc_cat_header = QLabel(t("admin.category_breakdown", default="Category Breakdown"))
        self._doc_cat_header.setProperty("fontRole", "label")
        layout.addWidget(self._doc_cat_header)
        self._doc_cat_table = QTableWidget(0, 2)
        self._doc_cat_table.setHorizontalHeaderLabels(["Category", "Count"])
        self._doc_cat_table.horizontalHeader().setStretchLastSection(True)
        self._doc_cat_table.setMaximumHeight(200)
        layout.addWidget(self._doc_cat_table)

        refresh_btn = Btn(
            content, text=t("admin.refresh", default="Refresh"),
            command=self._fetch_doc_stats, variant="secondary",
        )
        layout.addWidget(refresh_btn)
        layout.addStretch()

        scroll.setWidget(content)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        self._tab_widget.addTab(page, "")

    def _fetch_doc_stats(self) -> None:
        self._run_worker("get_admin_document_stats", self._on_doc_stats)

    def _on_doc_stats(self, data: Dict[str, Any]) -> None:
        total = data.get("total_documents", 0)
        storage = data.get("total_storage_bytes", 0)
        ocr_pct = data.get("ocr_coverage_pct", 0.0)

        # Format storage
        if storage >= 1024 ** 3:
            storage_str = f"{storage / (1024 ** 3):.2f} GB"
        elif storage >= 1024 ** 2:
            storage_str = f"{storage / (1024 ** 2):.2f} MB"
        else:
            storage_str = f"{storage / 1024:.2f} KB" if storage else "0 B"

        self._doc_total = _card(self, t("admin.total_docs", default="Total Documents"), str(total))
        self._doc_storage = _card(self, t("admin.storage_used", default="Storage Used"), storage_str)
        self._doc_ocr = _card(self, t("admin.ocr_coverage", default="OCR Coverage"), f"{ocr_pct}%")

        # Category breakdown
        by_cat = data.get("by_category", {})
        self._doc_cat_table.setRowCount(len(by_cat))
        for i, (cat, cnt) in enumerate(sorted(by_cat.items(), key=lambda x: -x[1])):
            self._doc_cat_table.setItem(i, 0, QTableWidgetItem(cat))
            self._doc_cat_table.setItem(i, 1, QTableWidgetItem(str(cnt)))

    # ═══════════════════════════════════════════════════════════════════
    # Sub-tab 3: System Info / Env / Log Tail
    # ═══════════════════════════════════════════════════════════════════

    def _build_system_tab(self) -> None:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        layout.setSpacing(SP["3"])

        header = SectionHeader(content, t("admin.system_info", default="System Info"))
        layout.addWidget(header)

        self._sys_table = QTableWidget(0, 2)
        self._sys_table.setHorizontalHeaderLabels(["Key", "Value"])
        self._sys_table.horizontalHeader().setStretchLastSection(True)
        self._sys_table.setMaximumHeight(150)
        layout.addWidget(self._sys_table)

        # Environment vars
        env_header = QLabel(t("admin.system_info", default="Environment"))
        env_header.setProperty("fontRole", "label")
        layout.addWidget(env_header)

        self._env_table = QTableWidget(0, 2)
        self._env_table.setHorizontalHeaderLabels(["Variable", "Value"])
        self._env_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._env_table)

        # Log tail
        log_header = QLabel(t("admin.log_tail", default="Log Tail (last 100 lines)"))
        log_header.setProperty("fontRole", "label")
        layout.addWidget(log_header)

        self._log_text = QTextEdit(content)
        self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet(
            f"QTextEdit {{ padding: 4px; border: 1px solid {COLOR_BORDER_SUBTLE}; "
            f"border-radius: 4px; background: {COLOR_BG_OVERLAY}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-family: monospace; font-size: 11px; }}"
        )
        layout.addWidget(self._log_text, 1)

        # Refresh buttons row
        btn_row = QHBoxLayout()
        sys_refresh_btn = Btn(
            content, text=t("admin.refresh", default="Refresh"),
            command=self._fetch_system_info, variant="secondary",
        )
        btn_row.addWidget(sys_refresh_btn)
        log_refresh_btn = Btn(
            content, text=t("admin.refresh_log", default="Refresh Log"), command=self._fetch_logs, variant="ghost",
        )
        btn_row.addWidget(log_refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        scroll.setWidget(content)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        self._tab_widget.addTab(page, "")

    def _fetch_system_info(self) -> None:
        self._run_worker("get_admin_system_info", self._on_system_info)
        self._run_worker("get_admin_system_env", self._on_system_env)

    def _on_system_info(self, data: Dict[str, Any]) -> None:
        info = [
            (t("admin.python_version_label", default="Python Version"), data.get("python_version", "—")),
            (t("admin.db_engine_label", default="DB Engine"), data.get("db_engine", "—")),
            (t("admin.db_path_label", default="DB Path"), data.get("db_path", "—")),
            (t("admin.api_version_label", default="API Version"), data.get("api_version", "—")),
            (t("admin.platform_label", default="Platform"), data.get("platform", "—")),
        ]
        self._sys_table.setRowCount(len(info))
        for i, (key, val) in enumerate(info):
            self._sys_table.setItem(i, 0, QTableWidgetItem(key))
            self._sys_table.setItem(i, 1, QTableWidgetItem(val))

    def _on_system_env(self, data: Dict[str, Any]) -> None:
        envs = data.get("variables", {})
        self._env_table.setRowCount(len(envs))
        for i, (key, val) in enumerate(sorted(envs.items())):
            self._env_table.setItem(i, 0, QTableWidgetItem(key))
            self._env_table.setItem(i, 1, QTableWidgetItem(val))

    def _fetch_logs(self) -> None:
        self._run_worker("get_admin_logs_tail", self._on_logs)

    def _on_logs(self, data: Dict[str, Any]) -> None:
        lines = data.get("lines", [])
        self._log_text.setText("\n".join(lines))

    # ═══════════════════════════════════════════════════════════════════
    # Sub-tab 4: Health / Cache
    # ═══════════════════════════════════════════════════════════════════

    def _build_health_tab(self) -> None:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        layout.setSpacing(SP["3"])

        header = SectionHeader(content, t("admin.health", default="Health"))
        layout.addWidget(header)

        self._health_grid = QGridLayout()
        self._health_grid.setSpacing(SP["3"])
        layout.addLayout(self._health_grid)

        layout.addStretch()

        # Cache clear
        clear_cache_btn = Btn(
            content, text=t("admin.clear_cache", default="Clear Cache"),
            command=self._clear_cache, variant="danger",
        )
        layout.addWidget(clear_cache_btn)

        refresh_btn = Btn(
            content, text=t("admin.refresh", default="Refresh"),
            command=self._fetch_health, variant="secondary",
        )
        layout.addWidget(refresh_btn)

        scroll.setWidget(content)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        self._tab_widget.addTab(page, "")

    def _fetch_health(self) -> None:
        self._run_worker("get_admin_detailed_health", self._on_health)

    def _on_health(self, data: Dict[str, Any]) -> None:
        services = data.get("services", [])
        # Clear existing cards
        while self._health_grid.count():
            item = self._health_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for i, svc in enumerate(services):
            name = svc.get("name", "?")
            status = svc.get("status", "unavailable")
            color = _STATUS_COLORS.get(status, _STATUS_COLORS["unavailable"])
            card = _card(
                self,
                name.capitalize(),
                status,
                color=color,
            )
            self._health_grid.addWidget(card, 0, i)

    def _clear_cache(self) -> None:
        self._run_worker("clear_admin_cache", self._on_cache_cleared)

    def _on_cache_cleared(self, data: Dict[str, Any]) -> None:
        status = data.get("status", "error")
        detail = data.get("detail", "")
        from ui.widgets.toast import Toast
        Toast.show_success(
            self,
            t("admin.cache_result", default="Cache: {status} — {detail}", status=status, detail=detail),
            anchor=self,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Async worker runner
    # ═══════════════════════════════════════════════════════════════════

    def _run_worker(
        self, method_name: str, callback, *args: Any, **kwargs: Any,
    ) -> None:
        """Fetch data from the backend in a background thread.

        Args:
            method_name: Name of the ``ApiClient`` method to call.
            callback:    Callable that receives the result dict/list.
            *args, **kwargs: Passed to the API method.
        """
        self._stop_worker()
        worker = _FetchWorker(self._api, method_name, *args, **kwargs)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(callback)
        worker.error.connect(self._on_fetch_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._current_worker = worker
        self._current_thread = thread
        thread.start()

    def _on_fetch_error(self, msg: str) -> None:
        logger.warning("Admin fetch error: %s", msg)
        from ui.widgets.toast import Toast
        Toast.show_error(
            self,
            t("admin.offline", default="Server unreachable"),
            anchor=self,
        )
