import json
import math
import threading
import tkinter as tk
import customtkinter as ctk
from dataclasses import asdict
from typing import Optional
from tkinter import filedialog, messagebox, ttk

from services.route_history_service import RouteHistoryRecord, RouteHistoryService
from services.i18n import t, register_listener, unregister_listener
from services.route_result_presenter import format_duration_minutes
from ui.history_map_preview import HistoryMapPreview
from ui.route_planner import RoutePlannerTab
from ui.styles import Theme
from ui.widgets import ActionButton, StyledCheckbutton, StyledEntry


class RouteHistoryView:
    """Professional route history browser for saved Route Planner calculations."""

    PAGE_SIZE = 50

    def __init__(self, parent, db, controller=None, embedded=False):
        self.parent = parent
        self.db = db
        self.controller = controller
        self.service = RouteHistoryService(db)
        self.current_page = 0
        self.total_rows = 0
        self.rows_by_tree_id = {}
        self.sort_by = "last_calculated_at"
        self.sort_dir = "DESC"
        self._selected_route_id = None
        self._compare_route_ids = []
        self._preview_token = 0
        self._map_preview = None
        self._i18n_widgets = []
        self._tree_heading_keys = []
        self._after_ids: list = []

        if embedded:
            self.win = None
            self.frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)
        else:
            self.win = ctk.CTkToplevel(parent)
            self.win.title(t("route_history.title"))
            self.win.geometry("1280x820")
            self.win.configure(fg_color=Theme.BG)
            Theme.apply(self.win)
            if self.win:
                self.win.protocol("WM_DELETE_WINDOW", self._on_close)
            self.frame = ctk.CTkFrame(self.win, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)

        self._setup_ui()
        self._load_async()

        if self.win:
            self.win.bind("<Destroy>", self._on_destroy)
        register_listener(self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_destroy(self, event=None):
        if event is not None and event.widget != (self.win or self.frame):
            return
        for aid in self._after_ids:
            try:
                target = self.win or self.frame or self.parent
                target.after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
        if self.win:
            if self.win:
                self.win.title(t("route_history.title"))
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
        self.stats_text.config(text=t("route_history.loading_placeholder"))
        self.compare_text.config(text=t("route_history.comparison_hint"), fg=Theme.MUTED)

    def _setup_ui(self):
        root = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        root.pack(fill="both", expand=True)

        header = ctk.CTkFrame(root, fg_color=Theme.BG)
        header.pack(fill="x", pady=(0, 12))
        lbl = ctk.CTkLabel(header, text=t("route_history.header"), fg_color=Theme.BG, text_color=Theme.ACCENT, font=Theme.FONT_TITLE)
        lbl.pack(side="left")
        self._i18n_tag(lbl, "route_history.header")
        btn = ActionButton(header, t("route_history.refresh"), self._load_async, color=Theme.SURFACE2)
        btn.pack(side="right", padx=(8, 0))
        self._i18n_tag(btn, "route_history.refresh")
        btn = ActionButton(header, t("route_history.open_planner"), self._open_selected_on_map, color=Theme.ACCENT)
        btn.pack(side="right")
        self._i18n_tag(btn, "route_history.open_planner")

        filters = ctk.CTkFrame(root, fg_color=Theme.SURFACE)
        filters.pack(fill="x", pady=(0, 12))

        lbl = ctk.CTkLabel(filters, text=t("route_history.search_label"), fg_color=Theme.SURFACE, text_color=Theme.TEXT)
        lbl.pack(side="left")
        self._i18n_tag(lbl, "route_history.search_label")
        self.search_var = tk.StringVar()
        self.e_search = StyledEntry(filters, textvariable=self.search_var, width=28)
        self.e_search.pack(side="left", padx=(8, 14))
        self.e_search.bind("<Return>", lambda _e: self._reset_and_load())

        lbl = ctk.CTkLabel(filters, text=t("route_history.profile_label"), fg_color=Theme.SURFACE, text_color=Theme.TEXT)
        lbl.pack(side="left")
        self._i18n_tag(lbl, "route_history.profile_label")
        self.c_profile = ctk.CTkComboBox(
            filters,
            values=["", "truck", "truck_fast", "truck_cheap", "truck_safe", "truck_short"],
            width=14,
            state="readonly",
            command=lambda v: self._reset_and_load(),
        )
        self.c_profile.pack(side="left", padx=(8, 14))

        lbl = ctk.CTkLabel(filters, text=t("route_history.truck_label"), fg_color=Theme.SURFACE, text_color=Theme.TEXT)
        lbl.pack(side="left")
        self._i18n_tag(lbl, "route_history.truck_label")
        self.truck_var = tk.StringVar()
        self.e_truck = StyledEntry(filters, textvariable=self.truck_var, width=18)
        self.e_truck.pack(side="left", padx=(8, 14))
        self.e_truck.bind("<Return>", lambda _e: self._reset_and_load())

        self.include_archived_var = tk.BooleanVar(value=False)
        cb = StyledCheckbutton(
            filters,
            text=t("route_history.archived_checkbox"),
            variable=self.include_archived_var,
            bg=Theme.SURFACE,
            activebackground=Theme.SURFACE,
            command=self._reset_and_load,
        )
        cb.pack(side="left", padx=(0, 12))
        self._i18n_tag(cb, "route_history.archived_checkbox")

        btn = ActionButton(filters, t("route_history.apply_button"), self._reset_and_load, color=Theme.SURFACE2)
        btn.pack(side="left")
        self._i18n_tag(btn, "route_history.apply_button")
        btn = ActionButton(filters, t("route_history.reset_button"), self._reset_filters, color=Theme.SURFACE2)
        btn.pack(side="left", padx=(8, 0))
        self._i18n_tag(btn, "route_history.reset_button")

        body = tk.PanedWindow(root, orient="horizontal", sashrelief="flat", bg=Theme.BG)
        body.pack(fill="both", expand=True)

        left = ctk.CTkFrame(body, fg_color=Theme.BG)
        right = ctk.CTkFrame(body, fg_color=Theme.BG, width=360)
        body.add(left, minsize=760)
        body.add(right, minsize=340)

        self._setup_table(left)
        self._setup_side_panel(right)

    def _setup_table(self, parent):
        table_frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
        table_frame.pack(fill="both", expand=True)

        cols = ("origin", "destination", "date", "truck", "distance", "duration", "profile")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended")
        headings = {
            "origin": t("route_history.table_origin"),
            "destination": t("route_history.table_destination"),
            "date": t("route_history.table_datetime"),
            "truck": t("route_history.table_truck"),
            "distance": t("route_history.table_distance"),
            "duration": t("route_history.table_duration"),
            "profile": t("route_history.table_profile"),
        }
        heading_keys = {
            "origin": "route_history.table_origin",
            "destination": "route_history.table_destination",
            "date": "route_history.table_datetime",
            "truck": "route_history.table_truck",
            "distance": "route_history.table_distance",
            "duration": "route_history.table_duration",
            "profile": "route_history.table_profile",
        }
        widths = {
            "origin": 170,
            "destination": 170,
            "date": 145,
            "truck": 130,
            "distance": 90,
            "duration": 90,
            "profile": 95,
        }
        for col in cols:
            self.tree.heading(col, text=headings[col], command=lambda c=col: self._sort(c))
            self.tree.column(col, width=widths[col], anchor="w")
            self._tree_heading_keys.append((col, heading_keys[col]))

        ysb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        xsb.pack(side="bottom", fill="x")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _e: self._open_selected_on_map())

        footer = ctk.CTkFrame(parent, fg_color=Theme.BG)
        footer.pack(fill="x")
        self.page_label = ctk.CTkLabel(footer, text="", fg_color=Theme.BG, text_color=Theme.MUTED)
        self.page_label.pack(side="left")
        btn = ActionButton(footer, t("route_history.next_button"), self._next_page, color=Theme.SURFACE2)
        btn.pack(side="right", padx=(8, 0))
        self._i18n_tag(btn, "route_history.next_button")
        btn = ActionButton(footer, t("route_history.prev_button"), self._prev_page, color=Theme.SURFACE2)
        btn.pack(side="right")
        self._i18n_tag(btn, "route_history.prev_button")

        actions = ctk.CTkFrame(parent, fg_color=Theme.SURFACE)
        actions.pack(fill="x", pady=(0, 2))
        btn = ActionButton(actions, t("route_history.reopen_button"), self._open_selected_on_map, color=Theme.ACCENT)
        btn.pack(side="left", padx=4)
        self._i18n_tag(btn, "route_history.reopen_button")
        btn = ActionButton(actions, t("route_history.calculate_trip_button"), self._calculate_trip_selected, color=Theme.ACCENT_SUCCESS)
        btn.pack(side="left", padx=4)
        self._i18n_tag(btn, "route_history.calculate_trip_button")
        btn = ActionButton(actions, t("route_history.recalculate_button"), self._recalculate_selected, color=Theme.SURFACE2)
        btn.pack(side="left", padx=4)
        self._i18n_tag(btn, "route_history.recalculate_button")
        btn = ActionButton(actions, t("route_history.duplicate_button"), self._duplicate_selected, color=Theme.SURFACE2)
        btn.pack(side="left", padx=4)
        self._i18n_tag(btn, "route_history.duplicate_button")
        btn = ActionButton(actions, t("route_history.export_button"), self._export_selected, color=Theme.SURFACE2)
        btn.pack(side="left", padx=4)
        self._i18n_tag(btn, "route_history.export_button")
        btn = ActionButton(actions, t("route_history.archive_button"), self._archive_selected, color=Theme.ORANGE)
        btn.pack(side="left", padx=4)
        self._i18n_tag(btn, "route_history.archive_button")
        btn = ActionButton(actions, t("route_history.delete_button"), self._delete_selected, color=Theme.DANGER)
        btn.pack(side="right", padx=4)
        self._i18n_tag(btn, "route_history.delete_button")

    def _setup_side_panel(self, parent):
        stats = ctk.CTkFrame(parent, fg_color=Theme.SURFACE)
        stats.pack(fill="x", padx=(12, 0), pady=(0, 12))
        lbl = ctk.CTkLabel(stats, text=t("route_history.section_stats"), fg_color=Theme.SURFACE, text_color=Theme.ACCENT, font=Theme.FONT_BOLD)
        lbl.pack(anchor="w")
        self._i18n_tag(lbl, "route_history.section_stats")
        self.stats_text = ctk.CTkLabel(stats, text=t("route_history.loading_placeholder"), fg_color=Theme.SURFACE, text_color=Theme.TEXT, justify="left", wraplength=320)
        self.stats_text.pack(fill="x", pady=(8, 0))

        preview = ctk.CTkFrame(parent, fg_color=Theme.SURFACE)
        preview.pack(fill="x", padx=(12, 0), pady=(0, 12))
        lbl = ctk.CTkLabel(preview, text=t("route_history.section_map"), fg_color=Theme.SURFACE, text_color=Theme.ACCENT, font=Theme.FONT_BOLD)
        lbl.pack(anchor="w")
        self._i18n_tag(lbl, "route_history.section_map")
        map_host = ctk.CTkFrame(preview, fg_color=Theme.SURFACE, height=200)
        map_host.pack(fill="x", pady=(8, 0))
        map_host.pack_propagate(False)
        self._map_preview = HistoryMapPreview(map_host, height=200)

        compare = ctk.CTkFrame(parent, fg_color=Theme.SURFACE)
        compare.pack(fill="both", expand=True, padx=(12, 0))
        lbl = ctk.CTkLabel(compare, text=t("route_history.section_comparison"), fg_color=Theme.SURFACE, text_color=Theme.ACCENT, font=Theme.FONT_BOLD)
        lbl.pack(anchor="w")
        self._i18n_tag(lbl, "route_history.section_comparison")
        self.compare_text = ctk.CTkLabel(
            compare,
            text=t("route_history.comparison_hint"),
            fg_color=Theme.SURFACE,
            text_color=Theme.MUTED,
            justify="left",
            wraplength=320,
        )
        self.compare_text.pack(fill="x", pady=(8, 10))
        btn = ActionButton(compare, t("route_history.compare_button"), self._compare_selected, color=Theme.SURFACE2)
        btn.pack(fill="x")
        self._i18n_tag(btn, "route_history.compare_button")

    def _reset_filters(self):
        self.search_var.set("")
        self.c_profile.set("")
        self.truck_var.set("")
        self.include_archived_var.set(False)
        self._reset_and_load()

    def _reset_and_load(self):
        self.current_page = 0
        self._load_async()

    def _load_async(self):
        self.page_label.config(text=t("route_history.loading_routes"))
        args = self._current_query()
        threading.Thread(target=self._load_worker, args=(args,), daemon=True).start()

    def _load_worker(self, args):
        try:
            rows = self.service.search_routes(**args)
            total = self.service.count_routes(
                search=args["search"],
                truck=args["truck"],
                profile=args["profile"],
                include_archived=args["include_archived"],
            )
            stats = self.service.get_statistics(include_archived=args["include_archived"])
            self._safe_after(0, lambda: self._apply_rows(rows, total, stats))
        except Exception as exc:
            error = str(exc)
            self._safe_after(0, lambda: messagebox.showerror(t("route_history.title"), error))

    def _current_query(self):
        return {
            "search": self.search_var.get().strip(),
            "truck": self.truck_var.get().strip(),
            "profile": self.c_profile.get().strip(),
            "include_archived": self.include_archived_var.get(),
            "sort_by": self.sort_by,
            "sort_dir": self.sort_dir,
            "limit": self.PAGE_SIZE,
            "offset": self.current_page * self.PAGE_SIZE,
        }

    def _apply_rows(self, rows, total, stats):
        self.rows_by_tree_id = {}
        self.total_rows = total
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in rows:
            iid = str(row.id)
            self.rows_by_tree_id[iid] = row
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    self._short(row.origin),
                    self._short(row.destination),
                    row.last_calculated_at.replace("T", " ").replace("Z", ""),
                    row.truck_label or row.truck_id or "",
                    f"{row.total_distance_km or 0:.1f} km",
                    format_duration_minutes(row.duration_min),
                    row.profile or "",
                ),
            )
        pages = max(1, math.ceil(total / self.PAGE_SIZE))
        self.page_label.config(text=t("route_history.page_info").format(current=self.current_page + 1, total=pages, count=self.total_rows))
        self._render_stats(stats)
        if self._map_preview:
            self._map_preview.clear()

    def _sort(self, column):
        mapping = {
            "origin": "origin",
            "destination": "destination",
            "date": "last_calculated_at",
            "truck": "truck",
            "distance": "distance",
            "duration": "duration",
            "profile": "profile",
        }
        new_sort = mapping.get(column, "last_calculated_at")
        if self.sort_by == new_sort:
            self.sort_dir = "ASC" if self.sort_dir == "DESC" else "DESC"
        else:
            self.sort_by = new_sort
            self.sort_dir = "ASC"
        self._reset_and_load()

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._load_async()

    def _next_page(self):
        if (self.current_page + 1) * self.PAGE_SIZE < self.total_rows:
            self.current_page += 1
            self._load_async()

    def _on_select(self, _event=None):
        selected = self.tree.selection()
        self._selected_route_id = int(selected[0]) if selected else None
        if self._selected_route_id:
            self._preview_token += 1
            token = self._preview_token
            route_id = self._selected_route_id
            threading.Thread(
                target=self._preview_worker,
                args=(route_id, token),
                daemon=True,
            ).start()
        elif self._map_preview:
            self._map_preview.clear()

    def _preview_worker(self, route_id: int, token: int) -> None:
        record = self.service.load_route(route_id)

        def apply() -> None:
            if token != self._preview_token:
                return
            self._show_map_preview(record)

        try:
            self._safe_after(0, apply)
        except tk.TclError:
            pass

    def _show_map_preview(self, record: Optional[RouteHistoryRecord]) -> None:
        if not self._map_preview:
            return
        if not record or not record.geometry:
            self._map_preview.clear()
            return
        self._map_preview.show_route(record.geometry)

    def _on_close(self) -> None:
        unregister_listener(self._on_language_changed)
        self._preview_token += 1
        if self._map_preview:
            self._map_preview.destroy()
            self._map_preview = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def _selected_ids(self):
        return [int(iid) for iid in self.tree.selection()]

    def _load_record_or_warn(self):
        if not self._selected_route_id:
            messagebox.showwarning(t("route_history.title"), t("route_history.warning_select_route"))
            return None
        record = self.service.load_route(self._selected_route_id)
        if not record:
            messagebox.showerror(t("route_history.error_not_found"), t("route_history.error_not_found"))
        return record

    def _open_selected_on_map(self):
        record = self._load_record_or_warn()
        if not record:
            return
        planner = RoutePlannerTab(self.parent, self.db, controller=self.controller)
        planner.load_history_route(record, draw=True)

    def _calculate_trip_selected(self):
        """Load route in planner so user can calculate a profit from it."""
        record = self._load_record_or_warn()
        if not record:
            return
        planner = RoutePlannerTab(self.parent, self.db, controller=self.controller)
        planner.load_history_route(record, draw=True)

    def _recalculate_selected(self):
        record = self._load_record_or_warn()
        if not record:
            return
        planner = RoutePlannerTab(self.parent, self.db, controller=self.controller)
        planner.load_history_route(record, draw=True)
        planner.win.after(300, planner._on_calculate_click)

    def _duplicate_selected(self):
        if not self._selected_route_id:
            messagebox.showwarning(t("route_history.title"), t("route_history.warning_select_route"))
            return
        self.service.duplicate_route(self._selected_route_id)
        self._load_async()

    def _archive_selected(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showwarning(t("route_history.title"), t("route_history.warning_select_one"))
            return
        for route_id in ids:
            self.service.archive_route(route_id)
        self._load_async()

    def _delete_selected(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showwarning(t("route_history.title"), t("route_history.warning_select_one"))
            return
        if not messagebox.askyesno(t("route_history.confirm_delete_title"), t("route_history.confirm_delete_msg").format(len(ids))):
            return
        for route_id in ids:
            self.service.delete_route(route_id)
        self._load_async()

    def _export_selected(self):
        record = self._load_record_or_warn()
        if not record:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv")],
            title=t("route_history.export_dialog"),
        )
        if not path:
            return
        fmt = "csv" if path.lower().endswith(".csv") else "json"
        if fmt == "json":
            payload = self.service.export_route(self._selected_route_id, "json") or asdict(record)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
        else:
            payload = self.service.export_route(self._selected_route_id, "csv") or ""
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(payload)
        messagebox.showinfo(t("route_history.export_dialog"), t("route_history.export_success").format(path))

    def _compare_selected(self):
        ids = self._selected_ids()
        if len(ids) != 2:
            self.compare_text.config(text=t("route_history.comparison_error"), fg=Theme.WARNING)
            return
        a = self.service.load_route(ids[0])
        b = self.service.load_route(ids[1])
        if not a or not b:
            return
        dist_delta = (b.total_distance_km or 0) - (a.total_distance_km or 0)
        dur_delta = (b.duration_min or 0) - (a.duration_min or 0)
        profile_a = a.profile or "-"
        profile_b = b.profile or "-"
        text = t("route_history.comparison_result").format(
            a=ids[0], b=ids[1],
            d_dist=dist_delta, d_dur=dur_delta,
            p_a=profile_a, p_b=profile_b,
        )
        self.compare_text.config(text=text, fg=Theme.TEXT)

    def _render_stats(self, stats):
        destinations = stats.get("most_common_destinations") or []
        dest_text = ", ".join(f"{name} ({count})" for name, count in destinations[:3]) or t("route_history.stats_none")
        text = t("route_history.stats_summary").format(
            count=stats.get('route_count', 0),
            dist=stats.get('total_distance_km', 0),
            dests=dest_text,
        )
        self.stats_text.config(text=text)

    def _money(self, value):
        return "" if value is None else f"{float(value):.2f}"

    def _short(self, value, limit=42):
        value = str(value or "")
        return value if len(value) <= limit else value[: limit - 1] + "…"

    def _safe_after(self, delay, callback):
        target = self.win or self.frame or self.parent
        try:
            aid = target.after(delay, callback)
            self._after_ids.append(aid)
            return aid
        except Exception:
            pass
            return None
