# ARCHITECTURAL REWORK PLAN

## Comprehensive Blueprint for Decoupling the Operion ERP Monolith into a Distributed API Engine

---

# Preamble: System Audit Summary

## Current State (from codebase analysis)

| Dimension | Status | Count |
|---|---|---|
| **Services** (`services/`) | Mixed purity | 97 files, ~30 raw `conn.execute()` leaks |
| **Repositories** (`repositories/`) | BaseRepository exists | 24 files, wraps raw SQL, used inconsistently |
| **UI Views** (`ui/views/`) | Direct DB coupling | 19 views with ~41 `Repository(self.db)` instantiations |
| **API Layer** (`services/api_service.py`) | Stub | 24 lines — fuel & exchange only, no REST |
| **Database** | SQLite-only | `ConnectionPool` / thread-local, WAL mode, no SQLAlchemy |
| **Tests** | 110 files / 2,021+ pass | pytest + pytest-qt, per-module |
| **Config** (`config.py`) | Minimal | No server/port/Redis/Celery config |
| **Document Center** (`document_center_view.py`) | 2-tab QTabWidget | Documents tab + Automation tab, 1,778 lines |
| **Python** | 3.9 strict | `typing.List/Dict/Optional/Union` enforced |
| **Package Manager** | pip + requirements.txt | `pyproject.toml` defines dev/optional deps, no `uv` yet |

## Target Architecture

```
Desktop Client (PySide6)
  Document Center        Calculator          Route Planner
    Docs  Auto  API   all views use           All views
    [API Dashboard]   → ApiClient (httpx)     use ApiClient
                           │ HTTP/JSON
Nginx Reverse Proxy         :443 (SSL termination, rate-limiting, logging)
                           │
FastAPI Backend             :8000 (Uvicorn + Gunicorn)
  /api/v1/trips  /api/v1/documents  /api/v1/ocr
  /api/v1/clients /api/v1/routes    /api/v1/fleet
  /api/v1/analytics /api/v1/health
                           │
            Service Layer (pure, injected repos)
                           │
            Repository Layer (BaseRepository)
                           │
  DatabaseManager    Redis Cache     Celery Workers
  (PostgreSQL/SQLite)(read-through)  (OCR, PDF gen)
```

## Zero-Regression Contract

Before any refactoring, every phase must pass these invariants:

- **All 2,021+ tests remain green.** No test may be deleted; only patched to match new signatures.
- **Document Center tabs preserve order:** Tab 0 = Documents, Tab 1 = Automation, **Tab 2 = API Dashboard (new)**.
- **No existing DB schema changes.** New tables (Redis keyspace, Celery task metadata) are additive only.
- **Backward-compatible SQLite** remains the dev fallback. PostgreSQL is production-only, gated by `OPERION_DB_ENGINE=postgresql`.
- **`DatabaseManager.conn`** property is never removed — only wrapped and deprecated gracefully.
- **`DocumentService`** facade is preserved as a compat shim; new code uses focused sub-services.

## Critical Migration Boundaries

| What changes | How existing code is protected |
|---|---|
| Raw `conn.execute()` in services → Repository methods | Service tests continue using mock repositories |
| `Repository(self.db)` in UI → `ApiClient.get('/docs/...')` | New `ApiClient` has identical method signatures |
| SQLite → PostgreSQL | `DatabaseManager` gains `pg_conn` alongside `conn`; `connection_pool.py` gets PG variant |
| Direct function calls → HTTP/JSON | `APIService` (existing class) is expanded, not replaced |
| Sync workers → Celery tasks | Existing QThread workers are wrapped, not removed, until Celery is proven |

---

# PHASE 0: FOUNDATION — PROJECT RESTRUCTURING & CONFIG

## Objective

Prepare the repository for distributed architecture without changing any runtime behavior. Lay down directory scaffolding, config schema, and Python 3.9 compliance tooling.

## Dependencies

None — this is the starting point.

## Step-by-Step Tasks

### 0.1 Create the Backend API Package Structure

```
backend/
├── __init__.py
├── main.py                          # FastAPI app factory
├── config.py                        # pydantic Settings
├── dependencies.py                  # FastAPI dependency injection
├── api/
│   ├── __init__.py
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── router.py                # Aggregates all v1 routers
│   │   ├── trips.py                 # /api/v1/trips
│   │   ├── documents.py             # /api/v1/documents
│   │   ├── ocr.py                   # /api/v1/ocr
│   │   ├── clients.py              # /api/v1/clients
│   │   ├── fleet.py                 # /api/v1/fleet
│   │   ├── routes.py                # /api/v1/routes
│   │   ├── analytics.py             # /api/v1/analytics
│   │   └── health.py                # /api/v1/health
│   └── deps.py                      # get_db, get_current_user, etc.
├── schemas/
│   ├── __init__.py
│   ├── document.py                  # DocumentCreate, DocumentResponse, etc.
│   ├── trip.py
│   ├── client.py
│   ├── ocr.py                       # OcrRequest, OcrResult, OcrPayload
│   ├── fleet.py
│   └── common.py                    # Pagination, ErrorResponse
├── celery_app/
│   ├── __init__.py
│   ├── celery.py                    # Celery app instance
│   └── tasks/
│       ├── __init__.py
│       ├── ocr_tasks.py             # process_document_ocr
│       └── document_tasks.py        # generate_pdf, build_package
├── cache.py                         # Redis cache client wrapper
└── middleware/
    ├── __init__.py
    ├── logging_middleware.py
    └── rate_limit_middleware.py
```

### 0.2 Create the Desktop Client Package

```
client/
├── __init__.py
├── api_client.py                    # Centralized httpx client
├── auth.py                          # Auth token management (future)
└── cache.py                         # Local response cache
```

### 0.3 Extend `config.py` with Server Settings

Add to existing `Config` class:

```python
# Database engine selection
DB_ENGINE = os.environ.get("OPERION_DB_ENGINE", "sqlite")
POSTGRES_DSN = os.environ.get("OPERION_POSTGRES_DSN", "")
# Redis
REDIS_URL = os.environ.get("OPERION_REDIS_URL", "redis://localhost:6379/0")
REDIS_CACHE_TTL = int(os.environ.get("OPERION_REDIS_CACHE_TTL", "3600"))
# Celery
CELERY_BROKER_URL = os.environ.get("OPERION_CELERY_BROKER", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.environ.get("OPERION_CELERY_RESULT", "redis://localhost:6379/2")
# Server
API_HOST = os.environ.get("OPERION_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("OPERION_API_PORT", "8000"))
API_WORKERS = int(os.environ.get("OPERION_API_WORKERS", "4"))
# Client
API_BASE_URL = os.environ.get("OPERION_API_BASE_URL", "http://127.0.0.1:8000")
```

### 0.4 Add Dependencies to `requirements.txt`

```
# API & Server
fastapi>=0.109.0,<0.200.0
uvicorn[standard]>=0.27.0
gunicorn>=21.2.0
pydantic>=2.0.0,<3.0.0

# Async HTTP client (desktop ↔ API)
httpx>=0.27.0

# Distributed
celery[redis]>=5.3.0
redis>=5.0.0

# Database
psycopg2-binary>=2.9.0           # PostgreSQL driver
asyncpg>=0.29.0                   # Async PG (future)

# DevOps
python-dotenv>=1.0.0
```

### 0.5 Create Pydantic v2 Settings Schema

File: `backend/config.py`:

```python
from typing import Optional
from pydantic_settings import BaseSettings  # or pydantic BaseSettings for v2


class BackendSettings(BaseSettings):
    db_engine: str = "sqlite"
    db_path: str = "data/cashflow.db"
    postgres_dsn: Optional[str] = None
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_workers: int = 4
    model_config = {"env_prefix": "OPERION_"}
```

### 0.6 Set up `uv` Package Manager

- Install `uv` globally: `pip install uv`
- Create `uv.lock` via `uv pip compile requirements.txt`
- Update `pyproject.toml` with `[tool.uv]` config section
- Add `build.bat` / `build.sh` using `uv` instead of pip

### 0.7 Create `.env.example` Template

```
OPERION_DB_ENGINE=sqlite
OPERION_POSTGRES_DSN=postgresql://user:pass@localhost:5432/operion
OPERION_REDIS_URL=redis://localhost:6379/0
OPERION_CELERY_BROKER=redis://localhost:6379/1
OPERION_CELERY_RESULT=redis://localhost:6379/2
OPERION_API_HOST=127.0.0.1
OPERION_API_PORT=8000
OPERION_API_BASE_URL=http://127.0.0.1:8000
```

### 0.8 Update Ruff Config for Phase 0 Compliance

Add `backend/` to `[tool.ruff]` source path and ensure all Phase 0 files pass `ruff check` and `ruff format`.

## Edge Cases / Risks — Phase 0

| Risk | Mitigation |
|---|---|
| **`uv` on Windows** | Test `uv pip install` on Windows PowerShell; ensure no path issues. |
| **pydantic-settings import** | Python 3.9 may need `from typing import Optional` in pydantic models. |
| **Existing `config.py` namespace collision** | The new `backend/config.py` must not shadow `config.py` at root. Use `import config as app_config` in backend code. |

## Definition of Done — Phase 0

- [ ] `backend/`, `client/` directory trees created with `__init__.py` files.
- [ ] `requirements.txt` updated with all new deps, installed successfully.
- [ ] `config.py` extended with all new env vars.
- [ ] `backend/config.py` (Pydantic Settings) loads from env without error.
- [ ] `uv pip compile requirements.txt` produces a valid lock file.
- [ ] `ruff check .` passes.
- [ ] All 2,021 tests still green.

