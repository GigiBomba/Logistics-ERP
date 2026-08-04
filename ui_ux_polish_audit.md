# UX Polish Audit — Operion ERP

**Auditor**: AI Design Review  
**Date**: 2026-07-22  
**Scope**: 10 core view files (read-only code review, no runtime testing)  
**Mandate**: Identify highest-ROI improvements requiring *minimum* engineering effort. No full redesigns.

---

## Overview

Operion ERP has a **solid structural foundation** — consistent dark theme, design tokens, reusable components (`Btn`, `Card`, `StyledTableWidget`), and proper async data loading. The codebase shows mature engineering.

**However**, several recurring UX friction points add up to a "polished backend, rough frontend" feeling:

1. **Randomized dashboard content** destroys user muscle memory.
2. **Over-dense filter bars** (especially Maintenance) cram 8+ controls into one row.
3. **Missing empty-state guidance** leaves users guessing what to do next.
4. **Button hierarchy is often inverted** — "Refresh" screams for attention while "Create" hides.
5. **No click-through on dashboard lists** — the Overview dashboard is a dead-end, not a launchpad.
6. **Redundant search fields** in Fleet (general + plate) create confusion.
7. **Hardcoded non-translated strings** ("PERIOADA") break i18n consistency.
8. **Conditional tabs** (Fleet expenses, Client Revenue) appear/disappear based on data, violating stability heuristics.

**Overall readiness**: The app is *functionally* ready for launch, but *perceptually* it feels like a powerful admin panel rather than a guided workflow tool. A focused 1-week polish sprint on the issues below would elevate it to customer-facing quality.

---

## By View

### 1. Overview Dashboard (`ui/views/overview_view.py`)
**Score**: 6/10

**Issues**:
1. **Random KPIs destroy predictability** — `_pick_random_content()` (line 175) selects 3 of 19 KPIs and 1 of 20 charts at random. A returning user sees different metrics every session. No way to pin favorites.
2. **Chart title is vague** — "ANALYTICS HIGHLIGHT — PAST 30 DAYS" (line 281) doesn't name the actual metric. Users can't tell if they're looking at revenue or fuel efficiency without reading the small subtitle.
3. **Alert strip "+ N more" is dead text** — line 655-658 renders `+ 2 more` as a blue QLabel with `PointingHandCursor`, but **no click handler is connected**. Users click and nothing happens. Broken promise.
4. **Active trips are not clickable** — `_trip_row()` (line 568) builds rows with plate, route, status badge, but no `mouseReleaseEvent` or click handler. The dashboard is a dead-end; users must navigate elsewhere to act on a trip.
5. **Recent activity lacks status context** — shows date/plate/client/profit (line 733) but no status badge. A user can't tell if a €3,400 profit trip is "Delivered" or "Invoiced" at a glance.
6. **Top trucks ranking colors are hard-coded hexes** — lines 691-693 use `#F59E0B` (gold), `#9CA3AF` (silver), `#B45309` (bronze). These don't adapt to the design token system and may clash with custom themes.

**Quick wins** (can be done in <1 hour):
- Connect the `more` label click to emit a navigation signal to the Dispatch Board filtered by alerts (line 658).
- Make `_trip_row` clickable: add `mouseReleaseEvent` that emits a signal to open the trip in Dispatch/History (line 568).
- Replace `_pick_random_content` with deterministic defaults (e.g., always show Revenue, Active Trucks, Top Driver) so the dashboard feels stable (line 175).
- Add `status_key` to recent activity rows and render a mini `StatusBadge` (line 733).

---

### 2. Analytics (`ui/views/analytics/__init__.py`)
**Score**: 7/10

**Issues**:
1. **Hardcoded Romanian label** — line 189 sets `label = Label(strip, "PERIOADA", role="muted")`. This is not translated and breaks the English UI. Should use `t("analytics.period_label")`.
2. **Refresh button has no tooltip on all platforms** — line 241-242 sets `setToolTip`, but the button is a unicode glyph `↻` inside a 32px fixed-width button. On touchscreens or when tooltips are disabled, the glyph is the *only* affordance. Many users won't recognize it.
3. **Tab switch loading overlay feels heavy** — line 295-302 shows a full-window `LoadingOverlay` with a progress bar every time a new analytics tab is clicked. For a local SQLite app, this creates perceived slowness. A skeleton shimmer or inline spinner would feel faster.
4. **Period buttons lack keyboard accessibility** — the pill group (lines 208-237) uses `QPushButton` with custom stylesheets but no `setAutoDefault` or focus ring styling. Keyboard users can't tell which period is focused.

