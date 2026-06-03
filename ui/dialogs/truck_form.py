"""Truck add/edit form dialog — extracted from fleet_tab.py."""
import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox
from typing import Optional

from services.fleet_service import FleetService
from services.i18n import t
from ui.styles import Theme
from ui.widgets import ActionButton, StyledCheckbutton, StyledEntry


class TruckFormDialog:
    """Scrollable form toplevel for creating or editing a truck."""

    def __init__(self, parent: tk.Widget, service: FleetService,
                 title: Optional[str] = None, truck: Optional[tuple] = None,
                 on_save=None, dta_service=None):
        self._service = service
        self._truck = truck
        self._on_save = on_save
        self._dta_service = dta_service

        if title is None:
            title = t("fleet.truck_form_title")

        self.win = ctk.CTkToplevel(parent)
        self.win.title(title)
        self.win.configure(fg_color=Theme.BG)
        Theme.apply(self.win)

        self._build()

    def _build(self):
        self._scroll_frame = ctk.CTkScrollableFrame(self.win, fg_color=Theme.BG)
        self._scroll_frame.pack(fill="both", expand=True)

        def make_field(label_text, default=""):
            ctk.CTkLabel(self._scroll_frame, text=label_text, fg_color=Theme.BG,
                         text_color=Theme.TEXT).pack(anchor="w")
            e = StyledEntry(self._scroll_frame)
            e.pack(fill="x", pady=6)
            default = "" if default is None else default
            e.insert(0, default)
            return e

        truck = self._truck
        self._fields = {
            'plate':       make_field(t("fleet.form_plate"),         truck["plate_number"] if truck else ""),
            'model':       make_field(t("fleet.form_model"),         truck["model"] if truck else ""),
            'manufacturer':make_field(t("fleet.form_manufacturer"),  truck["manufacturer"] if truck else ""),
            'year':        make_field(t("fleet.form_year"),          str(truck["year"]) if truck and truck.get("year") else ""),
            'vin':         make_field(t("fleet.form_vin"),           truck["vin"] if truck else ""),
            'fuel':        make_field(t("fleet.form_consumption"),   str(truck["fuel_consumption"]) if truck and truck.get("fuel_consumption") is not None else ""),
            'mileage':     make_field(t("fleet.form_km"),            str(truck["mileage"]) if truck and truck.get("mileage") is not None else "0"),
            'monthly_rate':make_field(t("fleet.form_rate"),          f"{truck['monthly_rate']:.2f}" if truck and truck.get("monthly_rate") is not None else "0"),
            'status':      make_field(t("fleet.form_status"),       truck.get("status") if truck else t("fleet.status_active")),
            'tracking_device_id': make_field(t("fleet.form_tracking_device_id"), truck.get("tracking_device_id") or ""),
        }

        self._driver_ids = []
        if self._dta_service:
            ctk.CTkLabel(self._scroll_frame, text=t("fleet.table_driver"), fg_color=Theme.BG, text_color=Theme.TEXT).pack(anchor="w", pady=(6, 0))
            drivers_list = [("", t("fleet.table_driver_unassigned"))]
            try:
                from repositories.driver_repository import DriverRepository
                dr_repo = DriverRepository(self._service.db)
                for dr in dr_repo.get_active_drivers():
                    drivers_list.append((str(dr["id"]), dr["name"]))
            except Exception:
                pass
            driver_names = [label for _, label in drivers_list]
            self._driver_names = driver_names
            self._driver_combo = ctk.CTkComboBox(self._scroll_frame, values=driver_names, state="readonly")
            self._driver_combo.pack(fill="x", pady=6)
            self._driver_ids = [did for did, _ in drivers_list]

            if truck and self._dta_service:
                assigned_driver = self._dta_service.get_driver_name_for_truck(truck["id"])
                if assigned_driver and assigned_driver in driver_names:
                    self._driver_combo.set(assigned_driver)

        self._active_var = tk.IntVar(value=(truck.get("active_status", 1) if truck else 1))
        StyledCheckbutton(self._scroll_frame, text=t("fleet.form_active"),
                          variable=self._active_var).pack(anchor="w", pady=(6, 12))

        ActionButton(self._scroll_frame, t("fleet.save_button"),
                     self._save, color=Theme.ACCENT_SUCCESS).pack(fill="x", pady=10)
        ActionButton(self._scroll_frame, t("fleet.cancel_button"),
                     self.win.destroy, color=Theme.SURFACE2).pack(fill="x")

    def _save(self):
        f = self._fields
        plate = f['plate'].get().strip().upper()
        if not plate:
            messagebox.showwarning(t("fleet.validation_plate_required"),
                                   t("fleet.validation_plate_required"))
            return
        try:
            year = int(f['year'].get()) if f['year'].get().strip() else None
        except ValueError:
            messagebox.showwarning(t("fleet.validation_year_invalid"),
                                   t("fleet.validation_year_invalid"))
            return
        try:
            fuel = float(f['fuel'].get()) if f['fuel'].get().strip() else None
        except ValueError:
            messagebox.showwarning(t("fleet.validation_consumption_invalid"),
                                   t("fleet.validation_consumption_invalid"))
            return
        try:
            mileage = float(f['mileage'].get() or 0)
            monthly_rate = float(f['monthly_rate'].get() or 0)
        except ValueError:
            messagebox.showwarning(t("fleet.validation_km_rate_service_invalid"),
                                   t("fleet.validation_km_rate_service_invalid"))
            return

        data = {
            "plate_number": plate,
            "model": f['model'].get(),
            "manufacturer": f['manufacturer'].get(),
            "year": year,
            "vin": f['vin'].get(),
            "fuel_consumption": fuel,
            "mileage": mileage,
            "monthly_rate": monthly_rate,
            "status": f['status'].get(),
            "active_status": self._active_var.get(),
            "tracking_device_id": f['tracking_device_id'].get().strip(),
        }

        try:
            if self._truck:
                truck_id = self._truck["id"]
                self._service.update_truck(truck_id, data)
            else:
                truck_id = self._service.add_truck(data)

            if self._dta_service and hasattr(self, "_driver_combo"):
                try:
                    selected_idx = self._driver_names.index(self._driver_combo.get())
                except ValueError:
                    selected_idx = -1
                if selected_idx >= 0:
                    driver_id_str = self._driver_ids[selected_idx]
                    if driver_id_str:
                        self._dta_service.assign_driver_to_truck(int(driver_id_str), truck_id)
                    else:
                        self._dta_service.unassign_truck(truck_id)

            if self._on_save:
                self._on_save()
            self.win.destroy()
        except Exception as ex:
            messagebox.showerror(t("fleet.error_save").format(""),
                                 t("fleet.error_save").format(ex))
