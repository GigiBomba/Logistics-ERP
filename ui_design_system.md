# Operion ERP — P0 Design System Cleanup Blueprint

> **Status:** Emergency optimization  
> **Scope:** 20+ PySide6 views  
> **Goal:** One canonical dark theme, zero module overrides, zero hardcoded values  

---

## 1. Canonical Design System

### 1.1 Spacing — exactly 4 values

All layout margins, padding, and gaps must resolve to one of these four tokens. No exceptions.

| Token | Value | Usage |
|-------|-------|-------|
| `SPACE_XS` | `8` | Tight gaps, icon-to-label spacing, checkbox spacing |
| `SPACE_SM` | `16` | Card internal padding, section gaps, button padding |
| `SPACE_MD` | `24` | Form section margins, dialog padding |
| `SPACE_LG` | `32` | Page gutters, major section breaks |

**Legacy numeric keys** (`SP["1"]` / `S["1"]` etc.) are remapped so existing code automatically resolves to the 4-value grid without renaming every call site:

```python
# ui/design_tokens.py
SP = {
    "1": SPACE_XS,   # 8  (was 4 — eliminated)
    "2": SPACE_XS,   # 8
    "3": SPACE_SM,   # 16 (was 12 — fixed)
    "4": SPACE_SM,   # 16
    "5": SPACE_MD,   # 24 (was 20 — fixed)
    "6": SPACE_MD,   # 24
    "8": SPACE_LG,   # 32
}
# Keys "10", "12", "16" are deleted.
```

### 1.2 Typography — exactly 3 levels

| Level | Size | Weight | Usage |
|-------|------|--------|-------|
| **Body** | `12px` | 400 / 600 | Body text, labels, table cells, badges, helper text |
| **Section** | `13px` | 600 | Section headers, tab labels, card subtitles, navigation |
| **Page** | `16px` | 600 / 700 | Page titles, KPI values, hero numbers, top-bar clock |

All other sizes are violations. `11px` and smaller text is banned. Data-dense widgets (tables, CMR badges) must use **Body (12px)** minimum.

### 1.3 Surface & Border Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `COLOR_BG_BASE` | `#0C0C0E` | App background |
| `COLOR_BG_ELEVATED` | `#141416` | Card / panel background |
| `COLOR_BG_OVERLAY` | `#1C1C1F` | Inputs, dropdowns, table rows |
| `COLOR_BORDER_SUBTLE` | `#2A2A30` | **Canonical card border** (1px) |
| `COLOR_BORDER_MEDIUM` | `#38383F` | Input / focus border |
| `COLOR_BORDER_STRONG` | `#505058` | Dividers, strong separators |

**Rule:** Every card, frame, or elevated surface uses `COLOR_BORDER_SUBTLE`. `COLOR_BORDER_MEDIUM` is reserved for input fields and focused states only.

### 1.4 Border Radius — exactly 4 tokens

| Token | Value | Usage |
|-------|-------|-------|
| `RADIUS_SM` | `4px` | Checkboxes, small badges, scrollbar handles, tiny dots |
| `RADIUS_MD` | `6px` | Buttons, inputs, tabs, menu items, group boxes |
| `RADIUS_LG` | `8px` | Cards, dialogs, kanban columns, calendars, toasts |
| `RADIUS_PILL` | `100px` | Radio buttons, status dots, monogram circles, pill badges |

**Eliminated:** `RADIUS_XL = 12` is removed from `design_tokens.py`.

### 1.5 Component Primitives — exactly 1 style each

| Primitive | Canonical Source | Key Properties |
|-----------|-------------------|----------------|
| **Card** | `theme_engine.py` → `_frame_qss()` | `bg: COLOR_BG_ELEVATED`, `border: 1px solid COLOR_BORDER_SUBTLE`, `radius: RADIUS_LG` |
| **Button** | `theme_engine.py` → `_button_qss()` | `min-height: 38px`, `radius: RADIUS_MD`, `padding: 8px 16px` |
| **Table** | `theme_engine.py` → `_table_qss()` | `bg: COLOR_BG_ELEVATED`, `alternate-bg: COLOR_BG_OVERLAY`, `gridline: COLOR_BORDER_MEDIUM`, `header: 12px uppercase` |
| **Input** | `theme_engine.py` → `_input_qss()` | `bg: COLOR_BG_OVERLAY`, `border: 1px solid COLOR_BORDER_MEDIUM`, `radius: RADIUS_MD`, `padding: 6px 10px` |

---

## 2. Inconsistency Map — File-by-File Fixes

### 2.1 Spacing Grid Violations

