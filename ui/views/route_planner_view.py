"""PySide6 route planner view.

Replaces ``ui/route_planner.py``. Uses ``MapWidget`` for the map and
``RoutePlannerController`` for business logic. Fully embedded as a QWidget.
"""

from __future__ import annotations

import contextlib
import logging
import os
import uuid
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services.fleet_service import FleetService
from services.i18n import register_listener, t, unregister_listener
from ui.performance_timer import PerfTimer
from services.operations.event_bus import (
    TRUCK_CREATED,
    TRUCK_DELETED,
    TRUCK_UPDATED,
    EventBus,
)
from services.route_history_service import RouteHistoryRecord, RouteHistoryService
from services.route_persistence import RoutePersistenceService
from services.route_planner_controller import RoutePlannerController
from services.route_result_presenter import format_history_loaded_info
from services.route_sharing_service import (
    build_google_maps_url,
    build_share_url,
    extract_stops_from_route_result,
)
from services.route_state import RouteStateManager
from services.stop_factory import normalize_existing_stop
from ui.components import (
    Btn,
    Card,
    EmptyState,
    Label,
    PageTitle,
    get_icon,
)
from ui.worker_pool import WorkerPool
from ui.design_tokens import (
    BTN_HEIGHT_SM,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRIMARY,
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
    COLOR_TEXT_WHITE,
    COLOR_WARNING_DEFAULT,
    FONT_SIZE_BASE,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_SIZE_XS,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_REGULAR,
    FONT_WEIGHT_SEMIBOLD,
    HOVER_MS,
    INPUT_HEIGHT,
    RADIUS_MD,
    RADIUS_PILL,
    RADIUS_SM,
    SP,
    SPACE_1,
    SPACE_12,
    SPACE_2,
    SPACE_3,
    SPACE_5,
)
from ui.map import MapWidget, QtRouteMapRenderer
from ui.widgets import (
    StyledComboBox,
)
from utils.labels import GRAPHHOPPER_PROFILES

logger = logging.getLogger(__name__)


def make_section_header(text: str) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 20, 0, 10)
    layout.setSpacing(8)

    label = QLabel(text.upper())
    label.setStyleSheet(
        f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_XS}px; font-weight: {FONT_WEIGHT_SEMIBOLD}; letter-spacing: 0.08em;"
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
    cb.setFixedHeight(BTN_HEIGHT_SM)
    cb.setStyleSheet(f"""
        QCheckBox {{
            color: {COLOR_TEXT_SECONDARY};
            font-size: {FONT_SIZE_BASE}px;
            font-weight: {FONT_WEIGHT_REGULAR};
            spacing: 8px;
        }}
        QCheckBox:hover {{ color: {COLOR_TEXT_PRIMARY}; }}
        QCheckBox::indicator {{
            width: 16px; height: 16px;
            border-radius: {RADIUS_SM}px;
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
    pill.setFixedHeight(SPACE_12)
    pill.setStyleSheet(f"""
        QFrame {{
            background: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_MD}px;
        }}
    """)
    pl = QVBoxLayout(pill)
    pl.setContentsMargins(10, 6, 10, 6)
    pl.setSpacing(2)

    val_lbl = QLabel(value)
    val_lbl.setStyleSheet(
        f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_MD}px; font-weight: {FONT_WEIGHT_SEMIBOLD}; border: none; background: transparent;"
    )
    lbl_w = QLabel(label)
    lbl_w.setStyleSheet(
        f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_XS}px; border: none; background: transparent;"
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
        self.field.setFixedHeight(INPUT_HEIGHT)
        self.field.setStyleSheet(f"""
            QLineEdit {{
                background: {COLOR_BG_OVERLAY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_SM}px;
                color: {COLOR_TEXT_PRIMARY};
                font-size: {FONT_SIZE_BASE}px;
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
            remove_btn.setFixedSize(SPACE_5, SPACE_5)
            remove_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLOR_TEXT_TERTIARY};
                    border: none;
                    font-size: {FONT_SIZE_MD}px;
                    font-weight: {FONT_WEIGHT_REGULAR};
                    border-radius: {RADIUS_SM}px;
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
        self.setFixedHeight(SPACE_2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QColor(COLOR_BORDER_MEDIUM))
        line_x = 5
        painter.drawLine(line_x, 0, line_x, self.height())
        painter.end()


from ui.widgets.flow_layout import FlowLayout  # noqa: F401
def make_country_chip(country_code: str) -> QWidget:
    chip = QWidget()
    chip.setFixedHeight(22)
    chip.setStyleSheet(f"""
        background: {COLOR_BG_OVERLAY};
        border: 1px solid {COLOR_BORDER_MEDIUM};
        border-radius: {RADIUS_PILL}px;
    """)
    row = QHBoxLayout(chip)
    row.setContentsMargins(8, 0, 6, 0)
    row.setSpacing(4)

    lbl = QLabel(country_code)
    lbl.setStyleSheet(
        f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_XS}px; font-weight: {FONT_WEIGHT_SEMIBOLD}; background: transparent; border: none;"
    )
    remove = QPushButton("\u00d7")
    remove.setFixedSize(14, 14)
    remove.setStyleSheet(f"""
        QPushButton {{
            background: transparent; border: none;
            color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_SM}px;
        }}
        QPushButton:hover {{ color: {COLOR_ERROR_DEFAULT}; }}
    """)
    row.addWidget(lbl)
    row.addWidget(remove)
    chip.remove_btn = remove
    return chip


