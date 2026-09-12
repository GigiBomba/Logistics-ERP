"""Network partition + heal chaos tests (Stage B P5-U2).

Simulates a desktop/mobile network partition and the subsequent heal/sync:

* P6 convergence — after the partition heals, desktop and mobile converge on
  one server-confirmed business state and every status transition is recorded
  exactly once (8.5.6 / P9 idempotency).
* R-CONF-01 — last-writer-wins arbitration for queued status updates that
  arrive from different sources; the final stored status equals the one the
  real transition path applied last (server order).
* R-CONF-03 — offline document upload dedup: re-uploading the same content
  hash dedups *and reports* the discard per-action (never a silent drop),
  while distinct hashes are both preserved.

All assertions are synchronous — no ``time.sleep``; events are observed
through the ``event_monitor`` fixture and its poll-free helpers.
"""
from __future__ import annotations

import pytest

from tests.workflow_integrity.fixtures.multi_platform_client import (
    DesktopClient,
    MobileClient,
)
from tests.workflow_integrity.personas import build_ionut_persona

pytestmark = pytest.mark.chaos_workflow


def _new_mobile(trip_service, db) -> MobileClient:
    """Build a fresh device with its own offline queue + session dedup set."""
    return MobileClient(trip_service, db)


class TestPartitionAndHeal:
    """Scenario 1 — desktop offline while the mobile keeps working.

    The driver queues the full delivery leg (Loading → In Transit → Delivered)
    plus a CMR document upload and an ad-hoc expense during the partition.
    When connectivity heals, one sync applies everything; both platforms read
    the same Delivered business state and each transition fires exactly one
    ``trip.status_changed`` event.
    """

    def test_partition_heal_applies_queued_actions_and_converges(
        self, db, trip_service, invoice_service, event_bus, event_monitor
    ):
        ids = build_ionut_persona(db)
        trip_id = ids["trip_ids"]["planned"]  # starts Planned

        desktop = DesktopClient(trip_service, invoice_service, event_bus, db)
        mobile = _new_mobile(trip_service, db)
        event_monitor.track("trip.status_changed")

        # ── Partition: desktop cannot reach the backend. The driver keeps
        #    working on mobile — every action accumulates in the offline queue.
        mobile.update_status(trip_id, "Loading", offline=True,
                             idempotency_key="np-loading")
        mobile.queue_document_upload(
            trip_id, title="cmr_loaded.jpg", category="cmr",
            file_name="cmr_loaded.jpg", idempotency_key="sha256:cmr-loaded",
        )
        mobile.update_status(trip_id, "In Transit", offline=True,
                             idempotency_key="np-in-transit")
        mobile.queue_expense(
            trip_id, description="Scale ticket Brasov", amount=15.0,
            currency="EUR", idempotency_key="np-expense-scale",
        )
        mobile.update_status(trip_id, "Delivered", offline=True,
                             idempotency_key="np-delivered")

        assert mobile.pending_actions() == 5
        # Nothing reached the server while partitioned.
        assert trip_service.get_by_id(trip_id)["status"] == "Planned"
        assert desktop.get_trip(trip_id)["status"] == "Planned"

        # ── Heal: one sync replays the queue through the real transition path.
        results = mobile.sync_queue()
        assert len(results) == 5
        assert mobile.pending_actions() == 0

        by_key = {r["idempotency_key"]: r for r in results}
        assert set(by_key) == {
            "np-loading", "sha256:cmr-loaded", "np-in-transit",
            "np-expense-scale", "np-delivered",
        }
        # Every queued action executed on heal — none silently dropped.
        for key in ("np-loading", "np-in-transit", "np-delivered"):
            entry = by_key[key]
            assert entry["action"] == "update_status"
            assert entry["applied"] is True
            assert entry["result"] is True
        doc = by_key["sha256:cmr-loaded"]
        assert doc["action"] == "document_upload" and doc["applied"] is True
        expense = by_key["np-expense-scale"]
        assert expense["action"] == "expense" and expense["applied"] is True

        # Exactly one status event per legal transition — Loading, In Transit,
        # Delivered — regardless of the document/expense actions interleaved.
        events = event_monitor.get_events("trip.status_changed")
        assert [e["data"]["new_status"] for e in events] == [
            "Loading", "In Transit", "Delivered",
        ]
        event_monitor.assert_event_count("trip.status_changed", 3)

        # P6 convergence: both platforms settle on the one server-confirmed
        # business state — the trip is Delivered everywhere.
        assert trip_service.get_by_id(trip_id)["status"] == "Delivered"
        assert desktop.get_trip(trip_id)["status"] == "Delivered"
        assert mobile.get_trip(trip_id)["status"] == "Delivered"

    def test_duplicate_status_replay_discarded_and_counted_once(
        self, db, trip_service, event_monitor
    ):
        """8.5.6 / P9: duplicate 'Delivered' submission dedups on replay.

        The driver double-submits the Delivered update while offline (network
        retry). The sync applies it exactly once — the duplicate key is
        discarded and reported in the per-action results, never applied twice.
        """
        ids = build_ionut_persona(db)
        trip_id = ids["trip_ids"]["in_transit"]  # In Transit → Delivered legal

        mobile = _new_mobile(trip_service, db)
        event_monitor.track("trip.status_changed")

        # Same logical intent queued twice while the network is down.
        mobile.update_status(trip_id, "Delivered", offline=True,
                             idempotency_key="np-delivered-dup")
        mobile.update_status(trip_id, "Delivered", offline=True,
                             idempotency_key="np-delivered-dup")
        assert mobile.pending_actions() == 2
        assert trip_service.get_by_id(trip_id)["status"] == "In Transit"

        results = mobile.sync_queue()
        assert len(results) == 2

        applied = [r for r in results if r["applied"]]
        deduped = [r for r in results if not r["applied"]]
        # First copy applied through the real transition path…
        assert len(applied) == 1
        assert applied[0]["idempotency_key"] == "np-delivered-dup"
        assert applied[0]["action"] == "update_status"
        assert applied[0]["result"] is True
        # …the duplicate was intercepted before apply and *reported*, not
        # silently discarded (an undeduped replay would have shown result False).
        assert len(deduped) == 1
        assert deduped[0]["idempotency_key"] == "np-delivered-dup"
        assert deduped[0]["result"] is None

        assert mobile.pending_actions() == 0
        assert mobile.replayed_keys() == {"np-delivered-dup"}
        # Exactly one recorded transition → one event.
        event_monitor.assert_event_count("trip.status_changed", 1)
        assert trip_service.get_by_id(trip_id)["status"] == "Delivered"


