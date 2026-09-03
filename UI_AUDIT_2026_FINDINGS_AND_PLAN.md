# Operion Desktop ERP — UI Production-Readiness Audit: Findings & Implementation Plan

**Date:** 2026-08-30
**Scope:** Desktop PySide6 UI (`ui/`, `main.py`) — audit only, then phased implementation.
**Status:** Audit complete. Phase 0 in progress.

---

## 1. Executive Summary

Operion's UI is **4.7/10** — a well-architected dark-theme desktop app whose *finish* is not yet commercial-grade. The shell (MainWindow → AppShell → Sidebar/TopBar/QStackedWidget), design tokens, global QSS theme engine, shared components, and a working screenshot harness are production-grade. The failure is **adoption and data**: 704 inline `setStyleSheet()` calls across 89/175 UI files, three competing typography maps, ~8 card implementations, and — most damaging — **machine-generated placeholder values and wrong-language strings baked into the translation data files**, which render literal placeholder titles ("DISPATCH BOARD SUBTITLE", "CONTROL PANEL TITLE") in the shipped UI.

**Key numbers**

| Metric | Score |
|---|---:|
| Global UI score | **4.7 / 10** |
| Design-system coherence | 4 / 10 |
| Navigation | 7 / 10 |
| Information hierarchy | 5 / 10 |
| Information density | 4.5 / 10 |
| Workflow UX | 5 / 10 |
| Professionalism | 4 / 10 |
| Accessibility | 4 / 10 |
| Responsive behavior | 4 / 10 |
| UI implementation quality | 5 / 10 |

**Readiness**

| Stage | Score | Primary blocker |
|---|---:|---|
| UI Prototype Readiness | 85/100 | — (passed) |
| Internal Testing Readiness | 65/100 | Placeholder/mixed-language text, blank Team screen, truncation |
| Father Pilot Readiness | 40/100 | User-visible "unfinished" signals within first 10 minutes |
| Public Launch Readiness | 20/100 | Above + responsive failure at 1024px, sub-10px fonts, no QA gate |

**Decision: no Qt Designer migration.** The design system is QSS + dynamic-property driven and works identically in raw PySide6; views are programmatic-composition-heavy where `.ui` files add nothing; migration of 80+ views pre-launch is catastrophic regression risk for near-zero visual gain. **Improve the existing PySide6 implementation.**

---

## 2. Audit Method & Evidence

- **Codebase mapping** — full `ui/` layer (175 Python files) mapped: architecture, views, widgets, dialogs, styling, navigation, workflows.
- **Rendered ground truth** — real app booted headlessly (offscreen QPA, seeded demo DB, fake admin auth) via `tools/ui_audit_harness.py`; **all 21 pages captured at 1440×900** → `tools/evidence_audit/`, **8 key pages at 1024×600** → `tools/evidence_audit_1024/` (PNG + per-widget geometry JSON per page; zero capture errors).
- **Independent specialist reviews** — design-system audit (code), rendered visual audit (all 21 screenshots), responsive comparison (8 screenshots at two sizes), architectural review (implementation quality, root causes, migration decision).
- **Verified source evidence** for the top findings (file:line):
  - `data/translations/en.json:1571-1572` — `"subtitle": "Dispatch Board Subtitle"`, `"title": "Dispatch Board"` (placeholder values in the English file)
  - `data/translations/en.json:1740` — `"kpi_unassigned": "Nedodijeljeni"` (Croatian in English file)
  - `data/translations/en.json:1739` — `"kpi_total": "Fahrer Gesamt"` (German in English file)
  - `data/translations/en.json:1767` — `"status_in_progress": "Status In Progress"` (placeholder-style)
  - `ui/design_tokens.py:124-136` — `STATUS_STYLES` with hardcoded Romanian labels ("Livrat", "În curs", "Anulat")
  - `ui/views/generators_view.py:84-88` — emoji icons (`📤📥🚛📁`) violating the qtawesome-only convention
  - `ui/delegates/alert_card_delegate.py:151` — hardcoded English `"Trip {alert.trip_id}"`
  - `ui/widgets/client_activity_timeline.py:129` — hardcoded English format string
  - `ui/main_window.py:1102` — `PlaceholderView` "Module not yet migrated"
  - `ui/views/automail_view.py:68,182` — `_PlaceholderPanel`
  - `ui/views/route_planner_view.py:205-222` — token-correct QSS duplicating the global theme (49 inline blocks in file)
  - `ui/views/cmr_form_view/cmr_form.py:203-279` — 7px fonts (below the 10px floor)
  - `ui/main_window.py:314-315` — hardcoded `resize(1400,900)` + `setMinimumSize(1024,600)`
  - `ui/theme_engine.py:123` — `refresh()` never called; theme engine imported by only 4 files
  - `ui/styles.py:87-89` — dead compatibility shim with hardcoded CSS strings (`Theme.apply` has zero callers)

**Capture limitations:** offscreen platform stubs Plotly charts and map tiles; chart/map areas render empty in evidence (the *empty-state design gap* is a real finding; the black void itself is partly a harness artifact).

---

## 3. Screen-by-Screen Grading (rendered, 1440×900)