LEAFLET_DARK_CSS = f"""
.leaflet-control-zoom {{
    border: none !important;
    box-shadow: none !important;
}}
.leaflet-control-zoom a {{
    background-color: {COLOR_BG_ELEVATED} !important;
    color: {COLOR_TEXT_PRIMARY} !important;
    border: 1px solid {COLOR_BORDER_SUBTLE} !important;
    border-radius: {RADIUS_MD}px !important;
    width: 28px !important;
    height: 28px !important;
    line-height: 28px !important;
    font-size: {FONT_SIZE_LG}px !important;
    font-weight: {FONT_WEIGHT_REGULAR} !important;
    display: block !important;
    margin-bottom: {SPACE_1}px !important;
    text-align: center !important;
    transition: background {HOVER_MS}ms ease;
}}
.leaflet-control-zoom a:hover {{
    background-color: {COLOR_BG_HOVER} !important;
    color: {COLOR_ACCENT_PRIMARY} !important;
    border-color: {COLOR_BORDER_MEDIUM} !important;
}}
.leaflet-control-attribution {{
    background: rgba(20, 20, 22, 0.7) !important;
    color: {COLOR_TEXT_TERTIARY} !important;
    font-size: {FONT_SIZE_XS}px !important;
    border-top-left-radius: {RADIUS_SM}px !important;
    padding: 2px 6px !important;
}}
.leaflet-control-attribution a {{ color: {COLOR_ACCENT_PRIMARY} !important; }}
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
    reverse_geocode_done = Signal(str, float, float)      # address, lat, lng

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        controller=None,
        api_client=None,
        # Injected service dependencies (optional — created from db if omitted)
        route_controller=None,
        route_history_service=None,
        route_state=None,
        fleet_service=None,
        persistence=None,
        geocode_service=None,
        conflict_service=None,
        export_service=None,
    ):
        super().__init__(parent)
        self.db = db
        self.controller = controller  # MainWindow reference for module switching
        self._api_client = api_client

        if db is not None:
            # Use injected instances or create from db
            self._core = route_controller or RoutePlannerController(db)
            self.route_history_service = route_history_service or RouteHistoryService(db)
            self.route_state = route_state or RouteStateManager(db)
            self.fleet_service = fleet_service or FleetService(db)
            self._persistence = persistence or RoutePersistenceService(
                self.route_history_service,
                self.route_state,
                self._core.cost_engine,
            )
            self._core.bind_persistence(self._persistence)
        else:
            self._core = None
            self.route_history_service = None
            self.route_state = None
            self.fleet_service = None
            self._persistence = None

        # Geocoding service for reverse geocode lookups (delegated to service)
        self.geocode_service = geocode_service
        if self.geocode_service is None:
            from services import geocode_nominatim
            self.geocode_service = geocode_nominatim

        # Export service for file operations (delegated to service)
        self.export_service = export_service
        if self.export_service is None and db is not None:
            from services.export_service import ExportService
            self.export_service = ExportService(db=db)

        # Conflict service for truck availability checks (lazy-loaded in _load_trucks)
        self._conflict_service = conflict_service

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
        self.reverse_geocode_done.connect(self._on_reverse_geocode_result)

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

        # Defer MapWidget construction so the view switch is instant.
        # Initialize to None so method guards don't crash before lazy init runs.
        self.map_widget = None
        self._map_renderer = None
        QTimer.singleShot(0, self._lazy_init_map)

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
        self.setAccessibleName("Route planner")
        self.setAccessibleDescription("Route planning with map and sidebar controls")
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
        panel.setMinimumWidth(320)
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
            QScrollBar:vertical {{ width: {SPACE_1}px; background: transparent; }}
            QScrollBar::handle:vertical {{ background: {COLOR_BORDER_MEDIUM}; border-radius: 2px; min-height: {SPACE_5}px; }}
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

        # Map — placeholder widget replaced lazily to avoid synchronous
        # QWebEngineView startup (~270 ms) in _build_ui().
        self.map_widget = QWidget()
        ph_layout = QVBoxLayout(self.map_widget)
        ph_layout.setAlignment(Qt.AlignCenter)
        ph_label = QLabel(t("route.loading_map", default="Loading map\u2026"))
        ph_label.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_LG}px;"
        )
        ph_layout.addWidget(ph_label)
        self.map_widget.setMinimumWidth(1)
        self._click_to_add_enabled = False
        content.addWidget(self.map_widget, 1)

        outer.addWidget(self._content_widget, 1)

        # Build sidebar content
        self._build_sidebar_content(scroll_layout, button_bar_layout)

    def _lazy_init_map(self) -> None:
        """Create the real MapWidget lazily, replacing the placeholder.

        Called once via QTimer.singleShot(0, …) at the end of __init__
        to avoid paying the ~270 ms cost of QWebEngineView + Folium HTML
        generation synchronously during _build_ui().
        """
        if self._map_renderer is not None:
            return  # Already initialised

        content_layout = self._content_widget.layout()

        # Remove ALL non-panel widgets from the content layout.
        # This handles both the initial placeholder and any orphaned
        # MapWidget left behind after shutdown/wakeup (where the C++
        # object was destroyed but the widget was never removed from
        # the layout — causing a 50/50 split between "Loading map…"
        # and the real map).
        if content_layout is not None:
            for i in range(content_layout.count() - 1, -1, -1):
                item = content_layout.itemAt(i)
                w = item.widget() if item else None
                if w is not None and w.objectName() != "route_panel":
                    content_layout.removeWidget(w)
                    w.deleteLater()

        # Create the real widget
        self.map_widget = MapWidget(self._content_widget)
        self._map_renderer = QtRouteMapRenderer(self.map_widget)
        self.map_widget.set_click_callback(self._on_map_click)
        self.map_widget.setMinimumWidth(1)
        if content_layout is not None:
            content_layout.addWidget(self.map_widget, 1)
        self.map_widget.loadFinished.connect(self._inject_map_styles)

    def _make_collapsible_card(
        self, title: str, body: QWidget, expanded: bool = True
    ) -> tuple[QFrame, QPushButton]:
        """Build a collapsible Card with a clickable header that toggles the body.

        Returns (card_frame, header_button).
        """
        card = Card()
        card.layout().setContentsMargins(0, 0, 0, 0)
        card.layout().setSpacing(0)

        # Header row
        header = QPushButton()
        header.setFixedHeight(36)
        header.setCursor(Qt.PointingHandCursor)
        header.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLOR_TEXT_SECONDARY};
                font-size: {FONT_SIZE_SM}px;
                font-weight: {FONT_WEIGHT_SEMIBOLD};
                text-align: left;
                padding: 0 {SPACE_3}px;
                border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
            }}
            QPushButton:hover {{
                color: {COLOR_TEXT_PRIMARY};
                background: {COLOR_BG_HOVER};
            }}
        """)
        # Arrow + title
        arrow = "\u25BC" if expanded else "\u25B6"
        header.setText(f"{arrow}  {title.upper()}")

        body.setVisible(expanded)

        def _toggle():
            expanded_new = not body.isVisible()
            body.setVisible(expanded_new)
            new_arrow = "\u25BC" if expanded_new else "\u25B6"
            header.setText(f"{new_arrow}  {title.upper()}")

        header.clicked.connect(_toggle)

        card.layout().addWidget(header)
        card.layout().addWidget(body)
        return card, header

    def _build_sidebar_content(self, sl: QVBoxLayout, bl: QVBoxLayout) -> None:
        # ═══ CARD 1: Route (waypoints + add-stop button) ═══
        route_body = QWidget()
        route_body_layout = QVBoxLayout(route_body)
        route_body_layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        route_body_layout.setSpacing(0)

        self._stops_container = QWidget()
        self._stops_container_layout = QVBoxLayout(self._stops_container)
        self._stops_container_layout.setContentsMargins(0, 0, 0, 0)
        self._stops_container_layout.setSpacing(0)
        self._stops_container_layout.setAlignment(Qt.AlignTop)
        route_body_layout.addWidget(self._stops_container)

        add_stop_btn = QPushButton(f"+ {t('route.add_stop')}")
        add_stop_btn.setFixedHeight(BTN_HEIGHT_SM)
        add_stop_btn.setCursor(Qt.PointingHandCursor)
        add_stop_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLOR_ACCENT_PRIMARY};
                border: none;
                font-size: {FONT_SIZE_SM}px;
                font-weight: {FONT_WEIGHT_MEDIUM};
                text-align: left;
                padding-left: 0;
            }}
            QPushButton:hover {{
                color: {COLOR_ACCENT_HOVER};
            }}
        """)
        add_stop_btn.clicked.connect(self._add_stop_field)
        route_body_layout.addWidget(add_stop_btn)

        sl.addSpacing(4)
        card1, _ = self._make_collapsible_card(
            t("route.section.smart_route"), route_body, expanded=True
        )
        sl.addWidget(card1)

        # ═══ CARD 2: Constraints (truck, profile, countries, toggles) ═══
        constraints_body = QWidget()
        constraints_layout = QVBoxLayout(constraints_body)
        constraints_layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        constraints_layout.setSpacing(8)

        # Truck selector: label + [combo + refresh button]
        truck_label = QLabel(t("route.select_truck"))
        truck_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_MEDIUM};")
        constraints_layout.addWidget(truck_label)

        truck_combo_row = QWidget()
        tcr_layout = QHBoxLayout(truck_combo_row)
        tcr_layout.setContentsMargins(0, 0, 0, 0)
        tcr_layout.setSpacing(4)

        self.truck_combo = StyledComboBox()
        self.truck_combo.setFixedHeight(INPUT_HEIGHT)
        self.truck_combo.setStyleSheet(f"""
            QComboBox {{
                background: {COLOR_BG_OVERLAY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_SM}px;
                color: {COLOR_TEXT_PRIMARY};
                font-size: {FONT_SIZE_BASE}px;
                padding: 0 10px;
            }}
            QComboBox:focus {{ border-color: {COLOR_ACCENT_PRIMARY}; }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox::down-arrow {{ width: 12px; height: 12px; }}
            QComboBox QAbstractItemView {{
                background: {COLOR_BG_OVERLAY};
                border: 1px solid {COLOR_BORDER_MEDIUM};
                border-radius: {RADIUS_MD}px;
                color: {COLOR_TEXT_PRIMARY};
                selection-background-color: {COLOR_BG_HOVER};
            }}
        """)
        self.truck_combo.currentIndexChanged.connect(self._on_truck_selected)
        tcr_layout.addWidget(self.truck_combo, 1)

        self._truck_refresh_btn = QPushButton("\u21bb")
        self._truck_refresh_btn.setFixedSize(BTN_HEIGHT_SM, BTN_HEIGHT_SM)
        self._truck_refresh_btn.setToolTip(t("common.refresh", default="Refresh"))
        self._truck_refresh_btn.setCursor(Qt.PointingHandCursor)
        self._truck_refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLOR_TEXT_TERTIARY};
                border: none;
                font-size: {FONT_SIZE_MD}px;
                border-radius: {RADIUS_SM}px;
            }}
            QPushButton:hover {{
                color: {COLOR_TEXT_PRIMARY};
                background: {COLOR_BG_HOVER};
            }}
        """)
        self._truck_refresh_btn.clicked.connect(self._load_trucks)
        tcr_layout.addWidget(self._truck_refresh_btn)

        constraints_layout.addWidget(truck_combo_row)

        # Route profile
        profile_label = QLabel(t("route.profile_label"))
        profile_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_MEDIUM};")
        constraints_layout.addWidget(profile_label)

        self._rebuild_profile_display_names()
        self.profile_combo = StyledComboBox(values=list(self._profile_key_to_display.values()))
        self.profile_combo.setFixedHeight(INPUT_HEIGHT)
        self.profile_combo.setStyleSheet(self.truck_combo.styleSheet())
        self.profile_combo.setCurrentText(self._profile_key_to_display.get("Recommended", "Recommended"))
        constraints_layout.addWidget(self.profile_combo)

        # Excluded Countries
        countries_label = QLabel(t("route.section.excluded_countries"))
        countries_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_MEDIUM};")
        constraints_layout.addWidget(countries_label)

        self._chips_container = QWidget()
        self._chips_container.setStyleSheet("background: transparent;")
        self._chips_container_layout = QVBoxLayout(self._chips_container)
        self._chips_container_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_container_layout.setSpacing(4)
        constraints_layout.addWidget(self._chips_container)

        add_country_btn = QPushButton(f"+ {t('route.add_country')}")
        add_country_btn.setCursor(Qt.PointingHandCursor)
        add_country_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {COLOR_ACCENT_PRIMARY}; font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_MEDIUM};
                text-align: left; padding: {SPACE_1}px 0;
            }}
            QPushButton:hover {{ color: {COLOR_ACCENT_HOVER}; }}
        """)
        add_country_btn.clicked.connect(self._open_country_selector)
        constraints_layout.addWidget(add_country_btn)

        # Toggle checkboxes
        self._compare_check = make_toggle_row(t("route.show_comparison"), checked=True)
        self._compare_check.stateChanged.connect(self._toggle_comparison)
        constraints_layout.addWidget(self._compare_check)

        self._click_add_check = make_toggle_row(t("route.click_to_add_stop"), checked=False)
        self._click_add_check.stateChanged.connect(self._on_click_add_changed)
        constraints_layout.addWidget(self._click_add_check)

        sl.addSpacing(4)
        card2, _ = self._make_collapsible_card(
            t("route.section.options"), constraints_body, expanded=True
        )
        sl.addWidget(card2)

        # ═══ CARD 3: Results (pills + create trip) ═══
        self._results_body = QWidget()
        results_layout_inner = QVBoxLayout(self._results_body)
        results_layout_inner.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        results_layout_inner.setSpacing(8)

        self._result_stack = QStackedWidget()

        # Page 0: Empty state
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setContentsMargins(0, 16, 0, 8)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(6)

        self._route_empty_state = EmptyState(
            parent=empty_page,
            icon_name="fa5s.route",
            title=t("route.empty_title", "Plan your first route"),
            subtitle=t("route.empty_desc", "Enter a start and destination to begin."),
        )
        empty_layout.addWidget(self._route_empty_state)

        self._empty_error_label = QLabel("")
        self._empty_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_error_label.setWordWrap(True)
        self._empty_error_label.setStyleSheet(f"color: {COLOR_ERROR_DEFAULT}; font-size: {FONT_SIZE_BASE}px;")
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
        self._loading_bar.setFixedHeight(SPACE_1)
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

        loading_text = QLabel(t("route.calculating"))
        loading_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_text.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_BASE}px;")
        loading_layout.addWidget(loading_text)
        loading_layout.addStretch()
        self._result_stack.addWidget(loading_page)

        # Page 2: Populated result
        result_page = QWidget()
        result_layout = QVBoxLayout(result_page)
        result_layout.setContentsMargins(0, 8, 0, 0)
        result_layout.setSpacing(8)

        self.route_summary_label = QLabel()
        self.route_summary_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px;")
        result_layout.addWidget(self.route_summary_label)

        # Grid of 4 metric pills
        pills_grid = QGridLayout()
        pills_grid.setSpacing(6)

        self.pill_distance = make_result_pill("\u2014", t("route.result.distance"))
        self.pill_duration = make_result_pill("\u2014", t("route.result.duration"))
        self.pill_fuel_cost = make_result_pill("\u2014", t("route.result.fuel_cost", default="Cost combustibil"))
        self.pill_rate = make_result_pill("\u2014", t("route.result.cost_per_km", default="Cost/km"))

        pills_grid.addWidget(self.pill_distance, 0, 0)
        pills_grid.addWidget(self.pill_duration, 0, 1)
        pills_grid.addWidget(self.pill_fuel_cost, 1, 0)
        pills_grid.addWidget(self.pill_rate, 1, 1)

        result_layout.addLayout(pills_grid)

        # "Create Trip" button — right-aligned below pills
        create_trip_row = QWidget()
        create_trip_row_layout = QHBoxLayout(create_trip_row)
        create_trip_row_layout.setContentsMargins(0, 0, 0, 0)
        create_trip_row_layout.setSpacing(0)
        create_trip_row_layout.addStretch(1)

        self._create_trip_btn = QPushButton(t("route.create_trip", default="Create Trip"))
        self._create_trip_btn.setFixedHeight(32)
        self._create_trip_btn.setCursor(Qt.PointingHandCursor)
        self._create_trip_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_ACCENT_PRIMARY};
                color: {COLOR_TEXT_WHITE};
                border: none;
                border-radius: {RADIUS_SM}px;
                font-size: {FONT_SIZE_SM}px;
                font-weight: {FONT_WEIGHT_MEDIUM};
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background: {COLOR_ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background: {COLOR_ACCENT_HOVER};
            }}
        """)
        self._create_trip_btn.clicked.connect(self._on_create_trip)
        create_trip_row_layout.addWidget(self._create_trip_btn)

        result_layout.addWidget(create_trip_row)

        # Compliance texts
        self._summary_text = QLabel("")
        self._summary_text.setWordWrap(True)
        self._summary_text.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px;")
        result_layout.addWidget(self._summary_text)

        self._explanation_text = QLabel("")
        self._explanation_text.setWordWrap(True)
        self._explanation_text.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_XS}px;")
        result_layout.addWidget(self._explanation_text)

        self._dispatch_container = QWidget()
        self._dispatch_container_layout = QVBoxLayout(self._dispatch_container)
        self._dispatch_container_layout.setContentsMargins(0, 0, 0, 0)
        self._dispatch_container_layout.setSpacing(SPACE_2)
        self._dispatch_container.hide()
        result_layout.addWidget(self._dispatch_container)

        result_layout.addStretch()
        self._result_stack.addWidget(result_page)

        results_layout_inner.addWidget(self._result_stack)

        sl.addSpacing(4)
        card3, self._results_card_header = self._make_collapsible_card(
            t("route.section.result"), self._results_body, expanded=False
        )
        sl.addWidget(card3)

        sl.addStretch(1)

        # ── Pinned Bottom Button Bar ──
        self.calc_btn = QPushButton(t("route.calculate"))
        self.calc_btn.setFixedHeight(36)
        self.calc_btn.setObjectName("calc_route_btn")
        self.calc_btn.setCursor(Qt.PointingHandCursor)
        self.calc_btn.setEnabled(False)
        self.calc_btn.setStyleSheet(f"""
            QPushButton#calc_route_btn {{
                background: {COLOR_ACCENT_PRIMARY};
                color: {COLOR_TEXT_WHITE};
                border: none;
                border-radius: {RADIUS_MD}px;
                font-size: {FONT_SIZE_BASE}px;
                font-weight: {FONT_WEIGHT_MEDIUM};
            }}
            QPushButton#calc_route_btn:hover {{
                background: {COLOR_ACCENT_HOVER};
            }}
            QPushButton#calc_route_btn:pressed {{
                background: {COLOR_ACCENT_HOVER};
            }}
            QPushButton#calc_route_btn:disabled {{
                background: rgba(99, 102, 241, 0.4);
                color: rgba(255, 255, 255, 0.4);
            }}
        """)
        self.calc_btn.clicked.connect(self._on_calculate_click)
        bl.addWidget(self.calc_btn)

        export_btn = QPushButton(t("route.export_metadata"))
        export_btn.setFixedHeight(BTN_HEIGHT_SM)
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_SM}px;
                font-size: {FONT_SIZE_SM}px;
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

        share_btn = QPushButton(t("route.share", default="Share"))
        share_btn.setFixedHeight(BTN_HEIGHT_SM)
        share_btn.setCursor(Qt.PointingHandCursor)
        share_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_SM}px;
                font-size: {FONT_SIZE_SM}px;
                font-weight: {FONT_WEIGHT_REGULAR};
            }}
            QPushButton:hover {{
                background: {COLOR_BG_HOVER};
                color: {COLOR_TEXT_PRIMARY};
                border-color: {COLOR_BORDER_MEDIUM};
            }}
        """)
        share_btn.clicked.connect(self._on_share_route)
        bl.addWidget(share_btn)

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
        """Load trucks asynchronously — show spinner during load."""
        with PerfTimer("route_planner.load_trucks"):
            if hasattr(self, '_show_loading'):
                self._show_loading()
            WorkerPool.run(
                fn=self._fetch_trucks_with_slots,
                on_result=self._on_trucks_loaded,
                on_error=self._on_trucks_error,
            )

    def _fetch_trucks_with_slots(self) -> dict:
        """Background: fetch all trucks + batch slot information."""
        # Lazy-init conflict service to avoid direct instantiation in view
        if self._conflict_service is None and self.fleet_service is not None:
            from services.conflict_service import TripConflictService
            self._conflict_service = TripConflictService(self.fleet_service.db)
        rows = self.fleet_service.get_trucks() if self.fleet_service else []
        plates = [row["plate_number"] for row in rows]

        # BATCH: one query for all slot availability
        slot_map = {}
        if self._conflict_service and plates:
            slot_map = self._conflict_service.get_next_available_slots_for_trucks(plates)

        return {"trucks": rows, "slot_map": slot_map}

    def _on_trucks_loaded(self, data: dict) -> None:
        """GUI thread: populate truck combo from batch data."""
        with PerfTimer("route_planner.trucks_loaded"):
            if hasattr(self, '_hide_loading'):
                self._hide_loading()
            trucks = data["trucks"]
            slot_map = data.get("slot_map", {})

            self._trucks_map = {}
            self._truck_label_to_id = {}
            self.truck_combo.clear()
            for row in trucks:
                truck_id = str(row["id"])
                plate = row["plate_number"]
                label = f"{plate} - {row.get('model') or ''}"
                next_slot = slot_map.get(plate)
                if next_slot:
                    label = f"{label}  [Available: {next_slot}]"
                self._truck_label_to_id[label] = truck_id
                self._trucks_map[truck_id] = row
                self.truck_combo.addItem(label, truck_id)
            if trucks:
                self.truck_combo.setCurrentIndex(0)
                self._selected_truck_id = self._truck_label_to_id.get(self.truck_combo.currentText())

    def _on_trucks_error(self, error: str) -> None:
        """Handle truck load error."""
        if hasattr(self, '_hide_loading'):
            self._hide_loading()
        logger.error("Failed to load trucks: %s", error)

    def _on_truck_selected(self, _index: int) -> None:
        self._selected_truck_id = self._truck_label_to_id.get(self.truck_combo.currentText())

    # ── Country exclusions ─────────────────────────────────────────────────────

    def _on_exclusions_changed(self) -> None:
        if self._core is None:
            return
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
        with PerfTimer("route_planner.render_stops"):
            while self._stops_container_layout.count():
                item = self._stops_container_layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    # Block signals on the field to prevent stale lambda callbacks
                    # from firing after the widget is removed from the layout
                    if hasattr(w, "field"):
                        w.field.blockSignals(True)
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
                    placeholder = t("route.stop_destination")
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
        if self.map_widget is not None and hasattr(self.map_widget, '_run_js'):
            self.map_widget._run_js(js)

    def _refresh_chips(self) -> None:
        while self._chips_container_layout.count():
            item = self._chips_container_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if self._core is None:
            return
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

    def _inject_map_styles(self, ok: bool) -> None:
        if not ok or getattr(QtRoutePlannerView, "LEAFLET_CSS_INJECTED", False):
            return
        if self.map_widget is None:
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
        self._reverse_geocode_async(lat, lng)

    def _reverse_geocode_async(self, lat: float, lng: float) -> None:
        """Fire a daemon thread to reverse-geocode via GeocodingService and emit result via signal."""
        import threading

        def _work():
            try:
                # Delegated to GeocodingService (nominatim)
                address = self.geocode_service.reverse_geocode(lat, lon=lng)
            except Exception:
                address = None
            if not address:
                address = f"{lat:.5f}, {lng:.5f}"
            self.reverse_geocode_done.emit(address, lat, lng)

        t = threading.Thread(target=_work, daemon=True, name="ReverseGeocode")
        t.start()

    def _on_reverse_geocode_result(self, address: str, lat: float, lng: float) -> None:
        """Slot — called on GUI thread when reverse geocode completes."""
        new_stop = normalize_existing_stop({
            "type": "stop",
            "lat": lat,
            "lon": lng,
            "address": address,
            "resolved": True,
        })
        self.stops_state.insert(len(self.stops_state) - 1, new_stop)
        self._render_stops_list()

    # ── Calculation ────────────────────────────────────────────────────────────

    def _on_calculate_click(self) -> None:
        # Delegated to RoutePlannerController (validate → RouteService internally)
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
            self._empty_error_label.setStyleSheet(f"color: {COLOR_WARNING_DEFAULT}; font-size: {FONT_SIZE_BASE}px;")
            self._empty_error_label.show()
            return

        self._calc_token += 1
        token = self._calc_token

        # TASK 11: Show loading state
        self.calc_btn.setEnabled(False)
        self._result_stack.setCurrentIndex(1)  # loading page
        self._dispatch_container.hide()

        def callback(result):
            self.route_result_received.emit(result, ctx, token)

        self._core.start_calculation(ctx, callback)

    def _on_route_result(self, result, ctx, token: int) -> None:
        if token != self._calc_token:
            return

        self.calc_btn.setEnabled(True)

        # Delegated to RoutePlannerController (process → RouteService internally)
        processed, err = self._core.process_calculation_result(
            result,
            ctx,
            self._collect_stop_addresses(),
        )
        if err:
            self._result_stack.setCurrentIndex(0)
            self._empty_error_label.setText(err)
            self._empty_error_label.setStyleSheet(f"color: {COLOR_ERROR_DEFAULT}; font-size: {FONT_SIZE_BASE}px;")
            self._empty_error_label.show()
            return
        if not processed:
            self._result_stack.setCurrentIndex(0)
            self._empty_error_label.setText(t("route.calc_failed"))
            self._empty_error_label.setStyleSheet(f"color: {COLOR_ERROR_DEFAULT}; font-size: {FONT_SIZE_BASE}px;")
            self._empty_error_label.show()
            return

        self._last_route_result = processed.route
        self._last_route_history_id = processed.route.get("history_id")
        self._last_route_calc_ctx = ctx
        self._populate_stops_from_route(processed.route)

        # Auto-expand the Results card
        if hasattr(self, '_results_card_header'):
            if not self._result_stack.isVisible():
                self._results_body.setVisible(True)
                header = self._results_card_header
                header.setText(f"\u25BC  {t('route.section.result').upper()}")

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

        # Open in Google Maps
        gmaps_btn = QPushButton(
            t("route.open_in_gmaps", default="Google Maps")
        )
        gmaps_btn.setFixedHeight(36)
        gmaps_btn.setCursor(Qt.PointingHandCursor)
        gmaps_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_SM}px;
                font-size: {FONT_SIZE_SM}px;
                font-weight: {FONT_WEIGHT_REGULAR};
                padding: 0 {SPACE_3}px;
            }}
            QPushButton:hover {{
                background: {COLOR_BG_HOVER};
                color: {COLOR_TEXT_PRIMARY};
                border-color: {COLOR_BORDER_MEDIUM};
            }}
        """)
        gmaps_btn.clicked.connect(self._on_open_in_gmaps)
        btn_layout.addWidget(gmaps_btn)

        discard_btn = Btn(btn_row, "", variant="danger", icon_name="mdi6.delete", command=self._discard_route)
        discard_btn.setFixedSize(36, 36)
        btn_layout.addWidget(discard_btn)

        self._dispatch_container_layout.addWidget(btn_row)
        self._dispatch_container.show()

    def _go_to_calculator(self) -> None:
        if self._last_route_history_id:
            truck_id = str(self._selected_truck_id) if self._selected_truck_id else None
            # Delegated to RoutePersistenceService (commit + truck assignment)
            self._persistence.commit_route(self._last_route_history_id, truck_id=truck_id)
            self._pending_clear = True
        if self.controller and hasattr(self.controller, "_switch_module"):
            self.controller._switch_module("calculator")

    def _discard_route(self) -> None:
        if self._last_route_history_id:
            # Delegated to RouteHistoryService
            self.route_history_service.discard_route(self._last_route_history_id)
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
        self._summary_text.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px;")
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

    # ── Create Trip ───────────────────────────────────────────────────────

    def _on_create_trip(self) -> None:
        """Create a trip pre-filled with route data, show success, navigate."""
        if not self._last_route_result or not self._persistence:
            return
        truck_id = str(self._selected_truck_id) if self._selected_truck_id else None
        try:
            self._persistence.commit_route(self._last_route_history_id, truck_id=truck_id)
            self._pending_clear = True
            self._summary_text.setText(t("route.create_trip_success", default="✓ Trip created successfully"))
            self._summary_text.setStyleSheet(f"color: {COLOR_SUCCESS_DEFAULT}; font-size: {FONT_SIZE_SM}px;")
            logger.info("Trip created from route #%s", self._last_route_history_id)
            # Navigate to dispatch board
            if self.controller and hasattr(self.controller, "_switch_module"):
                self.controller._switch_module("dispatch_board")
        except Exception as exc:
            logger.exception("Failed to create trip")
            self._summary_text.setText(
                t("route.create_trip_error", default="Failed to create trip: {error}").format(error=str(exc))
            )
            self._summary_text.setStyleSheet(f"color: {COLOR_ERROR_DEFAULT}; font-size: {FONT_SIZE_SM}px;")

    def _populate_stops_from_route(self, route: dict) -> None:
        stops = route.get("stops") or []
        for i, stop in enumerate(self.stops_state):
            if i < len(stops):
                try:
                    stop["lat"], stop["lon"] = float(stops[i][0]), float(stops[i][1])
                    stop["resolved"] = True
                except Exception:
                    pass
            # Populate address from coordinates if the stop has no address
            sid = stop.get("id", "")
            if sid and not stop.get("address") and stop.get("lat") is not None and stop.get("lon") is not None:
                fallback = f"{stop['lat']:.5f}, {stop['lon']:.5f}"
                stop["address"] = fallback
                if sid in self.stop_vars and not self.stop_vars[sid]:
                    self.stop_vars[sid] = fallback

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
            self._summary_text.setStyleSheet(f"color: {COLOR_WARNING_DEFAULT};")
            return
        self._summary_text.setText(t("route.export_success").format(path))
        self._summary_text.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px;")

    # ── Share / Google Maps ────────────────────────────────────────────────────

    def _on_share_route(self) -> None:
        if not self._last_route_result:
            return


        stops = extract_stops_from_route_result(self._last_route_result)
        route = self._last_route_result
        truck_label = None
        truck_id = None
        if self._selected_truck_id and self._trucks_map:
            truck_id = self._selected_truck_id
            truck_obj = self._trucks_map.get(truck_id, {})
            truck_label = truck_obj.get("plate_number") or truck_obj.get("name")

        profile_key = self._profile_display_to_key.get(
            self.profile_combo.currentText(), "Recommended"
        )

        share_url = build_share_url(
            stops=stops,
            profile=profile_key,
            truck_id=truck_id,
            truck_label=truck_label,
        )

        # Build Google Maps URL
        route_stops = route.get("stops") or []
        gmaps_url = ""
        if len(route_stops) >= 2:
            origin = (float(route_stops[0][0]), float(route_stops[0][1]))
            destination = (float(route_stops[-1][0]), float(route_stops[-1][1]))
            waypoints = []
            for s in route_stops[1:-1]:
                waypoints.append((float(s[0]), float(s[1])))
            gmaps_url = build_google_maps_url(origin, destination, waypoints)

        from ui.dialogs.share_route_dialog import ShareRouteDialog

        dialog = ShareRouteDialog(
            parent=self,
            share_url=share_url,
            google_maps_url=gmaps_url,
            on_export_file=self._on_share_export_file,
            on_share_via_os=self._on_share_via_os,
            on_open_in_gmaps=self._on_open_in_gmaps,
        )
        dialog.exec()

    def _on_share_export_file(self) -> str | None:
        """Export the current route as a .operionroute file and return the path."""
        if not self._last_route_result:
            return None

        path, _ = QFileDialog.getSaveFileName(
            self,
            t("route.export_file_title", default="Save Route File"),
            f"route_{self._last_route_history_id or 'export'}.operionroute",
            "Operion Route (*.operionroute)",
        )
        if not path:
            return None

        from services.route_sharing_service import encode_route_file

        stops = extract_stops_from_route_result(self._last_route_result)
        route = self._last_route_result
        profile_key = self._profile_display_to_key.get(
            self.profile_combo.currentText(), "Recommended"
        )
        truck_label = None
        truck_id = None
        if self._selected_truck_id:
            truck_id = self._selected_truck_id
            truck_obj = self._trucks_map.get(truck_id, {})
            truck_label = truck_obj.get("plate_number") or truck_obj.get("name")

        data = encode_route_file(
            stops=stops,
            profile=profile_key,
            truck_id=truck_id,
            truck_label=truck_label,
            geometry=route.get("geometry"),
            distance_km=route.get("distance_km"),
            duration_min=route.get("duration_min"),
        )

        try:
            # Delegated to ExportService for file I/O
            self.export_service.save_binary(path, data)
            self._summary_text.setText(
                t("route.export_success_file", default="Route saved: {path}").format(path=path)
            )
            self._summary_text.setStyleSheet(
                f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px;"
            )
            return path
        except OSError as exc:
            self._summary_text.setText(
                t("route.export_error", default="Failed to save: {error}").format(error=str(exc))
            )
            self._summary_text.setStyleSheet(
                f"color: {COLOR_ERROR_DEFAULT}; font-size: {FONT_SIZE_SM}px;"
            )
            return None

    def _on_share_via_os(self) -> None:
        """Export route file and open its containing folder in Explorer."""
        path = self._on_share_export_file()
        if not path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def _on_open_in_gmaps(self) -> None:
        """Open the current route in Google Maps in the default browser."""
        if not self._last_route_result:
            return

        route_stops = self._last_route_result.get("stops") or []
        if len(route_stops) < 2:
            return

        origin = (float(route_stops[0][0]), float(route_stops[0][1]))
        destination = (float(route_stops[-1][0]), float(route_stops[-1][1]))
        waypoints = []
        for s in route_stops[1:-1]:
            waypoints.append((float(s[0]), float(s[1])))

        gmaps_url = build_google_maps_url(origin, destination, waypoints)

        QDesktopServices.openUrl(QUrl(gmaps_url))

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

    @property
    def lbl_info(self) -> QLabel:
        """Backward-compat alias for the summary text label (used by tests)."""
        return self._summary_text

    def _remove_stop_field(self) -> None:
        """Backward-compat: remove the last intermediate stop (used by tests)."""
        stop_indices = [i for i, s in enumerate(self.stops_state) if s.get("type") == "stop"]
        if stop_indices:
            self._remove_stop_index(stop_indices[-1])

    def _toggle_click_add(self, enabled: bool) -> None:
        """Backward-compat: enable/disable click-to-add mode (used by tests)."""
        self._click_to_add_enabled = bool(enabled)
        if hasattr(self, "_click_add_check"):
            self._click_add_check.setChecked(bool(enabled))

    # ── Navigation data (from deep link / file open) ──────────────────────────

    def handle_nav_data(self, data: dict[str, Any]) -> None:
        """Handle incoming navigation data from a share URL or file open.

        Called by ``MainWindow._switch_module`` when the module is
        navigated to with data (e.g. ``--open-url`` or ``--open-file``).
        """
        share_url = data.get("share_url")
        share_file = data.get("share_file")
        if share_url:
            self._load_from_share_url(share_url)
        elif share_file:
            self._load_from_share_file(share_file)

    def _load_from_share_url(self, url: str) -> None:
        """Load route state from a share URL and trigger calculation."""
        patch = self._core.load_from_url(url)
        if patch is None:
            return
        self._apply_share_patch(patch)

    def _load_from_share_file(self, path: str) -> None:
        """Load route state from a .operionroute file and trigger calculation."""
        patch = self._core.load_from_route_file(path)
        if patch is None:
            return
        self._apply_share_patch(patch)

    def _apply_share_patch(self, patch: dict[str, Any]) -> None:
        """Apply a planner state patch from a share URL or file.

        Populates stops, selects the truck/profile, then fires the
        route calculation so the recipient sees the route immediately.
        """
        stops = patch.get("stops", [])
        if len(stops) >= 2:
            self.stops_state = stops
            self.stop_vars = {}
            self._render_stops_list()

        profile_label = patch.get("profile_label", "Recommended")
        display = self._profile_key_to_display.get(profile_label)
        if display:
            self.profile_combo.setCurrentText(display)

        truck_id = patch.get("truck_id")
        if truck_id:
            idx = self.truck_combo.findData(truck_id)
            if idx >= 0:
                self.truck_combo.setCurrentIndex(idx)

        # Also handle route result if the file contained full geometry
        route = patch.get("route")
        if route and route.get("geometry"):
            self._last_route_result = route
            self._show_route_result(
                distance_km=float(route.get("distance_km", 0)),
                duration_min=float(route.get("duration_min", 0)),
                fuel_cost_eur=0,
                summary_text="",
            )
            if self._map_renderer:
                self._map_renderer.draw_route(
                    route["geometry"],
                    route,
                    show_comparison=self._compare_check.isChecked(),
                    highlight_avoided=True,
                )
                self._map_renderer.update_stop_markers(self.stops_state)
                self._map_renderer.center_on_geometry(route["geometry"])
        else:
            # No geometry — trigger a fresh calculation
            self._on_calculate_click()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        if self._pending_clear:
            self._pending_clear = False
            self._clear_route_state()
        # Recreate map widget if it was destroyed by shutdown()
        try:
            self.map_widget.isWidgetType()
        except RuntimeError:
            self.map_widget = None
            self._map_renderer = None
            QtRoutePlannerView.LEAFLET_CSS_INJECTED = False
            self._lazy_init_map()

    def shutdown(self) -> None:
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)
        # Unsubscribe from the event bus so a recreated view doesn't
        # get duplicate events from a dead instance.
        if getattr(self, "_event_subscribed", False):
            try:
                self._event_bus.unsubscribe(TRUCK_CREATED, self._on_truck_event)
                self._event_bus.unsubscribe(TRUCK_UPDATED, self._on_truck_event)
                self._event_bus.unsubscribe(TRUCK_DELETED, self._on_truck_event)
            except Exception:
                pass
            self._event_subscribed = False
        # Cancel any in-flight route calculation and wait for completion
        with contextlib.suppress(Exception):
            if self._core is not None:
                self._core.cancel_calculation()
                runner = getattr(self._core, "_runner", None)
                if runner is not None:
                    thread = getattr(runner, "_current_thread", None)
                    if thread is not None and thread.is_alive():
                        thread.join(timeout=2.0)
        with contextlib.suppress(Exception):
            self.map_widget.destroy()
        self._map_renderer = None
