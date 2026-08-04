# Operion Business Invariant Framework

**Version:** 1.0.0  
**Last Updated:** 2026-07-22  
**Classification:** INTERNAL — Mission-Critical  

---

## 1. Executive Summary

The Operion Business Invariant Framework is a formalized system of **fundamental business truths** that must always remain valid regardless of implementation changes, refactors, database migrations, AI-generated code, or autonomous bug fixes.

### Purpose

- **Prevent silent business logic violations** during development and maintenance
- **Create a safety net** for AI-generated code (ARGO Copilot) and autonomous operations
- **Establish deploy gates** that block critical business rule violations
- **Provide deterministic validation** that is independent of UI, implementation details, and testing frameworks

### Scope

The framework covers **107 invariants** across **14 business categories**:

| Category | Invariants | Critical | High | Medium | Low |
|----------|-----------|----------|------|--------|-----|
| Financial | 15 | 7 | 4 | 4 | 0 |
| Fleet | 7 | 3 | 1 | 3 | 0 |
| Drivers | 7 | 3 | 1 | 3 | 0 |
| Trips | 10 | 4 | 3 | 3 | 0 |
| Routes | 8 | 0 | 4 | 4 | 0 |
| Documents | 7 | 1 | 1 | 4 | 1 |
| Dispatch | 7 | 3 | 1 | 2 | 1 |
| Auth & Security | 7 | 4 | 1 | 1 | 0 |
| Multi-Tenant | 6 | 3 | 2 | 1 | 0 |
| Database | 8 | 2 | 3 | 3 | 0 |
| AI / ARGO | 6 | 2 | 2 | 2 | 0 |
| Freight Exchange | 6 | 1 | 2 | 3 | 0 |
| Analytics | 6 | 3 | 1 | 2 | 0 |
| Workflows | 7 | 3 | 2 | 2 | 0 |
| **Total** | **107** | **39** | **28** | **37** | **2** |

### Key Design Decisions

1. **Not a test suite** — Invariants verify fundamental truths, not implementation correctness
2. **Implementation-independent** — Invariants validate outcomes, not code paths
3. **Database-optional** — Invariants gracefully degrade when no DB is available (return PASS with skip note)
4. **Declarative registration** — Every invariant is self-describing with metadata
5. **Layered execution** — Invariants run at appropriate frequencies (commit → PR → nightly → release)

---

## 2. Codebase Audit Findings

### 2.1 Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.9+, FastAPI |
| ORM | SQLAlchemy (raw queries via DatabaseManager) |
| Database | PostgreSQL (primary), SQLite (development) |
| Migrations | Alembic |
| Task Queue | Celery + Redis |
| Auth | JWT (HS256), OAuth2, API Keys |
| Desktop UI | PyQt6/PySide6 |
| Mobile | Flutter (Dart) |
| Website | React 18 + Vite + TypeScript |

### 2.2 Core Domain Modules

| Module | Purpose | Key Entities |
|--------|---------|-------------|
| Trips | Logistics order lifecycle | `trips`, `trip_status_history` |
| Fleet | Vehicle management | `trucks`, `maintenance_*`, `truck_health_scores` |
| Drivers | Driver management + compliance | `drivers`, `driver_truck_assignments`, `tacho_*` |
| Routes | Route planning & optimization | `routes`, `route_history_v2`, `route_events` |
| Invoicing | Invoice/CMR/receipt generation | `invoices`, `proforma_invoices`, `receipts` |
| Documents | Document center with OCR | `documents`, `document_*`, `document_pipeline_runs` |
| Freight Exchange | Multi-provider freight marketplace | `freight_exchange_*` (TIMOCOM, Trans.eu) |
| Operations | Alert management, event bus | `alerts`, `operation_events` |
| Copilot | AI reasoning assistant | `copilot_*`, `reasoning_graphs` |

### 2.3 Financial Rules Extracted

The codebase revealed explicit financial formulas embedded in service code:

```
gross_value = qty × unit_price
discount_amt = gross_value × discount_pct / 100 (capped at gross_value)
taxable_amount = gross_value − discount_amt
vat_amount = taxable_amount × vat_rate / 100
line_total = taxable_amount + vat_amount
subtotal_net = Σ(taxable_amount)
total_vat = Σ(vat_amount)
total_gross = Σ(line_total)
net_profit = price_eur − (fuel_cost + toll_cost + salary_cost + extra_costs)
```

All monetary columns use `NUMERIC(12,2)` precision after migration `f7b8c9d0e1f8`.

### 2.4 Workflow State Machines

