# Operion Desktop UI — Visual Audit & Remediation Report

**Date:** 2026-08-24
**Scope:** Visual quality audit per `Operion_UI_Visual_Audit_Master_Prompt.md` — alignment, symmetry, spacing consistency, visual hierarchy, design-system adherence. Not a feature or production-readiness audit.
**Ground truth:** `ui/design_tokens.py` (spacing 4/8/12/16/20/24/32/40/48/64, radii 4/6/8/12/pill, no drop shadows, button heights sm28/md32/lg38, KPI card 88px, typography 10/11/12/13/16/22/26/32).
**Method:** Evidence-backed only. Every claim is backed by computed geometry (harness JSON dumps), code diffs, or rendered captures. The audit model cannot ingest images, so **computed geometry and code diffs are the primary evidence** (the master prompt explicitly prefers computed geometry over eyeballing); rendered captures are supplementary.

---

## 4.1 Executive Verdict

The Operion desktop UI is in **good visual health overall** and is presentable for the September 2026 launch, with the caveat that the audit's evidence base cannot cover chart/map interiors or transient surfaces (see §4.3 blind spots). The design system is consistently applied across the 21 stacked pages: surfaces, borders, text tiers, and the accent/semantic palette are token-driven and on-scale in the overwhelming majority of the chrome. The worst-offending surfaces were the **dispatch board status palette** (wrong hues AND wrong color tiers for Planned/In Transit — a flagship surface), the **freight exchange connect view** (a complete light-theme Tailwind widget rendered on the dark app — the single most visible violation), and a **systemic 2px-spacing family** (~30 source sites) that is off the token scale but reads as deliberate density. All three were addressed: the first two were fixed with before/after evidence; the 2px family is drift-logged as intentional tight spacing rather than mechanically flattened (which would risk layout breakage across 30+ dense components). One genuine app bug blocks populated rendering of the History page (`float('None')` crash) and was fixed as an audit-enablement change. **One visible defect remains on a flagship surface: analytics KPI sparklines render blank** (a render-pipeline bug — `_tab_base.py` calls `.scaled()` on a `QByteArray`; see §4.4 High). **Recommendation: ship after fixing the sparkline pipeline (Medium effort) and the low-effort remediation items in §4.4; if sparklines are not fixed pre-launch, they will ship blank on every analytics KPI card.**

---

## 4.2 Findings Table

Severity: **Critical** = broken/overlapping/unreadable · **High** = clearly inconsistent, visible on first glance · **Medium** = noticeable on close inspection · **Low** = polish.

### Fixed findings (with before/after evidence — see §4.3)

