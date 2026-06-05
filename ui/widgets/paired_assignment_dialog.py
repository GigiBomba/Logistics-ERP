"""Paired assignment dialog for assigning truck + driver to a trip in one operation."""
import tkinter as tk
import customtkinter as ctk
from services.i18n import t
from ui.theme import COLORS, FONTS
from ui.styles import Theme


class PairedAssignmentDialog(ctk.CTkToplevel):
    """Side-by-side truck and driver picker with paired suggestion."""

    def __init__(self, parent, trip_data: dict, truck_items: list, driver_items: list,
                 paired_hint: str = "", on_assign_both=None,
                 on_assign_truck=None, on_assign_driver=None):
        super().__init__(parent)
        self.title(t("dispatch_board.pair_title"))
        self.geometry("600x500")
        self.configure(fg_color=COLORS["bg_surface"])
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self._trip_data = trip_data
        self._truck_items = truck_items
        self._driver_items = driver_items
        self._paired_hint = paired_hint
        self._on_assign_both = on_assign_both
        self._on_assign_truck = on_assign_truck
        self._on_assign_driver = on_assign_driver
        self._selected_truck = None
        self._selected_driver = None
        self._truck_widgets = {}
        self._driver_widgets = {}

        self._build()
        self.after(100, lambda: self.focus_set())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 8))
        ctk.CTkLabel(hdr, text=self._trip_data.get("trip_id", ""),
                     fg_color="transparent", text_color=COLORS["text_primary"],
                     font=FONTS["h2"]).pack(side="left")
        route = f"{self._trip_data.get('origin','?')} \u2192 {self._trip_data.get('destination','?')}"
        ctk.CTkLabel(hdr, text=route, fg_color="transparent",
                     text_color=COLORS["text_muted"], font=FONTS["small"]).pack(side="left", padx=12)

        lists_frame = ctk.CTkFrame(self, fg_color="transparent")
        lists_frame.pack(fill="both", expand=True, padx=12, pady=(4, 8))

        lists_frame.columnconfigure(0, weight=1)
        lists_frame.columnconfigure(1, weight=1)
        lists_frame.rowconfigure(0, weight=1)

        left = ctk.CTkFrame(lists_frame, fg_color=COLORS["bg_surface"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self._build_list_panel(left, "dispatch_board.pair_truck_label", self._truck_items,
                               self._truck_widgets, self._select_truck)

        right = ctk.CTkFrame(lists_frame, fg_color=COLORS["bg_surface"])
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self._build_list_panel(right, "dispatch_board.pair_driver_label", self._driver_items,
                               self._driver_widgets, self._select_driver)

        if self._paired_hint:
            hint_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_surface"], corner_radius=6)
            hint_frame.pack(fill="x", padx=12, pady=(0, 6))
            ctk.CTkLabel(hint_frame, text=self._paired_hint, fg_color="transparent",
                        text_color=COLORS["accent"], font=FONTS["small"]).pack(padx=10, pady=6)

        btn_row = ctk.CTkFrame(self, fg_color=COLORS["bg_elevated"], height=48)
        btn_row.pack(fill="x", side="bottom")
        btn_row.pack_propagate(False)

        ctk.CTkButton(btn_row, text=t("dispatch_board.pair_assign_both"),
                     fg_color=COLORS["accent"], text_color="#ffffff",
                     font=FONTS["body_bold"], cursor="hand2", height=30,
                     command=self._do_assign_both).pack(side="right", padx=(6, 12), pady=9)

        ctk.CTkButton(btn_row, text=t("dispatch_board.pair_assign_truck_only"),
                     fg_color="transparent", text_color=COLORS["text_secondary"],
                     font=FONTS["body_bold"], cursor="hand2", height=30,
                     command=self._do_assign_truck_only).pack(side="right", padx=6, pady=9)

        ctk.CTkButton(btn_row, text=t("dispatch_board.pair_assign_driver_only"),
                     fg_color="transparent", text_color=COLORS["text_secondary"],
                     font=FONTS["body_bold"], cursor="hand2", height=30,
                     command=self._do_assign_driver_only).pack(side="right", padx=6, pady=9)

        ctk.CTkButton(btn_row, text=t("dispatch_board.detail_cancel"),
                     fg_color=COLORS["bg_elevated"], text_color=COLORS["text_muted"],
                     font=FONTS["body_bold"], cursor="hand2", height=30,
                     command=self.destroy).pack(side="left", padx=12, pady=9)

    def _build_list_panel(self, parent, title_key, items, widget_map, select_fn):
        ctk.CTkLabel(parent, text=t(title_key), fg_color="transparent",
                    text_color=COLORS["text_primary"], font=FONTS["h3"]).pack(
            anchor="w", padx=8, pady=(8, 4))

        scroll = ctk.CTkScrollableFrame(parent, fg_color=COLORS["bg_surface"],
                                         scrollbar_button_color=COLORS["border"])
        scroll.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        colors = {
            "free": COLORS["success"],
            "returning": COLORS["warning"],
            "on_trip": COLORS["danger"],
            "blocked": COLORS["danger"],
        }

        for idx, item in enumerate(items):
            row = ctk.CTkFrame(scroll, fg_color=COLORS["bg_surface"], corner_radius=4, cursor="hand2")
            row.pack(fill="x", pady=1)
            item_id = idx
            widget_map[item_id] = row

            avail = item.get("available", True)
            dot_color = COLORS["success"] if avail else COLORS["danger"]
            if not avail and item.get("status_text", ""):
                pass

            dot = ctk.CTkFrame(row, fg_color=dot_color, width=8, height=8, corner_radius=4)
            dot.pack(side="left", padx=(6, 4), pady=8)
            dot.pack_propagate(False)

            fg = COLORS["text_primary"] if avail else COLORS["text_muted"]
            ctk.CTkLabel(row, text=item.get("label", "")[:24], fg_color="transparent",
                        text_color=fg, font=FONTS["small"], anchor="w").pack(
                side="left", padx=(2, 8))

            ctk.CTkLabel(row, text=item.get("sublabel", "")[:30], fg_color="transparent",
                        text_color=COLORS["text_muted"], font=FONTS["label"], anchor="w").pack(
                side="left", fill="x", expand=True, padx=(0, 8))

            st = item.get("status_text", "")
            if st:
                ctk.CTkLabel(row, text=st[:30], fg_color="transparent",
                            text_color=COLORS["warning"], font=FONTS["label"], anchor="e").pack(
                    side="right", padx=(4, 6))

            if avail:
                row.bind("<Enter>", lambda e, r=row: r.configure(fg_color=COLORS["bg_elevated"]))
                row.bind("<Leave>", lambda e, r=row: r.configure(fg_color=COLORS["bg_surface"]))
                row.bind("<Button-1>", lambda e, i=idx: select_fn(i))

    def _select_truck(self, idx):
        for wid in self._truck_widgets.values():
            wid.configure(fg_color=COLORS["bg_surface"])
        self._truck_widgets[idx].configure(fg_color=COLORS["accent_dim"])
        self._selected_truck = idx

    def _select_driver(self, idx):
        for wid in self._driver_widgets.values():
            wid.configure(fg_color=COLORS["bg_surface"])
        self._driver_widgets[idx].configure(fg_color=COLORS["accent_dim"])
        self._selected_driver = idx

    def _do_assign_both(self):
        truck_id = None
        driver_id = None
        if self._selected_truck is not None and self._selected_truck < len(self._truck_items):
            truck_id = self._truck_items[self._selected_truck].get("id")
        if self._selected_driver is not None and self._selected_driver < len(self._driver_items):
            driver_id = self._driver_items[self._selected_driver].get("id")

        if self._on_assign_both:
            self._on_assign_both(truck_id, driver_id)
        self.destroy()

    def _do_assign_truck_only(self):
        if self._selected_truck is not None and self._selected_truck < len(self._truck_items):
            truck_id = self._truck_items[self._selected_truck].get("id")
            if self._on_assign_truck:
                self._on_assign_truck(truck_id)
        self.destroy()

    def _do_assign_driver_only(self):
        if self._selected_driver is not None and self._selected_driver < len(self._driver_items):
            driver_id = self._driver_items[self._selected_driver].get("id")
            if self._on_assign_driver:
                self._on_assign_driver(driver_id)
        self.destroy()
