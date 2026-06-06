"""Client revenue chart — matplotlib bar chart embedded in CTkFrame."""
import customtkinter as ctk
from datetime import datetime
from ui.theme import COLORS, FONTS

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class ClientRevenueChart(ctk.CTkFrame):
    def __init__(self, parent, service, client_id, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_base"])
        super().__init__(parent, **kwargs)
        self.service = service
        self.client_id = client_id
        self._fig = None
        self._mpl_canvas = None
        self._build()

    def _build(self):
        self._destroy_canvas()

        history = self.service.get_client_revenue_history(self.client_id, months=12)
        if not history:
            lbl = ctk.CTkLabel(self, text="No revenue data yet", fg_color=COLORS["bg_base"],
                               text_color=COLORS["text_muted"], font=FONTS["small"])
            lbl.pack(pady=10)
            return

        history.reverse()
        months = [r["month"] for r in history]
        revenues = [r["revenue"] or 0 for r in history]
        profits = [r["profit"] or 0 for r in history]

        plt.style.use('dark_background')
        self._fig, ax = plt.subplots(figsize=(5, 2.2), dpi=95)
        self._fig.patch.set_facecolor(COLORS["bg_base"])
        ax.set_facecolor(COLORS["bg_base"])

        x = range(len(months))
        width = 0.35
        bars1 = ax.bar([i - width / 2 for i in x], revenues, width, label="Revenue",
                       color=COLORS["accent"], alpha=0.85)
        bars2 = ax.bar([i + width / 2 for i in x], profits, width, label="Profit",
                       color=COLORS["success"] if sum(profits) >= 0 else COLORS["danger"], alpha=0.85)

        short_months = [m[-2:] for m in months]
        ax.set_xticks(x)
        ax.set_xticklabels(short_months, fontsize=7, color=COLORS["text_muted"])
        ax.tick_params(colors=COLORS["text_muted"], labelsize=7, pad=2)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v/1000:.0f}k" if v else "0"))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(COLORS["border"])
        ax.spines["bottom"].set_color(COLORS["border"])
        ax.legend(fontsize=7, framealpha=0.3, facecolor=COLORS["bg_surface"],
                  edgecolor=COLORS["border"], labelcolor=COLORS["text_primary"])
        self._fig.tight_layout(pad=0.8)

        self._mpl_canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._mpl_canvas.draw()
        self._mpl_canvas.get_tk_widget().pack(fill="both", expand=True)

    def refresh(self, client_id=None):
        if client_id:
            self.client_id = client_id
        self._build()

    def _destroy_canvas(self):
        for w in self.winfo_children():
            w.destroy()
        if self._mpl_canvas:
            self._mpl_canvas.get_tk_widget().destroy()
            self._mpl_canvas = None
        if self._fig:
            plt.close(self._fig)
            self._fig = None

    def destroy(self):
        self._destroy_canvas()
        super().destroy()