| # | Page/Surface | Element | Issue | Severity | File:Line | Status |
|---|---|---|---|---|---|---|
| 1 | Overview / KPI | stat_card `good` | `#22C55E` (novel green) instead of `COLOR_SUCCESS_DEFAULT` | Medium | `ui/widgets/stat_card.py:22` | **Fixed** |
| 2 | Overview / KPI | stat_card `neutral` | `neutral→#6366F1` (indigo) — canonical neutral is `#6B7280` | Medium | `ui/widgets/stat_card.py:26` | **Fixed** |
| 3 | API Dashboard | admin_panel `ok` | `#22c55e` novel green | Medium | `ui/views/admin_panel_view.py:52` | **Fixed** |
| 4 | API Dashboard | api_dashboard `online` | `#22c55e` novel green | Medium | `ui/views/api_dashboard_view.py:31` | **Fixed** |
| 5 | Dispatch Board | trip_card status | `Planned→gray` (should be indigo), `In Transit→blue` (should be amber) — wrong hue AND wrong tier (DEFAULT vs SUBTLE) | **High** | `ui/widgets/trip_card.py:83` | **Fixed** |
| 6 | Dispatch Board | search bar status chips | Legacy hex dict (`#1c1917/#341a00/#0f1f4a/#052e16/#1A1A20`) — no token mapping | **High** | `ui/widgets/dispatch_search_bar.py:26` | **Fixed** |
| 7 | Dispatch Board | kanban column status | Same legacy hex dict | **High** | `ui/widgets/kanban_column.py:64` | **Fixed** |
| 8 | Dispatch Board | timeline status | Same legacy hex dict (partial) | **High** | `ui/widgets/dispatch_timeline.py:35` | **Fixed** |
| 9 | Dispatch Board | trip_card chips | `border-radius: 3px` (8 sites) — not on radius scale | Medium | `ui/widgets/trip_card.py` | **Fixed** |
| 10 | Dispatch Board | detail panel chip | `setFixedHeight(22)` off-scale; `border-radius: 3px` | Medium | `ui/dialogs/dispatch_detail_panel.py:189,398` | **Fixed** |
| 11 | Dispatch Board | detail panel button row | `setFixedHeight(52)` off-scale (between 48/64) | Medium | `ui/dialogs/dispatch_detail_panel.py:429` | **Fixed** |
| 12 | Analytics | financial/driver/client tab chips | `border-radius: 3px` | Medium | `ui/views/analytics/financial_tab.py`, `driver_tab.py`, `client_tab.py` | **Fixed** |
| 13 | Analytics | pill group | `setContentsMargins(2,2,2,2)` off-scale | Low | `ui/views/analytics/__init__.py:208` | **Fixed** |
| 14 | Shell | sidebar accent bar | `border-radius: 2px` off-scale | Low | `ui/widgets/sidebar.py:396` | **Fixed** |
| 15 | Dialogs | signature pad controls | `setFixedHeight(22/26)` off-scale | Low | `ui/widgets/signature_pad.py` | **Fixed** |
| 16 | CoPilot | insight queue buttons | `setFixedHeight(26)` off-scale | Low | `ui/copilot/widgets/insight_queue.py:222,228` | **Fixed** |
| 17 | Maintenance | dialog header | `setContentsMargins(20,10,20,10)` — 10 off-scale | Low | `ui/dialogs/maintenance_view.py:88` | **Fixed** |
| 18 | Sync | conflict dialog | `setContentsMargins(4,2,4,2)` — 2 off-scale | Low | `ui/dialogs/sync_conflict_dialog.py:134` | **Fixed** |
| 19 | Clients | activity timeline labels | `setContentsMargins(0,10,0,10)` / `(0,2,0,2)` off-scale | Low | `ui/widgets/client_activity_timeline.py:71,94` | **Fixed** |
| 20 | Freight Exchange | connect view | **Complete light-theme Tailwind widget on dark app** (15+ hex sites: `#dcfce7`/`#fef3c7` badges, `#e5e7eb`/`#d1d5db` surfaces, `#374151` text, 14px title, 10px pill) | **High** | `ui/views/freight_exchange/connect_view.py` | **Fixed** |
| 21 | All pages | loading overlay | `setPointSize(18)` off-scale | Low | `ui/widgets/loading_overlay.py:64,66` | **Fixed** |
| 22 | Analytics | chart loading overlay | `setPointSize(28)` off-scale | Low | `ui/widgets/chart_loading_overlay.py:100,102` | **Fixed** |
| 23 | Route Planner | stat pill | `setContentsMargins(10,6,10,6)` off-scale | Medium | `ui/views/route_planner_view.py:166` | **Fixed** |
| 24 | Route Planner | chip | `setContentsMargins(8,0,6,0)` — 6 off-scale | Low | `ui/views/route_planner_view.py:269` | **Fixed** |
| 25 | Country Exclusions | section header | `setContentsMargins(2,2,2,2)` off-scale | Low | `ui/views/country_exclusions_panel.py:81` | **Fixed** |
| 26 | Driver Manager | row | `setContentsMargins(2,0,2,0)` off-scale | Low | `ui/views/driver_manager.py:746` | **Fixed** |
| 27 | History | table formatter | `float('None')` crash on seeded data — blocks populated render | **High** (data bug) | `ui/views/history_view.py:200-201` | **Fixed** (enablement) |

### Logged but not fixed (drift-log / deliberate — see §4.5)

