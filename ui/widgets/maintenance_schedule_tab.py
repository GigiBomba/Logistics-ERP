import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox
from typing import Optional, Callable

from services.i18n import t
from ui.icons import iconed
from services.fleet_maintenance_service import FleetMaintenanceService, MaintType, MAINT_DISPLAY, MAINT_ICONS
from ui.styles import Theme
from ui.widgets import ActionButton, StyledEntry
from ui.theme import FONTS


class MaintenanceScheduleTab(ctk.CTkFrame):
    def __init__(self, parent, service: FleetMaintenanceService, truck_id: int,
                 truck_plate: str, win: tk.Toplevel, on_change: Optional[Callable] = None):
        super().__init__(parent, fg_color=Theme.BG)
        self.service = service
        self.truck_id = truck_id
        self.truck_plate = truck_plate
        self.win = win
        self.on_change = on_change
        self._i18n_widgets = []

        self._build()

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _build(self):
        toolbar = ctk.CTkFrame(self, fg_color=Theme.BG)
        toolbar.pack(fill="x")
        self._add_schedule_btn = ActionButton(toolbar, iconed("maint.schedule_add"), self._add_schedule_win,
                                               color=Theme.ACCENT_SUCCESS)
        self._add_schedule_btn.pack(side="left", padx=4)
        self._i18n_tag(self._add_schedule_btn, "maint.schedule_add")
        self._delete_schedule_btn = ActionButton(toolbar, iconed("maint.delete"), self._delete_schedule,
                                                  color=Theme.DANGER)
        self._delete_schedule_btn.pack(side="left", padx=4)
        self._i18n_tag(self._delete_schedule_btn, "maint.delete")

        self._schedule_container = ctk.CTkFrame(self, fg_color=Theme.BG)
        self._schedule_container.pack(fill="both", expand=True, padx=6, pady=4)
        self._refresh_schedules()

    def refresh_translations(self):
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.configure(text=f"{prefix}{iconed(key) if key.startswith('maint.') else t(key)}")
            except Exception:
                pass
        self._refresh_schedules()

    def _refresh_schedules(self):
        for w in self._schedule_container.winfo_children():
            w.destroy()
        schedules = self.service.get_schedules(self.truck_id)
        if not schedules:
            ctk.CTkLabel(self._schedule_container, text=iconed("maint.no_schedules"),
                          fg_color=Theme.BG, text_color=Theme.MUTED, font=FONTS["small"]).pack(pady=40)
            return

        for s in schedules:
            pred = self.service.predict_next_service(self.truck_id, s["maintenance_type"])
            card = ctk.CTkFrame(self._schedule_container, fg_color=Theme.SURFACE2)
            card.pack(fill="x", pady=3)

            mt = s["maintenance_type"]
            try:
                icon = MAINT_ICONS.get(MaintType(mt), "\u2699\uFE0F")
                disp = MAINT_DISPLAY.get(MaintType(mt), mt)
            except ValueError:
                icon = "\u2699\uFE0F"
                disp = mt

            row1 = ctk.CTkFrame(card, fg_color=Theme.SURFACE2)
            row1.pack(fill="x")
            ctk.CTkLabel(row1, text=f"{icon} {disp}", fg_color=Theme.SURFACE2, text_color=Theme.TEXT,
                         font=FONTS["small"]).pack(side="left")

            status = iconed("maint.status_ok")
            status_color = Theme.SUCCESS
            if pred and pred.get("overdue"):
                status = iconed("maint.status_overdue")
                status_color = Theme.DANGER
            elif pred and pred.get("remaining_km") is not None and pred["remaining_km"] < 5000:
                status = iconed("maint.status_due_soon")
                status_color = Theme.WARNING
            ctk.CTkLabel(row1, text=status, fg_color=Theme.SURFACE2, text_color=status_color,
                         font=FONTS["label"]).pack(side="right")

            details = []
            if s.get("interval_km"):
                details.append(iconed("maint.schedule_every_km", s["interval_km"]))
            if s.get("interval_months"):
                details.append(iconed("maint.schedule_every_months", s["interval_months"]))
            if s.get("fixed_expiry_date"):
                details.append(iconed("maint.schedule_expires", s["fixed_expiry_date"]))
            if s.get("last_done_km"):
                details.append(iconed("maint.schedule_last_km", s["last_done_km"]))
            if s.get("last_done_date"):
                details.append(iconed("maint.schedule_last_date", s["last_done_date"]))
            if details:
                ctk.CTkLabel(card, text=" | ".join(details), fg_color=Theme.SURFACE2, text_color=Theme.MUTED,
                             font=FONTS["label"]).pack(anchor="w", pady=(2, 0))

            if pred:
                parts = []
                if pred.get("due_km") is not None:
                    next_due_km = pred["due_km"]
                    remaining_km = pred.get("remaining_km", 0)
                    
                    # Color code based on proximity to due
                    if pred.get("overdue"):
                        color = Theme.DANGER
                        label = f"⚠️ {t('maint.schedule_next_due_km')}: {next_due_km:,.0f} km ({t('maint.status_overdue')})"
                    elif remaining_km < 500:
                        color = Theme.DANGER
                        label = f"⚠️ {t('maint.schedule_next_due_km')}: {next_due_km:,.0f} km ({remaining_km:,.0f} km {t('maint.status_remaining')})"
                    elif remaining_km < 5000:
                        color = Theme.WARNING
                        label = f"⚡ {t('maint.schedule_next_due_km')}: {next_due_km:,.0f} km ({remaining_km:,.0f} km {t('maint.status_remaining')})"
                    else:
                        color = Theme.SUCCESS
                        label = f"✓ {t('maint.schedule_next_due_km')}: {next_due_km:,.0f} km ({remaining_km:,.0f} km {t('maint.status_remaining')})"
                    
                    ctk.CTkLabel(card, text=label, fg_color=Theme.SURFACE2, text_color=color,
                                 font=FONTS["label"]).pack(anchor="w", pady=(2, 0))
                
                if pred.get("due_by_date"):
                    parts.append(iconed("maint.schedule_due_by", pred["due_by_date"]))
                if parts:
                    c = Theme.DANGER if pred.get("overdue") else Theme.MUTED
                    ctk.CTkLabel(card, text=" | ".join(parts), fg_color=Theme.SURFACE2, text_color=c,
                                 font=FONTS["label"]).pack(anchor="w")

            ActionButton(card, iconed("maint.edit"), lambda sid=s["id"]: self._edit_schedule(sid),
                         color=Theme.SURFACE3).pack(side="right")

    def _add_schedule_win(self):
        self._schedule_form(title=iconed("maint.schedule_form_title_add"))

    def _edit_schedule(self, sid):
        schedule = self.service.get_schedules(self.truck_id)
        schedule = next((s for s in schedule if s["id"] == sid), None)
        if schedule:
            self._schedule_form(title=iconed("maint.schedule_form_title_edit"), schedule=schedule)

    def _schedule_form(self, title="", schedule=None):
        win = ctk.CTkToplevel(self.win)
        win.title(title)
        win.geometry("500x450")
        win.configure(fg_color=Theme.BG)

        f = ctk.CTkFrame(win, fg_color=Theme.BG)
        f.pack(fill="both", expand=True)

        fields = {}

        def add_row(label):
            r = ctk.CTkFrame(f, fg_color=Theme.BG)
            r.pack(fill="x", pady=4)
            ctk.CTkLabel(r, text=label, fg_color=Theme.BG, text_color=Theme.MUTED,
                         font=FONTS["label"], width=20, anchor="w").pack(side="left")
            e = StyledEntry(r)
            e.pack(side="left", fill="x", expand=True)
            return e

        default_type = schedule["maintenance_type"] if schedule else MaintType.OIL_CHANGE.value
        r = ctk.CTkFrame(f, fg_color=Theme.BG)
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=iconed("maint.form_type"), fg_color=Theme.BG, text_color=Theme.MUTED,
                     font=FONTS["label"], width=20, anchor="w").pack(side="left")
        type_combo = ctk.CTkComboBox(r, values=[mt.value for mt in MaintType], state="readonly")
        type_combo.set(default_type)
        type_combo.pack(side="left")

        fields["interval_km"] = add_row(iconed("maint.schedule_form_interval_km"))
        fields["interval_months"] = add_row(iconed("maint.schedule_form_interval_months"))
        fields["expiry"] = add_row(iconed("maint.schedule_form_expiry"))
        fields["last_km"] = add_row(iconed("maint.schedule_form_last_km"))
        fields["last_date"] = add_row(iconed("maint.schedule_form_last_date"))

        if schedule:
            if schedule.get("interval_km"):
                fields["interval_km"].insert(0, str(schedule["interval_km"]))
            if schedule.get("interval_months"):
                fields["interval_months"].insert(0, str(schedule["interval_months"]))
            if schedule.get("fixed_expiry_date"):
                fields["expiry"].insert(0, schedule["fixed_expiry_date"])
            if schedule.get("last_done_km"):
                fields["last_km"].insert(0, str(schedule["last_done_km"]))
            if schedule.get("last_done_date"):
                fields["last_date"].insert(0, schedule["last_done_date"])

        def save():
            try:
                mt = type_combo.get()
                ikm = float(fields["interval_km"].get().strip()) if fields["interval_km"].get().strip() else None
                imo = int(fields["interval_months"].get().strip()) if fields["interval_months"].get().strip() else None
                exp = fields["expiry"].get().strip()
                lkm = float(fields["last_km"].get().strip()) if fields["last_km"].get().strip() else None
                ldt = fields["last_date"].get().strip()

                if schedule:
                    self.service.update_schedule(
                        schedule["id"],
                        interval_km=ikm, interval_months=imo,
                        fixed_expiry_date=exp,
                        last_done_km=lkm, last_done_date=ldt,
                    )
                else:
                    self.service.add_schedule(
                        self.truck_id, mt, ikm, imo, exp, lkm, ldt
                    )
                win.destroy()
                self._refresh_schedules()
                if self.on_change:
                    self.on_change()
            except Exception as e:
                messagebox.showerror(iconed("maint.error_generic"), str(e))

        ActionButton(f, iconed("maint.save"), save, color=Theme.ACCENT_SUCCESS).pack(fill="x", pady=8)
        ActionButton(f, iconed("maint.cancel"), win.destroy, color=Theme.SURFACE2).pack(fill="x")

    def _delete_schedule(self):
        schedules = self.service.get_schedules(self.truck_id)
        if not schedules:
            return
        sids = [s["id"] for s in schedules]
        win = ctk.CTkToplevel(self.win)
        win.title(iconed("maint.schedule_delete_title"))
        win.geometry("400x300")
        win.configure(fg_color=Theme.BG)
        ctk.CTkLabel(win, text=iconed("maint.schedule_delete_prompt"), fg_color=Theme.BG, text_color=Theme.TEXT).pack(pady=10)

        var = tk.StringVar()
        for s in schedules:
            try:
                disp = MAINT_DISPLAY.get(MaintType(s["maintenance_type"]), s["maintenance_type"])
            except ValueError:
                disp = s["maintenance_type"]
            ctk.CTkRadioButton(win, text=f"{disp}", variable=var, value=str(s["id"])).pack(anchor="w", padx=20)

        def do_delete():
            if var.get() and messagebox.askyesno(iconed("maint.schedule_delete_title"), iconed("maint.schedule_delete_confirm")):
                self.service.delete_schedule(int(var.get()))
                win.destroy()
                self._refresh_schedules()
        ActionButton(win, iconed("maint.delete"), do_delete, color=Theme.DANGER).pack(pady=10)
