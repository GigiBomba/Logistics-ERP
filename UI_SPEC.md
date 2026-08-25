# Operion Desktop ERP — UI Specification Dump

Current-state spec of the Qt desktop UI, derived from source. Covers look & feel, shell, and every page.

---

## 1. Overview

| | |
|---|---|
| **App** | Operion — logistics/freight ERP (transport, dispatch, fleet, invoicing, CMR, analytics) |
| **Stack** | PySide6 (Qt) desktop app. Plotly for charts (rendered to SVG → QPixmap), Folium/Leaflet in QWebEngineView for maps, qtawesome (Font Awesome 5 solid) icons, no emoji in nav |
| **Window** | `QMainWindow`, default 1400×900, min 1024×600. Title from app config |
| **Theme** | Dark-first design system (Linear / Stripe / JetBrains style). Near-black backgrounds, indigo accent `#6366F1`. Theme toggle (dark/light) exists in Settings and hot-reloads |
| **Fonts** | Inter (UI), Consolas (monospace values/KPIs), IBM Plex Sans (loading overlay) |
| **Language** | Romanian-first i18n (labels like "PERIOADA", "Planificat", "În curs", "Livrat"), full i18n system with language switch in Settings |
| **Modes** | LOCAL (local SQLite DB), REMOTE (API client) — decided at startup. All modules are remote-capable; DB-only features show a graceful "requires local database access" placeholder in remote mode |
| **Styling** | Inline stylesheet strings built from `ui/design_tokens.py` constants (no single global QSS file); shared widgets styled via property roles consumed by a theme engine |

---

## 2. Design System (tokens & components)

### Colors
- **Surfaces**: app bg `#0C0C0E`, card/panel `#141416`, inputs/dropdowns/table rows `#1C1C1F`, hover `#222226`, selected `#27272C`, stat cards `#1A1A24`
- **Borders**: subtle `#2A2A30` (default), medium `#38383F` (inputs/focus), strong `#505058`
- **Text**: primary `#F0F0F3`, secondary `#8E8EA0` (labels/captions), tertiary `#5A5A6E` (disabled/placeholders)
- **Accent**: indigo `#6366F1` (primary actions), hover `#5254CC`, tinted bg `#1E1F3D`
- **Semantic**: success emerald `#10B981`, warning amber `#F59E0B`, error red `#EF4444`, info blue `#3B82F6`, neutral gray `#6B7280` — each with subtle bg + light text variants
- **Chart palette**: indigo, emerald, amber, blue, pink on grid `#1E1E24`
- **Status mapping** (badges): delivered=green, planned=indigo, in_progress/in_transit=amber, cancelled=gray, overdue=red, maintenance=blue, loading=muted, invoiced=blue, paid=green

### Typography
- Sizes: 10 (timestamps) → 11 (table cells/labels) → 12 (body) → 13 (nav) → 16 (card values) → 22 (KPIs) → 26 (stat cards) → 32 (hero dashboard numbers). Weights 400/500/600/700

### Spacing / radius / motion
- Spacing scale 4/8/12/16/20/24/32/40/48/64; radii 4/6/8/12/pill
- Motion: fade 150ms, slide/collapse 200ms (OutCubic), hover 100ms, press 50ms, toast fade 250ms, spinner 800ms
- Elevation = border brightness shifts (no real shadows; Qt shadow perf is poor): flat `#2A2A30`, raised `#505058`, overlay `#38383F`

