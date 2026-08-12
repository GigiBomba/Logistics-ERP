# OPERION ECOSYSTEM LAUNCH INTEGRITY AUDIT — FINAL REPORT

**Date**: 2026-07-20
**Auditor**: Operion Launch Integrity Audit System
**Environment**: Windows 11, Python 3.11, SQLite (test), PySide6 6.11, Flutter (code review only)

---

## EXECUTIVE SUMMARY

### Total Workflows Audited: 9
### READY: 2
### READY AFTER FIX: 4
### NOT READY: 3

### Severity Count
| Severity | Count |
|----------|-------|
| S0 | 0 (7 fixed during audit) |
| S1 | 3 |
| S2 | 5 |
| S3 | 4 |

---

## Launch Readiness Scores

| Category | Score | Status |
|----------|-------|--------|
| Product Integrity | 60 / 100 | ⚠️ DEGRADED |
| Financial Integrity | 40 / 100 | 🔴 NOT READY |
| Regulatory Integrity | 70 / 100 | ⚠️ DEGRADED |
| Cross-App Integrity | 20 / 100 | 🔴 NOT READY |
| Offline Integrity | 10 / 100 | 🔴 NOT READY |
| AI Safety Integrity | 85 / 100 | ⚠️ DEGRADED |
| Security Integrity | 90 / 100 | ✅ READY |
| Operational Integrity | 65 / 100 | ⚠️ DEGRADED |

---

## FINAL VERDICT

# ⛔ LAUNCH NOT APPROVED

**Rationale**: 3 tiers (A2 Financial, C Cross-App, D Offline) have S0-level issues that cannot be resolved with small fixes. The financial accuracy risk from float-based monetary calculations, the incomplete offline sync backend, and the inability to verify cross-application consistency without running all four systems (desktop, mobile, website, backend) simultaneously make this launch unsafe for paying customers. However, significant progress has been made — 7 S0 issues found and fixed during this audit.

---

# TIER A1 — Company Onboarding

## Workflow: Company Onboarding (Website → Registration → Email Verification → Company Creation → Subscription → Desktop Login → Mobile Login)

### Tier
A

### Result
READY AFTER FIX

### Existence
PASS

### Functional Integrity
PASS

### Cross-System Integrity
PARTIAL

### Offline Integrity
N/A

### AI Safety Integrity
N/A

### Production Integrity
RISK

### Severity
S1

### Evidence
* JWT creation and validation tested: `tests/test_security_verification.py` (23 passed) — PyJWT encode/decode verified
* Refresh token rotation: `backend/security.py:123-130` uses `secrets.token_hex(64)` for opaque tokens
* Brute-force lockout: After 5 failed attempts → 429 response (test evidence from security suite)
* Registration endpoints: `tests/test_api/test_api_registration.py` — all pass with token response
* Organization creation: `backend/api/v1/auth.py` handles company creation during registration
* `company_id` propagation: confirmed via grep (100+ matches across repositories, services, and middleware)
* License creation: code paths exist but require PostgreSQL for E2E verification

### Root Cause
Onboarding requires PostgreSQL/Redis for full E2E verification. SQLite-only tests cannot verify the subscription/license pipeline or email verification flow end-to-end. The JWK-to-PyJWT migration introduced an `InsecureKeyLengthWarning` (13-byte test key below 32-byte minimum for SHA256).

### Smallest Safe Fix
None required at code level. For production, ensure `OPERION_JWT_SECRET_KEY` is set to ≥ 256-bit (32 bytes) in the production environment. Add a startup validation warning if the key is too short.

---

# TIER A2 — Financial Accuracy

## Workflow: Financial Accuracy (VAT calculation, invoice totals, currency conversion, PDF rendering, payment terms, due dates, rounding consistency)

### Tier
A

### Result
NOT READY

### Existence
PASS

### Functional Integrity
FAIL

### Cross-System Integrity
FAIL

### Offline Integrity
N/A

### AI Safety Integrity
N/A

### Production Integrity
FAIL

### Severity
S0

