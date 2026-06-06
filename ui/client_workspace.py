"""Client workspace — split-panel CRM layout replacing ClientManager."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import customtkinter as ctk
from typing import Any, Dict, List, Optional

from services.client_service import ClientService
from services.i18n import t, register_listener, unregister_listener
from ui.styles import Theme
from ui.widgets import StyledEntry, ActionButton
from ui.theme import FONTS, COLORS


class ClientWorkspace:
    """Embedded split-panel: client list (left) + detail (right)."""

    def __init__(self, parent, db, prefs=None):
        self.db = db
        self.service = ClientService(db)
        self._selected_id: Optional[int] = None
        self._search_user_typed = False
        self._all_clients: List[Dict[str, Any]] = []
        self._filter_inactive = False

        self.frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
        self.frame.pack(fill="both", expand=True)

        self._build_layout()
        self._load_data()
        register_listener(self._on_language_changed)
        self.frame.bind("<Destroy>", self._on_destroy)

    def _on_destroy(self, e=None):
        if e is not None and e.widget != self.frame:
            return
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        if not self._search_user_typed:
            self._search_entry.delete(0, "end")
            self._search_entry.insert(0, t("common.search"))
            self._search_entry.configure(text_color=COLORS["text_muted"])
        self._refresh_list()

    def _build_layout(self):
        paned = tk.PanedWindow(self.frame, orient="horizontal", bg=Theme.BG, sashwidth=2, sashpad=0)
        paned.pack(fill="both", expand=True)

        self._left = ctk.CTkFrame(paned, fg_color=Theme.BG, width=500)
        self._right = ctk.CTkFrame(paned, fg_color=Theme.BG, width=500)
        paned.add(self._left, stretch="always", minsize=300)
        paned.add(self._right, stretch="always", minsize=300)

        self._build_left_panel()
        self._build_right_placeholder()

    def _build_left_panel(self):
        top = ctk.CTkFrame(self._left, fg_color=Theme.SURFACE)
        top.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(top, text=t("client.title"), fg_color=Theme.SURFACE,
                     text_color=Theme.TEXT, font=FONTS["h2"]).pack(side="left", padx=10)

        self._search_entry = StyledEntry(top, width=140)
        self._search_entry.insert(0, t("common.search"))
        self._search_entry.configure(text_color=COLORS["text_muted"])
        self._search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self._search_entry.bind("<FocusOut>", self._on_search_focus_out)
        self._search_entry.bind("<KeyRelease>", lambda e: self._load_data())
        self._search_entry.pack(side="left", padx=5)

        self._inactive_btn = ActionButton(top, text=t("client.filter_active"),
                                          command=self._toggle_inactive,
                                          fg_color=Theme.SURFACE2, text_color=Theme.TEXT, width=30)
        self._inactive_btn.pack(side="left", padx=5)

        ActionButton(top, text="+ " + t("client.new_button"), command=self._open_form,
                     fg_color=Theme.ACCENT_PRIMARY, hover_color=Theme.ACCENT_SECONDARY,
                     text_color="#fff").pack(side="right", padx=10)

        tree_frame = ctk.CTkFrame(self._left, fg_color=Theme.BG)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

        cols = ("name", "trips", "revenue", "outstanding")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=20)
        self.tree.heading("name", text=t("client.table_name"))
        self.tree.heading("trips", text=t("client.table_trips"))
        self.tree.heading("revenue", text=t("client.table_revenue"))
        self.tree.heading("outstanding", text=t("client.table_outstanding"))
        self.tree.column("name", width=180, minwidth=100)
        self.tree.column("trips", width=55, anchor="center")
        self.tree.column("revenue", width=95, anchor="e")
        self.tree.column("outstanding", width=95, anchor="e")

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self._open_form(edit=True))

        btn_frame = ctk.CTkFrame(self._left, fg_color=Theme.BG)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        ActionButton(btn_frame, text=t("client.edit_button"), command=lambda: self._open_form(edit=True),
                     fg_color=Theme.ACCENT_PRIMARY, text_color="#fff").pack(side="left", padx=2)
        ActionButton(btn_frame, text=t("client.deactivate_button"), command=self._deactivate,
                     fg_color=Theme.DANGER, text_color="#fff").pack(side="left", padx=2)
        ActionButton(btn_frame, text=t("client.merge_button"), command=self._merge_clients,
                     fg_color=Theme.WARNING, text_color="#000").pack(side="left", padx=2)
        ActionButton(btn_frame, text=t("client.export_csv"), command=self._export_csv,
                     fg_color=Theme.GREEN, text_color="#fff").pack(side="right", padx=2)

    def _build_right_placeholder(self):
        self._detail_placeholder = ctk.CTkLabel(
            self._right, text=t("client.select_hint"),
            fg_color=Theme.BG, text_color=Theme.MUTED, font=FONTS["h3"],
            justify="center"
        )
        self._detail_placeholder.pack(expand=True)
        self._detail_frame = None
        self._detail_obj = None

    def _show_detail(self, client_id: int):
        if self._detail_frame:
            self._detail_frame.destroy()
            self._detail_frame = None
        self._detail_placeholder.pack_forget()

        self._detail_frame = ctk.CTkFrame(self._right, fg_color=Theme.BG)
        self._detail_frame.pack(fill="both", expand=True)
        self._detail_obj = _ClientDetailPanel(
            self._detail_frame, self.db, self.service, client_id,
            on_refresh_list=self._refresh_list
        )

    def _hide_detail(self):
        if self._detail_frame:
            self._detail_frame.destroy()
            self._detail_frame = None
            self._detail_obj = None
        self._detail_placeholder.pack(expand=True)

    def _on_search_focus_in(self, event):
        if self._search_entry.get() == t("common.search"):
            self._search_entry.delete(0, "end")
            self._search_entry.configure(text_color=Theme.TEXT)
        self._search_user_typed = True

    def _on_search_focus_out(self, event):
        if not self._search_entry.get().strip():
            self._search_entry.insert(0, t("common.search"))
            self._search_entry.configure(text_color=COLORS["text_muted"])
            self._search_user_typed = False

    def _toggle_inactive(self):
        self._filter_inactive = not self._filter_inactive
        self._inactive_btn.configure(
            fg_color=Theme.ACCENT_PRIMARY if self._filter_inactive else Theme.SURFACE2
        )
        self._load_data()

    def _load_data(self):
        query = (self._search_entry.get() or "").strip()
        if query == t("common.search"):
            query = ""
        if query:
            self._all_clients = self.service.search_advanced(
                query, include_inactive=self._filter_inactive, limit=200
            )
        else:
            self._all_clients = self.service.get_all_with_revenue(
                include_inactive=self._filter_inactive
            )
        self._refresh_list()

    def _refresh_list(self):
        prev_sel = self.tree.selection()
        prev_idx = self.tree.index(prev_sel[0]) if prev_sel else -1
        for item in self.tree.get_children():
            self.tree.delete(item)

        for c in self._all_clients:
            rev = c.get("total_revenue", 0) or 0
            outstanding = c.get("outstanding_balance", 0) or 0
            tag = "inactive" if not c.get("is_active", 1) else "active"
            self.tree.insert("", "end", values=(
                c.get("name", ""),
                c.get("trip_count", 0) or 0,
                f"{rev:,.0f} \u20ac",
                f"{outstanding:,.0f} \u20ac" if outstanding > 0 else "\u2014",
            ), tags=(tag,))

        self.tree.tag_configure("inactive", foreground=COLORS["text_muted"])
        self.tree.tag_configure("active", foreground=Theme.TEXT)

        if self._selected_id and self._detail_obj:
            self._show_detail(self._selected_id)
        elif prev_idx >= 0 and prev_idx < len(self._all_clients):
            self._selected_id = self._all_clients[prev_idx]["id"]
            self._show_detail(self._selected_id)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if 0 <= idx < len(self._all_clients):
            c = self._all_clients[idx]
            self._selected_id = c["id"]
            self._show_detail(self._selected_id)

    def _open_form(self, edit=False):
        if edit and not self._selected_id:
            return
        client = self.service.get_by_id(self._selected_id) if edit and self._selected_id else None
        _ClientFormDialog(self.frame, self.service, client_data=client, on_save=self._load_data)

    def _deactivate(self):
        if not self._selected_id:
            return
        client = self.service.get_by_id(self._selected_id)
        if not client:
            return
        count = self.service.get_trip_count(self._selected_id)
        msg = t("client.deactivate_confirm").format(name=client["name"])
        if count > 0:
            msg += t("client.deactivate_trips_warning").format(count=count)
        if messagebox.askyesno(t("common.confirm"), msg):
            self.service.deactivate(self._selected_id)
            self._hide_detail()
            self._selected_id = None
            self._load_data()

    def _merge_clients(self):
        if not self._selected_id:
            messagebox.showinfo(t("client.merge_title"), t("client.select_hint"))
            return
        _MergeDialog(self.frame, self.service, source_id=self._selected_id, on_done=self._load_data)

    def _export_csv(self):
        clients = self.service.get_all_with_revenue(include_inactive=self._filter_inactive)
        if not clients:
            messagebox.showinfo(t("common.info"), t("client.no_data_export"))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
            initialfile="clients_export.csv"
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Name", "Contact Person", "Phone", "Email", "VAT",
                             "City", "Type", "Total Revenue", "Trip Count", "Outstanding", "Active"])
            for c in clients:
                writer.writerow([
                    c.get("id", ""), c.get("name", ""), c.get("contact_person", ""),
                    c.get("phone", ""), c.get("email", ""), c.get("vat_number", ""),
                    c.get("address", ""), c.get("client_type", ""),
                    c.get("total_revenue", 0) or 0, c.get("trip_count", 0) or 0,
                    c.get("outstanding_balance", 0) or 0, c.get("is_active", 1),
                ])
        messagebox.showinfo(t("common.info"), t("client.csv_saved"))

    def wakeup(self):
        self._load_data()

    def shutdown(self):
        pass


class _ClientDetailPanel:
    """Right-panel detail view: profile + KPIs + contacts + chart + timeline + trips + invoices + tags + payment."""

    def __init__(self, parent, db, service: ClientService, client_id: int, on_refresh_list=None):
        self.db = db
        self.service = service
        self.client_id = client_id
        self._on_refresh_list = on_refresh_list
        self._chart_widget = None

        self.main = ctk.CTkScrollableFrame(parent, fg_color=Theme.BG,
                                           scrollbar_button_color=COLORS["border"])
        self.main.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        dash = self.service.get_client_dashboard(self.client_id)
        client = dash.get("client", {})
        contacts = dash.get("contacts", [])
        tags = dash.get("tags", [])

        self._build_profile_section(client, dash)
        self._build_kpi_section(dash)

        if contacts:
            self._build_contacts_section(contacts)

        self._build_tags_section(tags)

        try:
            self._build_revenue_chart()
        except Exception:
            pass

        self._build_trip_history(dash.get("recent_trips", []))
        self._build_invoice_section(dash)
        self._build_payment_summary()

        try:
            self._build_timeline()
        except Exception:
            pass

    def _build_profile_section(self, client, dash):
        section = ctk.CTkFrame(self.main, fg_color=Theme.SURFACE, corner_radius=10)
        section.pack(fill="x", padx=10, pady=(10, 5))

        header = ctk.CTkFrame(section, fg_color=Theme.SURFACE)
        header.pack(fill="x", padx=12, pady=(10, 5))

        name = client.get("name", "???")
        ctk.CTkLabel(header, text=name, fg_color=Theme.SURFACE,
                     text_color=Theme.TEXT, font=FONTS["h1"]).pack(side="left")

        c_type = client.get("client_type", "")
        if c_type:
            ctk.CTkLabel(header, text=c_type, fg_color=Theme.SURFACE,
                         text_color=COLORS["accent_text"], font=FONTS["label"]).pack(side="left", padx=8)

        rating = client.get("rating") or 0
        if rating:
            stars = "\u2605" * int(rating) + "\u2606" * (5 - int(rating))
            ctk.CTkLabel(header, text=stars, fg_color=Theme.SURFACE,
                         text_color=COLORS["warning"], font=FONTS["small"]).pack(side="left", padx=5)

        status_text = "Active" if client.get("is_active", 1) else "Inactive"
        status_color = COLORS["success"] if client.get("is_active", 1) else COLORS["text_muted"]
        ctk.CTkLabel(header, text=status_text, fg_color=Theme.SURFACE,
                     text_color=status_color, font=FONTS["label"]).pack(side="right", padx=5)

        ActionButton(header, text=t("client.edit_button"), command=self._edit_client,
                     fg_color=Theme.ACCENT_PRIMARY, text_color="#fff").pack(side="right", padx=5)

        fields_row = ctk.CTkFrame(section, fg_color=Theme.SURFACE)
        fields_row.pack(fill="x", padx=12, pady=(0, 10))

        details = []
        if client.get("contact_person"):
            details.append(f"\U0001f464 {client['contact_person']}")
        if client.get("phone"):
            details.append(f"\U0001f4de {client['phone']}")
        if client.get("email"):
            details.append(f"\u2709 {client['email']}")
        if client.get("vat_number"):
            details.append(f"VAT: {client['vat_number']}")

        for d in details:
            ctk.CTkLabel(fields_row, text=d, fg_color=Theme.SURFACE,
                         text_color=Theme.MUTED, font=FONTS["small"]).pack(side="left", padx=5)

        extra = []
        if client.get("address"):
            extra.append(client["address"])
        if client.get("notes"):
            extra.append(client["notes"])
        if client.get("payment_terms_days"):
            extra.append("Terms: {} days".format(client["payment_terms_days"]))
        if client.get("credit_limit_eur"):
            extra.append("Limit: \u20ac{:,}".format(int(client["credit_limit_eur"])))

        for e in extra:
            ctk.CTkLabel(fields_row, text=e, fg_color=Theme.SURFACE,
                         text_color=COLORS["text_muted"], font=FONTS["small"]).pack(side="left", padx=5)

    def _edit_client(self):
        client = self.service.get_by_id(self.client_id)
        _ClientFormDialog(self.main, self.service, client_data=client,
                          on_save=self._on_refresh_list or (lambda: None))

    def _rebuild(self):
        for w in self.main.winfo_children():
            w.destroy()
        self._build()

    def _kpi_card(self, parent, label, value, color=None):
        card = ctk.CTkFrame(parent, fg_color=Theme.SURFACE, corner_radius=8)
        card.pack(side="left", padx=4, fill="x", expand=True)
        ctk.CTkLabel(card, text=label, fg_color=Theme.SURFACE,
                     text_color=Theme.MUTED, font=FONTS["small"]).pack(anchor="w", padx=10, pady=(8, 0))
        ctk.CTkLabel(card, text=str(value), fg_color=Theme.SURFACE,
                     text_color=color or Theme.TEXT, font=FONTS["mono_lg"]).pack(anchor="w", padx=10, pady=(0, 8))

    def _build_kpi_section(self, dash):
        kpi_frame = ctk.CTkFrame(self.main, fg_color=Theme.BG)
        kpi_frame.pack(fill="x", padx=10, pady=5)

        total_rev = dash.get("total_revenue", 0) or 0
        total_profit = dash.get("total_profit", 0) or 0
        avg_profit = dash.get("avg_profit", 0) or 0
        total_trips = dash.get("total_trips", 0) or 0
        total_km = dash.get("total_km", 0) or 0
        outstanding = dash.get("outstanding_balance", 0) or 0
        last_30 = dash.get("trips_last_30_days", 0) or 0

        self._kpi_card(kpi_frame, t("client.kpi_total_revenue"), f"\u20ac {total_rev:,.0f}")
        self._kpi_card(kpi_frame, t("client.kpi_total_trips"), str(total_trips))
        self._kpi_card(kpi_frame, t("client.kpi_total_km"), f"{total_km:,.0f} km")
        self._kpi_card(kpi_frame, t("client.kpi_last_30d"), str(last_30))

        kpi_frame2 = ctk.CTkFrame(self.main, fg_color=Theme.BG)
        kpi_frame2.pack(fill="x", padx=10, pady=5)

        profit_color = COLORS["success"] if total_profit >= 0 else COLORS["danger"]
        outstanding_color = COLORS["warning"] if outstanding > 0 else COLORS["success"]
        self._kpi_card(kpi_frame2, t("client.kpi_total_profit"), f"\u20ac {total_profit:,.0f}", profit_color)
        self._kpi_card(kpi_frame2, t("client.kpi_avg_profit"), f"\u20ac {avg_profit:,.0f}")
        self._kpi_card(kpi_frame2, t("client.kpi_outstanding"), f"\u20ac {outstanding:,.0f}", outstanding_color)
        self._kpi_card(kpi_frame2, t("client.kpi_last_trip"), str(dash.get("last_trip_date", "\u2014"))[:10])

    def _section_header(self, parent, text):
        f = ctk.CTkFrame(parent, fg_color=Theme.BG)
        f.pack(fill="x", padx=10, pady=(10, 2))
        ctk.CTkLabel(f, text=text, fg_color=Theme.BG,
                     text_color=Theme.ACCENT, font=FONTS["h3"]).pack(side="left")
        line = ctk.CTkFrame(f, fg_color=COLORS["border"], height=1)
        line.pack(side="left", fill="x", expand=True, padx=8)

    def _build_contacts_section(self, contacts):
        self._section_header(self.main, t("client.section_contacts"))
        for c in contacts:
            row = ctk.CTkFrame(self.main, fg_color=Theme.BG)
            row.pack(fill="x", padx=15, pady=2)

            name = c.get("full_name", "")
            title = c.get("title", "")
            primary = " \u2605" if c.get("is_primary") else ""
            ctk.CTkLabel(row, text="{}{}".format(name, primary), fg_color=Theme.BG,
                         text_color=Theme.TEXT, font=FONTS["body_bold"]).pack(side="left")

            ctk.CTkLabel(row, text="  {}".format(title) if title else "", fg_color=Theme.BG,
                         text_color=Theme.MUTED, font=FONTS["small"]).pack(side="left")

            phone = c.get("phone", "")
            email = c.get("email", "")
            ctk.CTkLabel(row, text="{}  {}".format(phone, email) if phone or email else "",
                         fg_color=Theme.BG, text_color=Theme.MUTED, font=FONTS["small"]).pack(side="left", padx=10)

            ActionButton(row, text="Edit", command=lambda cid=c["id"]: self._edit_contact(cid),
                         fg_color=Theme.SURFACE2, text_color=Theme.TEXT, width=8).pack(side="right", padx=2)
            ActionButton(row, text="\u2716", command=lambda cid=c["id"]: self._delete_contact(cid),
                         fg_color=Theme.DANGER, text_color="#fff", width=6).pack(side="right", padx=2)

        ActionButton(self.main, text="+ Add Contact", command=self._add_contact,
                     fg_color=Theme.SURFACE2, text_color=Theme.ACCENT).pack(anchor="w", padx=15, pady=5)

    def _add_contact(self):
        _ContactDialog(self.main, self.service, client_id=self.client_id, on_save=self._rebuild)

    def _edit_contact(self, contact_id):
        contacts = self.service.get_contacts(self.client_id)
        ct_data = next((c for c in contacts if c["id"] == contact_id), None)
        _ContactDialog(self.main, self.service, client_id=self.client_id, contact_data=ct_data, on_save=self._rebuild)

    def _delete_contact(self, contact_id):
        if messagebox.askyesno(t("common.confirm"), t("client.confirm_delete_contact")):
            self.service.delete_contact(contact_id)
            self._rebuild()

    def _build_tags_section(self, tags):
        self._section_header(self.main, t("client.section_tags"))
        tags = [t_row.get("tag", t_row) for t_row in tags]
        if not tags:
            ctk.CTkLabel(self.main, text=t("client.no_tags"), fg_color=Theme.BG,
                         text_color=Theme.MUTED, font=FONTS["small"]).pack(anchor="w", padx=15, pady=5)
        else:
            tag_row = ctk.CTkFrame(self.main, fg_color=Theme.BG)
            tag_row.pack(fill="x", padx=15, pady=5)
            for tag in tags:
                chip = ctk.CTkFrame(tag_row, fg_color=COLORS["accent_dim"], corner_radius=6)
                chip.pack(side="left", padx=2)
                ctk.CTkLabel(chip, text=tag, fg_color=COLORS["accent_dim"],
                             text_color=COLORS["accent_text"], font=FONTS["label"]).pack(side="left", padx=6, pady=2)
                ctk.CTkLabel(chip, text="\u2716", fg_color=COLORS["accent_dim"],
                             text_color=COLORS["accent_text"], font=FONTS["label"],
                             cursor="hand2").pack(side="left", padx=(0, 4), pady=2)
                chip.winfo_children()[-1].bind("<Button-1>", lambda e, t=tag: self._remove_tag(t))

        add_frame = ctk.CTkFrame(self.main, fg_color=Theme.BG)
        add_frame.pack(fill="x", padx=15, pady=2)
        self._tag_entry = StyledEntry(add_frame, width=140, placeholder_text=t("client.tag_placeholder"))
        self._tag_entry.pack(side="left", padx=2)
        ActionButton(add_frame, text="+", command=self._add_tag,
                     fg_color=Theme.SURFACE2, text_color=Theme.ACCENT, width=6).pack(side="left", padx=2)

    def _add_tag(self):
        tag = (self._tag_entry.get() or "").strip()
        if tag:
            self.service.add_tag(self.client_id, tag)
            self._rebuild()

    def _remove_tag(self, tag):
        self.service.remove_tag(self.client_id, tag)
        self._rebuild()

    def _build_revenue_chart(self):
        from ui.client_revenue_chart import ClientRevenueChart
        self._section_header(self.main, t("client.section_chart"))
        chart_frame = ctk.CTkFrame(self.main, fg_color=Theme.BG)
        chart_frame.pack(fill="x", padx=10, pady=5)
        self._chart_widget = ClientRevenueChart(chart_frame, self.service, self.client_id)
        self._chart_widget.pack(fill="x")

    def _build_trip_history(self, trips):
        self._section_header(self.main, t("client.section_trips"))
        if not trips:
            ctk.CTkLabel(self.main, text=t("client.no_trips"), fg_color=Theme.BG,
                         text_color=Theme.MUTED, font=FONTS["small"]).pack(anchor="w", padx=15, pady=5)
            return

        tree_frame = ctk.CTkFrame(self.main, fg_color=Theme.BG)
        tree_frame.pack(fill="x", padx=10, pady=5)

        cols = ("date", "truck", "km", "revenue", "profit", "status")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=min(len(trips), 8))
        tree.heading("date", text=t("history.table_date"))
        tree.heading("truck", text=t("history.table_truck"))
        tree.heading("km", text=t("history.table_km"))
        tree.heading("revenue", text=t("client.table_revenue"))
        tree.heading("profit", text=t("history.table_profit"))
        tree.heading("status", text=t("edit_trip.field_status"))
        tree.column("date", width=85)
        tree.column("truck", width=95)
        tree.column("km", width=55, anchor="e")
        tree.column("revenue", width=75, anchor="e")
        tree.column("profit", width=75, anchor="e")
        tree.column("status", width=85, anchor="center")

        for t_row in trips:
            tree.insert("", "end", values=(
                (t_row.get("start_date") or t_row.get("created_at", ""))[:10],
                t_row.get("truck_number", ""),
                f"{t_row.get('distance_km', 0) or 0:,.0f}",
                f"\u20ac {t_row.get('total_price_eur', 0) or 0:,.0f}",
                f"\u20ac {t_row.get('net_profit', 0) or 0:,.0f}",
                t_row.get("status", ""),
            ))

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _build_invoice_section(self, dash):
        self._section_header(self.main, t("client.section_invoices"))
        invoices = dash.get("outstanding_invoices", [])
        if not invoices:
            ctk.CTkLabel(self.main, text=t("client.no_invoices"), fg_color=Theme.BG,
                         text_color=Theme.MUTED, font=FONTS["small"]).pack(anchor="w", padx=15, pady=5)
            return

        tree_frame = ctk.CTkFrame(self.main, fg_color=Theme.BG)
        tree_frame.pack(fill="x", padx=10, pady=5)

        cols = ("inv_number", "amount", "due_date", "status")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=min(len(invoices), 6))
        tree.heading("inv_number", text=t("client.table_inv_number"))
        tree.heading("amount", text=t("client.table_amount"))
        tree.heading("due_date", text=t("client.table_due_date"))
        tree.heading("status", text=t("client.table_inv_status"))
        tree.column("inv_number", width=120)
        tree.column("amount", width=80, anchor="e")
        tree.column("due_date", width=90)
        tree.column("status", width=80, anchor="center")

        for inv in invoices:
            status = inv.get("status", "")
            tag = "paid" if status == "Paid" else "unpaid"
            tree.insert("", "end", values=(
                inv.get("invoice_number", ""),
                f"\u20ac {inv.get('total_amount', 0) or 0:,.0f}",
                inv.get("due_date", ""),
                status,
            ), tags=(tag,))
        tree.tag_configure("paid", foreground=COLORS["success"])
        tree.tag_configure("unpaid", foreground=COLORS["warning"])

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _build_payment_summary(self):
        try:
            pay = self.service.get_payment_summary(self.client_id)
            if not pay or not pay.get("invoice_count"):
                return
            self._section_header(self.main, t("client.section_payment"))
            row = ctk.CTkFrame(self.main, fg_color=Theme.BG)
            row.pack(fill="x", padx=15, pady=5)
            self._kpi_card(row, "Billed", f"\u20ac {pay['total_billed']:,.0f}")
            self._kpi_card(row, "Paid", f"\u20ac {pay['total_paid']:,.0f}", COLORS["success"])
            self._kpi_card(row, "Unpaid", f"\u20ac {pay['unpaid']:,.0f}", COLORS["warning"])
            self._kpi_card(row, "Overdue", f"\u20ac {pay['overdue']:,.0f}",
                          COLORS["danger"] if pay["overdue"] > 0 else COLORS["success"])
        except Exception:
            pass

    def _build_timeline(self):
        from ui.client_activity_timeline import ClientActivityTimeline
        self._section_header(self.main, t("client.section_timeline"))
        tl_frame = ctk.CTkFrame(self.main, fg_color=Theme.BG)
        tl_frame.pack(fill="both", padx=15, pady=5)
        tl = ClientActivityTimeline(tl_frame, self.service, self.client_id)
        tl.pack(fill="x")


class _ClientFormDialog:
    def __init__(self, parent, service: ClientService, client_data=None, on_save=None):
        self.service = service
        self.client_data = client_data
        self.on_save = on_save
        self._editing = client_data is not None

        self.win = ctk.CTkToplevel(parent)
        self.win.title(t("client.edit_title") if self._editing else t("client.new_title"))
        self.win.geometry("500x700")
        self.win.configure(fg_color=Theme.BG)
        self.win.grab_set()

        body = ctk.CTkScrollableFrame(self.win, fg_color=Theme.BG,
                                       scrollbar_button_color=COLORS["border"])
        body.pack(fill="both", expand=True, padx=15, pady=15)

        fields = [
            ("name", "client.field_name", True),
            ("contact_person", "client.field_contact", False),
            ("phone", "client.field_phone", False),
            ("email", "client.field_email", False),
            ("address", "client.field_address", False),
            ("vat_number", "client.field_vat", False),
            ("client_type", "client.field_type", False),
            ("payment_terms_days", "client.field_payment_terms", False),
            ("credit_limit_eur", "client.field_credit_limit", False),
            ("default_rate_per_km", "client.field_default_rate", False),
            ("rating", "client.field_rating", False),
            ("notes", "client.field_notes", False),
        ]

        self.entries = {}
        for key, i18n_key, required in fields:
            ctk.CTkLabel(body, text=t(i18n_key), fg_color=Theme.BG,
                         text_color=Theme.TEXT, font=FONTS["label"]).pack(anchor="w", pady=(8, 2))
            if key == "client_type":
                entry = ctk.CTkComboBox(body, values=["", "Shipper", "Forwarder", "Broker", "Direct", "Other"],
                                        font=FONTS["body"])
                entry.pack(fill="x", pady=(0, 4))
                if client_data:
                    entry.set(client_data.get(key, "") or "")
                self.entries[key] = entry
            else:
                entry = StyledEntry(body)
                entry.pack(fill="x", pady=(0, 4))
                self.entries[key] = entry
                if client_data:
                    val = client_data.get(key) or ""
                    entry.insert(0, str(val))

        ActionButton(body, text=t("client.save_button"), command=self._save,
                     fg_color=Theme.ACCENT_SUCCESS, text_color="#fff").pack(pady=(15, 0))

    def _save(self):
        name = self.entries["name"]
        if isinstance(name, ctk.CTkComboBox):
            name = name.get()
        else:
            name = name.get()
        name = name.strip()
        if not name:
            messagebox.showwarning(t("common.warning"), t("client.name_required"))
            return

        data = {}
        for k, v in self.entries.items():
            val = v.get() if hasattr(v, "get") else str(v)
            if isinstance(val, str):
                val = val.strip()
            if k == "payment_terms_days":
                try:
                    val = int(val) if val else 30
                except ValueError:
                    val = 30
            if k == "credit_limit_eur":
                try:
                    val = float(val) if val else 0
                except ValueError:
                    val = 0
            if k == "default_rate_per_km":
                try:
                    val = float(val) if val else None
                except ValueError:
                    val = None
            if k == "rating":
                try:
                    val = int(val) if val else None
                except ValueError:
                    val = None
            data[k] = val

        if self._editing:
            self.service.update(self.client_data["id"], **data)
        else:
            existing = self.service._repo.get_by_name(name)
            if existing:
                messagebox.showwarning(t("common.warning"), t("client.already_exists").format(name=name))
                return
            self.service.create(**data)

        if self.on_save:
            self.on_save()
        self.win.destroy()


class _ContactDialog:
    def __init__(self, parent, service: ClientService, client_id: int, contact_data=None, on_save=None):
        self.service = service
        self.client_id = client_id
        self.contact_data = contact_data
        self.on_save = on_save
        self._editing = contact_data is not None

        self.win = ctk.CTkToplevel(parent)
        self.win.title(t("client.edit_contact") if self._editing else t("client.new_contact"))
        self.win.geometry("400x400")
        self.win.configure(fg_color=Theme.BG)
        self.win.grab_set()

        body = ctk.CTkFrame(self.win, fg_color=Theme.BG)
        body.pack(fill="both", expand=True, padx=20, pady=20)

        fields = [
            ("full_name", t("client.field_full_name")),
            ("title", t("client.field_title")),
            ("phone", t("client.field_phone")),
            ("email", t("client.field_email")),
            ("contact_type", t("client.field_contact_type")),
        ]

        self.entries = {}
        for key, label in fields:
            ctk.CTkLabel(body, text=label, fg_color=Theme.BG,
                         text_color=Theme.TEXT, font=FONTS["label"]).pack(anchor="w", pady=(8, 2))
            if key == "contact_type":
                entry = ctk.CTkComboBox(body, values=["primary", "billing", "operations", "management", "other"],
                                        font=FONTS["body"])
                entry.pack(fill="x", pady=(0, 4))
                if contact_data:
                    entry.set(contact_data.get(key, "operations"))
                else:
                    entry.set("operations")
            else:
                entry = StyledEntry(body)
                entry.pack(fill="x", pady=(0, 4))
                if contact_data:
                    val = contact_data.get(key) or ""
                    entry.insert(0, str(val))
            self.entries[key] = entry

        ActionButton(body, text=t("client.save_button"), command=self._save,
                     fg_color=Theme.ACCENT_SUCCESS, text_color="#fff").pack(pady=(15, 0))

    def _save(self):
        name = self.entries["full_name"]
        name_val = name.get() if hasattr(name, "get") else str(name)
        name_val = name_val.strip()
        if not name_val:
            messagebox.showwarning(t("common.warning"), t("client.name_required"))
            return

        data = {}
        for k, v in self.entries.items():
            val = v.get() if hasattr(v, "get") else str(v)
            if isinstance(val, str):
                val = val.strip()
            data[k] = val

        if self._editing:
            self.service.update_contact(self.contact_data["id"], **data)
        else:
            self.service.add_contact(self.client_id, **data)

        if self.on_save:
            self.on_save()
        self.win.destroy()


class _MergeDialog:
    def __init__(self, parent, service: ClientService, source_id: int, on_done=None):
        self.service = service
        self.source_id = source_id
        self.on_done = on_done

        self.win = ctk.CTkToplevel(parent)
        self.win.title(t("client.merge_title"))
        self.win.geometry("450x300")
        self.win.configure(fg_color=Theme.BG)
        self.win.grab_set()

        body = ctk.CTkFrame(self.win, fg_color=Theme.BG)
        body.pack(fill="both", expand=True, padx=20, pady=20)

        source = service.get_by_id(source_id)
        ctk.CTkLabel(body, text=t("client.merge_source").format(name=source["name"] if source else "?"),
                     fg_color=Theme.BG, text_color=Theme.TEXT, font=FONTS["body_bold"]).pack(anchor="w", pady=5)

        ctk.CTkLabel(body, text=t("client.merge_target_label"), fg_color=Theme.BG,
                     text_color=Theme.TEXT, font=FONTS["label"]).pack(anchor="w", pady=(15, 2))

        all_clients = service.get_all_with_revenue(include_inactive=True)
        names = [c["name"] for c in all_clients if c["id"] != source_id]
        self._name_to_id = {c["name"]: c["id"] for c in all_clients if c["id"] != source_id}

        self._target_combo = ctk.CTkComboBox(body, values=names, font=FONTS["body"])
        self._target_combo.pack(fill="x", pady=5)
        if names:
            self._target_combo.set(names[0])

        warn = ctk.CTkLabel(body, text=t("client.merge_warning"),
                            fg_color=Theme.BG, text_color=COLORS["warning"], font=FONTS["small"],
                            wraplength=400, justify="left")
        warn.pack(anchor="w", pady=(10, 5))

        ActionButton(body, text=t("client.merge_execute"), command=self._execute,
                     fg_color=Theme.DANGER, text_color="#fff").pack(pady=(10, 0))

    def _execute(self):
        target_name = self._target_combo.get()
        target_id = self._name_to_id.get(target_name)
        if not target_id:
            return
        if not messagebox.askyesno(t("client.merge_title"),
                                   t("client.merge_final_confirm").format(
                                       target=target_name, source=self.service.get_by_id(self.source_id)["name"])):
            return
        try:
            result = self.service.merge_clients(self.source_id, target_id)
            messagebox.showinfo(t("client.merge_title"),
                                "Moved: {} trips, {} invoices, {} contacts".format(
                                    result["trips"], result["invoices"], result["contacts"]))
        except Exception as ex:
            messagebox.showerror(t("common.error"), str(ex))
        if self.on_done:
            self.on_done()
        self.win.destroy()