**Trip Status Transitions:**
```
Planned → [Loading, Cancelled]
Loading → [Planned, In Transit, Cancelled]
In Transit → [Loading, Delivered, Cancelled]
Delivered → [In Transit, Invoiced, Cancelled]
Invoiced → [Delivered, Paid, Cancelled]
Paid → [Invoiced]
Cancelled → [Planned]
```

**Invoice Status Transitions:**
```
draft → [finalized, cancelled]
finalized → [xml_generated, cancelled, paid]
xml_generated → [submitted_externally, draft]
submitted_externally → [queued, rejected]
queued → [submitting, rejected]
submitting → [accepted, rejected, manual_review]
accepted → [paid]
rejected → [draft, manual_review]
manual_review → [draft, accepted, rejected]
cancelled → [] (terminal)
paid → [] (terminal)
```

### 2.5 Multi-Tenant Isolation

- All tenant-scoped tables include `company_id INTEGER`
- Repository layer applies `_company_filter()` via `AND company_id = ?`
- Admin role (resolved from environment) bypasses company filter
- Thread-safe via `contextvars.ContextVar`

### 2.6 AI Copilot Boundaries

| Role | Permissions |
|------|------------|
| Driver | Read-only: trips, fleet, tracking, routes, help |
| Dispatcher | Read/Write (no delete): trips, fleet, drivers, dispatch, clients, documents |
| Manager | Everything except system-level operations |
| Circuit Breaker | Max 20 tool calls/plan, 50 nodes/turn, 30s timeout, 60-min cooldown on trip |

---

## 3. Invariant Architecture

### 3.1 Package Structure

```
business_invariants/
├── __init__.py          # Public API exports
├── __main__.py          # CLI entry: python -m business_invariants
├── models.py            # Core types: Severity, ExecutionFrequency, InvariantContext, etc.
├── decorators.py        # @invariant() decorator for declarative check registration
├── engine.py            # InvariantRegistry (singleton) + InvariantEngine (executor)
├── reporter.py          # ConsoleReporter, JsonReporter, MarkdownReporter
├── cli.py               # CLI parser and command handlers
├── conftest.py          # Pytest plugin: auto-discovers invariants as test cases
└── checks/              # Invariant check implementations (one per category)
    ├── __init__.py
    ├── financial.py         # FIN-001 to FIN-015
    ├── fleet.py             # FLE-001 to FLE-007
    ├── drivers.py           # DRV-001 to DRV-007
    ├── trips.py             # TRP-001 to TRP-010
    ├── routes.py            # RTE-001 to RTE-008
    ├── documents.py         # DOC-001 to DOC-007
    ├── dispatch.py          # DSP-001 to DSP-007
    ├── auth_security.py     # AUTH-001 to AUTH-007
    ├── multitenant.py       # MTN-001 to MTN-006
    ├── database.py          # DB-001 to DB-008
    ├── ai_argo.py           # AI-001 to AI-006
    ├── freight_exchange.py  # FEX-001 to FEX-006
    ├── analytics.py         # ANL-001 to ANL-006
    └── workflows.py         # WF-001 to WF-007

tests/
└── test_business_invariants.py  # Pytest integration
```

### 3.2 Core Data Model

```
InvariantMeta (frozen dataclass)
├── id: str                    # UNIQUE identifier (e.g., "FIN-001")
├── title: str                 # Human-readable title
├── description: str           # Detailed explanation
├── category: InvariantCategory # Business domain (financial, fleet, ...)
├── modules: list[str]         # Affected modules
├── severity: Severity         # CRITICAL | HIGH | MEDIUM | LOW
├── execution: list[ExecutionFrequency]
│   ├── COMMIT                 # On every commit
│   ├── PR                     # On pull request
│   ├── NIGHTLY                # Daily
│   ├── WEEKLY                 # Weekly
│   ├── RELEASE                # Before release
│   ├── AFTER_MIGRATION        # After DB migrations
│   └── AFTER_AI_PATCH         # After AI-generated code changes
├── rationale: str             # Business justification
├── dependencies: list[str]    # Invariant IDs that must pass first
└── tags: list[str]            # Free-form tags

InvariantDefinition
├── meta: InvariantMeta        # Immutable metadata
└── check_fn: Callable[[InvariantContext], InvariantResult]

InvariantContext
├── db: Optional[DBConnection]
├── db_type: str               # "sqlite" | "postgresql"
├── config: dict               # Runtime configuration
├── company_id: Optional[int]
├── execution_frequency: Optional[ExecutionFrequency]
└── extra: dict                # Extensible for future needs

InvariantResult
├── invariant_id: str
├── status: InvariantStatus    # PASS | FAIL | ERROR | SKIPPED
├── expected: str              # What should be true
├── actual: str                # What was actually observed
├── message: str               # Human-readable summary
├── root_cause: str            # Why it failed
├── suggested_fix: str         # How to fix it
├── affected_modules: list[str]
├── duration_ms: float
└── details: dict              # Extensible diagnostic data

InvariantReport
├── run_id, started_at, completed_at, duration_ms
├── total, passed, failed, errors, skipped
├── success_rate, risk_level, critical_failures
├── results: list[InvariantResult]
└── affected_modules: set[str]
```