### Evidence
* **Float-based arithmetic everywhere**: `services/calculator.py`, `services/cost_engine.py`, `services/invoicing/service.py`, `services/invoicing/generator.py`, `services/exchange_rate_service.py` — ALL monetary calculations use `float` with `round()`. Only `services/invoicing/xml_export.py` uses `Decimal` (properly).
  * `services/calculator.py:96,99-100`: `fuel_cost = (km / 100) * consum_litri * fuel_price` followed by `total_costs = fuel_cost + toll_cost + salary_cost + extra_costs` and `net_profit = price_eur - total_costs` — all float
  * `services/invoicing/service.py:89-92`: `taxable_amount = round(gross_value - discount_amt, 2)`, `vat_amount = round(taxable_amount * vat_rate / 100, 2)` — float before rounding
  * `services/invoicing/service.py:108-110`: **Sum of individually-rounded line items** — guaranteed rounding drift from mathematically correct total
  * `services/exchange_rate_service.py:121-122`: `eur_amount = amount / rate_from; return eur_amount * rate_to` — all float
* **VAT discrepancy warning only**: `services/invoicing/generator.py:388-393` logged a warning and proceeded to generate invoices with inconsistent VAT — **FIXED** during this audit (now raises ValueError)
* **Sum-of-rounded-values drift**: Rounding each line item individually, then summing them, produces totals that can differ from the mathematically correct sum by ±1 cent per line item
* **Division-by-zero**: `services/cost_engine.py:110` (`cost_per_km = round(total_cost / request.distance_km, 4)`) — **FIXED** during this audit (added input validation)
* **Tests passed**: 105/106 financial tests pass (1 Qt visibility test unrelated to production logic)

### Root Cause
The codebase was built with `float` for monetary values throughout. Converting to `Decimal` would require a systematic refactor across ~15 files. The decision to use `float` for financial calculations in a logistics ERP that generates legally binding invoices is a fundamental design gap.

### Smallest Safe Fix
Requires architectural change — cannot be fixed with small edits. Minimum fix:
1. Replace `float` with `Decimal` in all monetary fields in `calculator.py`, `invoicing/service.py`, `generator.py`, `exchange_rate_service.py`, `cost_engine.py`
2. Change line-item summation to use Decimal summation before rounding (not after)
3. All monetary comparisons must use Decimal
4. Estimated effort: 3-5 days for a senior developer

---

# TIER A3 — Regulatory Documents

## Workflow: Regulatory Documents (CMR generation, numbered CMR boxes, UN/CEFACT compliance, eFTI XML validation, export/import round-trip)

### Tier
A

### Result
READY AFTER FIX

### Existence
PASS

### Functional Integrity
PARTIAL

### Cross-System Integrity
PASS

### Offline Integrity
N/A

### AI Safety Integrity
N/A

### Production Integrity
RISK

### Severity
S2

### Evidence
* CMR Generator: `services/invoicing/cmr_generator.py` (1303 lines) — comprehensive CMR waybill document generation
* eFTI XML: `services/invoicing/cmr_efti.py` (571 lines) — eFTI-compliant XML structure with date formatting
* XML export: `services/invoicing/xml_export.py` (391 lines) — proper `Decimal` usage with `ROUND_HALF_UP` (only module in the codebase that does this correctly)
* Test coverage: CMR/eFTI tests exist in the copilot and financial test suites
* `services/invoicing/xml_export.py:38` uses `Decimal` with `ROUND_HALF_UP` — best practice, should be the standard for all financial code

### Root Cause
CMR/eFTI generation code exists and is well-structured. Cannot verify UN/CEFACT XML schema compliance without running an XML validator against generated documents. The `cmr_efti.py` module references UN/CEFACT standard but XML round-trip validation requires PostgreSQL/integration test infrastructure.

### Smallest Safe Fix
Add a pre-launch manual step: generate sample CMR documents and validate against the UN/CEFACT XSD schema. Verify eFTI XML output can round-trip through the European Commission's eFTI validation tool.

---

# TIER B — ARGO (Core Differentiator)

## Workflow: ARGO End-to-End Demo (Natural language dispatch through full workflow)

### Tier
B

### Result
READY AFTER FIX

### Existence
PASS

### Functional Integrity
PASS

### Cross-System Integrity
PARTIAL

### Offline Integrity
N/A

