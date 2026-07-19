# Trans.eu API Knowledge Base

> **Generated:** 2026-07-16  
> **Sources:** OpenAPI 3.0.1 YAML spec (21,817 lines) + Web documentation + Full scraped docs (31,996 lines)  
> **Spec Version:** 1.0.0 (YAML dated January 2025)  
> **Base URL:** `https://api.platform.trans.eu/ext/`  
> **Auth Server:** `https://auth.platform.trans.eu`  
> **Company:** Trans.eu Group S.A., Racławicka 2–4, 53–146 Wrocław, Poland  
> **Contact:** api@trans.eu  
> **Callback IP:** 52.208.90.151

---

## Table of Contents

1. [API Overview](#1-api-overview)
2. [Domain Model](#2-domain-model)
3. [Dependency Graph](#3-dependency-graph)
4. [Authentication & Authorization](#4-authentication--authorization)
5. [Rate Limits](#5-rate-limits)
6. [Complete Endpoint Inventory](#6-complete-endpoint-inventory)
   - 6.1 [Auth API](#61-auth-api)
   - 6.2 [Freights API](#62-freights-api)
   - 6.3 [Routes & Contracts API](#63-routes--contracts-api)
   - 6.4 [Orders API](#64-orders-api)
   - 6.5 [Transports in Realization API](#65-transports-in-realization-api)
   - 6.6 [Dock Scheduler API](#66-dock-scheduler-api)
   - 6.7 [Vehicles / Vehicle Exchange API](#67-vehicles--vehicle-exchange-api)
   - 6.8 [Partners API](#68-partners-api)
   - 6.9 [Fleet API](#69-fleet-api)
   - 6.10 [My Company API](#610-my-company-api)
   - 6.11 [Media / Attachments API](#611-media--attachments-api)
   - 6.12 [Suggested Locations API](#612-suggested-locations-api)
   - 6.13 [Corporate & Private Exchange Lists](#613-corporate--private-exchange-lists)
7. [Schemas](#7-schemas)
8. [Callback / Webhook Events](#8-callback--webhook-events)
9. [Complete Enum / Allowed Values Dictionary](#9-complete-enum--allowed-values-dictionary)
10. [Error Handling](#10-error-handling)
11. [Pagination](#11-pagination)

---

## 1. API Overview

The Trans.eu Platform API connects Shippers, Freight Forwarders, and Carriers on a unified road transport platform. It enables programmatic management of freight offers, route contracts, transport orders, vehicle exchanges, fleet, dock/warehouse scheduling, real-time transport monitoring, and partner relationships.

### Key Capabilities

- **Freights:** Create, publish (7 publication methods), update, negotiate, archive
- **Routes & Contracts:** Create routes, fixed/flexible contracts, balancing, publication scenarios
- **Orders:** Full lifecycle (create, receive, confirm, cancel, archive, amend)
- **Transports in Realization:** List, detail, monitor, GeoJSON trace
- **Dock Scheduler:** Warehouses, time windows, announcements with full lifecycle
- **Vehicle Exchange:** Offers CRUD, refresh
- **Partners:** Manage contractors, groups, cooperation status
- **Fleet:** Vehicle pool management
- **My Company:** Company details, employees, suggested locations
- **Attachments:** Upload/download assets

### Server

| Environment | URL |
|---|---|
| Production API | `https://api.platform.trans.eu/ext/` |
| OAuth Authorization | `https://auth.platform.trans.eu` |

### API Versioning

APIs are versioned via URL path: `/v1/`, `/v2/` per domain.

---

## 2. Domain Model

```
                          TRANS.EU PLATFORM
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
    ┌────┴─────┐         ┌────┴─────┐         ┌─────┴──────┐
    │  COMPANY │         │  ROUTE   │         │   FLEET    │
    │          │         │  (V2)    │         │  (Vehicles)│
    │ Employees│         │ ──────── │         └────────────┘
    │ Partners │         │ Contracts│
    │ Locations│         │ (fixed/  │         ┌────────────┐
    └──────────┘         │  flex)   │         │  VEHICLE   │
                         │ Balancing│         │  EXCHANGE  │
    ┌──────────┐         └──────────┘         │  (Offers)  │
    │ FREIGHT  │                               └────────────┘
    │  (CRUD)  │
    │    │     │         ┌──────────┐
    │ Publication │──────│TRANSPORT │
    │  • Exchange       │  ORDER   │    ┌──────────────────┐
    │  • Private Exch   │    │      │    │ DOCK SCHEDULER  │
    │  • Corporate Exch │ Transport│    │ ─────────────── │
    │  • Selected Co's  │  Tasks   │    │ Warehouse       │
    │  • Direct Persons │    │      │    │ Time Window     │
    │  • Automation     │ Monitoring│   │ Announcement    │
    │  • SmartMatch     │  + Trace │    └──────────────────┘
    │  • Multi-Exchange └──────────┘
    │    (V2)
    │ Negotiation
    │  (Offers/Proposals)
    │ Internal Note
    │ Archive
    └──────────
```

### Entity Relationships

- **Company** → creates **Freights**, owns **Fleet**, manages **Partners**
- **Route** → has **Contracts** (fixed or flexible), can be **Balanced**
- **Freight** → has one or more **Publications** (to exchanges/partners/persons)
- **Freight** → spawns **Negotiations** (offers from carriers)
- **Freight** → when accepted becomes a **Transport Order**
- **Transport Order** → contains one or more **Transport Tasks**
- **Transport Task** → has **Monitoring** events + **Trace** (GPS trail, GeoJSON)
- **Warehouse** → has **Time Windows** (booking slots)
- **Time Window** → linked to **Announcements** (carrier arrival/status)
- **Company** → owns **Fleet Vehicles**
- **Company** → has **Partners/Contractors** with cooperation status

---

## 3. Dependency Graph

```
                    ┌──────────────┐
                    │  Auth Token  │
                    │  (OAuth 2.0) │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┬───────────┐
              │            │            │           │
              ▼            ▼            ▼           ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
      │ Freights │  │  Orders  │  │ Routes   │  │ Vehicles │
      │  (CRUD)  │  │ (V1/V2) │  │ & Contr. │  │ Exchange │
      │ Public.  │  │          │  │ (V1/V2)  │  │          │
      │ Negoti.  │  └────┬─────┘  └──────────┘  └──────────┘
      └────┬─────┘       │
           │      ┌──────┴──────┐
           │      │             │
           ▼      ▼             ▼
      ┌──────────┐       ┌─────────────┐
      │Transports│       │Dock Scheduler│
      │in Realiz.│       │  (Time Win) │
      └──────────┘       └─────────────┘
           │                  │
           ▼                  ▼
      ┌──────────┐       ┌─────────────┐
      │Monitoring│       │Announcements│
      │ + Trace  │       └─────────────┘
      └──────────┘

Independent APIs (no upstream dependency):
  ─ Partners API
  ─ Fleet API
  ─ My Company API
  ─ Suggested Locations API
  ─ Media/Attachments API
  ─ Corporate & Private Exchange Lists
```

### Dependency Rules

1. **Auth token** is required by ALL endpoints (mandatory dependency)
2. **Freight** must exist before creating publications, negotiations, or internal notes
3. **Route** must exist before creating contracts or publication scenarios
4. **Transport Order** requires an accepted freight (or direct creation via order-created)
5. **Transport Task** is always under a Transport Order
6. **Monitoring/Trace** requires an active Transport Task with GPS tracking
7. **Dock Scheduler** Time Windows linked to Warehouses; Announcements linked to Time Windows
8. **Vehicle Exchange** offers are independent of freights/orders
9. **Fleet** vehicles are independent (manage company vehicle pool)

---

## 4. Authentication & Authorization

### 4.1 Protocol

**OAuth 2.0 Authorization Code Flow** (RFC 6749)

### 4.2 Prerequisites

| Credential | Description | Obtained During |
|---|---|---|
| `client_id` | Application identifier | Registration form |
| `client_secret` | Application secret (confidential) | Registration form |
| `api-key` | Unique API key per app | Registration form |

### 4.3 Step 1 – Authentication Request

```
GET /oauth2/auth HTTP/1.1
Host: auth.platform.trans.eu
```

**Parameters:**

| Parameter | Required | Description |
|---|---|---|
| `client_id` | Yes | Client identifier from registration |
| `response_type` | Yes | MUST be `code` |
| `redirect_uri` | Yes | MUST match registered redirect URI |
| `state` | Recommended | Opaque CSRF token (min 8 chars, cryptographically random) |

The user logs in on the Trans.eu login page. After granting access, the server redirects with:

```
HTTP/1.1 302 Found
Location: https://example.com/app?code={authorization_code}&state={state}
```

The authorization code is single-use, lifetime **1 minute**.

### 4.4 Step 2 – Token Request

```
POST /ext/auth-api/accounts/token HTTP/1.1
Host: api.platform.trans.eu
Content-Type: application/x-www-form-urlencoded
Api-key: {unique_app_api-key}

grant_type=authorization_code&
code={code}&
redirect_uri={redirect_uri}&
client_id={client_id}&
client_secret={client_secret}
```

**Successful Response:**

```json
{
  "access_token": "59d9aa9b15cd59a61fc52014792efb6caa82373b",
  "token_type": "Bearer",
  "expires_in": 21599,
  "scope": "offers.loads.manage",
  "refresh_token": "d52d1d998d6533a3be8e7f26f904be513287938b"
}
```

### 4.5 Refresh Token Flow

```
POST /ext/auth-api/accounts/token HTTP/1.1
Host: api.platform.trans.eu
Content-Type: application/x-www-form-urlencoded
Api-key: {unique_app_api-key}

grant_type=refresh_token&
refresh_token={refresh_token}&
client_id={client_id}&
client_secret={client_secret}
```

### 4.6 Request Headers (All API Calls)

| Header | Value |
|---|---|
| `Authorization` | `Bearer {access_token}` |
| `Api-key` | `{unique_app_api_key}` |
| `Content-Type` | `application/json` (unless noted) |
| `Accept` | `application/json` |

### 4.7 OAuth Scopes (from YAML)

| Scope | Permission |
|---|---|
| `trans.freights-service.freights.read` | Read freights |
| `trans.freights-service.freights.manage` | Manage (create/update/delete) freights |
| `trans.freights-service.freights-publications.read` | Read freight publications |
| `trans.freights-service.proposals-requests.read` | Read proposals |
| `trans.freights-service.freights-archive.read` | Read archived freights |
| `trans.freight-orders.orders.read` | Read orders |
| `trans.freight-orders.orders.write` | Write orders |
| `trans.freight-orders.orders.manage` | Manage orders |
| `trans.freight-orders.order-attachments.write` | Write order attachments |
| `trans.exchange.vehicle-offers.read` | Read vehicle exchange offers |
| `trans.exchange.vehicle-offers.write` | Write vehicle exchange offers |
| `trans.exchange.offers.read` | Read exchange offers |
| `trans.offers.vehicles.manage` | Manage vehicle offers |

### 4.8 Security Scheme (OpenAPI 3.0)

```yaml
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

### 4.9 OAuth Error Codes

`invalid_request`, `invalid_client`, `invalid_grant`, `unauthorized_client`, `unsupported_grant_type`, `access_denied`

---

## 5. Rate Limits

| Endpoint Type | Limit |
|---|---|
| Token endpoints (`/ext/auth-api/accounts/token`) | **5 requests/second** |
| All other API endpoints | **15 requests/second** |

Exceeding limits returns **HTTP 429 Too Many Requests**.

---

## 6. Complete Endpoint Inventory

### 6.1 Auth API

| Method | Path | Summary |
|---|---|---|
| `POST` | `/ext/auth-api/accounts/token` | Exchange auth code for token OR refresh token |
| `GET` | `/oauth2/auth` | Initiate OAuth 2.0 Authorization Code flow (on auth.platform.trans.eu) |

---

### 6.2 Freights API

Base: `/freights-api/v1` (unless noted)

#### 6.2.1 Freight CRUD

| Method | Path | Summary | Auth Scope |
|---|---|---|---|
| `POST` | `/freights-api/v1/freights` | Create freight (draft, no publication) | manage |
| `GET` | `/freights-api/v1/freights` | List freights (filter, fields, sort, pagination) | read |
| `GET` | `/freights-api/v1/freights/{freightId}` | Get freight by ID | read |
| `PUT` | `/freights-api/v1/freights/{freightId}` | Update existing freight (draft only) | manage |
| `DELETE` | `/freights-api/v1/freights/{freightId}` | Delete draft freight | manage |
| `GET` | `/freights-api/v1/accepted` | List accepted freights (paginated 30/page) | read |

#### 6.2.2 Publication Methods

| Method | Path | Summary | Note |
|---|---|---|---|
| `POST` | `/freights-api/v1/freight-exchange` | Publish to Trans.eu Freight Exchange | Also create-as-draft with publish:false |
| `PUT` | `/freights-api/v1/freight-exchange/{freightId}` | Update exchange-published freight | |
| `POST` | `/freights-api/v1/private-exchange` | Publish to own private exchange | |
| `PUT` | `/freights-api/v1/private-exchange/{freightId}` | Update private-exchange freight | |
| `POST` | `/freights-api/v1/freight-corporate` | Publish to branded/corporate exchange | |
| `PUT` | `/freights-api/v1/freight-corporate/{freightId}` | Update corporate-exchange freight | |
| `POST` | `/freights-api/v1/freight-companies` | Publish to selected partner companies | |
| `PUT` | `/freights-api/v1/freight-companies/{freightId}` | Update companies-published freight | |
| `POST` | `/freights-api/v1/freight-employees` | Publish directly to specific persons | |
| `PUT` | `/freights-api/v1/freight-employees/{freightId}` | Update direct-to-person freight | |
| `POST` | `/freights-api/v1/freight-auto` | Publish using automation rules (predefined at Platform) | |
| `PUT` | `/freights-api/v1/freight-auto/{freightId}` | Update auto-published freight | |
| `POST` | `/freights-api/v1/freight-smartmatch` | Publish via SmartMatch | |
| `PUT` | `/freights-api/v1/freight-smartmatch/{freightId}` | Update SmartMatch freight | |
| `POST` | `/freights-api/v2/freights` | Publish to MULTI exchanges simultaneously **NEW** | V2 |
| `PUT` | `/freights-api/v1/freights/{freightId}/refresh_publication` | Refresh (bump) publication on exchange | |
| `PUT` | `/corporate-exchange-api/v1/corporate-exchange/{freightId}/refresh-publication` | Refresh on corporate exchange | Different API |
| `PUT` | `/private-exchange-api/v1/exchange/{freightId}/refresh-publication` | Refresh on private exchange | Different API |
| `POST` | `/freights-api/v1/cancelPublication/{freightId}` | Cancel active publication | |
| `POST` | `/freights-api/v1/cancelPublication` | Bulk cancel publications | |

#### 6.2.3 Archive

| Method | Path | Summary |
|---|---|---|
| `POST` | `/freights-api/v1/freights/{freightId}/archive` | Archive single freight |
| `POST` | `/freights-api/v1/freights/archive` | Bulk archive freights |
| `GET` | `/freights-api/v1/archive` | List archived freights |

#### 6.2.4 Offers / Negotiation (Publisher Side)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/freights-api/v1/freights/{freightId}/offers` | List offers for a freight |
| `GET` | `/freights-api/v1/freights/offers/{offerId}` | Get offer details + negotiation history |
| `PATCH` | `/freights-api/v1/freights/offers/{offerId}/negotiate` | Submit counter-price offer |
| `POST` | `/freights-api/v1/freights/offers/{offerId}/accept` | Accept carrier's offer |
| `POST` | `/freights-api/v1/freights/offers/{offerId}/reject` | Reject + definitively close negotiations |
| `POST` | `/freights-api/v1/freights/offers/{offerId}/renouncement` | Reject offer (can restart) |
| `POST` | `/freights-api/v1/freights/offers/{offerId}/withdraw` | Withdraw own (publisher's) last offer |
| `PATCH` | `/freights-api/v1/freights/offers/{offerId}/takeover` | Take over negotiations (another employee) |

#### 6.2.5 Proposals / Negotiation (Carrier Side)

| Method | Path | Summary | Version |
|---|---|---|---|
| `GET` | `/freights-api/v2/freight-proposals` | List all negotiated freight offers | V2 |
| `GET` | `/freights-api/v2/freight-proposals/{freightId}` | List proposals for a specific freight | V2 |
| `GET` | `/freights-api/v1/freight-proposals/accepted` | List accepted proposals | V1 |
| `GET` | `/freights-api/v1/freight-proposals/archived` | List archived proposals | V1 |

#### 6.2.6 Internal Note

| Method | Path | Summary |
|---|---|---|
| `POST` | `/freights-api/v1/freights/{freightId}/internal-note` | Create internal note (max 500 chars, one per freight) |
| `GET` | `/freights-api/v1/freights/{freightId}/internal-note` | Get internal note |
| `PUT` | `/freights-api/v1/freights/{freightId}/internal-note` | Update internal note |
| `DELETE` | `/freights-api/v1/freights/{freightId}/internal-note` | Delete internal note |

#### 6.2.7 Exchanges List

| Method | Path | Summary |
|---|---|---|
| `GET` | `/corporate-exchange-api/v1/corporate-exchange` | List corporate/private exchanges available |

---

### 6.3 Routes & Contracts API

Base: `/contracts-api/v1` or `/contracts-api/v2`

#### 6.3.1 Routes (V2)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/contracts-api/v2/routes` | List routes (paginated, limit/offset) |
| `GET` | `/contracts-api/v2/routes/{routeId}` | Get route details |
| `POST` | `/contracts-api/v2/routes` | Create a new route |
| `POST` | `/contracts-api/v1/routes/{routeId}` | Update a route |

#### 6.3.2 Route Contracts

| Method | Path | Summary |
|---|---|---|
| `GET` | `/contracts-api/v1/routes/{routeId}/contracts` | List contracts for a route |
| `POST` | `/contracts-api/v2/routes/{routeId}/publication-scenario` | Set/update publication scenario for route |
| `POST` | `/contracts-api/v2/routes/{routeId}/balance` | Balance contracts on route |

#### 6.3.3 Contracts (V2)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/contracts-api/v2/contracts` | List all contracts |
| `GET` | `/contracts-api/v2/contracts/{contractId}` | Get contract details |
| `POST` | `/contracts-api/v2/contracts/flexible` | Create flexible contract |
| `POST` | `/contracts-api/v2/contracts/fixed` | Create fixed contract |
| `POST` | `/contracts-api/v2/contracts/fixed/{contractId}` | Update fixed contract |

---

### 6.4 Orders API

Base: `/orders-api/v1`

#### 6.4.1 Created Orders

| Method | Path | Summary |
|---|---|---|
| `POST` | `/orders-api/v1/orders-created` | Create a new transport order |
| `GET` | `/orders-api/v1/orders-created` | List created orders |
| `GET` | `/orders-api/v1/orders-created/{orderId}` | Get created order by ID |
| `POST` | `/orders-api/v1/orders-created/{orderId}/cancel` | Cancel created order |
| `POST` | `/orders-api/v1/orders-created/{orderId}/archive` | Archive created order (only if delivery-confirmed) |
| `PATCH` | `/orders-api/v1/orders-created/{orderId}/confirm` | Confirm order delivery |
| `PUT` | `/orders-api/v1/orders-created/{orderId}` | Update order |

#### 6.4.2 Order Confirmations (Loading/Unloading)

| Method | Path | Summary |
|---|---|---|
| `POST` | `/orders-api/v1/orders-created/{orderId}/arrived` | Confirm arrival for loading |
| `POST` | `/orders-api/v1/orders-created/{orderId}/loading-arrived` | Confirm arrived at loading point |
| `POST` | `/orders-api/v1/orders-created/{orderId}/loaded` | Confirm loading complete |
| `POST` | `/orders-api/v1/orders-created/{orderId}/unloaded` | Confirm unloading complete |

#### 6.4.3 Received Orders

| Method | Path | Summary |
|---|---|---|
| `GET` | `/orders-api/v1/orders-received` | List received orders |
| `GET` | `/orders-api/v1/orders-received/{orderId}` | Get received order by ID |
| `POST` | `/orders-api/v1/orders-received/{orderId}/accept` | Accept received order |
| `POST` | `/orders-api/v1/orders-received/{orderId}/reject` | Reject received order |
| `POST` | `/orders-api/v1/orders/{orderId}/assignee` | Assign truck + driver to received order |

#### 6.4.4 Entry Execution Data

| Method | Path | Summary |
|---|---|---|
| `POST` | `/orders-api/v1/orders/awaiting-entry-execution-data` | Create order with awaiting-execution-data status |
| `GET` | `/orders-api/v1/orders/awaiting-entry-execution-data` | List orders awaiting execution data |
| `POST` | `/orders-api/v1/orders/{orderId}/required-execution-data/request` | Request execution data from carrier |
| `POST` | `/orders-api/v1/orders/{orderId}/required-execution-data/provide` | Provide required execution data |

#### 6.4.5 Order Conditions (V2 Amendment)

| Method | Path | Summary |
|---|---|---|
| `POST` | `/orders-api/v2/{orderId}/amendment/draft` | Change terms of accepted order |
| (doc) | Accept order conditions | Accept proposed order conditions |
| (doc) | Reject order conditions | Reject proposed order conditions |

#### 6.4.6 Order Attachments & Costs

| Method | Path | Summary |
|---|---|---|
| `POST` | `/orders-api/v1/orders/{orderId}/attachments` | Add attachment to order |
| `POST` | `/orders-api/v1/orders-created/{orderId}/costs` | Add additional costs |
| `PUT` | `/orders-api/v1/orders-created/{orderId}/costs/{costId}` | Update cost |
| `DELETE` | `/orders-api/v1/orders-created/{orderId}/costs/{costId}` | Remove cost |
| (doc) | Get invoice for transport document data | Retrieve invoice data |
| (doc) | Add invoice for transport document to order | Attach invoice to order |

#### 6.4.7 Order Handling

| Method | Path | Summary |
|---|---|---|
| (doc) | `PUT /orders-api/v1/orders-created/{orderId}/shipment-external-id` | Edit shipment external ID |
| (doc) | `GET /orders-api/v1/orders/find-by-freight-number/{freightRefNumber}` | Find transport order using freight number |

#### 6.4.8 Archive Orders

| Method | Path | Summary |
|---|---|---|
| `GET` | `/orders-api/v1/archive-orders-created` | List archived created orders |
| `GET` | `/orders-api/v1/archive-orders-received` | List archived received orders |

---

### 6.5 Transports in Realization API

Base: `/transports-api/v1`

| Method | Path | Summary |
|---|---|---|
| `GET` | `/transports-api/v1/transports` | List transport tasks (paginated 30/page) |
| `GET` | `/transports-api/v1/transports/{transportId}` | Get transport task by ID |
| `GET` | `/transports-api/v1/transports/{transportId}/monitoring` | Get monitoring events for a transport |
| `GET` | `/transports-api/api/rest/v1/transports/{transportId}/trace` | Retrieve monitoring trace (GeoJSON Feature/MultiPoint) |

**Filters:** `order_id`, `role` (shipper/carrier/spectator), `statuses[]`, `states[]` (new/active/completed/archived)

---

### 6.6 Dock Scheduler API

Base: `/ext/dock-scheduler-api/v1`

#### 6.6.1 Warehouses

| Method | Path | Summary |
|---|---|---|
| `GET` | `/ext/dock-scheduler-api/v1/warehouse` | List warehouses |
| `GET` | `/ext/dock-scheduler-api/v1/warehouse/{warehouseId}` | Get warehouse by ID |

#### 6.6.2 Time Windows

| Method | Path | Summary |
|---|---|---|
| `GET` | `/ext/dock-scheduler-api/v1/warehouse/timeWindow` | List/filter time windows |
| `POST` | `/ext/dock-scheduler-api/v1/warehouse/timeWindow` | Add time window (with optional purchase order) |
| `GET` | `/ext/dock-scheduler-api/v1/warehouse/timeWindow/{timeWindowId}` | Get time window by ID |
| `PATCH` | `/ext/dock-scheduler-api/v1/warehouse/timeWindow/{timeWindowId}` | Update time window |
| `DELETE` | `/ext/dock-scheduler-api/v1/warehouse/{timeWindowId}` | Delete time window |

#### 6.6.3 Announcements

| Method | Path | Summary |
|---|---|---|
| `POST` | `/ext/dock-scheduler-api/v1/announcement` | Add announcement |
| `GET` | `/ext/dock-scheduler-api/v1/announcement` | List announcements |
| `GET` | `/ext/dock-scheduler-api/v1/announcement/{announcementID}` | Get announcement by ID |
| `PATCH` | `/ext/dock-scheduler-api/v1/announcement/{announcementID}` | Update announcement |
| `PATCH` | `/ext/dock-scheduler-api/v1/announcement/{announcementID}/slot` | Change booking date and place |
| `GET` | `/ext/dock-scheduler-api/v1/announcement/{announcementID}/history` | Get announcement history |
| `DELETE` | `/ext/dock-scheduler-api/v1/announcement/{announcementID}` | Delete announcement |
| (doc) | Announcement status update | Update announcement stage |

---

### 6.7 Vehicles / Vehicle Exchange API

Base: `/vehicles-api/v1`

| Method | Path | Summary | Auth Scope |
|---|---|---|---|
| `GET` | `/vehicles-api/v1/vehicles` | List vehicle exchange offers | read |
| `GET` | `/vehicles-api/v1/vehicles/{offerId}` | Get vehicle offer by ID | read |
| `POST` | `/vehicles-api/v1/vehicles` | Add new vehicle exchange offer | write |
| `PUT` | `/vehicles-api/v1/vehicles/{offerId}` | Update vehicle offer | manage |
| `PATCH` | `/vehicles-api/v1/vehicles/{offerId}` | Update order (partial) | manage |
| `DELETE` | `/vehicles-api/v1/vehicles/{offerId}` | Delete vehicle offer | - |

---

### 6.8 Partners API

Base: `/partners-api/v1`

| Method | Path | Summary |
|---|---|---|
| `GET` | `/partners-api/v1/partners` | List partners (contractors) |
| `POST` | `/partners-api/v1/partners` | Add company to partners (send invitation) |
| `GET` | `/partners-api/v1/groups` | List groups |
| `POST` | `/partners-api/v1/groups` | Block cooperator |
| (doc) | `GET /partners-api/v1/partners/{partnerId}` | Get contractor by ID |
| (doc) | `GET /partners-api/v1/partners/{partnerId}/employees` | Get contractor employees |
| (doc) | `GET /partners-api/v1/partners/{partnerId}/fleet` | Get contractor fleet |
| (doc) | `POST /partners-api/v1/partners/{partnerId}/activate` | Activate cooperation |
| (doc) | `POST /partners-api/v1/partners/{partnerId}/block` | Block cooperation |

---

### 6.9 Fleet API

Base: `/fleet-api/v1`

| Method | Path | Summary |
|---|---|---|
| `GET` | `/fleet-api/v1/vehicles` | List fleet vehicles |
| `POST` | `/fleet-api/v1/vehicles` | Add vehicle to fleet |
| `DELETE` | `/fleet-api/v1/vehicles/{vehicleId}` | Delete vehicle from fleet |
| `GET` | `/fleet-api/v1/vehicles/{vehicleId}` | Get single vehicle details |

---

### 6.10 My Company API

Base: `/companies-api/v1`

| Method | Path | Summary |
|---|---|---|
| `GET` | `/companies-api/v1/companies` | Get own company details (legal name, VAT ID) |
| `GET` | `/companies-api/v1/companies/employees` | List employees |

---

### 6.11 Media / Attachments API

Base: `/media-storage-api/v1`

| Method | Path | Summary |
|---|---|---|
| `GET` | `/media-storage-api/v1/assets` | Get/download asset |
| `PUT` | `/media-storage-api/v1/assets` | Upload asset |

---

### 6.12 Suggested Locations API

| Method | Path | Summary |
|---|---|---|
| (doc) | `GET /ext/freights-api/v1/suggested-places` | List fixed locations for loading/unloading |
| (doc) | `POST /ext/freights-api/v1/suggested-places` | Add fixed location |
| (doc) | `DELETE /ext/freights-api/v1/suggested-places/{placeId}` | Delete suggestion from saved places |

---

### 6.13 Corporate & Private Exchange Lists

| Method | Path | Summary |
|---|---|---|
| `GET` | `/corporate-exchange-api/v1/corporate-exchange` | List exchanges (private + corporate) with roles |

**Response fields:** `corporate_exchanges[]` — each has `id`, `name`, `type` (1_private/2_corporate), `status`, `created_at`, `member.roles[]` (administrator/principal/mandatory), pagination via `page`, `page_size`, `has_next_page`.

---

## 7. Schemas

### 7.1 Freight Object

```json
{
  "id": 401560,
  "reference_number": "FR/2020/08/03/Y1F3",
  "status": "new|published|accepted|closed|in_progress|unsuccessful_publication|waiting_for_publication",
  "created": "2019-09-13T13:38:18+02:00",
  "archived_at": null,
  "ftl": true,
  "capacity": 20,
  "loading_meters": 2,
  "transport_type": "ftl|ltl|multi_ftl",
  "shipment_external_id": "fr23234",
  "vehicle_size": "bus|double_trailer|lorry|any_size|solo",
  "truck_bodies": ["cooler", "curtainsider", …],
  "temperature": { "min": -5.5, "max": 3 },
  "height": 3.1,
  "length": 12,
  "width": 3.1,
  "volume": 21,
  "transit_time": 460,
  "contact_employees": [
    { "last_name": "Nowak", "name": "Jan", "trans_id": "13443-1" }
  ],
  "loading": {
    "place": { "country": "pl", "locality": "Kraków", "postal_code": "31-008" },
    "timespans": { "begin": "2019-11-15T10:00:00+01:00", "end": "2019-11-15T11:00:00+01:00" }
  },
  "unloading": {
    "place": { "country": "pl", "locality": "Kraków", "postal_code": "31-008" },
    "timespans": { "begin": "2019-11-15T10:00:00+01:00", "end": "2019-11-15T11:00:00+01:00" }
  },
  "publication": {
    "id": 1234,
    "status": "active|finished|offers_timeout|waiting_for_publication",
    "publish_type": "companies|recommended|exchange",
    "end_reason": "accepted|canceled|rejected|timeout|regulations_violated|company_blocked|company_removed_from_exchange|failure",
    "price": { "currency": "eur", "value": 100, "period": { "days": 1, "payment": "deferred" } },
    "is_quick_pay": true,
    "is_recommended": true,
    "received_offers": 1,
    "sent_offers": 2,
    "stock_id": 1052518273,
    "is_proposal_request_exists": false,
    "auction_id": null,
    "offer_id": null
  },
  "requirements": {
    "is_ftl": true,
    "required_truck_bodies": ["truck"],
    "required_adr_classes": ["adr_1_1"],
    "required_ways_of_loading": ["side"],
    "vehicle_size": "any_size",
    "shipping_remarks": null,
    "temperature": { "min": 3, "max": 10 }
  },
  "loads": [
    {
      "id": 409459,
      "name": "Ładunek 1",
      "weight": 2,
      "height": 1,
      "width": 1,
      "length": 1,
      "amount": 1,
      "type_of_load": "palette",
      "volume": 1,
      "is_stackable": true,
      "is_exchangeable": true
    }
  ],
  "spots": [
    {
      "id": 1,
      "name": "Some place",
      "spot_order": 1,
      "place": {
        "address": { "country": "pl", "street": "Racławicka", "locality": "Wrocław", "postal_code": "53-146" },
        "coordinates": { "latitude": 51.085615, "longitude": 17.0105 }
      },
      "operations": [
        {
          "operation_order": 1,
          "type": "loading|unloading",
          "loads": [{ "amount": 1, "name": "name example", "type": "palette", "weight": 754, "volume": 99 }],
          "timespans": { "begin": "2019-11-21T12:00:00+0100", "end": "2019-11-21T12:00:00+0100" }
        }
      ]
    }
  ]
}
```

### 7.2 Transport Order Object

```json
{
  "id": "3e3f21cf-...",
  "order_number": "2025/05/13/1",
  "status": "new|accepted|delivery-confirmed|cancelled|waiting-for-confirmation",
  "freight_id": 3124920,
  "freight_reference_number": "FR/2025/04/03/2NPR",
  "shipment_external_id": null,
  "date_created": "2025-05-13T08:39:25.000Z",
  "source": { "name": "freight-orders" }
}
```

### 7.3 Transport Task Object

```json
{
  "id": "e6b7494b-...",
  "transport_number": "TT2025/05/13/1-1/1",
  "state": "new|active|completed|archived",
  "status": {
    "transport": { "value": "9_finished" },
    "monitoring": "finish"
  },
  "date_created": "2025-05-13T08:39:25.000Z",
  "companies": {
    "owner": { "id": 666666, "name": "Trans.eu" },
    "shipper": { "id": 666666, "name": "Trans.eu" },
    "carrier": { "id": 956529, "name": "MTCarrier" }
  },
  "devices": {
    "executor": { "details": { "name": "Paul Testowy", "phone": null } },
    "truck": { "details": { "plate_number": "DTR11111" } },
    "semitrailer": null
  },
  "operations": [
    {
      "id": "43cb5e7c-...",
      "type": "loading|unloading",
      "completed_at": "2025-05-13T09:00:33.000Z",
      "completion_status": { "type": "on_time|overdue" },
      "execution": {
        "arrival": { "date": "2025-05-13T08:59:35.000Z", "vehicle_weight": 2400 },
        "complete": { "date": "2025-05-13T09:00:33.000Z", "load_weight": 200, "vehicle_weight": 2600 }
      },
      "time_frame": { "date_from": "...", "date_to": "...", "is_precise": true },
      "place": {
        "address": { "country": "OF", "locality": "Babylon" },
        "coordinates": { "latitude": 34.5260109, "longitude": 69.1776838 },
        "timezone": "Asia/Kabul"
      }
    }
  ],
  "references": {
    "freight": { "id": "3124920", "number": "FR/2025/04/03/2NPR" },
    "order": { "id": "3e3f21cf-...", "number": "2025/05/13/1" }
  },
  "requirements": { "monitoring": { "value": "1_required" }, "tracking": true }
}
```

### 7.4 Monitoring Trace (GeoJSON)

```json
{
  "type": "Feature",
  "geometry": { "type": "MultiPoint", "coordinates": [[17.02328, 51.10547], [17.00543, 51.07439]] },
  "properties": {
    "timestamps": ["2025-09-02T11:09:41.000Z", "2025-09-02T11:10:41.000Z"],
    "date_received": ["2025-09-02T11:09:41.000Z", "2025-09-02T11:10:41.000Z"]
  }
}
```

### 7.5 Announcement Object

```json
{
  "id": 38602,
  "reference_number": "DS/16365BE/1",
  "status": "CONFIRMED|IN_PROGRESS|FINISHED|REFUSED",
  "stage": "Vehicle_Arrived|Started|Finished|Vehicle_Left",
  "date_from": "2023-07-14T08:00:00",
  "date_to": "2023-07-14T10:00:00",
  "operation_type": "loading|unloading",
  "operation_time": "PT2H",
  "carrier": { "id": 1013865, "legal_name": "Firma Testowa Przewoźnik" },
  "shipper": { "id": 1007386, "legal_name": "Firma Testowa Załadowca" },
  "driver": { "full_name": "Jan Kowalski", "phone_number": "+48888123456", "country": "PL" },
  "second_driver": { … },
  "vehicle": { "truck_plate_number": "123string", "trailer_plate_number": "456string", "vehicle_manufacturer": "SCANIA", "combustion_norm": "EURO 6" },
  "ramp": { "id": 2006, "name": "Suwnica A 1", "ramp_type": "GANTRY|RAMP" },
  "warehouse": { "id": 1567, "name": "Magazyn Stali" },
  "route": { "spots": [{ "order": 1, "address": {…}, "operations": [{ "operation_type": "unloading", "order": 1 }] }] },
  "notes": [{ "id": 26504, "note": "notatka", "type": "SHIPPER|SHIPPER_INTERNAL|CARRIER|CARRIER_INTERNAL" }],
  "external_reference_number": "123test"
}
```

### 7.6 Time Window with Purchase Order

```json
{
  "valid_from": "2025-09-08", "valid_to": "2025-09-08",
  "start_time": "12:00:00", "end_time": "18:00:00",
  "range_type": "CYCLE",
  "external_number": "1DX124DAW7871",
  "carrier": { "id": 956529 },
  "purchase_order": {
    "number": "PO-123",
    "execution_constraints": { "delivery_date": "2025-04-22", "delivery_conditions": "FCA", "payment_conditions": "NET30" },
    "delivery_place": { "receiver_name": "...", "country": "...", "city": "..." },
    "business_partner": { "number": "...", "name": "...", "tax_id": "...", "contact_person": "..." },
    "loads": [{ "name": "cargo", "type": "type", "quantity": 501, "weight": 11, "description": "..." }]
  },
  "route": { "spots": [{ "warehouse_id": 6596, "order": 1, "operations": [{ "operation_type": "loading", "belongs_to_time_window": true }] }] }
}
```

### 7.7 Route Contract Object

```json
{
  "id": "23ba734b-...",
  "carrier": {
    "company": { "id": 567321, "name": "EkoTransporter" },
    "contact_persons": [{ "employee": { "account_id": 771476, "trans_id": "1012334-1", "family_name": "Miller", "given_name": "Michael" } }]
  },
  "order_terms": {
    "automatic_order_sending": true,
    "payment_period": { "value": 12 },
    "monitoring": { "required": true },
    "insurance": {
      "load": { "currency": "eur", "value": 12000 },
      "third_party": { "currency": "eur", "value": 6000 }
    },
    "additional_terms": "additional terms text"
  }
}
```

### 7.8 Corporate/Private Exchange Object

```json
{
  "corporate_exchanges": [
    {
      "id": "006e95ea-...",
      "name": "API test",
      "type": "2_corporate",
      "status": "active",
      "created_at": "2026-02-09T13:23:28.832Z",
      "member": { "roles": ["principal", "mandatory"] }
    }
  ],
  "page": 1, "page_size": 2, "has_next_page": false
}
```

### 7.9 Company / Employee Object

```json
{
  "legal_name": "Trans.eu Group S.A.",
  "vat_id": "PL8942764658",
  "employees": [
    { "trans_id": "1038173-1", "given_name": "Jan", "family_name": "Kowalski", "account_id": 10116324 }
  ]
}
```

---

## 8. Callback / Webhook Events

Clients register a `callback_url` when creating objects. The system sends `POST` requests to that URL.

### 8.1 Callback Endpoints (callback_url accepted)

| Endpoint | Object Type |
|---|---|
| `POST /freights-api/v1/freight-exchange` | Freight |
| `POST /freights-api/v1/freight-employees` | Freight |
| `POST /freights-api/v2/freights` | Freight |
| `POST /freights-api/v1/freight-companies` | Freight |
| `POST /freights-api/v1/freight-auto` | Freight |
| `POST /freights-api/v1/private-exchange` | Freight |
| `POST /freights-api/v1/freight-corporate` | Freight |
| `POST /orders-api/v1/orders-created` | Order |
| `POST /ext/dock-scheduler-api/v1/announcement` | Announcement |
| `POST /ext/dock-scheduler-api/v1/warehouse/timeWindow` | Time Window |

### 8.2 Event Structure

```json
{
  "id": "87795",
  "event_name": "{event.name}",
  "occurred_at": "2026-01-25T11:41:11+00:00",
  "data": { "price": 560.20, "author": "12665-1" }
}
```

### 8.3 Freight Events

| Event Name | Description | Data |
|---|---|---|
| `freights.freight.create` | Freight created | — |
| `freights.freight.update` | Freight updated | — |
| `freights_processing.publication.finished` | Publication ended | — |
| `freights_processing.publication.negotiation_time_finished` | Negotiation time ended | — |
| `freights.proposal_request.accepted` | Offer accepted | `price` |
| `freights.proposal_request.created` | New negotiation started | — |
| `freights.proposal_request.negotiated` | New price offered | `price`, `author_id` |
| `freights.proposal_request.negotiation_lost` | Negotiation lost | `id`, `author_id`, `participant_company_id`, `freight_id` |
| `freights.proposal_request.rejected` | Offer rejected | — |
| `freights.proposal_request.renounced` | Offer renounced (can restart) | — |
| `freights.proposal_request.withdrawn` | Offer withdrawn | — |
| `freights.publication.accepted` | Publication accepted | — |
| `freights.publication.activated` | Publication activated | — |
| `freights.publication.canceled` | Publication cancelled | — |
| `freights.publication.created` | Publication created | — |
| `freights.publication.finished` | Publication finished | — |
| `freights.freight.order_from_contract_was_created` | Order created from contract | — |

### 8.4 Order Events

| Event Name | Description | Data |
|---|---|---|
| `freight_orders.order.attachment_added` | Attachment added | — |
| `freight_orders.order.attachment_removed` | Attachment removed | — |
| `freight_orders.order.attachment_visibility_changed` | Visibility changed | — |
| `freight_orders.order.created` | Order created | — |
| `freight_orders.order.delivery_was_confirmed` | Delivery confirmed | `freight_id`, `freight_reference_number`, `shipment_external_id`, `status` |
| `freight_orders.order.order_was_accepted_by_contract` | Auto-accepted by route contract | — |
| `freight_orders.order.order_was_cancelled` | Order cancelled | — |
| `freight_orders.order.proposal_submitted` | Terms change proposed | — |
| `freight_orders.order.proposal_was_accepted` | Terms accepted | — |
| `freight_orders.order.shipment_external_id_was_changed` | External ID changed | — |
| `freight_orders.order.transports_was_finished` | All transports unloaded | `freight_id`, `freight_reference_number`, `shipment_external_id`, `status` |

### 8.5 Transport Events

| Event Name | Description | Data |
|---|---|---|
| `transports.transport.devices_set_changed` | Vehicle/driver changed | `carrier_id`, `carrier_name`, `executor_name`, `executor_phone`, `freight_id`, `order_id`, `truck_plate_number`, `semitrailer_plate_number`, `shipment_external_id` |

### 8.6 Dock Scheduler Events

| Event Name | Description |
|---|---|
| `time_slot_management.announcement.created` | Announcement created |
| `time_slot_management.announcement.deleted` | Announcement deleted |
| `time_slot_management.announcement.updated` | Announcement updated |
| `time_slot_management.time_window.created` | Time window created |
| `time_slot_management.time_window.deleted` | Time window deleted |
| `time_slot_management.time_window.updated` | Time window updated |
| `time_slot_management.time_window.matching_result_with_freight_order_operations` | Time window matched with order operations |

---

## 9. Complete Enum / Allowed Values Dictionary

### 9.1 Currencies

`eur`, `all`, `bam`, `bgn`, `czk`, `gbp`, `huf`, `isk`, `kzt`, `kgs`, `mkd`, `mdl`, `pln`, `ron`, `rub`, `rsd`, `sek`, `chf`, `try`, `uah`, `byn`

### 9.2 Countries (ISO 2-letter)

`ad`, `af`, `al`, `am`, `at`, `az`, `ba`, `be`, `bg`, `by`, `ch`, `cy`, `cz`, `de`, `dk`, `dz`, `ee`, `eg`, `es`, `fi`, `fr`, `gb`, `ge`, `gr`, `hr`, `hu`, `ie`, `il`, `iq`, `ir`, `is`, `it`, `kg`, `kz`, `li`, `lt`, `lu`, `lv`, `ma`, `mc`, `md`, `me`, `mk`, `mt`, `nl`, `no`, `pk`, `pl`, `pt`, `ro`, `rs`, `ru`, `se`, `si`, `sk`, `sm`, `tj`, `tm`, `tn`, `tr`, `ua`, `uz`, `xk`

### 9.3 Truck Body Types

`cooler`, `isotherm`, `food-tanker`, `petroleum-tanker`, `chemical-tanker`, `gas-tanker`, `silos`, `standard-tent`, `curtainsider`, `mega`, `colimulde`, `log-trailer`, `platform-trailer`, `car-transporter`, `other`, `hook-truck`, `low-loader`, `truck`, `box`, `removal-truck`, `swap-body-system`, `20-standard`, `40-standard`, `45-standard`, `joloda`, `bde`, `open-box`, `meathanging`, `walkingfloor`, `tank-body-20`, `tank-body-40`, `tanker`

### 9.4 Vehicle Sizes

`bus`, `double_trailer`, `lorry`, `any_size`, `solo`, `lorry_solo`

### 9.5 Load / Package Types

`20gp_dry_van`, `20ot_open_top`, `20re_temperature_controlled`, `20vh_ventilated_container`, `40gp_dry_van`, `40hc_high_cube`, `40hw_palette_high_cube`, `40ot_open_top`, `40re_temperature_controlled`, `40rh_temperature_controlled_high_cube`, `45hc_high_cube`, `45hw_palette_high_cube`, `bag`, `barrel`, `big-bag`, `box`, `carton`, `container_palette`, `cp1`–`cp9` (chemical_palette), `cubic`, `eur_2`, `eur_3`, `eur_6`, `europalette`, `log`, `other`, `palette`, `piece`

### 9.6 Payment Types

`deferred`, `payment_in_advance`, `payment_on_unloading`

### 9.7 Publish Types

`exchange`, `companies`, `recommended`, `smartmatch`, `auto`

### 9.8 ADR Classes

`adr_1_1` through `adr_1_6`, `adr_2_1`–`adr_2_3`, `adr_3`, `adr_4_1`–`adr_4_3`, `adr_5_1`–`adr_5_2`, `adr_6_1`–`adr_6_2`, `adr_7`, `adr_8`, `adr_9`

### 9.9 Ways of Loading

`side`, `rear`, `top`, `crane`, `forklift`, `conveyor`, `tank_loading_from_top`, `tank_loading_from_bottom`, `pneumatic`, `pump`

### 9.10 Freight Statuses

| Status | Description |
|---|---|
| `new` | Newly created, never published |
| `waiting_for_publication` | Scheduled for publication at a future date |
| `in_progress` | Being published, under negotiation, or selecting offers |
| `accepted` | Carrier selected, freight accepted |
| `closed` | Unaccepted freight moved to archive |
| `unsuccessful_publication` | Publication ended without acceptance; re-publication possible |
| (archived) | Moved to archive |

### 9.11 Publication Statuses

| Status | Description |
|---|---|
| `null` | Freight not yet published |
| `active` | Currently being published |
| `finished` | Publication completed |
| `offers_timeout` | Decision date passed with offers available (not yet finished) |
| `waiting_for_publication` | Future publish date set |

### 9.12 Publication End Reasons

| Reason | Description |
|---|---|
| `accepted` | Carrier offer accepted |
| `canceled` | Publication manually cancelled |
| `rejected` | All carrier offers rejected |
| `timeout` | Publication expired (past unloading date, no offers) |
| `regulations_violated` | Cancelled by Trans.eu (regulation violation) |
| `company_blocked` | Publishing company blocked |
| `company_removed_from_exchange` | Company lost exchange authorization |
| `failure` | Internal system error |

### 9.13 Negotiation Statuses

| Status | Description |
|---|---|
| `acceptation` | Offer accepted, no further action possible |
| `negotiation` | Ongoing, further action possible |
| `rejection` | Finished without result, cannot restart |
| `renouncement` | Rejected, can restart |

### 9.14 Transport Task States

`new`, `active`, `completed`, `archived`

### 9.15 Transport Task Statuses

`1_awaiting_operation_dates`, `2_awaiting_required_information_for_transport_execution`, `3_ready`, `4_awaiting_confirmation_of_arrival_for_loading`, `5_awaiting_confirmation_of_loading`, `6_en_route`, `7_awaiting_confirmation_of_arrival_for_unloading`, `8_awaiting_confirmation_of_unloading`, `9_finished`, `10_task_cancelled`

### 9.16 Roles in Transport

`shipper`, `carrier`, `spectator`

### 9.17 Operation Types (Spots)

`loading`, `unloading`

### 9.18 Dock Scheduler Announcement Statuses

`CONFIRMED`, `IN_PROGRESS`, `FINISHED`, `REFUSED`

### 9.19 Dock Scheduler Announcement Stages

`Vehicle_Arrived`, `Started`, `Finished`, `Vehicle_Left`

### 9.20 Ramp Types

`GANTRY`, `RAMP`

### 9.21 Exchange Types

`1_private`, `2_corporate`

### 9.22 Exchange Member Roles

`administrator`, `principal`, `mandatory`

### 9.23 Transport Types

`ftl`, `ltl`, `multi_ftl`

### 9.24 Document Types (Driver)

`IDENTITY_CARD`, `DRIVING_LICENSE`, `PASSPORT`, `other`

### 9.25 Combustion Norms

`EURO 1` through `EURO 6`

### 9.26 Order Statuses

`new`, `accepted`, `delivery-confirmed`, `cancelled`, `waiting-for-confirmation`

### 9.27 Note Types (Announcement)

`SHIPPER`, `SHIPPER_INTERNAL`, `CARRIER`, `CARRIER_INTERNAL`

### 9.28 Contract Types

`fixed`, `flexible`

### 9.29 Contract Statuses

`registered`, `waiting_for_acceptance`, `waiting_for_carrier_offer`, `waiting_for_initial_carrier_offer`, `waiting_for_shipper_offer`, `active`, `accepted`, `refused`, `finished`, `finished_previously_accepted`

### 9.28 Monitoring Required Values

`1_required`

### 9.29 Completion Types (Transport Operations)

`CONFIRMED_MANUALLY`, `CONFIRMED_BY_TELEMATICS`

### 9.30 Completion Status Types

`on_time`, `overdue`

### 9.31 Monitoring Sources

`gps`, `manual`

---

## 10. Error Handling

### 10.1 HTTP Status Codes

| Code | Description |
|---|---|
| `200` | Success |
| `204` | Success (no content, DELETE) |
| `302` | Redirect (OAuth flow) |
| `400` | Bad request |
| `401` | Unauthorized |
| `404` | Not found |
| `422` | Unprocessable entity (validation error) |
| `429` | Too many requests (rate limit) |
| `5xx` | Server error |

### 10.2 Validation Error Format

```json
{
  "detail": "Failed Validation",
  "status": 422,
  "title": "Unprocessable Entity",
  "validation_messages": {
    "sortBy": {
      "notInArray": "Allowed values: status, created_at, loading_date, unloading_date, archived_at"
    }
  }
}
```

Typical validation errors: `Vehicle type not allowed for vehicle size`, invalid field values, missing required fields.

---

## 11. Pagination

- **Default page:** 1
- **Page size:** Max 30 results per page (transports, orders, freights lists)
- **Parameter:** `?page={n}`
- **Sorting:** `?sortBy={field}&order=asc|desc`
- **Contracts/Routes (V2):** `?limit={n}&offset={n}`
- **Archive/Accepted lists:** `?pagination={n}`

### Sortable Fields

- `status`, `created_at`, `loading_date`, `unloading_date`, `archived_at`

---

## Appendix: Quick Reference

### Common Headers

```
Authorization: Bearer {access_token}
Api-key: {unique_app_api_key}
Content-Type: application/json
Accept: application/json
```

### Base URL

```
https://api.platform.trans.eu/ext/
```

### Auth Endpoint

```
POST https://api.platform.trans.eu/ext/auth-api/accounts/token
GET https://auth.platform.trans.eu/oauth2/auth
```

### YAML Spec Download

`https://www.trans.eu/api/wp-content/uploads/TransEU202501.yaml_.zip`
(OpenAPI 3.0.1, 21,817 lines)

### All Service Prefixes

| Prefix | Domain |
|---|---|
| `/freights-api/v1` | Freights (V1) |
| `/freights-api/v2` | Freights (V2 — multi-exchange, proposals) |
| `/contracts-api/v1` | Routes & Contracts (V1) |
| `/contracts-api/v2` | Routes & Contracts (V2) |
| `/orders-api/v1` | Orders (V1) |
| `/orders-api/v2` | Orders (V2 — amendments) |
| `/transports-api/v1` | Transports in Realization |
| `/vehicles-api/v1` | Vehicle Exchange |
| `/partners-api/v1` | Partners/Contractors |
| `/fleet-api/v1` | Fleet |
| `/companies-api/v1` | My Company |
| `/media-storage-api/v1` | Attachments |
| `/corporate-exchange-api/v1` | Corporate Exchange Lists |
| `/private-exchange-api/v1` | Private Exchange Refresh |
| `/ext/dock-scheduler-api/v1` | Dock Scheduler |
| `/ext/auth-api` | Authentication Tokens |

### Support

- Email: `api@trans.eu`
- Registration: `https://www.trans.eu/api/register-your-app/`
- Callback IP whitelist: `52.208.90.151`
- Regulations: `https://www.trans.eu/api/regulations/`
