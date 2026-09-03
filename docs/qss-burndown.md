# Operion QSS Debt Burn-Down — Plan of Record (snapshot)

**Session:** 2026-08-30 · **Mode:** deepwork · **Scope:** grandfathered inline-QSS debt conversion
**Live session state:** `.slim/deepwork/qss-burndown.md` (git-local) — this file is the tracked snapshot per Oracle gate-5 M1.

---

## 1. Objective & Outcome

Convert the grandfathered inline `setStyleSheet` debt into theme-engine roles / canonical components, landing at a ledger that reflects only legitimately-dynamic styling, with every remaining call classified.

**Trajectory (corrected per gate-5 m5):** 714 (start) → 640 → 586 → 546 → 491 → 375 → **304 final** (acceptance ≤350 MET; −57.4%). Raw_hex 50→**44**, sub_10px 6→**0** (thermal-print reclass), role_inventory 206→**154** (dead 39→**7**, all annotated gate false-positives), fixed_geometry 21→**7** (pre-sprint), type-mismatch warnings 2.

**Phases (each: conversion lane → widget checklist → pre-regen gate proof → harness/pixel/re-diff evidence → designer spot-check → Oracle gate → boundary commit):**

| # | Phase | Sites | Ledger | Commit | Gate |
|---|---|---|---|---|---|
| 1 | Copilot widgets | 61→7 | 640→586 | `a320f3d7` | #1 PASS |
| 2 | Automail + m1/m2 | 47→9 | 586→546 | `20edcf9c` | #2 PASS |
| 3 | Freight + CMR | 52→13 | 546→491 | `9d30053f` | #3 PASS |
| 4 | Analytics + Dialogs + automail dialogs | 116→8 | 491→375 | `2c4fcf3a` | #4 PASS |
| 5 | Route planner + components + tail sweep + dead sweep | ~120→~30 | 375→304 | (final commit) | #5 PASS |

## 2. Oracle review log (all gates: 1 initial review, 0 re-reviews needed)

| Gate | Verdict | Key findings & remediation |
|---|---|---|
| 1 | PASS | M1 live `size`-attribute collision (route_planner 972/1492 + dead selectors) → Phase 5 size→sizeRole with designer re-approval; M2 gate Check 5 (role_inventory) implemented now; M3 functional-changes statement per phase; M4 boundary commits. m1/m2 → Phase 2; m3 dead `insight-card` prop dropped; m5 naming conventions → catalog header. |
| 2 | PASS | M1 QCheckBox `fontRole` no-op (QLabel-scoped selectors) → scoped rule + gate type-mismatch warning sub-check; M2 plan coverage gap (9 unscoped files) → Phase 4/5 scope extensions; stale test fixed; `text-transform` dead in Qt (m3); role-property test pattern canonical (m5). |
| 3 | PASS | `:focus:!hover` empirically VERIFIED working (negation defect is `:!checked`-only) → catalog note; QLabel `role`+`state` grammar for stateful labels codified; 3 static keeps → tail-sweep classification; `sub_lbl` inert `role="muted"` annotation corrected; m4 test pre-adaptation requirement. |
| 4 | PASS | M1 detach-before-delete systemic (36 takeAt sites) + harness DeferredDelete pump → Phase 5; M2 dead-selector 4-class sweep protocol; kept-count 8 corrected; DPI evidence at final gate. Regression found by designer (analytics heading double-render — pre-existing deferred-delete artifact, bisect-proven) fixed in `_tab_base.cleanup`. |
| 5 | PASS | M1 static-keep itemization must land in this snapshot (below); M2 final boundary commit staging (explicit; baseline json + .gitignore hunk + evidence dirs included; sprint files + `ui/styles.py` deletion excluded; `dashboard.py` partial-staged — carries a sprint plotly hunk). m1 `related_label` → `fontRole="helper"` cheap win (landed, 304→303); m2 harness subprocess timeout (landed); m3 StateLabel/Dot unit tests (post-launch gap); m4 DPI provenance: env `QT_SCALE_FACTOR=1.25` offscreen capture (`tools/evidence_dpi`); m5 trajectory correction (this section). |

## 3. Designer decisions (recorded, accepted design intent)

- **size→sizeRole renames APPROVED** (Create Trip 54→38px, Google Maps 56→40px tall — deliberate activation of previously-dead sm styling; reads intentional/professional).
- **class=* wire-up: LEAVE UNSTYLED.** The ~40 `Label(role=...)` component sites (page titles, section titles, field labels) render base-styled through every shipped baseline. Wiring them up = deliberate global visual change; deferred post-launch. **Deferred wire-up role list:** `secondary`, `muted`, `section-title`, `field-label`, `danger`, `success`, `default`, `label`, `body-bold`, `bold`, `page-title`, `kpi-value`, `kpi-label` (QLabel role values used by ui/components.Label).
- **DPI @125% PASS** (settings + dispatch_board scale cleanly; evidence: `tools/evidence_dpi`, env QT_SCALE_FACTOR=1.25).

## 4. End-state classification of the 304 residual inline calls

