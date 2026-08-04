# Phase 3–7: UI Optimization Execution Plan

---

## Phase 3: Fixer Tasks — Optimization

### Dependencies Between Fixes
```
Task C1 (DB indexes) ───────────────────────────────────────> can be done first, no deps
Task C2 (LIKE→range query) ─────────────────────────────────> can be done first, no deps
Task C3 (autocommit fix) ───────────────────────────────────> can be done first, no deps
Task C4 (DriverTruckService batch) ─────────────────────────> depends on step 1 (no schema change)
Task C5 (FleetTab async) ───────────────────────────────────> depends on C4
Task C6 (ConflictService batch) ────────────────────────────> independent
Task C7 (RoutePlanner async) ───────────────────────────────> depends on C6
Task C8 (OverviewView widget reuse) ────────────────────────> independent
Task C9 (OverviewView async data) ──────────────────────────> independent
Task C10 (FleetTab KPI reuse) ──────────────────────────────> independent
Task C11 (FleetTracking diff update) ───────────────────────> independent
Task C12 (Analytics lazy tabs) ─────────────────────────────> independent
Task C13 (Generators combo reuse) ──────────────────────────> independent
Task C14 (ClientWorkspace chart staleness) ─────────────────> independent
```

---

### 🔴 Task C1: Add Missing Composite Indexes

**Type**: Database migration
**Severity**: 🔴 Critical
**Dependencies**: None (standalone)

**What to do**:
Create a new Alembic migration adding these 4 indexes.

**SQL**:
```sql
-- Migration upgrade:
CREATE INDEX IF NOT EXISTS idx_trips_company_status ON trips(company_id, status);
CREATE INDEX IF NOT EXISTS idx_trips_company_created ON trips(company_id, created_at);
CREATE INDEX IF NOT EXISTS idx_trucks_company_status ON trucks(company_id, status);
CREATE INDEX IF NOT EXISTS idx_invoices_company_status ON invoices(company_id, status);

-- Migration downgrade:
DROP INDEX IF EXISTS idx_trips_company_status;
DROP INDEX IF EXISTS idx_trips_company_created;
DROP INDEX IF EXISTS idx_trucks_company_status;
DROP INDEX IF EXISTS idx_invoices_company_status;
```

**Verification**:
Run `EXPLAIN QUERY PLAN SELECT ... WHERE company_id = ? AND status = ?` — should show index usage.

---

### 🔴 Task C2: Fix LIKE→Range Query in get_kpi_stats

**Type**: SQL query optimization
**Severity**: 🔴 Critical
**Dependencies**: None (standalone)
**File**: `repositories/analytics_repository.py`
**Lines**: 138–173

**What to change**:

**Current (line 147)**:
```python
FROM trips WHERE created_at LIKE ? {self._company_filter()}
""", (f"%{current_month}%",) + self._company_params())
```

**Replace with**:
```python
FROM trips WHERE created_at >= ? AND created_at < ? {self._company_filter()}
""", (
    f"{current_month}-01",
    f"{_next_month(current_month)}-01",
) + self._company_params())
```

**Add helper** at module level:
```python
def _next_month(ym: str) -> str:
    """Return YYYY-MM of the month after *ym* (YYYY-MM)."""
    y, m = int(ym[:4]), int(ym[5:7])
    if m == 12:
        return f"{y+1}-01"
    return f"{y}-{m+1:02d}"
```

**Verification**:
Observe `EXPLAIN QUERY PLAN` output — should switch from `SCAN` to `SEARCH USING INDEX`.

---

### 🟡 Task C3: Fix PostgreSQL autocommit=True

**Type**: Database configuration
**Severity**: 🟡 Moderate
**Dependencies**: None (standalone)
**File**: `database/connection_pool.py`
**Lines**: 229, 248

**What to change**:

In `get_connection()` (line 229):
```python
# Change:
conn.autocommit = True
# To:
conn.autocommit = False
```

In `get_cached_connection()` (line 248):
```python
# Change:
conn.autocommit = True
# To:
conn.autocommit = False
```

**CRITICAL follow-up**: Audit ALL repository write methods to ensure they call `conn.commit()` after mutations. Search for:
```
grep -r "_execute(" repositories/ | grep "commit"
```

Every write must have `commit=True` or explicit commit. `BaseRepository._execute()` already supports `commit=True` parameter — verify all callers use it correctly.

