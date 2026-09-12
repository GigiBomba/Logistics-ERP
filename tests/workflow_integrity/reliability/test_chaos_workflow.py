"""CH-1 through CH-10: Chaos / Resilience at each workflow step.

Each test injects a failure at a specific workflow step through a REAL
service seam (mirroring the sibling chaos tests in ``reliability/chaos``)
and verifies that the system recovers gracefully — either via fallback,
queued retry, or clean error that leaves DB state consistent.

Real seams exercised (all synchronous, no ``time.sleep``):

* CH-1  — ``SearchEngineService.get_load`` (freight-exchange importer seam,
          blueprint §8.5.1).
* CH-2  — ``RouteService.calculate_route`` (GraphHopper routing seam,
          blueprint §8.5.2) + the evaluation engine's documented estimate
          fallback.
* CH-3  — ``FuelPriceService._do_refresh_all`` (fuel-price service seam,
          blueprint §8.5.3) + the ``get_price_with_cache`` FETCH_FAILED
          fallback and the ``TripCalculator`` default-price path.
* CH-4  — ``BaseRepository.commit_transaction`` (commit seam, blueprint
          §8.5.4) inside the real dispatch transaction — rollback,
          both-or-neither.
* CH-5  — EventBus/NotificationCenter notification-sender subscribers
          (driver FCM push seam, blueprint §8.5.5) — failure is contained,
          dispatch completes, the alert/observability side keeps a record.
* CH-6  — ``MobileClient`` offline queue + idempotency-key replay (dedup,
          blueprint §8.5.6 / P9) — exactly one Delivered transition.
* CH-7  — ``ImageProcessor.process`` (PaddleOCR seam, blueprint §8.5.7) —
          document stays persisted / awaiting OCR, re-runnable.
* CH-8  — ``InvoiceGenerator.generate`` (PDF-generation seam, blueprint
          §8.5.8) — draft persists, status unchanged, retry succeeds.
* CH-9  — ``AnalyticsRepository.get_overdue_data`` (analytics aggregation
          seam, blueprint §8.5.9) — caller guard returns empty, no crash.
* CH-10 — dispatch commit failure (cascade, blueprint §8.5.10) — trip stays
          Planned, downstream delivery/invoice steps stay blocked.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import tempfile
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest

from models.common import Money
from models.freight_exchange_models import LoadSearchResult
from models.invoice_models import InvoiceCreate
from repositories.analytics_repository import AnalyticsRepository
from repositories.document_repository import DocumentRepository
from repositories.trip_repository import TripRepository
from services.dispatch_service.errors import InvalidStatusTransitionError
from services.operations.event_bus import VALID_TRANSITIONS
from services.route_service import RouteService
from tests.workflow_integrity.personas.fixtures import (
    seed_client,
    seed_company,
    seed_driver,
    seed_trip,
    seed_truck,
)

pytestmark = pytest.mark.chaos_workflow

# ── Shared seams / constants ───────────────────────────────────────────────

_IMAGE_PROCESS_SEAM = (
    "services.document_automation.image_processor.ImageProcessor.process"
)
_OCR_EXTRACTOR_SEAM = (
    "services.document_automation.ocr_extractor.OcrExtractor.extract"
)


# ── Shared helpers ─────────────────────────────────────────────────────────

def _count(db, sql: str, params: tuple = ()) -> int:
    """Run a scalar COUNT and return the integer."""
    return int(db.conn.execute(sql, params).fetchone()[0])


def _trip_row(db, trip_id: int) -> dict:
    """Read the persisted trip row back through the repository layer."""
    row = TripRepository(db).get_by_id(trip_id)
    if row is None:
        raise AssertionError(f"trip #{trip_id} not found in repository")
    return row


def _doc_row(db, doc_id: int) -> dict:
    return dict(
        db.conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
    )


def _make_source_pdf(marker: str) -> str:
    """Create a small fake PDF on disk; return its path."""
    f = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, mode="w")
    f.write(f"%PDF-1.4 {marker} cmr document")
    f.close()
    return f.name


def _unlink_quietly(path: str) -> None:
    try:
        if path and os.path.isfile(path):
            os.unlink(path)
    except OSError:
        pass


def _make_load(provider_id: str = "trans_eu", provider_load_id: str = "TX-1",
               *, distance_km: float = 850.0, amount: float = 2450.0) -> LoadSearchResult:
    """A normalized ``LoadSearchResult`` (the adapter seam's output)."""
    return LoadSearchResult(
        result_id=f"{provider_id}-{provider_load_id}",
        provider_id=provider_id,
        provider_load_id=provider_load_id,
        origin="Timisoara, RO",
        destination="Munich, DE",
        pickup_window=(datetime(2026, 8, 1, 8, 0), datetime(2026, 8, 1, 12, 0)),
        delivery_window=(datetime(2026, 8, 3, 8, 0), datetime(2026, 8, 3, 16, 0)),
        price=Money(amount=amount, currency="EUR"),
        distance_km=distance_km,
        trailer_type="curtainsider",
        adr=False,
    )


def _seed_dispatch_target(db) -> dict:
    """Seed an isolated dispatch target (company + client + free truck/driver +
    an unassigned Planned trip) — mirrors ``test_service_cascade``."""
    company_id = seed_company(db, company_name="Cascade Chaos SRL",
                              subscription_tier="professional")
    client_id = seed_client(db, name="Cascade Chaos Client")
    driver_id = seed_driver(db, company_id=company_id, name="Cascade Driver",
                            license_number="RO-CASCADE-001")
    truck_id = seed_truck(db, plate_number="B-777-CAS", company_id=company_id)
    trip_id = seed_trip(
        db,
        company_id=company_id,
        client_id=client_id,
        client_name="Cascade Chaos Client",
        status="Planned",
        driver_name="",
        driver_id=None,
        truck_number="",
        truck_id=None,
        distance_km=500.0,
        total_price_eur=1500.0,
    )
    return {
        "company_id": company_id,
        "client_id": client_id,
        "driver_id": driver_id,
        "driver_name": "Cascade Driver",
        "truck_id": truck_id,
        "trip_id": trip_id,
    }


def _run_failing_dispatch(db, dispatch_service, ids: dict) -> None:
    """Run one atomic dispatch whose DB commit fails once (rolls back).

    ``commit_transaction`` (the wrapper around ``db.conn.commit()``) raises
    like a DB drop at the commit point; the repository ``transaction()``
    context manager runs the real sqlite rollback and re-raises.
    """
    trip_repo = TripRepository(db)
    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        with patch.object(
            trip_repo,
            "commit_transaction",
            side_effect=sqlite3.OperationalError("database is locked"),
        ):
            with trip_repo.transaction():
                result = dispatch_service.assign_both(
                    ids["trip_id"],
                    truck_id=ids["truck_id"],
                    driver_id=ids["driver_id"],
                )
                assert result.success is True


# ═════════════════════════════════════════════════════════════════════════
# CH-1 — Lead capture: freight exchange (TransEU) timeout
# ═════════════════════════════════════════════════════════════════════════

class TestChaosLeadCapture:
    """CH-1: Lead capture — freight exchange timeout."""

    def test_freight_exchange_timeout_graceful(self, db):
        """Simulate freight exchange API timeout — no lead is lost.

        The importer seam (``SearchEngineService.get_load``) raises
        ``TimeoutError`` during the failure window; nothing is persisted.
        The real pipeline has no retry queue (documented gap), so the
        recovery contract is: the retry after the exchange recovers
        imports the load exactly once and the trip is not lost.
        """
        from services.freight_exchange.import_pipeline import (
            ImportPipelineService,
        )
        from services.freight_exchange.search import SearchEngineService

        # Client 0 is the dispatcher-assignment placeholder the import
        # mapping uses; it must exist for the real TripService validation.
        db.conn.execute(
            "INSERT OR IGNORE INTO clients (id, name, email, phone, address, "
            "vat_number, is_active, created_at, updated_at) "
            "VALUES (0, 'Freight Exchange Import', 'freight@import.local', "
            "'+40-0', 'n/a', 'RO-FX-0', 1, datetime('now'), datetime('now'))"
        )
        db.conn.commit()

        pipeline = ImportPipelineService(db)
        load = _make_load("trans_eu", "TX-CHAOS-1", distance_km=850.0)
        trips_before = _count(db, "SELECT COUNT(*) FROM trips")

        # TransEU API times out while importing the won load.
        with patch.object(
            SearchEngineService, "get_load",
            new=AsyncMock(side_effect=TimeoutError("TransEU API timed out")),
        ):
            with pytest.raises(TimeoutError, match="TransEU API timed out"):
                asyncio.run(pipeline.import_load(
                    company_id=1, provider_id="trans_eu",
                    provider_load_id="TX-CHAOS-1", user_id=0,
                ))

        # No lead/trip lost: nothing persisted during the failure window.
        assert _count(db, "SELECT COUNT(*) FROM trips") == trips_before

        # Retry after the exchange recovers — import succeeds exactly once
        # and stamps the freight-exchange source metadata on the trip.
        # ``import_load`` dispatches the real ``TripService.create`` through
        # ``asyncio.to_thread``; the in-memory test DB is thread-local (each
        # thread gets its own empty ``:memory:`` connection), so the thread
        # boundary is bridged inline for the test environment only.
        with patch.object(
            SearchEngineService, "get_load", new=AsyncMock(return_value=load),
        ), patch(
            "services.freight_exchange.import_pipeline.asyncio.to_thread",
            side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs),
        ):
            result = asyncio.run(pipeline.import_load(
                company_id=1, provider_id="trans_eu",
                provider_load_id="TX-CHAOS-1", user_id=0,
            ))

        assert result.trip_id > 0
        assert result.source == "freight_exchange"
        assert result.source_provider_id == "trans_eu"
        assert result.source_reference_id == "TX-CHAOS-1"
        assert _count(db, "SELECT COUNT(*) FROM trips") == trips_before + 1
        row = db.conn.execute(
            "SELECT status, source, source_provider_id, source_reference_id "
            "FROM trips WHERE id = ?",
            (result.trip_id,),
        ).fetchone()
        assert row["status"] == "Planned"
        assert row["source"] == "freight_exchange"
        assert row["source_provider_id"] == "trans_eu"
        assert row["source_reference_id"] == "TX-CHAOS-1"

    def test_freight_exchange_partial_response_handled(self, workflow_env, db):
        """CH-1b: Trip creation must still work when external data is incomplete.

        Simulates a partial freight exchange response by creating a trip with
        minimal data — the system should not crash or produce inconsistent state
        when external services return partial payloads.
        """
        from tests.workflow_integrity.personas import build_ana_persona
        ids = build_ana_persona(db)
        # Create a trip with minimal data (simulating partial external response)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
            # Minimal required data — TripCreate requires distance_km > 0
            price_eur=1000.0,
            distance_km=1.0,
            fuel_cost=0.0,
            toll_cost=0.0,
            salary_cost=0.0,
            extra_costs=0.0,
            net_profit=1000.0,
        )
        assert trip_id > 0, "Trip creation should succeed with partial data"
        trip = workflow_env.get_trip(trip_id)
        assert trip is not None
        assert trip["status"] == "Planned"
        # Verify DB is consistent
        integrity = db.conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity == "ok"


