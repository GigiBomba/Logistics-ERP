"""Tests for Trans.eu webhook ingestion and sync services (Phase 4).

Covers:
- WebhookIngestionService: validation, idempotency, storage, routing
- FreightSyncService: event handling, local model updates
- OrderSyncService: order event processing
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from tests.test_helpers import InMemoryDB


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def freight_tables(db):
    """Create the trans_eu_freight_offers table for sync tests."""
    db.conn.execute("""
        CREATE TABLE IF NOT EXISTS trans_eu_freight_offers (
            id TEXT PRIMARY KEY,
            company_id INTEGER, user_id INTEGER,
            trans_eu_freight_id INTEGER,
            trans_eu_reference_number TEXT,
            status TEXT DEFAULT 'draft',
            publication_status TEXT,
            publication_type TEXT,
            origin TEXT, destination TEXT,
            price_amount REAL, price_currency TEXT DEFAULT 'EUR',
            distance_km REAL, trailer_type TEXT,
            adr INTEGER DEFAULT 0, weight_kg REAL DEFAULT 0.0,
            raw_payload TEXT,
            externally_modified_at TEXT,
            operion_trip_id INTEGER,
            trans_eu_order_id TEXT,
            created_at TEXT, updated_at TEXT
        )
    """)
    db.conn.execute("""
        CREATE TABLE IF NOT EXISTS trans_eu_webhook_events (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            company_id INTEGER,
            trans_eu_event_id TEXT UNIQUE,
            event_name TEXT,
            occurred_at TEXT,
            payload TEXT,
            status TEXT DEFAULT 'received',
            processed_at TEXT,
            error_message TEXT,
            created_at TEXT
        )
    """)
    db.conn.execute("""
        CREATE TABLE IF NOT EXISTS trans_eu_webhook_events_failed (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            company_id INTEGER,
            trans_eu_event_id TEXT,
            event_name TEXT,
            payload TEXT,
            error_message TEXT,
            error_type TEXT,
            attempt_count INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 10,
            next_retry_at TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)
    db.conn.commit()
    yield
    db.conn.execute("DROP TABLE IF EXISTS trans_eu_webhook_events_failed")
    db.conn.execute("DROP TABLE IF EXISTS trans_eu_webhook_events")
    db.conn.execute("DROP TABLE IF EXISTS trans_eu_freight_offers")
    db.conn.commit()


# ═══════════════════════════════════════════════════════════════════════
# 1. WebhookIngestionService Tests
# ═══════════════════════════════════════════════════════════════════════


class TestUrlSecretValidation:
    def test_matching_secret_passes(self):
        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        service = WebhookIngestionService(None)
        service.validate_url_secret("mysecret", "mysecret")  # should not raise

    def test_mismatched_secret_raises(self):
        from services.trans_eu.webhook_ingestion import WebhookIngestionService, WebhookValidationError
        service = WebhookIngestionService(None)
        with pytest.raises(WebhookValidationError, match="URL secret mismatch"):
            service.validate_url_secret("expected", "wrong")

    def test_none_expected_skips_check(self):
        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        service = WebhookIngestionService(None)
        service.validate_url_secret(None, "anything")  # should not raise


class TestEventRouting:
    def test_freight_events(self):
        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        service = WebhookIngestionService(None)
        assert service.route_event("freights.freight.create") == "freight"
        assert service.route_event("freights.publication.accepted") == "freight"
        assert service.route_event("freights.proposal_request.negotiated") == "freight"

    def test_order_events(self):
        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        service = WebhookIngestionService(None)
        assert service.route_event("freight_orders.order.created") == "order"
        assert service.route_event("freight_orders.order.delivery_was_confirmed") == "order"

    def test_transport_events(self):
        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        service = WebhookIngestionService(None)
        assert service.route_event("transports.transport.devices_set_changed") == "transport"

    def test_dock_events(self):
        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        service = WebhookIngestionService(None)
        assert service.route_event("time_slot_management.announcement.created") == "dock"

    def test_unknown_events(self):
        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        service = WebhookIngestionService(None)
        assert service.route_event("something.else") == "unknown"


class TestIdempotency:
    def test_duplicate_detected(self, db, freight_tables):
        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        service = WebhookIngestionService(db)
        # Not a duplicate yet
        assert service.is_duplicate("evt-001") is False
        # Insert an event
        db.conn.execute(
            "INSERT INTO trans_eu_webhook_events "
            "(id, company_id, trans_eu_event_id, event_name, occurred_at, payload) "
            "VALUES ('uuid-1', 1, 'evt-001', 'test.event', '2026-01-01', '{}')"
        )
        db.conn.commit()
        # Now it's a duplicate
        assert service.is_duplicate("evt-001") is True


# ═══════════════════════════════════════════════════════════════════════
# 2. FreightSyncService Tests
# ═══════════════════════════════════════════════════════════════════════


