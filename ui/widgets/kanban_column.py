import tkinter as tk
import customtkinter as ctk
import logging
from tkinter import ttk
from ui.styles import Theme
from ui.widgets.trip_card import TripCard
from services.i18n import t
from ui.theme import COLORS, FONTS

logger = logging.getLogger(__name__)


class KanbanColumn(ctk.CTkFrame):

    COLUMN_BG = COLORS["bg_base"]
    HEADER_BG = COLORS["bg_surface"]
    ACCENT_HEIGHT = 4

    STATUS_COLORS = {
        "Planned": COLORS["chip_planned"],
        "Loading": COLORS["chip_loading"],
        "In Transit": COLORS["chip_transit"],
        "Delivered": COLORS["chip_delivered"],
        "Cancelled": COLORS["chip_cancelled"],
    }

    def __init__(self, parent, status_key: str, title_key: str,
                 accent_color: str = None, on_card_click=None,
                 on_drag_start=None,
                 on_assign_truck=None, on_assign_driver=None,
                 show_load_older: bool = False,
                 on_load_older=None, on_retry=None, **kwargs):
        super().__init__(parent, fg_color=self.COLUMN_BG, **kwargs)
        self.status_key = status_key
        self.title_key = title_key
        self.accent_color = accent_color or self.STATUS_COLORS.get(status_key, COLORS["chip_planned"])
        self._on_card_click = on_card_click
        self._on_drag_start = on_drag_start
        self._on_assign_truck = on_assign_truck
        self._on_assign_driver = on_assign_driver
        self._show_load_older = show_load_older
        self._on_load_older = on_load_older
        self._on_retry = on_retry
        self._cards = []
        self._state = "idle"

        self._build_header()
        self._build_scrollable_area()
        self._build_load_older_button()

    def _build_header(self):
        accent_bar = ctk.CTkFrame(self, fg_color=self.accent_color, height=self.ACCENT_HEIGHT)
        accent_bar.pack(fill="x")
        accent_bar.pack_propagate(False)

        header_frame = ctk.CTkFrame(self, fg_color=self.HEADER_BG)
        header_frame.pack(fill="x")

        self._title_lbl = ctk.CTkLabel(header_frame, text=t(self.title_key),
                                       fg_color=self.HEADER_BG, text_color=Theme.TEXT,
                                       font=FONTS["h3"])
        self._title_lbl.pack(side="left", padx=(12, 0), pady=10)

        self._count_lbl = ctk.CTkLabel(header_frame, text=" • 0",
                                       fg_color=self.HEADER_BG, text_color=Theme.MUTED,
                                        font=FONTS["small"])
        self._count_lbl.pack(side="left", padx=(4, 12), pady=10)

    def _build_scrollable_area(self):
        self._scroll_frame = ctk.CTkScrollableFrame(self, fg_color=self.COLUMN_BG)
        self._scroll_frame.pack(fill="both", expand=True, padx=4, pady=(4, 8))

        self._loading_frame = ctk.CTkFrame(self._scroll_frame, fg_color=self.COLUMN_BG)
        self._loading_lbl = ctk.CTkLabel(self._loading_frame, text="",
                                         fg_color=self.COLUMN_BG, text_color=Theme.MUTED,
                                         font=FONTS["label"])
        self._loading_lbl.pack(pady=40)

        self._error_frame = ctk.CTkFrame(self._scroll_frame, fg_color=self.COLUMN_BG)
        self._error_lbl = ctk.CTkLabel(self._error_frame, text="",
                                       fg_color=self.COLUMN_BG, text_color=Theme.DANGER,
                                        font=FONTS["label"], wraplength=200,
                                       justify="center")
        self._error_lbl.pack(pady=(30, 8))
        self._retry_btn = ctk.CTkButton(self._error_frame,
                                        text=t("dispatch_board.retry"),
                                        fg_color=Theme.ACCENT, text_color=Theme.TEXT,
                                        font=FONTS["small"],
                                        cursor="hand2",
                                        command=self._handle_retry)
        self._retry_btn.pack()

    def _build_load_older_button(self):
        if not self._show_load_older:
            return
        self._load_older_frame = ctk.CTkFrame(self, fg_color=self.COLUMN_BG)
        self._load_older_btn = ctk.CTkButton(
            self._load_older_frame,
            text=t("dispatch_board.load_older"),
            fg_color=self.HEADER_BG, text_color=Theme.MUTED,
            font=FONTS["label"],
            cursor="hand2",
            command=self._handle_load_older,
        )
        self._load_older_btn.pack(pady=6, padx=10)
        self._load_older_frame.pack(fill="x", side="bottom")

    def _handle_retry(self):
        if self._on_retry:
            self._on_retry()

    def _handle_load_older(self):
        if self._on_load_older:
            self._on_load_older()

    def _clear_cards(self):
        for card in self._cards:
            card.destroy()
        self._cards.clear()
        self._loading_frame.pack_forget()
        self._error_frame.pack_forget()

    def show_loading(self):
        self._clear_cards()
        self._state = "loading"
        self._count_lbl.configure(text=" • ...")
        self._loading_lbl.configure(text=t("dispatch_board.loading"))
        self._loading_frame.pack(fill="x", pady=(0, 6))
        if self._show_load_older:
            self._load_older_frame.pack_forget()

    def show_error(self, error_msg: str):
        self._clear_cards()
        self._state = "error"
        self._count_lbl.configure(text=" • ⚠")
        self._error_lbl.configure(text=error_msg)
        self._error_frame.pack(fill="x", pady=(0, 6))
        if self._show_load_older:
            self._load_older_frame.pack_forget()

    def set_trips(self, trips: list):
        self._loading_frame.pack_forget()
        self._error_frame.pack_forget()
        self._state = "idle"

        # Build map of existing cards by trip_id_num for diff-based update
        existing = {}
        stale = list(self._cards)
        for card in list(self._cards):
            tid = card.trip_data.get("trip_id_num")
            if tid is not None:
                existing[tid] = card

        # Reuse or create cards; update data in place
        new_cards = []
        for trip in trips:
            tid = trip.get("trip_id_num")
            if tid is not None and tid in existing:
                card = existing[tid]
                card.update_data(trip)
                if card in stale:
                    stale.remove(card)
                new_cards.append(card)
            else:
                card = TripCard(self._scroll_frame, trip, on_click=self._on_card_click,
                               on_drag_start=self._on_drag_start,
                               on_assign_truck=self._on_assign_truck,
                               on_assign_driver=self._on_assign_driver)
                card.pack(fill="x", pady=(0, 6), padx=2)
                new_cards.append(card)

        # Remove cards no longer in the trip list
        for old_card in stale:
            old_card.destroy()

        self._cards = new_cards
        self._count_lbl.configure(text=f" • {len(trips)}")

        if self._show_load_older:
            self._load_older_frame.pack(fill="x", side="bottom")

    def refresh_title(self):
        self._title_lbl.configure(text=t(self.title_key))
        if self._show_load_older and hasattr(self, "_load_older_btn"):
            self._load_older_btn.configure(text=t("dispatch_board.load_older"))
        if hasattr(self, "_retry_btn"):
            self._retry_btn.configure(text=t("dispatch_board.retry"))

    def highlight_drop_zone(self):
        self.configure(border_width=2, border_color=self.accent_color)

    def unhighlight_drop_zone(self):
        self.configure(border_width=0)

    def highlight_valid(self):
        self.configure(border_width=2, border_color=COLORS["success"])

    def highlight_invalid(self):
        self.configure(border_width=2, border_color=COLORS["danger"])

    def add_card(self, card, index=0):
        self._loading_frame.pack_forget()
        self._error_frame.pack_forget()
        card.pack(in_=self._scroll_frame, fill="x", pady=(0, 6), padx=2)
        if index < len(self._cards):
            self._cards.insert(index, card)
        else:
            self._cards.append(card)
        self._update_count()

    def remove_card(self, card):
        if card in self._cards:
            self._cards.remove(card)
            card.pack_forget()
            self._update_count()

    def _update_count(self):
        self._count_lbl.configure(text=f" \u2022 {len(self._cards)}")


