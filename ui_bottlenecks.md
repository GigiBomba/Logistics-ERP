# Phase 2: UI Bottleneck Analysis

## Classification Legend

| Category | Meaning |
|----------|---------|
| 🔴 **BLOCKING** | Freezes UI thread; user perceives hang >500ms |
| 🟠 **DEGRADED** | Noticeable jank 200-500ms |
| 🟡 **INEFFICIENT** | Works but wastes cycles/wrong pattern |
| 🟢 **ACCEPTABLE** | No intervention needed |

---

## 1. FleetTab N+1 Query (🔴 CRITICAL — BLOCKING)

### Problem
For each truck row, a separate SQL query fetches the assigned driver name.

### Location
- **View**: `ui/views/fleet_tab/fleet_tab.py`
- **Method**: `_load_table_and_kpis()` — lines 500–533
- **N+1 loop**: lines 503–508

```python
for r in rows:                          # 100 trucks
    driver_name = (
        self._dta_service.get_driver_name_for_truck(r["id"])  # 1 DB query EACH
        if self._dta_service is not None else None
    )
```

### Downstream calls
- Service: `services/driver_truck_service.py:480` → `_repo.get_driver_name_for_truck(truck_id)`
- Repo: `repositories/driver_truck_assignment_repository.py` — plain `SELECT ... WHERE truck_id = ?`

### Why it blocks the UI
- All 100 queries run synchronously on the main thread
- Each query: ~5–10 ms (local SQLite), ~10–50 ms (remote PostgreSQL)
- Total: 500–5000 ms of blocked UI thread
- No `WorkerPool` usage — `refresh()` is synchronous (line 482)

### Fix pattern
Replace 100 individual queries with ONE batch query returning `{truck_id: driver_name}` mapping.

```sql
SELECT da.truck_id, d.name AS driver_name
FROM driver_truck_assignments da
JOIN drivers d ON da.driver_id = d.id
WHERE da.truck_id IN (?, ?, ?, ...)
```

### Confidence: **100%** — confirmed by direct code inspection

---

## 2. RoutePlanner N+1 Query (🔴 CRITICAL — BLOCKING)

### Problem
For each truck in the combo box, `get_next_available_slot()` fires a separate SQL query.

### Location
- **View**: `ui/views/route_planner_view.py`
- **Method**: `_load_trucks()` — lines 878–903
- **N+1 loop**: line 893

```python
for row in rows:  # up to 100 trucks
    next_slot = conflict_svc.get_next_available_slot(plate)  # 1 query EACH
```

### Downstream calls
- `services/conflict_service.py:get_next_available_slot(plate)` → queries trip conflicts for that specific truck

### Why it blocks the UI
- Synchronous, main-thread queries
- Each slot lookup scans trips table for that truck
- 100 trucks × ~10 ms = 1000 ms blocked

### Fix pattern
Batch query: get next available slot for ALL trucks in one SQL.

```sql
SELECT t.plate_number, MIN(t.created_at) as next_available
FROM trips t WHERE t.truck_id IN (?,?,...) AND t.status IN (...)
GROUP BY t.truck_id
```

Or: remove slot display from combo (non-critical info) and lazy-load on demand.

### Confidence: **100%** — confirmed by direct code inspection

---

## 3. OverviewView KPI Card Destroy/Recreate (🔴 HIGH — BLOCKING)

### Problem
Every `refresh()` destroys all KPI card widgets and creates new ones.

### Location
- **View**: `ui/views/overview_view.py`
- **Method**: `_rebuild_kpi_strip()` — lines 236–258

```python
# Clear existing cards (DESTROY)
while self._kpi_strip_layout.count():
    item = self._kpi_strip_layout.takeAt(0)
    w = item.widget()
    if w is not None:
        w.deleteLater()
self._kpi_widgets.clear()

# Rebuild (CREATE)
for key, label, default in kpi_defs:
    card = CompactKPICard(...)
    self._kpi_strip_layout.addWidget(card, 1)
```

### Why it blocks the UI
- Widget creation + layout recalculation on every 30s refresh
- Qt layout engine re-measures and re-positions all cards
- 3 cards × ~30 ms each = ~90 ms wasted per refresh

### Fix pattern
Create cards ONCE at build time. On refresh, only call `setText()` on the `value_label` reference (which is already stored in `self._kpi_value_labels`).

### Confidence: **100%** — code literally calls `deleteLater()` then `addWidget()` every refresh

---

## 4. FleetTab KPI Strip Destroy/Recreate (🟠 HIGH — DEGRADED)