| Screen | Visual | UX | Density | Consistency | Prof. | Access. | Launch Readiness | Priority |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Overview (Dashboard) | 6 | 6 | 5 | 6 | 6 | 5 | 5 | HIGH |
| Analytics | 5 | 5 | 6 | 5 | 4 | 4 | 4 | MED |
| Route Planner | 3 | 4 | 6 | 3 | 3 | 3 | 2 | HIGH |
| Calculator | 5 | 5 | 5 | 5 | 5 | 4 | 4 | MED |
| Dispatch Board | 4 | 5 | 3 | 4 | 3 | 3 | 2 | **CRITICAL** |
| Tracking | 3 | 4 | 5 | 4 | 3 | 3 | 3 | MED |
| Freight Exchange | 4 | 4 | 4 | 4 | 4 | 3 | 3 | MED |
| Fleet | 7 | 7 | 6 | 6 | 7 | 5 | 6 | HIGH |
| Driver Manager | 5 | 5 | 5 | 5 | 4 | 4 | 3 | HIGH |
| Clients | 6 | 5 | 5 | 5 | 5 | 4 | 4 | MED |
| Documents | 5 | 5 | 3 | 5 | 4 | 4 | 3 | HIGH |
| Maintenance | 3 | 4 | 5 | 4 | 3 | 3 | 2 | HIGH |
| Maintenance Control | 4 | 4 | 4 | 4 | 3 | 3 | 2 | MED |
| Tachograph | 3 | 4 | 5 | 4 | 3 | 3 | 2 | MED |
| Invoices | 5 | 5 | 4 | 5 | 4 | 4 | 3 | HIGH |
| History | 7 | 6 | 6 | 6 | 6 | 5 | 6 | MED |
| Route History | 4 | 4 | 5 | 4 | 4 | 3 | 3 | MED |
| Copilot / ARGO | 6 | 6 | 7 | 6 | 6 | 5 | 5 | MED |
| Migration Center | 6 | 5 | 5 | 5 | 5 | 4 | 4 | LOW |
| Settings | 7 | 6 | 5 | 6 | 6 | 5 | 6 | LOW |
| Team | 0 | 0 | 5 | 2 | 0 | 2 | 0 | **CRITICAL** |

Rendered top-10 problems (evidence-based): (1) literal placeholder text leaking into production UI; (2) map loading failures leaving black voids; (3) massive empty chart areas with no empty-state design; (4) text truncation/clipping inside fixed containers; (5) Team screen completely blank; (6) untranslated/mixed-language i18n values; (7) cramped kanban columns with clipped card content; (8) overcrowded filter bars; (9) truncated table headers; (10) empty cards/panels without consistent empty-state treatment.

---

## 4. Root-Cause Analysis (ranked)

1. **Migration-in-progress state** — CustomTkinter→PySide6 port froze halfway; dead shims became stable APIs new code layered onto.
2. **No enforcement mechanism** — nothing fails a build for `setStyleSheet`, hex literals, or <10px fonts. 704 QSS calls happened because nothing pushed back.
3. **AI-generated one-off styling** — views each re-derive "what a card looks like"; token-correct but duplicated, so drift is frozen at generation time.
4. **Component bypass** — no canonical registry; local QFrame + QSS is the shortest path.
5. **Semantic-level design-system gap** — palette/spacing centralized; radii, typography, component anatomy not.
6. **No visual QA gate** — the screenshot harness exists but is run manually/never.
7. **i18n pipeline contamination** — translation sweeps wrote placeholder and wrong-language values into the data files.

---

## 5. Top 20 UI Problems

| # | Problem | Severity | Difficulty | Systemic? |
|---|---|---|---|---|
| 1 | Translation placeholder values in data files | Critical | 1 | Yes |
| 2 | Wrong-language values in en.json | Critical | 1 | Yes |
| 3 | Team screen renders blank | Critical | 1 | Yes (empty-state pattern) |
| 4 | Empty chart/panel voids | Critical | 2 | Yes |
| 5 | Text truncation in fixed containers | Critical | 2 | Yes |
| 6 | Kanban unusable at 1024px | High | 3 | Yes |
| 7 | 704 inline setStyleSheet calls | High | 3 | Yes |
| 8 | 3 competing typography maps; 7–9px fonts | High | 1 | Yes |
| 9 | 8 card / 3 button / 2 badge implementations | High | 3 | Yes |
| 10 | Map failure = black dead zone | High | 2 | Yes |
| 11 | Two maintenance UIs split context | High | 3 | Yes |
| 12 | Invoices toolbar truncation + empty Bill To | High | 2 | Yes |
| 13 | Romanian labels baked into tokens | High | 1 | Yes |
| 14 | Fixed window/dialog geometry vs DPI | Medium | 2 | Yes |
| 15 | Density: 7-control filter bar (Maintenance Control) | Medium | 2 | Screen-specific |
| 16 | Dense category sidebar (Documents) | Medium | 2 | Screen-specific |
| 17 | PlaceholderView + debug artifacts in prod paths | Medium | 1 | Yes |
| 18 | No visual QA gate; harness unused | Medium | 2 | Yes |
| 19 | Emoji icons vs qtawesome convention | Low | 1 | Yes |
| 20 | Settings half-width dead space | Low | 1 | Screen-specific |

---

## 6. Minimum Viable UI Improvement Package

The smallest package that flips perception from "MVP" to "commercial":

| Item | Days | Share of perceived problem |
|---|---|---|
| A. Translation data sweep (placeholders, wrong-language, terminology) | 2–3 | ~40% |
| B. Empty/error-state pass (Team, charts, Bill To, insights, client detail, map zones, placeholder views) | 2–3 | ~20% |
| C. Truncation/clipping pass (fixed containers, table headers, buttons, kanban cards) | 2–3 | ~15% |
| D. QSS consolidation core (one source, delete shims, typography unification, ≥10px floor) | 3–4 | ~10% |
| E. Component consolidation (cards/buttons/badges/tables) | 3–4 | ~10% |
| F. Responsive floor (min 1280×720, kanban scroll, panel collapse) | 2–3 | ~5% |
| G. Visual QA gate in CI (harness + baselines) | 1–2 | prevention |

**Total core package: ~16–22 dev-days.**

---

## 7. Implementation Plan (Phases)

### Phase 0 — Data integrity & critical blockers (IN PROGRESS)
**Goal:** remove every user-visible "unfinished" signal; make the app look tested.
- **Lane 1 — i18n integrity:** sweep `data/translations/*.json` (placeholder values, wrong-language values, add `status.*` keys); move `STATUS_STYLES` labels (`ui/design_tokens.py`) behind i18n keys resolved in `ui/components.py` StatusBadge/StatusChip; fix hardcoded English (`alert_card_delegate.py:151`, `client_activity_timeline.py:129`).
- **Lane 2 — Empty states:** Team screen; `PlaceholderView`/`_PlaceholderPanel` removal; chart-widget-level empty state (analytics, maintenance, overview); Copilot insights; invoice "Bill To"; client detail panel; map loading/error states (route planner, tracking, route history).
- **Lane 3 — Truncation:** calculator result panel; Documents action buttons/columns; kanban card text + column min widths; table headers (driver manager, history, tachograph); invoice generators checkboxes/toolbar; freight exchange combo; emoji→qtawesome in generators_view.