# ═════════════════════════════════════════════════════════════════════════
# CH-2 — Route planning: GraphHopper timeout
# ═════════════════════════════════════════════════════════════════════════

class TestChaosRoutePlanning:
    """CH-2: Route planning — GraphHopper timeout."""

    def test_graphhopper_timeout_fallback(self, db, workflow_env):
        """Route planning failure falls back to distance estimation.

        The routing seam (``RouteService.calculate_route``) raises — the real
        evaluation engine catches it and continues with the documented
        estimate fallback (``distance_km or 500.0`` and per-km cost defaults).
        The estimated values flow into a real trip creation.
        """
        from services.freight_exchange.evaluation import EvaluationEngineService

        engine = EvaluationEngineService(db)
        # Provider reported no distance, so only the estimate path applies.
        load = _make_load("trans_eu", "RX-CHAOS-1", distance_km=0.0)

        with patch.object(
            engine._search, "get_load", new=AsyncMock(return_value=load),
        ), patch.object(
            RouteService, "calculate_route",
            side_effect=RuntimeError("GraphHopper API timed out"),
        ):
            evaluation = asyncio.run(engine.evaluate_load(
                company_id=1, provider_id="trans_eu",
                provider_load_id="RX-CHAOS-1",
            ))

        # Actual fallback behavior: 500 km deadhead estimate at ~60 km/h…
        assert evaluation.deadhead_distance_km == 500.0
        assert evaluation.estimated_duration_hours == pytest.approx(500.0 / 60.0)
        # …and the documented per-km cost defaults (fuel/toll/salary).
        assert float(evaluation.fuel_cost.amount) == 500.0 * 0.35
        assert float(evaluation.toll_cost.amount) == 500.0 * 0.08
        assert float(evaluation.driver_salary.amount) == 500.0 * 0.12
        # Profit is still computable from the estimated numbers.
        assert float(evaluation.expected_profit.amount) == pytest.approx(
            float(load.price.amount) - 500.0 * (0.35 + 0.08 + 0.12)
        )

        # Trip creation still succeeds with the estimated values.
        trip_id = workflow_env.create_trip(
            distance_km=evaluation.deadhead_distance_km,
            price_eur=float(evaluation.estimated_revenue.amount),
            fuel_cost=float(evaluation.fuel_cost.amount),
            toll_cost=float(evaluation.toll_cost.amount),
            salary_cost=float(evaluation.driver_salary.amount),
            net_profit=float(evaluation.expected_profit.amount),
            status="Planned",
        )
        assert trip_id > 0, "Trip creation must survive a GraphHopper timeout"
        trip = workflow_env.get_trip(trip_id)
        assert float(trip["distance_km"]) == 500.0
        assert float(trip["net_profit"]) > 0


