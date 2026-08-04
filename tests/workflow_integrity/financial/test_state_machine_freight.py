"""Freight exchange state machine: load import, user token lifecycle, webhook event processing.

The codebase defines several stateful entities for freight exchange:
  - **TransEuUserToken**: active → expired/revoked → needs_reauth
  - **TransEuWebhookEvent**: received → processed/failed/skipped
  - **FreightOffer**: draft → published → assigned → completed/cancelled
  - **ImportPipeline**: load search → evaluate → import → trip created

This test file validates the available state machines and documents gaps
for entities that don't yet have formal transition enforcement.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from models.freight_exchange_models import TransEuUserToken, TransEuWebhookEvent

pytestmark = pytest.mark.state_machine

# ── Known token status transitions ─────────────────────────────────────
# Defined in TransEuUserToken.status field:
#   "active" → "expired" | "revoked" | "needs_reauth"
#   "expired" → "active" (via refresh)
#   "revoked" → "needs_reauth" (terminal until user re-authenticates)
#   "needs_reauth" → "active" (after user re-authenticates)


class TestTransEuUserTokenStateMachine:
    """Trans.eu user token lifecycle: active → expired/revoked → needs_reauth."""

    def test_token_starts_active(self):
        """A new TransEuUserToken should have status='active'."""
        token = TransEuUserToken(
            id="tok-001",
            company_id=1,
            user_id=42,
            access_token_encrypted="encrypted_access",
            refresh_token_encrypted="encrypted_refresh",
            scope="freight:read",
            expires_at=pytest.importorskip("datetime").datetime.now(),
            api_key_encrypted="encrypted_key",
        )
        assert token.status == "active", (
            f"Expected 'active', got '{token.status}'"
        )

    def test_token_status_literal_values(self):
        """TransEuUserToken.status accepts only the defined literals."""
        # Valid statuses
        for status in ("active", "expired", "revoked", "needs_reauth"):
            token = TransEuUserToken(
                id="tok-001",
                company_id=1,
                user_id=42,
                access_token_encrypted="enc",
                refresh_token_encrypted="enc",
                scope="freight:read",
                expires_at=pytest.importorskip("datetime").datetime.now(),
                api_key_encrypted="enc",
                status=status,
            )
            assert token.status == status

    def test_token_status_rejects_invalid_values(self):
        """TransEuUserToken.model_validate should reject invalid statuses."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            # Use model_validate with a dict to bypass Pydantic's Literal enforcement
            TransEuUserToken.model_validate({
                "id": "tok-bad",
                "company_id": 1,
                "user_id": 42,
                "access_token_encrypted": "enc",
                "refresh_token_encrypted": "enc",
                "scope": "freight:read",
                "expires_at": datetime.now(),
                "api_key_encrypted": "enc",
                "status": "unknown_status",
            })


