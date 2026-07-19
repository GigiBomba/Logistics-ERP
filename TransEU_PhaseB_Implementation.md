# Trans.eu Phase B — Implementation Plan (Phases 2, 3, 4)

> **Prerequisites:** Phase A complete (models, migration, adapter, client, connection manager, tests)  
> **Phase B covers:** OAuth Flow, UI Integration, Webhooks & Background Sync  

---

## Audit Findings (Gap Analysis)

| # | Finding | Location | Severity |
|---|---|---|---|
| 1 | `_on_search()` is a hardcoded demo — no API call exists | `search_view.py:533-614` | 🔴 CRITICAL |
| 2 | No OAuth loopback server for desktop client | Missing entirely | 🔴 CRITICAL |
| 3 | No provider connection UI in freight exchange views | Missing entirely | 🔴 CRITICAL |
| 4 | No Trans.eu handler in webhook dispatcher | `webhooks.py` (only TIMOCOM) | 🔴 CRITICAL |
| 5 | Celery tasks referenced in schedule.py don't exist | `trans_eu_tasks.py` missing | 🔴 CRITICAL |
| 6 | No webhook ingestion or sync service | Missing entirely | 🔴 CRITICAL |
| 7 | Sort combo sends display text, not API field names | `search_view.py:345-349` | 🟡 MEDIUM |
| 8 | `trailer` field sent as string, API expects `list[str]` | `search_view.py` filter reading | 🟡 MEDIUM |
| 9 | No `connect_trans_eu` API endpoint on backend | `freight_exchange.py` | 🟡 MEDIUM |
| 10 | No method to get Trans.eu status in remote client | `remote_freight_exchange.py` | 🟡 MEDIUM |

---

## File Inventory

### Files to CREATE

| # | File | Phase | Purpose |
|---|---|---|---|
| 1 | `ui/views/freight_exchange/oauth_loopback.py` | 2 | Localhost HTTP server for OAuth redirect capture |
| 2 | `ui/views/freight_exchange/connect_view.py` | 2 | Provider connection widget (connect/disconnect/status) |
| 3 | `services/trans_eu/webhook_ingestion.py` | 4 | IP-whitelisted webhook receiver + idempotency |
| 4 | `services/trans_eu/sync_service.py` | 4 | Freight/order status sync from webhook events |
| 5 | `backend/celery_app/tasks/trans_eu_tasks.py` | 4 | 5 Celery tasks (token refresh, freight sync, failed webhooks, health, cleanup) |

### Files to MODIFY

| # | File | Phase | Changes |
|---|---|---|---|
| 1 | `backend/api/v1/freight_exchange.py` | 2 | Add `POST /freight/providers/connect_trans_eu` endpoint |
| 2 | `ui/views/freight_exchange/search_view.py` | 3 | Replace demo `_on_search()` with real API call; fix sort/trailer mapping |
| 3 | `client/remote_freight_exchange.py` | 2-3 | Add `connect_trans_eu()` and `get_trans_eu_status()` methods |
| 4 | `ui/views/freight_exchange/load_detail_view.py` | 3 | Extend for Trans.eu-specific fields (reference_number, publication_status) |
| 5 | `backend/api/v1/webhooks.py` | 4 | Add Trans.eu handler to `_dispatch_webhook()` |

### Files NOT to modify

| File | Reason |
|---|---|
| `services/freight_exchange/search.py` | Provider-agnostic — already works with Trans.eu |
| `services/freight_exchange/import_pipeline.py` | Provider-agnostic — already works |
| `services/freight_exchange/adapters/trans_eu.py` | Phase A complete — only bugfixes allowed |
| `services/freight_exchange/connection_manager.py` | Phase A complete |
| `services/trans_eu/client.py` | Phase A complete |
| `models/freight_exchange_models.py` | Phase A complete |

---

## Phase 2: OAuth Flow in Desktop Client

**Goal:** User clicks "Connect Trans.eu", authenticates via browser redirect, tokens stored securely.

### Step 2.1 — Create `ui/views/freight_exchange/oauth_loopback.py`

A lightweight, threading-based HTTP server on `localhost:19999` that captures the OAuth authorization code redirect from Trans.eu's auth server.

**Required behavior:**
- Starts on port 19999 (falls back to 19998, 19997 if occupied)
- Listens for GET `/trans-eu/callback?code=...&state=...`
- Extracts `code` and `error` from query params
- Returns HTML success/error page to browser
- Signals completion via `threading.Event`
- Provides `wait_for_code(timeout=120)` → returns `(code, error)`
- `build_auth_url(client_id, redirect_uri)` → returns full Trans.eu OAuth URL with random state
- `stop()` → shuts down the server

