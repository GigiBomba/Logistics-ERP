# Trans.eu → Operion Integration Architecture

> **Status:** Architectural Design  
> **Date:** 2026-07-16  
> **Prerequisite:** `TransEU_KnowledgeBase.md`  
> **Operion Blueprint:** `Operion_Freight_Exchange_Module_Blueprint.md`  
> **Principle:** Operion MUST remain provider-agnostic. Trans.eu is a provider, not the platform.

---

## Table of Contents

1. [Architectural Principle](#1-architectural-principle)
2. [System Overview](#2-system-overview)
3. [Provider Abstraction](#3-provider-abstraction)
4. [Authentication Architecture](#4-authentication-architecture)
5. [Internal Domain Model](#5-internal-domain-model)
6. [Service Boundaries](#6-service-boundaries)
7. [Synchronization Strategy](#7-synchronization-strategy)
8. [Event Flow](#8-event-flow)
9. [Module Impact Analysis](#9-module-impact-analysis)
10. [Data Ownership Model](#10-data-ownership-model)
11. [Caching Strategy](#11-caching-strategy)
12. [Conflict Resolution](#12-conflict-resolution)
13. [Error Handling & Retries](#13-error-handling--retries)
14. [Rate Limiting](#14-rate-limiting)
15. [Webhook Architecture](#15-webhook-architecture)
16. [Background Jobs](#16-background-jobs)
17. [Dependency Inversion](#17-dependency-inversion)
18. [Scalability & Maintainability](#18-scalability--maintainability)
19. [Phased Rollout Plan](#19-phased-rollout-plan)
20. [Open Decisions Requiring User Input](#20-open-decisions-requiring-user-input)

---

## 1. Architectural Principle

> **Operion exposes its own standardized freight exchange infrastructure. Every provider (Trans.eu, TIMOCOM, future) translates between its API and Operion's standardized models. The rest of the application must never know which provider is currently connected.**

This follows the same adapter pattern already established for Live Tracking (Wialon, Frotcom, Traccar behind one common interface) and the existing freight exchange subsystem (TIMOCOM adapter behind `FreightProviderAdapter`).

Adding Trans.eu should mean writing one adapter class plus service classes for Trans.eu-specific capabilities. Nothing in the Search Engine, Import Pipeline, Evaluation Engine, Fleet Matcher, or any downstream module changes.

**Validation gate:** If adding Trans.eu requires touching any module above the adapter layer, the abstraction has failed.

---

## 2. System Overview

```
                        OPERION APPLICATION LAYER
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │  AI Copilot  │  Dispatch  │  Route Planner  │  Fleet  │  Analytics  │  ... │
 └──────────────────────────────┬───────────────────────────────────────────────┘
                                │  All modules consume Operion's internal models
                                │  Zero provider awareness
 ┌──────────────────────────────┴───────────────────────────────────────────────┐
 │                DETERMINISTIC SERVICE LAYER                                    │
 │  Search Engine  │  Import Pipeline  │  Evaluation Engine  │  Fleet Matcher   │
 └──────────────────────────────┬───────────────────────────────────────────────┘
                                │  Provider-agnostic by construction
 ┌──────────────────────────────┴───────────────────────────────────────────────┐
 │                   PROVIDER ADAPTER LAYER                                      │
 │  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────┐                 │
 │  │TransEuAdapter    │  │TimocomAdapter    │  │ Future...   │                 │
 │  │(search + import) │  │(search + import) │  │             │                 │
 │  └────────┬─────────┘  └────────┬─────────┘  └─────────────┘                 │
 │  ┌────────┴──────────────────────────────────────────┐                       │
 │  │  TransEu-SPECIFIC SERVICE CLASSES                  │                       │
 │  │  FreightService  NegotiationService  OrderService  │                       │
 │  │  TransportService  DockSchedulerService            │                       │
 │  │  VehicleExchangeService  ContractService           │                       │
 │  │  PartnerService                                     │                       │
 │  └────────────────────────────────────────────────────┘                       │
 └──────────────────────────────┬───────────────────────────────────────────────┘
                                │
 ┌──────────────────────────────┴───────────────────────────────────────────────┐
 │  INFRASTRUCTURE LAYER                                                         │
 │  Webhook Ingestion  │  Rate Limiter  │  Circuit Breaker  │  Token Manager   │
 │  Celery Tasks       │  Redis Cache  │  Dead Letter Queue │  Audit Trail     │
 └──────────────────────────────────────────────────────────────────────────────┘
```

**Key invariant:** The adapter layer is the ONLY layer that imports Trans.eu-specific code. Everything above imports only Operion's internal models and services.

---

## 3. Provider Abstraction

### 3.1 Two-Layer Adapter Design

Trans.eu's API is significantly richer than TIMOCOM's. It includes capabilities (publication, negotiation, orders, transports, dock scheduler, contracts, vehicle exchange) that the existing `FreightProviderAdapter` ABC (6 methods: authenticate, refresh_session, test_connection, search_loads, get_load, capabilities) does not cover.

**Decision:** Use a two-layer strategy:

| Layer | Purpose | Interface |
|---|---|---|
| **Layer 1: `TransEuAdapter`** | Implements `FreightProviderAdapter` for the read/search/import path. Plugs into the existing Search Engine, Import Pipeline, Evaluation Engine, and Fleet Matcher with zero changes to those modules. | Extends `FreightProviderAdapter` ABC |
| **Layer 2: Trans.eu Domain Services** | Trans.eu-specific capabilities beyond search/import. Publication, negotiation, orders, transports, dock scheduler, contracts, vehicle exchange, partners. | Independent service classes, NOT under the adapter ABC |

**Rationale:** The existing `FreightProviderAdapter` was designed for "find loads on an external exchange and import them." It was NOT designed for bidirectional publishing, negotiation, order lifecycle management, real-time transport monitoring, or dock scheduling. Attempting to force these into the existing ABC would create a bloated, lowest-common-denominator interface that future providers couldn't reasonably implement.

When a second provider (e.g., Teleroute) adds similar rich functionality, generalize the relevant domain services into provider-agnostic interfaces at that point. Until then, YAGNI.

### 3.2 What the Adapter Covers (Layer 1)

| Trans.eu API | Adapter Method | Normalized Output |
|---|---|---|
| `GET /freights-api/v1/freights` (search) | `search_loads()` | `List[LoadSearchResult]` |
| `GET /freights-api/v1/freights/{id}` (detail) | `get_load()` | `LoadSearchResult` |
| OAuth token flow + refresh | `authenticate()` / `refresh_session()` | `ProviderSession` |
| Connection health | `test_connection()` | Health status |
| Provider metadata | `capabilities()` | `ProviderCapabilities` |

### 3.3 What the Domain Services Cover (Layer 2)

| Trans.eu Capability | Operion Domain Service |
|---|---|
| Freight CRUD, 7 publication methods, archive, internal notes | `TransEuFreightService` |
| Negotiation (offers, proposals, accept/reject/negotiate/withdraw/takeover) | `TransEuNegotiationService` |
| Transport orders (create, confirm, cancel, archive, conditions) | `TransEuOrderService` |
| Transports in realization (list, detail, monitoring, trace) | `TransEuTransportService` |
| Dock scheduler (warehouses, time windows, announcements) | `TransEuDockSchedulerService` |
| Vehicle exchange offers | `TransEuVehicleExchangeService` |
| Routes & contracts | `TransEuContractService` |
| Partners, fleet, company details | `TransEuPartnerService` |

---

## 4. Authentication Architecture

### 4.1 The OAuth Per-User Constraint

Trans.eu uses **OAuth 2.0 Authorization Code flow** where a human user must log in interactively on the Trans.eu Platform. This is fundamentally different from TIMOCOM's `client_credentials` flow (system-level API key).

**Implication:** Trans.eu tokens are user-scoped, not company-scoped. Each Operion dispatcher who uses Trans.eu must have their own OAuth token.

### 4.2 Token Storage Model

| Storage Level | Purpose |
|---|---|
| `trans_eu_user_tokens` table | Encrypted per-user tokens (access_token, refresh_token, api_key, client_id/client_secret, scope, expires_at, status) |
| Company service token | Optional: a single dedicated Trans.eu account for automated operations (scheduled searches, webhook ingestion, health checks). Stored in the same table with a marker. |

### 4.3 OAuth Flow

```
Desktop Client Flow:
  1. User clicks "Connect Trans.eu" in Operion
  2. Operion opens Trans.eu OAuth URL in system browser
  3. User logs in on Trans.eu Platform
  4. Trans.eu redirects to localhost:{port}/trans-eu/callback with authorization_code
  5. Local HTTP server in desktop client captures the code
  6. Desktop client sends code to Operion backend
  7. Backend exchanges code for tokens (access + refresh)
  8. Backend stores encrypted tokens in trans_eu_user_tokens
  9. User is redirected back to Operion with success state

Web Portal Flow (if applicable):
  1-3: Same
  4. Trans.eu redirects to https://operion.com/api/v1/trans-eu/oauth/callback
  5. Backend exchanges code for tokens
  6. User redirected to Operion portal
```

### 4.4 Token Refresh Strategy

| Trigger | Mechanism | Failure Handling |
|---|---|---|
| **On-demand (PRIMARY)** | Before any API call, check if token is within 10% of TTL. If so, refresh synchronously before proceeding. | If refresh returns 401 → mark token `needs_reauth`, notify user. |
| **Scheduled background (SECONDARY)** | Celery beat every 30 min scans tokens expiring within 1h. Proactively refreshes. | If refresh fails → mark `needs_reauth` on next attempt. User notified. |
| **User offline** | Token expires naturally. Background tasks use company service token if available. | User sees "reauthorization required" when they return. Guided through re-authentication flow. |

### 4.5 Multi-User Token Model

| Scenario | Token Used |
|---|---|
| User with active token performs a search | User's own token |
| User without token tries to search | Company service token (if configured). Otherwise: prompt to connect. |
| Background sync job (freight status poller) | Company service token |
| Webhook ingestion (read-only status updates) | Company service token or dedicated webhook endpoint token |
| Multi-user company-wide search across providers | Parallel: each user's token for their own Trans.eu search scope. Results merged. |

### 4.6 Security

- Tokens encrypted at rest (AES-256-GCM) using existing encrypted credential store
- `Api-key` header never stored in plaintext — encrypted alongside tokens
- Refresh token rotation: each refresh returns new refresh token, old one invalidated
- Audit log records all token operations (create, refresh, revoke, expire)

---

## 5. Internal Domain Model

### 5.1 Mapping Trans.eu Concepts to Operion Concepts

| Trans.eu Concept | Operion Internal Concept | New or Existing? | Decision Rationale |
|---|---|---|---|
| **Freight (search result)** | `LoadSearchResult` | Existing | Already handles origin, destination, dates, price, trailer, ADR. Extra fields in `raw_payload`. |
| **Freight (full object)** | `FreightOffer` | NEW | Includes spots, loads, requirements, publication state, contact employees, internal note. Needed for publication management and negotiation. |
| **Freight Publication** | `FreightOffer.publication` (embedded) | Embedded | Publication type, status, end reason, price — sub-fields of the freight, not a standalone entity. |
| **Negotiation/Offer** | `NegotiationOffer` | NEW | Tracks offer_id, freight_id, price, status (acceptation/negotiation/rejection/renouncement), proposer_company. |
| **Transport Order** | `Trip` (existing) + `FreightOrder` (NEW) | Hybrid | The trip is the canonical record (dispatch, invoicing). `FreightOrder` links Trans.eu order to the Operion trip, adding Trans.eu-specific state (order_number, costs, execution data). |
| **Transport Task** | `Trip` (existing) + `TransportTask` (NEW) | Hybrid | Enriches the trip with monitoring events, GPS trace (GeoJSON), operation confirmations, driver/vehicle data. |
| **Vehicle Exchange Offer** | `VehicleOffer` | NEW | Not an Operion vehicle — it's an offer to provide transport capacity. Distinct concept. |
| **Dock Scheduler Objects** | `DockWarehouse`, `DockTimeWindow`, `DockAnnouncement` | NEW | Warehouse/ramp configuration, booking slots, carrier arrivals. Potentially linkable to trips. |
| **Route Contract** | `ProviderContract` | NEW | Fixed or flexible contract for recurring freight. Could auto-generate trips on schedule. |
| **Partner/Contractor** | `Client` (existing) + `ProviderPartner` (NEW) | Hybrid | Trans.eu partners synced as Operion clients. Extra metadata (cooperation status, groups, Trans.eu partner_id) in linking table. |
| **Fleet Vehicle** | `Vehicle` (existing) + `ProviderVehicle` (NEW) | Hybrid | Trans.eu fleet vehicles synced as Operion vehicles. Extra Trans.eu-specific fields in linking table. |
| **Internal Note** | `FreightOffer.internal_note` | Embedded | Max 500 chars, one per freight. Simple enough to embed. |
| **Attachment** | `Document` (existing) | Existing | Trans.eu attachments imported as Operion documents, linked to trip/order. |

### 5.2 Non-Mapped Trans.eu Concepts

These Trans.eu concepts have NO Operion equivalent. They are stored in their own tables as Trans.eu-specific data, accessible only via Trans.eu domain services:

- `DockWarehouse`, `DockTimeWindow`, `DockAnnouncement`
- `ProviderContract` (route contracts)
- `VehicleOffer` (vehicle exchange offers)
- Negotiation state machine (specific to Trans.eu's negotiation flow)

**Design rule:** Do NOT try to generalize these into provider-agnostic concepts until a second provider demonstrates need. Premature abstraction creates complexity without value.

### 5.3 Structural Mismatches

| Trans.eu Structure | Operion Structure | Resolution |
|---|---|---|
| Multi-spot freights (`spots[]` with loading/unloading operations) | Single origin/destination in `LoadSearchResult` | Search results: use first spot's address as origin, last as destination. Full `FreightOffer`: store all spots. |
| Multiple cargo items (`loads[]` with individual types/weights) | Single `weight_kg` in search result | Search: sum weights. Full import: create individual trip load items from loads array. |
| `transit_time` (minutes) | `estimated_duration_hours` | Map `transit_time / 60` to hours. Evaluation engine prefers provider-provided estimate over route calculation when available. |
| V2 APIs for some endpoints, V1 for others | Single adapter | Adapter handles both versions. Upstream modules don't know. |

---

## 6. Service Boundaries

### 6.1 Service Layer Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  SEARCH & IMPORT (Provider-Agnostic)                           │
│  ─ Already exists. Zero changes for Trans.eu.                  │
│                                                                │
│  SearchEngineService → searches across all connected providers │
│  ImportPipelineService → maps any provider's load → Trip       │
│  EvaluationEngineService → evaluates any provider's load       │
│  FleetMatcherService → matches trucks to any provider's load   │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  CORE TRANS.EU OPERATIONS (Trans.eu-Specific)                  │
│                                                                │
│  TransEuFreightService → CRUD, publication, archive           │
│  TransEuNegotiationService → offers, proposals, lifecycle      │
│  TransEuOrderService → order creation, confirmations, costs    │
│  TransEuTransportService → monitoring, trace, events           │
│  TransEuDockSchedulerService → warehouses, windows, announce.  │
│  TransEuVehicleExchangeService → vehicle offers                │
│  TransEuContractService → routes, fixed/flexible contracts     │
│  TransEuPartnerService → partners, groups, cooperation         │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE (Shared Across Providers)                      │
│                                                                │
│  ConnectionManagerService → manages provider sessions          │
│  TokenManagerService → Trans.eu OAuth token lifecycle          │
│  WebhookIngestionService → receive, validate, route events     │
│  RateLimiterService → per-provider, per-endpoint rate limiting │
│  CircuitBreakerService → per-provider failure isolation        │
│  FreightSyncService → reconcile local state with provider      │
└────────────────────────────────────────────────────────────────┘
```

### 6.2 Dependency Direction

```
Application Layer (UI, Copilot, Analytics)
        │ depends on (imports)
        ▼
Operion Internal Services (search, import, evaluation, dispatch, invoicing)
        │ these services NEVER import any Trans.eu-specific code
        ▼
Provider Adapter Layer (TransEuAdapter implements FreightProviderAdapter)
        │ depends on
        ▼
Trans.eu Domain Services (TransEuFreightService, etc.)
        │ depends on
        ▼
Infrastructure (ConnectionManager, TokenManager, RateLimiter, CircuitBreaker)
        │ depends on
        ▼
Trans.eu API (HTTP calls)
```

**Dependency inversion:** The application layer depends on abstractions (internal models, service interfaces). The adapter layer implements those abstractions. Trans.eu-specific code is injected at startup and never leaked upward.

### 6.3 Boundary Enforcement

| Boundary | Rule |
|---|---|
| Adapter → Provider | The adapter is the ONLY class that makes HTTP calls to Trans.eu |
| Adapter → Internal Models | The adapter translates Trans.eu JSON → Operion Pydantic models |
| Internal Services → Provider | Internal services NEVER import Trans.eu-specific types |
| Internal Services → Adapter | Internal services call the adapter interface, never a Trans.eu-specific class |
| UI → Provider | The UI displays provider_id as a string tag. No provider-specific UI logic. |

---

## 7. Synchronization Strategy

### 7.1 Primary: Webhooks

Trans.eu sends webhooks to registered callback URLs when events occur. Webhooks are the PRIMARY synchronization mechanism because they provide near-real-time updates with zero polling overhead.

**Data flow:**
```
Trans.eu Platform event occurs
        │
        ▼ POST to callback URL
Operion Webhook Ingestion Service
        │
        ├─ Validate (IP whitelist, URL secret, event idempotency)
        ├─ Store raw event in trans_eu_webhook_events
        ├─ Route to appropriate handler (FreightSync / OrderSync / TransportSync)
        │       │
        │       ├─ Update internal models (FreightOffer, FreightOrder, TransportTask)
        │       ├─ Update linked Trips (if imported)
        │       └─ Publish to EventBus for cross-module listeners
        │
        └─ On failure → store in trans_eu_webhook_events_failed (dead letter)
```

### 7.2 Secondary: Polling (Webhook Fallback)

Polling serves as the FALLBACK for detecting events that were missed (Trans.eu couldn't deliver the webhook, Operion was down, network failure).

| Polled Data | Frequency | Purpose |
|---|---|---|
| Active freights (status changes) | Every 10 minutes | Detect freight acceptances/rejections/cancellations not received via webhook |
| Active transport orders | Every 10 minutes | Detect order confirmations/status changes |
| Vehicle exchange offers | Every 15 minutes | Refresh offer list |
| Token expiry | Every 30 minutes | Proactive refresh |

### 7.3 Reconciliation

A daily reconciliation job at 03:00 UTC cross-checks local state against Trans.eu for all active objects. Discrepancies are logged and flagged for manual review.

### 7.4 Bidirectional Sync for Imported Trips

When a Trans.eu freight is imported as an Operion trip:
1. Trip records `source='freight_exchange'`, `source_provider_id='trans_eu'`, `source_reference_id='<freight_id>'`
2. A `FreightOrder` record links the Trans.eu order to the Operion trip

**Direction: Trans.eu → Operion (automatic)**
- Order status changes → Trip status updates
- Transport task events → Trip assignment updates
- Delivery confirmed → Trip marked Delivered

**Direction: Operion → Trans.eu (explicit only)**
- Operion DOES NOT automatically sync changes back to Trans.eu
- Explicit actions only: publish freight, negotiate, accept offer, create order
- If a dispatcher changes truck/driver on an imported trip, it stays local unless explicitly published to Trans.eu

**Rationale:** Trans.eu is the source of truth for freight/order state. Operion is the source of truth for internal operations. Automatic bidirectional sync creates unresolvable conflicts and violates the single-source-of-truth principle.

---

## 8. Event Flow

### 8.1 Event Categories

| Category | Event Examples | Internal Action |
|---|---|---|
| **Freight lifecycle** | `freights.freight.create`, `freights.freight.update`, `freights.publication.activated`, `freights.publication.finished`, `freights.publication.canceled` | Upsert/update `FreightOffer`. Notify user of status changes. |
| **Negotiation** | `freights.proposal_request.created`, `freights.proposal_request.accepted`, `freights.proposal_request.negotiated`, `freights.proposal_request.rejected`, `freights.proposal_request.renounced`, `freights.proposal_request.withdrawn` | Create/update `NegotiationOffer`. Update `FreightOffer.status` on acceptance. Notify dispatcher. |
| **Order lifecycle** | `freight_orders.order.created`, `freight_orders.order.delivery_was_confirmed`, `freight_orders.order.order_was_cancelled`, `freight_orders.order.transports_was_finished`, `freight_orders.order.order_was_accepted_by_contract` | Create/update `FreightOrder`. Update linked Trip status. |
| **Transport monitoring** | `transports.transport.devices_set_changed` | Update `TransportTask` truck/driver. Update linked Trip assignment. |
| **Dock scheduler** | `time_slot_management.announcement.*`, `time_slot_management.time_window.*` | Create/update/delete `DockAnnouncement` / `DockTimeWindow`. |

### 8.2 Event → Notification Mapping

Webhook events propagate through the internal EventBus. Any module can subscribe:

| Notification | Trigger Event | Recipient |
|---|---|---|
| "New offer received on freight FR-123" | `freights.proposal_request.created` | Dispatcher assigned to freight |
| "Freight FR-123 was accepted by Carrier X at price Y" | `freights.proposal_request.accepted` | Freight publisher |
| "Your proposal on freight FR-123 was rejected" | `freights.proposal_request.rejected` | Carrier who sent offer |
| "Order 2025/05/13/1 delivery confirmed" | `freight_orders.order.delivery_was_confirmed` | Shipper + linked trip stakeholders |
| "Trans.eu token expiring — reauthorize now" | Token status → `needs_reauth` | Affected user |

### 8.3 Complete Event Inventory

For the full list of Trans.eu webhook events and their payloads, see `TransEU_KnowledgeBase.md` §8 (Freight Events: 18 events, Order Events: 11 events, Transport Events: 1 event, Dock Scheduler Events: 6 events).

---

## 9. Module Impact Analysis

### 9.1 AI Copilot → HIGH IMPACT

The Co-Pilot's tool layer needs new tools. Zero planner changes needed — it already routes to tools by capability.

| New Tool | Delegates To | User Intent |
|---|---|---|
| `search_trans_eu_freights` | `TransEuAdapter.search_loads()` → Search Engine | "Find me loads on Trans.eu going from Poland to Germany" |
| `publish_to_trans_eu` | `TransEuFreightService` | "Publish this freight to Trans.eu exchange" |
| `negotiate_offer` | `TransEuNegotiationService` | "Counter-offer 450 EUR on this Trans.eu freight" |
| `accept_trans_eu_offer` | `TransEuNegotiationService` | "Accept the carrier's offer on freight FR-123" |
| `create_transport_order` | `TransEuOrderService` | "Create a transport order from freight FR-123" |
| `monitor_transport` | `TransEuTransportService` → TransportTask | "Show me the current position of transport TT-456" |
| `check_dock_schedule` | `TransEuDockSchedulerService` | "What time windows are available at warehouse W-789?" |

Existing `search_exchange_loads` tool already works with Trans.eu via the Search Engine — zero changes.

**Data ownership:** Trans.eu is source of truth for published freights. Operion owns trips and negotiations.

### 9.2 Route Planning → LOW IMPACT

Already handled by the Import Pipeline. Existing `_map_to_trip_create()` creates stops from origin/destination. For multi-spot Trans.eu freights, extend mapping to create a `TripStop` for each spot-operation. No RouteService changes.

**Data ownership:** Operion owns the route once imported from a freight.

### 9.3 Dispatch → LOW-MEDIUM IMPACT

- Trans.eu-sourced trips appear on the dispatch board (already works via `source_provider_id='trans_eu'`)
- When Trans.eu reports `devices_set_changed` (truck/driver assigned on Trans.eu Platform), sync to trip assignment
- New column `externally_managed: bool` on trips: when true, dispatch changes are read-only in Operion (Trans.eu owns the assignment)
- Trans.eu order amendments (change terms after acceptance) trigger dispatch review workflow

**Sync flow:** Webhook → update trip truck_id/driver_id → dispatch board refreshes.

### 9.4 Fleet Management → LOW

Vehicle exchange offers are a Trans.eu-only concept. Optional: display Trans.eu exchange demand alongside fleet data in the vehicle management view. No changes to core fleet model.

### 9.5 Analytics → LOW-MEDIUM

- `source_provider_id` becomes a dimension in analytics queries (filter by provider)
- Revenue-per-provider metric: group trips by source_provider_id
- Trans.eu-specific metrics: freight acceptance rate, negotiation success rate, publication-to-acceptance time
- No new tables needed — existing trip-based analytics capture provider-sourced trips

### 9.6 Documents/OCR → LOW

When importing a Trans.eu freight, check for attachments and offer to import them via the existing DocumentService. Trans.eu order invoices can be downloaded as documents.

### 9.7 Notifications → MEDIUM

New notification types corresponding to Trans.eu webhook events. Each event maps to one notification type, gated by user notification preferences. The existing NotificationCenter subscribes to EventBus events and dispatches accordingly.

### 9.8 Customer Portal → LOW (Out of Scope for Phase 1)

If a client is linked to a Trans.eu partner, optionally show loads published for them. No default changes.

### 9.9 Mobile App → NONE

Drivers see trips regardless of source. No changes needed. Transport monitoring data from Trans.eu enriches the same trip/status objects the mobile app reads.

### 9.10 Invoicing → LOW

No changes needed. Trans.eu-sourced trips generate invoices normally. Trans.eu payment terms (`deferred`, `payment_in_advance`, `payment_on_unloading`) map to Operion payment terms during import.

### 9.11 Tacho/Maintenance → NONE

Trans.eu doesn't expose tachograph or maintenance data for carriers.

### 9.12 Backend APIs → MEDIUM

New API endpoints needed:

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/trans-eu/oauth/start` | Initiate OAuth flow (returns redirect URL) |
| `POST /api/v1/trans-eu/oauth/callback` | Exchange authorization code for tokens |
| `GET /api/v1/trans-eu/status` | Connection status, token validity |
| `POST /api/v1/trans-eu/disconnect` | Revoke tokens, disconnect |
| `POST /api/v1/trans-eu/freights/publish` | Publish freight to Trans.eu |
| `POST /api/v1/trans-eu/freights/{id}/negotiate` | Negotiate on a freight |
| `POST /api/v1/trans-eu/orders/create` | Create transport order |
| `GET /api/v1/trans-eu/orders/{id}/status` | Get order status |
| `POST /api/v1/webhooks/trans-eu/{company_id}` | Receive Trans.eu webhook |

Existing freight exchange endpoints (`GET /api/v1/freight/providers`, search, import) already work with Trans.eu.

### 9.13 Database → MEDIUM

New tables required:

| Table | Purpose |
|---|---|
| `trans_eu_user_tokens` | Per-user OAuth tokens |
| `trans_eu_webhook_events` | Raw webhook events (idempotency check) |
| `trans_eu_webhook_events_failed` | Dead letter queue for failed webhook processing |
| `freight_offers` | Trans.eu freight objects (beyond search results) |
| `negotiation_offers` | Negotiation state per freight |
| `freight_orders` | Link Trans.eu orders to Operion trips |
| `transport_tasks` | Transport monitoring data linked to trips |
| `dock_warehouses`, `dock_time_windows`, `dock_announcements` | Dock scheduler objects |
| `provider_contracts` | Route contracts |
| `provider_partners` | Partner linking table |
| `provider_vehicles` | Vehicle linking table |

Modifications to existing tables:

| Table | Change |
|---|---|
| `freight_exchange_connections` | Add `user_id` field (nullable — company-level connections use NULL) |
| `trips` | Already has `source`, `source_provider_id`, `source_reference_id` — no change needed |
| `clients` | Optional: add `trans_eu_partner_id` for partner sync |

### 9.14 Future Providers → ARCHITECTURAL

The architecture explicitly supports adding future providers:

| To Add a New Provider | Work Required |
|---|---|
| Read-only search + import (like TIMOCOM) | One adapter implementing `FreightProviderAdapter` |
| Rich capabilities (like Trans.eu) | One adapter + domain service classes |
| Provider with yet-unknown capability | Extend domain services, then generalize when a second provider arrives |

**Validation:** If adding a third provider requires changing the adapter interface or any module above the adapter layer, the architecture has a leak.

---

## 10. Data Ownership Model

### 10.1 Single Source of Truth

| Data Domain | Source of Truth | Rationale |
|---|---|---|
| **Freight publication state** | Trans.eu | The exchange controls whether a freight is active, finished, or cancelled |
| **Freight content (route, requirements, load details)** | Trans.eu | The freight object lives on Trans.eu |
| **Negotiation state** | Trans.eu | Negotiation is a Trans.eu Platform feature |
| **Order state** | Trans.eu | The order lifecycle is managed on Trans.eu |
| **Transport monitoring** | Trans.eu | GPS telematics come from Trans.eu's monitoring system |
| **Dock scheduler** | Trans.eu | Warehouses, time windows, announcements are Trans.eu Platform features |
| **Trip (Operion)** | Operion | The trip is an Operion-internal concept. It may reference a Trans.eu freight/order but is independently managed |
| **Dispatch assignments** | Operion (for Operion-created trips) / Trans.eu (for Trans.eu-managed orders) | Depends on `externally_managed` flag |
| **Invoices** | Operion | Invoices are generated and managed within Operion |
| **Clients (partners)** | Operion | Operion owns the client record; Trans.eu partners are synced as clients but Operion is authoritative for internal data |
| **Documents** | Operion | Once imported, Operion owns the document |
| **Analytics** | Operion | Analytics are computed from Operion's data warehouse |

### 10.2 Synchronization Direction

```
Trans.eu ────────────► Operion      (webhooks: status changes, events)
Trans.eu ◄──────────── Operion      (API calls: publish, negotiate, create order)
Trans.eu ◄──╳──► Operion            (NO automatic bidirectional sync of edits)
```

**Rule:** Operion never automatically pushes edits back to Trans.eu. If a dispatcher changes a freight in Operion, the change stays local unless explicitly published.

---

## 11. Caching Strategy

### 11.1 Cache Tiers

| Tier | Technology | Purpose |
|---|---|---|
| L1: Search results | Redis (existing) | Cross-provider search result cache. Key: `freight:search:{company_id}:{provider_id}:{hash(filters)}`. TTL: 180s. |
| L2: Freight details | Redis | Individual freight detail cache. Key: `freight:detail:{provider_id}:{freight_id}`. TTL: 60s. |
| L3: Static/reference data | Redis | Company details, partner lists, fleet vehicles, exchange lists, warehouse info. TTL: 600-3600s depending on data volatility. |

### 11.2 Cache TTL by Data Type

| Data Type | TTL | Reasoning |
|---|---|---|
| Search results | 180s (3 min) | Freight offers change frequently on exchanges |
| Freight detail | 60s (1 min) | Near-real-time detail view |
| Vehicle exchange offers | 300s (5 min) | Moderate change frequency |
| Partners list | 600s (10 min) | Infrequent changes |
| Fleet vehicles | 600s (10 min) | Infrequent changes |
| Routes | 600s (10 min) | Semi-static |
| Contracts | 300s (5 min) | Contracts can be updated |
| Warehouses | 3600s (1 hour) | Static setup |
| Announcements | 60s (1 min) | Time-sensitive dock slots |
| Suggested locations | 3600s (1 hour) | Static company data |
| OAuth tokens | NEVER cached | Security-sensitive, time-bound |

### 11.3 Cache Invalidation

- **TTL-based only** for Phase 1. No active invalidation from webhooks.
- **Per-provider, not per-merged-result-set**, so a TIMOCOM cache hit doesn't force a redundant Trans.eu hit.
- Phase 2: webhook-driven invalidation (e.g., `freights.freight.update` → invalidate detail cache for that freight_id).

### 11.4 Cache-Aware Search

The Search Engine already handles `Cache-Control` and `ETag` via the existing caching layer. Trans.eu does not expose cache headers — Operion manages freshness via TTL.

---

## 12. Conflict Resolution

### 12.1 Freight Editing Conflict (Operion vs Trans.eu Web UI)

**Scenario:** User publishes freight via Operion, then edits it on Trans.eu Platform website.

| Step | Action |
|---|---|
| 1. Operion stores `last_known_updated_at` from Trans.eu's freight object |
| 2. Before any Operion-initiated update, re-fetch freight from Trans.eu |
| 3. Compare `current.updated_at` with `stored.updated_at` |
| 4. If current > stored → CONFLICT: block update, show user diff |
| 5. User chooses: [View Changes] [Overwrite] [Discard] |
| 6. Conflict logged in audit trail |

**Note:** Trans.eu may not expose `updated_at` on freight objects. Webhook event `occurred_at` serves as proxy. Verify with Trans.eu API.

### 12.2 Already-Accepted Conflict

**Scenario:** Operion user clicks "Accept" but freight was already accepted by another dispatcher on Trans.eu Platform.

**Resolution:**
- Trans.eu API returns error → catch at service layer
- Update local `FreightOffer.status` to 'accepted'
- Show user: "This freight was already accepted on Trans.eu Platform"
- Disable accept button, link to current status

### 12.3 Simultaneous Edit (Both Systems)

**Resolution:** Last-write-wins.
- If Operion's update reaches Trans.eu after web UI edit → Operion's change wins
- Webhook notifies Operion of the web UI edit → applied after pending update
- No silent data loss: pre-update check warns user of external modification

### 12.4 Phase 1 Simplification

For Phase 1: simple last-write-wins with notification. Full conflict UI (diff view, merge) deferred to Phase 2 when real usage patterns emerge.

---

## 13. Error Handling & Retries

### 13.1 Retry Classification

| Failure | HTTP Codes | Retryable? | Max Retries | Backoff |
|---|---|---|---|---|
| Rate limit | 429 | ✅ Yes | 5 | Respect `Retry-After` header or 1s base + jitter |
| Server error | 500, 502, 503, 504 | ✅ Yes | 3 | 1s → 2s → 4s + jitter |
| Network error | timeout, connection refused | ✅ Yes | 3 | 1s → 2s → 4s + jitter |
| Auth error | 401 | ⚠️ Special | 1 (token refresh, then fail) | N/A |
| Not found | 404 | ❌ No | 0 | N/A |
| Bad request / validation | 400, 422 | ❌ No | 0 | N/A |

### 13.2 Auth Error Special Handling

On 401:
1. Attempt token refresh ONCE using the refresh token
2. If refresh succeeds → retry the original request with new token
3. If refresh fails → mark token `needs_reauth`, return clear error to caller
4. Auth errors do NOT count toward circuit breaker failures

### 13.3 Circuit Breaker

Per-provider circuit breaker prevents cascading failures:

| State | Behavior |
|---|---|
| CLOSED | Normal operation. Requests flow to Trans.eu. |
| OPEN | All requests immediately fail with `CircuitBreakerOpenError` without hitting Trans.eu. Duration: 30s. |
| HALF_OPEN | One probe request allowed. If success → CLOSED. If failure → back to OPEN. |

Circuit breaker is per `(company_id, provider_id)`, stored in Redis.

**Trip threshold:** 5 consecutive failures → OPEN.

### 13.4 Webhook Dead Letter Queue

Failed webhook processing → `trans_eu_webhook_events_failed` table:

| Retry # | Delay | After max (10 attempts) |
|---|---|---|
| 1 | 1 min | Mark `failed_permanent` |
| 2 | 2 min | Alert admin |
| 3 | 4 min | |
| 4 | 8 min | |
| 5 | 16 min | |
| 6 | 30 min | |
| 7-10 | 1h, 2h, 4h, 8h | |

---

## 14. Rate Limiting

### 14.1 Two-Tier Token Bucket

| Bucket | Limit | Scope |
|---|---|---|
| Token endpoints | 5 RPS | Token exchange and refresh operations |
| API endpoints | 15 RPS | All other Trans.eu API calls |

Rate limiter uses Redis sliding window counters per `(company_id, endpoint_type, second_timestamp)`.

### 14.2 Multi-User Arbitration

When multiple Operion users share a company's Trans.eu connection:
- All users share the company's rate limit bucket
- Fair queuing: requests are processed in order; no user starves another
- If bucket empty: wait up to 200ms with jitter → queue (1s timeout) → 429 to caller

### 14.3 Rate Limit Cascading

When the 15 RPS API bucket is exhausted:
1. Rate limiter returns "no token available"
2. Calling service (Search Engine, etc.) backs off with exponential delay
3. UI shows "Trans.eu is currently busy. Retrying..." with countdown
4. Circuit breaker trip count is NOT incremented (rate limiting is expected, not a failure)

### 14.4 Clarification Needed

**ASK TRANS.EU:** Is rate limiting per OAuth token, per client_id, or per IP? If per client_id, all Operion companies sharing the same Trans.eu app credentials compete for the same bucket. This requires a deployment-level rate limiter coordinating across tenants.

---

## 15. Webhook Architecture

### 15.1 Endpoint Design

```
POST /api/v1/webhooks/trans-eu/{company_id}?secret={company_webhook_secret}
```

**Why a single endpoint per company?** Trans.eu requires a `callback_url` per object creation. Operion sets the same callback URL for all objects created by a given company. The `{company_id}` in the URL path identifies the tenant.

### 15.2 Verification

| Layer | Method |
|---|---|
| IP whitelist | Only accept from `52.208.90.151` (Trans.eu's callback IP) |
| URL secret | `?secret={randomly_generated_per_company_uuid}` embedded in callback URL |
| Payload validation | Verify the referenced freight/order/announcement ID belongs to this company |
| Idempotency | Deduplicate via Trans.eu's `id` field (event ID). Already-processed events are skipped. |

**Note:** Trans.eu does not currently mention HMAC signature verification. If they add it, upgrade accordingly.

### 15.3 Processing Pipeline

```
1. Receive POST → validate IP
2. Validate URL secret
3. Parse JSON body → extract event_name, id, occurred_at, data
4. Check idempotency: if event_id already processed → 200 OK, skip
5. Store raw event in trans_eu_webhook_events
6. Route to handler based on event_name prefix:
   - "freights.*" → FreightSyncService
   - "freight_orders.*" → OrderSyncService
   - "transports.*" → TransportSyncService
   - "time_slot_management.*" → DockSchedulerSyncService
7. On success → publish to EventBus for cross-module consumers
8. On failure → store in dead letter queue, return 200 OK (don't let Trans.eu retry indefinitely)
```

### 15.4 Why Return 200 OK on Processing Failure?

Trans.eu's webhook retry behavior is undocumented. If Operion returns 4xx/5xx, Trans.eu may retry (possibly indefinitely), creating duplicate processing pressure. Instead:
- Always return 200 OK to acknowledge receipt
- Store failed events in the dead letter queue
- Process failed events asynchronously via the dead letter processor

---

## 16. Background Jobs

### 16.1 New Celery Tasks

| Task | Schedule | Purpose | Retry? |
|---|---|---|---|
| `trans_eu_refresh_tokens` | Every 30 min | Scan tokens expiring within 1h, refresh proactively | No |
| `trans_eu_sync_active_freights` | Every 10 min | Poll Trans.eu for status changes on active freights (webhook fallback) | Yes, 3 retries @ 60s |
| `trans_eu_process_failed_webhooks` | Every 15 min | Retry failed webhook events from dead letter queue | No (individual events have their own retry) |
| `trans_eu_health_check` | Every 5 min | Ping Trans.eu connection, update health status | No |
| `trans_eu_sync_vehicle_exchange` | Every 15 min | Refresh vehicle exchange offers | Yes, 2 retries @ 30s |
| `trans_eu_reconcile_orders` | Every 1 hour | Cross-check local order statuses vs Trans.eu | Yes, 3 retries @ 120s |
| `trans_eu_cleanup_expired_sessions` | Daily 03:00 UTC | Delete/archive revoked tokens older than 30 days | No |

### 16.2 Celery Beat Integration

All tasks registered in `backend/celery_app/schedule.py` following existing conventions. Each task uses the established `bind=True, max_retries, default_retry_delay` pattern.

### 16.3 Distributed Task Safety

To prevent duplicate execution across Celery workers: Redis-based distributed locks (`SETNX` with TTL) on each task. If lock acquisition fails, task is skipped (another worker is handling it).

### 16.4 Tenant Context

Celery tasks set `company_id` ContextVar before any database access, consistent with the existing fix applied to OCR/document tasks (Phase 2 hardening). Tasks that iterate all companies set and clear context per iteration.

---

## 17. Dependency Inversion

### 17.1 What Depends on What

```
┌──────────────────────────────────────────────────────────────────┐
│  HIGH-LEVEL MODULES (Application / Domain Logic)                 │
│  ─ NEVER import Trans.eu-specific types                          │
│  ─ ONLY import: Operion internal models + provider abstractions  │
│                                                                  │
│  ├── SearchEngineService → depends on FreightProviderAdapter ABC │
│  ├── ImportPipelineService → depends on LoadSearchResult model   │
│  ├── EvaluationEngineService → depends on LoadSearchResult model │
│  ├── FleetMatcherService → depends on LoadSearchResult model     │
│  ├── TripService → depends on TripCreate, Trip models            │
│  ├── AnalyticsService → depends on Trip, Analytics models        │
│  └── Copilot tools → depends on Service classes (not providers)  │
└──────────────────────────────────────────────────────────────────┘
                              ▲
                              │ implements
                              │
┌──────────────────────────────────────────────────────────────────┐
│  LOW-LEVEL MODULES (Provider Implementations)                    │
│  ─ CAN import Trans.eu-specific types, SDKs, API shapes          │
│  ─ CAN import Operion internal models (to produce them)          │
│                                                                  │
│  ├── TransEuAdapter → implements FreightProviderAdapter          │
│  ├── TransEuFreightService → calls Trans.eu API, returns models  │
│  ├── TransEuNegotiationService → calls Trans.eu API              │
│  └── ... (other domain services)                                 │
└──────────────────────────────────────────────────────────────────┘
```

### 17.2 Injection

Trans.eu services are injected via the existing dependency injection system. The application layer receives abstractions, not concrete implementations. The concrete adapter is registered at startup.

### 17.3 Namespace Isolation

| Namespace | Contents | Importable By |
|---|---|---|
| `services/freight_exchange/adapter_base.py` | `FreightProviderAdapter` ABC, `LoadSearchResult` model | Any module |
| `services/freight_exchange/adapters/trans_eu.py` | `TransEuAdapter`, Trans.eu-specific translation logic | Trans.eu domain services, DI container |
| `services/trans_eu/` | All Trans.eu domain services | DI container, Copilot tools (via abstraction) |
| `models/freight_exchange_models.py` | Provider-agnostic models | Any module |
| `models/trans_eu_models.py` | Trans.eu-specific models | Trans.eu services only |

### 17.4 Testing Boundaries

| Test Type | What It Tests | Provider-Specific? |
|---|---|---|
| `test_adapter_base.py` | ABC enforcement, registry behavior | No — tests the abstract interface |
| `test_trans_eu_adapter.py` | TransEuAdapter against mock Trans.eu responses | Yes — mocks HTTP, tests translation |
| `test_search_engine.py` | Multi-provider search with fake adapters | No — uses fake adapters, tests merging |
| `test_import_parity.py` | Identical output from different providers | No — proves provider-agnostic |
| `test_evaluation.py` | Evaluation engine with loads tagged different providers | No — proves provider_id has zero influence |

---

## 18. Scalability & Maintainability

### 18.1 Horizontal Scaling

| Component | Scaling Model |
|---|---|
| FastAPI workers | Multiple workers behind load balancer. Rate limiter (Redis-based) coordinates across workers. |
| Celery workers | Multiple workers. Distributed locks prevent duplicate task execution. |
| Redis | Single instance sufficient for caching and rate limiting at current scale. Cluster for production. |
| PostgreSQL | Connection pooling (existing `PostgresConnectionPool`). |

### 18.2 Adding Future Providers

The architecture is explicitly designed for provider addition:

| Provider Capability Level | Work to Add |
|---|---|
| **Level 1: Search-only** (like TIMOCOM) | 1 adapter class implementing `FreightProviderAdapter`. Register via decorator. Zero changes to any other module. |
| **Level 2: Rich capabilities** (like Trans.eu) | 1 adapter + N domain service classes. May add new internal models if the provider exposes concepts not already modeled. |
| **Level 3: Novel capability** | Extend domain services for the new concept. When a second provider arrives with the same concept → generalize the domain service into a provider-agnostic service. |

**Architectural validation gate for each new provider:** Adding provider N must require changes ONLY to `services/freight_exchange/adapters/` and `services/{provider_name}/`. If any other file changes, the abstraction is leaking.

### 18.3 Code Organization

```
services/
├── freight_exchange/
│   ├── adapter_base.py          # Abstract interface (NEVER edited for new providers)
│   ├── registry.py              # Provider registry (edit to register new adapter)
│   ├── search.py                # Search engine (NEVER edited for new providers)
│   ├── evaluation.py            # Evaluation engine (NEVER edited)
│   ├── fleet_matcher.py         # Fleet matcher (NEVER edited)
│   ├── import_pipeline.py       # Import pipeline (NEVER edited)
│   ├── connection_manager.py    # Session management (minor edits for new grant types)
│   ├── health_monitor.py        # Provider health (NEVER edited)
│   ├── risk_scoring.py          # Risk scoring (NEVER edited)
│   └── adapters/
│       ├── timocom.py           # TIMOCOM adapter
│       └── trans_eu.py          # Trans.eu adapter (NEW)
│
├── trans_eu/                    # Trans.eu-specific domain services (NEW)
│   ├── freight_service.py
│   ├── negotiation_service.py
│   ├── order_service.py
│   ├── transport_service.py
│   ├── dock_scheduler_service.py
│   ├── vehicle_exchange_service.py
│   ├── contract_service.py
│   ├── partner_service.py
│   ├── webhook_ingestion.py
│   └── sync_service.py
│
└── infrastructure/              # Shared infrastructure
    ├── rate_limiter.py
    ├── circuit_breaker.py
    ├── token_manager.py
    └── webhook_dispatcher.py
```

### 18.4 Configuration

| Config Key | Purpose | Example |
|---|---|---|
| `TRANS_EU_CLIENT_ID` | Trans.eu OAuth client_id | `"example_app_client_id"` |
| `TRANS_EU_CLIENT_SECRET` | Encrypted Trans.eu OAuth client_secret | (encrypted) |
| `TRANS_EU_API_KEY` | Trans.eu app-level Api-key | `"unique_app_api_key"` |
| `TRANS_EU_BASE_URL` | Trans.eu API base URL | `"https://api.platform.trans.eu/ext/"` |
| `TRANS_EU_AUTH_URL` | Trans.eu OAuth server | `"https://auth.platform.trans.eu"` |
| `TRANS_EU_REDIRECT_URI` | OAuth callback URL | `"https://operion.com/api/v1/trans-eu/oauth/callback"` |
| `TRANS_EU_CALLBACK_URL_TEMPLATE` | Webhook callback URL template | `"https://operion.com/api/v1/webhooks/trans-eu/{company_id}?secret={secret}"` |
| `TRANS_EU_RATE_LIMIT_TOKEN_RPS` | Token endpoint rate limit | `5` |
| `TRANS_EU_RATE_LIMIT_API_RPS` | API endpoint rate limit | `15` |

---

## 19. Phased Rollout Plan

### Phase 1: Read-Only Search & Import (2-3 weeks)

**Goal:** TransEuAdapter implements `FreightProviderAdapter`. Dispatchers can search Trans.eu and import loads as trips.

| Deliverable | Gate |
|---|---|
| `TransEuAdapter` with authenticate, search_loads, get_load, test_connection, capabilities | Token acquisition + search works end-to-end |
| OAuth flow in desktop client (localhost loopback server) | User can connect Trans.eu account |
| Token storage + refresh | Session persists across app restarts |
| Search via existing freight exchange UI | Dispatcher sees Trans.eu loads alongside TIMOCOM |
| Import as trip | Trans.eu load → Operion trip parity test passes |
| Webhook ingestion for freight status updates | Imported trip status stays in sync |
| Rate limiter + circuit breaker | Graceful handling of Trans.eu API limits |

**Zero changes to:** Search Engine, Import Pipeline, Evaluation Engine, Fleet Matcher, Route Planner, Dispatch, Fleet, Analytics.

### Phase 2: Rich Operations (3-4 weeks)

**Goal:** Publish freights, negotiate, manage orders, monitor transports.

| Deliverable | Gate |
|---|---|
| Freight publication (all methods) | Dispatcher can publish freight to Trans.eu exchange |
| Negotiation (accept, counter, reject, withdraw, takeover) | Full negotiation flow works via API |
| Transport order creation from accepted freight | Order created, linked to Operion trip |
| Transport monitoring (list, detail, trace) | GPS position and GeoJSON trace visible in Operion |
| Webhook-driven sync for all object types | Status changes propagate automatically |
| Reconciliation job | Daily consistency check |

### Phase 3: Full Platform Integration (2-3 weeks)

**Goal:** Dock scheduler, vehicle exchange, contracts, Copilot tools.

| Deliverable | Gate |
|---|---|
| Dock scheduler (warehouse browsing, time windows, announcements) | Warehouse manager can view dock schedule |
| Vehicle exchange offers (post, view, manage) | Fleet manager can post vehicle availability |
| Route contracts (fixed + flexible) | Contract manager can create and balance contracts |
| AI Copilot tools | Co-Pilot can search, publish, and negotiate on Trans.eu |
| Notification integration | Users receive alerts for Trans.eu events |
| Analytics integration | Trans.eu-sourced trips appear in reports with provider metrics |

### Phase 4: Polish & Scale (1-2 weeks)

| Deliverable | Gate |
|---|---|
| Conflict resolution UI | Users can resolve edit conflicts |
| Cache optimization | Response times under 500ms for cached searches |
| Provider-agnostic validation gate | Second fake provider added → zero changes above adapter layer |
| Performance testing | Sustained 15 RPS with multiple users |

---

## 20. Open Decisions Requiring User Input

### 20.1 OAuth Flow for Desktop Client

**Question:** Should the OAuth flow use a local loopback server in the PySide6 desktop client (port 19999), or should all OAuth happen in a web-based Operion portal?

**Recommendation:** Local loopback server in desktop client. It keeps the flow entirely within the user's environment, doesn't require a publicly accessible Operion instance, and matches OAuth best practices for native apps (RFC 8252). However, Firefox 128+ and Chrome 131+ restrict localhost redirects — a fallback (custom URI scheme `operion://trans-eu/callback`) may be needed.

### 20.2 Token Sharing Model

**Question:** Require every dispatcher to have their own Trans.eu OAuth token, or allow sharing a "pool" of tokens from a few authenticated accounts?

**Recommendation:** Per-user tokens for any user who actively searches/publishes. Company service token for background operations. This is:
- More secure (least privilege per user)
- Auditable (every action traced to a specific user)
- Compliant with Trans.eu's intent (OAuth Authorization Code implies per-user)
- But adds onboarding friction (every dispatcher must connect)

### 20.3 Automatic Trip Creation from Orders

**Question:** When a `freight_orders.order.created` webhook arrives (someone created an order on Trans.eu Platform), should Operion automatically create a trip, or wait for explicit dispatcher import?

**Recommendation:** Wait for explicit import. Automatic trip creation would clutter the trip list with orders the dispatcher may not want, and the pricing/route data on the order may be incomplete. Show a notification: "New order created on Trans.eu: #2025/05/13/1. [Import as Trip]"

### 20.4 Unknown Webhook Objects

**Question:** Should webhook events referencing objects not in our local database be silently dropped or logged?

**Recommendation:** Log at INFO level (not error). A webhook referencing an unknown freight_id is normal — it may be a freight managed entirely on the Trans.eu Platform by another dispatcher, not created via Operion. Only alert if the event references an object that WAS created via Operion but can't be found (indicating a sync bug).

### 20.5 Rate Limit Clarification

**ASK TRANS.EU:** Is the 15 RPS rate limit per OAuth token, per client_id, or per IP address? This determines whether we need per-tenant or deployment-level rate limiting.

### 20.6 Freight Updated-At Field

**VERIFY WITH TRANS.EU API:** Do freight objects include an `updated_at` timestamp? Is there ETag support for optimistic concurrency? If not, use `occurred_at` from the most recent webhook event as the proxy for "last modified."

### 20.7 Conflict UI in Phase 1

**Question:** Implement full conflict resolution UI (diff view) in Phase 1, or start with "last-write-wins + silent sync + notification" and add conflict UI in Phase 2?

**Recommendation:** Start simple (Phase 1: notification + simple overwrite/discard prompt). Full diff UI is complexity that should be driven by real conflict frequency data from Phase 1 usage.

---

## Appendix A: Trans.eu Rate Limit Reference

| Endpoint Type | Limit | HTTP Response |
|---|---|---|
| Token endpoints (`/ext/auth-api/accounts/token`) | 5 RPS | 429 Too Many Requests |
| All other API endpoints | 15 RPS | 429 Too Many Requests |

## Appendix B: Callback IP Whitelist

| Source | IP |
|---|---|
| Trans.eu callback server | `52.208.90.151` |

## Appendix C: OAuth Endpoints

| Purpose | URL |
|---|---|
| Authorization (user login) | `https://auth.platform.trans.eu/oauth2/auth` |
| Token exchange | `https://api.platform.trans.eu/ext/auth-api/accounts/token` |
| Token refresh | `https://api.platform.trans.eu/ext/auth-api/accounts/token` (grant_type=refresh_token) |

## Appendix D: Related Documents

| Document | Purpose |
|---|---|
| `TransEU_KnowledgeBase.md` | Complete Trans.eu API reference (endpoints, schemas, enums, webhooks) |
| `Operion_Freight_Exchange_Module_Blueprint.md` | Provider-agnostic freight exchange architecture |
| `ARCHITECTURALREWORK.md` | Operion system architecture |
| `TIMOCOM_READINESS_REPORT.md` | Enterprise readiness assessment |
| `AI_READINESS_REPORT.md` | AI/automation readiness |
