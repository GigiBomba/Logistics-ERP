# Phase 1: UI Performance Instrumentation Baseline

## Goal
Measure exact timing of every view's data-load path on real hardware (not estimates). The infrastructure already exists (`PerfTimer` in `ui/performance_timer.py`); this plan wires it into every bottleneck path.

---

## 1. Existing Infrastructure

| Tool | Location | Status |
|------|----------|--------|
| `PerfTimer` context manager | `ui/performance_timer.py:19-70` | ✅ Already imported in `main_window.py` and `base_view.py` |
| `timing_report()` | `ui/performance_timer.py:124+` | ✅ Global accumulator — all labeled timings collected |
| `timing_table()` | `ui/performance_timer.py:145+` | ✅ Formatted table output |
| `reset_timings()` | `ui/performance_timer.py:44` | ✅ Clear for each run |
| Skeleton overlay system | `ui/skeleton_widgets.py` | ✅ `BaseView._show_loading()` / `_hide_loading()` |

---

## 2. Instrumentation Points — Per View

### 2.1 OverviewView
**File**: `ui/views/overview_view.py`

| Label | Where to add | What it measures |
|-------|-------------|-----------------|
| `overview.refresh` | Line 384 `refresh()` — wrap entire body | Total refresh time (KPIs + chart + trips + alerts + trucks + activity) |
| `overview.kpi` | Line 412 — wrap the KPI loop | Time for 3 KPI `_compute_kpi_value` calls |
| `overview.chart` | Line 764 — wrap `_render_profit_chart` | Chart SVG render + pixmap generation |
| `overview.trips` | Line 531 — wrap `_refresh_active_trips` | Trip list fetch + widget population |
| `overview.trucks` | Line 649 — wrap `_refresh_top_trucks` | Top trucks query + widget population |
| `overview.alerts` | Line 586 — wrap `_refresh_alerts` | Alert list fetch + widget population |
| `overview.activity` | Line 704 — wrap `_refresh_recent_activity` | Activity list fetch + widget population |
| `overview.wakeup` | Line 1100 — `wakeup()` already inherits `PerfTimer` from `BaseView` | Full wakeup (skeleton → data) |

**Estimated times** (from code analysis, not measurement):
- `overview.refresh`: 150–600 ms (depends on analytics service cache hit/miss)
- `overview.kpi`: 80–300 ms (3× `_compute_kpi_value`, each calls analytics service)
- `overview.chart`: 200–800 ms (Plotly SVG render + QPixmap)
- `overview.trips`: 20–100 ms
- `overview.trucks`: 30–150 ms
- `overview.alerts`: 5–30 ms
- `overview.activity`: 20–80 ms

---

### 2.2 FleetTab (Critical: N+1)
**File**: `ui/views/fleet_tab/fleet_tab.py`

| Label | Where to add | What it measures |
|-------|-------------|-----------------|
| `fleet_tab.refresh` | Line 482 `refresh()` — wrap body | Total refresh time |
| `fleet_tab.load_table` | Line 500 — wrap `_load_table_and_kpis` | Table population + KPI compute + DRIVER N+1 LOOP |
| `fleet_tab.driver_loop` | Line 505 — wrap the `for r in rows` loop | **Critical N+1**: 100× `get_driver_name_for_truck` |
| `fleet_tab.chart` | Line 561 — wrap `_draw_charts` | Chart render |
| `fleet_tab.alerts` | Line 601 — wrap `_refresh_alerts` | Alert list |
| `fleet_tab.kpi_rebuild` | Line 291 — wrap `_rebuild_kpi_strip` | KPI card destroy + recreate |
| `fleet_tab.wakeup` | Line 173 — `wakeup()` | Wakeup from tab switch |

**Estimated times**:
- `fleet_tab.driver_loop`: **500–1500 ms** — 100 individual SQL `SELECT ... WHERE truck_id = ?` calls
- `fleet_tab.refresh`: 700–2500 ms (dominated by N+1)
- `fleet_tab.kpi_rebuild`: 30–80 ms

---

### 2.3 RoutePlanner (Critical: N+1)
**File**: `ui/views/route_planner_view.py`

| Label | Where to add | What it measures |
|-------|-------------|-----------------|
| `route_planner.load_trucks` | Line 878 — wrap `_load_trucks` | Truck combo rebuild + **N+1 slot queries** |
| `route_planner.slot_loop` | Line 889 — wrap the `for row in rows` loop | `get_next_available_slot` per truck |
| `route_planner.render_stops` | Line 929 — wrap `_render_stops_list` | WaypointRow widget destroy + recreate |

**Estimated times**:
- `route_planner.slot_loop`: **400–800 ms** — `get_next_available_slot` for each truck
- `route_planner.load_trucks`: 500–1000 ms
- `route_planner.render_stops`: 50–200 ms