**Verification**:
Run integration tests; check that multi-step operations (create trip + update truck status) are atomic — rollback on failure.

---

### 🔴 Task C4: DriverTruckService — Add Batch Query to Eliminate N+1

**Type**: Service/repository enhancement
**Severity**: 🔴 Critical
**Dependencies**: None (new method, no existing callers broken)
**Files**:
- `repositories/driver_truck_assignment_repository.py` — add `get_driver_names_for_trucks()`
- `services/driver_truck_service.py` — add `get_driver_names_for_trucks()`

**What to do**:

**Step 1 — Repository** (`repositories/driver_truck_assignment_repository.py`):
Add method:
```python
def get_driver_names_for_trucks(self, truck_ids: list[int]) -> dict[int, str]:
    """Return {truck_id: driver_name} mapping for a batch of trucks."""
    if not truck_ids:
        return {}
    placeholders = ", ".join("?" for _ in truck_ids)
    rows = self._fetchall(
        f"""SELECT da.truck_id, d.name
            FROM driver_truck_assignments da
            JOIN drivers d ON da.driver_id = d.id
            WHERE da.truck_id IN ({placeholders})
              AND da.active = 1"""
        , tuple(truck_ids)
    )
    return {row["truck_id"]: row["name"] for row in rows}
```

**Step 2 — Service** (`services/driver_truck_service.py:480`):
Add method:
```python
def get_driver_names_for_trucks(self, truck_ids: list[int]) -> dict[int, str]:
    """Batch version — one query for many trucks."""
    return self._repo.get_driver_names_for_trucks(truck_ids)
```

**Verification**:
Call with test truck IDs; verify output is `{int: str}` dict.

---

### 🔴 Task C5: FleetTab — Async Loading + N+1 Fix

**Type**: View refactor
**Severity**: 🔴 Critical
**Dependencies**: Task C4 (batch query method)
**File**: `ui/views/fleet_tab/fleet_tab.py`

**What to change**:

**Step 1 — Replace N+1 loop** (lines 503–508):
```python
# Current (N+1):
driver_name = (
    self._dta_service.get_driver_name_for_truck(r["id"])
    if self._dta_service is not None else None
) or t("fleet.table_driver_unassigned")

# Fix (batch):
pass  # See step 2 — this moves to on_result callback
```

**Step 2 — Wrap refresh() in WorkerPool** (line 482):
```python
def refresh(self) -> None:
    """Reload all truck data asynchronously."""
    self._show_loading()
    WorkerPool.run(
        fn=self._fetch_data,
        on_result=self._on_data_loaded,
        on_error=self._on_refresh_error,
    )

def _fetch_data(self) -> dict:
    """Background: fetch trucks + batch driver names."""
    rows = self.service.get_trucks()
    # BATCH: one query for all driver names
    truck_ids = [r["id"] for r in rows]
    driver_map = {}
    if self._dta_service and truck_ids:
        driver_map = self._dta_service.get_driver_names_for_trucks(truck_ids)
    return {"rows": rows, "driver_map": driver_map}

def _on_data_loaded(self, data: dict) -> None:
    """GUI thread: populate table + KPIs + chart."""
    self._hide_loading()
    rows = data["rows"]
    driver_map = data.get("driver_map", {})

    # Populate table (using batch driver map)
    table_rows = []
    for r in rows:
        driver_name = driver_map.get(r["id"]) or t("fleet.table_driver_unassigned")
        table_rows.append({...})  # existing mapping code
    self._table.set_data(table_rows)

    # Update KPIs
    self._update_kpi_values(rows)

    # Chart
    self._draw_charts(rows)
    self._refresh_alerts()
    self._filter_table()

def _on_refresh_error(self, error: str) -> None:
    self._hide_loading()
    QMessageBox.critical(self, t("main.error_title"), f"Load failed: {error}")
```

**Step 3 — Add `_update_kpi_values`** (extract from `_load_table_and_kpis`, lines 536–555):
```python
def _update_kpi_values(self, rows: list[dict]) -> None:
    """Update KPI card text values without destroying widgets."""
    total = len(rows)
    active = sum(1 for r in rows if r.get("active_status") in (1, True))
    if "kpi_total" in self._kpi_value_labels:
        self._kpi_value_labels["kpi_total"].setText(str(total))
    if "kpi_active" in self._kpi_value_labels:
        self._kpi_value_labels["kpi_active"].setText(str(active))
    # ... rest of KPI updates
```