#### `ui/design_tokens.py` (lines 92–101, 197–207)
**Problem:** `SPACE_3 = 12`, `SPACE_5 = 20`, plus `SPACE_10 = 40`, `SPACE_12 = 48`, `SPACE_16 = 64` exist.

**Fix:**
```python
# BEFORE (lines 92-101)
SPACE_1  = 4
SPACE_2  = 8
SPACE_3  = 12
SPACE_4  = 16
SPACE_5  = 20
SPACE_6  = 24
SPACE_8  = 32
SPACE_10 = 40
SPACE_12 = 48
SPACE_16 = 64

# AFTER
SPACE_XS = 8
SPACE_SM = 16
SPACE_MD = 24
SPACE_LG = 32

# Legacy numeric aliases (lines 197-207)
# BEFORE
SP = {
    "1": SPACE_1,
    "2": SPACE_2,
    "3": SPACE_3,
    "4": SPACE_4,
    "5": SPACE_5,
    "6": SPACE_6,
    "8": SPACE_8,
    "10": SPACE_10,
    "12": SPACE_12,
    "16": SPACE_16,
}

# AFTER
SP = {
    "1": SPACE_XS,
    "2": SPACE_XS,
    "3": SPACE_SM,
    "4": SPACE_SM,
    "5": SPACE_MD,
    "6": SPACE_MD,
    "8": SPACE_LG,
}
```

#### `ui/theme.py` (lines 129–139)
**Problem:** `S` dict mirrors the old 10-key spacing scale.

**Fix:**
```python
# BEFORE
S = {
    "1":  SPACE_1,
    "2":  SPACE_2,
    "3":  SPACE_3,
    "4":  SPACE_4,
    "5":  SPACE_5,
    "6":  SPACE_6,
    "8":  SPACE_8,
    "10": SPACE_10,
    "12": SPACE_12,
}

# AFTER
S = {
    "1":  SPACE_XS,
    "2":  SPACE_XS,
    "3":  SPACE_SM,
    "4":  SPACE_SM,
    "5":  SPACE_MD,
    "6":  SPACE_MD,
    "8":  SPACE_LG,
}
```

#### `ui/theme_engine.py` (line 157)
**Problem:** `_px()` helper still encodes the old scale including `5: 20`.

**Fix:**
```python
# BEFORE (line 157)
sizes = {"2": 8, "4": 16, "5": 20, "6": 24, "8": 32, "10": 40, "12": 48, "16": 64}

# AFTER
sizes = {"2": 8, "4": 16, "6": 24, "8": 32}
```

#### Files using deleted keys `SP["10"]` / `S["10"]` / `SP["12"]` / `S["12"]` / `SP["16"]` / `S["16"]`
These must be replaced with `SP["8"]` (32px) or `SPACE_LG`.

| File | Line | Before | After |
|------|------|--------|-------|
| `ui/widgets/__init__.py` | 296 | `S["10"]` | `S["8"]` |
| `ui/widgets/kanban_column.py` | 188, 199 | `S["10"]` | `S["8"]` |
| `ui/views/team_view.py` | 67 | `SP["10"]` | `SP["8"]` |
| `ui/views/settings_view/settings_view.py` | 218, 237 | `SP["10"]` | `SP["8"]` |
| `ui/views/route_history_view.py` | 108 | `SP["10"]` | `SP["8"]` |
| `ui/views/overview_view.py` | 194, 206 | `SP["10"]` | `SP["8"]` |
| `ui/views/maintenance_control_panel.py` | 168, 190 | `SP["10"]` | `SP["8"]` |
| `ui/views/maintenance_analytics_view.py` | 122 | `SP["10"]` | `SP["8"]` |
| `ui/views/history_view.py` | 100, 113 | `SP["10"]` | `SP["8"]` |
| `ui/views/generators_view.py` | 191 | `SP["10"]` | `SP["8"]` |
| `ui/views/fleet_tab/fleet_tab.py` | 262 | `SP["10"]` | `SP["8"]` |
| `ui/views/driver_manager.py` | 433 | `SP["10"]` | `SP["8"]` |
| `ui/views/dispatch_board/dispatch_board.py` | 219 | `SP["10"]` | `SP["8"]` |
| `ui/views/dashboard.py` | 330 | `SP["10"]` | `SP["8"]` |
| `ui/views/client_workspace/client_workspace.py` | 226 | `SP["10"]` | `SP["8"]` |
| `ui/views/client_manager.py` | 151 | `SP["10"]` | `SP["8"]` |
| `ui/views/analytics/__init__.py` | 127, 184 | `SP["10"]` | `SP["8"]` |
| `ui/views/analytics/_tab_base.py` | 474 | `SP["10"]` | `SP["8"]` |
| `ui/views/calculator_view.py` | 152 | `SP["10"]` | `SP["8"]` |
| `ui/views/bulk_payments_view.py` | 333, 345 | `SP["10"]` | `SP["8"]` |
| `tests/test_design_tokens.py` | 18, 59 | `SPACE_16` / `SP["16"]` | `SPACE_LG` / `SP["8"]` |