**Quick wins**:
- Replace `"PERIOADA"` with a translation key (line 189).
- Add a text label next to the refresh glyph, or replace with `Btn(..., icon="refresh", variant="ghost")` (line 241).
- Reduce `LoadingOverlay` to a 200ms inline skeleton inside the tab pane instead of a full modal overlay (line 295).

---

### 3. Dispatch Board (`ui/views/dispatch_board/dispatch_board.py`)
**Score**: 7/10

**Issues**:
1. **Primary action is Refresh, not Create** — lines 230-247 place Export CSV, Export PDF as ghost buttons, then Refresh as `variant="primary"`. The most common dispatch action is *creating or assigning a trip*, not refreshing the view. Refresh should be ghost/secondary; a "+ New Trip" button should be primary.
2. **Bulk toolbar has no entrance animation** — line 306 uses `.hide()` / `.show()`. A 150ms slide-down or fade would make the bulk mode feel intentional rather than glitchy.
3. **Cancelled column arbitrarily capped at 3 cards** — line 615 `CANCELLED_MAX = 3` with no UI to expand. Users searching for a cancelled trip from last week must use the search bar instead of scrolling. A "Show all" link or higher default (10) is safer.
4. **Empty state lacks a CTA** — line 351-357 shows "No trips found" with subtitle "Try adjusting your search", but no button to *clear filters* or *create a trip*. Add a "Clear filters" ghost button and a "Create trip" primary button inside the `EmptyState`.
5. **Export buttons are always visible** — even when the board is empty (line 230-240), users can click Export CSV/PDF and get empty files. Disable or hide them when `_board_stack.currentIndex() == 1` (empty state).

**Quick wins**:
- Swap Refresh to `variant="ghost"` and add a `Btn(..., "+ New Trip", variant="primary")` in the header (line 242).
- Add `EmptyState` CTA buttons for clear-filters and create-trip (line 351).
- Disable export buttons when no trips are loaded (line 230).
- Increase `CANCELLED_MAX` to 10 or add a "Show older" link (line 617).

---

### 4. Fleet Tab (`ui/views/fleet_tab/fleet_tab.py`)
**Score**: 6/10

**Issues**:
1. **Two redundant search fields** — lines 308-348 build both a general text search (`_e_search`) and a dedicated plate search (`_e_plate_search` + Find button). The general search already covers plate numbers (line 733-744 filters all columns). The plate field adds clutter and cognitive load. **Remove the plate row**; general search is sufficient.
2. **Quick-add form permanently consumes right-panel space** — lines 434-469 show plate/model/rate inputs always. For fleets >20 trucks, the chart and alerts are more valuable than this form. The form should collapse behind a "+ Quick Add" button or move to a dialog.
3. **Chart area information density is poor** — line 415-430 dedicates a minimum 200px tall panel to a single pie chart of truck statuses. A pie chart with 2 slices (Active/Inactive) is not worth the space. Replace with a compact horizontal bar or move it into a KPI card.
4. **Edit/Delete buttons don't guard against no-selection** — line 376-396. `_edit_truck_selected` and `_delete_truck` call `_get_selected_truck_id()` which shows a `QMessageBox.information` popup (line 782-785). A gentler approach: disable Edit/Delete when no row is selected, rather than throwing a modal dialog.
5. **Truck detail dialog wastes Maintenance tab space** — line 1005-1020 creates a Maintenance tab containing *only* a single centered button "Open Maintenance Manager" and a muted description. That's an entire tab for one button. Inline the maintenance KPIs here, or remove the tab and link directly from the left panel.
6. **Expenses tab is conditional** — line 1023 `if hasattr(self.service, 'get_expenses')`. Tabs that appear/disappear based on backend capabilities confuse users. If expenses are sometimes unavailable, show the tab disabled with a tooltip rather than hiding it.

**Quick wins**:
- Remove plate search row; rely on general filter (delete lines 331-346).
- Collapse quick-add form behind a `Btn(..., "+ Quick Add", variant="ghost")` toggle (line 434).
- Disable Edit/Delete buttons when table selection is empty, instead of popup (line 376).
- Replace pie chart with a compact 3-segment progress bar inside the KPI strip (line 415).