---

# PHASE 1: PURE BACKEND DECOUPLING (CORE BRAIN ISOLATION)

## Objective

Eliminate every raw `conn.execute()` from `services/` by moving all SQL into `repositories/`. Enforce the architectural boundary: Services receive Repositories via constructor injection; Services never touch `conn.execute()`.

## Dependencies

Phase 0 (directory scaffolding, config, deps installed).

## Step-by-Step Tasks

### 1.1 Audit and Catalog All Raw SQL Leaks

Run a script (or manual grep) to produce `REWORK_INVENTORY.json`:

```json
{
  "services/invoicing/cmr_generator.py": [
    {"line": 296, "pattern": "TripRepository(self.db).update_cmr_fields", "type": "direct_repo_instantiation"},
    {"line": 170, "pattern": "TripRepository(self.db)", "type": "direct_repo_instantiation"}
  ],
  "services/document_automation/document_grouper.py": [
    {"line": 41, "pattern": "db.conn.execute(\"SELECT documents_attached", "type": "raw_sql"},
    {"line": 250, "pattern": "self._trip_repo._execute(", "type": "service_calls_repo_internal"}
  ],
  ...
}
```

Files to audit:

- `services/document_automation/document_grouper.py` (lines 41, 76-78, 150, 250-264)
- `services/document_automation/pipeline.py` (line 68)
- `services/document_automation/ocr_extractor.py` (line 109)
- `services/document_automation/ai_fallback.py` (lines 115, 133)
- `services/document_automation/trip_matcher.py` (lines 173, 202, 441, 530)
- `services/document_automation/package_builder.py` (line 102)
- `services/document_automation/cloud_ocr.py` (line 32)
- `services/health_check.py` (line 30)
- `services/route_planner_controller.py` (line 365)
- `services/route_history_service.py` (lines 235, 245, 452, 464)
- `services/automail/reminder_service.py` (line 295)
- `services/operations/cmr_auto_generator.py` (lines 83, 112, 123, 134)
- `services/operations/dunner_engine.py` (lines 243, 292, 332, 347, 368)
- `services/operations/maintenance_engine.py` (line 221)
- `services/document/upload_service.py` (line 327)
- `services/document/versioning_service.py` (line 155)

### 1.2 Add Missing Repository Methods

For each raw SQL pattern found in services, add the corresponding method to the appropriate repository:

**Example: `document_grouper.py` line 41 → `TripRepository.get_documents_attached(trip_id)`**

Before (`services/document_automation/document_grouper.py:41`):

```python
row = db.conn.execute(
    "SELECT documents_attached FROM trips WHERE id = ?", (trip_id,)
).fetchone()
```

After — add to `repositories/trip_repository.py`:

```python
from typing import Optional


def get_documents_attached(self, trip_id: int) -> Optional[str]:
    row = self._fetchone(
        "SELECT documents_attached FROM trips WHERE id = ?", (trip_id,)
    )
    return row["documents_attached"] if row else None
```

Then in `document_grouper.py`:

```python
attached = self._trip_repo.get_documents_attached(trip_id)
```

**Full inventory of needed repo methods:**

| Repository | New Method | Replaces |
|---|---|---|
| `TripRepository` | `get_documents_attached(trip_id)` | `document_grouper.py:41` |
| `TripRepository` | `update_ocr_data(trip_id, payload, commit)` | `document_grouper.py:250-264` |
| `PipelineRepository` | `get_pending_runs()` | `pipeline.py:68` |
| `DocumentRepository` | `set_ocr_result(doc_id, text, engine, extracted_json)` | `ocr_extractor.py:109` |
| `DocumentRepository` | `set_ai_fallback_result(doc_id, field, value)` | `ai_fallback.py:115,133` |
| `TripRepository` | `search_trips_by_ocr_fields(fields_dict)` | `trip_matcher.py:173` |
| `TripRepository` | `match_trip_by_cmr_number(cmr_number)` | `trip_matcher.py:202` |
| `TripRepository` | `get_unmatched_trips_for_ocr()` | `trip_matcher.py:441` |
| `TripRepository` | `get_trip_for_batch_matching()` | `trip_matcher.py:530` |
| `DocumentRepository` | `get_documents_for_package_build(entity_type, entity_id)` | `package_builder.py:102` |
| `DocumentRepository` | `set_cloud_ocr_status(doc_id, status)` | `cloud_ocr.py:32` |
| `RouteRepository` | `get_route_history_by_date_range(start, end)` | `route_history_service.py:235` |
| `RouteRepository` | `get_route_events_by_route(route_id)` | `route_history_service.py:245` |
| `RouteRepository` | `get_route_statistics_summary()` | `route_history_service.py:452` |
| `RouteRepository` | `get_route_statistics_grouped()` | `route_history_service.py:464` |
| `AutoMailRepository` | `get_pending_reminders()` | `reminder_service.py:295` |
| `InvoiceRepository` | `get_cmr_auto_generation_candidates()` | `cmr_auto_generator.py:83` |
| `InvoiceRepository` | `update_cmr_auto_status(invoice_id, status)` | `cmr_auto_generator.py:112` |
| `InvoiceRepository` | (rest of cmr_auto_generator.py) | |
| `InvoiceRepository` | (dunner_engine.py uses) | |
| `MaintenanceRepository` | `get_upcoming_maintenance()` | `maintenance_engine.py:221` |
| `DocumentRepository` | `get_upload_status_batch(doc_ids)` | `upload_service.py:327` |
| `DocumentRepository` | `get_version_history(doc_id)` | `versioning_service.py:155` |

### 1.3 Convert All Service Direct Instantiation to Constructor Injection

**Example: `document_grouper.py` — BEFORE:**

```python
class DocumentGrouper:
    def __init__(self, db):
        self.db = db
        self.pipeline = PipelineRepository(db)
        self._doc_repo = DocumentRepository(db)
        self._trip_repo = TripRepository(db)
```

**AFTER:**

```python
from typing import Optional
from repositories.pipeline_repository import PipelineRepository
from repositories.document_repository import DocumentRepository
from repositories.trip_repository import TripRepository


class DocumentGrouper:
    def __init__(
        self,
        db,
        pipeline_repo: Optional[PipelineRepository] = None,
        doc_repo: Optional[DocumentRepository] = None,
        trip_repo: Optional[TripRepository] = None,
    ):
        self.db = db
        self.pipeline = pipeline_repo if pipeline_repo is not None else PipelineRepository(db)
        self._doc_repo = doc_repo if doc_repo is not None else DocumentRepository(db)
        self._trip_repo = trip_repo if trip_repo is not None else TripRepository(db)
```

This pattern preserves the default for existing callers while enabling test-time injection.

Files to convert:

1. `services/invoicing/cmr_generator.py` — remove `TripRepository(self.db)` at lines 170, 296
2. `services/document_automation/document_grouper.py` — convert all 3 repos
3. `services/document_automation/pipeline.py` — convert PipelineRepository
4. `services/document_automation/ocr_extractor.py` — convert DocumentRepository
5. `services/document_automation/ai_fallback.py` — convert DocumentRepository
6. `services/document_automation/trip_matcher.py` — convert TripRepository, DocumentRepository
7. `services/document_automation/package_builder.py` — convert TripRepository, DocumentRepository
8. `services/document_automation/cloud_ocr.py` — convert DocumentRepository
9. `services/route_planner_controller.py` — convert RouteRepository
10. `services/route_history_service.py` — convert RouteRepository
11. `services/automail/reminder_service.py` — convert AutoMailRepository
12. `services/operations/cmr_auto_generator.py` — convert InvoiceRepository
13. `services/operations/dunner_engine.py` — convert InvoiceRepository
14. `services/operations/maintenance_engine.py` — convert MaintenanceRepository
15. `services/document/upload_service.py` — convert DocumentRepository
16. `services/document/versioning_service.py` — convert DocumentRepository
17. `services/health_check.py` — convert using existing repo if available

### 1.4 Update Service Tests to Use Mock Repositories

For each converted service, update its test to inject a mock repository instead of a real DB.

**Example: `tests/test_document_grouper.py` — AFTER:**

```python
from unittest.mock import MagicMock
from repositories.trip_repository import TripRepository
from repositories.document_repository import DocumentRepository
from repositories.pipeline_repository import PipelineRepository


def test_group_documents():
    mock_trip_repo = MagicMock(spec=TripRepository)
    mock_trip_repo.get_documents_attached.return_value = None
    mock_trip_repo.get_by_id.return_value = {"id": 1, "status": "pending"}

    mock_doc_repo = MagicMock(spec=DocumentRepository)
    mock_pipeline_repo = MagicMock(spec=PipelineRepository)

    grouper = DocumentGrouper(
        db=mock_db,
        trip_repo=mock_trip_repo,
        doc_repo=mock_doc_repo,
        pipeline_repo=mock_pipeline_repo,
    )
    result = grouper.group_documents_for_trip(trip_id=1)
    # assert on result, verify mock calls
```

### 1.5 Verify Zero Direct `conn.execute()` in Services

```bash
rg "conn\.execute\(" services/ --type py
```

This should return zero results (only `repositories/` and `database/` may still use it).

## Edge Cases / Risks — Phase 1

| Risk | Mitigation |
|---|---|
| **Repository method naming collisions** | Prefix with entity: `get_documents_attached` not `get_attached` |
| **Transaction boundaries in services** | Move `begin/commit/rollback` into repository methods that need them. Services never manage transactions directly. |
| **Service A calls Service B which also had raw SQL** | Audit call chains; if Service A calls Service B, Service B must already be converted. Convert from leaf services upward. |
| **`_execute` with `commit=False` patterns** | Expose `commit` parameter on all new repo methods consistently |
| **Tests that use real DB and verify SQL side effects** | Add `_execute`/`_fetchone` to mock repo specs so tests don't break on missing attributes |