### Problem
Same destroy/recreate pattern as OverviewView.

### Location
- **View**: `ui/views/fleet_tab/fleet_tab.py`
- **Method**: `_rebuild_kpi_strip()` — lines 291–311

```python
while self._kpi_strip_layout.count():
    item = self._kpi_strip_layout.takeAt(0)
    w = item.widget()
    if w is not None:
        w.deleteLater()
```

### Fix pattern
Remove `_rebuild_kpi_strip()` entirely. Build cards once in `_build_kpi_strip()`. Update via `setText()`.

### Confidence: **100%**

---

## 5. FleetTracking Vehicle List Destroy/Recreate (🟠 HIGH — DEGRADED)

### Problem
Every poll cycle (30s), ALL vehicle rows are destroyed and recreated.

### Location
- **View**: `ui/views/fleet_tracking_view.py`
- **Method**: `_refresh_vehicle_list()` — lines 486–508

```python
# Remove existing rows (DESTROY ALL)
while self._vehicle_list_layout.count():
    item = self._vehicle_list_layout.takeAt(0)
    widget = item.widget()
    if widget is not None:
        widget.deleteLater()

# Rebuild ALL
for pos in sorted(positions, ...):
    self._build_vehicle_row(pos, truck_id)
```

### Why it blocks the UI
- 50 vehicles × 10 widgets each = 500 widget create/destroy cycles
- Happens every 30s in background
- Detail panel also destroys/recreates on selection (line 396–400)

### Fix pattern
Keep rows alive. On refresh, update text values in-place using widget references. Only create rows for new vehicles, remove rows for disappeared vehicles.

### Confidence: **100%**

---

## 6. AnalyticsView Eager Load of All 6 Tabs (🔴 HIGH — BLOCKING ON STARTUP)

### Problem
All 6 analytics tabs are created, data-fetched, and chart-rendered on first show.

### Location
- **View**: `ui/views/analytics/__init__.py`
- **Method**: `_start_loading()` — lines 108–123

```python
for idx in range(self._total_tabs):
    timer = QTimer(self)
    timer.timeout.connect(lambda i=idx: self._load_tab(i))
    timer.start(idx * self._tab_load_delay)  # 50ms staggered
```

Each `_load_tab()` calls `tab.refresh()` which queries DB and renders 5–20 Plotly charts.

### Why it blocks the UI
- Financial tab renders immediately (first timer)
- All 6 tabs render within 300ms (6×50ms stagger)
- Total: ~1800–9000ms where UI is behind a loading overlay
- Full-window LoadingOverlay blocks the entire analytics view

### Fix pattern
Lazy-load tabs: render ONLY the visible tab. Load others when user clicks them. Already has a `QTabWidget.currentChanged` signal (line 143) — use it to trigger lazy load.

### Confidence: **100%**

---

## 7. OverviewView Multiple Analytics Service Calls (🟡 MODERATE — WASTED CYCLES)

### Problem
`refresh()` makes 5+ separate analytics service calls, each potentially hitting the DB.

### Location
- **View**: `ui/views/overview_view.py`
- **Method**: `refresh()` — lines 384–407
- Calls: `_refresh_kpis()`, `_render_profit_chart()`, `_refresh_active_trips()`, `_refresh_top_trucks()`, `_refresh_recent_activity()`, `_refresh_alerts()`

### Why it matters
- `_compute_kpi_value()` (line 422) calls analytics service methods separately per KPI key
- `_refresh_active_trips()` calls `trip_service.get_all(limit=200)` (line 535)
- `_refresh_top_trucks()` calls `trip_service.get_top_trucks_by_revenue()` (line 655)
- `_refresh_recent_activity()` calls `trip_service.get_all(limit=6)` (line 708) — **duplicate** of line 535

### Fix pattern
Merge trip queries (active + top + recent) into one batch call. Use `WorkerPool` to run DB calls off main thread.

### Confidence: **90%** — dependent on service-level batching feasibility

---

## 8. Database: LIKE pattern for KPI month filter (🔴 CRITICAL — FULL TABLE SCAN)

### Problem
`get_kpi_stats()` uses `LIKE '%2026-01%'` instead of a range query.

### Location
- **Repo**: `repositories/analytics_repository.py`
- **Method**: `get_kpi_stats()` — line 147

```sql
SELECT ... FROM trips WHERE created_at LIKE ?  -- '%2026-01%'
```

### Why it blocks
- Full table scan — cannot use index on `created_at`
- Leading wildcard `%` forces sequential scan of entire `trips` table
- Every overview refresh triggers this