# ═════════════════════════════════════════════════════════════════════════
# CH-3 — Profit calculation: fuel price service unavailable
# ═════════════════════════════════════════════════════════════════════════

class TestChaosProfitCalculation:
    """CH-3: Profit calculation — fuel price service unavailable."""

    def test_fuel_price_service_unavailable_uses_default(self, db):
        """Profit calculation uses cached/default fuel price when the API is down.

        The fuel-price fetch seam (``_do_refresh_all``) fails — the real
        ``get_price_with_cache`` returns ``success=False`` with the default
        price 1.55 and a ``FETCH_FAILED`` error; ``get_price`` still yields a
        usable fallback and the calculator computes profit with it.
        """
        from services.calculator import TripCalculator
        from services.fuel_price_service import FuelPriceService
        from models.calculator_models import CalculationRequest

        with patch.object(FuelPriceService, "_do_refresh_all", return_value=False):
            svc = FuelPriceService()

            # Live fetch failed → fallback result, not a crash.
            result = svc.get_price_with_cache(force_refresh=True)
            assert result.success is False
            assert result.data == 1.55
            codes = [e.code for e in result.errors]
            assert "FETCH_FAILED" in codes
            # Deterministic reads still produce a usable default price.
            assert svc.get_price("RO") > 0
            assert svc.is_available() is True

        # The calculator runs with the default price — profit still computable.
        calc = TripCalculator()
        calc_result = calc.calculate(CalculationRequest(
            km=1200.0, price_eur=4800.0, fuel_price=1.55,
            days=3.0, consum_litri=30.0,
        ))
        assert calc_result.success is True
        data = calc_result.data
        assert data is not None
        assert data.net_profit > 0
        assert data.fuel_cost == pytest.approx((1200.0 / 100.0) * 30.0 * 1.55)