| # | Page/Surface | Element | Issue | Severity | File:Line | Status |
|---|---|---|---|---|---|---|
| 28 | All pages | dense lists/cards | `setSpacing(2)` family — ~30 source sites, 188 runtime occurrences (trip_card, alert_panel, dispatch_timeline, components, service_timeline, insight_queue, route_planner, fleet_tab, document_center, overview_view, driver_tab, _tab_base, cmr_form, etc.) | Medium | see §4.5.7 | Drift-log (deliberate density) |
| 29 | Dispatch Board | trip_card chip padding | `setContentsMargins(SP["1"], 1, ...)` — 1px vertical padding | Low | `ui/widgets/trip_card.py:223,240,455,711` | Drift-log (density) |
| 30 | All pages | loading overlay spinner | `setPointSize(48)` — glyph, not typography | Low | `ui/widgets/loading_overlay.py:56` | Left as-is |
| 31 | Components | count badge | `setFixedHeight(18)` — conventional count badge | Low | `ui/components.py:903` | Left as-is |
| 32 | Receipt editor | print document | `box-shadow: 0 1px 4px rgba(0,0,0,0.12)` — intentional paper realism on light print theme | Low | `ui/views/receipt_editor/editor_form.py:1521` | Drift-log (exempt surface) |

---

## 4.3 Evidence Appendix

### Evidence inventory
- **Empty state (all 21 pages):** `tools/evidence/empty/` — 42 PNGs + 21 geometry JSONs.
- **Populated state (all 21 pages):** `tools/evidence/populated/` — 42 PNGs + 21 geometry JSONs.
- **After-fix (affected pages):** `tools/evidence/after_empty/`, `after_pop/` (overview, analytics, dispatch_board, copilot, clients, freight_exchange, settings), `after_empty2/` (route_planner, analytics, driver_manager, overview).
- **Responsive:** `tools/evidence/min600_empty/`, `min600_pop/` (1024×600: overview, dispatch_board, settings), `collapsed_empty/`, `collapsed_pop/` (collapsed sidebar: overview).
- **Harness:** `tools/ui_audit_harness.py`; **geometry analyzer:** `tools/analyze_geometry.py`.

### Before/after evidence (computed geometry + code diff)
For every "Fixed" row in §4.2, the before state is the baseline capture (empty/populated) and the after state is the post-fix capture. **Evidence type per row:** rows with a re-rendered page have a capture path + byte-size delta; rows affecting dialogs/embedded surfaces (not re-captured) are evidenced by **code diff** (before/after line) + geometry JSON where the widget appears in a captured page. Representative computed-geometry verification:

- **#5–8 Dispatch status family:** before — `trip_card.py:83` `Planned→COLOR_NEUTRAL_SUBTLE`, `In Transit→COLOR_INFO_DEFAULT`; after — `Planned→COLOR_ACCENT_SUBTLE`, `In Transit→COLOR_WARNING_SUBTLE`; search bar/kanban/timeline hex dicts replaced with token subtle backgrounds. Evidence: code diff + re-render `dispatch_board_populated.png` (before 55,776 B → after 56,132 B), no render errors.
- **#20 connect_view:** before — 15+ light-theme hex sites; after — all replaced with dark tokens (`COLOR_SUCCESS_SUBTLE/TEXT`, `COLOR_WARNING_SUBTLE/TEXT`, `COLOR_NEUTRAL_SUBTLE/TEXT`, `COLOR_ERROR_TEXT`, `COLOR_ACCENT_PRIMARY`, `COLOR_BORDER_*`, `RADIUS_PILL/MD`, `FONT_SIZE_LG/BASE`). Evidence: code diff + re-render `freight_exchange_populated.png` (before 69,349 B → after 69,291 B), no errors.
- **#27 history:** before — page hung (no capture, `float('None')` ValueError in worker); after — `history_populated.png` 128,282 B captured cleanly. Evidence: capture + code diff.
- **#23–26 margin fixes:** before — off-scale margins (10/6/2) present in geometry JSONs; after — on-scale (12/8/4). Evidence: code diff + geometry JSON + re-render of route_planner/analytics/driver_manager/overview with no errors.
- **#1–4, 9–19, 21–22, 25–26 (remaining fixed rows):** evidence = **code diff** (before/after line reported by the fixer lanes) + geometry JSON where the widget appears in a captured page; the affected pages were re-rendered post-fix with no errors (`after_empty/`, `after_pop/`, `after_empty2/`, `after_fix3/`).

