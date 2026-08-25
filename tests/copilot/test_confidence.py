"""Confidence engine tests — threshold boundaries and weighted formula.

Blueprint: §10 — Confidence Engine (concrete formula, not a label).
"""
from __future__ import annotations


import pytest

from backend.copilot.schemas import Entity, Intent
from backend.copilot.confidence import (
    compute_confidence,
    confidence_bucket,
    needs_clarification,
    needs_recap,
    HIGH_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
    DEFAULT_WEIGHTS,
)


def _intent(name="test", entities=None, missing=None, raw="test"):
    return Intent(name=name, entities=entities or [], missing_required_entities=missing or [], raw_utterance=raw)


class TestConfidenceFormula:
    def test_weights_sum_to_one(self):
        total = sum(DEFAULT_WEIGHTS.values())
        assert pytest.approx(total, abs=0.001) == 1.0, f"Weights sum to {total}, expected 1.0"

    def test_perfect_confidence(self):
        intent = _intent(entities=[Entity(type="x", value="y", source="extracted", confidence=1.0)])
        score = compute_confidence(intent, intent_match_score=1.0, historical_success_rate=1.0)
        assert score == pytest.approx(1.0)

    def test_minimum_confidence(self):
        """Even with zero intent_match and zero historical data, the minimum score is
        0.20 because entity_confidence_avg defaults to 1.0 when there are no entities
        (w3=0.20 × 1.0 = 0.20). This is intentional — a floor that prevents the score
        from collapsing to absolute zero when entity extraction simply produced nothing."""
        intent = _intent(missing=["x"])
        score = compute_confidence(intent, intent_match_score=0.0, historical_success_rate=0.0)
        assert score == pytest.approx(0.20)

    def test_mid_range_confidence(self):
        intent = _intent(entities=[Entity(type="x", value="y", source="extracted", confidence=0.7)], missing=["z"])
        score = compute_confidence(intent, intent_match_score=0.8, historical_success_rate=0.75)
        assert 0.3 < score < 0.9, f"Expected mid-range, got {score}"

    def test_no_entities_perfect_completeness(self):
        intent = _intent(entities=[], missing=[])
        score = compute_confidence(intent, intent_match_score=1.0, historical_success_rate=1.0)
        assert score == pytest.approx(1.0)


class TestThresholdBoundaries:
    """§10 requires testing at each boundary: 0.549, 0.55, 0.849, 0.85."""

    def test_below_medium_is_low(self, subtests):
        assert confidence_bucket(0.549) == "low"
        assert needs_clarification(0.549) is True
        assert needs_recap(0.549) is False

    def test_at_medium_is_medium(self):
        assert confidence_bucket(0.55) == "medium"
        assert needs_clarification(0.55) is False
        assert needs_recap(0.55) is True

    def test_at_high_boundary(self):
        assert confidence_bucket(0.849) == "medium"
        assert needs_clarification(0.849) is False
        assert needs_recap(0.849) is True

    def test_at_high_is_high(self):
        assert confidence_bucket(0.85) == "high"
        assert needs_clarification(0.85) is False
        assert needs_recap(0.85) is False

    def test_above_high(self):
        assert confidence_bucket(0.95) == "high"
        assert needs_clarification(0.95) is False
        assert needs_recap(0.95) is False


class TestHistoricalSuccessRateDefault:
    def test_default_0_75(self):
        """Historical success rate defaults to 0.75 when <10 samples exist (§10, §22)."""
        intent = _intent(entities=[Entity(type="x", value="y", source="extracted", confidence=0.8)])
        score = compute_confidence(intent, intent_match_score=0.9)
        assert score < 1.0
        assert score > 0.5
