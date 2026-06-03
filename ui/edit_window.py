import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from services.i18n import t
from services.trip_service import TripService
from ui.widgets import StyledEntry, ActionButton
from ui.styles import Theme

class EditWindow:
    def __init__(self, parent, db, trip_id, callback):
        self.win = ctk.CTkToplevel(parent)
        self.win.configure(fg_color=Theme.BG)
        self.win.title(t("edit_trip.title").format(trip_id))
        self.win.geometry("500x600")
        Theme.apply(self.win)
        self.trip_service = TripService(db)
        self.trip_id = trip_id
        self.callback = callback

        self.data = self.trip_service.get_by_id(trip_id)
        self._setup_ui()

    def _setup_ui(self):
        container = ctk.CTkFrame(self.win, fg_color=Theme.BG)
        container.pack(fill="both", expand=True)

        fields = [
            ("truck_number", t("edit_trip.field_truck")),
            ("driver_name", t("edit_trip.field_driver")),
            ("client_name", t("edit_trip.field_client")),
            ("distance_km", t("edit_trip.field_distance")),
            ("net_profit", t("edit_trip.field_profit")),
        ]

        self.entries = {}
        for key, label in fields:
            ctk.CTkLabel(container, text=label, fg_color=Theme.BG, text_color=Theme.TEXT).pack(anchor="w", pady=(10,0))
            e = StyledEntry(container)
            e.insert(0, str(self.data[key]))
            e.pack(fill="x")
            self.entries[key] = e

        ActionButton(container, f"💾 {t('edit_trip.save_button')}", self._save, color=Theme.ACCENT_SUCCESS).pack(fill="x", pady=30)

    def _save(self):
        new_data = {key: self.entries[key].get() for key in self.entries}
        try:
            self.trip_service.update(self.trip_id, new_data)
            self.callback()
            self.win.destroy()
        except Exception as e:
            messagebox.showerror(t("edit_trip.error_title"), str(e))
