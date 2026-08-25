"""
Icon system for the ERP.
Icons are stored separately from translated text to avoid font/encoding issues.
Use iconed(key, *args, **kwargs) to get icon-prefixed localized text.
Use t(key, *args, **kwargs) for text-only (no icon).
"""
from __future__ import annotations

from services.i18n import t

# ── Icon glyphs (from Unicode BMP — safe across all fonts) ──
_GLYPHS = {
    "maint":           "\u2699",   # ⚙ gear
    "maint_analytics": "\u2699",   # ⚙ gear
    "maint_timeline":  "\u2699",   # ⚙ gear
    "fuel":            "\u26FD",   # ⛽ fuel pump
}

# ── Per-key icon overrides (more specific than section prefix) ──
_KEY_ICONS = {
    # maint section
    "maint.title":              "\u2699",   # ⚙
    "maint.header":             "\u2699",   # ⚙
    "maint.close":              "\u2716",   # ✖
    "maint.refresh":            "\u21BB",   # ↻
    "maint.tab_history":        "\u2630",   # ☰
    "maint.tab_schedules":      "\u2611",   # ☑
    "maint.tab_health":         "\u2665",   # ♥
    "maint.control_panel_title":"\u2699",   # ⚙
    "maint.avg_health":         "\u2699",   # ⚙
    "maint.due_service":        "\u2699",   # ⚙
    "maint.overdue":            "\u26A0",   # ⚠
    "maint.cost_30d":           "\u20AC",   # €
    "maint.total_cost_kpi":     "\u20AC",   # €
    "maint.critical_count":     "\u26A0",   # ⚠
    "maint.warning_count":      "\u26A0",   # ⚠
    "maint.info_count":         "\u2139",   # ℹ
    "maint.no_alerts_filter":   "\u2714",   # ✔
    "maint.action_resolve":     "\u2713",   # ✓
    "maint.action_truck":       "\u26DF",   # ⛟
    "maint.action_trip":        "\u2192",   # →
    "maint.action_maint":       "\u2699",   # ⚙
    "maint.action_remind":      "\u270E",   # ✎
    "maint.flash_truck_copied": "\u26DF",   # ⛟
    "maint.flash_trip_copied":  "\u2192",   # →
    "maint.flash_maint_scheduled":"\u2699", # ⚙
    "maint.flash_reminder":     "\u270E",   # ✎
    "maint.refresh_score":      "\u21BB",   # ↻
    "maint.predictions":        "\u270E",   # ✎
    "maint.no_schedules":       "\u2718",   # ✘
    "maint.no_records":         "\u2718",   # ✘
    "maint.status_ok":          "\u2714",   # ✔
    "maint.status_overdue":     "\u2718",   # ✘
    "maint.status_due_soon":    "\u26A0",   # ⚠
    "maint.excellent":          "\u2714",   # ✔
    "maint.fair":               "\u26A0",   # ⚠
    "maint.critical_health":    "\u2718",   # ✘
    "maint.metric_score":       "\u2699",   # ⚙
    "maint.metric_compliance":  "\u2714",   # ✔
    "maint.metric_overdue":     "\u26A0",   # ⚠
    "maint.metric_recurring":   "\u21BB",   # ↻
    "maint.metric_downtime":    "\u23F0",   # ⏰
    "maint.predictions_title":  "\u270E",   # ✎
    "maint.predictions_header": "\u270E",   # ✎
    "maint.edit":               "\u270E",   # ✎
    "maint.save":               "\u2714",   # ✔
    "maint.cancel":             "\u2716",   # ✖
    "maint.delete":             "\u2718",   # ✘
    "maint.add_record":         "\u271A",   # ✚
    "maint.export":             "\u21E9",   # ⇩
    "maint.prev":               "\u25C0",   # ◀
    "maint.next":               "\u25B6",   # ▶
    "maint.filter_label":       "\u25BC",   # ▼
    "maint.form_title_add":     "\u271A",   # ✚
    "maint.form_title_edit":    "\u270E",   # ✎
    "maint.confirm_delete_title":"\u2718",   # ✘
    "maint.confirm_delete_msg": "",
    "maint.schedule_add":       "\u271A",   # ✚
    "maint.schedule_form_title_add":"\u271A", # ✚
    "maint.schedule_form_title_edit":"\u270E", # ✎
    "maint.form_attachment":    "\U0001F4CE",  # 📎
    "maint.form_no_attachment": "\u2718",   # ✘
    "maint.form_choose_file":   "\U0001F4C2",  # 📂
    # maint_analytics section
    "maint_analytics.title":    "\u2699",   # ⚙
    # maint_timeline section
    "maint_timeline.title":     "\u2699",   # ⚙
    # fuel section
    "fuel.section_title":       "\u26FD",   # ⛽
}

ICONS = _KEY_ICONS


def iconed(key, *args, **kwargs):
    """Return localized string with prepended icon.

    Usage:
        iconed("maint.title", truck_plate)  → "⚙ Karbantartás - TRK-001"
        iconed("maint.save")                → "✔ Mentés"
        iconed("common.no_data")            → "Nincs adat" (no icon)
    """
    text = t(key, *args, **kwargs) if (args or kwargs) else t(key)
    if text is None:
        text = key
    icon = _KEY_ICONS.get(key) or _GLYPHS.get(key.split(".")[0], "")
    if icon:
        return f"{icon} {text}"
    return text
