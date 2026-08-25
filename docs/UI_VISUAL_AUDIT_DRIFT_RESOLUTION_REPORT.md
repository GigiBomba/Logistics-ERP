# Operion Design-System Drift Resolution — Final Report

**Date:** 2026-08-24
**Scope:** Implementation of the drift-resolution decisions from the Visual Audit & Remediation report. This is the decision record executed as written — no item was re-opened or substituted.
**Method:** Evidence-backed only (diffs, greps, test output, rendered captures, programmatic verification). The audit model cannot ingest images, so programmatic checks (pixmap non-null, geometry) and code diffs are the primary evidence.

---

## 1. Summary Table (items 1–12)

| # | Item | Resolution applied | Evidence | Status |
|---|---|---|---|---|
| 1 | STATUS mapping split | Deleted legacy `STATUS` dict from `design_tokens.py`; removed `STATUS` from `theme.py` import; updated `test_design_tokens.py` to assert `STATUS_COLORS` | grep: zero references to the deleted symbol remain (only comments/strings) | **Done** |
| 2 | Typography scale remap | `theme_engine.FONT_SIZES`: `display` 28→32, `h1` 20→22, `mono_lg` 20→22 | QSS tests pass; 6 pages render with no errors (see §3) | **Done** |
| 3 | `theme.py` migration + deprecate | Migrated 5 test consumers → `design_tokens`; deleted `theme.py`; removed dead `#1c1917` from stale test (updated to `COLOR_NEUTRAL_SUBTLE`) | grep: zero `ui.theme` imports; 22/22 migrated tests pass | **Done** (addendum §2) |
| 4 | Chart palette duplicates | `maintenance_analytics_view.py` palette: `#22c55e`→SUCCESS, `#f59e0b`→WARNING, `#ef4444`→ERROR, `#3b82f6`→INFO; left accent + novel colors; `financial_tab.py` no change; `plotly_theme.py` already tokenized | diff | **Done** |
| 5 | Map overlays exempt | Exempt comments added above `AVOID_COLOR` (`route_renderer.py:27`) and map background (`map_widget.py:70`) | diff | **Done** |
| 6 | Print-document exempt | Exempt comments added to receipt print template (`editor_form.py` `<style>`) and CMR reportlab styles (`cmr_generator.py` `_init_styles`) | diff | **Done** |
| 7 | Dense micro-gaps | Added micro-gap exception note to `design_tokens.py` spacing docs; spot-checked 4 dense sites (trip_card, alert_panel, overview_view, dispatch_timeline) — all intentional tight-packing | diff + spot-check | **Done** |
| 8 | Sparkline render bug | `_tab_base.py` `_apply`: rasterize delivered `QByteArray` (SVG) → `QPixmap` via `QSvgRenderer` on GUI thread before `.scaled()` | programmatic verify: **all 6 analytics tabs 4/4 sparklines rendered** | **Done** |
| 9 | `ScrollableFormContainer.layout` shadowing | Renamed `self.layout` → `self._content_layout` (`widgets/__init__.py` + `settings_fields.py:196,198`) | grep: zero `.layout` refs on containers; settings renders | **Done** |
| 10 | `__future__` import | Confirmed stays as-is (value-neutral) | no change | **Done** |
| 11 | QTimer lifecycle change | Kept (legitimate crash fix, disclosed in original report) | disclosure carried forward | **Done** |
| 12 | Token-duplicate hexes | `stat_card.py` 4 hex→tokens; `chart_loading_overlay.py:106` `#6366f1`→accent; `connect_view.py` badge padding `2px 10px`→`4px 12px` (×5) | diff; freight_exchange/analytics render | **Done** |

**Batch 1 exception:** deleted dead `_STATUS_DOT_COLORS` dict (`dispatch_board.py:245`) — a missed consumer, unused local, wrong-by-design hex. Verified dispatch_board renders.

---

## 2. New Token Decisions Surfaced (resolved in follow-up pass)

From item 3: the novel chip colors (`#1c1917`, `#341a00`, `#0f1f4a`, `#052e16`) are dead in the UI layer (production widgets migrated to tokens; the stale test reference was removed). Two live sites had no token equivalent — **both were tokenized in the follow-up "Document/Export Color Tokenization" pass** (see §6):