### Core components
- **Buttons** (`variant`): primary (accent bg, white text), secondary (bordered), danger (red), ghost (icon-only), success (green). Sizes sm 28 / md 32 / lg 38 px. Icons via qtawesome, tinted per variant
- **Cards**: `Card` (QFrame + padding toggle), `UniversalCard` (rounded icon box + title + primary + secondary info + ghost action; hover brightens border), `CompactKPICard` (88px, icon + label/value + trend), `KPICard` (mono value, label above)
- **Inputs**: `StyledLineEdit/TextEdit/ComboBox` — dark themed; `SearchInput` with leading magnifier + clear button; `DatePicker` = read-only field + calendar popup (frameless, dark, screen-clamped); `DebouncedLineEdit` (300ms debounce, used for all searches)
- **Badges/chips**: `StatusBadge`/`StatusChip` pill with per-status colors; `FilterChip` pill toggles; tag chips (subtle accent)
- **Toggles**: animated sliding switch
- **Toasts**: frameless, top-right anchored, auto-dismiss 2.5s, fade 250ms; `Toast.show_success/error` with check-circle / times-circle icons
- **Loading**: full-window `LoadingOverlay` (dark translucent + spinning half-circle + "Loading…" + optional progress, 20s safety timeout); chart overlays with pulsing skeleton bars and "n/total charts ready" counter; skeleton placeholder pages (ghost card shapes) for background loads
- **Dialogs**: all modal, fade-in 150ms, dark bg; form dialogs min-width ~450–600px
- **Empty states**: icon + title + subtitle + optional CTA (e.g. "Plan Your First Route")
- **Tables**: `StyledTableWidget` — dark rows, sortable headers with indicators, density toggle (compact/comfortable), context menus, colored status cells, grayed inactive rows
- **Form fields**: label + input + helper text + inline error label; required fields get red asterisk + red border on validation failure; validators for required/email/phone/vat/numeric

---

## 3. App Shell

```
┌──────────────────────────────────────────────────────────────┐
│ Sidebar (48↔200px) │ TopBar 44px (back · fuel dot · alerts   │
│                    │ bell · report issue · sync · clock)     │
│                    ├──────────────────────────────────────────┤
│                    │ QStackedWidget — active page (fade 150ms)│
└──────────────────────────────────────────────────────────────┘
```

### Sidebar
- Collapsed 48px (icon-only) → expanded 200px via animated width (200ms OutCubic); toggle = click the "O" monogram; state persisted
- Groups (collapsed together when filtering): **Overview** (Overview, Analytics) · **Operations** (Route Planner, Calculator, Dispatch Board, Tracking, Freight Exchange) · **Fleet** (Fleet, Drivers, Clients, Documents, Maintenance, Maintenance Control, Tachograph) · **Finance** (Invoices, History, Route History) · **Tools** (CoPilot, Migration Center) · **Administration** (Team — manager/admin only) · **Settings** (bottom-pinned)
- Item: qtawesome icon + label; active item = 4px indigo left bar + bold white label
- Search field (only when expanded) filters items, hides empty groups
- Keyboard shortcuts: Ctrl+1..9 for first nine nav items, Ctrl+S (calculator), Ctrl+H (history), Alt+Left (back)

### TopBar (44px)
- Back button (nav-stack aware, max 20 entries) + Recent dropdown — both hidden until usable
- Fuel price status dot (red/green by data age) · Alert bell with count badge → popup panel (340×420) listing up to 20 alerts: severity chip + title + relative time; click navigates to the relevant page (trip alerts jump to Dispatch Board) · Report Issue button (subject, description, severity, optional screenshot ≤10MB) · Sync status label → Sync Conflict dialog (per-row "Keep local" vs "Take server") · HH:MM clock (mono, 30s)

### Page switching
- Pages pre-created at startup with 200ms stagger (warmup); switching cross-fades 150ms

---

## 4. Global Page Patterns

Most pages share a recipe:
- **Header bar (72px)**: page title + subtitle, right-aligned actions (primary button + secondary/export/refresh)
- **Search/filter strip**: debounced text search + status/filter controls + result count
- **KPI strip**: 3–5 stat cards (mono values, color-coded by sentiment)
- **Table cards**: sortable, density toggle, right-click context menus, double-click opens edit dialog/detail
- **Auto-refresh**: 30s timers on dashboards/boards; 60s on maintenance panel; data loaded on background threads, delivered via signals, skeletons shown while loading
- **Export**: CSV / Excel / PDF buttons on most list views; JSON on editors/route history
- **Undo/redo**: operation engine with command pattern on status changes; toast feedback "Undo: Trip #N status: Old → New"

---

## 5. Pages (sidebar order)

