"""Dark-themed DateEntry wrapper that integrates with the Operion ERP colour system.

Wraps tkcalendar.DateEntry and applies COLORS from ui/theme.py so the calendar
popup and entry field match the application's dark aesthetic.
"""

import os
import sys
import tkinter as tk
from tkcalendar import DateEntry, Calendar

_theme_applied = False


def _apply_calendar_theme(cal: Calendar) -> None:
    """Push dark-theme colours into the Calendar popup widget."""
    from ui.theme import COLORS
    cal.configure(
        background=COLORS["bg_surface"],
        foreground=COLORS["text_primary"],
        selectbackground=COLORS["accent"],
        selectforeground="#ffffff",
        normalbackground=COLORS["bg_surface"],
        weekendbackground=COLORS["bg_surface"],
        othermonthbackground=COLORS["bg_base"],
        othermonthforeground=COLORS["text_muted"],
        othermonthwebackground=COLORS["bg_base"],
        othermonthweforeground=COLORS["text_muted"],
        weekendforeground=COLORS["accent"],
        headersbackground=COLORS["bg_elevated"],
        headersforeground=COLORS["text_secondary"],
        bordercolor=COLORS["border"],
        titleforeground=COLORS["text_primary"],
        arrowcolor=COLORS["text_secondary"],
        font=("Segoe UI", 10),
    )


def make_date_entry(parent, date_pattern="y-mm-dd",
                    placeholder="YYYY-MM-DD", height=38):
    """Create a dark-themed DateEntry that matches CTkEntry dimensions.

    Args:
        parent: parent widget
        date_pattern: tkcalendar date pattern ('y-mm-dd' = ISO format)
        placeholder: shown when field is empty
        height: entry height in px

    Returns:
        tkcalendar.DateEntry instance (tk.Entry subclass)
    """
    from ui.theme import COLORS

    global _theme_applied
    if not _theme_applied:
        _original_init = Calendar.__init__

        def _patched_init(self_cal, master=None, **kw):
            kw.setdefault("background", COLORS["bg_surface"])
            kw.setdefault("foreground", COLORS["text_primary"])
            kw.setdefault("selectbackground", COLORS["accent"])
            kw.setdefault("selectforeground", "#ffffff")
            kw.setdefault("normalbackground", COLORS["bg_surface"])
            kw.setdefault("weekendbackground", COLORS["bg_surface"])
            kw.setdefault("othermonthbackground", COLORS["bg_base"])
            kw.setdefault("othermonthforeground", COLORS["text_muted"])
            kw.setdefault("othermonthwebackground", COLORS["bg_base"])
            kw.setdefault("othermonthweforeground", COLORS["text_muted"])
            kw.setdefault("weekendforeground", COLORS["accent"])
            kw.setdefault("headersbackground", COLORS["bg_elevated"])
            kw.setdefault("headersforeground", COLORS["text_secondary"])
            kw.setdefault("bordercolor", COLORS["border"])
            kw.setdefault("titleforeground", COLORS["text_primary"])
            kw.setdefault("arrowcolor", COLORS["text_secondary"])
            kw.setdefault("font", ("Segoe UI", 10))
            _original_init(self_cal, master, **kw)

        Calendar.__init__ = _patched_init
        _theme_applied = True

    entry_style_kw = {
        "background": COLORS["bg_input"],
        "foreground": COLORS["text_primary"],
        "insertbackground": COLORS["text_primary"],
        "borderwidth": 0,
        "highlightthickness": 0,
        "relief": "flat",
    }

    entry_style_kw["disabledbackground"] = COLORS["bg_base"]
    entry_style_kw["disabledforeground"] = COLORS["text_muted"]

    date_entry = DateEntry(
        parent,
        date_pattern=date_pattern,
        width=0,
        height=1,
        **entry_style_kw,
    )
    date_entry.configure(font=("Segoe UI", 13))
    try:
        date_entry.configure(highlightbackground=COLORS["border"])
    except (AttributeError, tk.TclError):
        pass

    date_entry.delete(0, "end")
    date_entry._set_text("")
    date_entry._top_cal = None
    date_entry._placeholder = placeholder

    _orig_dropdown = date_entry.drop_down

    def _wrapped_dropdown():
        _orig_dropdown()
        if date_entry._top_cal:
            cal = date_entry._top_cal
            if cal.winfo_exists():
                _apply_calendar_theme(cal)

    date_entry.drop_down = _wrapped_dropdown

    def set_date(value):
        if value:
            try:
                date_entry.set_date(value)
            except Exception:
                date_entry.delete(0, "end")
                date_entry.insert(0, str(value))

    def clear_date():
        try:
            date_entry.delete(0, "end")
        except Exception:
            pass

    date_entry.set_date_str = set_date
    date_entry.clear = clear_date

    return date_entry
