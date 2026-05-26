import tkinter as tk
from tkinter import messagebox
from services.i18n import t, register_listener, unregister_listener
from ui.styles import Theme
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class AnalyticsView:
    def __init__(self, parent, db, prefs=None):
        self.win = tk.Toplevel(parent)
        self.win.title(f"📈 {t('analytics.title')}")
        self.win.geometry("1400x850")
        Theme.apply(self.win)
        self.db = db
        from services.preferences import PreferencesManager
        self.prefs = prefs or PreferencesManager(db)
        self._i18n_widgets = []
        self._chart_texts = []
        self._leg_lines = []
        self._pie_texts = []
        self._pie_keys = []
        self._fig = None
        self._canvas = None
        self._axes = None
        self._no_data_text = None
        self._setup_ui()
        self.win.bind("<Destroy>", self._on_destroy)
        register_listener(self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_destroy(self, event=None):
        if event is not None and event.widget != self.win:
            return
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
        self.win.title(f"📈 {t('analytics.title')}")
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.config(text=f"{prefix}{t(key)}")
            except Exception:
                pass
        for text_obj, key in self._chart_texts:
            try:
                text_obj.set_text(t(key))
            except Exception:
                pass
        for line, key in self._leg_lines:
            try:
                line.set_label(t(key))
            except Exception:
                pass
        for text_obj, key in zip(self._pie_texts, self._pie_keys):
            try:
                text_obj.set_text(t(key))
            except Exception:
                pass
        if self._no_data_text is not None:
            try:
                self._no_data_text.set_text(t("analytics.no_financial_data"))
            except Exception:
                pass
        if self._fig is not None and self._canvas is not None:
            try:
                if self._leg_lines:
                    for ax in self._axes.flat:
                        try:
                            ax.legend()
                        except Exception:
                            pass
                self._fig.tight_layout()
                self._canvas.draw_idle()
            except Exception:
                pass

    def _setup_ui(self):
        lbl = tk.Label(self.win, text=f"📊 {t('analytics.header')}", 
                 font=("Segoe UI", 16, "bold"), bg=Theme.BG, fg=Theme.TEXT)
        lbl.pack(pady=20)
        self._i18n_tag(lbl, "analytics.header", "📊 ")
        
        container = tk.Frame(self.win, bg=Theme.BG)
        container.pack(fill="both", expand=True, padx=20, pady=10)
        self._chart_container = container
        
        try:
            p_truck, p_driver, rev_exp = self.db.get_analytics_data()
            
            if not p_truck and not p_driver and not rev_exp:
                lbl = tk.Label(container, text=t("analytics.empty_state"), 
                         bg=Theme.BG, fg=Theme.MUTED, font=("Segoe UI", 12))
                lbl.pack(expand=True)
                self._i18n_tag(lbl, "analytics.empty_state")
                return

            fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=90)
            fig.patch.set_facecolor(Theme.BG)
            self._fig = fig
            self._axes = axes

            ax1 = axes[0, 0]
            ax1.set_facecolor(Theme.SURFACE)
            if p_truck:
                trucks = [str(x['truck_number']) for x in p_truck]
                profits_t = [float(x['p']) for x in p_truck]
                ax1.barh(trucks, profits_t, color=Theme.ACCENT)
            title1 = ax1.set_title(t("analytics.chart_top_trucks"), color=Theme.TEXT, fontsize=10)
            self._chart_texts.append((title1, "analytics.chart_top_trucks"))

            ax2 = axes[0, 1]
            ax2.set_facecolor(Theme.SURFACE)
            if rev_exp:
                months = [str(x['month']) for x in rev_exp]
                revs = [float(x['rev']) for x in rev_exp]
                exps = [float(x['exp']) for x in rev_exp]
                line1 = ax2.plot(months, revs, marker='o', label=t("analytics.legend_revenue"), color=Theme.ACCENT_SUCCESS, linewidth=2)[0]
                line2 = ax2.plot(months, exps, marker='o', label=t("analytics.legend_expenses"), color=Theme.DANGER, linewidth=2)[0]
                self._leg_lines = [(line1, "analytics.legend_revenue"), (line2, "analytics.legend_expenses")]
                ax2.legend(fontsize=8, facecolor=Theme.SURFACE, labelcolor='white')
            title2 = ax2.set_title(t("analytics.chart_revenue_vs_expenses"), color=Theme.TEXT, fontsize=10)
            self._chart_texts.append((title2, "analytics.chart_revenue_vs_expenses"))

            ax3 = axes[1, 0]
            ax3.set_facecolor(Theme.SURFACE)
            if p_driver:
                drivers = [str(x['driver_name']) for x in p_driver]
                profits_d = [float(x['p']) for x in p_driver]
                ax3.bar(drivers, profits_d, color=Theme.PURPLE_SOFT)
                ax3.tick_params(axis='x', rotation=30)
            title3 = ax3.set_title(t("analytics.chart_profit_per_driver"), color=Theme.TEXT, fontsize=10)
            self._chart_texts.append((title3, "analytics.chart_profit_per_driver"))

            ax4 = axes[1, 1]
            ax4.set_facecolor(Theme.SURFACE)
            
            total_profit_sum = sum([float(x['p']) for x in p_truck]) if p_truck else 0
            total_exp_sum = sum([float(x['exp']) for x in rev_exp]) if rev_exp else 0
            
            if (total_profit_sum + total_exp_sum) > 0:
                sizes = [max(0, total_profit_sum), max(0, total_exp_sum)]
                patches, texts, autotexts = ax4.pie(sizes, labels=[t("analytics.pie_profit"), t("analytics.pie_expenses")], autopct='%1.1f%%', 
                        colors=[Theme.ACCENT_SUCCESS, Theme.BORDER], 
                        textprops={'color':"w", 'fontsize': 9}, startangle=140)
                self._pie_texts = texts
                self._pie_keys = ["analytics.pie_profit", "analytics.pie_expenses"]
            else:
                self._no_data_text = ax4.text(0.5, 0.5, t("analytics.no_financial_data"), color=Theme.MUTED, ha='center')
            
            title4 = ax4.set_title(t("analytics.chart_profit_expenses_ratio"), color=Theme.TEXT, fontsize=10)
            self._chart_texts.append((title4, "analytics.chart_profit_expenses_ratio"))

            for ax in axes.flat:
                ax.tick_params(colors=Theme.TEXT, labelsize=8)
                for spine in ax.spines.values():
                    spine.set_color(Theme.BORDER)
            
            plt.tight_layout()
            
            canvas = FigureCanvasTkAgg(fig, master=container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            self._canvas = canvas

        except Exception as e:
            lbl = tk.Label(container, text=t("analytics.render_error").format(e), 
                     bg=Theme.BG, fg=Theme.DANGER)
            lbl.pack(expand=True)
            self._i18n_tag(lbl, "analytics.render_error")
