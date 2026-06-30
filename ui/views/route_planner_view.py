"""PySide6 route planner view.

Replaces ``ui/route_planner.py``. Uses ``MapWidget`` for the map and
``RoutePlannerController`` for business logic. Fully embedded as a QWidget.
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services.fleet_service import FleetService
from services.i18n import register_listener, t, unregister_listener
from services.operations.event_bus import (
    TRUCK_CREATED,
    TRUCK_DELETED,
    TRUCK_UPDATED,
    EventBus,
)
from services.route_history_service import RouteHistoryRecord, RouteHistoryService
from services.route_persistence import RoutePersistenceService
from services.route_planner_controller import RoutePlannerController
from services.route_profiles import GRAPHHOPPER_PROFILES
from services.route_result_presenter import format_history_loaded_info
from services.route_state import RouteStateManager
from services.stop_factory import normalize_existing_stop
from ui.components import (
    Btn,
    Label,
    PageTitle,
    get_icon,
)
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_HOVER,
    COLOR_BG_BASE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    FONT_SIZE_SM,
    FONT_SIZE_BASE,
    FONT_SIZE_MD,
    FONT_SIZE_LG,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD,
    FONT_WEIGHT_REGULAR,
    SP,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
)
from ui.map import MapWidget, QtRouteMapRenderer
from ui.theme import COLORS
from ui.widgets import (
    StyledComboBox,
)

logger = logging.getLogger(__name__)


def make_section_header(text: str) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 20, 0, 10)
    layout.setSpacing(8)

    label = QLabel(text.upper())
    label.setStyleSheet(
        f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; font-weight: 600; letter-spacing: 0.08em;"
    )

    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {COLOR_BORDER_SUBTLE};")

    layout.addWidget(label)
    layout.addWidget(line, 1)
    return container


def make_toggle_row(label_text: str, checked: bool = False) -> QCheckBox:
    cb = QCheckBox(label_text)
    cb.setChecked(checked)
    cb.setFixedHeight(28)
    cb.setStyleSheet(f"""
        QCheckBox {{
            color: {COLOR_TEXT_SECONDARY};
            font-size: 12px;
            font-weight: {FONT_WEIGHT_REGULAR};
            spacing: 8px;
        }}
        QCheckBox:hover {{ color: {COLOR_TEXT_PRIMARY}; }}
        QCheckBox::indicator {{
            width: 16px; height: 16px;
            border-radius: 4px;
            border: 1px solid {COLOR_BORDER_MEDIUM};
            background: {COLOR_BG_OVERLAY};
        }}
        QCheckBox::indicator:checked {{
            background: {COLOR_ACCENT_PRIMARY};
            border-color: {COLOR_ACCENT_PRIMARY};
        }}
        QCheckBox::indicator:hover {{ border-color: {COLOR_ACCENT_PRIMARY}; }}
    """)
    return cb


def make_result_pill(value: str, label: str) -> QFrame:
    pill = QFrame()
    pill.setFixedHeight(48)
    pill.setStyleSheet(f"""
        QFrame {{
            background: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: 6px;
        }}
    """)
    pl = QVBoxLayout(pill)
    pl.setContentsMargins(10, 6, 10, 6)
    pl.setSpacing(2)

    val_lbl = QLabel(value)
    val_lbl.setStyleSheet(
        f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: {FONT_WEIGHT_SEMIBOLD}; border: none; background: transparent;"
    )
    lbl_w = QLabel(label)
    lbl_w.setStyleSheet(
        f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; border: none; background: transparent;"
    )

    pl.addWidget(val_lbl)
    pl.addWidget(lbl_w)
    pill.value_label = val_lbl
    return pill


class WaypointRow(QWidget):
    def __init__(self, placeholder: str, dot_color: str,
                 show_remove: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"""
            background-color: {dot_color};
            border-radius: 5px;
        """)

        self.field = QLineEdit()
        self.field.setPlaceholderText(placeholder)
        self.field.setFixedHeight(32)
        self.field.setStyleSheet(f"""
            QLineEdit {{
                background: {COLOR_BG_OVERLAY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: 4px;
                color: {COLOR_TEXT_PRIMARY};
                font-size: 12px;
                padding: 0 10px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLOR_ACCENT_PRIMARY};
                background: {COLOR_BG_OVERLAY};
            }}
            QLineEdit::placeholder {{
                color: {COLOR_TEXT_TERTIARY};
            }}
        """)

        layout.addWidget(dot)
        layout.addWidget(self.field, 1)

        if show_remove:
            remove_btn = QPushButton("\u00d7")
            remove_btn.setFixedSize(20, 20)
            remove_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLOR_TEXT_TERTIARY};
                    border: none;
                    font-size: 14px;
                    font-weight: 400;
                    border-radius: 3px;
                }}
                QPushButton:hover {{
                    color: {COLOR_TEXT_PRIMARY};
                    background: {COLOR_BG_HOVER};
                }}
            """)
            layout.addWidget(remove_btn)
            self.remove_btn = remove_btn


class WaypointConnector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QColor(COLOR_BORDER_MEDIUM))
        line_x = 5
        painter.drawLine(line_x, 0, line_x, self.height())
        painter.end()


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing if spacing >= 0 else 4)
        self._items = []

    def __del__(self):
        while self._items:
            item = self._items.pop()

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x() + self.contentsMargins().left()
        y = rect.y() + self.contentsMargins().top()
        line_height = 0
        spacing = self.spacing()

        for item in self._items:
            widget = item.widget()
            if widget is None:
                continue
            space_x = spacing
            space_y = spacing
            next_x = x + widget.sizeHint().width() + space_x
            if next_x - space_x > rect.right() + 1 and line_height > 0:
                x = rect.x() + self.contentsMargins().left()
                y += line_height + space_y
                next_x = x + widget.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                widget.setGeometry(QRect(QPoint(x, y), widget.sizeHint()))
            x = next_x
            line_height = max(line_height, widget.sizeHint().height())

        return y + line_height - rect.y() + self.contentsMargins().bottom()