### Fix pattern
Replace with range query:

```sql
SELECT ... FROM trips
WHERE created_at >= '2026-01-01' AND created_at < '2026-02-01'
```

### Confidence: **100%**

---

## 9. Missing Composite Indexes (🟡 MODERATE)

### Problem
No composite indexes on frequently filtered column pairs.

### Location
- **Database schema**: `database/schema.py` or Alembic migrations

### Missing indexes:

| Table | Columns | Query pattern |
|-------|---------|---------------|
| `trips` | `(company_id, status)` | `WHERE company_id = ? AND status = ?` — used in active trip counts |
| `trips` | `(company_id, created_at)` | `WHERE company_id = ? AND created_at BETWEEN ? AND ?` — used in period filters |
| `trucks` | `(company_id, status)` | `WHERE company_id = ? AND status = ?` — fleet table queries |
| `invoices` | `(company_id, status)` | `WHERE company_id = ? AND status = ?` — unpaid invoice counts |

### Fix pattern
Add these indexes via Alembic migration:

```sql
CREATE INDEX IF NOT EXISTS idx_trips_company_status ON trips(company_id, status);
CREATE INDEX IF NOT EXISTS idx_trips_company_created ON trips(company_id, created_at);
CREATE INDEX IF NOT EXISTS idx_trucks_company_status ON trucks(company_id, status);
CREATE INDEX IF NOT EXISTS idx_invoices_company_status ON invoices(company_id, status);
```

### Confidence: **95%** — need EXPLAIN QUERY PLAN verification

---

## 10. PostgreSQL autocommit=True (🟡 MODERATE — DATA INTEGRITY RISK)

### Problem
All PostgreSQL pool connections set `autocommit=True`, meaning every statement commits immediately — no transactional safety.

### Location
- `database/connection_pool.py` — lines 229, 248

```python
conn.autocommit = True  # Both get_connection() and get_cached_connection()
```

### Risk
- Multi-step operations (e.g., create trip + update truck) have no rollback
- If step 2 fails, step 1 is already committed
- Data inconsistency under concurrent access

### Fix pattern
Set `autocommit=False`. Use explicit `conn.commit()` after successful multi-step operations. Ensure all repository methods that write to DB commit explicitly.

### Confidence: **100%**

---

## 11. GeneratorsView Trip Combo Rebuild (🟡 MODERATE — WASTED CYCLES)

### Problem
Trip combo in generators/invoices view is cleared and repopulated on every refresh.

### Location
- `ui/views/generators_view.py` — trip combo population logic

### Fix pattern
Update combo items in-place: add new, remove deleted, update changed. Avoid full clear+repopulate.

---

## 12. ClientWorkspace Revenue Chart Rebuild (🟡 MODERATE)

### Problem
Revenue chart widget is rebuilt on every refresh (like OverviewView chart).

### Location
- `ui/views/client_workspace/` — chart population logic

### Fix pattern
Use the same staleness-based approach as OverviewView's `_should_rerender_chart()`.

---

## 13. Design System: Inconsistent Border Radius (🟢 INEFFICIENT)

### Problem
Hardcoded border-radius values scattered across files:

| Value | File | Line Examples |
|-------|------|---------------|
| 2px | `theme_engine.py:867,1051`, `sidebar.py:306` | 2 occurrences |
| 3px | `trip_card.py:193,338,636`, `topbar.py:78,131,133`, `dispatch_alerts_panel.py:267` | 8+ occurrences |
| 4px | `dispatch_detail_panel.py:129,312`, `login_dialog.py:149,174`, `stat_card.py:72,103`, `dispatch_timeline.py:238`, `alert_panel.py:201` | 20+ occurrences |
| 6px | `dispatch_detail_panel.py:489`, `paired_assignment_dialog.py:186`, `chart_loading_overlay.py:141`, `theme_engine.py:1036,1090` | 6+ occurrences |
| 8px | `share_route_dialog.py:273`, `automail_view.py:77`, `automation_view.py:113,146` | — |
| 9px | `theme_engine.py:502,1182` | 2 occurrences |
| 12px | `chart_loading_overlay.py:160` | 1 occurrence |

Token definitions vs reality:
- `RADIUS_SM = 4` — mostly consistent
- `RADIUS_MD = 6` — mostly consistent  
- `RADIUS_LG = 8` — mostly consistent
- `RADIUS_PILL = 100` — used correctly in `components.py`