### AI Safety Integrity
PASS

### Production Integrity
RISK

### Severity
S1

### Evidence
* **Full tool infrastructure**: 30+ tools registered across 12 domains (dispatch, trips, fleet, drivers, clients, invoices, routes, OCR, maintenance, freight exchange, automail, email)
* **Safety levels**: SAFE / BUSINESS / DESTRUCTIVE fully implemented via `ConfirmationLevel` enum (`schemas.py:20-26`)
* **Planner**: `planner.py` handles intent extraction from natural language → creates `ExecutionPlan` with steps
* **Executor**: `executor.py` runs plan steps through state machine, checks permissions, validates guardrails
* **Pipeline verification**: 3,461 copilot tests pass (81 skipped, 2 minor temp file failures)
* **Confirmation phrase validation**: **FIXED** during this audit — all 6 DESTRUCTIVE tools now validate confirmation phrase matches entity ID; `dispatch.cancel` now has required `confirmation_phrase` field
* **Tenant isolation**: Redis key patterns `copilot:session:{company_id}:...` and `copilot:conversation:{company_id}:...` ensure ARGO context is per-tenant
* **Circuit breaker**: Per-company runaway prevention (3 consecutive failures, 20 L2 actions/hour, 5 identical action repeats)
* **Guardrails**: 50 node limit, 20 tool calls/plan, 32000 token limit, 30s tool timeout
* **Kill switch**: Platform-wide and per-company kill switch via Redis

### Root Cause
The ARGO pipeline is well-architected and thoroughly tested. The main risks are:
1. Prompt injection sanitizer is Phase 0 (not implemented) — acceptable for keyword-based Phase 1, but must be implemented before LLM integration
2. Plan store is in-memory dict — acceptable for single-instance, must move to Redis for multi-worker
3. WorldModel and AuditLog are stubs — acceptable for current phase, documented for Phase 2+

### Smallest Safe Fix
No further fixes required for the current Phase 1 (keyword-based) implementation. Document the Phase 2+ requirements:
- Prompt injection sanitizer before LLM routing
- Redis-backed plan store for multi-worker scaling
- Persistent audit log table

---

# TIER C — Cross-Application Consistency

## Workflow: Trip Consistency Matrix (Desktop → Backend → Mobile → Documents)

### Tier
C

### Result
NOT READY

### Existence
FAIL

### Functional Integrity
PARTIAL

### Cross-System Integrity
FAIL

### Offline Integrity
N/A

### AI Safety Integrity
N/A

### Production Integrity
FAIL

### Severity
S1

### Evidence
* **Repository model pattern**: Consistent `_company_filter` pattern across all repositories — all queries filter by `company_id`
* **Sync endpoint**: `backend/api/v1/mobile.py:757` — **"Currently a stub"** — only supports trips (200 limit) and messages (100 limit)
* **Field consistency**: Trip model fields (trip ID, client, truck, driver, status, distance, revenue, costs, profit, route geometry, document attachments) are defined consistently in `models/trip_models.py`
* **Cannot verify cross-surface consistency** without running:
  1. Desktop app (PySide6)
  2. Mobile app (Flutter — requires separate repo/build)
  3. Website (React dev server)
  4. Backend API (PostgreSQL required)

### Root Cause
Cross-application consistency cannot be verified in this environment — requires all four systems running simultaneously with real/persistent data. The mobile app is a separate Flutter project with its own build pipeline. E2E testing requires PostgreSQL for shared state.

### Smallest Safe Fix
Requires integration test infrastructure:
1. Start backend with PostgreSQL
2. Run Playwright E2E tests for website
3. Verify mobile app sync manually
4. Compare trip data across all surfaces

---

# TIER D — Offline & Sync Integrity

## Workflow: Driver Offline Scenario (Assign → Disconnect → Upload → Create → Message → Reconnect)

### Tier
D

### Result
NOT READY

### Existence
FAIL

### Functional Integrity
FAIL

### Cross-System Integrity
FAIL

### Offline Integrity
FAIL

### AI Safety Integrity
N/A

### Production Integrity
FAIL

### Severity
S0

