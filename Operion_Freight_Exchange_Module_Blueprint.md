# Operion Freight Exchange Integration — Implementation Blueprint

**Status:** Implementation-ready specification
**Audience:** AI coding agents building against the Operion ERP codebase (PySide6 desktop client + FastAPI/PostgreSQL backend)
**Enforced conventions carried over from existing Operion codebase:**
- All UI strings MUST go through `t()` backed by `ro.json` / `en.json`. No hardcoded strings anywhere in this feature.
- All new backend endpoints MUST enforce `company_id` multi-tenant isolation at the query layer (never trust a client-supplied `company_id`; derive it from the JWT).
- All new tables MUST ship with Alembic migrations, and every migration MUST be proven with a failing-then-passing test.
- All design surfaces MUST use the existing token system (indigo `#6366F1` primary, Inter typography, existing spacing scale) — no ad hoc colors or fonts.
- No step in this blueprint is "done" until it has an automated test that failed before the fix and passes after. Coding agents must paste before/after test output, not just claim completion.

This document is self-contained and covers freight-exchange integration as its own subsystem, end to end: architecture, data contracts, database schema, and a phased build sequence with gates. It does not require reading any other Operion planning document to follow.

---

## 1. Vision & Core Principle

**The goal is not "make the AI able to search TIMOCOM." The goal is "make Operion able to search freight exchanges" — plural, from day one, even though only one provider is connected at launch.**

Freight-exchange integration is built as a normal, dispatcher-facing ERP subsystem — with the same maturity bar as Dispatch, Fleet, or Route Planner — used manually by real dispatchers first. Any future AI/automation layer is a thin, optional consumer added much later, once the subsystem is already proven. It is never the reason this gets built, and it never gets to skip the line ahead of manual usability.

**Provider-agnostic by construction, not as a someday-refactor.** TIMOCOM is the first freight exchange this connects to, not the only one it's built for. Romanian/EU road freight dispatchers routinely work across multiple boards — Trans.eu, Teleroute, Wtransnet, and others alongside TIMOCOM — and a company should eventually be able to connect several simultaneously and search across all of them from one place. This blueprint mirrors the adapter pattern Operion already uses successfully for Live Tracking (Wialon, Frotcom, Traccar behind one common tracking interface) — the same shape of problem (several external providers, one normalized internal model) gets the same architectural answer. **Adding a second provider later should mean writing one new adapter class, never touching the Search Engine, Import Pipeline, Evaluation Engine, or Fleet Matcher.** If adding a provider ever requires changing any of those four, the abstraction has failed and needs fixing before more providers are added.

**Hard rule that shapes every layer below:** logistics intelligence (search, evaluation, truck matching) lives entirely inside Operion's own deterministic services — never inside a language model, a prompt, or any provider-specific code path. Every decision this subsystem makes must be explainable by pointing at a formula and its inputs, not by re-asking whatever produced the decision to justify itself after the fact. This is what makes the subsystem testable, debuggable, and trustworthy enough to eventually hand to an autonomous caller — and what makes it useful to a human dispatcher even if no AI layer is ever built on top of it at all.

---

## 2. Layer Overview

```
Dispatcher UI (manual search / import / evaluate screens, provider-selector included)
                                                │
                    Future: any automated caller (optional, built much later)
                                                │
                                                ▼
                        Deterministic Service Layer (§9) — plain service methods, nothing UI- or AI-specific
                                                ▼
        ┌───────────────────────┬───────────────────────────┬──────────────────────────┐
        Fleet Matcher          Evaluation Engine            Import Pipeline
        (§8)                   (§7)                         (§6)
        └───────────────────────┴───────────────────────────┴──────────────────────────┘
                                                ▼
                              Search Engine (§5) — provider-agnostic, normalizes across all connected providers
                                                ▼
                    Provider Adapter Layer (§3–§4) — one adapter per freight exchange
                                                ▼
        ┌───────────────────────┬───────────────────────────┬──────────────────────────┐
        TimocomAdapter         TransEuAdapter (future)      TeleroufeAdapter (future)   ...
        └───────────────────────┴───────────────────────────┴──────────────────────────┘
                    ▼                         ▼                          ▼
              TIMOCOM API                Trans.eu API                Teleroute API
```

Only the bottom two rows are provider-specific. Everything from the Search Engine upward has zero knowledge of which provider(s) a given result came from beyond a `provider_id` string tag. Each layer is built, tested, and put into real manual use before the next one starts (§10 has the exact gates). This is ordinary backend/frontend feature work — it only happens to be automation-ready later because it's built as clean, typed services rather than logic embedded directly in UI screens.