**Definition of done:** re-run `tools/ui_audit_harness.py` (21 pages @ 1440×900 + 8 @ 1024×600), compare against `tools/evidence_audit*` baselines; no placeholder titles, no blank screens, no clipped critical labels; designer visual sign-off on affected screens.

### Phase 1 — Design system enforcement (~1 week)
One font ladder from `design_tokens`; single QSS source (`QtTheme` absorbs `stylesheet.py` fragments; delete `styles.py`); `<10px` font ban; **lint gate** (`tools/ui_style_gate.py` failing on inline `setStyleSheet`/hex/`<10px` outside allowlist; pre-commit hook).

### Phase 2 — App shell polish (~3–4 days)
Token-driven window geometry; sidebar/topbar spacing normalization; minimum size decision (**raise to 1280×720**); DPI-safe dialogs.

### Phase 3 — Highest-value screens (~2 weeks)
Dispatch Board, Invoices/Generators, Route Planner, Documents, Driver Manager: strip inline QSS, fix truncation, empty states, density.

### Phase 4 — Density reduction (~1 week)
Filter bars, panels, duplicate actions, second maintenance UI.

### Phase 5 — Consistency (~ongoing)
Dialogs, forms, tables, badges, states via consolidated components.

### Phase 6 — Visual QA loop
Harness screenshots after every phase; baseline diffs in CI.

---

## 8. Effort Estimation (core package)

| Improvement | Diff. | Time | Regression | UX | Visual | I/E |
|---|---:|---:|---|---:|---:|---:|
| Translation placeholder sweep | 1 | 1–2 d | Low | 9 | 8 | 8.5 |
| Empty-state pass | 2 | 2–3 d | Low | 8 | 8 | 4.0 |
| Truncation/container pass | 2 | 2–3 d | Low | 8 | 6 | 3.5 |
| QSS consolidation + lint gate | 3 | 3–4 d | Med | 7 | 8 | 2.5 |
| Typography unification | 1 | 1 d | Low | 6 | 6 | 6.0 |
| Component consolidation | 3 | 3–4 d | Med | 7 | 7 | 2.3 |
| Responsive floor | 3 | 2–3 d | Med | 9 | 5 | 3.1 |
| Visual QA harness in CI | 3 | 1–2 d | Low | 5 | 0 | 2.5 |

---

## 9. What NOT to Touch (during UI sprint)

Backend services, database schema/migrations, API contracts, ARGO/CoPilot architecture, OCR pipeline, sync engine, invoice/CMR generation logic, financial calculations, business-invariant checks, mobile app, website, tests, deployment configs, translation *pipeline* code (fix data, not mechanics).

---

## 10. Verification Protocol (every phase)

1. `python tools/ui_audit_harness.py --seed --out tools/evidence_audit --size 1440x900 --wait 800` (21 pages)
2. `python tools/ui_audit_harness.py --seed --out tools/evidence_audit_1024 --size 1024x600 --wait 600 --pages overview,dispatch_board,route_planner,invoices,fleet,settings,documents,copilot`
3. Designer compares against pre-change baselines; geometry JSON diff for regressions.
4. Grep gates: no placeholder patterns (`Subtitle`, `Card Title`, `Panel Title`, `Prefix` as values) in `data/translations/en.json`; no wrong-language values; no `font-size: [7-9]px` in ui/ outside allowlist.

---

## 11. Change Log

| Date | Change | Lane | Verified |
|---|---|---|---|
| 2026-08-30 | Audit complete (this document) | — | ✓ rendered evidence |
| 2026-08-30 | Phase 0 launched: i18n integrity / empty states / truncation | 1, 2, 3 | pending harness re-run |
| 2026-08-30 | **Phase 0 COMPLETE** — see Phase 0 Results below | 1, 2, 3 + remediation | ✓ final capture: 21 pages @1440 + 8 @1024, zero errors, zero regressions, designer sign-off |
| 2026-08-30 | **Phase 1 COMPLETE** — see Phase 1 Results below | A, B, C | ✓ regression-free (designer), gate exit 0 |
| 2026-08-30 | **Phase 2 COMPLETE** — see Phase 2 Results below | A (shell), C (dialogs) | ✓ regression-free (designer), gate exit 0 |
| 2026-08-30 | **Phases 0–2 CONSOLIDATED VERIFICATION** — fresh captures, gate, tests, designer sign-off | all | ✓ see §15 |
| 2026-08-30 | Residual items fixed (route planner clip, kanban min-width at 1280) | fix-5, fix-6 | ✓ designer PASS ×2, gate exit 0 |
| 2026-08-30 | **Phase 3 COMPLETE** — see Phase 3 Results below | A–D | ✓ regression-free (designer), gate exit 0, debt 714→682 |
| 2026-08-30 | **Phase 4 COMPLETE** — see Phase 4 Results below | A–C + fix | ✓ designer IMPROVED ×7, 1 issue found+fixed, gate exit 0 |
| 2026-08-30 | **Phase 5 COMPLETE** — see Phase 5 Results below | A–C + fix | ✓ designer 20/21 OK (1 false alarm resolved), gate exit 0, debt 682→668 |
| 2026-08-30 | **Phases 3–5 CONSOLIDATED VERIFICATION** — fresh captures, gate, i18n, component identity, designer pass | all | ✓ PASS, zero regressions, improvement trajectory confirmed (§20) |
| 2026-08-30 | Pre-existing issues fixed (alerts tests, _toggle_grid ×4 files, timeline None, Godina/Servisni data) | fix-3 + direct | ✓ designer PASS ×4, gate exit 0 (§21) |
| 2026-08-30 | **Remaining deferrals resolved** — maintenance hub, component keeps, geometry 21→7, QSS 668→640, harness exit-code hardening | D1–D4 + direct | ✓ designer PASS, zero regressions, gate exit 0 (§22) |

## 20. Phases 3–5 Consolidated Verification (2026-08-30)

Independent end-to-end check of the current tree (fresh captures; no test-suite runs per user instruction):