class TestLastWriterWinsArbitration:
    """Scenario 2 — R-CONF-01 last-writer-wins arbitration.

    Conflicting queued status updates from different sources are applied in
    server order through the real transition path. The final stored status is
    the one the server applied last; both platforms show that same state.
    """

    def test_rconf01_last_writer_wins_after_heal(
        self, db, trip_service, invoice_service, event_bus, event_monitor
    ):
        """R-CONF-01: desktop commits Loading; mobile queues In Transit.

        Dispatcher changes the trip to Loading on the desktop at T=0 while the
        driver queues In Transit offline at T=0. On heal (T=60) the mobile's
        newer update is applied last-writer-wins — In Transit is a legal
        transition from Loading — and both platforms show In Transit.
        """
        ids = build_ionut_persona(db)
        trip_id = ids["trip_ids"]["planned"]  # Planned

        desktop = DesktopClient(trip_service, invoice_service, event_bus, db)
        mobile = _new_mobile(trip_service, db)
        event_monitor.track("trip.status_changed")

        # Desktop (online at T=0): Loading is committed at the server.
        assert desktop.transition_status(trip_id, "Loading") is True
        assert trip_service.get_by_id(trip_id)["status"] == "Loading"

        # Mobile (offline at T=0): In Transit is queued, not yet applied.
        mobile.update_status(trip_id, "In Transit", offline=True,
                             idempotency_key="rconf01-mobile")
        assert trip_service.get_by_id(trip_id)["status"] == "Loading"
        assert mobile.pending_actions() == 1

        # Heal at T=60: the queued update is applied in server order against
        # the state the desktop already committed → last writer wins.
        results = mobile.sync_queue()
        assert len(results) == 1
        entry = results[0]
        assert entry["applied"] is True
        assert entry["result"] is True  # Loading → In Transit is legal

        final = trip_service.get_by_id(trip_id)["status"]
        # The final stored status equals the last-applied transition.
        assert final == "In Transit"
        # Both platforms read the identical server-confirmed state.
        assert desktop.get_trip(trip_id)["status"] == final
        assert mobile.get_trip(trip_id)["status"] == final
        event_monitor.assert_event_count("trip.status_changed", 2)

    def test_server_order_arbitration_rejects_stale_queued_update(
        self, db, trip_service, invoice_service, event_bus, event_monitor
    ):
        """Server-order arbitration: an out-of-order queue cannot win.

        Two devices queue conflicting updates while offline (desk device wants
        Loading, driver mobile wants In Transit). If the driver mobile syncs
        first, In Transit is *not* legal from Planned — the real transition
        path rejects it (result False, no event) — and the later Loading is
        the last-applied state both platforms converge on.
        """
        ids = build_ionut_persona(db)
        trip_id = ids["trip_ids"]["planned"]

        desktop = DesktopClient(trip_service, invoice_service, event_bus, db)
        desk_device = _new_mobile(trip_service, db)      # dispatcher, offline
        driver_device = _new_mobile(trip_service, db)    # driver, offline
        event_monitor.track("trip.status_changed")

        # Both queued during the partition; neither reached the server yet.
        desk_device.update_status(trip_id, "Loading", offline=True,
                                  idempotency_key="desk-loading")
        driver_device.update_status(trip_id, "In Transit", offline=True,
                                    idempotency_key="driver-intransit")
        assert trip_service.get_by_id(trip_id)["status"] == "Planned"

        # Heal order = server application order. The driver device connects
        # first and replays In Transit against a still-Planned trip.
        stale = driver_device.sync_queue()
        assert len(stale) == 1
        # Executed but rejected: Planned → In Transit is not a legal move, so
        # the real transition path refuses it without changing state.
        assert stale[0]["applied"] is True
        assert stale[0]["result"] is False
        assert trip_service.get_by_id(trip_id)["status"] == "Planned"

        # The desk device syncs second: Loading is legal from Planned and is
        # the last successfully-applied update.
        desk_results = desk_device.sync_queue()
        assert len(desk_results) == 1
        assert desk_results[0]["result"] is True
        final = trip_service.get_by_id(trip_id)["status"]
        assert final == "Loading"

        # Only the accepted transition fired a status event (the rejected
        # stale update never produced a state change).
        event_monitor.assert_event_count("trip.status_changed", 1)
        # One business state, identical on every platform.
        assert desktop.get_trip(trip_id)["status"] == final
        assert desk_device.get_trip(trip_id)["status"] == final
        assert driver_device.get_trip(trip_id)["status"] == final