**Note on types used below:** `Money` refers to Operion's existing shared currency+amount value type, already used across Invoices/Receipts/Analytics — not something new introduced by this subsystem.

---

## 3. Provider Adapter Interface

**This is the layer that makes "provider-agnostic" real instead of aspirational.** Every freight exchange — TIMOCOM today, Trans.eu/Teleroute/Wtransnet/others later — implements the same interface. Nothing above this layer ever imports a provider-specific SDK or references a provider-specific payload shape.

```python
# app/services/freight_exchange/adapter_base.py

from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class ProviderCredentials(BaseModel):
    company_id: str
    provider_id: str                  # "timocom", "trans_eu", "teleroute", "wtransnet", ...
    client_id: str
    client_secret_encrypted: str      # via the existing encrypted-credentials store — no new secrets mechanism
    scope: list[str] = []

class ProviderSession(BaseModel):
    company_id: str
    provider_id: str
    access_token_encrypted: str
    expires_at: datetime
    refresh_token_encrypted: str | None
    last_health_check_at: datetime
    last_health_check_status: Literal["healthy", "degraded", "down"]

class ProviderHealthCheck(BaseModel):
    provider_id: str
    status: Literal["healthy", "degraded", "down"]
    latency_ms: int
    checked_at: datetime
    error: str | None = None

class ProviderCapabilities(BaseModel):
    """Not every freight exchange supports every filter or feature. The Search Engine (§5)
    reads this before building a request so it never sends a provider a filter it can't honor,
    and so the UI can grey out unsupported filters per connected provider rather than silently
    dropping them."""
    provider_id: str
    supported_filters: list[str]              # subset of LoadSearchFilters field names
    supports_saved_search: bool
    supports_offer_publishing: bool
    rate_limit_per_minute: int

class GeoFilter(BaseModel):
    location: str
    radius_km: float

class LoadSearchFilters(BaseModel):
    """The ONE normalized filter shape every adapter must translate to/from its provider's own
    API. New TIMOCOM-only (or any-provider-only) criteria go in extra_filters rather than
    forcing a schema change that implies every provider supports it."""
    origin: GeoFilter
    destination: GeoFilter
    pickup_date_from: "date"
    pickup_date_to: "date"
    delivery_date_from: "date | None" = None
    delivery_date_to: "date | None" = None
    trailer_type: list[str] | None = None
    adr_required: bool | None = None
    weight_kg_min: float | None = None
    weight_kg_max: float | None = None
    price_min: float | None = None
    distance_km_max: float | None = None
    extra_filters: dict = {}

class LoadSearchResult(BaseModel):
    """The ONE normalized result shape. Every adapter maps its provider's raw payload into this —
    the Search Engine, Evaluation Engine, and Fleet Matcher never see a provider-specific field."""
    result_id: str
    provider_id: str
    provider_load_id: str             # the ID as that specific provider knows it — opaque outside the adapter
    origin: str
    destination: str
    pickup_window: tuple[datetime, datetime]
    delivery_window: tuple[datetime, datetime]
    price: "Money"
    distance_km: float
    trailer_type: str
    adr: bool
    raw_payload: dict                 # retained for import-time completeness only; never surfaced to UI beyond the typed fields above

class FreightProviderAdapter(ABC):
    provider_id: str

    @abstractmethod
    async def authenticate(self, credentials: ProviderCredentials) -> ProviderSession: ...

    @abstractmethod
    async def refresh_session(self, session: ProviderSession) -> ProviderSession: ...

    @abstractmethod
    async def test_connection(self, session: ProviderSession) -> ProviderHealthCheck: ...

    @abstractmethod
    async def search_loads(self, session: ProviderSession, filters: LoadSearchFilters) -> list[LoadSearchResult]:
        """Implementations translate the normalized LoadSearchFilters into this provider's own
        query shape, call the provider's API, and map results back into LoadSearchResult. This
        translation is the ONLY place provider-specific API knowledge is allowed to live."""

    @abstractmethod
    async def get_load(self, session: ProviderSession, provider_load_id: str) -> LoadSearchResult: ...

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...
```

**Registry, same pattern as the Co-Pilot's `BaseTool` registry (if that blueprint is also in use) — adapters self-register and get validated at startup, not discovered at request time:**

