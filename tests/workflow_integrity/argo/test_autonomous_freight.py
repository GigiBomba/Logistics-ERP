"""ARGO-FREIGHT: §5.4 autonomous freight-exchange operations — search after delivery, evaluate/recommend, monitor.

Deterministic by construction: the world is built DIRECTLY from the ARGO
fixtures (``build_argo_world`` / ``make_tool_context``) — never through the
planner, never an LLM, and every provider call goes through a deterministic
seam.

Real tool classes exercised (registry-backed, same code the executor calls):

* ``FreightSearchLoadsTool``   — ``freight.search_loads`` (``freight_tools.py``)
  wraps ``SearchEngineService.search_loads`` (real health/capability gate +
  per-provider fan-out + result cap).  The ONLY mock is the provider adapter's
  ``search_loads``, which behaves like a real exchange server: it honours the
  exact ``LoadSearchFilters`` the REAL tool/engine path produced
  (origin city + radius, pickup schedule, capacity) and returns only loads
  that pass them.
* ``FreightEvaluateLoadTool``  — ``freight.evaluate_load`` wraps the real
  ``EvaluationEngineService`` (fetch via search engine → route estimate →
  CostEngine → risk scoring).  Provider ``get_load`` is the mocked seam.
* ``FreightRecommendDispatchTool`` — ``freight.recommend_dispatch`` runs the
  real evaluate → find-best-trucks → import-if-viable orchestration.
* ``FreightExchangeStatusTool`` / ``FreightMonitorTransportTool`` —
  ``freight.exchange_status`` reads real connection rows +
  ``ConnectionManagerService``; ``freight.monitor_transport`` runs the real
  tool body with only the HTTP ``TransEuClient.get`` seam mocked.

Provider seam
-------------
A ``freight_exchange_connections`` row (status ``connected``, long-lived
session) is seeded for the ARGO world's company against the REAL registered
``trans_eu`` adapter; only the adapter's network-touching methods
(``search_loads`` / ``get_load``) — or ``TransEuClient.get`` for monitoring —
are replaced with deterministic stand-ins.  Every filter construction, every
service call, every DB read and every result cap is real code.

Documented behavior (pinned by tests):

1. **``freight.recommend_dispatch`` respects fleet occupancy.**  When the
   whole healthy fleet is busy (``trucks.status = 'In Service'``, the exact
   state the dispatch availability checker blocks), the real tool refuses
   with ``status='failed'`` / ``load_viable=False`` and never ranks occupied
   trucks — Blueprint §5.4's "Bids without checking if truck is available"
   failure mode is closed.  An idle fleet still yields a recommendation.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest

# Importing the adapter modules self-registers the real adapters in the
# freight provider registry (services.freight_exchange.registry).
import services.freight_exchange.adapters.timocom  # noqa: F401
import services.freight_exchange.adapters.trans_eu  # noqa: F401

from backend.copilot.tools.freight_tools import (
    EvaluateLoadParams,
    ExchangeStatusParams,
    FreightEvaluateLoadTool,
    FreightExchangeStatusTool,
    FreightMonitorTransportTool,
    FreightRecommendDispatchTool,
    FreightSearchLoadsTool,
    MonitorTransportParams,
    RecommendDispatchParams,
    SearchLoadsParams,
)
from models.common import Money
from models.freight_exchange_models import LoadSearchFilters, LoadSearchResult
from services.freight_exchange import registry
from services.trans_eu.client import TransEuClient

from tests.workflow_integrity.argo.fixtures import (
    FREIGHT_LOADS,
    build_argo_world,
    make_tool_context,
    reset_circuit_breaker,
)

pytestmark = pytest.mark.argo

_PROVIDER = "trans_eu"
# Fixed (clock-free) exchange-feed timestamps — §5.8 determinism.
_BASE_DAY = date(2026, 7, 25)


# ── Autouse hygiene ───────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _registry_preservation():
    """Guarantee the real freight adapters stay registered across tests.

    The workflow-integrity suite has no autouse adapter-restorer of its own
    (the freight-exchange suite does).  Importing the adapter modules above
    registers ``trans_eu``/``timocom``; save the pre-test registry and restore
    it afterwards so this module can never leave the registry mutated for
    other ARGO / freight tests sharing the xdist worker.
    """
    before = dict(registry._registry)
    yield
    registry._registry.clear()
    registry._registry.update(before)


@pytest.fixture(autouse=True)
def _reset_circuit_breaker_after():
    """CircuitBreaker state is class-level — never leak into the next test."""
    yield
    reset_circuit_breaker()


# ── Deterministic helpers ─────────────────────────────────────────────────────

def _run(coro):
    """Run one async tool call inside a fresh event loop."""
    return asyncio.run(coro)


def _ctx(db, world):
    """ToolExecutionContext for the ARGO world (Ana, the dispatcher)."""
    return make_tool_context(
        db,
        company_id=world["company_id"],
        user_id=world["user_id"],
        role="dispatcher",
    )


def _seed_connection(db, company_id: int, provider_id: str = _PROVIDER) -> str:
    """Insert one connected provider session for the ARGO company."""
    conn_id = str(uuid.uuid4())
    session = json.dumps({
        "company_id": company_id,
        "provider_id": provider_id,
        "access_token_encrypted": "argo-test-token",
        "expires_at": "2099-01-01T00:00:00+00:00",
    })
    db.conn.execute(
        "INSERT INTO freight_exchange_connections (id, company_id, provider_id, "
        "credentials_encrypted, session_state, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, 'connected', ?)",
        (conn_id, company_id, provider_id, "encrypted-secret", session,
         datetime.now(timezone.utc).isoformat()),
    )
    db.conn.commit()
    return conn_id


def _feed_load(
    ref: str,
    origin: str,
    destination: str,
    price_eur: float,
    distance_km: float,
    pickup_date: date,
    weight_kg: float,
) -> LoadSearchResult:
    """Build one deterministic exchange-feed load (provider raw data shape)."""
    pickup = datetime(pickup_date.year, pickup_date.month, pickup_date.day,
                      8, 0, tzinfo=timezone.utc)
    return LoadSearchResult(
        result_id=ref,
        provider_id=_PROVIDER,
        provider_load_id=ref,
        origin=origin,
        destination=destination,
        pickup_window=(pickup, pickup + timedelta(hours=6)),
        delivery_window=(pickup + timedelta(hours=24), pickup + timedelta(hours=28)),
        price=Money(amount=price_eur, currency="EUR"),
        distance_km=distance_km,
        trailer_type="standard",
        adr=False,
        loading_country=origin.split(",")[-1].strip(),
        delivery_country=destination.split(",")[-1].strip(),
        weight_kg=weight_kg,
        loading_type="ftl",
    )


def _freight_feed() -> List[LoadSearchResult]:
    """The three canonical FREIGHT_LOADS as provider raw data.

    Weights are deterministic exchange-feed capacities (the shared fixture
    data has no weight column).  Schedules land on the fixed base day so a
    pickup-date-filtered search can select deterministically.
    """
    weights = {"TX-2026-0711": 26000.0, "TC-2026-0502": 12000.0, "TC-2026-0450": 15000.0}
    feed = []
    for load in FREIGHT_LOADS:
        feed.append(_feed_load(
            load["reference"],
            load["origin"],
            load["destination"],
            float(load["price_eur"]),
            float(load["distance_km"]),
            _BASE_DAY,
            weights[load["reference"]],
        ))
    return feed


def _provider_seam_search(seen: Dict[str, Any], feed: List[LoadSearchResult]):
    """Adapter-seam ``search_loads`` — behaves like the provider server.

    Records the real ``LoadSearchFilters`` the tool/engine produced, then
    honours them exactly the way an exchange server would: drops loads whose
    loading city is outside the requested origin, whose pickup falls outside
    the requested schedule, or whose weight exceeds the requested capacity.
    """
    async def _search(session, filters: LoadSearchFilters):
        seen["filters"] = filters
        origin_city = (
            filters.origin.location.split(",")[0].strip().lower()
            if filters.origin and filters.origin.location else ""
        )
        results = []
        for load in feed:
            city = load.origin.split(",")[0].strip().lower()
            if origin_city and city != origin_city:
                continue  # origin filter (loadingPlace + radius)
            if filters.pickup_date_from and filters.pickup_date_to:
                pickup = load.pickup_window[0].date()
                if not (filters.pickup_date_from <= pickup <= filters.pickup_date_to):
                    continue  # schedule filter (loadingDateFrom/To)
            if filters.weight_kg_max is not None and load.weight_kg > filters.weight_kg_max:
                continue  # capacity filter (weight_max)
            results.append(load)
        return results
    return _search


def _delivery_city_hint(db, world, index: int = 0) -> str:
    """Derive the return-load origin hint from a delivered trip row.

    The ARGO world's delivered trips are the fleet's last-completed
    deliveries; the loading place of the return leg is where a truck sits
    post-delivery.  We enrich the canonical delivered trip with that place
    and read it back through the SAME row a real workflow step would query.
    """
    trip_id = world["delivered_trip_ids"][index]
    db.conn.execute(
        "UPDATE trips SET place_of_loading = ?, loading_country = 'RO', "
        "delivery_country = 'RO' WHERE id = ?",
        ("Oradea, RO", trip_id),
    )
    db.conn.commit()
    row = db.conn.execute(
        "SELECT place_of_loading FROM trips WHERE id = ?", (trip_id,)
    ).fetchone()
    return row["place_of_loading"]


def _occupy_fleet(db, world) -> None:
    """Put every healthy truck into the dispatch-blocked busy state.

    ``trucks.status = 'In Service'`` is the canonical busy state the dispatch
    availability checker blocks (see test_autonomous_dispatch.py).  The update
    targets the world's healthy truck ids directly (persona trucks are not all
    stamped with a company_id in this schema layout).
    """
    ids = ",".join(str(tid) for tid in world["healthy_truck_ids"])
    db.conn.execute(
        f"UPDATE trucks SET status = 'In Service' WHERE id IN ({ids})",
    )
    db.conn.commit()


# ═════════════════════════════════════════════════════════════════════════════
# Scenario A — post-delivery return-load search filtering (§5.4 "return loads")
# ═════════════════════════════════════════════════════════════════════════════

class TestReturnLoadSearchFiltering:
    """ARGO-FREIGHT-A: after a delivery, search filters reachable loads."""

    def test_search_after_delivery_filters_by_origin_and_schedule(self, db):
        """Real tool path sends the delivered-city origin + schedule; unreachable loads are gone."""
        world = build_argo_world(db)
        _seed_connection(db, world["company_id"])
        hint = _delivery_city_hint(db, world)
        origin_city = hint.split(",")[0].strip()  # "Oradea"
        assert origin_city == "Oradea"

        # Feed: the 3 canonical loads on 2026-07-25 + one Oradea load that
        # loads on 2026-08-02 (same origin, wrong schedule).
        feed = _freight_feed()
        feed.append(_feed_load(
            "TC-2026-0451", "Oradea, RO", "Vienna, AT",
            1800.0, 600.0, date(2026, 8, 2), 12000.0,
        ))

        seen: Dict[str, Any] = {}
        adapter = registry.get_adapter(_PROVIDER)
        tool = FreightSearchLoadsTool()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(adapter, "search_loads", _provider_seam_search(seen, feed))
            result = _run(tool.execute(
                SearchLoadsParams(origin=origin_city, pickup_date="2026-07-25"),
                _ctx(db, world),
            ))

        assert result.status == "success", result
        # The REAL filter path reached the provider seam: origin city + radius
        # + exact pickup schedule.
        filters = seen["filters"]
        assert filters.origin.location == "Oradea"
        assert filters.origin.radius_km == 50.0
        assert filters.pickup_date_from == date(2026, 7, 25)
        assert filters.pickup_date_to == date(2026, 7, 25)
        # The engine really queried the connected provider (no capability skip).
        assert result.data["providers_queried"] == 1
        assert result.data["provider_statuses"] == [
            {"provider_id": _PROVIDER, "status": "ok", "error": ""}
        ]

        returned = {r["provider_load_id"] for r in result.data["results"]}
        # Reachable: same-city loading on the requested day.
        assert returned == {"TC-2026-0502"}
        # Unreachable loads excluded: wrong-origin loads (Cluj / Bucharest)
        # and the same-city load on the wrong loading date.
        assert "TX-2026-0711" not in returned
        assert "TC-2026-0450" not in returned
        assert "TC-2026-0451" not in returned

    def test_search_capacity_filter_excludes_overweight_reachable_load(self, db):
        """Real capacity filter (weight_kg_max) is sent; overweight load excluded."""
        world = build_argo_world(db)
        _seed_connection(db, world["company_id"])

        # Feed: the reachable Oradea load (12 t) plus an overweight Oradea
        # load (30 t) on the same day — capacity is the only differentiator.
        feed = _freight_feed()
        feed.append(_feed_load(
            "TX-2026-9999", "Oradea, RO", "Vienna, AT",
            2000.0, 620.0, _BASE_DAY, 30000.0,
        ))

        seen: Dict[str, Any] = {}
        adapter = registry.get_adapter(_PROVIDER)
        tool = FreightSearchLoadsTool()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(adapter, "search_loads", _provider_seam_search(seen, feed))
            result = _run(tool.execute(
                SearchLoadsParams(
                    origin="Oradea", pickup_date="2026-07-25", weight_kg=24000.0,
                ),
                _ctx(db, world),
            ))

        assert result.status == "success", result
        # Real filter path: the capacity cap reached the provider seam.
        assert seen["filters"].weight_kg_max == 24000.0

        returned = {r["provider_load_id"] for r in result.data["results"]}
        assert returned == {"TC-2026-0502"}
        assert "TX-2026-9999" not in returned  # 30 t > 24 t capacity


# ═════════════════════════════════════════════════════════════════════════════
# Scenario B — profitability + availability (§5.4 "Bid on load TX-1234")
# ═════════════════════════════════════════════════════════════════════════════

class TestEvaluateAndRecommend:
    """ARGO-FREIGHT-B: margin is computed; occupancy never checked (gap)."""

    def test_evaluate_load_computes_profit_margin(self, db):
        """Real evaluation engine returns a self-consistent positive margin."""
        world = build_argo_world(db)
        _seed_connection(db, world["company_id"])
        oradea = next(l for l in _freight_feed() if l.provider_load_id == "TC-2026-0502")

        adapter = registry.get_adapter(_PROVIDER)

        async def _get_load(session, load_id):
            return oradea if load_id == oradea.provider_load_id else None

        tool = FreightEvaluateLoadTool()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(adapter, "get_load", _get_load)
            result = _run(tool.execute(
                EvaluateLoadParams(
                    provider_id=_PROVIDER,
                    provider_load_id="TC-2026-0502",
                ),
                _ctx(db, world),
            ))

        assert result.status == "success", result
        data = result.data
        # Real code invariants across the returned LoadEvaluation:
        # expected_profit == revenue - (fuel + toll + driver salary), and the
        # margin is that profit over revenue.  Any drift = real bug.
        revenue = float(data["estimated_revenue"]["amount"])
        fuel = float(data["fuel_cost"]["amount"])
        toll = float(data["toll_cost"]["amount"])
        salary = float(data["driver_salary"]["amount"])
        profit = float(data["expected_profit"]["amount"])

        assert revenue == 1500.0  # the load's listed price
        assert profit == pytest.approx(revenue - fuel - toll - salary)
        assert data["profit_margin_pct"] == pytest.approx(profit / revenue * 100.0)
        assert profit > 0  # a profitable load stays profitable through the real engine
        assert 0.0 <= data["risk_score"] <= 1.0
        assert data["provider_load_id"] == "TC-2026-0502"

    def test_recommend_dispatch_refuses_when_fleet_occupied(self, db):
        """Guard: recommend_dispatch refuses when no truck is dispatchable.

        With every healthy truck in the busy state the dispatch availability
        checker blocks (``status = 'In Service'``), the real
        ``freight.recommend_dispatch`` must refuse (``failed``,
        ``load_viable=False``, no ranking) instead of bidding on the load
        with an occupied fleet — Blueprint §5.4's "Bids without checking if
        truck is available" failure mode.
        """
        world = build_argo_world(db)
        _seed_connection(db, world["company_id"])
        _occupy_fleet(db, world)

        busy = db.conn.execute(
            "SELECT COUNT(*) AS n FROM trucks WHERE status = 'In Service' AND id IN (%s)"
            % ",".join("?" * len(world["healthy_truck_ids"])),
            tuple(world["healthy_truck_ids"]),
        ).fetchone()["n"]
        assert busy == len(world["healthy_truck_ids"])

        oradea = next(l for l in _freight_feed() if l.provider_load_id == "TC-2026-0502")
        adapter = registry.get_adapter(_PROVIDER)

        async def _get_load(session, load_id):
            return oradea if load_id == oradea.provider_load_id else None

        async def _no_search(session, filters):
            return []

        tool = FreightRecommendDispatchTool()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(adapter, "get_load", _get_load)
            mp.setattr(adapter, "search_loads", _no_search)
            result = _run(tool.execute(
                RecommendDispatchParams(
                    provider_id=_PROVIDER,
                    provider_load_id="TC-2026-0502",
                    top_n=3,
                ),
                _ctx(db, world),
            ))

        # Occupied fleet ⇒ refusal: the load is not deemed viable and no
        # occupied truck is ever ranked.
        assert result.status == "failed", result
        assert result.data["load_viable"] is False
        assert result.data["best_trucks"] == []
        assert result.message_key == (
            "copilot.tool.freight.recommend_dispatch_no_available_trucks"
        )

    def test_recommend_dispatch_ranks_available_trucks_when_fleet_idle(self, db):
        """Companion: an available fleet still yields a recommendation.

        The ARGO world's healthy trucks are ``status='active'`` /
        ``active_status=1``; the guard must not block them.
        """
        world = build_argo_world(db)
        _seed_connection(db, world["company_id"])

        oradea = next(l for l in _freight_feed() if l.provider_load_id == "TC-2026-0502")
        adapter = registry.get_adapter(_PROVIDER)

        async def _get_load(session, load_id):
            return oradea if load_id == oradea.provider_load_id else None

        async def _no_search(session, filters):
            return []

        tool = FreightRecommendDispatchTool()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(adapter, "get_load", _get_load)
            mp.setattr(adapter, "search_loads", _no_search)
            result = _run(tool.execute(
                RecommendDispatchParams(
                    provider_id=_PROVIDER,
                    provider_load_id="TC-2026-0502",
                    top_n=3,
                ),
                _ctx(db, world),
            ))

        assert result.status == "success", result
        assert result.data["load_viable"] is True
        assert len(result.data["best_trucks"]) >= 1
        assert result.message_key == "copilot.tool.freight.recommend_dispatch_ok"

    def test_recommend_dispatch_ranks_only_available_trucks(self, db):
        """Partial availability: occupied trucks are excluded from the ranking.

        Only the one idle truck may appear in ``best_trucks`` — the busy
        trucks must never be recommended.
        """
        world = build_argo_world(db)
        _seed_connection(db, world["company_id"])

        available_id = world["healthy_truck_ids"][0]
        occupied = world["healthy_truck_ids"][1:]
        db.conn.execute(
            "UPDATE trucks SET status = 'In Service' WHERE id IN (%s)"
            % ",".join("?" * len(occupied)),
            tuple(occupied),
        )
        db.conn.commit()

        oradea = next(l for l in _freight_feed() if l.provider_load_id == "TC-2026-0502")
        adapter = registry.get_adapter(_PROVIDER)

        async def _get_load(session, load_id):
            return oradea if load_id == oradea.provider_load_id else None

        async def _no_search(session, filters):
            return []

        tool = FreightRecommendDispatchTool()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(adapter, "get_load", _get_load)
            mp.setattr(adapter, "search_loads", _no_search)
            result = _run(tool.execute(
                RecommendDispatchParams(
                    provider_id=_PROVIDER,
                    provider_load_id="TC-2026-0502",
                    top_n=5,
                ),
                _ctx(db, world),
            ))

        assert result.status == "success", result
        assert result.data["load_viable"] is True
        returned_ids = {m["vehicle_id"] for m in result.data["best_trucks"]}
        assert returned_ids == {available_id}
        assert returned_ids.isdisjoint(set(occupied))

    def test_recommend_dispatch_refuses_on_empty_fleet(self, db):
        """Empty fleet: no trucks at all ⇒ refusal, never a success.

        The ARGO persona trucks carry ``company_id = NULL`` (the test world's
        tenant convention — repos run unscoped because the tenant context is
        never set here), so the fleet is emptied by soft-deleting every truck
        row regardless of ``company_id``.
        """
        world = build_argo_world(db)
        _seed_connection(db, world["company_id"])
        db.conn.execute(
            "UPDATE trucks SET deleted_at = ?",
            ("2026-01-01T00:00:00+00:00",),
        )
        db.conn.commit()

        remaining = db.conn.execute(
            "SELECT COUNT(*) AS n FROM trucks WHERE deleted_at IS NULL"
        ).fetchone()["n"]
        assert remaining == 0

        oradea = next(l for l in _freight_feed() if l.provider_load_id == "TC-2026-0502")
        adapter = registry.get_adapter(_PROVIDER)

        async def _get_load(session, load_id):
            return oradea if load_id == oradea.provider_load_id else None

        async def _no_search(session, filters):
            return []

        tool = FreightRecommendDispatchTool()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(adapter, "get_load", _get_load)
            mp.setattr(adapter, "search_loads", _no_search)
            result = _run(tool.execute(
                RecommendDispatchParams(
                    provider_id=_PROVIDER,
                    provider_load_id="TC-2026-0502",
                    top_n=3,
                ),
                _ctx(db, world),
            ))

        assert result.status == "failed", result
        assert result.data["load_viable"] is False
        assert result.data["best_trucks"] == []
        assert result.message_key == (
            "copilot.tool.freight.recommend_dispatch_no_available_trucks"
        )


# ═════════════════════════════════════════════════════════════════════════════
# Scenario C — monitoring (§5.4 "Monitor load TX-1234 status")
# ═════════════════════════════════════════════════════════════════════════════

class TestFreightMonitoring:
    """ARGO-FREIGHT-C: connected-provider status and transport monitoring."""

    def test_exchange_status_surfaces_connected_monitoring_provider(self, db):
        """freight.exchange_status reports the real connected provider + monitoring capability."""
        world = build_argo_world(db)
        _seed_connection(db, world["company_id"])

        result = _run(FreightExchangeStatusTool().execute(
            ExchangeStatusParams(provider_id=_PROVIDER),
            _ctx(db, world),
        ))

        assert result.status == "success", result
        assert result.data["total"] == 1
        provider = result.data["providers"][0]
        assert provider["provider_id"] == _PROVIDER
        assert provider["status"] == "connected"
        # The registry adapter's real capability metadata says monitoring is
        # supported — the precondition the monitor tool relies on.
        assert provider["capabilities"]["supports_monitoring"] is True

    def test_monitor_transport_surfaces_status_record(self, db):
        """freight.monitor_transport returns the provider's transport status record.

        The real tool body runs end-to-end (session lookup, TransEuClient call,
        payload assembly); only the HTTP ``TransEuClient.get`` is mocked.
        """
        world = build_argo_world(db)
        _seed_connection(db, world["company_id"])

        transport_record = {
            "id": "TR-2026-1234",
            "status": "active",
            "vehiclePosition": {"latitude": 47.49, "longitude": 19.04},
            "events": [
                {"type": "loading_completed", "occurredAt": "2026-07-25T09:00:00Z"},
                {"type": "departed", "occurredAt": "2026-07-25T10:12:00Z"},
            ],
        }

        async def _fake_client_get(access_token, path, params=None):
            return dict(transport_record)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(TransEuClient, "get", _fake_client_get)
            result = _run(FreightMonitorTransportTool().execute(
                MonitorTransportParams(
                    provider_id=_PROVIDER,
                    transport_id="TR-2026-1234",
                ),
                _ctx(db, world),
            ))

        assert result.status == "success", result
        assert result.message_key == "copilot.tool.freight.monitor_transport_ok"
        record = result.data["transport"]
        # The tracking/event record surfaced by the monitor is the provider's.
        assert record["id"] == "TR-2026-1234"
        assert record["status"] == "active"
        assert [e["type"] for e in record["events"]] == ["loading_completed", "departed"]
