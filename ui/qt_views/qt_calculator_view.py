"""PySide6 profit calculator view.

Replaces the calculator form embedded in ``ui/main_window.py``. Supports full
save flow, conflict checking, client auto-creation, VAT handling, and live sync
from ``TripContextService``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
)

from services.i18n import t
from services.calculator import TripCalculator
from services.trip_context import (
    TripContextService,
    register_trip_listener,
    unregister_trip_listener,
)
from services.conflict_service import TripConflictService
from ui.qt_widgets import (
    StyledLineEdit,
    StyledComboBox,
    StyledCheckBox,
    ActionButton,
    SectionHeader,
    ScrollableFormContainer,
    field,
)
from ui.qt_widgets.qt_toast import Toast

logger = logging.getLogger(__name__)


class QtCalculatorView(ScrollableFormContainer):
    """Profit calculator with full save/conflict-check flow."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        fleet_service=None,
        trip_service=None,
        client_service=None,
        prefs=None,
        ops=None,
        fuel_service=None,
        api=None,
    ):
        super().__init__(parent, max_width=800)
        self.db = db
        self.fleet_service = fleet_service
        self.trip_service = trip_service
        self.client_service = client_service
        self.prefs = prefs
        self.ops = ops
        self.fuel_service = fuel_service
        self.api = api

        self.calculator = TripCalculator()
        self.conflict_service = TripConflictService(self.db) if self.db else None

        self._trucks: list = []
        self._truck_map: Dict[str, Dict[str, Any]] = {}
        self._selected_truck: Optional[Dict[str, Any]] = None
        self._selected_truck_fuel: float = 34.0
        self._route_distance: float = 0.0
        self._route_toll: float = 0.0
        self._route_fuel_liters: float = 0.0
        self._current_route_history_id: Optional[int] = None

        self._build_ui()
        self._load_trucks()
        self._sync_from_trip_context()

        self._trip_listener = self._on_trip_context_changed
        register_trip_listener(self._trip_listener)

    # ── UI build ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_identification_section()
        self._build_finance_section()
        self._build_costs_section()
        self._build_planning_section()
        self._build_actions_section()
        self._build_result_section()

    def _build_identification_section(self):
        self.add_widget(SectionHeader(self.content, t("main.section_identify")))

        # Truck dropdown
        self.truck_combo = StyledComboBox(self.content)
        self.truck_combo.currentIndexChanged.connect(self._on_truck_selected)
        self.add_widget(field(self.content, t("main.truck_label"), self.truck_combo))

        # Route badge (distance loaded from route planner)
        self.route_badge = QLabel("")
        self.route_badge.setProperty("fontRole", "muted")
        self.add_widget(self.route_badge)

        # Client
        self.e_client = StyledLineEdit(self.content, placeholder=t("main.client_label"))
        self.add_widget(field(self.content, t("main.client_label"), self.e_client))

    def _build_finance_section(self):
        self.add_widget(SectionHeader(self.content, t("main.section_finance")))

        self.e_price = StyledLineEdit(self.content, placeholder=t("main.offer_price"))
        self.add_widget(field(self.content, t("main.offer_price"), self.e_price))

        # VAT row
        vat_row = QWidget(self.content)
        vat_layout = QHBoxLayout(vat_row)
        vat_layout.setContentsMargins(0, 0, 0, 0)
        vat_layout.setSpacing(8)

        self._vat_check = StyledCheckBox(vat_row, text=t("main.vat_checkbox"))
        self._vat_check.stateChanged.connect(self._on_vat_toggled)
        vat_layout.addWidget(self._vat_check)

        self._vat_percent = StyledLineEdit(vat_row, text="19", placeholder="VAT %")
        self._vat_percent.setFixedWidth(70)
        self._vat_percent.setEnabled(False)
        vat_layout.addWidget(self._vat_percent)
        vat_layout.addStretch(1)
        self.add_widget(vat_row)

        # Pre/post VAT fields
        self._vat_fields_frame = QFrame(self.content)
        vat_ff_layout = QVBoxLayout(self._vat_fields_frame)
        vat_ff_layout.setContentsMargins(0, 0, 0, 0)
        vat_ff_layout.setSpacing(8)

        self._e_price_pre = StyledLineEdit(self._vat_fields_frame, placeholder=t("main.offer_price_pre_vat"))
        vat_ff_layout.addWidget(field(self._vat_fields_frame, t("main.offer_price_pre_vat"), self._e_price_pre))

        self._e_price_post = StyledLineEdit(self._vat_fields_frame, placeholder=t("main.offer_price_post_vat"))
        self._e_price_post.setReadOnly(True)
        vat_ff_layout.addWidget(field(self._vat_fields_frame, t("main.offer_price_post_vat"), self._e_price_post))

        self.add_widget(self._vat_fields_frame)
        self._vat_fields_frame.hide()

    def _build_costs_section(self):
        self.add_widget(SectionHeader(self.content, t("main.section_costs")))

        self.e_sal = StyledLineEdit(self.content, text="0", placeholder=t("main.salary_label"))
        self.add_widget(field(self.content, t("main.salary_label"), self.e_sal))

        self.e_extra = StyledLineEdit(self.content, text="0", placeholder=t("main.extra_costs_label"))
        self.add_widget(field(self.content, t("main.extra_costs_label"), self.e_extra))

    def _build_planning_section(self):
        self.add_widget(SectionHeader(self.content, t("main.section_planning")))

        self.e_start = StyledLineEdit(
            self.content,
            text=datetime.now().strftime("%d/%m/%Y"),
            placeholder=t("main.start_date_label"),
        )
        self.add_widget(field(self.content, t("main.start_date_label"), self.e_start))

        self.e_days = StyledLineEdit(self.content, text="1", placeholder=t("main.duration_label"))
        self.add_widget(field(self.content, t("main.duration_label"), self.e_days))

        self.e_term = StyledLineEdit(self.content, text="30", placeholder=t("main.payment_term_label"))
        self.add_widget(field(self.content, t("main.payment_term_label"), self.e_term))

    def _build_actions_section(self):
        self.calculate_btn = ActionButton(
            self.content,
            t("main.calculate_button"),
            command=self._handle_calculate,
            color=self._color("success"),
        )
        self.add_widget(self.calculate_btn)

    def _build_result_section(self):
        self.result_frame = QFrame(self.content)
        self.result_frame.setProperty("role", "card")
        result_layout = QVBoxLayout(self.result_frame)
        result_layout.setContentsMargins(16, 16, 16, 16)

        self.l_res = QLabel(t("main.placeholder_info"))
        self.l_res.setProperty("fontRole", "muted")
        self.l_res.setAlignment(Qt.AlignCenter)
        self.l_res.setWordWrap(True)
        result_layout.addWidget(self.l_res)

        self.add_widget(self.result_frame)

        self._fuel_status_lbl = QLabel("")
        self._fuel_status_lbl.setProperty("fontRole", "muted")
        self.add_widget(self._fuel_status_lbl)

        # Return key triggers calculation on most inputs
        for widget in (self.e_price, self.e_sal, self.e_extra, self.e_days, self.e_term):
            widget.returnPressed.connect(self._handle_calculate)

    # ── Truck loading / selection ──────────────────────────────────────────────

    def _load_trucks(self):
        if self.fleet_service is None:
            return
        try:
            self._trucks = self.fleet_service.get_trucks()
        except Exception:
            self._trucks = []

        self._truck_map = {}
        self.truck_combo.clear()
        if not self._trucks:
            self.truck_combo.addItem(t("app.loading"))
            return

        for r in self._trucks:
            tid = str(r.get("id"))
            label = f"{r.get('plate_number', '')} - {r.get('model', '')}"
            self.truck_combo.addItem(label, tid)
            try:
                row_dict = {k: r[k] for k in r.keys()}
            except Exception:
                row_dict = {
                    "id": r.get("id"),
                    "plate_number": r.get("plate_number"),
                    "model": r.get("model"),
                    "fuel_consumption": r.get("fuel_consumption"),
                    "fuel_consumption_l_per_100km": r.get("fuel_consumption_l_per_100km"),
                }
            self._truck_map[tid] = row_dict

        # Select first truck by default
        self._on_truck_selected(0)

    def _on_truck_selected(self, index: int):
        tid = self.truck_combo.itemData(index)
        if tid is None:
            return
        truck = self._truck_map.get(str(tid))
        self._selected_truck = truck
        if truck is None:
            self._selected_truck_fuel = 34.0
            return
        try:
            self._selected_truck_fuel = float(
                truck.get("fuel_consumption") or truck.get("fuel_consumption_l_per_100km") or 34.0
            )
        except Exception:
            self._selected_truck_fuel = 34.0

    # ── VAT handling ───────────────────────────────────────────────────────────

    def _on_vat_toggled(self, state: int):
        enabled = Qt.CheckState(state) == Qt.Checked
        self._vat_percent.setEnabled(enabled)
        if enabled:
            self._vat_fields_frame.show()
            self._update_vat_fields()
        else:
            self._vat_fields_frame.hide()

    def _update_vat_fields(self):
        try:
            price = float(self.e_price.text() or 0)
            vat_pct = float(self._vat_percent.text() or 0)
            self._e_price_pre.setText(f"{price:.2f}")
            post = round(price * (1 + vat_pct / 100), 2)
            self._e_price_post.setText(f"{post:.2f}")
        except ValueError:
            pass

    # ── Calculation & save ─────────────────────────────────────────────────────

    def _handle_calculate(self):
        try:
            km = float(self._route_distance or 0)
            price_raw = float(self.e_price.text() or 0)
            if km <= 0 or price_raw <= 0:
                QMessageBox.warning(self, t("main.warning_title"), t("main.fields_required"))
                return

            vat_enabled = self._vat_check.isChecked()
            vat_pct = 0.0
            price_pre_vat = price_raw
            if vat_enabled:
                try:
                    vat_pct = float(self._vat_percent.text() or 0)
                    price_pre_vat = float(self._e_price_pre.text() or price_raw)
                    price = float(self._e_price_post.text() or price_raw)
                except ValueError:
                    price = price_raw
                    vat_pct = 0
            else:
                price = price_raw

            rates = self.api.get_rates() if self.api else {"EUR": 1.0}
            currency = self.prefs.get_currency() if self.prefs else "EUR"
            rate_eur = rates.get(currency, 1.0)
            pret_eur = price / rate_eur
            pret_eur_pre_vat = price_pre_vat / rate_eur if vat_enabled else pret_eur

            cons = self._selected_truck_fuel

            fuel_price = self.fuel_service.get_price("DEFAULT", currency) if self.fuel_service else 1.55

            fuel_cost_from_route = None
            if self._route_fuel_liters > 0:
                fuel_cost_from_route = self._route_fuel_liters * fuel_price

            res = self.calculator.calculate(
                km, pret_eur, fuel_price,
                int(self.e_days.text() or 1), cons,
                float(self.e_extra.text() or 0), float(self.e_sal.text() or 0), float(self._route_toll or 0),
                fuel_cost_from_route,
            )

            try:
                dt_s = datetime.strptime(self.e_start.text(), "%d/%m/%Y")
            except Exception:
                dt_s = datetime.now()
            dt_end = dt_s + timedelta(days=int(self.e_days.text() or 1))
            dt_inc = dt_end + timedelta(days=int(self.e_term.text() or 0))

            self._display_result(res, dt_inc)

            truck_plate = self._selected_truck.get("plate_number") if self._selected_truck else None
            driver_id = self._selected_truck.get("driver_id") if self._selected_truck else None
            driver_name = self._selected_truck.get("driver_name") if self._selected_truck else None

            conflicts = []
            if self.conflict_service:
                conflicts = self.conflict_service.check_conflicts({
                    "truck_plate": truck_plate or "",
                    "driver_id": driver_id,
                    "start_date": dt_s.strftime("%Y-%m-%d"),
                    "end_date": dt_end.strftime("%Y-%m-%d"),
                    "distance_km": km,
                })

            if conflicts and self.conflict_service:
                conflict_msgs = [self.conflict_service.describe_conflict(c) for c in conflicts]
                msg = t("dispatch_board.conflict_warning_title") + "\n\n" + "\n".join(conflict_msgs)
                if QMessageBox.question(self, t("dispatch_board.conflict_warning_title"), msg) != QMessageBox.Yes:
                    return

            client_name = self.e_client.text().strip()
            client_id = None
            if client_name and self.client_service:
                client_id = self.client_service.get_or_create(client_name)

            trip_data = {
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "truck_number": truck_plate,
                "driver_name": driver_name,
                "driver_id": driver_id,
                "client_name": client_name,
                "client_id": client_id,
                "distance_km": km,
                "total_price_eur": round(pret_eur, 2),
                "rate_per_km": res.rate_per_km,
                "gross_per_km": res.gross_per_km,
                "net_profit": res.net_profit,
                "start_date": dt_s.strftime("%Y-%m-%d"),
                "end_date": dt_end.strftime("%Y-%m-%d"),
                "payment_date": dt_inc.strftime("%Y-%m-%d"),
                "currency": currency,
                "status": "Planned",
                "fuel_cost": res.fuel_cost,
                "toll_cost": res.toll_cost,
                "salary_cost": res.salary_cost,
                "extra_costs": res.extra_costs,
                "route_history_v2_id": self._current_route_history_id,
                "truck_consumption_l_per_100km": self._selected_truck_fuel,
            }
            if vat_enabled:
                trip_data["price_pre_vat"] = round(pret_eur_pre_vat, 2)
                trip_data["vat_percent"] = round(vat_pct, 2)

            if self.trip_service:
                self.trip_service.add(trip_data)
            Toast.show_success(self, f"✅ {t('main.save_success')}")

        except Exception as e:
            logger.exception("Calculator save failed")
            QMessageBox.critical(
                self, t("main.error_title"), f"{t('main.check_data').format(str(e))}"
            )

    def _display_result(self, res, dt_inc: datetime):
        if res.net_profit > 400:
            color_name = "text_success"
        elif res.net_profit > 0:
            color_name = "text_primary"
        else:
            color_name = "text_danger"
        color = self._color(color_name)
        summary = (
            f"💰 {t('main.net_profit').format(res.net_profit)}\n"
            f"📈 {t('main.gross_rate').format(res.gross_per_km, res.rate_per_km)}\n"
            f"📊 {t('main.margin').format(res.margin_percent, dt_inc.strftime('%d/%m/%Y'))}\n"
            f"{t('main.separator')}\n"
            f"⛽ {t('main.cost_breakdown').format(res.fuel_cost, res.toll_cost, res.salary_cost)}"
        )
        self.l_res.setText(summary)
        self.l_res.setProperty("fontRole", "")
        self.l_res.setStyleSheet(f"color: {color};")

    def _color(self, name: str) -> str:
        from ui.theme import COLORS
        return COLORS.get(name, "#ffffff")

    # ── TripContext sync ───────────────────────────────────────────────────────

    def _sync_from_trip_context(self):
        try:
            tc = TripContextService()._tc
            if tc and tc.route and tc.route.distance_km is not None:
                self._apply_trip_context(tc, ["route"])
        except Exception:
            pass

    def _on_trip_context_changed(self, tc, changed_fields):
        # Listener may be invoked from a background thread; schedule UI update on main thread.
        QTimer.singleShot(0, lambda: self._apply_trip_context(tc, changed_fields))

    def _apply_trip_context(self, tc, changed_fields):
        try:
            if tc.route and tc.route.distance_km is not None:
                self._route_distance = float(tc.route.distance_km)
                self.route_badge.setText(
                    f"\U0001f5fa\ufe0f {t('route.loaded_route', default='Route loaded')}:"
                    f" {self._route_distance:,.0f} km"
                )
            if tc.route and tc.route.route_history_v2_id is not None:
                self._current_route_history_id = tc.route.route_history_v2_id
            if tc.costs:
                if tc.costs.fuel_liters is not None:
                    self._route_fuel_liters = float(tc.costs.fuel_liters)
                if tc.costs.toll_cost is not None:
                    self._route_toll = float(tc.costs.toll_cost)
            if tc.truck and tc.truck.id is not None:
                truck_id = str(tc.truck.id)
                if truck_id in self._truck_map:
                    index = self.truck_combo.findData(truck_id)
                    if index >= 0:
                        self.truck_combo.setCurrentIndex(index)
        except Exception:
            pass

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self):
        self._load_trucks()
        self._sync_from_trip_context()

    def shutdown(self):
        try:
            unregister_trip_listener(self._trip_listener)
        except Exception:
            pass
