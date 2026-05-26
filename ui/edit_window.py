import tkinter as tk
from tkinter import ttk, messagebox
from services.i18n import t
from ui.widgets import StyledEntry, ActionButton
from ui.styles import Theme

class EditWindow:
    def __init__(self, parent, db, trip_id, callback):
        self.win = tk.Toplevel(parent)
        self.win.title(t("edit_trip.title").format(trip_id))
        self.win.geometry("500x600")
        Theme.apply(self.win)
        self.db = db
        self.trip_id = trip_id
        self.callback = callback
        
        self.data = self.db.get_trip_by_id(trip_id)
        self._setup_ui()

    def _setup_ui(self):
        container = tk.Frame(self.win, bg=Theme.BG, padx=30, pady=20)
        container.pack(fill="both", expand=True)

        fields = [
            ("truck_number", t("edit_trip.field_truck")),
            ("driver_name", t("edit_trip.field_driver")),
            ("client_name", t("edit_trip.field_client")),
            ("distance_km", t("edit_trip.field_distance")),
            ("net_profit", t("edit_trip.field_profit")),
            ("status", t("edit_trip.field_status"))
        ]

        self.entries = {}
        for key, label in fields:
            tk.Label(container, text=label, bg=Theme.BG, fg=Theme.TEXT).pack(anchor="w", pady=(10,0))
            if key == "status":
                e = ttk.Combobox(container, values=t("edit_trip.status_options"), state="readonly")
                e.set(self.data[key])
            else:
                e = StyledEntry(container)
                e.insert(0, str(self.data[key]))
            e.pack(fill="x")
            self.entries[key] = e

        ActionButton(container, f"💾 {t('edit_trip.save_button')}", self._save, color=Theme.ACCENT_SUCCESS).pack(fill="x", pady=30)

    def _save(self):
        new_data = {key: self.entries[key].get() for key in self.entries}
        try:
            self.db.update_trip(self.trip_id, new_data)
            self.callback()
            self.win.destroy()
        except Exception as e:
            messagebox.showerror(t("edit_trip.error_title"), str(e))