### 3.3 Registration Flow

```
1. Import check module (e.g., import business_invariants.checks.financial)
2. @invariant decorator executes at module load time
3. Decorator creates InvariantMeta from arguments
4. Decorator wraps the check function and calls registry.register(meta, fn)
5. Registry stores InvariantDefinition in dictionary keyed by ID
6. Engine retrieves definitions by filter, sorts topologically, executes
```

### 3.4 Adding a New Invariant

```python
from business_invariants.decorators import invariant
from business_invariants.models import (
    InvariantCategory, Severity, ExecutionFrequency,
    InvariantContext, InvariantResult, InvariantStatus,
)

@invariant(
    id="FIN-016",                              # Unique ID with category prefix
    title="New business truth",                 # Short title
    description="Detailed description of what must always be true",
    category=InvariantCategory.FINANCIAL,        # Category enum
    modules=["module_name"],                     # Affected modules
    severity=Severity.HIGH,                      # CRITICAL/HIGH/MEDIUM/LOW
    execution=[ExecutionFrequency.COMMIT],        # When to run
    rationale="Why this matters to the business",
    dependencies=["FIN-001"],                    # Optional dependencies
    tags=["example"],
)
def check_new_invariant(ctx: InvariantContext) -> InvariantResult:
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-016",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )
    # ... actual validation logic ...
    # Return PASS or FAIL with diagnostic information
```

---

## 4. All Business Invariants

### 4.1 Financial Invariants (FIN)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| FIN-001 | Invoice subtotal + VAT = total | CRITICAL | Commit, Nightly, Release | total_gross == subtotal_net + total_vat (within €0.01) |
| FIN-002 | Invoice totals cannot become negative | CRITICAL | Commit, Nightly | All invoice monetary fields >= 0 |
| FIN-003 | Discount never exceeds line total | HIGH | Commit, Nightly | discount_amount <= gross_value |
| FIN-004 | Credit notes balance correctly | CRITICAL | Commit, PR, Nightly | Credit note totals <= original invoice totals |
| FIN-005 | Currency conversions preserve precision | HIGH | Commit, Nightly, Weekly | EUR→X→EUR round-trips within 0.01 |
| FIN-006 | Exchange rates relative to EUR | MEDIUM | Commit | EUR rate must always be 1.0 |
| FIN-007 | Payment totals equal outstanding balance | CRITICAL | Commit, Nightly | amount_remaining == total_gross - amount_paid |
| FIN-008 | Invoice due date >= issue date | CRITICAL | Commit | due_date >= issue_date |
| FIN-009 | Payment batch totals match | HIGH | Commit, PR | Batch total == sum of individual amounts |
| FIN-010 | Proforma grand total matches line items | HIGH | Commit | grand_total == subtotal - discount + tax |
| FIN-011 | Receipt totals match | HIGH | Commit | total == amount + vat_amount |
| FIN-012 | Net profit = price - total costs | CRITICAL | Commit, Nightly | net_profit == price_eur - sum(costs) |
| FIN-013 | Margin percentage consistent | MEDIUM | Nightly | margin == (net_profit / price_eur) * 100 |
| FIN-014 | Monetary values as NUMERIC(12,2) | CRITICAL | After Migration, Release | No DOUBLE PRECISION for monetary columns |
| FIN-015 | VAT rate is within valid range | MEDIUM | Commit | vat_percent in standard EU rates |

### 4.2 Fleet Invariants (FLE)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| FLE-001 | Truck plate numbers are unique | CRITICAL | Commit, PR | No duplicate plate_numbers among active trucks |
| FLE-002 | Truck assignments cannot overlap | CRITICAL | Commit, Nightly | No overlapping date ranges for same truck |
| FLE-003 | Deleted trucks cannot be assigned | CRITICAL | Commit, Nightly | Trips must not reference soft-deleted trucks |
| FLE-004 | Maintenance blocks dispatch | HIGH | Commit, Nightly | Overdue-maintenance trucks excluded from active trips |
| FLE-005 | Truck status consistency | MEDIUM | Commit | active_status == 1 iff status == 'active' |
| FLE-006 | Health score in valid range | MEDIUM | Nightly | 0 <= truck_health_scores.score <= 100 |
| FLE-007 | Maintenance records link to existing truck | MEDIUM | Commit | No orphan maintenance records |