**Dependencies:** `http.server`, `threading`, `urllib.parse`, `uuid`

**Pattern to follow:** The existing codebase uses PySide6 threading patterns. Use `threading.Thread(daemon=True)` for the server thread. Keep the HTTP server class minimal — single-request, no keepalive.

**Verification:** Import successfully, start server, verify port binding, call stop.

### Step 2.2 — Create `ui/views/freight_exchange/connect_view.py`

A PySide6 widget for managing Trans.eu provider connections.

**Required widgets:**
- "Connect Trans.eu" button → starts OAuth flow
- Status indicator (connected/disconnected/token expiring)
- Token expiration display (e.g., "Token expires in 4h 23m")
- "Disconnect" button (shown when connected)
- "Test Connection" button
- Error display area

**OAuth flow wiring:**
1. User clicks "Connect Trans.eu"
2. View creates `OAuthLoopbackServer`, starts it
3. View builds auth URL and opens system browser (`webbrowser.open(auth_url)`)
4. View waits for code (shows "Waiting for authentication..." spinner)
5. On code received: calls `RemoteFreightExchange.connect_trans_eu(authorization_code, redirect_uri)`
6. On success: shows "Connected!" with token expiry
7. On error/timeout: shows error message

**Data flow:** ConnectView → RemoteFreightExchange → POST /api/v1/freight/providers/connect_trans_eu → ConnectionManagerService.connect_trans_eu_user → TransEuAdapter.authenticate → Trans.eu API

**Dependencies:** `PySide6.QtWidgets`, `webbrowser`, `OAuthLoopbackServer` (from step 2.1)

### Step 2.3 — Modify `backend/api/v1/freight_exchange.py`

Add a new endpoint for Trans.eu OAuth connection:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/freight/providers/connect_trans_eu` | `require_dispatcher` | Receive authorization_code, exchange for tokens, store |

**Request body (new Pydantic model `ConnectTransEuRequest`):**
```python
class ConnectTransEuRequest(BaseModel):
    authorization_code: str
    redirect_uri: str
```

**Handler logic:**
1. Extract `company_id` and `user_id` from JWT
2. Load Trans.eu client_id, client_secret, api_key from BackendSettings
3. Build `ProviderCredentials` with `grant_type="authorization_code"`, `authorization_code`, `redirect_uri`, `api_key`
4. Call `conn_mgr.connect_trans_eu_user(company_id, user_id, credentials)`
5. Return `{"status": "connected", "provider_id": "trans_eu", "user_id": user_id, "expires_at": session.expires_at.isoformat()}`

**Response shape:**
```json
{"status": "connected", "provider_id": "trans_eu", "user_id": 42, "expires_at": "2026-07-17T04:23:00+00:00"}
```

**Config keys to add to BackendSettings:**
- `trans_eu_client_id` — Trans.eu OAuth client_id
- `trans_eu_client_secret` — Trans.eu OAuth client_secret
- `trans_eu_api_key` — Trans.eu app-level Api-key

### Step 2.4 — Modify `client/remote_freight_exchange.py`

Add a new method:

```python
def connect_trans_eu(self, authorization_code: str, redirect_uri: str) -> dict:
    """Exchange OAuth authorization_code for Trans.eu tokens."""
    body = {"authorization_code": authorization_code, "redirect_uri": redirect_uri}
    return self._api._post("/api/v1/freight/providers/connect_trans_eu", body)

def get_trans_eu_status(self) -> dict:
    """Get Trans.eu connection status for current user."""
    # Filter providers list to just trans_eu
    providers = self.list_providers()
    for p in providers:
        if p.get("provider_id") == "trans_eu":
            return p
    return {"provider_id": "trans_eu", "status": "disconnected"}