def make_country_chip(country_code: str) -> QWidget:
    chip = QWidget()
    chip.setFixedHeight(22)
    chip.setStyleSheet(f"""
        background: {COLOR_BG_OVERLAY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: 11px;
    """)
    row = QHBoxLayout(chip)
    row.setContentsMargins(8, 0, 6, 0)
    row.setSpacing(4)

    lbl = QLabel(country_code)
    lbl.setStyleSheet(
        f"color: {COLOR_TEXT_PRIMARY}; font-size: 10px; font-weight: 600; background: transparent; border: none;"
    )
    remove = QPushButton("\u00d7")
    remove.setFixedSize(14, 14)
    remove.setStyleSheet(f"""
        QPushButton {{
            background: transparent; border: none;
            color: {COLOR_TEXT_TERTIARY}; font-size: 11px;
        }}
        QPushButton:hover {{ color: {COLOR_ERROR_DEFAULT}; }}
    """)
    row.addWidget(lbl)
    row.addWidget(remove)
    chip.remove_btn = remove
    return chip


LEAFLET_DARK_CSS = """
.leaflet-control-zoom {
    border: none !important;
    box-shadow: none !important;
}
.leaflet-control-zoom a {
    background-color: #141416 !important;
    color: #F0F0F3 !important;
    border: 1px solid #2A2A30 !important;
    border-radius: 6px !important;
    width: 28px !important;
    height: 28px !important;
    line-height: 28px !important;
    font-size: 16px !important;
    font-weight: 400 !important;
    display: block !important;
    margin-bottom: 4px !important;
    text-align: center !important;
    transition: background 0.1s ease;
}
.leaflet-control-zoom a:hover {
    background-color: #222226 !important;
    color: #6366F1 !important;
    border-color: #38383F !important;
}
.leaflet-control-attribution {
    background: rgba(20, 20, 22, 0.7) !important;
    color: #5A5A6E !important;
    font-size: 9px !important;
    border-top-left-radius: 4px !important;
    padding: 2px 6px !important;
}
.leaflet-control-attribution a { color: #6366F1 !important; }
"""