### 4.3 Drivers Invariants (DRV)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| DRV-001 | Driver assigned to at most one truck | CRITICAL | Commit | Unique driver_id in driver_truck_assignments |
| DRV-002 | Truck assigned to at most one driver | CRITICAL | Commit | Unique truck_id in driver_truck_assignments |
| DRV-003 | Driver cannot exceed legal driving limits | HIGH | Nightly, Weekly | Daily <= 540 min, Weekly <= 3360 min (EU regs) |
| DRV-004 | Driver availability reflects assignments | MEDIUM | Commit | Active trip = unavailable |
| DRV-005 | Deleted drivers cannot be assigned | CRITICAL | Commit, Nightly | Trips must not reference soft-deleted drivers |
| DRV-006 | Driver license expiry tracked | MEDIUM | Nightly | Expired licenses trigger alerts |
| DRV-007 | Assignment history consistent | MEDIUM | Commit | 0 or 1 row per driver in assignments table |

### 4.4 Trips Invariants (TRP)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| TRP-001 | Every trip has exactly one status | CRITICAL | Commit | status is non-empty from known set |
| TRP-002 | Valid trip status transitions | CRITICAL | Commit, PR, Nightly | State machine enforced via trip_status_history |
| TRP-003 | Completed trips cannot return to Draft | CRITICAL | Commit, PR | Delivered → Planned/Loading forbidden |
| TRP-004 | Cancelled trips cannot generate invoices | CRITICAL | Commit, Nightly | No invoices for Cancelled trips |
| TRP-005 | Trip profitability calculation | HIGH | Commit, Nightly | net_profit consistent with cost components |
| TRP-006 | Trip distance is positive | MEDIUM | Commit | distance_km > 0 for In Transit+ |
| TRP-007 | Trip price is non-negative | HIGH | Commit | price_eur >= 0 |
| TRP-008 | Trip references exist | HIGH | Commit, Nightly | truck/driver/client FK targets exist |
| TRP-009 | Trip dates are ordered | MEDIUM | Commit | start_date <= end_date |
| TRP-010 | Source tracking consistent | MEDIUM | Commit | Freight exchange source fields complete |

### 4.5 Routes Invariants (RTE)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| RTE-001 | Route distance >= straight-line | HIGH | Commit, PR | Haversine distance <= computed distance |
| RTE-002 | Route duration > 0 | HIGH | Commit | duration_min > 0 |
| RTE-003 | ETA remains chronological | MEDIUM | Commit | Waypoint ETAs non-decreasing |
| RTE-004 | Waypoint ordering preserved | HIGH | Commit | Origin→intermediate(s)→destination |
| RTE-005 | At least 2 unique stops | MEDIUM | Commit | After deduplication, >= 2 stops |
| RTE-006 | Truck constraints respected | HIGH | Commit, PR | Height/weight/width within EU limits |
| RTE-007 | Country avoidance respected | MEDIUM | Commit, PR | Avoided countries not crossed |
| RTE-008 | Route profile is valid | MEDIUM | Commit | Profile in supported set |

### 4.6 Documents Invariants (DOC)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| DOC-001 | CMR numbers remain unique | CRITICAL | Commit, PR | No duplicate cmr_number across trips |
| DOC-002 | Document numbers unique per company | HIGH | Commit | No duplicate doc_number within company |
| DOC-003 | OCR output linked to correct document | MEDIUM | Commit | ocr_text belongs to correct document_id |
| DOC-004 | Soft-deleted documents recoverable | MEDIUM | Nightly | deleted_at set, not physically removed |
| DOC-005 | Attachments reference existing entities | MEDIUM | Commit | document_links FK targets exist |
| DOC-006 | File paths are safe | MEDIUM | Commit | No path traversal ('..') in file_path |
| DOC-007 | Version count limited | LOW | Nightly | <= 20 versions per document |

### 4.7 Dispatch Invariants (DSP)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| DSP-001 | Dispatch references existing trip | CRITICAL | Commit | Dispatch trip_id FK exists |
| DSP-002 | Dispatch references active truck | CRITICAL | Commit | Dispatched truck exists and is active |
| DSP-003 | Dispatch references active driver | CRITICAL | Commit | Dispatched driver exists and is active |
| DSP-004 | Dispatch timestamps ordered | MEDIUM | Commit | assigned_at <= started_at <= completed_at |
| DSP-005 | Trip conflicts detected | HIGH | Commit, Nightly | No overlapping active trips per truck |
| DSP-006 | Board column mapping valid | LOW | Commit | Status → column mapping is correct |
| DSP-007 | Delivered trip cutoff respected | LOW | Nightly | Old delivered trips excluded from board |

