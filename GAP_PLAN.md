# GAP RECOVERY PLAN — PHASES, STAGES & STEPS

**Principle:** Each Phase tackles ~50 files. Each Stage tackles ~10 files. Each Step tackles 1-2 files.  
**Order:** Foundations first (data layer → services → API), then UI (higher churn, less risk), then infrastructure last.  
**Agent mapping:** Each Step → one `@fixer` session (bounded implementation). Stages sequenced; Steps within a Stage parallelizable.

---

## PHASE 1 — BACKEND FOUNDATION (~48 files)

**Goal:** Eliminate zero-coverage files in the data layer, services, middleware, and schemas. Every backend file reaches at least basic positive/negative tests.  
**Dependency gate:** None (can start immediately).

### Stage 1.1 — Domain Models (2 files)
- **Step 1.1a:** `models/freight_exchange_models.py` — 14 classes, 0% coverage. Test: all dataclass construction, field defaults, validators, edge cases (empty, null, boundary). 1 sub-agent.
- **Step 1.1b:** `models/tacho_models.py` — 7 classes, 0% coverage. Test: validators (`path_must_not_be_empty`), `DriverHoursAnalysis.is_compliant`, `FleetTachoSummary` calculations. 1 sub-agent.

### Stage 1.2 — Schemas (6 files)
- **Step 1.2a:** `backend/schemas/mobile.py` — 19 models, 0% coverage. Test: all Pydantic validators, field constraints, required/optional, serialization round-trip. 1 sub-agent.
- **Step 1.2b:** `backend/schemas/waitlist.py`, `auth.py`, `invoice.py`, `receipt.py`, `settings.py` — 5 files. Test: field constraints (`gt=0`, `min_length`, `max_length`), state machine constants, cross-field validators, boundary conditions. 2 sub-agents (batch by similarity).

### Stage 1.3 — Middleware (3 files)
- **Step 1.3a:** `backend/middleware/security_headers_middleware.py` — CSP, HSTS, X-Frame-Options, CORS in dev vs prod. Test: header presence, correct values, mode-dependent behavior. 1 sub-agent.
- **Step 1.3b:** `backend/middleware/webhook_middleware.py` — raw body preservation for HMAC signing. Test: body preserved, multipart handling, no-body requests. 1 sub-agent.
- **Step 1.3c:** `backend/middleware/*` — expand Redis backend for idempotency; add PrometheusMiddleware dispatch test; add lifespan/startup test for `create_app()`. 1 sub-agent.

### Stage 1.4 — Core Services (7 files)
- **Step 1.4a:** `services/audit_service.py` + `cost_engine.py` — audit logging CRUD, cost estimation with country/road factors. 1 sub-agent.
- **Step 1.4b:** `services/constraint_engine.py` + `route_persistence.py` — truck constraint validation, GraphHopper params, route record building. 1 sub-agent.
- **Step 1.4c:** `services/feature_flags.py` + `integration_health_service.py` + `payment_profile_service.py` — flag scope evaluation, health check orchestration, CRUD wrappers. 1 sub-agent.

### Stage 1.5 — Repository & Celery Gaps (5 files)
- **Step 1.5a:** `repositories/user_repository.py` — 0% coverage. Test: list/create/deactivate with company scoping. 1 sub-agent.
- **Step 1.5b:** `repositories/analytics_repository.py` — expand from ~20% to 80%+. Prioritize: dashboard charts, financial analytics, driver comparison, CTE queries. 2 sub-agents (batch by query complexity).
- **Step 1.5c:** `backend/celery_app/tasks/maintenance_tasks.py` — 0% coverage. Test: task execution, error handling, retry logic. 1 sub-agent.

### Stage 1.6 — Operations & Dispatch Gaps (6 files)
- **Step 1.6a:** `services/dispatch_service/availability.py` — CRITICAL: zero tests. Test each blocking condition in isolation (insurance, inspection, maintenance, license, medical, tacho hours), date parsing edge cases, concurrent blocks. 2 sub-agents (truck checks + driver checks).
- **Step 1.6b:** `services/operations/*` — expand: AlertManager max eviction, EventBus >100 subs stress test, OperationsEngine start() timer scheduling, TripStatusWorkflow None-truck path. 1 sub-agent.
- **Step 1.6c:** `services/document_automation/` — expand: `ai_fallback.ai_extract()`, `_sanitize_filename_part()`, `_detect_document_quad()`, `trip_matcher.py`, `package_builder.py`. 1 sub-agent.

### Stage 1.7 — Client Remote Services (4 files)
- **Step 1.7a:** `client/config.py` + `client/remote_ops_stub.py` — ClientConfig singleton, API URL/SSL resolution, EventBus stub substitute. 1 sub-agent.
- **Step 1.7b:** `client/remote_preferences.py` + `client/network/network_worker.py` — preferences API wrapper, QThread network worker with signal testing. 1 sub-agent.

