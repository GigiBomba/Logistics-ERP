# Database_Rework.md — Operion ERP SQLite → PostgreSQL Migration Master Blueprint

> **Phase:** Analysis Only (Phase 1 of 2)  
> **Status:** ✅ Complete — Ready for Phase 2 Implementation  
> **Application State:** Unchanged (zero modifications)  
> **Generated:** 2026-07-13  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Application Architecture](#2-application-architecture)
3. [Complete Database Interaction Inventory](#3-complete-database-interaction-inventory)
4. [Schema Audit](#4-schema-audit)
5. [SQLite-Specific Features Inventory](#5-sqlite-specific-features-inventory)
6. [Transaction Architecture Audit](#6-transaction-architecture-audit)
7. [Connection Lifecycle Audit](#7-connection-lifecycle-audit)
8. [Thread Safety Audit](#8-thread-safety-audit)
9. [ORM Readiness & Abstraction Scoring](#9-orm-readiness--abstraction-scoring)
10. [Query Complexity Report](#10-query-complexity-report)
11. [AI Readiness Audit](#11-ai-readiness-audit)
12. [Filesystem Assumptions](#12-filesystem-assumptions)
13. [Architectural Problems](#13-architectural-problems)
14. [Database Architecture Diagram](#14-database-architecture-diagram)
15. [Migration Difficulty Heatmap](#15-migration-difficulty-heatmap)
16. [PostgreSQL Readiness Score](#16-postgresql-readiness-score)
17. [Migration Roadmap](#17-migration-roadmap)
18. [Appendix](#18-appendix)

---

## 1. Executive Summary

| Metric | Count |
|---|---|
| **Total production files touching SQLite** | ~70 |
| **Total test files touching SQLite** | ~30 |
| **Repository files** | 27 |
| **Service files** | 86 |
| **Backend API endpoint files** | 9 |
| **Database core files** | 3 |
| **SQL migration files** | 3 |
| **Schema files (DDL)** | 1 (1246 lines) |
| **Tables** | ~40 |
| **Indexes** | 100+ |
| **Foreign keys** | 19 |
| **Triggers** | 6 |
| **FTS5 virtual tables** | 1 |
| **SQLite-specific SQL patterns** | 15 categories, ~300+ instances |
| **Direct SQL in API (bypasses repos)** | ~60 statements in 11 files |
| **Total SQL statements (production)** | ~650+ |
| **Existing PostgreSQL support** | ~15% (experimental, incomplete) |
| **Estimated migration effort** | 5-6 weeks |

---

## 2. Application Architecture

### 2.1 Dual-Mode Design

```
┌──────────────────────────────────────────────────────────────────┐
│                    OPERION ERP ARCHITECTURE                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐     ┌──────────────────────────────────────┐   │
│  │ Desktop App   │     │        Web App (React 19 + Vite)     │   │
│  │ (PySide6/Qt) │     │   ui/src/ → api.ts → HTTP fetch      │   │
│  │              │     │                                       │   │
│  │ main.py      │     │   localStorage JWT token              │   │
│  │ main_remote  │     │   ↓ HTTP REST                        │   │
│  │     .py      │     └──────────────┬───────────────────────┘   │
│  └──┬───────┬───┘                    │                            │
│     │       │                        │                            │
│     │ Local │ Remote                 │                            │
│     │ Mode  │ Mode                   │                            │
│     │       │                        │                            │
│     ▼       ▼                        ▼                            │
│  ┌──────────────┐    ┌──────────────────────────────────────┐   │
│  │ Database     │    │         FastAPI Backend                │   │
│  │ Manager      │    │   backend/main.py                      │   │
│  │ (Direct      │◄───│   backend/dependencies.py              │   │
│  │  SQLite)     │    │                                        │   │
│  └──────┬───────┘    │   ┌────────────────────────────────┐  │   │
│         │            │   │  API Routes (v1)                │  │   │
│         │            │   │  ├── admin.py   ★ direct SQL    │  │   │
│         │            │   │  ├── auth.py    ★ direct SQL    │  │   │
│         │            │   │  ├── registration.py            │  │   │
│         │            │   │  ├── users.py                   │  │   │
│         │            │   │  ├── fleet.py                   │  │   │
│         │            │   │  ├── webhooks.py                │  │   │
│         │            │   │  ├── health.py                  │  │   │
│         │            │   │  ├── gdpr.py                    │  │   │
│         │            │   │  └── waitlist.py                │  │   │
│         │            │   └────────────────────────────────┘  │   │
│         │            │   ┌────────────────────────────────┐  │   │
│         │            │   │ Celery Workers (background)     │  │   │
│         │            │   │ ocr_tasks, maintenance_tasks,    │  │   │
│         │            │   │ document_tasks                  │  │   │
│         │            │   └────────────────────────────────┘  │   │
│         │            └──────────────┬───────────────────────┘   │
│         │                           │                            │
│         ▼                           ▼                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  SERVICE LAYER (86 files)                 │   │
│  │  trip, fleet, client, document, analytics, route,         │   │
│  │  operations, dispatch, automail, invoicing,               │   │
│  │  document_automation, currency, tacho, ...                │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              REPOSITORY LAYER (27 files)                  │   │
│  │  BaseRepository → 26 specialized repositories             │   │
│  │  All use `self.db.conn.execute()` with `?` placeholders   │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  DATABASE LAYER (3 files)                  │   │
│  │  DatabaseManager → ConnectionPool → sqlite3.connect()     │   │
│  │  schema.py (all DDL)   migrations/*.sql                   │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│                           ▼                                      │
│                  ┌─────────────────┐                             │
│                  │  data/cashflow.db│                             │
│                  │  (SQLite file)   │                             │
│                  └─────────────────┘                             │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Desktop App Dual Mode

| Component | Local Mode (`main.py`) | Remote Mode (`main_remote.py`) |
|---|---|---|
| Database | `DatabaseManager(Config.DB_PATH)` → SQLite | `None` (no local DB) |
| Services | `FleetService(db)`, `TripService(db)`, etc. | `RemoteFleetService(api_client)`, etc. |
| Operations | `OperationsEngine(db, prefs)` | `RemoteOpsStub(api_client)` |
| Preferences | `PreferencesManager(db)` | `RemotePreferences()` |

### 2.3 Web Framework Stack

- **Backend:** FastAPI (Python)
- **Frontend:** React 19 + TypeScript + Vite 6 + TailwindCSS 4
- **Desktop:** PySide6/Qt
- **Async Tasks:** Celery + Redis
- **Web UI DB Access:** Exclusively through FastAPI REST API — zero direct DB access from browser

---

## 3. Complete Database Interaction Inventory

### 3.1 Files That Import `sqlite3`

| File | Type | Notes |
|---|---|---|
| `database/db_manager.py` | Core | DatabaseManager class |
| `database/connection_pool.py` | Core | ConnectionPool for SQLite |
| `repositories/tag_repository.py` | Repository | Only repo importing sqlite3 (catches `IntegrityError`) |
| `backend/api/v1/admin.py` | API | Direct `import sqlite3` for raw queries |
| `scripts/backfill_clients.py` | Script | Migration script |
| `scripts/backfill_truck_id.py` | Script | Migration script |
| `scripts/migrate_dates.py` | Script | Migration script |
| `scripts/restore_data_from_backup.py` | Script | Backup restore |
| `tests/integration/conftest.py` | Test | Test fixtures |
| `tests/test_db_manager.py` | Test | Unit tests |
| `tests/test_connection_pool.py` | Test | Pool tests |
| `tests/test_document_automation.py` | Test | Doc automation tests |
| `tests/test_cmr_generator.py` | Test | CMR tests |
| `tests/test_schema.py` | Test | Schema tests |
| `tests/test_helpers.py` | Test | Test helpers |
| `tests/test_missing_repositories.py` | Test | Coverage tests |
| `tests/chaos/*.py` (6 files) | Test | Chaos engineering |
| `tests/readiness/*.py` (2 files) | Test | Readiness tests |
| `tests/mutation/*.py` (1 file) | Test | Mutation tests |

### 3.2 Connection Creation Points

| File | Method | Type |
|---|---|---|
| `database/connection_pool.py:68` | `sqlite3.connect(self._db_path)` | Primary pool (thread-local) |
| `database/db_manager.py:147-173` | `sqlite3.connect(uri, uri=True)` | Read-only connection |
| `backend/dependencies.py:57-81` | `DatabaseManager(Config.DB_PATH)` | FastAPI singleton |
| `main.py:170-171` | `DatabaseManager(Config.DB_PATH)` | Desktop app instance |
| `backend/celery_app/tasks/ocr_tasks.py:19,108` | `DatabaseManager(...)` | Per-task instance |
| `backend/celery_app/tasks/document_tasks.py:26,87` | `DatabaseManager(...)` | Per-task instance |
| `backend/celery_app/tasks/maintenance_tasks.py:17` | `DatabaseManager(...)` | Per-task instance |
| `scripts/backfill_clients.py:105,110,114` | `sqlite3.connect(DB_PATH)` | Direct, no pool |
| `scripts/backfill_truck_id.py:177,182,186` | `sqlite3.connect(DB_PATH)` | Direct, no pool |
| `scripts/migrate_dates.py:277,286,300,306` | `sqlite3.connect(DB_PATH)` | Direct, no pool |
| `scripts/restore_data_from_backup.py:121` | `sqlite3.connect(backup_path)` | Backup file |

### 3.3 Direct SQL in API Endpoints (bypassing repositories)

| File | Direct SQL Queries | Transactions |
|---|---|---|
| `backend/api/v1/admin.py` | 12+ `db.conn.execute()` | — |
| `backend/api/v1/auth.py` | 2 `db.conn.execute()` | 1 `db.conn.commit()` |
| `backend/api/v1/registration.py` | 3 `db.conn.execute()` | commit + rollback |
| `backend/api/v1/users.py` | 3 `db.conn.execute()` | 4 `db.conn.commit()` |
| `backend/api/v1/webhooks.py` | 2 `db.conn.execute()` | 2 `db.conn.commit()` |
| `backend/api/v1/health.py` | 2 `db.conn.execute()` | — |
| `backend/api/v1/gdpr.py` | PRAGMA queries | 2 `db.conn.commit()` |
| `backend/api/v1/fleet.py` | 1 `db.conn.execute()` | — |
| `backend/dependencies_security.py` | 2 `db.conn.execute()` | — |
| `backend/oauth2.py` | 5 `db.conn.execute()` | 3 `db.conn.commit()` |
| `backend/celery_app/tasks/ocr_tasks.py` | 2 `db.conn.execute()` | 1 `db.conn.commit()` |
| `backend/celery_app/tasks/maintenance_tasks.py` | 1 `db.conn.execute()` | 1 `db.conn.commit()` |

### 3.4 Repository Layer — Complete Table

| Repository | Tables | Transactions | Score |
|---|---|---|---|
| `__init__.py` (BaseRepository) | N/A (base class) | begin/commit/rollback | 1 |
| `alert_repository.py` | alerts | YES | 1 |
| `analytics_repository.py` | trips, trucks, invoices, clients, documents | NO | 3 |
| `api_key_repository.py` | api_keys | NO | 1 |
| `audit_repository.py` | operation_events | YES | 1 |
| `automail_repository.py` | automail_*, email_logs, invoice_reminders | YES | 2 |
| `client_repository.py` | clients, trips, invoices | YES | 2 |
| `contact_repository.py` | client_contacts | YES | 1 |
| `document_repository.py` | documents, document_links, document_versions, contracts, document_templates, documents_fts | YES (BEGIN IMMEDIATE) | 2 |
| `driver_repository.py` | drivers | NO | 1 |
| `driver_truck_assignment_repository.py` | driver_truck_assignments, trucks, drivers | YES | 1 |
| `fleet_repository.py` | trucks, maintenance_records, maintenance_schedules, truck_health_scores | NO | 2 |
| `invoice_repository.py` | invoices, trips, clients | NO | 2 |
| `payment_profile_repository.py` | payment_profiles | NO | 1 |
| `pipeline_repository.py` | pipeline_runs, pipeline_packages, package_items | YES | 2 |
| `proforma_repository.py` | proforma_invoices | NO | 1 |
| `receipt_repository.py` | receipts | NO | 1 |
| `route_event_repository.py` | route_events | NO | 1 |
| `route_repository.py` | route_history_v2, trips | NO (PRAGMA) | 2 |
| `settings_repository.py` | settings | NO | 1 |
| `successive_carrier_repository.py` | successive_carriers | YES | 1 |
| `tacho_driver_activity_repository.py` | tacho_driver_activity | NO | 1 |
| `tacho_import_repository.py` | tacho_imports | NO | 1 |
| `tacho_vehicle_data_repository.py` | tacho_vehicle_data, tacho_imports | NO | 2 |
| `tag_repository.py` ★ imports sqlite3 directly | client_tags | NO | 1 |
| `trip_repository.py` | trips, trucks, invoices | YES | 2 |
| `truck_route_assignment_repository.py` | truck_route_assignments, route_history_v2 | NO | 1 |
| `user_repository.py` | users | NO | 1 |

---

## 4. Schema Audit

### 4.1 Complete Table Inventory (40 tables)

**Core Business:**
`trips`, `invoices`, `proforma_invoices`, `clients`, `drivers`, `trucks`, `routes`, `route_history`, `route_history_v2`, `route_events`, `truck_route_assignments`

**Fleet Maintenance:**
`maintenance_records`, `maintenance_schedules`, `truck_health_scores`

**Documents:**
`documents`, `documents_fts` (FTS5), `document_links`, `document_versions`, `contracts`, `document_templates`

**Document Automation:**
`document_pipeline_runs`, `document_package`, `document_package_items`

**CMR System:**
`cmr_counter`, `cmr_audit_log`, `successive_carriers`

**Operations & Audit:**
`alerts`, `operation_events`, `trip_status_history`

**Tachograph:**
`tacho_imports`, `tacho_driver_activity`, `tacho_vehicle_data`

**Financial:**
`receipts`, `payment_profiles`

**AutoMail/Dunner:**
`automail_templates`, `automail_schedules`, `automail_client_overrides`, `automail_settings`, `email_logs`, `invoice_reminders`

**Multi-Tenant & Auth:**
`companies`, `users`, `settings`, `api_keys`, `oauth2_clients`, `webhook_events`, `waitlist_entries`, `gps_telemetry`

**System:**
`schema_migrations`

### 4.2 Foreign Keys (19)

| From Table | Column | To Table | On Delete |
|---|---|---|---|
| `trips` | `trip_id` | `trips(id)` | CASCADE |
| `invoices` | `trip_id` | `trips(id)` | CASCADE |
| `email_logs` | `trip_id` | `trips(id)` | — |
| `invoice_reminders` | `invoice_id` | `invoices(id)` | — |
| `trucks` | `truck_id` | `trucks(id)` | — |
| `routes` | `route_id` | `routes(id)` | — |
| `route_history_v2` | `route_id` | `route_history_v2(id)` | SET NULL / CASCADE |
| `alerts` | `trip_id` | `trips(id)` | CASCADE |
| `operation_events` | `company_id` | `companies(id)` | — |
| `trip_status_history` | `trip_id` | `trips(id)` | CASCADE |
| `maintenance_records` | `truck_id` | `trucks(id)` | CASCADE |
| `maintenance_schedules` | `truck_id` | `trucks(id)` | CASCADE |
| `truck_health_scores` | `truck_id` | `trucks(id)` | CASCADE |
| `driver_truck_assignments` | `driver_id` | `drivers(id)` | CASCADE |
| `driver_truck_assignments` | `truck_id` | `trucks(id)` | CASCADE |
| `successive_carriers` | `trip_id` | `trips(id)` | CASCADE |
| `document_package_items` | `package_id` | `document_package(id)` | CASCADE |
| `automail_schedules` | `template_id` | `automail_templates(id)` | — |
| `cmr_audit_log` | `trip_id` | `trips(id)` | — |

### 4.3 Triggers (6)

- `documents_fts_ai` — AFTER INSERT sync FTS5
- `documents_fts_ad` — AFTER DELETE sync FTS5
- `documents_fts_au` — AFTER UPDATE sync FTS5
- `trg_pipeline_runs_stage_check` — BEFORE INSERT stage validation
- `trg_pipeline_runs_stage_check_upd` — BEFORE UPDATE stage validation
- `trg_pipeline_runs_status_check` — BEFORE INSERT status validation
- `trg_pipeline_runs_status_check_upd` — BEFORE UPDATE status validation

### 4.4 SQL Migrations

- `database/migrations/api_keys.sql` — API keys table creation
- `database/migrations/002_create_celery_user.sql` — Celery database user (PostgreSQL)
- `database/migrations/003_add_gps_telemetry_company_id.sql` — Multi-tenant column addition
- `database/schema.py` — ~60 ALTER TABLE ADD COLUMN statements embedded inline

### 4.5 Views

**None**

---

## 5. SQLite-Specific Features Inventory

### 5.1 Critical — Must Replace Before PostgreSQL Works

| Feature | Count | PostgreSQL Replacement | Risk |
|---|---|---|---|
| **AUTOINCREMENT** | ~48 in schema.py | `GENERATED ALWAYS AS IDENTITY` / `SERIAL` | 🔴 HIGH |
| **INTEGER PRIMARY KEY** (implicit autoincrement) | ~72 locations | `BIGINT GENERATED ALWAYS AS IDENTITY` | 🔴 HIGH |
| **`?` parameter placeholders** | ~100+ across all repos + scripts + API | `$1`/`$2` or `%s` (psycopg2) | 🔴 HIGH |
| **FTS5 virtual tables** (`documents_fts`) | 1 table + 3 triggers + ~8 query points | `tsvector`/`tsquery` with GIN indexes | 🔴 HIGH |
| **`INSERT OR IGNORE`** | ~54 occurrences | `INSERT ... ON CONFLICT DO NOTHING` | 🟡 MEDIUM |
| **`INSERT OR REPLACE`** | ~10 occurrences | `INSERT ... ON CONFLICT DO UPDATE SET ...` | 🟡 MEDIUM |
| **`datetime('now')`** | ~27 occurrences | `CURRENT_TIMESTAMP` or `now()` | 🟡 MEDIUM |
| **`SUBSTR()`** | ~9 occurrences | `SUBSTRING()` | 🟡 MEDIUM |
| **`last_insert_rowid()`** | ~100+ (mostly tests) | `INSERT ... RETURNING id` | 🟡 MEDIUM |
| **`sqlite_master`** | ~39 occurrences | `information_schema.tables` / `pg_catalog` | 🟡 MEDIUM |
| **PRAGMA statements** | ~12 occurrences | N/A (native in PostgreSQL) | 🟡 MEDIUM |

### 5.2 Moderate — Requires Adaptation

| Feature | Count | PostgreSQL Replacement | Risk |
|---|---|---|---|
| **`row_factory = sqlite3.Row`** | 3 locations | `RealDictCursor` or `DictCursor` (psycopg2) | 🟢 LOW |
| **`BEGIN IMMEDIATE`** | 2 locations | `BEGIN` (standard) works | 🟢 LOW |
| **WAL journal mode** | 1 location | N/A (automatic in PostgreSQL) | 🟢 LOW |
| **`executemany()`** | 6 locations | `execute_batch()` (psycopg2 extras) | 🟢 LOW |
| **`cursor.lastrowid`** | ~15 locations | `cursor.fetchone()[0]` after `RETURNING` | 🟢 LOW |
| **Read-only URI connection** | 1 location | Read-only connection string | 🟢 LOW |
| **TRIGGER with `RAISE(ABORT,...)`** | 4 triggers | `RAISE EXCEPTION '...'` | 🟡 MEDIUM |

### 5.3 Schema-Level Issues

| Issue | Details |
|---|---|
| **`GENERATED ALWAYS AS` column** (`trips.month`) | `TEXT GENERATED ALWAYS AS (SUBSTR(created_at, 1, 7)) STORED` — PostgreSQL syntax differs |
| **TEXT for dates** | All timestamps stored as `TEXT` (ISO-8601). PostgreSQL handles this but `TIMESTAMPTZ` is better |
| **No explicit BOOLEAN** | Boolean fields stored as `INTEGER` (0/1) — PostgreSQL has native `BOOLEAN` |
| **SQLite-specific date functions** | `JULIANDAY()`, `DATE(... 'weekday N')`, `DATE(... '+' || months || ' months')` |
| **Rowid references in FTS5** | `content_rowid='id'` in documents_fts — no PostgreSQL equivalent |

---

## 6. Transaction Architecture Audit

### 6.1 Critical Issues

#### Issue #1: BaseRepository Auto-Commits by Default
**File:** `repositories/__init__.py:109-113`

```python
def _execute(self, query: str, params: tuple = (), commit: bool = True) -> None:
    q = self._adapt_query(query)
    self.db.conn.execute(q, params)
    if commit:
        self.db.conn.commit()   # AUTO-COMMIT on every call by default
```

**Problem:** Every repository method that calls `_execute()` or `_execute_insert()` with default parameters commits after every single statement. Services calling multiple repository methods get multiple independent commits instead of one atomic transaction.

**PostgreSQL impact:** Multiple round-trips with individual commits is extremely expensive (WAL flush per commit). Partial failures leave data inconsistent.

**Recommended fix:** Change default `commit=True` to `commit=False`. Force callers to explicitly manage commits. Add a `transaction()` context manager.

---

#### Issue #2: Nested Transaction in Audit Repository Without Rollback
**File:** `repositories/audit_repository.py:55-78`

```python
try:
    self.begin_transaction()                      # Line 58
    try:
        self._execute(..., commit=False)
        self._execute(..., commit=False)
        self.commit_transaction()                 # Line 72
    except Exception:
        self.rollback_transaction()               # Line 74
        raise
except Exception as e:                            # Line 76
    import logging
    logging.getLogger("audit_repo").warning("Audit log write failed: %s", e)
    # ← NO ROLLBACK! Transaction remains open indefinitely
```

**Problem:** If `begin_transaction()` succeeds but inner `commit_transaction()` fails, outer `except` catches re-raised exception, logs it, but **never calls rollback**. Transaction stays open, holding locks.

**PostgreSQL impact:** Locked rows until end of transaction. Unreleased locks cause deadlocks and blocking.

**Recommended fix:** Call `rollback_transaction()` in outer `except` before logging.

---

#### Issue #3: CMR Counter Retry Loop Uses Plain `BEGIN`
**File:** `repositories/trip_repository.py:85-120`

```python
def get_next_cmr_sequence(self, year: int) -> tuple[str, int]:
    for attempt in range(3):
        try:
            self.begin_transaction()       # Uses "BEGIN", NOT "BEGIN IMMEDIATE"
            row = self._fetchone(...)      # SELECT
            # compute new sequence
            self._execute(..., commit=False)
            self.commit_transaction()
            break
        except Exception as e:
            self.rollback_transaction()
            if attempt < 2:
                time.sleep(0.1)
                continue
```

**Problem:** Uses plain `BEGIN` instead of `BEGIN IMMEDIATE`. Two concurrent threads could both read the same value and try to write the same sequence number.

**PostgreSQL impact:** PostgreSQL MVCC would handle this differently with row-level locks. `SELECT ... FOR UPDATE` needed.

**Recommended fix:** Use `BEGIN IMMEDIATE` for write transactions. Better yet: use `INSERT ... RETURNING` or database-level sequences.

---

#### Issue #4: Transaction Ownership Conflicts
**File:** `services/client_service.py:401-419`

```python
self._repo.begin_transaction()              # SERVICE starts transaction
moved_trips = self._repo.reassign_trips()   # Each may auto-commit internally
moved_invoices = self._repo.reassign_invoices()
moved_contacts = self._repo.reassign_contacts()
self._repo.reassign_tags()
self._repo.deactivate(from_id, commit=False)
self._repo.commit_transaction()             # SERVICE commits
```

**Problem:** Service thinks it controls the transaction, but repository methods have inconsistent commit behavior. `reassign_trips` calls `_execute_insert()` with `commit=False` (correct), but other methods may auto-commit.

**Recommended fix:** All repository write methods should default to `commit=False` when inside a service-managed transaction.

---

#### Issue #5: No Savepoint Usage in Production Code
**Problem:** Zero `SAVEPOINT`/`ROLLBACK TO`/`RELEASE SAVEPOINT` usage. Without savepoints, nested operations cannot selectively rollback within a transaction.

**Recommended fix:** Add `savepoint()` context manager to BaseRepository for nested operations.

---

### 6.2 Missing Rollback Paths

| File | Function | Issue |
|---|---|---|
| `repositories/document_repository.py:370-396` | `delete_batch()` | Rollback failure silently swallowed |
| `services/document_automation/document_grouper.py:246-252` | Link document | Rollback in `contextlib.suppress(Exception)` |
| `backend/api/v1/registration.py:107-111` | Registration | Original exception lost after rollback |

---

## 7. Connection Lifecycle Audit

### 7.1 Connection Lifecycle Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONNECTION LIFECYCLE                              │
├─────────────────────────────────────────────────────────────────────┤

  DESKTOP APP (PySide6)          FASTAPI BACKEND               CELERY WORKERS
  ────────────────────           ───────────────                ──────────────
  main.py:171                    dependencies.py:57             ocr_tasks.py:19
  DatabaseManager()              init_db() singleton            DatabaseManager()
       │                              │                              │
       ▼                              ▼                              ▼
  ConnectionPool()               ConnectionPool()              ConnectionPool()
  (thread-local, WAL)            (thread-local, WAL)           (per-task, WAL)
       │                              │                              │
       │── UI thread conn1            │── worker1 conn1              │── task conn1
       │── worker thread conn2        │── worker2 conn2              │   db.close() ✓
       │── worker thread conn3        │── worker3 conn3              │
       │                              │── worker4 conn4              │── task conn2
       ▼                              ▼                              │   db.close() ✓
  main.py:287                   shutdown hook:                       │
  db.close() ✓                  _db_instance.close() ✓           maintenance_tasks:17
                                                                db.close() ❌ LEAK
```

### 7.2 Connection Ownership

| Type | Owner | Closer | Lifetime | Risk |
|---|---|---|---|---|
| Desktop app DM | `main.py` (local var) | `main.py:287` | App process | ✅ OK |
| FastAPI singleton | `_db_instance` (global) | `_shutdown_db()` hook | App process | ✅ OK |
| Celery task DMs | Each task (local) | Task's `finally:` | Per task | ✅ OK* |
| Script DMs | Each script (local) | Script's explicit `.close()` | Script run | ✅ OK |
| Read-only conn | `admin.py` (local) | `admin.py:336 finally:` | Per request | ✅ OK |
| Direct sqlite3 in scripts | Each script | Each script's `.close()` | Script run | ✅ OK |

\* Exception: `maintenance_tasks.py:17` — `cleanup_expired_data()` creates `DatabaseManager` but **never calls `db.close()`**. 🔴 LEAK

### 7.3 Connection Leaks

| File | Function | Severity |
|---|---|---|
| `backend/celery_app/tasks/maintenance_tasks.py:17` | `cleanup_expired_data()` | 🔴 CRITICAL |
| `scripts/alert_checker.py:138` | `run_checks()` | 🔴 CRITICAL |

### 7.4 PostgreSQL-Specific Connection Concerns

1. **`PostgresConnectionPool.close_all()` only returns current thread's cached connection** — other threads' cached connections are orphaned.
2. **`get_cached_connection()` holds connections forever** — long-running threads hold connections indefinitely.
3. **Pool exhaustion risk** — `get_connection()` requires manual return via `return_connection()`. Easy to forget.
4. **Multi-worker uvicorn** — each worker process has its own singleton (safe by process isolation).

---

## 8. Thread Safety Audit

### 8.1 Thread Model

| Component | Thread Model | DB Access | Risk |
|---|---|---|---|
| Desktop UI (PySide6) | Main thread + QThread workers | Via DatabaseManager (thread-local) | ✅ Safe |
| PipelineWorker | QThread | Gets thread-local connection | ✅ Safe |
| AsyncTask (UI) | QThread | Callable may access DB → thread-local | ⚠️ Low risk |
| OcrService | 2 `threading.Thread` daemons | Shared DatabaseManager → thread-local | ✅ Safe |
| FastAPI handlers | Async event loop | Sync DB calls from async | ⚠️ Blocking risk |
| Celery workers | Separate processes | Each process has own DB file handle | ⚠️ Write contention |

### 8.2 Critical Findings

| # | Finding | Severity | File |
|---|---|---|---|
| 1 | CMR counter uses `BEGIN` instead of `BEGIN IMMEDIATE` | 🟡 MEDIUM | `repositories/trip_repository.py:85-120` |
| 2 | Multiple Celery workers writing same SQLite file | 🟡 MEDIUM | `backend/celery_app/tasks/` |
| 3 | FastAPI async handlers calling sync DB without `run_in_executor` | 🟡 MEDIUM | `backend/dependencies.py:84-89` |
| 4 | `PreferencesManager` not thread-safe if shared | 🟢 LOW | `services/preferences.py:87-92` |
| 5 | `BaseRepository.begin_transaction()` uses plain `BEGIN` | 🟢 LOW | `repositories/__init__.py:134-135` |
| 6 | `OcrService` shares `DatabaseManager` reference with worker threads | 🟢 LOW | `services/document/ocr_service.py:28-46` |

### 8.3 PostgreSQL Thread Safety Model Comparison

| Aspect | SQLite | PostgreSQL |
|---|---|---|
| Connection model | One per thread (thread-local) | Pooled, shared across threads |
| Write concurrency | Serialized (file lock) | Row-level locks, MVCC |
| Read concurrency | WAL allows concurrent reads | MVCC, snapshot isolation |
| Thread-safety | Requires thread-local storage | Built-in via `ThreadedConnectionPool` |
| Multi-process | File-level locking | Connection pool per process |
| GIL interaction | Releases during I/O wait in C code | Same via psycopg2 |

---

## 9. ORM Readiness & Abstraction Scoring

### 9.1 Scoring Key

| Score | Meaning |
|---|---|
| **0** | Perfect abstraction (DB details completely hidden) |
| **1** | Minor SQL leakage (one or two SQL-specific calls) |
| **2** | Mixed SQL and business logic (interleaved) |
| **3** | Heavy SQLite coupling (many SQLite-specific features) |
| **4** | Nearly impossible to migrate cleanly (deeply embedded SQLite) |

### 9.2 Scores by Layer

#### DATABASE LAYER (All Score 4)

| Module | Score | Reason |
|---|---|---|
| `database/schema.py` | 4 | 1246 lines of pure SQLite DDL |
| `database/connection_pool.py` | 4 | `sqlite3.connect()`, PRAGMA, WAL, thread-local |
| `database/db_manager.py` | 4 | PRAGMA, sqlite_master, datetime('now'), BEGIN IMMEDIATE, 1000+ lines |

#### REPOSITORIES — Ranked Easiest to Hardest

| Repository | Score | Key Issue |
|---|---|---|
| `tag_repository.py` | 1 | Clean CRUD, only imports sqlite3 for IntegrityError |
| `settings_repository.py` | 1 | Minor: sqlite_master in get_table_names() |
| `payment_profile_repository.py` | 1 | Clean CRUD |
| `contact_repository.py` | 1 | Clean CRUD with transaction pair |
| `user_repository.py` | 1 | Clean CRUD |
| `proforma_repository.py` | 1 | Clean CRUD |
| `receipt_repository.py` | 1 | Clean CRUD |
| `driver_repository.py` | 1 | Clean parameterized queries |
| `successive_carrier_repository.py` | 1 | Clean CRUD with bulk replace |
| `tacho_import_repository.py` | 1 | Clean CRUD |
| `tacho_driver_activity_repository.py` | 1 | Clean CRUD |
| `route_event_repository.py` | 1 | Clean CRUD |
| `audit_repository.py` | 1 | Clean parameterized queries |
| `alert_repository.py` | 1 | Batch insert pattern, clean |
| `driver_truck_assignment_repository.py` | 1 | JOINs clean, no engine-specific code |
| `api_key_repository.py` | 1 | Minor: datetime('now') in UPDATE |
| `truck_route_assignment_repository.py` | 1 | JOINs clean |
| `tacho_vehicle_data_repository.py` | 2 | ROW_NUMBER() window function, correlated subquery |
| `automail_repository.py` | 2 | Complex multi-table LEFT JOINs, datetime('now') |
| `invoice_repository.py` | 2 | Multi-table JOINs, COALESCE |
| `document_repository.py` | 2 | FTS5 MATCH, BEGIN IMMEDIATE, FTS rebuild |
| `fleet_repository.py` | 2 | `date('now', '+' || months || ' months')`, interval arithmetic |
| `client_repository.py` | 2 | `SUBSTR(start_date, 1, 7)` for month extraction |
| `trip_repository.py` | 2 | `JULIANDAY()` date arithmetic, CMR retry loop |
| `route_repository.py` | 2 | ON CONFLICT upsert, datetime(? ), PRAGMA in migration |
| `analytics_repository.py` | 3 | JULIANDAY, SUBSTR, DATE arithmetic, CTEs, ROW_NUMBER — heavily coupled |

#### BACKEND API

| Module | Score | Reason |
|---|---|---|
| `backend/api/v1/fleet.py` | 1 | Properly delegates to FleetService |
| `backend/api/v1/auth.py` | 2 | Direct SQL, mixed state management |
| `backend/api/v1/registration.py` | 2 | Direct `db.conn.execute()` for user/company |
| `backend/api/v1/users.py` | 2 | Direct raw SELECT/INSERT/UPDATE |
| `backend/api/v1/webhooks.py` | 2 | Direct `db.conn.execute()` |
| `backend/api/v1/health.py` | 2 | Raw `SELECT 1` |
| `backend/api/v1/admin.py` | 2 | `import sqlite3`, raw SQL in diagnostics |
| `backend/api/v1/gdpr.py` | 3 | PRAGMA table_info, dynamic SQL iteration |

#### SCRIPTS (All Score 4)

| Module | Reason |
|---|---|
| `scripts/seed_production_company.py` | Direct `db.conn.execute()` raw SQL, cursor.lastrowid |
| `scripts/backfill_clients.py` | Raw `sqlite3.connect()`, raw SQL strings |
| `scripts/backfill_truck_id.py` | Raw UPDATE with subqueries |
| `scripts/migrate_dates.py` | Complex date loops with raw UPDATE |
| `scripts/restore_data_from_backup.py` | sqlite_master, raw INSERT OR IGNORE |

#### SERVICES (Sampled)

| Module | Score | Reason |
|---|---|---|
| `services/trip_service.py` | 1 | Properly delegates to repositories |
| `services/fleet_service.py` | 1 | Properly delegates to repositories |
| `services/document_service.py` | 1 | Properly delegates to repositories |
| `services/analytics_service.py` | 1 | Properly delegates to repositories |
| `services/trip_context.py` | 3 | Direct `db_manager.add_trip()` — bypasses repo |
| `services/preferences.py` | 3 | Direct `db.get_settings()`, `db.save_setting()` |
| `services/health_check.py` | 3 | Raw `SELECT 1`, SettingsRepository for sqlite_master |

---

## 10. Query Complexity Report

### 10.1 Overall Statistics

| Metric | Count |
|---|---|
| **Total SQL Statements (production)** | ~650+ |
| **SELECT** | ~300+ |
| **INSERT** | ~65+ |
| **UPDATE** | ~60+ |
| **DELETE** | ~50+ |
| **JOINs** (all types) | 67 |
| **GROUP BY** | 59 |
| **ORDER BY** | 150+ |
| **HAVING** | 1 |
| **UNION/UNION ALL** | 0 (in prod code) |
| **Subqueries** | 15+ |
| **Window Functions** (ROW_NUMBER) | 2 |
| **CTEs** (WITH...AS) | 1 |
| **Transactions** (BEGIN/COMMIT/ROLLBACK) | 45 |
| **Bulk operations** (executemany) | 7 |
| **Dynamic SQL** (f-strings) | 200+ |

### 10.2 Top 5 Most Complex Queries

| Rank | Query | File | Lines | Tables | Risk |
|---|---|---|---|---|---|
| 1 | `get_client_payment_timeline` | `analytics_repository.py` | 616-667 | 3 + 2 CTEs | 🔴 HIGH |
| 2 | `get_tacho_status_data` | `tacho_vehicle_data_repository.py` | 46-65 | 4 | 🔴 HIGH |
| 3 | `get_latest_per_truck` | `tacho_vehicle_data_repository.py` | 68-79 | 3 | 🟡 MEDIUM |
| 4 | `get_driver_monthly_activity` | `analytics_repository.py` | 669-690 | 1 | 🟡 MEDIUM |
| 5 | `get_revenue_quarterly` | `analytics_repository.py` | 581-592 | 1 | 🟡 MEDIUM |

### 10.3 PostgreSQL Compatibility Issues in Queries

| Pattern | Locations | Fix |
|---|---|---|
| `JULIANDAY()` | 5 in analytics_repository.py | `EXTRACT(EPOCH FROM ...)` |
| `DATE(... 'weekday N')` | 2 in analytics_repository.py | `date_trunc('week', ...)` |
| `SUBSTR()` | 9 across analytics, client, fleet | `SUBSTRING()` |
| `DATE(... '+' || months || ' months')` | 2 in fleet_repository.py | `INTERVAL '1 month' * months` |
| `datetime('now')` | 27 across repos + schema | `CURRENT_TIMESTAMP` |
| `FTS5 MATCH` | 8 in document_repository.py | `tsvector @@ tsquery` |
| `INSERT OR IGNORE` | 54 across repos + API | `ON CONFLICT DO NOTHING` |
| `INSERT OR REPLACE` | 10 across repos | `ON CONFLICT DO UPDATE SET` |

### 10.4 Files with Highest SQL Density

| File | SQL Density | Complexity |
|---|---|---|
| `repositories/analytics_repository.py` | 95% | Very High |
| `repositories/tacho_vehicle_data_repository.py` | 80% | High |
| `repositories/invoice_repository.py` | 75% | Medium-High |
| `repositories/client_repository.py` | 70% | Medium-High |
| `repositories/fleet_repository.py` | 65% | Medium |
| `repositories/trip_repository.py` | 60% | Medium |

---

## 11. AI Readiness Audit

### 11.1 Readiness Scorecard

| Category | Status | Risk |
|---|---|---|
| UUID Readiness | ❌ CRITICAL — all PKs are INTEGER AUTOINCREMENT | 🔴 HIGH |
| Primary Key Consistency | ⚠️ `settings` has composite PK; `cmr_counter` has no PK | 🟡 MEDIUM |
| Foreign Key Consistency | ⚠️ 18 tables without FKs; `trips` missing FK to `drivers` | 🟡 MEDIUM |
| Timestamp Consistency | ✅ 28 tables have `created_at`; 14 have `updated_at` | 🟢 LOW |
| Soft Delete Readiness | ❌ ZERO soft-delete columns anywhere | 🔴 HIGH |
| Audit Logging | ⚠️ Logs creates/updates/deletes; missing reads/permission denials | 🟡 MEDIUM |
| Conversation Storage | ❌ ZERO tables for AI conversations or messages | 🔴 HIGH |
| Full-Text Search | ⚠️ Only documents have FTS; no BM25 ranking | 🟡 MEDIUM |
| Index Quality | ✅ 100+ indexes, good coverage | 🟢 LOW |
| Multi-Tenant Isolation | ⚠️ 17 tables lack `company_id` (including documents) | 🟡 MEDIUM |
| Vector Search | ❌ No pgvector; no embedding storage | 🔴 HIGH |
| Schema Extensibility | ✅ 20+ JSON columns; settings key-value pattern reusable | 🟢 LOW |

### 11.2 Critical Gaps for AI

#### Must Fix BEFORE PostgreSQL Migration (Security & AI Foundation)

| # | Gap | Tables Affected | Effort |
|---|---|---|---|
| 1 | **Add `company_id` to documents** | documents, client_contacts, client_tags | Medium |
| 2 | **Add missing FK constraints** | trips (driver_id, truck_id → FK) | Medium |
| 3 | **Add soft delete columns** (`deleted_at`) | All business tables | Medium |
| 4 | **Convert TEXT → TIMESTAMPTZ** | All timestamp columns | Easy |

#### Must Fix BEFORE AI Development Starts

| # | Gap | Tables Needed | Effort |
|---|---|---|---|
| 5 | **Create conversation storage** | ai_conversations, ai_messages, ai_tool_calls | Easy |
| 6 | **Expand audit logging** | Add READ, PERMISSION_DENIED event types | Medium |
| 7 | **Add FTS indexes for trips, clients, invoices** | New FTS5 tables (or wait for PostgreSQL tsvector) | Medium |

#### Should Do AFTER PostgreSQL Migration

| # | Gap | Effort |
|---|---|---|
| 8 | **Add UUID primary keys** (keep INTEGER as internal) | Medium |
| 9 | **Add pgvector** for embeddings | Medium |
| 10 | **Add database rate limiting** | Medium |
| 11 | **Add BM25 ranking** to FTS | Easy |

### 11.3 AI Table Designs (Proposed — Do NOT Implement Now)

```sql
-- ai_conversations: Session-level tracking
CREATE TABLE ai_conversations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conv_uuid UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id),
    company_id INTEGER NOT NULL REFERENCES companies(id),
    model TEXT NOT NULL DEFAULT 'gpt-4',
    title TEXT,
    token_count_total INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ai_messages: Individual message-level tracking
CREATE TABLE ai_messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES ai_conversations(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    tokens INTEGER DEFAULT 0,
    latency_ms INTEGER,
    metadata_json JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ai_tool_calls: Tool executions
CREATE TABLE ai_tool_calls (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES ai_conversations(id),
    message_id BIGINT REFERENCES ai_messages(id),
    tool_name TEXT NOT NULL,
    arguments_json JSONB,
    result_json JSONB,
    success BOOLEAN,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

---

## 12. Filesystem Assumptions

### 12.1 Complete Inventory

| Assumption | Location(s) | PostgreSQL Impact |
|---|---|---|
| Hardcoded filename `cashflow.db` | `config.py:9`, `backend/config.py:13`, 4 scripts | Must change to DSN/connection string |
| DB in `data/` subdirectory | `utils/resource_path.py:68` via `_app_dir()` | No longer file-based |
| `os.path.exists()` DB checks | `services/health_check.py:54`, 3 scripts | Replace with connection pool health check |
| `shutil.copy2()` database backups | 3 backfill scripts | Use `pg_dump` |
| `sqlite3.connect()` auto-creates file | `connection_pool.py:68` | PostgreSQL needs explicit `CREATE DATABASE` |
| `os.path.isfile(db_path)` | `services/route_planner_controller.py:370` | Connection check instead |
| `file:` URI for read-only | `database/db_manager.py:170` | Read-only connection string |
| Backup directory `data/backups/` | `scripts/restore_data_from_backup.py:25` | Use pg_dump directory |
| `.db` file extension | Multiple locations | N/A (PostgreSQL uses DSN) |

### 12.2 `data_path()` Function Behavior

```python
# utils/resource_path.py:68
def data_path(relative_path: str) -> str:
    return os.path.join(_app_dir(), relative_path)
```

- **Development:** Returns `<project_root>/data/cashflow.db`
- **Packaged:** Returns `<exe_dir>/data/cashflow.db`
- `Config.DB_PATH` env var (`OPERION_DB_PATH`) overrides this

---

## 13. Architectural Problems

### 13.1 Critical Issues (🔴)

1. **Direct SQL in API endpoints** — 11 API files bypass repositories entirely (~60 direct SQL statements)
2. **Multiple connection factory patterns** — `main.py`, `dependencies.py`, Celery tasks, scripts all create DatabaseManager differently
3. **Global database singleton** — `backend/dependencies.py` uses thread-locked singleton shared across all API requests
4. **Tight coupling to SQLite** — `db_manager.py` contains extensive PRAGMA/sqlite_master logic mixed with business logic
5. **FTS5 search embedded in document_repository** — ~8 query points use FTS5-specific MATCH + rowid references

### 13.2 Moderate Issues (🟡)

6. **Business logic mixed with SQL** — API endpoints contain validation + SQL in same functions
7. **Duplicate queries across layers** — User lookups appear in both `dependencies_security.py` and `auth.py`
8. **Missing PostgreSQL migration path** — `database/migrations/` only has 3 SQL files, none for PostgreSQL DDL
9. **`PostgresConnectionPool` is a stub** — 131-line stub with minimal implementation
10. **Schema migration system tied to SQLite** — `_run_column_migrations()` uses `PRAGMA table_info` + `ALTER TABLE`

### 13.3 Low Issues (🟢)

11. **30+ test files hardcode SQLite** — direct `import sqlite3`, `sqlite3.connect()` in tests
12. **`tag_repository.py` imports sqlite3** — only repository doing this (for `IntegrityError`)
13. **`route_planner_controller.py` checks `os.path.isfile(db_path)`** — filesystem assumption

---

## 14. Database Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       DATABASE ARCHITECTURE                               │
│                         Connection Flow                                   │
├──────────────────────────────────────────────────────────────────────────┤

   ┌──────────────────────────────────────────────────────────────────┐
   │                        ENTRY POINTS                               │
   │                                                                    │
   │  main.py ────► DatabaseManager(DB_PATH) ────► ConnectionPool      │
   │  main_remote.py ────► ApiClient ────► HTTP (no local DB)         │
   │  backend/main.py ────► create_app() ────► init_db() singleton     │
   │  celery_app/tasks/* ────► DatabaseManager() per task              │
   │  scripts/* ────► sqlite3.connect() direct                         │
   └──────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │                     DATABASE LAYER                                │
   │                                                                    │
   │  DatabaseManager                                                  │
   │  ├── conn (property) ────► ConnectionPool.conn (thread-local)     │
   │  ├── _init_db() ────► schema.py DDL execution                     │
   │  ├── _run_column_migrations() ────► ALTER TABLE via PRAGMA        │
   │  ├── _seed_automail_defaults() ────► Default data seeding         │
   │  ├── open_readonly_connection() ────► Direct sqlite3 connect      │
   │  └── close() ────► ConnectionPool.close_all()                     │
   │                                                                    │
   │  ConnectionPool (SQLite)                                           │
   │  ├── _local = threading.local()                                   │
   │  ├── conn (property) ────► sqlite3.connect() per thread           │
   │  ├── PRAGMA journal_mode=WAL                                      │
   │  ├── PRAGMA foreign_keys=ON                                       │
   │  ├── row_factory = sqlite3.Row                                    │
   │  └── check_same_thread=True                                       │
   │                                                                    │
   │  PostgresConnectionPool (Stub, incomplete)                         │
   │  └── psycopg2.pool.ThreadedConnectionPool                          │
   └──────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │                     REPOSITORY LAYER                               │
   │                                                                    │
   │  BaseRepository                                                    │
   │  ├── _adapt_query() ────► ? → %s for PostgreSQL                   │
   │  ├── _company_filter() ────► Multi-tenant scoping                 │
   │  ├── _execute() ────► db.conn.execute() + auto-commit             │
   │  ├── _execute_insert() ────► INSERT + lastrowid                   │
   │  ├── _execute_with_count() ────► UPDATE/DELETE + rowcount         │
   │  ├── begin_transaction() ────► "BEGIN" (should be BEGIN IMMEDIATE)│
   │  ├── commit_transaction() ────► db.conn.commit()                  │
   │  └── rollback_transaction() ────► db.conn.rollback()              │
   │                                                                    │
   │  26 Specialized Repositories (each wrapping a single table domain) │
   │  All use: self.db.conn.execute() with ? placeholders               │
   └──────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │                     SERVICE LAYER                                  │
   │                                                                    │
   │  86 service files across:                                          │
   │  ├── Core: trip, fleet, client, document, analytics, route        │
   │  ├── Financial: invoicing/*, payment_*, currency/*                │
   │  ├── Operations: operations/*, dispatch_service/*                 │
   │  ├── Document: document/*, document_automation/*                  │
   │  ├── Communication: automail/*                                    │
   │  └── Infrastructure: health_check, preferences, app_state         │
   │                                                                    │
   │  Most delegate to repositories (clean).                            │
   │  Exceptions: trip_context, preferences, health_check —             │
   │  call DatabaseManager directly, bypassing repositories.            │
   └──────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │                     PRESENTATION LAYER                             │
   │                                                                    │
   │  Desktop (PySide6/Qt)               Web (React 19 + TypeScript)   │
   │  ┌── main_window.py                 ┌── ui/src/lib/api.ts         │
   │  ├── views/* (40+ view files)       ├── fetch() with JWT          │
   │  ├── widgets/* (20+ widgets)        └── localStorage tokens       │
   │  ├── dialogs/*                                                     │
   │  └── delegates/*                     Web UI: ZERO direct DB access │
   │                                      All data via REST API         │
   │  Desktop: Direct DB (local mode)                                    │
   │  OR HTTP API (remote mode)                                         │
   └──────────────────────────────────────────────────────────────────┘

                            THREAD FLOW
                            ───────────

   Main Thread (Qt Event Loop):
   ├── DatabaseManager ──► ConnectionPool ──► thread-local conn_1
   └── UI rendering, signal handling

   QThread Workers (PipelineWorker, AsyncTask):
   ├── DatabaseManager (same instance, different thread)
   └── ConnectionPool ──► thread-local conn_2, conn_3, ...

   threading.Thread Workers (OcrService):
   ├── DatabaseManager (shared reference)
   └── ConnectionPool ──► thread-local conn_4, conn_5

   FastAPI Workers (asyncio event loop):
   ├── DatabaseManager (singleton, per process)
   └── ConnectionPool ──► thread-local conn per worker

   Celery Workers (separate processes):
   └── DatabaseManager (per task, per process)
       └── ConnectionPool ──► per-process connection

                            TRANSACTION FLOW
                            ────────────────

   Repository-Level:
   ├── begin_transaction() ──► "BEGIN"
   ├── _execute(commit=False) ──► db.conn.execute()
   ├── _execute(commit=False) ──► db.conn.execute()
   └── commit_transaction() / rollback_transaction()

   API-Level (bypassing repositories):
   ├── db.conn.execute("INSERT ...")
   ├── db.conn.execute("INSERT ...")
   └── db.conn.commit() / db.conn.rollback()

   Script-Level (raw sqlite3):
   ├── conn.execute("UPDATE ...")
   └── conn.commit()
```

---

## 15. Migration Difficulty Heatmap

### 15.1 Safest Modules (Low Risk — Weeks 1-2)

| Rank | Module | Score | Rationale |
|---|---|---|---|
| 1 | `tag_repository.py` | 1 | Clean CRUD, just needs `?` → `%s` |
| 2 | `settings_repository.py` | 1 | Clean CRUD, minor sqlite_master fix |
| 3 | `payment_profile_repository.py` | 1 | Pure CRUD |
| 4 | `contact_repository.py` | 1 | CRUD + transaction pair |
| 5 | `user_repository.py` | 1 | Pure CRUD |
| 6 | `proforma_repository.py` | 1 | CRUD + number generation |
| 7 | `receipt_repository.py` | 1 | CRUD + number generation |
| 8 | `driver_repository.py` | 1 | Clean parameterized queries |
| 9 | `tacho_import/repository.py` | 1 | Pure CRUD |
| 10 | `tacho_driver_activity_repository.py` | 1 | Pure CRUD |
| 11 | `route_event_repository.py` | 1 | Pure CRUD |
| 12 | `audit_repository.py` | 1 | Clean queries (but transaction bug needs fix) |
| 13 | `alert_repository.py` | 1 | Batch insert pattern, clean |
| — | `backend/api/v1/fleet.py` | 1 | Delegates to FleetService |
| — | `services/trip_service.py` | 1 | Delegates to repos |
| — | `services/fleet_service.py` | 1 | Delegates to repos |
| — | `services/document_service.py` | 1 | Delegates to repos |

### 15.2 Medium-Risk Modules (Weeks 2-3)

| Rank | Module | Score | Key Migration Issue |
|---|---|---|---|
| 14 | `driver_truck_assignment_repository.py` | 1 | JOIN queries need `%s` conversion |
| 15 | `truck_route_assignment_repository.py` | 1 | JOIN queries |
| 16 | `api_key_repository.py` | 1 | `datetime('now')` → `CURRENT_TIMESTAMP` |
| 17 | `tacho_vehicle_data_repository.py` | 2 | ROW_NUMBER() supported, needs testing |
| 18 | `automail_repository.py` | 2 | Complex JOINs, datetime('now') |
| 19 | `invoice_repository.py` | 2 | Multi-table JOINs |
| 20 | `fleet_repository.py` | 2 | `date(... '+' || months)` → INTERVAL |
| 21 | `client_repository.py` | 2 | `SUBSTR(...)` → `SUBSTRING(...)` |
| 22 | `route_repository.py` | 2 | ON CONFLICT syntax, PRAGMA removal |
| 23 | `pipeline_repository.py` | 2 | executemany → execute_batch |
| 24 | `trip_repository.py` | 2 | `JULIANDAY()` removal, CMR counter fix |
| — | `backend/api/v1/health.py` | 2 | Raw SQL → repository call |
| — | `backend/api/v1/webhooks.py` | 2 | Raw SQL → repository call |
| — | `backend/api/v1/registration.py` | 2 | Raw SQL → UserRepository |
| — | `backend/api/v1/users.py` | 2 | Raw SQL → UserRepository |
| — | `backend/api/v1/auth.py` | 2 | Raw SQL → proper service |
| — | `backend/oauth2.py` | 2 | Raw SQL → OAuth2Repository |

### 15.3 High-Risk Modules (Weeks 3-4)

| Rank | Module | Score | Key Migration Issue |
|---|---|---|---|
| 25 | `document_repository.py` | 2 | FTS5 → tsvector (hardest single repo) |
| 26 | `backend/api/v1/gdpr.py` | 3 | PRAGMA table_info, dynamic SQL |
| 27 | `services/trip_context.py` | 3 | Direct db_manager calls |
| 28 | `services/preferences.py` | 3 | Direct db_manager calls |
| 29 | `services/health_check.py` | 3 | Raw SQL, sqlite_master |
| 30 | `analytics_repository.py` | 3 | JULIANDAY, SUBSTR, DATE arithmetic everywhere |
| 31 | `backend/api/v1/admin.py` | 2 | 12+ queries with PRAGMA, raw SQL, read-only conn |

### 15.4 Critical Modules (Week 4-5)

| Rank | Module | Score | Key Migration Issue |
|---|---|---|---|
| 32 | `database/db_manager.py` | 4 | Complete rewrite of schema init, migrations, seeding |
| 33 | `database/schema.py` | 4 | All 40 tables need PostgreSQL DDL |
| 34 | `database/connection_pool.py` | 4 | Complete PostgresConnectionPool implementation |
| 35 | `scripts/*` (6 files) | 4 | Must retire or rewrite completely |

---

## 16. PostgreSQL Readiness Score

### 16.1 Category Scores

| Category | Score | Notes |
|---|---|---|
| **Architecture** | 45/100 | Dual-mode design is solid; direct SQL in API is the biggest weakness |
| **Maintainability** | 50/100 | Repositories exist but are inconsistently used; API bypasses them |
| **Thread Safety** | 70/100 | Thread-local connections are well-designed; a few race conditions exist |
| **Scalability** | 30/100 | SQLite's write serialization limits multi-Celery-worker throughput |
| **Security** | 55/100 | Parameterized queries used throughout; but 17 tables lack company_id |
| **AI Readiness** | 20/100 | No conversation storage, no soft delete, no vector support, no UUIDs |
| **Enterprise Readiness** | 35/100 | Missing audit logging for reads; no soft delete; file-based DB |
| **Migration Readiness** | 40/100 | Existing dual-engine flag is ~15% complete; most queries are SQLite-only |

### 16.2 Overall Readiness

```
████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  38/100

Current PostgreSQL readiness: 38%
```

### 16.3 What Each Score Means

- **Architecture (45/100):** The repository pattern exists and most services use it correctly. But 11 API endpoint files bypass repositories entirely with ~60 direct SQL statements. This must be fixed before PostgreSQL migration.

- **Maintainability (50/100):** Good patterns exist (BaseRepository, `_adapt_query()`, `_company_filter()`). But scripts are throwaway code with raw sqlite3, and schema.py is 100% SQLite-specific.

- **Thread Safety (70/100):** Thread-local ConnectionPool is well-designed. The main concerns are: CMR counter retry loop uses plain BEGIN, FastAPI async handlers block event loop on sync DB calls, and Celery multi-process write contention.

- **Scalability (30/100):** SQLite's single-writer model fundamentally limits write throughput. PostgreSQL would immediately improve Celery worker parallelism. Analytics queries are currently synchronous in async handlers.

- **Security (55/100):** Parameterized queries are used everywhere (good). But 17 tables lack `company_id` multi-tenant isolation — critical for SaaS deployment.

- **AI Readiness (20/100):** Almost nothing exists for AI. No conversation storage, no UUID PKs, no soft delete, no vector support, no FTS beyond documents. This is expected — AI development hasn't started yet.

- **Enterprise Readiness (35/100):** Missing soft delete, partial audit trail, file-based database, no read replicas. Suitable for current scale but not enterprise-grade.

- **Migration Readiness (40/100):** The dual-engine flag (`DB_ENGINE`) shows intent. `PostgresConnectionPool` exists but is incomplete. `_adapt_query()` handles `?` → `%s` conversion. But schema DDL is 100% SQLite, and no PostgreSQL migration files exist.

---

## 17. Migration Roadmap

### Phase 0: Pre-Migration Foundations (Week 0 — Concurrent with Phase 1)
**Objective:** Fix architectural issues that would complicate migration. **Do before touching any SQL.**

| Task | Files | Effort |
|---|---|---|
| P0.1: Add `transaction()` context manager to BaseRepository | `repositories/__init__.py` | 0.5 day |
| P0.2: Fix audit_repository.py missing rollback | `repositories/audit_repository.py:76-78` | 0.5 day |
| P0.3: Change `begin_transaction()` to `BEGIN IMMEDIATE` | `repositories/__init__.py:134-135` | 0.5 day |
| P0.4: Add `db.close()` to maintenance_tasks.py and alert_checker.py | 2 files | 0.5 day |
| P0.5: Fix CMR counter to use `BEGIN IMMEDIATE` | `repositories/trip_repository.py:85-120` | 0.5 day |
| P0.6: Add `company_id` to documents and related tables | `database/schema.py`, 5+ tables | 1 day |
| P0.7: Add soft delete columns (`deleted_at`) to all business tables | `database/schema.py` | 1 day |
| P0.8: Add missing FK constraints | `database/schema.py` | 1 day |

**Total Phase 0:** ~5 days  
**Verification:** Run full test suite. No behavior changes.  
**Rollback:** Revert commits. No data migration yet.

---

### Phase 1: Database Abstraction Layer (Week 1)
**Objective:** Complete the `PostgresConnectionPool` and make the codebase actually engine-agnostic.

| Task | Files | Effort |
|---|---|---|
| 1.1: Complete `PostgresConnectionPool` implementation | `database/connection_pool.py` | 2 days |
| 1.2: Add proper connection return (`return_connection`) in all code paths | `database/db_manager.py` | 1 day |
| 1.3: Create centralized placeholder adapter (remove per-repo `_adapt_query`) | `database/query_adapter.py` (NEW) | 1 day |
| 1.4: Refactor `DatabaseManager` engine dispatch — separate SQLite and PG paths | `database/db_manager.py` | 2 days |
| 1.5: Create Alembic migration framework (or custom PG migration runner) | `database/migrations/` | 1 day |

**Deliverables:**
- ✅ `DatabaseManager(engine="postgresql")` successfully connects to PostgreSQL
- ✅ All existing tests pass when run against SQLite (no regression)
- ✅ Placeholder adaptation works for both engines

**Rollback:** Switch `DB_ENGINE` back to `"sqlite"`.  
**DoD:** `health_check.py` returns green for both `check_database(sqlite)` and `check_database(postgresql)`.

---

### Phase 2: Schema Migration (Week 2)
**Objective:** Produce a working PostgreSQL schema identical to the SQLite schema.

| Task | Files | Effort |
|---|---|---|
| 2.1: Create `database/schema_pg.sql` — all 40 tables in PostgreSQL syntax | `database/schema_pg.sql` (NEW) | 3 days |
| 2.2: Convert all `INTEGER PRIMARY KEY AUTOINCREMENT` → `BIGINT GENERATED ALWAYS AS IDENTITY` | `database/schema_pg.sql` | (included) |
| 2.3: Convert FTS5 → tsvector (create `documents_search` tsvector column + GIN index + sync) | `database/schema_pg.sql` | 1 day |
| 2.4: Convert triggers: `RAISE(ABORT,...)` → `RAISE EXCEPTION '...'` | `database/schema_pg.sql` | 0.5 day |
| 2.5: Convert `GENERATED ALWAYS AS` column (`trips.month`) | `database/schema_pg.sql` | 0.5 day |
| 2.6: Convert `datetime('now')` → `CURRENT_TIMESTAMP` | `database/schema.py` (dual) | 0.5 day |
| 2.7: Add PostgreSQL migration files for existing schema versions | `database/migrations/` (NEW) | 0.5 day |

**Deliverables:**
- ✅ `schema_pg.sql` creates all 40+ tables in PostgreSQL
- ✅ `db_manager._init_db()` conditionally runs SQLite or PG schema
- ✅ All indexes, FKs, and triggers created

**Rollback:** Drop PostgreSQL database and recreate with `--engine sqlite`.  
**DoD:** `DatabaseManager(engine="postgresql")._init_db()` creates all tables without errors.

---

### Phase 3: Repository & API Migration (Weeks 3-4)
**Objective:** All queries work on PostgreSQL. Execute in dependency order (lowest-risk repos first).

#### Week 3 — Safe Repositories (Score 1)

| Task | Files | Effort |
|---|---|---|
| 3.1: Migrate repository batch 1 (tag, settings, payment_profile, contact, user, proforma, receipt) | 7 repos | 1 day |
| 3.2: Migrate repository batch 2 (driver, successive_carrier, tacho_import, tacho_driver_activity, route_event) | 5 repos | 1 day |
| 3.3: Migrate repository batch 3 (audit, alert, driver_truck_assignment, api_key, truck_route_assignment) | 5 repos | 1 day |
| 3.4: Migrate repository batch 4 (automail, invoice, fleet, client) | 4 repos | 1.5 days |
| 3.5: Migrate repository batch 5 (tacho_vehicle_data, route, pipeline, trip) | 4 repos | 1.5 days |

#### Week 4 — Complex Repositories & API Layer

| Task | Files | Effort |
|---|---|---|
| 3.6: Migrate `document_repository.py` (FTS5 → tsvector) | 1 repo | 2 days |
| 3.7: Migrate `analytics_repository.py` (JULIANDAY, SUBSTR, DATE arithmetic) | 1 repo | 2 days |
| 3.8: Refactor API endpoints to use repositories (health, webhooks, fleet, waitlist) | 4 API files | 1 day |
| 3.9: Refactor API endpoints (auth, registration, users, oauth2, dependencies_security) | 5 API files | 1.5 days |
| 3.10: Refactor API endpoints (admin, gdpr) | 2 API files | 1 day |
| 3.11: Migrate Celery tasks (ocr, maintenance, document) | 3 Celery task files | 0.5 day |

**For every file migrated:**
- Replace `?` → `%s` (or use centralized adapter)
- Replace `JULIANDAY()` → `EXTRACT(EPOCH FROM ...)`
- Replace `SUBSTR()` → `SUBSTRING()`
- Replace `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`
- Replace `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE SET`
- Replace `datetime('now')` → `CURRENT_TIMESTAMP`
- Replace `sqlite_master` → `information_schema.tables`
- Remove PRAGMA statements
- Replace `cursor.lastrowid` → `RETURNING id`
- Test both SQLite and PostgreSQL

**Rollback:** Each batch is independently revertible.  
**DoD:** Full test suite passes on BOTH SQLite and PostgreSQL.

---

### Phase 4: Service Layer & Scripts (Week 5)
**Objective:** Fix services that bypass repositories. Retire/rewrite scripts.

| Task | Files | Effort |
|---|---|---|
| 4.1: Refactor `trip_context.py` to use repositories | `services/trip_context.py` | 1 day |
| 4.2: Refactor `preferences.py` to use SettingsRepository | `services/preferences.py` | 0.5 day |
| 4.3: Refactor `health_check.py` — remove raw SQL, add PG health | `services/health_check.py` | 0.5 day |
| 4.4: Create data export/import tooling (SQLite → PostgreSQL) | `scripts/export_to_pg.py` (NEW) | 2 days |
| 4.5: Retire old scripts or rewrite with repository pattern | 6 scripts | 1 day |
| 4.6: Update `route_planner_controller.py` filesystem check | 1 file | 0.5 day |

**Rollback:** Keep original scripts as `.bak` files.  
**DoD:** Data export tool successfully migrates production data from SQLite to PostgreSQL.

---

### Phase 5: Testing & Validation (Week 5-6)
**Objective:** Full test coverage on PostgreSQL.

| Task | Effort |
|---|---|
| 5.1: Create PostgreSQL test fixtures (pytest fixture for PG) | 1 day |
| 5.2: Run full test suite against PostgreSQL | 2 days |
| 5.3: Fix all PostgreSQL-specific test failures | As needed |
| 5.4: Performance testing — query plan analysis, index optimization | 1 day |
| 5.5: Load test with concurrent web + Celery workers | 1 day |
| 5.6: Integration testing — full stack against PostgreSQL | 1 day |

**DoD:** All tests pass. Performance is equal or better than SQLite.

---

### Phase 6: Production Rollout (Week 6)
**Objective:** Zero-downtime migration.

| Task | Effort |
|---|---|
| 6.1: Create production PostgreSQL database and user | 0.5 day |
| 6.2: Run data migration (export SQLite → import PostgreSQL) | 0.5 day |
| 6.3: Run validation queries (row counts, checksums) | 0.5 day |
| 6.4: Deploy with `OPERION_DB_ENGINE=postgresql` flag (blue/green) | 0.5 day |
| 6.5: Smoke test all critical paths | 0.5 day |
| 6.6: Monitor for 24 hours | 1 day |
| 6.7: Remove SQLite fallback code (optional, Phase 6b) | 1 day |
| 6.8: Update deployment docs, .env.example, compose files | 0.5 day |
| 6.9: Update README with PostgreSQL setup instructions | 0.5 day |

**Rollback:** Set `OPERION_DB_ENGINE=sqlite`, point to backup.  
**DoD:** Production traffic running on PostgreSQL for 48 hours with zero errors.

---

### Phase 7: AI Readiness (Post-Migration — Not in This Scope)
**Objective:** Prepare database for Operion AI Co-Pilot.

| Task |
|---|
| 7.1: Add `ai_conversations`, `ai_messages`, `ai_tool_calls` tables |
| 7.2: Add `ai_token_usage` table for per-company billing |
| 7.3: Install pgvector extension, create `ai_document_embeddings` table |
| 7.4: Add BM25 ranking to document FTS |
| 7.5: Add UUID columns to all tables (keep INTEGER PKs) |
| 7.6: Expand audit logging to cover reads and permission denials |
| 7.7: Add database-driven rate limiting |

---

### Migration Order — File-Level (Dependency Graph)

```
Phase 0: Pre-Migration Fixes
  ├── repositories/__init__.py              (transaction context manager)
  ├── repositories/audit_repository.py      (rollback fix)
  ├── repositories/trip_repository.py       (CMR counter BEGIN IMMEDIATE)
  ├── backend/celery_app/tasks/maintenance_tasks.py (db.close() fix)
  └── scripts/alert_checker.py              (db.close() fix)

Phase 1: Database Abstraction Layer
  ├── database/connection_pool.py           (PostgresConnectionPool)
  ├── database/db_manager.py                (engine dispatch)
  ├── database/query_adapter.py             (NEW: centralized ? → %s)
  └── database/migrations/                  (Alembic setup)

Phase 2: Schema
  ├── database/schema_pg.sql               (NEW: PostgreSQL DDL)
  ├── database/schema.py                   (dual-engine schema dispatch)
  └── database/migrations/                 (PG migration files)

Phase 3: Repositories (by risk, lowest first)
  ├── repositories/tag_repository.py
  ├── repositories/settings_repository.py
  ├── repositories/payment_profile_repository.py
  ├── repositories/contact_repository.py
  ├── repositories/user_repository.py
  ├── repositories/proforma_repository.py
  ├── repositories/receipt_repository.py
  ├── repositories/driver_repository.py
  ├── repositories/successive_carrier_repository.py
  ├── repositories/tacho_import_repository.py
  ├── repositories/tacho_driver_activity_repository.py
  ├── repositories/route_event_repository.py
  ├── repositories/audit_repository.py
  ├── repositories/alert_repository.py
  ├── repositories/driver_truck_assignment_repository.py
  ├── repositories/api_key_repository.py
  ├── repositories/truck_route_assignment_repository.py
  ├── repositories/tacho_vehicle_data_repository.py
  ├── repositories/automail_repository.py
  ├── repositories/invoice_repository.py
  ├── repositories/fleet_repository.py
  ├── repositories/client_repository.py
  ├── repositories/route_repository.py
  ├── repositories/pipeline_repository.py
  ├── repositories/trip_repository.py
  ├── repositories/document_repository.py   (FTS5 → tsvector — HARDEST)
  └── repositories/analytics_repository.py  (JULIANDAY, SUBSTR — HARD)

Phase 3: API Layer
  ├── backend/api/v1/health.py
  ├── backend/api/v1/waitlist.py
  ├── backend/api/v1/webhooks.py
  ├── backend/api/v1/fleet.py
  ├── backend/api/v1/gdpr.py
  ├── backend/api/v1/users.py
  ├── backend/api/v1/registration.py
  ├── backend/api/v1/auth.py
  ├── backend/dependencies_security.py
  ├── backend/oauth2.py
  ├── backend/celery_app/tasks/maintenance_tasks.py
  ├── backend/celery_app/tasks/ocr_tasks.py
  └── backend/api/v1/admin.py              (12+ queries, PRAGMA — HARD)

Phase 4: Services & Scripts
  ├── services/trip_context.py
  ├── services/preferences.py
  ├── services/health_check.py
  ├── services/route_planner_controller.py
  ├── scripts/backfill_*.py (retire)
  ├── scripts/migrate_dates.py (retire)
  ├── scripts/restore_data_from_backup.py (rewrite for pg_dump)
  └── scripts/seed_production_company.py (rewrite)

Phase 5: Testing
Phase 6: Production Rollout
Phase 7: AI Readiness (future)
```

---

## 18. Appendix

### A. Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `OPERION_DB_PATH` | `data/cashflow.db` | SQLite database file path |
| `OPERION_DB_ENGINE` | `sqlite` | `sqlite` or `postgresql` |
| `OPERION_POSTGRES_DSN` | `""` | PostgreSQL connection string |
| `OPERION_DB_POOL_MIN` | `2` | Min connections in pool |
| `OPERION_DB_POOL_MAX` | `20` | Max connections in pool |
| `OPERION_REDIS_URL` | `redis://localhost:6379/0` | Redis cache |
| `OPERION_CELERY_BROKER` | `redis://localhost:6379/1` | Celery broker |

### B. Key Configuration Files

| File | Purpose |
|---|---|
| `config.py` | Desktop app configuration |
| `backend/config.py` | FastAPI backend configuration (Pydantic Settings) |
| `client/config.py` | Desktop client API configuration |
| `.env` / `.env.example` | Environment variable templates |
| `compose.yaml` / `compose.prod.yaml` | Docker Compose (includes PostgreSQL service) |

### C. Test Coverage

- **30+ test files** touch SQLite directly
- All tests must be updated to support PostgreSQL fixtures
- Chaos engineering tests specifically inject `sqlite3.OperationalError` / `sqlite3.DatabaseError`
- E2E tests hardcode `last_insert_rowid()` patterns — must switch to `RETURNING id`

### D. Glossary

| Term | Definition |
|---|---|
| **DatabaseManager** | Singleton/instance that wraps ConnectionPool and provides `conn` property |
| **ConnectionPool** | Thread-local SQLite connection pool (or psycopg2 pool for PG) |
| **BaseRepository** | Abstract repository with query helpers, placeholder adaptation, company scoping |
| **Direct SQL** | SQL executed on `db.conn` outside of repository pattern (in API endpoints) |
| **FTS5** | SQLite Full-Text Search virtual table (documents_fts) |
| **WAL** | Write-Ahead Logging — SQLite journal mode enabling concurrent reads |
| **JULIANDAY()** | SQLite date arithmetic function — not supported in PostgreSQL |
| **BEGIN IMMEDIATE** | SQLite transaction mode that acquires write lock immediately |

---

**END OF DATABASE_REWORK.MD**

*This document is the definitive blueprint for the Operion ERP SQLite → PostgreSQL migration. No migration code should be written without referencing this document. All Phase 2 implementation should follow the roadmap in Section 17.*
