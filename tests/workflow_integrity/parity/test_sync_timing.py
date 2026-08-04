"""Platform parity: Sync timing measurements."""
from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.parity


class TestSyncTiming:
    """Measure latency of common operations."""

    def test_trip_creation_under_500ms(self, workflow_env, db):
        """Trip creation must complete within 500ms."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        start = time.perf_counter()
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"Trip creation took {elapsed:.3f}s"
        assert trip_id > 0

    def test_status_transition_under_500ms(self, workflow_env, db):
        """Status transition must complete within 500ms."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        start = time.perf_counter()
        result = workflow_env.transition_status(trip_id, "Loading")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"Transition took {elapsed:.3f}s"
        assert result is True or result is not None