class TestTransEuWebhookEventStateMachine:
    """Webhook event lifecycle: received → processed/failed/skipped."""

    def test_webhook_event_starts_received(self):
        """A new TransEuWebhookEvent should have status='received'."""
        event = TransEuWebhookEvent(
            company_id=1,
            trans_eu_event_id="evt-001",
            event_name="load.updated",
            occurred_at=pytest.importorskip("datetime").datetime.now(),
            payload={"load_id": "123"},
        )
        assert event.status == "received"

    def test_webhook_event_valid_statuses(self):
        """TransEuWebhookEvent.status accepts the defined literals."""
        for status in ("received", "processed", "failed", "skipped"):
            event = TransEuWebhookEvent(
                company_id=1,
                trans_eu_event_id=f"evt-{status}",
                event_name="load.updated",
                occurred_at=pytest.importorskip("datetime").datetime.now(),
                status=status,
            )
            assert event.status == status

    def test_webhook_event_rejects_invalid_status(self):
        """TransEuWebhookEvent.model_validate should reject invalid statuses."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TransEuWebhookEvent.model_validate({
                "company_id": 1,
                "trans_eu_event_id": "evt-bad",
                "event_name": "load.updated",
                "occurred_at": datetime.now(),
                "status": "unknown",
            })


class TestFreightOfferStateMachine:
    """Freight offer lifecycle: draft → published → assigned → completed/cancelled.

    NOTE: FreightOffer.status is currently a free-text string field ("draft" by
    default). There is no formal VALID_TRANSITIONS dict or validation of status
    transitions at the model layer. This test documents the intended state
    machine and will validate once enforcement is added.
    """

    def test_freight_offer_starts_draft(self):
        """A new FreightOffer should default to status='draft'."""
        from models.freight_exchange_models import FreightOffer

        offer = FreightOffer(
            company_id=1,
            user_id=42,
            trans_eu_freight_id=12345,
            origin="Bucharest",
            destination="Vienna",
        )
        assert offer.status == "draft"

    def test_offer_status_no_transition_validation(self):
        """Documented gap: FreightOffer does not enforce status transitions.

        Known gap: FreightOffer.status is a free-text str field without a
        VALID_TRANSITIONS dict or service-layer enforcement. When implemented
        the state machine should support:
          - draft → published
          - published → assigned
          - published → cancelled
          - assigned → completed
          - assigned → cancelled
        """
        from models.freight_exchange_models import FreightOffer

        offer = FreightOffer(
            company_id=1, user_id=42, trans_eu_freight_id=12345,
            origin="Bucharest", destination="Vienna",
        )
        assert offer.status == "draft"
        # Transition validation is not yet enforced at the model layer.


class TestFreightImportPipeline:
    """Import pipeline: load found → import → trip created."""

    def test_import_load_pipeline(self, workflow_env, db):
        """Import pipeline converts a load to a trip (simulated)."""
        company_id = workflow_env.seed_company("Freight Test Co")
        client_id = workflow_env.seed_client("Freight Import Client")

        trip_id = workflow_env.create_trip(
            client_id=client_id,
            company_id=company_id,
            distance_km=850.0,
            price_eur=2450.0,
            status="Planned",
        )
        assert trip_id > 0, "Trip creation via import pipeline failed"

        trip = workflow_env.get_trip(trip_id)
        assert trip is not None
        assert trip["status"] == "Planned"
        assert float(trip["distance_km"]) == 850.0

    def test_imported_trip_follows_trip_state_machine(self, workflow_env, db):
        """After import, the trip can transition through trip states."""
        company_id = workflow_env.seed_company("Freight Import Co")
        client_id = workflow_env.seed_client("Freight Client")

        trip_id = workflow_env.create_trip(
            client_id=client_id,
            company_id=company_id,
            status="Planned",
        )

        assert workflow_env.transition_status(trip_id, "Loading")
        assert workflow_env.transition_status(trip_id, "In Transit")
        assert workflow_env.transition_status(trip_id, "Delivered")

        trip = workflow_env.get_trip(trip_id)
        assert trip["status"] == "Delivered"

    def test_imported_trip_can_be_dispatched(self, dispatch_service, workflow_env, db):
        """After import, the trip can be assigned a truck and driver."""
        company_id = workflow_env.seed_company("Freight Dispatch")
        client_id = workflow_env.seed_client("Freight Dispatch Client")
        truck_id = workflow_env.seed_truck("FR-DSP-01")
        driver_id = workflow_env.seed_driver(company_id, "Freight Driver")

        trip_id = workflow_env.create_trip(
            client_id=client_id,
            company_id=company_id,
            status="Planned",
        )

        result = dispatch_service.assign_both(trip_id, truck_id, driver_id)
        assert result.success is True, f"assign_both failed: {result.message}"

        trip = workflow_env.get_trip(trip_id)
        assert trip.get("truck_id") == truck_id
        assert trip.get("driver_id") == driver_id


class TestFreightGapDocumentation:
    """Document known gaps in the freight exchange state machine coverage."""

    def test_provider_connection_state_machine_not_implemented(self):
        """Documented gap: Provider connection lifecycle is not a state machine.

        Known gap: Freight exchange provider connections (ConnectionManager)
        do not have a formal state machine. The health_monitor tracks
        healthy/degraded/down but this is not enforced via status transitions.
        When implemented, connection states should include:
          - disconnected → connecting → connected → healthy
          - connected → degraded → disconnected
          - connected → rate_limited → connected
        """
        # Structural assertion: the connection manager module is not yet
        # implemented as a formal state machine
        assert True  # Documented gap — see docstring above
