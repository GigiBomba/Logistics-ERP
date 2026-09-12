"""Platform parity: Offline behavior of the mobile client (P3-U3).

Covers the offline queueing contract of the simulated ``MobileClient``:

* an offline status update is queued, applied exactly once on sync, and
  replayed keys are deduplicated on a re-sync (no double-apply);
* an offline expense that exceeds a limit must be flagged for approval
  on sync — documented gap (server-side validation absent → skip);
* offline document uploads are preserved and stay linked to their trip
  after sync, and re-uploading the same file (same content hash) dedups
  instead of silently discarding (R-CONF-03);
* login requires connectivity — documented gap (no offline-auth path at
  the service layer → skip);
* a status-change round trip stays within a fixed latency budget.

NOTE ON THE SHARED FIXTURE (surfaced, not modified — this unit may only
create this test file): ``MobileClient._replay_action`` instantiates
``TripStatusEngine(self.db, self.trip_service)`` and calls
``engine.force_trip_status(...)``, but ``TripStatusEngine.__init__`` only
accepts ``db`` and that class no longer exposes ``force_trip_status``
(it moved to ``TripStatusWorkflow`` / ``OperationsEngine``).  All queue /
dedup semantics under test here are exercised through a local subclass that
replays offline status updates through the real
``TripStatusEngine(db).transition(...)`` service path instead.
"""

from __future__ import annotations

import logging
import time

import pytest

from services.operations.trip_status_engine import TripStatusEngine
from tests.workflow_integrity.fixtures.multi_platform_client import MobileClient
from tests.workflow_integrity.personas import build_ionut_persona

pytestmark = pytest.mark.parity

logger = logging.getLogger(__name__)

# ── Latency budget (informational, deterministic) ────────────────────
SYNC_LATENCY_BUDGET_S = 5.0


class _ReplaySafeMobileClient(MobileClient):
    """MobileClient whose offline status replay uses the current service API.

    The shared fixture replays status updates through
    ``TripStatusEngine(db, trip_service).force_trip_status(...)``, an
    interface that no longer exists.  This subclass keeps every queuing /
    dedup behavior of the fixture intact and swaps only the broken
    status-replay call for the real ``TripStatusEngine(db).transition()``.
    """

    def _replay_action(self, action: str, item: dict) -> bool | None:
        if action == "update_status":
            try:
                engine = TripStatusEngine(self.db)
                return engine.transition(
                    item["trip_id"], item["status"], trigger="mobile_sync"
                )
            except Exception as exc:  # invalid / unknown transitions → False
                logger.warning(
                    "offline status replay failed for trip %s: %s",
                    item.get("trip_id"), exc,
                )
                return False
        return super()._replay_action(action, item)


class TestOfflineStatusUpdate:
    """Offline status updates: queue → apply-once → replay dedup."""

    def test_offline_status_update_queued_and_applied_once(
        self, db, trip_service, event_monitor
    ):
        """An offline update is queued, then applied exactly once on sync."""
        ids = build_ionut_persona(db)
        planned_id = ids["trip_ids"]["planned"]

        client = _ReplaySafeMobileClient(trip_service, db)
        event_monitor.track("trip.status_changed")

        # Offline: nothing is applied yet — the action is queued.
        client.update_status(
            planned_id, "Loading", offline=True, idempotency_key="offline-status-1"
        )
        assert client.pending_actions() == 1
        assert trip_service.get_by_id(planned_id)["status"] == "Planned"

        # Sync replays the queued action against the shared backend.
        results = client.sync_queue()
        assert len(results) == 1
        entry = results[0]
        assert entry["action"] == "update_status"
        assert entry["idempotency_key"] == "offline-status-1"
        assert entry["applied"] is True
        assert entry["result"] is True

        assert trip_service.get_by_id(planned_id)["status"] == "Loading"
        assert "offline-status-1" in client.replayed_keys()
        # The single action produced exactly one status-change event.
        event_monitor.assert_event_count("trip.status_changed", 1)

    def test_resync_is_noop_and_replayed_key_is_deduped(
        self, db, trip_service, event_monitor
    ):
        """Re-syncing the same queue is a no-op; a same-key retry dedups."""
        ids = build_ionut_persona(db)
        planned_id = ids["trip_ids"]["planned"]

        client = _ReplaySafeMobileClient(trip_service, db)
        event_monitor.track("trip.status_changed")

        client.update_status(
            planned_id, "Loading", offline=True, idempotency_key="offline-status-1"
        )
        client.sync_queue()
        event_monitor.assert_event_count("trip.status_changed", 1)

        # Re-sync of the drained queue is a pure no-op.
        assert client.sync_queue() == []
        assert client.pending_actions() == 0
        assert trip_service.get_by_id(planned_id)["status"] == "Loading"
        event_monitor.assert_event_count("trip.status_changed", 1)

        # A retry of the same logical action (same idempotency key) is
        # deduplicated via the replayed-keys set — reported, not applied.
        client.update_status(
            planned_id, "Loading", offline=True, idempotency_key="offline-status-1"
        )
        assert client.pending_actions() == 1
        retry = client.sync_queue()
        assert len(retry) == 1
        assert retry[0]["applied"] is False
        assert retry[0]["result"] is None

        assert trip_service.get_by_id(planned_id)["status"] == "Loading"
        assert client.replayed_keys() == {"offline-status-1"}
        event_monitor.assert_event_count("trip.status_changed", 1)


