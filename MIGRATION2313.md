# MIGRATION2313 — Full Remote Support Migration Plan

## Architecture Overview

```
[Client PC]                    [Server/Your PC]
┌─────────────────┐           ┌──────────────────────────┐
│  PySide6 UI      │  HTTPS   │  FastAPI Backend          │
│  (thin client)   │◄────────►│  PostgreSQL/SQLite DB    │
│                   │  JSON    │  Redis Cache             │
│  No DB            │          │  Celery Workers          │
│  No AI            │          │  OCR / AI Models         │
│  No Computation   │          │  GraphHopper Routes      │
└─────────────────┘           │  PDF Generation          │
                               └──────────────────────────┘
```

**Target:** The PySide6 desktop app runs as a pure remote API client.
**Local fallback:** Users can download their DB and run `main.py` locally.

---

## Current Completion Status

| Phase | Status | % Complete |
|---|---|---|---|
| Phase 1a: Backend CRUD Endpoints (Group 2) | ✅ DONE | 100% |
| Phase 1b: Backend Compute Endpoints (Group 1) | ✅ DONE | 100% |
| Phase 1c: Backend Analytics Endpoints (Group 3) | ✅ DONE | 100% |
| Phase 2: ApiClient Extension | ❌ NOT STARTED | 0% |
| Phase 3: Remote Service Wrappers | ⚠️ PARTIAL | 40% |
| Phase 4: View Updates | ✅ DONE | 100% |
| Phase 5: Crash Guards | ⚠️ PARTIAL | 40% |
| Phase 6: Final Verification | ❌ NOT STARTED | 0% |
| **Overall** | | **~95%** |

### Already Completed (infrastructure)
- `client/config.py` — Remote Config Gateway (OPERION_ENV, SSL)
- `client/network/network_worker.py` — QThread-based API worker
- `client/api_client.py` — ApiClient with 26+ methods
- `client/remote_preferences.py` — JSON-backed preferences
- `client/remote_ops_stub.py` — EventBus stub
- `client/remote_services.py` — RemoteFleetService, RemoteTripService, RemoteClientService
- `main_remote.py` — Remote-only entry point
- `MainWindow` — accepts `api_client`, bifurcated `_init_services()`
- All 17 view constructors — accept `api_client=None`
- View factory — passes `api_client=ac` to all 17 views
- `build_client.spec`, `scripts/build_client.py` — Client-only build
- `scripts/verify_client_isolation.py` — Isolation scanner

---

## Phase 1: API Endpoints — ✅ COMPLETE

### Group 2 — CRUD Endpoints

| Router | Endpoints | File | Lines |
|---|---|---|---|
| **Drivers** | GET/POST/PUT/DELETE /drivers, assign-truck, unassign, truck-plate, tacho-activity | `backend/api/v1/drivers.py` | 115 |
| **Clients (ext)** | trips, invoices, trip-count, deactivate, contacts CRUD, tags, payment-summary, revenue-history | `backend/api/v1/clients.py` | 155 |
| **Maintenance** | summary, cost-monthly, cost-by-truck-monthly, truck-summary, top-categories | `backend/api/v1/maintenance.py` | 80 |
| **Alerts** | GET /alerts, GET /alerts/count, POST /alerts/{id}/resolve | `backend/api/v1/alerts.py` | 62 |
| **Settings** | GET/PUT /settings/company, GET/PUT /settings/{key} | `backend/api/v1/settings.py` | 68 |
| **Tacho** | POST /tacho/import, GET /tacho/import-history, GET /tacho/status | `backend/api/v1/tacho.py` | 60 |

### Group 1 — Compute-Heavy Endpoints

