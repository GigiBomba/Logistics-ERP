import tkinter as tk
import customtkinter as ctk
import logging
from ui.styles import Theme
from ui.theme import COLORS, FONTS
from services.i18n import t
from utils.tk_helpers import safe_destroy

logger = logging.getLogger(__name__)


class TripCard(ctk.CTkFrame):

    CARD_BG = Theme.SURFACE2
    CARD_BG_HOVER = Theme.SURFACE3
    CARD_BORDER = Theme.BORDER
    CARD_BORDER_HOVER = Theme.ACCENT
    CORNER_RADIUS = 8
    LEFT_ACCENT_WIDTH = 4

    STATUS_COLORS = {
        "Planned": COLORS["chip_planned"],
        "Loading": COLORS["chip_loading"],
        "In Transit": COLORS["chip_transit"],
        "Delivered": COLORS["chip_delivered"],
        "Cancelled": COLORS["chip_cancelled"],
    }

    STATUS_TRANSLATION_KEYS = {
        "Planned": "dispatch_board.col_planned",
        "Loading": "dispatch_board.col_loading",
        "In Transit": "dispatch_board.col_in_transit",
        "Delivered": "dispatch_board.col_delivered",
        "Cancelled": "dispatch_board.col_cancelled",
    }

    DELAYED_COLOR = COLORS["danger"]
    DELAYED_BG = COLORS["danger_dim"]

    def __init__(self, parent, trip_data: dict, on_click=None, on_drag_start=None,
                 on_assign_truck=None, on_assign_driver=None, on_select_changed=None,
                 on_assign_both=None, **kwargs):
        super().__init__(parent, fg_color=self.CARD_BG, **kwargs)
        self.trip_data = trip_data
        self._on_click = on_click
        self._on_drag_start = on_drag_start
        self._on_assign_truck = on_assign_truck
        self._on_assign_driver = on_assign_driver
        self._on_select_changed = on_select_changed
        self._on_assign_both = on_assign_both
        self._hovered = False
        self._drag_data = {"x": 0, "y": 0, "dragging": False}
        self._active_dropdown = None
        self._delayed = False
        self._selected = False

        self._truck_lbl = None
        self._truck_clear_btn = None
        self._driver_lbl = None
        self._driver_clear_btn = None
        self._accent_bar = None
        self._date_lbl = None
        self._delayed_chip = None
        self._content_frame = None

        self.configure(border_width=1, border_color=self.CARD_BORDER, corner_radius=8)

        self._build_card()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)
        if on_click:
            self.configure(cursor="hand2")

    def _build_card(self):
        d = self.trip_data
        status = d.get("status", "Planned")
        accent_color = self.STATUS_COLORS.get(status, COLORS["chip_planned"])

        self._accent_bar = ctk.CTkFrame(self, fg_color=accent_color, width=self.LEFT_ACCENT_WIDTH)
        self._accent_bar.pack(side="left", fill="y")
        self._accent_bar.pack_propagate(False)

        self._content_frame = ctk.CTkFrame(self, fg_color=self.CARD_BG)
        self._content_frame.pack(side="left", fill="both", expand=True)

        self._content_frame.bind("<Enter>", self._on_enter)
        self._content_frame.bind("<Leave>", self._on_leave)
        self._content_frame.bind("<ButtonPress-1>", self._on_press)
        self._content_frame.bind("<B1-Motion>", self._on_motion)
        self._content_frame.bind("<ButtonRelease-1>", self._on_release)

        row1 = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 3))
        self._bind_row(row1)

        trip_id = d.get("trip_id", t("common.na"))
        id_lbl = ctk.CTkLabel(row1, text=trip_id, fg_color="transparent", text_color=Theme.TEXT,
                              font=FONTS["small"])
        id_lbl.pack(side="left")
        self._bind_label(row1, id_lbl)

        chip_container = ctk.CTkFrame(row1, fg_color="transparent")
        chip_container.pack(side="right")

        self._delayed_chip = ctk.CTkFrame(chip_container, fg_color=self.DELAYED_COLOR)
        delayed_lbl = ctk.CTkLabel(self._delayed_chip, text=t("dispatch_board.delayed"),
                                   fg_color=self.DELAYED_COLOR, text_color=COLORS["text_primary"],
                                    font=FONTS["label"])
        delayed_lbl.pack()

        self._chip_frame = ctk.CTkFrame(chip_container, fg_color=accent_color)
        self._chip_frame.pack(side="right", padx=(4, 0))
        self._chip_lbl = ctk.CTkLabel(self._chip_frame, text=t(self.STATUS_TRANSLATION_KEYS.get(status, status)), fg_color=accent_color, text_color=COLORS["text_primary"],
                                      font=FONTS["label"])
        self._chip_lbl.pack()

        truck_row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        truck_row.pack(fill="x", pady=(0, 2))
        truck_row.bind("<Enter>", self._on_enter)
        truck_row.bind("<Leave>", self._on_leave)

        truck_icon = ctk.CTkLabel(truck_row, text="\U0001f69a", fg_color="transparent", text_color=Theme.MUTED,
                                  font=FONTS["label"])
        truck_icon.pack(side="left")

        plate = d.get("truck_plate", "")
        plate_text = plate if plate else t("dispatch_board.assign_truck")
        plate_color = Theme.TEXT if plate else Theme.MUTED
        self._truck_lbl = ctk.CTkLabel(truck_row, text=plate_text, fg_color="transparent", text_color=plate_color,
                                        font=FONTS["label"], cursor="hand2")
        self._truck_lbl.pack(side="left", padx=(4, 0))
        self._truck_lbl.bind("<Button-1>", self._on_truck_click)
        self._truck_lbl.bind("<Enter>", lambda e: self._truck_lbl.configure(text_color=Theme.ACCENT))
        self._truck_lbl.bind("<Leave>", lambda e: self._truck_lbl.configure(text_color=plate_color))

        if plate:
            self._truck_clear_btn = ctk.CTkLabel(truck_row, text="\u2715", fg_color="transparent",
                                                  text_color=Theme.MUTED, font=FONTS["label"],
                                                cursor="hand2")
            self._truck_clear_btn.pack(side="right", padx=(4, 0))
            self._truck_clear_btn.bind("<Button-1>", self._on_truck_clear)

        both_row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        both_row.pack(fill="x", pady=(0, 1))
        both_label = ctk.CTkLabel(both_row, text="\u26a1 " + t("dispatch_board.assign_both"),
                                  fg_color="transparent", text_color=Theme.ACCENT,
                                  font=FONTS["label"], cursor="hand2")
        both_label.pack(side="left", padx=(20, 0))
        both_label.bind("<Button-1>", self._on_both_click)
        both_label.bind("<Enter>", lambda e: both_label.configure(text_color=Theme.ACCENT_HOVER))
        both_label.bind("<Leave>", lambda e: both_label.configure(text_color=Theme.ACCENT))

        driver_row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        driver_row.pack(fill="x", pady=(0, 2))
        driver_row.bind("<Enter>", self._on_enter)
        driver_row.bind("<Leave>", self._on_leave)

        driver_icon = ctk.CTkLabel(driver_row, text="\U0001f464", fg_color="transparent", text_color=Theme.MUTED,
                                  font=FONTS["label"])
        driver_icon.pack(side="left")

        driver = d.get("driver_name", "")
        driver_text = driver if driver else t("dispatch_board.assign_driver")
        driver_color = Theme.TEXT if driver else Theme.MUTED
        self._driver_lbl = ctk.CTkLabel(driver_row, text=driver_text, fg_color="transparent", text_color=driver_color,
                                        font=FONTS["label"], cursor="hand2")
        self._driver_lbl.pack(side="left", padx=(4, 0))
        self._driver_lbl.bind("<Button-1>", self._on_driver_click)
        self._driver_lbl.bind("<Enter>", lambda e: self._driver_lbl.configure(text_color=Theme.ACCENT))
        self._driver_lbl.bind("<Leave>", lambda e: self._driver_lbl.configure(text_color=driver_color))

        if driver:
            self._driver_clear_btn = ctk.CTkLabel(driver_row, text="\u2715", fg_color="transparent",
                                                  text_color=Theme.MUTED, font=FONTS["label"],
                                                 cursor="hand2")
            self._driver_clear_btn.pack(side="right", padx=(4, 0))
            self._driver_clear_btn.bind("<Button-1>", self._on_driver_clear)

        row3 = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 2))
        self._bind_row(row3)

        origin = d.get("origin", "?")
        destination = d.get("destination", "?")
        route_text = f"{origin} \u2192 {destination}"
        route_lbl = ctk.CTkLabel(row3, text=route_text, fg_color="transparent", text_color=Theme.MUTED,
                                 font=FONTS["label"], anchor="w", wraplength=220,
                                 justify="left")
        route_lbl.pack(side="left", fill="x", expand=True)
        self._bind_label(row3, route_lbl)

        row4 = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        row4.pack(fill="x", pady=(0, 2))
        self._bind_row(row4)

        departure = d.get("departure_date", "")
        eta = d.get("eta", "")
        date_parts = []
        if departure:
            date_parts.append(f"\u25b6 {departure}")
        if eta:
            date_parts.append(f"\u25c0 {eta}")
        date_text = "  ".join(date_parts) if date_parts else ""
        if date_text:
            self._date_lbl = ctk.CTkLabel(row4, text=date_text, fg_color="transparent", text_color=Theme.MUTED,
                                          font=FONTS["label"])
            self._date_lbl.pack(side="left")
            self._bind_label(row4, self._date_lbl)

        alerts_count = d.get("alerts_count", 0)
        if alerts_count and alerts_count > 0:
            alert_frame = ctk.CTkFrame(self._content_frame, fg_color=Theme.DANGER)
            alert_frame.pack(fill="x", pady=(3, 0))
            alert_lbl = ctk.CTkLabel(alert_frame,
                                     text=f"\u26a0 {alerts_count} {t('dispatch_board.alerts')}",
                                     fg_color=Theme.DANGER, text_color=COLORS["text_primary"],
                                font=FONTS["label"])
            alert_lbl.pack()

        # Live indicator row (hidden by default)
        self._live_row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._live_dot = ctk.CTkLabel(
            self._live_row, text="\u25cf " + t("dispatch_board.live"),
            font=FONTS["label"],
            text_color=COLORS["success"],
        )
        self._live_dot.pack(side="left")
        self._live_speed = ctk.CTkLabel(
            self._live_row,
            text="",
            font=FONTS["mono"],
            text_color=COLORS["text_secondary"]
        )
        self._live_speed.pack(side="right")

    def set_live_position(self, position):
        """Show or hide live speed indicator on the card."""
        if position and position.status == "moving" and position.speed_kmh > 3:
            self._live_speed.configure(
                text=f"{position.speed_kmh:.0f} km/h"
            )
            self._live_row.pack(fill="x", padx=2, pady=(0, 2))
        else:
            self._live_row.pack_forget()

    def _bind_row(self, frame):
        frame.bind("<ButtonPress-1>", self._on_press)
        frame.bind("<B1-Motion>", self._on_motion)
        frame.bind("<ButtonRelease-1>", self._on_release)
        frame.bind("<Enter>", self._on_enter)
        frame.bind("<Leave>", self._on_leave)

    def _bind_label(self, parent, label):
        label.bind("<ButtonPress-1>", self._on_press)
        label.bind("<B1-Motion>", self._on_motion)
        label.bind("<ButtonRelease-1>", self._on_release)
        label.bind("<Enter>", self._on_enter)
        label.bind("<Leave>", self._on_leave)

    def _on_enter(self, event=None):
        self._hovered = True
        self.configure(fg_color=self.DELAYED_BG if self._delayed else self.CARD_BG_HOVER,
                       border_color=self.CARD_BORDER_HOVER)
        if self._content_frame:
            self._content_frame.configure(fg_color=self.DELAYED_BG if self._delayed else self.CARD_BG_HOVER)

    def _on_leave(self, event=None):
        self._hovered = False
        self.configure(fg_color=self.DELAYED_BG if self._delayed else self.CARD_BG,
                       border_color=self.CARD_BORDER)
        if self._content_frame:
            self._content_frame.configure(fg_color=self.DELAYED_BG if self._delayed else self.CARD_BG)

    def _on_click_handler(self, event=None):
        if self._on_click:
            self._on_click(self.trip_data)

    def _on_press(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._drag_data["dragging"] = False

    def _on_motion(self, event):
        if not self._drag_data["dragging"]:
            dx = abs(event.x - self._drag_data["x"])
            dy = abs(event.y - self._drag_data["y"])
            if dx > 5 or dy > 5:
                self._drag_data["dragging"] = True
                if self._on_drag_start:
                    self._on_drag_start(self, event)
        elif self._on_drag_start:
            self._on_drag_start(self, event)

    def _on_release(self, event):
        if not self._drag_data["dragging"]:
            if event.state & 0x0004:
                self._selected = not self._selected
                self._update_selection_visual()
                if self._on_select_changed:
                    self._on_select_changed(self, self._selected)
            else:
                self._on_click_handler(event)
        self._drag_data["dragging"] = False

    def set_selected(self, selected: bool):
        if self._selected != selected:
            self._selected = selected
            self._update_selection_visual()

    def is_selected(self) -> bool:
        return self._selected

    def _update_selection_visual(self):
        if self._selected:
            self.configure(border_color=Theme.ACCENT, border_width=2)
        else:
            self.configure(border_color=self.CARD_BORDER, border_width=1)

    def _on_truck_click(self, event):
        if self._active_dropdown:
            return
        if self._on_assign_truck:
            self._on_assign_truck(self)

    def _on_driver_click(self, event):
        if self._active_dropdown:
            return
        if self._on_assign_driver:
            self._on_assign_driver(self)

    def _on_both_click(self, event):
        if self._on_assign_both:
            self._on_assign_both(self)

    def _on_truck_clear(self, event):
        if self._on_assign_truck:
            self._on_assign_truck(self, clear=True)

    def _on_driver_clear(self, event):
        if self._on_assign_driver:
            self._on_assign_driver(self, clear=True)

    def update_truck(self, truck_plate: str, truck_id=None):
        self.trip_data["truck_plate"] = truck_plate
        if truck_id is not None:
            self.trip_data["truck_id"] = truck_id

        if truck_plate:
            self._truck_lbl.configure(text=truck_plate, text_color=Theme.TEXT)
            if not self._truck_clear_btn:
                self._truck_clear_btn = ctk.CTkLabel(self._truck_lbl.master, text="\u2715",
                                                    fg_color="transparent", text_color=Theme.MUTED,
                                                     font=FONTS["label"], cursor="hand2")
                self._truck_clear_btn.pack(side="right", padx=(4, 0))
                self._truck_clear_btn.bind("<Button-1>", self._on_truck_clear)
        else:
            self._truck_lbl.configure(text=t("dispatch_board.assign_truck"), text_color=Theme.MUTED)
            if self._truck_clear_btn:
                self._truck_clear_btn.destroy()
                self._truck_clear_btn = None

    def update_driver(self, driver_name: str, driver_id=None):
        self.trip_data["driver_name"] = driver_name
        if driver_id is not None:
            self.trip_data["driver_id"] = driver_id

        if driver_name:
            self._driver_lbl.configure(text=driver_name, text_color=Theme.TEXT)
            if not self._driver_clear_btn:
                self._driver_clear_btn = ctk.CTkLabel(self._driver_lbl.master, text="\u2715",
                                                     fg_color="transparent", text_color=Theme.MUTED,
                                                    font=FONTS["label"], cursor="hand2")
                self._driver_clear_btn.pack(side="right", padx=(4, 0))
                self._driver_clear_btn.bind("<Button-1>", self._on_driver_clear)
        else:
            self._driver_lbl.configure(text=t("dispatch_board.assign_driver"), text_color=Theme.MUTED)
            if self._driver_clear_btn:
                self._driver_clear_btn.destroy()
                self._driver_clear_btn = None

    def set_dropdown(self, dropdown):
        self._active_dropdown = dropdown

    def show_error(self, field: str, message: str):
        error_lbl = ctk.CTkLabel(self, text=message, fg_color=Theme.DANGER, text_color=Theme.TEXT,
                                font=FONTS["label"], padx=6, pady=2)
        error_lbl.pack(fill="x", pady=(2, 0))
        try:
            self.after(3000, lambda: safe_destroy(error_lbl))
        except tk.TclError:
            pass

    def set_delayed(self, delayed: bool, minutes_overdue: int = 0):
        if delayed == self._delayed:
            return
        self._delayed = delayed

        if delayed:
            self._accent_bar.configure(fg_color=self.DELAYED_COLOR)
            self._delayed_chip.pack(side="right", padx=(0, 4))
            self.configure(fg_color=self.DELAYED_BG)
            if self._content_frame:
                self._content_frame.configure(fg_color=self.DELAYED_BG)
            if self._date_lbl:
                if minutes_overdue >= 60:
                    hours = minutes_overdue // 60
                    overdue_text = t("dispatch_board.hours_overdue").format(hours)
                else:
                    overdue_text = t("dispatch_board.minutes_overdue").format(minutes_overdue)
                self._date_lbl.configure(text=overdue_text, text_color=self.DELAYED_COLOR)
        else:
            status = self.trip_data.get("status", "Planned")
            accent_color = self.STATUS_COLORS.get(status, COLORS["chip_planned"])
            self._accent_bar.configure(fg_color=accent_color)
            self._delayed_chip.pack_forget()
            self.configure(fg_color=self.CARD_BG)
            if self._content_frame:
                self._content_frame.configure(fg_color=self.CARD_BG)
            if self._date_lbl:
                departure = self.trip_data.get("departure_date", "")
                eta = self.trip_data.get("eta", "")
                date_parts = []
                if departure:
                    date_parts.append(f"\u25b6 {departure}")
                if eta:
                    date_parts.append(f"\u25c0 {eta}")
                date_text = "  ".join(date_parts) if date_parts else ""
                self._date_lbl.configure(text=date_text, text_color=Theme.MUTED)

    def update_data(self, new_data: dict):
        old_status = self.trip_data.get("status", "")
        new_status = new_data.get("status", "")
        self.trip_data = dict(new_data)

        # Update status chip + accent bar
        if new_status != old_status:
            self._set_status(new_status)

        # Update truck plate
        if self._truck_lbl:
            new_plate = new_data.get("truck_plate", "")
            self.trip_data["truck_plate"] = new_plate
            if new_plate:
                self._truck_lbl.configure(text=new_plate, text_color=Theme.TEXT)
            else:
                self._truck_lbl.configure(text=t("dispatch_board.assign_truck"), text_color=Theme.MUTED)

        # Update driver name
        if self._driver_lbl:
            new_driver = new_data.get("driver_name", "")
            self.trip_data["driver_name"] = new_driver
            if new_driver:
                self._driver_lbl.configure(text=new_driver, text_color=Theme.TEXT)
            else:
                self._driver_lbl.configure(text=t("dispatch_board.assign_driver"), text_color=Theme.MUTED)

        # Update alerts count
        new_alerts = new_data.get("alerts_count", 0)
        self.trip_data["alerts_count"] = new_alerts

    def _set_status(self, status: str):
        self.trip_data["status"] = status
        accent_color = self.STATUS_COLORS.get(status, COLORS["chip_planned"])
        self._accent_bar.configure(fg_color=accent_color)
        self._chip_frame.configure(fg_color=accent_color)
        self._chip_lbl.configure(text=t(self.STATUS_TRANSLATION_KEYS.get(status, status)), fg_color=accent_color)