## Definition of Done — Phase 1

- [ ] Zero `conn.execute()` calls in `services/` directory (verified via grep).
- [ ] All 22 repository files have complete method coverage for their entity.
- [ ] All 16+ service files use constructor injection for dependencies.
- [ ] All service tests pass with mock repository injection.
- [ ] All 2,021+ tests green.

---

# PHASE 2: API SCHEMA LAYER — DATA CONTRACTS & FASTAPI ROUTERS

## Objective

Define Pydantic v2 schemas for every core entity and expose them via async FastAPI routers under `/api/v1/`. This phase creates the API but does NOT yet change the PySide6 client — the desktop still uses direct `DocumentService` calls via the compat shim.

## Dependencies

Phase 1 (all raw SQL removed from services, services injected).

## Step-by-Step Tasks

### 2.1 Define Pydantic v2 Schemas (Python 3.9 Compliant)

File: `backend/schemas/common.py`:

```python
from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel


T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 0
    page_size: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    total_pages: int


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
```

File: `backend/schemas/document.py`:

```python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class DocumentBase(BaseModel):
    title: str = ""
    category: str = ""
    entity_type: str = ""
    entity_id: Optional[int] = None
    tags: Optional[List[str]] = None
    description: str = ""
    expiry_date: Optional[str] = None


class DocumentCreate(DocumentBase):
    pass  # file upload handled via multipart/form-data


class DocumentResponse(DocumentBase):
    id: int
    doc_number: str
    file_name: str
    file_size: int
    mime_type: str
    uploaded_by: str
    uploaded_at: str
    updated_at: str
    is_archived: bool = False
    ocr_run_at: Optional[str] = None
    ocr_engine: Optional[str] = None
    ocr_text: Optional[str] = None
    extracted_data_json: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_signed: bool = False
    cmr_number: str = ""


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    expiry_date: Optional[str] = None


class DocumentLinkCreate(BaseModel):
    linked_entity_type: str
    linked_entity_id: int
    relation_type: str = "attached"


class DocumentLinkResponse(BaseModel):
    id: int
    document_id: int
    linked_entity_type: str
    linked_entity_id: int
    relation_type: str
    created_at: str
```

File: `backend/schemas/trip.py`:

```python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class TripBase(BaseModel):
    client_name: str = ""
    loading_city: str = ""
    loading_country: str = ""
    delivery_city: str = ""
    delivery_country: str = ""


class TripResponse(TripBase):
    id: int
    status: str
    created_at: str


class TripSearchParams(BaseModel):
    query: str = ""
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    driver_id: Optional[int] = None
    truck_id: Optional[int] = None
    page: int = 0
    page_size: int = 20
```

File: `backend/schemas/ocr.py`:

```python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class OcrRequest(BaseModel):
    document_id: int
    engine: str = "auto"  # "gemma3", "cloud", "tesseract", "auto"


class OcrResult(BaseModel):
    document_id: int
    ocr_text: str
    engine_used: str
    extracted_fields: Dict[str, Any]
    confidence: float = 0.0
    processing_time_ms: int = 0


class OcrFieldExtractionRequest(BaseModel):
    document_id: int
    fields_to_extract: Optional[List[str]] = None


class OcrFieldExtractionResponse(BaseModel):
    document_id: int
    fields: Dict[str, Any]
    errors: List[str] = []
```

### 2.2 Implement FastAPI Dependency Injection

File: `backend/dependencies.py`:

```python
from typing import Generator
from database.db_manager import DatabaseManager
from config import Config
from services.document_service import DocumentService
from services.trip_service import TripService
from repositories.document_repository import DocumentRepository
from repositories.trip_repository import TripRepository


def get_db() -> Generator[DatabaseManager, None, None]:
    """Dependency that yields a DatabaseManager for the request lifecycle."""
    db = DatabaseManager(Config.DB_PATH)
    try:
        yield db
    finally:
        db.close()


def get_document_repo(db: DatabaseManager = Depends(get_db)) -> DocumentRepository:
    return DocumentRepository(db)


def get_document_service(
    db: DatabaseManager = Depends(get_db),
    doc_repo: DocumentRepository = Depends(get_document_repo),
) -> DocumentService:
    return DocumentService(db)


def get_trip_repo(db: DatabaseManager = Depends(get_db)) -> TripRepository:
    return TripRepository(db)


def get_trip_service(
    db: DatabaseManager = Depends(get_db),
    trip_repo: TripRepository = Depends(get_trip_repo),
) -> TripService:
    from services.trip_service import TripService
    return TripService(db, trip_repo=trip_repo)
```

### 2.3 Implement FastAPI Routers

File: `backend/api/v1/documents.py`:

```python
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from backend.dependencies import get_document_service
from backend.schemas.document import (
    DocumentCreate, DocumentResponse, DocumentUpdate,
    DocumentLinkCreate, DocumentLinkResponse,
)
from backend.schemas.common import PaginatedResponse


router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=PaginatedResponse[DocumentResponse])
async def list_documents(
    query: str = Query("", description="Search query"),
    category: str = Query("", description="Document category filter"),
    entity_type: str = Query("", description="Entity type filter"),
    date_from: str = Query("", description="Start date (YYYY-MM-DD)"),
    date_to: str = Query("", description="End date (YYYY-MM-DD)"),
    mime_type: str = Query("", description="MIME type filter"),
    order: str = Query("uploaded_at DESC", description="Sort order"),
    page: int = Query(0, ge=0),
    page_size: int = Query(20, ge=1, le=100),
    service = Depends(get_document_service),
):
    result = service.advanced_search(
        query=query, category=category, entity_type=entity_type,
        date_from=date_from, date_to=date_to, mime_type=mime_type,
        order=order, page=page, page_size=page_size,
    )
    result["items"] = [DocumentResponse(**doc) for doc in result["items"]]
    return PaginatedResponse(**result)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    service = Depends(get_document_service),
):
    doc = service.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**doc)


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(""),
    entity_type: str = Form(""),
    entity_id: Optional[int] = Form(None),
    uploaded_by: str = Form("user"),
    service = Depends(get_document_service),
):
    # Save temp file, call service.upload(), return DocumentResponse
    ...


@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: int,
    update: DocumentUpdate,
    service = Depends(get_document_service),
):
    ...


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    service = Depends(get_document_service),
):
    success = service.delete(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted"}


@router.post("/{doc_id}/links", response_model=DocumentLinkResponse)
async def link_document(
    doc_id: int,
    link: DocumentLinkCreate,
    service = Depends(get_document_service),
):
    ...


@router.delete("/{doc_id}/links/{link_id}")
async def unlink_document(doc_id: int, link_id: int, service = Depends(get_document_service)):
    ...


@router.get("/{doc_id}/versions", response_model=List[dict])
async def get_versions(doc_id: int, service = Depends(get_document_service)):
    ...


@router.post("/{doc_id}/tags", response_model=DocumentResponse)
async def add_tag(doc_id: int, tag: str = Form(...), service = Depends(get_document_service)):
    ...


@router.delete("/{doc_id}/tags/{tag}")
async def remove_tag(doc_id: int, tag: str, service = Depends(get_document_service)):
    ...
```

File: `backend/api/v1/ocr.py`:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from backend.dependencies import get_document_service
from backend.schemas.ocr import OcrRequest, OcrResult


router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/run", response_model=OcrResult)
async def run_ocr(
    request: OcrRequest,
    background_tasks: BackgroundTasks,
    service = Depends(get_document_service),
):
    """Run OCR on a specific document (sync or background)."""
    ...


@router.get("/status/{doc_id}", response_model=OcrResult)
async def get_ocr_status(
    doc_id: int,
    service = Depends(get_document_service),
):
    """Get the last OCR result for a document."""
    doc = service.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return OcrResult(
        document_id=doc_id,
        ocr_text=doc.get("ocr_text", ""),
        engine_used=doc.get("ocr_engine", ""),
        extracted_fields=doc.get("extracted_data_json", {}),
    )


@router.post("/batch", response_model=List[OcrResult])
async def run_ocr_batch(
    doc_ids: List[int],
    background_tasks: BackgroundTasks,
    service = Depends(get_document_service),
):
    """Run OCR on multiple documents."""
    ...
```

File: `backend/api/v1/router.py`:

```python
from fastapi import APIRouter
from backend.api.v1 import documents, ocr, trips, clients, fleet, routes, analytics, health