**Verification**:
1. Open Fleet Tab — skeleton shows immediately
2. Data populates within 200ms (no N+1)
3. No UI freeze during load

---

### 🔴 Task C6: ConflictService — Add Batch Slot Query

**Type**: Service enhancement
**Severity**: 🔴 Critical
**Dependencies**: None (new method)
**Files**:
- `services/conflict_service.py` — add `get_next_available_slots_for_trucks()`

**What to do**:

**Current `get_next_available_slot(plate_number: str)`** — queries per truck.

**Add new method**:
```python
def get_next_available_slots_for_trucks(
    self, truck_plates: list[str]
) -> dict[str, str | None]:
    """Return {plate_number: next_available_time_or_None} for batch of trucks.
    
    Returns None for plates with no conflicts."""
    if not truck_plates:
        return {}
    placeholders = ", ".join("?" for _ in truck_plates)
    rows = self._fetchall(
        f"""SELECT t.plate_number, MIN(trip.end_date) as next_available
            FROM trucks t
            LEFT JOIN trips trip ON t.id = trip.truck_id
              AND trip.status NOT IN ('Delivered', 'Cancelled', 'Paid')
            WHERE t.plate_number IN ({placeholders})
            GROUP BY t.plate_number""",
        tuple(truck_plates)
    )
    return {r["plate_number"]: r["next_available"] for r in rows}
```

(Adjust SQL to match actual schema — this is a template.)

---

### 🔴 Task C7: RoutePlanner — Async Truck Loading + N+1 Fix

**Type**: View refactor
**Severity**: 🔴 Critical
**Dependencies**: Task C6 (batch slot query)
**File**: `ui/views/route_planner_view.py`
**Lines**: 878–903

**What to change**:

**Step 1 — Async `_load_trucks()`**:
```python
def _load_trucks(self) -> None:
    """Load trucks asynchronously — show skeleton or spinner."""
    self._show_loading()  # Use BaseView skeleton
    WorkerPool.run(
        fn=self._fetch_trucks_with_slots,
        on_result=self._on_trucks_loaded,
        on_error=self._on_trucks_error,
    )

def _fetch_trucks_with_slots(self) -> dict:
    """Background: fetch all trucks + batch slot information."""
    rows = self.fleet_service.get_trucks() if self.fleet_service else []
    trucks = []
    plates = []
    for row in rows:
        trucks.append(row)
        plates.append(row["plate_number"])

    # BATCH: one query for all slot availability
    slot_map = {}
    if self._conflict_service and plates:
        slot_map = self._conflict_service.get_next_available_slots_for_trucks(plates)

    return {"trucks": trucks, "slot_map": slot_map}

def _on_trucks_loaded(self, data: dict) -> None:
    """GUI thread: populate truck combo from batch data."""
    self._hide_loading()
    trucks = data["trucks"]
    slot_map = data.get("slot_map", {})

    self._trucks_map = {}
    self._truck_label_to_id = {}
    self.truck_combo.clear()
    for row in trucks:
        truck_id = str(row["id"])
        plate = row["plate_number"]
        label = f"{plate} - {row.get('model') or ''}"
        next_slot = slot_map.get(plate)
        if next_slot:
            label = f"{label}  [{t('dispatch_board.available_from').format(next_slot)}]"
        self._truck_label_to_id[label] = truck_id
        self._trucks_map[truck_id] = row
        self.truck_combo.addItem(label, truck_id)
    if trucks:
        self.truck_combo.setCurrentIndex(0)
        self._selected_truck_id = self._truck_label_to_id.get(self.truck_combo.currentText())

def _on_trucks_error(self, error: str) -> None:
    self._hide_loading()
    logger.error("Failed to load trucks: %s", error)
```

**Verification**:
1. Open Route Planner — trucks load in background
2. Combo populates without UI freeze
3. All 100+ trucks load in <200ms

---

### 🔴 Task C8: OverviewView — Eliminate KPI Widget Destroy/Recreate

**Type**: View optimization
**Severity**: 🔴 High
**Dependencies**: None
**File**: `ui/views/overview_view.py`

**What to change**:

**Step 1 — Build KPIs once** (modify `_build_kpi_strip`, lines 224–258):

Replace `_rebuild_kpi_strip()` call in `_build_kpi_strip()` with inline creation:

