"""TEL-16 (blueprint §14.4): telemetry must be queryable within 30s of emission.

This module implements the blueprint §14.2 TEL-16 assertion
("Telemetry must be available for query within 30 seconds of event emission")
against the suite's in-process pipeline: the ``telemetry_spy`` fixture
subscribes to every EventBus event synchronously, so by the time
``event_bus.publish()`` returns, the event is already captured and queryable.

The measured emission→capture latency is therefore expected to be in the
millisecond range (often sub-millisecond).  The assertion is deliberately
kept at the blueprint bound of 30_000 ms — the value is logged so the
millisecond reality is visible — rather than tightened to milliseconds, so a
slow CI runner cannot turn a pass into a flaky failure.  No ``time.sleep()``
is used anywhere: latency is derived from the spy's monotonic capture
timestamps.
"""
from __future__ import annotations
import logging

import pytest

pytestmark = pytest.mark.telemetry

# Register the telemetry fixtures (telemetry_spy / fake_telemetry_store) —
# see fixtures.py registration notes.
pytest_plugins = ["tests.workflow_integrity.telemetry.fixtures"]

logger = logging.getLogger(__name__)

# Blueprint §14.2 TEL-16: telemetry available for query within 30s.
TEL16_QUERY_BOUND_MS = 30_000.0

# A small batch so query_latency_ms() has a measurable capture span.
_BATCH_SIZE = 5


class TestTelemetryLatency:
    """TEL-16: telemetry must be available for query within 30 seconds of emission."""

    def test_emitted_event_queryable_within_30s(self, telemetry_spy, event_bus):
        """TEL-16: in-process emission → capture latency is below the 30s bound.

        Publishes a batch of events on the suite bus and derives the capture
        latency from the spy's monotonic capture timestamps.  In-process
        latency should be milliseconds; the assertion stays at the blueprint
        bound of 30_000 ms and the measured value is logged.
        """
        event_name = "trip.created"
        for i in range(_BATCH_SIZE):
            event_bus.publish(event_name, {"id": i})

        # The spy must have captured every published event synchronously.
        telemetry_spy.assert_events((event_name, _BATCH_SIZE))

        latency_ms = telemetry_spy.query_latency_ms(event_name)
        logger.info(
            "TEL-16: %d x %s emission->capture latency = %.3f ms "
            "(blueprint bound = %.0f ms)",
            _BATCH_SIZE,
            event_name,
            latency_ms,
            TEL16_QUERY_BOUND_MS,
        )

        assert (
            latency_ms < TEL16_QUERY_BOUND_MS
        ), (
            f"TEL-16 violated: emission->capture latency {latency_ms:.3f} ms "
            f"for {event_name} exceeds the 30s blueprint bound "
            f"({TEL16_QUERY_BOUND_MS:.0f} ms)"
        )

    def test_single_emission_queryable_immediately(self, telemetry_spy, event_bus):
        """TEL-16: a single emission is queryable as soon as publish() returns.

        Even for a lone capture the spy must report the event as captured and
        queryable (capture latency >= 0, strictly below the 30s bound).
        """
        event_name = "trip.created"
        event_bus.publish(event_name, {"id": 1})

        telemetry_spy.assert_events(event_name)
        latency_ms = telemetry_spy.query_latency_ms(event_name)
        logger.info(
            "TEL-16: single %s capture latency = %.3f ms (bound %.0f ms)",
            event_name,
            latency_ms,
            TEL16_QUERY_BOUND_MS,
        )
        assert 0.0 <= latency_ms < TEL16_QUERY_BOUND_MS, (
            f"TEL-16 violated: single-emission capture latency {latency_ms:.3f} ms "
            f"exceeds the 30s blueprint bound ({TEL16_QUERY_BOUND_MS:.0f} ms)"
        )