class TestOfflineExpenseApproval:
    """Offline expense handling on sync (approval-gated)."""

    @pytest.mark.skip(
        reason="Documented gap (parity P3-U3): no server-side over-limit "
        "expense validation in the service layer, and the simulated sync "
        "queue-result structure carries no approval flag — nothing to assert."
    )
    def test_over_limit_expense_flagged_for_approval_on_sync(self, db, trip_service):
        """An expense above the limit must surface an approval flag on sync."""
        ids = build_ionut_persona(db)
        planned_id = ids["trip_ids"]["planned"]

        client = _ReplaySafeMobileClient(trip_service, db)
        key = client.queue_expense(
            planned_id, description="Fuel receipt above limit", amount=9999.0
        )
        assert client.pending_actions() == 1

        results = client.sync_queue()
        entry = next(r for r in results if r["idempotency_key"] == key)
        # Absent until the server-side approval validation exists (see skip).
        assert entry.get("needs_approval") is True


class TestOfflineDocumentUpload:
    """R-CONF-03: Offline document uploads are preserved and deduplicated."""

    def test_distinct_document_hashes_both_preserved_on_sync(
        self, db, trip_service
    ):
        """Two different file hashes are both preserved and stay linked."""
        ids = build_ionut_persona(db)
        planned_id = ids["trip_ids"]["planned"]

        client = _ReplaySafeMobileClient(trip_service, db)
        # Content-addressed uploads: the file hash doubles as the idempotency key.
        hash_a = "sha256:aaaa"
        hash_b = "sha256:bbbb"
        key_a = client.queue_document_upload(
            planned_id, title="cmr_front.jpg", category="cmr",
            file_name="cmr_front.jpg", idempotency_key=hash_a,
        )
        key_b = client.queue_document_upload(
            planned_id, title="cmr_back.jpg", category="cmr",
            file_name="cmr_back.jpg", idempotency_key=hash_b,
        )
        assert (key_a, key_b) == (hash_a, hash_b)
        assert client.pending_actions() == 2

        results = client.sync_queue()
        applied = [r for r in results if r["applied"]]
        # Both distinct uploads were preserved — neither dropped nor merged.
        assert {r["idempotency_key"] for r in applied} == {hash_a, hash_b}
        assert {r["action"] for r in applied} == {"document_upload"}
        assert all(r["result"] is True for r in applied)
        # No queue residue: every queued action got a result entry.
        assert len(results) == 2
        assert client.pending_actions() == 0
        assert client.replayed_keys() == {hash_a, hash_b}

    def test_same_document_hash_reupload_dedups_without_silent_discard(
        self, db, trip_service
    ):
        """Re-uploading the same file hash dedups and reports it explicitly."""
        ids = build_ionut_persona(db)
        planned_id = ids["trip_ids"]["planned"]

        client = _ReplaySafeMobileClient(trip_service, db)
        same_hash = "sha256:cccc"
        client.queue_document_upload(
            planned_id, title="cmr_repeat.jpg", category="cmr",
            file_name="cmr_repeat.jpg", idempotency_key=same_hash,
        )
        client.sync_queue()
        assert same_hash in client.replayed_keys()

        # Driver retries the same upload after a reconnect blip.
        client.queue_document_upload(
            planned_id, title="cmr_repeat.jpg", category="cmr",
            file_name="cmr_repeat.jpg", idempotency_key=same_hash,
        )
        results = client.sync_queue()
        # A result entry IS returned for the duplicate — not silently dropped.
        assert len(results) == 1
        dup = results[0]
        assert dup["idempotency_key"] == same_hash
        assert dup["action"] == "document_upload"
        assert dup["applied"] is False
        assert dup["result"] is None
        assert client.pending_actions() == 0


class TestOfflineLogin:
    """Connectivity requirements at the auth boundary."""

    @pytest.mark.skip(
        reason="Documented gap (parity P3-U3): no offline-auth path at the "
        "service layer — login always requires connectivity."
    )
    def test_login_requires_connectivity(self):
        """Offline login must be impossible; no auth path exists offline."""
        # There is no offline login code path to exercise — the service layer
        # exposes auth only over the connected API.  See skip reason.
        raise AssertionError("unreachable — guarded by pytest.mark.skip")


class TestSyncLatency:
    """Sync latency informational budget checks (no sleeps)."""

    def test_status_change_roundtrip_within_sync_budget(
        self, db, trip_service, event_monitor
    ):
        """A queued status change must round-trip within the latency budget."""
        ids = build_ionut_persona(db)
        planned_id = ids["trip_ids"]["planned"]

        client = _ReplaySafeMobileClient(trip_service, db)
        event_monitor.track("trip.status_changed")

        start = time.perf_counter()
        client.update_status(
            planned_id, "Loading", offline=True,
            idempotency_key="latency-status-1",
        )
        assert client.pending_actions() == 1
        results = client.sync_queue()
        # Deterministic wait-free confirmation: the event is published
        # synchronously by the replay, so this never sleeps.
        event_monitor.assert_event_published(
            "trip.status_changed", data={"trip_id": planned_id}
        )
        elapsed = time.perf_counter() - start

        logger.info(
            "offline status-change round trip for trip %s: %.3fs (budget %.1fs)",
            planned_id, elapsed, SYNC_LATENCY_BUDGET_S,
        )
        assert results and results[0]["applied"] is True
        assert trip_service.get_by_id(planned_id)["status"] == "Loading"
        assert elapsed <= SYNC_LATENCY_BUDGET_S, (
            f"Status-change round trip took {elapsed:.3f}s — "
            f"exceeds the {SYNC_LATENCY_BUDGET_S:.1f}s budget"
        )