### Stage 1.8 — Backend External Gaps (freight exchange — ~12 files)
- **Step 1.8a:** `backend/api/v1/freight_exchange.py` — 14 endpoints, 0% coverage. Test: provider connect/disconnect, load search/import, OAuth flow. Mock all HTTP. 1 sub-agent.
- **Step 1.8b:** `services/freight_exchange/adapters/timocom.py` — adapter unit tests mirroring trans_eu tests. 1 sub-agent.
- **Step 1.8c:** `services/freight_exchange/health_monitor.py` — 0% coverage. Test: `run_all_health_checks()`, `_check_provider_health()`, timeout handling. 1 sub-agent.
- **Step 1.8d:** New chaos tests for T.eu/TIMOCOM — simulate API timeouts, 503s, SSL errors, rate limits; verify circuit breaker + rate limiter integration. 1 sub-agent.

---

## PHASE 2 — WEBSITE FRONTEND (~50 files)

**Goal:** Raise website coverage from ~60% to ~85%+. Focus on services (17%), untested pages (30), and industry pages (8).  
**Dependency gate:** None. Can run parallel to Phase 1.

### Stage 2.1 — Services (5 files)
- **Step 2.1a:** `website/src/services/analytics.ts` — `trackPageView`, `trackEvent`, `trackCTAClick`, `trackDownload`, `trackPricingInteraction`. Test: correct API calls, parameter passing, error resilience. 1 sub-agent.
- **Step 2.1b:** `website/src/services/jwt.ts` + `accessibility.tsx` — JWT verification, `SkipToContent`, `useReducedMotion`, `useFocusTrap`. 1 sub-agent.
- **Step 2.1c:** `website/src/services/seo.tsx` + `seo-improvements.tsx` — `getPageTitle`, `generateMetaTags`, `StructuredData`. Test: correct meta tag generation per page. 1 sub-agent.

### Stage 2.2 — i18n & Contexts (3 files)
- **Step 2.2a:** `website/src/i18n/locale-context.tsx` + `types.ts` — `LocaleProvider`, `useLocale` hook. Test: locale switching, default locale, localStorage persistence. 1 sub-agent.
- **Step 2.2b:** `website/src/contexts/auth-provider.tsx` — Auth context expansion. Test: token refresh, logout edge cases, session expiration. 1 sub-agent.

### Stage 2.3 — Shared Components (6 files)
- **Step 2.3a:** `comparison-table.tsx`, `table-of-contents.tsx`, `timeline.tsx`. 1 sub-agent.
- **Step 2.3b:** `testimonial-card.tsx`, `stat-card.tsx`, `error-boundary.tsx`. 1 sub-agent.

### Stage 2.4 — SEO Components (2 files)
- **Step 2.4a:** `seo-head.tsx`, `structured-data.tsx`. Test: correct rendering, structured data JSON-LD validity. 1 sub-agent.

### Stage 2.5 — Public Pages — Batch 1 (10 files)
- **Step 2.5a:** `home.tsx`, `features.tsx`, `pricing.tsx`, `download.tsx`, `mission.tsx`. 1 sub-agent.
- **Step 2.5b:** `contact.tsx`, `privacy.tsx`, `terms.tsx`, `not-found.tsx`, `waitlist.tsx`. 1 sub-agent.

### Stage 2.6 — Public Pages — Batch 2 (10 files)
- **Step 2.6a:** `error-500.tsx`, `error-maintenance.tsx`, `error-offline.tsx`, `api-playground.tsx`, `product-tour.tsx`. 1 sub-agent.
- **Step 2.6b:** `roi-calculator.tsx`, `route-demo.tsx`, `integrations-explorer.tsx`, `trust-center.tsx`, `blog-author.tsx`. 1 sub-agent.

### Stage 2.7 — Industry Pages (8 files)
- **Step 2.7a:** `industry-agriculture.tsx`, `construction.tsx`, `fleet.tsx`, `freight.tsx`. 1 sub-agent.
- **Step 2.7b:** `manufacturing.tsx`, `owner-ops.tsx`, `transport.tsx`. 1 sub-agent.

### Stage 2.8 — Dashboard & Admin Pages (11 files)
- **Step 2.8a:** `billing.tsx`, `downloads.tsx`, `documentation.tsx`, `licenses.tsx`, `onboarding.tsx`. 1 sub-agent.
- **Step 2.8b:** `organizations.tsx`, `organization-settings.tsx`, `blog-editor.tsx` (slug variant). 1 sub-agent.
- **Step 2.8c:** `admin-waitlist.tsx`, `overview-tab.tsx`, `entries-tab.tsx`, `campaign-tab.tsx`. 1 sub-agent.

