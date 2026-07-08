"""PySide6 route history browser.

Replaces ``ui/route_history_view.py``. Displays route history in a sortable
table with a map preview, async loading, and export/archive/delete actions.
"""

from __future__ import annotations

import contextlib
import json
import logging
import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from services.i18n import register_listener, t, unregister_listener
from services.route_history_service import RouteHistoryRecord, RouteHistoryService
from services.route_result_presenter import format_duration_minutes
from ui.components import (
    Btn,
    Card,
    Divider,
    Label,
    PageTitle,
)
from ui.design_tokens import SP
from ui.theme import COLORS
from ui.widgets import (
    StyledCheckBox,
    StyledTableWidget,
)
from ui.widgets.debounced_line_edit import DebouncedLineEdit

logger = logging.getLogger(__name__)

TABLE_COLUMNS = [
    ("origin", "route_history.table_origin", 150),
    ("destination", "route_history.table_destination", 150),
    ("last_calculated_at", "route_history.table_datetime", 140),
    ("truck", "route_history.table_truck", 120),
    ("distance_km", "route_history.table_distance", 90),
    ("duration_min", "route_history.table_duration", 90),
    ("profile", "route_history.table_profile", 90),
]

SORT_COLUMN_MAP = {
    "origin": "origin", "destination": "destination",
    "last_calculated_at": "last_calculated_at", "truck": "truck",
    "distance_km": "distance_km", "duration_min": "duration_min",
    "profile": "profile",
}


