import tkinter as tk
from typing import Optional
import customtkinter as ctk
from tkinter import ttk
from services.i18n import t, register_listener, unregister_listener
from ui.icons import iconed
from services.app_state import AppState
from ui.styles import Theme
from services.fleet_maintenance_service import FleetMaintenanceService
from services.operations.alert_manager import AlertType, Severity, Alert
from services.operations.operations_engine import OperationsEngine
from services.operations.event_bus import EventBus, ALERT_CREATED, ALERT_RESOLVED, MAINTENANCE_ADDED, MAINTENANCE_DELETED
from ui.widgets.fuel_panel import FuelPricePanel
from ui.theme import FONTS

ALERT_ICONS = {
    AlertType.MAINTENANCE: "\u2699",       # ⚙
    AlertType.INSPECTION: "\u2611",        # ☑
    AlertType.INSURANCE: "\u26E8",         # ⛨
    AlertType.OVERDUE_INVOICE: "\u20AC",   # €
    AlertType.TRIP_DELAY: "\u23F1",        # ⏱
    AlertType.INACTIVE_TRUCK: "\u25CB",    # ○
    AlertType.ROUTE_ISSUE: "\u26A0",       # ⚠
    AlertType.COMPLIANCE_WARNING: "\u2696",# ⚖
    AlertType.TACHOGRAPH_EXPIRY: "\U0001f4be",   # 💾
    AlertType.DRIVER_HOURS_WEEKLY: "\u23F1",       # ⏱
    AlertType.DRIVER_HOURS_DAILY: "\u23F1",        # ⏱
}

SEVERITY_ICONS = {
    Severity.CRITICAL: "\u26A0",           # ⚠
    Severity.WARNING: "\u26A0",            # ⚠
    Severity.INFO: "\u2139",               # ℹ
}

SEVERITY_COLORS = {
    Severity.CRITICAL: Theme.DANGER,
    Severity.WARNING: Theme.WARNING,
    Severity.INFO: Theme.INFO,
}

SEVERITY_LABELS = {
    Severity.CRITICAL: "maint.section_critical",
    Severity.WARNING: "maint.section_warnings",
    Severity.INFO: "maint.section_info",
}