#### Hardcoded spacing values (not using tokens)

| File | Line | Before | After |
|------|------|--------|-------|
| `ui/widgets/topbar.py` | 62 | `setContentsMargins(20, 0, 16, 0)` | `setContentsMargins(SPACE_MD, 0, SPACE_SM, 0)` |
| `ui/widgets/toast.py` | 35 | `setContentsMargins(16, 12, 16, 12)` | `setContentsMargins(SPACE_SM, SPACE_SM, SPACE_SM, SPACE_SM)` |
| `ui/widgets/sidebar.py` | 143 | `setContentsMargins(12, 0, 12, 0)` | `setContentsMargins(SPACE_SM, 0, SPACE_SM, 0)` |
| `ui/widgets/chart_loading_overlay.py` | 90 | `setSpacing(12)` | `setSpacing(SPACE_SM)` |
| `ui/dialogs/maintenance_view.py` | 86 | `setContentsMargins(20, 10, 20, 10)` | `setContentsMargins(SPACE_MD, SPACE_XS, SPACE_MD, SPACE_XS)` |
| `ui/views/route_planner_view.py` | 92 | `setContentsMargins(0, 20, 0, 10)` | `setContentsMargins(0, SPACE_MD, 0, SPACE_XS)` |
| `ui/views/route_planner_view.py` | 495 | `setContentsMargins(16, 16, 16, 12)` | `setContentsMargins(SPACE_SM, SPACE_SM, SPACE_SM, SPACE_SM)` |
| `ui/views/route_planner_view.py` | 504 | `setContentsMargins(16, 12, 16, 12)` | `setContentsMargins(SPACE_SM, SPACE_SM, SPACE_SM, SPACE_SM)` |
| `ui/views/country_exclusions_dialog.py` | 59 | `setSpacing(12)` | `setSpacing(SPACE_SM)` |
| `ui/skeleton_widgets.py` | 136, 270 | `setSpacing(12)` | `setSpacing(SPACE_SM)` |
| `ui/views/analytics/document_tab.py` | 102 | `setSpacing(12)` | `setSpacing(SPACE_SM)` |
| `ui/views/analytics/financial_tab.py` | 242 | `setContentsMargins(12, 8, 12, 8)` | `setContentsMargins(SPACE_SM, SPACE_XS, SPACE_SM, SPACE_XS)` |

---

### 2.2 Border Radius Inconsistency

#### `ui/design_tokens.py` (line 107)
**Problem:** `RADIUS_XL = 12` is not in the canonical 4-token set.

**Fix:**
```python
# BEFORE (line 107)
RADIUS_XL  = 12

# AFTER — delete the line entirely.
```
Also delete `"xl": RADIUS_XL` from the `RADIUS` legacy dict (line 211–216).

#### `ui/theme_engine.py` — hardcoded radii inside QSS strings

| Line | Before | After | Reason |
|------|--------|-------|--------|
| 502 | `border-radius: 9px;` | `border-radius: {RADIUS_PILL}px;` | Radio indicator (18×18) → perfect circle |
| 867 | `border-radius: 2px;` | `border-radius: {RADIUS_SM}px;` | Accent bar (3px wide) |
| 1051 | `border-radius: 2px;` | `border-radius: {RADIUS_SM}px;` | Nav accent (3px wide) |
| 1182 | `border-radius: 9px;` | `border-radius: {RADIUS_PILL}px;` | Badge (18×18) → perfect circle |

#### `ui/widgets/sidebar.py` (line 150)
**Fix:**
```python
# BEFORE (line 150)
f"background: {ACCENT}; border-radius: 16px;"

# AFTER
f"background: {ACCENT}; border-radius: {RADIUS_PILL}px;"
```
Also add import: `from ui.design_tokens import RADIUS_PILL`.

#### `ui/widgets/sidebar.py` (line 306)
**Fix:**
```python
# BEFORE (line 306)
accent.setStyleSheet("background: transparent; border-radius: 2px;")

# AFTER
accent.setStyleSheet(f"background: transparent; border-radius: {RADIUS_SM}px;")
```

#### `ui/widgets/trip_card.py` (lines 176, 193, 338, 594, 636, 668)
**Fix:** Replace every `border-radius: 3px;` with `border-radius: {RADIUS_SM}px;` (use f-string with token import).