### Stage 2.9 — E2E Expansion
- **Step 2.9a:** Add cross-browser (Firefox + Safari) Playwright config + fix failing specs. 1 sub-agent.
- **Step 2.9b:** Add visual regression testing (Playwright screenshot diff or Percy). 1 sub-agent.
- **Step 2.9c:** Add missing E2E journeys: pricing interaction, waitlist signup, ROI calculator, download flow, full auth (register → verify → login → password reset). 1 sub-agent.

---

## PHASE 3 — AI COPILOT (~55 files)

**Goal:** Copilot coverage from ~60% to ~85%+. Router endpoints, tool files, LLM integration, voice, security.  
**Dependency gate:** Phase 1 (services/models must be stable). Start after Phase 1 Stage 1.4.

### Stage 3.1 — Copilot Router — All 10 Endpoints
- **Step 3.1a:** `POST /copilot/chat` + `POST /copilot/voice` — full request/response cycle, auth, schema validation. 1 sub-agent.
- **Step 3.1b:** `GET /copilot/plans/{id}` + plan lifecycle (`confirm`, `cancel`, `undo`) — ownership validation, not-found vs not-owned, kill switch. 1 sub-agent.
- **Step 3.1c:** `GET /copilot/conversations` + `/{id}` + `GET /copilot/insights` — cursor pagination, Redis fallback, empty results. 1 sub-agent.
- **Step 3.1d:** WebSocket `/ws/{conversation_id}` — connect, message flow, token validation, disconnection, reconnection. 1 sub-agent.
- **Step 3.1e:** Internal helpers: `_push_plan_update`, `_validate_plan_ownership`, company-isolated in-memory stores (`_pending_plans`, `_plan_owners`, `_company_conversations`). 1 sub-agent.

### Stage 3.2 — Copilot Tools — Batch 1 (12 files)
- **Step 3.2a:** `dispatch_tools.py`, `document_tools.py`, `invoice_tools.py`, `payment_tools.py`. 1 sub-agent.
- **Step 3.2b:** `route_tools.py`, `route_sharing_tools.py`, `trip_tools.py`, `trip_crud_tools.py`. 1 sub-agent.
- **Step 3.2c:** `client_tools.py`, `client_crud_tools.py`, `driver_tools.py`, `driver_crud_tools.py`. 1 sub-agent.

### Stage 3.3 — Copilot Tools — Batch 2 (12 files)
- **Step 3.3a:** `automail_tools.py`, `cmr_tools.py`, `currency_tools.py`, `export_tools.py`. 1 sub-agent.
- **Step 3.3b:** `maintenance_tools.py`, `ocr_tools.py`, `tacho_tools.py`, `tracking_tools.py`. 1 sub-agent.
- **Step 3.3c:** `delete_tools.py`, `undo_tools.py`, `vehicle_tools.py`, `vehicle_crud_tools.py`. 1 sub-agent.

### Stage 3.4 — LLM Provider & Voice
- **Step 3.4a:** `backend/copilot/llm/providers/google_provider.py` — deep tests: `generate()` with mocked response, streaming chunks, token counting, error propagation, API key handling. 1 sub-agent.
- **Step 3.4b:** `backend/copilot/voice/tts.py` + `whisper_stt.py` + `piper_tts.py` — `synthesize()` with real/patched audio, full STT→LLM→TTS pipeline, language tier routing. 1 sub-agent.
- **Step 3.4c:** `backend/copilot/voice/` — remaining gaps: `schemas.py` field validation, `language_tiers.py` enum edge cases. 1 sub-agent.

### Stage 3.5 — Copilot Security
- **Step 3.5a:** Prompt injection sanitization — replace `assert True` placeholders with real tests. Test: SQL injection in user input, system prompt override attempts, context extraction. 1 sub-agent.
- **Step 3.5b:** Cross-company data isolation — plan storage isolation between tenants, JWT validation on WebSocket, permission checks on undo. 1 sub-agent.
- **Step 3.5c:** Rate limiting + token limit guardrails — `tier_gate.check_quota()`, `MAX_LLM_TOKENS_PER_TURN` enforcement, LLM provider failover routing. 1 sub-agent.

### Stage 3.6 — Copilot Mutation Tests
- **Step 3.6a:** Add mutation tests for `planner.py` intent extraction thresholds, `confidence.py` weights, `executor.py` guardrail constants, router lifecycle logic. 1 sub-agent.

---

## PHASE 4 — DESKTOP APP QT COMPONENTS + CLIENT (~48 files)

**Goal:** Eliminate 19 zero-coverage Qt files, expand partial coverage. Desktop Qt from ~85% to ~95%.  
**Dependency gate:** None (pure UI, no backend changes needed).