### Evidence
* **Mobile action queue**: `mobile_app/lib/core/sync/action_queue.dart` — FIFO queue persisted to JSON files, UUID v4 idempotency keys, Riverpod observable state
* **Mobile delta sync**: `mobile_app/lib/core/sync/delta_sync_service.dart` — cursor-based incremental sync
* **Local storage**: `mobile_app/lib/core/storage/local_db.dart` — **TODO: Replace with Isar** — JSON file-based, no transactions, no indexes, no queries
* **Backend sync endpoint**: `backend/api/v1/mobile.py:757` — **"Currently a stub"** — the comment literally says only trips and messages are supported:
  ```
  "Currently a stub. When entity is specified, queries the corresponding table for rows
   updated after since. Returns an empty result set until entity-specific sync logic
   is wired up."
  ```
* **No server-side action queue**: Mobile `ActionQueue.replayAll()` calls server endpoints directly with no server-side deduplication
* **No sync orchestration**: No `SyncManager` or `SyncOrchestrator` — the `DeltaSyncService` is entity-specific with no overall coordinator
* **Limited entity coverage**: Only trips and messages supported for delta sync — no documents, expenses, drivers, or fleet

### Root Cause
Offline sync was designed but not fully implemented. The backend sync endpoint is explicitly marked as a stub. The mobile app has the client-side infrastructure (action queue, delta sync, connectivity monitor) but the backend cannot process sync requests for most entity types. No server-side action queue means replay can create duplicates.

### Smallest Safe Fix
Requires significant backend work:
1. Wire entity-specific sync logic for all entity types (documents, expenses, drivers, fleet)
2. Add server-side idempotency key storage
3. Create sync orchestration service
4. Replace JSON file storage with Isar on mobile
5. Estimated effort: 4-6 weeks for a full-stack developer

---

# TIER E — AI Safety & Permission Integrity

## Workflow: ARGO Safety Level Audit (SAFE/BUSINESS/DESTRUCTIVE)

### Tier
E

### Result
READY AFTER FIX

### Existence
PASS

### Functional Integrity
PASS

### Cross-System Integrity
PASS

### Offline Integrity
N/A

### AI Safety Integrity
PASS

### Production Integrity
RISK

### Severity
S1

### Evidence
* **Safety levels**: `ConfirmationLevel` enum with SAFE (0), INFORMATIONAL (1), BUSINESS (2), DESTRUCTIVE (3) — `schemas.py:20-26`
* **SAFE tools (L0, execute immediately)**: vehicle_tools, driver_tools, route_tools, tracking_tools, currency_tools, analytics_tools, help_tools
* **BUSINESS tools (L2, require confirmation)**: dispatch_tools (create, bulk_assign), trip_crud_tools, vehicle_crud_tools, driver_crud_tools, client_crud_tools, invoice_tools, proforma_tools, receipt_tools, freight_tools, maintenance_tools, ocr_tools
* **DESTRUCTIVE tools (L3, require typed confirmation)**: trip.delete, vehicle.delete, driver.remove, client.delete, invoice.delete, route.delete, dispatch.cancel, automail.send_now, email.send_bulk
* **Confirmation flow**: Plan stored in `_pending_plans` when `requires_confirmation=True`, client must POST `/plans/{plan_id}/confirm`
* **Permission matrix**: admin (all), manager (all except system-level), dispatcher (read/write operational, no delete), driver (read-only)
* **Confirmation phrase FIX**: **6 S0 issues fixed** during this audit:
  1. All delete tools now validate `confirmation_phrase == str(entity_id)` (was: any non-empty string passed)
  2. `dispatch.cancel` now has a required `confirmation_phrase` field (was: none)
* **Guardrails**: 50 node max, 20 tool calls/plan, 32000 token max, 30s timeout
* **Circuit breaker**: 3 consecutive failures → trip, 20 L2 actions/hour per company, 5 identical action repeats
* **Kill switch**: Platform-wide and per-company (Redis)
* **Undo**: `UNDO_WINDOW_MINUTES = 30`, `supports_undo` flag on tools

### Root Cause
The safety architecture is well-designed. The two gaps found (missing dispatch.cancel confirmation phrase, delete tools not validating phrase against entity ID) were implementation oversights. Both are now fixed.