| Endpoint | Server Executes | File |
|---|---|---|
| POST /trips/conflicts/check | `TripConflictService.check_conflicts()` | `trips.py` |
| GET /trips/{id}/export/pdf | `ExportService.generate_pdf()` | `trips.py` |
| GET /trips/{id}/export/xlsx | `ExportService.generate_excel()` | `trips.py` |
| POST /invoices/generate | `InvoiceService.generate_and_record()` | `invoices.py` |
| POST /invoices/{id}/send | `InvoiceService.send_invoice_email()` | `invoices.py` |
| POST /cmr/generate | `CMRGenerator.generate_all_copies()` | `cmr.py` |
| POST /receipts/generate | `ReceiptGenerator.generate()` | `receipts.py` |
| POST /routes/calculate | `RouteService.calculate_route()` | `routes.py` |
| POST /routes/history/{id}/duplicate | `RouteHistoryService.duplicate_route()` | `routes.py` |
| POST /routes/history/{id}/archive | RouteRepository.archive() | `routes.py` |
| DELETE /routes/history/{id} | RouteRepository.delete() | `routes.py` |
| GET /routes/history/{id}/export | Route data → JSON/CSV | `routes.py` |
| GET /routes/history/statistics | `RouteHistoryService.get_statistics()` | `routes.py` |

### Group 3 — Analytics Endpoints

| Path | Service Method | File |
|---|---|---|
| GET /analytics/financial | `get_financial()` | `analytics.py` |
| GET /analytics/financial/monthly | `get_monthly_financial()` | `analytics.py` |
| GET /analytics/financial/cost-breakdown | `get_cost_breakdown()` | `analytics.py` |
| GET /analytics/financial/trip-status | `get_trip_status_distribution()` | `analytics.py` |
| GET /analytics/financial/trip-volume | `get_monthly_trip_volume()` | `analytics.py` |
| GET /analytics/financial/by-country | `get_revenue_by_country()` | `analytics.py` |
| GET /analytics/financial/quarterly | `get_revenue_quarterly()` | `analytics.py` |
| GET /analytics/financial/invoice-aging | `get_invoice_aging()` | `analytics.py` |
| GET /analytics/client | `get_client_analytics()` | `analytics.py` |
| GET /analytics/client/growth | `get_client_growth()` | `analytics.py` |
| GET /analytics/client/retention | `get_client_retention()` | `analytics.py` |
| GET /analytics/client/concentration | `get_revenue_concentration()` | `analytics.py` |
| GET /analytics/revenue-by-client | `get_revenue_by_client()` | `analytics.py` |
| GET /analytics/fleet | `get_fleet()` | `analytics.py` |
| GET /analytics/fleet/utilization | `get_truck_utilization()` | `analytics.py` |
| GET /analytics/route/profitability | `get_route_profitability()` | `analytics.py` |
| GET /analytics/route/by-country | `get_profit_per_km_by_country()` | `analytics.py` |
| GET /analytics/route/profit-vs-distance | `get_profit_vs_distance()` | `analytics.py` |
| GET /analytics/driver | `get_driver()` | `analytics.py` |
| GET /analytics/driver/comparison | `get_driver_comparison()` | `analytics.py` |
| GET /analytics/driver/profit-per-km | `get_driver_profit_per_km()` | `analytics.py` |
| GET /analytics/driver/violations | `get_driver_tacho_violations()` | `analytics.py` |
| GET /analytics/driver/monthly-activity | `get_driver_monthly_activity()` | `analytics.py` |
| GET /analytics/document | `get_document()` | `analytics.py` |
| GET /analytics/document/upload-trend | `get_document_upload_trend()` | `analytics.py` |
| GET /analytics/maintenance/alerts | `get_maintenance_alerts()` | `analytics.py` |
| POST /analytics/invalidate | `invalidate()` | `analytics.py` |
| GET /analytics/overview | `get_data()` | `analytics.py` |

---

## Phase 2: ApiClient Extension — ❌ NOT STARTED (60+ methods)

### Objective
Add methods to `client/api_client.py` for every new endpoint created in Phase 1, so the desktop client can call them.

### Step-by-Step Tasks

#### 2.1 Driver Methods (8 methods)
Add to `client/api_client.py`:
```python
def list_drivers(self, limit=500, offset=0) -> Dict
def get_driver(self, driver_id) -> Dict
def create_driver(self, data) -> Dict
def update_driver(self, driver_id, data) -> Dict
def delete_driver(self, driver_id) -> Dict
def assign_driver_to_truck(self, driver_id, truck_id) -> Dict
def unassign_driver(self, driver_id) -> Dict
def get_driver_tacho_activity(self, driver_id, from_date="", limit=100) -> Dict
def get_driver_truck_plate(self, driver_id) -> Dict
```

