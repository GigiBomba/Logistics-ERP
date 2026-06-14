"""PySide6 route history browser.

Replaces ``ui/route_history_view.py``. Displays route history in a sortable
table with a map preview, async loading, and export/archive/delete actions.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QComboBox,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QFrame,
    QFileDialog,
    QMessageBox,
    QHeaderView,
)

from services.i18n import t, register_listener, unregister_listener
from services.route_history_service import RouteHistoryRecord, RouteHistoryService
from services.route_result_presenter import format_duration_minutes
from ui.widgets import (
    ActionButton,
    StyledCheckBox,
    StyledTableWidget,
)
from ui.theme import COLORS, S

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

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        controller=None,
    ):
        super().__init__(parent)
        self.db = db
        self.controller = controller

        self.service = RouteHistoryService(db) if db else None
        self.sort_by = "last_calculated_at"
        self.sort_dir = "DESC"
        self._preview_token = 0
        self._selected_route_id: Optional[int] = None

        self._build_ui()
        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)
        self._load_page()

    # ── UI build ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S["5"], S["4"], S["5"], S["4"])
        layout.setSpacing(S["3"])

        self._build_filter_bar(layout)
        self._build_main_split(layout)
        self._build_footer(layout)

    def _build_filter_bar(self, layout: QVBoxLayout) -> None:
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(S["2"])

        self.e_search = QLineEdit()
        self.e_search.setPlaceholderText(t("route_history.search_placeholder"))
        self.e_search.returnPressed.connect(self._reset_and_load)
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

        apply_btn = ActionButton(bar, t("route_history.apply_button"), self._reset_and_load, variant="secondary")
        bar_layout.addWidget(apply_btn)
        reset_btn = ActionButton(bar, t("route_history.reset_button"), self._reset_filters, variant="secondary")
        bar_layout.addWidget(reset_btn)

        bar_layout.addStretch(1)
        layout.addWidget(bar)

    def _build_main_split(self, layout: QVBoxLayout) -> None:
        splitter = QSplitter(Qt.Horizontal)

        # Left: table
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
        splitter.addWidget(self.table)

        # Right: preview
        preview = QWidget()
        preview.setMinimumWidth(280)
        prev_layout = QVBoxLayout(preview)
        prev_layout.setContentsMargins(S["3"], 0, 0, 0)
        prev_layout.setSpacing(S["2"])

        # Map placeholder
        self._map_placeholder = QLabel(t("route_history.map_loading"))
        self._map_placeholder.setProperty("fontRole", "muted")
        self._map_placeholder.setAlignment(Qt.AlignCenter)
        self._map_placeholder.setMinimumHeight(200)
        self._map_placeholder.setStyleSheet(
            f"background-color: {COLORS.get('bg_surface', '#18181b')};"
            f" border: 1px solid {COLORS.get('border', '#27272a')}; border-radius: 6px;"
        )
        prev_layout.addWidget(self._map_placeholder)

        # Map widget (lazy-created)
        self._map_widget = None

        # Route info
        self._route_info = QLabel("")
        self._route_info.setProperty("fontRole", "small")
        self._route_info.setWordWrap(True)
        prev_layout.addWidget(self._route_info)

        # Stats
        self._stats_text = QLabel(t("route_history.loading_placeholder"))
        self._stats_text.setProperty("fontRole", "helper")
        self._stats_text.setWordWrap(True)
        prev_layout.addWidget(self._stats_text)

        prev_layout.addStretch(1)
        splitter.addWidget(preview)
        splitter.setSizes([600, 300])
        layout.addWidget(splitter, 1)

    def _build_footer(self, layout: QVBoxLayout) -> None:
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(S["2"])

        # ── Group 1: Refresh, Open Route Planner ──
        refresh_btn = ActionButton(footer, t("route_history.refresh"), self._load_page, variant="secondary")
        refresh_btn.setFixedHeight(34)
        footer_layout.addWidget(refresh_btn)

        planner_btn = ActionButton(footer, t("route_history.open_planner"), self._open_in_planner, variant="secondary")
        planner_btn.setFixedHeight(34)
        footer_layout.addWidget(planner_btn)

        # spacer
        sp1 = QFrame()
        sp1.setFrameShape(QFrame.VLine)
        sp1.setFrameShadow(QFrame.Sunken)
        sp1.setFixedWidth(2)
        footer_layout.addWidget(sp1)

        # ── Group 2: Recalculate, Duplicate, Export JSON, Export CSV ──
        recalc_btn = ActionButton(footer, t("route_history.recalculate"), self._recalculate, variant="secondary")
        recalc_btn.setFixedHeight(34)
        footer_layout.addWidget(recalc_btn)

        dup_btn = ActionButton(footer, t("route_history.duplicate_button"), self._duplicate_route, variant="secondary")
        dup_btn.setFixedHeight(34)
        footer_layout.addWidget(dup_btn)

        export_json_btn = ActionButton(footer, t("route_history.export_json"), lambda: self._export_selected("json"), variant="secondary")
        export_json_btn.setFixedHeight(34)
        footer_layout.addWidget(export_json_btn)

        export_csv_btn = ActionButton(footer, t("route_history.export_csv"), lambda: self._export_selected("csv"), variant="secondary")
        export_csv_btn.setFixedHeight(34)
        footer_layout.addWidget(export_csv_btn)

        # spacer
        sp2 = QFrame()
        sp2.setFrameShape(QFrame.VLine)
        sp2.setFrameShadow(QFrame.Sunken)
        sp2.setFixedWidth(2)
        footer_layout.addWidget(sp2)

        # ── Group 3: Archive, Delete ──
        archive_btn = ActionButton(footer, t("route_history.archive"), self._archive_route, variant="secondary")
        archive_btn.setFixedHeight(34)
        footer_layout.addWidget(archive_btn)

        delete_btn = ActionButton(footer, t("route_history.delete"), self._delete_route, variant="danger")
        delete_btn.setFixedHeight(34)
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
                f"Total: {stats.get('total', 0)} | "
                f"Active: {stats.get('active', 0)} | "
                f"Archived: {stats.get('archived', 0)}"
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
            QTimer.singleShot(0, lambda: self._apply_preview(record, token))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _apply_preview(self, record: Optional[RouteHistoryRecord], token: int) -> None:
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
            f"Date: {getattr(record, 'last_calculated_at', '')}\n"
            f"Truck: {getattr(record, 'truck', '')}\n"
            f"Distance: {getattr(record, 'distance_km', 0):,.0f} km\n"
            f"Duration: {dur}"
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
                idx = [c for c in TABLE_COLUMNS].index((col_id, label_key, width))
                item = self.table.horizontalHeaderItem(idx)
                if item:
                    item.setText(t(label_key))
            except Exception:
                pass

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        self._load_page()

    def shutdown(self) -> None:
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
        if self._map_widget:
            try:
                self._map_widget.destroy()
            except Exception:
                pass
            self._map_widget = None