class QtRoutePlannerView(QWidget):
    """Route planner with sidebar controls and an interactive map."""

    SIDEBAR_MIN_WIDTH = 300

    # Emitted from the route runner's worker thread when the calculation
    # completes.  ``Signal.emit`` is thread-safe — Qt queues the slot call
    # on the GUI thread, so we can safely touch widgets from the receiver.
    # (Previously we used ``QTimer.singleShot(0, ...)`` from the worker,
    # which created the timer in the *worker* thread — its event loop
    # never ran, so the result was never delivered to the GUI and the
    # "Calculating…" state hung forever.)
    route_result_received = Signal(object, object, int)   # result, ctx, token

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        controller=None,
    ):
        super().__init__(parent)
        self.db = db
        self.controller = controller  # MainWindow reference for module switching

        self._core = RoutePlannerController(db)
        self.route_history_service = RouteHistoryService(db)
        self.route_state = RouteStateManager(db)
        self.fleet_service = FleetService(db)
        self._persistence = RoutePersistenceService(
            self.route_history_service,
            self.route_state,
            self._core.cost_engine,
        )
        self._core.bind_persistence(self._persistence)

        self.profile_map = GRAPHHOPPER_PROFILES
        self._profile_key_to_display: dict[str, str] = {}
        self._profile_display_to_key: dict[str, str] = {}

        self.stop_vars: dict[str, str] = {}
        self._stop_rows: dict[int, QWidget] = {}
        self._stop_ids: dict[int, str] = {}
        self._waypoint_fields: dict[str, QLineEdit] = {}
        self._trucks_map: dict[str, Any] = {}
        self._truck_label_to_id: dict[str, str] = {}
        self._selected_truck_id: str | None = None

        self._last_route_result: dict[str, Any] | None = None
        self._last_route_history_id: int | None = None
        self._last_route_calc_ctx = None
        self._pending_clear = False
        self._calc_token = 0
        self._dispatch_frame: QWidget | None = None

        # Wire the cross-thread signal that delivers the route result
        # from the runner's worker thread to ``_on_route_result`` on the
        # GUI thread.  Queued connection is the default for cross-thread
        # signal/slot — exactly what we want.
        self.route_result_received.connect(self._on_route_result)

        self.stops_state = [
            normalize_existing_stop({"type": "start"}),
            normalize_existing_stop({"type": "destination"}),
        ]

        self._build_ui()
        self._render_stops_list()

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        # Subscribe to truck events so changes in the Fleet Manager
        # (or anywhere else) refresh this view's dropdown without an
        # app restart.  We unsubscribe in ``shutdown``.
        self._event_bus = EventBus()
        self._event_bus.subscribe(TRUCK_CREATED, self._on_truck_event)
        self._event_bus.subscribe(TRUCK_UPDATED, self._on_truck_event)
        self._event_bus.subscribe(TRUCK_DELETED, self._on_truck_event)
        self._event_subscribed = True

    def _on_truck_event(self, _event_data: Any) -> None:
        """Refresh the truck dropdown when a truck is created,
        updated, or deleted elsewhere.  Keeps the user's current
        selection if the truck is still in the list."""
        if not getattr(self, "_event_subscribed", False):
            return
        previous_id = self._selected_truck_id
        self._load_trucks()
        # Try to restore the previous selection so an unrelated
        # update (e.g. a plate typo fix) doesn't drop the user's
        # in-flight selection.
        if previous_id:
            for i in range(self.truck_combo.count()):
                if self.truck_combo.itemData(i) == previous_id:
                    self.truck_combo.setCurrentIndex(i)
                    break

    # ── UI construction ────────────────────────────────────────────────────────

    LEAFLET_CSS_INJECTED = False

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setContentsMargins(40, 0, 40, 0)
        hdr_layout.setSpacing(SP["1"])
        hdr.setFixedHeight(72)
        hdr_layout.addWidget(PageTitle(hdr, t("route.page_title", default="Route Planner")))
        hdr_layout.addWidget(Label(hdr, t("route.page_subtitle", default="Plan and optimise routes"), role="secondary"))
        outer.addWidget(hdr)

        self._content_widget = QWidget()
        content = QHBoxLayout(self._content_widget)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)

        # ── Left Panel (TASK 1) ──
        panel = QFrame()
        panel.setFixedWidth(340)
        panel.setObjectName("route_panel")
        panel.setStyleSheet(f"""
            QFrame#route_panel {{
                background-color: {COLOR_BG_ELEVATED};
                border-right: 1px solid {COLOR_BORDER_SUBTLE};
            }}
        """)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        # Scrollable content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ width: 4px; background: transparent; }}
            QScrollBar::handle:vertical {{ background: {COLOR_BORDER_MEDIUM}; border-radius: 2px; min-height: 20px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(16, 16, 16, 12)
        scroll_layout.setSpacing(0)
        scroll_area.setWidget(scroll_content)

        # Pinned button bar (never scrolls)
        button_bar = QWidget()
        button_bar.setFixedHeight(88)
        button_bar.setStyleSheet(f"background: {COLOR_BG_ELEVATED}; border-top: 1px solid {COLOR_BORDER_SUBTLE};")
        button_bar_layout = QVBoxLayout(button_bar)
        button_bar_layout.setContentsMargins(16, 12, 16, 12)
        button_bar_layout.setSpacing(6)

        panel_layout.addWidget(scroll_area, 1)
        panel_layout.addWidget(button_bar, 0)

        self._panel = panel
        self._scroll_layout = scroll_layout
        self._button_bar_layout = button_bar_layout

        content.addWidget(panel)

        # Map
        self.map_widget = MapWidget(self._content_widget)
        self._map_renderer = QtRouteMapRenderer(self.map_widget)
        self.map_widget.set_click_callback(self._on_map_click)
        self.map_widget.setMinimumWidth(1)
        self._click_to_add_enabled = False
        content.addWidget(self.map_widget, 1)

        outer.addWidget(self._content_widget, 1)

        # Inject dark Leaflet CSS after map loads
        self.map_widget.loadFinished.connect(self._inject_map_styles)

        # Build sidebar content
        self._build_sidebar_content(scroll_layout, button_bar_layout)

    def _build_sidebar_content(self, sl: QVBoxLayout, bl: QVBoxLayout) -> None:
        # ── TASK 2: Section Header — ROUTE ──
        sl.addWidget(make_section_header(t("route.section.smart_route", default="RUTĂ INTELIGENTĂ")))

        # ── TASK 3: Waypoint Inputs ──
        self._stops_container = QWidget()
        self._stops_container_layout = QVBoxLayout(self._stops_container)
        self._stops_container_layout.setContentsMargins(0, 0, 0, 0)
        self._stops_container_layout.setSpacing(0)
        self._stops_container_layout.setAlignment(Qt.AlignTop)
        sl.addWidget(self._stops_container)

        # "+ Adaugă Stop" button
        add_stop_btn = QPushButton(f"+ {t('route.add_stop')}")
        add_stop_btn.setFixedHeight(28)
        add_stop_btn.setCursor(Qt.PointingHandCursor)
        add_stop_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLOR_ACCENT_PRIMARY};
                border: none;
                font-size: 11px;
                font-weight: {FONT_WEIGHT_MEDIUM};
                text-align: left;
                padding-left: 18px;
            }}
            QPushButton:hover {{
                color: {COLOR_ACCENT_HOVER};
            }}
        """)
        add_stop_btn.clicked.connect(self._add_stop_field)
        sl.addWidget(add_stop_btn)

        # Remove "Elimină Stop" — removal is via × on each waypoint row

        # ── TASK 4: Options Section ──
        sl.addWidget(make_section_header(t("route.section.options", default="OPȚIUNI")))

        # Truck selector: label + [combo + refresh button]
        truck_label = QLabel(t("route.select_truck"))
        truck_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: {FONT_WEIGHT_MEDIUM};")
        sl.addWidget(truck_label)

        truck_combo_row = QWidget()
        tcr_layout = QHBoxLayout(truck_combo_row)
        tcr_layout.setContentsMargins(0, 0, 0, 0)
        tcr_layout.setSpacing(4)

        self.truck_combo = StyledComboBox()
        self.truck_combo.setFixedHeight(32)
        self.truck_combo.setStyleSheet(f"""
            QComboBox {{
                background: {COLOR_BG_OVERLAY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: 4px;
                color: {COLOR_TEXT_PRIMARY};
                font-size: 12px;
                padding: 0 10px;
            }}
            QComboBox:focus {{ border-color: {COLOR_ACCENT_PRIMARY}; }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox::down-arrow {{ width: 12px; height: 12px; }}
            QComboBox QAbstractItemView {{
                background: {COLOR_BG_OVERLAY};
                border: 1px solid {COLOR_BORDER_MEDIUM};
                border-radius: 6px;
                color: {COLOR_TEXT_PRIMARY};
                selection-background-color: {COLOR_BG_HOVER};
            }}
        """)
        self.truck_combo.currentIndexChanged.connect(self._on_truck_selected)
        tcr_layout.addWidget(self.truck_combo, 1)

        self._truck_refresh_btn = QPushButton("\u21bb")
        self._truck_refresh_btn.setFixedSize(28, 28)
        self._truck_refresh_btn.setToolTip(t("common.refresh", default="Refresh"))
        self._truck_refresh_btn.setCursor(Qt.PointingHandCursor)
        self._truck_refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLOR_TEXT_TERTIARY};
                border: none;
                font-size: 14px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                color: {COLOR_TEXT_PRIMARY};
                background: {COLOR_BG_HOVER};
            }}
        """)
        self._truck_refresh_btn.clicked.connect(self._load_trucks)
        tcr_layout.addWidget(self._truck_refresh_btn)

        sl.addWidget(truck_combo_row)
        sl.addSpacing(12)

        # Route profile
        profile_label = QLabel(t("route.profile_label"))
        profile_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: {FONT_WEIGHT_MEDIUM};")
        sl.addWidget(profile_label)

        self._rebuild_profile_display_names()
        self.profile_combo = StyledComboBox(values=list(self._profile_key_to_display.values()))
        self.profile_combo.setFixedHeight(32)
        self.profile_combo.setStyleSheet(self.truck_combo.styleSheet())
        self.profile_combo.setCurrentText(self._profile_key_to_display.get("Recommended", "Recommended"))
        sl.addWidget(self.profile_combo)

        # ── TASK 5: Excluded Countries as Chips ──
        sl.addWidget(make_section_header(t("route.section.excluded_countries", default="ȚĂRI EXCLUSE")))

        self._chips_container = QWidget()
        self._chips_container.setStyleSheet("background: transparent;")
        self._chips_container_layout = QVBoxLayout(self._chips_container)
        self._chips_container_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_container_layout.setSpacing(4)
        sl.addWidget(self._chips_container)

        add_country_btn = QPushButton(f"+ {t('route.add_country', default='Adaugă țară')}")
        add_country_btn.setCursor(Qt.PointingHandCursor)
        add_country_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {COLOR_ACCENT_PRIMARY}; font-size: 11px; font-weight: {FONT_WEIGHT_MEDIUM};
                text-align: left; padding: 4px 0;
            }}
            QPushButton:hover {{ color: {COLOR_ACCENT_HOVER}; }}
        """)
        add_country_btn.clicked.connect(self._open_country_selector)
        sl.addWidget(add_country_btn)

        # ── TASK 6: Toggle Checkboxes ──
        sl.addSpacing(16)

        self._compare_check = make_toggle_row(t("route.show_comparison"), checked=True)
        self._compare_check.stateChanged.connect(self._toggle_comparison)
        sl.addWidget(self._compare_check)
        sl.addSpacing(4)

        self._click_add_check = make_toggle_row(t("route.click_to_add_stop"), checked=False)
        self._click_add_check.stateChanged.connect(self._on_click_add_changed)
        sl.addWidget(self._click_add_check)

        # ── TASK 7: Route Result Panel ──
        sl.addSpacing(20)
        sl.addWidget(make_section_header(t("route.section.result", default="REZULTAT RUTĂ")))

        self._result_stack = QStackedWidget()

        # Page 0: Empty state
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setContentsMargins(0, 16, 0, 8)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(6)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon("mdi6.map-marker-path", color=COLOR_TEXT_TERTIARY).pixmap(28, 28))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_lbl = QLabel(t("route.info_placeholder", default="Info rută va apărea aici."))
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px; font-weight: {FONT_WEIGHT_MEDIUM};")

        sub_lbl = QLabel(t("route.info_empty_subtitle", default="Calculați o rută pentru detalii."))
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px;")

        empty_layout.addWidget(icon_lbl)
        empty_layout.addWidget(title_lbl)
        empty_layout.addWidget(sub_lbl)

        self._empty_error_label = QLabel("")
        self._empty_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_error_label.setWordWrap(True)
        self._empty_error_label.setStyleSheet(f"color: {COLORS.get('danger', '#ef4444')}; font-size: 12px;")
        self._empty_error_label.hide()
        empty_layout.addWidget(self._empty_error_label)

        self._result_stack.addWidget(empty_page)

        # Page 1: Loading state
        loading_page = QWidget()
        loading_layout = QVBoxLayout(loading_page)
        loading_layout.setContentsMargins(0, 16, 0, 8)
        loading_layout.setSpacing(8)

        self._loading_bar = QProgressBar()
        self._loading_bar.setRange(0, 0)
        self._loading_bar.setFixedHeight(4)
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {COLOR_BG_OVERLAY};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {COLOR_ACCENT_PRIMARY};
                border-radius: 2px;
            }}
        """)
        loading_layout.addWidget(self._loading_bar)

        loading_text = QLabel(t("route.calculating", default="Se calculează ruta..."))
        loading_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_text.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 12px;")
        loading_layout.addWidget(loading_text)
        loading_layout.addStretch()
        self._result_stack.addWidget(loading_page)

        # Page 2: Populated result
        result_page = QWidget()
        result_layout = QVBoxLayout(result_page)
        result_layout.setContentsMargins(0, 8, 0, 0)
        result_layout.setSpacing(8)

        self.route_summary_label = QLabel()
        self.route_summary_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
        result_layout.addWidget(self.route_summary_label)

        # Grid of 4 metric pills
        pills_grid = QGridLayout()
        pills_grid.setSpacing(6)

        self.pill_distance = make_result_pill("\u2014", t("route.result.distance", default="Distanță"))
        self.pill_duration = make_result_pill("\u2014", t("route.result.duration", default="Durată"))
        self.pill_fuel_cost = make_result_pill("\u2014", t("route.result.fuel_cost", default="Cost combustibil"))
        self.pill_rate = make_result_pill("\u2014", t("route.result.cost_per_km", default="Cost/km"))

        pills_grid.addWidget(self.pill_distance, 0, 0)
        pills_grid.addWidget(self.pill_duration, 0, 1)
        pills_grid.addWidget(self.pill_fuel_cost, 1, 0)
        pills_grid.addWidget(self.pill_rate, 1, 1)

        result_layout.addLayout(pills_grid)

        # Compliance texts
        self._summary_text = QLabel("")
        self._summary_text.setWordWrap(True)
        self._summary_text.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
        result_layout.addWidget(self._summary_text)

        self._explanation_text = QLabel("")
        self._explanation_text.setWordWrap(True)
        self._explanation_text.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;")
        result_layout.addWidget(self._explanation_text)

        self._dispatch_container = QWidget()
        self._dispatch_container_layout = QVBoxLayout(self._dispatch_container)
        self._dispatch_container_layout.setContentsMargins(0, 0, 0, 0)
        self._dispatch_container_layout.setSpacing(SPACE_2)
        self._dispatch_container.hide()
        result_layout.addWidget(self._dispatch_container)

        result_layout.addStretch()
        self._result_stack.addWidget(result_page)

        sl.addWidget(self._result_stack)
        sl.addStretch(1)

        # ── TASK 8: Pinned Bottom Button Bar ──
        self.calc_btn = QPushButton(t("route.calculate", default="Calculează Ruta"))
        self.calc_btn.setFixedHeight(36)
        self.calc_btn.setObjectName("calc_route_btn")
        self.calc_btn.setCursor(Qt.PointingHandCursor)
        self.calc_btn.setEnabled(False)
        self.calc_opacity = QGraphicsOpacityEffect()
        self.calc_opacity.setOpacity(0.4)
        self.calc_btn.setGraphicsEffect(self.calc_opacity)
        self.calc_btn.setStyleSheet(f"""
            QPushButton#calc_route_btn {{
                background: {COLOR_ACCENT_PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: {FONT_WEIGHT_MEDIUM};
            }}
            QPushButton#calc_route_btn:hover {{
                background: {COLOR_ACCENT_HOVER};
            }}
            QPushButton#calc_route_btn:pressed {{
                background: #4547B0;
            }}
            QPushButton#calc_route_btn:disabled {{
                background: {COLOR_ACCENT_PRIMARY};
                color: #FFFFFF;
            }}
        """)
        self.calc_btn.clicked.connect(self._on_calculate_click)
        bl.addWidget(self.calc_btn)

        export_btn = QPushButton(t("route.export_metadata"))
        export_btn.setFixedHeight(28)
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: 4px;
                font-size: 11px;
                font-weight: {FONT_WEIGHT_REGULAR};
            }}
            QPushButton:hover {{
                background: {COLOR_BG_HOVER};
                color: {COLOR_TEXT_PRIMARY};
                border-color: {COLOR_BORDER_MEDIUM};
            }}
        """)
        export_btn.clicked.connect(self._export_route_metadata)
        bl.addWidget(export_btn)

        # Remove old sidebar references
        self.calculate_btn = self.calc_btn

        self._load_trucks()
        self._refresh_chips()

    # ── Profile names ──────────────────────────────────────────────────────────

    def _rebuild_profile_display_names(self) -> None:
        self._profile_key_to_display = {k: t(f"route.profile_{k.lower()}") for k in self.profile_map}
        self._profile_display_to_key = {v: k for k, v in self._profile_key_to_display.items()}

    # ── Trucks ─────────────────────────────────────────────────────────────────

    def _load_trucks(self) -> None:
        try:
            from services.conflict_service import TripConflictService
            conflict_svc = TripConflictService(self.fleet_service.db)
            rows = self.fleet_service.get_trucks()
            self._trucks_map = {}
            self._truck_label_to_id = {}
            self.truck_combo.clear()
            for row in rows:
                truck_id = str(row["id"])
                plate = row["plate_number"]
                label = f"{plate} - {row.get('model') or ''}"
                next_slot = conflict_svc.get_next_available_slot(plate)
                if next_slot:
                    label = f"{label}  [{t('dispatch_board.available_from').format(next_slot)}]"
                self._truck_label_to_id[label] = truck_id
                self._trucks_map[truck_id] = row
                self.truck_combo.addItem(label, truck_id)
            if rows:
                self.truck_combo.setCurrentIndex(0)
                self._selected_truck_id = self._truck_label_to_id.get(self.truck_combo.currentText())
        except Exception:
            logger.exception("Failed to load trucks")

    def _on_truck_selected(self, _index: int) -> None:
        self._selected_truck_id = self._truck_label_to_id.get(self.truck_combo.currentText())

    # ── Country exclusions ─────────────────────────────────────────────────────

    def _on_exclusions_changed(self) -> None:
        codes = self._core.get_excluded_countries()
        if self._map_renderer:
            self._map_renderer.draw_avoided_country_overlays(codes)

    # ── Stops ──────────────────────────────────────────────────────────────────

    def _add_stop_field(self) -> None:
        self.stops_state.insert(len(self.stops_state) - 1, normalize_existing_stop({"type": "stop"}))
        self._render_stops_list()

    def _remove_stop_index(self, idx: int) -> None:
        if idx in (0, len(self.stops_state) - 1):
            return
        self.stops_state.pop(idx)
        self._render_stops_list()

    def _render_stops_list(self) -> None:
        while self._stops_container_layout.count():
            item = self._stops_container_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self._stop_rows.clear()
        self._stop_ids.clear()
        self._waypoint_fields = {}

        for idx, stop in enumerate(self.stops_state):
            sid = stop.get("id") or uuid.uuid4().hex
            stop["id"] = sid
            if sid not in self.stop_vars:
                self.stop_vars[sid] = stop.get("address", "") or ""

            if stop["type"] == "start":
                placeholder = t("route.stop_start", default="📍 Start...")
                dot_color = COLOR_SUCCESS_DEFAULT
                show_remove = False
            elif stop["type"] == "destination":
                placeholder = t("route.stop_destination", default="🏁 Destinație...")
                dot_color = COLOR_ERROR_DEFAULT
                show_remove = False
            else:
                placeholder = t("route.stop_n", default=f"Stop {idx}").format(idx)
                dot_color = COLOR_ACCENT_PRIMARY
                show_remove = True

            row = WaypointRow(placeholder, dot_color, show_remove=show_remove, parent=self._stops_container)
            row.field.setText(stop.get("address", ""))
            row.field.textChanged.connect(
                lambda text, s=sid: self._on_stop_text_changed(s, text)
            )
            self._waypoint_fields[sid] = row.field

            if show_remove and hasattr(row, "remove_btn"):
                row.remove_btn.clicked.connect(lambda checked, i=idx: self._remove_stop_index(i))

            self._stops_container_layout.addWidget(row)
            self._stop_rows[idx] = row
            self._stop_ids[idx] = sid

            # Connecting line between waypoints
            if idx < len(self.stops_state) - 1:
                connector = WaypointConnector(self._stops_container)
                self._stops_container_layout.addWidget(connector)

        # Bind Enter to calculate on last field
        if self._stop_rows:
            last_idx = len(self.stops_state) - 1
            last_row = self._stop_rows.get(last_idx)
            if last_row and hasattr(last_row, "field"):
                last_row.field.returnPressed.connect(self._on_calculate_click)

        # Update calc button state
        self._update_calc_button_state()

    def _on_stop_text_changed(self, sid: str, text: str) -> None:
        self.stop_vars[sid] = text
        self._update_calc_button_state()

    def _collect_stop_addresses(self) -> dict:
        return dict(self.stop_vars)

    def _row_address_pairs(self) -> list:
        result = []
        for idx, stop in enumerate(self.stops_state):
            sid = stop.get("id", "")
            addr = self.stop_vars.get(sid, stop.get("address", ""))
            result.append((idx, addr))
        return result

    def _toggle_comparison(self, state: int) -> None:
        if self._last_route_result:
            self._draw_route_on_map(self._last_route_result)

    def _on_click_add_changed(self, state: int) -> None:
        self._click_to_add_enabled = bool(state)
        if self._click_to_add_enabled:
            js = (
                "var el = document.querySelector('.leaflet-container');"
                "if (el) el.style.cursor = 'crosshair';"
            )
        else:
            js = (
                "var el = document.querySelector('.leaflet-container');"
                "if (el) el.style.cursor = '';"
            )
        self.map_widget._run_js(js)

    def _refresh_chips(self) -> None:
        while self._chips_container_layout.count():
            item = self._chips_container_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        codes = self._core.get_excluded_countries()
        chips_per_row = 5
        for i in range(0, len(codes), chips_per_row):
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            for code in codes[i:i + chips_per_row]:
                chip = make_country_chip(code)
                chip.remove_btn.clicked.connect(lambda checked, c=code: self._remove_excluded_country(c))
                row_layout.addWidget(chip)
            row_layout.addStretch()
            self._chips_container_layout.addWidget(row)

    def _remove_excluded_country(self, code: str) -> None:
        self._core.country_avoidance.toggle(code)
        self._refresh_chips()
        self._on_exclusions_changed()

    def _open_country_selector(self) -> None:
        from ui.views.country_exclusions_dialog import CountryExclusionsDialog
        dlg = CountryExclusionsDialog(
            self,
            self._core.country_avoidance,
        )
        if dlg.exec():
            self._refresh_chips()
            self._on_exclusions_changed()

    def _update_calc_button_state(self) -> None:
        if not hasattr(self, "stops_state") or len(self.stops_state) < 2:
            return
        start_sid = self.stops_state[0].get("id", "")
        dest_sid = self.stops_state[1].get("id", "")
        start_val = self.stop_vars.get(start_sid, "") or ""
        dest_val = self.stop_vars.get(dest_sid, "") or ""
        start_filled = bool(start_val.strip())
        dest_filled = bool(dest_val.strip())
        enabled = start_filled and dest_filled
        self.calc_btn.setEnabled(enabled)
        self.calc_opacity.setOpacity(1.0 if enabled else 0.4)

    def _inject_map_styles(self, ok: bool) -> None:
        if not ok or getattr(QtRoutePlannerView, "LEAFLET_CSS_INJECTED", False):
            return
        QtRoutePlannerView.LEAFLET_CSS_INJECTED = True
        js = f"""
        var style = document.createElement('style');
        style.textContent = `{LEAFLET_DARK_CSS}`;
        document.head.appendChild(style);
        """
        self.map_widget.page().runJavaScript(js)

    def _show_empty_state(self) -> None:
        self._result_stack.setCurrentIndex(0)
        self._empty_error_label.hide()
        self._empty_error_label.setText("")
        self._summary_text.setText("")
        self._explanation_text.setText("")
        self._dispatch_container.hide()

    def _show_route_result(self, distance_km: float, duration_min: float,
                           fuel_cost_eur: float, summary_text: str = "",
                           explanation_text: str = "") -> None:
        from utils.formatters import fmt_currency, fmt_distance
        from utils.formatting import format_duration

        self.pill_distance.value_label.setText(fmt_distance(distance_km))
        self.pill_duration.value_label.setText(format_duration(duration_min))
        self.pill_fuel_cost.value_label.setText(fmt_currency(fuel_cost_eur))
        rate = fuel_cost_eur / distance_km if distance_km > 0 else 0
        self.pill_rate.value_label.setText(fmt_currency(rate) + "/km")

        self._summary_text.setText(summary_text)
        self._explanation_text.setText(explanation_text)

        self._result_stack.setCurrentIndex(2)

    def _on_map_click(self, lat: float, lng: float) -> None:
        if not self._click_to_add_enabled:
            return

        address = self._reverse_geocode(lat, lng)

        new_stop = normalize_existing_stop({
            "type": "stop",
            "lat": lat,
            "lon": lng,
            "address": address,
            "resolved": True,
        })
        self.stops_state.insert(len(self.stops_state) - 1, new_stop)
        self._render_stops_list()

    @staticmethod
    def _reverse_geocode(lat: float, lng: float) -> str:
        try:
            import requests
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {"lat": lat, "lon": lng, "format": "json", "zoom": 14}
            headers = {"User-Agent": "OperionERP/1.0"}
            resp = requests.get(url, params=params, headers=headers, timeout=5)
            if resp.ok:
                data = resp.json()
                return data.get("display_name", "") or f"{lat:.5f}, {lng:.5f}"
        except Exception:
            pass
        return f"{lat:.5f}, {lng:.5f}"

    # ── Calculation ────────────────────────────────────────────────────────────

    def _on_calculate_click(self) -> None:
        ctx, err = self._core.validate_calculation_input(
            truck_id=self._selected_truck_id or "",
            trucks_map=self._trucks_map,
            profile_label=self._profile_display_to_key.get(
                self.profile_combo.currentText(), "Recommended"
            ),
            stops_state=self.stops_state,
            row_addresses=self._row_address_pairs(),
        )
        if err or ctx is None:
            self._result_stack.setCurrentIndex(0)
            self._empty_error_label.setText(err or "Unknown error")
            self._empty_error_label.setStyleSheet(f"color: {COLORS.get('warning', '#f59e0b')}; font-size: 12px;")
            self._empty_error_label.show()
            return

        self._calc_token += 1
        token = self._calc_token

        # TASK 11: Show loading state
        self.calc_btn.setEnabled(False)
        self.calc_opacity.setOpacity(0.4)
        self._result_stack.setCurrentIndex(1)  # loading page
        self._dispatch_container.hide()

        def callback(result):
            self.route_result_received.emit(result, ctx, token)

        self._core.start_calculation(ctx, callback)

    def _on_route_result(self, result, ctx, token: int) -> None:
        if token != self._calc_token:
            return

        self.calc_btn.setEnabled(True)
        self.calc_opacity.setOpacity(1.0)

        processed, err = self._core.process_calculation_result(
            result,
            ctx,
            self._collect_stop_addresses(),
        )
        if err:
            self._result_stack.setCurrentIndex(0)
            self._empty_error_label.setText(err)
            self._empty_error_label.setStyleSheet(f"color: {COLORS.get('danger', '#ef4444')}; font-size: 12px;")
            self._empty_error_label.show()
            return
        if not processed:
            self._result_stack.setCurrentIndex(0)
            self._empty_error_label.setText(t("route.calc_failed"))
            self._empty_error_label.setStyleSheet(f"color: {COLORS.get('danger', '#ef4444')}; font-size: 12px;")
            self._empty_error_label.show()
            return

        self._last_route_result = processed.route
        self._last_route_history_id = processed.route.get("history_id")
        self._last_route_calc_ctx = ctx
        self._populate_stops_from_route(processed.route)

        # Update route summary label from stop_vars
        route = processed.route
        cost_info = processed.cost_info
        stops = route.get("stops") or []
        start_sid = self.stops_state[0].get("id", "") if self.stops_state else ""
        dest_sid = self.stops_state[-1].get("id", "") if len(self.stops_state) > 1 else ""
        start_addr = self.stop_vars.get(start_sid, self.stops_state[0].get("address", "")) if self.stops_state else ""
        dest_addr = self.stop_vars.get(dest_sid, self.stops_state[-1].get("address", "")) if len(self.stops_state) > 1 else ""
        self.route_summary_label.setText(f"{start_addr} \u2192 {dest_addr}")

        # Update metric pills — route dict uses distance_km / duration_min,
        # fuel cost lives in cost_info
        distance_km = float(route.get("distance_km", 0))
        duration_min = float(route.get("duration_min", 0))
        fuel_cost = float(cost_info.get("fuel_cost", 0)) if cost_info else 0

        compliance = getattr(processed, "compliance", None)
        summary_text = getattr(compliance, "summary_text", "") if compliance else ""
        explanation_text = getattr(compliance, "explanation_text", "") if compliance else ""

        self._show_route_result(
            distance_km=distance_km,
            duration_min=duration_min,
            fuel_cost_eur=fuel_cost,
            summary_text=summary_text,
            explanation_text=explanation_text,
        )
        self._draw_route_on_map(route)
        self._show_dispatch_buttons()

    def _show_dispatch_buttons(self) -> None:
        # Clear existing
        while self._dispatch_container_layout.count():
            item = self._dispatch_container_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(SP["2"])

        calc_btn = Btn(
            btn_row,
            t("route.send_to_calculator"),
            variant="secondary",
            command=self._go_to_calculator,
        )
        btn_layout.addWidget(calc_btn, 1)

        discard_btn = Btn(btn_row, "", variant="danger", icon_name="mdi6.delete", command=self._discard_route)
        discard_btn.setFixedSize(36, 36)
        btn_layout.addWidget(discard_btn)

        self._dispatch_container_layout.addWidget(btn_row)
        self._dispatch_container.show()

    def _go_to_calculator(self) -> None:
        if self._last_route_history_id:
            truck_id = str(self._selected_truck_id) if self._selected_truck_id else None
            self._core.commit_route(self._last_route_history_id, truck_id=truck_id)
            self._pending_clear = True
        if self.controller and hasattr(self.controller, "_switch_module"):
            self.controller._switch_module("calculator")

    def _discard_route(self) -> None:
        if self._last_route_history_id:
            self._core.discard_route(self._last_route_history_id)
        self._clear_route_state()

    def _clear_route_state(self) -> None:
        self._last_route_result = None
        self._last_route_history_id = None
        self._last_route_calc_ctx = None
        self._dispatch_container.hide()
        while self._dispatch_container_layout.count():
            item = self._dispatch_container_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if self._map_renderer:
            self._map_renderer.clear_route_overlays()
            self._map_renderer.clear_stop_markers()
        self._summary_text.setText("")
        self._summary_text.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
        self._explanation_text.setText("")
        self._show_empty_state()
        self.stops_state = [
            normalize_existing_stop({"type": "start"}),
            normalize_existing_stop({"type": "destination"}),
        ]
        self.stop_vars = {}
        self._stop_rows = {}
        self._stop_ids = {}
        self._render_stops_list()

    def _populate_stops_from_route(self, route: dict) -> None:
        stops = route.get("stops") or []
        for i, stop in enumerate(self.stops_state):
            if i < len(stops):
                try:
                    stop["lat"], stop["lon"] = float(stops[i][0]), float(stops[i][1])
                    stop["resolved"] = True
                except Exception:
                    pass

    def _apply_compliance(self, compliance) -> None:
        if not compliance:
            return
        self._summary_text.setText(compliance.summary_text)
        self._explanation_text.setText(compliance.explanation_text)

    def _draw_route_on_map(self, route: dict) -> None:
        if not self._map_renderer:
            return
        geometry = route.get("geometry") or []
        if not geometry:
            return
        try:
            self._map_renderer.draw_route(
                geometry,
                route,
                show_comparison=self._compare_check.isChecked(),
                highlight_avoided=True,
            )
            self._map_renderer.update_stop_markers(self.stops_state)
        except Exception:
            logger.exception("Failed to draw route on map")

    # ── History load ───────────────────────────────────────────────────────────

    def load_history_route(self, record: RouteHistoryRecord, draw: bool = True) -> None:
        patch = self._core.load_history_record(record)

        if len(patch.get("stops") or []) >= 2:
            self.stops_state = patch["stops"]
            self.stop_vars = {}
            self._render_stops_list()

        if patch.get("profile_label"):
            key = patch["profile_label"]
            self.profile_combo.setCurrentText(
                self._profile_key_to_display.get(key, key)
            )
        if patch.get("truck_id"):
            try:
                idx = self.truck_combo.findData(patch["truck_id"])
                if idx >= 0:
                    self.truck_combo.setCurrentIndex(idx)
            except Exception:
                pass

        self._core.country_avoidance.set_selected(patch.get("excluded_countries") or [])
        self._refresh_chips()

        route = patch["route"]
        self._last_route_result = route
        self._show_route_result(
            distance_km=float(route.get("distance_km", 0)),
            duration_min=float(route.get("duration_min", 0)),
            fuel_cost_eur=0,
            summary_text=format_history_loaded_info(record),
        )

        if draw and route.get("geometry") and self._map_renderer:
            try:
                self._map_renderer.draw_route(
                    route["geometry"],
                    route,
                    show_comparison=self._compare_check.isChecked(),
                    highlight_avoided=True,
                )
                self._map_renderer.update_stop_markers(self.stops_state)
                self._map_renderer.center_on_geometry(route["geometry"])
            except Exception:
                logger.exception("Failed to draw history route on map")

    # ── Export ─────────────────────────────────────────────────────────────────

    def _export_route_metadata(self) -> None:
        path, err = self._core.export_route_metadata(self._last_route_result)
        if err:
            self._summary_text.setText(err)
            self._summary_text.setStyleSheet(f"color: {COLORS.get('warning', '#f59e0b')};")
            return
        self._summary_text.setText(t("route.export_success").format(path))
        self._summary_text.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")

    # ── i18n ───────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        try:
            old_key = self._profile_display_to_key.get(self.profile_combo.currentText(), "Recommended")
            self._rebuild_profile_display_names()
            self.profile_combo.clear()
            self.profile_combo.addItems(list(self._profile_key_to_display.values()))
            self.profile_combo.setCurrentText(
                self._profile_key_to_display.get(
                    old_key, self._profile_key_to_display.get("Recommended", "Recommended")
                )
            )
            self._refresh_chips()
            self._render_stops_list()
        except Exception:
            logger.exception("Language refresh failed")

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        if self._pending_clear:
            self._pending_clear = False
            self._clear_route_state()
        # Recreate map widget if it was destroyed by shutdown()
        try:
            self.map_widget.isWidgetType()
        except RuntimeError:
            from ui.map.map_widget import MapWidget
            self.map_widget = MapWidget(self._content_widget)
            self._map_renderer = QtRouteMapRenderer(self.map_widget)
            self.map_widget.set_click_callback(self._on_map_click)
            self.map_widget.setMinimumWidth(1)
            self.map_widget.loadFinished.connect(self._inject_map_styles)
            QtRoutePlannerView.LEAFLET_CSS_INJECTED = False
            content_layout = self._content_widget.layout()
            if content_layout:
                content_layout.addWidget(self.map_widget, 1)

    def shutdown(self) -> None:
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)
        # Unsubscribe from the event bus so a recreated view doesn't
        # get duplicate events from a dead instance.
        if getattr(self, "_event_subscribed", False):
            try:
                bus = EventBus()
                bus.unsubscribe(TRUCK_CREATED, self._on_truck_event)
                bus.unsubscribe(TRUCK_UPDATED, self._on_truck_event)
                bus.unsubscribe(TRUCK_DELETED, self._on_truck_event)
            except Exception:
                pass
            self._event_subscribed = False
        with contextlib.suppress(Exception):
            self.map_widget.destroy()
        self._map_renderer = None
