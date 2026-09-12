"""Schema-validity tests for the mandatory telemetry event catalog (§14.1).

Every event in ``EVENT_CATALOG`` (see ``event_catalog.py``) is exercised:
a payload carrying all required fields must pass schema validation (via
``TelemetrySpy.assert_schema``, which is resilient to the EventBus capture
shape ``{type, data}``), and a payload missing exactly one required field
must be reported with *that* field by ``event_catalog.validate_event``.

Parametrization over ``EVENT_CATALOG`` guarantees every catalog event is
covered; a meta-test introspects the parametrize markers to assert that
coverage explicitly.
"""
from __future__ import annotations

from typing import Any

import pytest

pytest_plugins = ["tests.workflow_integrity.telemetry.fixtures"]

pytestmark = pytest.mark.telemetry

from tests.workflow_integrity.telemetry.event_catalog import (  # noqa: E402
    EVENT_CATALOG,
    EventSchema,
    validate_event,
)

CATALOG_EVENT_NAMES = list(EVENT_CATALOG.keys())


# ---------------------------------------------------------------------------
# Plausible payload builder (single source of truth for sample values)
# ---------------------------------------------------------------------------

# Plausible values keyed by catalog field name.  Unknown fields fall back
# to a generated string so new catalog additions stay covered automatically.
_FIELD_SAMPLES: dict[str, Any] = {
    # workflow.started
    "workflow_id": "wf-2026-0001",
    "workflow_type": "trip_dispatch",
    "company_id": 7,
    "user_id": 3,
    "timestamp": "2026-07-21T12:00:00Z",
    "correlation_id": "corr-2026-0001",
    # workflow.completed
    "duration_ms": 1234,
    "result": "success",
    "summary": "Trip dispatched in 1234ms",
    # workflow.failed
    "failure_step": "dispatch",
    "error_type": "TimeoutError",
    "error_message": "SMTP unreachable",
    "stack_trace": "Traceback (most recent call last): ...",
    # rollback.executed
    "plan_id": "plan-42",
    "rollback_reason": "Invalid transition Planned->Delivered",
    "completed_steps_rolled_back": 2,
    # retry.triggered
    "operation_type": "invoice.send",
    "attempt_number": 1,
    "max_attempts": 3,
    "next_retry_at": "2026-07-21T12:05:00Z",
    # external_api.failed
    "api_name": "smtp",
    "endpoint": "/send",
    "status_code": 503,
    # ocr.low_confidence
    "document_id": "doc-001",
    "confidence_score": 0.42,
    "engine": "tesseract",
    "critical_fields_present": ["cmr_number"],
    "validation_score": 0.61,
    # invoice.generation_failed
    "trip_id": 101,
    "failure_reason": "invoice_number_sequence_exhausted",
    "attempted_by": "user-3",
    # tenant.isolation_violation_attempt
    "source_company_id": 7,
    "target_company_id": 12,
    "attempted_operation": "read_trips",
    "blocked_by": "tenant_isolation_gate",
    # argo.tool_denied
    "tool_name": "dispatch_tool",
    "reason": "insufficient permission",
    "permission_level": "dispatch:write",
    "requested_action": "create_dispatch",
    "user_role": "driver",
    # argo.plan_interrupted
    "completed_steps": 2,
    "interruption_reason": "circuit_breaker_tripped",
    "requires_human": True,
    # sync.conflict_detected
    "entity_type": "trip",
    "entity_id": "101",
    "device_a_value": "planned",
    "device_b_value": "delivered",
    "resolution": "server_wins",
    "resolution_strategy": "manual_review",
    # maintenance.dispatch_blocked
    "truck_id": 55,
    "maintenance_ticket_id": 8,
    "severity": "critical",
    "reassigned_to": 0,
    # financial.invariant_violation
    "invariant_id": "invoice-total-matches",
    "expected_value": 120.00,
    "actual_value": 118.50,
    "discrepancy": 1.50,
    # history.immutability_violation_attempt
    "field_name": "status",
    "attempted_change": "UPDATE invoices SET status='paid'",
    # entity fields (shared)
    "blocked_by": "immutability_gate",
    "failed_step": "invoicing",
}


def build_valid_payload(schema: EventSchema) -> dict[str, Any]:
    """Return a payload containing every required field of *schema*."""
    return {
        field: _FIELD_SAMPLES.get(field, f"<{field}>")
        for field in schema.required_fields
    }


def build_payload_missing(schema: EventSchema, missing_field: str) -> dict[str, Any]:
    """Return a payload with all required fields except *missing_field*."""
    return {
        field: _FIELD_SAMPLES.get(field, f"<{field}>")
        for field in schema.required_fields
        if field != missing_field
    }


def _parametrized_arg_values(func) -> list[str]:
    """Collect the first arg value of every ``parametrize`` marker on *func*."""
    values: list[str] = []
    for mark in getattr(func, "pytestmark", []):
        if getattr(mark, "name", None) != "parametrize":
            continue
        args = mark.args
        if len(args) < 2:
            continue
        for param_set in args[1]:
            vals = getattr(param_set, "values", None)
            values.append(vals[0] if vals else str(param_set))
    return values


# ---------------------------------------------------------------------------
# Valid payload: schema validation must pass (no missing fields)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("event_name", CATALOG_EVENT_NAMES)
def test_valid_payload_passes_schema(event_name: str, telemetry_spy, event_bus):
    """Publishing an event with all required fields passes schema validation."""
    schema = EVENT_CATALOG[event_name]
    payload = build_valid_payload(schema)

    event_bus.publish(event_name, payload)
    telemetry_spy.assert_events(event_name)

    # TelemetrySpy.assert_schema is resilient to the EventBus capture shape
    # (it flattens {type, data} captures before delegating to validate_event).
    telemetry_spy.assert_schema(event_name)

    # Direct check against the flat event shape as well.
    assert validate_event({"event_name": event_name, **payload}) == []


# ---------------------------------------------------------------------------
# Missing required field: validate_event must report exactly that field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("event_name", CATALOG_EVENT_NAMES)
def test_missing_required_field_is_reported(
    event_name: str, telemetry_spy, event_bus
):
    """Publishing an event without one required field reports that field."""
    schema = EVENT_CATALOG[event_name]
    missing_field = schema.required_fields[0]
    payload = build_payload_missing(schema, missing_field)

    # Direct validation reports exactly the missing field.
    assert validate_event({"event_name": event_name, **payload}) == [missing_field]

    # The spy (capture-shape-resilient) must also surface the missing field.
    event_bus.publish(event_name, payload)
    telemetry_spy.assert_events(event_name)
    with pytest.raises(AssertionError, match=missing_field):
        telemetry_spy.assert_schema(event_name)


# ---------------------------------------------------------------------------
# Every catalog event is exercised (parametrization coverage guarantee)
# ---------------------------------------------------------------------------


def test_every_catalog_event_is_exercised() -> None:
    """The parametrized schema tests cover the full ``EVENT_CATALOG``."""
    expected = set(EVENT_CATALOG)
    for test_name in (
        "test_valid_payload_passes_schema",
        "test_missing_required_field_is_reported",
    ):
        covered = set(_parametrized_arg_values(globals()[test_name]))
        assert covered == expected, (
            f"{test_name} must cover every catalog event; missing: "
            f"{sorted(expected - covered)}"
        )
    assert len(EVENT_CATALOG) >= 15