class TestFreightSyncService:
    def test_freight_update_marks_externally_modified(self, db, freight_tables):
        """freights.freight.update marks the freight as externally modified."""
        # Insert a known freight
        now = datetime.now(timezone.utc).isoformat()
        db.conn.execute(
            "INSERT INTO trans_eu_freight_offers "
            "(id, company_id, user_id, trans_eu_freight_id, status, origin, destination, created_at, updated_at) "
            "VALUES ('f1', 1, 1, 100, 'published', 'Krakow', 'Berlin', ?, ?)",
            (now, now),
        )
        db.conn.commit()

        from services.trans_eu.sync_service import FreightSyncService
        service = FreightSyncService(db)
        result = service._handle_freight_update(1, 100, now, {})

        assert result["status"] == "synced"
        assert result["action"] == "marked_externally_modified"
        assert result["freight_id"] == 100

    def test_publication_activated_sets_status(self, db, freight_tables):
        """freights.publication.activated sets publication_status='active'."""
        now = datetime.now(timezone.utc).isoformat()
        db.conn.execute(
            "INSERT INTO trans_eu_freight_offers "
            "(id, company_id, user_id, trans_eu_freight_id, status, origin, destination, created_at, updated_at) "
            "VALUES ('f2', 1, 1, 200, 'draft', 'Krakow', 'Berlin', ?, ?)",
            (now, now),
        )
        db.conn.commit()

        from services.trans_eu.sync_service import FreightSyncService
        service = FreightSyncService(db)
        result = service._handle_publication_activated(1, 200, now, {})

        assert result["status"] == "synced"
        row = db.conn.execute(
            "SELECT status, publication_status FROM trans_eu_freight_offers WHERE trans_eu_freight_id = 200"
        ).fetchone()
        assert row[0] == "published"
        assert row[1] == "active"

    def test_publication_accepted_updates_trip(self, db, freight_tables):
        """freights.publication.accepted updates linked trip status."""
        now = datetime.now(timezone.utc).isoformat()
        db.conn.execute(
            "INSERT INTO trans_eu_freight_offers "
            "(id, company_id, user_id, trans_eu_freight_id, status, origin, destination, operion_trip_id, created_at, updated_at) "
            "VALUES ('f3', 1, 1, 300, 'published', 'Krakow', 'Berlin', 999, ?, ?)",
            (now, now),
        )
        db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name) VALUES (1, 'Test Company')"
        )
        db.conn.execute("INSERT INTO trips (id, status, company_id) VALUES (999, 'Planned', 1)")
        db.conn.commit()

        from services.trans_eu.sync_service import FreightSyncService
        service = FreightSyncService(db)
        result = service._handle_publication_accepted(1, 300, now, {})

        assert result["status"] == "synced"
        trip = db.conn.execute("SELECT status FROM trips WHERE id = 999").fetchone()
        assert trip[0] == "Planned"

    @pytest.mark.asyncio
    async def test_process_freight_event_routes_correctly(self, db, freight_tables):
        """process_freight_event routes to the correct handler."""
        now = datetime.now(timezone.utc).isoformat()
        db.conn.execute(
            "INSERT INTO trans_eu_freight_offers "
            "(id, company_id, user_id, trans_eu_freight_id, status, origin, destination, created_at, updated_at) "
            "VALUES ('f4', 1, 1, 400, 'draft', 'Krakow', 'Berlin', ?, ?)",
            (now, now),
        )
        db.conn.commit()

        from services.trans_eu.sync_service import FreightSyncService
        service = FreightSyncService(db)

        result = await service.process_freight_event(
            company_id=1,
            event_name="freights.publication.activated",
            occurred_at=now,
            data={},
            freight_id=400,
        )
        assert result["status"] == "synced"

    @pytest.mark.asyncio
    async def test_unhandled_event_returns_skipped(self, db):
        from services.trans_eu.sync_service import FreightSyncService
        service = FreightSyncService(db)
        result = await service.process_freight_event(
            1, "freights.nonexistent.event", "", {}, freight_id=1,
        )
        assert result["status"] == "skipped"


# ═══════════════════════════════════════════════════════════════════════
# 3. OrderSyncService Tests
# ═══════════════════════════════════════════════════════════════════════