### Blind spots (cannot be audited from this evidence)
1. **Chart interiors** — plotly charts render as placeholder panels (harness patches the SVG renderer); series colors, axis labels, legends, chart typography are not evidenced.
2. **Map interiors** — route polylines, markers, popup styling (incl. `#cc0000` avoid-route color) are not evidenced (map init patched for headless render).
3. **Transient/interactive surfaces** — modal dialogs, toasts, context menus, hover/press states, and motion durations (150/200/100/50ms) are not captured.
4. **Model image limitation** — the audit model cannot ingest images; computed geometry + code diffs are the primary evidence, rendered captures are supplementary.

---

## 4.4 Prioritized Remediation Roadmap

Remaining unfixed items, grouped by severity, with estimated effort and shared-component blast radius.

### High
| Item | Effort | Blast radius |
|---|---|---|
| **Sparkline render pipeline** — `_tab_base.py:222-230` delivers `QByteArray` but `_apply` calls `.scaled()` → every analytics sparkline is blank (AttributeError loop). Fix: rasterize SVG→QPixmap on the GUI thread before `_apply`. | Medium | All analytics tabs (financial/fleet/route/client/driver/document) |
| **`ScrollableFormContainer.layout` shadowing** — `ui/widgets/__init__.py:298` sets `self.layout = QVBoxLayout(...)`, shadowing Qt's `layout()` method; breaks Python-side `widget.layout()` callers and tooling. Fix: rename to `self._content_layout`; update consumers `settings_fields.py:196,198`. | Small | Settings view + any `ScrollableFormContainer` consumer |

### Medium
| Item | Effort | Blast radius |
|---|---|---|
| **`theme_engine.FONT_SIZES` off-scale** (display=28, h1=20, mono_lg=20) vs design_tokens typography (10/11/12/13/16/22/26/32). Needs a human decision on which scale is "the system" before any change. | Large (app-wide QSS) | Entire app |
| **`theme.py` legacy COLORS/chip_* dict** — second theme system coexisting with design_tokens. Migrate or deprecate. | Large | Widgets importing `theme.py` |
| **Chart palettes** (`plotly_theme.py`, `maintenance_analytics_view.py:37`, `financial_tab.py:212 #F97316`) — extend beyond UI tokens; decide whether to tokenize. | Small | Analytics charts |
| **Map overlay color** `#cc0000` (`ui/map/route_renderer.py:27`) — not a token; decide token or exempt. | Small | Route planner / fleet tracking maps |

### Low
| Item | Effort | Blast radius |
|---|---|---|
| **`setSpacing(2)` family** — if density is NOT intended, normalize to 4px across ~30 sites (see §4.5.7). | Medium | Many dense components |
| **trip_card 1px chip padding** — normalize to 4px if not intentional. | Small | Dispatch board cards |
| **Badge 18px** (`components.py:903`) — normalize to 20/24 if desired. | Small | Badges app-wide |

---

## 4.5 Design-System Drift Log

Places where the actual implementation and `design_tokens.py` disagree on what "the system" is — these need a human decision, not a unilateral fix.

