# Operion UI Visual Audit — Blind-Spot Verification Report

**Date:** 2026-08-24
**Scope:** Closes the §4.3 blind spots of `docs/UI_VISUAL_AUDIT_REPORT.md` — chart interiors, map interiors, and transient/interactive surfaces. Evidence-backed only (programmatic figure inspection, code analysis with file:line references). The model cannot ingest images, so all checks are programmatic/code-based, not pixel comparison.

---

## 1. Chart Interiors — VERIFIED (PASS)

**Method:** `tools/verify_chart_interiors.py` builds all 20 chart factories in `ui/plotly_charts.py` with sample data, extracts every color and font size from the resulting `go.Figure` JSON (excluding Plotly's built-in template defaults, which are never rendered), and checks each against the token set (`design_tokens.py` hex values + `plotly_theme.py` PLOTLY_* values).

**Result: 19/20 chart types fully token-backed.** All trace colors, layout colors, and fonts resolve to tokens:

- **Series palette** (`plotly_theme.py:42-53`): `PLOTLY_ACCENT`/`SUCCESS`/`WARNING`/`DANGER`/`INFO` are direct token references (`ACCENT`, `SUCCESS`, `WARNING`, `DANGER`, `INFO`). The "light" variants (`PLOTLY_SECONDARY #818cf8`, `SUCCESS_LIGHT #4ade80`, `WARNING_LIGHT #fbbf24`, `DANGER_LIGHT #f87171`, `INFO_LIGHT #93c5fd`) are the documented chart-palette extension — exempt per audit item 4 ("data-viz palettes intentionally extend beyond UI tokens").
- **Layout theme** (`plotly_theme.py:82-146` `_make_base_layout`): fully token-driven — paper/plot bg `BG_SURFACE`, font `TEXT_PRIMARY`, grid `BORDER_DEFAULT`, axis line `BORDER_FAINT`, hoverlabel `BG_ELEVATED`/`BORDER_STRONG`, legend `TEXT_SECONDARY`, colorway = token palette.
- **Chart factories** (`plotly_charts.py`): text fonts use `TEXT_PRIMARY`/`TEXT_SECONDARY`/`TEXT_MUTED`, marker outlines `BG_ELEVATED`, fills derived from token RGB via `_hex_to_alpha`/`_hex_to_rgb_int`.

**Documented exemptions (not violations):**
- `make_heatmap_chart` default `color_map="YlOrRd"` — a deliberate named data-viz colorscale (9 colors), exempt per item 4.
- 7px heatmap cell annotations — chart-context dense size below the UI typography minimum (10px), analogous to the micro-gap spacing exception.

**Renderer:** `figure_to_svg_bytes` produces output; headless render times out and falls back to the error SVG (expected — the harness patches the SVG renderer for this reason). The real render path was already verified end-to-end by the sparkline fix: all 6 analytics tabs render 4/4 sparklines via `QSvgRenderer`.

---

## 2. Map Interiors — VERIFIED (mostly exempt; 2 token-consistency items)

**Method:** code analysis of `ui/map/route_renderer.py`, `ui/map/map_widget.py`, `ui/map/map_helpers.py`, and the map consumers (`fleet_tracking_view.py`, `route_planner_view.py`, `route_history_view.py`).

| Surface | Value | Status |
|---|---|---|
| Avoid-route polygon | `#cc0000` (`route_renderer.py:27-28`) | **EXEMPT** — comment present: "Map overlay colors are intentionally exempt from design_tokens.py (web surface, not app chrome)" |
| Map background | `#09090b` (`map_widget.py:70-72`) | **EXEMPT** — same comment present |
| Primary route polyline | `#6366f1` inline default (`map_widget.py:249`) | ⚠️ Matches `COLOR_ACCENT_PRIMARY` but inlined, not referenced |
| Alt route polyline | `"gray"` string (`route_renderer.py:26`) | ⚠️ Could use `COLOR_NEUTRAL_DEFAULT` |
| Route markers (start/stop/dest) | `"green"`/`"blue"`/`"red"` (`route_renderer.py:23-25`) | Hardcoded Leaflet color-marker names — functional, non-token |
| Fleet status markers | `"moving"`/`"stopped"`/`"idle"`/`"offline"` → green/grey/orange/red (`fleet_tracking_view.py:75-80`) | Hardcoded Leaflet color-marker names — functional, non-token |
| Popups | Leaflet defaults (`map_widget.py:182-184`) | No explicit styling — relies on Leaflet/CartoDB dark_matter |
| Marker icon size | `[25,41]` (`map_widget.py:179`) | Hardcoded Leaflet default |

**Verdict:** the two audit-flagged colors (`#cc0000`, `#09090b`) are properly exempt with comments. The remaining hardcoded values are Leaflet web-surface styling (markers, popups, icon sizes) — functional and consistent with the web-surface exemption. Two token-consistency items are actionable (primary polyline `#6366f1` → `COLOR_ACCENT_PRIMARY`, alt route `"gray"` → `COLOR_NEUTRAL_DEFAULT`).

---

## 3. Transient/Interactive Surfaces — VERIFIED (mostly token-driven; 3 actionable items)

**Method:** code analysis of all 11 dialogs in `ui/dialogs/`, `ui/widgets/toast.py`, context-menu code, hover/press QSS in `ui/theme_engine.py`/`ui/stylesheet.py`, and motion durations.

**Modal dialogs (11):** all token-driven or component-delegated (global QSS, `Card`/`Btn`/`Label` wrappers). No hardcoded colors found. `sync_conflict_dialog.py:73` sets the dialog bg inline via `COLOR_BG_BASE` (functionally fine, slightly inconsistent pattern).

**Toast:** colors token-driven (`_toast_qss()` in `theme_engine.py:1391-1400` uses `COLOR_ERROR_DEFAULT`, `COLOR_TEXT_PRIMARY`). ⚠️ `FADE_DURATION_MS = 250` (`toast.py:21`) duplicates the `TOAST_FADE_MS = 250` token without referencing it.

**Context menus:** global `QMenu` styling token-driven (`_menu_qss()` `theme_engine.py:1044-1066`: `COLOR_BG_ELEVATED`, `COLOR_BORDER_MEDIUM`, `COLOR_ACCENT_PRIMARY` selected). Two items:
- ⚠️ **Missing `QMenu::item:hover` state** — only `:selected` is defined; context-menu items have no hover feedback.
- ⚠️ `trip_card.py:845-851` context menu sets its own inline stylesheet with hardcoded `border-radius: 4px` instead of `RADIUS_SM`.

**Hover/press states:** buttons (`COLOR_ACCENT_HOVER`, `COLOR_BG_OVERLAY`), cards (`ELEVATION_RAISED`), table rows (`COLOR_BG_HOVER`), inputs (`COLOR_BORDER_STRONG`) — all token-driven.

**Motion durations:** dialog fades use `FADE_MS=150` ✓, slide `SLIDE_MS=200` ✓, spinner `SPINNER_MS=800` ✓ (all token-referenced). `QTimer.singleShot` values (500/1500/2000/3000/8000ms) are deferred callbacks, not animations — not token violations. `chart_loading_overlay.py` 50/80ms spinner tick intervals are ad-hoc but functional (not animation tokens).

---

## 4. Actionable Items — ALL FIXED (2026-08-24)

| # | Site | Item | Status |
|---|---|---|---|
| 1 | `map_widget.py:249` | `#6366f1` inline → `COLOR_ACCENT_PRIMARY` | **FIXED** — import added, default now references the token |
| 2 | `route_renderer.py:26` | `"gray"` → `COLOR_NEUTRAL_DEFAULT` | **FIXED** — import added, `ALT_ROUTE_COLOR` now references the token |
| 3 | `toast.py:21` | `FADE_DURATION_MS` → reference `TOAST_FADE_MS` | **FIXED** — class constant now references the token |
| 4 | `theme_engine.py` `_menu_qss()` | Add `QMenu::item:hover` state | **FIXED** — hover rule added using `COLOR_BG_HOVER` (verified present in generated QSS) |
| 5 | `trip_card.py:845-851` | Hardcoded `border-radius: 4px` → `RADIUS_SM` | **FIXED** — stylesheet now uses `RADIUS_SM` (also cleaned up the string concatenation) |

**Exemptions now documented in code** (so future maintainers don't "fix" them by mistake):
- `plotly_theme.py:40-46` — comment above the `*_LIGHT` palette variants (chart-palette extension, audit item 4 exemption).
- `plotly_charts.py` — `YlOrRd` default (named data-viz colorscale) and 7px heatmap cell annotation (chart-context size) both carry inline exemption comments.
- `route_renderer.py:23-25` — marker colors carry a Leaflet web-surface exemption comment (joining the existing `#cc0000`/`#09090b` exempt comments).

**Verification:** all changed modules import cleanly; `test_theme.py` + `test_component_qss.py` + `test_trip_card_logic.py` + `test_design_tokens.py` = **68 passed**; `QMenu::item:hover` confirmed in generated QSS; chart verification unchanged (19/20 token-backed + 2 documented exemptions).

---

## 5. Files

- `tools/verify_chart_interiors.py` — new programmatic chart-interior verification tool.
- Evidence: `tools/verify_chart_interiors.py` output (20 charts, 19/20 fully token-backed), explorer lane findings for maps/transient.