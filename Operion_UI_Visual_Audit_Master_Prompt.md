# MASTER PROMPT — Operion Desktop UI Visual Audit & Remediation

You are performing a **visual quality audit and fix pass** on the Operion desktop ERP (PySide6/Qt). This is not a feature-development task and not a full production-readiness audit — it is narrowly scoped to **how the UI looks and feels**: alignment, symmetry, spacing consistency, visual hierarchy, and adherence to the existing design system.

You are not allowed to self-report success. Every claim you make must be backed by a pasted artifact (screenshot, computed geometry, or code diff) in this same session. "Looks good now" with no evidence is treated as a failed pass.

---

## 0. Ground Truth — Design System

The single source of truth for anything visual is `ui/design_tokens.py`. Before touching any file, load it and treat every constant in it as law:

- **Surfaces**: app bg `#0C0C0E`, card/panel `#141416`, inputs/rows `#1C1C1F`, hover `#222226`, selected `#27272C`, stat cards `#1A1A24`
- **Borders**: subtle `#2A2A30`, medium `#38383F`, strong `#505058`
- **Text**: primary `#F0F0F3`, secondary `#8E8EA0`, tertiary `#5A5A6E`
- **Accent**: indigo `#6366F1`, hover `#5254CC`, tinted bg `#1E1F3D`
- **Semantic**: success `#10B981`, warning `#F59E0B`, error `#EF4444`, info `#3B82F6`, neutral `#6B7280`
- **Typography scale**: 10/11/12/13/16/22/26/32px, weights 400/500/600/700, Inter (UI) / Consolas (mono values) / IBM Plex Sans (loading overlay)
- **Spacing scale**: 4/8/12/16/20/24/32/40/48/64 — every margin, padding, and gap must map to one of these values. Any hardcoded pixel value not on this scale is a bug.
- **Radii**: 4/6/8/12/pill
- **Elevation**: border-brightness only (no drop shadows — this is intentional, do not "fix" it by adding shadows)
- **Component contracts**: `Card`, `UniversalCard`, `CompactKPICard` (88px), `KPICard`, `StatusBadge/Chip`, `FilterChip`, button sizes sm 28 / md 32 / lg 38px

**A "visual bug" in this audit is any deviation from this system** — not a matter of your taste. If something is ugly but token-compliant, flag it as a lower-severity design suggestion, separate from actual bugs. Do not redesign components wholesale; fix deviations and inconsistencies.

---

## 1. Scope

Full sweep across every page and surface in the app shell:

**Shell**: Sidebar (collapsed 48px / expanded 200px), TopBar (44px), page cross-fade transitions

**Pages**: Overview, Analytics (all 6 tabs: Financial/Fleet/Route/Client/Driver/Document), Route Planner, Calculator, Dispatch Board (Board/Alerts/Timeline), Fleet Tracking, Freight Exchange (search + load detail), Fleet, Drivers, Clients (Manager + AutoMail + workspace tabs), Documents, Maintenance Control, Maintenance Analytics, Tachograph, Invoices Generators (Invoice/CMR/Receipt/Proforma), History, Route History, CoPilot, Migration Center, Team, Settings

**Embedded surfaces**: API Dashboard, Admin Panel, Automation view, Bulk Payments, Package preview modal, Email composer

For each surface, check both the **empty state** and a **populated state** (real or representative data) — many alignment bugs only appear once table rows wrap, badges get long text, or cards have varying content lengths.

---

## 2. What to look for

Work through this checklist per page. Don't just eyeball it — where the framework allows, pull actual computed geometry (widget `.geometry()`, layout margins, `sizeHint()`) rather than guessing from a screenshot alone.

### Alignment & symmetry
- Header bars: is the 72px height and title/subtitle/action-button baseline actually consistent across pages, or does it drift by a few px per page?
- KPI strips: are stat cards equal width/height within a strip? Equal gaps between them?
- Table columns: consistent header height, consistent cell vertical padding, text baseline alignment between icon+label columns
- Form dialogs: label column widths consistent within a form; input fields left-edge aligned; helper/error text doesn't shift layout when it appears
- Icon + label pairs (sidebar items, buttons, badges): vertical centering, consistent icon-to-text gap
- Splitter-based layouts (Route History 60/40, Fleet Tracking 72/28, Documents 20/50/30, Automail 20/55/25): do panels actually respect these ratios at default window size, and do they degrade gracefully at the 1024×600 minimum?