#### `ui/widgets/topbar.py` (lines 78, 98, 131, 133)
**Fix:**
- Line 78: `border-radius: 3px;` → `border-radius: {RADIUS_SM}px;`
- Line 98: `border-radius: 8px;` → `border-radius: {RADIUS_LG}px;`
- Lines 131, 133: `border-radius: 3px;` → `border-radius: {RADIUS_SM}px;`

#### `ui/widgets/dispatch_alerts_panel.py` (line 267)
**Fix:** `border-radius: 3px;` → `border-radius: {RADIUS_SM}px;`

#### `ui/dialogs/dispatch_detail_panel.py` (lines 325, 489)
**Fix:**
- Line 325: `border-radius: 3px;` → `border-radius: {RADIUS_SM}px;`
- Line 489: `border-radius: 6px;` → `border-radius: {RADIUS_MD}px;` (already canonical, but tokenize it)

#### `ui/views/route_planner_view.py` (lines 179, 216, 281, 488, 728, 732)
**Fix:**
- Line 179: `border-radius: 5px;` → `border-radius: {RADIUS_MD}px;`
- Line 216: `border-radius: 3px;` → `border-radius: {RADIUS_SM}px;`
- Line 281: `border-radius: 6px !important;` → `border-radius: {RADIUS_MD}px !important;` (already canonical, tokenize)
- Line 488: `border-radius: 2px;` → `border-radius: {RADIUS_SM}px;`
- Lines 728, 732: `border-radius: 2px;` → `border-radius: {RADIUS_SM}px;`

#### `ui/views/fleet_tracking_view.py` (lines 337, 500)
**Fix:** `border-radius: 5px;` → `border-radius: {RADIUS_PILL}px;` (10×10 status dots should be circles).

#### `ui/views/generators_view.py` (line 435)
**Fix:** `border-radius: 2px;` → `border-radius: {RADIUS_SM}px;`

#### `ui/views/maintenance_control_panel.py` (lines 213, 214, 392, 393)
**Fix:** `border-radius: 2px;` → `border-radius: {RADIUS_SM}px;` (progress-bar chunks).

#### `ui/views/country_exclusions_dialog.py` (line 73)
**Fix:** `border-radius: 2px;` → `border-radius: {RADIUS_SM}px;`

#### `ui/views/analytics/financial_tab.py` (lines 164, 168)
**Fix:** `border-radius: 3px;` → `border-radius: {RADIUS_SM}px;`

#### `ui/views/analytics/driver_tab.py` (lines 311, 317)
**Fix:** `border-radius: 3px;` → `border-radius: {RADIUS_SM}px;`

#### `ui/views/analytics/client_tab.py` (line 367)
**Fix:** `border-radius: 3px;` → `border-radius: {RADIUS_SM}px;`

#### `ui/views/cmr_form_view/cmr_form.py` (lines 151, 157, 163, 227, 433)
**Fix:** All `border-radius: 4px;` and `border-radius: 3px;` → `border-radius: {RADIUS_SM}px;`.

#### `ui/views/cmr_form_view/cmr_fields.py` (line 635)
**Fix:** `border-radius: 3px;` → `border-radius: {RADIUS_SM}px;`

#### `ui/views/automail/timeline_panel.py` (lines 522, 526)
**Fix:** `border-radius: 12px;` → `border-radius: {RADIUS_PILL}px;` (pill buttons).

#### `ui/widgets/chart_loading_overlay.py` (line 160)
**Fix:** `border-radius: 12px;` → `border-radius: {RADIUS_LG}px;`

#### `ui/dialogs/share_route_dialog.py` (line 273)
**Fix:** `border-radius: 8px;` → `border-radius: {RADIUS_LG}px;` (already canonical, tokenize).

---

### 2.3 Button Height Mismatch

**Resolution:** **Option A — Adopt 38px as the canonical button height.**

Rationale: The global QSS already renders at 38px (`min-height: 38px` in `theme_engine.py` line 338, and `QComboBox` min-height 38px line 527). Changing the QSS down to 32px would compress every form row and break vertical rhythm where inputs and buttons sit side-by-side. It is safer to update the token to match reality.

#### `ui/design_tokens.py` (line 224)
**Fix:**
```python
# BEFORE (line 224)
BTN_HEIGHT        = 32

# AFTER
BTN_HEIGHT        = 38
```

#### `ui/design_tokens.py` (line 223)
**Fix:** Also align `ROW_HEIGHT` and `INPUT_HEIGHT` to the 8px grid:
```python
# BEFORE (lines 222-225)
ROW_HEIGHT        = 38
INPUT_HEIGHT      = 32
BTN_HEIGHT        = 32
BTN_HEIGHT_SM     = 28

# AFTER
ROW_HEIGHT        = 38   # already matches grid
INPUT_HEIGHT      = 38   # align to button height for form rows
BTN_HEIGHT        = 38
BTN_HEIGHT_SM     = 32   # small button on 8px grid
```

