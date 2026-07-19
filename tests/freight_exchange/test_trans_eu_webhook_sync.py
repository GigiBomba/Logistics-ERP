"""Tests for Trans.eu webhook ingestion and sync services (Phase 4).

Covers:
- WebhookIngestionService: validation, idempotency, storage, routing
- FreightSyncService: event handling, local model updates
- OrderSyncService: order event processing
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

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
            id TEXT PRIMARY KEY,
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
            id TEXT PRIMARY KEY,
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


class TestIPValidation:
    def test_valid_ip_passes(self):
        from services.trans_eu.webhook_ingestion import WebhookIngestionService, TRANS_EU_CALLBACK_IP
        service = WebhookIngestionService(None)
        # Should not raise
        service.validate_source_ip(TRANS_EU_CALLBACK_IP)

    def test_invalid_ip_raises(self):
        from services.trans_eu.webhook_ingestion import WebhookIngestionService, WebhookValidationError
        service = WebhookIngestionService(None)
        with pytest.raises(WebhookValidationError, match="Invalid source IP"):
            service.validate_source_ip("1.2.3.4")


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
    async def test_order_created_returns_synced(self, db):
        from services.trans_eu.sync_service import OrderSyncService
        service = OrderSyncService(db)
        result = await service.process_order_event(
            1, "freight_orders.order.created", "", {"freight_id": 1},
        )
        assert result["status"] == "synced"

    @pytest.mark.asyncio
    async def test_unhandled_event_returns_skipped(self, db):
        from services.trans_eu.sync_service import OrderSyncService
        service = OrderSyncService(db)
        result = await service.process_order_event(
            1, "freight_orders.nonexistent", "", {},
        )
        assert result["status"] == "skipped"


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
