Here's the comprehensive breakdown of every part of the app (excluding UI and Security) that could get automated tests:

---

## 1. Services (Business Logic) — **Unit Tests**

| Module | Path | What to test |
|--------|------|-------------|
| Calculator | `services/calculator.py` | Trip cost/profit calculations, margin formulas, fuel/toll/salary math |
| Cost Engine | `services/cost_engine.py` | Cost estimation with country/road-class weightings, per-km/per-day calculations |
| Currency Service | `services/currency_service.py` | Currency conversion, rounding, exchange-rate application |
| Exchange Rate Service | `services/exchange_rate_service.py` | Rate fetching from open.er-api/frankfurter, fallback chain |
| Fuel Price Service | `services/fuel_price_service.py` | Fuel price scraping, country-specific parsing |
| Conflict Service | `services/conflict_service.py` | Trip schedule overlap detection, driver/truck conflict resolution |
| Export Service | `services/export_service.py` | PDF generation, Excel export with proper column/row mappings |
| i18n | `services/i18n.py` | Translation loading (22 languages), locale switching, key fallback |
| Preferences | `services/preferences.py` | User preference read/write/sync |
| Country Exclusion | `services/country_exclusion.py` | Country routing exclusion logic |
| Country Borders | `services/country_borders.py` | Border geometry data integrity |
| Country Avoidance | `services/country_avoidance.py` | Avoidance rule evaluation |
| Geocode Nominatim | `services/geocode_nominatim.py` | Address→coord and coord→address resolution, caching |
| GraphHopper Network | `services/graphhopper_network.py` | HTTP helpers, request building, retry logic |
| Analytics Service | `services/analytics_service.py` | KPI aggregation, period-over-period calculations |
| Email Importer | `services/email_importer.py` | Email parsing, attachment extraction |
| Folder Watcher | `services/folder_watcher.py` | Filesystem monitoring triggers, file-type gating |
| Health Check | `services/health_check.py` | Filesystem/DB/cache health assertions |

---

## 2. Route Services — **Unit + Integration Tests**

| Module | Path | Test type |
|--------|------|-----------|
| Route Service | `services/route_service.py` | **Integration** — GraphHopper calls, cache hits/misses, toll/fuel estimation |
| Route Planner Controller | `services/route_planner_controller.py` | **Integration** — multi-stop orchestration, stop ordering, profile selection |
| Route State | `services/route_state.py` | **Unit** — state-machine transitions and invariants |
| Route Persistence | `services/route_persistence.py` | **Integration** — save/load route with all linked entities |
| Route History Service | `services/route_history_service.py` | **Integration** — history queries, filtering, stats |
| Route Sharing Service | `services/route_sharing_service.py` | **Unit** — QR code generation, URL encoding/decoding round-trip |
| Route Decoder | `services/route_decoder.py` | **Unit** — URL → route parameter parsing |
| Route Runner | `services/route_runner.py` | **Integration** — route execution lifecycle |
| Route Profiles | `services/route_profiles.py` | **Unit** — profile-to-cost mapping integrity |
| Route Result Presenter | `services/route_result_presenter.py` | **Unit** — result formatting, unit conversion |
| Route Compliance | `services/route_compliance.py` | **Unit** — driving-hours rules, rest-period checks |
| Stop Factory | `services/stop_factory.py` | **Unit** — stop creation from various input formats |

---

## 3. Fleet & Tracking Services — **Unit + Integration Tests**

| Module | Path | Test type |
|--------|------|-----------|
| Fleet Service | `services/fleet_service.py` | **Integration** — CRUD, maintenance scheduling, insurance tracking |
| Fleet Tracking Service | `services/fleet_tracking_service.py` | **Integration** — Wialon/Frotcom/Navixy adapter calls, telemetry parse |
| Fleet Maintenance Service | `services/fleet_maintenance_service.py` | **Unit** — maintenance interval math, predictive scoring |
| Driver-Truck Service | `services/driver_truck_service.py` | **Unit** — assignment validation, availability checking |
| Tacho Service | `services/tacho_service.py` | **Integration** — tachograph file parsing, activity extraction |

---

## 4. Operations Engine — **Unit + Integration Tests**