#### `ui/theme_engine.py` (line 527)
**Fix:** Remove the hardcoded `min-height: 38px` from `QComboBox` QSS and replace with token reference so it stays in sync:
```python
# BEFORE (line 527)
min-height: 38px;

# AFTER
min-height: {BTN_HEIGHT}px;
```
Add `BTN_HEIGHT` to the `design_tokens` import block at the top of `theme_engine.py`.

---

### 2.4 Hardcoded Micro-fonts (< 10px)

**Rule:** No font size below `FONT_SIZE_BASE` (12px). All instances of `7px`, `8px`, `9px` are upgraded to 12px (Body) or 13px (Section) depending on context.

#### `ui/views/cmr_form_view/cmr_form.py` (lines 151, 157, 163, 227)
**Fix:** `font-size: 7px;` → `font-size: {FONT_SIZE_BASE}px;` (box navigator badges).

#### `ui/views/cmr_form_view/cmr_form.py` (line 433)
**Fix:** `font-size: 8px;` → `font-size: {FONT_SIZE_BASE}px;`.

#### `ui/views/cmr_form_view/cmr_fields.py` (line 635)
**Fix:** `font-size: 8px;` → `font-size: {FONT_SIZE_BASE}px;`.

#### `ui/views/receipt_editor/editor_form.py` (lines 1505, 1566, 1571)
**Fix:**
- Line 1505: `font-size: 8px;` → `font-size: 10px;` (HTML print preview — minimum readable print size)
- Line 1566: `font-size:8px` → `font-size:10px`
- Line 1571: `font-size:8px` → `font-size:10px`

> **Note:** Receipt HTML is rendered to print/PDF, not to screen. 10px is the hard floor for thermal-printer legibility. If the template must stay under 10px for layout reasons, the layout itself is broken and needs reflow, not smaller text.

#### `ui/views/analytics/driver_tab.py` (lines 280, 324)
**Fix:**
- Line 280: `font-size: 8px;` → `font-size: {FONT_SIZE_BASE}px;` (week header labels).
- Line 324: `font-size: 9px;` → `font-size: {FONT_SIZE_BASE}px;` (activity summary).

#### `ui/views/automail/timeline_panel.py` (line 212)
**Fix:** `font-size: 8px;` → `font-size: {FONT_SIZE_BASE}px;` (status dot label).

#### `ui/theme_engine.py` (line 218)
**Fix:** `font-size: {cls._fs("label")}px;` currently resolves to 11px. Update `FONT_SIZES["label"]` to 12px (see §3.1).

---

### 2.5 Card Border Color Mismatch

**Canonical:** All cards use `COLOR_BORDER_SUBTLE` (`#2A2A30`).

#### `ui/theme_engine.py` — `_frame_qss()` (lines 839–880)
**Problem:** `QFrame[role="card"]`, `QFrame[role="card-elevated"]`, and `QFrame[role="kpi-card"]` all use `COLOR_BORDER_MEDIUM` (`#38383F`).

**Fix:**
```python
# BEFORE (lines 839-849)
QFrame[role="card"] {{
    background-color: {COLOR_BG_ELEVATED};
    border: 1px solid {COLOR_BORDER_MEDIUM};
    border-radius: {RADIUS_CARD}px;
}}

QFrame[role="card-elevated"] {{
    background-color: {COLOR_BG_OVERLAY};
    border: 1px solid {COLOR_BORDER_MEDIUM};
    border-radius: {RADIUS_CARD}px;
}}

# ... (line 876-880)
QFrame[role="kpi-card"] {{
    background-color: {COLOR_BG_ELEVATED};
    border: 1px solid {COLOR_BORDER_MEDIUM};
    border-radius: {RADIUS_CARD}px;
}}

# AFTER
QFrame[role="card"] {{
    background-color: {COLOR_BG_ELEVATED};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_CARD}px;
}}

QFrame[role="card-elevated"] {{
    background-color: {COLOR_BG_OVERLAY};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_CARD}px;
}}

QFrame[role="kpi-card"] {{
    background-color: {COLOR_BG_ELEVATED};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_CARD}px;
}}
```

> `stylesheet.py` `_card_qss()` already uses `COLOR_BORDER_SUBTLE` — no change needed there.

---

## 3. Fixer Task List

Each task is atomic (one file or one mechanical pattern). Fixers should check off tasks as PRs.

