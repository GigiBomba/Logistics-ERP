import csv
import logging
import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from services.i18n import t, register_listener, unregister_listener
from services.operations.event_bus import EventBus, DRIVER_CREATED, DRIVER_UPDATED, DRIVER_DELETED, TRUCK_UPDATED
from services.driver_truck_service import DriverTruckService
from ui.styles import Theme
from ui.widgets import ActionButton, StyledEntry, kpi_card
from ui.dialogs.driver_form import DriverFormDialog
from ui.theme import FONTS
from repositories.driver_repository import DriverRepository
from repositories.trip_repository import TripRepository

logger = logging.getLogger(__name__)


class DriverManager:

    def __init__(self, parent, db, open_window=True, ops=None):
        self.parent = parent
        self.db = db
        self.ops = ops
        self._event_bus = EventBus()
        self._driver_repo = DriverRepository(db)
        self._trip_repo = TripRepository(db)
        self._dta_service = DriverTruckService(db)

        self._i18n_widgets = []
        self._tree_heading_keys = []
        self._kpi_title_refs = []

        if open_window:
            self.win = ctk.CTkToplevel(parent)
            self.win.configure(fg_color=Theme.BG)
            self.win.title(t("driver_manager.title"))
            self.win.geometry("1000x650")
            Theme.apply(self.win)
            self.frame = ctk.CTkFrame(self.win, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)
        else:
            self.win = None
            self.frame = ctk.CTkFrame(parent, fg_color=Theme.BG)

        self._setup_ui()
        self.refresh()

        self.frame.bind("<Destroy>", self._on_destroy)
        self._event_bus.subscribe(TRUCK_UPDATED, self._on_truck_updated)
        register_listener(self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_destroy(self, event=None):
        if event is not None and event.widget != self.frame:
            return
        self._event_bus.unsubscribe(TRUCK_UPDATED, self._on_truck_updated)
        unregister_listener(self._on_language_changed)

    def _on_truck_updated(self, ev):
        try:
            self.frame.after(0, self.refresh)
        except Exception:
            pass

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
        if self.win is not None:
            self.win.title(t("driver_manager.title"))
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.config(text=f"{prefix}{t(key)}")
            except Exception:
                pass
        for col, key in self._tree_heading_keys:
            try:
                self.tree.heading(col, text=t(key))
            except Exception:
                pass
        for lbl, k in self._kpi_title_refs:
            try:
                lbl.config(text=t(k))
            except Exception:
                pass
        self.refresh()

    def _setup_ui(self):
        header = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        header.pack(fill="x", padx=12, pady=(8, 4))

        lbl = ctk.CTkLabel(header, text=t("driver_manager.title"), fg_color=Theme.BG,
                      text_color=Theme.ACCENT, font=Theme.FONT_TITLE)
        lbl.pack(side="left")
        self._i18n_tag(lbl, "driver_manager.title")

        ex_f = ctk.CTkFrame(header, fg_color=Theme.BG)
        ex_f.pack(side="right")
        btn = ActionButton(ex_f, t("driver_manager.export_csv"), self._export_csv, color=Theme.SURFACE2)
        btn.pack(side="right", padx=6)
        self._i18n_tag(btn, "driver_manager.export_csv")

        kpi_cont = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        kpi_cont.pack(fill="x", padx=12)

        self.kpi_total_val, kpi_total_lbl = kpi_card(kpi_cont, t("driver_manager.kpi_total"), "0")
        self._kpi_title_refs.append((kpi_total_lbl, "driver_manager.kpi_total"))
        self.kpi_expiring_val, kpi_expiring_lbl = kpi_card(kpi_cont, t("driver_manager.kpi_expiring"), "0")
        self._kpi_title_refs.append((kpi_expiring_lbl, "driver_manager.kpi_expiring"))
        self.kpi_on_trip_val, kpi_on_trip_lbl = kpi_card(kpi_cont, t("driver_manager.kpi_on_trip"), "0")
        self._kpi_title_refs.append((kpi_on_trip_lbl, "driver_manager.kpi_on_trip"))
        self.kpi_unassigned_val, kpi_unassigned_lbl = kpi_card(kpi_cont, t("driver_manager.kpi_unassigned"), "0")
        self._kpi_title_refs.append((kpi_unassigned_lbl, "driver_manager.kpi_unassigned"))

        search_f = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        search_f.pack(fill="x", padx=12, pady=(0, 6))
        lbl = ctk.CTkLabel(search_f, text=t("driver_manager.search_placeholder"), fg_color=Theme.BG, text_color=Theme.TEXT)
        lbl.pack(side="left")
        self._i18n_tag(lbl, "driver_manager.search_placeholder")
        self.e_search = StyledEntry(search_f)
        self.e_search.pack(side="left", fill="x", expand=True, padx=(8, 6))
        self.e_search.bind("<KeyRelease>", lambda e: self._filter_tree())

        table_f = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        table_f.pack(fill="both", expand=True, padx=12)

        cols = ("id", "name", "phone", "license", "license_exp", "medical_exp", "hire_date", "salary", "active", "truck")
        headings = (
            t("driver_manager.col_id"), t("driver_manager.col_name"), t("driver_manager.col_phone"),
            t("driver_manager.col_license"), t("driver_manager.col_license_expiry"),
            t("driver_manager.col_medical_expiry"), t("driver_manager.col_hire_date"),
            t("driver_manager.col_salary"), t("driver_manager.col_active"), t("driver_manager.col_truck")
        )
        heading_keys = [
            "driver_manager.col_id", "driver_manager.col_name", "driver_manager.col_phone",
            "driver_manager.col_license", "driver_manager.col_license_expiry",
            "driver_manager.col_medical_expiry", "driver_manager.col_hire_date",
            "driver_manager.col_salary", "driver_manager.col_active", "driver_manager.col_truck"
        ]

        self.tree = ttk.Treeview(table_f, columns=cols, show="headings")
        for c, h, k in zip(cols, headings, heading_keys):
            self.tree.heading(c, text=h)
            width = 120 if c in ("name", "license", "truck") else 90
            self.tree.column(c, width=width, anchor="center")
            self._tree_heading_keys.append((c, k))
        self.tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(table_f, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda e: self._edit_selected())
        self.tree.bind("<Button-3>", self._context_menu)

        btns = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        btns.pack(fill="x", padx=12)
        btn = ActionButton(btns, f"+ {t('driver_manager.add_driver')}", self._add_driver, color=Theme.ACCENT_SUCCESS)
        btn.pack(side="left", padx=6)
        self._i18n_tag(btn, "driver_manager.add_driver", "+ ")
        btn = ActionButton(btns, t("driver_manager.edit_driver"), self._edit_selected, color=Theme.ACCENT)
        btn.pack(side="left", padx=6)
        self._i18n_tag(btn, "driver_manager.edit_driver")
        btn = ActionButton(btns, t("driver_manager.delete_driver"), self._delete_selected, color=Theme.DANGER)
        btn.pack(side="right", padx=6)
        self._i18n_tag(btn, "driver_manager.delete_driver")

        # ── Tachograph detail panel (shows when driver selected) ──
        self._tacho_detail = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        self._tacho_detail.pack(fill="x", padx=12, pady=(8, 0))
        self._tacho_detail.pack_forget()

        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_driver_selected())

    def _get_selected_id_silent(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])["values"][0]

    def _on_driver_selected(self):
        driver_id = self._get_selected_id_silent()
        if not driver_id:
            self._tacho_detail.pack_forget()
            return
        self._show_driver_tacho_detail(int(driver_id))

    def _show_driver_tacho_detail(self, driver_id: int):
        for w in self._tacho_detail.winfo_children():
            w.destroy()
        self._tacho_detail.pack(fill="x", padx=12, pady=(8, 0))

        # Title
        ctk.CTkLabel(self._tacho_detail, text=t("tacho.driver_activity_title"),
                     fg_color=Theme.BG, text_color=Theme.ACCENT,
                     font=Theme.FONT_BOLD).pack(anchor="w")

        try:
            from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
            activity_repo = TachoDriverActivityRepository(self.db)
            from_date = datetime.now().date() - timedelta(days=28)
            records = activity_repo.get_by_driver(driver_id, from_date)
        except Exception:
            records = []

        if not records:
            ctk.CTkLabel(self._tacho_detail, text=t("tacho.no_activity"),
                         fg_color=Theme.BG, text_color=Theme.MUTED,
                         font=FONTS["small"]).pack(anchor="w", pady=4)
            return

        # Summary row
        total_driving = sum(r.get("driving_minutes", 0) or 0 for r in records)
        avg_daily = total_driving / 60 / len(records) if records else 0
        total_violations = sum(
            len(__import__("json").loads(r.get("violations") or "[]")) for r in records
        )

        summary = ctk.CTkFrame(self._tacho_detail, fg_color=Theme.SURFACE2)
        summary.pack(fill="x", pady=(4, 6))
        self._summary_chip(summary, t("tacho.total_hours"), f"{total_driving/60:.1f}h")
        self._summary_chip(summary, t("tacho.avg_daily"), f"{avg_daily:.1f}h")
        self._summary_chip(summary, t("tacho.violations"), str(total_violations),
                            color=Theme.DANGER if total_violations > 0 else Theme.SUCCESS)

        # Mini activity chart (last 14 days)
        chart_frame = ctk.CTkFrame(self._tacho_detail, fg_color=Theme.BG)
        chart_frame.pack(fill="x", pady=(4, 6))
        ctk.CTkLabel(chart_frame, text=t("tacho.last_14_days"),
                     fg_color=Theme.BG, text_color=Theme.MUTED,
                     font=FONTS["label"]).pack(anchor="w")

        last_14 = records[:14] if len(records) >= 14 else records
        bar_container = ctk.CTkFrame(chart_frame, fg_color=Theme.BG)
        bar_container.pack(fill="x", pady=(4, 0))
        for r in reversed(last_14):
            driving_h = (r.get("driving_minutes", 0) or 0) / 60
            if driving_h <= 9:
                bar_color = Theme.SUCCESS
            elif driving_h <= 10:
                bar_color = Theme.WARNING
            else:
                bar_color = Theme.DANGER
            h = min(int(driving_h * 6), 60)
            bar = tk.Canvas(bar_container, width=16, height=60, bg=Theme.BG,
                            highlightthickness=0)
            bar.pack(side="left", padx=1)
            bar.create_rectangle(2, 60 - h, 14, 60, fill=bar_color, outline="")
            date_str = str(r.get("activity_date", ""))[5:]  # mm-dd
            bar.create_text(8, 62, text=date_str, fill=Theme.MUTED,
                            font=("Segoe UI", 6), angle=90)

        # Last 5 violations
        violations = []
        for r in records:
            vlist = __import__("json").loads(r.get("violations") or "[]")
            for v in vlist:
                violations.append((r.get("activity_date", ""), v))
        if violations:
            ctk.CTkLabel(self._tacho_detail, text=t("tacho.recent_violations"),
                         fg_color=Theme.BG, text_color=Theme.MUTED,
                         font=FONTS["label"]).pack(anchor="w", pady=(4, 2))
            for date_str, v in violations[:5]:
                row = ctk.CTkFrame(self._tacho_detail, fg_color=Theme.SURFACE2)
                row.pack(fill="x", pady=1)
                ctk.CTkLabel(row, text=str(date_str),
                             fg_color=Theme.SURFACE2, text_color=Theme.MUTED,
                             font=FONTS["label"], width=90).pack(side="left", padx=4)
                ctk.CTkLabel(row, text=v,
                             fg_color=Theme.SURFACE2, text_color=Theme.DANGER,
                             font=FONTS["small"], wraplength=500).pack(side="left", padx=4)

    def _summary_chip(self, parent, label, value, color=None):
        chip = ctk.CTkFrame(parent, fg_color=Theme.SURFACE)
        chip.pack(side="left", padx=4, pady=2, fill="x", expand=True)
        ctk.CTkLabel(chip, text=label.upper(), fg_color=Theme.SURFACE,
                     text_color=Theme.MUTED, font=FONTS["label"]).pack(anchor="w", padx=4)
        ctk.CTkLabel(chip, text=value, fg_color=Theme.SURFACE,
                     text_color=color or Theme.TEXT, font=FONTS["small"]).pack(anchor="w", padx=4)

    def _context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            menu = tk.Menu(self.frame, tearoff=0, bg=Theme.SURFACE2, fg=Theme.TEXT)
            menu.add_command(label=t("driver_manager.edit_driver"), command=self._edit_selected)
            menu.add_command(label=t("driver_manager.toggle_active"), command=self._toggle_active)
            menu.add_separator()
            menu.add_command(label=t("driver_manager.delete_driver"), command=self._delete_selected)
            menu.tk_popup(event.x_root, event.y_root)

    def _get_selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(t("driver_manager.title"), t("driver_manager.no_driver_selected"))
            return None
        return self.tree.item(sel[0])["values"][0]

    def _get_selected_row(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])["values"]

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        try:
            drivers = self._driver_repo.get_all(limit=500)
            active_trips = self._trip_repo.get_by_statuses(["Loading", "In Transit"])

            driver_trip_ids = set()
            for trip in active_trips:
                did = trip.get("driver_id")
                if did:
                    driver_trip_ids.add(did)

            for d in drivers:
                did = d["id"]
                truck_text = self._dta_service.get_truck_plate_for_driver(did) or t("driver_manager.unassigned")

                self.tree.insert("", "end", values=(
                    did,
                    d.get("name", ""),
                    d.get("phone", ""),
                    d.get("license_category", ""),
                    d.get("license_expiry", ""),
                    d.get("medical_expiry", ""),
                    d.get("hire_date", ""),
                    f"{float(d.get('monthly_salary') or 0):.2f}",
                    t("common.yes") if d.get("is_active", 1) else t("common.no"),
                    truck_text,
                ))

            total = len(drivers)
            active = sum(1 for d in drivers if d.get("is_active", 1))
            self.kpi_total_val.config(text=str(total))
            self.kpi_on_trip_val.config(text=str(len(driver_trip_ids)))

            cutoff = datetime.now() + timedelta(days=30)
            expiring = 0
            for d in drivers:
                if d.get("is_active", 1):
                    for field in ("license_expiry", "medical_expiry"):
                        val = d.get(field, "")
                        if val:
                            try:
                                dt = datetime.strptime(val, "%Y-%m-%d")
                                if dt <= cutoff:
                                    expiring += 1
                                    break
                            except ValueError:
                                pass
            self.kpi_expiring_val.config(text=str(expiring))
            self.kpi_unassigned_val.config(text=str(total - active))

            self._filter_tree()
        except Exception as ex:
            logger.exception("refresh drivers failed")
            messagebox.showerror(t("main.error_title"), str(ex))

    def _filter_tree(self):
        query = self.e_search.get().strip().lower()
        for iid in self.tree.get_children():
            vals = [str(v).lower() for v in self.tree.item(iid)["values"]]
            visible = (query == "") or any(query in v for v in vals)
            if visible:
                try:
                    self.tree.reattach(iid, "", "end")
                except Exception:
                    pass
            else:
                try:
                    self.tree.detach(iid)
                except Exception:
                    pass

    def _add_driver(self):
        DriverFormDialog(self.frame, self._driver_repo, on_save=self.refresh,
                         dta_service=self._dta_service)

    def _edit_selected(self):
        driver_id = self._get_selected_id()
        if not driver_id:
            return
        row = self._driver_repo.get_by_id(driver_id)
        if not row:
            messagebox.showerror(t("driver_manager.title"), t("driver_manager.no_driver_selected"))
            return
        DriverFormDialog(self.frame, self._driver_repo, driver=row, on_save=self.refresh,
                         dta_service=self._dta_service)

    def _toggle_active(self):
        driver_id = self._get_selected_id()
        if not driver_id:
            return
        row = self._driver_repo.get_by_id(driver_id)
        if not row:
            return
        new_active = 0 if row.get("is_active", 1) else 1
        self._driver_repo.update(driver_id, {"is_active": new_active})
        self._event_bus.publish(DRIVER_UPDATED, {"driver_id": driver_id, "is_active": new_active})
        self.refresh()

    def _delete_selected(self):
        driver_id = self._get_selected_id()
        if not driver_id:
            return
        if not messagebox.askyesno(t("driver_manager.delete_driver"), t("driver_manager.confirm_delete")):
            return
        try:
            self._driver_repo.delete(driver_id)
            self._event_bus.publish(DRIVER_DELETED, {"driver_id": driver_id})
            self.refresh()
        except Exception as ex:
            messagebox.showerror(t("main.error_title"), str(ex))

    def _export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[(t("common.csv_filter"), "*.csv")])
        if not path:
            return
        try:
            drivers = self._driver_repo.get_all(limit=10000)
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow([t("common.id"), t("driver_manager.col_name"), t("driver_manager.col_phone"),
                            t("driver_manager.col_license"), t("driver_manager.col_license_expiry"),
                            t("driver_manager.col_medical_expiry"), t("driver_manager.col_hire_date"),
                            t("driver_manager.col_salary"), t("driver_manager.col_active")])
                for d in drivers:
                    w.writerow([
                        d.get("id"), d.get("name"), d.get("phone"), d.get("license_category"),
                        d.get("license_expiry"), d.get("medical_expiry"), d.get("hire_date"),
                        d.get("monthly_salary"), d.get("is_active")
                    ])
            messagebox.showinfo(t("driver_manager.export_csv"), t("driver_manager.export_success"))
        except Exception as ex:
            messagebox.showerror(t("main.error_title"), str(ex))