```

### Phase 2 Verification

| Test | What it proves |
|---|---|
| `test_oauth_loopback.py` — server starts, receives code, stops | OAuthLoopbackServer works correctly |
| `test_connect_trans_eu_endpoint.py` — POST returns connected with expires_at | Backend endpoint works |
| Manual test: click "Connect Trans.eu" → browser opens → login → connected | Full OAuth flow works end-to-end |
| Token stored in `trans_eu_user_tokens` table | Token persisted correctly |

---

## Phase 3: UI Integration

**Goal:** Dispatcher can search Trans.eu from the freight exchange UI and see real results.

### Step 3.1 — Modify `ui/views/freight_exchange/search_view.py`

**Replace the demo `_on_search()` method (lines 533-614).** The replacement must:

1. Read all filter values from the UI widgets (origin, destination, dates, trailer, ADR, weight, distance, loading type, countries, sort)
2. Translate sort display text to API field names (e.g., "Price ↑" → sort_by="price", sort_order="asc")
3. Send `trailer_type` as `list[str]`, not a single string
4. Call `RemoteFreightExchangeService.search_loads()` with the filter dict
5. Handle the response: populate table_data, update status bar, show loading state
6. Handle errors: show error message, keep existing results

**Sort field mapping (new helper `_map_sort_field()`):**

| UI Display | API sort_by | API sort_order |
|---|---|---|
| "Price ↑" (lowest first) | `price` | `asc` |
| "Price ↓" (highest first) | `price` | `desc` |
| "Distance ↑" | `distance` | `asc` |
| "Distance ↓" | `distance` | `desc` |
| "Date ↑" | `date` | `asc` |
| "Date ↓" | `date` | `desc` |
| default | `date` | `desc` |

**Trailer type fix:**
- Current: UI sends `"standard"` (single string) as `trailer` field
- Required: `trailer_type: list[str]` e.g., `["standard"]`
- Fix: wrap in list before sending

**Table row format (must match existing `set_table_data` expectations):**
```python
{
    "provider": "Trans.eu",
    "provider_id": "trans_eu",
    "load_id": "401560",
    "origin": "Krakow, PL",
    "destination": "Berlin, DE",
    "price": "€1,200",
    "distance": "537 km",
    "trailer": "cooler",
    "adr": "Yes" if result.adr else "No",
    "loading_type": result.loading_type.upper(),
    "actions": ""  # buttons added by table widget
}
```

**Provider health indicators:**
- After search, map `provider_statuses` to health indicator display
- Update the status bar with provider count and last updated timestamp

**Search method signature to call:**
```python
results = self._api.search_loads(
    origin_location=origin_text,
    destination_location=dest_text,
    pickup_date_from=self._date_from.text(),
    pickup_date_to=self._date_to.text(),
    trailer_type=trailer_list,      # FIXED: list[str]
    adr_required=bool(adr_checked),
    weight_kg_min=float(weight_min) if weight_min else None,
    weight_kg_max=float(weight_max) if weight_max else None,
    price_min=float(price_min) if price_min else None,
    distance_km_max=float(dist_max) if dist_max else None,
    loading_type=loading_type_val,
    loading_country=loading_country_val,
    delivery_country=delivery_country_val,
    sort_by=sort_field,
    sort_order=sort_order,
    provider_ids=["trans_eu"] if self._trans_eu_only else None,
)
```

### Step 3.2 — Modify `ui/views/freight_exchange/load_detail_view.py`

Extend the detail view to show Trans.eu-specific fields when the source is a Trans.eu freight:

**Additional fields to display (in the info section or as a new "Freight Details" group):**
- `reference_number` — freight reference number (e.g., "FR/2025/04/03/2NPR")
- `publication_status` — publication status
- `contact_employees` — assigned employees from the freight

**Implementation approach:**
- Add a new method `display_freight_details(freight_data: dict)` that populates additional labels
- Extract these fields from `raw_payload` in the LoadSearchResult when provider is "trans_eu"
- Show them in a collapsible section below the KPI cards

### Step 3.3 — Modify `client/remote_freight_exchange.py` (minor additions)

Verify the `search_loads()` method already filters out None values (it does — line with `{k: v for k, v in kwargs.items() if v is not None}`). No changes needed, but add explicit type hints for clarity.

### Phase 3 Verification

| Test | What it proves |
|---|---|
| `test_search_view_wiring.py` — mock API call, verify table populated | Search works end-to-end in UI |
| `test_sort_field_mapping.py` — all 6 sort options map correctly | Sort works correctly |
| `test_trailer_type_as_list.py` — trailer sent as list | Trailer type field fixed |
| Manual: search Trans.eu with real connection → see real results | Full UX works |
| Manual: click "Import" on a result → trip created with correct fields | Import pipeline works |

---

## Phase 4: Webhooks + Background Sync

**Goal:** Trans.eu status changes propagate automatically to Operion. Background jobs keep tokens fresh and data in sync.

### Step 4.1 — Create `services/trans_eu/webhook_ingestion.py`

Webhook ingestion service that processes incoming Trans.eu events.

**Key components:**

1. **IP whitelist check** — only accept from `52.208.90.151`
2. **URL secret verification** — callback URL includes `?secret={company_uuid}`
3. **Idempotency check** — deduplicate by `trans_eu_event_id` (stored in `trans_eu_webhook_events` table)
4. **Event storage** — persist raw event to `trans_eu_webhook_events` with status
5. **Event routing** — dispatch to handler based on `event_name` prefix
6. **Dead letter queue** — on processing failure, store to `trans_eu_webhook_events_failed`

**Event handler routing:**

| Event prefix | Handler |
|---|---|
| `freights.*` | `FreightSyncService` |
| `freight_orders.*` | `OrderSyncService` |
| `transports.*` | `TransportSyncService` |
| `time_slot_management.*` | `DockSchedulerSyncService` |
| Other | Log and skip |

### Step 4.2 — Create `services/trans_eu/sync_service.py`

Service that updates internal Operion models in response to Trans.eu webhook events.

**Event → Action mappings:**

| Trans.eu event | Action |
|---|---|
| `freights.freight.create` | INSERT `FreightOffer` into `trans_eu_freight_offers` |
| `freights.freight.update` | UPDATE `FreightOffer`, set `externally_modified_at` |
| `freights.publication.activated` | Set `publication_status='active'` |
| `freights.publication.canceled` | Set `publication_status='finished'` |
| `freights.publication.finished` | Set `publication_status='finished'` |
| `freights.publication.accepted` | Set `status='accepted'`. Update linked Trip status. |
| `freight_orders.order.created` | INSERT `FreightOrder`. Notify dispatcher. |
| `freight_orders.order.delivery_was_confirmed` | UPDATE linked Trip → `Delivered` |
| `freight_orders.order.order_was_cancelled` | UPDATE linked Trip → `Cancelled` |
| `freight_orders.order.transports_was_finished` | UPDATE linked Trip → `Delivered` |
| `transports.transport.devices_set_changed` | UPDATE `TransportTask` truck/driver. Sync to Trip assignment. |

**Implementation approach:**
- Each handler is a static/class method
- Receives `company_id` and parsed `payload`
- Looks up local models via `source_provider_id='trans_eu'` + `source_reference_id`
- Updates fields and persists
- Logs all mutations

### Step 4.3 — Create `backend/celery_app/tasks/trans_eu_tasks.py`

Five Celery tasks matching the schedule entries from Phase 0.

**Task 1: `trans_eu_refresh_tokens`** (every 30 min)
- Scan `trans_eu_user_tokens` where `status='active'` and `expires_at < NOW() + 1 hour`
- For each: call `TransEuClient.refresh_token()`
- On success: update `access_token_encrypted`, `refresh_token_encrypted`, `expires_at`, `last_refreshed_at`
- On failure: set `status='needs_reauth'`

**Task 2: `trans_eu_sync_active_freights`** (every 10 min)
- Webhook fallback: poll Trans.eu for status changes on locally-active freights
- Query `trans_eu_freight_offers` where `status NOT IN ('closed', 'accepted')`
- For each: fetch current freight from Trans.eu via adapter
- Compare statuses, update local records if changed

**Task 3: `trans_eu_process_failed_webhooks`** (every 15 min)
- Query `trans_eu_webhook_events_failed` where `status='pending'` AND `next_retry_at <= NOW()`
- For each: re-process the event
- On success: move to `status='resolved'`
- On failure: increment `attempt_count`, set `next_retry_at` using retry schedule (1m→2m→4m→8m→16m→30m→1h→2h→4h→8h)
- After 10 attempts: set `status='failed_permanent'`

**Task 4: `trans_eu_health_check`** (every 5 min)
- For each company with active Trans.eu connection:
  - Get session via `ConnectionManagerService.get_session()`
  - Call `TransEuAdapter.test_connection()`
  - Update `last_health_check_status` and `last_health_check_at`
- On failure: set status to `degraded` or `down`

**Task 5: `trans_eu_cleanup_expired_sessions`** (daily 03:00)
- Delete or archive `trans_eu_user_tokens` where `status='revoked'` AND `last_refreshed_at < NOW() - 30 days`
- Archive old `trans_eu_webhook_events` (> 90 days) to reduce table size

**Celery task pattern (following existing `ocr_tasks.py`):**
```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def trans_eu_sync_active_freights(self, company_id: int = None):
    try:
        set_company_context(company_id)
        db = DatabaseManager(Config.DB_PATH)
        # ... business logic ...
    except Exception as exc:
        logger.error("trans_eu_sync_active_freights failed: %s", exc)
        raise self.retry(exc=exc)
