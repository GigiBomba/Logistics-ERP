import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import csv
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from services.i18n import t
from ui.icons import iconed
from services.fleet_maintenance_service import FleetMaintenanceService, MaintType, MAINT_DISPLAY, MAINT_ICONS
from ui.styles import Theme
from ui.widgets import ActionButton, StyledEntry
from ui.theme import COLORS, FONTS

PAGE_SIZE = 20

PRESETS = [
    ("maint.preset_tire", MaintType.TIRE_REPLACEMENT, COLORS["text_muted"]),
    ("maint.preset_oil", MaintType.OIL_CHANGE, COLORS["warning"]),
    ("maint.preset_brake", MaintType.BRAKES, COLORS["danger"]),
]


class MaintenanceRecordTab(ctk.CTkFrame):
    def __init__(self, parent, service: FleetMaintenanceService, truck_id: int,
                 truck_plate: str, win: tk.Toplevel, on_change: Optional[Callable] = None):
        super().__init__(parent, fg_color=Theme.BG)
        self.service = service
        self.truck_id = truck_id
        self.truck_plate = truck_plate
        self.win = win
        self.on_change = on_change
        self._page = 0
        self._total = 0
        self._records: List[Dict[str, Any]] = []
        self._i18n_widgets = []
        self._tree_heading_keys = []

        self._build()

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _build(self):
        toolbar = ctk.CTkFrame(self, fg_color=Theme.BG)
        toolbar.pack(fill="x")

        self._add_btn = ActionButton(toolbar, iconed("maint.add_record"), self._add_record_win,
                     color=Theme.ACCENT_SUCCESS)
        self._add_btn.pack(side="left", padx=4)
        self._i18n_tag(self._add_btn, "maint.add_record")
        self._del_btn = ActionButton(toolbar, iconed("maint.delete"), self._delete_selected,
                      color=Theme.DANGER)
        self._del_btn.pack(side="left", padx=4)
        self._i18n_tag(self._del_btn, "maint.delete")
        self._exp_btn = ActionButton(toolbar, iconed("maint.export"), self._export_csv,
                      color=Theme.SURFACE2)
        self._exp_btn.pack(side="left", padx=4)
        self._i18n_tag(self._exp_btn, "maint.export")

        presets_f = ctk.CTkFrame(toolbar, fg_color=Theme.BG)
        presets_f.pack(side="left", padx=(10, 0))
        self._preset_btns = []
        for label_key, mt, color in PRESETS:
            btn = ctk.CTkButton(presets_f, text=t(label_key), fg_color=color, text_color="white",
                            font=FONTS["label"],
                            command=lambda m=mt: self._apply_preset_filter(m))
            btn.pack(side="left", padx=2)
            self._preset_btns.append((btn, label_key))
            self._i18n_tag(btn, label_key)
        self._clear_preset_btn = ctk.CTkButton(presets_f, text="\u2716", fg_color=Theme.SURFACE2, text_color=Theme.TEXT,
                  font=FONTS["label"],
                  command=self._clear_preset_filter)
        self._clear_preset_btn.pack(side="left", padx=2)

        self._filter_lbl = ctk.CTkLabel(toolbar, text=iconed("maint.filter_label"), fg_color=Theme.BG, text_color=Theme.MUTED,
                 font=FONTS["label"])
        self._filter_lbl.pack(side="left", padx=(20, 4))
        self._i18n_tag(self._filter_lbl, "maint.filter_label")
        type_opts = [""] + [mt.value for mt in MaintType]
        self.c_filter = ctk.CTkComboBox(toolbar, values=type_opts, width=16, command=lambda v: self._load_records())
        self.c_filter.set("")
        self.c_filter.pack(side="left")

        self._page_lbl = ctk.CTkLabel(toolbar, text="", fg_color=Theme.BG, text_color=Theme.MUTED,
                                  font=FONTS["label"])
        self._page_lbl.pack(side="right", padx=10)
        self._prev_btn = ActionButton(toolbar, iconed("maint.prev"), self._prev_page,
                      color=Theme.SURFACE2)
        self._prev_btn.pack(side="right", padx=2)
        self._i18n_tag(self._prev_btn, "maint.prev")
        self._next_btn = ActionButton(toolbar, iconed("maint.next"), self._next_page,
                      color=Theme.SURFACE2)
        self._next_btn.pack(side="right", padx=2)
        self._i18n_tag(self._next_btn, "maint.next")

        cols = ("date", "type", "km", "cost", "provider", "notes")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        col_keys = [
            ("date", "maint.col_date"),
            ("type", "maint.col_type"),
            ("km", "maint.col_km"),
            ("cost", "maint.col_cost"),
            ("provider", "maint.col_provider"),
            ("notes", "maint.col_notes"),
        ]
        for col, key in col_keys:
            self.tree.heading(col, text=t(key))
            self._tree_heading_keys.append((col, key))
        for c in cols:
            self.tree.column(c, width=120 if c in ("date", "type", "cost", "provider") else 200,
                             anchor="center" if c in ("km", "cost") else "w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=4)
        self.tree.bind("<Double-1>", lambda e: self._edit_record())
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        self._load_records()

    def refresh_translations(self):
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.configure(text=f"{prefix}{iconed(key) if key.startswith('maint.') else t(key)}")
            except Exception:
                pass
        for col, key in self._tree_heading_keys:
            try:
                self.tree.heading(col, text=t(key))
            except Exception:
                pass
        total_pages = max(1, (self._total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._page_lbl.config(text=iconed("maint.page_info", page=self._page + 1, other=total_pages, total=self._total))

    def _load_records(self):
        self.tree.delete(*self.tree.get_children())
        ft = self.c_filter.get() or None
        offset = self._page * PAGE_SIZE
        self._total = self.service.get_record_count(truck_id=self.truck_id, maint_type=ft)
        self._records = self.service.get_records(
            truck_id=self.truck_id, maint_type=ft, limit=PAGE_SIZE, offset=offset
        )

        for r in self._records:
            try:
                icon = MAINT_ICONS.get(MaintType(r["maintenance_type"]), "\u2699\uFE0F")
            except ValueError:
                icon = "\u2699\uFE0F"
            display_type = MAINT_DISPLAY.get(r["maintenance_type"], r["maintenance_type"].replace("_", " ").title())
            self.tree.insert("", "end", iid=str(r["id"]), values=(
                r["date"][:10] if r.get("date") else "",
                f"{icon} {display_type}",
                f"{r.get('km', ''):,.0f}" if r.get("km") else "",
                f"{r.get('cost', 0):.2f}" if r.get("cost") else "0.00",
                r.get("service_provider", "") or "",
                (r.get("notes", "") or "")[:60],
            ))

        total_pages = max(1, (self._total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._page_lbl.config(text=iconed("maint.page_info", page=self._page + 1, other=total_pages, total=self._total))

    def _next_page(self):
        total_pages = max(1, (self._total + PAGE_SIZE - 1) // PAGE_SIZE)
        if self._page < total_pages - 1:
            self._page += 1
            self._load_records()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._load_records()

    def _apply_preset_filter(self, maint_type):
        self.c_filter.set(maint_type.value)
        self._page = 0
        self._load_records()

    def _clear_preset_filter(self):
        self.c_filter.set("")
        self._page = 0
        self._load_records()

    def _add_record_win(self):
        self._record_form(title=iconed("maint.form_title_add"))

    def _edit_record(self):
        sel = self.tree.selection()
        if not sel:
            return
        rid = int(sel[0])
        record = self.service.get_records(truck_id=self.truck_id, limit=1000)
        record = next((r for r in record if r["id"] == rid), None)
        if record:
            self._record_form(title=iconed("maint.form_title_edit"), record=record)

    def _record_form(self, title="", record=None):
        win = ctk.CTkToplevel(self.win)
        win.title(title)
        win.geometry("550x500")
        win.configure(fg_color=Theme.BG)
        Theme.apply(win)

        f = ctk.CTkFrame(win, fg_color=Theme.BG)
        f.pack(fill="both", expand=True)

        fields = {}

        def add_row(label):
            r = ctk.CTkFrame(f, fg_color=Theme.BG)
            r.pack(fill="x", pady=4)
            ctk.CTkLabel(r, text=label, fg_color=Theme.BG, text_color=Theme.MUTED,
                     font=FONTS["label"], width=18, anchor="w").pack(side="left")
            e = StyledEntry(r)
            e.pack(side="left", fill="x", expand=True)
            return e

        type_opts = [mt.value for mt in MaintType]

        presets_row = ctk.CTkFrame(f, fg_color=Theme.BG)
        presets_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(presets_row, text=iconed("maint.form_quick"), fg_color=Theme.BG, text_color=Theme.MUTED,
                 font=FONTS["label"], width=18, anchor="w").pack(side="left")
        for label_key, mt, color in PRESETS:
            ctk.CTkButton(presets_row, text=t(label_key), fg_color=color, text_color="white",
                      font=FONTS["label"],
                      command=lambda m=mt: self._form_type_combo.set(m.value)).pack(side="left", padx=2)

        r = ctk.CTkFrame(f, fg_color=Theme.BG)
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=iconed("maint.form_type"), fg_color=Theme.BG, text_color=Theme.MUTED,
                 font=FONTS["label"], width=18, anchor="w").pack(side="left")
        self._form_type_combo = ctk.CTkComboBox(r, values=type_opts, width=28)
        self._form_type_combo.pack(side="left")
        if record:
            self._form_type_combo.set(record["maintenance_type"])
        else:
            self._form_type_combo.set(MaintType.OIL_CHANGE.value)

        fields["date"] = add_row(iconed("maint.form_date"))
        fields["date"].insert(0, record["date"][:10] if record and record.get("date") else datetime.now().strftime("%Y-%m-%d"))

        fields["km"] = add_row(iconed("maint.form_km"))
        if record and record.get("km"):
            fields["km"].insert(0, str(record["km"]))

        fields["cost"] = add_row(iconed("maint.form_cost"))
        if record and record.get("cost"):
            fields["cost"].insert(0, str(record["cost"]))

        fields["provider"] = add_row(iconed("maint.form_provider"))
        if record and record.get("service_provider"):
            fields["provider"].insert(0, record["service_provider"])

        fields["notes"] = add_row(iconed("maint.form_notes"))
        if record and record.get("notes"):
            fields["notes"].insert(0, record["notes"])

        def save():
            try:
                mt = self._form_type_combo.get()
                date = fields["date"].get().strip()
                km = float(fields["km"].get().strip()) if fields["km"].get().strip() else None
                cost = float(fields["cost"].get().strip()) if fields["cost"].get().strip() else None
                provider = fields["provider"].get().strip()
                notes = fields["notes"].get().strip()

                if record:
                    self.service.update_record(
                        record["id"], mt, date, km, cost, provider, notes,
                    )
                else:
                    self.service.add_record(self.truck_id, mt, date, km, cost, notes, provider)
                win.destroy()
                self._load_records()
                if self.on_change:
                    self.on_change()
            except Exception as e:
                messagebox.showerror(iconed("maint.error_generic"), str(e))

        ActionButton(f, iconed("maint.save"), save, color=Theme.ACCENT_SUCCESS).pack(fill="x", pady=8)
        ActionButton(f, iconed("maint.cancel"), win.destroy, color=Theme.SURFACE2).pack(fill="x")

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        if messagebox.askyesno(iconed("maint.confirm_delete_title"), iconed("maint.confirm_delete_msg", sel[0])):
            self.service.delete_record(int(sel[0]))
            self._load_records()
            if self.on_change:
                self.on_change()

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title=iconed("maint.export_title"),
        )
        if not path:
            return
        try:
            ft = self.c_filter.get() or None
            all_records = self.service.get_records(
                truck_id=self.truck_id, maint_type=ft, limit=10000, offset=0
            )
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([iconed("maint.col_date"), iconed("maint.col_type"), iconed("maint.col_km"), iconed("maint.col_cost"), iconed("maint.col_provider"), iconed("maint.col_notes")])
                for r in all_records:
                    writer.writerow([
                        r.get("date", ""),
                        r.get("maintenance_type", ""),
                        r.get("km", ""),
                        r.get("cost", ""),
                        r.get("service_provider", ""),
                        r.get("notes", ""),
                    ])
            messagebox.showinfo(iconed("maint.export_title"), iconed("maint.export_success", path))
        except Exception as e:
            messagebox.showerror(iconed("maint.error_generic"), str(e))