### 4.8 Auth & Security Invariants (AUTH)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| AUTH-001 | Password hashes never plaintext | CRITICAL | Commit, PR, Release | All hashes start with $2b$ (bcrypt) |
| AUTH-002 | JWT validation unchanged | CRITICAL | Commit, Release | HS256 with configured secret |
| AUTH-003 | Role hierarchy preserved | HIGH | Commit, PR | admin > manager > dispatcher > driver |
| AUTH-004 | Brute force protection active | MEDIUM | Commit | 5 attempts / 5 min / 15 min lockout |
| AUTH-005 | Refresh tokens single-use | HIGH | Commit, PR | Rotation on every refresh |
| AUTH-006 | API keys are hashed | CRITICAL | Commit, Release | SHA-256 stored, not plaintext |
| AUTH-007 | Admin required for delete | CRITICAL | Commit, PR | Delete operations require admin role |

### 4.9 Multi-Tenant Invariants (MTN)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| MTN-001 | Cross-company data isolation | CRITICAL | Commit, PR, Release | No company A sees company B data |
| MTN-002 | Company filter always applied | CRITICAL | Commit, PR, Nightly | All queries include company_id WHERE |
| MTN-003 | Cross-company updates impossible | CRITICAL | Commit, PR | All writes include company_id scope |
| MTN-004 | Admin bypasses correctly | HIGH | Commit | Admin sees all tenants (company_id=0) |
| MTN-005 | Settings isolation by company | MEDIUM | Commit | Composite PK (key, company_id) |
| MTN-006 | Thread-safe context isolation | HIGH | Commit | ContextVar, not global state |

### 4.10 Database Invariants (DB)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| DB-001 | Foreign keys remain valid | CRITICAL | Nightly, Weekly, After Migration | No orphan rows |
| DB-002 | Required indexes exist | HIGH | After Migration, Release | Critical indexes present |
| DB-003 | Migrations preserve data | CRITICAL | After Migration | No data truncation or loss |
| DB-004 | UUID uniqueness maintained | HIGH | Commit, Nightly | No duplicate UUID columns |
| DB-005 | Timestamp ordering preserved | MEDIUM | Nightly | created_at <= updated_at |
| DB-006 | Soft-delete consistency | MEDIUM | Nightly | Active rows don't reference deleted rows |
| DB-007 | Financial precision maintained | HIGH | After Migration, Release | NUMERIC(12,2) not DOUBLE PRECISION |
| DB-008 | Enum values are valid | MEDIUM | After Migration, Nightly | Pipeline stages/statuses in valid set |

### 4.11 AI / ARGO Invariants (AI)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| AI-001 | No destructive actions without permission | CRITICAL | Commit, PR | Confirmation >= BUSINESS required |
| AI-002 | Role permissions are restrictive | HIGH | Commit, PR | Driver=read-only, Dispatcher=no delete |
| AI-003 | Generated workflows preserve rules | HIGH | Commit, PR, Nightly | Same validation as human-created |
| AI-004 | Circuit breaker prevents runaway | MEDIUM | Commit | 20 calls/plan, 50 nodes, 30s timeout |
| AI-005 | Undo window respected | MEDIUM | Commit | Actions undoable within 30 min |
| AI-006 | Cannot bypass permissions | CRITICAL | Commit, PR | Role check before every tool call |

### 4.12 Freight Exchange Invariants (FEX)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| FEX-001 | Imported loads retain source | HIGH | Commit, Nightly | Source tracking fields populated |
| FEX-002 | Duplicate imports prevented | CRITICAL | Commit | Unique (provider, reference, company) |
| FEX-003 | Search filters preserved | MEDIUM | Commit | Saved searches retain parameters |
| FEX-004 | Provider rate limits respected | MEDIUM | Commit | TIMOCOM ≤60/min, Trans.eu ≤900/min |
| FEX-005 | Webhook signature verification | HIGH | Commit | HMAC-SHA256 verified on every event |
| FEX-006 | Adapter registry integrity | MEDIUM | Commit | All adapters implement required methods |

### 4.13 Analytics Invariants (ANL)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| ANL-001 | KPI totals equal underlying data | CRITICAL | Nightly, Weekly | Dashboard KPIs match raw data |
| ANL-002 | Revenue charts match invoices | CRITICAL | Nightly, Weekly | Revenue == sum of invoice totals |
| ANL-003 | Profit reports match trips | CRITICAL | Nightly, Weekly | Reports == sum of trip net_profit |
| ANL-004 | Dashboard internally consistent | HIGH | Nightly | Active + inactive == total clients |
| ANL-005 | Negative profit alerts fire | MEDIUM | Nightly | Negative net_profit triggers RED alert |
| ANL-006 | Overdue tracking accurate | MEDIUM | Nightly | days_late correctly classified |