### Stage 4.1 — Copilot Widgets — Batch 1 (4 files)
- **Step 4.1a:** `ui/copilot/widgets/timeline_widget.py` — 941 lines. Test: execution timeline display, step cards, reasoning graph tree, confirmation bar, signal/slot flows. 1 sub-agent.
- **Step 4.1b:** `ui/copilot/widgets/guided_overlay_widget.py` — 738 lines. Test: step navigation, dim/highlight, paintEvent, tour overlay interactions. 1 sub-agent.
- **Step 4.1c:** `ui/copilot/widgets/copilot_panel.py` — 456 lines. Test: text/voice message send, controller integration, UI state transitions. 1 sub-agent.
- **Step 4.1d:** `ui/copilot/widgets/insight_queue.py` — 445 lines. Test: insight cards, severity badges, action buttons, queue ordering. 1 sub-agent.

### Stage 4.2 — Copilot Widgets — Batch 2 (5 files)
- **Step 4.2a:** `ui/copilot/widgets/chat_input.py` — 230 lines. Test: text input, mic button, send logic, input validation. 1 sub-agent.
- **Step 4.2b:** `ui/copilot/widgets/chat_bubble.py` + `conversation_display.py` — 126+135 lines. Test: bubble rendering, message types, conversation scrolling. 1 sub-agent.
- **Step 4.2c:** `ui/copilot/widgets/confirmation_modal.py` — 607 lines. Test: modal display, confirm/cancel actions, keyboard handling. 1 sub-agent.
- **Step 4.2d:** `ui/copilot/widgets/thinking_indicator.py` + `audio_recorder.py` + `tts_player.py` — animations, audio recording state, TTS playback. 1 sub-agent.

### Stage 4.3 — Freight Exchange Qt Views (3 files)
- **Step 4.3a:** `ui/views/freight_exchange/connect_view.py` + `oauth_loopback.py` — OAuth connection flow, redirect handling. 1 sub-agent.
- **Step 4.3b:** `ui/views/freight_exchange/search_view.py` + `load_detail_view.py` — search form, results display, load details, import action. 1 sub-agent.

### Stage 4.4 — Untested Dialogs (4 files)
- **Step 4.4a:** `ui/dialogs/freight_provider_settings.py` — 446 lines. Test: validation, provider CRUD, settings persistence. 1 sub-agent.
- **Step 4.4b:** `ui/dialogs/paired_assignment_dialog.py` + `share_route_dialog.py` — truck/driver assignment logic, suggestion system, URL copy/export. 1 sub-agent.
- **Step 4.4c:** `ui/dialogs/trip_search_dialog.py` — date range filtering, result selection, search logic. 1 sub-agent.

### Stage 4.5 — Untested Views (3 files)
- **Step 4.5a:** `ui/views/bulk_payments_view.py` — 952 lines. Test: payment batch management, CSV export, CRUD operations. 1 sub-agent.
- **Step 4.5b:** `ui/views/copilot_view.py` + `ui/views/dashboard.py` — 71+1003 lines. Test: chat panel wrapper, KPI dashboard rendering, chart loading. 1 sub-agent.

### Stage 4.6 — Client Remote Services (4 files)
- **Step 4.6a:** `client/config.py` + `remote_ops_stub.py` — ClientConfig URL resolution, EventBus stub substitution. 1 sub-agent.
- **Step 4.6b:** `client/remote_preferences.py` + `network/network_worker.py` — preferences API, QThread network with signal testing. 1 sub-agent.

### Stage 4.7 — Expand Partial Qt Coverage (6 files)
- **Step 4.7a:** `ui/models/maintenance_view_model.py` + `tacho_status_model.py` — test health score computation, driver status calculations. 1 sub-agent.
- **Step 4.7b:** `ui/widgets/kanban_column.py` — drag-drop signals, loading/empty/error states. 1 sub-agent.
- **Step 4.7c:** `ui/map/map_helpers.py` + `route_renderer.py` — marker click, bounds calculation, polyline rendering. 1 sub-agent.

---

## PHASE 5 — MOBILE API (BACKEND) + UTILS + SCRIPTS (~42 files)

**Goal:** Mobile API to ~95% coverage. Utils to ~85%. Scripts to minimal smoke coverage.  
**Dependency gate:** Phase 1 Stage 1.2 (schemas). Start after Phase 1.

### Stage 5.1 — Mobile API Endpoints + Schemas
- **Step 5.1a:** Fix known bugs + add tests for `POST /mobile/driver/expenses` (`IntegrityError` on `receipt_number`). 1 sub-agent.
- **Step 5.1b:** Add tests for `GET /mobile/devices` + `DELETE /mobile/devices/{device_id}`. 1 sub-agent.
- **Step 5.1c:** Complete `test_mobile_additional.py` — fill in all 20 stub tests (approval flows, fleet data, messaging edge cases). 1 sub-agent.
- **Step 5.1d:** Unskip `test_mobile_mutation.py` — fix fuzzing test infrastructure. 1 sub-agent.
- **Step 5.1e:** Add mobile schema validation tests — all 19 model field constraints, optional/required, serialization. 1 sub-agent.