class TestOfflineDocumentUploadDedup:
    """Scenario 3 — R-CONF-03: offline document upload dedup by content hash.

    The content hash doubles as the upload's idempotency key. Re-uploading
    the same content is deduplicated and the discard is *reported* in the
    per-action sync results (never a silent drop); distinct hashes are both
    preserved.
    """

    def test_same_content_hash_reupload_deduped_and_reported(
        self, db, trip_service
    ):
        ids = build_ionut_persona(db)
        trip_id = ids["trip_ids"]["planned"]
        mobile = _new_mobile(trip_service, db)

        same_hash = "sha256:cmr-front-dupe"
        # Double-tap while offline queues the same upload twice in one batch.
        mobile.queue_document_upload(
            trip_id, title="cmr_front.jpg", category="cmr",
            file_name="cmr_front.jpg", idempotency_key=same_hash,
        )
        mobile.queue_document_upload(
            trip_id, title="cmr_front.jpg", category="cmr",
            file_name="cmr_front.jpg", idempotency_key=same_hash,
        )
        assert mobile.pending_actions() == 2

        results = mobile.sync_queue()
        assert len(results) == 2
        applied = [r for r in results if r["applied"]]
        deduped = [r for r in results if not r["applied"]]
        # One upload preserved…
        assert len(applied) == 1 and applied[0]["result"] is True
        # …one deduplicated — but reported per-action, not silently dropped.
        assert len(deduped) == 1
        assert deduped[0]["idempotency_key"] == same_hash
        assert deduped[0]["action"] == "document_upload"
        assert deduped[0]["result"] is None
        assert mobile.pending_actions() == 0

        # A later retry of the same content (post-heal reconnect blip) is
        # also deduplicated against the session's replayed keys.
        mobile.queue_document_upload(
            trip_id, title="cmr_front.jpg", category="cmr",
            file_name="cmr_front.jpg", idempotency_key=same_hash,
        )
        retry = mobile.sync_queue()
        assert len(retry) == 1
        assert retry[0]["idempotency_key"] == same_hash
        assert retry[0]["applied"] is False
        assert retry[0]["result"] is None
        assert mobile.replayed_keys() == {same_hash}

    def test_distinct_content_hashes_both_preserved(self, db, trip_service):
        ids = build_ionut_persona(db)
        trip_id = ids["trip_ids"]["planned"]
        mobile = _new_mobile(trip_service, db)

        hash_front = "sha256:cmr-front"
        hash_back = "sha256:cmr-back"
        # Two distinct photos of the same CMR uploaded offline.
        mobile.queue_document_upload(
            trip_id, title="cmr_front.jpg", category="cmr",
            file_name="cmr_front.jpg", idempotency_key=hash_front,
        )
        mobile.queue_document_upload(
            trip_id, title="cmr_back.jpg", category="cmr",
            file_name="cmr_back.jpg", idempotency_key=hash_back,
        )
        assert mobile.pending_actions() == 2

        results = mobile.sync_queue()
        applied = [r for r in results if r["applied"]]
        # Both distinct uploads preserved — neither merged nor dropped.
        assert len(applied) == 2
        assert {r["idempotency_key"] for r in applied} == {hash_front, hash_back}
        assert all(r["action"] == "document_upload" for r in applied)
        assert all(r["result"] is True for r in applied)
        assert len(results) == 2
        assert mobile.pending_actions() == 0
        assert mobile.replayed_keys() == {hash_front, hash_back}