# ═════════════════════════════════════════════════════════════════════════
# CH-4 — Dispatch: DB disconnect mid-dispatch
# ═════════════════════════════════════════════════════════════════════════

class TestChaosDispatch:
    """CH-4: Dispatch — DB disconnect mid-dispatch."""

    def test_db_disconnect_mid_dispatch_rollback(self, db, dispatch_service):
        """Dispatch is atomic — truck + driver assigned both or neither.

        The commit seam (``BaseRepository.commit_transaction``) dies at the
        commit point; the real transaction rolls back.  The persisted trip
        is back to the exact pre-dispatch state and no phantom assignment /
        invoice / history rows appeared anywhere.
        """
        ids = _seed_dispatch_target(db)
        trip_id = ids["trip_id"]
        invoice_count_before = _count(db, "SELECT COUNT(*) FROM invoices")
        history_before = _count(
            db,
            "SELECT COUNT(*) FROM trip_status_history WHERE trip_id = ?",
            (trip_id,),
        )

        _run_failing_dispatch(db, dispatch_service, ids)

        # Rolled back to the pre-dispatch state (verified via the repository).
        row = _trip_row(db, trip_id)
        assert row["status"] == "Planned"
        assert row["truck_id"] is None
        assert row["driver_id"] is None
        assert (row.get("truck_number") or "") == ""
        assert (row.get("driver_name") or "") == ""

        # Neither the truck nor the driver was persisted on any trip.
        assert _count(
            db, "SELECT COUNT(*) FROM trips WHERE truck_id = ?",
            (ids["truck_id"],),
        ) == 0
        assert _count(
            db, "SELECT COUNT(*) FROM trips WHERE driver_id = ?",
            (ids["driver_id"],),
        ) == 0

        # No phantom downstream rows during the failure window.
        assert _count(db, "SELECT COUNT(*) FROM invoices") == invoice_count_before
        assert _count(
            db,
            "SELECT COUNT(*) FROM trip_status_history WHERE trip_id = ?",
            (trip_id,),
        ) == history_before


