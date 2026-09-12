"""Definitive catalog of mandatory telemetry events (blueprint §14.1) and
the TEL assertion requirements (blueprint §14.2).

This module is the single source of truth for the Workflow Integrity Test
Suite: every critical workflow event defined in the Product Constitution must
appear here with its exact required fields, and every TEL-01..TEL-16 assertion
must map to the description in the architecture blueprint.

Reference: docs/blueprints/workflow_integrity_test_suite_architecture.md
Section 14 "Telemetry & Observability Assertions".
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EventSchema:
    """Schema for a mandatory telemetry event.

    Attributes:
        event_name: The event identifier published on the event bus,
            e.g. ``"workflow.started"``.
        required_fields: Every field that must be present in the event
            payload for the event to count as observable. Parenthetical
            annotations in the blueprint (e.g. "stack_trace (if available)")
            describe permitted field values, not additional fields.
    """

    event_name: str
    required_fields: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# §14.1 — Mandatory Telemetry Events (exact fields from the blueprint table)
# ---------------------------------------------------------------------------
EVENT_CATALOG: dict[str, EventSchema] = {
    schema.event_name: schema
    for schema in [
        EventSchema(
            "workflow.started",
            [
                "workflow_id",
                "workflow_type",
                "company_id",
                "user_id",
                "timestamp",
                "correlation_id",
            ],
        ),
        EventSchema(
            "workflow.completed",
            [
                "workflow_id",
                "workflow_type",
                "duration_ms",
                "result",
                "summary",
            ],
        ),
        EventSchema(
            "workflow.failed",
            [
                "workflow_id",
                "workflow_type",
                "failure_step",
                "error_type",
                "error_message",
                "stack_trace",
            ],
        ),
        EventSchema(
            "rollback.executed",
            [
                "workflow_id",
                "plan_id",
                "rollback_reason",
                "completed_steps_rolled_back",
            ],
        ),
        EventSchema(
            "retry.triggered",
            [
                "operation_type",
                "attempt_number",
                "max_attempts",
                "error_message",
                "next_retry_at",
            ],
        ),
        EventSchema(
            "external_api.failed",
            [
                "api_name",
                "endpoint",
                "status_code",
                "duration_ms",
                "error_message",
            ],
        ),
        EventSchema(
            "ocr.low_confidence",
            [
                "document_id",
                "confidence_score",
                "engine",
                "critical_fields_present",
                "validation_score",
            ],
        ),
        EventSchema(
            "invoice.generation_failed",
            [
                "trip_id",
                "failure_reason",
                "attempted_by",
            ],
        ),
        EventSchema(
            "tenant.isolation_violation_attempt",
            [
                "source_company_id",
                "target_company_id",
                "attempted_operation",
                "blocked_by",
            ],
        ),
        EventSchema(
            "argo.tool_denied",
            [
                "tool_name",
                "reason",
                "permission_level",
                "requested_action",
                "user_role",
            ],
        ),
        EventSchema(
            "argo.plan_interrupted",
            [
                "plan_id",
                "completed_steps",
                "failed_step",
                "interruption_reason",
                "requires_human",
            ],
        ),
        EventSchema(
            "sync.conflict_detected",
            [
                "entity_type",
                "entity_id",
                "device_a_value",
                "device_b_value",
                "resolution",
                "resolution_strategy",
            ],
        ),
        EventSchema(
            "maintenance.dispatch_blocked",
            [
                "truck_id",
                "trip_id",
                "maintenance_ticket_id",
                "severity",
                "reassigned_to",
            ],
        ),
        EventSchema(
            "financial.invariant_violation",
            [
                "invariant_id",
                "entity_type",
                "entity_id",
                "expected_value",
                "actual_value",
                "discrepancy",
            ],
        ),
        EventSchema(
            "history.immutability_violation_attempt",
            [
                "entity_type",
                "entity_id",
                "field_name",
                "attempted_change",
                "blocked_by",
            ],
        ),
    ]
}


def validate_event(event: dict) -> list[str]:
    """Return the list of required fields missing from ``event``.

    An empty list means the event satisfies its catalogued schema.  Events
    whose ``event_name`` is not part of the mandatory catalog are considered
    out of scope and return ``[]`` (they are not subject to §14.1 fields).
    """
    event_name = event.get("event_name")
    schema = EVENT_CATALOG.get(event_name)
    if schema is None:
        return []
    return [field_name for field_name in schema.required_fields if field_name not in event]


# ---------------------------------------------------------------------------
# §14.2 — Telemetry Test Requirements (TEL-01 through TEL-16)
# ---------------------------------------------------------------------------
TEL_ASSERTIONS: dict[str, str] = {
    "TEL-01": "Every golden workflow (3.1-3.10) emits workflow.started and either workflow.completed or workflow.failed",
    "TEL-02": "Every workflow failure emits workflow.failed with a non-null failure_step and error_message",
    "TEL-03": "Every ARGO multi-step plan emits exactly one workflow.started and one workflow.completed or workflow.failed",
    "TEL-04": "Every external API timeout (8.5.1-8.5.10) emits external_api.failed with correct api_name and status_code",
    "TEL-05": "Every OCR extraction below auto-link threshold emits ocr.low_confidence with the correct confidence_score",
    "TEL-06": "Every invoice generation failure emits invoice.generation_failed with the correct failure_reason",
    "TEL-07": "Every blocked cross-tenant access emits tenant.isolation_violation_attempt",
    "TEL-08": "Every ARGO tool call denied by permission gate emits argo.tool_denied",
    "TEL-09": "Every sync conflict detected and resolved emits sync.conflict_detected with resolution strategy",
    "TEL-10": "Every maintenance dispatch block emits maintenance.dispatch_blocked",
    "TEL-11": "Every detected financial invariant violation emits financial.invariant_violation",
    "TEL-12": "Every attempt to mutate a historical record emits history.immutability_violation_attempt",
    "TEL-13": "Every retry (reliability scenarios) emits retry.triggered with correct attempt_number",
    "TEL-14": "All telemetry events include correlation_id that links to the originating workflow",
    "TEL-15": "All telemetry events include company_id for multi-tenant routing",
    "TEL-16": "Telemetry must be available for query within 30 seconds of event emission",
}