```python
# app/services/freight_exchange/registry.py

@register_freight_provider
class TimocomAdapter(FreightProviderAdapter):
    provider_id = "timocom"
    # implements authenticate/search_loads/etc. against TIMOCOM's actual API

# Startup validation fails fast if a company's connection references an unregistered provider_id,
# or if a registered adapter is missing a required method — same discipline as every other
# registry pattern already established in this codebase.
```

---

## 4. Connection Management (multi-provider)

A company can connect to zero, one, or several providers simultaneously — connection state is per `(company_id, provider_id)`, not a single global connection.

```sql
-- alembic/versions/xxxx_create_freight_exchange_connections.py

CREATE TABLE freight_exchange_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    provider_id TEXT NOT NULL,                   -- 'timocom', 'trans_eu', 'teleroute', 'wtransnet', ...
    credentials_encrypted TEXT NOT NULL,          -- via the existing encrypted-credentials store
    session_state JSONB,                          -- current ProviderSession, refreshed in place
    status TEXT NOT NULL DEFAULT 'disconnected',   -- 'disconnected' | 'connected' | 'degraded' | 'error'
    last_health_check_at TIMESTAMPTZ,
    last_health_check_status TEXT,
    connected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, provider_id)
);

CREATE INDEX idx_freight_connections_company ON freight_exchange_connections (company_id);
```

- **Credential model:** one credential set per `(company, provider)` pair, stored in the existing encrypted-credentials store — user-owned API keys entered once per provider in settings. If a future managed/pooled-credential tier is ever introduced for a given provider, it resolves through the same adapter interface via a feature flag, never mixed with a company's own credentials in the same code path.
- **Health monitoring:** a scheduled background task (reuse the existing Celery + Redis task queue already in the stack) iterates every connected `(company, provider)` pair and calls that adapter's `test_connection()`, updating `last_health_check_status`. The Search Engine (§5) checks this before firing a live search against a given provider and skips/flags it with a clear message rather than timing out silently if that one provider is `down` — a degraded TIMOCOM connection should never block a Trans.eu search from returning results.
- **Test requirement (`tests/freight_exchange/test_connection.py`):** simulate an expiring token mid-session for one provider and assert `refresh_session()` transparently refreshes without the caller noticing; simulate one provider being down while another is healthy and assert a multi-provider search still returns the healthy provider's results with a clear per-provider status flag, not a total failure.

---

## 5. Search Engine (provider-agnostic)

Searches across one, several, or all connected providers and returns one normalized, merged result set.

```python
# app/services/freight_exchange/search.py

class SavedSearch(BaseModel):
    saved_search_id: str
    company_id: str
    user_id: str
    label: str
    filters: LoadSearchFilters
    provider_ids: list[str] | None = None   # None = search all connected providers
    created_at: datetime
    last_refreshed_at: datetime | None

class SearchEngineService:
    async def search_loads(
        self, company_id: str, filters: LoadSearchFilters, provider_ids: list[str] | None = None
    ) -> list[LoadSearchResult]:
        """provider_ids=None searches every connected, healthy provider for this company in
        parallel, merges results, and tags each with its provider_id. A provider that's down
        or lacks a required filter capability (per its ProviderCapabilities) is skipped with a
        logged reason, never silently — the caller can inspect which providers actually
        responded."""

    async def get_load(self, company_id: str, provider_id: str, provider_load_id: str) -> LoadSearchResult: ...
    async def save_search(self, company_id: str, user_id: str, filters: LoadSearchFilters, label: str, provider_ids: list[str] | None = None) -> SavedSearch: ...
    async def refresh_search(self, company_id: str, saved_search_id: str) -> list[LoadSearchResult]: ...
    async def get_recent_searches(self, company_id: str, user_id: str, limit: int = 20) -> list[SavedSearch]: ...
```

- **Caching:** Redis-backed, key `freight:search:{company_id}:{provider_id}:{sha256(filters)}` — cached **per provider**, not per merged result set, so a cache hit on one provider doesn't force a redundant hit on another. Short TTL (start at 3 minutes — freight loads expire fast; this cache exists purely to avoid re-hitting each provider's API for the same filters within a single dispatcher session, not as a substitute for a fresh search). TTL is a named config constant, not a magic number scattered across the codebase.
- **Migration:** `saved_searches` table (`id`, `company_id`, `user_id`, `label`, `filters JSONB`, `provider_ids JSONB` (nullable array), `created_at`, `last_refreshed_at`). JSONB for `filters` rather than a rigid relational schema, since the filter set is written/read as a whole, doesn't need cross-record querying, and needs to absorb new provider-specific criteria via `extra_filters` without a migration every time.
- **Test requirement:** with two fake adapters registered (one healthy, one simulated-down), assert `search_loads(provider_ids=None)` returns only the healthy provider's results plus a flag indicating the other was skipped and why — never a hard failure of the whole search because one provider had an issue.

