"""QtServiceTimelineWidget — PySide6 maintenance timeline.

Replaces ``ui/widgets/service_timeline_widget.py``. Shows a vertical timeline
of maintenance records with coloured dots and connecting lines, inside a
QScrollArea.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.icons import iconed
from services.fleet_maintenance_service import (
    FleetMaintenanceService,
    MaintType,
    MAINT_DISPLAY,
    MAINT_ICONS,
)
from ui.theme import COLORS, S
from ui.qt_styles import Theme
from ui.qt_widgets import ActionButton


NODE_COLORS = {
    MaintType.TIRE_REPLACEMENT: COLORS["text_muted"],
    MaintType.OIL_CHANGE: COLORS["warning"],
    MaintType.BRAKES: COLORS["danger"],
}
DEFAULT_NODE_COLOR = COLORS["text_muted"]
LINE_COLOR = Theme.SURFACE2
NODE_RADIUS = 7


class QtServiceTimelineWidget(QWidget):
    """Vertical timeline of maintenance records with coloured dots.

    Displays maintenance records in chronological order (newest first),
    each represented by a coloured dot on the left and detail text on the
    right.  Nodes are clickable — invokes the ``on_edit_record`` callback
    or opens a detail dialog.
    """

    def __init__(
        self,
        parent: Optional[QWidget],
        service: FleetMaintenanceService,
        truck_id: int,
        truck_plate: str,
        on_edit_record: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        super().__init__(parent)
        self.service = service
        self.truck_id = truck_id
        self.truck_plate = truck_plate
        self.on_edit_record = on_edit_record

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._build()

    # ── Colour helper ────────────────────────────────────────────────────────

    def _node_color(self, maint_type: str) -> str:
        try:
            return NODE_COLORS.get(MaintType(maint_type), DEFAULT_NODE_COLOR)
        except ValueError:
            return DEFAULT_NODE_COLOR

    # ── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        # -- Header -----------------------------------------------------------
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(S["2"], S["2"], S["2"], S["2"])
        header_layout.setSpacing(0)

        self._header_title_label = QLabel(iconed("maint_timeline.title"))
        self._header_title_label.setProperty("fontRole", "small")
        header_layout.addWidget(self._header_title_label)
        header_layout.addStretch(1)

        refresh_btn = ActionButton(
            header, iconed("maint.refresh"), self.refresh, variant="ghost",
        )
        header_layout.addWidget(refresh_btn)

        self._layout.addWidget(header)

        # -- Scroll area ------------------------------------------------------
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(S["2"], 0, S["2"], 0)
        self._scroll_layout.setSpacing(0)
        self._scroll_layout.setAlignment(Qt.AlignTop)

        self._scroll_area.setWidget(self._scroll_content)
        self._layout.addWidget(self._scroll_area, 1)

        # -- Load data --------------------------------------------------------
        self.refresh()

    # ── Public API ───────────────────────────────────────────────────────────

    def refresh(self):
        """Reload records from the service and rebuild the timeline."""
        self._clear_scroll()

        records = self.service.get_records(truck_id=self.truck_id, limit=1000)
        records.sort(key=lambda r: r.get("date", ""), reverse=True)

        if not records:
            empty_label = QLabel(iconed("maint.no_records"))
            empty_label.setProperty("fontRole", "muted")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setFixedHeight(120)
            self._scroll_layout.addWidget(empty_label)
            return

        for idx, rec in enumerate(records):
            self._draw_node(rec, is_last=(idx == len(records) - 1))

    def refresh_translations(self):
        """Update displayed strings after a locale change."""
        self._header_title_label.setText(iconed("maint_timeline.title"))

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _clear_scroll(self):
        while self._scroll_layout.count():
            item = self._scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    # ── Node drawing ─────────────────────────────────────────────────────────

    def _draw_node(self, rec: Dict[str, Any], is_last: bool = False):
        """Build a single timeline node row and append it to the scroll layout."""
        node_frame = QWidget()
        node_layout = QHBoxLayout(node_frame)
        node_layout.setContentsMargins(0, 0, 0, 0)
        node_layout.setSpacing(S["2"])

        # -- Left column: coloured dot ----------------------------------------
        left_col = QWidget()
        left_col.setFixedWidth(40)
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.setAlignment(Qt.AlignTop)

        color = self._node_color(rec["maintenance_type"])
        dot_size = NODE_RADIUS * 2

        # Outer wrapper to give the dot a little top breathing room
        dot_wrapper = QWidget()
        dot_wrapper_layout = QVBoxLayout(dot_wrapper)
        dot_wrapper_layout.setContentsMargins(0, S["1"], 0, 0)
        dot_wrapper_layout.setSpacing(0)
        dot_wrapper_layout.setAlignment(Qt.AlignCenter)

        dot = QFrame()
        dot.setFixedSize(dot_size, dot_size)
        dot.setStyleSheet(
            f"background-color: {color}; border-radius: {NODE_RADIUS}px;"
            f"border: 1px solid {Theme.SURFACE2};"
        )
        dot_wrapper_layout.addWidget(dot)
        left_layout.addWidget(dot_wrapper)

        node_layout.addWidget(left_col)

        # -- Right column: content --------------------------------------------
        content = QWidget()
        content.setCursor(Qt.PointingHandCursor)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, S["1"], 0, S["1"])
        content_layout.setSpacing(2)

        # Date
        date_str = rec.get("date", "")[:10] if rec.get("date") else ""
        date_label = QLabel(date_str)
        date_label.setProperty("fontRole", "small")
        content_layout.addWidget(date_label)

        # Type icon + display label
        try:
            icon = MAINT_ICONS.get(MaintType(rec["maintenance_type"]), "\u2699\uFE0F")
            disp = MAINT_DISPLAY.get(
                MaintType(rec["maintenance_type"]),
                rec["maintenance_type"].replace("_", " ").title(),
            )
        except ValueError:
            icon = "\u2699\uFE0F"
            disp = rec["maintenance_type"].replace("_", " ").title()
        type_label = QLabel(f"{icon} {disp}")
        type_label.setProperty("fontRole", "muted")
        content_layout.addWidget(type_label)

        # Cost / provider info
        parts = []
        cost = rec.get("cost")
        if cost is not None:
            parts.append(f"\u20AC{float(cost):.2f}")
        provider = rec.get("service_provider", "") or ""
        if provider:
            parts.append(provider)
        notes = rec.get("notes", "") or ""
        if notes and not provider:
            parts.append(notes[:50])
        if parts:
            detail_label = QLabel("  |  ".join(parts))
            detail_label.setProperty("fontRole", "muted")
            content_layout.addWidget(detail_label)

        if notes and provider:
            notes_label = QLabel(notes[:60])
            notes_label.setProperty("fontRole", "muted")
            content_layout.addWidget(notes_label)

        # -- Click handling ---------------------------------------------------
        content.mousePressEvent = lambda e, r=rec: self._on_node_click(r)  # type: ignore[assignment]

        node_layout.addWidget(content, 1)

        self._scroll_layout.addWidget(node_frame)

        # -- Connecting line between nodes ------------------------------------
        if not is_last:
            line_container = QWidget()
            line_container.setFixedWidth(40)
            line_container.setFixedHeight(14)
            line_container.setSizePolicy(
                QSizePolicy.Fixed, QSizePolicy.Fixed,
            )
            line_layout = QVBoxLayout(line_container)
            line_layout.setContentsMargins(0, 0, 0, 0)
            line_layout.setSpacing(0)
            line_layout.setAlignment(Qt.AlignCenter)

            line = QFrame()
            line.setFixedWidth(2)
            line.setFixedHeight(14)
            line.setProperty("role", "divider")
            line.setStyleSheet(f"background-color: {LINE_COLOR};")
            line_layout.addWidget(line)

            self._scroll_layout.addWidget(line_container)

    # ── Click handling ───────────────────────────────────────────────────────

    def _on_node_click(self, rec: Dict[str, Any]):
        """Handle a click on a timeline node."""
        if self.on_edit_record:
            self.on_edit_record(rec)
        else:
            self._show_detail_popup(rec)

    def _show_detail_popup(self, rec: Dict[str, Any]):
        """Display a detail dialog for a maintenance record."""
        dlg = QDialog(self)
        dlg.setWindowTitle(iconed("maint_timeline.detail_title"))
        dlg.setFixedSize(420, 300)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(S["5"], S["4"], S["5"], S["4"])
        layout.setSpacing(S["3"])

        date_str = rec.get("date", "")[:10] if rec.get("date") else t("common.na")
        try:
            disp = MAINT_DISPLAY.get(
                MaintType(rec["maintenance_type"]), rec["maintenance_type"],
            )
        except ValueError:
            disp = rec["maintenance_type"]

        rows = [
            (iconed("maint_timeline.field_date"), date_str),
            (iconed("maint_timeline.field_type"), disp),
            (
                iconed("maint_timeline.field_cost"),
                f"\u20AC{float(rec['cost']):.2f}"
                if rec.get("cost") is not None
                else t("common.na"),
            ),
            (
                iconed("maint_timeline.field_km"),
                f"{float(rec['km']):,.0f}"
                if rec.get("km")
                else t("common.na"),
            ),
            (
                iconed("maint_timeline.field_provider"),
                rec.get("service_provider", "") or t("common.na"),
            ),
            (
                iconed("maint_timeline.field_notes"),
                rec.get("notes", "") or t("common.na"),
            ),
        ]
        for label, val in rows:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(S["2"])

            label_w = QLabel(label)
            label_w.setProperty("fontRole", "muted")
            label_w.setFixedWidth(100)
            row_layout.addWidget(label_w)

            val_w = QLabel(str(val))
            val_w.setProperty("fontRole", "small")
            val_w.setWordWrap(True)
            row_layout.addWidget(val_w, 1)

            layout.addWidget(row)

        layout.addStretch(1)

        close_btn = ActionButton(dlg, iconed("maint.cancel"), dlg.accept,
                                 variant="secondary")
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)

        dlg.exec()
