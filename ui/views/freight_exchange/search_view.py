"""Freight Exchange search view — manual load search across providers."""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import (
    Btn,
    Divider,
    EmptyState,
    FieldLabel,
    Icon,
    Label,
    SectionTitle,
)
from ui.design_tokens import (
    COLOR_ACCENT_BORDER,
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_ELEVATED,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_ERROR_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_NEUTRAL_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    COLOR_WARNING_TEXT,
    FONT_SIZE_XS,
    INPUT_HEIGHT,
    RADIUS_LG,
    RADIUS_SM,
    ROW_HEIGHT,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
)
from ui.widgets import StyledTableWidget

logger = logging.getLogger(__name__)


class FreightSearchView(QWidget):
    """Search freight loads across connected providers."""

    def __init__(
        self,
        db,
        parent: Optional[QWidget] = None,
        freight_service=None,
    ):
        super().__init__(parent)
        self.db = db
        # ``freight_service`` is the RemoteFreightExchangeService injected in
        # remote mode; when set it takes precedence over the raw ``_api``
        # client configured by the host (see ``_on_search``).
        self._freight_service = freight_service
        self.setObjectName("freight_search_view")
        self._build_ui()

    # ── Public API ─────────────────────────────────────────────────

    def set_health_indicators(self, providers: list[dict]) -> None:
        """Update provider health indicators in the summary bar.

        Each dict must have keys ``status`` and ``name``.
        Status values: connected | healthy | degraded | error | down | disconnected.
        """
        self._clear_health_indicators()
        for p in providers:
            status = p.get("status", "disconnected")
            name = p.get("name", "")
            dot_color = self._health_color(status)
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(
                f"background: {dot_color}; border-radius: 4px;"
            )
            self._health_container.addWidget(dot)
            self._health_container.addSpacing(SPACE_1)
            self._health_container.addWidget(
                Label(self._summary_bar, name, role="muted")
            )
            self._health_container.addSpacing(SPACE_3)

    def show_loading(self, searching: bool = True) -> None:
        """Show or hide the loading overlay over the results table."""
        self._loading_overlay.setVisible(searching)
        self._search_btn.setEnabled(not searching)
        self._search_btn.setText(
            t("freight.searching") if searching else t("freight.filter.search_now")
        )
        if searching:
            self._results_table.hide()
            self._empty_state.hide()
            self._error_card.hide()
        else:
            self._results_table.show()

    def show_empty(self, visible: bool = True) -> None:
        """Show or hide the empty state in place of the table."""
        self._empty_state.setVisible(visible)
        self._results_table.setVisible(not visible)
        self._error_card.hide()

    def show_error(self, message: str) -> None:
        """Show an error card above the table."""
        self._error_label.setText(message)
        self._error_card.show()
        self._results_table.hide()
        self._empty_state.hide()

    def set_result_count(self, count: int) -> None:
        """Update the result count text in the summary bar."""
        self._result_count_label.setText(
            t("freight.results.count", count=count) if count >= 0 else ""
        )

    def set_table_data(self, rows: list[dict]) -> None:
        """Populate the results table with data rows."""
        self._results_table.set_data(rows)
        actions_col = 7  # last column (actions)
        for r in range(self._results_table.rowCount()):
            self._results_table.setCellWidget(
                r, actions_col, self._create_action_widget()
            )
        self._results_table.show()
        self._empty_state.hide()
        self._error_card.hide()

    def update_status_bar(
        self, has_providers: bool = True, last_updated: str = ""
    ) -> None:
        """Update the bottom status bar text."""
        if not has_providers:
            self._status_label.setText(t("freight.connection.no_providers"))
            self._status_label.setStyleSheet(
                f"font-size: {FONT_SIZE_XS}px; color: {COLOR_WARNING_TEXT};"
            )
        else:
            self._status_label.setStyleSheet(
                f"font-size: {FONT_SIZE_XS}px; color: {COLOR_TEXT_TERTIARY};"
            )
            if last_updated:
                self._status_label.setText(last_updated)
            else:
                self._status_label.setText(t("freight.results.last_updated"))

    # ── UI Construction ────────────────────────────────────────────

    def _build_ui(self):
        # Root layout: QHBoxLayout(self), margins SPACE_5, spacing SPACE_4
        root = QHBoxLayout(self)
        root.setContentsMargins(SPACE_5, SPACE_5, SPACE_5, SPACE_5)
        root.setSpacing(SPACE_4)

        self._build_sidebar()
        root.addWidget(self._sidebar)

        self._build_content()
        root.addLayout(self._right_area, 1)

    def _build_sidebar(self):
        self._sidebar = QWidget()
        self._sidebar.setObjectName("filter_panel")
        self._sidebar.setFixedWidth(280)
        self._sidebar.setStyleSheet(f"""
            QWidget#filter_panel {{
                background: {COLOR_BG_ELEVATED};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_LG}px;
            }}
        """)

        layout = QVBoxLayout(self._sidebar)
        layout.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
        layout.setSpacing(SPACE_4)

        # 1. SectionTitle
        layout.addWidget(SectionTitle(self._sidebar, t("freight.filters.title")))
        # 2. Divider
        layout.addWidget(Divider(self._sidebar))

        # ── Route group ──
        layout.addWidget(FieldLabel(self._sidebar, t("freight.filters.route")))
        self._origin_input = QLineEdit()
        self._origin_input.setPlaceholderText(t("freight.filter.loading_place"))
        self._origin_input.setFixedHeight(INPUT_HEIGHT)
        layout.addWidget(self._origin_input)

        self._dest_input = QLineEdit()
        self._dest_input.setPlaceholderText(t("freight.filter.delivery_place"))
        self._dest_input.setFixedHeight(INPUT_HEIGHT)
        layout.addWidget(self._dest_input)

        # ── Date group ──
        layout.addWidget(FieldLabel(self._sidebar, t("freight.filters.date_range")))
        date_row = QHBoxLayout()
        date_row.setSpacing(SPACE_2)
        self._date_from = QLineEdit()
        self._date_from.setPlaceholderText(
            t("freight.filter.date_from_placeholder")
        )
        self._date_from.setFixedHeight(INPUT_HEIGHT)
        date_row.addWidget(self._date_from)
        date_row.addWidget(Label(self._sidebar, "\u2013", role="muted"))
        self._date_to = QLineEdit()
        self._date_to.setPlaceholderText(
            t("freight.filter.date_to_placeholder")
        )
        self._date_to.setFixedHeight(INPUT_HEIGHT)
        date_row.addWidget(self._date_to)
        layout.addLayout(date_row)

        # ── Vehicle group ──
        layout.addWidget(FieldLabel(self._sidebar, t("freight.filters.vehicle")))
        self._trailer_combo = QComboBox()
        self._trailer_combo.addItems([
            t("freight.trailer.any"),
            t("freight.trailer.standard"),
            t("freight.trailer.refrigerated"),
            t("freight.trailer.tanker"),
            t("freight.trailer.flatbed"),
            t("freight.trailer.low_loader"),
        ])
        self._trailer_combo.setFixedHeight(INPUT_HEIGHT)
        layout.addWidget(self._trailer_combo)

        self._adr_check = QCheckBox(t("freight.filter.adr"))
        layout.addWidget(self._adr_check)

        # ── Weight group ──
        layout.addWidget(FieldLabel(self._sidebar, t("freight.filter.weight")))
        weight_row = QHBoxLayout()
        self._weight_min = QLineEdit()
        self._weight_min.setPlaceholderText(t("freight.filter.weight_min_placeholder"))
        self._weight_min.setFixedHeight(INPUT_HEIGHT)
        self._weight_max = QLineEdit()
        self._weight_max.setPlaceholderText(t("freight.filter.weight_max_placeholder"))
        self._weight_max.setFixedHeight(INPUT_HEIGHT)
        weight_row.addWidget(self._weight_min)
        weight_row.addWidget(QLabel("–"))
        weight_row.addWidget(self._weight_max)
        layout.addLayout(weight_row)
        layout.addSpacing(SPACE_3)

        # ── Price group ──
        layout.addWidget(FieldLabel(self._sidebar, t("freight.filter.price")))
        price_row = QHBoxLayout()
        self._price_min = QLineEdit()
        self._price_min.setPlaceholderText(t("freight.filter.price_min_placeholder", default="Min €"))
        self._price_min.setFixedHeight(INPUT_HEIGHT)
        self._price_max = QLineEdit()
        self._price_max.setPlaceholderText(t("freight.filter.price_max_placeholder", default="Max €"))
        self._price_max.setFixedHeight(INPUT_HEIGHT)
        price_row.addWidget(self._price_min)
        price_row.addWidget(QLabel("–"))
        price_row.addWidget(self._price_max)
        layout.addLayout(price_row)
        layout.addSpacing(SPACE_3)

        # ── Distance max ──
        layout.addWidget(FieldLabel(self._sidebar, t("freight.filter.distance")))
        self._distance_max = QLineEdit()
        self._distance_max.setPlaceholderText(t("freight.filter.distance_max_placeholder"))
        self._distance_max.setFixedHeight(INPUT_HEIGHT)
        layout.addWidget(self._distance_max)
        layout.addSpacing(SPACE_3)

        # ── Loading type ──
        layout.addWidget(FieldLabel(self._sidebar, t("freight.filter.loading_type")))
        self._loading_type = QComboBox()
        self._loading_type.addItems([t("freight.loading_type.any"), "FTL", "LTL"])
        self._loading_type.setFixedHeight(INPUT_HEIGHT)
        layout.addWidget(self._loading_type)
        layout.addSpacing(SPACE_3)

        # ── Country ──
        layout.addWidget(FieldLabel(self._sidebar, t("freight.filter.country")))
        self._loading_country = QLineEdit()
        self._loading_country.setPlaceholderText(t("freight.filter.loading_country_placeholder"))
        self._loading_country.setFixedHeight(INPUT_HEIGHT)
        layout.addWidget(self._loading_country)
        self._delivery_country = QLineEdit()
        self._delivery_country.setPlaceholderText(t("freight.filter.delivery_country_placeholder"))
        self._delivery_country.setFixedHeight(INPUT_HEIGHT)
        layout.addWidget(self._delivery_country)
        layout.addSpacing(SPACE_3)

        # ── Sidebar buttons (bottom, after addStretch()) ──
        layout.addStretch()

        self._search_btn = Btn(
            self._sidebar,
            text=t("freight.filter.search_now"),
            variant="primary",
            icon_name="mdi6.magnify",
            size="md",
        )
        self._search_btn.clicked.connect(self._on_search)
        self._search_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self._search_btn)

        layout.addSpacing(SPACE_3)

        self._save_btn = Btn(
            self._sidebar,
            text=t("freight.filter.save_search"),
            variant="secondary",
            icon_name="mdi6.content-save-outline",
            size="sm",
        )
        self._save_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self._save_btn)

    def _build_content(self):
        self._right_area = QVBoxLayout()
        self._right_area.setSpacing(SPACE_4)

        # ── Summary bar ──
        self._build_summary_bar()
        self._right_area.addWidget(self._summary_bar)

        # ── Error card (hidden by default) ──
        self._build_error_card()
        self._right_area.addWidget(self._error_card)

        # ── Sort controls ──
        sort_row = QHBoxLayout()
        sort_label = Label(self, t("freight.filter.sort_by") + ":", role="muted")
        sort_row.addWidget(sort_label)
        self._sort_combo = QComboBox()
        self._sort_combo.addItems([
            t("freight.sort.relevance"),
            t("freight.sort.price_asc"), t("freight.sort.price_desc"),
            t("freight.sort.distance_asc"), t("freight.sort.distance_desc"),
            t("freight.sort.date_asc"), t("freight.sort.date_desc"),
        ])
        self._sort_combo.setFixedHeight(INPUT_HEIGHT)
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        sort_row.addWidget(self._sort_combo)
        sort_row.addStretch()
        self._right_area.addLayout(sort_row)

        # ── Results table ──
        self._build_results_table()
        self._right_area.addWidget(self._results_table, 1)

        # ── Empty state (hidden by default) ──
        self._empty_state = EmptyState(
            parent=self,
            icon_name="mdi6.magnify-close",
            title=t("freight.results.empty_title"),
            subtitle=t("freight.results.empty_subtitle"),
        )
        self._right_area.addWidget(self._empty_state)

        # ── Status bar ──
        self._status_label = Label(self, role="muted")
        self._right_area.addWidget(self._status_label)

        # Initial state
        self._empty_state.hide()
        self._error_card.hide()
        self._loading_overlay.hide()
        self.update_status_bar(has_providers=False)

    def _build_summary_bar(self):
        self._summary_bar = QWidget()
        self._summary_bar.setStyleSheet(f"""
            QWidget {{
                background: {COLOR_BG_ELEVATED};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_LG}px;
            }}
        """)
        layout = QHBoxLayout(self._summary_bar)
        layout.setContentsMargins(SPACE_4, SPACE_3, SPACE_4, SPACE_3)

        self._result_count_label = Label(self._summary_bar, role="muted")
        layout.addWidget(self._result_count_label)
        layout.addStretch()

        self._health_container = QHBoxLayout()
        self._health_container.setSpacing(0)  # spacing managed by addSpacing calls
        layout.addLayout(self._health_container)

    def _build_error_card(self):
        self._error_card = QFrame(self)
        self._error_card.setStyleSheet(f"""
            background: {COLOR_ERROR_SUBTLE};
            border: 1px solid {COLOR_ERROR_DEFAULT};
            border-radius: {RADIUS_LG}px;
        """)
        error_layout = QHBoxLayout(self._error_card)
        error_layout.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
        error_layout.setSpacing(SPACE_2)

        error_icon = Icon("mdi6.alert-circle", color=COLOR_ERROR_TEXT, size=24)
        error_layout.addWidget(error_icon)

        self._error_label = Label(self._error_card, "", role="danger")
        error_layout.addWidget(self._error_label, 1)

    def _build_results_table(self):
        self._results_table = StyledTableWidget(
            parent=self,
            columns=[
                ("provider", t("freight.col.provider"), 100),
                ("origin", t("freight.filter.loading_place"), 140),
                ("destination", t("freight.filter.delivery_place"), 140),
                ("price", t("freight.filter.price"), 100),
                ("distance", t("freight.filter.distance"), 100),
                ("trailer", t("freight.filter.trailer_type"), 120),
                ("adr", t("freight.filter.adr"), 60),
                ("actions", "", 140),
            ],
        )
        # Alignments
        self._results_table.set_column_alignment(
            "price", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._results_table.set_column_alignment(
            "distance", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._results_table.set_column_alignment(
            "adr", Qt.AlignmentFlag.AlignCenter
        )
        self._results_table.set_column_alignment(
            "actions", Qt.AlignmentFlag.AlignCenter
        )
        # Row height
        self._results_table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)

        # Loading overlay — child of the table, covers it when shown
        self._loading_overlay = QFrame(self._results_table)
        self._loading_overlay.setStyleSheet(
            "background: rgba(12,12,14,0.7);"
        )
        self._loading_overlay.setCursor(Qt.CursorShape.WaitCursor)
        overlay_layout = QVBoxLayout(self._loading_overlay)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addWidget(
            Icon("mdi6.loading", color=COLOR_TEXT_SECONDARY, size=24)
        )
        overlay_layout.addWidget(
            Label(self._loading_overlay, t("freight.searching"), role="muted")
        )

        # Keep overlay sized to table
        self._results_table.resizeEvent = lambda ev: (
            setattr(self._loading_overlay, "_ignore_resize", True)
            or self._loading_overlay.resize(self._results_table.size())
            or StyledTableWidget.resizeEvent(self._results_table, ev)
        )

    def _create_action_widget(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(SPACE_1, 0, SPACE_1, 0)
        layout.setSpacing(SPACE_1)

        import_btn = Btn(
            container, text=t("freight.import"), variant="primary", size="sm"
        )
        layout.addWidget(import_btn)

        eval_btn = Btn(
            container, text=t("freight.evaluate"), variant="ghost", size="sm"
        )
        eval_btn.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {COLOR_ACCENT_BORDER};
                color: {COLOR_ACCENT_PRIMARY};
                border-radius: {RADIUS_SM}px;
            }}
        """)
        layout.addWidget(eval_btn)

        return container

    # ── Helpers ────────────────────────────────────────────────────

    def _on_sort_changed(self, index: int) -> None:
        """Handle sort combo changes — will re-query when API is available."""
        logger.debug("Sort changed to index %d (%s)", index, self._sort_combo.currentText())
        # Re-run search with new sort if there's an active search
        if self._origin_input.text().strip() and self._dest_input.text().strip():
            self._on_search()

    @staticmethod
    def _parse_float(text: str) -> Optional[float]:
        """Parse a float from user input, returning None if empty or invalid."""
        cleaned = text.strip().replace(",", ".").replace(" ", "")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _clear_health_indicators(self):
        while self._health_container.count():
            item = self._health_container.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    @staticmethod
    def _health_color(status: str) -> str:
        mapping = {
            "connected": COLOR_SUCCESS_DEFAULT,
            "healthy": COLOR_SUCCESS_DEFAULT,
            "degraded": COLOR_WARNING_DEFAULT,
            "error": COLOR_ERROR_DEFAULT,
            "down": COLOR_ERROR_DEFAULT,
            "disconnected": COLOR_NEUTRAL_DEFAULT,
        }
        return mapping.get(status, COLOR_NEUTRAL_DEFAULT)

    def _on_search(self):
        """Execute a search (placeholder — wired when API is available)."""
        origin = self._origin_input.text().strip()
        dest = self._dest_input.text().strip()

        if not origin or not dest:
            self.show_error(
                t("freight.filter.missing_route")
            )
            return

        # Read new filter fields
        weight_min = self._parse_float(self._weight_min.text())
        weight_max = self._parse_float(self._weight_max.text())
        price_min = self._parse_float(self._price_min.text())
        price_max = self._parse_float(self._price_max.text())
        distance_max = self._parse_float(self._distance_max.text())
        loading_type = self._loading_type.currentText().strip()
        loading_country = self._loading_country.text().strip()
        delivery_country = self._delivery_country.text().strip()
        sort_field = self._sort_combo.currentText() if hasattr(self, "_sort_combo") else ""

        search_params = {
            "origin": origin,
            "dest": dest,
            "date_from": self._date_from.text().strip(),
            "date_to": self._date_to.text().strip(),
            "trailer": self._trailer_combo.currentText(),
            "adr": self._adr_check.isChecked(),
            "weight_min": weight_min,
            "weight_max": weight_max,
            "price_min": price_min,
            "price_max": price_max,
            "distance_max": distance_max,
            "loading_type": loading_type,
            "loading_country": loading_country,
            "delivery_country": delivery_country,
            "sort": sort_field,
        }
        logger.debug("Search params: %s", search_params)

        # Call real API
        self.show_loading(searching=True)
        try:
            # Build filter kwargs for search_loads()
            # Only include non-None, non-empty values
            pickup_date_from = self._date_from.text().strip()
            pickup_date_to = self._date_to.text().strip()
            kwargs = {
                "origin_location": origin if origin else None,
                "destination_location": dest if dest else None,
                "pickup_date_from": pickup_date_from if pickup_date_from else None,
                "pickup_date_to": pickup_date_to if pickup_date_to else None,
            }

            # Trailer type — must be list[str]
            trailer_text = self._trailer_combo.currentText().strip()
            if trailer_text and trailer_text != t("freight.trailer.any"):
                kwargs["trailer_type"] = [trailer_text]

            # ADR
            if hasattr(self._adr_check, 'isChecked'):
                kwargs["adr_required"] = self._adr_check.isChecked()

            # Weight
            if weight_min:
                try:
                    kwargs["weight_kg_min"] = float(weight_min)
                except ValueError:
                    pass
            if weight_max:
                try:
                    kwargs["weight_kg_max"] = float(weight_max)
                except ValueError:
                    pass

            # Distance
            if distance_max:
                try:
                    kwargs["distance_km_max"] = float(distance_max)
                except ValueError:
                    pass

            # Price
            if price_min:
                try:
                    kwargs["price_min"] = float(price_min)
                except ValueError:
                    pass

            # Loading type
            if loading_type:
                kwargs["loading_type"] = loading_type

            # Countries
            if loading_country:
                kwargs["loading_country"] = loading_country
            if delivery_country:
                kwargs["delivery_country"] = delivery_country

            # Sort — map display text to API fields
            sort_text = "Date desc"
            if hasattr(self, "_sort_combo"):
                try:
                    sort_text = self._sort_combo.currentText()
                except Exception:
                    pass
            sort_field, sort_order = _map_sort_field(sort_text)
            if sort_field:
                kwargs["sort_by"] = sort_field
            if sort_order:
                kwargs["sort_order"] = sort_order

            # Call the API — prefer the injected freight service (remote mode,
            # e.g. ``RemoteFreightExchangeService``), falling back to the raw
            # ``_api`` client configured by the host.
            if getattr(self, "_freight_service", None) is not None:
                response = self._freight_service.search_loads(**kwargs)
            elif not hasattr(self, '_api') or self._api is None:
                raise RuntimeError("API client not configured")
            else:
                response = self._api.search_loads(**kwargs)
            results = response.get("results", [])
            provider_statuses = response.get("provider_statuses", [])
            providers_queried = response.get("providers_queried", 0)
            providers_skipped = response.get("providers_skipped", 0)

            # Update health indicators
            self.set_health_indicators(provider_statuses)

            # Map results to table rows
            rows = []
            for r in results:
                price_str = f"{r.get('price', {}).get('amount', 0):,.0f} {r.get('price', {}).get('currency', 'EUR')}" if isinstance(r.get('price'), dict) else str(r.get('price', ''))
                dist = r.get("distance_km", 0)
                dist_str = f"{dist:,.0f} km" if dist > 0 else ""
                rows.append({
                    "provider": r.get("provider_id", "").upper() if r.get("provider_id") else "",
                    "provider_id": r.get("provider_id", ""),
                    "load_id": r.get("provider_load_id", r.get("result_id", "")),
                    "origin": r.get("origin", ""),
                    "destination": r.get("destination", ""),
                    "price": price_str,
                    "distance": dist_str,
                    "trailer": r.get("trailer_type", ""),
                    "adr": "Yes" if r.get("adr") else "No",
                    "loading_type": str(r.get("loading_type", "")).upper(),
                    "__raw": r,  # preserve full result for detail view
                })

            self.set_table_data(rows)
            self.set_result_count(len(rows))

            # Status bar
            status_text = f"{providers_queried} provider(s) queried"
            if providers_skipped > 0:
                status_text += f", {providers_skipped} skipped"
            self._status_label.setText(status_text)

        except Exception as e:
            logger.exception("Search failed")
            self.show_error(f"Search failed: {str(e)[:200]}")
        finally:
            self.show_loading(searching=False)


def _map_sort_field(sort_text: str) -> tuple[str | None, str | None]:
    """Map UI sort display text to API sort_by and sort_order.

    Examples:
        "Price ↑" → ("price", "asc")
        "Date ↓" → ("date", "desc")
    """
    mapping = {
        "Price ↑": ("price", "asc"),
        "Price ↓": ("price", "desc"),
        "Distance ↑": ("distance", "asc"),
        "Distance ↓": ("distance", "desc"),
        "Date ↑": ("date", "asc"),
        "Date ↓": ("date", "desc"),
    }
    result = mapping.get(sort_text)
    if result:
        return result
    # Fallback: parse from text
    text_lower = sort_text.lower()
    if "price" in text_lower:
        return ("price", "asc" if "↑" in sort_text else "desc")
    if "distance" in text_lower:
        return ("distance", "asc" if "↑" in sort_text else "desc")
    if "date" in text_lower:
        return ("date", "asc" if "↑" in sort_text else "desc")
    return ("date", "desc")
