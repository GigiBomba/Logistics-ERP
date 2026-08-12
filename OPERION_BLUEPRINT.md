# Operion ERP — Complete System Blueprint

> **Audience:** Senior software engineer / architect new to the project
> **Last updated:** 2026-07-30
> **Purpose:** Full understanding of architecture, roles, modules, data flow, and tech stack

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Company & User Roles](#2-company--user-roles)
3. [Tech Stack](#3-tech-stack)
4. [Architecture: Desktop Client](#4-architecture-desktop-client-pyside6)
5. [Architecture: Backend API](#5-architecture-backend-api-fastapi)
6. [Architecture: Mobile App](#6-architecture-mobile-app-flutter)
7. [Database Schema](#7-database-schema)
8. [Authentication & Authorization](#8-authentication--authorization)
9. [Desktop UI: Navigation & Views](#9-desktop-ui-navigation--views)
10. [Desktop Services Layer](#10-desktop-services-layer)
11. [AI Copilot (ARGO)](#11-ai-copilot-argo)
12. [Freight Exchange Integration](#12-freight-exchange-integration)
13. [Document Automation & OCR](#13-document-automation--ocr)
14. [Invoicing & Financial](#14-invoicing--financial)
15. [Fleet & Driver Management](#15-fleet--driver-management)
16. [Mobile App: Screens & Features](#16-mobile-app-screens--features)
17. [Offline & Sync Architecture (Mobile)](#17-offline--sync-architecture-mobile)
18. [Security Architecture](#18-security-architecture)
19. [Testing Strategy](#19-testing-strategy)
20. [Business Invariants](#20-business-invariants)
21. [Configuration & Deployment](#21-configuration--deployment)

---

## 1. System Overview

Operion ERP is a **logistics management system** built for European transport companies. It consists of two client applications backed by a single FastAPI server:

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Desktop ERP** | PySide6 (Qt 6) + Python 3.9 | Full-featured back-office: dispatch, fleet, invoicing, analytics |
| **Mobile App** | Flutter 3.x (Dart) | Field companion for drivers + on-the-go dispatchers |
| **Backend API** | FastAPI (async Python) | REST API + WebSocket for real-time comms |
| **Database** | SQLite (dev) / PostgreSQL (prod) | Multi-tenant relational store |
| **Cache/Queue** | Redis | Session store, rate limiting, Celery broker |

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    DESKTOP ERP (PySide6)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────────┐ │
│  │ Dispatch │ │  Routes  │ │  Fleet   │ │  Invoicing / CMR    │ │
│  │  Board   │ │ Planner  │ │ Manager  │ │  Generator          │ │
│  └──────────┘ └──────────┘ └──────────┘ └─────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              ARGO AI Copilot (conversational UI)            │  │
│  └────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────┤
│                    LOCAL SERVICE LAYER                            │
│  TripService │ FleetService │ InvoicingService │ Analytics │ ... │
│  (Can operate against local SQLite OR delegate to remote API)     │
├──────────────────────────────────────────────────────────────────┤
│                    BACKEND API (FastAPI)                          │
│  ~130 endpoints • 20 routers • 60+ services • 27 repositories   │
│  JWT Auth • WebSocket • Celery tasks • Rate limiting • RBAC      │
├──────────────────────────────────────────────────────────────────┤
│                    DATABASE + REDIS                               │
│  PostgreSQL (prod) / SQLite (dev) • Redis (session/queue/cache)  │
└──────────────────────────────────────────────────────────────────┘
                         │  WebSocket + REST
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MOBILE APP (Flutter)                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │ Driver Shell │ │ Dispatcher   │ │ AI Copilot               │ │
│  │ (Nav/Status) │ │ Shell (KPI)  │ │ (Chat/Voice)             │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘ │
│  Offline-first • Delta Sync • Action Queue • Push Notifications │
└──────────────────────────────────────────────────────────────────┘
```

### Operating Modes

The desktop app has two operating modes determined at startup:

| Mode | Database | When used |
|------|----------|-----------|
| `LOCAL` | Local SQLite file | Standalone desktop operation |
| `REMOTE` | FastAPI backend (shared DB) | Multi-user / collaborative operation |
| `UNKNOWN` | Fallback | When neither can be detected |

Detection logic: `detect_mode(db, api_client)` in `ui/mode_guard.py`
- If both DB and API exist → `REMOTE` (preferred)
- If only local DB → `LOCAL`
- Views and services adapt accordingly: some features only available in one mode

---

## 2. Company & User Roles

### The Business Context

Operion is designed for **transport companies**. Each company has:

- **Manager (owner):** sets up the company, manages fleet, drivers, clients, invoices, analytics
- **Dispatcher / Secretary:** operational role — plans routes, dispatches trips, generates CMRs, tracks fleet
- **Driver:** on the road — sees assigned trips, navigates, updates status, captures documents
- **Admin (developer):** full system access for _Operion developers_, not for company users

### Role Definitions

| Role | Tag | Scope | Who |
|------|-----|-------|-----|
| **Admin** | `admin` | System-wide, bypasses company filtering | Operion developers, zero DB auth (env vars) |
| **Manager** | `manager` | Company-scoped, full business control | Fleet owner / company director |
| **Dispatcher** | `dispatcher` | Company-scoped, operational | Dispatcher, secretary, fleet manager |
| **Driver** | `driver` | Self only (own trips) | Truck driver |

### Permission Matrix

Exact rules from `services/permission_service.py`:

| Action | Admin | Manager | Dispatcher | Driver |
|--------|-------|---------|------------|--------|
| Create dispatch | ✓ | ✓ | ✓ | ✗ |
| Cancel dispatch | ✓ | ✓ | ✓ | ✗ |
| Create trip | ✓ | ✓ | ✓ | ✗ |
| Update trip | ✓ | ✓ | ✓ | ✗ |
| Delete trip | ✓ | ✗ | ✗ | ✗ |
| Create client | ✓ | ✓ | ✗ | ✗ |
| Update client | ✓ | ✓ | ✗ | ✗ |
| Delete client | ✓ | ✗ | ✗ | ✗ |
| Merge clients | ✓ | ✗ | ✗ | ✗ |
| Create vehicle | ✓ | ✓ | ✗ | ✗ |
| Update vehicle | ✓ | ✓ | ✗ | ✗ |
| Delete vehicle | ✓ | ✗ | ✗ | ✗ |
| Create driver | ✓ | ✓ | ✗ | ✗ |
| Update driver | ✓ | ✓ | ✗ | ✗ |
| Delete driver | ✓ | ✗ | ✗ | ✗ |
| Create invoice | ✓ | ✓ | ✗ | ✗ |
| Cancel invoice | ✓ | ✓ | ✗ | ✗ |
| Generate CMR | ✓ | ✓ | ✓ | ✗ |
| Upload document | ✓ | ✓ | ✓ | ✗ |
| Delete document | ✓ | ✓ | ✗ | ✗ |
| Export data | ✓ | ✓ | ✓ | ✗ |
| Send email | ✓ | ✓ | ✗ | ✗ |
| Schedule maintenance | ✓ | ✓ | ✗ | ✗ |
| View analytics | ✓ | ✓ | ✗ | ✗ |
| Create receipt | ✓ | ✓ | ✗ | ✗ |
| Generate payments | ✓ | ✓ | ✗ | ✗ |
| Manage users ("Team") | ✓ | ✓ | ✗ | ✗ |

### How Roles Flow Through the System

```
Login → JWT issued with "role" claim
  │
  ├─ FastAPI: require_dispatcher(), require_manager(), require_admin() dependencies
  │            → 403 if insufficient
  │
  ├─ Desktop sidebar: "Administration → Team" nav item only visible for admin/manager
  │
  └─ Mobile: ModeRouter routes to DriverShell or DispatcherShell based on role
              driver → 4 tabs (Map, Trip Overview, Copilot, Settings)
              dispatcher/manager/admin → 4 tabs (KPI Dashboard, Fleet Map, Copilot, More Hub)
```

### Multi-Tenant Isolation

Every table has a `company_id` column. The `BaseRepository` enforces:

- `_company_filter(alias)` → adds `AND alias.company_id = ?` to every query
- `_company_params()` → binds the current `company_id` from contextvar
- Admins bypass company filtering entirely (see all companies' data)
- Tenant context flows via `database.tenant_context` (contextvars), set by `get_current_user` after login

---

## 3. Tech Stack

### Desktop App (PySide6)

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.9+ |
| UI Framework | PySide6 (Qt 6) | 6.x |
| Maps | folium + QWebEngineView (Chromium) | — |
| Charts | Plotly → Kaleido SVG → QPixmap | — |
| HTTP Client | httpx | for REMOTE mode API calls |
| Icons | QtAwesome (Font Awesome 5) | — |
| Database (local) | sqlite3 (stdlib, WAL mode) | — |

### Backend API (FastAPI)

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | FastAPI (async) | — |
| Validation | Pydantic v2 | — |
| Auth | PyJWT (HS256) + bcrypt | — |
| Database Driver | sqlite3 stdlib / asyncpg for PostgreSQL | — |
| ORM | None (raw SQL + repositories) | — |
| Migrations | Alembic | — |
| Task Queue | Celery (broker: Redis) | — |
| Cache | Redis | — |
| Background GPS | Celery Beat (flush every 30s) | — |

### Mobile App (Flutter)

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Dart | 3.x |
| UI Framework | Flutter | ^3.12.2 |
| State Management | Riverpod | ^2.6.1 |
| HTTP | Dio | ^5.8.0+1 |
| WebSocket | web_socket_channel | ^3.0.3 |
| Secure Storage | flutter_secure_storage | ^9.2.4 |
| Push Notifications | firebase_core + firebase_messaging | ^3.15.2, ^15.2.5 |
| Connectivity | connectivity_plus | ^6.1.4 |
| Biometrics | local_auth | ^2.3.0 |
| Maps | flutter_map + OpenStreetMap | ^7.0.2 |
| Geolocation | geolocator | ^13.0.2 |
| Camera | image_picker | ^1.1.2 |
| Icons | lucide_icons_flutter | ^3.1.4 |
| Fonts | google_fonts (Inter) | ^6.2.1 |

### Infrastructure

| Component | Technology |
|-----------|-----------|
| Containerization | Docker + docker-compose |
| Production DB | PostgreSQL |
| Cache / Session | Redis |
| Reverse Proxy | (behind nginx/Caddy in prod) |

---

## 4. Architecture: Desktop Client (PySide6)

### Startup Sequence (`main.py`)

```
1. Load .env
2. Set Chromium GPU/compositor flags (before any Qt import)
3. Register _DummyBrowser to suppress fig.show()
4. Create QApplication, apply QSS stylesheet
5. Pre-warm QWebEngine (hidden 1×1 view)
6. require_admin_async() — login dialog if admin flow
7. Create MainWindow(db, api, prefs, ops)
8. window.show()
9. Handle --open-url / --open-file (operion:// protocol)
10. On exit: stop ops, close DB, shutdown Chromium
```

### Main Window Structure (`ui/main_window.py`)

```
MainWindow(QMainWindow)
├── Central widget: AppShell
│   ├── Sidebar (collapsible: 48px / 200px)
│   │   ├── Operion monogram (toggle expand)
│   │   ├── Search input (visible when expanded)
│   │   └── Nav groups + items → emits on_select(key)
│   ├── TopBar (44px)
│   │   ├── Breadcrumb + back button
│   │   ├── Fuel price dot
│   │   ├── Alert bell + badge
│   │   └── Clock
│   └── View container (QStackedWidget)
│       └── [Active view] (cross-fade animation, 150ms)
├── Mode detection → LOCAL / REMOTE / UNKNOWN
├── Module cache → lazy-create, pre-warmed at startup
│   (19 views created with 200ms stagger)
├── Navigation stack (max 20) → Alt+Left back
└── Keyboard shortcuts Ctrl+1..9 for first 9 nav items
```

### View Lifecycle

Every view inherits from `BaseView(QScrollArea)`:

```python
class BaseView:
    def wakeup(self):      # Called when view becomes active
    def shutdown(self):    # Called when view is deactivated
    def handle_nav_data(self, data):  # Optional: receive context when navigating

    # Helpers:
    _add_timer(self, interval_ms, callback)
    _add_shot(self, delay_ms, callback)     # one-shot timer
    _subscribe(self, event_type, callback)  # event bus, auto-unsubscribed on shutdown
    _publish(self, event_type, data)
    _register_i18n(self, key, widget)       # auto-update on language change
```

### Navigation Groups & Items

```
OVERVIEW GROUP (everyone)
  ├── Overview (Ctrl+1) — Dashboard KPIs, profit chart, active trips
  └── Analytics (Ctrl+2) — Revenue/fleet analytics

OPERATIONS GROUP (everyone)
  ├── Route Planner (Ctrl+3) — Multi-stop route optimization
  ├── Calculator (Ctrl+4) — Trip profit calculator
  ├── Dispatch Board (Ctrl+5) — Kanban trip dispatch
  ├── Live Tracking (Ctrl+6) — Fleet GPS map
  └── Freight Exchange — TIMOCOM/Trans.eu load search

FLEET GROUP (everyone)
  ├── Fleet (Ctrl+7) — Vehicle registry
  ├── Driver Manager (Ctrl+8) — Driver profiles
  ├── Clients (Ctrl+9) — Client CRM
  ├── Documents — Document center + OCR
  ├── Maintenance Analytics — Maintenance KPIs
  ├── Maintenance Control — Work orders
  └── Tachograph — .ddd import & analysis

FINANCE GROUP (everyone)
  ├── Generators — Invoice/CMR generation
  ├── Trip History — Trip records
  └── Route History — Saved routes

TOOLS GROUP (everyone)
  ├── AI Copilot — ARGO conversational assistant
  └── Migration Center — Data import/export

ADMINISTRATION GROUP (manager & admin only)
  └── Team — User accounts & role management

SETTINGS (everyone, pinned at bottom)
  └── Settings — Company config, language, theme, SMTP
```

---

## 5. Architecture: Backend API (FastAPI)

### App Factory (`backend/main.py`)

```python
def create_app() -> FastAPI:
    app = FastAPI(title="Operion API", version="...")

    # Middleware stack (order matters)
    app.add_middleware(CORSMiddleware, ...)
    app.add_middleware(CorrelationMiddleware)     # X-Request-ID
    app.add_middleware(LoggingMiddleware)          # method path status duration
    app.add_middleware(AuthMiddleware)             # X-API-Key validation
    app.add_middleware(SecurityHeadersMiddleware)  # HSTS, CSP, XFO, etc.
    app.add_middleware(IdempotencyMiddleware)      # Idempotency-Key dedup
    app.add_middleware(RateLimitMiddleware)        # 100 req/min per IP
    app.add_middleware(WebhookBodyMiddleware)      # Preserve raw body for webhooks
    app.add_middleware(InputSanitizationMiddleware) # Strip injection chars
    app.add_middleware(PrometheusMiddleware)       # Metrics

    # Global exception handler → RFC 7807 ProblemDetail
    app.add_exception_handler(Exception, problem_detail_handler)

    # Mount router
    app.include_router(api_v1_router)  # /api/v1 prefix
    return app
```

### Router Tree

All routers mounted via `backend/api/v1/router.py`:

| Router | Prefix under `/api/v1` | Auth Gate |
|--------|----------------------|-----------|
| health | `/health` | Public |
| auth | `/auth` | Public (except `/me`) |
| admin | `/admin` | `require_admin` |
| api_keys | `/api-keys` | `require_admin` |
| users | `/users` | `require_manager` |
| trips | `/trips` | `require_dispatcher` |
| clients | `/clients` | `require_dispatcher` |
| drivers | `/drivers` | `require_dispatcher` |
| fleet | `/fleet` | `require_dispatcher` |
| routes | `/routes` | `require_dispatcher` |
| documents | `/documents` | `require_dispatcher` |
| ocr | `/ocr` | `require_dispatcher` |
| invoices | `/invoices` | `require_dispatcher` |
| cmr | `/cmr` | `require_dispatcher` |
| receipts | `/receipts` | `require_dispatcher` |
| payments | `/payments` | `require_manager` |
| freight_exchange | `/freight` | `require_dispatcher` |
| analytics | `/analytics` | `require_manager` |
| maintenance | `/maintenance` | `require_dispatcher` |
| alerts | `/alerts` | `require_dispatcher` |
| settings | `/settings` | `require_manager` |
| tacho | `/tacho` | `require_dispatcher` |
| copilot | `/copilot` | `require_dispatcher` |
| webhooks | `/webhooks` | Public (HMAC-verified) |
| mobile | `/mobile` | JWT |
| registration | `/registration` | Public |
| waitlist | `/waitlist` | Public |
| route_demo | `/route-demo` | Public |
| feature_flags | `/feature-flags` | `require_admin` |
| gdpr | `/gdpr` | JWT |
| slo | `/slo` | `require_admin` |
| support | `/support` | Internal auth |
| oauth2 | `/oauth2` | Public |

### Service Layer Pattern

```
Router (thin)  →  Service (business logic)  →  Repository (data access)
                  ↕ PermissionService (RBAC)     ↕ BaseRepository (tenant isolation)
```

- **Routers**: param extraction, response formatting, dependency injection
- **Services**: business rules, validation, event publishing, audit logging
- **Repositories**: raw SQL, column allowlisting, parameterized queries, tenant scoping
- **PermissionService**: single source of truth for all authorization checks

### Repository Pattern

```python
class BaseRepository:
    COLUMNS: ClassVar[list[str]]  # allowlist for column names

    def _validate_columns(self, data):       # raises ValueError for unknown keys
    def _company_filter(self, alias=""):     # "AND alias.company_id = ?" or ""
    def _company_params(self):               # (company_id,) or ()
    def _set_company_from_context(self, d):  # injects company_id on INSERT
```

Multi-tenancy is enforced via contextvars:

```python
# database/tenant_context.py
_current_company_id = ContextVar("company_id", default=None)
_current_user_role = ContextVar("user_role", default="driver")

def set_tenant_context(company_id, role): ...
def get_company_id(): ...
def get_user_role(): ...
```

### Celery Tasks

| Task | Schedule | Purpose |
|------|----------|---------|
| `flush_gps_batch_to_postgres` | Every 30s | Batch GPS pings from Redis → PostgreSQL |
| `process_document_ocr` | On demand | OCR processing (max 3 retries) |
| `enforce_copilot_retention` | Daily | Delete old audit logs, null JSONB after 90d |
| `anonymize_copilot_data` | On demand | GDPR right-to-erasure for copilot data |

---

## 6. Architecture: Mobile App (Flutter)

### Entry Point (`mobile_app/lib/main.dart`)

```dart
void main() => runZonedGuarded(() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const OperionMobileApp());
}, (error, stack) => developer.log(...));

// Triple error handling:
FlutterError.onError = ...;           // Flutter framework errors
PlatformDispatcher.instance.onError = ...;  // Platform-level errors (never kills app)
runZonedGuarded(...);                 // Global catch-all
```

### App Root (`mobile_app/lib/app.dart`)

```dart
class OperionMobileApp extends StatelessWidget {
  Widget build(BuildContext context) {
    return ProviderScope(
      child: Consumer(
        builder: (_, ref, __) {
          final locale = ref.watch(localeProvider);
          final themeMode = ref.watch(themeModeProvider);
          return MaterialApp(
            locale: locale,
            themeMode: themeMode,
            theme: AppTheme.light,
            darkTheme: AppTheme.dark,
            home: const ModeRouter(),  // auth gate
            localizationsDelegates: [...],
            supportedLocales: AppLocalizations.supportedLocales,
          );
        },
      ),
    );
  }
}
```

### Riverpod Provider Architecture

```
                        ┌─────────────────────────────┐
                        │     ProviderScope (root)     │
                        └─────────────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
┌──────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  Core Providers  │     │  Feature Providers    │     │  Sync Providers      │
│                  │     │                      │     │                      │
│ secureTokenStore │     │ dispatcherOverview   │     │ syncTriggerProvider  │
│ apiClient        │     │ fleetPositions       │     │ syncStatusProvider   │
│ authState        │     │ tripOverview         │     │ actionQueueProvider  │
│ currentUser      │     │ copilotState         │     │ isOnlineProvider     │
│ isOffline        │     │ routeShareGeometry   │     │ syncCursorsProvider  │
│ locale           │     │ dispatcherJobs       │     │                      │
│ themeMode        │     │ dispatcherDrivers    │     │                      │
│ messageBus       │     │ dispatcherAlerts     │     │                      │
└──────────────────┘     └──────────────────────┘     └──────────────────────┘
```

### Provider Types Used

| Riverpod Type | Usage |
|-------------|-------|
| `Provider` | Singleton services (ApiClient, SecureTokenStore, MessageBus) |
| `StateProvider` | Simple mutable state (locale, themeMode, isOffline, unread counts) |
| `StateNotifierProvider` | Complex state machines (AuthStateNotifier, CopilotStateNotifier) |
| `FutureProvider` | One-shot API fetches (fleet positions, dispatcher overview) |
| `StreamProvider` | Real-time (connectivity stream) |
| `FutureProvider.family` | Parameterized fetches (alert detail by ID) |

### Navigation Shells

```
ModeRouter (ConsumerStatefulWidget)
├── Session restoration check
├── authState == unauthenticated → LoginScreen
├── authState == sessionExpired → SessionExpiredScreen
├── authState == authenticated
│   ├── user.role == driver → DriverShell (4 tabs)
│   │   ├── Tab 0: RouteShareNavScreen (map + turn-by-turn)
│   │   ├── Tab 1: DriverTripOverviewScreen (status + ETA)
│   │   ├── Tab 2: CopilotChatScreen
│   │   └── Tab 3: SettingsScreen
│   └── user.role in (dispatcher, manager, admin) → DispatcherShell (4 tabs)
│       ├── Tab 0: DispatcherHomeScreen (KPI dashboard)
│       ├── Tab 1: FleetMapScreen (live vehicle positions)
│       ├── Tab 2: CopilotChatScreen
│       └── Tab 3: MoreHubScreen (11-tile grid)
│           ├── Messages, Teams, Analytics (placeholder), Jobs, Alerts
│           ├── Profit Calculator, Route Planner, Freight Exchange
│           ├── Document Center, Local Download, Settings
```

---

## 7. Database Schema

### Core Tables (50+)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `companies` | Multi-tenant companies | id, company_name, subscription_tier |
| `users` | User accounts | id, email, password_hash, role, company_id, is_active |
| `auth_sessions` | Active sessions | company_id, user_email, token_hash, device_name, expires_at |
| `api_keys` | Per-partner API keys | id, key_hash, label, scopes, expires_at, company_id |
| `trips` | Trip records | id, company_id, status, client_id, truck_id, driver_id, price_eur, costs, start_date, end_date, cmr_number, source |
| `trip_status_history` | Status audit trail | trip_id, from_status, to_status, changed_by, changed_at |
| `clients` | Client/company CRM | id, company_id, name, vat_number, address, payment_terms, rating |
| `client_contacts` | Client contacts | id, client_id, name, email, phone, position |
| `client_tags` | Client tags | client_id, tag |
| `trucks` | Fleet vehicles | id, company_id, plate, brand, model, vin, status, year |
| `drivers` | Driver profiles | id, company_id, name, license_number, license_expiry, medical_expiry, adr_certificate_expiry |
| `driver_truck_assignments` | Driver ↔ truck | id, driver_id, truck_id, assigned_at, unassigned_at |
| `routes` | Saved routes | id, company_id, name, waypoints_json |
| `route_history_v2` | Route calculation results | id, fingerprint, geometry_compressed, estimates, company_id |
| `route_events` | Route lifecycle | route_id, event_type, timestamp |
| `truck_route_assignments` | Route ↔ truck | route_id, truck_id |
| `invoices` | Invoice header | id, company_id, client_id, trip_id, status, total, vat, issue_date, due_date |
| `proforma_invoices` | Proforma invoices | id, company_id, line_items_json, status |
| `receipts` | Payment receipts | id, invoice_id, amount, currency, receipt_date |
| `cmr_counter` | CMR numbering | year, last_sequence |
| `successive_carriers` | CMR carrier chain | cmr_id, carrier_order, carrier_name |
| `cmr_audit_log` | CMR changes | cmr_id, changed_by, changed_at, changes_json |
| `documents` | Document center (FTS5) | id, company_id, title, file_name, mime_type, ocr_text, extracted_data_json, category |
| `document_links` | Document to entity | document_id, linked_entity_type, linked_entity_id |
| `document_versions` | Version history | document_id, file_hash, uploaded_by, uploaded_at |
| `document_pipeline_runs` | OCR pipeline state | document_id, stage, status, engine, error_message |
| `maintenance_records` | Completed maintenance | id, truck_id, date, category, cost, notes |
| `maintenance_schedules` | Scheduled maintenance | id, truck_id, due_date, task, status |
| `truck_health_scores` | 0-100 health score | truck_id, score, calculated_at, factors_json |
| `tacho_imports` | Tachograph file import | id, driver_id, file_hash, imported_at |
| `tacho_driver_activity` | Daily activity | import_id, date, driving_min, working_min, rest_min |
| `tacho_vehicle_data` | Vehicle speed data | import_id, timestamp, speed, location |
| `alerts` | System alerts | id, company_id, type, severity, title, is_resolved |
| `operation_events` | Event log | id, event_type, entity_type, entity_id, data_json, timestamp |
| `gps_telemetry` | GPS position records | id, truck_id, lat, lng, speed, heading, recorded_at |
| `contracts` | Client contracts | id, client_id, start_date, end_date, terms |
| `email_logs` | Email send history | id, recipient, subject, status, sent_at |
| `invoice_reminders` | Payment reminders | invoice_id, reminder_number, sent_at |
| `settings` | Key-value preferences | company_id, key, value |
| `mobile_devices` | Registered push devices | id, user_id, device_id, platform, push_token, is_active |
| `freight_providers` | Exchange connections | id, company_id, provider_name, credentials_encrypted, is_connected |
| `saved_searches` | Freight search filters | id, company_id, name, filters_json, provider |

### Key Schema Features

- **Multi-tenant**: `company_id` on all business tables, composite indexes
- **Soft delete**: `deleted_at` timestamp on `trips`, `clients`, `trucks`, `drivers`
- **Full-text search**: FTS5 virtual table on `documents` (title, file_name, description, tags, text_content)
- **JSON columns**: `stops_json`, `geometry_compressed`, `adr_info_json`, `line_items_json`, `extracted_data_json`
- **Financial precision**: `NUMERIC(12,2)` for monetary columns
- **WAL mode**: SQLite Write-Ahead Logging for concurrent reads

### Alembic Migrations

Key migration milestones:

| Migration | Purpose |
|-----------|---------|
| Financial precision | Convert monetary columns to NUMERIC(12,2) |
| Datetime integrity | timestamptz conversion for date columns |
| Trans.eu Phase 1 | Freight exchange connections + saved searches |
| Copilot reasoning | Reasoning graph JSON storage |
| Document pipeline | Pipeline run tracking + version history |
| GPS telemetry | Batch GPS position ingestion |

---

## 8. Authentication & Authorization

### Login Flow

```
POST /api/v1/auth/token
Body: username (email), password, device_id (optional)

1. Brute-force lockout check: 5 failures in 5 min → 15 min block
2. Gate 1 — Admin gateway (env vars):
   - Compare email against OPERION_ADMIN_EMAIL
   - Verify password against OPERION_ADMIN_PASSWORD_HASH (bcrypt)
   - Zero database access
   - Role hardcoded as "admin"
3. Gate 2 — Database users table:
   - SELECT FROM users WHERE email = ? AND is_active = 1
   - bcrypt.verify_password(plain, hash)
   - Role from users.role field
4. On success:
   - Issue JWT access token (HS256, 15 min expiry)
   - Claims: {"sub": email, "role": role, "exp": ...}
   - Generate opaque refresh token (128-char hex)
   - Store refresh token hash in Redis (or in-memory dict)
   - Set httpOnly refresh_token cookie + return in body
   - Record session in auth_sessions table
```

### Token Refresh

```
POST /api/v1/auth/refresh
Body: refresh_token (or httpOnly cookie)

1. Look up refresh token by SHA-256 hash in Redis/in-memory
2. Check expiry
3. If device_id was stored, verify device is still active in mobile_devices
4. Token rotation: delete old refresh token, issue new pair
```

### JWT Format

```python
# Claims
{
    "sub": "user@example.com",    # email
    "role": "dispatcher",          # role name
    "exp": 1711812345              # expiry timestamp
}
# Algorithm: HS256
# Default expiry: 15 minutes
```

### API Key Authentication (Legacy / Machine-to-Machine)

```
Header: X-API-Key: <key>

Two tiers:
1. Global key: hmac.compare_digest against OPERION_API_KEY env var
2. Per-partner keys: SHA-256 hashed, stored in api_keys table with scopes + expiry
```

### Authorization Dependencies

```python
# FastAPI dependency chain:
require_admin     → requires role == "admin" or is_admin == True
require_manager   → requires role in ("admin", "manager")
require_dispatcher → requires role in ("admin", "manager", "dispatcher")

# Applied per-router:
@router.get("/trips")
async def list_trips(user = Depends(require_dispatcher)):
    ...
```

### Desktop Auth

The desktop app can authenticate via:
1. **Admin login gate** at startup (`require_admin_async()`) — env-var based
2. **Standard login** via API client (JWT) when in REMOTE mode
3. **Local mode** — no authentication required (single-user local DB)

### Mobile Auth

```
LoginScreen → POST /api/v1/auth/token (with device_id)
  → JWT stored in FlutterSecureStorage (Android EncryptedSharedPreferences / iOS Keychain)
  → On next launch: tryRefresh() → if refresh succeeds, restore session
  → On 401 during any API call: AuthInterceptor attempts refresh
    → if refresh fails: clearTokens() + ForceLogoutEvent → SessionExpiredScreen
```

---

## 9. Desktop UI: Navigation & Views

All 21 view classes, their exact location, and what they display:

### Dashboard & Overview

| View | File | Description |
|------|------|-------------|
| `QtOverviewView` | `ui/views/overview_view.py` | KPI strip (active trips, revenue, fleet utilization), Plotly profit chart, active trips table, top trucks by revenue, recent activity feed, alert strip |
| `QtAnalyticsView` | `ui/views/analytics/__init__.py` | Revenue analytics (period/client/route), fleet utilization breakdown, driver performance, overdue invoice aging, configurable date range |
| `QtFleetDashboard` | `ui/views/dashboard.py` | Fleet-wide KPIs, vehicle status summary, maintenance alerts |

### Operations

| View | File | Description |
|------|------|-------------|
| `QtRoutePlannerView` | `ui/views/route_planner_view.py` | Origin/destination/waypoint rows, truck profile selector (height/weight/width), country exclusion chips, GraphHopper route result pills (distance/duration/fuel/toll), folium map sidebar |
| `QtCalculatorView` | `ui/views/calculator_view.py` | Profit calculator form: revenue, fuel cost, toll cost, salary cost, extra costs; VAT toggle; auto-calculated profit/margin; TripContext sync for loading existing trips |
| `QtDispatchBoardView` | `ui/views/dispatch_board/dispatch_board.py` | 3-tab: Board (Kanban columns by status: Planned → Loading → In Transit → Delivered), Timeline (Gantt-style), Alerts; `QtKanbanColumn`, `QtTripCard` with drag-drop |
| `QTrackingView` | `ui/views/fleet_tracking_view.py` | Live fleet map (folium), color-coded vehicle markers, driver info on click |
| `FreightSearchView` | `ui/views/freight_exchange/search_view.py` | Provider health indicators, search filters (route, weight, type), load results table with import action |

### Fleet & Drivers

| View | File | Description |
|------|------|-------------|
| `QtFleetTab` | `ui/views/fleet_tab/fleet_tab.py` | KPI strip, search/filter bar, `StyledTableWidget` (sortable/resizable/CSV export), alerts panel, chart tab, quick-add form, truck detail dialog (maintenance history, documents, assignments) |
| `QtDriverManager` | `ui/views/driver_manager.py` | KPI cards (active drivers, expiring licenses), searchable driver table, tacho timeline visualization, CRUD dialog (license/medical/ADR fields) |
| `QtClientWorkspace` | `ui/views/client_workspace/client_workspace.py` | Client table with search, tabs: Details/Contacts/Invoices/Trips, CRUD dialogs, merge dialog, revenue charts |
| `QtMaintenanceAnalyticsView` | `ui/views/maintenance_analytics_view.py` | Cost trends, category breakdown, per-truck summary, monthly comparison |
| `QtMaintenanceControlPanel` | `ui/views/maintenance_control_panel.py` | Scheduled maintenance list, overdue alerts, record work dialog |
| `QtTachoImportView` | `ui/views/tacho_import_view.py` | Drag-drop .ddd file import, parsed data display (driving/working/rest), compliance warnings |

### Finance & Documents

| View | File | Description |
|------|------|-------------|
| `QtGeneratorsView` | `ui/views/generators_view.py` | Trip selector (pick trip to generate for), Invoice Editor tab, CMR Form tab, language selector for generated documents |
| `QtInvoiceEditor` | `ui/views/invoice_editor/__init__.py` | Line items table, VAT/discount calculation, PDF preview, e-Factura XML export, send email action |
| `QtCmrFormView` | `ui/views/cmr_form_view.py` | Full UN/CEFACT standard CMR form layout (numbered boxes), successive carriers section, signature pad |
| `QtDocumentCenterView` | `ui/views/document_center/document_center.py` | Upload button, category tree, FTS5 search bar, document list with OCR status, version history, linked entity browser |
| `QtHistoryView` | `ui/views/history_view.py` | Sortable/filterable trip history table, export to PDF/Excel/CSV, delete action |
| `QtRouteHistoryView` | `ui/views/route_history_view.py` | Saved route list, map preview on selection, duplicate/archive/export |

### Tools & Administration

| View | File | Description |
|------|------|-------------|
| `CoPilotView` | `ui/views/copilot_view.py` | Chat panel with utterance input, plan visualization, step-by-step execution display |
| `QtMigrationCenterView` | `ui/views/migration_center/migration_center_view.py` | 3 tabs: Import (software), Import (physical documents), Export |
| `QtTeamView` | `ui/views/team_view.py` | **Manager/admin only** — user table, invite user form, role assignment (admin/manager/dispatcher/driver) |
| `QtSettingsView` | `ui/views/settings_view/settings_view.py` | Company info, branding, language/currency/theme picker, SMTP config, fleet tracking provider config, maintenance thresholds |

---

## 10. Desktop Services Layer

### Local Services (work against local SQLite)

Located in `services/` at the project root:

| Service | File | Key Methods |
|---------|------|-------------|
| `TripService` | `services/trip_service.py` | `create_trip`, `update_trip`, `get_filtered`, `get_by_statuses`, `check_conflicts`, `update_cmr_fields` |
| `FleetService` | `services/fleet_service_impl.py` | `create_truck`, `update_truck`, `get_all`, `get_by_plate`, `add_maintenance_record`, `upsert_health_score` |
| `ClientService` | `services/client_service.py` | `create_client`, `update_client`, `merge_clients`, `get_dashboard_data`, `get_revenue_history` |
| `DriverTruckService` | `services/driver_truck_service.py` | `assign_driver`, `unassign_driver`, `get_current_assignment`, `get_assignment_history` |
| `RoutePlannerController` | `services/route_planner_controller.py` | `calculate_route` (calls GraphHopper), `get_profiles`, `check_country_restrictions` |
| `RouteHistoryService` | `services/route_history_service.py` | `save_route`, `get_history`, `duplicate_route`, `archive_route` |
| `CostEngine` | `services/cost_engine.py` | `calculate_trip_costs` (fuel/toll/salary/extras → totals + margin) |
| `InvoicingService` | `services/invoicing/service.py` | `create_invoice`, `finalize`, `send_email`, `transition_status` |
| `CmrGenerator` | `services/invoicing/cmr_generator.py` | `generate_pdf` (reportlab), `generate_efti_xml`, `get_next_sequence` |
| `ReceiptService` | `services/invoicing/receipt_service.py` | `create_receipt`, `generate_pdf` (amount-in-words) |
| `ProformaService` | `services/invoicing/proforma_service.py` | `create_proforma`, `convert_to_invoice` |
| `DocumentService` | `services/document_service.py` | `upload`, `search_fts5`, `run_ocr`, `link_to_entity`, `get_versions` |
| `OperationsEngine` | `services/operations/operations_engine.py` | Background worker: event processing, alert creation, email sending |
| `PermissionService` | `services/permission_service.py` | All `can_*` methods (see permission matrix) |
| `FuelPriceService` | `services/fuel_price_service.py` | Fetch fuel prices from external API |
| `PreferencesManager` | `services/preferences.py` | User preference persistence (theme, language, sidebar state) |

### Remote Services (delegate to FastAPI when in REMOTE mode)

Located in `client/`:

| Service | File |
|---------|------|
| `RemoteTripService` | `client/remote_trip_service.py` |
| `RemoteFleetService` | `client/remote_fleet_service.py` |
| `RemoteClientService` | `client/remote_client_service.py` |
| `RemoteFreightExchangeService` | `client/remote_freight_service.py` |
| `RemoteCopilotService` | `client/remote_copilot_service.py` |

### API Client (`client/api_client.py`)

- HTTPX-based, Bearer token auth
- Circuit breaker: 5 consecutive 502/503/504 → opens for 30s
- Exponential backoff: up to 3 retries
- Token auto-refresh on 401
- Dual-mode document service: API first, fall back to local DB

---

## 11. AI Copilot (ARGO)

### Architecture

```
User utterance → Sanitization → World Model Snapshot → LLM (structured plan)
  → Permission gate → Step-by-step execution → Confirmation (Level 3)
  → Audit log + Reasoning graph
```

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/copilot/chat` | Process natural language utterance |
| POST | `/api/v1/copilot/voice` | Voice input (STT transcript) |
| GET | `/api/v1/copilot/plans/{id}` | Get plan execution status |
| POST | `/api/v1/copilot/plans/{id}/cancel` | Cancel in-flight plan |
| POST | `/api/v1/copilot/plans/{id}/confirm` | Confirm + execute plan (Level 3) |
| POST | `/api/v1/copilot/plans/{id}/undo` | Undo completed step (30-min window) |
| GET | `/api/v1/copilot/conversations` | List conversations (cursor pagination) |
| GET | `/api/v1/copilot/conversations/{id}` | Conversation details |
| GET | `/api/v1/copilot/insights` | Proactive insights queue |
| WS | `/api/v1/copilot/ws/{conversation_id}` | Real-time plan timeline |

### World Model (`backend/copilot/world_model.py`)

A `WorldModelSnapshot` captures the current operational state:

```python
class WorldModelSnapshot:
    fleet: list[Truck]          # active vehicles
    drivers: list[Driver]       # available drivers
    trips: list[Trip]           # active trips
    documents: list[Document]   # recent documents
    dispatches: list[Dispatch]  # current dispatches
    maintenance: list[Alert]    # pending maintenance
    financial: list[Invoice]    # open invoices
    notifications: list[Alert]  # unread alerts
    open_problems: list[str]    # system issues
    todays_objectives: list     # daily KPIs
```

### Safety Mechanisms

| Mechanism | Detail |
|-----------|--------|
| **Kill switch** | Platform-wide + per-company: checked on every request, returns 503 |
| **Plan ownership** | Every plan validated against company_id |
| **Input sanitization** | `sanitize_free_text()` + injection detection |
| **Circuit breaker** | Max 20 tool calls per plan, 50 reasoning nodes, 30s timeout |
| **Level 3 confirmation** | Irreversible actions require typed confirmation phrase |
| **Retention** | Audit logs deleted after 24 months, reasoning graph JSONB nulled after 90 days |
| **Rate limiting** | Subject to standard 100 req/min per IP |

### Tool Permissions

Copilot tools are gated by the same `PermissionService` — a driver asking the copilot to "create an invoice" will be denied because `can_create_invoice` returns false for driver role.

---

## 12. Freight Exchange Integration

### Architecture

```
FreightExchangeScreen (UI) → RemoteFreightExchangeService (desktop API client)
  → FastAPI freight_exchange router → Service layer → Provider adapters

Providers (adapter pattern):
  ├── TimocomAdapter (WebSocket + REST)
  └── TransEuAdapter (OAuth 2.0 + REST)
```

### TIMOCOM Adapter

| Feature | Detail |
|---------|--------|
| Authentication | Username/password per company account |
| Load search | Full-text search with filters (origin, destination, weight, type) |
| Load import | Import exchange load as Operion trip |
| Saved searches | Persist and re-run search filters |
| Rate limiting | 60 requests/minute (enforced by `RateLimiter`) |
| Circuit breaker | 5 consecutive failures → opens for 30s |

### Trans.eu Adapter (Phase 1)

| Feature | Detail |
|---------|--------|
| Authentication | OAuth 2.0 per-user (each dispatcher has own token) |
| Freight search | Search + import via adapter pattern |
| Publication | Publish available trucks to Trans.eu |
| Negotiation | Accept/reject/counter-offer workflow |
| Transport orders | Create and manage orders |
| Transport monitoring | Real-time GPS from Trans.eu |
| Dock scheduler | Warehouse time-slot management |
| Webhook ingestion | Receive status updates via webhooks |

### Internal Services

| Service | Purpose |
|---------|---------|
| `ConnectionManagerService` | Provider connection lifecycle, credential storage (encrypted) |
| `SearchEngineService` | Cross-provider load search, result deduplication |
| `EvaluationEngineService` | Load profitability evaluation (margin calc, risk scoring) |
| `FleetMatcherService` | Best truck match for a load (capacity, location, availability) |
| `ImportPipelineService` | Import exchange load as Operion trip (maps fields, links back) |
| `HealthMonitorService` | Provider integration health status |
| `CircuitBreaker` | Failure isolation per provider |

---

## 13. Document Automation & OCR

### Pipeline Flow

```
Upload (manual or auto) → Document created (status: pending)
  → OCR triggered (auto or manual):
    1. PaddleOCR (primary) extracts text from image/PDF
    2. Tesseract (fallback) if PaddleOCR fails
    3. AI field extraction (dates, amounts, names, reference numbers)
    4. Trip matching (fuzzy match extracted data to existing trips)
    5. Document linked to matched trip
  → Document status: processed
```

### OCR Engine Configuration

| Engine | Priority | File types | Notes |
|--------|----------|------------|-------|
| PaddleOCR | Primary | images, scanned PDFs | Better accuracy for European languages |
| Tesseract | Fallback | images | Installed locally |
| Cloud OCR | Optional | images | When local OCR fails |
| AI Fallback | Last resort | images | Local LLM for hard cases |

### Pipeline Services

| Service | File | Purpose |
|---------|------|---------|
| `Pipeline` | `services/document_automation/pipeline.py` | Orchestrates the full import→OCR→extraction→matching flow |
| `OcrExtractor` | `services/document_automation/ocr_extractor.py` | PaddleOCR + Tesseract wrapper |
| `AiFallback` | `services/document_automation/ai_fallback.py` | ML-based fallback for difficult documents |
| `TripMatcher` | `services/document_automation/trip_matcher.py` | Match documents to trips via extracted fields (date, client, route) |
| `DocumentGrouper` | `services/document_automation/document_grouper.py` | Group related documents by trip |
| `PackageBuilder` | `services/document_automation/package_builder.py` | Build email packages (CMR + invoice + POD bundle) |

### Document Center Features

- **Upload**: File upload with categorization (CMR, invoice, POD, contract, other)
- **FTS5 search**: Full-text across title, file_name, description, tags, extracted OCR text
- **OCR processing**: Status tracking (pending/processing/done/failed), engine selection
- **Entity linking**: Attach documents to trips, clients, drivers, vehicles
- **Versioning**: File hash tracking, version history, replace/update
- **Expiry tracking**: Document-level expiry date + automated alerts
- **Email packages**: Bundle documents, send via SMTP

---

## 14. Invoicing & Financial

### Invoice Status Workflow

```
draft → finalized → xml_generated → submitted_externally → queued → submitting
    ↓          ↓            ↓               ↓                   ↓
cancelled   cancelled    cancelled      rejected             rejected
                                         ↓                     ↓
                                      draft OR              draft OR
                                    manual_review         manual_review
                                                             ↓
                                                        accepted → paid
                                                      manual_review
                                                           ↓
                                                       draft OR rejected
```

12 states, defined in `models/invoice_models.py`:

```python
INVOICE_STATUS_TRANSITIONS = {
    "draft": ["finalized", "cancelled"],
    "finalized": ["xml_generated", "cancelled", "paid"],
    "xml_generated": ["submitted_externally", "draft"],
    "submitted_externally": ["queued", "rejected"],
    "queued": ["submitting", "rejected"],
    "submitting": ["accepted", "rejected", "manual_review"],
    "accepted": ["paid"],
    "rejected": ["draft", "manual_review"],
    "manual_review": ["draft", "accepted", "rejected"],
    "cancelled": [],
    "paid": [],
}
```

### Invoice Types

| Type | Purpose |
|------|---------|
| `invoice` | Standard invoice |
| `storno` | Credit note (reversal) |
| `proforma` | Quotation |
| `receipt` | Payment confirmation |
| `advance` | Advance payment invoice |
| `final` | Final invoice |
| `correction` | Correcting invoice |

### Financial Calculations

```python
gross_value = qty × unit_price
discount_amt = gross_value × discount_pct / 100  # capped at gross_value
taxable_amount = gross_value − discount_amt
vat_amount = taxable_amount × vat_rate / 100
line_total = taxable_amount + vat_amount
net_profit = price_eur − (fuel_cost + toll_cost + salary_cost + extra_costs)
```

### Generated Documents

| Document | Library | Format | Content |
|----------|---------|--------|---------|
| Invoice | reportlab | PDF | Company header, line items, VAT summary, totals, QR code |
| e-Factura | xml.etree | XML | Romanian ANAF e-invoice format |
| CMR | reportlab | PDF | UN/CEFACT numbered boxes, parties, goods, signatures |
| eFTI | xml.etree | XML | Electronic Freight Transport Information |
| Receipt | reportlab | PDF | Amount in words, payment method, invoice reference |
| Proforma | reportlab | PDF | Quotation-style with validity date |

### Payment Reminder Engine (Dunner)

```
DunnerEngine
├── Scheduled reminders: up to 5 reminder levels
├── Template-based emails (invoice_due, invoice_overdue_1, ..., invoice_overdue_5)
├── Configurable intervals between reminders
└── AutoMail integration for sending
```

### Multi-Currency

- Base currency: EUR
- Exchange rates: fetched from external API (REST)
- Per-invoice currency selection
- Profit calculation always in EUR for comparability

---

## 15. Fleet & Driver Management

### Vehicle Lifecycle

```
Truck added (create) → Active → Maintenance → Active
                                  ↓
                              Decommissioned (soft delete)
```

### Health Scoring

Each truck gets a 0-100 health score (`truck_health_scores` table):
- Based on: maintenance frequency, recent repairs, mileage, alert count
- Calculated by `MaintenanceEngine`
- Displayed in fleet overview as color-coded indicator

### Maintenance

| Feature | Detail |
|---------|--------|
| Scheduled maintenance | Due date, task description, status tracking |
| Maintenance records | Completed work: date, category, cost, notes, vendor |
| Cost tracking | Per-truck monthly costs, category breakdown |
| Alerts | Overdue maintenance alert (color-coded) |
| Prediction | `MaintenanceEngine` forecasts upcoming needs |

### Tachograph Import

- File format: `.ddd` (digital tachograph files)
- Parsed data: driver activities (driving/working/rest/available in minutes), vehicle speed data
- EU 561/2006 compliance checks:
  - Daily driving ≤ 540 minutes
  - Weekly driving ≤ 3360 minutes
- Timeline visualization in driver manager

### GPS Tracking Adapters

| Provider | Features |
|----------|----------|
| **Wialon** | Session-based auth, unit search, position polling |
| **Frotcom** | Fleet management, driver behavior, position polling |
| **Navixy** | GPS tracking, geofencing, position polling |

Pluggable adapter pattern: `services/fleet_tracking_service.py` → adapter interface → concrete provider implementations.

---

## 16. Mobile App: Screens & Features

### Authentication Flow

```
App launch → ModeRouter.initState()
  → _restoreSession() (post-frame)
    → check refresh token exists
    → tryRefresh() POST /api/v1/auth/refresh
      → success: set authState = authenticated, set currentUser
      → failure: set authState = unauthenticated
```

| Screen | File | Behaviour |
|--------|------|-----------|
| `LoginScreen` | `features/auth/login_screen.dart` | Email/password form, biometric unlock button, error animation (slide-in, 5s auto-dismiss), UUID device_id attached to login |
| `SessionExpiredScreen` | `features/auth/session_expired_screen.dart` | Non-dismissible (canPop: false), biometric restore option, "Sign In" resets to unauthenticated |

### Driver Shell

4-tab bottom navigation:

#### Tab 0: RouteShareNavScreen
- flutter_map with OpenStreetMap tiles
- Route polyline from `routeShareGeometryProvider`
- TurnInstructionBanner (accent-colored, shows instruction + distance + ETA)
- BottomInfoBar (total distance, total duration, ETA)
- Current GPS position marker (blue dot)

#### Tab 1: DriverTripOverviewScreen
- Transport card: load info, origin → destination
- ETA card with `EtaConfidence` indicator (live/stale/unavailable)
- Elapsed time card
- `TransportStatusButtons`: auto-derived next actions based on current trip status
- Statuses: planned → loading → inTransit → delivered

#### Tab 2: CopilotChatScreen
- Full AI copilot interface (see below)

#### Tab 3: SettingsScreen
- Language: Romanian / English
- Theme: System / Light / Dark
- App version display
- Logout (confirmation dialog)

### Dispatcher Shell

4-tab bottom navigation:

#### Tab 0: DispatcherHomeScreen
- 2×2 KPI grid: active jobs, active drivers, open alerts, vehicles on road
- Quick action chips: Approve, Messages, Live Fleet
- Pull-to-refresh
- Watches `dispatcherOverviewProvider`

#### Tab 1: FleetMapScreen
- flutter_map with color-coded vehicle markers:
  - Green: active/driving
  - Orange: stopped
  - Gray: idle/offline (>5 min)
- Bottom sheet on tap: vehicle plate, driver name, status, last update
- Watches `fleetPositionsProvider`

#### Tab 2: CopilotChatScreen

#### Tab 3: MoreHubScreen
11-tile grid (2 columns):
| Tile | Screen | Purpose |
|------|--------|---------|
| Messages | `MessageListScreen`→`MessageChatScreen` | Driver↔dispatcher 1:1 chat |
| Teams | `TeamsScreen` | Driver list with filters (all/available/driving/off) |
| Analytics | `DispatcherAnalyticsScreen` | Placeholder → "open on desktop" |
| Jobs | `JobListScreen`→`JobDetailScreen` | Transport list, approve/reject/reassign |
| Alerts | `AlertInboxScreen` | Severity-coded alerts (low/medium/high/critical) |
| Profit Calc | `ProfitCalculatorScreen` | Revenue − fuel − tolls − maintenance − driver cost |
| Route Planner | `RoutePlannerScreen` | Origin/destination/waypoints → optimize |
| Freight Exch. | `FreightExchangeScreen` | Load board search (placeholder) |
| Documents | `DocumentCenterScreen` | Document list + camera OCR capture |
| Local DL | `LocalDownloadScreen` | Offline download by date range/category |
| Settings | `SettingsScreen` | Language/theme/logout |

### Copilot Chat (shared)

| Feature | Detail |
|---------|--------|
| State machine | Idle → Processing → AwaitingClarification/AwaitingConfirmation/Completed/Error |
| Level 3 confirmation | Typed phrase match for irreversible actions |
| Voice input | Push-to-talk (STT via backend `/copilot/voice`) |
| Text input | Send button + keyboard submit |
| Conversational | Full chat history, multi-turn |
| Offline history | Local conversation persistence |

### Additional Screens

| Screen | File | Description |
|--------|------|-------------|
| `DriverHomeScreen` | `features/driver/home/driver_home_screen.dart` | "My Day": active transports, next stop, unread messages, shimmer skeleton loading |
| `JobDetailScreen` | `features/dispatcher/` | Transport detail with approve/reject/reassign actions |
| `AlertInboxScreen` | `features/dispatcher/` | Alert list with severity badges, read/unread |
| `ApprovalDetailScreen` | `features/dispatcher/` | Approval workflow detail |
| `TeamsScreen` | `features/teams/` | Driver list with filter chips |
| `ProfitCalculatorScreen` | `features/profit_calculator/` | Client-side form → instantaneous calculation |
| `RoutePlannerScreen` | `features/route_planner/` | Origin/destination + waypoints, flutter_map preview |
| `DocumentCenterScreen` | `features/document_center/` | 2 tabs: Documents list, OCR Automation (camera capture → upload) |
| `LocalDownloadScreen` | `features/local_download/` | Category grid: documents, invoices, receipts, OCR, trips |
| `FreightExchangeScreen` | `features/freight_exchange/` | Search bar + empty state (base implementation) |
| `MessageListScreen` → `MessageChatScreen` | `features/dispatcher/` | Thread list → 1:1 chat |

---

## 17. Offline & Sync Architecture (Mobile)

### Core Components

```
              ┌─────────────────────────────────────┐
              │           ConnectivityMonitor         │
              │  (connectivity_plus → Stream<bool>)   │
              └────────────────┬────────────────────┘
                               │ isOnline stream
              ┌────────────────▼────────────────────┐
              │           ActionQueue                │
              │  Persistent FIFO queue (LocalDB)    │
              │  UUID idempotency keys               │
              │  Replay on reconnect                  │
              └────────────────┬────────────────────┘
                               │
              ┌────────────────▼────────────────────┐
              │           DeltaSyncService            │
              │  Cursor-based incremental sync        │
              │  GET /api/v1/mobile/sync?since=...    │
              └────────────────┬────────────────────┘
                               │
              ┌────────────────▼────────────────────┐
              │           LocalDatabase               │
              │  JSON file cache (app documents dir) │
              │  Namespaces: transports, sync_cursors│
              │  action_queue, default                │
              └─────────────────────────────────────┘
```

### Action Queue Detail

```dart
class QueuedAction {
  final String id;           // UUID v4 (idempotency key)
  final String endpoint;     // e.g., "/api/v1/mobile/transports/123/status"
  final String method;       // PATCH
  final Map<String, dynamic> data;  // body
  final DateTime createdAt;
  int retryCount;
}

class ActionQueue {
  Future<void> enqueue(endpoint, method, data);  // returns UUID
  Future<void> dequeue(id);
  Future<void> replayAll(executor);  // FIFO order
    // On success → dequeue
    // On 409/404 → dequeue (permanent failure → ConflictHandler message)
    // On transient → keep in queue, retry next cycle
}
```

### Conflict Resolution

Server-wins strategy with user-facing messages in Romanian:

```dart
class ConflictHandler {
  resolveStatusConflict(transportId, attemptedStatus, currentStatus) → String
  resolveReassignConflict(transportId, attemptedDriver) → String
  resolveExpiredAction(actionDescription) → String
}
```

### Delta Sync

```dart
class DeltaSyncService {
  sync(entityType):        // Read cursor → GET delta → cache → update cursor
  fullSync(entityType):    // Ignore cursor, fetch all
  getLastCursor(entityType) → String
  updateCursor(entityType, cursor)
}
```

### WebSocket

```dart
class WebSocketClient {
  // Auto-reconnect: exponential backoff 1s → 30s max
  // Heartbeat: 30-second ping
  // Auth: ?token=<jwt> query param
  // Stream: messages → Stream<Map<String, dynamic>>
}
```

---

## 18. Security Architecture

### Defense Layers

| Layer | Implementation |
|-------|---------------|
| **Transport** | HTTPS (TLS 1.2+) assumed in production |
| **Rate limiting** | 100 req/min per IP (Redis sorted sets, in-memory fallback) |
| **Authentication** | JWT (HS256, 15 min expiry) + opaque refresh tokens |
| **Authorization** | `PermissionService` (REST) + RBAC dependencies (FastAPI) |
| **API keys** | HMAC-compared global key + SHA-256 hashed per-partner keys |
| **Brute-force** | 5 failures / 5 min → 15 min lockout (per-email) |
| **SQL injection** | Parameterized queries + column allowlisting |
| **Multi-tenancy** | `company_id` contextvars enforced in every repository query |
| **Input sanitization** | Middleware strips control chars, injection payloads |
| **XSS** | CSP header + input sanitization |
| **CORS** | Explicit origin allowlist |
| **Idempotency** | 24h key-based deduplication for POST/PATCH/PUT |
| **Encryption at rest** | Fernet for sensitive fields (SMTP passwords, provider credentials) |
| **Webhook security** | HMAC-SHA256 signature verification |
| **Security headers** | HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, Cross-Origin-Resource-Policy |
| **Audit logging** | `operation_events` table for all write operations |
| **Device trust** | Mobile device_id + FCM token registration, deactivation on logout |
| **Biometric lock** | Local mobile authentication via `local_auth` |

### Password Policy

- bcrypt, 12 rounds
- 72-byte input truncation (matching bcrypt's limit)
- Min length: 6, max: 72 (actual enforced max)
- Constant-time comparison via `hmac.compare_digest`

### Error Handling

All API errors return RFC 7807 ProblemDetail:

```json
{
    "error_code": "TOKEN_INVALID",
    "detail": "Invalid or expired access token."
}
```

Error codes defined in `backend/errors.py` (ErrorCode enum).

---

## 19. Testing Strategy

### Test Count by Category

| Category | Count | Tooling |
|----------|-------|---------|
| Unit tests | ~100 | pytest |
| Integration tests | 12 | pytest + test DB |
| Security tests | ~25 | pytest (hypothesis + custom) |
| Load tests | ~20 | Locust + pytest |
| Stress tests | ~15 | pytest |
| Mutation tests | ~20 | pytest |
| Readiness tests | 546 | pytest |
| Mobile unit/widget tests | ~50 | flutter_test |
| Mobile integration tests | ~10 | integration_test |

### Desktop Test Structure

```
tests/
├── test_*.py               # Unit tests for services, views, models
├── security/               # AuthZ matrix, SQL injection, XSS, tenant isolation, etc.
├── loadtest/               # Locust + pytest: trips, routes, OCR, GPS, copilot
├── stress/                 # Large datasets, concurrent ops, connection pool, GPS 10k
├── migrations/             # Migration correctness tests
└── readiness/ (546 tests)  # Pre-release regression suite
```

### Mobile Test Structure

```
test/
├── core/                   # Auth, token, biometric, interceptor, websocket, sync
├── features/auth/          # Login, session expired screen tests
├── features/copilot/       # Copilot endpoints, models, state machine, screen
├── features/driver/        # Trip overview, route share, driver shell nav
├── features/dispatcher/    # Shell, home, fleet map, alerts, approvals
├── features/settings/      # Settings screen
├── features/teams/         # Driver list filters
├── features/route_planner/ # Route planner
├── features/profit_calculator/ # Calculator logic + screen
├── shared/models/          # All model serialization tests
├── widgets/                # Shared widget golden tests
├── i18n/                   # Localization coverage
├── integration_test/       # Full-app integration tests
├── connectivity_test.dart  # Connectivity monitor
├── offline_queue_test.dart # Action queue replay
└── sync_service_test.dart  # Delta sync
```

### Business Invariants (107 rules)

| Category | Count | Run Frequency |
|----------|-------|--------------|
| Financial | 15 | Every commit + nightly |
| Fleet | 7 | Every commit |
| Drivers | 7 | Every commit |
| Trips | 10 | Every commit |
| Routes | 8 | Every commit |
| Documents | 7 | Every commit |
| Dispatch | 7 | Every commit |
| Auth & Security | 7 | Every commit + PR |
| Multi-Tenant | 6 | Every PR |
| Database | 8 | After migration + nightly |
| AI / ARGO | 6 | Weekly |
| Freight Exchange | 6 | Weekly |
| Analytics | 6 | Before release |
| Workflows | 7 | Before release |

---

## 20. Business Invariants

107 automated business rules ensuring data integrity. Key invariants:

### Financial (FIN-001 to FIN-015)
- Net profit = revenue − all costs
- VAT amount must be taxable_amount × vat_rate / 100
- No negative invoice totals after discounts
- Payment amounts cannot exceed invoice total
- Currency conversion must be logged

### Fleet (FLE-001 to FLE-007)
- No two trucks can have the same plate within a company
- A truck cannot be assigned to two drivers simultaneously
- Health score must be 0-100
- Maintenance on a decommissioned truck is not allowed

### Drivers (DRV-001 to DRV-007)
- License expiry must be in the future for active drivers
- A driver cannot have overlapping trips
- Tachograph weekly driving limit: 3360 min

### Trips (TRP-001 to TRP-010)
- Status transitions must follow the defined state machine
- A trip can only have one truck at a time
- Price must be non-negative
- End date cannot precede start date

### Multi-Tenant (MTN-001 to MTN-006)
- All queries must be scoped by company_id
- Company A cannot see Company B's data
- Admin role bypasses company scoping

---

## 21. Configuration & Deployment

### Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPERION_DB_PATH` | No | `data/cashflow.db` | SQLite database path |
| `OPERION_DB_ENGINE` | No | `sqlite` | `sqlite` or `postgresql` |
| `OPERION_JWT_SECRET_KEY` | **Yes (prod)** | — | JWT signing secret |
| `OPERION_GRAPHHOPPER_URL` | No | `http://localhost:8989` | GraphHopper server |
| `OPERION_GRAPHHOPPER_KEY` | No | — | GraphHopper API key |
| `OPERION_SMTP_HOST` | No | — | SMTP server for emails |
| `OPERION_SMTP_PORT` | No | 587 | |
| `OPERION_SMTP_USER` | No | — | SMTP username |
| `OPERION_SMTP_PASSWORD` | No | — | SMTP password (Fernet encrypted) |
| `OPERION_FLEET_TRACKING` | No | 0 | Enable GPS integrations |
| `OPERION_API_HOST` | No | `127.0.0.1` | API bind address |
| `OPERION_API_PORT` | No | 8000 | API port |
| `OPERION_API_KEY` | **Yes (prod)** | — | Legacy API key for machine clients |
| `OPERION_ADMIN_EMAIL` | No | — | Admin gateway email (zero-DB auth) |
| `OPERION_ADMIN_PASSWORD_HASH` | No | — | Admin bcrypt hash (zero-DB auth) |
| `OPERION_REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection |
| `OPERION_RATE_LIMIT` | No | 100 | Max requests/min per IP |
| `OPERION_ENCRYPTION_KEY` | **Yes (with Fernet)** | — | Field-level encryption key |
| `OPERION_CORS_ORIGINS` | No | `*` | Allowed CORS origins |
| `OPERION_BCRYPT_ROUNDS` | No | 12 | bcrypt work factor |

### Deployment Topology

```
Development:
  Desktop app + SQLite (single binary)
  OR
  Docker Compose: FastAPI + PostgreSQL + Redis + Celery

Production:
  ┌─────────────────┐
  │  Desktop Clients │ ←─ PySide6 app per user
  └─────────────────┘
         │ HTTP + WebSocket
  ┌──────▼──────┐
  │  nginx/Caddy │  ←─ reverse proxy + TLS termination
  └──────┬──────┘
  ┌──────▼──────┐    ┌──────────┐    ┌──────────┐
  │  FastAPI     │ ←─ │ Redis    │    │ Celery   │
  │  (gunicorn)  │    │          │    │ Workers  │
  └──────┬──────┘    └──────────┘    └──────────┘
  ┌──────▼──────┐
  │  PostgreSQL  │
  └─────────────┘
         │
  ┌──────▼──────┐
  │  Mobile Apps │ ←─ Flutter (Android/iOS)
  └─────────────┘
```

### Build & Run

```bash
# Desktop (local mode)
python main.py

# Desktop (remote mode — connect to running backend)
python main.py

# Backend
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000

# Docker (full stack)
docker-compose -f compose.yaml up

# Mobile
cd mobile_app
flutter run --dart-define=OPERION_API_KEY=<key>

# Mobile (release)
flutter build apk --dart-define=OPERION_API_KEY=<key>
# or
flutter build ios --dart-define=OPERION_API_KEY=<key>
```

### Mobile Build Secrets

```sh
# API key passed at build time via --dart-define
OPERION_API_KEY=<key>  # must match backend's OPERION_API_KEY
```

---

> **End of Blueprint**
>
> This document is a living reference. When you encounter a discrepancy between this document and the source code, the source code is authoritative. Please update this document to reflect changes.