---

## 6. Import Pipeline (provider-agnostic)

A load from any connected provider never remains a "provider object" inside Operion. The moment a dispatcher decides to use one, it becomes an ordinary internal trip — regardless of which exchange it came from.

```
Any Provider's Load  →  Import  →  Operion Trip (via trip_service.create(), the SAME service manual trip creation uses)  →  every existing module
```

```python
# app/services/freight_exchange/import_pipeline.py

class ImportResult(BaseModel):
    trip_id: str
    source: Literal["manual", "freight_exchange"]
    source_provider_id: str | None       # "timocom", "trans_eu", ... — null for manual trips
    source_reference_id: str | None      # the provider_load_id, kept for traceability only
    imported_at: datetime
    imported_by_user_id: str

class ImportPipelineService:
    async def import_load(self, company_id: str, provider_id: str, provider_load_id: str, user_id: str) -> ImportResult:
        """Maps LoadSearchResult -> the SAME TripCreateSchema trip_service.create() already accepts
        for manually-entered trips, then calls trip_service.create() directly. No parallel
        provider-specific trip representation, no special-cased subtype anywhere downstream —
        and critically, no per-provider branching in this method beyond which adapter originally
        supplied the LoadSearchResult being imported."""
```

**Schema change (the only one needed anywhere else in Operion for this whole subsystem):** add nullable `source: str`, `source_provider_id: str`, and `source_reference_id: str` columns to the existing `trips` table. That's it — every downstream module (Profit Calculator, Route Planner, Cost Engine, Fleet Health, Dispatch Board, Driver Manager, Invoice Generator, Analytics) operates on the resulting trip exactly as it would for a manually created one, because it *is* one, regardless of which freight exchange it originated from.

**Test requirement — this is the one that actually proves the design works, not just describes it (`tests/freight_exchange/test_import_parity.py`):** create three trips with identical field values — one manually, one imported from a fake `timocom` adapter, one imported from a fake `trans_eu` adapter — and run all three through every downstream service listed above, asserting bit-identical output across all three. If any downstream service behaves differently based on `source_provider_id`, that's a bug in this pipeline.

---

## 7. Evaluation Engine (provider-agnostic)

Turns any imported or searched load into real business numbers by **orchestrating existing engines — it computes nothing itself that already has a home elsewhere in Operion, and it has zero provider-specific logic.**

```python
# app/services/freight_exchange/evaluation.py

class VehicleCompatibility(BaseModel):
    vehicle_id: str
    compatible: bool
    reasons: list[str]     # i18n keys, e.g. "freight.compat.trailer_mismatch"

class DriverCompatibility(BaseModel):
    driver_id: str
    compatible: bool
    hours_remaining: float
    reasons: list[str]

class LoadEvaluation(BaseModel):
    provider_id: str
    provider_load_id: str
    estimated_revenue: "Money"
    fuel_cost: "Money"
    toll_cost: "Money"
    driver_salary: "Money"
    deadhead_distance_km: float
    expected_profit: "Money"
    profit_margin_pct: float
    estimated_duration_hours: float
    risk_score: float                                   # 0.0–1.0, higher = riskier
    vehicle_compatibility: list[VehicleCompatibility]
    driver_compatibility: list[DriverCompatibility]
    evaluated_at: datetime

class EvaluationEngineService:
    async def evaluate_load(self, company_id: str, provider_id: str, provider_load_id: str, candidate_vehicle_id: str | None = None) -> LoadEvaluation:
        """
        Delegates to services that already exist elsewhere in Operion:
          - trip_calculator_service  → revenue, profit, margin (the same Trip Calculator manual trips use)
          - cost_engine_service      → fuel, toll estimates
          - route_service            → deadhead distance, duration
        The ONLY genuinely new logic here is risk scoring (app/services/freight_exchange/risk_scoring.py) —
        nothing else in Operion scores freight risk today, so this is a real new module, not a wrapper.
        It operates on the normalized LoadSearchResult (§3) and has no idea which provider it came from.
        """
```

