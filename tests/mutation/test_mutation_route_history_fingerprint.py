from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from services.route_history_service import RouteHistoryRecord, RouteHistoryService

pytestmark = pytest.mark.mutation


class TestKillMutationBuildFingerprint:
    """Kill common mutations in RouteHistoryService.build_fingerprint."""

    @pytest.fixture
    def service(self):
        svc = RouteHistoryService(MagicMock())
        svc._route_repo = MagicMock()
        svc._event_repo = MagicMock()
        svc._assignment_repo = MagicMock()
        return svc

    @pytest.fixture
    def base_record(self) -> RouteHistoryRecord:
        return RouteHistoryRecord(
            stops=[
                {"lat": 48.8566, "lon": 2.3522, "address": "Paris"},
                {"lat": 44.4268, "lon": 26.1025, "address": "Bucharest"},
            ],
            profile="truck",
            truck_id="TRUCK-001",
            excluded_countries=["UA", "MD"],
            metadata_version=1,
        )

    # ── 1. Different stop order → different fingerprint (sort mutation) ──
    def test_different_stop_order_different_fingerprint(self, service):
        """If a mutation sorts stops before fingerprinting, swapped
        stop order would produce the same hash. This test ensures they differ."""
        record_a = RouteHistoryRecord(
            stops=[
                {"lat": 48.8566, "lon": 2.3522, "address": "Paris"},
                {"lat": 44.4268, "lon": 26.1025, "address": "Bucharest"},
            ],
            profile="truck",
            truck_id="TRUCK-001",
        )
        record_b = RouteHistoryRecord(
            stops=[
                {"lat": 44.4268, "lon": 26.1025, "address": "Bucharest"},
                {"lat": 48.8566, "lon": 2.3522, "address": "Paris"},
            ],
            profile="truck",
            truck_id="TRUCK-001",
        )
        fp_a = service.build_fingerprint(record_a)
        fp_b = service.build_fingerprint(record_b)
        assert fp_a != fp_b, (
            "Swapped stop order must produce a different fingerprint. "
            "If a mutation sorts stops alphabetically this will fail."
        )

    # ── 2. Different profile → different fingerprint ──
    def test_different_profile_different_fingerprint(self, service, base_record):
        """If profile is removed from the fingerprint key, truck vs car
        routes would collide."""
        record_truck = base_record
        record_car = RouteHistoryRecord(
            stops=base_record.stops,
            profile="car",
            truck_id=base_record.truck_id,
            excluded_countries=base_record.excluded_countries,
        )
        fp_truck = service.build_fingerprint(record_truck)
        fp_car = service.build_fingerprint(record_car)
        assert fp_truck != fp_car, (
            "Distinct profiles must produce different fingerprints. "
            "A mutation that drops profile from the key will fail."
        )

    # ── 3. Different truck_id → different fingerprint ──
    def test_different_truck_id_different_fingerprint(self, service, base_record):
        """Two routes identical except truck_id must have distinct fingerprints."""
        record_a = base_record
        record_b = RouteHistoryRecord(
            stops=base_record.stops,
            profile=base_record.profile,
            truck_id="TRUCK-002",
            excluded_countries=base_record.excluded_countries,
        )
        fp_a = service.build_fingerprint(record_a)
        fp_b = service.build_fingerprint(record_b)
        assert fp_a != fp_b, (
            "Different truck_id must produce different fingerprints. "
            "A mutation that drops truck_id from the key will fail."
        )

    # ── 4. Excluded countries order-independent (sorted() removal) ──
    def test_excluded_countries_order_independent(self, service, base_record):
        """The sorted() call makes ['UA','MD'] and ['MD','UA'] identical.
        A mutation that removes sorted() will break this."""
        record_ab = RouteHistoryRecord(
            stops=base_record.stops,
            profile=base_record.profile,
            truck_id=base_record.truck_id,
            excluded_countries=["UA", "MD"],
        )
        record_ba = RouteHistoryRecord(
            stops=base_record.stops,
            profile=base_record.profile,
            truck_id=base_record.truck_id,
            excluded_countries=["MD", "UA"],
        )
        fp_ab = service.build_fingerprint(record_ab)
        fp_ba = service.build_fingerprint(record_ba)
        assert fp_ab == fp_ba, (
            "Excluded countries in different order must produce the same fingerprint. "
            "A mutation that removes sorted() will fail."
        )

    # ── 5. Excluded countries case-normalized (.upper() removal) ──
    def test_excluded_countries_case_normalized(self, service, base_record):
        """The .upper() call makes ['ua','md'] match ['UA','MD'].
        A mutation that removes .upper() will break this."""
        record_upper = RouteHistoryRecord(
            stops=base_record.stops,
            profile=base_record.profile,
            truck_id=base_record.truck_id,
            excluded_countries=["UA", "MD"],
        )
        record_lower = RouteHistoryRecord(
            stops=base_record.stops,
            profile=base_record.profile,
            truck_id=base_record.truck_id,
            excluded_countries=["ua", "md"],
        )
        fp_upper = service.build_fingerprint(record_upper)
        fp_lower = service.build_fingerprint(record_lower)
        assert fp_upper == fp_lower, (
            "Case-different but semantically equivalent country codes "
            "must produce the same fingerprint. A mutation that removes "
            ".upper() will fail."
        )

    # ── 6. Fingerprint is deterministic (same input → same output, 64 hex chars) ──
    def test_fingerprint_is_deterministic(self, service, base_record):
        """Same input must always produce the same 64-char hex SHA-256 digest."""
        fp1 = service.build_fingerprint(base_record)
        fp2 = service.build_fingerprint(base_record)
        assert fp1 == fp2, "Deterministic fingerprint must be identical on repeated calls."
        assert isinstance(fp1, str), "Fingerprint must be a string."
        assert len(fp1) == 64, "SHA-256 hex digest must be exactly 64 characters."
        assert all(c in "0123456789abcdef" for c in fp1), (
            "Hex digest must contain only hex characters."
        )