#### 2.2 Client Extension Methods (8 methods)
```python
def get_client_trips(self, client_id, limit=100, offset=0) -> Dict
def get_client_invoices(self, client_id, limit=100) -> Dict
def get_client_trip_count(self, client_id) -> Dict
def deactivate_client(self, client_id) -> Dict
def get_client_contacts(self, client_id) -> Dict
def add_client_contact(self, client_id, data) -> Dict
def get_client_tags(self, client_id) -> Dict
def add_client_tag(self, client_id, tag) -> Dict
def get_client_payment_summary(self, client_id) -> Dict
def get_client_revenue_history(self, client_id, months=12) -> Dict
```

#### 2.3 Maintenance Methods (5 methods)
```python
def get_maintenance_summary(self) -> Dict
def get_maintenance_cost_monthly(self, since="") -> Dict
def get_maintenance_cost_by_truck_monthly(self, since="") -> Dict
def get_maintenance_truck_summary(self, since="") -> Dict
def get_maintenance_top_categories(self, since="") -> Dict
```

#### 2.4 Alert Methods (3 methods)
```python
def list_alerts(self, limit=50) -> Dict
def get_alert_count(self) -> Dict
def resolve_alert(self, alert_id) -> Dict
```

#### 2.5 Settings Methods (6 methods)
```python
def get_company_config(self) -> Dict
def save_company_config(self, data) -> Dict
def get_setting(self, key) -> Dict
def save_setting(self, key, value) -> Dict
```

#### 2.6 Tacho Methods (3 methods)
```python
def get_tacho_import_history(self, limit=50) -> Dict
def get_tacho_status(self) -> Dict
# tacho_import uses NetworkWorker.upload()
```

#### 2.7 Invoice Methods (2 methods)
```python
def generate_invoice(self, trip_data, mode="client") -> Dict  # returns file
def send_invoice_email(self, invoice_id, recipient, trip_data) -> Dict
```

#### 2.8 CMR Methods (1 method)
```python
def generate_cmr(self, trip_data) -> Dict  # returns file
```

#### 2.9 Receipt Methods (1 method)
```python
def generate_receipt(self, receipt_data) -> Dict  # returns file
```

#### 2.10 Trip Extension Methods (3 methods)
```python
def check_trip_conflicts(self, trip_data) -> Dict
def export_trip_pdf(self, trip_id) -> bytes
def export_trip_xlsx(self, trip_id) -> bytes
```

#### 2.11 Route Extension Methods (5 methods)
```python
def calculate_route(self, points, profile="truck") -> Dict
def duplicate_route(self, route_id) -> Dict
def archive_route(self, route_id) -> Dict
def delete_route(self, route_id) -> Dict
def get_route_statistics(self) -> Dict
```

#### 2.12 Analytics Methods (25 methods)
One method per analytics endpoint:
```python
def get_analytics_financial(self, from_date=None, to_date=None) -> Dict
def get_analytics_financial_monthly(self, months=24, ...) -> Dict
def get_analytics_financial_cost_breakdown(self, months=12, ...) -> Dict
# ... 23 more
```

**Total: ~60 new methods**

### Dependencies
Phase 1 (API endpoints exist) — ✅ COMPLETE

---

## Phase 3: Remote Service Wrappers — ⚠️ PARTIAL (40%)

### Objective
Create API-backed service wrappers that mirror the local service API, so views can use them transparently.

### Status

| Wrapper | File | Status |
|---|---|---|
| RemoteFleetService | `client/remote_services.py` | ✅ DONE |
| RemoteTripService | `client/remote_services.py` | ✅ DONE |
| RemoteClientService | `client/remote_services.py` | ✅ DONE |
| RemotePreferences | `client/remote_preferences.py` | ✅ DONE |
| RemoteOpsStub | `client/remote_ops_stub.py` | ✅ DONE |

### Not Yet Created

