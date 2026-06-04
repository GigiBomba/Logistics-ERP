import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from typing import Any, Dict, List, Optional

from services.client_service import ClientService
from services.i18n import t, register_listener, unregister_listener
from ui.styles import Theme
from ui.widgets import StyledEntry, ActionButton
from ui.theme import FONTS, COLORS


class ClientManager:
    def __init__(self, parent, db, prefs=None, open_window=True):
        if open_window:
            self.win = ctk.CTkToplevel(parent) if parent else ctk.CTk()
            Theme.apply(self.win)  # if you use Theme.apply elsewhere
            self.frame = ctk.CTkFrame(self.win, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)
            self.win.title("Clients")
            self.win.geometry("800x600")
            self.win.configure(fg_color=Theme.BG)
        else:
            self.win = None
            self.frame = ctk.CTkFrame(parent, fg_color=Theme.BG)

        self.db = db
        self.service = ClientService(db)
        self._i18n_widgets: list = []
        self._selected_id: Optional[int] = None
        self._container = self.frame

        self._build_ui()
        self._load_data()
        register_listener(self._on_language_changed)
        # bind destroy to whichever widget is the top-level container
        self._top_widget = self.win if self.win is not None else self.frame
        self._top_widget.bind("<Destroy>", self._on_destroy)

    def _on_destroy(self, e=None):
        if e is not None and e.widget != self._top_widget:
            return
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        if self.win is not None:
            self.win.title(t("nav.clients"))
        self._load_data()

    def _build_ui(self):
        top = ctk.CTkFrame(self._container, fg_color=Theme.SURFACE)
        top.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(top, text=t("client.title"), fg_color=Theme.SURFACE,
                     text_color=Theme.TEXT, font=FONTS["h2"]).pack(side="left", padx=10)

        self._search_entry = StyledEntry(top)
        self._search_entry.insert(0, t("common.search"))
        self._search_entry.configure(text_color=COLORS["text_muted"])
        self._search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self._search_entry.bind("<FocusOut>", self._on_search_focus_out)
        self._search_entry.pack(side="left", padx=5)
        self._search_entry.bind("<KeyRelease>", lambda e: self._load_data())

        ActionButton(top, text="+ " + t("client.new_button"), command=self._open_form,
                     fg_color=Theme.ACCENT_PRIMARY, hover_color=Theme.ACCENT_SECONDARY,
                     text_color="#fff").pack(side="right", padx=10)

        # Treeview
        tree_frame = ctk.CTkFrame(self._container, fg_color=Theme.BG)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

        cols = ("id", "name", "contact", "phone", "email", "trips")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=15)
        headings = [
            ("id", "ID"),
            ("name", "client.table_name"),
            ("contact", "client.table_contact"),
            ("phone", "client.table_phone"),
            ("email", "client.table_email"),
            ("trips", "client.table_trips"),
        ]
        for col, key in headings:
            self.tree.heading(col, text=t(key))
        self.tree.column("id", width=40, anchor="center")
        self.tree.column("name", width=180)
        self.tree.column("contact", width=130)
        self.tree.column("phone", width=110)
        self.tree.column("email", width=150)
        self.tree.column("trips", width=60, anchor="center")

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._open_form(edit=True))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())

        # Action buttons
        btn_frame = ctk.CTkFrame(self._container, fg_color=Theme.BG)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        self._edit_btn = ActionButton(btn_frame, text=t("client.edit_button"), command=lambda: self._open_form(edit=True),
                                       fg_color=Theme.ACCENT_PRIMARY, text_color="#fff")
        self._edit_btn.pack(side="left", padx=5)
        self._deact_btn = ActionButton(btn_frame, text=t("client.deactivate_button"), command=self._deactivate,
                                        fg_color=Theme.DANGER, text_color="#fff")
        self._deact_btn.pack(side="left", padx=5)

        self._refresh_translations()

    def _on_search_focus_in(self, event):
        if self._search_entry.get() == t("common.search"):
            self._search_entry.delete(0, "end")
            self._search_entry.configure(text_color=Theme.TEXT)

    def _on_search_focus_out(self, event):
        if not self._search_entry.get().strip():
            self._search_entry.insert(0, t("common.search"))
            self._search_entry.configure(text_color=COLORS["text_muted"])

    def _load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        query = (self._search_entry.get() or "").strip()
        if query == t("common.search"):
            query = ""
        if query:
            clients = self.service.search(query, limit=200)
        else:
            clients = self.service.get_all()

        for c in clients:
            trip_count = self.service.get_trip_count(c["id"])
            self.tree.insert("", "end", values=(
                c["id"],
                c.get("name", ""),
                c.get("contact_person") or "",
                c.get("phone") or "",
                c.get("email") or "",
                trip_count,
            ), tags=("inactive",) if not c.get("is_active", 1) else ("active",))

        self.tree.tag_configure("inactive", foreground="gray")
        self.tree.tag_configure("active", foreground=Theme.TEXT)

    def _on_select(self):
        sel = self.tree.selection()
        if sel:
            values = self.tree.item(sel[0], "values")
            self._selected_id = int(values[0])

    def _open_form(self, edit=False):
        if edit and not self._selected_id:
            return
        client = self.service.get_by_id(self._selected_id) if edit and self._selected_id else None
        parent = self.win if self.win is not None else self.frame
        _ClientFormDialog(parent, self.service, client_data=client, on_save=self._load_data)

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
            self._load_data()

    def _refresh_translations(self):
        for widget, key, _ in self._i18n_widgets:
            try:
                widget.configure(text=t(key))
            except Exception:
                pass


class _ClientFormDialog:
    def __init__(self, parent, service: ClientService, client_data=None, on_save=None):
        self.service = service
        self.client_data = client_data
        self.on_save = on_save
        self._editing = client_data is not None

        self.win = ctk.CTkToplevel(parent)
        self.win.title(t("client.edit_title") if self._editing else t("client.new_title"))
        self.win.geometry("450x420")
        self.win.configure(fg_color=Theme.BG)
        self.win.grab_set()

        body = ctk.CTkFrame(self.win, fg_color=Theme.BG)
        body.pack(fill="both", expand=True, padx=15, pady=15)

        fields = [
            ("name", "client.field_name", True),
            ("contact_person", "client.field_contact", False),
            ("phone", "client.field_phone", False),
            ("email", "client.field_email", False),
            ("address", "client.field_address", False),
            ("vat_number", "client.field_vat", False),
            ("notes", "client.field_notes", False),
        ]

        self.entries = {}
        for key, i18n_key, required in fields:
            ctk.CTkLabel(body, text=t(i18n_key), fg_color=Theme.BG,
                         text_color=Theme.TEXT, font=FONTS["label"]).pack(anchor="w", pady=(8, 2))
            entry = StyledEntry(body)
            entry.pack(fill="x", pady=(0, 4))
            self.entries[key] = entry
            if client_data:
                val = client_data.get(key) or ""
                entry.insert(0, str(val))

        ActionButton(body, text=t("client.save_button"), command=self._save,
                     fg_color=Theme.ACCENT_SUCCESS, text_color="#fff").pack(pady=(15, 0))

    def _save(self):
        name = self.entries["name"].get().strip()
        if not name:
            messagebox.showwarning(t("common.warning"), t("client.name_required"))
            return

        data = {k: v.get().strip() for k, v in self.entries.items()}

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
