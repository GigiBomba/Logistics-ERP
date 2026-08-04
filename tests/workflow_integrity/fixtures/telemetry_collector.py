"""TelemetryCollector — captures telemetry events during test execution for verification.

Wraps the EventBus to collect all published events and provides assertions
for verifying required telemetry coverage per the TEL standards.
"""

from __future__ import annotations

from typing import Any
from services.operations.event_bus import EventBus


# Required telemetry events per the Product Constitution Section 14
REQUIRED_TELEMETRY_EVENTS = [
    "workflow.started", "workflow.completed", "workflow.failed",
    "rollback.executed", "retry.triggered", "external_api.failed",
    "ocr.low_confidence", "invoice.generation_failed",
    "tenant.isolation_violation_attempt", "argo.tool_denied",
    "argo.plan_interrupted", "sync.conflict_detected",
    "maintenance.dispatch_blocked", "financial.invariant_violation",
    "history.immutability_violation_attempt",
]


class TelemetryCollector:
    """Captures and asserts on telemetry events during a test run."""

    def __init__(self, event_bus: EventBus | None = None):
        self._bus = event_bus if event_bus is not None else EventBus()
        self._events: list[dict[str, Any]] = []
        self._subscribed: bool = False

    def start(self) -> None:
        """Subscribe to all required telemetry events."""
        if not self._subscribed:
            for evt in REQUIRED_TELEMETRY_EVENTS:
                self._bus.subscribe(evt, self._collect)
            self._subscribed = True
        self._events.clear()

    def _collect(self, event: dict[str, Any]) -> None:
        self._events.append(event)

    def stop(self) -> list[dict[str, Any]]:
        """Stop collecting and return all captured events."""
        return self._events

    def get_events(self, event_type: str | None = None) -> list[dict[str, Any]]:
        if event_type is None:
            return list(self._events)
        return [e for e in self._events if e.get("type") == event_type]

    def assert_all_required_events_fired(self) -> None:
        """Assert that every required telemetry event fired at least once."""
        fired = set(e.get("type") for e in self._events)
        missing = [e for e in REQUIRED_TELEMETRY_EVENTS if e not in fired]
        if missing:
            raise AssertionError(f"Missing required telemetry events: {missing}")

    def assert_event_fired(self, event_type: str) -> None:
        if not any(e.get("type") == event_type for e in self._events):
            raise AssertionError(f"Required telemetry event '{event_type}' was not fired")
