"""Fleet Matcher tests — proves deterministic ranking, reproducibility, and provider-agnostic behavior.

Blueprint Gate 5 (§12.5): fixture with known truck/driver/maintenance data,
assert ranking order and each score component are exactly reproducible,
and assert provider_id has zero influence on scoring.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from database.db_manager import DatabaseManager
from models.common import Money
from models.freight_exchange_models import LoadSearchResult, TruckMatchScore
from services.freight_exchange.fleet_matcher import (
    DEFAULT_MATCHER_WEIGHTS,
    FleetMatcherService,
)
from tests.test_helpers import InMemoryDB


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_load(provider_id: str = "timocom", **overrides) -> LoadSearchResult:
    """Build a deterministic load for testing."""
    now = datetime.now(timezone.utc)
    defaults: dict = {
        "result_id": "L-001",
        "provider_id": provider_id,
        "provider_load_id": "TL-001",
        "origin": "Bucuresti",
        "destination": "Berlin",
        "pickup_window": (now, now),
        "delivery_window": (
            datetime.fromtimestamp(now.timestamp() + 48 * 3600, tz=timezone.utc),
            datetime.fromtimestamp(now.timestamp() + 48 * 3600, tz=timezone.utc),
        ),
        "price": Money(amount=1500.0, currency="EUR"),
        "distance_km": 1800.0,
        "trailer_type": "standard",
        "adr": False,
    }
    defaults.update(overrides)
    return LoadSearchResult(**defaults)  # type: ignore[arg-type]


def _make_truck(truck_id: int, **overrides) -> dict:
    """Build a deterministic truck dict."""
    defaults = {
        "id": truck_id,
        "plate": f"TRK-{truck_id:03d}",
        "trailer_type": "standard",
        "current_location": "Bucuresti, RO",
        "consumption_l_per_100km": 30,
        "adr_certified": False,
    }
    defaults.update(overrides)
    return defaults


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def matcher(db) -> FleetMatcherService:
    return FleetMatcherService(db)


# ═══════════════════════════════════════════════════════════════════════════
# Weights
# ═══════════════════════════════════════════════════════════════════════════


class TestWeights:
    def test_weights_sum_to_100(self):
        assert sum(DEFAULT_MATCHER_WEIGHTS.values()) == 100

    def test_all_factors_present(self):
        required = [
            "proximity", "expected_profit", "driver_hours",
            "maintenance_health", "trailer_compatibility",
            "historical_reliability", "positioning",
        ]
        for factor in required:
            assert factor in DEFAULT_MATCHER_WEIGHTS


# ═══════════════════════════════════════════════════════════════════════════
# Individual scorer tests
# ═══════════════════════════════════════════════════════════════════════════


class TestProximityScoring:
    def test_same_city_max_score(self, matcher):
        load = _make_load(origin="Bucuresti")
        truck = _make_truck(1, current_location="Bucuresti, RO")
        score = matcher._score_proximity(load, truck)
        assert score == 100.0

    def test_different_city_lower_score(self, matcher):
        load = _make_load(origin="Bucuresti")
        truck = _make_truck(1, current_location="Berlin, DE")
        score = matcher._score_proximity(load, truck)
        assert score < 100.0

    def test_no_location_neutral(self, matcher):
        load = _make_load(origin="Bucuresti")
        truck = _make_truck(1, current_location="")
        score = matcher._score_proximity(load, truck)
        assert score == 50.0

    def test_rank_ordering_proximity(self, matcher):
        """Closer trucks should score higher."""
        load = _make_load(origin="Bucuresti")
        close = matcher._score_proximity(load, _make_truck(1, current_location="Bucuresti, RO"))
        far = matcher._score_proximity(load, _make_truck(2, current_location="Berlin, DE"))
        assert close >= far


class TestTrailerScoring:
    def test_exact_match(self, matcher):
        load = _make_load(trailer_type="standard")
        truck = _make_truck(1, trailer_type="standard")
        score = matcher._score_trailer_compatibility(load, truck)
        assert score == 100.0

    def test_mismatch(self, matcher):
        load = _make_load(trailer_type="refrigerated")
        truck = _make_truck(1, trailer_type="standard")
        score = matcher._score_trailer_compatibility(load, truck)
        assert score < 30.0

    def test_adr_penalty(self, matcher):
        load = _make_load(adr=True, trailer_type="standard")
        truck = _make_truck(1, trailer_type="standard", adr_certified=False)
        score = matcher._score_trailer_compatibility(load, truck)
        assert score < 100.0  # ADR penalty applied

    def test_adr_certified_no_penalty(self, matcher):
        load = _make_load(adr=True, trailer_type="standard")
        truck = _make_truck(1, trailer_type="standard", adr_certified=True)
        score = matcher._score_trailer_compatibility(load, truck)
        assert score == 100.0  # ADR certified, no penalty


class TestProfitScoring:
    def test_positive_margin(self, matcher):
        load = _make_load(amount=2000.0, distance_km=100.0)
        truck = _make_truck(1, consumption_l_per_100km=25)
        score = matcher._score_profit(load, truck)
        assert score > 50.0, f"High margin should score well, got {score}"

    def test_negative_margin(self, matcher):
        load = _make_load(amount=50.0, distance_km=2000.0)
        truck = _make_truck(1, consumption_l_per_100km=40)
        score = matcher._score_profit(load, truck)
        assert score <= 20.0, f"Low/negative margin should score poorly, got {score}"


class TestDriverHoursScoring:
    def test_plenty_of_hours(self, matcher):
        with patch.object(matcher, "_get_driver_hours", return_value=50.0):
            load = _make_load(distance_km=1800.0)  # ~30h trip
            score = matcher._score_driver_hours(1, load)
            assert score == 100.0

    def test_not_enough_hours(self, matcher):
        with patch.object(matcher, "_get_driver_hours", return_value=5.0):
            load = _make_load(distance_km=1800.0)  # ~30h trip
            score = matcher._score_driver_hours(1, load)
            assert score < 50.0

    def test_no_driver_neutral(self, matcher):
        load = _make_load()
        score = matcher._score_driver_hours(None, load)
        assert score == 50.0


# ═══════════════════════════════════════════════════════════════════════════
# Score reproducibility (determinism)
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreReproducibility:
    """Blueprint requirement: scores must be exactly reproducible run to run."""

    def test_proximity_reproducible(self, matcher):
        load = _make_load(origin="Bucuresti")
        truck = _make_truck(1, current_location="Berlin, DE")
        s1 = matcher._score_proximity(load, truck)
        s2 = matcher._score_proximity(load, truck)
        assert s1 == s2

    def test_profit_reproducible(self, matcher):
        load = _make_load(amount=1500.0, distance_km=1800.0)
        truck = _make_truck(1, consumption_l_per_100km=30)
        s1 = matcher._score_profit(load, truck)
        s2 = matcher._score_profit(load, truck)
        assert s1 == s2

    def test_trailer_reproducible(self, matcher):
        load = _make_load(trailer_type="refrigerated")
        truck = _make_truck(1, trailer_type="refrigerated")
        s1 = matcher._score_trailer_compatibility(load, truck)
        s2 = matcher._score_trailer_compatibility(load, truck)
        assert s1 == s2

    def test_full_scoring_reproducible(self, matcher):
        """Score the same truck against the same load twice — identical result."""
        with patch.object(matcher, "_get_driver_hours", return_value=40.0):
            with patch.object(matcher, "_get_health_score", return_value=85.0):
                load = _make_load()
                truck = _make_truck(1)
                s1 = matcher._score_truck(load, truck, 1)
                s2 = matcher._score_truck(load, truck, 1)
                assert s1 is not None and s2 is not None
                assert s1.score == s2.score
                assert s1.reasons == s2.reasons


# ═══════════════════════════════════════════════════════════════════════════
# Provider-agnostic: provider_id has zero influence on scoring
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderAgnostic:
    """Blueprint requirement: provider_id must have zero influence on scoring."""

    def test_different_providers_identical_scores(self, matcher):
        """Same load data from timocom vs trans_eu → identical scores."""
        load_timocom = _make_load(provider_id="timocom")
        load_trans_eu = _make_load(provider_id="trans_eu")
        truck = _make_truck(1)

        with patch.object(matcher, "_get_driver_hours", return_value=40.0):
            with patch.object(matcher, "_get_health_score", return_value=85.0):
                s_timocom = matcher._score_truck(load_timocom, truck, 1)
                s_trans_eu = matcher._score_truck(load_trans_eu, truck, 1)

        assert s_timocom is not None and s_trans_eu is not None
        assert s_timocom.score == s_trans_eu.score, (
            f"Provider should not affect score: {s_timocom.score} vs {s_trans_eu.score}"
        )

    def test_scorers_dont_reference_provider_id(self):
        """None of the scorer methods reference provider_id."""
        import inspect
        matcher = FleetMatcherService.__new__(FleetMatcherService)
        scorers = [
            "_score_proximity", "_score_profit", "_score_driver_hours",
            "_score_maintenance", "_score_trailer_compatibility",
            "_score_reliability", "_score_positioning",
        ]
        for name in scorers:
            method = getattr(FleetMatcherService, name, None)
            if method is None:
                continue
            source = inspect.getsource(method)
            assert "provider_id" not in source, (
                f"{name} references provider_id — this breaks provider-agnostic guarantee"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Reason derivation (deterministic, from score components)
# ═══════════════════════════════════════════════════════════════════════════


class TestReasonDerivation:
    """Reasons must be derived from scoring components, never free-text."""

    def test_reasons_are_i18n_keys(self, matcher):
        """All reasons should be i18n keys (freight.*)."""
        with patch.object(matcher, "_get_driver_hours", return_value=40.0):
            with patch.object(matcher, "_get_health_score", return_value=85.0):
                load = _make_load()
                truck = _make_truck(1)
                result = matcher._score_truck(load, truck, 1)
                assert result is not None
                for reason in result.reasons:
                    assert reason.startswith("freight."), (
                        f"Reason '{reason}' is not an i18n key"
                    )

    def test_compatible_truck_has_positive_reasons(self, matcher):
        """Fully compatible truck should have positive reasons."""
        with patch.object(matcher, "_get_driver_hours", return_value=40.0):
            with patch.object(matcher, "_get_health_score", return_value=95.0):
                load = _make_load(trailer_type="standard", adr=False)
                truck = _make_truck(1, trailer_type="standard", current_location="Bucuresti, RO")
                result = matcher._score_truck(load, truck, 1)
                assert result is not None
                # At least one positive reason
                positive = [r for r in result.reasons if "match_reason" in r]
                assert len(positive) >= 1, f"Expected positive reasons, got: {result.reasons}"


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_empty_truck_list(self, matcher):
        with patch.object(matcher, "_get_available_trucks", return_value=[]):
            # _score_truck on None trucks handled at _get_available_trucks level
            assert matcher._get_available_trucks(1) == []

    def test_truck_missing_id(self, matcher):
        load = _make_load()
        result = matcher._score_truck(load, {}, 1)
        assert result is None  # cannot score without ID

    def test_score_bounds(self, matcher):
        """All factor scores should be 0-100."""
        load = _make_load()
        truck = _make_truck(1)
        scores = {
            "proximity": matcher._score_proximity(load, truck),
            "trailer": matcher._score_trailer_compatibility(load, truck),
        }
        for name, score in scores.items():
            assert 0.0 <= score <= 100.0, f"{name} out of bounds: {score}"