**Risk scoring (new, but must be concrete, not vibes):** a documented, weighted formula over factors such as delivery-window tightness, cross-border complexity, counterparty rating (where a provider exposes one), and price-vs-market-rate deviation. Define the exact weights in `risk_scoring.py` as named config, tunable per company, not hardcoded inline — the same "formula you can point to, not a black box" discipline used throughout this subsystem. **Do not let counterparty-rating logic vary by provider inside this module** — if a provider doesn't expose a rating, that input is simply absent from the formula for loads from that provider, handled generically, not with per-provider `if` branches here.

**Test requirement (`tests/freight_exchange/test_evaluation.py`):** fixture a known load (from a fake adapter) + known vehicle/driver data, assert every field in `LoadEvaluation` matches hand-calculated expected values, and assert the service made exactly one call each to `trip_calculator_service`, `cost_engine_service`, and `route_service` — proving it orchestrates rather than reimplements, and does so identically no matter which `provider_id` is on the input.

---

## 8. Fleet Matcher (provider-agnostic)

Scores every available truck against a given load — from any provider — **a ranked list with reasoning, never just "nearest truck."**

```python
# app/services/freight_exchange/fleet_matcher.py

class TruckMatchScore(BaseModel):
    vehicle_id: str
    driver_id: str | None
    score: float                      # 0–100
    rank: int
    reasons: list[str]                # i18n keys, e.g. "freight.match_reason.lowest_deadhead", ordered by contribution
    distance_to_pickup_km: float
    expected_deadhead_km: float
    expected_profit: "Money"
    driver_hours_remaining: float | None
    maintenance_status: str
    trailer_compatible: bool

class FleetMatcherService:
    async def find_best_trucks(self, company_id: str, provider_id: str, provider_load_id: str, top_n: int = 5) -> list[TruckMatchScore]: ...
```

**Scoring formula — explicit, tunable, weighted-sum, never a black box, and identical regardless of which provider the load came from:**

```
score = w1*proximity_score + w2*expected_profit_score + w3*driver_hours_score
      + w4*maintenance_health_score + w5*trailer_compatibility_score
      + w6*historical_reliability_score + w7*positioning_score

Inputs behind each factor: distance from truck to pickup; current truck location; fuel consumption;
maintenance health (from the existing Fleet Health computation) and upcoming maintenance; driver
remaining driving hours (from the existing hours-of-service check); trailer compatibility;
historical on-time/reliability record; expected deadhead; expected final profit (from §7's Evaluation
Engine); and a positioning-for-future-work factor (does this dispatch leave the truck somewhere with
good onward-load prospects).

Weights are per-company config, not hardcoded — a company that prioritizes profit over fleet
positioning should be able to tune this without a code change.
```

**`reasons` are derived directly from which scoring components contributed most to the final score — never a free-text explanation bolted on after the fact by anything non-deterministic.** This is what makes Fleet Matcher fully deterministic and testable.

Example output shape (the format the dispatcher-facing UI renders directly, with the source provider shown for context but otherwise irrelevant to the scoring):
```
Truck 12 — Score: 96  (load via TIMOCOM)
  • Closest suitable vehicle
  • Driver has sufficient remaining hours
  • Lowest deadhead among compatible trucks
  • Highest expected profit

Truck 8 — Score: 91
Truck 5 — Score: 84
```

**Test requirement (`tests/freight_exchange/test_fleet_matcher.py`):** fixture with known truck/driver/maintenance data, assert both the ranking order and each score component are exactly reproducible run to run for loads tagged with different `provider_id` values but otherwise identical data — proving `provider_id` genuinely has zero influence on the scoring itself.

---

## 9. Deterministic Service Layer

Only after §3–§8 are built, proven, and in real manual dispatcher use does this layer matter. It's simply the list of plain service methods every caller — a dispatcher-facing UI screen today, any automated caller later — invokes. No GUI-specific or provider-specific logic lives here; everything above is orchestration over the layers below.

| Deterministic method | Backed by |
|---|---|
| `search_loads(provider_ids=None)` | Search Engine (§5) — searches all connected providers by default |
| `refresh_search` | Search Engine (§5) |
| `save_search` | Search Engine (§5) |
| `get_recent_searches` | Search Engine (§5) |
| `import_load(provider_id, provider_load_id)` | Import Pipeline (§6) |
| `evaluate_load(provider_id, provider_load_id)` | Evaluation Engine (§7) |
| `calculate_profitability` | Evaluation Engine → existing Trip Calculator |
| `find_best_truck(s)(provider_id, provider_load_id)` | Fleet Matcher (§8) |
| `find_best_driver` | Fleet Matcher's driver-compatibility dimension |
| `recommend_dispatch` | Orchestrates `evaluate_load` + `find_best_trucks`, composed here — never duplicated logic |
| `generate_evaluation_report` | Evaluation Engine + existing Export Service |
| `list_connected_providers` | Connection Management (§4) — returns each connection's status/health for the settings UI |
| `connect_provider(provider_id)` / `disconnect_provider(provider_id)` | Connection Management (§4) |