### Stage 5.2 — Mobile API — Scenario Tests
- **Step 5.2a:** Offline mode scenarios — request queuing, retry on reconnect, conflict detection. 1 sub-agent.
- **Step 5.2b:** Sync scenarios — cursor conflicts, concurrent sync, partial sync failures, invalid cursors. 1 sub-agent.
- **Step 5.2c:** Limited bandwidth + performance — response size limits, pagination latency. 1 sub-agent.
- **Step 5.2d:** Push notification delivery — FCM/APNs token handling failures, device registration lifecycle. 1 sub-agent.

### Stage 5.3 — Utils Gaps
- **Step 5.3a:** `utils/validation.py` — `validate_iban()`, `validate_bic()`, `validate_bank_account()`, `validate_payment_info()` — all financial validation, test with valid/invalid edge cases. 1 sub-agent.
- **Step 5.3b:** `utils/dates.py` — `parse_date_safe()` with multi-format inputs, `is_expired()` with boundary dates. 1 sub-agent.
- **Step 5.3c:** `utils/perf_log.py` — `perf_timer()` actual timing measurement, `perf_log()` formatting. 1 sub-agent.

### Stage 5.4 — Scripts — Critical Path (6 files)
- **Step 5.4a:** `scripts/validate_migration.py` + `verify_client_isolation.py` — migration validation logic, tenant isolation verification. 1 sub-agent.
- **Step 5.4b:** `scripts/backup.sh` + `restore_data_from_backup.py` — backup integrity, restore flow, error handling. 1 sub-agent.
- **Step 5.4c:** `scripts/build_client.py` + `ci_copilot_gates.py` — build process, CI gating logic. 1 sub-agent.

### Stage 5.5 — Database Migrations (10 files)
- **Step 5.5a:** Add Alembic test infrastructure — fixture that applies all migrations from empty DB, verifies schema matches expected. 1 sub-agent.
- **Step 5.5b:** Test remaining 9 untested Alembic migrations — upgrade + verify table/column presence, test downgrade on each. 1 sub-agent.
- **Step 5.5c:** Test `database/connection_pool.py` — thread-safety, connection limits, WAL mode behavior. 1 sub-agent.
- **Step 5.5d:** Test `database/uuid_helpers.py` — UUID generation formats, uniqueness, edge cases. 1 sub-agent.

---

## PHASE 6 — DESKTOP APP REACT FRONTEND (~41 files)

**Goal:** Raise desktop React from ~19% to ~80%+. This is the worst-covered module in the ecosystem.  
**Dependency gate:** None. Can run parallel to earlier phases but immediately after Phase 1 infrastructure is ready.

### Stage 6.1 — UI Components (4 files)
- **Step 6.1a:** `badge.tsx` — 6 variants (default, secondary, destructive, outline, success, warning), all sizes, forwardRef. 1 sub-agent.
- **Step 6.1b:** `card.tsx` — 6 sub-components (Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter), hover effects, forwardRef. 1 sub-agent.
- **Step 6.1c:** `input.tsx` + `loading-spinner.tsx` — Input, Label, Textarea, focus/disabled states, all spinner sizes, forwardRef. 1 sub-agent.

### Stage 6.2 — Shared Components (7 files)
- **Step 6.2a:** `testimonial-card.tsx`, `section-wrapper.tsx`, `pricing-card.tsx`, `feature-card.tsx`. 1 sub-agent.
- **Step 6.2b:** `empty-state.tsx`, `cta-section.tsx`, `page-header.tsx`. 1 sub-agent.

### Stage 6.3 — Auth Pages (3 files)
- **Step 6.3a:** `forgot-password.tsx` — email enumeration protection, form validation, API error display. 1 sub-agent.
- **Step 6.3b:** `reset-password.tsx` — token validation, password mismatch via `z.refine()`, API errors. 1 sub-agent.
- **Step 6.3c:** `verify-email.tsx` — static page rendering, navigation links. 1 sub-agent.

### Stage 6.4 — Public Pages (13 files)
- **Step 6.4a:** Desktop public pages — batch all 13 pages with Vitest rendering + interaction tests. 2 sub-agents.

### Stage 6.5 — Route Protection + API Client
- **Step 6.5a:** Route protection / auth guards — test: protected routes redirect unauthenticated, role-based access, session expiry behavior. 1 sub-agent.
- **Step 6.5b:** API client error handling — network failure, timeout, non-JSON responses, `api.post`/`api.postForm` tests. 1 sub-agent.

