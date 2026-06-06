"""Document Center view — centralized document management UI with P1 features."""
import json
import logging
import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from datetime import datetime
import customtkinter as ctk

from ui.theme import COLORS, FONTS, S, btn
from services.i18n import t
from services.document_service import DocumentService, IMAGE_MIME

logger = logging.getLogger(__name__)

PAGE_SIZE = 20


class DocumentCenterView(ctk.CTkFrame):
    def __init__(self, parent, db, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_base"])
        super().__init__(parent, **kwargs)
        self.db = db
        self._service = DocumentService(db)
        self._page = 0
        self._total = 0
        self._total_pages = 0
        self._docs = []
        self._active_category = ""
        self._sort_order = "uploaded_at DESC"
        self._filters_visible = False
        self._selected_ids = set()
        self._frame = self
        self._build()

    @property
    def frame(self):
        return self._frame

    def wakeup(self):
        self._load()

    def _build(self):
        self.columnconfigure(0, weight=20)
        self.columnconfigure(1, weight=50)
        self.columnconfigure(2, weight=30)
        self.rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._build_detail_sidebar()
        self._load()

    # ── Left Sidebar (categories + filters) ─────────────────────────────

    def _build_sidebar(self):
        left = ctk.CTkFrame(self, fg_color=COLORS["bg_surface"])
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(left, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=S["3"], pady=S["4"])
        ctk.CTkLabel(hdr, text=t("docs.title"), font=FONTS["h3"],
                     text_color=COLORS["text_primary"],
                     anchor="w").pack(anchor="w")

        self._cat_frame = ctk.CTkFrame(left, fg_color="transparent")
        self._cat_frame.grid(row=1, column=0, sticky="ew", padx=S["3"])

        self._filter_toggle = ctk.CTkButton(
            left, text=t("docs.filters"), fg_color="transparent",
            hover_color=COLORS["bg_elevated"],
            text_color=COLORS["text_secondary"], font=FONTS["body"],
            anchor="w", command=self._toggle_filters,
        )
        self._filter_toggle.grid(row=2, column=0, sticky="ew", padx=S["3"], pady=(S["3"], 0))

        self._filter_panel = ctk.CTkFrame(left, fg_color="transparent")
        self._build_filter_panel()

        self._upload_btn = btn(left, f"  {t('docs.upload')}", self._upload_dialog,
                               variant="primary")
        self._upload_btn.grid(row=4, column=0, sticky="ew", padx=S["3"],
                              pady=(S["6"], S["3"]))

    def _build_filter_panel(self):
        self._entity_type_var = tk.StringVar(value="")
        self._date_from_var = tk.StringVar(value="")
        self._date_to_var = tk.StringVar(value="")
        self._mime_type_var = tk.StringVar(value="")

    def _toggle_filters(self):
        if self._filters_visible:
            self._filter_panel.grid_forget()
            self._filters_visible = False
        else:
            self._filter_panel.grid(row=3, column=0, sticky="ew", padx=S["3"],
                                    pady=(S["2"], 0))
            self._populate_filter_panel()
            self._filters_visible = True

    def _populate_filter_panel(self):
        for w in self._filter_panel.winfo_children():
            w.destroy()

        ctk.CTkLabel(self._filter_panel, text=t("docs.filter_entity"),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(S["2"], 0))
        etypes = [""] + self._service.get_entity_types()
        ctk.CTkComboBox(self._filter_panel, values=etypes,
                        variable=self._entity_type_var, width=140,
                        command=lambda _: self._apply_filters(),
                        fg_color=COLORS["bg_input"],
                        border_color=COLORS["border"],
                        button_color=COLORS["bg_elevated"],
                        text_color=COLORS["text_primary"],
                        font=FONTS["body"]).pack(fill="x", pady=(0, S["2"]))

        ctk.CTkLabel(self._filter_panel, text=t("docs.filter_date_from"),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w")
        df_entry = ctk.CTkEntry(self._filter_panel, textvariable=self._date_from_var,
                                placeholder_text="YYYY-MM-DD",
                                fg_color=COLORS["bg_input"],
                                border_color=COLORS["border"],
                                text_color=COLORS["text_primary"],
                                font=FONTS["body"], height=28)
        df_entry.pack(fill="x", pady=(0, S["2"]))

        ctk.CTkLabel(self._filter_panel, text=t("docs.filter_date_to"),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w")
        dt_entry = ctk.CTkEntry(self._filter_panel, textvariable=self._date_to_var,
                                placeholder_text="YYYY-MM-DD",
                                fg_color=COLORS["bg_input"],
                                border_color=COLORS["border"],
                                text_color=COLORS["text_primary"],
                                font=FONTS["body"], height=28)
        dt_entry.pack(fill="x", pady=(0, S["2"]))

        ctk.CTkLabel(self._filter_panel, text=t("docs.filter_type"),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w")
        mtypes = [""] + [m.split("/")[-1] if "/" in m else m for m in self._service.get_mime_types()]
        ctk.CTkComboBox(self._filter_panel, values=mtypes,
                        variable=self._mime_type_var, width=140,
                        command=lambda _: self._apply_filters(),
                        fg_color=COLORS["bg_input"],
                        border_color=COLORS["border"],
                        button_color=COLORS["bg_elevated"],
                        text_color=COLORS["text_primary"],
                        font=FONTS["body"]).pack(fill="x", pady=(0, S["2"]))

        ctk.CTkButton(self._filter_panel, text=t("docs.filter_apply"),
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                      text_color="#ffffff", font=FONTS["body"], height=28,
                      command=self._apply_filters).pack(fill="x", pady=(S["2"], 0))
        ctk.CTkButton(self._filter_panel, text=t("docs.filter_clear"),
                      fg_color="transparent", hover_color=COLORS["bg_elevated"],
                      text_color=COLORS["text_muted"], font=FONTS["body"], height=28,
                      command=self._clear_filters).pack(fill="x", pady=(S["1"], 0))

    def _apply_filters(self):
        self._page = 0
        self._selected_ids.clear()
        self._load_documents()

    def _clear_filters(self):
        self._entity_type_var.set("")
        self._date_from_var.set("")
        self._date_to_var.set("")
        self._mime_type_var.set("")
        self._apply_filters()

    def _build_category_tree(self, categories):
        for w in self._cat_frame.winfo_children():
            w.destroy()

        all_btn = ctk.CTkButton(
            self._cat_frame,
            text=f"  {t('docs.cat_all')}  ({self._service._repo.count()})",
            fg_color="transparent" if self._active_category else COLORS["bg_elevated"],
            hover_color=COLORS["bg_elevated"],
            text_color=COLORS["text_primary"],
            font=FONTS["body"],
            anchor="w",
            command=lambda: self._filter_category(""),
        )
        all_btn.pack(fill="x", pady=(0, S["1"]))

        cat_labels = {
            "maintenance": t("docs.cat_maintenance"),
            "invoices": t("docs.cat_invoices"),
            "trips": t("docs.cat_trips"),
            "drivers": t("docs.cat_drivers"),
            "vehicles": t("docs.cat_vehicles"),
            "other": t("docs.cat_other"),
        }
        cat_counts = {r["category"]: r["cnt"] for r in categories}
        for cat_key in ["maintenance", "invoices", "trips", "drivers", "vehicles", "other"]:
            count = cat_counts.get(cat_key, 0)
            label = cat_labels.get(cat_key, cat_key)
            active = self._active_category == cat_key
            ctk.CTkButton(
                self._cat_frame,
                text=f"  {label}  ({count})",
                fg_color=COLORS["bg_elevated"] if active else "transparent",
                hover_color=COLORS["bg_elevated"],
                text_color=COLORS["text_secondary"],
                font=FONTS["body"], anchor="w",
                command=lambda c=cat_key: self._filter_category(c),
            ).pack(fill="x", pady=1)

    # ── Main list area ──────────────────────────────────────────────────

    def _build_main(self):
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", padx=(S["4"], S["4"]))
        center.columnconfigure(0, weight=1)
        center.rowconfigure(0, weight=0)
        center.rowconfigure(1, weight=0)
        center.rowconfigure(2, weight=1)
        center.rowconfigure(3, weight=0)

        toolbar = ctk.CTkFrame(center, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, S["2"]))
        toolbar.columnconfigure(1, weight=1)

        sort_vals = [t("docs.sort_newest"), t("docs.sort_oldest"),
                     t("docs.sort_name_az"), t("docs.sort_name_za"),
                     t("docs.sort_size_lg"), t("docs.sort_size_sm")]
        sort_keys = ["uploaded_at DESC", "uploaded_at ASC",
                     "title ASC", "title DESC",
                     "file_size DESC", "file_size ASC"]
        self._sort_combo = ctk.CTkComboBox(
            toolbar, values=sort_vals, width=120,
            command=self._on_sort_change,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            button_color=COLORS["bg_elevated"],
            text_color=COLORS["text_primary"],
            font=FONTS["body"],
        )
        self._sort_combo.set(sort_vals[0])
        self._sort_combo.grid(row=0, column=0, padx=(0, S["3"]))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search())
        search_entry = ctk.CTkEntry(
            toolbar, textvariable=self._search_var,
            placeholder_text=t("docs.search_placeholder"),
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"], border_width=1,
            text_color=COLORS["text_primary"],
            font=FONTS["body"], height=34, corner_radius=6,
        )
        search_entry.grid(row=0, column=1, sticky="ew", padx=S["3"])

        self._select_all_var = tk.BooleanVar(value=False)
        self._select_all_cb = ctk.CTkCheckBox(
            toolbar, text="", variable=self._select_all_var,
            command=self._toggle_select_all,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            border_color=COLORS["border"], width=18, height=18,
        )
        self._select_all_cb.grid(row=0, column=2, padx=(0, S["2"]))

        self._batch_bar = ctk.CTkFrame(center, fg_color="transparent")

        batch_zip_btn = ctk.CTkButton(
            self._batch_bar, text=t("docs.download_zip"),
            fg_color=COLORS["info"], hover_color=COLORS["info_dim"],
            text_color="#ffffff", font=FONTS["small"], height=28,
            command=self._download_zip_selected,
        )
        batch_zip_btn.pack(side="left", padx=(0, S["2"]))

        batch_del_btn = ctk.CTkButton(
            self._batch_bar, text=t("docs.batch_delete"),
            fg_color=COLORS["danger"], hover_color=COLORS["danger_dim"],
            text_color="#ffffff", font=FONTS["small"], height=28,
            command=self._batch_delete_selected,
        )
        batch_del_btn.pack(side="left")

        self._list_frame = ctk.CTkScrollableFrame(
            center, fg_color=COLORS["bg_base"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["border_hover"],
        )
        self._list_frame.grid(row=2, column=0, sticky="nsew")

        self._setup_drag_drop()

        pager = ctk.CTkFrame(center, fg_color="transparent")
        pager.grid(row=3, column=0, sticky="ew", pady=(S["3"], 0))

        self._page_label = ctk.CTkLabel(pager, text="", font=FONTS["small"],
                                        text_color=COLORS["text_muted"])
        self._page_label.pack(side="left")

        btn(pager, t("docs.prev"), self._prev_page, variant="secondary").pack(
            side="right", padx=(S["2"], 0))
        btn(pager, t("docs.next"), self._next_page, variant="secondary").pack(
            side="right")

    def _setup_drag_drop(self):
        try:
            self._list_frame.drop_target_register("DND_Files")
            self._list_frame.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self._list_frame.dnd_bind("<<DragLeave>>", self._on_drag_leave)
            self._list_frame.dnd_bind("<<Drop>>", self._on_drop)
            self._list_frame.dnd_enable(True)
        except Exception:
            pass

    def _on_drag_enter(self, event):
        try:
            self._list_frame.configure(fg_color=COLORS["accent_dim"])
        except Exception:
            pass

    def _on_drag_leave(self, event):
        try:
            self._list_frame.configure(fg_color=COLORS["bg_base"])
        except Exception:
            pass

    def _on_drop(self, event):
        try:
            self._list_frame.configure(fg_color=COLORS["bg_base"])
            data = event.data
            if data:
                paths = self._parse_drop_paths(data)
                if paths:
                    self._process_batch_upload(paths)
        except Exception:
            pass

    @staticmethod
    def _parse_drop_paths(data):
        paths = []
        for item in data.strip().split():
            item = item.strip()
            if item.startswith("{") and item.endswith("}"):
                item = item[1:-1]
            if os.path.isfile(item):
                paths.append(item)
        return paths

    # ── Detail sidebar ──────────────────────────────────────────────────

    def _build_detail_sidebar(self):
        right = ctk.CTkFrame(self, fg_color=COLORS["bg_surface"])
        right.grid(row=0, column=2, sticky="nsew")
        right.columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=S["4"], pady=S["4"])
        ctk.CTkLabel(hdr, text=t("docs.details"), font=FONTS["h3"],
                     text_color=COLORS["text_primary"],
                     anchor="w").pack(anchor="w")

        self._detail_content = ctk.CTkFrame(right, fg_color="transparent")
        self._detail_content.grid(row=1, column=0, sticky="nsew", padx=S["4"])

        self._detail_actions = ctk.CTkFrame(right, fg_color="transparent")
        self._detail_actions.grid(row=2, column=0, sticky="ew", padx=S["4"],
                                  pady=(0, S["4"]))
        self._show_detail(None)

    # ── Data loading ───────────────────────────────────────────────────

    def _load(self):
        self._load_categories()
        self._load_documents()

    def _load_categories(self):
        categories = self._service.get_categories()
        self._build_category_tree(categories)

    def _load_documents(self):
        for w in self._list_frame.winfo_children():
            w.destroy()

        query = self._search_var.get().strip()
        date_from = self._date_from_var.get().strip() if self._filters_visible else ""
        date_to = self._date_to_var.get().strip() if self._filters_visible else ""
        entity_type = self._entity_type_var.get().strip() if self._filters_visible else ""
        mime_filter = self._mime_type_var.get().strip() if self._filters_visible else ""

        if query:
            result = self._service.fts_search(
                query=query, category=self._active_category,
                entity_type=entity_type, order=self._sort_order,
                page=self._page, page_size=PAGE_SIZE,
            )
        else:
            result = self._service.advanced_search(
                query=query, category=self._active_category,
                entity_type=entity_type, date_from=date_from, date_to=date_to,
                mime_type=mime_filter, order=self._sort_order,
                page=self._page, page_size=PAGE_SIZE,
            )
        self._docs = result["items"]
        self._total = result["total"]
        self._total_pages = result["total_pages"]
        self._update_page_label()

        if self._selected_ids:
            self._show_batch_bar()
        else:
            self._batch_bar.grid_forget()

        if not self._docs:
            empty = ctk.CTkLabel(self._list_frame, text=t("docs.no_documents"),
                                 font=FONTS["body"],
                                 text_color=COLORS["text_muted"],
                                 anchor="center")
            empty.pack(pady=S["8"])
            self._show_detail(None)
            return

        for doc in self._docs:
            self._build_doc_row(doc)

    def _build_doc_row(self, doc):
        did = doc["id"]
        mime_type = doc.get("mime_type", "")

        row = ctk.CTkFrame(self._list_frame, fg_color=COLORS["bg_surface"],
                           corner_radius=6)
        row.pack(fill="x", pady=(0, S["2"]))

        cb_var = tk.BooleanVar(value=did in self._selected_ids)
        cb = ctk.CTkCheckBox(
            row, text="", variable=cb_var,
            command=lambda d=did, v=cb_var: self._toggle_select(d, v),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            border_color=COLORS["border"], width=18, height=18,
        )
        cb.pack(side="left", padx=(S["3"], S["2"]), pady=S["3"])

        thumb = self._service.get_thumbnail_path(did)
        icon_zone = ctk.CTkFrame(row, fg_color="transparent", width=48, height=48)
        icon_zone.pack(side="left", padx=(0, S["2"]), pady=S["2"])
        icon_zone.pack_propagate(False)

        if thumb and os.path.isfile(thumb):
            try:
                from PIL import Image as PILImage
                from PIL import ImageTk
                img = PILImage.open(thumb)
                img = img.resize((44, 33), PILImage.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                thumb_lbl = ctk.CTkLabel(icon_zone, text="", image=photo)
                thumb_lbl.image = photo
                thumb_lbl.pack(expand=True)
            except Exception:
                self._icon_label(icon_zone, mime_type)
        else:
            self._icon_label(icon_zone, mime_type)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=S["2"])

        title_text = doc.get("title", doc.get("file_name", ""))
        ctk.CTkLabel(info, text=title_text[:70], font=FONTS["body_bold"],
                     text_color=COLORS["text_primary"], anchor="w").pack(anchor="w")

        meta_parts = [doc.get("doc_number", "")]
        size = doc.get("file_size", 0)
        if size < 1024:
            meta_parts.append(f"{size} B")
        elif size < 1024 * 1024:
            meta_parts.append(f"{size / 1024:.1f} KB")
        else:
            meta_parts.append(f"{size / (1024 * 1024):.1f} MB")
        upload = doc.get("uploaded_at", "")[:10]
        if upload:
            meta_parts.append(upload)
        ctk.CTkLabel(info, text="  ".join(meta_parts), font=FONTS["small"],
                     text_color=COLORS["text_muted"], anchor="w").pack(anchor="w")

        tags_str = doc.get("tags", "[]")
        try:
            tag_list = json.loads(tags_str)
        except (json.JSONDecodeError, TypeError):
            tag_list = []
        if tag_list:
            tag_frame = ctk.CTkFrame(info, fg_color="transparent")
            tag_frame.pack(anchor="w", pady=(S["1"], 0))
            for tg in tag_list[:4]:
                chip = ctk.CTkFrame(tag_frame, fg_color=COLORS["accent_dim"],
                                    corner_radius=3)
                chip.pack(side="left", padx=(0, 2))
                ctk.CTkLabel(chip, text=tg, font=FONTS["label"],
                             text_color=COLORS["accent_text"]).pack(
                    padx=4, pady=1)

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.pack(side="right", padx=S["3"])

        ctk.CTkButton(actions, text=t("docs.view"),
                      fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"],
                      text_color="#ffffff", font=FONTS["small"],
                      width=40, height=24, corner_radius=4,
                      command=lambda d=doc: self._open_document(d)).pack(side="left", padx=1)

        ctk.CTkButton(actions, text=t("docs.email"),
                      fg_color=COLORS["info"],
                      hover_color=COLORS["info_dim"],
                      text_color="#ffffff", font=FONTS["small"],
                      width=40, height=24, corner_radius=4,
                      command=lambda d=doc: self._email_document(d)).pack(side="left", padx=1)

        ctk.CTkButton(actions, text=t("docs.delete"),
                      fg_color="transparent",
                      hover_color=COLORS["danger_dim"],
                      text_color=COLORS["text_muted"], font=FONTS["small"],
                      width=40, height=24, corner_radius=4,
                      command=lambda d=doc: self._delete_document(d)).pack(side="left", padx=1)

        for w in (row, info):
            w.bind("<Enter>", lambda e, r=row: r.configure(fg_color=COLORS["bg_elevated"]))
            w.bind("<Leave>", lambda e, r=row: r.configure(fg_color=COLORS["bg_surface"]))

        row.bind("<Button-1>", lambda e, d=doc: self._show_detail(d))
        info.bind("<Button-1>", lambda e, d=doc: self._show_detail(d))
        for c in info.winfo_children():
            c.bind("<Button-1>", lambda e, d=doc: self._show_detail(d))

    @staticmethod
    def _icon_label(parent, mime_type):
        icon = DocumentCenterView._icon_for(mime_type)
        ctk.CTkLabel(parent, text=icon, font=("Segoe UI", 20),
                     text_color=COLORS["text_secondary"]).pack(expand=True)

    # ── Detail panel (right sidebar) ──────────────────────────────────

    def _show_detail(self, doc):
        for w in self._detail_content.winfo_children():
            w.destroy()
        for w in self._detail_actions.winfo_children():
            w.destroy()

        if doc is None:
            ctk.CTkLabel(self._detail_content, text=t("docs.select_document"),
                         font=FONTS["small"],
                         text_color=COLORS["text_muted"],
                         anchor="w").pack(pady=S["4"])
            return

        c = self._detail_content
        title = doc.get("title", doc.get("file_name", ""))
        ctk.CTkLabel(c, text=title, font=FONTS["body_bold"],
                     text_color=COLORS["text_primary"], anchor="w",
                     wraplength=180).pack(anchor="w", pady=(0, S["2"]))

        ctk.CTkLabel(c, text=doc.get("doc_number", ""), font=FONTS["mono"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(anchor="w")

        size = doc.get("file_size", 0)
        if size < 1024:
            sz = f"{size} B"
        elif size < 1024 * 1024:
            sz = f"{size / 1024:.1f} KB"
        else:
            sz = f"{size / (1024 * 1024):.1f} MB"
        ctk.CTkLabel(c, text=f"{sz} | {doc.get('mime_type', '')}", font=FONTS["small"],
                     text_color=COLORS["text_muted"], anchor="w",
                     wraplength=180).pack(anchor="w", pady=(0, S["2"]))

        ctk.CTkLabel(c, text=t("docs.tags_label"), font=FONTS["label"],
                     text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(S["3"], 0))

        tag_frame = ctk.CTkFrame(c, fg_color="transparent")
        tag_frame.pack(anchor="w", fill="x", pady=(S["1"], S["2"]))

        tags_str = doc.get("tags", "[]")
        try:
            tag_list = json.loads(tags_str)
        except (json.JSONDecodeError, TypeError):
            tag_list = []

        for tg in tag_list:
            chip = ctk.CTkFrame(tag_frame, fg_color=COLORS["accent_dim"],
                                corner_radius=3)
            chip.pack(side="left", padx=(0, 3), pady=2)
            ctk.CTkLabel(chip, text=tg, font=FONTS["label"],
                         text_color=COLORS["accent_text"]).pack(
                side="left", padx=4, pady=1)
            ctk.CTkButton(chip, text="\u2716", width=16, height=16,
                          fg_color="transparent",
                          hover_color=COLORS["danger_dim"],
                          text_color=COLORS["text_muted"],
                          font=FONTS["label"],
                          command=lambda t=tg, d=doc: self._remove_tag(d["id"], t)).pack(
                side="left", padx=(0, 2))

        add_tag_frame = ctk.CTkFrame(c, fg_color="transparent")
        add_tag_frame.pack(anchor="w", fill="x", pady=(0, S["3"]))
        self._tag_entry = ctk.CTkEntry(
            add_tag_frame, placeholder_text=t("docs.add_tag"),
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["small"],
            height=26, width=100,
        )
        self._tag_entry.pack(side="left", fill="x", expand=True)
        self._tag_entry.bind("<Return>", lambda e, d=doc: self._add_tag_action(d["id"]))
        ctk.CTkButton(add_tag_frame, text="+", width=24, height=26,
                      fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"],
                      text_color="#ffffff",
                      font=FONTS["body"],
                      command=lambda d=doc: self._add_tag_action(d["id"])).pack(
            side="left", padx=(S["2"], 0))

        links = self._service.get_links(doc["id"])
        if links:
            ctk.CTkLabel(c, text=t("docs.linked_to"), font=FONTS["label"],
                         text_color=COLORS["text_muted"],
                         anchor="w").pack(anchor="w", pady=(S["3"], 0))
            for lk in links:
                ctk.CTkLabel(c, text=f"  {lk['linked_entity_type']} #{lk['linked_entity_id']}",
                             font=FONTS["small"],
                             text_color=COLORS["text_secondary"],
                             anchor="w").pack(anchor="w")

        expiry = doc.get("expiry_date", "")
        ctk.CTkLabel(c, text=t("docs.expiry_label"), font=FONTS["label"],
                     text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(S["3"], 0))
        expiry_frame = ctk.CTkFrame(c, fg_color="transparent")
        expiry_frame.pack(anchor="w", fill="x", pady=(S["1"], 0))
        self._expiry_var = tk.StringVar(value=expiry)
        exp_entry = ctk.CTkEntry(
            expiry_frame, textvariable=self._expiry_var,
            placeholder_text="YYYY-MM-DD",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["small"],
            height=26, width=100,
        )
        exp_entry.pack(side="left", fill="x", expand=True)
        exp_entry.bind("<Return>", lambda e, d=doc: self._set_expiry(d["id"]))
        ctk.CTkButton(expiry_frame, text=t("docs.set_expiry"), width=28, height=26,
                      fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"],
                      text_color="#ffffff", font=FONTS["small"],
                      command=lambda d=doc: self._set_expiry(d["id"])).pack(
            side="left", padx=(S["2"], 0))

        versions = self._service.get_versions(doc["id"])
        if versions:
            ctk.CTkLabel(c, text=t("docs.versions_label"), font=FONTS["label"],
                         text_color=COLORS["text_muted"],
                         anchor="w").pack(anchor="w", pady=(S["3"], 0))
            for v in versions[:5]:
                vtext = f"  v{v['version_number']}: {v.get('comment', v['created_at'][:10])}"
                vframe = ctk.CTkFrame(c, fg_color="transparent")
                vframe.pack(anchor="w", fill="x")
                ctk.CTkLabel(vframe, text=vtext, font=FONTS["small"],
                             text_color=COLORS["text_secondary"],
                             anchor="w").pack(side="left", fill="x", expand=True)
                ctk.CTkButton(vframe, text=t("docs.restore"), width=28, height=20,
                              fg_color="transparent",
                              hover_color=COLORS["accent_dim"],
                              text_color=COLORS["accent_text"],
                              font=FONTS["label"],
                              command=lambda d=doc, vn=v["version_number"]: self._restore_version(d["id"], vn)).pack(
                    side="right")

        ctk.CTkButton(c, text=t("docs.upload_version"), fg_color=COLORS["bg_elevated"],
                      hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_primary"], font=FONTS["small"],
                      height=26,
                      command=lambda d=doc: self._upload_version_dialog(d["id"])).pack(
            fill="x", pady=(S["3"], 0))

        act = self._detail_actions
        ctk.CTkButton(act, text=t("docs.view"), fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"],
                      text_color="#ffffff", font=FONTS["body"], height=30,
                      command=lambda d=doc: self._open_document(d)).pack(
            fill="x", pady=(0, S["2"]))
        ctk.CTkButton(act, text=t("docs.download_zip"),
                      fg_color=COLORS["info"],
                      hover_color=COLORS["info_dim"],
                      text_color="#ffffff", font=FONTS["body"], height=30,
                      command=lambda d=doc: self._download_single_zip(d)).pack(
            fill="x", pady=(0, S["2"]))
        ctk.CTkButton(act, text=t("docs.email"),
                      fg_color=COLORS["bg_elevated"],
                      hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_primary"], font=FONTS["body"],
                      height=30,
                      command=lambda d=doc: self._email_document(d)).pack(
            fill="x", pady=(0, S["2"]))
        ctk.CTkButton(act, text=t("docs.archive"),
                      fg_color="transparent",
                      hover_color=COLORS["bg_elevated"],
                      text_color=COLORS["text_muted"], font=FONTS["body"],
                      height=30,
                      command=lambda d=doc: self._archive_document(d)).pack(
            fill="x")

    def _add_tag_action(self, doc_id):
        tag = self._tag_entry.get().strip() if hasattr(self, '_tag_entry') else ""
        if tag:
            self._service.add_tag(doc_id, tag)
            self._tag_entry.delete(0, "end")
            self._refresh_detail(doc_id)

    def _remove_tag(self, doc_id, tag):
        self._service.remove_tag(doc_id, tag)
        self._refresh_detail(doc_id)

    def _set_expiry(self, doc_id):
        date = self._expiry_var.get().strip() if hasattr(self, '_expiry_var') else ""
        if date:
            self._service.set_expiry_date(doc_id, date)
            self._show_toast("Expiry date saved")
            self._refresh_detail(doc_id)

    def _restore_version(self, doc_id, version_number):
        if messagebox.askyesno(t("docs.confirm_restore"),
                                t("docs.confirm_restore_msg").format(v=version_number)):
            self._service.restore_version(doc_id, version_number)
            self._show_toast(f"Restored version {version_number}")
            self._refresh_detail(doc_id)

    def _upload_version_dialog(self, doc_id):
        path = filedialog.askopenfilename(
            title=t("docs.upload_version"),
            filetypes=[("All Supported",
                       "*.pdf;*.png;*.jpg;*.jpeg;*.docx;*.xlsx;*.csv;*.txt;*.zip")],
        )
        if not path:
            return
        comment = simpledialog.askstring("Version Comment", "What changed?", parent=self) or ""
        try:
            self._service.upload_new_version(doc_id, path, comment, "user")
            self._show_toast("New version uploaded")
        except Exception as e:
            messagebox.showerror("Version Error", str(e))
        self._refresh_detail(doc_id)

    def _refresh_detail(self, doc_id):
        doc = self._service.get_by_id(doc_id)
        if doc:
            self._show_detail(doc)

    # ── Actions ────────────────────────────────────────────────────────

    def _open_document(self, doc):
        self._service.open_file(doc["id"])

    def _upload_dialog(self):
        paths = filedialog.askopenfilenames(
            title=t("docs.upload_title"),
            filetypes=[
                ("All Supported",
                 "*.pdf;*.png;*.jpg;*.jpeg;*.docx;*.xlsx;*.csv;*.txt;*.zip;*.gif"),
                ("PDF", "*.pdf"),
                ("Images", "*.png;*.jpg;*.jpeg;*.gif"),
                ("Documents", "*.docx;*.xlsx;*.csv;*.txt"),
                ("All Files", "*.*"),
            ],
        )
        if not paths:
            return
        self._process_batch_upload(paths)

    def _process_batch_upload(self, paths):
        result = self._service.batch_upload(
            paths=paths,
            category=self._active_category or "",
            uploaded_by="user",
        )
        self._load()
        uploaded = len(result["uploaded"])
        dups = len(result["duplicates"])
        failed = len(result["rejected"]) + len(result["failed"])

        msg_parts = []
        if uploaded:
            msg_parts.append(f"Uploaded: {uploaded}")
        if dups:
            msg_parts.append(f"Duplicates skipped: {dups}")
        if failed:
            msg_parts.append(f"Failed: {failed}")

        if uploaded > 0:
            self._show_toast(" | ".join(msg_parts))
        if failed > 0:
            details = "\n".join(
                [f"  {r['file']}: {r.get('reason', 'Unknown')}" for r in (
                    result["rejected"] + result["failed"]
                )][:10]
            )
            messagebox.showwarning(
                t("docs.upload_title"),
                f"Some files were rejected:\n{details}",
            )

    def _email_document(self, doc):
        recipient = simpledialog.askstring(
            t("docs.email_title"), t("docs.email_prompt"),
            parent=self,
        )
        if not recipient:
            return
        try:
            ok = self._service.email_document(doc["id"], recipient)
            if ok:
                messagebox.showinfo(t("docs.email_title"),
                                    t("docs.email_sent"))
            else:
                messagebox.showerror(t("docs.email_title"),
                                     "SMTP not configured. Check settings.")
        except Exception as e:
            messagebox.showerror(t("docs.email_title"), str(e))

    def _download_zip_selected(self):
        if not self._selected_ids:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP archive", "*.zip")],
            title=t("docs.download_zip"),
        )
        if not path:
            return
        try:
            self._service.download_zip(list(self._selected_ids), path)
            messagebox.showinfo(t("docs.download_zip"), f"Saved: {path}")
        except Exception as e:
            messagebox.showerror(t("docs.download_zip"), str(e))

    def _download_single_zip(self, doc):
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP archive", "*.zip")],
            title=t("docs.download_zip"),
        )
        if not path:
            return
        try:
            self._service.download_zip([doc["id"]], path)
            messagebox.showinfo(t("docs.download_zip"), f"Saved: {path}")
        except Exception as e:
            messagebox.showerror(t("docs.download_zip"), str(e))

    def _delete_document(self, doc):
        if not messagebox.askyesno(
            t("docs.confirm_delete_title"),
            t("docs.confirm_delete_msg").format(
                name=doc.get("title", doc.get("file_name", ""))
            ),
        ):
            return
        try:
            self._service.delete(doc["id"])
            self._selected_ids.discard(doc["id"])
        except Exception as e:
            logger.error("Failed to delete document %d: %s", doc["id"], e)
            messagebox.showerror(t("docs.confirm_delete_title"), str(e))
        self._load()

    def _archive_document(self, doc):
        self._service.archive(doc["id"])
        self._selected_ids.discard(doc["id"])
        self._load()

    def _batch_delete_selected(self):
        if not self._selected_ids:
            return
        n = len(self._selected_ids)
        if not messagebox.askyesno(t("docs.confirm_delete_title"),
                                   f"Delete {n} selected document(s)?"):
            return
        try:
            self._service.delete_batch(list(self._selected_ids))
            self._selected_ids.clear()
        except Exception as e:
            messagebox.showerror(t("docs.confirm_delete_title"), str(e))
        self._load()

    # ── Selection ──────────────────────────────────────────────────────

    def _toggle_select(self, doc_id, var):
        if var.get():
            self._selected_ids.add(doc_id)
        else:
            self._selected_ids.discard(doc_id)
        if self._selected_ids:
            self._show_batch_bar()
        else:
            self._batch_bar.grid_forget()

    def _toggle_select_all(self):
        if self._select_all_var.get():
            self._selected_ids = {d["id"] for d in self._docs}
        else:
            self._selected_ids.clear()
        self._load_documents()
        if self._selected_ids:
            self._show_batch_bar()
        else:
            self._batch_bar.grid_forget()

    def _show_batch_bar(self):
        self._batch_bar.grid(row=1, column=0, sticky="ew",
                             pady=(0, S["2"]))

    # ── Navigation / filters ───────────────────────────────────────────

    def _filter_category(self, category):
        self._active_category = category
        self._page = 0
        self._selected_ids.clear()
        self._load()

    def _on_search(self):
        self._page = 0
        self._selected_ids.clear()
        self._load()

    def _on_sort_change(self, choice):
        sort_map = {
            t("docs.sort_newest"): "uploaded_at DESC",
            t("docs.sort_oldest"): "uploaded_at ASC",
            t("docs.sort_name_az"): "title ASC",
            t("docs.sort_name_za"): "title DESC",
            t("docs.sort_size_lg"): "file_size DESC",
            t("docs.sort_size_sm"): "file_size ASC",
        }
        self._sort_order = sort_map.get(choice, "uploaded_at DESC")
        self._page = 0
        self._selected_ids.clear()
        self._load_documents()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._selected_ids.clear()
            self._load_documents()

    def _next_page(self):
        if self._page < self._total_pages - 1:
            self._page += 1
            self._selected_ids.clear()
            self._load_documents()

    def _update_page_label(self):
        self._page_label.configure(
            text=f"{self._page + 1} / {max(1, self._total_pages)}  ({self._total})"
        )

    # ── Toast ───────────────────────────────────────────────────────────

    def _show_toast(self, msg):
        t2 = tk.Toplevel(self)
        try:
            from ui.styles import Theme
            Theme.apply(t2)
        except Exception:
            pass
        t2.overrideredirect(True)
        t2.geometry(f"+{self.winfo_rootx() + 100}+{self.winfo_rooty() + 100}")
        tk.Label(t2, text=msg, bg=COLORS["success"],
                 fg=COLORS["text_primary"],
                 font=FONTS["small"], padx=20, pady=10).pack()
        self.after(2000, t2.destroy)

    @staticmethod
    def _icon_for(mime_type):
        if mime_type == "application/pdf":
            return "\U0001F4C4"
        if mime_type in IMAGE_MIME:
            return "\U0001F5BC"
        if "spreadsheet" in mime_type or mime_type == "text/csv":
            return "\U0001F4CA"
        if "word" in mime_type or mime_type == "text/plain":
            return "\U0001F4C3"
        if mime_type == "application/zip":
            return "\U0001F4E6"
        return "\U0001F4CE"


def open_entity_documents(parent, db, entity_type, entity_id, title=""):
    win = ctk.CTkToplevel(parent)
    win.title(f"Documents — {title}" if title else "Entity Documents")
    win.geometry("650x500")
    try:
        from ui.styles import Theme
        Theme.apply(win)
    except Exception:
        pass
    win.configure(fg_color=COLORS["bg_base"])

    service = DocumentService(db)
    docs = service.get_documents_for_entity(entity_type, entity_id)

    header = ctk.CTkFrame(win, fg_color="transparent")
    header.pack(fill="x", padx=S["4"], pady=S["4"])
    ctk.CTkLabel(header, text=f"{title} ({len(docs)} docs)",
                 font=FONTS["h3"], text_color=COLORS["text_primary"],
                 anchor="w").pack(side="left")

    upload_btn = ctk.CTkButton(
        header, text=t("docs.upload"), fg_color=COLORS["accent"],
        hover_color=COLORS["accent_hover"],
        text_color="#ffffff", font=FONTS["body"], height=30,
        command=lambda: _upload_to_entity(win, service, entity_type, entity_id, refresh_fn),
    )
    upload_btn.pack(side="right")

    list_frame = ctk.CTkScrollableFrame(
        win, fg_color=COLORS["bg_base"],
        scrollbar_button_color=COLORS["border"],
        scrollbar_button_hover_color=COLORS["border_hover"],
    )
    list_frame.pack(fill="both", expand=True, padx=S["4"])

    def _build_list():
        for w in list_frame.winfo_children():
            w.destroy()
        current_docs = service.get_documents_for_entity(entity_type, entity_id)
        if not current_docs:
            ctk.CTkLabel(list_frame, text=t("docs.no_documents"),
                         font=FONTS["body"],
                         text_color=COLORS["text_muted"],
                         anchor="center").pack(pady=S["8"])
            return
        for doc in current_docs:
            row = ctk.CTkFrame(list_frame, fg_color=COLORS["bg_surface"],
                               corner_radius=6)
            row.pack(fill="x", pady=(0, S["2"]))

            icon = DocumentCenterView._icon_for(doc.get("mime_type", ""))
            ctk.CTkLabel(row, text=icon, font=("Segoe UI", 18),
                         text_color=COLORS["text_secondary"],
                         width=30).pack(side="left", padx=S["3"], pady=S["2"])

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, pady=S["2"])
            ctk.CTkLabel(info, text=doc.get("title", doc.get("file_name", "")),
                         font=FONTS["body_bold"],
                         text_color=COLORS["text_primary"],
                         anchor="w").pack(anchor="w")

            size = doc.get("file_size", 0)
            if size < 1024:
                sz = f"{size} B"
            elif size < 1024 * 1024:
                sz = f"{size / 1024:.1f} KB"
            else:
                sz = f"{size / (1024 * 1024):.1f} MB"
            ctk.CTkLabel(info, text=f"{doc.get('doc_number', '')} | {sz} | {doc.get('uploaded_at', '')[:10]}",
                         font=FONTS["small"],
                         text_color=COLORS["text_muted"],
                         anchor="w").pack(anchor="w")

            act = ctk.CTkFrame(row, fg_color="transparent")
            act.pack(side="right", padx=S["3"])
            ctk.CTkButton(act, text=t("docs.view"),
                          fg_color=COLORS["accent"],
                          hover_color=COLORS["accent_hover"],
                          text_color="#ffffff", font=FONTS["small"],
                          width=36, height=22, corner_radius=4,
                          command=lambda d=doc: service.open_file(d["id"])).pack(
                side="left", padx=1)
            ctk.CTkButton(act, text=t("docs.unlink"),
                          fg_color="transparent",
                          hover_color=COLORS["danger_dim"],
                          text_color=COLORS["text_muted"],
                          font=FONTS["small"],
                          width=36, height=22, corner_radius=4,
                          command=lambda d=doc: _unlink_and_refresh(service, d["id"], entity_type, entity_id)).pack(
                side="left", padx=1)

    def refresh_fn():
        _build_list()
        current = service.get_documents_for_entity(entity_type, entity_id)
        header.winfo_children()[0].configure(text=f"{title} ({len(current)} docs)")

    def _unlink_and_refresh(svc, doc_id, etype, eid):
        links = svc.get_links(doc_id)
        for lk in links:
            if lk["linked_entity_type"] == etype and lk["linked_entity_id"] == eid:
                svc.unlink_document(lk["id"])
                break
        refresh_fn()

    _build_list()


def _upload_to_entity(win, service, entity_type, entity_id, refresh_fn):
    paths = filedialog.askopenfilenames(
        title=t("docs.upload_title"),
        filetypes=[
            ("All Supported", "*.pdf;*.png;*.jpg;*.jpeg;*.docx;*.xlsx;*.csv;*.txt;*.zip"),
            ("All Files", "*.*"),
        ],
    )
    if not paths:
        return
    for src in paths:
        try:
            service.upload(source_path=src, entity_type=entity_type,
                          entity_id=entity_id, uploaded_by="user")
        except Exception:
            pass
    refresh_fn()