---

5. **Client Workspace (`ui/views/client_workspace/client_workspace.py`)
**Score**: 6/10

**Issues**:
1. **AutoMail tab is buried inside Client workspace** — lines 195-219. AutoMail is a cross-cutting feature, not a sub-feature of client management. Users looking for email automation won't think to open the Clients module. **Consider promoting AutoMail to a top-level module** or at least adding a navigation shortcut from the main sidebar.
2. **Client table has fixed max height** — line 265 `setMaximumHeight(500)`. On 1440p+ monitors, the table leaves massive whitespace below while the detail tabs are cramped. Use `setMinimumHeight` instead, or let the splitter distribute space.
3. **No empty-state in detail tabs** — line 318 disables `_client_tabs` when no client is selected, but shows nothing — just grayed-out tabs. A "Select a client to view details" centered message would guide first-time users.
4. **New Client button is far from the table** — line 244 puts "+ New" in the top header bar, while Edit/Deactivate sit below the table (lines 273-286). The primary CRUD action is spatially separated from the data it affects. Move "+ New Client" adjacent to the table action bar.
5. **Client form dialog is a wall of 12 fields** — lines 564-577 present all fields with equal visual weight. Required fields (`name`) and financial fields (`credit_limit_eur`, `payment_terms_days`) should be grouped into sections: "Basic Info", "Billing", "Notes".
6. **Revenue tab is empty until clicked, with no loading state** — line 314 comments `# QtClientRevenueChart` but the tab widget is just an empty `QWidget`. When switching to Revenue, there's a perceptible blank gap before the chart renders. Add a skeleton placeholder.

**Quick wins**:
- Add an empty-state widget inside `_client_tabs` when disabled: icon + "Select a client from the table above" (line 318).
- Move "+ New Client" button into the action bar below the table (line 244 → line 269).
- Group form fields into 3 `QGroupBox` / card sections in `_QtClientFormDialog` (line 611).
- Add `setMaximumHeight` removal or replace with flexible splitter (line 265).

---

### 6. Trip History (`ui/views/history_view.py`)
**Score**: 7/10

**Issues**:
1. **"Load More" button is an anti-pattern here** — line 203/324 doubles `_limit` and refreshes. For a 200-row default, clicking "Load More" jumps to 400, then 800. Users lose scroll position and the table repopulates from scratch. **Infinite scroll** or **paginated page numbers** are standard. At minimum, preserve vertical scroll position across refresh.
2. **"View Route" loses user context** — line 387 switches module to `route_planner` but doesn't pass `trip_id`. The user arrives at an empty route planner and must re-select the trip. Pass navigation data via `handle_nav_data` pattern used elsewhere.
3. **No bulk actions** — every button (Invoice, Export, Email, Delete) operates on a single selected row. For a history view, users often need to invoice 5 trips at once or delete a batch. A checkbox column + bulk toolbar (like Dispatch Board) would dramatically improve efficiency.
4. **Status is text-only color coding** — line 255-267 applies `setForeground(QColor)` to status text. Color-blind users can't distinguish "Planned" from "Delivered". Replace with the `StatusBadge` component used in the Overview dashboard.
5. **Action bar has 7 buttons in one row** — lines 194-219. On smaller screens this wraps awkwardly. Group into: `[Invoice] [Export ▼] [Actions ▼] [Delete]`. A split button or menu for exports would save space.

**Quick wins**:
- Pass `trip_id` to route planner via controller nav data (line 387).
- Replace status text coloring with `StatusBadge` widget (line 255).
- Collapse PDF, Excel, Email into an "Export" split-button or menu (line 198-200).
- Add `self.table.verticalScrollBar().value()` preservation in `refresh()` (line 223).

---

### 7. Route Planner (`ui/views/route_planner_view.py`)
**Score**: 7/10