# ═════════════════════════════════════════════════════════════════════════
# CH-5 — Driver notification: FCM push fails
# ═════════════════════════════════════════════════════════════════════════

class TestChaosDriverNotification:
    """CH-5: Driver notification — FCM push fails."""

    def test_fcm_push_fails_dispatch_still_completes(
        self, db, dispatch_service, event_bus, event_monitor, alert_manager
    ):
        """Notification failure must not block dispatch — and must be observable.

        A failing notification sender (the FCM push path) is registered on the
        assignment event channel: the EventBus contains every subscriber
        failure (event still recorded, healthy subscribers still run) and the
        dispatch itself is best-effort fire-and-forget — the assignment is
        persisted and the trip status is untouched.  The alert/observability
        pipeline (AlertManager → NotificationCenter) then records the
        driver-assignment alert durably even while its push sender raises.
        """
        from services.operations.alert_manager import AlertType, Severity
        from services.operations.notification_center import NotificationCenter

        ids = _seed_dispatch_target(db)
        trip_id = ids["trip_id"]

        event_monitor.track("trip.assigned", "alert.created")

        # ── Part 1: failing FCM push sender on the assignment channel ──
        healthy_deliveries: list[dict] = []

        def _failing_push_sender(ev: dict) -> None:
            raise RuntimeError("FCM push delivery failed")

        def _healthy_in_app_sender(ev: dict) -> None:
            healthy_deliveries.append(ev)

        event_bus.subscribe("trip.assigned", _failing_push_sender)
        event_bus.subscribe("trip.assigned", _healthy_in_app_sender)

        # Dispatch with the push sender dying mid-dispatch — still succeeds.
        result = dispatch_service.assign_both(
            trip_id, truck_id=ids["truck_id"], driver_id=ids["driver_id"]
        )
        assert result.success is True

        row = _trip_row(db, trip_id)
        assert row["truck_id"] == ids["truck_id"]
        assert row["driver_id"] == ids["driver_id"]
        # Notification failure never touches the trip status.
        assert row["status"] == "Planned"

        # Observability: both assignment events were recorded even though the
        # FCM sender raised, and the healthy in-app path still delivered them.
        assigned = event_monitor.get_events("trip.assigned")
        assert len(assigned) == 2
        truck_evs = [e for e in assigned if e["data"].get("truck_id") is not None]
        driver_evs = [e for e in assigned if e["data"].get("driver_id") is not None]
        assert len(truck_evs) == 1 and truck_evs[0]["data"]["truck_id"] == ids["truck_id"]
        assert len(driver_evs) == 1 and driver_evs[0]["data"]["driver_id"] == ids["driver_id"]
        assert len(healthy_deliveries) == 2

        # ── Part 2: alert/notification pipeline survives a sender crash ──
        nc = NotificationCenter(db)
        healthy_alerts: list[dict] = []

        def _raising_notifier(event_type: str, alert_data: dict) -> None:
            raise RuntimeError("FCM send failed")

        nc.subscribe(_raising_notifier)
        nc.subscribe(lambda et, ad: healthy_alerts.append(ad))

        alert = alert_manager.create_alert(
            alert_type=AlertType.POLICY_VIOLATION,
            severity=Severity.WARNING,
            title="Driver assignment",
            message=f"Trip #{trip_id} dispatched",
            trip_id=str(trip_id),
            metadata={"driver_id": ids["driver_id"]},
        )
        # The failing notifier did not crash the alert pipeline…
        assert alert is not None
        # …the observability side recorded it durably (DB row)…
        alert_row = db.conn.execute(
            "SELECT id, trip_id FROM alerts WHERE id = ?", (alert.id,)
        ).fetchone()
        assert alert_row is not None
        assert alert_row["trip_id"] == trip_id
        assert alert_manager.get_alert(alert.id) is not None
        # …the ALERT_CREATED event is on the bus…
        alert_events = event_monitor.get_events("alert.created")
        assert len(alert_events) == 1
        assert alert_events[0]["data"]["alert"]["id"] == alert.id
        # …and the healthy subscriber still received the alert payload.
        assert any(ad.get("id") == alert.id for ad in healthy_alerts)


