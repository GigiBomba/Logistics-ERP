"""Workflow Friction Rules — pure registry (blueprint §6 / §11).

Data-only module: no logic beyond lookups, no pytest imports.

Severity & penalty per docs/blueprints/workflow_integrity_test_suite_architecture.md:
- R1-R7 are hard rules (violation = launch blocker), penalty -15 each (§11).
- S1-S5 are soft rules (violation = friction score penalty), penalty -5 each (§11).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrictionRule:
    """One workflow friction rule from blueprint §6."""
    id: str
    title: str
    severity: str  # "hard" | "soft"
    description: str
    check_description: str
    penalty: int  # -15 hard / -5 soft (§11 penalty formula)


# ─────────────────────────────────────────────────────────────────────────────
# Hard Rules (R1-R7) — Violation = Launch Blocker  (blueprint §6)
# ─────────────────────────────────────────────────────────────────────────────

HARD_RULES: dict[str, FrictionRule] = {
    "R1": FrictionRule(
        id="R1",
        title="No Duplicate Data Entry",
        severity="hard",
        description=(
            "Any data entered once (client name, address, plate number, driver "
            "name, trip details) must never need to be re-entered at any point "
            "in a workflow."
        ),
        check_description=(
            "Automated flow walks each golden workflow and records every data "
            "entry event. Any field entered more than once = FAIL."
        ),
        penalty=-15,
    ),
    "R2": FrictionRule(
        id="R2",
        title="No Dead-End Screens",
        severity="hard",
        description=(
            "Every screen must provide at least one forward navigation path OR "
            "explicitly indicate the workflow is complete."
        ),
        check_description=(
            "For each screen in each golden workflow, verify there is either a "
            '"Next" action or a "Complete" status indicator.'
        ),
        penalty=-15,
    ),
    "R3": FrictionRule(
        id="R3",
        title="No Mandatory Desktop for Driver-Only Tasks",
        severity="hard",
        description=(
            "A driver must be able to complete their entire workflow without "
            "ever accessing the desktop application."
        ),
        check_description=(
            "Driver persona workflow must be completable on mobile alone."
        ),
        penalty=-15,
    ),
    "R4": FrictionRule(
        id="R4",
        title="No Mandatory Mobile for Accounting Tasks",
        severity="hard",
        description=(
            "An accountant must be able to complete their entire workflow "
            "without ever accessing the mobile application."
        ),
        check_description=(
            "Accountant persona workflow must be completable on desktop alone."
        ),
        penalty=-15,
    ),
    "R5": FrictionRule(
        id="R5",
        title="No Hidden Knowledge Required",
        severity="hard",
        description=(
            "Any information needed to complete a step must be available on "
            "that screen or reachable in ≤2 clicks. The user must not need to "
            "memorize data between screens."
        ),
        check_description=(
            "For each step in every golden workflow, verify all required "
            "reference data is visible."
        ),
        penalty=-15,
    ),
    "R6": FrictionRule(
        id="R6",
        title="No Silent Failures",
        severity="hard",
        description=(
            "Any action that fails (API error, validation failure, network "
            "timeout, permission denied) must produce a visible, actionable "
            "error message to the user."
        ),
        check_description=(
            "Instrument each critical action in workflows. Simulate failure. "
            "Verify user-visible error."
        ),
        penalty=-15,
    ),
    "R7": FrictionRule(
        id="R7",
        title="No State Incoherence Across Platforms",
        severity="hard",
        description=(
            "A state change on one platform must be visible on all other "
            "platforms within the acceptable sync delay for that feature."
        ),
        check_description=(
            "Cross-platform state comparison after each workflow action."
        ),
        penalty=-15,
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Soft Rules (S1-S5) — Violation = Friction Score Penalty  (blueprint §6)
# ─────────────────────────────────────────────────────────────────────────────

SOFT_RULES: dict[str, FrictionRule] = {
    "S1": FrictionRule(
        id="S1",
        title="Maximum 3 Clicks for Common Operations",
        severity="soft",
        description=(
            "Any operation performed more than 10 times per day (status "
            "update, document upload, expense entry) must be doable in "
            "≤3 clicks."
        ),
        check_description=(
            "Verify every operation performed more than 10 times per day "
            "(status update, document upload, expense entry) is doable in "
            "≤3 clicks."
        ),
        penalty=-5,
    ),
    "S2": FrictionRule(
        id="S2",
        title="Workflow Completion Visibility",
        severity="soft",
        description=(
            "At any point in a multi-step workflow, the user must be able to "
            "see where they are (step 3 of 5) and how many steps remain."
        ),
        check_description=(
            "Verify the user can see where they are (step 3 of 5) and how "
            "many steps remain at any point in a multi-step workflow."
        ),
        penalty=-5,
    ),
    "S3": FrictionRule(
        id="S3",
        title="Confirmation on Destructive Actions",
        severity="soft",
        description=(
            "Any action that deletes data, cancels a trip, or changes "
            "financial state must require explicit confirmation. Pre-filled "
            "confirmation text is unacceptable; user must type or actively "
            "acknowledge."
        ),
        check_description=(
            "Verify every action that deletes data, cancels a trip, or "
            "changes financial state requires explicit confirmation; "
            "pre-filled confirmation text is unacceptable."
        ),
        penalty=-5,
    ),
    "S4": FrictionRule(
        id="S4",
        title="Undo Support for Multi-Edit Operations",
        severity="soft",
        description=(
            "Any batch operation (bulk dispatch, bulk invoice, bulk status "
            "change) must support undo for at least 30 minutes."
        ),
        check_description=(
            "Verify every batch operation (bulk dispatch, bulk invoice, bulk "
            "status change) supports undo for at least 30 minutes."
        ),
        penalty=-5,
    ),
    "S5": FrictionRule(
        id="S5",
        title="Auto-Save of In-Progress Work",
        severity="soft",
        description=(
            "Any multi-field form must auto-save draft state at ≤60-second "
            "intervals. Losing in-progress work due to navigation or crash is "
            "unacceptable."
        ),
        check_description=(
            "Verify every multi-field form auto-saves draft state at "
            "≤60-second intervals; losing in-progress work due to navigation "
            "or crash is unacceptable."
        ),
        penalty=-5,
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Combined lookup + platform-only capability inventories (for R3/R4 tests)
# ─────────────────────────────────────────────────────────────────────────────

RULES: dict[str, FrictionRule] = {**HARD_RULES, **SOFT_RULES}

# Capabilities in the R3 driver-only workflow (blueprint §6 R3 / §2 Persona 4 /
# §4 parity matrix) that must be completable on the mobile platform alone —
# i.e. without ever accessing the desktop application.
MOBILE_ONLY_CAPABILITIES: list[str] = [
    "trip_status_update",        # Loading / In Transit / Delivered transitions
    "route_navigation",          # view route + turn-by-turn navigation
    "cmr_document_upload",       # photo of signed CMR
    "pod_document_upload",       # proof-of-delivery photo upload
    "expense_submission",        # fuel / parking expense + receipt photo
    "maintenance_fault_reporting",  # report a vehicle issue via mobile
    "dispatch_notification",     # receive assignment push notification
    "trip_details_view",         # view assigned trip / next assignment details
]

# Capabilities in the R4 accountant workflow (blueprint §6 R4 / §2 Persona 5 /
# §3.5 Invoice workflow) that must be completable on the desktop platform
# alone — i.e. without ever accessing the mobile application.
DESKTOP_ONLY_CAPABILITIES: list[str] = [
    "invoice_editing",           # full invoice line-item / VAT editing
    "invoice_finalization",      # finalize invoice, generate PDF
    "receipt_generation",        # auto-generate receipt on payment
    "payment_recording",         # record / confirm invoice payment
    "dunning_management",        # overdue review + dunning reminder approval
    "financial_reporting",       # reports, VAT reconciliation, month-end review
]