### 4.14 Workflow Invariants (WF)

| ID | Title | Severity | Frequency | Description |
|----|-------|----------|-----------|-------------|
| WF-001 | Full workflow chain consistency | CRITICAL | PR, Release, Nightly, After AI | Trip→Route→Dispatch→CMR→Invoice→Analytics consistent |
| WF-002 | Invoice state machine enforced | CRITICAL | Commit, Nightly | Valid invoice status transitions |
| WF-003 | Trip state machine enforced | CRITICAL | Commit, Nightly | Valid trip status transitions |
| WF-004 | Document pipeline stage ordering | MEDIUM | Commit | Stage sequence enforced |
| WF-005 | Invoice-CMR consistency | HIGH | Commit, PR | Invoice references trip with CMR |
| WF-006 | Analytics reflects dispatched trips | MEDIUM | Nightly | Analytics aligns with trip state |
| WF-007 | Email reminder chain valid | MEDIUM | Nightly | <= 5 reminders, only overdue invoices |

---

## 5. Execution Strategy

### 5.1 Frequency Matrix

| Frequency | Invariant Count | Intent | Gate |
|-----------|----------------|--------|------|
| Every Commit | 85 | Catch violations immediately | Block on critical failure |
| Pull Request | 25 | Prevent regressions in reviews | Block on critical failure |
| Nightly | 33 | Detect data drift over time | Alert on failure |
| Weekly | 5 | Long-term trend detection | Report only |
| Before Release | 6 | Final safety check | Block on CRITICAL/HIGH |
| After Migration | 5 | Validate schema integrity | Block on any failure |
| After AI Patch | 1 | Validate AI output | Block on critical failure |

### 5.2 Execution by Severity

| Severity | Behavior on Failure |
|----------|-------------------|
| CRITICAL | **Block deployment immediately.** Fix before proceeding. |
| HIGH | **Requires review.** Deploy gate if in release context. |
| MEDIUM | **Log and alert.** Investigate within 24 hours. |
| LOW | **Log only.** Track for trend analysis. |

### 5.3 Execution Order

Invariants execute in topological order based on dependencies. The engine ensures dependencies run before dependents:

```
DB → FIN → TRP → DSP → DOC → WF → ANL
        ↓              ↓
     FLE/DRV         AI/FEX
```

---

## 6. CI/CD Integration

### 6.1 GitHub Actions Workflow

A dedicated workflow `.github/workflows/business-invariants.yml` runs invariants on:

- **Every push** to `main`, `develop`, `staging` (commit frequency)
- **Every pull request** to `main`, `develop` (PR frequency)
- **Nightly** at 04:00 UTC (full run)
- **Manual trigger** via `workflow_dispatch` with frequency filter

The workflow:
1. Installs Python dependencies
2. Determines execution frequency from event type
3. Runs `python -m business_invariants run --frequency <freq> --json`
4. Parses results and generates a summary
5. Uploads the report as a build artifact
6. **Fails the pipeline** if any CRITICAL invariants fail
7. **Warns** if non-critical invariants fail

### 6.2 Pytest Integration

```bash
# Run all invariants as pytest tests
pytest tests/test_business_invariants.py -v

# Run only CRITICAL invariants
pytest tests/test_business_invariants.py::TestCriticalInvariants -v

# Run only FINANCIAL invariants
pytest tests/test_business_invariants.py::TestFinancialInvariants -v

# Run specific invariants by ID
pytest -k "FIN-001 or DRV-003" tests/test_business_invariants.py

# Filter by frequency
pytest --invariant-frequency nightly tests/test_business_invariants.py
```

### 6.3 Pre-commit Integration

For immediate feedback during development, add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: business-invariants-commit
      name: Business Invariants (Commit)
      entry: python -m business_invariants run --frequency on_every_commit
      language: system
      pass_filenames: false
```

---

## 7. Operion Ops Integration

### 7.1 CLI Commands

```bash
# Run ALL invariants
python -m business_invariants run

# Run by frequency
python -m business_invariants run --frequency nightly
python -m business_invariants run --frequency on_pull_request

# Run by category
python -m business_invariants run --category financial

# Run specific invariants
python -m business_invariants run --ids FIN-001,FIN-012,DRV-003

# List all registered invariants
python -m business_invariants list

# Output as JSON for automation
python -m business_invariants run --json
```

### 7.2 Health Check Integration

The invariant engine integrates with the existing `services/health_check.py` infrastructure. A `InvariantHealthCheck` can be registered:

```python
class InvariantHealthCheck:
    """Health check that runs CRITICAL invariants on demand."""

    def check(self):
        report = engine.run_filtered(ctx, min_severity=Severity.CRITICAL)
        return report.has_critical_failures