```python
def _build_kpi_strip(self, layout):
    self._kpi_strip = QFrame()
    self._kpi_strip_layout = QHBoxLayout(self._kpi_strip)
    self._kpi_strip_layout.setContentsMargins(0, 0, 0, 0)
    self._kpi_strip_layout.setSpacing(SP["2"])

    self._kpi_value_labels: dict[str, QLabel] = {}
    # Create cards ONCE — never destroy
    for src in self._selected_kpis:
        key = src["key"]
        label = self._kpi_label(src)
        card = CompactKPICard(self._kpi_strip, label=label, value="\u2014")
        self._kpi_value_labels[key] = card.value_label
        self._kpi_strip_layout.addWidget(card, 1)

    layout.addWidget(self._kpi_strip)
```

**Step 2 — Remove `_rebuild_kpi_strip()` method** (lines 236–258):
Delete the entire method.

**Step 3 — Update `_refresh_kpis()` to only set text** (lines 409–420):
This method already does the right thing — only calls `setText()` and `setStyleSheet()` on existing labels. No change needed.

**Step 4 — On i18n change, update labels without destroying cards**:
In `_on_language_changed()`, update label text via `_kpi_value_labels` parent's label widget (if stored).

**Verification**:
1. Open Overview — KPIs render immediately
2. After 30s auto-refresh — no widget creation/destruction visible
3. KPI values update in-place

---

### 🔴 Task C9: OverviewView — Async Data Loading

**Type**: View refactor
**Severity**: 🔴 High
**Dependencies**: None (can be done independently or after C8)
**File**: `ui/views/overview_view.py`

**What to change**:

**Wrap `refresh()` in WorkerPool** (line 384):

```python
def refresh(self):
    """Async refresh — skeleton shown during load."""
    if getattr(self, "_shutting_down", False):
        return
    try:
        self.isVisible()
    except RuntimeError:
        return

    now_ts = datetime.now().timestamp()
    if now_ts - self._last_refresh_ts < 2:
        return
    self._last_refresh_ts = now_ts

    self._show_loading()
    WorkerPool.run(
        fn=self._fetch_all_data,
        on_result=self._on_data_loaded,
        on_error=lambda e: (self._hide_loading(), logger.error("Refresh failed: %s", e)),
    )

def _fetch_all_data(self) -> dict:
    """Background: fetch all dashboard data in one batch."""
    # Merge trip queries to avoid duplicate DB calls
    # Active trips: get_all(200) + filter
    trips = self._trip_repo.get_all(limit=200) if self._trip_repo else []
    non_active = ("Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced", "LOADING")
    active = [t for t in trips if t.get("status", "") not in non_active]

    # Top trucks
    now = datetime.now()
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    month_end = now.strftime("%Y-%m-%d")
    top_trucks = self._trip_repo.get_top_trucks_by_revenue(
        month_start, month_end, limit=4
    ) if self._trip_repo else []

    # Alerts
    alerts = []
    if self.ops:
        with contextlib.suppress(Exception):
            alerts = self.ops.get_active_alerts(limit=5)

    return {
        "trips": active[:8],
        "active_count": len(active),
        "top_trucks": top_trucks,
        "alerts": alerts[:3],
        "recent": trips[:6],
    }

def _on_data_loaded(self, data: dict) -> None:
    """GUI thread: populate all widgets from pre-fetched data."""
    self._hide_loading()
    self._refresh_kpis()
    self._render_profit_chart()
    self._populate_trips(data.get("trips", []), data.get("active_count", 0))
    self._populate_alerts(data.get("alerts", []))
    self._populate_top_trucks(data.get("top_trucks", []))
    self._populate_activity(data.get("recent", []))
```

**Extract widget population from `_refresh_*` methods** into `_populate_*` methods that accept data parameter instead of querying DB themselves. `_refresh_*` methods become thin wrappers or are removed.

**Verification**:
1. Open Overview — skeleton visible for <500ms
2. All sections populate simultaneously (not sequentially)
3. No UI freeze

---

### 🟠 Task C10: FleetTab — Eliminate KPI Strip Destroy/Recreate

**Type**: View optimization  
**Severity**: 🟠 High
**Dependencies**: None (standalone)
**File**: `ui/views/fleet_tab/fleet_tab.py`
**Lines**: 291–311

**What to change**:

