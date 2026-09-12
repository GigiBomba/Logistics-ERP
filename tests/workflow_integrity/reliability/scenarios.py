"""Reliability scenario registry.

Pure data module — no fixtures, no imports of test infrastructure.

References:
- Blueprint §8 "Reliability Under Real Operations" (scenarios 1-10).
- Blueprint §13.2 "Conflict Resolution Tests" (R-CONF-01..R-CONF-07).

Scenario ids follow the ids already used by the existing test files:
- R-01 .. R-10     (tests/workflow_integrity/reliability/test_reliability.py)
- R-CONF-01 .. R-CONF-07 (tests/workflow_integrity/reliability/test_conflict_resolution.py)
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Scenario:
    """A reliability scenario taken from the architecture blueprint.

    Attributes:
        id: Stable scenario identifier (e.g. "R-01", "R-CONF-03").
        title: Short human-readable title.
        trigger: The real-world event that starts the scenario.
        expected_recovery: Ordered list of expected recovery behaviors.
        failure_modes: Failure modes the tests must guard against.
    """

    id: str
    title: str
    trigger: str
    expected_recovery: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)


SCENARIOS: list[Scenario] = [
    Scenario(
        id="R-01",
        title="Driver Uploads CMR in Tunnel (Signal Loss)",
        trigger=(
            "Driver uploads a CMR document via mobile app while entering a tunnel. "
            "Upload starts, signal drops at 60%."
        ),
        expected_recovery=[
            "Mobile detects connectivity loss via ConnectivityMonitor",
            "Upload is queued in ActionQueue with idempotency key",
            "OfflineBanner shown on mobile",
            'Driver sees "Upload paused — will resume when connected" status',
            (
                "On signal restore: queue replays FIFO, upload resumes from checkpoint "
                "or restarts with dedup"
            ),
            "Server receives complete upload → deducts by idempotency key",
            'Driver sees "Upload complete" notification',
            "OCR pipeline triggers on completed upload",
        ],
        failure_modes=[
            "Upload completes on server but mobile never gets confirmation (stale UI)",
            "Upload fails entirely after multiple retries (needs user to re-upload)",
            "Partial upload saved on server as corrupt document",
        ],
    ),
    Scenario(
        id="R-02",
        title="Backend Restarts During Dispatch",
        trigger=(
            'Dispatcher clicks "Assign Truck 3 to Trip 42" at the exact moment the '
            "backend restarts (deploy, crash, maintenance)."
        ),
        expected_recovery=[
            "Request reaches backend → connection lost mid-processing",
            'Frontend detects timeout → shows "Connection lost. Retrying..."',
            "On reconnect: frontend checks trip state — is truck 3 assigned?",
            '"Dispatch completed successfully" when the assignment committed',
            '"Dispatch failed. Please try again." with pre-filled form when it did not',
            (
                "No partial state: truck 3 not assigned to conflicting trip, trip not "
                "left in intermediary state"
            ),
        ],
        failure_modes=[
            'Trip shows "Loading" but truck is not actually assigned',
            "Truck shows assigned to two trips simultaneously",
            "Undo token created but action never completed",
        ],
    ),
    Scenario(
        id="R-03",
        title="Mobile Submits Duplicate Actions",
        trigger=(
            'Driver taps "Mark as Delivered" twice rapidly while in poor connectivity. '
            "Both requests reach server."
        ),
        expected_recovery=[
            "First request: status changes to Delivered, history recorded, downstream actions triggered",
            (
                "Second request: server detects trip is already Delivered → idempotency "
                "check → returns current state (not error)"
            ),
            "Driver sees no error, just the current state",
            "No duplicate CMR generation, no duplicate odometer updates, no duplicate invoice drafts",
        ],
        failure_modes=[
            "Duplicate status transition creates duplicate invoice draft",
            "Duplicate odometer update (mileage doubled)",
            "Duplicate history entry",
        ],
    ),
    Scenario(
        id="R-04",
        title="OCR Queue is Delayed",
        trigger=(
            "50 documents uploaded simultaneously by multiple drivers. "
            "OCR queue backs up."
        ),
        expected_recovery=[
            "Queue processes documents sequentially (2 workers)",
            'Dispatcher sees document status "Processing (waiting... position 12 of 50)"',
            "Documents processed in order, no loss",
            "High-priority documents (POD for critical deliveries) can be prioritized",
            "If queue stalls → alert to dispatcher",
            "All documents eventually processed, no silent drops",
        ],
        failure_modes=[
            "Documents processed out of order",
            "Queue stall without notification",
            "Document dropped silently when queue is full",
            'Worker crash mid-processing leaves document in "processing" state forever',
        ],
    ),
    Scenario(
        id="R-05",
        title="Invoice Email Fails",
        trigger=(
            "Accountant sends invoice email. SMTP server returns 5xx error "
            "(recipient server rejecting)."
        ),
        expected_recovery=[
            'Email status recorded as "Failed"',
            'Notification: "Invoice #42 email to client@example.com failed: recipient server rejected"',
            "Retry scheduled (3 attempts at 15-minute intervals)",
            'After all retries exhausted: escalated to accountant with "Manual intervention required"',
            "Accountant can: edit email, resend, download PDF and send manually",
            'Invoice not marked as "Sent" until email actually delivered',
        ],
        failure_modes=[
            "Invoice marked sent but email never delivered",
            "Silent retry without notifying user",
            "Retry count exhausted silently",
            "PDF not attached to retry",
        ],
    ),
    Scenario(
        id="R-06",
        title="Sync Conflict — Desktop vs Mobile",
        trigger=(
            "Dispatcher cancels trip on desktop while driver marks it delivered "
            "on mobile (offline)."
        ),
        expected_recovery=[
            'Desktop: trip cancelled, status = "Cancelled", notification queued to driver',
            "Mobile (offline): driver marks delivered, queued",
            "Mobile comes online: sync attempt",
            "Server detects conflict: trip is Cancelled, mobile says Delivered",
            "Cancellation wins (as per conflict resolution rules)",
            (
                'Driver receives notification: "Trip 42 was cancelled by dispatcher. '
                'Your status update was not applied."'
            ),
            'Mobile UI shows: "Trip cancelled" with dispatcher\'s reason',
            "No partial state: documents uploaded by driver remain linked to trip record",
        ],
        failure_modes=[
            "Both updates applied (trip is both Cancelled and Delivered)",
            "Mobile's update silently overwrites desktop's Cancellation",
            "Documents from driver lost during conflict resolution",
            "No notification to driver about the conflict",
        ],
    ),
    Scenario(
        id="R-07",
        title="Concurrent Invoice Generation",
        trigger=(
            "ARGO and accountant both trigger invoice generation for the same trip "
            "simultaneously."
        ),
        expected_recovery=[
            "First request creates invoice in `draft` status",
            (
                "Second request detects invoice already exists for this trip → returns "
                "existing invoice (not error, not duplicate)"
            ),
            "No duplicate invoice created",
            'System logs: "Invoice generation requested for trip 42 — invoice already exists"',
        ],
        failure_modes=[
            "Duplicate invoices created for same trip",
            "Error thrown that confuses the user",
            "Race condition creates two invoices, one of which is orphaned",
        ],
    ),
    Scenario(
        id="R-08",
        title="Multi-Tenant Data Isolation Breach",
        trigger=(
            "Company A's dispatcher searches for a truck by plate number that "
            "belongs to Company B."
        ),
        expected_recovery=[
            'Search returns empty or "not found"',
            "No data from Company B is visible to Company A",
            "No error that reveals existence of Company B's data",
        ],
        failure_modes=[
            "Truck from Company B appears in Company A's search results",
            "IDOR vulnerability: Company A can access Company B's trip details",
            "Analytics cross-contamination: Company A's revenue includes Company B's data",
        ],
    ),
    Scenario(
        id="R-09",
        title="Database Connection Pool Exhaustion",
        trigger=(
            "100 concurrent requests hit the backend (during peak operations "
            "with load testing)."
        ),
        expected_recovery=[
            "Requests queued, processed as connections become available",
            "Individual request timeouts handled gracefully per request (not cascading failure)",
            "No data corruption from half-completed transactions",
            "Pool recovers when load subsides",
            "Monitoring alert fires at 80% pool utilization",
        ],
        failure_modes=[
            "Requests fail with unhelpful errors",
            "Transaction partially commits, leaving inconsistent state",
            "Pool never recovers (connection leak)",
        ],
    ),
    Scenario(
        id="R-10",
        title="ARGO Plan Execution Partially Fails",
        trigger=(
            "ARGO attempts 5-step plan (search loads → evaluate margin → dispatch trucks → "
            "generate invoices → update analytics). Step 3 fails (truck unavailable)."
        ),
        expected_recovery=[
            "Plan stops at failed step",
            "Completed steps (search, evaluate) remain valid",
            "Failed step (dispatch) logged with reason",
            "Remaining steps (invoices, analytics) not executed — they depended on dispatch",
            'User sees: "Plan partially executed. Dispatched 2 of 3 trucks. Truck 7 unavailable."',
            "User can: retry failed step with different truck, roll back completed steps, or proceed",
            "Rollback (undo) reverts completed dispatches cleanly",
        ],
        failure_modes=[
            (
                "Plan continues executing after failure (dispatches 2 trucks, "
                "generates invoices for them without dispatch)"
            ),
            "Partial rollback (truck dispatched but not undone)",
            "No clear error message to user",
        ],
    ),
]

R_CONFLICT_SCENARIOS: list[Scenario] = [
    Scenario(
        id="R-CONF-01",
        title="Same Trip Edited on Desktop and Mobile Simultaneously",
        trigger=(
            "Dispatcher opens trip 42 on desktop; driver opens trip 42 on mobile (offline). "
            "Dispatcher changes status to 'Loading' on desktop at T=0; driver changes status "
            "to 'In Transit' on mobile at T=0 (offline, queued). Mobile comes online at T=60s."
        ),
        expected_recovery=[
            'Desktop status "Loading" committed at server at T=0',
            (
                'Mobile sync at T=60s: server detects mobile\'s "In Transit" is newer '
                'timestamp → legal transition from "Loading" → accepted'
            ),
            'Both platforms show "In Transit"',
            'Both users receive notification: "Trip 42 status updated to In Transit"',
            "No data loss, no duplicate events",
        ],
        failure_modes=[
            (
                "Both timestamps identical → server picks one, other gets "
                '"State changed since your edit. Current: Loading. Your edit: In Transit. '
                'Apply anyway?"'
            ),
        ],
    ),
    Scenario(
        id="R-CONF-02",
        title="Driver Marks Delivered While Dispatcher Cancels Trip",
        trigger=(
            "Dispatcher cancels trip 42 on desktop at T=0 → committed at T=0. "
            "Driver (offline) marks trip 42 as Delivered at T=0 → queued. "
            "Mobile comes online at T=120s."
        ),
        expected_recovery=[
            "Desktop cancellation committed at server at T=0",
            (
                "Mobile sync: server detects trip is Cancelled. Mobile's 'Delivered' is "
                "rejected (Cancellation wins per §13.1 authority matrix)"
            ),
            (
                'Driver sees: "Trip 42 was cancelled by dispatcher. '
                'Your status update was not applied."'
            ),
            "Documents uploaded by driver remain linked to trip record",
            "Cancellation reason visible to driver",
        ],
        failure_modes=[
            (
                "Mobile Delivered overwrites desktop Cancellation → trip shows Delivered "
                "after being operationally cancelled"
            ),
        ],
    ),
    Scenario(
        id="R-CONF-03",
        title="OCR Upload Occurs During Offline Period",
        trigger=(
            "Driver uploads CMR document while offline → queued in ActionQueue. "
            "Dispatcher uploads same document (different photo) to same trip on desktop. "
            "Mobile comes online, queued upload syncs."
        ),
        expected_recovery=[
            "Both documents preserved in server with different file hashes",
            "Both linked to same trip",
            "OCR runs independently on both",
            'Driver sees "Upload complete. 2 documents linked to trip 42"',
            "No duplicate trip matching triggered",
        ],
        failure_modes=[
            (
                "Same file hash from both → deduped, but one upload silently discarded "
                "without notification"
            ),
        ],
    ),
    Scenario(
        id="R-CONF-04",
        title="Duplicate Invoice Creation After Reconnect",
        trigger=(
            "ARGO generates invoice for trip 42 at T=0. Accountant (offline) also generates "
            "invoice for trip 42 at T=0. Accountant comes online at T=300s."
        ),
        expected_recovery=[
            "ARGO's invoice committed at server at T=0",
            (
                "Accountant's sync: server detects invoice already exists for trip 42 → "
                "rejects duplicate"
            ),
            'Accountant sees: "Invoice for trip 42 already exists. Opening existing invoice."',
            "No duplicate invoice created",
        ],
        failure_modes=[
            "Two invoices created for same trip, no notification to either creator",
        ],
    ),
    Scenario(
        id="R-CONF-05",
        title="ARGO Action Executed While Device Is Offline",
        trigger=(
            'User (desktop) tells ARGO: "Dispatch truck 3 to load TX-123" at T=0. '
            "Network drops between desktop and backend at T=1s. ARGO plan execution starts, "
            "partially completes step 1 (search loads), step 2 fails (dispatch)."
        ),
        expected_recovery=[
            'Plan saved on server with status "interrupted" when connection lost',
            (
                'On reconnect: ARGO reports "Your plan was interrupted. Completed: found '
                'load TX-123. Pending: dispatch. Resume?"'
            ),
            "User can resume, modify, or cancel",
            "No partial dispatch committed",
        ],
        failure_modes=[
            (
                "Plan step commits partially (truck assigned) without user confirmation → "
                "truck blocked for other loads"
            ),
        ],
    ),
    Scenario(
        id="R-CONF-06",
        title="Clock Skew Between Devices",
        trigger=(
            "Desktop clock is 5 minutes ahead of server; mobile clock is 5 minutes behind "
            "server. Both update trip 42 status at approximately the same wall-clock time."
        ),
        expected_recovery=[
            "Server rejects timestamps that are > 30s in the future or > 5min in the past",
            "Uses server timestamp for conflict resolution, not device timestamp",
            "Both devices notified of the authoritative timestamp",
            "Audit log records server timestamp as authoritative",
        ],
        failure_modes=[
            (
                'Device with clock 5min ahead creates "future" conflict that takes '
                "priority incorrectly"
            ),
        ],
    ),
    Scenario(
        id="R-CONF-07",
        title="Retry Storms After Connectivity Restoration",
        trigger=(
            "50 mobile devices come online simultaneously after a 2-hour network outage. "
            "Each device has 15-20 queued actions (status updates, document uploads, "
            "expense submissions)."
        ),
        expected_recovery=[
            "Server processes sync requests in device FIFO order",
            "Idempotency keys prevent duplicate processing per device",
            "Conflict detection applies to each action individually",
            "Each device receives per-action result (accepted/rejected/conflict)",
            "Server does not exceed connection pool limits (see Scenario 9)",
            'Processing backlog is visible to operations: "512 pending sync actions from 23 devices"',
        ],
        failure_modes=[
            "Server thundering-herd crash; some devices' actions silently lost",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Coverage map: scenario id -> dotted test names from the EXISTING test files.
#
# Only entries that already exist in the repo today are filled in.  Per-scenario
# test modules planned in blueprint §9 (e.g. test_signal_loss_upload.py,
# test_backend_restart.py, ...) do NOT exist yet, so their names are NOT
# referenced here — later P5 units will extend this map incrementally.
# ---------------------------------------------------------------------------
SCENARIO_COVERAGE: dict[str, list[str]] = {
    "R-01": [
        "tests.workflow_integrity.reliability.test_reliability."
        "TestDriverOfflineResilience.test_driver_upload_interrupted_by_signal_loss",
    ],
    "R-02": [
        "tests.workflow_integrity.reliability.test_reliability."
        "TestBackendRestartDuringDispatch.test_dispatch_survives_backend_restart",
    ],
    "R-03": [
        "tests.workflow_integrity.reliability.test_reliability."
        "TestMobileDuplicateActions.test_duplicate_delivery_marking_idempotent",
    ],
    "R-04": [
        "tests.workflow_integrity.reliability.test_reliability."
        "TestOCRQueueDelay.test_ocr_delayed_but_eventually_processed",
    ],
    "R-05": [
        "tests.workflow_integrity.reliability.test_reliability."
        "TestInvoiceEmailFailure.test_smtp_failure_invoice_still_finalized",
    ],
    "R-06": [
        "tests.workflow_integrity.reliability.test_reliability."
        "TestDesktopMobileSyncConflict.test_same_trip_edited_on_two_platforms",
    ],
    "R-07": [
        "tests.workflow_integrity.reliability.test_reliability."
        "TestConcurrentInvoiceGeneration.test_concurrent_invoice_creation_idempotent",
    ],
    "R-08": [
        "tests.workflow_integrity.reliability.test_reliability."
        "TestMultiTenantDataIsolation.test_concurrent_operations_on_different_companies",
    ],
    "R-09": [
        "tests.workflow_integrity.reliability.test_reliability."
        "TestDBConnectionPoolExhaustion.test_pool_exhaustion_recovers_gracefully",
    ],
    "R-10": [
        "tests.workflow_integrity.reliability.test_reliability."
        "TestARGOPartialFailure.test_argo_plan_partial_failure",
    ],
    # R-CONF-01..07 are covered by tests/workflow_integrity/reliability/test_conflict_resolution.py.
    "R-CONF-01": [
        "tests.workflow_integrity.reliability.test_conflict_resolution."
        "TestTwoPlatformConflict.test_concurrent_desktop_and_mobile_edit_merged",
    ],
    "R-CONF-02": [
        "tests.workflow_integrity.reliability.test_conflict_resolution."
        "TestDriverDeliveredDispatcherCancel.test_cancel_before_delivery_started_wins",
    ],
    "R-CONF-03": [
        "tests.workflow_integrity.reliability.test_conflict_resolution."
        "TestOCROfflineUpload.test_ocr_offline_queue_preserves_upload_order",
    ],
    "R-CONF-04": [
        "tests.workflow_integrity.reliability.test_conflict_resolution."
        "TestDuplicateInvoiceCreation.test_duplicate_invoice_after_reconnect_detected",
    ],
    "R-CONF-05": [
        "tests.workflow_integrity.reliability.test_conflict_resolution."
        "TestARGOOfflineAction.test_argo_offline_action",
    ],
    "R-CONF-06": [
        "tests.workflow_integrity.reliability.test_conflict_resolution."
        "TestClockSkewBetweenDevices.test_clock_skew_timestamps_reconciled",
    ],
    "R-CONF-07": [
        "tests.workflow_integrity.reliability.test_conflict_resolution."
        "TestRetryStorms.test_retry_storm_duplicate_detection",
    ],
}