**Issues**:
1. **Calculate button disabled with no explanation** — lines 1098-1108 disable `calc_btn` until start and destination are filled, but there's no inline helper text. A muted label below the button saying "Enter origin and destination to calculate" would remove guesswork.
2. **No primary action after route is calculated** — lines 1273-1293 show dispatch buttons ("Send to Calculator", "Google Maps") but nothing to *create a trip* from this route. The natural workflow is: plan route → save as trip. A "Create Trip" primary button should appear prominently in the result panel.
3. **Result pills use inconsistent number formatting** — line 1135-1139 calls `fmt_currency`, `fmt_distance`, `format_duration`, but `fmt_currency(rate) + "/km"` concatenates a formatted string with raw text. If `fmt_currency` adds a € prefix, the result is "€ 1.20/km" which is acceptable, but inconsistent with the fuel cost pill that shows "€ 45".
4. **Click-to-add-stop has no map cursor feedback** — lines 1045-1057 changes the Leaflet container cursor to `crosshair`, but there's no persistent UI indicator (e.g., a toast or banner) reminding the user they are in "add stop" mode. A temporary banner: "Click map to add a stop" would prevent accidental clicks.
5. **No saved routes / recent routes** — every session starts empty. A "Recent Routes" section above the waypoints (or a dropdown) would save repetitive data entry for recurring lanes.

**Quick wins**:
- Add a muted helper label below the Calculate button when disabled (line 1098).
- Add a "Create Trip" primary button in `_show_dispatch_buttons` (line 1273).
- Add a temporary toast/banner when `_click_to_add_enabled` is true (line 1045).

---

### 8. Generators (`ui/views/generators_view.py`)
**Score**: 7/10

**Issues**:
1. **Trip selector shows all trips with no grouping** — line 565-572 formats trips as `"#{id} {truck} — {client} ({date})"`. For 200+ trips, the dropdown is an unscrollable wall of text. Group by month or status, or add a type-ahead filter.
2. **CMR copy rows are always visible even when empty** — lines 417-470 show 4 copy rows (Sender, Consignee, Carrier, Administrative) with "not generated" status from startup. This creates visual noise before the user has done anything. **Hide the copies panel until the first generation**, or collapse it behind an accordion.
3. **Generate Single vs Generate All hierarchy is correct but labels are verbose** — lines 375-393. The buttons include emoji prefixes `📤` and `🚀` which feel informal for an ERP. Remove emojis for a more professional tone.
4. **No "last generated" timestamp** — once a CMR is generated, the status label says "generated" but not *when*. A timestamp ("2 min ago") helps users confirm they're looking at the latest version.
5. **Receipt and Proforma tabs are lazy-built but have no loading state** — lines 515-518/530-533. If the editor takes >100ms to construct, the tab appears blank. Add a `LoadingOverlay` or skeleton for the first build.

**Quick wins**:
- Remove emoji prefixes from CMR action buttons (line 375-388).
- Hide copies panel until `_cmr_last_paths` is non-empty, or add "Show copies" toggle (line 417).
- Add `QDateTime` timestamp to copy status labels (line 945).

---

### 9. Fleet Tracking (`ui/views/fleet_tracking_view.py`)
**Score**: 7/10

**Issues**:
1. **Vehicle list has no search/filter** — line 225-295. For fleets >15 vehicles, users must scroll the entire list. A `QLineEdit` filter at the top of the vehicle panel would allow instant narrowing by plate or name.
2. **"Fleet Detail" button loses truck context** — line 452-463. The button navigates to the generic Fleet module, not the specific truck's detail page. It should pass `truck_id` via `on_navigate` so the Fleet tab can auto-select the vehicle.
3. **Last updated label shows time only** — line 556 formats as `%H:%M:%S`. If the app runs overnight, "14:32:15" is ambiguous. Use `"14:32"` (shorter) or `"Today, 14:32"` for clarity.
4. **Refresh button is cryptic** — line 248-253 uses unicode `↻` with no text label. Same issue as Analytics. Add `"Refresh"` text or a more explicit icon.
5. **Detail panel fixed height wastes space on small screens** — line 289 `setFixedHeight(200)`. If the window is 768px tall, the vehicle list gets ~300px and the detail panel gets 200px, leaving little room for scrolling. Make the detail panel minimum 120px with a collapsible chevron.

**Quick wins**:
- Add a filter `QLineEdit` at the top of `_build_vehicle_panel` (line 225).
- Pass `truck_id` through `on_navigate` to Fleet tab (line 455).
- Change `_updated_lbl` format to `"Today, %H:%M"` (line 556).
- Replace refresh glyph with `Btn(..., "Refresh", variant="ghost", size="sm")` (line 248).

---