### Smallest Safe Fix
No further fixes required for launch. Document for Phase 2+:
- Prompt injection sanitizer before LLM integration
- Persistent audit log table (`copilot_audit_log`)
- Distributed plan store (Redis)

---

# TIER F — Security Integrity

## Workflow: Security Launch Audit (Authentication, Multi-Tenancy, File Security)

### Tier
F

### Result
READY

### Existence
PASS

### Functional Integrity
PASS

### Cross-System Integrity
PASS

### Offline Integrity
N/A

### AI Safety Integrity
N/A

### Production Integrity
PASS

### Severity
S3

### Evidence
* **Authentication**: 23/23 security verification tests pass
  * bcrypt password hashing with configurable rounds (`BackendSettings().bcrypt_rounds`)
  * PyJWT token creation/validation (migrated from python-jose)
  * HMAC timing-safe API key comparison (`hmac.compare_digest()`)
  * 128-char refresh tokens (`secrets.token_hex(64)`)
  * Brute-force lockout: 5 failed attempts → 429 response
* **Multi-tenancy**: `ContextVar`-based isolation via `set_company_context()` in `dependencies.py`
  * Every repository applies `_company_filter` for tenant-scoped queries
  * Celery tasks call `set_company_context(company_id)` before DB access
  * ARGO context stores keyed by `company_id` (Redis patterns: `copilot:session:{company_id}:...`)
* **File security**:
  * Extension allowlist (`.pdf,.png,.jpg,.docx,.xlsx,.csv,.txt,.zip`)
  * Extension blocklist (`.exe,.bat,.ps1,.sh,.msi,.com,.scr,.vbs,.jar,.reg,.dll`)
  * 20MB max upload size
  * SHA-256 deduplication
  * Path traversal prevention: `os.path.realpath()` + `normpath` with safe-base directory check
  * Filename sanitization
* **Security headers**: HSTS (31536000s, includeSubDomains), X-Content-Type-Options: nosniff, X-Frame-Options: DENY, CSP (self + API domain), Permissions-Policy restrictions
* **Rate limiting**: Redis-backed (ZREMRANGEBYSCORE/ ZCARD/ ZADD) with in-memory fallback
* **SQL injection prevention**: Column allowlists (`COLUMNS`), parameterized queries
* **Mass assignment prevention**: `extra="forbid"` on all Pydantic schemas
* **Generic error handler**: No stack traces in production

### Root Cause
Security implementation is thorough with defense-in-depth. Minor concern: `OPERION_API_KEY` middleware warns it's disabled if env var not set — acceptable for development; must be set in production.

### Smallest Safe Fix
Ensure production environment variables are set before launch:
- `OPERION_JWT_SECRET_KEY` (≥ 32 bytes)
- `OPERION_API_KEY`
- `OPERION_ENCRYPTION_KEY`
- `OPERION_RATE_LIMIT`
- Production CORS origin allowlist

---

# TIER G — Performance & Operational Readiness

## Workflow: Performance Under Load (Dispatch, Invoice, OCR, Notifications, ARGO)

### Tier
G

### Result
READY AFTER FIX

### Existence
PASS

### Functional Integrity
PASS

### Cross-System Integrity
N/A

### Offline Integrity
N/A

### AI Safety Integrity
N/A

### Production Integrity
RISK

### Severity
S2

### Evidence
* **Load test infrastructure**: `tests/loadtest/` directory exists with Locust-based tests
* **Test conftest**: `tests/loadtest/conftest.py` configured
* **CI/CD load test workflow**: `.github/workflows/loadtest.yml` configured
* **Celery task queue**: `backend/celery_app/` with Redis broker for async tasks (OCR, document processing, TransEU sync)
* **Rate limiting**: Configurable via `OPERION_RATE_LIMIT` env var with Redis backend (in-memory fallback per-worker)
* **Database connection**: SQLAlchemy with connection pooling, fallback to SQLite for development
* **Cannot run load tests** without PostgreSQL and Redis (Docker infrastructure required)

### Root Cause
Load test infrastructure exists but requires Docker (PostgreSQL + Redis) to execute. On a Windows development machine without Docker running, the load tests cannot execute.