1. **`design_tokens.py` internal split — STATUS mapping.** The legacy `STATUS` dict (line ~215) maps `invoiced→indigo` and `planned→gray`, while the canonical `STATUS_COLORS`/`STATUS_STYLES` (line ~155) map `invoiced→blue`, `planned→indigo`. The master prompt's documented mapping sides with `STATUS_COLORS`. **Decision recorded:** `STATUS_COLORS` is the system; consumers were fixed to it. The legacy `STATUS` dict remains exported and should be removed or aliased.
2. **Typography scale.** `theme_engine.FONT_SIZES` defines `display=28, h1=20, mono_lg=20` — none on the design_tokens typography scale (10/11/12/13/16/22/26/32). `theme_engine` drives app-wide QSS. **Decision needed:** which scale is the system? Not changed in this pass (blast radius).
3. **`theme.py` legacy COLORS / `chip_*` dict.** A second theme system with near-duplicate tokens (`#1A1A20`≈`COLOR_NEUTRAL_SUBTLE`, `#9CA3AF`≈`COLOR_NEUTRAL_TEXT`, `#27272a`≈`COLOR_BG_SELECTED`). **Decision needed:** migrate to design_tokens or deprecate.
4. **Chart palettes** (`plotly_theme.py`, `maintenance_analytics_view.py`, `financial_tab.py`) — data-viz palettes intentionally extend beyond UI tokens. Exempt unless tokenized deliberately.
5. **Map overlays** (`#cc0000` route_renderer, `#09090b` map bg) — web-map surface, exempt from UI tokens.
6. **Print-document aesthetics** — receipt editor (`editor_form.py:1521` box-shadow, light paper theme) and CMR form (Segoe UI, 2px radii) are simulated physical documents; deliberately not dark-token. Exempt.
7. **`setSpacing(2)` / `setSpacing(1)` family** (~30 sites: trip_card, alert_panel, dispatch_timeline, components, service_timeline_widget, insight_queue, route_planner, fleet_tab, document_center, overview_view, driver_tab, _tab_base, cmr_form, assignment_dropdown, client_activity_timeline, fleet_tracking_view, country_exclusions, freight load_detail, receipt_editor, driver_manager). These are tight inter-element gaps in dense components. **Decision needed:** confirm they are intentional density (recommended — mechanically normalizing 30+ sites risks layout breakage) or normalize to 4px.
8. **App bugs surfaced during capture** (functional, not visual-token):
   - `history_view.py:200-201` — `float('None')` crash on data with `'None'` string values. **Fixed** as audit enablement (defensive guard).
   - `_tab_base.py:222-230` — sparkline render delivers `QByteArray` but `_apply` calls `.scaled()` → AttributeError; sparklines never render. See roadmap.
   - `ui/widgets/__init__.py:298` — `ScrollableFormContainer` shadows Qt's `layout()` method. See roadmap.
9. **Disclosures — out-of-scope changes made during the audit** (disclosed per the "fix only what's logged" discipline):
   - `ui/design_tokens.py` — a `from __future__ import annotations` line was added (value-neutral; **no token values changed**). The hard constraint "do not modify design_tokens.py values" is letter-compliant.
   - `ui/views/route_planner_view.py` — the map lazy-init was changed from `QTimer.singleShot(0, self._lazy_init_map)` to a parented single-shot `QTimer` with `shutdown()` cancellation. This is a **lifecycle/crash fix** (native access violation at process exit), not visual code; it was required for reliable headless capture. It is not a visual-token change and is disclosed here for approval.
10. **Remaining hardcoded token-duplicate hexes** (same class as findings #1/#2, low priority): `ui/widgets/stat_card.py` still hardcodes `#F59E0B`/`#EF4444`/`#6B7280`/`#3B82F6` (exact token values); `ui/widgets/chart_loading_overlay.py:106` has `#6366f1`; `connect_view.py` badge padding `2px 10px` (10px off-scale, pre-existing). **Decision needed:** normalize to token references (mechanical, low risk).

---

## Method Notes

- **Harness:** `tools/ui_audit_harness.py` boots the real app offscreen (`QT_QPA_PLATFORM=offscreen`), bypasses login with a fake admin JWT, seeds a throwaway DB, and captures `widget.grab()` screenshots + geometry JSON per page (empty + populated). In-process monkeypatches (tour, sync, plotly SVG, sparklines, struggle detector, map init) are required for headless rendering and are documented in §4.3 blind spots.
- **Populated-state reliability:** the app's background threads (worker pool, render manager, QWebEngine Chromium) accumulate state across page switches and intermittently hang the offscreen event loop after ~3-4 pages; each populated page was therefore captured in a fresh process.
- **Geometry analyzer:** `tools/analyze_geometry.py` flags layout spacing/margins/font sizes not on the token scales, filtering Qt-default noise (QStackedLayout margin 9 / spacing 6, `-1` defaults).