| Module | Path | Test type |
|--------|------|-----------|
| Operations Engine | `services/operations/operations_engine.py` | **Integration** — singleton initialization, all-subsystems start/stop lifecycle |
| Event Bus | `services/operations/event_bus.py` | **Unit** — pub/sub dispatch, subscription, unsubscribe, handler error isolation |
| Alert Manager | `services/operations/alert_manager.py` | **Unit** — alert creation, deduplication, resolution, severity escalation |
| Maintenance Engine | `services/operations/maintenance_engine.py` | **Unit** — maintenance prediction from telemetry, interval math, overdue detection |
| Notification Center | `services/operations/notification_center.py` | **Integration** — email dispatch, SMS gateway call, retry on failure |
| Trip Status Engine | `services/operations/trip_status_engine.py` | **Unit** — all status transitions, invalid-transition rejection |
| Trip Status Workflow | `services/operations/trip_status_workflow.py` | **Unit** — workflow steps, undo reversal correctness |
| CMR Auto Generator | `services/operations/cmr_auto_generator.py` | **Unit** — trigger conditions, field population from trip data |
| Dunner Engine | `services/operations/dunner_engine.py` | **Unit** — reminder scheduling, due-date calculation, retry scheduling |
| Dunner Templates | `services/operations/dunner_templates.py` | **Unit** — template variable substitution, missing-variable handling |
| Rules | `services/operations/rules.py` | **Unit** — rule evaluation, AND/OR condition trees, action triggering |
| Undo Stack | `services/operations/undo_stack.py` | **Unit** — push/pop, redo, state snapshot correctness |

---

## 5. Invoicing — **Unit + Integration Tests**

| Module | Path | Test type |
|--------|------|-----------|
| Invoice Service | `services/invoicing/service.py` | **Integration** — CRUD, numbering sequence, tax calculation |
| Invoice Generator | `services/invoicing/generator.py` | **Unit** — PDF layout, field placement, reportlab output validity |
| Receipt Service | `services/invoicing/receipt_service.py` | **Unit** — receipt creation, line-item totals |
| Receipt Generator | `services/invoicing/receipt_generator.py` | **Unit** — PDF rendering, payment-method variants |
| Proforma Service | `services/invoicing/proforma_service.py` | **Unit** — proforma creation from invoice, status transitions |
| Config Manager | `services/invoicing/config_manager.py` | **Unit** — numbering schema, template selection |
| CMR Generator | `services/invoicing/cmr_generator.py` | **Unit** — UN/CEFACT box placement, carrier/shipper fields |
| CMR eFTI | `services/invoicing/cmr_efti.py` | **Unit** — XML schema validation, namespace handling |
| CMR Validator | `services/invoicing/cmr_validator.py` | **Unit** — mandatory field checks, cross-field consistency |

---

## 6. Document Management — **Unit + Integration Tests**

| Module | Path | Test type |
|--------|------|-----------|
| Versioning Service | `services/document/versioning_service.py` | **Integration** — version chain integrity, increment logic |
| Upload Service | `services/document/upload_service.py` | **Integration** — file accept, metadata extraction, path resolution |
| Template Service | `services/document/template_service.py` | **Unit** — template loading, field mapping |
| Search Service | `services/document/search_service.py` | **Integration** — FTS5 indexing, relevance ranking, phrase queries |
| OCR Service | `services/document/ocr_service.py` | **Integration** — OCR pipeline trigger, result storage |
| Expiry Service | `services/document/expiry_service.py` | **Unit** — expiration math, notification-trigger logic |
| Contract Service | `services/document/contract_service.py` | **Unit** — contract status lifecycle, renewal calculation |
| Document Service | `services/document_service.py` | **Integration** — full CRUD, tag/link, file-system synch |

---

## 7. Document Automation — **Unit + Integration Tests**

| Module | Path | Test type |
|--------|------|-----------|
| Pipeline | `services/document_automation/pipeline.py` | **Integration** — full pipeline run: import→enhance→OCR→validate→AI→match→package→email |
| Types | `services/document_automation/types.py` | **Unit** — enum values exhaustiveness |
| Trip Matcher | `services/document_automation/trip_matcher.py` | **Unit** — signal scoring, threshold configuration, false-positive handling |
| Package Builder | `services/document_automation/package_builder.py` | **Unit** — package assembly from matched docs |
| OCR Validator | `services/document_automation/ocr_validator.py` | **Unit** — confidence thresholds, field-sanity checks |
| OCR Extractor | `services/document_automation/ocr_extractor.py` | **Unit** — text region extraction, structured-field parsing |
| Image Processor | `services/document_automation/image_processor.py` | **Unit** — rotation, deskew, contrast normalization |
| Field Extractors | `services/document_automation/field_extractors.py` | **Unit** — regex/named-entity field extraction accuracy |
| Document Grouper | `services/document_automation/document_grouper.py` | **Unit** — grouping heuristics, timestamp clustering |
| Customer Detector | `services/document_automation/customer_detector.py` | **Unit** — name/fiscal-code matching against client DB |
| Cloud OCR | `services/document_automation/cloud_ocr.py` | **Integration** — Google Vision API call, Azure API call, response parse |
| AI Fallback | `services/document_automation/ai_fallback.py` | **Integration** — PaddleOCR call, text extraction quality |
| Email Template | `services/document_automation/email_template.py` | **Unit** — variable substitution, conditional blocks, missing-var handling |