This table is the intended integration surface for anything built on top of this subsystem in the future — but building that consumer is explicitly out of scope for this document. Every method already takes `provider_id` as an optional or explicit parameter, so a future automated caller (or the UI) can target "search everything" or "search just TIMOCOM" identically.

---

## 10. Adding a Second Provider (the payoff of building it this way)

This section exists to make the architectural claim in §1 checkable, not just asserted. When Trans.eu, Teleroute, Wtransnet, or any other freight exchange is added later, the work is:

1. Implement `TransEuAdapter(FreightProviderAdapter)` in `app/services/freight_exchange/adapters/trans_eu.py` — authenticate, search_loads, get_load, capabilities, mapped to Trans.eu's actual API shape.
2. Register it (`@register_freight_provider`).
3. Add a `freight_exchange_connections` row type for `provider_id='trans_eu'` (no schema change — the table is already provider-generic).
4. Add a "Connect Trans.eu" entry in the settings UI, reusing the same connection-flow component built for TIMOCOM.
5. Write `tests/freight_exchange/test_trans_eu_adapter.py` covering the same authenticate/search/health-check cases as the TIMOCOM adapter's tests.

**Nothing in §5 (Search Engine), §6 (Import Pipeline), §7 (Evaluation Engine), §8 (Fleet Matcher), or §9 (Deterministic Service Layer) changes.** If implementing a second provider ever requires touching any of those five, stop and treat it as a bug in this blueprint's abstraction rather than pushing the provider-specific change through — that's the concrete test of whether "provider-agnostic" actually held.

---

## 11. Future Automation (forward-looking note only — not part of this build)

Everything above is complete and independently valuable with zero AI involvement: a dispatcher can connect one or more freight exchanges, search across all of them at once, evaluate loads, and get ranked truck recommendations, entirely through a manual UI.

If Operion later adds an AI/automation layer (see the separate Operion AI Co-Pilot Blueprint document, if and when that's built), that layer should do nothing more than call the deterministic methods in §9 in some useful order and present the results — it should never re-implement search, evaluation, matching, or provider-specific logic itself, and it should never be given access to this subsystem before §12's gates are all met through real manual usage. That sequencing decision belongs to whichever document governs that layer; it is not a dependency of this one.

---

## 12. Build Sequencing & Gates

Each gate must be met by real usage evidence, not just code review, before the next layer starts:

1. **Provider Adapter Layer done when:** `TimocomAdapter` is fully implemented against the real TIMOCOM API, a dispatcher can click "test connection" in settings and get a real result, the health-check job runs on schedule across connected providers, and the adapter-level tests (§3, §4) pass. The adapter interface itself (not just the TIMOCOM implementation) should be reviewed at this gate specifically for provider-specific leakage.
2. **Search Engine done when:** a dispatcher can manually search with every filter listed in §3's `LoadSearchFilters`, see cached vs. fresh results behave correctly per provider, and save/recall searches. Still single-provider in practice at this point, but tested against the multi-provider-skip behavior (§5's test requirement) using a second fake adapter, so the multi-provider path is proven even before a second real provider exists.
3. **Import Pipeline done when:** a dispatcher has imported a real TIMOCOM load and the import-parity test (§6) passes — proving downstream modules genuinely can't tell the difference, and proving it generically (not "TIMOCOM-parity" but "any-provider-parity," per the three-way test in §6).
4. **Evaluation Engine done when:** evaluated numbers for several real loads have been manually spot-checked against hand calculation and match.
5. **Fleet Matcher done when:** dispatchers are actually using the ranked suggestions in real dispatch decisions, and the reproducibility test (§8) passes.
6. **Second provider (e.g. Trans.eu) done when:** §10's five-step process is followed with no changes required to §5–§9 — this is the gate that validates the whole architecture, not just a nice-to-have expansion.
7. **Only then** does this subsystem become a candidate for any future automation layer — and that's a separate build, governed by its own blueprint, not this one.

---

*End of blueprint. This document is intended to be fed section-by-section to coding agents as individual implementation prompts (§3 → §9), each gated by the corresponding checkpoint in §12 before the next section begins.*
