import tkinter as tk
from tkinter import ttk, messagebox
import os
from datetime import datetime, timedelta
from services.i18n import t, register_listener, unregister_listener
from ui.styles import Theme
from ui.widgets import ActionButton, StyledEntry
from services.export_service import ExportService
from services.invoicing.generator import InvoiceGenerator
from services.email_service import EmailService

class HistoryView:
    def __init__(self, parent, db, main_app, prefs=None):
        self.win = tk.Toplevel(parent)
        self.win.title(f"📋 {t('history.title')}")
        self.win.geometry("1350x750")
        Theme.apply(self.win)

        self.db = db
        self.main_app = main_app
        from services.preferences import PreferencesManager
        self.prefs = prefs or PreferencesManager(db)

        self.exporter = ExportService(prefs=self.prefs)
        self.invoice_service = InvoiceGenerator()
        self.email_service = EmailService(self.db)
        
        self._i18n_widgets = []
        self._tree_heading_keys = []
        
        self._setup_ui()
        self.refresh()

        self.win.bind("<Destroy>", self._on_destroy)
        register_listener(self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_destroy(self, event=None):
        if event is not None and event.widget != self.win:
            return
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
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
        f_top = tk.Frame(self.win, bg=Theme.SURFACE, pady=15, padx=20)
        f_top.pack(fill="x")

        lbl = tk.Label(f_top, text=f"🔍 {t('history.search_label')}", bg=Theme.SURFACE, fg=Theme.TEXT)
        lbl.pack(side="left")
        self._i18n_tag(lbl, "history.search_label", "🔍 ")
        self.e_search = StyledEntry(f_top, width=20)
        self.e_search.pack(side="left", padx=5)
        self.e_search.bind("<KeyRelease>", lambda e: self.refresh())

        self.c_status = ttk.Combobox(f_top, values=t("history.status_filter"), state="readonly", width=12)
        self.c_status.pack(side="left", padx=10)
        self.c_status.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        btn = ActionButton(f_top, t("history.reset_button"), self._reset, color=Theme.SURFACE2)
        btn.pack(side="left")
        self._i18n_tag(btn, "history.reset_button")

        f_table = tk.Frame(self.win, bg=Theme.BG)
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
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        self.tree.tag_configure('Planned', foreground=Theme.MUTED)
        self.tree.tag_configure('Loading', foreground=Theme.ORANGE)
        self.tree.tag_configure('In Transit', foreground=Theme.INFO)
        self.tree.tag_configure('Delivered', foreground=Theme.SUCCESS)
        self.tree.tag_configure('Invoiced', foreground=Theme.ACCENT)
        self.tree.tag_configure('Paid', foreground=Theme.GREEN, font=('Segoe UI', 9, 'bold'))

        sb = ttk.Scrollbar(f_table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        f_btns = tk.Frame(self.win, bg=Theme.BG, padx=20, pady=20)
        f_btns.pack(fill="x")
        
        btn = ActionButton(f_btns, f"🔄 {t('history.button_status')}", self._change_status, color=Theme.ORANGE)
        btn.pack(side="left", padx=5)
        self._i18n_tag(btn, "history.button_status", "🔄 ")
        btn = ActionButton(f_btns, f"✏️ {t('history.button_edit')}", self._edit, color=Theme.SURFACE2)
        btn.pack(side="left", padx=5)
        self._i18n_tag(btn, "history.button_edit", "✏️ ")
        btn = ActionButton(f_btns, f"🗺️ {t('history.button_view_route')}", self._view_route, color=Theme.INFO)
        btn.pack(side="left", padx=5)
        self._i18n_tag(btn, "history.button_view_route", "🗺️ ")
        
        tk.Frame(f_btns, bg=Theme.BORDER, width=2).pack(side="left", fill="y", padx=10)
        
        btn = ActionButton(f_btns, f"🧾 {t('history.button_invoice')}", self._generate_invoice, color=Theme.ACCENT)
        btn.pack(side="left", padx=5)
        self._i18n_tag(btn, "history.button_invoice", "🧾 ")
        btn = ActionButton(f_btns, f"📧 {t('history.button_email')}", self._send_invoice_email, color=Theme.ORANGE)
        btn.pack(side="left", padx=5)
        self._i18n_tag(btn, "history.button_email", "📧 ")
        
        tk.Frame(f_btns, bg=Theme.BORDER, width=2).pack(side="left", fill="y", padx=10)
        
        btn = ActionButton(f_btns, f"📄 {t('history.button_pdf')}", self._export_pdf, color=Theme.GREEN)
        btn.pack(side="left", padx=5)
        self._i18n_tag(btn, "history.button_pdf", "📄 ")
        btn = ActionButton(f_btns, f"📊 {t('history.button_excel')}", self._export_excel, color=Theme.EXCEL)
        btn.pack(side="left", padx=5)
        self._i18n_tag(btn, "history.button_excel", "📊 ")
        
        btn = ActionButton(f_btns, f"🗑️ {t('history.button_delete')}", self._delete, color=Theme.DANGER)
        btn.pack(side="right")
        self._i18n_tag(btn, "history.button_delete", "🗑️ ")

    def refresh(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        trips = self.db.get_filtered_trips(self.e_search.get(), status=self.c_status.get())
        for t in trips:
            s = t["status"]
            self.tree.insert("", "end", values=(t["id"], t["created_at"][:10], t["truck_number"], t["driver_name"], t["client_name"], t["distance_km"], f"{t['gross_per_km']:.2f}", f"{t['net_profit']:.2f}", s), tags=(s,))

    def _get_selection(self):
        sel = self.tree.selection()
        return self.tree.item(sel[0])['values'] if sel else None

    def _reset(self):
        self.e_search.delete(0, tk.END); self.c_status.set(""); self.refresh()

    def _change_status(self):
        data = self._get_selection()
        if not data: return
        sw = tk.Toplevel(self.win); sw.title(t("history.update_status_title")); sw.geometry("250x350"); Theme.apply(sw); sw.configure(padx=20, pady=20)
        for s in t("history.status_options"):
            def cmd(val=s):
                if val == 'Paid': self.db.mark_invoice_as_paid(data[0])
                else: self.db.update_status(data[0], val)
                self.refresh(); sw.destroy()
            ActionButton(sw, s, cmd, color=Theme.SURFACE).pack(fill="x", pady=2)

    def _generate_invoice(self):
        data = self._get_selection()
        if not data: return
        try:
            trip_data = self.db.get_trip_by_id(data[0])
            path = self.invoice_service.generate(trip_data, mode="client")
            due_date = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")
            self.db.create_invoice_record(data[0], f"INV-{data[0]}", trip_data['total_price_eur'], due_date)
            if os.path.exists(path): self.refresh(); os.startfile(path)
        except Exception as e: messagebox.showerror(t("history.error_title"), str(e))

    def _export_pdf(self):
        try:
            trips = self.db.get_filtered_trips(self.e_search.get(), status=self.c_status.get())
            if not trips:
                messagebox.showwarning(t("history.warning_title"), t("history.no_export_data"))
                return
            path = self.exporter.generate_pdf(trips)
            if os.path.exists(path): os.startfile(path)
        except Exception as e: messagebox.showerror(t("history.error_pdf"), str(e))

    def _export_excel(self):
        try:
            trips = self.db.get_filtered_trips(self.e_search.get(), status=self.c_status.get())
            if not trips: return
            path = self.exporter.generate_excel(trips)
            if os.path.exists(path): os.startfile(path)
        except Exception as e: messagebox.showerror(t("history.error_excel"), str(e))

    def _send_invoice_email(self):
            data = self._get_selection()
            if not data:
                messagebox.showwarning(t("history.warning_title"), t("history.select_trip_first"))
                return
        
            from tkinter import simpledialog
        
            recipient = simpledialog.askstring(t("history.email_recipient_title"), t("history.email_recipient_msg"), parent=self.win)
        
            if not recipient:
                return

            try:
                trip_data = self.db.get_trip_by_id(data[0])
                path = self.invoice_service.generate(trip_data, mode="client")
            
                from services.invoicing.config_manager import load_company_config
                conf = load_company_config()

                subj, body = self.email_service.get_template("invoice", {
                    "invoice_number": f"INV-{data[0]}",
                    "company_name": conf.get('company_name', 'Firma Noastra'),
                    "truck_number": trip_data['truck_number'],
                    "amount": trip_data['total_price_eur'],
                    "due_date": (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y"),
                })
            
                self.email_service.send_email(data[0], recipient, subj, body, attachment_path=path)
                messagebox.showinfo(t("history.email_success").format(recipient), t("history.email_success").format(recipient))
            
            except Exception as e:
                messagebox.showerror(t("history.email_error").format(''), t("history.email_error").format(str(e)))

    def _edit(self):
        data = self._get_selection()
        if data:
            from ui.edit_window import EditWindow
            EditWindow(self.win, self.db, data[0], self.refresh)

    def _view_route(self):
        data = self._get_selection()
        if not data:
            messagebox.showwarning(t("history.warning_title"), t("history.select_trip_first"))
            return
        trip = self.db.get_trip_by_id(data[0])
        route_id = trip.get('route_history_v2_id') if trip else None
        if not route_id:
            messagebox.showinfo(t("history.warning_title"), t("history.no_route_linked"))
            return
        from services.route_history_service import RouteHistoryService
        svc = RouteHistoryService(self.db)
        record = svc.get_route(route_id)
        if not record:
            messagebox.showerror(t("history.error_title"), t("history.route_not_found"))
            return
        from ui.route_planner import RoutePlannerTab
        tab = RoutePlannerTab(self.win, self.db, controller=self.main_app)
        tab.load_history_route(record, draw=True)

    def _duplicate(self):
        data = self._get_selection()
        if data:
            old = self.db.get_trip_by_id(data[0])
            if 'id' in old: del old['id']
            old['created_at'] = self.main_app.get_timestamp()
            old['status'] = 'Planned'
            self.db.add_trip(old); self.refresh()

    def _delete(self):
        data = self._get_selection()
        if data and messagebox.askyesno(t("history.confirm_delete_title"), t("history.confirm_delete_msg")):
            self.db.delete_trip(data[0]); self.refresh()
