"""New sidebar navigation panel — manual toggle, no hover collapse, grouped items."""
import logging
import tkinter as tk
import customtkinter as ctk
from ui.theme import COLORS, FONTS, S
from services.i18n import t, register_listener, unregister_listener

logger = logging.getLogger(__name__)


class NavPanel(ctk.CTkFrame):
    """Fixed sidebar with manual expand/collapse toggle, grouped nav items,
    and persistent state via PreferencesManager.
    """

    EXPANDED_WIDTH = 220
    COLLAPSED_WIDTH = 56
    ITEM_HEIGHT = 40
    TOP_BAR_HEIGHT = 52
    ACCENT_BAR_WIDTH = 3

    def __init__(self, parent, on_select=None, prefs=None, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_surface"])
        kwargs.setdefault("width", self.EXPANDED_WIDTH)
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
        self._separators = []    # separator widgets
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
        self._border = tk.Frame(self, bg=COLORS["border"], width=1)
        self._border.place(relx=1.0, rely=0, relheight=1, anchor="ne")

        # Top bar
        self._top_bar = ctk.CTkFrame(self, fg_color=COLORS["bg_surface"], height=self.TOP_BAR_HEIGHT)
        self._top_bar.pack(fill="x", pady=0)
        self._top_bar.pack_propagate(False)

        self._app_name_lbl = tk.Label(
            self._top_bar,
            text="FleetOS",
            bg=COLORS["bg_surface"],
            fg=COLORS["text_primary"],
            font=FONTS["h2"],
        )
        self._app_name_lbl.pack(side="left", padx=(12, 0))
        if not self._expanded:
            self._app_name_lbl.pack_forget()

        # Scrollable area for nav items
        self._scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg_surface"], scrollbar_button_color=COLORS["border"]
        )
        self._scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Container inside scrollable frame
        self._container = ctk.CTkFrame(self._scroll_frame, fg_color=COLORS["bg_surface"])
        self._container.pack(fill="both", expand=True, padx=0, pady=0)

        # Bottom settings area
        self._bottom_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_surface"], height=self.ITEM_HEIGHT + 8)
        self._bottom_frame.pack(fill="x", side="bottom", pady=(0, 0))
        self._bottom_frame.pack_propagate(False)

        # Divider above settings
        self._bottom_divider = tk.Frame(self._bottom_frame, bg=COLORS["border"], height=1)
        self._bottom_divider.pack(fill="x", side="top", padx=8, pady=(0, 0))

        self._settings_item = None

        # Hover expand/collapse bindings
        self.bind("<Enter>", self._on_cursor_enter, add="+")
        self.bind("<Leave>", self._on_cursor_leave, add="+")

        # Apply initial width
        self.configure(width=self.EXPANDED_WIDTH if self._expanded else self.COLLAPSED_WIDTH)

    # ── Public API ─────────────────────────────────────────────────────

    def add_group(self, name: str, i18n_key: str = None):
        """Add a visual group separator with optional label."""
        if i18n_key:
            self._group_i18n_keys[name] = i18n_key
        if self._groups:
            sep = tk.Frame(self._container, bg=COLORS["border"], height=1)
            sep.pack(fill="x", padx=8, pady=(S["2"], S["2"]))
            self._separators.append(sep)

        lbl = tk.Label(
            self._container,
            text=name,
            bg=COLORS["bg_surface"],
            fg=COLORS["text_muted"],
            font=FONTS["label"],
        )
        lbl.pack(anchor="w", padx=12, pady=(S["1"], 0))
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

        frame = tk.Frame(self._container, bg=COLORS["bg_surface"], height=self.ITEM_HEIGHT, cursor="hand2")
        frame.pack(fill="x", pady=(1, 1))
        frame.pack_propagate(False)

        # Left accent bar (hidden by default)
        accent = tk.Frame(frame, bg=COLORS["accent"], width=0)
        accent.pack(side="left", fill="y")
        accent.pack_propagate(False)

        # Icon label
        icon_lbl = tk.Label(
            frame,
            text=icon,
            bg=COLORS["bg_surface"],
            fg=COLORS["text_muted"],
            font=FONTS["h2"],
            width=3,
            anchor="center",
        )
        icon_lbl.pack(side="left", padx=(8, 0))

        # Text label
        text_lbl = tk.Label(
            frame,
            text=label,
            bg=COLORS["bg_surface"],
            fg=COLORS["text_secondary"],
            font=FONTS["small"],
            anchor="w",
        )
        text_lbl.pack(side="left", fill="x", expand=True, padx=(12, 8))
        if not self._expanded:
            text_lbl.pack_forget()

        # Bindings
        frame.bind("<Button-1>", lambda e, k=key: self.select(k))
        icon_lbl.bind("<Button-1>", lambda e, k=key: self.select(k))
        text_lbl.bind("<Button-1>", lambda e, k=key: self.select(k))

        frame.bind("<Enter>", lambda e, f=frame, i=icon_lbl, l=text_lbl, k=key:
                   self._on_item_enter(f, i, l, k))
        frame.bind("<Leave>", lambda e, f=frame, i=icon_lbl, l=text_lbl, k=key:
                   self._on_item_leave(f, i, l, k))
        icon_lbl.bind("<Enter>", lambda e, f=frame, i=icon_lbl, l=text_lbl, k=key:
                      self._on_item_enter(f, i, l, k))
        icon_lbl.bind("<Leave>", lambda e, f=frame, i=icon_lbl, l=text_lbl, k=key:
                      self._on_item_leave(f, i, l, k))
        text_lbl.bind("<Enter>", lambda e, f=frame, i=icon_lbl, l=text_lbl, k=key:
                       self._on_item_enter(f, i, l, k))
        text_lbl.bind("<Leave>", lambda e, f=frame, i=icon_lbl, l=text_lbl, k=key:
                       self._on_item_leave(f, i, l, k))

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
        frame = tk.Frame(self._bottom_frame, bg=COLORS["bg_surface"], height=self.ITEM_HEIGHT, cursor="hand2")
        frame.pack(fill="x", pady=(4, 0))
        frame.pack_propagate(False)

        accent = tk.Frame(frame, bg=COLORS["accent"], width=0)
        accent.pack(side="left", fill="y")
        accent.pack_propagate(False)

        icon_lbl = tk.Label(
            frame,
            text=icon,
            bg=COLORS["bg_surface"],
            fg=COLORS["text_muted"],
            font=FONTS["h2"],
            width=3,
            anchor="center",
        )
        icon_lbl.pack(side="left", padx=(8, 0))

        text_lbl = tk.Label(
            frame,
            text=label,
            bg=COLORS["bg_surface"],
            fg=COLORS["text_secondary"],
            font=FONTS["small"],
            anchor="w",
        )
        text_lbl.pack(side="left", fill="x", expand=True, padx=(12, 8))
        if not self._expanded:
            text_lbl.pack_forget()

        frame.bind("<Button-1>", lambda e, k=key: self.select(k))
        icon_lbl.bind("<Button-1>", lambda e, k=key: self.select(k))
        text_lbl.bind("<Button-1>", lambda e, k=key: self.select(k))

        frame.bind("<Enter>", lambda e, f=frame, i=icon_lbl, l=text_lbl, k=key:
                   self._on_item_enter(f, i, l, k))
        frame.bind("<Leave>", lambda e, f=frame, i=icon_lbl, l=text_lbl, k=key:
                   self._on_item_leave(f, i, l, k))
        icon_lbl.bind("<Enter>", lambda e, f=frame, i=icon_lbl, l=text_lbl, k=key:
                     self._on_item_enter(f, i, l, k))
        icon_lbl.bind("<Leave>", lambda e, f=frame, i=icon_lbl, l=text_lbl, k=key:
                     self._on_item_leave(f, i, l, k))
        text_lbl.bind("<Enter>", lambda e, f=frame, i=icon_lbl, l=text_lbl, k=key:
                      self._on_item_enter(f, i, l, k))
        text_lbl.bind("<Leave>", lambda e, f=frame, i=icon_lbl, l=text_lbl, k=key:
                      self._on_item_leave(f, i, l, k))

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
        item["frame"].configure(bg=COLORS["bg_elevated"])
        item["accent"].configure(width=self.ACCENT_BAR_WIDTH)
        item["icon"].configure(bg=COLORS["bg_elevated"], fg=COLORS["text_primary"])
        item["label"].configure(
            bg=COLORS["bg_elevated"], fg=COLORS["text_primary"], font=FONTS["small"]
        )

    def _deactivate(self, key):
        item = self._items.get(key)
        if not item:
            return
        item["frame"].configure(bg=COLORS["bg_surface"])
        item["accent"].configure(width=0)
        item["icon"].configure(bg=COLORS["bg_surface"], fg=COLORS["text_muted"])
        item["label"].configure(
            bg=COLORS["bg_surface"], fg=COLORS["text_secondary"], font=FONTS["small"]
        )

    def _on_item_enter(self, frame, icon, label, key):
        if key == self._active_key:
            return
        frame.configure(bg=COLORS["bg_elevated"])
        icon.configure(bg=COLORS["bg_elevated"], fg=COLORS["accent"])
        label.configure(bg=COLORS["bg_elevated"], fg=COLORS["text_primary"])
        if not self._expanded:
            self._show_tooltip(key, frame)

    def _on_item_leave(self, frame, icon, label, key):
        if key == self._active_key:
            return
        frame.configure(bg=COLORS["bg_surface"])
        icon.configure(bg=COLORS["bg_surface"], fg=COLORS["text_muted"])
        label.configure(bg=COLORS["bg_surface"], fg=COLORS["text_secondary"])
        self._hide_tooltip()

    # ── Toggle ─────────────────────────────────────────────────────────

    # ── Hover expand/collapse ───────────────────────────────────────────

    def _on_cursor_enter(self, event):
        self._set_width(self.EXPANDED_WIDTH)

    def _on_cursor_leave(self, event):
        sx = self.winfo_rootx()
        sy = self.winfo_rooty()
        sw = self.winfo_width()
        sh = self.winfo_height()
        cx, cy = event.x_root, event.y_root
        if not (sx <= cx <= sx + sw and sy <= cy <= sy + sh):
            self._set_width(self.COLLAPSED_WIDTH)

    def _set_width(self, width: int):
        should_expand = (width == self.EXPANDED_WIDTH)
        if should_expand == self._expanded:
            return
        self._expanded = should_expand
        self._save_state()
        self.configure(width=width)

        if self._expanded:
            self._app_name_lbl.pack(side="left", padx=(12, 0))
        else:
            self._app_name_lbl.pack_forget()

        for name, lbl in self._group_labels.items():
            if self._expanded:
                lbl.pack(anchor="w", padx=12, pady=(S["1"], 0))
            else:
                lbl.pack_forget()

        for key, item in self._items.items():
            text_lbl = item["label"]
            if self._expanded:
                text_lbl.pack(side="left", fill="x", expand=True, padx=(12, 8))
            else:
                text_lbl.pack_forget()

        for sep in self._separators:
            if self._expanded:
                sep.pack(fill="x", padx=8, pady=(S["2"], S["2"]))
            else:
                sep.pack_forget()

    # ── Tooltip (collapsed mode only) ──────────────────────────────────

    def _show_tooltip(self, key, anchor_widget):
        if self._tooltip_id:
            self.after_cancel(self._tooltip_id)
        self._tooltip_id = self.after(400, lambda: self._create_tooltip(key, anchor_widget))

    def _hide_tooltip(self):
        if self._tooltip_id:
            self.after_cancel(self._tooltip_id)
            self._tooltip_id = None
        if self._tooltip:
            self._tooltip.destroy()
            self._tooltip = None

    def _create_tooltip(self, key, anchor_widget):
        self._tooltip_id = None
        text = self._items.get(key, {}).get("text", "")
        if not text:
            return
        x = anchor_widget.winfo_rootx() + anchor_widget.winfo_width() + 8
        y = anchor_widget.winfo_rooty()
        tw = tk.Toplevel(self)
        tw.overrideredirect(True)
        tw.configure(bg=COLORS["bg_elevated"])
        tw.attributes("-topmost", True)
        lbl = tk.Label(
            tw,
            text=text,
            bg=COLORS["bg_elevated"],
            fg=COLORS["text_primary"],
            font=FONTS["small"],
            padx=8,
            pady=4,
        )
        lbl.pack()
        tw.update_idletasks()
        tw.geometry(f"+{x}+{y}")
        self._tooltip = tw

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
                    self._group_labels[name].config(text=t(i18n_key))
                except Exception:
                    pass

    def destroy(self):
        unregister_listener(self._on_language_changed)
        super().destroy()