# ═════════════════════════════════════════════════════════════════════════
# CH-6 — Delivery: offline status update + duplicate replay
# ═════════════════════════════════════════════════════════════════════════

class TestChaosDelivery:
    """CH-6: Delivery — offline status update."""

    def test_offline_delivery_status_stored_locally(
        self, db, trip_service, event_monitor
    ):
        """Offline 'Delivered' + duplicate replay → exactly one transition.

        The driver double-submits the Delivered update while offline (network
        retry).  The real idempotency-key dedup (reused from the network
        partition tests) applies the transition exactly once and reports the
        duplicate discard per-action.
        """
        from tests.workflow_integrity.fixtures.multi_platform_client import (
            MobileClient,
        )
        from tests.workflow_integrity.personas import build_ionut_persona

        ids = build_ionut_persona(db)
        in_transit_id = ids["trip_ids"]["in_transit"]
        event_monitor.track("trip.status_changed")

        mobile = MobileClient(trip_service, db)
        # Same logical intent queued twice while the network is down.
        mobile.update_status(in_transit_id, "Delivered", offline=True,
                             idempotency_key="chaos6-delivered")
        mobile.update_status(in_transit_id, "Delivered", offline=True,
                             idempotency_key="chaos6-delivered")
        assert mobile.pending_actions() == 2
        assert trip_service.get_by_id(in_transit_id)["status"] == "In Transit"

        results = mobile.sync_queue()
        assert len(results) == 2

        applied = [r for r in results if r["applied"]]
        deduped = [r for r in results if not r["applied"]]
        # First copy applied through the real transition path…
        assert len(applied) == 1
        assert applied[0]["action"] == "update_status"
        assert applied[0]["idempotency_key"] == "chaos6-delivered"
        assert applied[0]["result"] is True
        # …the duplicate was intercepted and reported, not silently dropped.
        assert len(deduped) == 1
        assert deduped[0]["idempotency_key"] == "chaos6-delivered"
        assert deduped[0]["result"] is None

        assert mobile.pending_actions() == 0
        assert mobile.replayed_keys() == {"chaos6-delivered"}
        # Exactly one recorded transition → one event; final state Delivered.
        event_monitor.assert_event_count("trip.status_changed", 1)
        assert trip_service.get_by_id(in_transit_id)["status"] == "Delivered"


# ═════════════════════════════════════════════════════════════════════════
# CH-7 — OCR: PaddleOCR crash
# ═════════════════════════════════════════════════════════════════════════