### (a) DYNAMIC runtime styling (~70%) — data-driven, token-based, correctly inline (cannot live in the theme)
Status/severity/state colors (trip-card chips + accent bars, dispatch severity chips, fuel dots, live dots, KPI value/subtitle colors across analytics tabs, urgency chips, expiry/status labels), user-picked brand color swatches (invoice/proforma/receipt editors), runtime reason→color maps (load_detail), empty-state icons, per-status badges. Category accepted across all gates.

### (b) Documented static-keeps (~20%) — itemized with candidate roles (post-launch mint candidates)

**automation_view.py (6):**
- `_style_primary_btn` / `_style_secondary_btn` / `_simple_status` — color `ACCENT_TEXT` (#818CF8); no theme rule uses it → candidate: `variant` pair or ACCENT_TEXT-based role
- `_candidates_box` — 11px + ACCENT; no 11px-accent combo → candidate: fontRole `sm-accent`
- header + mode_row (834/846) — elevated bg + bottom border; closest roles (button-bar/top-bar) differ in bg or border side → candidate: `panel-header` role
- (related_label was converted via `fontRole="helper"` in the final remediation — 304→303)

**trip_card.py (6):** `_both_lbl` (11px+ACCENT → `sm-accent`); `live_dot` (11px + SUCCESS_DEFAULT vs fontRole success = SUCCESS_TEXT → `sm-success-default`); `live_speed` (mono + SECONDARY → `mono-secondary`); error banner (solid ERROR_DEFAULT bg, 2/6 padding → `error-banner-solid`); alert banner frame (solid ERROR_DEFAULT + radius 4 → `panel-danger-solid`); menu border override (SUBTLE vs global MEDIUM → `QMenu[role="subtle"]`).

**overview_view.py (5):** 12px+primary labels ×3 (767/838/923 → `base-primary`); `more` (12px+ACCENT+500 → `base-accent-semibold`); `rev` (mono+12px+SUCCESS_TEXT → `mono-success`); `plate` (12px+SECONDARY+500 → `base-secondary-semibold`); rank idx (11px/600, dynamic color — color part stays inline).

**tacho_import_view.py (4):** `drop_icon` (28px → sizeRole extension); `drop_hint` (12px+500+SECONDARY → `base-secondary-semibold`); `steps` (13px+tertiary+padding 8 → `list-step` role); `_btn_vehicle` (border+hover override → `btn-outline-tight`); result_violations (warning chip 13px/2-8 vs warning-note 11px/4-8 → `chip-warning-lg`).

**dashboard.py (1):** feed_scroll (custom 4px scrollbar, thumb min-height 30, no arrows → `thin-scroll-no-arrows` variant).

**fleet_tracking_view.py (2):** 64px icon (sizeRole extension); HLine divider — `QFrame[role="hairline"]` exists but changes the paint mechanism (background fill vs HLine `color`); measured non-parity → hairline recorded as the post-launch candidate.

**route_planner_view.py (2 widgets, 12 dynamic re-setter call sites):** empty-error label + summary-text (runtime state colors — dynamic class).

**components.py (dynamic internals):** ActionButton color inference, KPICard value, CompactKPICard value+trend, StatusBadge dynamic colors, IconButton color params, FilterChip/Toggle runtime states — component-API-driven runtime styling (accepted).

### (c) Reverted conversions (honest static-keeps, measured non-parity)
- `related_label` (automation_view) — superseded by the `helper` conversion (final remediation)
- `color:` HLine dividers (fleet_tracking, dashboard) — hairline role changes paint mechanism; kept with hairline as candidate

### (d) Gate false-positive annotations (role_inventory dead=7, kept)
`QPushButton[variant="danger"]` (+hover), `QLineEdit[validation="success"]`, `QFrame#stat-card[hovered="true"]`, `QPushButton[tabRole="tab-button"][tabActive="true"]`, `QDialog[modal="true"]` (real Q_PROPERTY), `QLabel[role="pill-value"]` (StateLabel variable setter) — live via variable/bool/Q_PROPERTY setters invisible to the string-literal scanner; annotated in the theme_engine catalog header.

## 5. Final boundary commit (gate-5 M2)

Explicit staging; verified via `git diff --cached`:
- Include: phase-5 files (route_planner_view, components.py, theme_engine.py, automation_view, trip_card, fleet_tracking_view, overview_view, tacho_import_view, dashboard — partial-staged, its sprint plotly hunk excluded, connect_view/cmr files), tools/ui_audit_harness.py, tools/ui_style_gate.py, **tools/ui_style_gate_baseline.json** (304-state PASS depends on it), the `.gitignore` hunk (`.slim/deepwork/`), **this snapshot (docs/qss-burndown.md)**, phase-5 evidence dirs (evidence_final5, evidence_dpi, evidence_p5a/p5b/p5d*).
- Exclude: `ui/styles.py` deletion + all other unrelated sprint files (471 modified files in tree).

## 6. Post-launch candidates (from this record)

class=* wire-up project (with the role list in §3); static-keep mint list (§4b); hairline divider adoption; StateLabel/Dot unit tests (m5 pattern); harness timeout already landed; theme_engine per-domain split revisit if >3.5k lines (with order-preservation test).