### Stage 6.6 — Config + Snapshot Tests
- **Step 6.6a:** Config files + Vitest coverage reporter setup. 1 sub-agent.
- **Step 6.6b:** Snapshot tests for stable UI components — `button.tsx`, `badge.tsx`, `card.tsx`. 1 sub-agent.

---

## PHASE 7 — FLUTTER MOBILE APP — PART 1 (~50 files)

**Goal:** Shared models, core layer, and Copilot feature. First 50 files from ~30% to ~60%.  
**Dependency gate:** None. Can run parallel to other phases.

### Stage 7.1 — Shared Models — All 11 files (🔴 CRITICAL)
- **Step 7.1a:** `shared/models/alert.dart`, `document.dart`, `driver.dart`, `expense.dart`, `fleet_position.dart`. Test: JSON serialization/deserialization, field defaults, null safety. 1 sub-agent.  
- **Step 7.1b:** `shared/models/message.dart`, `sync_cursor.dart`, `transport.dart`, `user.dart`, `vehicle.dart`, `vehicle_document.dart`. Test: same. 1 sub-agent.

### Stage 7.2 — Core Network Layer
- **Step 7.2a:** `core/network/websocket_client.dart` — ~200 lines. Test: connect/disconnect, message send/receive, reconnection, error handling. 1 sub-agent.
- **Step 7.2b:** `core/network/message_bus.dart` — pub/sub patterns, error isolation, thread safety. 1 sub-agent.

### Stage 7.3 — Core Notifications (4 files)
- **Step 7.3a:** `core/notifications/push_service.dart` — 180 lines. Test: token registration, notification handling, error resilience. 1 sub-agent.
- **Step 7.3b:** `core/notifications/device_registration.dart` + `notification_providers.dart` + `notification_router.dart` — device CRUD, notification routing logic, provider state management. 1 sub-agent.

### Stage 7.4 — Core Sync System
- **Step 7.4a:** `core/sync/delta_sync_service.dart` — expand from ~8% to 80%+. Test: cursor management, delta calculation, full sync fallback. 1 sub-agent.
- **Step 7.4b:** `core/sync/sync_providers.dart` + `action_queue.dart` expansion — offline queue conflict resolution, provider state, retry logic. 1 sub-agent.
- **Step 7.4c:** `core/sync/connectivity_monitor.dart` + `conflict_handler.dart` — connectivity state changes, conflict resolution strategies. 1 sub-agent.

### Stage 7.5 — Core Storage + Auth
- **Step 7.5a:** `core/storage/secure_token_store.dart` — CRUD with secure storage, token refresh, error states. 1 sub-agent.
- **Step 7.5b:** `core/storage/local_db.dart` — expand from schema-only to full CRUD tests. 1 sub-agent.
- **Step 7.5c:** `core/auth/mode_router.dart` — offline/online mode routing, forced offline. 1 sub-agent.

### Stage 7.6 — Copilot Feature (6 files)
- **Step 7.6a:** `features/copilot/models/copilot_models.dart` + `copilot_integration.dart` — data models, backend integration. 1 sub-agent.
- **Step 7.6b:** `features/copilot/screens/copilot_screen.dart` + `voice/copilot_voice_handler.dart` — screen rendering, voice input flow. 1 sub-agent.
- **Step 7.6c:** `features/copilot/widgets/copilot_chat_bubble.dart` + `copilot_confirmation_sheet.dart` — widget rendering, interaction, confirmation flow. 1 sub-agent.

### Stage 7.7 — Theme + Entry Point (6 files)
- **Step 7.7a:** `core/theme/app_colors.dart`, `app_spacing.dart`, `app_theme.dart`, `app_typography.dart` — design token values, theme application. 1 sub-agent.
- **Step 7.7b:** `main.dart`, `app.dart` — app initialization, route setup, provider wiring. 1 sub-agent.

---

## PHASE 8 — FLUTTER MOBILE APP — PART 2 (~51 files)

**Goal:** Features (dispatcher, driver, settings), scroll test. From ~30-40% to ~75% overall.  
**Dependency gate:** Phase 7 (shared models and core must be tested first).

### Stage 8.1 — Dispatcher Feature — Screens (6 files)
- **Step 8.1a:** `dispatcher_shell.dart` + `alerts/approval_detail_screen.dart` — shell navigation, approval/rejection flow. 1 sub-agent.
- **Step 8.1b:** `analytics/dispatcher_analytics_screen.dart` + `analytics_providers.dart` — chart rendering, data loading/error states. 1 sub-agent.
- **Step 8.1c:** `drivers/driver_list_screen.dart` + `fleet/fleet_map_screen.dart` — driver list rendering, map display. 1 sub-agent.

### Stage 8.2 — Dispatcher Feature — Home + Jobs (4 files)
- **Step 8.2a:** `home/dispatcher_home_screen.dart` + `home/dispatcher_providers.dart` — dashboard cards, KPI data, provider state. 1 sub-agent.
- **Step 8.2b:** `jobs/job_list_screen.dart` + `jobs/job_providers.dart` — job list, filtering, provider state management. 1 sub-agent.

