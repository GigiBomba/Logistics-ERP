"""Freight Exchange load detail + evaluation + fleet match view."""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import (
    Btn,
    Card,
    CardHeader,
    CompactKPICard,
    Divider,
    FieldLabel,
    Label,
    MonoLabel,
    PageTitle,
    StatusBadge,
)
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_BASE,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_ERROR_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_INFO_SUBTLE,
    COLOR_INFO_TEXT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_SUCCESS_SUBTLE,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    COLOR_WARNING_SUBTLE,
    COLOR_WARNING_TEXT,
    FONT_SIZE_BASE,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_XS,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD,
    RADIUS_MD,
    RADIUS_PILL,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
)

logger = logging.getLogger(__name__)

# Reason styling map: (background, text_color)
_REASON_STYLE_MAP = {
    "closest_vehicle": (COLOR_INFO_SUBTLE, COLOR_INFO_TEXT),
    "highest_profit": (COLOR_SUCCESS_SUBTLE, COLOR_SUCCESS_TEXT),
    "maintenance_health": (COLOR_SUCCESS_SUBTLE, COLOR_SUCCESS_TEXT),
    "trailer_compatible": (COLOR_SUCCESS_SUBTLE, COLOR_SUCCESS_TEXT),
}


class FreightLoadDetailView(QWidget):
    """Shows load evaluation and fleet match results."""

    def __init__(self, db, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("freight_load_detail")
        self._match_rows: list[QFrame] = []
        self._build_ui()

    # ── Event filter: Enter on focused match row triggers assign ──────────
    def eventFilter(self, obj: QWidget, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and obj in self._match_rows:
            key = event.key()
            if key in (Qt.Key_Return, Qt.Key_Enter):
                assign_btn = obj.findChild(QPushButton, "assign_btn")
                if assign_btn:
                    assign_btn.click()
                return True
        return super().eventFilter(obj, event)

    # ── UI Construction ──────────────────────────────────────────────────
    def _build_ui(self):
        # Root layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_5, SPACE_5, SPACE_5, SPACE_5)
        layout.setSpacing(SPACE_5)

        # ── Header row ──────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(SPACE_3)

        self._back_top_btn = Btn(
            self,
            text=t("freight.back_to_search"),
            variant="ghost",
            icon_name="mdi6.arrow-left",
            size="sm",
        )
        header_row.addWidget(self._back_top_btn)

        self._dynamic_title = PageTitle(self, "")
        header_row.addWidget(self._dynamic_title, 1)  # stretch

        self._import_top_btn = Btn(
            self,
            text=t("freight.import"),
            variant="primary",
            icon_name="mdi6.truck-delivery",
            size="md",
        )
        header_row.addWidget(self._import_top_btn)

        self._refresh_btn = Btn(
            self,
            text=t("freight.refresh"),
            variant="secondary",
            icon_name="mdi6.refresh",
            size="sm",
        )
        header_row.addWidget(self._refresh_btn)

        layout.addLayout(header_row)

        # Below header: Divider + SPACE_4
        layout.addWidget(Divider(self))
        layout.addSpacing(SPACE_4)

        # ── Evaluation section ──────────────────────────────────────────
        self._eval_card = Card(self)
        CardHeader(
            self._eval_card.layout(),
            title=t("freight.evaluate"),
            subtitle=t("freight.eval.subtitle"),
        )

        # KPI row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(SPACE_4)

        self._kpi_revenue = CompactKPICard(
            self._eval_card,
            label=t("freight.eval.revenue"),
            icon_name="mdi6.currency-eur",
            value_color=COLOR_TEXT_PRIMARY,
        )
        kpi_row.addWidget(self._kpi_revenue)

        self._kpi_total_cost = CompactKPICard(
            self._eval_card,
            label=t("freight.eval.total_cost"),
            icon_name="mdi6.gas-station",
            value_color=COLOR_TEXT_SECONDARY,
        )
        kpi_row.addWidget(self._kpi_total_cost)

        self._kpi_profit = CompactKPICard(
            self._eval_card,
            label=t("freight.eval.expected_profit"),
            icon_name="mdi6.trending-up",
            value_color=COLOR_TEXT_PRIMARY,
        )
        kpi_row.addWidget(self._kpi_profit)

        self._kpi_margin = CompactKPICard(
            self._eval_card,
            label=t("freight.eval.profit_margin"),
            icon_name="mdi6.percent",
            value_color=COLOR_TEXT_PRIMARY,
        )
        kpi_row.addWidget(self._kpi_margin)

        self._kpi_risk = CompactKPICard(
            self._eval_card,
            label=t("freight.eval.risk_score"),
            icon_name="mdi6.shield-alert",
            value_color=COLOR_TEXT_PRIMARY,
        )
        kpi_row.addWidget(self._kpi_risk)

        self._eval_card.layout().addLayout(kpi_row)
        self._eval_card.layout().addSpacing(SPACE_4)

        # Compatibility section (inside card)
        self._compat_field = FieldLabel(
            self._eval_card, t("freight.eval.compatibility")
        )
        self._eval_card.layout().addWidget(self._compat_field)
        self._eval_card.layout().addSpacing(SPACE_2)

        self._compat_chip_layout = QHBoxLayout()
        self._compat_chip_layout.setSpacing(SPACE_2)
        self._eval_card.layout().addLayout(self._compat_chip_layout)

        layout.addWidget(self._eval_card)

        # ── Fleet Match section ─────────────────────────────────────────
        self._match_card = Card(self)
        CardHeader(
            self._match_card.layout(),
            title=t("freight.match"),
            subtitle=t("freight.match.subtitle"),
        )

        self._matches_layout = QVBoxLayout()
        self._matches_layout.setSpacing(SPACE_3)
        self._match_card.layout().addLayout(self._matches_layout)

        layout.addWidget(self._match_card)

        # ── Bottom action bar ───────────────────────────────────────────
        layout.addSpacing(SPACE_6)

        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(SPACE_3)

        self._back_bottom_btn = Btn(
            self,
            text=t("freight.back_to_search"),
            variant="ghost",
            icon_name="mdi6.arrow-left",
            size="md",
        )
        bottom_bar.addWidget(self._back_bottom_btn)

        bottom_bar.addStretch()

        self._import_bottom_btn = Btn(
            self,
            text=t("freight.import"),
            variant="primary",
            icon_name="mdi6.truck-delivery",
            size="md",
        )
        bottom_bar.addWidget(self._import_bottom_btn)

        self._evaluate_again_btn = Btn(
            self,
            text=t("freight.evaluate_again"),
            variant="secondary",
            icon_name="mdi6.refresh",
            size="md",
        )
        bottom_bar.addWidget(self._evaluate_again_btn)

        layout.addLayout(bottom_bar)

        # Initial tab order: top Back → Import → Refresh
        self.setTabOrder(self._back_top_btn, self._import_top_btn)
        self.setTabOrder(self._import_top_btn, self._refresh_btn)
        self._last_tab_widget = None

    # ── Match row builder ────────────────────────────────────────────────
    def _build_match_row(self, rank: int, match: dict) -> QFrame:
        """Build a single ranked match row as a focusable, hoverable card."""
        vehicle_id = match.get("vehicle_id", "?")
        score = match.get("score", 0)
        reasons: list = match.get("reasons", []) or []
        expected_profit = match.get("expected_profit", {})
        profit_amount = (
            expected_profit.get("amount", 0)
            if isinstance(expected_profit, dict)
            else expected_profit
        )
        driver_hours = match.get("driver_hours_remaining", 0)
        maintenance_status = match.get("maintenance_status", "")
        trailer_compatible = match.get("trailer_compatible", False)

        # Score color mapping
        if score >= 85:
            score_color = COLOR_SUCCESS_DEFAULT
        elif score >= 50:
            score_color = COLOR_WARNING_DEFAULT
        else:
            score_color = COLOR_ERROR_DEFAULT

        # ── Frame ─────────────────────────────────────────────────────
        row = QFrame(self._match_card)
        row.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_BG_OVERLAY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_MD}px;
            }}
            QFrame:hover {{
                background: {COLOR_BG_HOVER};
            }}
            QFrame:focus {{
                border: 1px solid {COLOR_ACCENT_PRIMARY};
            }}
        """)
        row.setCursor(Qt.PointingHandCursor)
        row.setFocusPolicy(Qt.StrongFocus)
        row.setFrameShape(QFrame.Shape.NoFrame)
        row.installEventFilter(self)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(SPACE_3, SPACE_3, SPACE_3, SPACE_3)
        row_layout.setSpacing(SPACE_4)

        # 1. Rank
        rank_label = MonoLabel(row, f"{rank:02d}", size="body")
        rank_label.setFixedWidth(32)
        rank_label.setStyleSheet(
            f"font-size: {FONT_SIZE_LG}px; font-weight: {FONT_WEIGHT_BOLD}; "
            f"color: {COLOR_TEXT_TERTIARY}; background: transparent; border: none;"
        )
        row_layout.addWidget(rank_label)

        # 2. Truck info
        truck_col = QVBoxLayout()
        truck_col.setSpacing(SPACE_1)

        truck_text = t("freight.match.truck_id", id=vehicle_id)
        truck_id_label = QLabel(truck_text, row)
        truck_id_label.setStyleSheet(
            f"font-size: {FONT_SIZE_BASE}px; font-weight: {FONT_WEIGHT_SEMIBOLD}; "
            f"color: {COLOR_TEXT_PRIMARY}; background: transparent; border: none;"
        )
        truck_col.addWidget(truck_id_label)

        trailer_type = match.get("trailer_type", "")
        sub_parts = [p for p in (trailer_type, maintenance_status) if p]
        sub_text = " · ".join(sub_parts)
        sub_label = QLabel(sub_text, row)
        sub_label.setStyleSheet(
            f"font-size: {FONT_SIZE_XS}px; color: {COLOR_TEXT_TERTIARY}; "
            f"background: transparent; border: none;"
        )
        truck_col.addWidget(sub_label)

        row_layout.addLayout(truck_col)

        # 3. Score bar
        score_col = QVBoxLayout()
        score_col.setSpacing(SPACE_1)
        score_col.setAlignment(Qt.AlignCenter)

        # Track
        track = QFrame(row)
        track.setFixedWidth(80)
        track.setFixedHeight(6)
        track.setStyleSheet(
            f"background: {COLOR_BG_BASE}; border-radius: {RADIUS_PILL}px; "
            f"border: none;"
        )
        track_layout = QHBoxLayout(track)
        track_layout.setContentsMargins(0, 0, 0, 0)
        track_layout.setSpacing(0)
        track_layout.setAlignment(Qt.AlignLeft)

        fill_width = max(1, int(80 * score / 100))
        fill = QFrame(track)
        fill.setFixedHeight(6)
        fill.setFixedWidth(fill_width)
        fill.setStyleSheet(
            f"background: {score_color}; border-radius: {RADIUS_PILL}px; "
            f"border: none;"
        )
        track_layout.addWidget(fill)
        track_layout.addStretch()
        score_col.addWidget(track)

        score_value = MonoLabel(row, f"{score:.0f}", size="body")
        score_value.setStyleSheet(
            f"font-size: {FONT_SIZE_MD}px; font-weight: {FONT_WEIGHT_BOLD}; "
            f"color: {score_color}; background: transparent; border: none;"
        )
        score_value.setAlignment(Qt.AlignCenter)
        score_col.addWidget(score_value)

        row_layout.addLayout(score_col)

        # 4. Reason badges (top 3)
        reason_layout = QHBoxLayout()
        reason_layout.setSpacing(2)
        reason_layout.setAlignment(Qt.AlignLeft)

        for i, reason in enumerate(reasons[:3]):
            # Normalize reason to string key
            if isinstance(reason, dict):
                reason_key = reason.get("reason", "")
            else:
                reason_key = str(reason)

            # Resolve colors from style map; default to info
            bg, fg = _REASON_STYLE_MAP.get(
                reason_key, (COLOR_INFO_SUBTLE, COLOR_INFO_TEXT)
            )

            # driver_hours special case
            if reason_key == "driver_hours":
                # Low hours if 4 or fewer remaining
                if driver_hours <= 4:
                    bg, fg = COLOR_WARNING_SUBTLE, COLOR_WARNING_TEXT
                else:
                    bg, fg = COLOR_INFO_SUBTLE, COLOR_INFO_TEXT

            badge = QLabel(reason_key, row)
            badge.setFixedHeight(18)
            badge.setStyleSheet(
                f"background: {bg}; color: {fg}; "
                f"border-radius: {RADIUS_PILL}px; border: none; "
                f"padding: 1px 6px; font-size: {FONT_SIZE_XS}px; "
                f"font-weight: {FONT_WEIGHT_SEMIBOLD};"
            )
            badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            reason_layout.addWidget(badge)

        if len(reasons) > 3:
            more_count = len(reasons) - 3
            more_label = QLabel(f"+{more_count}", row)
            more_label.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_XS}px; "
                f"background: transparent; border: none;"
            )
            reason_layout.addWidget(more_label)

        row_layout.addLayout(reason_layout)

        # 5. Profit preview
        if profit_amount >= 0:
            profit_text = f"+€{profit_amount:,.0f}"
            profit_color = COLOR_SUCCESS_TEXT
        else:
            profit_text = f"-€{abs(profit_amount):,.0f}"
            profit_color = COLOR_ERROR_TEXT
        profit_label = MonoLabel(row, profit_text, size="body")
        profit_label.setStyleSheet(
            f"font-size: {FONT_SIZE_BASE}px; font-weight: {FONT_WEIGHT_MEDIUM}; "
            f"color: {profit_color}; background: transparent; border: none;"
        )
        row_layout.addWidget(profit_label)

        # 6. Assign button
        assign_btn = Btn(
            row,
            text=t("freight.assign"),
            variant="primary",
            size="sm",
        )
        assign_btn.setObjectName("assign_btn")
        row_layout.addWidget(assign_btn)

        return row

    # ── Public methods ───────────────────────────────────────────────────
    def display_evaluation(self, evaluation: dict) -> None:
        """Populate the evaluation section from API response dict.

        Expected keys: estimated_revenue, fuel_cost, toll_cost,
        expected_profit, profit_margin_pct, risk_score,
        vehicle_compatibility, driver_compatibility.
        """
        rev = evaluation.get("estimated_revenue", {})
        fuel = evaluation.get("fuel_cost", {})
        toll = evaluation.get("toll_cost", {})
        profit = evaluation.get("expected_profit", {})
        margin = evaluation.get("profit_margin_pct", 0)
        risk = evaluation.get("risk_score", 0)

        currency = rev.get("currency", "EUR")

        # Revenue (static color)
        rev_amount = rev.get("amount", 0)
        self._kpi_revenue.value_label.setText(f"{rev_amount:,.0f} {currency}")

        # Total Cost (static color)
        fuel_amount = fuel.get("amount", 0) if isinstance(fuel, dict) else fuel
        toll_amount = toll.get("amount", 0) if isinstance(toll, dict) else toll
        total_cost = fuel_amount + toll_amount
        self._kpi_total_cost.value_label.setText(f"{total_cost:,.0f} {currency}")

        # Profit — dynamically recolored
        profit_amount = (
            profit.get("amount", 0)
            if isinstance(profit, dict)
            else profit
        )
        profit_color = (
            COLOR_SUCCESS_TEXT if profit_amount >= 0 else COLOR_ERROR_TEXT
        )
        self._kpi_profit.value_label.setText(f"{profit_amount:,.0f} {currency}")
        self._kpi_profit.value_label.setStyleSheet(f"color: {profit_color};")

        # Margin — dynamically recolored
        self._kpi_margin.value_label.setText(f"{margin:.1f}%")
        if margin >= 15:
            margin_color = COLOR_SUCCESS_TEXT
        elif margin >= 5:
            margin_color = COLOR_WARNING_TEXT
        else:
            margin_color = COLOR_ERROR_TEXT
        self._kpi_margin.value_label.setStyleSheet(f"color: {margin_color};")

        # Risk — dynamically recolored
        self._kpi_risk.value_label.setText(f"{risk:.2f}")
        if risk > 0.6:
            risk_color = COLOR_ERROR_TEXT
        elif risk > 0.3:
            risk_color = COLOR_WARNING_TEXT
        else:
            risk_color = COLOR_SUCCESS_TEXT
        self._kpi_risk.value_label.setStyleSheet(f"color: {risk_color};")

        # Compatibility chips
        self._rebuild_compatibility_chips(
            evaluation.get("vehicle_compatibility", []),
            evaluation.get("driver_compatibility", []),
        )

    def display_matches(self, matches: list[dict]) -> None:
        """Build ranked match rows from API response list.

        Each dict may contain: vehicle_id, score, reasons,
        expected_profit, driver_hours_remaining, maintenance_status,
        trailer_compatible, distance_to_pickup_km.
        """
        # Clear existing rows
        for row in self._match_rows:
            row.removeEventFilter(self)
            self._matches_layout.removeWidget(row)
            row.deleteLater()
        self._match_rows.clear()

        # Preserve tab chain from prior state, don't reset unconditionally
        if self._last_tab_widget is None:
            self._last_tab_widget = self._refresh_btn

        # Build each match row
        for rank, m in enumerate(matches, start=1):
            row = self._build_match_row(rank, m)
            self._matches_layout.addWidget(row)
            self._match_rows.append(row)

            # Chain tab order
            self.setTabOrder(self._last_tab_widget, row)
            self._last_tab_widget = row

        # Chain to bottom buttons
        self.setTabOrder(self._last_tab_widget, self._import_bottom_btn)
        self.setTabOrder(self._import_bottom_btn, self._back_bottom_btn)

    def display_freight_info(self, freight_data: dict):
        """Display Trans.eu-specific freight details.

        Shows reference_number, status, and contact employees extracted
        from the raw_payload of a LoadSearchResult or FreightOffer.

        Args:
            freight_data: dict with keys: reference_number, status,
                         publication_status, contact_employees, etc.
        """
        ref_number = freight_data.get("reference_number",
                    freight_data.get("trans_eu_reference_number", ""))
        status = freight_data.get("status", "")
        pub_status = freight_data.get("publication_status", "")
        pub_type = freight_data.get("publication_type", "")
        external_id = freight_data.get("shipment_external_id", "")

        # Build info text
        lines = []
        if ref_number:
            lines.append(f"Reference: {ref_number}")
        if status:
            lines.append(f"Status: {status}")
        if pub_status:
            lines.append(f"Publication: {pub_status}")
        if pub_type:
            lines.append(f"Published to: {pub_type}")
        if external_id:
            lines.append(f"External ID: {external_id}")

        # Contact employees (from raw_payload)
        employees = freight_data.get("contact_employees", [])
        if not employees and "raw_payload" in freight_data:
            raw = freight_data["raw_payload"]
            if isinstance(raw, dict):
                employees = raw.get("contact_employees", [])

        if employees and isinstance(employees, list):
            names = []
            for emp in employees:
                if isinstance(emp, dict):
                    name = emp.get("name", emp.get("given_name", ""))
                    surname = emp.get("last_name", emp.get("family_name", ""))
                    full = f"{name} {surname}".strip()
                    if full:
                        names.append(full)
            if names:
                lines.append(f"Contact: {', '.join(names)}")

        # Update or create an info area if there are lines
        if lines and hasattr(self, "_freight_info_label"):
            self._freight_info_label.setText("\n".join(lines))
            self._freight_info_label.setVisible(True)
        else:
            logger.debug("No freight info to display or _freight_info_label not set up")

    def set_load_for_import(self, provider_id: str, load_id: str):
        """Store the current load reference for import action.

        Args:
            provider_id: e.g., "trans_eu"
            load_id: provider-specific load identifier
        """
        self._current_import = {
            "provider_id": provider_id,
            "load_id": load_id,
        }

    def get_import_target(self) -> dict | None:
        """Get the stored import target. Returns None if not set."""
        return getattr(self, "_current_import", None)

    # ── Internal helpers ─────────────────────────────────────────────────
    def _rebuild_compatibility_chips(
        self,
        vehicle_compat: list[dict],
        driver_compat: list[dict],
    ) -> None:
        """Clear and rebuild vehicle/driver compatibility chips."""
        while self._compat_chip_layout.count():
            item = self._compat_chip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for vc in vehicle_compat:
            v_id = vc.get("vehicle_id", "?")
            v_compat = vc.get("compatible", False)
            chip = StatusBadge(
                self._eval_card,
                status_key="delivered" if v_compat else "cancelled",
                text=f"VH-{v_id}",
            )
            self._compat_chip_layout.addWidget(chip)

        for dc in driver_compat:
            d_id = dc.get("driver_id", "?")
            d_compat = dc.get("compatible", False)
            d_hours = dc.get("hours_remaining", 0)

            if d_compat:
                chip_text = f"DRV-{d_id} ({d_hours:.0f}h)"
                if d_hours > 4:
                    chip = StatusBadge(
                        self._eval_card, status_key="delivered", text=chip_text
                    )
                else:
                    chip = StatusBadge(
                        self._eval_card, status_key="in_progress", text=chip_text
                    )
            else:
                chip_text = f"DRV-{d_id}"
                chip = StatusBadge(
                    self._eval_card, status_key="overdue", text=chip_text
                )
            self._compat_chip_layout.addWidget(chip)