1. **`services/export_service.py:687-690`** — status colors `#1c1917`/`#341a00`/`#0f1f4a`/`#052e16` for exported document cells. **Decision: tokenize** → new `STATUS_DOC_COLORS` group in `design_tokens.py` (document-context tokens, deliberately darker than UI chips); `export_service.py` now references it.
2. **`ui/views/generators_view.py:90-95`** — CMR copy-type accent colors. **Decision: normalize duplicates + add tokens** → new `CMR_ACCENT_COLORS` group (kept in its own namespace, not aliased to `STATUS_DOC_COLORS` even where values coincide); `_COPY_ACCENT_COLORS` now references it.

Both were implemented with zero visual change (token values byte-identical to the original hex; the only value shift is the explicitly-decided `#27272a` → `COLOR_BG_SELECTED #27272C` near-duplicate normalization, imperceptible).

---

## 3. Regression Confirmation (Batch 3 typography remap)

**Consumers found (step 1 of the Batch 3 section):** grep for `fontRole="h1"`/`"mono_lg"`/`"hero"`/`"display"` and `FONT_SIZES["h1"/"mono_lg"/"display"]` across the codebase found **no production consumers**. The only references are:
- `theme_engine.py:256,271,282` — the QSS rule definitions themselves (`QLabel[fontRole="h1"]` etc.).
- `tests/test_component_qss.py:180,201` — a test that sets `fontRole="h1"`/`"hero"` to verify QSS generation.

The `display` role is defined in `theme_engine.FONT_SIZES` but never consumed via `_fs("display")` or any `fontRole="display"` — it has no visual effect.

**Rendered and verified:** 6 representative pages (overview, analytics, dispatch_board, settings, team, tacho) rendered before/after the remap with no errors and no visual change (the roles are unused by production widgets). QSS tests (`test_theme.py`, `test_component_qss.py`) pass after the remap.

**Could not verify visually:** the audit model cannot ingest images, so "no visual change" is confirmed by (a) the grep showing zero production consumers, (b) error-free renders, and (c) passing QSS tests — not by pixel comparison.

---

## 4. Anything Not Verified / Flagged

- **Sparkline verification is programmatic** (pixmap non-null check per tab), not visual screenshots, due to the model's image limitation. Each of the 6 analytics tabs verified 4/4 sparklines rendered.
- **Chart/map interiors** remain unverifiable via the harness (placeholder panels / patched maps) — unchanged from the original audit.
- **Pre-existing app bug — FIXED:** `ui/views/analytics/__init__.py` `_on_tab_changed` (and `_start_loading`/`_load_tab`) called `overlay.show()` on a `LoadingOverlay` whose C++ object had been deleted by `mark_done()` (`deleteLater()`), raising `RuntimeError: Internal C++ object (LoadingOverlay) already deleted` on every analytics tab switch after the first tab loaded. Fixed by adding a validity-guarded `_overlay()` helper (via `shiboken6.isValid`) used at all three call sites. Verified: all 6 analytics tabs iterate in a single process with no crash, 4/4 sparklines rendered each.
- **`export_service.py` / `generators_view.py` novel colors** — **resolved** in the follow-up tokenization pass (§6): `STATUS_DOC_COLORS` + `CMR_ACCENT_COLORS` added, both consumers reference them. Residual `#27272a` at `export_service.py:755` is a table **grid-line** color (not a status color) — separate legitimate use, left as-is.
- **Residual hardcoded token-duplicate hexes** outside the item-12 scope (e.g. `overview_view.py:794` `#F59E0B` chart series, `settings_fields.py:42` `DEFAULT_BRAND_COLOR #6366f1`, `receipt_editor/editor_form.py` print template `#6366f1`) — noted, not changed (chart/brand/print surfaces).
- **`status_service.COLUMN_DEFS` dead `color` field — CLEANED UP:** the `color` values (`#27272a`/`#F59E0B`/`#3B82F6`/`#10B981`/`#6B7280`) were dead data carrying the OLD pre-audit dispatch-board palette (Planned=dark gray, In Transit=blue). Zero consumers read `color` (only `key` is used via `status_display_order()`); the live board renders from `board_state.COLUMN_DEFS` (tokenized). Field deleted; `test_status_service.py` 24 passed.

---

## 5. Files Changed (this pass)