### Smallest Safe Fix
Before launch, run the existing load test suite:
```bash
docker compose -f docker-compose.test.yml up -d
locust -f tests/loadtest/ --headless -u 100 -r 10 --run-time 5m
```
Collect API latency, queue depth, memory usage, error rate, OCR throughput, and route calculation throughput. Classify as PASS / DEGRADED / FAIL.

---

# SUMMARY OF FIXES APPLIED DURING AUDIT

| # | Issue | File | Severity | Status |
|---|-------|------|----------|--------|
| 1 | `trip.delete` confirmation phrase not validated against trip_id | `backend/copilot/tools/delete_tools.py:66-67` | S0 | ✅ FIXED |
| 2 | `vehicle.delete` confirmation phrase not validated | `backend/copilot/tools/delete_tools.py:153-154` | S0 | ✅ FIXED |
| 3 | `driver.remove` confirmation phrase not validated | `backend/copilot/tools/delete_tools.py:243-244` | S0 | ✅ FIXED |
| 4 | `client.delete` confirmation phrase not validated | `backend/copilot/tools/delete_tools.py:330-331` | S0 | ✅ FIXED |
| 5 | `invoice.delete` confirmation phrase not validated | `backend/copilot/tools/delete_tools.py:420-421` | S0 | ✅ FIXED |
| 6 | `route.delete` confirmation phrase not validated | `backend/copilot/tools/delete_tools.py:511-512` | S0 | ✅ FIXED |
| 7 | `dispatch.cancel` missing `confirmation_phrase` field entirely | `backend/copilot/tools/dispatch_tools.py:70-74` | S0 | ✅ FIXED |
| 8 | `cost_engine.py` division by zero on `distance_km <= 0` | `services/cost_engine.py:104,110` | S1 | ✅ FIXED |
| 9 | VAT discrepancy > 0.05 logged warning but proceeded | `services/invoicing/generator.py:388-393` | S0 | ✅ FIXED |

---

# REMAINING ISSUES (NOT FIXED)

| # | Issue | File | Severity | Requires |
|---|-------|------|----------|----------|
| 1 | All financial calculations use `float` not `Decimal` | 15+ files across `services/` | S0 | Architectural refactor (3-5 days) |
| 2 | Backend sync endpoint is stub | `backend/api/v1/mobile.py:757` | S0 | Full sync implementation (4-6 weeks) |
| 3 | Mobile local DB uses JSON files (TODO: Isar) | `mobile_app/lib/core/storage/local_db.dart` | S1 | Replace with Isar (2-3 days) |
| 4 | Prompt injection sanitizer not implemented | Phase 0 | S1 | Implement before LLM integration |
| 5 | Sum of individually-rounded line items | `services/invoicing/service.py:108-110` | S1 | Change to sum-then-round (few hours) |
| 6 | Plan store in-memory (not distributed) | `backend/api/v1/copilot_router.py:28` | S2 | Move to Redis (1-2 days) |
| 7 | Audit logging is stub | `backend/copilot/audit.py` | S2 | Wire to `copilot_audit_log` table (1-2 days) |

---

# RECOMMENDED LAUNCH CHECKLIST

## Critical (Must fix before launch)
- [ ] Replace `float` with `Decimal` for all monetary calculations (S0)
- [ ] Complete backend sync implementation (S0)
- [ ] Set production JWT secret key ≥ 32 bytes
- [ ] Set `OPERION_API_KEY` in production environment
- [ ] Run load tests with PostgreSQL + Redis

## High Priority (Fix before launch if possible)
- [ ] Change VAT line-item summation to sum-then-round
- [ ] Replace mobile JSON file storage with Isar
- [ ] Implement prompt injection sanitizer before LLM routing
- [ ] Configure production CORS origin allowlist

## Medium Priority (Fix within first month post-launch)
- [ ] Move copilot plan store to Redis
- [ ] Wire copilot audit logging to database table
- [ ] Add rate limit per-user (currently per-IP only)
- [ ] Increase test HMAC key to ≥ 32 bytes (test env)
- [ ] Run accessibility audit (Playwright tests exist)

---

*Report generated by Operion Launch Integrity Audit System*
*Evidence-based. Optimism is not evidence.*