**Step 1 — Build KPIs once** (modify `_build_kpi_strip`, line 287):
```python
def _build_kpi_strip(self, layout: QVBoxLayout) -> None:
    self._kpi_strip = QFrame()
    self._kpi_strip_layout = QHBoxLayout(self._kpi_strip)
    self._kpi_strip_layout.setContentsMargins(SP["3"], 0, SP["3"], SP["2"])
    self._kpi_strip_layout.setSpacing(SP["2"])

    self._kpi_value_labels: dict[str, QLabel] = {}
    # Build ONCE
    kpi_defs = [
        ("kpi_total", "fleet.kpi_total_trucks", "0"),
        ("kpi_active", "fleet.kpi_active", "0"),
        ("kpi_leasing", "fleet.kpi_monthly_rate", "0"),
        ("kpi_alerts", "fleet.kpi_alerts", "0"),
    ]
    for key, title_key, default_val in kpi_defs:
        card = KPICard(self._kpi_strip, t(title_key), default_val)
        val_lbl = card.findChild(QLabel, "kpi-value")
        if val_lbl is not None:
            self._kpi_value_labels[key] = val_lbl
        self._kpi_strip_layout.addWidget(card, 1)

    layout.addWidget(self._kpi_strip)
```

**Step 2 — Delete `_rebuild_kpi_strip()`** (lines 291–311):
Remove this method entirely.

**Step 3 — Rename `_load_table_and_kpis` → `_update_kpi_values`** (keep only KPI update logic from lines 536–555):
The KPI part already uses `setText()` — keep it. No other references to `_rebuild_kpi_strip` exist.

**Verification**:
KPI cards persist across refreshes. Values update without flicker.

---

### 🟠 Task C11: FleetTracking — Diff-based Vehicle List Update

**Type**: View optimization
**Severity**: 🟠 High
**Dependencies**: None (standalone)
**File**: `ui/views/fleet_tracking_view.py`
**Lines**: 486–508

**What to change**:

Replace `_refresh_vehicle_list()` with diff-based update:

```python
def _refresh_vehicle_list(self, positions: list[VehiclePosition]) -> None:
    """Update vehicle list — add new rows, remove gone, update existing."""
    new_names = {p.name for p in positions}
    new_positions = {p.name: p for p in positions}

    # Remove rows for vehicles that disappeared
    to_remove = []
    for name, row_widget in self._vehicle_rows.items():
        if name not in new_names:
            to_remove.append(name)
    for name in to_remove:
        widget = self._vehicle_rows.pop(name)
        self._vehicle_list_layout.removeWidget(widget)
        widget.deleteLater()

    # Update existing, add new
    for pos in sorted(positions, key=lambda p: p.name.lower()):
        if pos.name in self._vehicle_rows:
            # Update existing row in-place
            self._update_vehicle_row(self._vehicle_rows[pos.name], pos)
        else:
            # Add new vehicle
            truck_id = fleet_tracking_service.match_to_truck(pos)
            row = self._build_vehicle_row_widget(pos, truck_id)
            self._vehicle_rows[pos.name] = row
            self._vehicle_list_layout.addWidget(row)

    self._updated_lbl.setText(datetime.now().strftime("%H:%M:%S"))
```

**Add `_vehicle_rows` to `__init__()`**:
```python
self._vehicle_rows: dict[str, QFrame] = {}
```

**Add `_update_vehicle_row()`**:
```python
def _update_vehicle_row(self, row: QFrame, position: VehiclePosition) -> None:
    """Update an existing vehicle row's text in-place."""
    # Find the name label and detail label children and update text
    labels = row.findChildren(QLabel)
    if len(labels) >= 2:
        labels[0].setText(position.name)  # name label
        labels[1].setText(self._vehicle_detail_text(position))  # detail label
```

**Refactor `_build_vehicle_row` → `_build_vehicle_row_widget`**:
Return the widget instead of adding it to layout directly (step 2 in `_refresh_vehicle_list` handles addition).

**Verification**:
1. Poll cycle runs — only changed vehicles trigger widget creation
2. Existing vehicle rows' text updates in-place
3. No flicker on position updates

---

### 🟠 Task C12: AnalyticsView — Lazy-load Tabs

**Type**: View refactor
**Severity**: 🔴 High
**Dependencies**: None (standalone)
**File**: `ui/views/analytics/__init__.py`

**What to change**:

**Step 1 — Replace eager `_start_loading()` with lazy single-tab load** (lines 108–123):
```python
def _start_loading(self) -> None:
    """Load only the first (visible) tab — rest are lazy."""
    if self._load_started:
        return
    self._load_started = True
    # Load only the initially visible tab (index 0)
    self._load_tab(0)
```