class MaintenanceControlPanel:
    def __init__(self, parent, db=None, prefs=None, ops=None, embedded=False):
        if embedded:
            self.win = None
            self.frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)
        else:
            self.win = ctk.CTkToplevel(parent)
            self.win.title(iconed("maint.control_panel_title"))
            self.win.geometry("1450x950")
            self.win.configure(fg_color=Theme.BG)
            Theme.apply(self.win)
            self.frame = ctk.CTkFrame(self.win, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)

        self.parent = parent
        self.db = db
        self.ops = OperationsEngine()
        self.event_bus = EventBus()
        self._alerts: list[Alert] = []
        self._filtered_alerts: list[Alert] = []
        self._refresh_scheduled = False
        self._closed = False
        self._i18n_tags = []
        self._app_state = AppState()
        self._after_ids: list = []

        self._build_header()
        self._build_maintenance_kpis()
        self._build_tachograph_status()
        self._build_filter_bar()
        self._build_fuel_panel()
        self._build_alert_center()
        self._subscribe_events()
        self._refresh()

        if self.win:
            self.win.bind("<Destroy>", self._on_destroy)
        else:
            self.frame.bind("<Destroy>", self._on_destroy)

        register_listener(self._on_language_changed)
        self._app_state.subscribe("currency", self._on_currency_changed)

    def _on_destroy(self, event=None):
        if event is not None and event.widget != (self.win or self.frame):
            return
        self._closed = True
        for aid in self._after_ids:
            try:
                target = self.win or self.frame or self.parent
                target.after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()
        self._unsubscribe_events()
        unregister_listener(self._on_language_changed)
        self._app_state.unsubscribe("currency", self._on_currency_changed)

    def _on_language_changed(self, lang):
        if self.win:
            self.win.title(iconed("maint.control_panel_title"))
        for widget, key, prefix in self._i18n_tags:
            try:
                widget.configure(text=prefix + (iconed(key) if key.startswith("maint.") else t(key)))
            except Exception:
                pass
        old_sev = self.c_severity.get()
        old_type = self.c_type.get()
        sev_opts = self._get_severity_options()
        type_opts = self._get_type_options()
        self._sev_all = sev_opts[0]
        self._type_all = type_opts[0]
        self.c_severity.configure(values=sev_opts)
        self.c_type.configure(values=type_opts)
        self.c_severity.set(old_sev if old_sev in sev_opts else sev_opts[0])
        self.c_type.set(old_type if old_type in type_opts else type_opts[0])
        self._render_alerts()
        self._refresh_maintenance_kpis()
        self._refresh_tachograph_status()

    def _on_currency_changed(self, currency):
        self._refresh_maintenance_kpis()

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_tags.append((widget, key, prefix))
        if key.startswith("maint."):
            widget.configure(text=prefix + iconed(key))
        else:
            widget.configure(text=prefix + t(key))

    def _get_severity_options(self):
        return [t("common.all"), Severity.CRITICAL.value, Severity.WARNING.value, Severity.INFO.value]

    def _get_type_options(self):
        return [t("common.all")] + [at.value for at in AlertType]

    def _subscribe_events(self):
        self.event_bus.subscribe(ALERT_CREATED, self._schedule_refresh)
        self.event_bus.subscribe(ALERT_RESOLVED, self._schedule_refresh)
        self.event_bus.subscribe(MAINTENANCE_ADDED, self._schedule_maintenance_refresh)
        self.event_bus.subscribe(MAINTENANCE_DELETED, self._schedule_maintenance_refresh)

    def _unsubscribe_events(self):
        self.event_bus.unsubscribe(ALERT_CREATED, self._schedule_refresh)
        self.event_bus.unsubscribe(ALERT_RESOLVED, self._schedule_refresh)
        self.event_bus.unsubscribe(MAINTENANCE_ADDED, self._schedule_maintenance_refresh)
        self.event_bus.unsubscribe(MAINTENANCE_DELETED, self._schedule_maintenance_refresh)

    def _schedule_refresh(self, event=None):
        if self._refresh_scheduled or self._closed:
            return
        self._refresh_scheduled = True
        self._safe_after(300, self._do_refresh)

    def _schedule_maintenance_refresh(self, event=None):
        if self._closed:
            return
        self._safe_after(200, self._refresh_maintenance_kpis)

    def _do_refresh(self):
        self._refresh_scheduled = False
        if not self._closed:
            self._refresh()

    def _build_header(self):
        header = ctk.CTkFrame(self.frame, fg_color=Theme.SURFACE)
        header.pack(fill="x")

        self._title_lbl = ctk.CTkLabel(
            header,
            text="",
            fg_color=Theme.SURFACE,
            text_color=Theme.TEXT,
            font=FONTS["h2"],
        )
        self._title_lbl.pack(side="left")
        self._i18n_tag(self._title_lbl, "maint.control_panel_title")

        self._alert_count_lbl = ctk.CTkLabel(
            header,
            text="",
            fg_color=Theme.SURFACE,
            text_color=Theme.MUTED,
            font=FONTS["label"],
        )
        self._alert_count_lbl.pack(side="right", padx=(10, 0))

        self._refresh_btn = ctk.CTkButton(
            header,
            text="",
            command=self._refresh,
            fg_color=Theme.ACCENT,
            text_color=Theme.TEXT,
            cursor="hand2",
            font=FONTS["small"],
        )
        self._refresh_btn.pack(side="right")
        self._i18n_tag(self._refresh_btn, "maint.refresh")

    def _build_maintenance_kpis(self):
        bar = ctk.CTkFrame(self.frame, fg_color=Theme.SURFACE2)
        bar.pack(fill="x")
        self._maint_header_lbl = ctk.CTkLabel(bar, text="", fg_color=Theme.SURFACE2, text_color=Theme.ACCENT,
                                          font=FONTS["label"])
        self._maint_header_lbl.pack(side="left", padx=(0, 12))
        self._i18n_tag(self._maint_header_lbl, "maint.control_panel_title")

        self._maint_kpis = {}
        kpi_defs = [
            ("avg_health", "maint.avg_health"),
            ("trucks_needing_service", "maint.due_service"),
            ("overdue_schedules", "maint.overdue"),
            ("cost_30d", "maint.cost_30d"),
            ("total_cost", "maint.total_cost_kpi"),
        ]
        for key, title_key in kpi_defs:
            c = ctk.CTkFrame(bar, fg_color=Theme.SURFACE2)
            c.pack(side="left", padx=4)
            title_lbl = ctk.CTkLabel(c, text="", fg_color=Theme.SURFACE2, text_color=Theme.MUTED,
                                  font=FONTS["label"])
            title_lbl.pack()
            self._i18n_tag(title_lbl, title_key)
            val_lbl = ctk.CTkLabel(c, text="...", fg_color=Theme.SURFACE2, text_color=Theme.TEXT,
                                font=FONTS["small"])
            val_lbl.pack()
            self._maint_kpis[key] = (title_lbl, val_lbl, title_key)

        self._refresh_maintenance_kpis()

    def _refresh_maintenance_kpis(self):
        try:
            svc = FleetMaintenanceService(self.db)
            summary = svc.get_summary()
            for key, (_title_lbl, lbl, _title_key) in self._maint_kpis.items():
                val = summary.get(key, t("common.na"))
                if key == "avg_health":
                    color = Theme.SUCCESS if val >= 80 else (Theme.WARNING if val >= 50 else Theme.DANGER)
                    lbl.config(text=f"{val}/100", text_color=color)
                elif key == "overdue_schedules":
                    color = Theme.DANGER if val > 0 else Theme.SUCCESS
                    lbl.config(text=str(val), text_color=color)
                elif key == "cost_30d" or key == "total_cost":
                    lbl.config(text=f"{float(val):,.0f}\u20AC", text_color=Theme.INFO)
                elif key == "trucks_needing_service":
                    color = Theme.WARNING if int(val) > 0 else Theme.SUCCESS
                    lbl.config(text=str(val), text_color=color)
                else:
                    lbl.config(text=str(val), text_color=Theme.TEXT)
        except Exception as e:
            logger = __import__("logging").getLogger("dashboard")
            logger.debug("Maintenance KPIs unavailable: %s", e)
            for _title_lbl, lbl, _title_key in self._maint_kpis.values():
                lbl.config(text=t("common.na"), text_color=Theme.MUTED)

    def _build_tachograph_status(self):
        """Section showing tachograph calibration status per truck."""
        section = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        section.pack(fill="x", padx=12, pady=(8, 4))

        hdr = ctk.CTkFrame(section, fg_color=Theme.BG)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text=t("tacho.section_status_title"),
                     fg_color=Theme.BG, text_color=Theme.ACCENT,
                     font=FONTS["h3"]).pack(side="left")

        import_btn = ctk.CTkButton(
            hdr, text=t("tacho.import_now"),
            command=self._navigate_to_tachograph,
            fg_color=Theme.ACCENT, text_color=Theme.TEXT,
            cursor="hand2", font=FONTS["small"],
            width=100, height=24,
        )
        import_btn.pack(side="right")

        self._tacho_scroll = ctk.CTkScrollableFrame(
            section, fg_color=Theme.BG, height=140,
            scrollbar_button_color=Theme.BORDER,
        )
        self._tacho_scroll.pack(fill="x", pady=(4, 0))
        self._refresh_tachograph_status()

    def _refresh_tachograph_status(self):
        for w in self._tacho_scroll.winfo_children():
            w.destroy()

        try:
            from repositories.tacho_vehicle_data_repository import TachoVehicleDataRepository
            from repositories.fleet_repository import FleetRepository
            tvd_repo = TachoVehicleDataRepository(self.db)
            fleet_repo = FleetRepository(self.db)
            trucks = fleet_repo.get_active_trucks()
        except Exception:
            ctk.CTkLabel(self._tacho_scroll, text=t("tacho.no_data"),
                         fg_color=Theme.BG, text_color=Theme.MUTED,
                         font=FONTS["small"]).pack()
            return

        if not trucks:
            ctk.CTkLabel(self._tacho_scroll, text=t("tacho.no_trucks"),
                         fg_color=Theme.BG, text_color=Theme.MUTED,
                         font=FONTS["small"]).pack()
            return

        # Header row
        row = ctk.CTkFrame(self._tacho_scroll, fg_color=Theme.SURFACE2, height=22)
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)
        ctk.CTkLabel(row, text=t("fleet.table_plate"), font=FONTS["label"],
                     text_color=Theme.MUTED, width=100).pack(side="left", padx=4)
        ctk.CTkLabel(row, text=t("tacho.last_import"), font=FONTS["label"],
                     text_color=Theme.MUTED, width=100).pack(side="left", padx=4)
        ctk.CTkLabel(row, text=t("tacho.calibration_date"), font=FONTS["label"],
                     text_color=Theme.MUTED, width=100).pack(side="left", padx=4)
        ctk.CTkLabel(row, text=t("tacho.expiry"), font=FONTS["label"],
                     text_color=Theme.MUTED, width=100).pack(side="left", padx=4)
        ctk.CTkLabel(row, text=t("common.status"), font=FONTS["label"],
                     text_color=Theme.MUTED, width=80).pack(side="left", padx=4)

        for truck in trucks:
            latest = tvd_repo.get_latest_by_truck(truck["id"])
            self._build_tacho_row(truck, latest)

    def _build_tacho_row(self, truck: dict, latest: Optional[dict]):
        row = ctk.CTkFrame(self._tacho_scroll, fg_color=Theme.SURFACE, height=28)
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        plate = truck.get("plate_number", "—")
        ctk.CTkLabel(row, text=plate, font=FONTS["small"],
                     text_color=Theme.TEXT, width=100).pack(side="left", padx=4)

        if not latest or not latest.get("calibration_expiry"):
            for _ in range(3):
                ctk.CTkLabel(row, text="—", font=FONTS["small"],
                             text_color=Theme.MUTED, width=100).pack(side="left", padx=4)
            chip = ctk.CTkLabel(row, text=t("tacho.status_no_data"),
                                font=FONTS["label"], fg_color=Theme.BORDER,
                                text_color=Theme.TEXT, corner_radius=4,
                                padx=4, height=16)
            chip.pack(side="left", padx=4)
            return

        # Last import date
        import_at = "—"
        try:
            from repositories.tacho_import_repository import TachoImportRepository
            ti_repo = TachoImportRepository(self.db)
            imp = ti_repo.get_by_id(latest.get("import_id"))
            if imp and imp.get("imported_at"):
                import_at = str(imp["imported_at"])[:10]
        except Exception:
            pass
        ctk.CTkLabel(row, text=import_at, font=FONTS["small"],
                     text_color=Theme.TEXT, width=100).pack(side="left", padx=4)

        # Calibration date
        calib_date = latest.get("calibration_date") or "—"
        ctk.CTkLabel(row, text=calib_date[:10] if isinstance(calib_date, str) else str(calib_date)[:10],
                     font=FONTS["small"], text_color=Theme.TEXT, width=100).pack(side="left", padx=4)

        # Expiry
        expiry_str = latest.get("calibration_expiry") or "—"
        ctk.CTkLabel(row, text=expiry_str[:10] if isinstance(expiry_str, str) else str(expiry_str)[:10],
                     font=FONTS["small"], text_color=Theme.TEXT, width=100).pack(side="left", padx=4)

        # Status chip
        from datetime import datetime
        try:
            expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d")
            days_left = (expiry_dt - datetime.now()).days
        except Exception:
            days_left = None

        if days_left is None:
            chip_text = t("tacho.status_no_data")
            chip_color = Theme.BORDER
            chip_text_color = Theme.TEXT
        elif days_left < 0:
            chip_text = t("tacho.status_expired")
            chip_color = Theme.DANGER
            chip_text_color = Theme.TEXT
        elif days_left <= 7:
            chip_text = f"{days_left}d"
            chip_color = Theme.DANGER
            chip_text_color = Theme.TEXT
        elif days_left <= 30:
            chip_text = f"{days_left}d"
            chip_color = Theme.WARNING
            chip_text_color = Theme.TEXT
        else:
            chip_text = t("tacho.status_valid")
            chip_color = Theme.SUCCESS
            chip_text_color = Theme.TEXT

        chip = ctk.CTkLabel(row, text=chip_text,
                            font=FONTS["label"], fg_color=chip_color,
                            text_color=chip_text_color, corner_radius=4,
                            padx=4, height=16)
        chip.pack(side="left", padx=4)

    def _navigate_to_tachograph(self):
        """Try to navigate to the tachograph import view via parent hierarchy."""
        target = self.parent
        for _ in range(5):
            if target is None:
                break
            if hasattr(target, "_switch_module"):
                target._switch_module("tachograph")
                return
            target = getattr(target, "master", None) or getattr(target, "parent", None)
        # Fallback: open as standalone view
        try:
            from ui.views.tacho_import_view import TachoImportView
            TachoImportView(self.parent, self.db)
        except Exception:
            pass

    def _build_filter_bar(self):
        fb = ctk.CTkFrame(self.frame, fg_color=Theme.SURFACE2)
        fb.pack(fill="x")

        self._lbl_severity = ctk.CTkLabel(fb, text="", fg_color=Theme.SURFACE2, text_color=Theme.MUTED, font=FONTS["label"])
        self._lbl_severity.pack(side="left")
        self._i18n_tag(self._lbl_severity, "maint.filter_severity")
        sev_opts = self._get_severity_options()
        self._sev_all = sev_opts[0]
        self.c_severity = ctk.CTkComboBox(fb, values=sev_opts, state="readonly", width=120, command=self._on_filter_change)
        self.c_severity.set(sev_opts[0])
        self.c_severity.pack(side="left", padx=(4, 16))

        self._lbl_type = ctk.CTkLabel(fb, text="", fg_color=Theme.SURFACE2, text_color=Theme.MUTED, font=FONTS["label"])
        self._lbl_type.pack(side="left")
        self._i18n_tag(self._lbl_type, "maint.filter_type")
        type_opts = self._get_type_options()
        self._type_all = type_opts[0]
        self.c_type = ctk.CTkComboBox(fb, values=type_opts, state="readonly", width=140, command=self._on_filter_change)
        self.c_type.set(type_opts[0])
        self.c_type.pack(side="left", padx=(4, 16))

        self._lbl_truck = ctk.CTkLabel(fb, text="", fg_color=Theme.SURFACE2, text_color=Theme.MUTED, font=FONTS["label"])
        self._lbl_truck.pack(side="left")
        self._i18n_tag(self._lbl_truck, "maint.filter_truck")
        self.e_truck = ctk.CTkEntry(fb, fg_color=Theme.INPUT_BG, text_color=Theme.TEXT,
                                    border_color=Theme.BORDER, border_width=1, corner_radius=6,
                                    width=120, font=FONTS["label"])
        self.e_truck.pack(side="left", padx=(4, 16))
        self.e_truck.bind("<KeyRelease>", self._on_filter_change)

        self._lbl_trip = ctk.CTkLabel(fb, text="", fg_color=Theme.SURFACE2, text_color=Theme.MUTED, font=FONTS["label"])
        self._lbl_trip.pack(side="left")
        self._i18n_tag(self._lbl_trip, "maint.filter_trip")
        self.e_trip = ctk.CTkEntry(fb, fg_color=Theme.INPUT_BG, text_color=Theme.TEXT,
                                   border_color=Theme.BORDER, border_width=1, corner_radius=6,
                                   width=120, font=FONTS["label"])
        self.e_trip.pack(side="left", padx=(4, 16))
        self.e_trip.bind("<KeyRelease>", self._on_filter_change)

        self.show_resolved = tk.BooleanVar(value=False)
        self._cb_show_resolved = ctk.CTkCheckBox(
            fb, text="",
            font=FONTS["label"],
            command=self._on_filter_change,
        )
        self._cb_show_resolved.configure(variable=self.show_resolved)
        self._cb_show_resolved.pack(side="left", padx=(16, 0))
        self._i18n_tag(self._cb_show_resolved, "maint.show_resolved")

        self._summary_lbl = ctk.CTkLabel(
            fb, text="", fg_color=Theme.SURFACE2, text_color=Theme.MUTED, font=FONTS["small"]
        )
        self._summary_lbl.pack(side="right", padx=(10, 0))

    def _build_alert_center(self):
        container = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        container.pack(fill="both", expand=True, padx=20, pady=(10, 20))

        self._scrollable = ctk.CTkScrollableFrame(container, fg_color=Theme.BG)
        self._scrollable.pack(fill="both", expand=True)

    def _build_fuel_panel(self):
        self._fuel_panel = FuelPricePanel(self.frame)
        self._fuel_panel.pack(fill="x", pady=(0, 6))

    def _refresh(self):
        if self._closed:
            return
        self._alerts = self.ops.get_active_alerts(limit=200)
        if self.show_resolved.get():
            resolved = self.ops.get_alerts(resolved=True, limit=200)
            self._alerts.extend(resolved)
        self._apply_filters()
        self._refresh_maintenance_kpis()

    def _on_filter_change(self, event=None):
        self._apply_filters()

    def _apply_filters(self):
        severity_filter = self.c_severity.get()
        type_filter = self.c_type.get()
        truck_filter = self.e_truck.get().strip().lower()
        trip_filter = self.e_trip.get().strip().lower()

        raw = self._alerts
        if severity_filter and severity_filter != self._sev_all:
            raw = [a for a in raw if a.severity.value == severity_filter]
        if type_filter and type_filter != self._type_all:
            raw = [a for a in raw if a.type.value == type_filter]
        if truck_filter:
            raw = [a for a in raw if a.truck_id and truck_filter in a.truck_id.lower()]
        if trip_filter:
            raw = [a for a in raw if a.trip_id and trip_filter in a.trip_id.lower()]

        raw.sort(key=lambda a: (
            0 if a.severity == Severity.CRITICAL else
            1 if a.severity == Severity.WARNING else 2,
            a.created_at or "",
        ), reverse=False)

        self._filtered_alerts = raw
        self._render_alerts()

    def _render_alerts(self):
        for w in self._scrollable.winfo_children():
            w.destroy()

        critical = [a for a in self._filtered_alerts if a.severity == Severity.CRITICAL]
        warnings = [a for a in self._filtered_alerts if a.severity == Severity.WARNING]
        info = [a for a in self._filtered_alerts if a.severity == Severity.INFO]

        total = len(self._filtered_alerts)
        alert_word = iconed("maint.alert_s") if total == 1 else iconed("maint.alert_plural")
        self._alert_count_lbl.config(
            text=f"{total} {alert_word}"
        )

        counts = []
        if critical:
            counts.append(iconed("maint.critical_count").format(len(critical)))
        if warnings:
            counts.append(iconed("maint.warning_count").format(len(warnings)))
        if info:
            counts.append(iconed("maint.info_count").format(len(info)))
        self._summary_lbl.config(text=" | ".join(counts))

        if not self._filtered_alerts:
            empty = ctk.CTkLabel(
                self._scrollable,
                text=iconed("maint.no_alerts_filter"),
                fg_color=Theme.BG,
                text_color=Theme.MUTED,
                font=FONTS["body"],
            )
            empty.pack(expand=True)
            return

        for severity, group in [(Severity.CRITICAL, critical), (Severity.WARNING, warnings), (Severity.INFO, info)]:
            if not group:
                continue
            self._build_section(severity, group)

    def _build_section(self, severity: Severity, alerts: list[Alert]):
        color = SEVERITY_COLORS[severity]
        icon = SEVERITY_ICONS[severity]
        label = t(SEVERITY_LABELS[severity])
        count = len(alerts)

        section = ctk.CTkFrame(self._scrollable, fg_color=Theme.BG)
        section.pack(fill="x", pady=(0, 16))

        header = ctk.CTkFrame(section, fg_color=Theme.BG)
        header.pack(fill="x", pady=(0, 8))

        stripl = ctk.CTkFrame(header, fg_color=color, width=4, height=20)
        stripl.pack(side="left")
        ctk.CTkLabel(
            header, text=f"{icon}  {label} ({count})",
            fg_color=Theme.BG, text_color=color,
            font=FONTS["h3"],
        ).pack(side="left", padx=(10, 0))

        sep = ctk.CTkFrame(header, fg_color=Theme.BORDER, height=1)
        sep.pack(side="left", fill="x", expand=True, padx=(14, 0))

        for alert in alerts:
            self._build_alert_card(section, alert)

    def _build_alert_card(self, parent: tk.Frame, alert: Alert):
        sev_color = SEVERITY_COLORS.get(alert.severity, Theme.MUTED)
        icon = ALERT_ICONS.get(alert.type, "\u2753")

        card = ctk.CTkFrame(parent, fg_color=Theme.SURFACE2)
        card.pack(fill="x", pady=(0, 6))

        strip = ctk.CTkFrame(card, fg_color=sev_color, width=4)
        strip.pack(side="left", fill="y")

        inner = ctk.CTkFrame(card, fg_color=Theme.SURFACE2)
        inner.pack(side="left", fill="both", expand=True, padx=(10, 12), pady=10)

        row1 = ctk.CTkFrame(inner, fg_color=Theme.SURFACE2)
        row1.pack(fill="x")

        ctk.CTkLabel(row1, text=icon, fg_color=Theme.SURFACE2, font=FONTS["body"]).pack(side="left")

        ctk.CTkLabel(
            row1, text=alert.title,
            fg_color=Theme.SURFACE2, text_color=Theme.TEXT,
            font=FONTS["small"], anchor="w",
        ).pack(side="left", padx=(8, 0), fill="x", expand=True)

        ts = alert.created_at
        if ts and len(ts) > 16:
            ts = ts[:16].replace("T", " ")
        ctk.CTkLabel(
            row1, text=ts or "",
            fg_color=Theme.SURFACE2, text_color=Theme.MUTED,
                font=FONTS["label"],
        ).pack(side="right")

        ctk.CTkLabel(
            inner, text=alert.message,
            fg_color=Theme.SURFACE2, text_color=Theme.MUTED,
            font=FONTS["label"], anchor="w", wraplength=900,
        ).pack(fill="x", pady=(2, 0))

        refs = []
        if alert.truck_id:
            refs.append(iconed("maint.label_truck", truck_id=alert.truck_id))
        if alert.trip_id:
            refs.append(iconed("maint.label_trip", trip_id=alert.trip_id))
        if refs:
            ctk.CTkLabel(
                inner, text="  \u2022  ".join(refs),
                fg_color=Theme.SURFACE2, text_color=Theme.INFO,
            font=FONTS["label"],
            ).pack(fill="x", pady=(2, 0))

        actions = ctk.CTkFrame(inner, fg_color=Theme.SURFACE2)
        actions.pack(fill="x", pady=(6, 0))

        self._action_btn(actions, iconed("maint.action_resolve"), Theme.SUCCESS, lambda aid=alert.id: self._resolve_alert(aid))
        if alert.truck_id:
            self._action_btn(actions, iconed("maint.action_truck"), Theme.ACCENT, lambda tid=alert.truck_id: self._open_truck(tid))
        if alert.trip_id:
            self._action_btn(actions, iconed("maint.action_trip"), Theme.INFO, lambda tip=alert.trip_id: self._open_trip(tip))
        if alert.truck_id and alert.severity in (Severity.CRITICAL, Severity.WARNING):
            self._action_btn(actions, iconed("maint.action_maint"), Theme.ORANGE, lambda tid=alert.truck_id: self._schedule_maint(tid))
        self._action_btn(actions, iconed("maint.action_remind"), Theme.PURPLE_SOFT, lambda a=alert: self._generate_reminder(a))

    def _action_btn(self, parent: tk.Frame, text: str, color: str, command):
        btn = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=color,
            text_color=Theme.TEXT,
            cursor="hand2",
            font=FONTS["label"],
        )
        btn.pack(side="left", padx=(0, 6))
        btn.bind("<Enter>", lambda e, b=btn, c=color: b.configure(fg_color=Theme.SURFACE3))
        btn.bind("<Leave>", lambda e, b=btn, c=color: b.configure(fg_color=c))

    def _resolve_alert(self, alert_id: str):
        self.ops.resolve_alert(alert_id)
        self._refresh()

    def _open_truck(self, truck_id: str):
        if hasattr(self.parent, "_open_fleet"):
            self.parent._open_fleet()
        target = self.win or self.frame
        target.clipboard_clear()
        target.clipboard_append(truck_id)
        self._flash_msg(iconed("maint.flash_truck_copied").format(truck_id))

    def _open_trip(self, trip_id: str):
        target = self.win or self.frame
        target.clipboard_clear()
        target.clipboard_append(trip_id)
        self._flash_msg(iconed("maint.flash_trip_copied").format(trip_id))

    def _schedule_maint(self, truck_id: str):
        self._flash_msg(iconed("maint.flash_maint_scheduled").format(truck_id))

    def _generate_reminder(self, alert: Alert):
        self._flash_msg(iconed("maint.flash_reminder").format(alert.title))

    def _flash_msg(self, msg: str):
        self._alert_count_lbl.config(text=msg, text_color=Theme.WARNING)
        total = len(self._filtered_alerts)
        alert_word = iconed("maint.alert_s") if total == 1 else iconed("maint.alert_plural")
        self._safe_after(2500, lambda: self._alert_count_lbl.config(
            text=f"{total} {alert_word}",
            text_color=Theme.MUTED,
        ))

    def _safe_after(self, delay, callback):
        target = self.win or self.frame or self.parent
        try:
            aid = target.after(delay, callback)
            self._after_ids.append(aid)
            return aid
        except Exception:
            pass
            return None
