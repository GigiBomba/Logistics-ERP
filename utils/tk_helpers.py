import tkinter as tk


def safe_destroy(widget):
    try:
        widget.destroy()
    except tk.TclError:
        pass
