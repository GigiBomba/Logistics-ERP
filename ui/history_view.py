import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox, simpledialog
import os
from datetime import datetime, timedelta
from services.i18n import t
from services.app_state import AppState
from ui.styles import Theme
from ui.widgets import ActionButton, StyledEntry
from services.export_service import ExportService
from services.trip_service import TripService
from services.invoicing.service import InvoiceService
from ui.theme import COLORS, FONTS
from services.preferences import PreferencesManager

class HistoryView:
    def __init__(self, parent, db, main_app=None, controller=None, prefs=None, ops=None, embedded=False):
        # Accept both `main_app` and `controller` keywords for compatibility with view_map entries
        if embedded:
            self.win = None
            self.frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)
            top_parent = self.frame
        else:
            self.win = ctk.CTkToplevel(parent)
            self.win.configure(fg_color=Theme.BG)
            self.win.title(f"📋 {t('history.title')}")
            self.win.geometry("1350x750")
            Theme.apply(self.win)
            self.frame = ctk.CTkFrame(self.win, fg_color=Theme.SURFACE)
            self.frame.pack(fill="both", expand=True)
            top_parent = self.win

        self.db = db
        # prefer explicit main_app, fall back to controller if provided
        self.main_app = main_app or controller
        self.ops = ops
        self.prefs = prefs or PreferencesManager(db)

        self.trip_service = TripService(db)
        self.invoice_service = InvoiceService(db, prefs=self.prefs)
        self.exporter = ExportService(prefs=self.prefs)
        
        self._i18n_widgets = []
        self._tree_heading_keys = []
        self._app_state = AppState()
        self._limit = 200
        
        self._setup_ui()
        self.refresh()

        if self.win:
            self.win.bind("<Destroy>", self._on_destroy)
        self._app_state.subscribe("language", self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_destroy(self, event=None):
        if event is not None and event.widget != (self.win or self.frame):
            return
        self._app_state.unsubscribe("language", self._on_language_changed)

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
        if self.win:
            if self.win:
                self.win.title(f"📋 {t('history.title')}")
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
        self.c_status.configure(values=t("history.status_filter"))
        self.c_status.set("")

    def _setup_ui(self):
        parent = self.frame if self.win is None else self.win

        f_top = ctk.CTkFrame(parent, fg_color=Theme.SURFACE)
        f_top.pack(fill="x")

        lbl = ctk.CTkLabel(f_top, text=f"🔍 {t('history.search_label')}", fg_color=Theme.SURFACE, text_color=Theme.TEXT)
        lbl.pack(side="left")
        self._i18n_tag(lbl, "history.search_label", "🔍 ")
        self.e_search = StyledEntry(f_top, width=20)
        self.e_search.pack(side="left", padx=5)
        self.e_search.bind("<KeyRelease>", lambda e: self.refresh())

        self.c_status = ctk.CTkComboBox(f_top, values=t("history.status_filter"), state="readonly", width=12, command=self._on_status_filter_changed)
        self.c_status.pack(side="left", padx=10)

        btn = ActionButton(f_top, t("history.reset_button"), self._reset, color=Theme.SURFACE2)
        btn.pack(side="left")
        self._i18n_tag(btn, "history.reset_button")

        self._count_lbl = ctk.CTkLabel(f_top, text="", fg_color=Theme.SURFACE, text_color=Theme.MUTED, font=FONTS["label"])
        self._count_lbl.pack(side="left", padx=10)

        load_more_btn = ActionButton(f_top, f"⬇ {t('history.button_load_more')}", self._load_more, color=Theme.SURFACE2)
        load_more_btn.pack(side="left")
        self._i18n_tag(load_more_btn, "history.button_load_more", "⬇ ")

        f_table = ctk.CTkFrame(parent, fg_color=Theme.BG)
        f_table.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("ID", "Data", "Camion", "Șofer", "Client", "KM", "Brut/km", "Profit", "Status")
        headers_map = {
            "ID": t("history.table_id"),
            "Data": t("history.table_date"),
            "Camion": t("history.table_truck"),
            "Șofer": t("history.table_driver"),
            "Client": t("history.table_client"),
            "KM": t("history.table_km"),
            "Brut/km": t("history.table_gross_per_km"),
            "Profit": t("history.table_profit"),
            "Status": t("history.table_status"),
        }
        heading_keys = {
            "ID": "history.table_id",
            "Data": "history.table_date",
            "Camion": "history.table_truck",
            "Șofer": "history.table_driver",
            "Client": "history.table_client",
            "KM": "history.table_km",
            "Brut/km": "history.table_gross_per_km",
            "Profit": "history.table_profit",
            "Status": "history.table_status",
        }
        self.tree = ttk.Treeview(f_table, columns=cols, show="headings", selectmode="browse")
        for c in cols: 
            self.tree.heading(c, text=headers_map.get(c, c))
            self.tree.column(c, width=100, anchor="center")
            self._tree_heading_keys.append((c, heading_keys[c]))
        
        # Status color tags — valid transitions from OperationsEngine
        _STATUS_TAGS = {
            "Planificat": COLORS["info"],
            "Planified": COLORS["info"],
            "Planned": COLORS["info"],
            "Încărcare": COLORS["warning"],
            "Loading": COLORS["warning"],
            "În tranzit": COLORS["accent"],
            "In Transit": COLORS["accent"],
            "Livrat": COLORS["success"],
            "Delivered": COLORS["success"],
            "Facturat": COLORS["warning"],
            "Invoiced": COLORS["warning"],
            "Plătit": COLORS["success"],
            "Paid": COLORS["success"],
            "Arhivat": COLORS["text_muted"],
            "Archived": COLORS["text_muted"],
        }
        for s, color in _STATUS_TAGS.items():
            self.tree.tag_configure(s, foreground=color, font=FONTS["label"])

        self.tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(f_table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        f_btns = ctk.CTkFrame(parent, fg_color=Theme.BG)
        f_btns.pack(fill="x")
        
        btn = ActionButton(f_btns, f"🗺️ {t('history.button_view_route')}", self._view_route, color=Theme.INFO)
        btn.pack(side="left", padx=5)
        self._i18n_tag(btn, "history.button_view_route", "🗺️ ")
        
        ctk.CTkFrame(f_btns, fg_color=Theme.BORDER, width=2).pack(side="left", fill="y", padx=10)
        
        btn = ActionButton(f_btns, f"🧾 {t('history.button_invoice')}", self._generate_invoice, color=Theme.ACCENT)
        btn.pack(side="left", padx=5)
        self._i18n_tag(btn, "history.button_invoice", "🧾 ")
        btn = ActionButton(f_btns, f"📧 {t('history.button_email')}", self._send_invoice_email, color=Theme.ORANGE)
        btn.pack(side="left", padx=5)
        self._i18n_tag(btn, "history.button_email", "📧 ")
        
        ctk.CTkFrame(f_btns, fg_color=Theme.BORDER, width=2).pack(side="left", fill="y", padx=10)
        
        btn = ActionButton(f_btns, f"📄 {t('history.button_pdf')}", self._export_pdf, color=Theme.GREEN)
        btn.pack(side="left", padx=5)
        self._i18n_tag(btn, "history.button_pdf", "📄 ")
        btn = ActionButton(f_btns, f"📊 {t('history.button_excel')}", self._export_excel, color=Theme.EXCEL)
        btn.pack(side="left", padx=5)
        self._i18n_tag(btn, "history.button_excel", "📊 ")
        
        btn = ActionButton(f_btns, f"🗑️ {t('history.button_delete')}", self._delete, color=Theme.DANGER)
        btn.pack(side="right")
        self._i18n_tag(btn, "history.button_delete", "🗑️ ")

    def _on_status_filter_changed(self, value):
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        trips = self.trip_service.get_filtered(self.e_search.get(), status=self.c_status.get(), limit=self._limit)
        for trip in trips:
            s = trip["status"]
            self.tree.insert("", "end", values=(trip["id"], trip["created_at"][:10], trip["truck_number"], trip["driver_name"], trip["client_name"], trip["distance_km"], f"{trip['gross_per_km']:.2f}", f"{trip['net_profit']:.2f}", s), tags=(s,))
        self._count_lbl.configure(text=f" ({len(trips)} / {self._limit})")

    def _load_more(self):
        self._limit *= 2
        self.refresh()

    def _get_selection(self):
        sel = self.tree.selection()
        return self.tree.item(sel[0])['values'] if sel else None

    def _reset(self):
        self.e_search.delete(0, tk.END); self.c_status.set(""); self._limit = 200; self.refresh()

    def _generate_invoice(self):
        data = self._get_selection()
        if not data: return
        try:
            trip_data = self.trip_service.get_by_id(data[0])
            path = self.invoice_service.generate(trip_data, mode="client")
            due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            self.invoice_service.create_record(data[0], f"INV-{data[0]}", trip_data.get('total_price_eur', 0), due_date)
            if os.path.exists(path): self.refresh(); os.startfile(path)
        except Exception as e: messagebox.showerror(t("history.error_title"), str(e))

    def _export_pdf(self):
        try:
            trips = self.trip_service.get_filtered(self.e_search.get(), status=self.c_status.get())
            if not trips:
                messagebox.showwarning(t("history.warning_title"), t("history.no_export_data"))
                return
            path = self.exporter.generate_pdf(trips)
            if os.path.exists(path): os.startfile(path)
        except Exception as e: messagebox.showerror(t("history.error_pdf"), str(e))

    def _export_excel(self):
        try:
            trips = self.trip_service.get_filtered(self.e_search.get(), status=self.c_status.get())
            if not trips: return
            path = self.exporter.generate_excel(trips)
            if os.path.exists(path): os.startfile(path)
        except Exception as e: messagebox.showerror(t("history.error_excel"), str(e))

    def _send_invoice_email(self):
        data = self._get_selection()
        if not data:
            messagebox.showwarning(t("history.warning_title"), t("history.select_trip_first"))
            return

        trip_id = data[0]
        trip_data = self.trip_service.get_by_id(trip_id)
        if not trip_data:
            messagebox.showerror(t("history.error_title"), t("history.email_error").format("trip not found"))
            return

        recipient = simpledialog.askstring(
            t("history.email_recipient_title"),
            t("history.email_recipient_msg"),
            parent=self.win or self.frame
        )
        if not recipient:
            return

        try:
            ok = self.invoice_service.send_invoice_email(
                trip_id=trip_id,
                recipient=recipient,
                smtp_config=self.prefs.get_smtp_config(),
                trip_data=trip_data,
                mode="client",
            )
            if ok:
                messagebox.showinfo(t("history.button_email"),
                                  t("history.email_success").format(recipient))
                self.refresh()
            else:
                messagebox.showerror(t("history.email_error"),
                                   t("history.email_error").format("SMTP send failed"))
        except ValueError as e:
            messagebox.showerror(t("history.email_error"), str(e))
        except Exception as e:
            messagebox.showerror(t("history.email_error"), f"Failed to send invoice: {e}")

    def _view_route(self):
        data = self._get_selection()
        if not data:
            messagebox.showwarning(t("history.warning_title"), t("history.select_trip_first"))
            return
        trip = self.trip_service.get_by_id(data[0])
        route_id = trip.get('route_history_v2_id') if trip else None
        if not route_id:
            messagebox.showinfo(t("history.warning_title"), t("history.no_route_linked"))
            return
        from services.route_history_service import RouteHistoryService
        svc = RouteHistoryService(self.db)
        record = svc.load_route(route_id)
        if not record:
            messagebox.showerror(t("history.error_title"), t("history.route_not_found"))
            return
        from ui.route_planner import RoutePlannerTab
        tab = RoutePlannerTab(self.win or self.frame, self.db, controller=self.main_app)
        tab.load_history_route(record, draw=True)

    def _delete(self):
        data = self._get_selection()
        if data and messagebox.askyesno(t("history.confirm_delete_title"), t("history.confirm_delete_msg")):
            self.trip_service.delete(data[0]); self.refresh()