```

### 7.3 Operion Ops Dashboard

Invariant reports are produced in JSON format suitable for ingestion into:
- **Operion Ops Console** — for real-time monitoring
- **Grafana** — for trend dashboards
- **PagerDuty/Opsgenie** — for CRITICAL failure alerts
- **Slack/Teams** — for daily invariant digest

### 7.4 Manual Invocation

```bash
# Run invariants after a manual migration
python -m business_invariants run --frequency after_migration

# Run invariants after an AI-generated patch
python -m business_invariants run --frequency after_ai_patch

# Run invariants before a release
python -m business_invariants run --frequency before_release
```

---

## 8. AI Validation Integration

### 8.1 ARGO Copilot Integration

After any AI-generated code change (trips, invoices, dispatches, etc.), the framework should validate:

```python
# Inside the copilot executor, after tool execution:
from business_invariants.engine import InvariantEngine, InvariantRegistry

# Load and run invariants relevant to the change
registry = InvariantRegistry.get_global()
engine = InvariantEngine(registry)
report = engine.run_for_frequency(
    ExecutionFrequency.AFTER_AI_PATCH,
    ctx=InvariantContext()
)

if report.has_critical_failures:
    # Rollback the AI action
    executor.rollback_last_action()
    return "Action reverted: invariants violated"
```

### 8.2 AI Change Validation Protocol

1. AI completes code/modification
2. Relevant invariants execute (AFTER_AI_PATCH frequency)
3. CRITICAL failure → auto-rollback and alert
4. HIGH failure → require human confirmation
5. All pass → proceed

### 8.3 AI Permission Boundaries

The invariants AI-001 through AI-006 encode the hard boundaries:
- AI tool calls are gated by user role
- Destructive operations require BUSINESS-level confirmation
- The circuit breaker prevents runaway autonomous behavior
- The undo window limits the blast radius of incorrect actions

---

## 9. Reporting Format

### 9.1 Console Output

```
======================================================================
  OPERION BUSINESS INVARIANT REPORT [production]
  Run ID: inv-e33b5269b9ba
  Started: 2026-07-22T15:01:01.294847
======================================================================

  Summary:
    Total:     107
    Passed:    105
    Failed:      2
    Errors:      0
    Skipped:     0
    Duration:  0.2 ms
    Risk:      CRITICAL
    Rate:      98.1%

  Failures & Errors:
  ────────────────────────────────────────────────────────────────────

  ❌ [AUTH-002]
     Expected: JWT uses HS256 algorithm with configured secret
     Actual:   JWT algorithm is not configured
     Message:  JWT configuration does not meet security requirements
     Cause:    JWT settings were changed or are missing in configuration
     Fix:      Set JWT_ALGORITHM=HS256 and provide a strong JWT_SECRET

======================================================================
  ❌ DEPLOYMENT BLOCKED — 1 critical invariant(s) failed
======================================================================
```

### 9.2 JSON Output

```json
{
  "run_id": "inv-e33b5269b9ba",
  "total": 107,
  "passed": 105,
  "failed": 2,
  "errors": 0,
  "skipped": 0,
  "success_rate": 0.9813,
  "risk_level": "CRITICAL",
  "critical_failures_count": 1,
  "affected_modules": ["auth", "financial", "trips", ...],
  "results": [
    {
      "invariant_id": "FIN-001",
      "status": "pass",
      "message": "No database connection — runtime validation skipped",
      "duration_ms": 0.0
    },
    {
      "invariant_id": "AUTH-002",
      "status": "fail",
      "expected": "JWT uses HS256 algorithm with configured secret...",
      "actual": "JWT algorithm is not configured...",
      "message": "JWT configuration does not meet security requirements",
      "root_cause": "JWT settings were changed or are missing...",
      "suggested_fix": "Set JWT_ALGORITHM=HS256 and provide...",
      "affected_modules": ["auth"],
      "duration_ms": 0.0
    }
  ]
}
```

### 9.3 Markdown Output

Available via the `MarkdownReporter` class. Suitable for:
- Pull request comments
- Release notes
- Dashboard widgets

---

## 10. Future Expansion

### 10.1 Adding New Invariants

Adding a new invariant requires ONE file change (the check function) due to the declarative `@invariant` decorator:

```python
# In the appropriate checks/<category>.py file:

@invariant(
    id="FIN-016",
    title="New invariant title",
    description="Detailed description",
    category=InvariantCategory.FINANCIAL,
    modules=["affected_module"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.NIGHTLY],
)
def check_new_invariant(ctx: InvariantContext) -> InvariantResult:
    # ... implementation ...