### 5.1 Overview (Dashboard)
Landing health snapshot, refreshed every 30s.
- Header: "Operion ERP" + company name + date + grid toggle
- **KPI strip**: 3 random cards sampled from a pool of 19 metrics (revenue, profit, margin %, active trucks, total km, avg consumption, maintenance alerts, top driver, client count, avg payment delay, top route, top country…); color-coded green/amber/red
- **Featured chart** (left 62%): one of 21 predefined Plotly charts, randomly picked — revenue by client, cost breakdown, trip status pie, quarterly revenue, fleet profitability/utilization, driver leaderboards, route corridors…; title prefixed with category ("FINANCIAL — Client Revenue"), subtitle "Past 30 Days"; staleness-cached 5 min
- **Right column (38%)**: Active Trips panel (≤8 rows: plate + route/client + status badge, non-terminal only) · Alerts strip (≤3 with severity icons, "+N more") · Top Trucks (4 ranked by monthly revenue, gold/silver/bronze rank colors, green mono revenue) · Recent Activity (last 6 trips: date, plate, client, signed colored profit; CTA if empty)
- Skeleton loading on fetch

### 5.2 Analytics (Ctrl+2)
Tabbed analytics hub, shared period filter: **PERIOADA** pill group — 30 days / 90 days / 6 months / 1 year / All + refresh (spinning ↺ during reload). Tabs lazy-loaded on first click, re-render if >5 min stale. Each tab header: grid toggle + export PNG (SVG write, 2× scale).

- **Financial** — "am I making money?": KPIs with 12-month sparklines (Total Revenue, Total Profit ±delta, Avg Margin % vs delta, DSO colored by 30/45-day thresholds) + margin progress bar vs 30% target. Charts: revenue & profit trend (dual line + area), invoice aging stacked bar (Current/31-60/61-90/90+), client & geographic lollipops (revenue/profit by client, country revenue), trip status pie, monthly trip volume area, cost breakdown stacked area (fuel/toll/salary/extra)
- **Fleet** — KPIs: active trucks, total km, avg consumption L/100km, cost/km, on-time delivery %, maintenance alerts. Charts: top-12 truck profit bars (green/red), fuel efficiency bars with 32 L/100km threshold vline (green/amber/red), utilization text rows, maintenance due list, 12-month fuel cost trend
- **Route** — KPIs: unique routes, most frequent route, avg profit/route, top country. Route performance table (Route/Trips/KM/Profit/Profit-KM; profit/km cells colored: >€1.0 green, €0.5–1.0 amber, <€0.5 red), profit/km bars, country treemap (top 10 by profit, margin-colored), route frequency bars
- **Client** — KPIs: total clients, top client, avg payment delay (30-day threshold), new clients. Charts: top-8 revenue + profit bars, payment delay bars with dashed "Target 30d" vline, revenue concentration donut (top-3 vs rest), 12-month growth trend, insight banner when revenue-vs-profit gap >15pts, payment behavior timeline widget
- **Driver** — KPIs: active drivers, avg trips/driver, avg profit/driver, unassigned trips (warning card). Driver comparison table (Profit/KM color-coded), tacho violations bars (top 8), Gantt-style weekly activity grid (rows=drivers, cols=weeks, last 12; colored cell = active week, "N/12" summary)
- **Document** — KPIs: invoices, CMRs, total docs, expiring ≤30 days. Donut (Invoices/CMRs/Other), 12-month upload trend, CMR generation trend, uploads vs expected dual-line, expiring documents list (urgency badges at 7/14/30 days)

### 5.3 Route Planner (Ctrl+3)
Full-screen: left sidebar (~320px, elevated) + interactive Leaflet map (CartoDB dark tiles). Bottom pinned bar: Calculate (primary) · Export Metadata (JSON) · Share.
- **Route card**: waypoint rows (start → stops → destination), "+ Add stop"; **Options card**: truck selector (plate + model + next-available slot), profile dropdown (truck / truck_fast / truck_cheap / truck_safe / truck_short / Recommended), excluded-country chips (with ×), toggles "Show comparison" (alt route in gray) and "Click to add stop" (crosshair, click map → reverse-geocode → insert stop)
- **Results card** (auto-expands): 4 pills — distance, duration, fuel cost €, cost/km €
- Map: green/blue/red stop markers, route polyline (downsampled ≤500 pts), avoided-country polygons (red, 15% opacity), zoom/pan native Leaflet, dark CSS injected
- Actions: **Create Trip** (→ Dispatch Board), **Send to Calculator**, Share dialog (copy link / `.operionroute` file export / open in Google Maps / QR code)