api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(documents.router)
api_v1_router.include_router(ocr.router)
api_v1_router.include_router(trips.router)
api_v1_router.include_router(clients.router)
api_v1_router.include_router(fleet.router)
api_v1_router.include_router(routes.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(health.router)
```

### 2.4 Create FastAPI Application Factory

File: `backend/main.py`:

```python
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.v1.router import api_v1_router
from backend.config import BackendSettings


def create_app(settings: Optional[BackendSettings] = None) -> FastAPI:
    if settings is None:
        settings = BackendSettings()

    app = FastAPI(
        title="Operion ERP API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router)

    @app.on_event("startup")
    async def startup():
        # Initialize DB, Redis, Celery connections
        ...

    @app.on_event("shutdown")
    async def shutdown():
        # Close DB, Redis, Celery connections
        ...

    return app


app = create_app()
```

### 2.5 Add `backend/api/v1/documents.py` Enhanced Endpoint for Reading Document Info

This is critical per user's requirement: "features to read info from the document and stuff will be all used on any document center document."

```python
@router.get("/{doc_id}/read", response_model=DocumentReadResult)
async def read_document_info(
    doc_id: int,
    service = Depends(get_document_service),
):
    """
    Read and extract all available information from a document.
    Combines: OCR text, extracted fields, linked entities, versions,
    expiry info, tags, and any AI-fallback extracted data.
    """
    doc = service.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentReadResult(
        document=DocumentResponse(**doc),
        ocr_text=doc.get("ocr_text", ""),
        extracted_fields=doc.get("extracted_data_json", {}),
        linked_entities=service.get_links(doc_id),
        versions=service.get_versions(doc_id),
        tags=json.loads(doc.get("tags", "[]")),
        expiry=doc.get("expiry_date", ""),
        is_expired=_is_expired(doc.get("expiry_date", "")),
    )
```

Corresponding schema:

```python
class DocumentReadResult(BaseModel):
    document: DocumentResponse
    ocr_text: str = ""
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    linked_entities: List[DocumentLinkResponse] = Field(default_factory=list)
    versions: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    expiry: str = ""
    is_expired: bool = False
```

### 2.6 Write API Tests Using `fastapi.testclient.TestClient`

File: `tests/test_api_documents.py`:

```python
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_list_documents_empty(client):
    response = client.get("/api/v1/documents/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_get_document_not_found(client):
    response = client.get("/api/v1/documents/99999")
    assert response.status_code == 404


def test_read_document_info(client):
    # Mock the service to return a fake document
    with patch("backend.dependencies.get_document_service") as mock_svc:
        mock_svc.return_value.get_by_id.return_value = {
            "id": 1, "title": "Test", "ocr_text": "Hello", ...
        }
        response = client.get("/api/v1/documents/1/read")
        assert response.status_code == 200
        data = response.json()
        assert data["ocr_text"] == "Hello"
```

## Edge Cases / Risks — Phase 2

| Risk | Mitigation |
|---|---|
| **Pydantic v2 `model_config` vs `Config` class** | Use `model_config = ConfigDict(...)` (Pydantic v2 style). Test with Python 3.9. |
| **`from __future__ import annotations` breaks Pydantic** | Avoid it in schema files. Use `typing.List`, `typing.Optional` instead. |
| **FastAPI `UploadFile` file handling on Windows** | Use `tempfile` module, ensure cleanup in `finally` block. |
| **`TestClient` vs real DB** | All API tests use mock services. Integration tests (separate file) use test SQLite DB. |
| **Route ordering conflicts** | Place `GET /{doc_id}/read` after `GET /` but before `GET /{doc_id}` with regex disambiguation: `GET /{doc_id:int}/read`. |

## Definition of Done — Phase 2

- [ ] All Pydantic v2 schemas defined for 8 entity groups (documents, trips, clients, fleet, routes, OCR, analytics, common).
- [ ] All FastAPI routers implemented with CRUD + search endpoints.
- [ ] `/api/docs` (Swagger UI) renders all endpoints correctly.
- [ ] `TestClient` tests pass for all endpoints (mock services).
- [ ] All 2,021 existing tests + new API tests green.
- [ ] `ruff check backend/` passes.

---

# PHASE 3: DISTRIBUTED INFRASTRUCTURE — REDIS, CELERY, POSTGRESQL

## Objective

Add Redis caching, Celery task queue, PostgreSQL support, and GPS telemetry ingestion. The system must auto-detect whether PostgreSQL or SQLite is in use.

## Dependencies

Phase 2 (API layer exists) — Phase 1 not strictly required but strongly recommended.

## Step-by-Step Tasks

### 3.1 Redis Caching Layer

File: `backend/cache.py`:

```python
import json
from typing import Any, Optional
import redis
from backend.config import BackendSettings


class RedisCache:
    def __init__(self, settings: BackendSettings):
        self._redis: Optional[redis.Redis] = None
        self._settings = settings
        self._enabled = False

    def connect(self) -> None:
        try:
            self._redis = redis.Redis.from_url(
                self._settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            self._redis.ping()
            self._enabled = True
        except (redis.ConnectionError, redis.TimeoutError):
            self._enabled = False

    def get(self, key: str) -> Optional[Any]:
        if not self._enabled or self._redis is None:
            return None
        try:
            value = self._redis.get(key)
            return json.loads(value) if value else None
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if not self._enabled or self._redis is None:
            return False
        try:
            ttl = ttl or self._settings.redis_cache_ttl
            self._redis.setex(key, ttl, json.dumps(value))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        if not self._enabled or self._redis is None:
            return False
        try:
            self._redis.delete(key)
            return True
        except Exception:
            return False

    def flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        if not self._enabled or self._redis is None:
            return 0
        try:
            keys = list(self._redis.scan_iter(match=pattern))
            if keys:
                return self._redis.delete(*keys)
            return 0
        except Exception:
            return 0


_cache_instance: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache(BackendSettings())
        _cache_instance.connect()
    return _cache_instance
```

Caching interceptor in `DocumentService`:

```python
def get_by_id(self, doc_id: int) -> Optional[Dict[str, Any]]:
    cache = get_cache()
    cache_key = f"doc:{doc_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    doc = self._repo.get_by_id(doc_id)
    if doc:
        cache.set(cache_key, doc, ttl=300)  # 5 min TTL
    return doc
```

Cache invalidation: Add `cache.delete(f"doc:{doc_id}")` in `update()`, `delete()`, `archive()`.

### 3.2 PostgreSQL Support in DatabaseManager

File: `database/db_manager.py` additions:

```python
import psycopg2
import psycopg2.extras


class DatabaseManager:
    def __init__(self, db_path: str, engine: str = "sqlite"):
        self._engine = engine
        if engine == "postgresql":
            self._pg_conn = psycopg2.connect(db_path)  # db_path is DSN
            self._pg_conn.cursor_factory = psycopg2.extras.RealDictCursor
        else:
            self._pool = ConnectionPool(db_path, timeout=30)
        self._init_db()

    @property
    def conn(self):
        if self._engine == "postgresql":
            return self._pg_conn
        return self._pool.conn

    def close(self):
        if self._engine == "postgresql":
            if self._pg_conn:
                self._pg_conn.close()
        else:
            self._pool.close_all()
```

**SQL compatibility shim:** In `BaseRepository._execute()`, detect `?` placeholders and convert to `%s` for PostgreSQL using a helper:

```python
def _adapt_query(self, query: str) -> str:
    if self.db._engine == "postgresql":
        return query.replace("?", "%s")
    return query
```

**Critical:** PostgreSQL requires explicit `RETURNING id` for `INSERT`. Add to `BaseRepository._execute_insert()`:

```python
def _execute_insert(self, query: str, params: tuple = (), commit: bool = True) -> int:
    if self.db._engine == "postgresql":
        if "RETURNING" not in query.upper():
            query = query.rstrip(";") + " RETURNING id"
        query = query.replace("?", "%s")
    cursor = self.db.conn.cursor()
    cursor.execute(query, params)
    if self.db._engine == "postgresql":
        row = cursor.fetchone()
        last_id = row["id"] if row else 0
    else:
        last_id = cursor.lastrowid
    if commit:
        self.db.conn.commit()
    return last_id
```

### 3.3 Celery Task Framework

File: `backend/celery_app/celery.py`:

```python
from celery import Celery
from backend.config import BackendSettings


settings = BackendSettings()

celery_app = Celery(
    "operion",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Bucharest",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 min max
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)
```

File: `backend/celery_app/tasks/ocr_tasks.py`:

```python
from typing import Dict, Any
from backend.celery_app.celery import celery_app
from services.document_service import DocumentService
from services.document_automation.ocr_extractor import extract_ocr_data
from config import Config
from database.db_manager import DatabaseManager


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_ocr(self, document_id: int, engine: str = "auto") -> Dict[str, Any]:
    """Offloaded OCR extraction for a single document."""
    db = DatabaseManager(Config.DB_PATH)
    try:
        service = DocumentService(db)
        doc = service.get_by_id(document_id)
        if not doc:
            return {"error": "Document not found", "document_id": document_id}

        file_path = doc.get("file_path", "")
        result = extract_ocr_data(file_path, engine=engine)

        service.update_ocr_result(
            document_id,
            ocr_text=result.get("text", ""),
            engine=result.get("engine", engine),
            extracted_json=result.get("fields", {}),
        )
        return {"status": "ok", "document_id": document_id, "engine": result.get("engine")}
    except Exception as exc:
        self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2)
def batch_ocr_documents(self, document_ids: list, engine: str = "auto") -> Dict[str, Any]:
    """Offloaded batch OCR for multiple documents."""
    results = []
    for doc_id in document_ids:
        result = process_document_ocr.delay(doc_id, engine)
        results.append({"document_id": doc_id, "task_id": result.id})
    return {"status": "batch_enqueued", "tasks": results}
```

File: `backend/celery_app/tasks/document_tasks.py`:

```python
@celery_app.task(bind=True, max_retries=2)
def generate_document_pdf(self, document_id: int, template_name: str) -> Dict[str, Any]:
    """Offloaded PDF generation (CMR, invoice, proforma)."""
    ...


@celery_app.task(bind=True, max_retries=2)
def build_email_package(self, document_ids: list, recipient: str, prefs: dict) -> Dict[str, Any]:
    """Offloaded ZIP + email send for batch documents."""
    ...
```

### 3.4 GPS Telemetry Ingestion to Redis

File: `backend/api/v1/fleet.py` additions:

```python
from backend.cache import get_cache
from typing import List
from pydantic import BaseModel


class GpsPing(BaseModel):
    truck_id: int
    latitude: float
    longitude: float
    speed_kmh: float = 0.0
    heading: int = 0
    timestamp: str  # ISO 8601
    driver_id: Optional[int] = None


@router.post("/gps/ingest", status_code=202)
async def ingest_gps_ping(ping: GpsPing):
    """
    Ingest a GPS ping from a mobile device.
    Writes to Redis first (fast, volatile), then batch-flushes
    to PostgreSQL via a periodic Celery task.
    """
    cache = get_cache()
    key = f"gps:live:{ping.truck_id}"
    cache.set(key, ping.model_dump(), ttl=120)  # 2 min live

    # Append to a per-company Redis list for batch flush
    cache.rpush(f"gps:batch:{company_id}", ping.model_dump_json())
    return {"status": "accepted"}


@router.get("/gps/live/{truck_id}")
async def get_live_position(truck_id: int):
    """Get the last known GPS position for a truck from Redis."""
    cache = get_cache()
    data = cache.get(f"gps:live:{truck_id}")
    if data is None:
        raise HTTPException(status_code=404, detail="No live data")
    return data


@router.post("/gps/batch", status_code=202)
async def ingest_gps_batch(pings: List[GpsPing]):
    """Batch ingest from mobile app (reduces HTTP overhead)."""
    cache = get_cache()
    for ping in pings:
        key = f"gps:live:{ping.truck_id}"
        cache.set(key, ping.model_dump(), ttl=120)
        cache.rpush(f"gps:batch:{company_id}", ping.model_dump_json())
    return {"status": "accepted", "count": len(pings)}
```

Celery periodic task for batch flush:

```python
@celery_app.task
def flush_gps_batch_to_postgres():
    """Periodic: drain Redis GPS batch queue into PostgreSQL."""
    cache = get_cache()
    if not cache._enabled:
        return

    db = DatabaseManager(Config.DB_PATH, engine=Config.DB_ENGINE)
    try:
        while True:
            # Per-company drain: lrange → insert → commit → ltrim (delete-after-commit)
            items = cache.lrange(f"gps:batch:{company_id}", 0, -1)
            if not items:
                break
            ping = json.loads(raw)
            # INSERT INTO gps_telemetry (truck_id, lat, lon, ...) VALUES (...)
            ...
        db.conn.commit()
    finally:
        db.close()
```

Celery Beat schedule (in `celery.py`):

```python
celery_app.conf.beat_schedule = {
    "flush-gps-every-30s": {
        "task": "backend.celery_app.tasks.ocr_tasks.flush_gps_batch_to_postgres",
        "schedule": 30.0,
    },
}
```

## Edge Cases / Risks — Phase 3

| Risk | Mitigation |
|---|---|
| **Redis not available** | `RedisCache` throws no exceptions — `_enabled = False`, all ops are no-ops. |
| **PostgreSQL placeholder differences** | `_adapt_query()` in `BaseRepository` handles `?` → `%s`. `INSERT RETURNING id` is critical. |
| **Celery worker memory leaks** | `worker_max_tasks_per_child=50` forces periodic worker recycling. |
| **GPS batch queue can grow unbounded** | Per-company keys `gps:batch:{company_id}`; flush drains via `lrange` → insert → commit → `ltrim` (delete-after-commit), with `max_retries=3` on the Celery task. |
| **SQLite FTS5 doesn't exist in PostgreSQL** | FTS5 queries are wrapped in `if self.db._engine == "sqlite"` blocks. PostgreSQL uses `tsvector`/`tsquery` alternative. |

## Definition of Done — Phase 3

- [ ] `RedisCache` connects to Redis (or gracefully degrades if unavailable).
- [ ] `DocumentService.get_by_id()` reads from cache first, falls back to DB.
- [ ] `DatabaseManager` works with both `engine="sqlite"` and `engine="postgresql"`.
- [ ] `?` → `%s` conversion passes `BaseRepository` tests for both engines.
- [ ] Celery worker starts, accepts tasks, executes `process_document_ocr`.
- [ ] GPS ingest → Redis → batch flush pipeline works end-to-end.
- [ ] All 2,021+ tests green.

---

# PHASE 4: DECOUPLING THE PYSIDE6 DESKTOP UI

## Objective

Replace all 41 direct `Repository(self.db)` instantiations in UI views with calls through a centralized `ApiClient` that communicates over HTTP/JSON with the FastAPI backend. Add the **API Dashboard tab** (Tab 3) to the Document Center.

## Dependencies

Phase 2 (API exists and is tested). Phase 3 optional but recommended for full experience.

## Step-by-Step Tasks

### 4.1 Implement the Centralized ApiClient

File: `client/api_client.py`:

```python
from typing import Any, Dict, List, Optional
import httpx
from config import Config


class ApiClient:
    """Centralized HTTP client for the PySide6 desktop app.

    All UI views call this instead of instantiating Repository(self.db).
    Falls back to direct service calls when the API server is unreachable
    (graceful degradation for standalone desktop mode).
    """

    def __init__(self, base_url: Optional[str] = None):
        self._base_url = base_url or Config.API_BASE_URL
        self._client = httpx.Client(timeout=30.0)
        self._online: Optional[bool] = None  # None = not checked yet

    # ── Health check ──────────────────────────────────────────────────

    def is_online(self) -> bool:
        if self._online is None:
            try:
                resp = self._client.get(f"{self._base_url}/api/v1/health")
                self._online = resp.status_code == 200
            except Exception:
                self._online = False
        return self._online

    # ── Generic HTTP helpers ──────────────────────────────────────────

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        resp = self._client.get(f"{self._base_url}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json_data: Optional[Dict] = None,
              files: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict[str, Any]:
        resp = self._client.post(
            f"{self._base_url}{path}",
            json=json_data, files=files, data=data,
        )
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, json_data: Dict) -> Dict[str, Any]:
        resp = self._client.put(f"{self._base_url}{path}", json=json_data)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> Dict[str, Any]:
        resp = self._client.delete(f"{self._base_url}{path}")
        resp.raise_for_status()
        return resp.json()

    # ── Document endpoints ────────────────────────────────────────────

    def list_documents(self, query: str = "", category: str = "",
                       entity_type: str = "", date_from: str = "",
                       date_to: str = "", mime_type: str = "",
                       order: str = "uploaded_at DESC",
                       page: int = 0, page_size: int = 20) -> Dict[str, Any]:
        return self._get("/api/v1/documents/", params={
            "query": query, "category": category, "entity_type": entity_type,
            "date_from": date_from, "date_to": date_to, "mime_type": mime_type,
            "order": order, "page": page, "page_size": page_size,
        })

    def get_document(self, doc_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/documents/{doc_id}")

    def read_document_info(self, doc_id: int) -> Dict[str, Any]:
        """Comprehensive read: OCR, fields, links, versions, tags, expiry."""
        return self._get(f"/api/v1/documents/{doc_id}/read")

    def upload_document(self, file_path: str, category: str = "",
                        entity_type: str = "", entity_id: Optional[int] = None,
                        uploaded_by: str = "user") -> Dict[str, Any]:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            data = {"category": category, "entity_type": entity_type,
                    "entity_id": str(entity_id or ""), "uploaded_by": uploaded_by}
            return self._post("/api/v1/documents/upload", files=files, data=data)

    def update_document(self, doc_id: int, **fields) -> Dict[str, Any]:
        return self._put(f"/api/v1/documents/{doc_id}", json_data=fields)

    def delete_document(self, doc_id: int) -> Dict[str, Any]:
        return self._delete(f"/api/v1/documents/{doc_id}")

    def link_document(self, doc_id: int, entity_type: str, entity_id: int,
                      relation_type: str = "attached") -> Dict[str, Any]:
        return self._post(f"/api/v1/documents/{doc_id}/links", json_data={
            "linked_entity_type": entity_type,
            "linked_entity_id": entity_id,
            "relation_type": relation_type,
        })

    def get_document_links(self, doc_id: int) -> List[Dict[str, Any]]:
        return self._get(f"/api/v1/documents/{doc_id}/links")

    def get_document_versions(self, doc_id: int) -> List[Dict[str, Any]]:
        return self._get(f"/api/v1/documents/{doc_id}/versions")

    def add_document_tag(self, doc_id: int, tag: str) -> Dict[str, Any]:
        return self._post(f"/api/v1/documents/{doc_id}/tags", data={"tag": tag})

    def remove_document_tag(self, doc_id: int, tag: str) -> Dict[str, Any]:
        return self._delete(f"/api/v1/documents/{doc_id}/tags/{tag}")

    # ── OCR endpoints ─────────────────────────────────────────────────

    def run_ocr(self, document_id: int, engine: str = "auto") -> Dict[str, Any]:
        return self._post("/api/v1/ocr/run", json_data={
            "document_id": document_id, "engine": engine,
        })

    def get_ocr_status(self, doc_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/ocr/status/{doc_id}")

    def run_ocr_batch(self, doc_ids: List[int]) -> Dict[str, Any]:
        return self._post("/api/v1/ocr/batch", json_data=doc_ids)

    # ── Trip endpoints ────────────────────────────────────────────────

    def list_trips(self, **params) -> Dict[str, Any]:
        return self._get("/api/v1/trips/", params=params)

    def get_trip(self, trip_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/trips/{trip_id}")

    # ── Health check ───────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        return self._get("/api/v1/health")

    def close(self) -> None:
        self._client.close()
```

### 4.2 Implement Fallback Wrapper — DualModeService

File: `client/api_client.py` addition:

```python
class DualModeDocumentService:
    """Transparent fallback: tries ApiClient first, falls back to local DocumentService.

    This allows gradual migration — the app works whether or not the API server is running.
    """

    def __init__(self, db=None, api_client: Optional[ApiClient] = None):
        self._db = db
        self._api = api_client or ApiClient()
        self._local: Any = None  # Lazy DocumentService

    def _get_local(self):
        if self._local is None and self._db is not None:
            from services.document_service import DocumentService
            self._local = DocumentService(self._db)
        return self._local

    def get_by_id(self, doc_id: int) -> Optional[Dict[str, Any]]:
        if self._api.is_online():
            try:
                return self._api.get_document(doc_id)
            except Exception:
                pass
        local = self._get_local()
        return local.get_by_id(doc_id) if local else None

    def list_documents(self, **kwargs) -> Dict[str, Any]:
        if self._api.is_online():
            try:
                return self._api.list_documents(**kwargs)
            except Exception:
                pass
        local = self._get_local()
        return local.advanced_search(**kwargs) if local else {"items": [], "total": 0}

    # ... (all DocumentService methods wrapped identically)
```

### 4.3 Convert One UI View Per Iteration

**Priority order** (most DB-coupled first):

1. `ui/views/automation_view.py` — 6 `Repository(self.db)` instantiations
   - Remove `PipelineRepository(self.db)` from `__init__`
   - Replace with `self._api = ApiClient()` or receive via constructor
   - `self._api.list_documents(...)` replaces `self._pipeline_repo.search(...)`

2. `ui/views/email_composer_modal.py` — 5 instantiations
3. `ui/views/receipt_editor.py` — 3 instantiations
4. `ui/views/package_preview_modal.py` — 2 instantiations
5. `ui/views/fleet_tab.py` — 1 instantiation
6. `ui/views/invoice_editor.py` — 1 instantiation
7. `ui/views/driver_manager.py` — 1 instantiation
8. `ui/views/settings_view.py` — 1 instantiation
9. `ui/views/dashboard.py` — 1 instantiation
10. `ui/views/generators_view.py` — 1 instantiation
11. `ui/views/automation_worker.py` — 1 instantiation
12. `ui/views/document_center_view.py` — `DocumentService(db)` at line 277
    - Convert to `DualModeDocumentService(db, api_client=api_client)`

Conversion pattern for each:

```python
# BEFORE
from repositories.pipeline_repository import PipelineRepository


class QtAutomationView(QWidget):
    def __init__(self, parent, db, prefs=None, ops=None):
        self._pipeline_repo = PipelineRepository(db)
        self._doc_repo = DocumentRepository(db)


# AFTER
from client.api_client import ApiClient


class QtAutomationView(QWidget):
    def __init__(self, parent, db, prefs=None, ops=None, api_client=None):
        self._api = api_client if api_client is not None else ApiClient()
        # db kept for backward compat, not used directly
```

### 4.4 Add API Dashboard Tab to Document Center

File: `ui/views/api_dashboard_view.py` (NEW):

```python
"""API Dashboard tab — monitor the backend API health, view endpoint
status, test OCR, inspect Redis/Celery connection status, and view
recent API request logs.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget, QGridLayout,
)
from client.api_client import ApiClient
from services.i18n import t
from ui.components import Btn
from ui.theme import COLORS, S
from ui.widgets import SectionHeader


class QtApiDashboardView(QWidget):
    """Embedded API monitoring and management dashboard.

    Shows:
      - API connection status (online/offline)
      - Redis cache status
      - Celery worker count
      - Recent OCR jobs
      - Endpoint latency table
      - Quick-actions: run OCR on selected doc, flush cache, etc.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        api_client: Optional[ApiClient] = None,
    ):
        super().__init__(parent)
        self.db = db
        self._api = api_client or ApiClient()
        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(5000)  # refresh every 5s

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        layout.setSpacing(S["3"])

        # Header
        header = SectionHeader(self, t("api.dashboard_title", default="API Dashboard"))
        layout.addWidget(header)

        # Status grid
        self._status_grid = QGridLayout()
        layout.addLayout(self._status_grid)

        # Quick action buttons
        actions_row = QHBoxLayout()
        self._test_ocr_btn = Btn(self, "Test OCR", command=self._test_ocr, variant="secondary")
        actions_row.addWidget(self._test_ocr_btn)
        self._flush_cache_btn = Btn(self, "Flush Cache", command=self._flush_cache, variant="ghost")
        actions_row.addWidget(self._flush_cache_btn)
        actions_row.addStretch()
        layout.addLayout(actions_row)

        # Log area
        logs_header = QLabel(t("api.recent_logs", default="Recent API Calls"))
        logs_header.setProperty("fontRole", "label")
        layout.addWidget(logs_header)

        self._log_scroll = QScrollArea()
        self._log_scroll.setWidgetResizable(True)
        self._log_content = QWidget()
        self._log_layout = QVBoxLayout(self._log_content)
        self._log_layout.setAlignment(Qt.AlignTop)
        self._log_scroll.setWidget(self._log_content)
        layout.addWidget(self._log_scroll, 1)

        self._refresh_status()

    def wakeup(self) -> None:
        self._refresh_status()

    def _refresh_status(self) -> None:
        # Clear status grid
        while self._status_grid.count():
            item = self._status_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Check API health
        online = self._api.is_online()
        status_color = COLORS["accent_green"] if online else COLORS["danger"]
        api_label = QLabel(f"API: {'ONLINE' if online else 'OFFLINE'}")
        api_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        self._status_grid.addWidget(api_label, 0, 0)

        if online:
            try:
                health = self._api.health_check()
                db_label = QLabel(f"DB: {health.get('database', '?')}")
                redis_label = QLabel(f"Redis: {health.get('redis', '?')}")
                celery_label = QLabel(f"Celery: {health.get('celery', '?')}")
                self._status_grid.addWidget(db_label, 1, 0)
                self._status_grid.addWidget(redis_label, 2, 0)
                self._status_grid.addWidget(celery_label, 3, 0)
            except Exception:
                pass

    def _test_ocr(self) -> None:
        """Test OCR on a random document."""
        ...

    def _flush_cache(self) -> None:
        """Flush Redis cache via API."""
        ...
```

### 4.5 Wire API Dashboard Tab into Document Center

In `ui/views/document_center_view.py:_build_ui()`:

```python
def _build_ui(self) -> None:
    main_layout = QVBoxLayout(self)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    self._tab_widget = QTabWidget()
    self._tab_widget.setProperty("role", "document-center-tabs")
    self._tab_widget.currentChanged.connect(self._on_tab_changed)
    main_layout.addWidget(self._tab_widget, 1)

    # ── Tab 1: Documents (three-panel layout) ───────────────────────
    # ... (existing code unchanged)

    # ── Tab 2: Automation ───────────────────────────────────────────
    # ... (existing code unchanged)

    # ── Tab 3: API Dashboard ──────────────────────────────────────── (NEW)
    self._api_dashboard_page = QWidget()
    self._api_dashboard_layout = QVBoxLayout(self._api_dashboard_page)
    self._api_dashboard_layout.setContentsMargins(0, 0, 0, 0)
    self._api_dashboard_layout.setSpacing(0)
    try:
        from ui.views.api_dashboard_view import QtApiDashboardView
        self._api_dashboard_view = QtApiDashboardView(
            self._api_dashboard_page,
            db=self.db,
            api_client=getattr(self, '_api_client', None),
        )
        self._api_dashboard_layout.addWidget(self._api_dashboard_view, 1)
    except Exception:
        logger.exception("Failed to construct QtApiDashboardView")
        self._api_dashboard_view = None
    self._tab_widget.addTab(self._api_dashboard_page, "")

    self._refresh_tab_titles()
    self.refresh()
```

Update `_refresh_tab_titles()`:

```python
def _refresh_tab_titles(self) -> None:
    self._tab_widget.setTabText(0, t("docs.tab_documents", default="Documents"))
    self._tab_widget.setTabText(1, t("automation.tab_title", default="Automation"))
    self._tab_widget.setTabText(2, t("api.tab_title", default="API Dashboard"))
```

Update `_on_tab_changed()`:

```python
def _on_tab_changed(self, index: int) -> None:
    if index == 1 and self._automation_view is not None:
        try:
            if hasattr(self._automation_view, "wakeup"):
                self._automation_view.wakeup()
        except Exception:
            logger.exception("Failed to wake automation view")
    elif index == 2 and self._api_dashboard_view is not None:
        try:
            if hasattr(self._api_dashboard_view, "wakeup"):
                self._api_dashboard_view.wakeup()
        except Exception:
            logger.exception("Failed to wake API dashboard view")
```

### 4.6 Update Tests for the New Tab

Extend `tests/test_document_center_tabs.py`:

```python
class TestDocumentCenterHasApiDashboardTab(unittest.TestCase):
    def setUp(self) -> None:
        _ensure_qapp()
        self.db, self.path = _new_db()
        from ui.views.document_center_view import QtDocumentCenterView
        self.view = QtDocumentCenterView(None, db=self.db)

    def tearDown(self) -> None:
        try:
            self.db.close()
        finally:
            os.unlink(self.path)
        self.view.deleteLater()

    def test_three_tabs(self) -> None:
        self.assertGreaterEqual(self.view._tab_widget.count(), 3)

    def test_third_tab_is_api_dashboard(self) -> None:
        self.assertIn("API", self.view._tab_widget.tabText(2))
```

## Edge Cases / Risks — Phase 4

| Risk | Mitigation |
|---|---|
| **API server unreachable** | `DualModeDocumentService` auto-falls back to local `DocumentService(db)`. App never crashes. |
| **Network latency in UI thread** | `ApiClient` uses synchronous `httpx.Client`. For heavy calls, wrap in `QThread` worker pattern (same as current OCR worker). |
| **Qt event loop blocking on HTTP** | Use `QTimer.singleShot(0, lambda: ...)` pattern; for long calls, use `QThread`. |
| **API auth not yet implemented** | Phase 4 assumes open localhost. Auth is Phase 6 (future). |
| **Tab indices shift** | Tests use tab text checks, not hardcoded indices. |

## Definition of Done — Phase 4

- [ ] All 19 UI views no longer instantiate `Repository(self.db)` directly.
- [ ] `ApiClient` has methods for all document, trip, OCR, client, fleet endpoints.
- [ ] `DualModeDocumentService` passes through to local when API is offline.
- [ ] API Dashboard tab appears as tab 3 in Document Center.
- [ ] API Dashboard shows live health status, Redis/Celery status.
- [ ] Test for 3 tabs passes.
- [ ] All 2,021+ tests green.

---

# PHASE 5: CONTAINERIZED DEPLOYMENT & DEVOPS

## Objective

Provide production-grade Docker Compose setup, multi-stage Dockerfile, and Nginx reverse proxy with SSL termination and rate limiting.

## Dependencies

Phases 2-4 complete (API exists, Celery exists, UI uses ApiClient).

## Step-by-Step Tasks

### 5.1 Multi-Stage Dockerfile (Python 3.9, uv, non-root user)

File: `Dockerfile`:

```dockerfile
# ── Stage 1: Builder ──────────────────────────────────────────────
FROM python:3.9-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────────────
FROM python:3.9-slim AS runtime

RUN groupadd -r operion && useradd -r -g operion -d /app operion

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . /app

RUN mkdir -p /app/data /app/logs /app/reports /app/data/documents \
    && chown -R operion:operion /app

USER operion

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["gunicorn", "backend.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

### 5.2 Celery Worker Dockerfile

File: `Dockerfile.worker`:

```dockerfile
FROM python:3.9-slim AS runtime

RUN groupadd -r operion && useradd -r -g operion -d /app operion

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN mkdir -p /app/data /app/logs /app/reports /app/data/documents \
    && chown -R operion:operion /app

USER operion

CMD ["celery", "-A", "backend.celery_app.celery", "worker", \
     "--loglevel=info", "--concurrency=2"]
```

### 5.3 Production Docker Compose

File: `docker-compose.yml`:

```yaml
version: "3.8"

services:
  db:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: operion
      POSTGRES_USER: operion
      POSTGRES_PASSWORD: ${OPERION_POSTGRES_PASSWORD:-operion_secret}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U operion -d operion"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "127.0.0.1:5432:5432"

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "127.0.0.1:6379:6379"

  api:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      OPERION_DB_ENGINE: postgresql
      OPERION_POSTGRES_DSN: postgresql://operion:${OPERION_POSTGRES_PASSWORD:-operion_secret}@db:5432/operion
      OPERION_REDIS_URL: redis://redis:6379/0
      OPERION_CELERY_BROKER: redis://redis:6379/1
      OPERION_CELERY_RESULT: redis://redis:6379/2
      OPERION_API_HOST: 0.0.0.0
      OPERION_API_PORT: 8000
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - app_data:/app/data
      - app_logs:/app/logs
      - app_reports:/app/reports

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    restart: unless-stopped
    environment:
      OPERION_DB_ENGINE: postgresql
      OPERION_POSTGRES_DSN: postgresql://operion:${OPERION_POSTGRES_PASSWORD:-operion_secret}@db:5432/operion
      OPERION_REDIS_URL: redis://redis:6379/0
      OPERION_CELERY_BROKER: redis://redis:6379/1
      OPERION_CELERY_RESULT: redis://redis:6379/2
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - app_data:/app/data
      - app_logs:/app/logs
      - app_reports:/app/reports

  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile.worker
    restart: unless-stopped
    command: celery -A backend.celery_app.celery beat --loglevel=info
    environment:
      OPERION_DB_ENGINE: postgresql
      OPERION_POSTGRES_DSN: postgresql://operion:${OPERION_POSTGRES_PASSWORD:-operion_secret}@db:5432/operion
      OPERION_REDIS_URL: redis://redis:6379/0
      OPERION_CELERY_BROKER: redis://redis:6379/1
      OPERION_CELERY_RESULT: redis://redis:6379/2
    depends_on:
      - redis

  nginx:
    image: nginx:1.25-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - api

volumes:
  pgdata:
  redisdata:
  app_data:
  app_logs:
  app_reports:
```

### 5.4 Nginx Reverse Proxy Configuration

File: `nginx.conf`:

```nginx
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 50M;

    # ── Rate limiting zones ──────────────────────────────────────────
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=upload_limit:10m rate=5r/s;

    # ── Upstream definition ──────────────────────────────────────────
    upstream api_backend {
        server api:8000;
    }

    # ── HTTP to HTTPS redirect ────────────────────────────────────────
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    # ── HTTPS server ─────────────────────────────────────────────────
    server {
        listen 443 ssl http2;
        server_name _;

        ssl_certificate /etc/nginx/certs/server.crt;
        ssl_certificate_key /etc/nginx/certs/server.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # ── Security headers ─────────────────────────────────────────
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # ── API proxy ────────────────────────────────────────────────
        location /api/ {
            limit_req zone=api_limit burst=50 nodelay;
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 120s;
            proxy_connect_timeout 10s;
        }

        # ── Upload endpoint ──────────────────────────────────────────
        location /api/v1/documents/upload {
            limit_req zone=upload_limit burst=10 nodelay;
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 300s;
            client_max_body_size 50M;
        }

        # ── Swagger docs ─────────────────────────────────────────────
        location /api/docs {
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location /api/redoc {
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # ── Health check (no rate limit) ─────────────────────────────
        location /api/v1/health {
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
        }

        # ── Deny all other paths ─────────────────────────────────────
        location / {
            return 403;
        }
    }
}
```

### 5.5 Self-Signed Cert Generation Script

File: `scripts/gen_certs.sh`:

```bash
#!/bin/bash
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout certs/server.key \
    -out certs/server.crt \
    -subj "/C=RO/ST=Bucharest/L=Bucharest/O=Operion/CN=localhost"
```

### 5.6 Environment Files

File: `.env.production`:

```
OPERION_POSTGRES_PASSWORD=change_me_in_production_use_secrets_manager
OPERION_DB_ENGINE=postgresql
OPERION_GRAPHHOPPER_URL=https://maps.operionerp.xyz
```

File: `.env.development`:

```
OPERION_DB_ENGINE=sqlite
OPERION_DB_PATH=data/cashflow.db
```

## Edge Cases / Risks — Phase 5

| Risk | Mitigation |
|---|---|
| **Docker Desktop on Windows** | Test with Docker Desktop WSL2 backend. `docker-compose.yml` uses Linux containers. |
| **SQLite in Docker** | Volume mount `./data:/app/data` ensures persistence. WAL mode works in containers. |
| **Celery Beat duplicates** | `celery-beat` is a single-instance service. Use Redis lock for multi-node safety. |
| **Self-signed certs** | Local dev only. Production uses Let's Encrypt via Certbot. |
| **Gunicorn + UvicornWorker on Windows** | Not supported. Windows uses `uvicorn backend.main:app` directly. `build.bat` handles this. |

## Definition of Done — Phase 5

- [ ] `docker compose up` starts all 6 services successfully.
- [ ] `curl http://localhost:8000/api/v1/health` returns `{"status": "ok"}`.
- [ ] `curl https://localhost/api/v1/health` works through Nginx.
- [ ] Celery worker processes background OCR tasks.
- [ ] Redis caching reduces DB query latency (measurable via API dashboard).
- [ ] All 2,021+ tests green in container (optional: `docker compose run --rm test`).

---

# 6. COMPREHENSIVE TEST INTEGRATION PROTOCOL

## 6.1 Test Architecture

```
tests/
├── conftest.py                        # Global fixtures (ensure_qapp, _new_db)
├── test_*.py                          # 110 existing test files (unchanged)
├── test_api/
│   ├── __init__.py
│   ├── conftest.py                    # API-specific fixtures (TestClient, mock services)
│   ├── test_api_documents.py          # TestClient → mock services
│   ├── test_api_ocr.py
│   ├── test_api_trips.py
│   ├── test_api_clients.py
│   ├── test_api_fleet.py
│   ├── test_api_routes.py
│   ├── test_api_analytics.py
│   └── test_api_health.py
├── test_integration/
│   ├── __init__.py
│   ├── test_api_with_sqlite.py        # Real SQLite DB, real DocumentService
│   ├── test_redis_cache.py            # Requires Redis running (marked @slow)
│   └── test_celery_tasks.py           # Requires Celery worker (marked @slow)
└── test_clients/
    ├── __init__.py
    ├── test_api_client.py             # Mock httpx, test ApiClient methods
    └── test_dual_mode_service.py      # Test fallback logic
```

## 6.2 Mocking Strategy

| Layer | Mock Target | Pattern |
|---|---|---|
| **API Tests** | `backend.dependencies.get_*` | `unittest.mock.patch` the dependency |
| **ApiClient Tests** | `httpx.Client` | `responses` library or `httpx.MockTransport` |
| **DualModeService** | `ApiClient.is_online` | Toggle return value to test both paths |
| **Celery Tasks** | `DatabaseManager`, `DocumentService` | Inject mock DB / mock service |

## 6.3 Test Markers for CI Pipelining

```python
import pytest

@pytest.mark.slow        # Tests requiring Redis/Celery/PostgreSQL
@pytest.mark.api         # FastAPI TestClient tests
@pytest.mark.unit        # Pure unit tests (no DB, no Qt)
@pytest.mark.qt          # Requires QApplication (PySide6)
@pytest.mark.integration # Real DB tests
```

## 6.4 CI Pipeline (Placeholder)

```yaml
# .github/workflows/test.yml
jobs:
  test:
    steps:
      - run: ruff check .
      - run: pytest tests/ -m "not slow and not integration" -n auto
      - run: pytest tests/ -m "api" --cov=backend
```

---

# 7. RISK REGISTER

| # | Risk | Probability | Severity | Mitigation |
|---|---|---|---|---|
| R1 | **Gunicorn + UvicornWorker on Windows** | High | Medium | Windows fallback to `uvicorn backend.main:app` directly. `build.bat` detects platform. |
| R2 | **SQLite concurrent writes from Gunicorn workers** | High | High | Phase 3 PostgreSQL as production requirement. SQLite dev only. Add retry loop in `_execute()`. |
| R3 | **PySide6 main thread blocked by httpx sync calls** | Medium | High | Use `QThread` wrappers for heavy API calls (same pattern as existing `ReRunOcrWorker`). |
| R4 | **Pydantic v2 `model_config` vs old `Config` class** | Medium | Medium | Test all schemas with Python 3.9 + Pydantic v2 before committing. |
| R5 | **`BaseRepository._execute_insert()` RETURNING id differences** | Medium | High | Comprehensive PG/SQLite cross-test in `test_integration/`. |
| R6 | **Redis not available in dev** | Medium | Low | `RedisCache._enabled = False` is full graceful degradation. |
| R7 | **FTS5 not available in PostgreSQL** | Medium | High | Conditional path: FTS5 for SQLite, `tsvector`/`tsquery` for PG. |
| R8 | **Tab index shifts break tests** | Low | Medium | Tests use tab text (`assertIn "API"`) not hardcoded indices. |
| R9 | **Async endpoint importing sync service with thread-local DB** | Medium | High | Use `run_in_executor` for sync DB calls or wrap in async-compatible `DatabaseManager`. |
| R10 | **Celery task serialization of complex objects** | Low | Medium | All Celery tasks accept and return JSON-serializable types only. |

---

# 8. IMPLEMENTATION ORDERING & DEPENDENCY GRAPH

```
Phase 0 (Foundation)
  │
  ▼
Phase 1 (Backend Decoupling)
  │
  ├───────────────────────────────────────────┐
  ▼                                           ▼
Phase 2 (API Schemas & FastAPI)     Phase 3 (Redis, Celery, PG)
  │                                           │
  └───────────────────┬───────────────────────┘
                      ▼
              Phase 4 (UI Decoupling + API Dashboard Tab)
                      │
                      ▼
              Phase 5 (Docker & Deployment)
```

**Parallelizable:** Phase 2 and Phase 3 can be built concurrently after Phase 1 completes. Phase 2 is critical-path for Phase 4. Phase 3 can be deferred without blocking Phase 4 (API Dashboard just shows "Redis: offline").

---

# 9. REWORK INVENTORY — RAW SQL LEAKS IN SERVICES

## Complete Audit

| File | Line | Pattern | Type | Target Repo |
|---|---|---|---|---|
| `services/document_automation/document_grouper.py` | 41 | `db.conn.execute("SELECT documents_attached..."` | raw_sql | TripRepository |
| `services/document_automation/document_grouper.py` | 76-78 | `PipelineRepository(db)`, `DocumentRepository(db)`, `TripRepository(db)` | direct_repo | constructor inj |
| `services/document_automation/document_grouper.py` | 150 | `UploadService(self.db, DocumentRepository(self.db))` | nested_repo | constructor inj |
| `services/document_automation/document_grouper.py` | 250-264 | `self._trip_repo._execute(...)` | raw_sql | TripRepository |
| `services/document_automation/pipeline.py` | 68 | `db.conn.execute(...)` | raw_sql | PipelineRepository |
| `services/document_automation/ocr_extractor.py` | 109 | `db.conn.execute(...)` | raw_sql | DocumentRepository |
| `services/document_automation/ai_fallback.py` | 115,133 | `db.conn.execute(...)` | raw_sql | DocumentRepository |
| `services/document_automation/trip_matcher.py` | 173,202,441,530 | `db.conn.execute(...)` | raw_sql | TripRepository |
| `services/document_automation/package_builder.py` | 102 | `db.conn.execute(...)` | raw_sql | DocumentRepository |
| `services/document_automation/cloud_ocr.py` | 32 | `db.conn.execute(...)` | raw_sql | DocumentRepository |
| `services/health_check.py` | 30 | `db.conn.execute(...)` | raw_sql | HealthRepository |
| `services/route_planner_controller.py` | 365 | `db.conn.execute(...)` | raw_sql | RouteRepository |
| `services/route_history_service.py` | 235,245,452,464 | `db.conn.execute(...)` | raw_sql | RouteRepository |
| `services/automail/reminder_service.py` | 295 | `db.conn.execute(...)` | raw_sql | AutoMailRepository |
| `services/operations/cmr_auto_generator.py` | 83,112,123,134 | `db.conn.execute(...)` | raw_sql | InvoiceRepository |
| `services/operations/dunner_engine.py` | 243,292,332,347,368 | `db.conn.execute(...)` | raw_sql | InvoiceRepository |
| `services/operations/maintenance_engine.py` | 221 | `db.conn.execute(...)` | raw_sql | MaintenanceRepository |
| `services/document/upload_service.py` | 327 | `db.conn.execute(...)` | raw_sql | DocumentRepository |
| `services/document/versioning_service.py` | 155 | `db.conn.execute(...)` | raw_sql | DocumentRepository |
| `services/invoicing/cmr_generator.py` | 170,296 | `TripRepository(self.db)` | direct_repo | constructor inj |

## UI Views with Direct Repository Instantiations

| File | Count | Repositories |
|---|---|---|
| `ui/views/automation_view.py` | 6 | PipelineRepository, DocumentRepository |
| `ui/views/email_composer_modal.py` | 5 | TripRepository, PipelineRepository |
| `ui/views/receipt_editor.py` | 3 | ClientRepository, FleetRepository, InvoiceRepository |
| `ui/views/package_preview_modal.py` | 2 | TripRepository, DocumentRepository |
| `ui/views/fleet_tab.py` | 1 | FleetRepository |
| `ui/views/invoice_editor.py` | 1 | InvoiceRepository |
| `ui/views/driver_manager.py` | 1 | TachoDriverActivityRepository |
| `ui/views/settings_view.py` | 1 | AutoMailRepository |
| `ui/views/dashboard.py` | 1 | AnalyticsRepository |
| `ui/views/generators_view.py` | 1 | DriverRepository |
| `ui/views/automation_worker.py` | 1 | PipelineRepository |
| `ui/views/document_center_view.py` | 1 | DocumentService(db) |
| **Total** | **41+** | |

---

# 10. BEFORE vs. AFTER REFACTORING EXAMPLES

## Example 1: Service Logic (Inline SQL → Injected Repository)

**BEFORE** — `services/document_automation/document_grouper.py`:

```python
class DocumentGrouper:
    def __init__(self, db):
        self.db = db
        self.pipeline = PipelineRepository(db)
        self._doc_repo = DocumentRepository(db)
        self._trip_repo = TripRepository(db)

    def group_documents_for_trip(self, trip_id: int) -> Dict[str, Any]:
        row = self.db.conn.execute(
            "SELECT documents_attached FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        return {"count": row[0] if row else 0}
```

**AFTER** — `services/document_automation/document_grouper.py`:

```python
from typing import Dict, Optional
from repositories.trip_repository import TripRepository
from repositories.document_repository import DocumentRepository
from repositories.pipeline_repository import PipelineRepository


class DocumentGrouper:
    def __init__(
        self,
        db,
        trip_repo: Optional[TripRepository] = None,
        doc_repo: Optional[DocumentRepository] = None,
        pipeline_repo: Optional[PipelineRepository] = None,
    ):
        self.db = db
        self._trip_repo = trip_repo if trip_repo is not None else TripRepository(db)
        self._doc_repo = doc_repo if doc_repo is not None else DocumentRepository(db)
        self._pipeline = pipeline_repo if pipeline_repo is not None else PipelineRepository(db)

    def group_documents_for_trip(self, trip_id: int) -> Dict[str, Any]:
        count = self._trip_repo.get_documents_attached(trip_id)
        return {"count": count}
```

## Example 2: UI View (Direct Repository → ApiClient)

**BEFORE** — `ui/views/automation_view.py`:

```python
from repositories.pipeline_repository import PipelineRepository
from repositories.document_repository import DocumentRepository


class QtAutomationView(QWidget):
    def __init__(self, parent, db, prefs=None, ops=None):
        self._pipeline_repo = PipelineRepository(db)
        self._doc_repo = DocumentRepository(db)

    def _refresh_from_db(self) -> None:
        runs = self._pipeline_repo.get_pending_runs()
        # ... render runs
```

**AFTER** — `ui/views/automation_view.py`:

```python
from client.api_client import ApiClient


class QtAutomationView(QWidget):
    def __init__(self, parent, db, prefs=None, ops=None, api_client=None):
        self._api = api_client if api_client is not None else ApiClient()
        # db kept for backward compatibility, not used directly

    def _refresh_from_db(self) -> None:
        try:
            response = self._api.list_documents(category="pipeline")
            runs = response.get("items", [])
        except Exception:
            runs = []  # fallback to empty state
        # ... render runs
```