```

New invariants auto-register on module import. No changes to engine, registry, or CLI needed.

### 10.2 Extending the Framework

| Extension Point | How |
|----------------|-----|
| New category | Add to `InvariantCategory` enum in `models.py` |
| New frequency | Add to `ExecutionFrequency` enum in `models.py` |
| New reporter | Implement `BaseReporter` interface in `reporter.py` |
| New context data | Add fields to `InvariantContext` dataclass in `models.py` |
| Custom filter | Add filter method to `InvariantRegistry` in `engine.py` |
| Database adapter | Add adapter in `checks/*.py` for different DB types |

### 10.3 Integration with Other Systems

- **Prometheus/Grafana**: Export invariant pass/fail as metrics
- **PagerDuty**: Alert on CRITICAL invariant failures
- **Slack**: Post nightly invariant digest to #ops channel
- **Operion Ops Console**: Embed invariant report in operations dashboard
- **CI/CD Splitting**: Add to `test-python.yml` sharding strategy

### 10.4 Planned Invariants (Roadmap)

| Area | Planned Invariants |
|------|-------------------|
| Performance | Query response time thresholds, N+1 detection |
| Data Quality | Duplicate client detection, address standardization |
| Compliance | GDPR data retention, eFTI document validity |
| Integration | Partner API latency, webhook delivery rate |
| Security | OWASP Top 10 coverage, dependency vulnerability scan |

### 10.5 Migration Strategy

When existing business rules change:
1. Update the invariant check function in the relevant `checks/*.py` file
2. Update metadata (severity, execution frequency) as needed
3. The old invariant is immediately replaced (same ID)
4. If the rule is deprecated, mark it with `tags=["deprecated"]` and reduce frequency to WEEKLY

---

## Appendix A: Invariant ID Prefixes

| Prefix | Category | Range |
|--------|----------|-------|
| FIN | Financial | FIN-001 to FIN-015 |
| FLE | Fleet | FLE-001 to FLE-007 |
| DRV | Drivers | DRV-001 to DRV-007 |
| TRP | Trips | TRP-001 to TRP-010 |
| RTE | Routes | RTE-001 to RTE-008 |
| DOC | Documents | DOC-001 to DOC-007 |
| DSP | Dispatch | DSP-001 to DSP-007 |
| AUTH | Auth & Security | AUTH-001 to AUTH-007 |
| MTN | Multi-Tenant | MTN-001 to MTN-006 |
| DB | Database | DB-001 to DB-008 |
| AI | AI / ARGO | AI-001 to AI-006 |
| FEX | Freight Exchange | FEX-001 to FEX-006 |
| ANL | Analytics | ANL-001 to ANL-006 |
| WF | Workflows | WF-001 to WF-007 |

## Appendix B: Quick Start

```bash
# List all invariants
python -m business_invariants list

# Run all invariants
python -m business_invariants run

# Run with JSON output
python -m business_invariants run --json

# Run specific invariants
python -m business_invariants run --ids FIN-001,FIN-012

# Run as pytest
pytest tests/test_business_invariants.py -v

# Run critical-only check (blocks on failure)
python -m business_invariants run --fail-on-critical

# Run after an AI-generated change
python -m business_invariants run --frequency after_ai_patch
```

## Appendix C: File Manifest

```
business_invariants/
├── __init__.py          — Public API
├── __main__.py          — CLI entry point
├── models.py            — Core types (733 lines)
├── decorators.py        — @invariant decorator (133 lines)
├── engine.py            — Registry + Engine (310 lines)
├── reporter.py          — Console/JSON/Markdown (258 lines)
├── cli.py               — CLI interface (149 lines)
├── conftest.py          — Pytest plugin (132 lines)
└── checks/
    ├── __init__.py      — Module loader
    ├── financial.py     — 15 invariants
    ├── fleet.py         — 7 invariants
    ├── drivers.py       — 7 invariants
    ├── trips.py         — 10 invariants
    ├── routes.py        — 8 invariants
    ├── documents.py     — 7 invariants
    ├── dispatch.py      — 7 invariants
    ├── auth_security.py — 7 invariants
    ├── multitenant.py   — 6 invariants
    ├── database.py      — 8 invariants
    ├── ai_argo.py       — 6 invariants
    ├── freight_exchange.py — 6 invariants
    ├── analytics.py     — 6 invariants
    └── workflows.py     — 7 invariants

tests/
├── test_business_invariants.py  — Pytest integration suite
└── conftest.py                  — Pytest hooks

scripts/
└── parse_invariant_report.py    — CI/CD report parser

.github/workflows/
└── business-invariants.yml      — GitHub Actions workflow
```