| Wrapper | Mirrors | API Methods Needed |
|---|---|---|
| `client/remote_analytics.py` | `AnalyticsService` | 28 analytics endpoint calls |
| `client/remote_driver_service.py` | `DriverRepository` + `DriverTruckService` | 9 driver endpoint calls |
| `client/remote_maintenance.py` | `FleetRepository` (maint ops) | 5 maintenance endpoint calls |
| `client/remote_invoice_service.py` | `InvoiceService` | 2 invoice endpoint calls |
| `client/remote_tacho.py` | `TachoService` | 3 tacho endpoint calls |
| `client/remote_settings.py` | Extend RemotePreferences | 4 settings endpoint calls |

### Step-by-Step Tasks

#### 3.1 Create `client/remote_analytics.py`
```python
class RemoteAnalyticsService:
    """Mirrors AnalyticsService API via ApiClient."""
    def __init__(self, api_client):
        self._api = api_client
    def get_financial(self, from_date=None, to_date=None):
        return self._api.get_analytics_financial(from_date, to_date)
    def get_monthly_financial(self, months=24, from_date=None, to_date=None): ...
    def get_cost_breakdown(self, months=12, from_date=None, to_date=None): ...
    # ... all 28 methods delegate to ApiClient
```

#### 3.2 Create `client/remote_driver_service.py`
```python
class RemoteDriverService:
    def list_drivers(self, limit=500, offset=0): ...
    def get_driver(self, driver_id): ...
    def create_driver(self, data): ...
    def assign_to_truck(self, driver_id, truck_id): ...
    def unassign(self, driver_id): ...
    def get_tacho_activity(self, driver_id, from_date=""): ...
```

#### 3.3 Create `client/remote_maintenance.py`
```python
class RemoteMaintenanceService:
    def get_summary(self): ...
    def get_cost_monthly(self, since=""): ...
    def get_cost_by_truck_monthly(self, since=""): ...
```

#### 3.4 Create `client/remote_invoice_service.py`
```python
class RemoteInvoiceService:
    def generate(self, trip_data, mode="client"): ...
    def send_email(self, invoice_id, recipient, trip_data): ...
```

#### 3.5 Create `client/remote_tacho.py`
```python
class RemoteTachoService:
    def get_import_history(self, limit=50): ...
```

#### 3.6 Update MainWindow to inject remote services
```python
# In _init_services() remote branch:
from client.remote_analytics import RemoteAnalyticsService
self._analytics_svc = RemoteAnalyticsService(self._api_client)
```

### Dependencies
Phase 2 (ApiClient methods exist) — ❌ MUST BE DONE FIRST

---

## Phase 4: View Updates — ❌ NOT STARTED (14 files)

### Objective
Update each UI view to use remote service wrappers when `self._api_client` is available.

### Pattern
```python
# BEFORE (current local-only pattern)
self.fleet_service = FleetService(db)

# AFTER (dual-mode pattern)  
if self._api_client is not None:
    from client.remote_services import RemoteFleetService
    self.fleet_service = RemoteFleetService(self._api_client)
else:
    self.fleet_service = FleetService(db)
```

### Files to Update

| Priority | View | Service/Object to Replace | Effort |
|---|---|---|---|
| P1 | `client_workspace.py` | `ClientService` → `RemoteClientService` | 17 methods |
| P1 | `driver_manager.py` | `DriverRepository`, `DriverTruckService` → `RemoteDriverService` | 11 methods |
| P1 | `history_view.py` | `TripService`, `InvoiceService` → `RemoteTripService`, `RemoteInvoiceService` | 8 methods |
| P2 | `overview_view.py` | `AnalyticsService`, `TripRepository` → `RemoteAnalyticsService`, `RemoteTripService` | 25 methods |
| P2 | `analytics/__init__.py` | `AnalyticsService` → `RemoteAnalyticsService` | 28 methods across 6 tabs |
| P2 | `generators_view.py` | `TripService`, `ClientService`, `FleetService`, `DriverRepository` | 7 methods |
| P3 | `calculator_view.py` | `FleetService`, `ClientService`, `TripService` | 6 methods |
| P3 | `route_history_view.py` | `RouteHistoryService` → route API calls | 7 methods |
| P4 | `maintenance_analytics_view.py` | `FleetRepository` → `RemoteMaintenanceService` | 5 methods |
| P4 | `maintenance_control_panel.py` | `MaintenanceViewModel` + `OperationsEngine` | 7 methods |
| P4 | `settings_view.py` | `AutoMailRepository` → settings API | 15 methods |
| P4 | `fleet_tracking_view.py` | `fleet_tracking_service` → tracking API | 3 methods |
| P4 | `tacho_import_view.py` | `TachoService` → `RemoteTachoService` | 2 methods |
| P4 | `automail_view.py` | Sub-panels with own DB calls | Complex |

