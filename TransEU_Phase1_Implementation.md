# Trans.eu Phase 1 — Implementation Plan

> **Status:** Ready for implementation  
> **Prerequisites:** `TransEU_Architecture.md` (approved), `TransEU_KnowledgeBase.md` (complete)  
> **Phase Goal:** Read-Only Search & Import — dispatchers can search Trans.eu and import loads as trips  

---

## Table of Contents

1. [Pre-Implementation Prerequisites](#a-pre-implementation-prerequisites)
2. [Implementation Phases](#b-implementation-phases)
3. [Complete File Inventory](#c-complete-file-inventory)
4. [Testing Strategy](#d-testing-strategy)
5. [Risk Areas & Mitigations](#e-risk-areas--mitigations)
6. [Effort Estimates](#f-effort-estimates)

---

## A. Pre-Implementation Prerequisites

These MUST be completed before any adapter/UI work. They touch shared models and infrastructure everything else depends on.

### A1. Model Changes — `models/freight_exchange_models.py`

Three backward-compatible additions:

**1. `ProviderCredentials` — add authorization_code fields**
```
New fields: grant_type (Literal["client_credentials", "authorization_code"] = "client_credentials")
            authorization_code: Optional[str] = None
            redirect_uri: Optional[str] = None
            api_key: Optional[str] = None
```

**2. `ProviderSession` — add user_id field**
```
New field: user_id: Optional[int] = None
```

**3. `ProviderCapabilities` — add Trans.eu flags**
```
New fields: supports_freight_publication: bool = False
            supports_negotiation: bool = False
            supports_transport_orders: bool = False
            supports_monitoring: bool = False
            supports_webhooks: bool = False
            supports_oauth_user: bool = False
            requires_api_key_header: bool = False
```

**4. New models at end of file:**
- `TransEuUserToken` — per-user OAuth token (company_id, user_id, access_token_encrypted, refresh_token_encrypted, expires_at, status, api_key_encrypted)
- `FreightOffer` — Trans.eu freight tracked in Operion (trans_eu_freight_id, status, publication_status, origin, destination, price, distance, raw_payload, operion_trip_id)
- `TransEuWebhookEvent` — raw webhook event storage (trans_eu_event_id for idempotency, event_name, occurred_at, payload, status)

### A2. Database Migration

**File:** `alembic/versions/xxxx_trans_eu_phase1.py`

**5 tables created + 1 column added:**

1. `ALTER TABLE freight_exchange_connections ADD COLUMN user_id INTEGER REFERENCES users(id)`  
   *(NULL for system-level providers like TIMOCOM, populated for Trans.eu)*

2. `CREATE TABLE trans_eu_user_tokens` — per-user OAuth token storage
   - id (UUID PK), company_id, user_id, trans_eu_account_id, access_token_encrypted, refresh_token_encrypted, scope, expires_at, api_key_encrypted, client_id, client_secret_encrypted, status (active|expired|revoked|needs_reauth), connected_at, last_used_at, last_refreshed_at
   - UNIQUE(company_id, user_id)

3. `CREATE TABLE trans_eu_freight_offers` — freight object tracking
   - id (UUID PK), company_id, user_id, trans_eu_freight_id, trans_eu_reference_number, status, publication_status, publication_type, origin, destination, pickup_from/to, delivery_from/to, price_amount, price_currency, distance_km, trailer_type, adr, weight_kg, raw_payload (TEXT/JSON), externally_modified_at, operion_trip_id (FK to trips), trans_eu_order_id, created_at, updated_at

4. `CREATE TABLE trans_eu_webhook_events` — incoming webhook idempotency
   - id (UUID PK), company_id, trans_eu_event_id (UNIQUE), event_name, occurred_at, payload (TEXT), status, processed_at, error_message, created_at

5. `CREATE TABLE trans_eu_webhook_events_failed` — dead letter queue
   - id (UUID PK), company_id, trans_eu_event_id, event_name, payload, error_message, error_type, attempt_count, max_attempts, next_retry_at, status (pending|retrying|failed_permanent|resolved), created_at

**Verification:** Migration must include `DOWN` (reversible) and a test that creates/drops all 5 tables.

### A3. Infrastructure — Redis-backed Components

**Issue:** Existing circuit breaker (`backend/copilot/circuit_breaker.py`) and rate limiter (`backend/middleware/rate_limit_middleware.py`) are in-memory only — state lost on restart, not shared across gunicorn workers.

**Solution:** Dedicated Redis-backed implementations for the freight exchange subsystem.

#### A3.1 — Create `services/freight_exchange/circuit_breaker.py`

- **Class:** `FreightCircuitBreaker`
- **State storage:** Redis keys `circuit_breaker:freight:{company_id}:{provider_id}`
- **States:** CLOSED → (5 consecutive failures) → OPEN (30s) → HALF_OPEN (1 probe request) → CLOSED or OPEN
- **Methods:** `is_allowed()`, `record_success()`, `record_failure()`, `reset()`
- **Auth errors (401) do NOT count toward trip threshold** — auth failure is a user problem, not a provider outage

#### A3.2 — Create `services/freight_exchange/rate_limiter.py`

- **Class:** `FreightRateLimiter`
- **Two buckets per (company_id, provider_id):** API calls (15 RPS), Token calls (5 RPS)
- **Algorithm:** Redis sorted-set sliding window per second
- **Methods:** `acquire_api()`, `acquire_token()`, `acquire_with_wait(timeout_ms=200)`
- **Key format:** `rate_limit:freight:{company_id}:{provider_id}:api` / `...:token`
- **Cleanup:** Keys auto-expire after 2 seconds

### A4. Celery Beat Wiring

**Issue:** `celery.py` has one hardcoded beat entry; `schedule.py` has 8 entries that are NOT auto-merged.

**Fix:** Add `celery_app.conf.beat_schedule.update(CELERY_BEAT_SCHEDULE)` to `celery.py`, then add Trans.eu tasks to `schedule.py`.

### A5. TransEuAdapter Skeleton

Create `services/freight_exchange/adapters/trans_eu.py` as a skeleton that:
- Extends `FreightProviderAdapter`
- Sets `provider_id = "trans_eu"`
- Registers via `@register_freight_provider`
- All 6 methods raise `NotImplementedError("Phase 1: not yet implemented")`

This lets the registry validate and other code reference `get_adapter("trans_eu")` without import errors. The skeleton is replaced in Phase 1.

---

## B. Implementation Phases

```
Phase 0 (Foundation) ─── prerequisite for everything
    │
    ├── Phase 1 (TransEuAdapter — Core Read Path)
    │       │
    │       ├── Phase 2 (OAuth Flow in Desktop Client)
    │       │       │
    │       │       ├── Phase 3 (UI Integration)
    │       │       │       │
    │       │       │       └── Phase 4 (Webhooks + Background Sync)
    │       │       │
    │       │       └── Phase 3 can start after Phase 2
    │       │
    │       └── Phase 2 depends on Phase 1 (needs adapter for token exchange)
    │
    └── All phases depend on Phase 0 having been completed
```

---

### PHASE 0: Foundation (Model Changes + Database + Infrastructure)

| Step | File | Action | Dependencies |
|---|---|---|---|
| 0.1 | `models/freight_exchange_models.py` | Add new fields + 3 new models | None |
| 0.2 | `alembic/versions/xxxx_trans_eu_phase1.py` | Create migration | Step 0.1 |
| 0.3 | `services/freight_exchange/circuit_breaker.py` | Create Redis-backed circuit breaker | None (Redis client injected) |
| 0.4 | `services/freight_exchange/rate_limiter.py` | Create Redis-backed rate limiter | None |
| 0.5 | `backend/celery_app/celery.py` | Merge schedule.py entries | None |
| 0.6 | `backend/celery_app/schedule.py` | Add Trans.eu task stubs | Step 0.5 |
| 0.7 | `services/freight_exchange/adapters/trans_eu.py` | Skeleton adapter (all 6 methods stubs) | Step 0.1 |

**Gate:** All tests pass. Migration applies cleanly. Skeleton adapter registers without errors. `test_model_changes`, `test_migration_applied`, `test_adapter_registration` pass.

**Estimated:** 1-2 days

---

### PHASE 1: TransEuAdapter — Core Read Path

| Step | File | Action | Dependencies |
|---|---|---|---|
| 1.1 | `services/trans_eu/client.py` (NEW) | HTTP client wrapper for Trans.eu API (Api-key injection, OAuth token exchange, request/response handling) | Phase 0 |
| 1.2 | `services/freight_exchange/adapters/trans_eu.py` | Replace skeleton with full implementation: `authenticate()` (authorization_code → token), `refresh_session()` (refresh_token grant), `test_connection()` (ping freights endpoint), `search_loads()` (filter translation + result mapping), `get_load()` (single freight fetch), `capabilities()` (all Trans.eu flags) | Step 1.1 |
| 1.3 | `services/freight_exchange/connection_manager.py` | Modify `connect_provider()` for authorization_code grant, add `get_trans_eu_token()` and `store_trans_eu_token()` methods | Phase 0, Step 1.2 |
| 1.4 | `services/freight_exchange/search.py` | Verify Search Engine works with Trans.eu adapter (should work as-is — confirm, fix if needed) | Step 1.2 |

**Key Implementation Details:**

**`search_loads()` filter translation:**
- `LoadSearchFilters.origin` → Trans.eu `loadingPlace` + `loadingRadiusKm`
- `LoadSearchFilters.destination` → Trans.eu `unloadingPlace` + `unloadingRadiusKm`
- `LoadSearchFilters.pickup_date_from/to` → Trans.eu `loadingDateFrom`/`loadingDateTo`
- `LoadSearchFilters.trailer_type` → Trans.eu `vehicleType` (comma-joined)
- `LoadSearchFilters.adr_required` → Trans.eu `adr` (string boolean)
- `LoadSearchFilters.weight_kg_min/max` → Trans.eu `weightFromKg`/`weightToKg`
- `LoadSearchFilters.sort_by` → Trans.eu `sortBy` (map: date→loading_date, price→price)
- `LoadSearchFilters.sort_order` → Trans.eu `order` (asc/desc)
- Default: `page=1`

**`_map_freight_to_result()` Trans.eu freight → LoadSearchResult mapping:**
- `id` → `result_id` + `provider_load_id`
- `loading.place` → `origin` (locality + ", " + country)
- `unloading.place` → `destination`
- `loading.timespans.begin/end` → `pickup_window`
- `unloading.timespans.begin/end` → `delivery_window`
- `publication.price.value` + `publication.price.currency` → `price` (Money)
- `transit_time / 60 * 70` → `distance_km` (estimate at ~70 km/h)
- `requirements.required_truck_bodies[0]` → `trailer_type`
- `requirements.required_adr_classes` non-empty → `adr`
- `sum(loads[].weight)` → `weight_kg`
- `ftl` flag → `loading_type` ("ftl" / "ltl")
- Full `raw` dict → `raw_payload`

**Gate:** `test_trans_eu_adapter.py` passes. `test_map_freight_to_result` produces valid LoadSearchResult from mock Trans.eu freight JSON. `test_search_returns_results` with fake adapter returns structured results. `test_import_parity_still_passes` — Trans.eu import produces same TripCreate as TIMOCOM.

**Estimated:** 3-4 days

---

### PHASE 2: OAuth Flow in Desktop Client

| Step | File | Action | Dependencies |
|---|---|---|---|
| 2.1 | `ui/views/freight_exchange/oauth_loopback.py` (NEW) | Localhost OAuth callback server (port 19999, threading-based, opens browser to Trans.eu auth URL, captures authorization_code from redirect) | Phase 0 |
| 2.2 | `ui/views/freight_exchange/connect_view.py` (NEW) | Provider connection UI: "Connect Trans.eu" button, status indicators, token expiration display | Step 2.1 |
| 2.3 | `backend/api/v1/freight_exchange.py` | Add `POST /freight/providers/connect_trans_eu` endpoint (receives authorization_code, exchanges for tokens, stores in trans_eu_user_tokens) | Phase 1 (Step 1.3) |

**OAuth Flow:**

```
1. User clicks "Connect Trans.eu" in Operion UI
2. Operion starts OAuthLoopbackServer on localhost:19999
3. Operion opens system browser to:
   https://auth.platform.trans.eu/oauth2/auth?client_id=...&response_type=code&redirect_uri=http://localhost:19999/trans-eu/callback&state=...
4. User logs in on Trans.eu Platform (in browser)
5. Trans.eu redirects to http://localhost:19999/trans-eu/callback?code=...&state=...
6. OAuthCallbackHandler captures the code, shows "success" page, signals completion
7. Desktop app sends {authorization_code, redirect_uri} to POST /freight/providers/connect_trans_eu
8. Backend calls TransEuAdapter.authenticate() → exchanges code for tokens
9. Backend stores encrypted tokens in trans_eu_user_tokens table
10. UI shows "Connected!" with token expiry time
```

**Edge cases:**
- User closes browser before completing login → timeout after 120s, show error
- User denies access → Trans.eu redirects with `error=access_denied` → show "Access denied"
- Port 19999 already in use → try 19998, 19997, etc.
- Token expires while user is working → auto-refresh (Phase 1 Step 1.2) or prompt for re-auth

**Gate:** User can click "Connect Trans.eu", complete OAuth in browser, and see "Connected" status with valid token. `test_oauth_flow_integration` passes.

**Estimated:** 2-3 days

---

### PHASE 3: UI Integration

| Step | File | Action | Dependencies |
|---|---|---|---|
| 3.1 | `ui/views/freight_exchange/search_view.py` | Replace demo placeholder in `_on_search()` with real API call via `RemoteFreightExchange.search_loads()`. Fix sort field mapping (display text → API field names). Fix trailer type mapping (send `trailer_type` list via `trailer` filter). | Phase 1 (Search Engine working) |
| 3.2 | `client/remote_freight_exchange.py` | Verify all methods work with Trans.eu. Add `get_trans_eu_status()` method. | Phase 2 (OAuth tokens available) |
| 3.3 | `ui/views/freight_exchange/load_detail_view.py` | Extend detail view to show Trans.eu-specific fields (reference_number, publication status, contact employees). Add "Import as Trip" action with feedback. | Phase 1 (get_load working) |

**Search View Changes (Step 3.1 — CRITICAL):**

Current `_on_search()` is a hardcoded demo. Must be replaced with:

```
def _on_search(self):
    self.show_loading(searching=True)
    try:
        response = self._api.search_loads(
            origin_location=self.origin_input.text(),
            destination_location=self.dest_input.text(),
            pickup_date_from=self.date_from.date().toString("yyyy-MM-dd"),
            pickup_date_to=self.date_to.date().toString("yyyy-MM-dd"),
            trailer_type=self.trailer_combo.currentData(),  # list[str], not string
            adr_required=self.adr_check.isChecked(),
            loading_type=self.loading_type_combo.currentData(),
            loading_country=self.loading_country_combo.currentData(),
            delivery_country=self.delivery_country_combo.currentData(),
            sort_by=self._map_sort_field(self.sort_combo.currentIndex()),
            sort_order="asc" if "↑" in self.sort_combo.currentText() else "desc",
        )
        results = response.get("results", [])
        provider_statuses = response.get("provider_statuses", [])
        
        self.set_table_data(results)
        self.update_status_bar(has_providers=True)
        self.set_result_count(len(results))
        
        # Log skipped providers
        for status in provider_statuses:
            if status.get("status") == "skipped":
                logger.warning("Provider %s skipped: %s", status["provider_id"], status.get("error"))
    except Exception as e:
        self.show_error(str(e))
    finally:
        self.show_loading(searching=False)
```

**Sort field mapping fix:**
- UI display: "Price ↑" → API: `sort_by="price"`, `sort_order="asc"`
- UI display: "Distance ↓" → API: `sort_by="distance"`, `sort_order="desc"`
- Added `_map_sort_field()` helper for the translation

**Trailer type mapping fix:**
- UI sends `trailer` as display string ("Curtainsider")
- API expects `trailer_type: Optional[list[str]]`
- Fix: Send as list with correct API value

**Gate:** Dispatcher can type origin/destination, select filters, click Search, and see real Trans.eu results (alongside TIMOCOM if connected). `test_ui_search_integration` passes.

**Estimated:** 2-3 days

---

### PHASE 4: Webhooks + Background Sync

| Step | File | Action | Dependencies |
|---|---|---|---|
| 4.1 | `services/trans_eu/webhook_ingestion.py` (NEW) | Webhook ingestion service: IP whitelist (52.208.90.151), URL secret verification, idempotency check via event_id, store to trans_eu_webhook_events, route to handler, dead letter queue on failure | Phase 0 (tables created) |
| 4.2 | `backend/api/v1/webhooks.py` | Add Trans.eu handler to existing webhook dispatcher. Set callback URL on freight/order creation. | Step 4.1 |
| 4.3 | `services/trans_eu/sync_service.py` (NEW) | Freight status sync: process webhook events to update FreightOffer records and linked Trips. Event → action mappings for freight lifecycle events. | Step 4.1 |
| 4.4 | `backend/celery_app/tasks/trans_eu_tasks.py` (NEW) | Celery tasks: `trans_eu_refresh_tokens` (every 30 min), `trans_eu_sync_active_freights` (every 10 min — webhook fallback), `trans_eu_process_failed_webhooks` (every 15 min), `trans_eu_health_check` (every 5 min), `trans_eu_cleanup_expired_sessions` (daily) | Phase 0 (Celery wired) |
| 4.5 | `backend/celery_app/schedule.py` | Add Trans.eu beat schedule entries (5 new entries) | Step 4.4 |

**Webhook Event → Internal Action Mappings:**

| Trans.eu Event | Internal Action |
|---|---|
| `freights.freight.create` | Upsert `FreightOffer` in `trans_eu_freight_offers` |
| `freights.freight.update` | Update `FreightOffer`, set `externally_modified_at` |
| `freights.publication.activated` | Update `publication_status='active'` |
| `freights.publication.canceled` | Update `publication_status='finished'` |
| `freights.publication.finished` | Update `publication_status='finished'` |
| `freights.publication.accepted` | Update `status='accepted'`. If linked trip exists, update trip status. |
| `freight_orders.order.created` | Create `FreightOrder` record. Notify dispatcher. |
| `freight_orders.order.delivery_was_confirmed` | Update linked trip status → 'Delivered' |
| `freight_orders.order.order_was_cancelled` | Update linked trip status → 'Cancelled' |

**Dead Letter Queue Retry Schedule:**
1m → 2m → 4m → 8m → 16m → 30m → 1h → 2h → 4h → 8h → `failed_permanent`

**Gate:** Webhook received from Trans.eu, processed, FreightOffer updated, linked Trip status synced. `test_webhook_ingestion`, `test_webhook_sync`, `test_dead_letter_queue` pass.

**Estimated:** 3-4 days

---

## C. Complete File Inventory

### Files to CREATE

| # | File | Phase | Purpose |
|---|---|---|---|
| 1 | `alembic/versions/xxxx_trans_eu_phase1.py` | 0 | 5 new tables + 1 column migration |
| 2 | `services/freight_exchange/circuit_breaker.py` | 0 | Redis-backed circuit breaker |
| 3 | `services/freight_exchange/rate_limiter.py` | 0 | Redis-backed token bucket rate limiter |
| 4 | `services/freight_exchange/adapters/trans_eu.py` | 0→1 | Trans.eu adapter (skeleton → full) |
| 5 | `services/trans_eu/__init__.py` | 1 | Package init |
| 6 | `services/trans_eu/client.py` | 1 | Low-level HTTP client for Trans.eu API |
| 7 | `services/trans_eu/webhook_ingestion.py` | 4 | Webhook ingestion pipeline |
| 8 | `services/trans_eu/sync_service.py` | 4 | Freight/order status sync |
| 9 | `backend/celery_app/tasks/trans_eu_tasks.py` | 4 | Celery tasks (token refresh, sync, cleanup) |
| 10 | `ui/views/freight_exchange/oauth_loopback.py` | 2 | Localhost OAuth callback server |
| 11 | `ui/views/freight_exchange/connect_view.py` | 2 | Provider connection UI |
| 12 | `tests/freight_exchange/test_trans_eu_phase0.py` | 0 | Model changes + migration + skeleton tests |
| 13 | `tests/freight_exchange/test_trans_eu_adapter.py` | 1 | Adapter unit tests (mapping, search, auth) |
| 14 | `tests/freight_exchange/test_trans_eu_oauth.py` | 2 | OAuth flow integration tests |
| 15 | `tests/freight_exchange/test_trans_eu_webhooks.py` | 4 | Webhook ingestion + sync tests |
| 16 | `tests/freight_exchange/test_trans_eu_celery.py` | 4 | Celery task unit tests |

### Files to MODIFY

| # | File | Phase | Changes |
|---|---|---|---|
| 1 | `models/freight_exchange_models.py` | 0 | Add grant_type, user_id, capabilities fields + 3 new models |
| 2 | `backend/celery_app/celery.py` | 0 | Merge schedule.py entries (~3 lines added) |
| 3 | `backend/celery_app/schedule.py` | 0→4 | Add 5 Trans.eu beat entries (Phase 4 actual, Phase 0 stubs) |
| 4 | `services/freight_exchange/connection_manager.py` | 1 | Extend for authorization_code grant + per-user token methods |
| 5 | `backend/api/v1/freight_exchange.py` | 2 | Add `POST /freight/providers/connect_trans_eu` endpoint |
| 6 | `backend/api/v1/webhooks.py` | 4 | Add Trans.eu handler dispatch |
| 7 | `ui/views/freight_exchange/search_view.py` | 3 | Replace demo `_on_search()` with real API call; fix sort + trailer mapping |
| 8 | `client/remote_freight_exchange.py` | 3 | Add `get_trans_eu_status()` |
| 9 | `ui/views/freight_exchange/load_detail_view.py` | 3 | Extend for Trans.eu-specific fields |

### Files NOT to modify (must remain UNCHANGED)

| File | Reason |
|---|---|
| `services/freight_exchange/search.py` | Search Engine is provider-agnostic — plugging in TransEuAdapter should work without changes |
| `services/freight_exchange/import_pipeline.py` | Import pipeline already handles any provider via source_provider_id |
| `services/freight_exchange/evaluation.py` | Evaluation engine is provider-agnostic (proven by tests) |
| `services/freight_exchange/fleet_matcher.py` | Fleet matcher is provider-agnostic (proven by tests) |
| `services/freight_exchange/registry.py` | Registry handles new adapters via decorator — no code change |
| `services/freight_exchange/adapter_base.py` | ABC does not change — all additions are to models + concrete adapters |

**If any of these files must change, the architecture has a leak — STOP and fix the abstraction.**

---

## D. Testing Strategy

### Phase 0 Tests

| Test File | Key Tests | What it proves |
|---|---|---|
| `test_trans_eu_phase0.py::TestModelChanges` | 4 tests — backward compat, new fields, grant_type default | Model changes don't break existing TIMOCOM flow |
| `test_trans_eu_phase0.py::TestMigrationApplied` | 2 tests — user_id column exists, trans_eu_user_tokens table exists | Migration applied correctly |
| `test_trans_eu_phase0.py::TestAdapterRegistration` | 2 tests — adapter in registry, provider_id correct | Skeleton adapter registers |

### Phase 1 Tests

| Test File | Key Tests | What it proves |
|---|---|---|
| `test_trans_eu_adapter.py::TestMapping` | 6 tests — origin, destination, price, trailer, ADR, weight, distance mapping | Trans.eu JSON → LoadSearchResult is correct for all field types |
| `test_trans_eu_adapter.py::TestEdgeCases` | 4 tests — empty loads, null price, missing fields, multi-spot | Adapter handles edge cases gracefully |
| `test_trans_eu_adapter.py::TestSearchFilters` | 4 tests — all filter combinations translate correctly | Filter translation is complete |
| `test_trans_eu_adapter.py::TestImportParity` | 1 test — Trans.eu import produces same TripCreate as TIMOCOM | Re-runs `test_import_parity.py` with trans_eu |
| `test_adapter_base.py` (existing) | All 10 test classes must pass | No regression in ABC/registry behavior |

### Phase 2 Tests

| Test File | Key Tests | What it proves |
|---|---|---|
| `test_trans_eu_oauth.py::TestOAuthFlow` | 4 tests — success, timeout, denied, port conflict | OAuth flow handles all user scenarios |
| `test_trans_eu_oauth.py::TestTokenStorage` | 2 tests — token encrypted, token retrieved | Tokens are securely stored and retrievable |
| `test_api_contract.py` (existing) | Extend with Trans.eu connect/disconnect endpoints | API contract holds |

### Phase 3 Tests

| Test File | Key Tests | What it proves |
|---|---|---|
| `test_ui_search_integration.py` (NEW) | 3 tests — search with Trans.eu only, multi-provider, empty results | UI search works end-to-end |
| `test_ui_sort_mapping.py` (NEW) | 2 tests — sort display → API field mapping | Sort field fix works |

### Phase 4 Tests

| Test File | Key Tests | What it proves |
|---|---|---|
| `test_trans_eu_webhooks.py::TestWebhookIngestion` | 3 tests — valid webhook, duplicate, invalid IP | Webhook ingestion pipeline works |
| `test_trans_eu_webhooks.py::TestWebhookSync` | 3 tests — freight update, order created, delivery confirmed | Status sync updates internal models |
| `test_trans_eu_webhooks.py::TestDeadLetterQueue` | 2 tests — processing failure → DLQ, retry schedule | DLQ works correctly |
| `test_trans_eu_celery.py::TestTokenRefresh` | 1 test — expiring token → refreshed | Scheduled refresh works |
| `test_trans_eu_celery.py::TestHealthCheck` | 2 tests — healthy, degraded | Health check integration |

### Integration / E2E

| Test | Phase | What it proves |
|---|---|---|
| `test_api_contract.py` (extend) | All | Trans.eu endpoints follow same contract as TIMOCOM |
| `test_integration.py` (extend) | All | Trans.eu adapter in full pipeline with other providers |
| `test_import_parity.py` (verify) | 1 | Trans.eu import produces identical downstream results |

---

## E. Risk Areas & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Trans.eu OAuth requires browser** — desktop app can't redirect natively | HIGH | Localhost loopback server (port 19999). Works on all platforms. RFC 8252 compliant. Firefox/Chrome restrictions on localhost redirects handled by trying alternate ports or custom URI scheme fallback. |
| **Rate limit per client_id not per token** — all companies sharing one Trans.eu app compete for 15 RPS | MEDIUM | Verify with Trans.eu. If per client_id: deployment-level rate limiter coordinating all companies. If per token: per-company limiter sufficient. |
| **Trans.eu freight schema more complex than TIMOCOM** — multi-spot, multi-load, publication sub-object | MEDIUM | For search results: use first spot as origin, last as destination, sum loads for weight. Full object stored in `raw_payload`. `FreightOffer` model captures full complexity for publication/negotiation phases. |
| **Webhook delivery reliability** — Trans.eu may not retry failed deliveries | MEDIUM | Periodic poller (every 10 min) as fallback. Dead letter queue with retry for processing failures. Always return 200 OK to Trans.eu even if processing fails. |
| **In-memory circuit breaker / rate limiter** — existing implementations are not Redis-backed | HIGH | Phase 0 creates dedicated Redis-backed implementations. Existing implementations remain for their existing use cases (Co-Pilot, middleware). |
| **Token refresh failure leaves user stranded** | MEDIUM | Scheduled background refresh reduces window. On failure → mark `needs_reauth`, notify user. Company service token (if configured) as fallback for background operations. |
| **Search view is a demo placeholder** — `_on_search()` returns hardcoded data | CRITICAL | Phase 3 replaces with real API call. This is the primary user-facing deliverable. |

---

## F. Effort Estimates

| Phase | Deliverables | Estimated | Notes |
|---|---|---|---|
| **Phase 0** | Models, migration, infrastructure (CB, RL), skeleton adapter, Celery wiring | 1-2 days | Foundation — everything depends on this |
| **Phase 1** | TransEuAdapter fully implemented, ConnectionManager extended, verified with fake adapter in search pipeline | 3-4 days | Core technical work |
| **Phase 2** | OAuth loopback server, connect UI, backend connect endpoint | 2-3 days | Can overlap with Phase 1 review |
| **Phase 3** | Search view integration (replace demo), detail view extensions, sort/trailer mapping fixes | 2-3 days | User-facing — most visible |
| **Phase 4** | Webhook ingestion, sync service, Celery tasks (5 tasks + beat entries), dead letter queue | 3-4 days | Operational reliability |
| **Testing** | Tests for each phase | Included in phase estimates | Tests written alongside code |
| **Total** | | **11-16 working days** | ~2.5-3.5 weeks for single developer |

### Parallelization Opportunities

- Phase 0, 1, 2, and 3 have sequential dependencies (each builds on prior)
- Phase 4 can partially overlap with Phase 3 webhook ingestion while UI work proceeds
- Tests can be written by a second developer while primary developer builds adapters

---

## Appendix: Verification Checklist Before Marking Phase 1 Complete

- [ ] `TransEuAdapter` passes all 6 abstract method tests
- [ ] `test_import_parity.py` passes with Trans.eu — downstream modules can't tell the difference
- [ ] Existing freight exchange tests (`test_adapter_base.py`, `test_api_contract.py`, `test_integration.py`) all pass — no regressions
- [ ] User can click "Connect Trans.eu", authenticate via browser, and see connected status
- [ ] User can search Trans.eu with filters and see real results in the search table
- [ ] User can click "Import" on a Trans.eu load and it creates a valid Operion trip
- [ ] Trip has `source='freight_exchange'`, `source_provider_id='trans_eu'`, `source_reference_id='<freight_id>'`
- [ ] Webhook from Trans.eu updates FreightOffer status
- [ ] Circuit breaker trips after 5 consecutive failures and recovers after 30s
- [ ] Rate limiter enforces 15 RPS for API calls and 5 RPS for token calls
- [ ] No changes to Search Engine, Import Pipeline, Evaluation Engine, Fleet Matcher, or Route Planner
- [ ] All Alembic migrations apply cleanly and are reversible
- [ ] No hardcoded Trans.eu URLs — all from config/environment