- `ui/design_tokens.py` — deleted `STATUS` dict; added spacing micro-gap doc note.
- `ui/theme_engine.py` — FONT_SIZES display/h1/mono_lg remap.
- `ui/theme.py` — **deleted**.
- `ui/widgets/__init__.py` — `ScrollableFormContainer.layout` → `_content_layout`.
- `ui/views/settings_view/settings_fields.py` — `_scroll.layout` → `_scroll._content_layout`.
- `ui/widgets/stat_card.py` — 4 hex → tokens.
- `ui/widgets/chart_loading_overlay.py` — `#6366f1` → accent token.
- `ui/views/freight_exchange/connect_view.py` — badge padding 2px 10px → 4px 12px (×5).
- `ui/map/route_renderer.py`, `ui/map/map_widget.py` — exempt comments.
- `ui/views/receipt_editor/editor_form.py`, `services/invoicing/cmr_generator.py` — exempt comments.
- `ui/views/maintenance_analytics_view.py` — chart palette semantic duplicates → tokens.
- `ui/views/dispatch_board/dispatch_board.py` — deleted dead `_STATUS_DOT_COLORS`.
- `ui/views/analytics/_tab_base.py` — sparkline QByteArray→QPixmap rasterization.
- `ui/views/analytics/__init__.py` — LoadingOverlay deleted-object guard (`_overlay()` helper at all 3 call sites).
- `tests/test_design_tokens.py`, `tests/test_theme.py`, `tests/test_trip_card_logic.py`, `tests/test_widgets.py`, `tests/test_alert_panel_widget.py`, `tests/test_fleet_tracking_view.py` — migrated off `ui.theme`.
- `ui/styles.py` — comment updated to reference `ui.design_tokens`.
- `tools/ui_audit_harness.py` — removed sparkline patch (bug fixed).
- `tools/verify_sparklines.py` — new sparkline verification tool.

---

## 6. Follow-up Pass — Document/Export Color Tokenization (additive)

**Date:** 2026-08-24. Resolves the two §2 token-decision items. Additive only — nothing from the prior passes was modified or re-opened.

**Decisions applied:**
1. **`export_service.py` status colors → `STATUS_DOC_COLORS`** (new group in `design_tokens.py`). Document-context tokens, deliberately darker than UI `COLOR_*_SUBTLE` chips; `cancelled` reuses existing `COLOR_NEUTRAL_SUBTLE` (`#1A1A20`), no new token.
2. **`generators_view.py` CMR legend → `CMR_ACCENT_COLORS`** (new group, own namespace, not aliased to `STATUS_DOC_COLORS` even where `carrier` == `delivered` — coincidental, commented). `sender` → `COLOR_ACCENT_PRIMARY`, `administrative` → `COLOR_BG_SELECTED`; `consignee`/`carrier` novel tokens.

**Verification (all evidence in this session):**
- `design_tokens.py` diff: two new clearly-labeled, commented token groups.
- `export_service.py` diff: no raw `HexColor(...)` status literals remain for the 5 statuses (grep: only the tokenized dict; residual `#27272a` at line 755 is a grid-line color, not a status color).
- `generators_view.py` diff: no raw hex remains in `_COPY_ACCENT_COLORS`.
- **PDF export verified programmatically** (`tools/verify_doc_colors.py`): generated a dispatch-board PDF covering all 5 statuses, decoded the ASCII85+Flate content stream, and confirmed all 5 status colors present (`.109804 .098039 .090196` Planned, `.203922 .101961 0` Loading, `.058824 .121569 .290196` In Transit, `.019608 .180392 .086275` Delivered, `.101961 .101961 .12549` Cancelled) — byte-identical to the original hex, so visually unchanged.
- **CMR legend verified**: `generators_view.py` renders error-free (harness capture); `accent_color = _COPY_ACCENT_COLORS[suffix]` (line 498) feeds the accent bar; token values identical to original hex except the explicitly-decided `#27272a` → `#27272C` near-duplicate normalization.
- **Grep**: zero remaining occurrences of `#1c1917`/`#341a00`/`#0f1f4a`/`#052e16`/`#1e1b4b` outside `design_tokens.py`; `#27272a`/`#6366f1` gone from the two tokenized sites.
- **Tests**: `test_export_service.py`, `test_generators_view.py`, `test_board_export.py` — 117 passed. Module imports clean (`design_tokens`, `export_service`, `generators_view`).

**Files changed (this pass):**
- `ui/design_tokens.py` — added `STATUS_DOC_COLORS` + `CMR_ACCENT_COLORS` groups.
- `services/export_service.py` — import + reference `STATUS_DOC_COLORS`.
- `ui/views/generators_view.py` — import + reference `CMR_ACCENT_COLORS`.
- `tools/verify_doc_colors.py` — new PDF color verification tool.