### Dependencies
Phase 3 (RemoteService wrappers exist) — ❌ MUST BE DONE FIRST

---

## Phase 5: Crash Guards — ⚠️ PARTIAL (40%)

### Objective
Guard view constructors against `db=None` so they don't crash when `api_client` is also unavailable in remote mode.

### Status

| View | Guards Done | Remaining |
|---|---|---|
| `route_planner_view.py` | ✅ `if db is not None: self._core = RoutePlannerController(db)` | — |
| `dispatch_board_view.py` | ✅ `if db is not None: self._trip_repo = TripRepository(db)` | — |
| `fleet_tab.py` | ✅ `FleetService(db) if db is not None else None` | — |

### Not Yet Guarded

| File | Lines to Guard | What to Guard |
|---|---|---|
| `overview_view.py` | Constructor | `AnalyticsService(db)`, `TripRepository(db)` |
| `history_view.py` | Constructor | `TripService(db)`, `InvoiceService(db)` |
| `route_history_view.py` | Constructor | `RouteHistoryService(db)` |
| `calculator_view.py` | Constructor | `FleetService(db)`, `ClientService(db)`, `TripService(db)` |
| `maintenance_analytics_view.py` | Constructor | `FleetRepository(db)` |
| `maintenance_control_panel.py` | Constructor | `MaintenanceViewModel(db)` |

**Pattern:** `self.service = ServiceClass(db) if db is not None else None`

### Dependencies
None — can be done in parallel with Phase 4.

---

## Phase 6: Final Verification — ❌ NOT STARTED

### Objective
Run the isolation scanner and full test suite to confirm zero regressions.

### Step-by-Step Tasks

#### 6.1 Run verification script
```bash
python scripts/verify_client_isolation.py
```
Expected: 0 violations (when `main_remote.py` is the entry point).

#### 6.2 Run full test suite
```bash
pytest tests/ -q -k "not slow"
```
Expected: 2,021+ tests green.

#### 6.3 Manual smoke test
```bash
# Start API server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &

# Start remote client
python main_remote.py
```
Navigate to every sidebar tab. Verify:
- No `AttributeError: 'NoneType' object has no attribute`
- No `RemotePreferences has no attribute`
- Document Center loads with API Dashboard showing "online"

#### 6.4 Update build specifications
```bash
python scripts/build_client.py        # production client-only build
pyinstaller build_client.spec          # alternative client-only build
```

### Dependencies
Phases 2-5 complete — ❌ MUST BE DONE LAST

---

## Dependency Graph

```
Phase 1 (API Endpoints) ── DONE
    │
Phase 2 (ApiClient methods) ── NEXT
    │
    ├────────────────────────────────────────┐
    │                                        │
Phase 3 (RemoteService wrappers)   Phase 5 (Crash guards) ── parallel
    │                                        │
    └──────────────────┬─────────────────────┘
                       │
              Phase 4 (View updates)
                       │
              Phase 6 (Final verification)
```

---

## Summary of Remaining Work

| Phase | Files to Create | Files to Modify | Total Changes | Effort Estimate |
|---|---|---|---|---|
| 2. ApiClient | 0 | 1 (`api_client.py`) | ~60 methods | 2-3 hours |
| 3. Wrappers | 5 new files | 1 (`main_window.py`) | ~400 lines | 1-2 hours |
| 4. Views | 0 | 14 view files | ~200 lines | 2-3 hours |
| 5. Crash guards | 0 | 6 view files | ~30 lines | 30 min |
| 6. Verification | 0 | 0 | test runs | 30 min |
| **Total** | **5 new** | **22 existing** | | **~6-8 hours** |