### Task A — Token Foundation
- [ ] **A1** `ui/design_tokens.py` — Replace spacing block (lines 92–101) with `SPACE_XS/SM/MD/LG`. Remove `SPACE_10/12/16`. Update `SP` dict (lines 197–207).
- [ ] **A2** `ui/design_tokens.py` — Set `BTN_HEIGHT = 38`, `INPUT_HEIGHT = 38`, `BTN_HEIGHT_SM = 32` (lines 222–225).
- [ ] **A3** `ui/design_tokens.py` — Delete `RADIUS_XL = 12` (line 107) and `"xl": RADIUS_XL` from `RADIUS` dict.
- [ ] **A4** `ui/theme.py` — Update `S` dict (lines 129–139) to 7-key grid mapping to 4 values.
- [ ] **A5** `ui/theme_engine.py` — Update `_px()` sizes dict (line 157) to `{"2": 8, "4": 16, "6": 24, "8": 32}`.
- [ ] **A6** `ui/theme_engine.py` — Import `BTN_HEIGHT` and replace `min-height: 38px` in `_combobox_qss()` with `min-height: {BTN_HEIGHT}px`.

### Task B — Typography Consolidation
- [ ] **B1** `ui/theme_engine.py` — Collapse `FONT_SIZES` dict (lines 70–82) to 3 levels:
  ```python
  FONT_SIZES = {
      "body": 12,
      "section": 13,
      "page": 16,
      "small": 12,
      "label": 12,
      "mono": 12,
      "display": 16,
      "h1": 16,
      "h2": 16,
      "h3": 13,
      "hero": 16,
      "mono_lg": 16,
      "mono_xl": 16,
  }
  ```
- [ ] **B2** `ui/theme_engine.py` — Update `_typography_qss()` so `page-title`, `section-title`, `kpi-value`, `kpi-label`, `field-label` all resolve to the 3 canonical sizes (12 / 13 / 16).
- [ ] **B3** `ui/stylesheet.py` — `_section_header_qss()` (line 109): `font-size: 11px` → `font-size: 12px`.
- [ ] **B4** `ui/views/cmr_form_view/cmr_form.py` — Tokenize and upgrade 7px / 8px badge fonts to 12px (lines 151, 157, 163, 227, 433).
- [ ] **B5** `ui/views/cmr_form_view/cmr_fields.py` — Upgrade 8px badge font to 12px (line 635).
- [ ] **B6** `ui/views/receipt_editor/editor_form.py` — Upgrade 8px footer/signature fonts to 10px (lines 1505, 1566, 1571).
- [ ] **B7** `ui/views/analytics/driver_tab.py` — Upgrade 8px / 9px fonts to 12px (lines 280, 324).
- [ ] **B8** `ui/views/automail/timeline_panel.py` — Upgrade 8px dot font to 12px (line 212).

### Task C — Border Radius Sweep
- [ ] **C1** `ui/theme_engine.py` — Tokenize hardcoded radii: line 502 (9px→PILL), 867 (2px→SM), 1051 (2px→SM), 1182 (9px→PILL).
- [ ] **C2** `ui/widgets/sidebar.py` — Tokenize monogram (16px→PILL, line 150) and nav-accent (2px→SM, line 306).
- [ ] **C3** `ui/widgets/trip_card.py` — Replace all 6 instances of `border-radius: 3px` with `RADIUS_SM`.
- [ ] **C4** `ui/widgets/topbar.py` — Replace 3px/8px radii with `RADIUS_SM` / `RADIUS_LG` (lines 78, 98, 131, 133).
- [ ] **C5** `ui/widgets/dispatch_alerts_panel.py` — Replace 3px radius with `RADIUS_SM` (line 267).
- [ ] **C6** `ui/dialogs/dispatch_detail_panel.py` — Replace 3px/6px radii with tokens (lines 325, 489).
- [ ] **C7** `ui/views/route_planner_view.py` — Replace 2px/3px/5px radii with tokens (lines 179, 216, 488, 728, 732). Leave 6px as-is (already canonical) but optional tokenization.
- [ ] **C8** `ui/views/fleet_tracking_view.py` — Replace 5px status-dot radii with `RADIUS_PILL` (lines 337, 500).
- [ ] **C9** `ui/views/generators_view.py` — Replace 2px radius with `RADIUS_SM` (line 435).
- [ ] **C10** `ui/views/maintenance_control_panel.py` — Replace 2px progress radii with `RADIUS_SM` (lines 213, 214, 392, 393).
- [ ] **C11** `ui/views/country_exclusions_dialog.py` — Replace 2px scrollbar radius with `RADIUS_SM` (line 73).
- [ ] **C12** `ui/views/analytics/*_tab.py` — Replace 3px radii with `RADIUS_SM` (`financial_tab` lines 164/168, `driver_tab` lines 311/317, `client_tab` line 367).
- [ ] **C13** `ui/views/cmr_form_view/cmr_form.py` & `cmr_fields.py` — Replace 3px/4px radii with `RADIUS_SM`.
- [ ] **C14** `ui/views/automail/timeline_panel.py` — Replace 12px pill radii with `RADIUS_PILL` (lines 522, 526).
- [ ] **C15** `ui/widgets/chart_loading_overlay.py` — Replace 12px radius with `RADIUS_LG` (line 160).