### 5.4 Calculator (Ctrl+4)
Trip profit calculator. Horizontal split: left form cards (55%) / right results card (45%).
- **Identification**: truck dropdown (+refresh), route distance badge, client dropdown (+refresh); **Finance**: offer price, VAT checkbox + %, pre/post-VAT readouts; **Costs**: distance, salary, extra costs; **Planning**: start date (dd/mm/yyyy), duration days, payment term days
- **Results**: Revenue, Total Cost, divider, **Profit Net** (large, green/red), profit %, rate/km, margin %, payment due date, cost breakdown (fuel | toll | salary)
- Enter = calculate; validates km>0, price>0; runs conflict check (prompts if overlap); can save trip to DB

### 5.5 Dispatch Board (Ctrl+5)
The operations centerpiece. 3 tabs: **Board | Alerts | Timeline**.
- Header (72px): title/subtitle + Export CSV · Export PDF · Refresh
- **Board tab**: search bar (debounced; filters trip id, plate, driver, origin, destination, status) + 5 status filter checkboxes with colored dots + "Showing X of Y" count → bulk toolbar (appears on multi-select: N selected · Clear Selection · Assign Driver · Assign Truck) → **5 kanban columns** (Planned gray, Loading amber, In Transit blue, Delivered green, Cancelled gray) — each: 4px accent bar, header with count, scrollable card list; Delivered shows last 4 (expandable to 30 days/2000 trips), Cancelled capped at 3
- **Trip cards**: truck icon + `#ID` + delayed chip + status chip · truck plate (or "Assign Truck") · "⚡ Assign Both" · driver name (or "Assign Driver") · origin → destination · departure/ETA dates · red "N alerts" banner · live GPS dot + speed for in-transit trips. Click = detail drawer; Ctrl+click = multi-select; drag = move; click plate/driver = inline assign dropdown; ✕ = clear assignment
- **Drag & drop**: forward-only transitions (Planned→Loading→In Transit→Delivered); backward requires confirmation; invalid = red column highlight + error toast
- **Hover quick actions**: View Details · Start Loading · Mark In Transit · Mark Delivered · Cancel Trip · Documents submenu (Generate Invoice/CMR/Receipt → Generators view)
- **Detail drawer**: 480px slide-in panel — trip fields + unresolved alerts (≤20, severity chips); Edit mode: status dropdown (valid targets only), dates, distance; Save/Cancel
- **Paired assignment dialog** (600×520): side-by-side truck/driver lists with availability dots, ⭐ score >70, sublabels (license cat / weekly hours), Auto-selects first available pair; scoring = next slot + fuel + health + tacho violations + weekly hours; Assign Both / Truck Only / Driver Only
- **Alerts tab**: day summary KPIs (departing/arriving today, critical count, needs-attention) · active alerts (≤20, resolve buttons, Resolve All) · unassigned trips grouped by missing truck/driver/both with Quick Assign · assignment summary counts
- **Timeline tab**: Gantt-like rows per truck with colored status bars
- 30s auto-refresh + event-bus incremental card updates (trip created/updated/status/assigned, alerts, truck/driver changes); conflict scan after each render

### 5.6 Fleet Tracking (Ctrl+6)
Live GPS map. Splitter: map 72% / vehicle sidebar 28%.
- Map markers color-coded: moving=green, stopped=gray, idle=orange, offline=red; click marker/row → pan + detail
- Sidebar: header (title, last-updated, refresh), vehicle cards (status dot, name, speed/address), fixed detail panel (name, status, speed, odometer, address; buttons Fleet Detail / Maintenance / Documents / Call Driver → toast with phone)
- Right-click vehicle: View Details / Maintenance / Documents / Show on Map. 30s polling
- Unconfigured state: globe icon + hint + Configure → Settings