### 10. Maintenance Control Panel (`ui/views/maintenance_control_panel.py`)
**Score**: 5/10

**Issues**:
1. **Filter bar is critically overcrowded** — lines 262-324 place **8 controls** in a single horizontal `QHBoxLayout`:
   - 3 severity checkboxes
   - Type dropdown
   - Truck text field
   - Trip text field
   - "Show resolved" checkbox
   - Summary label
   On screens <1400px wide, this wraps into an unreadable mess. **Break into two rows**: Row 1 = Severity + Type + Show resolved. Row 2 = Truck + Trip + Reset button.
2. **No "Reset Filters" button** — despite 6 filter controls, there's no one-click way to return to defaults. Users must uncheck 3 boxes and clear 2 text fields manually. Add a `Btn(..., "Reset", variant="ghost")`.
3. **Fuel price panel feels out of place** — line 347-349 adds `QtFuelPricePanel` at the bottom of a *maintenance* view. Fuel prices are an operations/finance concern, not a maintenance concern. This creates cognitive dissonance. **Move fuel prices to Overview or a dedicated Operations panel**.
4. **Tacho table has no empty-state CTA** — lines 254-259 show "No tachograph data" with subtitle, but no button to open the Tacho Import view. Add an "Import Tachograph" primary button inside the `EmptyState`.
5. **KPI shimmer animation may cause accessibility issues** — lines 353-370 rapidly toggle label colors every 800ms. This can trigger vestibular disorders. Reduce to a slow pulse (1.5s) or replace with a static skeleton.
6. **Alert list has no bulk resolve** — users can view alerts but must resolve them one-by-one elsewhere. A right-click menu or bulk checkbox column in the `QListView` would streamline maintenance workflows.

**Quick wins**:
- Split filter bar into two rows (lines 262-324).
- Add a Reset Filters button (new, ~5 lines).
- Remove or relocate `QtFuelPricePanel` (line 347).
- Add "Import Tachograph" CTA to tacho empty state (line 254).
- Slow shimmer timer to 1500ms (line 96).

---

## Cross-Cutting Issues

### A. Button Hierarchy Inversion
Across multiple views, **Refresh** is styled as `variant="primary"` while **Create/New** is secondary or missing:
- `dispatch_board.py:245` — Refresh primary
- `fleet_tab.py` — no "New" in header (only below table)
- `analytics/__init__.py:241` — Refresh is just a glyph, but still prominent

**Fix**: Adopt a strict rule: **Primary = create/assign/save. Secondary = export/filter. Ghost = refresh/cancel.** Audit every view and swap variants accordingly.

### B. i18n Leaks
Hardcoded non-translated strings appear in:
- `analytics/__init__.py:189` — `"PERIOADA"`
- `fleet_tab.py` — placeholder text in quick-add form is not translated (`text="0"` on rate field, line 458)
- `route_planner_view.py` — some `default=` strings are English fallbacks, but not all

**Fix**: Sweep for raw string literals in view constructors. Any user-visible text must go through `t()`.

### C. Missing Click-Through on Dashboard Lists
The Overview dashboard (`overview_view.py`) builds rich lists (Active Trips, Top Trucks, Recent Activity, Alerts) but none are interactive. This violates the "launchpad" mental model of a dashboard.

**Fix**: Emit a unified `navigate_to(module, data)` signal from all list rows. Connect in `MainWindow` to switch modules with context.

### D. Inconsistent Empty-State Patterns
Some views use the `EmptyState` component (`overview_view.py`, `fleet_tab.py`), others use raw `QLabel` with `fontRole="muted"` (`maintenance_control_panel.py`, `fleet_tracking.py`). The visual inconsistency makes the app feel patched together.

**Fix**: Mandate `EmptyState` component for all empty lists/tables. It provides icon + title + subtitle + optional CTA button consistently.

### E. Conditional Tab Visibility
`fleet_tab.py:1023` and `client_workspace.py:310` hide tabs based on backend capabilities. This makes the UI unpredictable — a user sees 4 tabs on one install and 3 on another, with no explanation.

**Fix**: Always show tabs. Disable them with a tooltip explaining why (e.g., "Enable expense tracking in Settings").

---

## Priority Matrix