**Step 2 — Wire `currentChanged` to trigger lazy load** (line 143 already has signal):
```python
self._tab_widget.currentChanged.connect(self._on_tab_changed)
```

**Replace `_on_tab_changed`** (line 291):
```python
def _on_tab_changed(self, index: int) -> None:
    """Lazy-load tab when user clicks it."""
    if index < 0 or index >= len(TAB_DEFS):
        return
    # Load tab if not yet created
    if index not in self._tabs:
        self._loading_overlay.show()
        self._loading_overlay.set_progress(0, 1)
        self._load_tab(index)
        self._loading_overlay.mark_done()
        self._loading_overlay.hide()
```

**Step 3 — Remove `_tab_load_delay` logic**:
Delete lines 72 (`_tab_load_delay = 50`), lines 117–123 (timer creation loop).

**Verification**:
1. Open Analytics — only Financial tab renders
2. Click Fleet tab → loads on demand
3. Total startup time drops from ~3s to ~0.5s

---

### 🟡 Task C13: GeneratorsView — In-place Combo Update

**Type**: View optimization
**Severity**: 🟡 Moderate
**Dependencies**: None
**File**: `ui/views/generators_view.py`

**What to do**:
1. Find the trip combo population method
2. Instead of `clear()` + loop `addItem()`, use dict to track current items
3. On refresh: add new items, remove deleted, skip unchanged

**Pattern**:
```python
# Store current combo items by value
_current = {self.trip_combo.itemData(i): i for i in range(self.trip_combo.count())}
_new = {trip["id"]: trip["display_label"] for trip in trips}

# Remove deleted
for vid in set(_current) - set(_new):
    self.trip_combo.removeItem(_current[vid])

# Add new
for vid in set(_new) - set(_current):
    self.trip_combo.addItem(_new[vid], vid)

# Update existing labels?
# Skip if labels match — QComboBox doesn't need label update unless text changes
```

---

### 🟡 Task C14: ClientWorkspace — Chart Staleness Pattern

**Type**: View optimization
**Severity**: 🟡 Moderate
**Dependencies**: None
**File**: `ui/views/client_workspace/` (main file)