### Stage 8.3 — Driver Feature — Shell + Documents (5 files)
- **Step 8.3a:** `driver_shell.dart` — driver app shell, navigation, role-based UI. 1 sub-agent.
- **Step 8.3b:** `documents/document_list_screen.dart` + `document_upload_screen.dart` — document list, upload flow, (build on existing upload tests). 1 sub-agent.
- **Step 8.3c:** `ocr_result_card.dart` — OCR result display, retry action. 1 sub-agent.

### Stage 8.4 — Driver Feature — Expenses + Home (5 files)
- **Step 8.4a:** `expenses/expense_list_screen.dart` + `expense_providers.dart` — expense list, provider state management. 1 sub-agent.
- **Step 8.4b:** `home/driver_providers.dart` — driver home state, data aggregation. 1 sub-agent.
- **Step 8.4c:** `notifications/driver_notifications_screen.dart` — notification list, read/unread state. 1 sub-agent.

### Stage 8.5 — Driver Feature — Transports + Vehicle (4 files)
- **Step 8.5a:** `transports/transport_list_screen.dart` — transport list, status filtering. 1 sub-agent.
- **Step 8.5b:** `vehicle/vehicle_detail_screen.dart` + `vehicle_providers.dart` — vehicle details, provider state. 1 sub-agent.

### Stage 8.6 — Settings + Scroll Tests (3 files)
- **Step 8.6a:** `features/settings/settings_screen.dart` — settings screen rendering, theme toggle, logout. 1 sub-agent.
- **Step 8.6b:** Scroll/widget tests for all `lib/shared/widgets/*` not yet covered — `offline_banner.dart`, `shimmer_loader.dart`, `staleness_indicator.dart`, `status_badge.dart`. 1 sub-agent.

### Stage 8.7 — Flutter Integration Tests + E2E
- **Step 8.7a:** Set up `integration_test/` directory with Flutter integration test infrastructure. 1 sub-agent.
- **Step 8.7b:** Auth flow integration test — login → home → logout. 1 sub-agent.
- **Step 8.7c:** Driver daily flow integration test — view transports → update status → log expense. 1 sub-agent.
- **Step 8.7d:** Dispatcher flow integration test — view fleet → approve alert → view analytics. 1 sub-agent.

### Stage 8.8 — Flutter Golden Tests + Performance
- **Step 8.8a:** Golden/screenshot tests for stable shared widgets — `app_button.dart`, `app_card.dart`, `app_text_field.dart`, `empty_state.dart`. 1 sub-agent.
- **Step 8.8b:** Performance benchmarks for critical screens — home screen load time, transport list scrolling, sync operation. 1 sub-agent.

### Stage 8.9 — Native Platform Tests
- **Step 8.9a:** Android — add unit tests for `MainActivity.kt`. 1 sub-agent.
- **Step 8.9b:** iOS — expand `RunnerTests.swift`. 1 sub-agent.

---

## PHASE 9 — CI/CD INFRASTRUCTURE (~20 files)

**Goal:** Tests actually run in CI, coverage is measured and enforced, parallel execution, proper test databases.  
**Dependency gate:** Must be last — depends on all tests existing.

### Stage 9.1 — Coverage Infrastructure
- **Step 9.1a:** Add `fail_under` threshold to `pyproject.toml` (start at 60%, ratchet up). 1 sub-agent.
- **Step 9.1b:** Add Codecov/Coveralls integration for Python + website + desktop coverage reports. 1 sub-agent.
- **Step 9.1c:** Add Vitest coverage reporter for desktop React app. 1 sub-agent.

### Stage 9.2 — CI Workflows
- **Step 9.2a:** Create dedicated pytest CI workflow on push/PR for all Python tests. 1 sub-agent.
- **Step 9.2b:** Add Playwright E2E CI workflow — run on Chromium + Firefox + Safari. 1 sub-agent.
- **Step 9.2c:** Add Flutter mobile test CI workflow — `flutter test` on Linux + MacOS. 1 sub-agent.

### Stage 9.3 — Test Infrastructure Upgrades
- **Step 9.3a:** Add pytest-xdist for parallel test execution + sharding in CI. 1 sub-agent.
- **Step 9.3b:** Create `docker-compose.test.yml` with PostgreSQL + Redis for integration tests. 1 sub-agent.
- **Step 9.3c:** Add PostgreSQL test fixtures — migrate core integration tests from SQLite InMemoryDB to real PostgreSQL. 1 sub-agent.
- **Step 9.3d:** Create test data factories (Factory Boy or equivalent) — reduce manual seeding. 1 sub-agent.