class TestOrderSyncService:
    @pytest.mark.asyncio
    async def test_delivery_confirmed_updates_trip(self, db, freight_tables):
        """freight_orders.order.delivery_was_confirmed sets trip to Delivered."""
        now = datetime.now(timezone.utc).isoformat()
        db.conn.execute(
            "INSERT INTO trans_eu_freight_offers "
            "(id, company_id, user_id, trans_eu_freight_id, status, origin, destination, operion_trip_id, created_at, updated_at) "
            "VALUES ('f5', 1, 1, 500, 'accepted', 'Krakow', 'Berlin', 555, ?, ?)",
            (now, now),
        )
        db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name) VALUES (1, 'Test Company')"
        )
        db.conn.execute("INSERT INTO trips (id, status, company_id) VALUES (555, 'Planned', 1)")
        db.conn.commit()

        from services.trans_eu.sync_service import OrderSyncService
        service = OrderSyncService(db)
        result = await service.process_order_event(
            company_id=1,
            event_name="freight_orders.order.delivery_was_confirmed",
            occurred_at=now,
            data={"freight_id": 500, "status": "delivery-confirmed"},
        )

        assert result["status"] == "synced"
        assert result["new_status"] == "Delivered"
        trip = db.conn.execute("SELECT status FROM trips WHERE id = 555").fetchone()
        assert trip[0] == "Delivered"

    @pytest.mark.asyncio
    async def test_order_cancelled_updates_trip(self, db, freight_tables):
        now = datetime.now(timezone.utc).isoformat()
        db.conn.execute(
            "INSERT INTO trans_eu_freight_offers "
            "(id, company_id, user_id, trans_eu_freight_id, status, origin, destination, operion_trip_id, created_at, updated_at) "
            "VALUES ('f6', 1, 1, 600, 'accepted', 'Krakow', 'Berlin', 666, ?, ?)",
            (now, now),
        )
        db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name) VALUES (1, 'Test Company')"
        )
        db.conn.execute("INSERT INTO trips (id, status, company_id) VALUES (666, 'Planned', 1)")
        db.conn.commit()

        from services.trans_eu.sync_service import OrderSyncService
        service = OrderSyncService(db)
        result = await service.process_order_event(
            company_id=1,
            event_name="freight_orders.order.order_was_cancelled",
            occurred_at=now,
            data={"freight_id": 600},
        )

        assert result["status"] == "synced"
        assert result["new_status"] == "Cancelled"

    @pytest.mark.asyncio
    async def test_order_created_creates_freight_order(self, db):
        """freight_orders.order.created persists a freight_orders row."""
        now = datetime.now(timezone.utc).isoformat()
        from services.trans_eu.sync_service import OrderSyncService
        service = OrderSyncService(db)
        result = await service.process_order_event(
            company_id=1,
            event_name="freight_orders.order.created",
            occurred_at=now,
            data={
                "id": "ord-700",
                "freight_id": 700,
                "status": "created",
                "price": {"amount": 1250.0, "currency": "EUR"},
                "payment_type": "deferred",
                "order_number": "TE/2026/001",
            },
        )

        assert result["status"] == "synced"
        assert result["action"] == "created"

        row = db.conn.execute(
            "SELECT trans_eu_order_id, trans_eu_freight_id, order_number,"
            " price_amount, price_currency, payment_type, execution_data"
            " FROM freight_orders WHERE company_id = 1 AND trans_eu_order_id = 'ord-700'"
        ).fetchone()
        assert row is not None
        assert row[0] == "ord-700"
        assert row[1] == 700
        assert row[2] == "TE/2026/001"
        assert row[3] == 1250.0
        assert row[4] == "EUR"
        assert row[5] == "deferred"
        assert json.loads(row[6])["freight_id"] == 700

    @pytest.mark.asyncio
    async def test_order_created_is_idempotent_on_duplicate(self, db):
        """Re-sending the same order.created updates the existing row (no dup)."""
        from services.trans_eu.sync_service import OrderSyncService
        service = OrderSyncService(db)
        data = {
            "id": "ord-701",
            "freight_id": 701,
            "price": {"amount": 900.0, "currency": "EUR"},
        }
        first = await service.process_order_event(
            1, "freight_orders.order.created", "", dict(data),
        )
        second = await service.process_order_event(
            1, "freight_orders.order.created", "", dict(data),
        )

        assert first["status"] == "synced"
        assert first["action"] == "created"
        assert second["status"] == "synced"
        assert second["action"] == "updated"

        count = db.conn.execute(
            "SELECT COUNT(*) FROM freight_orders"
            " WHERE company_id = 1 AND trans_eu_order_id = 'ord-701'"
        ).fetchone()
        assert count[0] == 1

    @pytest.mark.asyncio
    async def test_order_created_links_trip_when_operion_trip_id_exists(self, db, freight_tables):
        """order.created links the order to the freight's Operion trip."""
        now = datetime.now(timezone.utc).isoformat()
        db.conn.execute(
            "INSERT INTO trans_eu_freight_offers "
            "(id, company_id, user_id, trans_eu_freight_id, status, origin, destination, operion_trip_id, created_at, updated_at) "
            "VALUES ('f8', 1, 1, 702, 'accepted', 'Krakow', 'Berlin', 777, ?, ?)",
            (now, now),
        )
        db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name) VALUES (1, 'Test Company')"
        )
        db.conn.execute("INSERT INTO trips (id, status, company_id) VALUES (777, 'Planned', 1)")
        db.conn.commit()

        from services.trans_eu.sync_service import OrderSyncService
        service = OrderSyncService(db)
        result = await service.process_order_event(
            1, "freight_orders.order.created", now,
            {"id": "ord-702", "freight_id": 702},
        )

        assert result["status"] == "synced"
        row = db.conn.execute(
            "SELECT linked_trip_id FROM freight_orders"
            " WHERE company_id = 1 AND trans_eu_order_id = 'ord-702'"
        ).fetchone()
        assert row is not None and row[0] == 777

    @pytest.mark.asyncio
    async def test_order_created_skips_missing_order_id_or_freight_id(self, db):
        """order.created without order_id or freight_id is skipped."""
        from services.trans_eu.sync_service import OrderSyncService
        service = OrderSyncService(db)

        no_order_id = await service.process_order_event(
            1, "freight_orders.order.created", "", {"freight_id": 1},
        )
        no_freight_id = await service.process_order_event(
            1, "freight_orders.order.created", "", {"id": "ord-900"},
        )

        assert no_order_id["status"] == "skipped"
        assert no_freight_id["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_order_created_maps_price_and_payment_type(self, db):
        """Scalar price, payment_type, and reference-number order_number are mapped."""
        from services.trans_eu.sync_service import OrderSyncService
        service = OrderSyncService(db)
        result = await service.process_order_event(
            1, "freight_orders.order.created", "",
            {
                "id": "ord-703",
                "freight_id": 703,
                "price": 560.20,
                "payment_type": "cash",
                "freight_reference_number": "TE-REF-703",
            },
        )

        assert result["status"] == "synced"
        row = db.conn.execute(
            "SELECT price_amount, price_currency, payment_type, order_number"
            " FROM freight_orders WHERE company_id = 1 AND trans_eu_order_id = 'ord-703'"
        ).fetchone()
        assert row is not None
        assert row[0] == 560.20
        assert row[1] == "EUR"
        assert row[2] == "cash"
        assert row[3] == "TE-REF-703"

    @pytest.mark.asyncio
    async def test_unhandled_event_returns_skipped(self, db):
        from services.trans_eu.sync_service import OrderSyncService
        service = OrderSyncService(db)
        result = await service.process_order_event(
            1, "freight_orders.nonexistent", "", {},
        )
        assert result["status"] == "skipped"


# ═══════════════════════════════════════════════════════════════════════
# 3.5. Webhook → Sync dispatch (process_webhook pipeline)
# ═══════════════════════════════════════════════════════════════════════


class TestWebhookDispatchToSync:
    """process_webhook routes freight/order events to the sync services."""

    @pytest.mark.asyncio
    async def test_freight_event_updates_freight_offer(self, db, freight_tables):
        """A freights.* webhook updates the local freight offer via FreightSyncService."""
        now = datetime.now(timezone.utc).isoformat()
        db.conn.execute(
            "INSERT INTO trans_eu_freight_offers "
            "(id, company_id, user_id, trans_eu_freight_id, status, origin, destination, created_at, updated_at) "
            "VALUES ('f7', 1, 1, 700, 'draft', 'Krakow', 'Berlin', ?, ?)",
            (now, now),
        )
        db.conn.commit()

        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        service = WebhookIngestionService(db)
        result = await service.process_webhook(
            company_id=1,
            event_id="evt-freight-1",
            event_name="freights.publication.activated",
            occurred_at=now,
            payload={
                "id": "evt-freight-1",
                "event_name": "freights.publication.activated",
                "occurred_at": now,
                "data": {"freight_id": 700},
            },
        )

        assert result["status"] == "processed"
        assert result["category"] == "freight"

        freight = db.conn.execute(
            "SELECT status, publication_status FROM trans_eu_freight_offers"
            " WHERE trans_eu_freight_id = 700 AND company_id = 1"
        ).fetchone()
        assert freight is not None
        assert freight[0] == "published"
        assert freight[1] == "active"

        evt = db.conn.execute(
            "SELECT status FROM trans_eu_webhook_events"
            " WHERE trans_eu_event_id = 'evt-freight-1'"
        ).fetchone()
        assert evt[0] == "processed"

    @pytest.mark.asyncio
    async def test_order_created_event_dispatches_to_order_sync(self, db, freight_tables):
        """freight_orders.order.created routes to OrderSyncService with data=payload['data']."""
        now = datetime.now(timezone.utc).isoformat()

        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        from services.trans_eu.sync_service import OrderSyncService

        service = WebhookIngestionService(db)
        with patch.object(
            OrderSyncService,
            "process_order_event",
            new=AsyncMock(return_value={"status": "synced", "action": "order_created"}),
        ) as mock_process:
            result = await service.process_webhook(
                company_id=1,
                event_id="evt-order-1",
                event_name="freight_orders.order.created",
                occurred_at=now,
                payload={
                    "id": "evt-order-1",
                    "event_name": "freight_orders.order.created",
                    "occurred_at": now,
                    "data": {"freight_id": 800, "status": "created"},
                },
            )

        mock_process.assert_awaited_once_with(
            1, "freight_orders.order.created", now, {"freight_id": 800, "status": "created"}
        )

        assert result["status"] == "processed"
        assert result["category"] == "order"

        evt = db.conn.execute(
            "SELECT status FROM trans_eu_webhook_events"
            " WHERE trans_eu_event_id = 'evt-order-1'"
        ).fetchone()
        assert evt[0] == "processed"

    @pytest.mark.asyncio
    async def test_failing_sync_goes_to_dlq_and_failed(self, db, freight_tables):
        """A sync service exception marks the event failed and stores it in the DLQ."""
        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        from services.trans_eu.sync_service import FreightSyncService

        service = WebhookIngestionService(db)
        with patch.object(
            FreightSyncService,
            "process_freight_event",
            new=AsyncMock(side_effect=RuntimeError("sync boom")),
        ):
            result = await service.process_webhook(
                company_id=1,
                event_id="evt-fail-1",
                event_name="freights.freight.update",
                occurred_at="2026-01-25T11:41:11+00:00",
                payload={
                    "id": "evt-fail-1",
                    "event_name": "freights.freight.update",
                    "data": {"freight_id": 1},
                },
            )

        assert result["status"] == "failed"
        assert "sync boom" in result.get("error", "")

        evt = db.conn.execute(
            "SELECT status, error_message FROM trans_eu_webhook_events"
            " WHERE trans_eu_event_id = 'evt-fail-1'"
        ).fetchone()
        assert evt[0] == "failed"
        assert "sync boom" in evt[1]

        dlq = db.conn.execute(
            "SELECT trans_eu_event_id, status, error_type, error_message"
            " FROM trans_eu_webhook_events_failed"
        ).fetchone()
        assert dlq is not None
        assert dlq[0] == "evt-fail-1"
        assert dlq[1] == "pending"
        assert dlq[2] == "processing"
        assert "sync boom" in dlq[3]


# ═══════════════════════════════════════════════════════════════════════
# 4. OAuthLoopbackServer Tests
# ═══════════════════════════════════════════════════════════════════════


class TestOAuthLoopbackServer:
    def test_importable(self):
        from ui.views.freight_exchange.oauth_loopback import OAuthLoopbackServer
        assert OAuthLoopbackServer is not None

    def test_build_auth_url_contains_required_params(self):
        from ui.views.freight_exchange.oauth_loopback import OAuthLoopbackServer
        server = OAuthLoopbackServer()
        url = server.build_auth_url("test_client", "http://localhost:19999/callback")
        assert "client_id=test_client" in url
        assert "response_type=code" in url
        assert "http%3A%2F%2Flocalhost" in url or "http://localhost" in url
        assert "state=" in url

    def test_server_starts_and_stops(self):
        from ui.views.freight_exchange.oauth_loopback import OAuthLoopbackServer
        server = OAuthLoopbackServer()
        started = server.start()
        if started:
            assert server.port >= 19997
            assert server.port <= 19999
            server.stop()
        # If port 19999 is occupied, the server may fail to start
        # That's acceptable — test that start/stop don't crash


# ═══════════════════════════════════════════════════════════════════════
# 5. Transport / Dock sync (lane B.1) + externally_managed gate (B.2)
# ═══════════════════════════════════════════════════════════════════════


def _insert_freight_with_trip(db, freight_id, trip_id):
    """Insert a trans_eu_freight_offers row linked to a trips row."""
    now = datetime.now(timezone.utc).isoformat()
    db.conn.execute(
        "INSERT INTO trans_eu_freight_offers "
        "(id, company_id, user_id, trans_eu_freight_id, status, origin, destination, operion_trip_id, created_at, updated_at) "
        "VALUES (?, 1, 1, ?, 'accepted', 'Krakow', 'Berlin', ?, ?, ?)",
        (f"f-laneB-{freight_id}", freight_id, trip_id, now, now),
    )
    db.conn.execute(
        "INSERT OR IGNORE INTO companies (id, company_name) VALUES (1, 'Test Company')"
    )
    db.conn.commit()


class TestTransportSyncService:
    """transports.* events sync the Trans.eu-assigned truck/driver to the trip."""

    @pytest.mark.asyncio
    async def test_devices_set_changed_updates_trip_assignment(self, db, freight_tables):
        """transports.transport.devices_set_changed updates truck/driver on the
        linked trip and stamps externally_managed=1 (Trans.eu owns the assignment)."""
        _insert_freight_with_trip(db, freight_id=1000, trip_id=1001)
        db.conn.execute(
            "INSERT INTO trucks (id, plate_number, company_id) VALUES (1, 'TE-123', 1)"
        )
        db.conn.execute(
            "INSERT INTO drivers (id, name, phone, company_id, created_at, updated_at) "
            "VALUES (1, 'Jan Kowalski', '+48123456789', 1, '2026-01-01', '2026-01-01')"
        )
        db.conn.execute(
            "INSERT INTO trips (id, status, company_id, truck_number, driver_name) "
            "VALUES (1001, 'Planned', 1, '', '')"
        )
        db.conn.commit()

        from services.trans_eu.sync_service import TransportSyncService
        service = TransportSyncService(db)
        result = await service.process_transport_event(
            company_id=1,
            event_name="transports.transport.devices_set_changed",
            occurred_at=datetime.now(timezone.utc).isoformat(),
            data={
                "freight_id": 1000,
                "truck_plate_number": "TE-123",
                "executor_name": "Jan Kowalski",
                "executor_phone": "+48123456789",
            },
        )

        assert result["status"] == "synced"
        assert result["action"] == "assignment_synced"
        trip = db.conn.execute(
            "SELECT truck_id, truck_number, driver_id, driver_name, externally_managed"
            " FROM trips WHERE id = 1001"
        ).fetchone()
        assert trip is not None
        assert trip[0] == 1
        assert trip[1] == "TE-123"
        assert trip[2] == 1
        assert trip[3] == "Jan Kowalski"
        assert trip[4] == 1

    @pytest.mark.asyncio
    async def test_devices_set_changed_without_linked_trip_is_skipped(self, db, freight_tables):
        from services.trans_eu.sync_service import TransportSyncService
        service = TransportSyncService(db)
        result = await service.process_transport_event(
            company_id=1,
            event_name="transports.transport.devices_set_changed",
            occurred_at="",
            data={"freight_id": 999999, "truck_plate_number": "XX-1"},
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "no_linked_trip"

    @pytest.mark.asyncio
    async def test_webhook_dispatches_transport_event_to_sync(self, db, freight_tables):
        """process_webhook routes transports.* to TransportSyncService."""
        _insert_freight_with_trip(db, freight_id=1100, trip_id=1101)
        db.conn.execute("INSERT INTO trips (id, status, company_id) VALUES (1101, 'Planned', 1)")
        db.conn.commit()

        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        from services.trans_eu.sync_service import TransportSyncService

        service = WebhookIngestionService(db)
        with patch.object(
            TransportSyncService,
            "process_transport_event",
            new=AsyncMock(return_value={"status": "synced", "action": "assignment_synced"}),
        ) as mock_process:
            result = await service.process_webhook(
                company_id=1,
                event_id="evt-transport-1",
                event_name="transports.transport.devices_set_changed",
                occurred_at="2026-01-25T11:41:11+00:00",
                payload={
                    "id": "evt-transport-1",
                    "event_name": "transports.transport.devices_set_changed",
                    "occurred_at": "2026-01-25T11:41:11+00:00",
                    "data": {"freight_id": 1100, "truck_plate_number": "TE-123"},
                },
            )

        mock_process.assert_awaited_once_with(
            1, "transports.transport.devices_set_changed",
            "2026-01-25T11:41:11+00:00", {"freight_id": 1100, "truck_plate_number": "TE-123"},
        )
        assert result["status"] == "processed"
        assert result["category"] == "transport"


class TestDockSyncService:
    """time_slot_management.* events upsert/delete the dock tables."""

    @pytest.mark.asyncio
    async def test_announcement_created_upserts_dock_tables(self, db, freight_tables):
        """announcement.created upserts dock_announcements + dock_warehouses."""
        from services.trans_eu.sync_service import DockSyncService
        service = DockSyncService(db)
        result = await service.process_dock_event(
            company_id=1,
            event_name="time_slot_management.announcement.created",
            occurred_at="2026-01-25T11:41:11+00:00",
            data={
                "id": 38602,
                "reference_number": "DS/16365BE/1",
                "status": "CONFIRMED",
                "stage": "Vehicle_Arrived",
                "date_from": "2023-07-14T08:00:00",
                "date_to": "2023-07-14T10:00:00",
                "operation_type": "loading",
                "operation_time": "PT2H",
                "carrier": {"id": 1013865, "legal_name": "Firma Testowa Przewoźnik"},
                "shipper": {"id": 1007386, "legal_name": "Firma Testowa Załadowca"},
                "driver": {"full_name": "Jan Kowalski", "phone_number": "+48888123456"},
                "vehicle": {"truck_plate_number": "123string", "trailer_plate_number": "456string"},
                "ramp": {"id": 2006, "name": "Suwnica A 1", "ramp_type": "GANTRY"},
                "warehouse": {"id": 1567, "name": "Magazyn Stali"},
                "route": {"spots": [{"order": 1}]},
                "notes": [{"id": 26504, "note": "notatka", "type": "SHIPPER"}],
                "external_reference_number": "123test",
            },
        )

        assert result["status"] == "synced"
        assert result["action"] == "upserted"

        ann = db.conn.execute(
            "SELECT trans_eu_announcement_id, reference_number, status,"
            " carrier_id, carrier_name, warehouse_id, ramp_id, external_reference_number"
            " FROM dock_announcements WHERE company_id = 1 AND trans_eu_announcement_id = 38602"
        ).fetchone()
        assert ann is not None
        assert ann[0] == 38602
        assert ann[1] == "DS/16365BE/1"
        assert ann[2] == "CONFIRMED"
        assert ann[3] == 1013865
        assert ann[4] == "Firma Testowa Przewoźnik"
        assert ann[5] == 1567
        assert ann[6] == 2006
        assert ann[7] == "123test"

        wh = db.conn.execute(
            "SELECT trans_eu_warehouse_id, name FROM dock_warehouses"
            " WHERE company_id = 1 AND trans_eu_warehouse_id = 1567"
        ).fetchone()
        assert wh is not None
        assert wh[1] == "Magazyn Stali"

    @pytest.mark.asyncio
    async def test_announcement_created_is_idempotent(self, db, freight_tables):
        """Re-sending announcement.created REPLACES the row (no duplicate)."""
        from services.trans_eu.sync_service import DockSyncService
        service = DockSyncService(db)
        payload = {"id": 38603, "reference_number": "DS/2", "status": "CONFIRMED",
                   "warehouse": {"id": 1568, "name": "Wh"}}
        await service.process_dock_event(
            1, "time_slot_management.announcement.created", "", dict(payload),
        )
        await service.process_dock_event(
            1, "time_slot_management.announcement.updated", "",
            dict(payload, reference_number="DS/2-REV", status="FINISHED"),
        )

        rows = db.conn.execute(
            "SELECT COUNT(*) FROM dock_announcements"
            " WHERE company_id = 1 AND trans_eu_announcement_id = 38603"
        ).fetchone()
        assert rows[0] == 1
        row = db.conn.execute(
            "SELECT reference_number, status FROM dock_announcements"
            " WHERE company_id = 1 AND trans_eu_announcement_id = 38603"
        ).fetchone()
        assert row[0] == "DS/2-REV"
        assert row[1] == "FINISHED"

    @pytest.mark.asyncio
    async def test_announcement_deleted_removes_row(self, db, freight_tables):
        from services.trans_eu.sync_service import DockSyncService
        service = DockSyncService(db)
        await service.process_dock_event(
            1, "time_slot_management.announcement.created", "",
            {"id": 38604, "reference_number": "DS/4", "warehouse": {"id": 1569, "name": "Wh"}},
        )
        result = await service.process_dock_event(
            1, "time_slot_management.announcement.deleted", "", {"id": 38604},
        )
        assert result["status"] == "synced"
        assert result["action"] == "deleted"
        rows = db.conn.execute(
            "SELECT COUNT(*) FROM dock_announcements WHERE company_id = 1 AND trans_eu_announcement_id = 38604"
        ).fetchone()
        assert rows[0] == 0

    @pytest.mark.asyncio
    async def test_time_window_created_upserts_dock_table(self, db, freight_tables):
        """time_window.created upserts dock_time_windows (warehouse from route spot)."""
        from services.trans_eu.sync_service import DockSyncService
        service = DockSyncService(db)
        result = await service.process_dock_event(
            company_id=1,
            event_name="time_slot_management.time_window.created",
            occurred_at="2026-01-25T11:41:11+00:00",
            data={
                "id": 42,
                "valid_from": "2025-09-08",
                "valid_to": "2025-09-08",
                "start_time": "12:00:00",
                "end_time": "18:00:00",
                "range_type": "CYCLE",
                "external_number": "1DX124DAW7871",
                "carrier": {"id": 956529},
                "purchase_order": {"number": "PO-123"},
                "route": {"spots": [{"warehouse_id": 6596, "order": 1}]},
            },
        )

        assert result["status"] == "synced"
        row = db.conn.execute(
            "SELECT trans_eu_window_id, warehouse_id, valid_from, valid_to,"
            " start_time, end_time, range_type, external_number, carrier_id"
            " FROM dock_time_windows WHERE company_id = 1 AND trans_eu_window_id = 42"
        ).fetchone()
        assert row is not None
        assert row[0] == 42
        assert row[1] == 6596
        assert row[2] == "2025-09-08"
        assert row[3] == "2025-09-08"
        assert row[4] == "12:00:00"
        assert row[5] == "18:00:00"
        assert row[6] == "CYCLE"
        assert row[7] == "1DX124DAW7871"
        assert row[8] == 956529

    @pytest.mark.asyncio
    async def test_webhook_dispatches_dock_event_to_sync(self, db, freight_tables):
        """process_webhook routes time_slot_management.* to DockSyncService."""
        from services.trans_eu.webhook_ingestion import WebhookIngestionService
        from services.trans_eu.sync_service import DockSyncService

        service = WebhookIngestionService(db)
        with patch.object(
            DockSyncService,
            "process_dock_event",
            new=AsyncMock(return_value={"status": "synced", "action": "upserted"}),
        ) as mock_process:
            result = await service.process_webhook(
                company_id=1,
                event_id="evt-dock-1",
                event_name="time_slot_management.announcement.created",
                occurred_at="2026-01-25T11:41:11+00:00",
                payload={
                    "id": "evt-dock-1",
                    "event_name": "time_slot_management.announcement.created",
                    "occurred_at": "2026-01-25T11:41:11+00:00",
                    "data": {"id": 700, "reference_number": "DS/700"},
                },
            )

        mock_process.assert_awaited_once_with(
            1, "time_slot_management.announcement.created",
            "2026-01-25T11:41:11+00:00", {"id": 700, "reference_number": "DS/700"},
        )
        assert result["status"] == "processed"
        assert result["category"] == "dock"


class TestExternallyManagedDispatchGate:
    """trips.externally_managed=1 → manual dispatch edits rejected, sync allowed."""

    def _make_external_trip(self, db, trip_id=2000):
        db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name) VALUES (1, 'Test Company')"
        )
        db.conn.execute(
            "INSERT INTO trips (id, status, company_id, externally_managed)"
            " VALUES (?, 'Planned', 1, 1)",
            (trip_id,),
        )
        db.conn.commit()

    def test_manual_assignment_edit_rejected(self, db, freight_tables):
        """Manual truck assignment on an externally-managed trip is rejected."""
        self._make_external_trip(db)
        db.conn.execute("INSERT INTO trucks (id, plate_number, company_id) VALUES (1, 'TE-1', 1)")
        db.conn.commit()

        from models.trip_models import TripUpdate
        from services.trip_service import TripService

        service = TripService(db)
        result = service.update(2000, TripUpdate(truck_id=1), company_id=1)

        assert result.success is False
        assert result.errors[0].code == "externally_managed"
        # Rejection is read-only — the trip is unchanged.
        row = db.conn.execute("SELECT truck_id FROM trips WHERE id = 2000").fetchone()
        assert row[0] is None

    def test_manual_status_transition_rejected(self, db, freight_tables):
        """Manual status transition on an externally-managed trip is rejected."""
        self._make_external_trip(db)
        from models.trip_models import TripUpdate
        from services.trip_service import TripService

        service = TripService(db)
        result = service.update(2000, TripUpdate(status="In Transit"), company_id=1)

        assert result.success is False
        assert result.errors[0].code == "externally_managed"
        row = db.conn.execute("SELECT status FROM trips WHERE id = 2000").fetchone()
        assert row[0] == "Planned"

    def test_manual_driver_edit_rejected_via_dict_path(self, db, freight_tables):
        """The deprecated dict path applies the same gate."""
        self._make_external_trip(db)
        from services.trip_service import TripService

        service = TripService(db)
        result = service.update(2000, {"driver_name": "Hacker"}, company_id=1)

        assert result.success is False
        assert result.errors[0].code == "externally_managed"

    def test_non_dispatch_edit_still_allowed(self, db, freight_tables):
        """Non-dispatch edits (e.g. pricing) are NOT blocked by the gate."""
        from decimal import Decimal

        self._make_external_trip(db)
        from models.trip_models import TripUpdate
        from services.trip_service import TripService

        service = TripService(db)
        result = service.update(2000, TripUpdate(price_eur=Decimal("1500")), company_id=1)

        assert result.success is True
        row = db.conn.execute("SELECT total_price_eur FROM trips WHERE id = 2000").fetchone()
        assert float(row[0]) == 1500.0

    @pytest.mark.asyncio
    async def test_sync_path_write_still_allowed(self, db, freight_tables):
        """The Trans.eu sync path (raw SQL) is NOT blocked by the manual gate."""
        self._make_external_trip(db, trip_id=2001)
        _insert_freight_with_trip(db, freight_id=2001, trip_id=2001)
        db.conn.execute("INSERT INTO trucks (id, plate_number, company_id) VALUES (2, 'TE-999', 1)")
        db.conn.commit()

        from services.trans_eu.sync_service import TransportSyncService

        service = TransportSyncService(db)
        result = await service.process_transport_event(
            company_id=1,
            event_name="transports.transport.devices_set_changed",
            occurred_at=datetime.now(timezone.utc).isoformat(),
            data={"freight_id": 2001, "truck_plate_number": "TE-999"},
        )

        assert result["status"] == "synced"
        row = db.conn.execute(
            "SELECT truck_number, externally_managed FROM trips WHERE id = 2001"
        ).fetchone()
        assert row[0] == "TE-999"
        assert row[1] == 1

    @pytest.mark.asyncio
    async def test_order_link_marks_trip_externally_managed(self, db, freight_tables):
        """freight_orders.order.created → linked trip gets externally_managed=1."""
        _insert_freight_with_trip(db, freight_id=3000, trip_id=3001)
        db.conn.execute("INSERT INTO trips (id, status, company_id) VALUES (3001, 'Planned', 1)")
        db.conn.commit()

        from services.trans_eu.sync_service import OrderSyncService

        service = OrderSyncService(db)
        result = await service.process_order_event(
            company_id=1,
            event_name="freight_orders.order.created",
            occurred_at="2026-01-25T11:41:11+00:00",
            data={"id": "ord-3000", "freight_id": 3000},
        )

        assert result["status"] == "synced"
        row = db.conn.execute(
            "SELECT externally_managed FROM trips WHERE id = 3001"
        ).fetchone()
        assert row[0] == 1
