"""Search and filter bar for the dispatch board kanban."""
import customtkinter as ctk
from services.i18n import t
from ui.theme import COLORS, FONTS


STATUS_OPTIONS = ["Planned", "Loading", "In Transit", "Delivered", "Cancelled"]


class DispatchSearchBar(ctk.CTkFrame):
    """Search + status filter bar above kanban columns."""

    def __init__(self, parent, on_search=None, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_surface"], corner_radius=8, **kwargs)
        self._on_search = on_search
        self._query_var = ctk.StringVar()
        self._status_vars = {}
        self._result_lbl = None

        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", padx=8, pady=6)

        search_icon = ctk.CTkLabel(inner, text="\U0001f50d", fg_color="transparent",
                                   text_color=COLORS["text_muted"], font=FONTS["label"])
        search_icon.pack(side="left", padx=(4, 2))

        self._entry = ctk.CTkEntry(
            inner,
            textvariable=self._query_var,
            placeholder_text=t("dispatch_board.search_placeholder"),
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"],
            font=FONTS["body"],
            height=30,
            corner_radius=6,
        )
        self._entry.pack(side="left", fill="x", expand=True, padx=(2, 8))
        self._entry.bind("<KeyRelease>", lambda e: self._fire_search())
        self._query_var.trace_add("write", lambda *a: self._fire_search())

        status_frame = ctk.CTkFrame(inner, fg_color="transparent")
        status_frame.pack(side="left", padx=(0, 4))

        lbl = ctk.CTkLabel(status_frame, text="", fg_color="transparent",
                          text_color=COLORS["text_muted"], font=FONTS["label"])
        lbl.pack(side="left", padx=(0, 2))

        for s in STATUS_OPTIONS:
            var = ctk.BooleanVar(value=True)
            self._status_vars[s] = var
            colors_map = {
                "Planned": COLORS["chip_planned"],
                "Loading": COLORS["chip_loading"],
                "In Transit": COLORS["chip_transit"],
                "Delivered": COLORS["chip_delivered"],
                "Cancelled": COLORS["chip_cancelled"],
            }
            chip_color = colors_map.get(s, COLORS["chip_idle"])
            cb = ctk.CTkCheckBox(
                status_frame, text=s, variable=var,
                fg_color=chip_color, hover_color=chip_color,
                border_color=COLORS["border"], checkmark_color="#ffffff",
                text_color=COLORS["text_secondary"], font=FONTS["label"],
                command=self._fire_search,
                width=20, height=20,
            )
            cb.pack(side="left", padx=2)

        clear_btn = ctk.CTkButton(
            inner, text="\u2715", fg_color=COLORS["bg_elevated"],
            text_color=COLORS["text_muted"], font=FONTS["small"],
            cursor="hand2", width=28, height=28, corner_radius=6,
            command=self._clear,
        )
        clear_btn.pack(side="left", padx=(2, 0))

        self._result_lbl = ctk.CTkLabel(
            self, text="", fg_color="transparent",
            text_color=COLORS["text_muted"], font=FONTS["label"]
        )
        self._result_lbl.pack(anchor="w", padx=12, pady=(0, 4))

    def _fire_search(self):
        if self._on_search:
            query = self._query_var.get().strip().lower()
            statuses = [s for s, v in self._status_vars.items() if v.get()]
            self._on_search(query, statuses)

    def _clear(self):
        self._query_var.set("")
        for v in self._status_vars.values():
            v.set(True)
        self._fire_search()

    def set_result_count(self, visible: int, total: int):
        if self._result_lbl:
            if visible < total:
                self._result_lbl.configure(text=f"Showing {visible} of {total} trips")
            else:
                self._result_lbl.configure(text=f"{total} trips")