class TestChaosOCR:
    """CH-7: OCR — PaddleOCR crash."""

    def test_paddleocr_crash_document_still_saved(self, db):
        """Document is persisted in the failed/awaiting state and is re-runnable.

        The image-processing seam (``ImageProcessor.process``) crashes like a
        PaddleOCR failure; the real pipeline raises but leaves the documents
        row untouched (no partial OCR columns, no file corruption).  A retry
        with the fault removed drives the real pipeline to Completed.
        """
        from services.document_automation.pipeline import (
            run_for_existing_document,
        )
        from services.document_automation.types import (
            ExtractionResult,
            ProcessingResult,
        )

        src = _make_source_pdf("chaos7")
        doc_id = None
        try:
            now = datetime.now().isoformat()
            doc_id = DocumentRepository(db).create(
                doc_number="DOC-CH7-001",
                title="chaos7_cmr.pdf",
                category="cmr",
                entity_type="trip",
                entity_id=None,
                file_path=src,
                file_name=os.path.basename(src),
                file_size=os.path.getsize(src),
                mime_type="application/pdf",
                file_hash="chaos7-hash",
                tags="[]",
                description="",
                uploaded_by="0",
                uploaded_at=now,
                updated_at=now,
            )
            original = _doc_row(db, doc_id)
            assert original["ocr_run_at"] in (None, "")

            # PaddleOCR crashes mid-extraction — the pipeline wraps and raises.
            with patch(
                _IMAGE_PROCESS_SEAM,
                side_effect=RuntimeError("PaddleOCR crashed"),
            ):
                with pytest.raises(RuntimeError, match="Image processing failed"):
                    run_for_existing_document(db, doc_id)

            # Document persisted in the failed/awaiting state — the upload is
            # never lost, and no partial/corrupt OCR columns were written.
            failed = _doc_row(db, doc_id)
            for col in ("doc_number", "title", "category", "file_name", "file_path"):
                assert failed[col] == original[col], (
                    f"column {col} mutated by failed OCR"
                )
            assert failed["ocr_run_at"] in (None, "")
            assert failed["ocr_text"] in (None, "")
            assert failed["ocr_engine"] in (None, "")
            assert failed["extracted_data_json"] in (None, "", "{}")
            assert os.path.isfile(failed["file_path"])

            # Re-runnable: fault removed, the real pipeline completes the row.
            proc_result = ProcessingResult(
                pdf_path=src, pages=1, original_size=(100, 100),
                enhanced=False, method="copy",
            )
            extraction = ExtractionResult(
                full_text="CMR CH7 TEXT",
                extracted={"cmr_number": "CH7-001"},
                confidence=0.95,
                engine="chaos7-ocr",
                pages_processed=1,
            )
            with patch(_IMAGE_PROCESS_SEAM, return_value=proc_result), \
                    patch(_OCR_EXTRACTOR_SEAM, return_value=extraction):
                result = run_for_existing_document(db, doc_id)

            assert result["engine"] == "chaos7-ocr"
            assert result["extracted"]["cmr_number"] == "CH7-001"

            completed = _doc_row(db, doc_id)
            assert completed["ocr_run_at"] not in (None, "")
            assert completed["ocr_text"] == "CMR CH7 TEXT"
            assert completed["ocr_engine"] == "chaos7-ocr"
            parsed = json.loads(completed["extracted_data_json"])
            assert parsed["cmr_number"] == "CH7-001"
        finally:
            if doc_id is not None:
                _unlink_quietly(_doc_row(db, doc_id).get("file_path"))
            _unlink_quietly(src)


# ═════════════════════════════════════════════════════════════════════════
# CH-8 — Invoice: PDF generation crash
# ═════════════════════════════════════════════════════════════════════════

class TestChaosInvoicePDF:
    """CH-8: Invoice — PDF generation crash."""

    def test_pdf_generation_crash_invoice_still_persisted(
        self, workflow_env, invoice_service, db
    ):
        """Invoice draft persists with unchanged status even if PDF generation fails.

        The PDF-generation seam (``InvoiceGenerator.generate``) raises; the
        real ``generate_pdf`` returns a typed ``pdf_generation_failed`` error
        and the invoices row is untouched (status ``draft``, no ``pdf_path``).
        A retry with the fault removed generates the PDF successfully.
        """
        from services.invoicing.generator import InvoiceGenerator
        from tests.workflow_integrity.personas import build_elena_persona

        ids = build_elena_persona(db)
        result = invoice_service.create(InvoiceCreate(
            client_id=ids["client_ids"][0],
            trip_id=ids["trip_ids"]["delivered"][0],
            invoice_date=date(2026, 7, 21),
            due_date=date(2026, 8, 20),
            currency="EUR",
        ))
        assert result.success is True
        invoice_id = result.data.id
        inv = db.conn.execute(
            "SELECT id, status, pdf_path FROM invoices WHERE id = ?",
            (invoice_id,),
        ).fetchone()
        assert inv is not None
        assert inv["status"] == "draft"
        assert inv["pdf_path"] in (None, "")

        # PDF generator crashes during invoice PDF generation.
        with patch.object(
            InvoiceGenerator, "generate",
            side_effect=RuntimeError("PDF renderer crashed"),
        ):
            pdf_result = invoice_service.generate_pdf(invoice_id)

        assert pdf_result.success is False
        codes = [e.code for e in pdf_result.errors]
        assert "pdf_generation_failed" in codes
        # Draft persists, status unchanged, no partial pdf_path written.
        after = db.conn.execute(
            "SELECT id, status, pdf_path FROM invoices WHERE id = ?",
            (invoice_id,),
        ).fetchone()
        assert after["status"] == "draft"
        assert after["pdf_path"] in (None, "")

        # Retry after the PDF renderer recovers — generation succeeds.
        ok = invoice_service.generate_pdf(invoice_id)
        assert ok.success is True
        assert ok.data is not None and ok.data.pdf_path
        final = db.conn.execute(
            "SELECT status, pdf_path FROM invoices WHERE id = ?",
            (invoice_id,),
        ).fetchone()
        assert final["status"] == "draft"
        assert final["pdf_path"]


