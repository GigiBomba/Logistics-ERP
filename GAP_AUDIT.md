# OPERION ECOSYSTEM — COMPREHENSIVE TEST GAP AUDIT

> **Date:** 2026-07-18
> **Scope:** Desktop App · Website · Backend/Mobile API  
> **Methodologies:** Unit · Integration · E2E · Load · Stress · Chaos · Security · Concurrency · Mutation
> **Weighted ecosystem coverage estimate: ~65%**

---

## TABLE OF CONTENTS

1. [Backend API & Core](#1-backend-api--core)
2. [Backend Services](#2-backend-services)
3. [Domain Models & Repositories](#3-domain-models--repositories)
4. [Desktop App (Python Qt)](#4-desktop-app-python-qt)
5. [Desktop App (React Frontend)](#5-desktop-app-react-frontend)
6. [Website (React)](#6-website-react)
7. [AI Copilot Module](#7-ai-copilot-module)
8. [Mobile API](#8-mobile-api)
9. [Database, Migrations, Utils, Scripts](#9-database-migrations-utils-scripts)
10. [Test Infrastructure & CI/CD](#10-test-infrastructure--cicd)
11. [Top 10 Most Critical Gaps](#11-top-10-most-critical-gaps)

---

## 1. BACKEND API & CORE

### API Endpoints (`backend/api/v1/`)

| Metric | Value |
|--------|-------|
| Route files | 35 |
| Total endpoints | ~217 |
| Files with tests | 32 (91%) |
| Files with **ZERO tests** | 3 (9%) |

#### 🔴 Files with NO test coverage

| File | Endpoints | Risk |
|------|-----------|------|
| `copilot_router.py` | 10 endpoints | **CRITICAL** — chat, voice, plan lifecycle, conversations, insights, WebSocket |
| `freight_exchange.py` | 14 endpoints | **CRITICAL** — provider connect/disconnect, search, import, evaluate |
| `waitlist.py` | 1 endpoint | **LOW** — public waitlist signup |

### Middleware (`backend/middleware/`)

| Middleware | Coverage | Notes |
|------------|----------|-------|
| AuthMiddleware | ✅ Full | Timing-safe comparison, path whitelist, production guard |
| RateLimitMiddleware | ✅ Full | Threshold, window expiry, Redis fallback, concurrency |
| LoggingMiddleware | ✅ Full | Method/path/status/duration, sensitive header exclusion |
| CorrelationIdMiddleware | ✅ Full | ID generation, propagation, uniqueness |
| IdempotencyMiddleware | ✅ Full | Replay, miss, GET bypass (but Redis backend not tested) |
| **SecurityHeadersMiddleware** | **❌ None** | No unit tests — CSP, HSTS, X-Frame-Options behavior unverified |
| **WebhookBodyMiddleware** | **❌ None** | Entirely untested — HMAC body preservation is security-critical |
| **PrometheusMiddleware** | **❌ None** | No middleware dispatch tests, SLO failure path untested |

### Core (`backend/`)

| File | Coverage | Notes |
|------|----------|-------|
| `main.py` / `backend/main.py` | ⚠️ Partial | No lifespan/startup/shutdown tests; CORS only wildcard-checked |
| `config.py` / `backend/config.py` | ⚠️ Partial | Some env override tests; missing production-mode validation |
| `db.py` | ⚠️ Indirect | Re-exports DatabaseManager — tested via readiness |
| `security.py` | ✅ Good | Password hashing, JWT, bcrypt truncation, clock skew |
| `oauth2.py` | ✅ Excellent | Full OAuth2Service with scope filtering |
| `errors.py` | ✅ Excellent | ErrorCode enum, ProblemDetail, exception mapping |
| `cache.py` | ⚠️ Partial | Graceful degradation tested; **no TTL expiry tests, no RedisCache concurrency** |
| **`metrics.py`** | **❌ None** | PrometheusMetrics — only endpoint-format tested |
| **`backend/config.py` (root)** | **❌ None** | 90-line Config class with environment variable handling |

### Schemas (`backend/schemas/`)

| Schema File | Coverage | Notes |
|-------------|----------|-------|
| auth.py | **❌ None** | RefreshTokenRequest, ForgotPasswordRequest, ResetPasswordRequest — no constraint boundary tests |
| **mobile.py** | **❌ None** | **19 models, zero tests** |
| **waitlist.py** | **❌ None** | State machine constants (VALID_TRANSITIONS, FLEET_SIZE_VALUES) |
| **invoice.py** | **❌ None** | Field constraints (`gt=0`, `max_length`) never tested |
| **receipt.py** | **❌ None** | No validation tests |
| **settings.py** | **❌ None** | max_length constraints not tested |
| **cmr.py** | **❌ None** | Minimal but untested |
| admin.py | ✅ Yes | |
| driver.py | ✅ Yes | |
| fleet.py | ✅ Yes | |
| ocr.py | ✅ Yes | |
| payment_profile.py | ✅ Yes | |
| registration.py | ✅ Yes | |
| others | ⚠️ Partial | Field constraints, edge cases missing (e.g., `PaginatedResponse.from_items()` with `page_size=0`) |

---

## 2. BACKEND SERVICES

### Core Services (`services/`)

**59 files total. 7 have ZERO dedicated tests:**

| Service | Lines | Risk | Notes |
|---------|-------|------|-------|
| **`audit_service.py`** | ~80 | **HIGH** | Core audit logging — completely untested |
| **`cost_engine.py`** | ~120 | **HIGH** | Country factors, road class adjustments, fuel price fallback — all untested |
| **`constraint_engine.py`** | ~150 | **HIGH** | Truck height/weight/width/length, hazmat, axle load, GraphHopper params |
| **`route_persistence.py`** | ~100 | **HIGH** | Route record building, geometry compression, cost delegation |
| **`feature_flags.py`** | ~80 | **MEDIUM** | Scope evaluation (GLOBAL, PER_COMPANY, PER_USER, PERCENTAGE) |
| **`integration_health_service.py`** | ~70 | **MEDIUM** | Health check for all registered integrations |
| **`payment_profile_service.py`** | ~50 | **LOW** | Thin CRUD wrapper |

### Document & Invoicing Services

| Sub-service | Coverage | Gaps |
|-------------|----------|------|
| `document_automation/pipeline.py` | ✅ Good | `_sanitize_filename_part()` edge cases untested; `_rename_document_after_ocr()` only E2E |
| `document_automation/ocr_extractor.py` | ✅ Good | |
| `document_automation/image_processor.py` | ⚠️ Partial | `_detect_document_quad()` — two detection modes not tested |
| `document_automation/ai_fallback.py` | ⚠️ Partial | `ai_extract()` — main public API untested |
| **`document_automation/trip_matcher.py`** | **❌ None** | Only E2E coverage |
| **`document_automation/package_builder.py`** | **❌ None** | No dedicated tests |
| **`document_automation/ocr_validator.py`** | **❌ None** | No dedicated tests |
| **`document_automation/customer_detector.py`** | **❌ None** | No dedicated tests |
| `invoicing/generator.py` | ✅ Good | `SimpleDocTemplate` always mocked — real PDF not verified |
| **`invoicing/cmr_generator.py`** | **❌ None** | |
| **`invoicing/cmr_validator.py`** | **❌ None** | |
| **`invoicing/cmr_efti.py`** | **❌ None** | |
| **`invoicing/config_manager.py`** | **❌ None** | |
| **`invoicing/receipt_service.py`** | **❌ None** | |
| **`invoicing/service.py`** | **❌ Unit** | Only integration test coverage |
| `invoicing/proforma_service.py` | ⚠️ Partial | Typed CRUD not fully tested |
| `invoicing/receipt_generator.py` | ⚠️ Partial | `create()`, `generate_pdf()`, `finalize()` — permission checks, DB persistence missing |
| `automail/` | ⚠️ Partial | Actual SMTP sending paths never tested |
| **`currency/contract.py`** | **❌ Critical** | Conversion math, rounding, exchange rate edge cases — untested |

### Operations & Dispatch Services

| Component | Coverage | Gaps |
|-----------|----------|------|
| EventBus | ✅ Excellent | Stress test with >100 subscribers missing |
| AlertManager | ✅ Good | Max eviction policy, concurrent creation untested |
| Rules | ✅ Excellent | |
| TripStatusEngine | ✅ Very Good | |
| **AvailabilityChecker** | **❌ CRITICAL** | **Zero dedicated unit tests.** Insurance expiry, inspection expiry, maintenance overdue, license expiry, medical cert, tacho hours — all untested in isolation |
| DispatchService | ✅ Excellent | Concurrent assign operations missing |
| DunnerEngine | ✅ Good | Invoice re-check between fetch and send untested |
| OperationsEngine | ✅ Adequate | `start()` timer scheduling untested |

### Freight Exchange & Trans.eu

| Area | Coverage | Gaps |
|------|----------|------|
| Adapter mapping (Trans.eu) | ✅ Extensive | |
| **Adapter mapping (TIMOCOM)** | **❌ None** | No equivalent test file |
| Rate limiter | ✅ Full | |
| Circuit breaker | ✅ Full | Auth errors not counting — behavior not verified |
| Search engine | ✅ Full | |
| Webhook sync | ✅ Good | Ordering/consistency missing |
| HTTP client (Trans.eu) | ✅ Full | |
| **HTTP mock integration** | **❌ None** | Adapters never tested with mocked HTTP responses |
| **Data format skew tests** | **❌ None** | No version-skew or type-change detection |
| **Chaos tests for T.eu/TIMOCOM** | **❌ None** | No API failure, timeout, 503 simulations |
| **Health monitor** | **❌ None** | `run_all_health_checks()` — zero tests |
| OAuth full dance | ⚠️ Partial | Not end-to-end tested with mocked HTTP |

### Celery Tasks (`backend/celery_app/tasks/`)

| File | Coverage |
|------|----------|
| `document_tasks.py` | ✅ Partial |
| `insight_tasks.py` | ✅ Full |
| **`maintenance_tasks.py`** | **❌ None** |
| `ocr_tasks.py` | ✅ Partial |
| `retention_tasks.py` | ✅ Full |
| `trans_eu_tasks.py` | ✅ Full |

### Client Remote Services (`client/`)

**18 Python files in `client/`:**

| File | Coverage | Notes |
|------|----------|-------|
| `api_client.py` | ✅ Full | Includes mutation tests |
| `auth.py` | ✅ Full | |
| `auth_manager.py` | ✅ Full | |
| `cache.py` | ⚠️ Partial | |
| **`config.py`** | **❌ None** | ClientConfig singleton, API URL/SSL resolution |
| `remote_analytics.py` | ✅ Partial | |
| `remote_copilot.py` | ✅ Partial | |
| `remote_driver_service.py` | ✅ Partial | |
| `remote_feature_flags.py` | ✅ Full | |
| `remote_freight_exchange.py` | ✅ Full | |
| `remote_invoice_service.py` | ✅ Partial | |
| `remote_maintenance.py` | ✅ Partial | |
| **`remote_ops_stub.py`** | **❌ None** | EventBus remote substitute |
| **`remote_preferences.py`** | **❌ None** | Full preferences API, 160 lines |
| `remote_route_history.py` | ✅ Partial | |
| `remote_services.py` | ✅ Full | |
| `remote_tacho.py` | ✅ Partial | |
| **`network/network_worker.py`** | **❌ None** | 193 lines, PySide6 QThread |

---

## 3. DOMAIN MODELS & REPOSITORIES

### Domain Models (`models/`)

**21 model files. 19 have test coverage. 2 have ZERO:**

| Model File | Coverage | Notes |
|------------|----------|-------|
| **`freight_exchange_models.py`** | **❌ None** | 14 classes (LoadSearchFilters, TruckMatchScore, LoadEvaluation, TransEuWebhookEvent…) — complex business logic, 0 unit tests |
| **`tacho_models.py`** | **❌ None** | 7 classes — `path_must_not_be_empty` validator, `DriverHoursAnalysis.is_compliant`, `FleetTachoSummary` — all untested |
| `invoice_models.py` | ⚠️ Medium | Cross-field date validator only in mutation tests |
| `route_models.py` | ⚠️ Medium | `RouteStop` type validation, lat/lon range untested |
| All others (17) | ✅ High | Well-covered |

### Repositories (`repositories/` + `backend/repositories/`)

**31 repository files. 27 have tests. 1 has ZERO:**

| Repository | Coverage | Notes |
|------------|----------|-------|
| **`user_repository.py`** | **❌ None** | `list_users()`, `create_user()`, `deactivate_user()` — zero coverage |
| **`analytics_repository.py`** | **~20%** | 30+ complex SQL methods untested (dashboard charts, CTE queries, financial analytics, driver comparison) |
| `document_repository.py` | ⚠️ 70% | `advanced_search()` with 8 conditional filters — not tested |
| `fleet_repository.py` | ⚠️ 60% | `count_overdue_schedules()` complex calculation — not tested |
| All others | ✅ Good | |
| **Concurrent writes** | **❌ None** | No race condition tests for any repository |
| **PostgreSQL fixtures** | **❌ None** | All repos tested on SQLite InMemoryDB only |

---

## 4. DESKTOP APP (PYTHON QT)

### Views (`ui/views/` — 69 files)

**Previously reported gaps corrected by deep audit.** Most views DO have tests. Real untested views:

| File | Lines | Risk |
|------|-------|------|
| **`bulk_payments_view.py`** | 952 | **HIGH** — Payment batch management, CSV export |
| **`copilot_view.py`** | 71 | **MEDIUM** — AI Co-Pilot chat panel wrapper |
| **`dashboard.py`** | 1003 | **HIGH** — KPI dashboard |
| `freight_exchange/connect_view.py` | ? | **HIGH** |
| `freight_exchange/load_detail_view.py` | ? | **HIGH** |
| `freight_exchange/search_view.py` | 721 | **HIGH** |

### Dialogs (`ui/dialogs/` — 9 files)

| Dialog | Coverage | Risk |
|--------|----------|------|
| **`freight_provider_settings.py`** | **❌ None** | **HIGH** — 446 lines, provider connection settings |
| **`paired_assignment_dialog.py`** | **❌ None** | **MEDIUM** — 404 lines, no assignment/suggestion tests |
| **`share_route_dialog.py`** | **❌ None** | **MEDIUM** — 335 lines |
| **`trip_search_dialog.py`** | **❌ None** | **MEDIUM** — 271 lines |
| `dispatch_detail_panel.py` | ✅ Good | |
| `edit_window.py` | ✅ Good | |
| `login_dialog.py` | ✅ Basic | |
| `maintenance_view.py` | ✅ Good | |
| `trip_picker_dialog.py` | ⚠️ Indirect | Only imported in OCR tests |

### Widgets (`ui/widgets/` — 28 files)

| Widget | Coverage | Notes |
|--------|----------|-------|
| All widgets have at least basic tests | ✅ | Most have adequate tests |
| `kanban_column.py` | ⚠️ Indirect | Drag-drop signals not tested |
| `trip_card.py` | ✅ Good | |
| `sidebar.py` | ✅ Adequate | |

### Copilot UI (`ui/copilot/` — 24 files)

**Critical gap concentration — 7 widgets with ZERO tests:**

| Copilot File | Lines | Risk |
|--------------|-------|------|
| **`widgets/timeline_widget.py`** | 941 | **CRITICAL** — Execution timeline, step cards, reasoning tree |
| **`widgets/guided_overlay_widget.py`** | 738 | **CRITICAL** — Tour overlay, step navigation, paintEvent |
| **`widgets/copilot_panel.py`** | 456 | **HIGH** — Main chat panel |
| **`widgets/insight_queue.py`** | 445 | **HIGH** — Insight review queue |
| **`widgets/chat_input.py`** | 230 | **MEDIUM** — Text input, mic button, send logic |
| **`widgets/chat_bubble.py`** | 126 | **MEDIUM** |
| **`widgets/confirmation_modal.py`** | 607 | **HIGH** |
| **`widgets/conversation_display.py`** | 135 | **MEDIUM** |
| **`widgets/thinking_indicator.py`** | 100 | **LOW** |
| `audio_recorder.py` | 130 | **❌ None** |
| `tts_player.py` | 110 | **❌ None** |
| Controllers (4) | ✅ Good | Models, element_registry, tour_scripts OK |

### Map (`ui/map/` — 4 files)

| File | Coverage |
|------|----------|
| `map_widget.py` | ✅ Good |
| `route_renderer.py` | ✅ Basic |
| `map_helpers.py` | ✅ Covered |

---

## 5. DESKTOP APP (REACT FRONTEND)

### `ui/src/` — Overall: ~19% coverage

| Category | Total | Tested | Untested | Coverage |
|----------|-------|--------|----------|----------|
| UI Components | 5 | 1 | 4 | 20% |
| Shared Components | 7 | 0 | 7 | **0%** |
| Auth Pages | 5 | 2 | 3 | 40% |
| Public Pages | 13 | 0 | 13 | **0%** |
| Contexts | 2 | 2 | 0 | 100% |
| Lib | 2 | 2 | 0 | 100% |
| Config | 2 | 0 | 2 | **0%** |
| App/Entry | 2 | 0 | 2 | **0%** |
| **TOTAL** | **~41** | **8** | **33** | **~19%** |

#### 🔴 Files with no tests

| File | Category | Notes |
|------|----------|-------|
| `badge.tsx` | UI Component | 6 variants, forwardRef |
| `card.tsx` | UI Component | 6 sub-components |
| `input.tsx` | UI Component | Input, Label, Textarea |
| `loading-spinner.tsx` | UI Component | All sizes |
| `forgot-password.tsx` | Auth Page | Email enumeration protection |
| `reset-password.tsx` | Auth Page | Cross-field `z.refine()` validation |
| `verify-email.tsx` | Auth Page | Static page |
| `testimonial-card.tsx` | Shared | |
| `section-wrapper.tsx` | Shared | |
| `pricing-card.tsx` | Shared | Interactive (hover, click) |
| `page-header.tsx` | Shared | SEO/metadata |
| `feature-card.tsx` | Shared | |
| `empty-state.tsx` | Shared | |
| `cta-section.tsx` | Shared | |
| (All 13 public pages) | Pages | |
| `config/` | Config | |

#### ⚠️ Missing test categories

| Feature | Status |
|---------|--------|
| API error handling (network failure, timeout) | ❌ Not tested |
| `api.post` / `api.postForm` | ❌ Not tested |
| Route protection / auth guards | ❌ Not tested |
| Snapshot / visual regression | ❌ None |
| Theme switching (light mode explicitly) | ❌ Not tested |

---

## 6. WEBSITE (REACT)

### `website/src/` — Overall: ~71% coverage (but uneven)

| Category | Total | Tested | Untested | Coverage |
|----------|-------|--------|----------|----------|
| UI Components | 17 | 17 | 0 | **100%** |
| Auth Pages | 5 | 5 | 0 | **100%** |
| API/Config/Lib/Types | 5 | 5 | 0 | **100%** |
| Contexts | 2 | 1 | 1 | **50%** |
| Layout | 1 | 1 | 0 | **100%** |
| Shared Components | 32 | 26 | 6 | **81%** |
| Dashboard Pages | 13 | 7 | 6 | **54%** |
| Public Pages | 55 | 25 | 30 | **45%** |
| Admin Pages | 5 | 0 | 5 | **0%** |
| Docs Pages | 3 | 0 (v2 only) | 3 | **0%** |
| Services | 6 | 1 | 5 | **17%** |
| i18n | 2 | 0 | 2 | **0%** |
| SEO Components | 2 | 0 | 2 | **0%** |
| **TOTAL** | **~150** | **~90** | **~60** | **~60%** |

#### 🔴 Files with ZERO test coverage

**Services (5):**
- `services/analytics.ts` — Page views, events, CTA clicks, downloads
- `services/jwt.ts` — JWT verification
- `services/seo.tsx` — `getPageTitle`, `generateMetaTags`, `StructuredData`
- `services/seo-improvements.tsx` — SEO components
- `services/accessibility.tsx` — `SkipToContent`, `useReducedMotion`

**i18n (2):**
- `i18n/locale-context.tsx` — LocaleProvider, useLocale hook
- `i18n/types.ts`

**Contexts (1):**
- `contexts/auth-provider.tsx` — AuthContext (only partially via integration)

**Shared Components (6):**
- `comparison-table.tsx`, `table-of-contents.tsx`, `timeline.tsx`
- `testimonial-card.tsx`, `stat-card.tsx`

**Public Pages (30 — including 19 with absolutely no tests):**
- `home.tsx`, `features.tsx`, `pricing.tsx`, `download.tsx`, `mission.tsx`
- `contact.tsx`, `privacy.tsx`, `terms.tsx`, `not-found.tsx`, `error-500.tsx`
- `error-maintenance.tsx`, `error-offline.tsx`, `api-playground.tsx`
- `waitlist.tsx`, `product-tour.tsx`, `roi-calculator.tsx`, `route-demo.tsx`
- `integrations-explorer.tsx`, `trust-center.tsx`
- `blog-author.tsx`, `blog-category.tsx`
- All 8 industry pages (agriculture, construction, fleet, freight, manufacturing, owner-ops, transport)

**Dashboard Pages (6):**
- `billing.tsx`, `downloads.tsx`, `documentation.tsx`
- `licenses.tsx`, `onboarding.tsx`, `organizations.tsx`, `organization-settings.tsx`

**Admin Pages (5):**
- `blog-editor.tsx` (slug variant), `admin-waitlist.tsx`
- `overview-tab.tsx`, `entries-tab.tsx`, `campaign-tab.tsx`

**Docs Pages (3 — only v2 versions tested):**
- `docs-layout.tsx`, `docs-category.tsx`, `docs-article.tsx`

### Website E2E (Playwright)

| Aspect | Status |
|--------|--------|
| Total spec files | 16 |
| Authentication | ✅ Covered |
| Navigation | ✅ Covered |
| Accessibility | ✅ Covered |
| Responsive | ✅ Covered |
| Dark mode | ✅ Covered |
| SEO validation | ✅ Covered |
| Chaos (offline, API failures, rate limiting) | ✅ Covered |
| **Visual regression** | ❌ None (no Percy/Chromatic) |
| **Cross-browser** | ❌ Chromium only (no Firefox/Safari) |
| **Mobile emulation** | ❌ No iOS Safari |
| **Network throttling** | ❌ No 3G/LTE simulation |

### Website Stress (k6)

| Scenario | Status |
|----------|--------|
| Static pages (24) | ✅ |
| API endpoints (8) | ✅ |
| Sustained (50 VUs / 5 min) | ✅ |
| Spike (200 VUs) | ✅ |
| **Smoke test** | ❌ Missing |
| **Soak test** | ❌ Missing |
| **k6 chaos** | ❌ Missing (chaos only in Playwright) |

---

## 7. AI COPILOT MODULE

### Core Pipeline

| Component | Coverage | Notes |
|-----------|----------|-------|
| schemas.py | ✅ Full | Round-trip for all 11 models |
| executor.py | ✅ Full | State machine, guardrails, undo window |
| planner.py | ✅ Full | Intent extraction (14+ patterns) |
| reasoning.py | ✅ Good | |
| confidence.py | ✅ Full | |
| circuit_breaker.py | ✅ Full | |
| context.py | ✅ Good | |
| telemetry.py | ✅ Good | |
| human_handoff.py | ✅ Full | |
| tier_gate.py | ❌ None | `check_quota` is stub returning True |
| world_model.py | ✅ Phase 4 stub | Acceptable for stub |
| audit.py | ✅ Phase 0 stub | |
| i18n_scope.py | ❌ None | Trivial re-export |

### LLM Layer

| Component | Coverage | Notes |
|-----------|----------|-------|
| `llm/base.py` | ⚠️ Partial | Interface tested |
| `llm/registry.py` | ⚠️ Partial | |
| `llm/routing.py` | ⚠️ Partial | Construction only, never used in routing |
| **`llm/providers/google_provider.py`** | **❌ Shallow** | Only 5 unit tests. Missing: `generate()` with mocked response, streaming, token counting, error propagation |

### Copilot Router (`backend/api/v1/copilot_router.py`)

**🔴 CRITICAL — 10 endpoints, only 6 E2E smoke tests:**

| Endpoint | Direct Tests | Status |
|----------|-------------|--------|
| `POST /copilot/chat` | Only auth check | ❌ Incomplete |
| `POST /copilot/voice` | **Zero** | **❌ None** |
| `GET /copilot/plans/{id}` | Only 404 | **❌ Incomplete** |
| `POST /copilot/plans/{id}/cancel` | Only 404 | **❌ Incomplete** |
| `POST /copilot/plans/{id}/confirm` | Only 404 | **❌ Incomplete** |
| `POST /copilot/plans/{id}/undo` | **Zero** | **❌ None** |
| `GET /copilot/conversations` | **Zero** | **❌ None** |
| `GET /copilot/conversations/{id}` | **Zero** | **❌ None** |
| `GET /copilot/insights` | **Zero** | **❌ None** |
| WebSocket `/ws/{id}` | Token-missing only | **❌ Incomplete** |
| `_push_plan_update` | **Zero** | **❌ None** |
| `_validate_plan_ownership` | **Zero** | **❌ None** |

### Copilot Tools (`backend/copilot/tools/`)

**🔴 CRITICAL — 26 of 32 tool files have ZERO test coverage:**

| Tools | Coverage | Status |
|-------|----------|--------|
| `base.py`, `registry.py` | ✅ Full | |
| `freight_tools.py` | ✅ Full | |
| `help_tools.py` | ⚠️ Partial | |
| `proforma_tools.py`, `receipt_tools.py` | ⚠️ Partial | |
| **24 other tool files** | **❌ None** | Including: automail, client, cmr, currency, delete, dispatch, document, driver, export, invoice, maintenance, ocr, payment, route, route_sharing, tacho, tracking, trip, trip_crud, undo, vehicle, vehicle_crud, analytics_tools, client_crud |

### Voice

| Component | Coverage | Notes |
|-----------|----------|-------|
| `language_tiers.py` | ✅ Full | |
| `schemas.py` | ⚠️ Partial | |
| `tts.py` | ⚠️ ABC only | `synthesize()` never called |
| `whisper_stt.py` | ⚠️ Mock-based | |
| `piper_tts.py` | ⚠️ Mock-based | |

### Security

| Area | Status |
|------|--------|
| **Prompt injection** | **❌ Placeholder** — both tests are `assert True` |
| Plan ownership isolation | **❌ Not tested** |
| Cross-company data isolation | **❌ Not tested** |
| JWT on WebSocket | **❌ Not tested** |

---

## 8. MOBILE API

### Endpoints (24 total)

| Metric | Value |
|--------|-------|
| Endpoints with tests | 20 (83%) |
| Endpoints with **no tests** | 3 |

#### 🔴 Endpoints with NO tests

| Endpoint | Issue |
|----------|-------|
| **`POST /mobile/driver/expenses`** | **Known bug** — `sqlite3.IntegrityError` on `receipt_number` NOT NULL. Never fixed. |
| `GET /mobile/devices` | Never tested |
| `DELETE /mobile/devices/{device_id}` | Never tested |

#### Known Bugs Documented in Tests

| Bug | Location | Impact |
|-----|----------|--------|
| `receipt_number` NOT NULL → IntegrityError | test_mobile_endpoints.py:417-422 | POST /driver/expenses fails |
| `dispatcher_fleet` — `AttributeError` on `sqlite3.Row` | test_mobile_endpoints.py:556-559 | Fleet endpoint returns 500 |
| `list_messages` uses wrong column name | test_mobile_endpoints.py:444-448 | Message list may fail |
| `approval_id` int vs TEXT UUID mismatch | test_mobile_data_flow.py:587-592 | Type mismatch |

### Mobile Schemas

| Schema count | Coverage | Status |
|-------------|----------|--------|
| **19 models** | **0 tests** | **❌ None** — No ValidationError tests for any field constraints |

### Skipped / Stub Tests

| File | Lines Skipped | Reason |
|------|--------------|--------|
| `test_mobile_mutation.py` | 16 tests | `@pytest.mark.skip` |
| `test_mobile_additional.py` | **20 empty stubs** | ALL `@pytest.mark.skip` |
| `test_mobile_data_flow.py` | 2 empty stubs | `test_create_expense_then_verify_in_list`, `test_send_message_then_verify_in_list` |

### Missing Mobile-Specific Scenarios

| Scenario | Status |
|----------|--------|
| Offline mode / request queuing | ❌ None |
| Sync conflicts / cursor conflicts | ❌ None |
| Limited bandwidth / response size | ❌ None |
| Push notification delivery (FCM/APNs) | ❌ None |
| Delta sync edge cases | ❌ None |
| Mobile-specific performance tests | ❌ None |

---

## 9. DATABASE, MIGRATIONS, UTILS, SCRIPTS

### Database & Migrations

| Area | Coverage | Status |
|------|----------|--------|
| Alembic migrations (11 total) | **~15%** | **❌ 9 of 11 migrations have NO tests** |
| Migration downgrades | **0%** | **❌ No downgrade tests for ANY migration** |
| `connection_pool.py` | **❌ None** | PostgresConnectionPool thread-safety |
| `uuid_helpers.py` | **❌ None** | |

### Utils (16 modules)

| Module | Coverage | Status |
|--------|----------|--------|
| `formatting.py` | ✅ Full | All functions |
| `formatters.py` | ✅ Full | |
| `chart_export.py` | ✅ Extensive | |
| `editor_toolkit.py` | ✅ Extensive | |
| `number_to_words.py` | ✅ All | All edge cases |
| `helpers.py` | ✅ Basic | |
| `labels.py` | ✅ Full | |
| **`validation.py`** | **⚠️ Partial** | `validate_iban`, `validate_bic`, `validate_bank_account` — **all financial, all untested** |
| **`dates.py`** | **⚠️ Partial** | `parse_date_safe`, `is_expired` — untested |
| **`perf_log.py`** | **⚠️ Minimal** | `perf_timer()` actual timing untested |
| `logger.py` | ✅ Basic | |
| `observability.py` | ✅ Some | |
| `resource_path.py` | ✅ Partial | |
| `webengine_flags.py` | ⚠️ Indirect | |

### Scripts (48 files)

| Coverage | Status |
|----------|--------|
| **0%** | **❌ Zero test coverage for ANY script** |

**Critical untested scripts:**
- `validate_migration.py` — Migration validation
- `verify_client_isolation.py` — Security-critical tenant isolation
- `backup.sh`, `restore_data_from_backup.py` — Disaster recovery
- `build_client.py` — Build process
- `ci_copilot_gates.py` — CI gating
- All `backfill_*.py` scripts
- `gen_certs.sh` — Certificate generation

---

## 10. TEST INFRASTRUCTURE & CI/CD

### What Exists

| Item | Details |
|------|---------|
| Pytest | 400+ tests, 11 markers, InMemoryDB fixtures |
| Vitest (website) | Good config, jsdom, setup files |
| Vitest (desktop UI) | Config but no coverage reporter |
| Playwright E2E | 17 specs, `fullyParallel`, Chromium |
| Locust + k6 | Load testing for backend + website |
| Security tests | 34 files — authN/Z, SQLi, XSS, JWT fuzzing |
| Chaos tests | 19 files — DB, Redis, external APIs, network, file system |
| Concurrency tests | 8 files — race conditions, thread safety |
| Mutation tests | 19 Python + Stryker JS |
| GitHub workflows | loadtest, security, security-check, npm-audit |

### What's Missing

| Category | Missing |
|----------|---------|
| **Coverage thresholds** | No `fail_under`, no Codecov/Coveralls integration |
| **Test parallelism** | No pytest-xdist, no CI sharding |
| **Playwright in CI** | E2E tests never run in CI |
| **Python unit CI** | No dedicated pytest CI workflow |
| **Multi-OS testing** | Ubuntu only (no Windows/macOS) |
| **Multi-Python CI** | Only security-check uses 3.9/3.10/3.11 |
| **PostgreSQL test fixtures** | InMemoryDB SQLite only |
| **Visual regression** | No Percy/Chromatic/screenshot-diff |
| **Cross-browser E2E** | Chromium only (no Firefox/Safari) |
| **Mobile E2E** | No Appium/Calabash |
| **Test containers** | No ephemeral Docker test environment |
| **Test data factories** | No Factory Boy equivalent |
| **Security: OAuth2/OIDC** | Not tested |
| **Security: SSRF/XXE** | Not tested |
| **Concurrency: deadlocks** | Not tested |
| **Mutation: auth/security** | Auth layer uncovered |
| **Mutation: repositories** | Repository layer uncovered |

### Test Organization

```
tests/                          # Python (pytest)
├── chaos/          (19 files)  # Resilience/chaos
├── concurrency/    (8 files)   # Race conditions
├── copilot/        (55+ files) # AI Copilot
├── e2e/            (19 files)  # Desktop app workflows
├── freight_exchange/ (24 files)# Trans.eu integration
├── integration/    (5 files)   # Workflow integration
├── loadtest/       (13 files+) # Locust + scenarios
├── migrations/     (1 file)    # Alembic migrations
├── mutation/       (19 files)  # Mutation testing
├── readiness/      (10 files)  # Deployment validation
├── security/       (34 files)  # Security tests
├── stress/         (12 files)  # Stress tests
├── test_api/       (65+ files) # API endpoint tests

website/
├── src/__tests__/unit/        (15 files)
├── src/__tests__/integration/ (54 files)
├── src/__tests__/mutation/    (Stryker config)
├── e2e/                       (16 Playwright specs)

ui/src/
├── __tests__/     (8 files)   # Vitest
```

---

## 11. TOP 10 MOST CRITICAL GAPS

### 🔴 Gap #1: Copilot Router — 10 endpoints with near-zero coverage
- Voice, chat, plan lifecycle, conversations, insights, WebSocket all lack direct tests
- Plan ownership isolation between companies untested
- `_push_plan_update`, `_validate_plan_ownership` — entirely untested
- Prompt injection tests are `assert True` placeholders

### 🔴 Gap #2: Freight Exchange Router — 14 endpoints untested
- Provider connect/disconnect, search, load import, Trans.eu OAuth flow — all untested
- No chaos tests for Trans.eu/TIMOCOM API failures
- No HTTP mock integration tests for adapter methods
- TIMOCOM adapter has no equivalent unit test file

### 🔴 Gap #3: Copilot Tools — 26 of 32 files with ZERO tests
- Only base, registry, freight, help, proforma, receipt tools have any tests
- Dispatch, document, invoice, route, trip, client, vehicle tools — all untested

### 🔴 Gap #4: AvailabilityChecker — Zero dedicated tests
- Truck/driver insurance expiry, inspection, maintenance, license, medical, tacho hours checks — all untested in isolation
- Critical component in dispatch pipeline

### 🔴 Gap #5: Database Migrations — 9 of 11 Alembic migrations untested
- No downgrade tests for any migration (rollback safety unknown)
- `connection_pool.py`, `uuid_helpers.py` — untested

### 🔴 Gap #6: Desktop Copilot Qt Widgets — 9 files, ~3,700 lines, ZERO tests
- `timeline_widget.py` (941L), `guided_overlay_widget.py` (738L), `confirmation_modal.py` (607L), `copilot_panel.py` (456L), `insight_queue.py` (445L), `chat_input.py` (230L), `chat_bubble.py` (126L), `conversation_display.py` (135L), `thinking_indicator.py` (100L)
- `audio_recorder.py`, `tts_player.py` also untested

### 🔴 Gap #7: Desktop App React Frontend — 19% overall coverage
- 4 of 5 UI components untested; all 7 shared components untested
- Forgot/reset/verify password pages untested
- All public pages untested
- No route protection/auth guard tests
- API error handling (network failure, timeout) untested

### 🟠 Gap #8: Client Remote Services — 4 files with ZERO tests
- `client/config.py`, `client/remote_ops_stub.py`, `client/remote_preferences.py`, `client/network/network_worker.py`

### 🟠 Gap #9: Mobile API — Known bugs, 20 stub tests, 19 untested schemas
- POST /driver/expenses broken with known `IntegrityError`
- 20 stub tests all marked `@pytest.mark.skip`
- 0 schema validation tests for all 19 mobile schemas
- No offline/sync/bandwidth scenario tests

### 🟠 Gap #10: CI/CD — No coverage enforcement, no Playwright CI, no parallelism
- No `fail_under` threshold, no Codecov
- Playwright E2E tests never run in CI
- Python unit tests have no dedicated CI workflow
- Ubuntu-only (no Windows/macOS)
- No test parallelism or sharding
- No PostgreSQL test fixtures (InMemoryDB SQLite only)

---

## SUMMARY BY ECOSYSTEM COMPONENT

| Component | Estimated Coverage | Critical Remaining Gaps |
|-----------|------------------|------------------------|
| **Backend API** | ~90% | 3 untested route files (35 endpoints), 2 untested middleware |
| **Backend Services** | ~80% | 7 untested core services, AvailabilityChecker, Freight chaos |
| **Domain Models** | ~90% | 2 untested model modules (freight_exchange, tacho) |
| **Repositories** | ~85% | user_repo untested, analytics_repo 20% coverage |
| **Desktop App (Qt)** | ~85% | 19 untested files including Copilot widgets, freight exchange views, 4 dialogs |
| **Desktop App (React)** | ~19% | 33 of 41 files untested — worst coverage in ecosystem |
| **Website (React)** | ~60% | 50+ untested files — services, i18n, admin, industry pages |
| **AI Copilot** | ~60% | Router critical gap, 26 untested tool files, shallow GoogleProvider |
| **Mobile API** | ~70% | Known bugs, 20 stub tests, 0 schema tests, no mobile scenarios |
| **Database/Migrations** | ~15% | 9/11 migrations untested, no rollback tests |
| **Utils** | ~50% | Financial validation (IBAN/BIC) untested |
| **Scripts** | **0%** | 48 scripts, 0 tests |
| **CI/CD** | ~30% | No coverage, no Playwright CI, no parallelism |

> **Weighted ecosystem coverage estimate: ~65%**

### Strongest Areas
1. Security testing (34 files — authN/Z, SQLi, XSS, JWT fuzzing)
2. Chaos testing (19 files — DB, Redis, external APIs, network, file system, clock skew)
3. Dispatch & operations backend testing
4. Website UI component testing (17/17 = 100%)

### Weakest Areas
1. Desktop React frontend (~19%)
2. CI/CD infrastructure (~30%)
3. Database migrations (~15%)
4. Scripts (0%)
5. Copilot Router / Tools (large untested surfaces)
6. Mobile App (Flutter) (~30-40%)

---

## 12. MOBILE APP (FLUTTER)

**Location:** `C:\Users\Bonjo\source\repos\operion-mobile-app`
**Technology:** Flutter/Dart (cross-platform: iOS, Android, Windows, Web)

### Overview

| Metric | Value |
|--------|-------|
| Dart source files | **101** |
| Test files | **26** |
| Files with tests | ~35 (35%) |
| Files completely untested | **~66 (65%)** |
| Estimated overall coverage | **~30-40%** |
| Integration tests | **0** |
| E2E tests | **0** |
| Performance/benchmark tests | **0** |
| Screenshot/golden tests | **0** |

### Source Files by Layer

```
lib/
├── main.dart, app.dart                     (2 entry files)
├── core/
│   ├── auth/        (6 files)              # auth_providers, auth_service,
│   │                                        # biometric_service, mode_router,
│   │                                        # role_resolver, token_manager
│   ├── i18n/        (1 file)               # app_localizations
│   ├── network/     (11 files)             # api_client, auth_interceptor,
│   │                                        # message_bus, websocket_client,
│   │                                        # 7 endpoint files
│   ├── notifications/ (4 files)            # device_registration,
│   │                                        # notification_providers,
│   │                                        # notification_router, push_service
│   ├── storage/     (2 files)              # local_db, secure_token_store
│   ├── sync/        (5 files)              # action_queue, conflict_handler,
│   │                                        # connectivity_monitor,
│   │                                        # delta_sync_service, sync_providers
│   └── theme/       (4 files)              # app_colors, app_spacing,
│                                           # app_theme, app_typography
├── features/
│   ├── auth/        (2 files)
│   ├── copilot/     (8 files)              # integration, models, providers,
│   │                                        # screens, voice, widgets
│   ├── dispatcher/  (11 files)             # shell, alerts, analytics,
│   │                                        # drivers, fleet, home, jobs
│   ├── driver/      (22 files)             # shell, documents, expenses,
│   │                                        # home, messages, notifications,
│   │                                        # profile, transports, vehicle
│   └── settings/    (1 file)
├── l10n/            (3 files)              # app_en.arb, app_ro.arb
└── shared/
    ├── models/      (11 files)             # alert, document, driver, expense,
    │                                        # fleet_position, message,
    │                                        # sync_cursor, transport, user,
    │                                        # vehicle, vehicle_document
    └── widgets/     (9 files)              # app_button, app_card,
                                           # app_text_field, confirmation_dialog,
                                           # empty_state, offline_banner,
                                           # shimmer_loader, staleness_indicator,
                                           # status_badge
```

### Test Coverage by Module

| Module | Source | Test Files | Coverage | Status |
|--------|--------|------------|----------|--------|
| **Entry (main.dart, app.dart)** | 2 | 0 | 0% | ❌ |
| **Shared Models (all 11)** | 11 | 0 | **0%** | **🔴 CRITICAL** |
| **Copilot Feature** | 8 | 2 (endpoints + state) | ~20% | **🔴** |
| **Dispatcher Feature** | 11 | 1 (dispatcher_screens) | ~10% | **🔴** |
| **Driver Feature (partial)** | 22 | 8 widget tests | ~45% | ⚠️ |
| **Settings** | 1 | 0 | 0% | ❌ |
| **Sync System** | 5 | 2 (action_queue, sync_service) | ~20% | **🔴** |
| **Network Layer** | 11 | 4 (endpoints, interceptor, client) | ~65% | ⚠️ |
| **Auth Core** | 6 | 5 (service, biometric, token, role) | ~80% | ✅ |
| **Notifications** | 4 | 0 | 0% | ❌ |
| **Storage** | 2 | 1 (local_db) | ~25% | **🔴** |
| **Theme** | 4 | 0 | 0% | ❌ |
| **Shared Widgets** | 9 | 1 (shared_widgets) | ~80% | ✅ |
| **L10n/i18n** | 3 | 1 (localization) | ~85% | ✅ |
| **WebSocket** | 1 (websocket_client.dart) | 0 | **0%** | **🔴** |

### 🔴 Source Files with ZERO Test Coverage

**Core Layer (15 files):**
- `lib/main.dart`, `lib/app.dart`
- `lib/core/constants.dart`
- `lib/core/auth/mode_router.dart`
- `lib/core/i18n/app_localizations.dart`
- `lib/core/network/message_bus.dart`, `websocket_client.dart`
- `lib/core/notifications/device_registration.dart`, `notification_providers.dart`, `push_service.dart`
- `lib/core/storage/secure_token_store.dart`
- `lib/core/sync/sync_providers.dart`
- `lib/core/theme/app_colors.dart`, `app_spacing.dart`, `app_theme.dart`, `app_typography.dart`

**Shared Models — 11 files (🔴 CRITICAL — data layer entirely untested):**
- `lib/shared/models/alert.dart`, `document.dart`, `driver.dart`, `expense.dart`, `fleet_position.dart`, `message.dart`, `sync_cursor.dart`, `transport.dart`, `user.dart`, `vehicle.dart`, `vehicle_document.dart`

**Copilot Feature — 6 files:**
- `copilot_integration.dart`, `models/copilot_models.dart`, `screens/copilot_screen.dart`, `voice/copilot_voice_handler.dart`, `widgets/copilot_chat_bubble.dart`, `widgets/copilot_confirmation_sheet.dart`

**Dispatcher Feature — 10 files:**
- `dispatcher_shell.dart`, `alerts/approval_detail_screen.dart`, `analytics/analytics_providers.dart`, `analytics/dispatcher_analytics_screen.dart`, `drivers/driver_list_screen.dart`, `fleet/fleet_map_screen.dart`, `home/dispatcher_home_screen.dart`, `home/dispatcher_providers.dart`, `jobs/job_list_screen.dart`, `jobs/job_providers.dart`

**Driver Feature — 9 files:**
- `driver_shell.dart`, `documents/document_list_screen.dart`, `documents/ocr_result_card.dart`, `expenses/expense_list_screen.dart`, `expenses/expense_providers.dart`, `home/driver_providers.dart`, `notifications/driver_notifications_screen.dart`, `transports/transport_list_screen.dart`, `vehicle/vehicle_providers.dart`

**Settings — 1 file:**
- `settings_screen.dart`

### Files with Partial / Shallow Coverage

| Source File | Test File | Issue |
|-------------|-----------|-------|
| `delta_sync_service.dart` | `test/sync_service_test.dart` | Only ~8% — single test that starts/stops service |
| `action_queue.dart` | `test/offline_queue_test.dart` | Only ~32% — enqueue/dequeue only, no conflict resolution |
| `local_db.dart` | `test/core/local_db_test.dart` | Only schema initialization tested, no CRUD |
| `auth_providers.dart` | `test/core/auth_service_test.dart` | Only ~48% — login flow, but no rehydration/refresh |
| `login_screen.dart` | `test/auth/auth_screens_test.dart` | ~57% — basic render, no form validation edge cases |
| `session_expired_screen.dart` | `test/auth/auth_screens_test.dart` | ~48% — only renders, no navigation/logout tests |
| `job_detail_screen.dart` | `test/widgets/job_detail_screen_test.dart` | ~59% — renders but no interaction tests |

### Missing Test Types

| Test Type | Status |
|-----------|--------|
| Unit tests | ✅ 13 files |
| Widget tests | ✅ 12 files |
| **Integration tests** | **❌ None** (no `integration_test/` directory) |
| **E2E tests** | **❌ None** (no `e2e/` directory) |
| **Screenshot/golden tests** | **❌ None** |
| **Performance benchmarks** | **❌ None** |
| **Stress tests** | **❌ None** |
| **Mutation tests** | **❌ None** |
| **Chaos tests** | **❌ None** |

### Native Platform Tests

| Platform | Tests |
|----------|-------|
| **iOS (Swift)** | 1 basic file (`RunnerTests.swift`) |
| **Android (Kotlin)** | **0 tests** for `MainActivity.kt` |
| **Windows (C++)** | **0 tests** for any windows/ runner code |
| **Web (HTML/JS)** | **0 tests** |

### Critical Gaps Summary

| Priority | Gap | Details |
|----------|-----|---------|
| 🔴 #1 | **Shared Models (11 files)** | Data layer entirely untested — no serialization, JSON parsing, model validation tests |
| 🔴 #2 | **Copilot Feature (6 files)** | AI integration, voice handler, chat bubbles — completely untested |
| 🔴 #3 | **Dispatcher Feature (10 files)** | Fleet map, analytics, job list, approvals — nearly all untested |
| 🔴 #4 | **WebSocket Client** | Real-time communication layer — zero tests |
| 🔴 #5 | **Push Notifications (4 files)** | Device registration, notification routing, push service — zero tests |
| 🟠 #6 | **Delta Sync Service** | ~8% coverage — offline sync is critical for mobile |
| 🟠 #7 | **No Integration/E2E Tests** | Full user journeys never tested end-to-end |
| 🟠 #8 | **No Performance Tests** | No benchmarks on a mobile app where performance matters |
| 🟠 #9 | **Theme/Constants (4 files)** | Design system untested |

---

*End of audit. All findings sourced from direct file inspection across all modules of the Operion ecosystem — including `C:\Users\Bonjo\source\repos\Calculator logistica` (backend, desktop, website) and `C:\Users\Bonjo\source\repos\operion-mobile-app` (Flutter mobile app).*