```

### Step 4.4 — Modify `backend/api/v1/webhooks.py`

Add a Trans.eu handler to the existing `_dispatch_webhook()` function.

**Required changes:**
1. Add `"trans-eu"` to the dict that maps partner name → handler
2. Create `_handle_trans_eu_webhook(payload)` function
3. Extract `event_name`, `id`, `occurred_at`, `data` from payload
4. Extract `company_id` from the webhook URL path or from a lookup of the freight/order in the payload
5. Call `WebhookIngestionService.process_event(company_id, payload)`

**Trans.eu webhook payload format:**
```json
{
  "id": "87795",
  "event_name": "freights.proposal_request.accepted",
  "occurred_at": "2026-01-25T11:41:11+00:00",
  "data": {"price": 560.20, "author": "12665-1"}
}
```

**Note:** Trans.eu doesn't include `company_id` in the webhook payload. The `company_id` comes from the URL path: `POST /api/v1/webhooks/trans-eu/{company_id}?secret=...`. The existing webhook endpoint uses `{partner}` as the path param — for Trans.eu, we need `{partner}/{company_id}` or extract company_id from the Trans.eu event by looking up the freight/order in our local `FreightOffer` table.

**Simpler approach:** Make the Trans.eu webhook endpoint separate from the generic one, or extract `company_id` by looking up the freight_id/order_id from the event payload in our local tables.

### Phase 4 Verification

| Test | What it proves |
|---|---|
| `test_webhook_ingestion.py` — valid webhook, duplicate, invalid IP | Ingestion pipeline works |
| `test_webhook_sync.py` — freight update, order created, delivery confirmed | Sync service updates models |
| `test_dead_letter_queue.py` — failure → DLQ, retry schedule | DLQ works |
| `test_celery_tasks.py` — token refresh, health check | Celery tasks function |
| Manual: send test webhook → check FreightOffer updated | End-to-end webhook flow |

---

## Dependency Graph

```
Phase 2 (OAuth) ─── can start immediately
    │
    ├── Step 2.1 (loopback server) — independent
    ├── Step 2.2 (connect view) — depends on 2.1
    ├── Step 2.3 (backend endpoint) — depends on Phase A connection manager
    └── Step 2.4 (remote client) — depends on 2.3