- **Rendered ground truth (fresh):** `tools/evidence_v35/` (21 pages @1440×900) + `tools/evidence_v35_1280/` (8 pages @1280×720) — zero capture errors.
- **Designer sign-off (independent pass):** all 21 screens PASS vs the Phase-2 baseline — the only deltas are the four INTENTIONAL, previously-approved design changes (documents ghost sidebar, maintenance two-tier filters, freight collapsible advanced filters, migration h2 header) + seeded-data artifacts. **Zero regressions** at both sizes. Improvement trajectory vs the pre-audit baseline confirmed on 12+ screens (broken layouts → clean, functional, consistent).
- **Gate:** PASS (exit 0) — debt 668 inline QSS / 49 hex / 6 sub-10px frozen, 21 geometry warnings.
- **Component identity:** `ui.widgets.ActionButton is ui.components.ActionButton` → True (canonicalization holds); compact theme selectors present (23).
- **i18n integrity:** placeholder/wrong-language sweep clean; **found & fixed 6 emoji-in-translation values** (`automation.delete_run/download_pdf/download_run/download_zip`, `client.phone`, `client.email_icon`) — icon characters embedded in UI copy, removed (2 keys unused in ui/, verified).
- **Font floor:** only 3 exempt print-HTML lines remain.
- **Known pre-existing, documented, not re-run per instruction:** `test_dispatch_alerts_panel_widget.py` failures (stash-verified unrelated, predate the sprint).

## 21. Pre-Existing Issues Fixed (2026-08-30)

All documented pre-existing issues from the sprint are now closed:

