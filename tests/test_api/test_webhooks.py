"""Comprehensive tests for the webhooks API endpoints.

Tests cover:

*   ``verify_webhook_signature`` — HMAC verification
*   ``store_webhook_event`` — DB persistence
*   ``_dispatch_webhook`` — partner routing
*   ``_handle_timocom_webhook`` — TIMOCOM-specific handler
*   ``_publish_event_bus_event`` — EventBus publishing
*   ``receive_webhook`` (POST /webhooks/{partner}) — public receiver
*   ``list_webhook_events`` (GET /webhooks/events) — admin history
"""
from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.v1.webhooks import (
    _dispatch_webhook,
    _handle_timocom_webhook,
    _publish_event_bus_event,
    store_webhook_event,
    verify_webhook_signature,
)


# ── Helper to build a mock FastAPI Request ────────────────────────────────

def _mock_request(headers: dict | None = None, raw_body: bytes = b"") -> MagicMock:
    """Build a ``MagicMock`` that looks like a FastAPI ``Request``."""
    req = MagicMock()
    req.headers = headers or {}
    state = MagicMock()
    state.webhook_raw_body = raw_body
    req.state = state
    return req


# ======================================================================
# verify_webhook_signature
# ======================================================================

class TestVerifyWebhookSignature:
    """verify_webhook_signature() — HMAC-SHA256 signature verification."""

    def test_valid_signature(self):
        """Valid HMAC signature returns True."""
        secret = "super-secret-key"
        body = b'{"event": "shipment.created"}'
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        req = _mock_request(
            headers={"X-Webhook-Signature": f"sha256={sig}"},
            raw_body=body,
        )
        assert verify_webhook_signature(req, secret) is True

    def test_missing_header(self):
        """Missing X-Webhook-Signature header returns False."""
        req = _mock_request(headers={}, raw_body=b"{}")
        assert verify_webhook_signature(req, "secret") is False

    def test_header_without_sha256_prefix(self):
        """Header value without the 'sha256=' prefix returns False."""
        req = _mock_request(
            headers={"X-Webhook-Signature": "md5=abc123"},
            raw_body=b"{}",
        )
        assert verify_webhook_signature(req, "secret") is False

    def test_empty_signature_header(self):
        """Empty signature header value returns False."""
        req = _mock_request(
            headers={"X-Webhook-Signature": ""},
            raw_body=b"{}",
        )
        assert verify_webhook_signature(req, "secret") is False

    def test_no_raw_body(self):
        """Missing raw body (empty bytes) returns False."""
        secret = "super-secret-key"
        body = b'{"event": "test"}'
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        # bogus body so computed hash won't match the header
        req = _mock_request(
            headers={"X-Webhook-Signature": f"sha256={sig}"},
            raw_body=b"",
        )
        assert verify_webhook_signature(req, secret) is False

    def test_mismatched_signatures(self):
        """Different secret produces a different digest → False."""
        req = _mock_request(
            headers={"X-Webhook-Signature": "sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
            raw_body=b'{"event": "test"}',
        )
        assert verify_webhook_signature(req, "different-secret") is False


# ======================================================================
# store_webhook_event
# ======================================================================

class TestStoreWebhookEvent:
    """store_webhook_event() — INSERT into webhook_events."""

    def setup_method(self):
        self.mock_db = MagicMock()
        self.mock_conn = MagicMock()
        type(self.mock_db).conn = PropertyMock(return_value=self.mock_conn)  # type: ignore[misc]
        self.mock_cursor = MagicMock()
        self.mock_conn.execute.return_value = self.mock_cursor
        self.mock_cursor.lastrowid = 42

    def test_success_returns_lastrowid(self):
        """Successful insert returns the cursor's lastrowid."""
        result = store_webhook_event(
            self.mock_db,
            "timocom",
            "shipment.created",
            {"shipment_id": "SHIP-123"},
            True,
            "received",
        )
        assert result == 42
        self.mock_conn.execute.assert_called_once()
        self.mock_conn.commit.assert_called_once()

    def test_success_lastrowid_none_returns_zero(self):
        """When ``lastrowid`` is None the function returns 0."""
        self.mock_cursor.lastrowid = None
        result = store_webhook_event(
            self.mock_db, "wialon", "gps.position", {"lat": 52.5}, False
        )
        assert result == 0

    def test_db_error_returns_zero(self):
        """Any exception during insert returns 0."""
        self.mock_conn.execute.side_effect = RuntimeError("Disk full")
        result = store_webhook_event(
            self.mock_db, "timocom", "test.event", {"key": "val"}, True
        )
        assert result == 0

    def test_handles_all_payload_fields(self):
        """The SQL params include partner, event_type, payload JSON, and signature_valid as int."""
        self.mock_cursor.lastrowid = 99
        payload = {"offer_id": 456, "amount": 1250.0}
        store_webhook_event(
            self.mock_db, "timocom", "offer.accepted", payload, False
        )
        call_args = self.mock_conn.execute.call_args
        sql, params = call_args[0]
        assert "webhook_events" in sql
        assert params[0] == "timocom"
        assert params[1] == "offer.accepted"
        assert json.loads(params[2]) == payload
        assert params[3] == 0  # False encoded as int
        assert params[4] == "received"

    def test_accepts_default_processing_status(self):
        """Default processing_status is 'received'."""
        self.mock_cursor.lastrowid = 7
        store_webhook_event(
            self.mock_db, "timocom", "test", {}, True
        )
        params = self.mock_conn.execute.call_args[0][1]
        assert params[4] == "received"


# ======================================================================
# _dispatch_webhook
# ======================================================================

class TestDispatchWebhook:
    """_dispatch_webhook() — routes to partner handler or event bus."""

    def test_timocom_partner_calls_handle_timocom_webhook(self):
        """Partner 'timocom' delegates to ``_handle_timocom_webhook``."""
        with patch("backend.api.v1.webhooks._handle_timocom_webhook") as m:
            m.return_value = {"status": "dispatched", "details": "ok"}
            db = MagicMock()
            result = _dispatch_webhook(db, "timocom", "shipment.created", {"id": 1})
            m.assert_called_once_with(db, "shipment.created", {"id": 1})
            assert result == {"status": "dispatched", "details": "ok"}

    def test_generic_partner_publishes_event_bus_event(self):
        """Generic partner publishes ``webhook.<partner>.<event_type>`` on the event bus."""
        with patch("backend.api.v1.webhooks._publish_event_bus_event") as m:
            m.return_value = {"status": "dispatched"}
            db = MagicMock()
            result = _dispatch_webhook(db, "wialon", "gps.position", {"lat": 52.5})
            m.assert_called_once_with(
                db, "webhook.wialon.gps.position", {"lat": 52.5}
            )
            assert result == {"status": "dispatched"}


# ======================================================================
# _handle_timocom_webhook
# ======================================================================

class TestHandleTimocomWebhook:
    """_handle_timocom_webhook() — TIMOCOM-specific webhook handler."""

    def test_feature_flag_disabled_returns_disabled(self):
        """When ``timocom_integration`` is disabled, returns status 'disabled'."""
        with patch("services.feature_flags.FeatureFlagService") as ff_cls:
            ff = MagicMock()
            ff.is_enabled.return_value = False
            ff_cls.return_value = ff

            db = MagicMock()
            result = _handle_timocom_webhook(
                db, "shipment.created", {"company_id": 42}
            )
            assert result == {
                "status": "disabled",
                "details": "TIMOCOM integration is not enabled for this company",
            }
            ff.is_enabled.assert_called_once_with("timocom_integration", company_id=42)

    def test_no_company_id_defaults_to_zero(self):
        """When payload has no company_id, defaults to 0."""
        with patch("services.feature_flags.FeatureFlagService") as ff_cls:
            ff = MagicMock()
            ff.is_enabled.return_value = False
            ff_cls.return_value = ff

            db = MagicMock()
            _handle_timocom_webhook(db, "test.event", {})
            ff.is_enabled.assert_called_once_with("timocom_integration", company_id=0)

    def test_unknown_event_type_returns_skipped(self):
        """Unrecognized TIMOCOM event types return status 'skipped'."""
        with patch("services.feature_flags.FeatureFlagService") as ff_cls:
            ff = MagicMock()
            ff.is_enabled.return_value = True
            ff_cls.return_value = ff

            db = MagicMock()
            result = _handle_timocom_webhook(
                db, "some.random.event", {"company_id": 1}
            )
            assert result == {
                "status": "skipped",
                "details": "Unknown event type: some.random.event",
            }

    def test_known_event_type_dispatched(self):
        """Each known TIMOCOM event type is dispatched to the event bus."""
        for event_type in (
            "shipment.created",
            "shipment.updated",
            "shipment.cancelled",
            "offer.accepted",
            "offer.rejected",
            "document.available",
        ):
            with patch("services.feature_flags.FeatureFlagService") as ff_cls, \
                 patch("backend.api.v1.webhooks._publish_event_bus_event") as pub:
                ff = MagicMock()
                ff.is_enabled.return_value = True
                ff_cls.return_value = ff
                pub.return_value = {"status": "dispatched"}

                db = MagicMock()
                payload = {"company_id": 1, "shipment_id": "S-1"}
                result = _handle_timocom_webhook(db, event_type, payload)
                pub.assert_called_once_with(db, f"timocom.{event_type}", payload)
                assert result == {"status": "dispatched"}


# ======================================================================
# _publish_event_bus_event
# ======================================================================

class TestPublishEventBusEvent:
    """_publish_event_bus_event() — publish an event on the internal EventBus."""

    def test_success_returns_dispatched(self):
        """Successful publish returns ``{'status': 'dispatched', ...}``."""
        with patch("services.operations.event_bus.EventBus") as eb_cls:
            bus = MagicMock()
            eb_cls.get_instance.return_value = bus

            db = MagicMock()
            result = _publish_event_bus_event(
                db, "webhook.timocom.test", {"key": "val"}
            )
            eb_cls.get_instance.assert_called_once_with(db)
            bus.publish.assert_called_once_with("webhook.timocom.test", {"key": "val"})
            assert result == {
                "status": "dispatched",
                "details": "Event webhook.timocom.test queued",
            }

    def test_event_bus_error_returns_error(self):
        """When EventBus.publish raises, status is 'error' and details contain the message."""
        with patch("services.operations.event_bus.EventBus") as eb_cls:
            bus = MagicMock()
            bus.publish.side_effect = RuntimeError("Redis is down")
            eb_cls.get_instance.return_value = bus

            db = MagicMock()
            result = _publish_event_bus_event(
                db, "webhook.test.fail", {"key": "val"}
            )
            assert result == {
                "status": "error",
                "details": "Redis is down",
            }


# ======================================================================
# receive_webhook  (POST /webhooks/{partner})
# ======================================================================

class TestReceiveWebhookEndpoint:
    """POST /api/v1/webhooks/{partner} — public webhook receiver."""

    BASE = "/api/v1/webhooks"

    def setup_method(self):
        self.mock_db = MagicMock()
        self.mock_conn = MagicMock()
        type(self.mock_db).conn = PropertyMock(return_value=self.mock_conn)
        self.mock_cursor = MagicMock()
        self.mock_conn.execute.return_value = self.mock_cursor
        self.mock_cursor.lastrowid = 42

    # ------------------------------------------------------------------
    # Success paths
    # ------------------------------------------------------------------

    def test_valid_webhook_with_secret(self, app):
        """A valid signed webhook returns 200 with event_id and dispatch result."""
        from backend.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: self.mock_db

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs, \
             patch("backend.api.v1.webhooks._dispatch_webhook") as dw, \
             patch("backend.api.v1.webhooks._update_webhook_status") as us:

            gs.return_value = "shared-secret"
            dw.return_value = {"status": "dispatched", "details": "ok"}
            us.return_value = None

            client = TestClient(app)
            body = json.dumps({"event": "shipment.created", "data": {"id": 1}}).encode()
            sig = hmac.new(b"shared-secret", body, hashlib.sha256).hexdigest()

            resp = client.post(
                f"{self.BASE}/timocom",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": f"sha256={sig}",
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["received"] is True
            assert data["event_id"] == 42
            assert data["partner"] == "timocom"
            assert data["event_type"] == "shipment.created"
            assert data["status"] == "dispatched"
            assert data["details"] == "ok"

            dw.assert_called_once()
            us.assert_called_once_with(self.mock_db, 42, "dispatched")

        app.dependency_overrides.clear()

    def test_valid_webhook_without_secret(self, app):
        """When no secret is configured for the partner, signature check is skipped."""
        from backend.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: self.mock_db

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs, \
             patch("backend.api.v1.webhooks._dispatch_webhook") as dw, \
             patch("backend.api.v1.webhooks._update_webhook_status") as us:

            gs.return_value = ""  # no secret configured
            dw.return_value = {"status": "processed"}
            us.return_value = None

            client = TestClient(app)
            resp = client.post(
                f"{self.BASE}/frotcom",
                json={"event": "telemetry", "value": 42},
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["received"] is True
            assert "event_id" in data
            assert data["partner"] == "frotcom"

        app.dependency_overrides.clear()

    # ------------------------------------------------------------------
    # Event-type extraction from different keys
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("payload,expected_event_type", [
        ({"event": "shipment.created"}, "shipment.created"),
        ({"type": "gps.position"}, "gps.position"),
        ({"event_type": "telemetry"}, "telemetry"),
        ({"some_field": "value"}, "unknown"),
    ])
    def test_event_type_extraction(self, app, payload, expected_event_type):
        """The endpoint extracts event_type from 'event', 'type', 'event_type', or defaults to 'unknown'."""
        from backend.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: self.mock_db

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs, \
             patch("backend.api.v1.webhooks.store_webhook_event") as se, \
             patch("backend.api.v1.webhooks._dispatch_webhook") as dw, \
             patch("backend.api.v1.webhooks._update_webhook_status"):

            gs.return_value = ""
            se.return_value = 1
            dw.return_value = {"status": "processed"}

            client = TestClient(app)
            resp = client.post(f"{self.BASE}/partner-x", json=payload)

            assert resp.status_code == 200
            assert resp.json()["event_type"] == expected_event_type

        app.dependency_overrides.clear()

    # ------------------------------------------------------------------
    # Error paths — request validation
    # ------------------------------------------------------------------

    def test_invalid_json_body_returns_400(self, app):
        """Non-JSON body yields 400 Invalid JSON payload."""
        from backend.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: self.mock_db

        client = TestClient(app)
        resp = client.post(
            f"{self.BASE}/timocom",
            content=b"this is not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["detail"]

        app.dependency_overrides.clear()

    def test_non_dict_json_body_returns_400(self, app):
        """A JSON array is rejected with 400; must be a JSON object."""
        from backend.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: self.mock_db

        client = TestClient(app)
        resp = client.post(f"{self.BASE}/timocom", json=[1, 2, 3])
        assert resp.status_code == 400
        assert "JSON object" in resp.json()["detail"]

        app.dependency_overrides.clear()

    # ------------------------------------------------------------------
    # Error paths — signature
    # ------------------------------------------------------------------

    def test_invalid_signature_returns_403(self, app):
        """An invalid webhook signature returns 403 and stores the event as 'signature_failed'."""
        from backend.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: self.mock_db

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs, \
             patch("backend.api.v1.webhooks.store_webhook_event") as se:

            gs.return_value = "shared-secret"
            se.return_value = 0  # not used since 403 is raised

            client = TestClient(app)
            resp = client.post(
                f"{self.BASE}/timocom",
                json={"event": "test"},
                headers={"X-Webhook-Signature": "sha256=bogus"},
            )

            assert resp.status_code == 403
            assert "signature" in resp.json()["detail"].lower()

            # Verify the event was stored with signature_failed status
            se.assert_called_once()
            args, kwargs = se.call_args
            # args[0]=db, args[1]=partner, args[2]=event_type, args[3]=payload, args[4]=signature_valid, args[5]=processing_status
            assert args[4] is False  # signature_valid
            assert args[5] == "signature_failed"

        app.dependency_overrides.clear()

    def test_signature_verification_skipped_when_no_secret(self, app):
        """When secret is empty, signature verification is completely skipped."""
        from backend.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: self.mock_db

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs:
            gs.return_value = ""

            client = TestClient(app)
            # Send a bogus signature header — it should be ignored
            resp = client.post(
                f"{self.BASE}/timocom",
                json={"event": "test"},
                headers={"X-Webhook-Signature": "sha256:definitelywrong"},
            )

            assert resp.status_code == 200  # still succeeds
            assert resp.json()["received"] is True

        app.dependency_overrides.clear()

    # ------------------------------------------------------------------
    # Full-flow integration smoke
    # ------------------------------------------------------------------

    def test_success_event_stored_dispatched_and_status_updated(self, app):
        """Happy path: event is stored, dispatched, and its status updated."""
        from backend.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: self.mock_db

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs, \
             patch("backend.api.v1.webhooks._dispatch_webhook") as dw, \
             patch("backend.api.v1.webhooks._update_webhook_status") as us:

            gs.return_value = ""
            dw.return_value = {"status": "processed", "details": ""}
            us.return_value = None

            client = TestClient(app)
            resp = client.post(
                f"{self.BASE}/timocom",
                json={"event": "shipment.created", "company_id": 1},
            )

            assert resp.status_code == 200
            # Assert the store returned event_id 42 from our mock
            assert resp.json()["event_id"] == 42
            dw.assert_called_once()
            us.assert_called_once_with(self.mock_db, 42, "processed")

        app.dependency_overrides.clear()

    def test_handler_result_details_included_in_response(self, app):
        """The dispatch result's 'details' field is echoed in the endpoint response."""
        from backend.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: self.mock_db

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs, \
             patch("backend.api.v1.webhooks._dispatch_webhook") as dw, \
             patch("backend.api.v1.webhooks._update_webhook_status"):

            gs.return_value = ""
            dw.return_value = {"status": "dispatched", "details": "Event queued at 12:00"}

            client = TestClient(app)
            resp = client.post(
                f"{self.BASE}/timocom",
                json={"event": "test"},
            )
            assert resp.status_code == 200
            assert resp.json()["details"] == "Event queued at 12:00"

        app.dependency_overrides.clear()

    def test_handler_error_status_in_response(self, app):
        """When dispatch returns status 'error', the endpoint returns it."""
        from backend.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: self.mock_db

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs, \
             patch("backend.api.v1.webhooks._dispatch_webhook") as dw, \
             patch("backend.api.v1.webhooks._update_webhook_status"):

            gs.return_value = ""
            dw.return_value = {"status": "error", "details": "Bus unavailable"}

            client = TestClient(app)
            resp = client.post(
                f"{self.BASE}/timocom",
                json={"event": "test"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "error"
            assert resp.json()["details"] == "Bus unavailable"

        app.dependency_overrides.clear()


# ======================================================================
# list_webhook_events  (GET /webhooks/events)
# ======================================================================

class TestListWebhookEventsEndpoint:
    """GET /api/v1/webhooks/events — admin-only webhook event history."""

    BASE = "/api/v1/webhooks/events"

    def setup_method(self):
        self.mock_db = MagicMock()
        self.mock_conn = MagicMock()
        type(self.mock_db).conn = PropertyMock(return_value=self.mock_conn)

    def _override_auth_and_db(self, app):
        """Override ``get_db`` and ``require_admin`` to use mocks."""
        from backend.dependencies import get_db
        from backend.dependencies_security import require_admin

        app.dependency_overrides[get_db] = lambda: self.mock_db
        mock_user = {
            "id": 1,
            "email": "admin@test.com",
            "role": "admin",
            "is_admin": True,
            "company_id": 5,
        }
        app.dependency_overrides[require_admin] = lambda: mock_user
        return mock_user

    # ------------------------------------------------------------------
    # Success paths
    # ------------------------------------------------------------------

    def test_success_returns_event_list(self, app):
        """Returns a list of webhook events with total count."""
        mock_rows = [
            {"id": 1, "partner": "timocom", "event_type": "shipment.created", "payload": "{}"},
            {"id": 2, "partner": "wialon", "event_type": "gps", "payload": "{}"},
        ]
        self.mock_conn.execute.return_value.fetchall.return_value = mock_rows
        user = self._override_auth_and_db(app)

        client = TestClient(app)
        resp = client.get(self.BASE)

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["events"]) == 2
        assert data["events"][0]["id"] == 1

        # Verify company_id filter was applied
        sql = self.mock_conn.execute.call_args[0][0]
        assert "webhook_events.company_id = ?" in sql

        app.dependency_overrides.clear()

    def test_success_empty_list(self, app):
        """When there are no events, returns an empty list with total=0."""
        self.mock_conn.execute.return_value.fetchall.return_value = []
        self._override_auth_and_db(app)

        client = TestClient(app)
        resp = client.get(self.BASE)

        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert data["total"] == 0

        app.dependency_overrides.clear()

    # ------------------------------------------------------------------
    # Partner filter
    # ------------------------------------------------------------------

    def test_with_partner_filter(self, app):
        """The optional partner query parameter filters results."""
        self.mock_conn.execute.return_value.fetchall.return_value = [
            {"id": 3, "partner": "wialon", "event_type": "telemetry", "payload": "{}"},
        ]
        self._override_auth_and_db(app)

        client = TestClient(app)
        resp = client.get(f"{self.BASE}?partner=wialon&limit=10")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["events"][0]["partner"] == "wialon"

        # Verify the SQL included the partner filter
        sql = self.mock_conn.execute.call_args[0][0]
        assert "partner = ?" in sql

        app.dependency_overrides.clear()

    def test_partner_filter_without_matches(self, app):
        """Filtering by a partner with no events returns empty list."""
        self.mock_conn.execute.return_value.fetchall.return_value = []
        self._override_auth_and_db(app)

        client = TestClient(app)
        resp = client.get(f"{self.BASE}?partner=nonexistent")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["events"] == []

        app.dependency_overrides.clear()

    # ------------------------------------------------------------------
    # Error paths
    # ------------------------------------------------------------------

    def test_db_error_returns_error_in_response(self, app):
        """When the DB query fails, the endpoint returns events=[] and an error field."""
        self.mock_conn.execute.side_effect = RuntimeError("Connection refused")
        self._override_auth_and_db(app)

        client = TestClient(app)
        resp = client.get(self.BASE)

        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert "error" in data
        assert "Connection refused" in data["error"]

        app.dependency_overrides.clear()

    # ------------------------------------------------------------------
    # Auth guard
    # ------------------------------------------------------------------

    def test_no_auth_returns_401(self, app):
        """Without valid auth, the endpoint returns 401."""
        client = TestClient(app)
        resp = client.get(self.BASE)
        assert resp.status_code == 401