Phase 3 (UI) ─── depends on Phase 2 (needs OAuth for real searches)
    │
    ├── Step 3.1 (search view) — depends on Phase A adapter + Phase 2 client
    ├── Step 3.2 (detail view) — independent of 3.1 (can run parallel)
    └── Step 3.3 (remote client) — depends on 2.4

Phase 4 (Webhooks) ─── can start in parallel with Phase 3
    │
    ├── Step 4.1 (webhook ingestion) — depends on Phase A models/tables
    ├── Step 4.2 (sync service) — depends on 4.1
    ├── Step 4.3 (celery tasks) — depends on Phase A Celery wiring + 4.2
    └── Step 4.4 (webhook endpoint) — depends on 4.1
```

## Parallelization Opportunities

| Wave | Tasks | Can run in parallel |
|---|---|---|
| **Wave 1** | 2.1 (loopback) + 2.3 (backend endpoint) + 4.1 (webhook ingestion) | Yes — all independent |
| **Wave 2** | 2.2 (connect view) + 2.4 (remote client) + 4.2 (sync service) | Yes — 2.2 depends on 2.1, 2.4 on 2.3, 4.2 on 4.1 |
| **Wave 3** | 3.1 (search view) + 3.2 (detail view) + 4.3 (celery tasks) + 4.4 (webhook endpoint) | Yes — 3.1 depends on Phase 2 complete, 3.2 independent, 4.3 depends on 4.2, 4.4 depends on 4.1 |

## Estimated Effort

| Phase | Steps | Estimate |
|---|---|---|
| Phase 2 (OAuth) | 4 steps | 2-3 days |
| Phase 3 (UI) | 3 steps | 2-3 days |
| Phase 4 (Webhooks) | 4 steps | 3-4 days |
| Testing + Bug Sweep | Per phase | Included |
| **Total** | **11 steps** | **7-10 days** |

## Verification Checklist

- [ ] User clicks "Connect Trans.eu" → browser opens → login → connected status shown
- [ ] Token expiry displayed correctly in connect view
- [ ] `connect_trans_eu` API endpoint returns valid response
- [ ] Search with Trans.eu filters returns real results in the table
- [ ] Sort field mapping produces correct API parameters
- [ ] Trailer type sent as list, not string
- [ ] Load detail view shows Trans.eu-specific fields
- [ ] Webhook received → event stored → FreightOffer updated
- [ ] Duplicate webhook detected and skipped
- [ ] Dead letter queue receives failed events
- [ ] Celery token refresh task runs on schedule
- [ ] Celery health check updates connection status
- [ ] Existing tests still pass (no regressions)
- [ ] Provider-agnostic files still unchanged (search, import, evaluation, fleet matcher, adapter ABC, registry)