# ═════════════════════════════════════════════════════════════════════════
# CH-9 — Analytics: aggregation timeout
# ═════════════════════════════════════════════════════════════════════════

class TestChaosAnalytics:
    """CH-9: Analytics — aggregation timeout."""

    def test_aggregation_timeout_returns_partial_results(self, workflow_env, db):
        """Analytics aggregation query raising → empty result, no crash.

        The repository fetch seam raises (aggregation timeout); the real
        caller guard (``AnalyticsService.get_overdue_data``) catches it and
        renders an empty alert list with zero total — the dashboard never
        crashes.  A later query still succeeds (transient failure only).
        """
        from services.analytics_service import AnalyticsService
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)  # completed trips so a healthy query has data
        analytics = AnalyticsService(db)

        # Healthy baseline: the aggregation query returns financial data.
        baseline = analytics.get_financial()
        assert baseline is not None, "Analytics.get_financial() should return data"
        assert len(baseline) > 0

        # Aggregation query raises → the caller guard renders empty without crash.
        with patch.object(
            AnalyticsRepository, "get_overdue_data",
            side_effect=RuntimeError("aggregation query timed out"),
        ):
            alerts, total_overdue = analytics.get_overdue_data()
        assert alerts == []
        assert total_overdue == 0.0

        # Transient failure did not corrupt anything — the next query works.
        refreshed = analytics.get_financial()
        assert refreshed is not None


# ═════════════════════════════════════════════════════════════════════════
# CH-10 — Full workflow cascade failure
# ═════════════════════════════════════════════════════════════════════════

class TestCascadeFailure:
    """CH-10: Full cascade failure — dispatch dies, downstream steps blocked."""

    def test_full_cascade_recovery(self, db, dispatch_service):
        """Dispatch failure leaves the trip Planned and downstream steps blocked.

        The dispatch commit dies and rolls back; the trip stays Planned, the
        real state machine blocks the delivery step (the invoice step's
        precondition), no phantom invoice draft exists, and the DB integrity
        check passes.
        """
        ids = _seed_dispatch_target(db)
        trip_id = ids["trip_id"]

        _run_failing_dispatch(db, dispatch_service, ids)
        row = _trip_row(db, trip_id)
        assert row["status"] == "Planned"
        assert row["truck_id"] is None and row["driver_id"] is None

        # Downstream step — delivery: a still-Planned trip cannot be rushed to
        # Delivered; the real state machine refuses and state is unchanged.
        with pytest.raises(InvalidStatusTransitionError):
            dispatch_service.complete_trip(trip_id)
        assert _trip_row(db, trip_id)["status"] == "Planned"
        assert "Delivered" not in VALID_TRANSITIONS["Planned"]

        # Downstream step — invoice: no draft row for a trip that never
        # reached Delivered (zero phantom invoices during the failure window).
        assert _count(
            db, "SELECT COUNT(*) FROM invoices WHERE trip_id = ?", (trip_id,)
        ) == 0

        # No cascade leftovers: nothing references the aborted resources and
        # the DB is observably intact.
        assert _count(
            db, "SELECT COUNT(*) FROM trips WHERE truck_id = ?", (ids["truck_id"],)
        ) == 0
        assert _count(
            db, "SELECT COUNT(*) FROM trips WHERE driver_id = ?", (ids["driver_id"],)
        ) == 0
        integrity = db.conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity == "ok", f"DB integrity check failed: {integrity}"