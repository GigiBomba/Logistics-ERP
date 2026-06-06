"""Linear-style sidebar navigation panel."""
import logging
import tkinter as tk
import customtkinter as ctk
from ui.theme import COLORS, FONTS, S
from services.i18n import t, register_listener, unregister_listener

logger = logging.getLogger(__name__)

W_EXPANDED  = 220
W_COLLAPSED = 52
ITEM_H      = 36
ITEM_RADIUS = 6


class NavPanel(ctk.CTkFrame):
    """Fixed sidebar with hover expand/collapse, grouped nav items,
    and persistent state via PreferencesManager.
    """

    def __init__(self, parent, on_select=None, prefs=None, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_surface"])
        kwargs.setdefault("width", W_EXPANDED)
        kwargs.setdefault("corner_radius", 0)
        super().__init__(parent, **kwargs)
        self.pack_propagate(False)
        self._on_select = on_select
        self._prefs = prefs
        self._active_key = None
        self._expanded = True
        self._groups = []
        self._items = {}      # key -> widget dict
        self._labels = {}     # key -> text label widget
        self._group_labels = {}  # group name -> header widget
        self._item_i18n_keys = {}  # key -> i18n key for refresh
        self._group_i18n_keys = {}  # group name -> i18n key for refresh
        self._tooltip = None
        self._tooltip_id = None

        self._load_state()
        self._build()
        register_listener(self._on_language_changed)

    # ── Persistence ────────────────────────────────────────────────────

    def _load_state(self):
        if self._prefs is None:
            return
        try:
            raw = self._prefs._get_setting("sidebar_expanded")
            if raw is not None:
                self._expanded = raw.lower() == "true"
        except Exception:
            pass

    def _save_state(self):
        if self._prefs is None:
            return
        try:
            self._prefs._set_setting("sidebar_expanded", "true" if self._expanded else "false")
        except Exception:
            pass

    # ── Build ──────────────────────────────────────────────────────────

    def _build(self):
        # Right border line
        self._border = ctk.CTkFrame(
            self, fg_color=COLORS["border"], width=1, corner_radius=0
        )
        self._border.pack(side="right", fill="y")

        self._build_top_section()

        # Scrollable area for nav items
        self._scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_elevated"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        self._scroll_frame.pack(fill="both", expand=True, padx=0, pady=(S["2"], 0))

        # Container inside scrollable frame
        self._container = ctk.CTkFrame(
            self._scroll_frame, fg_color="transparent"
        )
        self._container.pack(fill="both", expand=True, padx=0, pady=0)

        # Bottom settings area
        self._bottom_frame = ctk.CTkFrame(
            self, fg_color="transparent", height=ITEM_H + 8
        )
        self._bottom_frame.pack(fill="x", side="bottom", pady=(0, 0))
        self._bottom_frame.pack_propagate(False)

        # Divider above settings
        ctk.CTkFrame(
            self._bottom_frame, fg_color=COLORS["border"],
            height=1, corner_radius=0
        ).pack(fill="x", side="top")

        self._settings_item = None

        # Hover expand/collapse bindings
        self.bind("<Enter>", self._on_cursor_enter, add="+")
        self.bind("<Leave>", self._on_cursor_leave, add="+")

        # Apply initial width
        self.configure(width=W_EXPANDED if self._expanded else W_COLLAPSED)

    def _build_top_section(self):
        top = ctk.CTkFrame(self, fg_color="transparent", height=56)
        top.pack(fill="x")
        top.pack_propagate(False)

        # "O" monogram icon — visible in both expanded and collapsed
        icon_outer = ctk.CTkFrame(
            top, fg_color=COLORS["accent"], corner_radius=6,
            width=28, height=28
        )
        icon_outer.pack(side="left", padx=(14, 0), pady=14)
        icon_outer.pack_propagate(False)
        ctk.CTkLabel(
            icon_outer, text="O", font=FONTS["h3"],
            text_color="white"
        ).place(relx=0.5, rely=0.5, anchor="center")

        # App name — hidden when collapsed
        self._app_name_frame = ctk.CTkFrame(top, fg_color="transparent")
        self._app_name_frame.pack(side="left", padx=(10, 0), fill="y")
        ctk.CTkLabel(
            self._app_name_frame, text=t("app.name"),
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w"
        ).pack(anchor="w")
        ctk.CTkLabel(
            self._app_name_frame, text=t("app.subtitle"),
            font=FONTS["label"],
            text_color=COLORS["text_muted"],
            anchor="w"
        ).pack(anchor="w")

        if not self._expanded:
            self._app_name_frame.pack_forget()

        self._toggle_btn = ctk.CTkButton(
            top, text="\u00ab" if self._expanded else "\u00bb", width=24, height=24,
            fg_color="transparent", text_color=COLORS["text_muted"],
            hover_color=COLORS["bg_elevated"],
            font=("Segoe UI", 12),
            command=self._toggle_expand,
        )
        self._toggle_btn.pack(side="right", padx=(0, 4), pady=14)

        # Divider below top section
        ctk.CTkFrame(
            self, fg_color=COLORS["border"],
            height=1, corner_radius=0
        ).pack(fill="x")

    # ── Public API ─────────────────────────────────────────────────────

    def add_group(self, name: str, i18n_key: str = None):
        """Add a visual group separator with optional label."""
        if i18n_key:
            self._group_i18n_keys[name] = i18n_key
        if self._groups:
            ctk.CTkFrame(
                self._container, fg_color="transparent", height=1
            ).pack(fill="x", padx=8, pady=(S["2"], S["2"]))

        lbl = ctk.CTkLabel(
            self._container,
            text=name.upper(),
            font=FONTS["label"],
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        lbl.pack(anchor="w", padx=14, pady=(S["1"], 0))
        self._group_labels[name] = lbl
        if not self._expanded:
            lbl.pack_forget()

        self._groups.append(name)

    def add_item(self, key: str, icon: str, label: str, group: str = None, i18n_key: str = None):
        """Add a navigation item. If group is provided and not yet created, a group is added."""
        if i18n_key:
            self._item_i18n_keys[key] = i18n_key
        if group and group not in self._groups:
            self.add_group(group)

        frame = ctk.CTkFrame(
            self._container,
            fg_color="transparent",
            corner_radius=ITEM_RADIUS,
            height=ITEM_H,
            cursor="hand2",
        )
        frame.pack(fill="x", padx=6, pady=1)
        frame.pack_propagate(False)

        # Left accent bar (hidden by default)
        accent = ctk.CTkFrame(
            frame, fg_color="transparent", width=3, corner_radius=2
        )
        accent.pack(side="left", fill="y")
        accent.pack_propagate(False)

        # Icon label
        icon_lbl = ctk.CTkLabel(
            frame,
            text=icon,
            font=("Segoe UI", 14),
            text_color=COLORS["text_muted"],
            width=32,
        )
        icon_lbl.pack(side="left")

        # Text label
        text_lbl = ctk.CTkLabel(
            frame,
            text=label,
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        text_lbl.pack(side="left", fill="x", expand=True, padx=(0, S["3"]))
        if not self._expanded:
            text_lbl.pack_forget()

        # Bindings
        def on_enter(e, k=key):
            if k != self._active_key:
                self._set_hover(k, True)

        def on_leave(e, k=key):
            if k != self._active_key:
                self._set_hover(k, False)

        def on_click(e, k=key):
            self.select(k)

        for w in (frame, accent, icon_lbl, text_lbl):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)

        self._items[key] = {
            "frame": frame,
            "accent": accent,
            "icon": icon_lbl,
            "label": text_lbl,
            "text": label,
        }
        self._labels[key] = text_lbl

    def add_settings_item(self, key: str, icon: str, label: str):
        """Add the settings item pinned to the bottom."""
        frame = ctk.CTkFrame(
            self._bottom_frame,
            fg_color="transparent",
            corner_radius=ITEM_RADIUS,
            height=ITEM_H,
            cursor="hand2",
        )
        frame.pack(fill="x", pady=(4, 0))
        frame.pack_propagate(False)

        accent = ctk.CTkFrame(
            frame, fg_color="transparent", width=3, corner_radius=2
        )
        accent.pack(side="left", fill="y")
        accent.pack_propagate(False)

        icon_lbl = ctk.CTkLabel(
            frame,
            text=icon,
            font=("Segoe UI", 14),
            text_color=COLORS["text_muted"],
            width=32,
        )
        icon_lbl.pack(side="left")

        text_lbl = ctk.CTkLabel(
            frame,
            text=label,
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        text_lbl.pack(side="left", fill="x", expand=True, padx=(0, S["3"]))
        if not self._expanded:
            text_lbl.pack_forget()

        def on_enter(e, k=key):
            if k != self._active_key:
                self._set_hover(k, True)

        def on_leave(e, k=key):
            if k != self._active_key:
                self._set_hover(k, False)

        def on_click(e, k=key):
            self.select(k)

        for w in (frame, accent, icon_lbl, text_lbl):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)

        self._items[key] = {
            "frame": frame,
            "accent": accent,
            "icon": icon_lbl,
            "label": text_lbl,
            "text": label,
        }
        self._labels[key] = text_lbl
        self._settings_item = key

    def select(self, key: str):
        if self._active_key:
            self._deactivate(self._active_key)
        self._active_key = key
        self._activate(key)
        if self._on_select:
            self._on_select(key)

    def highlight(self, key: str):
        if key == self._active_key:
            return
        if self._active_key:
            self._deactivate(self._active_key)
        self._active_key = key
        self._activate(key)

    def get_active_key(self):
        return self._active_key

    def refresh_labels(self, key_label_map: dict):
        for key, text in key_label_map.items():
            if key in self._items:
                self._items[key]["label"].configure(text=text)
                self._items[key]["text"] = text

    # ── Internal state helpers ─────────────────────────────────────────

    def _activate(self, key):
        item = self._items.get(key)
        if not item:
            return
        item["frame"].configure(fg_color=COLORS["bg_elevated"])
        item["accent"].configure(fg_color=COLORS["accent"])
        item["icon"].configure(text_color=COLORS["accent_text"])
        item["label"].configure(
            text_color=COLORS["text_primary"], font=FONTS["body_bold"]
        )

    def _deactivate(self, key):
        item = self._items.get(key)
        if not item:
            return
        item["frame"].configure(fg_color="transparent")
        item["accent"].configure(fg_color="transparent")
        item["icon"].configure(text_color=COLORS["text_muted"])
        item["label"].configure(
            text_color=COLORS["text_secondary"], font=FONTS["body"]
        )

    def _set_hover(self, key: str, hovered: bool):
        item = self._items.get(key)
        if not item:
            return
        if key == self._active_key:
            return
        item["frame"].configure(
            fg_color=COLORS["bg_elevated"] if hovered else "transparent"
        )

    # ── Hover expand/collapse ───────────────────────────────────────────

    def _toggle_expand(self):
        self._set_width(W_COLLAPSED if self._expanded else W_EXPANDED)

    def _on_cursor_enter(self, event):
        if not self._expanded:
            self._set_width(W_EXPANDED)

    def _on_cursor_leave(self, event):
        sx = self.winfo_rootx()
        sy = self.winfo_rooty()
        sw = self.winfo_width()
        sh = self.winfo_height()
        cx, cy = event.x_root, event.y_root
        if not (sx <= cx <= sx + sw and sy <= cy <= sy + sh):
            self._set_width(W_COLLAPSED)

    def _set_width(self, width: int):
        should_expand = (width == W_EXPANDED)
        if should_expand == self._expanded:
            return
        self._expanded = should_expand
        self._save_state()
        self.configure(width=width)

        if self._expanded:
            self._app_name_frame.pack(side="left", padx=(10, 0))
        else:
            self._app_name_frame.pack_forget()

        self._toggle_btn.configure(text="\u00ab" if self._expanded else "\u00bb")

        for name, lbl in self._group_labels.items():
            if self._expanded:
                lbl.pack(anchor="w", padx=14, pady=(S["1"], 0))
            else:
                lbl.pack_forget()

        for key, item in self._items.items():
            text_lbl = item["label"]
            if self._expanded:
                text_lbl.pack(side="left", fill="x", expand=True, padx=(0, S["3"]))
            else:
                text_lbl.pack_forget()

    # ── Language refresh ───────────────────────────────────────────────

    def _on_language_changed(self, lang):
        try:
            logger.debug("NavPanel language change -> %s | refreshing %d items + %d groups",
                        lang,
                        sum(1 for k in self._item_i18n_keys if k in self._labels),
                        sum(1 for n in self._group_i18n_keys if n in self._group_labels))
            self._refresh_labels()
        except Exception:
            logger.exception("NavPanel language refresh failed")

    def _refresh_labels(self):
        for key, i18n_key in self._item_i18n_keys.items():
            if key in self._labels:
                try:
                    self._labels[key].config(text=t(i18n_key))
                except Exception:
                    pass
        for name, i18n_key in self._group_i18n_keys.items():
            if name in self._group_labels:
                try:
                    self._group_labels[name].config(text=t(i18n_key).upper())
                except Exception:
                    pass

    def destroy(self):
        unregister_listener(self._on_language_changed)
        super().destroy()