**What to do**:
1. Find the chart render method (similar to OverviewView's `_render_profit_chart`)
2. Add staleness tracking:
   - Store `_last_chart_ts` and `_last_chart_key`
   - On `wakeup()`, check if chart data is < 5 minutes old
   - Skip re-render if fresh

**Pattern** (copy from `overview_view.py:764-771`):
```python
def _render_chart(self, _force: bool = False):
    now = time.time()
    if not _force and self._chart_render_ts and now - self._chart_render_ts < 300:
        return
    self._chart_render_ts = now
    # render chart ...
```

---

## Phase 4: UX Polish Plan

### 4.1 Skeleton States

**Already exists**: `ui/skeleton_widgets.py` with `SkeletonCard`, `SkeletonTable`, `SkeletonChart`, `SkeletonManager`.

**Enhancements needed**:

| View | Skeleton Type | Implementation |
|------|--------------|----------------|
| OverviewView | 3 KPI cards + 1 large chart + 2 list zones | `_show_loading()` shows `SkeletonManager` overlay. Already inherited from BaseView. |
| FleetTab | 4 KPI cards + table skeleton + chart placeholder | Use `SkeletonTable(rows=10, cols=12)` in layout before real data loads |
| RoutePlanner | Map skeleton + stop fields | Map has its own loading state (Leaflet spinner); stop fields show grayed-out inputs |
| FleetTracking | Map skeleton + vehicle list skeleton | `SkeletonCard` rows for vehicle list; map shows "Loading..." overlay |
| Analytics tabs | Chart grid skeletons | Each `PlotlyChartWidget` shows a gray placeholder until `set_figure()` fills it |

### 4.2 Progressive Data Loading

For the OverviewView, load in priority order:
1. **Immediate (0ms)**: KPI card values (cached from `AnalyticsService`)
2. **Fast (200ms)**: Active trips + alert counts + top trucks
3. **Slow (500ms)**: Chart render (Plotly SVG)

### 4.3 Non-blocking Refresh Indicators

Add a thin progress bar at the top of each view that auto-refreshes:
- Show on wakeup
- Pulse animation while loading
- Disappear when data arrives
- Use `QProgressBar` styled as Linear-style thin bar (2px height)

---

## Phase 5: Design System Cleanup

### 5.1 Spacing Normalization

**File**: `ui/design_tokens.py`

**Changes**:
```python
# Line 94 — Change from:
SPACE_3  = 12
# To:
SPACE_3  = 16   # Now 8px-grid compliant

# Line 96 — Change from:
SPACE_5  = 20
# To:
SPACE_5  = 24   # Now 8px-grid compliant
```

**Impact audit** (files using `SP["3"]` and `SP["5"]`):
- `SP["3"]` used in: `fleet_tab.py`, `overview_view.py`, `_tab_base.py`, `fleet_tracking_view.py`, `route_planner_view.py`, `main_window.py`, many more
- Visual impact: 12→16px = 4px extra spacing. Acceptable for most cases. Card margins will be slightly roomier.

**Alternative**: Add new tokens and deprecate old:
```python
SPACE_2_SMALL = 12  # Legacy alias for 12px
SPACE_5_SMALL = 20  # Legacy alias for 20px
```

### 5.2 Border Radius Standardization

**Goal**: Exactly 4 token values everywhere — RADIUS_SM(4), RADIUS_MD(6), RADIUS_LG(8), RADIUS_PILL(100).

**Fix plan** (search-and-replace):

| Find | Replace | Files |
|------|---------|-------|
| `border-radius: 2px` | `border-radius: {RADIUS_SM}px` (4px) | `sidebar.py:306`, `theme_engine.py:867,1051` |
| `border-radius: 3px` | `border-radius: {RADIUS_SM}px` (4px) | `trip_card.py:(8 places)`, `topbar.py:(3 places)`, `dispatch_alerts_panel.py:267`, `cmr_form.py:433`, `cmr_fields.py:635` |
| `border-radius: 9px` | `border-radius: {RADIUS_LG}px` (8px) or keep as `{RADIUS_MD + 3}` | `theme_engine.py:502,1182` |
| `border-radius: 12px` | `border-radius: {RADIUS_XL}px` | `chart_loading_overlay.py:160` |
| `border-radius: 16px` | `border-radius: {RADIUS_XL}px` | `sidebar.py:150` |

**Files per fixer**:
1. `ui/theme_engine.py` — 30+ hardcoded radii → token references
2. `ui/widgets/trip_card.py` — 8 occurrences
3. `ui/widgets/topbar.py` — 3 occurrences
4. `ui/views/cmr_form_view/cmr_form.py` — 5 occurrences
5. `ui/views/cmr_form_view/cmr_fields.py` — 1 occurrence
6. All other files — scattered

### 5.3 Font Size Cleanup

**Replace hardcoded micro-fonts**:

| File:Line | Current | Replace with |
|-----------|---------|--------------|
| `cmr_form.py:151,157,163,227` | `font-size: 7px` | `FONT_SIZE_XS` (10px) |
| `cmr_form.py:433` | `font-size: 8px` | `FONT_SIZE_XS` (10px) |
| `cmr_fields.py:635` | `font-size: 8px` | `FONT_SIZE_XS` (10px) |
| `driver_tab.py:280` | `font-size: 8px` | `FONT_SIZE_XS` (10px) |
| `timeline_panel.py:212` | `font-size: 8px` | `FONT_SIZE_XS` (10px) |
| `receipt_editor/editor_form.py:1505,1566,1571` | `font-size: 8px` | `FONT_SIZE_XS` (10px) — **HTML template** |

**Note**: The receipt_editor uses inline HTML for printing — these may be intentional for fitting content on physical paper. Flag for designer review.

### 5.4 Button Height Alignment

**File**: `ui/design_tokens.py:224`

**Change**:
```python
# From:
BTN_HEIGHT = 32
# To:
BTN_HEIGHT = 38  # Match QSS min-height
```

**File**: `ui/theme_engine.py:338`

No change needed — QSS already has `min-height: 38px`. Token now matches.

### 5.5 Card Border Color Audit

Search for color mismatches in card borders:
```bash
grep -rn "border.*card\|QFrame#stat-card\|QFrame#card" ui/ | grep border
```

The global QSS in `ui/stylesheet.py` uses `COLOR_BORDER_SUBTLE` for cards consistently. Spot-check individual file overrides.

---

## Phase 6: Navigation Rework

### 6.1 Current State

Navigation is flat: 20 items in a single sidebar grouped by category. All views are lazily created on first access (line 371 of `main_window.py`), cached in `_module_cache`, and pre-warmed on startup (lines 401-427).

### 6.2 Workflow-Oriented Proposal

**Current groups**:
```
Overview → Overview, Analytics
Operations → Route Planner, Calculator, Dispatch Board, Tracking, Freight Exchange
Fleet → Fleet, Driver Manager, Clients, Documents, Maintenance, Maintenance Control, Tachograph
Finance → Invoices, History, Route History
Tools → Co-Pilot, Migration Center
```

**Workflow-oriented proposal** (designer decision, not code change):
```
DASHBOARD → Overview, Analytics
DISPATCH → Dispatch Board, Route Planner, Fleet Tracking, Calculator, Freight Exchange
FLEET → Fleet, Driver Manager, Maintenance, Tachograph
CLIENTS → Client Workspace, Document Center
FINANCE → Invoices, History, Route History
ADMIN → Team, Settings, Migration Center, Co-Pilot
```

### 6.3 Quick Wins (no full redesign)

1. **Reorder sidebar groups** by frequency of use — put DISPATCH above FLEET
2. **Add badge counts** for active trips, alerts, unpaid invoices
3. **Add "Recent" section** — last 3 visited views for quick navigation
4. **Keyboard shortcuts** already exist (Ctrl+S for Calculator, Ctrl+H for History) — add more

---

## Phase 7: Verification Plan

### 7.1 Pass Criteria

| Metric | Target | How to Measure |
|--------|--------|---------------|
| FleetTab load time | <300ms | `PerfTimer` on `fleet_tab.refresh` |
| FleetTab N+1 queries | 1 query (not 100) | DB query log or SQLAlchemy/psycopg2 logging |
| RoutePlanner truck load | <300ms | `PerfTimer` on `route_planner.load_trucks` |
| OverviewView KPI refresh | <50ms | `PerfTimer` on `overview.kpi` |
| FleetTracking widget churn | 0 destroys on update | Check `deleteLater()` calls in `_refresh_vehicle_list` |
| Analytics startup | <1s for visible tab | `PerfTimer` on `analytics.total_load` |
| All views: no main-thread DB queries | ✅ | Lint rule: disallow DB access outside `WorkerPool.run()` |
| LIKE-based month query eliminated | ✅ | Grep for `LIKE '%2026-` in `analytics_repository.py` |
| autocommit=False for PG pool | ✅ | Check `connection_pool.py` line 229 |
| Composite indexes created | ✅ | `EXPLAIN QUERY PLAN` shows index usage |
| No widget destroy/recreate | ✅ | Audit `deleteLater()` calls in refresh paths |
| Button height token = QSS height | ✅ | `BTN_HEIGHT == 38`, `min-height: 38px` |
| All border-radius from tokens | ✅ | Grep for `border-radius: \d+px` — should be 0 occurrences |
| Font size >= 10px everywhere | ✅ | Grep for `font-size: [789]px` — should be 0 occurrences |

### 7.2 After-Report Template

```markdown
# UI Performance Optimization — After Report

## Date: YYYY-MM-DD
## Tester: [Name]
## Environment: [local/remote], [SQLite/PostgreSQL]

## Results

### FleetTab
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Refresh time (ms) | 1850 | ??? | — |
| DB queries per refresh | 102 | ??? | — |
| N+1 queries eliminated | — | ✅/❌ | — |
| Skeleton shown | No | ✅/❌ | — |

### RoutePlanner
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Truck load time (ms) | 780 | ??? | — |
| N+1 queries eliminated | — | ✅/❌ | — |

### OverviewView
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| KPI rebuild time (ms) | 142 | ??? | — |
| Widget destroy eliminated | — | ✅/❌ | — |

### AnalyticsView
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Startup time (ms) | 3000 | ??? | — |
| Tabs loaded at startup | 6 | ??? | — |

### FleetTracking
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Vehicle row churn (per poll) | 50 destroyed, 50 created | ??? | — |

### Database
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| LIKE month query | EXISTS | ✅/❌ | — |
| Composite indexes | 0 | 4 | — |
| autocommit | True | ✅/❌ | — |

### Design System
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Hardcoded border-radius (count) | 40+ | ??? | — |
| Font sizes <10px (count) | 11 | ??? | — |
| Button height mismatch | 32 vs 38px | ✅/❌ | — |

## Issues Found
1. [List any regressions or problems]

## Screenshots
[Before/after screenshots of key views]
```