### Task D — Card Border Color Unification
- [ ] **D1** `ui/theme_engine.py` — `_frame_qss()`: change `COLOR_BORDER_MEDIUM` → `COLOR_BORDER_SUBTLE` on `role="card"`, `role="card-elevated"`, `role="kpi-card"`.

### Task E — Spacing Hardcode Cleanup
- [ ] **E1** `ui/views/analytics/__init__.py` — Replace `SP["10"]` with `SP["8"]` (lines 127, 184).
- [ ] **E2** `ui/views/analytics/_tab_base.py` — Replace `SP["10"]` with `SP["8"]` (line 474).
- [ ] **E3** `ui/views/*` (bulk) — Replace all `SP["10"]` / `S["10"]` usages with `SP["8"]` / `S["8"]` (see table in §2.1).
- [ ] **E4** `ui/views/*` & `ui/widgets/*` — Replace hardcoded `12`, `16`, `20` in `setContentsMargins` / `setSpacing` with tokens (see table in §2.1).
- [ ] **E5** `tests/test_design_tokens.py` — Update assertions for deleted `SPACE_16` and `SP["16"]`.

---

## 4. Module-Specific Override Removal Plan

### 4.1 Route Planner — Scrollbar Override

**File:** `ui/views/route_planner_view.py` (lines 485–490)

**Current:**
```python
scroll_area.setStyleSheet(f"""
    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ width: 4px; background: transparent; }}
    QScrollBar::handle:vertical {{ background: {COLOR_BORDER_MEDIUM}; border-radius: 2px; min-height: 20px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
""")
```

**Fix:** Delete the entire `setStyleSheet` call. The global `theme_engine.py` `_scrollbar_qss()` already provides a consistent 8px dark scrollbar. If the 4px width was intentional for a ultra-minimal sidebar, override **only** the width property via a single-line stylesheet, inheriting all other colors from the global theme:
```python
scroll_area.verticalScrollBar().setStyleSheet("QScrollBar:vertical { width: 4px; }")
```

**Leaflet CSS** (lines 272–305): The hardcoded colors (`#141416`, `#F0F0F3`, `#2A2A30`, `#222226`, `#38383F`) are actually the same as the design tokens, so they are acceptable for web-view content. The radii (4px, 6px) are canonical. **No change required** except optional tokenization if the CSS is generated from Python.

### 4.2 Analytics — Tab Styles & Scrollbar Override

**File:** `ui/views/analytics/__init__.py` (lines 139–144)

**Current:** Inline `QTabWidget` / `QTabBar` stylesheet that overrides the global theme.

**Fix:** Remove the `setStyleSheet` block entirely. Rely on `theme_engine.py` `_tabwidget_qss()`. If the analytics tabs need a bottom-border active indicator instead of the global filled-tab style, the global style should be updated to support `[role="analytics-tab"]` — not overridden locally.

**File:** `ui/views/analytics/_tab_base.py` (lines 446–469)

**Current:** Custom 12px-wide scrollbar with 6px radius and `ACCENT` hover.

**Fix:** Delete the custom `setStyleSheet` on `self._scroll`. The global scrollbar is 8px, `BORDER_MEDIUM` handle, `BORDER_STRONG` hover. This is the canonical experience. If analytics needs the scrollbar gutter, use `padding-right` on the content layout instead of a local scrollbar stylesheet.

### 4.3 API Dashboard — Duplicate ActionButton

**File:** `ui/views/api_dashboard_view.py` (lines 64–69)

**Current:**
```python
class _ActionButton(QPushButton):
    ...
```

**Fix:** Delete the class. Replace the one usage (not shown in the snippet, but the file imports `Btn` from `ui.components`). Ensure `Btn` is an alias for `ActionButton` or switch to:
```python
from ui.widgets import ActionButton
# Replace any _ActionButton(...) with ActionButton(...)
```

---

## 5. Navigation Rework (Phase 6)

### 5.1 Problem with Current Navigation

The current sidebar (`ui/widgets/sidebar.py`) exposes a flat list of views. Dispatchers think in **workflow stages**, not module names. A flat nav forces cognitive translation ("Where do I go to check a driver's tacho?" → "Driver Manager").

### 5.2 Proposed Workflow-Oriented Structure

