import tkinter as tk
import customtkinter as ctk
import logging
from tkinter import ttk, messagebox
from typing import Any, Dict, Optional

from services.i18n import t
from ui.styles import Theme
from ui.widgets import ActionButton, StyledCheckbutton, StyledEntry

logger = logging.getLogger(__name__)


class DriverFormDialog:

    def __init__(self, parent, driver_repo, driver: Optional[Dict[str, Any]] = None,
                 on_save=None, dta_service=None):
        self._repo = driver_repo
        self._driver = driver
        self._on_save = on_save
        self._dta_service = dta_service

        title = t("driver_manager.edit_driver") if driver else t("driver_manager.add_driver")
        self.win = ctk.CTkToplevel(parent)
        self.win.configure(fg_color=Theme.BG)
        self.win.title(title)
        self.win.geometry("480x680")
        Theme.apply(self.win)

        self._build()

    def _build(self):
        self._scroll_frame = ctk.CTkScrollableFrame(self.win, fg_color=Theme.BG)
        self._scroll_frame.pack(fill="both", expand=True)

        def make_field(label_text, default=""):
            ctk.CTkLabel(self._scroll_frame, text=label_text, fg_color=Theme.BG, text_color=Theme.TEXT).pack(anchor="w")
            e = StyledEntry(self._scroll_frame)
            e.pack(fill="x", pady=6)
            e.insert(0, default)
            return e

        d = self._driver
        self._fields = {
            "name":              make_field(t("driver_manager.field_name"),              d.get("name", "") if d else ""),
            "phone":             make_field(t("driver_manager.field_phone"),             d.get("phone", "") if d else ""),
            "email":             make_field(t("driver_manager.field_email"),             d.get("email", "") if d else ""),
            "license_number":    make_field(t("driver_manager.field_license_number"),    d.get("license_number", "") if d else ""),
            "license_category":  make_field(t("driver_manager.field_license_category"),  d.get("license_category", "") if d else ""),
            "license_expiry":    make_field(t("driver_manager.field_license_expiry"),    d.get("license_expiry", "") if d else ""),
            "medical_expiry":    make_field(t("driver_manager.field_medical_expiry"),    d.get("medical_expiry", "") if d else ""),
            "hire_date":         make_field(t("driver_manager.field_hire_date"),         d.get("hire_date", "") if d else ""),
            "monthly_salary":    make_field(t("driver_manager.field_monthly_salary"),    str(d.get("monthly_salary", "0")) if d else "0"),
            "notes":             make_field(t("driver_manager.field_notes"),             d.get("notes", "") if d else ""),
        }

        if self._dta_service:
            ctk.CTkLabel(self._scroll_frame, text=t("driver_manager.col_truck"), fg_color=Theme.BG, text_color=Theme.TEXT).pack(anchor="w", pady=(6, 0))
            trucks = [("", t("driver_manager.unassigned"))]
            try:
                from repositories.fleet_repository import FleetRepository
                fleet_repo = FleetRepository(self._repo.db)
                for tr in fleet_repo.get_active_trucks():
                    trucks.append((str(tr["id"]), tr["plate_number"]))
            except Exception:
                pass
            self._truck_names = [label for _, label in trucks]
            self._truck_combo = ctk.CTkComboBox(self._scroll_frame, values=self._truck_names, state="readonly")
            self._truck_combo.pack(fill="x", pady=6)
            self._truck_ids = [tid for tid, _ in trucks]

            if d and self._dta_service:
                assigned_plate = self._dta_service.get_truck_plate_for_driver(d["id"])
                if assigned_plate and assigned_plate in self._truck_names:
                    self._truck_combo.set(assigned_plate)

        self._active_var = tk.IntVar(value=d.get("is_active", 1) if d else 1)
        StyledCheckbutton(self._scroll_frame, text=t("driver_manager.field_active"),
                          variable=self._active_var).pack(anchor="w", pady=(6, 12))

        ActionButton(self._scroll_frame, t("driver_manager.save"),
                     self._save, color=Theme.ACCENT_SUCCESS).pack(fill="x", pady=10)
        ActionButton(self._scroll_frame, t("driver_manager.cancel"),
                     self.win.destroy, color=Theme.SURFACE2).pack(fill="x")

    def _save(self):
        f = self._fields
        name = f["name"].get().strip()
        if not name:
            messagebox.showwarning(t("driver_manager.title"), t("driver_manager.field_name"))
            return

        try:
            salary = float(f["monthly_salary"].get() or 0)
        except ValueError:
            messagebox.showwarning(t("driver_manager.title"), t("driver_manager.field_monthly_salary"))
            return

        data = {
            "name": name,
            "phone": f["phone"].get(),
            "email": f["email"].get(),
            "license_number": f["license_number"].get(),
            "license_category": f["license_category"].get(),
            "license_expiry": f["license_expiry"].get(),
            "medical_expiry": f["medical_expiry"].get(),
            "hire_date": f["hire_date"].get(),
            "monthly_salary": salary,
            "notes": f["notes"].get(),
            "is_active": self._active_var.get(),
        }

        try:
            if self._driver:
                driver_id = self._driver["id"]
                self._repo.update(driver_id, data)
            else:
                driver_id = self._repo.create(data)

            if self._dta_service and hasattr(self, "_truck_combo"):
                selected_label = self._truck_combo.get()
                try:
                    selected_idx = self._truck_names.index(selected_label)
                except ValueError:
                    selected_idx = -1
                if selected_idx >= 0:
                    truck_id_str = self._truck_ids[selected_idx]
                    if truck_id_str:
                        self._dta_service.assign_driver_to_truck(driver_id, int(truck_id_str))
                    else:
                        self._dta_service.unassign_driver(driver_id)

            if self._on_save:
                self._on_save()
            self.win.destroy()
        except Exception as ex:
            messagebox.showerror(t("main.error_title"), str(ex))