---

## 8. AutoMail (Dunner) — **Unit + Integration Tests**

| Module | Path | Test type |
|--------|------|-----------|
| Template Service | `services/automail/template_service.py` | **Unit** — template render with all variable types, HTML escaping |
| Reminder Service | `services/automail/reminder_service.py` | **Unit** — schedule matching: days_before_due, on_due_date, days_after_due |
| History Service | `services/automail/history_service.py` | **Unit** — sent-email queries, bounce tracking, open-rate stats |

---

## 9. Repositories (Data Access Layer) — **Integration Tests**

All 24 repositories in `repositories/` should get **integration tests** against a real or in-memory SQLite:

| Repository | Tests |
|------------|-------|
| `trip_repository.py` | CRUD, filtering by status/date/client, pagination |
| `client_repository.py` | CRUD, search, tag filtering |
| `driver_repository.py` | CRUD, availability queries |
| `fleet_repository.py` | CRUD, health-score filtering, maintenance-status |
| `route_repository.py` | Save, load, filter by date/truck |
| `route_event_repository.py` | Event insertion, ordered retrieval |
| `truck_route_assignment_repository.py` | Assignment CRUD, conflict checks |
| `document_repository.py` | CRUD, tag associations, version chain |
| `invoice_repository.py` | CRUD, numbering sequence, trip-link |
| `proforma_repository.py` | CRUD, status transitions |
| `receipt_repository.py` | CRUD, line-item sum aggregation |
| `tag_repository.py` | CRUD, entity association/deassociation |
| `contact_repository.py` | CRUD, client-linked contacts |
| `tacho_import_repository.py` | Import record creation, status updates |
| `tacho_driver_activity_repository.py` | Bulk insert, activity aggregation |
| `tacho_vehicle_data_repository.py` | Vehicle record query by driver |
| `successive_carrier_repository.py` | CRUD, multi-carrier chain |
| `settings_repository.py` | Key-value read/write/defaults |
| `pipeline_repository.py` | Pipeline-run status tracking |
| `driver_truck_assignment_repository.py` | Pairing CRUD, date-range overlap checks |
| `audit_repository.py` | Insert, query by entity/date, retention trimming |
| `analytics_repository.py` | Aggregation queries, period-over-period diffs |
| `alert_repository.py` | CRUD, filters by severity/status/entity |
| `automail_repository.py` | Template/schedule CRUD, client-override resolution |

---

## 10. Database — **Integration Tests**

| Module | Path | Test type |
|--------|------|-----------|
| DB Manager | `database/db_manager.py` | **Integration** — connection pool, migration execution, backup/restore |
| Schema | `database/schema.py` | **Unit** — all CREATE TABLE/INDEX statements execute clean; foreign-key integrity |
| Connection Pool | `database/connection_pool.py` | **Unit** — pool exhaustion, connection reuse, thread safety |

---

## 11. Backend API — **Integration + E2E Tests**

| Module | Path | Test type |
|--------|------|-----------|
| **All API Routers** | `backend/api/v1/*.py` (16 routers) | **Integration** — HTTP request→response with test DB, status codes, response schemas |
| Health | `backend/api/v1/health.py` | GET /api/v1/health returns JSON |
| Auth | `backend/api/v1/auth.py` | Login with valid/invalid creds, token refresh, expiry |
| Admin | `backend/api/v1/admin.py` | DB query endpoints, config update, role checks |
| Trips | `backend/api/v1/trips.py` | CRUD, status transitions, filtering, pagination |
| Clients | `backend/api/v1/clients.py` | CRUD, search, contact linking |
| Drivers | `backend/api/v1/drivers.py` | CRUD, document links |
| Fleet | `backend/api/v1/fleet.py` | CRUD, maintenance linking |
| Routes | `backend/api/v1/routes.py` | History queries, route planning triggers |
| Invoices | `backend/api/v1/invoices.py` | CRUD, PDF generation trigger, status |
| Receipts | `backend/api/v1/receipts.py` | CRUD, PDF generation |
| CMR | `backend/api/v1/cmr.py` | Generate, validate, eFTI export |
| Documents | `backend/api/v1/documents.py` | Upload, tag, search, version |
| OCR | `backend/api/v1/ocr.py` | Trigger OCR, status polling |
| Tacho | `backend/api/v1/tacho.py` | File upload, import status, activity query |
| Maintenance | `backend/api/v1/maintenance.py` | Schedule CRUD, work-order status |
| Alerts | `backend/api/v1/alerts.py` | List, resolve, filter |
| Analytics | `backend/api/v1/analytics.py` | KPI endpoints, date-range filtering |
| Settings | `backend/api/v1/settings.py` | Read/write key-value settings |
| **Schemas** | `backend/schemas/*.py` (9 schema files) | **Unit** — pydantic validation (valid/invalid/edge-case payloads) |
| **Middleware** | | |
| Auth Middleware | `backend/middleware/auth_middleware.py` | **Unit** — valid/missing/expired token handling |
| Rate Limit Middleware | `backend/middleware/rate_limit_middleware.py` | **Unit** — limit enforcement, window expiry |
| Logging Middleware | `backend/middleware/logging_middleware.py` | **Unit** — request/response body capture, redaction |
| **Dependencies** | `backend/dependencies.py`, `backend/dependencies_security.py` | **Unit** — dependency resolution, scoping |
| **Cache** | `backend/cache.py` | **Integration** — Redis set/get/delete, TTL expiry |