1. **Alerts-panel test failures** (`test_dispatch_alerts_panel_widget.py`, 3) — diagnosed as STALE tests: they searched for a "TRIPS" StatCard label while the product key resolves to "Total Active" (and matched the raw-key fallback only when translations weren't loaded — order/state-dependent), and asserted a "Neither" label that the product intentionally renders as "No Truck or Driver". Product logic verified correct (`_DONE_STATUSES` excludes done statuses properly); tests updated to match by translation key with raw-key fallback. 46 tests pass.
2. **`_toggle_grid` silent no-op** (analytics `_tab_base.py`, `maintenance_analytics_view.py`, plus the same latent `.fig` bug in `dashboard.py` and `fleet_tab.py`) — all four accessed `chart.fig`/`chart.render()` which don't exist on `PlotlyChartWidget` (figure is `self._fig`, exposed via `figure()`; render path is `set_figure`); AttributeError was swallowed → button did nothing. Fixed with a new `PlotlyChartWidget.set_grid_visible()` API (updates axes, invalidates the id-keyed pixmap cache, re-renders); also fixed `_export_chart`'s `.fig` access with a None guard. Zero `.fig` accesses remain repo-wide.
3. **`timeline_panel.py` TypeError** — `days_past > 0` with `_compute_days_past()` returning `None` (empty/unparseable/future dates) would crash. Fixed: `days_past = self._compute_days_past(due) or 0`, preserving the "Due today" branch.
4. **Wrong-language values in en.json** — 7 more found beyond the Phase 0 sweep (ASCII Croatian invisible to diacritic heuristics): `fleet.table_year/detail_year/form_year` ("Godina" → "Year"), `fleet.table_service_km` ("Servisni KM" → "Service KM"), `fleet.kpi_service_due` ("Servis dospijeva" → "Service due"), `fleet.form_service_km`, `fleet.export_truck_csv_success` ("CSV kamiona spremljen" → "Truck CSV exported"). Broad ASCII term sweep now clean (2 remaining hits are English false positives). Designer-verified: fleet headers read ID · PLATE · MODEL · MANUFACTURER · **YEAR** · VIN · KM.

**Verification (targeted only, no broad suite runs per instruction):** alerts test file 46 pass; dashboard/fleet_tab related tests 74 pass; harness captures `tools/evidence_pfix1` (dispatch_board, analytics, maintenance) + `evidence_pfix2` (fleet, overview) + `evidence_pfix3` (final: fleet, dispatch_board, analytics, maintenance) — zero errors; designer PASS ×4 (fleet headers English, no regressions); gate PASS (exit 0, baseline regenerated, debt unchanged 668/49/6).

**Remaining documented deferrals (not bugs):** maintenance two-view consolidation (architectural, deliberate), 3 no-visual-change-rule component keeps, 668 grandfathered inline-QSS (dynamic/unique), 21 geometry warnings, harness 0xC0000005 teardown (environmental, offscreen QtWebEngine).

## 22. Remaining Deferrals Resolved (2026-08-30)

All five documented deferrals closed:

1. **Maintenance two-view unification (D1)** — new `QtMaintenanceHub` (`ui/views/maintenance_hub.py`): one "maintenance" page with CONTROL / ANALYTICS tabs hosting `QtMaintenanceControlPanel` + `QtMaintenanceAnalyticsView` as-is; lifecycle forwards wakeup/shutdown to the active tab (per-tab try/except so one view can't kill the hub). `maintenance_control` removed from the factory, nav, module/warmup keys; the harness page list updated; alert-panel navigation (`_NAV_DESTINATIONS`) re-pointed at the hub; orphaned sidebar icon removed. Designer: hub tabs render cleanly, CONTROL tab replicates the old page exactly.
2. **Component keeps resolved (D2)** — canonical components extended: `StatusBadge` gained solid/uppercase/bg/text modes (additive QSS), `IconButton` gained glyph mode + flat variant, new `CompactRow` component. trip-card status + delayed chips → StatusBadge solid; `_make_action_btn` → 5 flat IconButtons; overview `_trip_row` → CompactRow adapter. **Pixel-identical** (component-level mean diff 0.0; page diffs = seeded rotation only). One keep remains: `_btn_docs` (IconButton hover swaps icon color — not reproducible exactly, documented).
3. **Geometry warnings (D3)** — `fixed_geometry` 21 → **7**, all remaining documented decorative/canvas (8px dots, monogram, signature canvas); icon buttons converted to fixed-width + min-height with an empirically-verified note (global QSS inflates sizeHints, so naive min-size conversion would have changed rendering). Static chrome QSS → theme roles: login_dialog 8→1, sidebar 19→5, topbar 10→8 (−23 calls). Shell verified pixel-identical.
4. **Inline-QSS debt (D3+D2)** — grandfathered count **668 → 640** (−28 this batch; −74 cumulative from Phase 3's 714).
5. **Harness teardown (D4)** — root cause: native access violation in QtWebEngine/Chromium's GPU path under offscreen (bypasses Python entirely — before the fix every run died with 0xC0000005 after captures). Fixed with offscreen-safe Chromium GPU-disabling flags + clean shutdown (quit, delete QWebEngineViews, drain WorkerPool) + supervisor/marker pattern (`tools/.audit_complete`; parent derives exit code from on-disk evidence). Before: all runs −1073741819; after: exit 0 with marker, exit 1 on genuine failures, decision matrix verified.

**Verification:** full harness 20 pages @1440 + 9 pages @1280 (incl. the hub), zero errors, **reliable exit 0** (D4); gate PASS (640/49/6, 7 geometry warnings); designer pass: all 20 screens OK, **zero regressions**, parity confirmed for hub tabs / trip chips / glyph buttons / overview rows / shell. Evidence: `tools/evidence_defer/` + `tools/evidence_defer_1280/`.

**Deferral list is now EMPTY.** Remaining technical debt is the documented dynamic/unique inline QSS (640, frozen by the gate) — a maintenance burn-down item, not a defect.

## 23. Updated Global Score (2026-08-30, post Phases 0–6 + deferrals)

Recomputed from phase evidence (designer-verified rendered results at every boundary):

| Category | Weight | Before | Now | Basis |
|---|---:|---:|---:|---|
| Visual quality | 15% | 4.0 | 7.0 | 20/20 screens designer-OK; Team 0→7, Dispatch 4→7, Tacho 3→7, Driver 5→8; approved restyles |
| Information hierarchy | 15% | 5.0 | 6.5 | Real titles, demoted dominant headers; layouts preserved |
| Information density | 15% | 4.5 | 6.5 | Two-tier/collapsible filter bars, breathing rows, kanban min-widths |
| Workflow UX | 15% | 5.0 | 6.5 | Hub unification, crash fixes, alert navigation repaired |
| Consistency | 10% | 4.0 | 7.5 | One ladder/source, canonical components, gate-enforced |
| Navigation | 10% | 7.0 | 7.5 | Maintenance single entry |
| Professionalism | 10% | 4.0 | 7.5 | No visible unfinished signals |
| Accessibility | 5% | 4.0 | 5.0 | Font floor/tooltips/DPI — no systematic keyboard/focus pass yet |
| Responsive | 5% | 4.0 | 7.0 | 1280 min, scroll/wrap behaviors, 0 truncation verified |

**Global: 4.7 → 6.8/10.** Readiness: Prototype 85→95, Internal Testing 65→90, Father Pilot 40→75, Public Launch 20→65. Path to 8+: systematic accessibility pass, full non-English translation coverage, frozen-QSS burn-down.

## 19. Phase 5 Results (2026-08-30) — Component Consolidation

**Lane A — one component per primitive:**
- `ActionButton` canonicalized: single class `ui.components.ActionButton(_Btn)` with the exact legacy API; `ui.widgets.ActionButton` is now a re-export (identity check passes; all 29 call sites unchanged); dead `_ActionButton` in api_dashboard deleted.
- Hand-rolled fleet KPI card `_maint_kpi_card` REMOVED → canonical `StatCard` with a new optional `accent_color` param (5 call sites: odometer/last service/next due/cost/alerts/tacho).
- KEPT with measured reasons: `overview._trip_row` (UniversalCard can't reproduce the 34px compact row without structural diffs), `trip_card._make_action_btn` (18px flat glyph buttons), trip_card status chips (StatusBadge renders a bordered uppercase pill; cards need borderless solid chips), `KpiCard` (distinct elevated role).
- Tests: 77 + 246 pass; pixel-diffs 0.07–3.6 (seeded rotation); harness 4 pages both sizes, zero errors.

**Lane B — table consolidation:** inventory of all six owned views shows **every table already runs on the canonical `StyledTableWidget`** (consolidated in prior phases) — zero changes needed; raw `QTableWidget` remains only in out-of-scope files (admin panel, sync dialog). 100+ tests pass; the two non-zero pixel diffs (documents = intentional Phase-3D restyle + seeded rotation; clients = known skeleton artifact) classified as non-regressions.

**Lane C — theme-engine compact size class (the Phase 3A gap, now closed):**
- `ui/theme_engine.py` gained additive compact variants: `QPushButton[compact="true"]` (incl. secondary/sm), `QLineEdit/QComboBox/QCheckBox[compact="true"]` (32px fields, 16px indicator), `QScrollBar[compact="true"]` (4px), `[surface="elevated"]` and `[role="button-bar"]` (panel surfaces). Two empirical findings handled: compact rules set font-size explicitly (13 vs 12px body) and background-color explicitly (to beat the descendant surface rule).
- `route_planner_view.py`: **49 → 37 setStyleSheet calls (−12)** via `setProperty("compact")` + unpolish/polish. **Pixel-identical**: form diff mean 0.037–0.046/channel at both sizes; settings/calculator cross-check 0.0 (no theme leakage).
- Verified: harness both sizes, zero errors; geometry identical (calc 54px, combos 40px, panel 324px).

**Verification:** designer pass — 20/21 screens OK, zero regressions, 1 "documents sidebar" flag **resolved as a baseline mismatch** (compared against pre-restyle `evidence_verify`; pixel-diff vs the post-restyle `evidence_p3d` = mean 0.09–0.13, i.e. unchanged — the Phase-3D restyle was previously designer-approved). Gate PASS, debt **714 → 668** cumulative. Evidence: `tools/evidence_p5/` + `tools/evidence_p5_1280/`.

**Pre-existing latent bug found & fixed (surfaced by the wider test sweep):** `route_planner_view.py` stop placeholder `t("route.stop_n", default=f"Stop {idx}").format(idx)` raised `KeyError: 'n'` whenever the key resolved (translations loaded) — i.e., adding a waypoint stop would crash in production. Identical at git HEAD (not introduced by this sprint). Fixed → `t("route.stop_n", default="Stop {n}").format(n=idx)`; also removed a `📍` emoji from the stop-start placeholder default. All 31 route_planner tests pass; full UI sweep exit 0.

**Remaining (post-launch candidates):** `overview._trip_row` / `trip_card` chips / `_make_action_btn` consolidation (blocked by no-visual-change rule — needs a component-design decision), `KpiCard`/`Card` family merge, raw tables in admin panel + sync dialog, 668 grandfathered inline-QSS (dynamic/unique styling), 21 geometry warnings, maintenance two-view consolidation.

## 14. Phase 2 Results (2026-08-30) — App Shell Polish

**Lane A — window geometry + shell spacing:**
- New tokens: `WINDOW_MIN_WIDTH/HEIGHT = 1280/720`, `WINDOW_INITIAL_WIDTH/HEIGHT = 1440/900` (design_tokens).
- `main_window.py`: initial size = ~80% of primary-screen available geometry (clamped ≥1280×720), `setMinimumSize(1280, 720)` — **the 1024×600 minimum is gone** (the responsive audit proved it unviable for kanban/invoices/fleet).
- sidebar.py + topbar.py: all raw-int margins/spacings → SP tokens (12→SP3, 20→SP5, 16→SP4, 8→SP2, 4→SP1); TOPBAR_HEIGHT already tokenized.
- Verified: 88 tests passed; offscreen geometry checks (minimum enforced, resize(900,600) → actual 1280×720); harness 21 pages @1440 + 8 pages @1280×720, zero errors.

**Lane C — DPI-safe dialogs:**
- 7 dialog/popup fixed sizes → minimum + sizeHint-driven: report_issue (max cap removed), login (max cap removed), dispatch detail drawer (fixed width → min + seeded geometry, drawer slide math preserved), service timeline dialog, date picker popup, assignment dropdown popup, alert panel chips.
- Fixed 2 latent bugs found during verification: date_picker `isFixedSize()` (not in PySide6 — would crash) and assignment_dropdown `_walk_set_click` (`.__func__` on native handlers — would crash on first real fetch).
- Verified: 36/36 offscreen construction checks at 100% AND 150% font scale; signature pad canvas documented INTENTIONAL (PNG export geometry).
- Gate `fixed_geometry` warnings: 25 → 21 (remaining are intentional chrome).

**Verification:** designer rendered check (fresh session): zero shell regressions across all 21 pages at 1440; at the new 1280×720 minimum, 6/8 key screens OK, 2 acceptable-but-tight (dispatch_board kanban, route_planner Calculate button clip) — flagged for the Phase 3 responsive pass, not blockers. Gate: PASS (baseline regenerated after line shifts — same 714/50/6 debt, zero real drift).

**Remaining (Phase 3):** highest-value screens (Dispatch Board, Invoices, Route Planner, Documents, Driver Manager) — strip grandfathered inline QSS, density reduction, plus the two responsive tweaks (kanban horizontal scroll/collapse below ~1350px; route planner bottom bar min-height).

## 15. Phases 0–2 Consolidated Verification (2026-08-30)

Independent end-to-end verification of the current tree:

- **Rendered ground truth (fresh):** `tools/evidence_verify/` (21 pages @1440×900) + `tools/evidence_verify_1280/` (8 key pages @1280×720, the new minimum) — zero capture errors.
- **Designer sign-off (independent pass):** all 21 screens OK vs the Phase-0 baseline; **zero regressions**; two screens improved vs baseline (overview, freight_exchange — full empty-state text). All Phase-0 fixes still hold (team content, clients table, kanban, English KPIs/headers, real titles, no emoji artifacts). At 1280×720: 6/8 screens OK, 2 acceptable (dispatch kanban wraps tightly; route_planner Calculate button minor clip — both known, Phase 3).
- **Gate:** PASS (exit 0) — 714 inline-QSS / 50 hex / 6 sub-10px grandfathered, zero new; fixed_geometry 21 warnings.
- **i18n integrity:** en.json placeholder/wrong-language sweep CLEAN; all status.* and screen keys resolve to real copy.
- **Font floor:** only exempt thermal-print HTML (6 lines in receipt editor) remains sub-10px.
- **Dead code:** `ui/styles.py` deleted; `PlaceholderView` class gone ("Module not yet migrated" survives only as the intentional i18n default inside the new EmptyState).
- **Tests:** 39 UI test files (design tokens, components, theme engine, sidebar, top bar, main window, a11y, dispatch board, styles) — exit 0.
- **Found & fixed during verification:** one leftover emoji in the CMR generate button (`generators_view.py:460`) → replaced with a qtawesome paper-plane icon.
- **Environment note:** two frozen capture runs during this verification were caused by stray pytest wrapper processes (killed, re-ran clean) — not a code issue.

## 16. Residual Items Fixed (2026-08-30)

Both known responsive residuals from the consolidated verification, verified at the 1280×720 minimum:

1. **Route Planner bottom-bar clip** — root cause: `button_bar.setFixedHeight(88)` in `ui/views/route_planner_view.py:545` was far below the content's real minimum (~204px) because the theme QSS (`QPushButton { min-height: 38px; padding: 8px 16px }`) overrides the buttons' `setFixedHeight(36/28/28)`, inflating them to ~54–56px. Fix: `setMinimumHeight(224)`. Verified offscreen: Calculate (bottom 577), Export (649), Share (716) all fully inside the 720px window; designer: PASS — all three buttons fully visible.
2. **Kanban columns below 260px at 1280** — root cause: the columns container's 1372px floor existed only as `minimumSizeHint()`; `minimumWidth()` was 0, so `QScrollArea` with `widgetResizable(True)` crushed it. Fix: explicit `columns_container.setMinimumWidth(columns_layout.minimumSize().width())` (=1372px) in `ui/views/dispatch_board/dispatch_board.py:408`. Verified in the real view at 1280×720: all 5 columns exactly 260px, container 1372, viewport 1232, horizontal scrollbar max 140; wide viewports still expand (265px @1440, 297px @1600, no scrollbar). Designer: PASS — readable card text, horizontal scroll intentional.
3. **Gate reconciliation:** the emoji-fix + residual edits shifted baseline line numbers (same violations, ±1 line — 6 stale/new pairs, 1:1 mirror, zero real drift) → baseline regenerated; gate PASS (exit 0), 714/50/6 debt unchanged, 21 geometry warnings.

**Result: no residual items remain** — both minimum-size pressure points closed; the app is verified clean at 1280×720, gate-enforced, zero regressions.

## 17. Phase 3 Results (2026-08-30) — Highest-Value Screens

Inline-QSS strip + density across the five highest-value screens. Four lanes, empirically verified per change (pixel-diffs before/after, harness at 1440 + 1280, targeted tests).

**Lane A — Route Planner (52 → 49 calls):** the audit's premise that the ~49 inline blocks "duplicate the global theme identically" did NOT hold empirically. The planner uses a compact size class (32px inputs, 4px scrollbar, 16px checkboxes) the global theme (min-height 38px) cannot express — removing those rules measurably regressed rendering (combos 40→52px, panel +26px wide, interior bg flip) and was reverted. Only 3 genuinely redundant calls removed (transparent-on-transparent, token-consistent progress bar). Final form area **pixel-identical** (diff 0.0). The remaining debt here is a real gap: the theme engine lacks a "compact" size class — flagged for Phase 5 (component/theme work), not a strip issue.

**Lane B — Dispatch Board (57 → 34 call sites, −40%; trip_card 45 → 23):** removed pure global-theme duplicates (QLabel roles, ghost-button backgrounds, QMenu); consolidated repeated dynamic styling into helpers (`_set_accent_bar_color`, `_set_status_chip`, `_build_alert_banner`) with zero emitted-QSS change. Column geometry byte-identical; 1280 pixel-diff ≈ 0.03; 1440 diffs localized to seeded status rotation. All dispatch tests pass (3 pre-existing failures in `test_dispatch_alerts_panel_widget.py` confirmed unrelated via stash test).

**Lane C — Invoices/Generators:** the audit's "~10-20 static duplicates" also overstated — the calls are dynamic user-color swatches + unique chrome. The ONE real raw hex (`generators_view.py:509 #111113`) → `COLOR_BG_ELEVATED`. Zero raw hexes remain in on-screen styling of these files; bottom 60% of frames pixel-identical.

**Lane D — Documents + Driver Manager (12 → 6 kept):** **Documents category sidebar restyled** — solid purple blocks → ghost buttons with the nav-item active idiom (overlay bg + 3px accent left border + accent text). Designer verdict: "professional... a clear improvement... reduces visual noise, unambiguous wayfinding." Pixel-diff localized to the sidebar only. driver_manager: 3 row-action buttons → `variant="ghost"` property, QMenu sheet removed (7 → 3). The capture-time table diff was investigated and proven to be a harness skeleton-timing artifact (reproduces on git-HEAD code) — not a regression.

**Verification:** full harness 21 pages @1440 + 8 @1280, zero errors; designer pass: all 21 screens OK/IMPROVED, **zero regressions**; gate **PASS** with debt reduced **inline_qss 714 → 682, raw_hex 50 → 49**; UI test suite (document_center, driver_manager, dispatch, tokens, components, theme, shell, a11y) exit 0. Evidence: `tools/evidence_p3/` + `tools/evidence_p3_1280/`.

**Remaining (Phase 4+):** density pass across the rest (filter bars, second maintenance UI), component consolidation (cards/buttons/badges — Phase 5), theme-engine compact size class, remaining 682 grandfathered inline-QSS (mostly proven-necessary dynamic/unique styling), 21 geometry warnings.

## 18. Phase 4 Results (2026-08-30) — Density Reduction

**Lane A — Maintenance Control filter bar (audit's 7-control row):** the 13-widget single row → two-tier: PRIMARY (severity pills · type combo · truck search · "Resolved" toggle + compact counter + "More" toggle) + COLLAPSIBLE secondary (trip filter), mimicking the settings collapsible idiom with zero new QSS. **Designer-verified at 1280:** the primary row truncated ("SHOW RES", "ORE FILT", clipped counter) → fixed by fix-3 (labels "Resolved"/"More" via t() defaults, truck field 128px, counter "C:3 W:0 I:0") → offscreen geometry test 29/29 widgets fit, harness re-captured, designer **PASS** — all labels complete, secondary filter hidden.

**Lane B — Freight Exchange filter panel (audit's 9-group wall):** split into PRIMARY (Route, Date Range) + collapsible ADVANCED (Vehicle/ADR, Weight, Price, Distance, Loading Type, Countries — collapsed by default since expanded exceeds the 636px panel at 1280); new `_CollapsibleFilterSection` (chevron disclosure, zero inline QSS); spacing normalized 16→12px. 112 tests pass. Designer: **IMPROVED** at both sizes, no clipping.

**Lane C — Overview + Migration Center:** Recent Activity rows 14→24px (SP["6"]), SP-token element spacing/margins, client names paint-elided with tooltips (no more `[:22]` hard cut); same discipline on top-trucks/alert/active-trip rows; Migration Center header demoted from dominant PageTitle to h2 (16px) with true secondary subtitle. 91 tests pass. Designer: **IMPROVED** ×2 screens.

**Verification:** designer pass (fresh session) — 4 screens IMPROVED, zero regressions, one issue found (above) and fixed with a second PASS; gate PASS (exit 0, debt stable 682/49/6); evidence `tools/evidence_p4a..p4c*` + `evidence_p4a_fix`.

**Also fixed (pre-existing, surfaced by the wider test sweep):** `tests/ui/test_freight_provider_settings.py::test_empty_state_has_title` asserted the OLD buggy behavior (raw i18n key visible when translations are loaded); updated to assert "providers" in the resolved copy — passes with translations loaded or not (48 tests green).

**Deliberate scope decision:** the "second maintenance UI" (Maintenance Control vs Maintenance Analytics) was NOT merged — merging views changes navigation architecture and the harness page list, contradicting the audit's minimal-change principle. Documented as a post-launch consolidation candidate.

## 13. Phase 1 Results (2026-08-30) — Design-System Enforcement

**Lane A — single QSS source + typography unification:**
- `ui/styles.py` DELETED (dead CTk-compat shim; only test imports existed — `test_styles.py`/`test_theme.py` migrated to canonical sources).
- All 5 remaining `stylesheet.py` fragments moved into `QtTheme` (as `_stat_card_qss`, `_filter_qss`, `_section_header_qss`, `_tab_button_qss`, `_kanban_qss`); `_card_qss` (`QFrame#card`) merged into `_frame_qss` as a single comma-selector rule — **`QtTheme.qss()` is now the complete, only QSS source**; `ui/stylesheet.py` is a thin `build_stylesheet()` → `QtTheme.qss()` wrapper (main.py/main_remote.py untouched).
- **Card-border conflict resolved:** `role="card"`/`card-elevated`/`kpi-card`/`#card` unified on COLOR_BORDER_SUBTLE (#2A2A30) per design intent — rendered result: subtler, more refined cards, all still clearly bounded.
- **One font ladder:** `theme_engine.FONT_SIZES` now derives from `design_tokens.FONT_SIZE_*`; `FONT_FAMILY` → IBM Plex Sans, `FONT_MONO` → IBM Plex Mono (legacy Inter/Consolas eliminated repo-wide — calculator + alert-card delegate updated); nav icon 18→16px; fragment font sizes tokenized.
- `QtTheme.refresh()` kept (live caller: settings_fields theme switching).
- Tests: 125 passed (incl. migrated test_styles/test_theme).

**Lane B — readability floor (no on-screen font < 10px):**
- CMR form box badges 7/8px → 10px (+ badge width 18→20 for two-digit numbers), CMR fields badge 8→10, automail timeline dot 8→10, alert-card delegate QFont 8/9pt → 10pt.
- Remaining sub-10px: only the 6 exempt thermal-print HTML lines in receipt_editor (documented in gate allowlist).

**Lane C — enforcement gate (the anti-drift mechanism):**
- `tools/ui_style_gate.py` (pure stdlib): checks `inline_qss` (setStyleSheet), `raw_hex_colors`, `sub_10px_fonts`, `fixed_geometry` (warning, Phase 2) with hard allowlists (theme_engine, stylesheet, design_tokens, plotly_theme, map/, print/oauth files) + **baseline grandfathering** (`--baseline-generate`, stale-baseline warnings).
- Wired into `.pre-commit-config.yaml` (local hook) and `.github/workflows/test-python.yml` (ubuntu + py3.11 job step, fails fast).
- **Final state: GATE PASS, exit 0** — 714 inline QSS + 50 hex + 6 sub-10px frozen as grandfathered debt; any NEW violation fails CI/pre-commit from now on.

**Verification:** full harness capture `tools/evidence_p1_final/` (21 pages) + `tools/evidence_p1_final_1024/` (8 pages) — zero errors; designer regression check vs Phase-0 baseline: **all 21 screens OK, zero regressions** (cards subtly refined, IBM Plex uniform, nav icons legible).

**Remaining (Phase 2+):** inline-QSS debt reduction (714 grandfathered — strip in Phase 3 screen passes), fixed-geometry warnings (25, Phase 2), component consolidation, responsive floor, lint-gate enforcement of future work.

## 12. Phase 0 Results (2026-08-30)

All five critical blockers eliminated. Final screen scores (0–10, rendered, vs baseline):

| Screen | Before | After | Screen | Before | After |
|---|---:|---:|---|---:|---:|
| Team | 0 | **7** | Tachograph | 3 | **7** |
| Dispatch Board | 4 | **7** | Driver Manager | 5 | **8** |
| Fleet | 7 | **8** | Invoices | 5 | **7** |
| Calculator | 5 | **7** | Documents | 5 | **7** |
| Overview | 6 | **7** | Freight Exchange | 4 | **6** |
| Maintenance Control | 4 | **6** | Clients | 6 | **6** |
| Maintenance | 3 | **5** | History | 7 | **8** |
| Route Planner | 3 | **4** | Analytics | 5 | **6** |
| Tracking | 3 | **5** | Route History | 4 | **5** |
| Copilot | 6 | **7** | Migration Center / Settings | 6–7 | **6–7** |

**What was fixed:**
- **i18n data:** 158+ placeholder/wrong-language values corrected across all 22 translation files (en.json: 151 fixes incl. "Dispatch Board Subtitle", "Fahrer Gesamt", "Nedodijeljeni", fleet section "Hersteller"/"Tablica"; other languages: "X Title" placeholders); 5 new `status.*` keys; `alert_card`/`client_activity` keys.
- **STATUS_STYLES:** Romanian labels moved behind i18n keys (`design_tokens.py` → `t()` in StatusBadge/StatusChip); hardcoded English strings routed through `t()`.
- **Team screen:** root cause was a stuck BaseView skeleton (`_load_users` never called `_hide_loading()`) — fixed; page now renders header + add-user form + members table.
- **Clients page crash:** invalid `mdi6.file-invoice-outline` icon replaced (`fa5s.file-invoice`); all other Phase-0 icons glyph-validated.
- **Charts:** `PlotlyChartWidget.set_empty()` API + `figure_has_data()`; analytics/maintenance/overview route empty figures through it (chart black voids in captures are a harness stub artifact).
- **Maps:** loading panel + error/retry + 15s stall timeout on route planner / tracking / route history.
- **Truncation:** calculator result panel, documents icon buttons + filename wrapping, kanban columns (root cause: FlowLayout ignored minimum widths → QHBoxLayout + horizontal scroll, cards ≥260px), table headers (driver manager, history, tachograph, fleet, maintenance — ResizeToContents pattern), invoice editor checkboxes + FlowLayout action bar, generators emoji → qtawesome, freight combo popup, EmptyState word wrap (systemic).
- **Copy:** history/dispatch subtitles de-duplicated; emoji icons removed.

**Verification:** `tools/evidence_final/` (21 pages, 1440×900) + `tools/evidence_final_1024/` (8 pages, 1024×600) + `tools/evidence_final_fx/` (spot checks) — zero capture errors, zero regressions, designer sign-off.

**Remaining (Phase 1+ scope):** QSS consolidation (704 inline setStyleSheet), typography unification, component consolidation, responsive floor (kanban fine now; invoices/fleet at 1024 need the Phase-3 pass), DPI-safe geometry, 1024px minimum-size decision, lint gate + CI harness. Clients detail panel empty state is carryover debt (low priority).