### Stage 9.4 — Test Matrix Expansion
- **Step 9.4a:** Expand CI matrix to include Windows + macOS runners (where applicable). 1 sub-agent.
- **Step 9.4b:** Expand Python version matrix to 3.9/3.10/3.11 across all workflows. 1 sub-agent.

---

## SUMMARY — PHASE MAP

```
Phase 1  │ Backend Foundation          │ ~48 files │ Services, models, repos,
         │                              │           │ middleware, schemas, freight
         │                              │           │ exchange, client, celery
─────────┼──────────────────────────────┼───────────┼──────────────────────────────
Phase 2  │ Website Frontend            │ ~50 files │ Services, pages (public/
         │                              │           │ dashboard/admin/industry),
         │                              │           │ i18n, SEO, E2E expansion
─────────┼──────────────────────────────┼───────────┼──────────────────────────────
Phase 3  │ AI Copilot                  │ ~55 files │ Router endpoints, 26 tool
         │                              │           │ files, LLM provider, voice,
         │                              │           │ security, mutation
─────────┼──────────────────────────────┼───────────┼──────────────────────────────
Phase 4  │ Desktop Qt + Client         │ ~48 files │ 7 copilot widgets, 4 dialogs,
         │                              │           │ 3 freight views, 3 views,
         │                              │           │ 4 client files, partial
─────────┼──────────────────────────────┼───────────┼──────────────────────────────
Phase 5  │ Mobile API + Utils + Scripts│ ~42 files │ Endpoints, schemas, scenarios,
         │                              │           │ financial validation, dates,
         │                              │           │ migration scripts, DB migs
─────────┼──────────────────────────────┼───────────┼──────────────────────────────
Phase 6  │ Desktop React Frontend      │ ~41 files │ UI components, shared
         │                              │           │ components, auth pages,
         │                              │           │ public pages, route guards
─────────┼──────────────────────────────┼───────────┼──────────────────────────────
Phase 7  │ Flutter Mobile App — Part 1 │ ~50 files │ Shared models (11), core
         │                              │           │ (network, notifications, sync,
         │                              │           │ storage, auth), copilot (6),
         │                              │           │ theme, entry
─────────┼──────────────────────────────┼───────────┼──────────────────────────────
Phase 8  │ Flutter Mobile App — Part 2 │ ~51 files │ Dispatcher (12), driver (22),
         │                              │           │ settings, scroll, integration
         │                              │           │ tests, golden, perf, native
─────────┼──────────────────────────────┼───────────┼──────────────────────────────
Phase 9  │ CI/CD Infrastructure        │ ~20 files │ Coverage thresholds, CI
         │                              │           │ workflows, PostgreSQL fixtures,
         │                              │           │ test parallelism, matrix
─────────┼──────────────────────────────┼───────────┼──────────────────────────────

Total   │ 9 Phases, ~55 Stages        │ ~405 files │ ~405 files to cover
         │                              │           │ (of ~284 untested + ~120
         │                              │           │ partially covered)
```

## EXECUTION ORDER NOTES

- **Parallel-safe:** Phases 2, 4, 6, 7 can run fully parallel to each other (no shared dependencies).
- **Sequenced:** Phase 1 → Phase 3 (copilot depends on backend). Phase 1 → Phase 5 (mobile API depends on schemas).
- **Chained:** Phase 7 → Phase 8 (Flutter models/core → features).
- **Last:** Phase 9 (CI/CD depends on all tests existing).
- **Maximum parallelism:** Phases 2, 4, 6, 7 can be dispatched simultaneously after Phase 1's critical path is complete.

## TEST TYPE REQUIREMENTS PER MODULE

| Module | Unit | Widget | Integration | E2E | Golden | Perf | Chaos | Mutation |
|--------|------|--------|-------------|-----|--------|------|-------|----------|
| Backend services | ✅ | — | ✅ | — | — | ✅ | ✅ | ✅ |
| API endpoints | ✅ | — | ✅ | ✅ | — | ✅ | ✅ | — |
| Schemas/models | ✅ | — | — | — | — | — | — | ✅ |
| Repository | ✅ | — | ✅ | — | — | ✅ | — | — |
| Desktop Qt | ✅ | ✅ (Qt) | — | — | — | — | — | — |
| Desktop React | ✅ | ✅ (RTL) | ✅ | — | ✅ | — | — | — |
| Website React | ✅ | ✅ (RTL) | ✅ | ✅ (PW) | ✅ (PW) | — | ✅ (PW) | — |
| Mobile Flutter | ✅ | ✅ | ✅ | — | ✅ | ✅ | — | — |
| Mobile API | ✅ | — | ✅ | — | — | ✅ | ✅ | — |
| Scripts | ✅ | — | — | — | — | — | — | — |
| CI/CD | ✅ | — | ✅ | ✅ | — | — | — | — |
