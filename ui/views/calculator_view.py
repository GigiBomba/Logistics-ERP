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
    QScrollArea,
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
from ui.widgets import (
    StyledLineEdit,
    StyledComboBox,
    StyledCheckBox,
    field,
)
from ui.widgets.toast import Toast
from ui.design_tokens import SP, SUCCESS, DANGER
from ui.components import (
    Card, CardHeader, Btn, PageTitle, Label, MonoLabel, Divider,
)

logger = logging.getLogger(__name__)


class QtCalculatorView(QWidget):
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
        super().__init__(parent)
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
        self._load_clients()
        self._sync_from_trip_context()

        self._trip_listener = self._on_trip_context_changed
        register_trip_listener(self._trip_listener)

    # ── UI build ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SP["10"], 0, SP["10"], SP["10"])
        outer.setSpacing(SP["6"])

        # Header — 72px with 40px horizontal margins
        hdr = QWidget()
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setContentsMargins(0, SP["2"], 0, 0)
        hdr_layout.setSpacing(SP["1"])
        hdr.setFixedHeight(72)
        hdr_layout.addWidget(PageTitle(hdr, t("app.title", default="Profit Calculator")))
        hdr_layout.addWidget(Label(hdr, t("main.placeholder_info", default="Calculate trip profitability"), role="secondary"))
        outer.addWidget(hdr)

        # Horizontal split: left (55%) form cards, right (45%) results
        split = QHBoxLayout()
        split.setSpacing(SP["6"])

        # ── Left panel: scrollable form in cards ──
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        self.left_content = QWidget()
        self.left_content.setMaximumWidth(740)
        self.left_layout = QVBoxLayout(self.left_content)
        self.left_layout.setSpacing(SP["6"])
        self.left_layout.setAlignment(Qt.AlignTop)

        self._build_identification_section()
        self._build_finance_section()
        self._build_costs_section()
        self._build_planning_section()
        self._build_actions_section()

        left_scroll.setWidget(self.left_content)
        split.addWidget(left_scroll, 55)

        # ── Right panel: results ──
        self.results_card = Card(self)
        self.results_card.setMaximumWidth(500)
        self._build_result_section()
        split.addWidget(self.results_card, 45)

        outer.addLayout(split)

        # Return key triggers calculation on most inputs
        for widget in (self.e_price, self.e_sal, self.e_extra, self.e_days, self.e_term):
            widget.returnPressed.connect(self._handle_calculate)

    def _build_identification_section(self):
        card = Card(self.left_content)
        cl = card.layout()
        CardHeader(cl, t("main.section_identify"))

        # Truck dropdown
        self.truck_combo = StyledComboBox(card)
        self.truck_combo.currentIndexChanged.connect(self._on_truck_selected)
        cl.addWidget(field(card, t("main.truck_label"), self.truck_combo))

        # Route badge (distance loaded from route planner)
        self.route_badge = QLabel("")
        self.route_badge.setProperty("fontRole", "muted")
        cl.addWidget(self.route_badge)

        # Client
        self.e_client = StyledComboBox(card, values=[], state="readonly")
        cl.addWidget(field(card, t("main.client_label"), self.e_client))

        self.left_layout.addWidget(card)

    def _build_finance_section(self):
        card = Card(self.left_content)
        cl = card.layout()
        CardHeader(cl, t("main.section_finance"))

        self.e_price = StyledLineEdit(card, placeholder=t("main.offer_price"))
        cl.addWidget(field(card, t("main.offer_price"), self.e_price))

        # VAT row
        vat_row = QWidget(card)
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
        cl.addWidget(vat_row)

        # Pre/post VAT fields
        self._vat_fields_frame = QFrame(card)
        vat_ff_layout = QVBoxLayout(self._vat_fields_frame)
        vat_ff_layout.setContentsMargins(0, 0, 0, 0)
        vat_ff_layout.setSpacing(8)

        self._e_price_pre = StyledLineEdit(self._vat_fields_frame, placeholder=t("main.offer_price_pre_vat"))
        vat_ff_layout.addWidget(field(self._vat_fields_frame, t("main.offer_price_pre_vat"), self._e_price_pre))

        self._e_price_post = StyledLineEdit(self._vat_fields_frame, placeholder=t("main.offer_price_post_vat"))
        self._e_price_post.setReadOnly(True)
        vat_ff_layout.addWidget(field(self._vat_fields_frame, t("main.offer_price_post_vat"), self._e_price_post))

        cl.addWidget(self._vat_fields_frame)
        self._vat_fields_frame.hide()

        self.left_layout.addWidget(card)

    def _build_costs_section(self):
        card = Card(self.left_content)
        cl = card.layout()
        CardHeader(cl, t("main.section_costs"))

        self.e_sal = StyledLineEdit(card, text="0", placeholder=t("main.salary_label"))
        cl.addWidget(field(card, t("main.salary_label"), self.e_sal))

        self.e_extra = StyledLineEdit(card, text="0", placeholder=t("main.extra_costs_label"))
        cl.addWidget(field(card, t("main.extra_costs_label"), self.e_extra))

        self.left_layout.addWidget(card)

    def _build_planning_section(self):
        card = Card(self.left_content)
        cl = card.layout()
        CardHeader(cl, t("main.section_planning"))

        self.e_start = StyledLineEdit(
            card,
            text=datetime.now().strftime("%d/%m/%Y"),
            placeholder=t("main.start_date_label"),
        )
        cl.addWidget(field(card, t("main.start_date_label"), self.e_start))

        self.e_days = StyledLineEdit(card, text="1", placeholder=t("main.duration_label"))
        cl.addWidget(field(card, t("main.duration_label"), self.e_days))

        self.e_term = StyledLineEdit(card, text="30", placeholder=t("main.payment_term_label"))
        cl.addWidget(field(card, t("main.payment_term_label"), self.e_term))

        self.left_layout.addWidget(card)

    def _build_actions_section(self):
        self.calculate_btn = Btn(
            self.left_content,
            t("main.calculate_button"),
            variant="primary",
            command=self._handle_calculate,
        )
        self.left_layout.addWidget(self.calculate_btn)

    def _build_result_section(self):
        cl = self.results_card.layout()

        self._profit_label = MonoLabel(self.results_card, t("main.placeholder_info"), size="xl")
        self._profit_label.setAlignment(Qt.AlignCenter)
        self._profit_label.setWordWrap(True)
        cl.addWidget(self._profit_label)

        self._breakdown_container = QWidget(self.results_card)
        self._breakdown_layout = QVBoxLayout(self._breakdown_container)
        self._breakdown_layout.setContentsMargins(0, 0, 0, 0)
        self._breakdown_layout.setSpacing(SP["2"])
        cl.addWidget(self._breakdown_container)

        cl.addWidget(Divider(self.results_card))

        self._fuel_status_lbl = Label(self.results_card, "", role="muted")
        cl.addWidget(self._fuel_status_lbl)

        cl.addStretch()

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

    def _load_clients(self):
        """Populate client combo from the database."""
        if self.client_service is None:
            return
        try:
            clients = self.client_service.get_all()
        except Exception:
            clients = []
        self.e_client.clear()
        if not clients:
            self.e_client.addItem("")
            return
        for c in clients:
            name = c.get("name", "")
            if name:
                self.e_client.addItem(name, str(c.get("id")))

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

            client_name = self.e_client.currentText().strip()
            client_id = None
            if client_name:
                cid = self.e_client.currentData()
                if cid is not None:
                    client_id = int(cid)

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
        # Update profit number with SUCCESS/DANGER color
        color = SUCCESS if res.net_profit >= 0 else DANGER
        self._profit_label.setText(f"{res.net_profit:,.2f} €")
        self._profit_label.setStyleSheet(f"color: {color};")

        # Clear and rebuild breakdown rows
        while self._breakdown_layout.count():
            item = self._breakdown_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        rows = [
            (t("main.gross_rate"), f"{res.gross_per_km:.2f} / {res.rate_per_km:.2f} €/km"),
            (t("main.margin"), f"{res.margin_percent:.1f}%  |  {dt_inc.strftime('%d/%m/%Y')}"),
        ]
        for label_text, value in rows:
            row = QWidget(self._breakdown_container)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(SP["2"])
            lb = Label(row, label_text, role="secondary")
            vl = Label(row, value)
            row_layout.addWidget(lb)
            row_layout.addStretch()
            row_layout.addWidget(vl)
            self._breakdown_layout.addWidget(row)

        # Cost breakdown
        cost_label = QLabel(
            f"⛽ {res.fuel_cost:.2f} € Fuel  |  {res.toll_cost:.2f} € Toll  |  {res.salary_cost:.2f} € Salary"
        )
        cost_label.setProperty("role", "muted")
        cost_label.setWordWrap(True)
        self._breakdown_layout.addWidget(cost_label)

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