---

### 2.4 FleetTracking (High: widget rebuild)
**File**: `ui/views/fleet_tracking_view.py`

| Label | Where to add | What it measures |
|-------|-------------|-----------------|
| `tracking.poll_fetch` | Line 520 — wrap `_fetch_positions` | Background HTTP fetch to tracking API |
| `tracking.apply_update` | Line 540 — wrap `_apply_update` | Map markers + vehicle list rebuild |
| `tracking.refresh_list` | Line 486 — wrap `_refresh_vehicle_list` | **Widget destroy + recreate** for all vehicles |
| `tracking.detail_panel` | Line 389 — wrap `_show_detail_panel` | Detail panel rebuild |

**Estimated times**:
- `tracking.poll_fetch`: 200–2000 ms (network-dependent)
- `tracking.apply_update`: 50–200 ms
- `tracking.refresh_list`: 40–150 ms (delete + create ~50 vehicle rows × ~40 widgets)

---

### 2.5 AnalyticsView (High: eager load)
**File**: `ui/views/analytics/__init__.py`

| Label | Where to add | What it measures |
|-------|-------------|-----------------|
| `analytics.load_tab_financial` | In `_load_tab` (line 159) — wrap `tab.refresh()` per tab | Individual tab render time |
| `analytics.load_tab_fleet` | Same pattern | — |
| `analytics.load_tab_route` | — | — |
| `analytics.load_tab_client` | — | — |
| `analytics.load_tab_driver` | — | — |
| `analytics.load_tab_document` | — | — |
| `analytics.total_load` | Wrap `_start_loading` (line 108) or `_load_tab` completion | Total 6-tab load time |

**Estimated times** (per tab, with Plotly SVG renders):
- Financial tab: 300–2000 ms (5+ chart widgets)
- Fleet tab: 300–1800 ms
- Route tab: 300–1500 ms
- Client tab: 300–1500 ms
- Driver tab: 300–1200 ms
- Document tab: 200–800 ms
- **Total eager load**: 1800–9000 ms (staggered but sequential)

---

### 2.6 Other Views (quick additions)

| View | File | Key method | Label |
|------|------|-----------|-------|
| DispatchBoard | `ui/views/dispatch_board_view.py` | `refresh()` | `dispatch.refresh` |
| ClientWorkspace | `ui/views/client_workspace/` | `refresh()` | `client.refresh` |
| GeneratorsView | `ui/views/generators_view.py` | `refresh()` | `generators.refresh` |
| MaintenanceControl | `ui/views/maintenance_control_panel.py` | `refresh()` | `maint.refresh` |
| HistoryView | `ui/views/history_view.py` | `refresh()` | `history.refresh` |

---

## 3. Instrumentation Implementation

### Pattern to add to each method:

```python
from ui.performance_timer import PerfTimer

def refresh(self) -> None:
    with PerfTimer("view_label.refresh"):
        # existing refresh body
        ...
```

### For N+1 loops, instrument the loop body:

```python
# In FleetTab._load_table_and_kpis (line 503-508):
with PerfTimer("fleet_tab.driver_loop"):
    for r in rows:
        driver_name = self._dta_service.get_driver_name_for_truck(r["id"])
        ...
```

---

## 4. Baseline Collection Protocol

1. **Launch app** with `OPERION_PERF_LOG=1` environment variable
2. **Navigate to each view** sequentially (Overview → Fleet → Route Planner → Tracking → Analytics → others)
3. **Wait 5 seconds** on each view to ensure full render completion
4. **Call `timing_report()`** via debug console or log dump
5. **Save report** as `perf_baseline_YYYYMMDD_HHMM.txt`
6. **Repeat 3×** and average for stable measurements

---

## 5. Expected Baseline Output Format

```
=== Perf Timing Report ===
Label                               Count    Avg(ms)   Min(ms)   Max(ms)
overview.refresh                      9        324       210       587
overview.kpi                          9        142        89       280
overview.chart                        5        340       195       620
fleet_tab.refresh                     9        1850      1200      3100
fleet_tab.driver_loop                 9        1100       800      1800
fleet_tab.chart                       9        180       120       290
route_planner.load_trucks             9        780       600      1200
route_planner.slot_loop               9        650       480       980
route_planner.render_stops            9         95        60       180
tracking.apply_update                15         85        40       170
tracking.refresh_list                15         62        35       120
analytics.load_tab_financial          3       1800      1200      3100
analytics.load_tab_fleet              3       1500       900      2600
...
```

---

## 6. Success Criteria for Phase 1

- [ ] All 10+ timing labels present in report
- [ ] At least 3 samples per label (for statistical significance)
- [ ] All times recorded in milliseconds with <1ms precision
- [ ] Report file written to `logs/` directory
- [ ] Largest bottlenecks identified and ranked (for Phase 2 triage)