class QtRouteHistoryView(QWidget):
    """Route history browser with table, map preview, and route actions."""

    # Cross-thread signal: the preview-loader thread emits this from a
    # worker; Qt marshals the slot to the GUI thread.  (Using
    # ``QTimer.singleShot(0, ...)`` from a worker thread does NOT marshal —
    # Qt creates the timer in the calling thread and its event loop
    # never runs, so the preview never gets rendered.)
    preview_loaded = Signal(object, int)   # record, token

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        controller=None,
        api_client=None,
    ):
        super().__init__(parent)
        self.db = db
        self.controller = controller
        self._api_client = api_client

        if self._api_client is not None:
            from client.remote_route_history import RemoteRouteHistoryService
            self.service = RemoteRouteHistoryService(self._api_client)
        else:
            self.service = RouteHistoryService(db) if db else None
        self.sort_by = "last_calculated_at"
        self.sort_dir = "DESC"
        self._preview_token = 0
        self._selected_route_id: int | None = None

        self.preview_loaded.connect(self._apply_preview)
        self._build_ui()
        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)
        self._load_page()

    # ── UI build ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["10"], 0, SP["10"], SP["10"])
        layout.setSpacing(SP["3"])

        # Header
        hdr = QWidget()
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(SP["1"])
        hdr.setFixedHeight(72)
        hdr_layout.addWidget(PageTitle(hdr, t("route_history.page_title", default="Route History")))
        hdr_layout.addWidget(Label(hdr, t("route_history.page_subtitle", default="Browse, compare, and re-use past routes"), role="secondary"))
        layout.addWidget(hdr)

        # Filter strip — compact, no card
        self._build_filter_bar(layout)

        # Main content: table card + map preview card
        self._build_main_split(layout)

        # Bottom bar
        self._build_footer(layout)

    def _build_filter_bar(self, layout: QVBoxLayout) -> None:
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, SP["2"], 0, SP["2"])
        bar_layout.setSpacing(SP["2"])

        self.e_search = DebouncedLineEdit(placeholder=t("route_history.search_placeholder"))
        self.e_search.returnPressed.connect(self._reset_and_load)
        self.e_search.debouncedTextChanged.connect(self._reset_and_load)
        bar_layout.addWidget(self.e_search)

        self.c_profile = QComboBox()
        self.c_profile.addItems(["", "truck", "truck_fast", "truck_cheap", "truck_safe", "truck_short"])
        self.c_profile.currentTextChanged.connect(lambda v: self._reset_and_load())
        bar_layout.addWidget(self.c_profile)

        self.e_truck = QLineEdit()
        self.e_truck.setPlaceholderText(t("route_history.truck_placeholder"))
        self.e_truck.returnPressed.connect(self._reset_and_load)
        bar_layout.addWidget(self.e_truck)

        self._archived_check = StyledCheckBox(bar, text=t("route_history.archived_checkbox"))
        self._archived_check.stateChanged.connect(lambda s: self._reset_and_load())
        bar_layout.addWidget(self._archived_check)

        apply_btn = Btn(bar, t("route_history.apply_button"), variant="secondary", command=self._reset_and_load)
        bar_layout.addWidget(apply_btn)
        reset_btn = Btn(bar, t("route_history.reset_button"), variant="secondary", command=self._reset_filters)
        bar_layout.addWidget(reset_btn)

        bar_layout.addStretch(1)
        layout.addWidget(bar)

    def _build_main_split(self, layout: QVBoxLayout) -> None:
        splitter = QSplitter(Qt.Horizontal)

        # Left: table in a Card with no padding
        table_card = Card(self, padding=False)
        table_card_layout = table_card.layout()
        columns = [
            ("origin", t("route_history.table_origin"), 100),
            ("destination", t("route_history.table_destination"), 100),
            ("last_calculated_at", t("route_history.table_datetime"), 100),
            ("truck", t("route_history.table_truck"), 100),
            ("distance_km", t("route_history.table_distance"), 100),
            ("duration_min", t("route_history.table_duration"), 100),
            ("profile", t("route_history.table_profile"), 100),
        ]
        self.table = StyledTableWidget(self, columns=columns)
        self.table.horizontalHeader().setStretchLastSection(False)
        for i in range(len(columns)):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.table.rowSelected.connect(self._on_row_selected)
        self.table.rowDoubleClicked.connect(lambda d: self._open_in_planner())
        table_card_layout.addWidget(self.table)
        splitter.addWidget(table_card)

        # Right: map preview in a Card
        preview_card = Card(self)
        preview_card.setMinimumWidth(280)
        pc_layout = preview_card.layout()

        # Map placeholder (empty state)
        self._map_placeholder = QLabel(t("route_history.map_loading"))
        self._map_placeholder.setProperty("role", "muted")
        self._map_placeholder.setAlignment(Qt.AlignCenter)
        self._map_placeholder.setMinimumHeight(200)
        pc_layout.addWidget(self._map_placeholder)

        # Map widget (lazy-created)
        self._map_widget = None

        # Route info
        self._route_info = QLabel("")
        self._route_info.setProperty("role", "secondary")
        self._route_info.setWordWrap(True)
        pc_layout.addWidget(self._route_info)

        # Stats
        self._stats_text = QLabel(t("route_history.loading_placeholder"))
        self._stats_text.setProperty("role", "muted")
        self._stats_text.setWordWrap(True)
        pc_layout.addWidget(self._stats_text)

        pc_layout.addStretch()
        splitter.addWidget(preview_card)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    def _build_footer(self, layout: QVBoxLayout) -> None:
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(SP["2"])

        # ── Group 1: Refresh, Open Route Planner ──
        refresh_btn = Btn(footer, t("route_history.refresh"), variant="secondary", command=self._load_page)
        footer_layout.addWidget(refresh_btn)

        planner_btn = Btn(footer, t("route_history.open_planner"), variant="secondary", command=self._open_in_planner)
        footer_layout.addWidget(planner_btn)

        footer_layout.addWidget(Divider(footer, vertical=True))

        # ── Group 2: Recalculate, Duplicate, Export JSON, Export CSV ──
        recalc_btn = Btn(footer, t("route_history.recalculate"), variant="secondary", command=self._recalculate)
        footer_layout.addWidget(recalc_btn)

        dup_btn = Btn(footer, t("route_history.duplicate_button"), variant="secondary", command=self._duplicate_route)
        footer_layout.addWidget(dup_btn)

        export_json_btn = Btn(footer, t("route_history.export_json"), variant="secondary", command=lambda: self._export_selected("json"))
        footer_layout.addWidget(export_json_btn)

        export_csv_btn = Btn(footer, t("route_history.export_csv"), variant="secondary", command=lambda: self._export_selected("csv"))
        footer_layout.addWidget(export_csv_btn)

        footer_layout.addWidget(Divider(footer, vertical=True))

        # ── Group 3: Archive, Delete ──
        archive_btn = Btn(footer, t("route_history.archive"), variant="secondary", command=self._archive_route)
        footer_layout.addWidget(archive_btn)

        delete_btn = Btn(footer, t("route_history.delete"), variant="danger", command=self._delete_route)
        footer_layout.addWidget(delete_btn)

        footer_layout.addStretch(1)
        layout.addWidget(footer)

    # ── Data loading ───────────────────────────────────────────────────────────

    def _load_page(self) -> None:
        if self.service is None:
            return
        try:
            rows = self.service.search_routes(
                search=self.e_search.text().strip(),
                truck=self.e_truck.text().strip(),
                profile=self.c_profile.currentText(),
                include_archived=self._archived_check.isChecked(),
                sort_by=self.sort_by,
                sort_dir=self.sort_dir,
            )
            data = []
            for r in rows:
                data.append({
                    "origin": getattr(r, "origin", ""),
                    "destination": getattr(r, "destination", ""),
                    "last_calculated_at": getattr(r, "last_calculated_at", ""),
                    "truck": getattr(r, "truck", ""),
                    "distance_km": str(getattr(r, "distance_km", "") or ""),
                    "duration_min": str(getattr(r, "duration_min", "") or ""),
                    "profile": getattr(r, "profile", ""),
                    "id": getattr(r, "id", None),
                })
            self.table.set_data(data)
            self._update_stats()
        except Exception:
            logger.exception("Failed to load route history")

    def _update_stats(self) -> None:
        try:
            stats = self.service.get_statistics()
            text = (
                f"{t('route_history.label_total', default='Total:')} {stats.get('total', 0)} | "
                f"{t('route_history.label_active', default='Active:')} {stats.get('active', 0)} | "
                f"{t('route_history.label_archived', default='Archived:')} {stats.get('archived', 0)}"
            )
            self._stats_text.setText(text)
        except Exception:
            self._stats_text.setText("")

    # ── Sorting ────────────────────────────────────────────────────────────────

    def _on_header_clicked(self, idx: int) -> None:
        col_id = self.table._column_ids[idx] if idx < len(self.table._column_ids) else ""
        col = SORT_COLUMN_MAP.get(col_id, "last_calculated_at")
        if self.sort_by == col:
            self.sort_dir = "ASC" if self.sort_dir == "DESC" else "DESC"
        else:
            self.sort_by = col
            self.sort_dir = "ASC"
        self._load_page()

    # ── Selection & preview ────────────────────────────────────────────────────

    def _on_row_selected(self, row_data: dict) -> None:
        route_id = row_data.get("id")
        if route_id is None:
            self._clear_preview()
            return
        self._selected_route_id = int(route_id)
        self._preview_token += 1
        token = self._preview_token

        def worker():
            record = self.service.load_route(self._selected_route_id)
            # ``Signal.emit`` is thread-safe — the slot connected above
            # runs in the GUI thread, where widget updates are valid.
            self.preview_loaded.emit(record, token)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _apply_preview(self, record: RouteHistoryRecord | None, token: int) -> None:
        if token != self._preview_token:
            return
        if not record:
            self._clear_preview()
            return
        self._show_route_info(record)
        self._show_map_preview(record)

    def _clear_preview(self) -> None:
        if self._map_widget:
            self._map_widget.clear_overlays()
        self._route_info.setText("")

    def _show_route_info(self, record: RouteHistoryRecord) -> None:
        dur = format_duration_minutes(getattr(record, "duration_min", 0) or 0)
        info = (
            f"{t('route_history.label_date', default='Date:')} {getattr(record, 'last_calculated_at', '')}\n"
            f"{t('route_history.label_truck', default='Truck:')} {getattr(record, 'truck', '')}\n"
            f"{t('route_history.label_distance', default='Distance:')} {getattr(record, 'distance_km', 0):,.0f} km\n"
            f"{t('route_history.label_duration', default='Duration:')} {dur}"
        )
        self._route_info.setText(info)

    def _show_map_preview(self, record: RouteHistoryRecord) -> None:
        geometry = getattr(record, "geometry", None)
        if not geometry:
            return
        if self._map_widget is None:
            self._create_map_widget()
        self._map_widget.clear_overlays()
        try:
            coords = [(float(p[0]), float(p[1])) for p in geometry]
            if coords:
                self._map_widget.add_polyline(coords, color=COLORS.get("accent", "#6366f1"))
                self._map_widget.fit_bounds(
                    coords[0][0], coords[0][1], coords[-1][0], coords[-1][1],
                )
        except Exception:
            logger.exception("Map preview render failed")

    def _create_map_widget(self) -> None:
        try:
            from ui.map.map_widget import MapWidget
            self._map_widget = MapWidget(self._map_placeholder.parentWidget())
            self._map_placeholder.parentWidget().layout().replaceWidget(
                self._map_placeholder, self._map_widget
            )
            self._map_placeholder.hide()
            self._map_placeholder.deleteLater()
            self._map_placeholder = None
        except Exception:
            logger.exception("Failed to create map preview widget")

    # ── Filters ────────────────────────────────────────────────────────────────

    def _reset_and_load(self) -> None:
        self._load_page()

    def _reset_filters(self) -> None:
        self.e_search.clear()
        self.c_profile.setCurrentIndex(0)
        self.e_truck.clear()
        self._archived_check.setChecked(False)
        self._reset_and_load()

    # ── Actions ────────────────────────────────────────────────────────────────

    def _open_in_planner(self) -> None:
        data = self.table.selected_row_data()
        if not data or not data.get("id"):
            return
        route_id = int(data["id"])
        record = self.service.load_route(route_id)
        if not record:
            return
        if self.controller and hasattr(self.controller, "_switch_module"):
            self.controller._switch_module("route_planner")
            rp = self.controller.app_shell.view_container.currentWidget()
            if hasattr(rp, "load_history_route"):
                QTimer.singleShot(100, lambda: rp.load_history_route(record))

    def _recalculate(self) -> None:
        data = self.table.selected_row_data()
        if not data or not data.get("id"):
            return
        res = self.service.duplicate_route(int(data["id"]))
        if res:
            QMessageBox.information(self, t("route_history.recalculated"), t("route_history.recalculated_msg"))
            self._load_page()

    def _duplicate_route(self) -> None:
        data = self.table.selected_row_data()
        if not data or not data.get("id"):
            return
        self.service.duplicate_route(int(data["id"]))
        self._load_page()

    def _archive_route(self) -> None:
        data = self.table.selected_row_data()
        if not data or not data.get("id"):
            return
        if QMessageBox.question(
            self, t("route_history.archive_confirm"),
            t("route_history.archive_confirm_msg"),
        ) == QMessageBox.Yes:
            self.service.archive_route(int(data["id"]))
            self._load_page()

    def _delete_route(self) -> None:
        data = self.table.selected_row_data()
        if not data or not data.get("id"):
            return
        if QMessageBox.question(
            self, t("route_history.delete_confirm"),
            t("route_history.delete_confirm_msg"),
        ) == QMessageBox.Yes:
            self.service.delete_route(int(data["id"]))
            self._clear_preview()
            self._load_page()

    def _export_selected(self, fmt: str = "json") -> None:
        data = self.table.selected_row_data()
        if not data or not data.get("id"):
            return
        ext = f".{fmt}"
        path, _ = QFileDialog.getSaveFileName(
            self, t("route_history.export_dialog"), "", f"{fmt.upper()} (*{ext})"
        )
        if not path:
            return
        payload = self.service.export_route(int(data["id"]), fmt)
        if fmt == "json":
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(payload or "")
        QMessageBox.information(self, t("route_history.exported"), t("route_history.exported_msg"))

    def _compare_selected(self) -> None:
        data = self.table.selected_row_data()
        if not data or not data.get("id"):
            return
        record = self.service.load_route(int(data["id"]))
        if not record:
            return
        if self.controller and hasattr(self.controller, "_switch_module"):
            self.controller._switch_module("route_planner")
            rp = self.controller.app_shell.view_container.currentWidget()
            if hasattr(rp, "load_history_route"):
                QTimer.singleShot(100, lambda: rp.load_history_route(record, draw=True))

    # ── i18n ───────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        QTimer.singleShot(0, self._refresh_translations)

    def _refresh_translations(self) -> None:
        for col_id, label_key, width in TABLE_COLUMNS:
            try:
                idx = list(TABLE_COLUMNS).index((col_id, label_key, width))
                item = self.table.horizontalHeaderItem(idx)
                if item:
                    item.setText(t(label_key))
            except Exception:
                pass

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        self._load_page()

    def shutdown(self) -> None:
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)
        if self._map_widget:
            with contextlib.suppress(Exception):
                self._map_widget.destroy()
            self._map_widget = None