### Fix pattern
Replace ALL hardcoded `border-radius: Npx` with design tokens (`RADIUS_SM`, `RADIUS_MD`, `RADIUS_LG`, `RADIUS_PILL`). The 3px → `RADIUS_SM-1` needs a new token or use `RADIUS_SM`. The 9px needs `RADIUS_MD+3` or a new token.

---

## 14. Design System: Spacing Grid Violation (🟢 INEFFICIENT)

### Problem
`SPACE_3 = 12` and `SPACE_5 = 20` break the 8px grid. Everything should be multiples of 4 or 8.

### Location
- `ui/design_tokens.py` — lines 92–101

| Token | Value | Grid-compliant? |
|-------|-------|-----------------|
| SPACE_1 = 4 | ✅ | |
| SPACE_2 = 8 | ✅ | |
| SPACE_3 = 12 | ❌ | Should be 8 or 16 |
| SPACE_4 = 16 | ✅ | |
| SPACE_5 = 20 | ❌ | Should be 24 |
| SPACE_6 = 24 | ✅ | |
| SPACE_8 = 32 | ✅ | |
| SPACE_10 = 40 | ✅ | |

### Fix pattern
- `SPACE_3` → `8` (change or add `SPACE_2S` = 8, deprecate SPACE_3)
- `SPACE_5` → `24` (change or deprecate)
- Audit all usages of `SP["3"]` and `SP["5"]` — they may need compensation for the change

---

## 15. Design System: Button Height Mismatch (🟢 INEFFICIENT)

### Problem
Token says `BTN_HEIGHT = 32` but QSS says `min-height: 38px`.

### Location
- Token: `ui/design_tokens.py:224` — `BTN_HEIGHT = 32`
- QSS: `ui/theme_engine.py:338` — `min-height: 38px;`
- QSS: `ui/theme_engine.py:527` — `min-height: 38px;` (ComboBox too)

### Fix pattern
Decide canonical height:
- **Option A**: Set `BTN_HEIGHT = 38`, update token
- **Option B**: Set QSS `min-height` to `32px`, which would change all button heights
- **Option C**: Set both to `36px` as compromise

**Recommend Option A** — 38px is already the rendered height; align token to match.

---

## 16. Design System: Hardcoded Font Sizes (🟢 INEFFICIENT)

### Problem
7px and 8px font sizes in CMR/receipt forms are below minimum readability.

### Location
- `ui/views/cmr_form_view/cmr_form.py` — lines 151, 157, 163, 227, 433: `font-size: 7px` and `font-size: 8px`
- `ui/views/cmr_form_view/cmr_fields.py:635`: `font-size: 8px`
- `ui/views/analytics/driver_tab.py:280`: `font-size: 8px`
- `ui/views/automail/timeline_panel.py:212`: `font-size: 8px`
- `ui/views/receipt_editor/editor_form.py:1505,1566,1571`: `font-size: 8px`

### Fix pattern
Replace 7px → `FONT_SIZE_XS` (10px in design_tokens) or add `FONT_SIZE_2XS = 9` if micro-text is necessary. Replace 8px → `FONT_SIZE_XS` (10px).

---

## Summary: Bottleneck Ranking by Impact

| Rank | Bottleneck | View | Severity | Est. UI Block | Fix Complexity |
|------|-----------|------|----------|--------------|----------------|
| 1 | N+1 driver queries | FleetTab | 🔴 Critical | 500–5000ms | Low (batch SQL) |
| 2 | N+1 slot queries | RoutePlanner | 🔴 Critical | 400–1000ms | Low (batch SQL) |
| 3 | LIKE month scan | AnalyticsRepo | 🔴 Critical | 100–500ms/query | Trivial (1 line) |
| 4 | KPI widget destroy/recreate | OverviewView | 🔴 High | 60–90ms/refresh | Low (update in place) |
| 5 | 6-tab eager load | AnalyticsView | 🔴 High | 1800–9000ms startup | Medium (lazy load) |
| 6 | Vehicle list destroy/recreate | FleetTracking | 🟠 High | 40–150ms/poll | Medium (diff-based update) |
| 7 | KPI widget destroy/recreate | FleetTab | 🟠 High | 30–80ms/refresh | Low (update in place) |
| 8 | autocommit=True | ConnectionPool | 🟡 Moderate | Data integrity risk | Low |
| 9 | Missing composite indexes | Schema | 🟡 Moderate | 10–50ms/query | Low (migration) |
| 10 | Design system inconsistencies | Global | 🟢 Cosmetic | 0ms (visual only) | Medium (search+replace) |