### Spacing consistency
- Any margin/padding/gap value not on the 4/8/12/16/20/24/32/40/48/64 scale
- Inconsistent spacing between structurally identical elements (e.g. gap between KPI cards differs page to page)
- Cards with inconsistent internal padding vs. other cards of the same type

### Color & token compliance
- Any hardcoded hex color that duplicates or nearly-duplicates a token instead of referencing it (grep for raw hex strings outside `design_tokens.py`)
- Status/badge colors that don't match the documented mapping (delivered=green, planned=indigo, in_progress/in_transit=amber, cancelled=gray, overdue=red, maintenance=blue, invoiced=blue, paid=green)
- Insufficient contrast between text tiers and their background (primary/secondary/tertiary text on the surfaces they actually appear on)

### Typography
- Wrong size/weight for a given role (e.g. a KPI value rendering at body size, a table cell at nav size)
- Truncation without ellipsis, or ellipsis truncation on fields that shouldn't truncate (e.g. currency values)
- Mono font (Consolas) missing on numeric/KPI values where the system calls for it

### Component-level bugs
- Buttons: wrong height for their size variant (sm/md/lg), icon-only ghost buttons with inconsistent hit-target size
- Badges/chips: inconsistent pill radius or padding, text not vertically centered inside the pill
- Tables: sort indicator misalignment, density toggle not actually changing row height, grayed-inactive-row style bleeding into hover state
- Cards (`UniversalCard`, `CompactKPICard`, `KPICard`): icon box not square, title/value/trend not baseline-aligned
- Loading/skeleton states: skeleton shapes that don't match the real content's final dimensions (causes layout jump on load)
- Empty states: icon/title/subtitle not centered as a group within their container

### Responsive/resize behavior
- Sidebar expand/collapse: content reflow glitches, label truncation before the 200ms animation completes
- Window resize toward the 1024×600 minimum: overlapping elements, cut-off content, splitters that don't respect minimum panel widths
- Dialogs: min-width (450–600px) actually enforced; content doesn't overflow the dialog frame

### Motion
- Fade (150ms), slide/collapse (200ms OutCubic), hover (100ms), press (50ms) durations actually match spec, not left as Qt defaults
- Any animation that visibly stutters or skips a frame on page switch

---

## 3. Method — verification is mandatory

For every page you audit:

1. **Render it** (populated state where possible) and capture a screenshot or the exact widget geometry tree.
2. **Log every deviation found** as a row in the findings table (format below) — cite the exact file and line where the offending style/layout is set.
3. **Fix only what's logged.** Don't refactor unrelated code, don't change component APIs, don't touch business logic or data-fetching code.
4. **Re-render after the fix** and paste the "after" evidence next to the "before" in the same finding.
5. If a fix is not achievable without touching shared component code, say so explicitly and note the blast radius (which other pages use that component).

No finding may be marked "Fixed" without a pasted before/after comparison. No page may be marked "Clean" without pasted evidence that it was actually rendered and inspected — not inferred from reading the source.

---

## 4. Output format

### 4.1 Executive verdict (top of report)
One paragraph: overall visual quality state, worst-offending pages, and whether the app is presentable for the September 2026 launch as-is.

### 4.2 Findings table (per page)

| # | Page/Surface | Element | Issue | Severity | File:Line | Status |
|---|---|---|---|---|---|---|

Severity:
- **Critical** — broken/overlapping/unreadable, blocks usability
- **High** — clearly inconsistent with the design system, visible on first glance
- **Medium** — noticeable on close inspection, not embarrassing
- **Low** — polish-level, cosmetic

### 4.3 Evidence appendix
Before/after screenshots or geometry dumps for every "Fixed" row, grouped by page.

### 4.4 Prioritized remediation roadmap
Ordered list of remaining unfixed items (if any), grouped by severity, with estimated effort and which shared components they'd touch.

### 4.5 Design-system drift log
Separate list of any place where you found the actual implementation and `design_tokens.py` disagreeing on what "the system" is — these need a human decision (update the token or fix the implementation), not a unilateral fix.

---

## 5. Hard constraints

- Do not modify `design_tokens.py` values themselves — if you believe a token is wrong, log it in the drift log, don't change it unilaterally.
- Do not add drop shadows, gradients, or any visual language not already present in the system (no scope creep into a "redesign").
- Do not touch business logic, API calls, or data models — visual/layout code only.
- Do not mark anything complete without pasted before/after evidence in this session.
- If a page cannot be rendered in your environment (e.g. requires live DB/API data), say so explicitly rather than guessing at its appearance from source code alone.
