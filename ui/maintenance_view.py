import tkinter as tk
import customtkinter as ctk

from services.fleet_maintenance_service import FleetMaintenanceService
from services.i18n import t
from ui.icons import iconed, register_listener, unregister_listener
from ui.styles import Theme
from ui.widgets import ActionButton
from ui.widgets.maintenance_record_tab import MaintenanceRecordTab
from ui.widgets.maintenance_schedule_tab import MaintenanceScheduleTab
from ui.widgets.maintenance_health_tab import MaintenanceHealthTab
from ui.theme import FONTS


class MaintenanceView:
    def __init__(self, parent, db, truck_id, truck_plate):
        self.win = ctk.CTkToplevel(parent)
        self.win.configure(fg_color=Theme.BG)
        self.win.title(iconed("maint.title", truck_plate))
        self.win.geometry("1200x750")
        Theme.apply(self.win)

        self.db = db
        self.truck_id = truck_id
        self.truck_plate = truck_plate
        self.service = FleetMaintenanceService(db)

        self._i18n_widgets = []

        self._build_ui()
        self.win.bind("<Destroy>", self._on_destroy)
        register_listener(self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_destroy(self, e=None):
        if e is not None and e.widget != self.win:
            return
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        self.win.title(iconed("maint.title", self.truck_plate))
        self._title_lbl.configure(text=iconed("maint.header", self.truck_plate))
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.configure(text=f"{prefix}{(iconed(key) if key.startswith('maint.') else t(key))}")
            except Exception:
                pass
        for tab in (self._record_tab, self._schedule_tab, self._health_tab):
            if hasattr(tab, "refresh_translations"):
                tab.refresh_translations()

    def _build_ui(self):
        top = ctk.CTkFrame(self.win, fg_color=Theme.SURFACE)
        top.pack(fill="x")

        self._title_lbl = ctk.CTkLabel(top, text=iconed("maint.header", self.truck_plate),
                                       fg_color=Theme.SURFACE, text_color=Theme.TEXT,
                                       font=FONTS["h2"])
        self._title_lbl.pack(side="left", padx=20, pady=10)

        self._close_btn = ActionButton(top, iconed("maint.close"), self.win.destroy, color=Theme.SURFACE2)
        self._close_btn.pack(side="right", padx=20, pady=10)
        self._i18n_tag(self._close_btn, "maint.close")

        self._nb = ctk.CTkTabview(self.win, fg_color=Theme.BG)
        self._nb.pack(fill="both", expand=True, padx=12, pady=6)
        self._nb.add(iconed("maint.tab_history"))
        self._nb.add(iconed("maint.tab_schedules"))
        self._nb.add(iconed("maint.tab_health"))

        self._record_tab = MaintenanceRecordTab(self._nb.tab(iconed("maint.tab_history")),
                                                self.service, self.truck_id,
                                                self.truck_plate, self.win,
                                                on_change=self._on_maintenance_change)
        self._schedule_tab = MaintenanceScheduleTab(self._nb.tab(iconed("maint.tab_schedules")),
                                                    self.service, self.truck_id,
                                                    self.truck_plate, self.win,
                                                    on_change=self._on_maintenance_change)
        self._health_tab = MaintenanceHealthTab(self._nb.tab(iconed("maint.tab_health")),
                                                self.service, self.truck_id,
                                                self.truck_plate, self.win)

    def _on_maintenance_change(self):
        self._health_tab.refresh()