---

## 12. Celery Background Tasks — **Integration Tests**

| Module | Path | Test type |
|--------|------|-----------|
| OCR Tasks | `backend/celery_app/tasks/ocr_tasks.py` | Task enqueue, success/failure handling |
| Document Tasks | `backend/celery_app/tasks/document_tasks.py` | Task enqueue, retry on failure |
| Celery App Config | `backend/celery_app/celery.py` | Broker connection, task registration |

---

## 13. Client/Remote Layer — **Unit + Integration Tests**

| Module | Path | Test type |
|--------|------|-----------|
| API Client | `client/api_client.py` | **Integration** — HTTP calls with auth headers, error handling, retry |
| Auth Manager | `client/auth_manager.py` | **Unit** — login hydratation, token storage, expiry check |
| Cache | `client/cache.py` | **Unit** — set/get/ttl, invalidation |
| Remote Services Stubs | `client/remote_services.py` through `client/remote_analytics.py` (10 files) | **Unit** — stub correctness, method signatures match backend |
| Network Worker | `client/network/network_worker.py` | **Unit** — queue processing, concurrency |

---

## 14. Utils — **Unit Tests**

| Module | Path | What to test |
|--------|------|-------------|
| Helpers | `utils/helpers.py` | All utility functions |
| Formatting | `utils/formatting.py` | Number formatting (currencies, decimals), date formatting |
| Formatters | `utils/formatters.py` | Additional formatting edge cases |
| Validation | `utils/validation.py` | Email regex, phone regex, VAT-ID, IBAN, required-field |
| Labels | `utils/labels.py` | Label generation correctness |
| Dates | `utils/dates.py` | Date arithmetic, range validation, timezone handling |
| Number to Words | `utils/number_to_words.py` | All supported languages, edge numbers (0, negatives) |
| Logger | `utils/logger.py` | Log level config, rotation setup |
| Observability | `utils/observability.py` | Metric emission, gauge/stat format |
| Resource Path | `utils/resource_path.py` | Bundled vs dev path resolution |
| Chart Export | `utils/chart_export.py` | Headless chart render, file output |

---

## 15. Configuration — **Unit Tests**

| Module | Path |
|--------|------|
| `config.py` | Path resolution, default values, environment overrides |
| `backend/config.py` | Pydantic BaseSettings validation, OPERION_ prefix parsing |

---

## 16. App-Wide E2E Tests

| Scope | Description |
|-------|-------------|
| Complete Trip Lifecycle | Create trip → assign driver/truck → route plan → generate CMR → dispatch → status transitions → invoice generation → receipt → Dunner reminders |
| Document Automation Pipeline | Drop file in watched folder → OCR → match to trip → package → email → verify trip docs linked |
| Fleet Maintenance Lifecycle | Create maintenance schedule → trigger by telemetry → create work order → complete → update health score |
| Currency & Cost Flow | Fetch exchange rates → fetch fuel prices → create trip with foreign costs → calculate costs → export invoice with converted totals |

---

## Summary Count

| Layer | Modules | Test Type |
|-------|---------|-----------|
| Services (business logic) | 18 | Unit + Integration |
| Route Services | 12 | Unit + Integration |
| Fleet & Tracking | 5 | Unit + Integration |
| Operations Engine | 12 | Unit + Integration |
| Invoicing | 9 | Unit + Integration |
| Document Management | 8 | Unit + Integration |
| Document Automation | 13 | Unit + Integration |
| AutoMail | 3 | Unit |
| Repositories | 24 | Integration |
| Database | 3 | Unit + Integration |
| Backend API Routers | 16 | Integration |
| Backend Schemas | 9 | Unit |
| Backend Middleware | 3 | Unit |
| Backend Cache + Deps | 3 | Unit + Integration |
| Celery Tasks | 3 | Integration |
| Client/Remote | 13 | Unit + Integration |
| Utils | 10 | Unit |
| Configuration | 2 | Unit |
| E2E Flows | 4 scenarios | E2E |

**Total: ~170 testable modules** (excluding UI and Security)