### 5.7 Freight Exchange
Load marketplace (Trans.eu et al.).
- **Connect**: status badge + expiry countdown (red <10min, amber <30min), Connect (browser OAuth via localhost loopback :19999), Test, Disconnect
- **Search**: left filter panel (280px): origin/dest, date range, trailer type, ADR checkbox, weight min/max, price min/max, distance max, loading/delivery country; Search Now (primary) + Save Search. Results table: provider, origin, destination, price, distance, trailer, ADR, actions (Import / Evaluate). Sort combo (relevance/price/distance/date ↑↓). Provider health dots in summary bar
- **Load detail**: back/import/refresh header → evaluation card (Revenue, Total Cost, Expected Profit, Margin, Risk Score KPIs, color-coded) → ranked fleet matches (#01 rank, truck id, score bar green ≥85/amber ≥50/red <50, reason chips, profit preview, Assign)

### 5.8 Fleet
Truck management dashboard.
- Header (72px) + KPI strip (Total trucks, Active, Monthly leasing €, Active alerts)
- Split: table 70% / right tabbed panel 30% (**Alerts** list with colored left borders → navigates to Maintenance; **Charts** status pie + grid toggle; **Quick-add** plate + model + rate)
- Table columns: ID, Plate, Model, Manufacturer, Year, VIN, Mileage, Fuel consumption, Monthly rate €, Status, Active, Driver — searchable, sortable, density toggle, double-click detail, right-click menu (view/edit/delete)
- **Truck form dialog**: plate, model, manufacturer, year, VIN, fuel consumption, mileage, monthly rate, status, tracking device id, driver assignment, active
- Actions: Add / Edit / Delete (confirm) / Export CSV/Excel/PDF / Documents

### 5.9 Drivers (Ctrl+8)
- KPI strip: Total Drivers, **Expiring** (license/medical ≤30 days), **On Trip**, **Unassigned**
- Table: id, name, phone, license category, license expiry, medical expiry, hire date, salary, active, truck (plate/"Unassigned") + inline action buttons (edit, documents, truck assign)
- Collapsible tacho detail panel (last 28 days) on row selection
- **Driver form dialog** (480×600): name, phone, email, license number/category/expiry, medical expiry, hire date, monthly salary, notes, truck assignment, active
- Actions: Add/Edit/Delete, Import CSV, Export CSV, Documents, Assign Truck, Toggle Active

### 5.10 Clients (Ctrl+9)
- **Client manager**: search + "+ New Client" · table (id, name, contact, phone, email, trips) · Edit / Deactivate / density · right-click: Edit, View Trips (→ workspace), Deactivate (confirm w/ trip-count warning)
- **Client form dialog**: name (required), contact person, phone, email, address, VAT, notes; duplicate-name check
- **Client workspace**: outer tabs **Manager | AutoMail**; per-client detail tabs (enabled on selection):
  - **Details**: profile (type badge, star rating, active status; 9 double-click inline-editable fields incl. VAT/EORI, payment terms + credit limit) · KPI grid 2×4 (revenue, trips, km, profit, outstanding balance…) · contacts (primary star, types, add/edit/delete) · tags (chips + add) · payment summary (Billed/Paid/Unpaid/Overdue) · activity timeline
  - **Trips**: table + right-click Edit Trip / View Route / Generate Invoice
  - **Invoices**: table, green/amber status cells, right-click Edit/View/Download
  - **Revenue**: 12-month revenue vs profit grouped bars (profit green/red)

### 5.11 Documents
3-panel document hub. Top-level tabs: **Documents | Automation | API Dashboard** (admin-gated).
- Left sidebar (20%): category buttons with counts (All, Maintenance, Invoices, Proformas, Receipts, Trips, Drivers, Vehicles, Other) + filter toggle (entity type, date from/to, MIME) + Upload button
- Center list (50%): sort combo, debounced search, select-all, admin shield; batch bar on selection (Download ZIP, Batch Delete); doc rows (checkbox, 96×72 thumbnail, title, doc number, size, date, tag chips, View/Email/Delete); pager; empty state with upload CTA
- Right detail (30%): title, number, size/mime, editable tags, linked entities, expiry date picker, actions: Open, Email, Delete, **OCR**, **Link to Trip** (trip picker dialog)
- Search is full-text; auto-refreshes on document/invoice/proforma/receipt events

### 5.12 Maintenance Control
- KPIs: avg fleet health (0–100 + progress bar), trucks needing service, **overdue schedules** (red if >0), cost last 30d, total cost — 60s auto-refresh with shimmer
- **Tacho table**: driver/vehicle, card expiry, last download, next due; Import button
- **Alert list**: filter bar (severity checkboxes Critical/Warning/Info, type dropdown, truck/trip text filters, show-resolved) + C:W:I count summary; alert cards with colored left borders (red/amber/blue), resolve on click
- **Fuel panel** (collapsible): custom-painted horizontal bars of diesel price by country — red >€1.80, amber >€1.40, else green; max 15 countries; data-age label

### 5.13 Maintenance Analytics
- Header + two side-by-side Plotly charts: monthly cost per truck grouped bars (12 months, per-truck colors) + fleet total cost trend line
- Table: truck, YTD cost €, avg cost €, service count, top category; grid toggle; empty state when no data

### 5.14 Tachograph
Import tacho files (DDD/TGD). Split 45/55.
- Left: import card — **drop zone** (dashed border, drag or click; "DDD / TGD / alte fisiere tahograf"), two buttons (Driver Card / Vehicle Unit), progress label; result card after import: big ✓/✗, summary, driver/plate/calibration expiry/days imported/odometer, amber violations chip
- Right: import history table (date, type, file, records, status colored ok/error/partial), context menu (View Details / Re-import / Delete), density toggle

### 5.15 Invoices — Generators View
Unified workspace for generating documents for a trip. Header with trip selector (340px) + refresh; 4 tabs: **Invoice | CMR | Receipt | Proforma** (lazy-built; trip auto-fills everything).

**Invoice editor** (scrollable form, fixed top/bottom bars):
- Top bar: client combo, trip combo, Auto-fill (primary), Client/Internal checkboxes, refresh
- Sections: From/Bill To (company + client cards, read-only canvas labels with pencil-edit) · Invoice Details (number, issue date, due date, payment terms, branch, number format combo w/ examples) · Trip Details (plate, driver, distance, loading/unloading stops — dynamic rows) · **Line Items** table (#, description, amount; add/remove rows) · Totals (VAT rate 0/5/9/19/20/21/24/25%, discount type+value, currency EUR/RON/USD/GBP, read-only subtotal/tax/discount/grand total) · Branding (logo, color picker, signature, stamp) · Notes
- Bottom bar: Preview PDF · Generate PDF (primary) · Print · Email · Save Draft · Load Draft · Export JSON
- Romanian fiscal: CUI fields, series + number formats

**Proforma editor**: same pattern, minus trip selector; "Valid Until" instead of due date; payment terms (Net 30/15/60, Due on Receipt); auto-numbered; **Linked Documents** section with OCR autofill (autofills fields from scanned docs)

**Receipt editor** (only editor with live HTML preview pane, QWebEngineView):
- 12 sections: Type (11 types: customer payment, cash, driver/employee/fuel/toll reimbursement, refund, deposit, advance, other) · Invoice autofill · Info (number, issue date, payment date, currency, language, branch) · Parties (Received From / Received By) · Payment details (method Cash/Transfer/Card/Mobile/Other, refs) · Logistics (trip, customer, vehicle, trailer, pickup/delivery, route, dispatcher) · Purpose · Financial (amount, VAT, total, **amount in words**) · Employee expenses (conditional) · Attachments · Notes · Branding
- Toolbar: Generate PDF · Print · Save/Load Draft · Duplicate · Export JSON · Email

**CMR form** (UN/CEFACT 24-box, EN/RO bilingual):
- Heading with live **box navigator** — 24 number badges colored green (filled) / yellow (empty) / blue (informational), updating as you type
- Role selector: "I am the Consignor (Sender)" / "I am the Consignee (Receiver)" — swaps which party is auto-filled from company vs client
- 5 collapsible sections: Parties (Boxes 1,2,18,19 + successive carriers rows) · Goods (6–12 + ADR danger-goods expander: UN no, class, packing group, tunnel code) · Route (3–5, loading/delivery dates + ISO country codes, vehicle & driver card) · Instructions (13–17, 20: payment instruction, COD, charges table with Sender/Consignee columns) · Issue & Signatures (21–24: issue place/date + **3 signature pads** — freehand drawing canvas, saves PNG)
- Bottom bar: Preview · Generate CMR · Print · Save + progress bar; validation marks required fields red

### 5.16 History
Completed-trip archive with actions.
- Filter bar: search, status combo (Planned/In Transit/Loading/Delivered/Invoiced/Paid/Archived), Reset, count
- Table: ID, status (colored chips), date, truck, driver, client, km, brut/km, **profit** (green/red, bold if |profit|>1000)
- Actions: Generate Invoice (primary) · Export PDF/Excel · Email Invoice · View Route · Documents · Load More · Delete
- Right-click: Edit Trip / Generate Invoice / View Route

### 5.17 Route History
Browse past route calculations. Splitter: table 60% / map preview 40%.
- Filters: text search (origin/dest/truck/driver/CMR/client), profile dropdown, plate field, "Include archived", Apply/Reset
- Table: origin, destination, datetime, truck, distance, duration, profile
- Click row → load geometry → polyline preview on map; double-click → open in Planner; Recalculate (duplicate + re-run); context menu: Open Planner / Duplicate / Recalculate / Archive / Delete; Export JSON/CSV

### 5.18 CoPilot (AI assistant)
- **Chat panel** (dockable right side, min 320px): header (title + voice mode combo: Push to Talk / Wake Word + New Conversation) · conversation (user bubbles right-aligned accent-tinted, AI bubbles left-aligned elevated, HH:MM timestamps, max-width 480px) · input bar (QLineEdit + push-to-talk mic button + send). Mic states: idle (border), listening (red), processing (amber). Voice → Whisper transcription
- **Thinking indicator**: animated 3-dot pulsing "Thinking…"
- **Timeline widget**: execution plan steps with status dots (running pulse/awaiting/pending), expandable step params (secrets redacted `****`), reasoning graph tree view (GOAL/DECISION/QUERY nodes)
- **Confirmation modal**: step-by-step diff (red before / green after frames), Level-2 amber warning, Level-3 requires typing a phrase; OCR candidate pick-list with "None of these" escape
- **Insights queue** (enterprise): proactive cards (cost anomaly, driver alert, maintenance due, overdue invoice, fuel trend, return load, fleet availability) with severity pills and Review/Dismiss/Remind Later
- **Guided tours**: full-window overlay — 55% dim scrim, 3px indigo pulsing highlight ring around target, tooltip card (max 400px, step counter "2 / 8", Cancel/Skip/Replay); waits for click or text input on target; Escape cancels
- **Ask AI**: right-click any registered element → "Ask AI about this" → pre-fills chat with contextual question
- **Struggle detector**: heuristics (≥4 screen switches in 30s, A→B→A→B pattern, idle after rapid nav) fire subtle nudge tooltips after 120s cooldown

### 5.19 Migration Center
3 tabs for import/export.
- **Immigrate software**: wizard — format (CSV/Excel/JSON/XML) + entity (Clients/Drivers/Trucks/Trips/Invoices) + file picker → Preview → **field mapping** table (source column → target field + samples) → Validate & Find Duplicates → results (valid/invalid/duplicates counts, invalid rows table, duplicate resolution radios: skip/update/keep both) → Import with progress bar
- **Immigrate physical**: paper digitization — drop zone (PDF/JPG/PNG), batch progress, per-file status table (filename, status badge, doc type, confidence, actions), review card for low-confidence (<70%) docs
- **Emigrate**: entity selector → field checkboxes → date range → row preview → format radios → output path → Export with progress → "Open file" on success

### 5.20 Team
Card-based user management. **Add User** card: email, password, role combo (Dispatcher/Driver), driver-link combo (only for Driver role) · **Team Members** card: table (email, role, status, created, Deactivate button); context menu deactivate with confirmation

### 5.21 Settings
Single scrollable page of collapsible section cards + live section search + fixed bottom save bar (`_save_all` → hot-reloads SMTP/OCR/AI config, theme applies instantly).
- **Company**: name, CUI, reg number, address, city, country, phone, email, IBAN, bank
- **Branding**: logo path, company color (swatch + picker), signature, stamp
- **Preferences**: language, currency, theme (dark/light)
- **E-mail/SMTP**: server, port, user, password, alert recipients; Test Connection + View Logs
- **Fleet Tracking**: platform (Wialon, Frotcom, Navixy, Traccar, Generic REST) with dynamic per-platform fields + test
- **Maintenance**: alert days ahead, tacho warning/critical thresholds
- **Automation**: OCR credentials (Google Vision, Azure, PaddleOCR GPU + advanced config), AI Vision Gemma 3 (endpoint/key/model/max pages/RPM/timeout/confidence), Email Importer (IMAP host/port/user/password/interval/whitelist/delete), Folder Watcher (path/interval/recursive/delete)
- **Autonomous Mode** (enterprise): auto-dispatch, auto-invoice, auto-email toggles + circuit breaker status

---

## 6. Embedded / Supporting Surfaces

- **API Dashboard** (Document Center tab): status cards (API server, database, version — online/offline colored), Test API, Refresh, 5s auto-refresh, timestamped connection log (max 100 entries)
- **Admin Panel** (Document Center, admin JWT): tabs — Diagnostics (latency, Celery, Redis, config flags) · Database Inspector (table selector, schema, raw SQL runner) · Document Statistics (total/storage/OCR coverage/orphans + category breakdown) · System Info (env vars, log tail 100 lines) · Health (service cards, Clear Cache)
- **Automation view**: document pipeline (drop → OCR → match trip → package → email). Drop zone (JPG/PNG/PDF/TIFF/HEIC), run cards with stage dots + progress, detail panel (matched trip + confidence, extracted fields, candidate list, actions: Prepare Package, Send, manual trip search). Simple/Advanced mode. Concurrency cap (default 2, max 8). Feeds from email importer + folder watcher
- **Automail** (in Client Workspace): 3-panel splitter 20/55/25 — **Config** (master toggle, reminder schedules list with inline editor: trigger type days_before/on_due/days_after, template, attachment checkboxes; delivery rules: business hours, skip weekends; safety caps; presets Friendly/Professional/Strict) · **Timeline** (invoice reminders: stats bar sent/failed/outstanding, filter pills, per-invoice cards with Send Now/Skip/Cancel + colored dots) · **Editor** (template selector + CRUD, subject with `{{ variable }}` insert popup, rich-text body, format toolbar, live preview toggle, Send Test)
- **Bulk Payments**: recipient sources (clients/drivers/custom profiles) with searchable table (name, type, bank, IBAN) → batch table (add with amount prompt, edit/remove, total row) → **Export CSV** payment file. Custom profile dialog (bank details, type: custom/government/supplier/contractor/other, contact info)
- **Upload integration** (dev tool): file pick ≤50MB → upload with progress → OCR fetch → extracted fields panel
- **Package preview modal**: trip's documents as a reorderable drag list (ZIP or combined PDF) → Continue to Email
- **Email composer**: trip context auto-subject/body via templates, recipient detection, attachment validation (>25MB warning), SMTP send on background thread, save draft, sent-package tracking

---

## 7. Cross-Cutting Systems

- **Alerts**: types — trip delay, maintenance/inspection/insurance due, overdue invoice, inactive truck, route issue, compliance, tachograph expiry, driver hours (weekly/daily), document/contract expiry, policy violation. Severities CRITICAL (red) / WARNING (amber) / INFO (blue). Surfaced in: bell popup, dispatch Alerts tab, per-page alert lists, trip card banners
- **Sync**: local↔server conflict journal with per-row resolution (Keep local / Take server); sync status in topbar
- **Toasts/undo**: transient success/error feedback; undo/redo of status changes
- **Auto-refresh cadence**: dashboards 30s, fleet tracking 30s, maintenance panel 60s, API dashboard 5s
- **Performance**: charts rendered off-thread (SVG → rasterize), LRU-cached, resize-debounced; views pre-warmed at startup; worker pool + async tasks for all background I/O

---

## 8. Known Gaps / Notes

- Export implementations for dispatch board (CSV/PDF buttons) not located in view code
- Pending-trip highlight from alert navigation is stubbed (loads board, doesn't yet scroll/highlight the card)
- Freight provider settings: disconnect/test partially placeholder; Save Search button is a no-op placeholder
- Theme engine (`ui.theme_engine`) referenced by shared widgets; QSS is generated at runtime