| Issue | Effort | Impact | View |
|-------|--------|--------|------|
| Randomized dashboard KPIs destroy predictability | Low | High | Overview |
| Filter bar overcrowded (8 controls in 1 row) | Low | High | Maintenance |
| Alert "+ N more" is clickable but dead | Low | High | Overview |
| Missing "Create Trip" primary action after route calc | Low | High | Route Planner |
| Two redundant search fields in Fleet | Low | Medium | Fleet |
| Hardcoded "PERIOADA" breaks i18n | Low | Medium | Analytics |
| No click-through on dashboard lists | Low | High | Overview |
| Bulk toolbar has no entrance animation | Low | Low | Dispatch |
| Fuel panel out of place in Maintenance | Low | Medium | Maintenance |
| Conditional tabs confuse users | Low | Medium | Fleet, Client |
| "Load More" repaints table and loses scroll | Medium | Medium | History |
| No bulk actions in History | Medium | High | History |
| Status text-only color coding (no badges) | Low | Medium | History |
| Quick-add form permanently consumes space | Low | Medium | Fleet |
| Client form is a wall of 12 fields | Medium | Medium | Client |
| Revenue tab has no skeleton/placeholder | Low | Low | Client |
| CMR copy rows visible before generation | Low | Low | Generators |
| Refresh button hierarchy inverted | Low | Medium | Dispatch, Analytics |
| Vehicle list has no search | Low | Medium | Tracking |
| Tacho empty state lacks import CTA | Low | Low | Maintenance |

---

## Recommendations Summary

**Top 10 improvements ranked by impact/effort ratio:**

1. **Stabilize Overview dashboard content** — stop randomizing KPIs/charts (`overview_view.py:175`). Always show the 3 most important metrics. *(Effort: 5 min)*
2. **Fix dead "+ N more" alert link** — connect click handler or remove cursor (`overview_view.py:658`). *(Effort: 10 min)*
3. **Split Maintenance filter bar into two rows** — wrap severity/type/resolved on row 1, truck/trip/reset on row 2 (`maintenance_control_panel.py:262`). *(Effort: 15 min)*
4. **Add "Create Trip" primary button to Route Planner results** — the natural workflow end-point (`route_planner_view.py:1273`). *(Effort: 20 min)*
5. **Make Overview list rows clickable** — emit navigation signals from trips, trucks, alerts, activity (`overview_view.py:568`). *(Effort: 30 min)*
6. **Remove redundant plate search from Fleet** — general search already covers it (`fleet_tab.py:331`). *(Effort: 5 min)*
7. **Add empty-state guidance to Client detail tabs** — show "Select a client" message instead of grayed-out tabs (`client_workspace.py:318`). *(Effort: 15 min)*
8. **Swap Refresh to ghost, promote Create to primary in Dispatch header** — correct button hierarchy (`dispatch_board.py:245`). *(Effort: 5 min)*
9. **Replace History status text-colors with StatusBadge** — accessibility + scannability (`history_view.py:255`). *(Effort: 20 min)*
10. **Add vehicle list filter to Fleet Tracking** — instant search by plate/name (`fleet_tracking_view.py:225`). *(Effort: 20 min)*

---

## Launch Readiness UX Assessment

**Verdict: Cautionary Green — launchable, but not lovable.**

The application is **functionally robust** and **visually cohesive** thanks to the design token system. Users can perform all core logistics workflows: dispatching, fleet management, invoicing, route planning, and maintenance tracking.

**What holds it back from a confident launch:**
- **The dashboard feels like a demo**, not a command center. Randomized widgets and non-clickable lists make it a passive billboard rather than an active launchpad.
- **Maintenance view filter bar is the single worst UX moment** — 8 controls in one row signals "internal tool" energy.
- **History view lacks bulk actions** — power users managing 50+ trips/week will feel the friction immediately.
- **Route planner has no save/create action** — users plan a perfect route, then manually recreate it in a trip form. That's a broken workflow loop.

**What works well and should be protected:**
- Dark theme consistency and component reuse.
- Async loading patterns (WorkerPool, shimmer states).
- Event-bus driven live updates in Dispatch Board.
- Truck availability slots in Route Planner dropdown.
- Empty-state component usage (where present).

**Recommended pre-launch sprint (3-5 days):**
Implement the **Top 10 recommendations** above. They are almost entirely layout, signal wiring, and variant swaps — no schema changes, no API redesigns. The ROI is transforming the app from "competent internal tool" to "polished customer-facing ERP."