Re-group the 20+ views into **5 dispatcher mental models**. Each group expands accordion-style in the sidebar. Only one group open at a time to reduce visual noise.

```
┌─ OPERION ERP ──────────────┐
│  [M]  Monogram             │
├────────────────────────────┤
│  DISPATCH  ▼               │
│    ▸ Dispatch Board        │
│    ▸ Route Planner         │
│    ▸ Calculator            │
│    ▸ Bulk Payments         │
│  FLEET  ▶                  │
│  DOCUMENTS  ▶              │
│  FINANCE  ▶                │
│  SYSTEM  ▶                 │
├────────────────────────────┤
│  [⚡]  Alerts              │
│  [👤]  Account             │
└────────────────────────────┘
```

#### Group 1 — DISPATCH (daily operations)
- Dispatch Board (kanban + timeline)
- Route Planner (map + optimization)
- Calculator (cost/profit estimator)
- Bulk Payments (driver settlements)

#### Group 2 — FLEET (assets & compliance)
- Fleet Tracking (live GPS)
- Driver Manager (profiles, tacho, documents)
- Vehicle Maintenance (schedules, alerts)
- Route History (completed trips)

#### Group 3 — DOCUMENTS (paperwork & legal)
- CMR Forms (international consignment notes)
- Receipt Editor (payment receipts)
- Proforma / Invoices (billing documents)
- Generators (labels, barcodes, customs docs)

#### Group 4 — FINANCE (reporting & analytics)
- Analytics Dashboard (financial, fleet, route, client, driver, document tabs)
- Client Workspace (client profitability, aging)
- API Dashboard (backend health — move here from System; it is a monitoring view)

#### Group 5 — SYSTEM (configuration)
- Settings (company, users, integrations)
- Automail (email templates & schedules)
- Automation Rules (workflow triggers)
- Team Management (permissions)
- Admin Panel (tenant-level config)

### 5.3 Implementation Notes for Phase 6

1. **Sidebar widget** (`ui/widgets/sidebar.py`): Replace the flat `nav-item` list with a `QVBoxLayout` of collapsible `QFrame` groups. Each group has a `nav-group-label` header that toggles visibility of its child list.
2. **Active state**: Only the active view gets the `nav-accent` bar and bold label. The parent group header gets a subtle `COLOR_ACCENT_PRIMARY` left border (2px) when any child inside is active.
3. **Keyboard shortcuts**: Assign `Alt+1` through `Alt+5` to the five groups. Dispatchers rarely use mice for navigation during high-volume shifts.
4. **Badge aggregation**: If Alerts exist, show the red badge on the **Account** footer item, not inside a group. Fleet maintenance alerts should bubble up to the **Fleet** group header as a small amber dot.
5. **Collapsed state**: When the sidebar is collapsed (`SIDEBAR_COLLAPSED = 48`), show only icons. On hover, a floating tooltip shows the group name + current view name.

---

## 6. Execution Order for Fixers

1. **Merge A1–A6 first** (token changes). This is a single PR that touches `design_tokens.py`, `theme.py`, and `theme_engine.py`.
2. **Merge B1–B8** (typography) + **C1–C15** (radius) + **D1** (border color) in parallel — these are mechanical replacements.
3. **Merge E1–E5** (spacing hardcodes) after tokens are in `main`.
4. **Merge module overrides** (§4) — remove analytics tab style, route-planner scrollbar, api_dashboard duplicate.
5. **Phase 6** (navigation rework) is a separate design sprint; do not block P0 launch on it.

---

## 7. Acceptance Criteria

- [ ] `grep -r "font-size: 7px\|font-size: 8px\|font-size: 9px" ui/` returns **zero** matches.
- [ ] `grep -r "border-radius: 2px\|border-radius: 3px\|border-radius: 5px\|border-radius: 9px\|border-radius: 12px\|border-radius: 16px" ui/` returns **zero** matches (except inside web-view CSS strings if untokenized).
- [ ] `grep -r "SPACE_10\|SPACE_12\|SPACE_16\|S\[\"10\"\]\|SP\[\"10\"\]" ui/` returns **zero** matches.
- [ ] `grep -r "COLOR_BORDER_MEDIUM" ui/theme_engine.py | grep -v "input\|focus\|drop-down\|QComboBox\|QLineEdit\|QPlainTextEdit"` returns **zero** matches on card roles.
- [ ] `BTN_HEIGHT` equals the rendered `min-height` of `QPushButton` in the global QSS (both 38px).
- [ ] All analytics tabs render correctly with the global tab and scrollbar styles (no local overrides).
- [ ] Route planner sidebar scrollbar matches the global 8px theme.
- [ ] `ui/views/api_dashboard_view.py` no longer contains a class named `_ActionButton`.
